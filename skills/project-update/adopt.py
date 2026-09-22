"""Adopt a foreign AI-tool structure into claude-agentic's layout (`update.py --adopt`).

This module grows over WP6's plan steps; update.py keeps only flag parsing and the
calls into it, so new behaviour lives here.

Exit codes used by the adopt family (update.py returns them):
  4  unmapped, a failed check or an invalid proposal: a decision is needed
  5  refused: a gate that needs a human, a clean tree or a finished task did not hold
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import OrderedDict
from datetime import datetime, timezone

import render_instructions

REFUSED = "ADOPT_REFUSED"


def human_present():
    """The same condition WP2's approval uses: a terminal, or a launcher that
    declared the run unattended. An agent has neither.

    Duplicated from skills/ai-task/state.py (human_present) on purpose: the two
    skills are installed independently and neither imports the other."""
    return os.isatty(0) or bool(os.environ.get("AI_UNATTENDED"))


def clean_tree(root):
    """The paths `git status` reports as changed or untracked under root, or
    None when root is not inside a git work tree. `-z` keeps paths with spaces
    or quotes intact; a rename entry carries its source as a second record,
    which is skipped."""
    try:
        proc = subprocess.run(["git", "-C", root, "status", "--porcelain", "-z", "--untracked-files=all"],
                              capture_output=True, check=False)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    records = proc.stdout.decode("utf-8", "surrogateescape").split("\0")
    paths, skip = [], False
    for rec in records:
        if skip:
            skip = False
            continue
        if len(rec) < 4:
            continue
        status, path = rec[:2], rec[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            skip = True
    return paths


def refuse(reason, how):
    """Print the refusal the way every adopt gate does — the marker on the first
    stdout line, then what to do — and return exit code 5."""
    print("%s: %s" % (REFUSED, reason))
    print("  %s" % how)
    return 5


def budget_offenders(root, files, caps, block_of):
    """R21: one line per root instruction file over budget — its managed block
    over `caps["project"]`, or the whole file over `caps["skeleton"]`. Files that
    do not exist are skipped; a file under both budgets prints nothing."""
    out = []
    for name in files:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block = block_of(text)
        size = len(text.encode("utf-8"))
        if block is not None and caps.get("project") and len(block.encode("utf-8")) > caps["project"]:
            out.append("%s block %d B over the project budget of %d B"
                       % (name, len(block.encode("utf-8")), caps["project"]))
        if caps.get("skeleton") and size > caps["skeleton"]:
            out.append("%s file %d B over the skeleton budget of %d B" % (name, size, caps["skeleton"]))
    return out


# ---------------------------------------------------------------------------
# The mapping table (spec I2) and its matcher
# ---------------------------------------------------------------------------

TRANSFORMS = ("copy", "append-section", "rule", "instruction-file", "drop", "ignore")
MAP_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "adopt-map.json")
INCOMPLETE = "ADOPT_INCOMPLETE"
# Never walked for foreign files: not ours to read, or not text.
WALK_SKIP = {".git", ".ai", "vendor", "node_modules", "bower_components", "third_party",
             "Pods", "site-packages", ".venv", ".pnpm", ".yarn", "__pycache__"}
SECRET_RE = re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}"
                       r"|-----BEGIN [A-Z ]*PRIVATE KEY")
PLACEHOLDER_RE = re.compile(r"\{(dir|stem|rel)\}")


class TableError(Exception):
    """adopt-map.json is not a table this code can run: exit 2, like a bad
    migration registry."""


def glob_re(pattern):
    """`*` stops at `/`, `**` crosses it, `**/` also matches no directory at all."""
    out, i = [], 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif pattern.startswith("**", i):
            out.append(".*")
            i += 2
        elif pattern[i] == "*":
            out.append("[^/]*")
            i += 1
        elif pattern[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def load_table(path=MAP_FILE):
    try:
        with open(path, encoding="utf-8") as fh:
            table = json.load(fh)
    except (OSError, ValueError) as exc:
        raise TableError("%s: %s" % (path, exc)) from exc
    tools = table.get("tools")
    rows = table.get("rows")
    if table.get("version") != 1 or not isinstance(tools, dict) or not isinstance(rows, list):
        raise TableError("%s: needs version 1, a tools object and a rows list" % path)
    for n, row in enumerate(rows, 1):
        where = "%s row %d" % (path, n)
        if row.get("tool") not in tools:
            raise TableError("%s: unknown tool %r" % (where, row.get("tool")))
        if row.get("transform") not in TRANSFORMS:
            raise TableError("%s: unknown transform %r" % (where, row.get("transform")))
        source = row.get("source")
        if not isinstance(source, str) or not source or source.startswith("/") or ".." in source.split("/"):
            raise TableError("%s: bad source glob %r" % (where, source))
        if row["transform"] in ("copy", "append-section", "rule") and not row.get("dest"):
            raise TableError("%s: a %s row needs a dest" % (where, row["transform"]))
        if row["transform"] in ("drop", "ignore") and not row.get("why"):
            raise TableError("%s: a %s row needs a why" % (where, row["transform"]))
        row["_re"] = glob_re(source)
        row["_n"] = n
    return table


def under_root(path, root):
    """A root is a directory (`x/`), an exact file, or a glob naming either."""
    if root.endswith("/"):
        return path.startswith(root)
    if any(c in root for c in "*?"):
        rx = glob_re(root)
        parts = path.split("/")
        return any(rx.match("/".join(parts[:k])) for k in range(1, len(parts) + 1))
    return path == root or path.startswith(root + "/")


def walk(root):
    """Every file under root, relative with `/`, skipping WALK_SKIP directories."""
    out = []
    for here, dirs, files in os.walk(root):
        dirs[:] = sorted(d for d in dirs if d not in WALK_SKIP)
        rel = os.path.relpath(here, root)
        for name in sorted(files):
            out.append(name if rel == "." else "%s/%s" % (rel.replace(os.sep, "/"), name))
    return out


def has_signature(root, sig):
    path = os.path.join(root, sig.rstrip("/"))
    return os.path.isdir(path) if sig.endswith("/") else os.path.isfile(path)


# ---------------------------------------------------------------------------
# Planning
# ---------------------------------------------------------------------------

class Adoption:
    """What an adopt run found, beside the shared Plan: the lines that are not
    writes (spec I3) and the facts later steps record."""

    def __init__(self, mode):
        self.mode = mode
        self.detected = OrderedDict()   # tool -> OrderedDict(group -> count)
        self.notes = []                 # (action, subject, note), printed in I3 order
        self.unmapped = []              # (path, tool)
        self.split = []                 # split candidates awaiting a proposal or the fallback
        self.candidates = []            # (Candidate, row number): every split candidate
        self.split_errors = []          # (file, reason): a split that cannot be applied, exit 4
        self.split_done = OrderedDict()  # file -> what plan_split recorded (adopt.json.split)
        self.split_before = {}          # target -> bytes before the split wrote it (R9)
        self.split_dests = []           # every target a split writes, the instruction file included
        self.dropped = []               # dropped.jsonl records (spec I7)
        self.sources = []               # (path, tool, transform, row number, cleanup)
        self.destinations = []          # (dest-or-path, tool, router text or None, coexist bool)
        self.rows_used = set()
        self.checks = {}                # "no-line-lost"/"no-dangling" -> (status, detail text)

    def note(self, action, subject, text):
        self.notes.append((action, subject, text))


def slugify(text):
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "rule"


def expand(dest, path, roots):
    """Fill {dir}, {stem} and {rel} (the path under the tool's longest matching
    directory root, without its extension, `/` -> `-`)."""
    parent, name = os.path.split(path)
    stem = os.path.splitext(name)[0]
    under = [r for r in roots if r.endswith("/") and path.startswith(r)]
    rel = path[len(max(under, key=len)):] if under else path
    rel = os.path.splitext(rel)[0].replace("/", "-")
    values = {"dir": os.path.basename(parent), "stem": stem, "rel": rel}
    return PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], dest)


def frontmatter(text):
    """(dict of key -> [values], body, the frontmatter lines) or ({}, text, [])."""
    match = render_instructions.FRONTMATTER_RE.match(text)
    if not match:
        return {}, text, []
    front = render_instructions._frontmatter(match.group("body"), "frontmatter")  # pylint: disable=protected-access
    return front, text[match.end():], match.group("body").split("\n")


def literal_dir(pattern):
    parts = pattern.split("/")
    lead = []
    for part in parts[:-1]:
        if any(c in part for c in "*?[{"):
            break
        lead.append(part)
    return "/".join(lead)


def rule_content(plan, path, text, row, tool, adoption):
    """The `rule` transform: frontmatter rewritten, body verbatim. Returns
    (dest, content, note). Every frontmatter line is logged as rewritten."""
    fmap = row.get("frontmatter", {})
    try:
        front, body, raw = frontmatter(text)
    except render_instructions.RenderError as exc:
        return None, None, "frontmatter not readable: %s" % exc
    globs = []
    for value in front.get(fmap.get("paths", ""), []):
        globs.extend(g.strip() for g in value.split(",") if g.strip())
    always = False
    if fmap.get("always"):
        key, _, want = fmap["always"].partition("=")
        always = [v.lower() for v in front.get(key, [])] == [want.lower()]
    if not raw and fmap.get("always_when_absent"):
        always = True
    title = " ".join(front.get(fmap.get("title", ""), [])).strip()
    for n, line in enumerate(raw, 2):
        if line.strip():
            adoption.dropped.append({"source": path, "line": n, "text": line,
                                     "reason": "rewritten: frontmatter", "by": "transform:rule"})
    name = os.path.basename(path)
    stem = name[:-len(".instructions.md")] if name.endswith(".instructions.md") else os.path.splitext(name)[0]
    base = row["source"].split("*")[0]
    sub = os.path.dirname(path[len(base):]) if path.startswith(base) else ""
    slug = slugify((sub + "-" if sub else "") + stem)
    dirs = []
    for g in globs:
        d = literal_dir(g)
        if d and os.path.isdir(os.path.join(plan.root, d)) and d not in dirs:
            dirs.append(d)
    head = ("# %s\n\n" % title) if title else ""
    body = body.lstrip("\n")
    if dirs and not always:
        front_out = "---\ndirs: [%s]\npaths: [%s]\n---\n\n" % (
            ", ".join(dirs), ", ".join('"%s"' % g for g in globs))
        dest = ".ai/rules/%s.md" % slug
        note = "rule: %s -> paths:, dirs: [%s]" % (fmap.get("paths"), ", ".join(dirs))
    else:
        front_out = ("---\npaths: [%s]\n---\n\n" % ", ".join('"%s"' % g for g in globs)) if globs else ""
        dest = ".ai/policies/adopted/%s-%s.md" % (tool, slug)
        note = "rule: %s" % ("always" if always else "on demand, router row")
    return dest, (front_out + head + body).encode("utf-8"), note


def plan_file(plan, adoption, path, row, tool, roots):
    """Plan one matched source."""
    transform = row["transform"]
    adoption.rows_used.add(row["_n"])
    if transform == "ignore":
        adoption.note("ignored", path, "[%s] %s" % (tool, row["why"]))
        return
    adoption.sources.append((path, tool, transform, row["_n"], bool(row.get("cleanup"))))
    data = plan.read(path) or b""
    for n, line in enumerate(data.decode("utf-8", "replace").split("\n"), 1):
        if SECRET_RE.search(line):
            adoption.note("hint", "%s:%d" % (path, n), "looks like a secret (value not shown)")
    if transform == "drop":
        adoption.dropped.append({"source": path, "line": "*", "sha": "sha256:" + hashlib.sha256(data).hexdigest(),
                                 "reason": row["why"], "by": "transform:drop"})
        adoption.note("dropped", path, "[%s] %s" % (tool, row["why"]))
        return
    if adoption.mode == "coexist":
        adoption.note("kept", path, "[%s] %s, kept in place (coexist)" % (tool, transform))
        adoption.destinations.append((path, tool, row.get("router"), True))
        return
    text = data.decode("utf-8", "replace")
    if transform == "rule":
        dest, content, note = rule_content(plan, path, text, row, tool, adoption)
        if dest is None:
            adoption.unmapped.append((path, tool))
            adoption.note("unmapped", path, "[%s] %s" % (tool, note))
            return
    elif transform == "append-section":
        dest = expand(row["dest"], path, roots)
        # Not "## Adopted from <path>" (spec I2): that heading is itself a
        # reference to the old path, and would dangle after cleanup (I8).
        heading = "## Adopted from %s (%s)" % (TOOL_TITLE.get(tool, tool), os.path.basename(path))
        current = (plan.read(dest) or b"").decode("utf-8", "replace")
        if heading in current.split("\n"):
            adoption.destinations.append((dest, tool, row.get("router"), False))
            return  # already appended by an earlier run
        content = (current.rstrip("\n") + "\n\n" + heading + "\n\n" + text.strip("\n") + "\n").lstrip("\n").encode("utf-8")
        principles = sum(1 for line in text.split("\n") if line.startswith("### "))
        note = "append-section" + (" (hint: %d principles, at most 15)" % principles if principles > 15 else "")
    else:  # copy
        dest = expand(row["dest"], path, roots)
        content, note = data, "copy"
    existing = plan.read(dest)
    tag = "[%s] %s" % (tool, note)
    if transform == "append-section":
        plan.add("adopt", dest, note=tag, content=content, src=path, tool=tool)
        adoption.destinations.append((dest, tool, row.get("router"), False))
    elif existing is not None and existing != content:
        plan.add("conflict", dest, note=tag + "; the destination exists and differs", src=path, tool=tool)
    elif existing != content:
        plan.add("adopt", dest, note=tag, content=content, src=path, tool=tool)
        adoption.destinations.append((dest, tool, row.get("router"), False))
    else:
        adoption.destinations.append((dest, tool, row.get("router"), False))  # already there


def latest_with(root, name):
    """The greatest `.ai/reports/adopt-*` directory holding `name`, or None."""
    base = os.path.join(root, ".ai", "reports")
    try:
        dirs = sorted((d for d in os.listdir(base) if d.startswith("adopt-")), reverse=True)
    except OSError:
        return None
    for d in dirs:
        if os.path.isfile(os.path.join(base, d, name)):
            return ".ai/reports/%s" % d
    return None


def load_decisions(root):
    where = latest_with(root, "decisions.json")
    if where is None:
        return {}
    try:
        with open(os.path.join(root, where, "decisions.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise TableError("%s/decisions.json: %s" % (where, exc)) from exc


def plan_adopt(plan, table, mode="migrate", tools=None, shipped_block=None, skeleton_cap=None,
               instruction_files=frozenset(), shipped_files=None, run_checks=True, split_mode=None,
               splits=True):
    """Detect every foreign structure at the root and plan it onto `plan`.
    Returns the Adoption. Nothing is written."""
    root = plan.root
    adoption = Adoption(mode)
    wanted = [t for t in table["tools"] if tools is None or t in tools]
    # Instruction files (plan step 4, rules a and b): the plugin's own carry the
    # managed block and are only ever split candidates; a file without it is foreign.
    instruction = {}
    for tool in wanted:
        spec = table["tools"][tool]
        if spec["roots"]:
            continue
        for sig in spec["signature"]:
            path = os.path.join(root, sig)
            if not os.path.isfile(path):
                continue
            instruction[tool] = sig
    detected = [t for t in wanted if table["tools"][t]["roots"]
                and any(has_signature(root, s) for s in table["tools"][t]["signature"])]
    files = walk(root)
    all_decisions = load_decisions(root)
    decisions = all_decisions.get("unmapped", {})
    by_tool = OrderedDict((t, []) for t in detected)
    rows_of = {t: [r for r in table["rows"] if r["tool"] == t] for t in table["tools"]}
    for path in files:
        owners = [t for t in detected if any(under_root(path, r) for r in table["tools"][t]["roots"])]
        if not owners:
            continue
        taken = None
        for tool in owners:
            row = next((r for r in rows_of[tool] if r["_re"].match(path)), None)
            if row is not None:
                taken = (tool, row)
                break
        tool = taken[0] if taken else owners[0]
        by_tool[tool].append((path, taken[1] if taken else None))
    for tool, entries in by_tool.items():
        groups = OrderedDict()
        for path, _ in entries:
            group = next((r for r in table["tools"][tool]["roots"] if under_root(path, r)), path)
            groups[group] = groups.get(group, 0) + 1
        adoption.detected[tool] = groups
        roots = table["tools"][tool]["roots"]
        for path, row in entries:
            if row is None:
                decided = decisions.get(path)
                if decided and decided.get("action") in ("drop", "ignore", "copy"):
                    row = {"tool": tool, "source": path, "transform": decided["action"], "_n": 0,
                           "why": decided.get("why", "decided by a human"), "dest": decided.get("dest"),
                           "cleanup": decided["action"] != "ignore"}
                else:
                    adoption.unmapped.append((path, tool))
                    adoption.note("unmapped", path, "[%s] no mapping row — settle it in %s/decisions.json"
                                  % (tool, report_dir(plan)))
                    continue
            plan_file(plan, adoption, path, row, tool, roots)
    # Foreign signatures below the root are never adopted, only listed (R4).
    for path in files:
        nested = nested_signature(path, table, wanted)
        if nested and path not in decisions and all(p != path for p, _ in adoption.unmapped):
            tool, head = nested
            adoption.unmapped.append((path, tool))
            adoption.note("unmapped", path, "[%s] below the root (%s/) — only the root is adopted" % (tool, head))
    for tool, sig in instruction.items():
        text = (plan.read(sig) or b"").decode("utf-8", "replace")
        block = render_instructions.block_of(text)
        row = next(r for r in rows_of[tool])
        if block is None:
            adoption.detected[tool] = OrderedDict([(sig, 1)])
            adoption.rows_used.add(row["_n"])
            adoption.sources.append((sig, tool, "instruction-file", row["_n"], False))
            for n, line in enumerate(text.split("\n"), 1):
                if SECRET_RE.search(line):
                    adoption.note("hint", "%s:%d" % (sig, n), "looks like a secret (value not shown)")
        if shipped_block is None or not skeleton_cap:
            continue
        shipped = shipped_block(tool)
        whole = (text.replace(block, shipped) if block is not None else text.rstrip("\n") + "\n\n" + shipped)
        size = len(whole.encode("utf-8"))
        if size > skeleton_cap:
            adoption.rows_used.add(row["_n"])
            adoption.candidates.append((Candidate(sig, tool, text, shipped, skeleton_cap), row["_n"]))
    if splits and adoption.mode == "migrate":
        plan_splits(plan, adoption, adoption.candidates, split_mode, all_decisions)
    elif not splits:
        adoption.split = [c.path for c, _ in adoption.candidates]
    add_router_rows(plan, router_rows_text(adoption))
    if run_checks and not adoption.unmapped:
        line_status, lines, missing, missing_n = check_lines(plan, adoption)
        adoption.checks["no-line-lost"] = (line_status, lines, missing, missing_n)
        ref_status, hard_misses, warn_n = check_refs(plan, adoption, table, instruction_files, shipped_files)
        adoption.checks["no-dangling"] = (ref_status, hard_misses, warn_n)
    return adoption


def nested_signature(path, table, tools):
    """(tool, directory) when `path` sits under a foreign signature that is not
    at the root — `packages/x/.cursor/rules/a.mdc` -> ("cursor", "packages/x")."""
    parts = path.split("/")
    for tool in tools:
        spec = table["tools"][tool]
        if not spec["roots"] or any(under_root(path, r) for r in spec["roots"]):
            continue
        for sig in spec["signature"]:
            want = sig.rstrip("/").split("/")
            is_dir = sig.endswith("/")
            for k in range(1, len(parts) - len(want) + 1):
                if parts[k:k + len(want)] != want:
                    continue
                last = k + len(want)
                if (is_dir and last < len(parts)) or (not is_dir and last == len(parts)):
                    return tool, "/".join(parts[:k])
    return None


def today():
    """UTC date; ADOPT_TODAY overrides it only under CLAUDE_AGENTIC_TEST=1."""
    if os.environ.get("CLAUDE_AGENTIC_TEST") == "1" and os.environ.get("ADOPT_TODAY"):
        return os.environ["ADOPT_TODAY"]
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def report_dir(plan):
    return getattr(plan, "adopt_report_dir", None) or ".ai/reports/adopt-%s" % today()


NOTE_ORDER = ("kept", "split?", "dropped", "ignored", "unmapped", "hint")


def report(plan, adoption, applied=False):
    """The adopt report in spec I3's layout."""
    head = "adopt, applied" if applied else \
        "adopt dry run, mode: %s, nothing written; --apply to write" % adoption.mode
    print("project-update: %s (%s)" % (plan.root, head))
    if not (adoption.detected or adoption.candidates or adoption.unmapped):
        print("  no foreign structure detected")

    def shown(i):
        return "%s -> %s" % (i["src"], i["target"]) if i.get("src") else i["target"]
    width = max([len(shown(i)) for i in plan.items] + [len(n[1]) for n in adoption.notes]
                + [len(t) for t in adoption.detected] + [10])

    def row(action, subject, text):
        print("  %-9s %-*s  %s" % (action, width, subject, text))

    for tool, groups in adoption.detected.items():
        text = ", ".join("%s (%d)" % (g, c) if c > 1 or g.endswith("/") else g for g, c in groups.items())
        row("detect", tool, text)
    for i in plan.items:
        row(i["action"], shown(i), i["note"])
    for action in NOTE_ORDER:
        for act, subject, text in adoption.notes:
            if act == action:
                row(act, subject, text)
    if "no-line-lost" in adoption.checks:
        status, lines, missing, missing_n = adoption.checks["no-line-lost"]
        if status == "not_applicable":
            row("check", "no-line-lost", "not applicable (coexist)")
        elif status == "pass":
            row("check", "no-line-lost",
               "PASS (%d line(s), %d rewritten -> dropped.jsonl)" % (lines, len(adoption.dropped)))
        else:
            row("check", "no-line-lost", "FAIL: %d line(s): %s" % (missing_n, ", ".join(missing)))
    if "no-dangling" in adoption.checks:
        status, hard_misses, warn_n = adoption.checks["no-dangling"]
        if status == "pass":
            row("check", "no-dangling", "PASS (%d warning(s) outside the new structure)" % warn_n)
        elif adoption.mode == "coexist":
            row("check", "no-dangling", "FAIL: %s" % ", ".join(p for _tag, p in hard_misses[:20]))
        else:
            row("check", "no-dangling", "FAIL: %s" % ", ".join("%s:%s -> %s" % m for m in hard_misses[:20]))
    cleanup_n = sum(1 for _p, _t, _tr, _n, cleanup in adoption.sources if cleanup)
    both_pass = all(c[0] in ("pass", "not_applicable") for c in adoption.checks.values())
    if adoption.mode == "migrate" and cleanup_n and both_pass and not adoption.unmapped:
        row("cleanup?", "", "%d file(s) offered after both checks pass: --adopt --cleanup" % cleanup_n)
    auto = [i for i in plan.items if i["action"] not in ("conflict", "delete?")]
    conflicts = [i for i in plan.items if i["action"] == "conflict"]
    tail = ""
    if adoption.split:
        tail += ", %d split(s) awaiting a proposal" % len(adoption.split)
    if adoption.unmapped:
        tail += ", %d unmapped" % len(adoption.unmapped)
    print("%d automatic, %d conflict(s)%s" % (len(auto), len(conflicts), tail))


