# T-2026-11-01-1907-split-label-helpers-out — Split label helpers out of rr_state/dialog.py (<600 lines) and clear all pylint messages, no behaviour change

refactoring · guarded · started 2026-11-01T19:07:55Z · claude

## Weight

```
scope          2  skills/ai-task/rr_state/dialog.py referenced from 178 files
behaviour      1  keyword 'workflow' in skills/ai-task/rr_state/start.py
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        0  same module-split pattern as the existing rr_state partition with partition.json moves records (
coverage       1  9 of 12 code files have a test
W 5 → guarded   hints none · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/rr_state/labels.py, skills/ai-task/rr_state/dialog.py, skills/ai-task/rr_state/start.py, skills/ai-task/rr_state/verify.py, skills/ai-task/rr_state/review.py, skills/ai-task/rr_state/dialog_cmd.py, skills/ai-task/state.py, tests/fixtures/state/partition.json, hooks/guard/dialog.py, hooks/project-scaffold.py, hooks/runtime-gate.py, skills/project-update/update.py, tools/build-template-history.py, tests/fixtures/run-suite/test_fail.py, tests/fixtures/run-suite/test_green.py, tests/fixtures/run-suite/test_unexpected_success.py, tests/guard_harness.py, tests/run_suite.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_ere_unit.py, tests/test_install_dry_run.py, tests/test_profile_detect.py, tests/test_profiles.py, tests/test_project_update.py, tests/test_rename.py, tests/test_run_suite.py, tests/test_runtime_gate.py, tests/test_scaffold_differential.py, tests/test_scaffold_idempotency.py, tests/test_update_notice.py, tests/test_usage_report.py
tests: tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_ere_unit.py, tests/test_guard_characterization.py, tests/test_install_dry_run.py, tests/test_profile_detect.py, tests/test_profiles.py, tests/test_project_update.py, tests/test_rename.py, tests/test_run_suite.py, tests/test_runtime_gate.py, tests/test_scaffold_differential.py, tests/test_scaffold_idempotency.py, tests/test_state_characterization.py, tests/test_state_layout.py, tests/test_update_notice.py, tests/test_usage_report.py
- s1 · skills/ai-task/rr_state/labels.py, skills/ai-task/rr_state/dialog.py, skills/ai-task/rr_state/start.py, skills/ai-task/rr_state/verify.py, skills/ai-task/rr_state/review.py, skills/ai-task/rr_state/dialog_cmd.py, skills/ai-task/state.py, tests/fixtures/state/partition.json · tests/test_state_layout.py, tests/test_state_characterization.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py · done
- s2 · hooks/guard/dialog.py, hooks/project-scaffold.py, hooks/runtime-gate.py, skills/project-update/update.py, tools/build-template-history.py · tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_runtime_gate.py, tests/test_project_update.py, tests/test_scaffold_idempotency.py · done · after s1
- s3 · tests/fixtures/run-suite/test_fail.py, tests/fixtures/run-suite/test_green.py, tests/fixtures/run-suite/test_unexpected_success.py, tests/guard_harness.py, tests/run_suite.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_ere_unit.py, tests/test_install_dry_run.py, tests/test_profile_detect.py, tests/test_profiles.py, tests/test_project_update.py, tests/test_rename.py, tests/test_run_suite.py, tests/test_runtime_gate.py, tests/test_scaffold_differential.py, tests/test_scaffold_idempotency.py, tests/test_update_notice.py, tests/test_usage_report.py · tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_task_sensors.py, tests/test_ai_task_state.py, tests/test_codex_install.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_ere_unit.py, tests/test_install_dry_run.py, tests/test_profile_detect.py, tests/test_profiles.py, tests/test_project_update.py, tests/test_rename.py, tests/test_run_suite.py, tests/test_runtime_gate.py, tests/test_scaffold_differential.py, tests/test_scaffold_idempotency.py, tests/test_update_notice.py, tests/test_usage_report.py · done · after s2

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 56f31dcc1 | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/step-1.log | no |
| 2 | step | 0 | 540de00a1 | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/step-2.log | no |
| 3 | step | 0 | f2334bbdf | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/step-3.log | no |
| 4 | step | 0 | 4bdf528a0 | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/step-4.log | no |
| 5 | suite | 0 | 4bdf528a0 | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/suite-5.log | no |
| 6 | e2e | 0 | 4bdf528a0 | .ai/state/logs/T-2026-11-01-1907-split-label-helpers-out/e2e-6.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 skills/ai-task/rr_state/labels.py — new module is untracked (`??`) and is imported by dialog/start/verify/review/dialog_cmd/state.py. in_scope: yes — why it matters: a commit that stages only modified files would leave HEAD importing a missing module (state.py fails at import). The commit step must `git add` labels.py. No code change needed.
- [LOW] L2 tests/fixtures/state/partition.json (labels `approx_lines` 73, dialog 433) — the line estimates are well below actual (labels.py 99, dialog.py 540). in_scope: yes — why it matters: tools/state-partition.py reports 0 problems so the field is not enforced; cosmetic, but the "dialog stays under 600" claim rests on the real count (540), which holds.
- [INFO] I1 docs/sdlc/specs/small-oop-modules.md:266 and :407 — spec still places label_argv/subcommand*/validate_label/state_label in dialog.py and its state.py re-export block shows `from rr_state.dialog import ... validate_label ... LABEL_MAX`. in_scope: no — why it matters: docs now disagree with code; the spec is outside the declared inputs of this step. Record for a follow-up docs change; does not affect behaviour.
- [INFO] I2 hooks/runtime-gate.py, hooks/project-scaffold.py, hooks/guard/dialog.py, skills/project-update/update.py, tools/build-template-history.py — all five pylint edits read; no decision change. in_scope: yes (clean)

Checked and clean: no `labels` local/parameter shadowing in dialog.py, start.py, verify.py, dialog_cmd.py (review.py imports `labels as rr_labels`, its locals never touch it); state shim re-exports LABEL_MAX, validate_label from labels only; dialog.py `import re` removal safe; partition.json labels layer 1, imports fs {ENTRY, one_line, run_text}, dialog/start/verify/review/dialog_cmd imports consistent, moves record names all 13; finite_number closure renamed at all four sites; with-open creates/closes same; SystemExit(2) from None same exit/stderr; return None is a no-op under sys.exit; hook dialog.py change is a comment; every rc→_rc was never read; script=script binds the loop's current script; same_outcome(outcomes[0], outcomes[1]) equivalent (exactly two appended); deep_project never read kw; dialog_gate/dialog_contract/install_dry_run/project_update renames scope-safe; encoding additions only on empty files; PLUGIN imports unused; disables line-scoped with reasons, .pylintrc untouched.

Not reached (budget): running pylint/suite myself.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stays inside the plan: mechanical move + import re-pointing, no logic edits; hook/tool edits are lint-only; partition fixture updated consistently.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/guard/dialog.py | +1 −1 | Edit |
| hooks/project-scaffold.py | +2 −1 | Edit |
| hooks/runtime-gate.py | +4 −4 | Edit |
| skills/ai-task/rr_state/dialog.py | +14 −102 | Edit |
| skills/ai-task/rr_state/dialog_cmd.py | +4 −4 | Edit |
| skills/ai-task/rr_state/labels.py | +99 −0 | New |
| skills/ai-task/rr_state/review.py | +3 −2 | Edit |
| skills/ai-task/rr_state/start.py | +2 −2 | Edit |
| skills/ai-task/rr_state/verify.py | +2 −2 | Edit |
| skills/ai-task/state.py | +3 −2 | Edit |
| skills/project-update/update.py | +1 −1 | Edit |
| tests/fixtures/run-suite/test_fail.py | +1 −1 | Edit |
| tests/fixtures/run-suite/test_green.py | +1 −1 | Edit |
| tests/fixtures/run-suite/test_unexpected_success.py | +1 −1 | Edit |
| tests/fixtures/state/partition.json | +7 −6 | Edit |
| tests/guard_harness.py | +2 −2 | Edit |
| tests/run_suite.py | +1 −0 | Edit |
| tests/test_ai_path_guard.py | +1 −1 | Edit |
| tests/test_ai_scope_guard.py | +1 −1 | Edit |
| tests/test_ai_task_sensors.py | +1 −1 | Edit |
| tests/test_ai_task_state.py | +7 −7 | Edit |
| tests/test_codex_install.py | +7 −7 | Edit |
| tests/test_dialog_contract.py | +2 −2 | Edit |
| tests/test_dialog_gate.py | +12 −10 | Edit |
| tests/test_ere_unit.py | +4 −2 | Edit |
| tests/test_install_dry_run.py | +29 −29 | Edit |
| tests/test_profile_detect.py | +3 −3 | Edit |
| tests/test_profiles.py | +1 −1 | Edit |
| tests/test_project_update.py | +13 −12 | Edit |
| tests/test_rename.py | +2 −1 | Edit |
| tests/test_run_suite.py | +1 −0 | Edit |
| tests/test_runtime_gate.py | +1 −1 | Edit |
| tests/test_scaffold_differential.py | +1 −1 | Edit |
| tests/test_scaffold_idempotency.py | +1 −1 | Edit |
| tests/test_update_notice.py | +1 −1 | Edit |
| tests/test_usage_report.py | +1 −1 | Edit |
| tools/build-template-history.py | +1 −0 | Edit |

+238 −214 lines, 37 files

## Verdict

close: closed
facts: (a) green — suite green on 4bdf528a0 (run 5) · (b) green — 37 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
