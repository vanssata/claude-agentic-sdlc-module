#!/usr/bin/env python3
"""R36 spec design item 2: state.py keeps its own small consent-ledger reader
rather than importing the hooks' module. This contract feeds every reader the
same fixtures (tests/fixtures/dialog/ledger/), so the two cannot drift. Task 7c
asserted the state.py side; 7d1 added hooks/guard/dialog.py's reader to READERS."""

import json
import os
import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
