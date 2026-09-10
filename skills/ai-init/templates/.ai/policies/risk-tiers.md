<!-- generated from risk-tiers.json sha256:01c32f8ff038787e49070b8b0eb160eb4b4704a020b050678292051fc73a4fc6 -->
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

| Tier | Plans and reviews on |
|---|---|
| T0, T1 | FAST — the cheapest model that can follow an instruction |
| T2 | BALANCED |
| T3, T4 | STRONG |
| T5 | EXPERT, the session model itself |

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
