#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
runtime-gate.py under Codex: an EXPERT agent must fall back to STRONG while the
expert model cannot serve the account — and must NOT fall back because an agent
gave a poor answer. Both halves are tested here; the second one is the reason
the gate matches explicit capacity signals instead of the word "error".
The gate runs from a copy under a .codex/hooks/ directory, which is how
detect_runtime() knows it is the Codex gate; the legacy CODEX_MODEL_GATE* names
are still honoured, so they stay in use here.

The sections share one copy of the gate, one Codex home and one state file, in
the shell suite's order: test_NN_ names keep it.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import FIXTURES, PLUGIN  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-runtime-gate-codex.sh"

SRC_GATE = os.path.join(PLUGIN, "hooks", "runtime-gate.py")
FIX = os.path.join(FIXTURES, "codex-hooks")
GATE_VARS = re.compile(r"^(AI_RUNTIME_GATE|CLAUDE_FABLE_GATE|CODEX_MODEL_GATE)[A-Z_]*$")
UNSET = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_AGENTIC_SHARED", "CLAUDE_PROJECT_DIR",
         "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SESSION_ATTENDED", "AI_UNATTENDED")


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def has_line(pattern, text):
    return re.search(pattern, text, re.M) is not None


def hso(out):
    """hookSpecificOutput of a hook's stdout, {} when there is none."""
    try:
        return json.loads(out).get("hookSpecificOutput") or {}
    except (ValueError, AttributeError):
        return {}


def updated(out):
    return hso(out).get("updatedInput") or {}


