# Plan: Small OOP modules — WP1, the task state machine

Intent: `docs/sdlc/intent/small-oop-modules.questions.md` (brainstorm, Hybrid) · Spec:
`docs/sdlc/specs/small-oop-modules.md` · Written 2026-10-31, **not started**: the developer
asked for the plan on file and no implementation yet; `state.py start` runs only after the
risk burndown in flight closes and the human accepts this plan (guarded mode: plan mode).

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

## Weight, measured (2026-10-31, `state.py weight`, not journaled)

```
scope 2 · behaviour 1 (hint: keyword 'workflow' in CONTRIBUTING.md) · reversibility 0 ·
domain 0 (declared) · novelty 0 (declared) · coverage 1  →  W 4 → guarded
```

Guarded: plan mode, one review on BALANCED, `verify + e2e`, one human stop. The hint comes
from `CONTRIBUTING.md` being in the files; declaring behaviour 0 does not lower a hint. The
developer may raise to full for a STRONG review (`start --mode full --by "<name>"`), as
the burndown tasks were raised; the spec's FC9 argues the golden, not the mode, is the
mitigation. Constitution cited: C1 (golden records today's behaviour), C2 (characterization
first), C3 (refactoring, nothing mixed), C4 (files per step), C5 (commits are the human's),
C6 (weighed by effect, not by being a process).

## Flagged concerns of the spec, disposition at planning

| FC | Disposition |
|---|---|
| FC1 scope guard vs SDLC writing | not this plan's work; OQ2 stays with the developer. This plan file was written the same way (shell, new file) |
| FC2 R3 is a layout test, not a gate | kept as written; the layout test never reads the weight |
| FC3 the entry as a façade | accepted for WP1; OQ3 is a later tests-only task |
| FC4 `/rr-build-all` gains nothing | **decided: `/rr-build`, row by row, one session.** Every step edits `state.py`; a batch would serialise anyway and move the diff out of the session |
| FC5 WP6 shape | WP6's own plan, with a Codex trust probe on record |
| FC6 the roadmap is blocked | accepted by the developer on 2026-10-31; a production hotfix needs an explicit word |
| FC7 Hybrid self-answers | stand until overturned with `state.py answer --topic small-oop-modules Qn=…` |
| FC8 normalisation hides diffs | s1 commits `NORMALISE` as a named list; the review reads it first |
| FC9 behaviour 0, large diff | W 4 measured above; the mode is the developer's to raise |
| FC10 who designed it | folded in; this plan follows the corrected spec |
| FC11 ROADMAP not updated | the §0 draft is applied by a human, or by the agent once no task is in flight |

Committing this plan is the human's acceptance of the dispositions above; FC1/OQ2 and FC6
deserve an explicit word.

## Files that change

One task (WP1), nine steps; the rows are the steps. `rr_state/` is `skills/ai-task/rr_state/`.

| Step | Files |
|---|---|
| s0 | new `tools/state-partition.py` (reads `state.py` with `ast`: every top-level `def`, who calls whom; reads the partition; prints the module import graph, every cycle and every upward edge; exit 1 on a cycle, an unassigned or a doubly-assigned def), new `tests/fixtures/state/partition.json` (def → module, layer per module), new `tests/test_state_layout.py` (first version: partition complete and acyclic against the golden tree's defs) |
| s1 | new `tests/test_state_characterization.py` (`NORMALISE`, the four scripted runs, the `--help` enumeration), new `tests/fixtures/state/goldens/{help,light,guarded,full,dialog}.txt` |
| s2 | edit `skills/ai-task/state.py` only: `ENTRY = os.path.abspath(__file__)` once, the 17 `__file__` uses replaced (`:82` keeps its own for `sys.path`) |
| s3 | new `rr_state/__init__.py`, `rr_state/fs.py`, `rr_state/locks.py`, `rr_state/runtime.py`, `rr_state/policy.py`; edit `skills/ai-task/state.py` (the moved defs deleted, re-exports added) |
| s4 | new `rr_state/journal.py`, `rr_state/task.py`; edit `state.py` |
| s5 | new `rr_state/questions.py`, `rr_state/ledger.py`, `rr_state/gate.py`; edit `state.py` |
| s6 | new `rr_state/dialog.py`, `rr_state/authority.py`, `rr_state/report.py`, `rr_state/handoff.py`, `rr_state/profile.py`; edit `state.py` |
| s7 | new `rr_state/questions_cmd.py`, `rr_state/gate_cmd.py`, `rr_state/dialog_cmd.py`, `rr_state/report_cmd.py`, `rr_state/memory_cmd.py`, `rr_state/steps.py`, `rr_state/start.py`, `rr_state/verify.py`, `rr_state/review.py`, `rr_state/close.py`; edit `state.py` |
| s8 | new `rr_state/cli.py`; edit `skills/ai-task/state.py` (the shim of spec §Interfaces, under 200 lines), `tests/test_state_layout.py` (module sizes ≤ 600, no `global`, no `__file__` under `rr_state/`, re-export list vs `grep` of the suites, import graph from the real `import` lines), `.pylintrc` (`never-returning-functions` + `rr_state.fs.die`), `tests/test_install_dry_run.py` (`rr_state/__init__.py`, `rr_state/cli.py` in the installed list), `docs/architecture.md` (`:16`, `:82-95`), `CONTRIBUTING.md` (where the code lives, running one module's suite), `.ai/project/known-risks.md` (two mentions, relabel if they name internals) |

Not touched, by C3 and C4: `sensors.py`, `weight.py`, `memory_*.py`, every hook, every
skill text, `bin/riskrails.js`, `.ai/VERSION`, any policy or template. A need to touch one
is `SCOPE_CHANGE_REQUIRED`, never a silent widening.

Task files for `start --files` (every step's files, one list):
`skills/ai-task/state.py, skills/ai-task/rr_state/**, tools/state-partition.py,
tests/test_state_layout.py, tests/test_state_characterization.py,
tests/fixtures/state/**, tests/test_install_dry_run.py, .pylintrc, docs/architecture.md,
CONTRIBUTING.md, .ai/project/known-risks.md`.

## Order of work

Each step leaves the repository working and is about one commit. Step tests run through
`state.py verify --scope step --files "<comma list>"`; the suite once after s8
(`verify --scope all`), then e2e, failures fixed as one batch. *Consumes* names the steps a
row depends on (what `/rr-build-all` would read; here it is the order of `/rr-build`).

| Step | What | Tests (step scope) | Consumes |
|---|---|---|---|
| s0 | Partition on paper: `tools/state-partition.py` + `partition.json`; iterate the map until the import graph is acyclic and complete; the spec's layer table is the starting point, the graph is the authority (OQ5 decided here) | `tests/test_state_layout.py` | — |
| s1 | The golden: harness from `tests/test_ai_task_state.py` (`Project`), environment pinned (`AI_RUNTIME`, agent markers, `USER`, `git -c user.name/email`, fixed commit date), four runs incl. the dialog-on run, `--help` enumerated from `cli`'s parser via `import state`; `NORMALISE` listed in the docstring; `<STATE_PY>` as an exact token. Commit of its own | `tests/test_state_characterization.py` | — |
| **s2** | `ENTRY` replaces the 17 `__file__` uses in the single file (R6a) — **riskiest step**: the label comparisons (`validate_label`, `dialog_pick`), the refusal texts, `load_resolver`'s three `dirname`s, the migrations lookup, the Codex check. Early by design so the golden sees it as a no-op before anything moves | characterization, `test_ai_task_state`, `test_dialog_contract`, `test_dialog_gate` | s1 |
| s3 | Layers 0–1: `fs` (with `ENTRY`, `current_tree`, `run_text`), `locks` (one counter), `runtime` (detection only, `Runtime`), `policy`; entry re-exports; no `global` left in moved code | the same four | s0, s2 |
| s4 | Layers 2–3: `journal` (`emit` exactly as today; `journal_line(..., runtime="unknown")`), `task` (`claim_runtime` inside `load`, keyword `mutating=False`) | the same four + `tests/test_project_update.py` (`:871-890` imports `state`, deletes `sys.path[:2]`) | s3 |
| s5 | Layer 4: `questions` (parse/render/write), `ledger` (+`LOCK_STALE` via `locks`), `gate` (gate state only) | the same four | s4 |
| s6 | Layers 5–7: `dialog` (+ the pick memo), `authority`, `report` (`write_task_md` stays called by the commands), `handoff`, `profile` (`load_resolver` via `ENTRY`) | the same four + `tests/test_skills_surface.py` (runs `--help` on `decision`, `consent`, `steps`, `batch`, `start`) | s5 |
| s7 | Layer 8, one module per sub-step in the order `questions_cmd`, `gate_cmd`, `dialog_cmd`, `report_cmd`, `memory_cmd`, `steps`, `start`, `verify`, `review`, `close`; the entry shrinks as each leaves | the same five + `tests/test_memory_*.py`, `tests/test_weight.py` | s6 |
| s8 | `cli.py` (the three runtime resolutions as today), the shim, the full layout test, `.pylintrc`, the dry-run list, docs; R8 timing (20 runs each of `--help` and `status`, medians in `task.md`); then `verify --scope all`, e2e, `pylint $(git ls-files '*.py')` | `tests/test_state_layout.py`, then the suite | s7 |

After s8: `/rr-review` (BALANCED in guarded), `/rr-ship`; `/clear`. Then WP2's own plan.

### The programme after WP1 (later rows, each its own plan file)

| WP | File | Plan file | Consumes |
|---|---|---|---|
| WP2 | `skills/project-update/adopt.py` (2 219) | `docs/sdlc/plans/small-oop-modules-wp2.md` | WP1 closed |
| WP3 | `skills/project-update/update.py` (2 114) | `…-wp3.md` | WP2 |
| WP4 | `skills/ai-task/memory_sync.py` (1 571) | `…-wp4.md` | WP3 |
| WP5 | `hooks/guard/paths.py` (1 452) — guard golden byte-identical, `SH_WORD`/`SH_RE` invariant | `…-wp5.md` | WP4 |
| WP6 | `hooks/runtime-gate.py` (1 214) — OQ1 with a Codex trust probe | `…-wp6.md` | WP5 |

Each repeats s0–s2 for its own file (partition, golden, `__file__` audit) before the first
move. The roadmap block (spec Q5) lifts when WP6 closes.

## Risks

What could break, how it would show, which step carries it.

- **A label or a refusal prints the module path** (s2, s6). Every `state_label`,
  `approve_command` and refusal text would name `rr_state/x.py`; the hooks' label rule
  (`hooks/guard/dialog.py:163,488`) needs the basename `state.py`, so every dialog pick
  would be refused. Shows in the dialog-on golden and `test_dialog_contract`. That is why
  s2 is first and alone.
- **A cycle appears only at import time** (s3–s7). `cyclic-import` lowers the pylint score
  under 9.9 (R7) and a lazy import would hide it. s0's graph is checked before any move;
  the layout test re-derives it from the real `import` lines in s8.
- **Nested locks deadlock** (s3, s6). `question_lock` is taken by the gate and again by
  `write_task_md` inside it; a per-object counter waits on the second descriptor forever.
  Shows as a hung test; `locks.py` keeps one counter per process.
- **A patched module attribute stops being patched** (s4, s6). The suites patch
  `state_mod.json.dump` and `state_mod.os`; moved code that does `from json import dump`
  bypasses the patch and the disk-full tests go green for the wrong reason. The review
  checks for `from json import` / `from os import` in `rr_state/`.
- **The claim moves** (s4). `claim_runtime` ahead of `route_surface`/`guard_pending` changes
  which refusal wins; it stays inside `load`, and `cli.py` keeps the three resolutions.
- **The golden erases too much** (s1). A generic path regex would have hidden the `__file__`
  bug. `NORMALISE` is a named list; the entry path is an exact token; the review reads the
  list before the diff.
- **An installed home gets the new entry without the package** (s8). A traceback where a
  skill expects a refusal text. The entry exits with one line naming `npx riskrails`; the
  installer copies the whole skill directory (`bin/riskrails.js:759-760`), so only a hand
  copy reaches that state.
- **`-I` and `sys.path`** (s3, s8). `tests/test_project_update.py:882-888` deletes
  `sys.path[:2]` after `import state`; the entry's own insert must stay first.
- **Startup time** (s8). Twenty-odd imports per call; R8's 10 % is measured, not guessed.
  If it fails, `cli.py` imports layer-8 modules lazily per subcommand — a layout change,
  not a behaviour one.
- **Scope creep under the guard** (all). A doc or template outside the files list is
  `SCOPE_CHANGE_REQUIRED`; the burndown tasks showed how often "one more file" appears.
- **Found bugs** (all). R12: into the register, never fixed in a step; the review checks
  that no golden line changed "because it was wrong".

## Proof (tests)

| R | Proof | Step |
|---|---|---|
| R1 | `tests/test_state_characterization.py` (help + four runs byte-identical); `tests/test_skills_surface.py` (`--help` of five subcommands); `tests/test_install_routes.py:355` and `tests/test_project_update.py:871` (`-I`, the entry's own `sys.path` insert) | s1, s8 |
| R2 | `tests/test_state_layout.py`: entry under 200 lines; a run with `rr_state/` renamed away exits with the one-line message | s8 |
| R3 | `test_state_layout.py`: partition complete (every def of the golden tree's file once), every module ≤ 600 lines | s0, s8 |
| R4 | `test_state_layout.py`: zero `global` statements under `rr_state/`; the six class names exist; `test_ai_task_state.py:1324` (`journal_line` with six args) and `test_project_update.py:890` (`load(root, claim=False)`) pass unchanged | s3–s8 |
| R5 | the golden commit (s1) is green on the untouched tree and red when any recorded field changes (one deliberate edit, reverted, shown in the task report) | s1 |
| R6 | `test_state_layout.py`: the re-export list equals `grep -oh 'state_mod\.[A-Za-z_]*' tests/*.py`; no `from json import` / `from os import` in `rr_state/`; `git diff --stat` of the task shows no other test file changed | s8 |
| R6a | `test_state_layout.py`: no `__file__` under `rr_state/`; the dialog-on golden (label accepted, pick matched) | s2, s8 |
| R7 | `pylint $(git ls-files '*.py')` ends "rated at 10.00/10" (`lint_command`) | s8 |
| R8 | medians of 20 runs of `--help` and `status`, before (golden tree) and after, in `task.md`; within 10 % | s8 |
| R9 | `tests/test_install_dry_run.py` (the two new listed files exist), `tests/test_install_routes.py`, the install suites | s8 |
| R10 | `tools/state-partition.py` exit 0 on `partition.json` (s0); `test_state_layout.py` import graph acyclic and downward from real imports (s8) | s0, s8 |
| R11 | `grep -n 'ai-task/state.py' docs/architecture.md CONTRIBUTING.md` shows the package; `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` green | s8 |
| R12 | `state.py memory risks` lists what s2–s8 found; no golden line edited except by `NORMALISE` | all |
| R13 | out of WP1's scope; each later WP's plan carries its own row | — |
| R14 | `git revert` of the task's commits restores the single file; `verify --scope all` green on the reverted tree (checked once at `/rr-ship`, noted in `task.md`) | s8 |

Verification, per `.ai/policies/testing.md`: step tests as named; after s8
`python3 -I tests/run_suite.py --serial …` through `state.py verify --scope all`, then
`AI_E2E=1 … test_end_to_end.py` through `verify --scope e2e`; every failure fixed as one
batch.

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
  --files "skills/ai-task/state.py,skills/ai-task/rr_state/**,tools/state-partition.py,tests/test_state_layout.py,tests/test_state_characterization.py,tests/fixtures/state/**,tests/test_install_dry_run.py,.pylintrc,docs/architecture.md,CONTRIBUTING.md,.ai/project/known-risks.md" \
  --tests "tests/test_state_characterization.py,tests/test_ai_task_state.py,tests/test_dialog_contract.py,tests/test_dialog_gate.py,tests/test_state_layout.py" \
  --declare behaviour=0:"no guard decision, refusal, approval or install path changes; golden byte-identical" \
  --declare novelty=0:"stdlib only, the sibling-module pattern of sensors.py and memory_*.py" \
  --declare domain=0:"plugin internals" \
  --plan-file docs/sdlc/plans/small-oop-modules.steps.json --no-batch
```

`small-oop-modules.steps.json` is written at start from the Order of work (`s0`–`s8`, each
with its `files`, `tests`, `after`). Preconditions: no task in flight (`state.py status`),
the human has read this plan, FC1/OQ2 and FC6 have an explicit word.
