#!/usr/bin/env python3
"""Bring a project's claude-agentic files up to date with the installed plugin.

  update.py [project-dir] [--apply] [--check]

Default is a dry run: print what would change, write nothing.
  --apply   write the changes
  --check   print one line and exit 1 when an automatic update is pending

What it manages, and how:
  .ai/** (policies, workflows, agents, templates)   three-way update
  docs/sdlc/*/TEMPLATE.md                            three-way update
  .claude/memory/README.md, .codex/memory/README.md  three-way update, per runtime the project uses
  the managed block in CLAUDE.md and/or AGENTS.md    three-way update of the block only
  .gitignore                                         missing entries appended
  .ai/project/**, the instruction files themselves,
  .claude/settings.json, .codex/config.toml          created when missing, never updated

A project uses the runtime(s) it declares: CLAUDE.md or .claude/ means Claude
Code, AGENTS.md or .codex/ means Codex, both means both. A project that declares
neither gets the runtime this copy of the plugin was installed for, exactly as
the scaffolds do.

Three-way update: a file whose content is a version this plugin once shipped was
never edited, so it is replaced. An edited file is merged against the shipped
version closest to it (git merge-file for text, per key for JSON), keeping every
edit. A real conflict leaves the project file alone and puts the plugin's version
in a git-ignored local directory for a human or /project-update to merge.
"""
import argparse, contextlib, copy, difflib, hashlib, io, json, os, re, subprocess, sys, tempfile
from collections import OrderedDict
from datetime import datetime, timezone

sys.dont_write_bytecode = True  # never leave __pycache__ in an installed plugin
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import migrations  # noqa: E402  # lives next to this script
from migrations import SchemaError  # noqa: E402
import render_instructions  # noqa: E402  # lives next to this script
SKILLS = os.path.dirname(HERE)
TEMPLATES = {
    "ai-init": os.environ.get("CLAUDE_AGENTIC_TEMPLATES", os.path.join(SKILLS, "ai-init", "templates")),
    "project-init": os.environ.get("CLAUDE_ROUTING_TEMPLATES", os.path.join(SKILLS, "project-init", "templates")),
}
HISTORY = os.environ.get("CLAUDE_AGENTIC_HISTORY", os.path.join(HERE, "history"))
VERSION_FILE = ".ai/VERSION"
STATE_FILE = ".ai/state/current.json"
RULES_DIR = ".ai/rules"
# Directories a stale rule block is never hunted in: a dependency's instruction
# file is not ours (the path guard refuses it too), and .git is not text.
RULES_SKIP = {".git", ".ai", "vendor", "node_modules", "bower_components",
              "third_party", "Pods", "site-packages", ".venv", ".pnpm", ".yarn"}
START, END = "<!-- claude-agentic:start -->", "<!-- claude-agentic:end -->"
MISSING = object()
HASH_RE = re.compile(rb"sha256:[0-9a-f]{64}")

PROJECT_INIT_MAP = [  # template -> target, kind
    ("sdlc-README.md", "docs/sdlc/README.md", "update"),
    ("intent.md", "docs/sdlc/intent/TEMPLATE.md", "update"),
    ("spec.md", "docs/sdlc/specs/TEMPLATE.md", "update"),
    ("plan.md", "docs/sdlc/plans/TEMPLATE.md", "update"),
    ("adr.md", "docs/sdlc/adr/TEMPLATE.md", "update"),
    # the project's own principles: created once, then it is the project's file
    ("constitution.md", "docs/sdlc/constitution.md", "create"),
]
RUNTIME_MAP = {  # the per-runtime layer of the project-init scaffold
    "claude": [("memory-README.md", ".claude/memory/README.md", "update"),
               ("project-settings.json", ".claude/settings.json", "create")],
    "codex":  [("memory-README.md", ".codex/memory/README.md", "update"),
               ("project-config.toml", ".codex/config.toml", "create")],
    "gemini": [("memory-README.md", ".gemini/memory/README.md", "update")],
    "junie":  [("memory-README.md", ".junie/memory/README.md", "update")],
}
INSTRUCTION_FILE = {  # runtime -> (file, block template, minimal template)
    "claude": ("CLAUDE.md", "CLAUDE.block.md", "CLAUDE.minimal.md"),
    "codex":  ("AGENTS.md", "AGENTS.block.md", "AGENTS.minimal.md"),
    "gemini": ("GEMINI.md", "GEMINI.block.md", "GEMINI.minimal.md"),
    "junie":  (".junie/guidelines.md", "junie-guidelines.block.md",
               "junie-guidelines.minimal.md"),
}
SKELETON = {  # runtime -> the project-init template that scaffolds its instruction file
    "claude": "CLAUDE.md",
    "codex":  "AGENTS.md",
    "gemini": "GEMINI.md",
    "junie":  "junie-guidelines.md",
}


