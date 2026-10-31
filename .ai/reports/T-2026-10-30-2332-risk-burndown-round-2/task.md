# T-2026-10-30-2332-risk-burndown-round-2 — Risk burndown round 2: review residuals of B1-B4 (rule writer frozen blocks and case, weight.json and adopt env tests, status.py docstring and counters, bite_codes visible fallback, installer version message, moved_detail escaping, old command names in AGENTS.md template and RESUME_COMMAND)

bugfix · full · started 2026-10-30T23:32:03Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 267 files
behaviour      2  keyword 'workflow' in skills/ai-task/state.py; hint +1
reversibility  0  git revert returns everything
domain         0  plugin tooling (declared)
novelty        0  each fix follows the reviewer's suggested direction in the same file (declared)
coverage       1  4 of 5 code files have a test
W 5 → guarded   hints behaviour +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-30T23:32:03Z — /loop risk burndown round 2 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md)
batch: on by Ivan Kakurov at 2026-10-30T23:32:03Z — /loop risk burndown round 2 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md)

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, tests/test_project_adopt.py, skills/rr-status/status.py, tests/test_ai_status_root.py, skills/ai-task/sensors.py, tests/test_ai_task_sensors.py, bin/riskrails.js, tests/test_install_dry_run.py, skills/ai-task/state.py, tests/test_ai_task_state.py, skills/ai-init/templates/.ai/AGENTS.md, skills/project-update/history/**, skills/ai-init/templates/.ai/state/README.md, skills/ai-init/templates/.ai/rules/README.md, tests/test_migration_0006.py, docs/sdlc/plans/small-oop-modules.md
tests: tests/test_project_update.py, tests/test_project_adopt.py, tests/test_ai_status_root.py, tests/test_ai_task_sensors.py, tests/test_install_dry_run.py, tests/test_ai_task_state.py, tests/test_shared_tree.py
- s1 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · tests/test_project_adopt.py · tests/test_project_adopt.py · done
- s3 · skills/rr-status/status.py, tests/test_ai_status_root.py · tests/test_ai_status_root.py · done
- s4 · skills/ai-task/sensors.py, tests/test_ai_task_sensors.py · tests/test_ai_task_sensors.py · done
- s5 · bin/riskrails.js, tests/test_install_dry_run.py · tests/test_install_dry_run.py · done
- s6 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s7 · skills/ai-init/templates/.ai/AGENTS.md, skills/project-update/history/** · tests/test_project_update.py, tests/test_shared_tree.py · done · after s1
amended 2026-10-30T23:35:01Z: +skills/ai-init/templates/.ai/state/README.md, skills/ai-init/templates/.ai/rules/README.md — R-...-a0c4: the same old /project-update command name in two more shipped templates (state/README.md:9,40; rules/README.md:4,24); one history rebuild covers all three
amended 2026-10-30T23:39:45Z: +tests/test_migration_0006.py — suite-1 regression: test_r10_older_edited_router_gets_later_changes fails after the AGENTS.md template rename; the fixer may need its expectations if it pins the old row text
amended 2026-10-30T23:56:40Z: +docs/sdlc/plans/small-oop-modules.md — committed by Ivan Kakurov in d7421ab during this task (plan from another session), on top of the task's base; NOT round 2's work — listed only so close's diff-since-base measure covers it

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2332-risk-burndown-round-2 for implementation? (gate: human_approval)
asked: 2026-10-30T23:58:05Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T23:58:31Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | fb7046fa5 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/suite-1.log | no |
| 2 | suite | 0 | 4f3058a31 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/suite-2.log | no |
| 3 | e2e | 0 | 4f3058a31 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/e2e-3.log | no |
| 4 | suite | 0 | 73707f6f5 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/suite-4.log | no |
| 5 | e2e | 0 | 73707f6f5 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/e2e-5.log | no |
| 6 | suite | 0 | 73707f6f5 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/suite-6.log | no |
| 7 | e2e | 0 | 73707f6f5 | .ai/state/logs/T-2026-10-30-2332-risk-burndown-round-2/e2e-7.log | no |

suite passing · e2e passing · suite runs 4

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS

- [MEDIUM] M1 The casefold in the take-back walk's prune is not needed, has no test, and leaves blocks an older plugin wrote under a case-variant directory with no way back (`skills/project-update/update.py:1370`)  in_scope: yes
  why it matters: `os.walk` returns names as they are spelled on disk. The writer's invariant ("never write where the take-back never walks") only needs the writer's skip set to be a superset of the walker's, so `unwalked_dir`'s casefold (`:1410`) is enough on its own. Putting casefold in the walker as well makes it stop entering directories it walked at HEAD and in B2: `Vendor/` (common in Xcode projects), `pods/` (a Kubernetes repo's own manifests on Linux), `Node_Modules/`, `Third_Party/`. A block HEAD rendered into `pods/api/CLAUDE.md` is now frozen. While the rule still names that directory, the b44b hint covers it. Once the rule is deleted or its `dirs:` changes, the block stays in an instruction file that agents keep reading, and nothing says so: the hint only fires for targets a rule still names. No test covers this hunk. `test_the_rules_skip_comparison_ignores_case` passes the same with the walker comparing exactly: `vendor` on disk is pruned either way, and `Vendor/` and `PODS/` never exist on disk. On a case-sensitive filesystem the writer side also changes behaviour (a project's own `pods/` is no longer rendered). That part is at least visible as a hint.
  suggested direction: keep the walker's exact-name prune and casefold only in the writer (or resolve each component to its on-disk spelling, the risk's other option); if the walker must prune more, have it name the blocks it finds under directories it newly skips.

- [LOW] L1 The b44b hint tells the user to remove a block by hand that the same run already removes, when the symlinked directory points inside the project (`skills/project-update/update.py:1455-1459`)  in_scope: yes
  why it matters: take `linked -> real/`, where an older plugin wrote `linked/CLAUDE.md` (really `real/CLAUDE.md`). The walker enters `real/`, finds `(real/CLAUDE.md, slug)`, sees it is not in `managed`, and proposes "rule block … removed". In the same output, the writer's hint says "an earlier rendering of it is still there, the take-back never walks there: remove that block by hand". That is false here. It is only true when the symlink leads outside the project.
  suggested direction: claim "still there" only when the resolved path is outside the walk (realpath not under root, or under a skipped or nested directory).

- [LOW] L2 The b44b hint reads the target again, which B2's skip had stopped doing (`skills/project-update/update.py:1456`)  in_scope: yes
  why it matters: `plan.read` follows the symlinked directory, so it reads a file outside the project that the writer otherwise never touches. It opens without catching errors: a directory named `CLAUDE.md`, an unreadable file (for example root-owned `node_modules/` from a container) or a FIFO now raises an uncaught `OSError` or blocks inside `rules_update`. B2 skipped these targets before reading them. HEAD read every target, so this is a regression against B2, not against HEAD.
  suggested direction: guard the probe with `os.path.isfile` and no symlink on the way (or catch `OSError`), and drop the "earlier rendering" claim when it cannot be read.

- [LOW] L3 The new stderr line in `bite_codes` prints the raw `testing.md` value without escaping it (`skills/ai-task/sensors.py:261`)  in_scope: yes
  why it matters: `read_commands`'s `(.*)$` keeps `\r` and ESC. A `bite_codes` value holding `\r` or an escape sequence can draw a fake `expected fail: … it bites` over the real verdict line in a terminal, or put that text into the captured output an agent reads. The same task fixed exactly this class in `moved_detail` (e678). The recorded `run["bites"]` is unaffected, so only the display is exposed.
  suggested direction: escape non-printables as `moved_detail`'s `esc()` does (or print `%r`).

- [LOW] L4 Two of the three disk assertions in the case test check paths that were never targets (`tests/test_project_update.py:2524-2525`)  in_scope: yes
  why it matters: the targets are `Vendor/x/CLAUDE.md` and `PODS/y/CLAUDE.md`, but the loop checks `Vendor/CLAUDE.md` and `PODS/CLAUDE.md`. Those two checks are vacuous. The stdout assertions still make the test fail without the fix (verified by reading), so this is weak rather than missing coverage.
  suggested direction: assert on `Vendor/x` and `PODS/y`.

- [INFO] I1 The a0c4 residual is not recorded  in_scope: yes
  why it matters: after the revert, `skills/ai-init/templates/.ai/AGENTS.md:61,67` and `skills/ai-init/templates/.ai/rules/README.md:4,24` still name `/project-update` and `/ai-init`. Neither `task.md` nor the events record a0c4 as only partly closed, or why: the `git merge-file` adjacency breaking an old edited copy (test_migration_0006 r10, test_project_adopt r6_r15). The plan's `files:` still lists the two templates and `tests/test_migration_0006.py` as if they had been touched; all three are byte-identical to HEAD.
  suggested direction: keep a0c4 open in the register for those two templates, with the adjacency reason.

- [INFO] I2 The per-step record cannot attribute edits to steps  in_scope: yes
  why it matters: `step_done` reports s3, s4 and s5 as "0 files changed" and s2 (test_project_adopt only) as "9 files changed", yet round 2 did edit status.py, sensors.py and riskrails.js. The batch implementers ran in parallel, so the step boundary cannot be audited from the record. I checked scope by reading the hunks instead (below).
  suggested direction: none for this task; a note for the batch loop's step accounting.

## EXAMINED AND CLEAN
- Inherited, not re-derived: suite run 2 exit 0 and e2e run 3 exit 0 on tree 4f3058a3. No file under `skills/`, `bin/`, `tests/` or `hooks/` is newer than `suite-2.log`. No review-ledger or `sensors.json` exists for this task.
- **b44b test:** it would fail without the change (no "earlier rendering" text before), it has a negative case (`node_modules/bare` gets no claim), and `tree_sum` shows nothing under the skipped directory is rewritten.
- **a50b writer side:** `unwalked_dir`'s casefold is correct, and the test would fail with an exact compare (`create Vendor/x/CLAUDE.md`).
- **24b3:** the symlink test now fails if the islink guard at `update.py:902` is removed (it would take the render path, and the conflict assertion fails). The absent-JSON test pins `create weight.json` and `conflict weight.md` with rc 0.
- **d45b:** the prefix strip is consistent with the other test files; the suite is green.
- **status.py:** the 3278 docstring matches `budgets()`. `counter()` handles schema 7 first, then legacy `tests` as a dict and `reviews` as an int, then 0. TestFallbackReadsSchema7Counters would fail on the old code (it would show 0).
- **sensors ff63:** `bite_codes` is called only from `state.py:3936`, inside `safe_sensor`. Stdout is unchanged and pinned empty. A failing stderr write is caught and falls back to (1,). No test asserts an empty stderr on a bad value, and the suite is green.
- **riskrails.js 320f:** it takes the last non-empty stdout line. Timeout, exit status, signal and first stderr line are reported. 10c and 10d fail on the reported old behaviour ("found unknown").
- **state.py e678:** `isprintable()` escapes Cc, Cf (including bidi controls) and line separators. The test checks for both a raw ESC and a forged line.
- **RESUME_COMMAND (codex):** it follows the same convention as before (`codex exec '/<skill>'`). `skills/rr-build` is installed to `~/.codex/skills/` like `ai-task`, which is now only a deprecated alias. It also matches the human-facing line at `state.py:1971`. The test is updated.
- **Templates and history:** `AGENTS.md` and `rules/README.md` are byte-identical to HEAD. The new blob `a51517e1…` is the sha256 of the new `state/README.md`, listed once under `ai-init/.ai/state/README.md`. The reverted blobs `c7bb4967…` and `e5045295…` are gone from disk and from `index.json`. No blob is missing from the index.
- **state/README.md merge adjacency:** I compared all 7 earlier versions. The renames are at lines 4, 9, 17 and 40 of 64- to 67-line files (lines 4 and 9 in the 27-line ones), never at the end. Text a project appends at EOF does not touch them, so the AGENTS.md failure mode does not recur. Edits right next to those lines can still produce a conflict copy, as any template change can; no data is lost.
- **Scope:** round 2's hunks stay inside the amended plan. The `schema_line` / `"/rr-setup first"` renames are B4's, and the cleanup-symlink, tracked-ignored and `check=False` hunks are B2's; none were counted against round 2.
- not reached (budget): I did not run the step tests myself (the green suite on the same tree was inherited), and I did not check empirically, with `git merge-file`, that every old edited state/README.md merges cleanly (I reasoned from the diffs instead).

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved, amended plan. The reverted AGENTS.md and rules/README.md hunks leave a0c4 partly open, and that is not recorded (I1). The walker-side casefold (M1) goes further than the invariant needs.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| bin/riskrails.js | +14 −3 | Edit |
| docs/sdlc/plans/small-oop-modules.md | +190 −0 | New |
| skills/ai-init/templates/.ai/state/README.md | +4 −4 | Edit |
| skills/ai-task/sensors.py | +14 −4 | Edit |
| skills/ai-task/state.py | +5 −2 | Edit |
| skills/project-update/history/blobs/a51517e13e57420d2d88a6bcfb4055d762d4a0d10a8f88450929c5c4572213a9 | +67 −0 | New |
| skills/project-update/history/index.json | +2 −1 | Edit |
| skills/project-update/update.py | +30 −2 | Edit |
| skills/rr-status/status.py | +14 −3 | Edit |
| tests/test_ai_status_root.py | +21 −0 | Edit |
| tests/test_ai_task_sensors.py | +32 −0 | Edit |
| tests/test_ai_task_state.py | +14 −2 | Edit |
| tests/test_install_dry_run.py | +21 −0 | Edit |
| tests/test_project_adopt.py | +2 −2 | Edit |
| tests/test_project_update.py | +90 −0 | Edit |

+520 −23 lines, 15 files

## Verdict

close: closed
facts: (a) green — suite green on 73707f6f5 (run 6) · (b) green — 15 changed files, all in the task's files
gate: requested G1 at 2026-10-30T23:58:05Z; approved by Ivan Kakurov at 2026-10-30T23:58:31Z via dialog
confirm: none
handoffs: 7 · suite runs: 4 · review passes: 1
