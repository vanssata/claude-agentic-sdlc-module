#!/usr/bin/env python3
"""Bring a project's RiskRails files up to date with the installed plugin.

  update.py [project-dir] [--apply [--confirm-delete NAME] [--confirm-cleanup NAME]] [--check [--budget]]

Default is a dry run: print what would change, write nothing.
  --apply   write the changes
  --check   print one line and exit 1 when an update is pending
  --check --budget   print one line per root instruction file over its byte
            budget (block over `project`, file over `skeleton`) and exit 1
  --confirm-delete NAME   a human confirms this run's gated rows (`regenerate?`,
            `delete?`); refused (exit 5, CONFIRM_REFUSED) unless a terminal outside
            Claude Code or Codex (no agent-session marker) or AI_UNATTENDED
  --confirm-cleanup NAME  the same for the [cleanup] rows

Exit codes:
  0  done (or, with --check, the project is current)
  1  --check: an update is pending; --check --budget: a file is over budget
  2  usage error, missing templates, .ai/VERSION unreadable or newer than the plugin
  3  an apply aborted part-way; nothing after the failing item was written
  5  refused: --confirm-* without a human (CONFIRM_REFUSED on stdout line 1)
  6  a file this update keeps cannot be read (KEPT_UNREADABLE on stdout line 1); nothing written

This version regenerates its own files and converts nothing, except one split:
a project that still has the mixed files gets .ai/policies/verification.md (the
command lines of testing.md, verbatim) and .ai/policies/weight.project.json
(what its weight.json changed against the plugin's table) once, when they are absent.

What it does, per file:
  GENERATED  .ai/AGENTS.md, .ai/VERSION, .ai/policies/{path-guard.json, coding.md,
    safety.md, security.md, testing.md, weight.md}, .ai/rules/README.md,
    .ai/state/README.md, <runtime>/memory/README.md, the managed block of each
    instruction file: rewritten from the plugin. A copy that is a version the plugin
    once shipped is replaced (regenerate); an edited one waits for --confirm-delete
    (regenerate?) and its original is kept under .ai/reports/project-update-<date>/original/.
  KEPT  .ai/project, .ai/reports, .ai/memory, .ai/state, docs/sdlc, verification.md,
    weight.project.json, dialog.json, memory.json, .ai/local/memory, edited shared
    overrides, the text outside the managed blocks, .claude/settings.json,
    .codex/config.toml, .gitignore (entries appended): never rewritten.
  REMOVED  .ai/rules/<slug>.md, .ai/local/plugin-update/, the old weight.json after its
    split, an unedited copy of a shared file: delete?, gated, with a copy in original/.
  [cleanup] rows are unchanged: proposals only, settled with --confirm-cleanup.

A project uses the runtime(s) it declares: CLAUDE.md or .claude/ means Claude
Code, AGENTS.md or .codex/ means Codex, both means both. A project that declares
neither gets the runtime this copy of the plugin was installed for.
"""
import argparse, contextlib, hashlib, importlib.util, io, json, os, re, shlex, subprocess, sys, tempfile
from collections import OrderedDict
from datetime import datetime, timedelta, timezone

try:
    import tomllib
except ImportError:  # Python before 3.11: .codex/config.toml is not checked
    tomllib = None

sys.dont_write_bytecode = True  # never leave __pycache__ in an installed plugin
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import render_instructions  # noqa: E402  # lives next to this script
SKILLS = os.path.dirname(HERE)
LAST_MIGRATING_VERSION = "3.1.0"  # the last riskrails that converts older trees; I3 names it
EXIT_KEPT_UNREADABLE = 6
REFUSED = "CONFIRM_REFUSED"


class SchemaError(Exception):
    """The project's schema cannot be read or is newer than this plugin."""


def env(name, default=None):
    """RISKRAILS_<name>."""
    return os.environ.get("RISKRAILS_" + name, default)


TEMPLATES = {
    "ai-init": env("TEMPLATES", os.path.join(SKILLS, "ai-init", "templates")),
    "project-init": os.environ.get("CLAUDE_ROUTING_TEMPLATES", os.path.join(SKILLS, "project-init", "templates")),
}
HISTORY = env("HISTORY", os.path.join(HERE, "history"))
# The shared tree every project reads unless it keeps its own copy: installed
# beside the skills as riskrails/ai, or ai/ at the root of a checkout.
PLUGIN_HOME = os.path.dirname(SKILLS)
SHARED = env("SHARED") or next(
    (p for p in (os.path.join(PLUGIN_HOME, "riskrails", "ai"), os.path.join(PLUGIN_HOME, "ai"))
     if os.path.isdir(p)), os.path.join(PLUGIN_HOME, "riskrails", "ai"))
VERSION_FILE = ".ai/VERSION"
ROUTER_FILE = ".ai/AGENTS.md"
STALE_DAYS = 7  # an unclosed task whose last event is older is proposed for cleanup
STATE_FILE = ".ai/state/state.json"
TESTING_MD = ".ai/policies/testing.md"
VERIFICATION_MD = ".ai/policies/verification.md"
WEIGHT_JSON, WEIGHT_MD = ".ai/policies/weight.json", ".ai/policies/weight.md"
WEIGHT_PROJECT = ".ai/policies/weight.project.json"
LOCAL_CACHE = ".ai/local/plugin-update"

# D2. GENERATED targets copied from a template as they are. weight.md is rendered,
# .ai/VERSION is written last, the managed blocks and the runtimes' memory READMEs
# come from the maps below.
GENERATED = (ROUTER_FILE, ".ai/policies/path-guard.json", ".ai/policies/coding.md", ".ai/policies/safety.md",
             ".ai/policies/security.md", TESTING_MD, ".ai/rules/README.md", ".ai/state/README.md")
# Template files created when missing and never touched again: the project's own from then on.
CREATE_ONLY = (VERIFICATION_MD, WEIGHT_PROJECT, ".ai/reports/.gitkeep")
CREATE_ONLY_DIRS = (".ai/project/",)
# Template files that are not copied: written last, the plugin's own table, the human's switch.
NOT_COPIED = (VERSION_FILE, WEIGHT_JSON, WEIGHT_MD, ".ai/policies/dialog.json")
KEPT = (".ai/project/", ".ai/reports/", ".ai/memory/", ".ai/state/", "docs/sdlc/", ".ai/local/memory/",
        WEIGHT_PROJECT, VERIFICATION_MD, ".ai/policies/dialog.json", ".ai/policies/memory.json",
        ".claude/settings.json", ".codex/config.toml", ".gitignore")


def is_kept(path):
    """True for a path update.py never rewrites. A GENERATED path under a KEPT
    directory (.ai/state/README.md) is generated: the two sets are disjoint."""
    if path in GENERATED:
        return False
    return any(path == k or (k.endswith("/") and path.startswith(k)) for k in KEPT)


# The shared set, literally: the plugin's tree must equal it (tested). A project
# copy identical to a shipped version is offered for deletion; an edited one is an override.
SHARED_SET = frozenset((
    ".ai/policies/production.md", ".ai/policies/database.md", ".ai/policies/git.md", ".ai/policies/release.md",
    ".ai/policies/context-management.md", ".ai/policies/tooling.md", ".ai/policies/model-routing.md",
    ".ai/policies/review-economy.md",
    ".ai/agents/context.md", ".ai/agents/discovery.md", ".ai/agents/implementer.md",
    ".ai/agents/planner.md", ".ai/agents/release.md", ".ai/agents/reviewer.md", ".ai/agents/risk.md",
    ".ai/agents/security.md", ".ai/agents/tester.md",
    ".ai/templates/task-context.md", ".ai/templates/impact-report.md", ".ai/templates/review-report.md",
    ".ai/templates/release-report.md", ".ai/templates/architecture-decision.md",
    ".ai/templates/implementation-plan.md",
    ".ai/using-riskrails.md", ".ai/workflows.md",
))
RULES_DIR = ".ai/rules"
# Directories a stale rule block is never hunted in: a dependency's instruction
# file is not ours (the path guard refuses it too), and .git is not text.
# A child holding a .git entry (worktree, nested repository, submodule) is pruned
# too, by the take-back walk (rendered_rules) and by the writer (nested_tree). The
# writer also skips a RULES_SKIP name or a symlinked directory (unwalked_dir), so it
# never writes where the take-back never walks.
RULES_SKIP = {".git", ".ai", "vendor", "node_modules", "bower_components",
              "third_party", "Pods", "site-packages", ".venv", ".pnpm", ".yarn"}
# Compared case-insensitively: on a case-insensitive filesystem `Vendor/` is `vendor/`.
RULES_SKIP_FOLDED = frozenset(n.casefold() for n in RULES_SKIP)
find_block = render_instructions.find_block

RUNTIME_MAP = {  # the per-runtime layer of the project-init scaffold: template, target, kind
    "claude": [("memory-README.md", ".claude/memory/README.md", "regenerate"),
               ("project-settings.json", ".claude/settings.json", "create")],
    "codex":  [("memory-README.md", ".codex/memory/README.md", "regenerate"),
               ("project-config.toml", ".codex/config.toml", "create")],
    "gemini": [("memory-README.md", ".gemini/memory/README.md", "regenerate")],
    "junie":  [("memory-README.md", ".junie/memory/README.md", "regenerate")],
}
SDLC_CREATE = (("sdlc-README.md", "docs/sdlc/README.md"), ("constitution.md", "docs/sdlc/constitution.md"))
INSTRUCTION_FILE = {  # runtime -> (file, block template, minimal template)
    "claude": ("CLAUDE.md", "CLAUDE.block.md", "CLAUDE.minimal.md"),
    "codex":  ("AGENTS.md", "AGENTS.block.md", "AGENTS.minimal.md"),
    "gemini": ("GEMINI.md", "GEMINI.block.md", "GEMINI.minimal.md"),
    "junie":  (".junie/guidelines.md", "junie-guidelines.block.md",
               "junie-guidelines.minimal.md"),
}


