#!/usr/bin/env python3
"""R36: the dialog. Task 7c writes the payload half — what state.py prepares
for the dialog tool (golden payloads, the label rule, the multi-select split);
7d1 adds the hook half (the effective switch matrix, the recorder over the
7.0 fixtures, the ledger lock, Stop, the gate's fast path, the registrations).

The goldens are tests/fixtures/dialog/payload-golden/<case>.json, with the
scratch project's paths, task id, tree, branch and git user replaced by
placeholders. DIALOG_GOLDEN_UPDATE=1 rewrites them; review the diff."""

import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "dialog", "payload-golden")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from guard import dialog  # noqa: E402  pylint: disable=wrong-import-position
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position
from test_ai_task_state import CLEAN, STATE, DialogProject  # noqa: E402  pylint: disable=wrong-import-position
from guard_harness import decision as decision_of, hook_output  # noqa: E402  pylint: disable=wrong-import-position

PUSH = "git push origin feat/x"
SPIKE = os.path.join(ROOT, "tests", "fixtures", "dialog")
COMMIT = "git commit -m 'it'\"'\"'s done' -- a.py"
SAFE = "Not now — commit nothing"
NOW = datetime(2026, 10, 28, 12, 0, 0, tzinfo=timezone.utc)


def git(root, *args):
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True, text=True,
                          check=False).stdout.strip()


class TestPayload(unittest.TestCase):
    """R36.3: question ≤ 1200 characters, header ≤ 12, 2–4 options, the safe
    option first, multiSelect only for a command list, ≤ 4 questions a call."""

    def setUp(self):
        self.p = DialogProject()

    def tearDown(self):
        self.p.close()

    def normalise(self, text):
        name = git(self.p.root, "config", "user.name") or os.environ.get("USER") or "human"
        for value, placeholder in ((os.path.abspath(STATE), "<STATE>"), (self.p.root, "<ROOT>"),
                                   (git(self.p.root, "rev-parse", "--abbrev-ref", "HEAD"), "<BRANCH>"),
                                   (name, "<NAME>")):
            text = text.replace(value, placeholder)
        text = re.sub(r"T-\d{4}-\d{2}-\d{2}-\d{3}", "<TASK>", text)
        return re.sub(r"(tree|green on) [0-9a-f]{9}", r"\1 <TREE>", text)

    def shown(self):
        return json.loads(self.p.ok("decision", "show", "--json").stdout)

    def assert_golden(self, case, payload):
        text = self.normalise(json.dumps(payload, indent=1, ensure_ascii=False)) + "\n"
        path = os.path.join(GOLDEN, case + ".json")
        if os.environ.get("DIALOG_GOLDEN_UPDATE"):
            os.makedirs(GOLDEN, exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        with open(path, encoding="utf-8") as fh:
            self.assertEqual(text, fh.read(), "%s differs from its golden" % case)
        self.assert_shape(payload)

    def assert_shape(self, payload):
        self.assertLessEqual(len(payload["questions"]), 4)
        for question in payload["questions"]:
            self.assertLessEqual(len(question["question"]), 1200)
            self.assertLessEqual(len(question["header"]), 12)
            self.assertTrue(2 <= len(question["options"]) <= 4)
            self.assertTrue(question["options"][0]["label"].startswith(("Not now", "Keep")), question)
            commands = [o for o in question["options"][1:] if state_mod.validate_label(o["label"]) is None]
            if question["multiSelect"]:
                self.assertEqual(len(commands), len(question["options"]) - 1)

    def full_gate(self):
        """A full task, verified and reviewed, whose close opened the approval."""
        self.p.start("--mode", "full", "--by", "test")
        self.p.ok("verify", "--scope", "all")
        self.p.ok("review", "--verdict", "pass", "--tier", "STRONG", "--report", "-", stdin=CLEAN)
        return self.p.ok("close")

    def test_payload_golden(self):
        self.p.start()
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m 'it'\"'\"'s done' -- src/widget.py")
        self.assert_golden("commit", self.shown())
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m x -- src/widget.py",
                  "--command", PUSH)
        self.assert_golden("two-open", self.shown())
        self.assert_golden("commit-push", json.loads(self.p.ok("decision", "show", "--id", "D2", "--json").stdout))

    def test_payload_golden_approval_and_question(self):
        self.full_gate()
        self.assert_golden("approval", self.shown())
        self.p.ok("decision", "fallback", "--id", "D1", "--why", "golden")
        self.p.ok("ask", "Which cache key?", "--option", "A: per locale", "--option", "B: global",
                  "--recommend", "A", "--context", "src/widget.py:1")
        self.assert_golden("question", self.shown())

    def test_label_validator(self):
        here = os.path.abspath(STATE)
        good = ["git commit -m 'fix' -- a.py", "git commit -m \"it's done\" -- a.py", PUSH,
                "python3 %s --root /p approve --by 'Ivan Kakurov'" % here,
                "python3 %s --root /p reject --by me --why 'not now'" % here,
                "python3 %s profile set max20 --runtime claude" % here,
                "python3 %s --root /p verify --scope all --by me" % here,
                "python3 %s --root /p review --verdict pass --tier STRONG --by me" % here,
                "python3 %s --root /p start --goal g --mode light --by me" % here,
                "npx riskrails@3.1.0 --target claude --plan pro --yes"]
        bad = ["", " git commit -m x", "git commit -m x; ls", "git commit -m x & ls", "git commit -m x | ls",
               "git commit -m `id`", "git commit -m $(id)", "git commit -m x > f", "git commit -m x < f",
               "git commit -m 'a\nb'", "git commit -m 'x" + "y" * 400 + "'", "git push origin",
               "git push -f origin main", "git push origin main --tags", "git status",
               "python3 %s --root /p verify --scope all" % here, "python3 %s --root /p close" % here,
               "python3 %s --root /p start --mode light" % here, "python3 /tmp/other.py approve --by me",
               "npx riskrails --yes", "npx other@1.0.0 --yes", "git commit -m 'unbalanced",
               # review L2: any interpreter path, any state.py, a force push or a refspec
               "/tmp/x/python3 %s --root /p approve --by me" % here, "python3 /tmp/y/state.py approve --by me",
               "git push origin +feat", "git push origin HEAD:main", "git push origin feat:main"]
        for label in good:
            with self.subTest(good=label):
                self.assertIsNone(state_mod.validate_label(label))
        for label in bad:
            with self.subTest(bad=label):
                self.assertIsNotNone(state_mod.validate_label(label))

    def test_ambiguous_multiselect_splits(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m 'one, two' -- a.py",
                  "--command", PUSH)
        questions = self.shown()["questions"]
        self.assertEqual(len(questions), 2)
        self.assertEqual([q["multiSelect"] for q in questions], [False, False])
        self.assertEqual([[o["label"] for o in q["options"]] for q in questions],
                         [["Not now — commit nothing", "git commit -m 'one, two' -- a.py"],
                          ["Not now — commit nothing", PUSH]])
        plain = DialogProject()
        try:
            plain.ok("decision", "open", "--kind", "commit", "--command", "git commit -m one -- a.py",
                     "--command", PUSH)
            [question] = json.loads(plain.ok("decision", "show", "--json").stdout)["questions"]
            self.assertTrue(question["multiSelect"])
        finally:
            plain.close()

    def test_codex_shape(self):
        decision = {"id": "D3", "question": "q", "header": "Commit", "multi_select": True,
                    "options": [{"n": 1, "kind": "choice", "label": "Not now — commit nothing"},
                                {"n": 2, "kind": "command", "label": "git commit -m 'a, b'"},
                                {"n": 3, "kind": "command", "label": PUSH}]}
        payload = state_mod.dialog_payload([decision], "codex")
        self.assertEqual([q["id"] for q in payload["questions"]], ["d3_1", "d3_2"])
        self.assertTrue(all("multiSelect" not in q for q in payload["questions"]))


