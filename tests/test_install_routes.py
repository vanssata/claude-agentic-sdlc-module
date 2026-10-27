#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R17: the two install routes leave one effective tree.

Route (a) is `npx riskrails` alone. Route (b) is the plugin (its cache under
<home>/plugins/cache/<marketplace>/riskrails/<ver>/, a copy of this checkout)
plus `npx riskrails`. Each route's effective inventory is what the runtime
would run and load: every registered hook (event, matcher, command with its
script resolved, the script's sha), every skill (its tree's sha), the agents,
profile.json, the managed block and the settings keys. The two must be equal,
and no hook command may be registered twice. Also Review focus 2 (a
hand-edited settings.json meets the installer), the manifests' versions, and
the plugin hook files staying the npx registrations with the plugin root.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import PLUGIN, ScratchCase, env_with, install, read, read_json, write  # noqa: E402  pylint: disable=wrong-import-position

HOME_FILE = {"claude": "settings.json", "codex": "hooks.json"}
PLUGIN_FILE = {"claude": "hooks.json", "codex": "codex-hooks.json"}
SCRIPT = re.compile(r'"?(\$HOME/\.(?:claude|codex)/hooks|\$\{CLAUDE_PLUGIN_ROOT\}/hooks)/([\w.-]+)"?')


def sha(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()[:16]


def home_sha(path, home):
    """sha of a rendered file with the home it names replaced: the routes install into two homes."""
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read().replace(home.encode(), b"<HOME>")).hexdigest()[:16]


def tree_sha(top):
    h = hashlib.sha256()
    for d, dirs, files in sorted(os.walk(top)):
        dirs[:] = sorted(x for x in dirs if x != "__pycache__")
        for n in sorted(files):
            p = os.path.join(d, n)
            h.update(os.path.relpath(p, top).encode() + b"\0" + sha(p).encode())
    return h.hexdigest()[:16]


def make_plugin_cache(home, runtime, version=None, scope="user", enabled=True):
    """What `/plugin install riskrails` leaves: this checkout under the plugin cache and, with a
    scope, the runtime's record of it (Claude: installed_plugins.json + enabledPlugins;
    Codex: a [plugins."riskrails@riskrails"] table in config.toml)."""
    rt = os.path.join(home, "." + runtime)
    version = version or read_json(os.path.join(PLUGIN, "package.json"))["version"]
    dst = os.path.join(rt, "plugins", "cache", "riskrails", "riskrails", version)
    for part in ("skills", "hooks", ".claude-plugin", ".codex-plugin"):
        shutil.copytree(os.path.join(PLUGIN, part), os.path.join(dst, part),
                        ignore=shutil.ignore_patterns("__pycache__"))
    if scope is None:
        return dst
    if runtime == "claude":
        entry = {"scope": scope, "installPath": dst, "version": version}
        if scope == "project":
            entry["projectPath"] = os.path.join(home, "project")
        write(os.path.join(rt, "plugins", "installed_plugins.json"),
              json.dumps({"version": 2, "plugins": {"riskrails@riskrails": [entry]}}))
        settings = os.path.join(rt, "settings.json")
        doc = read_json(settings) if os.path.isfile(settings) else {}
        doc.setdefault("enabledPlugins", {})["riskrails@riskrails"] = enabled
        write(settings, json.dumps(doc, indent=2) + "\n")
    else:
        config = os.path.join(rt, "config.toml")
        text = read(config) if os.path.isfile(config) else ""
        write(config, text + ("\n" if text else "") + '[plugins."riskrails@riskrails"]\nenabled = %s\n'
              % ("true" if enabled else "false"))
    return dst


PLUGIN_TABLE = re.compile(r'\n*\[plugins\."riskrails@riskrails"\]\nenabled = (true|false)\n')


