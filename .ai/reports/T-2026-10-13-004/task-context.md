# Task context: T-2026-10-13-004 (task A of T-2026-10-13-001, Q5=A)

task: shared .ai/ files (policies except the four project-owned ones, agents/, workflows/, templates/) ship in the plugin under $AI_HOME/claude-agentic/ai/ and are read from there; a project copy, when present, is an override (Q2=A). Migration 0006 deletes project copies identical to a shipped version behind --confirm-delete and reports edited ones as overrides (Q3=A). skills/project-update/history/blobs removed. /ai-init copies only project-owned files.
project_owned (stay in project, Q2=A): .ai/policies/{risk-tiers.json,risk-tiers.md?,path-guard.json,testing.md,coding.md}, .ai/project/**, .ai/rules/**, .ai/state/**, .ai/reports/**, .ai/VERSION.
facts: discovery-A.md, discovery-B.md (§5), discovery-C.md and impact-report.md of T-2026-10-13-001 (same day, HEAD differs only by tier-model v2 + fixture commits).
key facts re-checked at HEAD:
- update.py:58 HISTORY dir; :152 class History; :574 three_way uses history.versions(key) as merge base and "equals a shipped version → replace"; :652 block_update uses history for the managed block; :902 project-init docs/sdlc templates go through three_way; :922 every ai-init template goes through three_way; :858 History built with migration renames.
- history/ = index.json + 198 blobs (1.1 MB).
- prose readers of .ai/policies|agents|workflows|templates paths: ai-task, ai-status, ai-init, project-update SKILL.md; agents/*.tmpl "Read first" lines; instructions/stub.md block; templates/.ai/AGENTS.md router.
- code readers (stay project-relative, files stay project-owned): sensors.py risk-tiers.json/testing.md; state.py risk-tiers.json/testing.md; ai-path-guard.sh path-guard.json.
legacy_constraints: as T-2026-10-13-001 task-context.md (prose-pinning tests: test-instruction-budget.sh router paths must exist, ai-task must contain ADVERSARIAL REVIEW; test-project-update.sh scaffolds oldest templates from blobs and fails on stale history; test-scaffold-idempotency.sh; test-end-to-end.sh needs scaffold templates).
open: what replaces history blobs as merge base for files still merged (project-owned policies, managed block, docs/sdlc TEMPLATE.md); whether .ai/AGENTS.md router stays in project; how subagents resolve the plugin path (absolute path rendered at install vs $AI_HOME prose).
