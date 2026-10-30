# Plan: Register groups 1–4 — cleanup findings, CI/release, stale names, state and guard fixes

Status: accepted 2026-10-30 by Ivan Kakurov (decisions below); run by `/rr-build-all`.

Source: `state.py memory risks --md` on HEAD bcbe68b, split into four groups and measured by
four read-only discovery passes (2026-10-30). Only entries that are still valid on HEAD and
need no further design are in this plan; the rest are listed under **Out of this plan**.

## Decisions (human, 2026-10-30)

| Q | Pick |
|---|---|
| G1 | M1: `logs/<id>/state.json` result is authoritative; a journal with `gate_approved` is never proposed. M2: keep an abandoned task's `state.json`; rows, comment and rr-setup say the logs are git-ignored and not recoverable. M3: a new `--confirm-cleanup NAME`, with the same human/tty checks as `--confirm-delete`; `--confirm-delete` no longer settles `[cleanup]` rows. |
| G2 | `.pylintrc` stays the human's (no fail-on change). Pin pylint to one version in `pylint.yml` and `npm-publish.yml`; a `find_print` unit test. Prerelease: `npm publish --tag next` when the version has a `-`. Rerun: publish skips the upload when `npm view riskrails@V version` already answers. `NODE_AUTH_TOKEN`: unchanged, the unknown is documented in the comment. |
| Behaviour 2 | Guard rules E8/E11/E13 are in: `HUMAN_BY_RE` applies with the dialog on and off and covers `start --mode … --by`; the dead `SETBY_RE` rule goes. Everything else of behaviour 2 is out (below). |
| C5 | The sentence of `docs/sdlc/constitution.md:10` is canonical, copied verbatim. |
| Q1 (g4-guard) | Of `start --mode … --by` the guard denies only `--mode light` (the one value that never raises); other lowerings stay with state.py's `human_route`. |
| Q2 (suite 1) | The `--mode light` deny applies only with the dialog off; with it on, the command reaches state.py, which opens the lowering decision (review H1, T-2026-10-28-010). `verify|review|reject --by` are denied in both modes: **spec R36.2 ("Off changes nothing") is amended for these verbs**; `tests/test_dialog_consent.py` follows. |

## Files that change

| Path | Step |
|---|---|
| `skills/project-update/update.py`, `tests/test_project_update.py`, `skills/rr-setup/SKILL.md` | g1-cleanup |
| `skills/project-init/templates/sdlc-README.md`, `skills/project-update/history/**` | g1-readme |
| `.github/workflows/{npm-publish,pylint,tests}.yml`, `tests/test_release.py` | g2-release |
| `tests/test_ere_unit.py`, `tests/test_guard_differential.py` | g2-timed |
| `ai/policies/{model-routing,review-economy,production,release}.md`, `skills/project-update/history/**` | g3-policies |
| `.ai/rules/skills.md`, `skills/{CLAUDE,AGENTS}.md`, `instructions/{routing,stub}.md`, `skills/project-init/templates/constitution.md`, `tools/build-template-history.py`, `tests/fixtures/adopt/README.md`, `tests/fixtures/instructions/rules-project/README.md`, `skills/project-update/history/**` | g3-rules |
| `README.md`, `CONTRIBUTING.md`, `docs/{faq,hooks,known-risks,local-memory,weight,project-update,installation}.md`, `bin/riskrails.js` | g3-docs |
| `hooks/context-guard.py`, `hooks/runtime-gate.py`, `tests/test_context_guard.py`, `tests/test_runtime_gate*.py` | g3-hooks |
| `skills/ai-task/state.py`, `tests/test_ai_task_state.py` | g4-state |
| `skills/ai-task/sensors.py`, `tests/test_ai_task_sensors.py` | g4-sensors |
| `hooks/guard/paths.py`, `tests/test_ai_path_guard.py`, `tests/test_guard_characterization.py`, `tests/fixtures/guard-characterization/**` | g4-guard |

## Order of work

### g1-cleanup — M1, M2+L2, M3, L4, L3 (one implementer, in this order)
`update.py` `task_journal`/`cleanup_update`/`deletion_hint`/`apply_item`/argparse. M1: a task is
finished when `logs/<id>/state.json` records a result or its journal has `gate_approved`; a torn
`task_closed` line no longer reads as unclosed when state.json says closed. M2: abandoned task's
`state.json` kept; comment at the `.ai/state/` skip and the row text say not recoverable by git;
L2: the commit-`.ai/`-first hint counts only non-`[cleanup]` deletions. M3: `--confirm-cleanup
NAME` (human/tty checks as `--confirm-delete`); rr-setup SKILL.md §update names both. L4:
malformed `RISKRAILS_NOW` exits 2 with a message. L3: the six missing assertions. Bugfixes
(M1, L4) get a test that fails before the fix. Tests: `tests/test_project_update.py`.

### g1-readme — L1 (after g1-cleanup)
`sdlc-README.md:24-27` names `$AI_HOME/skills/project-init/templates/{intent,spec,plan,adr}.md`
and how to copy one as an override; run `tools/build-template-history.py`. Tests:
`tests/test_project_update.py`.

