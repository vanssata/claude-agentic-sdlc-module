"""policy: the weight table's reads, the modes and the budgets they set, the documents rule and the weighing, the suite facts, and the next action each state asks for.

core: MODES, MODE_TIER, VERDICT_STATUS, mode_for, higher_mode, mode_setting, BATCH_DEFAULTS, BATCH_TIERS, batch_on, next_action_for, full_suite, suite_green, NEVER_DOCUMENTS, is_document, DOCUMENTS_ZEROED, weigh, review_next_action
shell: weight_policy, batch_policy, budget, added_lines, rescore_weight, rescore_v7, documents_cover
"""
import copy
import os
import posixpath
import re

from rr_state import fs, journal
from rr_state import runtime as rr_runtime

# weight.py and sensors.py sit beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None
try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None

MODES = ["light", "guarded", "full", "full_irreversible"]
# tier_set compat (R18): the old budget tables price a task by its T-label.
MODE_TIER = {"light": "T2", "guarded": "T4", "full": "T5", "full_irreversible": "T6"}

VERDICT_STATUS = {"pass": "passed", "pass_with_findings": "passed_with_findings",
                  "blockers_open": "blockers_open"}


def weight_policy(root):
    if weight is None:
        fs.die("weight.py is missing beside state.py: reinstall the plugin")
    try:
        return weight.load_policy(root)[0]
    except (OSError, ValueError) as exc:
        fs.die("cannot read the weight table: %s" % exc)
    return None                           # unreachable: die() exits


def mode_for(axes, policy, irreversible=False):
    """The mode six axis values earn under `policy`'s thresholds — weight.compute's
    rule, applied to re-scored axes; an irreversible_content hit is
    full_irreversible whatever the sum."""
    modes = policy.get("modes") or {}
    full = modes.get("full") or {}
    hard = full.get("hard_axes") or ["reversibility", "domain"]
    light_max = int((modes.get("light") or {}).get("max_w", 2))
    guarded_max = int((modes.get("guarded") or {}).get("max_w", 7))
    w = sum(int(axes.get(a) or 0) for a in weight.AXES)
    if irreversible or all(int(axes.get(a) or 0) >= 2 for a in hard):
        return "full_irreversible"
    if w >= int(full.get("min_w", guarded_max + 1)) or any(int(axes.get(a) or 0) >= 2 for a in hard):
        return "full"
    return "light" if w <= light_max else "guarded"


def higher_mode(a, b):
    return max(a, b, key=lambda m: MODES.index(m) if m in MODES else -1)


def mode_setting(policy, mode, key, default=None):
    """modes.<mode>.<key>; full_irreversible inherits what it does not say from full."""
    modes = policy.get("modes") or {}
    for name in ([mode, "full"] if mode == "full_irreversible" else [mode]):
        if key in (modes.get(name) or {}):
            return modes[name][key]
    return default


# The batch loop of /rr-build-all: one task for a whole plan, its own budgets.
BATCH_DEFAULTS = {"default": False, "review_rounds_max": 3, "max_suite_runs": 8, "parallel": 3, "tier": "BALANCED"}


BATCH_TIERS = ["FAST", "BALANCED", "STRONG", "EXPERT"]


