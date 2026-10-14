# G-M8 read probe — T-2026-10-13-004

Gate for Step 7 (plan rev 2, M8). A human fills this in after installing the
additive build (Steps 3–4) and before migration 0006 deletes any project copy.

Setup, once:

```bash
cd "/Store/Claude Plugins/claude-agentic"
./install.sh --target both          # your usual --plan / --codex-plan flags
ls ~/.claude/claude-agentic/ai/policies/git.md ~/.codex/claude-agentic/ai/policies/git.md
```

Run each probe in a project that has `.ai/` and **no** `.ai/policies/git.md` of
its own (so the shared copy is the one read). Where a task must be in flight,
use any T2+ task (`state.py quick ... --tier T2`) and `close` it afterwards.

Record exactly one of **allowed** / **prompted** / **refused** per row.

| # | Runtime / context | Action | Result |
|---|---|---|---|
| 1 | Claude Code main session, default permission mode | Read `~/.claude/claude-agentic/ai/policies/git.md` | allowed — main session Read, no prompt, `# Git policy` |
| 2 | Claude Code foreground subagent (e.g. `Explore`) | same Read | allowed (INFERENCE from row 3: a background subagent cannot prompt, so it reading without one covers the foreground case) |
| 3 | Claude Code background subagent | same Read | allowed — Explore (FAST) in background, no prompt, `# Git policy` |
| 4 | Claude Code, task in flight | Bash `~/.claude/claude-agentic/ai-path policies/git.md` | allowed — `ai-path --root <m8-probe>` with T-2026-10-13-004 in flight → `~/.claude/claude-agentic/ai/policies/git.md` |
| 5 | Codex `--sandbox read-only` | read `~/.codex/claude-agentic/ai/policies/git.md` | allowed — `codex exec` 0.157.1 → `# Git policy` |
| 6 | Codex `--sandbox read-only` | run `~/.codex/claude-agentic/ai-path policies/git.md` | allowed — `codex exec` → `~/.codex/claude-agentic/ai/policies/git.md` |
| 7 | Codex `--sandbox workspace-write` | read `~/.codex/claude-agentic/ai/policies/git.md` | allowed — `codex exec` → `# Git policy` |
| 8 | Codex `--sandbox workspace-write` | run `~/.codex/claude-agentic/ai-path policies/git.md` | allowed — `codex exec` → `~/.codex/claude-agentic/ai/policies/git.md` |

Prompt to use in each session, verbatim:

> Read ~/.claude/claude-agentic/ai/policies/git.md (Codex: ~/.codex/…) and print its first line. Do nothing else.

## Verdict

- All eight **allowed** → G-M8 passes; Step 7 may start.
- Any **prompted** or **refused** → `SCOPE_CHANGE_REQUIRED`: the plan gains a
  step that adds a read rule for `<home>/claude-agentic/` to
  `settings.common.json` (and the Codex config if a Codex row failed), before
  Step 7.

Filled in by: ikakarov  Date: 2026-10-14

Verdict: all eight allowed → G-M8 passes (results recorded by the agent at the human's request, 2026-10-14; probe project scaffolded without policies/git.md; rows 5–8 via `codex exec`).
