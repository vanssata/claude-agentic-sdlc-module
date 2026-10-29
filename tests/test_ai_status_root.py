#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
/rr-status resolves the project the same way the guards do, and stays short.

skills/rr-status/status.py prints `root:` first. It exists so a reader can see
WHICH .ai/ governs the directory they are in — a .ai/ in an ancestor, or in
$HOME, silently arms the path and scope guards for every repository below it,
and that is not visible from anywhere else. The line is only worth anything
while it agrees with find_ai_root, so this suite compares it, case by case,
with both implementations: hooks/lib/ai-hook-common.sh, and
hooks/guard/common.py, which the guards run since redesign 3.1. Then the
length: at most twenty lines (redesign R31), with a task in flight and without
one.
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from string import Template

PLUGIN = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(PLUGIN, "skills", "rr-status", "status.py")
STATE = os.path.join(PLUGIN, "skills", "ai-task", "state.py")
ALIAS = os.path.join(PLUGIN, "skills", "ai-status", "SKILL.md")

_spec = importlib.util.spec_from_file_location("guard_common", os.path.join(PLUGIN, "hooks", "guard", "common.py"))
guard_common = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard_common)

TWIN_OF = "test-ai-status-root.sh"

# status.py's root and the shell guard's find_ai_root, one per line, from $PWD.
RESOLVED = """
set -uo pipefail
. "$1/hooks/lib/ai-hook-common.sh"
python3 -I "$2" | sed -n "s/^root: //p" | grep -v "^none" || printf "\\n"
AI_CWD=$PWD
find_ai_root "$PWD" || printf "\\n"
"""

LINE_KEY = re.compile(r"^([a-z ]+: |       \(b\) )")


def git(*args):
    subprocess.run(["git"] + list(args), capture_output=True, check=True)


def status(*args, cwd=None):
    done = subprocess.run([sys.executable, "-I", STATUS] + list(args), capture_output=True, text=True,
                          cwd=cwd, check=False)
    return done.returncode, done.stdout


