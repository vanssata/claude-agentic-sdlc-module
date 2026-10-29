#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
sensors.py: tree snapshots, tree diffs and the project's own commands (R6).

The scratch project lives under a path containing a space on purpose — every
path this module hands to git or to a project command must survive one.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from string import Template

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SENSORS = os.path.join(ROOT, "skills", "ai-task", "sensors.py")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import sensors  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-ai-task-sensors.sh"

TESTING_MD = """# Testing policy
verify_command:      printf 'ok\\n'; exit ${FAKE_EXIT:-0}
step_test_command:   printf 'step %s\\n' {files}
e2e_command:         none
single_test:         # the template's comment, not a value
"""

# run_command from a pseudo-terminal: what does the command see on stdin?
PTY_PROBE = """
import importlib.util, os, pty, subprocess, sys
sensors, log = sys.argv[1], sys.argv[2]
code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('sensors', sys.argv[1]); "
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.run_command('.', 'if [ -t 0 ]; then echo tty; else echo notty; fi; read -r x; echo read=$?', sys.argv[2], 10)")
master, slave = pty.openpty()
done = subprocess.run([sys.executable, "-c", code, sensors, log], stdin=slave, timeout=30, check=False)
os.close(slave); os.close(master)
print(done.returncode, open(log).read().replace("\\n", " ").strip())
"""