def spike(name):
    with open(os.path.join(SPIKE, name + ".json"), encoding="utf-8") as fh:
        return json.load(fh)["payload"]


class Scratch:
    """A project root and a runtime home for the hooks' module: dialog.json on
    or off, a profile whose dialog tool is (or is not) the verified one, and
    decision.json written the way state.py's open_decision writes it."""

    def __init__(self, on=True, tool=True):
        self.tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.root = os.path.join(self.tmp.name, "p")
        self.home = os.path.join(self.tmp.name, "home")
        os.makedirs(os.path.join(self.root, ".ai", "policies"))
        os.makedirs(os.path.join(self.root, ".ai", "state"))
        if on:
            self.write(".ai/policies/dialog.json", {"version": 1, "enabled": True, "window_seconds": 120,
                                                    "stop_blocks_max": 2})
        for runtime, home in (("claude", self.home), ("codex", self.home + "-codex")):
            os.makedirs(os.path.join(home, "riskrails"))
            with open(os.path.join(home, "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
                json.dump({"plan": "max", "dialog": {"tool": dialog.DIALOG_TOOL[runtime] if tool else None}}, fh)
        self.vars = {"CLAUDE_CONFIG_DIR": self.home, "CODEX_HOME": self.home + "-codex",
                     "AI_UNATTENDED": "", "CLAUDE_CODE_SESSION_ATTENDED": "1"}
        self.env = mock.patch.dict(os.environ, self.vars)
        self.env.start()

    def close(self):
        self.env.stop()
        self.tmp.cleanup()

    def write(self, rel, data):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            json.dump(data, fh)

    def decide(self, *decisions):
        self.write(".ai/state/decision.json", {"version": 1, "open": list(decisions)})

    def ledger(self):
        path = dialog.ledger_path(self.root)
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line) for line in fh]


def decision(did, question, header, options, multi=False):
    """options: [(kind, label)] in offered order, numbered from 1."""
    return {"id": did, "kind": "commit", "question": question, "header": header, "multi_select": multi,
            "options": [{"n": n, "kind": kind, "label": label} for n, (kind, label) in enumerate(options, 1)]}


def relabel(payload, mapping, question, header, qid=None):
    """A recorded 7.0 payload with its question, header and labels renamed to
    a decision's: the harness's shape stays as recorded, the words become ours."""
    payload = json.loads(json.dumps(payload))
    tool_response = payload.get("tool_response")
    codex = isinstance(tool_response, str)
    for holder in [payload["tool_input"]] + ([] if codex else [tool_response]):
        q = holder["questions"][0]
        old = q["question"]
        q["question"], q["header"] = question, header
        for option in q["options"]:
            option["label"] = mapping.get(option["label"], option["label"])
            # What state.py's dialog_payload sends: SAFE is the choice, the rest commands.
            option["description"] = "nothing runs" if option["label"] == SAFE else "the session runs exactly this, once"
        if qid is not None:
            q["id"] = qid
        if "answers" in holder:
            answer = holder["answers"].pop(old)
            holder["answers"][question] = ", ".join(mapping.get(i, i) for i in answer.split(", "))
    if codex:
        [(old, entry)] = json.loads(tool_response)["answers"].items()
        entry["answers"] = [mapping.get(i, i) for i in entry["answers"]]
        payload["tool_response"] = json.dumps({"answers": {qid or old: entry}})
    return payload


def answer(payload, *items):
    """The same payload with the human's answer to its one question replaced."""
    payload = json.loads(json.dumps(payload))
    if isinstance(payload["tool_response"], str):
        [(qid, entry)] = json.loads(payload["tool_response"])["answers"].items()
        payload["tool_response"] = json.dumps({"answers": {qid: dict(entry, answers=list(items))}})
        return payload
    for holder in (payload["tool_input"], payload["tool_response"]):
        holder["answers"] = {holder["questions"][0]["question"]: ", ".join(items)} if items else {}
    return payload


def commit_payload(name="claude/ask-single", qid=None):
    """A recorded single-select renamed to the commit decision, the commit picked."""
    payload = relabel(spike(name), {"A": SAFE, "B": COMMIT}, "Commit a.py?", "Commit", qid)
    return answer(payload, COMMIT)


