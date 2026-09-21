---
name: ai-status
description: Show where the current agentic task stands — which .ai/ root governs this directory, id, stage, next action, risk tier, current step and its allowed files, test/e2e/review/security status, open risks, what the always-loaded instruction block costs — plus what each tier resolves to on this plan, the runtime gate and quota, and whether the risk-tier mirror is stale. Read-only. Use for "/ai-status", "where are we", "what is the agent working on", "why did a guard fire here".
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
   - human approval: required, and whether granted and by whom. When
     `human_approval.via` is `unattended`, or a `gate_approved` event carries
     `data.unattended`, **say so on its own line**: the gate was opened by a
     launcher variable rather than by a person at a terminal. That is legitimate
     in CI and misleading everywhere else, so it is reported, never hidden.
     When `requested_at` is set and `granted` is not, the gate is open and
     waiting — name the command the human has to run;
   - **pending questions.** `state.py questions --pending --format prose`. While
     any non-gate question is pending, nine commands exit 4 — that is usually the
     answer to "why is nothing happening";
   - `owner_runtime`, and whether it is the runtime this session is in. When they
     differ, say it plainly: the task was last touched from the other runtime, so
     the next mutating command records a `runtime_handoff`;
   - `resume_point` — the one line saying where the work was interrupted;
   - the age of `.ai/state/handoff.md`. When it is much older than `updated_at`
     the handoff was not rewritten by the last command; say so, and point at
     `state.py handoff` to refresh it.

3. **The audit trail.**

   ```bash
   python3 "$AI_HOME/skills/ai-task/state.py" events --last 8
   ```

   The journal, newest last, one line each. It is the fuller record: it carries
   the runtime, the actor and the typed `data` that `history[]` does not. If the
   journal is missing — a task created before schema 2, or a project that has not
   run `/project-update` — fall back to the last few `history` entries and say
   which of the two you are showing.

4. **Model routing, gate and quota.** Read them from the tools, not from a
   table in this file — the plan decides the models, and the same tier names a
   different model on each plan and each runtime:

   ```bash
   STATE="python3 $AI_HOME/skills/ai-task/state.py"
   for t in FAST BALANCED STRONG EXPERT; do echo "$t $($STATE profile --tier $t 2>/dev/null || echo '?')"; done
   $STATE profile --field label 2>/dev/null
   GATE="$AI_HOME/hooks/runtime-gate.py"
   python3 "$GATE" status 2>/dev/null
   python3 "$GATE" quota 2>/dev/null
   ```

   Report what each tier resolves to on this machine and **name the model, not
   only the tier**, so the reader knows what an escalation would cost. With no
   plan profile (an install from before WP5) say so, and read the pins instead:
   `grep -E '^(model|effort):' "$AI_HOME/agents/ai-expert.md"` on Claude Code,
   `grep -E '^model' "$AI_HOME/agents/ai-expert.toml"` on Codex. `architect` may
   pin a model of its own (or inherit the session): check its frontmatter.

   When the gate reports `active`, the top model is running one tier down right
   now — say until when, and why. Give the quota line as it prints, `stale`
   included; a stale or unknown quota is not a reason to move anything.

   If a task is in flight, add the preferred runtime when there is one — the
   last `preferred runtime:` line in `.ai/state/handoff.md` — and whether the
   task is handed over (`Handed to …` in the same file).

   Also print the pipeline profile, because it decides how much of a task is
   delegated:

   ```bash
   jq -r '.pipeline_profile // "team"' .ai/policies/risk-tiers.json
   ```

5. **The sensors.** One line, from the report `state.py review-gate` wrote —
   this is what decides whether a T2 review runs at all, so a reader must see
   it without asking:

   ```bash
   python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/ai-task/sensors.py" --root . report 2>/dev/null \
       | tail -n +2 || echo "sensors: not checked yet"
   ```

   Say which sensors are green, which are red, and which are `unavailable` —
   and for an unavailable one, print the line it proposes for
   `.ai/policies/testing.md`. An unavailable sensor is not a problem with the
   task; it is a review that will run.

6. **Risk-tier mirror staleness.** `.ai/policies/risk-tiers.md` carries the
   sha256 of the JSON it was generated from:

   ```bash
   python3 -c "import hashlib;print(hashlib.sha256(open('.ai/policies/risk-tiers.json','rb').read()).hexdigest())"
   grep -o 'sha256:[0-9a-f]*' .ai/policies/risk-tiers.md
   ```

   If they differ, warn in one line that the JSON changed and the markdown mirror
   did not. The JSON is the source of truth; the warning is not an error.

7. **Plugin version.** One line from:

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

8. **Instruction budget.** What this project loads on every turn, before any
   skill or policy is read. Advisory: the plugin measures its own block and
   never refuses the project's file.

   ```bash
   for f in CLAUDE.md AGENTS.md GEMINI.md .junie/guidelines.md; do
     [ -f "$AI_PROJECT/$f" ] && python3 "$AI_HOME/skills/project-update/render_instructions.py" \
       measure "$AI_PROJECT/$f" --block --budget 2048
   done
   [ -f "$AI_PROJECT/docs/sdlc/constitution.md" ] && \
     python3 "$AI_HOME/skills/project-update/render_instructions.py" \
       constitution "$AI_PROJECT/docs/sdlc/constitution.md"
   ```

   One line per instruction file: the bytes of the managed block and the budget.
   A line ending in `OVER` means the block is larger than the 2 048 B a project
   block is meant to cost — say whose it is to fix: if `/project-update` reports
   a conflict on that file, the block was edited here and the plugin will not
   rewrite it, so trimming it is the project's; otherwise it is the plugin's and
   `/project-update` will replace it. The constitution line names the count and
   the bytes, and anything above 15 principles or 4 096 B is a prompt to move a
   principle into `.ai/policies/`, not an error.

   The global stub is not measured here — `install.sh` prints its size line on
   every install, and `~/.claude/CLAUDE.md` is the user's file, not a project's.

9. **Guards.** Say in one line each whether the three hooks are active here:
   `ai-git-guard` always is; `ai-path-guard` and `ai-scope-guard` are active
   because of the `.ai/` at `AI_PROJECT` from step 1 — name it again here if it
   was not this repository, because that is where a surprising deny comes from;
   the scope guard is armed only while a step is current.
   The same three run in both runtimes. Under Codex they also see `apply_patch`,
   which can touch several files in one call — every path in the patch is checked
   separately, so one out-of-scope file rejects the whole patch. Codex has no
   hookable read tool, so `cap-large-read` is Claude-only there; note that if the
   session is running under Codex.

   **Under Codex, say this out loud as well.** The rule that denies
   `state.py approve` exists only once the user has trusted hooks through
   `/hooks`; until then nothing stops an agent from running it, and the agent
   contract and the TTY check are the whole defence. The file route degrades too:
   it needs a `session.json` prompt recorded after the gate was requested, and
   only the hook writes that file. So on an untrusted Codex install the honest
   report is that approval is terminal-only and unenforced. This is a permanent
   difference in what the system can *prove* about an approval, not a
   misconfiguration to fix — report it and carry on.

## Rules

- Read only. No edits, no state changes, no commits.
- Keep it to a screen. This is a status check, not a report.
