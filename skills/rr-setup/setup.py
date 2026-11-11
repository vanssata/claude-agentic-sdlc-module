#!/usr/bin/env python3
"""/rr-setup's deterministic half: a project's own toolbox, its verify command,
and whether superpowers is on (spec R9, R28, SQ5, SQ12 variant B).

  setup.py survey [--root DIR]              the toolbox, the proposed verify_command, the superpowers line
  setup.py check  [--root DIR]              exit 1 VERIFY_COMMAND_MISSING unless verification.md names one
  setup.py verify [--root DIR] --set CMD    write verify_command into verification.md (after the human confirmed)
  setup.py options [--root DIR] [--all] [--skip KEY]… --json
                                            what each of the four setup options is now, as one JSON object
  setup.py options [--root DIR] [--all] [--skip KEY]… --open
                                            the unset ones as one dialog. First line: OPTIONS_DIALOG D<n> …
                                            (then state.py's two lines), OPTIONS_FALLBACK <why> (the questions
                                            as prose) or OPTIONS_NONE

--skip KEY (memory|runtime|survey|verify, repeatable) leaves that option out of what is asked, for both outputs and
with --all; its entry in the --json facts stays. survey, check and options --json write nothing; options --open
writes only the decisions state.py opens, none in the fallback. The toolbox is production behaviour (C1): it is
inventoried in place, never copied or moved; what to inventory is the constants
FOREIGN_ROOTS and OWN_* below.
The enabledPlugins line is printed, never written: .claude/settings.json is the
human's.

Exit codes: 0 done; 1 VERIFY_COMMAND_MISSING; 2 usage;
3 refused (the line is already set); 6 state.py refused to open the dialog (its message is passed through).
"""
import argparse
import hashlib
import importlib
import json
import os
import re
import shlex
import shutil
import subprocess
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
PENDING_RE = re.compile(r"DIALOG_PENDING ((?:D\d+ )*D\d+) — ")   # state.py's first line: the decisions it opened
# `options`: the sibling skills, the state.py of this install (the one the dialog's commands name), the files the
# survey signal compares, and the signals that scaffold_ai.runtimes() reads for `--runtime auto` as (instruction
# file, runtime directory).
SKILLS = os.path.dirname(HERE)
AI_TASK = os.path.join(SKILLS, "ai-task")
STATE_PY = os.path.join(AI_TASK, "state.py")
OPTION_KEYS = ("memory", "runtime", "survey", "verify")      # the four options, in the order they are asked
OVERVIEW = os.path.join(".ai", "project", "overview.md")
OVERVIEW_TEMPLATE = os.path.join(SKILLS, "ai-init", "templates", OVERVIEW)
HISTORY_INDEX = os.path.join(SKILLS, "project-update", "history", "index.json")
HISTORY_KEY = "ai-init/.ai/project/overview.md"
RUNTIME_SIGNALS = {"claude": ("CLAUDE.md", ".claude"), "codex": ("AGENTS.md", ".codex"),
                   "gemini": ("GEMINI.md", ".gemini"), "junie": (None, ".junie")}
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


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
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


# ------------------------------------------------------------------ options

def sibling(directory, name):
    """A module of this skill or of another, imported once its directory leads sys.path: `python3 -I` puts none
    there, and the module's own imports are by name (memory_sync reaches memory_compact that way). Skills are
    installed independently, so a missing module is an ImportError for the caller to answer."""
    if directory not in sys.path:
        sys.path.insert(0, directory)
    sys.dont_write_bytecode = True  # a read-only verb leaves no __pycache__ in the install
    return importlib.import_module(name)


