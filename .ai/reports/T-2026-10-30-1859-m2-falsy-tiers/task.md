# T-2026-10-30-1859-m2-falsy-tiers — M2 of T-2026-10-30-1842: let a falsy tiers (e.g. []) through 0007 as HEAD did; pin a non-empty list tiers as the conflict

bugfix · full · started 2026-10-30T18:59:51Z · claude

## Weight

```
scope          2  skills/project-update/migrations/0007_weight_model.py referenced from 17 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/0007_weight_model.py matches needs_step **/migrations/**; hint 
domain         0  no auth, payments, secrets or personal data; the project-update merge of local JSON (declared)
novelty        0  one shape check in 0007 aligned with convert, same pattern as path_scopes (declared)
coverage       2  0 of 1 code files have a test
W 7 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py
tests: tests/test_project_update.py

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-1859-m2-falsy-tiers for implementation? (gate: human_approval)
asked: 2026-10-30T19:04:45Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T19:05:16Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | c4adaa13c | .ai/state/logs/T-2026-10-30-1859-m2-falsy-tiers/suite-1.log | no |
| 2 | e2e | 0 | c4adaa13c | .ai/state/logs/T-2026-10-30-1859-m2-falsy-tiers/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [LOW] L1 The new test proves only that the run printed no conflict, not that it succeeded (tests/test_project_update.py:251-256) in_scope: yes
  why it matters: it checks no Traceback and no `conflict .*risk-tiers\.json`; a SchemaError exit 2 or a skipped 0007 would also pass. It does fail on HEAD 376a8ab for the right reason.
  suggested direction: also assert dry/applied returncode 0 and/or that the dry run lists 0007.
- [LOW] L2 `_old_problem` checks a path scope's name with `is not None` where convert crashes only on an unhashable name with a string path (skills/project-update/migrations/0007_weight_model.py:195) in_scope: yes
  why it matters: same kind as M2: falsy non-string names and hashable non-string names (0, 1, true, 1.5) now conflict and hold the schema; at 18c221f they did not crash. From T-1842, untouched here; the human's decision covered tiers only.
  suggested direction: record as a risk for a human decision.
- [INFO] I1 Only the list `["x"]` is pinned, not a string tiers (tests/test_project_update.py:247-249) in_scope: yes — same branch; optional extra case.
- [INFO] I2 `_bad` writes "not a object" (0007_weight_model.py:179) in_scope: yes — predates this diff, already risk L2 of T-1842.

## EXAMINED AND CLEAN
Every falsy tiers (`[]`, `{}`, `""`, `0`, `false`, null, missing) gives why None and matches convert's `(old.get("tiers") or {}).items()`; every truthy wrong type still conflicts, exactly convert's crash set; the edited `["x"]` test fails on 18c221f with a Traceback; the new `[]` test fails on 376a8ab on the conflict regex; no other reader of the project's tiers; create path same; scope two planned files, no test weakened; 82 tests OK, suite-1.log and e2e-2.log written after the last edit.

## VERDICT
verdict: pass
scope_assessment: inside the approved plan, implements exactly the human's M2 decision. L2 is a sibling issue from T-1842 and needs a human call.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/0007_weight_model.py | +1 −1 | Edit |
| tests/test_project_update.py | +9 −2 | Edit |

+10 −3 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on c4adaa13c (run 1) · (b) green — 2 changed files, all in the task's files
gate: requested G1 at 2026-10-30T19:04:45Z; approved by Ivan Kakurov at 2026-10-30T19:05:16Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
