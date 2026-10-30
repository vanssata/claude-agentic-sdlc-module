#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
project-update: a project scaffolded from the oldest shipped templates, then
edited by hand, is brought up to date without losing an edit (TestProjectUpdate,
the twin of test-project-update.sh).

Migration 0007 (redesign 2.2a): the risk-tier table's edits land in
weight.json, a task in flight gets a mode, and the schema reaches 7 without a
human having to confirm anything.

Every 0007 project is today's scaffold with tests/fixtures/project-update/schema-v6/
laid over it, in a temp directory with a pinned HOME.
"""
import glob
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
SCAFFOLD = os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
MIGRATION = os.path.join(ROOT, "skills", "project-update", "migrations", "0007_weight_model.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "project-update", "schema-v6")
POLICIES = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies")
# The tier policy the plugin stopped shipping in migration 0011: a frozen copy of the
# last shipped version, for the projects that were scaffolded before and for 0007's input.
OLD_TIERS = os.path.join(ROOT, "tests", "fixtures", "project-update", "risk-tiers")
GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]

TWIN_OF = "test-project-update.sh"


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0007_under_test", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_json(path):
    """A JSON file; the task's current.json is read from state.json once migration
    0009 has moved it (R34), so a test reads the task before and after an update."""
    if path.endswith(os.path.join("state", "current.json")) and not os.path.exists(path):
        path = os.path.join(os.path.dirname(path), "state.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def shipped_tables():
    """What _shipped() returns, from the last shipped risk-tiers.json and today's weight.json."""
    doc = read_json(os.path.join(OLD_TIERS, "risk-tiers.json"))
    examples = {t: set(e.get("examples") or []) for t, e in doc["tiers"].items() if isinstance(e, dict)}
    scopes = {s["scope"]: set(s["paths"]) for s in doc["path_scopes"]}
    scalars = {k: [v] for k, v in load_migration()._scalars(doc).items()}  # pylint: disable=protected-access
    return examples, scopes, scalars, read_json(os.path.join(POLICIES, "weight.json"))


def edit_tiers(doc):
    """The risk-tier edits a real project would have."""
    doc["tiers"]["T1"]["examples"].append("a theme colour")
    doc["tiers"]["T4"]["examples"].append("the order export job")
    doc["tiers"]["T6"]["examples"].append("the ERP cut-over")
    extra = {"payments": ["src/Fiscal/**"], "auth": ["**/Login/**"], "infra": ["deploy/prod/**", "ansible/**"],
             "config": ["settings/**"], "pipeline": [".cursor/**"], "dependencies": ["Pipfile"],
             "tests": ["qa/**"]}
    for scope in doc["path_scopes"]:
        scope["paths"] += extra.get(scope["scope"], [])
    doc["path_scopes"].append({"scope": "fiscal", "min_tier": "T5", "paths": ["fiscal/**"]})
    doc["path_scopes"].append({"scope": "reports", "min_tier": "T3", "paths": ["reports/**"]})
    doc["sensors"]["tests"]["max_suite_runs"] = 5
    doc["sensors"]["tests"]["timeout_seconds"] = 900
    doc["remediation_rounds"] = 3
    return doc


class Project:
    def __init__(self, in_flight=False, weight=True, edited=False, tiers=False):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.home = os.path.join(self.tmp.name, "home")
        self.root = os.path.join(self.tmp.name, "p")
        os.makedirs(self.home)
        os.makedirs(self.root)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS", "CLAUDE_CONFIG_DIR")
                    and not k.startswith("RISKRAILS_")}
        self.env.update(HOME=self.home, CLAUDE_AGENTIC_SHARED=os.path.join(ROOT, "ai"))
        subprocess.run(["bash", SCAFFOLD, self.root, "--runtime", "claude"], env=self.env, check=True,
                       capture_output=True)
        shutil.copytree(os.path.join(FIXTURE, ".ai"), os.path.join(self.root, ".ai"), dirs_exist_ok=True)
        if in_flight:
            shutil.copytree(os.path.join(FIXTURE, "in-flight", ".ai"), os.path.join(self.root, ".ai"),
                            dirs_exist_ok=True)
        if tiers or edited:               # scaffolded before 0011 retired the tier policy
            shutil.copytree(OLD_TIERS, self.path("policies"), dirs_exist_ok=True)
        if not weight:                    # scaffolded before the weight table shipped (2.1)
            for name in ("weight.json", "weight.md"):
                os.remove(self.path("policies", name))
        if edited:
            doc = edit_tiers(read_json(self.path("policies", "risk-tiers.json")))
            with open(self.path("policies", "risk-tiers.json"), "w", encoding="utf-8") as fh:
                json.dump(doc, fh, indent=2)
                fh.write("\n")
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(GIT + ["-C", self.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.root, "commit", "-qm", "schema 6"], check=True)

    def path(self, *parts):
        return os.path.join(self.root, ".ai", *parts)

    def update(self, *args):
        return subprocess.run([sys.executable, "-I", UPDATE, self.root] + list(args), env=self.env,
                              capture_output=True, text=True, check=False)

    def confirm(self):
        """--apply --confirm-delete, as a human at a terminal (AI_UNATTENDED stands in for one)."""
        return subprocess.run([sys.executable, "-I", UPDATE, self.root, "--apply", "--confirm-delete", "tester"],
                              env=dict(self.env, AI_UNATTENDED="1"), capture_output=True, text=True, check=False)

    def read(self, *parts):
        with open(self.path(*parts), "rb") as fh:
            return fh.read()

    def version(self):
        return self.read("VERSION").decode().strip()

    def close(self):
        self.tmp.cleanup()


class TestMigration0007(unittest.TestCase):
    def test_conversion(self):
        mod = load_migration()
        base = read_json(os.path.join(POLICIES, "weight.json"))
        before = json.dumps(base, sort_keys=True)
        old = edit_tiers(read_json(os.path.join(OLD_TIERS, "risk-tiers.json")))
        new = mod.convert(old, base, shipped_tables())
        self.assertEqual(json.dumps(base, sort_keys=True), before, "the base is not changed")
        self.assertEqual(new["examples"]["light"][-1], "a theme colour")
        self.assertEqual(new["examples"]["guarded"][-1], "the order export job")
        self.assertEqual(new["examples"]["full"][-1], "the ERP cut-over")
        modules = new["axes"]["domain"]["modules"]
        self.assertIn("src/Fiscal/**", modules)
        self.assertIn("fiscal/**", modules)                         # unknown scope at T5
        self.assertNotIn("reports/**", json.dumps(new))             # unknown scope below T5: dropped
        self.assertNotIn("qa/**", json.dumps(new))                  # tests: dropped
        rev = new["axes"]["reversibility"]
        self.assertIn("deploy/prod/**", rev["irreversible"])
        self.assertIn("ansible/**", rev["needs_step"])
        self.assertIn("settings/**", rev["needs_step"])
        hints = {h["axis"]: h["paths"] for h in new["hints"]}
        self.assertIn("**/Login/**", hints["domain"])
        self.assertIn(".cursor/**", hints["behaviour"])
        self.assertIn("Pipfile", hints["novelty"])
        self.assertEqual((new["tests"]["max_suite_runs"], new["tests"]["timeout_seconds"]), (2, 900))
        self.assertEqual(new["remediation_rounds"], 3)
        for gone in ("tiers", "path_scopes", "diff_budget", "sensors", "pipeline_profiles", "model_tiers"):
            self.assertNotIn(gone, new)
        # Twice is once: a re-run adds nothing.
        self.assertEqual(mod.convert(old, new, shipped_tables()), new)
        # An unedited table converts to the shipped weight table exactly.
        plain = read_json(os.path.join(OLD_TIERS, "risk-tiers.json"))
        self.assertEqual(mod.convert(plain, base, shipped_tables()), base)

    def test_a_projects_own_weight_values_survive(self):
        # Review H1: an unedited risk-tiers.json carries no scalar, and an edited
        # one never overwrites a value the project already set in weight.json.
        mod = load_migration()
        base = read_json(os.path.join(POLICIES, "weight.json"))
        base["tests"].update(max_suite_runs=1, timeout_seconds=3600)
        base["remediation_rounds"] = 4
        plain = read_json(os.path.join(OLD_TIERS, "risk-tiers.json"))
        self.assertEqual(mod.convert(plain, base, shipped_tables()), base)
        edited = edit_tiers(read_json(os.path.join(OLD_TIERS, "risk-tiers.json")))
        got = mod.convert(edited, base, shipped_tables())
        self.assertEqual((got["tests"]["max_suite_runs"], got["tests"]["timeout_seconds"], got["remediation_rounds"]),
                         (1, 3600, 4))
        self.assertIn("the order export job", got["examples"]["guarded"])   # the non-scalar edits still land
        p = Project()
        try:
            weight = os.path.join(p.root, ".ai", "policies", "weight.json")
            with open(weight, "w", encoding="utf-8") as fh:
                json.dump(base, fh, indent=2)
                fh.write("\n")
            subprocess.run(GIT + ["-C", p.root, "commit", "-qam", "own weight values"], check=True)
            self.assertEqual(p.update("--apply").returncode, 0)
            after = json.loads(p.read("policies", "weight.json"))
            self.assertEqual((after["tests"]["max_suite_runs"], after["remediation_rounds"]), (1, 4))
        finally:
            p.close()

    def test_full_apply(self):
        p = Project(edited=True)
        try:
            dry = p.update()
            self.assertIn("schema    6 -> 11", dry.stdout)
            # 0007 neither moves nor deletes the old table; 0011 proposes it, edited copy flagged.
            self.assertEqual([line for line in dry.stdout.split("\n") if "[0007]" in line and "risk-tiers" in line], [])
            self.assertEqual(len([l for l in dry.stdout.split("\n") if l.startswith("  delete?") and "[0011]" in l]), 2)
            done = p.update("--apply")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(p.version(), "6", "the deletions wait for a human, and the schema stays")
            weight = json.loads(p.read("policies", "weight.json"))
            self.assertIn("the order export job", weight["examples"]["guarded"])
            self.assertIn("weight --mirror", done.stdout)
            # The old surface's table stays where it is, with the project's edits, until confirmed.
            self.assertIn("the order export job",
                          json.loads(p.read("policies", "risk-tiers.json"))["tiers"]["T4"]["examples"])
            self.assertTrue(os.path.isfile(p.path("policies", "risk-tiers.md")))
            confirmed = p.confirm()
            self.assertEqual((confirmed.returncode, p.version()), (0, "11"), confirmed.stdout + confirmed.stderr)
            self.assertFalse(os.path.exists(p.path("policies", "risk-tiers.json")))
            # The second run plans no migration and changes no file.
            snapshot = {n: p.read("policies", n) for n in os.listdir(p.path("policies"))}
            again = p.update("--apply")
            self.assertNotIn("schema ", again.stdout)
            self.assertEqual({n: p.read("policies", n) for n in os.listdir(p.path("policies"))}, snapshot)
            self.assertEqual(p.update("--check").returncode, 0)
        finally:
            p.close()

    def test_a_project_without_weight_json_gets_one(self):
        for edited in (False, True):
            p = Project(weight=False, edited=edited)
            try:
                done = p.update("--apply")
                self.assertEqual((done.returncode, p.version()), (0, "11" if not edited else "6"),
                                 done.stdout + done.stderr)
                with open(os.path.join(POLICIES, "weight.json"), "rb") as fh:
                    shipped = fh.read()
                if edited:
                    self.assertIn("the ERP cut-over", json.loads(p.read("policies", "weight.json"))["examples"]["full"])
                else:
                    self.assertEqual(p.read("policies", "weight.json"), shipped)
                self.assertTrue(os.path.isfile(p.path("policies", "weight.md")))
            finally:
                p.close()

    def test_in_flight_state(self):
        # Review focus 1, 0007's half: the task resumes on its own surface, in a
        # mode, with its scope still armed; 0007 run twice changes nothing more.
        p = Project(in_flight=True)
        try:
            done = p.update("--apply")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            state = json.loads(p.read("state", "state.json"))
            self.assertEqual(state["mode"], "guarded")
            self.assertEqual(state["weight"], {"w": None, "axes": {}, "unknown": ["migrated"]})
            self.assertNotIn("schema", state)
            self.assertEqual((state["current_stage"], state["approved_plan"]["current_step_id"]),
                             ("implementation", "1"))
            self.assertEqual(state["approved_plan"]["steps"][0]["allowed_files"],
                             ["src/Shared/Clock.php", "tests/ClockTest.php"])
            self.assertEqual(state["history"][-1]["event"], "schema_migrated")
            first = p.read("state", "state.json")
            p.update("--apply")
            self.assertEqual(p.read("state", "state.json"), first)
            env = dict(p.env, AI_RUNTIME="claude")
            self.assertEqual(state["risk_tier"], "T4")
            got = subprocess.run([sys.executable, "-I", STATE, "--root", p.root, "status"],
                                 env=env, capture_output=True, text=True, check=False)
            self.assertEqual(got.returncode, 0, got.stderr)
            self.assertIn("old surface", got.stdout)
            new = subprocess.run([sys.executable, "-I", STATE, "--root", p.root, "verify", "--scope", "suite"],
                                 env=env, capture_output=True, text=True, check=False)
            self.assertEqual(new.returncode, 1)
            self.assertIn("old surface", new.stderr)
        finally:
            p.close()

    def test_source_names_no_runtime(self):
        with open(MIGRATION, encoding="utf-8") as fh:
            text = fh.read()
        self.assertEqual(re.findall(r"claude|codex", text), [])


