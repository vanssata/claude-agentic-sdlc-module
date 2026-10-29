# The agents

Five agents, each a template under `agents/` that the installer renders with
the plan's model and effort for its tier (`~/.claude/agents/*.md`;
`~/.codex/agents/*.toml` through `scripts/render-codex-agents.py`, model and
effort pinned, `sandbox_mode = "read-only"`). None of them writes code: the
main session implements. Each one exists for a job the session should not do
in its own context — reading a lot, judging a lot, or arguing against the
session's own work.

| Agent | Tier | Spawned by | Returns |
|---|---|---|---|
| `Explore` | FAST, `low`; `Read`, `Grep`, `Glob` | any skill, for a lookup — where X is, one route, a config key — and for a file too large to open (`cap-large-read` points here) | paths with one line each, at most about thirty quoted lines, `file:line` |
| `log-reader` | FAST, `low`; `Write` and `Edit` disallowed | `/rr-build` and `/rr-build-all` for a long test log or CI output | the failing component, at most thirty raw lines, a root-cause hypothesis, what to check next — every failure listed |
| `ai-discovery` | BALANCED, `low`; read-only | `/rr-setup` (two in a light survey, six in a full one), `--audit`, and `/rr-build` for a reader that must judge — where a behaviour really lives, how installed third-party code behaves | `## FACTS` labelled KNOWN FACT (`file:line`) / INFERENCE / UNKNOWN / RISK, `## OPEN QUESTIONS` |
| `ai-reviewer` | BALANCED in guarded mode, STRONG in full; the tier passed per call as `model:` on Claude Code (the Codex file pins STRONG); read-only, about 40 tool calls in light and guarded, about 80 in full | `/rr-review` and `/rr-build-all`, one per review pass; in light mode only when `close` reports a red fact | `## FINDINGS` — `[BLOCKER] B1`, `[HIGH] H1`, MEDIUM, LOW, INFO, each with `file:line`, a reproduction and `in_scope: yes\|no`; `## EXAMINED AND CLEAN`, with `not reached (budget)` for what the cap left; `## VERDICT` — `pass`, `pass_with_findings` or `blockers_open`, and a `scope_assessment` |
| `architect` | STRONG in `/rr-spec`; EXPERT on `fable[1m]` at `xhigh` on Max, `opus` at `high` on Pro; `Read`, `Grep`, `Glob`, user memory | `/rr-spec` for the requirements and design; `/rr-plan` for a full-mode plan whose design is open; design questions outside a task | a design document — context, responsibilities, data flow, at least two alternatives with their tradeoffs, risks — and an ordered implementation plan with a verification criterion per step |

The shared contracts behind them are `ai/agents/*.md` in the installed tree:
`discovery.md`, `reviewer.md` and the brief every batch-build implementer and
fixer receives (`implementer.md`). A batch build's implementers are not agents
of this plugin: on Claude Code they are `general-purpose` subagents with
`model:` set to the BALANCED tier, on Codex an unnamed spawn with the model on
the call, each briefed with one step's files, tests and the contract, and none
of them calls `state.py`.

## Output contracts

Every agent returns a report the session can act on without reading the
files it read:

- **Facts carry a label and a location.** KNOWN FACT with `file:line`,
  INFERENCE with what it rests on, UNKNOWN with what would settle it, RISK.
  An inference is never written as a fact (`.ai/AGENTS.md`, rule 6).
- **A question comes back, never gets asked.** A subagent that needs a
  decision returns `## QUESTIONS_NEEDED` — question, options, why it blocks,
  context — and stops. The session records it with `state.py ask --batch`,
  the human answers in the conversation or on the `[Answer]:` line of
  `task.md`, and the work resumes with the answer in the brief.
- **The reviewer is bounded.** It reads the diff and the files it touches,
  runs only the named tests through `step_test_command`, writes no scripts and
  no timing loops, and stops at its call cap, saying what it did not reach.
  It assumes the implementation is wrong and looks for unintended behaviour
  change, hidden coupling, races, retry and idempotency problems, contract
  breaks, scope creep and weakened checks. With `focus: security` (a full-mode
  task whose domain axis is 2) it reads for authentication, authorization,
  secrets, payments, personal data and webhooks first.
- **A verdict is recorded, not announced.** `state.py review --verdict …
  --tier … --report -` writes the findings into `task.md` §Review and the
  journal; BLOCKER and HIGH findings in scope are fixed as one batch, MEDIUM
  and LOW go into the record with `state.py memory risk add`.

## Escalation

```
FAST → BALANCED → STRONG → EXPERT
```

One step at a time, for one task, on a named trigger that is written into the
task record — never the whole fleet, never starting at EXPERT because it
exists, never a failed reasoning task retried on a cheaper model. Three or
more parallel agents run on FAST or BALANCED. The STRONG triggers: the review
of a finished change (`ai-reviewer`), a full-mode plan whose design is open
(`architect`), root cause after a BALANCED diagnosis failed once or a bug in
concurrency, retries, caching or data integrity, a costly reversible design
choice with two or more viable options. The EXPERT triggers: STRONG could not
settle it (`confidence: uncertain`, or two STRONG results contradict each
other), an irreversible design with several viable options — core data model,
public API or event contract, service split — or the final check of a
production-incident root cause before a human acts on it. `runtime-gate`
enforces the budget: an EXPERT launch asks on Claude Code (explains on Codex)
unless the plan allows it, and `expert.max_per_task` caps how many a task may
make.

A STRONG or EXPERT agent receives a compact brief — the context summary,
`file:line` facts, the question and the options — and asks for a specific file
when it needs one. It is never sent to explore the repository.

## What never gets delegated

The final synthesis, and anything the user reads as a conclusion. A cheap
agent may collect the evidence for it; the main session writes it. The same
holds for the plan, the weight, the test run and the release: `/rr-plan`,
`state.py weight`, `state.py verify` and `/rr-ship` are the session's work.

## The honest answers

An agent that cannot find something says so. `ai-discovery` returns UNKNOWN
with what would settle it rather than a plausible guess; `log-reader` lists
every failure rather than the first; `ai-reviewer` writes `not reached
(budget)` under EXAMINED AND CLEAN rather than a clean bill for files it did
not open; `architect` ends with explicitly flagged concerns, especially where
the design contradicts a policy or the constitution. A FAST reader stops at
the first plausible match, which is why a trace through installed third-party
code goes to `ai-discovery` on BALANCED: there a wrong answer reads exactly
like a right one.
