#!/usr/bin/env python3
"""R36: the dialog. Task 7c writes the payload half — what state.py prepares
for the dialog tool (golden payloads, the label rule, the multi-select split);
7d1 adds the hook half (the recorder, the gate, the effective switch matrix).

The goldens are tests/fixtures/dialog/payload-golden/<case>.json, with the
scratch project's paths, task id, tree, branch and git user replaced by
placeholders. DIALOG_GOLDEN_UPDATE=1 rewrites them; review the diff."""

import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GOLDEN = os.path.join(ROOT, "tests", "fixtures", "dialog", "payload-golden")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position
from test_ai_task_state import CLEAN, STATE, DialogProject  # noqa: E402  pylint: disable=wrong-import-position

PUSH = "git push origin feat/x"


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


if __name__ == "__main__":
    unittest.main()
