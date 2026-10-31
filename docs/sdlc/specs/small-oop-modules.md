# Spec: Small modules — splitting the plugin's large scripts (functional core, three classes)

Status: proposed · 2026-10-31 · brainstorm `docs/sdlc/intent/small-oop-modules.questions.md`
(Hybrid mode, `agentic-sdlc-modes` Q1 = B; Q9–Q14 added 2026-10-31 after an external review
the developer pasted — §External review; Q16–Q19 added 17:41 after the session's assessment and a
Codex second opinion on `gpt-6-astra` — §Optimisation; Q15, the blockade, is pending for the
developer, answered 17:46: only `state.py` work is blocked) · the plan on file predates Q9–Q19 (FC12) · next:
`/rr-plan docs/sdlc/specs/small-oop-modules.md` again

The slug `small-oop-modules` stays — the plan, the roadmap and the questions file name it.
The title no longer says OOP because the design is not one: modules split by responsibility,
a class only where a resource or a value needs one (Q3, Q9, Q11), nothing inherited.

## Intent

**Problem.** Six scripts carry the plugin's decisions in files too large to read whole:
`skills/ai-task/state.py` 5 367 lines, 244 top-level functions, 0 classes, 70 module
globals, four of them mutated at run time through three `global` statements (`RUNTIME`,
`MUTATING` at `:5342`, `LOCK_DEPTH` `:1349`, `DIALOG_PICK` `:2911`);
`skills/project-update/adopt.py` 2 219; `skills/project-update/update.py` 2 146;
`skills/ai-task/memory_sync.py` 1 571; `hooks/guard/paths.py` 1 545; `hooks/runtime-gate.py`
1 214 (re-measured 2026-10-31 17:15, `wc -l`, while T-2026-10-31-1650 is in flight). Every one is over the
~4 000-line read cap or close to it, so an agent that changes one reads it through
`grep -n` and bounded windows, never as a whole — the T-2026-10-20-003 reviews found an
untested BLOCKER twice in exactly that mode. The sections `state.py` already draws
(journal and questions · plan profile · the gates · the dialog · the schema-7 surface ·
the batch loop · start/verify/review/close · the compact record) are the seams; the file
just never split along them. The open register lists 158 items against `state.py` alone.

**Outcome.**
- O1 `python3 <home>/skills/ai-task/state.py <cmd>` answers every subcommand with the same
  stdout, stderr, exit code, journal line and file on disk as before — proven by a
  characterization golden recorded on the tree before the first move, byte-identical after.
- O2 Every module of the split code is measured by size with 600 lines as the advisory line
  (Q16: over it is noted in the task report with the reason, never a failing check), and no
  function is reachable only through a module global that changes at run time.
- O3 A reader can open one module and see one job: the journal, the questions file, the
  gate, the dialog ledger, the batch loop — each with its tests named; a class exists only
  where a resource or a value needs one (three in WP1, R4), nothing inherits from anything.
- O4 Nothing else moves: `.ai/VERSION` stays 11, no migration, no change to `.ai/state/*`
  shapes, the installed copy is replaced by `npx riskrails` as today.
- O5 The hooks stay a separate world: nothing under `hooks/` imports the package and
  nothing in the package imports `hooks/guard`; the `python3 -I -S` boundary is unchanged.

**Affected users and systems.** Every `/rr-*` skill (they shell out to `state.py`), the
test suites that import `state`, `sensors`, `weight` from `skills/ai-task` on `sys.path`
(`tests/test_ai_task_state.py:26-35`, `tests/memory_harness.py:17`,
`hooks/memory-pre-push.py:19`), the installer (`bin/riskrails.js:368` calls `state.py
profile detect`; `:772` sets the executable bit on it; the skills tree is copied as a
directory), the pylint gate (`.pylintrc` names `state.die`), `docs/architecture.md`,
`CONTRIBUTING.md` and `.ai/project/`. User projects see no change: same commands, same
files, same refusals.

**Constraints and non-goals.** Python 3.11+, standard library only (CONTRIBUTING). A
refactoring changes no behaviour and is never mixed with a feature or a fix (C3; Q6). The
entry path is a contract — 109 files name it (Q2). `bin/riskrails.js` is out (Q7).
Not a goal: fewer subcommands, a new state schema, a plugin API for other tools, or
performance work beyond "not slower".

**Open questions.** See the last section; none blocks the plan of WP1.

### Decisions taken

