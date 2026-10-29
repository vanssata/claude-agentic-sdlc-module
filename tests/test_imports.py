#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R15: the plugin's Python is standard library only.

Every .py under hooks/, skills/, tests/, tools/ and scripts/ is parsed and each
absolute import is checked against sys.stdlib_module_names (3.10+). A module
the plugin ships itself is not a dependency: a name that is the stem of a .py
file, or a directory holding one, anywhere in those trees is local.
"""
import ast
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TREES = ("hooks", "skills", "tests", "tools", "scripts")


def python_files():
    for tree in TREES:
        for dirpath, dirnames, filenames in os.walk(os.path.join(ROOT, tree)):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            for name in filenames:
                if name.endswith(".py"):
                    yield os.path.join(dirpath, name)


def local_modules(files):
    names = set()
    for path in files:
        names.add(os.path.basename(path)[:-3])
        names.add(os.path.basename(os.path.dirname(path)))
    return names


def imported(path):
    """(line, top-level module) of every absolute import in one file."""
    with open(path, "rb") as fh:
        tree = ast.parse(fh.read(), filename=path)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module.split(".")[0]


class TestImports(unittest.TestCase):
    def test_stdlib_only(self):
        files = sorted(python_files())
        self.assertTrue(files, "no Python files found")
        local = local_modules(files)
        foreign = []
        for path in files:
            for line, module in imported(path):
                if module not in sys.stdlib_module_names and module not in local:
                    foreign.append("%s:%d imports %s" % (os.path.relpath(path, ROOT), line, module))
        self.assertEqual(foreign, [], "non-stdlib imports:\n" + "\n".join(foreign))

    def test_the_check_bites(self):
        # A third-party name is reported; a stdlib one and a local one are not.
        self.assertNotIn("yaml", sys.stdlib_module_names)
        self.assertIn("json", sys.stdlib_module_names)
        self.assertIn("guard", local_modules([os.path.join(ROOT, "hooks", "guard", "common.py")]))


if __name__ == "__main__":
    unittest.main()