def run(plan, args, shipped_block, skeleton_cap, instruction_files=frozenset(), shipped_files=None):
    """`update.py --adopt` without --apply: plan, report, and the exit code."""
    try:
        table = load_table()
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    tools = [t.strip() for t in args.tool.split(",")] if args.tool else None
    if tools:
        unknown = [t for t in tools if t not in table["tools"]]
        if unknown:
            print("project-update: unknown --tool %s (known: %s)" % (", ".join(unknown), ", ".join(table["tools"])),
                  file=sys.stderr)
            return 2
    if getattr(args, "check", False):
        return check_state(plan.root, table, shipped_block, skeleton_cap, instruction_files, shipped_files)
    requesting = getattr(args, "split_request", False)
    try:
        adoption = plan_adopt(plan, table, args.mode, tools, shipped_block, skeleton_cap, instruction_files,
                              shipped_files, run_checks=not requesting, split_mode=getattr(args, "split", None),
                              splits=not requesting)
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    if requesting:
        return write_requests(plan, adoption.candidates)
    problems = incomplete_reasons(plan, adoption, conflicts=False, checks=False)
    if problems:
        print("%s: %s" % (INCOMPLETE, "; ".join(problems)))
    report(plan, adoption)
    if getattr(args, "diff", False):
        print_diff(plan)
    return 4 if problems else 0


