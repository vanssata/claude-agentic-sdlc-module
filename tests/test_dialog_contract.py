#!/usr/bin/env python3
"""R36 spec design item 2: state.py keeps its own small consent-ledger reader
rather than importing the hooks' module. This contract feeds every reader the
same fixtures (tests/fixtures/dialog/ledger/), so the two cannot drift. Task 7c
asserts the state.py side; 7d1 adds hooks/guard/dialog.py's reader to READERS."""

import json
import os
import sys
import unittest
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "tests", "fixtures", "dialog", "ledger")
sys.path.insert(0, os.path.join(ROOT, "skills", "ai-task"))
import state as state_mod  # noqa: E402  pylint: disable=wrong-import-position


def state_reader(path, session, at):
    return [p["id"] for p in state_mod.live_picks(state_mod.read_ledger(None, path), session, at)]


READERS = {"state.py": state_reader}


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


if __name__ == "__main__":
    unittest.main()
