# Reviews of the spec `small-oop-modules` (2026-10-31)

Moved out of `docs/sdlc/specs/small-oop-modules.md` in the evening refine pass of 2026-10-31
(spec budget, Optimisation 4: evidence in linked material). The spec's requirements marked †
and its resolved concerns FC10 and FC13 point here. Nothing below was changed in the move.

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
