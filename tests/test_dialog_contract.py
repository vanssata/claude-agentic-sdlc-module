#!/usr/bin/env python3
"""R36 spec design item 2: state.py keeps its own small consent-ledger reader
rather than importing the hooks' module. This contract feeds every reader the
same fixtures (tests/fixtures/dialog/ledger/), so the two cannot drift. Task 7c
asserted the state.py side; 7d1 added hooks/guard/dialog.py's reader to READERS."""

import json
import os
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "dialog", "ledger")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position
from guard import dialog  # noqa: E402  pylint: disable=wrong-import-position


def state_reader(path, session, at):
    return [p["id"] for p in state_mod.live_picks(state_mod.read_ledger(None, path), session, at)]


def hooks_reader(path, session, at):
    return [p["id"] for p in dialog.live_picks(dialog.read_ledger(None, path), session, at)]


READERS = {"state.py": state_reader, "hooks/guard/dialog.py": hooks_reader}


def cases():
    with open(os.path.join(FIXTURES, "cases.json"), encoding="utf-8") as fh:
        return json.load(fh)


class TestLedgerContract(unittest.TestCase):
    def test_every_reader_agrees_on_every_case(self):
        for case in cases():
            at = datetime.strptime(case["at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            for name, reader in READERS.items():
                with self.subTest(case=case["name"], reader=name):
                    self.assertEqual(reader(os.path.join(FIXTURES, case["ledger"]), case["session"], at),
                                     case["live"])

    def test_every_fixture_has_a_case(self):
        used = {case["ledger"] for case in cases()}
        present = {name for name in os.listdir(FIXTURES) if name.endswith(".jsonl")}
        self.assertEqual(present - used, set())

    def test_fixture_lines_fit_one_write(self):
        for name in os.listdir(FIXTURES):
            if name.endswith(".jsonl"):
                with open(os.path.join(FIXTURES, name), "rb") as fh:
                    for line in fh:
                        self.assertLessEqual(len(line), state_mod.LEDGER_LINE_MAX, name)

    def test_both_label_rules_agree(self):
        """Review L1: the hooks' validate_label and state.py's, over labels that
        name this repository's state.py (state.py also checks the path)."""
        here = os.path.abspath(state_mod.__file__)
        labels = ["git commit -m 'fix' -- a.py", "git commit -m \"it's done\" -- a.py", "git push origin feat/x",
                  "git push origin mäin", "git push origin ma٣in", "git push origin +feat", "git push origin a:b",
                  "git push -f origin main", "git push origin", "npx riskrails@3.1.0 --target claude --yes",
                  "npx riskrails@１.0 --yes", "npx other@1.0.0 --yes", "git status", "",
                  "python3 %s --root /p approve --by me" % here, "python3 -I -S %s reject --by me" % here,
                  "python3 %s profile set max20" % here, "python3 %s --root /p verify --scope all" % here,
                  "python3 %s --root /p review --verdict pass --by me" % here, "python3 %s close" % here,
                  "python3 %s start --mode light --by me" % here, "python %s approve --by me" % here,
                  "git commit -m x; ls", "git commit -m $(id)", "git commit -m 'a\tb'"]
        for label in labels:
            with self.subTest(label=label):
                self.assertEqual(dialog.validate_label(label) is None, state_mod.validate_label(label) is None)

    def test_both_sides_share_the_limits(self):
        self.assertEqual((dialog.LINE_MAX, dialog.LOCK_STALE_S, dialog.LABEL_MAX, dialog.LEDGER_TYPES),
                         (state_mod.LEDGER_LINE_MAX, state_mod.LOCK_STALE, state_mod.LABEL_MAX,
                          state_mod.LEDGER_TYPES))


class TestSwitchContract(unittest.TestCase):
    """One rule for both switches: state.py dialog_on() and the hooks'
    switch_state() agree on every combination of their inputs."""

    CLEAR = ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID", "AI_UNATTENDED", "CLAUDE_CODE_SESSION_ATTENDED",
             "CLAUDE_CONFIG_DIR", "CODEX_HOME")

    def test_tables_are_equal(self):
        self.assertEqual(state_mod.SESSION_ENV, dialog.SESSION_ENV)
        self.assertEqual(state_mod.DIALOG_TOOL, dialog.DIALOG_TOOL)

    @staticmethod
    def build(tmp, runtime, policy, tool):
        root = os.path.join(tmp, "project")
        os.makedirs(os.path.join(root, ".ai", "policies"))
        deep = "[" * 200000                  # nested past the parser's recursion limit
        if policy is not None:
            with open(os.path.join(root, ".ai", "policies", "dialog.json"), "w", encoding="utf-8") as fh:
                if policy == "nested":
                    fh.write(deep)
                else:
                    json.dump({"enabled": policy}, fh)
        home = os.path.join(tmp, "home")
        if tool != "missing":
            # "legacy": the verified tool, but only in the pre-3.4b <home>/claude-agentic/ file
            # that read_profile() still falls back to; the hooks never read it.
            folder = "claude-agentic" if tool == "legacy" else "riskrails"
            os.makedirs(os.path.join(home, folder))
            value = dialog.DIALOG_TOOL[runtime] if tool in ("verified", "legacy") else "Wrong"
            with open(os.path.join(home, folder, "profile.json"), "w", encoding="utf-8") as fh:
                if tool == "nested":
                    fh.write(deep)
                else:
                    json.dump({"dialog": {"tool": value}}, fh)
        return root, home

    def test_dialog_on_agrees_with_switch_state(self):
        """On the diagonal, where the environment and the payload carry the same
        session id or both none: "on" is a dict, "off" and "closed" are None.
        The off-diagonal cases are test_session_ids_that_differ."""
        seen = set()
        for runtime in ("claude", "codex"):
            for policy in (True, None, False, "nested"):
                for unattended in (False, True):
                    for attended0 in (False, True):
                        for tool in ("verified", "wrong", "missing", "legacy", "nested"):
                            for sid in ("sess-1234", ""):
                                self.check(runtime, policy, unattended, attended0, tool, sid, sid, seen)
        self.assertEqual(seen, {"on", "off", "closed"})

    def test_session_ids_that_differ(self):
        """The one place the switches may differ. The hooks compare the payload's
        session id with their own environment's; dialog_on() only has the
        environment. (a) payload id, no environment id: hooks "on" (no own id to
        contradict), dialog_on None (no session to bind a pick to) - a pick cannot
        be bound, so the commit is denied: fail-safe. (b) environment id, no
        payload id: hooks "closed", dialog_on a dict (it never sees the payload),
        so only a payload-less call, which the hooks refuse anyway, differs.
        (c) different ids: hooks "closed", dialog_on a dict for the environment's
        id; the hook refuses the call, so the dict is never used to act on it."""
        for runtime in ("claude", "codex"):
            for tool in ("verified", "wrong"):
                seen = set()
                with self.subTest(runtime=runtime, tool=tool):
                    hooks, got = self.check(runtime, True, False, False, tool, "", "sess-1234", seen)
                    self.assertEqual((hooks, got), ("on" if tool == "verified" else "off", None))
                    hooks, got = self.check(runtime, True, False, False, tool, "sess-1234", "", seen)
                    self.assertEqual(hooks, "closed" if tool == "verified" else "off")
                    self.assertEqual(bool(got), tool == "verified")
                    hooks, got = self.check(runtime, True, False, False, tool, "sess-1234", "sess-other", seen)
                    self.assertEqual(hooks, "closed" if tool == "verified" else "off")
                    self.assertEqual(bool(got), tool == "verified")
                    if got:
                        self.assertEqual(got["session"], "sess-1234")

    def check(self, runtime, policy, unattended, attended0, tool, env_sid, payload_sid, seen):
        """Runs both switches; returns (hooks' state, dialog_on's result)."""
        name = "%s policy=%s unattended=%s attended0=%s tool=%s env_session=%r payload_session=%r" % (
            runtime, policy, unattended, attended0, tool, env_sid, payload_sid)
        sid = payload_sid
        diagonal = env_sid == payload_sid
        with tempfile.TemporaryDirectory() as tmp:
            root, home = self.build(tmp, runtime, policy, tool)
            env = {"CODEX_HOME" if runtime == "codex" else "CLAUDE_CONFIG_DIR": home}
            if env_sid:
                env[dialog.SESSION_ENV[runtime]] = env_sid
            if unattended:
                env["AI_UNATTENDED"] = "1"
            if attended0:
                env["CLAUDE_CODE_SESSION_ATTENDED"] = "0"
            payload = {"session_id": sid, "hook_event_name": "PreToolUse"}
            with mock.patch.dict(os.environ, env, clear=False), mock.patch.object(state_mod, "RUNTIME", runtime):
                for var in self.CLEAR:
                    if var not in env:
                        os.environ.pop(var, None)
                hooks = dialog.switch_state(root, runtime, payload)
                got = state_mod.dialog_on(root)
        with self.subTest(name):
            seen.add(hooks)
            if diagonal:
                self.assertEqual(bool(got), hooks == "on")
                if hooks == "on":
                    self.assertEqual(got["session"], payload["session_id"])
                if not sid and policy is True and tool == "verified" and not unattended and not attended0:
                    self.assertEqual(hooks, "closed")
                    self.assertIsNone(got)
            if hooks == "off":
                self.assertIsNone(got)
        return hooks, got


if __name__ == "__main__":
    unittest.main()