def run_gate(scratch, payload, env=None):
    """hooks/dialog-gate.py as a runtime runs it, in the scratch project."""
    payload = json.loads(json.dumps(payload).replace("__ROOT__", scratch.root))
    full = dict(os.environ)
    full.update(scratch.vars)
    full.update(env or {})
    proc = subprocess.run(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "dialog-gate.py")],
                          input=json.dumps(payload), capture_output=True, text=True, env=full, check=False,
                          cwd=scratch.root)
    return proc.returncode, proc.stdout + proc.stderr


class HookCase(unittest.TestCase):
    def setUp(self):
        self.s = Scratch()

    def tearDown(self):
        self.s.close()


class TestEffectiveSwitch(HookCase):
    """R36.1: on only when enabled, the tool is the verified one, AI_UNATTENDED
    is unset, the payload is the main session's and it has a session id."""

    def test_effective_switch_matrix(self):
        main, sub = spike("claude/ask-single"), spike("claude/subagent-pretooluse")
        for enabled, tool, unattended, subagent, no_session in itertools.product((True, False), repeat=5):
            with self.subTest(enabled=enabled, tool=tool, unattended=unattended, subagent=subagent,
                              no_session=no_session):
                s = Scratch(on=enabled, tool=tool)
                try:
                    payload = dict(sub if subagent else main)
                    if no_session:
                        payload.pop("session_id")
                    with mock.patch.dict(os.environ, {"AI_UNATTENDED": "1" if unattended else ""}):
                        got = dialog.effective_switch(s.root, "claude", payload)
                finally:
                    s.close()
                self.assertEqual(got, enabled and tool and not unattended and not subagent and not no_session)

    def test_runtime_unattended_marker_is_off(self):
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ATTENDED": "0"}):
            self.assertFalse(dialog.effective_switch(self.s.root, "claude", spike("claude/ask-single")))

    def test_codex_needs_its_own_verified_tool(self):
        payload = spike("codex/request-single")
        self.assertTrue(dialog.effective_switch(self.s.root, "codex", payload))
        with open(os.path.join(self.s.home + "-codex", "riskrails", "profile.json"), "w", encoding="utf-8") as fh:
            json.dump({"dialog": {"tool": None}}, fh)
        self.assertFalse(dialog.effective_switch(self.s.root, "codex", payload))

    def test_payload_runtime(self):
        self.assertEqual(dialog.payload_runtime(spike("codex/posttooluse"), "/x/hooks/dialog-gate.py"), "codex")
        self.assertEqual(dialog.payload_runtime(spike("claude/stop"), "/x/.codex/hooks/dialog-gate.py"), "claude")
        self.assertEqual(dialog.payload_runtime({}, "/h/.codex/hooks/dialog-gate.py"), "codex")


