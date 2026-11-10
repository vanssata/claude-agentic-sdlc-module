#!/usr/bin/env python3
"""Every fixture file is tracked by git, so the suite reads on a clean checkout what it reads here.

A fixture tree that copies a project's `.gitignore` hides its own `.ai/local/` and `.ai/state/`
files from `git add`; they stay on the machine that wrote them and the release's verify, on a
fresh clone, fails (v4.0.0, test_regenerate). Such a file is added with `git add -f`.
"""
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_PARTS = ("__pycache__",)


def ignored_fixtures():
    out = subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--ignored", "--exclude-standard",
                          "--", "tests/fixtures"], capture_output=True, text=True, check=True).stdout
    return [p for p in out.splitlines() if not any(part in p.split("/") for part in SKIP_PARTS)]


@unittest.skipUnless(shutil.which("git") and os.path.exists(os.path.join(ROOT, ".git")), "not a git checkout")
class TestFixturesTracked(unittest.TestCase):
    def test_no_fixture_file_is_ignored(self):
        self.assertEqual(ignored_fixtures(), [], "git add -f these: a clean checkout does not have them")


if __name__ == "__main__":
    unittest.main()