def batch_policy(policy, strict=False):
    """weight.json's batch section with every key filled in and checked. A table
    from before the section runs with the shipped numbers (R13). A bad value is
    refused where the task starts or the loop is switched (strict); a reader —
    status, the handoff — falls back to the shipped value and never crashes."""
    section = policy.get("batch") if isinstance(policy.get("batch"), dict) else {}
    out, problems = dict(BATCH_DEFAULTS), []
    for key, value in section.items():
        if key not in BATCH_DEFAULTS:
            continue
        if key == "default":
            if isinstance(value, bool):
                out[key] = value
            else:
                problems.append("batch.default must be true or false, not %r" % (value,))
        elif key == "tier":
            if isinstance(value, str) and value.upper() in BATCH_TIERS:
                out[key] = value.upper()
            else:
                problems.append("batch.tier must be one of %s, not %r" % ("/".join(BATCH_TIERS), value))
        elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
            problems.append("batch.%s must be a whole number of at least 1, not %r" % (key, value))
        else:
            out[key] = value
    if out["parallel"] >= 3 and out["tier"] not in ("FAST", "BALANCED"):
        problems.append("batch.tier %s with batch.parallel %d: three or more parallel agents run at FAST or "
                        "BALANCED (model-routing.md, Fan-out)" % (out["tier"], out["parallel"]))
    if problems and strict:
        fs.die("weight.json: " + "; ".join(problems))
    return out


def batch_on(state):
    return bool((state.get("batch") or {}).get("on"))


def budget(policy, state, key):
    """(limit, the table key the refusal names) for review_rounds_max or
    max_suite_runs: the batch section's while the batch loop is on, else the
    standard one — a task switched off mid-way keeps what it already spent."""
    if batch_on(state):
        return int(batch_policy(policy)[key]), "batch.%s" % key
    if key == "max_suite_runs":
        return int((policy.get("tests") or {}).get(key, 2)), "tests.max_suite_runs"
    return int(policy.get(key, 2)), key


def added_lines(root, base_tree, rel):
    """The lines `rel` gained since `base_tree` — all of them for a new file — so
    content that was already there never raises a re-score."""
    before = ""
    if base_tree and sensors is not None:
        code, text = sensors.git(root, ["cat-file", "-p", "%s:%s" % (base_tree, rel)])
        before = text if code == 0 and "\0" not in text[:8192] else ""
    seen = {}
    for line in before.splitlines():
        seen[line] = seen.get(line, 0) + 1
    out = []
    for line in fs.read_text(root, rel).splitlines():
        if seen.get(line):
            seen[line] -= 1
        else:
            out.append(line)
    return out


def rescore_weight(root, base_tree, files, current, policy):
    """Reversibility and domain from the diff's `files`, only upward (R26).

    It lives here, not in weight.py, because weight.py is at the spec's 300-line
    cap; the rules it applies are weight.json's, through weight.match. Returns
    {"axes", "raised": [{axis, from, to, evidence}], "operations", "irreversible"}.
    A pattern of `irreversible_content` in the lines a `needs_step` file gained is
    reversibility 2 and full_irreversible. The patterns are case-sensitive, as
    the SQL keywords they name are written: `rename()` in Python is not RENAME."""
    spec = policy.get("axes") or {}
    rules = policy.get("rules") or {}
    rev, dom = spec.get("reversibility") or {}, spec.get("domain") or {}
    axes = dict(current or {})
    found, operations = {}, []
    files = [f for f in dict.fromkeys(files or []) if f]
    for rel in files:
        hit = weight.match(rel, rev.get("irreversible"))
        if hit:
            found["reversibility"] = (2, "%s matches irreversible %s" % (rel, hit))
        elif weight.match(rel, rev.get("needs_step")):
            gained = added_lines(root, base_tree, rel)
            for pattern in rev.get("irreversible_content") or []:
                try:
                    rx = re.compile(pattern)
                except re.error:
                    continue
                line = next((ln for ln in gained if rx.search(ln)), None)
                if line is not None:
                    # The operation's keyword (DROP, ALTER …), not the pattern's
                    # source: it is what a human names in approve --confirm.
                    # The first word of the match; a match of only blanks or punctuation
                    # is named IRREVERSIBLE, never an IndexError.
                    word = re.search(r"[A-Za-z]+", rx.search(line).group(0))
                    operations.append(word.group(0).upper() if word else "IRREVERSIBLE")
                    if found.get("reversibility", (0,))[0] < 2:
                        found["reversibility"] = (2, "%s adds %r (irreversible_content %r)"
                                                  % (rel, line.strip()[:60], pattern))
            found.setdefault("reversibility", (1, "%s matches needs_step %s"
                                               % (rel, weight.match(rel, rev.get("needs_step")))))
        for value, key, said in ((2, "modules", "matches modules"), (1, "customer_visible", "is customer-visible:")):
            hit = weight.match(rel, dom.get(key))
            if hit and value > found.get("domain", (0,))[0]:
                found["domain"] = (value, "%s %s %s" % (rel, said, hit))
                break
    for hint in policy.get("hints") or []:
        hit = next((f for f in files if weight.match(f, hint.get("paths"))), None)
        if hit and hint.get("axis") == "domain":
            value, why = found.get("domain", (0, ""))
            found["domain"] = (min(2, value + int(rules.get("hint_raises_by", 1))),
                               "%shint %s (%s)" % (why + "; " if why else "", hint.get("note", ""), hit))
            break
    raised = []
    for axis in rules.get("rescore_axes") or ["reversibility", "domain"]:
        if axis not in found:
            continue
        value, why = found[axis]
        if value > int(axes.get(axis) or 0):
            raised.append({"axis": axis, "from": int(axes.get(axis) or 0), "to": value, "evidence": why})
            axes[axis] = value
    return {"axes": axes, "raised": raised, "operations": sorted(set(operations)),
            "irreversible": bool(operations)}


