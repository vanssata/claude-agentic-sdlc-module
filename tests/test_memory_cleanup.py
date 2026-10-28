#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Cleanup, restore, redact and pack (spec §D4, §D6, §D13, R8, R16, R20, R21,
R22, A9 B6, A10): cleanup ships off and runs only on the R22 conditions; it
moves, never deletes; a fresh clone shows every task from packages alone;
restore brings a directory back, or a marked reconstruction; a redaction is
the one change V2 accepts; pack keeps the rid set; all of them but restore
are the human's.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import memory_sync as ms  # noqa: E402  pylint: disable=wrong-import-position

USAGE = os.path.join(mh.ROOT, "skills", "usage-report", "usage-report.py")


def package_entries(p):
    out = []
    for name in sorted(os.listdir(p.path(".ai/memory"))):
        _, entries, errors = mf.parse_package(p.read(".ai/memory/" + name, binary=True), name)
        assert not errors, errors
        out += entries
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.task, _ = self.p.rich_task("decide the key")
        self.p.commit("one task")

    def cleanup_on(self):
        self.p.memory_json(cleanup=True)

    def usage(self, root, task):
        tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(["rm", "-rf", tmp], check=False))
        return subprocess.run([sys.executable, "-I", USAGE, "--task", task, "--project", root], capture_output=True,
                              text=True, check=False, env=mh.clean_env({"HOME": tmp})).stdout


class TestCleanup(Base):
    def test_refusals(self):
        human = ("memory", "cleanup", "--all", "--confirm-delete", "dev")
        self.assertEqual(self.p.run(*human).returncode, 5)
        done = self.p.run(*human, human=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("cleanup is off", done.stderr)
        self.cleanup_on()
        self.assertEqual(self.p.run("memory", "cleanup", "--all", "--confirm-delete", "x", human=True).returncode, 2)
        self.assertEqual(self.p.run("memory", "cleanup", "--all", human=True).returncode, 2)

    def test_cleanup_moves_and_show_is_unchanged(self):
        before = self.p.ok("memory", "show", self.task).stdout
        window = self.usage(self.p.root, self.task)
        self.cleanup_on()
        out = self.p.ok("memory", "cleanup", "--all", "--confirm-delete", "dev", human=True).stdout
        self.assertIn(".ai/reports/%s → .ai/state/logs/%s/report" % (self.task, self.task), out)
        self.assertFalse(self.p.exists(".ai/reports/" + self.task))
        self.assertTrue(self.p.exists(".ai/state/logs/%s/report/events.jsonl" % self.task))
        self.assertEqual(self.p.ok("memory", "show", self.task).stdout, before)              # R21
        self.assertEqual(self.usage(self.p.root, self.task).splitlines()[0], window.splitlines()[0])  # R20
        self.p.commit("cleaned up")
        self.assertEqual(self.p.run("memory", "verify", "--fresh-clone").returncode, 0)

    def test_a_record_that_misses_a_line_blocks_cleanup(self):
        with open(self.p.path(".ai/reports/%s/events.jsonl" % self.task), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-10-28T23:00:00.000Z", "task": self.task, "event": "note",
                                 "actor": "agent", "runtime": "claude", "stage": "done", "detail": "late",
                                 "data": {"kind": "decision", "text": "late"}}) + "\n")
        self.cleanup_on()
        done = self.p.run("memory", "cleanup", "--all", "--confirm-delete", "dev", human=True)
        self.assertEqual(done.returncode, 1)
        self.assertIn("V5", done.stderr)
        self.assertTrue(self.p.exists(".ai/reports/" + self.task))

    def test_across_filesystems_copy_verify_remove(self):
        self.cleanup_on()
        self.p.ok("memory", "cleanup", self.task, "--confirm-delete", "dev", human=True,
                  env={"AI_MEMORY_FORCE_EXDEV": "1"})
        self.assertFalse(self.p.exists(".ai/reports/" + self.task))
        self.assertTrue(self.p.exists(".ai/state/logs/%s/report/task.md" % self.task))

    def test_close_cleans_up_its_own_task_and_b6_crash_deletes_nothing(self):
        self.cleanup_on()
        self.p.commit("cleanup on")
        task = self.p.start("second", files="src/widget.py")
        self.p.write("src/widget.py", "x = 11\n")
        self.p.ok("verify", "--scope", "all")
        done = self.p.run("close", env={"AI_MEMORY_CRASH_AT": "B6"})
        self.assertEqual(done.returncode, 70)
        self.assertTrue(self.p.exists(".ai/reports/%s/events.jsonl" % task))           # not deleted early
        self.assertIn(task, {e["task"] for e in package_entries(self.p)})
        self.p.ok("memory", "cleanup", task, "--confirm-delete", "dev", human=True)
        self.assertFalse(self.p.exists(".ai/reports/" + task))
        third = self.p.start("third", files="src/widget.py")
        self.p.write("src/widget.py", "x = 12\n")
        self.p.ok("verify", "--scope", "all")
        out = self.p.ok("close").stdout
        self.assertIn("cleanup: .ai/reports/%s → .ai/state/logs/%s/report" % (third, third), out)


