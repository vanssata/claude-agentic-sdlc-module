# Plan: Small OOP modules — WP1, the task state machine

Intent: `docs/sdlc/intent/small-oop-modules.questions.md` (brainstorm, Hybrid) · Spec:
`docs/sdlc/specs/small-oop-modules.md` · Written 2026-10-31, re-derived 2026-10-31 17:50 from
the spec at commit 92fbacd (Q9–Q19: three classes by rule, hook isolation R15, core/shell
R16, the 600-line measure advisory, WP6 conditional, Q5 narrowed to `state.py` work),
amended 2026-10-31 20:40 for Q22–Q24: **the whole plan is one `/rr-build-all` task** —
every step implemented first, in parallel where `after` allows, by implementers on BALANCED
(`sonnet`, Sonnet 5.5) at effort `high`; a module step creates one file and never edits
`state.py`; one cut-over step; then the suite once, e2e once, one review, fixes as parallel
batches. **Not started**: `state.py start` runs only after the human commits this plan
(acceptance) and while no task editing `state.py` or `hooks/guard/dialog.py` is in flight
(Q14; T-2026-10-31-1650 closed in `4e8dddc`).

<!-- Stage 3. Concrete steps with their dependencies; /rr-build-all dispatches the ready ones in parallel, this session records them. -->

## Weight, measured (2026-10-31 20:36, `state.py weight` on the files below, not journaled)

```
scope 2 · behaviour 1 (hint: keyword 'workflow' in CONTRIBUTING.md) · reversibility 0 ·
domain 0 (declared) · novelty 0 (declared) · coverage 1  →  W 4 → guarded
```

Guarded: plan mode, one review on BALANCED, `verify + e2e`, one human stop. Unchanged by the
widened files (`tests/test_dialog_contract.py`, Q24). The hint comes from `CONTRIBUTING.md`
being in the files; declaring behaviour 0 does not lower a hint. The developer may raise to
full for a STRONG review (`start --mode full --by "<name>"`), as the burndown tasks were
raised; the spec's FC9 argues the golden, not the mode, is the mitigation. Constitution
cited: C1 (golden records today's behaviour), C2 (characterization first), C3 (refactoring,
nothing mixed), C4 (files per step), C5 (commits are the human's), C6 (weighed by effect, not
by being a process).

## How the task runs (Q22, Q23) — the decision and why

`/rr-build-all docs/sdlc/plans/small-oop-modules.md`, §2–§6 of that skill:

