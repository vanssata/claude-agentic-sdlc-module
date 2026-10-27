#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
state.py's schema-7 surface (redesign 2.2a): start, verify, review, close,
step-done, status, approve --confirm, task.md, and the re-score.

Every project here is a scratch git repository in a temp directory. The suite's
red/green switch is a flag file outside the repository, so flipping it never
changes the tree the two facts are measured on.
"""
import contextlib
import io
import json
import shutil
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE = os.path.join(ROOT, "skills", "ai-task", "state.py")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position
import sensors  # noqa: E402  pylint: disable=wrong-import-position
import weight  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-ai-task-state.sh"

ZERO = ["--declare", "behaviour=0:synthetic", "--declare", "domain=0:synthetic",
        "--declare", "novelty=0:synthetic"]
HEADINGS = ["## Weight", "## Plan", "## Questions", "## Verify", "## Review", "## Changes", "## Verdict"]
CLEAN = "FINDINGS\nnone\n"
FINDINGS = "FINDINGS\n[HIGH] H1 the cache key ignores the locale\nin_scope: yes\n[LOW] L1 naming\nVERDICT pass_with_findings\n"


class Project:
    """A scratch project with .ai/, a testing.md whose commands read flag files,
    one code file and its test, committed."""

    def __init__(self, files=None, name="p"):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.root = os.path.join(self.tmp.name, name)
        self.flags = os.path.join(self.tmp.name, "flags")
        os.makedirs(self.flags)
        os.makedirs(os.path.join(self.root, ".ai", "policies"))
        red, e2e = os.path.join(self.flags, "red"), os.path.join(self.flags, "e2ered")
        # flags/touch makes the suite edit a tracked file while it runs.
        touch = "test -e %s && echo touched >> src/moved.txt; " % os.path.join(self.flags, "touch")
        self.write(".ai/policies/testing.md",
                   "verify_command: sh -c '%stest ! -e %s' {files}\nstep_test_command: sh -c 'test ! -e %s' {files}\n"
                   "e2e_command: test ! -e %s\n" % (touch, red, os.path.join(self.flags, "stepred"), e2e))
        base = {"src/widget.py": "x = 1\n", "tests/test_widget.py": "assert True\n"}
        base.update(files or {})
        for rel, text in base.items():
            self.write(rel, text)
        subprocess.run(["git", "init", "-q", self.root], check=True)
        subprocess.run(["git", "-C", self.root, "add", "-A"], check=True)
        subprocess.run(["git", "-C", self.root, "-c", "user.email=t@t", "-c", "user.name=t",
                        "commit", "-qm", "init"], check=True)

    def write(self, rel, text):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def flag(self, name, on=True):
        path = os.path.join(self.flags, name)
        if on:
            open(path, "w", encoding="utf-8").close()  # pylint: disable=consider-using-with
        elif os.path.exists(path):
            os.remove(path)

    def run(self, *args, runtime="claude", human=False, stdin=None, env=None, state_py=STATE):
        """runtime=None leaves AI_RUNTIME unset, so detection decides; env adds
        variables after the agent markers are removed."""
        base = {k: v for k, v in os.environ.items()
                if k not in state_mod.AGENT_MARKERS and k not in ("AI_UNATTENDED", "AI_RUNTIME",
                                                                   "AI_HANDOFF_NO_PROMPT")}
        if runtime:
            base["AI_RUNTIME"] = runtime
        if human:
            base["AI_UNATTENDED"] = "1"
        base.update(env or {})
        env = base
        return subprocess.run([sys.executable, "-I", state_py, "--root", self.root] + list(args),
                              input=stdin if stdin is not None else "", capture_output=True, text=True,
                              env=env, check=False)

    def ok(self, *args, **kwargs):
        done = self.run(*args, **kwargs)
        assert done.returncode == 0, (args, done.returncode, done.stdout, done.stderr)
        return done

    def start(self, *extra, files="src/widget.py"):
        return self.ok("start", "--goal", "tweak the widget", "--workflow", "feature", "--files", files,
                       "--tests", "tests/test_widget.py", *ZERO, *extra)

    def state(self):
        with open(os.path.join(self.root, ".ai", "state", "current.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def archived(self, task_id):
        with open(os.path.join(self.root, ".ai", "state", "logs", task_id, "state.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def events(self, task_id):
        with open(os.path.join(self.root, ".ai", "reports", task_id, "events.jsonl"), encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def task_md(self, task_id):
        with open(os.path.join(self.root, ".ai", "reports", task_id, "task.md"), encoding="utf-8") as fh:
            return fh.read()

    def in_flight(self):
        return os.path.exists(os.path.join(self.root, ".ai", "state", "current.json"))

    def close(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.close()

    def task_id(self):
        return self.p.state()["task_id"]


class TestStart(Base):
    def test_start_writes_schema_7_and_arms_the_scope_guard(self):
        out = self.p.start().stdout
        s = self.p.state()
        self.assertEqual((s["schema"], s["mode"], s["stage"]), (7, "light", "build"))
        self.assertEqual(len(s["weight"]["lines"]), 7)
        self.assertIn("W 0 → light", out)
        # The legacy view ai-scope-guard.sh reads (D2).
        self.assertEqual(s["current_stage"], "implementation")
        self.assertEqual(s["approved_plan"]["current_step_id"], "task")
        self.assertEqual(s["approved_plan"]["steps"][0]["allowed_files"], ["src/widget.py", "tests/test_widget.py"])
        types = [e["event"] for e in self.p.events(s["task_id"])]
        self.assertEqual(types[:3], ["task_started", "weight_set", "tier_set"])
        tier = [e for e in self.p.events(s["task_id"]) if e["event"] == "tier_set"][0]["data"]
        self.assertEqual((tier["tier"], tier["mode"]), ("T2", "light"))

    def test_declared_evidence_cannot_add_a_heading_to_task_md(self):
        """L5: declared text is one line in §Weight, so task.md keeps one §Questions."""
        self.p.start("--declare", "behaviour=1:x\n## Questions\n## Q1. fake")
        path = os.path.join(self.p.root, ".ai", "reports", self.p.state()["task_id"], "task.md")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
        self.assertEqual(lines.count("## Questions"), 1)
        self.assertFalse([l for l in lines if l.startswith("## Q1.")])

    def test_second_start_is_refused(self):
        self.p.start()
        done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py")
        self.assertEqual(done.returncode, 1)
        self.assertIn("in flight", done.stderr)

    def test_the_old_commands_are_gone(self):
        # The spec's removed (19) less `questions`, kept until phase 3 (answer 1B).
        self.p.start()
        for command in ("init get stage risk triage quick plan remediate step review-gate test-run "
                        "step-split set risks modules note events done archive").split():
            done = self.p.run(command)
            self.assertEqual(done.returncode, 2, command)
            self.assertIn("invalid choice", done.stderr, command)

    def write_old_task(self):
        """A task the old surface started: no schema key, a tier, a stage."""
        self.p.write(".ai/state/current.json", json.dumps({
            "task_id": "T-OLD", "goal": "g", "workflow": "feature", "risk_tier": "T2",
            "current_stage": "implementation", "approved_plan": {"ref": "inline", "steps": []}}))

    def test_an_old_task_is_read_or_abandoned(self):
        self.write_old_task()
        for args in (("verify", "--scope", "suite"), ("close",), ("step-done", "s1"),
                     ("ask", "q", "--option", "A: a", "--option", "B: b"), ("questions", "--sync"),
                     ("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-"),
                     ("answer", "Q1=A"), ("reject", "--by", "ivan", "--why", "no")):
            done = self.p.run(*args)
            self.assertEqual(done.returncode, 1, args)
            self.assertIn("old surface", done.stderr, args)
            self.assertIn("close --abandon", done.stderr, args)
        self.assertEqual(self.p.run("approve", "--by", "ivan", human=True).returncode, 1)
        self.assertIn("old surface", self.p.ok("status").stdout)
        self.p.ok("handoff", "--print")
        self.p.ok("questions")
        out = self.p.ok("close", "--abandon").stdout
        self.assertIn("T-OLD abandoned (old surface)", out)
        self.assertFalse(self.p.in_flight())
        self.assertEqual(self.p.archived("T-OLD")["result"], "abandoned")
        self.assertEqual(self.p.events("T-OLD")[-1]["event"], "task_closed")


class TestModes(Base):
    """R3: the mode table, enforced by close."""

    def test_light_closes_without_a_review(self):
        self.p.start()
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        out = self.p.ok("close").stdout
        self.assertIn("closed (light)", out)
        self.assertFalse(self.p.in_flight())

    def test_guarded_refuses_until_one_review(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("one review verdict", done.stderr)
        self.p.ok("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-",
                  stdin=FINDINGS)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_guarded_blockers_open_keeps_it_open(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("blockers", done.stderr)

    def test_full_refuses_until_the_gate_is_approved(self):
        self.p.start("--mode", "full", "--by", "test")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        weak = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.assertEqual(weak.returncode, 1)
        self.assertIn("needs a STRONG review", weak.stderr)
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        out = self.p.ok("close").stdout
        self.assertIn("ready for approval", out)
        self.assertEqual(self.p.state()["stage"], "ship")
        self.assertEqual(self.p.run("close").returncode, 4)                 # the gate's question blocks
        self.assertEqual(self.p.run("approve", "--by", "ivan").returncode, 5)    # no human here
        self.p.ok("approve", "--by", "ivan", human=True)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_full_approval_is_for_the_tree_it_saw(self):
        self.p.start("--mode", "full", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.p.ok("close")
        self.p.ok("approve", "--by", "ivan", human=True)
        self.p.write("src/widget.py", "x = 3\n")                           # changed after the approval
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        out = self.p.ok("close").stdout
        self.assertIn("ready for approval", out)                           # asked again, not archived
        self.assertTrue(self.p.in_flight())

    def test_full_irreversible_needs_confirm(self):
        self.p.start("--mode", "full_irreversible", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.assertIn("--confirm", self.p.ok("close").stdout)
        refused = self.p.run("approve", "--by", "ivan", human=True)
        self.assertEqual(refused.returncode, 5)
        self.assertIn("--confirm", refused.stderr)
        self.p.ok("approve", "--by", "ivan", "--confirm", "rewrite the users table", human=True)
        task = self.task_id()
        self.p.ok("close")
        self.assertEqual(self.p.archived(task)["gate"]["confirm"], "rewrite the users table")
        self.assertIn('confirm: rewrite the users table', self.p.task_md(task))


class TestTwoFacts(Base):
    """R6: (a) green suite on the current tree; (b) diff inside the task's files."""

    def setUp(self):
        super().setUp()
        self.p.start()
        self.p.write("src/widget.py", "x = 2\n")

    def test_green_green_needs_no_review(self):
        self.p.ok("verify", "--scope", "all")
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_stale_tree_needs_a_review(self):
        self.p.ok("verify", "--scope", "all")
        self.p.write("src/widget.py", "x = 3\n")
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("the tree changed after the last verify", done.stderr)

    def test_out_of_scope_file_needs_a_review(self):
        self.p.write("src/other.py", "y = 1\n")
        self.p.ok("verify", "--scope", "all")
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("outside the task's files: src/other.py", done.stderr)

    def test_red_suite_needs_a_review(self):
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("red on this tree", done.stderr)

    def test_a_review_of_this_tree_answers_a_red_fact(self):
        self.p.write("src/other.py", "y = 1\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_human_edit_after_verify(self):
        # Review focus 5: a guarded task, reviewed and green, then the human edits a
        # file and resumes. close never archives silently.
        self.p.close()
        self.p = Project()
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.write("src/widget.py", "x = 99\n")                          # the human's edit
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("a fresh 'verify --scope all' or a review of this tree", done.stderr)
        self.assertTrue(self.p.in_flight())
        self.p.ok("verify", "--scope", "suite")
        stale_e2e = self.p.run("close")                                    # M2: e2e ran on the old tree
        self.assertEqual(stale_e2e.returncode, 2)
        self.assertTrue(stale_e2e.stderr.startswith("state.py: verify required"), stale_e2e.stderr)
        self.p.ok("verify", "--scope", "e2e")
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_red_under_the_other_runtime_is_a_finding(self):
        # R19: the same tree green under claude and red under codex.
        self.p.ok("verify", "--scope", "all")
        self.p.flag("red")
        done = self.p.run("verify", "--scope", "suite", runtime="codex")
        self.assertEqual(done.returncode, 1)
        self.assertIn("finding: red under codex", done.stdout)
        task = self.task_id()
        self.p.ok("close", runtime="codex")
        self.assertIn("finding:", self.p.task_md(task))


class TestSurface(Base):
    def test_size_is_reported_not_gated(self):
        # R4: a 2 000-line, 40-file change closes in light mode; size is only reported.
        self.p.start(files="src/gen/**")
        self.assertEqual(self.p.state()["mode"], "light")
        for i in range(40):
            self.p.write("src/gen/m%02d.py" % i, "".join("v%d = %d\n" % (n, n) for n in range(50)))
        self.p.ok("verify", "--scope", "all")
        task = self.task_id()
        self.p.ok("close")
        text = self.p.task_md(task)
        self.assertIn("+2000 −0 lines, 40 files", text)
        self.assertEqual(len(self.p.archived(task)["changes"]), 40)

    def test_task_md_sections(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-",
                  stdin=FINDINGS)
        task = self.task_id()
        self.p.ok("close")
        text = self.p.task_md(task)
        self.assertTrue(text.startswith("# %s — tweak the widget\n" % task))
        positions = [text.index(h + "\n") for h in HEADINGS]
        self.assertEqual(positions, sorted(positions))
        weight_block = text.split("## Weight\n\n```\n", 1)[1].split("```", 1)[0].strip().split("\n")
        self.assertEqual(len(weight_block), 7)
        self.assertIn("override: light → guarded by test", text)
        self.assertIn("| 1 | suite | 0 |", text)
        self.assertIn("[HIGH] H1 the cache key ignores the locale", text)
        self.assertIn("| src/widget.py | +1 −1 | Edit |", text)
        self.assertIn("close: closed", text)
        # R8: the reports directory holds the journal and task.md, nothing else.
        self.assertEqual(sorted(os.listdir(os.path.join(self.p.root, ".ai", "reports", task))),
                         ["events.jsonl", "task.md"])
        logs = os.path.join(self.p.root, ".ai", "state", "logs")
        self.assertTrue(os.path.isfile(os.path.join(logs, task, "state.json")))
        with open(os.path.join(logs, ".gitignore"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "*\n")
        self.assertFalse(os.path.exists(os.path.join(self.p.root, ".ai", "state", "handoff.md")))

    def test_suite_budget(self):
        # R20: the third suite run is the human's.
        self.p.start()
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "all")
        third = self.p.run("verify", "--scope", "suite")
        self.assertEqual(third.returncode, 6)
        self.assertTrue(third.stderr.startswith("state.py: SUITE_BUDGET"))
        self.assertEqual(self.p.run("verify", "--scope", "suite", "--by", "ivan").returncode, 5)
        self.p.ok("verify", "--scope", "suite", "--by", "ivan", human=True)
        events = self.p.events(self.task_id())
        self.assertEqual([e["data"]["by"] for e in events if e["event"] == "human_set"], ["ivan"])
        self.assertEqual(self.p.state()["verify"]["suite_runs"], 3)

    def test_review_budget(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        third = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.assertEqual(third.returncode, 6)
        self.assertIn("REVIEW_BUDGET", third.stderr)
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--by", "ivan", human=True)
        self.assertEqual(self.p.state()["review"]["status"], "passed")

    def test_review_closes_findings_after_a_green_fix(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-",
                  stdin=FINDINGS)
        self.assertEqual(self.p.state()["review"]["findings"], ["H1"])      # L1 is not a HIGH
        early = self.p.run("review", "--closes", "H1")
        self.assertEqual(early.returncode, 1)                               # nothing fixed yet
        self.p.write("src/widget.py", "x = 2\n")
        self.p.ok("verify", "--scope", "suite", "--after-fix", "locale in the key")
        self.p.ok("review", "--closes", "H1")
        self.assertEqual(self.p.state()["review"]["status"], "passed")

    def test_amend(self):
        # R25: the scope grows in place and the journal says why.
        self.p.start()
        self.p.write("src/other.py", "y = 1\n")
        self.p.ok("start", "--amend", "--files", "+src/other.py", "--why", "the widget imports it")
        s = self.p.state()
        self.assertIn("src/other.py", s["files"])
        self.assertIn("src/other.py", s["approved_plan"]["steps"][0]["allowed_files"])
        self.assertEqual((s["current_stage"], s["stage"]), ("implementation", "build"))
        change = [e for e in self.p.events(s["task_id"]) if e["event"] == "scope_change"][0]["data"]
        self.assertEqual(change, {"added": ["src/other.py"], "why": "the widget imports it"})
        self.p.ok("verify", "--scope", "all")
        task = s["task_id"]
        self.p.ok("close")
        self.assertIn("amended ", self.p.task_md(task))
        self.assertEqual(self.p.run("start", "--amend", "--files", "+x").returncode, 1)  # no task, and no --why

    def test_mode_override(self):
        # R27: raising is free; lowering needs a human, and both are journaled.
        self.p.start("--mode", "full", "--by", "lead")
        task = self.task_id()
        event = [e for e in self.p.events(task) if e["event"] == "mode_set"][0]["data"]
        self.assertEqual((event["from"], event["to"], event["by"]), ("light", "full", "lead"))
        self.p.ok("close", "--abandon")
        q = Project({"src/Payment/Pay.php": "<?php\n"})
        try:
            args = ["start", "--goal", "g", "--workflow", "feature", "--files", "src/Payment/Pay.php",
                    "--mode", "light", "--by", "ivan"]
            refused = q.run(*args)
            self.assertEqual(refused.returncode, 5)
            self.assertFalse(q.in_flight())
            q.ok(*args, human=True)
            s = q.state()
            self.assertEqual((s["mode"], s["mode_override"]["from"]), ("light", "full"))
            event = [e for e in q.events(s["task_id"]) if e["event"] == "mode_set"][0]
            self.assertEqual((event["actor"], event["data"]["to"]), ("human", "light"))
        finally:
            q.close()

    def test_expect_fail(self):
        # R33: the test shown failing before the fix is recorded as such.
        self.p.start()
        self.p.flag("stepred")
        done = self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py", "--expect", "fail")
        self.assertIn("it bites", done.stdout)
        run = self.p.state()["verify"]["runs"][-1]
        self.assertEqual((run["expected_fail"], run["bites"]), (True, True))
        self.p.flag("stepred", on=False)
        self.assertEqual(self.p.run("verify", "--scope", "step", "--files", "tests/test_widget.py",
                                    "--expect", "fail").returncode, 1)
        self.assertEqual(self.p.run("verify", "--scope", "suite", "--expect", "fail").returncode, 1)
        self.assertEqual(self.p.state()["verify"]["suite_runs"], 0)       # a step run is not a suite run

    def test_drop_table_rescores_to_full_irreversible(self):
        # R26: the diff adds DROP TABLE to a migration; verify raises the mode.
        self.p.start(files="db/migrations/0002_drop.sql")
        self.assertEqual(self.p.state()["weight"]["axes"]["reversibility"], 1)
        self.p.write("db/migrations/0002_drop.sql", "DROP TABLE users;\n")
        out = self.p.ok("verify", "--scope", "suite").stdout
        self.assertIn("re-score: reversibility 1 → 2", out)
        s = self.p.state()
        self.assertEqual((s["mode"], s["weight"]["operations"]), ("full_irreversible", ["DROP"]))
        raised = [e["data"] for e in self.p.events(s["task_id"]) if e["event"] == "weight_raised"]
        self.assertEqual((raised[0]["axis"], raised[0]["mode_to"]), ("reversibility", "full_irreversible"))
        self.assertEqual([e["data"]["tier"] for e in self.p.events(s["task_id"]) if e["event"] == "tier_set"],
                         ["T2", "T6"])
        self.p.ok("verify", "--scope", "all", "--e2e", "not-applicable", "no flow reads the table")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.p.ok("close")
        self.assertEqual(self.p.run("approve", "--by", "ivan", "--confirm", "yes", human=True).returncode, 5)
        self.p.ok("approve", "--by", "ivan", "--confirm", "DROP TABLE users", human=True)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_step_done(self):
        self.p.start("--mode", "guarded", "--by", "test", "--steps", "s1:src/widget.py;s2:src/b.py")
        self.p.write("src/widget.py", "x = 2\n")
        self.assertIn("next: s2", self.p.ok("step-done", "s1").stdout)
        self.p.write("src/zzz.py", "z = 1\n")
        done = self.p.run("step-done", "s2")
        self.assertEqual(done.returncode, 6)
        self.assertTrue(done.stderr.startswith("state.py: SCOPE_CHANGE_REQUIRED"))
        self.assertIn("--amend", done.stderr)
        # --force is still accepted, as before 2.6, and still forces nothing
        done = self.p.run("step-done", "s2", "--force")
        self.assertEqual(done.returncode, 6)
        self.assertTrue(done.stderr.startswith("state.py: SCOPE_CHANGE_REQUIRED"))

    def test_status(self):
        self.assertIn("task: none", self.p.ok("status").stdout)
        self.p.start()
        out = self.p.ok("status").stdout.strip().split("\n")
        self.assertLessEqual(len(out), 20)
        self.assertTrue(any(line.startswith("mode: light") for line in out))
        data = json.loads(self.p.ok("status", "--json").stdout)
        self.assertEqual((data["schema"], data["mode"]), (7, "light"))
        self.assertFalse(data["facts"]["a"][0])
        # /rr-status hands a schema-7 task to state.py status.
        status_py = os.path.join(ROOT, "skills", "rr-status", "status.py")
        shown = subprocess.run([sys.executable, "-I", status_py, "--root", self.p.root], capture_output=True,
                               text=True, check=False).stdout
        self.assertIn("mode: light", shown)
        self.assertIn("facts: (a) RED", shown)

    def test_a_narrowed_suite_is_not_fact_a(self):
        self.p.start()
        self.p.ok("verify", "--scope", "suite", "--files", "tests/test_widget.py")
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("no whole-suite", done.stderr)

    def test_a_rejection_is_answered_by_changing_the_work(self):
        self.p.start("--mode", "full", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.p.ok("close")
        self.p.ok("reject", "--by", "ivan", "--why", "the widget needs a test")
        same = self.p.run("close")
        self.assertEqual(same.returncode, 5)
        self.assertIn("nothing changed since", same.stderr)
        self.p.write("src/widget.py", "x = 222\n")
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        self.assertIn("ready for approval", self.p.ok("close").stdout)        # asked anew
        self.assertIsNone(self.p.state()["human_approval"]["rejected_at"])

    def test_rescore_keeps_a_human_lowering(self):
        q = Project({"src/Payment/Pay.php": "<?php\n"})
        try:
            q.ok("start", "--goal", "g", "--workflow", "feature", "--files", "src/Payment/Pay.php",
                 "--mode", "light", "--by", "ivan", human=True)
            q.write("src/Payment/Pay.php", "<?php // fee\n")
            q.ok("verify", "--scope", "all")
            self.assertEqual(q.state()["mode"], "light")
        finally:
            q.close()

    def test_red_then_green_across_runtimes_is_a_finding(self):
        self.p.start()
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "suite", runtime="codex").returncode, 1)
        self.p.flag("red", on=False)
        out = self.p.ok("verify", "--scope", "suite").stdout
        self.assertIn("finding: red under codex on a tree green under claude", out)
        self.assertEqual(len(self.p.state()["findings"]), 1)

    def test_a_mode_the_weight_already_gives_is_no_override(self):
        self.p.start("--mode", "light", "--by", "lead")
        s = self.p.state()
        self.assertIsNone(s["mode_override"])
        self.assertNotIn("mode_set", [e["event"] for e in self.p.events(s["task_id"])])

class TestReviewPass1(Base):
    """The findings of T-2026-10-25-008's STRONG review, each pinned: every test
    here failed on the tree before remediation R3."""

    def full_at_gate(self, mode="full"):
        """A full task, verified and reviewed, whose close has opened the gate."""
        self.p.start("--mode", mode, "--by", "test", files="src/widget.py,db/migrations/**")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.assertIn("ready for approval", self.p.ok("close").stdout)

    def test_an_approval_is_for_the_tree_close_put_up(self):
        # Review B1: a DROP written while the gate is open is never signed off by
        # an approval of the tree before it.
        self.full_at_gate()
        self.p.write("db/migrations/001.sql", "DROP TABLE users;\n")
        moved = self.p.run("approve", "--by", "ivan", human=True)
        self.assertEqual(moved.returncode, 5)
        self.assertIn("the tree changed after close asked", moved.stderr)
        self.p.ok("reject", "--by", "ivan", "--why", "the tree changed")
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        out = self.p.ok("close").stdout
        self.assertIn("full_irreversible ready for approval", out)
        self.assertIn('--confirm "<what it does, naming DROP>"', out)
        self.assertEqual(self.p.run("approve", "--by", "ivan", human=True).returncode, 5)
        self.p.ok("approve", "--by", "ivan", "--confirm", "drop the users table", human=True)
        task = self.task_id()
        self.p.ok("close")
        gate = self.p.archived(task)["gate"]
        self.assertEqual((gate["confirm"], gate["approved_tree"]), ("drop the users table", gate["tree"]))

    def test_confirm_names_an_alter_in_the_humans_words(self):
        # Review M6: operations are keywords, not the patterns' regex source.
        self.full_at_gate("full")
        self.p.ok("reject", "--by", "ivan", "--why", "add the column drop first")
        self.p.write("db/migrations/002.sql", "ALTER TABLE users DROP COLUMN email;\n")
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        self.p.ok("close")
        self.assertEqual(self.p.state()["weight"]["operations"], ["ALTER", "DROP"])
        self.p.ok("approve", "--by", "ivan", "--confirm", "ALTER TABLE users DROP COLUMN email", human=True)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_the_questions_file_route_closes_a_full_task(self):
        # Review M5: [Answer]: A plus questions --sync grants the gate close asked for.
        self.full_at_gate()
        qpath = os.path.join(self.p.root, ".ai", "reports", self.task_id(), "task.md")
        with open(qpath, encoding="utf-8") as fh:
            text = fh.read()
        at = text.rindex("[Answer]:")                                    # G1's own line, not the header's
        with open(qpath, "w", encoding="utf-8") as fh:
            fh.write(text[:at] + "[Answer]: A" + text[at + len("[Answer]:"):])
        self.p.ok("questions", "--sync", "--by", "ivan", human=True)
        task = self.task_id()
        self.p.ok("close")
        self.assertEqual(self.p.archived(task)["gate"]["approved_by"], "ivan")

    def test_a_verdict_must_agree_with_its_findings(self):
        # Review H2.
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        blocker = "FINDINGS\n[BLOCKER] B1 sql injection\nin_scope: yes\n"
        for verdict, report, why in (("pass", "", "FINDINGS block"),
                                     ("pass", blocker, "verdict is blockers_open"),
                                     ("pass", FINDINGS, "VERDICT line says pass_with_findings"),
                                     ("pass", "FINDINGS\n[HIGH] H1 x\n", "in-scope HIGH")):
            done = self.p.run("review", "--verdict", verdict, "--tier", "BALANCED", "--report", "-", stdin=report)
            self.assertEqual(done.returncode, 1, (verdict, report))
            self.assertIn(why, done.stderr)
        self.assertEqual(self.p.state()["review"]["passes"], 0)
        # Out of scope is not a blocker.
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-",
                  stdin="FINDINGS\n[BLOCKER] B1 elsewhere\nin_scope: no\n")

    def test_a_red_e2e_is_not_declared_away(self):
        # Review M1.
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.flag("e2ered")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        done = self.p.run("verify", "--scope", "e2e", "--e2e", "not-applicable", "because I say so")
        self.assertEqual(done.returncode, 1)
        self.assertIn("red on this tree", done.stderr)
        self.assertEqual(self.p.state()["verify"]["e2e"], "failing")

    def test_a_run_whose_tree_moved_stands_for_no_tree(self):
        # Review M3: the suite edits a tracked file while it runs.
        self.p.start()
        self.p.flag("touch")
        out = self.p.ok("verify", "--scope", "all").stdout
        self.assertIn("tree moved during the run", out)
        self.assertIsNone(self.p.state()["verify"]["runs"][0]["tree"])
        self.assertEqual(self.p.run("close").returncode, 2)

    def test_a_red_under_claude_is_never_waived(self):
        # Review M4: only a Codex-only red is a finding.
        self.p.start()
        self.p.ok("verify", "--scope", "suite", runtime="codex")
        self.p.flag("red")
        out = self.p.run("verify", "--scope", "suite").stdout
        self.assertNotIn("finding:", out)
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("went red on this tree after run 1 (run 2 under claude)", done.stderr)

    def test_start_refuses_an_empty_scope_and_a_tree_without_git(self):
        # Review M7, M8.
        done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", " , ")
        self.assertEqual(done.returncode, 1)
        self.assertIn("at least one file", done.stderr)
        shutil.rmtree(os.path.join(self.p.root, ".git"))
        done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py")
        self.assertEqual(done.returncode, 1)
        self.assertIn("needs a git repository", done.stderr)
        self.assertFalse(self.p.in_flight())

    def test_task_md_fences_a_report_that_quotes_code(self):
        # Review L1.
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-",
                  stdin="FINDINGS\nnone; quoted:\n```\nx = 1\n```\n")
        text = self.p.task_md(self.task_id())
        self.assertIn("````\nFINDINGS\nnone; quoted:\n```\nx = 1\n```\n````", text)
        self.assertIn("## Questions\n\nnone", text)

    def test_abandon_skips_the_checks(self):
        self.p.start("--mode", "full", "--by", "test")
        task = self.task_id()
        self.p.ok("close", "--abandon")
        self.assertEqual(self.p.archived(task)["result"], "abandoned")


