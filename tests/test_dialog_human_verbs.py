#!/usr/bin/env python3
"""ui-first-approvals s8 (R4, R5, R7, R9): the install decision the model may open, the refusal text and the plain
words the dialog shows -- and what stays the human's.

A case runs in a scratch project of tests/test_ai_task_state.py (`DialogProject`: the dialog on, a profile with its
dialog tool, the recorder's picks written by hand) and, for a command the hook gates, through hooks/ai-guard.py
as test_dialog_consent.py does. `npx` itself is not a guarded command: with no decision pending the gate lets any of
it through, today and after this step. The negatives here are about a PENDING gate."""

import json
import os
import shlex
import subprocess
import sys
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
from guard import dialog as hook_dialog  # noqa: E402  pylint: disable=wrong-import-position
from guard_harness import decision as decision_of  # noqa: E402  pylint: disable=wrong-import-position
import test_ai_task_state as tas  # noqa: E402  pylint: disable=wrong-import-position
from rr_state import dialog as rr_dialog  # noqa: E402  pylint: disable=wrong-import-position
from rr_state import labels as rr_labels  # noqa: E402  pylint: disable=wrong-import-position

NPX = "npx riskrails@4.3.0 --yes"
COMMIT = "git commit -m x -- a.py"
OPEN = ("decision", "open", "--kind", "install", "--command")


def guard(project, command, session=tas.DIALOG_SESSION, **extra):
    """The hook's verdict on a Bash command, in the session `session`; extra goes into the payload (agent_id)."""
    payload = dict({"session_id": session, "transcript_path": os.path.join(project.root, "t.jsonl"),
                    "cwd": project.root, "hook_event_name": "PreToolUse", "tool_name": "Bash",
                    "tool_use_id": "toolu_run", "tool_input": {"command": command}, "prompt_id": "turn_1"}, **extra)
    env = dict(os.environ, CLAUDE_CONFIG_DIR=project.home, AI_UNATTENDED="", CLAUDE_CODE_SESSION_ATTENDED="1")
    env.pop("CLAUDE_CODE_SESSION_ID", None)
    proc = subprocess.run(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "ai-guard.py")],
                          input=json.dumps(payload), capture_output=True, text=True, check=False,
                          cwd=project.root, env=env)
    return proc.stdout


def reason(out):
    try:
        return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
    except (ValueError, KeyError, TypeError):
        return out


class TestInstallDecision(tas.DialogBase):
    """R4: the install decision, its texts, and the picked command's way through the gate."""

    def test_it_opens_with_the_header_the_options_and_the_question(self):
        self.p.profile({"plan": "max", "dialog": {"tool": "AskUserQuestion"}, "plugin_version": "4.2.0"})
        done = self.p.ok(*OPEN, NPX)
        [question] = self.payload(done)["questions"]
        self.assertEqual(question["header"], "Install")
        self.assertEqual(question["question"],
                         "Install RiskRails 4.3.0 (installed 4.2.0)? It rewrites the hooks, skills and settings under "
                         "%s; restart the session afterwards." % self.p.home)
        self.assertEqual([o["label"] for o in question["options"]], ["Not now — keep 4.2.0", NPX])
        self.assertEqual([o["description"] for o in question["options"]],
                         ["nothing runs", rr_labels.describe(shlex.split(NPX))])
        [decision] = self.p.decisions()
        self.assertEqual((decision["kind"], decision["task"]), ("install", None))

    def test_the_picked_command_passes_the_gate_once_and_the_decision_settles(self):
        self.p.ok(*OPEN, NPX)
        self.p.pick("D1", 2)
        out = guard(self.p, NPX)
        self.assertEqual(decision_of(out), "allow", out[:400])
        self.assertEqual([e["type"] for e in self.p.ledger()], ["pick", "use"])
        self.p.run("decision", "show")          # any decision command prunes the settled decision
        self.assertEqual(self.p.decisions(), [], "the spent pick settled its decision")

    def test_not_now_is_a_choice_and_runs_nothing(self):
        self.p.ok(*OPEN, NPX)
        self.p.pick("D1", 1)
        self.assertIn("settled", self.p.ok("decision", "settle", "--id", "D1").stdout)
        self.assertEqual(self.p.decisions(), [])


