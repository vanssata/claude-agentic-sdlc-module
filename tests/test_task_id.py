#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R1, R2: the task id is T-YYYY-MM-DD-HHMM-<slug> (spec compact-project-memory
§D2). The bug it fixes (C2): next_task_id counted the day's report
directories, so two clones started the same day got the same id, and a
deleted report directory made the next start reuse an id (state.py
next_task_id, recent_notes). Legacy ids stay valid.
"""
import contextlib
import io
import os
import re
import shutil
import sys
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position
import memory_format as mf  # noqa: E402  pylint: disable=wrong-import-position
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position

MINUTE = datetime(2026, 10, 28, 17, 39, 12, tzinfo=timezone.utc)


class TestSlug(unittest.TestCase):
    def test_shape_and_whole_words(self):
        self.assertEqual(mf.slug_of("Compact the project memory, please"), "compact-the-project")
        for goal in ("a", "Fix it!", "R36 step 7d1: the inert hook half", "x" * 40, "ÉCOLE été"):
            slug = mf.slug_of(goal)
            self.assertRegex(slug, mf.SLUG_RE, goal)
        self.assertEqual(mf.slug_of("x" * 40), "x" * 24)
        self.assertEqual(mf.slug_of("ÉCOLE été"), "ecole-ete")

    def test_cyrillic_is_transliterated(self):
        self.assertEqual(mf.slug_of("Компактна памет за проекта"), "kompaktna-pamet-za")
        self.assertEqual(mf.slug_of("Щъркел и ютия"), "shtarkel-i-yutiya")

    def test_task_when_nothing_is_left(self):
        for goal in ("", "!!! ??? …", "Ωμέγα", "—"):
            self.assertEqual(mf.slug_of(goal), "task", goal)
        self.assertEqual(mf.slug_of("ab"), "ab-task")

    def test_deterministic(self):
        self.assertEqual(mf.slug_of("Same goal twice"), mf.slug_of("Same goal twice"))


class TestNewId(unittest.TestCase):
    def test_shape(self):
        task = mf.new_task_id(MINUTE, "compact-memory")
        self.assertEqual(task, "T-2026-10-28-1739-compact-memory")
        self.assertRegex(task, mf.NEW_ID_RE)
        self.assertRegex(task, state_mod.TASK_ID_RE)
        self.assertTrue(re.search(r"(^|/)\.ai/reports/[^/]+/", ".ai/reports/%s/task.md" % task))
        with self.assertRaises(ValueError):
            mf.new_task_id(MINUTE, "No")

    def test_disambiguator_counts_inside_the_slug(self):
        self.assertEqual(mf.with_suffix("abc", 2), "abc-2")
        long = mf.with_suffix("x" * 24, 9)
        self.assertEqual(len(long), 24)
        self.assertRegex("T-2026-10-28-1739-" + long, mf.NEW_ID_RE)

    def test_legacy_ids_stay_valid(self):
        for task in ("T-2026-09-21-001", "T-2026-10-28-011", "T-OLD", "T-2026.09-a_b"):
            self.assertEqual(state_mod.valid_task_id(task), task)
        self.assertRegex("T-2026-09-21-001", mf.LEGACY_ID_RE)
        self.assertNotRegex("T-2026-09-21-001", mf.NEW_ID_RE)


class TestNextTaskId(unittest.TestCase):
    """In process, on a fixed minute: the local disambiguator."""

    def setUp(self):
        self.p = mh.Project()

    def tearDown(self):
        self.p.close()

    def call(self, goal="Same goal", slug=None):
        return state_mod.next_task_id(self.p.root, goal, slug, at=MINUTE)

    def test_report_directory_log_directory_and_seal_each_count_as_taken(self):
        first = self.call()
        self.assertEqual(first, "T-2026-10-28-1739-same-goal")
        os.makedirs(self.p.path(".ai/reports/" + first))
        self.assertEqual(self.call(), first + "-2")
        os.makedirs(self.p.path(".ai/state/logs/%s-2" % first))
        self.assertEqual(self.call(), first + "-3")
        self.p.write(".ai/memory/2026-Q4.tester.abcd.jsonl",
                     '{"kind":"task","task":"%s-3"}\n' % first)
        self.assertEqual(self.call(), first + "-4")

    def test_after_nine_it_exits_2_naming_slug(self):
        seen = set()
        for _ in range(9):
            task = self.call()
            self.assertNotIn(task, seen)
            seen.add(task)
            os.makedirs(self.p.path(".ai/reports/" + task))
        err = io.StringIO()
        with contextlib.redirect_stderr(err), self.assertRaises(SystemExit) as caught:
            self.call()
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--slug", err.getvalue())

    def test_a_thousand_starts_in_one_minute_never_share_an_id(self):
        """A4: one goal gives 9 ids and then refuses (R1 caps the
        disambiguator at 9); 1 000 slugs in the same minute give 1 000 ids."""
        ids = []
        for n in range(1000):
            task = self.call(slug="s%d-task" % n)
            os.makedirs(self.p.path(".ai/reports/" + task))
            ids.append(task)
        self.assertEqual(len(set(ids)), 1000)
        same = []
        for _ in range(12):
            try:
                with contextlib.redirect_stderr(io.StringIO()):
                    task = self.call("one goal")
            except SystemExit as exc:
                self.assertEqual(exc.code, 2)
                break
            same.append(task)
            os.makedirs(self.p.path(".ai/reports/" + task))
        self.assertEqual(len(same), 9)
        self.assertEqual(len(set(same)), 9)


class TestStart(unittest.TestCase):
    """Through state.py start: the reported defect, then the flag."""

    def setUp(self):
        self.p = mh.Project("a")
        self.q = mh.Project("b", tmp=self.p.tmp)

    def tearDown(self):
        self.p.close()

    def test_two_roots_on_one_day_get_different_ids(self):
        first = self.p.start("fix the cache key")
        second = self.q.start("add the usage report")
        self.assertNotEqual(first, second)
        self.assertRegex(first, mf.NEW_ID_RE)
        self.assertRegex(second, mf.NEW_ID_RE)

    def test_a_deleted_report_directory_is_not_reused(self):
        first, _ = self.p.light_task("tweak the widget")
        shutil.rmtree(self.p.path(".ai/reports/" + first))
        second = self.p.start("tweak the widget")
        self.assertNotEqual(first, second)

    def test_slug_flag(self):
        task = self.p.start("anything at all", "--slug", "my-slug")
        self.assertTrue(task.endswith("-my-slug"), task)
        self.p.ok("close", "--abandon")
        for bad in ("No", "UPPER-case", "a" * 25, "trailing-"):
            done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py",
                              "--slug", bad, *mh.ZERO)
            self.assertEqual(done.returncode, 2, bad)
            self.assertIn("--slug", done.stderr)

    def test_task_id_flag_keeps_a_legacy_id(self):
        done = self.p.ok("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py",
                         "--task-id", "T-2026-09-01-001", *mh.ZERO)
        self.assertIn("T-2026-09-01-001 started", done.stdout)


if __name__ == "__main__":
    unittest.main()
