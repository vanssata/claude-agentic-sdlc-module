#!/usr/bin/env python3
"""Render the always-loaded instruction stubs from their single source.

`instructions/stub.md` is the one place the text of every managed block lives —
global and project, Claude Code and Codex. This module selects the groups that a
(scope, runtime) pair asks for, substitutes the per-runtime vocabulary of
`instructions/runtimes.json` and the `RENDER_*` variables the installer exports,
and writes the result. `install.sh` calls it by path; `update.py` imports it.

Standard library only, and it never shells out: the installer runs it before
anything else of the plugin is on disk.

    render_instructions.py render --scope global --runtime claude --kind block
                                  [--source DIR] [--var K=V ...] [--out FILE]
    render_instructions.py build  [--check] [--source DIR] [--templates DIR]
                                  [--project-init DIR]
    render_instructions.py measure FILE... [--block|--whole] [--budget BYTES]
    render_instructions.py constitution FILE [--max-lines 15] [--max-bytes 4096]

Exit codes: 0 ok, 1 drift / over budget / unresolved placeholder, 2 usage.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCOPES = ("global", "project", "skeleton", "skeleton-sdlc")
KINDS = ("block", "skeleton", "routing")

# The stub is the always-loaded text; routing.md is the long-form reference
# installed beside it and read on demand. Both use the same directive syntax.
SOURCE_FILES = {"block": "stub.md", "skeleton": "stub.md",
                "routing": "routing.md"}

BLOCK_START = "<!-- claude-agentic:start -->"
BLOCK_END = "<!-- claude-agentic:end -->"

DIRECTIVE_RE = re.compile(r"^<!--\s*stub:\s*(?P<attrs>.*?)\s*-->\s*$")
PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

# Per-directory rules. `.ai/rules/<slug>.md` is the source; what it renders into
# a directory's instruction file is a block of its own, so several rules can
# share a file and the text around them stays the project's.
RULE_START = "<!-- claude-agentic:rule:%s:start -->"
RULE_END = "<!-- claude-agentic:rule:%s:end -->"
RULE_MARKER_RE = re.compile(
    r"<!--\s*claude-agentic:rule:(?P<slug>[a-z0-9][a-z0-9-]*):start\s*-->"
)
RULE_GENERATED = ("<!-- generated from .ai/rules/%s.md by /project-update"
                  " \u2014 edit that file -->")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(?P<body>.*?)\n---[ \t]*(\n|\Z)", re.S)

# runtime -> the instruction file a directory of that runtime carries. Only
# these two read one per directory; Gemini and Junie have a project file only,
# so a rule renders nothing for them.
RULE_FILE = {"claude": "CLAUDE.md", "codex": "AGENTS.md"}

# Where Claude's own path-scoped copy of a rule goes. Written only when the rule
# sets `paths:` and the project declares Claude.
CLAUDE_RULES_DIR = ".claude/rules"

DEFAULT_SOURCE = Path(__file__).resolve().parents[2]
DEFAULT_TEMPLATES = DEFAULT_SOURCE / "skills" / "ai-init" / "templates"
DEFAULT_PROJECT_INIT = DEFAULT_SOURCE / "skills" / "project-init" / "templates"

# Placeholders the renderer never resolves: they are filled in by the scaffold,
# per project, long after build has written the template.
DEFERRED = ("PROJECT",)

# scope -> (kind, where, {runtime: file name}). `where` is the directory option
# the build targets of that scope live in.
TEMPLATES = {
    "project": ("block", "templates", {
        "claude": "CLAUDE.block.md",
        "codex": "AGENTS.block.md",
        "gemini": "GEMINI.block.md",
        "junie": "junie-guidelines.block.md",
    }),
    "skeleton": ("skeleton", "templates", {
        "claude": "CLAUDE.minimal.md",
        "codex": "AGENTS.minimal.md",
        "gemini": "GEMINI.minimal.md",
        "junie": "junie-guidelines.minimal.md",
    }),
    "skeleton-sdlc": ("skeleton", "project-init", {
        "claude": "CLAUDE.md",
        "codex": "AGENTS.md",
        "gemini": "GEMINI.md",
        "junie": "junie-guidelines.md",
    }),
}


class RenderError(Exception):
    """A problem with the stub source or an unresolved placeholder."""


class Group:
    """A run of lines and the directive that covers it."""

    __slots__ = ("scopes", "runtimes", "lines")

    def __init__(self, attrs, lines):
        self.scopes = _attr(attrs, "scope")
        self.runtimes = _attr(attrs, "runtime")
        self.lines = lines

    def selected(self, scope, runtime):
        return _matches(self.scopes, scope) and _matches(self.runtimes, runtime)


def _attr(attrs, name):
    """The comma list of one directive attribute, or None when it is absent."""
    if attrs is None:
        return None
    match = re.search(r"\b%s=([A-Za-z0-9_,*-]+)" % name, attrs)
    if not match:
        return None
    return [v for v in match.group(1).split(",") if v]


def _matches(values, wanted):
    return values is None or "*" in values or wanted in values


def parse(text):
    """Split stub source into groups. A directive covers the lines that follow it
    until the next directive line or a blank line."""
    groups, attrs, lines = [], None, []
    for line in text.split("\n"):
        directive = DIRECTIVE_RE.match(line)
        if directive:
            if lines:
                groups.append(Group(attrs, lines))
            attrs, lines = directive.group("attrs"), []
        elif line.strip() == "":
            if lines:
                groups.append(Group(attrs, lines))
            attrs, lines = None, []
        else:
            lines.append(line)
    if lines:
        groups.append(Group(attrs, lines))
    return groups


def vocabulary(source, runtime):
    path = Path(source) / "instructions" / "runtimes.json"
    try:
        runtimes = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RenderError("no %s" % path) from exc
    if runtime not in runtimes:
        raise RenderError("unknown runtime %r in %s" % (runtime, path))
    return runtimes[runtime]


# The budgets an installed plugin uses: install.sh copies skills/, not
# instructions/, so runtimes.json is only there in a checkout. Kept equal to
# `_budgets` in instructions/runtimes.json by tests/test-project-update.sh.
DEFAULT_BUDGETS = {"global": 2560, "project": 2048, "skeleton": 2048, "skeleton-sdlc": 2048}


def budgets(source):
    """scope -> byte budget. `_budgets` is absent until the diet switches it on.
    Without runtimes.json (an installed plugin) the shipped DEFAULT_BUDGETS
    apply; a runtimes.json that exists but does not parse is still an error."""
    path = Path(source) / "instructions" / "runtimes.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("_budgets", {})
    except FileNotFoundError:
        return dict(DEFAULT_BUDGETS)


def substitute(text, runtime_vars, extra_vars):
    """{{X}} from runtimes.json first, then --var K=V, then RENDER_X. Names in
    DEFERRED are left literal; anything else unresolved is an error."""

    def lookup(name):
        if name in runtime_vars:
            return runtime_vars[name]
        if name in extra_vars:
            return extra_vars[name]
        return os.environ.get("RENDER_" + name)

    out = []
    for number, line in enumerate(text.split("\n"), 1):
        pieces, last = [], 0
        for match in PLACEHOLDER_RE.finditer(line):
            name = match.group(1)
            value = match.group(0) if name in DEFERRED else lookup(name)
            if value is None:
                raise RenderError(
                    "unresolved placeholder %s on line %d" % (match.group(0), number)
                )
            pieces.append(line[last:match.start()])
            pieces.append(value)
            last = match.end()
        pieces.append(line[last:])
        out.append("".join(pieces))
    return "\n".join(out)


def render(scope, runtime, kind, source=DEFAULT_SOURCE, extra_vars=None):
    stub = Path(source) / "instructions" / SOURCE_FILES[kind]
    try:
        text = stub.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RenderError("no %s" % stub) from exc

    selected = [g for g in parse(text) if g.selected(scope, runtime)]
    if not selected:
        raise RenderError(
            "no stub group for scope=%s runtime=%s in %s" % (scope, runtime, stub)
        )

    body = "\n\n".join("\n".join(g.lines) for g in selected)
    body = substitute(body, vocabulary(source, runtime), extra_vars or {})
    body = re.sub(r"\n{3,}", "\n\n", body).strip("\n")
    if kind == "block":
        return "%s\n%s\n%s\n" % (BLOCK_START, body, BLOCK_END)
    return body + "\n"


def targets(templates=DEFAULT_TEMPLATES, project_init=DEFAULT_PROJECT_INIT,
            source=DEFAULT_SOURCE):
    """Every template `build` owns, as (scope, runtime, kind, path)."""
    dirs = {"templates": Path(templates), "project-init": Path(project_init)}
    known = set(json.loads(
        (Path(source) / "instructions" / "runtimes.json").read_text(encoding="utf-8")))
    for scope, spec in TEMPLATES.items():
        kind, where, names = spec[0], spec[1], spec[2]
        for runtime in sorted(names):
            if runtime in known:
                yield scope, runtime, kind, dirs[where] / names[runtime]


def build(check=False, source=DEFAULT_SOURCE, templates=DEFAULT_TEMPLATES,
          project_init=DEFAULT_PROJECT_INIT, out=sys.stdout):
    """Regenerate (or, with check, verify) every committed template from the stub.

    A template over its scope's budget is never written: the source is what has
    to shrink, not the check."""
    budget = budgets(source)
    drifted, oversized = [], []
    for scope, runtime, kind, path in targets(templates, project_init, source):
        text = render(scope, runtime, kind, source)
        limit = budget.get(scope)
        if limit is not None and len(text.encode("utf-8")) > limit:
            oversized.append((path, len(text.encode("utf-8")), limit))
            continue
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        drifted.append(path)
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    for path, size, limit in oversized:
        print("%s %d B over budget %d B — shrink instructions/stub.md"
              % (path, size, limit), file=sys.stderr)
    if check:
        for path in drifted:
            print("%s differs from instructions/stub.md — run "
                  "render_instructions.py build" % path, file=sys.stderr)
    else:
        for path in drifted:
            print("wrote %s" % path, file=out)
    return 1 if (oversized or (check and drifted)) else 0


# ------------------------------------------------------------------ rules
class Rule:
    """One `.ai/rules/<slug>.md`: where it applies, and what it says."""

    __slots__ = ("slug", "dirs", "paths", "body")

    def __init__(self, slug, dirs, paths, body):
        self.slug = slug
        self.dirs = dirs
        self.paths = paths
        self.body = body


def _scalar(value):
    """One frontmatter value. Quoted text is taken whole — a glob is full of
    characters a comment stripper would happily eat."""
    value = value.strip()
    if value[:1] in ('"', "'"):
        quote = value[0]
        end = value.find(quote, 1)
        if end < 0:
            raise RenderError("unterminated %s in %s" % (quote, value))
        return value[1:end]
    return value.split("#", 1)[0].strip().rstrip(",").strip()


def _frontmatter(raw, where):
    """The `key: [a, b]` / `key:` + `- a` subset of YAML the rule format uses.
    Anything richer is a rule file asking for a parser this must not grow."""
    data, key = {}, None
    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- "):
            if key is None:
                raise RenderError("%s: a list item before any key" % where)
            data[key].append(_scalar(stripped[2:]))
            continue
        if ":" not in stripped:
            raise RenderError("%s: %s is not `key: value`" % (where, stripped))
        name, _, value = stripped.partition(":")
        key, value = name.strip(), value.strip()
        if value.startswith("["):
            end = value.rfind("]")
            if end < 0:
                raise RenderError("%s: unterminated [ in %s" % (where, stripped))
            data[key] = [_scalar(v) for v in value[1:end].split(",") if v.strip()]
        elif not value or value.startswith("#"):
            data[key] = []
        else:
            data[key] = [_scalar(value)]
    return data


def parse_rule(slug, text, where=None):
    """A rule file into a Rule. `dirs:` is required — a rule that names no
    directory renders nowhere, which is a typo, not an intention."""
    where = where or (".ai/rules/%s.md" % slug)
    if not SLUG_RE.match(slug):
        raise RenderError("%s: a slug is lower-case letters, digits and hyphens" % where)
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise RenderError("%s: no --- frontmatter; dirs: is required" % where)
    front = _frontmatter(match.group("body"), where)
    unknown = sorted(set(front) - {"dirs", "paths"})
    if unknown:
        raise RenderError("%s: unknown key(s) %s — only dirs: and paths:"
                          % (where, ", ".join(unknown)))
    dirs = [d.rstrip("/") or "." for d in front.get("dirs", [])]
    if not dirs:
        raise RenderError("%s: dirs: is required and must name a directory" % where)
    for directory in dirs:
        if directory.startswith("/") or ".." in directory.split("/"):
            raise RenderError("%s: dirs: must stay inside the project: %s"
                              % (where, directory))
    body = text[match.end():].strip("\n")
    if not body.strip():
        raise RenderError("%s: the body is empty — a rule with no text renders nothing"
                          % where)
    return Rule(slug, dirs, front.get("paths", []), body)


def load_rules(rules_dir):
    """Every rule under `.ai/rules/`, by slug. README.md is the format, not a
    rule, so it is skipped — as the README itself says."""
    directory = Path(rules_dir)
    if not directory.is_dir():
        return []
    rules = []
    for path in sorted(directory.glob("*.md")):
        if path.name == "README.md":
            continue
        rules.append(parse_rule(path.stem, path.read_text(encoding="utf-8"),
                                where=str(path)))
    return rules


def rule_block(slug, body):
    """The managed block a rule renders into a directory's instruction file."""
    return "%s\n%s\n%s\n" % (RULE_START % slug, body.strip("\n"), RULE_END % slug)


