# Plan review — ai-reviewer (opus), verdict: pass, no blockers

- HIGH: case (b) too narrow — a spawn with no role and no model while default_subagent_model is EXPERT falls to (c). Fix: (b) = resolved model is EXPERT and no role file pins a model (call model or config default); inject model + reasoning_effort.
- MEDIUM: case (a) can make a working spawn fail (unknown agent_type) if the twin file exists where the gate looks but Codex has not registered it. Fix: rewrite only to a twin whose file has `name = "<role>-strong"`; walk up from payload cwd for .codex/agents, then ~/.codex/agents.
- MEDIUM: Q1 ordering on Codex launch_tier: pinned file → tier name list → call model → config default, RUNTIME == "codex" only.
- MEDIUM: validate FALLBACK_EFFORT against the reasoning_effort enum (minimal, low, medium, high, xhigh); omit it otherwise.
- LOW: backstop must pass hookEventName "SubagentStart" explicitly and send only additionalContext; test exact JSON.
- LOW: SubagentStart tier from model only when it maps to STRONG/EXPERT (FAST and BALANCED share terra).
- LOW: suffix matches mcp__x__spawn_agent — harmless, name it in a test.
- LOW: drop caller model_reasoning_effort in (a) too.
- LOW: docs/faq.md:360 stale — add to step 4.
- INFO (Codex source): role pins beat call model and effort (child_config.rs:62-73, role.rs:80-89); PostToolUse sees the rewritten input (registry.rs).
- Q1 yes (Codex only, order above); Q2 yes Codex only; Q3 Codex only; Q4 yes, also in (a); Q5 acceptable.
