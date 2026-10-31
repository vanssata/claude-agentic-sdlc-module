# Spec: Small modules — splitting the plugin's large scripts (functional core, three classes)

Status: proposed · 2026-10-31 · brainstorm `docs/sdlc/intent/small-oop-modules.questions.md`
(Hybrid mode, `agentic-sdlc-modes` Q1 = B; Q9–Q14 added 17:15 after an external review the
developer pasted; Q16–Q19 added 17:41 after the session's assessment and a Codex second opinion
on `gpt-6-astra` — §Optimisation; Q15 answered by the developer at 17:46: only `state.py` work
is blocked; Q20–Q24 added in the evening refine pass — spec budget, open concerns, parallel
implementers, one cut-over, the `RUNTIME` patch) · plan `docs/sdlc/plans/small-oop-modules.md`,
re-derived at `95b28ba` from this spec at `92fbacd` and amended in the same evening pass for
Q22–Q24 · next: the human commits spec, plan and questions file, then
`/rr-build-all docs/sdlc/plans/small-oop-modules.md` while no task touching `state.py` is in
flight (Q14)

Reviews — the external review of 17:15 and the architect's independent check — are in
`docs/sdlc/specs/small-oop-modules.reviews.md` (Optimisation 4: evidence in linked material).
Spec budget, as defaults (Optimisation 4): 17 requirements against the default of 12, kept
with the exception stated — each is one observable pin of a behaviour-0 refactoring, and
merging them would make the compound requirements the proposal warns against (Q20); six open
concerns (Q21), the rest listed as resolved with what closed each.

The slug `small-oop-modules` stays — the plan, the roadmap and the questions file name it.
The title no longer says OOP because the design is not one: modules split by responsibility,
a class only where a resource or a value needs one (Q3, Q9, Q11), nothing inherited.

## Intent

**Problem.** Six scripts carry the plugin's decisions in files too large to read whole:
`skills/ai-task/state.py` 5 367 lines, 244 top-level functions, 0 classes, 76 module
globals (names assigned at module level, counted by `ast`), four of them mutated at run time
through three `global` statements (`RUNTIME`,
`MUTATING` at `:5342`, `LOCK_DEPTH` `:1349`, `DIALOG_PICK` `:2911`);
`skills/project-update/adopt.py` 2 219; `skills/project-update/update.py` 2 146;
`skills/ai-task/memory_sync.py` 1 571; `hooks/guard/paths.py` 1 545; `hooks/runtime-gate.py`
1 214 (re-measured 2026-10-31 20:30 with `wc -l`, after T-2026-10-31-1650 closed in `4e8dddc`;
unchanged since 17:15, when that task sat at its gate with its edits already in the tree). Every one is over the
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

