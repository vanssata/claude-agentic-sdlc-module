# Model routing policy

Sonnet is the default. Facts are collected cheaply; Opus and Fable are paid for
only on a named trigger — adversarial review, high-risk decisions and what a
cheaper tier could not settle — never for fact collection.

## Tiers

| Tier | Runs on | Used for |
|---|---|---|
| **LOCAL** | *not available inside Claude Code* | see the note below |
| **FAST** | `haiku`, effort `low` | file and symbol inventories, listings, counting, running a command and reporting its output |
| **BALANCED** — default | `sonnet`, effort `low`–`medium` | the main session and implementation, discovery with judgment, context compression, planning up to T2, tests, release assembly |
| **STRONG** | `opus`, effort `high` | the Opus triggers below |
| **EXPERT** | `ai-expert`, pinned at install time — Fable 5.1 on Max with Fable, Opus 5 otherwise | the EXPERT triggers below |

**On LOCAL.** The original design of this system assumed a local model for
indexing and repetitive inspection. Claude Code has no local-model backend, so
that work is done by deterministic tools (`rg`, `git`, `jq`, the framework CLI)
plus `ai-indexer` on the cheapest hosted model. Nothing in this infrastructure
depends on a local model; if one becomes available it slots in at the FAST tier.

## Opus (STRONG) triggers

1. Review of a finished change before a commit is proposed (`ai-reviewer`), and
   `ai-security` for authentication, authorization, secrets, payments, personal
   data, webhooks and any T4/T5 change.
2. `ai-risk` on Sonnet answered T3+ or `confidence: uncertain` — re-run on Opus;
   `ai-planner` on Opus at T3/T4.
3. Root cause after a Sonnet diagnosis already failed once, or a bug in
   concurrency, retries/idempotency, caching or data integrity.
4. A reversible but costly design choice with two or more viable options
   (`architect`).

## EXPERT triggers

1. The task is T5: migration, infrastructure, production architecture.
2. STRONG could not settle it: `confidence: uncertain`, or two Opus results
   contradict each other.
3. An irreversible design with several viable options — core data model, public
   API or event contract, service split.
4. The final check of a T5 plan or of a production-incident root cause before a
   human acts on it.

## Escalation

```
FAST → BALANCED → STRONG → EXPERT
```

One step at a time, for one task, when a trigger fires — and the trigger is named
in the task record. Never escalate the whole fleet, never start at EXPERT because
it exists, and never retry a failed *reasoning* task on a cheaper model —
downgrading is for mechanical work only. An overload is not a failure: the
fallback chain moves the agent to another model on its own.

## Fan-out

Cost scales with the number of agents, and every agent pays its own start-up. A
sweep of three or more parallel agents runs on `haiku` or `sonnet`, always. One
Opus or EXPERT agent per question, and one EXPERT agent per task.

## Briefing the expensive tiers

Collect first, cheaply. An Opus or EXPERT agent receives a compact brief — the
context summary, `file:line` facts, the question and the options — and asks for a
specific file when it needs one. It is never sent to explore the repository.

## What never gets delegated

The final synthesis, and anything the user reads as a conclusion. A cheap agent
may collect the evidence for it; the main session writes it.
