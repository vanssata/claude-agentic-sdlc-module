#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
R11: the --line statusline of hooks/runtime-gate.py shows the task and what waits
on the human; with no task and no open decision the line is the unchanged code's.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from guard_harness import PLUGIN  # noqa: E402  pylint: disable=wrong-import-position

GATE = os.path.join(PLUGIN, "hooks", "runtime-gate.py")
STATE = {"task_id": "T-1", "mode": "guarded", "stage": "build", "questions": {"pending": []},
         "human_approval": {"requested_at": None, "gate_id": None}}


def line(root, gate=GATE):
    """The --line output of a statusline run in root, as text."""
    env = {"PATH": os.environ.get("PATH", ""), "USER": "tester", "LOGNAME": "tester", "TZ": "UTC", "HOME": root}
    proc = subprocess.run([sys.executable, "-I", "-S", gate, "statusline", "--line"],
                          input=json.dumps({"workspace": {"current_dir": root}}), capture_output=True,
                          text=True, env=env, check=False)
    return proc.stdout


def timed(root):
    started = time.perf_counter()
    line(root)
    return time.perf_counter() - started


def timed_factor():
    try:
        return float(os.environ.get("AI_TIMED_FACTOR") or 1)
    except ValueError:
        return 1.0


class TestStatuslineTask(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.project("proj")

    def project(self, name):
        root = os.path.join(self.tmp, name)
        os.makedirs(os.path.join(root, ".ai", "state"))
        return root

    def write(self, name, data, raw=False):
        with open(os.path.join(self.root, ".ai", "state", name), "w", encoding="utf-8") as fh:
            fh.write(data if raw else json.dumps(data))

    def segment(self):
        """The text after the prompt part of the line, colours removed."""
        text = line(self.root).split(" \033[02m|\033[00m ")[1]
        return text.replace("\033[36m", "").replace("\033[00m", "").strip()

    def test_no_task_no_decision_is_the_unchanged_line(self):
        old = os.path.join(self.tmp, "old-gate.py")
        shown = subprocess.run(["git", "-C", PLUGIN, "show", "HEAD:hooks/runtime-gate.py"], capture_output=True,
                               check=True)
        with open(old, "wb") as fh:
            fh.write(shown.stdout)
        for state in (None, '{"task_id": null}', "not json"):
            with self.subTest(state=state):
                if state is not None:
                    self.write("state.json", state, raw=True)
                self.assertEqual(line(self.root), line(self.root, old))
                self.assertNotIn("waiting", line(self.root))

    def test_task_in_flight_with_nothing_waiting(self):
        self.write("state.json", STATE)
        self.assertEqual(self.segment(), "T-1 · guarded · build")

    def test_task_with_decisions_questions_and_gate(self):
        self.write("state.json", dict(STATE, questions={"pending": ["Q2", "G1"]},
                                      human_approval={"requested_at": "t", "gate_id": "G1"}))
        self.write("decision.json", {"open": [{"id": "D3"}, {"id": "D4"}]})
        self.assertEqual(self.segment(), "T-1 · guarded · build waiting on you: D3 D4 Q2 G1")

    def test_more_than_three_ids_of_a_kind(self):
        self.write("state.json", dict(STATE, questions={"pending": ["Q%d" % n for n in range(1, 6)]}))
        self.write("decision.json", {"open": [{"id": "D%d" % n} for n in range(1, 5)]})
        self.assertEqual(self.segment(), "T-1 · guarded · build waiting on you: D1 D2 D3 +1 Q1 Q2 Q3 +2")

    def test_no_task_but_open_decisions(self):
        self.write("decision.json", {"open": [{"id": "D3"}]})
        self.assertEqual(self.segment(), "riskrails · waiting on you: D3")

    def test_malformed_files_leave_the_line_alone(self):
        plain = line(self.project("plain"))
        for state, decision in (("{", "["), ('{"task_id": 5, "questions": 3}', '{"open": "x"}'), ("[]", "null")):
            with self.subTest(state=state):
                self.write("state.json", state, raw=True)
                self.write("decision.json", decision, raw=True)
                out = line(self.root)
                self.assertTrue(out.endswith("\n"), out)
                self.assertNotIn("waiting", out)
        self.assertNotIn("riskrails", plain)

    def ledger(self, *lines):
        self.write("consent.jsonl", "".join(json.dumps(dict({"v": 1}, **line)) + "\n" for line in lines), raw=True)

    def decisions(self, count=2):
        self.write("decision.json", {"open": [
            {"id": "D%d" % n, "options": [{"n": 1, "kind": "choice"}, {"n": 2, "kind": "command"}]}
            for n in range(1, count + 1)]})

    def pick(self, decision, pick_id):
        return {"type": "pick", "id": pick_id, "decision": decision, "option": 2, "order": 1, "tool_use_id": "t"}

    def test_a_settled_unpruned_decision_is_not_shown(self):
        self.decisions()
        self.ledger({"type": "settle", "decision": "D1"})
        self.assertEqual(self.segment(), "riskrails · waiting on you: D2")

    def test_a_decision_with_all_picks_used_is_not_shown(self):
        self.decisions()
        self.ledger(self.pick("D1", "C1"), {"type": "use", "id": "C1"}, self.pick("D2", "C2"))
        self.assertEqual(self.segment(), "riskrails · waiting on you: D2")

    def test_an_offered_unused_pick_is_shown(self):
        self.decisions(1)
        self.ledger({"type": "offer", "decision": "D1"}, self.pick("D1", "C1"))
        self.assertEqual(self.segment(), "riskrails · waiting on you: D1")

    def test_a_missing_or_torn_ledger_keeps_the_open_list(self):
        """As `pending` with an empty ledger: every open decision still waits."""
        self.decisions()
        self.assertEqual(self.segment(), "riskrails · waiting on you: D1 D2")
        self.write("consent.jsonl", "{\n[1]\nnull\n", raw=True)
        self.assertEqual(self.segment(), "riskrails · waiting on you: D1 D2")

    def test_cost_with_100_decisions(self):
        """timed: the interleaved minimum with 100 open decisions against none, at most 10 ms more."""
        empty = self.project("empty")
        self.decisions(100)
        self.ledger(*[line for n in range(1, 101) for line in
                      ({"type": "offer", "decision": "D%d" % n}, self.pick("D%d" % n, "C%d" % n))])
        base, loaded = [], []
        for _ in range(7):
            base.append(timed(empty))
            loaded.append(timed(self.root))
        over = min(loaded) - min(base)
        self.assertLessEqual(over, 0.010 * timed_factor(), "%.1f ms over" % (over * 1000))


if __name__ == "__main__":
    unittest.main()
