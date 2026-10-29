---
name: rr-build-all
description: Run a whole programme plan as one task in a repository that has .ai/ — every row of docs/sdlc/plans/<slug>.md becomes a step with its files, tests and dependencies; the ready steps go to parallel implementer subagents on the BALANCED tier, serialized where one depends on another; after the last step the suite runs once to the end, every failure is recorded and fixed by parallel fixers as one batch, then one review at the mode's tier, its findings fixed by parallel fixers as one batch, then tests and the review again until it passes; the pass past the batch budget (three failed reviews) is the human's. Use on "/rr-build-all", "run the whole plan", "all points in one task", "sdlc-lite", "batch build".
argument-hint: [<path to docs/sdlc/plans/<slug>.md>] | --resume
---

# /rr-build-all $ARGUMENTS

One task for the whole plan — the loop a developer otherwise runs by hand: implement every
row, test once, fix everything, review, fix everything, again, until the review passes. The
mode (light, guarded, full) is still the weight's; batch only changes who implements, how
failures are fixed, and how many rounds run before the human. Resolve the install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-build-all" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

Shared files resolve through `"$AI_HOME/riskrails/ai-path" <path>`. Read `policies/safety.md`
and `using-riskrails.md` once per session. Every rule of `/rr-build` holds here: nothing outside
the task's files, no commit, a refusal names the way out and is never reworded around.

## 1. Resume or start

```bash
$STATE handoff --print
```

- **A task in flight whose handoff says `Batch: on`:** continue at its stage — §3 while
  `steps --ready` prints a step, §4 after the last `step-done`, §5 after a green verify.
- **A task in flight without that line:** it runs the standard way — say so and hand over to
  `/rr-build`. Only the human turns the loop on mid-task (`batch on`, §Switching).
- **No task in flight:** §2.

## 2. The plan → one task

`$ARGUMENTS` is a programme plan (default: the newest `docs/sdlc/plans/*.md`). Its spec's
**Flagged concerns** are resolved or accepted, as `/rr-plan` demands; a plan with an open
blocking question is not started.

1. **Rows → steps.** Every row of **Order of work** that an agent does becomes one step
   `{"id", "files", "tests", "after"}`: the row's files, the tests it names, and in `after` the
   rows it depends on — its *Consumes* line, a stated dependency, or an earlier row it builds
   on. A refactoring row stays its own task (C3): leave it out and say so. A human row (G1, …)
   is not a step: every row after it names in `after` every step before it, so nothing past
   the human row is ready until the rows before it are done — and its question (3.) answered.
2. **Weigh and start** — `/rr-plan`'s "A task" section, on the union of the steps' files, then:

   ```bash
   $STATE start --goal "<the plan's title>" --workflow feature --files "<every file of every step>" \
     --tests "<every test>" [--declare …] --plan-file /path/steps.json \
     --batch --by "<the human's name>" --why "/rr-build-all docs/sdlc/plans/<slug>.md" \
     [--mode <higher> --by "<name>"]
   ```

   An `after` id must exist and form no cycle; two steps that name one file are ordered by
   `start` itself (`ordered: s4 after s1 (shares …)`), so two implementers never hold one file.
   In full mode the written plan is the programme plan the human already accepted. With
   `batch.default` true in `.ai/policies/weight.json` the flag is implied; `--no-batch` opts out.
3. **A human row** becomes a question the moment every step before it is done — asked
   **before** the next wave is dispatched:
   `$STATE ask "G1 is yours: <what>" --option "A: done" --option "B: not yet" --recommend A`,
   then **stop**. Never dispatch while a question is pending (`step-done` and `close` exit 4;
   `steps --ready` still answers); `/rr-build-all --resume` goes on once the human answered.

## 3. Implement, by waves

```bash
$STATE steps --ready               # the next wave: the steps whose dependencies are done, one id per line
$STATE steps --json                # batch_policy.tier and .parallel: the implementers' tier, how many at once
$STATE profile --tier <that tier>  # the tier's model in this runtime (BALANCED as shipped)
```

**Resuming mid-wave** (after a compaction or a stop): before dispatching, compare
`git status --short` with each ready step's files. A ready step whose files already changed
was dispatched before and never recorded — do not send it again blind: brief its implementer
with that partial diff to finish, or `step-done` it if its tests pass.

Dispatch one subagent per ready step, at most `batch.parallel` (shipped 3) at once — under
Claude Code a `general-purpose` agent with `model:` set to that tier's model; under Codex a
spawn with no agent named, on that model. Its brief is the implementer contract,
`agents/implementer.md` in the shared tree, filled in:

- **Goal** — the row's text from the plan. **Allowed files** — the step's files, nothing else.
  **Forbidden files** — every other step's files, "another implementer holds them".
  **Required behaviour / behaviour that must not change** — from the row and the spec.
  **Required tests** — the step's tests.
- Its own tests, run directly: `step_test_command` from `.ai/policies/testing.md` with the
  step's tests in place of `{files}`. **A subagent never calls `state.py`** — one state file,
  one writer, this session.
- It returns `## RESULT`, or `## SCOPE_CHANGE_REQUIRED`, or `## QUESTIONS_NEEDED`.

After the wave, in this session:

- `RESULT` → `$STATE step-done <id>` for each step. Exit 6 names a file outside the task:
  `$STATE start --amend --files "+<path>" --why "…"`, then `step-done` again.