1. **Implement everything first.** `steps --ready` names the steps whose `after` are done;
   each goes to one implementer subagent — `general-purpose`, `model: sonnet` (BALANCED,
   Sonnet 5.5 in the Max profile), `effort: high` (the developer's instruction of 2026-10-31;
   routing.md's raise, named here) — at most `batch.parallel` (5 today) at once. A step waits
   only where it must: a module imports lower layers, so layer 0 lands before layer 1, and
   the ten layer-8 modules run five at a time. The implementer runs its step's tests itself
   and returns `## RESULT`; the session records `step-done`. Nothing else runs until
   `steps --ready` is empty.
2. **Then the test flow, once.** `verify --scope all`, then e2e; every failure classified by
   `log-reader`, the regressions fixed by parallel fixers as one batch, one run after.
3. **Then one review** at the mode's tier (BALANCED in guarded), its BLOCKER and HIGH
   findings fixed as one parallel batch, tests and review again until it passes; the pass
   past `review_rounds_max` (5) is the human's.
4. `/rr-ship`.

Why this shape is possible here, where FC4 said it was not: the old steps all edited
`state.py` (delete the moved defs, add re-exports), and `start` orders two steps that name
one file, so nothing ran in parallel. Now a module step **copies** its defs into
`rr_state/<mod>.py` and touches nothing else; `state.py` stays whole until one cut-over step
deletes everything that was copied and adds the re-exports. The golden therefore runs at s2
and at the cut-over, not after every layer (Q23). What finds a mechanical error in between is
static and cheap — pylint on the new file (`undefined-variable`, `import-error`), the layout
test's import of every present module and its partition check — and every module is its own
diff for the review. Test runs in total: the four suites twice (s2, s8), the layout test per
module step (seconds), the suite once, e2e once, plus the fix batches.

What is lost: a per-layer golden run that would locate a semantic regression to a band of
modules. What is kept: the golden's byte-identical proof, the layout test, the review of a
per-module diff. The spec's rejected "one big-bang commit" was one commit with neither.

## Flagged concerns of the spec, disposition at planning

| FC | Disposition |
|---|---|
| FC1 scope guard vs SDLC writing | not this plan's work; OQ2 stays with the developer. This plan file was written the same way (shell, new file); the evening pass ran with no task in flight |
| FC5 WP6 shape | WP6's own plan, with a Codex trust probe on record; WP6 conditional (Q19) |
| FC7 Hybrid self-answers | stand until overturned with `state.py answer --topic small-oop-modules Qn=…`; Q23 and Q24 of this pass are self-answers at 80 % |
| FC8 normalisation hides diffs | s1 commits `NORMALISE` as a named list; the review reads it first |
| FC9 behaviour 0, large diff | W 4 measured above; the mode is the developer's to raise; the review reads the cut-over diff (s8) first |
| FC11 ROADMAP not updated | the §0 draft is applied by a human, or by the agent once no task is in flight; it must now also show Q15 and Q22 |
| resolved in the spec (FC2–FC4, FC6, FC10, FC12–FC19) | as the spec's resolved list says; FC4 is superseded by Q22–Q23 (this plan's shape), FC12 by this re-derivation, FC15 by `4e8dddc`, FC19 by Q24 (two lines of `tests/test_dialog_contract.py`, in s8) |

Committing this plan is the human's acceptance of the dispositions above and of Q22–Q24;
FC1/OQ2 still deserves an explicit word (FC6 got one with Q15).

## Files that change

One task (WP1), 29 steps; `rr_state/` is `skills/ai-task/rr_state/`. A module step owns
exactly one new file — nothing two implementers could both hold.

