# T-2026-10-30-2223-risk-burndown-b2-project — Risk burndown B2: project-update hint/cleanup/rule-writer bugfixes, bite_codes range, rr-status budgets from weight.json, installer python 3.11 check, verify names the untracked artifact, lint gate fail-on

bugfix · guarded · started 2026-10-30T22:23:21Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 261 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  plugin tooling; no auth, data or payments (declared)
novelty        0  each fix follows an existing pattern in the same file (declared)
coverage       1  5 of 6 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T22:23:21Z — /loop risk burndown B2 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md)

## Plan

files: skills/project-update/update.py, skills/project-update/adopt.py, tests/test_project_update.py, tests/test_project_adopt.py, skills/ai-task/sensors.py, tests/test_ai_task_sensors.py, skills/rr-status/status.py, tests/test_ai_status_root.py, bin/riskrails.js, tests/test_install_dry_run.py, skills/ai-task/state.py, tests/test_ai_task_state.py, .pylintrc, tests/test_ere_unit.py
tests: tests/test_project_update.py, tests/test_project_adopt.py, tests/test_ai_task_sensors.py, tests/test_ai_status_root.py, tests/test_install_dry_run.py, tests/test_ai_task_state.py, tests/test_ere_unit.py
- s1 · skills/project-update/update.py, skills/project-update/adopt.py, tests/test_project_update.py, tests/test_project_adopt.py · tests/test_project_update.py, tests/test_project_adopt.py · done
- s2 · skills/ai-task/sensors.py, tests/test_ai_task_sensors.py · tests/test_ai_task_sensors.py · done
- s3 · skills/rr-status/status.py, tests/test_ai_status_root.py · tests/test_ai_status_root.py · done
- s4 · bin/riskrails.js, tests/test_install_dry_run.py · tests/test_install_dry_run.py · done
- s5 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s6 · .pylintrc · tests/test_ere_unit.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | aa2517791 | .ai/state/logs/T-2026-10-30-2223-risk-burndown-b2-project/suite-1.log | no |
| 2 | e2e | 0 | aa2517791 | .ai/state/logs/T-2026-10-30-2223-risk-burndown-b2-project/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
I found no BLOCKER, HIGH or MEDIUM. The six LOW and five INFO findings below do not change the verdict, which is **pass**.

Inputs: there is no review-ledger.md or sensors.json for this task, so I inherited nothing. Without `.ai/policies` reads beyond task.md I reviewed against the repo's CLAUDE.md and skills/CLAUDE.md. I did not edit anything. I checked whether the new tests fail without the fix by extracting `git archive HEAD` into the scratchpad (/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/5e84bc43-ba41-4d5d-8e94-542372176d9f/scratchpad/head), copying the new test files over and running only the new tests there.

## FINDINGS

- [LOW] L1 Blocks that earlier versions already wrote under a directory that is now skipped are left in place, frozen, and the hint misdescribes them (`skills/project-update/update.py:1451-1454`)  in_scope: yes
  why it matters: Before this change, a rule with `dirs: [vendor/x]` (or a symlinked directory pointing outside the walk) had its block rewritten on every run. Now the writer skips it and prints "rule X is not rendered there", but the old block is still in `vendor/x/CLAUDE.md` with the old rule text. The take-back never walks there, so nothing removes or updates it. Agents in that directory keep reading stale rules, and the hint tells the user nothing is there. A symlink pointing back inside the walked tree now behaves better (the take-back strips it and the result settles), so this only affects the outside-walk case.
  suggested direction: When `plan.read(target)` already holds a block for that slug, say in the hint that an earlier rendering is still there and must be removed by hand.

- [LOW] L2 On a case-insensitive filesystem (macOS default) the writer and the take-back still disagree (`skills/project-update/update.py:1408` vs `:1368`)  in_scope: yes
  why it matters: Both checks compare against `RULES_SKIP` case-sensitively, but the walk sees the name as spelled on disk. With `dirs: [Vendor/x]` and `vendor/` on disk, the writer passes `Vendor`, the file lands in `vendor/x/CLAUDE.md`, and the walk prunes `vendor`. That is the same never-taken-back block this risk is meant to close.
  suggested direction: Compare case-insensitively, or resolve each component to its on-disk spelling before checking `RULES_SKIP`.

