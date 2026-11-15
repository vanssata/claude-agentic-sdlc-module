#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The installer's wizard on a pseudo-terminal (spec ui-first-approvals R15, R16, R17): the real
installer, a terminal for stdin, stdout and stderr, a scratch HOME with both runtime homes inside
it. Each key is sent once the screen it answers has been drawn, never after a fixed sleep.
Stdlib only; the cases skip where no pseudo-terminal opens.
"""
import os
import re
import select
import shlex
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import INSTALLER, ScratchCase, env_with, install, read  # noqa: E402  pylint: disable=wrong-import-position
from test_profile_detect import SCRUB  # noqa: E402  pylint: disable=wrong-import-position

ENTER, ESC, SPACE, DOWN, LEFT = "\r", "\x1b", " ", "\x1b[B", "\x1b[D"
STAMP = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ")
HEADER = "Review — nothing is written until you pick Install"


def plain(text):
    """The terminal's bytes as lines: carriage returns and escape sequences dropped."""
    return re.sub(r"\x1b\[[0-9;?]*[A-Za-z]", "", text.replace("\r", ""))


class Term:
    """The installer on a pseudo-terminal: expect() reads until a screen shows, send() types a key."""

    def __init__(self, args, env, timeout=30):
        try:
            self.master, slave = os.openpty()
        except (AttributeError, OSError) as exc:
            raise unittest.SkipTest("no pseudo-terminal: %s" % exc) from exc
        self.proc = subprocess.Popen([*INSTALLER, *args], stdin=slave, stdout=slave, stderr=slave, env=env)  # pylint: disable=consider-using-with
        os.close(slave)
        self.text, self.mark, self.timeout = "", 0, timeout

    def _read(self, wait):
        if not select.select([self.master], [], [], wait)[0]:
            return True
        try:
            chunk = os.read(self.master, 65536)
        except OSError:
            return False
        self.text += chunk.decode("utf-8", "replace")
        return bool(chunk)

    def expect(self, want):
        """Read until `want` is on the screen drawn since the last expect(); the text so far on a miss."""
        deadline = time.monotonic() + self.timeout
        while want not in plain(self.text[self.mark:]):
            if time.monotonic() > deadline or not self._read(0.2):
                raise AssertionError("never saw %r; the terminal showed:\n%s" % (want, plain(self.text[self.mark:])))
        self.mark = len(self.text)

    def send(self, key):
        """Type one key."""
        os.write(self.master, key.encode())

    def finish(self):
        """Read to the end of the run: (exit code, everything drawn)."""
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline and self._read(0.2):
            pass
        code = self.proc.wait(timeout=self.timeout)
        os.close(self.master)
        return code, plain(self.text)


class Wizard(ScratchCase):
    """A scratch HOME per run, the menu on, nothing that changes what detection sees."""

    ARGS = ["--target", "both"]

    def home(self, name):
        """A scratch HOME with both runtime homes (empty) inside it."""
        home = self.path(name)
        os.makedirs(os.path.join(home, ".claude"))
        os.makedirs(os.path.join(home, ".codex"))
        return home

    def env(self, home, **extra):
        """The wizard's environment: a terminal type that has a menu, no colour, the homes in the scratch HOME."""
        return env_with(HOME=home, CLAUDE_DIR=os.path.join(home, ".claude"), CODEX_DIR=os.path.join(home, ".codex"),
                        **{"TERM": "xterm", "NO_COLOR": "1", "RISKRAILS_MENU": None, **dict.fromkeys(SCRUB), **extra})

    def start(self, home, args=None, **extra):
        """The installer on a terminal."""
        return Term(self.ARGS if args is None else args, self.env(home, **extra))

    def tree(self, home):
        """{path: text} of every file under the home, the home's own path and the clock's stamps normalised."""
        found = {}
        for root, _dirs, files in os.walk(home):
            for name in files:
                path = os.path.join(root, name)
                rel = os.path.relpath(path, home)
                text = read(path) if not os.path.islink(path) else "-> " + os.readlink(path)
                found[rel] = STAMP.sub("<time>", text.replace(home, "<HOME>"))
        return found

    def through(self, term, last):
        """Enter on steps 1..last-1 of 6, then stop at step `last`'s screen."""
        for step in range(1, last + 1):
            term.expect("step %d of 6" % step)
            if step < last:
                term.send(ENTER)

    def review_command(self, screen):
        """The `same as:` line the review printed, as the argv after `npx riskrails@<version>`."""
        line = next(ln for ln in screen.splitlines() if ln.startswith("same as: "))
        return shlex.split(line[len("same as: "):])[2:]


