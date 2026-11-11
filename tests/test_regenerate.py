#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
project-update regenerates its own files (spec riskrails-regenerate-not-migrate, R3-R7, R11-R18, R29).

Four trees, all in a temp directory with a pinned HOME:
  fresh          today's templates laid out as a scaffold would, over tests/fixtures/regenerate/fresh (the
                 project's own kept files)
  v3.1.0         the scaffold riskrails 3.1.0 made (schema 11): tests/fixtures/regenerate/v3.1.0
  v3.1.0-edited  that tree with a human's edits laid over it: tests/fixtures/regenerate/v3.1.0-edited
  dual           the 3.1.0 tree declaring Claude Code and Codex: tests/fixtures/regenerate/dual
"""
import glob
import hashlib
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
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "regenerate")
AI_TEMPLATES = os.path.join(ROOT, "skills", "ai-init", "templates")
PI_TEMPLATES = os.path.join(ROOT, "skills", "project-init", "templates")
GIT = ["git", "-c", "user.name=tester", "-c", "user.email=tester@example.invalid", "-c", "commit.gpgsign=false"]
TREES = ("fresh", "v3.1.0", "v3.1.0-edited", "dual")


def load(name, path):
    sys.path.insert(0, os.path.dirname(path))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(UPDATE))
import render_instructions  # noqa: E402  # pylint: disable=wrong-import-position,import-error
from rr_update import history, paths  # noqa: E402  # pylint: disable=wrong-import-position,import-error
W = load("weight_under_test", os.path.join(ROOT, "skills", "ai-task", "weight.py"))


def raw(path):
    with open(path, "rb") as fh:
        return fh.read()


def put(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as fh:
        fh.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def snapshot(root):
    """{relative path: bytes} of every file outside .git."""
    out = {}
    for top, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for name in files:
            full = os.path.join(top, name)
            if os.path.isfile(full):
                out[os.path.relpath(full, root).replace(os.sep, "/")] = raw(full)
    return out


def digest(snap):
    h = hashlib.sha256()
    for rel in sorted(snap):
        h.update(rel.encode() + b"\0" + snap[rel] + b"\0")
    return h.hexdigest()


def rows(out):
    """{target: action} of the plan rows a run printed."""
    found = {}
    for line in out.splitlines():
        m = re.match(r"  (create|regenerate\??|delete\??|split)\s+(\S+)", line)
        if m:
            found[m.group(2)] = m.group(1)
    return found


class Tree:
    """One project under test."""

    def __init__(self, kind):
        self.kind = kind
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.home = os.path.join(self.tmp.name, "home")
        self.root = os.path.join(self.tmp.name, "p")
        os.makedirs(self.home)
        os.makedirs(self.root)
        self.env = {k: v for k, v in os.environ.items()
                    if k not in ("CODEX_HOME", "AI_UNATTENDED", "CLAUDE_CONFIG_DIR") and not k.startswith("RISKRAILS_")}
        self.env.update(HOME=self.home, RISKRAILS_SHARED=os.path.join(ROOT, "ai"))
        getattr(self, "build_" + kind.replace(".", "_").replace("-", "_"))()
        subprocess.run(["git", "init", "-q", self.root], check=True)
        self.commit("start")

    # ---- the four trees
    def lay(self, name):
        shutil.copytree(os.path.join(FIXTURES, name), self.root, dirs_exist_ok=True)

    def build_fresh(self):
        shutil.copytree(os.path.join(AI_TEMPLATES, ".ai"), os.path.join(self.root, ".ai"))
        os.remove(self.path(".ai", "policies", "weight.json"))  # the plugin's table is read from the plugin
        self.lay("fresh")
        minimal = raw(os.path.join(AI_TEMPLATES, "CLAUDE.minimal.md")).replace(b"{{PROJECT}}", b"p")
        put(self.path("CLAUDE.md"), minimal.rstrip(b"\n") + b"\n\n" + raw(os.path.join(AI_TEMPLATES, "CLAUDE.block.md"))
            + b"\nOur text after the block.\n")
        put(self.path(".claude", "memory", "README.md"), raw(os.path.join(PI_TEMPLATES, "memory-README.md")))
        put(self.path("docs", "sdlc", "README.md"), raw(os.path.join(PI_TEMPLATES, "sdlc-README.md")))
        put(self.path(".gitignore"), raw(os.path.join(AI_TEMPLATES, "gitignore.snippet"))
            + raw(os.path.join(PI_TEMPLATES, "gitignore.snippet")))
        put(self.path(".ai", "policies", "weight.md"), W.mirror(W.load_policy(self.root)[0]).encode("utf-8"))

    def build_v3_1_0(self):
        self.lay("v3.1.0")

    def build_v3_1_0_edited(self):
        self.lay("v3.1.0")
        self.lay("v3.1.0-edited")

    def build_dual(self):
        self.lay("v3.1.0")
        self.lay("dual")

    # ---- helpers
    def path(self, *parts):
        return os.path.join(self.root, *parts)

    def commit(self, message):
        subprocess.run(GIT + ["-C", self.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.root, "commit", "-qm", message, "--allow-empty"], check=True)

    def status(self):
        return subprocess.run(["git", "-C", self.root, "status", "--porcelain"], capture_output=True, text=True,
                              check=True).stdout

    def update(self, *args, env=None):
        return subprocess.run([sys.executable, "-I", UPDATE, self.root] + list(args), env=env or self.env,
                              capture_output=True, text=True, check=False)

    def apply(self):
        """--apply --confirm-delete, as a human at a terminal (AI_UNATTENDED stands in for one)."""
        return self.update("--apply", "--confirm-delete", "tester", env=dict(self.env, AI_UNATTENDED="1"))

    def snap(self):
        return snapshot(self.root)

    def originals(self):
        found = glob.glob(self.path(".ai", "reports", "project-update-*", "original"))
        return found[0] if found else self.path("no-original-dir")

    def close(self):
        self.tmp.cleanup()


class Case(unittest.TestCase):
    def tree(self, kind):
        t = Tree(kind)
        self.addCleanup(t.close)
        return t


def block_of(data):
    found = render_instructions.find_block(data)
    return data[found[0]:found[1]]


def outside_block(data):
    found = render_instructions.find_block(data)
    return data[:found[0]], data[found[1]:]


class TestGenerated(Case):
    """R3: every GENERATED target ends byte-equal to its template, the managed block to its block template."""

    def test_every_template_file_is_classified(self):
        listed = set(paths.GENERATED) | set(paths.CREATE_ONLY) | set(paths.NOT_COPIED)
        for here, _dirs, names in os.walk(os.path.join(AI_TEMPLATES, ".ai")):
            for name in names:
                rel = os.path.relpath(os.path.join(here, name), AI_TEMPLATES).replace(os.sep, "/")
                with self.subTest(rel):
                    self.assertTrue(rel in listed or rel.startswith(paths.CREATE_ONLY_DIRS), rel)

    def test_generated_and_kept_are_disjoint(self):
        for rel in paths.GENERATED:
            self.assertFalse(paths.is_kept(rel), rel)
        for rel in paths.CREATE_ONLY:
            self.assertTrue(paths.is_kept(rel), rel)
        self.assertFalse(paths.is_kept(".ai/state/README.md"))
        self.assertTrue(paths.is_kept(".ai/state/state.json"))

    def test_generated_targets_equal_their_templates(self):
        for kind in TREES:
            with self.subTest(kind):
                t = self.tree(kind)
                done = t.apply()
                self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                for rel in paths.GENERATED:
                    self.assertEqual(raw(t.path(rel)), raw(os.path.join(AI_TEMPLATES, rel)), rel)
                self.assertEqual(raw(t.path(".ai", "VERSION")), raw(os.path.join(AI_TEMPLATES, ".ai", "VERSION")))
                self.assertEqual(t.apply().returncode, 0)
                self.assertEqual(raw(t.path(".ai", "policies", "weight.md")),
                                 W.mirror(W.load_policy(t.root)[0]).encode("utf-8"), "weight.md is the effective table")
                for rt, (name, block_tpl, _) in paths.INSTRUCTION_FILE.items():
                    if os.path.exists(t.path(name)):
                        self.assertEqual(block_of(raw(t.path(name))).rstrip(b"\n") + b"\n",
                                         raw(os.path.join(AI_TEMPLATES, block_tpl)), (name, rt))
                if os.path.isdir(t.path("docs", "sdlc")):
                    self.assertEqual(raw(t.path(".claude", "memory", "README.md")),
                                     raw(os.path.join(PI_TEMPLATES, "memory-README.md")))

    def test_an_old_shipped_copy_is_regenerated_without_a_gate(self):
        t = self.tree("v3.1.0")
        out = t.update().stdout
        for rel in (".ai/AGENTS.md", ".ai/policies/safety.md", ".ai/policies/testing.md", ".ai/state/README.md", ".ai/VERSION"):
            self.assertEqual(rows(out).get(rel), "regenerate", rel + "\n" + out)
        for rel in (".ai/policies/coding.md", ".ai/policies/path-guard.json"):
            self.assertNotIn(rel, rows(out), "unchanged since 3.1.0: nothing to do")
        self.assertNotIn("regenerate?", out)

    def test_the_fresh_scaffold_needs_nothing(self):
        t = self.tree("fresh")
        out = t.update().stdout
        self.assertEqual(rows(out), {}, out)
        self.assertEqual(t.update("--check").returncode, 0)


class TestKept(Case):
    """R4, R14, R18: a KEPT path is sha-identical after any run; the text outside a managed block too."""

    def test_kept_byte_identical(self):
        for kind in TREES:
            with self.subTest(kind):
                t = self.tree(kind)
                before = t.snap()
                kept = {rel: data for rel, data in before.items() if paths.is_kept(rel)}
                kept.update({rel: before[rel] for rel in before if rel == ".ai/policies/git.md"})  # an edited shared override
                self.assertGreater(len(kept), 5, "the tree holds kept files")
                for confirm in (False, True):
                    done = t.apply() if confirm else t.update("--apply")
                    self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
                    now = t.snap()
                    for rel, data in kept.items():
                        if rel == ".gitignore":
                            self.assertTrue(now[rel].startswith(data), "append-only")
                        elif rel in now or confirm is False:
                            self.assertEqual(now.get(rel), data, rel)
                for name in ("CLAUDE.md", "AGENTS.md"):
                    if name in before:
                        self.assertEqual(outside_block(t.snap()[name]), outside_block(before[name]), name)

    def test_dialog_and_memory_json(self):
        t = self.tree("v3.1.0-edited")
        os.remove(t.path(".ai", "policies", "dialog.json"))
        memory = raw(t.path(".ai", "policies", "memory.json"))
        t.apply()
        self.assertFalse(os.path.exists(t.path(".ai", "policies", "dialog.json")), "absent stays absent")
        self.assertEqual(raw(t.path(".ai", "policies", "memory.json")), memory)
        bare = self.tree("v3.1.0")
        bare.apply()
        self.assertFalse(os.path.exists(bare.path(".ai", "policies", "memory.json")), "absent stays absent")
        self.assertTrue(os.path.exists(bare.path(".ai", "policies", "dialog.json")))

    def test_local_memory_untouched(self):
        t = self.tree("v3.1.0-edited")
        config = raw(t.path(".ai", "local", "memory", "config.json"))
        out = t.apply().stdout
        self.assertEqual(raw(t.path(".ai", "local", "memory", "config.json")), config)
        self.assertFalse(os.path.exists(t.path(".ai", "local", "plugin-update")), "R18: the old cache is removed\n" + out)

    def test_nothing_outside_the_listed_sets_is_written(self):
        t = self.tree("v3.1.0-edited")
        put(t.path("src", "app.py"), "print(1)\n")
        before = t.snap()
        t.apply()
        self.assertEqual(t.snap()["src/app.py"], before["src/app.py"])


class TestIdempotent(Case):
    """R5: a second --apply plans nothing, --check exits 0, git has nothing to report."""

    def test_second_apply_is_empty(self):
        for kind in TREES:
            with self.subTest(kind):
                t = self.tree(kind)
                self.assertEqual(t.apply().returncode, 0)
                t.commit("updated")
                again = t.apply()
                self.assertEqual(rows(again.stdout), {}, again.stdout)
                self.assertIn("up to date with the installed plugin", again.stdout)
                self.assertEqual(t.update("--check").returncode, 0)
                self.assertEqual(t.status(), "", t.status())


class TestDryRun(Case):
    """R6: nothing is written; one row per action with its reason; an edited file's row names what it loses."""

    def test_dry_run_writes_nothing(self):
        for kind in TREES:
            with self.subTest(kind):
                t = self.tree(kind)
                before = digest(t.snap())
                self.assertEqual(t.update().returncode, 0)
                self.assertEqual(digest(t.snap()), before)
                self.assertEqual(t.update("--check").returncode, 1 if kind != "fresh" else 0)
                self.assertEqual(digest(t.snap()), before)

    def test_the_rows_of_an_edited_tree(self):
        t = self.tree("v3.1.0-edited")
        out = t.update().stdout
        found = rows(out)
        expected = {".ai/policies/verification.md": "split", ".ai/policies/weight.project.json": "split",
                    ".ai/policies/testing.md": "regenerate?", ".ai/policies/coding.md": "regenerate?",
                    ".ai/policies/path-guard.json": "regenerate?", ".ai/AGENTS.md": "regenerate?",
                    "CLAUDE.md": "regenerate?", ".ai/policies/weight.json": "delete?",
                    ".ai/rules/php-style.md": "delete?", ".ai/policies/tooling.md": "delete?",
                    ".ai/local/plugin-update/.ai/policies/coding.md": "delete?", ".ai/VERSION": "regenerate",
                    }
        for target, action in expected.items():
            self.assertEqual(found.get(target), action, target + "\n" + out)
        gated = {x.split()[1]: x for x in out.splitlines() if x.startswith("  regenerate?")}
        line = gated[".ai/policies/path-guard.json"]
        self.assertIn("drops 3 deny/allow pattern(s)", line)
        self.assertIn("original kept at .ai/reports/project-update-", line)
        self.assertIn("Money is integer cents", gated[".ai/policies/coding.md"], "the row names the line it loses")
        self.assertIn("awaiting --confirm-delete", out)

    def test_an_unconfirmed_apply_keeps_every_edited_file(self):
        t = self.tree("v3.1.0-edited")
        before = t.snap()
        self.assertEqual(t.update("--apply").returncode, 0)
        now = t.snap()
        for rel in (".ai/policies/testing.md", ".ai/policies/coding.md", ".ai/policies/path-guard.json", ".ai/AGENTS.md",
                    ".ai/policies/weight.json", ".ai/rules/php-style.md", ".ai/policies/tooling.md"):
            self.assertEqual(now[rel], before[rel], rel)
        self.assertEqual(now["CLAUDE.md"], before["CLAUDE.md"], "an edited block waits")
        self.assertFalse(glob.glob(t.path(".ai", "reports", "project-update-*", "original")))


