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
├── skills/                             rr-setup, rr-spec, rr-plan, rr-build, rr-build-all, rr-review, rr-ship, rr-status
│   └── ai-task/                        the state machine every skill drives
│       ├── state.py                    the entry: a shim that sets fs.ENTRY and calls rr_state.cli.main
│       ├── rr_state/                   the package behind it, layers 0 to 9 (below)
│       ├── memory_sync.py              the pre-push validator entry: the shim in .git/hooks/pre-push runs it by path
│       └── sensors.py, weight.py, memory_*.py   sibling modules (the map is below)
│   └── project-update/                 what /rr-setup --update runs
│       ├── update.py                   the entry: the docstring, sys.path, then rr_update.cli.main
│       ├── rr_update/                  the package behind it, layers 0 to 6 (below)
│       └── render_instructions.py, history/   the renderer of the managed blocks; the shipped versions
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
    ├── VERSION                         the schema (11)
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

`state.py` is only the entry: it sets `fs.ENTRY`, re-exports the names the tests
use and calls `rr_state.cli.main`. The code lives in the package
`skills/ai-task/rr_state/`, one module per job, in layers 0 to 9 (the exact map
is `tests/fixtures/state/partition.json`, checked by `python3
tools/state-partition.py`):

| Layer | Modules | Job |
|---|---|---|
| 0 | `fs`, `locks` | paths, clock, `die`, text and subprocess reads; the file locks |
| 1 | `runtime`, `questions`, `ledger` | which runtime drives; parse and render `## Questions`; the consent ledger |
| 2 | `journal` | the append-only `events.jsonl` |
| 3 | `policy`, `task` | pure reads of `weight.json` / `dialog.json`, modes; load and save the task dict |
| 4 | `gate`, `dialog`, `report` | the approval gate; the dialog, its picks and the authority checks; the two facts and the `task.md` lines |
| 5 | `profile`, `memory_cmd` | the resolved plan and its advice; `recall` and `memory` |
| 6 | `handoff` | `handoff.md` and the resume point |
| 7 | `questions_cmd`, `gate_cmd`, `report_cmd`, `steps`, `start`, `verify`, `review`, `close` | one module per command group |
| 8 | `dialog_cmd` | `decision` and `consent` |
| 9 | `cli` | the parser and `main` |

- **Imports only go downward** (R10): a module imports from lower layers and
  nothing imports `cli` or the entry; `tests/test_state_layout.py` builds the
  graph and fails on a cycle or an upward edge.
- **Three classes, no more** (R4): `Runtime` and `Profile` are frozen value
  objects, `Ledger` holds `consent.lock`; everything else is a function, and the
  task stays the dict that `load` returns. `main` builds the `Runtime` and
  passes it down; no module global names it.
- **Functional core, imperative shell** (R16): functions that parse, render or
  decide take data and return data, with no file, clock or subprocess; I/O sits
  in `fs`, `locks`, `journal`, `task`, `ledger`, `profile` and the command
  modules. The seams tests patch are module attributes such as `fs.now`.
- **The hooks never import the package** (R15): they run as `python3 -I -S` on
  the standard library, `hooks/guard/dialog.py` re-implements what it needs of
  the ledger, and nothing under `rr_state/` imports `hooks/`.

`update.py`, the project updater, has the same shape: the entry keeps its
docstring (the usage and the exit codes), sets `sys.dont_write_bytecode`, puts
its directory on `sys.path` and calls `rr_update.cli.main`; it re-exports
nothing. The package `skills/project-update/rr_update/` holds the code in
layers 0 to 6 (the map is `tests/fixtures/update/partition.json`, checked by
`tests/test_update_layout.py`):

| Layer | Modules | Job |
|---|---|---|
| 0 | `paths`, `files` | the file lists, `HERE` and the plugin's directories; hashing, reads, git |
| 1 | `history`, `gate`, `siblings` | the shipped versions; who may confirm; `weight.py` loaded by path |
| 2 | `kept`, `plan` | the files the update keeps and refuses to read; the `Plan` of one run |
| 3 | `weights`, `blocks`, `shared`, `rules`, `cleanup`, `hints` | one module per kind of row |
| 4 | `build` | `build_plan`: every row of one run |
| 5 | `apply`, `report` | write the rows, abort part-way; print them |
| 6 | `cli` | the parser and `main` |

Tests reach a name through the module that owns it (`from rr_update import
paths`, then `paths.SHARED`), never through the entry.
`tests/test_update_characterization.py` pins what the entry prints, returns and
leaves on disk over the regenerate fixtures.

The memory code beside `state.py` has the same discipline without a package
directory: `memory_sync.py` is the pre-push validator entry, and it stays at
that path because every project's `.git/hooks/pre-push` shim runs it by path
(`SELF` in `memory_io` points at it, and the shim text written into a project
stays byte for byte). It defines only `_git_out`, `base_for_new_branch`,
`pre_push` and `pre_push_cli`; the rest of packages mode lives in ten sibling
modules, in layers 0 to 5 that import only downward (the map is
`tests/fixtures/memory/partition.json`, checked by `tests/test_memory_layout.py`):

| Layer | Modules | Job |
|---|---|---|
| 0 | `memory_io` | the path constants (`HERE`, `VALIDATOR`, `SELF`), `MemoryError_`, the clock, JSON and byte reads, the atomic write, the clone lock, git |
| 1 | `memory_config`, `memory_packages` | the policy's schema and `MemoryConfig`, the mode; the packages on disk, the id and seal lookups (`sealed_task_ids`), the batch ledger |
| 2 | `memory_verify`, `memory_hook`, `memory_risks` | the findings, `verify` and the range check the validator runs; the shim, `enable`, `disable`; the risk writers |
| 3 | `memory_cleanup`, `memory_migrate` | cleanup, restore, redaction, pack; the move from files to packages |
| 4 | `memory_export` | the outbox, the compaction into a package, export and the close hook `after_close` |
| 5 | `memory_status` | the lines `memory status` prints; `show` |
| 6 | `memory_sync` | the validator entry above |

`rr_state/memory_cmd.py` reaches a name through the owner module, `close.py`
calls `memory_export.after_close`, `rr-setup/setup.py` uses `memory_config` and
`memory_io`; nothing imports a name through `memory_sync`.
`tests/test_memory_sync_characterization.py` pins what the packages-mode
commands print, return and write against `tests/fixtures/memory/goldens/sync/`.
`memory_compact.py`, `memory_format.py` and `memory_store.py` are unchanged.

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
