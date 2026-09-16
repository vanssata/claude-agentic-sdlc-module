# The agents

Ten static definitions plus two rendered at install time. They live in
`~/.claude/agents/` and are identical in every project; the project-specific half
of their instructions comes from `.ai/policies/` and `.ai/agents/`, which they
read at the start of a run.

Which of them a task actually spawns depends on `pipeline_profile` in
`.ai/policies/risk-tiers.json`. In the default `solo` profile a T1 task spawns
none and a T2 task spawns one (`ai-reviewer`); the rest run inline in the
session. See `docs/risk-tiers.md`.

| Agent | Model | Effort | Writes? | Runs at |
|---|---|---|---|---|
| `ai-indexer` | haiku | low | no | the start of discovery |
| `ai-discovery` | sonnet | low | no | discovery, impact analysis |
| `ai-context` | sonnet | medium | no | context |
| `ai-risk` | sonnet (opus on re-run) | medium | no | risk classification |
| `ai-planner` | sonnet (opus at T3/T4) | medium | no | plan |
| `ai-implementer` | sonnet | medium | **yes** | mechanical steps only |
| `ai-tester` | sonnet | low | no | after every step (team profile, or an unfamiliar test setup) |
| `ai-reviewer` | opus | high | no | plan review, adversarial review |
| `ai-security` | opus | high | no | T4, T5, auth or personal data |
| `ai-release` | sonnet | low | the report | release report at T4/T5 (solo) or from T2 (team) |
| `ai-expert` | the session model on Max; `opus`, pinned, on Pro | per plan | no | escalation only |

Three more come from the routing half, and are not part of the pipeline:

| Agent | Model | Effort | Role |
|---|---|---|---|
| `architect` | the session model on Max; `opus`, pinned, on Pro | high | design questions outside a task, or in a repository without `.ai/`. Returns a design and an ordered plan; never writes code |
| `Explore` | sonnet | low | fast read-only search: which files matter, and why |
| `log-reader` | sonnet | low | logs, test output, CI, kubectl and helm output, condensed to the errors that matter |

`reviewer` used to sit here too. `ai-reviewer` replaces it: adversarial rather
than descriptive, aware of the task's risk tier, and reading the project's own
policies. The installer retires the old file when you have not edited it.

Everything except `ai-implementer` and `ai-release` is read-only, and the
read-only ones declare `disallowedTools: Edit, Write, NotebookEdit` as well as
omitting those tools — belt and braces, because a review agent that can edit is a
review agent that will eventually edit.

## Output contracts

Each agent returns fixed headings so the manager can parse the result rather than
interpret prose:

| Agent | Returns |
|---|---|
| `ai-indexer` | `## INVENTORY`, `## OMITTED` |
| `ai-discovery` | `## FACTS` (labelled, with `file:line`), `## OPEN QUESTIONS` |
| `ai-context` | `## CONTEXT SUMMARY` with thirteen fixed fields |
| `ai-risk` | `## RISK CLASSIFICATION` with `tier`, `reason`, `confidence` |
| `ai-planner` | `## PLAN` with steps carrying `allowed_files` |
| `ai-implementer` | `## RESULT` or `## SCOPE_CHANGE_REQUIRED` |
| `ai-tester` | `## TEST RESULT` with one of five verdicts |
| `ai-reviewer` | `## FINDINGS`, `## EXAMINED AND CLEAN`, `## VERDICT` |
| `ai-security` | `## SECURITY FINDINGS`, `## EXAMINED AND CLEAN`, `## VERDICT` |
| `ai-release` | the filled release-report template |
| `ai-expert` | `## RESOLUTION` with `residual_risk` and `revisit_when` |

## Escalation

Two mechanisms, deliberately different:

- **Within the STRONG range**, pass `model: opus` to the same agent definition.
  `ai-risk` and `ai-planner` are written to work at either level; the caller
  decides based on the tier or on a `confidence: uncertain` answer.
- **To EXPERT**, call `ai-expert`, which is a separate definition because EXPERT
  resolves differently per plan: the session model on Max, and `opus` pinned on
  Pro, where the session runs `opusplan` and an inherited model would be Sonnet
  outside plan mode. Baking the resolution into its frontmatter at install time
  means every skill can just say "call `ai-expert`" and be correct on any plan.

Escalate one task at a time, on a trigger from `risk-tiers.json`. Never re-run
the whole fleet expensive, and never start at EXPERT because it exists.

## The honest answers

Three agents are explicitly allowed — and expected — to admit they could not
settle something:

- `ai-discovery` returns **UNKNOWN** with what would answer it;
- `ai-risk` returns `confidence: uncertain`, which triggers a re-run on a stronger
  model instead of a guess;
- `ai-tester` returns **UNKNOWN** rather than inventing a diagnosis.

This is the point. A confident wrong answer at the discovery stage propagates
through every later stage; an admitted gap costs one re-run.
