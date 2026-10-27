---
name: rr-plan
description: Plan work before any edit. Given a spec (docs/sdlc/specs/<slug>.md), write the programme plan docs/sdlc/plans/<slug>.md — files that change, order of work, risks, proof per requirement, rollback. Given one task, measure its weight with `state.py weight` (six axes, seven lines), take the mode it gives (light, guarded, full), shape the plan by that mode — inline, plan mode, or written — collect every question the plan depends on now, and register the task with `state.py start`, which arms the scope guard. Use on "/rr-plan", "plan this", "plan the implementation", "make the plan from the spec", and whenever /rr-build finds no task in flight.
argument-hint: <task in one sentence> | <path to docs/sdlc/specs/<slug>.md>
---

# /rr-plan $ARGUMENTS

Plan, never edit: this skill reads code and writes a plan, and the first edit
belongs to `/rr-build`. Resolve the install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-plan" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

Read `docs/sdlc/constitution.md` first and cite the principles a decision rests
on as `C<n>`; if it is absent, say so in one line and go on. `$STATE status`
first: a task already in flight is finished or abandoned before another starts.

## A spec → the programme plan

When `$ARGUMENTS` is a spec (default: the newest `docs/sdlc/specs/*.md`):

1. `docs/sdlc/plans/TEMPLATE.md` exists, else `/rr-setup`. If the spec's
   **Flagged concerns** holds unresolved items, list them and have the human
   resolve or explicitly accept each one before planning.
2. If `superpowers:writing-plans` is available, use it for the step
   granularity. Otherwise map each requirement to the files that must change
   (`grep -n`; `Explore` when a file is not found in a few calls), order the
   steps so each leaves the repository working, one step about one commit, and
   name the command or test that proves it.
3. Challenge it before writing: *what could this break* (callers, migrations,
   config, other environments) and *which step is the riskiest — can it move
   earlier or be split*. The answers go into **Risks**; mark the risky step.
4. Copy the template to `docs/sdlc/plans/<slug>.md`, fill **Files that change /
   Order of work / Risks / Proof / Rollback**; Proof maps every requirement R<n>
   to a test or command. One round of corrections; suggest the commit
   `plan: <title>`. Each row of the plan is later one task, planned below.

## A task → weight, mode, plan, start

**1. Classify** the request: feature, bugfix, refactoring, hotfix or
investigation — say which and why. `using-riskrails.md` in the shared tree
(`"$AI_HOME/riskrails/ai-path" using-riskrails.md`) and
`workflows.md#<kind>` say what each kind requires. A refactoring and a feature
are never one task.

**2. Name the files** from the request, confirmed with `grep -n`. Then weigh:

```bash
$STATE weight --files "<a>,<b>" --goal "<one sentence>" \
  --declare behaviour=<0-2>:"<evidence>" --declare novelty=<0-2>:"<evidence>"
```

Seven lines: six axes, W and the mode. Scope, reversibility, coverage and the
hints are measured; behaviour, domain and novelty are yours to declare, each
with its evidence — a declaration without one is refused. Declare what the
change does to the project's decisions, not how long it feels. An unknown axis
scores 1. A hint raises an axis; a declaration below a hint does not lower it.
The table is `.ai/policies/weight.json` (`weight.md` mirrors it).

**3. The mode is the weight's**, not yours: raising it is free
(`--mode <m> --by "<name>"` on `start`); lowering it is the human's, from their
own terminal. Shape the plan by it:

| Mode | Plan | Who sees it before the first edit |
|---|---|---|
| light | inline: files, the test, the rollback, in one to five lines | nobody — go |
| guarded | plan mode: numbered steps, each with its files and tests | the human accepts plan mode |
| full | written: steps, files, tests, what stays the same, risks, rollback; `architect` on STRONG when the design is open | the human reads and accepts it |

In every mode: a bugfix's first step is its failing test (C2); a change to
legacy behaviour without a test starts with a characterization test; the
rollback is one line, usually `git revert`. A plan over eight steps is advised
against, not refused — fewer, larger steps cost fewer handoffs.

**4. Questions, now.** Everything the plan depends on is asked before `start`,
so `/rr-build` stops only on a real blocker. Ask in the conversation, or on the
record with `$STATE ask --topic <slug> …` and `$STATE answer --topic <slug> …`
(see `/rr-spec`); a plan with an open **(blocking)** question is not accepted.

**5. Start.** One call registers the task, its weight and mode, its files and
steps, and arms the scope guard:

```bash
$STATE start --goal "<one sentence>" --workflow <kind> --files "<a>,<b>" \
  --tests "<t>" [--declare …] [--plan-file /path/steps.json] [--mode <m> --by "<name>"]
```

`--plan-file` is a JSON list `[{"id": "s1", "files": [...], "tests": [...]}]`
for a guarded or full plan with steps; a light task is one scope and needs none.
`--files` lists every file of every step — the guard refuses an edit outside
them. `--tests` names the task's own tests; a bugfix names its failing test. At
guarded and full, run `start` only after the human accepted the plan.

Then hand over: `/rr-build` continues from the state, in this session or the
next.
