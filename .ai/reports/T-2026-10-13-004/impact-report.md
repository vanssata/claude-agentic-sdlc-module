# Impact report: T-2026-10-13-004

Subset of T-2026-10-13-001/impact-report.md limited to point 1 + history.

## Direct callers
- skills/ai-init/scaffold-ai.sh:75-84 copies templates/.ai/** → narrows to project-owned files.
- skills/project-update/update.py: three_way (:574), block_update (:652), History (:152, :858), template walk (:902, :922) → shared keys stop being merged; migration 0006 added under skills/project-update/migrations/.
- install.sh → must install the shared tree to $AI_HOME/claude-agentic/ai/ (Claude and Codex homes).
- Prose: skills/{ai-task,ai-status,ai-init,project-update}/SKILL.md, agents/*.tmpl "Read first" lines, instructions/stub.md (+ rendered *.block.md), templates/.ai/AGENTS.md, routing.md.
- This repo's own .ai/ (it is also a project): its shared copies become overrides or are deleted by 0006.

## Data touched
- Existing users' project .ai/ trees: unedited shared copies deleted (gated), VERSION 5 → 6.
- skills/project-update/history/blobs/* removed (index.json fate open).

## Contracts affected
- /project-update output and exit codes for shared keys; --check reports schema 5 → 6.
- Agents and skills read shared files from the plugin path; a project copy overrides.
- Code readers unchanged: sensors.py, state.py, ai-path-guard.sh read only project-owned files.

## Blast radius if wrong
- A wrong path in prose: agents silently read nothing (soft). Wrong deletion: user policy edits lost (guarded by identical-to-shipped hash check and --confirm-delete).
- test-project-update.sh, test-scaffold-idempotency.sh, test-end-to-end.sh, test-instruction-budget.sh, test-install-dry-run.sh must change or stay green.

## Explicitly unaffected
- Guards' code and deny texts (test-guard-characterization.sh byte-identical), state.py, sensors.py, runtime-gate.py, plan profiles (task B), ai-task split (task C), .github/workflows/**.