| Step | Files |
|---|---|
| s0 | new `tools/state-partition.py` (reads `state.py` with `ast`: every top-level `def`, who calls whom; reads the partition; prints the module import graph, every cycle and every upward edge; exit 1 on a cycle, an unassigned or a doubly-assigned def), new `tests/fixtures/state/partition.json` (def → module, layer per module, core or shell per def — R16), new `tests/test_state_layout.py` (first form, **phase-aware**: while `state.py` still defines `main`, it checks every module present under `rr_state/` — its defs are the partition's, each exists in the golden tree's file with the same signature, the module imports, holds no `global` and no `__file__`; once the entry is the shim, the full form of s8) |
| s1 | new `tests/test_state_characterization.py` (`NORMALISE`, the four scripted runs, the `--help` enumeration), new `tests/fixtures/state/goldens/{help,light,guarded,full,dialog}.txt` |
| s2 | edit `skills/ai-task/state.py` only: `ENTRY = os.path.abspath(__file__)` once, the 17 `__file__` uses replaced (`:82` keeps its own for `sys.path`) |
| s3-fs … s7-close (24 module steps) | one new file each, `rr_state/<mod>.py`; `s3-fs` also creates `rr_state/__init__.py` (a docstring, nothing else). The modules and layers are the spec's table; `partition.json` (s0) is the authority on which defs |
| s8 | new `rr_state/cli.py`; edit `skills/ai-task/state.py` (every copied def deleted, the shim of spec §Interfaces, under 200 lines), `tests/test_state_layout.py` (the full form: module sizes printed, 600 advisory — Q16; no `global`; no `__file__` under `rr_state/`; re-export list vs the two greps of R6; import graph from the real `import` lines; the forbidden constructs of R4 — a class base other than a dataclass or `Exception`, `ABC`, `abstractmethod`, `Protocol`, `staticmethod`; no import crossing between `hooks/` and `rr_state/` — R15; no `os`, `subprocess`, `time`, `fcntl` import in a module whose defs are all core — R16; exactly one home per def), `.pylintrc` (`never-returning-functions` + `rr_state.fs.die`), `tests/test_install_dry_run.py` (`rr_state/__init__.py`, `rr_state/cli.py` in the installed list), `tests/test_dialog_contract.py` (two lines, Q24: `:133` loses the inert `RUNTIME` patch, `:314` calls `dialog_on(root, runtime=runtime)`) |
| s9 | `docs/architecture.md` (`:16`, `:82-95`), `CONTRIBUTING.md` (where the code lives, running one module's suite), `.ai/project/known-risks.md` (two mentions, relabel if they name internals) |

Not touched, by C3 and C4: `sensors.py`, `weight.py`, `memory_*.py`, every hook, every
skill text, `bin/riskrails.js`, `.ai/VERSION`, any policy or template. A need to touch one
is `SCOPE_CHANGE_REQUIRED`, never a silent widening. A module step that finds the partition
wrong (a def in the wrong module, a missing import edge) reports `SCOPE_CHANGE_REQUIRED` too:
`partition.json` is s0's file, the session changes it and re-dispatches the step.

Task files for `start --files` (every step's files, one list):
`skills/ai-task/state.py, skills/ai-task/rr_state/**, tools/state-partition.py,
tests/test_state_layout.py, tests/test_state_characterization.py,
tests/fixtures/state/**, tests/test_install_dry_run.py, tests/test_dialog_contract.py,
.pylintrc, docs/architecture.md, CONTRIBUTING.md, .ai/project/known-risks.md`.

## Order of work

**All steps are implemented before anything else runs** (Q22): `/rr-build-all` §3 dispatches
every ready step to an implementer, in parallel up to `batch.parallel`, waits where `after`
says so, records `step-done`, and only when no step is left runs §4 (the suite once, fixes as
a batch) and §5 (one review, fixes as a batch). *After* is the dependency `steps.json`
carries: a module step waits for s0 (the partition), s2 (the source already says `ENTRY`) and
every step of the layers it imports — the ladder is the conservative graph, `partition.json`
may loosen it at start (a module that imports nothing from a layer need not wait for it).
Step tests run by the implementer through `step_test_command` (`python3 -I tests/run_suite.py
{files}`), plus `pylint skills/ai-task/rr_state/<mod>.py` for a module step.

| Step | What | Tests (step scope) | After |
|---|---|---|---|
| s0 | Partition on paper: `tools/state-partition.py` + `partition.json`; iterate the map until the import graph is acyclic and complete; the spec's layer table is the starting point, the graph is the authority (OQ5 decided here); every def labelled core or shell (R16), and a module of one responsibility group merges with its neighbour when the graph allows (Q13); the phase-aware layout test | `tests/test_state_layout.py` | — |
| s1 | The golden: harness from `tests/test_ai_task_state.py` (`Project`), environment pinned (`AI_RUNTIME`, agent markers, `USER`, `git -c user.name/email`, fixed commit date), four runs incl. the dialog-on run, `--help` enumerated from the parser via `import state`; `NORMALISE` listed in the docstring; `<STATE_PY>` as an exact token. Its own commit | `tests/test_state_characterization.py` | — (parallel with s0) |
| **s2** | `ENTRY` replaces the 17 `__file__` uses in the single file (R6a) — **riskiest step**: the label comparisons (`validate_label`, `dialog_pick`), the refusal texts, `load_resolver`'s three `dirname`s, the migrations lookup, the Codex check, `own_runtime`'s path check. Early by design so the golden sees it as a no-op before anything is copied; serial — the only step before s8 that edits `state.py` | characterization, `test_ai_task_state`, `test_dialog_contract`, `test_dialog_gate` | s1 |
| s3-fs, s3-locks | layer 0: `fs` (with `ENTRY`, `current_tree`, `run_text`, `now`, `now_ms` — the seams, module-level) and `rr_state/__init__.py`; `locks` (one re-entrancy counter, `LOCK_STALE`) | layout test, pylint on the file | s0, s2 |
| s3-runtime, s3-policy | layer 1: `runtime` (detection only; `Runtime` a frozen dataclass whose docstring names its invariant — R4; `own_runtime(runtime="unknown")`, Q24); `policy` (core, no I/O) | the same | layer 0 |
| s4-journal | layer 2: functions over `root`, `task_id`; `emit` exactly as today; `journal_line(..., runtime="unknown")` | the same | layer 1 |
| s4-task | layer 3: `load` returns the dict, `save` writes it — no record class; `claim_runtime` inside `load`, keyword `mutating=False` | the same | s4-journal |
| s5-questions, s5-ledger, s5-gate | layer 4: `questions` (parse and render core, `write_questions` shell; functions, no file class), `ledger` (`Ledger(root)`, the one resource holder — `consent.lock` by `O_EXCL`; `LOCK_STALE` via `locks`), `gate` (gate state only) | the same | s4-task |
| s6-dialog | layer 5: the dialog functions and the pick memo; `dialog_on(root, runtime="unknown")` (Q24) | the same | layer 4 |
| s6-authority | layer 6: who may act | the same | s6-dialog |
| s6-report, s6-handoff, s6-profile | layer 7: `report` (`write_task_md` stays called by the commands), `handoff`, `profile` (`Profile` a frozen dataclass; `load_resolver` via `ENTRY`) | the same | s6-authority |
| s7-questions_cmd, s7-gate_cmd, s7-dialog_cmd, s7-report_cmd, s7-memory_cmd, s7-steps, s7-start, s7-verify, s7-review, s7-close | layer 8, one step per command module, ten in parallel (five at a time at `batch.parallel` 5) | the same | layer 7 |
| **s8** | **Cut-over**: `cli.py` (the three runtime resolutions as today, `Runtime` built there); the shim — every copied def deleted from `state.py`, the re-exports of R6 (both greps) added; the full layout test; `.pylintrc`; the dry-run list; the two lines of Q24; R8 timing (20 runs each of `--help` and `status`, medians in `task.md`); `pylint $(git ls-files '*.py')` | characterization, `test_ai_task_state`, `test_dialog_contract`, `test_dialog_gate`, `tests/test_project_update.py`, `tests/test_skills_surface.py`, `tests/test_state_layout.py`, `tests/test_install_dry_run.py` | every s3–s7 step |
| s9 | Docs (R11): the tree and "the state machine every skill drives" in `docs/architecture.md`, `CONTRIBUTING.md`, `.ai/project/known-risks.md` — written from `partition.json`, read by the review against the tree after s8 | `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` | s0 (parallel with s3–s8) |

After the last `step-done`: `verify --scope all`, e2e, one review (BALANCED in guarded),
fixes as parallel batches, `/rr-ship`; `/clear`. Then WP2's own plan.

A module step's brief (the implementer contract, `agents/implementer.md`, filled in): the row
above; allowed file — its module; forbidden — every other file, "another implementer holds
it"; the defs from `partition.json`; the rules R4 (a class only `Runtime`, `Profile`,
`Ledger`, each with its sentence), R6 (`json.dump`, `os.replace` as module attributes), R10
(imports only from lower layers, `from rr_state import fs` and `fs.now()` so the seams stay
patchable — never `from rr_state.fs import now`), R16 (the core/shell label in the docstring;
a core def imports no `os`, `subprocess`, `time`, `fcntl`); the body is today's, calls
qualified by module, nothing reworded. It never calls `state.py`.

### The programme after WP1 (later rows, each its own plan file)

| WP | File | Plan file | Consumes |
|---|---|---|---|
| WP1b | `skills/ai-task/state.py` (92): the re-exports deleted, the suites import `rr_state.*` (Q25, closes OQ3) | `docs/sdlc/plans/small-oop-modules-wp1b.md` | WP1 closed |
| ~~WP2~~ | dropped by Q26: `adopt.py` is deleted by the regenerate-not-migrate task (`docs/sdlc/intent/riskrails-regenerate-not-migrate.md`, its own spec and task, C3) | — | — |
| WP3 | `skills/project-update/update.py` (what is left after the regenerate-not-migrate task) | `…-wp3.md` | WP1b and that task closed |
| WP-L | folded into the regenerate-not-migrate task (Q26) | — | — |
| WP4 | `skills/ai-task/memory_sync.py` (1 571) | `…-wp4.md` | WP3 |
| WP5 | `hooks/guard/paths.py` (1 545) — guard golden byte-identical, `SH_WORD`/`SH_RE` invariant | `…-wp5.md` | WP4 |
| WP6 | `hooks/runtime-gate.py` (1 214) — **conditional (Q19)**: planned only once the measurement task of the spec's Optimisation section shows Codex in use, or a Codex-side bug forces a change; OQ1 with a Codex trust probe | `…-wp6.md` | WP5 + the condition |

Each repeats s0–s2 for its own file (partition, golden, `__file__` audit) before the first
copy, and runs in the same shape (Q22–Q23). What waits (Q5 as narrowed by Q15): only work
that edits `state.py` internals or the extracted interfaces, until the WP that owns that code
closes; the spec's Optimisation tasks (classification, activity scope, review strength, spec
budget, measurement, state ownership audit) and urgent fixes are separate tasks and may run
between the WPs. Sizes: `wc -l`, 2026-10-31 20:30.