- [LOW] L3 `moved_detail` prints path names exactly as found into output an agent reads (`skills/ai-task/state.py:3762-3765`)  in_scope: yes
  why it matters: Paths come from `git diff -z` with `core.quotepath=off`, so a file the suite writes with a newline or escape sequence in its name can fake a line in `verify` output, such as a fake success line. `update.py:1336-1340` (`tracked_ignored_hint`) escapes non-printable characters for exactly this reason; the new code does not follow that convention.
  suggested direction: Escape non-printable characters the way `tracked_ignored_hint` does.

- [LOW] L4 The installer's version check says "found unknown" without saying why, and refuses a valid Python whose stdout has extra lines (`bin/riskrails.js:121-126`)  in_scope: yes
  why it matters: stderr is ignored. A 10-second timeout, a pyenv shim that exits 127, or a nonzero exit all give "python3 3.11 or newer is required (found unknown)", which sends the user hunting for a version problem. The `^…$` match (no `m` flag) after `trim()` also refuses a 3.12 whose `sitecustomize` prints to stdout. It fails safe, but the message is misleading.
  suggested direction: Match the last line of stdout. When nothing matches, include `pv.error` / `pv.status` / the first stderr line in the message.

- [LOW] L5 The bite_codes risk is only half fixed (`skills/ai-task/sensors.py:248-259`)  in_scope: yes
  why it matters: The register entry for R-bite-codes-accepts-0-and-negatives-an-in-7319 asks for two things: accept only 1-255, and print one line when the field is present but unusable. Only the first was done. `bite_codes: 1 2` still quietly becomes `(1,)`. If the risk is closed as fixed, the silent-fallback half disappears from the register.
  suggested direction: Close only the range half and keep or re-file the silent-fallback half.

- [LOW] L6 status.py's module docstring still says it reads `.ai/policies/risk-tiers.json` (`skills/rr-status/status.py:8`)  in_scope: yes
  why it matters: This change made status.py stop reading that file, and migration 0011 deletes it, so the docstring now describes something the code no longer does.
  suggested direction: Name weight.json, falling back to the shipped table.

- [INFO] I1 `budgets()` mirrors `budget()` except in cases outside the change (`skills/rr-status/status.py:100-115`)  in_scope: yes
  why it matters: Batch values, batch defaults 8/3 and non-batch defaults 2/2 all match state.py's `BATCH_DEFAULTS`/`batch_policy`, and the shipped path equals `weight.SHIPPED`. The differences:
  - A weight.json that is unreadable, or valid JSON with no axes/modes, makes status show the shipped numbers, where state.py dies with "cannot read the weight table".
  - A non-int `tests.max_suite_runs` is printed as-is.
  - Already true before this change: on a schema-7 state where `state.py status` fails, `report()` reads the legacy counters `tests.suite_runs`/`reviews`. Schema 7 keeps `verify.suite_runs`/`review.passes`, so the counters show 0 next to correct budgets. The batch branch is only reachable in that fallback.
  suggested direction: Register the counter mismatch as a separate risk; it does not belong in this task.

- [INFO] I2 In test_10b, the rc==1 check does not discriminate (`tests/test_install_dry_run.py:348-360`)  in_scope: yes
  why it matters: On HEAD with the fake python3 the installer already exits 1 (it fails later, because the fake prints only `3.10`). Only the message assertion fails before the fix, and it does.
  suggested direction: None required; the message check pins the fix.

- [INFO] I3 When `.ai/reports` or `.ai/state/logs` is itself a symlink, cleanup prints one hint per task on every run (`skills/project-update/update.py:1279`)  in_scope: yes
  why it matters: `skipped` is reset for each task, so in a project with many tasks this is one hint per task per run, each naming the same symlink. Before the change it was the same number of `delete?` lines plus an aborting `--apply`, so it is no worse.
  suggested direction: Deduplicate across tasks.

- [INFO] I4 The `moved_detail` advice overstates the cause and skips `--literal-pathspecs` (`skills/ai-task/state.py:3756-3770`)  in_scope: yes
  why it matters: "Move the tree on every run" holds only if the content changes between runs. The "written by the suite" attribution is a guess about who wrote the file. The `ls-files` call has no `--literal-pathspecs`, but the only outcome is classifying an added file as untracked, which is effectively always true. Cost is fine: it runs only on a moved tree, both git calls go through `safe_sensor`, and git missing or too many arguments (E2BIG) degrades to `[]` or "all untracked" without raising.
  suggested direction: Optional wording only.

- [INFO] I5 The user-facing rules README does not mention that `dirs:` entries are refused under RULES_SKIP names, symlinks or nested git trees (`skills/ai-init/templates/.ai/rules/README.md:19-24`)  in_scope: yes
  why it matters: Users learn about it only from a hint. Editing the template triggers `build-template-history`, so this is a follow-up, not part of this task.
  suggested direction: Document it in a later template task.

