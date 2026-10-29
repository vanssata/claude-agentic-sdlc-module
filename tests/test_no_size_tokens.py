#!/usr/bin/env python3
"""exec" python3 -I "$0" "$@"
Size never gates (R4, phase 2): no shipped skill, hook, shared policy or
instruction file names the size gate the redesign removed — `diff_budget`,
`step-split`, `DIFF_BUDGET_EXCEEDED`, `over_budget`, the `rescore` sensor.

Three places keep the words on purpose: the migrations that read and drop the
old keys, the frozen template history, and the old `risk-tiers.*` policy
templates, whose removal changes what a user project receives and is its own
task (.ai/project/known-risks.md). `rescore_axes` in weight.json is the
re-score of the weight model, not the sensor, so the match is a whole word.

`step_test_command` hands every test path to bash; the line above makes bash
re-run this file under python3.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIRS = ("skills", "hooks", "ai", "instructions")
TOKENS = ("diff_budget", "step-split", "DIFF_BUDGET_EXCEEDED", "over_budget", "rescore")
TOKEN_RE = re.compile(r"(?<![\w-])(%s)(?![\w-])" % "|".join(re.escape(t) for t in TOKENS))
KEPT = ("skills/project-update/migrations/", "skills/project-update/history/",
        "skills/ai-init/templates/.ai/policies/risk-tiers.json",
        "skills/ai-init/templates/.ai/policies/risk-tiers.md")


def shipped_files():
    for top in DIRS:
        for base, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                rel = os.path.relpath(os.path.join(base, name), ROOT).replace(os.sep, "/")
                if not rel.startswith(KEPT):
                    yield rel


class TestNoSizeTokens(unittest.TestCase):
    def test_no_shipped_file_names_the_size_gate(self):
        hits = []
        for rel in shipped_files():
            try:
                with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                    lines = fh.read().splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            hits += ["%s:%d: %s" % (rel, n, m.group(1))
                     for n, line in enumerate(lines, 1) for m in TOKEN_RE.finditer(line)]
        self.assertEqual(hits, [], "the size gate is still named:\n" + "\n".join(hits[:40]))

    def test_the_match_is_a_whole_word(self):
        self.assertIsNone(TOKEN_RE.search('"rescore_axes": ["reversibility"]'))
        self.assertIsNone(TOKEN_RE.search("re-score: reversibility 0 -> 1"))
        self.assertIsNotNone(TOKEN_RE.search("sensors.rescore(declared)"))
        self.assertIsNotNone(TOKEN_RE.search("state.py step-split s1"))


if __name__ == "__main__":
    unittest.main()