def digest(data):
    """sha256 with LF line ends, as update.py's History.shipped reads a file a CRLF checkout changed."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


def in_git_tree(root):
    try:
        done = subprocess.run(["git", "-C", root, "rev-parse", "--is-inside-work-tree"],
                              capture_output=True, text=True, check=False)
    except OSError:  # no git binary
        return False
    return done.returncode == 0 and done.stdout.strip() == "true"


def dialog_on(root):
    """state.py's own answer (`consent --json`): the project's dialog.json on, the runtime's dialog tool verified and
    a session id in this environment. False without dialog.json and when state.py cannot answer."""
    if not os.path.isfile(os.path.join(root, ".ai", "policies", "dialog.json")):
        return False
    try:
        done = subprocess.run([sys.executable, "-I", "-B", os.path.join(AI_TASK, "state.py"), "--root", root,
                               "consent", "--json"], capture_output=True, text=True, check=False)
        data = json.loads(done.stdout) if done.returncode == 0 else None
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and data.get("dialog") is True


def author_source(cfg):
    """Where `cfg.author` comes from, in the order memory_sync.MemoryConfig.author tries them."""
    if cfg.local.get("author"):
        return "local config"
    return next(("$" + name for name in ("USER", "USERNAME") if os.environ.get(name)), "default")


def fts5():
    """FTS5 in this Python's sqlite3, by memory_store's own probe (AI_MEMORY_NO_FTS=1 turns it off);
    False without the sqlite3 module."""
    try:
        return sibling(AI_TASK, "memory_store").fts5_available()
    except ImportError:
        return False


def memory_option(root, git):
    """Packages-mode project memory: set once memory.json exists, its mode being `current`. `author` is what
    `memory enable` writes without --author (the local config, else $USER): memory_sync's own answer, never git's."""
    def unavailable(why):
        return {"key": "memory", "state": "unavailable", "why": why}
    if not git:
        return unavailable("not a git work tree")
    try:
        sync = sibling(AI_TASK, "memory_sync")
    except ImportError as exc:
        return unavailable("the memory modules are not installed beside state.py (%s)" % exc)
    try:
        cfg = sync.load_config(root)
    except sync.MemoryError_ as exc:
        return unavailable(str(exc))
    return {"key": "memory", "state": "set" if cfg.present else "unset", "current": cfg.mode if cfg.present else None,
            "author": cfg.author, "author_from": author_source(cfg),
            "period": None if cfg.present else sync.DEFAULTS["period"], "fts5": fts5()}


def runtime_option(root):
    """`declared`: the runtimes the repository already names, by the signals scaffold_ai.runtimes() reads.
    `auto`: what `--runtime auto` would scaffold now, as that function resolves it, in the spelling --runtime takes."""
    declared = [name for name, (instruction, directory) in RUNTIME_SIGNALS.items()
                if (instruction and os.path.exists(os.path.join(root, instruction)))
                or os.path.isdir(os.path.join(root, directory))]
    scaffold = sibling(HERE, "scaffold_ai")
    chosen = scaffold.runtimes("auto", root)
    return {"key": "runtime", "state": "set" if declared else "unset", "declared": declared,
            "auto": ",".join(name for name in scaffold.RUNTIMES if name in chosen)}


def surveyed(root):
    """No depth is recorded anywhere. A survey fills .ai/project/overview.md, so a copy that is none of the files
    the plugin shipped for it (today's template, or a version in project-update's history index: update.py's
    own test for an unedited file) has been written into."""
    mine = read_bytes(os.path.join(root, OVERVIEW))
    if mine is None:
        return False
    shipped = set()
    template = read_bytes(OVERVIEW_TEMPLATE)
    if template is not None:
        shipped.add(digest(template))
    try:
        shipped.update(json.loads(read_text(HISTORY_INDEX) or "{}")[HISTORY_KEY])
    except (ValueError, KeyError, TypeError):
        pass
    return digest(mine) not in shipped


def verify_option(root):
    """Set by check's own rule (a value that is not `none`); else the proposal `survey` makes, and the others."""
    current = verify_value(root)
    if current and current.lower() != "none":
        return {"key": "verify", "state": "set", "current": current}
    found = [{"command": command, "from": source} for command, source in verify_candidates(root)]
    return {"key": "verify", "state": "unset", "proposal": found[0] if found else None, "also": found[1:]}


