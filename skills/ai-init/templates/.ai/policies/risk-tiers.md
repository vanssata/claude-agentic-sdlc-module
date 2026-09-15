<!-- generated from risk-tiers.json sha256:17fa7392d1466e286d5aa83a19e364835c1977750ae1f186aec59e2046d688ea -->
<!-- If /ai-status reports this hash as stale, risk-tiers.json changed and this
     mirror did not. The JSON file is the source of truth; update this by hand. -->

# Risk tiers

Every task gets exactly one tier before anything is planned. The tier decides
three things: who plans it, who reviews it, and whether a human signs it off.

| Tier | What it covers | Plan reviewed | Human approves the plan | Adversarial review | Security review | Human approves the release |
|---|---|---|---|---|---|---|
| **T0** | documentation, comments, translations with no logic | no | no | no | no | no |
| **T1** | formatting, an isolated admin screen, a label | no | no | no | no | no |
| **T2** | a normal isolated feature, a new service with limited reach | no | no | yes | no | no |
| **T3** | shared domain behaviour: orders, workflows, async processing, an important integration | yes | yes | yes | when auth or personal data is touched | yes |
| **T4** | payments, accounting, tax, fiscal, authentication, authorization, order state transitions, customer data | yes | yes | yes | yes | yes |
| **T5** | migration strategy, infrastructure, Kubernetes, production deployment, destructive schema change, cross-system migration | yes | yes | yes | yes | yes |

## Which model works on it

The tier is the contract; which model it resolves to depends on the runtime the
session is in. The pipeline, the gates and the obligations below are identical
either way.

| Tier | Plans and reviews on | Claude Code | Codex |
|---|---|---|---|
| T0, T1 | FAST — the cheapest model that can follow an instruction | `haiku` | `gpt-5.6-terra` |
| T2 | BALANCED | `sonnet` | `gpt-5.6-terra` |
| T3, T4 | STRONG | `opus` | `gpt-5.6-sol` |
| T5 | EXPERT — `ai-expert` | pinned at install: Fable 5.1 where available, Opus 5 otherwise | `gpt-6-astra` |

Every agent without a trigger runs at BALANCED. The main session runs the model
the installed profile sets — Opus 5 [1m] at `medium` under Claude Code (Sonnet on
Pro), Sol at `high` under Codex.

Under Codex an agent's own file outranks the model asked for when it is spawned,
so the T3/T4 re-runs of `ai-risk` and `ai-planner` use the dedicated
`ai-risk-strong` and `ai-planner-strong` agents. Same tier, same trigger.

Report the model that actually ran, not the one that was requested: a rate-limit
gate may have moved an EXPERT agent down a tier.

Escalation is per task and one step at a time. The triggers are listed in
`risk-tiers.json`; the short version is that a cheap agent which returns thin,
contradictory or empty evidence gets escalated, and nothing starts expensive
"just in case".

A tier can be raised by anyone at any moment. Lowering one is a human decision,
written into the task record with the reason.

## Extra obligations by tier

- **T3 and above**: characterization tests come before any change to legacy behaviour.
- **T4**: the release report must have a rollback section and a monitoring section,
  and the plan must state the idempotency and retry behaviour explicitly.
- **T5**: migration analysis covering locks, table size, duration, deployment
  ordering and old-version compatibility; a rehearsed rollback, not a described
  one; and destructive operations need their own separate approval that names
  the operation.

## When the tier is not obvious

Take the higher one. The cost of an unnecessary review is a few minutes; the
cost of an unreviewed payment change is not.
