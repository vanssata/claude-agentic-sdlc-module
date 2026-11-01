# T-2026-10-31-1909-wp1-split-skills-ai-task — WP1: split skills/ai-task/state.py into rr_state/ behind an unchanged entry; behaviour pinned by the characterization golden

refactoring · guarded · started 2026-10-31T19:09:17Z · claude

## Weight

```
scope          2  tools/state-partition.py referenced from 6 files
behaviour      1  keyword 'workflow' in CONTRIBUTING.md
reversibility  0  git revert returns everything
domain         0  plugin internals (declared)
novelty        0  stdlib only, the sibling-module pattern of sensors.py and memory_*.py (declared)
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T19:09:17Z — /rr-build-all docs/sdlc/plans/small-oop-modules.md (Q22); restart with after from partition.json's real imports (plan §Start), s0-s2 already in the tree

## Plan

files: skills/ai-task/state.py, skills/ai-task/rr_state/**, tools/state-partition.py, tests/test_state_layout.py, tests/test_state_characterization.py, tests/fixtures/state/**, tests/test_install_dry_run.py, tests/test_dialog_contract.py, .pylintrc, docs/architecture.md, CONTRIBUTING.md, .ai/project/known-risks.md, tests/test_rename.py
tests: tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_state_layout.py
- s0 · tools/state-partition.py, tests/fixtures/state/partition.json, tests/test_state_layout.py · tests/test_state_layout.py · done
- s1 · tests/test_state_characterization.py, tests/fixtures/state/goldens/help.txt, tests/fixtures/state/goldens/light.txt, tests/fixtures/state/goldens/guarded.txt, tests/fixtures/state/goldens/full.txt, tests/fixtures/state/goldens/dialog.txt · tests/test_state_characterization.py · done
- s2 · skills/ai-task/state.py · tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py · done · after s1
- L0-fs · skills/ai-task/rr_state/fs.py, skills/ai-task/rr_state/__init__.py · no tests · done · after s0, s2
- L0-locks · skills/ai-task/rr_state/locks.py · no tests · done · after s0, s2
- L1-ledger · skills/ai-task/rr_state/ledger.py · no tests · done · after s0, s2, L0-fs
- L1-questions · skills/ai-task/rr_state/questions.py · no tests · done · after s0, s2, L0-fs
- L1-runtime · skills/ai-task/rr_state/runtime.py · no tests · done · after s0, s2, L0-fs
- L2-journal · skills/ai-task/rr_state/journal.py · no tests · done · after s0, s2, L0-fs, L1-runtime
- L3-policy · skills/ai-task/rr_state/policy.py · no tests · done · after s0, s2, L0-fs, L2-journal
- L3-task · skills/ai-task/rr_state/task.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal
- L4-dialog · skills/ai-task/rr_state/dialog.py · no tests · done · after s0, s2, L0-fs, L0-locks, L1-ledger, L1-runtime, L2-journal, L3-policy, L3-task
- L4-gate · skills/ai-task/rr_state/gate.py · no tests · done · after s0, s2, L0-fs, L0-locks, L1-questions, L2-journal, L3-task
- L4-report · skills/ai-task/rr_state/report.py · no tests · done · after s0, s2, L0-fs, L0-locks, L1-questions, L2-journal, L3-policy, L3-task
- L5-memory_cmd · skills/ai-task/rr_state/memory_cmd.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal, L3-task, L4-dialog
- L5-profile · skills/ai-task/rr_state/profile.py · no tests · done · after s0, s2, L0-fs, L1-ledger, L1-runtime, L3-task, L4-dialog
- L6-handoff · skills/ai-task/rr_state/handoff.py · no tests · done · after s0, s2, L0-fs, L1-questions, L1-runtime, L2-journal, L3-policy, L3-task, L5-profile
- L7-close · skills/ai-task/rr_state/close.py · no tests · done · after s0, s2, L0-fs, L2-journal, L3-policy, L3-task, L4-dialog, L4-gate, L4-report, L6-handoff
- L7-gate_cmd · skills/ai-task/rr_state/gate_cmd.py · no tests · done · after s0, s2, L0-fs, L2-journal, L3-task, L4-dialog, L4-gate, L4-report, L6-handoff
- L7-questions_cmd · skills/ai-task/rr_state/questions_cmd.py · no tests · done · after s0, s2, L0-fs, L0-locks, L1-questions, L2-journal, L3-task, L4-dialog, L4-gate, L6-handoff
- L7-report_cmd · skills/ai-task/rr_state/report_cmd.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal, L3-task, L4-dialog, L4-report, L5-profile, L6-handoff
- L7-review · skills/ai-task/rr_state/review.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal, L3-policy, L3-task, L4-dialog, L4-report, L6-handoff
- L7-start · skills/ai-task/rr_state/start.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal, L3-policy, L3-task, L4-dialog, L4-report, L5-profile, L6-handoff
- L7-steps · skills/ai-task/rr_state/steps.py · no tests · done · after s0, s2, L0-fs, L2-journal, L3-policy, L3-task, L4-dialog, L4-report, L6-handoff
- L7-verify · skills/ai-task/rr_state/verify.py · no tests · done · after s0, s2, L0-fs, L1-runtime, L2-journal, L3-policy, L3-task, L4-dialog, L4-report, L6-handoff
- L8-dialog_cmd · skills/ai-task/rr_state/dialog_cmd.py · no tests · done · after s0, s2, L0-fs, L1-ledger, L1-runtime, L3-task, L4-dialog, L5-profile, L7-questions_cmd
- s8 · skills/ai-task/rr_state/cli.py, skills/ai-task/state.py, tests/test_state_layout.py, .pylintrc, tests/test_install_dry_run.py, tests/test_dialog_contract.py · tests/test_state_characterization.py, tests/test_ai_task_state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_project_update.py, tests/test_skills_surface.py, tests/test_state_layout.py, tests/test_install_dry_run.py · done · after L0-fs, L0-locks, L1-runtime, L1-questions, L1-ledger, L2-journal, L3-policy, L3-task, L4-gate, L4-dialog, L4-report, L5-profile, L5-memory_cmd, L6-handoff, L7-questions_cmd, L7-gate_cmd, L7-report_cmd, L7-steps, L7-start, L7-verify, L7-review, L7-close, L8-dialog_cmd, s0, s1, s2
- s9 · docs/architecture.md, CONTRIBUTING.md, .ai/project/known-risks.md · tests/test_instruction_budget.py · done · after s0
amended 2026-10-31T19:54:48Z: +tests/test_rename.py — the allow-list entry of the old-name compat reader moves with the code: state.py:520 (read_profile fallback to <home>/claude-agentic/profile.json) is now rr_state/profile.py:28, its two explanatory comments rr_state/dialog.py:167,182; same invariant, new path (like R9's dry-run list)

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 82eb710ab | .ai/state/logs/T-2026-10-31-1909-wp1-split-skills-ai-task/suite-1.log | no |
| 2 | suite | 1 | e2a4a54b3 | .ai/state/logs/T-2026-10-31-1909-wp1-split-skills-ai-task/suite-2.log | no |
| 3 | suite | 0 | e2a4a54b3 | .ai/state/logs/T-2026-10-31-1909-wp1-split-skills-ai-task/suite-3.log | no |
| 4 | e2e | 0 | e2a4a54b3 | .ai/state/logs/T-2026-10-31-1909-wp1-split-skills-ai-task/e2e-4.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
Review of T-2026-10-31-1909, guarded mode, bounded inputs. I used about 31 tool calls. There was no review-ledger.md or sensors.json for this task, so I inherited nothing.

- [LOW] L1 `fs.ENTRY` defaults to `""`, but R6a says the default is "the package's parent joined with `state.py`" (`skills/ai-task/rr_state/fs.py:20`). in_scope: yes
  why it matters: code that imports `rr_state` without the shim would print `''` in refusal commands and compute `dirname("")` for the plugin root and migrations lookup. No shipped path does this: every caller goes through `state.py`, and the layout test only imports modules. It is a documented deviation from the spec, not a live bug.
  suggested direction: set the default to `os.path.join(dirname(dirname(__file__)), "state.py")`. R6a bans `__file__` under `rr_state/`, so that means a spec change, or leave it as is and record it.

- [LOW] L2 `# pylint: disable=unused-argument` is module-wide in `dialog_cmd`, `memory_cmd`, `report_cmd`, `start`, `verify` and `steps` (`steps.py:5` has no reason at all). in_scope: yes
  why it matters: `unused-argument` is now silenced for every function in those files. A future function that really drops an argument (or a missed `rt`) passes lint. R7 says "no new disable" about `.pylintrc`; these are inline, so the letter holds and the intent is bent.
  suggested direction: give `steps.py` a reason, or scope the disables to the `cmd_*` and `memory_*` handlers.

