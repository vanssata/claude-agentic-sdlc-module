# T-2026-10-30-1842-fix-open-risks-of-1825 — Fix the open risks of T-2026-10-30-1825: edit_json fn contract, 0007 type-malformed JSON and create-path dump as conflicts, one row for read_json+edit_json on one deep file

bugfix · full · started 2026-10-30T18:42:50Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 247 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/0007_weight_model.py matches needs_step **/migrations/**; hint 
domain         0  no auth, payments, secrets or personal data; the project-update merge of local JSON (declared)
novelty        0  the RecursionError-to-conflict pattern already exists in update.py edit_json/three_way (declared
coverage       1  1 of 2 code files have a test
W 6 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T18:42:50Z — /rr-build-all open risks of T-2026-10-30-1825

## Plan

files: skills/project-update/update.py, skills/project-update/migrations/0007_weight_model.py, skills/project-update/migrations/README.md, tests/test_project_update.py
tests: tests/test_project_update.py
- s1 · skills/project-update/update.py, skills/project-update/migrations/README.md · tests/test_project_update.py · done
- s2 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done · after s1
- s3 · skills/project-update/migrations/0007_weight_model.py, tests/test_project_update.py · tests/test_project_update.py · done · after s2, s1
- s4 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done · after s1, s2, s3

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-1842-fix-open-risks-of-1825 for implementation? (gate: human_approval)
asked: 2026-10-30T18:57:03Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T18:57:26Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 7f259c930 | .ai/state/logs/T-2026-10-30-1842-fix-open-risks-of-1825/suite-1.log | no |
| 2 | e2e | 0 | 7f259c930 | .ai/state/logs/T-2026-10-30-1842-fix-open-risks-of-1825/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M1 Shape gaps remain: a null node, or a non-list `hints[].paths`, in weight.json still crashes convert with a Traceback (skills/project-update/migrations/0007_weight_model.py:175-182 `_bad`, :205-224 `_new_problem`, against convert :107-111, :122-153) in_scope: yes
  why it matters: `_bad` treats null as absent, right on the read side (`x or {}`), wrong on the write side (dict.setdefault returns the existing None). Probed on the working tree: {"axes": null}, {"axes":{"domain":null}}, {"examples": null} → AttributeError NoneType .setdefault; {"axes":{"domain":{"modules":null}}}, {"examples":{"light":null}} → TypeError; {"hints": null} → TypeError not iterable; {"hints":[{"axis":"domain","paths":"x"}]} → AttributeError str.append, "paths": null → TypeError. Same for "tests": null and null reversibility.irreversible/needs_step. Each a Traceback from user JSON once the old table carries a value into that node; nothing written, run aborts. `_new_problem`'s docstring claims coverage it lacks.
  suggested direction: on the write side treat a present null as a wrong type; check hints[i].paths is a list or absent; pin one null case and the hints-paths case with a test that crashes on the current tree.
- [MEDIUM] M2 `"tiers": []` never crashed; the "fails before the fix" test pins a behaviour change, not a crash (tests/test_project_update.py test_a_risk_tiers_json_with_tiers_a_list_holds_the_schema_not_a_crash; 0007_weight_model.py:187) in_scope: yes
  why it matters: convert reads `(old.get("tiers") or {}).items()`; `[] or {}` is {}. On the HEAD export the test gave no Traceback, 0 conflicts, a normal schema 6 -> 11 plan; it failed only on the new conflict regex. The docstring and R-6ab7 premise are false for this input; the fix holds the schema for a table HEAD converted cleanly; the shapes that really crash ("tiers": ["x"], "x", 1) have no test. Conflicts with "production behaviour is the source of truth"; the literal ask named [] on a false premise.
  suggested direction: let an empty/falsy tiers through as HEAD did and pin a non-empty list or string instead; or keep the conflict and record it as a deliberate tightening. The human's call.
- [LOW] L1 The shape checks reject inputs HEAD converted without a crash, including nodes convert never touches for this project (0007_weight_model.py:186-198, :205-224; _new_problem runs even when nothing is carried, :250-253) in_scope: yes
  why it matters: tiers.T9.examples: "x", path_scopes as dict or string, an int/bool scope name, a list scope name with no paths; weight.json "hints": {} or "tests": "x" when nothing is carried — each now holds the schema on every run until a human edits the file. Some are improvements (examples: "abc" wrote characters), none pinned or recorded as intended.
  suggested direction: limit checks to nodes convert reads or writes for this old table, or record the tightening as intended.
- [LOW] L2 `_add` calls note.startswith(...) for every action, not only conflicts (skills/project-update/update.py:650); new messages read "not a object" and "is a int" (0007_weight_model.py:179) in_scope: yes
  why it matters: a non-str note now raises AttributeError in any operation; the public ctx.conflict(path, note) invites caller-built notes. Grammar errors are user-visible.
  suggested direction: compute `deep` only for action == "conflict" with a str note; article by word.
- [INFO] I1 No test asserts the "--mirror" hint is absent after a shape conflict or the create-path RecursionError (0007_weight_model.py:256-258) in_scope: yes — correct by reading today.
- [INFO] I2 The dedup is keyed on the note prefix "nested too deeply" (update.py:650-655) in_scope: yes — string coupling; a future same-prefix conflict meaning something else would be dropped.

## EXAMINED AND CLEAN
All 6 new tests fail on a HEAD export (tiers: [] only on the regex, see M2); the R-5e7a injected fault fires only on 0007's create-path dump (HEAD trace at 0007:181), no false pass; dedup is per target+migration, another reason stays its own row; read side probed clean; edit-path pre-parse falls back to edit_json's own conflict; idempotent re-run; R-891a docs match behaviour; only the four plan files changed, no test weakened. Not reached: Python other than 3.14 for the 470-490 figure; state.py tolerance of shapes L1 rejects.

## VERDICT
verdict: pass
(No BLOCKER or HIGH. M1 and M2 are MEDIUM in-scope findings worth fixing in the next batch.)
scope_assessment: stayed inside the approved plan's four files. M2 and L1 are behaviour tightening beyond "crash becomes conflict", based on a false premise for tiers: [], so the human should decide.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/0007_weight_model.py | +77 −5 | Edit |
| skills/project-update/migrations/README.md | +8 −0 | Edit |
| skills/project-update/update.py | +17 −5 | Edit |
| tests/test_project_update.py | +86 −0 | Edit |

+188 −10 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on 7f259c930 (run 1) · (b) green — 4 changed files, all in the task's files
gate: requested G1 at 2026-10-30T18:57:03Z; approved by Ivan Kakurov at 2026-10-30T18:57:26Z via dialog
confirm: none
handoffs: 7 · suite runs: 1 · review passes: 1
