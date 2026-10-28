#!/usr/bin/env python3
"""R36 (7d2): consent, end to end through hooks/ai-guard.py — the git consent
rule (R36.9), the path guard's pass-through for a live pick (R36.11) — and
R36.22, the model cannot forge consent.

A case runs in a scratch project of its own: dialog.json on or off, the
runtime's profile with its verified dialog tool, decision.json, the ledger's
picks written the way the recorder writes them, a task in flight when the case
needs one. The consent cases are a table here rather than fixture files: the
git-guard, path-guard and codex-hooks fixture directories run stateless (their
suites and the golden corpus), where a case that needs a ledger cannot hold."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from guard import dialog  # noqa: E402  pylint: disable=wrong-import-position
from guard_harness import decision as decision_of  # noqa: E402  pylint: disable=wrong-import-position
import test_dialog_gate as tg  # noqa: E402  pylint: disable=wrong-import-position
import test_ai_task_state as tas  # noqa: E402  pylint: disable=wrong-import-position

SESSION = "sess-main"
SAFE = tg.SAFE
STATE = "python3 /p/skills/ai-task/state.py --root . "
COMMIT = "git commit -m x -- a.py"
QUOTED = "git commit -m \"it's done\" -- a.py"
NO_VERIFY = "git commit --no-verify -m x"
APPROVE = STATE + "approve --by ivan"
PROFILE = "python3 /p/skills/ai-task/state.py profile set --runtime claude --plan max"
VERIFY = STATE + "verify --scope all --by ivan"


def dec(did, kind, *commands, session=None, runtime="claude"):
    options = [{"n": 1, "kind": "choice", "label": SAFE}] + [
        {"n": n, "kind": "command", "label": c} for n, c in enumerate(commands, 2)]
    out = {"id": did, "kind": kind, "runtime": runtime, "question": "Run it?", "header": "Run",
           "multi_select": len(commands) > 1, "options": options}
    if session:
        out["session"] = session
    return out


def pick(label, option=2, order=1, decision="D1", **kw):
    return dict({"decision": decision, "option": option, "order": order, "label": label}, **kw)


# (name, expect, command, reason in the deny, setup)
CASES = [
    ("git commit with no pick is refused (R36.9)", "deny", COMMIT, "CONSENT_REQUIRED", {}),
    ("the commit equal to the live pick runs, once (R36.7, R36.9)", "allow", COMMIT, None,
     {"decisions": [dec("D1", "commit", COMMIT)], "picks": [pick(COMMIT)], "ledger_after": ["pick", "use"]}),
    ("a pick never lifts the protected-branch rule (R36.9)", "deny", "git push origin main", "protected branch",
     {"decisions": [dec("D1", "commit", "git push origin main")], "picks": [pick("git push origin main")]}),
    ("a pick never lifts --no-verify, and the deny says the pick was used (review focus 1)", "deny", NO_VERIFY,
     "C1 was used", {"decisions": [dec("D1", "commit", NO_VERIFY)], "picks": [pick(NO_VERIFY)],
                     "ledger_after": ["pick", "use"]}),
    ("a label with quotes round-trips verbatim (review focus 2)", "allow", QUOTED, None,
     {"decisions": [dec("D1", "commit", QUOTED)], "picks": [pick(QUOTED)]}),
    ("a pick from another session is no consent (R36.7)", "deny", COMMIT, "CONSENT_REQUIRED",
     {"decisions": [dec("D1", "commit", COMMIT, session="another")], "picks": [pick(COMMIT, session="another")]}),
    ("an expired pick is no consent (R36.7)", "deny", COMMIT, "CONSENT_REQUIRED", {"picks": [pick(COMMIT, age=200)]}),
    ("a ledger that cannot be read means deny: the consent rule fails closed (R36.9)", "deny", COMMIT,
     "CONSENT_REQUIRED", {"unreadable_ledger": True}),
    ("dialog off: a commit runs as today (R36.2)", "allow", COMMIT, None, {"dialog": False}),
    ("a commit after cd needs a pick too (R36.9)", "deny", "cd src && " + COMMIT, "CONSENT_REQUIRED", {}),
    ("git -C <dir> commit needs a pick (R36.9)", "deny", "git -C /tmp commit -m x", "CONSENT_REQUIRED", {}),
] + [
    # Review M1: git commands that are not a commit or a push, and those that
    # change nothing, need no pick — none of them could be picked.
    ("dialog on: %s needs no pick (review M1)" % command, "allow", command, None, {})
    for command in ("git stash push -u -m wip", "git grep -n commit", "git help commit", "git commit --help",
                    "git push --dry-run origin feature", "git log --format=%s -- commit",
                    "git rev-list --count HEAD -- push", "echo git commit",
                    "gh pr create --title t --body \"after this, git push origin x\"")
] + [
    ("approve equal to the live pick passes the path guard; state.py checks argv (R36.11)", "allow", APPROVE, None,
     {"task": True, "decisions": [dec("D1", "approval", APPROVE)], "picks": [pick(APPROVE)],
      "ledger_after": ["pick"]}),
    ("approve with no pick keeps today's deny (R36.11)", "deny", APPROVE, "Refusing 'state.py approve'",
     {"task": True}),
    ("profile set equal to the live pick passes (R36.11)", "allow", PROFILE, None,
     {"decisions": [dec("D1", "plan_drift", PROFILE)], "picks": [pick(PROFILE)]}),
    ("dialog on: profile set with no pick is the human's (R36.11)", "deny", PROFILE, "profile set", {}),
    ("verify --by equal to the live pick passes (R36.11)", "allow", VERIFY, None,
     {"task": True, "decisions": [dec("D1", "budget", VERIFY)], "picks": [pick(VERIFY)]}),
    ("dialog on: verify --by with no pick is the human's (R36.11)", "deny", VERIFY, "--by", {"task": True}),
    ("dialog on: review --by with no pick is the human's (R36.11)", "deny",
     STATE + "review --by ivan --verdict pass", "--by", {"task": True}),
    # Review H1: raising a mode needs no human; a lowering opens its decision in state.py.
    ("dialog on: start --mode full --by reaches state.py (raising is free)", "allow",
     STATE + "start --mode full --by ivan --goal g", None, {}),
    ("dialog on: start --mode light --by reaches state.py, which opens the decision", "allow",
     STATE + "start --mode light --by ivan", None, {"task": True}),
    ("dialog on: reject --by with no pick is the human's (R36.11)", "deny",
     STATE + "reject --by ivan --why no", "--by", {"task": True}),
    ("dialog off: verify --by runs as today (R36.2)", "allow", VERIFY, None, {"task": True, "dialog": False}),
    ("dialog off: profile set runs as today (R36.2)", "allow", PROFILE, None, {"dialog": False}),
    ("running the recorder by hand is refused with the dialog on (R36.11)", "deny",
     "echo {} | python3 hooks/dialog-gate.py", "dialog-gate.py", {}),
    ("codex: a commit with no pick is refused (R36.9)", "deny", COMMIT, "CONSENT_REQUIRED", {"runtime": "codex"}),
    ("codex: the commit equal to the live pick runs (R36.9)", "allow", COMMIT, None,
     {"runtime": "codex", "decisions": [dec("D1", "commit", COMMIT, runtime="codex")],
      "picks": [pick(COMMIT, runtime="codex")]}),
    ("codex: approve with no pick keeps today's deny (R36.11)", "deny", APPROVE, "Refusing 'state.py approve'",
     {"runtime": "codex", "task": True}),
]


class Project:
    """A scratch project and runtime homes for one case."""

    def __init__(self, dialog_on=True, task=False):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.root = os.path.join(self.tmp.name, "p")
        os.makedirs(os.path.join(self.root, ".ai", "policies"))
        os.makedirs(os.path.join(self.root, ".ai", "state"))
        subprocess.run(["git", "init", "-q", "-b", "feature", self.root], check=True)
        self.home = os.path.join(self.tmp.name, "home")
        for runtime, home in (("claude", self.home), ("codex", self.home + "-codex")):
            os.makedirs(os.path.join(home, "riskrails"))
            self.write_abs(os.path.join(home, "riskrails", "profile.json"),
                           {"plan": "max", "dialog": {"tool": dialog.DIALOG_TOOL[runtime]}})
        if dialog_on:
            self.write(".ai/policies/dialog.json", {"version": 1, "enabled": True, "window_seconds": 120,
                                                    "stop_blocks_max": 2})
        if task:
            self.write(".ai/state/state.json", {"task_id": "T-1", "current_stage": "implementation"})
        self.env = dict(os.environ, CLAUDE_CONFIG_DIR=self.home, CODEX_HOME=self.home + "-codex",
                        AI_UNATTENDED="", CLAUDE_CODE_SESSION_ATTENDED="1")
        self.picks = 0

    def close(self):
        self.tmp.cleanup()

    @staticmethod
    def write_abs(path, data):
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def write(self, rel, data):
        self.write_abs(os.path.join(self.root, rel), data)

    def decide(self, *decisions):
        self.write(".ai/state/decision.json", {"version": 1, "open": list(decisions)})

    def pick(self, decision, option, order, label, session=SESSION, age=5, runtime="claude",
             tool_use_id="toolu_dialog"):
        self.picks += 1
        at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=age)
        line = {"v": 1, "type": "pick", "id": "C%d" % self.picks, "decision": decision, "option": option,
                "order": order, "label": label, "session": session, "tool_use_id": tool_use_id,
                "transcript": os.path.join(self.root, "t.jsonl"), "runtime": runtime, "at": dialog.stamp(at),
                "expires_at": dialog.stamp(at + timedelta(seconds=120))}
        with open(dialog.ledger_path(self.root), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line) + "\n")
        return line

    def ledger(self):
        return dialog.read_ledger(self.root)

    def guard(self, command, runtime="claude", session=SESSION, tool="Bash", tool_input=None, **extra):
        payload = dict({"session_id": session, "transcript_path": os.path.join(self.root, "t.jsonl"),
                        "cwd": self.root, "hook_event_name": "PreToolUse", "tool_name": tool,
                        "tool_use_id": "toolu_run",
                        "tool_input": tool_input if tool_input is not None else {"command": command},
                        ("turn_id" if runtime == "codex" else "prompt_id"): "turn_1"}, **extra)
        proc = subprocess.run(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "ai-guard.py")],
                              input=json.dumps(payload), capture_output=True, text=True, check=False,
                              cwd=self.root, env=self.env)
        return proc.stdout

    def reason(self, out):
        try:
            return json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"]
        except (ValueError, KeyError, TypeError):
            return out


class TestConsentCases(unittest.TestCase):
    def test_cases(self):
        for name, expect, command, reason, setup in CASES:
            with self.subTest(name):
                p = Project(dialog_on=setup.get("dialog", True), task=setup.get("task", False))
                try:
                    if setup.get("decisions"):
                        p.decide(*setup["decisions"])
                    for entry in setup.get("picks", []):
                        p.pick(entry["decision"], entry["option"], entry["order"], entry["label"],
                               **{k: v for k, v in entry.items()
                                  if k in ("session", "age", "runtime")})
                    if setup.get("unreadable_ledger"):
                        os.makedirs(dialog.ledger_path(p.root))
                    out = p.guard(command, runtime=setup.get("runtime", "claude"))
                    self.assertEqual(decision_of(out), expect, out[:400])
                    if reason:
                        self.assertIn(reason, p.reason(out))
                    if setup.get("ledger_after"):
                        self.assertEqual([e["type"] for e in p.ledger()], setup["ledger_after"])
                finally:
                    p.close()


class TestModelCannotForgeConsent(unittest.TestCase):
    """R36.22 (a)-(g) here; (h) and (i) on state.py's side below."""

    def setUp(self):
        self.p = Project(task=True)

    def tearDown(self):
        self.p.close()

    def test_model_cannot_forge_consent(self):
        p = self.p
        with self.subTest("(a) a write aimed at the ledger or decision.json"):
            for rel in (".ai/state/consent.jsonl", ".ai/state/decision.json"):
                path = os.path.join(p.root, rel)
                for tool, tool_input in (("Write", {"file_path": path, "content": "{}"}),
                                         ("Edit", {"file_path": path, "old_string": "a", "new_string": "b"}),
                                         ("MultiEdit", {"file_path": path, "edits": []})):
                    self.assertEqual(decision_of(p.guard(None, tool=tool, tool_input=tool_input)), "deny",
                                     (tool, rel))
                for command in ("echo x >> %s" % rel, "echo x | tee -a %s" % rel, "cp /tmp/x %s" % rel,
                                "python3 -c \"open('%s','a').write('x')\"" % rel):
                    self.assertEqual(decision_of(p.guard(command)), "deny", command)
        with self.subTest("(b) the recorder run by hand"):
            for command in ("echo {} | python3 hooks/dialog-gate.py",
                            "python3 -I -S \"$HOME/.claude/hooks/dialog-gate.py\" < /tmp/x.json"):
                self.assertEqual(decision_of(p.guard(command)), "deny", command)
        with self.subTest("(f) a pick from another session, expired, used or out of order"):
            p.decide(dec("D1", "commit", COMMIT, "git push origin feat/x"))
            p.pick("D1", 2, 1, COMMIT, session="another")
            self.assertEqual(decision_of(p.guard(COMMIT)), "deny", "another session")
            p.pick("D1", 2, 1, COMMIT, age=200, tool_use_id="toolu_2")
            self.assertEqual(decision_of(p.guard(COMMIT)), "deny", "expired")
            p.pick("D1", 2, 1, COMMIT, tool_use_id="toolu_3")
            p.pick("D1", 3, 2, "git push origin feat/x", tool_use_id="toolu_3")
            self.assertEqual(decision_of(p.guard("git push origin feat/x")), "deny", "out of order")
            self.assertEqual(decision_of(p.guard(COMMIT)), "deny", "the mismatch voided every pick")
            p.pick("D1", 2, 1, COMMIT, tool_use_id="toolu_4")
            self.assertEqual(decision_of(p.guard(COMMIT)), "allow")
            self.assertEqual(decision_of(p.guard(COMMIT)), "deny", "used")

    def test_recorder_side(self):
        s = tg.Scratch()
        try:
            commit = tg.COMMIT
            with self.subTest("(c) a PostToolUse whose tool is not the dialog tool"):
                s.decide(tg.decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", commit)]))
                self.assertEqual(dialog.record(s.root, "claude", dict(tg.commit_payload(), tool_name="Bash")), [])
            with self.subTest("(d) answers that are not offered labels"):
                payload = tg.answer(tg.commit_payload(), "git commit -m forged -- a.py")
                self.assertEqual([line["type"] for line in dialog.record(s.root, "claude", payload)],
                                 ["offer", "decline"])
            with self.subTest("(g) a dialog with no decision open"):
                os.remove(os.path.join(s.root, ".ai", "state", "decision.json"))
                self.assertEqual(dialog.record(s.root, "claude", tg.commit_payload()), [])
            with self.subTest("(e) labels with &&, $( or a newline"):
                for bad in ("git commit -m x && git push origin main", "git commit -m $(id)",
                            "git commit -m x\ngit push origin main"):
                    s.decide(tg.decision("D1", "Run?", "Run", [("choice", SAFE), ("command", bad)]))
                    payload = tg.answer(tg.relabel(tg.spike("claude/ask-single"), {"A": SAFE, "B": bad}, "Run?",
                                                   "Run"), bad)
                    self.assertNotIn("pick", [line["type"] for line in dialog.record(s.root, "claude", payload)])
            self.assertNotIn("pick", [line["type"] for line in s.ledger()])
        finally:
            s.close()


class TestForgeryOnStatePy(tas.DialogBase):
    """R36.22 (h) approve with a live pick but argv != label exits 5; (i) a
    hand-appended pick fails `consent audit`."""

    full_gate = tas.TestDialogRoute.full_gate
    name = tas.TestDialogRoute.name
    argv = tas.TestDialogRoute.argv
    label = tas.TestDialogRoute.label

    def test_argv_must_equal_label(self):
        self.full_gate()
        self.p.pick("D1", 2)
        done = self.p.run("approve", "--by", "someone else")
        self.assertEqual(done.returncode, 5, done.stdout)
        self.assertFalse(self.p.state()["human_approval"]["granted"])

    def test_hand_appended_pick_is_a_mismatch(self):
        transcript = os.path.join(self.p.tmp.name, "session.jsonl")
        with open(transcript, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"type": "tool_use", "id": "toolu_real"}) + "\n")
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x")
        self.p.pick("D1", 2, tool_use_id="toolu_hand_written", transcript=transcript)
        self.assertIn("C1 D1 mismatch", self.p.run("consent", "audit").stdout)


if __name__ == "__main__":
    unittest.main()