- [LOW] L3 The `Runtime()` default masks an omitted `rt`. 88 defs default to `rt=rr_runtime.Runtime()`, which means runtime "unknown" and mutating False. in_scope: yes
  why it matters: a future caller that forgets `rt=rt` records "unknown" in journal lines and skips the claim in `task.load`, silently. That failure matches the old global's default, so it is not a regression. I found no omission today (see EXAMINED AND CLEAN).
  suggested direction: none now. The layout test could pin "every call to an rt-taking callee inside a function holding `rt` passes it".

- [INFO] I1 NORMALISE has two broad rules. in_scope: yes
  `TREE9` (`\b(?=[0-9a-f]*\d)[0-9a-f]{9}\b`) and `TREE40` erase every tree value. The golden therefore cannot detect two tree values swapped in a message such as "was passing on <TREE9>, now <TREE9>". In the goldens `TREE9` only ever hides tree words (I read every context). The unit suites (`test_ai_task_state`) cover tree identity. This is the FC8 residue and I accept it. `ISO_TS` also hides whether a timestamp carries a fraction.

- [INFO] I2 Continuation lines in copied calls are misaligned after qualification and `rt=rt` were added (`review.py:86-93`, `dialog_cmd.py:79-80,129-132`, `verify.py:174-181`, `task.py:105-106`). in_scope: yes
  This is whitespace only and pylint does not flag it, but it is drift from "copied verbatim".

