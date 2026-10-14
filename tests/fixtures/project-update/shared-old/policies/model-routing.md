# Model routing policy

Facts are collected cheaply; thinking is paid for. The expensive tier belongs to
design, synthesis, adversarial review and the conclusions a human reads — never
to fact collection.

## Tiers

| Tier | Runs on | Used for |
|---|---|---|
| **LOCAL** | *not available inside Claude Code* | see the note below |
| **FAST** | `haiku`, effort `low` | file and symbol inventories, listings, counting, running a command and reporting its output |
| **BALANCED** | `sonnet`, effort `medium` | discovery with judgment, context compression, normal planning, tests, release assembly |
| **STRONG** | `opus`, effort `high` | architecture, high-risk planning, difficult legacy reasoning, adversarial review, security review |
| **EXPERT** | the session model, effort set at install time | only when STRONG cannot resolve the question |

**On LOCAL.** The original design of this system assumed a local model for
indexing and repetitive inspection. Claude Code has no local-model backend, so
that work is done by deterministic tools (`rg`, `git`, `jq`, the framework CLI)
plus `ai-indexer` on the cheapest hosted model. Nothing in this infrastructure
depends on a local model; if one becomes available it slots in at the FAST tier.

## Escalation

```
FAST → BALANCED → STRONG → EXPERT
```

One step at a time, for one task, when a trigger in `risk-tiers.json` fires.
Never escalate the whole fleet, never start at EXPERT because it exists, and
never retry a failed *reasoning* task on a cheaper model — downgrading is for
mechanical work only.

## Fan-out

Cost scales with the number of agents. A sweep of five or more parallel agents
runs on the cheap tier, always. A single deep dive may run on the session model.

## What never gets delegated

The final synthesis, and anything the user reads as a conclusion. A cheap agent
may collect the evidence for it; the main session writes it.
