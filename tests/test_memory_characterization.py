#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Characterization for compact-project-memory (C2, C3): what files mode prints
and writes does not move (A6, R15), and the three history tools keep their
answers (A11, R20). Legacy ids stay valid (R2).

The goldens under tests/fixtures/memory/goldens/ were recorded from the tree
before the change: AI_GOLDEN_ROOT names a checkout whose state.py and tools
run instead of this one's, and AI_RECORD_GOLDENS=1 writes what it printed.

  git archive <rev> skills tools hooks | tar -x -C /tmp/head
  AI_GOLDEN_ROOT=/tmp/head AI_RECORD_GOLDENS=1 python3 -I -m unittest discover -s tests \\
      -p test_memory_characterization.py

Normalised before the compare: the scratch root, task ids (the one change
files mode makes on purpose, Q3), timestamps, git hashes and durations.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_harness as mh  # noqa: E402  pylint: disable=wrong-import-position

PLUGIN = os.environ.get("AI_GOLDEN_ROOT") or mh.ROOT
RECORD = bool(os.environ.get("AI_RECORD_GOLDENS"))
GOLDENS = os.path.join(mh.FIXTURES, "goldens")
LEGACY = os.path.join(mh.FIXTURES, "legacy-reports")
STATE = os.path.join(PLUGIN, "skills", "ai-task", "state.py")


def normalise(text, root, ids=(), any_id=True):
    text = text.replace(os.path.realpath(root), "<ROOT>").replace(root, "<ROOT>")
    tmp = os.path.dirname(root)
    text = text.replace(os.path.realpath(tmp), "<TMP>").replace(tmp, "<TMP>")
    for task_id in sorted(ids, key=len, reverse=True):
        text = text.replace(task_id, "<ID>")
    if any_id:
        text = re.sub(r"T-\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+|T-\d{4}-\d{2}-\d{2}-\d{3}", "<ID>", text)
    text = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", "<TS>", text)
    text = re.sub(r"\b[0-9a-f]{40}\b", "<SHA>", text)
    text = re.sub(r"\b[0-9a-f]{9}\b", "<SHA9>", text)
    text = re.sub(r"\bin \d+s\b", "in <N>s", text)
    text = re.sub(r"\b\d+ min\b", "<N> min", text)
    return text


class Golden(unittest.TestCase):
    maxDiff = None

    def golden(self, name, text):
        path = os.path.join(GOLDENS, name)
        if RECORD:
            os.makedirs(GOLDENS, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
            return
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(text, fh.read(), name)


def run_state(p, *args, human=False):
    return subprocess.run([sys.executable, "-I", STATE, "--root", p.root] + list(args), input="",
                          capture_output=True, text=True, check=False,
                          env=mh.clean_env(human=human, extra={"HOME": p.tmp}))


class TestFilesMode(Golden):
    """A6: start, status, handoff, verify and close, their output and the
    files they leave; no memory directory after any of them."""

    def test_files_mode_is_unchanged_but_the_id(self):
        p = mh.Project()
        self.addCleanup(p.close)
        out, ids = [], []
        steps = [("start", "--goal", "tweak the widget", "--workflow", "feature", "--files", "src/widget.py",
                  "--tests", "tests/test_widget.py", *mh.ZERO),
                 ("status",), ("handoff", "--print"), ("verify", "--scope", "all"), ("close",), ("status",)]
        for i, args in enumerate(steps):
            if args[0] == "verify":
                p.write("src/widget.py", "x = 2\n")
            done = run_state(p, *args)
            ids += re.findall(r"T-\d{4}-\d{2}-\d{2}-[0-9a-z-]+", done.stdout)
            listing = [f for f in p.tree_listing() if not f.startswith(".ai/state/logs/") or f.endswith(".log")]
            out.append("$ state.py %s\nexit %d\n%s%s-- files\n%s\n" % (
                args[0], done.returncode, done.stdout, ("stderr: " + done.stderr) if done.stderr else "",
                "\n".join(listing)))
            for gone in (".ai/memory", ".ai/local/memory"):
                self.assertFalse(p.exists(gone), "%s after %s" % (gone, args[0]))
            del i
        self.golden("files-mode.txt", normalise("\n".join(out), p.root, set(ids)))


class TestTools(Golden):
    """A11: journal-summary, status.py and usage-report --task over copies of
    this repository's report directories."""

    def setUp(self):
        self.p = mh.Project()
        self.addCleanup(self.p.close)
        reports = self.p.path(".ai/reports")
        os.makedirs(reports, exist_ok=True)
        for name in sorted(os.listdir(LEGACY)):
            shutil.copytree(os.path.join(LEGACY, name), os.path.join(reports, name))

    def tool(self, *argv, env=None):
        done = subprocess.run([sys.executable, "-I", *argv], capture_output=True, text=True, check=False,
                              cwd=self.p.root, env=mh.clean_env(dict({"HOME": self.p.tmp}, **(env or {}))))
        return "exit %d\n%s%s" % (done.returncode, done.stdout, done.stderr)

    def test_journal_summary(self):
        text = self.tool(os.path.join(PLUGIN, "tools", "journal-summary.py"), self.p.root, "--timeline",
                         "T-2026-10-15-001", "T-2026-10-28-009")
        self.golden("journal-summary.txt", normalise(text, self.p.root, any_id=False))

    def test_usage_report_task(self):
        out = []
        for task in ("T-2026-10-28-009", "T-2026-10-27-007", "T-2026-10-15-001", "T-2026-09-21-001"):
            out.append(self.tool(os.path.join(PLUGIN, "skills", "usage-report", "usage-report.py"), "--task", task,
                                 "--project", self.p.root))
        self.golden("usage-report-task.txt", normalise("\n".join(out), self.p.root, any_id=False))

    def test_status_py(self):
        status = os.path.join(PLUGIN, "skills", "rr-status", "status.py")
        out = [self.tool(status, "--root", self.p.root)]
        run_state(self.p, "start", "--goal", "tweak the widget", "--workflow", "feature", "--files",
                  "src/widget.py", "--tests", "tests/test_widget.py", *mh.ZERO)
        out.append(self.tool(status, "--root", self.p.root))
        self.golden("status-py.txt", normalise("\n".join(out), self.p.root))


class TestLegacyIds(unittest.TestCase):
    """R2: every id valid_task_id accepts stays valid where a task id is read."""

    def test_legacy_ids_are_read(self):
        p = mh.Project()
        self.addCleanup(p.close)
        for name in os.listdir(LEGACY):
            shutil.copytree(os.path.join(LEGACY, name), p.path(".ai/reports/" + name))
        done = p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py",
                     "--task-id", "T-2026-09-01-001", *mh.ZERO)
        self.assertEqual(done.returncode, 0, done.stderr)
        p.ok("close", "--abandon")
        recall = p.ok("recall", "--files", "hooks/**", "--budget", "8000").stdout
        self.assertIn("T-2026-10-15-001", recall)
        self.assertIn("T-2026-10-15-001", p.ok("memory", "show", "T-2026-10-15-001").stdout)
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        done = subprocess.run([sys.executable, "-I", os.path.join(mh.ROOT, "skills", "usage-report",
                                                                  "usage-report.py"),
                               "--task", "T-2026-09-21-001", "--project", p.root], capture_output=True, text=True,
                              check=False, env=mh.clean_env({"HOME": tmp}))
        self.assertIn("task T-2026-09-21-001", done.stdout)


if __name__ == "__main__":
    unittest.main()
