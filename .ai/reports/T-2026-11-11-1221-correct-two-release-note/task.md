# T-2026-11-11-1221-correct-two-release-note — Correct two release-note claims: which installer menus highlight a detected or recorded choice (L1), and that the D3 Enter change holds with the menu on (L2)

feature · light · started 2026-11-11T12:21:16Z · claude

## Weight

```
scope          2  CHANGELOG.md referenced from 30 files
behaviour      0  wording of two docs only; no code (declared)
reversibility  0  git revert returns everything
domain         0  no code path changes (declared)
novelty        0  a sentence in CHANGELOG and README (declared)
coverage       0  no code file declared
W 2 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: CHANGELOG.md, README.md
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 78124a25c | .ai/state/logs/T-2026-11-11-1221-correct-two-release-note/suite-1.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +2 −2 | Edit |
| README.md | +2 −1 | Edit |

+4 −3 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 78124a25c (run 1) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 2 · suite runs: 1 · review passes: 0
