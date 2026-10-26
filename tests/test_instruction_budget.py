#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
What a session pays for in instruction text before it does any work.

R5: a light task reads `rr-build`, `weight.json` and the Verification block of
`testing.md` — together at most 400 lines. R28: the SessionStart cost — both
managed blocks, a 30-line handoff and `using-superpowers` — stays under 10 KB.
R32: the stub sends runners and verbatim extraction to FAST and readers that
judge to BALANCED, inside the 2560 B global budget.

`step_test_command` hands every test path to bash; the line above makes bash
re-run this file under python3.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RENDER = os.path.join(ROOT, "skills", "project-update", "render_instructions.py")
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
TEMPLATE_AI = os.path.join(ROOT, "skills", "ai-init", "templates", ".ai")
SUPERPOWERS_BYTES = 3686          # using-superpowers, as SQ12 measured it (3.6 KB)
GLOBAL_BUDGET = 2560
SESSION_START_BUDGET = 10240


def lines_of(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read().rstrip("\n").split("\n")


def render(scope, runtime):
    return subprocess.run([sys.executable, "-I", RENDER, "render", "--scope", scope, "--runtime", runtime,
                           "--kind", "block", "--var", "PLAN_LABEL=Max", "--var", "READ_LINES=4000"],
                          check=True, capture_output=True, text=True).stdout


def handoff_of_a_started_task():
    """The handoff `state.py start` writes in a scaffolded scratch project."""
    tmp = tempfile.mkdtemp()
    try:
        shutil.copytree(TEMPLATE_AI, os.path.join(tmp, ".ai"))
        with open(os.path.join(tmp, "a.txt"), "w", encoding="utf-8") as fh:
            fh.write("a\n")
        git = ["git", "-C", tmp, "-c", "user.name=t", "-c", "user.email=t@t"]
        subprocess.run(git + ["init", "-q"], check=True)
        subprocess.run(git + ["add", "-A"], check=True)
        subprocess.run(git + ["commit", "-qm", "base"], check=True)
        subprocess.run([sys.executable, "-I", STATE, "--root", tmp, "start", "--goal",
                        "a goal of ordinary length for a task in flight", "--workflow", "feature",
                        "--files", "a.txt"], check=True, capture_output=True, text=True)
        with open(os.path.join(tmp, ".ai", "state", "handoff.md"), encoding="utf-8") as fh:
            return fh.read()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class TestLightTaskReads(unittest.TestCase):
    def test_r5_build_weight_verification(self):
        build = lines_of(os.path.join(ROOT, "skills", "rr-build", "SKILL.md"))
        weight = lines_of(os.path.join(TEMPLATE_AI, "policies", "weight.json"))
        testing = lines_of(os.path.join(TEMPLATE_AI, "policies", "testing.md"))
        start = testing.index("## Verification")
        end = next((i for i in range(start + 1, len(testing)) if testing[i].startswith("## ")), len(testing))
        total = len(build) + len(weight) + (end - start)
        self.assertLessEqual(total, 400, "rr-build %d + weight.json %d + Verification %d lines"
                             % (len(build), len(weight), end - start))


class TestSessionStart(unittest.TestCase):
    def test_session_start_cost(self):
        handoff = handoff_of_a_started_task()
        self.assertLessEqual(len(handoff.rstrip("\n").split("\n")), 30, "the handoff is at most 30 lines")
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                total = (len(render("global", runtime).encode()) + len(render("project", runtime).encode())
                         + len(handoff.encode()) + SUPERPOWERS_BYTES)
                self.assertLessEqual(total, SESSION_START_BUDGET, "%s SessionStart %d B" % (runtime, total))


class TestReaderTiers(unittest.TestCase):
    def test_r32_readers_by_judgement(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                block = render("global", runtime)
                fast = [line for line in block.split("\n") if "FAST" in line]
                self.assertTrue(any("runners" in line and "verbatim" in line for line in fast),
                                "FAST for runners and verbatim extraction")
                self.assertTrue(any("BALANCED" in line and "judge" in line for line in block.split("\n")),
                                "BALANCED for readers that judge")
                self.assertLessEqual(len(block.encode()), GLOBAL_BUDGET)


if __name__ == "__main__":
    unittest.main()