def rule_doc(slug, paths, body):
    """Claude's path-scoped copy. The frontmatter has to be the first thing in
    the file for Claude Code to read it, so the generated line opens the body
    rather than the file."""
    front = "\n".join('  - "%s"' % p for p in paths)
    return "---\npaths:\n%s\n---\n%s\n\n%s\n" % (
        front, RULE_GENERATED % slug, body.strip("\n"))


def rule_targets(rules, runtimes):
    """What the rules render, in a fixed order: every (target, slug) a project
    with these runtimes should be carrying. Anything else carrying a rule marker
    is stale."""
    out = []
    for rule in rules:
        for runtime in sorted(runtimes):
            name = RULE_FILE.get(runtime)
            if name is None:
                continue
            for directory in rule.dirs:
                target = name if directory == "." else "%s/%s" % (directory, name)
                out.append(dict(kind="block", slug=rule.slug, target=target,
                                content=rule_block(rule.slug, rule.body)))
        if rule.paths and "claude" in runtimes:
            out.append(dict(kind="doc", slug=rule.slug,
                            target="%s/%s.md" % (CLAUDE_RULES_DIR, rule.slug),
                            content=rule_doc(rule.slug, rule.paths, rule.body)))
    return out


def splice_rule(text, slug, block):
    """Put one rule block into a file, replacing the block of that slug if it is
    already there. Everything outside the markers is the project's and is
    returned untouched."""
    start_marker, end_marker = RULE_START % slug, RULE_END % slug
    start, end = text.find(start_marker), text.find(end_marker)
    if start < 0 or end < 0:
        return text.rstrip("\n") + "\n\n" + block if text.strip() else block
    return text[:start] + block.rstrip("\n") + text[end + len(end_marker):]