def incomplete_reasons(plan, adoption, conflicts=True, checks=True):
    """Why an adopt cannot be applied as planned (exit 4), in the order a
    human settles them. The dry run leaves conflicts and checks to the report."""
    problems = []
    if adoption.unmapped:
        problems.append("%d file(s) have no mapping row" % len(adoption.unmapped))
    problems += ["%s: %s" % err for err in adoption.split_errors]
    if conflicts:
        if adoption.split:
            problems.append("%s: a split needs a proposal or --split fallback" % ", ".join(adoption.split))
        clash = [i["target"] for i in plan.items if i["action"] == "conflict"]
        if clash:
            problems.append("destination(s) exist and differ: %s" % ", ".join(clash))
    if checks:
        failed = [name for name, c in adoption.checks.items() if c[0] == "fail"]
        if failed:
            problems.append("%s FAIL on the plan" % ", ".join(failed))
    return problems


# ---------------------------------------------------------------------------
# I11 --adopt --check
# ---------------------------------------------------------------------------

def check_state(root, table, shipped_block, skeleton_cap, instruction_files, shipped_files=None):
    """`update.py --adopt --check`: exactly one of I11's five lines."""
    code, line = state_line(root, shipped_block, skeleton_cap, table, instruction_files, shipped_files)
    print(line)
    return code


def state_line(root, shipped_block, skeleton_cap, table=None, instruction_files=frozenset(), shipped_files=None):
    """(exit code, one I11 line). Detection only — no reference scan — so the
    plain dry run (D5) can afford it on every call."""
    if table is None:
        try:
            table = load_table()
        except TableError:
            return 0, "no foreign structure detected"
    where = latest_with(root, "adopt.json")
    if where is None:
        plan = _ThrowawayPlan(root)
        adoption = plan_adopt(plan, table, "migrate", None, shipped_block, skeleton_cap,
                              instruction_files, shipped_files, run_checks=False, splits=False)
        if not adoption.detected and not adoption.candidates:
            return 0, "no foreign structure detected"
        bits = ["%s (%d file(s))" % (t, sum(g.values())) for t, g in adoption.detected.items()]
        bits += ["%s (split?)" % c.path for c, _ in adoption.candidates]
        return 1, "foreign structure detected: %s — run /project-update --adopt" % ", ".join(bits)
    try:
        with open(os.path.join(root, where, "adopt.json"), encoding="utf-8") as fh:
            record_data = json.load(fh)
    except (OSError, ValueError):
        return 0, "no foreign structure detected"
    date = where.rsplit("adopt-", 1)[-1]
    regenerated = []
    deleted = set((record_data.get("cleanup") or {}).get("deleted") or [])
    for src in record_data.get("sources", []):
        full = os.path.join(root, src["path"])
        if src["path"] in deleted and os.path.isfile(full):
            regenerated.append(src["path"])  # it reappeared after cleanup (R16)
            continue
        if src.get("transform") == "instruction-file" or not os.path.isfile(full):
            # An instruction file stays, and the plain update re-renders its
            # block; growing again shows as split? in the dry run, not here.
            continue
        with open(full, "rb") as fh:
            current = "sha256:" + hashlib.sha256(fh.read()).hexdigest()
        if current != src.get("sha"):
            regenerated.append(src["path"])
    if regenerated:
        return 1, ("foreign files regenerated since the adopt of %s: %s — run /project-update --adopt"
                   % (date, ", ".join(sorted(regenerated))))
    checks = record_data.get("checks", {})
    failed = [name for name, c in checks.items() if c.get("status") not in ("pass", "not_applicable")]
    if failed or record_data.get("status") == "partial":
        what = failed[0].replace("_", "-") + " FAIL" if failed else "the apply was interrupted"
        return 1, "adoption of %s incomplete: %s — run /project-update --adopt" % (date, what)
    tools = ", ".join(sorted(record_data.get("tools", {})))
    pending = sum(1 for s in record_data.get("sources", []) if s.get("cleanup") and os.path.isfile(os.path.join(root, s["path"])))
    tail = "; %d file(s) await cleanup" % pending if pending else ""
    return 0, "adopted %s: %s — up to date%s" % (date, tools, tail)


class _ThrowawayPlan:
    """The minimal reader `plan_adopt` needs, for `--adopt --check` when no
    record exists yet: nothing is ever written through it."""

    def __init__(self, root):
        self.root = root
        self.items = []
        self.hints = []
        self.final = {}

    def exists(self, target):
        return os.path.exists(os.path.join(self.root, target))

    def read(self, target):
        path = os.path.join(self.root, target)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as fh:
            return fh.read()

    def add(self, *_a, **_k):
        pass  # a check never writes


# ---------------------------------------------------------------------------
# I7 no-line-lost: normalise, source/destination sets, dropped.jsonl coverage
# ---------------------------------------------------------------------------

