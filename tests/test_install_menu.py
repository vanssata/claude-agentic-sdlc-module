#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
The installer's questions on a terminal. TestTypedPrompt pins the typed plan
questions as 4.0.1 asks them (spec interactive-setup-options R1, C2): Claude's
and Codex's on a pseudo-terminal, and the one stderr line each branch prints
without one. Every run is a --dry-run in a scratch HOME, so nothing reads this
machine's account or install. Stdlib only; the pty cases skip where none opens.
"""
import json
import os
import select
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from install_harness import INSTALLER, ScratchCase, env_with, install, write  # noqa: E402  pylint: disable=wrong-import-position
from test_profile_detect import SCRUB, jwt  # noqa: E402  pylint: disable=wrong-import-position

CLAUDE_MAX = '{"oauthAccount":{"organizationType":"claude_max"}}'
CLAUDE_TEAM = '{"oauthAccount":{"organizationType":"claude_team"}}'
# The questions, verbatim (bin/riskrails.js, claudeRender and codexRender).
PROPOSE = "plan: %s (%s) — Enter to confirm, or type pro/team-pro/team-max/max/max20/balanced-max: "
SEAT = "Team org detected (claude_team) but not the seat. Enter plan [team-pro/team-max]: "
TYPE_PLAN = "Could not detect plan (organizationType=''). Enter plan [pro/team-pro/team-max/max/max20]: "
CODEX_PROPOSE = "codex plan: %s (%s) — Enter to confirm, or type plus/pro/balanced-max: "
CODEX_TYPE_PLAN = "Could not detect the ChatGPT plan (chatgpt_plan_type=''). Enter plan [plus/pro]: "
ENTER = "\r"   # what a terminal sends; the line discipline turns it into the newline ask() reads up to


def on_terminal(args, env, replies=(), timeout=30):
    """The installer as a person runs it: stdin and stderr on a pseudo-terminal, stdout on a pipe.

    replies are (prompt, keys): once prompt has appeared on the terminal, after the previous
    reply's prompt, keys are typed. Returns (exit code, stdout, the terminal's text with the
    line discipline's CRLF turned back into LF). A run still going after timeout seconds is
    killed, and a reply whose prompt never appeared fails the test; both show the terminal."""
    try:
        master, slave = os.openpty()
    except (AttributeError, OSError) as exc:  # no os.openpty on Windows, no free pty in some sandboxes
        raise unittest.SkipTest("no pseudo-terminal: %s" % exc) from exc
    term, out, seen = b"", b"", 0
    todo = [(prompt.encode(), keys.encode()) for prompt, keys in replies]
    try:
        with subprocess.Popen([*INSTALLER, *args], stdin=slave, stdout=subprocess.PIPE, stderr=slave,
                              env=env) as proc:
            os.close(slave)  # the child holds its own copies: EIO on the master means they are all closed
            slave = -1
            streams, deadline = [master, proc.stdout.fileno()], time.monotonic() + timeout
            while streams:
                left = deadline - time.monotonic()
                ready = select.select(streams, [], [], left)[0] if left > 0 else []
                if not ready:
                    proc.kill()
                    raise AssertionError("still running after %ss; the terminal showed:\n%s"
                                         % (timeout, term.decode(errors="replace")))
                for fd in ready:
                    try:
                        chunk = os.read(fd, 65536)
                    except OSError:  # EIO: the master once no process holds the slave
                        chunk = b""
                    if not chunk:
                        streams.remove(fd)
                    elif fd == master:
                        term += chunk
                    else:
                        out += chunk
                while todo and term.find(todo[0][0], seen) >= 0:
                    seen = term.find(todo[0][0], seen) + len(todo[0][0])
                    os.write(master, todo.pop(0)[1])
            code = proc.wait()
    finally:
        os.close(master)
        if slave >= 0:
            os.close(slave)
    text = term.decode().replace("\r\n", "\n")
    if todo:
        raise AssertionError("never asked %r; the terminal showed:\n%s" % (todo[0][0].decode(), text))
    return code, out.decode(), text


class TestTypedPrompt(ScratchCase):
    """R1: the plan questions as a person at a terminal sees them today, and the line each branch prints without one."""

    def home(self, name, account=None, login=None, claude_plan=None, codex_plan=None):
        """A scratch HOME: ~/.claude.json, a ChatGPT login and the plan an earlier install recorded, each optional."""
        home = self.path(name)
        os.makedirs(home)
        if account is not None:
            write(os.path.join(home, ".claude.json"), account)
        if login is not None:
            write(os.path.join(home, ".codex", "auth.json"),
                  json.dumps({"auth_mode": "chatgpt", "tokens": {"id_token": jwt(login)}}))
        for runtime, plan in (("claude", claude_plan), ("codex", codex_plan)):
            if plan is not None:
                write(os.path.join(home, "." + runtime, "riskrails", "profile.json"), json.dumps({"plan": plan}))
        return home

    def env(self, home):
        """The runtime homes inside the scratch HOME, and none of the variables that change what detection sees."""
        return env_with(HOME=home, CLAUDE_DIR=os.path.join(home, ".claude"), CODEX_DIR=os.path.join(home, ".codex"),
                        **dict.fromkeys(SCRUB))

    def ask(self, home, runtime, prompt, keys):
        return on_terminal(["--target", runtime, "--dry-run"], self.env(home), [(prompt, keys)])

    # == Claude on a terminal
    def test_claude_enter_confirms_detected(self):
        prompt = PROPOSE % ("max", "detected from organizationType claude_max")
        code, out, term = self.ask(self.home("claude-enter", account=CLAUDE_MAX), "claude", prompt, ENTER)
        self.assertEqual((code, term), (0, prompt + "\n"))
        self.assertIn("== claude: plan=max (Max, max profile)", out)

    def test_claude_typed_plan_wins(self):
        prompt = PROPOSE % ("max", "detected from organizationType claude_max")
        code, out, term = self.ask(self.home("claude-typed", account=CLAUDE_MAX), "claude", prompt, "pro" + ENTER)
        self.assertEqual((code, term), (0, prompt + "pro\n"))
        self.assertIn("== claude: plan=pro (Pro, pro profile)", out)

    def test_claude_previous_install_is_proposed(self):
        """The plan the last install recorded is the proposal, ahead of the detected one."""
        prompt = PROPOSE % ("max20", "recorded by the previous install")
        home = self.home("claude-recorded", account=CLAUDE_MAX, claude_plan="max20")
        code, out, term = self.ask(home, "claude", prompt, ENTER)
        self.assertEqual((code, term), (0, prompt + "\n"))
        self.assertIn("== claude: plan=max20 (Max 20x, max profile)", out)

    def test_claude_team_seat_typed(self):
        code, out, term = self.ask(self.home("claude-team", account=CLAUDE_TEAM), "claude", SEAT, "team-max" + ENTER)
        self.assertEqual((code, term), (0, SEAT + "team-max\n"))
        self.assertIn("== claude: plan=team-max (Team Max, max profile)", out)

    def test_claude_undetected_typed(self):
        code, out, term = self.ask(self.home("claude-unknown", account="{}"), "claude", TYPE_PLAN, "max" + ENTER)
        self.assertEqual((code, term), (0, TYPE_PLAN + "max\n"))
        self.assertIn("== claude: plan=max (Max, max profile)", out)

    def test_claude_undetected_enter_exits_2(self):
        """Enter alone on an undetected plan is no plan: exit 2, nothing rendered (the baseline of the spec's B4)."""
        code, out, term = self.ask(self.home("claude-empty", account="{}"), "claude", TYPE_PLAN, ENTER)
        self.assertEqual((code, term), (2, TYPE_PLAN + "\n--plan must be pro, team-pro, team-max, max, max20 or "
                                            "balanced-max (got '')\n"))
        self.assertNotIn("== claude:", out)

    # == Codex on a terminal
    def test_codex_enter_confirms_detected(self):
        prompt = CODEX_PROPOSE % ("plus", "detected from chatgpt_plan_type")
        code, out, term = self.ask(self.home("codex-enter", login="plus"), "codex", prompt, ENTER)
        self.assertEqual((code, term), (0, prompt + "\n"))
        self.assertIn("== codex: plan=plus (Plus)", out)

    def test_codex_typed_plan_wins(self):
        prompt = CODEX_PROPOSE % ("plus", "detected from chatgpt_plan_type")
        code, out, term = self.ask(self.home("codex-typed", login="plus"), "codex", prompt, "pro" + ENTER)
        self.assertEqual((code, term), (0, prompt + "pro\n"))
        self.assertIn("== codex: plan=pro (Pro)", out)

    def test_codex_previous_install_is_proposed(self):
        """The plan the last install recorded is the proposal, ahead of the detected one."""
        prompt = CODEX_PROPOSE % ("pro", "recorded by the previous install")
        code, out, term = self.ask(self.home("codex-recorded", login="plus", codex_plan="pro"), "codex", prompt, ENTER)
        self.assertEqual((code, term), (0, prompt + "\n"))
        self.assertIn("== codex: plan=pro (Pro)", out)

    def test_codex_undetected_typed(self):
        code, out, term = self.ask(self.home("codex-unknown"), "codex", CODEX_TYPE_PLAN, "plus" + ENTER)
        self.assertEqual((code, term), (0, CODEX_TYPE_PLAN + "plus\n"))
        self.assertIn("== codex: plan=plus (Plus)", out)

    def test_codex_undetected_enter_exits_2(self):
        code, out, term = self.ask(self.home("codex-empty"), "codex", CODEX_TYPE_PLAN, ENTER)
        self.assertEqual((code, term), (2, CODEX_TYPE_PLAN + "\n--codex-plan must be plus, pro or balanced-max (got '')\n"))
        self.assertNotIn("== codex:", out)

    # == no question
    def test_no_question_on_a_terminal(self):
        """A flag that names the plan, or --yes, asks nothing on a terminal either; --yes prints the line a pipe gets."""
        home = self.home("flags", account=CLAUDE_MAX, login="plus")
        for args, shown, plans in (
                (["--target", "claude", "--plan", "max"], "", ["== claude: plan=max (Max, max profile)"]),
                (["--target", "codex", "--codex-plan", "pro"], "", ["== codex: plan=pro (Pro)"]),
                (["--target", "claude", "--yes"], "detected plan: max (organizationType claude_max)\n",
                 ["== claude: plan=max (Max, max profile)"]),
                (["--target", "codex", "--yes"], "detected codex plan: plus (chatgpt_plan_type)\n",
                 ["== codex: plan=plus (Plus)"]),
                (["--target", "both", "--plan", "balanced-max"], "",
                 ["== claude: plan=balanced-max (BalancedMax, max profile)", "== codex: plan=balanced-max (BalancedMax)"])):
            with self.subTest(" ".join(args)):
                code, out, term = on_terminal([*args, "--dry-run"], self.env(home))
                self.assertEqual((code, term), (0, shown))
                for line in plans:
                    self.assertIn(line, out)

    def test_without_a_terminal(self):
        """stdin is no terminal: no question, and each branch prints exactly one line on stderr."""
        for name, runtime, scene, want_code, line in (
                ("claude-detected", "claude", {"account": CLAUDE_MAX}, 0, "detected plan: max (organizationType claude_max)"),
                ("claude-team", "claude", {"account": CLAUDE_TEAM}, 0,
                 "detected plan: team (claude_team) — seat unknown, using team-pro (Pro's models and limits); "
                 "pass --plan team-max for a Premium seat"),
                ("claude-recorded", "claude", {"account": "{}", "claude_plan": "max20"}, 0,
                 "plan: max20 (recorded by the previous install; organizationType='')"),
                ("claude-none", "claude", {"account": "{}"}, 1, "Could not detect plan; pass --plan pro|team-pro|team-max|max|max20"),
                ("codex-detected", "codex", {"login": "plus"}, 0, "detected codex plan: plus (chatgpt_plan_type)"),
                ("codex-recorded", "codex", {"codex_plan": "plus"}, 0, "codex plan: plus (recorded by the previous install)"),
                ("codex-none", "codex", {}, 0,
                 "could not detect the ChatGPT plan; using the pro profile — pass --codex-plan plus on Plus")):
            with self.subTest(name):
                home = self.home("piped-" + name, **scene)
                code, _out, err = install("--target", runtime, "--dry-run", env=self.env(home), merge=False)
                self.assertEqual((code, err), (want_code, line + "\n"))


if __name__ == "__main__":
    unittest.main()
