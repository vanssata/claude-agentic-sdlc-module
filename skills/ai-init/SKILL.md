---
name: ai-init
description: Survey an existing production codebase and build the .ai/ agentic engineering infrastructure around it — knowledge base, policies, risk tiers, workflows, agent contracts — then write an initial assessment. Read-only with respect to application code. Use on "set up agentic infrastructure", "analyse this project for AI work", "/ai-init", before the first /ai-task in a repository.
argument-hint: [team/CI/tracker context, optional]
---

# /ai-init $ARGUMENTS

Build the agentic infrastructure for **an existing production project**. This is
not a greenfield setup: the repository already contains legacy code,
undocumented rules, historical workarounds and behaviour that customers depend
on right now.

The skill is the same under Claude Code and under Codex. Only the install root
differs, so resolve it once instead of hard-coding `~/.claude`:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/ai-init" ] && break
done
```

Either copy of the scripts does the same thing — they operate on the project's
`.ai/` tree, not on the install — so which one resolves first does not matter.

## The rule for this entire skill

**Do not modify application code.** Not a rename, not a formatting fix, not a
"while I'm here". The only files this skill creates or edits are `.ai/**`, the
instruction file of each runtime in scope (`CLAUDE.md`, `AGENTS.md`, or both),
`.gitignore`, and (through the routing scaffold, if installed) `docs/sdlc/**`.
If you find problems — and you will — you document them. You do not fix them.

## Steps

### 1. Scaffold

Run the SDLC scaffold first, so `docs/sdlc/` and the runtime directory exist:

```bash
"$AI_HOME/hooks/project-scaffold.sh" "$PWD"
```

Then the agentic scaffold:

```bash
"$AI_HOME/skills/ai-init/scaffold-ai.sh" "$PWD"
```

Both take `--runtime auto|claude|codex|both`, and `auto` follows what the project
already declares (`CLAUDE.md`/`.claude/` → Claude, `AGENTS.md`/`.codex/` →
Codex), falling back to the runtime this copy was installed for. Pass `--runtime
both` when the repository is worked on from both, so one `.ai/` tree ends up with
two instruction files pointing at it.

Both are idempotent and never overwrite. Note which files they report creating —
if `.ai/project/overview.md` was **not** created, this project was already
initialised: ask whether to refresh the survey or stop.

### 2. Detect the stack yourself

This is a handful of `ls` and `grep -n` calls, not a delegation. Look for:
`composer.json` (read `require` and `scripts`), `package.json`, `Makefile`,
`pyproject.toml`, `go.mod`, `docker-compose*.yml`, `Dockerfile`, `.github/workflows`,
`.gitlab-ci.yml`, `Jenkinsfile`, `Chart.yaml`, `charts/`, `argocd/`, `phpunit.xml*`,
`phpstan.neon*`, `psalm.xml`, `ecs.php`, `rector.php`, `.php-cs-fixer*`,
`playwright.config.*`, `cypress.config.*`, `sonar-project.properties`.

For a Symfony or Sylius project also check, when present: `config/bundles.php`,
`config/packages/`, `src/Entity`, `src/Repository`, state machines and workflows,
Messenger transports and handlers, a command bus, event subscribers and
listeners, grids, form types and extensions, Twig templates and hooks, API
Platform resources, Sylius resources, payment methods, shipping, tax calculation,
promotions, channels, the customer/order/payment model, installed plugins,
custom state machines, and ERP, accounting or fiscal integrations.

### 3. One inventory pass, then fan out

Run `ai-indexer` once for a repository-wide inventory: top-level layout, file
counts per area, the largest files, entry points, and a summary of recent commit
subjects. It is on the cheapest model precisely so this pass is free.

Then fan out `ai-discovery` agents **in parallel, in one message**, one per area,
each handed the slice of the inventory it needs so it does not glob the
repository itself:

1. architecture and entry points — routes, commands, consumers, cron, webhooks;
2. domain modules — entities, repositories, services, state machines, workflows;
3. dependencies and integrations — payment, ERP, accounting, fiscal, shipping,
   any external API, and how failures are handled;
4. business rules and legacy — the rules the code enforces, the areas that are
   old or strange, and code that looks unused;
5. tests, CI/CD and tooling — what runs, where, and what it actually checks;
6. data and configuration — schema, migrations, queues, caches, environment
   configuration and how secrets are supplied (never their values).

This is a wide fan-out, so it stays on the cheap tier. Do not raise it.

### 4. Synthesise into `.ai/project/`

Write the discovery output into the knowledge base, preserving every label
verbatim: **KNOWN FACT** with `file:line`, **INFERENCE** with what it rests on,
**UNKNOWN** with what would answer it, **RISK** with what could go wrong. Never
promote an inference to a fact while summarising.

Where documentation and code disagree, use the four-line form:

```
Documented behaviour:
Observed behaviour:
Evidence:
Risk:
```

Do not resolve the contradiction. Record it.

Fill the "project specifics" sections of `.ai/policies/coding.md`,
`testing.md`, `database.md` and `release.md` **only if those files were created
in step 1**. If they already existed, someone has edited them: leave them alone.

Adjust `.ai/policies/risk-tiers.json` to this project — the tier examples should
name this codebase's actual critical areas, not generic ones. If you change the
JSON, update `risk-tiers.md` and its `sha256` comment to match.

### 5. Write the initial assessment

`.ai/project/initial-assessment.md`, with these sections:

1. project overview; 2. architecture discovered; 3. important modules;
4. critical business areas; 5. legacy hotspots; 6. high-risk integrations;
7. test maturity; 8. CI/CD maturity; 9. security observations;
10. missing documentation; 11. areas agents should not modify casually;
12. recommended risk-tier customisations; 13. recommended model routing;
14. recommended next improvements.

Section 14 is a list of recommendations. **Do not implement any of them.**

This is synthesis a human reads, so write it in the main session. Do not delegate.

### 6. Dry walkthrough of the pipeline

Take the first task you would suggest and narrate it through the stages —
DISCOVERY, CONTEXT, IMPACT, RISK, PLAN, IMPLEMENTATION, TEST, ADVERSARIAL
REVIEW, SECURITY REVIEW, RELEASE REPORT, HUMAN APPROVAL — saying at each stage
which agent would run, at which model tier, and which gate applies, according to
`.ai/policies/risk-tiers.json`.

Do the same, in two or three lines each, for the five shapes of change: a small
admin tweak, an isolated feature, a change to legacy order logic, a
payment/accounting change, and a database or infrastructure migration.

State plainly, in the output: **this is a dry walkthrough. No agent executed the
pipeline and nothing was validated by running it.** Then say how to actually run
it: `/ai-task <the suggested first task>`.

### 7. Report

Close with:

1. files created (a tree, from the scaffold output);
2. project-specific findings that surprised you;
3. the agent roster that now applies;
4. model routing for this plan;
5. the risk model, with any project-specific adjustment you made;
6. the context strategy;
7. safety restrictions now in force, and which are mechanical (hooks) versus
   policy;
8. existing tooling that the workflows will reuse rather than replace;
9. assumptions you made;
10. unresolved questions, and who can answer each;
11. the suggested first real task, and why that one.

Do not claim anything was validated that was not actually run.

## Rules

- No application code changes. None.
- Never read `.env`, secrets, dumps or production logs — the path guard refuses,
  and it is right to.
- Prefer deterministic tools to model tokens: `rg`, `git log`, `jq`, the framework
  CLI, the test runner.
- Do not install anything, add a dependency, or "modernise" a tool. Document what
  exists and how the workflows will use it.
- Suggest `git add .ai .gitignore` plus whichever instruction files the scaffold
  reported (`CLAUDE.md`, `AGENTS.md`) at the end; do not commit.
