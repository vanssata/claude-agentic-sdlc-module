# Plan: Interactive setup options — installer menu, /rr-setup dialog, memory + SQLite from setup

Intent: `docs/sdlc/intent/interactive-setup-options.questions.md` · Spec: `docs/sdlc/specs/interactive-setup-options.md`
· Target release 4.1.0 · Written 2026-11-11 against `1e6666a`.

<!-- Stage 3. Each task below is later planned with `/rr-plan` and run with `/rr-build`; its rows are that
     task's steps. The plan argues from the spec; executors read both. -->

## Decisions taken before planning

All by Ivan, 2026-11-11, in the `/rr-plan` dialog.

- **D1 OQ1 resolved:** the author prefill is local config, else `$USER` — the code's own default
  (`memory_sync.enable`), `--author` omitted from the command label; the value and its source are shown in the
  question text. `git config user.name` is not read. Unblocks C4; closes A2.
- **D2 A1 accepted as written:** task B runs in full mode, with a STRONG security-focused review and the human's
  approval; `docs/local-memory.md:35,44` is rewritten inside the same task (B4).
- **D3 B4 accepted:** on a TTY with an undetected Claude plan, Enter installs the highlighted row (`pro`) instead
  of exiting. Non-TTY, `--yes` and every flag path stay byte-identical (O2).
- **D4 The rest accepted as written:** A3, B1, B2, B3, the three C1 defects (documented, not fixed), the D
  assumptions; OQ2–OQ5 take the spec's defaults (OQ2: the Codex fallback covers a cap below 4; OQ3: no
  `--statusline-context` menu; OQ4: "Keep" / "I edit it myself"; OQ5: a teammate's clone is not asked).

## Departures from the spec's delivery order

| Spec | Plan | Why |
|---|---|---|
| Task A holds A1–A5, A2 a refactoring in its own commit | **Task R** = A1 + A2 (workflow refactoring), **Task A** = A3–A5 (feature) | a refactoring and a feature are never one task (C3, `/rr-plan` step 1); A1 pins the refactoring, so it belongs with it |
| A, then B, then C | **B → C**, with R → A in parallel at any time | B3 is the riskiest step; it goes first. R/A touch no file of B or C |
| `scaffold-ai.sh` usage comment (C5) | `skills/ai-init/scaffold-ai.sh` | that is where the script lives (`git ls-files`); `tests/fixtures/scaffold-port/scaffold-ai.sh` is a frozen port fixture and is not edited |

## Global constraints

Copied from the spec; every task's requirements include them.

- Non-TTY, `--yes` and any flag-given choice: installer stdout, stderr and written files byte-identical to 4.0.1 (O2).
- Zero npm dependencies; `package.json` `"dependencies": {}` unchanged (Q4). `bin/` is already in `files`.
- `hooks/ai-path-guard.sh` `SH_WORD`/`SH_RE` are not touched (repo `CLAUDE.md`).
- `memory disable|cleanup|pack|redact|migrate --move-logs` stay terminal-only (exit 5 from an agent).
- The agent never writes `.ai/policies/*.json`; `memory.json` is written by `memory enable` itself.
- No settings registry, no gate on `start`, no SessionStart detection (Q3).
- A BLOCKER closes only with a test that pins it (repo `CLAUDE.md`).

## Files that change

Paths under `rr_state/` are `skills/ai-task/rr_state/`.

| Step | Files |
|---|---|
| R1 | new `tests/test_install_menu.py` (`TestTypedPrompt`, pty helpers) |
| R2 | edit `bin/riskrails.js` (extract `pickClaudePlan` from `:397-406`, `pickCodexPlan` from `:1275-1282`; no output change) |
| A3 | new `bin/menu.js`; edit `tests/test_install_menu.py` (`TestReducer`) |
| A4 | edit `bin/riskrails.js` (`choose()`, `FABLE_GIVEN`, `CONTEXT_GIVEN`, `TARGET_GIVEN` next to `:61-101`, the six menus, abort, `RISKRAILS_MENU`), `tests/test_install_menu.py` (`TestMenu`) |
| A5 | edit `README.md`, the header of `bin/riskrails.js` (the `--help` text) |
| B1 | edit `tests/test_memory_pre_push.py` (`test_enable_refused_dialog_on_no_pick`) |
| B2 | edit `rr_state/labels.py:45-81`, `hooks/guard/dialog.py:222-239`, `tests/test_dialog_gate.py`, `tests/test_dialog_contract.py`, `tests/fixtures/state/partition.json` |
| B3 | edit `rr_state/memory_cmd.py` (`memory_enable:100`, `memory_human:42` gains `allow_dialog`), `tests/test_memory_pre_push.py`, `tests/fixtures/state/partition.json` |
| B4 | edit `docs/local-memory.md:35-44`, `skills/ai-init/templates/.ai/policies/safety.md:30-34`, `skills/project-update/history/**` (only via `tools/build-template-history.py`), `docs/sdlc/specs/command-choice-dialog.md` |
| C1 | edit `rr_state/dialog_cmd.py` (`decision_open:55` gains `--kind setup --spec`, `decision_settle:86` prints `SETUP_PICK`), `rr_state/cli.py:180-183`, `tests/test_dialog_gate.py`, `tests/fixtures/state/partition.json` |
| C2 | edit `tests/test_dialog_consent.py` (`test_setup_round_memory_first`) |
| C3 | edit `skills/rr-setup/setup.py` (`options --json`), `tests/test_setup.py` (`TestOptions`) |
| C4 | edit `skills/rr-setup/setup.py` (`options --open`, fallback text), `tests/test_setup.py` |
| C5 | edit `skills/rr-setup/scaffold_ai.py:47-62,145-158` (`--runtime none`), `skills/ai-init/scaffold-ai.sh` (usage comment), `tests/test_scaffold_idempotency.py`; `tests/test_scaffold_differential.py` only if it enumerates runtimes |
| C6 | edit `skills/rr-setup/SKILL.md` (step 0, apply order, `--options`, `argument-hint`), `tests/test_skills_surface.py` |