HISTORY = os.path.join(ROOT, "skills", "project-update", "history")
HOOK_SCAFFOLD = os.path.join(ROOT, "hooks", "project-scaffold.sh")
FIX = os.path.join(ROOT, "tests", "fixtures", "project-update")
SYNTH = os.path.join(FIX, "migrations-synthetic")
TEMPLATES = os.path.join(ROOT, "skills", "ai-init", "templates")
BLOCK = os.path.join(TEMPLATES, "AGENTS.block.md")
# NOMARK: every agent-session marker and AI_UNATTENDED, cleared for the terminal cases.
NOMARK = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI", "CODEX_SANDBOX",
          "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION", "AI_UNATTENDED")
# R13 reads a shell `pass` up to its first inner quote, and `pass "$3"` in a helper by its
# parameter name: these are the cases it records for check_refused's rules and the journal count.
CHECK_REFUSED_CASE = "$3"
JOURNAL_CASE = "one line per history entry ($(wc -l < "

HISTORY_KEYS = """
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import migrations                                        # noqa: E402
index = json.load(open(os.path.join(root, "skills/project-update/history/index.json")))
current, sources = set(), set()
for name, base in (("ai-init", os.path.join(root, "skills", "ai-init", "templates")),
                   ("project-init", os.path.join(root, "skills", "project-init", "templates")),
                   ("ai-init/.ai", os.path.join(root, "ai"))):
    for d, _, files in os.walk(base):
        for f in files:
            current.add("%s/%s" % (name, os.path.relpath(os.path.join(d, f), base)))
import update                                            # noqa: E402  # for the same key map production uses
mapped = update.template_targets()
for mod in migrations.load():
    for src, dst in mod.MOVES:
        key = migrations.template_key(src, mapped)
        if key:
            sources.add(key)
migrations.renames(mapped)   # production's key graph must be acyclic, not a smaller one
# A RETIRED successor joins the rename chain: that is how a template renamed on
# disk, which no MOVES pair can describe, keeps the versions it shipped under.
shipped = migrations.RETIRED
migrations.RETIRED = dict(shipped, **{"project-init/gone.md": "project-init/sdlc-README.md"})
chain = migrations.renames(mapped).get("project-init/sdlc-README.md", [])
migrations.RETIRED = shipped
assert "project-init/gone.md" in chain, "RETIRED successors must join the rename chain"
orphans = sorted(set(index) - current - sources - set(migrations.RETIRED))
reused = sorted(current & sources)
if orphans:
    print("orphaned history keys (add the move to MOVES, or the key to RETIRED): %s" % ", ".join(orphans))
if reused:
    print("a template is shipped at a path a migration moved away: %s" % ", ".join(reused))
sys.exit(1 if orphans or reused else 0)
"""

CONTIGUOUS = """
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "skills", "project-update"))
import migrations                                        # noqa: E402
mods = migrations.load()
assert [m.VERSION for m in mods] == list(range(1, len(mods) + 1)), "not contiguous from 0001"
migrations.renames()                                     # the key graph must be acyclic
"""


def text_of(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, content, mode="w"):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, mode, encoding=None if "b" in mode else "utf-8") as fh:
        fh.write(content)


def put_json(path, doc):
    """As jq writes it: two-space indent, non-ASCII as is, a final newline."""
    put(path, json.dumps(doc, indent=2, ensure_ascii=False) + "\n")


def sha256(path):
    return hashlib.sha256(raw(path)).hexdigest()


def grep(pattern, out):
    """`grep -c`: the lines of out that match."""
    return sum(1 for line in out.splitlines() if re.search(pattern, line))


def has(pattern, out):
    return grep(pattern, out) > 0


def tree_sum(d):
    """Path and content of every file outside .git."""
    out = []
    for top, dirs, files in os.walk(d):
        dirs[:] = [x for x in dirs if not (top == d and x == ".git")]
        out += [(os.path.relpath(os.path.join(top, f), d), raw(os.path.join(top, f)))
                for f in files if os.path.isfile(os.path.join(top, f))]
    return sorted(out)


def mirror_hashes(md):
    return re.findall(r"sha256:([0-9a-f]*)", text_of(md))


def insert_line(content, n, line, after):
    """sed 'Na line' (after) or 'Ni line' (before)."""
    rows = content.splitlines(keepends=True)
    at = n if after else n - 1
    return "".join(rows[:at] + [line + "\n"] + rows[at:]) if len(rows) >= n else content


def legacy(block):
    return re.sub(r"riskrails:(start|end)", r"Codex-agentic:\1", block)


def replace_line(path, n, line):
    rows = text_of(path).split("\n")
    rows[n - 1] = line
    put(path, "\n".join(rows))


def only(pattern):
    """The one path a glob names; a name that does not exist when it names none or several."""
    paths = glob.glob(pattern)
    return paths[0] if len(paths) == 1 else os.path.join(os.path.dirname(pattern), "<%d matches>" % len(paths))


FIXTURE_V7 = os.path.join(ROOT, "tests", "fixtures", "project-update", "schema-v7")
MIGRATION_0008 = os.path.join(ROOT, "skills", "project-update", "migrations", "0008_renames.py")


def to_schema_7(root):
    """Today's scaffold as a schema-7 project had it: the old marker and route
    names, and .ai/VERSION from the fixture."""
    shutil.copytree(os.path.join(FIXTURE_V7, ".ai"), os.path.join(root, ".ai"), dirs_exist_ok=True,
                    copy_function=shutil.copy)   # a fresh mtime: see TestMigration0009.setUp
    for rel, old, new in (("CLAUDE.md", b"<!-- riskrails:", b"<!-- claude-agentic:"),
                          (".ai/AGENTS.md", b"/riskrails/ai", b"/claude-agentic/ai")):
        path = os.path.join(root, rel)
        with open(path, "rb") as fh:
            data = fh.read()
        assert old in data, (rel, old)
        with open(path, "wb") as fh:
            fh.write(data.replace(old, new))


class TestMigration0008(unittest.TestCase):
    """R35: the markers and routes take the new name, the text around them stays
    byte for byte the project's, and the task's state is not rewritten (R34; the
    file moves in 0009)."""

    def setUp(self):
        self.p = Project()
        to_schema_7(self.p.root)
        claude = os.path.join(self.p.root, "CLAUDE.md")
        with open(claude, "rb") as fh:
            self.claude = b"# my own heading\n\nmy words  stay\r\n" + fh.read() + b"\nand after the block\n"
        with open(claude, "wb") as fh:
            fh.write(self.claude)

    def tearDown(self):
        self.p.close()

    def commit(self):
        subprocess.run(GIT + ["-C", self.p.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.p.root, "commit", "-qm", "schema 7"], check=True)

    def test_after_0007_in_flight(self):
        env = dict(self.p.env, AI_RUNTIME="claude")
        put(os.path.join(self.p.root, "src", "Clock.php"), "x\n")
        self.commit()
        started = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "start", "--goal", "mid-build",
                                  "--workflow", "feature", "--files", "src/Clock.php", "--tests", "tests/ClockTest.php",
                                  "--declare", "behaviour=0:none", "--declare", "novelty=0:none"],
                                 env=env, capture_output=True, text=True, check=False)
        self.assertEqual(started.returncode, 0, started.stderr)
        os.rename(self.p.path("state", "state.json"), self.p.path("state", "current.json"))  # schema 7 named it so
        state = self.p.read("state", "current.json")
        self.commit()
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.p.version(), "11")
        self.assertEqual(self.p.read("state", "state.json"), state, "0008 leaves the task's state alone; 0009 moves it as it is (R34)")
        self.assertFalse(os.path.exists(self.p.path("state", "current.json")))
        with open(os.path.join(self.p.root, "CLAUDE.md"), "rb") as fh:
            self.assertEqual(fh.read(), self.claude.replace(b"<!-- claude-agentic:", b"<!-- riskrails:"),
                             "only the marker word changes; the project's text is byte-identical")
        with open(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "AGENTS.md"), "rb") as fh:
            self.assertEqual(self.p.read("AGENTS.md"), fh.read(), "the router routes to the riskrails home")
        status = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "status"],
                                env=env, capture_output=True, text=True, check=False)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("mid-build", status.stdout)
        again = self.p.update("--apply")
        self.assertNotIn("schema ", again.stdout)
        self.assertEqual(self.p.update("--check").returncode, 0)

    def test_without_a_task(self):
        self.commit()
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertFalse(os.path.exists(self.p.path("state", "state.json")), "no task, no file is invented")
        self.assertNotIn(b"claude-agentic", open(os.path.join(self.p.root, "CLAUDE.md"), "rb").read())

    def test_rule_markers_keep_their_spacing(self):
        spec = importlib.util.spec_from_file_location("migration_0008_under_test", MIGRATION_0008)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        text = (b"<!--  claude-agentic:rule:payments:start -->\nbody claude-agentic stays\n"
                b"<!-- claude-agentic:rule:payments:end-->\n")
        self.assertEqual(mod.rename_markers(text),
                         b"<!--  riskrails:rule:payments:start -->\nbody claude-agentic stays\n"
                         b"<!-- riskrails:rule:payments:end-->\n")
        self.assertEqual(mod.rename_routes(b"`~/.claude/claude-agentic/ai-path x` and /claude-agentic/aix"),
                         b"`~/.claude/riskrails/ai-path x` and /claude-agentic/aix")


FIXTURE_V8 = os.path.join(ROOT, "tests", "fixtures", "project-update", "schema-v8")
MIGRATION_0009 = os.path.join(ROOT, "skills", "project-update", "migrations", "0009_state_file.py")


