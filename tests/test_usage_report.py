"""usage-report.py --task reads a schema-6 and a schema-7 journal (R18): the old
one prints its tier, the new one its mode beside the compat tier."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "skills", "usage-report", "usage-report.py")
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "usage-report")
TASK = "T-FIXTURE"


class TestTaskJournal(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.project = os.path.join(self.tmp.name, "project")
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(os.path.join(self.project, ".ai", "reports", TASK))
        os.makedirs(self.home)

    def tearDown(self):
        self.tmp.cleanup()

    def report(self, fixture):
        journal = os.path.join(self.project, ".ai", "reports", TASK, "events.jsonl")
        shutil.copyfile(os.path.join(FIXTURES, fixture), journal)
        env = dict(os.environ, CLAUDE_CONFIG_DIR=os.path.join(self.home, ".claude"),
                   CODEX_HOME=os.path.join(self.home, ".codex"),
                   USAGE_REPORT_CACHE=os.path.join(self.tmp.name, "cache.json"))
        done = subprocess.run([sys.executable, "-I", SCRIPT, "--task", TASK, "--project", self.project],
                              capture_output=True, text=True, env=env, check=False)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        return done.stdout.split("\n")

    def test_schema_6_prints_the_tier(self):
        head = self.report("schema-6.jsonl")[0]
        self.assertTrue(head.startswith("task %s tier T4 window 2026-09-01T10:00:00+00:00..2026-09-01T11:00:00"
                                        % TASK), head)
        self.assertNotIn("mode", head)

    def test_schema_7_prints_the_mode_and_the_compat_tier(self):
        out = self.report("schema-7.jsonl")
        self.assertTrue(out[0].startswith("task %s mode full_irreversible (tier T6) window" % TASK), out[0])
        # Both runtimes that wrote the journal are reported, each against the T-label's budget.
        self.assertEqual([line.split()[0] for line in out if line.startswith(("claude ", "codex "))],
                         ["claude", "codex"])


if __name__ == "__main__":
    unittest.main()
