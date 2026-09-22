# T-2026-09-21-001 — Codex multi-agent v2 gate fix

Workflow: bugfix. Tier: T3 (shared routing behaviour: every Codex agent spawn passes the gate). Design approved by the human 2026-09-22, with the SubagentStart backstop.

## Findings (verified live, codex-cli 0.155.1; Codex source rust-v0.155.1 and main 23ae65b)
- v2 spawn_agent is in the `collaboration` namespace; hooks see tool_name `collaborationspawn_agent`. PreToolUse and PostToolUse fire for it.
- A matcher of only [A-Za-z0-9_|] is an exact list: `Agent|spawn_agent` (codex/hooks.json:39,52) never matches.
- PreToolUse updatedInput is applied. A call-level `model` is overridden by the role .toml's pinned model (child_config.rs prepare_agent_spawn_config). Rewriting `agent_type` does reroute (tested live).
- v2 SpawnAgentArgs is deny_unknown_fields: `model_reasoning_effort` fails the spawn; the key is `reasoning_effort` (v1 and v2).
- SubagentStart output accepts only additionalContext (goes to the child); continue:false / exit 2 ignored. Payload has resolved `model` and the parent's session_id.

## Context (entry points)
- hooks/runtime-gate.py: AGENT_TOOLS / is_agent_event (627, 680); codex_pre_tool_use (707–738, writes `model_reasoning_effort` at 735); launch_model / agent_file_model / agent_name; launch_tier (815) / model_tier (799); journal_fallback (860); subagent_start (903); budget_pre_tool_use (962, uses is_agent_event on Codex); pre_tool_use (1017) merges via respond (775). FALLBACK / FALLBACK_EFFORT = STRONG tier on Codex (173–174); MODE gates rewrite vs explain.
- scripts/render-codex-agents.py renders roles from profiles/codex-{pro,plus}.json; `-strong` twins are `variant_of` roles (ai-risk-strong, ai-planner-strong). ai-expert is the only EXPERT role.
- install.sh:1045 summary line lists STRONG roles.
- codex/hooks.json gate matchers (39, 52); tests/test-codex-install.sh:100–106 asserts matcher split("|") contains spawn_agent.
- tests/test-runtime-gate.sh:202–211 stale "if Codex ever delivers one" block; tests/test-codex-agent-render.sh; tests/test-profiles.sh may count roles.
- docs/hooks.md ~309–319, 369 and README.md:459 wrongly say 0.155 fires no PreToolUse for spawn_agent.

## Must stay unaffected
- Claude Code path (claude_pre_tool_use, `Agent` tool, fable reroute).
- Budgets remain allow-and-explain on Codex (Codex cannot ask).
- MODE explain: no updatedInput.

## Verification
bash tests/run-all.sh (no fail-fast; prints FAILED list). No separate e2e suite beyond tests/test-end-to-end.sh inside run-all.
- 2026-09-22: plan approved by Ivan Kakurov (Q1 yes; Q2–Q5 defaults). Installed state.py has no approve-plan; recorded here.

## Verification (2026-09-22)
- `bash tests/run-all.sh`: every suite passes except test-context-guard.sh (142/143): "no snapshot and no transcript: silent". Reproduced on a clean worktree of HEAD a9f1a1a → existing failure, out of scope, not fixed.
- e2e: tests/test-end-to-end.sh 41/41 (inside run-all).
- pylint hooks/runtime-gate.py: 10.00/10.

## Release report (short form, T3)
**Changed**
- codex/hooks.json: gate PreToolUse/PostToolUse matcher `^Agent$|spawn_agent$` (regex; the old exact list never matched `collaborationspawn_agent`).
- hooks/runtime-gate.py: agent events = agent/task or any name ending in `spawn_agent`; Codex resolution in Codex's order (role pin > call model > default_subagent_model), project agent files looked up from the payload cwd to the git root; reroute (a) `agent_type` → `<role>-strong` twin (only one Codex would register, pinning below EXPERT), (b) unpinned launch → `model` + `reasoning_effort` (validated; `model_reasoning_effort` dropped), (c) otherwise explained as "not rerouted"; journal `to` = the model the child gets; Codex budgets rate the rerouted input; SubagentStart rates STRONG/EXPERT by the resolved model and, during an outage in rewrite mode, journals `missed_reroute` and tells the child (the only field SubagentStart accepts).
- profiles/codex-{pro,plus}.json + install.sh summary + renderer docstring: role `ai-expert-strong` (variant of ai-expert, STRONG, read-only).
- skills/ai-task/state.py: event type `missed_reroute`.
- Tests: test-runtime-gate.sh (v2 section replaces the stale "if Codex ever delivers one" block), test-codex-model-gate.sh, test-codex-install.sh, test-codex-agent-render.sh, test-ai-task-state.sh.
- Docs: docs/hooks.md (0.155 section corrected, reroute a/b/c, backstop, re-trust, max_concurrent_threads_per_session), README.md, docs/{agents,architecture,faq,hook-performance}.md.

**Deliberately preserved**: the Claude Code path (Fable reroute, Agent tool, Claude launch_tier/subagent_start), the gate never denies and fails open, Codex budgets explain and never ask, shims unchanged.

**Verification**: `bash tests/run-all.sh` — 23 suites pass; test-context-guard.sh 142/143 fails "no snapshot and no transcript: silent", reproduced on a clean worktree of HEAD (existing, out of scope). e2e: test-end-to-end.sh 41/41. pylint runtime-gate.py 10.00/10.

**Review**: plan review opus pass (1 HIGH + 3 MEDIUM folded into the plan); diff review opus pass (1 MEDIUM + 3 LOW fixed in R1).

**Rollback**: `git revert <commit>` and reinstall; re-trust the reverted entries in Codex /hooks. Immediate switch without code: `AI_RUNTIME_GATE=off` or `AI_RUNTIME_GATE_MODE=context`.

**Manual checks for the human**: reinstall (`install.sh --target codex`), re-trust the two changed runtime-gate entries in Codex `/hooks`, then `~/.codex/hooks/runtime-gate.py set 600 test` and spawn `ai-expert`: the child should run on gpt-5.6-sol as ai-expert-strong; `runtime-gate.py clear` afterwards.

**Open risks**: children that inherit the session model are caught only by the backstop; the existing context-guard failure.
