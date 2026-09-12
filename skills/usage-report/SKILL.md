---
name: usage-report
description: Report Claude Code token usage and cost from local transcripts at zero model cost. Use when the user asks what a session/day/project cost, how many tokens were burned, or which model spent the most — instead of parsing transcripts with the model.
---

# Usage report

Run the bundled script — do not re-derive the parsing logic from transcripts:

```bash
python3 ~/.claude/skills/usage-report/usage-report.py            # current project
python3 ~/.claude/skills/usage-report/usage-report.py --all      # all projects on this machine
python3 ~/.claude/skills/usage-report/usage-report.py --today    # current UTC day only
python3 ~/.claude/skills/usage-report/usage-report.py --session <prefix>
python3 ~/.claude/skills/usage-report/usage-report.py --root <dir>
```

It prints per-model token counts (input / output / cache write / cache read),
per-day cost, per-session cost, per-project cost (with `--all`), the subagent
share, and a total.

Notes:
- Reads `~/.claude/projects/**/*.jsonl` — local transcripts only; sessions from
  other machines are not visible.
- The DAY column is the transcript timestamp's UTC date; `--today` filters by
  UTC as well, so late-evening local work may land on the "previous" day.
- Prices are hardcoded in the script's `PRICES` table ($/MTok as of 2026-07);
  update them there when pricing changes.
- Costs are estimates computed from token counts; subscription plans (Pro/Max)
  don't bill per token — treat the dollar figures as model-usage equivalents.
- One API response spans several transcript lines (one per content block); the
  script counts each response once by `message.id`. CALLS is API responses, not
  transcript lines. Subagent transcripts are the `agent-*` sessions.
- Cache read and cache write are usually most of the cost: that is context
  length, not model choice — see the context-hygiene rules in `~/.claude/CLAUDE.md`.

Relay the numbers the user asked for; don't dump the full table unless asked.
