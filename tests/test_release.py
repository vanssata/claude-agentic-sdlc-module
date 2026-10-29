#!/usr/bin/env python3
"""Release plumbing: tools/sync-version.py keeps the five version fields in step.

The repository passes `--check`; a copy with one field changed fails it and names
the file; `--tag` must equal package.json's version; setting a version rewrites the
five places and nothing else; an invalid version exits 2 and changes nothing.
Every case works on a copy in a temporary directory.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = ROOT
TOOL = os.path.join(ROOT, "tools", "sync-version.py")
FILES = ("package.json", ".claude-plugin/plugin.json", ".claude-plugin/marketplace.json",
         ".codex-plugin/plugin.json")


def run(*args):
    """The tool through the current interpreter, isolated."""
    return subprocess.run([sys.executable, "-I", TOOL, *args], capture_output=True, text=True, check=False)


def copy_tree(dest):
    """The four files, with their directories, under dest."""
    for name in FILES:
        os.makedirs(os.path.dirname(os.path.join(dest, name)), exist_ok=True)
        shutil.copyfile(os.path.join(PLUGIN, name), os.path.join(dest, name))


def read(root, name):
    """A file's text, bytes kept."""
    with open(os.path.join(root, name), encoding="utf-8", newline="") as fh:
        return fh.read()


def write(root, name, text):
    """Write text without newline translation."""
    with open(os.path.join(root, name), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)


def package_version():
    """package.json's version in the repository."""
    return json.loads(read(PLUGIN, "package.json"))["version"]


class TestVersionSync(unittest.TestCase):
    """tools/sync-version.py --check and the setter."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        copy_tree(self.tmp)

    def test_repository_passes_check(self):
        res = run("--check")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)

    def test_one_file_at_another_version_fails_naming_it(self):
        name = ".codex-plugin/plugin.json"
        write(self.tmp, name, read(self.tmp, name).replace(package_version(), "0.0.1"))
        res = run("--check", "--root", self.tmp)
        self.assertEqual(res.returncode, 1)
        self.assertIn(name + ":0.0.1", res.stdout)

    def test_tag_must_equal_package_version(self):
        version = package_version()
        self.assertEqual(run("--check", "--tag", "v" + version).returncode, 0)
        self.assertEqual(run("--check", "--tag", version).returncode, 0)
        self.assertEqual(run("--check", "--tag", "v9.9.9").returncode, 1)

    def test_set_rewrites_only_the_version_values(self):
        before = {n: read(self.tmp, n) for n in FILES}
        old = package_version()
        res = run("9.9.9", "--root", self.tmp)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        for name in FILES:
            after = read(self.tmp, name)
            self.assertEqual(after.replace('"version": "9.9.9"', '"version": "%s"' % old), before[name], name)
        self.assertEqual(run("--check", "--tag", "9.9.9", "--root", self.tmp).returncode, 0)
        self.assertEqual(read(self.tmp, ".claude-plugin/marketplace.json").count('"version": "9.9.9"'), 2)

    def test_invalid_version_exits_2_and_changes_nothing(self):
        before = {n: read(self.tmp, n) for n in FILES}
        for bad in ("3.0", "v3.0.2", "3.0.2.1", "latest", "3.0.2; x"):
            self.assertEqual(run(bad, "--root", self.tmp).returncode, 2, bad)
        self.assertEqual({n: read(self.tmp, n) for n in FILES}, before)


COMMAND = "npx -y riskrails@latest --yes"


class TestReleaseWorkflow(unittest.TestCase):
    """The release workflow, checked as text (no yaml module in the standard library)."""

    def setUp(self):
        self.text = read(ROOT, ".github/workflows/npm-publish.yml")
        head, _, self.publish = self.text.partition("\n  publish:\n")
        self.verify = head.partition("\n  verify:\n")[2]

    def test_triggers_only_on_version_tags(self):
        on = self.text.partition("\non:\n")[2].partition("\nconcurrency:")[0]
        self.assertIn("tags: ['v*.*.*']", on)
        self.assertNotIn("branches", on)
        self.assertNotIn("pull_request", on)
        self.assertIn("cancel-in-progress: false", self.text)

    def test_verify_job_runs_the_gates(self):
        for needle in ('tools/sync-version.py --check --tag "$GITHUB_REF_NAME"',
                       "unittest discover -s tests -p 'test_*.py'",
                       "AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py",
                       "pylint $(git ls-files '*.py')", "npm pack --dry-run", "npm view"):
            self.assertIn(needle, self.verify)
        self.assertIn("contents: read", self.verify)

    def test_publish_job_is_gated_and_has_provenance(self):
        self.assertIn("needs: verify", self.publish)
        self.assertIn("environment: npm", self.publish)
        self.assertIn("id-token: write", self.publish)
        self.assertIn("contents: write", self.publish)
        self.assertIn("--provenance --access public", self.publish)
        self.assertIn("gh release view", self.publish)
        self.assertIn("--verify-tag", self.publish)

    def test_release_notes_carry_the_update_command(self):
        self.assertEqual(self.publish.count("echo '    " + COMMAND + "'"), 1)
        self.assertIn("echo '    ! " + COMMAND + "'", self.publish)
        notice = os.path.join(ROOT, "hooks", "update_notice.py")
        if not os.path.exists(notice):
            self.skipTest("hooks/update_notice.py not written yet")
        self.assertIn(COMMAND, read(ROOT, "hooks/update_notice.py"))


if __name__ == "__main__":
    unittest.main()