## Risks

What could break, how it would show, which step carries it.

- **A label or a refusal prints the module path** (s2, s8). Every `state_label`,
  `approve_command` and refusal text would name `rr_state/x.py`; the hooks' label rule
  (`hooks/guard/dialog.py:163,488`) needs the basename `state.py`, so every dialog pick
  would be refused. Shows in the dialog-on golden and `test_dialog_contract`. That is why
  s2 is first and alone.
- **A cycle appears only at import time** (s3–s7, s8). `cyclic-import` lowers the pylint
  score under 9.9 (R7) and a lazy import would hide it. s0's graph is checked before any
  copy; the layout test re-derives it from the real `import` lines in s8.
- **Nested locks deadlock** (s3-locks, s6-report). `question_lock` is taken by the gate and
  again by `write_task_md` inside it; a per-object counter waits on the second descriptor
  forever. Shows as a hung test; `locks.py` keeps one counter per process.
- **A patched module attribute stops being patched** (s3–s7, s8). The suites patch
  `state_mod.json.dump` and `state_mod.os`; copied code that does `from json import dump`
  bypasses the patch and the disk-full tests go green for the wrong reason; a module that
  writes `from rr_state.fs import now` binds the seam at import time and a patch of `fs.now`
  never reaches it. The review checks for `from json import` / `from os import` /
  `from rr_state.<mod> import <function>` in `rr_state/`.
