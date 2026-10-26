"""state.py's schema-7 surface (redesign 2.2a): start, verify, review, close,
step-done, status, approve --confirm, task.md, and the re-score.

Every project here is a scratch git repository in a temp directory. The suite's
red/green switch is a flag file outside the repository, so flipping it never
changes the tree the two facts are measured on.
"""
import json
import shutil
import os
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

ZERO = ["--declare", "behaviour=0:synthetic", "--declare", "domain=0:synthetic",
        "--declare", "novelty=0:synthetic"]
HEADINGS = ["## Weight", "## Plan", "## Questions", "## Verify", "## Review", "## Changes", "## Verdict"]
CLEAN = "FINDINGS\nnone\n"
FINDINGS = "FINDINGS\n[HIGH] H1 the cache key ignores the locale\nin_scope: yes\n[LOW] L1 naming\nVERDICT pass_with_findings\n"


class Project:
    """A scratch project with .ai/, a testing.md whose commands read flag files,
    one code file and its test, committed."""

    def __init__(self, files=None):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with  # close() ends it
        self.root = os.path.join(self.tmp.name, "p")
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

    def run(self, *args, runtime="claude", human=False, stdin=None):
        env = {k: v for k, v in os.environ.items()
               if k not in state_mod.AGENT_MARKERS and k not in ("AI_UNATTENDED", "AI_RUNTIME")}
        env["AI_RUNTIME"] = runtime
        if human:
            env["AI_UNATTENDED"] = "1"
        return subprocess.run([sys.executable, "-I", STATE, "--root", self.root] + list(args),
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

    def test_second_start_is_refused(self):
        self.p.start()
        done = self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", "src/widget.py")
        self.assertEqual(done.returncode, 1)
        self.assertIn("in flight", done.stderr)

    def test_old_and_new_surfaces_refuse_each_other(self):
        self.p.start()
        done = self.p.run("test-run", "--scope", "suite")
        self.assertEqual(done.returncode, 1)
        self.assertIn("schema-7 surface", done.stderr)

    def test_an_old_task_keeps_the_old_close(self):
        self.p.ok("quick", "--goal", "g", "--workflow", "feature", "--tier", "T2", "--files", "src/widget.py")
        done = self.p.run("verify", "--scope", "suite")
        self.assertEqual(done.returncode, 1)
        self.assertIn("old surface", done.stderr)
        self.assertNotIn("schema", self.p.state())
        # close reaches today's cmd_close: nothing done yet, so it closes the record.
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())


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

    def test_status(self):
        self.assertIn("task: none", self.p.ok("status").stdout)
        self.p.start()
        out = self.p.ok("status").stdout.strip().split("\n")
        self.assertLessEqual(len(out), 20)
        self.assertTrue(any(line.startswith("mode: light") for line in out))
        data = json.loads(self.p.ok("status", "--json").stdout)
        self.assertEqual((data["schema"], data["mode"]), (7, "light"))
        self.assertFalse(data["facts"]["a"][0])
        # /status hands a schema-7 task to state.py status.
        status_py = os.path.join(ROOT, "skills", "status", "status.py")
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
        qpath = os.path.join(self.p.root, ".ai", "reports", self.task_id(), "questions.md")
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
    """state.rescore and sensors.diff_files: reversibility and domain from the
    diff, only upward."""

    def setUp(self):
        self.policy = weight.load_policy("/nonexistent")[0]
        self.p = Project({"db/migrations/0001_init.sql": "CREATE TABLE users (id int);\nDROP TABLE old;\n"})
        self.base = git_tree(self.p.root)

    def tearDown(self):
        self.p.close()

    def rescore(self, files, current=None):
        return state_mod.rescore(self.p.root, self.base, files, current or dict.fromkeys(weight.AXES, 0),
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


if __name__ == "__main__":
    unittest.main()
