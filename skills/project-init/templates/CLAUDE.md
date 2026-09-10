# {{PROJECT}}

<!-- Project instructions for Claude Code. Keep it short: only what Claude cannot infer from the code. -->

## Commands

<!-- Build, test, lint, run. One line each. -->

## Conventions

<!-- Naming, layering, error handling, commit style. Things a reviewer would flag. -->

## Architecture

<!-- The five-sentence map: entry points, main modules, where state lives, how requests flow. -->

## SDLC workflow

`/ai-task <request>` is the default route for a change: it classifies the risk,
plans, implements one scoped step at a time, reviews, and stops at human approval.
Work that needs a written intent and specification first goes `/sdlc-intent` →
`/sdlc-spec` → `/sdlc-plan`, then hands the plan to `/ai-task` for the build.

Artefacts live in `docs/sdlc/` (see `docs/sdlc/README.md`); decisions in
`docs/sdlc/adr/`; project memory in `.claude/memory/`; task artefacts and the
audit trail in `.ai/reports/`. Run `/ai-init` if this repository has no `.ai/`.

## Things Claude gets wrong

<!-- Recurring mistakes and their corrections. Grow this list from code review. -->