class TestRuntimeGateCodex(unittest.TestCase):  # pylint: disable=too-many-public-methods
    @classmethod
    def setUpClass(cls):
        cls.tmp = tmp = tempfile.mkdtemp()
        cls.gate_path = os.path.join(tmp, ".codex", "hooks", "runtime-gate.py")
        os.makedirs(os.path.dirname(cls.gate_path))
        shutil.copy(SRC_GATE, cls.gate_path)
        os.chmod(cls.gate_path, 0o755)
        env = {k: v for k, v in os.environ.items() if k not in UNSET and not GATE_VARS.match(k)}
        env["HOME"] = os.path.join(tmp, "home")
        cls.env = env
        # A scratch Codex home whose custom agents pin the same models the installer does.
        cls.codex_home = home = os.path.join(tmp, "codex")
        os.makedirs(home + "/agents")
        subprocess.run([sys.executable, os.path.join(PLUGIN, "scripts", "render-codex-agents.py"), "--src", PLUGIN,
                        "--out", home + "/agents"], env=env, stdout=subprocess.DEVNULL, check=True)
        # No shipped role pins EXPERT since redesign 2.4; the reroute is generic, so an
        # EXPERT role and its STRONG twin are fixtures here.
        write(home + "/agents/ai-expert.toml", 'name = "ai-expert"\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "xhigh"\n')
        write(home + "/agents/ai-expert-strong.toml",
              'name = "ai-expert-strong"\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n')
        write(home + "/config.toml", 'model = "gpt-5.6-sol"\n\n[agents]\ndefault_subagent_model = "gpt-5.6-terra"\n')
        cls.state = os.path.join(tmp, "state.json")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ helpers
    def gate_rc(self, *args, stdin="", env=None, stderr=False):
        """(exit code, stdout[+stderr]) of the gate copy, with the Codex home and state pinned."""
        if not isinstance(stdin, str):
            stdin = json.dumps(stdin)
        full = dict(self.env, CODEX_HOME=self.codex_home, CODEX_MODEL_GATE_STATE=self.state)
        full.update(env or {})
        proc = subprocess.run([self.gate_path, *args], input=stdin, capture_output=True, text=True, env=full,
                              check=False)
        return proc.returncode, proc.stdout + (proc.stderr if stderr else "")

    def gate(self, *args, stdin="", env=None):
        return self.gate_rc(*args, stdin=stdin, env=env)[1]

    def fixture(self, name):
        with open(os.path.join(FIX, name), encoding="utf-8") as fh:
            return json.dumps(json.load(fh)["payload"]).replace("__ROOT__", self.tmp)

    def feed(self, name, env=None):
        """Send one fixture payload to the gate; its stdout."""
        return self.gate(stdin=self.fixture(name), env=env)

    def reset(self):
        if os.path.lexists(self.state):
            os.remove(self.state)

    def call(self, tool_input):
        return self.gate(stdin={"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": self.tmp,
                                "tool_input": tool_input})

    def status(self):
        return self.gate("status")

    # ------------------------------------------------------------------ sections
    def test_01_an_inactive_gate_stays_out_of_the_way(self):
        self.reset()
        out = self.feed("30-agent-expert-launch.json")
        self.assertEqual(out, "", "an expert launch is not rewritten while the model is available")
        self.assertTrue(has_line("^inactive", self.status()), "status reports inactive")

    def test_02_an_availability_failure_activates_the_gate(self):
        self.reset()
        self.feed("32-subagent-stop-rate-limit.json")
        self.assertTrue(has_line("^active: gpt-6-astra -> gpt-5.6-sol", self.status()),
                        "a rate limit on the expert model activates the gate")
        self.assertIn("rate_limit", self.status(), "status names the reason")
        self.assertIn("SubagentStop", self.status(), "status names the source")

    def test_03_while_active_an_expert_role_is_rerouted_to_its_strong_twin(self):
        # Codex applies a role's pinned model after the call's `model`, so rewriting
        # `model` cannot move ai-expert; rewriting agent_type to ai-expert-strong does.
        out = self.feed("30-agent-expert-launch.json")
        self.assertNotEqual(out, "", "the gate answers the launch")
        self.assertEqual(hso(out).get("permissionDecision"), "allow", "the launch is allowed, not blocked")
        self.assertEqual(updated(out).get("agent_type"), "ai-expert-strong", "agent_type is rewritten to the twin")
        self.assertFalse({"model", "model_reasoning_effort", "reasoning_effort"} & set(updated(out)),
                         "the twin's pinned model and effort decide, nothing else is injected")
        self.assertIsNotNone(updated(out).get("prompt"), "the rest of the spawn arguments are preserved")
        self.assertIn("is gpt-5.6-sol's, not gpt-6-astra's", hso(out).get("additionalContext") or "",
                      "the agent is told whose answer it is about to give")

    def test_04_a_balanced_launch_is_never_rewritten(self):
        out = self.feed("31-agent-balanced-launch.json")
        self.assertEqual(out, "", "an ai-discovery launch is untouched while the gate is active")

    def test_05_repeated_launches_keep_being_rewritten(self):
        out = self.feed("30-agent-expert-launch.json")
        self.assertEqual(updated(out).get("agent_type"), "ai-expert-strong", "a second launch is rerouted too")

    def test_06_a_poor_answer_is_not_an_availability_failure(self):
        self.reset()
        self.feed("33-subagent-stop-uncertain.json")
        self.assertTrue(has_line("^inactive", self.status()), "confidence: uncertain does not activate the gate")

    def test_07_a_failure_attributed_to_another_tier_does_not_activate_the_gate(self):
        self.reset()
        self.feed("34-subagent-stop-balanced-rate-limit.json")
        self.assertTrue(has_line("^inactive", self.status()), "a Terra rate limit leaves the expert tier alone")

    def test_08_the_record_expires(self):
        self.reset()
        self.gate("set", "60", "test")  # expiry is simulated below; a 1 s record can lapse before status reads it
        self.assertTrue(has_line("^active", self.status()), "a manual record activates the gate")
        with open(self.state, encoding="utf-8") as fh:
            data = json.load(fh)
        data["unavailable"]["until"] = int(time.time()) - 5
        write(self.state, json.dumps(data))
        self.assertTrue(has_line("^inactive", self.status()), "an expired record stops applying")
        out = self.feed("30-agent-expert-launch.json")
        self.assertEqual(out, "", "an expert launch runs on the expert model again after expiry")
        self.reset()
        script = ("import importlib.util, json, sys\n"
                  "spec = importlib.util.spec_from_file_location('gate', sys.argv[1])\n"
                  "gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)\n"
                  "gate.mark(2000000000.9, 'test', 'test')\n"
                  "print(json.load(open(gate.STATE))['unavailable']['until'])\n")
        env = dict(self.env, CODEX_HOME=self.codex_home, CODEX_MODEL_GATE_STATE=self.state)
        stored = subprocess.run([sys.executable, "-", self.gate_path], input=script, capture_output=True, text=True,
                                env=env, check=False).stdout
        self.assertEqual(stored.rstrip("\n"), "2000000001",
                         "a fractional expiry is rounded up, never ending the record early")

    def test_09_clear_re_enables_the_expert_model_early(self):
        self.gate("set", "3600", "manual")
        self.assertIn("cleared", self.gate("clear"), "clear reports what it did")
        self.assertTrue(has_line("^inactive", self.status()), "clear deactivates the gate")

    def test_10_a_roles_pinned_model_wins_over_an_explicit_model_on_the_spawn_as_in_codex(self):
        self.reset()
        self.gate("set", "3600", "manual")
        out = self.call({"agent_type": "ai-discovery", "model": "gpt-6-astra", "prompt": "x"})
        self.assertEqual(out, "", "an explicit expert model on a pinned cheap role is left alone (it runs on Terra)")
        out = self.call({"agent_type": "ai-expert", "model": "gpt-5.6-terra", "model_reasoning_effort": "xhigh",
                         "prompt": "x"})
        self.assertEqual(updated(out).get("agent_type"), "ai-expert-strong",
                         "an explicit cheap model does not take ai-expert past the gate")
        self.assertNotIn("model_reasoning_effort", updated(out),
                         "a caller's model_reasoning_effort (never a spawn argument) is dropped")

    def test_11_a_spawn_with_no_role_and_an_explicit_expert_model_gets_model_and_reasoning_effort(self):
        out = self.call({"model": "gpt-6-astra", "model_reasoning_effort": "xhigh", "prompt": "x"})
        u = updated(out)
        self.assertTrue(u.get("model") == "gpt-5.6-sol" and u.get("reasoning_effort") == "high"
                        and "model_reasoning_effort" not in u,
                        "model -> gpt-5.6-sol, reasoning_effort -> high, no model_reasoning_effort")

    def test_12_context_only_mode_explains_without_rewriting(self):
        out = self.feed("30-agent-expert-launch.json", env={"CODEX_MODEL_GATE_MODE": "context"})
        self.assertIsNone(hso(out).get("updatedInput"), "context mode does not rewrite the spawn arguments")
        self.assertIn("not rerouted", hso(out).get("additionalContext") or "",
                      "context mode says the launch is not rerouted")

    def test_13_the_gate_can_be_turned_off_entirely(self):
        out = self.feed("30-agent-expert-launch.json", env={"CODEX_MODEL_GATE": "off"})
        self.assertEqual(out, "", "CODEX_MODEL_GATE=off disables the rewrite")

    def test_14_malformed_input_fails_open(self):
        for bad in ("", "not json", "[]", '{"hook_event_name":"PreToolUse"}',
                    '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"oops"}',
                    '{"hook_event_name":"SubagentStop"}', '{"hook_event_name":"Nonsense","tool_name":"Agent"}'):
            with self.subTest(bad=bad):
                rc, out = self.gate_rc(stdin=bad, stderr=True)
                self.assertTrue(rc == 0 and out == "",
                                "fails open on: ${bad:-<empty>}".replace("${bad:-<empty>}", bad or "<empty>")
                                + ": exit %s, output: %s" % (rc, out))

    def test_15_an_unwritable_state_directory_does_not_break_a_spawn(self):
        rc, _ = self.gate_rc(stdin=self.fixture("30-agent-expert-launch.json"), stderr=True,
                             env={"CODEX_MODEL_GATE_STATE": "/proc/cannot/write.json"})
        self.assertEqual(rc, 0, "a state write failure still exits 0")

    def test_16_the_cli_reports_usage_for_an_unknown_command(self):
        rc, out = self.gate_rc("wibble", stderr=True)
        self.assertEqual(rc, 2, "an unknown command exits 2")
        self.assertIn("usage:", out, "it prints usage")


if __name__ == "__main__":
    unittest.main()
