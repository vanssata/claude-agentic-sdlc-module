#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
ai-path-guard: fixtures plus the "no .ai/ means no guard" property.

The sections run in the shell suite's order against one project tree, and each
moves the task state file as the shell one did: test_NN_ names keep the order.
"""
import os
import shutil
import sys
import tempfile
import time
import unittest
from string import Template

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import (FIXTURES, PLUGIN, HookAsserts, bash, codex_fixtures,  # noqa: E402  pylint: disable=wrong-import-position
                           decision, fixtures, run)

TWIN_OF = "test-ai-path-guard.sh"
# `pass "$name"` is decide()'s label parameter and `pass "and within $4 ms
# (${ms} ms)"` timed()'s budget line; the labels and budgets they were called
# with are the cases below.
SHELL_MECHANICS = ("$name", "and within $4 ms (${ms} ms)")

GUARD = os.path.join(PLUGIN, "hooks", "ai-path-guard.sh")
IMPLEMENTATION = '{"current_stage":"implementation","task_id":"T-1"}\n'
CONTROL_FILE = "removal of a claude-agentic control file"
WORK_CAP = "names more paths than the guard can check"


def pad_a(n):
    return "a" * n


def words(n):
    return "".join(" w%d" % i for i in range(1, n + 1))


def tool(cwd, name, path, **extra):
    return {"hook_event_name": "PreToolUse", "tool_name": name, "cwd": cwd,
            "tool_input": dict(file_path=path, **extra)}


class TestAiPathGuard(HookAsserts, unittest.TestCase):  # pylint: disable=too-many-public-methods
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.root = root = os.path.join(cls.tmp, "project")
        for d in (".ai/state", ".ai/policies", "src", "config", "var", "migrations", ".claude/agents",
                  ".claude/rules", ".codex", "vendor/acme/pkg", "node_modules/foo", ".ai/rules", "docs/sdlc"):
            os.makedirs(os.path.join(root, d))
        for rel, text in ((".env", "SECRET=1\n"), (".env.example", "SECRET=\n"),
                          (".ai/state/current.json", "{}\n"), (".ai/policies/path-guard.json", "{}\n"),
                          ("src/Service.php", "x\n"), ("var/dump-2026-09-01.sql", "x\n"),
                          ("migrations/Version20260101.sql", "x\n"), (".claude/agents/ai-reviewer.md", "x\n"),
                          (".ai/rules/payment.md", "x\n"), (".claude/rules/payment.md", "x\n"),
                          ("docs/sdlc/constitution.md", "x\n"), ("vendor/acme/pkg/AGENTS.md", "x\n"),
                          ("vendor/acme/pkg/.cursorrules", "x\n"), ("node_modules/foo/CLAUDE.md", "x\n"),
                          ("node_modules/foo/index.js", "x\n")):
            cls.write(os.path.join(root, rel), text)
        os.symlink("../.env", os.path.join(root, "config", "link.txt"))
        cls.noai = os.path.join(cls.tmp, "no-ai-here")
        os.makedirs(cls.noai)
        cls.home_t = os.path.join(cls.tmp, "user")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    @staticmethod
    def write(path, text):
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def state(self, text):
        """The task state file: its text, or None to remove it."""
        path = os.path.join(self.root, ".ai", "state", "current.json")
        if text is None:
            if os.path.exists(path):
                os.remove(path)
        else:
            self.write(path, text)

    def out(self, payload, env=None):
        return run(GUARD, payload, env=env)[1]

    def decide(self, label, expect, payload, env=None):
        with self.subTest(label):
            out = self.out(payload, env)
            self.assertEqual(decision(out), expect, "%s: %s" % (label, out[:200]))

    def says(self, label, needle, payload, env=None):
        with self.subTest(label):
            out = self.out(payload, env)
            self.assertIn(needle, out, "%s: %s" % (label, out[:200]))

    def timed(self, label, expect, payload, max_ms):
        t0 = time.monotonic()
        self.decide(label, expect, payload)
        ms = int((time.monotonic() - t0) * 1000)
        with self.subTest("%s: within %d ms (%d ms)" % (label, max_ms, ms)):
            self.assertLess(ms, max_ms, "%s took %d ms" % (label, ms))

    def within(self, template, payload, max_ms):
        t0 = time.monotonic()
        self.out(payload)
        ms = int((time.monotonic() - t0) * 1000)
        with self.subTest(Template(template).substitute(ms=ms)):
            self.assertLess(ms, max_ms)

    def b(self, command, cwd=None):
        return bash(command, cwd or self.root)

    def env_home(self):
        """decide_home: HOME is the test home, no runtime home overrides."""
        env = {k: v for k, v in os.environ.items() if k not in ("CLAUDE_CONFIG_DIR", "CODEX_HOME")}
        env["HOME"] = self.home_t
        return env

    def decide_home(self, label, expect, command):
        self.decide(label, expect, self.b(command), env=self.env_home())

    def test_01_project_with_ai_fixtures(self):
        self.assertFixtures(GUARD, fixtures(os.path.join(FIXTURES, "path-guard"), self.root))

    def test_02_codex_payloads_apply_patch_and_shell(self):
        os.makedirs(os.path.join(self.root, ".codex", "hooks"), exist_ok=True)
        self.write(os.path.join(self.root, ".codex", "hooks", "ai-git-guard.json"), "{}\n")
        self.assertFixtures(GUARD, codex_fixtures("path", self.root))

    def test_03_malformed_input_fails_open(self):
        self.assertFailsOpen(GUARD, "empty payload is allowed", "")
        self.assertFailsOpen(GUARD, "payload that is not JSON is allowed", "not json at all")
        self.assertFailsOpen(GUARD, "apply_patch with no command is allowed",
                             {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": self.root,
                              "tool_input": {}})
        self.assertFailsOpen(GUARD, "a patch with no file headers is allowed",
                             {"hook_event_name": "PreToolUse", "tool_name": "apply_patch", "cwd": self.root,
                              "tool_input": {"command": "*** Begin Patch\n*** End Patch"}})

    def test_04_the_runtime_lock_is_tied_to_a_task(self):
        edit_agent = tool(self.root, "Edit", self.root + "/.claude/agents/ai-reviewer.md")
        self.state(IMPLEMENTATION)
        self.decide("stage=implementation: editing an agent definition is denied", "deny", edit_agent)
        self.state('{"current_stage":"done","task_id":"T-1"}\n')
        self.decide("stage=done: the same edit is allowed again", "allow", edit_agent)
        self.state(None)
        self.decide("no task at all: the same edit is allowed", "allow", edit_agent)
        self.state("not json\n")
        self.decide("a state file that does not parse counts as in flight", "deny", edit_agent)
        self.state("{}\n")

    def test_05_approval_cannot_be_granted_from_an_agent_shell(self):
        # Not a fixture: the shared root always has a state file, and the point of
        # this rule is that it is armed by the task rather than standing permanently.
        approve = self.b("python3 /home/u/.claude/skills/ai-task/state.py --root . approve --by ivan")
        self.state(None)
        self.decide("no task in flight: state.py approve is none of the guard's business", "allow", approve)
        self.state('{"current_stage":"human_approval","task_id":"T-1"}\n')
        self.decide("with a task in flight the same call is denied", "deny", approve)
        with self.subTest("AI_UNATTENDED in the hook's own environment lets a launcher through"):
            self.assertEqual(self.out(approve, dict(os.environ, AI_UNATTENDED="1")), "")
        self.says("and the deny text teaches the human what to do", "Approval happens outside the agent", approve)
        self.says("including the unattended route and what it costs", "AI_UNATTENDED=1 in the launcher", approve)

    def test_06_the_humans_verdict_past_the_review_budget(self):
        setby = "python3 /home/u/.claude/skills/ai-task/state.py --root . set review_status passed --by ivan"
        self.state(None)
        self.decide("no task in flight: set --by is none of the guard's business", "allow", self.b(setby))
        self.state(IMPLEMENTATION)
        self.decide("with a task in flight, set review_status … --by is denied like approve", "deny", self.b(setby))
        for c in [
            'python3 /h/state.py set --by ivan review_status passed',
            'python3 /h/state.py set review_status passed --by=ivan',
            'python3 /h/state.py set review_status passed --b ivan',
            'S=/h/state.py; $S set review_status passed "--by" ivan',
        ]:
            self.decide("denied: " + c, "deny", self.b(c))
        for c in [
            'python3 /home/u/.claude/skills/ai-task/state.py set review_status passed',
            'python3 /h/state.py set review_status passed && git log --by-me',
            'python3 /h/state.py get --field review_status --by-the-way',
        ]:
            self.decide("allowed: " + c, "allow", self.b(c))
        with self.subTest("AI_UNATTENDED lets a launcher give the verdict"):
            self.assertEqual(self.out(self.b(setby), dict(os.environ, AI_UNATTENDED="1")), "")
        self.says("and the deny text names the budget and the human's command", "review_rounds_max", self.b(setby))
        self.state("{}\n")

    def test_07_the_context_guard_is_the_runtimes_to_run(self):
        hookrun = self.b("python3 /home/u/.claude/hooks/context-guard.py")
        self.decide("with a task in flight, running it by hand is denied", "deny", hookrun)
        with self.subTest("and AI_UNATTENDED lets a launcher through"):
            self.assertEqual(self.out(hookrun, dict(os.environ, AI_UNATTENDED="1")), "")
        self.state(None)
        self.decide("with no task it is none of the guard's business", "allow", hookrun)
        self.state(IMPLEMENTATION)
        # Reading, diffing, linting and testing these files is the ordinary work
        # of the repository they live in, and none of it may be refused.
        with self.subTest("reading, diffing, linting and testing the hook files stays allowed"):
            for c in [
                'grep -n APPROVE_RE /home/u/.claude/hooks/context-guard.py',
                'wc -l /home/u/.claude/hooks/context-guard.py',
                'pylint /home/u/.claude/hooks/context-guard.py',
                'git diff hooks/context-guard.py',
                'bash tests/test-ai-path-guard.sh',
                'diff hooks/context-guard.py /home/u/.claude/hooks/context-guard.py',
            ]:
                self.assertEqual(self.out(self.b(c))[:160], "", "'%s' must not be refused" % c)
        with self.subTest("and a writer's name in prose or a flag is not a write"):
            for c in [
                'grep -rn touch %s/.ai/policies/path-guard.json' % self.root,
                'echo touch %s/.ai/state/current.json' % self.root,
                'git log --grep chmod -- %s/.ai/state/current.json' % self.root,
            ]:
                self.assertEqual(self.out(self.b(c))[:160], "", "'%s' names a writer word, it does not run one" % c)
        self.state("{}\n")

    def test_08_confirm_delete_is_a_humans_not_an_agents(self):
        confirm = next(p for label, _, p in fixtures(os.path.join(FIXTURES, "path-guard"), self.root)
                       if label.startswith("45-bash-update-confirm-delete.json"))
        self.state(None)
        self.decide("no task in flight: still denied, a deletion needs no task to be irreversible", "deny", confirm)
        self.state("{}\n")
        with self.subTest("AI_UNATTENDED in the hook's own environment lets a launcher through"):
            self.assertEqual(self.out(confirm, dict(os.environ, AI_UNATTENDED="1")), "")
        with self.subTest("and the deny text names the terminal outside Claude Code or Codex"):
            out = self.out(confirm)
            self.assertIn("outside Claude Code or Codex", out)
            self.assertIn("terminal", out)
        # Spellings the review found one token away from the fixtures (T-2026-09-27-003 review).
        for c in [
            'python3 -m "update" . --apply --confirm-delete x',
            "python3 -m 'update' . --apply --confirm-delete x",
            'python3 -um update . --apply --confirm-delete x',
            'python3 -Bm update . --apply --confirm-delete x',
            'python3 skills/project-update/update.py . --apply 2>&1 --confirm-delete x',
            'python3 skills/project-update/update.py . --apply &>/tmp/o --confirm-delete x',
        ]:
            self.decide("denied: " + c, "deny", self.b(c))
        self.decide("but && still ends the segment", "allow",
                    self.b("python3 update.py . --apply && echo --confirm-delete"))
        # Reading the flag, running the dry runs, and every other --co… option stay allowed.
        for c in [
            'grep -n confirm-delete /home/u/.claude/skills/project-update/update.py',
            'grep -n -- --confirm-delete /home/u/.claude/skills/project-update/update.py',
            'python3 /home/u/.claude/skills/project-update/update.py . --adopt --cleanup',
            'python3 /home/u/.claude/skills/project-update/update.py . --apply',
            'ls --color',
            'foo --config x',
            'git commit -m "adopt: gate"',
            'cd "$ROOT" && pytest --co -q',
            '"$PY" -m pytest --co',
            'pytest tests/test_update.py --co',
            'python3 tools/db_update.py --confirm',
            'sed -n 1,5p update.py | grep -- --confirm-delete',
            'git commit -m "update.py: --confirm-delete"',
        ]:
            with self.subTest(Template("allowed: $c").substitute(c=c)):
                self.assertEqual(self.out(self.b(c))[:160], "", "'%s' must not be refused" % c)

    def test_09_a_backslash_newline_does_not_split_the_gate_rules(self):
        self.state('{"current_stage":"human_approval","task_id":"T-1"}\n')
        self.decide("state.py \\⏎approve --by x is denied", "deny",
                    self.b("python3 /home/u/.claude/skills/ai-task/state.py \\\napprove --by x"))
        self.decide("python3 \\⏎context-guard.py is denied", "deny",
                    self.b("python3 \\\n/home/u/.claude/hooks/context-guard.py"))
        # Spellings the T-2026-10-15-003 reviews found past APPROVE_RE.
        for c in [
            'python3 /h/state.py --root "/Store/Claude Plugins/p" approve --by x',
            "python3 /h/state.py --root '/a b' approve --by x",
            'python3 /h/state.py "approve" --by x',
            'python3 /h/state.py -- approve --by x',
            'S=/h/state.py; ($S approve --by x)',
            'echo $($S approve --by x)',
            'echo `$S approve --by x`',
        ]:
            self.decide("denied: " + c, "deny", self.b(c))
        for c in ['grep -n approve skills/ai-task/state.py', 'python3 /h/state.py get --field human_approval']:
            self.decide("allowed: " + c, "allow", self.b(c))
        self.decide("but grep x \\⏎context-guard.py is a read, not a run", "allow",
                    self.b("grep -n APPROVE_RE \\\nhooks/context-guard.py"))
        self.state("{}\n")

    def test_10_confirm_delete_is_denied_from_a_cwd_with_no_ai(self):
        noai = self.noai
        self.decide("update.py /abs/p --apply --confirm-delete x from a cwd without .ai/ is denied", "deny",
                    self.b("python3 /home/u/.claude/skills/project-update/update.py " + self.root
                           + " --apply --confirm-delete x", noai))
        for c in ['ls -la', 'python3 /home/u/.claude/skills/project-update/update.py %s --apply' % self.root,
                  'cat README.md']:
            self.decide("still allowed without .ai/: " + c, "allow", self.b(c, noai))
        # A variable head after ; & | ( or a backtick (T-2026-10-15-003 security review).
        for c in [
            'U=/x/update.py; true;$U --apply --confirm-delete bob',
            'true&&$U --apply --confirm-delete bob',
            '($U --apply --confirm-delete bob)',
            'echo $($U --apply --confirm-delete bob)',
            'echo `$U --apply --confirm-delete bob`',
        ]:
            self.decide("denied without .ai/: " + c, "deny", self.b(c, noai))
        self.decide("and a Write there stays none of the guard's business", "allow",
                    tool(noai, "Write", noai + "/x.txt"))

    def test_11_a_padded_line_cannot_outrun_the_hook_timeout(self):
        root, tmp = self.root, self.tmp
        for unit in ("a", "a "):
            pad = (unit * 200000)[:200000]
            long_hit = self.b("python3 update.py . --apply " + pad + " --co x")
            long_miss = self.b("echo " + pad[:20000])
            t0 = time.monotonic()
            self.decide("a 200 KB line ('%s' padding) holding update and --co is denied" % unit, "deny", long_hit)
            ms = int((time.monotonic() - t0) * 1000)
            with self.subTest(Template("and within a second (${ms} ms)").substitute(ms=ms)):
                self.assertLess(ms, 1000)
            self.decide("a 20 KB line ('%s' padding) without them is allowed" % unit, "allow", long_miss)
        # The variable head needs no `update` on the long line (security review).
        var_hit = self.b("U=/x/update.py\n" + "$U --co " * 8000 + "; $U --apply --confirm-delete bob")
        t0 = time.monotonic()
        self.decide("a 64 KB line of $U --co … --apply is denied", "deny", var_hit)
        ms = int((time.monotonic() - t0) * 1000)
        with self.subTest(Template("and within a second (${ms} ms)").substitute(ms=ms)):
            self.assertLess(ms, 1000)
        # A minified line full of --color and the word update is not a confirmed deletion (review).
        css = ("cat > dist/app.min.css <<'EOF'\n"
               + "".join("function update(){}:root{--color-%d:#fff}" % i for i in range(1, 601)) + "\nEOF")
        self.decide("a 25 KB minified CSS heredoc naming update and --color is allowed", "allow",
                    self.b(css, self.noai))
        # T-2026-10-15-004 (known-risks: "The path guard is quadratic on long lines"):
        # ere_match hands a line over 4096 characters to grep, and the forking work
        # per path and per token is capped, so no padded command outruns the timeout.
        b = self.b
        names = "".join(" file%d.txt" % i for i in range(1, 3001))
        self.timed("a 40 KB echo is allowed", "allow", b("echo " + pad_a(40000)), 1000)
        self.timed("a 40 KB sh -c string is allowed", "allow", b("sh -c '%s'" % pad_a(40000)), 1000)
        self.timed("a 200 KB echo followed by cat .env is denied", "deny", b("echo %s; cat .env" % pad_a(200000)), 1000)
        self.timed("rm -f of 3000 files and a task state file is denied", "deny",
                   b("rm -f%s .ai/state/current.json" % names), 5000)
        self.within("rm -f of 3000 ordinary files is decided within 5 s (${ms} ms)", b("rm -f" + names), 5000)
        self.timed("a 200 KB argument glued to a protected path is denied", "deny",
                   b("echo %s/.ai/state/current.json" % pad_a(200000)), 1000)
        self.timed("a 200 KB argument beside a frozen path, with no task, is allowed", "allow",
                   b("echo %s .claude/settings.json" % pad_a(200000)), 1000)
        self.state(None)
        cap = b("ls" + "".join(" .claude/agents/x%d.md" % i for i in range(1, 301)))
        self.decide("ls of 300 frozen paths is denied by the work cap", "deny", cap)
        self.says("and the deny says why", WORK_CAP, cap)
        # Prose is not counted (STRONG review): only tokens that hit the pre-filter.
        self.timed("a 300-word heredoc that mentions .env.example is allowed", "allow",
                   b("cat > docs/setup.md <<'EOF'\ncopy .env.example first.%s\nEOF" % words(300)), 3000)
        self.timed("a 300-word commit message that mentions .env.example is allowed", "allow",
                   b('git commit -m "copy .env.example%s"' % words(300)), 3000)
        # A padded mover operand (STRONG review BLOCKER: the operand grep was quadratic in UTF-8).
        self.timed("rm -f of a 200 KB operand and the task state file is denied", "deny",
                   b("rm -f %s/.ai/state/x.json .ai/state/current.json" % pad_a(200000)), 2000)
        # A deny reason over 128 KB still denies (review HIGH: jq --arg could not exec).
        self.timed("cp of a 140 KB-named file and another into .ai/state/ is denied", "deny",
                   b("cp %s.json x.json .ai/state/" % pad_a(140000)), 3000)
        # A long glob collapses to a short path (review HIGH).
        self.decide("a redirect into a 4200-character glob for current.json is denied", "deny",
                    b("echo hi > [%s]urrent.json; echo .env.example" % ("c" * 4200), root + "/.ai/state"))
        # One operand that does not resolve must not unresolve the rest (review HIGH).
        lnk = os.path.join(root, "lnk")
        os.makedirs(lnk, exist_ok=True)
        os.symlink(root + "/.ai/state", lnk + "/st")
        os.symlink("loopB", lnk + "/loopA")
        os.symlink("loopA", lnk + "/loopB")
        self.decide("mv into a symlinked state directory beside a symlink loop is denied", "deny",
                    b("mv current.json loopA/x .env.example st/", lnk))
        # Work nobody counts is on the clock too (re-review BLOCKER: 25000 plain operands, 14 s).
        many = "".join(" /f%d" % i for i in range(1, 25001))
        self.timed("mv of 25000 sources and the task state file is denied", "deny",
                   b("mv%s .ai/state/current.json /d" % many), 8000)
        self.within("mv of 25000 plain sources is decided within 8 s (${ms} ms)", b("mv%s /d" % many), 8000)
        # Inside every count the work is still bounded by the clock (review HIGH: 11.4 s).
        wc = os.path.join(tmp, "worst")
        os.makedirs(wc + "/.ai/policies")
        for i in range(1, 17):
            os.makedirs("%s/d%d/.claude/agents" % (wc, i))
            for j in range(1, 51):
                self.write("%s/d%d/.claude/agents/a%d.md" % (wc, i, j), "")
        worst = ("rm -f" + "".join(" .claude/agents/x%d.md" % i for i in range(1, 64))
                 + "; rm -rf" + "".join(" d%d" % i for i in range(1, 17)) + "; rm -f .ai/policies/path-guard.json")
        self.timed("63 frozen operands, 16 full directory scans and a policy file are denied", "deny",
                   b(worst, wc), 8000)
        self.timed("cat .env.example and 60 more tokens is allowed (the cap does not reach normal lines)", "allow",
                   b("cat .env.example" + words(60)), 3000)
        # The movers caps: 64 operands that need classify, 16 directory scans.
        frozen = lambda n: "".join(" .claude/agents/x%d.md" % i for i in range(1, n + 1))  # noqa: E731
        self.state(None)
        self.decide("rm -f of 30 frozen paths with no task is allowed", "allow", b("rm -f" + frozen(30)))
        self.says("rm -f of 70 frozen paths is denied by the work cap", WORK_CAP, b("rm -f" + frozen(70)))
        for i in range(1, 21):
            os.makedirs("%s/scan/d%d" % (tmp, i))
        dirs = lambda n: "".join(" %s/scan/d%d" % (tmp, i) for i in range(1, n + 1))  # noqa: E731
        self.decide("rm -rf of 16 directories is allowed", "allow", b("rm -rf" + dirs(16)))
        self.decide("rm -rf of 17 directories is denied by the work cap", "deny", b("rm -rf" + dirs(17)))
        # T-2026-10-20-001 (known-risks: padded sh -c segments): segments_of re-reads
        # at most 64 sh -c / eval strings, and every segment loop is on the clock.
        self.timed("6000 sh -c segments and rm of the task state file are denied", "deny",
                   b("sh -c x; " * 6000 + "rm -f .ai/state/current.json"), 2000)
        self.timed("6000 eval segments and rm of the task state file are denied", "deny",
                   b("eval x; " * 6000 + "rm -f .ai/state/current.json"), 2000)
        self.decide("64 sh -c segments and rm -f a.txt are allowed", "allow", b("sh -c x; " * 64 + "rm -f a.txt"))
        self.says("65 sh -c segments and rm -f a.txt are denied by the work cap", WORK_CAP,
                  b("sh -c x; " * 65 + "rm -f a.txt"))
        self.says("the 64th sh -c string is still read: its rm of the state file is denied", CONTROL_FILE,
                  b("sh -c x; " * 63 + "sh -c 'rm -f .ai/state/current.json'"))
        self.timed("100000 one-word segments and rm -f a.txt are allowed", "allow",
                   b("x;" * 100000 + "rm -f a.txt"), 3000)
        self.timed("100000 one-word segments and rm of the task state file are denied", "deny",
                   b("x;" * 100000 + "rm -f .ai/state/current.json"), 3000)
        # T-2026-10-21-001 (known-risks: many mover segments reach the 6 s clock): the
        # movers pass checks its segments in batches, one realpath and one loose_hits
        # per 32 KB of candidates, not one per segment, and every decision keeps its
        # reason and its place.
        self.timed("1000 rm segments and rm -f a.txt are allowed", "allow", b("rm x; " * 1000 + "rm -f a.txt"), 2000)
        pl = b("rm x; " * 1000 + "rm -f .ai/state/current.json")
        self.timed("1000 rm segments and rm of the task state file are denied", "deny", pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        globop = pad_a(4097) + "*"
        self.says("a control-file deny comes before a later segment's long glob operand deny", CONTROL_FILE,
                  b("rm -f .ai/state/current.json; rm -f " + globop))
        self.says("a long glob operand deny comes before a later segment's control-file deny",
                  "operand that holds a glob or expansion character",
                  b("rm -f %s; rm -f .ai/state/current.json" % globop))
        self.says("a later segment's mv destination is still a copy or move into, not a move of",
                  "copy or move into a claude-agentic control file", b("rm x; mv a.txt .ai/state/current.json"))
        for c in ("mv loopA/x y; mv current.json .env.example st/", "mv current.json .env.example st/; mv loopA/x y"):
            self.says(Template("$c: a symlink loop in one segment does not hide a symlinked state directory in "
                               "another").substitute(c=c), "claude-agentic control file", b(c, lnk))
        # Its STRONG review: one realpath for the whole line was a unit the clock could
        # not stop (400 segments of a symlink chain ran past 20 s; HEAD denied by the
        # clock in 5.1 s), and an early segment's deny waited for the whole line (HEAD
        # 0.2 s with the control-file reason, then 5.8 s with the work cap's).
        os.makedirs(root + "/chain", exist_ok=True)
        os.symlink(".", root + "/chain/c")
        chain = "chain/" + "c/" * 2000 + "x"
        self.timed("400 rm segments of a 4 KB symlink chain and rm of the task state file are denied", "deny",
                   b(("rm %s; " % chain) * 400 + "rm -f .ai/state/current.json"), 8000)
        pl = b("rm -f .ai/state/current.json; " + "rm x; " * 20000 + "rm y")
        self.timed("rm of the task state file before 20000 rm segments is denied", "deny", pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        # Its re-review: a batch was checked only when its candidates filled 32 KB, so
        # segments that add none (`rm -f;`) or one behind thousands of options left an
        # early deny waiting for the end of the line (HEAD 1.1 s with the control-file
        # reason, then 5 s with the work cap's). One segment past ARG_MAX, which HEAD
        # denied by the work cap once its realpath failed with E2BIG, is checked
        # candidate by candidate now: allowed when none of them is protected.
        pl = b("rm -f .ai/state/current.json; " + "rm -f; " * 150000 + "rm y")
        self.timed("rm of the task state file before 150000 rm segments with no operand is denied", "deny", pl, 3000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        pl = b("rm -f .ai/state/current.json; " + ("rm %sy; " % ("-f " * 2000)) * 200)
        self.timed("rm of the task state file before 200 rm segments of 2000 options is denied", "deny", pl, 3000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        deep = root + "/" + (pad_a(200) + "/") * 8
        os.makedirs(deep)
        self.decide("rm of 1500 files under a 1600-character cwd is allowed: past ARG_MAX, every candidate is checked",
                    "allow", b("rm" + words(1500), deep.rstrip("/")))
        # Its second re-review: a later segment slow to parse still held an early deny.
        # Stripping quotes one character at a time cost 0.27 s per 4 KB operand of
        # `""`: the state file before one 123 KB segment of 30 such operands was denied
        # by HEAD in 0.29 s with the control-file reason, by R2 in 6.0 s with the work
        # cap's. The strip is linear now, and a segment that would take the batch's text
        # past 32 KB is parsed only after the batch is checked.
        qop = "a" + '""' * 2047
        pl = b("rm -f .ai/state/current.json; rm" + (" " + qop) * 30)
        self.timed("rm of the task state file before a 123 KB segment of quote-padded operands is denied", "deny",
                   pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        pl = b(("rm %s; " % qop) * 16 + "rm -f .ai/state/current.json; " + ("rm %s; " % qop) * 8)
        self.timed("rm of the task state file among 24 quote-padded rm segments is denied", "deny", pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        self.decide("rm of the task state file inside runs of both quote kinds is denied", "deny",
                    b("rm \"'\".ai/state/current.json\"'\""))
        self.decide("cp -t into the state directory inside runs of both quote kinds is denied", "deny",
                    b("cp -t \"'\".ai/state\"'\" current.json"))
        self.decide("an operand of quotes only names no file", "allow", b("rm '\"\"' a.txt"))
        # Its third re-review: the batch was bounded by text, not by the absolute paths
        # a segment's candidates make. Under a 3.3 KB cwd one later `rm` of 5000 short
        # operands (29 KB of text) made 16 MB of them, built and resolved before the
        # earlier deny was checked (HEAD 0.11 s with the control-file reason, R3 5.6 s
        # with the work cap's). A destination multiplies every source the same way.
        deep2 = root + "/" + (pad_a(200) + "/") * 16
        os.makedirs(deep2)
        pl = b("rm -f %s/.ai/state/current.json; rm%s" % (root, words(5000)), deep2.rstrip("/"))
        self.timed("rm of the task state file before an rm of 5000 operands under a 3.3 KB cwd is denied", "deny",
                   pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)
        pl = b("rm -f .ai/state/current.json; mv" + words(3000) + " d/" + pad_a(4000))
        self.timed("rm of the task state file before an mv of 3000 sources into a 4 KB destination is denied",
                   "deny", pl, 2000)
        self.says("and the deny names the control file, not the work cap", CONTROL_FILE, pl)

    def test_12_sh_c_through_blanks_and_spellings(self):
        b = self.b
        # T-2026-10-20-002 (known-risks: the candidate filter and its regex ran in two
        # locales): both are bytewise, and the regex names the UTF-8 bytes of the 15
        # multibyte characters glibc's [[:space:]] matches, so a line that splits
        # /bin/sh, -c and the string on one of them through IFS is read in any locale.
        def sh_ifs(u, target):
            return "set -- '/bin/sh%s-c%srm -f %s'; IFS='%s'; $1" % (u, u, target, u)
        for cp in ("1680", "2000", "2001", "2002", "2003", "2004", "2005", "2006", "2008", "2009", "200A",
                   "2028", "2029", "205F", "3000"):
            u = chr(int(cp, 16))
            self.decide("IFS=U+%s running /bin/sh -c 'rm of the task state file' is denied" % cp, "deny",
                        b(sh_ifs(u, ".ai/state/current.json")))
            self.decide("echo of /bin/sh -c 'rm of the task state file' with U+%s blanks is denied" % cp, "deny",
                        b("echo /bin/sh%s-c%s'rm -f .ai/state/current.json'" % (u, u)))
            self.decide("IFS=U+%s running /bin/sh -c 'rm -f a.txt' is allowed" % cp, "allow", b(sh_ifs(u, "a.txt")))
        self.decide("under LC_ALL=C, IFS=U+3000 running /bin/sh -c 'rm of the task state file' is denied", "deny",
                    b(sh_ifs("　", ".ai/state/current.json")), env=dict(os.environ, LC_ALL="C"))
        # U+2007 is not in that set: like IFS=, it stays out of reach (known-risks).
        self.decide("IFS=U+2007 is not a blank: its /bin/sh -c split is allowed, as before", "allow",
                    b(sh_ifs(" ", ".ai/state/current.json")))
        # T-2026-10-20-003 (known-risks: sh -c spellings segments_of does not read): a
        # long option, -o/-O and its name, --, -, -e or a redirection beside -c, and a
        # quoted or backslashed command word all still run the string.
        for p in [
            'bash --norc -c', 'bash -o posix -c', 'bash +o posix -c', 'bash -O extglob -c',
            'bash -eo pipefail -c', 'bash --rcfile /dev/null -c', 'sh -c --', 'sh -c -', 'sh -c -e',
            'sh -c 2>/dev/null', 'sh -c 2> /dev/null', 'sh -c >/dev/null 2>&1', 'sh -c &>/dev/null',
            'sh </dev/null -c', "'sh' -c", '"bash" -c', '\\sh -c', "'/bin/sh' -c",
        ]:
            self.decide("%s 'rm of the task state file' is denied" % p, "deny",
                        b("%s 'rm -f .ai/state/current.json'" % p))
        for p in ['bash --norc -c', 'bash -o posix -c', 'sh -c --', 'sh -c 2>/dev/null', "'sh' -c", '\\sh -c']:
            self.decide("%s 'rm -f a.txt' is allowed" % p, "allow", b("%s 'rm -f a.txt'" % p))
        self.decide("sh -c 'x' 2>/dev/null is allowed", "allow", b("sh -c 'x' 2>/dev/null"))
        self.decide("sh -c echo -n hi is allowed", "allow", b("sh -c echo -n hi"))
        # Its review: a name after -c, a target of quoted and bare pieces, and a match
        # that begins at an argument (-exec is a cluster with a c) all still deny.
        for p in [
            'bash -c -o posix', 'bash -c +O extglob', 'bash -c -eo pipefail', 'bash -c -e -o pipefail',
            'bash -c 2>/dev/null -o posix', 'sh -c 2>"$HOME"/x', 'sh -c 2>/tmp/x\\ y',
            "find . -name 'sh' -exec sh -c", 'find . -name sh 2>/dev/null -exec sh -c',
            "find . -path '*/sh' -exec bash -c", "sudo -u 'sh' -c x bash -c",
        ]:
            self.decide("%s 'rm of the task state file' is denied" % p, "deny",
                        b("%s 'rm -f .ai/state/current.json'" % p))
        self.decide("a bash -c inside a sh -c string, rm of the task state file, is denied", "deny",
                    b("sh -c 'echo; bash -c \"rm -f .ai/state/current.json\"'"))
        self.decide("bash -c -o posix 'rm -f a.txt' is allowed", "allow", b("bash -c -o posix 'rm -f a.txt'"))
        self.decide("find -name 'sh' -exec sh -c 'rm -f a.txt' is allowed", "allow",
                    b("find . -name 'sh' -exec sh -c 'rm -f a.txt' \\;"))
        self.timed("200 KB of ' sh 2>' words and rm of the task state file are denied", "deny",
                   b("echo" + " sh 2>" * 33333 + " X sh -c x; rm -f .ai/state/current.json"), 2000)
        # Its second pass: a flag that takes no word is not counted before -c, as on
        # HEAD; a word stops at a multibyte blank, not only at an ASCII one, and keeps
        # the other characters whose first byte a multibyte blank shares.
        for p in [
            'bash ' + '-e ' * 9 + '-c', 'bash -e -u -x -v -e -u -x -v -e -c', 'sh -a -b -e -f -h -m -u -v -x -c',
            'bash ' + '-e ' * 20 + '-c', 'bash -o posix ' + '-e ' * 9 + '-O extglob -c',
            'bash 2>/tmp/…あ→ᚁx -c',
        ]:
            self.decide("%s 'rm of the task state file' is denied" % p, "deny",
                        b("%s 'rm -f .ai/state/current.json'" % p))
        self.decide("bash with 9 -e before -c and 'rm -f a.txt' is allowed", "allow",
                    b("bash %s-c 'rm -f a.txt'" % ("-e " * 9)))
        u = "　"
        self.timed("140 KB of U+3000 ' sh -o x' words and rm of the task state file are denied", "deny",
                   b("echo" + (u + "sh" + u + "-o" + u + "x") * 10000 + " X sh -c x; rm -f .ai/state/current.json"),
                   2000)
        self.timed("140 KB of U+3000 ' sh 2>x' words and rm -f a.txt are allowed", "allow",
                   b("echo" + (u + "sh" + u + "2>x") * 13000 + " X sh -c x; rm -f a.txt"), 2000)
        # Its fourth pass: a quoted piece holds no blank. With one, ` sh 2>\''` (\' is
        # escaped outside a quote, closes '…', is literal in "…") kept every start's
        # target quoted to the end of the line: 11.4 s at 200 KB. A quoted target with
        # a blank is therefore not read, as on HEAD (known-risks).
        self.timed("200 KB of ' sh 2>' words each followed by \\'' and rm of the task state file are denied", "deny",
                   b("echo" + " sh 2>\\''" * 22000 + " X sh -c x; rm -f .ai/state/current.json"), 2000)
        self.timed("140 KB of the same with U+3000 blanks and rm -f a.txt are allowed", "allow",
                   b("echo" + (u + "sh" + u + "2>\\''") * 11000 + " X sh -c x; rm -f a.txt"), 2000)
        self.decide("bash 2>'/tmp/a b' -c 'rm of the task state file' is allowed, as on HEAD", "allow",
                    b("bash 2>'/tmp/a b' -c 'rm -f .ai/state/current.json'"))

    def test_13_the_installed_shared_tree_is_frozen_during_a_task(self):
        # T-2026-10-13-004, Q4=A: <home>/claude-agentic/ai/ and ai-path are the rules a
        # run is judged by, like the policies they replace. The installed tree is
        # anchored to the runtime's home (direct-mode-diet D4b): the guard is given
        # the test home as its own, and every expectation stands.
        env = dict(os.environ, HOME=self.home_t, CLAUDE_CONFIG_DIR="", CODEX_HOME="")
        root, tmp = self.root, self.tmp
        for home in (".claude", ".codex"):
            sh = "%s/%s/claude-agentic" % (self.home_t, home)

            def t(label, expect, payload, home=home):
                self.decide("%s %s" % (home, label), expect, payload, env=env)

            def bc(command):
                return self.b(command)
            self.state(IMPLEMENTATION)
            t("in a task: Write to the shared tree is denied", "deny", tool(root, "Write", sh + "/ai/policies/git.md"))
            t("in a task: Edit of the shared tree is denied", "deny", tool(root, "Edit", sh + "/ai/policies/git.md"))
            t("in a task: Write to ai-path is denied", "deny", tool(root, "Write", sh + "/ai-path"))
            t("in a task: Read of the shared tree is allowed", "allow", tool(root, "Read", sh + "/ai/policies/git.md"))
            t("in a task: running ai-path is allowed", "allow", bc(sh + "/ai-path policies/git.md"))
            t("in a task: a sibling file is not frozen by this rule", "allow", tool(root, "Write", sh + "/ai-path.notes"))
            # T-2026-10-15-001 (known-risks a): the whole tree, replaced or removed in
            # one shell command, with nothing inside ai/ named on the line.
            t("in a task: rm -rf of the bare shared tree is denied", "deny", bc("rm -rf %s/ai" % sh))
            t("in a task: the same rm followed by && is denied", "deny", bc("rm -rf %s/ai && echo done" % sh))
            t("in a task: and with no space before the && (review: patsub_replacement ate the &)", "deny",
              bc("rm -rf %s/ai&& echo done" % sh))
            t("in a task: and with a redirect glued to the path", "deny", bc("rm -rf %s/ai>/dev/null" % sh))
            t("in a task: mv over the bare shared tree is denied", "deny", bc("mv %s/new %s/ai" % (tmp, sh)))
            t("in a task: cp -r of a directory named ai into the home is denied", "deny",
              bc("cp -r %s/new/ai %s/" % (tmp, sh)))
            t("in a task: install into the shared tree is denied", "deny",
              bc("install -m 644 %s/x %s/ai/policies/git.md" % (tmp, sh)))
            t("in a task: cp to a sibling that merely starts with ai is allowed", "allow",
              bc("cp %s/x %s/ai-notes" % (tmp, sh)))
            self.state(None)
            t("no task: Write to the shared tree is allowed", "allow", tool(root, "Write", sh + "/ai/policies/git.md"))
            t("no task: Write to ai-path is allowed", "allow", tool(root, "Write", sh + "/ai-path"))
            t("no task: rm -rf of the shared tree is the guard's business only in a task", "allow",
              bc("rm -rf %s/ai" % sh))
        self.state("{}\n")

    def test_14_ai_agents_is_an_override_path(self):
        # T-2026-10-15-001 (known-risks b): a project copy under .ai/agents/ shadows the
        # shared contract, so dropping one mid-task rewrites the reviewer's own rules.
        def agent_override(name):
            return tool(self.root, name, self.root + "/.ai/agents/reviewer.md")
        self.state(IMPLEMENTATION)
        self.decide("in a task: Write to .ai/agents/ is denied", "deny", agent_override("Write"))
        self.decide("in a task: Read of .ai/agents/ is allowed", "allow", agent_override("Read"))
        self.state(None)
        self.decide("no task: Write to .ai/agents/ is allowed", "allow", agent_override("Write"))
        self.state("{}\n")

    def test_15_parent_directories_and_segmentation(self):
        # T-2026-10-15-002: a directory above a protected file is the file, for a removal
        # or a move; protected files count always, the frozen runtime only in a task.
        root, home_t = self.root, self.home_t
        self.write(root + "/.ai/state/session.json", "{}\n")
        os.makedirs(home_t + "/.claude/hooks", exist_ok=True)
        os.makedirs(home_t + "/.claude/claude-agentic/ai/policies", exist_ok=True)
        self.write(home_t + "/.claude/hooks/ai-path-guard.sh", "x\n")
        self.write(home_t + "/.claude/claude-agentic/ai/policies/git.md", "x\n")
        dh = self.decide_home
        self.state(IMPLEMENTATION)
        dh("in a task: rm -rf ~/.claude/claude-agentic/ is denied", "deny", 'rm -rf ~/.claude/claude-agentic/')
        dh("in a task: rm -rf $HOME/.claude/claude-agentic is denied", "deny", 'rm -rf $HOME/.claude/claude-agentic')
        dh("in a task: rm -rf ${HOME}/.claude is denied", "deny", 'rm -rf ${HOME}/.claude')
        dh("in a task: rm -rf of a path with ./ and // in it is denied", "deny", 'rm -rf ~/.claude/./claude-agentic//ai')
        dh("in a task: cp f.txt ~/ stays allowed", "allow", 'cp f.txt ~/')
        # The STRONG review of T-2026-10-15-002: each of these was denied before the
        # segmentation and must stay denied — a here-string or an arithmetic << is no
        # heredoc, and a shell's -c string runs wherever the shell sits in the segment.
        for c in [
            'read -r a b <<< "$x"\nrm -f .ai/state/current.json',
            'grep foo <<<bar\nrm -f .ai/state/current.json',
            'read -r a <<< "$x"\nmv src/a.txt .claude/settings.json',
            'read -r a <<< "$x"\nchmod 000 .ai/state/current.json',
            'echo $((1<<2))\nrm -f .ai/state/current.json',
            '(( x <<= 1 ))\nrm -f .ai/state/current.json',
            "/bin/sh -c 'cd /tmp; rm -f .ai/state/current.json'",
            "xargs sh -c 'true; rm -f .ai/state/current.json'",
            "find . -exec sh -c 'true; rm -f .ai/state/current.json' \\;",
            "nice -n 5 bash -c 'true; rm -f .ai/state/current.json'",
            "timeout 5 sh -c 'x; rm -f .ai/state/current.json'",
            "bash -c $'true; rm -f .ai/state/current.json'",
        ]:
            dh("in a task: still denied: " + c.replace("\n", "⏎"), "deny", c)
        with self.subTest("in a task: the deny names the file found under the directory"):
            out = self.out(self.b("rm -rf .ai/state"))
            self.assertRegex(out, r"current\.json|session\.json")
        self.state(None)
        dh("no task: rm -rf .ai/state/ is still denied, it holds a control file", "deny", 'rm -rf .ai/state/')
        dh("no task: { rm -f .ai/state/session.json; } is denied", "deny", '{ rm -f .ai/state/session.json; }')
        dh("no task: rm -rf ~/.claude is denied, it holds the guard's own hooks", "deny", 'rm -rf ~/.claude')
        dh("no task: rm -rf .claude is allowed, the runtime is frozen only in a task", "allow", 'rm -rf .claude')
        dh("no task: mv .claude /tmp/x is allowed", "allow", 'mv .claude /tmp/x')
        dh("no task: rm -rf ~/.claude/claude-agentic/ is allowed", "allow", 'rm -rf ~/.claude/claude-agentic/')
        dh("no task: rm -rf vendor node_modules is allowed", "allow", 'rm -rf vendor node_modules')
        os.remove(root + "/.ai/state/session.json")
        self.state("{}\n")

    def test_16_reads_and_roots(self):
        # §4a: a one-liner that names .ai/state/ or .ai/reports/ is denied only when the
        # command also shows a write indicator; an eval keeps the old rule. The state
        # file is {} here, so a task is in flight throughout this section.
        root, tmp, dh = self.root, self.tmp, self.decide_home
        os.makedirs(root + "/.ai/reports/T-1", exist_ok=True)
        for c in [
            'python3 -c "import json; print(json.load(open(\'.ai/state/current.json\'))[\'current_stage\'])"',
            'python3 -c "print(open(\'.ai/reports/T-1/events.jsonl\', \'r\').read().count(\'gate\'))"',
            'python3 -c "import pathlib; print(pathlib.Path(\'.ai/state/current.json\').read_text())"',
            'python3 -c "import json; print(json.dumps(json.load(open(\'.ai/state/current.json\')), indent=2))" | head -20',
            'perl -e \'open(my $f, "<", ".ai/state/current.json"); print <$f>\'',
            'node -e "console.log(require(\'fs\').readFileSync(\'.ai/state/current.json\', \'utf8\'))"',
            'ruby -e \'puts File.read(".ai/state/current.json")\'',
        ]:
            dh("a read-only one-liner is allowed: " + c, "allow", c)
        for c in [
            'python3 -c "open(\'.ai/state/current.json\', \'w\').write(\'{}\')"',
            'python3 -c "open(\'.ai/reports/T-1/notes.md\', mode=\'a\').write(\'x\')"',
            'python3 -c "import pathlib; pathlib.Path(\'.ai/state/x.json\').open(\'w\').write(\'{}\')"',
            'python3 -c "open(\\".ai/state/x.json\\", \\"wb\\")"',
            'python3 -c "import os; os.open(\'.ai/state/x.json\', os.O_WRONLY | os.O_CREAT)"',
            'python3 -c "import pathlib; pathlib.Path(\'.ai/state/x.json\').write_text(\'{}\')"',
            'python3 -c "import pathlib; pathlib.Path(\'.ai/state/x.json\').write_bytes(b\'{}\')"',
            'python3 -c "import json; m=\'w\'; json.dump({}, open(\'.ai/state/x.json\', m))"',
            'python3 -c "import os; os.replace(\'/tmp/x\', \'.ai/state/current.json\')"',
            'python3 -c "import os; os.remove(\'.ai/state/current.json\')"',
            'python3 -c "import shutil; shutil.copy(\'/tmp/x\', \'.ai/state/current.json\')"',
            'python3 -c "import os; os.truncate(\'.ai/state/current.json\', 0)"',
            'python3 -c "import pathlib; pathlib.Path(\'.ai/state/x.json\').touch()"',
            'python3 -c "import os; os.unlink(\'.ai/state/current.json\')"',
            'python3 -c "import os; os.rename(\'/tmp/x\', \'.ai/state/current.json\')"',
            'python3 -c "import os; os.symlink(\'/tmp/x\', \'.ai/state/current.json\')"',
            'python3 -c "import subprocess; subprocess.run([\'rm\', \'.ai/state/current.json\'])"',
            'python3 -c "import os; os.system(\'rm .ai/state/current.json\')"',
            'perl -e \'open(my $f, ">", ".ai/state/current.json")\'',
            'perl -e \'open(F, ">>.ai/reports/T-1/events.jsonl")\'',
            'perl -e \'open(F, "+<", ".ai/state/current.json")\'',
            'perl -e \'system("rm", ".ai/state/current.json")\'',
            "perl -e '`rm .ai/state/current.json`'",
            'ruby -e \'File.write(".ai/state/current.json", "{}")\'',
            'ruby -e \'File.delete(".ai/state/current.json")\'',
            'ruby -e \'IO.write(".ai/state/current.json", "{}")\'',
            'ruby -e \'require "fileutils"; FileUtils.rm(".ai/state/current.json")\'',
            'node -e "require(\'fs\').writeFileSync(\'.ai/state/current.json\', \'{}\')"',
            'node -e "const fs = require(\'fs\'); fs.appendFileSync(\'.ai/reports/T-1/events.jsonl\', \'x\')"',
            'node -e "const fs = require(\'fs\'); fs.rmSync(\'.ai/state/current.json\')"',
            'node -e "const fs = require(\'fs\'); fs.copyFileSync(\'/tmp/x\', \'.ai/state/current.json\')"',
            'node -e "const fs = require(\'fs\'); fs.mkdirSync(\'.ai/reports/T-9\')"',
            'node -e "require(\'child_process\').execSync(\'rm .ai/state/current.json\')"',
            'python3 -c \'print(1)\'; php -r \'file_put_contents(".ai/state/current.json", "{}");\'',
            'python3 -c \'print(1)\'; php -r \'copy("/tmp/x", ".ai/state/current.json");\'',
            'python3 -c \'print("{}")\' > .ai/reports/T-1/notes.md',
            'python3 -c \'print("{}")\' >> .ai/reports/T-1/notes.md',
            'python3 -c \'print("{}")\' | tee -a .ai/reports/T-1/notes.md',
            'eval "cat .ai/state/current.json"',
        ]:
            dh("a writing one-liner is denied: " + c, "deny", c)
        # The indicator regex runs in-process up to 4096 characters (ere_match): a
        # padded line of open( calls is the slow case for its [^)]* pieces.
        for unit in ("open(", "a"):
            pad = unit * (4000 // len(unit))
            self.timed("a 4 KB one-liner padded with '%s' that reads the state is allowed" % unit, "allow",
                       self.b("python3 -c \"print(open('.ai/state/current.json').read())\" # " + pad), 500)

        # §4b: the protected and task patterns are anchored to the project root and to
        # the runtime homes. The same basenames are denied under the root and allowed in
        # a tree outside it, in the plugin's templates and in a fixture tree.
        scratch = tmp + "/scratch"
        os.makedirs(scratch + "/.ai/state")
        os.makedirs(scratch + "/.ai/policies")
        self.write(scratch + "/.ai/state/current.json", "{}\n")
        self.write(scratch + "/.ai/policies/path-guard.json", "{}\n")

        def write_at(path, cwd=root):
            return tool(cwd, "Write", path, content="{}")
        for rel in [
            '.ai/state/current.json', '.ai/state/handoff.md', '.ai/reports/T-1/questions.md',
            '.ai/reports/T-1/events.jsonl', '.ai/policies/path-guard.json', '.ai/policies/risk-tiers.json',
            '.ai/workflows/t3.md', '.ai/AGENTS.md', '.claude/settings.json', '.claude/agents/x.md',
            '.claude/hooks/ai-x.sh', '.codex/config.toml', '.codex/hooks/ai-x.sh', 'docs/sdlc/constitution.md',
            '.github/copilot-instructions.md', '.junie/guidelines.md', '.cursor/rules/x.mdc', '.cursorrules',
        ]:
            self.decide("in a task: Write to %s under the root is denied" % rel, "deny", write_at(root + "/" + rel))
            self.decide("in a task: Write to %s in a tree outside the root is allowed" % rel, "allow",
                        write_at(scratch + "/" + rel))
            self.decide("in a task: Write to %s under the ai-init templates is allowed" % rel, "allow",
                        write_at(root + "/skills/ai-init/templates/" + rel))
            self.decide("in a task: Write to %s under a fixture tree is allowed" % rel, "allow",
                        write_at(root + "/tests/fixtures/adopt/x/" + rel))
        self.decide("Write through src/.. to the root's policy file is denied", "deny",
                    write_at(root + "/src/../.ai/policies/risk-tiers.json"))
        self.decide("Write through //./ to the root's state file is denied", "deny",
                    write_at(root + "//.ai/./state/current.json"))
        self.decide("Write through ../ out of the root is allowed", "allow",
                    write_at(root + "/../scratch/.ai/policies/path-guard.json"))
        rootlink = tmp + "/rootlink"
        os.symlink(root, rootlink)
        self.decide("Write by the physical path while the cwd is a link to the root is denied", "deny",
                    tool(rootlink, "Write", root + "/.ai/policies/path-guard.json"))
        self.decide("Write of a new state file through a link to the root is denied", "deny",
                    write_at(rootlink + "/.ai/state/session-new.json"))
        self.decide("Edit from cwd=src of the root's policy file is denied", "deny",
                    tool(root + "/src", "Edit", root + "/.ai/policies/path-guard.json"))
        dh("cat of a policy file outside the root is allowed", "allow", "cat %s/.ai/policies/path-guard.json" % scratch)
        dh("cat of the root's policy file is still denied", "deny", 'cat .ai/policies/path-guard.json')
        dh("cp into a state file outside the root is allowed", "allow", "cp /tmp/x %s/.ai/state/current.json" % scratch)
        dh("a redirect into a state file outside the root is allowed", "allow",
           "echo '{}' > %s/.ai/state/current.json" % scratch)
        dh("rm -rf of a .ai/ tree outside the root is allowed", "allow", "rm -rf %s/.ai" % scratch)
        dh("a redirect through src/.. into the root's policy file is denied", "deny",
           'echo x > src/../.ai/policies/path-guard.json')
        dh("cp through src/.. onto the root's policy file is denied", "deny",
           'cp /tmp/x src/../.ai/policies/risk-tiers.json')
        dh("rm -rf .ai/state is still denied", "deny", 'rm -rf .ai/state')
        # The home trees: ~/.claude/hooks/ai-* and the shared tree, by every spelling.
        home_t = self.home_t

        def write_home(label, config_dir, expect, path):
            env = dict(os.environ, HOME=home_t, CLAUDE_CONFIG_DIR=config_dir, CODEX_HOME="")
            self.decide(label, expect, write_at(path), env=env)
        write_home("Write to ~/.claude/hooks/ai-* is denied", "", "deny", home_t + "/.claude/hooks/ai-path-guard.sh")
        write_home("Write to ~/.codex/hooks/ai-* is denied", "", "deny", home_t + "/.codex/hooks/ai-git-guard.sh")
        write_home("in a task: Write to ~/.claude/settings.json is denied", "", "deny", home_t + "/.claude/settings.json")
        write_home("in a task: Write to ~/.claude/claude-agentic/ai/ is denied", "", "deny",
                   home_t + "/.claude/claude-agentic/ai/policies/git.md")
        write_home("Write to $CLAUDE_CONFIG_DIR/hooks/ai-* is denied", tmp + "/cfg", "deny",
                   tmp + "/cfg/hooks/ai-path-guard.sh")
        write_home("in a task: Write to $CLAUDE_CONFIG_DIR/settings.json is denied", tmp + "/cfg", "deny",
                   tmp + "/cfg/settings.json")
        write_home("Write to hooks/ai-* of a .claude/ that is no runtime home is allowed", "", "allow",
                   scratch + "/.claude/hooks/ai-x.sh")
        dh("rm ~/.claude/hooks/ai-x is denied", "deny", 'rm ~/.claude/hooks/ai-x')
        dh("rm -f \"$HOME\"/.claude/hooks/ai-path-guard.sh is denied", "deny",
           'rm -f "$HOME"/.claude/hooks/ai-path-guard.sh')
        dh("echo x > ~/.claude/hooks/ai-path-guard.sh is denied", "deny", 'echo x > ~/.claude/hooks/ai-path-guard.sh')
        dh("in a task: cp into ~/.claude/claude-agentic/ai/ is denied", "deny",
           'cp /tmp/x ~/.claude/claude-agentic/ai/policies/git.md')
        os.remove(rootlink)

    def test_17_nested_roots_reads_head_allowed_missed_writes(self):
        # B1: a cwd inside a nested .ai/ tree (a fixture, the ai-init templates, a
        # worktree) must not unprotect the outer project's control files: every
        # ancestor that holds .ai/ is a root. HEAD denied all of these.
        nest = self.tmp + "/nest"
        for d in (".ai/state", ".ai/policies", ".ai/reports/T-1", "sub/fix/.ai/policies"):
            os.makedirs(nest + "/" + d)
        self.write(nest + "/.ai/state/current.json", "{}\n")
        self.write(nest + "/.ai/policies/path-guard.json", "{}\n")
        cwd = nest + "/sub/fix"

        def nest_tool(name, path):
            return tool(cwd, name, path, content="{}")
        self.decide("cwd in a nested .ai/ tree: Write to the outer root's state file is denied", "deny",
                    nest_tool("Write", nest + "/.ai/state/current.json"))
        self.decide("cwd in a nested .ai/ tree: Write to the outer root's handoff is denied", "deny",
                    nest_tool("Write", nest + "/.ai/state/handoff.md"))
        self.decide("cwd in a nested .ai/ tree: Edit of the outer root's policy file is denied", "deny",
                    nest_tool("Edit", nest + "/.ai/policies/path-guard.json"))
        self.decide("cwd in a nested .ai/ tree: Write to the outer root's journal is denied", "deny",
                    nest_tool("Write", nest + "/.ai/reports/T-1/events.jsonl"))
        self.decide("cwd in a nested .ai/ tree: echo >> ../../.ai/state/handoff.md is denied", "deny",
                    self.b("echo x >> ../../.ai/state/handoff.md", cwd))
        self.decide("cwd in a nested .ai/ tree: cp onto the outer root's policy file is denied", "deny",
                    self.b("cp /tmp/x %s/.ai/policies/path-guard.json" % nest, cwd))
        self.decide("cwd in a nested .ai/ tree: its own policy file is still the nearest root's", "deny",
                    nest_tool("Write", nest + "/sub/fix/.ai/policies/path-guard.json"))
        self.decide("cwd in a nested .ai/ tree: an ordinary file of the outer root is allowed", "allow",
                    nest_tool("Write", nest + "/src.txt"))
        dh = self.decide_home
        # M1: reads of report files that HEAD allowed at the fast path stay allowed:
        # incidental words (a count('a'), sys.stdout.write, re.compile, .copy(), a '|')
        # are no write.
        for c in [
            'python3 -c "print(open(\'.ai/reports/T-1/notes.md\').read().count(\'a\'))"',
            'python3 -c "import sys; sys.stdout.write(open(\'.ai/reports/T-1/review-report.md\').read())"',
            'python3 -c "import re; r=re.compile(\'BLOCKER\'); print(len(r.findall(open(\'.ai/reports/T-1/review-report.md\').read())))"',
            'python3 -c "import json; d=json.load(open(\'.ai/reports/T-1/sensors.json\')).copy(); print(d)"',
            'python3 -c "print(\'|\'.join(open(\'.ai/reports/T-1/plan.md\').read().split()))"',
            'ls .ai/reports/T-1/ && python3 -c "import sys; sys.stdout.write(\'ok\')"',
        ]:
            dh("a read HEAD allowed stays allowed: " + c, "allow", c)
        # L1, L2: write spellings the first indicators missed.
        for c in [
            'ruby -e \'f = File.new(".ai/state/handoff.md", "w"); f.puts "x"\'',
            'python3 -c "from pathlib import Path; Path(\'/tmp/c.json\').replace(\'.ai/state/current.json\')"',
            'python3 -c "import fileinput; [print(l) for l in fileinput.input(\'.ai/state/handoff.md\', inplace=True)]"',
            'python3 -c "import io; io.FileIO(\'.ai/state/current.json\', \'w\')"',
            'perl -MFile::Slurp -e \'write_file(".ai/state/handoff.md", "x")\'',
            "perl -pi -e 's/a/b/' .ai/reports/T-1/notes.md",
            "perl -i -pe 's/a/b/' .ai/reports/T-1/notes.md",
            'ruby -i -pe \'sub(/a/, "b")\' .ai/reports/T-1/notes.md',
        ]:
            dh("a writing one-liner is denied: " + c, "deny", c)

    def test_18_m2_l4(self):
        dh = self.decide_home
        # M2: a switch that only starts with an in-place letter, a str.replace and a
        # quoted 'a' after any comma are reads. HEAD denied the first five.
        for c in [
            'ruby -rdigest -e \'puts Digest::SHA256.hexdigest(File.read(".ai/state/current.json"))\'',
            "perl -mio -e 'print 1' .ai/reports/T-1/notes.md",
            'python3 -c "from pathlib import Path; print(Path(\'.ai/state/current.json\').read_text().replace(\'a\',\'b\'))"',
            'python3 -c "import json; d=json.load(open(\'.ai/state/current.json\')); print(d.get(\'x\', \'a\'))"',
            'python3 -c "print(\'x\', \'|y\', open(\'.ai/state/current.json\').read())"',
            "perl -Mstrict -e 'print 1' .ai/reports/T-1/notes.md",
            'python3 -c "print(\', \'.join(open(\'.ai/state/current.json\').read().split()))"',
        ]:
            dh("a read is allowed: " + c, "allow", c)
        # L4: Path.copy, copy_into and move_into (Python 3.14) write their target.
        for c in [
            'python3 -c "from pathlib import Path; Path(\'/tmp/x\').copy(\'.ai/state/current.json\')"',
            'python3 -c "from pathlib import Path; t=\'.ai/state/current.json\'; Path(\'/tmp/x\').copy(t, follow_symlinks=False)"',
            'python3 -c "from pathlib import Path; Path(\'/tmp/x\').copy_into(\'.ai/state/\')"',
            'python3 -c "from pathlib import Path; Path(\'/tmp/x\').move_into(\'.ai/state/\')"',
        ]:
            dh("a writing one-liner is denied: " + c, "deny", c)
        # Writes that the tightened indicators must still see; ruby -r json -i is a
        # miss on HEAD, the separate argument ended the option loop.
        for c in [
            "perl -pie 's/a/b/' .ai/reports/T-1/notes.md",
            "perl -i.bak -pe 's/a/b/' .ai/reports/T-1/notes.md",
            "perl -0777 -pi -e 's/a/b/' .ai/reports/T-1/notes.md",
            "perl -I lib -i -pe 's/a/b/' .ai/reports/T-1/notes.md",
            'ruby -i2 -pe \'sub(/a/, "b")\' .ai/reports/T-1/notes.md',
            'ruby -r json -i -pe \'sub(/a/, "b")\' .ai/reports/T-1/notes.md',
            'python3 -c "import os; a=\'.ai/state/\'; b=\'handoff.md\'; print(\'x\', file=open(os.path.join(a, b), \'w\'))"',
            'node -e "const fs=require(\'fs\'); fs.openSync(\'.ai/state/current.json\', \'a\')"',
            'perl -e \'open my $fh, ">", ".ai/state/handoff.md"; print $fh "x"\'',
            'perl -e \'my $f=".ai/state/handoff.md"; open(F, ">>$f"); print F "x"\'',
            'python3 -c "from pathlib import Path; f=Path(\'.ai/state/handoff.md\').open(\'w\'); print(\'x\', file=f)"',
            'python3 -c "print(\'x\', file=open(\'.ai/state/handoff.md\', mode=\'w\'))"',
            'python3 -c "from pathlib import Path; p=Path(\'/tmp/c\'); t=Path(\'.ai/state/current.json\'); p.replace(str(t))"',
        ]:
            dh("a writing one-liner is still denied: " + c, "deny", c)
        # Review of T-2026-10-25-001, H1, L1: the first-argument walk reads three
        # levels of parens, quoted strings and new Class(; HEAD denied all of these.
        for c in [
            'python3 -c "import os; open(os.path.join(os.getcwd(), \'.ai/state/current.json\'), \'w\').close()"',
            'python3 -c "from pathlib import Path; f=open(str(Path.cwd() / \'.ai/reports/T-1/notes.md\'), \'a\'); print(\'x\', file=f)"',
            'node -e "const fs=require(\'fs\'), path=require(\'path\'); const fd=fs.openSync(path.join(process.cwd(), \'.ai/state/current.json\'), \'w\'); fs.writeSync(fd, \'{}\')"',
            'ruby -e "File.open(File.expand_path(File.join(Dir.pwd, \'.ai/state/current.json\')), \'w\') { |f| f.puts \'x\' }"',
            'php -c x.ini -e "\\$h = fopen(dirname(getcwd()) . \'/.ai/reports/T-1/notes.md\', \'a\'); fprintf(\\$h, \'x\');"',
            'perl -MIO::File -e \'my $fh = new IO::File(".ai/reports/T-1/notes.md", "w"); print $fh "x"\'',
            'php -c x.ini -e "\\$f = new SplFileObject(\'.ai/state/current.json\', \'w\');"',
            'python3 -c "print(\'x\', file=open(\'.ai/reports/T-1/a,b.md\', \'w\'))"',
            'python3 -c "print(\'x\', file=open(\\".ai/reports/T-1/n.md\\", \\"a\\"))"',
            'python3 -c "import os; from pathlib import Path; p=Path(\'/tmp/a\'); p.replace(os.path.join(\'.ai/state/\', \'b\'))"',
            "perl -gpi -e 's/a/b/' .ai/reports/T-1/notes.md",
            "perl -tpi -e 's/a/b/' .ai/reports/T-1/notes.md",
            'ruby -vpi -e \'sub(/a/, "b")\' .ai/reports/T-1/notes.md',
            'ruby -E utf-8 -i -pe \'sub(/a/, "b")\' .ai/reports/T-1/notes.md',
        ]:
            dh("a writing one-liner is still denied: " + c, "deny", c)
        # L2: a copy.copy and a str.replace whose string holds a paren are reads.
        for c in [
            'python3 -c "import copy, json; from pathlib import Path; d=copy.copy(json.loads(Path(\'.ai/state/current.json\').read_text())); print(d)"',
            'python3 -c "from pathlib import Path; print(Path(\'.ai/state/current.json\').read_text().replace(\')\', \'\'))"',
        ]:
            dh("a read is allowed: " + c, "allow", c)
        # The mode indicator walks the first argument with a nested group: a long line
        # of commas and parens goes to grep (ere_match), measured at 40 KB.
        self.timed("a 40 KB one-liner of commas and parens that reads the state is allowed", "allow",
                   self.b("python3 -c \"print(open('.ai/state/current.json').read())\" # open(" + "(a, b)," * 5800),
                   1000)

    def test_19_project_without_ai_every_guard_is_inert(self):
        bare = self.tmp + "/bare"
        os.makedirs(bare)
        self.write(bare + "/.env", "SECRET=1\n")
        with self.subTest("no .ai/: reading .env is not blocked"):
            self.assertEqual(self.out(tool(bare, "Read", bare + "/.env")), "")


if __name__ == "__main__":
    unittest.main()
