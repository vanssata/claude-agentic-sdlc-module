# Architecture

How the pieces fit: the installed home, a project's `.ai/`, the pipeline, the
state, the hooks, the two adapters. Everything below is provider-neutral
except the last section.

## Three layers

```
~/.claude/  or  ~/.codex/               the installed home (npx riskrails)
├── CLAUDE.md | AGENTS.md               the managed block: the rules an agent is unsafe without (≤ 2 560 B)
├── settings.json | config.toml         model, effort, limits, hooks — from profiles/<plan>.json
├── agents/                             Explore, log-reader, ai-discovery, ai-reviewer, architect — tier baked in
├── hooks/                              ai-guard.py + guard/, cap-large-read, context-guard, runtime-gate, dialog-gate, …
├── skills/                             rr-setup, rr-spec, rr-plan, rr-build, rr-build-all, rr-review, rr-ship, rr-status (+ aliases)
│   └── ai-task/state.py                the state machine every skill drives
└── riskrails/
    ├── ai/                             the shared tree: policies, agent contracts, workflows, templates, using-riskrails.md
    ├── ai-path                         prints which copy of a shared file applies to a project
    ├── routing.md                      the model ladder and thresholds, read on demand
    └── profile.json                    the plan resolved: tiers, budgets, the dialog tool

<project>/
├── CLAUDE.md | AGENTS.md               the same block, project scope (≤ 2 048 B), the rest is yours
├── docs/sdlc/                          constitution.md; intent/, specs/, plans/, adr/
└── .ai/
    ├── AGENTS.md                       the router: one row per job → the policy that answers it
    ├── VERSION                         the schema (10)
    ├── project/                        the surveyed knowledge base, every claim labelled
    ├── policies/                       weight.json + weight.md, dialog.json, path-guard.json, testing.md, coding.md, safety.md, security.md
    ├── rules/                          rules scoped to directories, rendered into their instruction files
    ├── state/                          state.json, handoff.md, session.json, decision.json, consent.jsonl, logs/   (not committed)
    ├── reports/<task-id>/              task.md + events.jsonl per task
    └── memory/                         the compact record, in packages mode
```

A project reads a shared file from `riskrails/ai/<path>` unless it has its own
at `.ai/<path>`, which overrides it and stops receiving the plugin's changes.
`.ai/AGENTS.md` is a router, not a rulebook: a job → the one file to read, so
nothing loads that the task does not need.

## The pipeline

```
/rr-spec   idea → docs/sdlc/specs/<slug>.md        brainstorm on record, architect on STRONG, Flagged concerns
/rr-plan   spec → docs/sdlc/plans/<slug>.md        files, order, risks, proof per requirement, rollback
           task → weight → mode → plan → start     six axes, three modes; the plan shaped by the mode; the scope guard armed
/rr-build  edit inside the task's files; each step's own tests; the suite once, to the end; failures as one batch
/rr-review one adversarial pass at the mode's tier; BLOCKER and HIGH fixed as one batch; one scoped re-review
/rr-ship   close measures the two facts; full mode asks the human; the commit is the human's
```

`/rr-build-all` runs a whole plan as one task: every row a step with its
`after` dependencies, the ready rows to parallel implementers on BALANCED,
the suite once, parallel fixers, the review loop until it passes or the budget
stops at the human. `/rr-status` shows where a task stands at zero model cost;
`/rr-setup` builds `.ai/` and keeps it current.

**The weight picks the mode, the mode picks the ceremony.** Scope,
reversibility and coverage are measured from the tree; behaviour, domain and
novelty are declared by the session with evidence; hints from the project's
table raise an axis by one. W ≤ 2 is **light**: an inline plan, no review
unless a fact is red, no human stop. W 3–7 is **guarded**: the plan in plan
mode, which the human accepts; one review on BALANCED; e2e runs. W ≥ 8, or
reversibility or domain at 2, is **full**: a written plan, `architect` when
the design is open, one review on STRONG with a security focus when domain is
2, and the human approves the tree. Reversibility and domain are re-scored
from the real diff at `verify` and `close`; the mode only rises during a task,
and lowering it is the human's ([weight.md](weight.md)).

**The session implements.** Reading is delegated — a lookup to `Explore`, a
long log to `log-reader`, a trace that needs judgement to `ai-discovery` —
because a file read into the session is paid for on every later turn and an
agent returning twenty lines is cheaper than five tool results that stay. The
edit itself is not delegated: the session holds the plan, the scope and the
reason for every change, and a subagent that writes code loses all three at
the handoff. The one exception is the batch build, where each step is small
enough to brief completely.

## The state

`state.py` is the only writer of the task state, and every decision it makes
is deterministic — a measurement, never a judgement. No model writes or reads
these files on the pipeline's behalf; the skills call the commands and read
their one-line answers.

