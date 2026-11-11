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
import re
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


def on_terminal(args, env, replies=(), timeout=30, cmd=None):
    """The installer as a person runs it: stdin and stderr on a pseudo-terminal, stdout on a pipe.

    replies are (prompt, keys): once prompt has appeared on the terminal, after the previous
    reply's prompt, keys are typed. Returns (exit code, stdout, the terminal's text with the
    line discipline's CRLF turned back into LF). A run still going after timeout seconds is
    killed, and a reply whose prompt never appeared fails the test; both show the terminal.
    cmd, when given, runs instead of the installer with args (a shell around it, say)."""
    try:
        master, slave = os.openpty()
    except (AttributeError, OSError) as exc:  # no os.openpty on Windows, no free pty in some sandboxes
        raise unittest.SkipTest("no pseudo-terminal: %s" % exc) from exc
    term, out, seen = b"", b"", 0
    todo = [(prompt.encode(), keys.encode()) for prompt, keys in replies]
    try:
        with subprocess.Popen(cmd or [*INSTALLER, *args], stdin=slave, stdout=subprocess.PIPE, stderr=slave,
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
                        RISKRAILS_MENU="off", **dict.fromkeys(SCRUB))

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


MENU = os.path.join(os.path.dirname(INSTALLER[1]), "menu.js")


def node_json(script, *args):
    """Run a node script with bin/menu.js required as `m`; its stdout parsed as JSON."""
    proc = subprocess.run([INSTALLER[0], "-e", "const m = require(%s);\n%s" % (json.dumps(MENU), script), *args],
                          capture_output=True, text=True, check=True, stdin=subprocess.DEVNULL)
    return json.loads(proc.stdout)


class TestReducer(unittest.TestCase):
    """R2: bin/menu.js's pure key reducer and the keypress-to-token mapping, without a terminal."""

    def test_keys(self):
        """↑/k ↓/j stop at the ends, Home/End, 1–9 jump (never past the list), Enter picks, Ctrl-C/Esc/q abort."""
        run = ("const [count, index, keys] = JSON.parse(process.argv[1]);\n"
               "let s = {index, count, done: null};\n"
               "for (const k of keys) { s = m.reduce(s, m.token(k)); if (s.done) break; }\n"
               "process.stdout.write(JSON.stringify([s.index, s.done]));")
        key = lambda name, **kw: {"name": name, **kw}  # noqa: E731 pylint: disable=unnecessary-lambda-assignment
        for name, count, index, keys, want in (
                ("down", 6, 0, [key("down")], [1, None]),
                ("j", 6, 0, [key("j"), key("j")], [2, None]),
                ("up stops at the top", 6, 0, [key("up"), key("k")], [0, None]),
                ("down stops at the bottom", 3, 1, [key("down")] * 5, [2, None]),
                ("home", 6, 4, [key("home")], [0, None]),
                ("end", 6, 1, [key("end")], [5, None]),
                ("digit jumps", 6, 0, [key("4")], [3, None]),
                ("digit past the list is ignored", 3, 1, [key("7")], [1, None]),
                ("enter picks", 6, 2, [key("return")], [2, "pick"]),
                ("lf enter picks", 6, 2, [key("down"), key("enter")], [3, "pick"]),
                ("escape aborts", 6, 2, [key("escape")], [2, "abort"]),
                ("q aborts", 6, 2, [key("q")], [2, "abort"]),
                ("ctrl-c aborts", 6, 2, [key("c", ctrl=True)], [2, "abort"]),
                ("other keys do nothing", 6, 2, [key("x"), key("k", ctrl=True), key("c"), {"sequence": "?"}], [2, None])):
            with self.subTest(name):
                self.assertEqual(node_json(run, json.dumps([count, index, keys])), want)

    def test_no_terminal_exits_3(self):
        """Without a terminal the child draws nothing, prints nothing and exits 3: the installer types instead."""
        spec = json.dumps({"title": "plan", "items": [{"value": "pro", "label": "pro"}], "initial": 0})
        proc = subprocess.run([INSTALLER[0], MENU], capture_output=True, text=True, check=False,
                              stdin=subprocess.DEVNULL, env=env_with(RISKRAILS_MENU_SPEC=spec))
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (3, "", ""))

    def test_rows_fit_the_terminal(self):
        """A row wider than the terminal is cut, so the redraw erases exactly the lines it drew."""
        spec = {"title": "plan", "items": [{"value": "pro", "label": "pro", "note": "x" * 200}], "initial": 0}
        shown = node_json("process.stdout.write(JSON.stringify(m.lines(JSON.parse(process.argv[1]), 0, 40)))",
                          json.dumps(spec))
        self.assertEqual(len(shown), 2)
        self.assertTrue(all(len(line.replace("\x1b[7m", "").replace("\x1b[0m", "")) <= 39 for line in shown), shown)