- `SCOPE_CHANGE_REQUIRED` → amend as above and send the same step again. A file that belongs
  to another change goes into `.ai/project/known-risks.md`, not into the task.
- `QUESTIONS_NEEDED` → `$STATE ask --batch /path/questions.json`, show the questions, **stop**;
  the human answers, and `/rr-build-all --resume` goes on from the handoff.

Then `steps --ready` again. Nothing ready and nothing pending: §4. Keep this session small:
read `## RESULT` blocks, never a subagent's diff; `git status --short` is the only view of the
tree you need between waves.

## 4. Tests once, failures fixed as one parallel batch

After the last wave, `$STATE step-done <id> && $STATE verify --scope all`:

```bash
$STATE verify --scope all
$STATE verify --scope all --e2e not-applicable "<why the change reaches no e2e flow>"
```

Green: §5. **Red:** a FAST `log-reader` reads the log by path and returns every failure
classified — new regression, existing failure, environment, unknown (`testing.md`, "Reading a
failure") — each with `file:line`. Then:

- an existing failure → one entry in `.ai/project/known-risks.md`; an environment failure →
  one more run, no code change;
- the new regressions, grouped by the file they point at → one fixer subagent per group, in
  parallel, at most `batch.parallel`, on the batch tier, briefed with the failures' excerpts
  and the files it may touch (that group's files, inside the task's). Fix the code, never the
  test; report `files_changed` and what stayed unfixed;
- one run: `$STATE verify --scope all --after-fix "<n> regressions: <one line each>"`.

Red again → the same once more. Exit 6 `SUITE_BUDGET` — past `batch.max_suite_runs`
(shipped 8) — is the human's run: the pick in the dialog, or the command it prints, in their
own terminal. **Stop.**

## 5. Review, findings fixed as one parallel batch, again until it passes

One `ai-reviewer` at the mode's tier, briefed as `/rr-review` §2 says: the whole diff since the
task's base, the task's files, the tests, the last verify log; unbounded "look for" in full
mode, the security focus when the domain axis is 2. Record it verbatim:

```bash
$STATE review --verdict <pass|pass_with_findings|blockers_open> --tier <BALANCED|STRONG> \
  [--focus security] --report - <<'EOF'
<the reviewer's FINDINGS and VERDICT, unchanged>
EOF
```

- **pass** → §6.
- **pass_with_findings** → the in-scope HIGHs, grouped by file, one fixer per group in
  parallel; `$STATE verify --scope all --after-fix "H1,H2: …"`; `$STATE review --closes "H1,H2"`
  → §6. Each MEDIUM and LOW is one `$STATE memory risk add`, not a fix; only a BLOCKER, a HIGH
  or a regression buys an `--after-fix` run.
- **blockers_open** → every in-scope BLOCKER and HIGH, grouped by file, one fixer per group in
  parallel; `$STATE verify --scope all --after-fix "B1,H1: …"` (red: §4's batch); then
  **§5 again, a full pass** — a fix batch across many files is a new change, not a scoped one.

Exit 6 `REVIEW_BUDGET` after `batch.review_rounds_max` passes (shipped 3 — three failed
reviews) — the next verdict is the human's: the pick in the dialog, or the command it prints,
in their own terminal. Show the open findings and **stop**. A `verify` past its budget inside
this loop is `SUITE_BUDGET`, handled the same way.

## 6. Ship

`/rr-ship` — `close` measures the two facts and, in full mode, asks the human to approve,
exactly as for any task; for a documents-only change since the green suite it is
`$STATE verify --scope step --files "<doc_tests>" && $STATE verify --scope e2e && $STATE close`. Suggest `/clear` after it.

## Switching

- **To the standard loop ("full" from here):** `$STATE batch off --by "<name>" --why "<why>"`.
  The standard budgets apply from now, counting what was spent — with two passes behind you,
  the next verdict is already the human's. The session implements the remaining steps itself;
  continue with `/rr-build`, `/rr-review`, `/rr-ship`. Anyone may do this: it raises the rigor.
- **To batch, mid-task:** lowers the rigor — the human's, in their own terminal:
  `python3 <AI_HOME>/skills/ai-task/state.py --root <project> batch on --by "<name>"`. Never
  from a tool call; the refusal (`APPROVAL_REFUSED`) prints that command.
- **The project's default:** `batch.default` in `.ai/policies/weight.json`, beside
  `batch.review_rounds_max`, `batch.max_suite_runs`, `batch.parallel` and `batch.tier`
  (`/rr-setup --update` adds the section). A policy is the human's and is frozen during a task.

## Rules

- The mode is the weight's and only rises; the scope guard, the two facts, the gate and the
  three nevers are untouched by batch.
- Three or more parallel agents run at BALANCED, never above — `start` refuses `batch.tier`
  above it when `batch.parallel` is three or more; one reviewer per pass, at the mode's tier;
  the session writes every conclusion (`model-routing.md`).
- One writer of the state: a subagent never calls `state.py`; this session records every step,
  run and verdict.
- Failures and findings are fixed as batches, never one at a time; a test is never edited to
  make it pass; what is outside the task is written down, not fixed.
- No commit, push, merge or deploy. The task ends at `/rr-ship`; approval is the human's.
