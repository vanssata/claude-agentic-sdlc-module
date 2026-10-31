# T-2026-10-30-1347-rr-setup-update — rr-setup --update: regenerate the derived .ai/policies/weight.md from the project's weight.json instead of three-way merging it with the template (false conflict on every update, R-weight-md-conflict-recurs-on-every-rr-se-1d6e)

bugfix · guarded · started 2026-10-30T13:47:00Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 231 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data; a plugin update script (declared)
novelty        0  the same pattern update.py used for the risk-tiers mirror until b7f3058 (declared)
coverage       0  2 of 2 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/project-update/update.py, skills/ai-task/weight.py, tests/test_project_update.py, README.md
tests: tests/test_project_update.py
amended 2026-10-30T13:54:52Z: +README.md — the README test count follows the two new tests (1042 -> 1044)

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | e31d64b65 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-1.log | yes |
| 2 | step | 1 | 914dccf81 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-2.log | no |
| 3 | step | 1 | 43b331b65 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-3.log | no |
| 4 | step | 1 | 179ff125e | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-4.log | no |
| 5 | step | 0 | 396d4c072 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-5.log | no |
| 6 | suite | 0 | 396d4c072 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/suite-6.log | no |
| 7 | e2e | 0 | 396d4c072 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/e2e-7.log | no |
| 8 | step | 0 | 6df97c583 | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/step-8.log | no |
| 9 | suite | 0 | 70302a98c | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/suite-9.log | no |
| 10 | e2e | 0 | 70302a98c | .ai/state/logs/T-2026-10-30-1347-rr-setup-update/e2e-10.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 "Faithful mirror" detection is byte-equality with the *current* renderer, so a future renderer change resurrects the conflict (skills/project-update/update.py:866). A weight.md rendered by an older plugin's mirror() no longer equals render_weight(disk); falls to three_way; sha line differs; conflict every update until a human runs state.py weight --mirror. The header already carries the sha of the JSON it was rendered from. Suggested: decide whether "faithful" means header sha matches disk JSON, or byte-equal to today's render; document if the latter is intended.
- [MEDIUM] M2 Tests pin only the happy path; the fallbacks that protect a human's data are untested (tests/test_project_update.py:1576-1621): hand-edited weight.md must still go to three_way; stale mirror; missing weight.md created; the except branch (valid JSON, wrong shape); symlinked or absent weight.json. Removing the ours == render(disk) guard keeps both new tests green. Test 1's assertNotIn("weight.md", out) is broad. Suggested: one test for a hand-edited mirror not overwritten, one for an unrenderable JSON falling back without a crash.
- [LOW] L1 Stray whitespace edit: SDLC_TEMPLATES =(( lost its space (tests/test_project_update.py:1623). Revert.
- [LOW] L2 RecursionError (and OSError from the temp dir, an import failure in weight_module()) not caught (update.py:868): a crash of the whole plan instead of the text-merge fallback; not realistic input. Suggested: catch Exception around the render.
- [LOW] L3 An aborted apply between the weight.json and weight.md writes leaves the mirror stale; the next run conflicts until a human regenerates it.
- [INFO] I1 Behaviour checked unchanged: missing weight.md created via three_way; weight.json absent on disk (0007 in the same run) falls back; symlinked weight.json falls back; symlinked weight.md as before; CRLF checkouts conflict as before.
## EXAMINED AND CLEAN
Apply precondition (seen recorded before add); ordering (JSON walked first, plan.removed honoured); JSON conflict path adds nothing; idempotency; a migration-planned weight.md falls back; --check counting; renderer loading; scope (README 1044 matches).
## VERDICT
verdict: pass_with_findings
scope_assessment: Inside the stated bugfix; the one unrelated edit is the accidental whitespace change (L1). M1 and M2 are the items worth acting on before commit.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +1 −1 | Edit |
| skills/project-update/update.py | +49 −1 | Edit |
| tests/test_project_update.py | +56 −0 | Edit |

+106 −2 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 70302a98c (run 9) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 2 · review passes: 1
