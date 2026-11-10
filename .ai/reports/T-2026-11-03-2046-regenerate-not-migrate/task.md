# T-2026-11-03-2046-regenerate-not-migrate — riskrails regenerates its own files: no --adopt, no migrations, no legacy fallbacks; weight.project.json and verification.md split once

feature · full · started 2026-11-03T20:46:07Z · claude

## Weight

```
scope          2  skills/ai-task/weight.py referenced from 161 files
behaviour      2  keyword 'state machine' in README.md; hint +1
reversibility  0  git revert returns everything
domain         1  "guard configuration: path-guard patterns and the scope state file" (declared)
novelty        2  package.json is a dependency manifest; hint +1
coverage       1  14 of 20 code files have a test
W 8 → full   hints behaviour +1, novelty +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
re-score 2026-11-03T22:26:07Z at verify: reversibility 0 → 1 — skills/project-update/migrations/0001_schema_version.py matches needs_step **/migrations/**
re-score 2026-11-03T22:26:07Z at verify: domain 1 → 2 — tests/fixtures/adopt/large-agents-md/src/Payment/PaymentGateway.php matches modules **/Payment/**
batch: on by Ivan Kakurov at 2026-11-03T20:46:07Z — /rr-build-all docs/sdlc/plans/riskrails-regenerate-not-migrate.md

## Plan

files: skills/ai-task/weight.py, skills/ai-task/sensors.py, skills/rr-setup/setup.py, skills/rr-setup/scaffold_ai.py, skills/ai-init/templates/.ai/policies/testing.md, skills/ai-init/templates/.ai/AGENTS.md, skills/ai-init/templates/.ai/policies/verification.md, skills/ai-init/templates/.ai/policies/weight.project.json, tests/memory_harness.py, tests/test_end_to_end.py, tests/fixtures/state/**, tests/fixtures/setup/**, tests/test_weight.py, tests/test_ai_task_sensors.py, tests/test_setup.py, tests/test_ai_task_state.py, tests/test_state_characterization.py, tests/test_scaffold_idempotency.py, skills/project-update/update.py, skills/rr-status/status.py, skills/ai-task/rr_state/report.py, skills/ai-init/templates/.ai/VERSION, skills/project-update/adopt.py, skills/project-update/adopt-map.json, skills/project-update/migrations/**, tests/fixtures/regenerate/**, tests/fixtures/adopt/**, tests/fixtures/project-update/**, tests/test_migration_0006.py, tests/test_migration_0010.py, tests/test_migration_0011.py, tests/test_project_adopt.py, tests/test_install_dry_run.py, tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_rename.py, tests/test_ai_status_root.py, tests/test_no_size_tokens.py, skills/project-update/render_instructions.py, scripts/ai-path, scripts/resolve-profile.py, skills/ai-task/rr_state/profile.py, skills/ai-task/rr_state/dialog.py, skills/ai-task/rr_state/fs.py, skills/ai-task/memory_store.py, hooks/guard/scope.py, hooks/guard/paths.py, hooks/context-guard.py, hooks/runtime-gate.py, skills/usage-report/usage-report.py, bin/riskrails.js, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/.ai/state/README.md, tests/fixtures/guard-characterization/**, tests/fixtures/scope-guard/**, tests/fixtures/path-guard/**, tests/test_no_fallbacks.py, tests/test_ai_scope_guard.py, tests/test_ai_path_guard.py, tests/test_guard_differential.py, tests/test_context_guard.py, tests/test_guard_characterization.py, tests/test_merge_migration.py, tests/test_instruction_budget.py, tests/test_runtime_gate_codex.py, tests/test_scaffold_differential.py, tests/test_runtime_gate_fable.py, tests/test_codex_agent_render.py, tests/test_shared_prompts_model_free.py, hooks/ai-path-guard-defaults.json, skills/ai-init/templates/.ai/policies/security.md, .pylintrc, tests/fixtures/codex-hooks/**, tests/test_runtime_gate.py, skills/ai-status/**, skills/sdlc-intent/**, skills/sdlc-plan/**, skills/sdlc-spec/**, skills/ai-task/SKILL.md, skills/project-update/SKILL.md, skills/ai-init/SKILL.md, skills/project-init/SKILL.md, skills/usage-report/SKILL.md, skills/ai-audit/SKILL.md, ai/workflows/**, ai/agents/manager.md, ai/using-riskrails.md, skills/rr-setup/SKILL.md, skills/rr-*/SKILL.md, skills/ai-init/templates/**, instructions/routing.md, README.md, docs/project-update.md, docs/installation.md, docs/getting-started.md, docs/faq.md, docs/architecture.md, docs/hooks.md, docs/known-risks.md, CHANGELOG.md, package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, skills/project-update/history/**, tests/test_skills_surface.py, tests/test_install_routes.py, skills/ai-task/rr_state/start.py, skills/ai-task/weight_overlay.py, skills/ai-init/templates/.ai/policies/weight.md, tests/fixtures/memory/goldens/**, tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_profiles.py, docs/weight.md, skills/ai-audit/templates/**, skills/project-init/templates/**, skills/ai-task/rr_state/cli.py, skills/ai-task/rr_state/questions_cmd.py, skills/ai-task/state.py, skills/ai-task/rr_state/runtime.py, tests/fixtures/state/goldens/help.txt
tests: tests/test_weight.py, tests/test_ai_task_sensors.py, tests/test_setup.py, tests/test_ai_task_state.py, tests/test_state_characterization.py, tests/test_scaffold_idempotency.py, tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_rename.py, tests/test_ai_status_root.py, tests/test_no_size_tokens.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_no_fallbacks.py, tests/test_ai_scope_guard.py, tests/test_guard_differential.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_codex_install.py, tests/test_skills_surface.py, tests/test_install_routes.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py
- s1 · skills/ai-task/weight.py, skills/ai-task/sensors.py, skills/rr-setup/setup.py, skills/rr-setup/scaffold_ai.py, skills/ai-init/templates/.ai/policies/testing.md, skills/ai-init/templates/.ai/AGENTS.md, skills/ai-init/templates/.ai/policies/verification.md, skills/ai-init/templates/.ai/policies/weight.project.json, tests/memory_harness.py, tests/test_end_to_end.py, tests/fixtures/state/**, tests/fixtures/setup/**, tests/test_weight.py, tests/test_ai_task_sensors.py, tests/test_setup.py, tests/test_ai_task_state.py, tests/test_state_characterization.py, tests/test_scaffold_idempotency.py · tests/test_weight.py, tests/test_ai_task_sensors.py, tests/test_setup.py, tests/test_ai_task_state.py, tests/test_state_characterization.py, tests/test_scaffold_idempotency.py · done
- s2 · skills/project-update/update.py, skills/rr-status/status.py, skills/ai-task/rr_state/report.py, skills/ai-init/templates/.ai/VERSION, skills/project-update/adopt.py, skills/project-update/adopt-map.json, skills/project-update/migrations/**, tests/fixtures/regenerate/**, tests/fixtures/adopt/**, tests/fixtures/project-update/**, tests/test_migration_0006.py, tests/test_migration_0010.py, tests/test_migration_0011.py, tests/test_project_adopt.py, tests/test_install_dry_run.py, tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_rename.py, tests/test_ai_status_root.py, tests/test_no_size_tokens.py · tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_rename.py, tests/test_ai_status_root.py, tests/test_no_size_tokens.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py · done · after s1
- s3 · skills/project-update/update.py, skills/project-update/render_instructions.py, skills/rr-setup/scaffold_ai.py, scripts/ai-path, scripts/resolve-profile.py, skills/ai-task/rr_state/profile.py, skills/ai-task/rr_state/dialog.py, skills/ai-task/rr_state/fs.py, skills/ai-task/memory_store.py, skills/ai-task/sensors.py, skills/rr-status/status.py, hooks/guard/scope.py, hooks/guard/paths.py, hooks/context-guard.py, hooks/runtime-gate.py, skills/usage-report/usage-report.py, bin/riskrails.js, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/.ai/state/README.md, tests/fixtures/guard-characterization/**, tests/fixtures/scope-guard/**, tests/fixtures/path-guard/**, tests/test_no_fallbacks.py, tests/test_rename.py, tests/test_ai_scope_guard.py, tests/test_ai_path_guard.py, tests/test_guard_differential.py, tests/test_context_guard.py, tests/test_guard_characterization.py, tests/test_merge_migration.py, tests/test_instruction_budget.py, tests/test_runtime_gate_codex.py, tests/test_scaffold_differential.py, tests/test_migration_0006.py, tests/test_runtime_gate_fable.py, tests/test_end_to_end.py, tests/test_codex_agent_render.py, tests/test_shared_prompts_model_free.py, tests/test_scaffold_idempotency.py, tests/test_rename.py, tests/test_shared_tree.py, tests/test_project_adopt.py, tests/test_project_update.py · tests/test_no_fallbacks.py, tests/test_rename.py, tests/test_ai_scope_guard.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_context_guard.py, tests/test_runtime_gate.py · done · after s2, s1
- s4 · hooks/guard/paths.py, hooks/ai-path-guard-defaults.json, skills/ai-init/templates/.ai/policies/security.md, hooks/runtime-gate.py, .pylintrc, bin/riskrails.js, tests/test_merge_migration.py, tests/fixtures/path-guard/**, tests/fixtures/guard-characterization/**, tests/fixtures/codex-hooks/**, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_install_dry_run.py, tests/test_ai_path_guard.py · tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_codex_install.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py · done · after s3, s2
- s5 · skills/ai-status/**, skills/sdlc-intent/**, skills/sdlc-plan/**, skills/sdlc-spec/**, skills/ai-task/SKILL.md, skills/project-update/SKILL.md, skills/ai-init/SKILL.md, skills/project-init/SKILL.md, skills/usage-report/SKILL.md, skills/ai-audit/SKILL.md, ai/workflows/**, ai/agents/manager.md, ai/using-riskrails.md, bin/riskrails.js, skills/rr-setup/SKILL.md, skills/rr-*/SKILL.md, skills/ai-init/templates/**, instructions/routing.md, README.md, docs/project-update.md, docs/installation.md, docs/getting-started.md, docs/faq.md, docs/architecture.md, docs/hooks.md, docs/known-risks.md, CHANGELOG.md, package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, skills/project-update/history/**, tests/test_skills_surface.py, tests/test_install_dry_run.py, tests/test_install_routes.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py, tests/test_no_fallbacks.py · tests/test_skills_surface.py, tests/test_install_dry_run.py, tests/test_install_routes.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py, tests/test_project_update.py, tests/test_no_fallbacks.py · done · after s4, s1, s2, s3
amended 2026-11-03T20:59:24Z: +skills/ai-task/rr_state/start.py — s1: R9 makes load_policy return (policy, [shipped, project]); cmd_weight's --json policy field and --mirror read the old single path (state_characterization golden, 12 weight-mirror cases)
amended 2026-11-03T21:05:11Z: +skills/ai-task/weight_overlay.py — Q1=B: the overlay loader goes into its own module so weight.py stays under test_line_limits' 300-line cap
amended 2026-11-03T21:07:04Z: +skills/ai-init/templates/.ai/policies/weight.md — s2: test_history_covers_every_template (in test_project_update, s2's suite) needs history entries for s1's new and changed templates; weight.md template is rendered from the effective table (spec :161)
amended 2026-11-03T21:36:27Z: +tests/fixtures/memory/goldens/** — s2: VERSION 11->12 moves 'schema: project 0 · plugin 11' in memory goldens (status-py, files-mode); files-mode lists policies/verification.md after s1
amended 2026-11-03T21:52:10Z: +tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_profiles.py — s3: suites that pin the removed current.json / claude-agentic profile / legacy block-rename fallbacks (R21 C/D) and its token allow-list rows
amended 2026-11-03T22:20:44Z: +docs/weight.md, skills/ai-audit/templates/**, skills/project-init/templates/**, skills/ai-task/rr_state/cli.py, skills/ai-task/rr_state/questions_cmd.py, skills/ai-task/state.py, skills/ai-task/rr_state/runtime.py, tests/fixtures/state/goldens/help.txt — s5 R26: alias-command and 'one version' text left in files outside the step (test_no_fallbacks PENDING OUTSIDE rows); the plan deletes ai/workflows and agents/manager.md, which update.py SHARED_SET and test_shared_tree pin

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. s1: weight.py is 323 lines after R9's overlay loader and the effective-table mirror; tests/test_weight.py test_line_limits caps it at 300. Raise the cap or split?
asked: 2026-11-03T21:02:22Z · stage: implementation
context: tests/test_weight.py test_line_limits; skills/ai-task/weight.py; implementer's QUESTIONS_NEEDED
A. raise the cap to 325 in test_line_limits (the loader and mirror add 23 lines; weight.py was exactly at 300)
B. new module skills/ai-task/weight_overlay.py holding the overlay loader (_table/_overlay); weight.py's load_policy calls it, no re-exports; cap stays 300 (recommended)
X. Other — answer as `X: <text>`
[Answer]: B — by Ivan Kakurov via dialog at 2026-11-03T21:05:08Z

## G1. Approve T-2026-11-03-2046-regenerate-not-migrate for implementation? (gate: human_approval)
asked: 2026-11-10T20:22:28Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-11-10T20:25:17Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 6ca97d662 | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/suite-1.log | no |
| 2 | e2e | 1 | 6ca97d662 | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/e2e-2.log | no |
| 3 | suite | 0 | 7a413ecac | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/suite-3.log | no |
| 4 | e2e | 0 | 7a413ecac | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/e2e-4.log | no |
| 5 | suite | 0 | 967aa97a9 | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/suite-5.log | no |
| 6 | e2e | 0 | 967aa97a9 | .ai/state/logs/T-2026-11-03-2046-regenerate-not-migrate/e2e-6.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass_with_findings (focus security)

```
## FINDINGS