def instruction_history_keys():
    """{instruction file: [history keys]} — a root instruction file is shipped
    twice, as the project-init skeleton that scaffolds it and as the ai-init
    minimal template, so a migration that matches shipped text must see both."""
    out = {}
    for runtime, (name, _, minimal_tpl) in INSTRUCTION_FILE.items():
        out[name] = ["project-init/" + SKELETON[runtime], "ai-init/" + minimal_tpl]
    return out


def template_targets():
    """{project target: history key} for the templates that land outside .ai/.
    Every runtime's entries, not only this project's, so a rename resolves the
    same way for a Claude, a Codex and a dual-runtime project."""
    out = {target: "project-init/" + src for src, target, _ in PROJECT_INIT_MAP}
    for entries in RUNTIME_MAP.values():
        for src, target, _ in entries:
            out[target] = "project-init/" + src
    return out


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
    def __init__(self, root, renames=None):
        try:
            with open(os.path.join(root, "index.json"), encoding="utf-8") as fh:
                self.index = json.load(fh)
        except (OSError, ValueError):
            self.index = {}
        self.root = root
        # {new key: [old keys]} from the migrations' MOVES: a template that moved
        # keeps the versions it was shipped under its old name.
        self.renames = renames or {}

    def chain(self, key):
        """A template's keys, the oldest name first, ending with this one. The
        registry rules out cycles; the visited set makes the walk safe anyway."""
        out, seen = [], set()

        def walk(k):
            if k in seen:
                return
            seen.add(k)
            for old in self.renames.get(k, []):
                walk(old)
            out.append(k)
        walk(key)
        return out

    def versions(self, key):
        """Every shipped version of a template, oldest first, as bytes. A file
        the user edited before a rename is merged against the version it was
        installed from, which was shipped under the old key."""
        out = []
        for k in self.chain(key):
            for h in self.index.get(k, []):
                try:
                    out.append(read(os.path.join(self.root, "blobs", h)))
                except OSError:
                    pass
        return out


# ---------------------------------------------------------------- merging
def closest(candidates, ours, score):
    best, best_score = None, -1.0
    for c in candidates:  # oldest first; ties keep the older one
        s = score(c, ours)
        if s > best_score:
            best, best_score = c, s
    return best


def text_ratio(a, b):
    return difflib.SequenceMatcher(None, a.splitlines(), b.splitlines(), autojunk=False).ratio()


def merge_text(ours, base, theirs):
    with tempfile.TemporaryDirectory() as d:
        paths = [os.path.join(d, n) for n in ("ours", "base", "theirs")]
        for p, c in zip(paths, (ours, base, theirs)):
            with open(p, "wb") as fh:
                fh.write(c)
        r = subprocess.run(["git", "merge-file", "-p", "--quiet", *paths], capture_output=True, check=False)
    return r.stdout if r.returncode == 0 else None


def flatten(value, prefix=""):
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out.update(flatten(v, prefix + ("." if prefix else "") + str(k)))
        return out or {prefix: {}}
    return {prefix: value}


def json_score(base, ours):
    fb, fo = flatten(base), flatten(ours)
    return sum(1 for k, v in fo.items() if k in fb and fb[k] == v)


def merge_json(base, ours, theirs, path, conflicts):
    if ours == theirs:
        return ours
    if ours == base:
        return theirs
    if theirs == base:
        return ours
    if isinstance(ours, dict) and isinstance(theirs, dict) and (base is MISSING or isinstance(base, dict)):
        b = base if isinstance(base, dict) else {}
        out = OrderedDict()
        for k in list(ours) + [k for k in theirs if k not in ours]:
            v = merge_json(b.get(k, MISSING), ours.get(k, MISSING), theirs.get(k, MISSING), path + [k], conflicts)
            if v is not MISSING:
                out[k] = v
        return out
    conflicts.append(".".join(map(str, path)) or "(root)")
    return ours


def dump_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def leaf_changes(before, after):
    """Changed leaf paths; a whole new or removed subtree is reported once, at its top."""
    fb, fa = flatten(before), flatten(after)

    def top(key, other):
        parts = key.split(".")
        for n in range(1, len(parts) + 1):
            prefix = ".".join(parts[:n])
            if not any(k == prefix or k.startswith(prefix + ".") for k in other):
                return prefix
        return key

    out = set()
    for k in set(fb) | set(fa):
        if k not in fb:
            out.add("+ " + top(k, fb))
        elif k not in fa:
            out.add("- " + top(k, fa))
        elif fb[k] != fa[k]:
            out.add("~ " + k)
    return sorted(out, key=lambda c: c[2:])


# ---------------------------------------------------------------- schema
def detect_version(plan):
    """A project's schema version: None when .ai/ is absent (not an agentic project),
    0 when .ai/ has no VERSION (every project scaffolded before schema 1)."""
    if not os.path.isdir(os.path.join(plan.root, ".ai")):
        return None
    try:
        raw = plan.read(VERSION_FILE)
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
    return int(text)


