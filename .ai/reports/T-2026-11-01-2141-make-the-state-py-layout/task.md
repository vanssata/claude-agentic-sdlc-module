# T-2026-11-01-2141-make-the-state-py-layout — Make the state.py layout and characterization tests independent of the Python version and checkout path, so the full suite is green on release Python 3.12

bugfix · guarded · started 2026-11-01T21:41:11Z · claude

## Weight

```
scope          2  tools/state-partition.py referenced from 11 files
behaviour      1  keyword 'workflow' in tests/fixtures/state/goldens/dialog.txt
reversibility  0  git revert returns everything
domain         0  test infrastructure (declared)
novelty        0  two more normalise rules beside the existing ones and a hash function swap (declared)
coverage       2  0 of 1 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tools/state-partition.py, tests/fixtures/state/partition.json, tests/test_state_layout.py, tests/test_state_characterization.py, tests/fixtures/state/goldens/help.txt, tests/fixtures/state/goldens/dialog.txt, tests/fixtures/state/goldens/light.txt, tests/fixtures/state/goldens/guarded.txt, tests/fixtures/state/goldens/full.txt
tests: tests/test_state_layout.py, tests/test_state_characterization.py
- s1 · tools/state-partition.py, tests/fixtures/state/partition.json, tests/test_state_layout.py · tests/test_state_layout.py · done
- s2 · tests/test_state_characterization.py, tests/fixtures/state/goldens/help.txt, tests/fixtures/state/goldens/dialog.txt, tests/fixtures/state/goldens/light.txt, tests/fixtures/state/goldens/guarded.txt, tests/fixtures/state/goldens/full.txt · tests/test_state_characterization.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | dd1352c5a | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/step-1.log | yes |
| 2 | step | 0 | 7f74dcf92 | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/step-2.log | no |
| 3 | step | 1 | 37c82f046 | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/step-3.log | yes |
| 4 | step | 0 | 75fffa50e | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/step-4.log | no |
| 5 | suite | 1 | 75fffa50e | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/suite-5.log | no |
| 6 | suite | 0 | 75fffa50e | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/suite-6.log | no |
| 7 | e2e | 0 | 75fffa50e | .ai/state/logs/T-2026-11-01-2141-make-the-state-py-layout/e2e-7.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 tests/fixtures/state/partition.json defs — two stale ast.dump-format value_hash entries remain (LOCK_DEPTH, DIALOG_PICK; RUNTIME/MUTATING retired). The old hashes were already mismatched for these values, so the file now mixes hash formats. They are skipped by the layout test via `memos` (name not in memos), so nothing is hidden today, but a later `state-partition.py --write` would silently re-encode them. in_scope: yes — suggested direction: note in task risk list or null the two hashes in a follow-up; no change required for this task.
- [INFO] I1 ast.unparse stability is not guaranteed for every future value: my probe showed no 3.12/3.13/3.14 difference and the only 3.11 mismatch was my own probe item that doesn't parse there; unparse can change across versions (f-string quoting changed in 3.12). It is stable for all 76 module-level non-def values in rr_state/*.py today (byte-identical on 3.11/3.12/3.13/3.14, including tuples, dicts, regexes, LOCK_STALE float, no f-strings). TestValueHash pins only one literal (a call with a raw string + attribute). in_scope: no
- [INFO] I2 USAGE joins any `^usage: ` line plus indented lines, not only argparse output; in the goldens `usage:` appears only in help.txt (39 lines), so no effect outside help.txt. in_scope: no

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed within the plan: tests, fixtures and the tool's hash function only; no shipped skill code changed.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| tests/fixtures/state/goldens/dialog.txt | +1 −1 | Edit |
| tests/fixtures/state/goldens/help.txt | +21 −62 | Edit |
| tests/fixtures/state/partition.json | +69 −69 | Edit |
| tests/test_state_characterization.py | +49 −5 | Edit |
| tests/test_state_layout.py | +9 −0 | Edit |
| tools/state-partition.py | +3 −1 | Edit |

+152 −138 lines, 6 files

## Verdict

close: closed
facts: (a) green — suite green on 75fffa50e (run 6) · (b) green — 6 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
