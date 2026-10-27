#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
ai-git-guard: fixtures in a scratch repo, plus the branch-resolution cases that
only make sense with a real checked-out branch.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import (FIXTURES, PLUGIN, HookAsserts, bash, codex_fixtures,  # noqa: E402  pylint: disable=wrong-import-position
                           decision, fixtures, run)

TWIN_OF = "test-ai-git-guard.sh"
# `pass "$3"` in the shell suite is expect()'s label parameter, not a case; the
# labels it was called with are the cases below.
SHELL_MECHANICS = ("$3",)

GUARD = os.path.join(PLUGIN, "hooks", "ai-git-guard.sh")


class TestAiGitGuard(HookAsserts, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.root = os.path.join(cls.tmp, "repo")
        os.makedirs(os.path.join(cls.root, "src", "Payment"))
        # The guard reads the shipped defaults, not a config the developer
        # running the tests happens to have installed.
        home = os.path.join(cls.tmp, "home")
        os.makedirs(os.path.join(home, ".claude", "hooks"))
        cls.env = dict(os.environ, HOME=home)
        cls.git("init", "-q", "-b", "main")
        cls.git("config", "user.email", "test@example.com")
        cls.git("config", "user.name", "test")
        cls.write("src/Payment/Gateway.php", "x\n")
        cls.git("add", "src")
        cls.git("commit", "-qm", "init")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def git(cls, *args):
        subprocess.run(["git", "-C", cls.root, *args], check=True, env=cls.env)

    @classmethod
    def write(cls, rel, text):
        with open(os.path.join(cls.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def expect(self, expected, command, label):
        with self.subTest(label):
            _, out = run(GUARD, bash(command, self.root), env=self.env)
            self.assertEqual(decision(out), expected, "%s: %s" % (label, out[:200]))

    def test_fixtures_on_branch_main_then_branch_resolution(self):
        self.assertFixtures(GUARD, fixtures(os.path.join(FIXTURES, "git-guard"), self.root), env=self.env)

        self.expect("deny", "git push", "bare 'git push' while on main is denied")
        self.expect("deny", "git push origin HEAD", "'git push origin HEAD' while on main is denied")
        self.expect("deny", "git push origin main", "explicit push to main is denied")
        self.expect("deny", "git merge feature/x", "merging into main is denied")
        self.expect("deny", "git reset --hard origin/main", "hard reset on main is denied")

        self.git("checkout", "-q", "-b", "feature/payment-fee")
        try:
            self.expect("allow", "git push", "bare 'git push' on a feature branch is allowed")
            self.expect("allow", "git push origin HEAD", "'git push origin HEAD' on a feature branch is allowed")
            self.expect("allow", "git merge main", "merging main INTO a feature branch is allowed")
            self.expect("allow", "git reset --hard origin/feature/payment-fee",
                        "hard reset on a feature branch is allowed")
            self.expect("deny", "git push origin feature/x:main", "pushing a feature branch onto main is denied")
        finally:
            self.git("checkout", "-q", "main")

    def test_wildcard_add_sees_what_git_would_stage(self):
        env_file = os.path.join(self.root, ".env")
        self.write(".env", "SECRET=1\n")
        try:
            self.expect("deny", "git add .", "'git add .' with an untracked .env is denied")
            self.expect("deny", "git add -A", "'git add -A' with an untracked .env is denied")
        finally:
            os.remove(env_file)
        self.write(".env.example", "SECRET=\n")
        try:
            self.expect("allow", "git add .", "'git add .' with only .env.example is allowed")
        finally:
            os.remove(os.path.join(self.root, ".env.example"))

    def test_outside_a_git_repo(self):
        plain = os.path.join(self.tmp, "plain")
        os.makedirs(plain, exist_ok=True)
        _, out = run(GUARD, bash("echo hello", plain), env=self.env)
        self.assertEqual(out, "", "a non-git command outside a repo is allowed")

    def test_codex_payloads(self):
        self.assertFixtures(GUARD, codex_fixtures("git", self.root), env=self.env)
        self.assertFailsOpen(GUARD, "a malformed Codex payload fails open", "{ not json", env=self.env)


if __name__ == "__main__":
    unittest.main()
