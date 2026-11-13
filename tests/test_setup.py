"""setup.py (redesign 2.5): R9 — `check` exits 1 VERIFY_COMMAND_MISSING; R10 — the
verify command lives in .ai/policies/verification.md; R28 — the superpowers line is
printed and never written; SQ5 — the toolbox is inventoried in place, never copied;
OQ3 — there is no `adopt` verb.

The project is tests/fixtures/setup/new-shop-like, stored encoded
(`dot-claude` → `.claude`, `fixture-CLAUDE.md` → `CLAUDE.md`) and scaffolded with
the plugin's own scripts, the way the update tests build their fixtures.

`options --json` (spec interactive-setup-options R9, R16) is TestOptions, TestOptionsMemory and
TestOptionsSignals; `options --open` (R10, R16, R17) is TestOptionsOpen: they build their own small projects, and
the environment their runs see.
"""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "skills", "rr-setup", "setup.py")
SCAFFOLD = os.path.join(ROOT, "skills", "rr-setup", "scaffold_ai.py")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "setup", "new-shop-like")
OVERVIEW_TEMPLATE = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "project", "overview.md")
HISTORY = os.path.join(ROOT, "skills", "project-update", "history")
NOT_COPIED = {"README.md", "fixture.json"}
# What `--runtime auto` falls back to on a project that declares no runtime: the one this copy is installed for.
INSTALLED = "codex" if "/.codex/" in SETUP else "claude"


def decode(rel):
    rel = re.sub(r"(^|/)dot-", r"\1.", rel)
    return re.sub(r"(^|/)fixture-([A-Z]+\.md)$", r"\1\2", rel)


def tree_sha(root):
    digest = hashlib.sha256()
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            path = os.path.join(base, name)
            digest.update(os.path.relpath(path, root).encode())
            with open(path, "rb") as fh:
                digest.update(fh.read())
    return digest.hexdigest()


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def snapshot(top):
    """Every entry under `top`, .git/ included, with what a write would change: bytes, size, mtime and mode —
    a directory's mtime moves when a file is created in it, even one that is removed again."""
    seen = {}
    for base, dirs, files in os.walk(top):
        for name in dirs + files:
            path = os.path.join(base, name)
            info = os.lstat(path)
            body = None
            if os.path.islink(path):
                body = os.readlink(path)
            elif os.path.isfile(path):
                body = hashlib.sha256(read_bytes(path)).hexdigest()
            seen[os.path.relpath(path, top)] = (info.st_mode, info.st_size, info.st_mtime_ns, body)
    return seen


