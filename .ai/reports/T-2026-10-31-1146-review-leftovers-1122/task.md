# T-2026-10-31-1146-review-leftovers-1122 — T-2026-10-31-1122 review leftovers: L1 docstring, L2 closed-deny text, I1 fixed JSON depth cap, I2 read_profile RecursionError, flaky test_gate_fast_path

feature · guarded · started 2026-10-31T11:46:34Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      2  a valid dialog.json/profile.json nested past the fixed cap reads as malformed (off): the accepte
reversibility  0  git revert returns everything
domain         1  commit/push consent switch readers; no parseable shallow file changes route (declared)
novelty        0  bugfixes and a test measurement in existing code (declared)
coverage       0  3 of 3 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T11:46:34Z — /rr-build-all ~/.claude/plans/t1122-review-leftovers.md (review leftovers of T-2026-10-31-1122)

## Plan

files: skills/ai-task/state.py, hooks/guard/dialog.py, hooks/guard/git.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py
tests: tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py
- s1 · skills/ai-task/state.py, hooks/guard/dialog.py, hooks/guard/git.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py · tests/test_dialog_contract.py, tests/test_dialog_consent.py · done
- s2 · tests/test_dialog_gate.py · tests/test_dialog_gate.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 086a20ccd | .ai/state/logs/T-2026-10-31-1146-review-leftovers-1122/suite-1.log | no |
| 2 | e2e | 0 | 086a20ccd | .ai/state/logs/T-2026-10-31-1146-review-leftovers-1122/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The two copies of the scanner are pinned only by the constant, and the string-escape logic is tested on one shape (hooks/guard/dialog.py:78-99, skills/ai-task/state.py:2355-2377, tests/test_dialog_contract.py:93-96)  in_scope: yes
  why it matters: test_tables_are_equal pins JSON_DEPTH_MAX only; the function bodies are separate copies that could drift. No case has an escaped backslash right before a closing quote ("\\"). Hand-run case counted correctly; logic right today, but a later edit to one copy's esc branch would not be caught.
  suggested direction: add one "\\\\" plus brackets-after-string case to the cap test, or assert both copies give identical results over a small table of strings.
- [LOW] L2 The test_read_profile_survives_deep_nesting case at JSON_DEPTH_MAX + 1 cannot fail (tests/test_dialog_contract.py:122)  in_scope: yes
  why it matters: "[" * 65 is unterminated, so plain json.load raises JSONDecodeError and read_profile returns {} with or without the fix. Only the 200000 case pins the RecursionError catch (it fails on old code), so I2 is pinned.
  suggested direction: drop the vacuous case, or make it a balanced 65-level object in a valid shape.
- [INFO] I1 read_decisions still uses bare json.load and does not catch RecursionError (hooks/guard/dialog.py:228-231)  in_scope: no
  why it matters: a 200000-deep .ai/state/decision.json would raise an uncaught RecursionError in the gate hook; only state.py writes that file. Risk-register item, LOW inside the boundary.
- [INFO] I2 The ch in "[{" loop assumes str input (dialog.py:84)  in_scope: yes
  why it matters: callers pass fh.read() from a text handle; a bytes input would raise TypeError, which read_profile does not catch. No caller can pass it today.

## EXAMINED AND CLEAN
Scanner correctness (strings, \" and \\ before a closing quote, non-ASCII, BOM same as before, 64 passes / 65 raises); real files read as before; hot-path cost ~0.04 ms on the real profile.json; cap tests fail without the fix; timing test still catches a persistent slowdown, budget kept; L1/L2 of the original review done; verify log Ran 1137 tests OK (skipped=5); scope six files; no BLOCKER.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the plan: six files, the declared L1/L2/I1/I2 items, and the timing-test stabilisation. No behaviour changes for any file nested up to 64 levels.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/guard/dialog.py | +28 −2 | Edit |
| hooks/guard/git.py | +2 −1 | Edit |
| skills/ai-task/state.py | +34 −6 | Edit |
| tests/test_dialog_consent.py | +1 −0 | Edit |
| tests/test_dialog_contract.py | +39 −0 | Edit |
| tests/test_dialog_gate.py | +10 −6 | Edit |

+114 −15 lines, 6 files

## Verdict

close: closed
facts: (a) green — suite green on 086a20ccd (run 1) · (b) green — 6 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 1 · review passes: 1
