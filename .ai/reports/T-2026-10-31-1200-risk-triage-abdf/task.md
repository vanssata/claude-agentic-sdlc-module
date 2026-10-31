# T-2026-10-31-1200-risk-triage-abdf — Risk triage A, B, D, F: read_decisions RecursionError and five test pins

feature · guarded · started 2026-10-31T12:00:53Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in tests/test_ai_task_state.py
reversibility  0  git revert returns everything
domain         1  dialog gate reader; no consent route changes (declared)
novelty        0  one except tuple and tests in existing code (declared)
coverage       0  1 of 1 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T12:00:53Z — /rr-build-all ~/.claude/plans/risk-triage-a-b-d-f.md (FIX_NOW rows of the A/B/D/F triage)

## Plan

files: hooks/guard/dialog.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
tests: tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
- s1 · hooks/guard/dialog.py, tests/test_dialog_gate.py · tests/test_dialog_gate.py · done
- s2 · tests/test_dialog_contract.py · tests/test_dialog_contract.py · done
- s3 · tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s4 · tests/test_profile_detect.py · tests/test_profile_detect.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 6712f64f5 | .ai/state/logs/T-2026-10-31-1200-risk-triage-abdf/suite-1.log | no |
| 2 | e2e | 0 | 6712f64f5 | .ai/state/logs/T-2026-10-31-1200-risk-triage-abdf/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 test_read_decisions_survives_deep_nesting pins the reader but not the gate (tests/test_dialog_gate.py)  in_scope: yes
  why it matters: only the "[" * 200000 half can fail on a regression; no test shows gate() still allows when decision.json is corrupt, so a later change of [] into a deny goes unseen.
  suggested direction: optional — one hook-level case that a deep decision.json gives an Allow.
- [LOW] L2 read_only_ledger skip is correct for the suite's uid, but its root branch is never exercised (tests/test_ai_task_state.py:2138-2142)  in_scope: yes
  why it matters: as non-root both tests run; on a filesystem that ignores modes the settle-write-failure path is silently untested — a strict improvement over failing.
  suggested direction: none needed.
- [INFO] I1 The ambiguity test pins a dead end (tests/test_dialog_gate.py, test_two_decisions_sharing_question_text_decline_ambiguous)  in_scope: yes
  why it matters: two open decisions with identical question text can never be answered through the dialog; not shown that decision open prevents it or that it falls back to the terminal.
  suggested direction: record whether decision open can create two decisions with the same question text.
- [INFO] I2 The RecursionError clause in read_profile is not what the 200000 case tests (tests/test_dialog_contract.py:124-137)  in_scope: no
  why it matters: json_loads_capped raises ValueError above 64 first; the clause is harmless defence.
  suggested direction: none.
- [INFO] I3 state.py read_decisions has the same hole this task closed in the hook (skills/ai-task/state.py:2625-2635)  in_scope: no
  why it matters: catches (OSError, ValueError) only; a too-deep decision.json tracebacks decision show and profile detect --open, contradicting "exit 0 always (R36.16)". Only state.py writes that file.
  suggested direction: register it; one-token fix plus a test.

## EXAMINED AND CLEAN
dialog.py:229 — gate unchanged in effect (RecursionError went to check's except Exception → allow; now [] → Allow); recorder writes no ledger line either way. Claim 1 fails before. No interpreter dependence found. read_profile cases not vacuous, at-cap catches off-by-one. Scanner table discriminates escape handling. Part-question test non-vacuous over both runtimes. Ambiguity test matches dialog.py:637/645. Codex ack test covers round trip and independence with the isolated home. Only five declared files; no loosened assertions.

## VERDICT
verdict: pass
scope_assessment: Inside the approved plan. One except-tuple token in production, plus test pins. Nothing was refactored.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/guard/dialog.py | +1 −1 | Edit |
| tests/test_ai_task_state.py | +2 −0 | Edit |
| tests/test_dialog_contract.py | +50 −4 | Edit |
| tests/test_dialog_gate.py | +48 −0 | Edit |
| tests/test_profile_detect.py | +36 −0 | Edit |

+137 −5 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on 6712f64f5 (run 1) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