def project_runtimes(root):
    """The runtimes a project declares, or the one this plugin copy serves."""
    out = []
    if os.path.exists(os.path.join(root, "CLAUDE.md")) or os.path.isdir(os.path.join(root, ".claude")):
        out.append("claude")
    if os.path.exists(os.path.join(root, "AGENTS.md")) or os.path.isdir(os.path.join(root, ".codex")):
        out.append("codex")
    if os.path.exists(os.path.join(root, "GEMINI.md")) or os.path.isdir(os.path.join(root, ".gemini")):
        out.append("gemini")
    if os.path.isdir(os.path.join(root, ".junie")):
        out.append("junie")
    if not out:
        out.append("codex" if "/.codex/" in HERE + "/" else "claude")
    return out


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


class History:
    """index.json answers "was this ever shipped" from hashes alone; the blobs
    give the one-time split its base values."""

    def __init__(self, root):
        try:
            with open(os.path.join(root, "index.json"), encoding="utf-8") as fh:
                self.index = json.load(fh)
        except (OSError, ValueError, RecursionError):
            self.index = {}
        self.root = root

    def versions(self, key):
        """Every shipped version of a template, oldest first, as bytes."""
        out = []
        for h in self.index.get(key, []):
            try:
                out.append(read(os.path.join(self.root, "blobs", h)))
            except OSError:
                pass
        return out

    def hashes(self, key):
        """The sha of every version shipped under this key; a version whose blob is gone still counts."""
        return set(self.index.get(key, []))

    def shipped(self, key, data):
        """True when these bytes are a version the plugin shipped, also after a checkout turned its line endings into CRLF."""
        known = self.hashes(key)
        return sha(data) in known or sha(data.replace(b"\r\n", b"\n")) in known


def shared_files():
    """{".ai/<rel>": bytes} for every shared file the shared tree holds; empty when the tree is not installed."""
    out = {}
    for path in sorted(SHARED_SET):
        full = os.path.join(SHARED, path[len(".ai/"):])
        if os.path.isfile(full):
            out[path] = read(full)
    return out


def undeclared_shared():
    """Files in the shared tree outside the shared set, as .ai/ paths."""
    out = []
    for here, _dirs, files in os.walk(SHARED):
        for name in files:
            rel = ".ai/" + os.path.relpath(os.path.join(here, name), SHARED).replace(os.sep, "/")
            if rel not in SHARED_SET:
                out.append(rel)
    return sorted(out)


def git_dirty_ai(root):
    """True when .ai/ has changes git does not hold yet: git is the rollback of
    a migration that deletes, so it must hold them first. False outside a work
    tree, where there is nothing to say."""
    try:
        res = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", ".ai"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0 and bool(res.stdout.strip())


def git_states(root, rel_dir):
    """A function path -> how git holds a file under `rel_dir` (project-relative):
    "tracked" (committed and unchanged), "uncommitted" (changed, staged or not yet
    tracked, so git has no copy to restore) or "ignored"; None outside a work tree
    or for a path git does not know."""
    def run(*args):
        res = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=30, check=False)
        return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else None
    try:
        prefix = run("rev-parse", "--show-prefix")
        tracked = run("ls-files", "-z", "--", rel_dir)
        status = run("status", "--porcelain=v1", "-z", "--ignored", "-uall", "--", rel_dir)
    except (OSError, subprocess.SubprocessError):
        return lambda path: None
    if prefix is None or tracked is None or status is None:
        return lambda path: None
    prefix = prefix.strip()
    tracked = set(tracked.split("\0"))
    dirty, ignored = set(), []
    entries = status.split("\0")
    skip = False
    for entry in entries:
        if skip:  # the origin path of a rename
            skip = False
            continue
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        if "R" in xy or "C" in xy:
            skip = True
        if xy == "!!":
            ignored.append(path)
        else:
            dirty.add(path)

    def classify(path):
        if path in dirty:
            return "uncommitted"
        if any(path == i or (i.endswith("/") and path.startswith(i)) for i in ignored):
            return "ignored"
        return "tracked" if path in tracked else None
    return classify


def dump_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def unsafe_path(root, path):
    """Why a project-relative path must not be deleted: a symlink on the way to it,
    or a real path outside the project; None when it is safe. Run at plan time and
    again right before the delete."""
    real_root = os.path.realpath(root)
    here = root
    for part in path.split("/"):
        here = os.path.join(here, part)
        if os.path.islink(here):
            return "%s is a symlink" % os.path.relpath(here, root).replace(os.sep, "/")
    real = os.path.realpath(os.path.join(root, path))
    if real != real_root and not real.startswith(real_root + os.sep):
        return "%s resolves outside the project (%s)" % (path, real)
    return None

# ---------------------------------------------------------------- the one gate
# Set in the environment of a shell an agent runs: Claude Code's CLAUDECODE,
# and the names Codex gives its tool calls. Present counts, an empty value too.
AGENT_MARKERS = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI",
                 "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION")


def ai_unattended():
    """AI_UNATTENDED is set when it is non-empty and not 0, false or no (case
    and blanks ignored): one rule in every reader (risk 0587)."""
    return os.environ.get("AI_UNATTENDED", "").strip().lower() not in ("", "0", "false", "no")


def human_gate():
    """(passed, via, why) for --confirm-delete. A terminal outside any agent
    session is a human: via "terminal". Otherwise a launcher that declared the
    run unattended (AI_UNATTENDED) passes: via "unattended", as state.py's
    approve records it. Anything else is refused, and `why` says what was seen —
    a terminal alone is not enough, since an agent can open a pty (F3).

    Duplicated in spirit from skills/ai-task/state.py (human_present) on purpose:
    the two skills are installed independently and neither imports the other."""
    markers = [name for name in AGENT_MARKERS if name in os.environ]
    if os.isatty(0) and not markers:
        return True, "terminal", ""
    if ai_unattended():
        return True, "unattended", ""
    if markers:
        return False, None, ("this run is inside an agent session (%s %s set); run it in a terminal "
                             "outside Claude Code or Codex, not through the `!` prefix"
                             % (", ".join(markers), "is" if len(markers) == 1 else "are"))
    return False, None, "this run has no terminal"


# The name typed into --confirm-delete is the audit trail; the template's own
# "<your name>" copied verbatim names no one. The whole value, not a substring.


# The name typed into --confirm-delete is the audit trail; the template's own
# "<your name>" copied verbatim names no one. The whole value, not a substring.
PLACEHOLDER_NAME_RE = re.compile(r"\A\s*(?:<[^>]*>|your\s+name)\s*\Z", re.IGNORECASE)


def placeholder_name(name):
    return bool(PLACEHOLDER_NAME_RE.match(name or ""))


def refuse(reason, how):
    """Print the refusal the way every gate does — the marker on the first
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




# ---------------------------------------------------------------- the kept files
def template_version():
    """The schema number this plugin ships (its .ai/VERSION template)."""
    return int(read(os.path.join(TEMPLATES["ai-init"], VERSION_FILE)).decode().strip())


def project_version(root):
    """The project's .ai/VERSION: 0 when there is none; SchemaError when it cannot
    be read, is not a number, or is newer than this plugin's."""
    path = os.path.join(root, VERSION_FILE)
    try:
        raw = read(path) if os.path.lexists(path) else None
    except OSError as exc:  # a directory, a mode-000 file, a dangling link
        raise SchemaError("%s cannot be read: %s" % (VERSION_FILE, exc)) from exc
    if raw is None:
        return 0
    try:
        text = raw.decode("utf-8").strip()
    except UnicodeDecodeError:
        text = ""
    if not re.fullmatch(r"\d+", text):
        raise SchemaError("%s is not a schema number: %r" % (VERSION_FILE, raw[:40]))
    ours = template_version()
    if int(text) > ours:
        raise SchemaError("%s says schema %s, this plugin ships schema %d — update the plugin "
                          "(riskrails/install.sh)" % (VERSION_FILE, text, ours))
    return int(text)


_MODULES = {}


def sibling(name, *parts):
    """A module of another skill, loaded by path once per run (skills are installed independently)."""
    if name not in _MODULES:
        spec = importlib.util.spec_from_file_location("riskrails_" + name, os.path.join(SKILLS, *parts))
        _MODULES[name] = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_MODULES[name])
    return _MODULES[name]


def weight_module():
    """skills/ai-task/weight.py, the renderer behind `state.py weight --mirror`."""
    return sibling("weight", "ai-task", "weight.py")


def weight_overlay():
    """skills/ai-task/weight_overlay.py: the plugin's table with the project's laid over it."""
    return sibling("weight_overlay", "ai-task", "weight_overlay.py")


def shipped_weight():
    return os.path.join(TEMPLATES["ai-init"], WEIGHT_JSON)