class TestWizard(Wizard):
    """R15, R16, R17."""

    def test_enter_through_every_step_is_the_yes_install(self):
        """R15: Enter on every step, then Install, writes the tree `--yes` writes; R17: the final box."""
        wiz, yes = self.home("wiz"), self.home("yes")
        term = self.start(wiz)
        self.through(term, 6)
        term.send(ENTER)
        code, screen = term.finish()
        self.assertEqual(code, 0, screen)
        self.assertEqual(install(*self.ARGS, "--plan", "pro", "--codex-plan", "pro", "--context", "default", "--yes",
                                 env=self.env(yes, RISKRAILS_MENU="off"))[0], 0)
        self.assertGreater(len(self.tree(wiz)), 50)
        self.assertEqual(self.tree(wiz), self.tree(yes))
        self.assertIn("riskrails is installed", screen)
        self.assertIn("next: /rr-setup", screen)
        commands = [ln.strip("│ ") for ln in screen.splitlines() if "same as: " in ln]
        self.assertEqual(len(commands), 2, screen)   # the review's, then the final box's
        self.assertEqual(commands[0], commands[1])
        self.assertIn("--target both --plan pro --statusline riskrails --codex-plan pro --context default --yes", commands[0])

    def test_review_shows_the_dry_run_and_cancel_writes_nothing(self):
        """R16: the header, the dry run's text and `same as:`; Cancel exits 130 and the home has no file.
        R17: that command with --dry-run prints the text the review showed."""
        home = self.home("review")
        term = self.start(home)
        self.through(term, 6)
        shown = plain(term.text)
        self.assertIn(HEADER, shown)
        term.send(DOWN)
        term.send(DOWN)
        term.send(ENTER)
        code, screen = term.finish()
        self.assertEqual(code, 130, screen)
        self.assertEqual(self.tree(home), {})
        dry = install(*self.review_command(shown), "--dry-run", env=self.env(home, RISKRAILS_MENU="off"), merge=False)
        self.assertEqual(dry[0], 0, dry[2])
        review = STAMP.sub("<time>", shown)
        for line in STAMP.sub("<time>", dry[1]).splitlines():
            self.assertIn(line, review)

    def test_back_keeps_the_earlier_pick_and_escape_writes_nothing(self):
        """Back from step 3 returns to step 2 with the plan picked there highlighted; Esc exits 130."""
        home = self.home("back")
        term = self.start(home)
        self.through(term, 2)
        term.send(DOWN)
        term.expect("❯ 2. team-pro")
        term.send(ENTER)
        term.expect("step 3 of 6")
        term.send(LEFT)
        term.expect("❯ 2. team-pro")   # step 2 again, the earlier pick highlighted
        term.send(ENTER)
        term.expect("step 3 of 6")
        term.send(ESC)
        code, screen = term.finish()
        self.assertEqual(code, 130, screen)
        self.assertEqual(self.tree(home), {})

    def test_space_toggles_a_runtime(self):
        """The runtimes step: Space unchecks Claude Code, and the steps that follow are Codex's alone."""
        home = self.home("space")
        term = self.start(home)
        term.expect("[x] 1. claude")
        term.send(SPACE)
        term.expect("[ ] 1. claude")
        term.send(ENTER)
        term.expect("step 2 of 4")
        term.send(ESC)
        code, screen = term.finish()
        self.assertEqual(code, 130, screen)
        self.assertNotIn("› plan ›", screen.split("step 2 of 4")[-1].splitlines()[0])
        self.assertEqual(self.tree(home), {})


class TestNoWizard(Wizard):
    """The typed prompts stay where they were, and --uninstall never shows a wizard."""

    def test_menu_off_and_dumb_terminal_ask_the_typed_question(self):
        """RISKRAILS_MENU=off and TERM=dumb: today's typed plan question, no wizard screen."""
        for name, extra in (("off", {"RISKRAILS_MENU": "off"}), ("dumb", {"TERM": "dumb"})):
            with self.subTest(name):
                term = self.start(self.home(name), ["--target", "claude"], **extra)
                term.expect("Enter plan [pro/team-pro/team-max/max/max20]: ")
                term.send("pro" + ENTER)
                code, screen = term.finish()
                self.assertEqual(code, 0, screen)
                self.assertNotIn("step 1 of", screen)
                self.assertNotIn(HEADER, screen)

    def test_uninstall_shows_no_wizard(self):
        """--uninstall on a terminal goes straight to its plan."""
        term = self.start(self.home("uninstall"), ["--uninstall", "--target", "both", "--dry-run"])
        code, screen = term.finish()
        self.assertEqual(code, 0, screen)
        self.assertNotIn("step 1 of", screen)
        self.assertIn("nothing to uninstall", screen)


if __name__ == "__main__":
    unittest.main()
