# Questions — T-2026-10-13-001
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Point 3, plan profiles: the 7 profiles/*.json also carry budgets (fan-out, EXPERT per task, direct-mode cap, tokens) and preferred_runtime, which have no frontmatter equivalent and which runtime-gate.py enforces. What replaces them?
asked: 2026-10-13T12:53:14Z · stage: context
context: profiles/max.json:19-59, hooks/runtime-gate.py:1081-1135, skills/ai-task/state.py:563-575
A. Two files, profiles/claude.json and profiles/codex.json: a per-plan tier table (model + effort per tier) plus the Codex roles; profile.json keeps runtime, plan, label, tiers, roles. budgets, preferred_runtime, direct-mode cap and the inherits mechanism are removed; the fan-out and EXPERT limits stay as prose in routing.md; resolve-profile.py and the budget code in runtime-gate.py go. (recommended)
B. Keep the 7 files and resolve-profile.py; skip point 3 entirely.
C. Keep budgets and their enforcement; only drop the inherits variants (max20, balanced-max, codex-balanced-max) and fold their differences into a flag.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T13:14:24Z

## Q2. Point 1, which .ai/ files stay in the project when shared policies move to the plugin root?
asked: 2026-10-13T12:53:14Z · stage: context
context: skills/ai-init/scaffold-ai.sh:75-84, skills/project-update/update.py:918-922, sensors.py:363,:536, hooks/ai-path-guard.sh:44
A. risk-tiers.json, path-guard.json, testing.md and coding.md stay in the project (they hold project values); every other policy, agent contract, workflow and template ships in the plugin under $AI_HOME/claude-agentic/ai/, and a project copy of one of those, when present, is read as an override. (recommended)
B. Only project/, rules/, state/ and reports/ stay; the project values (test commands, pipeline_profile, path-guard additions) move into one new .ai/project.json and testing.md/coding.md/risk-tiers.json ship in the plugin too.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T13:14:24Z

## Q3. Point 1, existing projects that already hold copies of the moved files: what does /project-update do with them?
asked: 2026-10-13T12:53:14Z · stage: context
context: skills/project-update/update.py:574-628,:874-886; migrations/__init__.py:22-30
A. Migration 0006: a copy identical to any shipped version is deleted (behind the existing --confirm-delete gate); an edited copy stays and is reported as an override. (recommended)
B. Leave every copy in place and simply stop managing it; the user deletes by hand.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T13:14:24Z

## Q4. Point 4, Codex config.toml: merge-codex-config.py manages six keys (model, model_reasoning_effort, agents.*). Without it, where do they come from?
asked: 2026-10-13T12:53:14Z · stage: context
context: scripts/merge-codex-config.py:33-39, hooks/runtime-gate.py:694-701, install.sh:1048
A. install.sh prints the six lines for the user to paste and docs/codex-setup.md documents them; install never writes config.toml. runtime-gate.py keeps reading agents.default_subagent_model and falls back to the profile tier when the key is absent. (recommended)
B. Keep merge-codex-config.py; apply only the rest of point 4.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T13:16:27Z

## Q5. The T5 diff budget is 400 lines / 15 files per task and 150 / 6 per step (risk-tiers.json diff_budget), and step-done refuses a step over it. This work package removes ~6000 lines and 190+ files; no split into steps fits. How do we proceed?
asked: 2026-10-13T13:17:37Z · stage: impact_analysis
context: .ai/policies/risk-tiers.json diff_budget; skills/ai-task/state.py:943
A. Split into three tasks run one after another — A (T5): policies from the plugin root, migration 0006, history/blobs removal, ai-init copies only project files; B (T4): profiles collapse, runtime-gate without budgets, Codex render-only; C (T3): ai-task split, canonical rules, definition of done, skill anatomy, lint + trigger eval, README/docs archive — and calibrate this repository's diff_budget for a plugin repo (exclude skills/project-update/history/** and tests/fixtures/** from the count; per_task T3-T5 3000 lines / 80 files, per_step 800 / 25). This task becomes task A. (recommended)
B. One task, as scoped; calibrate the budget to 8000 lines / 300 files per task, 1500 / 60 per step.
C. Keep the budgets; the task is rescoped to what fits (point 1 only, in several tasks), the rest is dropped.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T13:23:11Z