- [HIGH] H1 (data integrity / domain weighting) Running `/rr-setup` on an existing tree creates empty `verification.md` and `weight.project.json`, so the one-time split never runs. (`skills/rr-setup/scaffold_ai.py:226-240`, `skills/project-update/update.py:809,818`) in_scope: yes
  - **Cause:** the scaffold copies every `.ai/` template that is missing and skips only `weight.json`. Both new files are now templates under `skills/ai-init/templates/.ai/policies/`. `split_once` runs only "when the new file is absent".
  - **How it is reached:** `rr-setup/SKILL.md` Setup step 1 always runs `scaffold-ai.sh`. When `overview.md` already exists it then says "run --update".
  - **Scenario:** a 3.1.0 project whose `weight.json` holds `domain.modules: ["**/Payment/**"]` and whose `testing.md` holds `verify_command` runs `/rr-setup`. The scaffold writes the pristine template files. The dry run of `--update` then shows no `split` row and shows `delete? .ai/policies/weight.json "[split] superseded by weight.project.json"`, which is false because nothing was carried. From that point:
    - Weight is computed from the shipped table, so payment changes weigh lighter and get less review.
    - `verify_command` is empty, and only a hint says so.
    - After the human confirms, the project's overrides survive only under `original/`.
  - `check_kept` does not notice that `weight.project.json` is the pristine template while `weight.json` still holds project leaves. No test runs the scaffold and then the update on an old tree.
  - **Suggested direction:** the scaffold should skip the split targets when `.ai/` already existed (`had_ai`), or the split should also run when the new file is byte-equal to its shipped template. Pin either with a scaffold-then-update test on the v3.1.0 fixture.