class TestGate(Case):
    """R7, R16, R29: an edited generated file and every removal wait for a human; the original is kept."""

    def test_confirmed_run_keeps_the_originals(self):
        t = self.tree("v3.1.0-edited")
        before = t.snap()
        done = t.apply()
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        for rel in (".ai/policies/testing.md", ".ai/policies/coding.md", ".ai/policies/path-guard.json", ".ai/AGENTS.md",
                    ".ai/policies/weight.json", ".ai/rules/php-style.md", ".ai/policies/tooling.md",
                    ".ai/local/plugin-update/.ai/policies/coding.md", "CLAUDE.md"):
            self.assertEqual(raw(os.path.join(t.originals(), rel)), before[rel], rel)
        for rel in (".ai/policies/weight.json", ".ai/rules/php-style.md", ".ai/policies/tooling.md"):
            self.assertFalse(os.path.exists(t.path(rel)), rel)
        self.assertEqual(raw(t.path(".ai", "policies", "git.md")), before[".ai/policies/git.md"], "an edited override stays")
        rec = json.loads(raw(glob.glob(t.path(".ai", "reports", "project-update-*", "migration.json"))[0]))
        self.assertEqual(rec["deletions"][0]["confirmed_by"], "tester")
        self.assertEqual(rec["deletions"][0]["via"], "unattended")

    def test_rule_source_gated(self):
        t = self.tree("v3.1.0-edited")
        source = raw(t.path(".ai", "rules", "php-style.md"))
        self.assertEqual(t.update("--apply").returncode, 0)
        self.assertEqual(raw(t.path(".ai", "rules", "php-style.md")), source, "unconfirmed: the source stays")
        self.assertIn(b"riskrails:rule:php-style:start", raw(t.path("src", "CLAUDE.md")), "and stays rendered")
        self.assertEqual(t.apply().returncode, 0)
        self.assertFalse(os.path.exists(t.path(".ai", "rules", "php-style.md")))
        self.assertEqual(raw(os.path.join(t.originals(), ".ai", "rules", "php-style.md")), source)
        self.assertNotIn(b"riskrails:rule:php-style", raw(t.path("src", "CLAUDE.md")), "the rendered block goes with it")
        self.assertTrue(os.path.exists(t.path(".ai", "rules", "README.md")), "the README is regenerated, not removed")

    def test_refused_token(self):
        t = self.tree("v3.1.0-edited")
        before = digest(t.snap())
        agent = dict(t.env, CLAUDECODE="1")
        done = t.update("--apply", "--confirm-delete", "tester", env=agent)
        self.assertEqual(done.returncode, 5)
        self.assertTrue(done.stdout.splitlines()[0].startswith("CONFIRM_REFUSED:"), done.stdout)
        self.assertNotIn("ADOPT_REFUSED", done.stdout)
        self.assertEqual(digest(t.snap()), before)
        placeholder = t.update("--apply", "--confirm-delete", "<your name>", env=dict(t.env, AI_UNATTENDED="1"))
        self.assertEqual(placeholder.returncode, 2)

    def test_a_confirm_flag_needs_apply(self):
        t = self.tree("v3.1.0")
        self.assertEqual(t.update("--confirm-delete", "tester").returncode, 2)


