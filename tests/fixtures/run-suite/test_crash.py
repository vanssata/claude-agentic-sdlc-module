#!/usr/bin/env python3
"""Fixture for tests/test_run_suite.py: a test that kills its own process, so no result file is written."""
import os
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


class TestCrash(AliveMixin, unittest.TestCase):
    def test_dies(self):
        os._exit(3)


if __name__ == "__main__":
    unittest.main()