# Old shapes the update no longer converts: literal checks, nothing parsed (D4).
OLD_MARKERS = (b"<!-- claude-agentic:", b"<!-- Codex-agentic:")


def check_kept(root):
    """[(path, reason)] for every kept file its own reader cannot take and every old
    shape this version no longer converts. Reads only: the caller refuses on a
    non-empty answer before anything is written (R12)."""
    bad = []

    def raw_of(rel):
        path = os.path.join(root, rel)
        if not os.path.lexists(path):
            return None
        try:
            return read(path)
        except OSError as exc:
            bad.append((rel, "cannot be read: %s" % (exc.strerror or exc)))
            return None

    def json_object(rel, data):
        try:
            doc = json.loads(data.decode("utf-8"))
        except (ValueError, RecursionError) as exc:  # UnicodeDecodeError is a ValueError
            bad.append((rel, "is not valid JSON (%s)" % (type(exc).__name__ if isinstance(exc, RecursionError) else exc)))
            return None
        if not isinstance(doc, dict):
            bad.append((rel, "is not a JSON object"))
            return None
        return doc

    for rel in (STATE_FILE, ".ai/policies/dialog.json", ".ai/policies/memory.json", ".claude/settings.json"):
        data = raw_of(rel)
        if data is not None:
            json_object(rel, data)
    data = raw_of(WEIGHT_PROJECT)
    if data is not None:
        doc = json_object(WEIGHT_PROJECT, data)
        if doc is not None and doc.get("version") != 1:
            bad.append((WEIGHT_PROJECT, "has no \"version\": 1"))
        elif doc is not None:
            try:
                weight_overlay().load(shipped_weight(), os.path.join(root, WEIGHT_PROJECT))
            except ValueError as exc:
                bad.append((WEIGHT_PROJECT, str(exc).split(": ", 1)[-1]))
    data = raw_of(VERIFICATION_MD)
    if data is not None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            bad.append((VERIFICATION_MD, "is not UTF-8 text"))
    data = raw_of(".codex/config.toml")
    if data is not None and tomllib is not None:
        try:
            tomllib.loads(data.decode("utf-8"))
        except ValueError as exc:  # TOMLDecodeError and UnicodeDecodeError
            bad.append((".codex/config.toml", "is not valid TOML (%s)" % exc))
    # the old weight.json is read once, by the split, so it must parse then
    if not os.path.lexists(os.path.join(root, WEIGHT_PROJECT)):
        data = raw_of(WEIGHT_JSON)
        if data is not None:
            json_object(WEIGHT_JSON, data)
    old_shapes(root, bad)
    return bad


def old_shapes(root, bad):
    """The four literal detectors of an older riskrails' files (D4)."""
    exists = lambda rel: os.path.lexists(os.path.join(root, rel))  # noqa: E731
    if exists(".ai/state/current.json") and not exists(STATE_FILE):
        bad.append((".ai/state/current.json", "is the task state of a riskrails before 3.4b (there is no state.json)"))
    if exists(".ai/policies/risk-tiers.json") and not exists(WEIGHT_JSON) and not exists(WEIGHT_PROJECT):
        bad.append((".ai/policies/risk-tiers.json", "is the risk-tier policy of a riskrails before 2.2 (there is no weight table)"))
    names = set(render_instructions.RULE_FILE.values()) | {e[0] for e in INSTRUCTION_FILE.values()}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in RULES_SKIP
                             and not os.path.lexists(os.path.join(dirpath, d, ".git")))
        for name in filenames:
            rel = os.path.relpath(os.path.join(dirpath, name), root).replace(os.sep, "/")
            if name not in names and rel not in names:
                continue
            try:
                data = read(os.path.join(root, rel))
            except OSError:
                continue  # an unreadable instruction file is the plan's to report, not an old shape
            found = next((m for m in OLD_MARKERS if m in data), None)
            if found:
                bad.append((rel, "carries %s of a riskrails before 3.4b" % found.decode()))


def kept_refusal(bad):
    """I3, verbatim: one line per failing file, then the rest."""
    for rel, why in bad:
        print("KEPT_UNREADABLE: %s: %s" % (rel, why))
    print("project-update: nothing was deleted or written. This version regenerates its own files and no longer "
          "converts older ones.")
    print("Install riskrails@%s (npx riskrails@%s), run /rr-setup --update with it, then install this version "
          "and run /rr-setup --update again." % (LAST_MIGRATING_VERSION, LAST_MIGRATING_VERSION))
    return EXIT_KEPT_UNREADABLE


# ---------------------------------------------------------------- planning
class Plan:
    def __init__(self, root):
        self.root = root
        self.items = []   # dicts: action, target, note, content, reason, keep, expect
        self.hints = []
        self.confirm_delete = None  # the human who confirmed this run's gated rows
        self.confirm_via = None  # why that gate passed: "terminal" or "unattended"
        self.confirm_cleanup = None  # the human who confirmed this run's [cleanup] deletions
        self.cleanup_via = None
        self.version_from = None  # the .ai/VERSION this run started from
        self.final = {}   # target -> bytes after this run (for cross-file fixes)
        self.removed = set()  # targets this run takes away
        self.seen = {}    # target -> sha of what was on disk when it was first read,
        #                   or None when nothing was there: apply's precondition
        self.git_kept = set()  # [cleanup] targets git holds or should hold: a hint and an original/ copy
        self.report_dir = ".ai/reports/project-update-%s" % datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # The project as this run leaves it: planned content first, then the disk.
    # File readers in the planning path go through these, not the disk.
    def exists(self, target):
        if target in self.final:
            return True
        return target not in self.removed and os.path.exists(os.path.join(self.root, target))

    def read(self, target):
        if target in self.final:
            return self.final[target]
        if not self.exists(target):
            return None
        data = read(os.path.join(self.root, target))
        self.seen.setdefault(target, sha(data))  # what apply must find there
        return data

    def remove(self, target):
        self.final.pop(target, None)
        self.removed.add(target)

    def before(self, target):
        """The sha of the target as this run first read it, None when it was
        absent. Recorded by the read that planned the change, so the precondition
        and the planning input are the same bytes."""
        if target not in self.seen:
            path = os.path.join(self.root, target)
            self.seen[target] = sha(read(path)) if os.path.isfile(path) and not os.path.islink(path) else None
        return self.seen[target]

    def add(self, action, target, note="", content=None, reason=None, keep=False):
        self.items.append(dict(action=action, target=target, note=note, content=content,
                               reason=reason, keep=keep, expect=self.before(target)))
        if content is not None:
            self.final[target] = content
            self.removed.discard(target)  # planned content wins over an earlier removal

    def original_of(self, target):
        return "%s/original/%s" % (self.report_dir, target)

    def gated(self, action, target, note, content=None, reason=None):
        """A change that waits for a human: `regenerate?` / `delete?` until
        --apply --confirm-delete NAME, then `regenerate` / `delete` with the original kept
        under original/ (R7)."""
        if self.confirm_delete:
            self.add(action, target, note, content=content, reason=reason, keep=True)
            if action == "delete":
                self.remove(target)
        else:
            self.add(action + "?", target, note, reason=reason)


# ---------------------------------------------------------------- regenerate
def lost_lines(ours, theirs):
    """The lines of the project's copy that the plugin's version does not have."""
    kept = set(theirs.decode("utf-8", "replace").splitlines())
    return [line.strip() for line in ours.decode("utf-8", "replace").splitlines()
            if line.strip() and line not in kept]


def patterns_of(data):
    """The count of non-empty deny and allow patterns in a path-guard.json, or None when it is not one."""
    try:
        doc = json.loads(data)
        return sum(1 for key in ("deny_patterns", "allow_patterns") for p in doc.get(key) or []
                   if isinstance(p, str) and p.strip())
    except (ValueError, AttributeError, TypeError, RecursionError):
        return None


def edited_note(plan, target, ours, theirs):
    """What a gated regenerate would lose, and where the original goes (R6)."""
    lost = lost_lines(ours, theirs)
    shown = "; ".join("`%s`" % (line[:48] + ("…" if len(line) > 48 else "")) for line in lost[:3])
    note = "edited here: %d line(s) of yours are not in the plugin's version%s" % (len(lost), " (" + shown + ")" if shown else "")
    if target.endswith("path-guard.json"):
        count = patterns_of(ours)
        note += "; drops %s deny/allow pattern(s)" % ("an unreadable number of" if count is None else count)
    return "%s; original kept at %s" % (note, plan.original_of(target))


def regenerate(plan, history, key, target, theirs):
    """D5: absent -> create; equal -> nothing; a version the plugin once shipped -> regenerate;
    anything else is the human's edit -> regenerate? behind the gate."""
    ours = plan.read(target)
    if ours is None:
        plan.add("create", target, content=theirs)
    elif ours == theirs:
        return
    elif history.shipped(key, ours):
        plan.add("regenerate", target, "unchanged since it was installed", content=theirs)
    else:
        plan.gated("regenerate", target, edited_note(plan, target, ours, theirs), content=theirs)


def effective_weight(plan):
    """The weight table as this run leaves it: the plugin's with weight.project.json laid over it."""
    own = plan.read(WEIGHT_PROJECT)
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "weight.project.json")
        if own is not None:
            with open(path, "wb") as fh:
                fh.write(own)
        return weight_overlay().load(shipped_weight(), path)


