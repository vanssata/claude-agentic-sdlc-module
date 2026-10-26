"""Migration 0007 (redesign 2.2a): the risk-tier table's edits land in
weight.json, a task in flight gets a mode, and the schema reaches 7 without a
human having to confirm anything.

Every project is today's scaffold with tests/fixtures/project-update/schema-v6/
laid over it, in a temp directory with a pinned HOME.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPDATE = os.path.join(ROOT, "skills", "project-update", "update.py")
SCAFFOLD = os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
MIGRATION = os.path.join(ROOT, "skills", "project-update", "migrations", "0007_weight_model.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "project-update", "schema-v6")
POLICIES = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies")
GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]


def load_migration():
    spec = importlib.util.spec_from_file_location("migration_0007_under_test", MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def shipped_tables():
    """What _shipped() returns, from today's shipped risk-tiers.json and weight.json."""
    doc = read_json(os.path.join(POLICIES, "risk-tiers.json"))
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
    def __init__(self, in_flight=False, weight=True, edited=False):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.home = os.path.join(self.tmp.name, "home")
        self.root = os.path.join(self.tmp.name, "p")
        os.makedirs(self.home)
        os.makedirs(self.root)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_AGENTIC_MIGRATIONS", "CLAUDE_CONFIG_DIR")}
        self.env.update(HOME=self.home, CLAUDE_AGENTIC_SHARED=os.path.join(ROOT, "ai"))
        subprocess.run(["bash", SCAFFOLD, self.root, "--runtime", "claude"], env=self.env, check=True,
                       capture_output=True)
        shutil.copytree(os.path.join(FIXTURE, ".ai"), os.path.join(self.root, ".ai"), dirs_exist_ok=True)
        if in_flight:
            shutil.copytree(os.path.join(FIXTURE, "in-flight", ".ai"), os.path.join(self.root, ".ai"),
                            dirs_exist_ok=True)
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
        old = edit_tiers(read_json(os.path.join(POLICIES, "risk-tiers.json")))
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
        plain = read_json(os.path.join(POLICIES, "risk-tiers.json"))
        self.assertEqual(mod.convert(plain, base, shipped_tables()), base)

    def test_a_projects_own_weight_values_survive(self):
        # Review H1: an unedited risk-tiers.json carries no scalar, and an edited
        # one never overwrites a value the project already set in weight.json.
        mod = load_migration()
        base = read_json(os.path.join(POLICIES, "weight.json"))
        base["tests"].update(max_suite_runs=1, timeout_seconds=3600)
        base["remediation_rounds"] = 4
        plain = read_json(os.path.join(POLICIES, "risk-tiers.json"))
        self.assertEqual(mod.convert(plain, base, shipped_tables()), base)
        edited = edit_tiers(read_json(os.path.join(POLICIES, "risk-tiers.json")))
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
            self.assertIn("schema    6 -> 7", dry.stdout)
            self.assertNotIn("delete?", dry.stdout)
            self.assertEqual([line for line in dry.stdout.split("\n") if "[0007]" in line and "risk-tiers" in line], [])
            done = p.update("--apply")
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            self.assertEqual(p.version(), "7")
            weight = json.loads(p.read("policies", "weight.json"))
            self.assertIn("the order export job", weight["examples"]["guarded"])
            self.assertIn("weight --mirror", done.stdout)
            # The old surface's table stays where it is, with the project's edits (the
            # template walk merges it as before; 0007 neither moves nor deletes it).
            self.assertIn("the order export job",
                          json.loads(p.read("policies", "risk-tiers.json"))["tiers"]["T4"]["examples"])
            self.assertTrue(os.path.isfile(p.path("policies", "risk-tiers.md")))
            # 0007 runs once: the second run plans no migration and changes no file.
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
                self.assertEqual((done.returncode, p.version()), (0, "7"), done.stdout + done.stderr)
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
            state = json.loads(p.read("state", "current.json"))
            self.assertEqual(state["mode"], "guarded")
            self.assertEqual(state["weight"], {"w": None, "axes": {}, "unknown": ["migrated"]})
            self.assertNotIn("schema", state)
            self.assertEqual((state["current_stage"], state["approved_plan"]["current_step_id"]),
                             ("implementation", "1"))
            self.assertEqual(state["approved_plan"]["steps"][0]["allowed_files"],
                             ["src/Shared/Clock.php", "tests/ClockTest.php"])
            self.assertEqual(state["history"][-1]["event"], "schema_migrated")
            first = p.read("state", "current.json")
            p.update("--apply")
            self.assertEqual(p.read("state", "current.json"), first)
            env = dict(p.env, AI_RUNTIME="claude")
            got = subprocess.run([sys.executable, "-I", STATE, "--root", p.root, "get", "--field", "risk_tier"],
                                 env=env, capture_output=True, text=True, check=False)
            self.assertEqual(got.stdout.strip(), "T4")
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


if __name__ == "__main__":
    unittest.main()