- [MEDIUM] M1 A second confirmed regenerate on the same day loses the newer human edit. (`skills/project-update/update.py:1555-1558`) in_scope: yes
  - **Cause:** `keep_original` is skipped when `original/<path>` already exists, and `report_dir` is per date.
  - **Scenario:**
    1. Day D: a confirmed run regenerates `coding.md` and saves A to `original/`.
    2. The same day, the human adds project text B to `coding.md` (now `regenerate?` again).
    3. They confirm again. B is overwritten with no copy.
  - At HEAD this guard only covered migration rewrites outside `.ai/`, and edited files were three-way merged, not replaced. Now it covers `coding.md`, `path-guard.json`, `AGENTS.md` and the managed blocks, which breaks plan Risk 1's "every loss is gated and copied". The delete path always copies, so it is not affected.
  - **Suggested direction:** never skip the copy when the bytes differ from the saved original (for example a suffixed copy), and pin it with a TestGate case.

- [MEDIUM] M2 `/rr-status` budgets still read the project's old `weight.json` and ignore `weight.project.json`. (`skills/rr-status/status.py:99-102`, docstring `:8`) in_scope: yes
  - **Cause:** R9 moved the source of truth to the overlay. `state.py` (`policy.py:36`, through `weight.load_policy`) now enforces shipped table plus overlay, but `status.py` still reads `.ai/policies/weight.json`, else the shipped table.
  - **Scenario:** after the split the old `weight.json` stays until a human confirms its `delete?`. Until then `/rr-status` shows that file's `batch` and `max_suite_runs`. After the confirm it shows the shipped values. `state.py` enforces `weight.project.json`'s values in both cases.
  - This repository is in exactly that state now: `.ai/policies/weight.json` and `weight.project.json` both exist.
  - **Suggested direction:** read the shipped table with `weight.project.json` laid over it (the same merge as `weight_overlay.load`), keeping `status.py`'s no-import robustness.

- [MEDIUM] M3 The rr-setup `--update` text still describes behaviour that was removed. (`skills/rr-setup/SKILL.md:136,149-151,164-168`; `docs/project-update.md:9`) in_scope: yes
  - Step 3 talks about "Lines marked `policy`", step 4 about `[sdlc]` TEMPLATE.md housekeeping (decision 2 removed it), and step 5 about `conflict` lines with "delete the copy" (the conflict cache is gone).
  - R26 requires `--update` steps 2-6 to be rewritten. As written, an agent is told to look for, and hand-merge, rows that can no longer appear, while the new `regenerate?` row is explained only in passing.
  - **Suggested direction:** rewrite steps 3-5 around `split` / `regenerate` / `regenerate?` / `delete?` and drop `[sdlc]` and `conflict`.

- [MEDIUM] M4 (test integrity) `TestKept.test_kept_byte_identical` stops asserting under `--confirm-delete`. (`tests/test_regenerate.py:251`) in_scope: yes
  - The condition `elif rel in now or confirm is False:` means that on the confirmed pass a KEPT file that vanished is not checked at all.
  - R4 says every KEPT path is sha-identical "after any `--update` run". No KEPT file should disappear under `--confirm-delete` (cleanup has its own flag), so this escape only weakens the pin: a future bug that deletes a kept file under confirm would pass.
  - **Suggested direction:** assert presence and equality on both passes.

- [LOW] L1 (authorization) Deny messages point the agent to a deleted file and a retired command. (`hooks/guard/paths.py:38,45-47,53`)
  - `WHY_CONFIRM_DELETE` says "See skills/project-update/SKILL.md", which R19 deleted. `WHY_PROTECTED` says "during a schema migration by update.py", and `WHY_TASK` says "through /project-update".
  - They are held by the guard golden (R8, byte-identical) and the allow-list row `hooks/guard/paths.py` `/project-update`.
  - **Suggested direction:** a separate behaviour-1 change (deny text, golden re-recorded) that points to `/rr-setup --update`. Record it in the risk register now.

- [LOW] L2 The `test_no_fallbacks` allow-list row for `hooks/ai-path-guard-defaults.json` gives a false reason and hides stale text. (`tests/test_no_fallbacks.py:109`, `hooks/ai-path-guard-defaults.json:2`)
  - The row says "writing current.json stays refused (deny pattern)". The only `current.json` in that file is the `_comment` sentence "(.ai/state/state.json, or else current.json, exists…)", which describes the read fallback s3 removed. The write deny is `(^|/)\.ai/state/`, which has no `current.json` literal.
  - s4 edited this exact `_comment` and left the clause in.
  - The other KEEP rows are justified: frozen shell or port sides, old-tree fixtures, D4 literals, the gitignore header, R8 fixtures, `coding.md` held for its history hash, and installer finding 7.

- [LOW] L3 `docs/hooks.md:276` still says "The older `CLAUDE_FABLE_GATE_*` and `CODEX_MODEL_GATE_*` variables are still read".
  - A user following the docs who sets `CLAUDE_FABLE_GATE=off` now gets the gate active. The CHANGELOG does say they were removed.
  - `test_no_fallbacks` misses this because the `fable-gate` tokens are scoped to `hooks/` and `bin/` only, and `CLAUDE_FABLE_GATE` is not a token at all.

- [LOW] L4 (secrets/authorization) Path-guard patterns under the old key `dependency_instruction_patterns` stop working silently. (`hooks/guard/paths.py:721`, `update.py:636-653`)
  - The guard stops reading that key the moment 4.0.0 is installed (OQ9, pinned by `test_20b`). `update.py` neither detects it as an old shape nor counts it: `patterns_of` counts only `deny_patterns` and `allow_patterns`. The `regenerate?` row therefore says "drops 0 deny/allow pattern(s)" for a file whose only denies sat under the old key.
  - The behaviour change was decided, but F5's "the row names what it drops" does not hold here.
  - **Suggested direction:** count the old key too, or add a hint naming it.

- [LOW] L5 The installer neither detects nor warns about a pre-3.4b `<!-- claude-agentic:start -->` block in the global `~/.claude/CLAUDE.md` or `AGENTS.md`. (`bin/riskrails.js:1203-1207`)
  - It appends a second, riskrails block beside the old one. The warning regex only looks for `claude-routing` and "Model routing / allocation".
  - D1 says "detect, refuse, never convert". The same gap exists in `scaffold_ai.py`'s `BLOCK`, which now appends next to a legacy pair; `update.py` then refuses that file under exit 6.

- [LOW] L6 Spec Risk 5's orphan hint is not implemented.
  - A project copy of `.ai/workflows/*.md` or `.ai/agents/manager.md` (stubs removed from `SHARED_SET`) is neither offered for deletion nor named in a hint. `shared_update` only iterates the current set.
  - In the same vein: schema-10 `risk-tiers.json`/`.md` sitting beside a `weight.json` (formerly migration 0011) are no longer proposed for deletion.

- [LOW] L7 The CHANGELOG over-states the refusal (`CHANGELOG.md` 4.0.0, `rr-setup/SKILL.md:124`).
  - It says "a project last updated by a riskrails before 3.1.0 is refused". Only the four literal old shapes are refused. A schema-9 or schema-10 tree without them is regenerated, and conversions it never received (0010's `dialog.json`, 0011's retirement) are simply skipped.