## Order of work

Each task: every step runs `step_test_command` on its named tests before `step-done`; the task ends with
`verify_command` once to the end, then `e2e_command` once (`.ai/policies/testing.md:37-39,92-94`). **Mode** is
the expected value; the one `state.py weight` computes when the task is planned wins, and raising it is free.

### Task B — memory route (first; riskiest) · workflow feature · expected **full** (behaviour 2, C6; D2)

Consumes: —. Produces: `memory_human(root, what, allow_dialog=False)`; `memory enable` accepted by both label
allowlists; the line `memory: via dialog (consent C<n>, decision D<n>)`.

1. **B1** characterization (C2): with the dialog on and no pick, `memory enable` from an agent exits 5. Green on
   today's tree. Tests: `tests/test_memory_pre_push.py::test_enable_refused_dialog_on_no_pick`.
2. **B2** allowlists: `memory enable [--author S] [--period P] [--index none|sqlite]` — and no other `memory` verb —
   in `labels.py` and its copy in `hooks/guard/dialog.py`. Tests: `test_dialog_gate.py::test_label_validator`,
   `test_dialog_contract.py::test_both_label_rules_agree`, `tests/test_state_layout.py` (partition).
3. **B3 ⚠ riskiest step** — `memory_enable` passes `allow_dialog=True`; nothing else in `memory_cmd.py` changes.
   Tests: `test_memory_pre_push.py::test_enable_via_dialog_pick`, `::test_enable_pick_used_once`,
   `::test_disable_stays_terminal`, B1's test still green.
4. **B4** docs: a memory pick in the dialog is a human route; template history regenerated by the tool. Tests:
   `test_project_update.py::test_history_covers_every_template`, the doc tests.

Then `/rr-review` on STRONG, security-focused; `/rr-ship` requests the human's approval.

### Task C — setup options (after B) · workflow feature · expected **full** (B1: a new decision opener)

Consumes: B (`memory enable` label passes `validate_label`; `allow_dialog` on enable). Produces:
`state.py decision open --kind setup --spec FILE|-`; `SETUP_PICK key=value`; `setup.py options [--all] --json|--open`
with first line `OPTIONS_DIALOG …` | `OPTIONS_FALLBACK <why>` | `OPTIONS_NONE`; `scaffold-ai.sh --runtime none`.

1. **C1** opener and settle (atomic open, the label checks of spec §Interfaces). Tests:
   `test_dialog_gate.py::test_setup_spec_opens_atomically`, `::test_setup_spec_rejects_foreign_command`,
   `::test_setup_settle_prints_pick`, `tests/test_state_layout.py`. Consumes B2.
2. **C2** pin only: in a four-question round the memory pick is next and passes the gate. Tests:
   `test_dialog_consent.py::test_setup_round_memory_first`. Consumes C1, B3.
3. **C3** `options --json`, read-only. Tests: `test_setup.py::TestOptions::test_fresh_all_unset`,
   `::test_detects_configured`, `::test_writes_nothing`.
4. **C4** `options --open` + fallback; author per D1. Tests: `::TestOptionsOpen::test_open_prints_dialog`,
   `::test_memory_labels_prefilled`, `::test_no_git_no_memory`, `::TestOptionsOpenOutcomes::test_dialog_off_fallback`.
   Consumes C1, C3.
5. **C5** `--runtime none`. Tests: `test_scaffold_idempotency.py::test_runtime_none`,
   `tests/test_scaffold_differential.py`.
6. **C6** `SKILL.md` flow. Tests: `test_skills_surface.py::test_rr_setup_options_flow`. Consumes C4, C5.

### Task R — installer characterization + extract (any time) · workflow **refactoring** · expected guarded

Consumes: —. Produces: `pickClaudePlan()`, `pickCodexPlan()`; `tests/test_install_menu.py` pty helpers.

1. **R1** (spec A1) characterization on a pty: Enter confirms, a typed value, Codex, the non-TTY stderr lines.
   Green on today's tree. Tests: `tests/test_install_menu.py::TestTypedPrompt`.
2. **R2** (spec A2) extract the two plan pickers; behaviour unchanged. Tests: R1's tests, `tests/test_install_dry_run.py`,
   `tests/test_codex_install.py`.

