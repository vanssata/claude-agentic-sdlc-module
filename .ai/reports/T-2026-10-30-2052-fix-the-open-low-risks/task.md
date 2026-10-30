# T-2026-10-30-2052-fix-the-open-low-risks — Fix the open LOW risks of T-2026-10-30-2032-1917-risks (L1-L4): README note/reason types, rc==2, boolean/string conflict cases, docstring

feature · full · started 2026-10-30T20:52:31Z · claude

## Weight

```
scope          2  skills/project-update/migrations/README.md referenced from 133 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  2  skills/project-update/migrations/README.md matches needs_step **/migrations/**; hint +1
domain         0  docs and tests of the update plugin, no money or identity (declared)
novelty        0  the tests extend existing cases (declared)
coverage       0  no code file declared
W 5 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T20:52:31Z — /rr-build-all inline plan: LOW risks of T-2026-10-30-2032-1917-risks

## Plan

files: skills/project-update/migrations/README.md, tests/test_project_update.py
tests: tests/test_project_update.py
- s1 · skills/project-update/migrations/README.md · tests/test_project_update.py · done
- s2 · tests/test_project_update.py · tests/test_project_update.py · done · after s1

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2052-fix-the-open-low-risks for implementation? (gate: human_approval)
asked: 2026-10-30T21:01:24Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T21:02:30Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 68df08ec0 | .ai/state/logs/T-2026-10-30-2052-fix-the-open-low-risks/suite-1.log | no |
| 2 | e2e | 0 | 68df08ec0 | .ai/state/logs/T-2026-10-30-2052-fix-the-open-low-risks/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
FINDINGS
- [LOW] L1 — skills/project-update/migrations/README.md:24-26 — The sentence "Any other type stops the update with a SchemaError" claims more than the code does for `ctx.edit_text` and `ctx.delete`. — `edit_text` only reaches `_add` (and so the str check) when the file exists and `fn` changed it (update.py:685-692, `if new != data`). `delete` only reaches it when `self.exists(path)` (update.py:758-759). So a non-str note or reason on a call that changes nothing passes silently. A migration author can test on a project where the edit is a no-op, see no error, and the SchemaError only appears in a user project where the edit applies. `conflict` always goes through `_add` (update.py:609-611), so the conflict bullet at :57-59 is accurate. Suggested direction: say "is refused when the operation is planned", or note that a no-op call is not checked.
- [INFO] I1 — skills/project-update/migrations/README.md:26, :58-59 — "exit 2" holds for the dry run, `--check` (reason on stdout) and `--apply`, but not for `--adopt`. — All three go through `build_plan` inside the `except SchemaError` at update.py:2037-2043, and the apply branch comes after it. Under `--adopt`, `adopt.gates` → `u.plain_pending` (adopt.py:1358 → update.py:1845-1849) calls `build_plan` with no SchemaError handler anywhere in adopt.py, so the same error ends in a traceback with exit 1. This was already true before the task and applies to every SchemaError, including non-bytes content. in_scope: no (pre-existing, outside the task's files); for the risk register.
- [INFO] I2 — tests/test_project_update.py:355, :358 — The new text checks match only the type phrase, not the field. — "is a boolean, not a list" and "is a string, not a list" do match the real messages, "tiers.T1.examples is a boolean, not a list" and "a path scope's paths is a string, not a list" (0007_weight_model.py:203, :216, :224). But a change that named the wrong field would still pass. Asserting the full phrase would pin the field too.
- [INFO] I3 — tests/test_project_update.py:348 — The docstring tag "R-0007" is not a risk id like its neighbours (R-a6a8). These cases come from L3 of T-2026-10-30-2032-1917-risks. Cosmetic.
- [INFO] I4 — tests/test_project_update.py:243-244 — The new L4 docstring is true but names only one key. — `edit_tiers` changes `sensors.tests.max_suite_runs`=5 and `timeout_seconds`=900 (tests:81-82); the other two tests keys equal the shipped values and are dropped by the first clause at 0007:143. With `base["tests"]="x"`, `_get` gives None at every tests.* key (0007:90-93), while the template has 2, 1800, 1, 2097152, so `_get(base,key) != _get(template,key)` and every tests scalar is dropped (0007:143-144). "convert carries no tests scalar" is therefore correct; the cause is the same for timeout_seconds as for the one key it names. The old false claim ("convert never writes a top-level tests key") is gone. No assertion changed.

VERDICT: pass
scope_assessment: The change stayed inside the approved plan. It touches only the two task files, each of L1-L4 maps to its hunk, and nothing in skills/ code changed. L1 is a wording overclaim in documentation; the INFO rows go to the risk register or are cosmetic.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/migrations/README.md | +6 −2 | Edit |
| tests/test_project_update.py | +13 −5 | Edit |

+19 −7 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 68df08ec0 (run 1) · (b) green — 2 changed files, all in the task's files
gate: requested G1 at 2026-10-30T21:01:24Z; approved by Ivan Kakurov at 2026-10-30T21:02:30Z via dialog
confirm: none
handoffs: 6 · suite runs: 1 · review passes: 1
