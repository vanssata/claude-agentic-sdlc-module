#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
runtime-gate.py: the one gate behind both old names (R5). test-runtime-gate-fable.sh
and test-runtime-gate-codex.sh prove the behaviour per runtime (the shims they
once ran through are gone since redesign 1.3); this one proves what is new — the
AI_RUNTIME_GATE names winning over the old ones, the runtime read from the home
the hook runs from, the one-time import of an old gate's state, and failing open.

The sections share one home and one project, in the shell suite's order:
test_NN_ names keep it.
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
from guard_harness import FIXTURES, PLUGIN  # noqa: E402  pylint: disable=wrong-import-position

TWIN_OF = "test-runtime-gate.sh"

SRC_GATE = os.path.join(PLUGIN, "hooks", "runtime-gate.py")
FIX = os.path.join(FIXTURES, "codex-hooks")
RESOLVE = os.path.join(PLUGIN, "scripts", "resolve-profile.py")
GATE_VARS = re.compile(r"^(AI_RUNTIME_GATE|CLAUDE_FABLE_GATE|CODEX_MODEL_GATE)[A-Z_]*$")
UNSET = ("CLAUDE_CONFIG_DIR", "CODEX_HOME", "CLAUDE_PROJECT_DIR", "CLAUDE_CODE_SUBAGENT_MODEL",
         # A background or `-p` session exports CLAUDE_CODE_SESSION_ATTENDED=0 and a CI
         # launcher AI_UNATTENDED=1; the gate then never asks, and the "should ask"
         # assertions below would fail for the wrong reason.
         "CLAUDE_CODE_SESSION_ATTENDED", "AI_UNATTENDED")


def hso(out):
    """hookSpecificOutput of a hook's stdout, {} when there is none."""
    try:
        return json.loads(out).get("hookSpecificOutput") or {}
    except (ValueError, AttributeError):
        return {}


def decision(out):
    return hso(out).get("permissionDecision") or "none"


def upd(out):
    return hso(out).get("updatedInput")


def has_line(pattern, text):
    return re.search(pattern, text, re.M) is not None


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh)


def write(path, text):
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def count(path, needle):
    """grep -c: the lines of a file that hold `needle`, 0 when there is no file."""
    try:
        with open(path, encoding="utf-8") as fh:
            return sum(needle in line for line in fh)
    except OSError:
        return 0


def last_line(path):
    with open(path, encoding="utf-8") as fh:
        return json.loads(fh.read().splitlines()[-1])


