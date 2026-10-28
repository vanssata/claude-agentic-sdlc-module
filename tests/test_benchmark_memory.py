#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R27: tools/benchmark-memory.py — seeded, deterministic histories; the report
separates cold and warm, build and query, and says what it read and returned.
"""
import importlib.util
import json
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "benchmark-memory.py")
SPEC = importlib.util.spec_from_file_location("benchmark_memory", TOOL)
bench = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bench)


class TestGenerate(unittest.TestCase):
    def test_same_seed_same_history(self):
        a, b = bench.generate(50, seed=7, journal_kb=2), bench.generate(50, seed=7, journal_kb=2)
        self.assertEqual([t["entries"] for t in a], [t["entries"] for t in b])
        self.assertEqual([t["journal"] for t in a], [t["journal"] for t in b])
        self.assertNotEqual([t["entries"] for t in a], [t["entries"] for t in bench.generate(50, seed=8)])

    def test_entries_are_valid_records(self):
        for t in bench.generate(30, seed=3):
            for e in t["entries"]:
                self.assertEqual(bench.mf.validate(e), [], e)
            self.assertGreaterEqual(len(t["journal"]), 2 * 1024 - 400)

    def test_report_fields(self):
        done = subprocess.run([sys.executable, "-I", TOOL, "--tasks", "20", "--seed", "5", "--journal-kb", "1",
                               "--json"], capture_output=True, text=True, check=True)
        rows = json.loads(done.stdout)
        self.assertEqual([r["layout"] for r in rows], ["legacy", "packages"])
        for row in rows:
            for key in ("tasks", "files_read", "storage_bytes", "recall_bytes", "file_recall_ms_cold",
                        "file_recall_ms_warm", "file_search_ms_cold", "file_search_ms_warm"):
                self.assertIn(key, row)
        for key in ("index_build_ms", "index_recall_ms_cold", "index_search_ms_warm", "index_bytes"):
            self.assertIn(key, rows[1])
        again = json.loads(subprocess.run([sys.executable, "-I", TOOL, "--tasks", "20", "--seed", "5",
                                           "--journal-kb", "1", "--json"], capture_output=True, text=True,
                                          check=True).stdout)
        for a, b in zip(rows, again):
            for key in ("files_read", "storage_bytes", "recall_bytes"):
                self.assertEqual(a[key], b[key], key)


if __name__ == "__main__":
    unittest.main()