DOWN, ESC, CTRL_C = "\x1b[B", "\x1b", "\x03"
CLAUDE_MENUS = ("plan (", "fable (", "context —", "statusline —")   # a max plan, the order the installer asks


class TestMenu(ScratchCase):
    """R3–R8: the arrow-key menus on a terminal. Enter through every menu gives the run a pipe gets."""

    home = TestTypedPrompt.home

    def env(self, home, path=None, homes=True, **extra):
        """The menu on (a terminal type that has one), the runtime homes in the scratch HOME unless homes=False."""
        dirs = {"CLAUDE_DIR": os.path.join(home, ".claude"), "CODEX_DIR": os.path.join(home, ".codex")} if homes else {}
        overrides = {"HOME": home, "TERM": "xterm", "RISKRAILS_MENU": None, **dirs, **dict.fromkeys(SCRUB)}
        overrides.update({"PATH": path} if path else {}, **extra)
        return env_with(**overrides)

    def piped(self, home, *args, **env):
        """The same run without a terminal: its stdout is what Enter through every menu must give
        (the timestamps a dry run prints aside; see same())."""
        return install(*args, "--dry-run", env=self.env(home, **env), merge=False)[1]

    def same(self, out, piped):
        """Two dry runs' stdout, equal but for the second their UTC timestamps fall on."""
        stamp = lambda s: re.sub(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", "<utc>", s)  # noqa: E731 pylint: disable=unnecessary-lambda-assignment
        self.assertEqual(stamp(out), stamp(piped))

    def bare_path(self, home, *runtimes):
        """PATH without any claude or codex, plus a fake executable for each runtime named."""
        fake = os.path.join(home, "fakebin")
        os.makedirs(fake, exist_ok=True)
        for rt in runtimes:
            write(os.path.join(fake, rt), "#!/bin/sh\necho '%s 1.0.0'\n" % rt)
            os.chmod(os.path.join(fake, rt), 0o755)
        bare = [d for d in os.environ.get("PATH", "").split(os.pathsep)
                if d and not any(os.access(os.path.join(d, rt), os.X_OK) for rt in ("claude", "codex"))]
        return os.pathsep.join([fake, *bare])

    def test_plan_enter_confirms(self):
        """R3: the proposal is preselected — detected, else the previous install's (also for a Team org with no
        seat), else pro (D3: Enter installs it instead of exiting) — and Enter gives the piped run's stdout."""
        for name, scene, why, plan in (
                ("detected", {"account": CLAUDE_MAX}, "detected from organizationType claude_max", "max"),
                ("recorded", {"account": "{}", "claude_plan": "max20"}, "recorded by the previous install", "max20"),
                ("team-recorded", {"account": CLAUDE_TEAM, "claude_plan": "max"}, "recorded by the previous install", "max"),
                ("team", {"account": CLAUDE_TEAM}, "Team org claude_team, seat unknown", "team-pro"),
                ("undetected", {"account": "{}"}, "could not detect the plan, organizationType=''", "pro")):
            with self.subTest(name):
                home = self.home("enter-" + name, **scene)
                menus = [m for m in CLAUDE_MENUS if plan in ("max", "max20", "team-max") or m != "fable ("]
                code, out, term = on_terminal(["--target", "claude", "--dry-run"], self.env(home),
                                              [(m, ENTER) for m in menus])
                self.assertEqual(code, 0, term)
                self.assertIn("plan (%s) — ↑/↓" % why, term)
                self.assertIn("plan: %s (%s)\n" % (plan, why), term)
                self.assertIn("== claude: plan=%s " % plan, out)
                # Piped, an undetected plan exits 1 and a Team org wins over a recorded plan (R1); on a terminal
                # the recorded plan is proposed first, as the typed question proposes it.
                if name in ("detected", "recorded"):
                    self.same(out, self.piped(home, "--target", "claude"))

    def test_plan_arrow_down(self):
        """R3: ↓ from the detected max is max20, the six plans in the header's order."""
        home = self.home("arrow", account=CLAUDE_MAX)
        code, out, term = on_terminal(["--target", "claude", "--dry-run"], self.env(home),
                                      [("plan (", DOWN + ENTER), *[(m, ENTER) for m in CLAUDE_MENUS[1:]]])
        self.assertEqual(code, 0, term)
        self.assertIn("plan: max20\n", term)
        self.assertIn("== claude: plan=max20 (Max 20x, max profile)", out)
        rows = [line for line in term.split("plan (")[1].splitlines()[1:7]]
        self.assertEqual([r.split(". ")[1].split()[0] for r in rows],
                         ["pro", "team-pro", "team-max", "max", "max20", "balanced-max"])

    def test_codex_plan(self):
        """R4: the Codex plan menu preselects the detected plan; with --target both it comes last, after
        Claude's plan, fable, context and statusline (context is asked once)."""
        home = self.home("codex", account=CLAUDE_MAX, login="plus")
        code, out, term = on_terminal(["--target", "codex", "--dry-run"], self.env(home),
                                      [("context —", ENTER), ("codex plan (", DOWN + ENTER)])
        self.assertEqual(code, 0, term)
        self.assertIn("codex plan (detected from chatgpt_plan_type) — ↑/↓", term)
        self.assertIn("codex plan: pro\n", term)
        self.assertIn("== codex: plan=pro (Pro)", out)
        code, out, term = on_terminal(["--target", "both", "--dry-run"], self.env(home),
                                      [(m, ENTER) for m in (*CLAUDE_MENUS, "codex plan (")])
        self.assertEqual(code, 0, term)
        self.assertEqual(term.count("context —"), 1)
        self.same(out, self.piped(home, "--target", "both"))

    def test_runtime_menu(self):
        """R5: with no --target, --home or --codex-home, the detected set is preselected; a pick installs that set;
        a flag or a named home skips the menu; nothing detected is today's exit 1, no menu."""
        home = self.home("runtime", account=CLAUDE_MAX, login="plus")
        path = self.bare_path(home, "claude")
        code, out, term = on_terminal(["--dry-run"], self.env(home, path=path, homes=False),
                                      [("runtime (detected: claude) — ↑/↓", ENTER), *[(m, ENTER) for m in CLAUDE_MENUS]])
        self.assertEqual(code, 0, term)
        self.assertIn("runtime: claude (detected: claude)\n", term)
        self.same(out, self.piped(home, path=path, homes=False))
        self.assertIn("detected runtime: claude\n", out)
        code, out, term = on_terminal(["--dry-run"], self.env(home, path=path, homes=False),
                                      [("runtime (", DOWN + DOWN + ENTER), *[(m, ENTER) for m in CLAUDE_MENUS],
                                       ("codex plan (", ENTER)])
        self.assertEqual(code, 0, term)
        self.assertIn("runtime: both\n", term)
        self.assertNotIn("detected runtime:", out)
        self.assertIn("== claude: plan=max ", out)
        self.assertIn("== codex: plan=plus (Plus)", out)
        for name, args, env in (("target", ["--target", "auto"], {"homes": False}),
                                ("home", ["--home", os.path.join(home, ".claude")], {"homes": False}),
                                ("CLAUDE_DIR", [], {})):
            with self.subTest(name):
                code, _out, term = on_terminal([*args, "--dry-run"], self.env(home, path=path, **env),
                                               [(m, ENTER) for m in CLAUDE_MENUS])
                self.assertEqual(code, 0, term)
                self.assertNotIn("runtime (", term)
        code, out, term = on_terminal(["--dry-run"], self.env(home, path=self.bare_path(self.path("none")), homes=False))
        self.assertEqual(code, 1, term)
        self.assertNotIn("runtime (", term)
        self.assertIn("No supported runtime found.", term)

    def test_option_menus_and_flags(self):
        """R6: picks in the fable, context and statusline menus give the run their flags give; each flag skips
        its menu; fable is asked on max tiers only, not on pro or balanced-max; the recorded statusline is
        preselected."""
        home = self.home("options", account=CLAUDE_MAX)
        code, out, term = on_terminal(["--target", "claude", "--dry-run"], self.env(home),
                                      [("plan (", ENTER), ("fable (auto on max) — ↑/↓", DOWN + ENTER),
                                       ("context —", DOWN + ENTER), ("statusline —", DOWN + ENTER)])
        self.assertEqual(code, 0, term)
        for line in ("fable: no\n", "context: economy\n", "statusline: own\n"):
            self.assertIn(line, term)
        self.same(out, self.piped(home, "--target", "claude", "--fable", "no", "--context", "economy",
                                         "--statusline", "own"))
        for name, args, menus in (
                ("every flag", ["--plan", "max", "--fable", "yes", "--context", "default", "--statusline", "riskrails"], ()),
                ("pro", ["--plan", "pro"], ("context —", "statusline —")),
                ("balanced-max", ["--plan", "balanced-max"], ("context —", "statusline —")),
                ("fable flag", ["--plan", "max20", "--fable", "no"], ("context —", "statusline —")),
                ("context flag", ["--plan", "max", "--context", "economy"], ("fable (", "statusline —"))):
            with self.subTest(name):
                code, _out, term = on_terminal(["--target", "claude", *args, "--dry-run"], self.env(home),
                                               [(m, ENTER) for m in menus])
                self.assertEqual(code, 0, term)
                self.assertEqual([m for m in CLAUDE_MENUS if m in term], list(menus))
        recorded = self.home("statusline-recorded", account=CLAUDE_MAX)
        write(os.path.join(recorded, ".claude", "riskrails", "statusline.json"), json.dumps({"mode": "own"}))
        code, out, term = on_terminal(["--target", "claude", "--plan", "max", "--fable", "yes", "--context", "default",
                                       "--dry-run"], self.env(recorded), [("statusline (", ENTER)])
        self.assertEqual(code, 0, term)
        self.assertIn("statusline: own (recorded by the previous install)\n", term)
        self.same(out, self.piped(recorded, "--target", "claude", "--plan", "max", "--fable", "yes"))

    def test_abort_restores_terminal(self):
        """R7: Esc, Ctrl-C or q in any menu exits 130 with one line, the terminal's settings as before and the
        homes untouched — also at the last menu, after Claude's branch was rendered."""
        for name, replies in (
                ("esc at the first menu", [("plan (", ESC)]),
                ("ctrl-c at context", [("plan (", ENTER), ("fable (", ENTER), ("context —", CTRL_C)]),
                ("q at the codex plan", [*[(m, ENTER) for m in CLAUDE_MENUS], ("codex plan (", "q")])):
            with self.subTest(name):
                home = self.home("abort-" + name.split()[0], account=CLAUDE_MAX, login="plus")
                before = sorted(os.path.relpath(os.path.join(d, f), home) for d, _, fs in os.walk(home) for f in fs)
                shell = ('stty -g; "$0" "$@"; echo "exit=$?"; stty -g')
                _code, out, term = on_terminal([], self.env(home), replies,
                                               cmd=["sh", "-c", shell, *INSTALLER, "--target", "both"])
                first, code_line, last = out.splitlines()[0], out.splitlines()[-2], out.splitlines()[-1]
                self.assertEqual(code_line, "exit=130", term)
                self.assertEqual(first, last)
                self.assertIn("riskrails: aborted — nothing was written\n", term)
                after = sorted(os.path.relpath(os.path.join(d, f), home) for d, _, fs in os.walk(home) for f in fs)
                self.assertEqual(after, before)

    def test_menu_off_typed_prompt(self):
        """R8: RISKRAILS_MENU=off or 0, or TERM=dumb, asks the typed question of 4.0.1, verbatim, and only it."""
        home = self.home("off", account=CLAUDE_MAX)
        why = "detected from organizationType claude_max"
        for name, extra in (("off", {"RISKRAILS_MENU": "off"}), ("0", {"RISKRAILS_MENU": "0"}), ("dumb", {"TERM": "dumb"})):
            with self.subTest(name):
                code, out, term = on_terminal(["--target", "claude", "--dry-run"], self.env(home, **extra),
                                              [(PROPOSE % ("max", why), ENTER)])
                self.assertEqual((code, term), (0, PROPOSE % ("max", why) + "\n"))
                self.assertIn("== claude: plan=max (Max, max profile)", out)


if __name__ == "__main__":
    unittest.main()
