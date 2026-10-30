# T-2026-10-30-0758-register-g1-4 — Register groups 1-4: cleanup findings, CI/release, stale names, state and guard fixes

feature · full · started 2026-10-30T07:58:40Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 224 files
behaviour      2  keyword 'workflow' in .github/workflows/npm-publish.yml; hint +1
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       1  5 of 8 code files have a test
W 7 → guarded   hints behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-30T07:58:40Z — /rr-build-all docs/sdlc/plans/register-groups-1-4.md
batch: on by Ivan Kakurov at 2026-10-30T07:58:40Z — /rr-build-all docs/sdlc/plans/register-groups-1-4.md

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, skills/rr-setup/SKILL.md, skills/project-init/templates/sdlc-README.md, skills/project-update/history/**, .github/workflows/npm-publish.yml, .github/workflows/pylint.yml, .github/workflows/tests.yml, tests/test_release.py, tests/test_ere_unit.py, tests/test_guard_differential.py, ai/policies/model-routing.md, ai/policies/review-economy.md, ai/policies/production.md, ai/policies/release.md, .ai/rules/skills.md, skills/CLAUDE.md, skills/AGENTS.md, instructions/routing.md, instructions/stub.md, skills/project-init/templates/constitution.md, tools/build-template-history.py, tests/fixtures/adopt/README.md, tests/fixtures/instructions/rules-project/README.md, README.md, CONTRIBUTING.md, docs/faq.md, docs/hooks.md, docs/known-risks.md, docs/local-memory.md, docs/weight.md, docs/project-update.md, docs/installation.md, bin/riskrails.js, hooks/context-guard.py, hooks/runtime-gate.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py, skills/ai-task/state.py, tests/test_ai_task_state.py, skills/ai-task/sensors.py, tests/test_ai_task_sensors.py, hooks/guard/paths.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/fixtures/guard-characterization/**, docs/sdlc/plans/register-groups-1-4.md, skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md, skills/ai-init/templates/junie-guidelines.block.md, tests/test_dialog_consent.py
tests: tests/test_project_update.py, tests/test_release.py, tests/test_ere_unit.py, tests/test_guard_differential.py, tests/test_shared_prompts_model_free.py, tests/test_instruction_budget.py, tests/test_project_adopt.py, tests/test_scaffold_idempotency.py, tests/test_install_dry_run.py, tests/test_skills_surface.py, tests/test_no_size_tokens.py, tests/test_rename.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py, tests/test_ai_task_state.py, tests/test_weight.py, tests/test_ai_task_sensors.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py
- g1-cleanup · skills/project-update/update.py, tests/test_project_update.py, skills/rr-setup/SKILL.md · tests/test_project_update.py · done
- g1-readme · skills/project-init/templates/sdlc-README.md, skills/project-update/history/** · tests/test_project_update.py · done · after g1-cleanup
- g2-release · .github/workflows/npm-publish.yml, .github/workflows/pylint.yml, .github/workflows/tests.yml, tests/test_release.py · tests/test_release.py · done
- g2-timed · tests/test_ere_unit.py, tests/test_guard_differential.py · tests/test_ere_unit.py, tests/test_guard_differential.py · done
- g3-policies · ai/policies/model-routing.md, ai/policies/review-economy.md, ai/policies/production.md, ai/policies/release.md, skills/project-update/history/** · tests/test_shared_prompts_model_free.py, tests/test_instruction_budget.py, tests/test_project_update.py · done · after g1-readme, g1-cleanup
- g3-rules · .ai/rules/skills.md, skills/CLAUDE.md, skills/AGENTS.md, instructions/routing.md, instructions/stub.md, skills/project-init/templates/constitution.md, tools/build-template-history.py, tests/fixtures/adopt/README.md, tests/fixtures/instructions/rules-project/README.md, skills/project-update/history/** · tests/test_instruction_budget.py, tests/test_project_update.py, tests/test_project_adopt.py, tests/test_scaffold_idempotency.py · done · after g3-policies, g1-cleanup, g1-readme
- g3-docs · README.md, CONTRIBUTING.md, docs/faq.md, docs/hooks.md, docs/known-risks.md, docs/local-memory.md, docs/weight.md, docs/project-update.md, docs/installation.md, bin/riskrails.js · tests/test_install_dry_run.py, tests/test_skills_surface.py, tests/test_no_size_tokens.py, tests/test_rename.py · done · after g3-rules
- g3-hooks · hooks/context-guard.py, hooks/runtime-gate.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py · tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate_fable.py · done
- g4-state · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py, tests/test_weight.py · done
- g4-sensors · skills/ai-task/sensors.py, tests/test_ai_task_sensors.py · tests/test_ai_task_sensors.py · done
- g4-guard · hooks/guard/paths.py, tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/fixtures/guard-characterization/** · tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py · done · after g2-timed
amended 2026-10-30T08:09:09Z: +skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md — g3-rules: C5 in instructions/stub.md must be re-rendered into the shipped block templates (render_instructions.py build), test_one_source_the_committed_templates_are_rendered
amended 2026-10-30T08:09:17Z: +skills/ai-init/templates/junie-guidelines.block.md — g3-rules: the fourth committed render of instructions/stub.md
amended 2026-10-30T08:18:47Z: +tests/test_dialog_consent.py — Q2=A: the dialog-off verify --by case (R36.2) changes by the human's decision; the dialog-on --mode light case stays allow

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. g4-guard: what should the path guard deny of an agent's 'state.py start ... --mode ... --by'? (raising a mode is free and documented in rr-plan/rr-build-all; state.py already refuses a lowering via human_route)
asked: 2026-10-30T08:01:32Z · stage: implementation
A. deny only --mode light with --by (the one value that can never raise); other lowerings stay with state.py's check (recommended)
B. deny every start --mode --by and move raising to the human's terminal (widens scope to rr-build-all, rr-plan, faq, weight docs)
C. leave start --mode out of the guard; only verify/review/reject --by in both dialog modes plus SETBY removal
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T08:03:32Z

## Q2. Suite-1: the new HUMAN_BY_RE contradicts test_dialog_consent: (1) dialog ON 'start --mode light --by' must reach state.py so it opens the lowering decision (review H1, T-2026-10-28-010) - the guard now denies it first; (2) dialog OFF 'verify --by' must run as today (spec R36.2 'Off changes nothing'). What now?
asked: 2026-10-30T08:17:53Z · stage: implementation
A. --mode light deny only with the dialog OFF (dialog ON keeps H1's route); verify/review/reject --by deny in both modes as decided - update the R36.2 case and note R36.2 amended in the plan (recommended)
B. like A, but keep R36.2 too: with the dialog OFF the guard denies nothing new (E11 stays open in the register); only SETBY removal and the dialog-ON --mode light route stay unchanged
C. deny in both modes as implemented; update both test cases (dialog ON lowering to light then only from the human's terminal)
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T08:18:33Z

## G1. Approve T-2026-10-30-0758-register-g1-4 for implementation? (gate: human_approval)
asked: 2026-10-30T08:44:54Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T08:45:26Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | aad62d40b | .ai/state/logs/T-2026-10-30-0758-register-g1-4/suite-1.log | no |
| 2 | suite | 0 | 8e4ed54dc | .ai/state/logs/T-2026-10-30-0758-register-g1-4/suite-2.log | no |
| 3 | e2e | 0 | 8e4ed54dc | .ai/state/logs/T-2026-10-30-0758-register-g1-4/e2e-3.log | no |
| 4 | suite | 0 | 336215de8 | .ai/state/logs/T-2026-10-30-0758-register-g1-4/suite-4.log | no |
| 5 | e2e | 0 | 336215de8 | .ai/state/logs/T-2026-10-30-0758-register-g1-4/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS
- [HIGH] H1 --confirm-cleanup has no path-guard rule: CONFIRM (hooks/guard/paths.py:68-73, :1161-1176) cannot match --confirm-cleanup, so an agent line with inline AI_UNATTENDED=1 reaches update.py --apply --confirm-cleanup and adopt.human_gate (adopt.py:47) accepts it; deletes git-ignored logs and reports and records a forged confirmed_by. Regression vs [cleanup] needing --confirm-delete; decision G1 M3 not met. in_scope: yes
- [MEDIUM] M1 E3: --expect fail counts only exit 1 as a bite (state.py:3902); pytest exits 2 on a collection error, phpunit 2 on an errored test, cargo 101; wider than the plan (exit 2 only). in_scope: yes
- [MEDIUM] M2 [cleanup] rows under .ai/reports/<id>/** are git-tracked, not git-ignored; deletion_hint skipped and no original/ copy, an uncommitted report dir is lost without warning (update.py:1141-1146, :1583-1585; rr-setup/SKILL.md). in_scope: yes
- [MEDIUM] M3 publish rerun skips the upload on a version-string match only; a re-pointed tag on attempt 2 announces a commit npm does not serve (.github/workflows/npm-publish.yml:70-82, :110-114). in_scope: yes
- [LOW] L1 moved-3.4.json:117 says start --mode light --by is denied with the dialog off as well as on; under Q2 it is dialog-off only. in_scope: yes
- [LOW] L2 the timed cases (test_ai_path_guard.py:206-214) are over LONG_CMD=4096 and time the long-command rule, not HUMAN_BY_RE/START_LIGHT_RE on the Python path (~4000 chars, repeated $S start --by heads ending in xlight). in_scope: yes
- [LOW] L3 MODE_LIGHT misses argparse abbreviations --mo/--mod (allow_abbrev). in_scope: yes
- [LOW] L4 instructions/stub.md:50 lost "outside" and "correction" in the byte-budget rewrite. in_scope: yes
- [INFO] I1 sensors --relative drops index-staged paths outside the root from fact (b). I2 E5 by event type, not marker. I3 HUMAN_BY_RE matches quoted/echo text (risk recorded). I4 fact (a) red after one doc change. I5 --confirm prefix now ambiguous (argparse exit 2).
## VERDICT
verdict: pass_with_findings
scope_assessment: inside the plan and its three amendments; H1 a gap against G1 M3; M1 wider than the plan (every non-1 exit).
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/rules/skills.md | +1 −1 | Edit |
| .github/workflows/npm-publish.yml | +23 −4 | Edit |
| .github/workflows/pylint.yml | +1 −1 | Edit |
| .github/workflows/tests.yml | +1 −1 | Edit |
| README.md | +1 −1 | Edit |
| ai/policies/model-routing.md | +7 −7 | Edit |
| ai/policies/production.md | +3 −3 | Edit |
| ai/policies/release.md | +2 −2 | Edit |
| ai/policies/review-economy.md | +27 −30 | Edit |
| bin/riskrails.js | +5 −5 | Edit |
| docs/sdlc/plans/register-groups-1-4.md | +2 −0 | Edit |
| hooks/context-guard.py | +1 −1 | Edit |
| hooks/guard/paths.py | +41 −30 | Edit |
| hooks/runtime-gate.py | +6 −6 | Edit |
| instructions/routing.md | +1 −1 | Edit |
| instructions/stub.md | +2 −2 | Edit |
| skills/AGENTS.md | +1 −1 | Edit |
| skills/CLAUDE.md | +1 −1 | Edit |
| skills/ai-init/templates/AGENTS.block.md | +1 −1 | Edit |
| skills/ai-init/templates/CLAUDE.block.md | +1 −1 | Edit |
| skills/ai-init/templates/GEMINI.block.md | +1 −1 | Edit |
| skills/ai-init/templates/junie-guidelines.block.md | +1 −1 | Edit |
| skills/ai-task/sensors.py | +6 −3 | Edit |
| skills/ai-task/state.py | +23 −7 | Edit |
| skills/project-init/templates/constitution.md | +1 −1 | Edit |
| skills/project-init/templates/sdlc-README.md | +3 −3 | Edit |
| skills/project-update/history/blobs/07ff7fa6f93d471ff533f553b4e523e4105ccde1f3dab70132c5237728f68422 | +13 −0 | New |
| skills/project-update/history/blobs/18c7a2753ce9cb6f6d3d1e9d5d1125d75950b879d56b7325225b200869631b29 | +15 −0 | New |
| skills/project-update/history/blobs/7170553410bba904ffb7edb4b231e3b3579b85542d84de717299980938f82c9d | +13 −0 | New |
| skills/project-update/history/blobs/d6e5b34d475e7187d2a8cb2aac7e7f1a427142baf6461bda387d70ceb4d8a8c1 | +30 −0 | New |
| skills/project-update/history/blobs/e120ff4e32b2e950fc94ada4e787d57dc9c790da37223e5a202d74f7e3aadf80 | +13 −0 | New |
| skills/project-update/history/index.json | +20 −10 | Edit |
| skills/project-update/update.py | +75 −28 | Edit |
| skills/rr-setup/SKILL.md | +7 −3 | Edit |
| tests/fixtures/adopt/README.md | +1 −1 | Edit |
| tests/fixtures/guard-characterization/golden.txt | +4 −0 | Edit |
| tests/fixtures/guard-characterization/moved-3.4.json | +5 −1 | Edit |
| tests/fixtures/instructions/rules-project/README.md | +1 −1 | Edit |
| tests/test_ai_path_guard.py | +57 −15 | Edit |
| tests/test_ai_task_sensors.py | +41 −0 | Edit |
| tests/test_ai_task_state.py | +62 −0 | Edit |
| tests/test_context_guard.py | +1 −1 | Edit |
| tests/test_dialog_consent.py | +2 −1 | Edit |
| tests/test_ere_unit.py | +21 −3 | Edit |
| tests/test_guard_differential.py | +1 −1 | Edit |
| tests/test_project_update.py | +77 −7 | Edit |
| tests/test_release.py | +33 −4 | Edit |
| tools/build-template-history.py | +1 −1 | Edit |

+656 −192 lines, 48 files

## Verdict

close: closed
facts: (a) green — suite green on 336215de8 (run 4) · (b) green — 48 changed files, all in the task's files
gate: requested G1 at 2026-10-30T08:44:54Z; approved by Ivan Kakurov at 2026-10-30T08:45:26Z via dialog
confirm: none
handoffs: 10 · suite runs: 3 · review passes: 1
