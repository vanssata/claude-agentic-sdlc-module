# The agents

Ten static definitions plus one rendered at install time. They are identical in
every project; the project-specific half of their instructions comes from
`.ai/policies/` and `.ai/agents/`, which they read at the start of a run.

The roster and the tiers are the same in both runtimes. The prompt bodies are
written once, in `agents/*.md`; `scripts/render-codex-agents.py` converts them
into `~/.codex/agents/*.toml` using the tier and sandbox mode declared for each
role in `profiles/codex.json`. So there is one place to change what an agent
says, and one place to change what it costs.

| Agent | Tier | Claude | Codex | Effort | Writes? | Runs at |
|---|---|---|---|---|---|---|
| `ai-indexer` | FAST | haiku | Terra | low | no | the start of discovery |
| `ai-discovery` | FAST/BALANCED | sonnet | Terra | low | no | discovery, impact analysis |
| `ai-context` | BALANCED | sonnet | Terra | medium | no | context |
| `ai-risk` | BALANCED | sonnet | Terra | medium | no | risk classification |
| `ai-planner` | BALANCED | sonnet | Terra | medium | no | plan |
| `ai-risk-strong` | STRONG | — (use `model: opus`) | Sol | high | no | the T3+/uncertain re-run |
| `ai-planner-strong` | STRONG | — (use `model: opus`) | Sol | high | no | planning at T3/T4 |
| `ai-implementer` | BALANCED | sonnet | Terra | medium | **yes** | mechanical steps only |
| `ai-tester` | BALANCED | sonnet | Terra | medium | no | after every step |
| `ai-reviewer` | STRONG | opus | Sol | high | no | plan review, adversarial review |
| `ai-security` | STRONG | opus | Sol | high | no | T4, T5, auth or personal data |
| `ai-release` | BALANCED | sonnet | Terra | medium | the report | release report |
| `ai-expert` | EXPERT | Fable, or Opus with `--fable no` | Astra | xhigh | no | escalation only |

Three more come from the routing half, and are not part of the pipeline:

| Agent | Tier | Claude | Codex | Effort | Role |
|---|---|---|---|---|---|
| `architect` | STRONG | opus | Sol | high | design questions outside a task, or in a repository without `.ai/`. Returns a design and an ordered plan; never writes code |
| `Explore` | FAST | sonnet | Terra | low | fast read-only search: which files matter, and why |
| `log-reader` | FAST | sonnet | Terra | low | logs, test output, CI, kubectl and helm output, condensed to the errors that matter |

The main session runs Opus 5 [1m] at `medium` on Max, Sonnet on Pro, Sol at `high`
under Codex.

**Every definition pins its model on purpose, in both runtimes.** Claude's
built-in `Plan` and `general-purpose` resolve to `CLAUDE_CODE_SUBAGENT_MODEL`
(sonnet), and a Codex agent with no `model` resolves to the Terra `[agents]`
default — an omitted model silently drops a reviewer to BALANCED either way.

The two `-strong` agents exist only under Codex, and only because of a precedence
rule: Codex reads a value from the agent's own file ahead of the value passed at
spawn time, so "run `ai-risk` on a stronger model" cannot work there. Under Claude
Code that same escalation is `model: opus` on the ordinary agent.

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

- **Within the STRONG range**, the caller decides based on the tier or on a
  `confidence: uncertain` answer. Under Claude Code, pass `model: opus` to the
  same agent definition — `ai-risk` and `ai-planner` are written to work at either
  level. Under Codex, call `ai-risk-strong` or `ai-planner-strong`, because a
  spawn-time model would be overridden by the agent's own file.
- **To EXPERT**, call `ai-expert`, which is a separate definition because the
  EXPERT model is install-dependent: Fable 5.1 on Max with Fable, Opus 5
  otherwise, Astra under Codex. The installer pins it, so every skill can just say
  "call `ai-expert`" and be correct anywhere. `fallbackModel` applies to pinned
  subagents as well, so a Fable overload still lands on Opus; under Codex the same
  job is done by `codex-model-gate`, which rewrites an Astra launch to Sol while
  Astra is rate-limited or unavailable.

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