class TestRecorder(HookCase):
    """R36.6: the answers come from tool_response; an exact label is a pick,
    anything else a decline whose text is not stored."""

    def commit_decision(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))

    def multi_decision(self, first="git commit -m x -- a.py"):
        self.s.decide(decision("D2", "Commit and push?", "Commit",
                               [("choice", SAFE), ("command", first), ("command", PUSH)], multi=True))

    def test_pick_from_tool_response(self):
        self.commit_decision()
        payload = commit_payload()
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([line["type"] for line in lines], ["offer", "pick"])
        pick = lines[1]
        self.assertEqual((pick["id"], pick["decision"], pick["option"], pick["order"], pick["label"]),
                         ("C1", "D1", 2, 1, COMMIT))
        self.assertEqual((pick["session"], pick["tool_use_id"]), (payload["session_id"], payload["tool_use_id"]))
        self.assertEqual((pick["at"], pick["expires_at"]), ("2026-10-28T12:00:00Z", "2026-10-28T12:02:00Z"))
        self.assertEqual(self.s.ledger(), [dict({"v": 1}, **line) for line in lines])

    def test_multi_select_picks_in_offered_order(self):
        self.multi_decision()
        payload = relabel(spike("claude/ask-multi"), {"A": SAFE, "B": "git commit -m x -- a.py", "C": PUSH},
                          "Commit and push?", "Commit")
        payload["tool_response"]["answers"]["Commit and push?"] = "%s, %s" % (PUSH, "git commit -m x -- a.py")
        picks = [line for line in dialog.record(self.s.root, "claude", payload, NOW) if line["type"] == "pick"]
        self.assertEqual([(p["id"], p["order"], p["option"], p["label"]) for p in picks],
                         [("C1", 1, 2, "git commit -m x -- a.py"), ("C2", 2, 3, PUSH)])
        self.assertEqual(dialog.next_live_pick(self.s.root, payload["session_id"], NOW)["id"], "C1")

    def test_choice_only_is_one_pick(self):
        self.commit_decision()
        payload = relabel(spike("claude/ask-single"), {"A": SAFE, "B": COMMIT}, "Commit a.py?", "Commit")
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("option")) for line in lines], [("offer", None), ("pick", 1)])

    def test_choice_with_commands_is_ambiguous(self):
        self.multi_decision()
        payload = relabel(spike("claude/ask-multi"), {"A": SAFE, "B": "git commit -m x -- a.py", "C": PUSH},
                          "Commit and push?", "Commit")
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("why")) for line in lines],
                         [("offer", None), ("decline", "ambiguous")])

    def test_other_text_is_decline(self):
        self.multi_decision()
        payload = relabel(spike("claude/ask-other"), {"A": SAFE, "B": "git commit -m x -- a.py", "C": PUSH},
                          "Commit and push?", "Commit")
        payload["tool_response"]["answers"]["Commit and push?"] = "git commit -m x -- a.py, secret words here"
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("why")) for line in lines],
                         [("offer", None), ("decline", "other text")])
        self.assertNotIn("secret words", json.dumps(self.s.ledger()))
        recorded = relabel(spike("claude/ask-other"), {"A": SAFE, "B": "git commit -m x -- a.py", "C": PUSH},
                           "Commit and push?", "Commit")
        self.assertEqual([line["type"] for line in dialog.record(self.s.root, "claude", recorded, NOW)],
                         ["offer", "decline"])

    def test_esc_is_decline(self):
        """Esc: only the PreToolUse fires (7.0), so nothing consents and the
        decision stays open until its window; a PreToolUse writes nothing."""
        self.s.decide(decision("D1", "Pick one?", "Single", [("choice", "A"), ("choice", "B")]))
        payload = spike("claude/ask-esc")
        self.assertEqual(payload["hook_event_name"], "PreToolUse")
        self.assertEqual(run_gate(self.s, payload), (0, ""))
        self.assertEqual(self.s.ledger(), [])
        self.assertIsNone(dialog.next_live_pick(self.s.root, payload["session_id"], NOW))

    def test_empty_answer_is_decline(self):
        self.commit_decision()
        payload = answer(commit_payload())
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("why")) for line in lines],
                         [("offer", None), ("decline", "no answer")])

    def test_free_dialog_never_consents(self):
        """A dialog the model wrote itself, not equal to an open decision,
        records nothing, even when an option is a command label."""
        self.assertEqual(dialog.record(self.s.root, "claude", commit_payload(), NOW), [])
        self.commit_decision()
        reworded = answer(relabel(spike("claude/ask-single"), {"A": SAFE, "B": COMMIT}, "Commit a.py now?",
                                  "Commit"), COMMIT)
        self.assertEqual(dialog.record(self.s.root, "claude", reworded, NOW), [])
        reordered = relabel(spike("claude/ask-single"), {"A": COMMIT, "B": SAFE}, "Commit a.py?", "Commit")
        self.assertEqual(dialog.record(self.s.root, "claude", reordered, NOW), [])
        self.assertEqual(self.s.ledger(), [])

    def test_codex_adapter_fixture(self):
        """R36.19: Codex's string tool_response maps to the same shape;
        "None of the above" and "user_note: …" are a decline."""
        self.commit_decision()
        payload = commit_payload("codex/request-single", "d1")
        self.assertEqual(dialog.adapt_response("codex", payload), [[COMMIT]])
        lines = dialog.record(self.s.root, "codex", payload, NOW)
        self.assertEqual([(line["type"], line.get("label"), line.get("runtime")) for line in lines],
                         [("offer", None, None), ("pick", COMMIT, "codex")])
        other = relabel(spike("codex/request-other"), {"A": SAFE, "B": COMMIT}, "Commit a.py?", "Commit", "d1")
        self.assertEqual(dialog.adapt_response("codex", other),
                         [["None of the above", "user_note: Some text to test"]])
        self.assertEqual([line["type"] for line in dialog.record(self.s.root, "codex", other, NOW)],
                         ["offer", "decline"])
        self.assertNotIn("Some text", json.dumps(self.s.ledger()))

    def test_duplicate_question_text_is_ambiguous(self):
        """7c splits a multi-select whose label holds ", " into single-selects
        sharing the decision's question text; Claude keys answers by that
        text, so neither answer can be told apart: a decline."""
        self.multi_decision(first="git commit -m 'a, b' -- a.py")
        sent = dialog.dialog_payload(dialog.read_decisions(self.s.root), "claude")
        self.assertEqual(len(sent["questions"]), 2)
        payload = dict(spike("claude/ask-single"), tool_input=dict(sent),
                       tool_response=dict(sent, answers={"Commit and push?": PUSH}))
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("why")) for line in lines],
                         [("offer", None), ("decline", "ambiguous")])

    def test_label_rule_checked_again(self):
        self.s.decide(decision("D1", "Run?", "Run", [("choice", SAFE), ("command", "git status")]))
        payload = answer(relabel(spike("claude/ask-single"), {"A": SAFE, "B": "git status"}, "Run?", "Run"),
                         "git status")
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("why")) for line in lines], [("offer", None), ("decline", "label")])

    def test_misleading_description_records_nothing(self):
        """Review L3 of T-2026-10-28-009: the descriptions the human read are
        part of the question; a dialog whose descriptions differ from the
        prepared ones is not the decision's dialog."""
        self.commit_decision()
        payload = commit_payload()
        for holder in (payload["tool_input"], payload["tool_response"]):
            holder["questions"][0]["options"][1]["description"] = "CANCEL - nothing runs"
        self.assertEqual(dialog.record(self.s.root, "claude", payload, NOW), [])
        self.assertEqual(self.s.ledger(), [])

    def test_round_without_call_id_or_transcript_writes_nothing(self):
        """Review L2: a payload with no tool_use_id would merge with another
        round; none with no transcript could be audited."""
        self.commit_decision()
        for key in ("tool_use_id", "transcript_path"):
            with self.subTest(missing=key):
                self.assertEqual(dialog.record(self.s.root, "claude", dict(commit_payload(), **{key: ""}), NOW), [])
        self.assertEqual(self.s.ledger(), [])

    def test_round_lands_whole_or_not_at_all(self):
        """Review L4: a line over the limit refuses the round before its first write."""
        self.multi_decision()
        payload = relabel(spike("claude/ask-multi"), {"A": SAFE, "B": "git commit -m x -- a.py", "C": PUSH},
                          "Commit and push?", "Commit")
        payload = answer(payload, "git commit -m x -- a.py", PUSH)
        offer = len(dialog.encode_line({"type": "offer", "decisions": ["D2"], "session": payload["session_id"],
                                        "tool_use_id": payload["tool_use_id"]}))
        with mock.patch.object(dialog, "LINE_MAX", offer + 10), self.assertRaises(OSError):
            dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual(self.s.ledger(), [])

    def test_state_py_label_by_form_on_every_route(self):
        """Review M2: on the plugin route the hooks live in the plugin cache and
        the skills' state.py in <home>; the hook checks the form, state.py the path."""
        for script in (os.path.abspath(STATE), "/home/u/.claude/skills/ai-task/state.py",
                       "/home/u/.codex/skills/ai-task/state.py"):
            with self.subTest(script=script):
                self.assertIsNone(dialog.validate_label("python3 %s --root /p approve --by me" % script))
        for label in ("python3 /home/u/x/notstate.py approve --by me", "/usr/bin/python3 /h/state.py approve --by me",
                      "python3 -X /h/state.py approve --by me", "python3 /h/state.py close"):
            with self.subTest(label=label):
                self.assertIsNotNone(dialog.validate_label(label))

    def test_label_rule_matches_state_py(self):
        here = os.path.abspath(STATE)
        for label in ["git commit -m 'fix' -- a.py", PUSH, "git push origin +feat", "git push origin HEAD:main",
                      # another state.py's path: the hook checks the form only, state.py the path (M2)
                      "python3 %s --root /p approve --by me" % here,
                      "python3 -I %s --root /p verify --scope all --by me" % here,
                      "python3 %s --root /p close" % here, "npx riskrails@3.1.0 --target claude --yes",
                      "npx other@1.0.0 --yes", "git commit -m x; ls", "git status", " git commit",
                      "git commit -m 'x" + "y" * 400 + "'",
                      # review L1: ASCII only, as state.py's patterns
                      "git push origin mäin", "git push origin ma٣in", "npx riskrails@１.0 --yes"]:
            with self.subTest(label=label):
                self.assertEqual(dialog.validate_label(label) is None, state_mod.validate_label(label) is None)