LIST_MARKER_RE = re.compile(r"^([-*+]|\d+[.)])\s+")
CHECKBOX_RE = re.compile(r"^\[[ xX]\]\s+")
HEADING_RE = re.compile(r"^#{1,6}\s")
ALNUM_RE = re.compile(r"[A-Za-z0-9]")


def normalise(line):
    """I7: strip, ignorable (empty / bare heading / no alphanumeric character)
    is None, otherwise one list marker and one checkbox marker stripped,
    whitespace collapsed, casefolded."""
    line = line.strip()
    if not line or HEADING_RE.match(line) or not ALNUM_RE.search(line):
        return None
    line = LIST_MARKER_RE.sub("", line, count=1)
    line = CHECKBOX_RE.sub("", line, count=1)
    return re.sub(r"\s+", " ", line).casefold()


def text_of(content):
    return content.decode("utf-8", "replace") if isinstance(content, bytes) else content


def check_lines(plan, adoption):
    """I7 no-line-lost: source lines, minus what a transform or a decision
    dropped, must all be in some destination the run writes. `plan.final`
    covers the whole file, per target, so a router row's own text never
    counts against a source (it is not a source, and dest coverage only ever
    helps). Returns (status "pass"/"fail", lines, missing[:20] as "file:line",
    missing_count)."""
    if adoption.mode == "coexist":
        return "not_applicable", 0, [], 0
    targets = {d for d, _t, _r, coexist in adoption.destinations if not coexist}
    targets |= {i["target"] for i in plan.items if i["content"] is not None}
    targets |= set(adoption.split_dests)  # on disk after --apply, `plan` has no items
    dest_lines = set()
    for target in targets:
        for raw in text_of(plan.read(target) or b"").split("\n"):
            n = normalise(raw)
            if n:
                dest_lines.add(n)
    dropped_star = {d["source"] for d in adoption.dropped if d.get("line") == "*"}
    dropped_at = {(d["source"], d["line"]) for d in adoption.dropped if d.get("line") != "*"}
    lines, missing = 0, []
    for path, _tool, transform, _n, _cleanup in adoption.sources:
        only = None
        if transform == "instruction-file":
            if path not in adoption.split_done:
                continue  # not a split: the file stays where it is, whole
            # The text as the split read it: on disk it is already rewritten.
            text = adoption.split_done[path]["text"]
            only = set(adoption.split_done[path]["nums"])
        elif transform == "ignore":
            continue
        else:
            text = text_of(plan.read(path) or b"")
        whole_dropped = path in dropped_star
        for i, raw in enumerate(text.split("\n"), 1):
            if only is not None and i not in only:
                continue
            n = normalise(raw)
            if n is None:
                continue
            lines += 1
            if whole_dropped or (path, i) in dropped_at:
                continue
            if n not in dest_lines:
                missing.append("%s:%d" % (path, i))
    status = "fail" if missing else "pass"
    return status, lines, missing[:20], len(missing)


# ---------------------------------------------------------------------------
# I8 no-dangling-reference
# ---------------------------------------------------------------------------

REF_BOUNDARY_BEFORE = r"(^|[\s`\"'(@=:,])"
REF_BOUNDARY_AFTER = r"(?=$|[\s`\"')>,:;])"
MAX_SCAN_BYTES = 20 * 1024 * 1024


def ref_pattern(old_path):
    """The reference pattern for a path (and for `./path`); a directory root
    (trailing `/`) also matches everything below it."""
    escaped = re.escape(old_path.rstrip("/"))
    if old_path.endswith("/"):
        return re.compile(REF_BOUNDARY_BEFORE + r"\.?/?" + escaped + r"/\S*")
    return re.compile(REF_BOUNDARY_BEFORE + r"\.?/?" + escaped + REF_BOUNDARY_AFTER)


def old_paths_for(adoption, table):
    """I8: every source whose row has cleanup: true, plus every detected
    tool's `roots` entries."""
    paths = {path for path, _tool, _transform, _n, cleanup in adoption.sources if cleanup}
    for tool in adoption.detected:
        paths |= set(table["tools"][tool]["roots"])
    return sorted(paths)


HARD_PREFIXES = (".ai/", "docs/sdlc/", ".claude/", ".codex/", ".gemini/", ".junie/",
                 ".github/prompts/", ".github/instructions/")
HARD_AI_EXCEPT = (".ai/reports/adopt-", ".ai/state/", ".ai/local/")


def is_hard_scope(path, text, instruction_files):
    if path in instruction_files:
        return True
    if os.path.basename(path) in (".junie/guidelines.md".rsplit("/", 1)[-1], "CLAUDE.md", "AGENTS.md")             and render_instructions.RULE_MARKER_RE.search(text):
        return True  # a nested instruction file carrying a rule block (I8)
    if path.startswith(".ai/"):
        return not any(path.startswith(p) for p in HARD_AI_EXCEPT)
    return any(path.startswith(p) for p in HARD_PREFIXES if p != ".ai/")


def is_binary(data):
    return b"\0" in data[:8192]


def git_files(root):
    try:
        proc = subprocess.run(["git", "-C", root, "ls-files", "-z"], capture_output=True, check=False)
    except OSError:
        return None
    if proc.returncode != 0:
        return None
    return [p for p in proc.stdout.decode("utf-8", "surrogateescape").split("\0") if p]


COEXIST_LINK_RE = re.compile(r"^\| .* \| (?P<path>\S+) \(kept in place; its globs are "
                             r"not applied by this runtime\) \|$", re.M)


def check_refs(plan, adoption, table, instruction_files=frozenset(), shipped_files=None):
    """I8 no-dangling-reference: every old path (or, in coexist, every linked
    foreign path) still readable, and no reference to a path this run took
    away is left behind in the hard scope; a reference in the warn scope is
    reported but does not fail. Returns (status, hard_misses, warn_count)."""
    if adoption.mode == "coexist":
        linked = {path for path, _tool, _router, _coexist in adoption.destinations}
        linked |= set(COEXIST_LINK_RE.findall(text_of(plan.read(ROUTER_FILE) or b"")))
        missing = sorted(path for path in linked if not plan.exists(path))
        return ("fail" if missing else "pass"), [("<coexist>", p) for p in missing], 0
    old = old_paths_for(adoption, table)
    if not old:
        return "pass", [], 0
    patterns = [ref_pattern(p) for p in old]
    moved = {path for path, _tool, _transform, _n, cleanup in adoption.sources if cleanup}
    files = git_files(plan.root)
    if files is None:
        files = walk(plan.root)
    # What the run leaves behind: planned content first (plan.final), then disk.
    files = sorted(set(files) | set(plan.final))
    hard_misses, warn_count = [], 0
    for path in files:
        if path in moved or path in old:
            continue
        if path in plan.final:
            data = plan.final[path]
        else:
            full = os.path.join(plan.root, path)
            try:
                if os.path.getsize(full) > MAX_SCAN_BYTES:
                    continue
                with open(full, "rb") as fh:
                    data = fh.read()
            except OSError:
                continue
        if is_binary(data):
            continue
        # A file whose bytes still match what the plugin ships is the plugin's
        # own words, not this project's: a generic example ("a `.cursorrules`
        # or the like", `.ai/policies/security.md`) is not a dependency on
        # this project's foreign structure, so it never fails hard scope —
        # it still counts toward warn (harmless: warn never fails the run).
        unedited = shipped_files is not None and shipped_files.get(path) == data
        text = data.decode("utf-8", "replace")
        hard = is_hard_scope(path, text, instruction_files) and not unedited
        for i, line in enumerate(text.split("\n"), 1):
            hit = next((p for p, rx in zip(old, patterns) if rx.search(line)), None)
            if hit is None:
                continue
            if hard:
                hard_misses.append((path, i, hit))
            else:
                warn_count += 1
            break  # one hit per line is enough to classify it
    return ("fail" if hard_misses else "pass"), hard_misses, warn_count


# ---------------------------------------------------------------------------
# I9 router rows
# ---------------------------------------------------------------------------

TOOL_TITLE = {"speckit": "Spec Kit", "kiro": "Kiro", "aidlc": "AI-DLC", "cursor": "Cursor",
             "copilot": "Copilot", "junie": "Junie", "gemini": "Gemini", "claude": "Claude", "codex": "Codex"}
ROUTER_FILE = ".ai/AGENTS.md"


def router_rows_text(adoption):
    """I9: one row per (tool, destination directory) in migrate mode, one row
    per (tool, path) in coexist. Returns the row texts, in first-seen order."""
    rows = OrderedDict()
    for dest, tool, router_text, coexist in adoption.destinations:
        title = router_text or ("an adopted %s file" % TOOL_TITLE.get(tool, tool))
        if coexist:
            key = (tool, dest)
            shown = dest
            suffix = " (kept in place; its globs are not applied by this runtime)"
        else:
            rel_dir = os.path.dirname(dest)
            key = (tool, rel_dir)
            shown = (rel_dir[len(".ai/"):] if rel_dir.startswith(".ai/") else rel_dir) + "/"
            suffix = ""
        rows.setdefault(key, "| %s | %s%s |" % (title, shown, suffix))
    return list(rows.values())


def add_router_rows(plan, rows):
    """Append new router rows after the last row of `.ai/AGENTS.md`'s routing
    table, idempotent by exact text. Returns the count actually added."""
    if not rows:
        return 0
    text = text_of(plan.read(ROUTER_FILE) or b"")
    if not text:
        return 0
    lines = text.split("\n")
    last = max((i for i, l in enumerate(lines) if l.startswith("|")), default=None)
    if last is None:
        return 0
    to_add = [r for r in rows if r not in lines]
    if not to_add:
        return 0
    new_lines = lines[:last + 1] + to_add + lines[last + 1:]
    plan.add("router", ROUTER_FILE, note="+%d row(s)" % len(to_add), content="\n".join(new_lines).encode("utf-8"))
    return len(to_add)


# ---------------------------------------------------------------------------
# --adopt --apply (R5, R6, R15, R16)
# ---------------------------------------------------------------------------

