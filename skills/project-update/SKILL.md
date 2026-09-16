---
name: project-update
description: Bring an existing project's claude-agentic files up to date with the installed plugin — .ai/ policies, workflows, agent contracts and templates, the managed block in CLAUDE.md, the docs/sdlc templates and .gitignore entries. Untouched files are replaced, edited files are three-way merged keeping every edit, real conflicts are never overwritten. Use on "/project-update", "update the rules in this project", "обнови правилата", after reinstalling the plugin, or when /ai-status says the project is behind. /ai-init and /project-init call it when run again.
argument-hint: [--apply]
---

# /project-update $ARGUMENTS

The skill is the same under Claude Code and under Codex; resolve the install
root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/project-update" ] && break
done
```

`UPDATE` below means:

```bash
python3 "$AI_HOME/skills/project-update/update.py" "$PWD"
```

The script does the whole update deterministically. Your job is to show what it
will do, get a confirmation where one is owed, and merge what it cannot.

## 1. A task in flight

```bash
python3 "$AI_HOME/skills/ai-task/state.py" get --quiet
```

If a task is in flight, say so: updating the policies mid-task can change which
gates the rest of it needs. Ask whether to finish it first. Do not continue
without an answer.

## 2. Dry run

```bash
$UPDATE
```

Show its output as is; it is already short. If it says up to date and prints no
hint, say so and stop.

## 3. Confirm policy changes

Lines marked `policy` change `.ai/policies/*.json`: which stages a tier requires,
who runs them, what the guards allow. Those files are human-owned. Explain each
change in one plain sentence — for example "T0 and T1 no longer have a plan
stage" — and ask for confirmation.

Skip the question when there are no `policy` lines, or when `$ARGUMENTS`
contains `--apply`: then the human has already decided.

## 4. Apply

```bash
$UPDATE --apply
```

## 5. Merge the conflicts

A `conflict` line means the file was edited here and changed in the plugin, and
no clean merge exists. The project file was left alone; the plugin's version is
in the git-ignored copy the line names.

- **A markdown file:** read both. Keep everything project-specific — filled-in
  sections, local rules, names of this codebase's files — and take the plugin's
  rule and structure changes. Edit the project file, then delete the copy.
- **A JSON policy file:** you cannot edit it; the path guard refuses, on
  purpose. The script already applied every non-conflicting change and kept the
  project's value for the paths it lists. For each one, show the project value
  and the plugin value, and tell the human which one the plugin now expects and
  why it matters. They edit it.
- **The managed block in `CLAUDE.md` or `AGENTS.md`:** merge it like a markdown
  file, inside the markers only.

## 6. Hints

`verify_command is empty`: ask the developer for the one command that proves
the project is healthy and what a green run ends with, and fill the Verification
section of `.ai/policies/testing.md`. Every `/ai-task` depends on it.

## 7. Report

```bash
$UPDATE --check
git diff --stat
```

Say what changed, what was merged by hand, and what is left for the human. If
`/ai-status` would now show a stale risk-tier mirror, say so: it means the JSON
and its markdown mirror disagreed before this update, and the mirror needs a
hand edit. Suggest `git add -A .ai docs/sdlc .gitignore` plus the runtime
directories and instruction files the project has (`.claude CLAUDE.md`,
`.codex AGENTS.md`) and a commit; do not commit.

## Rules

- The script writes; you do not reimplement it. Never copy template files over
  project files by hand.
- `.ai/project/**`, the project `CLAUDE.md` outside the managed block and
  `.claude/settings.json` and `.codex/config.toml` belong to the project. The
  script only creates them when missing, and so do you.
- A conflict is resolved by merging, never by taking the plugin's version
  wholesale.
