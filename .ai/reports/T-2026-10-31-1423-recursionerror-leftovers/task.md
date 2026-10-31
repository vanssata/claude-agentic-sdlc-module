# T-2026-10-31-1423-recursionerror-leftovers — RecursionError leftovers of T-2026-10-31-1414: valid_decisions and the other .ai/state readers of state.py; pin profile detect --open on a deep decision.json

bugfix · guarded · started 2026-10-31T14:23:30Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 46 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  "error handling of local files only; no auth, money or data" (declared)
novelty        0  "same except-tuple pattern as R-...-588e in T-2026-10-31-1414" (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T14:23:30Z — /rr-build-all: review leftovers aa6e and bc09 of T-2026-10-31-1414

## Plan

files: skills/ai-task/state.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
tests: tests/test_ai_task_state.py, tests/test_profile_detect.py
- s1 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s2 · tests/test_profile_detect.py · tests/test_profile_detect.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | f17bd54c2 | .ai/state/logs/T-2026-10-31-1423-recursionerror-leftovers/suite-1.log | no |
| 2 | e2e | 0 | f17bd54c2 | .ai/state/logs/T-2026-10-31-1423-recursionerror-leftovers/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 The consent.jsonl pin cannot tell the two ledger fixes apart, and it does not pin what the fix does. (tests/test_ai_task_state.py:2502-2506) in_scope: yes
  why it matters: deep line appended, then `decision show` and `decision settle --id D1`; only assertNotIn("Traceback"). sync_dialog reaches both read_ledger (via prune_decisions) and mirror_ledger, so not vacuous, but reverting only mirror_ledger's hunk would still fail it by trace; nothing asserts skip-the-line behaviour, rc or resulting state; a read_ledger returning [] or settle returning 0 without consuming the pick would also pass.
  suggested direction: assert read_ledger and mirror_ledger directly on {valid, deep, valid}: two entries, two journal events, advanced cursor; in the CLI case assert decision settle's rc and state.
- [LOW] L1 The state.json and session.json cases assert only "same returncode as malformed" and "no Traceback". (tests/test_ai_task_state.py:2497-2500) in_scope: yes
  why it matters: no check that the deep state.json is left untouched (state.py:387) or that read_session returned {}; the equal-rc check covers it in practice.
  suggested direction: one "file content unchanged" assertion for state.json.
- [INFO] I1 read_journal still catches only ValueError per line (skills/ai-task/state.py:334-335) in_scope: no; .ai/reports/, under the recorded readers-outside-.ai/state/ risk.
- [INFO] I2 The hooks' readers of .ai/state/ files catch only ValueError. in_scope: no; hooks/guard/dialog.py:402 read_ledger; hooks/context-guard.py prompt_count, :397, :413, :661; hooks/dialog-gate.py:39; runtime-gate.py:921. A deep consent.jsonl line is now skipped by state.py while the hook's reader raises; the contract fixtures (state.py:2551) have no deep line; the hook's fail-open/closed on the uncaught error not checked.
## EXAMINED AND CLEAN
All seven .ai/state/ readers catch RecursionError, none missed. Each changed path takes the existing malformed path, no new fail-open. Deep decision.json: valid_decisions -> set(), approve exits 5, granted false. New tests green; suite log Ran 1147 tests OK (skipped=5). Isolation clean. Scope: five one-token except edits plus pins.
## VERDICT
scope_assessment: stayed inside the plan; no in_scope BLOCKER or HIGH; I1 and I2 to the risk register.
VERDICT: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/ai-task/state.py | +5 −5 | Edit |
| tests/test_ai_task_state.py | +51 −0 | Edit |
| tests/test_profile_detect.py | +14 −0 | Edit |

+70 −5 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on f17bd54c2 (run 1) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
