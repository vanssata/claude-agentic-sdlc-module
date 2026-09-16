# Getting started

## 1. Install

```bash
cd "/Store/Claude Plugins/claude-agentic"
./install.sh
```

It detects your plan from `~/.claude.json`, writes the model, effort and context
settings for it, renders the EXPERT tier accordingly, copies the agents, hooks
and skills into `~/.claude/`, registers five hooks in `settings.json` and writes
one managed block into `~/.claude/CLAUDE.md`.

If you had `claude-routing` installed, this run migrates its block away; see the
migration section of the README.

Restart Claude Code, then check:

```
/config     → the model and effort match your plan
/skills     → ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*
/hooks      → five hooks
```

Try it without committing to anything first:

```bash
./install.sh --dry-run
```

## 2. Survey a project

In the repository you want to work in:

```
/ai-init
```

It runs the scaffold, detects the stack, asks you what you already know about
the project and confirms it with `grep`, sends two discovery agents to the
places memory is least reliable — legacy and risks, tests and data — and writes
`.ai/`. For a codebase you do not know, `/ai-init --survey full` fans out six
agents instead; on a large legacy codebase that costs real tokens, and the
fan-out is on the cheapest model for exactly that reason.

Before it finishes it asks for the one command that proves the project is
healthy and writes it into `.ai/policies/testing.md`. That command is the
feedback loop every later task closes before reporting done.

It does not touch application code. When it finishes, read
`.ai/project/initial-assessment.md` first: fourteen sections, ending with
recommendations that it deliberately did **not** implement.

Then read `.ai/project/known-risks.md` and `.ai/project/legacy.md`. Those are the
two files that will save you later.

Commit it:

```bash
git add .ai CLAUDE.md .gitignore
git commit -m "add agentic engineering infrastructure"
```

## 3. A small task, end to end

```
/ai-task fix the wording on the admin fee column header
```

What happens:

1. It classifies this as a **feature** (or you correct it), and starts a task.
2. You said where the column lives, or it asks; `grep -n` confirms the template
   and the translation key. Discovery, context and impact are one short
   summary, written inline and recorded — a lightweight stage is still a stage.
3. The trigger table says **T1**: an isolated presentation change. No agent was
   needed to say so.
4. T1 needs no plan review, no adversarial review, no security review and no
   human approval, so the plan is a few lines and implementation starts.
5. The step names the template and the translation file. If you now try to edit
   the pricing service, the scope guard refuses it.
6. The verification command from `testing.md` runs; its last lines are shown.
7. A short release report, which is also the commit message body, and the
   command that would commit it.

Total: minutes, no subagent spawned, and on Pro the whole thing ran on Sonnet.

## 4. A dangerous task, end to end

```
/ai-task add a 2% handling fee to card payments
```

The same pipeline, and a very different shape:

1. `ai-risk` returns **T4** — payments.
2. From the tier table, T4 requires: plan review, human approval of the plan,
   adversarial review, security review, a rollback section and a monitoring
   section.
3. Planning goes to `ai-planner` on `opus`, and the plan must name the
   characterization tests that pin the current fee behaviour **before** anything
   changes. This is the tier where the `solo` profile starts delegating.
4. You are shown the plan and the review, and asked to approve it. Nothing is
   implemented until you do.
5. Implementation goes step by step, each one scope-guarded.
6. `ai-reviewer` looks for rounding, currency, refunds, existing orders,
   idempotency and what happens on a retry.
7. `ai-security` reviews it against the full checklist and reports what it
   examined and found clean, not only what it found wrong.
8. `ai-release` assembles the report; you approve the merge.

At no point does an agent commit, merge or deploy.

## 5. Audit what you already have

```
/ai-audit
```

Writes `docs/ai-sdlc-adoption-plan.md`: an inventory of your current AI
configuration, 0–3 scores against the twelve AI-native SDLC plays with citations,
three phased adoption phases in dependency order, guardrail fixes, and the
questions only your team can answer.

It writes that one file and nothing else.

## Where to go next

- `docs/hooks.md` — what exactly is blocked, and how to adjust it
- `docs/risk-tiers.md` — tuning the tiers to your codebase
- `docs/agents.md` — who does what, and why some agents are allowed to say "I do
  not know"