- **The claim moves** (s4-task, s8). `claim_runtime` ahead of `route_surface`/`guard_pending`
  changes which refusal wins; it stays inside `load`, and `cli.py` keeps the three
  resolutions.
- **The golden erases too much** (s1). A generic path regex would have hidden the `__file__`
  bug. `NORMALISE` is a named list; the entry path is an exact token; the review reads the
  list before the diff.
- **A copy that is wrong stays silent until s8** (s3–s7). Nothing runs a copied module but
  its import; a call left unqualified is a `NameError` at call time. pylint on the file
  (`undefined-variable`, `import-error`) and the layout test's import run in every module
  step; the golden and the four suites at s8 find what they miss, and the review reads the
  s8 diff first. This is the price of Q23, paid knowingly.
- **Two implementers, one partition** (s3–s7). A step that needs a def moved or an import
  edge added cannot edit `partition.json`; it reports `SCOPE_CHANGE_REQUIRED`, the session
  edits s0's file and re-dispatches. A module step is never widened to the partition.
- **The `RUNTIME` patch** (s8). `test_dialog_contract.py:314` would set an attribute the
  package never reads; Q24's two lines go in with the shim, in the step the globals
  disappear — earlier they would fail against the untouched entry.
- **Many implementers, one state file** (all). Only this session calls `state.py`; a subagent
  that did would race the journal. The brief forbids it (`/rr-build-all`, Rules); the cost of
  24 briefs at effort `high` is bounded by their scope — one module, `grep -n` and bounded
  reads of its defs, never the whole file — and `/rr-status --cost` after the task shows what
  it took, the measurement the spec's Optimisation 5 asks for.
