# Getting started

## 1. Install

```bash
cd "/Store/Claude Plugins/claude-agentic"
./install.sh
```

It detects your plan from `~/.claude.json`, writes the model, effort and context
settings for it, renders the EXPERT tier accordingly, copies the agents, hooks
and skills into `~/.claude/`, registers five hooks in `settings.json` (plus
`fable-gate` when Fable is enabled) and writes one managed block into
`~/.claude/CLAUDE.md`.

If you had `claude-routing` installed, this run migrates its block away; see the
migration section of the README.

Restart Claude Code, then check:

```
/config     → the model and effort match your plan
/skills     → ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report
/hooks      → five hooks, plus fable-gate on a Fable install
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

It runs the scaffold, detects the stack, fans out discovery agents across six
areas, and writes `.ai/`. On a large legacy codebase this takes a while and costs
real tokens — the fan-out is on the cheapest model for exactly that reason.

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
2. Discovery finds the template and the translation key.
3. Context is two sentences, written inline — a lightweight stage is still a
   stage, and it is recorded.
4. `ai-risk` returns **T1**: an isolated presentation change.
5. T1 needs no plan review, no adversarial review, no security review and no
   human approval, so the plan is short and implementation starts.
6. The step names the template and the translation file. If you now try to edit
   the pricing service, the scope guard refuses it.
7. `ai-tester` runs the suite.
8. A short release report, and the commands that would commit it.

Total: minutes, and one cheap model did most of it.

## 4. A dangerous task, end to end

```
/ai-task add a 2% handling fee to card payments
```

The same pipeline, and a very different shape:

1. `ai-risk` returns **T4** — payments.
2. From the tier table, T4 requires: plan review, human approval of the plan,
   adversarial review, security review, a rollback section and a monitoring
   section.
3. Planning runs on `opus`, and the plan must name the characterization tests
   that pin the current fee behaviour **before** anything changes.
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