class MigrationContext:
    """What a migration sees: the project as this run leaves it, not the disk."""

    def __init__(self, plan, module, version_from, state, history):
        self.plan = plan
        self.module = module
        self.version_from = version_from
        self.state = state
        self.history = history
        self.root = plan.root
        self.runtimes = project_runtimes(plan.root)

    # ---- what the plugin shipped, so a migration can recognise its own text
    # instead of matching a regular expression against the project's prose.
    def instruction_files(self):
        """The root instruction files this project actually has, one per runtime
        it declares."""
        return [INSTRUCTION_FILE[rt][0] for rt in self.runtimes
                if self.exists(INSTRUCTION_FILE[rt][0])]

    def shipped(self, path):
        """Every version of every template the plugin ever shipped at this
        project path, oldest first. Renamed templates come with it: History
        follows the MOVES chain and RETIRED."""
        keys = list(instruction_history_keys().get(path, []))
        key = migrations.template_key(path, template_targets())
        if key and key not in keys:
            keys.append(key)
        out = []
        for k in keys:
            for version in self.history.versions(k):
                if version not in out:
                    out.append(version)
        return out

    def block_status(self, path):
        """"none" when this file has no managed block, "shipped" when the block
        is one the plugin installed, "edited" when a human changed it inside the
        markers — the one case where the plugin never writes over it."""
        text = self.read(path)
        runtime = next((rt for rt, entry in INSTRUCTION_FILE.items() if entry[0] == path), None)
        if text is None or runtime is None:
            return "none"
        start, end = text.find(START.encode()), text.find(END.encode())
        if start < 0 or end < 0:
            return "none"
        ours = text[start:end + len(END)] + b"\n"
        block_tpl = INSTRUCTION_FILE[runtime][1]
        tpl = read(os.path.join(TEMPLATES["ai-init"], block_tpl))
        if ours == tpl or ours in self.history.versions("ai-init/" + block_tpl):
            return "shipped"
        return "edited"

    def hint(self, text):
        """Say something to the human that is not an operation on a file."""
        if text not in self.plan.hints:
            self.plan.hints.append(text)

    def exists(self, path):
        return self.read(path) is not None

    def read(self, path):
        self._check_path(path)
        try:
            return self.plan.read(path)
        except OSError as exc:
            raise SchemaError("%04d: %s cannot be read: %s" % (self.module.VERSION, path, exc)) from exc

    def _check_path(self, path):
        why = migrations.path_error(path)
        if why:
            raise SchemaError("%04d: %r is %s" % (self.module.VERSION, path, why))

    def read_json(self, path):
        raw = self.read(path)
        if raw is None:
            return None
        try:
            return json.loads(raw, object_pairs_hook=OrderedDict)
        except ValueError:
            return None

    # ---- operations. Each is idempotent: a target already in its final state
    # records nothing, so a re-run after an interrupted apply is a no-op.
    def _add(self, action, target, note="", **kw):
        self._check_path(target)
        if not isinstance(kw.get("content", b""), bytes):
            raise SchemaError("%04d: %s content must be bytes, not %s"
                              % (self.module.VERSION, target, type(kw["content"]).__name__))
        self.plan.add(action, target, note, migration=self.module.VERSION, **kw)

    def create(self, path, content):
        """Add a file the project does not have yet."""
        if not self.exists(path):
            self._add("create", path, content=content)

    def move(self, src, dst):
        """Move a file the project may have edited. The pair must be in MOVES, so
        the rename is visible to the history lookup without running the migration."""
        if (src, dst) not in self.module.MOVES:
            raise SchemaError("%04d: move(%r, %r) is not in MOVES" % (self.module.VERSION, src, dst))
        data = self.read(src)
        if data is None:  # already moved, or the project never had it
            return
        there = self.read(dst)
        if there is not None and there != data:
            self._add("conflict", dst, "%s was moved here, but this file already exists" % src,
                      conflict_copy=data, src=src)
            return
        # there == data means a previous apply wrote dst and stopped before
        # removing src: the move simply finishes.
        self._add("move", dst, content=data, src=src)
        self.plan.remove(src)

    def edit_text(self, path, fn, note="migrated"):
        """Rewrite a text file the project has; fn returns its input to do nothing."""
        data = self.read(path)
        if data is None:
            return
        new = fn(data)
        if new != data:
            self._add("update", path, note, content=new)

    def edit_json(self, path, fn):
        """Rewrite a JSON file the project has. A policy file's leaf changes are
        listed for confirmation, exactly as a merged policy change is."""
        raw = self.read(path)
        if raw is None:
            return
        try:
            before = json.loads(raw, object_pairs_hook=OrderedDict)
        except ValueError as exc:
            # Not "nothing to do": the migration could not run. A conflict holds
            # the schema version, so the next run tries again.
            self._add("conflict", path, "is not valid JSON, so this migration could not run (%s)" % exc)
            return
        after = fn(copy.deepcopy(before))
        if after == before:
            return
        policy = leaf_changes(before, after) if "/policies/" in "/" + path else None
        self._add("update", path, "migrated", content=dump_json(after), policy=policy)

    def patch_state(self, fn):  # noqa: D401
        """Change the task in flight. update.py writes .ai/state/current.json the
        way state.py does — atomically, with a history entry — so a task started
        before the migration keeps working after it."""
        if self.state is None:
            return
        after = fn(copy.deepcopy(self.state))
        if not isinstance(after, dict):
            raise SchemaError("%04d: patch_state must return the state object, not %s"
                              % (self.module.VERSION, type(after).__name__))
        if after == self.state:
            return
        after["updated_at"] = utc_now()
        after.setdefault("history", []).append(
            {"at": utc_now(), "event": "schema_migrated",
             "detail": "%04d %s" % (self.module.VERSION, self.module.TITLE)})
        self.state = after
        self._add("update", STATE_FILE, "task state migrated",
                  content=(json.dumps(after, indent=2, ensure_ascii=False) + "\n").encode())

    def delete(self, path, reason):
        """Propose a deletion. It is only listed until a human passes
        --apply --confirm-delete NAME; nothing else in this file removes a file."""
        if not self.exists(path):
            return
        if not self.plan.confirm_delete:
            self._add("delete?", path, reason, reason=reason)
            return
        self._add("delete", path, reason, reason=reason)
        # Out of the virtual tree, so this run's template walk does not put it
        # back. A template the plugin still ships is re-created by the next run:
        # a migration that deletes must retire the template in the same release.
        self.plan.remove(path)


