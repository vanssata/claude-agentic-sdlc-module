# T-2026-10-30-1917-0007-shape-risks — fix the open risks of T-2026-10-30-1842 and T-2026-10-30-1859: 0007 shape checks only on the nodes convert reads or writes, null where convert writes, hints paths, path scope name, _add deep check, _bad article, empty-tiers test

bugfix · full · started 2026-10-30T19:17:25Z · claude

## Weight

```
scope          2  skills/project-update/migrations/0007_weight_model.py referenced from 19 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/0007_weight_model.py matches needs_step **/migrations/**; hint 
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       1  1 of 2 code files have a test
W 8 → full   hints reversibility +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T19:17:25Z — /rr-build-all: open risks of T-2026-10-30-1842 and T-2026-10-30-1859 (user's plan in the command)

## Plan

files: skills/project-update/migrations/0007_weight_model.py, skills/project-update/update.py, tests/test_project_update.py
tests: tests/test_project_update.py
- s1 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done · after s1

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-1917-0007-shape-risks for implementation? (gate: human_approval)
asked: 2026-10-30T19:30:54Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T20:17:41Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 094d7eb71 | .ai/state/logs/T-2026-10-30-1917-0007-shape-risks/suite-1.log | no |
| 2 | e2e | 0 | 094d7eb71 | .ai/state/logs/T-2026-10-30-1917-0007-shape-risks/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M1 Object-valued `examples` and `paths` are still conflicts, but the pre-18c221f convert converted them without crashing (skills/project-update/migrations/0007_weight_model.py:209, :214). in_scope: yes. R-2 says input the old convert handled without a crash must pass, with an exception only for strings. `{"tiers": {"T1": {"examples": {"the ERP cut-over": 1}}}}` wrote "the ERP cut-over" into examples.light before 18c221f; now a conflict ("tiers.T1.examples is a OrderedDict, not a list"), schema stays 6. Same for `{"path_scopes": [{"scope": "money", "paths": {"src/pay/**": 1}}]}`. Not introduced by this task (HEAD's _bad flagged dicts too). Direction: let a dict through as before, or have the human widen R-2's exception to "not a list" and write it down.
- [LOW] L1 The article fix still yields wrong text for object-valued and null nodes (0007_weight_model.py:189-191, used at :209, :214, :217 and _new_problem). read_json parses with object_pairs_hook=OrderedDict (update.py:633), so _kind is "OrderedDict" and the case-sensitive _an gives "a OrderedDict"; null reads "is a null"; weight.json side shows Python names "dict"/"str" beside JSON "object"/"string". The R-4207 test pins only "an int". Direction: map _kind to JSON names, "is null" without an article, pin an object case and a null case.
- [LOW] L2 The weight.json half of R-8aec has no test pinning the "passes" direction (tests/test_project_update.py:260-275): converts_clean is only called with risk-tiers.json; `"hints": {}` / `"tests": "x"` never run, so restoring unconditional checks keeps every test green. Direction: converts_clean(..., "weight.json") for tests "x", and hints {} with an old table carrying no hint scope.
- [LOW] L3 converts_clean drops the returned schema version (tests/test_project_update.py:262): a conflict on weight.json or any other hold at 6 would still pass. Direction: assert version == "7".
- [INFO] I1 A string leaf in weight.json is a conflict even when the pre-check convert would not have crashed (0007_weight_model.py:241-251) — `value not in "str"` may hold for every value; R-30c9 requires the hints[i].paths conflict and HEAD already conflicted on string leaves under axes. No action.

## EXAMINED AND CLEAN
_writes/convert refactor output-identical (order, axes {}, empty irreversible/needs_step, dedup, scalars, twice-is-once); every old-side crash path covered by _old_problem; R-5f4c correct; every base-side crash path covered by _new_problem incl. null intermediates, non-empty list leaves, hints list and first matching dict's paths; create path unaffected; update.py _add unchanged for str notes, test fails on HEAD; new tests fail on the old tree; R-d16c asserts present; TestMigration0007 18 OK; suite-1.log 1079 tests OK (skipped=5); scope inside the three files.

## VERDICT
verdict: pass
scope_assessment: inside the plan's three files, every hunk maps to a requirement. M1 and L1 are partial gaps against R-8aec's literal rule and R-4207's grammar; neither causes a crash or data loss — a conflict holds the schema, the safe outcome.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/0007_weight_model.py | +74 −47 | Edit |
| skills/project-update/update.py | +3 −2 | Edit |
| tests/test_project_update.py | +56 −0 | Edit |

+133 −49 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 094d7eb71 (run 1) · (b) green — 3 changed files, all in the task's files
gate: requested G1 at 2026-10-30T19:30:54Z; approved by Ivan Kakurov at 2026-10-30T20:17:41Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
