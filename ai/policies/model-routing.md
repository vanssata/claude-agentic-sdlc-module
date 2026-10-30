# Model routing policy

**The tiers are the contract; the models are the implementation.** This project
can be worked on from Claude Code, from Codex, or from both, and the pipeline is
identical either way. What changes is which model each tier resolves to. Routine
workload runs on the cheap tier; the expensive tiers are paid for only on a named
trigger — adversarial review, high-risk decisions and what a cheaper tier could
not settle — never for fact collection.

## Tiers

| Tier | Model | Used for |
|---|---|---|
| **LOCAL** | *not available* | see the note below |
| **FAST** | the plan's FAST model, effort `low` | reading and running: file search, inventories, counting, logs and test output, running a command and reporting it (`Explore`, `log-reader`) |
| **BALANCED** — default for agents | the plan's BALANCED model, effort `low`–`medium` | discovery with judgment (`ai-discovery`), the review in guarded mode (`ai-reviewer`; under Codex its file pins STRONG) |
| **STRONG** | the plan's STRONG model, effort `high` | the STRONG triggers below (`ai-reviewer` in full mode, `architect`) |
| **EXPERT** | the plan's EXPERT model — `xhigh` where the plan allows it, `high` elsewhere; `architect` may pin a model of its own | the EXPERT triggers below |

Which model a tier is depends on the plan and the runtime: the installed profile
decides it, `state.py profile --tier <TIER>` prints it for the runtime you are in,
and `/rr-status` shows the plan's budget. This file names tiers only, so it is true on
every plan.

The main session runs the model the installed profile sets and does the
implementation itself. Planning, the weight, the test run and the release are
its work too, not an agent's: `/rr-plan`, `state.py weight`, `state.py verify`,
`/rr-ship`. Which stages spawn an agent at all
is decided by the mode `state.py weight` gives: light runs direct — no review
unless `close` reports a red fact — guarded has one BALANCED review, full one
STRONG review, and nothing runs on STRONG below full — and tests run once
after the last step, to the end, with every failure fixed as one batch.

**Reading by difficulty.** A lookup — where X is, one route, service id, config
key or template — is FAST work (`Explore`). A trace of how the *installed*
third-party code behaves — `vendor/`, `node_modules/`, through decorators,
compiler passes, service or template overrides and event subscribers — is
BALANCED work at effort `low`: `ai-discovery`, named. A FAST reader tends to
stop at the first plausible match, and there a wrong answer reads exactly
like a right one.

**Codex agent precedence.** A value written into a Codex agent file wins over the
model asked for when the agent is spawned. So "the same agent on a stronger
model" cannot work there: a named agent runs on the tier its file pins, and an
EXPERT question is a spawn with no agent named and the EXPERT model on the
call. Same tier, same trigger, different mechanism.

**On LOCAL.** The original design of this system assumed a local model for
indexing and repetitive inspection. Neither runtime has a local-model backend, so
that work is done by deterministic tools (`rg`, `git`, `jq`, the framework CLI)
plus `Explore` on the cheapest hosted model. Nothing in this infrastructure
depends on a local model; if one becomes available it slots in at the FAST tier.

## STRONG triggers

1. Review of a finished change before a commit is proposed (`ai-reviewer`), with
   a `focus: security` brief for authentication, authorization, secrets,
   payments, personal data and webhooks — a full-mode task whose domain is 2.
2. A full-mode plan whose design is open (`architect`). The session plans
   everything else, and the weight is `state.py weight`, never an agent.
3. Root cause after a BALANCED diagnosis already failed once, or a bug in
   concurrency, retries/idempotency, caching or data integrity.
4. A reversible but costly design choice with two or more viable options
   (`architect`).

## EXPERT triggers

1. The task is full and irreversible: migration, infrastructure, production architecture.
2. STRONG could not settle it: `confidence: uncertain`, or two STRONG results
   contradict each other.
3. An irreversible design with several viable options — core data model, public
   API or event contract, service split.
4. The final check of a full-and-irreversible plan or of a production-incident root cause before a
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
sweep of three or more parallel agents runs at FAST or BALANCED, always. One
STRONG or EXPERT agent per question, and one EXPERT agent per task.

## Briefing the expensive tiers

Collect first, cheaply. A STRONG or EXPERT agent receives a compact brief — the
context summary, `file:line` facts, the question and the options — and asks for a
specific file when it needs one. It is never sent to explore the repository.

## Reporting what actually ran

Every artifact that names a tier names the model too — "STRONG (<model>)", with
the model `state.py profile --tier STRONG` printed — because a tier alone does not tell a reviewer what the review
cost or how much weight to give it. Report the model that **ran**, not the one
that was requested: a gate may have sent an EXPERT agent down one tier during a
rate limit, and a Codex agent file may have overridden the spawn-time model. Both
runtimes expose the current state through `/rr-status`.

## What never gets delegated

The final synthesis, and anything the user reads as a conclusion. A cheap agent
may collect the evidence for it; the main session writes it.
