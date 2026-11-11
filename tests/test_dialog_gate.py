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
import types
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "dialog", "payload-golden")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
sys.path.insert(0, os.path.join(ROOT, "hooks"))
from guard import dialog  # noqa: E402  pylint: disable=wrong-import-position
import state  # noqa: E402,F401  pylint: disable=wrong-import-position,unused-import  # sets rr_state.fs.ENTRY
from rr_state import dialog as rr_dialog, dialog_cmd as rr_dialog_cmd, labels as rr_labels  # noqa: E402  pylint: disable=wrong-import-position
from test_ai_task_state import CLEAN, DIALOG_SESSION, STATE, DialogProject  # noqa: E402  pylint: disable=wrong-import-position
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
        text = re.sub(r"T-\d{4}-\d{2}-\d{2}-(?:\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*|\d{3})", "<TASK>", text)
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
            commands = [o for o in question["options"][1:] if rr_labels.validate_label(o["label"]) is None]
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
        # R13: `memory enable` with --author, --period, --index each at most once, two words each, in any
        # order — and no other memory verb
        memory = "python3 %s --root /p memory" % here
        good += [memory + " enable" + tail for tail in (
            "", " --author ivan", " --author 'Ivan Kakurov'", " --period month", " --period quarter", " --period year",
            " --index none", " --index sqlite", " --author ivan --period quarter --index sqlite",
            " --index sqlite --period year --author ivan")]
        good.append("python3 -I %s --runtime claude --root /p memory enable --period year" % here)
        bad += [memory + tail for tail in (
            # every other verb, and what only looks like the verb
            "", " disable", " cleanup", " pack", " redact", " migrate --apply", " status", " export", " show T-1",
            " verify", " search x", " risk add", " risks", " enabled", " Enable", " --author ivan enable",
            # a missing value, the `=` form, a repeated option, an unknown one (an argparse abbreviation too)
            " enable --author", " enable --period", " enable --index", " enable --author ivan --period",
            " enable --author=ivan", " enable --period=quarter", " enable --index=sqlite",
            " enable --author ivan --author bob", " enable --period month --period year",
            " enable --period quarter --period quarter", " enable --index none --index sqlite",
            " enable --force", " enable --apply", " enable --confirm-delete ivan", " enable --help", " enable -h",
            " enable --json", " enable --auth ivan", " enable --per quarter", " enable --ind sqlite",
            " enable --root /q", " enable --runtime claude", " enable --by me",
            # a positional extra
            " enable now", " enable --author ivan now", " enable now --author ivan", " enable -- --author ivan",
            " enable --author ivan --period quarter --index sqlite extra",
            # a value of the wrong kind
            " enable --period week", " enable --period Quarter", " enable --period ''", " enable --period quarter,year",
            " enable --index fts", " enable --index SQLITE", " enable --index ''", " enable --index sqlite3",
            " enable --author -ivan", " enable --author -1", " enable --author ''", " enable --author --index",
            " enable --author --period quarter",
            # the one-simple-command rule still holds
            " enable --author ivan; ls", " enable --author $(id)", " enable --author `id`",
            " enable --author ivan && git push origin main", " enable --author ivan | tee x",
            " enable --author ivan > f")]
        bad += ["python3 /tmp/y/state.py --root /p memory enable", "python3 /tmp/other.py memory enable"]
        for label in good:
            with self.subTest(good=label):
                self.assertIsNone(rr_labels.validate_label(label))
        for label in bad:
            with self.subTest(bad=label):
                self.assertIsNotNone(rr_labels.validate_label(label))
        self.assertIn("memory enable", rr_labels.validate_label("git status"))

    def test_commit_opener_stays_git_only(self):
        """R13 widens the label rule, not the opener the model may call: `decision open --kind commit` still
        offers git commit and git push only, so no model-opened decision carries `memory enable`."""
        for verb in ("memory enable --author ivan --period quarter", "approve --by me"):
            label = "python3 %s --root %s %s" % (os.path.abspath(STATE), self.p.root, verb)
            with self.subTest(label=label):
                self.assertIsNone(rr_labels.validate_label(label))
                done = self.p.run("decision", "open", "--kind", "commit", "--command", label)
                self.assertEqual(done.returncode, 6, done.stderr)
                self.assertIn("a commit decision offers git commit and git push only", done.stderr)
        self.assertEqual(self.p.decisions(), [])

    def test_ambiguous_multiselect_splits(self):
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m 'one, two' -- a.py",
                  "--command", PUSH)
        questions = self.shown()["questions"]
        self.assertEqual(len(questions), 2)
        self.assertEqual([q["multiSelect"] for q in questions], [False, False])
        # Claude keys answers by question text: the two parts must differ (8fec).
        self.assertTrue(questions[0]["question"].endswith(" (1 of 2)"), questions[0]["question"])
        self.assertTrue(questions[1]["question"].endswith(" (2 of 2)"), questions[1]["question"])
        self.assertNotEqual(questions[0]["question"], questions[1]["question"])
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

    def test_split_suffix_keeps_question_within_max(self):
        options = [{"n": 1, "kind": "choice", "label": "Not now — commit nothing"},
                   {"n": 2, "kind": "command", "label": "git commit -m 'a, b'"},
                   {"n": 3, "kind": "command", "label": PUSH}]
        long = "x" * rr_dialog.QUESTION_MAX
        long_decision = {"id": "D3", "question": long, "header": "Commit", "multi_select": True, "options": options}
        texts = [q["question"] for q in rr_dialog.dialog_payload([long_decision], "claude")["questions"]]
        self.assertEqual(len(texts), 2)
        self.assertTrue(all(len(t) <= rr_dialog.QUESTION_MAX for t in texts), [len(t) for t in texts])
        self.assertEqual([t[-9:] for t in texts], [" (1 of 2)", " (2 of 2)"])
        self.assertEqual(texts, [q["question"] for _, _, q in dialog.offered([long_decision], "claude")])
        unsplit = dict(long_decision, multi_select=False)
        self.assertEqual(rr_dialog.dialog_payload([unsplit], "claude")["questions"][0]["question"], long)

    def test_part_question_copies_agree(self):
        """R-two-part-question-copies: state.py's part_question and the hook's
        copy send the same text for every length, split or not, on both runtimes."""
        options = [{"n": 1, "kind": "choice", "label": SAFE},
                   {"n": 2, "kind": "command", "label": "git commit -m 'a, b'"},
                   {"n": 3, "kind": "command", "label": PUSH}]
        suffix = len(" (1 of 2)")
        lengths = (0, 1, 80, rr_dialog.QUESTION_MAX - suffix - 1, rr_dialog.QUESTION_MAX - suffix,
                   rr_dialog.QUESTION_MAX - suffix + 1, rr_dialog.QUESTION_MAX - 1,
                   rr_dialog.QUESTION_MAX, rr_dialog.QUESTION_MAX + 1)
        for runtime, multi, length in itertools.product(("claude", "codex"), (True, False), lengths):
            text = "".join("abcdefghij"[i % 10] for i in range(length))
            dec = {"id": "D3", "question": text, "header": "Commit", "multi_select": multi, "options": options}
            with self.subTest(runtime=runtime, multi=multi, length=length):
                theirs = [q["question"] for q in rr_dialog.dialog_payload([dec], runtime)["questions"]]
                ours = [q["question"] for _, _, q in dialog.offered([dec], runtime)]
                self.assertEqual(theirs, ours)
                self.assertEqual(len(theirs), 2 if multi else 1)

    def test_codex_shape(self):
        codex_decision = {"id": "D3", "question": "q", "header": "Commit", "multi_select": True,
                    "options": [{"n": 1, "kind": "choice", "label": "Not now — commit nothing"},
                                {"n": 2, "kind": "command", "label": "git commit -m 'a, b'"},
                                {"n": 3, "kind": "command", "label": PUSH}]}
        payload = rr_dialog.dialog_payload([codex_decision], "codex")
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
        for name in ("CLAUDE_CODE_SESSION_ID", "CODEX_THREAD_ID"):     # deterministic: a test sets them itself
            os.environ.pop(name, None)

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
            picked = holder["answers"].pop(old)
            holder["answers"][question] = ", ".join(mapping.get(i, i) for i in picked.split(", "))
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

    def test_switch_state_matrix(self):
        """off / closed / on, the env-mismatch case included; closed is no dialog."""
        main, sub = spike("claude/ask-single"), spike("claude/subagent-pretooluse")
        own = main["session_id"]
        rows = (("on", {}, main), ("closed", {}, sub), ("closed", {}, dict(main, session_id="")),
                ("closed", {}, {k: v for k, v in main.items() if k != "session_id"}),
                ("closed", {}, [main]), ("on", {"CLAUDE_CODE_SESSION_ID": own}, main),
                ("closed", {"CLAUDE_CODE_SESSION_ID": own + "-other"}, main),
                ("on", {"CLAUDE_CODE_SESSION_ID": ""}, main),
                ("off", {"AI_UNATTENDED": "1"}, sub), ("off", {"CLAUDE_CODE_SESSION_ATTENDED": "0"}, sub))
        for want, env, payload in rows:
            with self.subTest(want=want, env=env):
                with mock.patch.dict(os.environ, env):
                    self.assertEqual(dialog.switch_state(self.s.root, "claude", payload), want)
                    self.assertEqual(dialog.effective_switch(self.s.root, "claude", payload), want == "on")
        self.assertEqual(dialog.switch_state(None, "claude", main), "off")
        self.assertEqual(dialog.SESSION_ENV, {"claude": "CLAUDE_CODE_SESSION_ID", "codex": "CODEX_THREAD_ID"})
        off = Scratch(on=False)
        try:
            self.assertEqual(dialog.switch_state(off.root, "claude", sub), "off")
        finally:
            off.close()
        notool = Scratch(tool=False)
        try:
            self.assertEqual(dialog.switch_state(notool.root, "claude", sub), "off")
        finally:
            notool.close()

    def test_codex_hook_env_has_no_session_variable_to_compare(self):
        payload = spike("codex/request-single")
        with mock.patch.dict(os.environ, {"CLAUDE_CODE_SESSION_ID": "unrelated"}):
            self.assertEqual(dialog.switch_state(self.s.root, "codex", payload), "on")

    def test_scaffolded_project_is_on(self):
        """the matrix row "scaffolded project is on": the template the scaffold and
        migration 0010 write is read by effective_switch as the switch on."""
        s = Scratch(on=False)
        try:
            shutil.copy(os.path.join(ROOT, "skills", "ai-init", "templates", ".ai", "policies", "dialog.json"),
                        os.path.join(s.root, ".ai", "policies", "dialog.json"))
            # the template ships the background-session opt-in off: the project decides
            self.assertEqual(dialog.dialog_policy(s.root),
                             {"window_seconds": 120, "stop_blocks_max": 2, "background_sessions": False})
            self.assertTrue(dialog.effective_switch(s.root, "claude", spike("claude/ask-single")))
        finally:
            s.close()

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