- [INFO] I3 Alias spelling is inconsistent (`rr_policy`, `rr_report`, `rr_runtime`, `questions_mod`). `dialog.py` is 610 lines against the 600 advisory. `Ledger` and `Profile` were not added, which the spec permits. in_scope: yes
  None of this affects behaviour.

- [INFO] I4 `tests/test_rename.py` is a pure relocation, not a weakening. in_scope: yes
  The `state.py` allow-list entry moved to `rr_state/profile.py`. The `rr_state/dialog.py` entry exists because the `read_profile()` fallback comment (the "claude-agentic/ fallback" text) now sits in `dialog.py:167`; HEAD's `state.py` carried the same comment under the one old entry. The allow-list now has two entries instead of one, with no new category.

- [INFO] I5 `test_state_layout.py` has 4 skips (`entry_defines_main()` phase gating at `:231` and `:266`). The skipped classes are the pre-cut-over forms; the post-cut-over classes run, 38 tests ok. in_scope: yes

## EXAMINED AND CLEAN
- FC8, NORMALISE.
  - I read the docstring and the code. The exact replacements are STATE_PY, ROOT, TMP, PLUGIN_ROOT and TASK_IDS, applied longest first, with STATE_PY before PLUGIN_ROOT. The regex rules are ISO_TS, TREE40, TREE9 and DURATION.
  - The entry path is an exact token and no regex touches a path. `<PLUGIN_ROOT>/skills/ai-task/rr_state/x.py` stays visible, and a test pins "no rule erases a module path".
  - No exit code, line order or arbitrary number is erased. DURATION only follows `exit N `. The goldens contain no `rr_state` text.
  - The goldens (21:01–21:02) were written before any `rr_state` module existed (21:11 onward) and before the shim (21:45), so they were recorded on the original `state.py`. No UPDATE_GOLDENS use is recorded in the task events.
