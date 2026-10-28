#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The History interface (spec §D7, R11, A2, M10): FileHistory over legacy
report directories answers tasks, entries, raw_journal, task_window and
risks; SqliteHistory with and without FTS5 gives byte-identical recall and
search on 200 seeded file sets; a busy index falls back to files and says
so; a deleted index loses nothing.
"""
import importlib.util
import os
import random
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_store  # noqa: E402  pylint: disable=wrong-import-position
import memory_sync as ms  # noqa: E402  pylint: disable=wrong-import-position

SPEC = importlib.util.spec_from_file_location("benchmark_memory", os.path.join(mh.ROOT, "tools",
                                                                               "benchmark-memory.py"))
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)
LEGACY = os.path.join(mh.FIXTURES, "legacy-reports")


def body(text):
    """Recall without its header's index field: the one byte that names the backend."""
    lines = text.split("\n")
    lines[0] = " · ".join(part for part in lines[0].split(" · ") if not part.startswith("index "))
    return "\n".join(lines)


class TestFileHistoryOverLegacy(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="ai-memory-store-")
        self.addCleanup(shutil.rmtree, self.root, True)
        for task in os.listdir(LEGACY):
            shutil.copytree(os.path.join(LEGACY, task), os.path.join(self.root, ".ai", "reports", task))
        self.history = memory_store.open_history(self.root)

    def test_the_interface(self):
        tasks = self.history.tasks()
        self.assertEqual(len({s["task"] for s in tasks}), 7)
        self.assertEqual(len(tasks), 8)                                    # T-2026-10-15-001 has two instances
        entries = self.history.entries("T-2026-10-28-009")
        self.assertEqual(entries[-1]["kind"], "task")
        self.assertEqual(self.history.entries("T-2026-10-15-001#1")[-1]["result"], "restarted")
        raw = self.history.raw_journal("T-2026-10-28-009")
        self.assertTrue(raw.startswith(b'{"ts": "2026-10-28T17:06:11.616Z"'))
        self.assertEqual(self.history.task_window("T-2026-10-28-009"),
                         ("2026-10-28T17:06:11.616Z", "2026-10-28T18:17:20.461Z"))
        self.assertIsNone(self.history.task_window("T-1999-01-01-001"))
        self.assertEqual(self.history.risks(), [])
        self.assertEqual(self.history.source()["legacy"], 7)

    def test_the_index_answers_the_same(self):
        index = memory_store.SqliteHistory(self.root)
        for files in (["hooks/**"], ["skills/ai-task/state.py"], ["tests/**", "bin/riskrails.js"]):
            self.assertEqual(body(index.recall(files, 1500)[0]), body(self.history.recall(files, 1500)[0]))
        self.assertEqual(index.search("review"), self.history.search("review"))