def next_action_for(state):
    if batch_on(state):
        return ("batch loop: 'steps --ready' → implementers, step-done each; 'verify --scope all', red fixed "
                "as one batch; review, findings fixed as one batch; again until it passes; the pass past the "
                "batch budget is the human's")
    return {
        "light": "edit, then 'state.py verify --scope all', then 'state.py close'",
        "guarded": "edit, 'state.py verify --scope all', one review ('state.py review'), then 'state.py close'",
        "full": "edit, 'state.py verify --scope all', one STRONG review, then 'state.py close' "
                "requests the human's approval",
        "full_irreversible": "edit, 'state.py verify --scope all', one STRONG review, then 'state.py close'; "
                             "the human approves with --confirm \"<operation>\"",
    }.get(state.get("mode"), "edit, verify, close")


def rescore_v7(root, state, policy, at, rt=rr_runtime.Runtime()):
    """R26 at verify and close: raises are applied, journaled and printed; the
    task never restarts and the other four axes are not recomputed."""
    if sensors is None:
        return
    diff = fs.safe_sensor(sensors.diff_files, root, state["diff"].get("base_tree"), fs.current_tree(root))
    if not diff:
        return
    current = state["weight"].get("axes") or {}
    got = rescore_weight(root, state["diff"].get("base_tree"), [d["path"] for d in diff], current, policy)
    # The documents rule (faster-task-cycle (c)): the axes it zeroed come back, upward, once the
    # diff holds a path that is neither a document nor a test — `start --amend` does not re-weigh.
    zeroed = (state["weight"].get("documents_only") or {}).get("zeroed") or {}
    tests = ((policy.get("axes") or {}).get("coverage") or {}).get("test_globs")
    outside = next((d["path"] for d in diff if not is_document(d["path"], policy)
                    and not weight.match(d["path"], tests)), None)
    if outside:
        for axis, value in zeroed.items():
            if int(got["axes"].get(axis) or 0) < int(value):
                got["raised"].append({"axis": axis, "from": int(got["axes"].get(axis) or 0), "to": int(value),
                                      "evidence": "a non-document changed (%s)" % outside})
                got["axes"][axis] = int(value)
    before = state["mode"]
    ops = sorted(set(state["weight"].get("operations") or []) | set(got["operations"]))
    # Only what the diff moved can move the mode: an unchanged measurement must
    # not undo a mode a human lowered (R27).
    was = mode_for(current, policy, bool(state["weight"].get("operations")))
    now_measured = mode_for(got["axes"], policy, bool(ops))
    mode = higher_mode(before, now_measured) if now_measured != was else before
    if not got["raised"] and mode == before and ops == (state["weight"].get("operations") or []):
        return
    state["weight"].update(axes=got["axes"], w=sum(got["axes"].values()), operations=ops)
    state["mode"] = mode
    for r in got["raised"]:
        journal.emit(root, state, "weight_raised", "%s %d -> %d at %s: %s" % (r["axis"], r["from"], r["to"], at,
                                                                     fs.one_line(r["evidence"], 200)),
             dict(r, mode_from=before, mode_to=mode), rt=rt)
        state["weight"]["rescores"].append("%s at %s: %s %d → %d — %s"
                                           % (fs.now(), at, r["axis"], r["from"], r["to"], r["evidence"]))
        print("re-score: %s %d → %d — %s" % (r["axis"], r["from"], r["to"], fs.one_line(r["evidence"], 120)))
    if mode != before:
        state["weight"]["rescores"].append("%s at %s: mode %s → %s%s" % (
            fs.now(), at, before, mode, " (irreversible: %s)" % ", ".join(ops) if got["irreversible"] else ""))
        journal.emit(root, state, "tier_set", "%s (mode %s, compat)" % (MODE_TIER[mode], mode),
             {"tier": MODE_TIER[mode], "mode": mode, "w": state["weight"]["w"]}, rt=rt)
        state["next_action"] = next_action_for(state)
        print("mode: %s → %s — %s" % (before, mode, state["next_action"]))