- FC9, cut-over, `cli.main` against HEAD's `main`.
  - The parser is identical. `description` is the literal first docstring line, covered by `help.txt`.
  - The three resolutions match:
    - topic mode gets `Runtime()` (unknown, mutating False), as the old untouched globals gave.
    - `profile` computes its name from `--runtime`, then `AI_RUNTIME`, then `CLAUDECODE`, with mutating False.
    - everything else gets `detect_runtime` plus `args.command in MUTATING_COMMANDS`.
  - The order is `route_surface`, then `guard_pending` (not for `close --abandon`, via the `getattr` on abandon), then `sync_dialog`, then `func`. The claim stays inside `task.load` (`rt.mutating if claim is None else claim`). `guard_pending` and `route_surface` load with `claim=False`, so no claim moved ahead of a refusal.
  - `MUTATING_COMMANDS`, `BLOCKING_COMMANDS` and `DIALOG_SYNC_COMMANDS` are unchanged.
  - The shim does `sys.path.insert(0, …)` first, then imports `fs` inside try/except ImportError with a one-line exit, then sets `fs.ENTRY = os.path.abspath(__file__)` before importing `cli`. The git mode is 100755.
  - The old "global RUNTIME/MUTATING" are gone. `abandon_old` still receives `(args, root, rt=rt)` through `args.func`.
- `rt` threading (the golden only exercises runtime "claude").
  - I took the 81 names that have an `rt=` parameter and grepped every call site. I looked at the continuation lines of every multi-line call, including all 8 `journal_line(` sites (HEAD has 8) and every `emit`, `offer_decision`, `open_decision`, `apply_choice` and `cmd_answer` call. Every call passes `rt=rt` or `runtime=rt.name`.
  - The `own_runtime`, `dialog_on`, `journal_line` and `other_runtime` calls all pass `runtime=`. A missing `rt` inside a function with no `rt` parameter would also be a NameError, and pylint stays at baseline.
  - All 15 old `RUNTIME` and `MUTATING` uses map to `rt.name` or `rt.mutating`: `task.py:79-107`, `handoff.py:34,184,203`, `start.py:188`, `verify.py:73,91`, `review.py:120`, `memory_cmd.py:225`.
  - `MEMORY_ACTIONS[action](…, rt=rt)` and `decision_open` and `decision_settle` pass it on.
