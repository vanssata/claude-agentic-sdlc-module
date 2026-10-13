# Impact report: T-2026-10-13-001

## Direct callers
- install.sh → scripts/resolve-profile.py (:286, :882), scripts/merge-codex-config.py (:938, :1048), scripts/render-codex-agents.py (:904), render_instructions (import), agents/*.tmpl placeholders, profiles/*.json, settings.gate.json.
- hooks/runtime-gate.py → <home>/claude-agentic/profile.json (tiers, budgets, label, plan); ~/.codex/config.toml default_subagent_model.
- skills/ai-task/state.py → profile.json (cmd_profile, direct_mode_cap, preferred_runtime, handoff --for review); .ai/policies/risk-tiers.json; testing.md.
- skills/ai-task/sensors.py → risk-tiers.json, testing.md (project-relative; unchanged by this task).
- skills/ai-status, skills/usage-report → profile.json (--tier, label, budgets display).
- skills/ai-init/scaffold-ai.sh → templates/.ai/** (copies everything).
- skills/project-update/update.py → history/blobs, migrations, templates, managed block.
- agents/*.tmpl, skills/*/SKILL.md prose → `.ai/policies/*`, `.ai/agents/*`, `.ai/workflows/*`, `.ai/templates/*` paths.
- tests: 25 suites, the prose-pinning ones listed in task-context.md.

## Data touched
- <home>/claude-agentic/profile.json shape (keys removed: budgets, preferred_runtime, inherits, settings fragment).
- Project `.ai/` trees of existing users: shared files become deletable (migration 0006, --confirm-delete).
- `.ai/VERSION` 5 → 6.
- skills/project-update/history/* (188 blobs + index) removed.

## Contracts affected
- `state.py profile --tier X` and `--field label` keep working (tiers/label stay in profile.json). `--field budgets.*` and `preferred_runtime.*` disappear; direct-mode cap (exit 8) and `preferred runtime:` advice disappear; `handoff --for review` keeps the default T4 threshold without the profile key.
- runtime-gate.py: budget enforcement (fan-out, EXPERT per task) removed; fable→opus and Codex EXPERT→STRONG fallbacks, quota and statusline stay.
- Codex: config.toml never written by install; the six keys are printed and documented.
- /ai-init: copies only project-specific files; /project-update: migration 0006 deletes unedited shared copies, reports edited ones as overrides.
- Skill set: `/ai-task` (direct, T0–T3 + triage) and a new `/ai-sdlc` (T4/T5 and team), both installed; install.sh skill list and test-install-dry-run.sh:170-176 updated.
- Backward compatible for a project: a project copy of a shared file is read as an override, so nothing a user edited is lost.

## Other environments
- Codex runtime: render-codex-agents.py reads tiers/roles from profiles/codex.json (same keys as before, one file). Gemini/Junie instruction files: unchanged.
- Pro vs Max plans: the tier table keeps per-plan model/effort; the Fable architect line stays a `--fable` option.

## Blast radius if wrong
- A wrong path in a skill or agent prompt makes an agent read nothing (prose, soft failure). A wrong path in sensors/state/hook code breaks `/ai-task` in every project — covered by test-end-to-end.sh and test-ai-task-state.sh.
- A migration that deletes an edited copy loses user policy edits — guarded by the identical-to-shipped check and --confirm-delete.

## Explicitly unaffected
- The three guards (ai-git-guard, ai-path-guard, ai-scope-guard), cap-large-read, context-guard, project-scaffold: not edited; test-guard-characterization.sh must stay byte-identical.
- state.py commands other than profile/direct_mode_cap/preferred_runtime; sensors.py; usage-report.py (only the budget display line).
- .github/workflows/** (T5 scope): not touched.
- Guard deny texts, risk tier semantics, stage list.

## Risk tier
T4 — the change alters the enforcement/installation layer used by every project (install.sh, runtime-gate.py, ai-init/project-update) and removes capabilities; reversible with git revert, so not T5.
