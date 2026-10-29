#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
runtime-gate.py under Claude Code (the plugin path is not under a .codex/, so
detect_runtime() answers claude): records Fable unavailability from
StopFailure / PostToolUse / the statusline, rewrites model: fable -> opus on
PreToolUse:Agent while the record lives, and fails open. The legacy
CLAUDE_FABLE_GATE* names are still honoured, so they stay in use here. Then the
installer: the Fable branch is registered only on a Fable install, a later
non-Fable install strips it again, and the old fable-gate.py shim is retired.

The sections share one home, one state file and one project, in the shell
suite's order: test_NN_ names keep it.
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
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import PLUGIN  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-runtime-gate-fable.sh"
# `pass "$3"` is expect_route()'s label parameter; the labels it was called with
# are the cases below.
SHELL_MECHANICS = ("$3",)

GATE = os.path.join(PLUGIN, "hooks", "runtime-gate.py")
INSTALL = os.path.join(PLUGIN, "bin", "riskrails.js")  # the installer since 3.5
GATE_VARS = re.compile(r"^(AI_RUNTIME_GATE|CLAUDE_FABLE_GATE|CODEX_MODEL_GATE)[A-Z_]*$")
UNSET = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_AGENTIC_SHARED", "CLAUDE_PROJECT_DIR",
         "CLAUDE_CODE_SUBAGENT_MODEL", "CLAUDE_CODE_SESSION_ATTENDED", "AI_UNATTENDED", "CLAUDE_DIR")
