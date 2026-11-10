# Workflow: feature

New behaviour that someone asked for. The default workflow.

> Who runs a stage is set by `pipeline_profile` in `policies/risk-tiers.json`.
> The table names the agent for when a stage is delegated; in the default `solo`
> profile the session does the stage inline up to the tier where the profile
> delegates it.

| Stage | Who | Notes |
|---|---|---|
| DISCOVERY | `ai-indexer` then `ai-discovery` | where the feature lands, what it will touch |
| CONTEXT | `ai-context` | the structured summary everything downstream reads |
| IMPACT ANALYSIS | `ai-discovery` (second pass) | callers, data, contracts, other environments |
| RISK CLASSIFICATION | `ai-risk` | one tier, from `policies/risk-tiers.json` |
| PLAN | none at T0/T1; the session at T2; `ai-planner` from T3 | steps with `allowed_files`; STRONG for T3/T4, `ai-expert` for T5 |
| PLAN REVIEW | `ai-reviewer` | T3 and above |
| IMPLEMENTATION | the session, one step at a time | scope-guarded |
| TEST | the session (`ai-tester` in `team`) | once, after the last step; a step's own single test when cheap |
| ADVERSARIAL REVIEW | `ai-reviewer` | T2 and above |
| SECURITY REVIEW | `ai-security` | T4, T5, and anything touching auth or personal data |
| RELEASE REPORT | `ai-release` | full report from T2 up |
| HUMAN APPROVAL | the human | the pipeline stops here |

## Specific to this workflow

- The plan states what stays the same, not only what changes. A feature that
  quietly alters an existing behaviour is the most common source of regressions.
- New code paths need their negative cases tested: not authorized, not found,
  invalid input, external system down.
- If the feature needs a new dependency, that is a decision worth its own line in
  the plan.