class TestMigration0009(unittest.TestCase):
    """R34's contract half: a task in flight moves from current.json to
    state.json, byte for byte, and the readers 3.4b shipped still arm on it."""

    LEGACY = os.path.join(".ai", "state", "current.json")
    NEW = os.path.join(".ai", "state", "state.json")

    def setUp(self):
        self.p = Project()
        # shutil.copy, not copy2: a checkout writes the schema-6 and schema-8 VERSION files in
        # the same second, and with the fixture's mtime and size git's stat cache would take
        # the copied '8' for the committed '6' — 'nothing to commit' on a fresh clone.
        shutil.copytree(os.path.join(FIXTURE_V8, ".ai"), os.path.join(self.p.root, ".ai"), dirs_exist_ok=True,
                        copy_function=shutil.copy)

    def tearDown(self):
        self.p.close()

    def commit(self):
        subprocess.run(GIT + ["-C", self.p.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.p.root, "commit", "-qm", "schema 8"], check=True)

    def start_task(self):
        """A task started with today's state.py, put back under its schema-8 name."""
        env = dict(self.p.env, AI_RUNTIME="claude")
        put(os.path.join(self.p.root, "src", "Clock.php"), "x\n")
        self.commit()
        started = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "start", "--goal", "mid-build",
                                  "--workflow", "feature", "--files", "src/Clock.php", "--tests", "tests/ClockTest.php",
                                  "--declare", "behaviour=0:none", "--declare", "novelty=0:none"],
                                 env=env, capture_output=True, text=True, check=False)
        self.assertEqual(started.returncode, 0, started.stderr)
        os.rename(os.path.join(self.p.root, self.NEW), os.path.join(self.p.root, self.LEGACY))
        self.commit()
        with open(os.path.join(self.p.root, self.LEGACY), "rb") as fh:
            return fh.read()

    def has(self, rel):
        return os.path.exists(os.path.join(self.p.root, rel))

    def test_in_flight_moves_and_is_still_read(self):
        before = self.start_task()
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertFalse(self.has(self.LEGACY), "current.json moved away")
        self.assertEqual(self.p.read("state", "state.json"), before, "the task's bytes are unchanged")
        env = dict(self.p.env, AI_RUNTIME="claude")
        status = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "status"],
                                env=env, capture_output=True, text=True, check=False)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("mid-build", status.stdout)
        self.assertEqual(self.p.update("--check").returncode, 0)

    def test_second_run_is_a_no_op(self):
        self.start_task()
        self.p.update("--apply")
        moved = self.p.read("state", "state.json")
        again = self.p.update("--apply")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertNotIn("schema ", again.stdout)
        self.assertEqual(self.p.read("state", "state.json"), moved)
        self.assertFalse(self.has(self.LEGACY))

    def test_without_a_task(self):
        self.commit()
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertFalse(self.has(self.NEW) or self.has(self.LEGACY), "no task, no file is invented")

    def test_state_json_already_there_is_untouched(self):
        self.commit()
        put(os.path.join(self.p.root, self.NEW), "{\"task_id\": \"T-new\"}\n")
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(self.p.read("state", "state.json"), b"{\"task_id\": \"T-new\"}\n")
        self.assertFalse(self.has(self.LEGACY))

    def test_both_files_is_a_conflict_and_nothing_changes(self):
        legacy = "{\"task_id\": \"T-old\"}\n"
        put(os.path.join(self.p.root, self.LEGACY), legacy)
        put(os.path.join(self.p.root, self.NEW), "{\"task_id\": \"T-new\"}\n")
        self.commit()
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertIn("conflict  .ai/state/current.json", done.stdout)
        self.assertIn("already exists", done.stdout)
        self.assertEqual(self.p.version(), "8", "the schema is held at 8")
        self.assertEqual(self.p.read("state", "state.json"), b"{\"task_id\": \"T-new\"}\n")
        self.assertEqual(self.p.read("state", "current.json"), legacy.encode())

    def test_move_leaves_no_copy_of_the_task_state_in_the_report(self):
        self.start_task()
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        copies = []
        for dirpath, _, names in os.walk(os.path.join(self.p.root, ".ai", "reports")):
            copies += [os.path.join(dirpath, n) for n in names if n in ("current.json", "state.json")]
        self.assertEqual(copies, [], "git-ignored task state is not copied into a tracked report")

    def test_revert_runs_the_real_3_4b_state_py_on_the_moved_task(self):
        self.start_task()
        self.assertEqual(self.p.update("--apply").returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            archive = subprocess.run(["git", "-C", ROOT, "archive", "c361c54", "skills/ai-task"],
                                     capture_output=True, check=True).stdout
            subprocess.run(["tar", "-x", "-C", tmp], input=archive, check=True)
            old = os.path.join(tmp, "skills", "ai-task", "state.py")
            env = dict(self.p.env, AI_RUNTIME="claude")
            status = subprocess.run([sys.executable, "-I", old, "--root", self.p.root, "status"],
                                    env=env, capture_output=True, text=True, check=False)
        self.assertEqual(status.returncode, 0, status.stdout + status.stderr)
        self.assertIn("mid-build", status.stdout)

    def test_revert_check_the_3_4b_readers_arm_on_the_moved_file(self):
        """Reverting to 3.4b after the move: its state.py and its scope guard read
        state.json, so the task in flight is still guarded."""
        self.start_task()
        self.assertEqual(self.p.update("--apply").returncode, 0)
        root = self.p.root
        sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        try:
            import state as state_mod  # pylint: disable=import-outside-toplevel
            from guard_harness import guard, run  # pylint: disable=import-outside-toplevel
        finally:
            del sys.path[:2]
        self.assertEqual(state_mod.state_path(root), os.path.join(root, self.NEW))
        self.assertEqual(state_mod.load(root, claim=False)["goal"], "mid-build")
        outside = {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": root,
                   "tool_input": {"file_path": root + "/src/Elsewhere.php"}}
        inside = dict(outside, tool_input={"file_path": root + "/src/Clock.php"})
        self.assertIn("SCOPE_CHANGE_REQUIRED", run(guard("scope"), outside)[1], "the scope guard arms on state.json")
        self.assertEqual(run(guard("scope"), inside)[1], "")
        with open(os.path.join(ROOT, "hooks", "guard", "paths.py"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("/.ai/state/state.json", text, "the path guard reads state.json first")
        self.assertIn("/.ai/state/current.json", text, "and current.json otherwise")

    def test_migration_declares_the_move(self):
        spec = importlib.util.spec_from_file_location("migration_0009_under_test", MIGRATION_0009)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertEqual(mod.VERSION, 9)
        self.assertEqual(mod.MOVES, [(".ai/state/current.json", ".ai/state/state.json")])


class TestProjectUpdate(unittest.TestCase):  # pylint: disable=too-many-public-methods
    """project-update: a project scaffolded from the oldest shipped templates, then
    edited by hand, is brought up to date without losing an edit."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDownClass ends it
        cls.t = cls.tmp.name
        os.makedirs(os.path.join(cls.t, "home"))
        cls.env = {k: v for k, v in os.environ.items()
                   if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS", "CLAUDE_CONFIG_DIR",
                                "CLAUDE_AGENTIC_TEMPLATES", "CLAUDE_ROUTING_TEMPLATES")
                   and not k.startswith("RISKRAILS_")}
        cls.env.update(HOME=os.path.join(cls.t, "home"), CLAUDE_AGENTIC_SHARED=os.path.join(ROOT, "ai"))
        cls.current = int(subprocess.run(
            [sys.executable, "-I", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import migrations; "
             "print(migrations.CURRENT)", os.path.join(ROOT, "skills", "project-update")],
            env=cls.env, capture_output=True, text=True, check=True).stdout)
        # The shared keys come from the ai/ tree itself, not from a list: those files are
        # no longer scaffolded, and test_migration_0006.py covers a project carrying them.
        cls.shared_keys = sorted("ai-init/.ai/" + os.path.relpath(os.path.join(d, f), os.path.join(ROOT, "ai"))
                                 for d, _, files in os.walk(os.path.join(ROOT, "ai")) for f in files)
        # The oldest shipped templates, built from history.
        cls.old = os.path.join(cls.t, "old")
        for key, versions in read_json(os.path.join(HISTORY, "index.json")).items():
            if key == "ai-init/.ai/VERSION":
                continue   # a project from before schema 1 has no VERSION: that is schema 0
            if key in cls.shared_keys:
                continue   # read from the plugin since 0006, never scaffolded
            name, rel = key.split("/", 1)
            put(os.path.join(cls.old, name, "templates", rel), raw(os.path.join(HISTORY, "blobs", versions[0])), "wb")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    # -- helpers ------------------------------------------------------------

    def run_(self, args, merge=False, unset=(), **extra):
        env = {k: v for k, v in self.env.items() if k not in unset}
        env.update(extra)
        done = subprocess.run(args, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT if merge else subprocess.DEVNULL, text=True, check=False)
        return done.returncode, done.stdout

    def upd(self, d, *args, merge=False, **extra):
        return self.run_([sys.executable, "-I", UPDATE, d] + list(args), merge=merge, **extra)

    def status(self, d, **kw):
        return self.run_([sys.executable, "-I", STATE, "--root", d, "status"], **kw)

    def pty(self, args, unset=(), **extra):
        """The command with a terminal on stdin (util-linux script), stdout and stderr merged,
        \\r stripped; the exit status is the command's. SHELL is pinned because script -c runs it."""
        rc, out = self.run_(["script", "-qec", shlex.join(args), "/dev/null"], unset=unset, SHELL="/bin/bash",
                            **extra)
        return rc, out.replace("\r", "")

    def has_pty(self):
        try:
            return self.pty([sys.executable, "-c", "import os; print(os.isatty(0))"])[1].strip() == "True"
        except OSError:
            return False

    def dir(self, name):
        path = os.path.join(self.t, name)
        os.makedirs(path, exist_ok=True)
        return path

    def tpl(self, name):
        return os.path.join(self.old, name, "templates")

    def routing(self, d, *args, templates=None):
        extra = {"CLAUDE_ROUTING_TEMPLATES": templates} if templates else {}
        self.run_(["bash", HOOK_SCAFFOLD, d] + list(args), **extra)

    def agentic(self, d, *args, templates=None):
        extra = {"CLAUDE_AGENTIC_TEMPLATES": templates} if templates else {}
        self.run_(["bash", SCAFFOLD, d] + list(args), **extra)

    def v0_project(self, name, rt="auto"):
        """A project as it was before .ai/VERSION existed: oldest templates, no VERSION,
        the knowledge base a human wrote, and a task in flight."""
        d = self.dir(name)
        self.agentic(d, "--runtime", rt, templates=self.tpl("ai-init"))
        shutil.copytree(os.path.join(FIX, "schema-v0", ".ai"), os.path.join(d, ".ai"), dirs_exist_ok=True)
        return d

    def v2_project(self, name):
        """A project at schema 2, both runtimes, from the oldest templates: its root
        instruction files still carry the shipped `## SDLC workflow` section."""
        d = self.dir(name)
        self.routing(d, "--runtime", "both", templates=self.tpl("project-init"))
        self.agentic(d, "--runtime", "both", templates=self.tpl("ai-init"))
        shutil.copytree(os.path.join(FIX, "schema-v2", ".ai"), os.path.join(d, ".ai"), dirs_exist_ok=True)
        return d

    def current_project(self, name, *args):
        d = self.dir(name)
        self.routing(d, *args)
        self.agentic(d, *args)
        return d

    def legacy_project(self, name, agents):
        d = self.dir(name)
        os.makedirs(os.path.join(d, ".codex"), exist_ok=True)
        self.routing(d)
        self.agentic(d)
        subprocess.run(["git", "-C", d, "init", "-q"], env=self.env, check=True)
        put(os.path.join(d, "AGENTS.md"), agents)
        return d

    def next_templates(self):
        """The plugin the synthetic migrations belong to: the template moves with the file
        (R12 forbids shipping a template at a path a migration moved away) and gains a
        line, so the merge at the new path has something to merge."""
        nxt = os.path.join(self.t, "next-templates")
        if not os.path.isdir(nxt):
            shutil.copytree(TEMPLATES, nxt, symlinks=True)
            policies = os.path.join(nxt, ".ai", "policies")
            os.rename(os.path.join(policies, "coding.md"), os.path.join(policies, "code-style.md"))
            path = os.path.join(policies, "code-style.md")
            put(path, insert_line(text_of(path), 2, "A line the next plugin version inserted near the top.", after=False))
        return nxt

    def apply_all(self, d):
        """--apply, then the human's --confirm-delete: a project that holds the retired tier policy
        (migration 0011) reaches the current schema only through both."""
        self.upd(d, "--apply")
        return self.upd(d, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1")

    def version(self, d):
        return text_of(os.path.join(d, ".ai", "VERSION")).strip()

    def cur(self):
        return str(self.current)

    # -- the cases ----------------------------------------------------------

    def test_history_covers_every_template(self):
        """the shipped history covers every current template"""
        index = read_json(os.path.join(HISTORY, "index.json"))
        stale, shared = [], set()
        # The shared tree ai/ is recorded under the ai-init/.ai/ keys it shipped under,
        # by hash only: a shared copy is classified, never merged, so it needs no blob.
        for name, base in (("ai-init", TEMPLATES),
                           ("project-init", os.path.join(ROOT, "skills", "project-init", "templates")),
                           ("ai-init/.ai", os.path.join(ROOT, "ai"))):
            for d, _, files in os.walk(base):
                for f in files:
                    p = os.path.join(d, f)
                    key = "%s/%s" % (name, os.path.relpath(p, base))
                    if name == "ai-init/.ai":
                        shared.add(key)
                    h = sha256(p)
                    if h not in index.get(key, []) or (name != "ai-init/.ai" and
                                                       not os.path.exists(os.path.join(HISTORY, "blobs", h))):
                        stale.append(key)
        owned = {h for k, v in index.items() if k not in shared for h in v}
        stale += ["blob only a shared key references: " + b
                  for b in sorted(set(os.listdir(os.path.join(HISTORY, "blobs"))) - owned)]
        self.assertEqual(stale, [], "every template version is in history/ (else run tools/build-template-history.py)")
        self.assertGreaterEqual(len(self.shared_keys), 29, "the shared keys are read from ai/")

    def test_oldest_project_is_brought_up_to_date(self):
        """build the oldest shipped templates from history"""
        p = self.dir("proj")
        self.routing(p, templates=self.tpl("project-init"))
        self.agentic(p, templates=self.tpl("ai-init"))
        subprocess.run(["git", "-C", p, "init", "-q"], env=self.env, check=True)
        rt = os.path.join(p, ".ai", "policies", "risk-tiers.json")
        md = os.path.join(p, ".ai", "policies", "risk-tiers.md")
        self.assertNotIn("pipeline_profile", read_json(rt), "the old project has no pipeline_profile yet")

        # Hand edits a real project would have.
        put(os.path.join(p, ".ai", "policies", "testing.md"), "\nphpunit: vendor/bin/phpunit\n", "a")
        # T0.examples is the one tier key identical in the oldest template and the current one,
        # so this edit merges cleanly instead of conflicting.
        doc = read_json(rt)
        doc["tiers"]["T0"]["examples"].append("Fiscal printer bridge")
        put_json(rt, doc)
        edited_tiers = (raw(rt), raw(md))
        # Line 4 differs between the oldest state README and the current one, so this edit conflicts.
        replace_line(os.path.join(p, ".ai", "state", "README.md"), 4, "my own wording of who writes current.json")
        put(os.path.join(p, ".ai", "project", "overview.md"), "the overview a human wrote\n")
        put(os.path.join(p, "CLAUDE.md"), "\n# my notes\nkeep me\n", "a")
        os.remove(os.path.join(p, ".ai", "policies", "security.md"))

        # dry run
        before = tree_sum(p)
        rc, out = self.upd(p, merge=True)
        self.assertEqual(rc, 0, "the dry run exits 0\n" + out)
        self.assertEqual(tree_sum(p), before, "the dry run writes nothing")
        self.assertTrue(has(r"policy .*\+ batch$", out), "policy changes are listed for confirmation")
        self.assertEqual(len(re.findall(r"(?m)^  delete\?   .ai/policies/risk-tiers\.(json|md) .*\[0011\]", out)), 2,
                         "migration 0011 proposes the retired tier policy for deletion\n" + out)
        rc, out = self.upd(p, "--check")
        self.assertEqual(rc, 1, "--check exits 1 while an update is pending")
        # The exact shape /ai-status reads: one line, the reasons, the command (R21 keeps it byte-identical).
        # One manual merge: the state README edit. weight.json, which carries the T0 example migration 0007
        # converts from risk-tiers.json, merges: three_way drops the history versions equal to the current
        # template, and since the batch section was added the history holds a shipped version that differs
        # (the one before it), which becomes the base; against it the example is the project's only edit.
        # It conflicted while no such base existed.
        self.assertTrue(len(out.splitlines()) == 1 and has(
            r"^project is behind the installed plugin: schema 0 -> [0-9]+, [0-9]+ file\(s\) to update, "
            r"1 need a manual merge, 2 deletion\(s\) a human must confirm, the schema stays at 0 until they are "
            r"settled — run /rr-setup --update$", out), "the plain --check line keeps its exact shape\n" + out)

        # apply
        _, out = self.upd(p, "--apply", merge=True)
        self.assertEqual((raw(rt), raw(md)), edited_tiers,
                         "the retired tier policy is no longer merged: it waits, as the project had it, for a human")
        testing = text_of(os.path.join(p, ".ai", "policies", "testing.md"))
        self.assertTrue(has("^## Verification", testing) and "phpunit: vendor/bin/phpunit" in testing,
                        "an edited markdown policy is merged: new section and the edit")
        self.assertIn("my own wording", text_of(os.path.join(p, ".ai", "state", "README.md")),
                      "a real conflict leaves the project file alone")
        self.assertEqual(raw(os.path.join(p, ".ai", "local", "plugin-update", ".ai", "state", "README.md")),
                         raw(os.path.join(TEMPLATES, ".ai", "state", "README.md")),
                         "and puts the plugin's version in the local copy")
        self.assertEqual(subprocess.run(["git", "-C", p, "check-ignore", "-q",
                                         ".ai/local/plugin-update/.ai/state/README.md"], env=self.env,
                                        check=False).returncode, 0,
                         "the conflict copy is git-ignored")
        self.assertEqual(raw(os.path.join(p, ".ai", "policies", "safety.md")),
                         raw(os.path.join(TEMPLATES, ".ai", "policies", "safety.md")), "an untouched file is replaced")
        self.assertEqual(text_of(os.path.join(p, ".ai", "project", "overview.md")).rstrip("\n"),
                         "the overview a human wrote", ".ai/project/ is never updated")
        self.assertTrue(os.path.isfile(os.path.join(p, ".ai", "policies", "security.md")),
                        "a missing template is created")
        claude = text_of(os.path.join(p, "CLAUDE.md"))
        self.assertTrue("keep me" in claude and ".ai/state/handoff.md" in claude,
                        "the CLAUDE.md block is updated and the rest of the file kept")
        self.assertEqual(grep("riskrails:start", claude), 1, "one managed block remains")
        self.assertIn("verify_command is empty", out, "an empty verify_command is flagged")

        # idempotent
        snap = tree_sum(p)
        _, out = self.upd(p, "--apply", merge=True)
        self.assertTrue(has("^0 automatic, 1 conflict\\(s\\), 2 deletion", out),
                        "a second run has nothing automatic left\n" + out)
        self.assertEqual(tree_sum(p), snap, "a second run changes nothing")
        rc, out = self.upd(p, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, "a human confirms the deletions\n" + out)
        self.assertEqual(self.version(p), self.cur(), "and the schema moves on")
        self.assertFalse(os.path.exists(rt) or os.path.exists(md), "the retired tier policy is gone")
        rc, out = self.upd(p, "--check")
        self.assertEqual(rc, 0, "--check exits 0 once only a hand-merge choice remains")
        self.assertEqual(out.rstrip("\n"), "project matches the installed plugin (1 file(s) differ by hand-merge choice)",
                         "the plain --check line is byte-identical")

    def test_codex_project(self):
        """a Codex project gets its AGENTS.md block and .codex/ layer, and no stray CLAUDE.md"""
        p4 = self.dir("proj4")
        self.routing(p4, "--runtime", "codex", templates=self.tpl("project-init"))
        self.agentic(p4, "--runtime", "codex", templates=self.tpl("ai-init"))
        self.assertTrue(os.path.lexists(os.path.join(p4, "AGENTS.md"))
                        and not os.path.lexists(os.path.join(p4, "CLAUDE.md")), "the fixture is a Codex-only project")
        put(os.path.join(p4, "AGENTS.md"), "\n# my codex notes\nkeep me\n", "a")
        os.remove(os.path.join(p4, ".codex", "memory", "README.md"))
        _, out = self.upd(p4, "--apply", merge=True)
        agents = text_of(os.path.join(p4, "AGENTS.md"))
        self.assertTrue("keep me" in agents and "riskrails:start" in agents,
                        "the AGENTS.md block is managed and the rest of the file kept\n" + out)
        self.assertEqual(grep("riskrails:start", agents), 1, "one AGENTS.md block remains")
        self.assertTrue(not os.path.lexists(os.path.join(p4, "CLAUDE.md"))
                        and not os.path.isdir(os.path.join(p4, ".claude")), "no Claude layer is added to a Codex project")
        self.assertTrue(os.path.isfile(os.path.join(p4, ".codex", "memory", "README.md")),
                        "a missing .codex/memory/README.md is recreated")
        self.assertTrue(os.path.isfile(os.path.join(p4, ".codex", "config.toml")), ".codex/config.toml is left in place")
        self.assertIn(".codex/memory/local/", text_of(os.path.join(p4, ".gitignore")),
                      "the Codex ignore entry is appended")
        self.upd(p4, "--apply")
        _, out = self.upd(p4)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a second run on the Codex project is a no-op\n" + out)

    def test_dual_and_four_runtime_projects(self):
        """a dual-runtime project keeps both instruction files in step"""
        p5 = self.dir("proj5")
        self.agentic(p5, "--runtime", "both", templates=self.tpl("ai-init"))
        self.upd(p5, "--apply")
        self.assertTrue(".ai/state/handoff.md" in text_of(os.path.join(p5, "CLAUDE.md"))
                        and "riskrails:start" in text_of(os.path.join(p5, "AGENTS.md")),
                        "both blocks are brought up to date over the one .ai/ tree")

        # a project that also declares Gemini and Junie gets their blocks too
        p6 = self.dir("proj6")
        self.agentic(p6, "--runtime", "claude,codex,gemini,junie")
        for f in ("GEMINI.md", ".junie/guidelines.md"):
            with self.subTest(Template("$f carries the managed block").substitute(f=f)):
                self.assertIn("riskrails:start", text_of(os.path.join(p6, f)))
        self.assertIn(".ai/policies/safety.md", text_of(os.path.join(p6, "GEMINI.md")),
                      "the Gemini block routes to the policies like every other runtime")
        self.upd(p6, "--apply")
        _, out = self.upd(p6)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a four-runtime project is idempotent\n" + out)
        # an edited block is the user's, in a fourth runtime exactly as in the first
        put(os.path.join(p6, "GEMINI.md"), "\n<!-- riskrails:start -->\nmy own text\n<!-- riskrails:end -->\n")
        _, out = self.upd(p6)
        self.assertIn("conflict  GEMINI.md", out, "an edited Gemini block is a conflict, never overwritten")

    def test_up_to_date_project_and_non_project(self):
        """an up-to-date project and a non-project"""
        p3 = self.dir("proj3")
        self.routing(p3, templates=os.path.join(ROOT, "skills", "project-init", "templates"))
        self.agentic(p3, templates=TEMPLATES)
        _, out = self.upd(p3)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a freshly scaffolded project is up to date\n" + out)
        self.assertEqual(self.upd(self.dir("empty"))[0], 2, "a repository without .ai/ or docs/sdlc/ is refused")

    def test_schema_version(self):
        """a project carries a schema version"""
        cur = self.cur()
        s0 = self.v0_project("schema0")
        self.assertFalse(os.path.lexists(os.path.join(s0, ".ai", "VERSION")),
                         "a project from before the schema has no .ai/VERSION")
        _, out = self.upd(s0)
        self.assertTrue(has("^  schema    0 -> " + cur, out), "the dry run says which schema step is pending\n" + out)
        rc, out = self.upd(s0, "--check")
        self.assertTrue(rc == 1 and "schema 0 -> " + cur in out, "--check exits 1 and names the schema step\n" + out)
        before = tree_sum(s0)
        self.upd(s0)
        self.assertEqual(tree_sum(s0), before, "the migration dry run writes nothing")
        self.apply_all(s0)
        self.assertEqual(self.version(s0), cur, "the apply records the schema version")
        _, out = self.upd(s0)
        self.assertTrue(has("^0 automatic", out), "a second run has nothing left to migrate\n" + out)
        rc, out = self.upd(s0, "--check")
        self.assertEqual(rc, 0, "--check exits 0 once the schema is current")
        self.assertEqual(out.rstrip("\n"), "project matches the installed plugin", "the plain current line is byte-identical")

    def test_task_in_flight_reaches_schema_2(self):
        """a task in flight survives the journey to schema 2 (R14)"""
        cur = self.cur()
        s7 = self.dir("schema1")
        self.agentic(s7, templates=self.tpl("ai-init"))
        shutil.copytree(os.path.join(FIX, "schema-v1", ".ai"), os.path.join(s7, ".ai"), dirs_exist_ok=True)
        # What the old surface's `quick` wrote at schema 1, as a literal: the command
        # that made it was removed in redesign 2.6.
        t7 = "T-2026-09-20-001"
        os.makedirs(os.path.join(s7, ".ai", "reports", t7), exist_ok=True)
        current = os.path.join(s7, ".ai", "state", "current.json")
        put(current, json.dumps({
            "task_id": t7, "goal": "add the per-line fee", "workflow": "feature", "current_stage": "implementation",
            "risk_tier": "T2", "completed_steps": [], "test_status": "not_run", "review_status": "not_started",
            "approved_plan": {"ref": "inline", "current_step_id": "1",
                              "steps": [{"step_id": "1", "description": "add the per-line fee",
                                         "allowed_files": ["src/Fee.php"]}]},
            "human_approval": {"required": False, "granted": False, "granted_by": None, "granted_at": None},
            "history": [{"at": "2026-09-20T10:00:00Z", "event": "task_started", "detail": "add the per-line fee"},
                        {"at": "2026-09-20T10:00:00Z", "event": "stage", "detail": "intake -> discovery"},
                        {"at": "2026-09-20T10:00:01Z", "event": "risk_classified", "detail": "T2: quick"},
                        {"at": "2026-09-20T10:00:01Z", "event": "stage", "detail": "discovery -> implementation: quick"},
                        {"at": "2026-09-20T10:00:01Z", "event": "plan_approved", "detail": "inline"},
                        {"at": "2026-09-20T10:00:01Z", "event": "step_started", "detail": "1: quick"}]}) + "\n")
        put(os.path.join(s7, ".ai", "VERSION"), "1\n")

        self.assertIn("old surface", self.status(s7, unset=("CLAUDECODE",))[1],
                      "the v1 task answers state.py status before the migration")
        hist = len(read_json(current)["history"])
        _, out = self.upd(s7)
        self.assertTrue(has("^  schema    1 -> " + cur, out), "the dry run names the schema step\n" + out)
        journal = os.path.join(s7, ".ai", "reports", t7, "events.jsonl")
        self.assertFalse(os.path.lexists(journal), "and writes no journal yet")
        self.apply_all(s7)
        self.assertEqual(self.version(s7), cur, "the apply reaches the current schema")
        state = read_json(current)
        self.assertTrue(state["current_stage"] == "implementation" and self.status(s7, unset=("CLAUDECODE",))[0] == 0,
                        "and the task still answers afterwards")
        self.assertIn(t7, str((state.get("questions") or {}).get("file")), "with the schema-2 keys now on disk")
        self.assertTrue(all(k in state["human_approval"] for k in ("requested_at", "gate_id", "unattended")),
                        "including the gate's own")

        self.assertTrue(os.path.isfile(journal), "the journal is backfilled")
        # The migration adds one schema_migrated entry to history as it patches the state.
        n = raw(journal).count(b"\n")
        self.assertEqual(n, hist + 1, JOURNAL_CASE.split("$", 1)[0] + str(n) + ")")
        events = [json.loads(line) for line in text_of(journal).splitlines()]
        self.assertTrue(all(e["data"].get("backfilled") is True and e["data"].get("legacy_event") is not None
                            for e in events), "every line says it was reconstructed, and from what")
        self.assertTrue(all(e.get("actor") == "migration" and e.get("runtime") == "unknown" for e in events),
                        "and that a migration wrote it, from no runtime")
        stage = [e for e in events if e["event"] == "stage_started"][0]
        self.assertEqual(stage["data"].get("to"), "discovery", "a stage line keeps both ends of the move")
        tier = [e for e in events if e["event"] == "tier_set"][0]
        self.assertTrue(tier["data"].get("tier") == "T2" and tier["data"].get("from") is None,
                        "a tier line records what it can, and leaves what it cannot as null")
        with open(journal, encoding="utf-8") as fh:
            parsed = [json.loads(line) for line in fh]
        self.assertEqual(len(parsed), n, "and every line of it parses back")

        _, out = self.upd(s7)
        self.assertTrue(has("^0 automatic", out), "a second run has nothing to do\n" + out)
        before = raw(journal)
        self.upd(s7, "--apply")
        self.assertEqual(raw(journal), before, "and never appends to the journal twice")
        # Since redesign 2.6 a task the old surface started is read or abandoned, never
        # worked: the commands that would carry it on are gone.
        rc, out = self.run_([sys.executable, "-I", STATE, "--root", s7, "verify", "--scope", "suite"], merge=True,
                            unset=("CLAUDECODE",))
        self.assertTrue(rc == 1 and "close --abandon" in out, "the migrated task names its way out\n" + out)

    def test_schema_3_takes_the_pipeline_text_out(self):
        """schema 3: the pipeline text leaves the instruction files, the human's text stays (R12/R13)"""
        s8 = self.v2_project("schema2")
        self.assertTrue(has("^## SDLC workflow", text_of(os.path.join(s8, "CLAUDE.md")))
                        and has("^## SDLC workflow", text_of(os.path.join(s8, "AGENTS.md"))),
                        "the schema-2 fixture carries the shipped section in both files")
        put(os.path.join(s8, "CLAUDE.md"), "\n# my notes\nkeep me\n", "a")
        # A line rewritten inside the managed block, where the plugin also changed it.
        data = raw(os.path.join(s8, "AGENTS.md"))
        start = data.find(b"<!-- claude-agentic:start -->")
        line2 = data.find(b"\n", data.find(b"\n", start) + 1) + 1
        line3 = data.find(b"\n", line2) + 1
        put(os.path.join(s8, "AGENTS.md"), data[:line2] + b"my own rule, right inside the block\n" + data[line3:], "wb")
        put(os.path.join(s8, "GEMINI.md"), "# GEMINI\n\nmy own instructions\n")          # a third runtime, no block yet
        put(os.path.join(s8, ".ai", "AGENTS.md"), "\n## my routing note\nalways ask me first\n", "a")

        before = tree_sum(s8)
        _, out = self.upd(s8)
        self.assertTrue(has(r"^  update    CLAUDE.md .*\[0003\] SDLC workflow section removed "
                            r"\(now in the managed block\)", out), "the dry run names the section it will take out\n" + out)
        self.assertIn("AGENTS.md: the managed block was edited here", out,
                      "and hints that an edited block cannot be replaced")
        self.assertNotIn("CLAUDE.md: the managed block was edited here", out,
                         "a pristine block under the pre-3.4b markers is the shipped one (review M1)")
        self.assertEqual(tree_sum(s8), before, "the dry run writes nothing")

        self.apply_all(s8)
        claude = text_of(os.path.join(s8, "CLAUDE.md"))
        self.assertNotIn("SDLC workflow", claude, "the shipped section is removed")
        self.assertTrue("keep me" in claude and grep("riskrails:start", claude) == 1,
                        "and the human's own lines and the one block are kept")
        self.assertIn("SDLC workflow", text_of(only(os.path.join(s8, ".ai", "reports", "project-update-*", "original",
                                                                 "CLAUDE.md"))),
                      "the file the migration rewrote is kept under .ai/reports/")
        agents = text_of(os.path.join(s8, "AGENTS.md"))
        self.assertIn("my own rule, right inside the block", agents, "an edited managed block is never overwritten")
        self.assertEqual(raw(os.path.join(s8, ".ai", "local", "plugin-update", "AGENTS.md")), raw(BLOCK),
                         "and the plugin's stub waits in the local copy")
        self.assertNotIn("SDLC workflow", agents,
                         "the section leaves the file whose block was edited, which is a separate decision")
        gemini = text_of(os.path.join(s8, "GEMINI.md"))
        self.assertTrue("riskrails:start" in gemini and "my own instructions" in gemini,
                        "a third runtime's file gains the block without losing its text")
        self.assertEqual(self.version(s8), self.cur(),
                         Template("the schema reaches $CURRENT: 0003 holds it for nothing").substitute(CURRENT=self.cur()))

        _, out = self.upd(s8)
        # Two hand-merge choices: the edited managed block, and the router — edited on
        # the oldest shipped version, so the plugin's later router changes really
        # collide with the human's note (T-2026-10-13-004 re-review: not silenced).
        self.assertTrue(has("^0 automatic, 2 conflict", out) and has(r"^  conflict  *\.ai/AGENTS\.md", out),
                        "a second run has only the two hand-merge choices left, the router among them\n" + out)
        router = text_of(os.path.join(s8, ".ai", "AGENTS.md"))
        self.assertTrue(grep("^## Shared files$", router) == 1 and has("^always ask me first$", router),
                        "the router keeps the human's note and names the shared files once")
        self.assertEqual(self.upd(s8, "--check")[0], 0, "--check exits 0 once only a hand-merge choice remains")

    def test_edited_section_is_only_hinted_at(self):
        """an edited section is the human's, and is only ever hinted at"""
        s9 = self.v2_project("schema2edited")
        claude = os.path.join(s9, "CLAUDE.md")
        put(claude, re.sub(r"(?m)^`/ai-task <request>` is the default route for a change: it classifies the risk,$",
                           "`/ai-task <request>` is the default route here, and we always open an ADR first,",
                           text_of(claude)))
        snap = raw(claude)
        _, out = self.upd(s9, "--apply", merge=True)
        self.assertTrue(raw(claude) != snap and "we always open an ADR first" in text_of(claude),
                        "an edited section survives the migration\n" + out)
        self.assertIn("CLAUDE.md: the SDLC workflow section was edited", out,
                      "and the human is told it is now theirs to keep")
        self.assertFalse(has(r"^  update    CLAUDE.md .*\[0003\]", out), "0003 plans no rewrite it cannot match verbatim")
        self.upd(s9, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1")   # 0011's retired tier policy
        self.assertEqual(self.version(s9), self.cur(), "and the schema still advances")

    def test_migrations_name_no_runtime(self):
        """the migration says nothing about which runtime a project uses"""
        migrations = os.path.join(ROOT, "skills", "project-update", "migrations")
        for name, label in (("0002_task_journal.py", "0002 names no runtime"),
                            ("0004_deterministic_gates.py", "0004 names no runtime"),
                            ("0005_runtimes_and_plans.py", "0005 names no runtime")):
            with self.subTest(label):
                self.assertIsNone(re.search(r"claude|codex", text_of(os.path.join(migrations, name)), re.I))
        # claude-agentic is the plugin's old name (0008 renames it), not a runtime.
        branching = [f for f in glob.glob(os.path.join(migrations, "[0-9]*.py"))
                     if re.search(r"claude(?!-agentic)|codex", text_of(f))]
        self.assertEqual(branching, [], "no migration branches on the runtime")

    def test_sdlc_only_project(self):
        """a docs/sdlc-only project has no schema and runs no migration"""
        s6 = self.dir("sdlconly")
        self.routing(s6, templates=self.tpl("project-init"))
        _, out = self.upd(s6)
        self.assertFalse(has("schema|VERSION", out), "no schema for a docs/sdlc-only project\n" + out)
        rc, out = self.upd(s6, merge=True, CLAUDE_AGENTIC_MIGRATIONS=os.path.join(FIX, "migrations-broken"))
        self.assertEqual(rc, 0, "and a broken registry cannot break it\n" + out)

    def test_unusable_version_stops_the_run(self):
        """an unusable .ai/VERSION stops the run, with a reason, having written nothing"""
        s1 = self.v0_project("schemabad")
        for bad in (str(self.current + 1), "abc", ""):
            put(os.path.join(s1, ".ai", "VERSION"), bad + "\n")
            snap = tree_sum(s1)
            rc, out = self.upd(s1, "--apply", merge=True)
            crc, chk = self.upd(s1, "--check")
            with self.subTest(Template("VERSION '$bad' exits 2 and --check says why").substitute(bad=bad)):
                self.assertTrue(rc == 2 and crc == 2 and chk.strip() and snap == tree_sum(s1), out + " / " + chk)

    def test_registry_is_ordered(self):
        """the migration registry is ordered, and a broken one is refused"""
        s2 = self.v0_project("schemabroken")
        rc, out = self.upd(s2, merge=True, CLAUDE_AGENTIC_MIGRATIONS=os.path.join(FIX, "migrations-broken"))
        self.assertTrue(rc == 2 and "0002" in out, "a gap in the migrations exits 2 and names it\n" + out)
        rc, out = self.run_([sys.executable, "-I", "-c", CONTIGUOUS, ROOT], merge=True)
        self.assertEqual(rc, 0, "the shipped migrations are contiguous and their renames acyclic\n" + out)

    def test_migration_breaking_the_rules_is_refused(self):
        """a migration that breaks the rules is refused before anything is written"""
        s5 = self.v0_project("schemarules")
        snap = tree_sum(s5)
        # The registry must reject the MOVES cases itself, before any migration runs: the
        # message starts with the file name. A downstream refusal would not protect a
        # project whose files the MOVES pair names.
        for fixture, says, rule in (
                ("migrations-invalid", "0001_mismatch.py: VERSION is 2",
                 "a VERSION that disagrees with the file name is refused"),
                ("migrations-badmoves", "0001_badpath.py: MOVES path",
                 "a MOVES pair leaving the project is refused by the registry"),
                ("migrations-dupmove", "0002_second.py: MOVES destination",
                 "two moves onto one destination are refused by the registry"),
                ("migrations-undeclared", "is not in MOVES", "a move the module did not declare is refused"),
                ("migrations-escape", "not a normalised project",
                 "an operation on a path outside the project is refused"),
                ("migrations-bad-content", "must be bytes", "content that is not bytes is refused")):
            rc, out = self.upd(s5, "--apply", merge=True, CLAUDE_AGENTIC_MIGRATIONS=os.path.join(FIX, fixture))
            with self.subTest(rule, case=CHECK_REFUSED_CASE):
                self.assertTrue(rc == 2 and has(says, out) and snap == tree_sum(s5), "rc=%d %s" % (rc, out))
        self.assertFalse(os.path.lexists(os.path.join(self.t, "outside-the-project.md")),
                         "and nothing was written outside the project")

    def test_migrations_run_before_the_merge(self):  # pylint: disable=too-many-statements
        """migrations run before the merge, and every operation is listed once"""
        s3 = self.v0_project("schemaops")
        put(os.path.join(s3, ".ai", "policies", "coding.md"), "\n## My own rule\nalways reproduce the bug first\n", "a")
        # A task in flight as the old surface's `quick` left it (removed in redesign 2.6).
        current = os.path.join(s3, ".ai", "state", "current.json")
        put(current, json.dumps({
            "task_id": "T-2026-09-20-002", "goal": "a task in flight", "workflow": "feature",
            "current_stage": "implementation", "risk_tier": "T2", "completed_steps": [],
            "approved_plan": {"ref": "inline", "current_step_id": "1",
                              "steps": [{"step_id": "1", "description": "a task in flight",
                                         "allowed_files": [".ai/policies/coding.md"]}]},
            "history": [{"at": "2026-09-20T10:00:00Z", "event": "task_started", "detail": "a task in flight"}]}) + "\n")
        synth = {"CLAUDE_AGENTIC_MIGRATIONS": SYNTH, "CLAUDE_AGENTIC_TEMPLATES": self.next_templates()}
        _, out = self.upd(s3, **synth)
        self.assertTrue(has("^  schema    0 -> 3 ", out), "the schema line counts every pending migration\n" + out)
        self.assertEqual(grep(r"^  move      .ai/policies/coding.md -> .ai/policies/code-style.md  \[0002\]", out), 1,
                         "a move is listed once, with its source and its migration")
        self.assertNotIn("still-not-there", out, "a move whose source is absent is skipped")
        self.assertTrue(has("^  merge     .ai/policies/code-style.md .*your edits kept", out),
                        "the template history follows the move: the file merges at its new path")
        self.assertTrue(has(r"^  delete\?   .ai/legacy-notes.md .*needs --apply --confirm-delete NAME", out),
                        "a deletion is proposed, not performed")
        self.assertTrue(has(r"policy .*~ schema_probe|policy .*\+ schema_probe", out),
                        "a migration's policy edit is listed for confirmation")
        self.assertIn("deletion(s) awaiting --confirm-delete", out, "the summary counts what is waiting for a human")
        self.assertIn("a task is in flight while the schema changes", out, "a task in flight is flagged")
        first = next((l for l in out.splitlines() if re.search(r"^  (create|move|update|delete\?)", l)), "")
        self.assertIn("[000", first, "the migrations are planned before the template merge")

        # the apply keeps the edit at the new path, the original, and the task
        self.upd(s3, "--apply", **synth)
        style = text_of(os.path.join(s3, ".ai", "policies", "code-style.md"))
        self.assertIn("always reproduce the bug first", style, "an edit made at the old path survives the move")
        self.assertIn("A line the next plugin version inserted near the top", style,
                      "and the new template's change arrives with it")
        self.assertFalse(os.path.lexists(os.path.join(s3, ".ai", "policies", "coding.md")), "and the old path is gone")
        reports = os.path.join(s3, ".ai", "reports", "project-update-*")
        self.assertTrue(os.path.isfile(only(os.path.join(reports, "original", ".ai", "policies", "coding.md"))),
                        "the original is kept under .ai/reports/")
        self.assertEqual(text_of(os.path.join(s3, ".ai", "project", "schema-note.md")).rstrip("\n"),
                         "added by migration 0001", "create adds a file once")
        self.assertEqual(read_json(os.path.join(s3, ".ai", "policies", "risk-tiers.json")).get("schema_probe"), "0003",
                         "a policy edit is applied")
        testing = os.path.join(s3, ".ai", "policies", "testing.md")
        self.assertIn("added by migration 0003", text_of(testing), "a text edit is applied")
        self.upd(s3, "--apply", **synth)   # plan() runs again while the schema is held
        self.assertEqual(grep("added by migration 0003", text_of(testing)), 1,
                         "an idempotent edit does not apply twice when the run repeats")
        legacy_notes = os.path.join(s3, ".ai", "legacy-notes.md")
        self.assertTrue(os.path.isfile(legacy_notes), "the proposed deletion did not happen")
        self.assertFalse(os.path.lexists(os.path.join(s3, ".ai", "VERSION")),
                         "and the schema is held until the deletion is settled")
        rc, out = self.upd(s3, "--check", **synth)
        self.assertTrue(rc == 1 and "the schema stays at 0" in out,
                        "--check reports a held schema instead of calling the project current\n" + out)
        state = read_json(current)
        self.assertEqual(state["approved_plan"]["steps"][0]["allowed_files"][0], ".ai/policies/code-style.md",
                         "the task in flight follows the migration")
        self.assertEqual(state["history"][-1]["event"], "schema_migrated", "and the state records why")
        self.assertIn("old surface", self.status(s3, **synth)[1], "state.py still reads the migrated state")
        self.assertEqual(text_of(os.path.join(s3, ".ai", "project", "overview.md")).split("\n")[0], "# Overview",
                         ".ai/project/ is left alone by a migration run")

        # a human confirms the deletion, and only then is it performed
        self.assertEqual(self.upd(s3, "--confirm-delete", "tester", **synth)[0], 2,
                         "--confirm-delete without --apply is refused")
        self.assertEqual(self.upd(s3, "--apply", "--confirm-delete", "", **synth)[0], 2,
                         "an empty confirmation name is refused")
        rc, out = self.upd(s3, "--apply", "--confirm-delete", "tester", **synth)
        self.assertEqual(rc, 5, "--confirm-delete without a human present is refused (exit 5)\n" + out)
        self.assertEqual(out.split("\n")[0].split(":")[0], "ADOPT_REFUSED", "and says so on the first stdout line")
        self.assertTrue(os.path.lexists(legacy_notes), "and the file is still there")
        with self.subTest("the F3 terminal cases"):
            if not self.has_pty():
                self.skipTest("no pty here (script -qec gives no terminal): the F3 terminal cases did not run")
            tty = os.path.join(self.t, "schemaops-tty")
            shutil.copytree(s3, tty, symlinks=True)
            rc, out = self.pty(["env", "CLAUDECODE=1", sys.executable, "-I", UPDATE, s3, "--apply", "--confirm-delete",
                                "tester"], unset=NOMARK, **synth)
            self.assertTrue(rc == 5 and os.path.lexists(legacy_notes) and "CLAUDECODE" in out,
                            "CLAUDECODE=1 with a terminal: exit 5, names the marker, the file stays")
            rc, out = self.pty([sys.executable, "-I", UPDATE, tty, "--apply", "--confirm-delete", "tester"],
                               unset=NOMARK, **synth)
            rec = os.path.join(tty, ".ai", "reports", "project-update-*", "migration.json")
            self.assertTrue(rc == 0 and not os.path.lexists(os.path.join(tty, ".ai", "legacy-notes.md"))
                            and read_json(only(rec))["deletions"][0]["via"] == "terminal",
                            "a terminal and no marker: deleted, migration.json says via: terminal")
        # The launcher's declaration, on this command only: no terminal here or in CI.
        self.upd(s3, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1", **synth)
        self.assertFalse(os.path.lexists(legacy_notes), "the confirmed deletion is performed")
        self.assertTrue(os.path.isfile(only(os.path.join(reports, "original", ".ai", "legacy-notes.md"))),
                        "its original is kept too")
        rec = read_json(only(os.path.join(reports, "migration.json")))
        self.assertEqual(rec["deletions"][0]["confirmed_by"], "tester", "migration.json records who confirmed it")
        self.assertEqual(rec["deletions"][0]["via"], "unattended", "and why the gate passed: via unattended")
        self.assertEqual(str(rec["to"]), self.version(s3), "and the version the project actually reached")
        _, out = self.upd(s3, **synth)
        self.assertTrue(has("^0 automatic", out), "a second run after the migrations is a no-op\n" + out)

    def test_symlinked_target_aborts_the_apply(self):
        """a target that is not a regular file aborts the apply"""
        s4 = self.v0_project("schemalink")
        testing = os.path.join(s4, ".ai", "policies", "testing.md")
        os.remove(testing)
        os.symlink(os.path.join(self.t, "elsewhere"), testing)
        rc, out = self.upd(s4, "--apply", merge=True)
        self.assertTrue(rc == 3 and not os.path.lexists(os.path.join(self.t, "elsewhere")),
                        "a symlinked target exits 3 and is not written through\n" + out)
        self.assertIn("nothing after it was written; run the dry run again", out, "and the abort says what to do")

    def test_both_runtimes_reach_the_same_schema(self):
        """both runtimes reach the same schema"""
        for rt in ("claude", "codex", "both"):
            d = self.v0_project("schema-" + rt, rt)
            self.apply_all(d)
            with self.subTest(Template("Claude-only, Codex-only and dual-runtime projects all reach schema $CURRENT")
                              .substitute(CURRENT=self.cur()), runtime=rt):
                self.assertEqual(self.version(d), self.cur())

    def test_rendered_rules(self):  # pylint: disable=too-many-statements
        """a rendered rule whose source is gone waits for a human, like any deletion (R9)"""
        rd = self.current_project("rules-gate", "--runtime", "claude")
        shutil.copytree(os.path.join(ROOT, "tests", "fixtures", "instructions", "rules-project", ".ai"),
                        os.path.join(rd, ".ai"), dirs_exist_ok=True)
        os.makedirs(os.path.join(rd, "src", "Payment"))
        os.makedirs(os.path.join(rd, "tests", "Payment"))
        self.assertEqual(self.upd(rd, "--apply")[0], 0, "the rules could not be rendered")
        payment_md = os.path.join(rd, "src", "Payment", "CLAUDE.md")
        put(payment_md, "\n# mine\nkeep me\n", "a")
        os.remove(os.path.join(rd, ".ai", "rules", "payment.md"))
        _, out = self.upd(rd, merge=True)
        self.assertTrue(has(r"delete\? *.claude/rules/payment.md", out),
                        "the path-scoped copy is proposed, not deleted\n" + out)
        self.assertIn("needs --apply --confirm-delete NAME", out, "and says how a human confirms it")
        self.upd(rd, "--apply")
        rule = os.path.join(rd, ".claude", "rules", "payment.md")
        self.assertTrue(os.path.isfile(rule), "an --apply without the confirmation leaves it alone")
        self.assertIn("keep me", text_of(payment_md), "the human's text around a removed block survives")
        self.assertNotIn("riskrails:rule:payment", text_of(payment_md),
                         "the stale block was taken out without a gate: it is ours")
        self.upd(rd, "--apply", "--confirm-delete", "Ivan", AI_UNATTENDED="1")
        self.assertFalse(os.path.isfile(rule), "the confirmed deletion is performed")
        self.assertTrue(os.path.isfile(os.path.join(rd, ".ai", "reports", "project-update-" + time.strftime(
            "%Y-%m-%d", time.gmtime()), "original", ".claude", "rules", "payment.md")), "its original is kept")
        _, out = self.upd(rd, merge=True)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "and the project is then up to date\n" + out)

        # a nested worktree or repository is not this project's: its rule blocks are never touched
        rn = os.path.join(self.t, "rules-nested")
        shutil.copytree(rd, rn, symlinks=True)
        stale = "# theirs\n<!-- riskrails:rule:gone:start -->\nold\n<!-- riskrails:rule:gone:end -->\n"
        for sub in (".claude/worktrees/wt", "vendor-repo"):
            put(os.path.join(rn, sub, "src", "Payment", "CLAUDE.md"), stale)
        put(os.path.join(rn, ".claude", "worktrees", "wt", ".git"),
            "gitdir: /elsewhere/.git/worktrees/wt\n")                      # a worktree: .git is a file
        os.makedirs(os.path.join(rn, "vendor-repo", ".git"))                 # a repository: .git is a dir
        _, out = self.upd(rn, merge=True)
        self.assertFalse(has("worktrees/wt|vendor-repo", out), "the dry run names neither nested tree\n" + out)
        rc, out = self.upd(rn, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0: a nested tree's blocks are not pending\n" + out)
        self.upd(rn, "--apply")
        for sub in (".claude/worktrees/wt", "vendor-repo"):
            with self.subTest(Template("--apply leaves $sub/src/Payment/CLAUDE.md byte-identical").substitute(sub=sub)):
                self.assertEqual(text_of(os.path.join(rn, sub, "src", "Payment", "CLAUDE.md")), stale)

        # a rule naming a nested tree is not written there: the writer covers what the take-back walks (M1)
        rw = os.path.join(self.t, "rules-nested-writer")
        shutil.copytree(rd, rw, symlinks=True)
        put(os.path.join(rw, "libs", "sub", ".git"), "gitdir: ../../.git/modules/libs/sub\n")   # a submodule
        put(os.path.join(rw, ".claude", "worktrees", "wt", ".git"), "gitdir: /elsewhere/.git/worktrees/wt\n")
        os.makedirs(os.path.join(rw, ".claude", "worktrees", "wt", "src"))
        put(os.path.join(rw, ".ai", "rules", "sub.md"),
            "---\ndirs: [libs, libs/sub, .claude/worktrees/wt/src]\n---\n# Sub rules\n- new text\n")
        stale = "# theirs\n<!-- riskrails:rule:sub:start -->\nold\n<!-- riskrails:rule:sub:end -->\n"
        put(os.path.join(rw, "libs", "sub", "CLAUDE.md"), stale)
        _, out = self.upd(rw, merge=True)
        self.assertFalse(has(r"^  (create|update) +(libs/sub|\.claude/worktrees/wt)/", out),
                         "the dry run plans no write inside either nested tree\n" + out)
        self.assertTrue(has("^  hint +libs/sub/CLAUDE.md: libs/sub is a nested git tree", out),
                        "a hint names libs/sub and why the rule is not rendered there")
        self.assertTrue(has("^  create +libs/CLAUDE.md ", out), "the rule's target outside the nested tree still renders")
        self.upd(rw, "--apply")
        self.assertEqual(text_of(os.path.join(rw, "libs", "sub", "CLAUDE.md")), stale,
                         "--apply leaves libs/sub/CLAUDE.md byte-identical")
        self.assertFalse(os.path.lexists(os.path.join(rw, ".claude", "worktrees", "wt", "src", "CLAUDE.md")),
                         "--apply creates nothing inside the worktree")
        libs = os.path.join(rw, "libs", "CLAUDE.md")
        self.assertTrue(os.path.isfile(libs) and "riskrails:rule:sub:start" in text_of(libs),
                        "--apply renders the control target libs/CLAUDE.md")
        rc, out = self.upd(rw, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0: a hint is not a pending update\n" + out)

        # a dirs: entry spelled with ./ or // targets the file the take-back walks (M1)
        rs = os.path.join(self.t, "rules-spelling")
        shutil.copytree(rd, rs, symlinks=True)
        os.makedirs(os.path.join(rs, "lib", "x"))
        os.makedirs(os.path.join(rs, "lib", "y"))
        put(os.path.join(rs, ".ai", "rules", "lib.md"),
            '---\ndirs: ["./lib", "lib//x", "lib/./y", lib]\n---\n# Lib rules\n- lib text\n')
        put(os.path.join(rs, ".ai", "rules", "top.md"), '---\ndirs: ["./"]\n---\n# Root rules\n- root text\n')
        _, out = self.upd(rs, merge=True)
        for t in ("lib/CLAUDE.md", "lib/x/CLAUDE.md", "lib/y/CLAUDE.md"):
            with self.subTest(Template("the dry run plans create $t").substitute(t=t)):
                self.assertTrue(has("^  create +%s " % re.escape(t), out), out)
        self.assertFalse(has(r"^  [a-z?]+ +[^ ]*(\./|//)", out), "no planned target is spelled with ./ or //")
        self.assertEqual(grep("^  create +lib/CLAUDE.md ", out), 1, "./lib and lib plan lib/CLAUDE.md once")
        self.assertTrue(has("^  update +CLAUDE.md ", out), 'dirs: ["./"] still targets the root CLAUDE.md')
        rc, out = self.upd(rs, "--apply", merge=True)
        self.assertEqual(rc, 0, "--apply exits 0\n" + out)
        _, out = self.upd(rs, merge=True)
        self.assertTrue(has("^0 automatic, 0 conflict", out),
                        "the run after --apply is up to date: no create/remove alternation\n" + out)
        rc, out = self.upd(rs, "--check", merge=True)
        self.assertEqual(rc, 0, "--check exits 0 after --apply\n" + out)
        lib = os.path.join(rs, "lib", "CLAUDE.md")
        self.assertEqual(grep("riskrails:rule:lib:start", text_of(lib)) if os.path.isfile(lib) else 0, 1,
                         "lib/CLAUDE.md holds one lib block: ./lib and lib collapse")
        self.assertIn("riskrails:rule:top:start", text_of(os.path.join(rs, "CLAUDE.md")),
                      "--apply renders the ./ rule into the root CLAUDE.md")
        rx = os.path.join(self.t, "rules-spelling-escape")
        shutil.copytree(rd, rx, symlinks=True)
        put(os.path.join(rx, ".ai", "rules", "esc.md"), "---\ndirs: [a/../b]\n---\n# Escape\n- text\n")
        _, out = self.upd(rx, merge=True)
        self.assertIn("must stay inside the project: a/../b", out,
                      "dirs: [a/../b] is still refused before it is normalised")

    def test_every_history_key_is_accounted_for(self):
        """every key in the template history is accounted for"""
        rc, out = self.run_([sys.executable, "-I", "-c", HISTORY_KEYS, ROOT], merge=True)
        self.assertEqual(rc, 0, "no history key is orphaned, and no moved-away path is shipped again\n" + out)

    def test_schema_4_gate_keys(self):
        """schema 4: a task in flight gains the gate keys and keeps working (R14)"""
        s9 = self.current_project("schema3", "--runtime", "claude")
        shutil.copytree(os.path.join(FIX, "schema-v3", ".ai"), os.path.join(s9, ".ai"),
                        dirs_exist_ok=True)      # VERSION 3 and a task in flight, as the fixture ships them
        current = os.path.join(s9, ".ai", "state", "current.json")
        _, out = self.upd(s9)
        self.assertIn("[0004]", out, "the dry run names the state migration")
        self.assertNotIn("diff", read_json(current), "and the dry run writes nothing into the state")
        self.upd(s9, "--apply")
        state = read_json(current)
        label = "the keys are added with nulls, and nothing else is touched"
        self.assertIsNone(state["diff"]["base_tree"], "a base tree must not be invented")
        self.assertEqual(state["diff"]["task"]["status"], "not_measured", label)
        self.assertEqual(state["tests"], {"runs": [], "suite_runs": 0}, label)
        self.assertIsNone(state["risk_tier_lowered"]["by"], label)
        self.assertTrue(state["sensors"]["file"].endswith("sensors.json"), label)
        steps = state["approved_plan"]["steps"]
        self.assertEqual([s["kind"] for s in steps], ["implementation", "implementation"], label)
        self.assertTrue(all(s["tree_before"] is None and s["diff"] is None for s in steps), label)
        self.assertTrue(state["goal"] == "widen the export" and state["completed_steps"] == ["1"], label)
        self.assertEqual(self.version(s9), self.cur(), Template("the schema reaches $CURRENT").substitute(CURRENT=self.cur()))
        _, out = self.upd(s9)
        self.assertTrue(has("^0 automatic", out), "a second run has nothing to do\n" + out)
        self.assertIn("old surface", self.status(s9, unset=("CLAUDECODE",))[1],
                      "a task that started before schema 4 is still read after it")

    def test_schema_5_handoff_keys(self):
        """schema 5: a task in flight gains the handoff keys (R17)"""
        s10 = self.current_project("schema4", "--runtime", "claude")
        shutil.copytree(os.path.join(FIX, "schema-v4", ".ai"), os.path.join(s10, ".ai"),
                        dirs_exist_ok=True)      # VERSION 4 and a task in flight
        current = os.path.join(s10, ".ai", "state", "current.json")
        self.assertGreaterEqual(self.current, 5, "the migrations reach schema 5 or later")
        self.assertEqual(self.upd(s10, "--check")[0], 1, "--check exits 1 at schema 4")
        _, out = self.upd(s10)
        self.assertIn("[0005]", out, "the dry run names migration 0005")
        self.upd(s10, "--apply")
        state = read_json(current)
        label = "the keys are added with nulls, and nothing else is touched"
        self.assertTrue(state["handoff"]["pending_to"] is None and state["handoff"]["pending_since"] is None, label)
        self.assertEqual(state["handoff"]["file"], ".ai/state/handoff.md", label)
        self.assertIsNone(state["cross_vendor_review"], label)
        self.assertEqual(state["diff"]["task"]["status"], "not_measured", label)     # schema 4 untouched
        self.assertTrue(state["goal"] == "widen the export" and state["completed_steps"] == ["1"], label)
        self.assertEqual(self.version(s10), self.cur(), Template("the schema reaches $CURRENT").substitute(CURRENT=self.cur()))
        _, out = self.upd(s10)
        self.assertTrue(has("^0 automatic", out), "a second run has nothing to do\n" + out)
        self.assertEqual(self.upd(s10, "--check")[0], 0, "--check exits 0 once migrated")
        self.assertEqual(len([h for h in state["history"] if str(h.get("detail")).startswith("0005 ")]), 1,
                         "schema_migrated 0005 is recorded in the task's history")

    def test_check_budget(self):
        """--check --budget: a root instruction file over its byte budget exits 1 (WP6 R21)"""
        b = self.current_project("budget", "--runtime", "claude")
        rc, out = self.upd(b, "--check", "--budget")
        self.assertTrue(rc == 0 and not out.strip(), "a fresh scaffold is within budget: exit 0, nothing printed\n" + out)
        self.assertEqual(self.upd(b, "--budget")[0], 2, "--budget without --check is a usage error")
        put(os.path.join(b, "CLAUDE.md"), "x" * 400 + "\n", "a")
        rc, out = self.upd(b, "--check", "--budget")
        self.assertTrue(rc == 1 and has(r"^CLAUDE\.md file [0-9]+ B over the skeleton budget of 2048 B$", out),
                        "a padded CLAUDE.md exits 1 and names the file and the budget\n" + out)
        self.assertNotIn(" block ", out, "only the offender is listed")
        # An installed plugin has skills/ but no instructions/: the budgets must still apply.
        inst = os.path.join(self.t, "installed", "skills")
        shutil.copytree(os.path.join(ROOT, "skills", "project-update"), os.path.join(inst, "project-update"))
        rc, out = self.run_([sys.executable, "-I", os.path.join(inst, "project-update", "update.py"), b, "--check",
                             "--budget"], merge=True)
        self.assertTrue(rc == 1 and "over the skeleton budget of 2048 B" in out and "Traceback" not in out,
                        "from a skills-only install the shipped budgets apply\n" + out)
        shipped = json.dumps(read_json(os.path.join(ROOT, "instructions", "runtimes.json"))["_budgets"],
                             sort_keys=True, separators=(",", ":"))
        _, default = self.run_([sys.executable, "-I", "-c", "import json, sys; sys.path.insert(0, sys.argv[1]); "
                                "import render_instructions as r; "
                                "print(json.dumps(r.DEFAULT_BUDGETS, sort_keys=True, separators=(',', ':')))",
                                os.path.join(ROOT, "skills", "project-update")])
        self.assertEqual(shipped, default.strip(), "DEFAULT_BUDGETS equals _budgets in runtimes.json")

    def test_legacy_marker_pair_is_renamed(self):
        """a legacy Codex-agentic marker pair is renamed, not doubled"""
        # An AGENTS.md written before the plugin's markers were unified carries
        # <!-- Codex-agentic:start/end -->. The block inside is the shipped one.
        block = text_of(BLOCK)
        old = legacy(block)
        lp = self.legacy_project("legacy", "# legacy\n\nkeep me above\n\n" + old + "\n# my notes\nkeep me below\n")
        rc, out = self.upd(lp, merge=True)
        self.assertEqual(rc, 0, "the dry run exits 0 on a legacy marker\n" + out)
        self.assertTrue(has("AGENTS.md .*legacy Codex-agentic markers renamed", out),
                        "the dry run says the markers will be renamed")
        self.assertNotIn("AGENTS.md (split?)", out,
                         "the dry run sees the legacy block as the managed block (no split? hint)")
        self.upd(lp, "--apply", merge=True)
        agents = text_of(os.path.join(lp, "AGENTS.md"))
        self.assertEqual(grep("riskrails:start", agents), 1, "one current block remains")
        self.assertNotIn("Codex-agentic", agents, "the legacy markers are gone")
        self.assertTrue("keep me above" in agents and "keep me below" in agents, "the text around the block is kept")
        rows = agents.splitlines(keepends=True)
        start = next(i for i, l in enumerate(rows) if "riskrails:start" in l)
        end = next(i for i, l in enumerate(rows) if i > start and "riskrails:end" in l)
        self.assertEqual("".join(rows[start:end + 1]), block, "the renamed block is the shipped one")
        _, out = self.upd(lp, "--apply", merge=True)
        self.assertTrue(has("^0 automatic, 0 conflict", out), "a second run has nothing left\n" + out)

        # An edited line inside a legacy block: the markers are renamed and the edit is
        # kept — the same path an edited current block takes.
        e = self.legacy_project("legacy-edited",
                                "# legacy\n\n" + insert_line(old, 3, "my own rule, right inside the block", after=True))
        self.upd(e, "--apply", merge=True)
        agents = text_of(os.path.join(e, "AGENTS.md"))
        self.assertNotIn("Codex-agentic", agents, "an edited legacy block gets the current markers")
        self.assertIn("my own rule, right inside the block", agents, "and its edit is kept")
        self.assertEqual(grep("riskrails:start", agents), 1, "with one block")

        # Half a current pair next to a legacy pair is a broken file: nothing is renamed.
        h = self.legacy_project("legacy-half", "# half\n\n<!-- riskrails:start -->\nlone start\n\n" + old)
        self.upd(h, "--apply", merge=True)
        agents = text_of(os.path.join(h, "AGENTS.md"))
        self.assertTrue("Codex-agentic:start" in agents and grep("riskrails:end", agents) == 1,
                        "a lone current marker beside a legacy pair renames nothing\n" + agents)

    def test_budget_hint_for_a_pristine_legacy_block(self):
        """budget hint: a pristine legacy block over the budget is the plugin's to trim, not the project's"""
        # The hint compares the block with the shipped one. A legacy pair must be
        # compared through its renamed markers, or a block that --apply will rewrite
        # anyway is reported as "edited here, trimming it is yours".
        pt = os.path.join(self.t, "padded-tpl")
        shutil.copytree(TEMPLATES, pt, symlinks=True)
        padded = text_of(os.path.join(pt, "AGENTS.block.md"))
        i = padded.index("<!-- riskrails:end -->")
        put(os.path.join(pt, "AGENTS.block.md"),
            padded[:i] + "<!-- padding, over the project budget -->\n" * 60 + padded[i:])
        pb = self.legacy_project("padded-legacy", "# legacy\n\n" + legacy(text_of(os.path.join(pt, "AGENTS.block.md"))))
        _, out = self.upd(pb, merge=True, CLAUDE_AGENTIC_TEMPLATES=pt)
        self.assertTrue(has("AGENTS.md: the managed block is [0-9]* B, budget [0-9]* B — the plugin ships it that size",
                            out), "an untouched legacy block over budget is the plugin's")
        self.assertNotIn("trimming it is yours", out, "no 'edited here' for the untouched block")
        # The same block with one line of the project's own inside it is the project's.
        agents = os.path.join(pb, "AGENTS.md")
        put(agents, insert_line(text_of(agents), 3, "my own rule, right inside the block", after=True))
        _, out = self.upd(pb, merge=True, CLAUDE_AGENTIC_TEMPLATES=pt)
        self.assertTrue(has("AGENTS.md: the managed block is .* trimming it is yours", out),
                        "an edited legacy block over budget is the project's\n" + out)

    # -- SDLC templates the plugin supplies, and the cleanup proposals ------

    SDLC_TEMPLATES = (("intent.md", "intent"), ("spec.md", "specs"), ("plan.md", "plans"), ("adr.md", "adr"))

    def sdlc_project(self, name, keep=()):
        """A current project with the SDLC TEMPLATE.md of `keep` as the plugin ships them
        (an older scaffold left all four) and the others absent."""
        d = self.current_project(name)
        for src, sub in self.SDLC_TEMPLATES:
            target = os.path.join(d, "docs", "sdlc", sub, "TEMPLATE.md")
            if sub in keep:
                put(target, text_of(os.path.join(ROOT, "skills", "project-init", "templates", src)))
            elif os.path.exists(target):
                os.remove(target)
        return d

    def test_sdlc_templates_are_retired(self):
        """an unedited TEMPLATE.md is offered for deletion, an edited one stays with one hint,
        a missing one is never created, and --check stays 0"""
        d = self.sdlc_project("retire", keep=("intent", "specs", "adr"))
        put(os.path.join(d, "docs", "sdlc", "adr", "TEMPLATE.md"), "\n# our own wording\n", "a")
        _, out = self.upd(d)
        for sub in ("intent", "specs"):
            self.assertTrue(has(r"^  delete\?   docs/sdlc/%s/TEMPLATE.md .*\[sdlc\] the plugin supplies it: "
                                r"skills/project-init/templates/" % sub, out), out)
        self.assertFalse(has(r"delete\?   docs/sdlc/adr/TEMPLATE.md", out), "an edited copy is kept\n" + out)
        self.assertTrue(has(r"^  hint      1 file\(s\) override the plugin's SDLC template.*adr/TEMPLATE.md", out), out)
        self.assertFalse(os.path.exists(os.path.join(d, "docs", "sdlc", "plans", "TEMPLATE.md")),
                         "a missing copy is not created again")
        self.assertEqual(self.upd(d, "--check")[0], 0, "a deletion a human must confirm is not a pending update")
        crlf = self.sdlc_project("retire-crlf")
        shipped = raw(os.path.join(ROOT, "skills", "project-init", "templates", "plan.md"))
        put(os.path.join(crlf, "docs", "sdlc", "plans", "TEMPLATE.md"), shipped.replace(b"\n", b"\r\n"), "wb")
        self.assertTrue(has(r"delete\?   docs/sdlc/plans/TEMPLATE.md .*\[sdlc\]", self.upd(crlf)[1]),
                        "a CRLF copy of the shipped template is still unedited")
        bare = self.sdlc_project("retire-bare")
        rc, out = self.upd(bare, "--check")
        self.assertEqual(rc, 0, "a project without the four files is complete\n" + out)
        self.assertNotIn("TEMPLATE.md", self.upd(bare)[1])
        rc, out = self.upd(d, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        self.assertFalse(os.path.exists(os.path.join(d, "docs", "sdlc", "intent", "TEMPLATE.md")))
        self.assertTrue(os.path.exists(os.path.join(d, "docs", "sdlc", "adr", "TEMPLATE.md")))

    def task_dir(self, d, task_id, events, logs=()):
        """A task's journal (events: [(days ago, event, data)]), one report file and its run logs."""
        lines = [json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - ago * 86400)),
                             "task": task_id, "event": ev, "detail": (more[0] if more else ""), "data": data})
                 for ago, ev, data, *more in events]
        put(os.path.join(d, ".ai", "reports", task_id, "events.jsonl"), "\n".join(lines) + "\n")
        put(os.path.join(d, ".ai", "reports", task_id, "task.md"), "x\n")
        for name in logs:
            put(os.path.join(d, ".ai", "state", "logs", task_id, name), "log\n")

    def cleanup_project(self, name):
        d = self.current_project(name)
        self.task_dir(d, "T-2026-01-01-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": False})],
                      logs=("verify.log", "review.log", "state.json"))
        self.task_dir(d, "T-2026-01-02-001", [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})],
                      logs=("verify.log", "state.json"))
        self.task_dir(d, "T-2026-01-03-001", [(9, "task_started", {}), (8, "step_started", {})], logs=("a.log",))
        self.task_dir(d, "T-2026-01-04-001", [(3, "task_started", {}), (2, "step_started", {})], logs=("b.log",))
        self.task_dir(d, "T-2026-01-05-001", [(40, "task_started", {})], logs=("c.log",))
        put_json(os.path.join(d, ".ai", "state", "state.json"), {"task_id": "T-2026-01-05-001"})
        # finished by other evidence than a whole task_closed line (M1)
        self.task_dir(d, "T-2026-01-06-001", [(40, "task_started", {}), (39, "gate_approved", {})], logs=("g.log",))
        self.task_dir(d, "T-2026-01-07-001", [(40, "task_started", {})], logs=("h.log",))
        put_json(os.path.join(d, ".ai", "state", "logs", "T-2026-01-07-001", "state.json"), {"result": "done"})
        # a torn task_closed line and no state.json: still unclosed
        self.task_dir(d, "T-2026-01-08-001", [(40, "task_started", {})], logs=("i.log",))
        put(os.path.join(d, ".ai", "reports", "T-2026-01-08-001", "events.jsonl"),
            '{"ts": "2000-01-01T00:00:00Z", "event": "task_closed", "da', "a")
        # abandoned by the detail alone
        self.task_dir(d, "T-2026-01-09-001", [(30, "task_started", {}), (29, "task_closed", {}, "abandoned")],
                      logs=("j.log", "state.json"))
        # a symlink in a closed task's logs is never followed or listed
        os.symlink(os.path.join(d, ".ai", "state", "logs", "T-2026-01-01-001", "verify.log"),
                   os.path.join(d, ".ai", "state", "logs", "T-2026-01-01-001", "link.log"))
        return d

    def test_cleanup_proposals(self):
        """the logs of a closed task, an abandoned and a long-idle unclosed task are proposed; a recent
        and the in-flight task are not; --check is unaffected"""
        d = self.cleanup_project("cleanup")
        before = tree_sum(d)
        _, out = self.upd(d)
        self.assertTrue(has(r"^  delete\?   \.ai/state/logs/T-2026-01-01-001/ \(2 files\) +\[cleanup\] "
                            r"log of closed task T-2026-01-01-001", out), "one line per task, *.log only\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-02-001/ \(2 files\) +\[cleanup\] abandoned task "
                            r"T-2026-01-02-001", out), out)
        self.assertTrue(has(r"delete\?   \.ai/state/logs/T-2026-01-02-001/ \(1 file\) +\[cleanup\] abandoned task"
                            r".*--confirm-cleanup NAME.*not recoverable through git", out),
                        "an abandoned task keeps its state.json; the row says git cannot restore the logs\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-09-001/ .*abandoned task", out),
                        "abandonment by the event detail alone\n" + out)
        self.assertEqual(grep(r"unclosed task T-2026-01-0[67]-001", out), 0,
                         "gate_approved, or a state.json result, finishes a task\n" + out)
        self.assertTrue(has(r"unclosed task T-2026-01-08-001", out), "a torn task_closed alone is unclosed\n" + out)
        self.assertEqual(grep(r"link\.log", out), 0, "a symlink is skipped\n" + out)
        self.assertEqual(grep(r"commit \.ai/ first", out), 0,
                         "cleanup rows alone do not raise the commit-first hint\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-03-001/ \(2 files\) +\[cleanup\] unclosed task "
                            r"T-2026-01-03-001, last event \d{4}-\d\d-\d\d", out), out)
        self.assertEqual(grep(r"T-2026-01-04-001", out), 0, "an open task idle for 2 days is left alone\n" + out)
        self.assertEqual(grep(r"T-2026-01-05-001", out), 0, "the task in flight is never proposed\n" + out)
        self.assertEqual(self.upd(d, "--check")[0], 0)
        self.assertEqual(tree_sum(d), before, "a dry run writes nothing")

    def test_cleanup_malformed_now_and_flight(self):
        """a malformed RISKRAILS_NOW is a usage error, not a traceback; the task named by the legacy
        current.json is in flight"""
        d = self.cleanup_project("cleanup-now")
        rc, out = self.upd(d, merge=True, RISKRAILS_NOW="yesterday")
        self.assertEqual(rc, 2, out)
        self.assertTrue("RISKRAILS_NOW" in out and "Traceback" not in out, out)
        self.assertEqual(len(out.strip().splitlines()), 1, "one line\n" + out)
        os.remove(os.path.join(d, ".ai", "state", "state.json"))
        put_json(os.path.join(d, ".ai", "state", "current.json"), {"task_id": "T-2026-01-03-001"})
        _, out = self.upd(d)
        self.assertEqual(grep(r"T-2026-01-03-001", out), 0, "current.json names the task in flight\n" + out)

    def test_cleanup_confirmed_deletes_and_prunes(self):
        """--apply --confirm-cleanup removes the proposed files and the directories they leave empty;
        --confirm-delete alone does not settle them"""
        d = self.cleanup_project("cleanup-apply")
        before = tree_sum(d)
        rc, out = self.upd(d, "--apply", "--confirm-delete", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        self.assertEqual(tree_sum(d), before, "--confirm-delete leaves every [cleanup] row\n" + out)
        self.assertEqual(self.upd(d, "--confirm-cleanup", "tester")[0], 2, "--confirm-cleanup needs --apply")
        self.assertEqual(self.upd(d, "--apply", "--confirm-cleanup", "")[0], 2, "an empty name is refused")
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester")
        self.assertEqual(rc, 5, "--confirm-cleanup without a human present is refused\n" + out)
        self.assertEqual(out.split("\n")[0].split(":")[0], "ADOPT_REFUSED")
        self.assertEqual(tree_sum(d), before)
        if self.has_pty():
            tty = self.cleanup_project("cleanup-tty")
            rc, out = self.pty(["env", "CLAUDECODE=1", sys.executable, "-I", UPDATE, tty, "--apply",
                                "--confirm-cleanup", "tester"], unset=NOMARK)
            self.assertTrue(rc == 5 and "CLAUDECODE" in out, "an agent marker with a terminal is refused\n" + out)
            rc, out = self.pty([sys.executable, "-I", UPDATE, tty, "--apply", "--confirm-cleanup", "tester"],
                               unset=NOMARK)
            self.assertEqual(rc, 0, out)
            self.assertEqual(read_json(only(os.path.join(tty, ".ai", "reports", "project-update-*",
                                                         "migration.json")))["deletions"][0]["via"], "terminal")
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        report = glob.glob(os.path.join(d, ".ai", "reports", "project-update-*"))
        rec = read_json(os.path.join(report[0], "migration.json"))
        self.assertEqual((rec["deletions"][0]["confirmed_by"], rec["deletions"][0]["via"]),
                         ("tester", "unattended"))
        self.assertFalse(os.path.exists(os.path.join(report[0], "original")), "no original/ copy of a [cleanup]")
        logs = os.path.join(d, ".ai", "state", "logs")
        self.assertEqual(sorted(os.listdir(os.path.join(logs, "T-2026-01-01-001"))), ["link.log", "state.json"],
                         "the closed task's logs go, its state.json stays (and a symlink is never followed)")
        self.assertEqual(os.listdir(os.path.join(logs, "T-2026-01-02-001")), ["state.json"],
                         "an abandoned task's state.json stays")
        self.assertTrue(os.path.islink(os.path.join(logs, "T-2026-01-01-001", "link.log")), "the symlink stays")
        self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", "T-2026-01-02-001")))
        self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", "T-2026-01-03-001")))
        self.assertFalse(os.path.exists(os.path.join(logs, "T-2026-01-03-001")))
        self.assertTrue(os.path.exists(os.path.join(logs, "T-2026-01-04-001", "b.log")))
        self.assertTrue(os.path.exists(os.path.join(logs, "T-2026-01-05-001", "c.log")))
        self.assertTrue(os.path.isdir(os.path.join(d, ".ai", "reports")))

    def git_(self, d, *args):
        subprocess.run(GIT + ["-C", d] + list(args), env=self.env, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)

    def abandoned(self, d, task_id):
        self.task_dir(d, task_id, [(30, "task_started", {}), (29, "task_closed", {"abandoned": True})],
                      logs=("verify.log",))

    def test_cleanup_reports_are_tracked_not_git_ignored(self):
        """#5: a report dir git holds is worded 'tracked'; one it does not hold keeps the commit-first
        hint; both keep an original/ copy; the git-ignored logs keep their wording and no copy"""
        d = self.current_project("cleanup-git")
        subprocess.run(["git", "-C", d, "init", "-q"], env=self.env, check=True)
        put(os.path.join(d, ".gitignore"), ".ai/state/logs/\n")
        self.abandoned(d, "T-2026-01-01-001")
        self.git_(d, "add", "-A")
        self.git_(d, "commit", "-qm", "base")
        _, out = self.upd(d)
        self.assertFalse(has(r"commit \.ai/ first", out), "a committed report needs no hint\n" + out)
        self.assertTrue(has(r"delete\?   \.ai/reports/T-2026-01-01-001/ \(2 files\) +\[cleanup\] abandoned task "
                            r"T-2026-01-01-001; tracked: git can restore a committed copy", out), out)
        self.assertTrue(has(r"delete\?   \.ai/state/logs/T-2026-01-01-001/ .*not recoverable through git", out), out)
        self.abandoned(d, "T-2026-01-02-001")            # written after the commit: untracked
        _, out = self.upd(d)
        self.assertTrue(has(r"hint +commit \.ai/ first", out), "an untracked report keeps the hint\n" + out)
        self.assertTrue(has(r"T-2026-01-02-001/ \(2 files\) .*uncommitted: git holds no copy", out), out)
        rc, out = self.upd(d, "--apply", "--confirm-cleanup", "tester", AI_UNATTENDED="1", merge=True)
        self.assertEqual(rc, 0, out)
        orig = os.path.join(glob.glob(os.path.join(d, ".ai", "reports", "project-update-*"))[0], "original")
        for task_id in ("T-2026-01-01-001", "T-2026-01-02-001"):
            self.assertTrue(os.path.isfile(os.path.join(orig, ".ai", "reports", task_id, "task.md")),
                            "an original/ copy of a report file")
            self.assertFalse(os.path.exists(os.path.join(d, ".ai", "reports", task_id)))
        self.assertFalse(os.path.exists(os.path.join(orig, ".ai", "state")), "no copy of git-ignored logs")

    def test_cleanup_unreadable_state_json_is_a_task_in_flight(self):
        """#11: an unparsable state.json proposes nothing as stale"""
        d = self.cleanup_project("cleanup-torn")
        put(os.path.join(d, ".ai", "state", "state.json"), "{ not json")
        _, out = self.upd(d)
        self.assertEqual(grep(r"\[cleanup\]", out), 0, "nothing is proposed while a task may be in flight\n" + out)

    SWAP = """
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "skills", "project-update"))
import update                                            # noqa: E402
root = sys.argv[2]
plan = update.build_plan(root, confirm_cleanup="tester", cleanup_via="unattended")
reports = os.path.join(root, ".ai", "reports")
os.rename(os.path.join(reports, "T-2026-01-02-001"), os.path.join(reports, "moved"))
os.symlink("moved", os.path.join(reports, "T-2026-01-02-001"))     # same bytes, now behind a symlink
try:
    update.apply(plan)
except update.Abort as exc:
    print("ABORT", exc.why)
    sys.exit(0)
print("DELETED")
"""

    def test_cleanup_apply_refuses_a_path_swapped_to_a_symlink(self):
        """#70 (n): unsafe_target's check is repeated right before the delete"""
        d = self.cleanup_project("cleanup-swap")
        done = subprocess.run([sys.executable, "-I", "-c", self.SWAP, ROOT, d], env=self.env,
                              capture_output=True, text=True)
        self.assertTrue(done.stdout.startswith("ABORT") and "is a symlink" in done.stdout,
                        done.stdout + done.stderr)
        self.assertTrue(os.path.isfile(os.path.join(d, ".ai", "reports", "moved", "task.md")), "nothing deleted")


class TestMemoryPolicy(unittest.TestCase):
    """compact-project-memory (plan Risks): .ai/policies/memory.json is the
    project's, written by `memory enable`; no template ships it, and --update
    leaves it and the record byte for byte as they are."""

    def test_update_leaves_memory_json_and_the_record_alone(self):
        p = Project()
        try:
            policy = b'{\n  "schema": 1,\n  "mode": "packages",\n  "period": "month",\n  "cleanup": false\n}\n'
            with open(p.path("policies", "memory.json"), "wb") as fh:
                fh.write(policy)
            os.makedirs(p.path("memory"))
            with open(p.path("memory", "2026-10.dev.abcd.jsonl"), "wb") as fh:
                fh.write(b'{"author":"dev","batch":"abcd","created":"2026-10-01T00:00:00Z","format":1,'
                         b'"period":"2026-10","pkg":"riskrails-memory"}\n')
            subprocess.run(GIT + ["-C", p.root, "add", "-A"], check=True)
            subprocess.run(GIT + ["-C", p.root, "commit", "-qm", "memory on"], check=True)
            done = p.update("--apply")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(p.read("policies", "memory.json"), policy)
            self.assertEqual(os.listdir(p.path("memory")), ["2026-10.dev.abcd.jsonl"])
            self.assertNotIn("memory.json", done.stdout)
            self.assertFalse(os.path.exists(os.path.join(TEMPLATES, ".ai", "policies", "memory.json")))
        finally:
            p.close()


if __name__ == "__main__":
    unittest.main()
