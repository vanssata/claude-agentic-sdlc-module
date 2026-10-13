# Discovery B — ai-task, plan profiles, gates, Codex adapter (T-2026-10-13-001)

## 0. Two "profile" concepts
- KNOWN FACT: (a) plan profiles = profiles/*.json (7), resolved into `<home>/claude-agentic/profile.json`; (b) pipeline profile = `pipeline_profile` solo|team in .ai/policies/risk-tiers.json:4 (solo :7, team :85). `team-pro`/`team-max` in install.sh --plan are Claude plan names (install.sh:3,259-273).
- INFERENCE: "collapse the 7 profiles into solo and team" mixes (a) and (b); needs a human decision.

## 1. skills/ai-task/SKILL.md
- KNOWN FACT: frontmatter :1-5; preamble AI_HOME/STATE :16-26; `## 0. Resume or start` :31-114 (resume/abandon/init :32-75; workflow :76; preferred runtime :79-84; pipeline_profile jq :86-90; direct vs sdlc :92-110; tier-first :112-113); `## 1a` :115-192 (steps 1-6 at :119,:137,:147,:153,:174,:183; closing :189-192); `## 1` :193-520 (TRIAGE :226, PLAN :265, PLAN REVIEW :291, IMPLEMENTATION :308, TEST :355 (batch :384, e2e :399), ADVERSARIAL :411, SECURITY :463, RELEASE :473, HUMAN APPROVAL :482-520); Questions :521-584; Keeping context small :585-606; Rules :607-end.
- KNOWN FACT: `$STATE profile --tier` at :101,:175-177,:241,:274,:437. team-only text at :231,:237,:267,:274,:291,:479.
- RISK: section 1 interleaves solo and team text (:228-237,:267-274,:475-479); a split rewrites those lines.
- KNOWN FACT: dependants on the skill: ai-status/SKILL.md:112-138 (profile --tier, pipeline_profile); ai-init/SKILL.md and workflows mention pipeline_profile. UNKNOWN: how install_skills registers skills (.codex-plugin/plugin.json:8 `skills: ./skills/` suggests directory discovery).

## 2. Plan profiles
- KNOWN FACT: Claude files = settings.json fragment (model, availableModels, fallbackModel, effortLevel, modelSettings, autoCompactWindow; max.json:2-13) + `claude_agentic` {inherits, plan, label, runtime, tiers.{FAST,BALANCED,STRONG,EXPERT}={model,effort,agents[]} + EXPERT.architect_model_with_fable (max.json:19-59), budgets{fan_out, direct_mode.max_tier, expert, tokens}, preferred_runtime{default, by_workflow, quota_pct, cross_vendor_review_from}}.
- KNOWN FACT: Codex files = session{model, effort}, agents{enabled, max_concurrent_threads_per_session, default_subagent_model, default_subagent_reasoning_effort}, tiers, labels, roles (tier, source, variant_of, sandbox_mode, effort, description_prefix, escalation_note), plan, plan_rule (codex-plus.json:3-139) + claude_agentic without tiers.
- KNOWN FACT: pro vs max: session opusplan vs claude-opus-5-5[1m]; autoCompactWindow 300000 vs 800000; EXPERT high vs xhigh + architect fable[1m]; fan-out 1/1/serial vs 3/2. max20 inherits max, overrides budgets only. balanced-max inherits max, 200k model, EXPERT high. codex-plus/pro/balanced-max differ in session effort, threads, EXPERT effort, FAST (luna on balanced-max :15), fan-out.
- KNOWN FACT: readers: scripts/resolve-profile.py (:1-125; inherits :40-66, Codex tier synthesis from roles :69-76,:84-85, --fable :90-93); install.sh (agentic_profile :180-188, write_profile :189-200, plan detection :208-281, settings render :283-295, PLAN_SPECIFIC :337-372, gate registration :374-388, RENDER_* :390-411, Codex profile :882-903, write_profile at :731/:1054, dry-run :506/:944); hooks/runtime-gate.py :133-150,:861-867; state.py read_profile :480-489, cmd_profile :539-560; usage-report.py:585; ai-status/SKILL.md:112-121.
- KNOWN FACT: agent template placeholders: {{FAST_MODEL}},{{BALANCED_MODEL}},{{STRONG_MODEL}},{{EXPERT_MODEL_LINE}},{{ARCHITECT_MODEL_LINE}}, {{*_EFFORT}}; ai-release/implementer/discovery/context have model line only. instructions/runtimes.json holds no tiers (text vars + _budgets). Claude agents installed with `model:` pinned (install.sh:329-336); Codex agents TOML from profile tiers+roles (render-codex-agents.py:82-87).
- RISK: a single frontmatter cannot express per-plan variation (Pro EXPERT high vs Max xhigh; architect fable only on max+Fable; Codex FAST luna vs terra); budgets/fan-out/direct_mode.max_tier have no frontmatter equivalent.

## 3. hooks/runtime-gate.py (1266 lines)
- KNOWN FACT: handlers :1156-1162 — claude: PreToolUse (:396 + budget :1081), PostToolUse :428, StopFailure :453, SubagentStart :992, SubagentStop :1040; codex: PreToolUse, PostToolUse :812, SubagentStart :1032, SubagentStop :1147. CLI: status, quota, clear, set, statusline (:1165-1216). Runtime by script location :191-196; shims pass --as (:1238). No SessionStart.
- KNOWN FACT: reads `<home>/state/runtime-gate.json` (:163), legacy state (:211-229), profile.json (:861-867), .ai/state/current.json (:910-924), agent frontmatter model (:321-366), .codex/agents/*.toml (:652-691), ~/.codex/config.toml default_subagent_model (:694-701), Claude transcripts (:300-348), Codex rollout (:532-583). Writes unavailable, last_expert_launch, quota, running_agents, pending_launches, expert_launches (:272-294,:511-529,:1099-1133); journals model_fallback/missed_reroute via state.py event (:946-965). Fails open (:1257-1259).
- KNOWN FACT: profile-driven: profile_tier :133 → Codex EXPERT/FALLBACK defaults :178-181; profile_fable :143 → statusline :490; profile()/model_tier/launch_tier :861-886; budget_pre_tool_use :1081-1135 (fan_out, expert.max_per_task; active only when profile has budgets :1089-1091). Fallback: Claude fable→opus :396-425,:428-440,:453-469,:484-495; Codex EXPERT→-strong twin :755-809,:812-839,:1015-1029 (strong_twin :681 refuses without twin). Quota :498-616 independent.
- RISK: budget_pre_tool_use is the only enforcer of fan_out / expert.max_per_task. Codex -strong twins come from the roles table (codex-plus.json:104-131).
- KNOWN FACT: fable-gate.py / codex-model-gate.py are execv shims (:11, :12-16). settings.gate.json registers PreToolUse/PostToolUse Agent, SubagentStart/Stop, StopFailure rate_limit|model_not_found (:4-62); install.sh drops StopFailure unless max+Fable (:378-384). codex/hooks.json: 3 guards + runtime-gate (^Agent$|spawn_agent$) + context-guard.

## 4. Codex adapter
- KNOWN FACT: merge-codex-config.py manages six keys: model, model_reasoning_effort (:33), agents.enabled, agents.default_subagent_model, agents.default_subagent_reasoning_effort, agents.max_concurrent_threads_per_session (:34-39); docstring says five (:10). Values from profile session.*/agents.* (:128-132).
- KNOWN FACT: render-codex-agents.py: --src agents/<source>.md.tmpl, --profile (default codex-pro.json :134), --out; one <role>.toml per roles entry (:143-150); model/effort from profile.tiers[tier] (:84-87), role effort overrides; unrendered placeholders die (:110).
- RISK: render-only still needs a Codex tiers/roles source; (3) and (4) interact.
- KNOWN FACT: install.sh Codex: detection :83-127 (:103); codex_detect_plan :818-830; codex_render :843-928 (profile :881-883, agents :904, RENDER_* :906-933); codex_dry_run :935-964 (merge :938); codex_apply :975-1056 (agents :978-981, hooks :983-998, skills :1000-1001, hooks.json merge :1003-1045 with legacy sed :1016-1020, config.toml merge :1048, AGENTS.md/routing/profile :1050-1054); codex_summary :1059; run :1090. .codex-plugin/plugin.json metadata only.
- RISK: dropping the config.toml keys removes session model/effort and agents.*; runtime-gate reads default_subagent_model (:694-701). install.sh:1016 and routing.md:107 still name codex-model-gate.

