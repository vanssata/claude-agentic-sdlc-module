# Plan: Small OOP modules — WP1b, no re-exports on `state.py`

Spec: `docs/sdlc/specs/small-oop-modules.md` (§Work packages row 1b; R6 as rewritten by Q25;
OQ3 closed) · Programme: `docs/sdlc/plans/small-oop-modules.md` · WP1 closed in `b9bb20f` ·
Written 2026-10-31 23:20. WP2 was dropped by Q26 (`adopt.py` is deleted by the
regenerate-not-migrate task, `docs/sdlc/intent/riskrails-regenerate-not-migrate.md`), so
this is the next small-oop-modules task. **Not started**: `state.py start` runs after the
human commits this plan.

<!-- Stage 3. Concrete steps with their dependencies; /rr-build-all dispatches the ready ones in parallel, this session records them. -->

## Weight, measured (2026-10-31 23:20, `state.py weight`, not journaled)

```
scope · behaviour · reversibility 0 · domain 0 (declared: "import lines of the state suites
and the entry; no auth, data or payments") · novelty 0 (declared: "the WP1 layout,
re-exports removed") · coverage 0  →  W 3 → guarded
```

Guarded: one review on BALANCED, `verify + e2e`. C3 (refactoring only), C4, C5.

## What changes (KNOWN FACT, grep 2026-10-31 23:00)

`state.py:76-89` re-exports 44 names for five suites that do `import state as state_mod`:
`tests/test_ai_task_state.py:28`, `tests/test_dialog_contract.py:19`,
`tests/test_dialog_gate.py:30`, `tests/test_task_id.py:21`, `tests/test_project_update.py:885`.
Under Q25 each `state_mod.<name>` becomes the owning module (`from rr_state import task` →
`task.load`, a patch on the module the code looks the name up in). Stays, as the entry used
as an entry: `import state; state.main()` (`tests/test_ai_task_state.py:35`, the
characterization and layout tests), `state_mod.__file__`; `state_mod.json` / `state_mod.os`
are the stdlib modules and become `json` / `os`. `skills/ai-task/memory_compact.py` names
`state.py` only in a comment — untouched.

A test edit is import lines, qualified names and patch targets only; an assertion, an
expected text or a fixture is never edited (R6). The implementer's `## RESULT` says so and the
review reads every test hunk first.

## Order of work

| Step | Files | Tests (step scope) | After |
|---|---|---|---|
| b1 | `tests/test_ai_task_state.py` | that file, `tests/test_state_characterization.py` | — |
| b2 | `tests/test_dialog_contract.py`, `tests/test_dialog_gate.py` | those files | — |
| b3 | `tests/test_task_id.py`, `tests/test_project_update.py` | those files | — |
| b4 | `skills/ai-task/state.py` (`:76-89` deleted; `fs.ENTRY` and `from rr_state.cli import main` stay); `tests/test_state_layout.py` (the re-export check becomes: the entry imports nothing from `rr_state` but `fs` and `cli.main`, and no `state_mod.<name>` other than `main` / `__file__` in `tests/`, `exec`'d snippets included) | `tests/test_state_characterization.py`, `tests/test_state_layout.py`, the five suites of b1–b3 | b1, b2, b3 |

b1–b3 in parallel (three Sonnet 5.5 implementers), b4 after. Then `verify --scope all` (it
runs e2e itself), one review (BALANCED), fixes as a parallel batch, `/rr-ship`.

## Proof

`tests/test_state_characterization.py` byte-identical; every suite green with its assertions
untouched; `tests/test_state_layout.py` fails on a re-export or a `state_mod.<name>` left.

## Rollback

`git revert` of the task's commit restores the re-exports (R14).

## Start — later, not now

```bash
$STATE start --goal "WP1b: state.py re-exports nothing; the suites import the owning rr_state module (Q25)" \
  --workflow refactoring \
  --files "skills/ai-task/state.py,tests/test_ai_task_state.py,tests/test_dialog_contract.py,tests/test_dialog_gate.py,tests/test_task_id.py,tests/test_project_update.py,tests/test_state_layout.py" \
  --tests "<every step's tests>" \
  --declare 'domain=0:"import lines of the state suites and the entry; no auth, data or payments"' \
  --declare 'novelty=0:"the WP1 layout, re-exports removed"' \
  --plan-file <scratchpad>/steps.json --batch --by "Ivan Kakurov" \
  --why "/rr-build-all docs/sdlc/plans/small-oop-modules-wp1b.md"
```
