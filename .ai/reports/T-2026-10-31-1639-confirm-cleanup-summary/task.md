# T-2026-10-31-1639-confirm-cleanup-summary — update.py dry-run summary names --confirm-cleanup for [cleanup] rows and --confirm-delete for the rest, instead of --confirm-delete for all

bugfix · guarded · started 2026-10-31T16:39:29Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 194 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  0  git revert returns everything
domain         0  "one printed summary line of a dry run, no money or identity or personal data" (declared)
novelty        0  "the per-row note at update.py:1978 already splits cleanup from delete" (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/project-update/update.py, tests/test_project_update.py
tests: tests/test_project_update.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 2 | 50b14e20e | .ai/state/logs/T-2026-10-31-1639-confirm-cleanup-summary/step-1.log | yes |
| 2 | step | 1 | 50b14e20e | .ai/state/logs/T-2026-10-31-1639-confirm-cleanup-summary/step-2.log | yes |
| 3 | step | 0 | 142b899cb | .ai/state/logs/T-2026-10-31-1639-confirm-cleanup-summary/step-3.log | no |
| 4 | suite | 0 | 142b899cb | .ai/state/logs/T-2026-10-31-1639-confirm-cleanup-summary/suite-4.log | no |
| 5 | e2e | 0 | 142b899cb | .ai/state/logs/T-2026-10-31-1639-confirm-cleanup-summary/e2e-5.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [INFO] I1 update.py:2124-2126 — the `--check` path has its own summary, "N deletion(s) a human must confirm", which counts cleanup and regular deletions together. It names no flag, so it is not wrong. Not part of this task's goal or diff. in_scope: yes (note only, no action)
- [INFO] I2 adopt.py:1705 prints its own "N deletion(s) awaiting --confirm-delete". That is the `--adopt --cleanup` path, which really is behind `--confirm-delete` (Plan.delete docstring, update.py:~757). Correct and untouched. in_scope: yes (note only)
- [INFO] I3 The old summary text also appears in docs/sdlc/plans/adaptive-cross-runtime-sdlc-wp1-schema-migrations.md:69 and docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp1-schema-migrations.md:227. Both describe the regular-deletion form, which is unchanged, and are historical specs. The spec example has no cleanup row. in_scope: no

No BLOCKER, HIGH, MEDIUM or LOW findings.

## VERDICT
verdict: pass
scope_assessment: Stayed inside the plan: a single printed summary line and its test pin.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/update.py | +6 −2 | Edit |
| tests/test_project_update.py | +3 −0 | Edit |

+9 −2 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 142b899cb (run 4) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 1
