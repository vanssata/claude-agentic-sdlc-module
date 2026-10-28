---
name: rr-build
description: Do the work of one task in a repository that has .ai/ — resume it from its handoff, or plan and start it through /rr-plan when none is in flight; edit inside the task's files under the scope guard (widened in place with `start --amend`), run each step's own tests, show a bugfix's test failing before the fix, run the verification command once to the end and fix every failure as one batch, and stop only on a real blocker. Hands over to /rr-review and /rr-ship by the task's mode. Use for any change in a repository with .ai/, on "/rr-build", "do it", "continue", "resume the task".
argument-hint: [what you want done] | --resume
---

# /rr-build $ARGUMENTS

You implement, in this session, and keep your own context small. The same
under Claude Code and Codex; resolve the install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-build" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

Shared policies resolve through `"$AI_HOME/riskrails/ai-path" <path>`: a
project file at the same path under `.ai/` wins. Read `policies/safety.md` and
`using-riskrails.md` once per session.

## 1. Resume or start

```bash
$STATE handoff --print
```

- **No task in flight:** run `/rr-plan $ARGUMENTS` — it weighs the task, picks
  the mode, shapes the plan and calls `start`. Come back here after it. (The
  message may point at the old `init` command: it starts an old-surface task.)
- **`$STATE status` prints `old surface`:** the task was started before this
  plugin; the new commands refuse it and this skill cannot finish it. Say so and
  let the human decide whether to finish it with the version that started it,
  or to drop it.
- **A task in flight:** the handoff is the cheapest way back in — mode, step,
  files, decisions, pending questions, the resume point, in at most thirty lines.
  Trust it over a compaction summary; it is rendered from the state. If
  `$ARGUMENTS` asks for something else, say what is in flight and ask whether to
  finish it, or drop it with `$STATE close --abandon`. Never discard it silently.
  A handoff line `Batch: on` means the task runs the loop of `/rr-build-all` —
  parallel implementers and fixers, its own budgets — continue there.
- **`Handed to <the other runtime>`:** every state change exits 7 until that
  runtime resumes it. Say where to resume; take it back with
  `$STATE handoff --to <this runtime>` only when asked. `Handed to <this
  runtime>`: resume at its resume point.

`$STATE status` prints the same in twenty lines whenever you need it.

## 2. Edit, inside the task

Before the first edit, recall what the record already holds about the task's
files — open risks, residual findings, decisions and why, within a token budget,
read-only: `$STATE recall --files "<the task's files>"` (`memory show <id>` for
one task in full).

Implement it yourself. The scope guard refuses an edit to a file the task does
not name. That refusal is the plan being enforced, not an obstacle:

```
SCOPE_CHANGE_REQUIRED — say which file and why, then widen the task in place:
$STATE start --amend --files "+<path>" --why "<why the task needs it>"
```

The amendment is journaled; the task is not re-planned. A file that belongs to
a different change is not amended in — it is recorded with `$STATE memory risk
add --title … --where "file:line" --label RISK --what …` (in files mode that
writes `.ai/project/known-risks.md`) and left for its own task.

Production behaviour is the source of truth: code that looks wrong may be
load-bearing. Change only what the task asked for; a refactoring never rides
along with a feature (`workflows.md#refactoring`).

## 3. Each step's own tests

After each piece of work run **only its own tests**, to the end, and fix their
failures there:

```bash
$STATE verify --scope step --files "<its tests>"
```

Never the full suite mid-edit, never e2e. **A bugfix shows its test failing
before the fix** (C2):

```bash
$STATE verify --scope step --files "<the new test>" --expect fail   # must bite
```

`expected fail: … it bites` is the proof; "does not bite yet" means the test
does not reproduce the bug — fix the test, not the code.

A task with steps (guarded or full, from the plan) closes each one:

```bash
$STATE step-done <step-id>
```

It measures what the step changed. Exit 6 `SCOPE_CHANGE_REQUIRED` names the
files outside the task and the `start --amend` that widens it. A step still open
at `close` is finished by `close`.