class TestDifferential(unittest.TestCase):
    """R11, A2: FileHistory, SqliteHistory, SqliteHistory without FTS5."""

    @classmethod
    def setUpClass(cls):
        cls.root = tempfile.mkdtemp(prefix="ai-memory-diff-")
        os.makedirs(os.path.join(cls.root, ".ai"))
        cls.tasks = bench.generate(600, seed=21, journal_kb=1)
        bench.write_packages(cls.root, cls.tasks)
        legacy = bench.generate(12, seed=22, journal_kb=1)
        bench.write_legacy(cls.root, legacy)
        with open(os.path.join(cls.root, ".ai", "project-risks.tmp"), "w", encoding="utf-8"):
            pass
        os.makedirs(os.path.join(cls.root, ".ai", "project"))
        with open(os.path.join(cls.root, ".ai", "project", "known-risks.md"), "w", encoding="utf-8") as fh:
            fh.write("# Known risks\n\n## A risk on mod01\n\n- **Where**: `src/mod01/x.py`\n- **Status**: open\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.root, ignore_errors=True)

    def backends(self):
        plain = memory_store.FileHistory(self.root)
        fts = memory_store.SqliteHistory(self.root)
        os.environ["AI_MEMORY_NO_FTS"] = "1"
        try:
            nofts = memory_store.SqliteHistory(self.root)
            nofts.path = nofts.path + ".nofts"
            nofts.data()
        finally:
            del os.environ["AI_MEMORY_NO_FTS"]
        return plain, fts, nofts

    def test_200_seeded_file_sets(self):
        plain, fts, nofts = self.backends()
        self.assertTrue(memory_store.fts5_available())
        self.assertFalse(nofts.fts)
        pool = bench.file_pool(random.Random(21))
        rng = random.Random(5)
        for n in range(200):
            files = rng.sample(pool, rng.randint(1, 3))
            if n % 7 == 0:
                files.append("src/mod%02d/**" % rng.randint(0, 39))
            budget = rng.choice((300, 1500, 5000))
            want = body(plain.recall(files, budget)[0])
            self.assertEqual(body(fts.recall(files, budget)[0]), want, files)
            self.assertEqual(body(nofts.recall(files, budget)[0]), want, files)
        for query in ("cache", "cache loc", "guard path", "risk", "bench", "Ключ", "", "nothing-here"):
            want = plain.search(query, limit=50)
            self.assertEqual(fts.search(query, limit=50), want, query)
            self.assertEqual(nofts.search(query, limit=50), want, query)
        self.assertEqual(fts.search("", {"kind": "risk"}, limit=500), plain.search("", {"kind": "risk"}, limit=500))

    def test_a_deleted_index_is_rebuilt_to_the_same_answers(self):
        index = memory_store.SqliteHistory(self.root)
        first = index.recall(["src/mod01/**"], 1500)[0]
        os.remove(index.path)
        self.assertEqual(memory_store.SqliteHistory(self.root).recall(["src/mod01/**"], 1500)[0], first)

    def test_a_layout_mismatch_rebuilds(self):
        index = memory_store.SqliteHistory(self.root)
        index.data()
        con = sqlite3.connect(index.path)
        con.execute("PRAGMA user_version=99")
        con.commit()
        con.close()
        again = memory_store.SqliteHistory(self.root)
        self.assertEqual(len(again.all_entries()), len(index.all_entries()))


class TestFallback(unittest.TestCase):
    def test_a_busy_writer_falls_back_to_files_and_says_so(self):
        p = mh.Project()
        self.addCleanup(p.close)
        p.ok("memory", "enable", "--author", "dev", "--index", "sqlite", human=True)
        task, _ = p.light_task("indexed")
        header = p.ok("recall", "--files", "src/widget.py").stdout.splitlines()[0]
        self.assertTrue(header.endswith("· index sqlite"), header)
        p.light_task("second", change="x = 4\n")
        p.write(".ai/project/known-risks.md", "# Known risks\n")             # a new source: the index is behind
        con = sqlite3.connect(p.path(".ai/local/memory/index.sqlite3"), timeout=0, isolation_level=None)
        con.execute("BEGIN EXCLUSIVE")
        try:
            out = p.ok("recall", "--files", "src/widget.py", env={"AI_MEMORY_BUSY_MS": "50"}).stdout
        finally:
            con.execute("ROLLBACK")
            con.close()
        self.assertIn("index sqlite (fallback: files)", out.splitlines()[0])
        self.assertIn(task, out)
        status = p.ok("memory", "status").stdout
        self.assertIn("index: sqlite", status)
        self.assertIn("fts5: yes", status)
        rebuilt = p.ok("memory", "rebuild").stdout
        self.assertIn("index: rebuilt", rebuilt)
        self.assertEqual(ms.load_config(p.root).index, "sqlite")

    def test_fts5_unavailable_is_reported(self):
        p = mh.Project()
        self.addCleanup(p.close)
        p.ok("memory", "enable", "--index", "sqlite", human=True)
        status = p.ok("memory", "status", env={"AI_MEMORY_NO_FTS": "1"}).stdout
        self.assertIn("FTS5 unavailable in this SQLite", status)
        self.assertIn("results identical, slower", status)


if __name__ == "__main__":
    unittest.main()
