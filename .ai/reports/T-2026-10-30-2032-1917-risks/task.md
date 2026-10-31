# T-2026-10-30-2032-1917-risks — Fix the open risks of T-2026-10-30-1917 (0007 object examples/paths, JSON type names, direction tests, converts_clean, _add note str)

bugfix · full · started 2026-10-30T20:32:16Z · claude

## Weight

```
scope          2  skills/project-update/migrations/0007_weight_model.py referenced from 21 files
behaviour      2  "changes the project-update migration 0007 conversion and the MigrationContext._add contract" (d
reversibility  2  skills/project-update/migrations/0007_weight_model.py matches needs_step **/migrations/**; hint 
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       1  1 of 2 code files have a test
W 9 → full   hints reversibility +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T20:32:15Z — /rr-build-all inline plan: the five open risks of T-2026-10-30-1917

## Plan

files: skills/project-update/migrations/0007_weight_model.py, skills/project-update/update.py, tests/test_project_update.py
tests: tests/test_project_update.py
- m1 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done
- l1 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done · after m1
- l2 · tests/test_project_update.py · tests/test_project_update.py · done · after m1, l1
- l3 · tests/test_project_update.py · tests/test_project_update.py · done · after m1, l1, l2
- note · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done · after m1, l1, l2, l3

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2032-1917-risks for implementation? (gate: human_approval)
asked: 2026-10-30T20:45:57Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T20:47:46Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 21a993f0d | .ai/state/logs/T-2026-10-30-2032-1917-risks/suite-1.log | no |
| 2 | e2e | 0 | 21a993f0d | .ai/state/logs/T-2026-10-30-2032-1917-risks/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
No BLOCKER, HIGH or MEDIUM. Four LOW (test/doc gaps; none changes what a user project ends up with).
- [LOW] L1 The new note-must-be-str contract is not written into the migration contract (skills/project-update/migrations/README.md:24, :53-55) in_scope: yes — README says content is bytes, never that a note / delete reason / edit_text note must be str; the next migration author finds out from a SchemaError (exit 2). README is outside the task's files: risk register.
- [LOW] L2 The R-638a test checks the message but not the refusal (tests/test_project_update.py:2216-2227) in_scope: yes — rc is discarded; assert rc == 2 (update.py:2043) as test_a_migrations_own_recursion_error… does at line 2130.
- [LOW] L3 Two goal-named conflict cases have no test: a boolean, and a string `paths` (tests/test_project_update.py:345-351) in_scope: yes — add {"tiers":{"T1":{"examples":true}}} and {"path_scopes":[{"scope":"payments","paths":"abc"}]}; regression pins only (old tree conflicted too).
- [LOW] L4 A new test's docstring contradicts the code (tests/test_project_update.py:242-244) in_scope: yes — says convert never writes a top-level `tests` key; _writes emits ("set", ("tests", …)) when weight.json holds the shipped value (0007_weight_model.py:150-155); the test passes because the edited `tests` no longer matches the template.
- [INFO] I1 assert_no_conflict requires " 0 conflict(s)" for the whole run (tests/test_project_update.py:235-241) in_scope: yes — stricter than "no 0007 conflict"; not a false pass (", 10 conflict(s)" does not match).
- [INFO] I2 _kind still falls back to the Python type name (0007_weight_model.py:194) in_scope: no — unreachable from json.loads values.
EXAMINED AND CLEAN: M1 object values through _writes/_shipped; _bad tuple want prints "not a list"; every _kind/_an message; every _add caller in update.py, shipped migrations and fixtures passes a str note (rules_update, adopt.py call plan.add); every new test red on the pre-fix tree (L2 on 1d623cf~1); L3 regex matches the report row format (update.py:1920); no assertion weakened; scope: only the three task files.
## VERDICT
verdict: pass
scope_assessment: inside the approved plan; only the three task files; each goal item maps to one step. L1 (README) needs a scope change and belongs in the risk register.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/0007_weight_model.py | +13 −5 | Edit |
| skills/project-update/update.py | +3 −0 | Edit |
| tests/test_project_update.py | +112 −17 | Edit |

+128 −22 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 21a993f0d (run 1) · (b) green — 3 changed files, all in the task's files
gate: requested G1 at 2026-10-30T20:45:57Z; approved by Ivan Kakurov at 2026-10-30T20:47:46Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
