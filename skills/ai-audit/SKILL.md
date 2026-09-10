---
name: ai-audit
description: Audit a repository against the twelve plays of the AI-native SDLC playbook and produce docs/ai-sdlc-adoption-plan.md — inventory, 0–3 gap scores with citations, three phased adoption phases respecting the dependency order, guardrail fixes and open questions. Read-only except for that one file. Use on "/ai-audit", "audit our AI setup", "how mature is our agent workflow".
argument-hint: [project/team/CI/tracker context, optional]
---

# /ai-audit $ARGUMENTS

Audit what this repository already has and produce an adoption plan that **builds
on it rather than starting over**. Most repositories that reach this skill have
some AI configuration already; the plan's job is to find the gaps worth closing,
in an order that works.

## The rule for this entire skill

The only file you write is `docs/ai-sdlc-adoption-plan.md`. Everything else in
this run is read-only. Do not fix the problems you find — the plan is the
deliverable, and the team decides what to act on.

## Steps

### 1. Context

Read `.ai/project/overview.md` if it exists — its "team and process context"
section is exactly what this skill needs. If it does not exist, ask once, with
`AskUserQuestion`, for: what the project is, team size and who owns product and
architecture decisions, the CI/CD system and whether there is a staging
environment, the tracker that is the source of truth, and any hard constraints
(no production credentials for agents, a required human approval on every pull
request, regulatory obligations).

Do not invent this. An adoption plan written against a guessed team is worthless.

### 2. Inventory, read-only

Delegate the wide read to `ai-indexer` and, where judgment is needed, to
`ai-discovery` or `Explore`. Cover:

- `CLAUDE.md` at the root and every nested one — length, currency, contradictions;
- `.claude/settings.json` and `.claude/settings.local.json` — permissions, hooks,
  environment, models;
- `.claude/hooks/`, `.claude/skills/`, `.claude/agents/`, `.claude/commands/`;
- CI workflows (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`);
- branch protection — via `gh api repos/{owner}/{repo}/branches/{branch}/protection`
  when `gh` is authenticated, otherwise **unverified**, and say so;
- test, build and lint entry points: `Makefile`, `composer.json` scripts,
  `package.json` scripts, `phpunit.xml`, `phpstan.neon`, `ecs.php`;
- `REVIEW.md`, intent/spec/plan folders, `docs/adr/`, `.ai/`.

For each: **exists / partial / missing**, plus one line on its quality.

### 3. Score the twelve plays

Read `~/.claude/skills/ai-audit/templates/play-scoring-rubric.md` for what each
play means and what evidence to look for. Score each 0–3 and cite the file and
line that justifies the score.

This is judgment built on the evidence from step 2, so do it in the main session.
Do not delegate it, and do not re-read the repository to do it.

Write **unverified** rather than a guess, and list what would settle it. An audit
that reports a fabricated 2 is worse than one that admits it could not see.

### 4. Three phases

Respect the dependency order:

- no prerequisites: CLAUDE.md, skills, the feedback loop, hooks, plan mode;
- subagents and evals need CLAUDE.md and the feedback loop;
- the PR review loop needs evals and subagents;
- CI/CD integration needs the PR review loop and hooks;
- closing the loop needs CI/CD integration and intent.

Roughly two weeks per phase. Every item states: the play it advances and the
target score; the exact files to create or change with a short sketch of their
content; the owner role (engineer, tech lead, platform, product owner); its
prerequisites; governance — what is enforced, where the evidence is logged, who
approves; and one leading and one lagging metric with where the data comes from
(git log, pull-request metadata, CI logs, OpenTelemetry export).

Order by: risk reduction for what agents can already do in this repository today,
then low effort and high leverage, then what unblocks later plays.

### 5. Guardrail review

Separately flag anything in the current configuration that is unsafe or has
drifted, with the minimal fix for each:

- permissions that allow more than the team intends;
- hooks that can be bypassed locally, or that live in a file the agent can edit;
- secrets reachable by the agent — including through a Bash command;
- test files editable during a fix task, which lets a failing test be "fixed" by
  deleting it;
- a `CLAUDE.md` that is stale, self-contradictory, or longer than a page;
- when there is no `.ai/`: note that the path and scope guards are inactive here,
  and only the global git guard applies.

### 6. Write it

Copy `~/.claude/skills/ai-audit/templates/ai-sdlc-adoption-plan.md` to
`docs/ai-sdlc-adoption-plan.md` and fill it in: Inventory, Gap scores, Phase 1,
Phase 2, Phase 3, Guardrail fixes, Open questions for the team. Keep it under
about four pages — a plan nobody finishes reading changes nothing.

Then say, plainly, what you could not verify.

## Rules

- One file written. Nothing else in the repository changes.
- Cite or admit. Never a score without evidence or an "unverified".
- Build on what exists. If the repository already has a working convention, the
  plan strengthens it rather than replacing it with a different one.
- Do not commit. Suggest `git add docs/ai-sdlc-adoption-plan.md`.