class TestRuntimeGate(unittest.TestCase):  # pylint: disable=too-many-public-methods
    proj = task = None  # set by test_07, which starts a task the later sections read

    @classmethod
    def setUpClass(cls):
        cls.tmp = tmp = tempfile.mkdtemp()
        env = {k: v for k, v in os.environ.items() if k not in UNSET and not GATE_VARS.match(k)}
        env["HOME"] = os.path.join(tmp, "home")
        cls.env = env
        # One installed copy per runtime, where install.sh puts them.
        cls.cl = cl = os.path.join(env["HOME"], ".claude")
        cls.cx = cx = os.path.join(env["HOME"], ".codex")
        for d in (cl + "/hooks", cl + "/agents", cx + "/hooks", cx + "/agents"):
            os.makedirs(d)
        for d in (cl + "/hooks", cx + "/hooks"):
            shutil.copy(SRC_GATE, d)
        cls.g = cl + "/hooks/runtime-gate.py"
        cls.cxg = cx + "/hooks/runtime-gate.py"
        write(cl + "/agents/architect.md", "---\nname: architect\nmodel: fable[1m]\n---\nbody\n")
        subprocess.run([sys.executable, os.path.join(PLUGIN, "scripts", "render-codex-agents.py"), "--src", PLUGIN,
                        "--out", cx + "/agents"], env=env, stdout=subprocess.DEVNULL, check=True)
        # No shipped role pins EXPERT on Codex since redesign 2.4; the reroute is
        # generic, so an EXPERT role and its STRONG twin are fixtures here.
        write(cx + "/agents/ai-expert.toml", 'name = "ai-expert"\nmodel = "gpt-6-astra"\nmodel_reasoning_effort = "xhigh"\n')
        write(cx + "/agents/ai-expert-strong.toml",
              'name = "ai-expert-strong"\nmodel = "gpt-5.6-sol"\nmodel_reasoning_effort = "high"\n')
        write(cx + "/config.toml", 'model = "gpt-5.6-sol"\n\n[agents]\ndefault_subagent_model = "gpt-5.6-terra"\n')
        cls.now = int(time.time())

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def gate(self, hook, *args, stdin="", stderr=False, **env):
        """Run a gate copy; (exit code, stdout[+stderr])."""
        if not isinstance(stdin, str):
            stdin = json.dumps(stdin)
        proc = subprocess.run([sys.executable, hook, *args], input=stdin, capture_output=True, text=True,
                              env=dict(self.env, **env), check=False)
        return proc.returncode, proc.stdout + (proc.stderr if stderr else "")

    def out(self, hook, *args, **kw):
        return self.gate(hook, *args, **kw)[1]

    def rmrf(self, *paths):
        for p in paths:
            shutil.rmtree(p, ignore_errors=True)

    def resolve(self, plan, fable, dest):
        out = subprocess.run([sys.executable, RESOLVE, plan, "--fable", fable, "--print", "agentic"],
                             capture_output=True, text=True, env=self.env, check=True).stdout
        write(dest, out)

    def claude_call(self):
        return {"hook_event_name": "PreToolUse", "tool_name": "Agent", "cwd": "/nonexistent",
                "tool_input": {"subagent_type": "architect", "prompt": "p"}}

    def codex_call(self):
        with open(os.path.join(FIX, "30-agent-expert-launch.json"), encoding="utf-8") as fh:
            return json.dumps(json.load(fh)["payload"]).replace("__ROOT__", self.tmp)

    def launch(self, hook, agent, session="s1", model="", **env):
        tool_input = {"subagent_type": agent, "prompt": "p"}
        if model:
            tool_input["model"] = model
        return self.out(hook, stdin={"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": session,
                                     "cwd": self.proj, "tool_input": tool_input}, **env)

    def v2(self, event, tool_input, session="cx", tool="collaborationspawn_agent", extra=None, **env):
        payload = {"hook_event_name": event, "tool_name": tool, "session_id": session, "turn_id": "u",
                   "cwd": self.proj, "tool_input": tool_input}
        payload.update(extra or {})
        return self.out(self.cxg, stdin=payload, **env)

    def st(self, agent, model, agent_id, session="st", **env):
        return self.out(self.cxg, stdin={"hook_event_name": "SubagentStart", "session_id": session, "turn_id": "u",
                                         "cwd": self.proj, "agent_id": agent_id, "agent_type": agent,
                                         "model": model}, **env)

    def test_01_the_runtime_is_the_home_the_hook_runs_from(self):
        cl, cx, g, cxg = self.cl, self.cx, self.g, self.cxg
        self.assertTrue(has_line("^inactive: model: fable", self.out(g, "status")), "~/.claude/hooks -> Claude Code")
        self.assertTrue(has_line("^inactive: EXPERT agents run on gpt-6-astra", self.out(cxg, "status")),
                        "~/.codex/hooks -> Codex")
        self.gate(g, "set", "600", "test")
        self.assertTrue(os.path.isfile(cl + "/state/runtime-gate.json"), "state in <home>/state/runtime-gate.json")
        self.assertFalse(os.path.exists(cx + "/state/runtime-gate.json"), "and the other runtime's state is untouched")
        out = self.out(g, stdin=self.claude_call())
        self.assertEqual((upd(out) or {}).get("model"), "opus", "a Fable launch is rewritten to opus")
        self.assertEqual(hso(out).get("permissionDecision"), "allow", "with allow, never deny")
        self.gate(g, "clear")
        self.gate(cxg, "set", "600", "test")
        out = self.out(cxg, stdin=self.codex_call())
        self.assertEqual((upd(out) or {}).get("agent_type"), "ai-expert-strong",
                         "an EXPERT spawn is rerouted to its STRONG twin")
        self.gate(cxg, "clear")

    def test_02_the_shims_are_gone(self):
        for s in ("fable-gate", "codex-model-gate"):
            with self.subTest(Template("the plugin ships no $s.py").substitute(s=s)):
                self.assertFalse(os.path.exists(os.path.join(PLUGIN, "hooks", s + ".py")))

    def test_03_new_names_win_over_the_old_ones(self):
        tmp, g, cxg = self.tmp, self.g, self.cxg
        new, old = tmp + "/new.json", tmp + "/old.json"
        self.gate(g, "set", "60", "x", AI_RUNTIME_GATE_STATE=new, CLAUDE_FABLE_GATE_STATE=old)
        self.assertTrue(os.path.isfile(new) and not os.path.exists(old),
                        "AI_RUNTIME_GATE_STATE before CLAUDE_FABLE_GATE_STATE")
        self.gate(g, "set", "60", "x", CLAUDE_FABLE_GATE_STATE=old)
        self.assertTrue(os.path.isfile(old), "the old name still works alone")
        out = self.out(g, stdin=self.claude_call(), AI_RUNTIME_GATE_STATE=new, CLAUDE_FABLE_GATE_FALLBACK="sonnet",
                       AI_RUNTIME_GATE_FALLBACK="haiku")
        self.assertEqual((upd(out) or {}).get("model"), "haiku", "AI_RUNTIME_GATE_FALLBACK before CLAUDE_FABLE_GATE_FALLBACK")
        out = self.out(g, stdin=self.claude_call(), AI_RUNTIME_GATE="off", CLAUDE_FABLE_GATE="on",
                       AI_RUNTIME_GATE_STATE=new)
        self.assertEqual(out, "", "AI_RUNTIME_GATE=off disables it")
        out = self.out(cxg, stdin=self.codex_call(), CODEX_MODEL_GATE="off", AI_RUNTIME_GATE_STATE=tmp + "/new-cx.json")
        self.assertEqual(out, "", "CODEX_MODEL_GATE=off still disables the Codex side")
        self.gate(cxg, "set", "60", "x", CODEX_MODEL_GATE_STATE=tmp + "/cx-old.json",
                  CLAUDE_FABLE_GATE_STATE=tmp + "/wrong.json")
        self.assertTrue(os.path.isfile(tmp + "/cx-old.json") and not os.path.exists(tmp + "/wrong.json"),
                        "each runtime reads only its own old names")

    def test_04_an_old_gates_state_is_imported_once(self):
        cl, cx, g, cxg = self.cl, self.cx, self.g, self.cxg
        self.rmrf(cl + "/state")
        os.makedirs(cl + "/state")
        write_json(cl + "/state/fable-gate.json", {"unavailable": {"until": int(time.time()) + 600, "reason": "rate_limit",
                                                                   "source": "StopFailure"}, "last_fable_launch": 1})
        self.assertTrue(has_line("^active: Fable -> opus", self.out(g, "status")), "a live fable-gate record carries over")
        state = read_json(cl + "/state/runtime-gate.json")
        self.assertTrue(state.get("imported_from") == "fable-gate.json"
                        and state.get("unavailable", {}).get("reason") == "rate_limit"
                        and "last_fable_launch" not in state,
                        "only the outage record is imported, and the import is recorded" + ": %s" % state)
        self.gate(g, "clear")
        self.assertTrue(has_line("^inactive", self.out(g, "status")), "once: clear is not undone by a second import")
        self.rmrf(cx + "/state")
        os.makedirs(cx + "/state")
        write_json(cx + "/state/codex-model-gate.json", {"unavailable": {"until": int(time.time()) + 600,
                                                                         "reason": "model_unavailable",
                                                                         "source": "SubagentStop"}})
        self.assertTrue(has_line("^active: gpt-6-astra -> gpt-5.6-sol", self.out(cxg, "status")),
                        "a live codex-model-gate record carries over")

    def test_05_quota_claude_code_from_the_statusline(self):
        cl, g, now, tmp = self.cl, self.g, self.now, self.tmp
        self.rmrf(cl + "/state", cl + "/claude-agentic")
        line = self.out(g, "statusline", "--then", "cat >/dev/null; echo LINE",
                        stdin={"rate_limits": {"seven_day": {"used_percentage": 42.5, "resets_at": now + 86400},
                                               "five_hour": {"used_percentage": 7}}})
        self.assertIn("LINE", line.splitlines(), "the statusline still prints the user's own line")
        q = json.loads(self.out(g, "quota", "--json"))
        self.assertTrue(q["runtime"] == "claude" and q["weekly_pct"] == 42.5 and q["five_hour_pct"] == 7
                        and q["resets_at"] == now + 86400 and q["source"] == "statusline" and q["stale"] is False
                        and q["seen_at"] > 0
                        and sorted(q) == ["five_hour_pct", "resets_at", "runtime", "seen_at", "source", "stale",
                                          "weekly_pct"],
                        "quota --json has the seven keys from the statusline payload" + ": %s" % q)
        self.assertTrue(has_line("^inactive", self.out(g, "status")), "42% used marks nothing")
        self.assertIn("weekly 42%, 5-hour 7%", self.out(g, "quota"), "quota prints one readable line")

        os.makedirs(cl + "/claude-agentic")
        write(cl + "/claude-agentic/profile.json", '{"plan":"max","fable":false}')
        self.gate(g, "statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 95}}})
        self.assertTrue(has_line("^inactive", self.out(g, "status")),
                        "fable: false — 95% records the quota but marks no Fable outage")
        self.assertEqual(json.loads(self.out(g, "quota", "--json"))["weekly_pct"], 95,
                         "and the quota is still recorded")
        write(cl + "/claude-agentic/profile.json", '{"plan":"max","fable":true}')
        self.gate(g, "statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 95}}})
        self.assertTrue(has_line("^active: Fable", self.out(g, "status")), "fable: true — 95% marks Fable unavailable")
        self.gate(g, "clear")

        path = cl + "/state/runtime-gate.json"
        state = read_json(path)
        state["quota"]["seen_at"] = 1000
        write_json(path, state)
        self.assertIs(json.loads(self.out(g, "quota", "--json"))["stale"], True, "a reading older than 24 h is stale")
        state = read_json(path)
        state["quota"]["seen_at"] = now
        state["quota"]["resets_at"] = now - 60
        write_json(path, state)
        self.assertIs(json.loads(self.out(g, "quota", "--json"))["stale"], True, "a reading past its reset is stale")
        self.rmrf(cl + "/state")
        q = json.loads(self.out(g, "quota", "--json"))
        self.assertTrue(q["stale"] is True and q["weekly_pct"] is None, "no reading at all is stale")

        self.rmrf(cl + "/state")
        self.gate(g, "statusline", stdin={"rate_limits": {"seven_day": {"used_percentage": 30}}},
                  CLAUDE_FABLE_GATE_STATE=tmp + "/legacy-q.json")
        self.assertTrue(not os.path.exists(tmp + "/legacy-q.json") and read_json(path)["quota"]["weekly_pct"] == 30,
                        "a state named by the old variable gets no quota; the ledger stays in runtime-gate.json")

    def test_06_quota_codex_from_the_newest_rollout(self):
        cx, cxg, now = self.cx, self.cxg, self.now
        self.rmrf(cx + "/state")
        old_day, new_day = cx + "/sessions/2026/09/19", cx + "/sessions/2026/09/21"
        os.makedirs(old_day)
        os.makedirs(new_day)
        iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now))

        def tc(weekly, five, resets):
            return json.dumps({"timestamp": iso, "type": "event_msg", "payload": {
                "type": "token_count", "info": {}, "rate_limits": {
                    "limit_id": "codex",
                    "primary": {"used_percent": five, "window_minutes": 300, "resets_at": resets - 3600},
                    "secondary": {"used_percent": weekly, "window_minutes": 10080, "resets_at": resets}}}},
                separators=(",", ":")) + "\n"
        write(old_day + "/rollout-old.jsonl", tc(10, 1, now + 9000))
        two_days_ago = time.time() - 2 * 86400
        os.utime(old_day + "/rollout-old.jsonl", (two_days_ago, two_days_ago))
        new = new_day + "/rollout-new.jsonl"
        write(new, tc(50, 20, now + 9000) + '{"type":"response_item","payload":{}}\n' + tc(73, 36, now + 7200)
              + '{"type":"event_msg","payload":{"type":"agent_message"}}\n')
        q = json.loads(self.out(cxg, "quota", "--json"))
        self.assertTrue(q["runtime"] == "codex" and q["weekly_pct"] == 73 and q["five_hour_pct"] == 36
                        and q["resets_at"] == now + 7200 and q["source"] == "rollout" and q["seen_at"] == now
                        and q["stale"] is False,
                        "the last token_count of the newest rollout: secondary is weekly, primary is 5-hour" + ": %s" % q)
        with open(new, "a", encoding="utf-8") as fh:
            fh.write(tc(99, 99, now + 7200))
        self.assertEqual(json.loads(self.out(cxg, "quota", "--json"))["weekly_pct"], 73,
                         "the rollout is read at most once a minute")
        state_path = cx + "/state/runtime-gate.json"
        state = read_json(state_path)
        state["quota_checked_at"] = 0
        write_json(state_path, state)
        self.assertEqual(json.loads(self.out(cxg, "quota", "--json"))["weekly_pct"], 99, "and again once the minute is up")
        write(new_day + "/rollout-big.jsonl", tc(5, 5, now + 7200) + "x" * 70000 + "\n")
        state = read_json(state_path)
        state["quota_checked_at"] = 0
        write_json(state_path, state)
        self.assertEqual(json.loads(self.out(cxg, "quota", "--json"))["weekly_pct"], 99,
                         "only the last 64 KB is read: a newest file with no token_count there changes nothing")
        self.rmrf(cx + "/sessions", cx + "/state")
        q = json.loads(self.out(cxg, "quota", "--json"))
        self.assertTrue(q["stale"] is True and q["source"] is None, "no rollout: unknown and stale")

    def test_07_budgets_expert_asks(self):
        cl, cx, tmp = self.cl, self.cx, self.tmp
        self.rmrf(cl + "/state", cx + "/state")
        self.resolve("max", "yes", cl + "/claude-agentic/profile.json")
        os.makedirs(cx + "/claude-agentic", exist_ok=True)
        self.resolve("codex-plus", "no", cx + "/claude-agentic/profile.json")
        proj = type(self).proj = tmp + "/proj"
        os.makedirs(proj + "/.ai")
        os.makedirs(proj + "/src")
        git = ["git", "-C", proj]
        subprocess.run(git + ["init", "-q"], check=True, env=self.env)
        write(proj + "/src/a.py", "x\n")
        subprocess.run(git + ["add", "-A"], check=True, env=self.env)
        subprocess.run(git + ["-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "base"], check=True,
                       env=self.env)
        subprocess.run([sys.executable, os.path.join(PLUGIN, "skills", "ai-task", "state.py"), "--root", proj, "start",
                        "--goal", "g", "--workflow", "feature", "--files", "src/a.py",
                        "--declare", "behaviour=0:fixture", "--declare", "domain=0:fixture",
                        "--declare", "novelty=0:fixture"], capture_output=True, env=self.env, check=False)
        task = type(self).task = read_json(proj + "/.ai/state/current.json")["task_id"]
        g = self.g
        out = self.launch(g, "architect")
        self.assertTrue(decision(out) == "ask"
                        and re.search("EXPERT agents run only when asked on Max",
                                      hso(out).get("permissionDecisionReason", "")),
                        "max: an EXPERT launch asks, with the reason" + ": %s" % out)
        self.assertEqual(self.launch(g, "ai-reviewer"), "", "max: a STRONG launch goes through silently")
        self.assertEqual(self.launch(g, "architect", "s1", "sonnet"), "",
                         "an explicit model on the call decides the tier: architect with model: sonnet does not ask")
        out = self.launch(g, "architect", AI_UNATTENDED="1")
        self.assertTrue(decision(out) == "none" and "unattended" in hso(out).get("additionalContext", ""),
                        "AI_UNATTENDED=1: allowed and explained, never asked" + ": %s" % out)
        self.resolve("max20", "yes", cl + "/claude-agentic/profile.json")
        self.rmrf(cl + "/state")
        o1, o2, o3 = (self.launch(g, "architect") for _ in range(3))
        self.assertEqual(o1 + o2, "", "max20: two EXPERT launches in a task need no question")
        self.assertTrue(decision(o3) == "ask" and task in hso(o3).get("permissionDecisionReason", ""),
                        "max20: the third asks, naming the task" + ": %s" % o3)
        self.assertEqual(read_json(cl + "/state/runtime-gate.json")["expert_launches"].get(task), 3,
                         "the count is keyed by the task id")
        out = self.out(self.cxg, stdin=self.codex_call())
        self.assertTrue(decision(out) not in ("ask", "deny") and "Codex cannot ask" in hso(out).get("additionalContext", ""),
                        "codex-plus: an EXPERT spawn is allowed and explained, never asked" + ": %s" % out)

    def test_08_no_fan_out_budget_and_no_agent_count(self):
        cl, g = self.cl, self.g
        self.resolve("max", "yes", cl + "/claude-agentic/profile.json")
        self.rmrf(cl + "/state")
        with self.subTest("six parallel launches of one session: no question"):
            for _ in range(6):
                self.assertEqual(self.launch(g, "Explore", "batch"), "")
        for e in ("SubagentStart", "SubagentStop"):
            rc, out = self.gate(g, stdin={"hook_event_name": e, "session_id": "s1", "agent_type": "Explore",
                                          "agent_id": "a1"})
            with self.subTest(Template("Claude Code $e is a no-op, exit 0").substitute(e=e)):
                self.assertEqual((rc, out), (0, ""))
        path = cl + "/state/runtime-gate.json"
        self.assertTrue(not os.path.exists(path)
                        or not ("running_agents" in read_json(path) or "pending_launches" in read_json(path)),
                        "nothing counts running or pending agents")

    def test_09_codex_multi_agent_v2_launches(self):
        # Codex 0.155 multi-agent v2: spawn_agent sits in the `collaboration` namespace,
        # and hooks see namespace + name with no separator (traced live 2026-09-22).
        # PreToolUse and PostToolUse fire for it; updatedInput is applied, but a role's
        # pinned model beats the call's `model`, so an EXPERT role is rerouted through
        # agent_type; SpawnAgentArgs refuses unknown fields, so the effort key is
        # `reasoning_effort`. SubagentStart accepts only additionalContext.
        cx, cxg, proj, task, tmp = self.cx, self.cxg, self.proj, self.task, self.tmp
        if not os.path.lexists(cx + "/skills"):
            os.symlink(os.path.join(PLUGIN, "skills"), cx + "/skills")  # where install.sh puts state.py
        self.rmrf(cx + "/state")
        self.gate(cxg, "set", "600", "rate_limit")
        ev = "%s/.ai/reports/%s/events.jsonl" % (proj, task)
        before = count(ev, '"model_fallback"')
        out = self.v2("PreToolUse", {"task_name": "t", "agent_type": "ai-expert", "message": "m"}, "e1")
        u = upd(out) or {}
        self.assertTrue(u.get("agent_type") == "ai-expert-strong" and "model" not in u and "reasoning_effort" not in u
                        and u.get("message") == "m" and decision(out) == "allow",
                        "ai-expert is rerouted by agent_type to ai-expert-strong, nothing injected" + ": %s" % out)
        ctx = hso(out).get("additionalContext", "")
        self.assertTrue("ai-expert-strong" in ctx and "gpt-5.6-sol" in ctx,
                        "the context names the twin and the model it runs on")
        data = last_line(ev)["data"]
        self.assertTrue(count(ev, '"model_fallback"') - before == 1 and data.get("agent") == "ai-expert"
                        and data.get("from") == "gpt-6-astra" and data.get("to") == "gpt-5.6-sol",
                        "one model_fallback line, to the model the twin pins" + ": %s" % data)
        self.assertEqual((read_json(cx + "/state/runtime-gate.json").get("expert_launches") or {}).get(task, 0), 0,
                         "the budget rates the rerouted launch: no EXPERT launch counted")

        out = self.v2("PreToolUse", {"task_name": "t", "model": "gpt-6-astra", "model_reasoning_effort": "xhigh",
                                     "message": "m"}, "e2")
        u = upd(out) or {}
        self.assertTrue(u.get("model") == "gpt-5.6-sol" and u.get("reasoning_effort") == "high"
                        and "model_reasoning_effort" not in u,
                        "no role, explicit expert model: model and reasoning_effort rewritten, "
                        "model_reasoning_effort dropped" + ": %s" % out)
        out = self.v2("PreToolUse", {"task_name": "t", "model": "gpt-6-astra", "message": "m"}, "e3",
                      AI_RUNTIME_GATE_FALLBACK_EFFORT="bogus")
        u = upd(out) or {}
        self.assertTrue(u.get("model") == "gpt-5.6-sol" and "reasoning_effort" not in u,
                        "an effort Codex would refuse is left out, not sent" + ": %s" % out)
        shutil.copy(cx + "/config.toml", tmp + "/config.bak")
        write(cx + "/config.toml", 'model = "gpt-5.6-sol"\n\n[agents]\ndefault_subagent_model = "gpt-6-astra"\n')
        out = self.v2("PreToolUse", {"task_name": "t", "message": "m"}, "e4")
        u = upd(out) or {}
        self.assertTrue(u.get("model") == "gpt-5.6-sol" and u.get("reasoning_effort") == "high",
                        "no role, no model, EXPERT as default_subagent_model: the call gets model and "
                        "reasoning_effort" + ": %s" % out)
        shutil.move(tmp + "/config.bak", cx + "/config.toml")

        write(cx + "/agents/my-expert.toml", 'name = "my-expert"\nmodel = "gpt-6-astra"\n')
        out = self.v2("PreToolUse", {"task_name": "t", "agent_type": "my-expert", "message": "m"}, "e5")
        self.assertTrue(upd(out) is None and decision(out) == "none"
                        and "not rerouted" in hso(out).get("additionalContext", ""),
                        "a pinned EXPERT role with no twin is explained, not rewritten" + ": %s" % out)
        write(cx + "/agents/my-expert-strong.toml", 'name = "someone-else"\nmodel = "gpt-5.6-sol"\n')
        out = self.v2("PreToolUse", {"task_name": "t", "agent_type": "my-expert", "message": "m"}, "e6")
        self.assertIsNone(upd(out), "a twin file whose name Codex would not register is not used")
        os.remove(cx + "/agents/my-expert.toml")
        os.remove(cx + "/agents/my-expert-strong.toml")
        out = self.v2("PreToolUse", {"task_name": "t", "agent_type": "ai-expert", "message": "m"}, "e7",
                      AI_RUNTIME_GATE_MODE="context")
        self.assertTrue(upd(out) is None and "not rerouted" in hso(out).get("additionalContext", ""),
                        "context mode: explained as not rerouted, no updatedInput" + ": %s" % out)
        with self.subTest("Task stays an agent event; an MCP tool ending in spawn_agent matches too (documented)"):
            for t in ("Task", "mcp__x__spawn_agent"):
                out = self.v2("PreToolUse", {"agent_type": "ai-expert", "message": "m"}, "e8", t)
                self.assertEqual((upd(out) or {}).get("agent_type"), "ai-expert-strong", "%s: %s" % (t, out))

        self.gate(cxg, "clear")
        os.makedirs(proj + "/.git", exist_ok=True)
        os.makedirs(proj + "/.codex/agents")
        os.makedirs(proj + "/sub")
        write(proj + "/.codex/agents/ai-expert.toml", 'name = "ai-expert"\nmodel = "gpt-5.6-sol"\n')
        self.rmrf(cx + "/state")
        out = self.out(cxg, stdin={"hook_event_name": "PreToolUse", "tool_name": "collaborationspawn_agent",
                                   "session_id": "ov", "cwd": proj + "/sub",
                                   "tool_input": {"agent_type": "ai-expert", "message": "m"}})
        try:
            launches = read_json(cx + "/state/runtime-gate.json").get("expert_launches")
        except (OSError, ValueError):
            launches = None
        self.assertTrue(out == "" and launches in (None, False),
                        "a project file re-pinning ai-expert to Sol (from a subdirectory) is rated STRONG by the "
                        "budget too" + ": %s %s" % (out, launches))
        self.rmrf(proj + "/.git", proj + "/.codex", proj + "/sub")
        self.v2("PostToolUse", {"agent_type": "ai-expert", "message": "m"}, "p1", "collaborationspawn_agent",
                {"tool_response": "429 Too Many Requests"})
        self.assertTrue(has_line("^active", self.out(cxg, "status")),
                        "PostToolUse on collaborationspawn_agent records the outage")

    def test_10_codex_subagentstart_is_the_missed_reroute_backstop_only(self):
        cx, cxg = self.cx, self.cxg
        ev = "%s/.ai/reports/%s/events.jsonl" % (self.proj, self.task)
        self.rmrf(cx + "/state")
        out = self.st("worker", "gpt-5.6-sol", "w1")
        self.assertTrue(out == "" and not os.path.exists(cx + "/state/runtime-gate.json"),
                        "a STRONG start is silent and records nothing")
        self.assertEqual(self.st("ai-expert", "gpt-6-astra", "w3"), "", "no outage: an EXPERT start is silent")
        self.gate(cxg, "set", "600", "rate_limit")
        before = count(ev, '"missed_reroute"')
        out = self.st("ai-expert", "gpt-6-astra", "w4")
        doc = json.loads(out)
        h = doc.get("hookSpecificOutput", {})
        self.assertTrue(sorted(doc) == ["hookSpecificOutput"] and sorted(h) == ["additionalContext", "hookEventName"]
                        and h["hookEventName"] == "SubagentStart" and "gpt-6-astra" in h["additionalContext"]
                        and "not rerouted" in h["additionalContext"],
                        "backstop: an EXPERT start during an outage tells the child, in the only field "
                        "SubagentStart takes" + ": %s" % out)
        line = last_line(ev)
        self.assertTrue(count(ev, '"missed_reroute"') - before == 1 and line.get("actor") == "hook"
                        and line["data"].get("model") == "gpt-6-astra" and line["data"].get("agent") == "ai-expert",
                        "and journals one missed_reroute line" + ": %s" % line)
        b = count(ev, '"missed_reroute"')
        out = self.st("ai-expert", "gpt-6-astra", "w5", AI_RUNTIME_GATE_MODE="context")
        self.assertTrue(out == "" and count(ev, '"missed_reroute"') == b,
                        "context mode chose not to reroute: nothing is reported as missed")
        self.gate(cxg, "clear")

    def test_11_budgets_an_expert_ask_is_attended_only(self):
        cl, g = self.cl, self.g
        self.rmrf(cl + "/state")
        out = self.launch(g, "architect", CLAUDE_CODE_SESSION_ATTENDED="0")
        self.assertTrue(decision(out) == "none" and "unattended" in hso(out).get("additionalContext", ""),
                        "claude -p (CLAUDE_CODE_SESSION_ATTENDED=0) is unattended: explained, never asked" + ": %s" % out)
        self.assertEqual(decision(self.launch(g, "architect", CLAUDE_CODE_SESSION_ATTENDED="1")), "ask",
                         "an attended session still asks")
        self.gate(g, "set", "600", "test")
        path = cl + "/state/runtime-gate.json"
        state = read_json(path)
        state["running_agents"] = {"s1": [{"tier": "STRONG", "started_at": 1}]}
        state["pending_launches"] = {"s1": []}
        write_json(path, state)
        self.gate(g, "clear")
        state = read_json(path)
        self.assertTrue(not ("unavailable" in state or "running_agents" in state or "pending_launches" in state)
                        and state.get("expert_launches") not in (None, False),
                        "clear ends the outage, drops a pre-2.4 agent count and keeps the EXPERT count" + ": %s" % state)

    def test_12_model_fallback_is_journaled_on_a_rewrite(self):
        cl, g, tmp = self.cl, self.g, self.tmp
        if not os.path.lexists(cl + "/skills"):
            os.symlink(os.path.join(PLUGIN, "skills"), cl + "/skills")  # where install.sh puts state.py
        self.resolve("max", "yes", cl + "/claude-agentic/profile.json")
        self.rmrf(cl + "/state")
        self.gate(g, "set", "600", "rate_limit")
        ev = "%s/.ai/reports/%s/events.jsonl" % (self.proj, self.task)
        before = count(ev, '"model_fallback"')
        out = self.launch(g, "architect", AI_UNATTENDED="1")
        self.assertEqual((upd(out) or {}).get("model"), "opus", "architect rerouted to opus")
        after = count(ev, '"model_fallback"')
        self.assertEqual(after - before, 1, "exactly one model_fallback line")
        line = last_line(ev)
        self.assertTrue(line.get("actor") == "hook" and line["data"] == {**line["data"], "agent": "architect",
                                                                          "from": "fable[1m]", "to": "opus",
                                                                          "reason": "rate_limit"},
                        "actor hook, {agent, from, to, reason}" + ": %s" % line)
        self.out(g, stdin={"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s9",
                           "cwd": "/nonexistent", "tool_input": {"subagent_type": "architect", "prompt": "p"}},
                 AI_UNATTENDED="1")
        self.assertEqual(count(ev, '"model_fallback"'), after, "no task at cwd, no line")
        os.makedirs(tmp + "/broken/skills/ai-task")
        write(tmp + "/broken/skills/ai-task/state.py", "import sys\nsys.exit(3)\n")
        rc, out = self.gate(g, stdin={"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "s1",
                                      "cwd": self.proj, "tool_input": {"subagent_type": "architect", "prompt": "p",
                                                                       "model": "fable[1m]"}},
                            CLAUDE_CONFIG_DIR=tmp + "/broken", AI_RUNTIME_GATE_STATE=cl + "/state/runtime-gate.json",
                            AI_UNATTENDED="1")
        self.assertTrue(rc == 0 and (upd(out) or {}).get("model") == "opus",
                        "a broken state.py: the launch is still rerouted, exit 0" + ": rc=%d %s" % (rc, out))
        self.gate(g, "clear")

    def test_13_fails_open_never_denies(self):
        with self.subTest("malformed input and an unwritable state exit 0 silently on both runtimes"):
            for stdin in ("", "not json", "[]",
                          '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"x"}'):
                for g in (self.g, self.cxg):
                    rc, out = self.gate(g, stdin=stdin, stderr=True, AI_RUNTIME_GATE_STATE="/proc/cannot/write.json")
                    self.assertEqual((rc, out), (0, ""), "%s: input %r" % (g, stdin))
        rc, _ = self.gate(self.g, "wibble")
        self.assertEqual(rc, 2, "an unknown command exits 2")
        with open(SRC_GATE, encoding="utf-8") as fh:
            self.assertNotIn('"deny"', fh.read(), "the gate has no deny path")

    def test_14_parallel_hooks_do_not_lose_each_others_writes(self):
        ls = self.tmp + "/lock-state.json"
        payload = json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Agent", "session_id": "par",
                              "cwd": self.proj, "tool_input": {"subagent_type": "architect", "prompt": "p"}})
        env = dict(self.env, AI_RUNTIME_GATE_STATE=ls)
        procs = []
        for _ in range(20):
            p = subprocess.Popen([sys.executable, self.g], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,  # pylint: disable=consider-using-with
                                 env=dict(env, AI_UNATTENDED="1"), text=True)
            p.stdin.write(payload)
            p.stdin.close()
            procs.append(p)
        procs.append(subprocess.Popen([sys.executable, self.g, "set", "600", "rate_limit"], stdin=subprocess.DEVNULL,  # pylint: disable=consider-using-with
                                      stdout=subprocess.DEVNULL, env=env))
        for p in procs:
            p.wait()
        state = read_json(ls)
        n = (state.get("expert_launches") or {}).get(self.task, 0)
        self.assertEqual(n, 20, "20 parallel EXPERT launches count 20")
        self.assertTrue((state.get("unavailable") or {}).get("until"), "an outage recorded during the launches survives")

    def test_15_settings_that_do_not_parse_or_fit_keep_the_default(self):
        g = self.g
        rc, out = self.gate(g, "status", stderr=True, AI_RUNTIME_GATE_TTL="30m",
                            AI_RUNTIME_GATE_STATE=self.tmp + "/lock-state.json")
        self.assertEqual(rc, 0, "TTL=30m does not crash the gate" + ": %s" % out)
        self.gate(g, "set", "600", "test")
        out = self.out(g, stdin=self.claude_call(), AI_RUNTIME_GATE_FALLBACK="gpt-5.6-sol")
        self.assertEqual((upd(out) or {}).get("model"), "opus", "a Codex model in the shared FALLBACK is ignored by Claude")
        out = self.out(g, stdin=self.claude_call(), AI_RUNTIME_GATE_CLAUDE_FALLBACK="sonnet",
                       AI_RUNTIME_GATE_FALLBACK="haiku")
        self.assertEqual((upd(out) or {}).get("model"), "sonnet", "AI_RUNTIME_GATE_CLAUDE_FALLBACK wins over the shared name")
        self.gate(g, "clear")


if __name__ == "__main__":
    unittest.main()
