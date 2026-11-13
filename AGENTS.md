# claude-agentic

<!-- Project instructions for Codex. Keep it short: only what the agent cannot infer from the code. -->

## Commands

<!-- Build, test, lint, run. One line each. -->

## Verification

<!-- The one command that proves the project is healthy. Run it before reporting any task done, and show the output. -->

## Conventions

<!-- Naming, layering, error handling, commit style. Things a reviewer would flag. -->

## Architecture

<!-- Five sentences: entry points, main modules, where state lives, how requests flow. -->

## Things Codex gets wrong

<!-- Recurring mistakes and their corrections. Grow this list from code review. -->

<!-- riskrails:start -->
## AI agent workflow

This repository runs an agentic pipeline under `.ai/`. Read `.ai/AGENTS.md` first: it routes to the policies, workflows and rules, which load on demand; `.ai/policies/` is binding.

- Production behaviour is the source of truth: document problems outside the task, do not fix them.

- A change runs through `/rr-build <request>`; `/rr-status` shows where it stands. Each step names the files it may touch — an edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED`. One `apply_patch` is checked file by file: a patch that reaches outside the step is refused whole.

- Verify before reporting done: `verify_command` from `.ai/policies/testing.md` once, to the end, then `e2e_command` once; every failure fixed as one batch; show the output.
- No agent merges or deploys; commit, push, approval only as the dialog picks and the harness records, else a human outside. When a review flags the same mistake twice, the correction goes into this file.
- Files, not chat, carry decisions: `.ai/reports/<task-id>/task.md` (answer by filling `[Answer]:`), `.ai/state/handoff.md` (read first when resuming), `docs/sdlc/constitution.md`.
<!-- riskrails:end -->

## Project rules

- This project's own skills, hooks, agents and scripts: `.ai/policies/toolbox.md`.

### Changes under hooks/

- Weigh a change by what it does to a user project's decisions, never by the hook being a process every call runs through (constitution C6). The mode is what W gives (`state.py weight`); the rows below set the behaviour axis.
- behaviour 0: no guard decision moves, golden byte-identical. behaviour 1: adds a deny or changes a deny's text, golden re-recorded. behaviour 2: allows what was denied or weakens a refusal — declare it, `--declare behaviour=2:"<the effect>"`. Start such a task with `start --mode full --by <name>`: its weight lands in guarded, and these effects keep a STRONG review and the gate.
- The guards defend against an agent's mistakes, not a constructed command: such a finding is accepted in `known-risks.md` under the threat model in `.ai/policies/safety.md`.

### Changes under skills/

- Weigh a change by what it does to a user project's decisions, never by the skill being a process (constitution C6). The mode is what W gives (`state.py weight`); the rows below set the behaviour axis.
- behaviour 0: skill or agent text, `usage-report`, no `state.py` refusal moves. behaviour 1: adds a `state.py` check, a sensor or a refusal. behaviour 2: weakens a refusal, changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, the review verdict transitions) or changes install and migration (the `project-update` merge; a migration also raises reversibility through its hint) — declare it, `--declare behaviour=2:"<the effect>"`. Start such a task with `start --mode full --by <name>`: its weight lands in guarded, and these effects keep a STRONG review and the gate.
- A change to a shipped template or to `ai/` runs `tools/build-template-history.py` in the same task, or `tests/test_project_update.py` (`test_history_covers_every_template`) goes red.
