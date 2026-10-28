# Plan: Batch build — one task for a whole plan, parallel implementers and fixers, a review loop that stops at the human after three failed passes

Intent: `docs/sdlc/intent/batch-build.md` · Spec: `docs/sdlc/specs/batch-build.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Written 2026-10-28 on `feat/batch-build` (HEAD `520e065`). One task in **full** mode (C6: the budgets and
the switch change when the human is asked — behaviour 2, declared), four steps in dependency order, one
STRONG review, the human's approval at `close`. The task runs in a worktree so `new-refactor` and its
task in flight (T-2026-10-28-011) stay untouched. No agent commits (C5).

## Files that change

| Step | Files |
|---|---|
| s1-policy | edit `skills/ai-init/templates/.ai/policies/weight.json` (the `batch` section), `skills/ai-task/weight.py` (`mirror()` prints a `Batch:` line); regenerate `skills/ai-init/templates/.ai/policies/weight.md` (`state.py --root skills/ai-init/templates weight --mirror`); edit `tests/test_weight.py` |
| s2-state | edit `skills/ai-task/state.py` (`BATCH_DEFAULTS`, `batch_policy`, `budget`, `after` in `parse_steps`, `check_steps`, `order_shared_files`, `ready_steps`, `cmd_steps`, `cmd_batch`, `start --batch/--no-batch`, `step-done` by readiness, the `batch_set` event, the status/handoff/task.md lines, help text); edit `tests/test_ai_task_state.py` (class `TestBatch`) |
| s3-skill | new `skills/rr-build-all/SKILL.md`; edit `skills/rr-build/SKILL.md`, `skills/rr-plan/SKILL.md`, `skills/rr-review/SKILL.md` (a few lines each); edit `tests/test_skills_surface.py` (`NEW` gains `rr-build-all`; one test that the skill names commands `state.py` accepts) |
| s4-docs | edit `ai/using-riskrails.md` (one table row, one short section), `docs/weight.md` (section "Batch"), `README.md` (one paragraph under Use); regenerate `skills/project-update/history/**` (`tools/build-template-history.py`) |
| — | the record of this task: `docs/sdlc/intent/batch-build.md`, `docs/sdlc/specs/batch-build.md`, `docs/sdlc/plans/batch-build.md`; `.ai/project/known-risks.md` for anything found outside the task |

Nothing under `hooks/`, `bin/`, `install.sh`, `instructions/` or `skills/project-update/migrations/`
changes: a new top-level key needs no migration (R13), the installer copies every `skills/*` directory,
and the global instruction block is not touched (its 2560 B budget stays as it is).

## Order of work

1. **s1-policy** — the table first, so every later step reads real numbers. `batch` in the template with
   the shipped values; `mirror()` prints `Batch: …`; regenerate the template mirror. Proof: `tests/test_weight.py`
   (the shipped section's keys and values; `test_mirror_fresh`).
2. **s2-state** (after s1) — **the riskiest step**: it touches `start`, `verify`, `review`, `step-done`,
   `status`, `handoff` and `task.md`. What stays the same: a task without `after` and without `--batch`
   behaves byte-for-byte as today (same `next_action`, same lines, same budgets) — the existing
   `TestStart`, `TestModes`, `TestReviewPass1/2`, `TestSurface` are the characterization. New tests
   (`TestBatch`): unknown/cyclic `after` refused; `steps --ready` by waves; shared-file ordering printed and
   applied; `--batch --by` on, `--no-batch` off, the project default; three passes then `REVIEW_BUDGET`
   naming `batch.review_rounds_max`; the suite budget 8; `batch off` returns the standard budgets counting
   what was spent; `batch on` from an agent exits 5, from the human route turns on; the `batch_set` event is
   refused by `event`; the status, handoff and task.md lines; the 20/30-line caps. Proof:
   `tests/test_ai_task_state.py`, `tests/test_ai_status_root.py`, `tests/test_weight.py`.
3. **s3-skill** (after s2) — the skill text and the three edits; `NEW` in the surface test. Proof:
   `tests/test_skills_surface.py`, `tests/test_instruction_budget.py` (rr-build + template weight.json +
   template testing.md ≤ 400 lines), `tests/test_codex_agent_render.py`.
4. **s4-docs** (after s3) — the shared tree, the prose, the README, then the history rebuild. Proof:
   `tests/test_project_update.py` (history covers every template), `tests/test_shared_prompts_model_free.py`.

Then `state.py verify --scope all` once to the end (`bash tests/run-all.sh`, then
`AI_E2E=1 … test_end_to_end.py`), every failure fixed as one batch; one STRONG `ai-reviewer`; `close`.

## Risks

- **Budget reads missed.** A path that still reads `policy["review_rounds_max"]` directly would refuse a
  batch task at the third pass. Noticed by: `grep -n 'review_rounds_max\|max_suite_runs' state.py` lists
  only `budget()` and the mirror text after s2; `TestBatch` runs three passes.
- **`step-done` picks a step whose dependencies are open.** The "first ready pending step" rule reduces to
  today's "first pending step" when no step has `after`; a test covers both.
- **The handoff over 30 lines, status over 20.** One added line each; `tests/test_instruction_budget.py`
  pins the handoff, `status_lines` truncates at 20 — the batch line is placed before the truncation point
  (after `mode:`), so it is never the one cut.
- **Skill length and budgets.** The surface test caps a skill at 300 lines; the instruction-budget test
  caps rr-build + weight.json + testing.md at 400 lines (351 today). Each edit is counted before `verify`.
- **History stale.** `tools/build-template-history.py` runs last in s4; `test_project_update` fails while
  it is stale.
- **Codex parity.** No model name in any skill or in `ai/`; the model-free test guards it.
- **This repository's own table** is frozen during the task (FC5): the `batch` section is merged in later by
  the human with `/rr-setup --update`; the code defaults make the feature work meanwhile.

## Proof (tests)

| Requirement | Proof |
|---|---|
| R1 (rows → steps; a human row is a question) | `/rr-build-all` text; `TestBatch.test_a_pending_question_blocks_the_next_wave` (ask, then `step-done` exits 4) |
| R2 (`after`: unknown, cycle, shared-file ordering) | `TestBatch.test_after_unknown_self_cycle_and_shape_refused`, `test_shared_file_orders_steps`, `test_shared_tests_and_patterns_order_steps`, `test_the_first_ready_step_starts` |
| R3 (`steps --ready` by waves) | `TestBatch.test_steps_ready_by_waves`, `test_a_wave_is_recorded_in_any_order` (recorded in any order; the journal's `own`/`others`/`unready`) |
| R4 (parallel implementers, contract, no state.py from a subagent) | `/rr-build-all` text; `test_skills_surface.TestNewSkills.test_build_all_names_live_commands` |
| R5, R6 (one verify, parallel fixers, full pass after blockers) | `/rr-build-all` text; `TestBatch.test_three_passes_then_the_human` (verify/review sequence) |
| R7 (batch budgets, REVIEW_BUDGET on pass 4, SUITE_BUDGET on run 9) | `TestBatch.test_three_passes_then_the_human`, `test_suite_budget_is_eight` |
| R8 (`--batch --by`, `--no-batch`, `batch.default`) | `TestBatch.test_flag_and_project_default` |
| R9 (`batch off` counts what was spent; `batch on` is the human's) | `TestBatch.test_three_passes_then_the_human` (the `batch off` half), `test_batch_on_is_the_humans` |
| R10 (mode, gate, nevers unchanged) | existing `TestModes`, `TestTwoFacts`, `TestReviewPass1/2` green; `TestBatch.test_full_mode_still_asks_the_human`, `test_steps_without_after_behave_as_before` |
| R11 (status, handoff, task.md lines; caps) | `TestBatch.test_lines_show_batch` (+ `test_instruction_budget` handoff ≤ 30) |
| R12 (skill, texts, mirror, history) | `test_skills_surface`, `test_weight.test_mirror_fresh`, `test_project_update`, `test_instruction_budget`, `test_shared_prompts_model_free` |
| R13 (no section → defaults; a malformed section refused at start; the fan-out rule on `tier`/`parallel`) | `TestBatch.test_table_without_the_section_uses_the_defaults` |
| R14 (`batch_set` not forgeable) | `TestBatch.test_batch_set_is_not_forgeable` |

## Rollback

`git revert <the task's commit>`: every change is in tracked files; no migration, no data, no user tree
is touched. A user project that already merged the `batch` key keeps an ignored key, which `load_policy`
tolerates. Nothing a revert does not undo.
