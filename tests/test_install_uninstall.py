#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R18: `--uninstall` on a seeded home. Every pre-existing file comes back equal except the printed
"kept" items; nothing is deleted, only moved under backups/<stamp>/; a second run does nothing.
Each case installs into its own scratch home and clocks both runs with RISKRAILS_NOW, so the
uninstall's backups are in backups/2026-03-04T050607 (the install took backups/2026-03-04).
"""
import json
import os
import shutil
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import ScratchCase, env_with, install, read, read_json, write  # noqa: E402  pylint: disable=wrong-import-position

CLOCK = "2026-03-04T05:06:07"
STAMP = "backups/2026-03-04T050607"
OWN_LINE = "my-statusline.sh"
SETTINGS = {
    "theme": "dark",
    "env": {"MY_VAR": "1"},
    "statusLine": {"type": "command", "command": OWN_LINE},
    "hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "command": "/home/me/bin/mine.sh"}]}],
              "Notification": [{"hooks": [{"type": "command", "command": "/home/me/bin/notify.sh"}]}]},
}
CLAUDE_MD = "# My notes\n\nKeep answers short.\n"
HOOKS = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "/home/me/bin/codex-stop.sh"}]}]}}
AGENTS_MD = "codex notes\n"


def run(home, *args, clock=CLOCK):
    """The installer with the home's own flags; (exit code, output)."""
    flag = "--codex-home" if os.path.basename(home).startswith("codex") else "--home"
    return install(*args, flag, home, env=env_with(HOME=home, RISKRAILS_NOW=clock))


def read_bytes(path):
    with open(path, "rb") as fh:
        return fh.read()


def files(home):
    """{relative path: bytes} of every file and link under home, backups/ left out."""
    found = {}
    for top, dirs, names in os.walk(home):
        if top == home:
            dirs[:] = [d for d in dirs if d != "backups"]
        for name in names:
            full = os.path.join(top, name)
            found[os.path.relpath(full, home)] = os.readlink(full) if os.path.islink(full) else read_bytes(full)
    return found


def plan_lines(out):
    return [line for line in out.splitlines() if line.startswith(("moved:", "edited:", "kept:"))]


