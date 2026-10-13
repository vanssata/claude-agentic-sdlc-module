# Risk tiers

Every task gets exactly one tier before anything is planned. The tier decides who
plans the change, who reviews it, and whether a human signs it off. It replaces
the judgement "this looks easy", which is the judgement that causes incidents.

## The tiers

The tier is the **scope** of a change — what it reaches — never its size. How
many files or lines a change touches is measured and reported by the diff
budget; it does not classify. Three questions settle most cases: does it change
a process that other code runs through (T4 at least)? does it touch money,
identity or customer data (T5)? is it irreversible (T6)? Adding a resource and
the screens that present it, without changing an existing process, is T3 —
without the characterization tests, the STRONG review and the human gates that
start at T4.

| Tier | Covers |
|---|---|
| **T0** | documentation, comments, translations with no logic |
| **T1** | formatting, a label, a template or stylesheet change with no logic |
| **T2** | an isolated admin screen or form, a new field, a grid column or filter, a small feature that changes no existing process |
| **T3** | CRUD and presentation: a new resource with its entity, repository, form, grid, routes, menu and translations; a non-critical API extension; a new service with limited reach |
| **T4** | shared domain behaviour and processes: shared services, orders, workflows, async processing, an important integration, a schema migration that adds to a table, configuration and dependencies |
| **T5** | payments, accounting, tax, fiscal, authentication, authorization, order state transitions, customer data, external financial systems |
| **T6** | migration strategy, infrastructure, Kubernetes, production deployment, data migration, destructive schema change, cross-system migration |

## Who does each stage

The tier decides whether a stage runs. `pipeline_profile` in the same JSON
decides who runs it — the session inline, or a subagent with its own context
window. The default `solo` profile runs T0–T4 in **direct mode** (no state file
below T2, one `state.py quick` call from T2 to T4, cheap readers only; at T2
and T3 the sensors are the review and a `sonnet` reviewer runs only when one is
red; at T4 the session writes the plan in plan mode, the human approves it
before any edit, characterization tests come first and the one review is on
`opus`) and the full pipeline from T5: delegated plan, plan review, security
review and the release report, and discovery too at T6. Tests
run once, to the end, and every failure is fixed as one batch. `team` delegates every stage except
implementation at every tier. The full table is in the mirror each project
carries, `.ai/policies/risk-tiers.md`, and the triggers that make `solo`
delegate anyway — an unfamiliar area, an `UNKNOWN` the plan depends on, a
non-obvious T4+ tier, long test output — are under `delegate_anyway_when`.

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
- Size does not lower a tier. A three-line change in a payment path is T5.
- Size does not raise one either. The diff budget in `risk-tiers.json` is
  advisory: over it, `state.py step-done` warns and names `step-split`, and the
  re-score leaves the tier alone. Only a project that writes
  `diff_budget.enforce: true` turns it back into a gate. Advisory never means
  unread: a task over its budget keeps its model review — `review-gate` refuses
  `skipped_green` while the size is over.
- Every default path floor that changes a process — `config`, `dependencies`,
  `migrations`, the pipeline's own files — is T4, above the T3 ceiling at which
  the sensors may stand in for a reader. A dependency bump always gets a reader.
- A project whose `risk-tiers.json` still describes six tiers (no `T6`) is read
  on its own scale — its direct-mode cap stays T3 and its review skip stays at
  T2 — until `/project-update` renumbers it.
- `confidence: uncertain` from `ai-risk` is a real answer, and it causes a re-run
  on a stronger model rather than a guess.
- An agent may **raise** a tier at any time. Lowering one is a human decision,
  written into the task record with the reason.

## What each tier costs you

| Tier | Plans and reviews on | Extra obligations |
|---|---|---|
| T0, T1 | the session, directly; no plan stage, no state file | — |
| T2, T3 | the session, directly, with a few-line plan; the sensors are the review, BALANCED reviews only when one is red | one `state.py quick` record; the named tests must fail without the change (`bite`) |
| T4 | the session plans in plan mode; STRONG reviews | human plan approval, characterization tests before touching legacy, human approval of the result |
| T5 | STRONG | all of T4, plus a delegated plan and plan review, security review, a mandatory rollback and monitoring section, and explicit idempotency and retry behaviour |
| T6 | EXPERT | all of T5, plus migration analysis (locks, table size, duration, deploy order, old-version compatibility) and a **rehearsed** rollback |

Destructive database operations at any tier need their own separate approval that
names the operation. An agent proposes them; it never runs them.