def full_suite(run):
    """A run of the whole suite: one narrowed with --files proves only those files."""
    return run.get("scope") == "suite" and not run.get("expected_fail") and not run.get("files")


def suite_green(state):
    return any(full_suite(r) and r.get("exit") == 0 for r in state["verify"]["runs"])


# Never a document, whatever weight.json's `documents` says: the policies and the per-directory rules bind the agents.
NEVER_DOCUMENTS = (".ai/policies/**", ".ai/rules/**")


def is_document(path, policy):
    """The one definition of a document (faster-task-cycle D4): `documents.globs`, minus
    `documents.except`, NEVER_DOCUMENTS, code and tests; no `documents` key, no document."""
    docs = policy.get("documents") or {}
    cov = (policy.get("axes") or {}).get("coverage") or {}
    return bool(weight.match(path, docs.get("globs"))
                and not any(weight.match(path, pats) for pats in (
                    docs.get("except"), NEVER_DOCUMENTS, cov.get("code_globs"), cov.get("test_globs"))))


DOCUMENTS_ZEROED = ("behaviour", "domain", "novelty")


def weigh(root, files, declared, goal, policy, globs=()):
    """weight.compute, plus the documents rule (faster-task-cycle (c), in state.py because
    weight.py is at its line cap). Predicate P: at least one concrete file, every file a
    document (is_document) or a test, at least one a document. When P holds, file text no
    longer scores behaviour (the goal's keyword still does, exactly as in compute), and
    behaviour, domain and novelty still UNKNOWN become 0 with the evidence "documents only"; hints and
    declarations were applied inside compute. `documents_only` is {"zeroed": {axis: what it
    would have scored}}, None when P does not hold or the policy has no `documents` key.
    `globs` are the task's glob entries, which score nothing themselves: P fails when one is
    not itself a document or test glob."""
    concrete = [posixpath.normpath(f.strip().replace(os.sep, "/")) for f in files if f.strip()]
    tests = ((policy.get("axes") or {}).get("coverage") or {}).get("test_globs")
    inside = all(not f.startswith(("/", "../")) and f != ".." for f in concrete)
    if not (inside and all(is_document(g, policy) or weight.match(g, tests) for g in globs)
            and any(is_document(f, policy) for f in concrete)
            and all(is_document(f, policy) or weight.match(f, tests) for f in concrete)):
        result = weight.compute(root, files, declared, goal, policy=policy)
        result.documents_only = None
        return result
    scored = copy.deepcopy(policy)
    keywords = list(((policy.get("axes") or {}).get("behaviour") or {}).get("keywords") or [])
    if not (goal and any(re.search(r"\b%s\b" % re.escape(k), goal, re.I) for k in keywords)):
        # No goal keyword: file text must not score. With one, compute reads the goal first
        # (value 1 whatever the files hold), so keeping the list scores exactly as plain compute does.
        scored["axes"]["behaviour"] = dict(scored["axes"].get("behaviour") or {}, keywords=[])
    result = weight.compute(root, files, declared, goal, policy=scored)
    zeroed = {}
    for axis in DOCUMENTS_ZEROED:
        if axis not in result.unknown:
            continue
        if result.axes[axis] != 0:
            zeroed[axis] = result.axes[axis]
        result.axes[axis], result.evidence[axis] = 0, "documents only"
        result.unknown.remove(axis)
    result.w = sum(result.axes.values())
    result.mode = mode_for(result.axes, policy)
    result.documents_only = {"zeroed": zeroed}
    return result


