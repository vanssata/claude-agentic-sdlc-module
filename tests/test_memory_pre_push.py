#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
hooks/memory-pre-push.py and `memory enable|disable` (spec §D10, §I5, R14,
R16, R17, A8, A10): the checks V1–V9 on the pushed blobs, per ref; the exit
codes; the shim installed only where no hook and no core.hooksPath exist.
"""
import importlib.util
import json
import os
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import memory_sync as ms  # noqa: E402  pylint: disable=wrong-import-position

ZERO = "0" * 40
FACTOR = float(os.environ.get("AI_TIMED_FACTOR", "1"))


class Repo(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.base = self.p.commit("memory on")
        self.task, _ = self.p.light_task("first change")
        self.head = self.p.commit("first task")

    def package(self):
        name = sorted(os.listdir(self.p.path(".ai/memory")))[0]
        return ".ai/memory/" + name

    def lines(self):
        return self.p.read(self.package(), binary=True).split(b"\n")[:-1]

    def put(self, lines, message="edit"):
        self.p.write(self.package(), b"\n".join(lines) + b"\n", mode="wb")
        return self.p.commit(message)

    def check(self, old, new):
        done = mh.hook_run(self.p.root, "--range", "%s..%s" % (old, new))
        return done.returncode, done.stderr


class TestChecks(Repo):
    def test_a_valid_range_is_clean(self):
        self.assertEqual(self.check(self.base, self.head), (0, ""))

    def test_v1_crlf_and_bom_name_the_line(self):
        lines = self.lines()
        lines[2] = lines[2] + b"\r"
        code, err = self.check(self.head, self.put(lines))
        self.assertEqual(code, 1)
        self.assertRegex(err, r"memory-pre-push: %s\.\.\w+: V1: %s:3: CRLF line ending — fix: " % (
            self.head, self.package().replace(".", r"\.")))
        self.assertIn("checked 1 packages", err)
        lines = self.lines()
        lines[0] = b"\xef\xbb\xbf" + lines[0].rstrip(b"\r")
        code, err = self.check(self.head, self.put([l.rstrip(b"\r") for l in lines]))
        self.assertIn(":1: starts with a UTF-8 BOM", err)

    def test_v2_a_lost_record(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        kept = [l for l in lines if json.loads(l).get("rid") != json.loads(lines[1]).get("rid")]
        del seal
        code, err = self.check(self.head, self.put(kept))
        self.assertEqual(code, 1)
        self.assertIn(": V2: .ai/memory/: 1 record(s) of", err)

    def test_v3_two_unchained_seals(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        other = mf.with_rid(dict(seal, goal="another goal"))
        code, err = self.check(self.head, self.put(lines + [mf.canonical(other)]))
        self.assertEqual(code, 1)
        self.assertIn(": V3: ", err)
        self.assertIn("%s#1 has 2 seals not chained by supersedes" % self.task, err)

    def test_v4_a_digest_that_does_not_match(self):
        lines = self.lines()
        seal = json.loads(lines[-1])
        bad = mf.with_rid(dict(seal, digest="sha256:" + "0" * 64))
        code, err = self.check(self.head, self.put(lines[:-1] + [mf.canonical(bad)]))
        self.assertEqual(code, 1)
        self.assertIn(": V4: ", err)

    def test_v5_a_closed_task_without_its_record(self):
        q = mh.Project("files", tmp=self.p.tmp)
        task, _ = q.light_task("closed before enable")
        q.ok("memory", "enable", "--author", "dev", human=True)
        head = q.commit("enable")
        done = mh.hook_run(q.root, "--tree", head)
        self.assertEqual(done.returncode, 1)
        self.assertIn("V5: .ai/reports/%s/events.jsonl: %s#1 is closed but has no seal — fix: state.py memory "
                      "export %s" % (task, task, task), done.stderr)

    def test_v5_legacy_tasks_without_a_seal_are_not_findings(self):
        os.makedirs(self.p.path(".ai/reports/T-2026-10-28-009"))
        for name in ("events.jsonl", "task.md"):
            with open(os.path.join(mh.FIXTURES, "legacy-reports", "T-2026-10-28-009", name), encoding="utf-8") as fh:
                self.p.write(".ai/reports/T-2026-10-28-009/" + name, fh.read())
        self.assertEqual(self.check(self.head, self.p.commit("legacy dir")), (0, ""))
        self.assertIn("legacy, not migrated: 1", self.p.ok("memory", "status").stdout)

    def test_v6_logs_and_local_data(self):
        self.p.write(".ai/reports/%s/suite-1.log" % self.task, "log\n")
        code, err = self.check(self.head, self.p.commit("a log"))
        self.assertEqual(code, 1)
        self.assertIn(": V6: .ai/reports/%s/suite-1.log: a log is committed" % self.task, err)
        self.p.git("rm", "-q", "--cached", ".ai/reports/%s/suite-1.log" % self.task)
        self.p.git("add", "-f", ".ai/local/memory/batches.json")
        code, err = self.check(self.head, self.p.commit("local data"))
        self.assertIn(": V6: .ai/local/memory/batches.json: local data is committed", err)

    def test_v7_with_cleanup_on(self):
        self.p.memory_json(cleanup=True)
        code, err = self.check(self.head, self.p.commit("cleanup on"))
        self.assertEqual(code, 1)
        self.assertIn(": V7: .ai/reports/%s/: cleanup is on and %s is sealed" % (self.task, self.task), err)

    def test_v8_size(self):
        self.p.memory_json(package_max_bytes=200)
        code, err = self.check(self.head, self.p.commit("tiny limit"))
        self.assertEqual(code, 1)
        self.assertIn("over twice package_max_bytes", err)
        self.p.memory_json(package_max_bytes=len(self.p.read(self.package(), binary=True)) - 1)
        code, err = self.check(self.head, self.p.commit("warn only"))
        self.assertEqual(code, 0, err)
        self.assertIn("V8-warn", err)

    def test_files_mode_is_silent_and_errors_fail_closed(self):
        self.p.memory_json(mode="files")
        self.assertEqual(self.check(self.head, self.p.commit("off")), (0, ""))
        code, err = self.check("nosuchrev", "alsono")
        self.assertEqual(code, 3)
        self.assertIn("state.py memory verify --all", err)
        self.assertIn("git push --no-verify", err)

    def test_the_hook_form_per_ref(self):
        remote = os.path.join(self.p.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", remote], check=True)
        self.p.git("remote", "add", "origin", remote)
        self.p.git("push", "-q", "--no-verify", "origin", self.base + ":refs/heads/main")
        self.p.git("fetch", "-q", "origin")
        lines = self.lines()
        bad = self.put(lines[:1] + [lines[1] + b"\r"] + lines[2:])
        stdin = "".join(["refs/heads/main %s refs/heads/main %s\n" % (self.head, self.base),
                         "refs/heads/new %s refs/heads/new %s\n" % (bad, ZERO),
                         "refs/tags/v1 %s refs/tags/v1 %s\n" % (bad, ZERO),
                         "(delete) %s refs/heads/gone %s\n" % (ZERO, self.base)])
        done = mh.hook_run(self.p.root, "origin", remote, stdin=stdin)
        self.assertEqual(done.returncode, 1)
        self.assertIn("memory-pre-push: refs/heads/new: V1:", done.stderr)
        self.assertNotIn("refs/heads/main:", done.stderr)
        self.assertNotIn("refs/tags/v1", done.stderr)
        self.assertEqual(mh.hook_run(self.p.root, "origin", remote, stdin=stdin.splitlines()[0] + "\n")
                         .returncode, 0)

    def test_v9_a_pending_export_stops_a_local_push(self):
        os.makedirs(self.p.path(".ai/local/memory/outbox"), exist_ok=True)
        self.p.write(".ai/local/memory/outbox/T-x~1.jsonl", "{}\n")
        stdin = "refs/heads/main %s refs/heads/main %s\n" % (self.head, self.base)
        done = mh.hook_run(self.p.root, "origin", "url", stdin=stdin)
        self.assertEqual(done.returncode, 1)
        self.assertIn("V9: .ai/local/memory/outbox: an export is pending", done.stderr)
        self.assertEqual(self.check(self.base, self.head), (0, ""))          # --range: V9 off

    def test_a_real_push_runs_the_installed_hook(self):
        remote = os.path.join(self.p.tmp, "remote.git")
        subprocess.run(["git", "init", "-q", "--bare", "--initial-branch=main", remote], check=True)
        self.p.git("remote", "add", "origin", remote)
        self.assertEqual(self.p.git("push", "-q", "origin", "main", check=False).returncode, 0)
        lines = self.lines()
        self.put(lines[:1] + lines[2:])
        done = self.p.git("push", "-q", "origin", "main", check=False)
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("V2", done.stderr)

    def test_v6_sqlite_outside_ai_is_the_projects(self):
        """Review M6: only the index's own kind of file under .ai/ is refused."""
        self.p.write("tests/fixtures/db/app.sqlite3", "SQLite format 3\n")
        self.assertEqual(self.check(self.head, self.p.commit("a fixture db")), (0, ""))
        self.p.write(".ai/index.sqlite3", "SQLite format 3\n")
        code, err = self.check(self.head, self.p.commit("an index"))
        self.assertEqual(code, 1)
        self.assertIn(": V6: .ai/index.sqlite3: local data is committed", err)

    def test_journals_are_read_in_one_batch(self):
        """Review M5: one `cat-file --batch` for all journals, not one per journal."""
        for n in range(6):
            self.p.light_task("task %d" % n, change="x = %d\n" % (n + 10))
        head = self.p.commit("six more")
        calls = []
        real = ms.subprocess.run

        def counting(args, *a, **kw):
            if "cat-file" in args and "--batch" in args:
                calls.append(args)
            return real(args, *a, **kw)  # pylint: disable=subprocess-run-check
        ms.subprocess.run = counting
        try:
            findings, stats = ms.validate_range(self.p.root, self.head, head)
        finally:
            ms.subprocess.run = real
        self.assertEqual(findings, [])
        self.assertEqual(stats["tasks"], 7)
        self.assertLessEqual(len(calls), 3, calls)                      # T's packages, O's, T's journals


