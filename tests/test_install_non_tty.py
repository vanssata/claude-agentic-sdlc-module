#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R13: the installer's stdout, stderr and exit code without a terminal, and with --yes, are
byte-identical to 4.2.0.

tests/fixtures/install/non-tty.golden was recorded from `git archive HEAD` of 4.2.0, before any
bin/ edit, by running RUNS through transcript() against that export. Each run gets a fresh home
(HOME, CLAUDE_DIR and CODEX_DIR point into it) and stdin is /dev/null, so nothing touches the
real home, a terminal or the network.

NORMALISE is exactly what is erased before the compare, in this order, and nothing else: the
scratch home -> <HOME>, the installer's own directory -> <PLUGIN>, the date in backups/<date> ->
<DATE>, an ISO timestamp (the dry run prints the profile's written_at) -> <TIME>, the package
version -> <VERSION>.

Re-record only for a change that is meant to move this output, never to make a refactoring pass:

  UPDATE_GOLDENS=1 python3 -I tests/run_suite.py tests/test_install_non_tty.py

Without the switch a missing or different golden fails, with a unified diff.
"""
import difflib
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, env_with, install, read, write  # noqa: E402  pylint: disable=wrong-import-position

GOLDEN = os.path.join(PLUGIN, "tests", "fixtures", "install", "non-tty.golden")
UPDATE = bool(os.environ.get("UPDATE_GOLDENS"))

RUNS = [
    ("claude --yes", ["--target", "claude", "--plan", "pro", "--yes"]),
    ("claude --yes --dry-run", ["--target", "claude", "--plan", "pro", "--yes", "--dry-run"]),
    ("claude, no --yes, no terminal", ["--target", "claude", "--plan", "pro"]),
    ("claude, no plan, no terminal", ["--target", "claude"]),
    ("codex --yes", ["--target", "codex", "--yes"]),
]


def version():
    return re.search(r'"version":\s*"([^"]+)"', read(os.path.join(PLUGIN, "package.json"))).group(1)


def normalise(text, home, ver):
    text = text.replace(home, "<HOME>").replace(PLUGIN, "<PLUGIN>")
    text = re.sub(r"backups/\d{4}-\d{2}-\d{2}", "backups/<DATE>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", "<TIME>", text)
    return text.replace(ver, "<VERSION>")


def transcript(base):
    """The runs' stdout, stderr and exit code as one text; each run in its own home under base."""
    ver, parts = version(), []
    for n, (label, args) in enumerate(RUNS):
        home = os.path.join(base, "home%d" % n)
        os.makedirs(home)
        env = env_with(HOME=home, CLAUDE_DIR=os.path.join(home, ".claude"), CODEX_DIR=os.path.join(home, ".codex"))
        code, out, err = install(*args, env=env, merge=False)
        parts.append("##### %s\n##### exit %d\n##### stdout\n%s##### stderr\n%s" % (
            label, code, normalise(out, home, ver), normalise(err, home, ver)))
    return "".join(parts)


class NonTtyGolden(ScratchCase):

    def test_output_is_the_recorded_4_2_0_output(self):
        base = tempfile.mkdtemp(prefix="non-tty-", dir=self.tmp)
        text = transcript(base)
        shutil.rmtree(base, ignore_errors=True)
        if UPDATE:
            write(GOLDEN, text)
            return
        self.assertTrue(os.path.exists(GOLDEN), "no golden %s: record it with UPDATE_GOLDENS=1" % GOLDEN)
        golden = read(GOLDEN)
        if text != golden:
            diff = list(difflib.unified_diff(golden.splitlines(), text.splitlines(), "golden", "now", lineterm="", n=2))
            self.fail("non-TTY installer output differs from its golden (%d diff lines):\n%s" % (len(diff), "\n".join(diff[:120])))


if __name__ == "__main__":
    unittest.main()
