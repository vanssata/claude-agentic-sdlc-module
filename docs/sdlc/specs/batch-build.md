# Spec: Batch build — one task for a whole plan, parallel implementers and fixers, a review loop that stops at the human after three failed passes

Intent: `docs/sdlc/intent/batch-build.md`

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Written 2026-10-28 on `feat/batch-build` (worktree of `new-refactor`, HEAD `520e065`). The developer's
intent is the two messages quoted in the intent file; the design is the session's (the session runs
above the STRONG tier, so no `architect` was spawned — `model-routing.md` "What never gets delegated").
Constitution: `docs/sdlc/constitution.md` C1–C6 are cited where a decision rests on them.

## Requirements

- **R1 One task for a whole plan** (outcome O1). A programme plan `docs/sdlc/plans/<slug>.md` can be run
  as one task: every row of **Order of work** is one step of that task, with the row's files, tests and the
  rows it depends on. A human row (G1, G2 …) is not a step: every row after it names every step before it
  in `after`, and its question is asked, before the next wave is dispatched, the moment those steps are
  done; while it is pending `step-done` and `close` exit 4 and nothing is dispatched, so the rows after it
  wait for the human.
- **R2 Dependencies are data** (O2). `state.py start --plan-file` accepts `"after": ["s1", …]` per step.
  An unknown id or a cycle is refused at `start` (exit 1, naming the step; a cycle closed by an implied
  ordering names that edge). In a batch task, two steps that name the same file or pattern — among their
  files or their tests; `./a` and `a`, `src/*.py` and `src/a.py` count as shared — are ordered, the later
  row after the earlier, and `start` prints every ordering it added, so two implementers never hold one
  file at the same time. A standard task's steps run one after another and are not reordered.
- **R3 The next wave is a command** (O2). `state.py steps [--ready] [--json]` lists the steps with status
  and `after`; `--ready` prints the steps not yet done (pending or in progress) whose dependencies are all
  done, one id per line, nothing and exit 0 when there is none; `--json` adds `batch_policy`, the section in
  force. Read-only.
