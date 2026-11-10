#!/usr/bin/env python3
"""/rr-setup's deterministic half: a project's own toolbox, its verify command,
and whether superpowers is on (spec R9, R28, SQ5, SQ12 variant B).

  setup.py survey [--root DIR]              the toolbox, the proposed verify_command, the superpowers line
  setup.py check  [--root DIR]              exit 1 VERIFY_COMMAND_MISSING unless verification.md names one
  setup.py verify [--root DIR] --set CMD    write verify_command into verification.md (after the human confirmed)

survey and check write nothing. The toolbox is production behaviour (C1): it is
inventoried in place, never copied or moved; what to inventory is the constants
FOREIGN_ROOTS and OWN_* below.
The enabledPlugins line is printed, never written: .claude/settings.json is the
human's.

Exit codes: 0 done; 1 VERIFY_COMMAND_MISSING; 2 usage;
3 refused (the line is already set).
"""
import argparse
import json
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFICATION = os.path.join(".ai", "policies", "verification.md")
SUPERPOWERS_KEY = "superpowers@superpowers-marketplace"
SKIP_DIRS = {".git", ".ai", "vendor", "node_modules", "__pycache__", ".venv"}
PURPOSE_MAX = 120
UNKNOWN = "UNKNOWN — no description and no leading comment"
VERIFY_RE = re.compile(r"(?m)^verify_command:[ \t]*(.*)$")
MAKE_TARGET_RE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9_. \t-]*?)\s*:(?![=:])(.*)$")
BLOCK_SCALAR_RE = re.compile(r"^[|>][-+]?$")
# Paths a foreign AI tool owns (Spec Kit, Kiro, AI-DLC, Cursor, Copilot): no part of the project's own toolbox.
FOREIGN_ROOTS = [
    ".specify/",
    "specs/",
    ".claude/commands/speckit*",
    ".claude/skills/speckit-*",
    ".github/prompts/speckit*",
    ".github/skills/speckit-*",
    ".github/agents/speckit*",
    ".codex/prompts/speckit*",
    ".agents/skills/speckit-*",
    ".gemini/commands/speckit*",
    ".cursor/commands/speckit*",
    ".cursor/skills/speckit-*",
    ".kiro/",
    "aidlc-docs/",
    ".amazonq/rules/aws-aidlc-rules/",
    ".amazonq/aws-aidlc-rule-details/",
    ".cursorrules",
    ".cursor/",
    ".github/copilot-instructions.md",
    ".github/instructions/",
]
# What `survey` inventories in place (SQ5): globs by kind, the guards' name words, the verify-command sources.
OWN_INVENTORY = [
    {"glob": ".claude/skills/*/SKILL.md", "kind": "skill", "router": "skill"},
    {"glob": ".claude/commands/**/*.md", "kind": "command", "router": "command"},
    {"glob": ".claude/rules/**/*.md", "kind": "rule"},
    {"glob": ".claude/agents/*.md", "kind": "agent"},
    {"glob": ".claude/hooks/*", "kind": "hook"},
    {"glob": ".agents/skills/*/SKILL.md", "kind": "skill", "router": "skill"},
    {"glob": ".codex/skills/*/SKILL.md", "kind": "skill", "router": "skill"},
    {"glob": ".codex/prompts/*.md", "kind": "command", "router": "command"},
    {"glob": ".codex/agents/*", "kind": "agent"},
    {"glob": ".codex/hooks/*", "kind": "hook"},
    {"glob": "bin/*.sh", "kind": "script"},
    {"glob": "Makefile", "kind": "make"},
]
OWN_GUARDS = {
    "ai-git-guard": [
        "git",
        "commit",
        "push",
        "merge"
    ],
    "ai-path-guard": [
        "path",
        "protect",
        "protected",
        "secret",
        "secrets",
        "dotenv"
    ],
    "ai-scope-guard": [
        "scope"
    ]
}
OWN_VERIFY = [
    {"file": "Makefile", "make_target": ["test", "tests", "check", "qa"], "command": "make {name}"},
    {"file": "composer.json", "script": ["test", "tests", "qa", "check"], "command": "composer {name}"},
    {"file": "package.json", "script": ["test"], "command": "npm test"},
    {"file": "bin/*.sh", "stem": ["test", "tests", "run-tests", "check"], "command": "bin/{name}.sh"},
    {"file": "phpunit.xml.dist", "command": "vendor/bin/phpunit"},
    {"file": "phpunit.xml", "command": "vendor/bin/phpunit"},
    {"file": "pytest.ini", "command": "python3 -m pytest"},
]


