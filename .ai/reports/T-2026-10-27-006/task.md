# T-2026-10-27-006 — Rename the state file current.json to state.json and the plugin claude-agentic to RiskRails/riskrails, with migration 0008 and one version of old-name compatibility (R34, R35; plan row 3.4b)

refactoring · full · started 2026-10-27T19:35:02Z · claude

## Weight

```
scope          2  README.md referenced from 147 files
behaviour      1  keyword 'workflow' in README.md
reversibility  2  skills/project-update/migrations/0008_renames.py matches needs_step **/migrations/**; hint +1
domain         1  UNKNOWN — neither measured nor declared
novelty        1  a new migration on the existing migrations framework; installer home move + symlink is new (decl
coverage       1  8 of 14 code files have a test
W 8 → full   hints reversibility +1 · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: README.md, agents/*, agents/ai-reviewer.md.tmpl, ai/*, codex/*, docs/*.md, docs/sdlc/plans/claude-agentic-redesign.md, hooks/*, hooks/ai-path-guard-defaults.json, hooks/ai-scope-guard.sh, hooks/context-guard.py, hooks/guard/paths.py, hooks/guard/scope.py, hooks/runtime-gate.py, install.sh, instructions/*, profiles/*, scripts/*, settings.common.json, skills/*, skills/ai-init/templates/.ai/state/README.md, skills/ai-task/*, skills/project-update/adopt.py, skills/project-update/migrations/0008_renames.py, skills/project-update/migrations/README.md, skills/project-update/migrations/__init__.py, skills/project-update/render_instructions.py, skills/project-update/update.py, skills/rr-status/status.py, tests/*, tests/fixtures/guard-characterization/*, tests/fixtures/path-guard/*, tests/fixtures/project-update/schema-v7/*, tests/lib.sh, tests/test-codex-install.sh, tests/test-dual-runtime-install.sh, tests/test-guard-characterization.sh, tests/test-install-dry-run.sh, tests/test-profiles.sh, tests/test-shared-tree.sh, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_context_guard.py, tests/test_end_to_end.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_project_adopt.py, tests/test_project_update.py, tests/test_rename.py, tests/test_runtime_gate.py, tools/build-template-history.py, tools/golden-diff.py, skills/ai-init/templates/*.block.md, skills/ai-init/templates/.ai/AGENTS.md, skills/ai-init/templates/.ai/rules/README.md, skills/project-update/history/*, instructions/stub.md, tests/test_render_instructions.py, skills/ai-init/templates/.ai/VERSION, skills/rr-setup/scaffold_ai.py, tests/test_scaffold_idempotency.py, tests/test-scaffold-idempotency.sh, tests/fixtures/scaffold-port/*, tests/test_instruction_budget.py, docs/sdlc/specs/claude-agentic-redesign.md
tests: tests/test-codex-install.sh, tests/test-dual-runtime-install.sh, tests/test-install-dry-run.sh, tests/test-profiles.sh, tests/test-shared-tree.sh, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_context_guard.py, tests/test_guard_characterization.py, tests/test_project_adopt.py, tests/test_project_update.py, tests/test_rename.py, tests/test_runtime_gate.py
- s1 · skills/ai-task/*, hooks/guard/scope.py, hooks/guard/paths.py, hooks/context-guard.py, hooks/runtime-gate.py, hooks/ai-path-guard-defaults.json, hooks/ai-scope-guard.sh, skills/rr-status/status.py, skills/project-update/adopt.py, skills/project-update/update.py, skills/project-update/migrations/README.md, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/.ai/state/README.md, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_end_to_end.py, tests/test_project_adopt.py, tests/test_project_update.py, tests/test_guard_differential.py, tests/fixtures/path-guard/* · tests/test_ai_task_state.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_ai_task_sensors.py · done
- s2 · skills/project-update/migrations/0008_renames.py, skills/project-update/migrations/__init__.py, skills/project-update/migrations/README.md, skills/project-update/update.py, skills/project-update/render_instructions.py, skills/project-update/adopt.py, tests/test_project_update.py, tests/test_project_adopt.py, tests/fixtures/project-update/schema-v7/* · tests/test_project_update.py, tests/test_project_adopt.py · done
- s3 · hooks/*, scripts/*, profiles/*, settings.common.json, codex/*, instructions/*, ai/*, agents/*, skills/*, tools/build-template-history.py, tests/test_rename.py, tests/* · tests/test_rename.py · done
- s4 · install.sh, tests/test-install-dry-run.sh, tests/test-dual-runtime-install.sh, tests/test-codex-install.sh, tests/test-profiles.sh, tests/test-shared-tree.sh, tests/lib.sh · tests/test-install-dry-run.sh, tests/test-dual-runtime-install.sh, tests/test-codex-install.sh, tests/test-profiles.sh, tests/test-shared-tree.sh · done
- s5 · tests/fixtures/guard-characterization/*, tools/golden-diff.py, tests/test_guard_characterization.py, tests/test-guard-characterization.sh, README.md, docs/*.md, docs/sdlc/plans/claude-agentic-redesign.md · tests/test_guard_characterization.py · done
amended 2026-10-27T19:44:20Z: +skills/ai-init/templates/*.block.md, skills/ai-init/templates/.ai/AGENTS.md, skills/ai-init/templates/.ai/rules/README.md, skills/project-update/history/*, instructions/stub.md, tests/test_render_instructions.py — the marker rename (0008's subject) must land with the templates that carry the markers and their history, or s2's tests cannot pass
amended 2026-10-27T19:46:24Z: +skills/ai-init/templates/.ai/VERSION — a new scaffold starts at schema 8 once migration 0008 exists
amended 2026-10-27T19:50:46Z: +skills/rr-setup/scaffold_ai.py — the scaffold detects an existing managed block by its start marker; it must know the riskrails marker or it appends a second block
amended 2026-10-27T19:51:20Z: +tests/test_scaffold_idempotency.py — its assertions name the managed-block marker that 0008 renames
amended 2026-10-27T19:51:33Z: +tests/test-scaffold-idempotency.sh — the shell twin run by run-all.sh greps the managed-block marker that 0008 renames
amended 2026-10-27T20:04:18Z: +tests/fixtures/scaffold-port/* — Q1=A: the frozen scaffold copies get a rename-only patch so the differential still compares
amended 2026-10-27T20:09:14Z: +tests/test_instruction_budget.py — it asserts the installed routing.md path, which moves to riskrails/ in s4
amended 2026-10-27T20:52:34Z: +docs/sdlc/specs/claude-agentic-redesign.md — Q2=B: R34 is split — 3.4b ships the both-name readers, the file move moves to a later task

## Questions

[questions.md](questions.md) — 0 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 5e4a6745f | .ai/state/logs/T-2026-10-27-006/step-1.log | yes |
| 2 | step | 1 | f1b3ca1b2 | .ai/state/logs/T-2026-10-27-006/step-2.log | no |
| 3 | step | 1 | cee77bbe9 | .ai/state/logs/T-2026-10-27-006/step-3.log | no |
| 4 | step | 1 | edf2c5d6f | .ai/state/logs/T-2026-10-27-006/step-4.log | no |
| 5 | step | 0 | acae22424 | .ai/state/logs/T-2026-10-27-006/step-5.log | no |
| 6 | step | 1 | 6c152636c | .ai/state/logs/T-2026-10-27-006/step-6.log | yes |
| 7 | step | 1 | 27aedb459 | .ai/state/logs/T-2026-10-27-006/step-7.log | no |
| 8 | step | 0 | 6e8f4e006 | .ai/state/logs/T-2026-10-27-006/step-8.log | no |
| 9 | step | 1 | 2acee6125 | .ai/state/logs/T-2026-10-27-006/step-9.log | no |
| 10 | step | 0 | f61047d8e | .ai/state/logs/T-2026-10-27-006/step-10.log | no |
| 11 | step | 0 | 890c68066 | .ai/state/logs/T-2026-10-27-006/step-11.log | no |
| 12 | suite | 0 | e2d427bc0 | .ai/state/logs/T-2026-10-27-006/suite-12.log | no |
| 13 | e2e | 0 | e2d427bc0 | .ai/state/logs/T-2026-10-27-006/e2e-13.log | no |
| 14 | step | 1 | 637c51878 | .ai/state/logs/T-2026-10-27-006/step-14.log | no |
| 15 | suite | 0 | 998f5900a | .ai/state/logs/T-2026-10-27-006/suite-15.log | no |
| 16 | e2e | 0 | 998f5900a | .ai/state/logs/T-2026-10-27-006/e2e-16.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS
- [HIGH] H1 docs/sdlc/plans/claude-agentic-redesign.md:344 (with skills/ai-task/state.py:398-405, hooks/guard/scope.py:336-338) — The plan's rollback ("A revert therefore leaves migrated user projects working") is false: the dual-name readers (read_state_path, scope/paths/context-guard/runtime-gate/status/adopt fallbacks) ship in this same change. A project that ran 0008 (or whose new state.py saved once — save() deletes current.json) has only state.json and .ai/VERSION 8. After `git revert`, HEAD's scope guard returns early when current.json is absent (an implementation-stage task silently loses its scope guard), HEAD's path guard sees no task so task_protected_patterns (.claude/settings*.json, .ai/policies/) become writable mid-task, HEAD's state.py says "no task in flight", and HEAD's update.py refuses schema 8 > 7, so /rr-setup --update cannot repair it. Reversibility-2 task whose documented rollback silently disables guards. Direction: expand/contract (ship both-name readers one version, move the file the next) or correct the Rollback text to require restoring current.json + VERSION 7 per project by hand. — in_scope: yes
- [MEDIUM] M1 skills/project-update/update.py:447-455 (MigrationContext.block_status) — refactoring regression: block_status passes an old <!-- claude-agentic:start --> block through current_markers (renamed to riskrails) but compares against raw history.versions(...) (old markers); renamed_markers is applied in block_update but not here. Every pre-3.4b block version except the last now classifies as "edited" (6 of 8 shipped CLAUDE.block versions). Executed: a pristine schema-2 project (v2_project helper) updated with this tree prints `hint CLAUDE.md: the managed block was edited here, so the plugin's stub cannot replace it — move your lines below the block…` and the same for AGENTS.md, while the same run says "managed block replaced (unchanged since it was installed)"; HEAD prints neither hint. Caller is migration 0003, so any project < schema 3 gets contradictory advice. test_schema_3_takes_the_pipeline_text_out only asserts the AGENTS.md hint is present, never absent for a pristine file. Direction: compare against map(renamed_markers, …) as block_update does; pin with a negative assertion. — in_scope: yes
- [MEDIUM] M2 skills/ai-task/state.py:402-405, skills/ai-task/state.py:466, hooks/runtime-gate.py:131,142,857, skills/project-update/update.py:505 — compat is one-directional (new reads old, old never reads new). (a) Mixed install: on a dual-runtime machine where only one runtime got this build (install.sh --target claude, Codex still on old copies in ~/.codex/hooks and skills), the first new state.py save in a shared project deletes current.json even before /rr-setup --update — the other runtime's old scope guard and path-guard task arming go inert for that task, silently. (b) state.py / runtime-gate / usage-report read the profile only at <home>/riskrails/profile.json, no fallback to claude-agentic/; a skills tree updated without re-running install.sh (the .codex-plugin route ships ./skills/) loses its plan budgets silently ("no profile, no budget"). (c) 0006's require_shared checks only <other home>/riskrails/ai: a Codex home installed pre-3.4b now makes 0006 refuse a 5→8 update that HEAD allowed (fails safe, with an instruction). Direction: profile fallback to claude-agentic/profile.json for one version; an install-time note when the other runtime's home has not moved. — in_scope: yes
- [LOW] L1 skills/ai-task/state.py:404-407 — save() does os.remove(legacy) inside the try whose failure dies with "cannot write state.json … nothing was recorded"; if the remove fails (permissions, or a concurrent save already removed it between exists and remove) that message is false — state.json was written. Use contextlib.suppress(FileNotFoundError) as remove_state does, and a separate message. — in_scope: yes
- [LOW] L2 tests/test_project_update.py:88,499, tests/test_merge_migration.py:54-56, tests/test_instruction_budget.py:149-150, tests/test_codex_agent_render.py:59, tests/test_shared_prompts_model_free.py:97 — env scrub lists still remove only CLAUDE_AGENTIC_* and tests still set CLAUDE_AGENTIC_SHARED/TEMPLATES; the code now prefers RISKRAILS_*, so a developer/CI shell exporting RISKRAILS_SHARED/TEMPLATES/MIGRATIONS silently overrides what the tests set. The new names RISKRAILS_TEMPLATES/HISTORY/MIGRATIONS/TEST in update.py/adopt.py/migrations/__init__.py are never exercised (only ai-path's SHARED is, in test_rename). The current.json fallbacks in runtime-gate.project_task, context-guard.task_in_flight, sensors.resolve_trees, status.state_file, adopt.task_in_flight have no test. Codex home move untested (only the Claude dir in test-install-dry-run.sh). — in_scope: yes
- [LOW] L3 hooks/ai-path-guard-defaults.json:2 — the shipped _comment still says task arming is ".ai/state/current.json exists and has not reached \"done\""; test_rename cannot catch it (not an old plugin name). — in_scope: yes
- [LOW] L4 tests/test_rename.py:22-39 — the allow-list is per file, not per line: any new non-compat old name in update.py, render_instructions.py, scaffold_ai.py or adopt.py passes; install.sh (the file with the most compat lines) is outside SCOPE (matches the spec's list); SKIP_DIRS={"history"} skips any directory named history anywhere. — in_scope: yes
- [LOW] L5 tests/test_project_update.py test_migrations_name_no_runtime — `claude(?!-agentic)` is a narrow, justified exemption; it still catches a bare `claude` runtime branch, and the original never used re.I. Noted as an acceptable weakening, not a defect. — in_scope: yes
- [INFO] I1 skills/project-update/migrations/0008_renames.py:28-30 — ROUTE's `ai(?:-path)?\b` backtracks to match /claude-agentic/ai-<anything>; MARKER also rewrites a marker the user quotes in a fenced code block or prose in a root instruction file. Harmless in practice; 0008 is idempotent (a re-run is a no-op). — in_scope: yes
- [INFO] I2 install.sh:557-568 (move_home) — a dangling symlink at <home>/riskrails makes mv fail and set -e aborts the install (verified by execution); an old home that is itself a symlink into dotfiles is left as is, so projects below schema 8 keep routing to a tree no install updates; rule blocks in subdirectories keep legacy markers forever when the project has no .ai/rules/ (rules_update returns early). Also resolve-profile with both keys present leaves claude_agentic in the --print settings output. — in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the approved plan and its amendments, and no feature rode along. Guard decisions are identical on the forward path, as the golden check confirms. Two problems remain: the plan's rollback for 0008 does not hold (H1), and one advisory output changed in a refactoring (M1, confirmed by execution).
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +17 −11 | Edit |
| codex/hooks.json | +1 −1 | Edit |
| docs/agents.md | +1 −1 | Edit |
| docs/architecture.md | +2 −2 | Edit |
| docs/faq.md | +2 −2 | Edit |
| docs/getting-started.md | +2 −2 | Edit |
| docs/hook-performance.md | +1 −1 | Edit |
| docs/hooks.md | +2 −2 | Edit |
| docs/sdlc/plans/claude-agentic-redesign.md | +14 −5 | Edit |
| docs/sdlc/specs/claude-agentic-redesign.md | +10 −8 | Edit |
| hooks/ai-git-guard.sh | +1 −1 | Edit |
| hooks/ai-guard.py | +1 −1 | Edit |
| hooks/ai-path-guard-defaults.json | +2 −2 | Edit |
| hooks/ai-path-guard.sh | +1 −1 | Edit |
| hooks/ai-scope-guard.sh | +2 −2 | Edit |
| hooks/context-guard.py | +5 −2 | Edit |
| hooks/guard/paths.py | +11 −6 | Edit |
| hooks/guard/scope.py | +6 −3 | Edit |
| hooks/lib/ai-hook-common.sh | +1 −1 | Edit |
| hooks/project-scaffold.py | +1 −1 | Edit |
| hooks/runtime-gate.py | +13 −5 | Edit |
| install.sh | +72 −39 | Edit |
| instructions/routing.md | +1 −1 | Edit |
| instructions/stub.md | +2 −2 | Edit |
| profiles/balanced-max.json | +1 −1 | Edit |
| profiles/codex-balanced-max.json | +1 −1 | Edit |
| profiles/codex-plus.json | +1 −1 | Edit |
| profiles/codex-pro.json | +1 −1 | Edit |
| profiles/max.json | +1 −1 | Edit |
| profiles/max20.json | +1 −1 | Edit |
| profiles/pro.json | +1 −1 | Edit |
| scripts/ai-path | +2 −2 | Edit |
| scripts/render-codex-agents.py | +2 −2 | Edit |
| scripts/resolve-profile.py | +11 −8 | Edit |
| skills/ai-init/scaffold-ai.sh | +1 −1 | Edit |
| skills/ai-init/templates/.ai/AGENTS.md | +2 −2 | Edit |
| skills/ai-init/templates/.ai/VERSION | +1 −1 | Edit |
| skills/ai-init/templates/.ai/rules/README.md | +1 −1 | Edit |
| skills/ai-init/templates/AGENTS.block.md | +2 −2 | Edit |
| skills/ai-init/templates/CLAUDE.block.md | +2 −2 | Edit |
| skills/ai-init/templates/GEMINI.block.md | +2 −2 | Edit |
| skills/ai-init/templates/junie-guidelines.block.md | +2 −2 | Edit |
| skills/ai-task/sensors.py | +6 −4 | Edit |
| skills/ai-task/state.py | +27 −7 | Edit |
| skills/project-update/adopt.py | +16 −7 | Edit |
| skills/project-update/history/blobs/65acd4be95c695d0cc20cb5f4faffe0f44e0873b385c124140b223c41328cb56 | +13 −0 | New |
| skills/project-update/history/blobs/7eee4ea9f6e778ff691c263621e717c021505b86386034cc64f8ebbfc9d8fe65 | +13 −0 | New |
| skills/project-update/history/blobs/aa67a169b0bba217aa0aa88a65346920c84c42447c36ba5f7ea65f422c1fe5d8 | +1 −0 | New |
| skills/project-update/history/blobs/ae49c96abe45e56e88ae5e28e046212f7114d6413785cbe998f692d2914792be | +24 −0 | New |
| skills/project-update/history/blobs/c076d603cffc731823d2acf096bcc17cca1d99eee24b0aa313776d7d01571b4f | +13 −0 | New |
| skills/project-update/history/blobs/fe513647c66e8883b326ea884a7e9cb045ce54c49b03d2e75a0b73c4756c423e | +67 −0 | New |
| skills/project-update/history/index.json | +14 −7 | Edit |
| skills/project-update/migrations/0008_renames.py | +43 −0 | New |
| skills/project-update/migrations/__init__.py | +5 −3 | Edit |
| skills/project-update/render_instructions.py | +28 −16 | Edit |
| skills/project-update/update.py | +52 −25 | Edit |
| skills/rr-build/SKILL.md | +1 −1 | Edit |
| skills/rr-plan/SKILL.md | +1 −1 | Edit |
| skills/rr-setup/SKILL.md | +3 −3 | Edit |
| skills/rr-setup/scaffold_ai.py | +4 −4 | Edit |
| skills/rr-spec/SKILL.md | +1 −1 | Edit |
| skills/rr-status/SKILL.md | +1 −1 | Edit |
| skills/rr-status/status.py | +9 −3 | Edit |
| skills/usage-report/usage-report.py | +10 −5 | Edit |
| tests/fixtures/guard-characterization/golden.txt | +59 −44 | Edit |
| tests/fixtures/path-guard/110-write-state-json.json | +1 −0 | New |
| tests/fixtures/path-guard/111-bash-sed-i-state-json.json | +1 −0 | New |
| tests/fixtures/project-update/schema-v7/.ai/VERSION | +1 −0 | New |
| tests/fixtures/project-update/schema-v7/README.md | +10 −0 | New |
| tests/fixtures/scaffold-port/project-scaffold.sh | +1 −1 | Edit |
| tests/fixtures/scaffold-port/scaffold-ai.sh | +3 −3 | Edit |
| tests/test-codex-install.sh | +12 −12 | Edit |
| tests/test-dual-runtime-install.sh | +14 −14 | Edit |
| tests/test-install-dry-run.sh | +46 −24 | Edit |
| tests/test-profiles.sh | +7 −7 | Edit |
| tests/test-scaffold-idempotency.sh | +9 −9 | Edit |
| tests/test-shared-tree.sh | +9 −9 | Edit |
| tests/test_ai_path_guard.py | +29 −9 | Edit |
| tests/test_ai_scope_guard.py | +16 −4 | Edit |
| tests/test_ai_task_state.py | +28 −2 | Edit |
| tests/test_codex_agent_render.py | +6 −5 | Edit |
| tests/test_instruction_budget.py | +9 −9 | Edit |
| tests/test_merge_migration.py | +3 −3 | Edit |
| tests/test_migration_0006.py | +2 −1 | Edit |
| tests/test_project_adopt.py | +3 −3 | Edit |
| tests/test_project_update.py | +120 −28 | Edit |
| tests/test_rename.py | +94 −0 | New |
| tests/test_runtime_gate.py | +10 −10 | Edit |
| tests/test_scaffold_idempotency.py | +9 −9 | Edit |
| tests/test_shared_prompts_model_free.py | +2 −1 | Edit |
| tests/test_usage_report.py | +2 −2 | Edit |

+1064 −431 lines, 91 files

## Verdict

close: closed
facts: (a) green — suite green on 998f5900a (run 15) · (b) green — 91 changed files, all in the task's files
gate: requested G1 at 2026-10-27T21:03:28Z; approved by vanssa at 2026-10-27T21:06:37Z via terminal
confirm: none
handoffs: 12 · suite runs: 2 · review passes: 1
