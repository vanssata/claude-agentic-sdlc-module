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
# The default entry: state.py imported from its cached bytecode, about half the
# start-up of running it as a script; state_py=STATE keeps the script entry.
SHIM = "import sys; sys.argv[0] = %r; sys.path.insert(0, %r); import state; state.main()" % (
    STATE, os.path.dirname(STATE))

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

    def run(self, *args, runtime="claude", human=False, stdin=None, env=None, state_py=None):
        """runtime=None leaves AI_RUNTIME unset, so detection decides; env adds
        variables after the agent markers are removed; state_py=None runs SHIM."""
        base = {k: v for k, v in os.environ.items()
                if k not in state_mod.AGENT_MARKERS and k not in ("AI_UNATTENDED", "AI_RUNTIME",
                                                                   "AI_HANDOFF_NO_PROMPT")}
        if runtime:
            base["AI_RUNTIME"] = runtime
        if human:
            base["AI_UNATTENDED"] = "1"
        base.update(env or {})
        env = base
        entry = ["-c", SHIM] if state_py is None else [state_py]
        return subprocess.run([sys.executable, "-I"] + entry + ["--root", self.root] + list(args),
                              input=stdin if stdin is not None else "", capture_output=True, text=True,
                              env=env, check=False)

    def ok(self, *args, **kwargs):
        done = self.run(*args, **kwargs)
        assert done.returncode == 0, (args, done.returncode, done.stdout, done.stderr)
        return done

    def start(self, *extra, files="src/widget.py", **kwargs):
        return self.ok("start", "--goal", "tweak the widget", "--workflow", "feature", "--files", files,
                       "--tests", "tests/test_widget.py", *ZERO, *extra, **kwargs)

    def state_file(self):
        """The file the task sits in: state.json, or a legacy current.json."""
        new = os.path.join(self.root, ".ai", "state", "state.json")
        return new if os.path.exists(new) else os.path.join(self.root, ".ai", "state", "current.json")

    def state(self):
        with open(self.state_file(), encoding="utf-8") as fh:
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
        return os.path.exists(self.state_file())

    def close(self):
        self.tmp.cleanup()


DIALOG_SESSION = "sess-7c"
DIALOG_ON = json.dumps({"version": 1, "enabled": True, "window_seconds": 120, "stop_blocks_max": 2})


def stamp(at=None):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() if at is None else at))