class TestRestore(Base):
    def test_restore_from_the_raw_store(self):
        self.cleanup_on()
        self.p.ok("memory", "cleanup", "--all", "--confirm-delete", "dev", human=True)
        out = self.p.ok("memory", "restore", self.task).stdout
        self.assertIn("restored from .ai/state/logs/%s/report" % self.task, out)
        self.assertTrue(self.p.exists(".ai/reports/%s/events.jsonl" % self.task))

    def test_restore_from_the_record_in_a_clone_without_raw_files(self):
        self.cleanup_on()
        self.p.ok("memory", "cleanup", "--all", "--confirm-delete", "dev", human=True)
        self.p.commit("cleaned")
        q = mh.Project("clone", tmp=self.p.tmp, clone_of=self.p.root)
        self.assertIn("(no journal: the window is the record's seal for %s)" % self.task,
                      self.usage(q.root, self.task))                                # R20 in a clone
        out = q.ok("memory", "restore", "--all").stdout
        self.assertIn("%s restored from record" % self.task, out)
        md = q.read(".ai/reports/%s/task.md" % self.task)
        self.assertTrue(md.startswith("<!-- restored from record "))
        events = [json.loads(line) for line in q.read(".ai/reports/%s/events.jsonl" % self.task).splitlines()]
        self.assertTrue(all(e["data"]["restored"] for e in events))
        self.assertEqual({e["actor"] for e in events} - {"agent", "human", "hook", "migration", "unknown"}, set())


class TestRedact(Base):
    def test_redaction_is_the_humans_and_v2_accepts_it(self):
        note = [e for e in package_entries(self.p) if e["kind"] == "note"][0]
        self.assertEqual(self.p.run("memory", "redact", note["rid"], "--field", "text", "--why", "a secret")
                         .returncode, 5)
        old = self.p.git("rev-parse", "HEAD").stdout.strip()
        out = self.p.ok("memory", "redact", note["rid"], "--field", "text", "--why", "a secret", human=True).stdout
        self.assertIn("redacted: text", out)
        entries = package_entries(self.p)
        self.assertNotIn(note["rid"], {e["rid"] for e in entries})
        rewritten = [e for e in entries if e["kind"] == "note" and e["text"] == "[redacted]"]
        self.assertEqual(len(rewritten), 1)
        redaction = [e for e in entries if e["kind"] == "redaction"][0]
        self.assertEqual((redaction["target"], redaction["field"], redaction["why"]), (note["rid"], "text",
                                                                                      "a secret"))
        self.assertEqual(self.p.ok("memory", "verify").stdout.splitlines()[-1], "memory verify: ok")
        new = self.p.commit("redacted")
        done = mh.hook_run(self.p.root, "--range", "%s..%s" % (old, new))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(self.p.run("memory", "redact", note["rid"], "--field", "text", "--why", "again",
                                    human=True).returncode, 1)


class TestPack(unittest.TestCase):
    def test_pack_a_closed_period_keeps_the_rid_set(self):
        p = mh.Project()
        self.addCleanup(p.close)
        ids = [p.light_task("task %d" % i, change="x = %d\n" % i)[0] for i in range(3)]
        p.ok("memory", "enable", "--author", "dev", "--period", "month", human=True)
        cfg = ms.load_config(p.root)
        for i, task in enumerate(ids):
            p.git("checkout", "-q", "-B", "branch-%d" % i)
            ms.export(p.root, [task], cfg, stamp="2025-03-1%dT00:00:00Z" % i)
        batches = sorted(os.listdir(p.path(".ai/memory")))
        self.assertEqual(len(batches), 3)
        rids = {e["rid"] for e in package_entries(p)}
        self.assertEqual(p.run("memory", "pack", "--period", "2025-03", "--confirm-delete", "dev").returncode, 5)
        self.assertEqual(p.run("memory", "pack", "--period", "2999-01", "--confirm-delete", "dev",
                               human=True).returncode, 2)
        old = p.commit("batches")
        out = p.ok("memory", "pack", "--period", "2025-03", "--confirm-delete", "dev", human=True).stdout
        self.assertIn("pack: .ai/memory/2025-03.dev.jsonl", out)
        self.assertEqual(os.listdir(p.path(".ai/memory")), ["2025-03.dev.jsonl"])
        self.assertEqual({e["rid"] for e in package_entries(p)}, rids)
        new = p.commit("packed")
        done = mh.hook_run(p.root, "--range", "%s..%s" % (old, new))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(p.read(".ai/local/memory/batches.json"))["open"], {})


if __name__ == "__main__":
    unittest.main()
