# Intent: Batch build — one task for a whole plan, parallel implementers and fixers, a review loop that stops at the human after three failed passes

<!-- Stage 1 of the SDLC flow. Say WHAT and WHY. Leave HOW to the spec. -->

Written 2026-10-28 from the developer's two messages of that evening (verbatim below), not from a
`state.py ask --topic` brainstorm: the request is concrete enough to fill every part, and the developer
asked for the work to be done in a worktree and tested in isolation. The example it generalises is
T-2026-10-28-011, where the developer ran the whole programme plan `compact-project-memory` (M1–M12) as
one full-mode task with one review instead of twelve tasks.

## The developer's words

> Виж как съм изпълнил последния план - всички точки в една задача, може ли да направиш скил с който това
> да може да се прави винаги. Не да се правят 20 малки задачи със тежките тестове и т.н. а една голяма която
> да се изпълни примерно - rr-build-all да прави всичко това. Като накрая пуска тестове като само запсива
> грешките, след това ги оправя на един път. След тестовете и идва ревюто което пак записва находките и след
> това ги оправя на един път, след като е оправило находките пуска отново цикъла за тестове и след това пак
> ревю. Този цилъл се поватаря докато ревюто мине. При три падания на ревюто се иска човешка намеса.
> Корекецията по тестовете и ревютата може да се правят от суб агенти на sonnet 5.5 или еквивалента му за
> codex. Това трябва да е нещо като sdlc-lite или и аз не занм как да го кръстя но е важно да го има като
> опция и да може да се настройва на ниво прокет кой мод да е поподразбиране. Също така да е въжможно по
> време на изпълението на интента да се сменя на havi/full или коректното име.
>
> Това трябва да стане в worktree и ако е необходимо да се тества в изолирана среда.
>
> Имам предвид паралено да се орпавят падналите тестове и ревюта. Също така ако може да се пусакт паралено и
> субагенти който да реализират точките по задачите като се изкчават ако имат зависимости

In English: run a whole plan as one task, not twenty small tasks each with the heavy tests and reviews;
at the end run the tests once, record the failures, fix them in one go; then the review, record the
findings, fix them in one go, then tests again and the review again; repeat until the review passes;
after three failed reviews ask a human; the fixes may be done by subagents on the BALANCED tier (Sonnet
5.5 or its Codex equivalent); call it something like "sdlc-lite", make it an option with a project-level
default, and make it possible to switch to the heavy ("full") way while a plan is being executed. Do it in
a worktree, test in isolation. The fixes of tests and findings run in parallel, and the plan's points are
implemented by parallel subagents, serialized where they depend on each other.

## Problem

- A programme plan of N rows costs N tasks today, each with its own plan, suite run, e2e run, review and
  (in full mode) approval — the per-task ceremony dominates when the rows are small and related.
- The developer already works around it by hand (T-2026-10-28-011: twelve rows, one task), which the
  skills neither describe nor support: the steps run one after another in the session, the review budget
  is two passes, the suite budget two runs, and nothing says who fixes what in parallel.
- The budgets were sized for one row. A whole-plan task needs a loop — tests, fixes, review, fixes, again —
  with a stop that is still the human's.

## Outcome

- **O1** `/rr-build-all <plan>` runs every row of a programme plan as the steps of one task and ends at
  `/rr-ship` like any task; a plan of twelve rows is one record, one suite run per round, one review per
  round.
- **O2** The rows run as parallel subagents on the BALANCED tier where they are independent, and in order
  where one depends on another; `state.py` says which rows are ready.
- **O3** Failures of the suite and findings of the review are recorded first, then fixed as one batch by
  parallel subagents, then one verify; a review follows every fixed batch.
- **O4** The loop stops at the human after three failed review passes (and past the suite budget), through
  the same `REVIEW_BUDGET` / `SUITE_BUDGET` stop the pipeline already has.
- **O5** A project sets whether this is the default (`weight.json`), and a task can be started with or
  without it.
- **O6** During a task the developer can switch it off (back to the standard, "full" way) with one command;
  switching it on mid-task is the human's.

## Affected users and systems

- The developer running plans in this repository and in user projects, in Claude Code and in Codex.
- `state.py` (start, steps, verify, review, step-done, status, handoff, task.md), `weight.json` and its
  mirror, the skills `/rr-plan`, `/rr-build`, `/rr-review`, the new `/rr-build-all`, the shared tree
  (`using-riskrails.md`), `docs/weight.md`, `README.md`, the template history.

## Constraints and non-goals

- The mode (light/guarded/full) stays the weight's and only rises; the scope guard, the two facts, the gate
  and the three nevers stay. Batch is a loop shape, not a fourth rigor.
- No new agent file (redesign 2.4 removed `ai-implementer`); no model name in any skill (tiers only); no
  migration (a new table key merges on `/rr-setup --update`).
- This repository's own `.ai/policies/weight.json` is frozen during a task; it is updated by the human
  afterwards.
- Non-goals: a per-subagent scope guard; a cross-session scheduler; changing how a single-row task runs
  when batch is off.

### Decisions taken

- **Name.** The flag is `batch` (state, `weight.json` section, `state.py batch on|off`); the command is
  `/rr-build-all`; the prose may say "sdlc-lite" once. Not a mode, so no clash with `light`/`full`.
- **"Three failures → human"** is `batch.review_rounds_max: 3` and the existing `REVIEW_BUDGET` refusal.
- **A human row (G*) of a plan** becomes a question that blocks the next wave, not a step.
- **After `blockers_open`** the next review in batch is a full pass (the developer: "и след това пак ревю").
- **Fixers and implementers** run on `batch.tier` (BALANCED); the reviewer stays on the mode's tier.

## Open questions

none blocking.
