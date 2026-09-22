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
        self.split = []                 # instruction files that are split candidates
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
        heading = "## Adopted from %s" % path
        current = (plan.read(dest) or b"").decode("utf-8", "replace")
        if heading in current.split("\n"):
            return
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
               instruction_files=frozenset(), shipped_files=None):
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
    decisions = load_decisions(root).get("unmapped", {})
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
            outside = len(text.replace(block, "").encode("utf-8")) if block is not None else len(text.encode("utf-8"))
            keep = skeleton_cap - len(shipped.encode("utf-8"))
            adoption.split.append(sig)
            adoption.note("split?", sig, "%d B outside the block, keep budget %d B; needs --adopt "
                          "--split-request or --split fallback" % (outside, keep))
    add_router_rows(plan, router_rows_text(adoption))
    if not adoption.unmapped:
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


def report_dir(plan):
    return getattr(plan, "adopt_report_dir", None) or \
        ".ai/reports/adopt-%s" % datetime.now(timezone.utc).strftime("%Y-%m-%d")


NOTE_ORDER = ("kept", "split?", "dropped", "ignored", "unmapped", "hint")


def report(plan, adoption, applied=False):
    """The adopt report in spec I3's layout."""
    head = "adopt, applied" if applied else \
        "adopt dry run, mode: %s, nothing written; --apply to write" % adoption.mode
    print("project-update: %s (%s)" % (plan.root, head))
    if not adoption.detected and not adoption.split and not adoption.unmapped:
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
    try:
        adoption = plan_adopt(plan, table, args.mode, tools, shipped_block, skeleton_cap, instruction_files, shipped_files)
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    if adoption.unmapped:
        print("%s: %d file(s) have no mapping row" % (INCOMPLETE, len(adoption.unmapped)))
    report(plan, adoption)
    return 4 if adoption.unmapped else 0


# ---------------------------------------------------------------------------
# I11 --adopt --check
# ---------------------------------------------------------------------------

def check_state(root, table, shipped_block, skeleton_cap, instruction_files, shipped_files=None):
    """`update.py --adopt --check`: exactly one of I11's five lines."""
    where = latest_with(root, "adopt.json")
    if where is None:
        plan = _ThrowawayPlan(root)
        adoption = plan_adopt(plan, table, "migrate", None, shipped_block, skeleton_cap, instruction_files, shipped_files)
        if not adoption.detected and not adoption.split:
            print("no foreign structure detected")
            return 0
        bits = ["%s (%d file(s))" % (t, sum(g.values())) for t, g in adoption.detected.items()]
        print("foreign structure detected: %s — run /project-update --adopt" % ", ".join(bits))
        return 1
    try:
        with open(os.path.join(root, where, "adopt.json"), encoding="utf-8") as fh:
            record_data = json.load(fh)
    except (OSError, ValueError):
        print("no foreign structure detected")
        return 0
    date = where.rsplit("adopt-", 1)[-1]
    regenerated = []
    for src in record_data.get("sources", []):
        full = os.path.join(root, src["path"])
        if not os.path.isfile(full):
            continue
        with open(full, "rb") as fh:
            current = "sha256:" + hashlib.sha256(fh.read()).hexdigest()
        if current != src.get("sha"):
            regenerated.append(src["path"])
    if regenerated:
        print("foreign files regenerated since the adopt of %s: %s — run /project-update --adopt"
             % (date, ", ".join(sorted(regenerated))))
        return 1
    checks = record_data.get("checks", {})
    failed = [name for name, c in checks.items() if c.get("status") not in ("pass", "not_applicable")]
    if failed:
        print("adoption of %s incomplete: %s FAIL — run /project-update --adopt"
             % (date, failed[0].replace("_", "-")))
        return 1
    tools = ", ".join(sorted(record_data.get("tools", {})))
    pending = sum(1 for s in record_data.get("sources", []) if s.get("cleanup") and os.path.isfile(os.path.join(root, s["path"])))
    tail = "; %d file(s) await cleanup" % pending if pending else ""
    print("adopted %s: %s — up to date%s" % (date, tools, tail))
    return 0


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
    dest_lines = set()
    for item in plan.items:
        if item["content"] is not None:
            for raw in text_of(item["content"]).split("\n"):
                n = normalise(raw)
                if n:
                    dest_lines.add(n)
    dropped_star = {d["source"] for d in adoption.dropped if d.get("line") == "*"}
    dropped_at = {(d["source"], d["line"]) for d in adoption.dropped if d.get("line") != "*"}
    lines, missing = 0, []
    for path, _tool, transform, _n, _cleanup in adoption.sources:
        if transform in ("ignore", "instruction-file"):
            continue  # not planned onto a destination in this step; step 7 owns them
        text = text_of(plan.read(path) or b"")
        whole_dropped = path in dropped_star
        for i, raw in enumerate(text.split("\n"), 1):
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
    hard_misses, warn_count = [], 0
    for path in files:
        if path in moved or path in old:
            continue
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
