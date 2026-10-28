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
- No agent commits, merges or deploys; approval is given by a human outside the agent. When a review flags the same mistake twice, the correction goes into this file.
- Files, not chat, carry decisions: `.ai/reports/<task-id>/task.md` (answer by filling `[Answer]:`), `.ai/state/handoff.md` (read first when resuming), `docs/sdlc/constitution.md` (this project's principles).
<!-- riskrails:end -->
