<!-- claude-agentic:rule:skills:start -->
# Skills rules
- Weigh a change by what it does to a user project's decisions, never by the skill being a process (constitution C6). The mode is what W gives (`state.py weight`); the rows below set the behaviour axis.
- behaviour 0: skill or agent text, `usage-report`, no `state.py` refusal moves. behaviour 1: adds a `state.py` check, a sensor or a refusal. behaviour 2: weakens a refusal, changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, the review verdict transitions) or changes install and migration (the `project-update` merge; a migration also raises reversibility through its hint) — declare it, `--declare behaviour=2:"<the effect>"`. Start such a task with `start --mode full --by <name>`: its weight lands in guarded, and these effects keep a STRONG review and the gate.
- A change to a shipped template or to `ai/` runs `tools/build-template-history.py` in the same task, or `tests/test-project-update.sh` goes red.
<!-- claude-agentic:rule:skills:end -->