class TestSplitOnce(Case):
    """R11: verification.md and weight.project.json are made once, when absent; then the old files are not read."""

    def test_the_split(self):
        t = self.tree("v3.1.0-edited")
        old = raw(t.path(".ai", "policies", "testing.md")).decode()
        out = t.update("--apply").stdout
        self.assertEqual(rows(out)[".ai/policies/verification.md"], "split")
        verification = raw(t.path(".ai", "policies", "verification.md")).decode()
        for line in ("verify_command:      python3 -m unittest discover -s tests",
                     "step_test_command:   python3 -m unittest {files}",
                     "                     # continuation line kept with its field", "e2e_command:         none"):
            self.assertIn(line + "\n", verification, line)
        self.assertIn("## Project specifics", verification)
        self.assertIn("Our CI runs tests/ on every push; fixtures live in tests/data.", verification)
        self.assertEqual(old, raw(t.path(".ai", "policies", "testing.md")).decode(), "unconfirmed: testing.md waits")
        doc = json.loads(raw(t.path(".ai", "policies", "weight.project.json")))
        self.assertEqual(doc["version"], 1)
        self.assertEqual(doc["tests"], {"max_suite_runs": 7})
        self.assertEqual(doc["domain"], {"modules": ["**/Payment/**"]})
        self.assertEqual(doc["scope"], {"hot_paths": ["src/Checkout/**"]})
        self.assertIn("this shop: a banner colour", doc["examples"]["light"], "a list is carried whole")
        self.assertGreater(len(doc["examples"]["light"]), 1)
        self.assertEqual(sorted(doc), ["_comment", "domain", "examples", "scope", "tests", "version"],
                         "leaves equal to the plugin's table are not carried")
        self.assertTrue(os.path.exists(t.path(".ai", "policies", "weight.json")), "its removal is gated")
        self.assertIn("carried", out)

    def test_the_second_run_has_no_split_row(self):
        t = self.tree("v3.1.0-edited")
        self.assertEqual(t.update("--apply").returncode, 0)
        verification = raw(t.path(".ai", "policies", "verification.md"))
        weight = raw(t.path(".ai", "policies", "weight.project.json"))
        put(t.path(".ai", "policies", "testing.md"), "verify_command: something else entirely\n")
        old = json.loads(raw(t.path(".ai", "policies", "weight.json")))
        old["tests"]["max_suite_runs"] = 99
        put(t.path(".ai", "policies", "weight.json"), json.dumps(old))
        second = t.update("--apply").stdout
        self.assertNotIn("split", rows(second).values(), second)
        self.assertEqual(raw(t.path(".ai", "policies", "verification.md")), verification, "never read again")
        self.assertEqual(raw(t.path(".ai", "policies", "weight.project.json")), weight)
        self.assertEqual(rows(second).get(".ai/policies/weight.json"), "delete?", "still offered for removal")

    def test_a_pristine_tree_splits_to_the_templates_values(self):
        t = self.tree("v3.1.0")
        out = t.update("--apply").stdout
        self.assertEqual(rows(out)[".ai/policies/verification.md"], "split", "the field lines are copied")
        doc = json.loads(raw(t.path(".ai", "policies", "weight.project.json")))
        self.assertEqual(sorted(doc), ["_comment", "version"], "nothing differs from the shipped table")
        policy = W.load_policy(t.root)[0]
        policy.pop("_comment")
        self.assertEqual(policy, json.loads(raw(os.path.join(AI_TEMPLATES, ".ai", "policies", "weight.json"))))

    def test_scaffold_then_update_still_splits(self):
        """H1: /rr-setup runs the scaffold over an old tree before --update; the split must still carry the project."""
        t = self.tree("v3.1.0-edited")
        env = dict(t.env, RISKRAILS_TEMPLATES=AI_TEMPLATES)
        subprocess.run(["bash", os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh"), t.root], env=env,
                       capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
        out = t.update("--apply").stdout
        self.assertEqual(rows(out).get(".ai/policies/verification.md"), "split", out)
        self.assertEqual(rows(out).get(".ai/policies/weight.project.json"), "split", out)
        self.assertIn("verify_command:      python3 -m unittest discover -s tests",
                      raw(t.path(".ai", "policies", "verification.md")).decode())
        doc = json.loads(raw(t.path(".ai", "policies", "weight.project.json")))
        self.assertEqual(doc["domain"], {"modules": ["**/Payment/**"]})

    def test_a_pristine_template_target_is_split_when_the_old_file_has_leaves(self):
        """H1, second guard: a target equal to its shipped template counts as absent -- and only then."""
        t = self.tree("v3.1.0-edited")
        for rel in ("verification.md", "weight.project.json"):
            shutil.copyfile(os.path.join(AI_TEMPLATES, ".ai", "policies", rel), t.path(".ai", "policies", rel))
        out = t.update("--apply").stdout
        self.assertEqual(rows(out)[".ai/policies/weight.project.json"], "split", out)
        self.assertEqual(rows(out)[".ai/policies/verification.md"], "split", out)
        self.assertEqual(json.loads(raw(t.path(".ai", "policies", "weight.project.json")))["tests"],
                         {"max_suite_runs": 7})
        self.assertEqual(rows(t.update("--apply").stdout).get(".ai/policies/weight.project.json"), None,
                         "the second run has no split row")

    def test_a_fresh_pristine_tree_invents_no_split(self):
        t = self.tree("fresh")
        self.assertNotIn("split", rows(t.update("--apply").stdout).values())

    def test_an_existing_new_file_is_never_overwritten(self):
        t = self.tree("fresh")
        put(t.path(".ai", "policies", "testing.md"), "verify_command: other\n")
        before = t.snap()
        t.update("--apply")
        for rel in (".ai/policies/verification.md", ".ai/policies/weight.project.json"):
            self.assertEqual(t.snap()[rel], before[rel])


class TestRefusal(Case):
    """R12, R13: a kept file its reader cannot take, or an old shape, refuses the whole run (exit 6)."""

    def cases(self):
        invalid = b"{not json"
        return [
            ("state.json invalid", ".ai/state/state.json", invalid),
            ("state.json a list", ".ai/state/state.json", b"[1]"),
            ("weight.project.json invalid", ".ai/policies/weight.project.json", invalid),
            ("weight.project.json version", ".ai/policies/weight.project.json", b'{"version": 2}'),
            ("weight.project.json axes", ".ai/policies/weight.project.json", b'{"version": 1, "axes": 5}'),
            ("verification.md not utf-8", ".ai/policies/verification.md", b"\xff\xfe\x00"),
            ("dialog.json", ".ai/policies/dialog.json", invalid),
            ("memory.json", ".ai/policies/memory.json", b'"text"'),
            ("settings.json", ".claude/settings.json", invalid),
            ("config.toml", ".codex/config.toml", b"[broken\nx ="),
            ("old weight.json", ".ai/policies/weight.json", invalid),
            ("current.json without state.json", ".ai/state/current.json", b"{}"),
            ("claude-agentic markers", "CLAUDE.md", b"<!-- claude-agentic:start -->\nx\n<!-- claude-agentic:end -->\n"),
            ("Codex-agentic markers", "AGENTS.md", b"<!-- Codex-agentic:start -->\nx\n<!-- Codex-agentic:end -->\n"),
        ]

    def test_each_reader_and_old_shape(self):
        for label, rel, content in self.cases():
            with self.subTest(label):
                t = self.tree("v3.1.0")
                put(t.path(rel), content)
                before = digest(t.snap())
                for args in ((), ("--apply",), ("--check",)):
                    done = t.update(*args)
                    self.assertEqual(done.returncode, 6, "%s %s\n%s%s" % (label, args, done.stdout, done.stderr))
                    first = done.stdout.splitlines()[0]
                    self.assertTrue(first.startswith("KEPT_UNREADABLE: %s: " % rel), first)
                    self.assertIn("project-update: nothing was deleted or written. This version regenerates its own "
                                  "files and no longer converts older ones.", done.stdout)
                    self.assertEqual(digest(t.snap()), before, "nothing written")
                confirmed = t.apply()
                self.assertEqual(confirmed.returncode, 6)
                self.assertEqual(digest(t.snap()), before)

    def test_risk_tiers_without_a_weight_table(self):
        t = self.tree("v3.1.0")
        os.remove(t.path(".ai", "policies", "weight.json"))
        put(t.path(".ai", "policies", "risk-tiers.json"), "{}\n")
        done = t.update("--apply")
        self.assertEqual(done.returncode, 6, done.stdout)
        self.assertTrue(done.stdout.startswith("KEPT_UNREADABLE: .ai/policies/risk-tiers.json: "))

    def test_names_version(self):
        self.assertEqual(paths.LAST_MIGRATING_VERSION, "3.1.0")
        t = self.tree("v3.1.0")
        put(t.path(".ai", "state", "state.json"), "nope")
        out = t.update().stdout
        self.assertIn("Install riskrails@%s (npx riskrails@%s), run /rr-setup --update with it, then install this "
                      "version and run /rr-setup --update again." % (paths.LAST_MIGRATING_VERSION, paths.LAST_MIGRATING_VERSION), out)

    def test_every_failing_file_has_its_line(self):
        t = self.tree("v3.1.0")
        put(t.path(".ai", "state", "state.json"), "nope")
        put(t.path(".ai", "policies", "memory.json"), "nope")
        lines = [x for x in t.update().stdout.splitlines() if x.startswith("KEPT_UNREADABLE")]
        self.assertEqual(len(lines), 2)

    def test_a_task_in_flight_is_a_hint_not_a_refusal(self):
        t = self.tree("v3.1.0-edited")
        done = t.update()
        self.assertEqual(done.returncode, 0)
        self.assertIn("a task is in flight while files are regenerated", done.stdout)

    def test_a_newer_schema_is_exit_2(self):
        t = self.tree("fresh")
        put(t.path(".ai", "VERSION"), "99\n")
        done = t.update()
        self.assertEqual(done.returncode, 2)
        self.assertIn("schema 99", done.stderr)


class TestBlock(Case):
    """R15: the managed block is rewritten between its markers, appended when missing, created with its file."""

    def test_rewritten_between_the_markers(self):
        t = self.tree("v3.1.0-edited")
        before = raw(t.path("CLAUDE.md"))
        t.apply()
        after = raw(t.path("CLAUDE.md"))
        self.assertTrue(after.startswith(b"# "))
        self.assertEqual(outside_block(after), outside_block(before))
        self.assertIn(b"Our text before the block.", after)
        self.assertNotIn(b"our own line inside the block", after)
        self.assertEqual(block_of(after).rstrip(b"\n") + b"\n", raw(os.path.join(AI_TEMPLATES, "CLAUDE.block.md")))

    def test_an_unedited_old_block_needs_no_gate(self):
        t = self.tree("v3.1.0")
        current = raw(os.path.join(AI_TEMPLATES, "CLAUDE.block.md"))
        older = [v for v in history.History(paths.HISTORY).versions("ai-init/CLAUDE.block.md") if v != current and b"<!-- riskrails:start -->" in v]
        self.assertTrue(older, "the history holds an older block")
        text = raw(t.path("CLAUDE.md"))
        found = render_instructions.find_block(text)
        put(t.path("CLAUDE.md"), text[:found[0]] + older[0].rstrip(b"\n") + text[found[1]:])
        out = t.update().stdout
        self.assertEqual(rows(out).get("CLAUDE.md"), "regenerate", out)
        self.assertNotIn("regenerate?", out)

    def test_appended_when_there_is_none(self):
        t = self.tree("fresh")
        put(t.path("CLAUDE.md"), "# Mine\n\nOnly my text.\n")
        out = t.update("--apply").stdout
        self.assertEqual(rows(out).get("CLAUDE.md"), "regenerate")
        text = raw(t.path("CLAUDE.md"))
        self.assertTrue(text.startswith(b"# Mine\n\nOnly my text.\n"))
        self.assertEqual(text[text.index(b"<!-- riskrails:start"):].rstrip(b"\n") + b"\n",
                         raw(os.path.join(AI_TEMPLATES, "CLAUDE.block.md")))

    def test_created_with_its_file(self):
        t = self.tree("fresh")
        os.remove(t.path("CLAUDE.md"))
        t.update("--apply")
        text = raw(t.path("CLAUDE.md"))
        self.assertTrue(text.startswith(b"# p\n"), text[:40])
        self.assertIn(b"<!-- riskrails:start -->", text)

    def test_dual_runtime_has_one_block_per_file(self):
        t = self.tree("dual")
        t.apply()
        for name, tpl in (("CLAUDE.md", "CLAUDE.block.md"), ("AGENTS.md", "AGENTS.block.md")):
            self.assertEqual(block_of(raw(t.path(name))).rstrip(b"\n") + b"\n", raw(os.path.join(AI_TEMPLATES, tpl)), name)


class TestShared(Case):
    """R17: an unedited shared copy is offered for deletion; an edited one stays, with one hint."""

    def test_set_equals_the_plugins_tree(self):
        found = set()
        for here, _dirs, names in os.walk(os.path.join(ROOT, "ai")):
            for name in names:
                found.add(".ai/" + os.path.relpath(os.path.join(here, name), os.path.join(ROOT, "ai")).replace(os.sep, "/"))
        self.assertEqual(set(paths.SHARED_SET), found)

    def test_unedited_and_edited_copies(self):
        t = self.tree("v3.1.0-edited")
        out = t.update().stdout
        self.assertEqual(rows(out).get(".ai/policies/tooling.md"), "delete?")
        self.assertNotIn(".ai/policies/git.md", rows(out))
        self.assertIn("override the plugin's shared copy", out)
        self.assertIn(".ai/policies/git.md", out)
        t.apply()
        self.assertFalse(os.path.exists(t.path(".ai", "policies", "tooling.md")))
        self.assertTrue(os.path.exists(t.path(".ai", "policies", "git.md")))


if __name__ == "__main__":
    unittest.main()