def die(message, code=2):
    print("setup.py: %s" % message, file=sys.stderr)
    sys.exit(code)


def read_text(path):
    """The text with `\n` line ends; `write` puts a CRLF file's `\r\n` back."""
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def is_crlf(path):
    try:
        with open(path, "rb") as fh:
            return b"\r\n" in fh.read()
    except OSError:
        return False


def glob_re(pattern):
    """The glob dialect: `*` stops at `/`, `**` crosses it, `**/` may match nothing."""
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
        else:
            out.append(re.escape(pattern[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def under_root(path, root):
    if root.endswith("/"):
        return path.startswith(root)
    return bool(glob_re(root).match(path)) or any(
        glob_re(root).match("/".join(path.split("/")[:n])) for n in range(1, path.count("/") + 1))


def walk(root):
    """Every file, following a symlinked directory (a skill linked from a
    shared tree is still the project's) but entering each real directory once."""
    seen = set()
    for base, dirs, files in os.walk(root, followlinks=True):
        real = os.path.realpath(base)
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS
                         and not os.path.exists(os.path.join(base, d, ".git")))
        for name in sorted(files):
            yield os.path.relpath(os.path.join(base, name), root).replace(os.sep, "/")


# ------------------------------------------------------------------ purpose

def clip(text):
    text = " ".join(text.split())
    return text if len(text) <= PURPOSE_MAX else text[:PURPOSE_MAX - 1].rstrip() + "…"


def frontmatter_description(lines):
    """(line number, description) from a `---` frontmatter block, or None."""
    if not lines or lines[0].strip() != "---":
        return None
    for n, line in enumerate(lines[1:], 2):
        if line.strip() == "---":
            return None
        match = re.match(r"description:\s*(.*)$", line)
        if not match or not match.group(1).strip():
            continue
        value = match.group(1).strip()
        if BLOCK_SCALAR_RE.match(value):
            # `description: >-` / `|`: the text is the indented lines below it.
            body = []
            for more in lines[n:]:
                if more.strip() == "---" or (more.strip() and not more[:1].isspace()):
                    break
                body.append(more.strip())
            text = " ".join(b for b in body if b)
            return (n + 1, text) if text else None
        return n, value.strip("\"'")
    return None


def markdown_purpose(lines):
    found = frontmatter_description(lines)
    if found:
        return found
    body, start = lines, 1
    if lines and lines[0].strip() == "---":
        ends = [n for n, line in enumerate(lines[1:], 1) if line.strip() == "---"]
        if ends:
            body, start = lines[ends[0] + 1:], ends[0] + 2
    for n, line in enumerate(body, start):
        text = line.strip().lstrip("#").strip()
        if text:
            return n, text
    return None


def comment_purpose(lines):
    """The first comment after the shebang and blank lines: `# …`, `// …`, a docstring."""
    for n, line in enumerate(lines, 1):
        text = line.strip()
        if not text or (n == 1 and text.startswith("#!")):
            continue
        for lead in ("#", "//", '"""', "'''"):
            if text.startswith(lead):
                text = text[len(lead):].strip().rstrip('"\'').strip()
                return (n, text) if text else None
        return None
    return None


def purpose_of(root, rel):
    full = os.path.join(root, rel)
    real, base = os.path.realpath(full), os.path.realpath(root)
    if os.path.commonpath([real, base]) != base:
        return None  # a link out of the project: listed UNKNOWN, never read into toolbox.md
    text = read_text(full)
    if text is None:
        return None
    lines = text.splitlines()
    if rel.endswith(".md"):
        return markdown_purpose(lines)
    return comment_purpose(lines)


def make_targets(root, rel="Makefile"):
    """[(line, target, purpose or None)]: `t: ## purpose`, else the comment just above."""
    text = read_text(os.path.join(root, rel))
    if text is None:
        return []
    out, above = [], None
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith("#"):
            above = line.lstrip("#").strip() or None
            continue
        match = MAKE_TARGET_RE.match(line)
        if match and not match.group(1).startswith("."):
            rest = match.group(2)
            purpose = rest.split("##", 1)[1].strip() if "##" in rest else above
            for target in match.group(1).split():
                out.append((n, target, purpose or None))
        if not line.startswith("\t"):
            above = None
    return out


# ---------------------------------------------------------------- inventory

def inventory(root):
    """[{path, kind, line, purpose, name, router}] in table order, then path order."""
    paths = [p for p in walk(root) if not any(under_root(p, r) for r in FOREIGN_ROOTS)]
    items, seen = [], set()
    for row in OWN_INVENTORY:
        pattern = glob_re(row["glob"])
        for rel in paths:
            if rel in seen or not pattern.match(rel):
                continue
            if "/hooks/" in rel and os.path.basename(rel).startswith("."):
                continue
            seen.add(rel)
            if row["kind"] == "make":
                for n, target, purpose in make_targets(root, rel):
                    items.append({"path": rel, "kind": "make", "line": n, "name": target,
                                  "purpose": purpose, "router": None})
                continue
            found = purpose_of(root, rel)
            items.append({"path": rel, "kind": row["kind"], "line": found[0] if found else None,
                          "purpose": found[1] if found else None, "name": command_name(rel, row),
                          "router": row.get("router")})
    return items


def command_name(rel, row):
    """`/name` a skill or command is invoked by: the skill's directory, or the
    command's path under its directory with `/` as `:`."""
    if row.get("router") == "skill":
        return rel.split("/")[-2]
    if row.get("router") == "command":
        base = row["glob"].split("*", 1)[0]
        return rel[len(base):-len(".md")].replace("/", ":")
    return os.path.basename(rel)


def guard_overlap(items):
    """{guard: [hook paths doing its job]} by the hook file name's words."""
    found = {g: [] for g in OWN_GUARDS}
    for item in items:
        if item["kind"] != "hook":
            continue
        words = set(re.split(r"[^a-z0-9]+", os.path.basename(item["path"]).lower()))
        for guard, keys in OWN_GUARDS.items():
            if words & set(keys):
                found[guard].append(item["path"])
    return found


# ------------------------------------------------------------------- verify

def verify_candidates(root):
    """[(command, source)] in table order; the first is the proposal. Nothing is run."""
    out = []
    for row in OWN_VERIFY:
        pattern = row["file"]
        if "*" in pattern:
            regex = glob_re(pattern)
            files = [p for p in walk(root) if regex.match(p)]
        else:
            files = [pattern] if os.path.isfile(os.path.join(root, pattern)) else []
        for rel in files:
            if "make_target" in row:
                targets = {t for _n, t, _p in make_targets(root, rel)}
                names = [t for t in row["make_target"] if t in targets]
            elif "script" in row:
                try:
                    scripts = (json.loads(read_text(os.path.join(root, rel)) or "{}") or {}).get("scripts") or {}
                except ValueError:
                    scripts = {}
                names = [s for s in row["script"] if s in scripts
                         and "no test specified" not in str(scripts[s])]
            elif "stem" in row:
                stem = os.path.basename(rel)[:-len(".sh")]
                names = [stem] if stem in row["stem"] else []
            else:
                names = [""]
            for name in names[:1]:
                command = row["command"].format(name=name)
                if command not in [c for c, _s in out]:
                    out.append((command, "%s%s" % (rel, " %s" % name if name else "")))
    return out


def verify_value(root):
    """None when verification.md is missing or has no verify_command line; else the
    value, '' for the template's comment-only line (sensors.read_commands' rule)."""
    text = read_text(os.path.join(root, VERIFICATION))
    if text is None:
        return None
    match = VERIFY_RE.search(text)
    if not match:
        return None
    value = match.group(1).strip()
    return "" if value.startswith("#") else value


# -------------------------------------------------------------- superpowers

def settings_files(root):
    home = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")
    return [os.path.join(home, "settings.json"),
            os.path.join(root, ".claude", "settings.json"),
            os.path.join(root, ".claude", "settings.local.json")]


def superpowers_line(root):
    """One line. Later files override earlier ones, as Claude Code merges them."""
    state, where = None, None
    for path in settings_files(root):
        try:
            with open(path, encoding="utf-8") as fh:
                plugins = (json.load(fh) or {}).get("enabledPlugins") or {}
        except (OSError, ValueError, AttributeError):
            continue
        for key, value in plugins.items() if isinstance(plugins, dict) else ():
            if key.split("@", 1)[0] == "superpowers":
                state, where = bool(value), "%s (%s)" % (path, key)
    if state:
        return "superpowers: enabled in %s — /rr-* delegate to it where it has the skill" % where
    return ("superpowers: not enabled%s — optional; to enable it, add to .claude/settings.json yourself: "
            "\"enabledPlugins\": {\"%s\": true}" % (" (disabled in %s)" % where if where else "", SUPERPOWERS_KEY))


def write(path, text):
    """In place through a symlink, keeping the file's mode and a CRLF file's
    line ends; a failed write leaves no temporary file behind."""
    path = os.path.realpath(path)
    if is_crlf(path):
        text = text.replace("\r\n", "\n").replace("\n", "\r\n")
    tmp = path + ".setup-tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
        if os.path.exists(path):
            shutil.copymode(path, tmp)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ----------------------------------------------------------------- commands

def cmd_survey(root):
    items = inventory(root)
    print("toolbox: %d item(s)" % len(items))
    for item in items:
        where = "%s:%d" % (item["path"], item["line"]) if item["line"] else item["path"]
        name = " %s" % item["name"] if item["kind"] == "make" else ""
        print("  %-8s %s%s — %s" % (item["kind"], where, name, clip(item["purpose"]) if item["purpose"] else UNKNOWN))
    for guard, paths in guard_overlap(items).items():
        print("  guard    %s: %s" % (guard, ", ".join(paths) + " (same job, kept)" if paths else "no project hook"))
    current = verify_value(root)
    candidates = verify_candidates(root)
    if current:
        print("verify_command: %s (verification.md)" % current)
    elif candidates:
        print("verify_command: proposed `%s` (from %s) — write it with `setup.py verify --set` once the human "
              "confirms" % candidates[0])
    else:
        print("verify_command: none found in Makefile, composer.json, package.json or bin/ — ask the human")
    for command, source in candidates[1:]:
        print("  also     `%s` (from %s)" % (command, source))
    print(superpowers_line(root))
    return 0


def cmd_check(root):
    value = verify_value(root)
    if not value or value.lower() == "none":
        print("VERIFY_COMMAND_MISSING: %s names no verify_command — propose one with `setup.py survey`, "
              "write it with `setup.py verify --set \"<command>\"` after the human confirms" % VERIFICATION)
        return 1
    print("verify_command: %s" % value)
    return 0


def cmd_verify(root, command):
    command = (command or "").strip()
    if not command or "\n" in command or command.startswith("#"):
        die("--set needs one command on one line")
    path = os.path.join(root, VERIFICATION)
    text = read_text(path)
    if text is None or not VERIFY_RE.search(text):
        die("%s has no verify_command line — run /rr-setup --update first" % VERIFICATION)
    current = verify_value(root)
    if current and current.lower() != "none":
        print("refused: verify_command is already `%s` — the human edits %s" % (current, VERIFICATION))
        return 3
    match = VERIFY_RE.search(text)
    write(path, text[:match.start()] + "verify_command:      " + command + text[match.end():])
    print("verify_command: %s (written to %s)" % (command, VERIFICATION))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="setup.py", description=__doc__.split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("survey", "check", "verify"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        if name == "verify":
            p.add_argument("--set", dest="command", required=True)
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        die("%s is not a directory" % root)
    if args.cmd == "survey":
        return cmd_survey(root)
    if args.cmd == "check":
        return cmd_check(root)
    return cmd_verify(root, args.command)


if __name__ == "__main__":
    sys.exit(main())
