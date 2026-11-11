# T-2026-11-11-2211-wp5-hooks-guard-paths-py — WP5: hooks/guard/paths.py becomes the path-guard entry and sibling paths_* rule modules; behaviour unchanged

refactoring · guarded · started 2026-11-11T22:11:25Z · claude

## Weight

```
scope          2  hooks/guard/paths_base.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in CONTRIBUTING.md
reversibility  0  git revert returns everything
domain         0  "moves path-guard code verbatim between modules; no rule, pattern, cap or message changes" (decl
novelty        0  "the WP1-WP4 pattern on a fifth file; guard/ is already a package" (declared)
coverage       2  0 of 9 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-11-11T22:11:25Z — /rr-build-all docs/sdlc/plans/small-oop-modules-wp5.md

## Plan

files: tests/fixtures/guard/partition.json, tests/test_guard_layout.py, hooks/guard/paths_base.py, hooks/guard/paths_fs.py, hooks/guard/paths_shell.py, hooks/guard/paths_human.py, hooks/guard/paths_interp.py, hooks/guard/paths_classify.py, hooks/guard/paths_movers.py, hooks/guard/paths_bash.py, hooks/guard/paths.py, tests/test_ere_unit.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, tests/test_codex_install.py, docs/architecture.md, CONTRIBUTING.md, docs/known-risks.md, docs/sdlc/plans/small-oop-modules-wp5.md
tests: tests/test_guard_layout.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_ai_git_guard.py, tests/test_ere_unit.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, tests/test_codex_install.py, tests/test_instruction_budget.py, tests/test_skills_surface.py
- s0 · tests/fixtures/guard/partition.json, tests/test_guard_layout.py · no tests · done
- s1 · hooks/guard/paths_base.py, hooks/guard/paths_fs.py, hooks/guard/paths_shell.py, hooks/guard/paths_human.py, hooks/guard/paths_interp.py, hooks/guard/paths_classify.py, hooks/guard/paths_movers.py, hooks/guard/paths_bash.py · no tests · done · after s0
- s2 · hooks/guard/paths.py, tests/test_ere_unit.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, tests/test_codex_install.py, tests/test_guard_layout.py · no tests · done · after s1, s0
- s3 · docs/architecture.md, CONTRIBUTING.md, docs/known-risks.md · no tests · done · after s1
amended 2026-11-11T22:41:42Z: +docs/sdlc/plans/small-oop-modules-wp5.md — review L2: record the phys_path deviation and the start in the plan, where the programme keeps its decisions

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | df5b41461 | .ai/state/logs/T-2026-11-11-2211-wp5-hooks-guard-paths-py/suite-1.log | no |
| 2 | e2e | 0 | df5b41461 | .ai/state/logs/T-2026-11-11-2211-wp5-hooks-guard-paths-py/e2e-2.log | no |
| 3 | step | 0 | fbe98b370 | .ai/state/logs/T-2026-11-11-2211-wp5-hooks-guard-paths-py/step-3.log | no |
| 4 | e2e | 0 | fbe98b370 | .ai/state/logs/T-2026-11-11-2211-wp5-hooks-guard-paths-py/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
I found no BLOCKER, HIGH or MEDIUM. The fail-open risk you asked me to dig into does not show up in this tree. There are three LOW findings, all in the docs and the task record, plus three INFO notes. Verdict: **pass**.

There was no `review-ledger.md` or `sensors.json` for this task, so I inherited nothing from a ledger. I took the verify logs as given: `suite-1.log` (1 395 OK, skipped 42) and `e2e-2.log`. Both were written after the last file edit (log 00:31:46, last edit 00:28:27). I reviewed against `.ai/` and the brief, read-only, in guarded mode.

## FINDINGS

- [LOW] L1 `CONTRIBUTING.md:96-98` — in_scope: yes
  - **What is wrong:** it tells contributors that a future pure move is proved with `python3 -I tests/test_guard_layout.py --moved-from <rev>`. That command only works against the old single-file `paths.py`. `moved_from` always reads `git show <rev>:hooks/guard/paths.py` (`partition.json` `"source"`, `tests/test_guard_layout.py:782-797`). It then looks up each module's names in that file.
  - **Failure scenario:** after this change, at any revision `paths.py` is the entry. A real move between two `paths_*` modules would then fail with "X is not in the source (D6)" for every name. Pointing it at a revision from before the split compares against old code, so it flags every legitimate edit made since. A contributor following the doc gets either false failures or an outdated comparison.
  - **Direction:** say the command proves the WP5 cut-over only, or describe what proves a later move (the golden plus `partition.json` edited to match).

- [LOW] L2 `docs/sdlc/plans/small-oop-modules-wp5.md:144` and `.ai/reports/T-2026-11-11-2211-wp5-hooks-guard-paths-py/task.md` — in_scope: yes
  - **What is wrong:** the plan's module map still puts `.phys_path` in `paths_classify`. The session's decision to keep it as a `PathGuard` method appears only in `partition.json`, the layout test and the `paths_classify.py` docstring (line 5). `task.md` has no mention of `phys_path` (checked with grep).
  - **Failure scenario:** a later reader or re-review checking against the plan sees the tree contradicting it, with no reason on record. The W0613 reasoning is sound; it just isn't written down where decisions live.
  - **Direction:** record the deviation and its reason in `task.md` (the main session's job).

- [LOW] L3 `docs/known-risks.md:49` — in_scope: yes
  - **What is wrong:** the "Source" line of the self-approval risk now names only `hooks/guard/paths_human.py`. The refusal itself, `raise Deny("Refusing 'state.py approve' …")`, is in `hooks/guard/paths_bash.py:58-59`. `paths_human` holds only `APPROVE_RE` and `dialog_consent`. The plan's s3 note ("the confirm gate's source") fits line 72, not line 49.
  - **Failure scenario:** someone auditing the approve gate from this risk entry reads the wrong module for the decision.
  - **Direction:** name both `paths_human.py` and `paths_bash.py` on line 49.

- [INFO] I1 upgrade window, `hooks/ai-guard.py:69-93` with `bin/riskrails.js:1179-1182,1474` — in_scope: no
  - **Why it matters (would be HIGH inside the boundary):** `paths.py` now needs eight sibling files at import time. Any state where the entry is new but a sibling is missing turns into a silent allow, and the scope check is skipped too. Examples: an install interrupted mid-copy, a hook firing while the copy loop runs (the glob copies `paths.py` before `paths_base.py`), or a hand-copied single file. The installer copies every `hooks/guard/*.py`, the two install tests now check all eight files, and the protected pattern `(guard|lib)/` covers the new files. So the steady state is fine; only the window between files is open. Risk register, not remediation.

- [INFO] I2 R8 margin — in_scope: yes. Read went from 18.1 to 19.5 ms (+7.7%) in one of the two runs, and Bash 1 KB from 35.3 to 37.7 ms (+6.8%). Both are inside the 10% bound, but importing eight more modules uses most of it. That matters for any later work package that adds import-time cost to the guard.

- [INFO] I3 the move proof is one-shot — in_scope: yes. In the final phase the suite cannot compare moved nodes against the old source; only the command-line `--moved-from` can. Once the change is committed, `--moved-from HEAD` no longer means anything. So the evidence of a faithful move is this task's recorded run plus the byte-identical golden. That is acceptable for D6; the record should say so.

## EXAMINED AND CLEAN

- **Test hunks (D5):** each hunk is allowed.
  - `test_ere_unit.py`: the import line and `paths_fs.find_print`.
  - `test_no_fallbacks.py`: the KEEP row moves to `paths_base.py`, which holds `WHY_TASK`, the text with `/project-update`.
  - `test_install_dry_run.py` and `test_codex_install.py`: the installed lists.
  - No assertion, expected text or fixture was edited, and the golden is untouched.
- **Method table:** 27 bindings. Each one is `name = paths_<home>.name` to a function of that name with `self` first. I counted 27 such functions across the modules, with no decorators.
- **Kept methods:** 9 are kept. `move_problems` compares the kept methods and `check` against HEAD; I re-ran it and got `move_problems: none`.
- **Nothing re-exported:** there is no `__all__`. The entry's imports (`T`, `WHY_WORK_CAP`, `cd_physical`, `lexnorm`, `chomp_all`, …) are all used by the kept methods.
- **Every `self.<attr>` before and after:** the set of names is identical except the five D3 renames (`_roots_under`, `_mode`, `_loc_pat`, `_loc_text`, `_from_loc`). Every name is either an instance attribute, a `MoverState` attribute or a bound method. Nothing reached through `self` is unbound.
- **Old method names elsewhere:** none in `hooks/`, `tests/`, `skills/`, `bin/` or `codex/`. There is no `getattr`, `globals()`, `sys.modules` or `__import__` in the `paths*` modules.
- **Name resolution (the fail-open risk):**
  - pylint (E0602 and E0401 on) rates `paths.py`, `paths_*.py` and `test_guard_layout.py` 10.00/10, so there are no undefined globals or failed imports.
  - Every `guard.common` name a module imports was already in the original import list, so each is the same object.
  - No module-level mutable state is mutated anywhere, so nothing is duplicated across module objects.
  - `LoopError` is defined once, in `paths_fs`; `realpath_m` raises it and `paths_movers` catches that same class (`:59`).
  - `Deny` is the single class from `guard.common`, as `ai-guard.py` expects.
  - The function-level imports (`datetime`, `guard.dialog` in `dialog_consent`) and the default arguments are unchanged.
  - The imports go only downward with no cycle (layers 0/1/2/3), and nothing imports the entry.
- **Top-level names:** every original top-level name exists in exactly one new module (set diff empty); the new names are only the moved functions.
- **Comments:** the sorted multiset of comment lines, old against new, shows no line lost. Each original block comment paired with the line that follows it gives the same pairs in the new tree. Only new headers were added (the method-table group labels, plus a repeated "the check" header in `paths.py`). Inline comments stay on identical code lines.
- **`test_guard_layout.py` and `partition.json`:**
  - The phase detection cannot quietly skip the final checks. Any extra top-level name in `paths.py` drops the tree into the copy phase, whose checks then fail loudly.
  - The final phase has a catch-all, `test_nothing_else_is_wrong`.
  - The synthetic tests show each check can fail, including a wrong binding, a binding left out, a stale renamed call and a drifting kept method.
  - `canon` drops None and [] fields; I see no realistic collision.
  - I ran the file myself: 58 tests OK (skipped 11, the single/copy phases).
- **Install routes:** the Claude and Codex installers both copy every `hooks/guard/*.py`, and the `codex-` filter does not hit `paths_*`. npm `files` ships `hooks/`.
- **Docs:** the `architecture.md` layers and edges match `partition.json`. "rr_state imports nothing under hooks/" holds: the only dynamic load in `rr_state`, in `profile.py:364`, is not hooks code. `known-risks.md:72` is correct (`confirm_delete` lives in `paths_human`).
- **Scope:** every changed file is in the task's file list.
- **Not reached (budget):** a line-by-line reading of the bodies of `paths_movers.movers` and `paths_bash.check_bash`. I relied on the AST comparison against HEAD, the golden and the differential test for those.

## VERDICT
verdict: pass
scope_assessment: the change stays inside the approved plan's files and the R6 test-edit rules. The one change to the plan's module map (`phys_path` kept in `PathGuard`) is justified, but it is not recorded in the plan or `task.md` (L2).

I created two scratch comparison files in `/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/c5881c69-38b9-4470-ac87-08434f20c6c7/scratchpad/`. Nothing in the repository was changed.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CONTRIBUTING.md | +9 −0 | Edit |
| docs/architecture.md | +16 −0 | Edit |
| docs/known-risks.md | +3 −2 | Edit |
| docs/sdlc/plans/small-oop-modules-wp5.md | +10 −3 | Edit |
| hooks/guard/paths.py | +48 −1406 | Edit |
| hooks/guard/paths_base.py | +59 −0 | New |
| hooks/guard/paths_bash.py | +176 −0 | New |
| hooks/guard/paths_classify.py | +205 −0 | New |
| hooks/guard/paths_fs.py | +137 −0 | New |
| hooks/guard/paths_human.py | +105 −0 | New |
| hooks/guard/paths_interp.py | +162 −0 | New |
| hooks/guard/paths_movers.py | +393 −0 | New |
| hooks/guard/paths_shell.py | +288 −0 | New |
| tests/fixtures/guard/partition.json | +172 −0 | New |
| tests/test_codex_install.py | +3 −0 | Edit |
| tests/test_ere_unit.py | +2 −2 | Edit |
| tests/test_guard_layout.py | +1445 −0 | New |
| tests/test_install_dry_run.py | +5 −1 | Edit |
| tests/test_no_fallbacks.py | +1 −1 | Edit |

+3239 −1415 lines, 19 files

## Verdict

close: closed
facts: (a) green — documents only since run 1 (3 files: CONTRIBUTING.md, docs/known-risks.md, docs/sdlc/plans/small-oop-modules-wp5.md); doc_tests green in run 3 on fbe98b370 · (b) green — 19 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 1