def option_facts(root, show_all=False, skip=()):
    """What each of the four setup options is now, read-only (spec interactive-setup-options R9, R16). `ask` lists
    the unset ones in the order memory, runtime, survey, verify; `show_all` lists every one not unavailable; `skip`
    leaves keys out of it that the caller has answered another way (/rr-setup --survey). The facts of a skipped
    option stay as computed: they are still true, and only what is asked changes."""
    git = in_git_tree(root)
    options = [memory_option(root, git), runtime_option(root),
               {"key": "survey", "state": "set" if surveyed(root) else "unset"}, verify_option(root)]
    return {"schema": 1, "root": root, "git": git, "dialog": dialog_on(root),
            "ask": [o["key"] for o in options if o["key"] not in skip
                    and (o["state"] == "unset" or (show_all and o["state"] == "set"))],
            "options": options}


# ------------------------------------------------------------ options --open

def state_label(root, *words):
    """The command that runs this install's state.py with `words` on this project, absolute and quoted as
    rr_state.labels.state_label writes it: a pick and the call the agent makes are then one string. A copy, not an
    import: rr_state.fs.ENTRY is only set by state.py's own entry."""
    return "python3 %s %s" % (shlex.quote(STATE_PY), shlex.join(["--root", root, *words]))


def choice_option(label, value):
    return {"kind": "choice", "label": label, "value": value}


def command_option(label, description):
    return {"kind": "command", "label": label, "description": description}


def shown(text):
    """`text` inside backticks, as a label shows a command, or None when the opener would refuse it: a backtick of its
    own ends the span early, and a choice value is at most 200 printable characters (dialog_cmd.SETUP_VALUE_MAX), so
    that "Use `…`" stays inside the labels' 400."""
    return "`%s`" % text if text and "`" not in text and len(text) <= 200 and text.isprintable() else None


def decision(key, question, options):
    return {"key": key, "header": key.capitalize(), "question": question, "options": options}


def memory_decision(option, root, name):
    """Memory is asked first, so that its pick is the earliest the gate passes (spec B3). Its commands are `memory
    enable` of this install's state.py: --period only while memory.json is absent (`period` is then set), never
    --author, because enable writes the author the question names (D1): the local config's, else $USER's."""
    period = ["--period", option["period"]] if option["period"] else []
    who = "Author %s (from %s)" % (option["author"], option["author_from"])
    if option["state"] == "set":
        first = choice_option("Keep — %s mode" % option["current"], "keep")
        question = ("Project memory for %s is in %s mode: off keeps closed tasks only in .ai/reports/. packages also writes "
                    "one compact committed file per developer per period under .ai/memory/, checked by a pre-push hook. "
                    "%s. Keep it, or run memory enable?" % (name, option["current"], who))
    else:
        first = choice_option("Off — keep files mode", "off")
        question = ("Project memory for %s: off keeps closed tasks only in .ai/reports/. packages also writes one compact "
                    "committed file per developer per %s under .ai/memory/, checked by a pre-push hook. %s, period %s. "
                    "Turn it on?" % (name, option["period"], who, option["period"]))
    return decision("memory", question, [
        first,
        command_option(state_label(root, "memory", "enable", *period),
                       "packages; installs .git/hooks/pre-push unless one exists or core.hooksPath is set"),
        command_option(state_label(root, "memory", "enable", *period, "--index", "sqlite"),
                       "plus a local, git-ignored SQLite index; FTS5 %s — without it search scans: same results, slower"
                       % ("yes" if option["fts5"] else "no"))])


def runtime_decision(option, name):
    """No "Not now": the four runtimes use all the options a question has. `auto` names what it resolves to: the
    runtime this copy is installed for while the repository declares none, else what it declares."""
    auto = "Auto — what the repository declares"
    auto += " (%s)" % option["auto"] if option["declared"] else ", else %s" % option["auto"]
    return decision("runtime", "Which agent runtimes work on %s? The scaffold adds their instruction files and directories "
                               "and never removes one." % name,
                    [choice_option(auto, "auto"), choice_option("Claude Code only", "claude"),
                     choice_option("Codex only", "codex"), choice_option("Claude Code and Codex", "both")])


