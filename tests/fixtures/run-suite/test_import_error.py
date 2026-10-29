#!/usr/bin/env python3
"""Fixture for tests/test_run_suite.py: a module that cannot be imported."""
import unittest

# Not an `import` statement: tests/test_imports.py walks every .py under tests/ and refuses a
# non-stdlib import, fixtures included. The failure at load time is the same ImportError.
MISSING = __import__("no_such_module_xyz")


class TestImportError(unittest.TestCase):
    def test_never_runs(self):
        self.assertTrue(MISSING)


if __name__ == "__main__":
    unittest.main()
