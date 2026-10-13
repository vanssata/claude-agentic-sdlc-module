# Task context: T-2026-10-13-001

task: simplify the plugin along six points + small items (see state goal); source of ideas: addyosmani/agent-skills (thin commands, fat skills, no per-project copies, skill anatomy, lint + trigger evals, one shared definition of done, one orchestration rule).
affected_modules: skills/ai-init, skills/project-update, skills/ai-task (SKILL.md only), skills/ai-status, profiles/, scripts/, hooks/runtime-gate.py, install.sh, instructions/, agents/*.tmpl, .ai/ (this repo's own tree), docs/, README.md, tests/.
entry_points: install.sh (plan detection :208-281, profile :180-200, Codex :843-1056); scaffold-ai.sh:75-84 (copies templates/.ai/** into the project); update.py three_way :574-628, block_update :652-684; render-codex-agents.py :84-87 (tiers from profile); runtime-gate.py profile() :861, budget_pre_tool_use :1081; state.py cmd_profile :539, direct_mode_cap :563, preferred_runtime :509.
execution_flow: install.sh → resolve-profile.py → profile.json + rendered agents (model: pinned) + routing.md + CLAUDE.md block; /ai-init → scaffold-ai.sh copies .ai/** ; /project-update → update.py three-way merge against history/blobs; /ai-task reads .ai/policies/* (prose) and state.py reads risk-tiers.json, testing.md, profile.json.
relevant_files: see discovery-A/B/C.md (file:line facts).
interfaces: profile.json keys read by state.py (tiers, budgets.direct_mode, preferred_runtime, label, plan), runtime-gate.py (tiers, budgets, label), usage-report.py:585, ai-status; risk-tiers.json pipeline_profile (state.py:569, sensors.py:363, SKILL jq); path-guard.json (ai-path-guard.sh:44, optional); testing.md commands (sensors.py:536, state.py); the managed-block markers (update.py:66); migrations registry (contiguous, VERSION = highest).
dependencies: jq, python3, git; no node (a lint/eval must be python or bash).
legacy_constraints:
- tests pin prose: test-instruction-budget.sh (required phrases, byte budgets, router template must not contain 'ADVERSARIAL REVIEW', ai-task/SKILL.md must; every backticked path in the router must exist), test-shared-prompts-model-free.sh (no model names in skills/agents/instructions/templates), test-ai-status-root.sh (bash block shape), test-guard-characterization.sh (deny texts), test-install-dry-run.sh:170-176 (SKILL.md list), test-profiles.sh, test-ai-task-state.sh:1161-1243 (profiles via resolve-profile.py).
- hooks fail open; ai-path-guard.sh unions project path-guard.json with plugin defaults.
- .github/workflows/** is a T5 path scope: not touched by this task.
- the global block budget is 2560 B; the project block 2048 B.
business_rules: no AI attribution anywhere; no agent commits; vendor/ untouched; the guards (git/path/scope) stay as they are.
tests: verify_command bash tests/run-all.sh (~5 min); e2e bash tests/test-end-to-end.sh; lint pylint; baseline run in progress (scratchpad/baseline-tests.log).
known_risks:
- policy files mix shared prose with project values (testing.md commands, risk-tiers.json pipeline_profile, coding.md specifics) — a naive move strands them.
- budgets/fan-out/EXPERT limits are enforced only by runtime-gate budget_pre_tool_use; dropping profile budgets drops that enforcement.
- render-codex-agents.py needs a Codex tier/role source; dropping config.toml merge leaves the Codex session model unset unless documented.
- review-economy.md live (179) and template (136) have drifted; root CLAUDE.md is hand-written.
unknowns: whether state.py/sensors.py read review-economy text; how install_skills registers skills (directory discovery assumed); wp6 OQ6 status.
open_questions: Q1 plan profiles shape; Q2 which .ai/ files stay project-owned; Q3 existing projects' copies; Q4 Codex config.toml — asked via state.py ask.
