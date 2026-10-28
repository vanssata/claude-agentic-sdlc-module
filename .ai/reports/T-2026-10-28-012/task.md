# T-2026-10-28-012 — Batch build: one task for a whole plan, parallel implementers and fixers, a review loop that stops at the human after three failed passes — /rr-build-all, state.py steps and batch on|off, after on plan-file steps, the weight.json batch section

feature · full · started 2026-10-28T20:38:25Z · claude

## Weight

```
scope          2  skills/ai-init/templates/.ai/policies/weight.json referenced from 8 files
behaviour      2  a new budget table (batch.review_rounds_max 3, batch.max_suite_runs 8) lets a task run three rev
reversibility  0  git revert returns everything
domain         0  the plugin pipeline itself; no money, identity or personal data (declared)
novelty        1  a new policy section, a new skill and three state.py commands on existing mechanisms (plan-file 
coverage       0  2 of 2 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by agent per skills/CLAUDE.md at 2026-10-28T20:38:25Z — behaviour 2 starts full: the batch budgets and the switch change when the human is asked; the developer chose one task, one STRONG review, the gate

## Plan

files: skills/ai-init/templates/.ai/policies/weight.json, skills/ai-init/templates/.ai/policies/weight.md, skills/ai-task/weight.py, skills/ai-task/state.py, skills/rr-build-all/SKILL.md, skills/rr-build/SKILL.md, skills/rr-plan/SKILL.md, skills/rr-review/SKILL.md, ai/using-riskrails.md, docs/weight.md, README.md, skills/project-update/history/**, tests/test_weight.py, tests/test_ai_task_state.py, tests/test_skills_surface.py, docs/sdlc/intent/batch-build.md, docs/sdlc/specs/batch-build.md, docs/sdlc/plans/batch-build.md, .ai/project/known-risks.md, tests/test_project_update.py, ai/policies/review-economy.md, .ai/reports/T-2026-10-28-012/review-report.md
tests: tests/test_weight.py, tests/test_ai_task_state.py, tests/test_ai_status_root.py, tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_codex_agent_render.py, tests/test_project_update.py, tests/test_shared_prompts_model_free.py
- s1-policy · skills/ai-init/templates/.ai/policies/weight.json, skills/ai-init/templates/.ai/policies/weight.md, skills/ai-task/weight.py, tests/test_weight.py · tests/test_weight.py · done
- s2-state · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py, tests/test_ai_status_root.py, tests/test_weight.py · done
- s3-skill · skills/rr-build-all/SKILL.md, skills/rr-build/SKILL.md, skills/rr-plan/SKILL.md, skills/rr-review/SKILL.md, tests/test_skills_surface.py · tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_codex_agent_render.py · done
- s4-docs · ai/using-riskrails.md, docs/weight.md, README.md, skills/project-update/history/** · tests/test_project_update.py, tests/test_shared_prompts_model_free.py · done
amended 2026-10-28T21:00:01Z: +tests/test_project_update.py — test_oldest_project_is_brought_up_to_date pins the count of manual merges; with a third shipped weight.json in history the migrated table now has a closer base (the version before the batch section), so weight.json merges cleanly and the count is 1 (the state README), not 2
amended 2026-10-28T21:16:51Z: +ai/policies/review-economy.md — review H1: the binding review policy (review-economy.md §3 and the not-traded list) must name the batch exception, else a session reading it stops the batch loop after two passes
amended 2026-10-28T21:18:56Z: +.ai/reports/T-2026-10-28-012/review-report.md — the STRONG review's FINDINGS and VERDICT, verbatim, as the file 'review --report' reads (the guard refuses a report this long on stdin)

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-28-012 for implementation? (gate: human_approval)
asked: 2026-10-28T21:40:51Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]:

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 9453b9b99 | .ai/state/logs/T-2026-10-28-012/step-1.log | no |
| 2 | step | 0 | f2bba7602 | .ai/state/logs/T-2026-10-28-012/step-2.log | no |
| 3 | step | 0 | 8cd212d6c | .ai/state/logs/T-2026-10-28-012/step-3.log | no |
| 4 | step | 0 | bdc56a728 | .ai/state/logs/T-2026-10-28-012/step-4.log | no |
| 5 | step | 1 | 21cac9fcf | .ai/state/logs/T-2026-10-28-012/step-5.log | no |
| 6 | step | 1 | cc079c365 | .ai/state/logs/T-2026-10-28-012/step-6.log | no |
| 7 | step | 0 | 2bb5b667c | .ai/state/logs/T-2026-10-28-012/step-7.log | no |
| 8 | suite | 0 | f753e47d0 | .ai/state/logs/T-2026-10-28-012/suite-8.log | no |
| 9 | e2e | 0 | f753e47d0 | .ai/state/logs/T-2026-10-28-012/e2e-9.log | no |
| 10 | step | 0 | bea12abb2 | .ai/state/logs/T-2026-10-28-012/step-10.log | no |
| 11 | suite | 1 | b25143a64 | .ai/state/logs/T-2026-10-28-012/suite-11.log | no |
| 12 | step | 0 | b25143a64 | .ai/state/logs/T-2026-10-28-012/step-12.log | no |
| 13 | suite | 0 | b25143a64 | .ai/state/logs/T-2026-10-28-012/suite-13.log | no |
| 14 | e2e | 0 | b25143a64 | .ai/state/logs/T-2026-10-28-012/e2e-14.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass_with_findings

```
# Review — T-2026-10-28-012, pass 1, STRONG (claude-opus-5-5), full mode

