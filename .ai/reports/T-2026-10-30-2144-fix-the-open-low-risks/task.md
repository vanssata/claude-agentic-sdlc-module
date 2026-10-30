# T-2026-10-30-2144-fix-the-open-low-risks — Fix the open low risks of T-2026-10-30-2052: README str-check wording, adopt SchemaError exit 2, stricter 0007 conflict assertions

bugfix · full · started 2026-10-30T21:44:40Z · claude

## Weight

```
scope          2  skills/project-update/migrations/README.md referenced from 135 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/README.md matches needs_step **/migrations/**; hint +1
domain         0  plugin tooling error path; no auth, data or payments (declared)
novelty        0  mirrors update.py main() SchemaError handling at :2040-2043 (declared)
coverage       0  1 of 1 code files have a test
W 5 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T21:44:40Z — /rr-build-all inline plan: open risks of T-2026-10-30-2052

## Plan

files: skills/project-update/migrations/README.md, skills/project-update/adopt.py, tests/test_project_adopt.py, tests/test_project_update.py
tests: tests/test_project_adopt.py, tests/test_project_update.py
- s1 · skills/project-update/migrations/README.md · tests/test_project_update.py · done
- s2 · skills/project-update/adopt.py, tests/test_project_adopt.py · tests/test_project_adopt.py · done
- s3 · tests/test_project_update.py · tests/test_project_update.py · done · after s1

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2144-fix-the-open-low-risks for implementation? (gate: human_approval)
asked: 2026-10-30T21:53:55Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T21:56:22Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | a5005fdf5 | .ai/state/logs/T-2026-10-30-2144-fix-the-open-low-risks/suite-1.log | no |
| 2 | e2e | 0 | a5005fdf5 | .ai/state/logs/T-2026-10-30-2144-fix-the-open-low-risks/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS

No BLOCKER, HIGH or MEDIUM findings. All three risks close against the real code.

- [LOW] L1 The new test does not check which stream the message goes to, and it does not check that nothing was written (`tests/test_project_adopt.py:965-968`)  in_scope: yes
  why it matters: `upd(..., merge=True)` merges stderr into stdout. If the handler at `adopt.py:1419` were changed to print to stdout, the test would still pass, which breaks the update.py convention (stderr everywhere except `--check`). Exit 2 having written nothing is true by construction: gates run before any write, and `partial_record` only reads. But the test doesn't pin it, unlike the other refusal tests, which compare `tree_sha` before and after.
  suggested direction: run once without `merge` and assert the reason is absent from stdout, and compare `tree_sha(d)` before and after, as `assert_refused` does.

- [LOW] L2 The synthetic migration's number is hardcoded as `0012_bad_note.py` / `VERSION = 12` (`tests/test_project_adopt.py:963-964`)  in_scope: yes
  why it matters: the test copies the real registry (0001-0011) and adds a twelfth migration. When the plugin ships a real `0012_*.py`, `migrations.load()` raises "duplicate migration 0012". The run still exits 2, but the "note must be str" assertion fails. So it breaks loudly, not silently, and the next person to add a migration has to fix an unrelated test.
  suggested direction: derive the number from `max(NNNN in the copied dir) + 1` and write both the file name and `VERSION` from it.

- [INFO] I1 The new handler converts more than migration errors, and the extra cases are untested (`skills/project-update/adopt.py:1416-1420`)  in_scope: yes
  why it matters: the only source of SchemaError inside `gates` is `u.plain_pending` → `build_plan`. `clean_tree` and `task_in_flight` are adopt's own functions and raise none, so the catch hides nothing foreign. But it also turns the non-migration SchemaErrors of `build_plan` into exit 2: unreadable or non-numeric `.ai/VERSION` (`update.py:451,459`), project schema ahead of the plugin (`:1555`), a broken registry, and an unreadable or invalid task state (`:779-789`). That is the correct behaviour, identical to `main()` at `:2040-2043`. The comment says only "a migration's error", and only the migration case has a test.
  suggested direction: none needed; optionally widen the comment.

- [INFO] I2 The `apply_run` docstring still lists exits "0, 3, 4 or 5" (`skills/project-update/adopt.py:1405-1406`), and `skills/rr-setup/SKILL.md:197-198` documents only 5 and 4 for `--adopt`  in_scope: yes
  why it matters: both are now missing exit 2, which this change adds a second path to (`TableError` already returned 2). The practical effect is small: step 1 of the rr-setup adopt flow runs `$UPDATE --check`, which already exits 2 with the reason on stdout for the same SchemaError, so the session stops before `--adopt --apply`.
  suggested direction: add exit 2 to the docstring in a later docs touch.

- [INFO] I3 The test helpers don't strip the new `RISKRAILS_*` names from the environment (`tests/test_project_adopt.py:204-207`)  in_scope: no
  why it matters: the env filter removes `CLAUDE_AGENTIC_MIGRATIONS` and `CLAUDE_AGENTIC_TEST` but not `RISKRAILS_MIGRATIONS` or `RISKRAILS_TEST`. `migrations/__init__.py:20` reads `RISKRAILS_MIGRATIONS` first, so a developer shell that exports it would make the new test's `CLAUDE_AGENTIC_MIGRATIONS=mig` have no effect. The test would fail loudly, not pass falsely. This gap predates the change and affects every test that redirects the registry. Inside the boundary it would be LOW.
  suggested direction: risk register; strip both names in all the test env filters in one separate task.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved plan: four files, s1-s3 as planned, no other code in skills/ changed, and the 0007 assertions were tightened, not weakened. The two LOW findings are test-hardening suggestions and don't move the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/adopt.py | +5 −1 | Edit |
| skills/project-update/migrations/README.md | +4 −1 | Edit |
| tests/test_project_adopt.py | +13 −0 | Edit |
| tests/test_project_update.py | +2 −2 | Edit |

+24 −4 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on a5005fdf5 (run 1) · (b) green — 4 changed files, all in the task's files
gate: requested G1 at 2026-10-30T21:53:55Z; approved by Ivan Kakurov at 2026-10-30T21:56:22Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
