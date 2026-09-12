---
name: ai-status
description: Show where the current agentic task stands — id, stage, next action, risk tier, current step and its allowed files, test/review/security status, open risks — plus which model the EXPERT tier resolves to and whether the risk-tier mirror is stale. Read-only. Use for "/ai-status", "where are we", "what is the agent working on".
---

# /ai-status

Read-only. This skill never changes state; it reports it.

## Steps

1. **Find the project.** Walk up from `$PWD` for a `.ai/` directory. If there is
   none, say so and point at `/ai-init` — nothing else in this skill applies.

2. **The task in flight:**

   ```bash
   python3 "$HOME/.claude/skills/ai-task/state.py" get
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

4. **Model routing.** Read `~/.claude/settings.json`:

   ```bash
   jq -r '{model, fallbackModel, effortLevel}' ~/.claude/settings.json
   grep -E '^(model|effort):' ~/.claude/agents/ai-expert.md
   python3 ~/.claude/hooks/fable-gate.py status 2>/dev/null
   ```

   Report what the tiers resolve to on this machine: FAST is haiku, BALANCED is
   sonnet (and the session, per `model`), STRONG is opus, and **EXPERT is the
   `model:` pinned in `ai-expert.md`** — name it, so the reader knows what an
   escalation would actually cost. If `model` is not sonnet, say so: the session
   is running above the default tier. When EXPERT is fable and the gate reports
   `active`, EXPERT is running on Opus right now — say until when, and why.

5. **Risk-tier mirror staleness.** `.ai/policies/risk-tiers.md` carries the
   sha256 of the JSON it was generated from:

   ```bash
   python3 -c "import hashlib;print(hashlib.sha256(open('.ai/policies/risk-tiers.json','rb').read()).hexdigest())"
   grep -o 'sha256:[0-9a-f]*' .ai/policies/risk-tiers.md
   ```

   If they differ, warn in one line that the JSON changed and the markdown mirror
   did not. The JSON is the source of truth; the warning is not an error.

6. **Guards.** Say in one line each whether the three hooks are active here:
   `ai-git-guard` always is; `ai-path-guard` and `ai-scope-guard` are active
   because `.ai/` exists; the scope guard is armed only while a step is current.

## Rules

- Read only. No edits, no state changes, no commits.
- Keep it to a screen. This is a status check, not a report.
