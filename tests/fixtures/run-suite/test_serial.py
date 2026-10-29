#!/usr/bin/env python3
"""Fixture for tests/test_run_suite.py: a serial class that must run alone (R4)."""
import glob
import os
import unittest


class TestTimed(unittest.TestCase):
    def test_alone(self):
        alive_dir = os.environ.get("RUN_SUITE_ALIVE_DIR")
        self.assertTrue(alive_dir, "RUN_SUITE_ALIVE_DIR is not set")
        self.assertEqual(glob.glob(os.path.join(alive_dir, "alive-*")), [])


if __name__ == "__main__":
    unittest.main()
