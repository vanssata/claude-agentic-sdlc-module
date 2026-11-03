# T-2026-11-03-1952-wp1b-state-py-re-exports — WP1b: state.py re-exports nothing; the suites import the owning rr_state module (Q25)

refactoring · guarded · started 2026-11-03T19:52:04Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 69 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  "import lines of the state suites and the entry; no auth, data or payments" (declared)
novelty        0  "the WP1 layout, re-exports removed" (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-11-03T19:52:04Z — /rr-build-all docs/sdlc/plans/small-oop-modules-wp1b.md

## Plan

files: skills/ai-task/state.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_task_id.py, tests/test_project_update.py, tests/test_state_layout.py
tests: tests/test_ai_task_state.py, tests/test_state_characterization.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_task_id.py, tests/test_project_update.py, tests/test_state_layout.py
- b1 · tests/test_ai_task_state.py · tests/test_ai_task_state.py, tests/test_state_characterization.py · done
- b2 · tests/test_dialog_contract.py, tests/test_dialog_gate.py · tests/test_dialog_contract.py, tests/test_dialog_gate.py · done
- b3 · tests/test_task_id.py, tests/test_project_update.py · tests/test_task_id.py, tests/test_project_update.py · done
- b4 · skills/ai-task/state.py, tests/test_state_layout.py · tests/test_state_characterization.py, tests/test_state_layout.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_task_id.py, tests/test_project_update.py · done · after b1, b2, b3

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 303bf5de3 | .ai/state/logs/T-2026-11-03-1952-wp1b-state-py-re-exports/suite-1.log | no |
| 2 | e2e | 0 | 303bf5de3 | .ai/state/logs/T-2026-11-03-1952-wp1b-state-py-re-exports/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS

Reviewed in guarded mode against the diff at base 974eb04. Every test hunk was read against R6 before the other checks.

- [LOW] L1 The layout test's use check is blind to any spelling except `state_mod.<name>`, and the entry's import check stops at the sys.path insert (`tests/test_state_layout.py:~420-445`, `:302-306`)  in_scope: yes
  why it matters: the plan (b4) asks for exactly the `state_mod.<name>` and `patch.object(state_mod, …)` greps, and the test delivers them, including exec'd snippets, because it scans the raw file text. The checks have gaps, though.
  - They catch `state_mod.load(` and `patch.object(state_mod, "load")`, and a leftover inside a string snippet (`test_the_use_check_sees_a_leftover` pins all three).
  - They do not catch `import state as s; s.load`, `from state import load`, or `state.load` through the bare `import state` that two suites now keep.
  - The entry import check does catch a re-added `from rr_state.<mod> import x` or `import rr_state.x`, anywhere in the file, via `ast.walk`.
  - A re-export of a non-package name is caught only if it sits before the `sys.path.insert` line. For example `import json` added after it, or a module-level `load = …`, passes. The line cap (<200) is the only other guard.
  - Both gaps are small. Nothing in the current tree exploits them: grep shows no `from state import`, `state_mod` (apart from `tests/test_dialog_contract.py:19,87`, `__file__` only) or `state.<name>` in tests, and the only `import state` hits are the two bare imports, the SHIM string and `test_state_characterization.py`.
  failure scenario: a future suite writes `import state as s; s.read_session(...)`. Q25 is violated and the layout test stays green.
  suggested direction: optionally widen the regex to any alias of `state`, or add an AST check that tests never read attributes off the entry module. This is not needed to close WP1b.

- [LOW] L2 Possible pylint W0621 (redefined-outer-name) from the new module-level `import state` in `tests/test_ai_task_state.py:28`  in_scope: yes
  why it matters: `state` is now a module-level name in that file. Functions bind a local `state` at `:661`, `:1785` and `:2684`, and `:3410` binds one too. Pylint would likely report W0621 for these.
  - `.pylintrc` fails only on E, F, W0702 and W1510, with a 9.9 score floor.
  - A few warnings should not break CI, but the score impact is unmeasured because pylint is not installed here and no sensors.json exists for this task.
  - `tests/test_dialog_gate.py` has no local `state` binding, so it is unaffected.
  failure scenario: CI lint score drops slightly. It would break only if the ratio is already marginal.
  suggested direction: run the lint command once. If it warns, `import state as _entry` or an inline disable fixes it.

- [INFO] I1 Observation, `in_scope: yes`: the bare `import state` is necessary and sufficient for the suites that need it, and the in-process order of tests does not mask a missing import
  - It is needed because `import state` sets `rr_state.fs.ENTRY`, which `labels.validate_label` (`labels.py:77,94`), `dialog.py` (`:88,442,526`) and `runtime.py:26,60` read at call time. Their default is `""`.
  - Where `ENTRY` is read in the suites that have no entry import: `tests/test_task_id.py` calls `next_task_id`, `valid_task_id` and `TASK_ID_RE`, and `tests/test_project_update.py` calls `fs.state_path` and `task.load(claim=False)`. Neither read `ENTRY`.
  - Standalone passes: `test_task_id` (14 tests), `test_dialog_contract` (9 tests), `test_state_layout` (15 tests) and `test_project_update.TestMigration0009` (9 tests), each in a fresh process with no prior `import state`.
  - `test_dialog_gate.py`'s bare import is partly redundant, because it also imports `test_ai_task_state` (which does the same import). That is harmless and explicit.
  - `test_dialog_contract.py` keeps `import state as state_mod` (used only for `__file__`, `:87`), which also sets `ENTRY`.
  - The latent risk is theoretical. A future suite that calls `validate_label` or `dialog_*` and imports only `rr_state.*` would see `ENTRY == ""` when run alone and pass or fail by test order.

- [INFO] I2 `tests/test_task_id.py` leans on import order
  - `memory_harness` (line 17, `sys.path.insert(0, AI_TASK)`) must be imported before `from rr_state import task`. It is, and the standalone run passes.
  - Reordering the imports would break it, and there is no comment saying so. Every other test importing ai-task modules either inserts its own path or imports `memory_harness`, so the `test_project_update.py` leak removal is not depended on.

- [INFO] I3 Out of scope, observation
  - Nothing outside the tests reaches `state.<name>`. Grep of hooks, bin, scripts, skills and docs outside `docs/sdlc` found only subprocess invocations of `state.py` by path (`hooks/guard/dialog.py`, `hooks/context-guard.py`), the path string in `rr_state/handoff.py:194`, and docs that name `state.json`.
  - I did not grep `docs/sdlc`'s specs, plans and reports for code snippets that show `state_mod`.

## EXAMINED AND CLEAN

- **R6 test hunks, all five suites** (`tests/test_ai_task_state.py`, `tests/test_dialog_contract.py`, `tests/test_dialog_gate.py`, `tests/test_task_id.py`, `tests/test_project_update.py`)
  - Every hunk is an import line, a `state_mod.X` to `rr_<owner>.X` qualification, or a patch target.
  - No assertion, expected text or fixture changed.
  - Only whitespace drifted: the `rescore` continuation line in `test_ai_task_state.py` is now off by one column, and pylint's C checks are disabled.
- **Owner of each name** matches where the old re-export imported it from. For example `AGENT_MARKERS` is in `runtime`, `current_tree`, `session_path` and `read_session` are in `fs`, `abandon_old` and `sealed_task_ids` are in `task`, and `archive_v7` is in `close`.
- **json/os patches** (`tests/test_ai_task_state.py:632-658`)
  - The old `state_mod.json` and `state_mod.os` were the stdlib module objects, so `patch.object(json, "dump")` and `patch.object(os, "replace")` act on the same objects as before.
  - `wraps=os.replace` is still evaluated before the patch is applied.
  - The package code `close.py`/`task.py` reaches `os.replace` and `json.dump` through its own `import os`/`import json`, which are those same modules, so the patches exercise the same behaviour. No patch moved off an inert re-export binding.
- **`tests/test_dialog_contract.py` `run(rr_dialog, text)`** compares the same `json_loads_capped` function the entry used to re-export.

- **`skills/ai-task/state.py`**
  - After the change it holds `import os`/`import sys`, `fs.ENTRY` and `from rr_state.cli import main`.
  - The `json` import is gone and nothing in the entry uses it.
  - `fs.ENTRY = os.path.abspath(__file__)` is intact, and the file is 73 lines (the layout test checks <200).
- **`tests/test_project_update.py` sys.path**
  - The function-local import now runs between exactly two inserts and `del sys.path[:2]`. The old `import state` inserted a third entry, so the old `[:2]` delete left the ai-task dir behind. That leak is now gone.
  - No later test depends on it, as shown under I2.
  - The `rr_state` modules stay in `sys.modules`, as they did before with `state`.
- **Other `tests/test_state_layout.py` assertions**
  - The "before the sys.path insert" assertion now expects `["import os", "import sys"]`, which is the intended drop of `import json`.
  - `SHIM_ABSENT`, `INDIRECT` and `expected_reexports` are removed, and nothing references them any more.
  - The surviving `test_the_entry_main_and_paths` still checks `state.main` against `rr_state.cli.main`, `__file__` and `fs.ENTRY`.
  - Dropping the old `state.json is json` and `state.os is os` assertions matches the new rule that the entry has no `json` or `os` attributes to inherit.
- **`tests/test_state_characterization.py`** is byte-identical: `git status` shows it unmodified and the diff is empty.
- **Last verify**: `suite-1.log` ends green (1239 tests, 9 skipped, 76.7 s) and `e2e-2.log` ends green (5 tests).
- **Not reached (budget)**
  - No mutation run of the layout test: a re-export added, a leftover `state_mod.x`, `from state import x`. L1 comes from reading the regexes and AST walk.
  - Pylint and `run_suite.py` were not run (pylint is not installed here).

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the approved plan. The entry loses its re-export block, the suites take import and qualification edits only, and `tests/test_state_layout.py` gets the rewritten R6 check. The characterization test is untouched. No behaviour change found. The two LOW findings are a check-coverage gap in the new layout test and a probable lint warning. Neither blocks, but both can be closed cheaply.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/ai-task/state.py | +1 −21 | Edit |
| tests/test_ai_task_state.py | +44 −39 | Edit |
| tests/test_dialog_contract.py | +17 −16 | Edit |
| tests/test_dialog_gate.py | +15 −14 | Edit |
| tests/test_project_update.py | +3 −3 | Edit |
| tests/test_state_layout.py | +34 −36 | Edit |
| tests/test_task_id.py | +4 −4 | Edit |

+118 −133 lines, 7 files

## Verdict

close: closed
facts: (a) green — suite green on 303bf5de3 (run 1) · (b) green — 7 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
