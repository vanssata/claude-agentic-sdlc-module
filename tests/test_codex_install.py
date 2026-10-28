#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
install.sh --target codex: the Codex branch must set the managed routing keys
and nothing else, register the guards without duplicating them, write exactly
one managed AGENTS.md block, and survive being run twice over a config the
user has edited. Python twin of test-codex-install.sh; stdlib only (a small
text reader stands in for tomllib, which Python 3.10 lacks).

The sections share one scratch tree and build on each other, in the shell
suite's order: test_NN_ names keep it.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import (PLUGIN, ScratchCase, env_with, install, read,  # noqa: E402  pylint: disable=wrong-import-position
                             read_json, write)

TWIN_OF = "test-codex-install.sh"


def bre(pattern):
    """A grep (basic regex) pattern as a Python one: ( ) { } | + ? are literal outside brackets."""
    out, in_class = [], False
    for ch in pattern:
        if in_class:
            in_class = ch != "]"
            out.append(ch)
        elif ch == "[":
            in_class = True
            out.append(ch)
        elif ch in "(){}|+?":
            out.append("\\" + ch)
        else:
            out.append(ch)
    return "".join(out)


def has(pattern, text):
    """grep -q 'pattern' over text."""
    return re.search(bre(pattern), text, re.M) is not None


def count_lines(pattern, text, extended=False):
    """grep -c."""
    rx = pattern if extended else bre(pattern)
    return sum(1 for line in text.split("\n") if re.search(rx, line))


def has_line(text, line):
    """grep -qx 'line'."""
    return line in text.split("\n")


def split_dotted(text):
    parts, cur, quoted = [], "", False
    for ch in text:
        if ch == '"':
            quoted = not quoted
        elif ch == "." and not quoted:
            parts.append(cur.strip())
            cur = ""
        else:
            cur += ch
    parts.append(cur.strip())
    return parts


def toml_pairs(path):
    """{dotted key: value text} of a config.toml: tables, bare/quoted keys, strings, numbers, booleans.

    A line that is neither a table header, a key = value, a comment nor blank raises ValueError."""
    table, pairs = [], {}
    for raw in read(path).split("\n"):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("["):
            if not line.endswith("]"):
                raise ValueError(line)
            table = split_dotted(line.strip("[]"))
            continue
        key, eq, value = line.partition("=")
        if not eq or not key.strip() or "=" in value.split('"')[0]:
            raise ValueError(line)
        value = value.strip()
        if value.startswith('"'):
            end = value.index('"', 1)
            value = value[1:end]
        else:
            value = value.split("#")[0].strip()
            value = {"true": "True", "false": "False"}.get(value, value)
        pairs[".".join(table + split_dotted(key))] = value
    return pairs


def toml_get(path, dotted):
    return toml_pairs(path).get(dotted, "")


def commands(data, event):
    """jq '[.hooks[event][].hooks[].command]'."""
    return [h["command"] for e in data["hooks"].get(event, []) for h in e["hooks"]]


def all_commands(data):
    return [h["command"] for entries in data["hooks"].values() for e in entries for h in e.get("hooks", [])]


def today():
    return datetime.date.today().isoformat()


