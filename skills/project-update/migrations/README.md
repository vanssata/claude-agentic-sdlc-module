# Writing a migration

For plugin developers; `/rr-setup --update` runs them. One module per version in
this directory, named `NNNN_slug.py`, numbered contiguously from `0001`, with
`VERSION` equal to the prefix, a one-line `TITLE`, a static `MOVES` list and
`plan(ctx)`.

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
  writer of the task's state file (`.ai/state/state.json`, `current.json` in a
  project not yet at schema 9) other than `state.py`. A migration that
  moves a path a task's step may touch must patch it, or the scope guard will
  stop that task on a file that no longer exists.
- Operations are planned, never written: the dry run must list everything.
  Paths are project-relative and normalised, and content is `bytes`.
- `plan(ctx)` runs again on every run until the schema version advances, and a
  conflict or an unconfirmed deletion holds it back. Every `fn` must therefore be
  idempotent: append a line only when it is not already there, or the next run
  appends it again.

## What a migration can ask the plugin

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
- `ctx.template(path)` — the bytes the plugin ships today at that path, from the
  scaffold or the shared tree. `ctx.is_shipped(path, data)` — whether these bytes
  are a version ever shipped there (CRLF counts; `index.json` alone answers).
- `ctx.require_shared(paths)` — refuse (exit 2, nothing written) when a shared
  file those copies fall back to is missing from an installed home.
  `ctx.unsafe_target(path)` — why a path must not be deleted (a symlink, or
  outside the project). `ctx.override_note(path)` — the wording for an edited
  shared copy. Words that name a runtime live in `update.py`, never in a
  migration.

A migration that edits a file **outside `.ai/`** is editing the project's own
file: `apply` copies the original to
`.ai/reports/project-update-<date>/original/<path>` before the first write, so
what was there is recoverable without git.