## 5. state.py profile / handoff
- KNOWN FACT: cmd_profile :539-560 dies without profile.json (:542-544). preferred_runtime :509-525 (+quota :492-506, advice :528-536). direct_mode_cap :563-575 reads budgets.direct_mode.max_tier + pipeline_profile, exit 8 only for solo above cap. handoff --for review :2189-2198 reads cross_vendor_review_from (default T4); handoff --to needs other runtime installed (:2176-2178, installed() :476).
- INFERENCE: without profile.json, `profile --tier/--field` dies → SKILL.md :101,:175-177,:241,:274,:437 and ai-status :112-113 break; handoff survives.
- RISK: test-ai-task-state.sh:1161-1243 resolves real profiles via resolve-profile.py (:1165-1167).

## 6. Tests
- test-profiles.sh: claude_agentic shape (:12), resolver overrides (:41), budget rules (:58), agent template tiers (:90). test-runtime-gate.sh: runtime from home (:27), shims (:42), env names (:48), legacy import (:63), quota (:75,:110), EXPERT budget (:142), fan-out (:177), Codex v2 spawn (:202). test-fable-gate.sh: fable→opus, StopFailure, statusline, fail-open, registration only on Fable install. test-codex-model-gate.sh: EXPERT→STRONG only on capacity signals. test-codex-install.sh: managed routing keys only, guards no dup, one AGENTS.md block, idempotent (:39,:51,:82,:90). test-codex-agent-render.sh: valid TOML, role→tier model. test-dual-runtime-install.sh: --target auto|claude|codex|both. test-merge-migration.sh: claude-routing absorption, agents declare tier (:76). test-install-dry-run.sh: every plan/fable combo, agent model per plan (:115). test-ai-task-state.sh WP5 :1161-1243. test-shared-prompts-model-free.sh: no model names in shared prompts (:29,:38).

## 7. Always-loaded block
- KNOWN FACT: instructions/stub.md is the one source; placeholders from runtimes.json then RENDER_* (stub.md:12; render_instructions.py:180). routing.md long form (Claude :3-40, Codex :52-118), written to <home>/claude-agentic/routing.md. render_instructions.py: render, build [--check], measure, constitution (:13-18); SOURCE_FILES :35-36. install.sh render_stub :147-151, block_size :155-169; Claude block :726; Codex :1050-1051; project files via hooks/project-scaffold.sh :97-113.
- KNOWN FACT: budgets runtimes.json:42-47: global 2560 B, project 2048, skeleton 2048; pinned by test-instruction-budget.sh (:98-101,:117,:255,:88).

## Open questions
- Plan profiles (a) or pipeline profile (b)? What replaces budgets, preferred_runtime, direct_mode.max_tier?
- Without config.toml managed keys, where do Codex session model/effort and agents.default_subagent_model come from?
- Tier→model source for render-codex-agents.py once profiles collapse? Do the -strong/-balanced twins stay?
- Does a second skill need registration in install_skills / manifests?