class TestReviewPass2(Base):
    """The findings of the scoped re-review of R3, each pinned: every test here
    failed on the tree before remediation R4."""

    def guarded(self):
        self.p.start("--mode", "guarded", "--by", "test")
        self.p.write("src/widget.py", "x = 2\n")

    def test_e2e_command_none_is_declared_on_every_tree(self):
        # Review N1: `none` is never run, so an edit after it is no dead end.
        with open(os.path.join(self.p.root, ".ai", "policies", "testing.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.p.write(".ai/policies/testing.md", text.split("e2e_command:")[0] + "e2e_command: none\n")
        self.guarded()
        self.assertIn("e2e: not applicable", self.p.ok("verify", "--scope", "all").stdout)
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.write("src/widget.py", "x = 3\n")
        self.p.ok("verify", "--scope", "suite")
        owed = self.p.run("close")
        self.assertEqual(owed.returncode, 2)
        self.assertIn("--e2e not-applicable", owed.stderr)
        self.assertIn("e2e: not applicable", self.p.ok("verify", "--scope", "e2e").stdout)
        self.assertEqual([r for r in self.p.state()["verify"]["runs"] if r["scope"] == "e2e"], [])
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_a_red_e2e_is_not_declared_away_after_an_edit(self):
        # Review M1 (pass 2): an edit and a suite run do not make a red e2e
        # declarable; the next e2e run decides.
        self.guarded()
        self.p.flag("e2ered")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        self.p.write("src/widget.py", "x = 2  \n")                        # whitespace only
        self.p.ok("verify", "--scope", "suite")
        done = self.p.run("verify", "--scope", "e2e", "--e2e", "not-applicable", "because I say so")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no e2e run since has passed", done.stderr)
        self.assertEqual(self.p.state()["verify"]["e2e"], "failing")
        self.p.flag("e2ered", on=False)
        self.p.ok("verify", "--scope", "e2e")
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.ok("close")

    def test_a_refused_declaration_runs_no_suite(self):
        # Review N3: the refusal comes before the suite, so no run is lost.
        self.guarded()
        self.p.flag("e2ered")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        done = self.p.run("verify", "--scope", "all", "--e2e", "not-applicable", "because I say so")
        self.assertEqual(done.returncode, 1)
        self.assertIn("red on this tree", done.stderr)
        verify = self.p.state()["verify"]
        self.assertEqual((verify["suite_runs"], len(verify["runs"])), (1, 2))
        # The unrecorded run's log is the trace of a suite that ran for nothing.
        logs = os.listdir(os.path.join(self.p.root, ".ai", "state", "logs", self.task_id()))
        self.assertNotIn("suite-3.log", logs)

    def test_a_green_under_codex_does_not_answer_a_red_under_claude(self):
        # Review M4 (pass 2) and N2: red under claude, then green under codex, on
        # one tree: recorded, and close is blocked until claude is green.
        self.p.start()
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "suite").returncode, 1)
        self.p.flag("red", on=False)
        out = self.p.ok("verify", "--scope", "suite", runtime="codex").stdout
        self.assertIn("red under claude on a tree green under codex — recorded in task.md", out)
        self.assertEqual(len(self.p.state()["findings"]), 1)
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2)
        self.assertIn("red on this tree under claude (run 1); green under codex (run 2) does not answer it",
                      done.stderr)
        self.p.ok("verify", "--scope", "suite", "--by", "ivan", human=True)    # run 3: past the budget
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_the_shipped_verdict_section_is_read(self):
        # Review N4: ai/agents/reviewer.md writes "## VERDICT" and "verdict: <x>".
        self.guarded()
        self.p.ok("verify", "--scope", "all")
        report = "FINDINGS\nnone\n\n## VERDICT\nverdict: pass_with_findings\nscope_assessment: inside\n"
        done = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=report)
        self.assertEqual(done.returncode, 1)
        self.assertIn("VERDICT line says pass_with_findings", done.stderr)
        self.p.ok("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-",
                  stdin=report)