- **An installed home gets the new entry without the package** (s8). A traceback where a
  skill expects a refusal text. The entry exits with one line naming `npx riskrails`; the
  installer copies the whole skill directory (`bin/riskrails.js:759-760`), so only a hand
  copy reaches that state.
- **`-I` and `sys.path`** (s8). `tests/test_project_update.py:882-888` deletes
  `sys.path[:2]` after `import state`; the entry's own insert must stay first.
- **Startup time** (s8). Twenty-odd imports per call; R8's 10 % is measured, not guessed.
  If it fails, `cli.py` imports layer-8 modules lazily per subcommand — a layout change,
  not a behaviour one.
- **Scope creep under the guard** (all). A doc or template outside the files list is
  `SCOPE_CHANGE_REQUIRED`; the burndown tasks showed how often "one more file" appears.
- **A class slips in as a namespace** (s3–s7). The rule of R4 is a sentence in the
  docstring naming the resource or the invariant; the layout test counts classes under
  `rr_state/` and the review reads each docstring. Three today; a fourth needs its sentence.
- **A core function reaches I/O** (s0, s5–s7). A `render_*` that reads the clock or a
  `parse_*` that opens a file makes the golden depend on the environment; s0's label and
  the import check of the layout test catch it, the review reads any def whose label moved.
- **A hook imports the package** (s3–s8). `hooks/guard/*` runs under `-I -S` with its own
  `sys.path`; an import of `rr_state` there would work in the suite and fail in a user
  project. The layout test reads both trees' `import` lines (R15).
- **The tree moves under the golden** (s1→s2). A task that edits `state.py` between the
  recording and s2 pins the wrong tree. Precondition of `start`; s1 is re-run if
  `git log -1 -- skills/ai-task/state.py` changed since the recording (Q14).
- **Found bugs** (all). R12: into the register, never fixed in a step; the review checks
  that no golden line changed "because it was wrong".

## Proof (tests)

