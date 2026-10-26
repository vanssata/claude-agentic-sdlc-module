"""setup.py (redesign 2.5): R9 — `check` exits 1 VERIFY_COMMAND_MISSING, `adopt`
writes toolbox.md and router rows on a project shaped like new-shop; R28 — the
superpowers line is printed and never written; SQ5 — the toolbox is inventoried
in place, never copied.

The project is tests/fixtures/setup/new-shop-like, stored encoded
(`dot-claude` → `.claude`, `fixture-CLAUDE.md` → `CLAUDE.md`) and scaffolded with
the plugin's own scripts, the way tests/test-project-adopt.sh builds its fixtures.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SETUP = os.path.join(ROOT, "skills", "rr-setup", "setup.py")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "setup", "new-shop-like")
NOT_COPIED = {"README.md", "fixture.json"}


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
        text = self.read(".ai/policies/testing.md")
        self.write(".ai/policies/testing.md", re.sub(r"(?m)^verify_command:.*$", "verify_command: " + value, text))


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

    def test_no_testing_md_is_missing(self):
        os.remove(self.path(".ai/policies/testing.md"))
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
        self.assertRegex(self.read(".ai/policies/testing.md"), r"(?m)^verify_command:\s+make test$")
        self.assertEqual(self.run_setup("check").returncode, 0)
        again = self.run_setup("verify", "--set", "composer test")
        self.assertEqual(again.returncode, 3)
        self.assertRegex(self.read(".ai/policies/testing.md"), r"(?m)^verify_command:\s+make test$")

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
        self.assertIn("verify_command: make test (testing.md)", out)

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


class TestAdopt(Project):
    """R9: toolbox.md and router rows; idempotent; a human's toolbox.md is never overwritten."""

    def test_dry_run_writes_nothing(self):
        before = tree_sha(self.root)
        result = self.run_setup("adopt")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("write .ai/policies/toolbox.md (12 item(s))", result.stdout)
        self.assertIn("router   | Deploy the current branch to staging and smoke-test the checkout. Use on "
                      "\"deploy to staging\". | `/deploy-staging` |", result.stdout)
        self.assertEqual(tree_sha(self.root), before)

    def test_apply(self):
        agents_before = self.read(".ai/AGENTS.md")
        settings_before = self.read(".claude/settings.json")
        result = self.run_setup("adopt", "--apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        toolbox = self.read(".ai/policies/toolbox.md")
        self.assertIn("- [/deploy-staging](../../.claude/skills/deploy-staging/SKILL.md) — Deploy the current "
                      "branch to staging", toolbox)
        self.assertIn("KNOWN FACT `.claude/skills/deploy-staging/SKILL.md:3`", toolbox)
        self.assertIn("- [bin/deploy.sh](../../bin/deploy.sh) — UNKNOWN", toolbox)
        self.assertIn("- [make test](../../Makefile) — The fast suite, e2e excluded — KNOWN FACT `Makefile:12`",
                      toolbox)
        self.assertIn("- `ai-git-guard`: this project's `.claude/hooks/block-git-push.sh` does the same job — kept",
                      toolbox)
        self.assertIn("- `ai-scope-guard`: no project hook does its job", toolbox)
        for link in re.findall(r"\]\(\.\./\.\./([^)]+)\)", toolbox):
            self.assertTrue(os.path.isfile(self.path(link)), link)
        agents = self.read(".ai/AGENTS.md")
        self.assertTrue(agents.startswith(agents_before.rsplit("\n|", 1)[0]))
        added = [l for l in agents.splitlines() if l not in agents_before.splitlines()]
        self.assertEqual([l.rsplit("|", 2)[-2].strip() for l in added],
                         ["policies/toolbox.md", "`/deploy-staging`", "`/sylius-fixtures`", "`/release-notes`"])
        self.assertTrue(os.path.isdir(self.path(".claude/skills/deploy-staging")), "a source moved")
        self.assertEqual(self.read(".claude/settings.json"), settings_before)

        again = self.run_setup("adopt", "--apply")
        self.assertEqual(again.returncode, 0)
        self.assertIn("unchanged .ai/policies/toolbox.md", again.stdout)
        self.assertIn("router   no new row", again.stdout)
        self.assertEqual(self.read(".ai/AGENTS.md"), agents)

    def test_reworded_row_is_not_added_twice(self):
        self.run_setup("adopt", "--apply")
        agents = self.read(".ai/AGENTS.md").replace("| Load the Sylius fixture suite into the local database |",
                                                    "| loading fixtures |")
        self.write(".ai/AGENTS.md", agents)
        self.run_setup("adopt", "--apply")
        self.assertEqual(self.read(".ai/AGENTS.md").count("`/sylius-fixtures`"), 1)

    def test_edited_toolbox_is_refused(self):
        self.run_setup("adopt", "--apply")
        self.write(".ai/policies/toolbox.md", self.read(".ai/policies/toolbox.md") + "\nMy own note.\n")
        result = self.run_setup("adopt", "--apply")
        self.assertEqual(result.returncode, 3)
        self.assertIn("My own note.", self.read(".ai/policies/toolbox.md"))

    def test_no_router_file(self):
        os.remove(self.path(".ai/AGENTS.md"))
        result = self.run_setup("adopt")
        self.assertEqual(result.returncode, 2)
        self.assertIn(".ai/AGENTS.md not found", result.stderr)



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
        self.assertEqual(self.run_setup("adopt", "--apply").returncode, 0)
        agents = self.read(".ai/AGENTS.md")
        self.assertEqual(agents.count("`/deploy-staging`"), 1)
        self.assertEqual(agents.count("`/sylius-fixtures`"), 1)
        self.assertIn(".agents/skills/deploy-staging/SKILL.md", self.read(".ai/policies/toolbox.md"))

    def test_symlinked_skill_directory(self):  # M3
        self.write("shared/skills/linked/SKILL.md", "---\ndescription: A skill shared between shops\n---\n")
        os.symlink(os.path.join("..", "..", "shared", "skills", "linked"), self.path(".claude/skills/linked"))
        out = self.run_setup("survey").stdout
        self.assertIn("skill    .claude/skills/linked/SKILL.md:2 — A skill shared between shops", out)

    def test_prose_mention_does_not_suppress_a_row(self):  # L1
        self.write(".ai/AGENTS.md", self.read(".ai/AGENTS.md") +
                   "\nRun `/deploy-staging` by hand; policies/toolbox.md lists the rest.\n")
        self.run_setup("adopt", "--apply")
        rows = [l for l in self.read(".ai/AGENTS.md").splitlines() if l.startswith("|")]
        self.assertTrue(any(l.endswith("| `/deploy-staging` |") for l in rows))
        self.assertTrue(any(l.endswith("| policies/toolbox.md |") for l in rows))

    def test_crlf_symlink_and_mode_survive(self):  # L2
        testing = self.path(".ai/policies/testing.md")
        shared = self.path("shared/testing.md")
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

if __name__ == "__main__":
    unittest.main()