class TestStatusRoot(unittest.TestCase):
    """The inner directory is a real repository, so a walk that stopped at the git
    root — the tempting shortcut, and the wrong one — is caught here rather than
    in someone's terminal."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        for d in ("outer/repo/src/deep", "bare/src", "outer/.ai", "outer/repo/.ai"):
            os.makedirs(os.path.join(self.tmp, d))
        git("-C", os.path.join(self.tmp, "outer", "repo"), "init", "-q", "-b", "main")
        git("-C", os.path.join(self.tmp, "bare"), "init", "-q", "-b", "main")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def rel(self, path):
        return path[len(self.tmp) + 1:] if path.startswith(self.tmp + "/") else path

    def resolved(self, rel):
        """(status.py, the shell guard, the Python guard), each relative to tmp or EMPTY."""
        d = os.path.join(self.tmp, rel)
        env = dict(os.environ, PWD=d)
        out = subprocess.run(["bash", "-c", RESOLVED, "_", PLUGIN, STATUS], capture_output=True, text=True,
                             cwd=d, env=env, check=False).stdout.split("\n")
        got = [out[0] if out else "", out[1] if len(out) > 1 else "", guard_common.find_ai_root(d, d) or ""]
        return tuple(self.rel(g) or "EMPTY" for g in got)

    def check(self, label, rel, expect):
        with self.subTest(Template("$label ($status)").substitute(label=label, status=expect)):
            got = self.resolved(rel)
            self.assertEqual(len(set(got)), 1, "%s: status.py and the guards disagree: %s" % (label, got))
            self.assertEqual(got[0], expect, "%s: all agree on the wrong root" % label)

    def test_status_and_find_ai_root_resolve_the_same_root(self):
        self.check("its own .ai/ at the repository root", "outer/repo", "outer/repo")
        self.check("its own .ai/, from a subdirectory", "outer/repo/src/deep", "outer/repo")
        shutil.rmtree(os.path.join(self.tmp, "outer", "repo", ".ai"))
        self.check("a .ai/ inherited from an ancestor", "outer/repo", "outer")
        self.check("inherited, from a subdirectory", "outer/repo/src/deep", "outer")
        self.check("no .ai/ anywhere above", "bare/src", "EMPTY")

    def test_root_flag(self):
        shutil.rmtree(os.path.join(self.tmp, "outer", "repo", ".ai"))
        _, out = status("--root", os.path.join(self.tmp, "outer", "repo", "src", "deep"))
        self.assertIn("root: %s\n" % os.path.join(self.tmp, "outer"), out,
                      "--root starts the same walk from another directory")

    def test_no_root(self):
        rc, out = status(cwd=os.path.join(self.tmp, "bare", "src"))
        self.assertEqual(rc, 1, out)
        self.assertRegex(out, r"(?m)^root: none", "no .ai/ above: root: none, exit 1")

    def test_no_task_in_flight(self):
        rc, out = status("--root", os.path.join(self.tmp, "outer"))
        self.assertEqual(rc, 0, out)
        self.assertLessEqual(len(out.splitlines()), 3, out)
        self.assertRegex(out, r"(?m)^task: none — no task in flight")
        self.assertRegex(out, r"(?m)^schema: project 0 · plugin [0-9]",
                         "root, no task in flight and schema: three lines")


class TestPopulatedTask(unittest.TestCase):
    """A populated task stays within twenty lines."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        p = cls.p = os.path.join(cls.tmp, "proj")
        os.makedirs(os.path.join(p, "src"))
        os.makedirs(os.path.join(p, ".ai", "policies"))
        git("-C", p, "init", "-q", "-b", "main")
        git("-C", p, "config", "user.email", "t@example.com")
        git("-C", p, "config", "user.name", "t")
        with open(os.path.join(p, "src", "a.py"), "w", encoding="utf-8") as fh:
            fh.write("base\n")
        git("-C", p, "add", "-A")
        git("-C", p, "commit", "-qm", "base")
        with open(os.path.join(p, ".ai", "VERSION"), "w", encoding="utf-8") as fh:
            fh.write("7\n")
        files = ",".join("src/f%d.py" % i for i in range(1, 31))
        cls.state("start", "--goal", "a goal long enough to wrap\nand written over\nthree lines",
                  "--workflow", "feature", "--files", files, "--declare", "behaviour=0:fixture",
                  "--declare", "domain=0:fixture", "--declare", "novelty=0:fixture")
        cls.state("ask", "one question", "--option", "A: yes", "--option", "B: no")
        cls.state("ask", "two question", "--option", "A: yes", "--option", "B: no")
        cls.rc, cls.out = status("--root", p)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @classmethod
    def state(cls, *args):
        env = {k: v for k, v in os.environ.items() if k != "AI_UNATTENDED"}
        subprocess.run([sys.executable, STATE, "--root", cls.p] + list(args), capture_output=True,
                       env=env, check=False)

    def test_at_most_twenty_lines(self):
        n = len(self.out.splitlines())
        with self.subTest(Template("a populated task: $n lines, at most 20").substitute(n=n)):
            self.assertEqual(self.rc, 0, self.out)
            self.assertLessEqual(n, 20, self.out)

    def test_it_shows_every_key(self):
        for prefix in ("root: " + self.p, "task: T-", "mode: light · W ", "stage: build",
                       "files: 30 in scope — src/f1.py", "verify: suite not_run · runs 0/2", "review: ",
                       "questions: 2 pending", "task: T-2026", "schema: project 7 · plugin", "last event: "):
            with self.subTest(Template("it shows: $prefix").substitute(prefix=prefix)):
                self.assertIn(prefix, self.out)

    def test_every_line_starts_with_its_key(self):
        """facts: prints (a) and (b) on two lines, the second indented under the first."""
        self.assertEqual([line for line in self.out.splitlines() if not LINE_KEY.match(line)], [],
                         "a multi-line goal stays on its own line (every line starts with its key)")

    def test_a_long_file_list_is_shortened(self):
        self.assertIn("(+26 more)", self.out, "a long file list is shortened, not wrapped")


class TestAlias(unittest.TestCase):
    """ai-status is an alias."""

    def setUp(self):
        with open(ALIAS, encoding="utf-8") as fh:
            self.text = fh.read()

    @staticmethod
    def description(text):
        m = re.search(r"(?m)^description: (.*)$", text)
        return m.group(1) if m else ""

    def test_the_alias_is_short(self):
        self.assertLessEqual(self.text.count("\n"), 12, "ai-status/SKILL.md is at most 12 lines")
        self.assertLessEqual(len(self.description(self.text).encode()), 80, "its description is at most 80 bytes")

    def test_its_first_body_line(self):
        body = self.text.split("\n---\n", 1)[1] if self.text.startswith("---\n") else ""
        first = next((line for line in body.split("\n") if line.strip()), "")
        self.assertEqual(first, "deprecated → /rr-status", "its first body line is 'deprecated → /rr-status'")

    def test_rr_status_description(self):
        with open(os.path.join(PLUGIN, "skills", "rr-status", "SKILL.md"), encoding="utf-8") as fh:
            desc = self.description(fh.read())
        self.assertLessEqual(len(desc.encode()) + 1, 1024, "rr-status/SKILL.md's description fits 1024 bytes")

    def test_no_bare_status_skill(self):
        self.assertFalse(os.path.exists(os.path.join(PLUGIN, "skills", "status")),
                         "there is no bare skills/status any more")


if __name__ == "__main__":
    unittest.main()
