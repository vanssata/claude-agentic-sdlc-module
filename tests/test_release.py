#!/usr/bin/env python3
"""Release plumbing: tools/sync-version.py keeps the five version keys (in four files) in step.

The repository passes `--check`; a copy with one field changed fails it and names
the file; `--tag` must equal package.json's version; setting a version rewrites the
five version keys (four files) and nothing else; an invalid version exits 2 and changes nothing.
Every case works on a copy in a temporary directory.
"""
import json
import os
import re
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
        self.detect = head.partition("\n  detect:\n")[2].partition("\n  verify:\n")[0]

    def test_triggers_on_version_tags_and_a_package_json_change_on_main(self):
        on = self.text.partition("\non:\n")[2].partition("\nconcurrency:")[0]
        self.assertIn("tags: ['v*.*.*']", on)
        self.assertIn("branches: [main]", on)
        self.assertIn("paths: [package.json]", on)
        self.assertNotIn("pull_request", on)
        concurrency = self.text.partition("\nconcurrency:")[2].partition("\n\n")[0]
        self.assertIn("group: release\n", concurrency + "\n")
        self.assertNotIn("ref_name", concurrency)
        self.assertIn("cancel-in-progress: false", concurrency)

    def test_detect_job_decides_the_tag_and_whether_to_release(self):
        self.assertNotEqual(self.detect.strip(), "", "no detect job")
        self.assertIn("contents: read", self.detect)
        self.assertNotIn("contents: write", self.detect)
        self.assertNotIn("id-token", self.detect)
        outputs = self.detect.partition("outputs:")[2]
        self.assertRegex(outputs, r"(?m)^\s+tag:")
        self.assertRegex(outputs, r"(?m)^\s+release:")
        for needle in ("^v[0-9]+\\.[0-9]+\\.[0-9]+(-[0-9A-Za-z.-]+)?$", "gh release view",
                       "git ls-remote", "$GITHUB_SHA"):
            self.assertIn(needle, self.detect)

    def test_detect_validates_the_whole_tag_string_not_line_by_line(self):
        check = ("RE='^v[0-9]+\\.[0-9]+\\.[0-9]+(-[0-9A-Za-z.-]+)?$'\n"
                 'if ! [[ "$TAG" =~ $RE ]]; then\n')
        self.assertIn(check, "\n".join(line.strip() for line in self.detect.splitlines()) + "\n")
        self.assertNotRegex(self.detect, r"printf[^\n]*\$TAG[^\n]*\|\s*grep")
        self.assertNotIn("$TAG' is not", self.detect)
        script = check + "  echo refused\n  exit 1\nfi\necho accepted\n"
        for tag, code in (("v1.2.3", 0), ("v1.2.3-rc.1", 0), ("v1.2.3\nrelease=true", 1)):
            res = subprocess.run(["bash", "-c", 'set -euo pipefail\nTAG="$1"\n' + script, "bash", tag],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(res.returncode, code, "%r: %s" % (tag, res.stdout + res.stderr))

    def test_verify_job_waits_for_detect_and_runs_only_when_a_release_is_due(self):
        self.assertIn("needs: detect", self.verify)
        self.assertIn("if: needs.detect.outputs.release == 'true'", self.verify)
        self.assertIn("TAG: ${{ needs.detect.outputs.tag }}", self.verify)
        self.assertIn("tools/changelog-section.py", self.verify)
        self.assertNotIn("$GITHUB_REF_NAME", self.verify)
        self.assertNotIn("$GITHUB_REF_NAME", self.publish)

    def test_no_needs_expression_inside_a_run_script(self):
        lines = self.text.splitlines()
        self.assertTrue(any("needs.detect.outputs" in line for line in lines), "no detect output is used")
        for line in lines:
            if "${{ needs." not in line:
                continue
            key = line.strip().split(":", 1)[0]
            self.assertTrue(key == "if" or re.fullmatch(r"[A-Z][A-Z0-9_]*", key),
                            "a needs expression outside env:/if: -> " + line)

    def test_verify_job_runs_the_gates(self):
        for needle in ('tools/sync-version.py --check --tag "$TAG"',
                       "python3 -I tests/run_suite.py --serial test_guard_characterization.TestTimed"
                       " --serial test_dialog_gate.TestGateFastPath",
                       "AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py",
                       "pylint $(git ls-files '*.py')", "npm pack --dry-run", "npm view"):
            self.assertIn(needle, self.verify)
        self.assertIn("contents: read", self.verify)

    def test_verify_job_prepares_the_full_suite(self):
        suite = self.verify.index("tests/run_suite.py")
        self.assertNotIn("unittest discover -s tests -p 'test_*.py'", self.verify)
        self.assertEqual(self.verify.count("actions/setup-node@v7"), 1)
        self.assertLess(self.verify.index("actions/setup-node@v7"), suite)
        self.assertIn("fetch-depth: 0", self.verify[:self.verify.index("Set up Python")])
        self.assertIn('AI_TIMED_FACTOR: "3"', self.verify)
        self.assertLess(self.verify.index('AI_TIMED_FACTOR: "3"'), suite)

    def test_publish_job_is_gated_and_has_provenance(self):
        self.assertRegex(self.publish, r"needs: \[detect, verify\]")
        self.assertIn("TAG: ${{ needs.detect.outputs.tag }}", self.publish)
        self.assertIn("environment: npm", self.publish)
        self.assertIn("id-token: write", self.publish)
        self.assertIn("contents: write", self.publish)
        self.assertIn("--provenance --access public", self.publish)
        self.assertIn("gh release view", self.publish)
        self.assertIn("--verify-tag", self.publish)

    def test_publish_creates_the_tag_between_the_upload_and_the_release_with_the_changelog(self):
        for needle in ('git push origin "refs/tags/$TAG"', "gh release create"):
            self.assertIn(needle, self.publish)
        upload = self.publish.index("npm publish")
        push = self.publish.index('git push origin "refs/tags/$TAG"')
        release = self.publish.index("gh release create")
        self.assertLess(upload, push)
        self.assertLess(push, release)
        self.assertIn('git tag "$TAG" "$GITHUB_SHA"', self.publish)
        self.assertIn("Create the tag", self.publish)
        self.assertIn('python3 tools/changelog-section.py "$V"', self.publish)
        self.assertLess(self.publish.index("tools/changelog-section.py"), release)

    def test_a_prerelease_publishes_under_the_next_tag(self):
        self.assertIn("--provenance --access public --tag next", self.publish)
        self.assertIn("*-*)", self.publish)
        self.assertEqual(self.publish.count("npm publish"), 2)

    def test_a_rerun_skips_the_upload_and_reaches_the_release(self):
        view = self.publish.index('npm view "riskrails@$V" version')
        self.assertLess(view, self.publish.index("npm publish"))
        self.assertLess(self.publish.index("exit 0"), self.publish.index("npm publish"))
        self.assertLess(view, self.publish.index("Announce as a GitHub Release"))
        self.assertIn('[ "$RUN_ATTEMPT" = "1" ]', self.verify)
        self.assertIn("github.run_attempt", self.verify)

    def test_a_rerun_fails_when_the_registry_commit_differs(self):
        head = self.publish.index('npm view "riskrails@$V" gitHead')
        self.assertLess(self.publish.index('npm view "riskrails@$V" version'), head)
        self.assertLess(head, self.publish.index("exit 0"))
        self.assertIn('"$HEAD_SHA" != "$GITHUB_SHA"', self.publish)
        self.assertIn("exit 1", self.publish[head:self.publish.index("exit 0")])
        self.assertIn("::warning::", self.publish)

    def test_the_empty_token_comment_states_the_unknown(self):
        self.assertIn("NODE_AUTH_TOKEN: ${{ secrets.NPM_TOKEN }}", self.publish)
        self.assertIn("Not verified here", self.publish)
        self.assertNotIn("it is ignored", self.publish)

    def test_pylint_is_pinned_to_one_version_in_both_workflows(self):
        pins = {}
        for name in ("npm-publish.yml", "pylint.yml"):
            text = read(ROOT, ".github/workflows/" + name)
            self.assertNotRegex(text, r"pip install pylint\s*$", name)
            found = re.findall(r"pip install pylint==(\d+\.\d+\.\d+)\s", text)
            self.assertEqual(len(found), 1, name)
            pins[name] = found[0]
        self.assertEqual(len(set(pins.values())), 1, pins)

    def test_release_notes_carry_the_update_command(self):
        self.assertEqual(self.publish.count("echo '    " + COMMAND + "'"), 1)
        self.assertIn("echo '    ! " + COMMAND + "'", self.publish)
        notice = os.path.join(ROOT, "hooks", "update_notice.py")
        self.assertTrue(os.path.exists(notice), "hooks/update_notice.py is missing")
        self.assertIn(COMMAND, read(ROOT, "hooks/update_notice.py"))


CHANGELOG = """# Changelog

## [Unreleased]

### Added
- not yet

## [1.3.0] \u2014 2026-01-03

### Fixed
- middle fix

## [1.2.3-rc.1] \u2014 2026-01-02

- candidate

## [1.2.2] \u2014 2026-01-01

### Added
- last one
- second line

"""


class TestChangelogSection(unittest.TestCase):
    """tools/changelog-section.py prints the section of a CHANGELOG for a given version."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(self._tmp.cleanup)
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "tools", "changelog-section.py")),
                        "tools/changelog-section.py is missing")
        self.log = os.path.join(self._tmp.name, "CHANGELOG.md")
        write(self._tmp.name, "CHANGELOG.md", CHANGELOG)

    @staticmethod
    def section(*args):
        """The tool through the current interpreter, isolated."""
        tool = os.path.join(ROOT, "tools", "changelog-section.py")
        return subprocess.run([sys.executable, "-I", tool, *args], capture_output=True, text=True, check=False)

    def test_a_middle_section_comes_without_its_heading_or_the_next_section(self):
        res = self.section("1.3.0", "--file", self.log)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(res.stdout.strip("\n"), "### Fixed\n- middle fix")
        self.assertNotIn("## [", res.stdout)

    def test_the_last_section_runs_to_the_end_of_the_file(self):
        res = self.section("1.2.2", "--file", self.log)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(res.stdout.strip("\n"), "### Added\n- last one\n- second line")

    def test_a_prerelease_version_is_found(self):
        res = self.section("1.2.3-rc.1", "--file", self.log)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(res.stdout.strip("\n"), "- candidate")

    def test_a_missing_version_exits_1_and_says_so(self):
        res = self.section("9.9.9", "--file", self.log)
        self.assertEqual(res.returncode, 1)
        self.assertIn("has no section for 9.9.9", res.stderr)
        self.assertEqual(res.stdout, "")

    def test_an_invalid_version_exits_2(self):
        for bad in ("abc", "1.2", "Unreleased", "v1.2.3"):
            self.assertEqual(self.section(bad, "--file", self.log).returncode, 2, bad)

    def test_the_repository_changelog_has_the_4_1_0_section(self):
        res = self.section("4.1.0")
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertIn("### Added", res.stdout)


SMOKE = ("test_release.py", "test_update_notice.py", "test_install_routes.py",
         "test_shared_tree.py", "test_skills_surface.py", "test_context_guard.py",
         "test_state_layout.py", "test_state_characterization.py")


class TestSmokeWorkflow(unittest.TestCase):
    """The smoke gate (tests.yml), checked as text."""

    def setUp(self):
        self.text = read(ROOT, ".github/workflows/tests.yml")

    def test_triggers_on_pull_request_and_push_to_main(self):
        on = self.text.partition("\non:\n")[2].partition("\npermissions:")[0]
        self.assertIn("push:\n    branches: [main]", on)
        self.assertIn("pull_request:", on)
        self.assertNotIn("tags", on)

    def test_runs_the_smoke_files_through_the_parallel_runner(self):
        self.assertIn("python3 -I tests/run_suite.py $SMOKE_FILES", self.text)
        listed = re.search(r"SMOKE_FILES: >-\n((?:\s+tests/\S+.*\n)+)", self.text)
        self.assertIsNotNone(listed)
        files = listed.group(1).split()
        self.assertEqual(sorted(files), sorted("tests/" + n for n in SMOKE))
        for name in files:
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name)), name)
        self.assertNotIn("unittest discover -s tests -p 'test_*.py'", self.text)

    def test_end_to_end_step_stays(self):
        self.assertIn("AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py", self.text)

    def test_full_job_runs_nightly_and_on_demand_with_the_release_command(self):
        on = self.text.partition("\non:\n")[2].partition("\npermissions:")[0]
        self.assertIn("schedule:\n    - cron:", on)
        self.assertIn("workflow_dispatch:", on)
        self.assertEqual(on.count("cron:"), 1)
        smoke, _, full = self.text.partition("\n  full:\n")
        self.assertIn("github.event_name != 'schedule'", smoke)
        self.assertIn("github.event_name == 'schedule' || github.event_name == 'workflow_dispatch'", full)
        release = read(ROOT, ".github/workflows/npm-publish.yml")
        cmd = re.search(r"run: (python3 -I tests/run_suite\.py .*)\n", release).group(1)
        self.assertIn("run: " + cmd + "\n", full)
        self.assertIn('python-version: "3.12"', full)
        self.assertEqual(full.count("python-version:"), 1)
        self.assertIn("AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py", full)
        self.assertIn('AI_TIMED_FACTOR: "3"', full)

    def test_matrix_and_tools_check_stay(self):
        self.assertIn('python-version: ["3.11", "3.12", "3.13"]', self.text)
        self.assertIn("for tool in bash jq git python3 patch diff node;", self.text)


class TestInstallHarnessNode(unittest.TestCase):
    """The install suites run the installer with PATH cut to /usr/bin:/bin. A bare "node"
    is looked up on that PATH, and setup-node installs under /opt/hostedtoolcache: the
    release run 40973600734 failed with FileNotFoundError 'node' (review B1)."""

    def test_the_installer_names_node_by_its_absolute_path(self):
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        try:
            import install_harness  # pylint: disable=import-outside-toplevel
        finally:
            sys.path.pop(0)
        found = shutil.which("node")
        self.assertIsNotNone(found, "node is not on PATH; the runner must install it")
        node = install_harness.INSTALLER[0]
        self.assertTrue(os.path.isabs(node), "INSTALLER runs %r, resolved on the caller's PATH" % node)
        self.assertEqual(os.path.realpath(node), os.path.realpath(found))


if __name__ == "__main__":
    unittest.main()
