# T-2026-10-30-1825-fix-the-low-findings-of — Fix the LOW findings of T-2026-10-30-1806: 0007 _loads RecursionError, edit_json fn outside the guard, dump_json guard tests, read_json comment and conflict dedup

bugfix · full · started 2026-10-30T18:25:35Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 245 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/0007_weight_model.py matches needs_step **/migrations/**; hint 
domain         0  "no auth, payments, secrets or personal data; the project-update merge of local JSON" (declared)
novelty        0  "the RecursionError-to-conflict pattern already exists in update.py edit_json/three_way" (declar
coverage       1  1 of 2 code files have a test
W 6 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, skills/project-update/migrations/0007_weight_model.py
tests: tests/test_project_update.py
- s1 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done · after s1
- s3 · tests/test_project_update.py · tests/test_project_update.py · done · after s2
- s4 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done · after s3

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-1825-fix-the-low-findings-of for implementation? (gate: human_approval)
asked: 2026-10-30T18:39:11Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T18:39:51Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 2 | 47adbcfe9 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-1.log | yes |
| 2 | step | 1 | 47adbcfe9 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-2.log | yes |
| 3 | step | 0 | 9060b3995 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-3.log | no |
| 4 | step | 1 | c64b83db0 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-4.log | yes |
| 5 | step | 0 | 2dde06c22 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-5.log | no |
| 6 | step | 0 | 3d9a59a77 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-6.log | no |
| 7 | step | 1 | fcafb2978 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-7.log | yes |
| 8 | step | 0 | 52c361353 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/step-8.log | no |
| 9 | suite | 0 | 52c361353 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/suite-9.log | no |
| 10 | e2e | 0 | 52c361353 | .ai/state/logs/T-2026-10-30-1825-fix-the-low-findings-of/e2e-10.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [LOW] L1 (skills/project-update/update.py:704) — `# Outside the guard: a RecursionError in the migration's own edit is its bug, not the file's.` True for the only edit_json caller today (0007's convert), not in general. in_scope: yes
  why it matters: a future migration whose fn walks the document with Python recursion (~2+ frames per level) on a file that just passed copy.deepcopy (~470-490 levels at limit 1000) can hit the limit; the run dies with a traceback naming no file, though the cause is the file's depth. Nothing reaches this today: only 0007_weight_model.py:183 calls edit_json, only 0007 calls read_json.
  suggested direction: state the contract in the edit_json docstring (and migrations/README.md): fn must not recurse over the document in Python, or must guard itself; reword the comment to "an unguarded fn's RecursionError is reported as its own".
- [INFO] I1 (.ai/reports/T-2026-10-30-1825-fix-the-low-findings-of/task.md §Verify, run 1) in_scope: yes — run 1 recorded expected_fail: yes with exit 2 was a run_suite usage error, not a red test; the real red run for s1 is run 2 (step-2.log:6). Record hygiene only.
- [INFO] I2 (s3 tests test_edit_jsons_write_past_the_limit_is_a_conflict, test_three_ways_write_of_a_merged_policy_past_the_limit_is_a_conflict) in_scope: yes — cannot fail on the current tree (plan says so); the only evidence they detect a missing guard is the implementer's mutation runs, in neither events.jsonl nor a log. Put one line with the mutation and the failing test name into the record before close.
- [INFO] I3 (skills/project-update/migrations/0007_weight_model.py:122,123,134) in_scope: no — pre-existing: convert crashes on type-malformed (not deep) user JSON: "tiers": [] (AttributeError at .items()), a path scope with "scope": ["x"] (TypeError, unhashable), weight.json a JSON array (AttributeError at new.setdefault). 0007 dies mid-plan; nothing written. Risk register.
- [INFO] I4 (0007_weight_model.py:181, update.py:415 dump_json) in_scope: no — pre-existing: the project supports Python 3.11+; on 3.11-3.13 json.dumps(indent=2) is believed to use the pure-Python encoder (3.14 uses C, encoder.py:253; older versions from memory, unchecked). weight.json absent + edited risk-tiers.json with a scalar nested several hundred levels: line 181 raises an uncaught RecursionError (not through edit_json). Deep-JSON test depths are calibrated for 3.14.
- [INFO] I5 (update.py:646-648) in_scope: yes — dedup matches target+note+migration, so read_json then edit_json on the same deep file in one migration still gives two rows ("could not read it", "could not run"). Accepted by the plan; no shipped migration does it.

## EXAMINED AND CLEAN
- Ordinary input unchanged; _loads only gains RecursionError; edit_json order deepcopy → fn → compare/leaf_changes/dump_json unchanged, only try-blocks split; _add early-returns only for conflict; every Plan item carries action/target/note/migration (Plan.add, update.py:839, only producer).
- s2 crash not reachable through 0007: convert has no Python recursion; anything that passes the copy passes fn; a deep scalar landing in after is caught by guarded leaf_changes; the 3000-level copy-limit test still hits the deepcopy guard; a crash in fn happens in build_plan before any write.
- s1 and 0007:177-185 correct (None != None → no hint; template plugin-owned).
- s4 dedup keyed by VERSION, never matches across migrations or migration None; held-schema logic (update.py:1548) still sees one conflict.
- read_json comment accurate.
- DUMP_FAULT runner exercises the production paths (argv, sys.path, global lookup of dump_json at update.py:710 and 961; project_own forces the JSON merge path).
- s1, s2, s4 tests failed on the base tree for the right reason (step-2, step-4, step-7 logs); suite-9 1067 tests OK (5 skipped), e2e OK.
- Scope: three planned files only; no test weakened. Not reached: s3 mutations not reproduced (read-only); Python 3.11-3.13 not run.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the accepted plan: steps s1–s4 only, in the three named files, with no refactoring and no unrelated edits. I3 and I4 are pre-existing 0007 robustness gaps for the risk register; not grounds for remediation in this task.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/0007_weight_model.py | +1 −1 | Edit |
| skills/project-update/update.py | +14 −5 | Edit |
| tests/test_project_update.py | +85 −2 | Edit |

+100 −8 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 52c361353 (run 9) · (b) green — 3 changed files, all in the task's files
gate: requested G1 at 2026-10-30T18:39:11Z; approved by Ivan Kakurov at 2026-10-30T18:39:51Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
