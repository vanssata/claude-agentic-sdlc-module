# T-2026-10-29-2006-faster-task-cycle — Faster task cycle — parallel suite, fewer reruns, bounded review

feature · full · started 2026-10-29T20:06:10Z · claude

## Weight

```
scope          1  README.md not measured (over 10 files)
behaviour      2  row 2b adds a path where close accepts a tree changed after the last green verify (weakens a ref
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  new parallel runner tests/run_suite.py; the rest extends existing state.py close/weigh paths (de
coverage       0  2 of 2 code files have a test
W 5 → guarded   hints none · unknown scope, domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-29T20:06:10Z — /rr-build-all docs/sdlc/plans/faster-task-cycle.md
batch: on by Ivan Kakurov at 2026-10-29T20:06:10Z — /rr-build-all docs/sdlc/plans/faster-task-cycle.md

## Plan

files: tests/run_suite.py, tests/test_run_suite.py, tests/fixtures/run-suite/test_green.py, tests/fixtures/run-suite/test_fail.py, tests/fixtures/run-suite/test_error.py, tests/fixtures/run-suite/test_import_error.py, tests/fixtures/run-suite/test_crash.py, tests/fixtures/run-suite/test_hang.py, tests/fixtures/run-suite/test_unexpected_success.py, tests/fixtures/run-suite/test_skip.py, tests/fixtures/run-suite/test_serial.py, README.md, CONTRIBUTING.md, skills/rr-review/SKILL.md, skills/rr-build-all/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-build/SKILL.md, skills/ai-task/state.py, skills/ai-task/sensors.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_skills_surface.py, .ai/project/known-risks.md, agents/ai-reviewer.md.tmpl, tests/test_weight.py, docs/weight.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/82138d05-b6a9-4724-86b1-fc58625c36dc/scratchpad/review-1.md, docs/sdlc/specs/faster-task-cycle.md
tests: tests/test_run_suite.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_ai_status_root.py, tests/test_skills_surface.py, tests/test_codex_agent_render.py, tests/test_shared_prompts_model_free.py, tests/test_instruction_budget.py, tests/test_weight.py
- s1 · tests/run_suite.py, tests/test_run_suite.py, tests/fixtures/run-suite/test_green.py, tests/fixtures/run-suite/test_fail.py, tests/fixtures/run-suite/test_error.py, tests/fixtures/run-suite/test_import_error.py, tests/fixtures/run-suite/test_crash.py, tests/fixtures/run-suite/test_hang.py, tests/fixtures/run-suite/test_unexpected_success.py, tests/fixtures/run-suite/test_skip.py, tests/fixtures/run-suite/test_serial.py, README.md, CONTRIBUTING.md · tests/test_run_suite.py · done
- s2 · skills/rr-review/SKILL.md, skills/rr-build-all/SKILL.md, skills/rr-ship/SKILL.md, skills/ai-task/state.py, skills/ai-task/sensors.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_skills_surface.py, .ai/project/known-risks.md · tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_ai_status_root.py, tests/test_skills_surface.py · done
- s3 · agents/ai-reviewer.md.tmpl, skills/rr-review/SKILL.md, tests/test_skills_surface.py · tests/test_codex_agent_render.py, tests/test_shared_prompts_model_free.py, tests/test_skills_surface.py, tests/test_instruction_budget.py · done · after s2
- s4 · skills/ai-task/state.py, tests/test_weight.py, tests/test_ai_task_state.py, docs/weight.md · tests/test_weight.py, tests/test_ai_task_state.py · done · after s2
- s5 · skills/rr-build/SKILL.md, skills/rr-review/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-build-all/SKILL.md, tests/test_skills_surface.py · tests/test_instruction_budget.py, tests/test_skills_surface.py · done · after s2, s3, s4
amended 2026-10-29T20:38:35Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/82138d05-b6a9-4724-86b1-fc58625c36dc/scratchpad/review-1.md — the review report is recorded from a file: the Bash guard refuses a long state.py heredoc
amended 2026-10-29T20:39:58Z: +docs/sdlc/specs/faster-task-cycle.md — review H1/I2: the G1/G2 proposal in the spec's Interfaces lacks ai/** in documents.except and test_project_update/test_shared_tree in doc_tests, and lists the e2e-only test_end_to_end

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-29-2006-faster-task-cycle for implementation? (gate: human_approval)
asked: 2026-10-29T20:49:47Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via terminal at 2026-10-29T20:50:50Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 150f71e3f | .ai/state/logs/T-2026-10-29-2006-faster-task-cycle/suite-1.log | no |
| 2 | e2e | 0 | 150f71e3f | .ai/state/logs/T-2026-10-29-2006-faster-task-cycle/e2e-2.log | no |
| 3 | suite | 0 | 2d091b623 | .ai/state/logs/T-2026-10-29-2006-faster-task-cycle/suite-3.log | no |
| 4 | e2e | 0 | 2d091b623 | .ai/state/logs/T-2026-10-29-2006-faster-task-cycle/e2e-4.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS

- [HIGH] H1 With the spec's proposed `documents` table and `doc_tests` (G1/G2), the plugin's shipped `ai/**` tree counts as documents: the hard floor `NEVER_DOCUMENTS` is only `.ai/policies/**` (`skills/ai-task/state.py:3661`), the proposed `except` list has no `ai/**` (spec Interfaces, `docs/sdlc/specs/faster-task-cycle.md:275-276`), and the test that pins `ai/**` is not in the proposed `doc_tests`.  in_scope: yes
  why it matters: I ran `is_document` with the proposed table: True for `ai/policies/coding.md`, `ai/agents/reviewer.md`, `ai/workflows/feature.md`, `.ai/rules/*.md`. Each is hash-pinned by `tests/test_project_update.py:773-795` (`test_history_covers_every_template`: "else run tools/build-template-history.py"). After G1/G2, an edit to a shared binding policy after a green suite passes close's fact (a) on a green `doc_tests` run while the full suite is red — a concrete false green, not the general drift of concern 4. And `weigh` scores the same edit (a change to policies every user project reads) behaviour/domain/novelty 0 → light, against C6 and `skills/CLAUDE.md`.
  suggested direction: add `ai/**` to the floor or the proposed `except` (and decide `.ai/rules/**`); add `tests/test_project_update.py` (and `tests/test_shared_tree.py`) to the proposed `doc_tests`.

- [MEDIUM] M1 Plan row 2's step "`doc_tests` confirmation" (`docs/sdlc/plans/faster-task-cycle.md:89`) — run the grep, "the list goes into the task report under this step for G1" — was not done or not recorded: `task.md` and `events.jsonl` carry no such list.  in_scope: yes
  why it matters: G1 inherits only the spec's proposal, which already misses at least `test_project_update.py` (H1); the plan's own grep (`ROOT\b|os\.walk|…`) would have surfaced it.
  suggested direction: run the row-2 grep and record the confirmed list in the task record before close.

- [MEDIUM] M2 `weigh` re-applies the goal's keyword only when behaviour is still UNKNOWN after the keyword-stripped compute (`skills/ai-task/state.py:3699-3704`). When compute set behaviour otherwise, the keyword is lost, contrary to R12 ("a goal keyword still gives behaviour 1").  in_scope: yes
  why it matters: measured — goal "document the workflow transition", only a new `docs/new.md`: `weigh` behaviour 0 ("every declared file is new"), plain compute 1. Same goal with a behaviour hint on `docs/flow.md`: `weigh` 1 ("hint +1"), compute 2 (keyword + hint). Both under-weight. Neither case is in `test_weight.py` `TestDocumentsOnly` (keyword and hint are only tested separately on an existing file).
  suggested direction: strip only file-text matches (or apply the goal keyword before hints and the new-file rule), and add the two combined cases.

- [MEDIUM] M3 The new rr-ship row keys on `2 verify required` + "only documents changed since run …" (`skills/rr-ship/SKILL.md:38`), but close prints that text under `review required`. Probed: light → `state.py: review required (light mode) — a review, because only documents changed since run 1 …`; guarded reviewed → `review required (guarded mode) — a fresh 'verify --scope all' or a review of this tree, because only documents changed …`.  in_scope: yes
  why it matters: an agent following the table matches the `2 review required → /rr-review` row and buys a full review — the opposite of the saving; no test pins the prefix the row relies on.
  suggested direction: key the row on `review required … only documents changed since run` (or make close report the documents refusal as a `verify` kind), and pin the prefix in a test.

- [LOW] L1 D2 selects G as the last full-suite run with an exit and a tree (`state.py:3722`): a red full-suite run after G whose tree moved during the run (tree None), or with exit None on another tree, is ignored.  in_scope: yes
  why it matters: that red is evidence that the edits since G broke something; the rule then rests on `doc_tests` alone. Matches the spec's D2 wording but is weaker than "no red since G".
  suggested direction: off when any full-suite run after G is red, whatever its tree.

- [LOW] L2 The MEDIUM/LOW → `memory risk add` rule is attached only to the `pass_with_findings` bullet (`skills/rr-review/SKILL.md:84-93`, `skills/rr-build-all/SKILL.md:147-150`).  in_scope: yes
  why it matters: a `pass` verdict can carry in-scope MEDIUM/LOW findings and its `review … && close` chain closes without registering them (R8 short). Under `pass_with_findings` the text doesn't say to add the risks before the `--after-fix` run; a `known-risks.md` edit after it moves the tree, so `review --closes` refuses ("needs a full suite") and buys another suite run.
  suggested direction: one sentence: register MEDIUM/LOW risks first, then the after-fix run or the pass chain.

- [LOW] L3 `cmd_start` hands `weigh` only concrete files (`state.py:3484`): `--files README.md,src/**` satisfies P and weighs light although the task may edit code under the glob.  in_scope: yes
  why it matters: the task runs light until the first `verify`/`close` re-score raises it once a code path is in the diff; the end mode is right, the intermediate one is not.
  suggested direction: P fails when any task file is a glob not itself under a document glob.

- [LOW] L4 rr-review §3 says to record the verdict with `review --verdict <verdict>`, and §4 "pass" now says "the record and the close are one call" (`skills/rr-review/SKILL.md:84-86`); read in order, they ask for the verdict to be recorded twice.  in_scope: yes
  why it matters: a duplicate review pass in the record, review rounds spent.
  suggested direction: §3 says that for `pass` the record is §4's chain.

- [INFO] I1 Runner orphans: `sensors.run_command`'s timeout kills the runner with SIGKILL (`subprocess.run(timeout=…)`); the children run in their own sessions (`start_new_session=True`) and survive with no per-file timeout left. Also a tiny race where a child spawned between `Popen` and `children.add` escapes `kill_all` on SIGTERM; SIGHUP not handled.  in_scope: yes
  why it matters: low — needs a run past 1800 s (few cores, or piled-up 600 s timeouts); lingering processes, not a false green (exit None).
  suggested direction: optional parent-death check in the child (poll the parent pid), or note it in concern 6.

- [INFO] I2 The proposed `doc_tests` includes `tests/test_end_to_end.py`, every class `skipUnless(AI_E2E)` — under step scope it passes having run nothing. Guarded/full cover it through the separate "e2e on this tree" requirement; light does not.  in_scope: yes
  suggested direction: drop it from `doc_tests` (leave it to e2e) or say so in G1's text.

- [INFO] I3 Row 3's reviewer bound replaces "Verify by execution…" and forbids scratch scripts and timing loops (`agents/ai-reviewer.md.tmpl:50-53`). This repository's recurring blocker class — a regex's running time (`CLAUDE.md`, "Things Claude Code gets wrong") — can then no longer be confirmed by the reviewer, only by the manager's probe (`ai/policies/review-economy.md` §1). Accepted by the spec (R11).  in_scope: yes
  suggested direction: allow one timed probe for regex/performance claims, or state in rr-review §2 that the manager runs it.

- [INFO] I4 `read_commands` does not strip a trailing comment (pre-existing): `doc_tests: none  # …` reads as switched on; the rule then refuses with an odd command (`--files "none,#,…"`), not a false green.  in_scope: yes
  suggested direction: compare against the first token, or document that the line takes no comment.

## EXAMINED AND CLEAN
- Inherited, not re-derived: your D1–D5 and `weigh` P-predicate probes, green suite run 1 (974 tests) and e2e run 2, the known risks (`TestGateFastPath` under default jobs, runner not yet `verify_command`, exit 2 as a bite).
- Q1 false green through `close`: `diff_files` uses `--no-renames` (rename = D+A; deletion keeps its path; both fail D4 — `test_rename_py_to_md_refuses` holds); symlink — git tracks the link path, an edit through the link shows the target's path, a code target fails D4; a path matching both `documents.globs` and `code_globs`/`test_globs` is not a document; extra `--files` beyond `doc_tests` is a superset, harmless; the command is always `step_test_command` expanded; a tree-moved step run has tree None and never matches the current tree; a step run under Codex counts as green, D2 stricter than R19 on G's tree; snapshot excludes `.ai/state`, `.ai/reports`, `.ai/memory` — exactly as fact (a) always has; `review --closes` still needs a full suite and e2e on this tree is still owed in guarded/full (confirmed with a probe); `review --verdict pass` with an in-scope HIGH dies non-zero so the `&& close` chain does not run.
- Q2 `weigh` vs `compute` without the key: `is_document` False everywhere → `compute` called with the original arguments; `as_dict` unchanged; `documents_only` reaches JSON/state only when not None; `mode_for` matches compute's mode rule (same defaults, `min_w`); the `inside` check only ever falls back to plain `compute`.
- Q3 `rescore_v7`: the raise iterates every diff path, deletions included; `rescore_weight` works on a copy of the axes so `was` is pre-raise; `higher_mode` keeps a raised mode after the non-document is reverted; close re-scores before `two_facts`.
- Q4 `tests/run_suite.py`: missing/garbled/foreign result files red; exit≠0 after a green result red; timeout (killpg on the group) and SIGTERM/SIGINT red; a default serial id matching nothing exits 2; a broken import stays red through the parallel phase; `--collect` and the run share the loader call and `tests/` has no `__init__.py` packages, so `listdir` == `discover`; `summarize` counts lost files as errors.
- `status --json` dying on a broken `weight.json`: probed — pre-existing (it dies on the here-branch too), not a regression.
- `TESTING_FIELDS`: no other consumers that would change for user projects.
- Not reached (budget): a per-line review of the `test_skills_surface.py` and `test_instruction_budget.py` assertions (inherited green).

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the plan rows 1–5 files. One plan step was not carried out: row 2's `doc_tests` confirmation (M1). No refactoring mixed in. H1 and M1 concern the configuration this task hands to the human's G1/G2 — they activate only after G1/G2, but they decide whether the documents rule is safe in this repository.
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +100 −0 | Edit |
| CONTRIBUTING.md | +5 −1 | Edit |
| README.md | +3 −2 | Edit |
| agents/ai-reviewer.md.tmpl | +5 −3 | Edit |
| docs/sdlc/specs/faster-task-cycle.md | +7 −2 | Edit |
| docs/weight.md | +7 −0 | Edit |
| skills/ai-task/sensors.py | +1 −1 | Edit |
| skills/ai-task/state.py | +109 −4 | Edit |
| skills/rr-build-all/SKILL.md | +8 −4 | Edit |
| skills/rr-build/SKILL.md | +1 −1 | Edit |
| skills/rr-review/SKILL.md | +10 −5 | Edit |
| skills/rr-ship/SKILL.md | +2 −1 | Edit |
| tests/fixtures/run-suite/test_crash.py | +29 −0 | New |
| tests/fixtures/run-suite/test_error.py | +29 −0 | New |
| tests/fixtures/run-suite/test_fail.py | +29 −0 | New |
| tests/fixtures/run-suite/test_green.py | +35 −0 | New |
| tests/fixtures/run-suite/test_hang.py | +31 −0 | New |
| tests/fixtures/run-suite/test_import_error.py | +16 −0 | New |
| tests/fixtures/run-suite/test_serial.py | +16 −0 | New |
| tests/fixtures/run-suite/test_skip.py | +29 −0 | New |
| tests/fixtures/run-suite/test_unexpected_success.py | +30 −0 | New |
| tests/run_suite.py | +396 −0 | New |
| tests/test_ai_task_sensors.py | +4 −0 | Edit |
| tests/test_ai_task_state.py | +320 −0 | Edit |
| tests/test_run_suite.py | +272 −0 | New |
| tests/test_skills_surface.py | +53 −0 | Edit |
| tests/test_weight.py | +138 −0 | Edit |

+1685 −24 lines, 27 files

## Verdict

close: closed
facts: (a) green — suite green on 2d091b623 (run 3) · (b) green — 27 changed files, all in the task's files
gate: requested G1 at 2026-10-29T20:49:47Z; approved by vanssa at 2026-10-29T20:50:50Z via terminal
confirm: none
handoffs: 9 · suite runs: 2 · review passes: 1
