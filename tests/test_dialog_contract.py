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

    def test_both_readers_skip_only_a_too_deep_line(self):
        """A line nested past the parser's stack is torn like any other: both
        readers skip it and nothing else (written to a temp file: a fixture
        line may not pass LEDGER_LINE_MAX)."""
        good = json.dumps({"v": 1, "type": "void", "ids": ["C1"]})
        other = json.dumps({"v": 1, "type": "void", "ids": ["C2"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "consent.jsonl")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("%s\n%s\n%s\n" % (good, "[" * 200000, other))
            seen = {"state.py": state_mod.read_ledger(None, path), "hooks/guard/dialog.py": dialog.read_ledger(None, path)}
        for name, entries in seen.items():
            with self.subTest(reader=name):
                self.assertEqual([e["ids"] for e in entries], [["C1"], ["C2"]])

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
        self.assertEqual(state_mod.JSON_DEPTH_MAX, dialog.JSON_DEPTH_MAX)

    @staticmethod
    def nested(total, key_tail):
        """A valid object of exactly `total` nesting levels, the outer one counted."""
        return '{"%s": %s, "s": "[[{\\"]"}' % (key_tail, "[" * (total - 1) + "0" + "]" * (total - 1)) \
            if total > 1 else '{}'

    def test_nesting_cap_is_one_rule(self):
        """A file nested exactly JSON_DEPTH_MAX deep reads in both modules; one level
        deeper is malformed in both, whatever the stack depth."""
        cap = dialog.JSON_DEPTH_MAX
        for runtime in ("claude", "codex"):
            for total, ok in ((cap, True), (cap + 1, False)):
                with self.subTest(runtime=runtime, total=total), tempfile.TemporaryDirectory() as tmp:
                    root = os.path.join(tmp, "project")
                    os.makedirs(os.path.join(root, ".ai", "policies"))
                    with open(os.path.join(root, ".ai", "policies", "dialog.json"), "w", encoding="utf-8") as fh:
                        fh.write(self.nested(total, "enabled").replace('"enabled": ', '"enabled": true, "x": ', 1))
                    home = os.path.join(tmp, "home")
                    os.makedirs(os.path.join(home, "riskrails"))
                    tool = dialog.DIALOG_TOOL[runtime]
                    with open(os.path.join(home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
                        fh.write(self.nested(total, "dialog").replace('"dialog": ', '"dialog": {"tool": "%s"}, "x": ' % tool, 1))
                    env = {"CODEX_HOME" if runtime == "codex" else "CLAUDE_CONFIG_DIR": home}
                    with mock.patch.dict(os.environ, env, clear=False):
                        self.assertEqual(dialog.dialog_policy(root) is not None, ok)
                        self.assertEqual(state_mod.dialog_policy(root) is not None, ok)
                        self.assertEqual(dialog.dialog_tool(runtime) == tool, ok)
                        self.assertEqual(state_mod.dialog_tool_verified(runtime) == tool, ok)

    def test_read_profile_survives_deep_nesting(self):
        """read_profile returns {} for a non-dict too, so the cap cases are objects: a dict
        nested exactly JSON_DEPTH_MAX deep is read, one level deeper is {} only because of the cap."""
        cap = state_mod.JSON_DEPTH_MAX

        def balanced(total):
            return '{"a":' + "[" * (total - 1) + "0" + "]" * (total - 1) + "}"
        for name, text, want in (("unterminated 200000", "[" * 200000, {}),
                                 ("balanced cap + 1", balanced(cap + 1), {}),
                                 ("balanced cap", balanced(cap), json.loads(balanced(cap)))):
            with self.subTest(case=name), tempfile.TemporaryDirectory() as tmp:
                os.makedirs(os.path.join(tmp, "riskrails"))
                with open(os.path.join(tmp, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
                    fh.write(text)
                with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": tmp}, clear=False):
                    self.assertEqual(state_mod.read_profile("claude"), want)

    def test_scanner_copies_agree_on_escapes(self):
        """The two json_loads_capped scanners are copies; a drift in one copy's string/escape
        handling must turn this red, so the table puts brackets next to quotes and backslashes."""
        cap = dialog.JSON_DEPTH_MAX

        def deep(total, head):
            return '{%s"a":%s0%s}' % (head, "[" * (total - 1), "]" * (total - 1))
        texts = [
            '{"a": "\\\\", "b": [[0]]}',                    # escaped backslash before the closing quote
            '{"a": "\\"[[", "b": 1}',                        # escaped quote, then brackets, inside a string
            '{"a": "[[[{{{]]]}}}", "b": [1]}',
            '{"a": "\u005b\u00e9\u4e2d", "b": []}',
            '{}', '[]', '',
            deep(cap, '"s": "\\"[[[", '),
            deep(cap + 1, '"s": "\\"[[[", '),
            deep(cap, '"s": "\\\\", '),
            deep(cap + 1, '"s": "\\\\", '),
            deep(cap, '"s": "\\\\\\"[{", '),
            deep(cap + 1, '"s": "]]]}}}", '),
        ]

        def run(module, text):
            try:
                return ("ok", module.json_loads_capped(text))
            except ValueError as exc:
                return ("err", type(exc).__name__ if not isinstance(exc, json.JSONDecodeError) else "decode")
        for text in texts:
            with self.subTest(text=text[:60]):
                a, b = run(dialog, text), run(state_mod, text)
                self.assertEqual(a[0], b[0])
                if a[0] == "ok":
                    self.assertEqual(a[1], b[1])
        # the cap itself is enforced, not just agreed on, in both copies
        for module in (dialog, state_mod):
            self.assertEqual(module.json_loads_capped(deep(cap, '"s": "\\"[[[", '))["s"], '"[[[')
            with self.assertRaises(ValueError):
                module.json_loads_capped(deep(cap + 1, '"s": "\\\\", '))

    @staticmethod
    def build(tmp, runtime, policy, tool):
        root = os.path.join(tmp, "project")
        os.makedirs(os.path.join(root, ".ai", "policies"))
        deep = "[" * 200000                  # nested past the parser's recursion limit
        if policy is not None:
            with open(os.path.join(root, ".ai", "policies", "dialog.json"), "w", encoding="utf-8") as fh:
                if policy == "nested":
                    fh.write(deep)
                elif policy in ("background", "background-text"):
                    # background_sessions: only the boolean true counts, a string is no opt-in
                    json.dump({"enabled": True,
                               "background_sessions": True if policy == "background" else "true"}, fh)
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
            for policy in (True, None, False, "nested", "background", "background-text"):
                for unattended in (False, True):
                    for attended0 in (False, True):
                        for tool in ("verified", "wrong", "missing", "legacy", "nested"):
                            for sid in ("sess-1234", ""):
                                self.check(runtime, policy, unattended, attended0, tool, sid, sid, seen)
        self.assertEqual(seen, {"on", "off", "closed"})

    def test_background_sessions_opt_in(self):
        """dialog.json background_sessions: true keeps the switch on when Claude
        Code marks the session unattended (CLAUDE_CODE_SESSION_ATTENDED=0, a
        background job a human may still be chatting in). Only that marker: an
        explicit AI_UNATTENDED, a subagent, a missing session id, an unverified
        tool and a string instead of true still turn it off or close it."""
        for runtime in ("claude", "codex"):
            seen = set()
            with self.subTest(runtime=runtime):
                cases = (
                    # policy, AI_UNATTENDED, ATTENDED=0, tool, session id -> hooks' state
                    (("background", False, True, "verified", "sess-1234"), "on"),
                    (("background", False, False, "verified", "sess-1234"), "on"),
                    ((True, False, True, "verified", "sess-1234"), "off"),
                    (("background-text", False, True, "verified", "sess-1234"), "off"),
                    (("background", True, True, "verified", "sess-1234"), "off"),
                    (("background", True, False, "verified", "sess-1234"), "off"),
                    (("background", False, True, "wrong", "sess-1234"), "off"),
                    (("background", False, True, "verified", ""), "closed"),
                )
                for args, want in cases:
                    hooks, got = self.check(runtime, args[0], args[1], args[2], args[3], args[4], args[4], seen)
                    self.assertEqual(hooks, want, args)
                    self.assertEqual(bool(got), want == "on", args)
                with tempfile.TemporaryDirectory() as tmp:
                    root, home = self.build(tmp, runtime, "background", "verified")
                    env = {"CODEX_HOME" if runtime == "codex" else "CLAUDE_CONFIG_DIR": home,
                           "CLAUDE_CODE_SESSION_ATTENDED": "0"}
                    with mock.patch.dict(os.environ, env):
                        for var in self.CLEAR:      # the scratch home only, never the machine's profile
                            if var not in env:
                                os.environ.pop(var, None)
                        payload = {"session_id": "sess-1234", "agent_id": "a1"}
                        self.assertEqual(dialog.switch_state(root, runtime, payload), "closed",
                                         "a subagent stays closed under the opt-in")

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
            with mock.patch.dict(os.environ, env, clear=False):
                for var in self.CLEAR:
                    if var not in env:
                        os.environ.pop(var, None)
                hooks = dialog.switch_state(root, runtime, payload)
                got = state_mod.dialog_on(root, runtime=runtime)
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
