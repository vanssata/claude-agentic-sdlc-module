# T-2026-10-31-1852-wp1-split-skills-ai-task — WP1: split skills/ai-task/state.py into rr_state/ behind an unchanged entry; behaviour pinned by the characterization golden

refactoring · guarded · started 2026-10-31T18:52:00Z · claude

## Weight

```
scope          2  tests/test_install_dry_run.py referenced from 18 files
behaviour      1  keyword 'workflow' in CONTRIBUTING.md
reversibility  0  git revert returns everything
domain         0  plugin internals (declared)
novelty        0  stdlib only, the sibling-module pattern of sensors.py and memory_*.py (declared)
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T18:52:00Z — /rr-build-all docs/sdlc/plans/small-oop-modules.md (Q22)

## Plan

files: skills/ai-task/state.py, skills/ai-task/rr_state/**, tools/state-partition.py, tests/test_state_layout.py, tests/test_state_characterization.py, tests/fixtures/state/**, tests/test_install_dry_run.py, tests/test_dialog_contract.py, .pylintrc, docs/architecture.md, CONTRIBUTING.md, .ai/project/known-risks.md
tests: tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_state_layout.py
- s0 · tools/state-partition.py, tests/fixtures/state/partition.json, tests/test_state_layout.py · tests/test_state_layout.py · in_progress
- s1 · tests/test_state_characterization.py, tests/fixtures/state/goldens/help.txt, tests/fixtures/state/goldens/light.txt, tests/fixtures/state/goldens/guarded.txt, tests/fixtures/state/goldens/full.txt, tests/fixtures/state/goldens/dialog.txt · tests/test_state_characterization.py · pending
- s2 · skills/ai-task/state.py · tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py · pending · after s1
- s3-fs · skills/ai-task/rr_state/fs.py, skills/ai-task/rr_state/__init__.py · tests/test_state_layout.py · pending · after s0, s2
- s3-locks · skills/ai-task/rr_state/locks.py · tests/test_state_layout.py · pending · after s0, s2, s3-fs
- s3-runtime · skills/ai-task/rr_state/runtime.py · tests/test_state_layout.py · pending · after s3-fs, s3-locks, s0, s2
- s3-policy · skills/ai-task/rr_state/policy.py · tests/test_state_layout.py · pending · after s3-fs, s3-locks, s0, s2, s3-runtime
- s4-journal · skills/ai-task/rr_state/journal.py · tests/test_state_layout.py · pending · after s3-runtime, s3-policy, s0, s3-fs, s3-locks
- s4-task · skills/ai-task/rr_state/task.py · tests/test_state_layout.py · pending · after s4-journal, s0, s3-fs, s3-locks, s3-runtime, s3-policy
- s5-questions · skills/ai-task/rr_state/questions.py · tests/test_state_layout.py · pending · after s4-task, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal
- s5-ledger · skills/ai-task/rr_state/ledger.py · tests/test_state_layout.py · pending · after s4-task, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s5-questions
- s5-gate · skills/ai-task/rr_state/gate.py · tests/test_state_layout.py · pending · after s4-task, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s5-questions, s5-ledger
- s6-dialog · skills/ai-task/rr_state/dialog.py · tests/test_state_layout.py · pending · after s5-questions, s5-ledger, s5-gate, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task
- s6-authority · skills/ai-task/rr_state/authority.py · tests/test_state_layout.py · pending · after s6-dialog, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate
- s6-report · skills/ai-task/rr_state/report.py · tests/test_state_layout.py · pending · after s6-authority, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog
- s6-handoff · skills/ai-task/rr_state/handoff.py · tests/test_state_layout.py · pending · after s6-authority, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-report
- s6-profile · skills/ai-task/rr_state/profile.py · tests/test_state_layout.py · pending · after s6-authority, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-report, s6-handoff
- s7-questions_cmd · skills/ai-task/rr_state/questions_cmd.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority
- s7-gate_cmd · skills/ai-task/rr_state/gate_cmd.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd
- s7-dialog_cmd · skills/ai-task/rr_state/dialog_cmd.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd
- s7-report_cmd · skills/ai-task/rr_state/report_cmd.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd
- s7-memory_cmd · skills/ai-task/rr_state/memory_cmd.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd
- s7-steps · skills/ai-task/rr_state/steps.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd
- s7-start · skills/ai-task/rr_state/start.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps
- s7-verify · skills/ai-task/rr_state/verify.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps, s7-start
- s7-review · skills/ai-task/rr_state/review.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps, s7-start, s7-verify
- s7-close · skills/ai-task/rr_state/close.py · tests/test_state_layout.py · pending · after s6-report, s6-handoff, s6-profile, s0, s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps, s7-start, s7-verify, s7-review
- s8 · skills/ai-task/rr_state/cli.py, skills/ai-task/state.py, tests/test_state_layout.py, .pylintrc, tests/test_install_dry_run.py, tests/test_dialog_contract.py · tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_project_update.py, tests/test_skills_surface.py, tests/test_state_layout.py, tests/test_install_dry_run.py · pending · after s3-fs, s3-locks, s3-runtime, s3-policy, s4-journal, s4-task, s5-questions, s5-ledger, s5-gate, s6-dialog, s6-authority, s6-report, s6-handoff, s6-profile, s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps, s7-start, s7-verify, s7-review, s7-close, s0, s1, s2
- s9 · docs/architecture.md, CONTRIBUTING.md, .ai/project/known-risks.md · tests/test_instruction_budget.py, tests/test_skills_surface.py · pending · after s0, s8

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|

suite not_run · e2e not_run · suite runs 0

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: abandoned
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 1 · suite runs: 0 · review passes: 0
