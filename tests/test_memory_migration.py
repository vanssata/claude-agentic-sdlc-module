#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
`state.py memory migrate` (spec §D12, R24, R25, A2, A12): the report first;
then closed legacy tasks from tracked files into batches by their closed_at
period, sealed keys skipped, the same rids in every clone; known-risks.md into
risk entries that render its sections byte for byte, and a stub; the
committed logs moved out by the human.
"""
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_compact as mc  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position

LEGACY = os.path.join(mh.FIXTURES, "legacy-reports")
RISKS = ("# Known risks\n\n<!-- notes -->\n\n## First thing\n\n- **Found**: 2026-10-01, by T-2026-10-01-001\n"
         "- **Where**: `src/widget.py:1`\n- **What could go wrong**: it breaks\n- **Status**: open\n\n"
         "## Second thing\n\n- **Where**: `hooks/x.py`\n- **Status**: accepted — callers\n- **Label**: KNOWN FACT\n")


def legacy_project(name="p", tmp=None):
    p = mh.Project(name, tmp=tmp)
    for task in sorted(os.listdir(LEGACY)):
        shutil.copytree(os.path.join(LEGACY, task), p.path(".ai/reports/" + task))
    p.write(".ai/project/known-risks.md", RISKS)
    p.ok("memory", "enable", "--author", "dev", human=True)
    p.commit("legacy reports")
    return p


def package_entries(p):
    out = []
    for name in sorted(os.listdir(p.path(".ai/memory"))) if p.exists(".ai/memory") else []:
        _, entries, errors = mf.parse_package(p.read(".ai/memory/" + name, binary=True), name)
        assert not errors, errors
        out += entries
    return out


class TestReport(unittest.TestCase):
    def test_the_report_comes_first_and_changes_nothing(self):
        p = legacy_project()
        self.addCleanup(p.close)
        before = p.tree_listing()
        out = p.ok("memory", "migrate", "--report").stdout
        self.assertIn(".ai/local/memory/migration-report.md", out)
        report = p.read(".ai/local/memory/migration-report.md")
        self.assertIn("| T-2026-10-15-001 | 2 | yes | T-2026-10-15-001 | 11/11, 46/46 | restarted, closed | - |",
                      report)
        self.assertIn("| T-2026-09-23-001 | 1 | no (state-only)", report)
        self.assertIn("- .ai/reports/T-2026-10-25-004/bite-must_fail.log (", report)
        self.assertIn("## Committed logs (", report)
        self.assertIn("- sections parsed: 2", report)
        self.assertIn("- renders byte for byte: yes", report)
        self.assertIn("- duplicate titles: none", report)
        self.assertIn("- handoff_written: ", report)
        self.assertEqual([f for f in p.tree_listing() if not f.startswith(".ai/local/")],
                         [f for f in before if not f.startswith(".ai/local/")])
        self.assertFalse(p.exists(".ai/memory"))


class TestApply(unittest.TestCase):
    def setUp(self):
        self.p = legacy_project()
        self.addCleanup(self.p.close)

    def test_apply_seals_every_closed_task_once(self):
        files_mode_recall = self.p.ok("recall", "--files", "hooks/**,skills/**", "--budget", "8000").stdout
        out = self.p.ok("memory", "migrate", "--apply").stdout
        self.assertIn("backup: .ai/local/memory/backup-", out)
        tar = [n for n in os.listdir(self.p.path(".ai/local/memory")) if n.startswith("backup-")]
        self.assertEqual(len(tar), 1)
        entries = package_entries(self.p)
        seals = sorted(mf.key_of(e) for e in entries if e["kind"] == "task")
        self.assertIn("T-2026-10-15-001#1", seals)
        self.assertIn("T-2026-10-15-001#2", seals)
        self.assertEqual(len(seals), 8)
        self.assertTrue(all(e["source"] == "migration" for e in entries if e["kind"] == "task"))
        names = sorted(os.listdir(self.p.path(".ai/memory")))
        self.assertEqual(sorted({n.split(".")[0] for n in names}), ["2026-Q3", "2026-Q4"])
        self.assertEqual(self.p.ok("memory", "verify").stdout.splitlines()[-1], "memory verify: ok")
        again = self.p.ok("memory", "migrate", "--apply").stdout
        self.assertIn("migrated 0 task instance(s); 8 already sealed", again)
        self.assertEqual(sorted(os.listdir(self.p.path(".ai/memory"))), names)
        packaged = self.p.ok("recall", "--files", "hooks/**,skills/**", "--budget", "8000").stdout
        self.assertEqual(files_mode_recall.splitlines()[1:], packaged.splitlines()[1:])     # A2
        self.assertIn("packages 2 + legacy 0", packaged.splitlines()[0])
        self.p.commit("migrated")
        done = mh.hook_run(self.p.root, "--tree", "HEAD")
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_a_large_period_rotates_batches(self):
        """Review M7: whole tasks per batch, a new batch before package_max_bytes."""
        cap = 30000
        self.p.memory_json(package_max_bytes=cap)
        self.p.commit("a small cap")
        self.p.ok("memory", "migrate", "--apply")
        q4 = sorted(n for n in os.listdir(self.p.path(".ai/memory")) if n.startswith("2026-Q4."))
        self.assertGreater(len(q4), 1)
        for name in q4:
            _, entries, errors = mf.parse_package(self.p.read(".ai/memory/" + name, binary=True), name)
            self.assertEqual(errors, [])
            seals = [e for e in entries if e["kind"] == "task"]
            size = len(self.p.read(".ai/memory/" + name, binary=True))
            self.assertTrue(size <= cap or len(seals) == 1, (name, size, len(seals)))
            for seal in seals:                # a task never splits across batches
                self.assertEqual(seal["entries"], sum(1 for e in entries if mf.key_of(e) == mf.key_of(seal)
                                                      and e["kind"] != "task"))
        self.assertEqual(len([e for e in package_entries(self.p) if e["kind"] == "task"]), 8)

    def test_two_clones_give_the_same_rids(self):
        q = mh.Project("q", tmp=self.p.tmp, clone_of=self.p.root)
        q.ok("memory", "enable", "--author", "other", human=True)
        self.p.ok("memory", "migrate", "--apply")
        q.ok("memory", "migrate", "--apply")
        self.assertEqual({e["rid"] for e in package_entries(self.p)}, {e["rid"] for e in package_entries(q)})

    def test_incomplete_coverage_is_reported_not_exported(self):
        with open(self.p.path(".ai/reports/T-2026-10-26-002/events.jsonl"), "a", encoding="utf-8") as fh:
            fh.write('{"torn": \n')
        self.p.commit("a torn line")
        out = self.p.ok("memory", "migrate", "--apply").stdout
        self.assertIn("1 incomplete (reported, not exported)", out)
        self.assertIn("incomplete: T-2026-10-26-002#1", out)
        self.assertNotIn("T-2026-10-26-002", {e["task"] for e in package_entries(self.p)})

    def test_risks_become_entries_and_a_stub(self):
        out = self.p.ok("memory", "migrate", "--apply", "--risks").stdout
        self.assertIn("risks: 2 entries", out)
        stub = self.p.read(".ai/project/known-risks.md")
        self.assertLessEqual(len(stub.splitlines()), 10)
        self.assertEqual(mc.parse_known_risks(stub)[0], [])
        risks = [e for e in package_entries(self.p) if e["kind"] == "risk"]
        self.assertEqual([r["actor"] for r in risks], ["migration", "migration"])
        _, leftovers = mc.parse_known_risks(RISKS)
        rendered = mc.render_known_risks(sorted(risks, key=lambda r: r["seq"]), leftovers)
        self.assertEqual(rendered, RISKS)                                     # A12
        self.assertEqual(sum(1 for r in risks if r.get("label_derived")), 1)
        listed = self.p.ok("memory", "risks", "--status", "all").stdout
        self.assertIn("First thing", listed)
        self.assertIn("Second thing", listed)

    def test_move_logs_is_the_humans(self):
        done = self.p.run("memory", "migrate", "--move-logs", "--confirm-delete", "dev")
        self.assertEqual(done.returncode, 5)
        done = self.p.run("memory", "migrate", "--move-logs", "--confirm-delete", "someone", human=True)
        self.assertEqual(done.returncode, 2)
        out = self.p.ok("memory", "migrate", "--move-logs", "--confirm-delete", "dev", human=True).stdout
        self.assertIn("git rm --cached --quiet --pathspec-from-file=.ai/local/memory/logs-to-rm.txt", out)
        self.assertTrue(self.p.exists(".ai/state/logs/T-2026-10-25-004/legacy/bite-must_fail.log"))
        self.assertFalse(self.p.exists(".ai/reports/T-2026-10-25-004/bite-must_fail.log"))
        self.p.git("rm", "--cached", "--quiet", "--pathspec-from-file=.ai/local/memory/logs-to-rm.txt")
        self.p.commit("drop logs")
        tracked = self.p.git("ls-files", ".ai/reports").stdout.split()
        self.assertFalse([t for t in tracked if t.endswith(".log")])
        listing = self.p.read(".ai/local/memory/logs-to-rm.txt").split()
        self.assertEqual(len(listing), 6)


if __name__ == "__main__":
    unittest.main()
