#!/usr/bin/env python3
"""ui-first-approvals s11 (R7, R9): the state.py refusals name the dialog first when it is on, and say so in plain
words; with the dialog off each prints today's constant, byte for byte.

One table over the seven sites. `TODAY` holds each site's text as `git show HEAD:<file>` has it (the variable parts
are what the run prints: the path, the stage, the reason). Each site runs on a project with the dialog on and one with
it off; the exit code is today's in both. `close` for a full_irreversible task keeps its terminal command by design
(R5: a pick never approves it), so its row pins the text the same on and off."""

import os
import re
import shlex
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import test_ai_task_state as tas  # noqa: E402  pylint: disable=wrong-import-position
from rr_state import labels as rr_labels  # noqa: E402  pylint: disable=wrong-import-position

CMD = "python3 %s --root %s" % (shlex.quote(tas.STATE), "%s")
LOWER = ["start", "--goal", "tweak the widget", "--workflow", "feature", "--files", "src/widget.py",
         "--tests", "tests/test_widget.py", "--declare", "behaviour=2:x", "--declare", "domain=2:x",
         "--declare", "novelty=0:x", "--mode", "light", "--by", "test"]
AGENT_TOKENS = ("SUITE_BUDGET", "REVIEW_BUDGET", "weight.json", "state.py", "APPROVAL_REFUSED", "DIALOG_PENDING")


def why_of(err):
    return re.search(r"Refused because (.*)\.\n$", err, re.S).group(1)


def full_gate(p):
    p.start("--mode", "full", "--by", "test")
    p.ok("verify", "--scope", "all")
    p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=tas.CLEAN)
    p.ok("close")


def site_batch(p):
    p.start()
    return p.run("batch", "on", "--by", "ivan")


def site_start(p):
    return p.run(*LOWER)


def site_verify(p):
    p.start()
    for _ in range(2):
        p.ok("verify", "--scope", "suite")
    return p.run("verify", "--scope", "suite")


def site_review(p):
    p.start("--mode", "guarded", "--by", "test")
    for _ in range(2):
        p.ok("review", "--verdict", "blockers_open", "--tier", "BALANCED", "--report", "-", stdin=tas.CLEAN)
    return p.run("review", "--verdict", "pass", "--tier", "BALANCED", "--report", "-", stdin=tas.CLEAN)


def site_gate(p):
    full_gate(p)
    return p.run("verify", "--scope", "suite")


def site_questions(p):
    full_gate(p)
    path = os.path.join(p.root, ".ai", "reports", p.state()["task_id"], "task.md")
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    at = text.rindex("[Answer]:")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text[:at] + "[Answer]: A" + text[at + len("[Answer]:"):])
    session = os.path.join(p.root, ".ai", "state", "session.json")
    if os.path.exists(session):
        os.remove(session)
    return p.run("questions", "--sync", "--by", "ivan")


def site_approve(p):
    full_gate(p)
    return p.run("approve", "--by", "ivan")


def site_approve_irreversible(p):
    p.start("--mode", "full_irreversible", "--by", "test")
    p.ok("verify", "--scope", "all")
    p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=tas.CLEAN)
    p.ok("close")
    return p.run("approve", "--by", "ivan", "--confirm", "it drops nothing")


def site_close(p):
    p.start("--mode", "full_irreversible", "--by", "test")
    p.ok("verify", "--scope", "all")
    p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=tas.CLEAN)
    return p.run("close")


def today_batch(p, err):
    return ("APPROVAL_REFUSED — turning the batch loop on during a task lowers the rigor, so it is the human's. In "
            "their own terminal:\n  %s batch on --by \"<name>\"\nRefused because %s." % (CMD % shlex.quote(p.root), why_of(err)))


def today_start(p, err):
    mode = re.search(r"lowering the mode from (\w+) to light", err).group(1)
    return ("APPROVAL_REFUSED — lowering the mode from %s to light is a human's decision. Run it in your own "
            "terminal:\n  %s start … --mode light --by test\nRefused because %s."
            % (mode, CMD % shlex.quote(p.root), why_of(err)))


