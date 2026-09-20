---
name: ai-status
description: Show where the current agentic task stands — which .ai/ root governs this directory, id, stage, next action, risk tier, current step and its allowed files, test/e2e/review/security status, open risks — plus which model the EXPERT tier resolves to and whether the risk-tier mirror is stale. Read-only. Use for "/ai-status", "where are we", "what is the agent working on", "why did a guard fire here".
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

1. **Find the project, and name the root you found.** The guards resolve their
   project the same way — nearest ancestor of the working directory holding a
   `.ai/` directory — so this is what makes the opt-in boundary visible:

   ```bash
   AI_PROJECT=""; d=$PWD
   while [ -n "$d" ] && [ "$d" != / ]; do
     [ -d "$d/.ai" ] && { AI_PROJECT="$d"; break; }
     d="${d%/*}"; [ -n "$d" ] || d=/
   done
   [ -n "$AI_PROJECT" ] || { [ -d /.ai ] && AI_PROJECT=/; }
   GIT_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
   ```

   The walk is `find_ai_root` in `hooks/lib/ai-hook-common.sh`, down to the
   `/.ai` case — it has to be, or the status can report "no project" in a
   directory where the guards are armed, which is the blind spot this closes.
   `tests/test-ai-status-root.sh` runs this block out of this file and compares
   the two.

   If `AI_PROJECT` is empty, say so and point at `/ai-init` — nothing else in
   this skill applies.

   Otherwise print the root. Say it plainly when it is the repository you are in
   (`AI_PROJECT` equals `GIT_ROOT`, or there is no git repository and it equals
   `$PWD`), and **warn** when it is not:

   - `AI_PROJECT` is an ancestor of `GIT_ROOT` — this repository is governed by a
     `.ai/` that belongs to a directory above it. Name both paths. The guards,
     the scope enforcement and every path in this report come from that outer
     project, not from this one. Either this repository wants its own
     `/ai-init`, or the outer `.ai/` does not belong where it is.
   - `AI_PROJECT` is `$HOME` — say so in as many words. A `.ai/` directory in the
     home directory silently arms the path and scope guards for **every**
     repository under it, including ones that never ran `/ai-init`, and it is
     almost always a mistake rather than a decision.

   This is a warning, not an error: report it and carry on with the rest.

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
   - test, e2e, review and security status;
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
   | EXPERT | `ai-expert`: `opus` pinned everywhere (`xhigh` on Max and Team Max, `high` on Pro and Team Pro) | the `model` pinned in `ai-expert.toml` (`xhigh` on Pro, `high` on Plus) |

   Under Claude Code, when `model` is `opusplan`, say so in one line: Opus in
   plan mode, Sonnet when executing, and `ai-expert` and `architect` pin `opus`
   explicitly. On Max and Team Max the session is Opus 5, `ai-expert` pins `opus` at `xhigh`, and
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
   say so and point at `/project-update`. The line names a schema step
   (`schema 0 -> 1`) when the project's `.ai/` tree predates the installed
   layout, and says the schema is held when a migration is waiting on a human.

   Exit 2 is not "behind": the script refused to run and the line says why —
   usually an `.ai/VERSION` newer than the installed plugin (the project was
   updated by a newer plugin than this one) or an unreadable one. Show that line
   and say that `/project-update` cannot run until it is resolved; a newer
   version means this machine's plugin needs updating, not the project.

7. **Guards.** Say in one line each whether the three hooks are active here:
   `ai-git-guard` always is; `ai-path-guard` and `ai-scope-guard` are active
   because of the `.ai/` at `AI_PROJECT` from step 1 — name it again here if it
   was not this repository, because that is where a surprising deny comes from;
   the scope guard is armed only while a step is current.
   The same three run in both runtimes. Under Codex they also see `apply_patch`,
   which can touch several files in one call — every path in the patch is checked
   separately, so one out-of-scope file rejects the whole patch. Codex has no
   hookable read tool, so `cap-large-read` is Claude-only there; note that if the
   session is running under Codex.

## Rules

- Read only. No edits, no state changes, no commits.
- Keep it to a screen. This is a status check, not a report.
