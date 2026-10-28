<!-- riskrails:rule:hooks:start -->
# Hooks rules
- Weigh a change by what it does to a user project's decisions, never by the hook being a process every call runs through (constitution C6). The mode is what W gives (`state.py weight`); the rows below set the behaviour axis.
- behaviour 0: no guard decision moves, golden byte-identical. behaviour 1: adds a deny or changes a deny's text, golden re-recorded. behaviour 2: allows what was denied or weakens a refusal — declare it, `--declare behaviour=2:"<the effect>"`. Start such a task with `start --mode full --by <name>`: its weight lands in guarded, and these effects keep a STRONG review and the gate.
- The guards defend against an agent's mistakes, not a constructed command: such a finding is accepted in `known-risks.md` under the threat model in `.ai/policies/safety.md`.
<!-- riskrails:rule:hooks:end -->
