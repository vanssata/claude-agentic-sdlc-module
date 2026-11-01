# Plan: riskrails regenerates its own files — no adopt, no migrations, no legacy fallbacks

Intent: `docs/sdlc/intent/riskrails-regenerate-not-migrate.md` · Spec: `docs/sdlc/specs/riskrails-regenerate-not-migrate.md`
Written 2026-11-01. **Not started**: `state.py start` runs after the human accepts this plan and has done s0.
Runs as **one task through `/rr-build-all`** (OQ12): every row of *Order of work* is one step.

## Weight, measured (2026-11-01, `state.py weight`, not journaled)

```
scope 2 (update.py referenced from 217 files) · behaviour 2 (declared: install/update of user projects,
deletes user files behind the gate, removes fallbacks the guards read — weight.json:205, hooks/CLAUDE.md:3, C6)
· reversibility 2 (needs_step **/migrations/**) · domain 1 (guard configuration) · novelty 1 · coverage 1
→ W 9 → full
```

Full: written plan accepted by the human, one STRONG review at the end, the approval gate (C5).

## Decisions on the spec's open questions (Ivan Kakurov, 2026-11-01, in the dialog)

| # | Answer | What it changes against the spec |
|---|---|---|
| OQ1 | **delete per Q1** (not A3) | `.ai/rules/<slug>.md` leave KEPT; each is `delete?` behind the gate, original to `original/`. R16 rewritten below. |
| OQ2 | **both behind the gate** (design default) | coding.md and path-guard.json GENERATED; the path-guard row prints the dropped pattern count (D5, F5). |
| OQ3 | **delete `setup.py adopt`** | `cmd_adopt`, the toolbox.md writer, its CLI verb, its test cases and its SKILL.md text go (s1). |
| OQ4 | **remove the fallbacks bare** — no R24 | R24 dropped: weight.py, sensors and the guards just stop reading old shapes. Spec Risks 2–4 are accepted, not mitigated. update's own D4 check (R12, Q4) stays. |
| OQ5 | `[cleanup]` rows stay (A6) | — |
| OQ6 | closed: `npm view riskrails versions` lists 3.1.0 (2026-11-01) | F13 closed; I3 names an installable version. |
| OQ7 | `docs/sdlc/README.md` frozen (A7) | — |
| OQ8 | edited shared overrides KEPT + hint (A5) | — |
| OQ9 | **group F in this task** | new step s4. |
| OQ10 | `CONFIRM_REFUSED` | R29 as written. |
| OQ11 | `.ai/local/memory/` KEPT (A4); release **4.0.0** (A8) | s5 bumps the version. |
| OQ12 | **one task, steps** via `/rr-build-all` | — |
| F1–F12 | accepted as designed | — |

## Found while planning (KNOWN FACT, grep 2026-11-01) — corrections to the spec

1. **This repository's own verify breaks at s1** without a pre-step: R10 makes `verification.md` the only source of
   `verify_command`, OQ4 removes the fallback, and `.ai/policies/` is task-protected while a task is in flight
   (`hooks/ai-path-guard-defaults.json`, `(^|/)\.ai/policies/`). → **s0, by the human, before `start`.**
2. **R25 moves from D9 step 3 to s2**: `skills/rr-status/status.py:78` and `skills/ai-task/rr_state/report.py:157`
   `os.listdir(.../project-update/migrations)`; deleting the dir in s2 would break both.
3. **R21's tokens collide with paths that stay**: `/ai-task`, `/ai-init`, `/project-update`, `/ai-audit`,
   `/usage-report` occur inside `skills/ai-task/…`, `skills/ai-init/templates/…`, `skills/project-update/update.py`
   (kept, Q3/C3); `migrations/` occurs in user-project fixtures (`tests/test_ai_task_state.py:674` `db/migrations/`,
   `tests/test_guard_characterization.py:134`, `tests/test_ai_path_guard.py:54`). The test matches command tokens not
   preceded by a path character (`(?<![\w./-])/ai-task\b`) and `project-update/migrations`, not bare `migrations/`.
4. **`current.json` stays in the guards' protected patterns** (path-guard fixtures 34, 53, 101, 102 …; 131 mentions in
   `tests/test_ai_path_guard.py`): denies on writing a state file — KEEP rows in R21's allow-list; only the *read*
   fallbacks (D8 D) go.
