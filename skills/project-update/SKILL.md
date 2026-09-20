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

A `schema 0 -> 1` line means the project was initialised before the current tree
layout and a migration will run before anything is merged. `[0001]` marks the
lines a migration owns. A `move` line moves a file the project may have edited —
the edit is carried to the new path — and keeps a copy of the original under
`.ai/reports/project-update-<date>/`. A `delete?` line is a proposal, not a
deletion: see step 4.

`.ai/VERSION` is the schema of the project's `.ai/` tree. It is not the
`"version"` inside `.ai/policies/risk-tiers.json`, which versions that file's
content.

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

Exit 3 means the apply stopped: a file changed between the dry run and the
write, a target is not a regular file (a symlink is refused, never followed), or
a write failed. Nothing after that item was written, every operation is
idempotent, and the message names the file. Run the dry run again and show it.

**A `delete?` line is for the human, not for you.** Never pass
`--confirm-delete` yourself, not even when `$ARGUMENTS` contains `--apply`.
Show the proposed deletion and its reason, and give them the command to run in
their own terminal:

```bash
python3 "$AI_HOME/skills/project-update/update.py" "$PWD" --apply --confirm-delete "<your name>"
```

Give it with `$AI_HOME` and `$PWD` already substituted — they are variables of
your session, not of their shell.

The name they type goes into `.ai/reports/project-update-<date>/migration.json`,
next to a copy of the file. Say that the schema version stays where it is until
the deletion is settled — the update is not finished while it is pending, and
`--check` keeps saying so. There are two ways to settle it: run that command, or
delete the file by hand. There is no way to decline a proposal and move on; say
so plainly rather than leaving them waiting for a third option.

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

`the managed block is N B, budget 2048 B`: the always-loaded block costs more
than a project block is meant to cost, and it is re-read on every turn of every
task. The hint says whose it is to fix. *Edited here* means the plugin will not
rewrite it — offer to move the project's own lines out of the markers, so the
next run can replace the block with the plugin's stub. *The plugin ships it that
size* is a plugin bug: report it, do not trim the project's file.

`N principles, at most 15` / `N B, at most 4096` on
`docs/sdlc/constitution.md`: advisory here, hard only for the plugin's own
template. A constitution nobody can hold in their head is not one — offer to
move the principles that are really policy into `.ai/policies/`.

`that rule is not rendered; the rest are`: a file under `.ai/rules/` did not
parse. Name it and what it needs (a `paths:` list and a body); the other rules
were rendered.

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
- `--confirm-delete` is typed by a human. So is any edit to `.ai/policies/*.json`.
- The schema version advances only when its migrations are finished. A conflict
  or an unconfirmed deletion from a migration holds it back on purpose: writing
  it would make the next run see a current project and plan nothing.

## Writing a migration

One module per version in `skills/project-update/migrations/`, named
`NNNN_slug.py`, numbered contiguously from `0001`, with `VERSION` equal to the
prefix, a one-line `TITLE`, a static `MOVES` list and `plan(ctx)`.

- Every rename a migration performs belongs in `MOVES`, so the template history
  follows the file and the project's edits merge at the new path. `ctx.move`
  refuses a pair that is not there.
- A template renamed under `skills/project-init/templates/` changes its history
  key without moving any project path; record it in `RETIRED` as
  `{"project-init/old-name.md": "project-init/new-name.md"}`. `RETIRED` also
  takes `None` for a template that is simply gone. The test suite fails on a
  history key that is neither current, nor a `MOVES` source, nor listed there.
- A migration that deletes must retire the template in the same release,
  otherwise the next run re-creates the file.
- `ctx.patch_state` is the only way to change a task in flight, and the only
  writer of `.ai/state/current.json` other than `state.py`. A migration that
  moves a path a task's step may touch must patch it, or the scope guard will
  stop that task on a file that no longer exists.
- Operations are planned, never written: the dry run must list everything.
  Paths are project-relative and normalised, and content is `bytes`.
- `plan(ctx)` runs again on every run until the schema version advances, and a
  conflict or an unconfirmed deletion holds it back. Every `fn` must therefore be
  idempotent: append a line only when it is not already there, or the next run
  appends it again.

### What a migration can ask the plugin

`ctx` carries what the plugin knows about itself, so a migration recognises its
own text instead of matching a pattern against the human's prose:

- `ctx.instruction_files()` — the root instruction files this project actually
  has, one per runtime it declares (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.junie/guidelines.md`).
- `ctx.shipped(path)` — every version of every template the plugin ever
  installed at that path, oldest first, following renames. A migration that
  removes shipped text matches it **verbatim against one of these**; a regular
  expression over the project's prose is how a migration eats a paragraph
  somebody wrote.
- `ctx.block_status(path)` — `"none"`, `"shipped"` or `"edited"` for the managed
  block. An edited block is never written over, by a migration or by anything
  else.
- `ctx.hint(text)` — say something to the human that is not an operation on a
  file. The right answer whenever the text is no longer the plugin's.

A migration that edits a file **outside `.ai/`** is editing the project's own
file: `apply` copies the original to
`.ai/reports/project-update-<date>/original/<path>` before the first write, so
what was there is recoverable without git.