| R | Proof | Step |
|---|---|---|
| R1 | `tests/test_state_characterization.py` (help + four runs byte-identical); `tests/test_skills_surface.py` (`--help` of five subcommands); `tests/test_install_routes.py:355` and `tests/test_project_update.py:871` (`-I`, the entry's own `sys.path` insert) | s1, s8 |
| R2 | `tests/test_state_layout.py`: entry under 200 lines; a run with `rr_state/` renamed away exits with the one-line message | s8 |
| R3 | `test_state_layout.py`: partition complete (every def of the golden tree's file once, after the cut; the present modules' defs before it); module sizes printed, over 600 noted in `task.md` with the reason (advisory, Q16) | s0, s3–s7, s8 |
| R4 | `test_state_layout.py`: zero `global` statements under `rr_state/`; the classes are `Runtime`, `Profile`, `Ledger`, each docstring naming its resource or invariant; no class base other than a dataclass or `Exception`, no `ABC`, `abstractmethod`, `Protocol`, `staticmethod`; `test_ai_task_state.py:1324` (`journal_line` with six args) and `test_project_update.py:890` (`load(root, claim=False)`) pass unchanged; `test_dialog_contract.py:314` passes `runtime=` (Q24) | s3–s8 |
| R5 | the golden commit (s1) is green on the untouched tree and red when any recorded field changes (one deliberate edit, reverted, shown in the task report) | s1 |
| R6 | `test_state_layout.py`: the re-export list equals the union of `grep -oh 'state_mod\.[A-Za-z_]*' tests/*.py` and `grep -oh 'patch\.object(state_mod, "[A-Za-z_]*"' tests/*.py`; no `from json import` / `from os import` / `from rr_state.<mod> import <function>` in `rr_state/`; `git diff --stat` of the task shows no test file changed except the dry-run list and the two lines of `test_dialog_contract.py` (Q24) | s8 |
| R6a | `test_state_layout.py`: no `__file__` under `rr_state/`; the dialog-on golden (label accepted, pick matched) | s2, s8 |
| R7 | `pylint $(git ls-files '*.py')` ends "rated at 10.00/10" (`lint_command`); per module step, `pylint` on the new file alone | s3–s7, s8 |
| R8 | medians of 20 runs of `--help` and `status`, before (golden tree) and after, in `task.md`; within 10 % | s8 |
| R9 | `tests/test_install_dry_run.py` (the two new listed files exist), `tests/test_install_routes.py`, the install suites | s8 |
| R10 | `tools/state-partition.py` exit 0 on `partition.json` (s0); `test_state_layout.py` import graph acyclic and downward from real imports (s8) | s0, s8 |
| R11 | `grep -n 'ai-task/state.py' docs/architecture.md CONTRIBUTING.md` shows the package; `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` green | s9 |
| R12 | `state.py memory risks` lists what s2–s8 found; no golden line edited except by `NORMALISE` | all |
| R13 | out of WP1's scope; each later WP's plan carries its own row | — |
| R15 | `test_state_layout.py`: no `import` line under `hooks/` names `rr_state` or `state`, none under `rr_state/` names `hooks`; `tests/test_guard_characterization.py` green | s3–s8 |
| R16 | `partition.json` labels every def; `test_state_layout.py`: a module whose defs are all core imports none of `os`, `subprocess`, `time`, `fcntl`; the golden's timestamps come only through `fs.now` / `fs.now_ms` | s0, s8 |
| R14 | `git revert` of the task's commits restores the single file; `verify --scope all` green on the reverted tree (checked once at `/rr-ship`, noted in `task.md`) | s8 |

Verification, per `.ai/policies/testing.md`: step tests as named; after the last step
`python3 -I tests/run_suite.py --serial …` through `state.py verify --scope all`, then
`AI_E2E=1 … test_end_to_end.py` through `verify --scope e2e`; every failure fixed as one
batch (`/rr-build-all` §4).

## Rollback

`git revert` of the task's commit series, newest first; the single `state.py` returns, the
`rr_state/` directory disappears, no state, schema, policy or template changed, so nothing
is migrated back. The installed copy follows with `npx riskrails`. The golden (s1) and the
partition tool (s0) can stay after a revert — they describe the behaviour, not the layout.

## Start — the command to run later, not now

```bash
STATE="python3 $HOME/.claude/skills/ai-task/state.py"
$STATE start --goal "WP1: split skills/ai-task/state.py into rr_state/ behind an unchanged entry; behaviour pinned by the characterization golden" \
  --workflow refactoring \
  --files "skills/ai-task/state.py,skills/ai-task/rr_state/**,tools/state-partition.py,tests/test_state_layout.py,tests/test_state_characterization.py,tests/fixtures/state/**,tests/test_install_dry_run.py,tests/test_dialog_contract.py,.pylintrc,docs/architecture.md,CONTRIBUTING.md,.ai/project/known-risks.md" \
  --tests "tests/test_state_characterization.py,tests/test_ai_task_state.py,tests/test_dialog_contract.py,tests/test_dialog_gate.py,tests/test_state_layout.py" \
  --declare behaviour=0:"no guard decision, refusal, approval or install path changes; golden byte-identical" \
  --declare novelty=0:"stdlib only, the sibling-module pattern of sensors.py and memory_*.py" \
  --declare domain=0:"plugin internals" \
  --plan-file docs/sdlc/plans/small-oop-modules.steps.json \
  --batch --by "Ivan Kakurov" --why "/rr-build-all docs/sdlc/plans/small-oop-modules.md (Q22)"
```

`small-oop-modules.steps.json` is written at start from the Order of work: 29 entries
`{"id", "files", "tests", "after"}`, the module steps' `after` tightened from the ladder to
`partition.json`'s real imports. `--batch` turns on the loop of `/rr-build-all`
(`batch.default` is false); `batch.parallel` 5 and `batch.tier` BALANCED are `weight.json`'s
and the human's to change before start (a policy is frozen during a task). The implementers'
effort `high` is set on each spawn (Q22). Preconditions: no task in flight (`state.py
status`), no task touching `state.py` or `hooks/guard/dialog.py` in flight (Q14), the human
has committed this plan, FC1/OQ2 has an explicit word (FC6 has Q15).
