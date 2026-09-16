---
name: ai-status
description: Show where the current agentic task stands — id, stage, next action, risk tier, current step and its allowed files, test/review/security status, open risks — plus which model the EXPERT tier resolves to and whether the risk-tier mirror is stale. Read-only. Use for "/ai-status", "where are we", "what is the agent working on".
---

# /ai-status

Read-only. This skill never changes state; it reports it.

Resolve the install root once — the skill runs the same under Claude Code and
under Codex, and the state it reads lives in the project, not in the install:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/ai-task" ] && break
done
```

## Steps

1. **Find the project.** Walk up from `$PWD` for a `.ai/` directory. If there is
   none, say so and point at `/ai-init` — nothing else in this skill applies.

2. **The task in flight:**

   ```bash
   python3 "$AI_HOME/skills/ai-task/state.py" get
   ```

   If there is none, say "no task in flight" and skip to step 4. Otherwise report,
   compactly:

   - task id, goal, workflow, risk tier;
   - current stage and next action;
   - the current step, if any: its description and its `allowed_files` — this is
     what the scope guard is enforcing right now;
   - completed steps out of total;
   - test, review and security status;
   - open risks;
   - human approval: required, and whether granted and by whom;
   - how long since `updated_at`. Flag a stage of `implementation` that has not
     moved in a long time: it may have stopped mid-step.

3. **The audit trail.** The last few `history` entries, one line each, so the
   reader can see how the task got here.

4. **Model routing.** Report the ladder of the runtime you are actually running
   in. Read whichever configuration exists:

   ```bash
   # Claude Code
   jq -r '{model, fallbackModel, effortLevel}' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/settings.json"
   grep -E '^(model|effort):' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/agents/ai-expert.md"
   python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks/fable-gate.py" status 2>/dev/null

   # Codex
   grep -E '^(model|model_reasoning_effort|default_subagent_)' "${CODEX_HOME:-$HOME/.codex}/config.toml"
   grep -E '^(model|model_reasoning_effort) *=' "${CODEX_HOME:-$HOME/.codex}/agents/ai-expert.toml"
   python3 "${CODEX_HOME:-$HOME/.codex}/hooks/codex-model-gate.py" status 2>/dev/null
   ```

   Report what the tiers resolve to on this machine, and **name the model, not
   the tier** — so the reader knows what an escalation would actually cost:

   | Tier | Claude Code | Codex |
   |---|---|---|
   | FAST | haiku | `gpt-5.6-terra` (Terra) |
   | BALANCED | sonnet | `gpt-5.6-terra` (Terra) |
   | STRONG | opus | `gpt-5.6-sol` (Sol) |
   | EXPERT | `ai-expert`: the session model on Max and Team Max, `opus` pinned on Pro and Team Pro | the `model` pinned in `ai-expert.toml` (`xhigh` on Pro, `high` on Plus) |

   Under Claude Code, when `model` is `opusplan`, say so in one line: Opus in
   plan mode, Sonnet when executing, and `ai-expert` and `architect` pin `opus`
   explicitly. On Max and Team Max the session is Opus 5, `ai-expert` inherits it, and
   `architect` alone may be pinned to `fable[1m]` — check its frontmatter:

   ```bash
   grep -E '^model:' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/agents/architect.md" || echo "architect inherits the session model"
   ```

   When a runtime's gate reports `active`, its top model is running one tier down
   right now — say until when, and why. A Codex install has no `fable-gate`, a
   Claude install has no `codex-model-gate`; report only the one that exists.

   Also print the pipeline profile, because it decides how much of a task is
   delegated:

   ```bash
   jq -r '.pipeline_profile // "team"' .ai/policies/risk-tiers.json
   ```

5. **Risk-tier mirror staleness.** `.ai/policies/risk-tiers.md` carries the
   sha256 of the JSON it was generated from:

   ```bash
   python3 -c "import hashlib;print(hashlib.sha256(open('.ai/policies/risk-tiers.json','rb').read()).hexdigest())"
   grep -o 'sha256:[0-9a-f]*' .ai/policies/risk-tiers.md
   ```

   If they differ, warn in one line that the JSON changed and the markdown mirror
   did not. The JSON is the source of truth; the warning is not an error.

6. **Plugin version.** One line from:

   ```bash
   python3 "$AI_HOME/skills/project-update/update.py" "$PWD" --check
   ```

   When it exits 1, the project's rules are older than the installed plugin:
   say so and point at `/project-update`.

7. **Guards.** Say in one line each whether the three hooks are active here:
   `ai-git-guard` always is; `ai-path-guard` and `ai-scope-guard` are active
   because `.ai/` exists; the scope guard is armed only while a step is current.
   The same three run in both runtimes. Under Codex they also see `apply_patch`,
   which can touch several files in one call — every path in the patch is checked
   separately, so one out-of-scope file rejects the whole patch. Codex has no
   hookable read tool, so `cap-large-read` is Claude-only there; note that if the
   session is running under Codex.

## Rules

- Read only. No edits, no state changes, no commits.
- Keep it to a screen. This is a status check, not a report.
