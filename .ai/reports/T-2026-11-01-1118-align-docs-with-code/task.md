# T-2026-11-01-1118-align-docs-with-code — Align docs with code: --confirm-cleanup, update.py exit codes, tracked-ignored hint, BATCH_DEFAULTS and the journal cap in their rr_state modules

feature · light · started 2026-11-01T11:18:58Z · claude

## Weight

```
scope          2  docs/project-update.md referenced from 158 files
behaviour      0  docs only (declared)
reversibility  0  git revert returns everything
domain         0  documents only
novelty        0  corrects text to existing code (declared)
coverage       0  no code file declared
W 2 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: docs/project-update.md, docs/weight.md, docs/local-memory.md
tests: tests/test_shared_prompts_model_free.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | b68747011 | .ai/state/logs/T-2026-11-01-1118-align-docs-with-code/suite-1.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/local-memory.md | +1 −1 | Edit |
| docs/project-update.md | +14 −3 | Edit |
| docs/weight.md | +1 −1 | Edit |

+16 −5 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on b68747011 (run 1) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 2 · suite runs: 1 · review passes: 0