def survey_decision(option, name):
    options = [choice_option("Light — your 10-minute brain dump + 2 discovery agents", "light"),
               choice_option("Full — inventory + 6 discovery agents", "full")]
    if option["state"] == "set":
        options.append(choice_option("Keep the current survey", "keep"))
    return decision("survey", "How deep should the first survey of %s go?" % name, options)


def verify_decision(option):
    """Unset: not now, the proposal, at most one other candidate, or typed in chat (a free-text answer is a decline,
    so a command of the human's own is typed after the dialog: spec A3). A command the opener would refuse is not
    offered. Set (--all): keep it, or edit it by hand — verify_command is the human's once written."""
    intro = "verify_command — the fast suite every task runs, e2e excluded."
    if option["state"] == "set":
        current = shown(option["current"])
        return decision("verify", "%s Current: %s." % (intro, current or "set in .ai/policies/verification.md"),
                        [choice_option("Keep %s" % current if current else "Keep the current command", "keep"),
                         choice_option("Change — I edit it myself", "edit")])
    proposal = [option["proposal"]] if option["proposal"] and shown(option["proposal"]["command"]) else []
    also = [c for c in option["also"] if shown(c["command"])][:1]
    found = proposal + also
    options = [choice_option("Not now — ask me in chat", "")]
    options += [choice_option("Use %s" % shown(c["command"]), c["command"]) for c in found]
    options.append(choice_option("Another — I type it in chat", "other"))
    proposed = ("Proposed: %s (from %s)." % (shown(found[0]["command"]), found[0]["from"]) if found
                else "No proposal: nothing found in the project's files.")
    return decision("verify", "%s %s" % (intro, proposed), options)


def decision_for(option, root, name):
    if option["key"] == "memory":
        return memory_decision(option, root, name)
    if option["key"] == "runtime":
        return runtime_decision(option, name)
    if option["key"] == "survey":
        return survey_decision(option, name)
    return verify_decision(option)


def dialog_off_why(root):
    """Why state.py's switch is off here, as the first cause found in the order it tests them: the project's
    dialog.json, an unattended run or session, then the two it cannot be told apart by from here (the runtime's dialog
    tool the installer verified, a session id)."""
    try:
        with open(os.path.join(root, ".ai", "policies", "dialog.json"), encoding="utf-8") as fh:
            enabled = (json.load(fh) or {}).get("enabled") is True
    except (OSError, ValueError, AttributeError):
        enabled = False
    if not enabled:
        return "no enabled .ai/policies/dialog.json"
    if os.environ.get("AI_UNATTENDED", "").strip().lower() not in ("", "0", "false", "no"):
        return "AI_UNATTENDED is set (an unattended run)"
    if os.environ.get("CLAUDE_CODE_SESSION_ATTENDED") == "0":
        return "CLAUDE_CODE_SESSION_ATTENDED=0 (an unattended session)"
    return "the runtime's dialog tool is not verified (riskrails/profile.json dialog.tool) or this session has no id"