def today_verify(p, err):
    name = re.search(r"allows 2 \((.*?)\)", err).group(1)
    return ("SUITE_BUDGET — 2 suite runs; weight.json allows 2 (%s). Running it again is not the next move: the "
            "human decides. In their own terminal:\n  %s verify --scope suite --by \"<name>\""
            % (name, CMD % shlex.quote(p.root)))


def today_review(p, err):
    name = re.search(r"allows 2 \((.*?)\)", err).group(1)
    return ("REVIEW_BUDGET — 2 review passes; weight.json allows 2 (%s). The next verdict is the human's, in their "
            "own terminal:\n  %s review --verdict <verdict> --tier BALANCED --by \"<name>\"" % (name, CMD % shlex.quote(p.root)))


def today_gate(p, err):  # pylint: disable=unused-argument
    path = re.search(r"unanswered in (\S+):", err).group(1)
    stage = re.search(r"Stage stays at (\S+)\.", err).group(1)
    return ("QUESTIONS_PENDING — 1 unanswered in %s: G1. G1 is the approval gate: run 'state.py approve --by "
            "\"<name>\"' or 'state.py reject --by \"<name>\" --why \"<text>\"' in your own terminal. Stage stays at "
            "%s." % (path, stage))


def today_questions(p, err):  # pylint: disable=unused-argument
    return ("APPROVAL_REFUSED — there is no .ai/state/session.json, so no human turn can be seen. Fill the answer, "
            "tell the session, and sync again, or run in your own terminal:\n  %s approve --by ivan"
            % (CMD % shlex.quote(p.root)))


def today_approve(p, err):
    gate = re.search(r"on (G\d+) in (\S+) and tell", err)
    return ("APPROVAL_REFUSED — approval happens outside the agent. Run in your own terminal:\n  %s approve --by ivan\n"
            "or set [Answer]: A on %s in %s and tell the session to sync. An unattended run exports AI_UNATTENDED=1 in "
            "the launcher's environment; the journal then records the approval as unattended.\nRefused because %s."
            % (CMD % shlex.quote(p.root), gate.group(1), gate.group(2), why_of(err)))


# name: (run, today's text, exit code, a phrase the dialog-on text opens its refusal with)
SITES = {
    "batch on": (site_batch, today_batch, 5, "APPROVAL_REFUSED — turning the batch loop on during a task is the human's."),
    "lowering the mode": (site_start, today_start, 5, "APPROVAL_REFUSED — lowering the mode from "),
    "suite budget": (site_verify, today_verify, 6, "SUITE_BUDGET — 2 suite runs; weight.json allows 2 ("),
    "review budget": (site_review, today_review, 6, "REVIEW_BUDGET — 2 review passes; weight.json allows 2 ("),
    "the gate": (site_gate, today_gate, 4, "QUESTIONS_PENDING — 1 unanswered in "),
    "approve": (site_approve, today_approve, 5, "APPROVAL_REFUSED — 'state.py approve' is the human's."),
    "gate questions": (site_questions, today_questions, 5, "APPROVAL_REFUSED — 'state.py approve' is the human's."),
}


