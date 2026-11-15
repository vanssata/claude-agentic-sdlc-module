#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The installer wizard's pure half (spec ui-first-approvals R15-R17): bin/wizard.js turns what is
detected into steps, the choices into the equivalent flag line, and builds the review and final
box texts. Node is driven without a terminal or a home. Stdlib only.
"""
import json
import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import INSTALLER  # noqa: E402  pylint: disable=wrong-import-position

WIZARD = os.path.join(os.path.dirname(INSTALLER[1]), "wizard.js")


def call(name, *args):
    """wizard.<name>(...args) in node; the result parsed from JSON."""
    script = ("const w = require(%s);\nprocess.stdout.write(JSON.stringify(w[%s](...JSON.parse(process.argv[1]))));"
              % (json.dumps(WIZARD), json.dumps(name)))
    proc = subprocess.run([INSTALLER[0], "-e", script, json.dumps(list(args))],
                          capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    return json.loads(proc.stdout)


def ids(detected):
    """The step ids for a detection."""
    return [s["id"] for s in call("steps", detected)]


class TestSteps(unittest.TestCase):
    """R15: the stepper's steps, a step present only when it applies."""

    def test_both_runtimes_on_a_max_plan(self):
        """Every step, in the spec's order, with fable after the plan."""
        self.assertEqual(ids({"claude": True, "codex": True, "plan": "max"}),
                         ["runtimes", "plan", "fable", "context", "statusline", "codex plan", "review"])

    def test_claude_only_without_fable(self):
        """No Codex plan step; no fable step on pro."""
        self.assertEqual(ids({"claude": True, "codex": False, "plan": "pro"}),
                         ["runtimes", "plan", "context", "statusline", "review"])

    def test_codex_only(self):
        """No Claude plan, fable or statusline step."""
        self.assertEqual(ids({"claude": False, "codex": True}), ["runtimes", "context", "codex plan", "review"])

    def test_stepper_fields_and_descriptions(self):
        """step/of/trail name the stepper line; every option has a one-line description."""
        steps = call("steps", {"claude": True, "codex": True, "plan": "max20", "codexPlan": "plus"})
        self.assertEqual([s["step"] for s in steps], list(range(1, len(steps) + 1)))
        for step in steps:
            self.assertEqual(step["of"], len(steps))
            self.assertEqual(step["trail"], [s["id"] for s in steps])
            for item in step["items"]:
                self.assertTrue(item["note"] and "\n" not in item["note"], (step["id"], item))
        by_id = {s["id"]: s for s in steps}
        self.assertTrue(by_id["runtimes"]["multi"])
        self.assertEqual([i["checked"] for i in by_id["runtimes"]["items"]], [True, True])
        self.assertEqual(by_id["plan"]["items"][by_id["plan"]["initial"]]["value"], "max20")
        self.assertEqual(by_id["codex plan"]["items"][by_id["codex plan"]["initial"]]["value"], "plus")
        self.assertEqual([i["value"] for i in by_id["review"]["items"]], ["install", "back", "cancel"])

    def test_checked_follows_detection(self):
        """Only the detected runtime starts checked."""
        items = call("steps", {"claude": True, "codex": False})[0]["items"]
        self.assertEqual([(i["value"], i["checked"]) for i in items], [("claude", True), ("codex", False)])


class TestFlags(unittest.TestCase):
    """R17: the equivalent flag command."""

    def test_defaults_are_the_yes_defaults(self):
        """Nothing chosen beyond the target: --context default --yes."""
        got = call("flags", {"target": "both", "version": "4.3.0"})
        self.assertEqual(got["text"], "npx riskrails@4.3.0 --target both --context default --yes")
        self.assertEqual(got["argv"], got["text"].split(" "))

    def test_every_choice(self):
        """Flags in the spec's order."""
        got = call("flags", {"target": "both", "plan": "max", "fable": "no", "statusline": "own", "codexPlan": "plus",
                             "context": "economy", "version": "4.3.0"})
        self.assertEqual(got["text"], "npx riskrails@4.3.0 --target both --plan max --fable no --statusline own "
                                      "--codex-plan plus --context economy --yes")

    def test_target_drops_the_other_runtimes_flags(self):
        """A Claude-only line has no --codex-plan; a Codex-only line no --plan, --fable or --statusline."""
        choices = {"plan": "pro", "fable": "no", "statusline": "riskrails", "codexPlan": "pro", "version": "4.3.0"}
        claude = call("flags", dict(choices, target="claude"))["text"]
        codex = call("flags", dict(choices, target="codex"))["text"]
        self.assertEqual(claude, "npx riskrails@4.3.0 --target claude --plan pro --fable no --statusline riskrails "
                                 "--context default --yes")
        self.assertEqual(codex, "npx riskrails@4.3.0 --target codex --codex-plan pro --context default --yes")


class TestTexts(unittest.TestCase):
    """R16, R17: the review's lines and the final box."""

    def test_review_lines(self):
        """The heading, the dry run's text without its trailing newlines, then the command."""
        lines = call("reviewLines", "== claude: plan=max\nagents: a,b\n\n", "npx riskrails@4.3.0 --target claude --context default --yes")
        self.assertEqual(lines, ["Review — nothing is written until you pick Install", "", "== claude: plan=max",
                                 "agents: a,b", "", "same as: npx riskrails@4.3.0 --target claude --context default --yes"])

    def test_final_box(self):
        """A box of equal-width rows naming the next step and the command."""
        box = call("finalBox", {"command": "npx riskrails@4.3.0 --target both --context default --yes", "next": "/rr-setup"})
        self.assertEqual(len({len(row) for row in box}), 1)
        text = "\n".join(box)
        self.assertIn("next: /rr-setup", text)
        self.assertIn("same as: npx riskrails@4.3.0 --target both --context default --yes", text)
        self.assertTrue(box[0].startswith("┌") and box[-1].startswith("└"))

    def test_final_box_default_next(self):
        """Without a next step, the project setup is named."""
        self.assertIn("/rr-setup", "\n".join(call("finalBox", {"command": "c"})))


if __name__ == "__main__":
    unittest.main()
