#!/usr/bin/env python3
"""R1-R5: tests/run_suite.py, the parallel runner, on the fixtures in tests/fixtures/run-suite.

A false green here is BLOCKER-class: each way a file can go wrong (failure, error, import
error, crash without a result, unexpected success, timeout, garbled result) is pinned by a
case that the runner must report red with exit 1.
"""
import importlib.util
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(ROOT, "tests", "run_suite.py")
FIX = os.path.join("tests", "fixtures", "run-suite")


def load_runner():
    spec = importlib.util.spec_from_file_location("run_suite_under_test", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def porcelain():
    r = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
                       text=True, check=False)
    return r.stdout


class Base(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.mkdtemp(prefix="test-run-suite-")
        self.addCleanup(shutil.rmtree, self.scratch, True)
        self.alive = os.path.join(self.scratch, "alive")
        self.tmp = os.path.join(self.scratch, "tmp")
        os.mkdir(self.alive)
        os.mkdir(self.tmp)

    def env(self):
        env = dict(os.environ)
        env["RUN_SUITE_ALIVE_DIR"] = self.alive
        env["TMPDIR"] = self.tmp
        return env

    def args(self, *files, extra=()):
        return [sys.executable, "-I", RUNNER, "--start", os.path.join(ROOT, FIX), *extra, *files]

    def run_suite(self, *files, extra=(), timeout=120):
        r = subprocess.run(self.args(*files, extra=extra), cwd=ROOT, env=self.env(),
                           capture_output=True, text=True, timeout=timeout, check=False)
        return r.returncode, r.stdout + r.stderr

    def leftovers(self):
        """Processes whose command line carries this test's private TMPDIR."""
        r = subprocess.run(["pgrep", "-f", self.tmp], capture_output=True, text=True, check=False)
        return r.stdout.split()


class TestVerdicts(Base):
    def test_green_exits_0_with_unittest_tail(self):
        rc, out = self.run_suite("test_green.py", "test_skip.py")
        self.assertEqual(rc, 0, out)
        self.assertIn("Ran 3 tests in", out)
        self.assertEqual(out.rstrip().splitlines()[-1], "OK (skipped=1)")
        self.assertIn("ok    test_green.py", out)

    def test_failure_exits_1(self):
        rc, out = self.run_suite("test_fail.py")
        self.assertEqual(rc, 1, out)
        self.assertEqual(out.rstrip().splitlines()[-1], "FAILED (failures=1)")
        self.assertIn("==== FAIL test_fail.py (exit 1) ====", out)
        self.assertLess(out.index("FAIL  test_fail.py"), out.index("==== FAIL test_fail.py"))
        self.assertIn("==== end test_fail.py ====", out)

    def test_error_exits_1(self):
        rc, out = self.run_suite("test_error.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAILED (errors=1)", out)
        self.assertIn("fixture error", out)

    def test_import_error_exits_1(self):
        rc, out = self.run_suite("test_import_error.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAILED (errors=1)", out)
        self.assertIn("no_such_module_xyz", out)

    def test_crash_without_result_exits_1(self):
        rc, out = self.run_suite("test_crash.py")
        self.assertEqual(rc, 1, out)
        line = [ln for ln in out.splitlines() if ln.startswith("FAIL  test_crash.py")]
        self.assertEqual(len(line), 1, out)
        self.assertIn("no result", line[0])
        self.assertIn("FAILED", out.rstrip().splitlines()[-1])

    def test_unexpected_success_exits_1(self):
        rc, out = self.run_suite("test_unexpected_success.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAILED (unexpected successes=1)", out)

    def test_garbled_result_is_red(self):
        runner = load_runner()
        path = os.path.join(self.scratch, "garbled.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write('{"file": "test_x.py", "tests": 3, "fail')
        self.assertIsNone(runner.read_result(path))
        self.assertIsNone(runner.read_result(os.path.join(self.scratch, "missing.json")))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[1, 2]")
        self.assertIsNone(runner.read_result(path))
        # a child that writes a truncated result to the path in its own argv and exits 0
        start = os.path.join(self.scratch, "start")
        os.mkdir(start)
        with open(os.path.join(start, "test_garble.py"), "w", encoding="utf-8") as fh:
            fh.write(
                "import os, sys, unittest\n"
                "class T(unittest.TestCase):\n"
                "    def test_it(self):\n"
                "        with open(sys.argv[sys.argv.index('--result') + 1], 'w') as out:\n"
                "            out.write('{\"file\": \"test_garble.py\", \"tests\": 1, \"fail')\n"
                "        os._exit(0)\n")
        r = subprocess.run([sys.executable, "-I", RUNNER, "--start", start, "test_garble.py"],
                           cwd=ROOT, env=self.env(), capture_output=True, text=True,
                           timeout=60, check=False)
        out = r.stdout + r.stderr
        self.assertEqual(r.returncode, 1, out)
        self.assertIn("FAIL  test_garble.py", out)
        self.assertIn("unreadable result", out)

    def test_no_fail_fast(self):
        rc, out = self.run_suite("test_fail.py", "test_green.py")
        self.assertEqual(rc, 1, out)
        self.assertIn("FAIL  test_fail.py", out)
        self.assertIn("ok    test_green.py", out)
        self.assertIn("Ran 3 tests in", out)
        self.assertIn("FAILED (failures=1)", out)


class TestTimeoutAndSignals(Base):
    def test_timeout_kills_the_group(self):
        t0 = time.monotonic()
        rc, out = self.run_suite("test_hang.py", extra=("--timeout", "2"))
        self.assertLess(time.monotonic() - t0, 60)
        self.assertEqual(rc, 1, out)
        line = [ln for ln in out.splitlines() if ln.startswith("TIME  test_hang.py")]
        self.assertEqual(len(line), 1, out)
        self.assertIn("timed out after 2s", line[0])
        self.assertEqual(self.leftovers(), [])

    def test_sigterm_kills_children_and_exits_1(self):
        proc = subprocess.Popen(self.args("test_hang.py", "test_green.py"), cwd=ROOT, env=self.env(),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            deadline = time.monotonic() + 60
            while time.monotonic() < deadline and not any(
                    n.startswith("alive-") for n in os.listdir(self.alive)):
                time.sleep(0.1)
            self.assertTrue(any(n.startswith("alive-") for n in os.listdir(self.alive)),
                            "the hang fixture never started")
            self.assertNotEqual(self.leftovers(), [])
            proc.send_signal(signal.SIGTERM)
            out, _ = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.communicate()
        self.assertEqual(proc.returncode, 1, out)
        self.assertEqual(self.leftovers(), [])
        self.assertEqual(os.listdir(self.tmp), [], "the temporary directory was not removed")


class TestSerial(Base):
    def test_serial_runs_alone_after_the_parallel_phase(self):
        rc, out = self.run_suite("test_green.py", "test_serial.py", "test_skip.py",
                                 extra=("--serial", "test_serial.TestTimed"))
        self.assertEqual(rc, 0, out)
        self.assertIn("serial ok  test_serial.TestTimed  1 test", out)
        lines = out.splitlines()
        serial_at = [i for i, ln in enumerate(lines) if ln.startswith("serial ")][0]
        for name in ("test_green.py", "test_serial.py", "test_skip.py"):
            at = [i for i, ln in enumerate(lines) if ln.startswith("ok    " + name)]
            self.assertEqual(len(at), 1, out)
            self.assertLess(at[0], serial_at)
        self.assertIn("Ran 4 tests in", out)

    def test_serial_id_matching_nothing_is_usage(self):
        rc, out = self.run_suite("test_green.py", extra=("--serial", "test_serial.TestNope"))
        self.assertEqual(rc, 2, out)
        rc, out = self.run_suite("test_serial.py", extra=("--serial", "test_serial.Test"))
        self.assertEqual(rc, 2, "an id matches whole dotted components only: " + out)

    def test_default_serial_is_the_timed_class(self):
        runner = load_runner()
        self.assertEqual(runner.DEFAULT_SERIAL, "test_guard_characterization.TestTimed")
        r = subprocess.run([sys.executable, "-I", RUNNER, "--collect", "test_guard_characterization.py"],
                           cwd=ROOT, env=self.env(), capture_output=True, text=True,
                           timeout=120, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(any(ln.startswith(runner.DEFAULT_SERIAL + ".") for ln in r.stdout.splitlines()))


class TestUsage(Base):
    def test_literal_files_placeholder_is_usage(self):
        rc, out = self.run_suite("{files}")
        self.assertEqual(rc, 2, out)

    def test_unknown_and_non_test_files_are_usage(self):
        self.assertEqual(self.run_suite("test_no_such_file.py")[0], 2)
        self.assertEqual(self.run_suite("test_green.py", os.path.join("tests", "run_suite.py"))[0], 2)

    def test_jobs_below_one_is_usage(self):
        rc, out = self.run_suite("test_green.py", extra=("--jobs", "0"))
        self.assertEqual(rc, 2, out)

    def test_no_test_files_is_usage(self):
        empty = os.path.join(self.scratch, "empty")
        os.mkdir(empty)
        r = subprocess.run([sys.executable, "-I", RUNNER, "--start", empty], cwd=ROOT,
                           env=self.env(), capture_output=True, text=True, timeout=60, check=False)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)

    def test_a_path_in_another_directory_is_usage(self):
        rc, out = self.run_suite(os.path.join("tests", "test_run_suite.py"))
        self.assertEqual(rc, 2, out)

    def test_a_path_in_the_start_directory_is_accepted(self):
        rc, out = self.run_suite(os.path.join(FIX, "test_green.py"))
        self.assertEqual(rc, 0, out)


class TestEnvironmentAndRepository(Base):
    def test_writes_nothing_in_the_repository(self):
        before = porcelain()
        rc, out = self.run_suite("test_green.py", "test_fail.py")
        self.assertEqual(rc, 1, out)
        self.assertEqual(porcelain(), before)
        self.assertEqual(os.listdir(self.tmp), [], "the temporary directory was not removed")

    def test_environment_passes_through_unchanged(self):
        # the serial fixture reads RUN_SUITE_ALIVE_DIR from the child's environment
        rc, out = self.run_suite("test_serial.py", extra=("--serial", "test_serial.TestTimed"))
        self.assertEqual(rc, 0, out)


class TestCollect(Base):
    def test_collect_matches_discover(self):
        r = subprocess.run([sys.executable, "-I", RUNNER, "--collect"], cwd=ROOT, env=self.env(),
                           capture_output=True, text=True, timeout=300, check=False)
        self.assertEqual(r.returncode, 0, r.stderr)
        tests_dir = os.path.join(ROOT, "tests")

        def ids(suite):
            for item in suite:
                if isinstance(item, unittest.TestSuite):
                    yield from ids(item)
                else:
                    yield item.id()

        want = sorted(ids(unittest.TestLoader().discover(tests_dir, "test_*.py")))
        got = r.stdout.splitlines()
        self.assertEqual(got, want)
        self.assertGreater(len(got), 500)
        self.assertFalse([i for i in got if i.startswith(("test_green", "test_hang", "test_crash"))])


if __name__ == "__main__":
    unittest.main()