def open_dialog(root, decisions):
    """The decisions piped to this install's state.py, which opens all of them or none. Returns (exit code, None) once
    it answered: 0 with OPTIONS_DIALOG and its two lines unchanged, 6 with its refusal passed through (the skill
    settles what is open first, or falls back); (None, why) when it found the dialog off after all, for the fallback."""
    spec = json.dumps({"schema": 1, "decisions": decisions})           # ASCII only: no locale decides how it is read
    try:
        done = subprocess.run([sys.executable, "-I", "-B", "-X", "utf8", STATE_PY, "--root", root, "decision", "open",
                               "--kind", "setup", "--spec", "-"],
                              input=spec, capture_output=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        sys.stderr.write("setup.py: cannot run %s (%s)\n" % (STATE_PY, exc))
        return 6, None
    if done.returncode == 1:              # its die() default: the dialog off after all, or a decision.json it cannot read
        last = ([line for line in done.stderr.splitlines() if line.strip()] or ["no message"])[-1]
        text = " ".join(last.replace(root + os.sep, "").replace("state.py: ", "", 1).split())
        return None, "state.py could not open the dialog: %s" % (text if len(text) <= 200 else text[:199] + "…")
    if done.returncode != 0:
        sys.stderr.write(done.stderr or "setup.py: state.py exited %d without a message\n" % done.returncode)
        return 6, None
    ids = PENDING_RE.match(done.stdout.split("\n", 1)[0])
    if not ids:
        sys.stderr.write("setup.py: state.py answered with no DIALOG_PENDING line; 'state.py decision show' lists "
                         "what it opened\n")
        return 6, None
    sys.stderr.write(done.stderr)
    print("OPTIONS_DIALOG %s" % ids.group(1))
    sys.stdout.write(done.stdout)
    return 0, None


def fallback_lines(root, why, decisions):
    """The questions as numbered prose, in the dialog's words (a command is its arguments after the project's root, and
    its description), then, when memory is asked, the command the human runs: nothing is enabled from here, and
    nothing is written."""
    prefix = state_label(root) + " "
    lines = ["OPTIONS_FALLBACK %s" % why]
    for number, item in enumerate(decisions, 1):
        lines.append("%d. %s: %s" % (number, item["header"], item["question"]))
        lines += ["   %s) %s" % (letter, o["label"] if o["kind"] == "choice"
                                  else "%s — %s" % (o["label"][len(prefix):], o["description"]))
                  for letter, o in zip("abcd", item["options"])]
    memory = next((d for d in decisions if d["key"] == "memory"), None)
    if memory:
        enable = next(o["label"] for o in memory["options"] if o["kind"] == "command")
        lines.append("memory is the human's, in their own terminal: %s [--index sqlite]" % enable)
    return lines


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


def cmd_options(root, show_all, skip):
    print(json.dumps(option_facts(root, show_all, skip), ensure_ascii=False))
    return 0


def cmd_options_open(root, show_all, skip):
    """R10, R17: nothing to ask → OPTIONS_NONE; the dialog on → the questions opened through state.py; else the
    questions as prose. Memory is only ever in `ask` inside a git work tree (R16)."""
    facts = option_facts(root, show_all, skip)
    if not facts["ask"]:
        print("OPTIONS_NONE")
        return 0
    name = os.path.basename(root) or root
    by_key = {o["key"]: o for o in facts["options"]}
    decisions = [decision_for(by_key[key], root, name) for key in facts["ask"]]
    if facts["dialog"]:
        code, why = open_dialog(root, decisions)
        if code is not None:
            return code
    else:
        why = dialog_off_why(root)
    print("\n".join(fallback_lines(root, why, decisions)))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="setup.py", description=__doc__.split("\n\n", 1)[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("survey", "check", "verify", "options"):
        p = sub.add_parser(name)
        p.add_argument("--root", default=".")
        if name == "verify":
            p.add_argument("--set", dest="command", required=True)
        if name == "options":
            p.add_argument("--all", action="store_true")
            p.add_argument("--skip", action="append", default=[], choices=OPTION_KEYS)
            output = p.add_mutually_exclusive_group(required=True)
            output.add_argument("--json", action="store_true")
            output.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        die("%s is not a directory" % root)
    if args.cmd == "survey":
        return cmd_survey(root)
    if args.cmd == "check":
        return cmd_check(root)
    if args.cmd == "options":
        run = cmd_options if args.json else cmd_options_open
        return run(root, args.all, args.skip)
    return cmd_verify(root, args.command)


if __name__ == "__main__":
    sys.exit(main())