def git_tree(root):
    subprocess.run(["git", "-C", root, "add", "-A"], check=True)
    return subprocess.run(["git", "-C", root, "write-tree"], check=True,
                          capture_output=True, text=True).stdout.strip()


class TestRescore(unittest.TestCase):
    """state.rescore_weight and sensors.diff_files: reversibility and domain from the
    diff, only upward."""

    def setUp(self):
        self.policy = weight.load_policy("/nonexistent")[0]
        self.p = Project({"db/migrations/0001_init.sql": "CREATE TABLE users (id int);\nDROP TABLE old;\n"})
        self.base = git_tree(self.p.root)

    def tearDown(self):
        self.p.close()

    def rescore(self, files, current=None):
        return state_mod.rescore_weight(self.p.root, self.base, files, current or dict.fromkeys(weight.AXES, 0),
                                 self.policy)

    def test_content_already_there_never_raises_past_needs_step(self):
        self.p.write("db/migrations/0001_init.sql", "CREATE TABLE users (id int);\nDROP TABLE old;\n-- n\n")
        got = self.rescore(["db/migrations/0001_init.sql"])
        self.assertEqual((got["axes"]["reversibility"], got["irreversible"]), (1, False))

    def test_only_upward_and_only_two_axes(self):
        current = dict(dict.fromkeys(weight.AXES, 0), reversibility=2, scope=1)
        got = self.rescore(["db/migrations/0001_init.sql", "src/Payment/Pay.php"], current)
        self.assertEqual((got["axes"]["reversibility"], got["axes"]["domain"], got["axes"]["scope"]), (2, 2, 1))
        self.assertEqual([r["axis"] for r in got["raised"]], ["domain"])

    def test_lowercase_is_not_a_keyword(self):
        self.p.write("db/migrations/0003.py", "def rename(): drop = 1\n")
        self.assertFalse(self.rescore(["db/migrations/0003.py"])["irreversible"])

    def test_mode_for_matches_compute(self):
        for axes, mode in (({}, "light"), ({"scope": 2, "behaviour": 1}, "guarded"),
                           ({"domain": 2}, "full"), ({"domain": 2, "reversibility": 2}, "full_irreversible")):
            self.assertEqual(state_mod.mode_for(axes, self.policy), mode)

    def test_snapshot_sees_a_same_size_edit_made_in_the_index_second(self):
        # Racy git: an edit that keeps the size, made in the second the index was
        # written, must not vanish from a snapshot taken a second later. The copy
        # of the index has to keep its mtime, or git trusts the stale stat.
        p = Project()
        try:
            subprocess.run(["git", "-C", p.root, "add", "-A"], check=True)
            p.write("src/widget.py", "x = 9\n")                      # same size as "x = 1\n"
            time.sleep(1.2)
            expected = git_tree(p.root)                              # a real add re-reads the file
            subprocess.run(["git", "-C", p.root, "reset", "-q"], check=True)
            p.write("src/widget.py", "x = 1\n")
            subprocess.run(["git", "-C", p.root, "add", "-A"], check=True)
            p.write("src/widget.py", "x = 9\n")
            time.sleep(1.2)
            self.assertEqual(sensors.snapshot_tree(p.root), expected)
        finally:
            p.close()

    def test_diff_files_names_every_status(self):
        os.remove(os.path.join(self.p.root, "src/widget.py"))
        self.p.write("src/new.py", "y = 2\n")
        self.p.write("db/migrations/0001_init.sql", "changed\n")
        got = sensors.diff_files(self.p.root, self.base, git_tree(self.p.root))
        self.assertEqual(sorted((d["path"], d["status"]) for d in got),
                         [("db/migrations/0001_init.sql", "M"), ("src/new.py", "A"), ("src/widget.py", "D")])
        self.assertIsNone(sensors.diff_files(self.p.root, None, self.base))


