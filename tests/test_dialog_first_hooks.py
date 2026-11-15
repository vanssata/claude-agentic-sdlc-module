#!/usr/bin/env python3
"""R6: the hook texts name the dialog first when it is on, and no decision moves.

One table row per text: with the dialog on, the word "dialog" comes before
"terminal" (or the text names no terminal); with the dialog off, and under
AI_UNATTENDED, the text is today's constant byte for byte, or the hook says
nothing at all where today's route never reaches the text. The allow/deny
decision of each case is pinned beside the text."""

import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from guard import paths_base  # noqa: E402  pylint: disable=wrong-import-position
from guard_harness import decision as decision_of, hook_output  # noqa: E402  pylint: disable=wrong-import-position
import test_dialog_consent as tc  # noqa: E402  pylint: disable=wrong-import-position
import test_dialog_gate as tg  # noqa: E402  pylint: disable=wrong-import-position

APPROVE_HEAD = "Refusing 'state.py approve' from an agent session."
OTHER_COMMIT = "git commit -m other -- b.py"


def dialog_first(case, text):
    """The dialog route is named, and the terminal, when named, comes after it."""
    case.assertIn("dialog", text)
    if "terminal" in text:
        case.assertLess(text.index("dialog"), text.index("terminal"), text)


class TestGuardTexts(unittest.TestCase):
    """The PreToolUse refusals: (command, task, setup) -> (decision, reason) per switch state."""

    def verdict(self, command, dialog_on=True, task=False, env=None, setup=None, **guard):
        p = tc.Project(dialog_on=dialog_on, task=task)
        self.addCleanup(p.close)
        p.env.update(env or {})
        if setup:
            setup(p)
        out = p.guard(command, **guard)
        return decision_of(out), p.reason(out)

    def test_approve_refusal(self):
        today = APPROVE_HEAD + paths_base.WHY_APPROVE
        got, reason = self.verdict(tc.APPROVE, task=True)
        self.assertEqual(got, "deny")
        self.assertTrue(reason.startswith(APPROVE_HEAD), reason)
        dialog_first(self, reason)
        self.assertNotEqual(reason, today)
        self.assertEqual(self.verdict(tc.APPROVE, task=True, dialog_on=False), ("deny", today), "dialog off")
        self.assertEqual(self.verdict(tc.APPROVE, task=True, env={"AI_UNATTENDED": "1"})[0], "allow",
                         "unattended: the human's route is not asked")

    def test_consent_required_no_live_pick(self):
        got, reason = self.verdict(tc.COMMIT)
        self.assertEqual(got, "deny")
        self.assertTrue(reason.startswith("CONSENT_REQUIRED"), reason)
        dialog_first(self, reason)
        self.assertEqual(self.verdict(tc.COMMIT, dialog_on=False)[0], "allow", "dialog off: no consent rule")
        self.assertEqual(self.verdict(tc.COMMIT, env={"AI_UNATTENDED": "1"})[0], "allow", "unattended")

    def test_consent_required_closed_session_keeps_the_terminal_route(self):
        got, reason = self.verdict(tc.COMMIT, agent_id="a1")
        self.assertEqual(got, "deny")
        self.assertTrue(reason.startswith("CONSENT_REQUIRED — this session cannot answer the dialog"), reason)
        self.assertNotIn("Ask the human in the dialog", reason)

    def test_consent_mismatch(self):
        def one_pick(p):
            p.decide(tc.dec("D1", "commit", tc.COMMIT))
            p.pick("D1", 2, 1, tc.COMMIT)
        got, reason = self.verdict(OTHER_COMMIT, setup=one_pick)
        self.assertEqual(got, "deny")
        self.assertTrue(reason.startswith("CONSENT_MISMATCH"), reason)
        dialog_first(self, reason)
        self.assertEqual(self.verdict(OTHER_COMMIT, dialog_on=False)[0], "allow", "dialog off: no gate")


class TestStopFallback(unittest.TestCase):
    """hooks/dialog-gate.py's last word, once the blocks are spent."""

    def stop(self, scratch, **env):
        code, out = tg.run_gate(scratch, dict(tg.spike("claude/stop"), stop_hook_active=True), env)
        self.assertEqual(code, 0, out)
        return hook_output(out)

    def scratch(self, on=True):
        s = tg.Scratch(on=on)
        self.addCleanup(s.close)
        s.decide(tg.decision("D1", "Commit a.py?", "Commit", [("choice", tg.SAFE), ("command", tg.COMMIT)]))
        return s

    def test_fallback_names_the_dialog_first(self):
        text = self.stop(self.scratch())["systemMessage"]
        self.assertTrue(text.startswith("DECISION_PENDING D1 is still open. Reply in this chat (for example "
                                        "\"ask me again\") and the session sends you the dialog; or settle it in "
                                        "your terminal: python3 "), text)
        dialog_first(self, text)
        self.assertIn("decision settle --id D1 --pick <n>", text)

    def test_dialog_off_says_nothing(self):
        self.assertEqual(self.stop(self.scratch(on=False)), {})
        self.assertEqual(self.stop(self.scratch(), AI_UNATTENDED="1"), {})

    def test_a_new_prompt_resets_the_count(self):
        s = self.scratch()
        tg.prompt(s)
        self.assertEqual(self.stop_without_active(s).get("decision"), "block")
        tg.prompt(s)
        self.assertEqual(self.stop_without_active(s).get("decision"), "block")
        self.assertEqual([e["turn"] for e in s.ledger()], [1, 2])

    @staticmethod
    def stop_without_active(scratch):
        return hook_output(tg.run_gate(scratch, tg.spike("claude/stop"))[1])


if __name__ == "__main__":
    unittest.main()
