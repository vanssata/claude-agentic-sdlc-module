# T-2026-10-29-1940-speed-up-tests-test-ai — Speed up tests/test_ai_task_state.py: bytecode shim in Project.run if >=30% per call, per-module template repo copied per test; same 174 ids, no assert removed

refactoring · light · started 2026-10-29T19:40:34Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 27 files
behaviour      1  keyword 'workflow' in tests/test_ai_task_state.py
reversibility  0  git revert returns everything
domain         0  tests only
novelty        0  tests only
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → light by Ivan Kakurov at 2026-10-29T19:40:34Z — plan faster-task-cycle 1F: test-only refactoring

## Plan

files: tests/test_ai_task_state.py
tests: tests/test_ai_task_state.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 7580b9089 | .ai/state/logs/T-2026-10-29-1940-speed-up-tests-test-ai/step-1.log | no |
| 2 | suite | 0 | - | .ai/state/logs/T-2026-10-29-1940-speed-up-tests-test-ai/suite-2.log | no |
| 3 | suite | 0 | d50be0436 | .ai/state/logs/T-2026-10-29-1940-speed-up-tests-test-ai/suite-3.log | no |

suite passing · e2e not_required · suite runs 2

## Review

none yet

## Changes

measured at close

## Verdict

close: open — edit, then 'state.py verify --scope all', then 'state.py close'
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 0
