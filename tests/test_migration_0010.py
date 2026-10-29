#!/usr/bin/env python3
"""R36.1: migration 0010 writes .ai/policies/dialog.json, the dialog's switch,
on, to a project at schema 9; a project that has the file keeps it, a second
run changes nothing, and a task in flight survives."""

import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_project_update import GIT, STATE, Project, put  # noqa: E402  pylint: disable=wrong-import-position

SWITCH = '{ "version": 1, "enabled": true, "window_seconds": 120, "stop_blocks_max": 2 }\n'
REL = os.path.join(".ai", "policies", "dialog.json")


class TestMigration0010(unittest.TestCase):

    def setUp(self):
        self.p = Project()
        self.file = os.path.join(self.p.root, REL)
        self.at_schema_9()

    def tearDown(self):
        self.p.close()

    def commit(self, msg="schema 9"):
        subprocess.run(GIT + ["-C", self.p.root, "add", "-A"], check=True)
        subprocess.run(GIT + ["-C", self.p.root, "commit", "-qm", msg], check=True)

    def at_schema_9(self):
        """What 0009 leaves: no switch file, VERSION 9."""
        if os.path.exists(self.file):
            os.remove(self.file)
        put(os.path.join(self.p.root, ".ai", "VERSION"), "9\n")
        self.commit()

    def test_writes_enabled_and_prints(self):
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "10"), done.stdout + done.stderr)
        with open(self.file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), SWITCH)
        hints = [line for line in done.stdout.splitlines() if "dialog.json" in line and "enabled" in line]
        self.assertEqual(len(hints), 1, done.stdout)
        self.assertIn("false", hints[0])
        # idempotent
        self.commit("schema 10")
        again = self.p.update("--apply")
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        self.assertNotIn("dialog.json", again.stdout)
        with open(self.file, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), SWITCH)

    def test_existing_file_untouched(self):
        mine = b'{ "version": 1, "enabled": false }\n'
        with open(self.file, "wb") as fh:
            fh.write(mine)
        self.commit("a human turned it off")
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "10"), done.stdout + done.stderr)
        with open(self.file, encoding="utf-8") as fh:
            kept = json.load(fh)
        self.assertIs(kept["enabled"], False, "the human's switch is not turned back on")
        self.assertFalse([l for l in done.stdout.splitlines() if "dialog is on" in l], "no hint for a kept file")

    def test_missing_file_at_schema_10_is_the_humans_choice(self):
        put(os.path.join(self.p.root, ".ai", "VERSION"), "10\n")
        self.commit("schema 10, switch removed")
        self.assertFalse(os.path.exists(self.file))
        plan = self.p.update("--check")
        self.assertNotIn("dialog.json", plan.stdout + plan.stderr)
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertFalse(os.path.exists(self.file), "the dialog is not switched back on")

    def test_hints_name_the_constitution_and_no_task_hint_without_one(self):
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertTrue([l for l in done.stdout.splitlines() if "C5" in l and "constitution" in l], done.stdout)
        self.assertFalse([l for l in done.stdout.splitlines() if "task is in flight: the dialog" in l])

    def test_in_flight_task_gets_a_hint(self):
        self.start_task()
        done = self.p.update("--apply")
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        hints = [l for l in done.stdout.splitlines() if "task is in flight: the dialog" in l]
        self.assertEqual(len(hints), 1, done.stdout)
        self.assertIn("false", hints[0])

    def start_task(self):
        put(os.path.join(self.p.root, "src", "Clock.php"), "x\n")
        self.commit("code")
        env = dict(self.p.env, AI_RUNTIME="claude")
        started = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "start", "--goal", "mid-build",
                                  "--workflow", "feature", "--files", "src/Clock.php", "--tests", "tests/ClockTest.php",
                                  "--declare", "behaviour=0:none", "--declare", "novelty=0:none"],
                                 env=env, capture_output=True, text=True, check=False)
        self.assertEqual(started.returncode, 0, started.stderr)
        self.commit("task started")

    def test_in_flight_state(self):
        put(os.path.join(self.p.root, "src", "Clock.php"), "x\n")
        self.commit("code")
        env = dict(self.p.env, AI_RUNTIME="claude")
        started = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "start", "--goal", "mid-build",
                                  "--workflow", "feature", "--files", "src/Clock.php", "--tests", "tests/ClockTest.php",
                                  "--declare", "behaviour=0:none", "--declare", "novelty=0:none"],
                                 env=env, capture_output=True, text=True, check=False)
        self.assertEqual(started.returncode, 0, started.stderr)
        state = os.path.join(self.p.root, ".ai", "state", "state.json")
        with open(state, "rb") as fh:
            before = fh.read()
        self.commit("task started")
        done = self.p.update("--apply")
        self.assertEqual((done.returncode, self.p.version()), (0, "10"), done.stdout + done.stderr)
        with open(state, "rb") as fh:
            self.assertEqual(fh.read(), before, "the task's bytes are unchanged")
        status = subprocess.run([sys.executable, "-I", STATE, "--root", self.p.root, "status"],
                                env=env, capture_output=True, text=True, check=False)
        self.assertEqual(status.returncode, 0, status.stderr)
        self.assertIn("mid-build", status.stdout)


if __name__ == "__main__":
    unittest.main()
