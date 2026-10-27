#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
ai-scope-guard: fixtures plus the stage/state properties that must disarm it.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import (FIXTURES, PLUGIN, HookAsserts, guard, codex_fixtures, fixtures,  # noqa: E402  pylint: disable=wrong-import-position
                           run)

TWIN_OF = "test-ai-scope-guard.sh"

GUARD = guard("scope")  # the shim hooks/ai-scope-guard.sh ran exactly this until 3.5


def edit(cwd, path):
    return {"hook_event_name": "PreToolUse", "tool_name": "Edit", "cwd": cwd, "tool_input": {"file_path": path}}


class TestAiScopeGuard(HookAsserts, unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "project")
        os.makedirs(os.path.join(self.root, ".ai", "state"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def put_state(self, state, name="current.json"):
        with open(os.path.join(self.root, ".ai", "state", name), "w", encoding="utf-8") as fh:
            json.dump(state, fh)

    def write_state(self, stage, step="1", name="current.json"):
        self.put_state({
            "task_id": "T-2026-09-09-001",
            "goal": "add a fee to the payment gateway",
            "workflow": "feature",
            "risk_tier": "T4",
            "current_stage": stage,
            "approved_plan": {
                "ref": ".ai/reports/T-2026-09-09-001/implementation-plan.md",
                "current_step_id": step,
                "steps": [
                    {"step_id": "1",
                     "description": "add the fee calculation",
                     "allowed_files": ["src/Payment/*.php", "tests/Payment/*.php"],
                     "forbidden_files": ["src/Payment/LegacyGateway.php"],
                     "forbidden_reason": "legacy gateway behaviour is frozen for this task",
                     "status": "in_progress",
                     "required_tests": ["tests/Payment/GatewayTest.php"]},
                ],
            },
        }, name)

    def out(self, payload):
        return run(GUARD, payload)[1]

    def test_stage_implementation(self):
        self.write_state("implementation", "1")
        self.assertFixtures(GUARD, fixtures(os.path.join(FIXTURES, "scope-guard"), self.root))

    def test_codex_apply_patch_payloads(self):
        self.write_state("implementation", "1")
        self.assertFixtures(GUARD, codex_fixtures("scope", self.root))
        out_of_scope = next(p for label, _, p in codex_fixtures("scope", self.root)
                            if label.startswith("21-scope-apply-patch-out-of-scope.json"))
        with self.subTest("an out-of-scope patch is refused with the SCOPE_CHANGE_REQUIRED signal"):
            self.assertIn("SCOPE_CHANGE_REQUIRED", self.out(out_of_scope))
        self.assertFailsOpen(GUARD, "a malformed Codex payload fails open", "{ not json")

    def test_disarmed_states(self):
        payload = edit(self.root, self.root + "/src/Order/OrderProcessor.php")
        self.write_state("plan", "1")
        self.assertEqual(self.out(payload), "", "stage=plan: out-of-scope edit is not blocked")
        self.write_state("implementation", "")
        self.assertEqual(self.out(payload), "", "no current_step_id: not blocked")
        self.write_state("implementation", "99")
        self.assertEqual(self.out(payload), "", "unknown step id: fails open")
        os.remove(os.path.join(self.root, ".ai", "state", "current.json"))
        self.assertEqual(self.out(payload), "", "no state file: not blocked")
        bare = os.path.join(self.tmp, "bare")
        os.makedirs(os.path.join(bare, "src"))
        self.assertEqual(self.out(edit(bare, bare + "/src/x.php")), "", "no .ai/: not blocked")
        # The deny message must carry the literal signal the manager parses for.
        self.write_state("implementation", "1")
        self.assertIn("SCOPE_CHANGE_REQUIRED", self.out(payload),
                      "deny message contains the SCOPE_CHANGE_REQUIRED signal")

    def test_either_state_file_name_arms_the_guard(self):
        # R34: state.json from 3.4b; current.json is still read for one version.
        payload = edit(self.root, self.root + "/src/Order/OrderProcessor.php")
        self.write_state("implementation", "1", name="state.json")
        self.assertIn("SCOPE_CHANGE_REQUIRED", self.out(payload), "state.json alone arms the guard")
        self.write_state("plan", "1")
        self.assertIn("SCOPE_CHANGE_REQUIRED", self.out(payload),
                      "with both names, state.json is the one read")
        self.write_state("plan", "1", name="state.json")
        self.write_state("implementation", "1")
        self.assertEqual(self.out(payload), "", "with both names, the legacy file is not read")

    def test_a_step_id_used_twice(self):
        # Every step carrying the current id contributes — not just the first one
        # found. A plan should never reissue a step id, but when it does (an
        # amendment that reuses one, a bug in state.py) the rules of all of them
        # apply. The case that matters: an unrestricted first duplicate must not
        # cancel what a later one forbids, because a guard with empty lists allows
        # everything.
        def dup_state(first):
            self.put_state({"task_id": "T-1", "current_stage": "implementation", "approved_plan": {
                "current_step_id": "1", "steps": [
                    {"step_id": "1", "allowed_files": first, "forbidden_files": [],
                     "forbidden_reason": "first reason"},
                    {"step_id": "1", "allowed_files": ["tests/x.php"], "forbidden_files": ["src/secret.php"],
                     "forbidden_reason": "second reason"}]}})

        def edit_of(rel):
            return self.out(edit(self.root, self.root + "/" + rel))
        for first in (["src/a.php"], []):
            dup_state(first)
            label = json.dumps(first, separators=(",", ":"))
            with self.subTest(Template("first step allowed_files=$first: the second step's forbidden_files still bite")
                              .substitute(first=label)):
                self.assertIn("explicitly forbidden", edit_of("src/secret.php"))
            with self.subTest(Template("first step allowed_files=$first: the second step's allowed_files count too")
                              .substitute(first=label)):
                self.assertEqual(edit_of("tests/x.php"), "")
        dup_state(["src/a.php"])
        self.assertEqual(edit_of("src/a.php"), "", "the first step's allowed_files count as well")
        self.assertIn("SCOPE_CHANGE_REQUIRED", edit_of("src/nowhere.php"), "a file in neither step is still out of scope")


if __name__ == "__main__":
    unittest.main()