class TestSensors(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.root = os.path.join(self.tmp.name, "with space", "project")
        for d in (".ai/state", ".ai/reports", ".ai/policies", "src/Payment", "tests", "docs"):
            os.makedirs(os.path.join(self.root, d))
        self.git("init", "-q")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "Test")
        self.write("src/app.php", "base\n")
        self.write("composer.lock", "lock\n")
        self.git("add", "-A")
        self.git("commit", "-qm", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        return subprocess.run(["git", "-C", self.root] + list(args), capture_output=True, text=True,
                              check=True).stdout

    def write(self, rel, text, mode="w"):
        with open(os.path.join(self.root, rel), mode, encoding="utf-8") as fh:
            fh.write(text)

    def read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def n(self, *args, env=None):
        """sensors.py on the scratch project: (exit code, stdout)."""
        full = dict(os.environ)
        full.pop("FAKE_EXIT", None)
        full.update(env or {})
        done = subprocess.run([sys.executable, "-I", SENSORS, "--root", self.root] + list(args),
                              capture_output=True, text=True, env=full, check=False)
        return done.returncode, done.stdout.rstrip("\n")

    def snapshot(self):
        rc, out = self.n("snapshot")
        self.assertEqual(rc, 0, out)
        return out

    def changed(self):
        """Section 2's change: two edits, a lock file among them, and a new file."""
        base = self.snapshot()
        self.write("src/app.php", "base\nchanged\nagain\n")
        self.write("composer.lock", "newline in a lock file\n", "a")
        self.write("docs/guide.md", "# docs\n")
        return base, self.snapshot()

    # section 1: snapshot

    def test_snapshot(self):
        base = self.snapshot()
        self.assertRegex(base, r"^[0-9a-f]{2,}$", "snapshot prints a tree hash")
        self.assertEqual(base, self.git("rev-parse", "HEAD^{tree}").strip(),
                         "a clean worktree snapshots to HEAD's tree")

    def test_the_developers_index_is_untouched(self):
        """The real index must come out of a snapshot exactly as it went in: the
        module copies it, and a developer who had staged work keeps it staged."""
        self.write("src/staged.php", "staged\n")
        self.git("add", "src/staged.php")
        before = self.git("diff", "--cached", "--name-only")
        self.snapshot()
        self.assertEqual(self.git("diff", "--cached", "--name-only"), before, "the developer's index is untouched")

    def test_untracked_files_and_the_tasks_own_state(self):
        base = self.snapshot()
        self.write(".ai/state/current.json", "state\n")
        self.write("src/new.php", "untracked\n")
        tree = self.snapshot()
        self.assertNotEqual(tree, base, "an untracked source file is in the tree, as git diff HEAD would not show")
        names = self.git("ls-tree", "-r", "--name-only", tree).split("\n")
        self.assertEqual([n for n in names if n.startswith(".ai/state/")], [],
                         "the task's own state is dropped from the snapshot")

    # section 2: the diff is a file list between two trees

    def test_the_diff_is_a_file_list(self):
        base, after = self.changed()
        rc, out = self.n("diff", "--from", base, "--to", after)
        self.assertEqual((rc, out), (0, "M\tcomposer.lock\nA\tdocs/guide.md\nM\tsrc/app.php"),
                         "every changed file is listed with its status, a lock file included")
        _, out = self.n("diff", "--from", base, "--to", after, "--format", "json")
        self.assertEqual(len(json.loads(out)["files"]), 3, "--format json carries the same list")
        # git's own list is the reference; a sensor that disagrees with git is wrong.
        self.assertEqual(len(self.git("diff", "--name-only", base, after).splitlines()), 3,
                         "the list matches git diff --name-only")

    def test_no_base_tree(self):
        _, after = self.changed()
        rc, out = self.n("diff", "--to", after)
        self.assertEqual(rc, 3, out)
        self.assertIn("no base tree recorded", out, "no base tree is unavailable, never an empty diff")

    def test_a_plan_glob_reads_as_the_scope_guard_reads_it(self):
        """The scope guard's reading of a plan glob, not a stricter one: a file the
        hook allows must never be refused by state.py's step-done."""
        got = (bool(sensors.scope_any("src/Payment/Fee.php", ["src/*.php"])),
               bool(sensors.scope_any("src/a/b.php", ["src"])),
               bool(sensors.scope_any("tests/x.php", ["src/**"])))
        self.assertEqual(got, (True, True, False),
                         "a plan glob reads as the scope guard reads it (* crosses /, a directory prefixes)")

    # section 3: run is the project's own command, to the end, into a log

    def test_run(self):
        self.write(".ai/policies/testing.md", TESTING_MD)
        suite_log = os.path.join(self.tmp.name, "suite.log")
        rc, out = self.n("run", "--scope", "suite", "--log", suite_log)
        self.assertEqual(rc, 0, out)
        self.assertRegex(out, r"(?m)^suite *green")
        self.assertEqual(self.read(suite_log), "ok\n", "a green run exits 0 and its output is in the log")
        rc, out = self.n("run", "--scope", "suite", "--log", suite_log, env={"FAKE_EXIT": "1"})
        self.assertEqual(rc, 2, out)
        self.assertIn("RED", out, "a red run exits 2")
        step_log = os.path.join(self.tmp.name, "step.log")
        self.n("run", "--scope", "step", "--files", "tests/a b.php", "--log", step_log)
        self.assertEqual(self.read(step_log), "step tests/a b.php\n", "{files} takes the step's paths, quoted")
        rc, out = self.n("run", "--scope", "e2e")
        self.assertEqual(rc, 0, out)
        self.assertIn("n/a", out, "a command written as none is not applicable")
        rc, out = self.n("run", "--scope", "single", "--test", "x")
        self.assertEqual(rc, 3, out)
        self.assertIn("not written down", out, "a comment-only line is not written down yet, which is not none")

    def test_the_project_command_never_gets_the_humans_terminal(self):
        """A human runs 'verify --by' past the budget from their own terminal. The
        suite must not inherit it: an installer that prompts when stdin is a tty,
        or a test of the terminal-only approve route, behaves differently there
        (T-2026-10-26-001 run 17)."""
        log = os.path.join(self.tmp.name, "tty.log")
        done = subprocess.run([sys.executable, "-c", PTY_PROBE, SENSORS, log], capture_output=True, text=True,
                              check=False)
        self.assertEqual(done.stdout.strip(), "0 notty read=1",
                         "run_command gives the command /dev/null, not a terminal, as stdin")

    def test_read_commands_reads_doc_tests(self):
        self.write(".ai/policies/testing.md", TESTING_MD + "doc_tests:          tests/test_a.py tests/test_b.py\n")
        self.assertEqual(sensors.read_commands(self.root)["doc_tests"], "tests/test_a.py tests/test_b.py")

    # section 4: the old sensors are gone (R6)

    def test_the_old_sensors_are_gone(self):
        base, after = self.changed()
        for c in ("rescore", "check", "report", "bite", "detect"):
            with self.subTest(Template("sensors.py $c is gone").substitute(c=c)):
                self.assertEqual(self.n(c)[0], 2)
        for f in ("--tier", "--allowed", "--scope"):
            with self.subTest(Template("diff takes no $f: size is not measured").substitute(f=f)):
                self.assertEqual(self.n("diff", "--from", base, "--to", after, f, "x")[0], 2)


if __name__ == "__main__":
    unittest.main()
