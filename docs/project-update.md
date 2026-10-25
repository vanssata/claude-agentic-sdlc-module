# Updating a project

How `/project-update` brings a project's `.ai/` tree, managed block and SDLC
templates up to date with the installed plugin, how migrations run, how to roll
one back, and how `--adopt` moves another AI tool's layout in.

## Shared files and project-owned files

`install.sh` updates `~/.claude/` (or `~/.codex/`), and with it the shared
tree at `<home>/claude-agentic/ai/`: the 29 policies, agent contracts,
workflows and templates that are the same in every project. A project does not
copy them; it reads them from there, and a file at the same path under `.ai/`
wins as an **override**. `<home>/claude-agentic/ai-path <path>` prints which one
applies. What a project owns stays in the project — `.ai/project/`, `rules/`,
`state/`, `reports/`, `VERSION`, `AGENTS.md`, and the policies `risk-tiers.json`,
`risk-tiers.md`, `path-guard.json`, `testing.md`, `coding.md`, `safety.md` and
`security.md` — together with `docs/sdlc/` and the `CLAUDE.md` block. Those are
copies, and stay as they were. Pull the new ones in with:

```bash
/project-update          # dry run, confirm the policy changes, apply, merge conflicts
```

Running `/ai-init` or `/project-init` again in an initialised project does the
same. `/ai-status` says when a project is behind.

## How a file is updated

The plugin ships every version of every project-owned template it has ever
installed (`skills/project-update/history/`, built from git by
`tools/build-template-history.py`; the shared files keep only their hashes,
since nothing is merged into them any more). That is how the update tells files
apart:

| The project file is | What happens |
|---|---|
| missing | created |
| a version the plugin once shipped | replaced — nobody edited it |
| edited, markdown | three-way merged against the closest shipped version; every edit kept |
| edited, JSON policy | merged key by key; the project's value wins wherever both changed |
| edited where the plugin changed the same lines | left alone; the plugin's version goes to `.ai/local/plugin-update/` for a merge |
| `.ai/project/**`, `CLAUDE.md` outside the block, `.claude/settings.json` | never touched |
| moved by a migration | moved, with your edits merged at the new path; the original kept under `.ai/reports/project-update-<date>/` |
| proposed for deletion by a migration | listed as `delete?` and left alone until a human passes `--apply --confirm-delete NAME` |
| a shared file the plugin once shipped, unedited | `delete?` (`[0006]` during the migration, `[shared]` afterwards) — the project reads the shared tree instead, once a human confirms |
| a shared file the project edited | kept as an override, with a hint: it no longer receives the plugin's changes, and nothing tells you when it falls behind |

## Schema version and migrations

The tree also carries a schema version in `.ai/VERSION`; the current one is
**6** (the shared files: `.ai/AGENTS.md` gains a `## Shared files` section
first, then every unedited copy of a shared file is proposed for deletion,
edited ones are reported as overrides), and a project initialised before the
version existed is schema 0. Migration 0006 deletes nothing while any installed
home (`~/.claude`, `~/.codex`) lacks the shared file it would fall back to — it
exits 2 and asks for `install.sh` — and holds `.ai/VERSION` at 5 until the
deletion is confirmed. Every machine of a team upgrades the plugin before a
project at schema 6 is committed; an older plugin refuses it. Migrations under
`skills/project-update/migrations/` run in order before anything is merged —
they move, add, edit and propose deletions, all inside the same dry run — and
the version is written last, only once they are finished.

Changes to `.ai/policies/*.json` are listed per key and need a confirmation
before they are applied. A risk-tier mirror that was in sync stays in sync; one
that was already stale stays flagged. Nothing is deleted, and no version is
advanced, without the migration that asked for it finishing: a conflict *from a
migration*, or a deletion it proposed and nobody confirmed, holds `.ai/VERSION`
where it is, and `/ai-status` keeps reporting the project as behind. An ordinary
merge conflict does not.

Changed a template? Run `tools/build-template-history.py` and commit the result;
the test suite fails until you do.

## Rolling back migration 0006

**Rolling back 0006 is git first.** Commit `.ai/` before the run (the update
says so when it is dirty), then:

```bash
git restore --source=<commit before the migration> --staged --worktree -- .ai
```

That also reverts everything else under `.ai/` committed since — reports,
project notes. To keep them, restore only `.ai/VERSION`, `.ai/AGENTS.md` and the
paths `migration.json` lists.

and keep the project off `/project-update --apply` until the plugin is
downgraded, because a new plugin plans 0006 again. Without a commit, the
originals under `.ai/reports/project-update-<date>/original/` bring the deleted
files back (`migration.json` lists them), and nothing else: write the schema
back by hand with `printf '5\n' > .ai/VERSION`, or an older plugin refuses the
project (exit 2). The router keeps its new section, which stays true while the
copies exist. Roll projects back before installing a plugin older than the
shared tree.

## Adopting another AI tool's layout

A project that already carries another AI tool's structure — Spec Kit
(`.specify/`, `specs/`), Kiro (`.kiro/`), Cursor (`.cursorrules`,
`.cursor/rules/`), Copilot (`.github/copilot-instructions.md`), AI-DLC, or a
`CLAUDE.md`/`AGENTS.md` too large to load on every turn — is adopted with
`/project-update --adopt`. The dry run maps every file through
`skills/project-update/adopt-map.json` and writes nothing; `--apply` moves the
content into `docs/sdlc/` and `.ai/`, keeps each original under
`.ai/reports/adopt-<date>/original/`, and passes two checks on disk: no line
lost, no reference left pointing at an old path. A file no row maps stops the
run until a human decides. `--mode coexist` leaves the files where they are and
only routes to them. The foreign files are deleted by a separate
`--adopt --cleanup`, on a committed tree, and only with `--apply
--confirm-delete NAME` typed by a human in a terminal outside Claude Code or
Codex. `/ai-status` says when a structure is
waiting, or came back after an adopt.
