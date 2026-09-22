# Review ledger — manager probe (runtime-gate.py, Codex side), outage active

| Input | Outcome |
|---|---|
| name under key `agent` (not agent_type) | the same key is rewritten to ai-expert-strong — ok |
| project `.codex/agents/ai-expert.toml` pinning sol, cwd a subdirectory | silent (walk-up found the override) — ok |
| v1 `spawn_agent`, `fork_context` + model astra | (b): model sol, reasoning_effort high — ok |
| agent_type `../x` + model astra | name refused by the file lookup, treated as unpinned → (b) — ok (Codex rejects the name anyway) |
| ai-expert with non-string `model: 5` | (a) twin; `model` passed through untouched — acceptable (Codex's own parse decides) |
| `collaborationwait_agent` | not an agent event, silent — ok |
| twin file present but pinning EXPERT | (c) not rerouted; wording said "no twin" → fixed to "no usable twin: …" |
| caller `reasoning_effort: xhigh` with call-level astra | replaced by the STRONG effort — ok |
