#!/usr/bin/env python3
"""Migration 0011: the retired tier policy (register #20, #50, #58, #62).

A project at schema 10 that still holds .ai/policies/risk-tiers.json and
risk-tiers.md gets both proposed for deletion behind --confirm-delete, with the
original kept; an edited copy is proposed too and says so; a project without the
files gets nothing; a second run proposes nothing; the plugin ships neither
template, so a new project's scaffold has no such file and no run re-creates one.
"""

import glob
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_project_update import GIT, ROOT, Project, put  # noqa: E402  pylint: disable=wrong-import-position

JSON, MD = (os.path.join(".ai", "policies", n) for n in ("risk-tiers.json", "risk-tiers.md"))
TEMPLATES = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies")


class TestMigration0011(unittest.TestCase):

    def setUp(self):
        self.p = None

    def tearDown(self):
        if self.p:
            self.p.close()

    def at_schema_10(self, **kwargs):
        self.p = Project(**kwargs)
        put(os.path.join(self.p.root, ".ai", "VERSION"), "10\n")
        self.commit("schema 10")
        return self.p

    def commit(self, msg):
        subprocess.run(GIT + ["-C", self.p.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.p.root, "commit", "-qm", msg, "--allow-empty"], check=True)

    def mine(self, rel):
        return os.path.join(self.p.root, rel)

    @staticmethod
    def proposals(out):
        return [line for line in out.splitlines() if line.startswith("  delete?") and "[0011]" in line]

    def test_the_plugin_ships_neither_template(self):
        for name in ("risk-tiers.json", "risk-tiers.md"):
            self.assertFalse(os.path.exists(os.path.join(TEMPLATES, name)), name)
        p = Project()                                   # a new project's scaffold
        try:
            self.assertFalse(os.path.exists(os.path.join(p.root, JSON)))
            self.assertFalse(os.path.exists(os.path.join(p.root, MD)))
            self.assertEqual(p.version(), "6")          # the fixture's schema, not the scaffold's
        finally:
            p.close()

    def test_proposes_both_and_waits_for_the_human(self):
        p = self.at_schema_10(tiers=True)
        dry = p.update()
        self.assertEqual(len(self.proposals(dry.stdout)), 2, dry.stdout)
        self.assertIn("schema    10 -> 11", dry.stdout)
        self.assertTrue(os.path.exists(self.mine(JSON)), "a dry run deletes nothing")
        done = p.update("--apply")
        self.assertEqual((done.returncode, p.version()), (0, "10"), done.stdout + done.stderr)
        self.assertTrue(os.path.exists(self.mine(JSON)) and os.path.exists(self.mine(MD)),
                        "without --confirm-delete both files stay")
        self.assertEqual(len(self.proposals(done.stdout)), 2, done.stdout)

    def test_the_human_confirms_and_the_original_is_kept(self):
        p = self.at_schema_10(tiers=True)
        with open(self.mine(JSON), "rb") as fh:
            before = fh.read()
        done = p.confirm()
        self.assertEqual((done.returncode, p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertFalse(os.path.exists(self.mine(JSON)) or os.path.exists(self.mine(MD)))
        kept = glob.glob(os.path.join(p.root, ".ai", "reports", "project-update-*", "original", JSON))
        self.assertEqual(len(kept), 1, "the original of the deleted file is kept")
        with open(kept[0], "rb") as fh:
            self.assertEqual(fh.read(), before)
        self.assertEqual(len(glob.glob(os.path.join(p.root, ".ai", "reports", "project-update-*", "original", MD))), 1)

    def test_an_edited_copy_is_proposed_and_flagged(self):
        p = self.at_schema_10(tiers=True)
        put(self.mine(JSON), "\n", "a")
        self.commit("the project edited its tier table")
        lines = {l.split()[1]: l for l in self.proposals(p.update().stdout)}
        self.assertEqual(sorted(lines), [".ai/policies/risk-tiers.json", ".ai/policies/risk-tiers.md"])
        self.assertIn("edited this copy", lines[".ai/policies/risk-tiers.json"])
        self.assertNotIn("edited this copy", lines[".ai/policies/risk-tiers.md"], "an unedited copy is not flagged")
        done = p.confirm()
        self.assertEqual((done.returncode, p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertFalse(os.path.exists(self.mine(JSON)))

    def test_a_second_run_proposes_nothing_and_nothing_is_recreated(self):
        p = self.at_schema_10(tiers=True)
        p.confirm()
        self.commit("settled")
        again = p.update("--apply")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertEqual(self.proposals(again.stdout), [])
        self.assertNotIn("risk-tiers", again.stdout, "the template walk does not bring the files back")
        self.assertFalse(os.path.exists(self.mine(JSON)) or os.path.exists(self.mine(MD)))
        self.assertEqual(p.update("--check").returncode, 0)

    def test_a_project_without_the_files_gets_nothing(self):
        p = self.at_schema_10()
        dry = p.update()
        self.assertEqual(self.proposals(dry.stdout), [], dry.stdout)
        self.assertIn("schema    10 -> 11", dry.stdout)
        done = p.update("--apply")
        self.assertEqual((done.returncode, p.version()), (0, "11"), done.stdout + done.stderr)
        self.assertNotIn("delete", done.stdout)
        self.assertFalse(os.path.exists(self.mine(JSON)))

    def test_only_one_of_the_two_present(self):
        p = self.at_schema_10(tiers=True)
        os.remove(self.mine(MD))
        self.commit("the mirror was already deleted")
        self.assertEqual(len(self.proposals(p.update().stdout)), 1)
        done = p.confirm()
        self.assertEqual((done.returncode, p.version()), (0, "11"), done.stdout + done.stderr)


if __name__ == "__main__":
    unittest.main()
