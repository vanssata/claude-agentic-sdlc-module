# Getting started

## 1. Install

```bash
cd "/Store/Claude Plugins/claude-agentic"
./install.sh
```

It detects which runtimes you have — Claude Code, Codex, or both — and installs
only for those. If it finds neither it stops and tells you to name one with
`--target`; it never guesses.

**Claude Code.** It detects your plan from `~/.claude.json`, writes the model,
effort and context settings for it, renders the EXPERT tier accordingly, copies
the agents, hooks and skills into `~/.claude/`, registers the hooks in
`settings.json` and writes one managed block into `~/.claude/CLAUDE.md`.

**Codex.** It renders the agent roster to `~/.codex/agents/*.toml`, copies the
hooks and skills, merges `hooks.json`, writes one managed block into
`~/.codex/AGENTS.md`, and sets six keys in `config.toml`: the session to Sol at
`high`, and the `[agents]` defaults to Terra at `medium`. Everything else in that
file — your comments, projects, MCP servers, marketplaces — is preserved, and the
previous version is kept as `config.toml.bak`.

> If Astra is your current Codex default, this changes it to Sol. That is the
> point of the routing, not an accident: the session model is the single largest
> cost, and Astra stays one escalation away.

If you had `claude-routing` installed, this run migrates its block away; see the
migration section of the README.

Restart the runtime, then check:

```
Claude Code
  /config     → the model and effort match your plan
  /skills     → ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report
  /hooks      → the three guards, cap-large-read, project-scaffold, and fable-gate on a Fable install

Codex
  /hooks      → the three guards and codex-model-gate — REVIEW AND TRUST THEM HERE,
                or they do not run and nothing is enforced
  codex --version && grep -E '^model' ~/.codex/config.toml
```

Try it without committing to anything first:

```bash
./install.sh --dry-run
./install.sh --target codex --dry-run    # one runtime at a time
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

Commit it — add whichever instruction files the scaffold reported creating:

```bash
git add .ai .gitignore CLAUDE.md          # and/or AGENTS.md
git commit -m "add agentic engineering infrastructure"
```

If the repository is worked on from both runtimes, scaffold both instruction
files over the one shared `.ai/` tree:

```bash
"$AI_HOME/skills/ai-init/scaffold-ai.sh" "$PWD" --runtime both
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
   the pricing service, the scope guard refuses it — including as one file inside
   a larger `apply_patch` under Codex, which rejects the whole patch.
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
3. Planning runs at the STRONG tier — `ai-planner` with `model: opus` under Claude
   Code, `ai-planner-strong` on Sol under Codex — and the plan must name the characterization tests
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

## 6. See what it cost

```
/usage-report
```

Reads local transcripts from both runtimes and prints per-model token counts,
per-day and per-session cost, the subagent share and a total — at zero model
cost. Compare runtimes by the token columns; the Codex dollar column is an
estimate until someone verifies the rates in `skills/usage-report/prices.json`,
and the report says so under the total rather than quietly presenting a guess.

## Where to go next

- `docs/hooks.md` — what exactly is blocked, and how to adjust it
- `docs/risk-tiers.md` — tuning the tiers to your codebase
- `docs/agents.md` — who does what, and why some agents are allowed to say "I do
  not know"