class TestRecorder(HookCase):  # pylint: disable=too-many-public-methods  # one test per case keeps failures named
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

    def test_split_multiselect_parts_are_recorded_per_part(self):
        """8fec: the two single-selects of a split decision carry different
        question texts, so Claude's answers keyed by text read as picks."""
        first = "git commit -m 'x, y' -- a.py"
        split = decision("D2", "Commit and push?", "Commit",
                         [("choice", SAFE), ("command", first), ("command", PUSH)], multi=True)
        self.s.decide(split)
        sent = dialog.dialog_payload([split], "claude")
        questions = sent["questions"]
        self.assertEqual(len(questions), 2)
        payload = json.loads(json.dumps(spike("claude/ask-single")))
        answers = {questions[0]["question"]: first, questions[1]["question"]: PUSH}
        payload["tool_input"] = {"questions": questions, "answers": answers}
        payload["tool_response"] = {"questions": questions, "answers": answers}
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        picks = [line for line in lines if line["type"] == "pick"]
        self.assertEqual([(p["order"], p["option"], p["label"]) for p in picks], [(1, 2, first), (2, 3, PUSH)])
        self.assertEqual([line for line in lines if line["type"] == "decline"], [])

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
        """Two questions with one text (the pre-8fec split shape) cannot be
        told apart by Claude's answers keyed by text: unanswerable, and the
        shared-text set is no longer the offered one, so nothing is picked."""
        self.multi_decision(first="git commit -m 'a, b' -- a.py")
        sent = dialog.dialog_payload(dialog.read_decisions(self.s.root), "claude")
        self.assertEqual(len(sent["questions"]), 2)
        same = {"questions": [dict(q, question="Commit and push?") for q in sent["questions"]]}
        payload = dict(spike("claude/ask-single"), tool_input=dict(same),
                       tool_response=dict(same, answers={"Commit and push?": PUSH}))
        self.assertEqual(dialog.adapt_response("claude", payload), [[""], [""]])
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([line for line in lines if line["type"] == "pick"], [])

    def test_two_decisions_sharing_question_text_decline_ambiguous(self):
        """Two open decisions with one question text but different options are
        both offered; Claude's answers are keyed by text, so neither can be
        told from the other: each is a decline "ambiguous", nothing is picked."""
        other = "git commit -m two -- b.py"
        self.s.decide(decision("D1", "Commit?", "Commit", [("choice", SAFE), ("command", COMMIT)]),
                      decision("D2", "Commit?", "Commit", [("choice", SAFE), ("command", other)]))
        sent = dialog.dialog_payload(dialog.read_decisions(self.s.root), "claude")
        self.assertEqual([q["question"] for q in sent["questions"]], ["Commit?", "Commit?"])
        payload = dict(spike("claude/ask-single"), tool_input=dict(sent),
                       tool_response=dict(sent, answers={"Commit?": COMMIT}))
        self.assertEqual(dialog.adapt_response("claude", payload), [[""], [""]])
        lines = dialog.record(self.s.root, "claude", payload, NOW)
        self.assertEqual([(line["type"], line.get("decision"), line.get("why")) for line in lines],
                         [("offer", None, None), ("decline", "D1", "ambiguous"), ("decline", "D2", "ambiguous")])
        self.assertEqual(lines[0]["decisions"], ["D1", "D2"])
        self.assertEqual([line for line in self.s.ledger() if line["type"] == "pick"], [])

    def test_read_decisions_survives_deep_nesting(self):
        """R-read-decisions-does-not-catch-recursione: a deeply nested
        decision.json is unreadable like a malformed one, not a crash."""
        path = os.path.join(self.s.root, ".ai", "state", "decision.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("[" * 200000)
        self.assertEqual(dialog.read_decisions(self.s.root), [])
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        self.assertEqual(dialog.read_decisions(self.s.root), [])

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
                self.assertEqual(dialog.validate_label(label) is None, rr_labels.validate_label(label) is None)


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

    def deep_vs_malformed(self, relpath, content, active):
        """The Stop outcome with `content` in relpath for a too-deep text and a malformed one."""
        path = os.path.join(self.s.root, *relpath)
        outs = []
        for text in ("[" * 200000, "{not json"):
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(content(text))
            code, raw = run_gate(self.s, dict(spike("claude/stop"), stop_hook_active=active))
            self.assertEqual(code, 0)
            self.assertNotIn("Traceback", raw)
            outs.append(hook_output(raw))
        return outs

    def test_stop_deep_session_json_is_malformed_session_json(self):
        """R-hooks-readers-of-ai-state-files-do-not-c-7d54: prompt_count."""
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        for active in (False, True):
            # pylint: disable-next=unbalanced-tuple-unpacking  # deep_vs_malformed returns a pair
            deep, bad = self.deep_vs_malformed((".ai", "state", "session.json"), lambda t: t, active)
            self.assertEqual(deep, bad)
            self.assertTrue(deep, "an open decision still answers the Stop")

    def test_stop_deep_ledger_line_is_malformed_ledger_line(self):
        """The hook's read_ledger skips a too-deep line like a torn one."""
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        sid = spike("claude/stop")["session_id"]
        line = json.dumps({"v": 1, "type": dialog.STOP_BLOCK, "session": sid, "turn": None, "decisions": ["D1"]})
        content = lambda t: "%s\n%s\n%s\n" % (line, t, line)
        # pylint: disable-next=unbalanced-tuple-unpacking  # deep_vs_malformed returns a pair
        deep, bad = self.deep_vs_malformed((".ai", "state", "consent.jsonl"), content, False)
        self.assertEqual(deep, bad)
        self.assertEqual(dialog.read_ledger(self.s.root, types={dialog.STOP_BLOCK}).__len__(), 2)

    def test_codex_deep_tool_response_is_malformed(self):
        payload = {"tool_input": {"questions": [{"id": "q1"}]}}
        deep = dialog.adapt_response("codex", dict(payload, tool_response="[" * 200000))
        bad = dialog.adapt_response("codex", dict(payload, tool_response="{not json"))
        self.assertEqual(deep, bad)

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

    def test_closed_writes_nothing_and_returns_empty(self):
        """a call the hook cannot bind to a session is closed: no ledger line, no output."""
        self.s.decide(decision("D1", "Commit a.py?", "Commit", [("choice", SAFE), ("command", COMMIT)]))
        mismatch = {"CLAUDE_CODE_SESSION_ID": "another-session"}
        self.assertEqual(run_gate(self.s, commit_payload(), mismatch), (0, ""))
        self.assertEqual(run_gate(self.s, dict(commit_payload(), session_id="")), (0, ""))
        code, out = run_gate(self.s, dict(spike("claude/stop"), agent_id="a1"), mismatch)
        self.assertEqual((code, hook_output(out)), (0, {}))
        code, out = run_gate(self.s, spike("claude/stop"), mismatch)
        self.assertEqual((code, hook_output(out)), (0, {}))
        self.assertEqual(self.s.ledger(), [])

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
        """timed: the floor of the whole ai-guard.py process on a Grep payload, no decision.json.
        Bare-interpreter and gate runs are interleaved and the minimum of each is compared:
        load only adds time, a real slowdown raises every run including the minimum."""
        budget = 0.015 * timed_factor()
        bare, gate = [], []
        for _ in range(7):
            bare.append(timed(["python3", "-I", "-S", "-c", "pass"], ""))
            gate.append(timed(["python3", "-I", "-S", os.path.join(ROOT, "hooks", "ai-guard.py")],
                              json.dumps(self.grep()), self.s.root))
        floor = min(gate) - min(bare)
        self.assertLessEqual(floor, budget, "%.1f ms over the interpreter's start" % (floor * 1000))


class TestDecisionGate(HookCase):  # pylint: disable=too-many-public-methods  # one test per case keeps failures named
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

    def test_gate_allows_on_too_deep_decision_json(self):
        # read_decisions catches RecursionError; end to end the hook allows (R-deep-decision-json-gate-allow-not-pinned-47ef)
        with open(os.path.join(self.s.root, ".ai", "state", "decision.json"), "w", encoding="utf-8") as fh:
            fh.write("[" * 200000)
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


GONE = object()                           # a spec change that removes the field instead of setting it
# state.py whose third open_decision is refused, as it is when another process wrote decision.json in between
RACE = """\
import sys
sys.path.insert(0, %r)
import state
from rr_state import dialog
real, calls = dialog.open_decision, []


def racing(*args, **kwargs):
    calls.append(args[4])
    if len(calls) == 3:
        return None, "DECISION_DUPLICATE - D9 is open with this very question"
    return real(*args, **kwargs)


dialog.open_decision = racing
state.main()
"""


def edited(spec, path, value):
    """A copy of `spec` with `value` at `path` (keys and indices); GONE removes the field."""
    spec = json.loads(json.dumps(spec))
    holder = spec
    for step in path[:-1]:
        holder = holder[step]
    if value is GONE:
        del holder[path[-1]]
    else:
        holder[path[-1]] = value
    return spec


class TestSetupOpener(unittest.TestCase):
    """R11, R12: `state.py decision open --kind setup --spec`, the /rr-setup questions. Every check runs before the
    first write and the decisions open in the spec's order or not at all; a settled choice prints SETUP_PICK."""

    def setUp(self):
        self.p = DialogProject()

    def tearDown(self):
        self.p.close()

    @staticmethod
    def choice(label, value, description=None):
        return dict({"kind": "choice", "label": label, "value": value},
                    **({"description": description} if description else {}))

    @staticmethod
    def command(project, *options):
        """`memory enable [options]` for this project, as state.py writes the label."""
        return {"kind": "command", "label": rr_labels.state_label(project.root, ["memory", "enable"] + list(options))}

    def spec(self, project=None):
        """The four questions /rr-setup opens (spec §Interfaces): memory first, the only commands in it."""
        project = project or self.p
        packages = ("--author", "vanssa", "--period", "quarter")
        return {"schema": 1, "decisions": [
            {"key": "memory", "header": "Memory", "question": "Project memory for p: off keeps closed tasks only in "
                                                              ".ai/reports/. Turn it on?",
             "options": [self.choice("Off — keep files mode", "off", "closed tasks stay in .ai/reports/"),
                         dict(self.command(project, *packages), description="packages; installs .git/hooks/pre-push"),
                         self.command(project, *packages, "--index", "sqlite")]},
            {"key": "runtime", "header": "Runtime", "question": "Which agent runtimes work on p?",
             "options": [self.choice("Auto — what the repository declares", "auto"),
                         self.choice("Claude Code only", "claude"), self.choice("Codex only", "codex"),
                         self.choice("Claude Code and Codex", "both")]},
            {"key": "survey", "header": "Survey", "question": "How deep should the first survey of p go?",
             "options": [self.choice("Light — a brain dump and 2 discovery agents", "light"),
                         self.choice("Full — inventory and 6 discovery agents", "full")]},
            {"key": "verify", "header": "Verify", "question": "verify_command — the fast suite. Proposed: `make test`.",
             "options": [self.choice("Not now — ask me in chat", ""), self.choice("Use `make test`", "make test"),
                         self.choice("Another — I type it in chat", "other")]}]}

    def open(self, spec, stdin=None, **kwargs):
        return self.p.run("decision", "open", "--kind", "setup", "--spec", "-",
                          stdin=json.dumps(spec) if stdin is None else stdin, **kwargs)

    def kept(self):
        """decision.json byte for byte, and the ledger: what a refused open leaves as it found them."""
        path = os.path.join(self.p.root, ".ai", "state", "decision.json")
        raw = None
        if os.path.exists(path):
            with open(path, "rb") as fh:
                raw = fh.read()
        return raw, self.p.ledger()

    def refused(self, spec, code, text, stdin=None, **kwargs):
        before = self.kept()
        done = self.open(spec, stdin, **kwargs)
        self.assertEqual((done.returncode, done.stdout), (code, ""), done.stdout + done.stderr)
        self.assertIn(text, done.stderr)
        self.assertEqual(self.kept(), before, "a refused open writes nothing")
        return done

    def answered(self, project, done, answers, call="toolu_setup"):
        """The human's answers to the dialog `done` printed, recorded by the PostToolUse hook itself: `answers` maps
        a question's text to the label picked, or to free text, which the recorder reads as a decline."""
        questions = json.loads(done.stdout.splitlines()[1])["questions"]
        payload = dict(json.loads(json.dumps(spike("claude/ask-single"))), session_id=DIALOG_SESSION, tool_use_id=call)
        for holder in ("tool_input", "tool_response"):
            payload[holder] = {"questions": questions, "answers": answers}
        hooked = types.SimpleNamespace(root=project.root, vars={
            "CLAUDE_CONFIG_DIR": project.home, "CLAUDE_CODE_SESSION_ID": DIALOG_SESSION, "AI_UNATTENDED": "",
            "CLAUDE_CODE_SESSION_ATTENDED": "1"})
        self.assertEqual(run_gate(hooked, payload), (0, ""))
        return questions

    def test_setup_spec_opens_atomically(self):
        spec = self.spec()
        # a third decision that cannot open: the four open none
        self.refused(edited(spec, ("decisions", 2, "options", 0), self.command(self.p, "--author", "vanssa")),
                     6, "CONSENT_LABEL_INVALID")
        self.assertFalse(os.path.exists(os.path.join(self.p.root, ".ai", "state", "decision.json")))
        # one question text twice in a spec (the text as open_decision stores it: stripped)
        self.refused(edited(spec, ("decisions", 1, "question"), "  %s\n" % spec["decisions"][0]["question"]),
                     6, "DECISION_DUPLICATE")
        # the dialog off: exit 1 with its message, nothing opened
        self.refused(spec, 1, "the dialog is off here", env={"CLAUDE_CODE_SESSION_ID": ""})
        # one decision already open: four more do not fit, and a question already asked is not asked again
        self.p.ok("decision", "open", "--kind", "commit", "--command", "git commit -m one")
        self.refused(spec, 6, "DECISION_LIMIT")
        [commit] = self.p.decisions()
        self.refused({"schema": 1, "decisions": [spec["decisions"][1], dict(spec["decisions"][2], question=commit["question"])]},
                     6, "DECISION_DUPLICATE")
        self.assertEqual([d["id"] for d in self.p.decisions()], [commit["id"]])
        self.p.ok("decision", "fallback", "--id", commit["id"], "--why", "test")
        # the valid spec opens all four, in its order, as one dialog
        done = self.open(spec)
        self.assertEqual(done.returncode, 0, done.stderr)
        opened = self.p.decisions()
        ids = [d["id"] for d in opened]
        self.assertEqual([d["setup_key"] for d in opened], ["memory", "runtime", "survey", "verify"])
        self.assertEqual({(d["kind"], d["opened_by"], d["multi_select"]) for d in opened},
                         {("setup", "decision open --kind setup", False)})
        self.assertEqual([int(i[1:]) for i in ids], list(range(int(ids[0][1:]), int(ids[0][1:]) + 4)))
        # a choice keeps its value and settles as "set"; a command is only its label
        stored = [[(o["kind"], o["label"], o.get("value"), o.get("effect")) for o in d["options"]] for d in opened]
        wanted = [[(o["kind"], o["label"], o.get("value"), "set" if o["kind"] == "choice" else None)
                   for o in item["options"]] for item in spec["decisions"]]
        self.assertEqual(stored, wanted)
        self.assertEqual(opened[0]["options"][0]["description"], "closed tasks stay in .ai/reports/")
        lines = done.stdout.splitlines()
        self.assertEqual((len(lines), done.stdout.count("DIALOG_PENDING")), (2, 1), done.stdout)
        self.assertTrue(lines[0].startswith("DIALOG_PENDING %s — " % " ".join(ids)), lines[0])
        sent = json.loads(lines[1])
        self.assertEqual([q["question"] for q in sent["questions"]], [d["question"] for d in spec["decisions"]])
        self.assertEqual(sent, dialog.dialog_payload(dialog.read_decisions(self.p.root), "claude"),
                         "the call the gate demands is the one printed")

    def test_setup_spec_rejects_foreign_command(self):
        entry, root = os.path.abspath(STATE), self.p.root
        elsewhere = os.path.join(self.p.tmp.name, "elsewhere")

        def memory(tail):
            return "python3 %s --root %s %s" % (entry, root, tail)
        # a command label the dialog's own rule may pass, and still not `memory enable` of this state.py and project
        foreign = {
            "git commit": "git commit -m x -- a.py", "approve": memory("approve --by me"),
            "memory disable": memory("memory disable"), "memory cleanup": memory("memory cleanup --all"),
            "another root": "python3 %s --root %s memory enable" % (entry, elsewhere),
            "another state.py": "python3 /tmp/y/state.py --root %s memory enable" % root,
            "a relative state.py": "python3 skills/ai-task/state.py --root %s memory enable" % root,
            "a --root relative to the cwd": "python3 %s --root %s memory enable" % (entry, os.path.relpath(root)),
            "a --runtime": memory("--runtime claude memory enable"),
            "interpreter flags": "python3 -I %s --root %s memory enable" % (entry, root),
            "two --root": memory("--root %s memory enable" % root), "no --root": "python3 %s memory enable" % entry,
            "a relative --root": "python3 %s --root . memory enable" % entry,
            "python, not python3": "python %s --root %s memory enable" % (entry, root),
            "a second command": memory("memory enable; ls"), "an option the rule has no name for": memory("memory enable --force"),
        }
        for name, label in foreign.items():
            with self.subTest(command=name):
                self.refused(edited(self.spec(), ("decisions", 0, "options", 1), {"kind": "command", "label": label}),
                             6, "CONSENT_LABEL_INVALID")
        # only the memory decision offers a command
        self.refused(edited(self.spec(), ("decisions", 1, "options", 1), self.command(self.p, "--author", "vanssa")),
                     6, "only the memory decision offers a command")
        # a choice never reads as a command: the gate passes a Bash command equal to any pick, and a pick that is a
        # state.py label is run by dialog_pick
        command = self.spec()["decisions"][0]["options"][1]["label"]
        readable = {"python3": "python3 is what runs it", "git": "git status", "npx": "npx riskrails@4.1.0 --yes",
                    "the command itself": command, "a padded state.py call": "  " + memory("approve --by me"),
                    "state.py through python": "python %s --root %s approve --by me" % (entry, root),
                    "a quoted git commit": "\"git\" commit -m x -- a.py"}
        for name, label in readable.items():
            with self.subTest(choice=name):
                self.refused(edited(self.spec(), ("decisions", 2, "options", 1), self.choice(label, "full")),
                             6, "a choice label never reads as a command")
        for name, label in {"empty": "", "too long": "x" * (rr_labels.LABEL_MAX + 1), "not printable": "Full\tdeep"}.items():
            with self.subTest(choice=name):
                self.refused(edited(self.spec(), ("decisions", 2, "options", 1), self.choice(label, "full")),
                             6, "a choice label is 1 to")
        self.refused(edited(self.spec(), ("decisions", 2, "options", 1), self.choice("Light — a brain dump and 2 "
                     "discovery agents", "full")), 6, "carry the same label")
        # what is not the spec's shape is a bad spec (exit 2), whatever the labels say
        deep = "[" * (rr_dialog.JSON_DEPTH_MAX + 1) + "]" * (rr_dialog.JSON_DEPTH_MAX + 1)
        for name, text in {"empty": "", "not JSON": "{", "a list": "[]", "NaN": "NaN", "nested too deep": deep,
                           "over the size limit": json.dumps(self.spec()) + " " * rr_dialog_cmd.SETUP_SPEC_MAX}.items():
            with self.subTest(text=name):
                self.refused(None, 2, "bad spec", stdin=text)
        value, text = rr_dialog_cmd.SETUP_VALUE_MAX, "a" * (rr_dialog.QUESTION_MAX + 1)
        shapes = {
            "an extra field of the spec": (("extra",), 1), "schema 2": (("schema",), 2), "schema true": (("schema",), True),
            "schema 1.0": (("schema",), 1.0), "no schema": (("schema",), GONE), "no decisions": (("decisions",), []),
            "decisions that is no list": (("decisions",), {}), "an unknown key": (("decisions", 1, "key"), "colour"),
            "a key twice": (("decisions", 1, "key"), "memory"), "a key that is a list": (("decisions", 1, "key"), ["runtime"]),
            "an empty header": (("decisions", 1, "header"), " "), "an empty question": (("decisions", 1, "question"), "\n"),
            "a header that is no text": (("decisions", 1, "header"), 7), "an extra field of a decision": (("decisions", 1, "multi"), True),
            "no header": (("decisions", 1, "header"), GONE), "one option": (("decisions", 2, "options"), [self.choice("Full", "full")]),
            "options that is no list": (("decisions", 2, "options"), "Light, Full"),
            "an option that is no object": (("decisions", 1, "options", 0), "Auto"),
            "an unknown kind": (("decisions", 1, "options", 0, "kind"), "multi"),
            "a choice without a value": (("decisions", 1, "options", 0, "value"), GONE),
            "a numeric value": (("decisions", 1, "options", 0, "value"), 5), "a null value": (("decisions", 1, "options", 0, "value"), None),
            "a value over the limit": (("decisions", 1, "options", 0, "value"), "a" * (value + 1)),
            "a value with a newline": (("decisions", 1, "options", 0, "value"), "a\nb"),
            "an extra field of an option": (("decisions", 1, "options", 0, "effect"), "ack"),
            "a command with a value": (("decisions", 0, "options", 1, "value"), "x"),
            "a label that is no text": (("decisions", 1, "options", 0, "label"), 5),
            "a description that is no text": (("decisions", 1, "options", 0, "description"), 5),
            "a description over the limit": (("decisions", 1, "options", 0, "description"), text),
            "a lone surrogate": (("decisions", 1, "question"), "a\ud800b")}
        for name, (path, new) in shapes.items():
            with self.subTest(shape=name):
                self.refused(edited(self.spec(), path, new), 2, "bad spec")
        five = edited(self.spec(), ("decisions",), self.spec()["decisions"] + self.spec()["decisions"][:1])
        self.refused(five, 2, "1 to 4 decisions")
        self.refused(edited(self.spec(), ("decisions", 1, "options"), self.spec()["decisions"][1]["options"] * 2),
                     2, "2 to 4 options")
        # the rule is not tighter than the command it names: no option at all, or all three in any order, one with a blank
        spec = {"schema": 1, "decisions": [
            {"key": "memory", "header": "Memory", "question": "Turn it on?",
             "options": [self.choice("Off", "off"), self.command(self.p),
                         self.command(self.p, "--index", "sqlite", "--period", "year", "--author", "Ivan K")]}]}
        self.assertEqual(self.open(spec).returncode, 0)
        # usage: --spec belongs to --kind setup, --command to --kind commit, and the kinds are those two
        for args, code, text in (
                (("--kind", "setup", "--spec", "-", "--command", "git commit -m x"), 2, "takes --spec FILE|- and no --command"),
                (("--kind", "setup"), 2, "takes --spec FILE|- and no --command"),
                (("--kind", "setup", "--spec", os.path.join(self.p.tmp.name, "nope.json")), 2, "bad spec"),
                (("--kind", "commit", "--spec", "-", "--command", "git commit -m x"), 2, "takes --command, not --spec"),
                (("--kind", "approval", "--spec", "-"), 1, "takes --kind commit or --kind setup")):
            with self.subTest(args=args):
                done = self.p.run("decision", "open", *args, stdin=json.dumps(self.spec()))
                self.assertEqual((done.returncode, done.stdout), (code, ""), done.stderr)
                self.assertIn(text, done.stderr)

    def test_setup_values_are_the_vocabulary(self):
        """What the skill applies is what the human read: a choice sets one of its key's words, and a verify choice
        that sets a command shows it, whole, inside backticks, in its own label."""
        words = {"memory": ("off", "keep"), "runtime": ("auto", "claude", "codex", "both"),
                 "survey": ("light", "full", "keep"), "verify": ("", "other", "keep", "edit")}
        self.assertEqual(rr_dialog_cmd.SETUP_VALUES, words, "step C4 generates exactly this vocabulary")
        # another word, a different case, a blank or a word of another key is a bad spec (exit 2)
        index = {"memory": 0, "runtime": 1, "survey": 2}
        for key, values in {"memory": ("", "on", "Off", "off ", "packages", "other"),
                            "runtime": ("", "Claude", "gemini", "claude,codex", "none", "keep"),
                            "survey": ("", "medium", "Full", "other", "both")}.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    done = self.refused(edited(self.spec(), ("decisions", index[key], "options", 0, "value"), value),
                                        2, "bad spec")
                    self.assertIn("a %s choice sets one of: %s" % (key, ", ".join(words[key])), done.stderr)
        # a verify command that its own label does not show, whole, inside backticks is refused (exit 6)
        for name, (label, value, description) in {
                "a label that does not show it": ("Use the fast suite", "make test", None),
                "a description that shows it": ("Use the fast suite", "make test", "runs `make test`"),
                "no backticks": ("Use make test", "make test", None), "a bare command": ("make test", "make test", None),
                "another command in the span": ("Use `make test`", "make lint", None),
                "a part of the span": ("Use `make test -x`", "make test", None),
                "an unclosed backtick": ("Use `make test", "make test", None),
                "a backtick in the value": ("Use `a`b`", "a`b", None),
                "two spans fused into one value": ("Use `a` `b`", "a` `b", None)}.items():
            with self.subTest(command=name):
                self.refused(edited(self.spec(), ("decisions", 3, "options", 1), self.choice(label, value, description)),
                             6, "CONSENT_LABEL_INVALID — a verify command is shown verbatim in its label, inside backticks")
        # a command shown whole as a span of its own label opens, one word of a key needs no span, and every word opens
        commands = {"schema": 1, "decisions": [{"key": "verify", "header": "Verify", "question": "verify_command?", "options": [
            self.choice("Not now — ask me in chat", ""), self.choice("Keep `make test`", "keep"),
            self.choice("Run `make lint` first, then `make test`", "make test"),
            self.choice("Use `sh -c 'pytest -x'`", "sh -c 'pytest -x'")]}]}
        self.assertEqual(self.open(commands).returncode, 0)
        self.assertEqual([[o["value"] for o in d["options"]] for d in self.p.decisions()],
                         [["", "keep", "make test", "sh -c 'pytest -x'"]])
        self.p.ok("decision", "fallback", "--id", self.p.decisions()[0]["id"], "--why", "test")
        every = {"schema": 1, "decisions": [
            {"key": key, "header": key.title(), "question": "Which %s?" % key,
             "options": [self.choice("%s: %s" % (key, word or "nothing"), word) for word in words[key]]} for key in words]}
        self.assertEqual(self.open(every).returncode, 0)
        self.assertEqual([[o["value"] for o in d["options"]] for d in self.p.decisions()],
                         [list(words[key]) for key in words])

    def test_setup_spec_is_read_from_a_file(self):
        path = os.path.join(self.p.tmp.name, "spec.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.spec(), fh)
        done = self.p.run("decision", "open", "--kind", "setup", "--spec", path)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual([d["setup_key"] for d in self.p.decisions()], ["memory", "runtime", "survey", "verify"])

    def test_setup_decision_belongs_to_the_task_in_flight(self):
        """As the commit opener does: the decision names the task, and the journal says it was opened."""
        self.p.start()
        task_id = self.p.state()["task_id"]
        self.assertEqual(self.open({"schema": 1, "decisions": self.spec()["decisions"][2:3]}).returncode, 0)
        [opened] = self.p.decisions()
        self.assertEqual((opened["kind"], opened["setup_key"], opened["task"]), ("setup", "survey", task_id))
        self.assertEqual([(e["data"]["decision"], e["data"]["kind"], e["data"]["options"])
                          for e in self.p.events(task_id) if e["event"] == "decision_opened"],
                         [(opened["id"], "setup", 2)])

    def test_setup_open_withdraws_what_it_opened(self):
        """A race the checks cannot see: the third open_decision is refused, so the two before it are withdrawn."""
        wrapper = os.path.join(self.p.tmp.name, "race.py")
        with open(wrapper, "w", encoding="utf-8") as fh:
            fh.write(RACE % os.path.dirname(STATE))
        spec = self.spec()
        spec["decisions"] = spec["decisions"][:3]
        done = self.open(spec, state_py=wrapper)
        self.assertEqual((done.returncode, done.stdout), (6, ""), done.stderr)
        self.assertIn("DECISION_DUPLICATE - D9 is open", done.stderr)
        self.assertEqual(self.p.decisions(), [])
        self.assertEqual([(e["decision"], e["effect"]) for e in self.p.ledger() if e["type"] == "settle"],
                         [("D1", "withdrawn"), ("D2", "withdrawn")])

    def test_setup_settle_prints_pick(self):
        spec = self.spec()
        done = self.open(spec)
        self.assertEqual(done.returncode, 0, done.stderr)
        questions = [q["question"] for q in json.loads(done.stdout.splitlines()[1])["questions"]]
        # the human answers all four: two choices, free text (a decline), a choice that sets nothing
        self.answered(self.p, done, dict(zip(questions, ["Off — keep files mode", "Claude Code and Codex",
                                                         "something else entirely", "Not now — ask me in chat"])))
        self.assertEqual([(e["type"], e.get("decision"), e.get("why")) for e in self.p.ledger()],
                         [("offer", None, None), ("pick", "D1", None), ("pick", "D2", None),
                          ("decline", "D3", "other text"), ("pick", "D4", None)])
        settled = [self.p.ok("decision", "settle", "--id", d).stdout for d in ("D1", "D2", "D3", "D4")]
        self.assertEqual(settled, [
            "D1 settled: Off — keep files mode (set)\nSETUP_PICK memory=off\n",
            "D2 settled: Claude Code and Codex (set)\nSETUP_PICK runtime=both\n",
            "D3 settled: declined in the dialog (other text); nothing runs\nSETUP_PICK survey=\n",
            "D4 settled: Not now — ask me in chat (set)\nSETUP_PICK verify=\n"])
        self.assertEqual([e["effect"] for e in self.p.ledger() if e["type"] == "settle"],
                         ["set", "set", "declined", "set"])
        self.assertEqual(self.p.decisions(), [])
        # the terminal route (here a launcher that declared the run unattended) prints it too; a command is run, not settled
        other = DialogProject()
        try:
            done = other.run("decision", "open", "--kind", "setup", "--spec", "-", stdin=json.dumps(self.spec(other)))
            self.assertEqual(done.returncode, 0, done.stderr)
            pick = other.run("decision", "settle", "--id", "D2", "--pick", "4", human=True)
            self.assertEqual((pick.returncode, pick.stdout), (0, "D2 settled: Claude Code and Codex (set)\n"
                                                                  "SETUP_PICK runtime=both\n"), pick.stderr)
            spaced = other.run("decision", "settle", "--id", "D4", "--pick", "2", human=True)
            self.assertEqual((spaced.returncode, spaced.stdout), (0, "D4 settled: Use `make test` (set)\n"
                                                                     "SETUP_PICK verify=make test\n"), spaced.stderr)
            command = other.run("decision", "settle", "--id", "D1", "--pick", "2", human=True)
            self.assertEqual(command.returncode, 1, command.stdout)
            self.assertIn("is a command: run it in this terminal instead", command.stderr + command.stdout)
            self.assertNotIn("SETUP_PICK", command.stdout)
            # a memory command picked in the dialog is run, not settled: no SETUP_PICK for it
            sqlite = [o["label"] for o in other.decisions()[0]["options"] if o["kind"] == "command"][1]
            self.answered(other, done, {questions[0]: sqlite}, call="toolu_command")
            run = other.run("decision", "settle", "--id", "D1")
            self.assertEqual(run.returncode, 1, run.stdout)
            self.assertIn("has a live pick: run it verbatim", run.stderr)
            self.assertNotIn("SETUP_PICK", run.stdout + run.stderr)
        finally:
            other.close()


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


class TestC5Text(unittest.TestCase):
    """R36.21: the three sentences C5 replaced are gone from every shipped file."""

    OLD = ("No agent commits, merges or deploys; approval is given by a human outside the agent",
           "No agent commits, pushes, merges or deploys; the pipeline ends at human approval, given outside the agent",
           "You cannot approve",
           "No agent commits, merges or deploys; a human approves outside the agent",
           "Approval is given by a human, outside the agent",
           "the pipeline ends at human approval",
           "never commits, pushes or approves")
    SKIP = ("skills/project-update/history/", "tests/fixtures/", "docs/sdlc/specs/", "docs/sdlc/plans/",
            "docs/sdlc/intent/", ".ai/reports/", ".ai/memory/", "tests/test_dialog_gate.py")

    def test_c5_text_everywhere(self):
        listed = subprocess.run(["git", "-C", ROOT, "ls-files", "-z", "--cached", "--others", "--exclude-standard"], capture_output=True, text=True,
                                check=True).stdout.split("\0")
        hits = []
        for rel in filter(None, listed):
            path = os.path.join(ROOT, rel)
            if rel.startswith(self.SKIP) or not os.path.isfile(path):
                continue
            try:
                with open(path, encoding="utf-8") as fh:
                    text = " ".join(fh.read().split())
            except (OSError, UnicodeDecodeError):
                continue
            hits += ["%s: %s" % (rel, old) for old in self.OLD if old in text]
        self.assertEqual(hits, [])


if __name__ == "__main__":
    unittest.main()