def strip_rule(text, slug):
    """Take one rule block away again, and the blank line it was given."""
    start_marker, end_marker = RULE_START % slug, RULE_END % slug
    start, end = text.find(start_marker), text.find(end_marker)
    if start < 0 or end < 0:
        return text
    head, tail = text[:start], text[end + len(end_marker):]
    if head.strip() and tail.strip():
        return head.rstrip("\n") + "\n\n" + tail.lstrip("\n")
    if head.strip():
        return head.rstrip("\n") + "\n"
    return tail.lstrip("\n")


def rule_slugs_in(text):
    """The slugs of every rule block a file carries."""
    return [m.group("slug") for m in RULE_MARKER_RE.finditer(text)]


def block_of(text):
    """The managed block of an instruction file, markers included, or None."""
    start = text.find(BLOCK_START)
    end = text.find(BLOCK_END)
    if start < 0 or end < 0:
        return None
    return text[start:end + len(BLOCK_END)]


def measure(paths, whole=False, budget=None, out=sys.stdout):
    """Print `<file> <kind> N B` per file; exit 1 when one is over budget."""
    over = False
    for name in paths:
        text = Path(name).read_text(encoding="utf-8")
        kind = "file"
        if not whole:
            block = block_of(text)
            if block is not None:
                text, kind = block, "block"
        size = len(text.encode("utf-8"))
        line = "%s %s %d B" % (name, kind, size)
        if budget is not None:
            line += " (budget %d)" % budget
            if size > budget:
                line += " OVER"
                over = True
        print(line, file=out)
    return 1 if over else 0


