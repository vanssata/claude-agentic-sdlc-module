# T-2026-10-30-1806-fix-the-open-risks-of-t — Fix the open risks of T-2026-10-30-1744 (deep-JSON RecursionError paths, unreachable clause, stacked weight-mirror hints, rr-setup untrack wording)

feature · guarded · started 2026-10-30T18:06:35Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 243 files
behaviour      1  keyword 'messenger' in skills/rr-setup/SKILL.md
reversibility  0  git revert returns everything
domain         0  "no auth, payments, secrets or personal data; the project-update merge of local JSON/markdown" (
novelty        0  "the RecursionError-to-conflict pattern already exists in three_way (update.py:927-936)" (declar
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T18:06:34Z — /rr-build-all open risks of T-2026-10-30-1744

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, skills/rr-setup/SKILL.md
tests: tests/test_project_update.py, tests/test_skills_surface.py, tests/test_instruction_budget.py
- s1 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · skills/rr-setup/SKILL.md · tests/test_skills_surface.py, tests/test_instruction_budget.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 53f817dd3 | .ai/state/logs/T-2026-10-30-1806-fix-the-open-risks-of-t/suite-1.log | no |
| 2 | e2e | 0 | 53f817dd3 | .ai/state/logs/T-2026-10-30-1806-fix-the-open-risks-of-t/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
No BLOCKER and no HIGH. Two LOW, three INFO. Every in-scope claim closes against the code.

- [LOW] L1 edit_json's second RecursionError catch also wraps the migration's own `fn` (`skills/project-update/update.py:697-704`)  in_scope: yes
  why it matters: a migration bug that raises RecursionError (unbounded recursion in `fn`) is reported as "nested too deeply, so this migration could not run" and holds the schema. Before the change it crashed loudly. The conflict message then blames the user's file for the migration's bug. No shipped migration does this: 0007 is the only `edit_json` caller and its `convert` is not recursive on user data. The code comment names "the migration's edit" as covered, so the trade-off is deliberate.
  suggested direction: accept it, or separate `fn` from the copy/compare/dump guard.

- [LOW] L2 No test pins the `dump_json(merged)` guard in three_way or the `dump_json(after)` guard in edit_json (`update.py:702`, `update.py:953`)  in_scope: yes
  why it matters: the brief asked for a test per path that crashes on the base tree. These two guards are not covered, but the implementer's unreachability claim holds. I measured `dump_json` handling 19000 levels. `deepcopy` fails at 498 levels, `leaf_changes` at 994, and `d == copy.deepcopy(d)` at 497. The only unmeasured step is `merge_json` on differing trees. `json.loads` fails past ~20000 levels, so the `dump_json` guards are defensive only. If `dump_json`'s encoder changes, they are untested.
  suggested direction: leave it; the code comment already says guard-only.

- [INFO] I1 `read_json` returns None on RecursionError and records a conflict, so 0007 still creates a default `weight.json` (`update.py:632-637`, `migrations/0007_weight_model.py:172-180`)  in_scope: yes
  The only caller of `read_json` is 0007 at line 172. With `old=None` and `weight.json` absent, line 180 runs `ctx.create(NEW, template)`. It creates a default table and does not overwrite anything. `risk-tiers.json` is untouched and `MOVES=[]`. The conflict holds the schema through `plan.held` (`update.py:1538`). VERSION is not bumped. The code comment ("None would let a migration create or overwrite what it cannot read") is slightly overstated, because the create still happens. Same behaviour as the existing invalid-JSON case.

- [INFO] I2 Migration 0007 `_loads` (`migrations/0007_weight_model.py:56`, called at line 185) still crashes on a 200000-level `weight.json`  in_scope: no
  `_loads` catches only `(TypeError, ValueError)`. Pre-existing; the base tree crashed earlier at `edit_json`. Goes to the risk register, not to remediation. Severity inside the boundary would be LOW.

- [INFO] I3 The `read_json` and `edit_json` conflicts are not de-duplicated  in_scope: yes
  Repeated reads of the same deep file add repeated conflict rows. Cosmetic; today there is one reader.

## EXAMINED AND CLEAN
- M1 closes: the new test fails with RecursionError from three_way's json.loads when the clause is removed.
- L2 tests fail on the base tree; each pins its own clause (removed in turn, matching test failed).
- L4 test fails on base; rendering_raised suppresses the stale hint only when the renderer raised.
- L1 is a no-behaviour-change removal.
- three_way merge restructure is equivalent.
- SKILL.md L3 wording accurate against update.py.
- Scope: only the three task files changed.
- Verify logs: suite-1 Ran 1062 tests OK (skipped=5); e2e-2 Ran 5 OK.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the plan: three files, only the five named risks. Every BLOCKER-class claim from the brief is pinned by a test that fails without its clause. The two LOWs are optional and the INFO rows do not move the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/update.py | +25 −7 | Edit |
| skills/rr-setup/SKILL.md | +5 −4 | Edit |
| tests/test_project_update.py | +64 −0 | Edit |

+94 −11 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 53f817dd3 (run 1) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 1