**Open questions.** See §Open questions; none blocks the plan of WP1.

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
- **The next extraction after the first moves: `setup.py` or the dialog and consent readers? (OQ-M1, from the earlier ADR 0001 version of this spec, `9aa0299`)** — the dialog and consent readers (A), with `setup.py` (B) later; A meant one shared stdlib reader replacing the copies in `hooks/guard/dialog.py` and `state.py`. **Superseded by Q10**: hooks and `rr_state` share no code, each keeps its own dialog reader, so the shared-reader part does not apply; the dialog code moves inside WP1 as `rr_state/dialog.py` (layer 5) *(OQ-M1, by Ivan Kakurov, 2026-10-31; marked superseded by Q10 by Ivan Kakurov's pick in the app, recorded by claude on 2026-10-31 when the ADR 0001 version was replaced in the merge `0671755`)*
- **Spec budget (Optimisation 4, defaults): 17 requirements against the default of 12 — merge, or keep with the exception stated?** — keep all 17; the exception is stated in the spec header: each requirement is one observable pin of a behaviour-0 refactoring, and merging them would make the compound requirements the proposal warns against *(Q20, by claude · self-answer in the refine pass of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T18:08:35Z)*
- **Flagged concerns after the refine pass: which stay open (the default is at most 6)?** — open: FC1 (OQ2), FC5 (OQ1), FC7, FC8, FC9, FC11; resolved, one line each with what closed it: FC2, FC3, FC4, FC6, FC10, FC12–FC18 *(Q21, by claude · self-answer in the refine pass of 2026-10-31, over 70 % confident by the developer's rule, via prose at 2026-10-31T18:08:35Z)*
- **Who implements WP1 and in what shape?** — `/rr-build-all` with parallel implementers on BALANCED (`sonnet`, Sonnet 5.5) at effort `high`; a module step creates one file under `rr_state/` and nothing else, waits only for the layers it imports, the cut-over step edits `state.py` once; the suite once after the last step, then one review, fixes as parallel batches — supersedes FC4 *(Q22, by Ivan Kakurov, instruction in the `/rr-spec` call of 2026-10-31 (evening): implementers on Sonnet 5.5 high in parallel where possible, waiting where needed, the whole code first and then review/test, big steps with minimal tests; recorded by claude via prose at 2026-10-31T18:37:09Z)*
- **Cut-over: once, or per layer band?** — once: between s2 and the cut every step is a new file checked by the layout test, pylint and an import; the four suites run at s2 and at the cut, `verify --scope all` and e2e once, then one review *(Q23, by claude · self-answer in the refine pass of 2026-10-31, over 80 % confident by the developer's rule of this pass, via prose at 2026-10-31T18:37:09Z)*
- **`tests/test_dialog_contract.py:314` patches `state_mod.RUNTIME` by name and calls `dialog_on(root)`, which reads the global through `own_runtime()` (`state.py:503`): edit the test, keep a process-wide memo, or forward the attribute?** — edit two lines of the test: the inert patch at `:133` is dropped, `:314` passes `runtime=runtime`; `dialog_on` and `own_runtime` default to `runtime="unknown"` (R4); WP1's only test edit beside R9, listed in R6, whose generated list also greps `patch.object(state_mod, "<name>")` *(Q24, by claude · self-answer in the refine pass of 2026-10-31, over 80 % confident by the developer's rule of this pass, via prose at 2026-10-31T18:37:09Z)*

## Requirements

Each is testable; the outcome it serves is in brackets. Items marked † were corrected after
the independent check (`docs/sdlc/specs/small-oop-modules.reviews.md`).

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
  checks completeness of the partition (every `def` of the golden tree's file found once —
  phase-aware, Q23: while the entry still holds the code it checks the modules present, once
  the entry is the shim exactly one home per def), and the import graph (R10).
  The pylint `too-many-*` checks are off in `.pylintrc` and are not the measure. [O2]
- **R4 A class needs a resource or an invariant; three pass today; nothing inherited; two
  process-wide memos, no `global`.** † (Q9, Q11, Q17.) The rule, not a quota: a class holds a named resource or keeps a named invariant,
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
  (`journal_line`, `load`, `sync_answers`, `dialog_on`, `own_runtime` — Q24) take the runtime
  values as keyword parameters
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
  except `tests/test_install_dry_run.py` (R9), two lines of `tests/test_dialog_contract.py`
  (Q24, below) and the two new files of R3 and R5. The names the suites reach as
  `state_mod.<name>` (33 on 2026-10-31: `validate_label`, `AGENT_MARKERS`, `journal_line`,
  `load`, `is_document`, `abandon_old`, `LEDGER_LINE_MAX`, … and the modules
  `state_mod.json`, `state_mod.os`) are re-exported by the entry; the list is generated at
  plan time from `grep -oh 'state_mod\.[A-Za-z_]*' tests/*.py` **and** from
  `grep -oh 'patch\.object(state_mod, "[A-Za-z_]*"' tests/*.py` (a string-named attribute
  the first grep misses — today only `RUNTIME`), and checked by the layout test. Moved code
  keeps calling `json.dump` and `os.replace` as module attributes (the suites patch them
  there), never `from json import dump`; the same for the package's own seams — `from
  rr_state import fs` and `fs.now()`, never `from rr_state.fs import now`. A test that checks
  `state_mod.__file__` still sees the entry. A re-export serves a read, never a patch:
  `test_dialog_contract.py:314` patches `state_mod.RUNTIME` and calls `dialog_on(root)`, which
  reads the global through `own_runtime()` (`state.py:503`); after R4 there is no global to
  patch, so that line passes `runtime=runtime` and the inert patch at `:133` is dropped — the
  two-line edit of Q24, read by the review. Moving the suites onto package imports is OQ3. [O1]
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

Module sizes are reported by the layout test (advisory, Q16); `dialog.py` is the candidate for a further split
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

### Order of moves inside WP1 (Q22, Q23)

0. Partition script + import graph on paper (R3, R10); fix the map until acyclic — `s0`, in
parallel with 1. 1. Golden (R5) on the untouched tree; its own commit — `s1`. 2. `ENTRY`
replaces every `__file__` (R6a), still in the single file; the four suites green — `s2`, the
one move the golden must see as a no-op, serial. 3. **Copy phase**: one step per module of
the map, each creating `rr_state/<mod>.py` and nothing else — the defs the partition assigns
to it, copied from `state.py` with their calls qualified by module (`fs.now()`, R16), the
core/shell label in the docstring; `state.py` is not edited, so the scope guard has nothing
to serialise and the implementers run in parallel, a step waiting only for the layers it
imports (layer 0 first, layer 8 last). Step test: the layout test on the partial tree (the
present modules' defs match the partition, import, hold no `global` or `__file__`) and
pylint on the new file (`undefined-variable`, `import-error` — the mechanical errors of a
move). 4. **Cut-over**, one step: `cli.py`, the entry shrinks to the shim (the copied defs
deleted, the re-exports of R6 added), the layout test's final form, `.pylintrc`, the dry-run
list (R9), the two lines of Q24; the four suites green. 5. Docs (R11), a step of its own,
parallel with 3. Then, once: `verify --scope all`, e2e, one review, fixes as batches — the
`/rr-build-all` loop. The golden therefore runs at s2 and at the cut, not after each layer
(Q23); what locates a mechanical error between them is static — pylint, the import, the
partition check — and every module is its own diff.

### Work packages

| WP | File | Lines | Shape | Golden | Note |
|---|---|---|---|---|---|
| 1 | `skills/ai-task/state.py` | 5 367 | entry + `rr_state/` | new, R5 | this spec's plan |
| 2 | `skills/project-update/adopt.py` | 2 219 | entry + `adopt/` | the adopt suite's `--dry-run` fixtures | deletion gate text byte-identical |
| 3 | `skills/project-update/update.py` | 2 146 | entry + `update/`, migrations untouched | dry-run output over the fixture projects | `--confirm-delete` path guard spelling unchanged |
| 4 | `skills/ai-task/memory_sync.py` | 1 571 | modules beside `memory_store`, `memory_compact`, `memory_format` | `tests/fixtures/memory/goldens/` exists | packages mode `verify --fresh-clone` |
| 5 | `hooks/guard/paths.py` | 1 545 | already a package: split `paths.py` into rule groups | `test_guard_characterization` golden exists | **byte-identical guard golden**; CLAUDE.md `SH_WORD`/`SH_RE` invariant |
| 6 | `hooks/runtime-gate.py` | 1 214 | OQ1: single file (`.pylintrc`: "must run as a single file") or shim + package like `ai-guard.py` + `guard/` | new | **conditional (Q19)**: planned only after the measurement task shows Codex in use, or when a Codex-side bug forces a change; Codex re-approves a changed hook entry; the entry line must not change |

Order: 1 → 2 → 3 → 4 → 5, one task each in the shape of Q22–Q23 (`/rr-build-all`: module
steps create files, one cut-over, parallel implementers), the next starting after the
previous closed green; 6 only on its condition (Q19). Every WP is a refactoring by C3; its
weight is measured by `/rr-plan` (Policy conformance gives the expected mode). WP2–WP6 each
repeat step 0 and the `__file__` audit of R6a for their own file before the first copy.
Sizes: `wc -l` on 2026-10-31 20:30, after T-2026-10-31-1650 closed.

### Alternatives rejected

- **A class per subcommand (Q3-B).** Forty classes with one method each; the ceremony hides
  the two things that matter — which file a command touches and which journal type it
  writes. Rejected for the reason the redesign rejected seven tiers.
- **Functions only (Q3-C).** Keeps the four run-time globals, so every module would still
  reach into shared mutable state; the import-direction rule (R10) could not hold.
- **A new entry and 109 rewrites (Q2-B).** Touches every skill, the installer and the docs
  for no behaviour gain, and breaks the installed copy until `npx riskrails` runs.
- **One big-bang commit.** The golden would catch a regression but not locate it;
  incremental moves keep every diff reviewable. The copy phase of Q23 is not this: every
  module is its own step and diff, pylint and the import check each as it lands, and the
  cut-over deletes what was already copied and checked — only the per-layer golden run is
  given up (Q23), for the parallel implementers of Q22.
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
dialog.dialog_on(root, runtime="unknown") -> dict | None   runtime.own_runtime(runtime="unknown")
                                                   the keyword the suite passes instead of patching (Q24)
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

**`tests/test_dialog_contract.py` delta (Q24).** `:133` loses the inert
`mock.patch.object(state_mod, "RUNTIME", runtime)`; `:314` calls
`state_mod.dialog_on(root, runtime=runtime)` instead of patching. Two lines; nothing else in
the suites changes.

**Config keys, schema, journal vocabulary, questions format, exit codes:** unchanged.

## Policy conformance

- **C1** — the golden records what the code does today, bugs included (R5, R12); the register,
  not the refactoring, carries the fix.
- **C2** — characterization before the change; the golden is committed first and runs red on
  any difference.
- **C3** — refactoring only: Q6, R12; the plan has no row that fixes, adds or removes
  behaviour. A finding that wants one becomes its own bugfix task.
- **C4** — each WP names its files; WP1 touches `skills/ai-task/state.py`,
  `skills/ai-task/rr_state/**`, `tools/state-partition.py`, the two new test files with the
  partition and golden fixtures, the dry-run test, two lines of `tests/test_dialog_contract.py`
  (Q24), `.pylintrc`, the three doc files. An edit outside is `SCOPE_CHANGE_REQUIRED`; a
  module step owns one file (Q22).
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
- **`.ai/policies/testing.md`** — step tests: the four suites at s2 and at the cut-over, the
  layout test and pylint on the new file for a module step (Q23); `verify --scope all` once
  after the last step; e2e once; failures as one batch.
- **`~/.claude/riskrails/routing.md` and `.ai/policies/model-routing.md`** — implementers
  on BALANCED (`sonnet`, Sonnet 5.5 in the Max profile) at effort `high`, in parallel through
  `/rr-build-all` (Q22; `batch.tier` BALANCED and `batch.parallel` 5 in `weight.json`): three
  or more parallel agents run at BALANCED, never above; `high` is a raise over the tier's
  `low`–`medium`, named here as routing.md asks — the developer's instruction, and a wrong
  qualification in a copied call is a `NameError` only the cut-over would otherwise see. The
  session records every step, run and verdict (one writer of the state), runs `verify` and
  writes the conclusion; one reviewer per pass at the mode's tier. The module steps never
  share a file (Q23), so `start` has nothing to serialise but the layers. Design was written
  in the session (Fable, the model the triggering intent names) and checked independently by
  `architect` on STRONG (FC10, the reviews file).
- **`.ai/policies/security.md` and the hooks' `-I -S` boundary** — R15: the package and the
  hooks never import each other; the layout test measures it. The duplication the external
  review noticed is a boundary, not a debt.
- **ADRs** — `docs/sdlc/adr/` does not exist; no accepted decision binds this spec.
- **Redesign spec R4 "size never gates"** — R3's 600-line limit is a code-layout test, not a
  weight input; it never changes a mode or a refusal (FC2).

## Flagged concerns

Six open (Q21); the rest resolved, one line each with what closed it. A human overturns any
decision named here with `state.py answer --topic small-oop-modules Qn=<letter>` (FC7).

- **FC1 The scope guard and the SDLC flow disagree.** This spec was written while
  T-2026-10-30-2251-risk-burndown-b5 was in flight. The scope guard refused the Write tool
  for every path — `docs/sdlc/**` and the session scratchpad outside the repository alike
  (`SCOPE_CHANGE_REQUIRED`, `hooks/guard/scope.py:367`). The questions file went through
  `state.py ask --topic`, the sanctioned route; the spec and the intent, both new files,
  went through the shell, which the scope guard does not cover; the edit of the existing
  `ROADMAP.md` was refused by the runtime's own classifier and was not made (FC11). It
  happened again on 2026-10-31 at 17:15, with T-2026-10-31-1650 at its gate: Write and Edit
  were refused for this spec and for the scratchpad, Q9–Q19 went through `state.py ask`, the
  spec's edits went through the shell, and the runtime's classifier refused the sentence that
  recorded exactly this — so the record was written in the evening pass, with no task in
  flight. A guard written per task met a workflow that runs per activity, and the gap is a
  hole as much as a nuisance: an agent on a task can write any new document through `cat`.
  The human decides: an allow list for `docs/sdlc/**` and the scratchpad in the scope guard
  (allows what was denied — behaviour 2, full mode), or the rule that `/rr-spec` waits for a
  free tree; Optimisation 2 (activity scope) is the measured proposal. OQ2, Ivan's; not
  fixed here.
- **FC5 WP6 may not be splittable.** `.pylintrc` records that `runtime-gate.py` "must run as
  a single file" for two runtimes, and Codex drops trust on a changed hook entry. The
  `ai-guard.py` + `guard/` pattern shows a shim can work; whether the Codex entry survives it
  is OQ1, decided at WP6's plan with a live probe, never assumed — and WP6 is conditional
  (Q19).
- **FC7 Hybrid self-answers.** Of 24 questions, 20 were proposed and accepted by the agent
  under `agentic-sdlc-modes` Q1 = B (Q1–Q4, Q6, Q7, Q9–Q14, Q16–Q21, Q23, Q24), recorded
  `via prose` because a self-answer `via` does not exist yet (ROADMAP §1); Q5, Q8, Q15, Q22
  and OQ-M1 are the developer's. The threshold was 70 % until the evening pass and 80 % from
  it. A human overturns any with `state.py answer --topic small-oop-modules Qn=<letter>` and
  the plan re-reads the file.
- **FC8 Golden normalisation can hide a diff.** The list grew after the independent check
  (M1); it is still the place a real change can hide. `NORMALISE` is reviewed as part of the
  golden commit (R5); a reviewer's first question is "what does `NORMALISE` erase", and the
  entry path is an exact token, never a regex.
- **FC9 Behaviour 0 and a 5 000-line diff.** C6 and the weight table put this change low
  (W 4, guarded, measured again on the widened files at 20:36); its blast radius is every
  skill. The mitigation is the golden plus the suites, not a higher mode; the developer may
  still raise the mode by hand, which the journal records. Q23 concentrates the proof at two
  points, s2 and the cut-over, with static checks between — the review reads the cut-over
  diff first.
- **FC11 The ROADMAP was not updated.** The order of work (§0: risk burndown → this spec →
  the multi-agent intent; everything else blocked, narrowed by Q15 to `state.py` work) is
  drafted, but `ROADMAP.md` was last changed at `3426735` (2026-10-29): the edit was refused
  while B5 was in flight (the auto-mode classifier, after the scope guard). The record is
  this spec and the questions file until a human applies the draft.

**Resolved** (what closed each):

- FC2 R3 looked like a size gate — Q16: the 600-line measure is advisory; the layout test
  fails on cycles, upward edges, `global`, forbidden constructs and hook crossings only.
- FC3 the entry becomes a façade — accepted for WP1; the cleanup is OQ3.
- FC4 `/rr-build-all` gained nothing while every step edited `state.py` — superseded by Q22
  and Q23: module steps create files only, so the implementers run in parallel and one
  cut-over step edits the entry.
- FC6 blocking the roadmap parked fixes — Q15 (the developer): only work on `state.py`
  internals or the extracted interfaces waits; a production-breaking hotfix in a user
  project is a separate task, never mixed with a WP.
- FC10 who designed this — the session (Fable) wrote it, `architect` on STRONG checked it;
  the findings and what they changed are in `small-oop-modules.reviews.md`.
- FC12 the plan on file was stale (the first draft) — re-derived at `95b28ba` from the spec
  at `92fbacd`, amended in the evening pass for Q22–Q24; nothing in it had run.
- FC13 no second architect check of the revision — accepted: the revision removed structure
  and added two measurable rules; the first check's B1–L4 still shape the steps.
- FC14 the naming comment — out of scope; `rr_state` stays the package name.
- FC15 timing against T-2026-10-31-1650 — that task closed in `4e8dddc`; the precondition of
  `start` (no task touching `state.py` or `hooks/guard/dialog.py` in flight, Q14) is checked
  again at start.
- FC16 the questions file counted against T-1650's fact (b) — cleared by the commit
  `92fbacd`.
- FC17 the blockade narrowed, not lifted — recorded as Q15; a bugfix inside `state.py` still
  waits for the WP that owns the code.
- FC18 the second opinion was a model — `gpt-6-astra`, read-only, one run, 17:35; its
  `file:line` evidence was spot-checked where it changed Q16, Q17, Q19.
- FC19 (found in the evening pass) a string-named patch a re-export cannot serve —
  `test_dialog_contract.py:314` patches `state_mod.RUNTIME` and `dialog_on(root)` reads it
  through `own_runtime()`; Q24: two lines of that test change, listed in R6, and R6's
  generated list greps string-named patches too.

## Open questions

- **OQ1 (WP6, plan-time)** Shape of `runtime-gate.py`: single file, or shim + package. Owner:
  the planner of WP6, with a Codex `/hooks` trust probe on record.
- **OQ2 (human)** Scope guard allow list for `docs/sdlc/**` and the runtime scratchpad while a
  task is in flight, or "`/rr-spec` waits for a free tree". Owner: Ivan Kakurov. Behaviour 2
  if allowed; not this spec's work.
- **OQ3 (after WP1)** Move the suites from `import state` to `rr_state.*` and drop the
  re-exports. Owner: a later tests-only task.
- **OQ4 (closed by Q16)** The 600-line measure is advisory; the partition script and the
  layout test report sizes, and the task report notes a module over it with the reason.
  Nothing left to decide.
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