PREFIX = '"$HOME/.claude/hooks/runtime-gate.py" statusline'
ORIG = 'bash ~/.claude/statusline-command.sh --flag "two words" \'single\''
FABLE_EVENTS = ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop", "StopFailure")


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def write_json(path, data):
    write(path, json.dumps(data))


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def read_text(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def has_line(pattern, text):
    return re.search(pattern, text, re.M) is not None


def hso(out):
    """hookSpecificOutput of a hook's stdout, {} when there is none."""
    try:
        return json.loads(out).get("hookSpecificOutput") or {}
    except (ValueError, AttributeError):
        return {}


def commands(settings, event=None):
    """Every hook command in a settings.json (of one event, or of all)."""
    hooks = settings.get("hooks") or {}
    events = [event] if event else list(hooks)
    return [h.get("command") or "" for e in events for entry in hooks.get(e) or []
            for h in entry.get("hooks") or []]


def gate_count(path):
    return sum("runtime-gate" in c for c in commands(read_json(path)))


def old_count(path):
    return sum("fable-gate" in c for c in commands(read_json(path)))


def settings_has_gate(path, event):
    return any("runtime-gate" in c for c in commands(read_json(path), event))


def now():
    return int(time.time())


def sub(out):
    """What `$(...)` makes of a command's output: no trailing newlines."""
    return out.rstrip("\n")


class TestRuntimeGateFable(unittest.TestCase):  # pylint: disable=too-many-public-methods
    @classmethod
    def setUpClass(cls):
        cls.tmp = tmp = tempfile.mkdtemp()
        home = os.path.join(tmp, "home")
        cls.cfg = cfg = os.path.join(home, ".claude")
        cls.state = os.path.join(tmp, "state", "fable-gate.json")
        # Isolate from the developer's own ~/.claude: agents, state and env.
        env = {k: v for k, v in os.environ.items() if k not in UNSET and not GATE_VARS.match(k)}
        env.update(HOME=home, CLAUDE_CONFIG_DIR=cfg, CLAUDE_FABLE_GATE_STATE=cls.state)
        cls.env = env
        os.makedirs(cfg + "/agents")
        os.makedirs(tmp + "/project/.claude/agents")
        write(cfg + "/agents/ai-expert.md",
              "---\nname: ai-expert\n# model: pinned\nmodel: fable\neffort: xhigh\n---\nbody\n")
        write(cfg + "/agents/ai-reviewer.md", "---\nname: ai-reviewer\nmodel: opus\neffort: high\n---\nbody\n")
        write(cfg + "/agents/architect.md", "---\nname: architect\nmodel: opus\n---\nbody\n")
        write(tmp + "/project/.claude/agents/architect.md", "---\nname: architect\nmodel: fable\n---\nproject override\n")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    # ------------------------------------------------------------------ helpers
    def run_cmd(self, argv, stdin="", env=None):
        """(exit code, stdout, stderr) of a command under the suite's env plus `env`."""
        if not isinstance(stdin, str):
            stdin = json.dumps(stdin)
        proc = subprocess.run(argv, input=stdin, capture_output=True, text=True,
                              env=dict(self.env, **(env or {})), check=False)
        return proc.returncode, proc.stdout, proc.stderr

    def gate_rc(self, *args, stdin="", env=None):
        rc, out, _ = self.run_cmd([sys.executable, GATE, *args], stdin, env)
        return rc, out

    def gate(self, *args, stdin="", env=None):
        return self.gate_rc(*args, stdin=stdin, env=env)[1]

    def node(self, claude_dir, *args, env=None):
        """The installer with CLAUDE_DIR set: stdout and stderr together, as `2>&1`."""
        _, out, err = self.run_cmd(["node", INSTALL, *args], env=dict(env or {}, CLAUDE_DIR=claude_dir))
        return out + err

    def bash_c(self, command, home, stdin):
        return self.run_cmd(["bash", "-c", command], stdin, {"HOME": home})[1]

    def reset_state(self):
        if os.path.lexists(self.state):
            os.remove(self.state)

    def set_marker(self, until):
        write_json(self.state, {"unavailable": {"until": until, "reason": "rate_limit", "source": "test"}})

    def until(self):
        return read_json(self.state)["unavailable"]["until"]

    def marker_active(self):
        return has_line("^active", self.gate("status"))

    def agent_run(self, tool_input, cwd=None, transcript="", env=None):
        payload = {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": cwd or self.tmp + "/elsewhere",
                   "tool_input": tool_input}
        if transcript:
            payload["transcript_path"] = transcript
        return self.gate_rc(stdin=payload, env=env)

    def agent_call(self, tool_input, cwd=None, transcript="", env=None):
        return self.agent_run(tool_input, cwd, transcript, env)[1]

    def routed_model(self, tool_input, cwd=None, transcript="", env=None):
        """The model after the hook, or "unchanged"."""
        out = self.agent_call(tool_input, cwd, transcript, env)
        if not out:
            return "unchanged"
        return (hso(out).get("updatedInput") or {}).get("model") or "malformed"

    def expect_route(self, expected, tool_input, label, cwd=None, transcript="", env=None):
        got = self.routed_model(tool_input, cwd, transcript, env)
        self.assertEqual(got, expected, "%s: expected %s, got %s" % (label, expected, got))

    def stop_failure(self, error, extra=None, env=None):
        payload = {"hook_event_name": "StopFailure", "cwd": "/nowhere", "error": error}
        payload.update(extra or {})
        return self.gate(stdin=payload, env=env)

    def post(self, tool_input, response, env=None, transcript=""):
        payload = {"hook_event_name": "PostToolUse", "tool_name": "Agent", "cwd": "/nowhere",
                   "tool_input": tool_input, "tool_response": response}
        if transcript:
            payload["transcript_path"] = transcript
        return self.gate(stdin=payload, env=env)

    def transcript(self, version):
        """Path of a transcript written by that Claude Code version."""
        path = "%s/transcript-%s.jsonl" % (self.tmp, version)
        first = {"type": "user", "version": version,
                 "message": {"content": 'the "version":"9.9.9" in a message is not one'}}
        write(path, json.dumps(first, separators=(",", ":")) + '\n{"type":"summary"}\n')
        return path

    def high(self):
        return {"model": {"display_name": "Sonnet"},
                "rate_limits": {"seven_day": {"used_percentage": 95, "resets_at": now() + 7200}}}

    def fresh_dir(self, name, settings=None):
        """A scratch CLAUDE_DIR (<tmp>/<name>/.claude when `name` has a home) with optional settings.json."""
        path = os.path.join(self.tmp, name)
        os.makedirs(path)
        if settings is not None:
            write_json(path + "/settings.json", settings)
        return path

    # ------------------------------------------------------------------ the gate
    def test_01_pretooluse_agent_with_no_record(self):
        self.reset_state()
        self.expect_route("unchanged", {"subagent_type": "ai-expert", "prompt": "p", "description": "d"},
                          "a pinned Fable agent runs on Fable while Fable is available")
        self.expect_route("unchanged", {"subagent_type": "general-purpose", "model": "fable", "prompt": "p"},
                          "an explicit model: fable is left alone")

    def test_02_pretooluse_agent_while_fable_is_unavailable(self):
        self.set_marker(now() + 600)
        self.expect_route("opus", {"subagent_type": "ai-expert", "prompt": "p", "description": "d"},
                          "ai-expert (frontmatter model: fable) is routed to opus")
        self.expect_route("opus", {"subagent_type": "general-purpose", "model": "fable", "prompt": "p"},
                          "an explicit model: fable is routed to opus")
        self.expect_route("opus", {"subagent_type": "x", "model": "fable[1m]", "prompt": "p"},
                          "fable[1m] is routed too")
        self.expect_route("unchanged", {"subagent_type": "ai-reviewer", "prompt": "p"}, "an Opus agent is untouched")
        self.expect_route("unchanged", {"subagent_type": "Explore", "model": "sonnet", "prompt": "p"},
                          "a Sonnet agent is untouched")
        self.expect_route("unchanged", {"subagent_type": "fork", "model": "fable", "prompt": "p"},
                          "a fork is untouched (it ignores model)")
        self.expect_route("unchanged", {"subagent_type": "architect", "prompt": "p"},
                          "user-level architect (opus) is untouched")
        self.expect_route("opus", {"subagent_type": "architect", "prompt": "p"},
                          "a project-level architect pinned to fable wins over the user one, and is routed",
                          self.tmp + "/project")

    def test_03_claude_code_subagent_model_last_since_2_1_251_first_before_it(self):
        ai_expert = {"subagent_type": "ai-expert", "prompt": "p"}
        own_sonnet = {"subagent_type": "x", "model": "sonnet", "prompt": "p"}
        sonnet, fable = {"CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"}, {"CLAUDE_CODE_SUBAGENT_MODEL": "fable"}
        self.expect_route("opus", {"subagent_type": "no-definition", "prompt": "p"},
                          "an agent with no definition falls back to CLAUDE_CODE_SUBAGENT_MODEL", env=fable)
        self.expect_route("opus", ai_expert,
                          "a frontmatter model: fable outranks CLAUDE_CODE_SUBAGENT_MODEL=sonnet, and is routed", env=sonnet)
        self.expect_route("unchanged", {"subagent_type": "no-definition", "model": "sonnet", "prompt": "p"},
                          "the call's own model: sonnet outranks CLAUDE_CODE_SUBAGENT_MODEL=fable, and stays on Sonnet",
                          env=fable)
        self.expect_route("opus", {"subagent_type": "no-definition", "model": "fable", "prompt": "p"},
                          "the call's own model: fable outranks CLAUDE_CODE_SUBAGENT_MODEL=sonnet, and is routed", env=sonnet)
        self.expect_route("unchanged", {"subagent_type": "ai-reviewer", "prompt": "p"},
                          "a frontmatter model: opus outranks CLAUDE_CODE_SUBAGENT_MODEL=fable", env=fable)
        for v in ("2.1.251", "2.1.276", "2.2.0", "3.0.0"):
            self.expect_route("opus", ai_expert,
                              Template("Claude Code $v: the frontmatter outranks the variable").substitute(v=v),
                              transcript=self.transcript(v), env=sonnet)
            self.expect_route("unchanged", own_sonnet,
                              Template("Claude Code $v: the call's own model outranks the variable").substitute(v=v),
                              transcript=self.transcript(v), env=fable)
        for v in ("2.1.219", "2.1.250", "2.0.76", "1.0.128"):
            self.expect_route("unchanged", ai_expert,
                              Template("Claude Code $v: the variable outranks the frontmatter, so nothing runs on Fable"
                                       ).substitute(v=v), transcript=self.transcript(v), env=sonnet)
            self.expect_route("opus", own_sonnet,
                              Template("Claude Code $v: the variable outranks the call's own model").substitute(v=v),
                              transcript=self.transcript(v), env=fable)
        self.expect_route("opus", ai_expert, "an unreadable transcript means the current order",
                          transcript=self.tmp + "/no-such-transcript.jsonl", env=sonnet)
        write(self.tmp + "/transcript-bad.jsonl", 'not json\n{"version":"garbage"}\n{"version":7}\n')
        self.expect_route("opus", ai_expert, "a transcript with no usable version means the current order",
                          transcript=self.tmp + "/transcript-bad.jsonl", env=sonnet)
        self.expect_route("opus", ai_expert, "with the variable unset an old Claude Code changes nothing",
                          transcript=self.transcript("2.1.219"))

    def test_04_the_rewrite_keeps_the_call_and_is_a_well_formed_decision(self):
        out = self.agent_call({"subagent_type": "ai-expert", "prompt": "keep me", "description": "keep",
                               "run_in_background": True})
        u = hso(out).get("updatedInput") or {}
        self.assertTrue(u.get("prompt") == "keep me" and u.get("description") == "keep"
                        and u.get("run_in_background") is True and u.get("subagent_type") == "ai-expert",
                        "every other Agent input field is preserved")
        h = hso(out)
        self.assertTrue(h.get("hookEventName") == "PreToolUse" and h.get("permissionDecision") == "allow"
                        and re.search("opus", h.get("additionalContext") or "")
                        and re.search("rate_limit", h.get("permissionDecisionReason") or ""),
                        "the output is a well-formed PreToolUse decision that tells Claude and the user why")
        out = self.gate(stdin={"hook_event_name": "PreToolUse", "tool_name": "Read",
                               "tool_input": {"file_path": "/x", "model": "fable"}})
        self.assertEqual(out, "", "a non-Agent tool is ignored")
        self.expect_route("unchanged", {"subagent_type": "ai-expert", "prompt": "p"},
                          "CLAUDE_FABLE_GATE=off disables the rewrite", env={"CLAUDE_FABLE_GATE": "off"})
        self.expect_route("sonnet", {"subagent_type": "ai-expert", "prompt": "p"},
                          "the fallback model is configurable", env={"CLAUDE_FABLE_GATE_FALLBACK": "sonnet"})

    def test_05_the_record_expires_on_its_own(self):
        self.set_marker(now() - 1)
        self.expect_route("unchanged", {"subagent_type": "ai-expert", "prompt": "p"},
                          "an expired record no longer routes Fable agents")
        self.reset_state()
        script = ("import importlib.util, json, sys\n"
                  "spec = importlib.util.spec_from_file_location('gate', sys.argv[1])\n"
                  "gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)\n"
                  "gate.mark(2000000000.9, 'test', 'test')\n"
                  "print(json.load(open(gate.STATE))['unavailable']['until'])\n")
        _, stored, _ = self.run_cmd([sys.executable, "-", GATE], script)
        self.assertEqual(sub(stored), "2000000001",
                         "a fractional expiry is rounded up, never ending the record early")

    def test_06_stopfailure_records_unavailability(self):
        self.reset_state()
        self.stop_failure("rate_limit", {"last_assistant_message": "API Error: 429 rate limit for claude-fable-5-1"})
        self.assertTrue(self.marker_active(), "a rate_limit that names Fable records it")
        self.expect_route("opus", {"subagent_type": "ai-expert", "prompt": "p"}, "the next Fable agent is routed to opus")
        left = self.until() - now()  # rounded up, so up to TTL + 1 s
        self.assertTrue(3000 < left <= 3601, "rate_limit holds for CLAUDE_FABLE_GATE_TTL (1h)")

        self.reset_state()
        self.stop_failure("model_not_found", {"agent_type": "ai-expert"})
        self.assertTrue(self.marker_active(), "model_not_found in an agent pinned to fable records it")
        self.assertGreater(self.until() - now(), 20000, "model_not_found holds longer (6h)")

        self.reset_state()
        write(self.tmp + "/transcript.jsonl",
              '{"message":{"model":"claude-sonnet-5"}}\n{"message":{"model":"claude-fable-5-1"}}\n')
        self.stop_failure("rate_limit", {"transcript_path": self.tmp + "/transcript.jsonl"})
        self.assertTrue(self.marker_active(), "a rate_limit in a transcript last served by Fable records it")

        self.reset_state()
        self.agent_call({"subagent_type": "ai-expert", "prompt": "p"})
        self.stop_failure("rate_limit")
        self.assertTrue(self.marker_active(), "a rate_limit right after a Fable agent launched is attributed to it")

        self.reset_state()
        self.stop_failure("rate_limit", {"last_assistant_message": "429 for claude-sonnet-5"})
        self.assertFalse(self.marker_active(), "a rate_limit with no sign of Fable is ignored")
        write_json(self.state, {"last_fable_launch": now() - 3600})
        self.stop_failure("rate_limit")
        self.assertFalse(self.marker_active(), "a Fable launch outside the window is not blamed")
        self.reset_state()
        self.stop_failure("authentication_failed", {"last_assistant_message": "fable"})
        self.assertFalse(self.marker_active(), "authentication_failed does not route to Opus (Opus would fail too)")
        self.stop_failure("overloaded", {"last_assistant_message": "fable overloaded"})
        self.assertFalse(self.marker_active(), "overloaded is left to fallbackModel")

        self.set_marker(now() + 20000)
        self.stop_failure("rate_limit", {"last_assistant_message": "fable 429"})
        self.assertGreater(self.until(), now() + 19000, "a shorter record never shortens a longer one")

    def test_07_posttooluse_agent_records_a_fallback_off_fable(self):
        self.reset_state()
        ai_expert = {"subagent_type": "ai-expert", "prompt": "p"}
        self.post(ai_expert, {"status": "completed", "resolvedModel": "claude-fable-5-1"})
        self.assertFalse(self.marker_active(), "a Fable agent that stayed on Fable records nothing")
        self.post(ai_expert, {"status": "completed", "resolvedModel": "claude-fable-5-1",
                              "modelsUsed": ["claude-fable-5-1", "claude-opus-5"]})
        self.assertTrue(self.marker_active(), "a mid-run swap off Fable (modelsUsed) records it")
        self.assertLessEqual(self.until() - now(), 901, "an overload fallback holds only briefly (15 min)")
        self.reset_state()
        self.post(ai_expert, {"status": "async_launched", "resolvedModel": "claude-opus-5"})
        self.assertTrue(self.marker_active(), "a Fable agent that started on Opus records it")
        self.reset_state()
        self.post({"subagent_type": "ai-reviewer", "prompt": "p"},
                  {"status": "completed", "resolvedModel": "claude-sonnet-5"})
        self.assertFalse(self.marker_active(), "a fallback on a non-Fable agent is ignored")

        self.reset_state()
        sonnet = {"CLAUDE_CODE_SUBAGENT_MODEL": "sonnet"}
        self.post(ai_expert, {"status": "completed", "resolvedModel": "claude-sonnet-5"}, sonnet,
                  self.transcript("2.1.219"))
        self.assertFalse(self.marker_active(),
                         "before 2.1.251 a Fable agent the variable sent to Sonnet is not a fallback")
        self.post(ai_expert, {"status": "completed", "resolvedModel": "claude-opus-5"}, sonnet,
                  self.transcript("2.1.276"))
        self.assertTrue(self.marker_active(),
                        "since 2.1.251 a Fable agent that started on Opus records it, whatever the variable says")
        self.reset_state()
        self.post(ai_expert, {"status": "completed", "resolvedModel": "claude-sonnet-5"}, sonnet)
        self.assertFalse(self.marker_active(), "with no readable version a disputed agent is not blamed on Fable")
        self.stop_failure("model_not_found", {"agent_type": "ai-expert"}, sonnet)
        self.assertFalse(self.marker_active(),
                         "with no readable version StopFailure does not attribute a disputed agent to Fable")
        self.stop_failure("model_not_found", {"agent_type": "ai-expert", "transcript_path": self.transcript("2.1.276")},
                          sonnet)
        self.assertTrue(self.marker_active(),
                        "since 2.1.251 StopFailure attributes a Fable-pinned agent to Fable, whatever the variable says")

    def test_08_statusline_weekly_limit_nearly_used(self):
        self.reset_state()
        reset_at = now() + 7200
        self.gate("statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 93.5, "resets_at": reset_at}}})
        self.assertTrue(self.marker_active(), "93.5% of the weekly limit routes Fable to Opus")
        self.assertEqual(self.until(), reset_at, "until the weekly reset (epoch)")
        self.reset_state()
        iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now() + 5000))
        self.gate("statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 99, "resets_at": iso}}})
        self.assertGreater(self.until(), now() + 4000, "an ISO resets_at is understood")
        self.reset_state()
        self.gate("statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 40}}})
        self.assertFalse(self.marker_active(), "below the threshold nothing is recorded")
        out = self.gate("statusline", stdin='{"model":{"id":"x"}}')
        self.assertTrue(out == "" and not os.path.exists(self.state),
                        "statusline mode prints nothing and tolerates missing rate_limits")

    def test_09_fails_open(self):
        for bad in ('not json', '[]', '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"string"}', ''):
            rc, out = self.gate_rc(stdin=bad)
            self.assertTrue(rc == 0 and out == "",
                            "malformed input '${bad:0:20}' is allowed silently".replace("${bad:0:20}", bad[:20])
                            + ": rc=%s out=%s" % (rc, out))
        self.set_marker(now() + 600)
        os.chmod(self.state, 0)
        try:
            rc, _ = self.agent_run({"subagent_type": "ai-expert", "prompt": "p"})
        finally:
            os.chmod(self.state, 0o600)
        self.assertEqual(rc, 0, "an unreadable state file never breaks an Agent call")
        write(self.state, "{broken")
        self.expect_route("unchanged", {"subagent_type": "ai-expert", "prompt": "p"},
                          "a corrupt state file means Fable is tried")

    def test_10_cli(self):
        self.reset_state()
        self.assertTrue(has_line("^inactive", self.gate("status")), "status reports inactive")
        self.gate("set", "120", "manual", "test")
        self.assertTrue(self.marker_active(), "set records a manual window")
        self.gate("clear")
        self.assertFalse(self.marker_active(), "clear re-enables Fable")
        self.assertEqual(self.gate_rc("bogus")[0], 2, "an unknown command exits 2")

    def test_11_statusline_then_the_users_statusline_runs_unchanged_behind_the_check(self):
        self.reset_state()
        high = self.high()
        out = self.gate("statusline", "--then", 'jq -r .model.display_name | sed "s/^/[model] /"', stdin=high)
        self.assertEqual(sub(out), "[model] Sonnet", "the inner command gets the same stdin and its output passes through")
        self.assertTrue(self.marker_active(), "and the weekly check still recorded 95%")
        rc, out = self.gate_rc("statusline", "--then", "echo partial; exit 3", stdin=high)
        self.assertTrue(rc == 3 and sub(out) == "partial", "the inner command's exit code is passed through")
        self.reset_state()
        out = self.gate("statusline", "--then", "echo still-here", stdin=high, env={"CLAUDE_FABLE_GATE": "off"})
        self.assertTrue(sub(out) == "still-here" and not self.marker_active(),
                        "CLAUDE_FABLE_GATE=off skips the check but keeps the statusline")
        out = self.gate("statusline", "--then", "cat", stdin="garbage")
        self.assertEqual(sub(out), "garbage", "unparseable input still reaches the user's statusline")
        out = self.gate("statusline", "--then", 'echo "$HOME" | grep -q . && printf "%s|%s" "a b" \'c"d\'', stdin=high)
        self.assertEqual(sub(out), 'a b|c"d', "quoting inside the inner command survives")

    # ------------------------------------------------------------------ installer
    # Since WP5 the gate is runtime-gate.py, registered on every Claude plan (OQ4);
    # the Fable branch (StopFailure) only on a Fable install. The fable-gate.py shim
    # is gone since redesign 1.3: an install retires an old copy into backups/<date>/.
    def test_12_installer_dry_runs_per_install_option(self):
        none = self.tmp + "/none"
        out = self.node(none, "--plan", "max", "--fable", "yes", "--dry-run")
        self.assertIn("fable-gate=on runtime-gate=on", out,
                      "--plan max --fable yes: the gate and its Fable branch are on")
        self.assertIn("runtime-gate.py status", out,
                      "--plan max --fable yes: CLAUDE.md explains the gate and the Opus re-run")
        self.assertIn('"matcher": "rate_limit|model_not_found"', out,
                      "--plan max --fable yes: StopFailure is matched on the two unavailability errors")
        for plan, fable in (("max", "no"), ("pro", "no"), ("pro", "yes")):
            out = self.node(none, "--plan", plan, "--fable", fable, "--dry-run")
            self.assertIn("fable-gate=off runtime-gate=on", out,
                          "--plan $1 --fable $2: the gate is on, its Fable branch off".replace("$1", plan).replace("$2", fable))
            self.assertNotIn("runtime-gate.py status", out,
                             "--plan $1 --fable $2: CLAUDE.md does not describe the Fable reroute"
                             .replace("$1", plan).replace("$2", fable))
            self.assertNotIn('"StopFailure"', out,
                             "--plan $1 --fable $2: no StopFailure entry".replace("$1", plan).replace("$2", fable))
        out = self.node(none, "--plan", "max", "--dry-run")
        self.assertIn("fable-gate=on", out, "--plan max (fable auto) turns the Fable branch on")

    def test_13_installer_real_installs_per_option(self):
        d = self.fresh_dir("c-max-yes")
        self.node(d, "--plan", "max", "--fable", "yes")
        for ev in FABLE_EVENTS:
            self.assertTrue(settings_has_gate(d + "/settings.json", ev), "max+fable registers runtime-gate on $ev"
                            .replace("$ev", ev))
        pre = [e for e in read_json(d + "/settings.json")["hooks"]["PreToolUse"]
               if "runtime-gate" in (e["hooks"][0].get("command") or "")]
        self.assertTrue(pre and pre[-1]["matcher"] == "Agent", "the PreToolUse entry matches the Agent tool")
        self.assertTrue(os.access(d + "/hooks/runtime-gate.py", os.X_OK), "runtime-gate.py is installed executable")
        self.assertFalse(os.path.exists(d + "/hooks/fable-gate.py"), "the fable-gate.py shim is not installed")
        self.assertEqual(old_count(d + "/settings.json"), 0, "no fable-gate command is registered")
        self.assertIn("model: fable[1m]", read_text(d + "/agents/architect.md").splitlines(),
                      "architect keeps model: fable[1m] (the gate reroutes at run time)")
        self.node(d, "--plan", "max", "--fable", "yes")
        self.assertEqual(gate_count(d + "/settings.json"), 5, "a re-install does not duplicate the gate's five entries")

        for plan, fable in (("max", "no"), ("pro", "no")):
            d = self.fresh_dir("c-%s-%s" % (plan, fable))
            self.node(d, "--plan", plan, "--fable", fable)
            self.assertEqual(gate_count(d + "/settings.json"), 4,
                             "--plan $1 --fable $2 registers the gate on four events".replace("$1", plan).replace("$2", fable))
            self.assertNotIn("StopFailure", read_json(d + "/settings.json").get("hooks") or {},
                             "--plan $1 --fable $2 adds no StopFailure event".replace("$1", plan).replace("$2", fable))
            self.assertFalse(has_line("^model: fable", read_text(d + "/agents/architect.md")),
                             "--plan $1 --fable $2 leaves no agent on fable".replace("$1", plan).replace("$2", fable))

    def test_14_installer_switching_fable_off_drops_the_fable_branch_and_nothing_else(self):
        d = self.fresh_dir("c-switch", {"hooks": {
            "PostToolUse": [{"matcher": "Agent", "hooks": [{"type": "command", "command": "my-agent-logger.sh"}]}],
            "StopFailure": [{"matcher": "rate_limit", "hooks": [{"type": "command", "command": "notify-me.sh"}]}]}})
        path = d + "/settings.json"
        self.node(d, "--plan", "max", "--fable", "yes")
        self.assertEqual(gate_count(path), 5, "fable yes adds the gate next to the user's own hooks")
        out = self.node(d, "--plan", "max", "--fable", "no")
        self.assertEqual(gate_count(path), 4, "a later --fable no leaves the gate on four events")
        self.assertIn("removed: runtime-gate StopFailure", out, "the removal is reported")
        self.assertIn("my-agent-logger.sh", commands(read_json(path), "PostToolUse"),
                      "the user's own PostToolUse:Agent hook survives")
        self.assertEqual(commands(read_json(path), "StopFailure"), ["notify-me.sh"],
                         "the user's own StopFailure hook survives, alone")
        self.assertEqual(len(commands(read_json(path), "PreToolUse")), 3,
                         "cap-large-read, ai-guard and the gate stay registered")
        self.node(d, "--plan", "max", "--fable", "yes")
        self.assertEqual(gate_count(path), 5, "switching Fable back on restores the Fable branch")

        d = self.fresh_dir("c-pro-after-max")
        path = d + "/settings.json"
        self.node(d, "--plan", "max", "--fable", "yes")
        self.node(d, "--plan", "pro")
        self.assertEqual(gate_count(path), 4, "moving from max to pro keeps the gate, without its Fable branch")
        self.assertNotIn("StopFailure", read_json(path)["hooks"], "and drops the StopFailure event it alone used")
        self.assertTrue(read_json(path)["statusLine"]["command"].startswith(PREFIX),
                        "and keeps the quota statusline (every plan)")

    def test_15_installer_an_install_from_before_wp5_is_upgraded_not_doubled(self):
        h = self.tmp + "/h-upgrade"
        d = h + "/.claude"
        old = '"$HOME/.claude/hooks/fable-gate.py"'
        entry = {"type": "command", "command": old, "timeout": 5}
        os.makedirs(d + "/hooks")
        write_json(d + "/settings.json", {
            "statusLine": {"type": "command", "command": old + " statusline --then 'my-line.sh'"},
            "hooks": {"PreToolUse": [{"matcher": "Agent", "hooks": [entry]}],
                      "PostToolUse": [{"matcher": "Agent", "hooks": [entry]},
                                      {"matcher": "Agent", "hooks": [{"type": "command", "command": "my-agent-logger.sh"}]}],
                      "StopFailure": [{"matcher": "rate_limit|model_not_found", "hooks": [entry]}]}})
        write(d + "/hooks/fable-gate.py", "#!/usr/bin/env python3\n# the old shim\n")
        out = self.node(d, "--plan", "max", "--fable", "yes")
        path = d + "/settings.json"
        today = time.strftime("%Y-%m-%d")
        backup = "%s/backups/%s/hooks/fable-gate.py" % (d, today)
        self.assertTrue(not os.path.exists(d + "/hooks/fable-gate.py") and has_line("^# the old shim", read_text(backup))
                        and "retired: hooks/fable-gate.py -> backups/%s/hooks/fable-gate.py" % today in out,
                        "the old fable-gate.py shim is retired into backups/<date>/hooks/")
        self.assertEqual(old_count(path), 0, "every fable-gate entry is replaced")
        per_event = {ev: sum("runtime-gate" in c for c in commands(read_json(path), ev)) for ev in FABLE_EVENTS}
        self.assertEqual(per_event, dict.fromkeys(FABLE_EVENTS, 1), "exactly one gate command per event after the upgrade")
        self.assertIn("replaced: fable-gate hooks with runtime-gate", out, "the replacement is reported")
        self.assertIn("my-agent-logger.sh", commands(read_json(path), "PostToolUse"),
                      "the user's hook on the same event survives the upgrade")
        self.assertEqual(read_json(path)["statusLine"]["command"],
                         "\"$HOME/.claude/hooks/runtime-gate.py\" statusline --context --then 'my-line.sh'",
                         "the old statusline wrapper is re-pointed, the user's command kept")
        self.assertIn("statusline: moved the fable-gate statusline wrapper", out, "the move is reported")

    def test_16_installer_the_quota_check_runs_through_the_statusline_on_every_plan(self):
        h = self.tmp + "/h-wrap"
        d = h + "/.claude"
        os.makedirs(d)
        write_json(d + "/settings.json", {"statusLine": {"type": "command", "command": ORIG, "padding": 1}})

        def command():
            return read_json(d + "/settings.json")["statusLine"]["command"]
        out = self.node(d, "--plan", "max", "--fable", "yes", "--dry-run")
        self.assertIn("statusline: would have wrapped", out, "the dry run says it would wrap the statusline")
        self.assertEqual(command(), ORIG, "and the dry run leaves it alone")
        out = self.node(d, "--plan", "max", "--fable", "yes")
        cmd = command()
        self.assertTrue(cmd.startswith(PREFIX + " --context --then "),
                        "an install wraps an existing statusline command, with the context line: %s" % cmd)
        self.assertIn("statusline: wrapped", out, "the wrap is reported")
        self.assertEqual(read_json(d + "/settings.json")["statusLine"]["padding"], 1, "other statusLine fields are kept")
        self.node(d, "--plan", "max", "--fable", "yes")
        self.assertEqual(command(), cmd, "a re-install does not wrap twice")

        write(h + "/.claude/statusline-command.sh", '#!/usr/bin/env bash\ncat >/dev/null; printf "my-statusline %s" "$*"\n')
        self.reset_state()
        out = self.bash_c(cmd, h, self.high())
        self.assertEqual(sub(out), "Sonnet\nmy-statusline --flag two words single",
                         "the installed wrapper prints the model, then runs the original statusline with its arguments intact")
        self.assertTrue(self.marker_active(), "and records the weekly limit through the installed hook")

        self.node(d, "--plan", "max", "--fable", "no")
        self.assertEqual(command(), cmd, "--fable no keeps the wrapper: the quota is read on every plan")
        out = self.node(d, "--plan", "max", "--fable", "no", "--statusline-context", "no")
        self.assertEqual(command(), PREFIX + " --then " + cmd[len(PREFIX + " --context --then "):],
                         "--statusline-context no rewrites the wrapper in place, the user's command byte for byte")
        self.assertIn("statusline: removed the model and context line", out, "the rewrite is reported")
        self.node(d, "--plan", "max", "--fable", "no")
        self.assertEqual(command(), cmd, "and --statusline-context yes puts --context back")

        h = self.tmp + "/h-none"
        d = h + "/.claude"
        os.makedirs(d)
        self.node(d, "--plan", "max", "--fable", "yes", "--statusline-context", "no")
        self.assertEqual(command(), PREFIX,
                         "with no statusline and --statusline-context no, an install adds the bare check")
        out = self.bash_c(command(), h, self.high())
        self.assertEqual(out, "", "which prints nothing")
        self.node(d, "--plan", "max", "--fable", "yes")
        self.assertEqual(command(), PREFIX + " --context", "by default the added statusline shows the model and the context")
        out = self.bash_c(command(), h, self.high())
        self.assertEqual(sub(out), "Sonnet", "which prints the model alone when the payload has no context_window")

        for plan, fable in (("max", "no"), ("pro", "no")):
            h = "%s/h-%s-%s" % (self.tmp, plan, fable)
            d = h + "/.claude"
            os.makedirs(d)
            write_json(d + "/settings.json", {"statusLine": {"type": "command", "command": ORIG}})
            self.node(d, "--plan", plan, "--fable", fable)
            self.assertTrue(command().startswith(PREFIX + " --context --then "),
                            "--plan $1 --fable $2 wraps the statusline too (OQ4)".replace("$1", plan).replace("$2", fable))


if __name__ == "__main__":
    unittest.main()
