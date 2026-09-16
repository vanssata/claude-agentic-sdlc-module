<!-- generated from risk-tiers.json sha256:e7cc8b00983d6022206aa576187a2d4dccc656aaea41b26dc32123b4b064e965 -->
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

## Who does each stage: the pipeline profile

`pipeline_profile` in `risk-tiers.json` decides who runs a stage, never whether
it runs. Every tier keeps its `stages_required`; the profile says which of them
go to a subagent.

| Tier | `solo` (default) delegates | `team` delegates |
|---|---|---|
| T0, T1 | nothing — no plan either: one `triage` call, say which files, edit, verify (T1) | discovery (and the test run at T1) |
| T2 | the adversarial review, on `sonnet`; the plan is a short inline list of steps | every stage except implementation |
| T3 | plan, plan review, adversarial review — on `opus` | every stage except implementation |
| T4 | plan, plan review, adversarial review, security review, release report | every stage except implementation |
| T5 | discovery and impact as well; the plan goes to `ai-expert` | every stage except implementation |

Tests run **once, after the last step** — the verification command in
`testing.md` — plus the step's own single test when that is cheap, and the
failing test first for a bugfix. T0 and T1 have no plan, so the scope guard is
not armed for them; the session names the files it will touch instead.

In `solo` the session still delegates one `ai-discovery` when the area is
unfamiliar or the plan depends on an `UNKNOWN`, `ai-risk` on `opus` when a T3+
classification is not obvious, and `log-reader` when the verification output is
long. The triggers are listed under `delegate_anyway_when`.

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