# Dirt an adopt tolerates: its own record, and the two git-ignored directories.
ALLOWED_DIRT = (".ai/reports/adopt-", ".ai/state/", ".ai/local/")
ORIGINAL_CAP = 1024 * 1024
INSTRUCTION_ROOT = ("CLAUDE.md", "AGENTS.md", "GEMINI.md", ".junie/guidelines.md")


def sha256(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def read_record(root, where):
    try:
        with open(os.path.join(root, where, "adopt.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def partial_record(root):
    """(directory, record) of the latest adopt.json when it is `partial` — an
    apply that stopped part-way — else (None, None)."""
    where = latest_with(root, "adopt.json")
    if where is None:
        return None, None
    rec = read_record(root, where)
    if rec and rec.get("status") == "partial":
        return where, rec
    return None, None


def task_in_flight(root):
    """The task in .ai/state/current.json when its stage is not `done`."""
    try:
        with open(os.path.join(root, ".ai", "state", "current.json"), encoding="utf-8") as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        return None
    stage = state.get("current_stage")
    return None if stage in (None, "done") else "%s at stage %s" % (state.get("task_id", "a task"), stage)


def gates(root, u, planned_writes):
    """R5, in the order a human fixes them. Returns a refusal (reason, how) or None."""
    if not os.path.isdir(os.path.join(root, ".ai")):
        return "the project has no .ai/", "run /ai-init first, then /project-update --adopt"
    dirty = clean_tree(root)
    if dirty is None:
        return "the project is not a git work tree", "run `git init` and commit, so the adopt can be undone"
    running = task_in_flight(root)
    if running:
        return "a task is in flight (%s)" % running, "finish or abandon it with /ai-task first"
    outside = [p for p in dirty if not p.startswith(ALLOWED_DIRT) and p not in planned_writes]
    if outside:
        more = " and %d more" % (len(outside) - 3) if len(outside) > 3 else ""
        return ("the tree has uncommitted changes: %s%s" % (", ".join(outside[:3]), more),
                "commit or stash them first, so the adopt is one reviewable change")
    if u.plain_pending(root, ignore=planned_writes):
        return "the project is behind the installed plugin", "run /project-update --apply first, then adopt"
    return None


def keep_original_bounded(u, plan, rel, record):
    """R6: a copy with its mode under <record dir>/original/, unless it is over
    1 MiB or binary — then git keeps it, and it is listed."""
    full = os.path.join(plan.root, rel)
    if not os.path.isfile(full):
        return
    target = os.path.join(plan.report_dir, "original", rel)
    if os.path.exists(os.path.join(plan.root, target)):
        return  # a resumed apply already kept it
    size = os.path.getsize(full)
    with open(full, "rb") as fh:
        head = fh.read(8192)
    if size > ORIGINAL_CAP or b"\0" in head:
        if rel not in record["original_skipped"]:
            record["original_skipped"].append(rel)
        return
    u.write_file(plan.root, target, u.read(full), mode=os.stat(full).st_mode & 0o7777)
    record["original_bytes"] += size


def phase_of(item):
    """1: destinations, router rows, rendered rule blocks; 2: a rewrite of a
    root instruction file. A source never loses a line before its destination
    exists (plan step 6)."""
    return 2 if item["target"] in INSTRUCTION_ROOT and item["action"] == "adopt" else 1


def test_stop_after():
    """ADOPT_STOP_AFTER=<phase>, read only under CLAUDE_AGENTIC_TEST=1."""
    if os.environ.get("CLAUDE_AGENTIC_TEST") != "1":
        return None
    try:
        return int(os.environ.get("ADOPT_STOP_AFTER", ""))
    except ValueError:
        return None


def write_json(u, root, rel, data):
    u.write_file(root, rel, (json.dumps(data, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))


def apply_run(plan, args, u, skeleton_cap, instruction_files=frozenset(), shipped_files=None):
    """`update.py --adopt --apply`: gates, originals, phased writes, the checks
    on disk, the record. Exit 0, 3 (aborted), 4 (incomplete) or 5 (refused)."""
    root = plan.root
    try:
        table = load_table()
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    tools = [t.strip() for t in args.tool.split(",")] if args.tool else None
    resume_dir, resume = partial_record(root)
    planned_writes = set(resume.get("planned_writes", [])) if resume else set()
    refusal = gates(root, u, planned_writes)
    if refusal:
        return refuse(*refusal)
    plan.report_dir = plan.adopt_report_dir = resume_dir or ".ai/reports/adopt-%s" % today()
    adoption = plan_adopt(plan, table, args.mode, tools, u.shipped_block, skeleton_cap,
                          instruction_files, shipped_files, split_mode=getattr(args, "split", None))
    problems = incomplete_reasons(plan, adoption)
    if problems:
        print("%s: %s — nothing written" % (INCOMPLETE, "; ".join(problems)))
        report(plan, adoption)
        return 4
    # Nested rule blocks for the rules this run writes (plan step 6, HIGH 5).
    planned_rules = {i["target"]: text_of(i["content"]) for i in plan.items
                     if i["content"] is not None and i["target"].startswith(".ai/rules/")}
    if planned_rules:
        u.rules_update(plan, u.project_runtimes(root), planned=planned_rules)
    writes = [i for i in plan.items if i["content"] is not None and i["action"] != "delete?"]
    record = resume or {"version": 1, "mode": args.mode, "adopted_at": u.utc_now(),
                        "original_bytes": 0, "original_skipped": []}
    record["status"] = "partial"
    record["planned_writes"] = sorted(set(record.get("planned_writes", [])) | {i["target"] for i in writes})
    record.setdefault("original_bytes", 0)
    record.setdefault("original_skipped", [])
    rec_path = plan.report_dir + "/adopt.json"
    written, recorded = {}, []
    try:
        write_json(u, root, rec_path, record)
        # Every source cleanup may take away, and every project file outside
        # .ai/ this run rewrites, is kept before anything is written.
        for path, _tool, _transform, _n, cleanup in adoption.sources:
            if cleanup:
                keep_original_bounded(u, plan, path, record)
        for item in writes:
            if not item["target"].startswith(".ai/") and item["expect"] is not None:
                keep_original_bounded(u, plan, item["target"], record)
        write_json(u, root, rec_path, record)
        stop = test_stop_after()
        for phase in (1, 2):
            for item in writes:
                if phase_of(item) == phase:
                    u.apply_item(plan, item, written, recorded)
            if stop == phase:
                print("project-update: stopped after phase %d (ADOPT_STOP_AFTER, test only)" % phase)
                return 3
    except u.Abort as exc:
        print("project-update: aborted: %s — re-run --adopt --apply to resume" % exc.why, file=sys.stderr)
        return 3
    except OSError as exc:
        print("project-update: aborted: %s — re-run --adopt --apply to resume" % exc, file=sys.stderr)
        return 3
    return finish(plan, adoption, record, rec_path, u, table, instruction_files, shipped_files)


def finish(plan, adoption, record, rec_path, u, table, instruction_files, shipped_files):
    """The two checks on disk, then the record: adopt.json, report.md, dropped.jsonl."""
    root = plan.root
    disk = u.Plan(root)  # reads the tree as it is now
    line_status, lines, missing, missing_n = check_lines(disk, adoption)
    ref_status, hard_misses, warn_n = check_refs(disk, adoption, table, instruction_files, shipped_files)
    added = check_added(disk, adoption)
    now = u.utc_now()
    tools = OrderedDict((t, {"files": sum(g.values())}) for t, g in adoption.detected.items())
    for cand, _row in adoption.candidates:  # a split is never `detect`ed, but it is adopted
        if cand.path in adoption.split_done:
            tools.setdefault(cand.tool, {"files": 1})
    sources = []
    for path, tool, transform, _n, cleanup in adoption.sources:
        entry = {"path": path, "sha": sha256(disk.read(path) or b""), "tool": tool,
                 "transform": transform, "cleanup": cleanup}
        item = next((i for i in plan.items if i.get("src") == path and i["content"] is not None), None)
        if item is not None:
            entry["dest"] = item["target"]
            entry["dest_sha"] = sha256(disk.read(item["target"]) or b"")
        if os.path.exists(os.path.join(root, plan.report_dir, "original", path)):
            entry["original"] = "original/" + path
        sources.append(entry)
    merged = OrderedDict((s["path"], s) for s in record.get("sources", []))
    for entry in sources:  # same-day runs merge by source path (I10)
        merged[entry["path"]] = entry
    status = "applied" if "fail" not in (line_status, ref_status) and not added else "incomplete"
    split = dict(record.get("split", {}))
    for path, done in adoption.split_done.items():
        split[path] = {k: done[k] for k in ("by", "proposal_sha", "kept_bytes", "moves", "dropped")}
    if split:
        record["split"] = split
    record.update({
        "status": status, "mode": adoption.mode, "tools": dict(record.get("tools", {}), **tools),
        "sources": list(merged.values()), "dropped": len(adoption.dropped),
        "ignored": sorted({s for a, s, _t in adoption.notes if a == "ignored"}),
        "unmapped": [p for p, _t in adoption.unmapped],
        "checks": record_checks(line_status, lines, missing_n, ref_status, hard_misses, warn_n, now),
        "cleanup": record.get("cleanup") or {"offered": adoption.mode == "migrate" and status == "applied",
                                             "confirmed_by": None, "at": None, "unattended": None,
                                             "tty": None, "deleted": []},
    })
    if adoption.split_done:  # R9 for a split, on disk
        record["checks"]["no_line_added"] = {"status": "fail" if added else "pass", "checked_at": now,
                                             "added": len(added)}
    record.pop("planned_writes", None)
    write_json(u, root, rec_path, record)
    u.write_file(root, plan.report_dir + "/dropped.jsonl",
                 "".join(json.dumps(d, ensure_ascii=False) + "\n" for d in adoption.dropped).encode("utf-8"))
    u.write_file(root, plan.report_dir + "/report.md", report_md(plan, adoption, record).encode("utf-8"))
    adoption.checks["no-line-lost"] = (line_status, lines, missing, missing_n)
    adoption.checks["no-dangling"] = (ref_status, hard_misses, warn_n)
    report(plan, adoption, applied=True)
    skipped = record["original_skipped"]
    print("  original  %d B kept in %s/original/%s" % (
        record["original_bytes"], plan.report_dir,
        "; %d skipped (git has them): %s" % (len(skipped), ", ".join(skipped)) if skipped else ""))
    print("  record    %s" % rec_path)
    if added:
        row_fmt = "  %-9s %s"
        print(row_fmt % ("check", "no-line-added FAIL: %s" % ", ".join(added[:20])))
    if status != "applied":
        print("%s: a check failed on disk — see %s" % (INCOMPLETE, rec_path))
        return 4
    return 0


def record_checks(line_status, lines, missing_n, ref_status, hard_misses, warn_n, now):
    return {"no_line_lost": {"status": line_status, "checked_at": now, "lines": lines, "missing": missing_n},
            "no_dangling": {"status": ref_status, "checked_at": now, "hard": len(hard_misses), "warn": warn_n}}


def report_md(plan, adoption, record):
    """The human rendering of the record, in the intent's order."""
    out = ["# Adopt %s (%s)" % (plan.report_dir.rsplit("adopt-", 1)[-1], adoption.mode), ""]
    out += ["## Detected", ""] + ["- %s: %d file(s)" % (t, v["files"]) for t, v in record["tools"].items()]
    out += ["", "## Where each piece went", ""]
    out += ["- `%s` -> `%s` (%s)" % (s["path"], s["dest"], s["transform"]) for s in record["sources"] if s.get("dest")]
    out += ["", "## Dropped", ""]
    out += ["- `%s%s`: %s" % (d["source"], "" if d["line"] == "*" else ":%s" % d["line"], d["reason"])
            for d in adoption.dropped]
    out += ["", "## Ignored or unmapped", ""] + ["- ignored `%s`" % p for p in record["ignored"]]
    out += ["- unmapped `%s`" % p for p in record["unmapped"]]
    checks = record["checks"]
    out += ["", "## Checks", "",
            "- no-line-lost: %s (%d lines, %d missing)" % (
                checks["no_line_lost"]["status"], checks["no_line_lost"]["lines"], checks["no_line_lost"]["missing"]),
            "- no-dangling: %s (%d hard, %d warning(s))" % (
                checks["no_dangling"]["status"], checks["no_dangling"]["hard"], checks["no_dangling"]["warn"])]
    offered = [s["path"] for s in record["sources"]
               if s.get("cleanup") and os.path.exists(os.path.join(plan.root, s["path"]))]
    out += ["", "## Proposed for deletion", ""]
    if offered and record["cleanup"]["offered"]:
        out += ["- `%s`" % p for p in offered]
        out += ["", "Run `/project-update --adopt --cleanup` to review; a human confirms the deletion."]
    else:
        out += ["- nothing"]
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# --adopt --cleanup (R13, R14's refusal): the one deletion adopt makes, behind
# the record, a clean tree, both checks recomputed, and a human
# ---------------------------------------------------------------------------

CLEANUP_HEADING = "## Cleanup"


def plan_cleanup(plan, args, u, table, skeleton_cap, instruction_files, shipped_files):
    """(refusal, where, record, targets, adoption). `refusal` is (reason, how)
    or None; every gate runs before anything is listed, so a refusal never
    shows a list to confirm. `adoption` is set once the checks were recomputed."""
    root = plan.root

    def no(reason, how, adoption=None):
        return (reason, how), None, None, None, adoption
    if not os.path.isdir(os.path.join(root, ".ai")):
        return no("the project has no .ai/", "run /ai-init first")
    where = latest_with(root, "adopt.json")
    record = read_record(root, where) if where else None
    if record is None:
        return no("no adopt record to clean up", "run /project-update --adopt --apply first")
    if args.mode == "coexist" or record.get("mode") == "coexist":
        return no("coexist keeps the foreign files",
                  "to move them, run /project-update --adopt --apply (mode migrate), then --cleanup")
    checks = record.get("checks", {})
    if record.get("status") != "applied" or any(c.get("status") != "pass" for c in checks.values()):
        return no("the adopt of %s is not complete (R12)" % where.rsplit("adopt-", 1)[-1],
                  "run /project-update --adopt --apply until both checks pass")
    running = task_in_flight(root)
    if running:
        return no("a task is in flight (%s)" % running, "finish or abandon it with /ai-task first")
    dirty = clean_tree(root)
    if dirty is None:
        return no("the project is not a git work tree", "cleanup deletes only what git can restore")
    if dirty:  # no exceptions: `git checkout -- <path>` is the rollback
        more = " and %d more" % (len(dirty) - 3) if len(dirty) > 3 else ""
        return no("the tree has uncommitted changes: %s%s" % (", ".join(dirty[:3]), more),
                  "commit the adopt (its record included) first, so the deletion is its own change")
    targets, changed = [], []
    for src in record.get("sources", []):
        path = src["path"]
        if not src.get("cleanup") or path in INSTRUCTION_ROOT or not os.path.isfile(os.path.join(root, path)):
            continue  # R17: an instruction file is never deleted
        if sha256(plan.read(path) or b"") != src.get("sha"):
            changed.append(path)
        targets.append(src)
    if changed:
        return no("source(s) changed since the adopt: %s" % ", ".join(changed[:3]),
                  "run /project-update --adopt --apply again, then --cleanup")
    # R13: both checks recomputed on the tree as it is now. A pending adopt
    # write would let them pass against the plan instead of the disk.
    adoption = plan_adopt(plan, table, "migrate", None, u.shipped_block, skeleton_cap,
                          instruction_files, shipped_files)
    what = ["%s FAIL" % name for name, c in adoption.checks.items() if c[0] == "fail"]
    pending = [i for i in plan.items if i["action"] != "delete?"]
    if pending:
        what.append("%d adopt item(s) pending" % len(pending))
    if adoption.unmapped or adoption.split:
        what.append("%d unmapped, %d split(s) waiting" % (len(adoption.unmapped), len(adoption.split)))
    if what:
        return no("the adopt no longer holds on the current tree: %s" % "; ".join(what),
                  "run /project-update --adopt to see why, settle it, then --cleanup", adoption)
    return None, where, record, targets, adoption


def cleanup_run(plan, args, u, skeleton_cap, instruction_files=frozenset(), shipped_files=None):
    """`update.py --adopt --cleanup [--apply --confirm-delete NAME]`. Exit 0 or
    5 (refused); a failed removal is exit 3 with the record naming what went."""
    try:
        table = load_table()
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    refusal, where, record, targets, adoption = plan_cleanup(
        plan, args, u, table, skeleton_cap, instruction_files, shipped_files)
    if refusal:
        code = refuse(*refusal)
        if adoption is not None:
            report(plan, adoption)  # the recomputed checks, so the human sees what fails
        return code
    confirm = (getattr(args, "confirm_delete", None) or "").strip()
    if confirm and not human_present():  # update.py checks too; this module stands alone
        return refuse("--confirm-delete is typed by a human, and this run has no terminal",
                      "run the same command yourself in a terminal")
    date = where.rsplit("adopt-", 1)[-1]
    head = "adopt cleanup of %s, applied" % date if confirm else \
        "adopt cleanup dry run of %s, nothing deleted; a human confirms with --apply --confirm-delete NAME" % date
    print("project-update: %s (%s)" % (plan.root, head))
    width = max([len(s["path"]) for s in targets] + [12])
    for name in ("no-line-lost", "no-dangling"):
        print("  %-9s %-*s  PASS (recomputed on the current tree)" % ("check", width, name))
    if not targets:
        print("0 deletion(s): nothing left to clean up")
        return 0
    if not confirm:
        for src in targets:
            print("  %-9s %-*s  [%s] %s; needs --apply --confirm-delete NAME"
                  % ("delete?", width, src["path"], src["tool"], src["transform"]))
        print("%d deletion(s) awaiting --confirm-delete" % len(targets))
        return 0
    tty = os.isatty(0)
    record["cleanup"] = {"offered": True, "confirmed_by": confirm, "at": u.utc_now(),
                         "unattended": not tty, "tty": tty, "deleted": []}
    plan.report_dir = plan.adopt_report_dir = where  # the record's own directory, not today's
    rec_path = where + "/adopt.json"
    write_json(u, plan.root, rec_path, record)  # who and when, before the first removal
    code = 0
    try:
        for src in targets:
            remove_confirmed(u, plan, src["path"], record, table)
            print("  %-9s %-*s  [%s] confirmed by %s" % ("delete", width, src["path"], src["tool"], confirm))
    except OSError as exc:
        print("project-update: aborted: %s — %s names what was deleted" % (exc, rec_path), file=sys.stderr)
        code = 3
    write_json(u, plan.root, rec_path, record)
    cleanup_report_md(u, plan.root, where, record)
    print("%d deleted, confirmed by %s%s; originals in %s/original/" % (
        len(record["cleanup"]["deleted"]), confirm,
        " (deleted unattended)" if record["cleanup"]["unattended"] else "", where))
    return code


def remove_confirmed(u, plan, rel, record, table):
    """Delete one confirmed source: its original kept first (bounded, into the
    record's directory), then the file, then any directory left empty inside
    its tool's roots — so the signature goes with the files."""
    keep_original_bounded(u, plan, rel, record)
    os.remove(os.path.join(plan.root, rel))
    record["cleanup"]["deleted"].append(rel)
    tool = next((s["tool"] for s in record.get("sources", []) if s["path"] == rel), None)
    roots = [r.rstrip("/") for r in table["tools"].get(tool, {}).get("roots", []) if r.endswith("/")]
    parent = os.path.dirname(rel)
    while parent and any(parent == r or parent.startswith(r + "/") for r in roots):
        full = os.path.join(plan.root, parent)
        if not os.path.isdir(full) or os.listdir(full):
            break
        os.rmdir(full)
        parent = os.path.dirname(parent)


def cleanup_report_md(u, root, where, record):
    """report.md gains (or replaces) its Cleanup section."""
    path = os.path.join(root, where, "report.md")
    try:
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        text = ""
    text = text.split("\n" + CLEANUP_HEADING + "\n", 1)[0].rstrip("\n") + "\n"
    c = record["cleanup"]
    out = ["", CLEANUP_HEADING, "",
           "- %d file(s) deleted at %s, confirmed by %s%s" % (
               len(c["deleted"]), c["at"], c["confirmed_by"], " (deleted unattended)" if c["unattended"] else "")]
    out += ["- `%s`" % p for p in c["deleted"]]
    u.write_file(root, where + "/report.md", (text + "\n".join(out) + "\n").encode("utf-8"))


# ---------------------------------------------------------------------------
# The instruction-file split (R7, R8, R9, R17, R19): a request with no text,
# a proposal of line ranges, the deterministic fallback, the diff
# ---------------------------------------------------------------------------

SPLIT_KEYS = frozenset(("version", "source", "source_sha", "keep", "moves", "dropped"))
MOVE_KEYS = frozenset(("lines", "dest", "heading", "dirs", "paths"))
DROP_KEYS = frozenset(("lines", "why"))
ALLOWED_DEST = (".ai/policies/adopted/<slug>.md", ".ai/rules/<slug>.md", ".ai/project/<slug>.md",
                "docs/sdlc/constitution.md")
ALLOWED_DEST_RE = re.compile(r"\A(?:\.ai/(?:policies/adopted|rules|project)/[a-z0-9][a-z0-9-]*\.md"
                             r"|docs/sdlc/constitution\.md)\Z")


class SplitError(Exception):
    """A proposal the tool will not apply: exit 4 with this reason."""


class Candidate:
    """A root instruction file over `_budgets.skeleton` once its block is the
    shipped one. `nums` are the 1-based lines a split must place: every line
    outside the block, or only the markers left out when the block was edited
    (WP3 R13's case), so the human's edits inside it are split too."""

    def __init__(self, path, tool, text, shipped, cap):
        self.path, self.tool, self.text, self.shipped = path, tool, text, shipped
        self.sha = sha256(text.encode("utf-8"))
        self.lines = text.split("\n")
        if self.lines and self.lines[-1] == "":
            self.lines.pop()
        block = render_instructions.block_of(text)
        self.block = None
        if block is not None:
            start = next(i for i, l in enumerate(self.lines, 1) if render_instructions.BLOCK_START in l)
            end = next(i for i, l in enumerate(self.lines, 1) if render_instructions.BLOCK_END in l)
            self.block = (start, end)
        self.edited = block is not None and block != shipped
        if self.block is None:
            self.nums = list(range(1, len(self.lines) + 1))
        elif self.edited:
            self.nums = [n for n in range(1, len(self.lines) + 1) if n not in self.block]
        else:
            self.nums = [n for n in range(1, len(self.lines) + 1) if not self.block[0] <= n <= self.block[1]]
        self.keep_budget = cap - len(shipped.encode("utf-8"))
        self.outline = [{"line": n, "heading": self.lines[n - 1]} for n in self.nums
                        if HEADING_RE.match(self.lines[n - 1])]

    def line(self, n):
        return self.lines[n - 1]


def file_slug(path):
    return slugify(path)  # CLAUDE.md -> claude-md, .junie/guidelines.md -> junie-guidelines-md


def spans(nums):
    """[3, 4, 5, 9] -> "3-5, 9"."""
    out, nums = [], sorted(nums)
    for n in nums:
        if out and n == out[-1][1] + 1:
            out[-1][1] = n
        else:
            out.append([n, n])
    return ", ".join("%d" % a if a == b else "%d-%d" % (a, b) for a, b in out)


def request_name(cand, all_candidates, kind):
    """`split-request.json` / `split-proposal.json` for one candidate, with the
    file slug in the name when several files are split in one adopt."""
    if len(all_candidates) == 1:
        return "split-%s.json" % kind
    return "split-%s-%s.json" % (kind, file_slug(cand.path))


def split_request(cand, where, all_candidates):
    """I4: the outline, the allow-list and the keep budget. No text."""
    return OrderedDict([
        ("version", 1), ("source", cand.path), ("source_sha", cand.sha), ("lines", len(cand.lines)),
        ("block", list(cand.block) if cand.block else None), ("block_edited", cand.edited),
        ("cover", spans(cand.nums)), ("outline", cand.outline), ("keep_budget_bytes", cand.keep_budget),
        ("allowed_dest", list(ALLOWED_DEST)),
        ("proposal", "%s/%s" % (where, request_name(cand, all_candidates, "proposal")))])


def find_proposal(root, cand, stale=False):
    """(where, data) of a split-proposal*.json in any adopt-* directory whose
    `source` and `source_sha` match the file on disk; newest first. One
    proposal per sha: a match is always reused, never re-requested (R7).
    With `stale`, the newest proposal for this file whatever its sha."""
    base = os.path.join(root, ".ai", "reports")
    try:
        dirs = sorted((d for d in os.listdir(base) if d.startswith("adopt-")), reverse=True)
    except OSError:
        return None, None
    for d in dirs:
        try:
            names = sorted(n for n in os.listdir(os.path.join(base, d))
                           if n.startswith("split-proposal") and n.endswith(".json"))
        except OSError:
            continue
        for name in names:
            try:
                with open(os.path.join(base, d, name), encoding="utf-8") as fh:
                    data = json.load(fh)
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and data.get("source") == cand.path and (stale or data.get("source_sha") == cand.sha):
                return ".ai/reports/%s/%s" % (d, name), data
    return None, None


def _range(value, cand, what):
    if (not isinstance(value, list) or len(value) != 2 or not all(isinstance(v, int) and not isinstance(v, bool)
                                                                  for v in value)):
        raise SplitError("%s: a range is [first, last], two line numbers" % what)
    first, last = value
    if not 1 <= first <= last <= len(cand.lines):
        raise SplitError("%s: range [%d, %d] is outside lines 1-%d" % (what, first, last, len(cand.lines)))
    return list(range(first, last + 1))


def _strings(value, what):
    if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
        raise SplitError("%s must be a non-empty list of strings" % what)
    return value


def load_proposal(data, cand, root, tracked):
    """Validate an I5 proposal against the file on disk. Returns
    (keep nums, moves, dropped) where each move is a dict with `nums`; raises
    SplitError naming the first reason it cannot be applied. No key carries
    text into a destination: `heading` must be empty or an outline heading,
    byte for byte (plan-review MEDIUM 14)."""
    if not isinstance(data, dict):
        raise SplitError("the proposal is not a JSON object")
    extra = sorted(set(data) - SPLIT_KEYS)
    if extra:
        raise SplitError("unknown key(s) %s — a proposal carries line ranges, never text" % ", ".join(extra))
    if data.get("version") != 1:
        raise SplitError("version must be 1")
    if data.get("source") != cand.path:
        raise SplitError("source is %r, not %s" % (data.get("source"), cand.path))
    if data.get("source_sha") != cand.sha:
        raise SplitError("source_sha does not match %s on disk — ask for a new --split-request" % cand.path)
    covered = {}

    def claim(nums, what):
        for n in nums:
            if n in covered:
                raise SplitError("line %d is in both %s and %s" % (n, covered[n], what))
            if n not in cand_nums:
                raise SplitError("%s: line %d is %s" % (what, n, "a managed-block marker" if cand.edited
                                                          else "inside the managed block"))
            covered[n] = what
        return nums
    cand_nums = set(cand.nums)
    for key in ("keep", "moves", "dropped"):
        if not isinstance(data.get(key, []), list):
            raise SplitError("%s must be a list" % key)
    keep = []
    for i, rng in enumerate(data.get("keep", []), 1):
        keep += claim(_range(rng, cand, "keep[%d]" % i), "keep[%d]" % i)
    headings = {o["heading"] for o in cand.outline}
    moves = []
    for i, move in enumerate(data.get("moves", []), 1):
        what = "moves[%d]" % i
        if not isinstance(move, dict):
            raise SplitError("%s is not an object" % what)
        extra = sorted(set(move) - MOVE_KEYS)
        if extra:
            raise SplitError("%s: unknown key(s) %s — a move carries line ranges, never text" % (what, ", ".join(extra)))
        dest = move.get("dest")
        if not isinstance(dest, str) or not ALLOWED_DEST_RE.match(dest):
            raise SplitError("%s: dest %r is not one of %s" % (what, dest, ", ".join(ALLOWED_DEST)))
        heading = move.get("heading") or ""
        if not isinstance(heading, str) or (heading and heading not in headings):
            raise SplitError("%s: heading %r is not a heading of the request's outline" % (what, heading))
        rule = dest.startswith(".ai/rules/")
        dirs, paths = [], []
        if rule:
            dirs = _strings(move.get("dirs"), "%s: dirs (required for .ai/rules/)" % what)
            for d in dirs:
                d = d.rstrip("/")
                if d.startswith("/") or ".." in d.split("/") or not os.path.isdir(os.path.join(root, d)):
                    raise SplitError("%s: dirs entry %r is not a directory of the tree" % (what, d))
            if "paths" in move:
                paths = _strings(move["paths"], "%s: paths" % what)
                for p in paths:
                    pat = glob_re(p)
                    if not any(pat.match(f) for f in tracked or ()):
                        raise SplitError("%s: paths glob %r matches no tracked file" % (what, p))
        elif "dirs" in move or "paths" in move:
            raise SplitError("%s: dirs and paths belong to an .ai/rules/ destination only" % what)
        nums = claim(_range(move.get("lines"), cand, what), what)
        moves.append({"nums": nums, "dest": dest, "heading": heading, "dirs": [d.rstrip("/") for d in dirs],
                      "paths": paths})
    dropped = []
    for i, drop in enumerate(data.get("dropped", []), 1):
        what = "dropped[%d]" % i
        if not isinstance(drop, dict):
            raise SplitError("%s is not an object" % what)
        extra = sorted(set(drop) - DROP_KEYS)
        if extra:
            raise SplitError("%s: unknown key(s) %s" % (what, ", ".join(extra)))
        why = drop.get("why")
        if not isinstance(why, str) or not why.strip():
            raise SplitError("%s: why must say why the lines are dropped" % what)
        dropped.append({"nums": claim(_range(drop.get("lines"), cand, what), what), "why": why.strip()})
    gap = cand_nums - set(covered)
    if gap:
        raise SplitError("lines %s are in no range — every line outside the block is kept, moved or dropped"
                         % spans(gap))
    kept = sum(len(cand.line(n).encode("utf-8")) + 1 for n in keep)
    if kept > cand.keep_budget:
        raise SplitError("keep is %d B, over the keep budget of %d B" % (kept, cand.keep_budget))
    return sorted(keep), moves, dropped


def fallback_split(cand):
    """R8's deterministic split: every line to place goes, verbatim, to one
    `.ai/policies/adopted/<file-slug>.md`. No model."""
    return [], [{"nums": list(cand.nums), "dest": ".ai/policies/adopted/%s.md" % file_slug(cand.path),
                 "heading": "", "dirs": [], "paths": []}], []


def rewritten(cand, keep):
    """The instruction file after the split: the kept lines where they were,
    the shipped block in place of the old one (at the end when there was none)."""
    keep = set(keep)
    out, inside = [], []
    for n, line in enumerate(cand.lines, 1):
        if cand.block and n == cand.block[0]:
            out.append(cand.shipped)
        elif cand.block and cand.block[0] < n <= cand.block[1]:
            if n in keep:
                inside.append(line)  # an edited block's kept lines follow the shipped block
            if n == cand.block[1]:
                out += inside
        elif n in keep:
            out.append(line)
    if cand.block is None:
        while out and not out[-1].strip():
            out.pop()
        out += ([""] if out else []) + [cand.shipped]
    return "\n".join(out).strip("\n") + "\n"


def section_of(cand, move):
    body = "\n".join(cand.line(n) for n in move["nums"]).strip("\n")
    heading = move["heading"] or "## Adopted from %s, lines %s" % (cand.path, spans(move["nums"]))
    first = body.split("\n", 1)[0]
    return (body if first == heading else heading + "\n\n" + body), heading


def plan_split(plan, adoption, cand, row_n, how, keep, moves, dropped, proposal_sha=None):
    """Put one split on `plan`: the destinations first, then the rewrite of
    the instruction file (apply's phase 2, so no line leaves before it has
    somewhere to be)."""
    tag = "[%s] split (%s)" % (cand.tool, how)
    generated = set()
    by_dest = OrderedDict()
    for move in moves:
        by_dest.setdefault(move["dest"], []).append(move)
    for dest, group in by_dest.items():
        sections = []
        for move in group:
            text, heading = section_of(cand, move)
            sections.append(text)
            generated.add(normalise(heading))
        body = "\n\n".join(sections)
        current = plan.read(dest)
        adoption.split_before.setdefault(dest, current)
        current_text = text_of(current or b"")
        ranges = spans([n for m in group for n in m["nums"]])
        if body in current_text:
            adoption.split_dests.append(dest)  # already there: a resumed apply
            continue
        if dest.startswith(".ai/rules/"):
            dirs = list(OrderedDict.fromkeys(d for m in group for d in m["dirs"]))
            paths = list(OrderedDict.fromkeys(p for m in group for p in m["paths"]))
            front = "---\ndirs: [%s]\n" % ", ".join(dirs)
            front += ("paths: [%s]\n" % ", ".join('"%s"' % p for p in paths)) if paths else ""
            front += "---\n"
            generated.update(normalise(l) for l in front.split("\n"))
            content = front + "\n" + body + "\n"
            if current is not None:
                plan.add("conflict", dest, note=tag + "; the rule exists and differs", src=cand.path, tool=cand.tool)
                continue
        else:
            content = (current_text.rstrip("\n") + "\n\n" if current_text.strip() else "") + body + "\n"
        plan.add("adopt", dest, note="%s lines %s" % (tag, ranges), content=content.encode("utf-8"),
                 src=cand.path, tool=cand.tool)
        adoption.split_dests.append(dest)
        if dest.startswith(".ai/policies/adopted/"):
            adoption.destinations.append((dest, cand.tool, None, False))
    for drop in dropped:
        for n in drop["nums"]:
            if normalise(cand.line(n)) is not None:
                adoption.dropped.append({"source": cand.path, "line": n, "text": cand.line(n),
                                         "reason": drop["why"], "by": "proposal"})
    result = rewritten(cand, keep)
    generated.update(normalise(l) for l in cand.shipped.split("\n"))
    adoption.split_before.setdefault(cand.path, plan.read(cand.path))
    if result.encode("utf-8") != plan.read(cand.path):
        plan.add("adopt", cand.path, note="%s: %d B kept, managed block re-rendered" % (tag, len(result.encode("utf-8"))),
                 content=result.encode("utf-8"), src=cand.path, tool=cand.tool)
    adoption.split_dests.append(cand.path)
    if all(s[0] != cand.path for s in adoption.sources):
        adoption.sources.append((cand.path, cand.tool, "instruction-file", row_n, False))
    adoption.split_done[cand.path] = {
        "by": how, "proposal_sha": proposal_sha, "kept_bytes": sum(len(cand.line(n).encode("utf-8")) + 1 for n in keep),
        "moves": len(moves), "dropped": len(dropped), "text": cand.text, "nums": cand.nums, "generated": generated}


def check_added(plan, adoption):
    """R9 for a split, the other direction of I7: every non-ignorable line of
    a file the split writes is a source line, a generated line (a heading,
    frontmatter, the shipped block) or content the file already had.
    Returns the offending "file:line"s."""
    if not adoption.split_done:
        return []
    allowed = set()
    for done in adoption.split_done.values():
        allowed.update(normalise(l) for l in done["text"].split("\n"))
        allowed.update(done["generated"])
    bad = []
    for target in OrderedDict.fromkeys(adoption.split_dests):
        before = {normalise(l) for l in text_of(adoption.split_before.get(target) or b"").split("\n")}
        for i, raw in enumerate(text_of(plan.read(target) or b"").split("\n"), 1):
            n = normalise(raw)
            if n is not None and n not in allowed and n not in before:
                bad.append("%s:%d" % (target, i))
    return bad


def plan_splits(plan, adoption, candidates, split_mode, decisions):
    """Plan every candidate by proposal or fallback; what cannot be planned
    stays `split?` (awaiting) or goes to `split_errors` (exit 4)."""
    tracked = None
    fallback = decisions.get("split")
    for cand, row_n in candidates:
        how = split_mode
        wants_fallback = fallback == "fallback" or (isinstance(fallback, dict) and fallback.get(cand.path) == "fallback")
        where, data = (None, None) if how == "fallback" else find_proposal(plan.root, cand)
        if how is None:
            how = "proposal" if data is not None else ("fallback" if wants_fallback else None)
        if how is None:
            where, data = find_proposal(plan.root, cand, stale=True)
            how = "proposal" if data is not None else None  # stale: validation names the sha
        if how is None:
            adoption.split.append(cand.path)
            adoption.note("split?", cand.path, "%d B outside the block, keep budget %d B; needs --adopt "
                          "--split-request or --split fallback"
                          % (sum(len(cand.line(n).encode("utf-8")) + 1 for n in cand.nums), cand.keep_budget))
            continue
        if how == "fallback":
            plan_split(plan, adoption, cand, row_n, "fallback", *fallback_split(cand))
            continue
        if data is None:
            adoption.split_errors.append((cand.path, "--split proposal, and no split-proposal.json matches "
                                                     "its sha — run --adopt --split-request"))
            continue
        if tracked is None:
            tracked = git_files(plan.root) or []
        try:
            keep, moves, dropped = load_proposal(data, cand, plan.root, tracked)
        except SplitError as exc:
            adoption.split_errors.append((cand.path, "%s: %s" % (where, exc)))
            continue
        with open(os.path.join(plan.root, where), "rb") as fh:
            proposal_sha = sha256(fh.read())
        plan_split(plan, adoption, cand, row_n, "proposal", keep, moves, dropped, proposal_sha)
    bad = check_added(plan, adoption)
    if bad:
        adoption.split_errors.append((", ".join(sorted(adoption.split_done)),
                                      "no-line-added FAIL: %d line(s) come from no source: %s"
                                      % (len(bad), ", ".join(bad[:20]))))


def write_requests(plan, candidates):
    """`--adopt --split-request`: one I4 file per candidate with no matching
    proposal, into today's record. Writes nothing else. Returns the exit code."""
    if not candidates:
        print("project-update: no split candidate — nothing to request")
        return 0
    where = report_dir(plan)
    for cand, _row in candidates:
        found, _data = find_proposal(plan.root, cand)
        if found:
            print("  split     %s  a proposal for this sha exists, reused: %s" % (cand.path, found))
            continue
        rel = "%s/%s" % (where, request_name(cand, [c for c, _ in candidates], "request"))
        full = os.path.join(plan.root, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            json.dump(split_request(cand, where, [c for c, _ in candidates]), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        print("  split     %s  request written: %s (the session writes the proposal next to it)" % (cand.path, rel))
    return 0


def print_diff(plan):
    """`--adopt --diff`: one unified diff per target this run would write."""
    import difflib  # pylint: disable=import-outside-toplevel
    for target in OrderedDict.fromkeys(i["target"] for i in plan.items if i["content"] is not None):
        path = os.path.join(plan.root, target)
        before = ""
        if os.path.isfile(path):
            with open(path, "rb") as fh:
                before = fh.read().decode("utf-8", "replace")
        after = text_of(plan.final.get(target, b""))
        sys.stdout.writelines(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                   "a/" + target, "b/" + target))
