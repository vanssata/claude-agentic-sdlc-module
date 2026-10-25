# claude-agentic

<!-- Project instructions for Claude Code. Keep it short: only what the agent cannot infer from the code. -->

## Commands

<!-- Build, test, lint, run. One line each. -->

## Verification

<!-- The one command that proves the project is healthy. Run it before reporting any task done, and show the output. -->

## Conventions

<!-- Naming, layering, error handling, commit style. Things a reviewer would flag. -->

## Architecture

<!-- Five sentences: entry points, main modules, where state lives, how requests flow. -->

## Things Claude Code gets wrong

<!-- Recurring mistakes and their corrections. Grow this list from code review. -->

- A BLOCKER is closed only with a test that pins it; for a regex's running time, a `timed` case at the measured size that fails on the tree before the fix. Reviews of T-2026-10-20-003 found an untested blocker twice, and its BLOCKERs 2, 4 and 5 all came from edits to `SH_WORD`/`SH_RE` in `hooks/ai-path-guard.sh`, where the invariant is: no piece of a word crosses the blank after a match start's `sh`.
- A change to this plugin's hooks, skills or `state.py` is not T4 for being "a process every call runs through": T-2026-10-21-001, a 51-line guard bugfix, ran as T4 and cost 25.4M tokens and three STRONG reviews. Tier it by what it does to a user project's decisions — the "this repository:" examples in `.ai/policies/risk-tiers.json`, constitution C6.

<!-- claude-agentic:start -->
## AI agent workflow

This repository runs an agentic pipeline under `.ai/`. Read `.ai/AGENTS.md` first: it routes to the policies, workflows and rules, which load on demand; `.ai/policies/` is binding.

- Production behaviour is the source of truth: document problems outside the task, do not fix them.

- A change runs through `/ai-task <request>`; `/ai-status` shows where it stands. Each step names the files it may touch — an edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED`.

- Verify before reporting done: `verify_command` from `.ai/policies/testing.md` once, to the end, then `e2e_command` once; every failure fixed as one batch; show the output.
- No agent commits, merges or deploys; approval is given by a human outside the agent. When a review flags the same mistake twice, the correction goes into this file.
- Files, not chat, carry decisions: `.ai/reports/<task-id>/questions.md` (answer by filling `[Answer]:`), `.ai/state/handoff.md` (read first when resuming), `docs/sdlc/constitution.md` (this project's principles).
<!-- claude-agentic:end -->