## FINDINGS
- [HIGH] H1 The binding review policy still forbids a third review pass, and the change does not touch it. Location: `ai/policies/review-economy.md:90-94`, `:206-207`, against `skills/rr-build-all/SKILL.md:140-147` and `docs/sdlc/specs/batch-build.md` (Policy conformance, the review-economy bullet). review-economy.md ships to every project as `.ai/policies/review-economy.md`, and the instructions declare that directory binding. It says "A task gets **two passes** … at every tier … When both are spent, a third pass is not the next move: the human decides". Under "What this policy will not trade away" it says "Past the two passes of §3, a human — not a third pass — decides". The task's files do not include review-economy.md and the diff does not change it. Yet the spec claims conformance ("'two passes' becomes a per-task number read from the table"). A batch task, or every task when `batch.default` is true, now gets a third full STRONG pass without the human. That is exactly the behaviour-2 effect this task declares. Consequence: a session or reviewer reading the binding policy either stops the batch loop after two passes, or follows the skill against a binding rule. A user reading the policy is also told something false about when they are asked. The fix needs a SCOPE_CHANGE: add the batch exception to §3 and to the not-traded list, then run tools/build-template-history.py.
  in_scope: yes
- [MEDIUM] M1 Tasks without `--batch` and without `after` no longer behave byte-for-byte as before. Location: `skills/ai-task/state.py:3214` (order_shared_files runs for every start, `--steps` shorthand included) and `:4061`. I checked this by running both trees on a scratch project: `start --steps "s1:src/a.py;s2:src/a.py;s3:src/b.py"`, then `step-done s3`. HEAD prints no `ordered:` line, and step-done prints `step s3 done; next: s2`. The new tree prints `ordered: s2 after s1 (shares src/a.py)`, task.md gets `- s2 · src/a.py · no tests · pending · after s1`, and step-done prints `step s3 done; all steps done` while s1 is in_progress and s2 is pending. The docstring at :4059 ("the first pending one when no step has `after`, as before") assumes no `after`, but order_shared_files itself creates `after` on standard tasks. The test `test_steps_without_after_behave_as_before` only covers steps with disjoint files. Fix direction: apply the shared-file ordering only when batch is on, or keep the old step-done pick for non-batch tasks.
  in_scope: yes
- [MEDIUM] M2 step-done says "all steps done" while steps are still pending. Location: `skills/ai-task/state.py:4061-4067`. `following` is None whenever no *ready* pending step exists, and the print then says "all steps done". I checked this by running: a batch task with s1, s2 ready and s3 after s1; both edited in one wave; `step-done s2` before `step-done s1` printed `step s2 done; all steps done` with s3 pending. The skill records a wave's steps in any order (SKILL.md:89), so the session is told the plan is finished mid-plan and may jump to §4 verify. Fix direction: tell "nothing ready yet (n pending)" apart from "all steps done".
  in_scope: yes
