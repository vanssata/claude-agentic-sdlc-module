# Risk tiers

Every task gets exactly one tier before anything is planned. The tier decides who
plans the change, who reviews it, and whether a human signs it off. It replaces
the judgement "this looks easy", which is the judgement that causes incidents.

## The tiers

| Tier | Covers |
|---|---|
| **T0** | documentation, comments, translations with no logic |
| **T1** | formatting, an isolated admin screen, a label |
| **T2** | a normal isolated feature, a new service with limited reach |
| **T3** | shared domain behaviour: orders, workflows, async processing, an important integration |
| **T4** | payments, accounting, tax, fiscal, authentication, authorization, order state transitions, customer data |
| **T5** | migration strategy, infrastructure, Kubernetes, production deployment, destructive schema change, cross-system migration |

## Two files, one source of truth

`/ai-init` copies both into every project:

- **`.ai/policies/risk-tiers.json`** is the source of truth. `/ai-task` reads it
  to decide which stages are mandatory; `ai-risk` reads it to classify.
- **`.ai/policies/risk-tiers.md`** is a human-readable mirror, carrying the
  sha256 of the JSON it was generated from.

`/ai-status` recomputes that hash and warns in one line when the mirror is stale.
It is a warning, not a build step: keeping a one-page mirror in sync is a
one-person job, and a hard gate there would be ceremony.

## Tuning it for your project

The shipped tiers are generic. After `/ai-init`, edit the `examples` in
`risk-tiers.json` so they name **this codebase's** critical areas — the actual
service that talks to the fiscal device, the actual state machine that moves
orders. A tier table full of generic examples gets ignored; one that names the
files people are afraid of gets read.

If you change the JSON, update the markdown and its hash comment.

## Rules of classification

- When two tiers are arguable, take the higher one.
- Size does not lower a tier. A three-line change in a payment path is T4.
- `confidence: uncertain` from `ai-risk` is a real answer, and it causes a re-run
  on a stronger model rather than a guess.
- An agent may **raise** a tier at any time. Lowering one is a human decision,
  written into the task record with the reason.

## What each tier costs you

| Tier | Plans and reviews on | Extra obligations |
|---|---|---|
| T0, T1 | FAST | — |
| T2 | BALANCED | adversarial review |
| T3 | STRONG | plan review, human plan approval, characterization tests before touching legacy |
| T4 | STRONG | all of T3, plus security review, a mandatory rollback and monitoring section, and explicit idempotency and retry behaviour |
| T5 | EXPERT | all of T4, plus migration analysis (locks, table size, duration, deploy order, old-version compatibility) and a **rehearsed** rollback |

Destructive database operations at any tier need their own separate approval that
names the operation. An agent proposes them; it never runs them.
