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
        self.sources = []               # (path, tool, transform, row number)
        self.rows_used = set()

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
    adoption.sources.append((path, tool, transform, row["_n"]))
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
    elif existing is not None and existing != content:
        plan.add("conflict", dest, note=tag + "; the destination exists and differs", src=path, tool=tool)
    elif existing != content:
        plan.add("adopt", dest, note=tag, content=content, src=path, tool=tool)


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


def plan_adopt(plan, table, mode="migrate", tools=None, shipped_block=None, skeleton_cap=None):
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
            adoption.sources.append((sig, tool, "instruction-file", row["_n"]))
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
    for tool, groups in adoption.detected.items():
        text = ", ".join("%s (%d)" % (g, c) if c > 1 or g.endswith("/") else g for g, c in groups.items())
        print("  %-9s %-*s  %s" % ("detect", width, tool, text))
    for i in plan.items:
        print("  %-9s %-*s  %s" % (i["action"], width, shown(i), i["note"]))
    for action in NOTE_ORDER:
        for act, subject, text in adoption.notes:
            if act == action:
                print("  %-9s %-*s  %s" % (act, width, subject, text))
    auto = [i for i in plan.items if i["action"] not in ("conflict", "delete?")]
    conflicts = [i for i in plan.items if i["action"] == "conflict"]
    tail = ""
    if adoption.split:
        tail += ", %d split(s) awaiting a proposal" % len(adoption.split)
    if adoption.unmapped:
        tail += ", %d unmapped" % len(adoption.unmapped)
    print("%d automatic, %d conflict(s)%s" % (len(auto), len(conflicts), tail))


def run(plan, args, shipped_block, skeleton_cap):
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
    try:
        adoption = plan_adopt(plan, table, args.mode, tools, shipped_block, skeleton_cap)
    except TableError as exc:
        print("project-update: %s" % exc, file=sys.stderr)
        return 2
    if adoption.unmapped:
        print("%s: %d file(s) have no mapping row" % (INCOMPLETE, len(adoption.unmapped)))
    report(plan, adoption)
    return 4 if adoption.unmapped else 0