def load_setup():
    """setup.py as a module of this process, for the functions that need no sibling module and no project."""
    spec = importlib.util.spec_from_file_location("rr_setup_under_test", SETUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Project(unittest.TestCase):
    """A scaffolded copy of the fixture, and a CLAUDE_CONFIG_DIR of its own so
    the developer's real settings never decide a result."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="setup py ")
        self.root = os.path.join(self.tmp, "shop")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        for script in (["bash", os.path.join(ROOT, "hooks", "project-scaffold.sh")],
                       ["bash", os.path.join(ROOT, "skills", "ai-init", "scaffold-ai.sh")]):
            os.makedirs(self.root, exist_ok=True)
            subprocess.run(script + [self.root, "--runtime", "claude"], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with open(os.path.join(FIXTURE, "fixture.json"), encoding="utf-8") as fh:
            append = json.load(fh).get("instruction_append", {})
        for base, _dirs, files in os.walk(FIXTURE):
            for name in files:
                src = os.path.join(base, name)
                rel = os.path.relpath(src, FIXTURE).replace(os.sep, "/")
                if rel in NOT_COPIED:
                    continue
                dst = os.path.join(self.root, decode(rel))
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if decode(rel) in append:
                    with open(src, encoding="utf-8") as fh, open(dst, "a", encoding="utf-8") as out:
                        out.write(fh.read())
                else:
                    shutil.copy2(src, dst)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_setup(self, *args):
        env = dict(os.environ, CLAUDE_CONFIG_DIR=self.home)
        return subprocess.run([sys.executable, "-I", SETUP] + list(args) + ["--root", self.root],
                              capture_output=True, text=True, env=env, check=False)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def read(self, rel):
        with open(self.path(rel), encoding="utf-8") as fh:
            return fh.read()

    def write(self, rel, text):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def set_verify(self, value):
        text = self.read(".ai/policies/verification.md")
        self.write(".ai/policies/verification.md", re.sub(r"(?m)^verify_command:.*$", "verify_command: " + value, text))


class TestCheck(Project):
    """R9: no verify_command, no setup."""

    def test_template_line_is_missing(self):
        result = self.run_setup("check")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertTrue(result.stdout.startswith("VERIFY_COMMAND_MISSING"), result.stdout)

    def test_none_is_missing(self):
        self.set_verify("none")
        result = self.run_setup("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("VERIFY_COMMAND_MISSING", result.stdout)

    def test_no_verification_md_is_missing(self):
        os.remove(self.path(".ai/policies/verification.md"))
        result = self.run_setup("check")
        self.assertEqual(result.returncode, 1)
        self.assertIn("VERIFY_COMMAND_MISSING", result.stdout)

    def test_a_command_passes(self):
        self.set_verify("make test")
        result = self.run_setup("check")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(result.stdout.strip(), "verify_command: make test")


class TestVerifySet(Project):
    """`verify --set` writes the line only where none is set; a set one is the human's."""

    def test_set_then_refuse(self):
        result = self.run_setup("verify", "--set", "make test")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(self.read(".ai/policies/verification.md"), r"(?m)^verify_command:\s+make test$")
        self.assertEqual(self.run_setup("check").returncode, 0)
        again = self.run_setup("verify", "--set", "composer test")
        self.assertEqual(again.returncode, 3)
        self.assertRegex(self.read(".ai/policies/verification.md"), r"(?m)^verify_command:\s+make test$")

    def test_testing_md_is_not_the_source(self):
        """R10 / OQ4: a verify_command in testing.md is not read, and `--set` writes verification.md only."""
        self.write(".ai/policies/testing.md", "verify_command: make test\n")
        self.assertEqual(self.run_setup("check").returncode, 1)
        self.assertEqual(self.run_setup("verify", "--set", "composer test").returncode, 0)
        self.assertRegex(self.read(".ai/policies/verification.md"), r"(?m)^verify_command:\s+composer test$")
        self.assertEqual(self.read(".ai/policies/testing.md"), "verify_command: make test\n")

    def test_no_verify_command_line_is_refused(self):
        self.write(".ai/policies/verification.md", "# Verification\n")
        result = self.run_setup("verify", "--set", "make test")
        self.assertEqual(result.returncode, 2)
        self.assertIn("verification.md has no verify_command line", result.stderr)

    def test_two_lines_refused(self):
        result = self.run_setup("verify", "--set", "make test\nrm -rf /")
        self.assertEqual(result.returncode, 2)


class TestSurvey(Project):
    """SQ5: the inventory, the proposal and the superpowers line; nothing written."""

    def test_inventory_and_proposal(self):
        before = tree_sha(self.root)
        result = self.run_setup("survey")
        self.assertEqual(result.returncode, 0, result.stderr)
        out = result.stdout
        for line in ("skill    .claude/skills/deploy-staging/SKILL.md:3 — Deploy the current branch to staging",
                     "skill    .claude/skills/sylius-fixtures/SKILL.md:3 — Load the Sylius fixture suite",
                     "command  .claude/commands/release-notes.md:1 — Draft the release notes",
                     "rule     .claude/rules/doctrine.md:5 — Doctrine entities | migrations",
                     "agent    .claude/agents/php-reviewer.md:3 — Reviews PHP changes",
                     "hook     .claude/hooks/block-git-push.sh:2 — Refuse git push from an agent session.",
                     "hook     .claude/hooks/format-php.sh:3 — Run php-cs-fixer on the edited file.",
                     "script   bin/run-tests.sh:2 — PHPUnit, then Behat",
                     "script   bin/deploy.sh — UNKNOWN",
                     "make     Makefile:5 up — Start the containers",
                     "make     Makefile:9 qa — Static analysis and coding standard",
                     "make     Makefile:12 test — The fast suite, e2e excluded",
                     "guard    ai-git-guard: .claude/hooks/block-git-push.sh (same job, kept)",
                     "guard    ai-path-guard: no project hook",
                     "verify_command: proposed `make test` (from Makefile test)",
                     "also     `composer test` (from composer.json test)",
                     "also     `bin/run-tests.sh` (from bin/run-tests.sh run-tests)"):
            self.assertIn(line, out)
        self.assertNotIn("post-install-cmd", out)
        self.assertEqual(tree_sha(self.root), before, "survey wrote a file")

    def test_set_command_is_reported_not_proposed(self):
        self.set_verify("make test")
        out = self.run_setup("survey").stdout
        self.assertIn("verify_command: make test (verification.md)", out)

    def test_foreign_tool_paths_are_not_own(self):
        self.write(".claude/skills/speckit-plan/SKILL.md", "---\ndescription: Spec Kit plan\n---\n")
        out = self.run_setup("survey").stdout
        self.assertNotIn("speckit-plan", out)


class TestSuperpowers(Project):
    """R28: printed, never written."""

    def test_not_enabled_prints_the_line(self):
        before = tree_sha(self.root)
        out = self.run_setup("survey").stdout
        self.assertIn('superpowers: not enabled — optional; to enable it, add to .claude/settings.json yourself: '
                      '"enabledPlugins": {"superpowers@superpowers-marketplace": true}', out)
        self.assertEqual(tree_sha(self.root), before)
        self.assertEqual(os.listdir(self.home), [])

    def test_enabled_user_wide(self):
        with open(os.path.join(self.home, "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"enabledPlugins": {"superpowers@superpowers-marketplace": True}}, fh)
        out = self.run_setup("survey").stdout
        self.assertRegex(out, r"(?m)^superpowers: enabled in .*settings\.json \(superpowers@superpowers-marketplace\)")

    def test_project_disables_it(self):
        with open(os.path.join(self.home, "settings.json"), "w", encoding="utf-8") as fh:
            json.dump({"enabledPlugins": {"superpowers@superpowers-marketplace": True}}, fh)
        self.write(".claude/settings.local.json", json.dumps({"enabledPlugins": {"superpowers@x": False}}))
        out = self.run_setup("survey").stdout
        self.assertIn("superpowers: not enabled (disabled in", out)


class TestNoAdopt(Project):
    """OQ3: `setup.py adopt` is gone; argparse refuses the unknown verb and nothing is written."""

    def test_adopt_is_an_unknown_verb(self):
        before = tree_sha(self.root)
        for extra in ((), ("--apply",)):
            with self.subTest(extra=extra):
                result = self.run_setup("adopt", *extra)
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("invalid choice: 'adopt'", result.stderr)
        self.assertEqual(tree_sha(self.root), before)
        self.assertFalse(os.path.exists(self.path(".ai/policies/toolbox.md")))


class TestReviewFindings(Project):
    """T-2026-10-26-004 review M1–M3, L1–L3: each pinned on the tree that had it."""

    def test_block_scalar_description(self):  # M1
        self.write(".claude/skills/folded/SKILL.md",
                   "---\nname: folded\ndescription: >-\n  Build the catalogue\n  search index.\n---\n")
        out = self.run_setup("survey").stdout
        self.assertIn("skill    .claude/skills/folded/SKILL.md:4 — Build the catalogue search index.", out)
        self.assertNotIn(">-", out)

    def test_mirrored_skill_is_one_route(self):  # M2
        self.write(".agents/skills/deploy-staging/SKILL.md", self.read(".claude/skills/deploy-staging/SKILL.md"))
        self.write(".claude/commands/sylius-fixtures.md", "# Load fixtures, the command form\n")
        out = self.run_setup("survey").stdout
        self.assertIn("skill    .agents/skills/deploy-staging/SKILL.md", out)
        self.assertIn("skill    .claude/skills/deploy-staging/SKILL.md", out)
        self.assertIn("command  .claude/commands/sylius-fixtures.md", out)

    def test_symlinked_skill_directory(self):  # M3
        self.write("shared/skills/linked/SKILL.md", "---\ndescription: A skill shared between shops\n---\n")
        os.symlink(os.path.join("..", "..", "shared", "skills", "linked"), self.path(".claude/skills/linked"))
        out = self.run_setup("survey").stdout
        self.assertIn("skill    .claude/skills/linked/SKILL.md:2 — A skill shared between shops", out)

    def test_link_out_of_the_project_is_not_read(self):  # register #52
        outside = os.path.join(self.tmp, "secret.sh")
        with open(outside, "w", encoding="utf-8") as fh:
            fh.write("# SECRET-MARKER-52\necho hi\n")
        os.symlink(outside, self.path(".claude/hooks/linked-out.sh"))
        self.write(".claude/hooks/.hidden.sh", "# HIDDEN-MARKER-52\n")
        survey = self.run_setup("survey").stdout
        self.assertNotIn("SECRET-MARKER-52", survey)
        self.assertNotIn("HIDDEN-MARKER-52", survey)

    def test_crlf_symlink_and_mode_survive(self):  # L2
        testing = self.path(".ai/policies/verification.md")
        shared = self.path("shared/verification.md")
        os.makedirs(os.path.dirname(shared), exist_ok=True)
        with open(testing, encoding="utf-8") as fh:
            text = fh.read()
        with open(shared, "w", encoding="utf-8", newline="") as fh:
            fh.write(text.replace("\n", "\r\n"))
        os.chmod(shared, 0o640)
        os.remove(testing)
        os.symlink(shared, testing)
        self.assertEqual(self.run_setup("verify", "--set", "make test").returncode, 0)
        self.assertTrue(os.path.islink(testing))
        with open(shared, "rb") as fh:
            raw = fh.read()
        self.assertIn(b"verify_command:      make test\r\n", raw)
        self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))
        self.assertEqual(os.stat(shared).st_mode & 0o777, 0o640)
        self.assertEqual([n for n in os.listdir(os.path.dirname(testing)) if "tmp" in n], [])

    def test_multi_target_make_line(self):  # L3
        with open(self.path("Makefile"), "a", encoding="utf-8") as fh:
            fh.write("\nlint cs: ## Coding standard\n\tvendor/bin/phpcs\n")
        out = self.run_setup("survey").stdout
        self.assertIn(" lint — Coding standard", out)
        self.assertIn(" cs — Coding standard", out)


class OptionsProject(unittest.TestCase):
    """A project built by hand for `options`, and the environment its runs see: USER, HOME, git's config and the
    agent markers are set here, so nothing of the developer's or of a running agent decides a result."""

    # An overview.md a survey has written into: the shipped template and a labelled statement.
    SURVEYED = read_bytes(OVERVIEW_TEMPLATE) + b"\n- Stack: Symfony 6.4 (composer.json:12)\n"

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="options ")
        self.root = os.path.join(self.tmp, "shop")
        self.home = os.path.join(self.tmp, "home")
        os.makedirs(self.home)
        own = ("CLAUDECODE", "USER", "USERNAME", "HOME", "XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR")
        self.env = {k: v for k, v in os.environ.items()
                    if k not in own and not k.startswith(("AI_", "CODEX_", "CLAUDE_CODE_", "GIT_"))}
        self.env.update(USER="tester", HOME=self.home, XDG_CONFIG_HOME=self.home, CLAUDE_CONFIG_DIR=self.home,
                        AI_RUNTIME="claude", AI_MEMORY_NO_FTS="1", GIT_CONFIG_NOSYSTEM="1",
                        GIT_CEILING_DIRECTORIES=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def path(self, rel):
        return os.path.join(self.root, rel)

    def write(self, rel, data):
        os.makedirs(os.path.dirname(self.path(rel)), exist_ok=True)
        with open(self.path(rel), "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))

    def git_init(self):
        subprocess.run(["git", "init", "-q", self.root], check=True, capture_output=True, env=self.env)

    def build(self, git=True):
        """A project by hand: the two files the options read, as the scaffold writes them — a comment-only
        verify_command and the unedited overview.md."""
        self.write(".ai/policies/verification.md",
                   "# Verification\n\nverify_command:      # the fast suite, e2e excluded\n")
        self.write(".ai/project/overview.md", read_bytes(OVERVIEW_TEMPLATE))
        if git:
            self.git_init()

    def dialog_env(self):
        """What state.py's dialog switch wants besides this environment: dialog.json on, the runtime's dialog tool
        verified in its home. Returns the one variable left, the session id."""
        self.write(".ai/policies/dialog.json",
                   json.dumps({"version": 1, "enabled": True, "window_seconds": 120, "stop_blocks_max": 2}))
        os.makedirs(os.path.join(self.home, "riskrails"), exist_ok=True)
        with open(os.path.join(self.home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
            json.dump({"plan": "max", "dialog": {"tool": "AskUserQuestion"}}, fh)
        return {"CLAUDE_CODE_SESSION_ID": "sess-1"}

    def run_setup(self, *args, env=None, cwd=None):
        return subprocess.run([sys.executable, "-I", SETUP, *args], capture_output=True, text=True, check=False,
                              env=dict(self.env, **(env or {})), cwd=cwd)

    def options(self, *args, root=None, env=None, cwd=None):
        done = self.run_setup("options", "--json", "--root", root or self.root, *args, env=env, cwd=cwd)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stderr, "")
        return json.loads(done.stdout)

    @staticmethod
    def option(data, key):
        return next(o for o in data["options"] if o["key"] == key)


class TestOptions(OptionsProject):
    """`options --json` says what each of the four setup options is now, and writes nothing
    (spec interactive-setup-options R9)."""

    def test_fresh_all_unset(self):
        self.build()
        self.assertEqual(self.options(), {
            "schema": 1, "root": self.root, "git": True, "dialog": False,
            "ask": ["memory", "runtime", "survey", "verify"],
            "options": [
                {"key": "memory", "state": "unset", "current": None, "author": "tester", "author_from": "$USER",
                 "period": "quarter", "fts5": False},
                {"key": "runtime", "state": "unset", "declared": [], "auto": INSTALLED},
                {"key": "survey", "state": "unset"},
                {"key": "verify", "state": "unset", "proposal": None, "also": []}]})

    def test_detects_configured(self):
        self.build()
        self.write(".ai/policies/memory.json", json.dumps({"schema": 1, "mode": "packages"}))
        self.write("CLAUDE.md", "# Shop\n")
        self.write(".ai/project/overview.md", self.SURVEYED)
        self.write(".ai/policies/verification.md", "verify_command:      make test\n")
        data = self.options()
        self.assertEqual(data["ask"], [])
        self.assertEqual([(o["key"], o["state"]) for o in data["options"]],
                         [("memory", "set"), ("runtime", "set"), ("survey", "set"), ("verify", "set")])
        memory, runtime, _survey, verify = data["options"]
        self.assertEqual((memory["current"], memory["period"]), ("packages", None))
        self.assertEqual((runtime["declared"], runtime["auto"]), (["claude"], "claude"))
        self.assertEqual(verify, {"key": "verify", "state": "set", "current": "make test"})
        self.assertEqual(self.options("--all")["ask"], ["memory", "runtime", "survey", "verify"])

    def test_writes_nothing(self):
        """Nothing under the project or the home changes: not .ai/, not .git/, not a temporary file that is
        removed again — with state.py's switch consulted, memory read and the toolbox walked."""
        self.build()
        env = self.dialog_env()
        self.write(".ai/policies/memory.json", json.dumps({"schema": 1, "mode": "packages"}))
        self.write(".ai/local/memory/config.json", json.dumps({"schema": 1, "author": "tester", "index": "none"}))
        self.write("Makefile", "test:\n\t@echo ok\n")
        self.write("CLAUDE.md", "# Shop\n")
        before = snapshot(self.tmp)
        first = self.options(env=env)
        second = self.options("--all", env=env)
        self.assertEqual(snapshot(self.tmp), before)
        self.assertIs(first["dialog"], True, "state.py was not asked")
        self.assertEqual(second["ask"], ["memory", "runtime", "survey", "verify"])

    def test_leaves_no_bytecode_in_the_install(self):
        """Read-only means the plugin's own directories too: no __pycache__ appears beside the modules setup.py
        imports or beside the state.py it asks. It runs from a copy of the install, which also shows that nothing
        but the sibling skills is looked up."""
        install = os.path.join(self.tmp, "install", "skills")
        for skill in ("ai-init", "ai-task", "project-update", "rr-setup"):
            shutil.copytree(os.path.join(ROOT, "skills", skill), os.path.join(install, skill),
                            ignore=shutil.ignore_patterns("__pycache__", "blobs"))
        self.build()
        env = self.dialog_env()
        done = subprocess.run([sys.executable, "-I", os.path.join(install, "rr-setup", "setup.py"), "options",
                               "--json", "--all", "--root", self.root],
                              capture_output=True, text=True, check=False, env=dict(self.env, **env))
        self.assertEqual(done.returncode, 0, done.stderr)
        data = json.loads(done.stdout)
        self.assertIs(data["dialog"], True, "state.py was not asked")
        self.assertEqual(self.option(data, "memory")["state"], "unset", "memory_sync was not loaded")
        self.assertEqual([d for d, _dirs, _files in os.walk(install) if os.path.basename(d) == "__pycache__"], [])

    def test_options_without_json_is_a_usage_error(self):
        self.build()
        for args in (["options"], ["options", "--all"]):
            with self.subTest(args=args):
                done = self.run_setup(*args, "--root", self.root)
                self.assertEqual(done.returncode, 2)
                self.assertEqual(done.stdout, "")
                self.assertIn("--json", done.stderr)

    def test_root_is_absolute(self):
        self.build()
        self.assertEqual(self.options(root="shop", cwd=self.tmp)["root"], self.root)

    def test_scaffold_ignores_the_record(self):
        """The record and the task logs are local data by default: the scaffold's .gitignore ignores both."""
        os.makedirs(self.root)
        self.git_init()
        subprocess.run([sys.executable, "-I", SCAFFOLD, self.root, "--runtime", "claude"], check=True,
                       capture_output=True, env=self.env)
        lines = read_bytes(self.path(".gitignore")).decode().splitlines()
        self.assertIn(".ai/memory/", lines)
        self.assertIn(".ai/reports/", lines)

    def test_scaffolded_project(self):
        """The scaffold's own output, then the proposal `survey` prints: the same command and sources."""
        os.makedirs(self.root)
        self.git_init()
        subprocess.run([sys.executable, "-I", SCAFFOLD, self.root, "--runtime", "claude"], check=True,
                       capture_output=True, env=self.env)
        self.write("Makefile", "test:\n\t@echo ok\n")
        self.write("composer.json", json.dumps({"scripts": {"test": "phpunit"}}))
        data = self.options()
        self.assertEqual(data["ask"], ["memory", "survey", "verify"])
        self.assertEqual(self.option(data, "runtime"),
                         {"key": "runtime", "state": "set", "declared": ["claude"], "auto": "claude"})
        verify = self.option(data, "verify")
        survey = self.run_setup("survey", "--root", self.root).stdout
        self.assertIn("verify_command: proposed `%(command)s` (from %(from)s)" % verify["proposal"], survey)
        self.assertEqual(verify["also"], [{"command": "composer test", "from": "composer.json test"}])
        self.assertIn("also     `composer test` (from composer.json test)", survey)

    def test_dialog_is_state_pys_answer(self):
        self.build()
        session = {"CLAUDE_CODE_SESSION_ID": "sess-1"}
        self.assertIs(self.options(env=session)["dialog"], False, "no dialog.json")
        env = self.dialog_env()
        self.assertIs(self.options(env=env)["dialog"], True)
        self.assertIs(self.options()["dialog"], False, "no session id to bind a pick to")
        self.assertIs(self.options(env=dict(env, AI_UNATTENDED="1"))["dialog"], False, "an unattended run")
        sub = os.path.join(self.root, "app")      # state.py would walk up to this project's .ai/; the root given rules
        os.makedirs(sub)
        self.assertIs(self.options(root=sub, env=env)["dialog"], False, "no .ai/ of its own")

    def test_dialog_is_false_when_state_py_cannot_answer(self):
        spec = importlib.util.spec_from_file_location("rr_setup_under_test", SETUP)
        setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(setup)
        done = subprocess.CompletedProcess
        answers = (("no interpreter", {"side_effect": OSError("no interpreter")}),
                   ("exit 1", {"return_value": done([], 1, '{"dialog": true}', "refused")}),
                   ("not JSON", {"return_value": done([], 0, "dialog: on", "")}),
                   ("not an object", {"return_value": done([], 0, "[true]", "")}),
                   ("not a boolean", {"return_value": done([], 0, '{"dialog": 1}', "")}))
        self.build()
        self.dialog_env()
        for name, patch in answers:
            with self.subTest(name), mock.patch.object(setup.subprocess, "run", **patch):
                self.assertIs(setup.dialog_on(self.root), False)
        with mock.patch.object(setup.subprocess, "run", return_value=done([], 0, '{"dialog": true, "live": []}', "")):
            self.assertIs(setup.dialog_on(self.root), True)


class TestOptionsMemory(OptionsProject):
    """The memory option: R16 (a git work tree), D1 (the author `memory enable` would write), the FTS5 probe."""

    def test_outside_git_memory_is_unavailable(self):
        """R16: `memory enable` needs a git work tree; the three other options are still asked."""
        self.build(git=False)
        data = self.options("--all")
        self.assertIs(data["git"], False)
        self.assertEqual(self.option(data, "memory"),
                         {"key": "memory", "state": "unavailable", "why": "not a git work tree"})
        self.assertEqual(data["ask"], ["runtime", "survey", "verify"])

    def test_a_subdirectory_of_a_work_tree_is_inside_it(self):
        self.build()
        sub = os.path.join(self.root, "app")
        os.makedirs(sub)
        data = self.options(root=sub)
        self.assertIs(data["git"], True)
        self.assertEqual(self.option(data, "memory")["state"], "unset")

    def test_memory_is_set_by_the_file_not_its_mode(self):
        """`memory disable` leaves mode "files" in memory.json: the human has decided, so it is not asked again."""
        self.build()
        self.write(".ai/policies/memory.json", json.dumps({"schema": 1, "mode": "files"}))
        data = self.options()
        memory = self.option(data, "memory")
        self.assertEqual((memory["state"], memory["current"], memory["period"]), ("set", "files", None))
        self.assertNotIn("memory", data["ask"])

    def test_broken_memory_json_is_unavailable(self):
        """`memory enable` would refuse it, so the dialog must not offer it."""
        self.build()
        self.write(".ai/policies/memory.json", "{not json")
        data = self.options("--all")
        memory = self.option(data, "memory")
        self.assertEqual(memory["state"], "unavailable")
        self.assertIn("memory.json is not valid JSON", memory["why"])
        self.assertEqual(data["ask"], ["runtime", "survey", "verify"])

    def test_author_is_what_enable_writes(self):
        """D1: the author shown is the one `memory enable` writes without --author — the local config, else $USER —
        and git's user.name is never read."""
        self.build()
        with open(os.path.join(self.home, ".gitconfig"), "w", encoding="utf-8") as fh:
            fh.write("[user]\n\tname = Someone Else\n")
        subprocess.run(["git", "-C", self.root, "config", "user.name", "Local Name"], check=True, env=self.env)
        env = {"USER": "Ivan.Kakurov"}
        memory = self.option(self.options(env=env), "memory")
        self.assertEqual((memory["author"], memory["author_from"]), ("ivan-kakurov", "$USER"))
        shown = memory["author"]
        self.write(".ai/local/memory/config.json", json.dumps({"schema": 1, "author": "from-config", "index": "none"}))
        memory = self.option(self.options(env=env), "memory")
        self.assertEqual((memory["author"], memory["author_from"]), ("from-config", "local config"))
        os.remove(self.path(".ai/local/memory/config.json"))
        # The writer itself, as a human's terminal runs it: the config it writes names the author that was shown.
        done = subprocess.run([sys.executable, "-I", STATE, "--root", self.root, "memory", "enable"],
                              capture_output=True, text=True, check=False, env=dict(self.env, **env, AI_UNATTENDED="1"))
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(json.loads(read_bytes(self.path(".ai/local/memory/config.json")))["author"], shown)
        memory = self.option(self.options(env=env), "memory")
        self.assertEqual((memory["state"], memory["current"], memory["period"], memory["author_from"]),
                         ("set", "packages", None, "local config"))

    def test_author_without_user_or_config(self):
        self.build()
        for env, want in (({"USER": ""}, ("unknown", "default")),
                          ({"USER": "", "USERNAME": "Win.User"}, ("win-user", "$USERNAME"))):
            with self.subTest(env=env):
                memory = self.option(self.options(env=env), "memory")
                self.assertEqual((memory["author"], memory["author_from"]), want)

    def test_fts5_follows_the_probe(self):
        """memory_store's own probe, AI_MEMORY_NO_FTS=1 included; False in a Python without sqlite3."""
        self.build()
        self.assertIs(self.option(self.options(), "memory")["fts5"], False)
        self.assertIsInstance(self.option(self.options(env={"AI_MEMORY_NO_FTS": ""}), "memory")["fts5"], bool)
        # `sys.modules["sqlite3"] = None` makes `import sqlite3` fail, as it does where the module is not built.
        code = ("import runpy, sys; sys.modules['sqlite3'] = None; sys.argv = sys.argv[1:]; "
                "runpy.run_path(sys.argv[0], run_name='__main__')")
        done = subprocess.run([sys.executable, "-I", "-c", code, SETUP, "options", "--json", "--root", self.root],
                              capture_output=True, text=True, check=False, env=dict(self.env, AI_MEMORY_NO_FTS=""))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertIs(self.option(json.loads(done.stdout), "memory")["fts5"], False)


class TestOptionsSignals(OptionsProject):
    """What makes the runtime, survey and verify options set: the signals the scaffold reads, an overview the
    plugin did not ship, check's rule for verify_command."""

    def test_runtime_signals_follow_the_scaffold(self):
        """`declared` comes from setup.py's table of the signals, `auto` from scaffold_ai's own resolution: a signal
        one reads and the other does not shows here."""
        cases = [("CLAUDE.md", ["claude"]), (".claude/settings.json", ["claude"]), ("AGENTS.md", ["codex"]),
                 (".codex/config.toml", ["codex"]), ("GEMINI.md", ["gemini"]), (".gemini/settings.json", ["gemini"]),
                 (".junie/guidelines.md", ["junie"])]
        for n, (rel, declared) in enumerate(cases):
            with self.subTest(rel=rel):
                root = os.path.join(self.tmp, "r%d" % n)
                os.makedirs(os.path.join(root, os.path.dirname(rel)), exist_ok=True)
                with open(os.path.join(root, rel), "w", encoding="utf-8") as fh:
                    fh.write("x\n")
                self.assertEqual(self.option(self.options(root=root), "runtime"),
                                 {"key": "runtime", "state": "set", "declared": declared, "auto": ",".join(declared)})
        both = os.path.join(self.tmp, "both")
        os.makedirs(both)
        for name in ("AGENTS.md", "CLAUDE.md"):
            with open(os.path.join(both, name), "w", encoding="utf-8") as fh:
                fh.write("x\n")
        self.assertEqual(self.option(self.options(root=both), "runtime"),
                         {"key": "runtime", "state": "set", "declared": ["claude", "codex"], "auto": "claude,codex"})

    def test_verify_none_is_unset_and_a_command_is_set(self):
        self.build()
        self.write("Makefile", "test:\n\t@echo ok\n")
        want = {"key": "verify", "state": "unset", "proposal": {"command": "make test", "from": "Makefile test"},
                "also": []}
        self.assertEqual(self.option(self.options(), "verify"), want)
        self.write(".ai/policies/verification.md", "verify_command: None\n")      # `check`'s rule: none is no command
        self.assertEqual(self.option(self.options(), "verify"), want)
        self.write(".ai/policies/verification.md", "verify_command: make test\n")
        self.assertEqual(self.option(self.options(), "verify"),
                         {"key": "verify", "state": "set", "current": "make test"})

    def test_survey_is_an_overview_the_plugin_did_not_ship(self):
        """No depth is recorded: an overview.md that is a version the plugin shipped — today's, an older one in
        project-update's history, either with CRLF line ends — was never written into."""
        self.build()
        today = read_bytes(OVERVIEW_TEMPLATE)
        with open(os.path.join(HISTORY, "index.json"), encoding="utf-8") as fh:
            versions = json.load(fh)["ai-init/.ai/project/overview.md"]
        older = [h for h in versions if h != hashlib.sha256(today).hexdigest()]
        self.assertTrue(older, "the history index holds no older overview.md: the pre-rename template is not pinned")
        for name, data in (("today's", today), ("today's, CRLF", today.replace(b"\n", b"\r\n")),
                           ("an older one", read_bytes(os.path.join(HISTORY, "blobs", older[0])))):
            with self.subTest(name):
                self.write(".ai/project/overview.md", data)
                self.assertEqual(self.option(self.options(), "survey"), {"key": "survey", "state": "unset"})
        self.write(".ai/project/overview.md", self.SURVEYED)
        self.assertEqual(self.option(self.options(), "survey"), {"key": "survey", "state": "set"})
        os.remove(self.path(".ai/project/overview.md"))
        self.assertEqual(self.option(self.options(), "survey"), {"key": "survey", "state": "unset"})


class OpenProject(OptionsProject):
    """What the `options --open` tests share: the texts of the dialog (spec §Dialog texts) for a project named shop,
    projects with the dialog on, and the reading of what state.py opened."""

    MEMORY = ("Project memory for shop: off keeps closed tasks only in .ai/reports/. packages also writes one compact "
              "file per developer per quarter under .ai/memory/; both stay local (git-ignored) unless you run "
              "'state.py memory enable --share git' in your own terminal. "
              "Author tester (from $USER), period quarter. Turn it on?")
    RUNTIME = ("Which agent runtimes work on shop? The scaffold adds their instruction files and directories and "
               "never removes one.")
    SURVEY = "How deep should the first survey of shop go?"
    VERIFY = "verify_command — the fast suite every task runs, e2e excluded."
    PACKAGES = "packages; local, git-ignored record under .ai/memory/"
    INDEXED = "plus a local, git-ignored SQLite index; FTS5 no — without it search scans: same results, slower"
    LIGHT = "Light — your 10-minute brain dump + 2 discovery agents"
    FULL = "Full — inventory + 6 discovery agents"
    NOT_NOW, OTHER = "Not now — ask me in chat", "Another — I type it in chat"
    RUNTIMES = ["Auto — what the repository declares, else " + INSTALLED, "Claude Code only", "Codex only",
                "Claude Code and Codex"]

    def project(self, name, git=True):
        """Another project of its own, <tmp>/<name>/shop, as build() makes it, with the dialog on: its environment."""
        self.root = os.path.join(self.tmp, name, "shop")
        self.build(git=git)
        return self.dialog_env()

    def configured(self, name):
        """A project with all four options set, as TestOptions.test_detects_configured makes it, the dialog on."""
        env = self.project(name)
        self.write(".ai/policies/memory.json", json.dumps({"schema": 1, "mode": "packages"}))
        self.write("CLAUDE.md", "# Shop\n")
        self.write(".ai/project/overview.md", self.SURVEYED)
        self.write(".ai/policies/verification.md", "verify_command:      make test\n")
        return env

    def open(self, *args, env=None):
        return self.run_setup("options", "--open", "--root", self.root, *args, env=env)

    def decisions(self):
        path = self.path(".ai/state/decision.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["open"]

    def kept(self):
        """decision.json and the consent ledger byte for byte: what a refused open must leave as it found them."""
        paths = [self.path(".ai/state/" + name) for name in ("decision.json", "consent.jsonl")]
        return tuple(read_bytes(p) if os.path.exists(p) else None for p in paths)

    def enable(self, *words, entry=STATE):
        """`memory enable` of that state.py on this project, as rr_state.labels.state_label writes the label."""
        return "python3 %s %s" % (shlex.quote(entry), shlex.join(["--root", self.root, "memory", "enable", *words]))

    def asked(self, done):
        """The questions of a successful --open: its three lines are the id line, state.py's own, and its JSON."""
        self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines), 3, done.stdout)
        return json.loads(lines[2])["questions"]

    def prose(self):
        """The four questions as numbered prose, for a project with no verify candidate, and the memory command for
        the human's own terminal."""
        return "\n".join([
            "1. Memory: " + self.MEMORY, "   a) Off — keep files mode",
            "   b) memory enable --period quarter — " + self.PACKAGES,
            "   c) memory enable --period quarter --index sqlite — " + self.INDEXED,
            "2. Runtime: " + self.RUNTIME] + ["   %s) %s" % (letter, label) for letter, label in zip("abcd", self.RUNTIMES)] + [
            "3. Survey: " + self.SURVEY, "   a) " + self.LIGHT, "   b) " + self.FULL,
            "4. Verify: %s No proposal: nothing found in the project's files." % self.VERIFY,
            "   a) " + self.NOT_NOW, "   b) " + self.OTHER,
            "memory is the human's, in their own terminal: %s [--index sqlite]" % self.enable("--period", "quarter")]) + "\n"


class TestOptionsOpen(OpenProject):
    """`options --open` with the dialog on (spec interactive-setup-options R10, R16): the questions state.py opens, in
    this order, with these texts and commands — and what makes a question not asked."""

    def test_open_prints_dialog(self):
        """R10: the four questions open as one dialog, memory first — its pick is then the earliest the gate sees
        (spec B3) — and the output is the id line, then state.py's own two lines, unchanged."""
        env = self.project("fresh")
        self.write("Makefile", "test:\n\t@echo ok\n")
        self.write("composer.json", json.dumps({"scripts": {"test": "phpunit"}}))
        done = self.open(env=env)
        questions = self.asked(done)
        opened = self.decisions()
        ids = " ".join(d["id"] for d in opened)
        head, pending, _payload = done.stdout.splitlines()
        self.assertEqual(len(opened), 4)
        self.assertEqual(head, "OPTIONS_DIALOG " + ids)
        self.assertTrue(pending.startswith("DIALOG_PENDING %s — call AskUserQuestion with exactly this JSON" % ids), pending)
        self.assertEqual([(d["kind"], d["setup_key"]) for d in opened],
                         [("setup", key) for key in ("memory", "runtime", "survey", "verify")])
        self.assertEqual([q["header"] for q in questions], ["Memory", "Runtime", "Survey", "Verify"])
        for old in ("committed", "checked by a pre-push hook"):
            self.assertNotIn(old, questions[0]["question"])
        self.assertIn("both stay local (git-ignored) unless you run 'state.py memory enable --share git' "
                      "in your own terminal", questions[0]["question"])
        self.assertEqual([q["question"] for q in questions],
                         [self.MEMORY, self.RUNTIME, self.SURVEY, "%s Proposed: `make test` (from Makefile test)." % self.VERIFY])
        self.assertEqual([[o["label"] for o in q["options"]] for q in questions], [
            ["Off — keep files mode", self.enable("--period", "quarter"),
             self.enable("--period", "quarter", "--index", "sqlite")],
            self.RUNTIMES, [self.LIGHT, self.FULL],
            [self.NOT_NOW, "Use `make test`", "Use `composer test`", self.OTHER]])
        self.assertEqual([o["description"] for o in questions[0]["options"][1:]], [self.PACKAGES, self.INDEXED])
        # what the skill reads back after a pick: a choice sets its value, a command is only its label
        self.assertEqual([[o.get("value") for o in d["options"]] for d in opened],
                         [["off", None, None], ["auto", "claude", "codex", "both"], ["light", "full"],
                          ["", "make test", "composer test", "other"]])

    def test_memory_labels_prefilled(self):
        """R16, D1: no label carries --author — the question names the author enable will use and where it comes from —
        and --period quarter is there only while memory.json is absent."""
        def no_author(questions):
            labels = [o["label"] for q in questions for o in q["options"]]
            self.assertEqual([label for label in labels if "--author" in label], [])
            return questions[0]
        memory = no_author(self.asked(self.open(env=self.project("fresh"))))
        self.assertEqual([o["label"] for o in memory["options"][1:]],
                         [self.enable("--period", "quarter"), self.enable("--period", "quarter", "--index", "sqlite")])
        self.assertEqual(shlex.split(memory["options"][1]["label"]),
                         ["python3", STATE, "--root", self.root, "memory", "enable", "--period", "quarter"])
        self.assertIn("Author tester (from $USER), period quarter. Turn it on?", memory["question"])
        # a local config names the author, and the question says where it comes from
        env = self.project("local")
        self.write(".ai/local/memory/config.json", json.dumps({"schema": 1, "author": "from-config", "index": "none"}))
        memory = no_author(self.asked(self.open(env=env)))
        self.assertIn("Author from-config (from local config), period quarter.", memory["question"])
        self.assertEqual([o["label"] for o in memory["options"][1:]],
                         [self.enable("--period", "quarter"), self.enable("--period", "quarter", "--index", "sqlite")])
        # memory.json exists and holds the period: asked again with --all, no --period, and a way to keep what is set
        env = self.configured("set")
        memory = no_author(self.asked(self.open("--all", env=env)))
        self.assertEqual([o["label"] for o in memory["options"]],
                         ["Keep — packages mode", self.enable(), self.enable("--index", "sqlite")])
        self.assertIn("Author tester (from $USER). Keep it, or run memory enable?", memory["question"])

    def test_fts5_is_the_probes_answer(self):
        """The index option says whether this Python's SQLite has FTS5, as options --json reports it."""
        env = self.project("fts")
        env["AI_MEMORY_NO_FTS"] = ""
        fts5 = self.option(self.options(env=env), "memory")["fts5"]
        indexed = self.asked(self.open(env=env))[0]["options"][2]
        self.assertIn("FTS5 %s — without it search scans" % ("yes" if fts5 else "no"), indexed["description"])
        env["AI_MEMORY_NO_FTS"] = "1"
        self.assertIn("FTS5 no —", self.run_setup("options", "--open", "--root", self.root,
                                                  env=dict(env, AI_UNATTENDED="1")).stdout)

    def test_labels_are_what_state_label_writes(self):
        """The commands are rr_state.labels.state_label's own output for this install's state.py — a copy of its
        formula in setup.py cannot drift unseen; the root has a space in it, so the quoting is part of the pin."""
        env = self.project("quoted")
        label = self.asked(self.open(env=env))[0]["options"][1]["label"]
        code = ("import sys; sys.path.insert(0, %r); from rr_state import fs, labels; fs.ENTRY = %r; "
                "print(labels.state_label(%r, ['memory', 'enable', '--period', 'quarter']))"
                % (os.path.dirname(STATE), STATE, self.root))
        written = subprocess.run([sys.executable, "-I", "-B", "-c", code], capture_output=True, text=True, check=False)
        self.assertEqual(written.returncode, 0, written.stderr)
        self.assertEqual(written.stdout.strip(), label)
        self.assertIn("'%s'" % self.root, label)

    def test_no_git_no_memory(self):
        """R16: `memory enable` needs a git work tree, so outside one there is no memory question — not in the dialog,
        not in the prose, with --all or without."""
        env = self.project("plain", git=False)
        done = self.open(env=env)
        questions = self.asked(done)
        self.assertEqual([q["header"] for q in questions], ["Runtime", "Survey", "Verify"])
        self.assertEqual([d["setup_key"] for d in self.decisions()], ["runtime", "survey", "verify"])
        self.assertEqual(done.stdout.splitlines()[0], "OPTIONS_DIALOG " + " ".join(d["id"] for d in self.decisions()))
        self.assertNotIn("memory", done.stdout.lower())
        for args in ((), ("--all",)):
            with self.subTest(args=args):
                prose = self.open(*args, env=dict(env, AI_UNATTENDED="1")).stdout
                self.assertTrue(prose.startswith("OPTIONS_FALLBACK AI_UNATTENDED is set"), prose)
                self.assertEqual(re.findall(r"(?m)^\d\. (\w+):", prose), ["Runtime", "Survey", "Verify"])
                self.assertNotIn("memory", prose.lower())

    def test_open_asks_only_the_unset_ones(self):
        """O5: on a project that is partly set up only the unset options are asked, in the usual order; the dialog is
        as short as that, and the ids are the ones state.py gave."""
        env = self.configured("part")
        os.remove(self.path(".ai/policies/memory.json"))
        self.write(".ai/policies/verification.md", "verify_command:      # the fast suite, e2e excluded\n")
        done = self.open(env=env)
        self.assertEqual([q["header"] for q in self.asked(done)], ["Memory", "Verify"])
        self.assertEqual(done.stdout.splitlines()[0], "OPTIONS_DIALOG " + " ".join(d["id"] for d in self.decisions()))
        self.assertEqual([d["setup_key"] for d in self.decisions()], ["memory", "verify"])

    def test_skip_survey_asks_the_rest(self):
        """--skip KEY leaves a question out — /rr-setup --survey has answered the survey one: memory, runtime and
        verify are asked, in their order, and no survey decision is opened; the prose leaves it out as well, and a
        skipped memory takes the human's command with it."""
        env = self.project("skip")
        done = self.open("--skip", "survey", env=env)
        self.assertEqual([q["header"] for q in self.asked(done)], ["Memory", "Runtime", "Verify"])
        self.assertEqual([d["setup_key"] for d in self.decisions()], ["memory", "runtime", "verify"])
        self.assertEqual(done.stdout.splitlines()[0], "OPTIONS_DIALOG " + " ".join(d["id"] for d in self.decisions()))
        prose = self.open("--skip", "survey", "--skip", "memory", env=dict(env, AI_UNATTENDED="1")).stdout
        self.assertEqual(re.findall(r"(?m)^\d\. (\w+):", prose), ["Runtime", "Verify"])
        self.assertNotIn("memory is the human's", prose)

    def test_skip_with_all(self):
        """--skip with --all: what is set is asked again except what is skipped, each with its way to keep it."""
        env = self.configured("skipall")
        done = self.open("--all", "--skip", "memory", "--skip", "verify", env=env)
        questions = self.asked(done)
        self.assertEqual([q["header"] for q in questions], ["Runtime", "Survey"])
        self.assertEqual([[o["label"] for o in q["options"]] for q in questions],
                         [["Auto — what the repository declares (claude)"] + self.RUNTIMES[1:],
                          [self.LIGHT, self.FULL, "Keep the current survey"]])
        self.assertEqual([d["setup_key"] for d in self.decisions()], ["runtime", "survey"])

    def test_skip_drops_the_key_from_ask_not_from_the_facts(self):
        """--json: a skipped option's entry is as computed — the facts are still true — and only `ask` changes,
        with --all as without it."""
        self.configured("facts")
        os.remove(self.path(".ai/policies/memory.json"))           # memory is unset, the other three are set
        facts = self.options()["options"]
        cases = (((), ["memory"]), (("--skip", "memory"), []), (("--skip", "verify"), ["memory"]),
                 (("--all",), ["memory", "runtime", "survey", "verify"]),
                 (("--all", "--skip", "runtime", "--skip", "survey"), ["memory", "verify"]),
                 (("--all", "--skip", "memory", "--skip", "memory"), ["runtime", "survey", "verify"]))
        for args, ask in cases:
            with self.subTest(args=args):
                data = self.options(*args)
                self.assertEqual((data["ask"], data["options"]), (ask, facts))

    def test_open_all_asks_every_option(self):
        """O5, OQ4: --all on a project with everything set asks all four, each with a way to keep what is there."""
        env = self.configured("all")
        questions = self.asked(self.open("--all", env=env))
        opened = self.decisions()
        self.assertEqual([q["header"] for q in questions], ["Memory", "Runtime", "Survey", "Verify"])
        self.assertEqual([[o["label"] for o in q["options"]] for q in questions], [
            ["Keep — packages mode", self.enable(), self.enable("--index", "sqlite")],
            ["Auto — what the repository declares (claude)"] + self.RUNTIMES[1:],
            [self.LIGHT, self.FULL, "Keep the current survey"],
            ["Keep `make test`", "Change — I edit it myself"]])
        self.assertEqual([[o.get("value") for o in d["options"]] for d in opened],
                         [["keep", None, None], ["auto", "claude", "codex", "both"], ["light", "full", "keep"],
                          ["keep", "edit"]])
        self.assertEqual(questions[3]["question"], "%s Current: `make test`." % self.VERIFY)
        # the same questions as prose: keep first, and the human's command has no --period either
        prose = self.open("--all", env=dict(env, AI_UNATTENDED="1")).stdout
        self.assertIn("   a) Keep — packages mode\n   b) memory enable — %s\n   c) memory enable --index sqlite — %s\n"
                      % (self.PACKAGES, self.INDEXED), prose)
        self.assertTrue(prose.endswith("memory is the human's, in their own terminal: %s [--index sqlite]\n"
                                       % self.enable()), prose)

    def test_verify_options(self):
        """The verify question offers what the opener accepts: the proposal and at most one other candidate; a command
        with a backtick, over 200 characters or on several lines is not offered, and the limit itself is."""
        setup = load_setup()
        intro = "verify_command — the fast suite every task runs, e2e excluded."

        def found(command, source="Makefile test"):
            return {"command": command, "from": source}

        def asked(option):
            item = setup.verify_decision(dict({"key": "verify", "state": "unset", "proposal": None, "also": []}, **option))
            return item["question"], [(o["label"], o["value"]) for o in item["options"]]
        other = ("Use `composer test`", "composer test")
        self.assertEqual(asked({"proposal": found("make test"), "also": [found("composer test", "composer.json test"),
                                                                           found("npm test", "package.json test")]}),
                         (intro + " Proposed: `make test` (from Makefile test).",
                          [(self.NOT_NOW, ""), ("Use `make test`", "make test"), other, (self.OTHER, "other")]))
        for bad in ("a`b", "x" * 201, "two\nlines", ""):
            with self.subTest(bad=bad):
                self.assertEqual(asked({"proposal": found(bad), "also": [found("composer test", "composer.json test")]}),
                                 (intro + " Proposed: `composer test` (from composer.json test).",
                                  [(self.NOT_NOW, ""), other, (self.OTHER, "other")]))
        self.assertEqual(asked({"proposal": found("x" * 200)})[1][1], ("Use `%s`" % ("x" * 200), "x" * 200))
        self.assertEqual(asked({}), (intro + " No proposal: nothing found in the project's files.",
                                    [(self.NOT_NOW, ""), (self.OTHER, "other")]))
        for current, label in (("make test", "Keep `make test`"), ("a`b", "Keep the current command"),
                               ("x" * 201, "Keep the current command")):
            with self.subTest(current=current):
                item = setup.verify_decision({"key": "verify", "state": "set", "current": current})
                self.assertEqual([(o["label"], o["value"]) for o in item["options"]],
                                 [(label, "keep"), ("Change — I edit it myself", "edit")])
        # the limit is the opener's: a command of 200 characters is accepted by state.py, the label and all
        env = self.project("limits")
        spec = {"schema": 1, "decisions": [setup.verify_decision({"key": "verify", "state": "unset", "also": [],
                                                                   "proposal": found("x" * 200)})]}
        opened = subprocess.run([sys.executable, "-I", STATE, "--root", self.root, "decision", "open", "--kind", "setup",
                                 "--spec", "-"], input=json.dumps(spec), capture_output=True, text=True, check=False,
                                env=dict(self.env, **env))
        self.assertEqual(opened.returncode, 0, opened.stderr)

    def test_open_leaves_no_bytecode_in_the_install(self):
        """The state.py the dialog is opened with is the sibling of this setup.py — the labels name it, and it accepts
        them — and nothing it or setup.py imports leaves a __pycache__ in the install."""
        install = os.path.join(self.tmp, "install", "skills")
        for skill in ("ai-init", "ai-task", "project-update", "rr-setup"):
            shutil.copytree(os.path.join(ROOT, "skills", skill), os.path.join(install, skill),
                            ignore=shutil.ignore_patterns("__pycache__", "blobs"))
        env = self.project("installed")
        done = subprocess.run([sys.executable, "-I", os.path.join(install, "rr-setup", "setup.py"), "options", "--open",
                               "--root", self.root], capture_output=True, text=True, check=False,
                              env=dict(self.env, **env))
        memory = self.asked(done)[0]
        entry = os.path.join(install, "ai-task", "state.py")
        self.assertEqual(memory["options"][1]["label"], self.enable("--period", "quarter", entry=entry))
        self.assertEqual([d for d, _dirs, _files in os.walk(install) if os.path.basename(d) == "__pycache__"], [])


class TestOptionsOpenOutcomes(OpenProject):
    """`options --open` when there is nothing to ask, no dialog to ask in (R17) or state.py refuses: the answer, and
    what is written."""

    def test_open_none(self):
        """O5: nothing unset, nothing asked — OPTIONS_NONE, with the dialog on too, and nothing is opened."""
        env = self.configured("done")
        before = snapshot(self.tmp)
        done = self.open(env=env)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "OPTIONS_NONE\n", ""))
        self.assertEqual(snapshot(self.tmp), before)
        self.assertEqual(self.decisions(), [])

    def test_skip_every_unset_key_is_options_none(self):
        """A skip that leaves nothing to ask is OPTIONS_NONE — with the dialog on, with --all, and when the one
        unset key is the one skipped — and nothing is opened."""
        every = ["--skip", "memory", "--skip", "runtime", "--skip", "survey", "--skip", "verify"]
        env = self.project("skipnone")
        before = snapshot(self.tmp)
        for args in (every, ["--all"] + every):
            with self.subTest(args=args):
                done = self.open(*args, env=env)
                self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "OPTIONS_NONE\n", ""))
        self.assertEqual(snapshot(self.tmp), before)
        env = self.configured("skiplast")
        os.remove(self.path(".ai/policies/memory.json"))           # the only unset option is memory
        done = self.open("--skip", "memory", env=env)
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "OPTIONS_NONE\n", ""))
        self.assertEqual(self.decisions(), [])

    def test_skip_bad_key_is_a_usage_error(self):
        """KEY is one of the four option keys, once per --skip: anything else is exit 2 before anything runs."""
        env = self.project("skipbad")
        cases = ((("--skip", "nonsense"), "invalid choice: 'nonsense'"), (("--skip", "Survey"), "invalid choice: 'Survey'"),
                 (("--skip", "survey", "--skip", "nonsense"), "invalid choice: 'nonsense'"),
                 (("--skip",), "expected one argument"))
        for output in ("--open", "--json"):
            for args, why in cases:
                with self.subTest(output=output, args=args):
                    done = self.run_setup("options", output, "--root", self.root, *args, env=env)
                    self.assertEqual((done.returncode, done.stdout), (2, ""))
                    self.assertIn(why, done.stderr)
        self.assertEqual(self.decisions(), [])

    def test_dialog_off_fallback(self):
        """R17, O7: without a dialog — no dialog.json, a runtime whose dialog tool is not verified, an unattended run,
        an unattended session — the questions come as prose, then the memory command for the human's own terminal;
        no decision and nothing else is written."""
        codex = os.path.join(self.tmp, "codex")
        os.makedirs(os.path.join(codex, "riskrails"))
        with open(os.path.join(codex, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
            json.dump({"plan": "max", "dialog": {"tool": None}}, fh)
        cases = (("no dialog.json", "no enabled .ai/policies/dialog.json", {}, True),
                 ("the Codex tool is not verified", "dialog tool is not verified",
                  {"AI_RUNTIME": "codex", "CODEX_HOME": codex, "CODEX_THREAD_ID": "thread-1"}, False),
                 ("AI_UNATTENDED=1", "AI_UNATTENDED is set", {"AI_UNATTENDED": "1"}, False),
                 ("CLAUDE_CODE_SESSION_ATTENDED=0", "CLAUDE_CODE_SESSION_ATTENDED=0",
                  {"CLAUDE_CODE_SESSION_ATTENDED": "0"}, False))
        for n, (name, why, extra, drop_policy) in enumerate(cases):
            with self.subTest(name):
                env = self.project("off%d" % n)
                if drop_policy:
                    os.remove(self.path(".ai/policies/dialog.json"))
                before = snapshot(self.tmp)
                done = self.open(env=dict(env, **extra))
                self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
                head, body = done.stdout.split("\n", 1)
                self.assertTrue(head.startswith("OPTIONS_FALLBACK ") and why in head, head)
                self.assertEqual(body, self.prose())
                self.assertEqual(snapshot(self.tmp), before, "the fallback wrote something")
                self.assertFalse(os.path.exists(self.path(".ai/state/decision.json")))

    def test_open_falls_back_when_state_py_exits_1(self):
        """state.py's own exit 1 is the dialog off after all, or a decision.json it cannot read: the questions come as
        prose with its message as the reason, and the file is left as it was."""
        env = self.project("broken")
        self.write(".ai/state/decision.json", "{not json")
        done = self.open(env=env)
        self.assertEqual((done.returncode, done.stderr), (0, ""), done.stdout)
        head, body = done.stdout.split("\n", 1)
        self.assertRegex(head, r"\AOPTIONS_FALLBACK state\.py could not open the dialog: "
                               r"\.ai/state/decision\.json is unreadable")
        self.assertEqual(body, self.prose())
        self.assertEqual(read_bytes(self.path(".ai/state/decision.json")), b"{not json")

    def test_open_refusal_passes_through(self):
        """Risks 4, 5: state.py opens all four or none. With a decision already open its refusal is the answer — exit 6,
        its message on stderr, nothing on stdout, nothing opened — and so it is when the same questions are open."""
        env = self.project("busy")
        commit = subprocess.run([sys.executable, "-I", STATE, "--root", self.root, "decision", "open", "--kind", "commit",
                                 "--command", "git commit -m one"],
                                capture_output=True, text=True, check=False, env=dict(self.env, **env))
        self.assertEqual(commit.returncode, 0, commit.stderr)
        before = self.kept()
        done = self.open(env=env)
        self.assertEqual((done.returncode, done.stdout), (6, ""))
        self.assertRegex(done.stderr, r"\Astate\.py: DECISION_LIMIT — 1 questions are open and the spec adds 4;")
        self.assertEqual(self.kept(), before)
        self.assertEqual([d["kind"] for d in self.decisions()], ["commit"])
        env = self.project("twice")
        self.asked(self.open(env=env))
        before = self.kept()
        done = self.open(env=env)
        self.assertEqual((done.returncode, done.stdout), (6, ""))
        self.assertTrue(done.stderr.startswith("state.py: DECISION_DUPLICATE — "), done.stderr)
        self.assertEqual(self.kept(), before)
        self.assertEqual(len(self.decisions()), 4)

    def test_state_py_answers(self):
        """What open_dialog makes of each answer state.py can give: its two lines behind the id line, the dialog off
        after all handed back for the fallback, every other refusal passed through as exit 6."""
        setup = load_setup()
        spec = [setup.decision("survey", "Q?", [setup.choice_option("Light", "light"), setup.choice_option("Full", "full")])]
        pending = ("DIALOG_PENDING D4 D5 — call AskUserQuestion with exactly this JSON, then run the picked command "
                   "verbatim or 'state.py decision settle --id D4':\n")
        payload = '{"questions": [{"question": "Q?"}]}\n'
        refused = "state.py: DECISION_LIMIT — 1 questions are open and the spec adds 4; one dialog call carries 4\n"
        done = subprocess.CompletedProcess
        cases = (("opened, ids not from D1", done([], 0, pending + payload, ""), (0, None),
                  "OPTIONS_DIALOG D4 D5\n" + pending + payload, ""),
                 ("the dialog off after all", done([], 1, "", "state.py: the dialog is off here (.ai/policies/dialog.json)\n"),
                  (None, "state.py could not open the dialog: the dialog is off here (.ai/policies/dialog.json)"), "", ""),
                 ("a refusal", done([], 6, "", refused), (6, None), "", refused),
                 ("a bad spec", done([], 2, "", "state.py: bad spec — x\n"), (6, None), "", "state.py: bad spec — x\n"),
                 ("an exit without a message", done([], 7, "", ""), (6, None), "",
                  "setup.py: state.py exited 7 without a message\n"),
                 ("an answer without the id line", done([], 0, "no dialog\n", ""), (6, None), "",
                  "setup.py: state.py answered with no DIALOG_PENDING line; 'state.py decision show' lists what it "
                  "opened\n"),
                 ("no state.py to run", OSError("no interpreter"), (6, None), "",
                  "setup.py: cannot run %s (no interpreter)\n" % setup.STATE_PY))
        for name, answer, want, out, err in cases:
            with self.subTest(name):
                patch = {"side_effect": answer} if isinstance(answer, OSError) else {"return_value": answer}
                with mock.patch.object(setup.subprocess, "run", **patch), contextlib.redirect_stdout(io.StringIO()) as stdout, \
                        contextlib.redirect_stderr(io.StringIO()) as stderr:
                    got = setup.open_dialog("/p", spec)
                self.assertEqual((got, stdout.getvalue(), stderr.getvalue()), (want, out, err))

    def test_open_and_json_exclude_each_other(self):
        self.build()
        done = self.run_setup("options", "--open", "--json", "--root", self.root)
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("not allowed with argument", done.stderr)


if __name__ == "__main__":
    unittest.main()