- **R4 Parallel implementers** (O2). `/rr-build-all` dispatches the ready steps to subagents on the batch
  tier (`batch.tier`, shipped BALANCED), at most `batch.parallel` at once, each under the implementer
  contract (`agents/implementer.md`): the step's goal, its files as the only allowed files, the other
  steps' files as forbidden, its tests, its own test command. A subagent runs its step's tests directly
  (`step_test_command` with the step's files) and never `state.py`; the session records `step-done` after
  the wave. `SCOPE_CHANGE_REQUIRED` from a subagent becomes `start --amend`; `QUESTIONS_NEEDED` becomes
  `ask --batch` and stops the run.
- **R5 Tests once, failures fixed in parallel, as one batch** (O3). After the last step
  `verify --scope all` runs once to the end. Every failure is classified (`testing.md` "Reading a failure");
  the new regressions are grouped by the file they point at and fixed by parallel fixer subagents on the
  batch tier, at most `batch.parallel` at once, with the rule "fix the code, never the test"; then one
  `verify --scope all --after-fix "…"`. An existing failure goes to `known-risks.md`; an environment
  failure gets one more run.
- **R6 Review, findings fixed in parallel, loop until it passes** (O3, O4). One `ai-reviewer` at the mode's
  tier records a verdict. `pass` closes the loop. `pass_with_findings`: the in-scope HIGHs are fixed by
  parallel fixers as one batch, `verify --after-fix`, `review --closes`. `blockers_open`: every in-scope
  BLOCKER and HIGH is fixed by parallel fixers as one batch, `verify --after-fix`, then a **full** review
  pass again — the loop repeats until a pass.
- **R7 Three failed passes stop at the human** (O4). A batch task has its own budgets,
  `batch.review_rounds_max` (shipped 3) and `batch.max_suite_runs` (shipped 8), read wherever the standard
  `review_rounds_max` and `tests.max_suite_runs` are read today. The pass past the budget is refused with
  `REVIEW_BUDGET` (exit 6) exactly as today — the dialog pick or the terminal command — so the fourth
  verdict is the human's; the run past the suite budget is `SUITE_BUDGET` (exit 6) the same way.
- **R8 Per task, with a project default** (O5). `start --batch --by "<who>"` turns the flag on and journals
  it (`batch_set`); `start --no-batch` opts out of a project default; with neither flag,
  `weight.json.batch.default` decides (shipped `false`). `--batch` without `--by` and `--batch` with
  `--no-batch` are refused.
- **R9 Switching during the task** (O6). `state.py batch off --by "<who>" --why "<text>"` returns the task
  to the standard loop: the standard budgets apply from then on, counting what was already spent (a task
  with two review passes behind it has its next verdict at the human), the session implements, and
  `/rr-build`, `/rr-review`, `/rr-ship` continue it. `batch on` during a task lowers the rigor, so it is the
  human's: a terminal outside an agent session or `AI_UNATTENDED`, else `APPROVAL_REFUSED` (exit 5) with
  the terminal command printed. Both are journaled as `batch_set`.
- **R10 What batch does not change** (C4, C5, C6). The mode comes from the weight of the union of the
  steps' files and only rises; the scope guard, the two facts, the e2e rule, the gate in full mode, the
  `--confirm` of full_irreversible and the three nevers are untouched. A batch task in full mode still ends
  at the human's `approve`.
- **R11 Visible state** (O6). `status` shows one `batch:` line (on, by whom, review and suite spent against
  the batch budgets, the ready steps); `handoff` one `Batch:` line; `task.md` shows `after` on each step
  line and the batch flag in §Weight. `status` stays ≤ 20 lines, the handoff ≤ 30.
- **R12 Texts** (O1). A new skill `/rr-build-all` (≤ 300 lines, model-free, no removed command or agent)
  carries the loop; `/rr-plan`, `/rr-build` and `/rr-review` name the batch cases in a few lines each;
  `using-riskrails.md`, `docs/weight.md` and `README.md` explain it; the template `weight.json` ships the
  section and its mirror (`weight.md`) is regenerated; `skills/project-update/history/` is rebuilt.
- **R13 No migration** (C1). A project table without a `batch` section runs with the shipped defaults
  (`BATCH_DEFAULTS` in `state.py`); `/rr-setup --update`'s three-way merge adds the key to a project table
  the user never edited and to one they did (a new key merges cleanly).
- **R14 Journal** (I3). `batch_set` joins `EVENT_TYPES` and `FORGEABLE_EVENTS`: `state.py event` refuses
  to write it.

## Design

**Components.**

- `weight.json` gains one top-level section, `batch` (§Interfaces). `weight.py mirror()` prints it on a
  `Batch:` line so the mirror still carries the whole table.
- `state.py`:
  - `BATCH_DEFAULTS` and `batch_policy(policy)` — the section with every key filled in.
  - `budget(policy, state, key)` — `review_rounds_max` and `max_suite_runs` for this task: the batch value
    when `state["batch"]["on"]`, else the standard one. `cmd_verify`, `cmd_review` and `status_lines`
    read budgets only through it; the two refusal texts name `batch.<key>` when the batch value applied.
  - `parse_steps` keeps `after` (a list of ids) on each step; `check_steps(steps)` refuses an unknown id,
    a self-reference and a cycle (depth-first with a visiting set), then `order_shared_files(steps)` adds
    the earlier step to the later one's `after` when they share a file and returns the lines `start` prints.
  - `ready_steps(state)` — pending steps whose `after` are all `done`, in plan order. `cmd_steps` renders
    them. `cmd_step_done_v7` starts the first *ready* pending step instead of the first pending one, which
    is the same step when nothing has `after`.
  - `state["batch"] = {"on": bool, "by": str|None, "why": str|None, "since": ts|None}`;
    `apply_defaults_v7` adds `{"on": False}` to a task from before this change.
  - `cmd_start`: `--batch`, `--no-batch`, the default from the policy; the `batch_set` event; the
    `next_action` text for a batch task; the printed ordering lines.
  - `cmd_batch(on|off)`: `off` is open to anyone with `--by` and `--why`; `on` takes the human route
    (`human_route`, no dialog). Both rewrite `next_action`, the handoff and `task.md`.
  - `status_lines`, `handoff_lines`, `task_md_lines`: the lines of R11.
- `skills/rr-build-all/SKILL.md`: resume or plan → waves → verify and parallel fixers → review and
  parallel fixers → loop → `/rr-ship`; the switch; keeping context small.
- The implementer brief is the shared `agents/implementer.md` (already the contract for one step); the
  subagent is a plain spawn — `general-purpose` under Claude Code, an unnamed spawn under Codex — on
  `$STATE profile --tier <batch.tier>`.

**Data flow of one batch run.**

```
/rr-build-all <plan>
  └─ /rr-plan: rows → steps{id, files, tests, after}; human rows → questions; weight(union) → mode
  └─ start --batch --by <who> --plan-file steps.json [--mode <higher> --by …]
  loop over waves:
     steps --ready ──► ≤ parallel implementers (BALANCED) ──► RESULT | SCOPE_CHANGE_REQUIRED | QUESTIONS_NEEDED
                                                              └─ step-done <id> each
  verify --scope all ──red──► log-reader (FAST) classifies ──► ≤ parallel fixers ──► verify --after-fix
  review (mode's tier) ──► pass ─────────────────────────────────────────────────► /rr-ship
                      └──► pass_with_findings ──► fixers ──► verify --after-fix ──► review --closes ──► /rr-ship
                      └──► blockers_open ──► fixers ──► verify --after-fix ──► review again (full pass)
  pass 4 ──► REVIEW_BUDGET (exit 6): the human's verdict, in the dialog or the terminal
  batch off --by … --why … at any point ──► the standard loop from here
```

**Alternatives rejected.**

1. *A fourth mode `lite` on the ladder.* The mode is the rigor — plan shape, reviewer tier, gate — and the
   weight sets it; batch is a loop shape with its own budgets and can run at any rigor (a whole-plan task
   lands in full by its weight, and the user's own T-2026-10-28-011 ran exactly so). A mode would also fight
   "the mode only rises" (lite below light?) and the names (`lite` next to `light`). Rejected.
2. *Each implementer records its own step through `state.py verify --scope step` and `step-done`.* Parallel
   writers on `current.json` and the journal; the lock is per command, not per wave. Rejected: subagents run
   the test command directly, the session records.
3. *A new `ai-implementer` agent file.* Redesign 2.4 removed it and `tests/test_skills_surface.py` refuses
   the name in any skill. A plain spawn with the implementer contract as its brief works in both runtimes.
4. *A scoped re-review after a `blockers_open` fix batch, as `/rr-review` does.* A fix batch across many
   files by several subagents is a new change, and the developer asked for "tests, then the review again";
   the budget is counted per pass, so a full pass costs no extra budget over a scoped one. Rejected.
5. *A separate `.ai/policies/batch.json`.* The budgets belong beside the budgets they replace, in one table
   with one mirror and one `/rr-setup --update` merge. Rejected.
6. *`after` in the `--steps "id:a,b:t"` shorthand.* A fourth `:` field would read as a file. `after` is
   plan-file only; a one-scope or a short task does not need it.

## Interfaces

**`weight.json`** (template and project; every key optional, the shipped values are the defaults):

```json
"batch": {"default": false, "review_rounds_max": 3, "max_suite_runs": 8, "parallel": 3, "tier": "BALANCED"}
```

**`--plan-file`** entry: `{"id": "s3", "files": ["a.py"], "tests": ["tests/test_a.py"], "after": ["s1", "s2"]}`;
`after` optional, ids must exist, no cycle.

**Checks at `start` and `batch on`**: the `batch` section's numbers are whole numbers ≥ 1, `default` a
boolean, `tier` one of FAST/BALANCED/STRONG/EXPERT; a tier above BALANCED with `parallel` ≥ 3 is refused
(the fan-out rule). A reader (`status`, the handoff) falls back to the shipped value instead of failing.

**`step_done` event data**: `{"step_id", "files": n, "own": [paths inside the step's files and tests],
"others": [the rest of the diff], "unready": [dependencies not done when it was recorded]}`; `step-done`
prints `n still open: …` while steps remain, `all steps done` only when none does.

**`state.py`** (new or changed):

```
start … [--batch --by WHO [--why TEXT] | --no-batch]      flag on/off; default weight.json batch.default
steps [--ready] [--json]                                   read-only; --ready: one ready id per line
batch on|off --by WHO [--why TEXT]                         off: anyone; on: the human's route (exit 5 otherwise)
```

Exit codes unchanged: 1 refusal, 4 question pending, 5 `APPROVAL_REFUSED`, 6 `REVIEW_BUDGET` /
`SUITE_BUDGET`. Journal: `batch_set` `{"on": bool, "by": …, "why": …, "via": terminal|unattended|null}`,
actor `human` when `on` came through the human route, else `agent`.

**State** (`current.json`): `"batch": {"on": false|true, "by": null|str, "why": null|str, "since": null|ts}`;
each step gains `"after": [ids]`.

**Lines.** `status`: `batch: on by <who> · review <n>/<max> · suite <n>/<max> · ready <ids|none>`.
`handoff`: `Batch: on · ready <ids|none> · review <n>/<max> · suite <n>/<max>`. `task.md` §Plan step line:
`- s3 · a.py · tests/test_a.py · pending · after s1, s2`; §Weight: `batch: on by <who> at <ts> — <why>`.
`start` prints `ordered: s3 after s1 (shares a.py)` per added ordering.

**Skill** `/rr-build-all [<path to docs/sdlc/plans/<slug>.md> | --resume]`.

## Policy conformance

- **C1, safety.md** — nothing outside the task is fixed; an implementer's observations go to
  `known-risks.md`; every subagent reads only the files its step names.
- **C3** — a refactoring row of a plan is still its own task (the skill says so); batch never mixes kinds.
- **C4** — the task's files are the union of the steps' files; a subagent's `SCOPE_CHANGE_REQUIRED` is
  answered with `start --amend`, never around the guard.
- **C5, the three nevers** — no commit, no approval, no lowering: `batch on` mid-task and the fourth verdict
  are the human's; `batch off` raises rigor and is free.
- **C6, `skills/CLAUDE.md`** — the budgets and the switch change when the human is asked: behaviour 2,
  declared; this task starts `--mode full --by`, one STRONG review, the gate.
- **testing.md** — three scopes kept: a subagent runs only its step's tests, the suite once after the last
  step, e2e once; failures fixed as one batch; a test is never edited to pass.
- **model-routing.md** — the fan-out is at BALANCED (three or more parallel agents never above it); one
  STRONG reviewer per pass; the session writes every conclusion.
- **review-economy.md §3** — "two passes" becomes a per-task number read from the table; the principle
  (fix as one batch, never one finding at a time, the pass past the budget is the human's) is kept.
- **context-management** — the session reads RESULT blocks and `file:line` excerpts, never a subagent's
  diff or a log.
- **Codex** — the skill names tiers and the contract; `tests/test_shared_prompts_model_free.py` keeps the
  shared tree model-free.

## Flagged concerns

- **FC1 A weaker autonomy budget, by configuration.** Three review passes and eight suite runs before a human
  is more than today's two and two; "never past a budget" is kept only because the budget itself moved.
  Mitigations: the default is off; the project sets it in a policy file that is frozen during a task; every
  pass is a full review that must pass before `close`; the gate in full mode stays. Declared behaviour 2.
- **FC2 `start --batch --by` is journaled, not gated.** An agent could start a batch task on its own — and
  could even `close --abandon` a task and start it again with `--batch --by "<the human's name>"`, so the
  human route on `batch on` mid-task is a convention backed by the journal (actor `agent`, the abandon and
  the restart both on record), not a wall. The skill text and the project default are the policy, the
  journal line the audit. A `batch.start: human` knob would close it; not built here.
- **FC3 The scope guard is per task, not per subagent.** An implementer can edit another step's file; the
  contract forbids it, the step ordering keeps shared files apart, and the `step_done` event records which
  changed paths were the step's own and which were not (`own` / `others`), with a printed note in a batch
  task. The diff itself is cumulative across a wave and checked against the task's files only. A
  per-subagent guard is out of scope.
- **FC4 One working tree, several writers.** Two fixers on the same file would collide: fixers are grouped
  by file; steps that share a file are serialized (R2). Not a lock.
- **FC5 This repository's own table.** `.ai/policies/weight.json` is task-protected, so the section reaches
  it only through `/rr-setup --update` after the merge, by the human; until then this repository runs
  batch with the code defaults.
- **FC6 Cost.** A batch task may spend three STRONG reviews. The developer chose it; `/rr-status --cost`
  shows it, and `batch off` is one command.
- **FC7 Codex parallelism** depends on its spawn facility; the skill names the tier and the contract, not
  the mechanism.

## Open questions

none blocking. The human row of a plan is a question, not a step (decided, R1).