| File | Written by | Holds |
|---|---|---|
| `.ai/state/state.json` | `state.py` | the task (schema 7): id, goal, workflow, mode, stage, files, tests, steps, the weight with its axes and re-scores, verify runs, review passes, the gate, the batch flag, the facts |
| `.ai/reports/<task-id>/events.jsonl` | `state.py`, the hooks | the journal, append-only: `weight_set`, `mode_set`, `verify_run`, `review_verdict`, `question_asked`, `question_answered`, `gate_requested`, `gate_approved`, `decision_*`, `consent_*`, `model_fallback`, `risk_recorded` … with the runtime and the actor of each |
| `.ai/reports/<task-id>/task.md` | `state.py`, rendered from the state and the journal | the record a human reads: `## Weight`, `## Plan`, `## Questions` (kept as written, with the `[Answer]:` lines), `## Verify`, `## Review` (one fenced pass each), `## Changes`, `## Verdict` |
| `.ai/state/handoff.md` | `state.py` | at most thirty lines: mode, step, files, decisions, pending questions, the resume point; injected at session start; removed at close |
| `.ai/state/session.json` | `context-guard.py` | the runtime driving, the prompt count, the last human turn |
| `.ai/state/decision.json`, `consent.jsonl` | `state.py`, `dialog-gate.py` | an open decision for the runtime's dialog, and the picks the human made |
| `.ai/state/logs/<task-id>/` | `state.py verify` | the full test output per run; the archived `state.json` after close; never committed |

The commands, by group: `start` (with `--amend`, `--mode --by`, `--plan-file`,
`--batch`), `step-done`, `steps`, `batch`, `verify`, `review`, `close`;
`approve`, `reject`; `weight`, `status`, `handoff`; `ask`, `answer`,
`questions`, `decision`, `consent`; `event` (the hooks' channel, which refuses
the forgeable types); `profile`; `recall` and `memory`. A task started by an
older plugin answers `status`, `handoff` and `questions` and can be dropped
with `close --abandon`; everything else refuses it as `old surface`.

**The two facts.** `close` measures, never asks: (a) a green whole-suite
`verify` on the tree as it is now; (b) every changed file inside the task's
files. Green and green in light mode closes the task. A red fact in light mode
makes a review owed; guarded and full owe one anyway, and e2e. A change whose
files since the green run are all documents may close on the documents' own
tests (`doc_tests` in `testing.md`) without a second full run.

**The approval gate** exists in full mode only. `close` records
`gate_requested`, prints the facts and the way to approve, and stops. With the
dialog switch on, the approval is a pick in the runtime's own question tool,
recorded by `dialog-gate.py` and consumed once; otherwise it is `state.py
approve --by <name>` in the human's own terminal, which refuses without a TTY.
A `full_irreversible` task (reversibility and domain both 2, or irreversible
content in the diff) takes `approve --confirm <operation>` in the terminal,
never the dialog. The approval covers the tree presented; a changed tree
invalidates it. `reject --by --why` holds `close` at exit 5 until the tree
changes. `AI_UNATTENDED=1` passes every human check and stamps the record
`unattended`.

**Budgets** are refusals with a printed command, and running past one is the
human's: two whole-suite runs per task (`SUITE_BUDGET` on the third), two
review passes (`REVIEW_BUDGET`), three review rounds and eight suite runs in a
batch task, one EXPERT launch per task on most plans.

## The hooks

The rules an instruction file states, the hooks enforce ([hooks.md](hooks.md)):
one guard process on every tool call (decision, git, paths, scope), the read
cap, the context guard, the runtime gate, the dialog gate. A guard is regex
over a command line or a path — a tripwire for the honest mistake, not a
sandbox — and it fails open, so a broken hook never locks a session. The
characterization golden of 1 341 recorded decisions proves that a change to
the engine moved no decision.

## Cost

Three things cost tokens: the session re-reading its context on every turn,
the agents it spawns, and the suite runs that print into the context. The
design answers each: one short always-loaded file per runtime and a router for
the rest; readers on the cheapest tier returning `file:line` excerpts; test
output written to a log and read by `log-reader`, never into the session. The
mode keeps the expensive parts — a written plan, a STRONG review, a human
stop — for the changes whose weight earns them. `/rr-status --cost` reads the
local transcripts of both runtimes and shows the split per task, model and
tier at zero model cost; the per-task figures in the installed profile are
reported next to it, never enforced.

## The two adapters

Claude Code and Codex differ in four places, and each is handled once:

- **Where files go and what an agent looks like.** `npx riskrails` renders the
  same templates to `agents/*.md` with YAML frontmatter, or to `agents/*.toml`
  with the model, effort and `sandbox_mode` pinned, because a Codex agent
  file's model beats the one asked for at launch.
- **How hooks are registered.** A `hooks` block in `settings.json`, or
  `hooks.json` trusted in `/hooks`. Codex has no `Read` hook, no `Setup`, no
  `Notification`, no `StopFailure`; the guard sees `apply_patch` as an `Edit`
  with every path checked, and `runtime-gate` learns an outage at
  `SubagentStop` instead of `StopFailure`.
- **How a human is asked.** `AskUserQuestion` or `request_user_input` for
  the dialog; a Codex hook cannot ask, so a budget check that asks on Claude
  Code explains on Codex.
- **Which model a tier is.** `profiles/<plan>.json` per runtime, resolved into
  `profile.json` ([routing.md](routing.md)).

Everything else — `.ai/`, `state.py`, the skills, the weight, the guards'
rules — is one implementation, and `tests/test_end_to_end.py` drives one task
through both runtimes over one `.ai/` tree to prove it.
