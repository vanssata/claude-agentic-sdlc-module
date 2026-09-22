# Implementation plan — T-2026-09-21-001

Produced by ai-planner (opus). Tier T3, workflow bugfix, profile solo.

goal: make runtime-gate see Codex multi-agent v2 launches (`collaborationspawn_agent`) and reroute them in a way that takes effect (role twin via `agent_type`, or call-level `model` + `reasoning_effort`), journal the real fallback, backstop at SubagentStart, correct the docs.

## Current behaviour
- `codex/hooks.json:39,52` matcher `Agent|spawn_agent` is an exact list; never matches `collaborationspawn_agent`. `is_agent_event` (runtime-gate.py:627,680) rejects it too. Reroute and budgets never run on Codex.
- The rewrite sets `model` (beaten by the role's pinned model) and `model_reasoning_effort` (:735), which v2 SpawnAgentArgs rejects: the spawn fails.
- `launch_model` puts the call's `model` before the role's pinned model; Codex resolves the other way round.
- Explain mode's additionalContext claims the agent "runs on FALLBACK instead" — false.
- `subagent_start` takes the tier from the name only.
- Docs say 0.155 fires no PreToolUse for spawns, and name `agents.max_threads`.

## Desired behaviour
- Matcher `^Agent$|spawn_agent$`; `is_agent_event` accepts `agent`/`task` (exact, any case) or any name ending in `spawn_agent`.
- MODE rewrite + active EXPERT outage:
  - (a) named role pins EXPERT and `<role>-strong.toml` exists (where agent_file_model looks) pinning a non-EXPERT model → rewrite the key the call used (AGENT_NAME_KEYS) to `<role>-strong`, nothing else.
  - (b) call passes own `model`, names no pinning role → `model` = FALLBACK, `reasoning_effort` = FALLBACK_EFFORT, drop any `model_reasoning_effort`.
  - (c) otherwise explain only (no updatedInput, no permissionDecision), with the reason.
- Journal records the model the child actually gets (twin's pinned model / FALLBACK / none).
- Explain mode says "not rerouted".
- `subagent_start` on Codex: tier from payload `model` first; EXPERT model during outage → journal `missed_reroute` + additionalContext to the child.
- Role `ai-expert-strong` rendered on STRONG. Docs corrected.

## Explicitly unaffected
Claude path (claude_pre_tool_use/post/stop_failure, Agent tool, Fable reroute, settings.gate.json, Claude branches of launch_tier and subagent_start). Codex budgets stay allow-and-explain. Gate never denies. Shims ≤ 20 lines. Quota, statusline, SubagentStop classification.

## Steps
1. **Failing tests** — tests/test-runtime-gate.sh (replace :202–211 with a v2 section: fan-out explained; ai-expert → ai-expert-strong with journal to gpt-5.6-sol; call-level astra → model sol + reasoning_effort high, no model_reasoning_effort; custom pinned role without twin → explain "not rerouted"; MODE context → no updatedInput; PostToolUse marks outage; SubagentStart tier from model; missed_reroute backstop + journal, silent without outage; `Task` still an agent event; line 39 expects agent_type; case (a) not counted against expert budget), tests/test-codex-model-gate.sh (:47–52, :60–63, :106–115 per Q1, :118–122, new call-level case), tests/test-codex-install.sh (:100–106 regex semantics; :68 twin installed), tests/test-codex-agent-render.sh (ai-expert-strong on Sol/high/read-only, pro and plus), tests/test-ai-task-state.sh (event missed_reroute accepted). Payloads inline, no new fixture (golden.txt).
2. **Twin role + event** — profiles/codex-pro.json, profiles/codex-plus.json (identical role `ai-expert-strong`: variant_of ai-expert, STRONG, read-only, description_prefix "STRONG stand-in for ai-expert, launched by runtime-gate while the EXPERT model is unavailable. Do not spawn it directly.", escalation_note: answer is STRONG's, say so under residual risk, say if the question must wait for EXPERT), install.sh:1045, scripts/render-codex-agents.py docstring, skills/ai-task/state.py EVENT_TYPES += missed_reroute (not forgeable).
3. **Gate and matcher** — hooks/runtime-gate.py, codex/hooks.json: AGENT_TOOLS {agent, task} + suffix; `agent_name_key`; Codex pin-first resolution (launch_model, Codex launch_tier) per Q1; cases a/b/c; truthful context; `journal_event` extracted from journal_fallback; Codex budget reads the updatedInput already in RESPONSE; subagent_start tier from model + backstop after the lock; matcher on both gate entries.
4. **Docs** — docs/hooks.md (:308–320, :366–369, :380, :392–395, backstop + event), README.md (:459, ~434), docs/agents.md:10–11, docs/architecture.md ~298, docs/hook-performance.md ~131.

## Verification
`bash tests/run-all.sh` once after step 4, failures fixed as one batch. No separate e2e (test-end-to-end.sh is inside run-all). Manual: trusted /hooks entry + ai-expert spawn during `runtime-gate.py set 600 test`.

## Compatibility
Changed matcher entries lose their trust hash; until re-trusted Codex skips them (same as today). Twin appears only after reinstall; without it (a) falls to (c). An older installed state.py rejects missed_reroute silently. `reasoning_effort` valid in v1 and v2.

## Migration impact
None.

## Rollback
Revert and reinstall (re-trust again). Leftover ai-expert-strong.toml harmless. `AI_RUNTIME_GATE=off` / `AI_RUNTIME_GATE_MODE=context` switch immediately.

## Observability
`state.py events --type model_fallback` (to: gpt-5.6-sol); `missed_reroute` lines and "not rerouted" child context mean a launch reached EXPERT during an outage.

## Risks
- Step 1 red on purpose (bugfix rule); no push between steps 1 and 3.
- Case (a) leaves a call-level reasoning_effort; not verified the twin's pinned effort overrides it.
- PostToolUse may carry the original input: the twin's own rate limit could re-mark EXPERT (rare; v2 tool_response is the spawn ack).
- `^Agent$|spawn_agent$` valid in Oniguruma and Rust regex.
- Q1 changes documented behaviour: an explicit cheap `model` on ai-expert no longer escapes the gate.

## Open questions
- Q1 (blocking): Codex resolution pin-first in launch_model and Codex launch_tier? Recommended yes.
- Q2: Codex budgets rate the rerouted input (case a/b count as STRONG, not against expert.max_per_task)? Default yes, Codex only.
- Q3: SubagentStart tier from model on Claude too? Default Codex only.
- Q4: drop caller `model_reasoning_effort` in case (b) — decided yes.
- Q5: the reader for missed_reroute is `state.py events --type missed_reroute` + docs/hooks.md.

Out of scope, noted: docs/agents.md:10 omits ai-reviewer-balanced from the Codex-only variants.

## Amendments after plan review (see plan-review.md)
- (b) widened: resolved model (call `model` or `default_subagent_model`) is EXPERT and no role file pins a model → inject `model` + `reasoning_effort`.
- (a) only when the twin file carries `name = "<role>-strong"`; lookup walks up from the payload `cwd` through `.codex/agents`, then `~/.codex/agents`.
- Codex launch_tier order: pinned file → tier name list → call model → config default.
- `reasoning_effort` emitted only when FALLBACK_EFFORT ∈ {minimal, low, medium, high, xhigh}.
- `model_reasoning_effort` dropped from updatedInput in (a) and (b).
- SubagentStart: tier from `model` only when it maps to STRONG/EXPERT; backstop output `{"hookSpecificOutput":{"hookEventName":"SubagentStart","additionalContext":…}}` exactly; tested.
- Test: `mcp__x__spawn_agent` is matched (documented, harmless).
- Step 4 adds docs/faq.md.
