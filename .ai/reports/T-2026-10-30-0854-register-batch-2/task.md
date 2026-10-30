# T-2026-10-30-0854-register-batch-2 — Register batch 2: remaining mechanical fixes and the risk-tiers retirement

feature · full · started 2026-10-30T08:54:26Z · claude

## Weight

```
scope          2  hooks/guard/paths.py matches hot_paths hooks/**
behaviour      2  "migration 0011 retires risk-tiers.*; update.py cleanup/merge changes; ignore snippet; bite_code
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       1  7 of 9 code files have a test
W 7 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-30T08:54:26Z — /rr-build-all docs/sdlc/plans/register-batch-2.md
re-score 2026-10-30T09:28:00Z at verify: reversibility 0 → 1 — skills/project-update/migrations/0011_retire_risk_tiers.py matches needs_step **/migrations/**
batch: on by Ivan Kakurov at 2026-10-30T08:54:26Z — /rr-build-all docs/sdlc/plans/register-batch-2.md

## Plan

files: hooks/guard/paths.py, hooks/guard/common.py, tests/test_ai_path_guard.py, tests/fixtures/guard-characterization/**, skills/ai-task/state.py, skills/ai-task/sensors.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, skills/ai-init/templates/.ai/policies/testing.md, skills/project-update/history/**, skills/usage-report/usage-report.py, tests/test_usage_report.py, skills/project-update/update.py, skills/rr-setup/SKILL.md, tests/test_project_update.py, tests/test_migration_0006.py, skills/rr-review/SKILL.md, skills/rr-build-all/SKILL.md, skills/rr-setup/setup.py, tests/test_setup.py, skills/project-update/render_instructions.py, instructions/stub.md, skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md, skills/ai-init/templates/junie-guidelines.block.md, skills/ai-init/templates/gitignore.snippet, .github/workflows/npm-publish.yml, .github/workflows/tests.yml, tests/test_release.py, hooks/update_notice.py, tests/test_update_notice.py, README.md, docs/installation.md, skills/project-update/migrations/**, skills/ai-init/templates/.ai/**, ai/policies/review-economy.md, tests/test_migration_0011.py, tests/fixtures/**, docs/**, docs/sdlc/plans/register-batch-2.md, tests/test_scaffold_idempotency.py, tests/test_migration_0010.py, tests/test_merge_migration.py, tests/fixtures/memory/goldens/files-mode.txt, tests/fixtures/memory/goldens/status-py.txt, tests/test_end_to_end.py
tests: tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_dialog_consent.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_weight.py, tests/test_project_update.py, tests/test_usage_report.py, tests/test_migration_0006.py, tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_setup.py, tests/test_project_adopt.py, tests/test_release.py, tests/test_update_notice.py, tests/test_context_guard.py, tests/test_scaffold_idempotency.py, tests/test_install_dry_run.py
- guard · hooks/guard/paths.py, hooks/guard/common.py, tests/test_ai_path_guard.py, tests/fixtures/guard-characterization/** · tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_dialog_consent.py · done
- state · skills/ai-task/state.py, skills/ai-task/sensors.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, skills/ai-init/templates/.ai/policies/testing.md, skills/project-update/history/** · tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_weight.py, tests/test_project_update.py · done
- usage · skills/usage-report/usage-report.py, tests/test_usage_report.py · tests/test_usage_report.py · done
- update · skills/project-update/update.py, skills/rr-setup/SKILL.md, tests/test_project_update.py, tests/test_migration_0006.py · tests/test_project_update.py, tests/test_migration_0006.py · done · after state
- texts · skills/rr-review/SKILL.md, skills/rr-build-all/SKILL.md · tests/test_skills_surface.py, tests/test_instruction_budget.py · done
- setup · skills/rr-setup/setup.py, tests/test_setup.py, skills/project-update/render_instructions.py · tests/test_setup.py, tests/test_instruction_budget.py · done · after texts
- instr · instructions/stub.md, skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md, skills/ai-init/templates/junie-guidelines.block.md, skills/project-update/history/** · tests/test_instruction_budget.py, tests/test_project_adopt.py, tests/test_project_update.py · done · after state, update, texts, setup
- consent · skills/ai-init/templates/gitignore.snippet, skills/project-update/history/** · tests/test_project_update.py · done · after instr, state, update
- ci · .github/workflows/npm-publish.yml, .github/workflows/tests.yml, tests/test_release.py · tests/test_release.py · done
- notice · hooks/update_notice.py, tests/test_update_notice.py · tests/test_update_notice.py, tests/test_context_guard.py · done
- docs · README.md, docs/installation.md · tests/test_skills_surface.py · done · after texts
- retire · skills/project-update/migrations/**, skills/ai-init/templates/.ai/**, skills/project-update/update.py, skills/ai-task/state.py, ai/policies/review-economy.md, skills/project-update/history/**, tests/test_migration_0011.py, tests/test_project_update.py, tests/test_migration_0006.py, tests/test_ai_task_state.py, tests/fixtures/**, docs/** · tests/test_project_update.py, tests/test_migration_0006.py, tests/test_ai_task_state.py, tests/test_project_adopt.py, tests/test_scaffold_idempotency.py, tests/test_install_dry_run.py · done · after update, state, consent, guard, instr, docs
amended 2026-10-30T09:12:36Z: +tests/test_scaffold_idempotency.py — consent step: a test that the shipped ignore snippet matches .ai/state/consent.jsonl (#33)
amended 2026-10-30T09:25:15Z: +tests/test_migration_0010.py, tests/test_merge_migration.py — retire: schema 11 and the retired risk-tiers templates move the pins in these two tests (decided scope: retirement)
amended 2026-10-30T09:28:46Z: +tests/fixtures/memory/goldens/files-mode.txt, tests/fixtures/memory/goldens/status-py.txt — suite-1: schema 11 moves the 'plugin 10' line in two memory goldens; the same line's '/project-update' suffix becomes /rr-setup --update (risk R-status-schema-line-still-says-behind-run-6fc8)
amended 2026-10-30T09:30:38Z: +tests/test_end_to_end.py — e2e: a new scaffold ships weight.json, not risk-tiers.json (migration 0011)

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-0854-register-batch-2 for implementation? (gate: human_approval)
asked: 2026-10-30T09:45:09Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T09:45:52Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 81a60025f | .ai/state/logs/T-2026-10-30-0854-register-batch-2/suite-1.log | no |
| 2 | suite | 0 | 79923f8a3 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/suite-2.log | no |
| 3 | e2e | 1 | 79923f8a3 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/e2e-3.log | no |
| 4 | suite | 0 | 3a81d1be7 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/suite-4.log | no |
| 5 | e2e | 0 | 3a81d1be7 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/e2e-5.log | no |
| 6 | e2e | 0 | 8bf7c9838 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/e2e-6.log | no |
| 7 | step | 0 | 8bf7c9838 | .ai/state/logs/T-2026-10-30-0854-register-batch-2/step-7.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M1 A project below schema 10 that has not confirmed 0011's delete? stays at its starting schema, so 0007-0010 re-run on every update; 0007 re-adds carried values to weight.json a human removed (update.py:1401-1407, 0011_retire_risk_tiers.py:11-13, 0007_weight_model.py:171-188; pinned by test_full_apply). in_scope: yes
- [LOW] L1 skills/rr-status/status.py:105 still reads risk-tiers.json for max_suite_runs/review_rounds_max; after 0011 it shows the hard-coded defaults. in_scope: yes
- [LOW] L2 cleanup_update has no plan-time unsafe_path check; a symlinked .ai/reports/<id> is proposed and every apply aborts on it (update.py:1133-1176 vs 1620-1623). in_scope: yes
- [LOW] L3 sensors.bite_codes accepts 0 and negatives; an invalid list falls back to (1,) silently (sensors.py:248-256). in_scope: yes
- [LOW] L4 no timed case for the MODE_LIGHT-led branch with many '$S start --m light' heads. Session probe (rr-review §2): START_LIGHT_RE and HUMAN_BY_RE at 4005-4090 chars, 0.2 ms each via guard Matcher.ere_match — linear. in_scope: yes
- [LOW] L5 docs/project-update.md has no row for schema 11; rollback misses that a schema-10 plugin refuses a schema-11 project until .ai/VERSION is set back. in_scope: yes
- [LOW] L6 no expected_fail verify run is journaled for the bugfix tests (implementers reported fail-before runs in their results). in_scope: yes
- [LOW] L7 #18 deferred to the register (accepted) without a plan amendment. in_scope: yes
- [INFO] I1 no test for 0011's symlinked risk-tiers branch. I2 risk-tiers.md flagged as edited after old fix_mirror sha rewrites. I3 routers' Shared files text, ai/agents/risk.md:3, this repo's .ai/AGENTS.md:34 and testing.md:112 still name risk-tiers. I4 the 3.11 floor is not checked by the installer. I5 update.py:1131 whitespace typo. I6 abandon_old leaves a .tmp on json.dump failure. I7 consent.jsonl stays tracked in this repo. I8 task.md retire step omits tests/test_migration_0011.py. I9 stub.md lost the '(this project's principles)' gloss. I10 no test for a BOM-prefixed config file. I11 sensors.py:9 docstring lists detect.
## VERDICT
verdict: pass
scope_assessment: inside the plan's files and its journaled amendments; #18 deferred without amendment (L7); M1 arises from the existing hold-at-start rule now applied to nearly every project.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +9 −0 | Edit |
| .github/workflows/tests.yml | +36 −2 | Edit |
| README.md | +4 −4 | Edit |
| docs/installation.md | +2 −2 | Edit |
| hooks/guard/common.py | +2 −0 | Edit |
| hooks/guard/paths.py | +1 −1 | Edit |
| hooks/update_notice.py | +20 −14 | Edit |
| instructions/stub.md | +2 −2 | Edit |
| skills/ai-init/templates/.ai/AGENTS.md | +1 −1 | Edit |
| skills/ai-init/templates/.ai/VERSION | +1 −1 | Edit |
| skills/ai-init/templates/.ai/policies/risk-tiers.json | +0 −628 | Delete |
| skills/ai-init/templates/.ai/policies/risk-tiers.md | +0 −180 | Delete |
| skills/ai-init/templates/.ai/policies/testing.md | +14 −6 | Edit |
| skills/ai-init/templates/AGENTS.block.md | +2 −2 | Edit |
| skills/ai-init/templates/CLAUDE.block.md | +2 −2 | Edit |
| skills/ai-init/templates/GEMINI.block.md | +2 −2 | Edit |
| skills/ai-init/templates/gitignore.snippet | +1 −0 | Edit |
| skills/ai-init/templates/junie-guidelines.block.md | +2 −2 | Edit |
| skills/ai-task/sensors.py | +18 −1 | Edit |
| skills/ai-task/state.py | +15 −8 | Edit |
| skills/project-update/history/blobs/00289f98434fed230eebe768dfb3425f83d737866a3aebc97aa95167c4fa0c6e | +131 −0 | New |
| skills/project-update/history/blobs/25d4f2a86deb5e2574bb3210b67bb24fcc4afb19f93a7b65a057daa874a9d18e | +1 −0 | New |
| skills/project-update/history/blobs/48d9950f16e31d55475f566a80dc95f64b35f1c804d2f51729e313a4f29bac8d | +13 −0 | New |
| skills/project-update/history/blobs/5a93f78b4ed4d416c171139b2ce610a117f9c1dd46fbb56ca86729cb4c53d10c | +6 −0 | New |
| skills/project-update/history/blobs/774b1e3a04ef0d49d33c44a2cfecd92eb6f6b738a12b6a681103ba7fc13e7b86 | +67 −0 | New |
| skills/project-update/history/blobs/7f063e79195a5c85c37b7260dd20c184d3b9bea85e37202e0bbca73ad84bba49 | +13 −0 | New |
| skills/project-update/history/blobs/c8573ca1f810ce6c4ac49456a4c1725b93e0d3b74c54ce95d46d8747777895f0 | +13 −0 | New |
| skills/project-update/history/index.json | +16 −8 | Edit |
| skills/project-update/migrations/0011_retire_risk_tiers.py | +37 −0 | New |
| skills/project-update/migrations/__init__.py | +6 −1 | Edit |
| skills/project-update/render_instructions.py | +1 −1 | Edit |
| skills/project-update/update.py | +115 −69 | Edit |
| skills/rr-build-all/SKILL.md | +2 −2 | Edit |
| skills/rr-review/SKILL.md | +13 −8 | Edit |
| skills/rr-setup/SKILL.md | +7 −3 | Edit |
| skills/rr-setup/setup.py | +7 −1 | Edit |
| skills/usage-report/usage-report.py | +4 −2 | Edit |
| tests/fixtures/memory/goldens/files-mode.txt | +2 −2 | Edit |
| tests/fixtures/memory/goldens/status-py.txt | +2 −2 | Edit |
| tests/fixtures/project-update/risk-tiers/risk-tiers.json | +628 −0 | New |
| tests/fixtures/project-update/risk-tiers/risk-tiers.md | +180 −0 | New |
| tests/test_ai_path_guard.py | +15 −0 | Edit |
| tests/test_ai_task_sensors.py | +16 −0 | Edit |
| tests/test_ai_task_state.py | +60 −2 | Edit |
| tests/test_end_to_end.py | +4 −2 | Edit |
| tests/test_merge_migration.py | +1 −1 | Edit |
| tests/test_migration_0006.py | +5 −8 | Edit |
| tests/test_migration_0010.py | +3 −3 | Edit |
| tests/test_migration_0011.py | +129 −0 | New |
| tests/test_project_update.py | +125 −66 | Edit |
| tests/test_release.py | +24 −0 | Edit |
| tests/test_scaffold_idempotency.py | +16 −15 | Edit |
| tests/test_setup.py | +13 −1 | Edit |
| tests/test_update_notice.py | +29 −5 | Edit |
| tests/test_usage_report.py | +13 −0 | Edit |

+1851 −1060 lines, 55 files

## Verdict

close: closed
facts: (a) green — documents only since run 4 (1 files: README.md); doc_tests green in run 7 on 8bf7c9838 · (b) green — 55 changed files, all in the task's files
gate: requested G1 at 2026-10-30T09:45:09Z; approved by Ivan Kakurov at 2026-10-30T09:45:52Z via dialog
confirm: none
handoffs: 7 · suite runs: 3 · review passes: 1
