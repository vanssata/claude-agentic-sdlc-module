---
name: sdlc-plan
description: SDLC stage 3 — from an intent + spec produce docs/sdlc/plans/<slug>.md, an ordered implementation plan (files that change, order of work, risks, proof/tests, rollback) that the main session then executes step by step. Use after /sdlc-spec, "plan the implementation", "make the plan from the spec".
argument-hint: <path to docs/sdlc/specs/<slug>.md>
---

# /sdlc-plan $ARGUMENTS

Input: a spec file (default: most recent `docs/sdlc/specs/*.md`) and its sibling intent.
Output: `docs/sdlc/plans/<slug>.md`.

## Steps

1. **Prerequisites** — spec and intent exist; `docs/sdlc/plans/TEMPLATE.md` exists (else
   `/project-init`). If the spec's **Flagged concerns** contains unresolved items, list them and
   ask the user to resolve or explicitly accept each one before planning.
2. **Plan-mode reasoning** — treat this as plan mode: read, do not edit code. If the
   `superpowers:writing-plans` skill is available, use it for the step granularity; otherwise:
   - map each requirement to the files that must change (`grep -n`, `Explore` for discovery);
   - order the steps so each one leaves the repo working and verifiable;
   - one step ≈ one commit; name the command/test that proves it.
3. **Challenge it** before writing: answer explicitly
   - *What could this break?* (callers, migrations, config, other environments)
   - *Which step is the riskiest, and can it move earlier or be split?*
   Put the answers into **Risks** and mark the risky step in **Order of work**.
4. **Write** — copy `docs/sdlc/plans/TEMPLATE.md` to `docs/sdlc/plans/<slug>.md`, replace
   `{{TITLE}}`/`{{SLUG}}`, fill **Files that change / Order of work / Risks / Proof / Rollback**.
   Proof maps every requirement R<n> to a test or command.
5. **Confirm** — one round of corrections.
6. **Hand-off** — suggested commit `git add docs/sdlc/plans/<slug>.md && git commit -m "plan: <title>"`;
   then build in the main session one step at a time, running `ai-reviewer` before each commit.
   In a repository with `.ai/`, hand the plan to `/ai-task` instead and let the pipeline
   run the review and approval gates for the task's risk tier.
   If the plan is approved in plan mode, also save it to the runtime's plan directory —
   `.claude/plans/<slug>.md` under Claude Code, `.codex/plans/<slug>.md` under Codex. The
   canonical copy stays in `docs/sdlc/plans/`, which is shared by both.