def run_migrations(plan, version, history):
    """Plan every migration this project is missing, oldest first, before the
    three-way merge sees a single file. Returns the modules that ran."""
    mods = [m for m in migrations.load() if version < m.VERSION <= migrations.CURRENT]
    state = None
    try:
        raw = plan.read(STATE_FILE)
    except OSError as exc:
        raise SchemaError("%s cannot be read: %s — a migration must see the task in flight"
                          % (STATE_FILE, exc)) from exc
    if raw is not None:
        # state.py dies loudly on a corrupt current.json because ai-scope-guard
        # derives its boundaries from it; a migration must not quietly skip it.
        try:
            state = json.loads(raw, object_pairs_hook=OrderedDict)
        except ValueError as exc:
            raise SchemaError("%s is not valid JSON (%s) — inspect it by hand" % (STATE_FILE, exc)) from exc
        if not isinstance(state, dict):
            raise SchemaError("%s is not a task state object" % STATE_FILE)
    for mod in mods:
        # A copy each, taken from the plan: a migration that mutates ctx.state in
        # place without patch_state changes nothing for the next one.
        planned = plan.final.get(STATE_FILE)
        if planned is not None:
            state = json.loads(planned, object_pairs_hook=OrderedDict)
        mod.plan(MigrationContext(plan, mod, version, copy.deepcopy(state), history))
    if state is not None:
        plan.hints.append("%s: a task is in flight while the schema changes — check that the files "
                          "its current step may touch still exist afterwards" % STATE_FILE)
    return mods