class Uninstall(ScratchCase):

    def seeded_claude(self, name):
        home = self.path(name)
        write(os.path.join(home, "settings.json"), json.dumps(SETTINGS))
        write(os.path.join(home, "CLAUDE.md"), CLAUDE_MD)
        write(os.path.join(home, "agents", "mine.md"), "---\nname: mine\n---\nmy agent\n")
        write(os.path.join(home, "skills", "myskill", "SKILL.md"), "---\nname: myskill\n---\nmine\n")
        write(os.path.join(home, "hooks", "mine.sh"), "#!/bin/sh\n")
        before = files(home)
        code, out = run(home, "--yes", "--target", "claude", "--plan", "pro")
        self.assertEqual(code, 0, out)
        return home, before

    def test_01_a_seeded_home_comes_back_and_nothing_is_deleted(self):
        home, before = self.seeded_claude("claude-roundtrip")
        installed = files(home)
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 0, out)
        after = files(home)
        for rel, data in before.items():
            if rel not in ("settings.json", "CLAUDE.md"):
                self.assertEqual(after.get(rel), data, "%s did not come back as it was" % rel)
        self.assertEqual(json.loads(after["settings.json"]), SETTINGS, "settings.json is not the seeded one")
        self.assertEqual(after["CLAUDE.md"].decode(), CLAUDE_MD, "CLAUDE.md is not the seeded one")
        gone = sorted(set(installed) - set(after))
        self.assertTrue(gone and "riskrails/routing.md" in gone and "agents/architect.md" in gone, gone)
        lost = [rel for rel in gone if not os.path.isfile(os.path.join(home, STAMP, rel))]
        self.assertEqual(lost, [], "removed from its place and not under %s" % STAMP)
        for rel in ("settings.json", "CLAUDE.md"):
            self.assertEqual(read(os.path.join(home, STAMP, rel)), installed[rel].decode(), "the %s backup is not the installed file" % rel)
        for kept in ("kept: Codex config.toml: values stay", "kept: the riskrails plugin: stays installed", "kept: every project's .ai/: stays"):
            self.assertIn(kept, out)

    def test_02_a_settings_key_edited_after_the_install_is_kept_and_printed(self):
        home, _ = self.seeded_claude("claude-edited")
        settings = read_json(os.path.join(home, "settings.json"))
        settings["model"] = "my-own-model"
        write(os.path.join(home, "settings.json"), json.dumps(settings))
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(read_json(os.path.join(home, "settings.json"))["model"], "my-own-model")
        self.assertIn("kept: settings.json: model differs from what the recorded plan writes; left as it is", out)

    def test_03_a_second_uninstall_does_nothing_and_says_so(self):
        home, _ = self.seeded_claude("claude-twice")
        run(home, "--uninstall", "--target", "claude", "--yes")
        before, backups = files(home), sorted(os.listdir(os.path.join(home, "backups")))
        code, out = run(home, "--uninstall", "--target", "claude", "--yes", clock="2026-03-04T06:00:00")
        self.assertEqual(code, 0, out)
        self.assertIn("nothing to uninstall", out)
        self.assertEqual((files(home), sorted(os.listdir(os.path.join(home, "backups")))), (before, backups))

    def test_04_dry_run_writes_nothing_and_prints_the_plan_of_the_real_run(self):
        home, _ = self.seeded_claude("claude-dry")
        before, backups = files(home), sorted(os.listdir(os.path.join(home, "backups")))
        code, dry = run(home, "--uninstall", "--target", "claude", "--dry-run")
        self.assertEqual(code, 0, dry)
        self.assertEqual((files(home), sorted(os.listdir(os.path.join(home, "backups")))), (before, backups))
        self.assertIn("dry run, nothing written", dry)
        _, real = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertTrue(plan_lines(dry))
        self.assertEqual(plan_lines(dry), plan_lines(real))

    def test_05_a_flag_that_does_not_go_with_uninstall_is_a_usage_error(self):
        home, _ = self.seeded_claude("claude-flag")
        before = files(home)
        for flag in (["--plan", "pro"], ["--context=economy"], ["--statusline", "own"]):
            code, out = run(home, "--uninstall", "--target", "claude", "--yes", *flag)
            self.assertEqual(code, 2, out)
            self.assertIn(flag[0].split("=")[0] + " does not go with --uninstall", out)
        self.assertEqual(files(home), before)

    def test_06_without_a_terminal_it_needs_yes_or_dry_run(self):
        home, _ = self.seeded_claude("claude-tty")
        before = files(home)
        code, out = run(home, "--uninstall", "--target", "claude")
        self.assertEqual(code, 2, out)
        self.assertIn("--yes", out)
        self.assertIn("--dry-run", out)
        self.assertEqual(files(home), before)

    def test_08_the_launcher_link_moves_with_the_install_and_a_foreign_one_stays(self):
        base = self.path("launcher")
        home, link = os.path.join(base, ".claude"), os.path.join(base, ".local", "bin", "claude-1m")
        os.makedirs(os.path.dirname(link))
        code, out = install("--yes", "--target", "claude", "--plan", "max", "--home", home,
                            env=env_with(HOME=base, RISKRAILS_NOW=CLOCK))
        self.assertEqual(code, 0, out)
        self.assertEqual(os.readlink(link), os.path.join(home, "bin", "claude-1m"), "the install made no link")
        code, dry = install("--uninstall", "--target", "claude", "--dry-run", "--home", home, env=env_with(HOME=base, RISKRAILS_NOW=CLOCK))
        self.assertIn("moved: ~/.local/bin/claude-1m -> backups/", dry)
        self.assertTrue(os.path.islink(link), "the dry run touched the link")
        code, out = install("--uninstall", "--target", "claude", "--yes", "--home", home, env=env_with(HOME=base, RISKRAILS_NOW=CLOCK))
        self.assertEqual(code, 0, out)
        self.assertFalse(os.path.lexists(link), "the link is still on the PATH")
        moved = os.path.join(home, "backups", "2026-03-04", ".local", "bin", "claude-1m")   # a fresh install took no backup, so the date is free
        self.assertEqual(os.readlink(moved), os.path.join(home, "bin", "claude-1m"), "the link is not under backups/")
        code, out = install("--uninstall", "--target", "claude", "--yes", "--home", home, env=env_with(HOME=base, RISKRAILS_NOW="2026-03-04T06:00:00"))
        self.assertIn("nothing to uninstall", out)
        for kind in ("file", "link"):
            other = self.path("foreign-" + kind)
            os.makedirs(os.path.join(other, ".local", "bin"))
            foreign = os.path.join(other, ".local", "bin", "claude-1m")
            code, out = install("--yes", "--target", "claude", "--plan", "max", "--home", os.path.join(other, ".claude"),
                                env=env_with(HOME=other, RISKRAILS_NOW=CLOCK))
            self.assertEqual(code, 0, out)
            os.remove(foreign)   # the install links over a link of any kind; the foreign one comes after it
            if kind == "file":
                write(foreign, "mine\n")
            else:
                os.symlink("/usr/bin/true", foreign)
            code, out = install("--uninstall", "--target", "claude", "--yes", "--home", os.path.join(other, ".claude"),
                                env=env_with(HOME=other, RISKRAILS_NOW=CLOCK))
            self.assertEqual(code, 0, out)
            self.assertNotIn("~/.local/bin", out)
            self.assertEqual(os.readlink(foreign) if kind == "link" else read(foreign), "/usr/bin/true" if kind == "link" else "mine\n")

    def test_07_a_codex_home_keeps_its_config_and_the_users_hooks(self):
        home = self.path("codex-roundtrip")
        write(os.path.join(home, "hooks.json"), json.dumps(HOOKS))
        write(os.path.join(home, "AGENTS.md"), AGENTS_MD)
        write(os.path.join(home, "agents", "mine.toml"), "name = 'mine'\n")
        code, out = run(home, "--yes", "--target", "codex", "--codex-plan", "pro")
        self.assertEqual(code, 0, out)
        installed = files(home)
        code, out = run(home, "--uninstall", "--target", "codex", "--yes")
        self.assertEqual(code, 0, out)
        after = files(home)
        self.assertEqual(json.loads(after["hooks.json"]), HOOKS)
        self.assertEqual(after["AGENTS.md"].decode(), AGENTS_MD)
        self.assertEqual(after["agents/mine.toml"], b"name = 'mine'\n")
        self.assertEqual(after["config.toml"], installed["config.toml"], "config.toml values stay")
        self.assertIn("kept: Codex config.toml: values stay", out)
        gone = sorted(set(installed) - set(after))
        self.assertTrue([g for g in gone if g.startswith("agents/")], gone)
        self.assertEqual([g for g in gone if not os.path.isfile(os.path.join(home, STAMP, g))], [])

    def test_09_hook_entries_go_when_the_hooks_directory_was_deleted_by_hand(self):
        home, _ = self.seeded_claude("claude-nohooks")
        shutil.rmtree(os.path.join(home, "hooks"))
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 0, out)
        self.assertEqual(json.loads(read_bytes(os.path.join(home, "settings.json"))), SETTINGS)

    def test_10_a_move_that_fails_stops_with_settings_clean_and_a_second_run_finishes(self):
        """The failing move, the same for any user and root: backups/ is a link into skills/rr-build, so the
        move of skills/rr-build to backups/<stamp>/skills/rr-build is a move into itself (EINVAL)."""
        home, _ = self.seeded_claude("claude-partial")
        backups, inside = os.path.join(home, "backups"), os.path.join(home, "skills", "rr-build")
        os.rename(backups, os.path.join(inside, "earlier"))
        os.symlink(inside, backups)
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 1, out)
        for part in ("could not move skills/rr-build into backups/", "EINVAL", "done: edited settings.json", "left: skills/rr-build",
                     "nothing was deleted", "run --uninstall again", "backups/2026-03-04/)"):
            self.assertIn(part, out)
        self.assertNotIn("at Object", out, "a stack trace")
        self.assertEqual(json.loads(read_bytes(os.path.join(home, "settings.json"))), SETTINGS, "settings.json still holds entries of ours")
        os.remove(backups)
        os.mkdir(backups)
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 0, out)
        self.assertTrue(os.path.isfile(os.path.join(backups, "2026-03-04", "skills", "rr-build", "SKILL.md")))
        left = [rel for rel in files(home) if rel.startswith(("skills/rr-", "agents/architect", "hooks/ai-guard", "riskrails/"))]
        self.assertEqual(left, [])
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertIn("nothing to uninstall", out)

    def test_11_a_key_the_install_overwrote_is_named_with_the_backup_that_holds_the_earlier_value(self):
        home = self.path("claude-overwritten")
        write(os.path.join(home, "settings.json"), json.dumps({"autoCompactEnabled": False, "theme": "dark"}))
        code, out = run(home, "--yes", "--target", "claude", "--plan", "max")
        self.assertEqual(code, 0, out)
        code, dry = run(home, "--uninstall", "--target", "claude", "--dry-run")
        code, out = run(home, "--uninstall", "--target", "claude", "--yes")
        self.assertEqual(code, 0, out)
        backup = os.path.join(home, "backups", "2026-03-04", "settings.json")
        for text in (dry, out):
            self.assertIn("removed: settings.json: autoCompactEnabled", text)
            self.assertIn("an earlier value of yours, if you had one, is in " + backup, text)
        self.assertFalse(read_json(backup)["autoCompactEnabled"])
        self.assertNotIn("autoCompactEnabled", read_json(os.path.join(home, "settings.json")))


if __name__ == "__main__":
    unittest.main()