def registered(home, runtime, plugin_dir):
    """(event, matcher, command, script sha) for every hook the runtime would run."""
    rt = os.path.join(home, "." + runtime)
    sources = [(read_json(os.path.join(rt, HOME_FILE[runtime])).get("hooks", {}), rt + "/hooks")]
    if plugin_dir:
        sources.append((read_json(os.path.join(plugin_dir, "hooks", PLUGIN_FILE[runtime]))["hooks"],
                        plugin_dir + "/hooks"))
    out = []
    for hooks, hook_dir in sources:
        for event, groups in hooks.items():
            for g in groups:
                for h in g.get("hooks", []):
                    cmd = h.get("command", "")
                    m = SCRIPT.search(cmd)
                    script = os.path.join(hook_dir, m.group(2)) if m else None
                    out.append((event, g.get("matcher", ""), SCRIPT.sub(r"<hooks>/\2", cmd),
                                h.get("timeout"), sha(script) if script and os.path.isfile(script) else "missing"))
    return out


def inventory(home, runtime, plugin_dir=None):
    rt = os.path.join(home, "." + runtime)
    skills_root = os.path.join(plugin_dir or rt, "skills")
    skills = {n: tree_sha(os.path.join(skills_root, n)) for n in sorted(os.listdir(skills_root))
              if os.path.isdir(os.path.join(skills_root, n))}
    agents = {n: home_sha(os.path.join(rt, "agents", n), home) for n in sorted(os.listdir(os.path.join(rt, "agents")))}
    profile = json.loads(read(os.path.join(rt, "riskrails", "profile.json")).replace(home, "<HOME>"))
    profile.pop("written_at", None)
    doc = os.path.join(rt, "CLAUDE.md" if runtime == "claude" else "AGENTS.md")
    block = re.search(r"<!-- riskrails:start -->.*?<!-- riskrails:end -->", read(doc), re.S).group(0).replace(home, "<HOME>")
    inv = {"hooks": sorted(registered(home, runtime, plugin_dir)), "skills": skills, "agents": agents,
           "profile": profile, "block": block}
    if runtime == "claude":
        settings = read_json(os.path.join(rt, "settings.json"))
        settings.pop("hooks", None)
        settings.pop("enabledPlugins", None)
        inv["settings"] = json.loads(json.dumps(settings).replace(home, "<HOME>"))
    else:
        config = re.sub(r"\n{3,}", "\n\n", PLUGIN_TABLE.sub("\n", read(os.path.join(rt, "config.toml")))).strip()
        config = config.replace(home, "<HOME>")
        inv["config"] = hashlib.sha256(config.encode()).hexdigest()[:16]
    return inv


