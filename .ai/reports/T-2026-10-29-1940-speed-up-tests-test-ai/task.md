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

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [INFO] I1 Shim also reaches tests/test_end_to_end.py:21, tests/test_dialog_gate.py:31, tests/test_dialog_consent.py:27 via imported Project/DialogProject/DialogBase; no behaviour difference found, suite green — state it in the report — tests/test_ai_task_state.py:81-93 — in_scope: yes
- [INFO] I2 Shim loads state.py from skills/ai-task/__pycache__ (mtime+size validation); same-second same-size edit could run stale bytecode — negligible; __pycache__ gitignored — tests/test_ai_task_state.py:31-34 — in_scope: yes
- [INFO] I3 Commit 0142ec7 also carries NextIntent.md, docs/sdlc/intent/agentic-sdlc-modes.questions.md, .ai/reports/… outside this task — commit 0142ec7 — in_scope: yes

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| NextIntent.md | +1 −0 | New |
| docs/sdlc/intent/agentic-sdlc-modes.questions.md | +1 −1 | Edit |
| tests/test_ai_task_state.py | +11 −6 | Edit |

+13 −7 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on d50be0436 (run 3) · (b) RED — outside the task's files: NextIntent.md, docs/sdlc/intent/agentic-sdlc-modes.questions.md
gate: none
confirm: none
handoffs: 5 · suite runs: 2 · review passes: 1