def prompt(scratch):
    """A human turn: context-guard.py's UserPromptSubmit counts it in session.json."""
    subprocess.run([os.path.join(ROOT, "hooks", "context-guard.py")], check=False, capture_output=True, text=True,
                   input=json.dumps({"hook_event_name": "UserPromptSubmit", "session_id": "s", "cwd": scratch.root,
                                     "prompt": "go on"}),
                   env=dict(os.environ, **scratch.vars), cwd=scratch.root)


class TestGateHook(HookCase):
    """hooks/dialog-gate.py: the recorder end to end, and Stop (R36.13)."""

    def stop(self, active=False, **env):
        code, out = run_gate(self.s, dict(spike("claude/stop"), stop_hook_active=active), env)
        self.assertEqual(code, 0)
        return hook_output(out)

    def test_stop_blocks_twice_then_releases(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        prompt(self.s)
        with open(os.path.join(self.s.root, ".ai", "state", "session.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["prompt_count"], 1, "an open decision counts turns without a task")
        for active in (False, True):
            out = self.stop(active)
            self.assertEqual(out.get("decision"), "block", out)
            self.assertTrue(out["reason"].startswith("DECISION_PENDING D1 — call AskUserQuestion"), out)
            sent = json.loads(out["reason"].split(": ", 1)[1])
            self.assertEqual(sent, dialog.dialog_payload(dialog.read_decisions(self.s.root), "claude"))
        released = self.stop(True)
        self.assertNotIn("decision", released)
        self.assertIn("decision settle --id D1 --pick", released["systemMessage"])
        prompt(self.s)
        self.assertEqual(self.stop().get("decision"), "block", "a new human turn resets the count")
        self.assertEqual([line["turn"] for line in self.s.ledger()], [1, 1, 2])

    def test_stop_without_a_turn_honours_stop_hook_active(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        self.assertEqual(self.stop().get("decision"), "block")
        self.assertIn("systemMessage", self.stop(True))

    def test_stop_silent_without_a_decision_or_switch(self):
        self.assertEqual(self.stop(), {})
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        os.remove(os.path.join(self.s.root, ".ai", "policies", "dialog.json"))
        self.assertEqual(self.stop(), {})
        self.assertEqual(self.stop(AI_UNATTENDED="1"), {})
        self.assertEqual(self.s.ledger(), [])

    def test_post_tool_use_records_through_the_hook(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        self.assertEqual(run_gate(self.s, commit_payload()), (0, ""))
        self.assertEqual([(line["type"], line.get("label")) for line in self.s.ledger()],
                         [("offer", None), ("pick", COMMIT)])
        subagent = dict(commit_payload(), agent_id="a1", tool_use_id="toolu_sub")
        self.assertEqual(run_gate(self.s, subagent), (0, ""))
        self.assertEqual(len(self.s.ledger()), 2, "a subagent's dialog consents to nothing")

    def test_off_writes_nothing(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        os.remove(os.path.join(self.s.root, ".ai", "policies", "dialog.json"))
        self.assertEqual(run_gate(self.s, commit_payload()), (0, ""))
        self.assertEqual(self.s.ledger(), [])

    def test_never_a_deny_and_fails_open(self):
        for stdin in ("", "not json", "[]", json.dumps(spike("claude/subagent-pretooluse"))):
            proc = subprocess.run(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "dialog-gate.py")],
                                  input=stdin, capture_output=True, text=True, check=False, cwd=self.s.root)
            self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""), stdin)


class TestGateFastPath(HookCase):
    """R36.12: with no decision.json the decision check costs one stat."""

    def guard(self, payload):
        proc = subprocess.run(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "ai-guard.py")],
                              input=json.dumps(payload), capture_output=True, text=True, check=False,
                              cwd=self.s.root)
        return proc.returncode, proc.stdout + proc.stderr

    def grep(self):
        return {"hook_event_name": "PreToolUse", "tool_name": "Grep", "cwd": self.s.root,
                "session_id": "s", "tool_use_id": "toolu_1", "tool_input": {"pattern": "x"}}

    def test_later_checks_still_run(self):
        """The new first check must not end the run: git still denies."""
        payload = dict(self.grep(), tool_name="Bash", tool_input={"command": "git push --force origin main"})
        self.assertEqual(decision_of(self.guard(payload)[1]), "deny")

    def test_broken_decision_module_keeps_the_other_checks(self):
        """Review M1: a half-done install — guard/decision.py missing or not
        importable — must not turn git, paths and scope off."""
        payload = dict(self.grep(), tool_name="Bash", tool_input={"command": "git push --force origin main"})
        for broken in (None, "def check(ctx):\n    return (\n"):
            with self.subTest(broken=broken), tempfile.TemporaryDirectory() as tmp:
                hooks = os.path.join(tmp, "hooks")
                shutil.copytree(os.path.join(ROOT, "hooks"), hooks,
                                ignore=shutil.ignore_patterns("__pycache__"))
                target = os.path.join(hooks, "guard", "decision.py")
                if broken is None:
                    os.remove(target)
                else:
                    with open(target, "w", encoding="utf-8") as fh:
                        fh.write(broken)
                proc = subprocess.run(["python3", "-I", "-S", os.path.join(hooks, "ai-guard.py")],
                                      input=json.dumps(payload), capture_output=True, text=True, check=False,
                                      cwd=self.s.root)
                self.assertEqual(decision_of(proc.stdout), "deny", proc.stdout + proc.stderr)

    def test_gate_fast_path(self):
        """timed: the whole ai-guard.py process on a Grep payload, no decision.json."""
        budget = 0.015 * timed_factor()
        overhead = min(timed(["python3", "-I", "-S", "-c", "pass"], "") for _ in range(5))
        median = sorted(timed(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "ai-guard.py")],
                              json.dumps(self.grep()), self.s.root) for _ in range(5))[2]
        self.assertLessEqual(median - overhead, budget, "%.1f ms over the interpreter's start" %
                             ((median - overhead) * 1000))


