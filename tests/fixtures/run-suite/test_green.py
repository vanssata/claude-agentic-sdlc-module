#!/usr/bin/env python3
"""Fixture for tests/test_run_suite.py: two passing tests."""
import os
import time
import unittest


class AliveMixin:
    """R4: every parallel fixture test marks itself alive in RUN_SUITE_ALIVE_DIR."""

    def setUp(self):
        self.alive_dir = os.environ.get("RUN_SUITE_ALIVE_DIR")
        self.alive = None
        if self.alive_dir:
            self.alive = os.path.join(self.alive_dir, "alive-%d" % os.getpid())
            with open(self.alive, "w", encoding="utf-8") as fh:
                fh.write("x")

    def tearDown(self):
        if self.alive and os.path.exists(self.alive):
            os.remove(self.alive)


class TestGreen(AliveMixin, unittest.TestCase):
    def test_one(self):
        time.sleep(0.3)  # long enough for a serial sibling started now to see the alive file
        self.assertEqual(1 + 1, 2)

    def test_two(self):
        time.sleep(0.3)
        self.assertTrue(True)


if __name__ == "__main__":
    unittest.main()