## EXAMINED AND CLEAN

- **Do the tests fail without the fix?** Run against the HEAD tree:
  - The cleanup-symlink, rule-writer, both TestLegacyBudgets and moved-tree tests fail.
  - The tracked-ignored test: all 11 subtests fail (pytest still reports the parent as PASSED, which is a subtest artefact).
  - test_10b: its message subtest fails.

  The new tests have no vacuous assertions, apart from I2.
- **The writer and the take-back now agree** (except L2):
  - `unwalked_dir` checks every path component for RULES_SKIP names, at any depth, as the walk's prune does.
  - `os.path.islink` is checked on every component, so a symlink higher up is caught, matching `os.walk(followlinks=False)`.
  - The `.ai` and `.git` directories are caught.
  - `""` and `"."` (the root) pass.
  - `..` and absolute paths are already refused, and `normpath` is applied, in `render_instructions.parse_rule:350-361`.
  - The skip applies to blocks only (docs are unaffected), runs after `nested_tree`, and ordinary `dirs:` entries still render (the `ok/` control in the test).
- **cleanup:** an unsafe target is never proposed or deleted, under `--confirm-cleanup` too (`plan.remove` is not reached). `--apply` no longer aborts, safe siblings are still deleted, a hint is always printed (nothing is left silently), and `deletion_hint` is unaffected.
- **`--check` and /ai-status:** hints are never part of `pending` and never printed under `--check`. The only effect is that skipped rule targets no longer count as pending, and a symlinked cleanup target under `--confirm-cleanup` no longer counts as a pending `delete`. Both are reductions.
- **Tracked-ignored wording:** "from the project root" is correct for all three forms. `rm --cached -- <path>` and `ls-files` resolve against the working directory, and paths are relative to `plan.root`, which is also right in a monorepo subdirectory.
- **bite_codes:** the range check is correct for 0, negatives, 256 and mixed lists; `" 255"` parses; the single caller is `state.py:3933`.
- **`check=False`:** right in all three places, because each caller inspects `returncode`/stdout itself. Repo-wide `pylint --disable=all --enable=W0702,W1510` scores 10.00; the only inline disable is the existing one at `tests/test_memory_pre_push.py:204`.
- **The JS check:**
  - It runs after `--help`/`--version` handling and after the onPath check.
  - It uses the same `env`/PATH as onPath.
  - Undecodable bytes in stdout are replaced, not fatal.
  - A Python with major version 4 or above passes.
  - CI's matrix (3.11-3.13) passes.
  - Windows is out of scope, as briefed.
- **`moved_detail`** is only reached on the tree-moved branch, is fully wrapped in `safe_sensor`, and no tool parses `verify` stdout (checked with grep).
- **Not re-run, taken from the brief:** the suite and e2e results (suite-1.log / e2e-2.log) and the pylint 9.98 score.
- not reached (budget): case-insensitive behaviour of `unsafe_path`; a write-time recheck of `unwalked_dir` at `--apply` (whether something can change between plan and apply). That recheck is old behaviour, not added by this change.

## VERDICT

verdict: pass
scope_assessment: The change stayed inside the approved plan (files s1-s6). The adopt.py docstring, tests/test_project_adopt.py, the three weight_mirror tests, docs/sdlc/plans/register-batch-2.md and skills/rr-setup/SKILL.md are B1's, as the brief says. tests/test_ere_unit.py is named in the plan but unchanged, which is expected for s6. There is no scope creep and no refactoring mixed in. The RULES_SKIP comment update matches the new behaviour. R-bite-codes-…-7319 is only partly fixed (L5), so its register entry should not be closed in full.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .pylintrc | +2 −3 | Edit |
| bin/riskrails.js | +8 −0 | Edit |
| skills/ai-task/sensors.py | +4 −1 | Edit |
| skills/ai-task/state.py | +26 −0 | Edit |
| skills/project-update/update.py | +32 −7 | Edit |
| skills/rr-status/status.py | +20 −4 | Edit |
| tests/test_ai_status_root.py | +31 −0 | Edit |
| tests/test_ai_task_sensors.py | +5 −1 | Edit |
| tests/test_ai_task_state.py | +11 −1 | Edit |
| tests/test_install_dry_run.py | +14 −0 | Edit |
| tests/test_project_update.py | +60 −1 | Edit |

+213 −18 lines, 11 files

## Verdict

close: closed
facts: (a) green — suite green on aa2517791 (run 1) · (b) green — 11 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