class TestDecisionGate(HookCase):
    """R36.5, R36.7, R36.8, R36.12, R36.15 (hook half): hooks/ai-guard.py while
    a decision is open, end to end."""

    SESSION = "sess-main"
    STATE = "python3 /p/skills/ai-task/state.py"

    def setUp(self):
        super().setUp()
        self.n = 0

    def open(self, *commands, **extra):
        self.s.decide(dict(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE)] +
                                    [("command", c) for c in commands], multi=len(commands) > 1), **extra))

    def append(self, line):
        with dialog.ledger_lock(self.s.root):
            dialog.ledger_append(self.s.root, line)

    def pick(self, label, option=2, order=1, session=None, age=5, tool_use_id="toolu_dialog"):
        self.n += 1
        at = datetime.now(timezone.utc).replace(microsecond=0) - timedelta(seconds=age)
        self.append({"type": "pick", "id": "C%d" % self.n, "decision": "D1", "option": option, "order": order,
                     "label": label, "session": session or self.SESSION, "tool_use_id": tool_use_id,
                     "transcript": "t.jsonl", "runtime": "claude", "at": dialog.stamp(at),
                     "expires_at": dialog.stamp(at + timedelta(seconds=120))})

    def guard(self, command=None, tool="Bash", tool_input=None, hooks=ROOT, **extra):
        payload = dict({"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": self.s.root,
                        "session_id": self.SESSION, "prompt_id": "p1", "transcript_path": "t.jsonl",
                        "tool_use_id": "toolu_run",
                        "tool_input": tool_input if tool_input is not None else {"command": command}}, **extra)
        proc = subprocess.run(["python3", "-I", "-S", os.path.join(hooks, "hooks", "ai-guard.py")],
                              input=json.dumps(payload), capture_output=True, text=True, check=False,
                              cwd=self.s.root)
        out = proc.stdout
        reason = json.loads(out)["hookSpecificOutput"]["permissionDecisionReason"] if out else ""
        return decision_of(out), reason

    def sent(self):
        return dialog.dialog_payload(dialog.read_decisions(self.s.root), "claude")

    def types(self):
        return [line["type"] for line in self.s.ledger()]

    def test_gate_denies_all_but_three(self):
        self.open(COMMIT)
        expected = json.dumps(self.sent(), ensure_ascii=False)
        for tool, tool_input in (("Grep", {"pattern": "x"}), ("Read", {"file_path": "a.py"}),
                                 ("Bash", {"command": "ls"}), ("Write", {"file_path": "a.py", "content": ""}),
                                 ("mcp__x__y", {})):
            with self.subTest(tool=tool):
                verdict, reason = self.guard(tool=tool, tool_input=tool_input)
                self.assertEqual(verdict, "deny")
                self.assertTrue(reason.startswith("DECISION_PENDING D1"), reason)
                self.assertIn(expected, reason)
        for command in (self.STATE + " decision show", self.STATE + " --root . decision show --json",
                        self.STATE + " decision settle --id D1", '$STATE decision show',
                        self.STATE + " decision fallback --id D1 --why 'the dialog is not available'"):
            with self.subTest(command=command):
                self.assertEqual(self.guard(command), ("allow", ""))
        for command in (self.STATE + " decision show; ls", self.STATE + " decision open --kind commit"):
            with self.subTest(command=command):
                self.assertEqual(self.guard(command)[0], "deny")
        self.assertEqual(self.guard(tool="AskUserQuestion", tool_input=self.sent()), ("allow", ""))
        self.pick(COMMIT)
        self.assertEqual(self.guard(COMMIT), ("allow", ""))

    def test_dialog_input_must_match(self):
        self.open(COMMIT)
        changed = self.sent()
        changed["questions"][0]["options"][1]["description"] = "nothing runs"
        verdict, reason = self.guard(tool="AskUserQuestion", tool_input=changed)
        self.assertEqual(verdict, "deny")
        self.assertIn(json.dumps(self.sent(), ensure_ascii=False), reason)
        self.assertEqual(self.s.ledger(), [], "a refused dialog call is no offer")
        self.assertEqual(self.guard(tool="AskUserQuestion", tool_input=self.sent()), ("allow", ""))
        self.assertEqual([(e["type"], e.get("decisions"), e.get("tool_use_id")) for e in self.s.ledger()],
                         [("offer", ["D1"], "toolu_run")])

    def test_gate_skips_subagent(self):
        """Review focus 3: a subagent cannot answer a dialog; the gate does not
        stop its tools."""
        self.open(COMMIT)
        self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}, agent_id="a1"), ("allow", ""))

    def test_gate_is_the_opening_sessions(self):
        """A decision another session or runtime opened does not stop this one."""
        for extra in ({"session": "another"}, {"runtime": "codex"}):
            with self.subTest(extra=extra):
                self.open(COMMIT, **extra)
                self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}), ("allow", ""))
        self.open(COMMIT, session=self.SESSION, runtime="claude")
        self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"})[0], "deny")

    def test_once(self):
        self.open(COMMIT)
        self.pick(COMMIT)
        self.assertEqual(self.guard(COMMIT), ("allow", ""))
        self.assertEqual(self.types(), ["pick", "use"])
        verdict, reason = self.guard(COMMIT)
        self.assertEqual(verdict, "deny")
        self.assertIn("CONSENT_REQUIRED", reason)

    def test_window_and_chain(self):
        self.open(COMMIT, PUSH)
        self.pick(COMMIT, 2, 1)
        self.pick(PUSH, 3, 2)
        self.assertEqual(self.guard(COMMIT), ("allow", ""))
        self.assertEqual(self.guard(PUSH), ("allow", ""))
        self.assertEqual(self.types(), ["pick", "pick", "use", "use"])
        self.open(COMMIT)
        self.pick(COMMIT, age=200, tool_use_id="toolu_late")
        self.assertEqual(self.guard(COMMIT)[0], "deny", "a pick past its window is no pick")

    def test_other_session(self):
        self.open(COMMIT)
        self.pick(COMMIT, session="another")
        verdict, reason = self.guard(COMMIT)
        self.assertEqual(verdict, "deny")
        self.assertTrue(reason.startswith("DECISION_PENDING D1"), reason)

    def test_order(self):
        self.open(COMMIT, PUSH)
        self.pick(COMMIT, 2, 1)
        self.pick(PUSH, 3, 2)
        verdict, reason = self.guard(PUSH)
        self.assertEqual(verdict, "deny")
        self.assertTrue(reason.startswith("CONSENT_MISMATCH"), reason)
        self.assertIn(COMMIT, reason)
        self.assertIn(PUSH, reason)

    def test_mismatch_voids_all_picks(self):
        self.open(COMMIT, PUSH)
        self.pick(COMMIT, 2, 1)
        self.pick(PUSH, 3, 2)
        verdict, reason = self.guard("git commit -m other -- b.py")
        self.assertEqual(verdict, "deny")
        self.assertTrue(reason.startswith("CONSENT_MISMATCH"), reason)
        self.assertEqual(self.s.ledger()[-1]["type"], "void")
        self.assertEqual(self.s.ledger()[-1]["ids"], ["C1", "C2"])
        self.assertTrue(self.guard(COMMIT)[1].startswith("DECISION_PENDING D1"), "the decision reopens")

    def test_offer_without_pick_falls_back(self):
        """R36.15: an offer neither picked nor declined by the next PreToolUse
        means the recorder did not run; the decision falls back to the terminal."""
        self.open(COMMIT)
        self.append({"type": "offer", "decisions": ["D1"], "session": self.SESSION, "tool_use_id": "toolu_old"})
        verdict, reason = self.guard(tool="Grep", tool_input={"pattern": "x"})
        self.assertEqual(verdict, "deny")
        self.assertTrue(reason.startswith("DECISION_FALLBACK D1"), reason)
        self.assertIn(COMMIT, reason)
        self.assertEqual(dialog.read_decisions(self.s.root), [])
        self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}), ("allow", ""))

    def test_failed_fallback_fails_open(self):
        """Review M2: a fallback state.py cannot run is the gate's own error —
        it allows, and the way out (decision show|settle|fallback) stays open."""
        self.open(COMMIT)
        self.append({"type": "offer", "decisions": ["D1"], "session": self.SESSION, "tool_use_id": "toolu_old"})
        self.assertEqual(self.guard(self.STATE + " decision fallback --id D1 --why x"), ("allow", ""))
        with tempfile.TemporaryDirectory() as plugin:
            # A plugin root with the hooks and no skills/ai-task/state.py.
            shutil.copytree(os.path.join(ROOT, "hooks"), os.path.join(plugin, "hooks"),
                            ignore=shutil.ignore_patterns("__pycache__"))
            self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}, hooks=plugin), ("allow", ""))
        self.assertEqual(len(dialog.read_decisions(self.s.root)), 1, "nothing settled it")

    def test_dialog_call_carries_nothing_else(self):
        """Review L1: a title or pre-filled answers beside the prepared questions
        is not the prepared call."""
        self.open(COMMIT)
        for extra in ({"title": "Safety check: the second option CANCELS the commit"},
                      {"answers": {"Commit a.py?": COMMIT}}, {"annotations": {}}):
            with self.subTest(extra=extra):
                self.assertEqual(self.guard(tool="AskUserQuestion", tool_input=dict(self.sent(), **extra))[0],
                                 "deny")
        self.assertEqual(self.s.ledger(), [])

    def test_answered_offer_does_not_fall_back(self):
        self.open(COMMIT)
        self.append({"type": "offer", "decisions": ["D1"], "session": self.SESSION, "tool_use_id": "toolu_dialog"})
        self.pick(COMMIT)
        self.assertTrue(self.guard(tool="Grep", tool_input={"pattern": "x"})[1].startswith("DECISION_PENDING"))
        self.assertEqual(len(dialog.read_decisions(self.s.root)), 1)

    def test_denied_after_use_settles_and_explains(self):
        """Review focus 1: a picked command another git rule denies has spent
        its pick; the deny says so and how to ask again."""
        picked = "git commit --no-verify -m x"
        self.open(picked)
        self.pick(picked)
        verdict, reason = self.guard(picked)
        self.assertEqual(verdict, "deny")
        self.assertIn("--no-verify", reason)
        self.assertIn("C1 was used", reason)
        self.assertIn("decision open", reason)
        self.assertEqual(self.types(), ["pick", "use"])

    def test_gate_fails_open_on_error(self):
        for text in ("not json", '{"open": "x"}', '{"open": [{"id": "D1", "options": 3}]}'):
            with self.subTest(text=text):
                with open(os.path.join(self.s.root, ".ai", "state", "decision.json"), "w", encoding="utf-8") as fh:
                    fh.write(text)
                self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}), ("allow", ""))

    def test_off_is_today(self):
        self.open(COMMIT)
        os.remove(os.path.join(self.s.root, ".ai", "policies", "dialog.json"))
        self.assertEqual(self.guard(tool="Grep", tool_input={"pattern": "x"}), ("allow", ""))
        self.assertEqual(self.guard(COMMIT), ("allow", ""))

    def test_stop_is_the_opening_sessions(self):
        """Q1 of T-2026-10-28-010: Stop blocks only the session that opened it."""
        stop = spike("claude/stop")
        self.open(COMMIT, session="another")
        self.assertEqual(hook_output(run_gate(self.s, stop)[1]), {})
        self.open(COMMIT, session=stop["session_id"])
        self.assertEqual(hook_output(run_gate(self.s, stop)[1]).get("decision"), "block")