# ---------------------------------------------------------------------------
# Ported in redesign 2.6 from tests/test-ai-task-state.sh: the cases whose
# subject outlives the old surface (the journal, runtime ownership, questions,
# the gate and its file route, handoff.md, WP5), set up with start and close
# instead of init, stage and get. The old file keeps only what needs no task.

PTY_RUN = """
import os, pty, sys
env = dict(os.environ)
for name in sys.argv[3].split(","):
    env.pop(name, None)
for pair in sys.argv[4].split(",") if sys.argv[4] else []:
    key, _, value = pair.partition("=")
    env[key] = value
os.environ.clear(); os.environ.update(env)
status = pty.spawn([sys.executable, "-I", sys.argv[1], "--root", sys.argv[2]] + sys.argv[5:])
sys.exit(os.waitstatus_to_exitcode(status))
"""


class Ported(Base):
    def qpath(self, task_id=None):
        return os.path.join(self.p.root, ".ai", "reports", task_id or self.task_id(), "task.md")

    def qtext(self, task_id=None):
        with open(self.qpath(task_id), encoding="utf-8") as fh:
            return fh.read()

    def fill(self, qid, answer, task_id=None):
        """The human's hand edit: the [Answer]: line of block <qid>."""
        lines = self.qtext(task_id).split("\n")
        start = next(i for i, line in enumerate(lines) if line.startswith("## %s." % qid))
        end = next(i for i in range(start, len(lines)) if lines[i].startswith("[Answer]:"))
        lines[end] = ("[Answer]: " + answer).rstrip()
        with open(self.qpath(task_id), "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines))

    def questions(self):
        return json.loads(self.p.ok("questions", "--format", "json").stdout)

    def of(self, event, task_id=None):
        return [e for e in self.p.events(task_id or self.task_id()) if e["event"] == event]

    def session(self, **data):
        self.p.write(".ai/state/session.json", json.dumps(data))

    def approval(self):
        return self.p.state()["human_approval"]

    def open_gate(self):
        """A full task, verified and reviewed, whose close has opened the gate."""
        self.p.start("--mode", "full", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.assertIn("ready for approval", self.p.ok("close").stdout)

    def reopen_gate(self, text):
        """After a rejection: change the work, verify it, and close asks again."""
        self.p.write("src/widget.py", text)
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        self.assertIn("ready for approval", self.p.ok("close").stdout)

    def unattended(self, *args):
        return self.p.run(*args, runtime=None, env={"AI_UNATTENDED": "1"})

    def in_pty(self, *args, set_env=""):
        """state.py from a pseudo-terminal, every agent marker removed, then set_env set."""
        markers = ",".join(list(state_mod.AGENT_MARKERS) + ["AI_RUNTIME", "AI_UNATTENDED"])
        return subprocess.run([sys.executable, "-c", PTY_RUN, STATE, self.p.root, markers, set_env] + list(args),
                              capture_output=True, text=True, check=False)


class TestJournal(Ported):
    def test_start_opens_the_journal_with_a_typed_line(self):
        self.p.run("start", "--goal", "journal core", "--workflow", "feature", "--files", "src/widget.py",
                   *ZERO, runtime=None)
        first = self.p.events(self.task_id())[0]
        self.assertEqual((first["event"], first["task"], first["data"]["workflow"]),
                         ("task_started", self.task_id(), "feature"))
        self.assertEqual((first["runtime"], first["actor"]), ("unknown", "agent"))
        self.assertRegex(first["ts"], r"\.[0-9]{3}Z$")

    def test_a_journal_that_cannot_be_written_never_fails_the_command(self):
        self.p.start()
        journal = os.path.join(self.p.root, ".ai", "reports", self.task_id(), "events.jsonl")
        os.remove(journal)
        os.makedirs(journal)                                # a directory: os.open fails for every user
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py")
        self.assertEqual(len(self.p.state()["verify"]["runs"]), 1)    # the state write is the contract

    def test_an_oddly_shaped_state_still_answers(self):
        self.p.start()
        s = self.p.state()
        s["human_approval"] = None
        self.p.write(".ai/state/current.json", json.dumps(s))
        self.p.ok("status")
        self.p.ok("handoff", "--print")

    def test_hook_events_and_what_event_refuses(self):
        self.p.start()
        self.p.ok("event", "handoff_written", "--detail", "precompact", "--data", '{"reason":"precompact","lines":21}')
        line = self.of("handoff_written")[-1]
        self.assertEqual((line["actor"], line["data"]["lines"]), ("hook", 21))
        self.assertIn("unknown event type", self.p.run("event", "not_a_type").stderr)
        forged = self.p.run("event", "gate_approved", "--detail", "granted by the human via terminal",
                            "--data", '{"by":"the human","via":"terminal","tty":true}')
        self.assertEqual(forged.returncode, 5)
        self.assertIn("not by 'event'", forged.stderr)
        self.assertEqual(self.of("gate_approved"), [])
        for kind in ("gate_requested", "gate_rejected", "task_started", "task_closed"):
            self.assertEqual(self.p.run("event", kind, "--detail", "x").returncode, 5, kind)
        self.p.ok("event", "model_fallback", "--detail", "fable overloaded", "--data", '{"agent":"architect"}')
        self.p.ok("event", "missed_reroute", "--detail", "gpt-6-astra reached during an outage",
                  "--data", '{"agent":"ai-expert","model":"gpt-6-astra","reason":"rate_limit"}')

    def test_task_id_is_a_directory_name(self):
        for bad in ("../../../outside/evil", "T-1/../.."):
            done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py",
                              "--task-id", bad, *ZERO)
            self.assertEqual(done.returncode, 1, bad)
            self.assertIn("--task-id takes a directory name", done.stderr)
        self.assertFalse(os.path.exists(os.path.join(self.p.tmp.name, "outside")))
        self.p.ok("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py",
                  "--task-id", "T-2026.09-a_b", *ZERO)


class TestOwnership(Ported):
    """R10, I10: the first mutating command owns the task; another runtime's
    change hands it over before the work it covers."""

    def test_a_change_from_another_runtime_hands_the_task_over(self):
        self.p.start()
        self.assertEqual(self.p.state()["owner_runtime"], "claude")
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py")
        self.assertEqual(self.of("runtime_handoff"), [])
        self.p.ok("status", runtime="codex")
        self.assertEqual(self.of("runtime_handoff"), [])              # a read hands nothing off
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py", runtime="codex")
        moved = self.of("runtime_handoff")
        self.assertEqual([(e["data"]["from"], e["data"]["to"], e["data"]["via"]) for e in moved],
                         [("claude", "codex", "resume")])
        self.assertEqual(self.p.state()["owner_runtime"], "codex")
        events = [e["event"] for e in self.p.events(self.task_id())]
        # by position, not by timestamp: events inside one command share a millisecond
        self.assertLess(events.index("runtime_handoff"), len(events) - 1, events)
        self.assertIn("--runtime", self.p.ok("--help").stdout)

    def test_detection_precedence(self):
        self.p.start()
        ask = ("ask", "q", "--option", "A: a", "--option", "B: b")
        self.session(runtime="codex", session_id="s1")
        self.p.ok(*ask, runtime=None)
        self.assertEqual(self.p.state()["owner_runtime"], "codex")    # session.json when nothing else
        self.p.ok(*ask, runtime=None, env={"CLAUDECODE": "1"})
        self.assertEqual(self.p.state()["owner_runtime"], "claude")   # CLAUDECODE outranks session.json
        self.p.ok("--runtime", "codex", *ask, runtime=None, env={"CLAUDECODE": "1"})
        self.assertEqual(self.p.state()["owner_runtime"], "codex")    # --runtime outranks CLAUDECODE
        os.remove(os.path.join(self.p.root, ".ai", "state", "session.json"))
        self.p.ok(*ask, runtime=None, env={"CLAUDECODE": "1"})
        self.assertEqual(self.p.state()["owner_runtime"], "claude")   # CLAUDECODE before unknown

    def test_the_copy_under_codex_home_is_codex(self):
        home = os.path.join(self.p.tmp.name, "codex-home")
        shutil.copytree(os.path.dirname(STATE), os.path.join(home, "skills", "ai-task"),
                        ignore=shutil.ignore_patterns("__pycache__"))
        copy = os.path.join(home, "skills", "ai-task", "state.py")
        self.p.start()
        self.session(runtime="claude", session_id="s2")
        ask = ("ask", "q", "--option", "A: a", "--option", "B: b")
        self.p.ok(*ask, runtime=None, env={"CODEX_HOME": home}, state_py=copy)
        self.assertEqual(self.p.state()["owner_runtime"], "codex")
        self.p.ok(*ask)
        self.p.ok(*ask, runtime=None, env={"CODEX_HOME": home, "CLAUDECODE": "1"}, state_py=copy)
        self.assertEqual(self.p.state()["owner_runtime"], "codex")    # an inherited CLAUDECODE does not win

    def test_two_appenders_lose_and_interleave_nothing(self):
        pids = []
        for worker in ("a", "b"):
            pid = os.fork()
            if pid == 0:
                for i in range(200):
                    state_mod.append_journal(self.p.root, "T-concurrent", state_mod.journal_line(
                        "T-concurrent", "note", "agent", "test", "%s-%03d" % (worker, i),
                        {"kind": "decision", "text": "x" * 300}))
                os._exit(0)                               # pylint: disable=protected-access
            pids.append(pid)
        for pid in pids:
            os.waitpid(pid, 0)
        with open(os.path.join(self.p.root, ".ai", "reports", "T-concurrent", "events.jsonl"), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 400)
        self.assertEqual(len([json.loads(line) for line in lines]), 400)

    def test_a_journal_line_stays_under_the_cap(self):
        cut = json.loads(state_mod.journal_line("T-x", "note", "agent", "plan", "d" * 5000, {"error": "e" * 9000}))
        self.assertEqual((len(cut["detail"]), len(cut["data"]["error"])), (500, 1000))
        huge = state_mod.journal_line("T-x", "note", "agent", "plan", "d", {"text": "x" * 9000})
        self.assertLessEqual(len(huge.encode()), 4096)
        self.assertEqual(json.loads(huge)["data"], {"truncated": True})


class TestQuestions(Ported):
    """R1-R5: ask writes the file, never the model; the file is the record."""

    def setUp(self):
        super().setUp()
        self.p.start()

    def ask_rounding(self):
        self.p.ok("ask", "Which rounding rule applies to the per-line fee?",
                  "--option", "A: Round half up per line", "--option", "B: Round half even per order total",
                  "--recommend", "A", "--context", "src/Payment/FeeCalculator.php:42",
                  "--by", "ai-planner via main session")

    def test_ask_writes_the_file(self):
        self.ask_rounding()
        q = self.questions()[0]
        self.assertEqual((q["id"], q["question"], [o["key"] for o in q["options"]], q["recommend"], q["pending"]),
                         ("Q1", "Which rounding rule applies to the per-line fee?", ["A", "B"], "A", True))
        self.assertIn("FeeCalculator.php:42", q["context"])
        self.assertRegex(self.qtext(), r"(?m)^X\. Other — answer as")
        self.assertEqual(self.p.state()["questions"]["pending"], ["Q1"])
        self.assertEqual(self.of("question_asked")[0]["data"]["recommended"], "A")

    def test_a_hand_edited_answer_round_trips(self):
        self.ask_rounding()
        before = [line for line in self.qtext().split("\n") if not line.startswith("[Answer]")]
        self.fill("Q1", "B")
        self.p.ok("questions", "--sync", "--by", "ivan")
        self.assertEqual([line for line in self.qtext().split("\n") if not line.startswith("[Answer]")], before)
        self.assertEqual(len(re.findall(r"(?m)^\[Answer\]: B — by ivan via file at ", self.qtext())), 1)
        answered = self.of("question_answered")
        self.assertEqual([(e["data"]["via"], e["data"]["choice"], e["actor"]) for e in answered],
                         [("file", "B", "human")])
        synced = self.qtext()
        self.p.ok("questions", "--sync")
        self.assertEqual((self.qtext(), len(self.of("question_answered"))), (synced, 1))   # idempotent

    def test_the_questions_live_in_task_md(self):
        """R7, R8: §Questions holds the blocks, the other sections stay, no questions.md."""
        self.ask_rounding()
        text = self.qtext()
        self.assertEqual([h for h in HEADINGS if ("\n%s\n" % h) in text], HEADINGS)
        section = text[text.index("## Questions\n"):text.index("\n## Verify\n")]
        self.assertIn("## Q1. Which rounding rule", section)
        self.assertNotIn("\nnone\n", section)
        self.assertFalse(os.path.exists(os.path.join(os.path.dirname(self.qpath()), "questions.md")))

    def test_a_filled_answer_survives_a_rerender(self):
        """D1: task.md is rewritten from the state after every change, §Questions is read back."""
        self.ask_rounding()
        self.fill("Q1", "B")
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py")   # rewrites task.md
        self.assertRegex(self.qtext(), r"(?m)^\| 1 \| step \|")
        self.assertRegex(self.qtext(), r"(?m)^\[Answer\]: B$")
        self.p.ok("questions", "--sync", "--by", "ivan")
        self.assertEqual([(e["data"]["via"], e["data"]["choice"]) for e in self.of("question_answered")],
                         [("file", "B")])
        self.assertEqual(self.p.state()["questions"]["pending"], [])

    def test_a_task_started_before_the_fold_keeps_its_questions_md(self):
        """A task in flight with a legacy questions.md: read, answered, carried into task.md; the file stays."""
        legacy = os.path.join(os.path.dirname(self.qpath()), "questions.md")
        with open(legacy, "w", encoding="utf-8") as fh:
            fh.write("# Questions — %s\n<!-- Written by state.py. -->\n\n## Q1. Which rounding rule?\n"
                     "asked: 2026-10-20T10:00:00Z · stage: planning\nA. Half up (recommended)\nB. Half even\n"
                     "X. Other — answer as `X: <text>`\n[Answer]:\n" % self.task_id())
        self.assertEqual([(q["id"], q["pending"]) for q in self.questions()], [("Q1", True)])
        self.p.ok("answer", "Q1=A", "--by", "ivan")
        self.assertRegex(self.qtext(), r"(?m)^## Q1\. Which rounding rule\?\n(?:.*\n)*?\[Answer\]: A — by ivan ")
        self.assertTrue(os.path.isfile(legacy))
        self.assertEqual([(q["id"], q["pending"]) for q in self.questions()], [("Q1", False)])

    def test_an_answer_that_is_not_an_option_stays_pending(self):
        self.ask_rounding()
        self.fill("Q1", "F")
        self.assertIn("Q1: invalid choice 'F'", self.p.ok("questions", "--sync").stderr)
        self.assertTrue(self.questions()[0]["pending"])
        self.p.ok("answer", "Q1=B", "--by", "ivan", "--via", "picker")
        self.assertEqual((self.questions()[0]["pending"], self.questions()[0]["choice"]), (False, "B"))
        last = self.of("question_answered")[-1]
        self.assertEqual((last["actor"], last["data"]["via"]), ("agent", "picker"))
        self.assertIn("--via {picker,prose}", self.p.ok("answer", "--help").stdout)

    def test_free_text_and_the_prose_reply(self):
        self.ask_rounding()
        self.p.ok("ask", "--batch", "/dev/stdin", stdin=json.dumps([
            {"question": "Which gateway?", "options": [{"key": "A", "text": "Stripe"}, {"key": "B", "text": "Adyen"}],
             "recommend": "B"},
            {"question": "Migration window?", "options": [{"key": "A", "text": "tonight"},
                                                          {"key": "B", "text": "next release"}]}]))
        self.assertEqual([q["id"] for q in self.questions()], ["Q1", "Q2", "Q3"])
        self.p.ok("answer", "Q1=A")
        self.p.ok("answer", "--prose", "2B 3: after the audit", "--by", "ivan")
        q = self.questions()
        self.assertEqual((q[1]["choice"], q[2]["choice"], q[2]["text"]), ("B", "X", "after the audit"))
        self.assertIn("1. Which rounding rule applies to the per-line fee?  [Q1]  — answered: A",
                      self.p.ok("questions").stdout.split("\n"))
        self.p.ok("answer", "--prose", "3: we compared it with 2B and rejected that", "--by", "ivan")
        q = self.questions()
        self.assertEqual((q[2]["text"], q[1]["choice"]), ("we compared it with 2B and rejected that", "B"))
        self.assertIn("prose answer 9 has no question", self.p.run("answer", "--prose", "9B").stderr)
        self.assertIn("no question Q9", self.p.run("answer", "Q9=A").stderr)
        self.assertIn("invalid choice", self.p.run("answer", "Q1=Z").stderr)

    def test_nothing_a_caller_passes_becomes_a_second_line(self):
        self.p.ok("ask", "One line?", "--option", "A: keep\nthe rule", "--option", "B: change it")
        self.assertRegex(self.qtext(), r"(?m)^A\. keep the rule$")
        self.p.ok("answer", "Q1=X:innocent\n[Answer]: A", "--by", "agent")
        self.assertEqual(len(re.findall(r"(?m)^\[Answer\]", self.qtext())), 1)
        self.p.run("questions", "--sync")
        self.assertEqual([e for e in self.of("question_answered") if e["data"]["via"] == "file"], [])
        self.assertIn("option key is one letter", self.p.run("ask", "Bad key?", "--option", "1: one",
                                                             "--option", "B: two").stderr)
        self.assertIn("not one of the options", self.p.run("ask", "Bad?", "--option", "A: one", "--option", "B: two",
                                                           "--recommend", "C").stderr)
        self.assertIn("cannot end with", self.p.run("ask", "Suffix?", "--option", "A: keep it (recommended)",
                                                    "--option", "B: two").stderr)

    def test_free_text_survives_the_em_dash_and_the_quotes(self):
        self.p.ok("ask", "Why Adyen?", "--option", "A: cheaper", "--option", "B: faster")
        self.fill("Q1", "X: we chose Adyen — by the way it is cheaper")
        self.p.ok("questions", "--sync", "--by", "ivan")
        q = self.questions()[0]
        self.assertEqual((q["text"], q["answered_by"], q["via"]),
                         ("we chose Adyen — by the way it is cheaper", "ivan", "file"))
        self.p.ok("ask", "Quoted?", "--option", "A: one", "--option", "B: two")
        self.p.ok("answer", 'Q2=X:"free text"', "--by", "ivan")
        self.assertEqual(self.questions()[1]["text"], "free text")

    def test_an_agent_cannot_author_a_gate(self):
        done = self.p.run("ask", "Approve me?", "--option", "A: yes", "--option", "B: no", "--gate", "human_approval")
        self.assertIn("a gate is requested by 'state.py close' in full mode, not by ask", done.stderr)

    def test_a_pending_question_blocks_what_moves_the_task_and_nothing_else(self):
        self.p.ok("ask", "Which rule?", "--option", "A: one", "--option", "B: two")
        state_file = os.path.join(self.p.root, ".ai", "state", "current.json")
        with open(state_file, encoding="utf-8") as fh:
            before = fh.read()
        qbefore = self.qtext()
        for args in (("verify", "--scope", "all"), ("step-done", "task"), ("approve", "--by", "me"), ("close",)):
            done = self.p.run(*args)
            self.assertEqual(done.returncode, 4, args)
            self.assertIn("QUESTIONS_PENDING — 1 unanswered in .ai/reports/%s/task.md: Q1. Answer with "
                          "'state.py answer Q1=<letter>'" % self.task_id(), done.stderr, args)
            with open(state_file, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), before, args)
            self.assertEqual(self.qtext(), qbefore, args)
        for args in (("status",), ("handoff", "--print"), ("questions",), ("event", "model_fallback"),
                     ("ask", "q", "--option", "A:one", "--option", "B:two")):
            self.p.ok(*args)
        self.p.ok("answer", "Q1=A")
        self.p.ok("answer", "Q2=A")
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py")

    def test_close_abandon_is_the_way_out_of_an_unanswerable_question(self):
        self.p.ok("ask", "Is this reproducible?", "--option", "A: yes", "--option", "B: no")
        self.assertEqual(self.p.run("close").returncode, 4)
        self.p.ok("close", "--abandon")

    def test_twelve_asks_at_once_all_land(self):
        env = {k: v for k, v in os.environ.items() if k not in state_mod.AGENT_MARKERS}
        env["AI_RUNTIME"] = "claude"
        procs = [subprocess.Popen([sys.executable, "-I", STATE, "--root", self.p.root, "ask", "Question %d?" % i,  # pylint: disable=consider-using-with
                                   "--option", "A: one", "--option", "B: two"], env=env,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(12)]
        for proc in procs:
            proc.wait()
        self.assertEqual(len(self.questions()), 12)
        self.assertEqual(len(self.of("question_asked")), 12)

    def test_ask_takes_ownership_and_reading_does_not(self):
        self.p.ok("ask", "Whose task?", "--option", "A: claude", "--option", "B: codex", runtime="codex")
        self.assertEqual(self.p.state()["owner_runtime"], "codex")
        self.assertEqual(self.of("runtime_handoff")[-1]["data"]["to"], "codex")
        before = self.p.state()["updated_at"]
        self.p.ok("questions")
        self.p.ok("questions", "--pending")
        self.assertEqual(self.p.state()["updated_at"], before)

    def test_ask_ends_an_unattended_turn_with_the_launcher_line(self):
        out = self.p.ok("ask", "Ship it?", "--option", "A: yes", "--option", "B: no", human=True).stdout
        self.assertEqual(out.strip().split("\n")[-1],
                         "WAITING_FOR_ANSWERS .ai/reports/%s/task.md Q1" % self.task_id())
        out = self.p.ok("ask", "Second?", "--option", "A: yes", "--option", "B: no").stdout
        self.assertNotIn("WAITING_FOR_ANSWERS", out)


class TestGate(Ported):
    """R11, R13: approval happens outside the agent, through one of three routes,
    each recorded as what it was."""

    def test_approve_before_a_gate_is_refused(self):
        self.p.start("--mode", "full", "--by", "test")
        done = self.p.run("approve", "--by", "ivan")
        self.assertEqual(done.returncode, 5)
        self.assertIn("APPROVAL_REFUSED — no gate was requested: 'state.py close' requests it for a full-mode task.",
                      done.stderr)

    def test_close_opens_the_gate_and_freezes_the_task(self):
        self.open_gate()
        self.assertRegex(self.qtext(), r"(?m)^## G1\. Approve %s for implementation\? \(gate: human_approval\)$"
                         % re.escape(self.task_id()))
        self.assertIsNotNone(self.approval()["requested_at"])
        requested = self.of("gate_requested")[0]["data"]
        self.assertEqual(requested["gate"], "human_approval")
        self.assertIsNotNone(requested["requested_at"])
        self.assertEqual(self.p.run("verify", "--scope", "suite").returncode, 4)
        self.assertEqual(self.p.run("close").returncode, 4)
        self.assertEqual(len(re.findall(r"(?m)^## G", self.qtext())), 1)

    def test_a_piped_approve_is_refused_and_names_every_route(self):
        self.open_gate()
        with open(os.path.join(self.p.root, ".ai", "state", "current.json"), encoding="utf-8") as fh:
            before = fh.read()
        done = self.p.run("approve", "--by", "ivan")
        self.assertEqual(done.returncode, 5)
        lines = done.stderr.split("\n")
        self.assertEqual(lines[0], "state.py: APPROVAL_REFUSED — approval happens outside the agent. "
                                   "Run in your own terminal:")
        self.assertRegex(lines[1], r"^  python3 '?.*/skills/ai-task/state\.py'? --root '?%s'? approve --by ivan$"
                         % re.escape(self.p.root))
        self.assertIn("set [Answer]: A on G1 in .ai/reports/%s/task.md and tell the session to sync"
                      % self.task_id(), done.stderr)
        self.assertIn("AI_UNATTENDED=1 in the launcher's environment; the journal then records the approval as "
                      "unattended.", done.stderr)
        with open(os.path.join(self.p.root, ".ai", "state", "current.json"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)
        self.assertFalse(self.approval()["granted"])

    def test_the_printed_command_survives_a_space(self):
        self.p.close()
        self.p = Project(name="with space")
        self.open_gate()
        printed = self.p.run("approve", "--by", "the human").stderr.split("\n")[1]
        argv = shlex.split(printed)
        self.assertEqual(argv[argv.index("--root") + 1], self.p.root)
        self.assertEqual(argv[-3:], ["approve", "--by", "the human"])

    def test_a_terminal_inside_an_agent_session_is_not_a_human(self):
        self.open_gate()
        for marker in ("CLAUDECODE=1", "CODEX_THREAD_ID=x"):
            done = self.in_pty("approve", "--by", "ivan", set_env=marker)
            self.assertEqual(done.returncode, 5, marker)
            self.assertIn(marker.split("=")[0], done.stdout)
            self.assertIn("not through the `!` prefix", done.stdout)
            self.assertFalse(self.approval()["granted"])

    def test_a_terminal_is_what_the_gate_is_looking_for(self):
        self.open_gate()
        done = self.in_pty("approve", "--by", "ivan")
        self.assertEqual(done.returncode, 0, done.stdout)
        a = self.approval()
        self.assertEqual((a["granted"], a["via"], a["unattended"]), (True, "terminal", False))
        approved = self.of("gate_approved")
        self.assertEqual([(e["actor"], e["data"]["via"], e["data"]["tty"]) for e in approved],
                         [("human", "terminal", True)])
        self.assertRegex(self.qtext(), r"(?m)^\[Answer\]: A — by ivan via terminal at ")
        self.assertIn("already approved by ivan", self.unattended("approve", "--by", "someone-else").stdout)
        self.assertEqual(len(self.of("gate_approved")), 1)
        self.p.ok("close")                                  # the gate's own question blocks nothing now
        self.assertFalse(self.p.in_flight())

    def test_the_unattended_route_is_allowed_and_never_invisible(self):
        for env in ({"AI_UNATTENDED": "1"}, {"AI_UNATTENDED": "1", "CLAUDECODE": "1"}):
            self.open_gate()
            self.p.ok("approve", "--by", "launcher", runtime=None, env=env)
            a = self.approval()
            self.assertEqual((a["granted"], a["via"], a["unattended"]), (True, "unattended", True), env)
            line = self.of("gate_approved")[-1]
            self.assertEqual((line["actor"], line["data"]["via"], line["data"]["unattended"], line["data"]["tty"]),
                             ("agent", "unattended", True, False))
            self.p.ok("close")

    def test_a_pending_question_comes_first_and_the_gates_own_does_not(self):
        self.open_gate()
        self.assertEqual(self.p.run("approve", "--by", "ivan").returncode, 5)     # past the pending check
        self.p.ok("ask", "Which rule?", "--option", "A: one", "--option", "B: two")
        done = self.p.run("approve", "--by", "ivan")
        self.assertEqual(done.returncode, 4)
        self.assertIn("QUESTIONS_PENDING", done.stderr)

    def test_reject_records_the_refusal_and_consumes_the_request(self):
        self.open_gate()
        self.p.ok("reject", "--by", "ivan", "--why", "the migration has no rollback")
        a = self.approval()
        self.assertEqual((a["granted"], a["requested_at"], a["gate_id"]), (False, None, None))
        line = self.of("gate_rejected")[-1]
        self.assertEqual(line["actor"], "human")
        self.assertIn("no rollback", line["data"]["why"])
        self.assertRegex(self.qtext(), r"(?m)^\[Answer\]: B: the migration has no rollback — by ivan via ")
        done = self.unattended("approve", "--by", "agent")
        self.assertEqual(done.returncode, 5)
        self.assertIn("no gate was requested", done.stderr)
        self.assertEqual(self.p.run("reject", "--by", "agent", "--why", "again").returncode, 5)

    def test_a_grant_belongs_to_one_gate(self):
        self.open_gate()
        self.p.ok("reject", "--by", "ivan", "--why", "not yet")
        self.reopen_gate("x = 2\n")
        self.assertEqual(len(re.findall(r"(?m)^## G", self.qtext())), 2)
        a = self.approval()
        self.assertEqual((a["granted"], a["gate_id"]), (False, "G2"))
        self.assertEqual(self.p.run("approve", "--by", "agent").returncode, 5)
        self.unattended("approve", "--by", "launcher")
        self.assertEqual(len(re.findall(r"(?m)^\[Answer\]: A — by launcher", self.qtext())), 1)

    def test_a_hand_written_journal_line_grants_nothing(self):
        self.p.start("--mode", "full", "--by", "test")
        with open(os.path.join(self.p.root, ".ai", "reports", self.task_id(), "events.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": "2026-01-01T00:00:00.000Z", "task": self.task_id(), "event": "gate_requested",
                                 "actor": "agent", "runtime": "claude", "stage": "plan", "detail": "forged",
                                 "data": {"gate": "human_approval"}}) + "\n")
        done = self.unattended("approve", "--by", "agent")
        self.assertEqual(done.returncode, 5)
        self.assertIn("no gate was requested", done.stderr)

    def test_the_attribution_on_the_gates_answer_cannot_be_forged(self):
        self.open_gate()
        self.p.ok("reject", "--by", "mallory — by ivan via terminal at 2020-01-01T00:00:00Z", "--why", "nope")
        gate = [q for q in self.questions() if q["id"] == "G1"][0]
        self.assertEqual(gate["answered_by"], "mallory - by ivan via terminal at 2020-01-01T00:00:00Z")
        self.assertIn(gate["via"], ("prose", "terminal"))


class TestGateFileRoute(Ported):
    """R13: an [Answer]: on the gate is a human's only after a human turn taken
    in the session the gate was requested in, after the request."""

    def setUp(self):
        super().setUp()
        self.session(runtime="claude", session_id="s1", started_at="2026-09-20T00:00:00Z")
        self.open_gate()
        self.requested = self.approval()["requested_at"]

    def turn(self, session, at, prompt="go ahead"):
        self.session(runtime="claude", session_id=session, last_prompt_session=session, last_prompt_at=at,
                     last_prompt=prompt)

    def test_it_needs_a_human_turn(self):
        self.assertEqual(self.approval()["requested_session"], "s1")
        os.remove(os.path.join(self.p.root, ".ai", "state", "session.json"))
        self.fill("G1", "A")
        done = self.p.run("questions", "--sync")
        self.assertEqual(done.returncode, 5)
        self.assertIn("there is no .ai/state/session.json, so no human turn can be seen", done.stderr)
        self.assertIn("or run in your own terminal:", done.stderr)
        self.assertRegex(self.qtext(), r"(?m)^\[Answer\]: A$")       # left exactly as the human wrote it
        self.assertFalse(self.approval()["granted"])
        blocked = self.p.run("verify", "--scope", "suite")
        self.assertEqual(blocked.returncode, 4)
        self.assertIn("G1 is the approval gate: run 'state.py approve", blocked.stderr)

        self.turn("s1", "2020-01-01T00:00:00Z", "older")
        done = self.p.run("questions", "--sync")
        self.assertEqual(done.returncode, 5)
        self.assertIn("is older than the approval request (%s)" % self.requested, done.stderr)
        self.turn("window-2", self.requested, "whats the weather")
        done = self.p.run("questions", "--sync")
        self.assertEqual(done.returncode, 5)
        self.assertIn("came from another session (window-2, not s1, which is where the gate was requested)",
                      done.stderr)
        self.assertFalse(self.approval()["granted"])

        self.turn("s1", self.requested, "yes, approve it")         # the same second is a turn on the plan
        self.assertRegex(self.p.ok("questions", "--sync", "--by", "ivan").stdout, r"gate approved by .* via the file")
        a = self.approval()
        self.assertEqual((a["granted"], a["via"], a["unattended"]), (True, "file", False))
        line = self.of("gate_approved")[-1]
        self.assertEqual((line["actor"], line["data"]["via"], line["data"]["tty"]), ("human", "file", False))
        self.assertRegex(self.qtext(), r"(?m)^\[Answer\]: A — by .* via file at ")
        self.assertNotIn("gate approved", self.p.ok("questions", "--sync").stdout)
        self.assertEqual(len(self.of("gate_approved")), 1)
        task = self.task_id()
        self.p.ok("close")
        self.assertEqual(self.p.archived(task)["gate"]["via"], "file")

    def test_it_can_reject(self):
        self.fill("G1", "B: the migration has no rollback")
        self.turn("s1", self.requested)
        self.assertRegex(self.p.ok("questions", "--sync").stdout, r"gate rejected by .* via the file")
        a = self.approval()
        self.assertEqual((a["granted"], a["requested_at"]), (False, None))
        line = self.of("gate_rejected")[-1]
        self.assertEqual(line["actor"], "human")
        self.assertIn("no rollback", line["data"]["why"])

    def test_it_can_run_unattended_as_the_agent_it_is(self):
        os.remove(os.path.join(self.p.root, ".ai", "state", "session.json"))
        self.fill("G1", "A")
        self.unattended("questions", "--sync", "--by", "launcher")
        a = self.approval()
        self.assertEqual((a["granted"], a["via"], a["unattended"]), (True, "file", True))
        line = self.of("gate_approved")[-1]
        self.assertEqual((line["actor"], line["data"]["unattended"]), ("agent", True))
        evidence = line["data"].get("evidence") or {}
        self.assertTrue(evidence.get("session") is not None or evidence.get("unattended") is True)

    def test_free_text_on_the_gate_is_not_a_rejection(self):
        self.turn("s1", self.requested)
        self.fill("G1", "yes, go ahead — but check the rollback")
        self.assertIn("is the approval gate: answer it A or B", self.p.ok("questions", "--sync").stderr)
        self.assertIsNotNone(self.approval()["requested_at"])

    def test_a_refused_sync_still_records_the_answers_it_wrote(self):
        self.p.ok("ask", "Second?", "--option", "A: one", "--option", "B: two")
        self.fill("G1", "A")
        self.fill("Q1", "B")
        self.turn("another", self.requested)
        self.assertEqual(self.p.run("questions", "--sync").returncode, 5)
        self.assertNotIn("Q1", self.p.state()["questions"]["pending"])

    def test_it_takes_ownership_like_any_other_change(self):
        self.fill("G1", "A")
        self.turn("s1", self.requested)
        self.p.ok("questions", "--sync", "--by", "ivan", runtime="codex")
        self.assertEqual(self.p.state()["owner_runtime"], "codex")
        self.assertEqual(self.of("runtime_handoff")[-1]["data"]["to"], "codex")

    def test_a_terminal_rejection_beats_a_sync_already_under_way(self):
        state = state_mod.load(self.p.root, claim=False)
        self.turn("s1", self.requested)
        self.fill("G1", "A")

        class Args:                                    # what cmd_questions would pass
            by, sync, pending, topic, format = "the agent", True, False, None, "prose"
        lines, questions = state_mod.parse_questions(self.qpath())
        gates = [q for q in state_mod.sync_answers(self.p.root, state, self.qpath(), lines, questions, Args)
                 if q["kind"] == "G"]
        self.assertTrue(gates)
        self.p.ok("reject", "--by", "ivan", "--why", "no rollback plan")      # in those seconds
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                state_mod.close_gate_from_file(self.p.root, state, gates[0], "the agent")
            except SystemExit:
                pass
        self.assertFalse(self.approval()["granted"])
        self.assertEqual(self.of("gate_approved"), [])
        self.assertEqual(self.of("gate_rejected")[-1]["data"]["by"], "ivan")

    def test_a_gate_opened_with_no_session_cannot_close_from_the_file(self):
        self.p.ok("reject", "--by", "ivan", "--why", "again")
        os.remove(os.path.join(self.p.root, ".ai", "state", "session.json"))
        self.reopen_gate("x = 2\n")
        self.assertIsNone(self.approval()["requested_session"])
        self.fill("G2", "A")
        self.session(runtime="claude", last_prompt_session="s9", last_prompt_at="2099-01-01T00:00:00Z")
        self.p.run("questions", "--sync")
        self.assertFalse(self.approval()["granted"])


class TestHandoffFile(Ported):
    """R6: handoff.md is what a session needs first, in at most thirty lines,
    derived from the state, so nothing about it can fail a command."""

    def handoff_md(self):
        with open(os.path.join(self.p.root, ".ai", "state", "handoff.md"), encoding="utf-8") as fh:
            return fh.read()

    def test_what_it_carries(self):
        self.p.start(files="src/widget.py,src/Payment/Fee.php")
        self.session(runtime="claude", session_id="s", last_prompt_at="2026-09-20T10:11:50Z",
                     last_prompt="make the fee configurable " * 40)
        self.p.ok("ask", "Rounding?", "--option", "A: up", "--option", "B: even")
        out = self.p.ok("handoff", "--print").stdout
        self.assertLessEqual(len(out.splitlines()), 30)
        for part in ("# Handoff — %s (feature, %s)" % (self.task_id(), self.p.state()["mode"]), "Goal: tweak the widget", "Next: ",
                     "Pending questions: Q1 — .ai/reports/%s/task.md" % self.task_id(),
                     "## Decisions (latest 3)", "## Rejected (latest 3)", "## Failed attempts (latest 3)",
                     "## Latest user instruction (verbatim,"):
            self.assertIn(part, out)
        prompt = "".join(line for line in out.splitlines() if line.startswith("> "))
        self.assertTrue(100 <= len(prompt) <= 305, len(prompt))
        self.assertIn("← resume point (step task: src/widget.py, src/Payment/Fee.php", out)
        self.assertEqual(self.p.state()["resume_point"]["runtime"], "claude")

    def test_it_is_a_file_rewritten_by_the_commands_that_move_the_task(self):
        self.p.start()
        self.p.ok("ask", "Which rule?", "--option", "A: one", "--option", "B: two")
        self.assertRegex(self.handoff_md(), r"(?m)^Pending questions: Q1 — ")
        self.p.ok("answer", "Q1=A")
        self.assertRegex(self.handoff_md(), r"(?m)^Pending questions: none$")
        self.assertTrue(self.handoff_md().split("\n")[0].endswith(" (stage)"))
        self.p.ok("handoff")
        self.assertTrue(self.handoff_md().split("\n")[0].endswith(" (manual)"))
        self.p.ok("handoff", "--reason", "precompact")
        self.assertTrue(self.handoff_md().split("\n")[0].endswith(" (precompact)"))
        line = self.of("handoff_written")[-1]
        self.assertEqual(line["data"]["reason"], "precompact")
        self.assertGreater(line["data"]["lines"], 10)
        self.assertEqual(self.p.state()["handoff"]["file"], ".ai/state/handoff.md")
        before = self.p.state()["updated_at"]
        self.p.ok("handoff", "--reason", "precompact")
        self.assertEqual(self.p.state()["updated_at"], before)        # handoff alone never writes current.json
        render = lambda: self.p.ok("handoff", "--print").stdout.split("\n")[1:]   # noqa: E731
        self.assertEqual(render(), render())

    def test_what_it_says_when_there_is_nothing_to_say(self):
        self.p.start()
        out = self.p.ok("handoff", "--print").stdout
        self.assertEqual(out.count("\n- none\n"), 3)
        self.assertEqual(out.rstrip().split("\n")[-1], "> none recorded")
        out = self.p.ok("handoff", "--print", env={"AI_HANDOFF_NO_PROMPT": "1"}).stdout
        self.assertIn("omitted (AI_HANDOFF_NO_PROMPT=1)", out.rstrip().split("\n")[-1])
        self.assertIn("--to", self.p.ok("handoff", "--help").stdout)

    def test_close_takes_it_away_and_a_new_task_rewrites_it(self):
        self.p.start()
        self.p.ok("close", "--abandon")
        self.assertFalse(os.path.exists(os.path.join(self.p.root, ".ai", "state", "handoff.md")))
        self.p.ok("start", "--goal", "task B about search", "--workflow", "feature", "--files", "src/widget.py", *ZERO)
        self.assertIn("task B about search", self.handoff_md())

    def test_nothing_about_it_can_fail_a_command(self):
        self.p.start()
        self.session(runtime="claude", last_prompt=12345, last_prompt_at=42)
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_widget.py")
        self.assertEqual(self.p.ok("handoff", "--print").stdout.rstrip().split("\n")[-1], "> 12345")
        self.p.ok("event", "note", "--data", '{"kind":"decision","text":{"nested":1}}')
        with open(os.path.join(self.p.root, ".ai", "reports", self.task_id(), "events.jsonl"), "a",
                  encoding="utf-8") as fh:
            fh.write("not json at all\n")
        self.p.ok("ask", "q", "--option", "A: a", "--option", "B: b")
        handoff = os.path.join(self.p.root, ".ai", "state", "handoff.md")
        os.remove(handoff)
        os.makedirs(handoff)                                    # unwritable: best effort
        self.p.ok("answer", "Q1=A")
        self.assertEqual(self.p.state()["questions"]["pending"], [])


class TestWP5(Ported):
    """WP5: handoff --to moves a task on purpose; exit 7 until the other runtime
    resumes it; the advisory line names the preferred runtime."""

    def setUp(self):
        super().setUp()
        homes = os.path.join(self.p.tmp.name, "homes")
        self.homes = {"CLAUDE_CONFIG_DIR": os.path.join(homes, "claude"), "CODEX_HOME": os.path.join(homes, "codex")}
        resolve = os.path.join(ROOT, "scripts", "resolve-profile.py")
        for home, plan in ((self.homes["CLAUDE_CONFIG_DIR"], ["max", "--fable", "yes"]),
                           (self.homes["CODEX_HOME"], ["codex-pro", "--fable", "no"])):
            os.makedirs(os.path.join(home, "skills", "ai-task"))
            os.makedirs(os.path.join(home, "claude-agentic"))
            open(os.path.join(home, "skills", "ai-task", "state.py"), "w", encoding="utf-8").close()  # pylint: disable=consider-using-with
            profile = subprocess.run([sys.executable, resolve] + plan + ["--print", "agentic"], capture_output=True,
                                     text=True, check=True).stdout
            with open(os.path.join(home, "claude-agentic", "profile.json"), "w", encoding="utf-8") as fh:
                fh.write(profile)

    def s(self, runtime, *args, env=None):
        merged = dict(self.homes)
        merged.update(env or {})
        return self.p.run("--runtime", runtime, *args, runtime=None, env=merged)

    def start5(self, workflow="feature"):
        return self.s("claude", "start", "--goal", "move it", "--workflow", workflow, "--files", "src/widget.py", *ZERO)

    def test_handoff_to_and_exit_7(self):
        self.assertEqual(self.start5().returncode, 0)
        done = self.s("claude", "handoff", "--to", "codex", "--why", "claude quota")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertRegex(done.stdout, r"Handed .* to codex \(manual\)")
        self.assertRegex(done.stdout, r"headless \(not run\): cd .* && codex exec '/ai-task'")
        s = self.p.state()
        self.assertEqual((s["owner_runtime"], s["resume_point"]["runtime"], s["handoff"]["pending_to"]),
                         ("codex", "codex", "codex"))
        line = self.of("runtime_handoff")[-1]
        self.assertEqual((line["data"]["from"], line["data"]["to"], line["data"]["via"], line["data"]["tty"],
                          line["data"]["reason"], line["actor"]),
                         ("claude", "codex", "manual", False, "claude quota", "agent"))
        with open(os.path.join(self.p.root, ".ai", "state", "handoff.md"), encoding="utf-8") as fh:
            self.assertRegex(fh.read(), r"(?m)^Handed to codex at .* resume there with /ai-task")
        self.assertEqual(self.s("claude", "handoff", "--to", "codex").returncode, 2)
        ask = ("ask", "q", "--option", "A: a", "--option", "B: b")
        refused = self.s("claude", *ask)
        self.assertEqual(refused.returncode, 7)
        self.assertTrue(refused.stderr.startswith("state.py: RUNTIME_HANDOFF_PENDING"))
        self.assertEqual(self.s("claude", "status").returncode, 0)         # a read is fine
        moved = len(self.of("runtime_handoff"))
        self.assertEqual(self.s("codex", *ask).returncode, 0)
        self.assertIsNone(self.p.state()["handoff"]["pending_to"])
        self.assertEqual(len(self.of("runtime_handoff")), moved)          # no second event on resume
        self.assertEqual(self.s("codex", "handoff", "--to", "claude", "--why", "back").returncode, 0)
        self.assertEqual(self.s("claude", *ask).returncode, 0)
        self.assertEqual(self.p.state()["owner_runtime"], "claude")
        self.assertEqual(self.s("claude", "handoff", "--to", "codex").returncode, 0)   # pending questions do not block
        shell = self.p.run("ask", "q", "--option", "A: a", "--option", "B: b", runtime=None,
                           env=dict(self.homes, AI_RUNTIME=""))
        self.assertEqual(shell.returncode, 7)
        self.assertIn("--runtime claude handoff --to claude", shell.stderr)

    def test_a_runtime_that_is_not_installed_is_refused(self):
        self.start5()
        done = self.s("claude", "handoff", "--to", "codex", env={"CODEX_HOME": os.path.join(self.p.tmp.name, "nowhere")})
        self.assertEqual(done.returncode, 2)
        self.assertIn("not installed", done.stderr)

    def test_a_self_handoff_on_an_unowned_task_is_refused(self):
        self.start5()
        s = self.p.state()
        s["owner_runtime"] = None
        self.p.write(".ai/state/current.json", json.dumps(s))
        self.assertEqual(self.s("claude", "handoff", "--to", "claude").returncode, 2)
        self.assertIsNone(self.p.state()["handoff"]["pending_to"])

    def test_a_review_handoff_below_the_threshold_is_noted_not_recorded(self):
        self.start5()
        done = self.s("claude", "handoff", "--to", "codex", "--for", "review")
        self.assertEqual(done.returncode, 0)
        self.assertIn("below cross_vendor_review_from", done.stdout)
        self.assertIsNone(self.p.state()["cross_vendor_review"])

    def test_the_advisory_line(self):
        done = self.start5("refactoring")
        self.assertIn("preferred runtime: codex (plan table: refactoring -> codex)", done.stderr.split("\n"))
        with open(os.path.join(self.p.root, ".ai", "state", "handoff.md"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("preferred runtime: codex (plan table: refactoring -> codex)", text.split("\n"))
        self.assertLessEqual(len(text.splitlines()), 30)
        self.assertEqual(self.p.state()["owner_runtime"], "claude")       # nothing moves by itself

    def test_no_advice_when_the_other_runtime_is_not_installed(self):
        done = self.s("claude", "start", "--goal", "g", "--workflow", "refactoring", "--files", "src/widget.py", *ZERO,
                      env={"CODEX_HOME": os.path.join(self.p.tmp.name, "nowhere")})
        self.assertNotIn("preferred runtime", done.stderr)

    def test_quota_advice(self):
        now = int(time.time())
        gate = os.path.join(self.homes["CLAUDE_CONFIG_DIR"], "state")
        os.makedirs(gate)
        with open(os.path.join(gate, "runtime-gate.json"), "w", encoding="utf-8") as fh:
            json.dump({"quota": {"weekly_pct": 95, "seen_at": now, "resets_at": now + 3600, "source": "statusline"}}, fh)
        self.assertIn("preferred runtime: codex (quota 95% >= 90%)", self.start5().stderr.split("\n"))


class TestSensorsSurface(unittest.TestCase):
    """R6: sensors.py is the tree snapshot and diff and the command runner; the
    budget, the re-score and the static sensors are gone."""

    def test_only_the_diff_and_the_runner_are_left(self):
        for name in ("snapshot_tree", "diff_files", "numstat", "run_command", "command_for", "expand_files",
                     "scope_any"):
            self.assertTrue(callable(getattr(sensors, name, None)), name)
        for name in ("measure", "rescore", "check", "bite", "detect", "sensor_duplicates",
                     "sensor_traceability", "sensor_plan_sections", "load_policy", "run_at_base"):
            self.assertFalse(hasattr(sensors, name), name)
        commands = sensors.build_parser()._subparsers._group_actions[0].choices  # pylint: disable=protected-access
        self.assertEqual(sorted(commands), ["diff", "run", "snapshot"])


class TestNoTask(unittest.TestCase):
    """What needs no task: the failure modes that must be loud rather than
    silent, and topic questions, which live with a document and need no .ai/."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # tearDown ends it
        self.root = os.path.join(self.tmp.name, "project")
        os.makedirs(os.path.join(self.root, ".ai", "state"))
        os.makedirs(os.path.join(self.root, ".ai", "reports"))
        self.topic = os.path.join(self.tmp.name, "topic")
        os.makedirs(os.path.join(self.topic, "docs", "sdlc", "intent"))

    def tearDown(self):
        self.tmp.cleanup()

    def run_state(self, root, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDECODE", "AI_RUNTIME")}
        env["CLAUDE_CONFIG_DIR"] = os.path.join(self.tmp.name, "home", ".claude")
        env["CODEX_HOME"] = os.path.join(self.tmp.name, "home", ".codex")
        done = subprocess.run([sys.executable, "-I", STATE, "--root", root] + list(args), input="",
                              capture_output=True, text=True, env=env, check=False)
        return done.stdout + done.stderr

    def topic_ok(self, *args):
        out = self.run_state(self.topic, *args)
        self.assertNotIn("Traceback", out)
        return out

    def test_a_corrupt_state_file_is_loud_and_untouched(self):
        path = os.path.join(self.root, ".ai", "state", "current.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json at all")
        self.assertIn("unreadable", self.run_state(self.root, "status"),
                      "a corrupt state file reports the problem")
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "not json at all", "and is left exactly as it was")

    def test_no_ai_at_all(self):
        self.assertIn("run /ai-init first", self.run_state(self.tmp.name, "status"),
                      "a project without .ai/ says what to do")

    def test_topic_questions_live_with_the_document(self):
        """R17: topic questions need no .ai/."""
        self.topic_ok("ask", "What problem are we solving?", "--option", "A: decisions are lost",
                      "--option", "B: cost", "--topic", "my-idea")
        self.assertTrue(os.path.isfile(os.path.join(self.topic, "docs", "sdlc", "intent", "my-idea.questions.md")),
                        "a topic question lands beside its intent")
        self.topic_ok("answer", "Q1=A", "--topic", "my-idea", "--by", "ivan")
        md = self.topic_ok("questions", "--topic", "my-idea", "--format", "md")
        self.assertRegex(md, r"(?m)^- \*\*What problem are we solving\?\*\* — decisions are lost",
                         "--format md renders the Decisions taken line")
        self.assertFalse(os.path.isdir(os.path.join(self.topic, ".ai")), "and no .ai/ was created")
        found = [os.path.join(d, n) for d, dirs, files in os.walk(self.topic) for n in dirs + files
                 if n in ("events.jsonl", ".ai")]
        self.assertEqual(found, [], "a topic question writes no journal anywhere in the tree")

    def test_a_topic_slug_that_is_a_path_is_refused(self):
        out = self.run_state(self.topic, "ask", "Escape?", "--option", "A: one", "--option", "B: two",
                             "--topic", "../../pwned/evil")
        self.assertIn("takes a slug of lowercase letters", out, "a slug that is a path is refused")
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, "pwned"))
                         or os.path.exists(os.path.join(self.topic, "docs", "pwned")),
                         "and nothing was written outside docs/sdlc/intent/")

    def test_a_topic_file_cannot_hold_a_gate(self):
        out = self.run_state(self.topic, "ask", "Gate?", "--option", "A: one", "--option", "B: two",
                             "--gate", "human_approval", "--topic", "my-idea")
        self.assertIn("a gate is requested by", out, "a topic file cannot hold a gate either")


if __name__ == "__main__":
    unittest.main()