- [LOW] L8 Code hygiene in `update.py`: the placeholder comment is duplicated at :359-364, there are stray blank lines at :400-402 and :1471, and `reports =os.path` at :979.

- [INFO] I1 `test_state_characterization` commits `testing.md`, writes `verification.md` with the same commands after the commit, and renames it in the dump so the golden stays byte-identical. (`tests/test_state_characterization.py:196-210,281-284`) in_scope: yes
  - The suite therefore no longer shows which file `state.py` reads. R10 is still proven by `TestVerificationFile` and `TestVerifySet`.

- [INFO] I2 `old_shapes` walks the whole project and reads every `CLAUDE.md`/`AGENTS.md`/`GEMINI.md` outside the skipped dirs. in_scope: no
  - A FIFO with one of those names would block the read. A vendored directory not in `RULES_SKIP` (for example `venv/` or `deps/`) holding an old-marker file refuses the whole update, and installing 3.1.0, as the message says, would not fix it.
  - Severity inside the boundary would be LOW.

## EXAMINED AND CLEAN

- **R8 and guard golden:** `git diff HEAD --stat` shows no change under `tests/fixtures/path-guard/`, `codex-hooks/` or `guard-characterization/`.
  - Decision 7 (writing both `current.json` and `state.json` in the characterization tree) hides only the accepted OQ4 change. That change is pinned on the negative case by `test_ai_path_guard.test_20` ("only a legacy current.json … allowed") and `test_ai_scope_guard.test_only_state_json_arms_the_guard`. No guard decision outside `current.json` or `dependency_instruction_patterns` moved. The `SH_WORD`/`SH_RE` code was not touched.
- **Confirm gate (authentication/authorization):**
  - `human_gate`, `AGENT_MARKERS`, `placeholder_name` and `refuse` match HEAD's `adopt.py` line for line.
  - Every `--confirm-*` flag requires `--apply`, rejects an empty or placeholder name and is checked by `human_gate`; exit 5 prints `CONFIRM_REFUSED`.
  - `--confirm-delete` does not settle `[cleanup]` rows: `cleanup_update` uses `confirm_cleanup`.
  - Tested by `TestGate.test_refused_token`, with the tree digest unchanged.
- **`delete?` and its original/ copy (Risk 1):** every confirmed `delete` copies its original, except `.ai/state` and git-ignored cleanup, as at HEAD. `unsafe_path` is checked again at apply time. The path-guard row prints the dropped count and the original/ path (`TestDryRun` asserts "drops 3"). Gated regenerates copy the original (with the same-day exception in M1).
- **Decision 1 (`--check` and gated rows):** HEAD already left `delete?` and `conflict` rows out of "pending" and exited 0, so this keeps HEAD's semantics. No hook or `state.py` caller reads `--check`.
- **Decision 2:** consistent with D2 (`docs/sdlc/**` KEPT, R4). Only the SKILL text is stale (M3).
- **Decision 3:** acceptable. The `weight.md` mirror header says "edit the JSON and regenerate", its content comes from JSON that the split carries, and a hand-written file is gated.
- **Decision 5 (runtime gate):** at HEAD, `QUOTA_STATE` already equalled `STATE` unless the legacy `*_STATE` variable was set, so there is no new sharing and no new race. The `test_08` `reset_state` only isolates test pollution. Ignoring `CLAUDE_FABLE_GATE=off` makes the gate stricter, not weaker.
- **Decision 6:** the shipped hint matched only this plugin's own path, which is now deleted, so weighting in user projects is unchanged.
- **Decision 8:** the `partition.json` edits match `fs.py`, and the suite is green.
- **Decision 9:** `scaffold_ai.py` skips `weight.json` (A2), which is consistent.
- **Decision 4 (deleted tests):** I checked the removed test names in `test_project_update`, `test_ai_task_state`, `test_install_dry_run`, `test_setup`, `test_shared_tree`, `test_rename`, `test_codex_install` and `test_runtime_gate*`.
  - Each maps to removed behaviour: migrations, three-way merge, adopt, the old weight mirror and risk-tiers convert, legacy markers, `current.json`, the old home, `--as`, the legacy import.
  - `test_a_symlink_into_the_walked_project_adds_no_by_hand_clause` was kept (now at :901).
  - Only `test_every_history_key_is_accounted_for`'s orphan half is lost. That is low value now that renames are gone.
- **History rebuild:** `index.json` only gained hashes, none were removed.
- **Split logic:** `split_testing` and `split_weight` match R11. `check_kept` validates the old `weight.json` before the split reads it. `effective_weight` and `state.py weight --mirror` render the same dict, so a second run is a no-op.
- **Logs:** the suite log shows 1133 tests, OK (skipped=9). The e2e log ends with OK.
- **Security checklist areas:**
  - authentication and authorization: gate above.
  - secrets: `path-guard` defaults unchanged apart from the `_comment` (L2), and L4.
  - personal or payment data: none touched, apart from the domain weighting in H1.
  - webhooks and SSRF: none.
  - input validation: `check_kept` readers.
  - injection: `verification.md` lines are copied verbatim from the same author, so there is no new trust boundary.
  - IDOR: n/a.
  - deserialization: JSON and TOML only, `RecursionError` handled.
  - file and command execution: atomic `write_file`, symlinked target refused, `unsafe_path` checked before deletes.
  - dependencies: none added.
  - data exposure: `original/` stays under `.ai/reports/`.
  - audit logging: `migration.json` records `confirmed_by` and `via` on each confirmed delete and regenerate.
- **Not reached (budget):** a line-by-line read of `render_instructions.py`'s legacy removal, `rules_update`, `test_install_dry_run:410`, `test_end_to_end` and the `bin/riskrails.js` alias and docs sweep beyond `RETIRED_SKILLS`.

## VERDICT

