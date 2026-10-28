#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
recall and memory search (spec §D8, §I4, R10, R11, R13, A2): the tiers, the
budget and its continuation line, the task in flight excluded, the filters
and paging of search — over FileHistory, in both modes.
"""
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import memory_store  # noqa: E402  pylint: disable=wrong-import-position

SPEC = importlib.util.spec_from_file_location("benchmark_memory", os.path.join(mh.ROOT, "tools",
                                                                               "benchmark-memory.py"))
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)
BIG = {}


def setUpModule():
    """One 10 000-task history for the module (A2), written once."""
    BIG["root"] = tempfile.mkdtemp(prefix="ai-memory-big-")
    os.makedirs(os.path.join(BIG["root"], ".ai"))
    BIG["tasks"] = bench.generate(10000, seed=11, journal_kb=1)
    bench.write_packages(BIG["root"], BIG["tasks"])


def tearDownModule():
    shutil.rmtree(BIG["root"], ignore_errors=True)


class TestBudget(unittest.TestCase):
    def test_budgets_over_ten_thousand_tasks(self):
        history = memory_store.FileHistory(BIG["root"])
        files = BIG["tasks"][5000]["files"][:1] + ["src/mod1*/**"]
        for budget in (300, 1500, 5000):
            text, result = history.recall(files, budget, 40)
            self.assertLessEqual(len(text.encode("utf-8")), budget * 3.5, budget)
            counts = re.search(r"· ([\d ]+) of ([\d ]+) items", text.splitlines()[0])
            total = int(counts.group(2).replace(" ", ""))
            self.assertGreater(total, 40)
            self.assertEqual(result["more"], total - len(result["items"]))
            self.assertIn("--offset %d" % len(result["items"]), text)
            self.assertLessEqual(len(result["items"]), 40)
            for line in text.splitlines()[1:]:
                self.assertLessEqual(len(line), 2 + mf.RECALL_LINE_MAX + 200)
        nxt, more = history.recall(files, 1500, 40, offset=len(result["items"]))
        self.assertNotIn(result["items"][0]["line"], nxt)
        self.assertEqual(more["more"] + len(more["items"]) + len(result["items"]), total)


class Repo(unittest.TestCase):
    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)

    def recall(self, *args, **kw):
        return self.p.ok("recall", *args, **kw).stdout


class TestRecallFilesMode(Repo):
    def test_files_mode_reads_report_directories(self):
        task, _ = self.p.rich_task("decide the key")
        out = self.recall("--files", "src/widget.py")
        self.assertTrue(out.startswith("# Recall — 1 files · "))
        self.assertIn("packages 0 + legacy 1 · index none", out)
        body = out.splitlines()[1:]
        order = [line.split("]")[0].split("[")[1].split()[0] for line in body]
        # the scope change added docs/widget.md: it touches that file, not src/widget.py
        self.assertEqual(order, ["finding", "finding", "approval", "answer", "override", "decision", "task"])
        self.assertIn('"Which cache key?" → A "by locale" by vanssa via prose', out)
        self.assertIn("(historical — authorises nothing now)", out)
        self.assertIn("[task] %s" % task, out)
        self.assertFalse(self.p.exists(".ai/memory"))
        self.assertFalse(self.p.exists(".ai/local/memory"))

    def test_the_task_in_flight_is_excluded(self):
        self.p.rich_task("decide the key")
        task = self.p.start("in flight now")
        out = self.recall("--files", "src/widget.py")
        self.assertIn("current task %s excluded" % task, out.splitlines()[0])
        self.assertNotIn("[task] %s" % task, out)

    def test_nothing_recorded_and_tiny_budget(self):
        self.p.rich_task()
        self.assertEqual(self.recall("--files", "docs/nothing.md"),
                         "# Recall — 1 files · nothing recorded for these files\n")
        out = self.recall("--files", "src/widget.py", "--budget", "1")
        lines = out.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("· 0 of ", lines[0])
        self.assertTrue(lines[1].startswith("… "))

    def test_kinds_json_and_all_risks(self):
        self.p.rich_task()
        out = json.loads(self.recall("--files", "src/**", "--kinds", "decision", "--json"))
        self.assertEqual(sorted(out), ["budget", "files", "items", "more", "next", "schema", "source", "used"])
        self.assertTrue(out["items"])
        self.assertTrue(all(i["kind"] in ("question", "override", "approval", "note") for i in out["items"]))
        self.assertEqual(sorted(out["source"]), ["fallback", "fts5", "index", "legacy", "packages"])
        self.assertEqual(sorted(out["items"][0]), ["kind", "line", "rid", "src", "task", "ts"])
        self.assertEqual(self.p.run("recall").returncode, 2)

    def test_codex_reads_the_same(self):
        self.p.rich_task()
        self.assertEqual(self.recall("--files", "src/widget.py", runtime="codex"),
                         self.recall("--files", "src/widget.py"))


class TestStanding(Repo):
    """Review M2, M3: recall shows a risk's latest state and a task's standing review."""

    def test_a_risk_closed_in_its_own_task_is_not_open(self):
        self.p.ok("memory", "enable", "--author", "dev", human=True)
        self.p.start("found and fixed", files="src/widget.py")
        out = self.p.ok("memory", "risk", "add", "--title", "Stale key", "--where", "src/widget.py:1",
                        "--label", "RISK", "--what", "stale").stdout
        rkey = out.split()[1]
        self.p.ok("memory", "risk", "close", rkey, "--status", "fixed", "--why", "fixed here")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("close")
        recall = self.recall("--files", "src/widget.py")
        self.assertNotIn("[risk open", recall)
        self.assertNotIn(rkey, recall)
        self.assertIn("[risk fixed", self.recall("--files", "src/widget.py", "--all-risks"))
        self.assertEqual(self.p.ok("memory", "risks").stdout.splitlines()[0], "# Risks — open · 0")

    def test_findings_of_an_earlier_pass_are_not_residual(self):
        task = self.p.start("re-reviewed", "--mode", "full", "--by", "tester")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "blockers_open", "--tier", "STRONG", "--report", "-",
                  stdin="FINDINGS\n- [BLOCKER] B1 `src/widget.py:1` the key is wrong\nin_scope: yes\n"
                        "VERDICT blockers_open\n")
        self.p.write("src/widget.py", "x = 3\n")
        self.p.ok("verify", "--scope", "all", "--after-fix", "B1: the key")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=mh.CLEAN)
        self.p.ok("close")
        self.p.ok("approve", "--by", "vanssa", human=True)
        self.p.ok("close")
        recall = self.recall("--files", "src/widget.py")
        self.assertNotIn("B1", recall)
        self.assertIn("[task] %s" % task, recall)


class TestSearch(Repo):
    def setUp(self):
        super().setUp()
        self.first, _ = self.p.rich_task("decide the key")
        self.second, _ = self.p.light_task("another change", change="x = 9\n")

    def search(self, *args):
        return json.loads(self.p.ok("memory", "search", *args, "--json").stdout)

    def test_prefix_tokens_and_filters(self):
        hits = self.search("cache loc")
        self.assertTrue(hits["items"])
        self.assertTrue(all(i["task"] == self.first for i in hits["items"]))
        self.assertEqual({i["kind"] for i in self.search("", "--kind", "task")["items"]}, {"task"})
        self.assertEqual({i["task"] for i in self.search("", "--task", self.second)["items"]}, {self.second})
        self.assertTrue(self.search("", "--by", "vanssa")["items"])
        self.assertFalse(self.search("", "--until", "2000-01-01")["items"])
        self.assertTrue(self.search("", "--since", "2000-01-01")["items"])
        self.assertTrue(self.search("", "--file", "docs/widget.md")["items"])
        self.assertFalse(self.search("", "--file", "docs/nothing.md")["items"])
        self.assertFalse(self.search("nosuchword")["items"])

    def test_paging(self):
        everything = self.search("", "--limit", "100")
        first = self.search("", "--limit", "3")
        rest = self.search("", "--limit", "100", "--offset", "3")
        self.assertEqual([i["rid"] for i in first["items"] + rest["items"]], [i["rid"] for i in everything["items"]])
        stamps = [i["ts"] for i in everything["items"]]
        self.assertEqual(stamps, sorted(stamps, reverse=True))
        text = self.p.ok("memory", "search", "", "--limit", "2").stdout
        self.assertIn("more: --offset 2", text)


if __name__ == "__main__":
    unittest.main()
