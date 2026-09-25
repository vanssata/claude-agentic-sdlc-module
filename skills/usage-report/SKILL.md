---
name: usage-report
description: Report agent token usage and cost from local transcripts at zero model cost, for Claude Code and for Codex. Use when the user asks what a session/day/project cost, how many tokens were burned, which model spent the most, or how the two runtimes compare — instead of parsing transcripts with the model.
---

# Usage report

Run the bundled script — do not re-derive the parsing logic from transcripts.
Resolve the install root first; the skill is the same in both runtimes:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/usage-report" ] && break
done
R="python3 $AI_HOME/skills/usage-report/usage-report.py"

$R                        # current project, every runtime that has transcripts
$R --all                  # all projects on this machine
$R --today                # current UTC day only
$R --session <prefix>     # one session (Claude) or thread (Codex) id prefix
$R --provider codex       # one runtime only: auto | claude | codex | both
$R --provider claude --root <dir>
$R --task <task-id> [--project DIR]   # one /ai-task task against its plan budget
$R --budgets              # the installed plans' budget tables
$R --no-cache             # ignore the parse cache for this run
```

It prints per-model token counts (input / output / cache write / cache read),
a per-runtime split when both have data, per-day cost, per-session cost,
per-project cost, the subagent share, and a total.

`--provider auto` (the default) reads whichever runtimes have a transcript
directory. `both` demands both and says so if one is missing. `--root` names one
directory and therefore selects one runtime: an explicit `--provider` wins,
otherwise the directory is sniffed (Codex names its files `rollout-*.jsonl`) and
falls back to Claude, which is what a bare `--root` meant before.

## What it reads

| | Claude Code | Codex |
|---|---|---|
| transcripts | `~/.claude/projects/**/*.jsonl` | `~/.codex/sessions/**/rollout-*.jsonl` |
| one response is | several lines, one per content block | one `token_usage_record` |
| deduplicated by | `message.id`, keeping the largest `output_tokens` | `response_id` |
| model comes from | the message itself | the `turn_context` for the same `turn_id` |
| project | the mangled directory name | `cwd` from the session or turn context |
| subagents | `agent-*` sessions | a thread whose `session_meta.source` is a `subagent`, reported by name |

Local transcripts only; sessions from other machines are not visible.

### The parse cache

Transcripts are append-only and they grow: re-reading every line of every
session on each report is most of what the script does. So each file's parse
state is kept on disk, keyed by its path, mtime and size, and a rescan folds
only the bytes past the offset it stopped at.

`~/.cache/claude-agentic/usage-report.json` (or `$XDG_CACHE_HOME`).
`USAGE_REPORT_CACHE=<path>` moves it; `USAGE_REPORT_CACHE=` turns it off;
`--no-cache` skips it for one run without touching the file.

Same mtime, size and fold as the entry, and the file is not read again unless
its last line was unterminated when it was folded; grown, and
only the new bytes are read, up to the last complete line. A last line with no
newline after it is reported but not stored, so the next run reads it again —
completed or not — instead of folding half a record. Shrunk, a different first
block, or a state the other runtime's fold wrote, and the file is parsed from
zero. A cache that cannot be read, was written by another version, or holds
something this version cannot fold into is dropped rather than trusted: when the
cache is wrong it costs a reparse, not a wrong number.

Transcripts that no longer exist are dropped on each write; nothing else prunes
it, so the file grows with the history on the machine — roughly 230 bytes per
recorded response — a claude response stores two rows, one for its day and one
overall, so tens of MB for a long, busy history. The warm run pays for
reading and re-writing all of it whichever transcript changed, which is why the
cache wins on fat transcripts and can be a small loss on lean ones; `--no-cache`
is the measurement, not a guess. It is written 0600, in a directory it creates 0700 —
it holds project paths, session ids and token counts taken from transcripts the
runtimes themselves keep private. A directory that already exists keeps the
permissions it has; only the file's own mode is guaranteed.

Delete the file if you ever suspect it: the next run rebuilds it, and
`--no-cache` tells you within one run whether it was the cache talking.

### The task journal, when the question is "what did *this task* cost"

The transcripts carry tokens but no notion of a task; the journal
(`.ai/reports/<task-id>/events.jsonl`, schema 2 and up) carries the task but no
tokens. Between them they bracket the work: `task_started` and `task_closed` are
the first and last lines of a task's journal, and their timestamps are UTC ISO-8601
— the same clock the transcripts use.

```bash
python3 "$AI_HOME/skills/ai-task/state.py" events --format jsonl \
  | jq -r 'select(.event=="task_started" or .event=="task_closed") | "\(.ts) \(.event)"'
```

`--task <id>` does that for you: it reads the task's journal (never writes it),
takes the window from its first line to `task_closed` (or to now while it is
open), the final tier from the last `tier_set`/`tier_raised`, and the runtimes
from the journal lines and any `runtime_handoff`. It then prints each involved
runtime's tokens in the window — in, cache, out, total — and that runtime's own
plan budget for the tier (`budgets.tokens.per_task` in
`<home>/claude-agentic/profile.json`) with the share used:

```
task T-2026-09-21-001 tier T3 window 2026-09-21T10:00:00+00:00..2026-09-21T11:00:00+00:00
claude   tokens in 400,000 cache 1,900,000 out 100,000 total 2,400,000
         budget max T3 6.0M · used 2.4M (40%)
```

Say two things whenever you quote it: the window includes anything else the
session did in the same minutes, and the budgets are reported, never enforced —
conservative placeholders to be calibrated from these very numbers.
`--budgets` prints the tables themselves for every installed runtime.

## Reading the numbers

- The DAY column is the transcript timestamp's UTC date; `--today` filters by UTC
  as well, so late-evening local work may land on the "previous" day.
- CALLS is API responses, not transcript lines.
- Codex's `input_tokens` is the whole prompt *including* the cached part, so the
  script subtracts `cached_input_tokens` before billing; the IN column is fresh
  input in both runtimes. The `turn_token_usage` and `thread_token_usage` fields
  in the same record are running totals — the script does not read them.
- Prices live in `prices.json` next to the script, one table per provider.
  Edit that file when pricing changes; the parser does not need touching. A
  provider whose table has `rates_verified: false` gets an explicit ESTIMATE note
  under the total — the token columns are measured, the dollar column is not.
- Costs are estimates computed from token counts; subscription plans don't bill
  per token — treat the dollar figures as model-usage equivalents, and compare
  runtimes by tokens rather than by dollars unless both tables are verified.
- Cache read and cache write are usually most of the cost: that is context
  length, not model choice — see the context-hygiene rules in the global
  instruction file (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`).

Relay the numbers the user asked for; don't dump the full table unless asked.