GENERATED_HEADER = b"generated by `state.py weight --mirror`"


def weight_md(plan, history):
    """weight.md is always rendered from the shipped table and the overlay (spec :161). A file that is
    a rendering or a shipped version is replaced; one a human wrote is gated."""
    try:
        theirs = weight_module().mirror(effective_weight(plan)).encode("utf-8")
    except (ValueError, OSError, KeyError, TypeError, AttributeError, RecursionError) as exc:
        plan.hints.append("%s: not rendered (%s: %s); fix %s, then run this again"
                          % (WEIGHT_MD, type(exc).__name__, exc, WEIGHT_PROJECT))
        return
    ours = plan.read(WEIGHT_MD)
    if ours is None:
        plan.add("create", WEIGHT_MD, "rendered from the weight table", content=theirs)
    elif ours == theirs:
        return
    elif GENERATED_HEADER in ours[:600] or history.shipped("ai-init/" + WEIGHT_MD, ours):
        plan.add("regenerate", WEIGHT_MD, "rendered from the weight table", content=theirs)
    else:
        plan.gated("regenerate", WEIGHT_MD, edited_note(plan, WEIGHT_MD, ours, theirs), content=theirs)


def block_update(plan, history, runtime):
    """R15, D5: the managed block of one instruction file. Rewritten between its markers; no block
    -> appended; no file -> a minimal one with the block. Text outside the markers is never touched."""
    name, block_tpl, minimal_tpl = INSTRUCTION_FILE[runtime]
    tpl = read(os.path.join(TEMPLATES["ai-init"], block_tpl))
    text = plan.read(name)
    if text is None:
        created = read(os.path.join(TEMPLATES["ai-init"], minimal_tpl)).replace(
            b"{{PROJECT}}", os.path.basename(plan.root).encode())
        plan.add("create", name, "with the managed block", content=created.rstrip(b"\n") + b"\n\n" + tpl)
        return
    found = find_block(text)
    if found is None:
        plan.add("regenerate", name, "managed block appended", content=text.rstrip(b"\n") + b"\n\n" + tpl)
        return
    s, e = found[0], found[1]
    ours = text[s:e] + b"\n"
    if ours == tpl:
        return
    content = text[:s] + tpl.rstrip(b"\n") + text[e:]
    if history.shipped("ai-init/" + block_tpl, ours):
        plan.add("regenerate", name, "managed block replaced (unchanged since it was installed)", content=content)
    else:
        plan.gated("regenerate", name, "managed block " + edited_note(plan, name, ours, tpl), content=content)


# ---------------------------------------------------------------- the one-time split
FIELD_LINE = re.compile(r"(?:%s):" % "|".join(
    ("verify_command", "step_test_command", "e2e_command", "lint_command", "typecheck_command",
     "single_test", "doc_tests", "bite_codes", "healthy_output", "runtime")))
SPECIFICS_RE = re.compile(r"(?m)^## Project specifics[ \t]*$")


def split_testing(testing, template):
    """R11: verification.md from testing.md. The field lines are copied verbatim with their continuation
    lines (indented, after a field line), then `## Project specifics` to the end of the file."""
    lines = testing.decode("utf-8").splitlines(keepends=True)
    fields, taking = [], False
    for line in lines:
        if FIELD_LINE.match(line):
            fields.append(line)
            taking = True
        elif taking and line[:1] in (" ", "\t") and line.strip():
            fields.append(line)
        else:
            taking = False
    text = template.decode("utf-8")
    if not fields:
        return template, 0
    head = text[:re.search(r"(?m)^verify_command:", text).start()]
    tail = SPECIFICS_RE.search(testing.decode("utf-8"))
    specifics = testing.decode("utf-8")[tail.start():] if tail else text[SPECIFICS_RE.search(text).start():]
    body = "".join(fields)
    return (head + body + ("" if body.endswith("\n") else "\n") + "\n" + specifics).encode("utf-8"), len(fields)


def leaves(value, prefix=()):
    """{path tuple: leaf} — objects are walked, a list or scalar (or an empty object) is one leaf."""
    if isinstance(value, dict) and value:
        out = {}
        for k, v in value.items():
            out.update(leaves(v, prefix + (k,)))
        return out
    return {prefix: value}


def split_weight(old, history, template):
    """R11: weight.project.json from the old weight.json: the leaves that differ from that leaf in every
    version the plugin shipped (lists whole). -> (bytes, carried paths, uncarried paths that differ from today's table)."""
    mine = json.loads(old.decode("utf-8"), object_pairs_hook=OrderedDict)
    tables = []
    for blob in history.versions("ai-init/" + WEIGHT_JSON) + [read(shipped_weight())]:
        try:
            tables.append(leaves(json.loads(blob.decode("utf-8"))))
        except (ValueError, RecursionError):
            continue
    today = tables[-1] if tables else {}
    carried, uncarried = OrderedDict(), []
    for path, value in leaves(mine).items():
        if path[:1] in (("version",), ("_comment",)) or not path:
            continue
        if any(path in t and t[path] == value for t in tables):
            if today.get(path, ...) != value:
                uncarried.append(".".join(map(str, path)))
            continue
        here = carried
        for part in path[:-1]:
            here = here.setdefault(part, OrderedDict())
        here[path[-1]] = value
    doc = json.loads(template.decode("utf-8"), object_pairs_hook=OrderedDict)
    doc.update(carried)
    paths = [".".join(map(str, p)) for p in leaves(carried) if p]
    return dump_json(doc), paths, uncarried


def listed(names, limit=6):
    shown = ", ".join(names[:limit])
    return shown + (" and %d more" % (len(names) - limit) if len(names) > limit else "")


def unwritten(plan, history, target, template):
    """True when the new file is absent, or is still a shipped template (today's or any in the history index):
    a scaffold run over an old tree can leave one, and it carries nothing of the project."""
    if not plan.exists(target):
        return True
    data = plan.read(target)
    return data is not None and (data.replace(b"\r\n", b"\n") == template.replace(b"\r\n", b"\n")
                                 or history.shipped("ai-init/" + target, data))


def split_once(plan, history):
    """R11: when verification.md / weight.project.json are absent (or only a shipped template), make them from
    testing.md / weight.json (once); with a project's own file present the old file is not read again.
    The old weight.json is then REMOVED, gated."""
    tpl = TEMPLATES["ai-init"]
    template = read(os.path.join(tpl, VERIFICATION_MD))
    if unwritten(plan, history, VERIFICATION_MD, template):
        absent = not plan.exists(VERIFICATION_MD)
        testing = plan.read(TESTING_MD)
        content, count = split_testing(testing, template) if testing is not None else (template, 0)
        if count:
            plan.add("split", VERIFICATION_MD, "%d command line(s) of testing.md copied verbatim, with its "
                     "Project specifics" % count, content=content)
        elif absent:
            plan.add("create", VERIFICATION_MD, content=content)
    template = read(os.path.join(tpl, WEIGHT_PROJECT))
    if unwritten(plan, history, WEIGHT_PROJECT, template):
        absent = not plan.exists(WEIGHT_PROJECT)
        old = plan.read(WEIGHT_JSON)
        if old is None:
            if absent:
                plan.add("create", WEIGHT_PROJECT, content=template)
        else:
            content, carried, uncarried = split_weight(old, history, template)
            if absent or content != plan.read(WEIGHT_PROJECT):
                note = "%d leaf/leaves of weight.json that differ from the plugin's table carried (%s)" % (
                    len(carried), listed(carried) or "none")
                if uncarried:
                    note += "; %d not carried, equal to an older shipped value: %s" % (len(uncarried), listed(uncarried))
                plan.add("split", WEIGHT_PROJECT, note, content=content)
    if plan.exists(WEIGHT_JSON):
        why = "[split] superseded by %s; the plugin's table is read from the plugin" % WEIGHT_PROJECT
        plan.gated("delete", WEIGHT_JSON, why, reason=why)


