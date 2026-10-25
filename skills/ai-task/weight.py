"""Weight — six axes, 0 to 2 each, from .ai/policies/weight.json.

Pure computation: it reads the declared files, the tree listing and `git grep`,
and writes nothing. A measured value is a floor: the session may raise an axis
with one evidence line, never lower it; an axis nobody measured or declared is
UNKNOWN and scores `rules.unknown_scores`. docs/weight.md says why.
"""
import functools
import hashlib
import json
import os
import re
import subprocess
import time

AXES = ("scope", "behaviour", "reversibility", "domain", "novelty", "coverage")
MAX_FILES = 10           # scope is measured on the first ten declared files
GREP_SECONDS = 5.0       # the whole scope measurement's budget; past it, UNKNOWN
COMMON_SHARE = 0.25      # an identifier in more than this share of the tree is a word,
COMMON_MIN = 20          # not a reference — counted in a tree of at least this many files
TEXT_LIMIT = 1 << 20     # a keyword scan reads at most 1 MB of a declared file
# Referenced by path, not by name: a template or config file is loaded by its path.
PATH_SUFFIXES = (".twig", ".html", ".htm", ".yaml", ".yml", ".json", ".toml", ".ini",
                 ".xml", ".conf", ".cfg", ".env", ".j2", ".tpl", ".neon")
SKIP_DIRS = {".git", "node_modules", "vendor", "__pycache__"}
SHIPPED = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                       "ai-init", "templates", ".ai", "policies", "weight.json")


class Weight:
    """`w`, `axes`, `hints`, `unknown`, `evidence`, `mode`, and the `notes` --long prints."""

    def __init__(self, axes, evidence, hints, unknown, notes, mode, thresholds):
        self.axes, self.evidence, self.hints, self.unknown = axes, evidence, hints, unknown
        self.notes, self.mode, self.thresholds, self.w = notes, mode, thresholds, sum(axes.values())

    def as_dict(self):
        return {k: getattr(self, k) for k in ("w", "mode", "axes", "evidence", "hints", "unknown", "notes")}


def load_policy(root):
    """(policy, path): the project's table, else the one this plugin ships.
    A broken table raises ValueError, never a silent default."""
    own = os.path.join(root, ".ai", "policies", "weight.json")
    path = own if os.path.isfile(own) else SHIPPED
    with open(path, encoding="utf-8") as fh:
        policy = json.load(fh)
    if not isinstance(policy, dict) or not all(isinstance(policy.get(k), dict) for k in ("axes", "modes")):
        raise ValueError("%s has no axes or modes table" % path)
    return policy, path


@functools.lru_cache(maxsize=None)
def _glob_re(pattern):
    """`**` crosses directories, `*` does not, `**/` also matches none; a
    pattern without a slash matches a basename at any depth (gitignore's rule)."""
    tokens = {"**/": "(?:[^/]*/)*", "**": ".*", "*": "[^/]*", "?": "[^/]"}
    body = "".join(tokens.get(t, re.escape(t)) for t in re.split(r"(\*\*/|\*\*|\*|\?)", pattern) if t)
    return re.compile("^" + ("" if "/" in pattern else "(?:.*/)?") + body + "$")


def match(path, patterns):
    """The first pattern `path` matches, or None."""
    return next((p for p in patterns or [] if _glob_re(p).match(path)), None)


def _git(root, args, timeout):
    try:
        return subprocess.run(["git", "-C", root] + args, capture_output=True, timeout=max(timeout, 0.01), check=False)
    except (OSError, subprocess.SubprocessError):
        return None


def tree_files(root):
    """Every file, repo-relative: git's listing (untracked too, ignores honoured), else a walk."""
    done = _git(root, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], 10)
    if done is not None and done.returncode == 0:
        return sorted({p for p in done.stdout.decode("utf-8", "replace").split("\0") if p})
    found = []
    for dirpath, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        found += [os.path.relpath(os.path.join(dirpath, f), root).replace(os.sep, "/") for f in files]
    return sorted(found)


