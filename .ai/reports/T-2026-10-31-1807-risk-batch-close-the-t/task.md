# T-2026-10-31-1807-risk-batch-close-the-t — Risk batch: close the T-1529 review leftovers (RecursionError pins and readers, reject atomicity) and the dialog-background follow-ups (opt-in limited to non-SDK entrypoints, one AI_UNATTENDED rule, consent pin, duplicate-question refusal, spec)

bugfix · guarded · started 2026-10-31T18:07:30Z · claude

## Weight

```
scope          2  skills/ai-task/weight.py referenced from 130 files
behaviour      2  narrows background_sessions to non-SDK entrypoints and changes how AI_UNATTENDED=0 reads on the 
reversibility  0  git revert returns everything
domain         0  developer tooling, no money, identity or personal data (declared)
novelty        0  same except-tuple widening as T-1529; the opt-in and AI_UNATTENDED readers already exist (declar
coverage       1  7 of 8 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, skills/ai-task/weight.py, hooks/guard/dialog.py, hooks/runtime-gate.py, hooks/context-guard.py, hooks/update_notice.py, hooks/guard/paths.py, skills/project-update/adopt.py, docs/hooks.md, docs/sdlc/specs/command-choice-dialog.md, tests/test_ai_task_state.py, tests/test_runtime_gate.py, tests/test_context_guard.py, tests/test_update_notice.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py
tests: tests/test_ai_task_state.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_update_notice.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py
- s1 · skills/ai-task/state.py, skills/ai-task/weight.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · in_progress
- s2 · hooks/context-guard.py, hooks/guard/dialog.py, hooks/update_notice.py, hooks/runtime-gate.py, tests/test_context_guard.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_update_notice.py, tests/test_runtime_gate.py · tests/test_context_guard.py, tests/test_dialog_gate.py, tests/test_update_notice.py, tests/test_runtime_gate.py · pending · after s1
- s3 · hooks/guard/dialog.py, skills/ai-task/state.py, hooks/runtime-gate.py, hooks/guard/paths.py, skills/project-update/adopt.py, tests/test_dialog_contract.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py, tests/test_ai_task_state.py · tests/test_dialog_contract.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py · pending · after s2
- s4 · skills/ai-task/state.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_task_state.py · tests/test_dialog_consent.py, tests/test_dialog_gate.py · pending · after s3
- s5 · docs/sdlc/specs/command-choice-dialog.md, docs/hooks.md · no tests · pending · after s4

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|

suite not_run · e2e not_run · suite runs 0

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: abandoned
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 1 · suite runs: 0 · review passes: 0