class TestRegistrations(unittest.TestCase):
    """7d1 step 3: every registration lands in both routes' sources and both
    plugin files, the same apart from where the hooks live."""

    ROUTES = {"claude": ("settings.common.json", "hooks/hooks.json", "*", "AskUserQuestion"),
              "codex": ("codex/hooks.json", "hooks/codex-hooks.json", ".*", "^request_user_input$")}

    @staticmethod
    def entries(path, script):
        with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
            hooks = json.load(fh)["hooks"]
        return sorted((event, group.get("matcher"), hook.get("timeout"),
                       re.sub(r"^python3 -I -S \"[^\"]*/hooks/", "", hook["command"]))
                      for event, groups in hooks.items() for group in groups for hook in group["hooks"]
                      if hook["command"].endswith("/hooks/%s\"" % script))

    def test_registrations_equal_in_both_routes(self):
        for runtime, (npx, plugin, star, tool) in self.ROUTES.items():
            with self.subTest(runtime=runtime):
                gate = self.entries(npx, "dialog-gate.py")
                self.assertEqual(gate, [("PostToolUse", tool, 5, 'dialog-gate.py"'),
                                        ("Stop", None, 5, 'dialog-gate.py"')])
                self.assertEqual(self.entries(plugin, "dialog-gate.py"), gate)
                guard = self.entries(npx, "ai-guard.py")
                self.assertEqual(guard, [("PreToolUse", star, 15, 'ai-guard.py"')])
                self.assertEqual(self.entries(plugin, "ai-guard.py"), guard)

    def test_no_ask_timeout_in_the_sources(self):
        for path in ("settings.common.json", "hooks/hooks.json"):
            with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
                self.assertNotIn("askUserQuestionTimeout", fh.read(), path)