# ---------------------------------------------------------------- shared files, rules, caches
def require_shared(paths, runtimes):
    """Refuse, before anything is written, to drop a project copy whose shared fallback is missing:
    in this plugin's tree, or in another installed home of a runtime the project declares. A home
    this machine does not have is not checked."""
    undeclared = sorted(p for p in paths if p not in SHARED_SET)
    if undeclared:
        raise SchemaError("not in the shared set, never deleted as a shared copy: %s" % ", ".join(undeclared))
    rels = sorted(p[len(".ai/"):] for p in paths)
    missing = [r for r in rels if not os.path.isfile(os.path.join(SHARED, r))]
    if missing:
        raise SchemaError("the plugin's shared tree %s lacks %d file(s) a project copy would fall back to: %s — "
                          "reinstall the plugin (install.sh), then run this again" % (SHARED, len(missing), ", ".join(missing)))
    homes = {"claude": os.path.join(os.path.expanduser("~"), ".claude"),
             "codex": os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")}
    mine = os.path.realpath(PLUGIN_HOME)
    for runtime in runtimes:
        home = homes.get(runtime)
        if (not home or os.path.realpath(home) == mine
                or not os.path.isdir(os.path.join(home, "skills", "project-update"))):
            continue
        tree = os.path.join(home, "riskrails", "ai")
        missing = [r for r in rels if not os.path.isfile(os.path.join(tree, r))]
        if missing:
            raise SchemaError("%s has this plugin installed for %s, but %d of the %d shared file(s) a project copy "
                              "would fall back to are missing from %s — run `install.sh --target %s` from this "
                              "build, then run this again" % (home, runtime, len(missing), len(rels), tree, runtime))


def shared_update(plan, history, runtimes):
    """R17: an unedited copy of a shared file is offered for deletion; an edited one is an
    override, kept, and named once (OQ8)."""
    edited, candidates = [], []
    extra = undeclared_shared()
    if extra:
        plan.hints.append("the shared tree %s holds %d file(s) outside the shared set, ignored — reinstall the "
                          "plugin (install.sh) if you did not put them there: %s" % (SHARED, len(extra), ", ".join(extra)))
    for path in sorted(shared_files()):
        data = plan.read(path)
        if data is None:
            continue
        why = unsafe_path(plan.root, path)
        if why:
            plan.hints.append("%s: %s, so this update never deletes it — check by hand whether it is still "
                              "needed" % (path, why))
        elif not history.shipped("ai-init/" + path, data):
            edited.append(path)
        else:
            candidates.append(path)
    if candidates:
        try:
            require_shared(candidates, runtimes)
        except SchemaError as exc:
            plan.hints.append("%s — the copies stay until then" % exc)
            candidates = []
    for path in candidates:
        why = "[shared] identical to a shipped version"
        plan.gated("delete", path, why, reason=why)
    if edited:
        plan.hints.append("%d file(s) override the plugin's shared copy and no longer receive its changes: %s — "
                          "diff each against %s/<path>; `ai-path <path>` shows which applies; delete one when it "
                          "adds nothing" % (len(edited), ", ".join(edited), SHARED))


def rule_sources(plan):
    """OQ1: a rule source is not kept. Each `.ai/rules/<slug>.md` is `delete?` behind the gate with its
    original copied; until it is confirmed the rule stays rendered."""
    rules = os.path.join(plan.root, RULES_DIR)
    for name in sorted(os.listdir(rules)) if os.path.isdir(rules) else []:
        rel = "%s/%s" % (RULES_DIR, name)
        if name.endswith(".md") and name != "README.md" and os.path.isfile(os.path.join(rules, name)) \
                and not unsafe_path(plan.root, rel):
            why = "[rules] rule sources are not kept by an update: the rendered blocks go with it"
            plan.gated("delete", rel, why, reason=why)


def local_cache(plan):
    """R18: .ai/local/plugin-update/ (the old merge's conflict copies) is removed; .ai/local/memory/ is never touched."""
    for here, _dirs, names in os.walk(os.path.join(plan.root, LOCAL_CACHE)):
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(here, name), plan.root).replace(os.sep, "/")
            if not unsafe_path(plan.root, rel):
                why = "[local] the old merge's cache, not written any more"
                plan.gated("delete", rel, why, reason=why)