def _read(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            data = fh.read(TEXT_LIMIT)
    except OSError:
        return None
    return None if b"\0" in data[:8192] else data.decode("utf-8", "replace")


def references(root, needle, word, listing, deadline):
    """Files containing `needle` (a whole word when `word`), None past the deadline: git grep, else `listing`."""
    done = _git(root, ["grep", "-lIzwF" if word else "-lIzF", "--untracked", "-e", needle],
                deadline - time.monotonic()) if time.monotonic() < deadline else None
    if done is None and time.monotonic() >= deadline:
        return None
    if done is not None and done.returncode in (0, 1):
        return {p for p in done.stdout.decode("utf-8", "replace").split("\0") if p}
    rx = re.compile((r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" if word else "%s") % re.escape(needle))
    hits = set()
    for rel in listing:
        if time.monotonic() >= deadline:
            return None
        if rx.search(_read(root, rel) or ""):
            hits.add(rel)
    return hits


def _ident(rel):
    base = os.path.basename(rel)
    return base if base.startswith(".") else base.split(".", 1)[0]


def _scope(root, files, existing, axis, tests, listing, notes):
    """max over the declared files of their reference band; hot_paths → 2."""
    deadline, best, why, unknown = time.monotonic() + GREP_SECONDS, 0, "no references", False
    low, high = (axis.get("bands") or [0, 5])[:2]
    for n, rel in enumerate(files):
        hot = match(rel, axis.get("hot_paths"))
        if hot:
            value, line = 2, "%s matches hot_paths %s" % (rel, hot)
        elif rel not in existing:
            value, line = 0, "%s is new" % rel
        elif n >= MAX_FILES:
            value, line, unknown = 1, "%s not measured (over %d files)" % (rel, MAX_FILES), True
        else:
            by_path = rel.endswith(PATH_SUFFIXES)
            hits = references(root, rel if by_path else _ident(rel), not by_path, listing, deadline)
            if hits is None:
                value, line, unknown = 1, "%s not measured (grep budget %gs)" % (rel, GREP_SECONDS), True
            else:
                count = len({h for h in hits if h != rel and not match(h, tests)})
                if len(listing) >= COMMON_MIN and count > COMMON_SHARE * len(listing):
                    value, unknown = 1, True
                    line = "%s: '%s' is in %d of %d files — a word, not a reference" % (
                        rel, _ident(rel), count, len(listing))
                else:
                    value = 0 if count <= low else 1 if count <= high else 2
                    line = "%s referenced from %d files" % (rel, count)
        notes.append("scope: " + line)
        if value > best or (value == best and why == "no references"):
            best, why = value, line
    return best, why, unknown and best < 2


def _first(files, patterns):
    return next(((f, p) for f in files for p in [match(f, patterns)] if p), None)


def _measure(root, files, goal, policy, listing, notes):
    """{axis: (value, evidence, unknown)} before hints and declarations; an
    axis only the session can judge is absent."""
    axes = policy["axes"]
    existing = {f for f in files if os.path.isfile(os.path.join(root, f))}
    tests = (axes.get("coverage") or {}).get("test_globs") or []
    tests_only = bool(files) and all(match(f, tests) for f in files)
    out = {"scope": _scope(root, files, existing, axes.get("scope") or {}, tests, listing, notes)}

    keywords = (axes.get("behaviour") or {}).get("keywords") or []
    kw_hit = next(("keyword '%s' in %s" % (kw, source)
                   for source, text in [("the goal", goal)] + [(f, _read(root, f)) for f in sorted(existing)]
                   for kw in keywords if text and re.search(r"\b%s\b" % re.escape(kw), text, re.I)), None)
    if kw_hit:
        out["behaviour"] = (1, kw_hit, False)
    elif tests_only or not existing:
        out["behaviour"] = (0, "tests only" if tests_only else "every declared file is new", False)

    rev, dom = axes.get("reversibility") or {}, axes.get("domain") or {}
    for axis, two, one, said in (("reversibility", rev.get("irreversible"), rev.get("needs_step"),
                                  ("matches irreversible", "matches needs_step")),
                                 ("domain", dom.get("modules"), dom.get("customer_visible"),
                                  ("matches modules", "is customer-visible:"))):
        hit2, hit1 = _first(files, two), _first(files, one)
        if hit2 or hit1:
            out[axis] = (2, "%s %s %s" % (hit2[0], said[0], hit2[1]), False) if hit2 else \
                (1, "%s %s %s" % (hit1[0], said[1], hit1[1]), False)
    out.setdefault("reversibility", (0, "git revert returns everything", False))

    manifest = _first(files, (axes.get("novelty") or {}).get("manifests"))
    if manifest:
        out["novelty"] = (1, "%s is a dependency manifest" % manifest[0], False)
    if tests_only:
        for axis in ("domain", "novelty"):
            out.setdefault(axis, (0, "tests only", False))

    cov = axes.get("coverage") or {}
    code = [f for f in files if match(f, cov.get("code_globs")) and not match(f, tests)]
    test_names = [os.path.basename(t) for t in set(listing) | set(files) if match(t, tests)]
    covered = [f for f in code if any(_ident(f) in t for t in test_names) or match(f, list(cov.get("map") or {}))]
    value = 0 if len(covered) == len(code) else 1 if covered else 2
    out["coverage"] = (value, "%d of %d code files have a test" % (len(covered), len(code))
                       if code else "no code file declared", False)
    return out


def _declared(root, path):
    """`path` repo-relative. A directory or a path outside `root` is refused: scored, it would read as new."""
    rel = os.path.relpath(os.path.join(root, path), root).replace(os.sep, "/")
    real = os.path.relpath(os.path.realpath(os.path.join(root, rel)), os.path.realpath(root)).replace(os.sep, "/")
    if any((p + "/").startswith("../") for p in (rel, real)):
        raise ValueError("%s is outside %s: declare the project's own files" % (path, root))
    if os.path.isdir(os.path.join(root, rel)):
        raise ValueError("%s is a directory: declare the files in it that change" % path)
    return rel


def compute(root, files, declared, goal="", policy=None):
    """Score repo-relative `files` with the session's `declared` {axis: (n, evidence)}; a lower one is replaced."""
    root = os.path.abspath(root)
    policy = policy or load_policy(root)[0]
    for axis, (n, _why) in declared.items():
        if axis not in AXES or n not in (0, 1, 2):
            raise ValueError("cannot declare %s=%r: axes are %s, values 0-2" % (axis, n, ", ".join(AXES)))
    files = list(dict.fromkeys(_declared(root, f.strip()) for f in files if f.strip()))
    notes, hints, unknown, hinted = [], [], [], set()
    measured = _measure(root, files, goal, policy, tree_files(root), notes)
    rules = policy.get("rules") or {}
    raise_by, unknown_scores = int(rules.get("hint_raises_by", 1)), int(rules.get("unknown_scores", 1))
    for hint in policy.get("hints") or []:
        axis, hit = hint.get("axis"), next((f for f in files if match(f, hint.get("paths"))), None)
        if hit and axis in AXES and not (axis in hinted and rules.get("hint_raises_once_per_axis", True)):
            hinted.add(axis)
            value, why, flag = measured.get(axis, (None, "", False))
            measured[axis] = (min(2, (value or 0) + raise_by), why or hint.get("note", "hint"), flag)
            hints.append("%s +%d: %s (%s)" % (axis, raise_by, hint.get("note", ""), hit))
    axes, evidence = {}, {}
    for axis in AXES:
        value, why, flag = measured.get(axis, (None, "", False))
        if axis in declared:
            n, because = declared[axis]
            if value is not None and n < value:
                notes.append("%s: declared %d below the measurement %d — replaced" % (axis, n, value))
            elif value is None or n > value:
                value, why, flag = n, "%s (declared)" % because, False
        if value is None:
            value, why, flag = unknown_scores, "UNKNOWN — neither measured nor declared", True
        axes[axis], evidence[axis] = value, ("%s; hint +%d" % (why, raise_by)) if axis in hinted else why
        if flag:
            unknown.append(axis)
    modes = policy["modes"]
    full = modes.get("full") or {}
    hard = full.get("hard_axes") or ["reversibility", "domain"]
    light_max, guarded_max = (int((modes.get(m) or {}).get("max_w", d)) for m, d in (("light", 2), ("guarded", 7)))
    full_min = int(full.get("min_w", guarded_max + 1))
    w = sum(axes.values())
    mode = "full_irreversible" if all(axes[a] >= 2 for a in hard) else \
        "full" if w >= full_min or any(axes[a] >= 2 for a in hard) else \
        "light" if w <= light_max else "guarded"
    thresholds = "light ≤%d · guarded %d–%d · full ≥%d or %s=2" % (
        light_max, light_max + 1, guarded_max, full_min, "/".join(hard))
    return Weight(axes, evidence, hints, unknown, notes, mode, thresholds)


def render(result, long=False):
    """Seven lines: one per axis and the verdict; `long` adds the notes, ≤ 20 in all."""
    lines = ["%-14s %d  %s" % (axis, result.axes[axis], result.evidence[axis][:96]) for axis in AXES]
    lines.append("W %d → %s   hints %s · unknown %s · %s" % (
        result.w, result.mode, ", ".join(h.split(":", 1)[0] for h in result.hints) or "none",
        ", ".join(result.unknown) or "none", result.thresholds))
    if long:
        extra = result.hints + result.notes
        extra = extra if len(extra) <= 13 else extra[:12] + ["… %d more" % (len(extra) - 12)]
        lines += ["  " + line[:110] for line in extra]
    return "\n".join(lines)


def mirror(path):
    """weight.md for the JSON at `path`, carrying its sha256."""
    with open(path, "rb") as fh:
        raw = fh.read()
    policy = json.loads(raw.decode("utf-8"))
    out = ["# Weight table", "",
           "<!-- generated by `state.py weight --mirror` from weight.json; edit the JSON and regenerate."
           " sha256: %s -->" % hashlib.sha256(raw).hexdigest(), "",
           "Six axes, 0–2 each; W is their sum. Why each rule is what it is: the plugin's `docs/weight.md`.", "",
           "| Axis | Measured by | Table |", "|---|---|---|"]
    for axis in AXES:
        spec = dict((policy.get("axes") or {}).get(axis) or {})
        how = spec.pop("measure", "session")
        table = "; ".join("%s: %s" % (k, json.dumps(v, ensure_ascii=False)) for k, v in spec.items())
        out.append("| %s | %s | %s |" % (axis, how, table.replace("|", "\\|") or "—"))
    out += ["", "| Mode | When | Plan | Review | Reviewer | Human stops | Suite |", "|---|---|---|---|---|---|---|"]
    for name, mode in (policy.get("modes") or {}).items():
        when = mode.get("when") or ("W ≤ %s" % mode["max_w"] if "max_w" in mode else
                                    "W ≥ %s or %s = 2" % (mode.get("min_w"), " or ".join(mode.get("hard_axes", []))))
        out.append("| %s | %s |" % (name, when) + "".join(" %s |" % mode.get(k, "as full") for k in
                                                         ("plan", "review", "reviewer", "human_stops", "suite")))
    out += ["", "| Hint paths | Axis | Note |", "|---|---|---|"]
    out += ["| %s | %s +%s | %s |" % (", ".join("`%s`" % p for p in h.get("paths", [])), h.get("axis"),
                                      (policy.get("rules") or {}).get("hint_raises_by", 1), h.get("note", ""))
            for h in policy.get("hints") or []]
    out += ["", "Rules: " + json.dumps(policy.get("rules") or {}, ensure_ascii=False), "",
            "Budgets: review_rounds_max %s · remediation_rounds %s · tests %s" % (
                policy.get("review_rounds_max"), policy.get("remediation_rounds"),
                json.dumps(policy.get("tests") or {}))]
    return "\n".join(out) + "\n"