- Body drift. I normalised module qualifiers, `rt=rt` and `rt.name` on both sides and compared the line sets of HEAD's `state.py` and all of `rr_state/`. The lines left on the old side are the module docstring and usage text (moved to the shim), the `def` lines that gained `rt`, `__file__` to `ENTRY`, `RUNTIME` to `rt.name`, and the `LOCK_DEPTH` and `DIALOG_PICK` holders. No reworded line, dropped comment, changed default or changed constant remains. `LEDGER_LINE_MAX, LOCK_STALE = 4096, 2.0` was split into two assignments with the same values.
- Seams and constructs. Under `rr_state/` there are no `global` statements and no `__file__` (the `grep` for `^global` and `__file__` found none). I found no `from json import` or `from os import` in `rr_state/`, and no `from rr_state.<mod> import <function>`; the only such imports are in the shim's re-exports, where they belong. `LOCK_DEPTH[0]` and `DIALOG_PICK[0]` are used consistently, with `dialog.DIALOG_PICK[0]` read qualified from `gate_cmd` and `review`.
- Labels and refusals. Every printed command uses `fs.ENTRY`. Sites checked: `dialog.py` (89, 266, 283, 511, 595), `profile.py` (266, 271, 362), `questions_cmd`, `verify`, `memory_cmd`, `steps`, `review`, `start`, `report.py:155`, `runtime.py:26,60`. The directory walks keep their `dirname` depth: `report.py` uses 2 (migrations) and `profile.py` uses 3 (resolver).
- R15 and R16. `memory-pre-push.py` only imports `memory_sync` from `skills/ai-task`, with no `rr_state` or `state` import. The layout test asserts no crossing in either direction. I spot-checked the core-labelled functions `close_owed`, `arm_scope`, `installer_command`, `old_surface_refusal`, `context_mode` and `gate_approved_for` and found no `os.`, `open(`, `time.`, `fs.` or `environ` in them. The all-core-module import check passes.
- Test edits. The two lines of `test_dialog_contract.py` match Q24. The dropped `RUNTIME` patch was inert because `dialog_policy(root)` takes no runtime, and `dialog_on(root, runtime=runtime)` is equivalent to the old patched call. The dry-run list gained the two spec'd files. No other test file was edited, and none was skipped or weakened. No `state_mod` patch targets a retired global.
- Packaging. The installer copies the skill directory whole, skipping `__pycache__` (`bin/riskrails.js:759-775`). `ai-path-guard-defaults.json:40` protects the whole `skills/ai-task/` directory, so `rr_state/` is covered. `status.py`, `riskrails.js`, `context-guard` and `runtime-gate` only reference the `state.py` path.
- Re-exports beyond the R6 greps: `json_loads_capped` is justified by `tests/test_dialog_contract.py:176,189`; `json` and `os` are imported in the shim for the same reason.
- I reran `tests/test_state_characterization.py` and `tests/test_state_layout.py`: 47 tests, OK (4 skipped, phase-gated).
- Not reached (budget): the 1 213-test suite and e2e (inherited from the last verify, suite-3 and e2e-4 green). The timing claim of R8 (not re-measured, per instructions). A runtime-"codex" path run end to end (covered statically by the `rt` audit; the unit suites hold `handoff --to`). `tools/state-partition.py` internals beyond what the layout test exercises.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the plan. The edits are the shim, the 25 `rr_state` modules, the partition tool and fixtures, the two new suites, the R6/R9-listed test edits, `.pylintrc` (one `never-returning-functions` entry), `CONTRIBUTING.md` and `docs/architecture.md`. The only addition outside the spec's list is the `test_rename.py` allow-list relocation, which is pure. There are no open BLOCKER or HIGH findings, only LOW and INFO notes.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .pylintrc | +1 −1 | Edit |
| CONTRIBUTING.md | +15 −0 | Edit |
| docs/architecture.md | +38 −1 | Edit |
| skills/ai-task/rr_state/__init__.py | +1 −0 | New |
| skills/ai-task/rr_state/cli.py | +210 −0 | New |
| skills/ai-task/rr_state/close.py | +171 −0 | New |
| skills/ai-task/rr_state/dialog.py | +610 −0 | New |
| skills/ai-task/rr_state/dialog_cmd.py | +164 −0 | New |
| skills/ai-task/rr_state/fs.py | +214 −0 | New |
| skills/ai-task/rr_state/gate.py | +125 −0 | New |
| skills/ai-task/rr_state/gate_cmd.py | +125 −0 | New |
| skills/ai-task/rr_state/handoff.py | +226 −0 | New |
| skills/ai-task/rr_state/journal.py | +126 −0 | New |
| skills/ai-task/rr_state/ledger.py | +145 −0 | New |
| skills/ai-task/rr_state/locks.py | +84 −0 | New |
| skills/ai-task/rr_state/memory_cmd.py | +310 −0 | New |
| skills/ai-task/rr_state/policy.py | +378 −0 | New |
| skills/ai-task/rr_state/profile.py | +373 −0 | New |
| skills/ai-task/rr_state/questions.py | +336 −0 | New |
| skills/ai-task/rr_state/questions_cmd.py | +321 −0 | New |
| skills/ai-task/rr_state/report.py | +271 −0 | New |
| skills/ai-task/rr_state/report_cmd.py | +230 −0 | New |
| skills/ai-task/rr_state/review.py | +164 −0 | New |
| skills/ai-task/rr_state/runtime.py | +80 −0 | New |
| skills/ai-task/rr_state/start.py | +257 −0 | New |
| skills/ai-task/rr_state/steps.py | +131 −0 | New |
| skills/ai-task/rr_state/task.py | +395 −0 | New |
| skills/ai-task/rr_state/verify.py | +231 −0 | New |
| skills/ai-task/state.py | +23 −5299 | Edit |
| tests/test_dialog_contract.py | +3 −3 | Edit |
| tests/test_install_dry_run.py | +1 −0 | Edit |
| tests/test_rename.py | +2 −1 | Edit |
| tests/test_state_layout.py | +253 −6 | Edit |

+6014 −5311 lines, 33 files

## Verdict

close: closed
facts: (a) green — suite green on e2a4a54b3 (run 3) · (b) green — 33 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 3 · review passes: 1