def task_journal(root, task_id):
    """(finished, abandoned, last event as a datetime) from the task's journal,
    or None when it holds no readable event. A task is finished when its journal
    has task_closed or gate_approved, or when logs/<id>/state.json records a
    result (so a torn task_closed line does not make a closed task look unclosed)."""
    closed = abandoned = False
    last = None
    try:
        with open(os.path.join(root, ".ai", "reports", task_id, "events.jsonl"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
    except (OSError, UnicodeDecodeError):
        return None
    for line in lines:
        try:
            ev = json.loads(line)
            when = datetime.strptime(ev["ts"][:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except (ValueError, KeyError, TypeError, RecursionError):
            continue
        if last is None or when > last:
            last = when
        if ev.get("event") == "task_closed":
            closed = True
            data = ev.get("data")
            abandoned = (isinstance(data, dict) and data.get("abandoned") is True) or ev.get("detail") == "abandoned"
        elif ev.get("event") == "gate_approved":
            closed = True
    try:
        with open(os.path.join(root, ".ai", "state", "logs", task_id, "state.json"), encoding="utf-8") as fh:
            result = json.load(fh).get("result")
    except (OSError, ValueError, AttributeError, UnicodeDecodeError, RecursionError):
        result = None
    if isinstance(result, str) and result:
        closed = True
        abandoned = abandoned or result == "abandoned"
    return None if last is None else (closed, abandoned, last)


def cleanup_update(plan, now=None):
    """Old run logs and stale unclosed tasks, proposed for deletion and never
    deleted unasked (only with --confirm-cleanup). A closed task's `*.log` files
    go (its state.json stays); an abandoned task loses every file under
    .ai/reports/<id>/ and .ai/state/logs/<id>/ except that state.json; an unclosed
    one idle for STALE_DAYS loses every file in both. The task in flight is
    never touched. `now` is a datetime; RISKRAILS_NOW (ISO, Z) overrides it."""
    if now is None:
        try:
            now = datetime.strptime(env("NOW") or utc_now(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            print("project-update: RISKRAILS_NOW %r is not a UTC time like 2026-01-31T12:00:00Z" % env("NOW"),
                  file=sys.stderr)
            raise SystemExit(2) from None
    flight = None
    raw = plan.read(STATE_FILE)
    if raw is not None:
        try:
            flight = json.loads(raw).get("task_id")
        except (ValueError, AttributeError, RecursionError):
            return  # unreadable: a task may be in flight, so no task is proposed as stale
    reports =os.path.join(plan.root, ".ai", "reports")
    logs = os.path.join(plan.root, ".ai", "state", "logs")

    def files(base, rel, only_logs=False, keep=()):
        out = []
        for here, _dirs, names in os.walk(os.path.join(base, rel)):
            for n in names:
                full = os.path.join(here, n)
                if os.path.isfile(full) and not os.path.islink(full) and (not only_logs or n.endswith(".log")) \
                        and n not in keep:
                    out.append(os.path.relpath(full, plan.root).replace(os.sep, "/"))
        return out

    for task_id in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        journal = task_journal(plan.root, task_id)
        if journal is None or task_id == flight:
            continue
        closed, abandoned, last = journal
        if abandoned:
            why, targets = "[cleanup] abandoned task %s" % task_id, \
                files(reports, task_id) + files(logs, task_id, keep=("state.json",))
        elif not closed and now - last > timedelta(days=STALE_DAYS):
            why = "[cleanup] unclosed task %s, last event %s" % (task_id, last.strftime("%Y-%m-%d"))
            targets = files(reports, task_id) + files(logs, task_id)
        elif closed:
            why, targets = "[cleanup] log of closed task %s" % task_id, files(logs, task_id, only_logs=True)
        else:
            continue
        # .ai/reports/ is usually git-tracked; only .ai/state/ is git-ignored run state
        held = git_states(plan.root, ".ai/reports/" + task_id)
        skipped = set()
        for target in sorted(targets):
            unsafe = unsafe_path(plan.root, target)
            if unsafe:     # --apply would abort on it: say so instead of proposing it
                if unsafe not in skipped:
                    skipped.add(unsafe)
                    plan.hints.append("%s: not proposed for deletion, %s — remove it yourself if it should go"
                                      % (target, unsafe))
                continue
            note = why
            state = held(target) if target.startswith(".ai/reports/") else None
            if state == "tracked":
                note += "; tracked: git can restore a committed copy"
            elif state == "uncommitted":
                note += "; uncommitted: git holds no copy of it"
            elif state == "ignored":
                note += "; git-ignored: not recoverable through git"
            if state in ("tracked", "uncommitted"):
                plan.git_kept.add(target)
            if plan.confirm_cleanup:
                plan.add("delete", target, note, reason=why)
                plan.remove(target)
            else:
                plan.add("delete?", target, note, reason=why)


def deletion_hint(plan):
    """M4: git is the rollback of a deletion or an overwrite; it must hold .ai/ first.
    A [cleanup] deletion of git-ignored run state is not counted: git does not roll it back;
    one under .ai/reports/ that git tracks, or should, is."""
    if any(i["action"] in ("delete?", "delete", "regenerate?") and i["target"].startswith(".ai/")
           and (not (i.get("reason") or "").startswith("[cleanup]") or i["target"] in plan.git_kept)
           for i in plan.items) \
            and git_dirty_ai(plan.root):
        plan.hints.append("commit .ai/ first: git is this update's rollback "
                          "(`git status -- .ai` lists what it does not hold yet)")


TRACKED_IGNORED_SHOWN = 10  # per-file hints before tracked_ignored_hint counts the rest


def tracked_ignored_hint(plan):
    """A file under .ai/state that git tracks although an ignore rule lists it: the rule
    has no effect on it. Read-only: the human untracks it; nothing is planned.
    At most TRACKED_IGNORED_SHOWN files get their own hint; one more line counts the rest."""
    try:
        res = subprocess.run(["git", "-C", plan.root, "ls-files", "-z", "-ci", "--exclude-standard",
                              "--", ".ai/state"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return
    if res.returncode != 0:
        return
    # --literal-pathspecs: a * ? [ ] in a name is that name, not a pattern that matches its neighbours.
    all_cmd = "git ls-files -z -ci --exclude-standard -- .ai/state | xargs -0 -r git --literal-pathspecs rm --cached --"
    names = [os.fsdecode(raw) for raw in res.stdout.split(b"\0") if raw]
    for path in names[:TRACKED_IGNORED_SHOWN]:
        # A control character (or a byte that is not UTF-8, which fsdecode keeps as a lone
        # surrogate) in the name would forge a report line or break the copy-paste command:
        # show it escaped, and untrack by the NUL-safe listing.
        shown = "".join(c if c.isprintable() else repr(c)[1:-1] for c in path)
        if shown == path:
            plan.hints.append("%s: tracked by git but ignored by an ignore rule — the rule has no "
                              "effect on a tracked file, so every run leaves the tree dirty and "
                              "`git commit -a` sweeps it in; untrack it yourself, from the project root: "
                              "`git --literal-pathspecs rm --cached -- %s` and commit (the file stays on disk)"
                              % (shown, shlex.quote(path)))
        else:
            plan.hints.append("%s: tracked by git but ignored by an ignore rule — the rule has no "
                              "effect on a tracked file, so every run leaves the tree dirty and "
                              "`git commit -a` sweeps it in; this name cannot be typed safely, so "
                              "untrack it, from the project root, with `%s`, which untracks EVERY tracked, ignored file "
                              "under .ai/state, not only this one, and commit (the files stay on disk)"
                              % (shown, all_cmd))
    if len(names) > TRACKED_IGNORED_SHOWN:
        plan.hints.append(".ai/state: %d more file(s) tracked by git but ignored by an ignore rule, "
                          "not listed; untrack ALL tracked, ignored files under .ai/state "
                          "(the ones listed above too), from the project root, with `%s` and commit (the files stay on disk)"
                          % (len(names) - TRACKED_IGNORED_SHOWN, all_cmd))


def rendered_rules(plan):
    """Every (file, slug) in the project that carries a rule block today, plus
    every path-scoped copy under .claude/rules/. Walked rather than remembered:
    a manifest would be one more file to keep true, and the markers already say
    who wrote them."""
    blocks, docs = [], []
    names = set(render_instructions.RULE_FILE.values())
    for dirpath, dirnames, filenames in os.walk(plan.root):
        dirnames[:] = sorted(d for d in dirnames if d not in RULES_SKIP
                             and not os.path.lexists(os.path.join(dirpath, d, ".git")))
        rel_dir = os.path.relpath(dirpath, plan.root)
        for name in sorted(filenames):
            rel = name if rel_dir == "." else os.path.join(rel_dir, name)
            rel = rel.replace(os.sep, "/")
            if name in names:
                text = plan.read(rel)
                if text is None:
                    continue
                for slug in render_instructions.rule_slugs_in(text.decode("utf-8", "replace")):
                    blocks.append((rel, slug))
            elif rel.startswith(render_instructions.CLAUDE_RULES_DIR + "/") and name.endswith(".md"):
                text = plan.read(rel)
                if text is not None and render_instructions.RULE_GENERATED % name[:-3] in \
                        text.decode("utf-8", "replace"):
                    docs.append(rel)
    return blocks, docs


def nested_tree(root, rel_dir):
    """The first directory below the root on the way to `rel_dir`, `rel_dir`
    included, that holds a .git entry (a worktree, a nested repository, a
    submodule), or None. The same predicate rendered_rules() prunes on."""
    # "." and "" are the root itself (dirs: ["."] reaches here as ""), whose
    # own .git is not a nested tree.
    parts = [p for p in rel_dir.split("/") if p not in ("", ".")]
    for i in range(1, len(parts) + 1):
        candidate = "/".join(parts[:i])
        if os.path.lexists(os.path.join(root, candidate, ".git")):
            return candidate
    return None


def unwalked_dir(root, rel_dir):
    """Why the take-back walk (rendered_rules) never enters `rel_dir`, or None:
    a RULES_SKIP name on the way, or a symlinked directory on the way."""
    here = root
    for part in (p for p in rel_dir.split("/") if p not in ("", ".")):
        here = os.path.join(here, part)
        if part.casefold() in RULES_SKIP_FOLDED:
            return "%s is under a directory the take-back never walks (%s)" % (rel_dir, part)
        if os.path.islink(here):
            return "%s is a symlink, which the take-back never follows" % os.path.relpath(here, root).replace(os.sep, "/")
    return None


def _frozen_block(plan, target, slug):
    """True when `target` is a readable regular file inside the project, holding a
    block for `slug`, at a place the take-back walk (rendered_rules) never enters: a
    RULES_SKIP name or a nested git tree on its real path. A symlink that leads inside
    the walked part of the project is removed by the same run; one that leads outside
    the project, a directory, a FIFO or an unreadable file is not read at all."""
    full = os.path.join(plan.root, target)
    try:
        real = os.path.realpath(full)
        base = os.path.realpath(plan.root)
        if os.path.commonpath([real, base]) != base or not os.path.isfile(real):
            return False
        rel_dir = os.path.relpath(os.path.dirname(real), base).replace(os.sep, "/")
        parts = [p for p in rel_dir.split("/") if p not in ("", ".")]
        if not (any(p in RULES_SKIP for p in parts) or nested_tree(base, rel_dir) is not None):
            return False
        held = plan.read(target)
    except (OSError, ValueError):
        return False
    return held is not None and slug in render_instructions.rule_slugs_in(held.decode("utf-8", "replace"))


def rules_update(plan, runtimes):
    """Render `.ai/rules/<slug>.md` into the instruction file of every directory
    it names, and take back what a rule no longer asks for. The text around a
    block belongs to the project and is never read for meaning, only preserved.
    A rule whose source this run deletes is no longer rendered."""
    rules_path = os.path.join(plan.root, RULES_DIR)
    if not os.path.isdir(rules_path):
        return
    try:
        rules = [r for r in render_instructions.load_rules(rules_path)
                 if "%s/%s.md" % (RULES_DIR, r.slug) not in plan.removed]
    except render_instructions.RenderError as exc:
        plan.hints.append("%s — that rule is not rendered; the rest are" % exc)
        return
    wanted = render_instructions.rule_targets(rules, runtimes)
    managed = {(i["target"], i["slug"]) for i in wanted if i["kind"] == "block"}
    kept_docs = {i["target"] for i in wanted if i["kind"] == "doc"}

    for item in wanted:
        source = "%s/%s.md" % (RULES_DIR, item["slug"])
        target, content = item["target"], item["content"]
        tree = nested_tree(plan.root, os.path.dirname(target)) if item["kind"] == "block" else None
        if tree is not None:
            # Not this project's file, and the take-back never walks there: a
            # block written there could never be taken back again.
            plan.hints.append("%s: %s is a nested git tree (worktree, repository or submodule)"
                              " — rule %s is not rendered there" % (target, tree, item["slug"]))
            continue
        skip = unwalked_dir(plan.root, os.path.dirname(target)) if item["kind"] == "block" else None
        if skip is not None:
            hint = "%s: %s — rule %s is not rendered there" % (target, skip, item["slug"])
            if _frozen_block(plan, target, item["slug"]):
                hint += ("; an earlier rendering of it is still there, the take-back never walks there:"
                         " remove that block by hand")
            plan.hints.append(hint)
            continue
        current = plan.read(target)
        if item["kind"] == "doc":
            new = content.encode()
            if current is None:
                plan.add("create", target, "rendered from " + source, content=new)
            elif current != new:
                plan.add("regenerate", target, "rendered from " + source, content=new)
            continue
        text = "" if current is None else current.decode("utf-8")
        new = render_instructions.splice_rule(text, item["slug"], content).encode()
        if current is None:
            plan.add("create", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)
        elif current != new:
            plan.add("regenerate", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)

    blocks, docs = rendered_rules(plan)
    for target, slug in blocks:
        if (target, slug) in managed:
            continue
        text = plan.read(target).decode("utf-8")
        # The block is ours; the file is not. Take the block, leave the file.
        plan.add("regenerate", target, "rule block %s removed (%s/%s.md no longer renders here)"
                 % (slug, RULES_DIR, slug),
                 content=render_instructions.strip_rule(text, slug).encode())
    for target in docs:
        if target in kept_docs:
            continue
        # The whole file is a rendered copy, so taking it away is a deletion, and
        # a deletion waits for a human exactly as a migration's does.
        slug = os.path.basename(target)[:-3]
        why = "[rules] %s" % ("%s/%s.md no longer sets paths:" % (RULES_DIR, slug)
                              if slug in {r.slug for r in rules}
                              else "source %s/%s.md is gone" % (RULES_DIR, slug))
        if plan.confirm_delete:
            plan.add("delete", target, why, reason=why)
            plan.remove(target)
        else:
            plan.add("delete?", target, why, reason=why)


def gitignore_update(plan, snippet_path):
    snippet = read(snippet_path).decode().splitlines()
    current = plan.read(".gitignore") or b""
    have = set(current.decode().splitlines())
    missing = [l for l in snippet if l.strip() and not l.startswith("#") and l not in have]
    if not missing:
        return
    header = [l for l in snippet if l.startswith("#") and l not in have]
    add = "\n".join(header + missing) + "\n"
    sep = b"\n" if current and not current.endswith(b"\n") else b""
    new = current + sep + add.encode()
    # Replace an earlier .gitignore item from this run instead of stacking two.
    plan.items = [i for i in plan.items if i["target"] != ".gitignore"]
    plan.add("regenerate", ".gitignore", "entries appended: " + ", ".join(missing), content=new)


def budget_hints(plan, runtimes):
    """What the always-loaded block costs this project after this run.

    Downstream the budget is advisory (R4): the plugin measures its own block
    and says what it costs, but a project's own file is never refused. A block
    that is over budget and still the one the plugin installed is the plugin's
    to trim; an edited one is the project's."""
    try:
        cap = render_instructions.budgets(render_instructions.DEFAULT_SOURCE).get("project")
    except render_instructions.RenderError:
        return
    if not cap:
        return
    for rt in runtimes:
        name, block_tpl, _ = INSTRUCTION_FILE[rt]
        text = plan.read(name)
        if text is None:
            continue
        block = render_instructions.block_of(text.decode("utf-8", "replace"))
        if block is None:
            continue
        size = len(block.encode("utf-8"))
        if size <= cap:
            continue
        shipped = read(os.path.join(TEMPLATES["ai-init"], block_tpl)).rstrip(b"\n")
        whose = ("the plugin ships it that size — report it"
                 if block.encode("utf-8").rstrip() == shipped
                 else "it was edited here, so the plugin will not rewrite it: trimming it is yours")
        plan.hints.append("%s: the managed block is %d B, budget %d B — %s"
                          % (name, size, cap, whose))


def constitution_hint(plan):
    """R10: the cap is hard for the shipped template and advisory for a project.
    The rule lives in render_instructions; this only relays what it says."""
    rel = "docs/sdlc/constitution.md"
    path = os.path.join(plan.root, rel)
    if not os.path.isfile(path):
        return
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        render_instructions.constitution(path, out=io.StringIO())
    for line in err.getvalue().splitlines():
        plan.hints.append(line.replace(path, rel))


def verification_hints(plan):
    """R10: update's empty-field hints read verification.md."""
    text = plan.read(VERIFICATION_MD)
    if text is None:
        return
    for field, why in (
        ("verify_command", "the feedback loop needs it"),
        ("step_test_command", "a step runs only its own tests"),
        ("e2e_command", "e2e runs once at the end of a task; write 'none' if there is no suite"),
        ("lint_command", "a sensor reads it; read the project's config files for it, and write 'none' if there is none"),
        ("typecheck_command", "a sensor reads it; read the project's config files for it, and write 'none' if there is none"),
    ):
        if re.search(rb"(?m)^" + field.encode() + rb":[ \t]*(#.*)?$", text):
            plan.hints.append("%s: %s is empty — %s" % (VERIFICATION_MD, field, why))
        elif not re.search(rb"(?m)^" + field.encode() + rb":", text):
            plan.hints.append("%s: %s is missing — %s" % (VERIFICATION_MD, field, why))


PHASE = {"split": 0, "delete": 2, "delete?": 2}


def build_plan(root, confirm_delete=None, confirm_via=None, confirm_cleanup=None, cleanup_via=None):
    """D3: split_once -> regenerate -> shared -> block per runtime -> rules -> local -> gitignore, cleanup, hints.
    The caller has run check_kept: nothing here reads a kept file for meaning."""
    plan = Plan(root)
    plan.confirm_cleanup = confirm_cleanup
    plan.cleanup_via = cleanup_via
    plan.confirm_delete = confirm_delete
    plan.confirm_via = confirm_via
    has_ai = os.path.isdir(os.path.join(root, ".ai"))
    has_sdlc = os.path.isdir(os.path.join(root, "docs", "sdlc"))
    if not (has_ai or has_sdlc):
        return None
    history = History(HISTORY)
    runtimes = project_runtimes(root)
    plan.version_from = project_version(root) if has_ai else None

    if has_sdlc:
        tpl = TEMPLATES["project-init"]
        for src, target in SDLC_CREATE:  # the project's own from then on
            if not plan.exists(target):
                plan.add("create", target, content=read(os.path.join(tpl, src)).replace(
                    b"{{PROJECT}}", os.path.basename(root).encode()))
        for rt in runtimes:
            for src, target, kind in RUNTIME_MAP[rt]:
                content = read(os.path.join(tpl, src))
                if kind == "create":
                    if not plan.exists(target):
                        plan.add("create", target, content=content)
                else:
                    regenerate(plan, history, "project-init/" + src, target, content)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

    if has_ai:
        tpl = TEMPLATES["ai-init"]
        split_once(plan, history)
        files = []
        for dirpath, _, names in os.walk(os.path.join(tpl, ".ai")):
            for n in names:
                files.append(os.path.relpath(os.path.join(dirpath, n), tpl).replace(os.sep, "/"))
        for rel in sorted(files):
            if rel in NOT_COPIED or rel in (VERIFICATION_MD, WEIGHT_PROJECT):
                continue
            content = read(os.path.join(tpl, rel))
            if rel in CREATE_ONLY or rel.startswith(CREATE_ONLY_DIRS):
                if not plan.exists(rel):
                    plan.add("create", rel, content=content)
            else:
                regenerate(plan, history, "ai-init/" + rel, rel, content)
        weight_md(plan, history)
        shared_update(plan, history, runtimes)
        rule_sources(plan)
        local_cache(plan)
        cleanup_update(plan)
        for rt in runtimes:
            block_update(plan, history, rt)
        rules_update(plan, runtimes)
        deletion_hint(plan)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))
        tracked_ignored_hint(plan)
        verification_hints(plan)
        budget_hints(plan, runtimes)
        if plan.items and plan.exists(STATE_FILE):
            plan.hints.append("%s: a task is in flight while files are regenerated — check that the files "
                              "its current step may touch still exist afterwards" % STATE_FILE)
        # Last of the items: an apply that stops short leaves the version alone, and the next run plans the rest again.
        ours = template_version()
        if plan.version_from != ours:
            plan.add("regenerate" if plan.exists(VERSION_FILE) else "create", VERSION_FILE,
                     "schema %d" % ours, content=b"%d\n" % ours)
    if has_sdlc:
        constitution_hint(plan)
    plan.items.sort(key=lambda i: 3 if i["target"] == VERSION_FILE else PHASE.get(i["action"], 1))
    return plan


# ---------------------------------------------------------------- output
class Abort(Exception):
    """A precondition failed: the project is not what the dry run described."""

    def __init__(self, item, why):
        super().__init__(why)
        self.item, self.why = item, why


def current_sha(root, target):
    """The sha of a target now, or None when it is absent. A path that is not a
    regular file has no content this tool may replace."""
    path = os.path.join(root, target)
    if os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):
        raise Abort(None, "%s is not a regular file" % target)
    return sha(read(path)) if os.path.isfile(path) else None


def check(plan, item, target, expect, written):
    """The target must still be what the dry run read, or what this run wrote."""
    try:
        now_sha = current_sha(plan.root, target)
    except Abort as exc:
        raise Abort(item, exc.why) from exc
    want = written.get(target, expect)
    if now_sha != want:
        raise Abort(item, "%s changed since the dry run read it" % target)


def default_mode():
    mask = os.umask(0)
    os.umask(mask)
    return 0o666 & ~mask


def write_file(root, target, content, mode=None):
    """Atomic, like state.py: a crash leaves the old file or the new one, never
    half of one. The temp file is created with mkstemp in the target's directory,
    so a planted name cannot redirect the write, and a symlinked target is
    refused rather than followed. The target keeps the mode it had. A symlinked
    *directory* on the way to it is still followed, as every writer here always
    has."""
    path = os.path.join(root, target)
    if os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):
        raise Abort(None, "%s is not a regular file" % target)
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    if mode is None:
        mode = os.stat(path).st_mode & 0o7777 if os.path.isfile(path) else default_mode()
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def keep_original(plan, target):
    """A faithful copy of what a move or a delete takes away, mode included.
    Nothing else is ever lost, so nothing else is copied."""
    path = os.path.join(plan.root, target)
    write_file(plan.root, os.path.join(plan.report_dir, "original", target),
               read(path), mode=os.stat(path).st_mode & 0o7777)



def record_run(plan, ops, deletions):
    """The record of what was taken away or overwritten, rewritten after every such operation:
    an abort must not lose the note of a change a human approved. A second run on the same
    day appends to the record instead of replacing it."""
    path = os.path.join(plan.report_dir, "migration.json")
    existing = {}
    full = os.path.join(plan.root, path)
    if os.path.isfile(full):
        try:
            existing = json.loads(read(full), object_pairs_hook=OrderedDict)
        except (ValueError, RecursionError):  # too deep reads as malformed
            existing = {}
        if not isinstance(existing, dict):  # hand-edited into another shape
            existing = {}
    record = OrderedDict()
    record["from"] = existing.get("from", plan.version_from)
    # The version the project is actually at now, read from the disk: this record is
    # written before the files change, and an aborted run never reaches the template's.
    version_path = os.path.join(plan.root, VERSION_FILE)
    on_disk = read(version_path).decode().strip() if os.path.isfile(version_path) else ""
    record["to"] = int(on_disk) if on_disk.isdigit() else record["from"]
    record["applied_at"] = utc_now()
    # A recovery re-run replays the same operation: record it once.
    record["ops"] = list(existing.get("ops", []))
    record["ops"] += [o for o in ops if o not in record["ops"]]
    record["deletions"] = list(existing.get("deletions", []))
    record["deletions"] += [d for d in deletions
                            if not any(e.get("path") == d["path"] for e in record["deletions"])]
    if existing and all(existing.get(k) == record[k] for k in ("from", "to", "ops", "deletions")):
        return  # a run that changed nothing leaves the record as it was
    write_file(plan.root, path, dump_json(record))


def apply(plan):
    """Write the plan, in order. Every item checks its target first; a violation
    or a failed write aborts before the next item, leaving everything after it
    unwritten. Every operation is idempotent, so the re-run is the recovery."""
    written, recorded = {}, []
    for item in plan.items:
        try:
            apply_item(plan, item, written, recorded)
        except Abort as exc:
            raise Abort(exc.item or item, exc.why) from exc
        except OSError as exc:
            raise Abort(item, str(exc)) from exc
    # The run finished: say which version it actually reached.
    try:
        if recorded or os.path.isfile(os.path.join(plan.root, plan.report_dir, "migration.json")):
            record_run(plan, [], [])
    except OSError as exc:
        raise Abort(None, str(exc)) from exc


def apply_item(plan, item, written, recorded):
    target, action = item["target"], item["action"]
    reason = item.get("reason") or ""
    cleanup = reason.startswith("[cleanup]")
    if action in ("delete?", "regenerate?"):  # listed only, until a human confirms it
        return
    by = dict(confirmed_by=plan.confirm_cleanup if cleanup else plan.confirm_delete,
              via=plan.cleanup_via if cleanup else plan.confirm_via, at=utc_now())
    if action == "delete":
        # the plan-time symlink check is repeated: a path swapped since is refused
        why = unsafe_path(plan.root, target)
        if why:
            raise Abort(item, why)
        check(plan, item, target, item["expect"], written)
        # git-ignored task state: a [cleanup] deletion of it is NOT recoverable through git, and
        # copying what it removes would defeat the cleanup, so no original/ copy is kept. A report
        # file git tracks, or should, is kept like any other deletion.
        if not target.startswith(".ai/state/") and (not cleanup or target in plan.git_kept):
            keep_original(plan, target)
        recorded.append(target)
        # Recorded before the file is gone: an abort later must not lose the note
        # of what was taken away, or of who approved it.
        record_run(plan, [dict(action=action, path=target)], [dict(path=target, **by)])
        os.remove(os.path.join(plan.root, target))
        written[target] = None
        if reason.startswith(("[cleanup]", "[local]")):
            prune_empty(plan.root, target)
        return
    check(plan, item, target, item["expect"], written)
    if item["keep"] and item["expect"] is not None and target not in written:
        # A change a human confirmed overwrites what they wrote: keep it, so it can be read back.
        if not os.path.exists(os.path.join(plan.root, plan.original_of(target))):
            keep_original(plan, target)
        recorded.append(target)
        record_run(plan, [dict(action=action, path=target, **by)], [])
    write_file(plan.root, target, item["content"])
    written[target] = sha(item["content"])


def prune_empty(root, target):
    """The directories a cleanup or cache deletion left empty, up to (not including)
    .ai/reports, .ai/state/logs and .ai/local; a directory with anything in it stays."""
    top = ".ai/state/logs" if target.startswith(".ai/state/logs/") else \
        ".ai/local" if target.startswith(LOCAL_CACHE + "/") else ".ai/reports"
    here = os.path.dirname(target)
    while here.startswith(top + "/"):
        try:
            os.rmdir(os.path.join(root, here))
        except OSError:
            return
        here = os.path.dirname(here)


def report(plan, applied):
    auto = [i for i in plan.items if i["action"] not in ("delete?", "regenerate?")]
    gated = [i for i in plan.items if i["action"] in ("delete?", "regenerate?")]
    head = "applied" if applied else "dry run, nothing written; --apply to write"
    print("project-update: %s (%s)" % (plan.root, head))
    if not plan.items:
        print("  up to date with the installed plugin")
    # a cleanup is one line per directory, however many files it holds
    rows, groups = [], {}
    for i in plan.items:
        if (i["reason"] or "").startswith("[cleanup]"):
            parts = i["target"].split("/")
            where = "/".join(parts[:4] if i["target"].startswith(".ai/state/logs/") else parts[:3])
            key = (where, i["action"], i["note"])
            if key in groups:
                groups[key]["count"] += 1
                continue
            row = dict(i, count=1)
            groups[key] = row
            row["target"] = where
            i = row
        rows.append(i)
    for (where, _action, _note), row in groups.items():
        row["target"] = "%s/ (%d file%s)" % (where, row["count"], "" if row["count"] == 1 else "s")
    width = max([len(i["target"]) for i in rows] + [10])
    for i in rows:
        note = i["note"]
        if i["action"] in ("delete?", "regenerate?"):
            if (i["reason"] or "").startswith("[cleanup]"):
                note += "; needs --apply --confirm-cleanup NAME"
                if i["target"].startswith(".ai/state/"):
                    note += " (git-ignored: not recoverable through git)"
            else:
                note += "; needs --apply --confirm-delete NAME"
        print("  %-9s %-*s  %s" % (i["action"], width, i["target"], note))
    for h in plan.hints:
        print("  hint      " + h)
    tail = ""
    # the summary names the flag each row names: [cleanup] rows settle with --confirm-cleanup only
    cleanups = [i for i in gated if (i["reason"] or "").startswith("[cleanup]")]
    if len(gated) > len(cleanups):
        tail += ", %d change(s) awaiting --confirm-delete" % (len(gated) - len(cleanups))
    if cleanups:
        tail += ", %d cleanup file(s) awaiting --confirm-cleanup" % len(cleanups)
    print("%d automatic%s" % (len(auto), tail))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--budget", action="store_true",
                    help="with --check: exit 1 when a root instruction file is over its byte budget")
    ap.add_argument("--confirm-delete", metavar="NAME",
                    help="a human confirms this run's gated rows (regenerate?, delete?), and is recorded in "
                         "the migration report; only with --apply")
    ap.add_argument("--confirm-cleanup", metavar="NAME",
                    help="a human confirms this run's [cleanup] deletions (run logs and stale task files, "
                         "git-ignored and not recoverable through git); only with --apply. "
                         "--confirm-delete does not settle them")
    args = ap.parse_args()
    confirm_via = cleanup_via = None
    for flag, name in (("--confirm-delete", args.confirm_delete), ("--confirm-cleanup", args.confirm_cleanup)):
        if name is None:
            continue
        if not args.apply:
            ap.error("%s only makes sense with --apply" % flag)
        if not name.strip():
            ap.error("%s needs the name of the human who confirmed the change" % flag)
        if placeholder_name(name):
            ap.error("%s got the placeholder %r; type your own name, it is the audit trail"
                     % (flag, name.strip()))
        passed, via, why = human_gate()
        if not passed:
            # Under an agent-session marker the AI_UNATTENDED route is the launcher's
            # to declare, not the agent's to type: the hint names it only otherwise.
            hint = "run the same command yourself in a terminal outside Claude Code or Codex"
            if "agent session" not in why:
                hint += ", or set AI_UNATTENDED=1 if a launcher runs it unattended on your behalf"
            return refuse("%s is typed by a human, and %s" % (flag, why), hint)
        if flag == "--confirm-delete":
            confirm_via = via
        else:
            cleanup_via = via
    if args.budget and not args.check:
        ap.error("--budget only makes sense with --check")
    root = os.path.abspath(args.root)
    if args.check and args.budget:
        offenders = budget_offenders(
            root, [INSTRUCTION_FILE[rt][0] for rt in project_runtimes(root)],
            render_instructions.budgets(render_instructions.DEFAULT_SOURCE), render_instructions.block_of)
        for line in offenders:
            print(line)
        return 1 if offenders else 0
    for name, tpl in TEMPLATES.items():
        if not os.path.isdir(tpl):
            print("project-update: %s templates not found at %s (run riskrails/install.sh)" % (name, tpl), file=sys.stderr)
            return 2
    if not (os.path.isdir(os.path.join(root, ".ai")) or os.path.isdir(os.path.join(root, "docs", "sdlc"))):
        print("project-update: %s has neither .ai/ nor docs/sdlc/ — run /rr-setup first" % root, file=sys.stderr)
        return 2
    try:
        if os.path.isdir(os.path.join(root, ".ai")):
            project_version(root)
        bad = check_kept(root)
        if bad:
            return kept_refusal(bad)
        plan = build_plan(root, confirm_delete=args.confirm_delete, confirm_via=confirm_via,
                          confirm_cleanup=args.confirm_cleanup, cleanup_via=cleanup_via)
    except SchemaError as exc:
        # --check is read by /rr-status, which reads stdout: it must see the reason.
        print("project-update: %s" % exc, file=sys.stdout if args.check else sys.stderr)
        return 2
    if args.check:
        pending = [i for i in plan.items if not i["action"].endswith("?")]
        waiting = [i for i in plan.items if i["action"].endswith("?") and not (i["reason"] or "").startswith("[cleanup]")]
        if pending:
            bits = ["%d file(s) to update" % len(pending)]
            if waiting:
                bits.append("%d change(s) a human must confirm" % len(waiting))
            print("project is behind the installed plugin: %s — run /rr-setup --update" % ", ".join(bits))
            return 1
        print("project matches the installed plugin"
              + (" (%d change(s) wait for --confirm-delete)" % len(waiting) if waiting else ""))
        return 0
    if args.apply:
        try:
            apply(plan)
        except Abort as exc:
            where = "%s %s" % (exc.item["action"], exc.item["target"]) if exc.item else "the update"
            print("project-update: aborted at %s: %s — nothing after it was written; "
                  "run the dry run again" % (where, exc.why), file=sys.stderr)
            return 3
    report(plan, args.apply)
    return 0


if __name__ == "__main__":
    sys.exit(main())
