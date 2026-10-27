"""The guard suites' shared harness, the Python side of tests/lib.sh.

A fixture is a JSON file: { "case": "...", "expect": "allow" | "deny",
"payload": { ...hook stdin... } }; the literal __ROOT__ inside a payload is
replaced with the scratch project path. A hook's decision is "allow" when it
prints nothing, else its hookSpecificOutput.permissionDecision, else
"malformed".
"""
import glob
import json
import os
import subprocess
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(TESTS)
FIXTURES = os.path.join(TESTS, "fixtures")


def run(hook, stdin, env=None, cwd=None, args=()):
    """Run a hook with `stdin` (str or a JSON-able value); (exit code, stdout+stderr)."""
    if not isinstance(stdin, str):
        stdin = json.dumps(stdin)
    proc = subprocess.run([hook, *args], input=stdin, capture_output=True, text=True,
                          env=env, cwd=cwd, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def decision(out):
    if not out:
        return "allow"
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] or "malformed"
    except (ValueError, KeyError, TypeError):
        return "malformed"


def fixtures(directory, root, guard=None):
    """(label, expect, payload text) per fixture file, sorted; `guard` picks Codex ones."""
    for path in sorted(glob.glob(os.path.join(directory, "*.json"))):
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if guard is not None and data.get("guard", "") != guard:
            continue
        payload = json.dumps(data["payload"]).replace("__ROOT__", root)
        yield "%s: %s" % (os.path.basename(path), data["case"]), data["expect"], payload


def codex_fixtures(guard, root):
    return fixtures(os.path.join(FIXTURES, "codex-hooks"), root, guard)


def bash(command, cwd, event="PreToolUse"):
    return {"hook_event_name": event, "tool_name": "Bash", "cwd": cwd,
            "tool_input": {"command": command}}


class HookAsserts(unittest.TestCase):
    """The lib.sh assertions, for a suite's TestCase to inherit."""

    def assertFixtures(self, hook, cases, env=None):
        for label, expect, payload in cases:
            with self.subTest(label):
                _, out = run(hook, payload, env=env)
                self.assertEqual(decision(out), expect, "%s: %s" % (label, out[:200]))

    def assertFailsOpen(self, hook, label, stdin="", env=None):
        with self.subTest(label):
            rc, out = run(hook, stdin, env=env)
            self.assertEqual((rc, out), (0, ""), label)
