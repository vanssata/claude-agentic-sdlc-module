# Plan: UI-first approvals and an installer wizard (4.3.0)

Spec: `docs/sdlc/specs/ui-first-approvals.md` · Decisions: `docs/sdlc/intent/ui-first-approvals.questions.md`
· Record: `docs/sdlc/specs/ui-first-approvals.lessons.md`

Status: written 2026-11-15, not yet accepted. Run by `/rr-build-all` as one task, one cycle,
on `feat/ui-first-approvals` (cut from `main` at `b7a04b2`).

**Model routing.** Implementers and fixers: `general-purpose`, `model: sonnet`. Every suite,
golden-diff, lint and CI log: `log-reader`, `model: haiku`, returning `file:line` excerpts.
The session decides: wave dispatch, every conflict, every fix-or-defer, the lessons rows.
One `ai-reviewer` at the mode's tier (full: STRONG, `model: opus`).

**Flagged concerns of the spec.** Shown to Ivan on 2026-11-15; he committed the spec
(`c09867c`) and ran `/rr-plan`. Taken as accepted: 1 (answers recorded as his), 3 (memory
verbs and deletions keep the terminal), 4 (R3 decided by its failing test), 5 (two switch
readers), 6 (size; the cut is uninstall), 8 (Codex `config.toml` kept on uninstall). Still
his, outside the task: 2 (the Remote Control probe, after the release) and 7 (below).
Q10 (2026-11-15, Ivan's answer) added R23–R28 and concerns 9–13 — shown to him with the
revised spec; step s17 and the `ROADMAP.md` line of s15 are theirs.

**Before the start (human).** `fix/ere-lazy-compile` (`5e0a2a8`) edits the guard and is not
on `main`. Ivan chose to merge it first: PR #82 is open. After its merge this branch is
rebased onto `main`, and only then does `state.py start` run.

## Files that change

| Area | Files | What |
|---|---|---|
| label twins | `skills/ai-task/rr_state/labels.py`, `hooks/guard/dialog.py` | edit: `batch on --by` as a label; `labels.describe` |
| dialog core | `rr_state/dialog.py`, `dialog_cmd.py`, `cli.py` | edit: `human_refusal`, `decision open --kind install` |
| state refusals | `rr_state/steps.py`, `questions_cmd.py`, `gate.py`, `close.py`, `start.py`, `verify.py`, `review.py` | edit: dialog-first text when the dialog is on; `batch on` takes the pick |
| status | `rr_state/report.py`, `report_cmd.py`, `skills/rr-status/status.py`, `skills/rr-status/SKILL.md` | edit: `waiting on …` line, `--json` key |
| hooks | `hooks/guard/paths_base.py`, `paths_bash.py`, `git.py`, `decision.py`, `hooks/dialog-gate.py` | edit: dialog-on texts; the `npx` pick is spent |
| statusline, notice | `hooks/runtime-gate.py`, `hooks/update_notice.py`, `hooks/context-guard.py` | edit: task segment; dialog-first notice |
| skill texts | `skills/rr-build/SKILL.md`, `skills/rr-spec/SKILL.md` | edit: picker first |
| installer | `bin/ansi.js`, `bin/wizard.js`, `bin/uninstall.js` (new); `bin/menu.js`, `bin/riskrails.js` (edit) | colour, wizard, review, uninstall, backup stamp |
| fixtures | `tests/fixtures/{state,guard}/partition.json`, `tests/fixtures/guard-characterization/golden.txt`, `tests/fixtures/dialog/payload-golden/*.json`, `tests/fixtures/memory/goldens/status-py.txt`, `tests/fixtures/install/non-tty.golden` (new) | re-recorded where a text or a name moved |
| docs | `docs/glossary.md`, `docs/dialog-probe.md`, `docs/media/wizard.tape` (new); `docs/faq.md`, `docs/installation.md`, `docs/known-risks.md`, `README.md`, `CHANGELOG.md`, `ROADMAP.md` | edit; the 4.4.0 diet named in the roadmap |
| tight code | `ai/agents/implementer.md`, `ai/agents/reviewer.md`, `agents/ai-reviewer.md.tmpl`, `skills/ai-init/templates/.ai/policies/coding.md`, `skills/rr-ship/SKILL.md`, `skills/project-update/history/` (regenerated) | edit: the texts of the spec's §Interfaces, verbatim |
| version | `package.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json` | 4.3.0 through `tools/sync-version.py` |

## Order of work

Each row is one step. *Files* are what the step may edit; *New tests* are the files it
creates and holds. An existing shared suite has one owner per chain and is listed under
*Files*, never under two parallel steps — `start` orders steps that share a file.

| Step | Does (requirements) | Files | New tests | After |
|---|---|---|---|---|
| s1 twins | R1: the `batch on` rule as data in both twins, `labels.describe` | `rr_state/labels.py`, `hooks/guard/dialog.py`, `tests/test_dialog_contract.py`, `tests/test_dialog_gate.py` | – | – |
| s2 statusline | R11 | `hooks/runtime-gate.py` | `tests/test_statusline_task.py` | – |
| s3 notice | R8 | `hooks/update_notice.py`, `hooks/context-guard.py`, `tests/test_update_notice.py` | – | – |
| s4 picker | R10 | `skills/rr-build/SKILL.md`, `skills/rr-spec/SKILL.md` | `tests/test_picker_first_texts.py` | – |
| s5 golden | R13: the non-TTY and `--yes` output of today's installer, recorded before any `bin/` edit | `tests/fixtures/install/non-tty.golden` | `tests/test_install_non_tty.py` | – |
| s6 menu | R14, the menu half of R15: colour gate, stepper, back, help line, multi-select | `bin/ansi.js`, `bin/menu.js`, `tests/test_install_menu.py` | – | – |
| s7 planners | pure halves of R15–R18 | `bin/wizard.js`, `bin/uninstall.js` | `tests/test_install_wizard.py`, `tests/test_install_uninstall_plan.py` | – |
| s8 dialog core | R4, R5, the helper for R7 and R9 | `rr_state/dialog.py`, `rr_state/dialog_cmd.py`, `rr_state/cli.py` | `tests/test_dialog_human_verbs.py` | s1 |
| **s9 hooks** (riskiest) | R3 with its failing test first, R6; golden re-recorded, `tools/golden-diff.py` output kept | `hooks/guard/{paths_base,paths_bash,git,decision}.py`, `hooks/dialog-gate.py`, `tests/fixtures/guard-characterization/golden.txt`, `tests/test_dialog_consent.py`, `tests/test_dialog_gate.py`, `tests/fixtures/dialog/payload-golden/*.json` | `tests/test_dialog_first_hooks.py` | s1 |
| s10 backups, uninstall | R18, R19; counts the suites that pin `backups/<date>` first | `bin/riskrails.js`, `tests/test_install_dry_run.py`, `tests/test_install_routes.py`, `tests/test_codex_install.py` | `tests/test_install_uninstall.py`, `tests/test_install_backups.py` | s5, s7 |
| s11 state refusals | R2, R7, R9: `batch on` takes the pick; the seven refusal sites | `rr_state/{steps,questions_cmd,gate,close,start,verify,review}.py`, `tests/test_ai_task_state.py` | `tests/test_dialog_batch.py`, `tests/test_dialog_first_state.py` | s8, s9 |
| s12 status | R12 | `rr_state/{report,report_cmd}.py`, `skills/rr-status/{status.py,SKILL.md}`, `tests/test_ai_status_root.py`, `tests/test_ai_task_state.py`, `tests/test_state_characterization.py`, `tests/test_memory_characterization.py`, `tests/fixtures/memory/goldens/status-py.txt` | – | s11 |
| s13 wizard wiring | R15–R17 in the installer | `bin/riskrails.js` | `tests/test_install_wizard_pty.py` | s6, s10 |
| s14 partitions, lint | both partitions recomputed (`tools/state-partition.py --write` and the guard's), `test_state_layout`, `test_guard_layout`; `pylint` on every new module by name | `tests/fixtures/state/partition.json`, `tests/fixtures/guard/partition.json` | – | s9, s12 |
| s15 docs | R20, R28 | `docs/glossary.md`, `docs/dialog-probe.md`, `docs/media/wizard.tape`, `docs/faq.md`, `docs/installation.md`, `docs/known-risks.md`, `README.md`, `ROADMAP.md` | – | s11, s13 |
| s16 version, record | R21, R22; the README test count; the CHANGELOG credits the Q10 reading | `package.json`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `.codex-plugin/plugin.json`, `CHANGELOG.md`, `README.md`, `docs/sdlc/specs/ui-first-approvals.lessons.md` | – | s14, s15, s17 |
| s17 tight code | R23–R27: counts the suites that pin these texts first; the wording of the spec's §Interfaces, verbatim; `tools/build-template-history.py`; a second Codex copy of the reviewer text, if one exists, gets the same lines by `SCOPE_CHANGE_REQUIRED` | `ai/agents/implementer.md`, `ai/agents/reviewer.md`, `agents/ai-reviewer.md.tmpl`, `skills/ai-init/templates/.ai/policies/coding.md`, `skills/rr-ship/SKILL.md`, `skills/project-update/history/index.json` and the blobs the tool writes | `tests/test_tight_code_texts.py` | – |

Waves (at most five agents at once, `batch.parallel`): **1** s1–s7, s17 · **2** s8, s9, s10 ·
**3** s11, s13 · **4** s12, s15 · **5** s14 · **6** s16 (the session).

Rules for every implementer brief:
- Dialog off, `AI_UNATTENDED`, non-TTY and `--yes`: today's bytes. A test that pins one of
  them and turns red means the change is wrong, not the test.
- A red assertion in a file the step does not own is reported, never edited; the session
  hands it to the owner or to the wave's fixer batch.
- A bugfix shows its test failing on the tree before the fix (s9, R3). If R3's test is
  green on today's tree, no code changes and the step says so.
- A new pattern over command text in the bash guard gets its `timed` case beside
  `tests/test_ai_path_guard.py:398-413`. None is planned.
- A step that edits a shipped template or `ai/` runs `tools/build-template-history.py`.
- Scratch files go under the step's own `scratchpad/<step-id>/`, written by Bash heredoc.
- Q10 holds for this build through the brief, because the installed plugin is 4.2.0: every
  implementer and fixer brief carries, verbatim from the spec's §Interfaces, the two
  implementer lines (simplest version; no new dependency) and the three coding lines (one
  function one thing; inputs in, result out; what an error message says).
- s17 writes texts, not rules of its own: a sentence that is not in the spec's §Interfaces is
  not added, and no size is named anywhere (`tests/test_no_size_tokens.py`).
- R12 as built: the `waiting on …` line is added only when a task is in flight or a
  decision is open; with no task the output is today's (`task: none — no task in flight`).

The lessons file is in the task's files: after each wave the session appends one row per
step; after the review, each row's "review findings" cell gets its count of `padding:`
findings ("padding 0" is written). A row holds — first-try green or not, the error text, what fixed it, tokens when the harness
reports them, and what the base workflow should change.

### Batch end

`state.py verify --scope all` once, after s16; `log-reader` reads the log; every failure is
fixed by one batch of parallel sonnet fixers. Then one review, focus list R1, R3, R4, R18, with the two Q10 list items (padding, an
unplanned dependency) and the `READ FIRST` section in its brief, verbatim from the spec,
plus the `golden-diff` output of s9. Its in-scope BLOCKER and HIGH findings go to one fixer
batch, each closed by a test. Uninstall still red after its fixer batch: the session
unregisters `--uninstall`, keeps `bin/uninstall.js` and its tests, and writes the deferral
into the CHANGELOG and the lessons file (Q9).

## Risks

| Risk | How it shows | Mitigation |
|---|---|---|
| **s9 re-records the guard golden and hides a decision flip** | an allow where a deny was | `tools/golden-diff.py` output pasted in the step report and read by the reviewer; new allow cases live in tests, not in the golden |
| Twin drift | `test_dialog_contract` red | one step owns both twins; table equality plus generated-argv parity |
| A behaviour-2 effect without its test (CLAUDE.md) | a BLOCKER in review | each moved refusal: one positive test, its negatives in `TestStillRefused` |
| Dialog-off bytes move | `test_ai_task_state`, `test_state_characterization` red | `human_refusal` returns `None` without a decision; R7's off cases compare with today's constants |
| Installer output moves | `test_install_non_tty` red | s5 lands before s10; backups keep `backups/<date>` for the first run of a day |
| Raw terminal left behind | the pty test hangs | Esc, Ctrl-C and SIGTERM cases; `stty sane` named in the abort text as today |
| Uninstall loses user data | round-trip test red | move, never delete; settings keys removed only when equal to the rendered snippet |
| Status line breaks goldens | `status-py.txt`, characterization suites red | the line appears only with a task or an open decision; s12 owns those suites |
| A text pinned by a suite s17 does not own | `test_shared_tree`, an installer list or the `project-update` history red | s17 counts them before its first edit; the history is regenerated in the step; the `doc_tests` are its step tests |
| The reviewer spends its pass on taste | a long review, padding findings above MEDIUM | the cap is in the text (three, MEDIUM at most); R27 is the first Q10 cut |
| Partition and lint | `test_state_layout`, `pylint` on untracked modules | s14, with new modules linted by name |
| Second-resolution names under load | a backup-stamp test flakes in the full suite | s10's tests inject the clock; none sleeps |
| A wrong `after` cannot be amended | `close --abandon` and a new `start` | the `after` column comes from the files above; `start` prints every `ordered:` line — read them before the first dispatch |
| The review is large (about 3k lines) | budget of review rounds | the focus list; step reports carry the diffs' summaries |

## Proof (tests)

| R | Proof |
|---|---|
| R1 | `tests/test_dialog_contract.py`, `tests/test_dialog_gate.py` |
| R2 | `tests/test_dialog_batch.py` |
| R3 | `tests/test_dialog_consent.py`, the failing run shown first |
| R4, R5 | `tests/test_dialog_human_verbs.py` (`TestStillRefused` for R5) |
| R6 | `tests/test_dialog_first_hooks.py`, `tools/golden-diff.py` |
| R7, R9 | `tests/test_dialog_first_state.py` (`TestPlainWords` for R9) |
| R8 | `tests/test_update_notice.py` |
| R10 | `tests/test_picker_first_texts.py`, `tests/test_instruction_budget.py` |
| R11 | `tests/test_statusline_task.py` |
| R12 | `tests/test_ai_status_root.py` |
| R13 | `tests/test_install_non_tty.py` |
| R14 | `tests/test_install_menu.py` |
| R15–R17 | `tests/test_install_wizard.py`, `tests/test_install_wizard_pty.py` |
| R18 | `tests/test_install_uninstall.py`, `tests/test_install_uninstall_plan.py` |
| R19 | `tests/test_install_backups.py` |
| R20 | the `doc_tests` of `.ai/policies/verification.md` |
| R21 | the lessons file has a row for s1–s17 |
| R22 | `python3 tools/sync-version.py --check` |
| R23–R27 | `tests/test_tight_code_texts.py`, the `doc_tests` (`test_project_update`, `test_shared_tree`, `test_instruction_budget`, `test_no_size_tokens`) |
| R28 | `ROADMAP.md` names the 4.4.0 step |
| all | `state.py verify --scope all`, once |

## Rollback

Before the merge: drop the branch. After it: `git revert` the merge commit on `main`; the
npm package cannot be unpublished, so publish 4.3.1 from the revert and
`npm deprecate riskrails@4.3.0`; a user returns with `npx riskrails@4.2.0`. No schema change is
planned, so no project migration is undone.