class TestPlainWords(tas.DialogBase):
    """R9: a command option without a description of its own carries `labels.describe`, stored when the decision
    opens, so both twins read the same text."""

    def test_a_commit_option_stores_its_plain_words(self):
        self.commit(COMMIT, "git push origin feat/x")
        self.assertEqual(self.p.decisions()[0]["options"][0].get("description"), None, "a choice stores none")
        stored = {o["label"]: o.get("description") for o in self.p.decisions()[0]["options"]}
        self.assertEqual(stored[COMMIT], rr_labels.describe(shlex.split(COMMIT)))
        self.assertEqual(stored["git push origin feat/x"], rr_labels.describe(["git", "push", "origin", "feat/x"]))
        done = self.p.ok("decision", "show")
        questions = self.payload(done)["questions"]
        self.assertEqual([o["description"] for o in questions[0]["options"]][:2],
                         ["nothing runs", "Save the finished work as a commit in git."])

    def test_the_hook_twin_reads_the_stored_text(self):
        self.commit(COMMIT)
        for option in self.p.decisions()[0]["options"]:
            if option["kind"] == "command":
                self.assertEqual(rr_dialog.option_description(option), option["description"])
        offered = hook_dialog.offered(self.p.decisions(), "claude")
        self.assertIn("Save the finished work", json.dumps(offered, ensure_ascii=False))


class TestHumanRefusal(unittest.TestCase):
    """R7: the dialog-first text with a decision, None without one."""

    def test_with_a_decision_the_text_is_exact(self):
        self.assertEqual(
            rr_dialog.human_refusal("'state.py approve'", "python3 s.py approve --by you", "no pick is live", "D3"),
            "APPROVAL_REFUSED — 'state.py approve' is the human's. Ask them in the dialog: send DIALOG_PENDING D3 "
            "(printed above), then run the command they pick, verbatim, once. Or they run, in their own terminal:\n"
            "  python3 s.py approve --by you\nRefused because no pick is live.")

    def test_without_a_decision_it_is_none(self):
        for decision in (None, ""):
            self.assertIsNone(rr_dialog.human_refusal("x", "y", "z", decision))