## 4. Verify once, to the end

After the last edit:

```bash
$STATE verify --scope all
$STATE verify --scope all --e2e not-applicable "<why the change reaches no e2e flow>"
```

It runs `verify_command` from `.ai/policies/testing.md` with no fail-fast,
then — when the suite is green and the mode runs e2e — `e2e_command`, each to
the end, with the log under `.ai/state/logs/<task>/`. Exit 0 is green and
needs no agent to interpret. If the Verification block is empty, take the
command from the project instruction file or CI, say so, and ask the human to
write it into `testing.md` — it is theirs.

**Red: fix as one batch.** Read the log by path — `grep -n` for the failures,
`tail`, or `log-reader` (FAST) for a long one; never the log into this session.
Classify **every** failure first: new regression, existing failure, environment.
Fix all new regressions together, then run once more, naming what the batch
fixed:

```bash
$STATE verify --scope all --after-fix "<n> regressions: <one line each>"
```

- An existing failure is recorded with `$STATE memory risk add`, not fixed.
- An environment failure gets one more run, not a code change.
- Never edit a test to make it pass.
- Two whole-suite runs are the budget (`tests.max_suite_runs`; in a batch task
  `batch.max_suite_runs`). The third
  exits 6 `SUITE_BUDGET`: running it again is the human's decision, from their
  own terminal, with the command it prints — or the pick: with the dialog on it
  also prints `DIALOG_PENDING`, and you run the command the human picks,
  verbatim, once.

`verify` re-scores reversibility and domain from the diff. A `re-score:` line
can raise the mode; the `next:` it prints is the path from here. A mode never
drops during a task.

## 5. Questions — only real blockers

The plan collected the questions. During the build only these stop you: a guard
refusal you cannot answer with `--amend`, a re-score to reversibility or domain
2, or a plan assumption the code proves false. Then:

```bash
$STATE ask "<one line>" --option "A: <text>" --option "B: <text>" \
  --recommend A --context "<file:line>"
$STATE ask --batch /path/questions.json   # a subagent's QUESTIONS_NEEDED, as a JSON list
```

The batch is `[{"question": "…", "options": [{"key": "A", "text": "…"}, …],
"recommend": "A", "context": "file:line"}]` — a QUESTIONS_NEEDED option
`"A: text"` becomes `{"key": "A", "text": "text"}`.

Option keys are single letters, A first, at least two; `--recommend` marks the
one you would pick. Then **stop** and show the questions: while one is pending,
`step-done` and `close` exit 4. The human answers in the conversation — record
it with `$STATE answer Q1=B Q2=X:"free text"` or `--prose "1B 2A"` — or fills the
`[Answer]:` line in `.ai/reports/<task-id>/task.md` §Questions, which is then the
record. Never edit that file, and never answer on the human's behalf.

## 6. Hand over by mode

| Mode | Next |
|---|---|
| light | `/rr-ship` — `close` decides from the two facts whether a review is owed |
| guarded | `/rr-review` (one pass, BALANCED), then `/rr-ship` |
| full | `/rr-review` (one pass, STRONG), then `/rr-ship`, which asks the human |

## Keeping context small

- `grep -n`, then read the ranges that matched. A large file or a log goes to a
  FAST reader — `Explore` for code, `log-reader` for output — which returns
  `file:line` excerpts, never the file. A reader that must judge (where a
  behaviour really lives, whether two paths are coupled) is `ai-discovery` on
  BALANCED.
- Do not rediscover what `.ai/project/` records; if it is wrong, fix that file
  in this task.
- Between steps your context holds the goal, the mode, the current step and the
  last verdict. Everything else is on disk: `task.md`, the handoff, the logs.
- Tools and MCP servers the task does not need stay off.

## Rules

- No commit, push, merge or deploy. The task ends at `/rr-ship`, and approval is
  the human's.
- A refusal from a guard or from `state.py` names the way out; follow it, never
  reword the command to get past it.
- Failures are fixed in batches; one red test never restarts the task.
- Problems found outside the task are written down, not fixed.