class TestDialogFirst(unittest.TestCase):
    """R7: dialog on, "dialog" before "terminal"; dialog off, today's constant."""

    def test_on_the_refusal_names_the_dialog_before_the_terminal(self):
        for name, (run, _, code, opening) in SITES.items():
            with self.subTest(name):
                p = tas.DialogProject()
                self.addCleanup(p.close)
                done = run(p)
                self.assertEqual(done.returncode, code, done.stderr)
                self.assertTrue(done.stderr.startswith("state.py: " + opening), done.stderr)
                self.assertIn("dialog", done.stderr)
                self.assertLess(done.stderr.index("dialog"), done.stderr.index("terminal"), done.stderr)
                self.assertIn("Refused because ", done.stderr)
                self.assertIn("DIALOG_PENDING D1", done.stdout + done.stderr)

    def test_off_the_text_is_todays_constant_byte_for_byte(self):
        for name, (run, today, code, _) in SITES.items():
            with self.subTest(name):
                p = tas.DialogProject(on=False)
                self.addCleanup(p.close)
                done = run(p)
                self.assertEqual(done.returncode, code, done.stderr)
                self.assertEqual(done.stderr, "state.py: " + today(p, done.stderr) + "\n")
                self.assertNotIn("DIALOG_PENDING", done.stdout + done.stderr)

    def test_unattended_is_todays_text_too(self):
        """Under AI_UNATTENDED no dialog is on and the human route passes; the budgets' no-`--by` text is today's."""
        p = tas.DialogProject()
        self.addCleanup(p.close)
        p.start()
        for _ in range(2):
            p.ok("verify", "--scope", "suite")
        done = p.run("verify", "--scope", "suite", human=True)
        self.assertEqual(done.returncode, 6, done.stderr)
        self.assertEqual(done.stderr, "state.py: " + today_verify(p, done.stderr) + "\n")

    def test_close_of_a_full_irreversible_task_keeps_the_terminal_command_on_and_off(self):
        """By design (R5): no pick approves a full_irreversible task, so the hand-over names no dialog."""
        outs = []
        for on in (True, False):
            p = tas.DialogProject(on=on)
            self.addCleanup(p.close)
            done = site_close(p)
            self.assertEqual(done.returncode, 0, done.stderr)
            self.assertIn("approve in your own terminal, then run close again:\n  %s approve --by \"<name>\" --confirm"
                          % (CMD % shlex.quote(p.root)), done.stdout)
            self.assertNotIn("DIALOG_PENDING", done.stdout)
            outs.append(re.sub(r"T-\S+", "T", done.stdout))
        self.assertEqual(outs[0].count("\n"), outs[1].count("\n"))

    def test_approve_keeps_the_answer_route_after_the_dialog_sentence(self):
        p = tas.DialogProject()
        self.addCleanup(p.close)
        done = site_approve(p)
        self.assertRegex(done.stderr.rstrip(), r" Or set \[Answer\]: A on G1 in \S+ and tell the session to sync\.$")

    def test_approve_of_a_full_irreversible_task_is_todays_text_on_and_off(self):
        for on in (True, False):
            p = tas.DialogProject(on=on)
            self.addCleanup(p.close)
            done = site_approve_irreversible(p)
            self.assertEqual(done.returncode, 5, done.stderr)
            self.assertEqual(done.stderr, "state.py: " + today_approve(p, done.stderr) + "\n")

    def test_the_third_route_of_the_gate_questions_is_kept(self):
        p = tas.DialogProject()
        self.addCleanup(p.close)
        done = site_questions(p)
        self.assertTrue(done.stderr.rstrip().endswith("Or fill the [Answer]: line, tell the session, and sync again."),
                        done.stderr)


class TestPlainWords(tas.DialogBase):
    """R9: the question each opener shows is in plain words; each command option carries its stored description."""

    def check(self, run, sentence):
        done = run(self.p)
        [question] = self.payload(done)["questions"]
        for token in AGENT_TOKENS:
            self.assertNotIn(token, question["question"])
        self.assertIn(sentence, question["question"])
        [decision] = self.p.decisions()
        commands = [o for o in decision["options"] if o["kind"] == "command"]
        self.assertTrue(commands)
        for option in commands:
            self.assertEqual(option["description"], rr_labels.describe(shlex.split(option["label"])))
        shown = [o["description"] for o in question["options"]]
        self.assertEqual(shown[1:], [o["description"] for o in commands])

    def test_the_suite_budget_question(self):
        self.check(site_verify, "The test suite has run 2 times; this task allows 2. Run it once more?")

    def test_the_review_budget_question(self):
        self.check(site_review, "2 review passes so far; this task allows 2. The next verdict is yours.")

    def test_the_batch_question(self):
        self.check(site_batch, "Turn the batch loop on for this task? It lowers the rigor for the rest of the task")

    def test_the_mode_question(self):
        self.check(site_start, "The task's weight says mode ")
        [decision] = self.p.decisions()
        self.assertIn("Lower it to light (by test)?", decision["question"])


if __name__ == "__main__":
    unittest.main()