class DialogProject(Project):
    """A Project with the dialog on (R36): the test writes dialog.json itself —
    the template lands in 7f (D4) — a plan profile whose dialog tool is
    AskUserQuestion, and the agent session a pick is bound to. pick() and
    append() stand in for the recorder hook of 7d1."""

    def __init__(self, files=None, name="p", on=True):
        files = dict(files or {})
        if on:
            files[".ai/policies/dialog.json"] = DIALOG_ON
        super().__init__(files, name)
        # The labels name the repository's git user as --by: fixed here, so a
        # golden does not depend on the machine's global config.
        subprocess.run(["git", "-C", self.root, "config", "user.name", "Rita Human"], check=True)
        self.home = os.path.join(self.tmp.name, "home")
        self.profile({"plan": "max", "profile": "max", "dialog": {"tool": "AskUserQuestion"}})
        self.picks = 0

    def profile(self, data):
        os.makedirs(os.path.join(self.home, "riskrails"), exist_ok=True)
        with open(os.path.join(self.home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def run(self, *args, env=None, **kwargs):  # pylint: disable=arguments-differ
        base = {"CLAUDECODE": "1", "CLAUDE_CODE_SESSION_ID": DIALOG_SESSION, "CLAUDE_CONFIG_DIR": self.home,
                "CLAUDE_CODE_SESSION_ATTENDED": "1"}
        base.update(env or {})
        return super().run(*args, env=base, **kwargs)

    def decisions(self):
        path = os.path.join(self.root, ".ai", "state", "decision.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)["open"]

    def ledger(self):
        path = os.path.join(self.root, ".ai", "state", "consent.jsonl")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def append(self, **line):
        line = dict({"v": 1}, **line)
        line.setdefault("at", stamp())
        os.makedirs(os.path.join(self.root, ".ai", "state"), exist_ok=True)
        with open(os.path.join(self.root, ".ai", "state", "consent.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")

    def pick(self, decision_id, option, order=1, session=DIALOG_SESSION, ago=0, window=120, tool_use_id=None,
             transcript=""):
        """The line the recorder writes when the human picks `option` of a decision;
        one tool_use_id is one dialog call, so a multi-pick passes the same one."""
        decision = next(d for d in self.decisions() if d["id"] == decision_id)
        label = next(o["label"] for o in decision["options"] if o["n"] == option)
        self.picks += 1
        cid, at = "C%d" % self.picks, time.time() - ago
        self.append(type="pick", id=cid, decision=decision_id, option=option, order=order, label=label,
                    session=session, tool_use_id=tool_use_id or "toolu_%s" % cid, transcript=transcript,
                    runtime="claude", at=stamp(at), expires_at=stamp(at + window))
        return cid


class Base(unittest.TestCase):
    def setUp(self):
        self.p = Project()

    def tearDown(self):
        self.p.close()

    def task_id(self):
        return self.p.state()["task_id"]


class TestStart(Base):
    def test_start_writes_schema_7_and_arms_the_scope_guard(self):
        out = self.p.start(state_py=STATE).stdout
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

    def test_start_writes_state_json_and_resumes_a_legacy_task_in_place(self):
        """R34's contract half: a task starts in state.json; one a version before
        left in current.json is read and saved where it is."""
        self.p.start()
        task = self.task_id()
        new = os.path.join(self.p.root, ".ai", "state", "state.json")
        legacy = os.path.join(self.p.root, ".ai", "state", "current.json")
        self.assertTrue(os.path.exists(new) and not os.path.exists(legacy), "start writes state.json")
        self.p.write("src/other.py", "y = 1\n")
        self.p.ok("start", "--amend", "--files", "+src/other.py", "--why", "a save")
        self.assertFalse(os.path.exists(legacy), "a save creates no second file")
        os.rename(new, legacy)
        self.assertIn(task, self.p.ok("status").stdout)
        self.p.write("src/third.py", "z = 1\n")
        self.p.ok("start", "--amend", "--files", "+src/third.py", "--why", "a save")
        self.assertTrue(os.path.exists(legacy) and not os.path.exists(new), "current.json is saved where it is")
        with open(legacy, encoding="utf-8") as fh:
            self.assertIn("src/third.py", json.load(fh)["files"])

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

    def documents_project(self):
        """A scratch project whose own table has the `documents` key, and a task over README.md alone."""
        with open(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies", "weight.json"),
                  encoding="utf-8") as fh:
            table = json.load(fh)
        table["documents"] = {"globs": ["**/*.md"], "except": ["skills/**", "hooks/**"]}
        p = Project(files={".ai/policies/weight.json": json.dumps(table), "README.md": "# r\n"})
        self.addCleanup(p.close)
        p.ok("start", "--goal", "fix a typo", "--workflow", "feature", "--files", "README.md",
             "--tests", "tests/test_widget.py")
        s = p.state()
        self.assertEqual((s["mode"], s["weight"]["w"], s["weight"]["documents_only"]["zeroed"]),
                         ("light", 0, {"behaviour": 1, "domain": 1, "novelty": 1}))
        p.ok("start", "--amend", "--files", "+src/widget.py", "--why", "the typo is in a docstring")
        p.write("src/widget.py", "x = 2\n")
        return p

    def test_a_non_document_after_amend_raises_the_zeroed_axes(self):
        # R13: start --amend does not re-weigh; verify restores what the documents rule zeroed.
        p = self.documents_project()
        out = p.ok("verify", "--scope", "all").stdout
        for axis in ("behaviour", "domain", "novelty"):
            self.assertIn("re-score: %s 0 → 1" % axis, out)
        self.assertIn("a non-document changed (src/widget.py)", out)
        s = p.state()
        self.assertEqual((s["mode"], s["weight"]["w"]), ("guarded", 3))
        raised = [e["data"] for e in p.events(s["task_id"]) if e["event"] == "weight_raised"]
        self.assertEqual([(r["axis"], r["mode_to"]) for r in raised],
                         [(a, "guarded") for a in ("behaviour", "domain", "novelty")])
        self.assertIn("a non-document changed (src/widget.py)", raised[0]["evidence"])

    def test_a_non_document_after_amend_raises_the_zeroed_axes_at_close(self):
        # The same raise when only close sees the diff: it re-scores before it names what is owed.
        p = self.documents_project()
        done = p.run("close")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn("re-score: behaviour 0 → 1", done.stdout)
        self.assertIn("a non-document changed (src/widget.py)", done.stdout)
        s = p.state()
        self.assertEqual((s["mode"], s["weight"]["w"]), ("guarded", 3))
        self.assertEqual(len([e for e in p.events(s["task_id"]) if e["event"] == "weight_raised"]), 3)

    def test_documents_only_still_light_when_only_documents_changed(self):
        with open(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies", "weight.json"),
                  encoding="utf-8") as fh:
            table = json.load(fh)
        table["documents"] = {"globs": ["**/*.md"], "except": []}
        p = Project(files={".ai/policies/weight.json": json.dumps(table), "README.md": "# r\n"})
        self.addCleanup(p.close)
        p.ok("start", "--goal", "fix a typo", "--workflow", "feature", "--files", "README.md",
             "--tests", "tests/test_widget.py")
        p.write("README.md", "# r2\n")
        self.assertNotIn("re-score", p.ok("verify", "--scope", "all").stdout)
        self.assertEqual(p.state()["mode"], "light")

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
        state_file = self.p.state_file()
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
        with open(self.p.state_file(), encoding="utf-8") as fh:
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
        with open(self.p.state_file(), encoding="utf-8") as fh:
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
        self.assertEqual(self.p.state()["updated_at"], before)        # handoff alone never writes the state file
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
            os.makedirs(os.path.join(home, "riskrails"))
            open(os.path.join(home, "skills", "ai-task", "state.py"), "w", encoding="utf-8").close()  # pylint: disable=consider-using-with
            profile = subprocess.run([sys.executable, resolve] + plan + ["--print", "agentic"], capture_output=True,
                                     text=True, check=True).stdout
            with open(os.path.join(home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
                fh.write(profile)

    def s(self, runtime, *args, env=None):
        merged = dict(self.homes)
        merged.update(env or {})
        return self.p.run("--runtime", runtime, *args, runtime=None, env=merged)

    def start5(self, workflow="feature"):
        return self.s("claude", "start", "--goal", "move it", "--workflow", workflow, "--files", "src/widget.py", *ZERO)

    def test_profile_from_a_home_installed_before_3_4b(self):
        # Review M2: a skills tree updated without install.sh still finds its plan under claude-agentic/.
        home = self.homes["CLAUDE_CONFIG_DIR"]
        os.rename(os.path.join(home, "riskrails"), os.path.join(home, "claude-agentic"))
        got = self.s("claude", "profile", "--tier", "STRONG")
        self.assertEqual((got.returncode, got.stdout.strip()), (0, "opus"), got.stderr)

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


# ---------------------------------------------------------------------------
# R36 step 7c: decisions, the consent ledger, the dialog route.

class DialogBase(unittest.TestCase):
    def setUp(self):
        self.p = DialogProject()

    def tearDown(self):
        self.p.close()

    def commit(self, *commands, **kwargs):
        args = ["decision", "open", "--kind", "commit"]
        for command in commands:
            args += ["--command", command]
        return self.p.run(*args, **kwargs)

    def payload(self, done):
        """The dialog JSON an opener printed under its DIALOG_PENDING line."""
        lines = done.stdout.split("\n")
        at = next(i for i, line in enumerate(lines) if line.startswith("DIALOG_PENDING "))
        return json.loads(lines[at + 1])

    def journal(self, event):
        return [e for e in self.p.events(self.p.state()["task_id"]) if e["event"] == event]

    def in_pty(self, *args):
        markers = ",".join(list(state_mod.AGENT_MARKERS) + ["AI_RUNTIME", "AI_UNATTENDED"])
        return subprocess.run([sys.executable, "-c", PTY_RUN, STATE, self.p.root, markers, ""] + list(args),
                              capture_output=True, text=True, check=False)


class TestDialogDecisions(DialogBase):
    """R36.3, R36.4, R36.14, R36.15, R36.24: state.py alone prepares a decision;
    the ledger's lines settle it and are mirrored into the journal."""

    def test_decision_is_the_opening_sessions(self):
        """Q1 of T-2026-10-28-010: a decision records the session and runtime
        that opened it; `decision show` is that session's."""
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        [opened] = self.p.decisions()
        self.assertEqual((opened["session"], opened["runtime"]), (DIALOG_SESSION, "claude"))
        self.assertIn("git commit -m x", self.p.ok("decision", "show").stdout)
        other = self.p.run("decision", "show", env={"CLAUDE_CODE_SESSION_ID": "another"})
        self.assertEqual(other.returncode, 1, other.stdout)
        self.assertIn("no open decision", other.stderr)

    def test_switch_off_falls_back(self):
        """R36.15: when the project turns the dialog off, an open decision falls
        back to the terminal route on the next run, journaled."""
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        os.remove(os.path.join(self.p.root, ".ai", "policies", "dialog.json"))
        self.p.run("decision", "show")
        self.assertEqual(self.p.decisions(), [])
        self.assertEqual([(e["type"], e.get("effect")) for e in self.p.ledger()], [("settle", "fallback")])

    def test_decision_open_commit_validates_labels(self):
        for bad in ("git commit -m x; rm -rf ~", "git commit -m \"$(id)\"", "git commit -m a | tee x",
                    "git commit -m 'two\nlines'", "git commit -m a && git push origin main",
                    "git push --force origin main", "git push origin", "ls -la"):
            with self.subTest(label=bad):
                done = self.commit(bad)
                self.assertEqual(done.returncode, 6, done.stderr)
                self.assertIn("CONSENT_LABEL_INVALID", done.stderr)
        self.assertEqual(self.p.decisions(), [])
        other = self.p.run("decision", "open", "--kind", "approval", "--command", "git commit -m x")
        self.assertEqual(other.returncode, 1)
        self.assertIn("takes --kind commit", other.stderr)
        done = self.commit("git commit -m 'fix it' -- src/widget.py")
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("DIALOG_PENDING D1 "), done.stdout)
        [question] = self.payload(done)["questions"]
        self.assertEqual((question["header"], question["multiSelect"]), ("Commit", False))
        self.assertEqual([o["label"] for o in question["options"]],
                         ["Not now — commit nothing", "git commit -m 'fix it' -- src/widget.py"])
        [decision] = self.p.decisions()
        self.assertEqual((decision["id"], decision["kind"], decision["opened_by"]), ("D1", "commit", "decision open"))
        self.assertLessEqual(len(decision["question"]), 1200)

    def test_the_switch_is_off_unless_everything_holds(self):
        rows = {"no session id": {"CLAUDE_CODE_SESSION_ID": ""},
                "unattended runtime": {"CLAUDE_CODE_SESSION_ATTENDED": "0"},
                "AI_UNATTENDED": {"AI_UNATTENDED": "1"}}
        for name, env in rows.items():
            with self.subTest(row=name):
                done = self.commit("git commit -m x", env=env)
                self.assertEqual(done.returncode, 1)
                self.assertIn("the dialog is off here", done.stderr)
        self.p.profile({"plan": "max", "dialog": {"tool": None}})
        self.assertIn("the dialog is off here", self.commit("git commit -m x").stderr)
        self.p.profile({"plan": "max", "dialog": {"tool": "AskUserQuestion"}})
        self.p.write(".ai/policies/dialog.json", json.dumps({"version": 1, "enabled": False}))
        self.assertIn("the dialog is off here", self.commit("git commit -m x").stderr)
        os.remove(os.path.join(self.p.root, ".ai", "policies", "dialog.json"))
        self.assertIn("the dialog is off here", self.commit("git commit -m x").stderr)
        self.assertEqual(self.p.decisions(), [])

    def test_two_opens_do_not_clobber(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m one")
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m two")
        self.assertEqual([d["id"] for d in self.p.decisions()], ["D1", "D2"])
        shown = json.loads(self.p.ok("decision", "show", "--json").stdout)
        self.assertEqual([q["options"][1]["label"] for q in shown["questions"]],
                         ["git commit -m one", "git commit -m two"])
        only = json.loads(self.p.ok("decision", "show", "--id", "D2", "--json").stdout)
        self.assertEqual(len(only["questions"]), 1)

    def test_four_open_max(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m a",
                  "--command", "git push origin main")
        for n in range(3):
            self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m n%d" % n)
        done = self.commit("git commit -m five")
        self.assertEqual(done.returncode, 6)
        self.assertIn("DECISION_LIMIT", done.stderr)
        self.assertEqual(len(json.loads(self.p.ok("decision", "show", "--json").stdout)["questions"]), 4)

    def test_show_with_nothing_open(self):
        done = self.p.run("decision", "show")
        self.assertEqual(done.returncode, 1)
        self.assertIn("no open decision", done.stderr)

    def test_decision_settle_choice(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        refused = self.p.run("decision", "settle", "--id", "D1")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("nothing is recorded for D1", refused.stderr)
        cid = self.p.pick("D1", 1)
        out = self.p.ok("decision", "settle", "--id", "D1").stdout
        self.assertIn("D1 settled: Not now — commit nothing (defer)", out)
        self.assertEqual(self.p.decisions(), [])
        settle = self.p.ledger()[-1]
        self.assertEqual((settle["type"], settle["decision"], settle["pick"], settle["effect"]),
                         ("settle", "D1", cid, "defer"))
        self.assertFalse(os.path.exists(os.path.join(self.p.root, ".ai", "state", "decision.json")))

    def test_a_decline_settles_as_declined(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.p.append(type="decline", decision="D1", why="other_text")
        self.assertIn("declined", self.p.ok("decision", "settle", "--id", "D1").stdout)
        self.assertEqual(self.p.ledger()[-1]["effect"], "declined")

    def test_a_live_command_pick_is_run_not_settled(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.p.pick("D1", 2)
        done = self.p.run("decision", "settle", "--id", "D1")
        self.assertEqual(done.returncode, 1)
        self.assertIn("has a live pick: run it verbatim", done.stderr)
        self.assertIn("git commit -m x", done.stderr)

    def test_settle_pick_needs_terminal(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        done = self.p.run("decision", "settle", "--id", "D1", "--pick", "1")
        self.assertEqual(done.returncode, 5)
        self.assertIn("APPROVAL_REFUSED", done.stderr)
        command = self.in_pty("decision", "settle", "--id", "D1", "--pick", "2")
        self.assertEqual(command.returncode, 1, command.stdout)
        self.assertIn("run it in this terminal instead", command.stdout)
        human = self.in_pty("decision", "settle", "--id", "D1", "--pick", "1")
        self.assertEqual(human.returncode, 0, human.stdout)
        self.assertEqual(self.p.decisions(), [])
        self.assertEqual(self.p.ledger()[-1]["effect"], "defer")

    def test_fallback_prints_terminal_commands(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x",
                  "--command", "git push origin main")
        self.assertEqual(self.p.run("decision", "fallback", "--id", "D1").returncode, 1)
        out = self.p.ok("decision", "fallback", "--id", "D1", "--why", "the recorder is not trusted").stdout
        self.assertIn("D1 falls back to the terminal", out)
        self.assertIn("\n  git commit -m x\n  git push origin main\n", out)
        self.assertEqual(self.p.decisions(), [])
        self.assertEqual(self.p.ledger()[-1]["effect"], "fallback")

    def test_used_picks_settle_the_decision(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        cid = self.p.pick("D1", 2)
        self.p.append(type="use", id=cid, by="git-guard")
        self.assertEqual(self.p.run("decision", "show").returncode, 1)
        self.assertEqual(self.p.decisions(), [])
        settle = self.p.ledger()[-1]
        self.assertEqual((settle["type"], settle["pick"], settle["effect"]), ("settle", cid, "approved"))

    def test_ledger_mirrored(self):
        self.p.start()
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.assertEqual(self.journal("decision_opened")[0]["data"], {"decision": "D1", "kind": "commit",
                                                                       "options": 2})
        cid = self.p.pick("D1", 2)
        self.p.append(type="use", id=cid, by="git-guard")
        self.p.run("decision", "show")
        self.p.run("decision", "show")
        recorded, used, settled = (self.journal(e) for e in ("consent_recorded", "consent_used", "decision_settled"))
        self.assertEqual([len(recorded), len(used), len(settled)], [1, 1, 1])
        self.assertEqual(recorded[0]["data"]["id"], cid)
        self.assertEqual(recorded[0]["detail"], "git commit -m x")
        self.assertEqual(settled[0]["data"]["effect"], "approved")

    def test_a_task_mirrors_only_lines_after_its_start(self):
        self.p.append(type="decline", decision="D9", why="empty")
        self.p.start()
        self.p.append(type="decline", decision="D10", why="empty")
        self.p.run("decision", "show")
        self.assertEqual([e["data"]["decision"] for e in self.journal("decision_declined")], ["D10"])

    def test_consent_audit(self):
        transcript = os.path.join(self.p.tmp.name, "session.jsonl")
        with open(transcript, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "tool_use", "id": "toolu_real"}) + "\n")
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x",
                  "--command", "git push origin main")
        self.p.pick("D1", 2, tool_use_id="toolu_real", transcript=transcript)
        self.p.pick("D1", 3, order=2, tool_use_id="toolu_forged", transcript=transcript)
        self.p.pick("D1", 2, tool_use_id="toolu_nowhere")
        done = self.p.run("consent", "audit")
        self.assertEqual(done.returncode, 1)
        self.assertIn("C1 D1 ok\nC2 D1 mismatch\nC3 D1 unverifiable\n", done.stdout)
        rows = json.loads(self.p.run("consent", "audit", "--json").stdout)
        self.assertEqual([r["result"] for r in rows], ["ok", "mismatch", "unverifiable"])

    def test_consent_lists_live_picks(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m y")
        self.p.pick("D1", 2, session="another")
        self.p.pick("D2", 2)
        listed = json.loads(self.p.ok("consent", "--json").stdout)
        self.assertTrue(listed["dialog"])
        self.assertEqual([p["id"] for p in listed["live"]], ["C2"])
        self.assertIn("live picks: 1", self.p.ok("consent").stdout)

    def test_ask_opens_a_question_decision(self):
        self.p.start()
        done = self.p.ok("ask", "Which cache?", "--option", "A: per locale", "--option", "B: global",
                         "--recommend", "A")
        [question] = self.payload(done)["questions"]
        self.assertEqual(question["header"], "Q1")
        self.assertEqual([o["label"] for o in question["options"]],
                         ["Not now — leave it pending", "A — per locale", "B — global"])
        self.assertEqual(question["options"][1]["description"], "per locale (recommended)")
        [decision] = self.p.decisions()
        self.assertEqual((decision["kind"], decision["question_id"]), ("question", "Q1"))
        self.p.pick("D1", 2)
        out = self.p.ok("decision", "settle", "--id", "D1").stdout
        self.assertIn("Q1 answered", out)
        self.assertRegex(self.p.task_md(self.p.state()["task_id"]), r"\[Answer\]: A — by .+ via dialog at ")
        self.assertEqual(self.p.decisions(), [])
        self.assertNotIn("DIALOG_PENDING", self.p.ok("ask", "Four?", "--option", "A: a", "--option", "B: b",
                                                     "--option", "C: c", "--option", "D: d").stdout)

    def test_event_refuses_the_dialog_types(self):
        self.p.start()
        for event in ("decision_opened", "consent_recorded", "consent_used", "consent_voided",
                      "decision_declined", "decision_settled", "decision_fallback", "plan_drift"):
            with self.subTest(event=event):
                self.assertEqual(self.p.run("event", event).returncode, 5)


class TestDialogRoute(DialogBase):
    """R36.10: human_route() takes the dialog when a live pick of this session is
    this very command; close and the budget refusals open the decisions (R36.3);
    the dialog off is today, byte for byte (R36.2)."""

    def full_gate(self):
        self.p.start("--mode", "full", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        return self.p.ok("close")

    def name(self):
        return subprocess.run(["git", "-C", self.p.root, "config", "user.name"], capture_output=True, text=True,
                              check=False).stdout.strip() or os.environ.get("USER") or "human"

    def argv(self, label):
        """The label as the agent runs it: Project.run supplies interpreter, script and --root."""
        tokens = shlex.split(label)
        self.assertEqual(tokens[:4], ["python3", STATE, "--root", self.p.root])
        return tokens[4:]

    def label(self, decision_id, n):
        decision = next(d for d in self.p.decisions() if d["id"] == decision_id)
        return next(o["label"] for o in decision["options"] if o["n"] == n)

    def test_close_opens_approval_decision_when_dialog_on(self):
        done = self.full_gate()
        self.assertIn("ready for approval", done.stdout)
        self.assertNotIn("approve in your own terminal", done.stdout)
        self.assertIn("\nDIALOG_PENDING D1 — call AskUserQuestion", done.stdout)
        [question] = self.payload(done)["questions"]
        name = shlex.quote(self.name())
        self.assertEqual([o["label"] for o in question["options"]], [
            "Not now — leave the gate open",
            "python3 %s --root %s approve --by %s" % (STATE, self.p.root, name),
            "python3 %s --root %s reject --by %s --why 'rejected in the dialog'" % (STATE, self.p.root, name)])
        self.assertEqual((question["header"], question["multiSelect"]), ("Approve", False))
        self.assertIn("facts: (a) ", question["question"])
        [decision] = self.p.decisions()
        self.assertEqual((decision["kind"], decision["opened_by"], decision["task"]),
                         ("approval", "close", self.p.state()["task_id"]))
        self.assertIn("picks in the dialog (D1)", self.p.state()["next_action"])

    def test_close_prints_terminal_command_when_dialog_off(self):
        self.p.close()
        self.p = DialogProject(on=False)
        done = self.full_gate()
        self.assertIn("approve in your own terminal, then run close again:\n  python3 ", done.stdout)
        self.assertNotIn("DIALOG_PENDING", done.stdout)
        self.assertEqual(self.p.decisions(), [])

    def test_approve_via_dialog(self):
        self.full_gate()
        cid = self.p.pick("D1", 2)
        done = self.p.ok(*self.argv(self.label("D1", 2)))
        self.assertIn("(via dialog)", done.stdout)
        approved = self.journal("gate_approved")[-1]["data"]
        self.assertEqual((approved["via"], approved["consent"], approved["decision"], approved["tool_use_id"]),
                         ("dialog", cid, "D1", "toolu_%s" % cid))
        self.assertEqual([(e["type"], e.get("id") or e.get("effect")) for e in self.p.ledger()[-2:]],
                         [("use", cid), ("settle", "approved")])
        self.assertEqual(self.p.decisions(), [])
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_dialog_argv_must_equal_label(self):
        self.full_gate()
        self.p.pick("D1", 2)
        for args in (["approve", "--by", "someone else"], ["approve", "--by", self.name(), "--note", "x"]):
            with self.subTest(argv=args):
                done = self.p.run(*args)
                self.assertEqual(done.returncode, 5, done.stdout)
                self.assertIn("APPROVAL_REFUSED", done.stderr)
        argv = self.argv(self.label("D1", 2))
        for env in ({"CLAUDE_CODE_SESSION_ID": "another"}, {"CLAUDECODE": "1", "AI_RUNTIME": "codex"}):
            with self.subTest(env=env):
                self.assertEqual(self.p.run(*argv, env=env).returncode, 5)
        self.assertEqual([e["type"] for e in self.p.ledger()], ["pick"], "a refusal spends no pick")
        self.assertFalse(self.p.state()["human_approval"]["granted"])

    def test_an_expired_pick_is_no_pick(self):
        self.full_gate()
        self.p.pick("D1", 2, ago=200)
        self.assertEqual(self.p.run(*self.argv(self.label("D1", 2))).returncode, 5)

    def test_a_pick_does_not_outlive_its_gate(self):
        """Review H1: an approve label is the same string for every gate, so the
        pick for D1 (gate G1, the first tree) must not sign gate G2 on a changed
        tree after the agent rejected and closed again."""
        self.full_gate()
        label = self.label("D1", 2)
        self.p.pick("D1", 2)
        self.p.ok("reject", "--by", "agent", "--why", "redo")
        self.assertEqual([d["id"] for d in self.p.decisions()], [], "the rejection settles D1")
        self.p.write("src/widget.py", "x = 3\n")
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "e2e")
        self.p.ok("close")
        self.assertEqual([d["id"] for d in self.p.decisions()], ["D2"])
        self.assertEqual(self.label("D2", 2), label, "the same string — only the decision tells them apart")
        done = self.p.run(*self.argv(label))
        self.assertEqual(done.returncode, 5, done.stdout)
        self.assertFalse(self.p.state()["human_approval"]["granted"])
        self.assertNotIn("use", [e["type"] for e in self.p.ledger()])

    def test_a_dropped_decision_spends_no_pick(self):
        self.full_gate()
        self.p.pick("D1", 2)
        os.remove(os.path.join(self.p.root, ".ai", "state", "decision.json"))
        self.assertEqual(self.p.run(*self.argv(self.label_from_ledger())).returncode, 5)

    def label_from_ledger(self):
        return next(e["label"] for e in self.p.ledger() if e["type"] == "pick")

    def test_a_reoffer_after_expiry_is_live(self):
        """Review M1/M2: an expired pick of an earlier round blocks neither the new
        pick nor the decision's settling."""
        self.full_gate()
        self.p.pick("D1", 2, ago=200)
        cid = self.p.pick("D1", 2)
        self.p.ok(*self.argv(self.label("D1", 2)))
        self.assertEqual(self.journal("gate_approved")[-1]["data"]["consent"], cid)
        self.assertEqual(self.p.decisions(), [])

    def test_terminal_approval_settles_the_decision(self):
        self.full_gate()
        done = self.in_pty("approve", "--by", "ivan")
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertEqual(self.p.decisions(), [])
        self.assertEqual(self.p.ledger()[-1]["effect"], "approved")

    def test_rollback_line_follows_reversibility(self):
        """Review M3: the question states what the weight says about rollback."""
        facts = state_mod.task_facts
        state = {"task_id": "T-1", "goal": "g", "mode": "full", "verify": {"runs": []}, "review": {},
                 "weight": {"w": 8, "axes": {"reversibility": 2}, "evidence": {"reversibility": "deploy/x.yaml"}}}
        self.assertIn("rollback: git revert is not enough — reversibility 2: deploy/x.yaml",
                      facts(self.p.root, state))
        state["weight"]["axes"]["reversibility"] = 0
        self.assertIn("rollback: git revert", facts(self.p.root, state))

    def test_a_refusal_at_exit_4_writes_nothing(self):
        """Review L1: the dialog sync runs after the questions guard."""
        self.p.start()
        self.p.ok("ask", "Which?", "--option", "A: a", "--option", "B: b", "--option", "C: c", "--option", "D: d")
        self.p.append(type="decline", decision="D9", why="empty")
        path = self.p.state_file()
        with open(path, encoding="utf-8") as fh:
            before = fh.read()
        self.assertEqual(self.p.run("verify", "--scope", "suite").returncode, 4)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(fh.read(), before)

    def test_a_decline_after_a_choice_wins(self):
        """Review L4: the human's last answer decides."""
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.p.pick("D1", 1)
        self.p.append(type="decline", decision="D1", why="other_text")
        self.assertIn("declined", self.p.ok("decision", "settle", "--id", "D1").stdout)

    def test_irreversible_stays_terminal(self):
        self.p.start("--mode", "full_irreversible", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        done = self.p.ok("close")
        self.assertIn("approve in your own terminal", done.stdout)
        self.assertNotIn("DIALOG_PENDING", done.stdout)
        argv = ["approve", "--by", "me", "--confirm", "it drops nothing"]
        self.p.append(type="pick", id="C1", decision="D1", option=2, order=1, session=DIALOG_SESSION,
                      label="python3 %s --root %s %s" % (STATE, self.p.root, shlex.join(argv)),
                      expires_at=stamp(time.time() + 120))
        refused = self.p.run(*argv)
        self.assertEqual(refused.returncode, 5, refused.stdout)
        self.assertFalse(self.p.state()["human_approval"]["granted"])

    def test_label_with_quotes_round_trips(self):
        subprocess.run(["git", "-C", self.p.root, "config", "user.name", "Ivan \"Vanko\" O'Neil"], check=True)
        self.full_gate()
        label = self.label("D1", 2)
        self.assertIsNone(state_mod.validate_label(label))
        self.p.pick("D1", 2)
        self.p.ok(*self.argv(label))
        self.assertEqual(self.p.state()["human_approval"]["granted_by"], "Ivan \"Vanko\" O'Neil")

    def test_reject_via_dialog_settles_declined(self):
        self.full_gate()
        cid = self.p.pick("D1", 3)
        self.p.ok(*self.argv(self.label("D1", 3)))
        self.assertEqual(self.journal("gate_rejected")[-1]["data"]["consent"], cid)
        self.assertEqual(self.p.ledger()[-1]["effect"], "declined")
        self.assertIsNotNone(self.p.state()["human_approval"]["rejected_at"])

    def test_not_now_keeps_the_gate_open(self):
        self.full_gate()
        self.p.pick("D1", 1)
        self.p.ok("decision", "settle", "--id", "D1")
        self.assertEqual(self.p.decisions(), [])
        self.assertIsNotNone(self.p.state()["human_approval"]["requested_at"])
        self.assertFalse(self.p.state()["human_approval"]["granted"])

    def test_suite_budget_opens_human_set(self):
        self.p.start()
        self.p.ok("verify", "--scope", "suite")
        self.p.ok("verify", "--scope", "suite")
        done = self.p.run("verify", "--scope", "suite")
        self.assertEqual(done.returncode, 6)
        self.assertIn("SUITE_BUDGET", done.stderr)
        [question] = self.payload(done)["questions"]
        self.assertEqual(question["options"][0]["label"], "Keep the budget — stop here")
        label = self.label("D1", 2)
        self.assertEqual(self.argv(label), ["verify", "--scope", "suite", "--by", self.name()])
        cid = self.p.pick("D1", 2)
        self.p.ok(*self.argv(label))
        human = [e for e in self.journal("human_set") if e["data"].get("field") == "suite_runs"][-1]["data"]
        self.assertEqual((human["via"], human["consent"]), ("dialog", cid))

    def test_review_budget_opens_human_set(self):
        self.p.start("--mode", "guarded", "--by", "test")
        for _ in range(2):
            self.p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        done = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.assertEqual(done.returncode, 6)
        [question] = self.payload(done)["questions"]
        self.assertEqual(len(question["options"]), 4)
        label = self.label("D1", 2)
        self.assertEqual(self.argv(label), ["review", "--verdict", "pass", "--tier", "BALANCED", "--by", self.name()])
        self.p.pick("D1", 2)
        self.p.ok(*self.argv(label))
        self.assertEqual(self.journal("human_set")[-1]["data"]["via"], "dialog")
        self.assertEqual(self.p.state()["review"]["status"], "passed")

    def test_lowering_start_mode_opens_human_set(self):
        args = ["start", "--goal", "tweak the widget", "--workflow", "feature", "--files", "src/widget.py",
                "--tests", "tests/test_widget.py", "--declare", "behaviour=2:x", "--declare", "domain=2:x",
                "--declare", "novelty=0:x", "--mode", "light", "--by", "test"]
        done = self.p.run(*args)
        self.assertEqual(done.returncode, 5)
        self.assertIn("APPROVAL_REFUSED — lowering the mode", done.stderr)
        [decision] = self.p.decisions()
        self.assertEqual((decision["kind"], decision["opened_by"], decision["task"]), ("human_set", "start --mode", None))
        self.assertEqual(self.argv(self.label("D1", 2)), args)
        self.p.pick("D1", 2)
        self.p.ok(*args)
        self.assertEqual(self.p.state()["mode"], "light")
        self.assertEqual(self.journal("mode_set")[-1]["data"]["via"], "dialog")


class TestBatch(Base):
    """The batch loop of /rr-build-all (docs/sdlc/specs/batch-build.md): `after`
    on plan-file steps, the next wave, the batch budgets, the switch, the lines."""

    PLAN = [{"id": "s1", "files": ["src/a.py"], "tests": ["tests/test_widget.py"]},
            {"id": "s2", "files": ["src/b.py"], "tests": []},
            {"id": "s3", "files": ["src/c.py"], "tests": [], "after": ["s1", "s2"]},
            {"id": "s4", "files": ["src/a.py", "src/d.py"], "tests": [], "after": ["s3"]}]
    FILES = "src/a.py,src/b.py,src/c.py,src/d.py"
    BLOCK = "FINDINGS\n[BLOCKER] B1 the lock is not held\nin_scope: yes\nVERDICT blockers_open\n"

    def setUp(self):
        self.p = None

    def tearDown(self):
        if self.p:
            self.p.close()

    def _project(self, batch=None, table=True):
        """A scratch project whose own weight.json is the shipped table with its
        batch section replaced by `batch` (None: removed); table=False leaves the
        project without a table, so the shipped one applies."""
        if self.p:
            self.p.close()
        files = {"src/a.py": "a\n", "src/b.py": "b\n", "src/c.py": "c\n", "src/d.py": "d\n"}
        if table:
            with open(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies", "weight.json"),
                      encoding="utf-8") as fh:
                policy = json.load(fh)
            if batch is None:
                del policy["batch"]
            else:
                policy["batch"] = dict(policy["batch"], **batch)
            files[".ai/policies/weight.json"] = json.dumps(policy)
        self.p = Project(files=files)
        return self.p

    def _plan(self, steps):
        path = os.path.join(self.p.tmp.name, "plan.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(steps, fh)
        return path

    def _start(self, *extra, steps=None):
        return self.p.start("--plan-file", self._plan(self.PLAN if steps is None else steps), *extra, files=self.FILES)

    def _try_start(self, steps, *extra):
        return self.p.run("start", "--goal", "g", "--workflow", "feature", "--files", self.FILES,
                          "--plan-file", self._plan(steps), *ZERO, *extra)

    def _ready(self):
        return self.p.ok("steps", "--ready").stdout.split()

    def _batch_events(self):
        return [e["data"] for e in self.p.events(self.task_id()) if e["event"] == "batch_set"]

    def test_after_unknown_self_cycle_and_shape_refused(self):
        self._project(table=False)
        cases = (([{"id": "s1", "files": ["src/a.py"], "after": ["nope"]}], "is not a step"),
                 ([{"id": "s1", "files": ["src/a.py"], "after": ["s1"]}], "lists itself"),
                 ([{"id": "s1", "files": ["src/a.py"], "after": ["s2"]},
                   {"id": "s2", "files": ["src/b.py"], "after": ["s1"]}], "form a cycle"),
                 ([{"id": "s1", "files": ["src/a.py"], "after": "s2"}], '"after" is a JSON list'))
        for steps, text in cases:
            with self.subTest(text=text):
                done = self._try_start(steps)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(text, done.stderr)
                self.assertFalse(self.p.in_flight())
        # In a batch task the shared file orders y after x, and x says it is after y: a cycle, with
        # the implied edge named (review L7).
        done = self._try_start([{"id": "x", "files": ["src/a.py"], "after": ["y"]}, {"id": "y", "files": ["src/a.py"]}],
                               "--batch", "--by", "ivan")
        self.assertEqual(done.returncode, 1)
        self.assertIn("form a cycle: x -> y -> x", done.stderr)
        self.assertIn("y after x is implied: they share src/a.py", done.stderr)

    def test_shared_file_orders_steps(self):
        self._project(table=False)
        out = self._start("--batch", "--by", "ivan").stdout
        self.assertIn("ordered: s4 after s1 (shares src/a.py)", out)
        steps = {s["id"]: s for s in self.p.state()["steps"]}
        self.assertEqual((steps["s4"]["after"], steps["s2"]["after"]), (["s3", "s1"], []))
        self.assertIn("- s3 · src/c.py · no tests · pending · after s1, s2", self.p.task_md(self.task_id()))

    def test_steps_ready_by_waves(self):
        self._project(table=False)
        self._start()
        self.assertEqual(self._ready(), ["s1", "s2"])
        listing = self.p.ok("steps").stdout
        self.assertIn("s1 · in_progress · after - · ready", listing)
        self.assertIn("s3 · pending · after s1, s2 · waiting", listing)
        self.assertIn("next: s2", self.p.ok("step-done", "s1").stdout)
        self.assertEqual(self._ready(), ["s2"])
        self.assertIn("next: s3", self.p.ok("step-done", "s2").stdout)
        self.assertEqual(self._ready(), ["s3"])
        self.p.ok("step-done", "s3")
        self.assertEqual(self._ready(), ["s4"])
        self.assertIn("all steps done", self.p.ok("step-done", "s4").stdout)
        self.assertEqual(self._ready(), [])
        shown = json.loads(self.p.ok("steps", "--json").stdout)
        self.assertEqual((shown["ready"], shown["batch"], len(shown["steps"])), ([], False, 4))
        self.assertEqual((shown["batch_policy"]["tier"], shown["batch_policy"]["parallel"]), ("BALANCED", 3))

    def test_steps_without_after_behave_as_before(self):
        self._project(table=False)
        self.p.start("--steps", "s1:src/a.py;s2:src/b.py", files=self.FILES)
        self.assertEqual(self._ready(), ["s1", "s2"])
        self.assertIn("next: s2", self.p.ok("step-done", "s1").stdout)
        self.assertEqual(self.p.state()["batch"], {"on": False, "by": None, "why": None, "since": None})
        self.assertNotIn("batch:", self.p.ok("status").stdout)
        self.assertNotIn("Batch:", self.p.ok("handoff", "--print").stdout)
        self.assertNotIn("after", self.p.task_md(self.task_id()).split("## Plan")[1].split("## Questions")[0])
        # Review M1: outside batch, steps that share a file are not reordered, and step-done
        # picks the first pending step as before.
        self.p.ok("close", "--abandon")
        out = self.p.start("--steps", "s1:src/a.py;s2:src/a.py;s3:src/b.py", files=self.FILES).stdout
        self.assertNotIn("ordered:", out)
        self.assertEqual([s["after"] for s in self.p.state()["steps"]], [[], [], []])
        self.assertIn("step s3 done; next: s2", self.p.ok("step-done", "s3").stdout)

    def test_flag_and_project_default(self):
        self._project(batch={"default": True})
        refused = self._try_start(self.PLAN, "--batch")
        self.assertEqual(refused.returncode, 1)
        self.assertIn("--batch needs --by", refused.stderr)
        both = self._try_start(self.PLAN, "--batch", "--by", "ivan", "--no-batch")
        self.assertEqual(both.returncode, 1)
        self.assertIn("exclude each other", both.stderr)
        out = self._start().stdout                                           # the project's default
        self.assertIn("batch: on by weight.json batch.default · review 3 passes · suite 8 runs · 3 at once on "
                      "BALANCED", out)
        batch = self.p.state()["batch"]
        self.assertEqual((batch["on"], batch["by"]), (True, "weight.json batch.default"))
        self.assertEqual(self._batch_events(), [{"on": True, "by": "weight.json batch.default", "why": None,
                                                "via": None, "review_passes": 0, "suite_runs": 0}])
        self.assertIn("batch loop:", self.p.state()["next_action"])
        self.p.ok("close", "--abandon")
        self._start("--mode", "full", "--by", "agent", "--why", "the mode's reason")   # review L5
        self.assertEqual(self.p.state()["batch"]["by"], "weight.json batch.default")
        self.assertIsNone(self._batch_events()[-1]["why"])
        self.p.ok("close", "--abandon")
        self._start("--no-batch")
        self.assertFalse(self.p.state()["batch"]["on"])
        self.p.ok("close", "--abandon")
        self._start("--batch", "--by", "ivan", "--why", "/rr-build-all")
        self.assertEqual(self.p.state()["batch"]["by"], "ivan")
        self.assertIn("batch: on by ivan at ", self.p.task_md(self.task_id()))
        self.assertIn("— /rr-build-all", self.p.task_md(self.task_id()))

    def test_three_passes_then_the_human(self):
        self._project(table=False)
        self._start("--mode", "guarded", "--batch", "--by", "ivan")
        self.p.ok("verify", "--scope", "all")
        for _ in range(3):
            self.p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=self.BLOCK)
        self.assertIn("then a full review pass again", self.p.state()["next_action"])
        owed = self.p.run("close")
        self.assertEqual(owed.returncode, 2)
        self.assertIn("a full review pass again", owed.stderr)                   # review L4: close_owed
        fourth = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.assertEqual(fourth.returncode, 6)
        self.assertIn("REVIEW_BUDGET", fourth.stderr)
        self.assertIn("allows 3 (batch.review_rounds_max)", fourth.stderr)
        self.assertEqual(self.p.state()["review"]["passes"], 3)
        self.assertIn("review: blockers_open (3 of 3)", self.p.ok("status").stdout)
        # Off: the standard budget from here, counting what was spent — the next verdict is the human's.
        off = self.p.ok("batch", "off", "--by", "ivan", "--why", "the standard loop from here")
        self.assertIn("batch off by ivan · review 3/2 · suite 1/2", off.stdout)
        self.assertFalse(self.p.state()["batch"]["on"])
        self.assertEqual(self._batch_events()[-1], {"on": False, "by": "ivan", "why": "the standard loop from here",
                                                   "via": None, "review_passes": 3, "suite_runs": 1})
        self.assertIn("one scoped re-review", self.p.state()["next_action"])
        again = self.p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.assertEqual(again.returncode, 6)
        self.assertIn("allows 2 (review_rounds_max)", again.stderr)
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", "--by", "ivan",
                  stdin=CLEAN, human=True)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_suite_budget_is_eight(self):
        self._project(table=False)
        self._start("--batch", "--by", "ivan")
        for _ in range(8):
            self.p.ok("verify", "--scope", "suite")
        ninth = self.p.run("verify", "--scope", "suite")
        self.assertEqual(ninth.returncode, 6)
        self.assertIn("SUITE_BUDGET", ninth.stderr)
        self.assertIn("allows 8 (batch.max_suite_runs)", ninth.stderr)
        self.assertIn("suite 8/8", self.p.ok("status").stdout)

    def test_batch_on_is_the_humans(self):
        self._project(table=False)
        self._start()
        refused = self.p.run("batch", "on", "--by", "ivan")
        self.assertEqual(refused.returncode, 5)
        self.assertIn("APPROVAL_REFUSED", refused.stderr)
        self.assertIn("batch on --by", refused.stderr)
        self.assertFalse(self.p.state()["batch"]["on"])
        self.assertEqual(self.p.run("batch", "on").returncode, 1)                 # --by is required
        out = self.p.ok("batch", "on", "--by", "ivan", human=True).stdout
        self.assertIn("batch on by ivan · review 0/3 · suite 0/8", out)
        self.assertTrue(self.p.state()["batch"]["on"])
        self.assertIn("batch is already on", self.p.ok("batch", "on", "--by", "ivan", human=True).stdout)
        self.assertEqual((self._batch_events()[-1]["via"], self._batch_events()[-1]["on"]), ("unattended", True))
        self.assertEqual(self.p.run("batch", "off", "--by", "ivan").returncode, 1)  # --why is required
        self.p.ok("batch", "off", "--by", "ivan", "--why", "done with it")
        self.assertFalse(self.p.state()["batch"]["on"])

    def test_lines_show_batch(self):
        self._project(table=False)
        self._start("--batch", "--by", "ivan")
        status = self.p.ok("status").stdout.splitlines()
        self.assertLessEqual(len(status), 20)
        self.assertEqual(status[3], "batch: on by ivan · review 0/3 · suite 0/8 · ready s1, s2")
        handoff = self.p.ok("handoff", "--print").stdout.splitlines()
        self.assertLessEqual(len(handoff), 30)
        self.assertIn("Batch: on · ready s1, s2 · review 0/3 · suite 0/8", handoff)
        self.assertIn("batch loop: 'steps --ready'", handoff[2])
        md = self.p.task_md(self.task_id())
        self.assertIn("batch: on by ivan at ", md)
        self.assertIn("- s4 · src/a.py, src/d.py · no tests · pending · after s3, s1", md)

    def test_table_without_the_section_uses_the_defaults(self):
        self._project(batch=None)                     # the project's own table predates the section
        out = self._start("--batch", "--by", "ivan").stdout
        self.assertIn("review 3 passes · suite 8 runs · 3 at once on BALANCED", out)
        self._project(batch={"review_rounds_max": 1, "max_suite_runs": 1, "parallel": 2, "tier": "STRONG"})
        out = self._start("--batch", "--by", "ivan").stdout
        self.assertIn("review 1 passes · suite 1 runs · 2 at once on STRONG", out)
        self.p.ok("verify", "--scope", "suite")
        self.assertEqual(self.p.run("verify", "--scope", "suite").returncode, 6)
        # Review L1, L6: a malformed section is refused at start, whether or not the task is batch;
        # three or more parallel agents never run above BALANCED.
        for bad, text in (({"review_rounds_max": "three"}, "batch.review_rounds_max must be a whole number"),
                          ({"default": "false"}, "batch.default must be true or false"),
                          ({"tier": "LOCAL"}, "batch.tier must be one of"),
                          ({"tier": "STRONG", "parallel": 5}, "three or more parallel agents run at FAST or BALANCED")):
            with self.subTest(bad=bad):
                self._project(batch=bad)
                done = self._try_start(self.PLAN)
                self.assertEqual(done.returncode, 1, done.stdout + done.stderr)
                self.assertIn(text, done.stderr)
                self.assertIn("weight.json:", done.stderr)

    def test_batch_set_is_not_forgeable(self):
        self._project(table=False)
        self._start()
        self.assertEqual(self.p.run("event", "batch_set").returncode, 5)

    def test_a_pending_question_blocks_the_next_wave(self):
        self._project(table=False)
        self._start("--batch", "--by", "ivan")
        self.p.ok("ask", "G1 is yours: apply the staged policy edits", "--option", "A: done", "--option", "B: not yet")
        self.assertEqual(self.p.run("step-done", "s1").returncode, 4)
        self.assertEqual(self._ready(), ["s1", "s2"])                           # read-only: it still answers
        self.assertIn("Pending questions: Q1", self.p.ok("handoff", "--print").stdout)
        self.p.ok("answer", "Q1=A")
        self.p.ok("step-done", "s1")

    def test_full_mode_still_asks_the_human(self):
        self._project(table=False)
        self._start("--mode", "full", "--batch", "--by", "ivan")
        self.p.write("src/a.py", "a = 2\n")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        self.assertIn("ready for approval", self.p.ok("close").stdout)
        self.p.ok("batch", "off", "--by", "ivan", "--why", "the standard loop from here")
        self.assertIn("the human approves", self.p.state()["next_action"])        # review L4: the gate's text stays
        self.assertEqual(self.p.run("approve", "--by", "ivan").returncode, 5)
        self.p.ok("approve", "--by", "ivan", human=True)
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_a_wave_is_recorded_in_any_order(self):
        """Review M2, M5, L3: a wave's steps are recorded in any order; the journal
        says what each step's diff held, and the summary never says done too early."""
        self._project(table=False)
        self._start("--batch", "--by", "ivan", steps=[{"id": "s1", "files": ["src/a.py"]},
                                                      {"id": "s2", "files": ["src/b.py"]},
                                                      {"id": "s3", "files": ["src/c.py"], "after": ["s1"]}])
        self.p.write("src/a.py", "a = 2\n")
        self.p.write("src/b.py", "b = 2\n")
        out = self.p.ok("step-done", "s2").stdout
        self.assertIn("step s2 done; 2 still open: s1, s3", out)
        self.assertIn("note: the diff also holds 1 file(s) outside this step's own — src/a.py", out)
        data = [e for e in self.p.events(self.task_id()) if e["event"] == "step_done"][-1]["data"]
        self.assertEqual((data["own"], data["others"], data["unready"]), (["src/b.py"], ["src/a.py"], []))
        out = self.p.ok("step-done", "s3").stdout                                 # before s1, which it is after
        self.assertIn("note: s3 was done before s1, which it is after", out)
        self.assertEqual([e for e in self.p.events(self.task_id()) if e["event"] == "step_done"][-1]["data"]["unready"],
                         ["s1"])
        self.assertIn("step s1 done; all steps done", self.p.ok("step-done", "s1").stdout)

    def test_shared_tests_and_patterns_order_steps(self):
        """Review M4: tests count, patterns count, ./a is a."""
        self._project(table=False)
        out = self._start("--batch", "--by", "ivan",
                          steps=[{"id": "a", "files": ["src/a.py"], "tests": ["tests/test_widget.py"]},
                                 {"id": "b", "files": ["src/b.py"], "tests": ["tests/test_widget.py"]},
                                 {"id": "c", "files": ["src/*.py"]},
                                 {"id": "d", "files": ["./src/d.py"]},
                                 {"id": "e", "files": ["src/d.py"]}]).stdout
        self.assertIn("ordered: b after a (shares tests/test_widget.py)", out)
        self.assertIn("ordered: c after a (shares src/*.py)", out)
        self.assertIn("ordered: e after d (shares src/d.py)", out)
        after = {s["id"]: s["after"] for s in self.p.state()["steps"]}
        self.assertEqual((after["b"], after["c"], after["d"], after["e"]), (["a"], ["a", "b"], ["c"], ["c", "d"]))

    def test_the_first_ready_step_starts(self):
        """Review L2: start opens the first step whose dependencies are done."""
        self._project(table=False)
        self._start("--batch", "--by", "ivan", steps=[{"id": "s1", "files": ["src/a.py"], "after": ["s2"]},
                                                      {"id": "s2", "files": ["src/b.py"]}])
        self.assertEqual([(s["id"], s["status"]) for s in self.p.state()["steps"]],
                         [("s1", "pending"), ("s2", "in_progress")])
        self.assertEqual(self._ready(), ["s2"])
        self.assertIn("current s2", self.p.ok("status").stdout)


class TestDocumentsOnly(unittest.TestCase):
    """2b (docs/sdlc/specs/faster-task-cycle.md, D1-D5): after a green suite, a documents-only
    edit closes on a green run of `doc_tests`. Every project builds its own policy."""

    DOCUMENTS = {"globs": ["**/*.md", "docs/**/*.json", ".ai/**/*.json"],
                 "except": ["skills/**", "hooks/**", "agents/**", "instructions/**", "codex/**"]}
    FILES = "src/widget.py,README.md,docs/guide.md,skills/guide.md,.ai/policies/x.md,tests/test_docs.py"
    DOC_RUN = ("verify", "--scope", "step", "--files", "tests/test_docs.py")
    ACTIONABLE = 'only documents changed since run %d (%d files): \'verify --scope step --files "%s"\''
    OLD = "the tree changed after the last verify"

    def setUp(self):
        self.p = None

    def tearDown(self):
        if self.p:
            self.p.close()

    def project(self, documents=True, doc_tests="tests/test_docs.py"):
        """A scratch project; documents=False has no `documents` key, doc_tests=None no such line."""
        with open(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies", "weight.json"),
                  encoding="utf-8") as fh:
            policy = json.load(fh)
        if documents:
            policy["documents"] = self.DOCUMENTS
        self.p = Project(files={".ai/policies/weight.json": json.dumps(policy), "README.md": "# r\n",
                                "docs/guide.md": "g\n", "skills/guide.md": "s\n", ".ai/policies/x.md": "x\n",
                                "tests/test_docs.py": "assert True\n"})
        if doc_tests is not None:
            with open(os.path.join(self.p.root, ".ai", "policies", "testing.md"), "a", encoding="utf-8") as fh:
                fh.write("doc_tests: %s\n" % doc_tests)
        return self.p

    def green_then(self, *edits, mode=()):
        """start, one green whole-suite run (G, run 1), then the edits (path, text)."""
        self.p.start(*mode, files=self.FILES)
        self.p.ok("verify", "--scope", "all")
        for rel, text in edits:
            self.p.write(rel, text)

    def close_refused(self, text):
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertIn(text, done.stderr)
        self.assertTrue(self.p.in_flight())

    # R10: without the key and the line, nothing changes (C2) — green before and after 2b.

    def test_without_the_key_a_document_edit_after_green_still_refuses(self):
        self.project(documents=False, doc_tests=None)
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_without_the_key_red_on_this_tree_refuses(self):
        self.project(documents=False, doc_tests=None)
        self.p.start(files=self.FILES)
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        self.close_refused("the suite is red on this tree")

    # D1

    def test_globs_without_doc_tests_is_off(self):
        self.project(doc_tests=None)
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_doc_tests_none_is_off(self):
        self.project(doc_tests="none")
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_doc_tests_without_globs_is_off(self):
        self.project(documents=False)
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    # D2

    def test_no_green_full_run_is_off(self):
        self.project()
        self.p.start(files=self.FILES)
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "all").returncode, 1)
        self.p.flag("red", False)
        self.p.write("README.md", "# edited\n")
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_red_full_run_on_g_tree_under_another_runtime_refuses(self):
        self.project()
        self.p.start(files=self.FILES)
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "suite", runtime="codex").returncode, 1)
        self.p.flag("red", False)
        self.p.ok("verify", "--scope", "all")               # G: green, on a tree that also has a red run
        self.p.write("README.md", "# edited\n")
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_a_red_run_after_g_is_not_g(self):
        self.project()
        self.green_then()
        self.p.flag("red")
        self.assertEqual(self.p.run("verify", "--scope", "suite", runtime="codex").returncode, 1)
        self.p.flag("red", False)
        self.p.write("README.md", "# edited\n")
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    # D3, D4

    def test_a_code_file_in_the_diff_refuses(self):
        self.project()
        self.green_then(("README.md", "# edited\n"), ("src/widget.py", "x = 2\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_a_test_file_in_the_diff_refuses(self):
        self.project()
        self.green_then(("README.md", "# edited\n"), ("tests/test_docs.py", "assert 1\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_a_policy_path_refuses_even_when_globs_match(self):
        self.project()
        self.green_then((".ai/policies/x.md", "changed\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_a_rules_path_refuses_even_when_globs_match(self):
        self.project()
        self.p.start(files=self.FILES + ",.ai/rules/x.md")
        self.p.ok("verify", "--scope", "all")
        self.p.write(".ai/rules/x.md", "changed\n")
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_the_documents_refusal_is_a_review_required_line(self):
        # rr-ship's table matches this line by its `review required (` start. close writes it
        # through die(), so it is on stderr behind the `state.py: ` prefix.
        self.project()
        self.green_then(("README.md", "# edited\n"))
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2, done.stderr)
        lines = [ln for ln in (done.stdout + done.stderr).splitlines() if "only documents changed since run" in ln]
        self.assertEqual(len(lines), 1, done.stdout + done.stderr)
        self.assertRegex(lines[0], r"^(state\.py: )?review required \(\w+ mode\) — .*only documents changed since run")

    def test_except_glob_refuses(self):
        self.project()
        self.green_then(("skills/guide.md", "changed\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_rename_py_to_md_refuses(self):
        self.project()
        self.green_then()
        os.rename(os.path.join(self.p.root, "src", "widget.py"), os.path.join(self.p.root, "docs", "widget.md"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.OLD)

    def test_is_document_is_one_predicate(self):
        policy = dict(weight.load_policy(ROOT)[0], documents=self.DOCUMENTS)
        paths = ("README.md", "docs/a/b.md", "docs/x.json", ".ai/state/x.json", ".ai/policies/weight.json",
                 ".ai/policies/x.md", "skills/a.md", "src/a.py", "tests/test_a.py", "notes.txt")
        self.assertEqual([p for p in paths if state_mod.is_document(p, policy)],
                         ["README.md", "docs/a/b.md", "docs/x.json", ".ai/state/x.json"])
        self.assertFalse(state_mod.is_document("README.md", {}), "no `documents` key: nothing is a document")
        self.assertEqual(state_mod.NEVER_DOCUMENTS, (".ai/policies/**", ".ai/rules/**"))

    # D5

    def test_without_a_scoped_run_the_refusal_names_the_command(self):
        self.project()
        self.green_then(("README.md", "# edited\n"))
        self.close_refused(self.ACTIONABLE % (1, 1, "tests/test_docs.py"))

    def test_scoped_run_missing_a_doc_test_refuses(self):
        self.project(doc_tests="tests/test_docs.py tests/test_more.py")
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.close_refused(self.ACTIONABLE % (1, 1, "tests/test_docs.py,tests/test_more.py"))

    def test_scoped_run_naming_every_doc_test_closes(self):
        self.project(doc_tests="tests/test_docs.py tests/test_more.py")
        self.green_then(("README.md", "# edited\n"))
        self.p.ok("verify", "--scope", "step", "--files", "tests/test_docs.py,tests/test_more.py")
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())

    def test_red_scoped_run_refuses(self):
        self.project()
        self.green_then(("README.md", "# edited\n"))
        self.p.flag("stepred")
        self.assertEqual(self.p.run(*self.DOC_RUN).returncode, 1)
        self.close_refused(self.ACTIONABLE % (1, 1, "tests/test_docs.py"))

    def test_scoped_run_expected_fail_refuses(self):
        self.project()
        self.green_then(("README.md", "# edited\n"))
        self.assertEqual(self.p.run(*self.DOC_RUN, "--expect", "fail").returncode, 1)   # exit 0 inside: no bite
        self.assertTrue(self.p.state()["verify"]["runs"][-1]["expected_fail"])
        self.close_refused(self.ACTIONABLE % (1, 1, "tests/test_docs.py"))

    def test_scoped_run_before_g_refuses(self):
        self.project()
        self.p.start(files=self.FILES)
        self.p.write("README.md", "# edited\n")
        self.p.ok(*self.DOC_RUN)                             # run 1, on the edited tree
        self.p.write("README.md", "# r\n")
        self.p.ok("verify", "--scope", "all")                # G is run 2, on the unedited tree
        self.p.write("README.md", "# edited\n")              # the tree of run 1 again: n <= G.n
        self.close_refused(self.ACTIONABLE % (2, 1, "tests/test_docs.py"))

    def test_scoped_run_on_another_tree_refuses(self):
        self.project()
        self.green_then(("README.md", "# edited\n"))
        self.p.ok(*self.DOC_RUN)
        self.p.write("README.md", "# edited again\n")
        self.close_refused(self.ACTIONABLE % (1, 1, "tests/test_docs.py"))

    # the green path and what must not move

    def test_green_doc_tests_after_g_closes(self):
        self.project()
        self.green_then(("README.md", "# edited\n"), ("docs/guide.md", "g2\n"))
        self.p.ok(*self.DOC_RUN)
        task = self.p.state()["task_id"]
        self.p.ok("close")
        self.assertFalse(self.p.in_flight())
        archived = self.p.archived(task)
        self.assertEqual(archived["facts"]["documents"],
                         {"since_run": 1, "since_tree": archived["verify"]["runs"][0]["tree"], "run": 2,
                          "paths": ["README.md", "docs/guide.md"], "tests": ["tests/test_docs.py"]})
        self.assertTrue(archived["facts"]["a"][0])
        self.assertIn("documents only since run 1", archived["facts"]["a"][1])
        self.assertIn("documents only since run 1", self.p.task_md(task))

    def test_e2e_is_still_owed_on_this_tree(self):
        self.project()
        self.green_then(mode=("--mode", "guarded", "--by", "test"))
        self.p.write("README.md", "# edited\n")
        self.p.ok("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=CLEAN)
        self.p.ok(*self.DOC_RUN)
        done = self.p.run("close")
        self.assertEqual(done.returncode, 2, done.stderr)
        self.assertTrue(done.stderr.startswith("state.py: verify required"), done.stderr)
        self.assertIn("e2e on this tree", done.stderr)

    def test_review_closes_still_needs_a_full_suite(self):
        self.project()
        self.green_then(mode=("--mode", "guarded", "--by", "test"))
        self.p.ok("review", "--verdict", "pass_with_findings", "--tier", "BALANCED", "--report", "-", stdin=FINDINGS)
        self.p.write("README.md", "# edited\n")
        self.p.ok(*self.DOC_RUN)
        done = self.p.run("review", "--closes", "H1")
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("stay open", done.stderr)


if __name__ == "__main__":
    unittest.main()
