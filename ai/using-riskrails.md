# Using riskrails

One page: which command when, the three modes, the three nevers. The skills hold
the steps; `policies/` holds the rules; this says which to open.

## Which command when

| You want to | Run |
|---|---|
| set up `.ai/` in a project, or bring it up to the installed plugin | `/rr-setup`, `/rr-setup --update` |
| move another AI tool's files into this layout | `/rr-setup --adopt` |
| score the repository against the twelve plays | `/rr-setup --audit` |
| turn an idea into intent, requirements and design | `/rr-spec <idea>` |
| plan a spec into tasks, or one task into a mode and a start | `/rr-plan <spec or task>` |
| do the work, or resume it | `/rr-build` (no task in flight: it runs `/rr-plan` first) |
| run a whole plan as one task — parallel implementers and fixers, tests and the review again until it passes | `/rr-build-all <plan>` |
| review the change | `/rr-review` — guarded and full, or when `close` asks |
| close the task, get the human's approval | `/rr-ship` |
| see where the task stands, or what it cost | `/rr-status`, `/rr-status --cost` |

The old names (`/ai-task`, `/ai-init`, `/sdlc-spec` …) stay one version as aliases.

## Three modes

`state.py weight` scores six axes 0–2 — scope, behaviour, reversibility, domain,
novelty, coverage — and the sum W picks the mode. The table and its thresholds
are `policies/weight.json`; `policies/weight.md` mirrors it. Reversibility or
domain at 2 is full whatever W is.

- **light** — plan inline, edit, `verify --scope all`, `close`. No review unless
  one of the two facts is red; no human stop.
- **guarded** — the plan in plan mode, which the human accepts; one review on
  BALANCED; e2e runs.
- **full** — a written plan the human accepts; one review on STRONG (security
  focus when domain is 2); `close` asks the human to approve the tree in their
  own terminal. Full and irreversible adds `approve --confirm` naming the
  operation.

The mode only rises during a task (`verify` and `close` re-score reversibility
and domain from the diff); lowering it is the human's.

## Batch — one task for a whole plan

`/rr-build-all docs/sdlc/plans/<slug>.md` runs every row of a programme plan as
one task: the ready rows go to parallel implementers on BALANCED (`after`
serializes the dependent ones), the suite runs once, every failure is fixed by
parallel fixers as one batch, one review at the mode's tier, its findings fixed
as one batch, then tests and the review again until it passes. Its budgets are
`weight.json` `batch.*`: three failed review passes (`batch.review_rounds_max`)
and eight suite runs stop at the human — `REVIEW_BUDGET` and `SUITE_BUDGET`, as
always. The mode, the guard, the two facts and the gate are unchanged.
`batch.default` makes it the project's default; `state.py batch off --by …
--why …` returns a task to the standard loop (anyone); `batch on` mid-task is
the human's, from their own terminal.

## The two facts

`close` measures, never asks: (a) a green whole-suite `verify` on the tree as it
is now; (b) every changed file inside the task's files. Green and green in light
mode closes without a review.

## Three nevers

1. **Never past the guard.** An edit outside the task's files is refused —
   answer `SCOPE_CHANGE_REQUIRED` and widen the task with
   `state.py start --amend --files "+a" --why "…"`. A refusal is not a hint to
   reword.
2. **Never the human's decision.** No agent approves, lowers a mode, runs past
   a budget (`SUITE_BUDGET`, `REVIEW_BUDGET`), answers a question for the human,
   or passes `--confirm-delete`. Print the command; the human runs it.
3. **Never commit, push, merge or deploy.** The task ends at `close`; the
   commit is the human's.

Problems found outside the task go into `project/known-risks.md`, not into the
diff. Production behaviour is the source of truth.