### g2-release — smoke node, dead skipTest, prerelease tag, rerun, token comment, pylint pin
`tests.yml` tool loop checks node; `TestInstallHarnessNode` asserts `shutil.which("node")`;
`test_release_notes_carry_the_update_command` loses its skip; publish: rerun skip, `--tag next`;
pylint pinned in both workflows; text asserts in `TestReleaseWorkflow`/`TestSmokeWorkflow`.
Tests: `tests/test_release.py`.

### g2-timed — wall-clock budgets, find_print test
Scale `test_ere_unit.py:104,119` and `test_guard_differential.py:197` by `AI_TIMED_FACTOR`
(pattern of `test_guard_characterization.py:576`); a `find_print` byte-order unit test (b, a, c,
a dot name). Tests: `tests/test_ere_unit.py`, `tests/test_guard_differential.py`.

### g3-policies — tiers T0–T6 in shared policies (after g1-readme: history)
Mode/tier names replace T-labels where they name today's routing; T-numbers that are history or
measurement narrative stay. Run `tools/build-template-history.py`. Tests:
`tests/test_shared_prompts_model_free.py`, `tests/test_instruction_budget.py`, `tests/test_project_update.py`.

### g3-rules — removed shell-suite names, C5 wording (after g3-policies: history)
`.ai/rules/skills.md:7` and its renders; fixture READMEs; C5 verbatim in the template,
`instructions/routing.md:49`, `instructions/stub.md:27,50`; history rebuilt. Never this
repository's `CLAUDE.md` managed block. Tests: `tests/test_instruction_budget.py`,
`tests/test_project_update.py`, `tests/test_project_adopt.py`, `tests/test_scaffold_idempotency.py`.

### g3-docs — old command names in docs and installer help
`/ai-task`, `/ai-init`, `/ai-status`, `/ai-audit` → `/rr-*` where they name the current surface;
`/project-update` → `/rr-setup --update`; the deprecated-aliases paragraph (`README.md:145-146`)
and `docs/installation.md:187-193` stay. `bin/riskrails.js:1209-1210,1415`. Tests:
`tests/test_install_dry_run.py`, `tests/test_skills_surface.py`, `tests/test_no_size_tokens.py`, `tests/test_rename.py`.

### g3-hooks — old names in hook messages
`context-guard.py:555` resume message → `/rr-build`; `runtime-gate.py` docstring and messages
naming `fable-gate`/`codex-model-gate` (not the `LEGACY` code). Tests: `tests/test_context_guard.py`,
`tests/test_runtime_gate.py`, `tests/test_runtime_gate_codex.py`, `tests/test_runtime_gate_fable.py`.

### g4-state — E2, E3, E4, E5, E7, E10
`documents_cover` sees a red full-suite run with no tree; `cmd_verify --expect fail` does not
count runner exit 2 as a bite; `cmd_start`/`weigh` does not weigh a non-document glob beside
documents as light; `cmd_event` stamps `agent` when no hook marker is set; `archive_v7` writes
atomically; `status_lines` re-reads the questions file. Each a regression test that fails
before its fix. Tests: `tests/test_ai_task_state.py`, `tests/test_weight.py`.

### g4-sensors — E14
`numstat`/`diff_files` report paths relative to the `.ai/` root when it sits below the git top
level. A fixture with `.ai/` in a subdirectory. Tests: `tests/test_ai_task_sensors.py`.

### g4-guard — E8/E11/E13 (after g2-timed: test_guard_differential)
`HUMAN_BY_RE` with the dialog on and off, plus `start --mode … --by`; `SETBY_RE`/`WHY_SET_BY`
removed; moved decisions named in `moved-3.4.json`, golden re-recorded. No `SH_WORD`/`SH_RE`
change. Tests: `tests/test_ai_path_guard.py`, `tests/test_guard_characterization.py`,
`tests/test_guard_differential.py`.

### Batch end
`verify --scope all` once (runs e2e), failures fixed as one batch; one STRONG review (full);
README test count from verify's `Ran N`; close; the human approves.

### Human rows (after close)
- H1 `.ai/policies/testing.md:98,151-155` — the lint gate as `.pylintrc` has it (fail-on=E,F, fail-under=9.9), and `:99,133` for the timed-factor note.

## Out of this plan (stay in the register, own tasks)

E1 drift ack with the dialog off; E6 read-only one-liner beside `$(...)`; E12 gate's
questions-file route; E16 scratchpad outside an open step; profile budget keys T0–T5 and
`DIRECT_MODE_CAP`; retiring `risk-tiers.*` with a migration; shipped template texts naming
removed commands (`ai-init/templates/.ai/policies/testing.md`, `state/README.md`); verify
`--files` whitespace splitting; lint fail-on W0702/W1510 (the human's).
Closed as obsolete on HEAD: E9 (`state.py:381` says `start`), E15 (`cmd_set` gone; residual is E11),
G3 "Project docs still name the state.py commands redesign 2.6 removed".

## Risks

- `skills/project-update/history/**` is written by three steps; `start` orders them.
- Re-rendered instruction files change hashes the update tests pin; g3-rules runs those tests.
- The guard change moves decisions on purpose; each one is named in `moved-3.4.json`.

## Rollback

One branch, `fix/register-groups-1-4`; no migration, no schema change. Revert the branch.