# ---------------------------------------------------------------- planning
class Plan:
    def __init__(self, root):
        self.root = root
        self.items = []   # dicts: action, target, note, content, conflict_copy, policy
        self.hints = []
        self.schema = None  # (from, to, [migration modules]) when migrations are pending
        self.confirm_delete = None  # the human who confirmed this run's deletions
        self.held = None  # the schema version kept until a migration item is settled
        self.final = {}   # target -> bytes after this run (for cross-file fixes)
        self.removed = set()  # targets this run takes away
        self.seen = {}    # target -> sha of what was on disk when it was first read,
        #                   or None when nothing was there: apply's precondition
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
        and the merge input are the same bytes. A second item for the same target
        (a move and then its merge) is checked against what this run wrote."""
        if target not in self.seen:
            path = os.path.join(self.root, target)
            self.seen[target] = sha(read(path)) if os.path.isfile(path) and not os.path.islink(path) else None
        return self.seen[target]

    def add(self, action, target, note="", content=None, conflict_copy=None, policy=None,
            migration=None, src=None, reason=None):
        expect = self.before(target)
        self.items.append(dict(action=action, target=target, note=note, content=content,
                               conflict_copy=conflict_copy, policy=policy, migration=migration,
                               src=src, reason=reason, expect=expect,
                               src_expect=self.before(src) if src else None))
        if content is not None:
            self.final[target] = content
            self.removed.discard(target)  # planned content wins over an earlier removal

    @property
    def local_dir(self):
        base = ".ai/local/plugin-update" if os.path.isdir(os.path.join(self.root, ".ai")) \
            else ".claude/memory/local/plugin-update"
        return base


def three_way(plan, history, key, target, theirs):
    ours = plan.read(target)
    if ours is None:
        plan.add("create", target, content=theirs)
        return
    is_mirror = target.endswith(".ai/policies/risk-tiers.md")
    norm = (lambda b: HASH_RE.sub(b"sha256:" + b"0" * 64, b)) if is_mirror else (lambda b: b)
    if norm(ours) == norm(theirs):
        return
    versions = [v for v in history.versions(key) if norm(v) != norm(theirs)]
    if any(norm(v) == norm(ours) for v in versions):
        policy = None
        if target.endswith(".json") and "/policies/" in "/" + target:
            try:
                policy = leaf_changes(json.loads(ours, object_pairs_hook=OrderedDict),
                                      json.loads(theirs, object_pairs_hook=OrderedDict))
            except ValueError:
                policy = None
        plan.add("update", target, "unchanged since it was installed",
                 content=fix_mirror(plan, target, theirs, ours), policy=policy)
        return

    if target.endswith(".json"):
        try:
            o = json.loads(ours, object_pairs_hook=OrderedDict)
            t = json.loads(theirs, object_pairs_hook=OrderedDict)
            bases = [json.loads(v, object_pairs_hook=OrderedDict) for v in versions]
        except ValueError:
            plan.add("conflict", target, "not valid JSON; not merged", conflict_copy=theirs)
            return
        base = closest(bases, o, json_score) if bases else MISSING
        conflicts = []
        merged = merge_json(base, o, t, [], conflicts)
        policy = leaf_changes(o, merged) if "/policies/" in "/" + target else None
        if merged == o and not conflicts:
            return
        if merged != o:
            plan.add("merge", target, "your edits kept", content=dump_json(merged), policy=policy)
        if conflicts:
            plan.add("conflict", target, "kept your value for: " + ", ".join(conflicts), conflict_copy=theirs)
            model_keys = [c for c in conflicts if c.split(".")[0] == "model_tiers" or ".review_model" in "." + c]
            if target.endswith("policies/risk-tiers.json") and model_keys:
                hint = ("%s: %s — the plugin now names tiers (FAST/BALANCED/STRONG/EXPERT), not models; "
                        "the model of a tier comes from the installed plan: state.py profile --tier <TIER>"
                        % (target, ", ".join(model_keys)))
                if hint not in plan.hints:
                    plan.hints.append(hint)
        return

    base = closest(versions, norm(ours), lambda b, o: text_ratio(norm(b), o)) if versions else None
    merged = merge_text(norm(ours), norm(base), norm(theirs)) if base is not None else None
    if merged is None:
        plan.add("conflict", target, "edited here and changed in the plugin", conflict_copy=theirs)
    elif merged != norm(ours):
        plan.add("merge", target, "your edits kept", content=fix_mirror(plan, target, merged, ours))


def fix_mirror(plan, target, content, ours):
    """risk-tiers.md carries the sha256 of risk-tiers.json. Carry the project's sync
    state forward: a mirror that matched its JSON before this run points at the JSON
    this run leaves behind; a mirror that was already stale, or a JSON left with a
    conflict, keeps its old hash so /ai-status keeps warning."""
    if not target.endswith(".ai/policies/risk-tiers.md"):
        return content
    old = HASH_RE.search(ours)
    # The disk, not the plan: the question is whether the mirror matched the JSON
    # the project had before this run.
    json_target = target[:-3] + ".json"
    json_path = os.path.join(plan.root, json_target)
    before = read(json_path) if os.path.exists(json_path) else None
    in_sync = old is not None and before is not None and old.group(0) == b"sha256:" + sha(before).encode()
    conflicted = any(i["action"] == "conflict" and i["target"] == json_target for i in plan.items)
    after = plan.final.get(json_target, None if json_target in plan.removed else before)
    if in_sync and not conflicted and after is not None:
        return HASH_RE.sub(b"sha256:" + sha(after).encode(), content, count=1)
    return HASH_RE.sub(old.group(0), content, count=1) if old else content


def block_update(plan, history, runtime):
    name, block_tpl, minimal_tpl = INSTRUCTION_FILE[runtime]
    if name in plan.removed:  # a migration moved this instruction file away
        return
    tpl = read(os.path.join(TEMPLATES["ai-init"], block_tpl))
    text = plan.read(name)
    if text is None:
        created = read(os.path.join(TEMPLATES["ai-init"], minimal_tpl)).replace(
            b"{{PROJECT}}", os.path.basename(plan.root).encode())
        plan.add("create", name, "with the managed block", content=created.rstrip(b"\n") + b"\n\n" + tpl)
        return
    s, e = text.find(START.encode()), text.find(END.encode())
    if s < 0 or e < 0:
        plan.add("update", name, "managed block appended",
                 content=text.rstrip(b"\n") + b"\n\n" + tpl)
        return
    e += len(END)
    ours = text[s:e] + b"\n"
    if ours == tpl:
        return
    versions = [v for v in history.versions("ai-init/" + block_tpl) if v != tpl]
    if ours in versions:
        new_block = tpl
        note = "managed block replaced (unchanged since it was installed)"
    else:
        base = closest(versions, ours, text_ratio) if versions else None
        new_block = merge_text(ours, base, tpl) if base is not None else None
        note = "managed block merged, your edits kept"
    if new_block is None:
        plan.add("conflict", name, "the managed block was edited here and changed in the plugin",
                 conflict_copy=tpl)
        return
    plan.add("update", name, note, content=text[:s] + new_block.rstrip(b"\n") + text[e:])


def rendered_rules(plan):
    """Every (file, slug) in the project that carries a rule block today, plus
    every path-scoped copy under .claude/rules/. Walked rather than remembered:
    a manifest would be one more file to keep true, and the markers already say
    who wrote them."""
    blocks, docs = [], []
    names = set(render_instructions.RULE_FILE.values())
    for dirpath, dirnames, filenames in os.walk(plan.root):
        dirnames[:] = sorted(d for d in dirnames if d not in RULES_SKIP)
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


def rules_update(plan, runtimes):
    """Render `.ai/rules/<slug>.md` into the instruction file of every directory
    it names, and take back what a rule no longer asks for. The text around a
    block belongs to the project and is never read for meaning, only preserved."""
    rules_path = os.path.join(plan.root, RULES_DIR)
    if not os.path.isdir(rules_path):
        return
    try:
        rules = render_instructions.load_rules(rules_path)
    except render_instructions.RenderError as exc:
        plan.hints.append("%s — that rule is not rendered; the rest are" % exc)
        return
    wanted = render_instructions.rule_targets(rules, runtimes)
    managed = {(i["target"], i["slug"]) for i in wanted if i["kind"] == "block"}
    kept_docs = {i["target"] for i in wanted if i["kind"] == "doc"}

    for item in wanted:
        source = "%s/%s.md" % (RULES_DIR, item["slug"])
        target, content = item["target"], item["content"]
        current = plan.read(target)
        if item["kind"] == "doc":
            new = content.encode()
            if current is None:
                plan.add("create", target, "rendered from " + source, content=new)
            elif current != new:
                plan.add("update", target, "rendered from " + source, content=new)
            continue
        text = "" if current is None else current.decode("utf-8")
        new = render_instructions.splice_rule(text, item["slug"], content).encode()
        if current is None:
            plan.add("create", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)
        elif current != new:
            plan.add("update", target, "rule block %s from %s" % (item["slug"], source),
                     content=new)

    blocks, docs = rendered_rules(plan)
    for target, slug in blocks:
        if (target, slug) in managed:
            continue
        text = plan.read(target).decode("utf-8")
        # The block is ours; the file is not. Take the block, leave the file.
        plan.add("update", target, "rule block %s removed (%s/%s.md no longer renders here)"
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
    plan.items = [i for i in plan.items if i["target"] != ".gitignore" or i["migration"] is not None]
    plan.add("update", ".gitignore", "entries appended: " + ", ".join(missing), content=new)


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


def build_plan(root, confirm_delete=None):
    plan = Plan(root)
    plan.confirm_delete = confirm_delete
    has_ai = os.path.isdir(os.path.join(root, ".ai"))
    has_sdlc = os.path.isdir(os.path.join(root, "docs", "sdlc"))
    if not (has_ai or has_sdlc):
        return None
    # Only a project with .ai/ runs migrations, so only it can be carrying a
    # moved file — and a faulty registry must not break the projects that cannot.
    # renames() validates the registry, raising the same SchemaError as load().
    history = History(HISTORY, migrations.renames(template_targets()) if has_ai else {})

    runtimes = project_runtimes(root)
    if has_ai:
        version = detect_version(plan)
        migrations.load()  # CURRENT comes from the file names; this validates the registry
        if version > migrations.CURRENT:
            raise SchemaError("%s says schema %d, this plugin ships schema %d — update the plugin "
                              "(claude-agentic/install.sh)" % (VERSION_FILE, version, migrations.CURRENT))
        if version < migrations.CURRENT:
            mods = run_migrations(plan, version, history)
            plan.schema = (version, migrations.CURRENT, mods)
            # The schema only advances when its migrations are done. Writing
            # VERSION over an unresolved conflict, or over a deletion nobody has
            # confirmed, would drop the operation: the next run would see a
            # current project and plan nothing.
            stuck = [i for i in plan.items if i["migration"] is not None
                     and i["action"] in ("conflict", "delete?")]
            if stuck:
                plan.held = version
                plan.hints.append("the schema stays at %d until %s — resolve a conflict by hand, confirm a "
                                  "deletion with --apply --confirm-delete NAME, then run /project-update again"
                                  % (version, ", ".join("%s (%s)" % (i["target"], i["action"]) for i in stuck)))
            else:
                # Last of the migration items: an apply that stops short leaves the
                # version alone, and the next run plans the same migrations again.
                plan.add("update" if plan.exists(VERSION_FILE) else "create", VERSION_FILE,
                         "schema %d" % migrations.CURRENT, content=b"%d\n" % migrations.CURRENT,
                         migration=migrations.CURRENT)

    if has_sdlc:
        tpl = TEMPLATES["project-init"]
        entries = list(PROJECT_INIT_MAP)
        for rt in runtimes:
            entries += RUNTIME_MAP[rt]
        for src, target, kind in entries:
            content = read(os.path.join(tpl, src))
            if target in plan.removed:  # a migration moved it away in this run
                continue
            if kind == "create":
                if not plan.exists(target):
                    plan.add("create", target, content=content.replace(
                        b"{{PROJECT}}", os.path.basename(root).encode()))
            else:
                three_way(plan, history, "project-init/" + src, target, content)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

    if has_ai:
        tpl = TEMPLATES["ai-init"]
        files = []
        for dirpath, _, names in os.walk(os.path.join(tpl, ".ai")):
            for n in names:
                files.append(os.path.relpath(os.path.join(dirpath, n), tpl))
        # JSON before markdown, so the risk-tier mirror can point at the merged JSON.
        for rel in sorted(files, key=lambda r: (not r.endswith(".json"), r)):
            if rel == VERSION_FILE:  # owned by the migration step, never merged
                continue
            if rel in plan.removed:  # a migration moved it away in this run
                continue
            content = read(os.path.join(tpl, rel))
            if rel.startswith(".ai/project/") or rel.startswith(".ai/reports/"):
                if not plan.exists(rel):
                    plan.add("create", rel, content=content)
                continue
            three_way(plan, history, "ai-init/" + rel, rel, content)
        for rt in runtimes:
            block_update(plan, history, rt)
        rules_update(plan, runtimes)
        gitignore_update(plan, os.path.join(tpl, "gitignore.snippet"))

        testing = plan.read(".ai/policies/testing.md")
        if testing is not None:
            for field, why in (
                ("verify_command", "the feedback loop needs it"),
                ("step_test_command", "a step runs only its own tests"),
                ("e2e_command", "e2e runs once at the end of a task; write 'none' if there is no suite"),
                ("lint_command", "a sensor reads it; run `sensors.py detect`, and write 'none' if there is none"),
                ("typecheck_command", "a sensor reads it; run `sensors.py detect`, and write 'none' if there is none"),
            ):
                if re.search(rb"(?m)^" + field.encode() + rb":[ \t]*(#.*)?$", testing):
                    plan.hints.append(".ai/policies/testing.md: %s is empty — %s" % (field, why))
                elif not re.search(rb"(?m)^" + field.encode() + rb":", testing):
                    plan.hints.append(".ai/policies/testing.md: %s is missing — %s" % (field, why))
        budget_hints(plan, runtimes)

    if has_sdlc:
        constitution_hint(plan)
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


def record_migration(plan, ops, deletions):
    """The record of what was taken away, rewritten after every such operation:
    an abort must not lose the note of a deletion a human approved. A second run
    on the same day appends to the record instead of replacing it."""
    path = os.path.join(plan.report_dir, "migration.json")
    existing = {}
    full = os.path.join(plan.root, path)
    if os.path.isfile(full):
        try:
            existing = json.loads(read(full), object_pairs_hook=OrderedDict)
        except ValueError:
            existing = {}
        if not isinstance(existing, dict):  # hand-edited into another shape
            existing = {}
    record = OrderedDict()
    record["from"] = existing.get("from", plan.schema[0] if plan.schema else None)
    # The version the project is actually at now, read from the disk and not from
    # the plan: this record is written before the files move, and an aborted run
    # never reaches CURRENT.
    version_path = os.path.join(plan.root, VERSION_FILE)
    on_disk = read(version_path).decode().strip() if os.path.isfile(version_path) else ""
    record["to"] = int(on_disk) if on_disk.isdigit() else record["from"]
    if plan.schema and record["to"] != plan.schema[1]:
        record["target"] = plan.schema[1]
        if plan.held is not None:
            record["held_at"] = plan.held
    record["applied_at"] = utc_now()
    # A recovery re-run replays the same operation: record it once.
    record["ops"] = list(existing.get("ops", []))
    record["ops"] += [o for o in ops if o not in record["ops"]]
    record["deletions"] = list(existing.get("deletions", []))
    record["deletions"] += [d for d in deletions
                            if not any(e.get("path") == d["path"] for e in record["deletions"])]
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
    # The run finished: say which version it actually reached. Also after a run
    # that replayed an aborted one and so recorded no operation of its own.
    try:
        if recorded or os.path.isfile(os.path.join(plan.root, plan.report_dir, "migration.json")):
            record_migration(plan, [], [])
    except OSError as exc:
        raise Abort(None, str(exc)) from exc


def apply_item(plan, item, written, recorded):
    target, action = item["target"], item["action"]
    if action == "delete?":  # listed only, until a human confirms it
        return
    mode = None
    if action in ("move", "delete"):
        source = item["src"] if action == "move" else target
        check(plan, item, source, item["src_expect"] if action == "move" else item["expect"], written)
        if action == "move":
            check(plan, item, target, item["expect"], written)
            mode = os.stat(os.path.join(plan.root, source)).st_mode & 0o7777
        keep_original(plan, source)
        recorded.append(target)
        # Recorded before the file is gone: an abort later must not lose the note
        # of what was taken away, or of who approved a deletion.
        record_migration(plan,
                         [dict(action=action, migration=item["migration"],
                               **(dict(src=item["src"], dst=target) if action == "move" else dict(path=target)))],
                         [dict(path=target, confirmed_by=plan.confirm_delete, at=utc_now())]
                         if action == "delete" else [])
    elif item["content"] is not None:
        check(plan, item, target, item["expect"], written)
        # A migration rewriting a file outside .ai/ is rewriting a file the
        # project owns. Keep what it had, exactly as a move or a deletion does,
        # so a rewrite a human disagrees with can be read back and undone.
        if item["migration"] is not None and not target.startswith(".ai/") \
                and item["expect"] is not None and target not in written \
                and not os.path.exists(os.path.join(plan.root, plan.report_dir, "original", target)):
            keep_original(plan, target)
    if item["content"] is not None:
        write_file(plan.root, target, item["content"], mode=mode)
        written[target] = sha(item["content"])
    if action == "move":
        os.remove(os.path.join(plan.root, item["src"]))
        written[item["src"]] = None
    elif action == "delete":
        os.remove(os.path.join(plan.root, target))
        written[target] = None
    if item["conflict_copy"] is not None:
        write_file(plan.root, os.path.join(plan.local_dir, target), item["conflict_copy"])


def report(plan, applied):
    auto = [i for i in plan.items if i["action"] not in ("conflict", "delete?")]
    conflicts = [i for i in plan.items if i["action"] == "conflict"]
    deletions = [i for i in plan.items if i["action"] == "delete?"]
    head = "applied" if applied else "dry run, nothing written; --apply to write"
    print("project-update: %s (%s)" % (plan.root, head))
    if not plan.items:
        print("  up to date with the installed plugin")
    def shown(i):
        return "%s -> %s" % (i["src"], i["target"]) if i["src"] else i["target"]
    width = max([len(shown(i)) for i in plan.items] + [10])
    if plan.schema:
        frm, to, mods = plan.schema
        print("  %-9s %-*s  (%d migration%s: %s)" % (
            "schema", width, "%d -> %d" % (frm, to), len(mods), "" if len(mods) == 1 else "s",
            ", ".join("%04d %s" % (m.VERSION, m.TITLE) for m in mods)))
    for i in plan.items:
        note = i["note"]
        if i["migration"] is not None:
            note = "[%04d]%s" % (i["migration"], " " + note if note else "")
        if i["action"] == "delete?":
            note += "; needs --apply --confirm-delete NAME"
        if i["action"] == "conflict" and i["conflict_copy"] is not None:
            note += "; plugin version %s %s/%s" % ("at" if applied else "will be at", plan.local_dir, i["target"])
        print("  %-9s %-*s  %s" % (i["action"], width, shown(i), note))
        for change in i["policy"] or []:
            print("  %-9s %-*s    %s" % ("policy", width, "", change))
    for h in plan.hints:
        print("  hint      " + h)
    tail = ""
    if any(i["policy"] for i in auto):
        tail += ", %d policy change(s) to confirm" % sum(len(i["policy"] or []) for i in auto)
    if deletions:
        tail += ", %d deletion(s) awaiting --confirm-delete" % len(deletions)
    print("%d automatic, %d conflict(s)%s" % (len(auto), len(conflicts), tail))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("root", nargs="?", default=".")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--confirm-delete", metavar="NAME",
                    help="a human confirms this run's proposed deletions, and is recorded in "
                         "the migration report; only with --apply")
    args = ap.parse_args()
    if args.confirm_delete is not None:
        if not args.apply:
            ap.error("--confirm-delete only makes sense with --apply")
        if not args.confirm_delete.strip():
            ap.error("--confirm-delete needs the name of the human who confirmed the deletion")
    root = os.path.abspath(args.root)
    for name, tpl in TEMPLATES.items():
        if not os.path.isdir(tpl):
            print("project-update: %s templates not found at %s (run claude-agentic/install.sh)" % (name, tpl), file=sys.stderr)
            return 2
    try:
        plan = build_plan(root, confirm_delete=getattr(args, "confirm_delete", None))
    except SchemaError as exc:
        # --check is read by /ai-status, which reads stdout: it must see the reason.
        print("project-update: %s" % exc, file=sys.stdout if args.check else sys.stderr)
        return 2
    if plan is None:
        print("project-update: %s has neither .ai/ nor docs/sdlc/ — run /ai-init or /project-init first" % root,
              file=sys.stderr)
        return 2
    pending = [i for i in plan.items if i["action"] not in ("conflict", "delete?")]
    if args.check:
        conflicts = sum(1 for i in plan.items if i["action"] == "conflict")
        if pending or plan.schema:
            bits = []
            if plan.schema:
                bits.append("schema %d -> %d" % plan.schema[:2])
            files = sum(1 for i in pending if i["migration"] is None)
            if files:
                bits.append("%d file(s) to update" % files)
            if conflicts:
                bits.append("%d need a manual merge" % conflicts)
            deletions = sum(1 for i in plan.items if i["action"] == "delete?")
            if deletions:
                bits.append("%d deletion(s) a human must confirm" % deletions)
            if plan.held is not None:
                bits.append("the schema stays at %d until they are settled" % plan.held)
            print("project is behind the installed plugin: %s — run /project-update" % ", ".join(bits))
            return 1
        print("project matches the installed plugin" + (" (%d file(s) differ by hand-merge choice)" % conflicts if conflicts else ""))
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
