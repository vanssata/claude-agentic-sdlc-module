#!/usr/bin/env python3
"""ui-first-approvals s11 (R2): `batch on` takes the dialog's pick.

With the dialog on and no pick, `batch on --by` opens a decision (header "Batch") and is refused with the dialog-first
text, exit 5; the option the human picks, run verbatim, passes once as `via dialog` and `batch_set` carries the consent
id. With the dialog off, and under AI_UNATTENDED, today's behaviour. Runs in the scratch project of
tests/test_ai_task_state.py (`DialogProject`)."""

import os
import re
import shlex
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import test_ai_task_state as tas  # noqa: E402  pylint: disable=wrong-import-position

BATCH_ON = ["batch", "on", "--by", "ivan"]
TODAY = ("APPROVAL_REFUSED — turning the batch loop on during a task lowers the rigor, so it is the human's. In their "
         "own terminal:\n  python3 %s --root %s batch on --by \"<name>\"\nRefused because %s.")


class TestBatchOnTakesThePick(tas.DialogBase):
    """R2: the pick is this session's, equal to the command, inside its window, and spent once."""

    def label(self):
        return self.p.decisions()[0]["options"][1]["label"]

    def refused(self):
        self.p.start()
        done = self.p.run(*BATCH_ON)
        self.assertEqual(done.returncode, 5, done.stdout)
        return done

    def test_no_pick_opens_the_batch_decision_and_refuses_dialog_first(self):
        done = self.refused()
        [decision] = self.p.decisions()
        self.assertEqual((decision["header"], decision["kind"], decision["opened_by"]), ("Batch", "human_set", "batch on"))
        [question] = self.payload(done)["questions"]
        self.assertEqual(question["options"][0]["label"], "Keep the standard loop")
        self.assertEqual(self.label(), "python3 %s --root %s batch on --by ivan" % (tas.STATE, shlex.quote(self.p.root)))
        self.assertTrue(done.stderr.startswith(
            "state.py: APPROVAL_REFUSED — turning the batch loop on during a task is the human's. Ask them in the "
            "dialog: send DIALOG_PENDING D1 (printed above), then run the command they pick, verbatim, once. Or they "
            "run, in their own terminal:\n  python3 %s --root %s batch on --by \"<name>\"\nRefused because "
            % (shlex.quote(tas.STATE), shlex.quote(self.p.root))), done.stderr)
        self.assertFalse(self.p.state()["batch"]["on"])

    def test_the_picked_command_passes_with_via_dialog_and_the_consent_id(self):
        self.refused()
        cid = self.p.pick("D1", 2)
        self.p.ok(*BATCH_ON)
        self.assertTrue(self.p.state()["batch"]["on"])
        [event] = self.journal("batch_set")
        self.assertEqual((event["data"]["via"], event["data"]["consent"], event["data"]["on"]), ("dialog", cid, True))
        self.assertIn("use", [line["type"] for line in self.p.ledger()], "the pick is spent")

    def test_the_pick_is_spent_once(self):
        self.refused()
        self.p.pick("D1", 2)
        self.p.ok(*BATCH_ON)
        self.p.ok("batch", "off", "--by", "ivan", "--why", "back to the standard loop")
        again = self.p.run(*BATCH_ON)
        self.assertEqual(again.returncode, 5, again.stdout)
        self.assertFalse(self.p.state()["batch"]["on"])

    def test_keep_the_standard_loop_runs_nothing(self):
        self.refused()
        self.p.pick("D1", 1)
        self.p.ok("decision", "settle", "--id", "D1")
        self.assertFalse(self.p.state()["batch"]["on"])

    def test_the_decision_is_not_opened_again_for_a_batch_already_on(self):
        self.p.start("--batch", "--by", "ivan")
        done = self.p.ok(*BATCH_ON)
        self.assertIn("batch is already on", done.stdout)
        self.assertEqual(self.p.decisions(), [])


class TestBatchOnOffAndUnattended(tas.DialogBase):
    """Today's behaviour where the dialog is not the route."""

    def test_dialog_off_prints_today_and_opens_nothing(self):
        off = tas.DialogProject(on=False)
        self.addCleanup(off.close)
        off.start()
        done = off.run(*BATCH_ON)
        self.assertEqual(done.returncode, 5, done.stdout)
        why = re.search(r"Refused because (.*)\.\n$", done.stderr, re.S).group(1)
        self.assertEqual(done.stderr, "state.py: " + TODAY % (shlex.quote(tas.STATE), shlex.quote(off.root), why) + "\n")
        self.assertNotIn("DIALOG_PENDING", done.stdout)
        self.assertEqual(off.decisions(), [])

    def test_unattended_passes_as_before_and_opens_nothing(self):
        self.p.start()
        self.p.ok(*BATCH_ON, human=True)
        self.assertEqual(self.journal("batch_set")[-1]["data"]["via"], "unattended")
        self.assertEqual(self.p.decisions(), [])


if __name__ == "__main__":
    unittest.main()