verdict: pass_with_findings
scope_assessment: The change stayed inside the plan's s1–s5 file lists plus the six amendments recorded in `task.md`. No refactoring was mixed in. `CLAUDE_ROUTING_TEMPLATES` was already present at HEAD.
ai_context_safety: no sensitive path (`.env`, secrets, dumps) was read during this review.
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .claude-plugin/marketplace.json | +2 −2 | Edit |
| .claude-plugin/plugin.json | +1 −1 | Edit |
| .codex-plugin/plugin.json | +1 −1 | Edit |
| .pylintrc | +1 −1 | Edit |
| CHANGELOG.md | +22 −0 | Edit |
| README.md | +38 −83 | Edit |
| agents/ai-reviewer.md.tmpl | +1 −1 | Edit |
| ai/agents/manager.md | +0 −5 | Delete |
| ai/using-riskrails.md | +0 −3 | Edit |
| ai/workflows/bugfix.md | +0 −4 | Delete |
| ai/workflows/feature.md | +0 −4 | Delete |
| ai/workflows/hotfix.md | +0 −4 | Delete |
| ai/workflows/investigation.md | +0 −4 | Delete |
| ai/workflows/refactoring.md | +0 −4 | Delete |
| bin/riskrails.js | +13 −59 | Edit |
| docs/architecture.md | +1 −1 | Edit |
| docs/faq.md | +11 −13 | Edit |
| docs/getting-started.md | +2 −6 | Edit |
| docs/hooks.md | +6 −7 | Edit |
| docs/installation.md | +35 −35 | Edit |
| docs/known-risks.md | +6 −22 | Edit |
| docs/project-update.md | +32 −87 | Edit |
| docs/weight.md | +1 −1 | Edit |
| hooks/ai-path-guard-defaults.json | +1 −1 | Edit |
| hooks/context-guard.py | +2 −4 | Edit |
| hooks/guard/paths.py | +3 −6 | Edit |
| hooks/guard/scope.py | +1 −3 | Edit |
| hooks/runtime-gate.py | +18 −58 | Edit |
| instructions/routing.md | +2 −2 | Edit |
| package.json | +1 −1 | Edit |
| scripts/ai-path | +1 −1 | Edit |
| scripts/resolve-profile.py | +0 −3 | Edit |
| skills/ai-audit/SKILL.md | +0 −9 | Delete |
| skills/ai-audit/templates/ai-sdlc-adoption-plan.md | +1 −1 | Edit |
| skills/ai-audit/templates/play-scoring-rubric.md | +1 −1 | Edit |
| skills/ai-init/SKILL.md | +0 −9 | Delete |
| skills/ai-init/templates/.ai/AGENTS.md | +6 −6 | Edit |
| skills/ai-init/templates/.ai/VERSION | +1 −1 | Edit |
| skills/ai-init/templates/.ai/policies/security.md | +1 −2 | Edit |
| skills/ai-init/templates/.ai/policies/testing.md | +5 −12 | Edit |
| skills/ai-init/templates/.ai/policies/verification.md | +18 −0 | New |
| skills/ai-init/templates/.ai/policies/weight.json | +0 −1 | Edit |
| skills/ai-init/templates/.ai/policies/weight.md | +1 −2 | Edit |
| skills/ai-init/templates/.ai/policies/weight.project.json | +4 −0 | New |
| skills/ai-init/templates/.ai/project/architecture.md | +1 −1 | Edit |
| skills/ai-init/templates/.ai/project/initial-assessment.md | +2 −2 | Edit |
| skills/ai-init/templates/.ai/project/overview.md | +1 −1 | Edit |
| skills/ai-init/templates/.ai/rules/README.md | +2 −2 | Edit |
| skills/ai-init/templates/.ai/state/README.md | +1 −1 | Edit |
| skills/ai-status/SKILL.md | +0 −9 | Delete |
| skills/ai-task/SKILL.md | +0 −9 | Delete |
| skills/ai-task/memory_store.py | +8 −9 | Edit |
| skills/ai-task/rr_state/cli.py | +1 −1 | Edit |
| skills/ai-task/rr_state/dialog.py | +2 −4 | Edit |
| skills/ai-task/rr_state/fs.py | +5 −13 | Edit |
| skills/ai-task/rr_state/profile.py | +2 −4 | Edit |
| skills/ai-task/rr_state/questions_cmd.py | +1 −1 | Edit |
| skills/ai-task/rr_state/report.py | +3 −4 | Edit |
| skills/ai-task/rr_state/runtime.py | +1 −1 | Edit |
| skills/ai-task/rr_state/start.py | +7 −7 | Edit |
| skills/ai-task/sensors.py | +10 −11 | Edit |
| skills/ai-task/state.py | +3 −3 | Edit |
| skills/ai-task/weight.py | +17 −17 | Edit |
| skills/ai-task/weight_overlay.py | +38 −0 | New |
| skills/project-init/SKILL.md | +0 −9 | Delete |
| skills/project-init/templates/constitution.md | +2 −2 | Edit |
| skills/project-update/SKILL.md | +0 −9 | Delete |
| skills/project-update/adopt-map.json | +0 −91 | Delete |
| skills/project-update/adopt.py | +0 −2225 | Delete |
| skills/project-update/history/blobs/00f5e27ce2d66e3a1d8b222b013ae8fa1fed32612d91a551e0c661cee3ef9c2d | +34 −0 | New |
| skills/project-update/history/blobs/0a6b1b6dd06a35582b2e9989a1f41c40abc29254b8e482714fcc6f0a7b16c406 | +32 −0 | New |
| skills/project-update/history/blobs/0aeb04b04262683cac6513545683486a73dc473b447bba43b5aaab18403957a6 | +34 −0 | New |
| skills/project-update/history/blobs/0ce913a28996f546f72d570b0e5a376362e993ce4d805bc4aae57d38caa44212 | +41 −0 | New |
| skills/project-update/history/blobs/0ea9e36446b624b73b2a821231b2ee66a357b43d584a5b23da48b3c800855e65 | +41 −0 | New |
| skills/project-update/history/blobs/0fb1d68678a1349195b2e79433bb20174d25874e3bfd0b70410bb4e428b4e4b8 | +35 −0 | New |
| skills/project-update/history/blobs/119b2b9d0f9c647a243540724edac6b29afa020c69aa205797bcfa9eb06bc021 | +35 −0 | New |
| skills/project-update/history/blobs/1d0fe3ee5fb8260ba610942d4bbdfff7410fbe80ed826ac07f32985031dc2b3f | +34 −0 | New |
| skills/project-update/history/blobs/1de9a37ed6402893dcab6e61ddbf15ffd35f15a6d84b18e675a0c5bf4e981f85 | +42 −0 | New |
| skills/project-update/history/blobs/1f44e1a236233dcbab58064f39b69f798b35d1d9a29f8c615b5b12854ce633cb | +15 −0 | New |
| skills/project-update/history/blobs/1f824645299579cbdd8141642ddbb4bca9fd5fe9d3112f036d8221f0811e0abf | +40 −0 | New |
| skills/project-update/history/blobs/235fb88393cfe20dd58b35fe9785cc45baf5ffe21a13d926652d76ec68cea8b7 | +35 −0 | New |
| skills/project-update/history/blobs/36cb593293496fbcf38df828a9b9b2bc0d5a53333f584a5319ebc3d799016e24 | +4 −0 | New |
| skills/project-update/history/blobs/3918b4ee011d9477b9d2779e2893ab599749c406d4b09439a9748b64fbff58f3 | +18 −0 | New |
| skills/project-update/history/blobs/449273200dfec2a56885c881ff34d40e8ecc00da53c24c2d09b7fbeb1004d255 | +40 −0 | New |
| skills/project-update/history/blobs/4c45aee9b9fc5f6b4e1d9739e434c4094975a5a8dec6b9703fb25f3080680c77 | +124 −0 | New |
| skills/project-update/history/blobs/4dd3fa12bc45acc8c836ab65d790248ca7504a021bca6677499d17bb3d798ed9 | +64 −0 | New |
| skills/project-update/history/blobs/51e3f15095d7123ea8566b512479ee10a6cb2f336b7352a259a083a887bd7116 | +33 −0 | New |
| skills/project-update/history/blobs/5497a204967bea7dab29079a6e1dfa3d8713b2d2cb294c2779378039f03a55fc | +36 −0 | New |
| skills/project-update/history/blobs/56e16072c2f3edc6c8897c690d09a11d12fc414c3e3f361f359f7dc609a21282 | +4 −0 | New |
| skills/project-update/history/blobs/60c4d7e7fde7049d92d84295fc13ca9a91eb2de423be08f093b3ee5d5e817ff8 | +64 −0 | New |
| skills/project-update/history/blobs/6221b7c14cc04634e485e562d464c6860d45666a7f63e293c06bb2944ff556cc | +27 −0 | New |
| skills/project-update/history/blobs/637971cfb844ef4285e2886a4b1c834fb2ed5c46e773adb88c2c147fea626ad3 | +33 −0 | New |
| skills/project-update/history/blobs/65af2282eea2a51fcc27a4acf2c26c727b0961c30e1be13176369200c460c219 | +34 −0 | New |
| skills/project-update/history/blobs/66ecd73e303e7bbc1aa8ee72435d0d10812ff7b2eff0adac59bbf0a303e2cc01 | +41 −0 | New |
| skills/project-update/history/blobs/6a43bf32461b22b87fafe2865529dc04fa66cd00182a2a7598aa071667ca255a | +35 −0 | New |
| skills/project-update/history/blobs/6d6dee8634abf9ac057bb206828b83a893a2afcf4f86bbe69e839a3b47d0adde | +48 −0 | New |
| skills/project-update/history/blobs/7224ede803ea81e65a456e21b6028a0e848e8a880456c6503eebe7534ca4f6aa | +74 −0 | New |
| skills/project-update/history/blobs/765a39a202617096c232017822ae738d37e4405430c71700dc7bc14bf1ba794e | +33 −0 | New |
| skills/project-update/history/blobs/77577440a933d1cabd8c6f4a6401cf361a784aa09a25500a6f7b44ead8ab5e55 | +41 −0 | New |
| skills/project-update/history/blobs/7bae90789625d6fb9071ecb412d14a8d1eb0bc5659d8d284c4eaf213e1b5de56 | +67 −0 | New |
| skills/project-update/history/blobs/7bcdf9a0e6b85277b9b60669150224b9414d2e32821ff06f4d148eb1d18785bb | +42 −0 | New |
| skills/project-update/history/blobs/7f834103e9d97aea44e76717bcdcbbe349c560e5b81a42ce85a1cec341041281 | +4 −0 | New |
| skills/project-update/history/blobs/7fb3acb0211818efebc2234863db0b8c846022a7280a6d2d69f267dbf63db48c | +34 −0 | New |
| skills/project-update/history/blobs/87f0855859ff68cc6c988cc0b631ee7f56af7fbba062172bf80e01f4982cc054 | +35 −0 | New |
| skills/project-update/history/blobs/8abab74759766d02b5cb7b0c3e59a3d440b25a454216cd8fea325c23fd822d36 | +33 −0 | New |
| skills/project-update/history/blobs/8cbefbf1aa412bae3e5019acd40b8fe0598fceba6c781906b3bc6dbd014f6b23 | +4 −0 | New |
| skills/project-update/history/blobs/a1fb50e6c86fae1679ef3351296fd6713411a08cf8dd1790a4fd05fae8688164 | +1 −0 | New |
| skills/project-update/history/blobs/a3df7268feb0780be0d2cf9acced6ed81780a7790f36fe024b6ea0b1bd6eb7a6 | +35 −0 | New |
| skills/project-update/history/blobs/af56dc16e44ae1d8c3dac4c3ca82e2163b719553c02ea455e77430bab9a14089 | +4 −0 | New |
| skills/project-update/history/blobs/b28721136482dafb9fd2801af340364cb97e9f6eaa987908606c786045b8d334 | +28 −0 | New |
| skills/project-update/history/blobs/b3726422d767f9219fea633bea77f0c99ad9af843c591e6e928e1ccd2a47f374 | +27 −0 | New |
| skills/project-update/history/blobs/b3839425f9d0ab2efa42a6f5e9488ec2d26ca5fb8dcd694b8ab098e10743ca46 | +32 −0 | New |
| skills/project-update/history/blobs/b9e09cb24958cd6831589997558974bd6356305306e8f9685e226bcdc30d60ac | +4 −0 | New |
| skills/project-update/history/blobs/ba14a457e83f9dde65e4190fdfab83b912f7398c1442a2a1cb3d89bfac741cf3 | +8 −0 | New |
| skills/project-update/history/blobs/bceb7189444bb6291b262ca08e34db01010dda2f6e64d696231ec3c343c95c66 | +34 −0 | New |
| skills/project-update/history/blobs/bf82a2bb4fce1bd349ff66118930a01d61a7af8e2bd8d200c721d43afc58c713 | +34 −0 | New |
| skills/project-update/history/blobs/c4dbeb180292a6199ad73a3be861ece07c1f8bf6bf0cc7ca204412bc8e1bb1d8 | +31 −0 | New |
| skills/project-update/history/blobs/c644838866df2001a42501a988dd7b77aacf862bf09d22b465f3cd8a22c6b6eb | +33 −0 | New |
| skills/project-update/history/blobs/c980d74f76a4bdfb38c94b573ac10a54eb50b850b052e15fa6f2442889b36ccb | +32 −0 | New |
| skills/project-update/history/blobs/ceed2f3bd937f862d0e6ca59ce1b1e3603e19a0d7f85d90d6dfeb7bf690153be | +29 −0 | New |
| skills/project-update/history/blobs/d0cf6388f35a92a0cf607d33909278382f6d7b6a4c32e281b9f9e0ea652c7b91 | +5 −0 | New |
| skills/project-update/history/blobs/d51ea2e893482a20c5882056cf8043327ca1dc1c957927f6746929a47ee8368e | +45 −0 | New |
| skills/project-update/history/blobs/d78f5e0bb1380259fce2cce009785a9a11f6de8b87a160080b9872c059f95060 | +34 −0 | New |
| skills/project-update/history/blobs/d97f46a2cca020406252b1f7baa4184617fa71faca3885e2379c44ae4e1d9327 | +67 −0 | New |
| skills/project-update/history/blobs/da3ecd4c4c414c93d04488685931df39a56bf959bfeb9c45cb1aea2c13bd991b | +38 −0 | New |
| skills/project-update/history/blobs/e129bf71a5a922e24b2c1bc8daa8a5d2b5589b0069770e17ce17e7db5ed4e7a4 | +27 −0 | New |
| skills/project-update/history/blobs/e504529519a371892838725f8b89b5d32e3300e345bcbf2643a3a1a48434b3dd | +24 −0 | New |
| skills/project-update/history/blobs/e9e62d03ca70b3dffccef8dceeb214173352cfef005145e519f0e037993f1c03 | +36 −0 | New |
| skills/project-update/history/blobs/effefbaaf4beb8f1ba55081d6b7e74bf25ebb91045dd10613418f17b95fa7182 | +33 −0 | New |
| skills/project-update/history/blobs/f6af4581bafbf62b257d57e06c3ae2c5998aeca608ee7df037fcc3c3e4b563a9 | +34 −0 | New |
| skills/project-update/history/blobs/fc35045777d29630303430752a651b3e553580a581036a02cc103eb96a46f4b0 | +34 −0 | New |
| skills/project-update/history/blobs/fdc21345c77f92a42d244aa104f393f439a0ff9981a9fd462bd837e8a47931bb | +48 −0 | New |
| skills/project-update/history/index.json | +32 −13 | Edit |
| skills/project-update/migrations/0001_schema_version.py | +0 −13 | Delete |
| skills/project-update/migrations/0002_task_journal.py | +0 −123 | Delete |
| skills/project-update/migrations/0003_context_diet.py | +0 −65 | Delete |
| skills/project-update/migrations/0004_deterministic_gates.py | +0 −57 | Delete |
| skills/project-update/migrations/0005_runtimes_and_plans.py | +0 −35 | Delete |
| skills/project-update/migrations/0006_shared_files.py | +0 −154 | Delete |
| skills/project-update/migrations/0007_weight_model.py | +0 −295 | Delete |
| skills/project-update/migrations/0008_renames.py | +0 −43 | Delete |
| skills/project-update/migrations/0009_state_file.py | +0 −25 | Delete |
| skills/project-update/migrations/0010_dialog_switch.py | +0 −30 | Delete |
| skills/project-update/migrations/0011_retire_risk_tiers.py | +0 −37 | Delete |
| skills/project-update/migrations/README.md | +0 −76 | Delete |
| skills/project-update/migrations/__init__.py | +0 −186 | Delete |
| skills/project-update/render_instructions.py | +12 −45 | Edit |
| skills/project-update/update.py | +757 −1172 | Edit |
| skills/rr-setup/SKILL.md | +28 −73 | Edit |
| skills/rr-setup/scaffold_ai.py | +7 −7 | Edit |
| skills/rr-setup/setup.py | +96 −164 | Edit |
| skills/rr-status/status.py | +7 −10 | Edit |
| skills/sdlc-intent/SKILL.md | +0 −9 | Delete |
| skills/sdlc-plan/SKILL.md | +0 −9 | Delete |
| skills/sdlc-spec/SKILL.md | +0 −9 | Delete |
| skills/usage-report/SKILL.md | +0 −10 | Delete |
| skills/usage-report/usage-report.py | +4 −5 | Edit |
| tests/fixtures/adopt/README.md | +0 −49 | Delete |
| tests/fixtures/adopt/aidlc/README.md | +0 −18 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/aidlc-state.md | +0 −4 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/audit.md | +0 −5 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/construction/build-and-test/build-and-test-instructions.md | +0 −3 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/construction/orders-api/functional-design/business-logic-model.md | +0 −3 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/construction/plans/construction-plan.md | +0 −4 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/inception/application-design/unit-of-work.md | +0 −3 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/inception/plans/inception-plan.md | +0 −4 | Delete |
| tests/fixtures/adopt/aidlc/aidlc-docs/inception/requirements/requirements.md | +0 −6 | Delete |
| tests/fixtures/adopt/aidlc/dot-amazonq/aws-aidlc-rule-details/common/process-overview.md | +0 −3 | Delete |
| tests/fixtures/adopt/aidlc/dot-amazonq/rules/aws-aidlc-rules/core-workflow.md | +0 −4 | Delete |
| tests/fixtures/adopt/aidlc/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/copilot/README.md | +0 −12 | Delete |
| tests/fixtures/adopt/copilot/app/main.py | +0 −2 | Delete |
| tests/fixtures/adopt/copilot/dot-github/copilot-instructions.md | +0 −4 | Delete |
| tests/fixtures/adopt/copilot/dot-github/instructions/python.instructions.md | +0 −7 | Delete |
| tests/fixtures/adopt/copilot/dot-github/instructions/review.instructions.md | +0 −6 | Delete |
| tests/fixtures/adopt/copilot/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/copilot/tests/test_main.py | +0 −2 | Delete |
| tests/fixtures/adopt/cursor/README.md | +0 −17 | Delete |
| tests/fixtures/adopt/cursor/dot-cursor/mcp.json | +0 −3 | Delete |
| tests/fixtures/adopt/cursor/dot-cursor/rules/frontend/react.mdc | +0 −8 | Delete |
| tests/fixtures/adopt/cursor/dot-cursor/rules/general.mdc | +0 −8 | Delete |
| tests/fixtures/adopt/cursor/dot-cursor/rules/testing.mdc | +0 −8 | Delete |
| tests/fixtures/adopt/cursor/dot-cursor/rules/typescript.mdc | +0 −8 | Delete |
| tests/fixtures/adopt/cursor/dot-cursorrules | +0 −3 | Delete |
| tests/fixtures/adopt/cursor/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/cursor/src/components/Button.tsx | +0 −3 | Delete |
| tests/fixtures/adopt/cursor/src/hooks/useCart.ts | +0 −3 | Delete |
| tests/fixtures/adopt/junie-gemini/README.md | +0 −11 | Delete |
| tests/fixtures/adopt/junie-gemini/dot-junie/guidelines.md | +0 −5 | Delete |
| tests/fixtures/adopt/junie-gemini/fixture-GEMINI.md | +0 −6 | Delete |
| tests/fixtures/adopt/junie-gemini/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/kiro/README.md | +0 −21 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/aws-aidlc-rule-details/common/process-overview.md | +0 −3 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/settings/mcp.json | +0 −3 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/specs/user-auth/design.md | +0 −10 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/specs/user-auth/requirements.md | +0 −10 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/specs/user-auth/tasks.md | +0 −5 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/steering/api-standards.md | +0 −9 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/steering/aws-aidlc-rules/core-workflow.md | +0 −3 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/steering/product.md | +0 −7 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/steering/release-checklist.md | +0 −8 | Delete |
| tests/fixtures/adopt/kiro/dot-kiro/steering/tech.md | +0 −4 | Delete |
| tests/fixtures/adopt/kiro/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/kiro/src/api/routes.ts | +0 −1 | Delete |
| tests/fixtures/adopt/large-agents-md/README.md | +0 −16 | Delete |
| tests/fixtures/adopt/large-agents-md/fixture-AGENTS.md | +0 −47 | Delete |
| tests/fixtures/adopt/large-agents-md/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/large-agents-md/split-proposal.fixture.json | +0 −7 | Delete |
| tests/fixtures/adopt/large-agents-md/src/Payment/PaymentGateway.php | +0 −9 | Delete |
| tests/fixtures/adopt/large-claude-md/README.md | +0 −16 | Delete |
| tests/fixtures/adopt/large-claude-md/fixture-CLAUDE.md | +0 −47 | Delete |
| tests/fixtures/adopt/large-claude-md/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/large-claude-md/split-proposal.fixture.json | +0 −7 | Delete |
| tests/fixtures/adopt/large-claude-md/src/Payment/PaymentGateway.php | +0 −9 | Delete |
| tests/fixtures/adopt/speckit/README.md | +0 −28 | Delete |
| tests/fixtures/adopt/speckit/dot-claude/commands/speckit.specify.md | +0 −5 | Delete |
| tests/fixtures/adopt/speckit/dot-claude/skills/speckit-plan/SKILL.md | +0 −6 | Delete |
| tests/fixtures/adopt/speckit/dot-gemini/commands/speckit.plan.toml | +0 −4 | Delete |
| tests/fixtures/adopt/speckit/dot-github/prompts/speckit.tasks.prompt.md | +0 −5 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/extensions.yml | +0 −1 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/extensions/x/extension.yml | +0 −2 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/init-options.json | +0 −1 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/integrations/claude.manifest.json | +0 −1 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/integrations/speckit.manifest.json | +0 −1 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/memory/constitution.md | +0 −22 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/presets/x/preset.md | +0 −3 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/scripts/bash/create-new-feature.sh | +0 −3 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/templates/spec-template.md | +0 −5 | Delete |
| tests/fixtures/adopt/speckit/dot-specify/workflows/x.md | +0 −3 | Delete |
| tests/fixtures/adopt/speckit/fixture.json | +0 −1 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/checklists/requirements.md | +0 −4 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/data-model.md | +0 −5 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/plan.md | +0 −13 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/quickstart.md | +0 −4 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/research.md | +0 −3 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/spec.md | +0 −12 | Delete |
| tests/fixtures/adopt/speckit/specs/001-user-auth/tasks.md | +0 −7 | Delete |
| tests/fixtures/memory/goldens/files-mode.txt | +8 −8 | Edit |
| tests/fixtures/memory/goldens/status-py.txt | +2 −2 | Edit |
| tests/fixtures/project-update/migrations-bad-content/0001_str.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-badmoves/0001_badpath.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-broken/0001_first.py | +0 −7 | Delete |
| tests/fixtures/project-update/migrations-broken/0003_third.py | +0 −7 | Delete |
| tests/fixtures/project-update/migrations-dupmove/0001_first.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-dupmove/0002_second.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-escape/0001_escape.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-invalid/0001_mismatch.py | +0 −8 | Delete |
| tests/fixtures/project-update/migrations-synthetic/0001_create.py | +0 −9 | Delete |
| tests/fixtures/project-update/migrations-synthetic/0002_move.py | +0 −10 | Delete |
| tests/fixtures/project-update/migrations-synthetic/0003_edits.py | +0 −29 | Delete |
| tests/fixtures/project-update/migrations-undeclared/0001_undeclared.py | +0 −8 | Delete |
| tests/fixtures/project-update/risk-tiers/risk-tiers.json | +0 −628 | Delete |
| tests/fixtures/project-update/risk-tiers/risk-tiers.md | +0 −180 | Delete |
| tests/fixtures/project-update/schema-v0/.ai/legacy-notes.md | +0 −4 | Delete |
| tests/fixtures/project-update/schema-v0/.ai/project/overview.md | +0 −4 | Delete |
| tests/fixtures/project-update/schema-v0/README.md | +0 −12 | Delete |
| tests/fixtures/project-update/schema-v1/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v1/README.md | +0 −4 | Delete |
| tests/fixtures/project-update/schema-v2/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v2/README.md | +0 −13 | Delete |
| tests/fixtures/project-update/schema-v3/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v3/.ai/state/current.json | +0 −82 | Delete |
| tests/fixtures/project-update/schema-v3/README.md | +0 −12 | Delete |
| tests/fixtures/project-update/schema-v4/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v4/.ai/state/current.json | +0 −121 | Delete |
| tests/fixtures/project-update/schema-v4/README.md | +0 −13 | Delete |
| tests/fixtures/project-update/schema-v5/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v5/README.md | +0 −12 | Delete |
| tests/fixtures/project-update/schema-v6/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v6/README.md | +0 −10 | Delete |
| tests/fixtures/project-update/schema-v6/in-flight/.ai/state/current.json | +0 −45 | Delete |
| tests/fixtures/project-update/schema-v7/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v7/README.md | +0 −10 | Delete |
| tests/fixtures/project-update/schema-v8/.ai/VERSION | +0 −1 | Delete |
| tests/fixtures/project-update/schema-v8/README.md | +0 −8 | Delete |
| tests/fixtures/project-update/shared-old/AGENTS.v5.md | +0 −56 | Delete |
| tests/fixtures/project-update/shared-old/SOURCES.txt | +0 −4 | Delete |
| tests/fixtures/project-update/shared-old/agents/manager.md | +0 −34 | Delete |
| tests/fixtures/project-update/shared-old/policies/model-routing.md | +0 −42 | Delete |
| tests/fixtures/project-update/shared-old/workflows/feature.md | +0 −27 | Delete |
| tests/fixtures/regenerate/dual/AGENTS.md | +37 −0 | New |
| tests/fixtures/regenerate/dual/CLAUDE.md | +37 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/local/memory/config.json | +1 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/memory/notes.md | +2 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/policies/memory.json | +1 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/policies/verification.md | +9 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/policies/weight.project.json | +7 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/project/overview.md | +2 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/reports/T-2026-01-01-0001/task.md | +1 −0 | New |
| tests/fixtures/regenerate/fresh/.ai/state/state.json | +3 −0 | New |
| tests/fixtures/regenerate/fresh/.claude/settings.json | +1 −0 | New |
| tests/fixtures/regenerate/fresh/docs/sdlc/constitution.md | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/AGENTS.md | +68 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/memory/notes.md | +2 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/coding.md | +33 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/git.md | +3 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/memory.json | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/path-guard.json | +10 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/testing.md | +134 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/tooling.md | +105 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/policies/weight.json | +227 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/reports/T-2026-01-01-0001/task.md | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/rules/php-style.md | +5 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.claude/settings.json | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.gitignore | +7 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/CLAUDE.md | +42 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/docs/sdlc/constitution.md | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/AGENTS.md | +67 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/VERSION | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/coding.md | +32 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/dialog.json | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/path-guard.json | +5 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/safety.md | +84 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/security.md | +75 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/testing.md | +131 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/weight.json | +49 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/policies/weight.md | +32 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/architecture.md | +40 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/business-rules.md | +21 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/dependencies.md | +27 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/glossary.md | +8 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/initial-assessment.md | +8 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/integrations.md | +20 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/known-risks.md | +16 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/legacy.md | +28 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/modules.md | +18 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/project/overview.md | +27 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/reports/.gitkeep | +0 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/rules/README.md | +24 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.ai/state/README.md | +67 −0 | New |
| tests/fixtures/regenerate/v3.1.0/.gitignore | +6 −0 | New |
| tests/fixtures/regenerate/v3.1.0/CLAUDE.md | +37 −0 | New |
| tests/fixtures/state/goldens/dialog.txt | +1 −1 | Edit |
| tests/fixtures/state/goldens/full.txt | +2 −2 | Edit |
| tests/fixtures/state/goldens/guarded.txt | +2 −2 | Edit |
| tests/fixtures/state/goldens/help.txt | +1 −1 | Edit |
| tests/fixtures/state/goldens/light.txt | +4 −4 | Edit |
| tests/fixtures/state/partition.json | +3 −4 | Edit |
| tests/memory_harness.py | +4 −5 | Edit |
| tests/test_ai_path_guard.py | +28 −15 | Edit |
| tests/test_ai_scope_guard.py | +9 −12 | Edit |
| tests/test_ai_status_root.py | +20 −13 | Edit |
| tests/test_ai_task_sensors.py | +44 −9 | Edit |
| tests/test_ai_task_state.py | +27 −33 | Edit |
| tests/test_codex_agent_render.py | +1 −1 | Edit |
| tests/test_codex_install.py | +0 −25 | Edit |
| tests/test_context_guard.py | +10 −13 | Edit |
| tests/test_dialog_contract.py | +2 −2 | Edit |
| tests/test_end_to_end.py | +7 −5 | Edit |
| tests/test_guard_characterization.py | +7 −3 | Edit |
| tests/test_install_dry_run.py | +36 −55 | Edit |
| tests/test_install_routes.py | +16 −0 | Edit |
| tests/test_instruction_budget.py | +7 −30 | Edit |
| tests/test_merge_migration.py | +0 −210 | Delete |
| tests/test_migration_0006.py | +0 −649 | Delete |
| tests/test_migration_0010.py | +0 −127 | Delete |
| tests/test_migration_0011.py | +0 −129 | Delete |
| tests/test_no_fallbacks.py | +220 −0 | New |
| tests/test_no_size_tokens.py | +3 −3 | Edit |
| tests/test_profiles.py | +2 −2 | Edit |
| tests/test_project_adopt.py | +0 −1592 | Delete |
| tests/test_project_update.py | +167 −1826 | Edit |
| tests/test_regenerate.py | +637 −0 | New |
| tests/test_rename.py | +4 −42 | Edit |
| tests/test_runtime_gate.py | +20 −40 | Edit |
| tests/test_runtime_gate_codex.py | +8 −9 | Edit |
| tests/test_runtime_gate_fable.py | +18 −10 | Edit |
| tests/test_scaffold_differential.py | +20 −14 | Edit |
| tests/test_scaffold_idempotency.py | +18 −25 | Edit |
| tests/test_setup.py | +43 −92 | Edit |
| tests/test_shared_prompts_model_free.py | +1 −1 | Edit |
| tests/test_shared_tree.py | +36 −85 | Edit |
| tests/test_skills_surface.py | +12 −19 | Edit |
| tests/test_state_characterization.py | +12 −3 | Edit |
| tests/test_weight.py | +100 −7 | Edit |

+6565 −12759 lines, 375 files

## Verdict

close: closed
facts: (a) green — suite green on 967aa97a9 (run 5) · (b) green — 375 changed files, all in the task's files
gate: requested G1 at 2026-11-10T20:22:28Z; approved by Ivan Kakurov at 2026-11-10T20:25:17Z via dialog
confirm: none
handoffs: 10 · suite runs: 3 · review passes: 1