class InstallRoutes(ScratchCase):

    def npx(self, home, runtime, *args, rc=0):
        if runtime == "claude" and "--plan" not in args:
            args = ("--plan", "pro") + args
        env = env_with(HOME=home, CLAUDE_DIR=os.path.join(home, ".claude"), CODEX_DIR=os.path.join(home, ".codex"))
        got, out = install("--target", runtime, *args, env=env)
        self.assertEqual(got, rc, out)
        return out

    def assertSkillsResolve(self, home, runtime):
        """B1: the rr-* skills' own loop finds the install root and runs state.py from it."""
        with open(os.path.join(PLUGIN, "skills", "rr-build", "SKILL.md"), encoding="utf-8") as fh:
            loop = re.search(r"^for AI_HOME in .*?^done$", fh.read(), re.S | re.M).group(0)
        env = env_with(HOME=home, CLAUDE_CONFIG_DIR=None, CODEX_HOME=None)
        proc = subprocess.run(["bash", "-c", loop + '\npython3 "$AI_HOME/skills/ai-task/state.py" --help >/dev/null'
                               '\n"$AI_HOME/riskrails/ai-path" policies/safety.md'],
                              env=env, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, "%s: the skills cannot find their scripts: %s" % (runtime, proc.stderr))

    def routes(self, runtime, *args):
        a, b = self.path(runtime + "-a" + "".join(args)), self.path(runtime + "-b" + "".join(args))
        os.makedirs(a)
        os.makedirs(b)
        self.npx(a, runtime, *args)
        plugin_dir = make_plugin_cache(b, runtime)
        out = self.npx(b, runtime, *args)
        return a, b, plugin_dir, out

    def assertNoDuplicate(self, home, runtime, plugin_dir):
        seen = [(e, c) for e, _, c, _, _ in registered(home, runtime, plugin_dir)]
        dups = sorted({x for x in seen if seen.count(x) > 1})
        self.assertEqual(dups, [], "a hook command is registered twice")

    def test_equal_effective_inventories(self):
        for runtime, args in (("claude", ("--plan", "max", "--fable", "yes")), ("claude", ("--plan", "pro")),
                              ("codex", ("--codex-plan", "pro"))):
            with self.subTest(runtime=runtime, args=args):
                a, b, plugin_dir, out = self.routes(runtime, *args)
                self.assertIn("loads the skills and runs the hooks; npx installs the skills without SKILL.md", out)
                ia, ib = inventory(a, runtime), inventory(b, runtime, plugin_dir)
                for key in ia:
                    self.assertEqual(ia[key], ib[key], "%s differs between the routes" % key)
                rt_skills = os.path.join(b, "." + runtime, "skills")
                self.assertFalse([n for n in ib["skills"] if os.path.exists(os.path.join(rt_skills, n, "SKILL.md"))],
                                 "npx installed a SKILL.md the plugin carries")
                for n in ib["skills"]:
                    plugin_files = sorted(os.path.relpath(os.path.join(d, f), os.path.join(plugin_dir, "skills", n))
                                          for d, _, fs in os.walk(os.path.join(plugin_dir, "skills", n)) for f in fs)
                    home_files = sorted(os.path.relpath(os.path.join(d, f), os.path.join(rt_skills, n))
                                        for d, _, fs in os.walk(os.path.join(rt_skills, n)) for f in fs)
                    self.assertEqual(home_files, [f for f in plugin_files if f != "SKILL.md"],
                                     "skills/%s: npx keeps every script beside the plugin's SKILL.md" % n)
                self.assertSkillsResolve(b, runtime)
                self.assertNotIn("missing", [x[4] for x in ia["hooks"] + ib["hooks"]], "a hook names a missing script")

    def test_no_duplicate_hook_command(self):
        """Risk 8: npx first, then the plugin, then npx again — nothing runs twice."""
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                home = self.path("dup-" + runtime)
                os.makedirs(home)
                self.npx(home, runtime)
                self.assertNoDuplicate(home, runtime, None)
                plugin_dir = make_plugin_cache(home, runtime)
                out = self.npx(home, runtime)
                self.assertIn("removed: the hook entries the riskrails plugin now runs", out)
                self.assertNoDuplicate(home, runtime, plugin_dir)
                day = datetime.date.today().isoformat()
                self.assertTrue(os.path.isdir(os.path.join(home, "." + runtime, "backups", day, "skills", "rr-build")),
                                "the skills an earlier npx installed are retired into backups/")
                self.assertFalse(os.path.exists(os.path.join(home, "." + runtime, "skills", "rr-build", "SKILL.md")))
                self.assertSkillsResolve(home, runtime)
                out = self.npx(home, runtime)
                self.assertNotIn("removed:", out, "a re-run removed entries again")
                self.assertNoDuplicate(home, runtime, plugin_dir)

    def test_foreign_keys_survive(self):
        """Review focus 2: a hand-edited settings.json meets the installer."""
        home = self.path("foreign")
        settings = os.path.join(home, ".claude", "settings.json")
        original = {
            "theme": "dark", "permissions": {"allow": ["Bash(ls:*)"]},
            "hooks": {"PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "/opt/mine/check.sh",
                                               "statusMessage": "Prüfe die Befehle — ✓ 検査"}]},
                {"matcher": "Read|Edit|Write|MultiEdit|NotebookEdit|Bash",
                 "hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/ai-path-guard.sh\"", "timeout": 10}]},
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "/opt/mine/hooks/ai-scope-guard.sh.wrapper"}]}],
                "Stop": [{"hooks": [{"type": "command", "command": "notify-send done"}]}]}}
        write(settings, json.dumps(original, ensure_ascii=False, indent=2) + "\n")
        before = sha(settings)
        self.npx(home, "claude", "--plan", "pro")
        after = read_json(settings)
        self.assertEqual(after["theme"], "dark")
        self.assertEqual(after["permissions"], {"allow": ["Bash(ls:*)"]})
        cmds = [(e, h["command"], h.get("statusMessage")) for e, gs in after["hooks"].items() for g in gs for h in g["hooks"]]
        self.assertIn(("PreToolUse", "/opt/mine/check.sh", "Prüfe die Befehle — ✓ 検査"), cmds)
        self.assertIn(("Stop", "notify-send done", None), cmds)
        self.assertIn(("PreToolUse", "/opt/mine/hooks/ai-scope-guard.sh.wrapper", None), cmds,
                      "L2: a user's own command that merely contains a shim's name stays")
        self.assertEqual(len([c for _, c, _ in cmds if "ai-guard.py" in c]), 1, cmds)
        self.assertFalse([c for _, c, _ in cmds if c.endswith("-guard.sh\"")], cmds)
        backup = os.path.join(home, ".claude", "backups", datetime.date.today().isoformat(), "settings.json")
        self.assertTrue(os.path.isfile(backup) and sha(backup) == before, "no dated backup of the original")

    def test_a_cache_alone_is_not_an_active_plugin(self):
        """H1: only a plugin the runtime records as installed for the user and enabled takes
        over the skills and hooks; a cache folder, a project-scope install or a disabled
        plugin leaves the npx install whole."""
        cases = (("claude", None, True), ("claude", "project", True), ("claude", "user", False),
                 ("codex", None, True), ("codex", "user", False))
        for runtime, scope, enabled in cases:
            with self.subTest(runtime=runtime, scope=scope, enabled=enabled):
                home = self.path("inactive-%s-%s-%s" % (runtime, scope, enabled))
                os.makedirs(home)
                self.npx(home, runtime)
                make_plugin_cache(home, runtime, scope=scope, enabled=enabled)
                out = self.npx(home, runtime)
                self.assertNotIn("loads the skills and runs the hooks", out)
                self.assertNotIn("removed: the hook entries the riskrails plugin now runs", out)
                hooks = [h["command"] for gs in read_json(os.path.join(home, "." + runtime, HOME_FILE[runtime]))["hooks"].values()
                         for g in gs for h in g["hooks"]]
                self.assertEqual(len([c for c in hooks if "/hooks/ai-guard.py" in c]), 1, hooks)
                self.assertTrue(os.path.isfile(os.path.join(home, "." + runtime, "skills", "rr-build", "SKILL.md")))

    def test_the_plugin_version_is_the_numerically_latest(self):
        """M2: 3.10.0 is newer than 3.9.0; Claude reads installPath, Codex compares numbers."""
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                home = self.path("versions-" + runtime)
                os.makedirs(home)
                make_plugin_cache(home, runtime, version="3.10.0")
                make_plugin_cache(home, runtime, version="3.9.0", scope=None)
                out = self.npx(home, runtime)
                self.assertIn("riskrails 3.10.0 (riskrails)", out)

    def test_an_unreadable_home_file_stops_before_any_change(self):
        """M1, L6: a settings.json / hooks.json the installer cannot merge exits 5 with nothing written."""
        bad = ('{"a": 1,, }', "[]", '{"hooks": []}', '{"hooks": {"PreToolUse": {}}}', '{"hooks": {"Stop": [1]}}')
        for runtime in ("claude", "codex"):
            for n, text in enumerate(bad):
                with self.subTest(runtime=runtime, text=text):
                    home = self.path("bad-%s-%d" % (runtime, n))
                    target = os.path.join(home, "." + runtime, HOME_FILE[runtime])
                    write(target, text)
                    shim = os.path.join(home, "." + runtime, "hooks", "ai-git-guard.sh")
                    write(shim, "#!/bin/sh\n")
                    out = self.npx(home, runtime, rc=5)
                    self.assertIn(HOME_FILE[runtime], out)
                    self.assertNotIn("Traceback", out)
                    self.assertNotIn("TypeError", out)
                    self.assertEqual(read(target), text, "the file is left as it was")
                    self.assertTrue(os.path.isfile(shim), "nothing is retired")
                    self.assertFalse(os.path.exists(os.path.join(home, "." + runtime, "agents")), "nothing is installed")

    def test_the_dry_run_names_what_it_would_retire(self):
        """L5: the dry run lists the hook files apply installs and the shims and skills it retires."""
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                home = self.path("dry-" + runtime)
                os.makedirs(home)
                out = self.npx(home, runtime, "--dry-run")
                hooks_line = re.search(r"^   hooks:   (.*)$", out, re.M).group(1).split(",")
                for name in ("hooks.json", "codex-hooks.json", "AGENTS.md", "CLAUDE.md"):
                    self.assertNotIn(name, hooks_line)
                self.assertIn("ai-guard.py", hooks_line)
                self.assertRegex(out, r"(?m)^   retire:  hooks/ai-git-guard\.sh, hooks/ai-path-guard\.sh, hooks/ai-scope-guard\.sh")
                make_plugin_cache(home, runtime)
                out = self.npx(home, runtime, "--dry-run")
                self.assertRegex(out, r"(?m)^   skills:  .*without SKILL\.md")

    def test_versions_agree(self):
        version = read_json(os.path.join(PLUGIN, "package.json"))["version"]
        claude = read_json(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"))
        market = read_json(os.path.join(PLUGIN, ".claude-plugin", "marketplace.json"))
        codex = read_json(os.path.join(PLUGIN, ".codex-plugin", "plugin.json"))
        self.assertEqual({claude["version"], market["metadata"]["version"], market["plugins"][0]["version"],
                          codex["version"]}, {version})
        self.assertEqual({claude["name"], market["name"], codex["name"],
                          read_json(os.path.join(PLUGIN, ".agents", "plugins", "marketplace.json"))["name"]}, {"riskrails"})
        self.assertEqual(read_json(os.path.join(PLUGIN, "package.json"))["dependencies"], {})

    def test_plugin_hook_files_are_the_npx_registrations(self):
        """hooks/hooks.json and hooks/codex-hooks.json drift from neither source."""
        common = read_json(os.path.join(PLUGIN, "settings.common.json"))["hooks"]
        gate = read_json(os.path.join(PLUGIN, "settings.gate.json"))["hooks"]
        want = {k: list(v) for k, v in common.items()}
        for k, v in gate.items():
            if k != "StopFailure":           # the Fable branch: npx registers it on a Fable install
                want[k] = want.get(k, []) + v
        root = lambda doc, home: json.loads(json.dumps(doc).replace(  # noqa: E731
            "$HOME/.%s/hooks/" % home, "${CLAUDE_PLUGIN_ROOT}/hooks/"))
        self.assertEqual(read_json(os.path.join(PLUGIN, "hooks", "hooks.json"))["hooks"], root(want, "claude"))
        self.assertEqual(read_json(os.path.join(PLUGIN, "hooks", "codex-hooks.json"))["hooks"],
                         root(read_json(os.path.join(PLUGIN, "codex", "hooks.json"))["hooks"], "codex"))


if __name__ == "__main__":
    unittest.main()