def documents_cover(root, state, policy, tree):
    """Fact (a) through the documents rule (faster-task-cycle D1-D5): (ok, why, facts).
    why is "" when the rule is off or does not apply: today's refusal text stands."""
    off = (False, "", None)
    tests = (fs.safe_sensor(sensors.read_commands, root) or {}).get("doc_tests", "").split()
    if not (policy.get("documents") or {}).get("globs") or not tests or tests == ["none"]:
        return off                                                              # D1
    runs = [r for r in state["verify"]["runs"] if full_suite(r) and r.get("exit") is not None and r.get("tree")]
    g = runs[-1] if runs else None
    if not g or g["exit"] != 0 or any(r["tree"] == g["tree"] and r["exit"] != 0 for r in runs):
        return off                                                              # D2
    # A full-suite run after G that is not green stops the rule, whatever its tree (it may be None).
    if any(full_suite(r) and r["n"] > g["n"] and r.get("exit") != 0 for r in state["verify"]["runs"]):
        return off
    diff = fs.safe_sensor(sensors.diff_files, root, g["tree"], tree)
    if not diff or not all(is_document(d["path"], policy) for d in diff):
        return off                                                              # D3, D4
    paths = [d["path"] for d in diff]
    steps = [r for r in state["verify"]["runs"] if r.get("scope") == "step" and not r.get("expected_fail")
             and r.get("tree") == tree]
    s = steps[-1] if steps else None                                            # D5
    if not (s and s["n"] > g["n"] and s.get("exit") == 0 and all(t in (s.get("files") or []) for t in tests)):
        return (False, "only documents changed since run %d (%d files): 'verify --scope step --files \"%s\"'"
                % (g["n"], len(paths), ",".join(tests)), None)
    return (True, "documents only since run %d (%d files: %s); doc_tests green in run %d on %s"
            % (g["n"], len(paths), ", ".join(paths[:5]) + (", …" if len(paths) > 5 else ""), s["n"], tree[:9]),
            {"since_run": g["n"], "since_tree": g["tree"], "run": s["n"], "paths": paths[:20], "tests": tests})


def review_next_action(state):
    """What follows the last verdict — also after `batch off`, which changes what
    a blockers_open verdict asks for: a full pass in batch, a scoped re-review outside."""
    status = state["review"].get("status")
    if status == "blockers_open":
        if batch_on(state):
            return ("fix every BLOCKER and HIGH as one parallel batch, 'state.py verify --scope all "
                    "--after-fix \"…\"', then a full review pass again")
        return "fix the blockers, 'state.py verify --scope all --after-fix \"…\"', one scoped re-review"
    if status in VERDICT_STATUS.values():
        return "'state.py close'"
    return next_action_for(state)
