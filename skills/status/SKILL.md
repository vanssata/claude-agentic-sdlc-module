---
name: status
description: Show where the agentic task in this directory stands, in at most twenty lines — which .ai/ root governs it, task and goal, tier and workflow, stage and next action, the current step and its files, tests and suite runs against the cap, e2e, review and security, the approval gate, pending questions, open risks, the project's schema against the plugin's, and the last journal event. Read-only and model-free. `--cost` adds the task's token report. Use for "/status", "where are we", "what is the agent working on", "why did a guard fire here".
---

# /status

Read-only. Run the script and print its output **verbatim**, as a code block —
no summary, no table, no commentary before it:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -f "$AI_HOME/skills/status/status.py" ] && break
done
python3 -I "$AI_HOME/skills/status/status.py" --root "$PWD"
```

With `--cost` in the request, add `--cost`: the task's token report from
`usage-report.py` follows the status lines.

After the output, at most one line, and only when a line asks for it:

- `root:` is an ancestor of this repository, or `$HOME`: that `.ai/` arms the
  guards for every repository below it. Say so.
- `schema: … — behind`: point at `/project-update`.
- `questions: N pending` with N > 0: the pipeline is halted until they are
  answered (`state.py questions --pending --format md`).
- `approval: requested`: the human runs `state.py approve --by "<name>"` in
  their own terminal; you cannot.

Exit 1 with `root: none` means no `.ai/` governs this directory: `/ai-init`
sets one up.
