#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R13: a shell suite and its Python twin name the same cases while both exist.

A Python suite that translates a shell one says so with a module-level
`TWIN_OF = "test-<x>.sh"`; that pair is checked while the shell suite exists.
A shared stem alone pairs nothing: test_usage_report.py and five others are
suites of their own beside the shell ones, not translations. A shell case is
the text of the first argument of a `pass` call, as written in the source. A
Python case is any string constant in the twin (a docstring, a subTest label,
a message) or a test method's name. Every shell case must appear among them;
the shell suite is deleted once its twin is green on the same tree, which ends
the pairing.
"""
import ast
import os
import re
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))

# `pass "…"` or `pass '…'` at the start of a statement; the text as written.
PASS_RE = re.compile(r'''(?:^|[;&|{(]|then|else|do)\s*pass\s+("(?:[^"\\]|\\.)*"|'[^']*')''', re.M)


def shell_cases(text):
    return {m.group(1)[1:-1] for m in PASS_RE.finditer(text)}


def python_cases(source):
    names = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            names.add(node.value)
            names.add(node.value.strip().split("\n", 1)[0])
        elif isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
            names.add(node.name)
    return names


def twin_of(path):
    """The shell suite a Python suite declares it translates, or None."""
    with open(path, encoding="utf-8") as fh:
        tree = ast.parse(fh.read())
    for node in tree.body:
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name) and node.targets[0].id == "TWIN_OF"
                and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)):
            return node.value.value
    return None


def pairs(directory):
    for name in sorted(os.listdir(directory)):
        if name.startswith("test_") and name.endswith(".py"):
            sh = twin_of(os.path.join(directory, name))
            if sh and os.path.isfile(os.path.join(directory, sh)):
                yield sh, name


def missing(directory, sh, py):
    with open(os.path.join(directory, sh), encoding="utf-8", errors="surrogateescape") as fh:
        wanted = shell_cases(fh.read())
    with open(os.path.join(directory, py), encoding="utf-8") as fh:
        have = python_cases(fh.read())
    return sorted(wanted - have)


class TestSuiteParity(unittest.TestCase):
    def test_every_pair_names_the_same_cases(self):
        for sh, py in pairs(TESTS):
            with self.subTest(pair=sh):
                self.assertEqual(missing(TESTS, sh, py), [], "%s cases missing from %s" % (sh, py))

    def test_the_check_bites(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "test-demo-suite.sh"), "w", encoding="utf-8") as fh:
                fh.write('pass "first case"\n[ x ] && pass \'second case\' || fail "x"\n')
            with open(os.path.join(tmp, "test_demo_suite.py"), "w", encoding="utf-8") as fh:
                fh.write('TWIN_OF = "test-demo-suite.sh"\n\ndef test_a():\n    """first case"""\n')
            with open(os.path.join(tmp, "test_other.py"), "w", encoding="utf-8") as fh:
                fh.write('def test_b():\n    """unrelated"""\n')
            with open(os.path.join(tmp, "test-other.sh"), "w", encoding="utf-8") as fh:
                fh.write('pass "not translated"\n')
            self.assertEqual(list(pairs(tmp)), [("test-demo-suite.sh", "test_demo_suite.py")])
            self.assertEqual(missing(tmp, "test-demo-suite.sh", "test_demo_suite.py"), ["second case"])


if __name__ == "__main__":
    unittest.main()
