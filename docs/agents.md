# The agents

Ten static definitions plus two rendered at install time. They are identical in
every project; the project-specific half of their instructions comes from
`.ai/policies/` and `.ai/agents/`, which they read at the start of a run.

The roster and the tiers are the same in both runtimes. The prompt bodies are
written once, in `agents/*.md`; `scripts/render-codex-agents.py` converts them
into `~/.codex/agents/*.toml` using the tier and sandbox mode declared for each
role in `profiles/codex-{plus,pro}.json`, plus three Codex-only variants, `ai-risk-strong`,
`ai-planner-strong` and `ai-expert-strong` (the runtime gate's stand-in for
`ai-expert` while the EXPERT model is unavailable), that pin Sol — Codex reads an agent's own file ahead of
the model passed at spawn time, so "run `ai-risk` on a stronger model" cannot
work there. Under Claude Code the same escalation is `model: opus` on the
ordinary agent.

Which of them a task actually spawns depends on `pipeline_profile` in
`.ai/policies/risk-tiers.json`. In the default `solo` profile T0–T2 run in
direct mode: a T1 task spawns none, a T2 task spawns one (`ai-reviewer` on
`sonnet`), plus cheap readers on `haiku` when a search or a test run is long.
The full pipeline starts at T3. See `docs/risk-tiers.md`.

| Agent | Claude | Codex | Effort | Writes? | Runs at |
|---|---|---|---|---|---|
| `ai-indexer` | haiku | Terra | low | no | the start of discovery |
| `ai-discovery` | sonnet | Terra | low | no | discovery, impact analysis |
| `ai-context` | sonnet | Terra | medium | no | context |
| `ai-risk` | sonnet (opus on re-run) | Terra (`ai-risk-strong` on Sol for the re-run) | medium | no | risk classification |
| `ai-planner` | sonnet (opus at T3/T4) | Terra (`ai-planner-strong` on Sol at T3/T4) | medium | no | plan |
| `ai-implementer` | sonnet | Terra | medium | **yes** | mechanical steps only |
| `ai-tester` | sonnet | Terra | low | no | one named scope at a time: a step's own tests, the suite after the last step, e2e once at the end (team profile, or an unfamiliar test setup) |
| `ai-reviewer` | opus | Sol | high | no | plan review, adversarial review |
| `ai-security` | opus | Sol | high | no | T4, T5, auth or personal data |
| `ai-release` | sonnet | Terra | low | the report | release report at T4/T5 (solo) or from T2 (team) |
| `ai-expert` | `opus`, pinned on every plan | Astra, xhigh on Pro, high on Plus | xhigh on Max and Team Max, high on Pro and Team Pro | no | escalation only |

Three more come from the routing half, and are not part of the pipeline:

| Agent | Claude | Codex | Effort | Role |
|---|---|---|---|---|
| `architect` | `fable[1m]`, pinned, on Max and Team Max with Fable; the session model with `--fable no`; `opus`, pinned, on Pro and Team Pro | Sol | xhigh on Fable, else high | design questions outside a task, or in a repository without `.ai/`. Returns a design and an ordered plan; never writes code |
| `Explore` | sonnet | Terra | low | fast read-only search: which files matter, and why |
| `log-reader` | sonnet | Terra | low | logs, test output, CI, kubectl and helm output, condensed to the errors that matter |

The main session runs Opus 5 at `medium` on Max and Team Max, `opusplan` on Pro
and Team Pro, Sol at `high` under Codex on Pro and at `medium` on Plus.

`reviewer` used to sit here too. `ai-reviewer` replaces it: adversarial rather
than descriptive, aware of the task's risk tier, and reading the project's own
policies. The installer retires the old file when you have not edited it.

Everything except `ai-implementer` and `ai-release` is read-only, and the
read-only ones declare `disallowedTools: Edit, Write, NotebookEdit` as well as
omitting those tools — belt and braces, because a review agent that can edit is a
review agent that will eventually edit. The Codex renderer expresses the same
thing as `sandbox_mode = "read-only"`, with `workspace-write` for exactly those
two agents.

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
  resolves differently per plan: `opus` is pinned everywhere — at `xhigh` on Max
  and Team Max, at `high` on Pro and Team Pro — rather than inherited, because a
  session may run on Sonnet (`opusplan` outside plan mode, `/model`, or an IDE
  agent's Model setting) and the last-resort tier must not drop below the `opus`
  reviewer it escalates from. Fable, where enabled, is pinned on
  `architect` alone — design questions outside a task — and nothing else ever
  runs on it. Under Codex `ai-expert` is pinned to the plan's EXPERT model, and `runtime-gate`
  rewrites such a launch to the STRONG model while Astra is rate-limited or unavailable.
  Baking the resolution into the frontmatter at install time means every skill
  can just say "call `ai-expert`" and be correct on any plan and runtime.

The triggers for each tier are in the managed instruction block and in
`.ai/policies/model-routing.md`. Escalate one task at a time, on a named trigger.
Never re-run the whole fleet expensive, and never start at EXPERT because it
exists.

## The honest answers

Three agents are explicitly allowed — and expected — to admit they could not
settle something:

- `ai-discovery` returns **UNKNOWN** with what would answer it;
- `ai-risk` returns `confidence: uncertain`, which triggers a re-run at STRONG
  instead of a guess;
- `ai-tester` returns **UNKNOWN** rather than inventing a diagnosis.

This is the point. A confident wrong answer at the discovery stage propagates
through every later stage; an admitted gap costs one re-run.
