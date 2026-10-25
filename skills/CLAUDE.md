<!-- claude-agentic:rule:skills:start -->
# Skills rules
- Tier by what the change does to a user project's decisions, never by the skill being a process (constitution C6).
- T2: skill or agent text, `usage-report`, no `state.py` refusal moves. T3: adds a `state.py` check, a sensor or a refusal. T4: weakens a refusal, changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, `review_status` transitions) or changes install and migration (the `project-update` merge).
- A change to a shipped template or to `ai/` runs `tools/build-template-history.py` in the same task, or `tests/test-project-update.sh` goes red.
<!-- claude-agentic:rule:skills:end -->