5. **`.ai/VERSION` template 11 → 12** in s2: the split changes the tree shape, and spec Risk 11 ("3.1.0 refuses a
   regenerated tree") holds only if VERSION is newer than 3.1.0's.
6. **Fixture inputs of `tests/test_state_characterization.py`** write `testing.md` fields (3 sites): s1 moves the input
   to `verification.md`; the golden *output* stays byte-identical (WP1 R5).
7. **Installer fable-gate sites outside D8 F** — `bin/riskrails.js:580-599` (statusline wrapper), `:1106-1135`
   (fable-gate hook entries replaced, shim retired), `:1176`: **default OUT** of s4. Removing them leaves a pre-WP5
   `settings.json` with a hook command pointing at a retired shim — an error on every tool call, not a silent no-op.
   Named in CHANGELOG as kept.
8. **OQ1's consequence**: with every `<slug>.md` `delete?` on every update, the rules feature has no durable home —
   each run proposes deleting each project rule. The plan does what was decided (gate; rendering code unchanged, so a
   declined deletion keeps the rule rendered).

## Files that change

| Step | Files (new / edit / delete) |
|---|---|
| s0 (human) | new `.ai/policies/verification.md` (the field lines of `.ai/policies/testing.md:92-103` verbatim + `## Project specifics`); new `.ai/policies/weight.project.json` (this repo's leaves differing from the shipped table: `tests`, `batch`, `documents`, `examples` — weight.json:186-223); edit `.ai/policies/testing.md` step-test row for `skills/project-update/**` (:154: − test_project_adopt.py, + test_regenerate.py, test_no_fallbacks.py) |
| s1 | edit `skills/ai-task/weight.py`, `skills/ai-task/sensors.py`, `skills/rr-setup/setup.py` (verification.md; `MAP_FILE` → `FOREIGN_ROOTS`; `cmd_adopt` + toolbox writer deleted), `skills/rr-setup/scaffold_ai.py`, `skills/ai-init/templates/.ai/policies/testing.md`, `skills/ai-init/templates/.ai/AGENTS.md`; new `skills/ai-init/templates/.ai/policies/verification.md`, `skills/ai-init/templates/.ai/policies/weight.project.json`; tests `tests/test_weight.py`, `tests/test_ai_task_sensors.py`, `tests/test_setup.py`, `tests/test_ai_task_state.py`, `tests/test_state_characterization.py` (inputs only), `tests/memory_harness.py`, `tests/test_end_to_end.py`, `tests/test_scaffold_idempotency.py` |
| s2 | edit `skills/project-update/update.py` (D2–D7, `split_once`, `check_kept`, CLI, `SHARED_SET`, `LAST_MIGRATING_VERSION`; human_gate/placeholder_name/refuse/budget_offenders moved in), `skills/rr-status/status.py:70-84`, `skills/ai-task/rr_state/report.py:157`, `skills/ai-init/templates/.ai/VERSION` (12); delete `skills/project-update/{adopt.py,adopt-map.json,migrations/}`; new `tests/test_regenerate.py`, `tests/fixtures/regenerate/{fresh,v3.1.0,v3.1.0-edited,dual}/`; edit `tests/test_project_update.py`, `tests/test_shared_tree.py`, `tests/test_rename.py` (adopt cases), `tests/test_ai_status_root.py`, `tests/test_no_size_tokens.py:24`, `tests/test_install_dry_run.py:410`; delete `tests/test_project_adopt.py`, `tests/fixtures/adopt/`, `tests/test_migration_00{06,10,11}.py`, `tests/fixtures/project-update/{migrations-*,schema-v*,risk-tiers,shared-old}` |
| s3 | edit (D8 C, D) `skills/project-update/update.py`, `skills/project-update/render_instructions.py`, `skills/rr-setup/scaffold_ai.py`, `scripts/ai-path`, `scripts/resolve-profile.py`, `skills/ai-task/rr_state/{profile,dialog,fs}.py`, `skills/ai-task/memory_store.py:17`, `skills/ai-task/sensors.py:353`, `skills/rr-status/status.py:8,39-41`, `hooks/guard/scope.py:6,336-338`, `hooks/guard/paths.py:674-677`, `hooks/context-guard.py:394`, `hooks/runtime-gate.py:130-132,917`, `skills/usage-report/usage-report.py:584-586`, `bin/riskrails.js` (:304, :351, :711-721, :810-813, :835-846 + calls), `agents/ai-reviewer.md.tmpl:57`, `skills/ai-init/templates/.ai/state/README.md:48`; new `tests/test_no_fallbacks.py`; edit `tests/test_rename.py` (R22), the 15 suites setting `CLAUDE_AGENTIC_*` env (R23), `tests/test_ai_scope_guard.py`, `tests/test_ai_path_guard.py`, `tests/test_guard_differential.py`, `tests/test_context_guard.py`, `tests/test_guard_characterization.py` + its golden (re-recorded once) |
| s4 | edit (D8 F) `hooks/guard/paths.py:722-725` (`dependency_instruction_patterns`), `hooks/ai-path-guard-defaults.json:2` (its `_comment` sentence), `skills/ai-init/templates/.ai/policies/security.md:56`, `hooks/runtime-gate.py` (`LEGACY` :79, :98-99, :169-172, :219-223, :1112, `--as` :1187-1188), `.pylintrc:29`, `bin/riskrails.js:825-834` and dry-run line :687; delete `tests/test_merge_migration.py`; edit `tests/test_runtime_gate.py` (:194, :223-239), `tests/test_runtime_gate_codex.py`, `tests/test_install_dry_run.py`, `tests/test_ai_path_guard.py` |
| s5 | delete `skills/{ai-status,sdlc-intent,sdlc-plan,sdlc-spec}/`, `SKILL.md` of `skills/{ai-task,project-update,ai-init,project-init,usage-report,ai-audit}/`, `ai/workflows/*.md`, `ai/agents/manager.md`; edit `ai/using-riskrails.md:21`, `bin/riskrails.js` (`RETIRED_SKILLS`, :763, :679, :1321), `skills/rr-setup/SKILL.md`, `skills/rr-*/SKILL.md` alias mentions, `skills/ai-init/templates/**` naming alias commands, `instructions/routing.md`, `README.md` (+ test count), `docs/{project-update,installation,getting-started,faq,architecture,hooks,known-risks}.md`, `CHANGELOG.md` (4.0.0, breaking), `package.json` + plugin manifests via `tools/sync-version.py`, `skills/project-update/history/**` via `tools/build-template-history.py`; tests `tests/test_skills_surface.py`, `tests/test_install_dry_run.py`, `tests/test_install_routes.py`, `tests/test_instruction_budget.py`, `tests/test_shared_prompts_model_free.py`, `tests/test_no_fallbacks.py` (allow-list shrinks) |

## Order of work

Linear: each step shares a file with the next (update.py s2→s3, guards s3→s4, `bin/riskrails.js` s3→s4→s5), so
`/rr-build-all` runs them one at a time; one review after s5 (OQ12).

| Step | Requirements | Tests (step scope) | Consumes |
|---|---|---|---|
| s0 | — (human, outside the agent, committed before `start`) | `python3 -I tests/run_suite.py test_weight` green | — |
| s1 | R9, R10, OQ3 | test_weight, test_ai_task_sensors, test_setup, test_ai_task_state, test_state_characterization, test_scaffold_idempotency | s0 |
| **s2 (riskiest)** | R1–R8, R11–R18, R25, R28, R29 | test_project_update, test_regenerate, test_shared_tree, test_rename, test_ai_status_root, test_no_size_tokens, test_ai_path_guard, test_guard_characterization | s1 |
| s3 | R21 (C, D), R22, R23 | test_no_fallbacks, test_rename, test_ai_scope_guard, test_ai_path_guard, test_guard_characterization, test_guard_differential, test_context_guard, test_runtime_gate | s2 |
| s4 | R21 (F), OQ9 | test_runtime_gate, test_runtime_gate_codex, test_runtime_gate_fable, test_install_dry_run, test_codex_install, test_ai_path_guard, test_guard_characterization | s3 |
| s5 | R19, R20, R26, R27, R30 | test_skills_surface, test_install_dry_run, test_install_routes, test_instruction_budget, test_shared_prompts_model_free, test_history_covers_every_template, test_no_fallbacks | s4 |

s2 is the riskiest (update.py ~2 147 → ~1 300 lines, every migration path deleted, the one-time split added). It
cannot move earlier (it reads s1's file formats) and is not split further: R3/R4/R7/R12 are one flow, and its tests are
the only proof the regenerate keeps kept bytes. Its implementer writes `tests/test_regenerate.py` first (red on the tree
before s2, where `--update` still migrates) and gets `TestKept` green before anything else.

R16 (rewritten by OQ1): `.ai/rules/README.md` regenerated; each `.ai/rules/<slug>.md` is `delete?` with its original
kept; rendering of rule blocks and `.claude/rules/*.md` unchanged (`rules_update` without `planned`) — it renders what
is left. Proof: rules cases of test_project_update.py + `TestGate.test_rule_source_gated`.

## Risks

1. **Data loss in GENERATED files** (spec Risk 1, wider after OQ1/OQ2: rule sources, coding.md project half,
   path-guard patterns, router rows from past adopt runs). Noticed by `TestDryRun` (the row names lost lines) and
   `TestGate` (original/ copy byte-equal). Every loss is gated and copied.
2. **Old shapes misbehave silently** (accepted with OQ4): a project that installs 4.0.0 and does not run
   `/rr-setup --update` weighs without its `domain.modules` (lighter), finds no `verify_command`, and a task sitting in
   `current.json` is not scope-guarded. CHANGELOG and rr-setup say "run `/rr-setup --update` right after install".
3. **This repo during the task** (finding 1): s0 must land before `start`, else s1's step tests and the final verify
   find no command.
4. **Guard golden re-record** (s3, s4): current.json-only cases become inert. The golden diff is reviewed case by case;
   a changed case outside current.json / dependency_instruction_patterns is a BLOCKER, closed only by a pinning test
   (root CLAUDE.md).
5. **Token test false positives / negatives** (finding 3): anchored regex, stale-entry check (test_rename.py:86-88
   style), every allow-list row with its reason.
6. **Large test deletion hides lost coverage**: each deleted suite maps to a removed behaviour (R2's list); the
   `--confirm-delete` guard fixtures stay (R8).
7. **Dual-runtime skew** (spec Risk 7): the plugin route and `npx riskrails` both reinstalled — CHANGELOG.
8. **Installer retire** (R20) moves user-visible skill dirs into backups; the dry run lists them first.
9. **Callers of update.py** (217 referencing files, mostly docs and tests): removed flags exit 2; rr-setup/SKILL.md's
   `--adopt` text is stale between s2 and s5 — inside the task only.

## Proof (tests)

| R | Proof |
|---|---|
| R1 | `tests/test_project_update.py::TestCli.test_removed_flags` |
| R2 | `tests/test_no_fallbacks.py::test_removed_paths_absent` |
| R3, R4, R14, R18 | `tests/test_regenerate.py::TestGenerated`, `TestKept` (four fixture trees) |
| R5 | `TestIdempotent` |
| R6 | `TestDryRun` |
| R7, R16, R29 | `TestGate` (incl. `test_rule_source_gated`, `test_refused_token`) |
| R8 | `test_ai_path_guard` fixtures 45–50, codex-hooks 41 byte-identical |
| R9 | `tests/test_weight.py::TestOverlay` |
| R10 | `test_ai_task_sensors::TestVerificationFile`, `test_setup::TestVerifySet` |
| R11 | `TestSplitOnce` |
| R12, R13 | `TestRefusal` (a subTest per reader and old shape; `test_names_version`) |
| R15 | `TestBlock` |
| R17 | `test_shared_tree` set-equality, `TestShared` |
| R19 | `test_skills_surface` expected set |
| R20 | `test_install_dry_run`, `test_install_routes` |
| R21, R23 | `test_no_fallbacks::test_no_legacy_tokens` (anchored tokens, allow-list with reasons, stale-entry check) |
| R22 | `test_rename.py` |
| R24 | **dropped** (OQ4) |
| R25 | `test_ai_status_root` (in s2) |
| R26 | R21 + `test_skills_surface`, `test_instruction_budget`, `test_shared_prompts_model_free` |
| R27 | `test_history_covers_every_template` |
| R28 | existing `--check --budget` cases |
| R30 | `state.py verify --scope all` once (it runs e2e itself), green; README count updated |
| OQ3 | `test_setup`: the `adopt` verb exits 2 |
| OQ9 | `test_no_fallbacks` tokens `fable-gate`, `codex-model-gate`, `dependency_instruction_patterns`, `claude-routing`, `Model allocation` over hooks/ and bin/ (allow-list: finding 7's sites) |

## Rollback

`git revert` of the task's commit restores update.py, adopt, the migrations and the fallbacks. A project already
updated by 4.0.0 goes back to `npx riskrails@3.1.0` only after restoring `.ai/` from git or `original/` (3.1.0 refuses
VERSION 12).

## Start — after acceptance and s0

```bash
$STATE start --goal "riskrails regenerates its own files: no --adopt, no migrations, no legacy fallbacks; weight.project.json and verification.md split once" \
  --workflow feature \
  --files "<every file of s1–s5 above>" --tests "<every step's tests>" \
  --declare 'behaviour=2:"changes install and update of user projects, deletes user files behind the gate, removes fallbacks the guards read (weight.json:205, hooks/CLAUDE.md:3, C6)"' \
  --declare 'novelty=1:"regenerate with a history-hash gate reuses update.py apply/gate/history; overlay and split are new"' \
  --declare 'domain=1:"guard configuration: path-guard patterns and the scope state file"' \
  --plan-file <scratchpad>/steps.json --batch --by "Ivan Kakurov" \
  --why "/rr-build-all docs/sdlc/plans/riskrails-regenerate-not-migrate.md"
```

A feature, not a refactoring: behaviour is removed and two files are introduced (C3 — no rename, no update.py split).