class TestStillRefused(tas.DialogBase):  # pylint: disable=too-many-public-methods  # one test per case keeps failures named
    """R5: one negative each."""

    def test_install_with_the_dialog_off(self):
        off = tas.DialogProject(on=False)
        self.addCleanup(off.close)
        done = off.run(*OPEN, NPX)
        self.assertEqual(done.returncode, 1, done.stdout)
        self.assertIn("the dialog is off here", done.stderr)
        self.assertEqual(off.decisions(), [])

    def test_install_while_a_task_is_in_flight(self):
        self.p.start()
        done = self.p.run(*OPEN, NPX)
        self.assertEqual(done.returncode, 6, done.stdout)
        self.assertIn("INSTALL_DURING_TASK", done.stderr)
        self.assertIn(self.p.state()["task_id"], done.stderr)
        self.assertEqual(self.p.decisions(), [])

    def test_install_with_any_other_command_form(self):
        for command in ("npx other@4.3.0 --yes", "npx riskrails@^4.3.0 --yes", "npx riskrails@latest --yes",
                        "npx riskrails@4.3.0 --yes --target claude", "npx riskrails@4.3.0",
                        "npx -y riskrails@4.3.0 --yes", "npx riskrails@4.3.0 --yes && ls",
                        "npx riskrails@4.3.0 --yes; ls", "git commit -m x", "npx riskrails --yes",
                        "npx riskrails@4.3 --yes", "npx riskrails@4.3.0-rc.1 --yes", " " + NPX):
            with self.subTest(command):
                done = self.p.run(*OPEN, command)
                self.assertEqual(done.returncode, 6, done.stdout)
                self.assertIn("CONSENT_LABEL_INVALID", done.stderr)
        with self.subTest("a second command"):
            done = self.p.run(*OPEN, NPX, "--command", NPX.replace("4.3.0", "4.3.1"))
            self.assertEqual(done.returncode, 6, done.stdout)
        with self.subTest("no command"):
            self.assertEqual(self.p.run("decision", "open", "--kind", "install").returncode, 6)
        self.assertEqual(self.p.decisions(), [])

    def pending_npx(self):
        """D1 offers the npx command, D2 keeps the gate pending after D1 is spent."""
        self.p.ok(*OPEN, NPX)
        self.p.ok("decision", "open", "--kind", "commit", "--command", COMMIT)

    def test_a_pick_from_another_session_does_not_pass_a_pending_gate(self):
        self.pending_npx()
        self.p.pick("D1", 2, session="another")
        out = guard(self.p, NPX)
        self.assertEqual(decision_of(out), "deny", out[:400])
        self.assertIn("DECISION_PENDING", reason(out))

    def test_a_subagent_does_not_spend_the_pick_and_its_git_commit_stays_refused(self):
        """The hook reads a call with an agent_id as no session that can answer a dialog: the pending gate is not
        applied to it and, `npx` being no guarded command, it is not refused either -- but it spends nothing, so
        the human's pick stays for the session; the git consent rule refuses the subagent's commit."""
        self.pending_npx()
        self.p.pick("D1", 2)
        guard(self.p, NPX, agent_id="a1")
        self.assertEqual([e["type"] for e in self.p.ledger()], ["pick"], "the subagent spent nothing")
        out = guard(self.p, COMMIT, agent_id="a1")
        self.assertEqual(decision_of(out), "deny", out[:400])
        self.assertIn("CONSENT_REQUIRED", reason(out))

    def test_a_pick_after_its_window_does_not_pass_a_pending_gate(self):
        self.pending_npx()
        self.p.pick("D1", 2, ago=200)
        out = guard(self.p, NPX)
        self.assertEqual(decision_of(out), "deny", out[:400])
        self.assertIn("DECISION_PENDING", reason(out))

    def test_a_spent_pick_does_not_pass_a_pending_gate_again(self):
        self.pending_npx()
        self.p.pick("D1", 2)
        self.assertEqual(decision_of(guard(self.p, NPX)), "allow")
        again = guard(self.p, NPX)
        self.assertEqual(decision_of(again), "deny", again[:400])
        self.assertIn("DECISION_PENDING", reason(again))

    def test_approve_of_a_full_irreversible_task_stays_refused_through_a_pick(self):
        self.p.start("--mode", "full_irreversible", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=tas.CLEAN)
        self.p.ok("close")
        argv = ["approve", "--by", "me", "--confirm", "it drops nothing"]
        self.p.append(type="pick", id="C1", decision="D1", option=2, order=1, session=tas.DIALOG_SESSION,
                      label="python3 %s --root %s %s" % (tas.STATE, self.p.root, shlex.join(argv)),
                      expires_at=tas.stamp(time.time() + 120))
        refused = self.p.run(*argv)
        self.assertEqual(refused.returncode, 5, refused.stdout)
        self.assertFalse(self.p.state()["human_approval"]["granted"])

    def test_every_memory_verb_but_enable_is_not_a_valid_label(self):
        head = ["python3", tas.STATE, "--root", self.p.root, "memory"]
        for verb in ("disable", "cleanup", "pack", "redact", "migrate --apply", "status", "export", "show T-1",
                     "verify", "search x", "risk add", "risks", "Enable"):
            with self.subTest(verb):
                self.assertFalse(rr_labels.state_label_ok(head[2:] + shlex.split(verb)), verb)
                self.assertFalse(hook_dialog.state_label_ok(head + shlex.split(verb)), verb)
        self.assertTrue(rr_labels.state_label_ok(head[2:] + ["enable"]), "not vacuous")

    def test_the_update_script_with_confirm_delete_is_not_a_valid_label(self):
        for label in ("python3 /p/skills/project-update/update.py --confirm-delete ivan",
                      "python3 /p/skills/project-update/update.py --root /q --confirm-delete ivan"):
            with self.subTest(label):
                self.assertIsNotNone(rr_labels.validate_label(label))
                self.assertIsNotNone(hook_dialog.validate_label(label))

    def test_the_agent_cannot_settle_a_pick_for_the_human(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", COMMIT)
        done = self.p.run("decision", "settle", "--id", "D1", "--pick", "1")
        self.assertEqual(done.returncode, 5, done.stdout)
        self.assertIn("APPROVAL_REFUSED", done.stderr)
        self.assertEqual(len(self.p.decisions()), 1)

    def pending_batch(self):
        """A task with `batch on` refused once: D1 holds the command as option 2. Returns its argv."""
        self.p.start()
        self.assertEqual(self.p.run("batch", "on", "--by", "ivan").returncode, 5)
        return ["batch", "on", "--by", "ivan"]

    def assert_batch_refused(self, *argv):
        done = self.p.run(*argv)
        self.assertEqual(done.returncode, 5, done.stdout)
        self.assertIn("APPROVAL_REFUSED", done.stderr)
        self.assertFalse(self.p.state()["batch"]["on"])

    def test_batch_on_without_the_pick(self):
        self.assert_batch_refused(*self.pending_batch())

    def test_batch_on_with_a_pick_run_twice(self):
        argv = self.pending_batch()
        self.p.pick("D1", 2)
        self.p.ok(*argv)
        self.p.ok("batch", "off", "--by", "ivan", "--why", "standard loop again")
        self.assert_batch_refused(*argv)

    def test_batch_on_with_a_pick_of_another_session(self):
        argv = self.pending_batch()
        self.p.pick("D1", 2, session="another")
        self.assert_batch_refused(*argv)

    def test_batch_on_with_a_pick_after_its_window(self):
        argv = self.pending_batch()
        self.p.pick("D1", 2, ago=200)
        self.assert_batch_refused(*argv)

    def test_batch_on_with_a_pick_for_a_different_by_or_an_added_option(self):
        self.pending_batch()
        self.p.pick("D1", 2)
        self.assert_batch_refused("batch", "on", "--by", "someone-else")
        self.assert_batch_refused("batch", "on", "--by", "ivan", "--why", "an added option")

    def test_batch_off_and_every_other_batch_form_are_not_valid_labels(self):
        head = ["python3", tas.STATE, "--root", self.p.root, "batch"]
        for form in ("off --by ivan --why x", "off --by ivan", "on", "on --why x", "on --by", "on --by ivan --by you",
                     "on --by -x", "on --by ivan --batch", "status", "ON --by ivan", "on --by ivan extra"):
            with self.subTest(form):
                self.assertFalse(rr_labels.state_label_ok(head[2:] + shlex.split(form)), form)
                self.assertFalse(hook_dialog.state_label_ok(head + shlex.split(form)), form)
        for form in ("on --by ivan", "on --by ivan --why x"):
            self.assertTrue(rr_labels.state_label_ok(head[2:] + shlex.split(form)), "not vacuous")
            self.assertTrue(hook_dialog.state_label_ok(head + shlex.split(form)), "not vacuous")

    def test_a_pick_does_not_lift_a_git_rule(self):
        for command in ("git push origin main", "git commit --no-verify -m x"):
            with self.subTest(command):
                other = tas.DialogProject()
                self.addCleanup(other.close)
                other.ok("decision", "open", "--kind", "commit", "--command", command)
                other.pick("D1", 2)
                out = guard(other, command)
                self.assertEqual(decision_of(out), "deny", out[:400])


if __name__ == "__main__":
    unittest.main()
