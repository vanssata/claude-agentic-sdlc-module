"""The install suites' shared harness: one place that names the installer.

Every install suite runs the installer through `install()`, so switching the
installer under test is one line here (INSTALLER). The environment is the
caller's with overrides; a value of None removes the variable, which is how a
suite keeps an inherited CLAUDE_DIR/CODEX_DIR from leaking into an auto run.
"""
import json
import os
import shutil
import subprocess
import tempfile
import unittest

TESTS = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(TESTS)
INSTALLER = ["node", os.path.join(PLUGIN, "bin", "riskrails.js")]


def env_with(**overrides):
    env = dict(os.environ)
    for key in ("CLAUDE_DIR", "CODEX_DIR"):
        env.pop(key, None)
    for key, value in overrides.items():
        if value is None:
            env.pop(key, None)
        else:
            env[key] = value
    return env


def install(*args, env=None, stdin=None, cwd=None, merge=True):
    """Run the installer; (exit code, stdout+stderr) or, with merge=False, (exit code, stdout, stderr).

    stdin is /dev/null unless given as text: the installer must never wait on a terminal in a test."""
    proc = subprocess.run([*INSTALLER, *args], input=stdin,
                          stdin=None if stdin is not None else subprocess.DEVNULL,
                          capture_output=True, text=True, env=env if env is not None else env_with(),
                          cwd=cwd, check=False)
    if merge:
        return proc.returncode, proc.stdout + proc.stderr
    return proc.returncode, proc.stdout, proc.stderr


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


class ScratchCase(unittest.TestCase):
    """A TestCase with one scratch directory per class, as the shell suites' $TMP."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="install-suite-")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def path(self, *parts):
        return os.path.join(self.tmp, *parts)