class TestTimed(unittest.TestCase):
    def test_a_59_task_history_validates_quickly(self):
        spec = importlib.util.spec_from_file_location("bench", os.path.join(mh.ROOT, "tools", "benchmark-memory.py"))
        bench = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(bench)
        p = mh.Project()
        self.addCleanup(p.close)
        p.memory_json()
        bench.write_packages(p.root, bench.generate(59, seed=2))
        head = p.commit("59 tasks")
        started = time.time()
        done = mh.hook_run(p.root, "--tree", head)
        elapsed = time.time() - started
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertLess(elapsed, 0.5 * FACTOR + 0.4, "%.3f s (the sanity bound is 500 ms plus interpreter start)"
                        % elapsed)


class TestInstall(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)

    def hook(self):
        return self.p.path(".git/hooks/pre-push")

    def test_enable_and_disable_need_the_human(self):
        for args in (("memory", "enable"), ("memory", "disable")):
            done = self.p.run(*args)
            self.assertEqual(done.returncode, 5, args)
            self.assertIn("APPROVAL_REFUSED", done.stderr)
        self.assertFalse(self.p.exists(".ai/policies/memory.json"))
        self.assertFalse(os.path.exists(self.hook()))

    def test_install_idempotent_and_removed(self):
        self.assertIn("pre-push: installed", self.p.ok("memory", "enable", human=True).stdout)
        self.assertTrue(os.access(self.hook(), os.X_OK))
        with open(self.hook(), encoding="utf-8") as fh:
            self.assertIn(ms.HOOK_MARKER, fh.read())
        self.assertIn("pre-push: current", self.p.ok("memory", "enable", human=True).stdout)
        policy = json.loads(self.p.read(".ai/policies/memory.json"))
        self.assertEqual((policy["mode"], policy["period"], policy["cleanup"]), ("packages", "quarter", False))
        out = self.p.ok("memory", "disable", human=True).stdout
        self.assertIn("pre-push: removed", out)
        self.assertFalse(os.path.exists(self.hook()))
        self.assertEqual(json.loads(self.p.read(".ai/policies/memory.json"))["mode"], "files")

    def test_a_foreign_hook_is_kept_and_the_snippet_printed(self):
        os.makedirs(os.path.dirname(self.hook()), exist_ok=True)
        self.p.write(".git/hooks/pre-push", "#!/bin/sh\necho mine\n")
        out = self.p.ok("memory", "enable", human=True).stdout
        self.assertIn("pre-push: foreign", out)
        self.assertIn('rr_in=$(mktemp) && cat > "$rr_in"', out)
        self.assertEqual(self.p.read(".git/hooks/pre-push"), "#!/bin/sh\necho mine\n")
        self.p.ok("memory", "disable", human=True)
        self.assertEqual(self.p.read(".git/hooks/pre-push"), "#!/bin/sh\necho mine\n")

    def test_core_hooks_path_is_respected(self):
        self.p.git("config", "core.hooksPath", ".githooks")
        out = self.p.ok("memory", "enable", human=True).stdout
        self.assertIn("pre-push: hookspath", out)
        self.assertFalse(self.p.exists(".githooks/pre-push"))
        self.assertFalse(os.path.exists(self.hook()))

    def run_shim(self, stdin=""):
        return subprocess.run(["sh", self.hook(), "origin", "url"], input=stdin, capture_output=True, text=True,
                              check=False, cwd=self.p.root,
                              env=mh.clean_env({"HOME": self.p.tmp, "CODEX_HOME": self.p.tmp}))

    def test_the_shim_without_a_validator_warns_and_passes(self):
        self.p.ok("memory", "enable", human=True)
        text = self.p.read(".git/hooks/pre-push").replace(ms.VALIDATOR, "/nonexistent/memory-pre-push.py")
        self.p.write(".git/hooks/pre-push", text.replace(ms.SELF, "/nonexistent/memory_sync.py"))
        done = self.run_shim()
        self.assertEqual(done.returncode, 0)
        self.assertIn("validator not found — this push is not checked", done.stderr)
        status = self.p.ok("memory", "status", env={"HOME": self.p.tmp, "CODEX_HOME": self.p.tmp}).stdout
        self.assertIn("validator missing — pushes are NOT checked", status)

    def test_without_the_hook_file_the_shim_runs_the_module(self):
        """Review M8: a Codex install copies skills/ai-task/ but not every hook."""
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        text = self.p.read(".git/hooks/pre-push").replace(ms.VALIDATOR, "/nonexistent/memory-pre-push.py")
        self.p.write(".git/hooks/pre-push", text)
        base = self.p.commit("memory on")
        self.p.light_task("checked through the module")
        head = self.p.commit("task")
        name = sorted(os.listdir(self.p.path(".ai/memory")))[0]
        lines = self.p.read(".ai/memory/" + name, binary=True).split(b"\n")
        self.p.write(".ai/memory/" + name, b"\n".join(lines[:1] + lines[2:]), mode="wb")
        bad = self.p.commit("drops a record")
        self.assertEqual(self.run_shim("refs/heads/main %s refs/heads/main %s\n" % (head, base)).returncode, 0)
        done = self.run_shim("refs/heads/main %s refs/heads/main %s\n" % (bad, head))
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn(": V2: ", done.stderr)
        self.assertNotIn("not checked", done.stderr)
        self.assertNotIn("validator missing", self.p.ok("memory", "status").stdout)


if __name__ == "__main__":
    unittest.main()