- [MEDIUM] M3 A human row (G1) cannot hold back the rows after it. Location: `skills/rr-build-all/SKILL.md:43-47`, `:61-64`. A human row is not a step, so it cannot appear in `after`, and the skill only says "note which steps come after it". A row placed after G1 with no other dependency is ready in wave 1. Its implementer runs before G1 is even asked (G1 is asked only "when the steps before it are done"). step-done's exit 4 blocks only the *recording*, not the implementation. R1 ("so the rows after it wait") is not met. Fix direction: have the skill give every row after a human row an `after` naming every step before that row, or give the row a placeholder step.
  in_scope: yes
- [MEDIUM] M4 The shared-file ordering misses step tests and patterns, so two implementers can hold one file (your probe 4, confirmed and widened). Location: `skills/ai-task/state.py:3214-3224`. Only `files` are compared, by exact string. A step's `tests` are not compared, although task_files() puts them in the guard's scope (state.py:3140-3145) and the implementer contract says "Add the required tests in the same step". Two steps that both name `tests/test_x.py` under `tests` (this task's own s1 and s2 both name tests/test_weight.py) run in parallel and both edit it. Overlapping globs (`src/*.py` against `src/a.py`) and `./src/a.py` against `src/a.py` are not ordered either. This ordering is FC4's only mitigation. Fix direction: compare files + tests, and use weight.match() so patterns count as overlapping.
  in_scope: yes
- [MEDIUM] M5 In a wave, step-done diffs and the journal do not describe the steps. Location: `skills/ai-task/state.py:4050`, `:4061-4064`, and FC3 in the spec. I checked this by running: two parallel steps edited a.py and b.py; both step_done events recorded `files: 2`. A ready step recorded from `pending` measures from base_tree. The step that step-done starts next gets `tree_before` = the post-wave tree, so its own diff is near-empty, and its `step_started` event is journaled after the work was already done. The SCOPE_CHANGE_REQUIRED at :4053 also blames whichever step is recorded first for another step's out-of-task file. FC3 lists "`step-done`'s diff shows it" as the mitigation for one implementer editing another step's file; it does not, because the diff is cumulative and checked only against the task's union. Fix direction: drop that claim from FC3 and the docs, or record per-step paths (diff ∩ step files, plus the rest) in step_done.
  in_scope: yes
- [LOW] L1 Malformed batch values crash status and `handoff --print`, and silently stop the handoff file from updating (your probe 1, confirmed). Location: `skills/ai-task/state.py:3040-3048`, `:1723-1731`, `:3394-3397`. I checked this by running with `batch.review_rounds_max: "three"`: start succeeds and prints `review three passes`. `status` then exits 1 with a ValueError traceback, and so does `handoff --print`. write_handoff swallows the error, so `.ai/state/handoff.md` silently stops updating. `batch off` recovers the task. Also `"default": "false"` (a string) is truthy and turns batch on, and None raises TypeError. Fix direction: validate the section once in batch_policy() (ints ≥ 0, a bool, a known tier) and die naming the key.
  in_scope: yes
- [LOW] L2 start marks steps[0] in_progress whatever its `after` says (your probe 2, confirmed). Location: `skills/ai-task/state.py:3366-3367`. I checked this by running a plan where s1 is after s2: `steps` shows `s1 · in_progress · after s2 · waiting`, `--ready` prints only s2, and status says `current s1`. Fix direction: start the first ready step.
  in_scope: yes
- [LOW] L3 step-done does not check readiness (your probe 3, confirmed). Location: `skills/ai-task/state.py:4037-4058`. It accepts a step whose `after` are not done; ordering holds only by convention. Fix direction: print a note and put `unready: [...]` in the event data, not a refusal.
  in_scope: yes
- [LOW] L4 `batch on|off` and close overwrite next_action with the wrong text. Location: `skills/ai-task/state.py:4111` (cmd_batch → review_next_action) and `:3874`. I checked this by running a full task with the gate requested: next_action "the human approves in their own terminal, then 'state.py close' again" became "'state.py close'" after `batch off`, and the handoff says so too. This bypasses nothing (close still exits 4 on G1), but it misleads. close_owed's blockers_open text still says "one scoped re-review" in a batch task, contradicting review_next_action's full pass. Fix direction: leave next_action alone outside build/review, and make close_owed's text batch-aware.
  in_scope: yes
- [LOW] L5 batch_set records the wrong author when the project default turned batch on. Location: `skills/ai-task/state.py:3348-3349`. With `batch.default` true, `by` is `args.by or "weight.json batch.default"`. A start that carries `--mode full --by agent --why "<mode reason>"` (this very task's shape) journals `batch_set "on by agent"` with the mode override's why, although the policy turned it on. Fix direction: give the default its own author whenever `--batch` was not passed.
  in_scope: yes
- [LOW] L6 Nothing checks `batch.tier` against the fan-out rule, and the skill hardcodes the tier. Location: `skills/ai-task/state.py:3026`, `skills/rr-build-all/SKILL.md:70`, `:171`, `ai/policies/model-routing.md:88-92`. `tier` and `parallel` are taken as given; the test itself sets `tier STRONG, parallel 5`. model-routing.md says three or more parallel agents run at FAST or BALANCED, "always". The skill runs `profile --tier BALANCED` while its comment says "(weight.json batch.tier)", so a project's tier setting is either ignored or breaks the fan-out rule. Fix direction: refuse tiers above BALANCED when parallel ≥ 3, and have the skill read the tier from start's `batch:` line.
  in_scope: yes
- [LOW] L7 A cycle created by the shared-file ordering is refused with no explanation. Location: `skills/ai-task/state.py:3308-3310`. The ordering always puts the later row after the earlier one. A valid plan that lists a dependent row before its dependency, where the two share a file, is refused with "the steps' after form a cycle: x -> y -> x". The implied edge is never shown, because the `ordered:` lines print only after a successful start. Fix direction: name the implied edge in the refusal.
  in_scope: yes
- [LOW] L8 The skill does not say how to resume a half-finished wave. Location: `skills/rr-build-all/SKILL.md:31-33`, `:87-96`. Nothing records which steps were dispatched. After compaction or a stop in the middle of a wave, `steps --ready` lists steps whose implementers already edited the tree but were never recorded, and the skill re-dispatches them on top of their partial work. Fix direction: tell the session to check `git status` against each ready step's files before re-dispatching it.
  in_scope: yes
- [INFO] I1 The budget dialog texts changed for non-batch tasks. Location: `skills/ai-task/state.py:3598`, `:3733`. The SUITE_BUDGET and REVIEW_BUDGET questions now end with "(tests.max_suite_runs)" or "(review_rounds_max)" on standard tasks too. The die texts are unchanged. Harmless, but not byte-for-byte.
  in_scope: yes
- [INFO] I2 FC2 is wider than the spec says. Location: `skills/ai-task/state.py:3343-3349`, `skills/rr-build-all/SKILL.md:53`. `batch on` mid-task needs the human, but an agent can `close --abandon` and then `start --batch --by "<the human's name>"`, and the skill tells the agent to write the human's name. The journal then reads "on by <human>" (actor agent) for a choice the agent made. This was accepted as FC2; it is noted here because it makes the gate on `batch on` largely symbolic.
  in_scope: yes
- [INFO] I3 Spec and code differ on what "ready" means. Location: `docs/sdlc/specs/batch-build.md` R3, against `skills/ai-task/state.py:3253-3258`. R3 says `--ready` prints the *pending* steps; the code and the test also print in_progress steps. The code's choice is the one the loop needs; the spec text should follow it.
  in_scope: yes
- [INFO] I4 Your probe 5 is confirmed as working as designed. Location: `tests/test_project_update.py:681-684`, `skills/project-update/update.py:777-799`. three_way() drops history versions equal to the current shipped file (theirs). Before this change that left no candidate, so the base was MISSING and weight.json conflicted. With 7f3859… now in history, closest() has one base, the migrated table's only edit against it is the T0 example, and the batch key merges cleanly. The new count of 1 manual merge is correct and is not a weakened test. The comment's "closest" wording is slightly loose: it is "a base now exists", not a choice between two candidates. The using-riskrails.md hash 25d08… has no blob, which is correct (shared keys are hash-only).
  in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: inside
model: claude-opus-5-5 (Opus 5.5)
```

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on b25143a64 (run 13) · (b) green — 22 changed files, all in the task's files
gate: requested G1 at 2026-10-28T21:40:51Z; approved by - at - via -
confirm: none
handoffs: 5 · suite runs: 3 · review passes: 1
