#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
update_notice.py and its use in context-guard.py's SessionStart: the notice appears
for a newer cached release on a startup, for both runtimes, and nowhere else; the
refresh child writes the cache from a file:// registry; nothing is spawned without
the installer's riskrails/ directory. No network: the registry URL is a temp file
or a closed port.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import PLUGIN  # noqa: E402  pylint: disable=wrong-import-position

GUARD = os.path.join(PLUGIN, "hooks", "context-guard.py")
NOTICE = os.path.join(PLUGIN, "hooks", "update_notice.py")
COMMAND = "npx -y riskrails@latest --yes"


def installed(runtime):
    manifest = ".codex-plugin" if runtime == "codex" else ".claude-plugin"
    with open(os.path.join(PLUGIN, manifest, "plugin.json"), encoding="utf-8") as fh:
        return json.load(fh)["version"]


def bump(version, by=1):
    major, minor, patch = (int(n) for n in version.split("."))
    return f"{major}.{minor}.{patch + by}"


class TestUpdateNotice(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.home = self.tmp + "/home"
        self.config = self.home + "/.claude"
        self.codex = self.home + "/.codex"
        self.project = self.tmp + "/project"
        for path in (self.config + "/riskrails", self.codex + "/riskrails", self.project + "/.git"):
            os.makedirs(path)
        self.registry = self.tmp + "/registry.json"
        self.env = {k: v for k, v in os.environ.items() if k not in (
            "AI_HOOK_RUNTIME", "CI", "RISKRAILS_NO_UPDATE_CHECK", "CLAUDE_CODE_SESSION_ID", "CLAUDECODE")}
        self.env.update(HOME=self.home, CLAUDE_CONFIG_DIR=self.config, CODEX_HOME=self.codex,
                        AI_CONTEXT_GUARD_STATE=self.tmp + "/state",
                        RISKRAILS_REGISTRY_URL="http://127.0.0.1:9/riskrails/latest")

    def cache_path(self, runtime):
        return (self.codex if runtime == "codex" else self.config) + "/riskrails/update-check.json"

    def cache(self, runtime, latest, age=60):
        with open(self.cache_path(runtime), "w", encoding="utf-8") as fh:
            json.dump({"checked_at": int(time.time()) - age, "latest": latest}, fh)

    def start(self, runtime="claude", source="startup", **env):
        payload = {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": self.project}
        if source is not None:
            payload["source"] = source
        proc = subprocess.run([GUARD], input=json.dumps(payload), capture_output=True, text=True,
                              cwd=self.project, check=False,
                              env=dict(self.env, AI_HOOK_RUNTIME=runtime, **env))
        return proc.stdout

    def test_newer_release_is_announced(self):
        for runtime in ("claude", "codex"):
            with self.subTest(runtime=runtime):
                have = installed(runtime)
                self.cache(runtime, bump(have))
                doc = json.loads(self.start(runtime))
                self.assertEqual(
                    doc["systemMessage"],
                    f"RiskRails {bump(have)} is available (installed {have}). Update: {COMMAND} "
                    f"— inside Claude Code or Codex CLI: ! {COMMAND} — then /rr-setup --update in each project.")
                context = doc["hookSpecificOutput"]["additionalContext"]
                self.assertIn(bump(have), context)
                self.assertIn("never run the update yourself", context)

    def test_missing_source_counts_as_startup(self):
        self.cache("claude", bump(installed("claude")))
        self.assertIn("is available", self.start(source=None))

    def test_no_newer_release_changes_nothing(self):
        baseline = self.start()
        have = installed("claude")
        for latest in (have, bump(have, 0).rsplit(".", 1)[0] + ".0", "0.0.1", bump(have) + "-beta.1", "junk", None):
            with self.subTest(latest=latest):
                self.cache("claude", latest)
                self.assertEqual(self.start(), baseline)

    def test_only_a_startup_is_told(self):
        self.cache("claude", bump(installed("claude")))
        for source in ("resume", "clear", "compact"):
            with self.subTest(source=source):
                self.assertNotIn("is available", self.start(source=source))

    def test_switches_turn_it_off(self):
        self.cache("claude", bump(installed("claude")), age=10 * 86400)
        for name in ("RISKRAILS_NO_UPDATE_CHECK", "CI"):
            with self.subTest(name=name):
                self.env["RISKRAILS_REGISTRY_URL"] = "file://" + self.registry
                self.write_registry(bump(installed("claude"), 5))
                self.assertEqual(self.start(**{name: "1"}), "")
                time.sleep(0.5)
                self.assertEqual(self.read_cache("claude")["latest"], bump(installed("claude")))

    def test_no_installer_directory_spawns_nothing(self):
        shutil.rmtree(self.config + "/riskrails")
        self.write_registry(bump(installed("claude")))
        self.env["RISKRAILS_REGISTRY_URL"] = "file://" + self.registry
        self.start()
        time.sleep(0.5)
        self.assertFalse(os.path.exists(self.config + "/riskrails"))

    def test_stale_cache_starts_a_refresh(self):
        self.write_registry(bump(installed("claude"), 2))
        self.env["RISKRAILS_REGISTRY_URL"] = "file://" + self.registry
        self.start()
        for _ in range(50):
            if os.path.exists(self.cache_path("claude")):
                break
            time.sleep(0.1)
        self.assertEqual(self.read_cache("claude")["latest"], bump(installed("claude"), 2))

    def test_refresh_writes_the_cache(self):
        self.write_registry("9.9.9")
        self.refresh(RISKRAILS_REGISTRY_URL="file://" + self.registry)
        data = self.read_cache("claude")
        self.assertEqual(data["latest"], "9.9.9")
        self.assertLess(abs(time.time() - data["checked_at"]), 60)
        self.assertEqual(os.listdir(self.config + "/riskrails"), ["update-check.json"])

    def test_failed_refresh_keeps_the_previous_latest(self):
        self.cache("claude", "2.0.0", age=10 * 86400)
        self.refresh()
        data = self.read_cache("claude")
        self.assertEqual(data["latest"], "2.0.0")
        self.assertLess(abs(time.time() - data["checked_at"]), 60)

    def test_failed_first_refresh_records_the_attempt(self):
        self.refresh()
        data = self.read_cache("claude")
        self.assertIsNone(data["latest"])
        self.assertIn("checked_at", data)

    def test_prerelease_from_the_registry_is_not_kept(self):
        self.write_registry("9.9.9-rc.1")
        self.refresh(RISKRAILS_REGISTRY_URL="file://" + self.registry)
        self.assertIsNone(self.read_cache("claude")["latest"])

    def test_installed_layout_uses_profile_version(self):
        # The installer copies the hooks into <home>/hooks/ with no plugin manifest above
        # them; the installed version then comes from <home>/riskrails/profile.json.
        payload = {"hook_event_name": "SessionStart", "session_id": "s1", "cwd": self.project,
                   "source": "startup"}
        for runtime, home in (("claude", self.config), ("codex", self.codex)):
            with self.subTest(runtime=runtime):
                hooks = home + "/hooks"
                os.makedirs(hooks)
                for src in (GUARD, NOTICE):
                    shutil.copy(src, hooks)
                self.cache(runtime, "3.0.2")
                for version, expected in (("3.0.1", True), ("unknown", False)):
                    with open(home + "/riskrails/profile.json", "w", encoding="utf-8") as fh:
                        json.dump({"plugin_version": version}, fh)
                    proc = subprocess.run([hooks + "/context-guard.py"], input=json.dumps(payload),
                                          capture_output=True, text=True, cwd=self.project, check=False,
                                          env=dict(self.env, AI_HOOK_RUNTIME=runtime))
                    self.assertEqual("RiskRails 3.0.2 is available (installed 3.0.1)" in proc.stdout,
                                     expected, proc.stdout + proc.stderr)

    # -- helpers
    def write_registry(self, version):
        with open(self.registry, "w", encoding="utf-8") as fh:
            json.dump({"name": "riskrails", "version": version}, fh)

    def read_cache(self, runtime):
        with open(self.cache_path(runtime), encoding="utf-8") as fh:
            return json.load(fh)

    def refresh(self, **env):
        subprocess.run([sys.executable, "-I", NOTICE, "--refresh", self.cache_path("claude")],
                       env=dict(self.env, **env), check=False, timeout=30)


if __name__ == "__main__":
    unittest.main()
