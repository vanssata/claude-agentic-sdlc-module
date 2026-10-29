# T-2026-10-27-002 — Redesign 3.3b: port the four state-side shell suites to Python unittest twins and delete them (e2e keeps a one-line wrapper)

refactoring · guarded · started 2026-10-27T08:34:53Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 9 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  test files only, no shipped code (declared)
novelty        0  same pattern as 3.3a guard twins (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test-ai-task-state.sh, tests/test-ai-task-sensors.sh, tests/test_ai_status_root.py, tests/test-ai-status-root.sh, tests/test_end_to_end.py, tests/test-end-to-end.sh, tests/run-all.sh, .ai/project/known-risks.md
tests: tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_ai_status_root.py, tests/test_end_to_end.py, tests/test_suite_parity.py
- s1 · tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test-ai-task-state.sh, tests/test-ai-task-sensors.sh · tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_suite_parity.py · done
- s2 · tests/test_ai_status_root.py, tests/test-ai-status-root.sh · tests/test_ai_status_root.py, tests/test_suite_parity.py · done
- s3 · tests/test_end_to_end.py, tests/test-end-to-end.sh, tests/run-all.sh, .ai/project/known-risks.md · tests/test_end_to_end.py, tests/test_suite_parity.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 2 | 268ff1d3e | .ai/state/logs/T-2026-10-27-002/step-1.log | no |
| 2 | step | 0 | 268ff1d3e | .ai/state/logs/T-2026-10-27-002/step-2.log | no |
| 3 | step | 0 | 0b5f70780 | .ai/state/logs/T-2026-10-27-002/step-3.log | no |
| 4 | step | 0 | fcefd0283 | .ai/state/logs/T-2026-10-27-002/step-4.log | no |
| 5 | suite | 0 | fcefd0283 | .ai/state/logs/T-2026-10-27-002/suite-5.log | no |
| 6 | e2e | 0 | fcefd0283 | .ai/state/logs/T-2026-10-27-002/e2e-6.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The Python twin checks "SCOPE_CHANGE_REQUIRED" as a substring of the guard's whole stdout+stderr; the shell checked only `.hookSpecificOutput.permissionDecisionReason`. A guard that put the signal in another field or on stderr would pass now and failed before. No such output exists today: both deny paths carry it in the reason. — tests/test_end_to_end.py (the two `"SCOPE_CHANGE_REQUIRED" in out` checks, Claude and Codex) — in_scope: yes
- [LOW] L2 "the context guard is installed into Codex too" uses `os.path.lexists`; the shell used `[ -e ]`. A dangling symlink at `hooks/context-guard.py` would pass now and failed before. install.sh copies files, so this is theoretical. — tests/test_end_to_end.py (`os.path.lexists(os.path.join(chooks, "context-guard.py"))`) — in_scope: yes
- [INFO] I1 R13 parity can no longer check the e2e pair: `TWIN_OF = "test-end-to-end.sh"` still points at the wrapper, which has no `pass` labels, so the pair passes with nothing to compare. `SHELL_MECHANICS` is a dead constant that nothing reads. A hand comparison of the deleted shell suites' 77 labels against the twins' strings, using the parity module's own functions (10, 17, 13 and 37 labels in the four suites), found none missing; parity matches any string constant anywhere in the twin, so it is a weak guard. — tests/test_end_to_end.py:22-27 — in_scope: yes
- [INFO] I2 `.ai/policies/testing.md` lines 94 and 143-144 still name the deleted suites and the old "end to end: N passed" output; the known-risks entry already records this. — .ai/policies/testing.md — in_scope: no (needs a file outside the boundary)

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +11 −2 | Edit |
| tests/run-all.sh | +2 −2 | Edit |
| tests/test-ai-status-root.sh | +0 −106 | Delete |
| tests/test-ai-task-sensors.sh | +0 −139 | Delete |
| tests/test-ai-task-state.sh | +0 −46 | Delete |
| tests/test-end-to-end.sh | +2 −170 | Edit |
| tests/test_ai_status_root.py | +209 −0 | New |
| tests/test_ai_task_sensors.py | +196 −0 | New |
| tests/test_ai_task_state.py | +75 −1 | Edit |
| tests/test_end_to_end.py | +217 −2 | Edit |

+712 −468 lines, 10 files

## Verdict

close: closed
facts: (a) green — suite green on fcefd0283 (run 5) · (b) green — 10 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