- **Scope of the split: which files does this spec cover?** — state.py as WP1 with its own plan and task; the other five as later work packages under the same spec, each with its own plan, task and golden, in the order of their size *(Q1, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z)*
- **The entry point: what happens to the path every caller uses?** — skills/ai-task/state.py stays, as a thin CLI entry (argparse, dispatch, main) over a package skills/ai-task/rr_state/ — the 109 files that name the path, the test shim (import state; state.main()), bin/riskrails.js:368 and the installed copy are untouched *(Q2, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z)*
- **Shape of the modules: how far does the OOP go?** — one module per seam the file already draws (journal and questions, profile, gates, dialog, the schema-7 surface, batch, start/verify/review/close, compact record), with a class only where state is threaded through many functions — the task record, the journal, the resolved profile, the runtime context; no class per command *(Q3, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z)*
- **Proof that no behaviour changes (C2, C3): what pins the refactoring?** — characterization first — the existing suites plus a new CLI golden recorded on the tree before the split (every subcommand's --help, and a scripted task run's stdout, journal and task.md with timestamps normalised), byte-identical after; each WP green on verify --scope all and e2e before the next starts *(Q4, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z)*
- **Order of work: where does this refactor sit against everything else on the roadmap?** — next after the risk burndown in flight (T-2026-10-30-2251-risk-burndown-b5 and the rest of its loop); every other row — ROADMAP §1 operating modes, §2 open rows, the multi-agent intent — is blocked until the last WP of this spec closes *(Q5, by Ivan Kakurov via prose instruction of 2026-10-31, recorded by claude via prose at 2026-10-30T23:06:50Z)*
- **An open risk or a bug met while splitting: what does the refactoring do with it?** — records it in the register (state.py memory risk add) and moves on; a fix is its own bugfix task after the WP closes — a refactoring changes no behaviour (C3), and a bugfix starts with its failing test (C2) *(Q6, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:50Z)*
- **bin/riskrails.js (1 442 lines, JavaScript, the installer): in or out?** — out — a different language and toolchain, and a change to how user projects are installed scores behaviour 2 (C6, weight.json examples), so it would drag every WP into full mode *(Q7, by claude · Hybrid self-answer (agentic-sdlc-modes Q1=B) via prose at 2026-10-30T23:06:51Z)*
- **The risk-aware multi-agent intent that triggered this spec: what is written now?** — an intent file only — docs/sdlc/intent/risk-aware-multi-agent-adlc.md with the capability assessment, the gap list and the reduced scope, status blocked by this spec; its spec and plan are written after the last WP closes, against the split code *(Q8, by Ivan Kakurov via prose instruction of 2026-10-31, recorded by claude via prose at 2026-10-30T23:06:51Z)*
- **Classes: which of the spec's six survive the external review of 2026-10-31?** — three: `Runtime` and `Profile` as frozen dataclasses (value objects), `Ledger` as the one resource-holding class (lock, append, read, mirror); the task record stays the dict `load`/`save` return today, the JSON being the contract hooks, tests and both runtimes read; the journal and the questions file stay functions over a path *(Q9, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **Hook isolation: may rr_state and hooks/guard share code?** — no: nothing under `hooks/` imports `skills/ai-task/rr_state` and nothing under `rr_state` imports `hooks/guard`; the duplication between `hooks/guard/dialog.py` and `rr_state/dialog.py` is intentional and stays; the layout test fails on either import; WP5 and WP6 split inside `hooks/` only *(Q10, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **Forbidden constructs: what does the layout test refuse under rr_state/?** — no inheritance and no Abstract/ABC base, no dependency-injection container, no interface or Protocol with one implementation, no repository or service class per JSON operation, no class that is only a namespace of static methods; the layout test greps for `ABC`, `abstractmethod`, `Protocol`, `staticmethod` and any class base other than a dataclass or `Exception` *(Q11, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **Core and shell: where do pure functions, I/O and the seams live?** — functional core, imperative shell: parse, render and decide functions take data and return data; I/O sits in `fs`, `locks`, `journal`, `task` load/save, `ledger` and the command modules; the clock and command-runner seams stay module-level functions (`fs.now`, `fs.now_ms`, `fs.run_text`, `sensors.git`) a test patches as module attributes — no Clock or Runner object, no injected parameter *(Q12, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **Granularity: the spec's nine-layer ladder or the review's eight files?** — the ladder stays the partition, read as eight responsibility groups (store, journal, questions, decisions, lifecycle, profile and runtime, reporting, cli); a module exists for one cohesive responsibility, never to satisfy the 600-line layout test, and two modules of one group merge when the import graph allows *(Q13, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **Timing: when does WP1 start against T-2026-10-31-1650-dialog-background?** — the golden is recorded and the WP1 task started only after that task and every other task editing `state.py` or `hooks/guard/dialog.py` has closed; the golden is re-recorded if any such task lands between the recording and the first move *(Q14, by claude · self-answer after the external review of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T17:17:46Z)*
- **The 600-line limit of R3: a failing check or an advisory measure?** — advisory: the layout test prints module sizes and fails only on an import cycle, an upward edge, a `global` statement, a forbidden construct or a hooks/rr_state crossing; a module over 600 lines is noted in the task report with the reason *(Q16, by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31, over 70 % confident, via prose at 2026-10-31T17:41:29Z)*
- **Classes: a quota of three, or a rule?** — a rule: a class needs a named resource it holds or an invariant it keeps, written in its docstring; `Runtime`, `Profile` and `Ledger` pass it today, a fourth needs the same sentence, not a spec change *(Q17, by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31, over 70 % confident, via prose at 2026-10-31T17:41:29Z)*
- **The optimisation proposals outside the split: where are they recorded and in what order?** — in this spec's Optimisation section as separate tasks, none inside a WP, in the order: task classification, activity scope for documents, review strength by named risk, spec budget as defaults, runtime and cost measurement per task, state ownership audit before any merge *(Q18, by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31, over 70 % confident, via prose at 2026-10-31T17:41:29Z)*
- **WP6 (hooks/runtime-gate.py): keep it in the order, or make it conditional?** — conditional: planned only after the measurement task shows Codex in use, or when a Codex-side bug forces a change to the file; WP1–WP5 unaffected *(Q19, by claude · self-answer after the session's assessment and the Codex Astra second opinion of 2026-10-31, over 70 % confident, via prose at 2026-10-31T17:41:29Z)*
- **Does the split still block every other roadmap row (Q5)?** — no: the split blocks only work that edits `state.py` internals or the extracted interfaces; the policy tasks of the Optimisation section and urgent fixes run as separate tasks, never mixed with a WP — this narrows Q5 *(Q15, by Ivan Kakurov, reply "Only state.py work" in the app, recorded by claude via picker at 2026-10-31T17:46:24Z)*

## Requirements

Each is testable; the outcome it serves is in brackets. Items marked † were corrected after
the independent check (see that section).

- **R1 Entry contract.** `skills/ai-task/state.py` stays at its path, executable, runnable
  as `python3 -I state.py` and as `import state; state.main()`. Every subcommand, flag,
  default, help text, exit code and output line is unchanged. The entry keeps its own
  `sys.path.insert(0, <its dir>)` (a suite deletes `sys.path[:2]` after importing it). [O1]
- **R2 Package beside the entry.** The code moves to `skills/ai-task/rr_state/` (a Python
  package; the directory `ai-task` itself is never imported — it is on `sys.path`). The entry
  becomes the parser and dispatch plus the re-exports of R6, under 200 lines. A missing
  package prints one line naming `npx riskrails` instead of a traceback. [O3, O4]
- **R3 One module, one seam, one layer.** † Every top-level function of today's file is
  assigned to exactly one module (a partition, produced by a script at plan time, not the
  indicative map below); module sizes are reported, 600 lines advisory (Q16); each module
  sits in one layer of the Design's ladder. `tests/test_state_layout.py` prints line counts,
  checks completeness of the
  partition (every `def` of the golden tree's file found once), and the import graph (R10).
  The pylint `too-many-*` checks are off in `.pylintrc` and are not the measure. [O2]
- **R4 A class needs a resource or an invariant; three pass today; nothing inherited; two
  process-wide memos, no `global`.** † (Q9, Q11, Q17, replacing the six classes of the first
  draft.) The rule, not a quota: a class holds a named resource or keeps a named invariant,
  and its docstring says which; a fourth class needs that sentence, not a spec change. `Runtime` (runtime name and the mutating
  flag, a frozen dataclass built by `main` exactly as today's three code paths do) and
  `Profile` (the resolved plan, tiers, budgets, dialog tool — a frozen dataclass) are value
  objects; `Ledger` (`consent.jsonl` + `decision.json` behind `consent.lock`) is the one
  class that holds a resource. Everything else is a function: the task record stays the
  dict that `load` returns and `save` writes — the JSON on disk is the contract hooks, tests
  and both runtimes read, and a wrapper object would put a second shape in front of it; the
  journal is `append_journal` / `read_journal` / `emit` over a path; the questions file is
  `parse_questions` / `render_*` / `write_questions`. Refused under `rr_state/`, and
  grepped by the layout test: a class base other than a dataclass or `Exception`, `ABC`,
  `abstractmethod`, `Protocol`, `staticmethod`, a dependency-injection container, an
  interface with one implementation, a repository or service class per JSON operation.
  Process-wide state is limited to two single objects: the lock re-entrancy counter
  (`locks.py`, one per process — nested `question_lock` calls on two paths must not
  deadlock) and the dialog-pick memo (`dialog.py`). No `global` statement anywhere; the
  layout test greps for it. Functions the suites call directly with today's signatures
  (`journal_line`, `load`, `sync_answers`) take the runtime values as keyword parameters
  whose defaults equal today's import-time values (`runtime="unknown"`,
  `mutating=False`). [O2, O3]
- **R5 Characterization golden first.** † Before the first move, a commit of its own adds
  `tests/test_state_characterization.py` and `tests/fixtures/state/goldens/`: (a) `--help`
  of the root parser and of every subcommand and sub-subcommand, enumerated from the parser
  so a missing one fails; (b) four scripted runs on the harness's scratch project — light
  (`start` → `step-done` → `verify` → `close`), guarded (plus `ask`, `answer`, `review`),
  full (plus `approve` refused from an agent session, `handoff`, `status`, `questions
  --format md`), and dialog-on (`decision open --kind commit`, a pick, the approve label,
  `consent audit`) — recording stdout, stderr, exit codes, `events.jsonl`, `task.md`,
  `handoff.md`, `decision.json`. The environment is pinned (`AI_RUNTIME`, the agent markers,
  `USER`, `git -c user.name -c user.email`, a fixed commit date). Normalised by a named list
  `NORMALISE`: timestamps, task ids, `duration_s`, `diff.base_commit`, session / tool-use /
  consent ids, the scratch path — and the entry's path as the exact token `<STATE_PY>`,
  never a generic path regex (a generic one would hide a moved `__file__`). Red on any
  other difference. [O1]
- **R6 Existing tests are the proof, not the patient.** † No test file is edited in WP1
  except `tests/test_install_dry_run.py` (R9) and the two new files of R3 and R5. The names
  the suites reach as `state_mod.<name>` (33 on 2026-10-31: `validate_label`,
  `AGENT_MARKERS`, `journal_line`, `load`, `is_document`, `abandon_old`, `LEDGER_LINE_MAX`,
  … and the modules `state_mod.json`, `state_mod.os`) are re-exported by the entry; the list
  is generated from `grep -oh 'state_mod\.[A-Za-z_]*' tests/*.py` at plan time and checked
  by the layout test. Moved code keeps calling `json.dump` and `os.replace` as module
  attributes (the suites patch them there), never `from json import dump`. A test that
  checks `state_mod.__file__` still sees the entry. Moving the suites onto package imports
  is OQ3. [O1]
- **R6a One entry-path constant.** † Seventeen `__file__` uses in today's file mean "the path
  of state.py": the dialog pick and `validate_label` compare it with a label's script path,
  the refusal texts and `state_label` print it, `load_resolver` and the migrations lookup
  walk `dirname` from it, the Codex check searches it. After the move each would resolve to
  `rr_state/<mod>.py`. One constant `ENTRY` in `fs.py`, set by the entry before it imports
  `cli` (default: the package's parent joined with `state.py`), replaces every one; the
  layout test fails on any other `__file__` under `rr_state/`. [O1]
- **R7 Lint gate.** `pylint $(git ls-files '*.py')` stays at 10.00/10 with the shipped
  `.pylintrc`; the only edit to it is `never-returning-functions`, which gains the
  package's `die`. No new `disable` — `cyclic-import` (R0401) stays on, so a cycle costs
  the score as well as R10. [O2]
- **R8 Not slower.** `state.py --help` and `state.py status` on the scratch project: the
  median of 20 runs after the split is within 10 % of the median on the golden tree.
  Measured in the task report (`.ai/reports/<id>/task.md`), not by a timed test — the
  suite already has two wall-clock classes that run serially. [O1]
- **R9 Installed and copied.** † The installer copies a skill as a whole directory
  (`bin/riskrails.js:759-760`, `__pycache__` skipped) and prints one `installed:
  skills/<name>` line per skill; `tests/test_install_dry_run.py:379-395` checks that listed
  files exist. The delta adds `skills/ai-task/rr_state/__init__.py` and
  `skills/ai-task/rr_state/cli.py` to that list. The `chmodX` list (`:772`) is unchanged;
  the install, routes and dry-run suites stay green. [O4]
- **R10 Import direction.** † Modules import only downward in the ladder of Design §Layers;
  nothing imports `cli` or the entry. The layout test builds the import graph from the
  `import` lines of every module under `rr_state/` and fails on a cycle or an upward edge.
  The graph is produced and checked **before** the golden is recorded, on the partition
  script's output, so a cycle is found on paper, not after a move. [O3]
- **R11 Docs in the same task.** `docs/architecture.md` (the tree and "the state machine
  every skill drives"), `CONTRIBUTING.md` (where the code lives, how to run one module's
  tests), `.ai/project/*.md` where they name `state.py` internals. [O3]
- **R12 Risks met, not fixed.** A bug or an open risk found while moving code is recorded
  with `state.py memory risk add` and left in place; the golden pins the current behaviour
  including the bug. [C3; Q6]
- **R13 Later work packages, same pattern.** WP2–WP6 (Design §Work packages) each start
  with their own golden, keep their entry path and executable bit, and close green before
  the next starts. WP6's shape is an open question (OQ1). [O2, O3]
- **R14 Rollback.** Every WP is one task on one branch; `git revert` of its commits
  restores the single file. No state, schema or policy file changes, so nothing has to be
  migrated back. [O4]
- **R15 Hook isolation.** (Q10) No module under `hooks/` imports `skills/ai-task/rr_state`
  (or `state`), and no module under `rr_state/` imports anything under `hooks/`. The hooks
  run as `python3 -I -S` with the standard library only (`hooks/ai-guard.py:27`,
  `hooks/dialog-gate.py:17`); `hooks/guard/dialog.py` re-implements what it needs of the
  dialog ledger on purpose and keeps doing so. The layout test reads the `import` lines of
  both trees and fails on a crossing. WP5 and WP6 split inside `hooks/` only. [O5]
- **R16 Functional core, imperative shell.** (Q12) A function that parses, renders or
  decides takes data and returns data and touches no file, clock or subprocess: the policy
  reads over a loaded dict, questions parsing and rendering, `weight`, step ordering, the
  two facts' comparison, the handoff and task.md line builders. I/O lives in `fs`, `locks`,
  `journal`, `task` (load/save), `ledger`, `profile` detection and the command modules,
  which call the core and write. The seams a test needs are module-level functions patched
  as attributes — `fs.now`, `fs.now_ms`, `fs.run_text`, `sensors.git`, `json.dump`,
  `os.replace` — never a Clock or Runner object and never an injected parameter;
  `sensors.py` is the precedent (`state.py:84`: "measurement only; it never writes this
  file"). The partition script of R3 labels every function core or shell; the label is
  recorded in the module docstring, and a core function that imports `os`, `subprocess`,
  `time` or `fcntl` fails the layout test. [O3]

## Design

### Layers and the module map for WP1 (`skills/ai-task/rr_state/`)

Indicative: the functions named are today's; the plan's first step produces the exact
partition (R3) and the import graph (R10) before anything moves. A module imports only
from layers below its own. Corrected after the independent check (its B2): `human_route`,
`claim_runtime`, `current_tree`, `open_gate`, `sync_answers` and `write_task_md` sit where
the callers' greps put them, not where the file's comments did. Read as responsibilities
(Q13), the ladder is eight groups — **store** (`fs`, `locks`, `task`), **journal**,
**questions**, **decisions** (`ledger`, `gate`, `dialog`, `authority`), **lifecycle**
(`start`, `steps`, `verify`, `review`, `close`), **profile and runtime**, **reporting**
(`report`, `handoff`), **cli** — close to the eight files the external review proposed; the
finer modules exist because `lifecycle` alone would be about 2 000 lines and because the
import graph needs the layers. A module is never created to satisfy the 600-line layout
test; two modules of one group merge when the graph allows it. The Class column marks the
three classes of R4; every other row is functions over the dict and the paths.

| Layer | Module | Holds | Class |
|---|---|---|---|
| 0 | `fs.py` | `ENTRY` (R6a), `find_root*`, `die`, the `*_path` helpers, `logs_dir`, `read_text`, `read_lines`, `now`, `now_ms`, `current_tree`, `run_text` | — |
| 0 | `locks.py` | `question_lock`, the one re-entrancy counter (today `LOCK_DEPTH`), `ledger_lock`, `LOCK_STALE` | — |
| 1 | `runtime.py` | detection only: `RUNTIMES`, `AGENT_MARKERS`, `agent_markers`, `installed_runtime`, `detect_runtime`, `runtime_home`, `own_runtime`, `other_runtime`, `installed` | `Runtime` (frozen dataclass: name, mutating) |
| 1 | `policy.py` | pure reads of `weight.json` / `dialog.json`: `weight_policy`, `mode_for`, `higher_mode`, `mode_setting`, `batch_policy`, `batch_on`, `budget`, `dialog_policy`, `dialog_on`, `is_document`, `documents_cover`, `NEVER_DOCUMENTS` | — |
| 2 | `journal.py` | `EVENT_TYPES`, `FORGEABLE_EVENTS`, size caps, `journal_line(..., runtime="unknown")`, `append_journal`, `read_journal`, `record`, `emit` (history + one journal line — exactly today's `emit`, no task.md write) | — (functions over `root`, `task_id`) |
| 3 | `task.py` | `load`/`save`/`apply_defaults*`, `claim_runtime` (stays inside `load`, exit 7 and `runtime_handoff` as today), `sealed_task_ids`, `next_task_id`, `valid_task_id`, `is_v7`, `in_flight`, `route_surface`, `old_surface_refusal`, `abandon_old` | — (the dict is the record) |
| 4 | `questions.py` | regexes, `parse_questions`, `parse_answer_body`, `parse_prose`, `render_*`, `question_block`, `write_questions`, `is_pending`, `set_pending` | — (core: parse/render; shell: write) |
| 4 | `ledger.py` | `ledger_path`, `ledger_append`, `read_ledger`, `latest_rounds`, `live_picks`, `read_decisions`, `write_decisions`, `next_decision_id`, `LEDGER_TYPES`, `LEDGER_LINE_MAX` | `Ledger` (holds `consent.lock`) |
| 4 | `gate.py` | gate state only: `guard_pending`, `request_gate`, `open_gate`, `close_gate`, `close_gate_from_file`, `gate_approved_for`, `confirm_names` | — |
| 5 | `dialog.py` | `label_argv`, `subcommand*`, `validate_label`, `state_label`, `dialog_questions`, `open_decision`, `dialog_payload`, `print_dialog`, `offer_decision`, `settle_decision`, `prune_decisions`, `mirror_ledger`, `sync_dialog`, `dialog_pick` (+ its memo), `valid_decisions`, `retire_approvals`, `pick_data`, `task_facts`, `audit_pick` | — |
| 6 | `authority.py` | who may act: `human_route`, `human_turn`, `refuse_approval`, `offer_approval`, `approve_command`, `gate_question_text` | — |
| 7 | `report.py` | `md_cell`, `task_md_lines`, `write_task_md`, `status_lines`, `schema_line` | — |
| 7 | `handoff.py` | `set_resume_point`, `recent_notes`, `handoff_lines`, `write_handoff`, `handoff_to` | — |
| 7 | `profile.py` | plan detection for both runtimes, drift ack, `PLAN_PROFILES`, `SAME_TIER`, `load_resolver` (via `ENTRY`) | `Profile` (frozen dataclass) |
| 8 | `questions_cmd.py` | `cmd_ask`, `cmd_answer`, `cmd_questions`, `apply_answers`, `sync_answers` (calls `open_gate` and `write_handoff`, so it lives above both) | — |
| 8 | `gate_cmd.py` | `cmd_approve`, `cmd_approve_v7`, `cmd_reject` | — |
| 8 | `dialog_cmd.py` | `cmd_decision`, `decision_open`, `decision_settle`, `apply_choice`, `cmd_consent` | — |
| 8 | `steps.py` | `parse_steps`, `_overlap`, `order_shared_files`, `check_steps`, `ready_steps`, `next_action_for`, `cmd_steps`, `cmd_batch`, `cmd_step_done_v7` | — |
| 8 | `start.py` | `task_files`, `arm_scope`, `added_lines`, `parse_declares`, `cmd_start`, `start_amend`, `rescore_*`, `weigh`, `cmd_weight`, `safe_sensor` | — |
| 8 | `verify.py` | `full_suite`, `suite_green`, `moved_detail`, `run_v7`, `e2e_*`, `cmd_verify` | — |
| 8 | `review.py` | `read_report`, `open_findings`, `verdict_matches_findings`, `review_next_action`, `cmd_review`, `review_closes` | — |
| 8 | `close.py` | `two_facts`, `close_owed`, `cmd_close_v7`, `archive_v7`, `memory_after_close` | — |
| 8 | `report_cmd.py` | `cmd_event`, `cmd_status`, `cmd_handoff`, `cmd_profile*` | — |
| 8 | `memory_cmd.py` | the `memory` / `recall` surface over `memory_store`, `memory_sync` (lazy imports kept) | — |
| 9 | `cli.py` | `main`: parser, subparsers, the three runtime resolutions exactly as today (topic mode → `unknown`; `profile` → short chain; else `detect_runtime`), `set_defaults(func=…)` | — |

Module sizes are checked by the layout test; `dialog.py` is the candidate for a further split
(`labels.py`) if it measures over 600.

### Data flow

```
state.py (entry) ── sets fs.ENTRY, parses argv ──► cli.main
                                     │  rt = Runtime(name, mutating)      resolved as today, three ways
                                     │  root = fs.find_root(args.root)
                                     ▼
                      command module  cmd_<x>(args, root, rt)
                        │ state = task.load(root, claim=…) ──► task.py   the dict, claim_runtime inside load, as today
                        │ journal.emit(root, state, …)     ──► journal.py one history entry + one journal line
                        │ report.write_task_md(…)            called by the ~15 command sites that call it today
                        │ questions.* (functions) · Ledger(root) · Profile  one file each
                        │ core functions in between: data in, data out, no I/O (R16)
                        ▼
                      sensors.py · weight.py · memory_*.py   unchanged sibling modules
```

`Runtime` carries what `RUNTIME` and `MUTATING` carry today and is passed explicitly; the
functions the suites call with fixed signatures keep keyword defaults equal to the old
import-time values (R4). `LOCK_DEPTH` stays one counter per process in `locks.py` — the
gate locks the questions file and `write_task_md` locks it again inside, and a per-object
counter would deadlock on the second descriptor. `DIALOG_PICK` becomes the memo in
`dialog.py`. Nothing else is process-wide.

### Order of moves inside WP1

0. Partition script + import graph on paper (R3, R10); fix the map until acyclic. 1. Golden
(R5) on the untouched tree; commit. 2. `ENTRY` constant replaces every `__file__` (R6a) —
still in the single file; golden green (this is the one move the golden must see as a
no-op). 3. Layers 0–1: `fs.py`, `locks.py`, `runtime.py`, `policy.py`; entry re-exports;
golden green. 4. Layers 2–3: `journal.py`, `task.py`. 5. Layer 4: `questions.py`,
`ledger.py`, `gate.py`. 6. Layers 5–7: `dialog.py`, `authority.py`, `report.py`,
`handoff.py`, `profile.py`. 7. Layer 8, one module per step. 8. `cli.py`; the entry shrinks
to the shim; layout test; docs (R11). Each move is one step with
`tests/test_state_characterization.py tests/test_ai_task_state.py
tests/test_dialog_contract.py tests/test_dialog_gate.py` as its step tests; the suite once
at the end (`verify --scope all`), then e2e.

### Work packages

| WP | File | Lines | Shape | Golden | Note |
|---|---|---|---|---|---|
| 1 | `skills/ai-task/state.py` | 5 256 | entry + `rr_state/` | new, R5 | this spec's plan |
| 2 | `skills/project-update/adopt.py` | 2 219 | entry + `adopt/` | the adopt suite's `--dry-run` fixtures | deletion gate text byte-identical |
| 3 | `skills/project-update/update.py` | 2 114 | entry + `update/`, migrations untouched | dry-run output over the fixture projects | `--confirm-delete` path guard spelling unchanged |
| 4 | `skills/ai-task/memory_sync.py` | 1 571 | modules beside `memory_store`, `memory_compact`, `memory_format` | `tests/fixtures/memory/goldens/` exists | packages mode `verify --fresh-clone` |
| 5 | `hooks/guard/paths.py` | 1 452 | already a package: split `paths.py` into rule groups | `test_guard_characterization` golden exists | **byte-identical guard golden**; CLAUDE.md `SH_WORD`/`SH_RE` invariant |
| 6 | `hooks/runtime-gate.py` | 1 214 | OQ1: single file (`.pylintrc`: "must run as a single file") or shim + package like `ai-guard.py` + `guard/` | new | **conditional (Q19)**: planned only after the measurement task shows Codex in use, or when a Codex-side bug forces a change; Codex re-approves a changed hook entry; the entry line must not change |

Order: 1 → 2 → 3 → 4 → 5, one task each, the next starting after the previous closed
green; 6 only on its condition (Q19). Every WP is a refactoring by C3; its weight is measured by `/rr-plan`
(Policy conformance gives the expected mode). WP2–WP6 each repeat step 0 and the
`__file__` audit of R6a for their own file before the first move.

### Alternatives rejected

- **A class per subcommand (Q3-B).** Forty classes with one method each; the ceremony hides
  the two things that matter — which file a command touches and which journal type it
  writes. Rejected for the reason the redesign rejected seven tiers.
- **Functions only (Q3-C).** Keeps the four run-time globals, so every module would still
  reach into shared mutable state; the import-direction rule (R10) could not hold.
- **A new entry and 109 rewrites (Q2-B).** Touches every skill, the installer and the docs
  for no behaviour gain, and breaks the installed copy until `npx riskrails` runs.
- **One big-bang commit.** The golden would catch a regression but not locate it;
  incremental moves with the golden green after each keep every diff reviewable.
- **Several scripts with their own CLIs** (`questions.py`, `dialog.py` …). The skills'
  `$STATE` variable and the journal's one-writer rule assume one process owns the task; two
  entry points would need a lock protocol — a behaviour change.
- **Six classes (this spec's first draft: `TaskState`, `Journal`, `QuestionsFile` as well).**
  A `TaskState` object puts a second shape in front of the JSON that hooks, tests and both
  runtimes read, and every function that takes the dict today would change signature or
  unwrap it; `Journal` and `QuestionsFile` would hold nothing but a path — a namespace, not
  an object. Dropped after the external review (Q9).
- **The review's eight flat files** (`state_store`, `journal`, `questions`, `decisions`,
  `lifecycle`, `profile`, `cli`, entry). The same responsibilities; but `lifecycle` would be
  ~2 000 lines and `decisions` ~1 500, and the import graph of the independent check (B2)
  needs the layers between them. Kept as the reading of the ladder, not as the partition (Q13).
- **Injected `Clock` and `Runner` objects.** The seam the suites use today is a module
  attribute (`state_mod.json.dump`, `state_mod.os`); an injected object would thread a
  parameter through ~40 command functions for a seam a patch already gives (Q12).
- **One shared package the hooks import.** It would break the `-I -S` boundary the hooks
  run behind; the duplication in `hooks/guard/dialog.py` is intentional (Q10).

## Interfaces

**The entry after WP1** (`skills/ai-task/state.py`; the re-export list is generated at plan
time, R6 — the names below are the 2026-10-31 grep):

```python
#!/usr/bin/env python3
"""<the current first docstring line — argparse prints it>"""
import json, os, sys                                # json and os: the suites patch state_mod.json.dump / state_mod.os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from rr_state import fs
except ImportError:
    sys.exit("rr_state/ is missing beside state.py: re-run `npx riskrails`")
fs.ENTRY = os.path.abspath(__file__)                 # R6a: the one path the package prints and compares
from rr_state.cli import main
from rr_state.fs import die, state_path, current_tree
from rr_state.runtime import AGENT_MARKERS
from rr_state.journal import journal_line, append_journal
from rr_state.task import load, valid_task_id, next_task_id, abandon_old, TASK_ID_RE
from rr_state.policy import is_document, mode_for, NEVER_DOCUMENTS
from rr_state.locks import LOCK_STALE
from rr_state.questions import parse_questions
from rr_state.questions_cmd import sync_answers
from rr_state.ledger import read_ledger, live_picks, LEDGER_LINE_MAX, LEDGER_TYPES
from rr_state.dialog import validate_label, dialog_payload, task_facts, LABEL_MAX
from rr_state.gate import close_gate_from_file, confirm_names
from rr_state.start import rescore_weight
from rr_state.close import archive_v7
if __name__ == "__main__":
    main()
```

**The three classes and the functions beside them** (shapes, not code; every method is a
function that exists today — R4):

```
@dataclass(frozen=True) Runtime(name: str = "unknown", mutating: bool = False)
                                                   built by cli.main, three resolutions as today
@dataclass(frozen=True) Profile(runtime, plan, tiers, budgets, dialog_tool)
  profile.detect(runtime) -> Profile   profile.read(home) -> Profile   profile.drift(p) -> dict | None
Ledger(root)                                       the one resource holder: consent.lock by O_EXCL
  .append(line) .read() .latest_rounds() .live_picks() .mirror(decisions)
task.load(root, required=True, claim=None, rt=None) -> dict      the record is the dict, as today;
task.save(root, state)                                           claim_runtime inside load, exit 7 unchanged
journal.append_journal(root, task_id, text) / read_journal(root, task_id) -> list[dict]
journal.emit(root, state, event, …)                history + one journal line, nothing else
questions.parse_questions(path) -> list[dict]      core: no I/O beyond the read it is handed
questions.render_*(…) -> list[str]                 core
questions.write_questions(path, lines)             shell
locks.question_lock(path) / locks.ledger_lock(root)        one re-entrancy counter per process
fs.now() / fs.now_ms() / fs.run_text(root, argv)   the seams, patched as module attributes
```

**Tests and fixtures added.** `tests/test_state_characterization.py` (R5),
`tests/fixtures/state/goldens/{help,light,guarded,full,dialog}.txt`,
`tests/test_state_layout.py` (R3, R4, R6, R6a, R10). `NORMALISE` is one named list in the
characterization module, listed in its docstring; `<STATE_PY>` is an exact-string
replacement of the entry's path.

**`.pylintrc` delta.** `never-returning-functions=sys.exit,argparse.parse_error,state.die,rr_state.fs.die`.

**`tests/test_install_dry_run.py` delta.** The installed-files list (`:379-395`) gains
`skills/ai-task/rr_state/__init__.py` and `skills/ai-task/rr_state/cli.py`.

**Config keys, schema, journal vocabulary, questions format, exit codes:** unchanged.

## Policy conformance

- **C1** — the golden records what the code does today, bugs included (R5, R12); the register,
  not the refactoring, carries the fix.
- **C2** — characterization before the change; the golden is committed first and runs red on
  any difference.
- **C3** — refactoring only: Q6, R12; the plan has no row that fixes, adds or removes
  behaviour. A finding that wants one becomes its own bugfix task.
- **C4** — each WP names its files; WP1 touches `skills/ai-task/state.py`,
  `skills/ai-task/rr_state/**`, the two new test files, the dry-run test, `.pylintrc`, the
  three doc files. An edit outside is `SCOPE_CHANGE_REQUIRED`.
- **C5** — no commit, push or approval by the agent; WP1's commit series is the human's.
- **C6** — weighed by effect on a user project's decisions: no guard decision moves, no
  `state.py` refusal changes, no approval or install path changes — behaviour 0, the
  weight table's first "this repository" example (`weight.json:197`). Expected mode by the
  table: **light or guarded**. The developer may raise it to full for a STRONG review
  (as B5 was raised); the spec does not score it full "for being a process" — CLAUDE.md
  names that mistake.
- **CLAUDE.md "A BLOCKER is closed only with a test that pins it"** — the golden is that test
  for the whole WP; a review BLOCKER on a specific move adds a case to it.
- **`.ai/AGENTS.md` #6** — `.ai/project/` entries that name `state.py` internals are
  relabelled in the same task (R11).
- **`.ai/policies/testing.md`** — step tests are the two state suites; `verify --scope
  all` once after the last step; e2e once; failures as one batch.
- **`~/.claude/riskrails/routing.md`** — the session implements; `/rr-build-all` would send
  the steps to BALANCED implementers but every step shares `state.py`, so `start` serialises
  them; row by row with `/rr-build` costs the same and keeps the diff in the session. Design
  was written in the session (Fable, the model the triggering intent names) and checked
  independently by `architect` on STRONG (FC10).
- **`.ai/policies/security.md` and the hooks' `-I -S` boundary** — R15: the package and the
  hooks never import each other; the layout test measures it. The duplication the external
  review noticed is a boundary, not a debt.
- **ADRs** — `docs/sdlc/adr/` does not exist; no accepted decision binds this spec.
- **Redesign spec R4 "size never gates"** — R3's 600-line limit is a code-layout test, not a
  weight input; it never changes a mode or a refusal (FC2).

## Flagged concerns

- **FC1 The scope guard and the SDLC flow disagree.** This spec was written while
  T-2026-10-30-2251-risk-burndown-b5 was in flight. The scope guard refused the Write tool
  for every path — `docs/sdlc/**` and the session scratchpad outside the repository alike
  (`SCOPE_CHANGE_REQUIRED`, `hooks/guard/scope.py:367`). The questions file went through
  `state.py ask --topic`, the sanctioned route; the spec and the intent, both new files,
  went through the shell, which the scope guard does not cover; the edit of the existing
  `ROADMAP.md` was refused by the runtime's own classifier and was not made (FC11). A guard
  written per task met a workflow that runs per activity, and the gap is a hole as much as a
  nuisance: an agent on a task can write any new document through `cat`. The human decides:
  an allow list for `docs/sdlc/**` and the scratchpad in the scope guard (allows what was
  denied — behaviour 2, full mode), or the rule that `/rr-spec` waits for a free tree. OQ2;
  not fixed here.
- **FC2 R3 looks like a size gate.** The redesign (spec R4) removed size from every gate. R3
  limits a module's length in a layout test; it decides nothing about a task. Stated so the
  plan does not reintroduce lines as a weight input.
- **FC3 The entry becomes a façade.** Re-exporting 33 names keeps the suites untouched (R6)
  but leaves two import paths for one function. Accepted for WP1; the cleanup is OQ3.
- **FC4 `/rr-build-all` gains nothing here.** Every WP1 step edits `state.py`; `start`
  serialises steps that share a file, so the implementers run one at a time. Use `/rr-build`
  row by row, or accept a serial batch for its review loop alone.
- **FC5 WP6 may not be splittable.** `.pylintrc` records that `runtime-gate.py` "must run as
  a single file" for two runtimes, and Codex drops trust on a changed hook entry. The
  `ai-guard.py` + `guard/` pattern shows a shim can work; whether the Codex entry survives it
  is OQ1, decided at WP6's plan with a live probe, never assumed.
- **FC6 Blocking the roadmap parks fixes.** Q5 blocks ROADMAP §2 (Memory M1/M9 bugfixes,
  the shared policy texts that still describe T0–T6, the three unprotected hooks) and §1
  until WP6 closes. The developer chose that on 2026-10-31 with one exception, the risk
  burndown in flight. A production-breaking hotfix in a user project is not covered by the
  exception; if one is needed, the human grants it in writing — this spec does not.
- **FC7 Eight Hybrid self-answers.** Every decision above was proposed and accepted by the
  agent under `agentic-sdlc-modes` Q1 = B, recorded `via prose` because a self-answer `via`
  does not exist yet (ROADMAP §1). Q5 and Q8 quote the developer's instruction verbatim. A
  human overturns any with `state.py answer --topic small-oop-modules Qn=<letter>` and the
  plan re-reads the file.
- **FC8 Golden normalisation can hide a diff.** The list grew after the independent check
  (M1); it is still the place a real change can hide. `NORMALISE` is reviewed as part of the
  golden commit (R5); a reviewer's first question is "what does `NORMALISE` erase", and the
  entry path is an exact token, never a regex.
- **FC9 Behaviour 0 and a 5 000-line diff.** C6 and the weight table put this change low;
  its blast radius is every skill. The mitigation is the golden plus the suites, not a
  higher mode; the developer may still raise the mode by hand, which the journal records.
- **FC10 Who designed this.** The skill says `architect` on STRONG; the triggering intent
  names Fable as the architecture model, and the session is Fable. The design was written in
  the session and sent to `architect` on `opus` for an independent check; two BLOCKERs and
  five HIGHs came back and are folded in (next section). Neither is a human review.
- **FC11 The ROADMAP was not updated.** The order of work (§0: risk burndown → this spec →
  the multi-agent intent; everything else blocked) is drafted but the edit of `ROADMAP.md`
  was refused while B5 is in flight (the auto-mode classifier, after the scope guard).
  The record is this spec and the questions file until a human applies the draft.

- **FC12 The plan on file is stale.** `docs/sdlc/plans/small-oop-modules.md` (written
  2026-10-31, not started) derives from the six-class draft: its R4 row expects "the six
  class names exist" in the layout test and spreads them over s3–s8. After Q9–Q14 the plan
  is re-derived with `/rr-plan`; nothing in it has run, so nothing is undone.
- **FC13 No second independent check.** The skill sends the design to `architect` on
  STRONG; this revision was not sent. The delta removes structure (three classes instead of
  six, functions over the dict) and adds two measurable rules (R15, R16); the first check's
  findings B1–L4 stand unchanged — H3 (lock re-entrancy) and H4 (fixed signatures) are
  untouched by dropping the wrappers. The source of the revision is model output the
  developer pasted (§External review), not a human review. The human may still ask for a
  STRONG pass before `/rr-plan`.
- **FC14 The naming comment is out of this spec's scope.** The same paste assessed the
  product name (RiskRails, about 8/10; `claude-agentic` rejected as runtime-bound). This
  spec takes from it only that the package prefix `rr_` follows the product name; domain,
  npm and trademark checks are a separate task and are not opened here.
- **FC15 Timing against the in-flight task.** Q14: WP1's golden is recorded only on a tree
  where T-2026-10-31-1650 (files `hooks/guard/dialog.py`, `skills/ai-task/state.py`) and
  every other task touching those files has closed, and the risk burndown the plan header
  names. A golden recorded earlier would pin a tree that changes under it.
- **FC16 This revision's questions file counts against T-1650.** `state.py status` after
  Q9–Q14: fact (b) RED, "outside the task's files: … small-oop-modules.questions.md". That
  task closes only once this spec and the questions file are committed on their own, as the `spec:` commit below;
  OQ2 remains the human's.

- **FC17 The blockade is narrowed, not lifted.** Q15 (the developer, 17:46) limits Q5 to work
  that edits `state.py` internals or the extracted interfaces. The Optimisation tasks and
  urgent fixes may start; a bugfix inside `state.py` still waits for the WP that owns the
  code, and ROADMAP.md still shows the old order (FC11).
- **FC18 The second opinion is a model, not a human.** Codex on `gpt-6-astra`, read-only, with
  the session's measurements as input, one run, 2026-10-31 17:35; its `file:line` evidence
  was spot-checked where it changed a decision (Q16, Q17, Q19) and not elsewhere. The
  developer named the agent; the EXPERT-tier rule of `routing.md` was met by that naming.

## Open questions

- **OQ1 (WP6, plan-time)** Shape of `runtime-gate.py`: single file, or shim + package. Owner:
  the planner of WP6, with a Codex `/hooks` trust probe on record.
- **OQ2 (human)** Scope guard allow list for `docs/sdlc/**` and the runtime scratchpad while a
  task is in flight, or "`/rr-spec` waits for a free tree". Owner: Ivan Kakurov. Behaviour 2
  if allowed; not this spec's work.
- **OQ3 (after WP1)** Move the suites from `import state` to `rr_state.*` and drop the
  re-exports. Owner: a later tests-only task.
- **OQ4 (WP1, plan-time)** The 600-line limit: confirm or tighten once the partition script
  measures the modules; the limit is a layout test, never a gate.
- **OQ5 (WP1, plan-time)** Whether `authority.py` (layer 6) is one module or folds into
  `dialog.py`; decided by the import graph of step 0, not by taste.

## Optimisation proposals (2026-10-31, the session's assessment merged with a Codex second opinion)

The developer asked how far the project is over-engineered. The session measured (source
25 074 lines, tests 28 108, docs 16 631; `state.py` 38 subcommands, 63 event types, six state
files per task; 54 tasks: light 5, guarded 33, full 16, nine raised to full by hand; a
four-minute guarded task 1,33M tokens; $1 707 API-equivalent since 2 October) and proposed
six changes; Codex on `gpt-6-astra` (read-only, the same question and measurements) returned
seven with `file:line` evidence. Verdict of both: the excess is in process and policy, not in
the code; the split lowers the context of later changes but not approvals, artefacts or
tokens per task. Merged, ranked, each its own task outside the WPs (Q18):

| # | Task | Evidence | Where the two differed, and what stands |
|---|---|---|---|
| 1 | **Task classification.** Drop behaviour scoring from generic keywords; trial light at W ≤ 3 while domain and reversibility still escalate; replay past tasks and inspect false negatives around approval, install and deletion | `skills/ai-task/weight.py:163`, `.ai/policies/weight.md:18` | session: light as the default; Astra: a calibration experiment first. Stands: the experiment, with the replay |
| 2 | **Activity scope for documents.** Spec and plan work names its document paths; a task owns its report and scratch paths; close-time scope equals write-time scope | `hooks/guard/scope.py:359`, `state.py:4269`, FC1 | session: a blanket `docs/sdlc/**` allow; Astra: no, that tree holds governance files. Stands: named paths per activity; the runtime's own classifier is outside either |
| 3 | **Review strength by named risk.** A manual raise to full needs a reason; STRONG for domain, irreversibility or an approval-boundary change, BALANCED otherwise | `state.py:3608`, `:3626`, `.ai/policies/weight.md:20` | session: BALANCED unless domain 2; Astra: irreversibility and approval boundaries matter too. Stands: the three named risks |
| 4 | **Spec budget as defaults.** Intent ≤ 60 lines, ≤ 12 requirements, ≤ 6 flagged concerns, evidence in linked material; `architect` on STRONG for a named architectural risk, not for behaviour 2 alone | `skills/rr-spec/SKILL.md:69`, this spec | session: caps; Astra: defaults with a justified exception, caps breed compound requirements. Stands: defaults |
| 5 | **Measure runtimes and cost per task.** Record runtime, mode, review rounds, refusals and cache-read volume per task; pause new Codex-facing capability until the numbers exist; keep Codex contracts and fixes | `docs/dialog-spike.md:105`, `state.py:2333` | session: freeze Codex; Astra: Claude-only transcripts are not proof of zero use. Stands: measure first, freeze only new capability (Q19 makes WP6 conditional on it) |
| 6 | **State ownership audit before any merge.** Writers, readers, lifetime, locking and recovery per file; merge only what is demonstrably redundant | `state.py:2328`, `:2162` | session: merge `decision.json` into `consent.jsonl`, `session.json` into `state.json`; Astra: different lifetimes may justify separate files. Stands: the audit, no merger committed |
| 7 | **Does the split block everything?** | this spec Q5, FC6 | both: only work touching `state.py` internals or the extracted interfaces. Decided so by the developer, Q15 |

Both reviews keep, untouched: characterization of observable behaviour including refusal
paths and exit codes (R5); human authorization bound to the session and the recorded command
(`state.py:2088`, `:2100`, `:2161`); hook isolation with its limited duplication (R15).

## External review (2026-10-31, model output pasted by the developer, 17:15)

The developer pasted an assessment of "split into OOP modules, SOLID throughout" against
this repository and asked for the spec to take it into account; where the session was over
70 % sure of the answer it recorded it (Q9–Q14, the developer's rule of 2026-10-31). Its
measurements (5 362 lines, ~244 functions) match the re-measurement within five lines.

| Point made | Checked against | Folded into |
|---|---|---|
| A full OOP/SOLID rewrite adds indirection and migration risk; split by responsibility, OOP only where there is state and invariants | Q3 already said so; the six classes of the first draft went further than that | title, O3, R4, Q9 |
| A rich `TaskState` complicates serialisation and compatibility; the JSON is a public contract | `load` returns the plain dict (`state.py:377`), `save` writes it (`:423`); hooks and both runtimes read the file | R4, Interfaces, Alternatives |
| `hooks/guard/dialog.py` does not import `state.py` on purpose (`python3 -I -S`); merging them breaks a security boundary | `hooks/guard/dialog.py:21-27` imports only the stdlib; `hooks/ai-guard.py:27`, `hooks/dialog-gate.py:17` | O5, R15, Q10 |
| `sensors.py` is the precedent for a reasonable extraction | `state.py:84` "measurement only; it never writes this file"; 457 lines, subprocess and git only | R16, Q12 |
| Functional core + imperative shell; eight files (`state_store`, `journal`, `questions`, `decisions`, `lifecycle`, `profile`, `cli`, entry) | the ladder of the independent check (B2) already groups this way; `lifecycle` as one file would be ~2 000 lines | Design §Layers (eight groups), Q13, Alternatives |
| OOP only for a resource/transaction holder, a transition with invariants, a dependency seam, a value object | `ledger_lock` holds `consent.lock` by `O_EXCL` (`:2513`); `Runtime` and `Profile` are values; the seams are module attributes the suites already patch | R4, R16, Q9, Q12 |
| Not: inheritance, `Abstract*`, a DI container, single-implementation interfaces, a repository/service per JSON operation, a static-method namespace class | none exists today (0 classes); the layout test keeps it so | R4, Q11 |
| Of SOLID, S matters; D and I at I/O boundaries; O on proven need; L irrelevant | — | R4, R16 |
| Extraction first, behaviour unchanged, the entry kept as a façade, each extraction its own small refactoring with characterization tests | already R1, R5, R6, Q4, Q6 | unchanged |
| Not mixed with the current task on `state.py` and `dialog.py` | T-2026-10-31-1650 in flight, at its gate | Q14, FC15 |
| The product name (RiskRails) | out of scope | FC14 |

## Independent check (architect, STRONG tier, 2026-10-31, read-only)

Verdict: **sound with corrections** — the thin entry, the golden-first order and the goal
hold; the first module map, the `Runtime` shape and the golden's coverage did not. Every
finding below was spot-checked in the session against the file before it was folded in.

| # | Finding | Folded into |
|---|---|---|
| B1 | 17 `__file__` uses mean "the path of state.py" — the dialog pick and `validate_label` compare it with a label's script path (`state.py:2407`, `:2807`), refusal texts print it, `load_resolver` and the migrations lookup walk `dirname` from it; moved as-is, every new label would be refused and the pick would fail closed | R6a, step 2 of the order, `<STATE_PY>` token in R5, entry sets `fs.ENTRY` |
| B2 | The first map had cycles: `human_route` → `dialog_pick` → `load` → `claim_runtime` → `emit` → runtime name; `offer_approval` ↔ `valid_decisions`/`open_gate`; `sync_answers` ↔ `write_handoff`/`parse_questions`; `current_tree` used by dialog but placed in a command module | the nine-layer ladder, `authority.py`, `questions_cmd.py`, `current_tree` in `fs.py`, step 0 import graph on paper |
| H1 | The suites patch `state_mod.json.dump` and `state_mod.os`; moved code must keep module-attribute calls | R6, entry imports `json`, `os` |
| H2 | "emit mirrors task.md" was a behaviour change (C3) and a cycle; today `emit` writes history and one journal line, ~15 command sites call `write_task_md` themselves | `journal.py` row, data flow |
| H3 | `LOCK_DEPTH` is per-process re-entrancy across nested `question_lock` calls (`:2149` inside `:4703`); on an instance it deadlocks | `locks.py`, R4 |
| H4 | `journal_line`, `load`, `sync_answers` are called by the suites with fixed signatures and read the globals | keyword defaults equal to import-time values, R4 |
| H5 | `Runtime.from_env` = detect + claim moved the claim ahead of `route_surface` / `guard_pending` / `sync_dialog` and merged `main`'s three resolutions | claim stays in `load`; `cli.py` keeps the three paths |
| M1 | Normalisation missed `duration_s`, `diff.base_commit`, `user.name`/`USER`, session / tool-use / consent ids, the plugin path, the env | R5 |
| M2 | No scripted run reached a dialog pick or a label, so the golden could not catch B1 or H3 | the dialog-on run, R5 |
| M3 | Line ranges overlapped; `questions.py` was already 623 lines | map by names, partition script, R3 |
| M4 | R9 as written was not observable (the installer prints per skill, not per directory) | R9 |
| M5 | `LOCK_STALE` is the ledger lock's constant, not the questions file's | `locks.py` |
| L1 | `-I` holds because the entry inserts its own directory; no `runpy`/`exec`/single-file copy anywhere; a stale `.pyc` is harmless | R1 |
| L2 | A home with the new entry and no package would traceback | R2, the entry's one-line exit |
| L3 | "pylint limits already in force" meant nothing (`too-many-*` off); `cyclic-import` stays on and would cost R7 | R3, R7 |
| L4 | `test_project_update.py:882-888` deletes `sys.path[:2]` after `import state` | R1 |

Not folded in: nothing. Open from the check: whether layer 6 stands alone (OQ5).
