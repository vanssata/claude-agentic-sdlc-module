# T-2026-10-30-2217-risk-burndown-b1-adopt — Risk burndown B1: adopt exit-2 docs, adopt SchemaError test hardening, RISKRAILS_* env filters, weight_mirror fallback tests, schema-11 rollback note

bugfix · guarded · started 2026-10-30T22:17:38Z · claude

## Weight

```
scope          2  skills/project-update/adopt.py referenced from 76 files
behaviour      1  keyword 'messenger' in skills/rr-setup/SKILL.md
reversibility  0  git revert returns everything
domain         0  plugin tooling tests and docs (declared)
novelty        0  tightens existing tests and fixes wording, following existing patterns (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T22:17:38Z — /loop risk burndown B1 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md)

## Plan

files: skills/project-update/adopt.py, skills/rr-setup/SKILL.md, tests/test_project_adopt.py, tests/test_project_update.py, tests/test_migration_0006.py, tests/test_merge_migration.py, tests/test_instruction_budget.py, docs/sdlc/plans/register-batch-2.md
tests: tests/test_skills_surface.py, tests/test_project_adopt.py, tests/test_project_update.py, tests/test_migration_0006.py, tests/test_merge_migration.py, tests/test_instruction_budget.py, tests/test_no_size_tokens.py
- s1 · skills/project-update/adopt.py, skills/rr-setup/SKILL.md · tests/test_skills_surface.py · done
- s2 · tests/test_project_adopt.py · tests/test_project_adopt.py · done
- s3 · tests/test_project_update.py, tests/test_migration_0006.py, tests/test_merge_migration.py, tests/test_instruction_budget.py · tests/test_project_update.py, tests/test_migration_0006.py, tests/test_merge_migration.py, tests/test_instruction_budget.py · done
- s4 · docs/sdlc/plans/register-batch-2.md · tests/test_no_size_tokens.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 7db55a5b5 | .ai/state/logs/T-2026-10-30-2217-risk-burndown-b1-adopt/suite-1.log | no |
| 2 | e2e | 0 | 7db55a5b5 | .ai/state/logs/T-2026-10-30-2217-risk-burndown-b1-adopt/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 (test vacuity) The symlinked-weight.json test has no positive assertion and no rc check (`tests/test_project_update.py:2125-2135`, `test_a_symlinked_weight_json_leaves_the_mirror_to_the_text_merge`)  in_scope: yes
  why it matters: it calls `self.upd(d, merge=True)` and then only runs four `assertNotIn` checks. The exit code is never checked, and nothing says what the run did with `weight.md`. Any early exit that prints none of those strings would pass, and so would a run that never reached `weight_mirror`.
  I could not run a no-guard mutation (read-only). I traced the code instead. With the `islink` guard (`update.py:900`) removed, `disk` would be the real file's bytes, the mirror would equal its render, and `fresh` would be a render of the merged JSON. In the case where the merged JSON equals the project's JSON, that gives no item and no hint, so the test still passes. The test pins "no crash", not "disk is None, so a text merge".
  suggested direction: assert the rc, and assert the positive outcome of the text-merge path (a `weight.md` row or conflict, or no row). Better, show once that it fails with the guard removed.
- [LOW] L1 (test vacuity) The absent-weight.json test has the same weakness (`tests/test_project_update.py:2137-2144`)  in_scope: yes
  why it matters: it has no rc assertion and only `NotIn` checks. An absent weight.json also makes the run create weight.json from the template (JSON is processed first), so the real behaviour is richer than what the test pins. The docstring says "leaves the mirror to the text merge", but nothing observes that merge.
  suggested direction: same as M1.
- [LOW] L2 (test isolation) The adopt test env is stripped by an explicit list, not by the `RISKRAILS_` prefix (`tests/test_project_adopt.py:204-208`)  in_scope: yes
  why it matters: the stated goal is parity with the other files, and the claim about them is true: they strip `RISKRAILS_*` by prefix at `test_project_update.py:96,921`, `test_migration_0006.py:215`, `test_merge_migration.py:58` and `test_instruction_budget.py:151`. The adopt list names only MIGRATIONS, TEMPLATES, TEST and SHARED. These `RISKRAILS_` names are still read by the code and still leak in:
    - `RISKRAILS_NOW`, read in `update.py` and overriding the clock.
    - `RISKRAILS_NO_UPDATE_CHECK`.
    - `RISKRAILS_REGISTRY_URL`.
  The test's own `CLAUDE_AGENTIC_SHARED` is not shadowed. `RISKRAILS_SHARED` is stripped, and `update.py:65-66` `env()` prefers `RISKRAILS_X` over `CLAUDE_AGENTIC_X`, so the strip is correct and needed. A malformed `RISKRAILS_NOW` in a developer's shell would still break the adopt suite.
  suggested direction: use the same prefix filter (`not k.startswith("RISKRAILS_")`) as the other files.
- [INFO] I1 (docs) The two exit-2 descriptions cover different ground (`adopt.py:1406`, `skills/rr-setup/SKILL.md:198`)  in_scope: yes
  why it matters: both say "the routing table or a migration could not be read". The `SchemaError` that `gates()` catches (`adopt.py:1419`) also covers `.ai/VERSION` being unreadable, not a number, or ahead of the plugin (`update.py:451,459,1555`). The wording is slightly narrow but not wrong. "Nothing written" and "reason on stderr, prefixed `project-update:`" both check out against `adopt.py:1411-1421`, which writes nothing before these returns.
- [INFO] I2 (test strength) The adopt test's stdout check leans on a pair of runs (`tests/test_project_adopt.py:968-975`)  in_scope: yes
  why it matters: the second run drops stderr (`run_` uses DEVNULL when `merge=False`), so its `NotIn "note must be str"` only means something because the first, merged run asserted the reason is present.
  - The combination is sound: rc 2 is asserted in both runs, and `tree_sha` is unchanged, so the second run sees the identical tree.
  - Together they do prove the reason is not on stdout.
  - The number is now derived from the registry (the `max(...)+1` line, with `re` imported).
  - No action needed.

## EXAMINED AND CLEAN
- Rollback sentence in `register-batch-2.md`: `SchemaError` "says schema %d, this plugin ships schema %d — update the plugin" at `update.py:1555`. It is caught at `update.py:2040`, which returns 2, so exit 2 is right. The wording is accurate: reverting removes 0011 (the migration came from commit b7f3058), so CURRENT drops to 10 while a migrated project stays at 11. The sentence is correct in substance. `docs/project-update.md:29` already says "schema 11".
- The adopt SchemaError test runs the first call with `--apply` against a synthetic migration number that is registry max + 1 (earlier hardcoded 12). It asserts rc 2, the reason text, no Traceback and an unchanged `tree_sha`, so it does reach the code (the reason is asserted present).
- `RISKRAILS_SHARED` stripped against the class's `CLAUDE_AGENTIC_SHARED`: no conflict, as above.
- Test 1, missing weight.md (`test_project_update.py:2110-2121`): it asserts rc 0 and that the created file equals the template's. The project's JSON has an extra example, so a render would differ from the template. It discriminates the text path from the render path.
- Scope: the diff touches only the files named in the plan. `test_migration_0006.py`, `test_merge_migration.py` and `test_instruction_budget.py` are unchanged, because they already strip by prefix.
- Ran `-k weight_mirror -k weight_json` in `test_project_update` (19 tests), and the adopt schema_error test. All pass.
- Inherited from the task record and not re-derived: suite 1 and e2e 2 exit 0 on tree 7db55a5b5.
- Not reached (budget): a mutation run of the symlink and absent-json tests (read-only mode, no scratch scripts). `sensors.json` does not exist for this task, so I took nothing from it.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the approved plan. It is docs and tests plus one docstring, with no code behaviour change. The weight symlink and absent-json tests are weaker than their docstrings claim (M1, L1). The adopt test env filter is narrower than the prefix filter used elsewhere (L2).
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/sdlc/plans/register-batch-2.md | +1 −0 | Edit |
| skills/project-update/adopt.py | +2 −1 | Edit |
| skills/rr-setup/SKILL.md | +3 −1 | Edit |
| tests/test_project_adopt.py | +9 −2 | Edit |
| tests/test_project_update.py | +35 −0 | Edit |

+50 −4 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on 7db55a5b5 (run 1) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