def tree_hashes(root):
    """sha256 of every regular file under root, backups/ at the top left out."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath == root:
            dirnames[:] = [d for d in dirnames if d != "backups"]
        for name in filenames:
            full = os.path.join(dirpath, name)
            if os.path.isfile(full) and not os.path.islink(full):
                with open(full, "rb") as fh:
                    out[os.path.relpath(full, root)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def bak_outside_backups(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        if dirpath == root:
            dirnames[:] = [d for d in dirnames if d != "backups"]
        found += [os.path.join(dirpath, n) for n in dirnames + filenames if n.endswith(".bak")]
    return found


def b64(data):
    return base64.urlsafe_b64encode(json.dumps(data).encode()).decode().rstrip("=")


class CodexInstall(ScratchCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        # An isolated HOME: the plan must come from the test, never from this
        # machine's ~/.codex/auth.json.
        cls.home = os.path.join(cls.tmp, "home")
        os.makedirs(cls.home)
        cls.dir = os.path.join(cls.tmp, "codex")

    def env(self, **extra):
        return env_with(HOME=self.home, **extra)

    def codex(self, codex_dir, *args, home=None, merge=True):
        env = env_with(HOME=home or self.home, CODEX_DIR=codex_dir)
        return install("--target", "codex", *args, env=env, merge=merge)

    def check(self, label, ok, detail=""):
        with self.subTest(label):
            self.assertTrue(ok, "%s: %s" % (label, detail))

    def payload(self, command):
        return json.dumps({"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": "/",
                           "tool_input": {"command": command}}, separators=(",", ":"))

    def guard(self, command):
        proc = subprocess.run(["python3", "-I", "-S", os.path.join(self.dir, "hooks", "ai-guard.py")], input=self.payload(command),
                              capture_output=True, text=True, env=self.env(), check=False)
        return proc.stdout

    def test_01_dry_run_writes_nothing_and_shows_the_change(self):
        probe = self.path("probe")
        os.makedirs(probe)
        rc, out = self.codex(probe, "--dry-run")
        self.check("the dry run exits 0", rc == 0, out)
        self.check("the target directory is untouched", os.listdir(probe) == [], os.listdir(probe))
        self.check("the dry run names the model it would set",
                   has('would have added model = "gpt-5.6-sol"', out), out)
        self.check("the AGENTS.md block renders completely", not has("{{", out),
                   "an unrendered placeholder reached the output")
        self.check("the managed block is shown", has("riskrails:start", out), "the managed block should be printed")
        self.check("with no ChatGPT login the pro profile is assumed", has("plan=pro (Pro)", out), out)
        self.check("the fallback says how to pick plus", has("--codex-plan plus", out), out)

    def test_02_the_plus_plan_renders_its_own_profile(self):
        probe = self.path("probe")
        rc, out = self.codex(probe, "--codex-plan", "plus", "--dry-run")
        self.check("--codex-plan plus exits 0", rc == 0, out)
        self.check("plus is reported", has("plan=plus (Plus)", out), out)
        self.check("plus runs the session at medium",
                   has('would have added model_reasoning_effort = "medium"', out), out)
        self.check("plus caps agent threads at 3",
                   has("would have added max_concurrent_threads_per_session = 3", out), out)
        self.check("the AGENTS.md block names the Plus plan", has("ChatGPT Plus plan", out), out)
        self.check("the AGENTS.md block keeps xhigh off on Plus", has("`xhigh` stays off", out), out)
        self.check("the plus block renders completely", not has("{{", out), out)
        rc, out = self.codex(probe, "--codex-plan", "team", "--dry-run")
        self.check("an unknown --codex-plan is rejected", rc != 0, out)

    def test_03_the_plan_is_read_from_the_chatgpt_login(self):
        home_p = self.path("home-plus")
        os.makedirs(os.path.join(home_p, ".codex"))
        jwt = ".".join([b64({"alg": "none"}),
                        b64({"https://api.openai.com/auth": {"chatgpt_plan_type": "plus"}}), "sig"])
        write(os.path.join(home_p, ".codex", "auth.json"),
              '{"auth_mode":"chatgpt","tokens":{"id_token":"%s"}}' % jwt)
        rc, out = self.codex(os.path.join(home_p, ".codex"), "--dry-run", home=home_p)
        self.check("chatgpt_plan_type=plus is detected", has("detected codex plan: plus", out), out)
        self.check("the detected plan selects the plus profile", has("plan=plus (Plus)", out), out)

    def test_04_real_install(self):
        rc, out = self.codex(self.dir)
        self.check("install exits 0", rc == 0, out)
        self.check("the summary names the plan", has("plan            pro", out), out)
        for f in ("agents/ai-discovery.toml agents/ai-reviewer.toml agents/log-reader.toml agents/architect.toml "
                  "agents/Explore.toml "
                  "hooks/runtime-gate.py hooks/context-guard.py hooks/lib/ai-hook-common.sh hooks/ai-git-guard.json "
                  "hooks/ai-path-guard-defaults.json hooks.json config.toml AGENTS.md "
                  "skills/ai-task/state.py skills/ai-init/scaffold-ai.sh skills/usage-report/usage-report.py "
                  "hooks/ai-guard.py hooks/guard/__init__.py hooks/guard/common.py hooks/guard/ere.py "
                  "hooks/guard/git.py hooks/guard/paths.py hooks/guard/scope.py").split():
            self.check("$f installed".replace("$f", f), os.path.exists(os.path.join(self.dir, f)), "%s missing" % f)
        self.check("the guards are executable", os.access(os.path.join(self.dir, "hooks", "ai-guard.py"), os.X_OK),
                   "guards should be executable")
        # The guards are shims over hooks/ai-guard.py and its guard/ package: the
        # installed copy must run the port, not only hold its files.
        self.check("the installed git guard runs the port and denies a force push",
                   '"permissionDecision":"deny"' in self.guard("git push --force"),
                   "the installed git guard did not deny a force push")
        self.check("the installed git guard allows ls", self.guard("ls").rstrip("\n") == "",
                   "the installed git guard should allow ls")
        self.check("the model gate is executable", os.access(os.path.join(self.dir, "hooks", "runtime-gate.py"), os.X_OK),
                   "the gate should be executable")
        self.check("the codex-model-gate.py shim is not installed",
                   not os.path.exists(os.path.join(self.dir, "hooks", "codex-model-gate.py")),
                   "the codex-model-gate.py shim is gone (redesign 1.3)")
        self.check("cap-large-read is not installed (Codex has no hookable Read tool)",
                   not os.path.exists(os.path.join(self.dir, "hooks", "cap-large-read.py")),
                   "cap-large-read has no Codex event to fire on and must not be installed")
        self.check("the Fable gate is not installed",
                   not os.path.exists(os.path.join(self.dir, "hooks", "fable-gate.py")),
                   "the Fable gate is Claude-only")

    def test_05_the_session_defaults_to_sol_at_high_effort(self):
        cfg = os.path.join(self.dir, "config.toml")
        self.check("model = gpt-5.6-sol", toml_get(cfg, "model") == "gpt-5.6-sol",
                   "model should be gpt-5.6-sol, got %s" % toml_get(cfg, "model"))
        self.check("model_reasoning_effort = high", toml_get(cfg, "model_reasoning_effort") == "high",
                   "effort should be high")
        self.check("agents are enabled", toml_get(cfg, "agents.enabled") == "True", "agents.enabled should be true")
        self.check("subagents default to Terra", toml_get(cfg, "agents.default_subagent_model") == "gpt-5.6-terra",
                   "subagent default should be Terra")
        self.check("subagents default to medium effort",
                   toml_get(cfg, "agents.default_subagent_reasoning_effort") == "medium",
                   "subagent effort should be medium")
        self.check("concurrency is bounded", toml_get(cfg, "agents.max_concurrent_threads_per_session") == "6",
                   "max_concurrent_threads_per_session should be 6")

    def test_06_hooks_json(self):
        hooks_path = os.path.join(self.dir, "hooks.json")
        data = read_json(hooks_path)
        n = len(commands(data, "PreToolUse"))
        self.check("two PreToolUse hooks registered (ai-guard, runtime-gate)", n == 2, "expected 2 PreToolUse commands, got %s" % n)
        scope = [bool(re.search("ai-guard\\.py", e["hooks"][0]["command"]))
                 for e in data["hooks"]["PreToolUse"] if re.search("apply_patch", e["matcher"])]
        self.check("the guard (its scope check) watches apply_patch", bool(scope) and scope[-1],
                   "the scope guard should match apply_patch")
        self.check("the runtime gate listens on SubagentStop",
                   bool(re.search("runtime-gate", data["hooks"]["SubagentStop"][0]["hooks"][0]["command"])),
                   "SubagentStop hook missing")
        self.check("and on SubagentStart, to count running agents",
                   bool(re.search("runtime-gate", data["hooks"]["SubagentStart"][0]["hooks"][0]["command"])),
                   "SubagentStart hook missing")
        problems = []
        for ev in ("PreToolUse", "PostToolUse"):
            # Codex 0.155 multi-agent v2 names the tool collaborationspawn_agent (namespace
            # + name, no separator). A matcher of only [A-Za-z0-9_|] is an exact list in
            # Codex, so it must be a regex; Codex tests it unanchored, like jq's test().
            ms = [e["matcher"] for e in data["hooks"][ev]
                  for h in e["hooks"] if re.search("runtime-gate", h["command"])]
            m = ms[0] if len(ms) == 1 else ""
            if not m:
                problems.append("%s: expected exactly one gate entry" % ev)
            if not has("[^A-Za-z0-9_|]", m):
                problems.append("%s gate matcher '%s' is an exact list in Codex, not a regex" % (ev, m))
            for t in ("collaborationspawn_agent", "spawn_agent", "Agent"):
                if not (m and re.search(m, t)):
                    problems.append("%s gate matcher '%s' misses %s" % (ev, m, t))
            for t in ("Bash", "apply_patch", "AgentX", "wait_agent"):
                if m and re.search(m, t):
                    problems.append("%s gate matcher '%s' also matches %s" % (ev, m, t))
        self.check("the gate's PreToolUse/PostToolUse matcher is a regex that sees collaborationspawn_agent, "
                   "spawn_agent and Agent only", not problems, problems)
        self.check("no codex-model-gate command is registered",
                   len([c for c in all_commands(data) if re.search("codex-model-gate", c)]) == 0,
                   "codex-model-gate still registered")

        # Codex has both compaction events and SessionStart, so the context guard is
        # registered on the same three events it serves on the Claude side.
        for ev in ("UserPromptSubmit", "PreCompact", "SessionStart"):
            n = len([c for c in commands(data, ev) if re.search("context-guard", c)])
            self.check("the context guard is registered once under $ev".replace("$ev", ev), n == 1,
                       "expected one %s registration, got %s" % (ev, n))
        matchers = [e["matcher"] for e in data["hooks"]["SessionStart"]
                    if any(re.search("context-guard", h["command"]) for h in e["hooks"])]
        self.check("on every SessionStart source, as on the Claude side",
                   "\n".join(matchers) == "startup|resume|clear|compact", "the SessionStart matcher is wrong")
        self.check("with the prompt path on the shorter timeout",
                   str(data["hooks"]["UserPromptSubmit"][0]["hooks"][0]["timeout"]) == "5",
                   "UserPromptSubmit should time out at 5")

        self.codex(self.dir)
        data = read_json(hooks_path)
        n = len([c for c in all_commands(data) if re.search("context-guard", c)])
        self.check("a second install does not duplicate any of the three", n == 3,
                   "expected 3 registrations after a re-install, got %s" % n)
        n = len(commands(data, "PreToolUse"))
        self.check("and the PreToolUse count is still two", n == 2, "PreToolUse should stay 2, got %s" % n)

    def test_07_an_install_from_before_wp5_is_upgraded_not_doubled(self):
        up = self.path("codex-upgrade")
        os.makedirs(os.path.join(up, "hooks"))
        os.makedirs(os.path.join(up, "agents"))
        day = today()
        write(os.path.join(up, "hooks", "codex-model-gate.py"), "#!/usr/bin/env python3\n# the old shim\n")
        write(os.path.join(up, "skills", "status", "SKILL.md"), "---\nname: status\n---\nold\n")
        stale = "code-implementer qa-runner qa-fixer db-migrator doc-lookup log-inspector sylius-i18n-keys".split()
        # Redesign 2.4: nine agents and the four tier twins are no longer installed.
        retired_24 = ("ai-context ai-expert ai-implementer ai-indexer ai-planner ai-release ai-risk ai-security "
                      "ai-tester ai-reviewer-balanced ai-risk-strong ai-planner-strong ai-expert-strong").split()
        for a in stale + retired_24:
            write(os.path.join(up, "agents", a + ".toml"), 'name = "%s"\n' % a)
        write(os.path.join(up, "agents", "ai-reviewer.toml"), "old\n")
        write(os.path.join(up, "agents", "ai-reviewer.toml.bak"), "older\n")
        old = '"$HOME/.codex/hooks/codex-model-gate.py"'
        entry = {"type": "command", "command": old, "timeout": 5}
        write(os.path.join(up, "hooks.json"), json.dumps({"hooks": {
            "PreToolUse": [{"matcher": "Agent", "hooks": [dict(entry)]}],
            "PostToolUse": [{"matcher": "Agent", "hooks": [dict(entry)]}],
            "SubagentStop": [{"hooks": [dict(entry)]}, {"hooks": [{"type": "command", "command": "my-stop.sh"}]}]}}))
        rc, out = self.codex(up, "--codex-plan", "pro")
        data = read_json(os.path.join(up, "hooks.json"))
        self.check("an upgrade replaces every codex-model-gate command",
                   len([c for c in all_commands(data) if re.search("codex-model-gate", c)]) == 0,
                   "a codex-model-gate command is left")
        with self.subTest("exactly one gate command per event after the upgrade"):
            for ev in ("PreToolUse", "PostToolUse", "SubagentStart", "SubagentStop"):
                n = len([c for c in commands(data, ev) if re.search(r"/hooks/runtime-gate\.py", c)])
                self.assertEqual(n, 1, "%s has %s gate commands after the upgrade" % (ev, n))
        self.codex(up, "--codex-plan", "pro")
        data = read_json(os.path.join(up, "hooks.json"))
        self.check("a second install changes nothing",
                   len([c for c in all_commands(data) if re.search(r"-gate\.py", c)]) == 4,
                   "reinstall doubled or renamed the gate")
        self.check("the user's own SubagentStop hook survives", "my-stop.sh" in commands(data, "SubagentStop"),
                   "user hook lost")
        self.check("the replacement is reported, with the /hooks re-trust reminder",
                   has("replaced: codex-model-gate.py hooks with runtime-gate.py — "
                       "review the changed gate entries once in /hooks", out), out)
        self.check("the installed shim is retired into backups/<date>/hooks/",
                   not os.path.exists(os.path.join(up, "hooks", "codex-model-gate.py"))
                   and has("^# the old shim", read(os.path.join(up, "backups", day, "hooks", "codex-model-gate.py"))),
                   "shim not retired: %s" % out)
        with self.subTest("the seven stale agents are retired into backups/<date>/agents/"):
            for a in stale:
                self.assertTrue(not os.path.exists(os.path.join(up, "agents", a + ".toml"))
                                and os.path.isfile(os.path.join(up, "backups", day, "agents", a + ".toml")),
                                "agents/%s.toml not retired: %s" % (a, out))
        with self.subTest("the nine agents and four twins of redesign 2.4 are retired into backups/<date>/agents/"):
            for a in retired_24:
                self.assertTrue(not os.path.exists(os.path.join(up, "agents", a + ".toml"))
                                and os.path.isfile(os.path.join(up, "backups", day, "agents", a + ".toml"))
                                and has("retired: agents/%s.toml -> backups/%s/agents/%s.toml" % (a, day, a), out),
                                "agents/%s.toml not retired (2.4): %s" % (a, out))
        got = " ".join(sorted(n[:-5] for n in os.listdir(os.path.join(up, "agents")) if n.endswith(".toml")))
        self.check("and exactly the five agents are left", got == "Explore ai-discovery ai-reviewer architect log-reader",
                   "codex agents after the upgrade: %s" % got)
        self.check("skills/status is retired into backups/<date>/skills/ on the Codex home",
                   not os.path.exists(os.path.join(up, "skills", "status"))
                   and os.path.isfile(os.path.join(up, "backups", day, "skills", "status", "SKILL.md"))
                   and has("retired: skills/status -> backups/%s/skills/status" % day, out),
                   "skills/status not retired: %s" % out)
        bak = os.path.join(up, "agents", "ai-reviewer.toml.bak")
        moved = os.path.join(up, "backups", day, "agents", "ai-reviewer.toml.bak")
        self.check("a *.bak beside a live agent moves to backups/<date>/agents/",
                   not os.path.exists(bak) and os.path.exists(moved) and read(moved).rstrip("\n") == "older",
                   "agent .bak not swept: %s" % out)
        left = bak_outside_backups(up)
        self.check("no *.bak is left outside backups/", not left, "*.bak left: %s" % left)

    def test_08_the_managed_agents_md_block(self):
        agents = read(os.path.join(self.dir, "AGENTS.md"))
        routing = read(os.path.join(self.dir, "riskrails", "routing.md"))
        self.check("exactly one managed block", count_lines("riskrails:start", agents) == 1,
                   "expected one managed block")
        self.check("routing.md names the BALANCED model", has("gpt-5.6-terra", routing), "routing.md should name Terra")
        self.check("routing.md names the EXPERT model", has("gpt-6-astra", routing), "routing.md should name Astra")
        self.check("the block carries tiers, not model names", has("Models are tiers, not names", agents),
                   "the block should carry tiers, not names")
        self.check("the block carries the pipeline contract", has("rr-build", agents),
                   "the pipeline contract is missing")

    def test_09_profile_json_r4(self):
        prof = read_json(os.path.join(self.dir, "riskrails", "profile.json"))
        ok = (prof.get("runtime") == "codex" and prof.get("plan") in ("plus", "pro") and prof.get("fable") is False
              and len(((prof.get("tiers") or {}).get("STRONG") or {}).get("model") or "") > 0)
        self.check("profile.json written for the Codex install, tiers read from the Codex profile", ok,
                   "codex profile.json missing or wrong")
        self.check("config.toml has no riskrails", not has("riskrails", read(os.path.join(self.dir, "config.toml"))),
                   "riskrails leaked into config.toml")
        probe = self.path("probe-profile")
        rc, out = self.codex(probe, "--codex-plan", "plus", "--dry-run")
        self.check("--dry-run lists the Codex profile.json",
                   has("^== profile.json (plan tables): %s/riskrails/profile.json" % probe, out),
                   "codex dry run should list profile.json")
        self.check("and does not write it", not os.path.exists(os.path.join(probe, "riskrails", "profile.json")),
                   "dry run wrote profile.json")

    def test_10_re_install_is_idempotent(self):
        before = tree_hashes(self.dir)
        self.codex(self.dir)
        after = tree_hashes(self.dir)
        changed = sorted(k for k in set(before) | set(after) if before.get(k) != after.get(k))[:10]
        self.check("a second install changes no file", before == after, "the second install changed files: %s" % changed)
        data = read_json(os.path.join(self.dir, "hooks.json"))
        self.check("hook entries are not duplicated", len(commands(data, "PreToolUse")) == 2, "hooks duplicated")
        self.check("the managed block is not duplicated",
                   count_lines("riskrails:start", read(os.path.join(self.dir, "AGENTS.md"))) == 1, "block duplicated")

    def test_11_a_user_owned_config_survives_untouched_apart_from_the_managed_keys(self):
        dir2 = self.path("codex2")
        os.makedirs(dir2)
        cfg = os.path.join(dir2, "config.toml")
        original = ('# my own notes, keep these\n'
                    'model = "gpt-6-astra"\n'
                    'model_reasoning_effort = "xhigh"\n'
                    'service_tier = "fast"\n'
                    '\n'
                    '[projects."/home/me/work"]\n'
                    'trust_level = "trusted"\n'
                    '\n'
                    '[mcp_servers.docs]\n'
                    'url = "https://developers.openai.com/mcp"\n'
                    '\n'
                    '[agents]\n'
                    'interrupt_message = false\n'
                    '\n'
                    '[marketplaces.personal]\n'
                    'source_type = "git"\n')
        write(cfg, original)
        orig_copy = self.path("config.orig")
        write(orig_copy, original)
        self.codex(dir2)
        self.check("the managed model key is updated in place", toml_get(cfg, "model") == "gpt-5.6-sol",
                   "model should be gpt-5.6-sol")
        self.check("the managed effort key is updated in place", toml_get(cfg, "model_reasoning_effort") == "high",
                   "effort should be high")
        self.check("an unrelated top-level key survives", toml_get(cfg, "service_tier") == "fast",
                   "service_tier was lost")
        self.check("an MCP server survives",
                   toml_get(cfg, "mcp_servers.docs.url") == "https://developers.openai.com/mcp",
                   "the MCP server was lost")
        self.check("a marketplace table survives", toml_get(cfg, "marketplaces.personal.source_type") == "git",
                   "the marketplace was lost")
        self.check("an unmanaged key inside [agents] survives", toml_get(cfg, "agents.interrupt_message") == "False",
                   "agents.interrupt_message was lost")
        self.check("the managed [agents] keys are added alongside it",
                   toml_get(cfg, "agents.default_subagent_model") == "gpt-5.6-terra",
                   "the subagent default was not added")
        self.check("comments survive", has("# my own notes, keep these", read(cfg)), "a comment was dropped")
        backup = os.path.join(dir2, "backups", today(), "config.toml")
        self.check("the old config is backed up into backups/<date>/, not beside it",
                   os.path.isfile(backup) and not os.path.exists(os.path.join(dir2, "config.toml.bak")),
                   "no backups/<date>/config.toml")

        def same(a, b):
            with open(a, "rb") as fa, open(b, "rb") as fb:
                return fa.read() == fb.read()

        self.check("the backup is the original file", os.path.isfile(backup) and same(orig_copy, backup),
                   "the backup does not match the original")
        # Review M1: a second install the same day changes nothing in config.toml, so
        # it must not replace the user's original in that day's backup with ours.
        rc, out = self.codex(dir2)
        self.check("a second install the same day keeps the original in the backup",
                   os.path.isfile(backup) and same(orig_copy, backup),
                   "same-day re-install overwrote the config backup: %s" % read(backup))
        self.check("an unchanged config.toml is not backed up again", not has("backup: config.toml", out), out)
        # Review I1: a symlinked instruction file is saved as its content, not as a link.
        os.makedirs(self.path("dotfiles"))
        write(self.path("dotfiles", "AGENTS.md"), "dotfile notes\n")
        link = os.path.join(dir2, "AGENTS.md")
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(self.path("dotfiles", "AGENTS.md"), link)
        self.codex(dir2)
        saved = os.path.join(dir2, "backups", today(), "AGENTS.md")
        self.check("a symlinked AGENTS.md is backed up as its content",
                   not os.path.islink(saved) and os.path.isfile(saved) and has_line(read(saved), "dotfile notes"),
                   "symlinked AGENTS.md backed up as a link")
        try:
            toml_pairs(cfg)
            parses = True
        except ValueError:
            parses = False
        self.check("the edited config still parses", parses, "the edited config is not valid TOML")

    def test_12_a_malformed_config_is_left_alone(self):
        dir3 = self.path("codex3")
        os.makedirs(dir3)
        write(os.path.join(dir3, "config.toml"), "this is not = = toml\n")
        rc, out = self.codex(dir3)
        self.check("a config that does not parse aborts the install", rc != 0, out)
        self.check("the unparseable config is left exactly as it was",
                   has_line(read(os.path.join(dir3, "config.toml")), "this is not = = toml"),
                   "the broken config was modified")

    def test_13_an_existing_third_party_hook_survives_the_merge(self):
        dir4 = self.path("codex4")
        os.makedirs(dir4)
        write(os.path.join(dir4, "hooks.json"), json.dumps(
            {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "my-own-guard.sh"}]}]}}))
        self.codex(dir4)
        data = read_json(os.path.join(dir4, "hooks.json"))
        self.check("the user's own hook is kept", "my-own-guard.sh" in commands(data, "PreToolUse"),
                   "the user's hook was clobbered")
        self.check("our guard and gate are appended alongside it", len(commands(data, "PreToolUse")) == 3,
                   "expected 3 PreToolUse commands")

    def test_14_a_hand_edited_git_guard_config_survives_a_re_install(self):
        path = os.path.join(self.dir, "hooks", "ai-git-guard.json")
        data = read_json(path)
        data["protected_branches"] += ["develop"]
        write(path, json.dumps(data))
        self.codex(self.dir)
        self.check("a local edit to ai-git-guard.json is preserved",
                   "develop" in read_json(path)["protected_branches"],
                   "the user's git guard config was overwritten")

    def test_15_backups_never_land_inside_skills(self):
        write(os.path.join(self.dir, "skills", "ai-init", "EXTRA.md"), "stale\n")
        self.codex(self.dir)
        skills = os.path.join(self.dir, "skills")
        stray = [n for n in os.listdir(skills) if n.endswith(".bak") and os.path.isdir(os.path.join(skills, n))]
        self.check("no *.bak directory is left in skills/", not stray, "a backup was left in skills/")
        self.check("the backup went to backups/<date>/skills/",
                   os.path.isdir(os.path.join(self.dir, "backups", today(), "skills", "ai-init")),
                   "backup not found in backups/<date>/skills/")

    def test_16_an_agents_md_with_a_legacy_codex_agentic_pair_gets_one_block_renamed(self):
        lg = self.path("codex-legacy")
        os.makedirs(lg)
        block = read(os.path.join(PLUGIN, "skills", "ai-init", "templates", "AGENTS.block.md"))
        legacy = re.sub(r"riskrails:(start|end)", r"Codex-agentic:\1", block)
        agents = os.path.join(lg, "AGENTS.md")
        write(agents, "# legacy\n\nkeep me above\n\n" + legacy + "\n# my notes\nkeep me below\n")
        rc, out = self.codex(lg, "--codex-plan", "pro")
        text = read(agents)
        self.check("exactly one managed block after the install",
                   count_lines(r"(riskrails|[Cc]odex-agentic):start", text, extended=True) == 1,
                   "a legacy pair was doubled")
        self.check("the legacy markers are renamed", not has("Codex-agentic", text),
                   "the legacy markers are still there")
        self.check("the text around the block is kept", has("keep me above", text) and has("keep me below", text),
                   "text around the legacy block lost")
        self.check("the install says what it renamed",
                   has("AGENTS.md: updated + renamed the legacy Codex-agentic markers", out),
                   "no rename note in the install output")
        self.check("block_size measures the renamed block", not has("AGENTS.md: managed block 0 B", out),
                   "block_size measured 0 B")
        self.codex(lg, "--codex-plan", "pro")
        self.check("a reinstall keeps one block", count_lines("riskrails:start", read(agents)) == 1,
                   "reinstall doubled the block")

    def test_17_the_shell_guard_entries_of_an_older_install_are_replaced(self):
        """3.5: the three ai-*-guard.sh entries and files give way to one ai-guard.py entry."""
        old = self.path("codex-shims")
        os.makedirs(os.path.join(old, "hooks"))
        shims = [{"matcher": "Bash", "hooks": [{"type": "command", "command": '"$HOME/.codex/hooks/ai-%s-guard.sh"' % g}]}
                 for g in ("git", "path", "scope")]
        mine = {"matcher": "Bash", "hooks": [{"type": "command", "command": "my-own-guard.sh"}]}
        write(os.path.join(old, "hooks.json"), json.dumps({"hooks": {"PreToolUse": shims + [mine]}}))
        for g in ("git", "path", "scope"):
            write(os.path.join(old, "hooks", "ai-%s-guard.sh" % g), "#!/bin/sh\n")
        rc, out = self.codex(old)
        data = read_json(os.path.join(old, "hooks.json"))
        cmds = all_commands(data)
        self.check("no shell guard entry is left", not [c for c in cmds if re.search(r"ai-(git|path|scope)-guard\.sh", c)], cmds)
        self.check("exactly one ai-guard.py entry", len([c for c in cmds if "ai-guard.py" in c]) == 1, cmds)
        self.check("the user's own hook stays", "my-own-guard.sh" in cmds, cmds)
        self.check("the install says the guard entry needs a review in /hooks",
                   "review the new guard entry once in /hooks" in out, out)
        day = datetime.date.today().isoformat()
        self.check("the shim files are retired into backups/", all(
            not os.path.lexists(os.path.join(old, "hooks", "ai-%s-guard.sh" % g))
            and os.path.isfile(os.path.join(old, "backups", day, "hooks", "ai-%s-guard.sh" % g))
            for g in ("git", "path", "scope")), out)

    def test_18_dialog_tool_only_on_verified_version(self):
        """R36.19: request_user_input only for a Codex on spike 7.0's list (>= 0.165.0); else null."""
        bare = os.pathsep.join(d for d in os.environ.get("PATH", "").split(os.pathsep)
                               if d and not os.access(os.path.join(d, "codex"), os.X_OK))
        for version, want in (("codex-cli 0.165.0", "request_user_input"), ("codex-cli 0.166.2", "request_user_input"),
                              ("codex-cli 1.0.0", "request_user_input"), ("codex-cli 0.164.0", None),
                              ("not a version", None), (None, None)):
            with self.subTest(version=version):
                home = self.path("dialog-%s" % (version or "absent").replace(" ", "-"))
                fake = os.path.join(home, "fakebin")
                os.makedirs(fake)
                if version:
                    write(os.path.join(fake, "codex"), "#!/bin/sh\necho '%s'\n" % version)
                    os.chmod(os.path.join(fake, "codex"), 0o755)
                codex_dir = os.path.join(home, ".codex")
                rc, out = install("--target", "codex", "--codex-plan", "pro",
                                  env=env_with(HOME=home, CODEX_DIR=codex_dir, PATH=fake + os.pathsep + bare))
                self.assertEqual(rc, 0, out)
                prof = read_json(os.path.join(codex_dir, "riskrails", "profile.json"))
                self.assertEqual(prof.get("dialog"), {"tool": want})
                self.assertEqual((prof.get("set_by") or {}).get("via"), "installer")

    def test_19_status_line_items(self):
        merger = os.path.join(PLUGIN, "scripts", "merge-codex-config.py")
        profile = self.path("status-profile.json")
        write(profile, json.dumps({"session": {"model": "m", "model_reasoning_effort": "high"}, "agents": {}}))
        head = 'model = "m"\nmodel_reasoning_effort = "high"\n'

        def merge(text, *flags):
            cfg = self.path("status-config.toml")
            if text is None:
                if os.path.exists(cfg):
                    os.remove(cfg)
            else:
                write(cfg, text)
            proc = subprocess.run([sys.executable, merger, cfg, "--profile", profile, "--no-backup", *flags],
                                  capture_output=True, text=True, check=False)
            return proc.returncode, read(cfg) if os.path.exists(cfg) else None, proc.stdout + proc.stderr

        both = '["model-with-reasoning", "context-used"]'
        # Review M3: an unset key is Codex's own default items; ours would replace them.
        rc, text, out = merge(None, "--status-context", "yes")
        self.check("an empty config gets no status_line, with a note",
                   rc == 0 and text == head + "\n[agents]\n" and "not set: Codex's default items" in out,
                   "%s\n%s" % (text, out))
        rc, again, out = merge(text, "--status-context", "yes")
        self.check("a second run is idempotent", rc == 0 and again == text and "already set" in out, out)
        empty = head + "\n[tui]\nstatus_line = []\n"
        rc, text, out = merge(empty, "--status-context", "yes")
        self.check("an empty list is the user's choice and stays empty",
                   rc == 0 and "status_line = []\n" in text and "empty on purpose" in out, "%s\n%s" % (text, out))

        mine = head + '\n[tui]\nstatus_line = ["git-branch", "context-used", "current-dir"]\ntheme = "dark"\n'
        rc, text, out = merge(mine, "--status-context", "yes")
        want = head + ('\n[tui]\nstatus_line = ["git-branch", "context-used", "current-dir", "model-with-reasoning"]\n'
                       'theme = "dark"\n')
        self.check("an existing list is kept in order, the missing item appended once",
                   rc == 0 and text.startswith(want), "%s\n%s" % (text, out))
        rc, again, _ = merge(text, "--status-context", "yes")
        self.check("and appended once only", again == text, again)

        multi = head + '\n[tui]\nstatus_line = [\n  "git-branch",  # mine\n  "current-dir",\n]\n\n[agents]\n'
        rc, text, out = merge(multi, "--status-context", "yes")
        self.check("a multi-line list becomes one line with the user's items first",
                   rc == 0 and 'status_line = ["git-branch", "current-dir", "model-with-reasoning", "context-used"]\n'
                   in text and "[agents]" in text, "%s\n%s" % (text, out))

        rc, text, _ = merge(head + '\n[tui]\ntheme = "dark"\n', "--status-context", "yes")
        self.check("a [tui] table without the key does not get it",
                   rc == 0 and "status_line" not in text, text)

        dotted = head + 'tui.status_line = ["git-branch"]\n'
        rc, text, out = merge(dotted, "--status-context", "yes")
        self.check("a dotted tui.status_line is left alone, the rest still merged",
                   rc == 0 and 'tui.status_line = ["git-branch"]\n' in text and "left [tui] status_line alone" in out,
                   "%s\n%s" % (text, out))

        for flags in (("--status-context", "no"), ()):
            rc, text, _ = merge(mine, *flags)
            self.check("%s touches no status_line" % (" ".join(flags) or "no flag"),
                       rc == 0 and 'status_line = ["git-branch", "context-used", "current-dir"]\n' in text, text)

        for name, flags, want in (("codex-status", (), 'status_line = ["git-branch", %s' % both[1:]),
                                  ("codex-status-off", ("--statusline-context", "no"), 'status_line = ["git-branch"]\n')):
            dirn = self.path(name)
            os.makedirs(dirn)
            write(os.path.join(dirn, "config.toml"), '[tui]\nstatus_line = ["git-branch"]\n')
            self.codex(dirn, *flags)
            self.check("installer %s: %s" % (" ".join(flags) or "default", want.strip()),
                       want in read(os.path.join(dirn, "config.toml")), read(os.path.join(dirn, "config.toml")))
        dir7 = self.path("codex-status-unset")
        os.makedirs(dir7)
        self.codex(dir7)
        self.check("the installer leaves an unset status_line to Codex",
                   "status_line" not in read(os.path.join(dir7, "config.toml")), read(os.path.join(dir7, "config.toml")))


if __name__ == "__main__":
    unittest.main()
