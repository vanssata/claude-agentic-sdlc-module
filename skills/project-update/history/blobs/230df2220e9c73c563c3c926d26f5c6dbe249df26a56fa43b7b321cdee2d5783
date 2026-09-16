# Context management policy

Context length, not model choice, is the dominant cost of an agent session: the
main session re-reads its whole context on every turn, so one large file read is
paid for again on every subsequent turn.

## The progressive strategy

```
repository → candidate files → relevant files → structured summary → task context
```

Each arrow narrows the material. Agents downstream of the summary should receive
the summary plus the exact files they need, never the repository.

## Rules for every agent

- Search with `rg -n` / `grep -n` and read only the ranges that matched. Do not
  read a file in order to search it.
- Never read a file over ~4000 lines whole. Read the range, or send a reader
  agent and keep its answer.
- Never paste logs, test output, migrations, lockfiles or generated code into the
  context. Summarise, cite, and move on.
- Prefer one subagent that returns twenty lines over five tool calls whose raw
  output stays in context for the rest of the session.
- Do not rediscover what `.ai/project/` already records. If it is wrong, fix the
  file — that is what it is for.

## Context budgets

| Tier | Gets |
|---|---|
| FAST | a file list, a pattern, one question |
| BALANCED | the task context plus the specific files named in it |
| STRONG | the compressed task context plus the critical source, nothing else |
| EXPERT | only what the decision turns on: the conflict, the constraints, the options |

Never hand a stronger model unrelated source files, full logs, complete git
history, dependency trees, vendor directories, caches or build artifacts.

## Deterministic tools first

`rg`, `git`, `jq`, an AST tool, the language server, PHPStan/Psalm, the framework
CLI and the test runner answer questions exactly and for free. Ask the model to
reason **about their output**, not to reproduce what they already know.

## Structured context shape

The Context agent produces exactly this, and nothing else:

```
task:
affected_modules:
entry_points:
execution_flow:
relevant_files:
interfaces:
dependencies:
legacy_constraints:
business_rules:
tests:
known_risks:
unknowns:
open_questions:
```
