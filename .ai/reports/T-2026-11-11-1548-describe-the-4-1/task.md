# T-2026-11-11-1548-describe-the-4-1 — Describe the 4.1 installer menus, the flags that skip them and RISKRAILS_MENU in installation.md and getting-started.md (closes review L3 of T-2026-11-11-1147)

feature · light · started 2026-11-11T15:48:27Z · claude

## Weight

```
scope          2  docs/installation.md referenced from 43 files
behaviour      0  docs wording only (declared)
reversibility  0  git revert returns everything
domain         0  no code path changes (declared)
novelty        0  the README paragraph from 8f32901, adapted (declared)
coverage       0  no code file declared
W 2 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: docs/installation.md, docs/getting-started.md
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | bb039d2f5 | .ai/state/logs/T-2026-11-11-1548-describe-the-4-1/suite-1.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/getting-started.md | +6 −1 | Edit |
| docs/installation.md | +10 −0 | Edit |

+16 −1 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on bb039d2f5 (run 1) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 2 · suite runs: 1 · review passes: 0