def timed(command, stdin, cwd=None):
    started = time.perf_counter()
    subprocess.run(command, input=stdin, capture_output=True, text=True, check=False, cwd=cwd)
    return time.perf_counter() - started


def timed_factor():
    try:
        return float(os.environ.get("AI_TIMED_FACTOR") or 1)
    except ValueError:
        return 1.0


class TestPayloadFields(unittest.TestCase):
    def test_session_fields_read_or_empty(self):
        from guard import common  # pylint: disable=import-outside-toplevel
        recorded = spike("claude/subagent-pretooluse")
        for raw in (json.dumps(recorded), json.dumps(recorded) + "\n{}"):     # the plain and the stream route
            payload = common.Payload(raw.encode("utf-8"), "/")
            self.assertEqual([common.b_to_u(getattr(payload, f)) for f in ("session_id", "transcript_path",
                                                                           "tool_use_id")],
                             [recorded["session_id"], recorded["transcript_path"], recorded["tool_use_id"]])
        bare = common.Payload(b'{"tool_name":"Grep","cwd":"/","hook_event_name":"PreToolUse"}', "/")
        self.assertEqual([common.b_to_u(getattr(bare, f)) for f in ("session_id", "transcript_path", "tool_use_id")],
                         ["", "", ""])


class TestLedger(HookCase):
    def lock(self, age):
        path = os.path.join(self.s.root, ".ai", "state", "consent.lock")
        with open(path, "w", encoding="utf-8"):
            pass
        os.utime(path, (time.time() - age, time.time() - age))
        return path

    def test_stale_lock_taken_over(self):
        lock = self.lock(dialog.LOCK_STALE_S + 1)
        started = time.time()
        with dialog.ledger_lock(self.s.root):
            dialog.ledger_append(self.s.root, {"type": "void", "ids": ["C1"]})
        self.assertLess(time.time() - started, dialog.LOCK_STALE_S)
        self.assertEqual([line["type"] for line in self.s.ledger()], ["void"])
        self.assertFalse(os.path.exists(lock))

    def test_fresh_lock_is_waited_for(self):
        """A live writer's lock is not taken until it is LOCK_STALE_S old."""
        self.lock(0)
        started = time.time()
        with mock.patch.object(dialog, "LOCK_STALE_S", 0.3):
            with dialog.ledger_lock(self.s.root):
                waited = time.time() - started
        self.assertGreaterEqual(waited, 0.3)

    def test_line_over_4096_refused(self):
        with dialog.ledger_lock(self.s.root):
            with self.assertRaises(OSError):
                dialog.ledger_append(self.s.root, {"type": "void", "ids": ["C%d" % i for i in range(1000)]})
            dialog.ledger_append(self.s.root, {"type": "void", "ids": ["C1"]})
        self.assertEqual([line["ids"] for line in self.s.ledger()], [["C1"]])

    def test_pick_ids_continue_the_ledger(self):
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        payload = commit_payload()
        dialog.record(self.s.root, "claude", payload, NOW)
        later = NOW + timedelta(seconds=5)
        lines = dialog.record(self.s.root, "claude", dict(payload, tool_use_id="toolu_second"), later)
        self.assertEqual([line["id"] for line in lines if line["type"] == "pick"], ["C2"])
        self.assertEqual(dialog.next_live_pick(self.s.root, payload["session_id"], later)["id"], "C2")


if __name__ == "__main__":
    unittest.main()