### Task A — installer menu (after R) · workflow feature · expected guarded (C6: no project decision moves)

Consumes: R (`pickClaudePlan`, `pickCodexPlan`, the pty helpers).

1. **A3** `bin/menu.js`: pure reducer + keypress child, exit 0/130/3. Tests: `::TestReducer::test_keys`.
2. **A4** wire `choose()` and the six menus in order runtime, plan, fable, context, statusline, Codex plan. Tests:
   `::TestMenu::*` (R3–R8), and R1's tests under `RISKRAILS_MENU=off`.
3. **A5** `README.md` and the `--help` header. Tests: `tests/test_install_dry_run.py` (help text), doc tests.

## Risks

| # | What could break | Where it shows | Mitigation |
|---|---|---|---|
| 1 | **B3** widens who can turn on a committed, project-wide mode and write `.git/hooks/pre-push` | any agent route reaching `memory enable` | argv identity binds the pick; other argv, a second run and `disable/cleanup/pack/redact` → 5 are each a test; STRONG security review (D2) |
| 2 | The two label allowlists drift (B2) | the gate passes what `state.py` refuses, or the reverse | `test_both_label_rules_agree` feeds both the same cases |
| 3 | C1 lets the model open decisions whose choice text misleads | a human picks a misdescribed option | choices run nothing; the only command is this `state.py`'s `memory enable` for this root; a choice label never equals or starts like a command; `consent audit` afterwards (B1 accepted, D4) |
| 4 | Four setup questions fill `DECISIONS_MAX`; an open decision makes the open fail | `/rr-setup` exits 6 | atomic: none opened; the skill settles first or falls back (B2) |
| 5 | Pick window (120 s) and order: memory must be the next live pick | memory label refused by the gate | memory opened first; pinned by C2 / R15 (B3, INFERENCE until then) |
| 6 | Raw mode left on after a crash; parent stdin competing with the child | user's terminal unusable | child owns raw mode; `stty -g` equal before/after is a test (R7); parent prints a `stty sane` hint on a killed child |
| 7 | Non-TTY output drifts (O2) | CI installs, `install_harness.py` goldens | the menu runs only on a TTY; R1 green under `RISKRAILS_MENU=off`; existing install tests unchanged |
| 8 | `--runtime none` changes the scaffold port's behaviour | `test_scaffold_differential.py` | new value only; `auto|claude|codex|both` paths untouched |
| 9 | Template history out of date after B4 | `test_history_covers_every_template` | regenerate only with `tools/build-template-history.py` |
| 10 | Reverting B after a project enabled memory through a pick | that project stays in packages mode | rollback note below |

## Proof (tests)

| R | Proof |
|---|---|
| R1 | `tests/test_install_menu.py::TestTypedPrompt::*` green on `1e6666a` and under `RISKRAILS_MENU=off` after A4 |
| R2 | `::TestReducer::test_keys` |
| R3 | `::TestMenu::test_plan_enter_confirms`, `::test_plan_arrow_down` |
| R4 | `::TestMenu::test_codex_plan` |
| R5 | `::TestMenu::test_runtime_menu` |
| R6 | `::TestMenu::test_option_menus_and_flags` |
| R7 | `::TestMenu::test_abort_restores_terminal` |
| R8 | `::TestMenu::test_menu_off_typed_prompt` |
| R9 | `tests/test_setup.py::TestOptions::test_fresh_all_unset`, `::test_detects_configured`, `::test_writes_nothing` |
| R10 | `::TestOptionsOpen::test_open_prints_dialog` |
| R11 | `tests/test_dialog_gate.py::test_setup_spec_opens_atomically`, `::test_setup_spec_rejects_foreign_command` |
| R12 | `tests/test_dialog_gate.py::test_setup_settle_prints_pick` |
| R13 | `tests/test_dialog_gate.py::test_label_validator`, `tests/test_dialog_contract.py::test_both_label_rules_agree` |
| R14 | `tests/test_memory_pre_push.py::test_enable_refused_dialog_on_no_pick` (first, green before B3), `::test_enable_via_dialog_pick`, `::test_enable_pick_used_once`, `::test_disable_stays_terminal` |
| R15 | `tests/test_dialog_consent.py::test_setup_round_memory_first` |
| R16 | `::TestOptionsOpen::test_memory_labels_prefilled` (D1: no `--author` when local config or `$USER` gives it; source in the text), `::test_no_git_no_memory` |
| R17 | `::TestOptionsOpenOutcomes::test_dialog_off_fallback` |
| R18 | `tests/test_scaffold_idempotency.py::test_runtime_none` |
| R19 | `tests/test_skills_surface.py::test_rr_setup_options_flow` |
| R20 | doc tests; `tests/test_project_update.py::test_history_covers_every_template` |
| all | per task: `verify_command` once to the end, then `e2e_command` once |

## Rollback

`git revert` of the task's merge commit, per task; tasks revert independently except C, which needs B (revert C
first). A project that turned memory on through a pick stays in packages mode after reverting B: the human runs
`state.py memory disable` in their own terminal.
