# T-2026-10-26-002 — Redesign 2.4: agents from 14 to 5 templates (Explore, log-reader, ai-discovery, ai-reviewer, architect), no -strong/-balanced twins; budgets.fan_out and budgets.direct_mode out of runtime-gate.py and the profiles

refactoring · full · started 2026-10-26T10:40:41Z · claude

## Weight

```
scope          2  agents/ai-context.md.tmpl referenced from 107 files
behaviour      2  weight.json:204 — install.sh retires nine agents and four Codex twins into backups/ (changes how
reversibility  0  git revert returns everything
domain         0  plugin tooling, no auth/payments/personal data (declared)
novelty        0  removal along the plan's 2.4 row; retire mechanism already exists at install.sh:569 (declared)
coverage       1  3 of 4 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-26T10:40:41Z — skills/CLAUDE.md: a behaviour-2 change starts in full to keep a STRONG review and the gate; chosen by the human 2026-10-26

## Plan

files: agents/ai-context.md.tmpl, agents/ai-expert.md.tmpl, agents/ai-implementer.md.tmpl, agents/ai-indexer.md.tmpl, agents/ai-planner.md.tmpl, agents/ai-release.md.tmpl, agents/ai-risk.md.tmpl, agents/ai-security.md.tmpl, agents/ai-tester.md.tmpl, agents/ai-reviewer.md.tmpl, profiles/balanced-max.json, profiles/codex-balanced-max.json, profiles/codex-plus.json, profiles/codex-pro.json, profiles/max.json, profiles/max20.json, profiles/pro.json, scripts/render-codex-agents.py, tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh, ai/agents/context.md, ai/agents/implementer.md, ai/agents/planner.md, ai/agents/release.md, ai/agents/risk.md, ai/agents/security.md, ai/agents/tester.md, ai/agents/reviewer.md, tests/test-shared-tree.sh, skills/project-update/history/index.json, hooks/runtime-gate.py, skills/usage-report/usage-report.py, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/fixtures/codex-hooks/30-agent-expert-launch.json, tests/fixtures/codex-hooks/32-subagent-stop-rate-limit.json, tests/fixtures/codex-hooks/33-subagent-stop-uncertain.json, install.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh, instructions/routing.md, ai/policies/model-routing.md, ai/policies/release.md, ai/templates/review-report.md, ai/templates/task-context.md, tests/test-instruction-budget.sh, .ai/project/known-risks.md
tests: tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh, tests/test-shared-tree.sh, tests/test-project-update.sh, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh, tests/test-instruction-budget.sh
- s1 · agents/ai-context.md.tmpl, agents/ai-expert.md.tmpl, agents/ai-implementer.md.tmpl, agents/ai-indexer.md.tmpl, agents/ai-planner.md.tmpl, agents/ai-release.md.tmpl, agents/ai-risk.md.tmpl, agents/ai-security.md.tmpl, agents/ai-tester.md.tmpl, agents/ai-reviewer.md.tmpl, profiles/balanced-max.json, profiles/codex-balanced-max.json, profiles/codex-plus.json, profiles/codex-pro.json, profiles/max.json, profiles/max20.json, profiles/pro.json, scripts/render-codex-agents.py, tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh · tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh · in_progress
- s2 · ai/agents/context.md, ai/agents/implementer.md, ai/agents/planner.md, ai/agents/release.md, ai/agents/risk.md, ai/agents/security.md, ai/agents/tester.md, ai/agents/reviewer.md, tests/test-shared-tree.sh, skills/project-update/history/index.json · tests/test-shared-tree.sh, tests/test-project-update.sh · pending
- s3 · hooks/runtime-gate.py, skills/usage-report/usage-report.py, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/fixtures/codex-hooks/30-agent-expert-launch.json, tests/fixtures/codex-hooks/32-subagent-stop-rate-limit.json, tests/fixtures/codex-hooks/33-subagent-stop-uncertain.json · tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh · pending
- s4 · install.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh · tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh · pending
- s5 · instructions/routing.md, ai/policies/model-routing.md, ai/policies/release.md, ai/templates/review-report.md, ai/templates/task-context.md, tests/test-instruction-budget.sh, .ai/project/known-risks.md, skills/project-update/history/index.json · tests/test-instruction-budget.sh, tests/test-project-update.sh · pending

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
