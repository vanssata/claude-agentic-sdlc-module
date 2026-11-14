# claude-agentic

## Things Claude Code gets wrong

- A BLOCKER is closed only with a test that pins it; for a regex's running time, a `timed` case at the measured size that fails on the tree before the fix. Reviews of T-2026-10-20-003 found an untested blocker twice, and its BLOCKERs 2, 4 and 5 came from edits to `SH_WORD`/`SH_RE` in the retired `hooks/ai-path-guard.sh`. Those regexes were deleted in R22 (`710a2aa`): `hooks/guard/paths_bash.py` splits top-level segments only (`paths_shell.py` `shell_segments`; a `sh -c`/`eval` string is not re-parsed, `:70-71`) and refuses unread a command over `LONG_CMD` = 4096 characters that names a guarded path or a gate verb (`:33,49`). A new pattern over command text gets its own `timed` case beside `tests/test_ai_path_guard.py:398-413`.
- A change to this plugin's hooks, skills or `state.py` does not score behaviour 2 for being "a process every call runs through": T-2026-10-21-001, a 51-line guard bugfix, ran as T4 and cost 25.4M tokens and three STRONG reviews. Weigh it by what it does to a user project's decisions — the "this repository:" examples in `.ai/policies/weight.project.json`, `docs/weight.md` (Modes and the old tiers), constitution C6.

<!-- riskrails:start -->
## AI agent workflow

This repository runs an agentic pipeline under `.ai/`. Read `.ai/AGENTS.md` first: it routes to the policies, workflows and rules, which load on demand; `.ai/policies/` is binding.

- Production behaviour is the source of truth: document problems outside the task, do not fix them.

- A change runs through `/rr-build <request>`; `/rr-status` shows where it stands. Each step names the files it may touch — an edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED`.

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