def constitution(path, max_lines=15, max_bytes=4096, out=sys.stdout):
    """A constitution nobody can hold in their head is not one. Count the
    numbered principles and the bytes, and say which line broke the cap."""
    text = Path(path).read_text(encoding="utf-8")
    principles = [line for line in text.split("\n")
                  if re.match(r"^C\d+\.", line.strip())]
    size = len(text.encode("utf-8"))
    print("%s %d principles, %d B" % (path, len(principles), size), file=out)
    over = False
    if len(principles) > max_lines:
        print("%s: %d principles, at most %d — move the rest to .ai/policies/"
              % (path, len(principles), max_lines), file=sys.stderr)
        over = True
    if size > max_bytes:
        print("%s: %d B, at most %d B" % (path, size, max_bytes), file=sys.stderr)
        over = True
    for line in principles:
        body = line.strip()
        if len(body.encode("utf-8")) > 200:
            print("%s: a principle is %d B — one line each: %s…"
                  % (path, len(body.encode("utf-8")), body[:60]), file=sys.stderr)
            over = True
    return 1 if over else 0


def _parse_vars(pairs):
    out = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise RenderError("--var wants K=V, got %r" % pair)
        key, value = pair.split("=", 1)
        out[key] = value
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(prog="render_instructions.py")
    sub = parser.add_subparsers(dest="command", required=True)

    render_cmd = sub.add_parser("render", help="render one stub")
    render_cmd.add_argument("--scope", required=True, choices=SCOPES)
    render_cmd.add_argument("--runtime", required=True)
    render_cmd.add_argument("--kind", default="block", choices=KINDS)
    render_cmd.add_argument("--source", default=str(DEFAULT_SOURCE))
    render_cmd.add_argument("--var", action="append", metavar="K=V")
    render_cmd.add_argument("--out")

    build_cmd = sub.add_parser("build", help="regenerate the committed templates")
    build_cmd.add_argument("--check", action="store_true")
    build_cmd.add_argument("--source", default=str(DEFAULT_SOURCE))
    build_cmd.add_argument("--templates", default=str(DEFAULT_TEMPLATES))
    build_cmd.add_argument("--project-init", default=str(DEFAULT_PROJECT_INIT))

    measure_cmd = sub.add_parser("measure", help="size a file or its managed block")
    measure_cmd.add_argument("files", nargs="+")
    measure_cmd.add_argument("--block", dest="whole", action="store_false",
                             default=False)
    measure_cmd.add_argument("--whole", dest="whole", action="store_true")
    measure_cmd.add_argument("--budget", type=int)

    const_cmd = sub.add_parser("constitution", help="check a constitution's size")
    const_cmd.add_argument("file")
    const_cmd.add_argument("--max-lines", type=int, default=15)
    const_cmd.add_argument("--max-bytes", type=int, default=4096)

    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            return build(args.check, args.source, args.templates, args.project_init)
        if args.command == "measure":
            return measure(args.files, args.whole, args.budget)
        if args.command == "constitution":
            return constitution(args.file, args.max_lines, args.max_bytes)
        text = render(
            args.scope, args.runtime, args.kind, args.source, _parse_vars(args.var)
        )
    except RenderError as exc:
        print("render_instructions.py: %s" % exc, file=sys.stderr)
        return 1
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
