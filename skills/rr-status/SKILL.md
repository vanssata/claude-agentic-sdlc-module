---
name: rr-status
description: Show where the task in this directory stands, in at most twenty lines — which .ai/ root governs it, task and goal, mode and weight, stage and next action, steps and files, verify runs against the budget, the two facts, review, the approval gate, pending questions, the project's schema against the plugin's, and the last journal event. Read-only and model-free. `--cost` adds token usage and cost from the local transcripts, for Claude Code and Codex. Use for "/rr-status", "where are we", "what is the agent working on", "why did a guard fire here", "what did this task / session / day cost".
argument-hint: [--cost [usage-report flags]]
---

# /rr-status $ARGUMENTS

Read-only. Resolve the install root, run the script and print its output
**verbatim**, as a code block — no summary, no table, no commentary before it:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -f "$AI_HOME/skills/rr-status/status.py" ] && break
done
python3 -I "$AI_HOME/skills/rr-status/status.py" --root "$PWD"
```

After the output, at most one line, and only when a line asks for it:

- `root:` is an ancestor of this repository, or `$HOME`: that `.ai/` arms the
  guards for every repository below it. Say so.
- `schema: … — behind`: point at `/rr-setup --update`.
- `questions: N pending` with N > 0: the task is halted until they are
  answered — `/rr-build` shows them. The count can lag an `[Answer]:` line the
  human filled in the file; `state.py handoff --print` re-reads the file.
- `gate: requested`: the human runs the `approve` command `/rr-ship` printed,
  in their own terminal; you cannot.

Exit 1 with `root: none` means no `.ai/` governs this directory: `/rr-setup`
sets one up.

## --cost

With `--cost` and nothing else, add `--cost` to the `status.py` call: the
task's token report follows the status lines. With any other usage flag, run the
bundled report instead — never re-derive the parsing from transcripts:

```bash
R="python3 $AI_HOME/skills/usage-report/usage-report.py"
$R                        # current project, every runtime that has transcripts
$R --all | --today        # all projects on this machine | the current UTC day
$R --session <prefix>     # one session (Claude) or thread (Codex) id prefix
$R --provider auto|claude|codex|both [--root <dir>]
$R --task <task-id> [--project DIR]   # one task, from its journal's window
$R --budgets              # the installed plans' budget tables
$R --no-cache             # ignore the parse cache for this run
```

It prints per-model tokens (input, output, cache write, cache read), a
per-runtime split when both have data, per-day, per-session and per-project
cost, the subagent share and a total. Relay the numbers asked for; do not dump
the table unless asked.

Say these whenever you quote it:

- `--task` brackets the task by its journal (`task_started` to `task_closed`,
  UTC): the window includes anything else the session did in those minutes. It
  prints the mode when the journal has one, else the tier, and the plan's budget
  for it — reported, never enforced.
- The dollar column is an estimate from token counts. Subscription plans are not
  billed per token; a provider whose table in `prices.json` has
  `rates_verified: false` gets an ESTIMATE note. Compare runtimes by tokens.
- DAY is the UTC date; CALLS counts API responses. Codex's input includes the
  cached part, so the script subtracts it; IN is fresh input in both runtimes.
- Cache read and write are usually most of the cost: that is context length, not
  model choice.

Local transcripts only (`~/.claude/projects/**/*.jsonl`,
`~/.codex/sessions/**/rollout-*.jsonl`); sessions from other machines are not
visible. The parse cache is `~/.cache/claude-agentic/usage-report.json`
(`USAGE_REPORT_CACHE=<path>` moves it, empty turns it off); delete it if you
suspect it, and `--no-cache` tells within one run whether it was the cache.
