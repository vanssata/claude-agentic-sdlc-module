# T-2026-10-31-1414-risk-triage-rest-state — Risk triage rest: state.py read_decisions survives deep nesting; gate Allow on deep decision.json pinned

bugfix · guarded · started 2026-10-31T14:14:12Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 44 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         1  decision.json reader; no consent route changes (declared)
novelty        0  one except tuple and tests in existing code (declared)
coverage       0  1 of 1 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T14:14:12Z — /rr-build-all ~/.claude/plans/risk-triage-rest.md (FIX_NOW rows of the remaining-risk triage)

## Plan

files: skills/ai-task/state.py, tests/test_ai_task_state.py, tests/test_dialog_gate.py
tests: tests/test_ai_task_state.py, tests/test_dialog_gate.py
- s1 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s2 · tests/test_dialog_gate.py · tests/test_dialog_gate.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 8c2ad1f67 | .ai/state/logs/T-2026-10-31-1414-risk-triage-rest-state/suite-1.log | no |
| 2 | e2e | 0 | 8c2ad1f67 | .ai/state/logs/T-2026-10-31-1414-risk-triage-rest-state/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 valid_decisions still lets a too-deep decision.json traceback (skills/ai-task/state.py:2929-2939)  in_scope: yes
  why it matters: bare json.load catching (OSError, ValueError, KeyError, TypeError), not RecursionError; the last decision.json reader without it. Path human_route(allow_dialog=True) -> dialog_pick -> valid_decisions, reached by approve/reject (line 2303) with the dialog on; tracebacks there (sync_dialog/prune_decisions now swallow it, valid_decisions does not). Fails closed (no approval granted), not a security hole. Same class as 588e. Not confirmed by running (guard refuses writing .ai/state/decision.json from the shell); read from the code.
  suggested direction: add RecursionError to that except tuple or read through json_loads_capped; add a dialog-on approve/reject case. If deferred, register as a risk.
- [LOW] L1 profile detect --open, the second command 588e names, has no test (tests/test_ai_task_state.py:2243)  in_scope: yes
  why it matters: correct by construction (open_drift -> read_decisions die() -> SystemExit handler at state.py:887 -> decision: None, exit 0, R36.16 holds), but only decision show is pinned; nothing guards the SystemExit handler / RecursionError interplay.
  suggested direction: one case: deep decision.json, profile detect --open --detect-runtime ... in drift, assert rc 0 and no Traceback; or close 588e as partial.
- [INFO] I1 Exit code conflict with R36.16 does not exist (skills/ai-task/state.py:884-889)  in_scope: yes
  why it matters: decision show die()s exit 1 as for malformed JSON; profile detect --open catches the die, exit 0; a harmless stderr line.
## EXAMINED AND CLEAN
- read_decisions fix: one-word catch addition, same die() path as malformed JSON.
- prune_decisions: only a RecursionError traceback becomes the silent return malformed JSON already took; runs for MUTATING_COMMANDS | {approve, reject, decision} via sync_dialog.
- test red-first quality: decision show runs prune_decisions then read_decisions, so the test fails if either catch is removed; passes on the tree (ran it).
- test_gate_allows_on_too_deep_decision_json passes; honestly a regression pin.
- other json.loads: read_profile and dialog_* already catch RecursionError; session and --plan-file readers out of scope.
- scope: three allowed files, two catch edits, two tests; no refactoring, no weakened test. Behaviour 0-1.
## VERDICT
verdict: pass_with_findings
scope_assessment: inside the plan; 588e closed for decision show and the prune path; profile detect --open correct but unpinned; valid_decisions leaves a same-class residual on approve/reject with the dialog on.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/ai-task/state.py | +2 −2 | Edit |
| tests/test_ai_task_state.py | +14 −0 | Edit |
| tests/test_dialog_gate.py | +6 −0 | Edit |

+22 −2 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 8c2ad1f67 (run 1) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
