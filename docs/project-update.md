# Updating a project

`npx riskrails` updates the runtime home — `~/.claude/` or `~/.codex/` — and
with it the shared tree at `<home>/riskrails/ai/`. A project does not copy the
shared files; it reads them from there. What a project owns stays in the
project and is brought up to the installed plugin with one command:

```bash
/rr-setup --update        # dry run, confirm the policy changes, apply, merge conflicts
```

Under the skill it is `skills/project-update/update.py <root>` (dry run),
`--apply`, and `--check` to see whether the project is behind. `/rr-status`
says so too, and `update.py --check --budget` exits 1 when a root instruction
file is over its byte budget.

## Shared files and project-owned files

The shared tree holds the policies, agent contracts, workflows and templates
that are the same in every project (31 files on 2026-10-30). A project reads
`<home>/riskrails/ai/<path>` unless it has a regular file at the same path
under `.ai/`, which then **overrides** the shared one and stops receiving its
changes; `<home>/riskrails/ai-path <path>` prints the copy that applies. What a
project owns:

| Project-owned | What it is |
|---|---|
| `.ai/project/*.md` | the knowledge base `/rr-setup` surveyed |
| `.ai/policies/weight.json`, `weight.md` | the weight table and its generated mirror |
| `.ai/policies/dialog.json` | the dialog switch |
| `.ai/policies/path-guard.json` | the project's additions to the path guard |
| `.ai/policies/testing.md`, `coding.md`, `safety.md`, `security.md` | the project's own rules and the Verification commands |
| `.ai/policies/memory.json` | present once a human ran `state.py memory enable` |
| `.ai/AGENTS.md`, `.ai/rules/`, `.ai/VERSION` | the router, the scoped rules, the schema number |
| `.ai/state/`, `.ai/reports/`, `.ai/memory/` | the task in flight, the closed tasks, the compact record |
| `docs/sdlc/`, the managed block in `CLAUDE.md` / `AGENTS.md` | the SDLC artefacts, the always-loaded rules |

The plugin ships every version of every project-owned template it has ever
installed (`skills/project-update/history/`, built from git by
`tools/build-template-history.py`; the shared files keep only their hashes
there). That is how the update tells files apart.

## How a file is updated

| The project file is | What happens |
|---|---|
| missing | created |
| a version the plugin once shipped | replaced — nobody edited it |
| edited, markdown | three-way merged against the closest shipped version; every edit kept |
| edited, JSON policy | merged key by key; the project's value wins wherever both changed; the changes are listed per key and need a confirmation |
| edited where the plugin changed the same lines | left alone; the plugin's version goes to `.ai/local/plugin-update/` for a merge by hand |
| `.ai/project/**`, `CLAUDE.md` outside the block, `.claude/settings.json` | never touched |
| moved by a migration | moved, with your edits merged at the new path; the original kept under `.ai/reports/project-update-<date>/` |
| proposed for deletion by a migration | listed as `delete?` and left alone until a human runs `update.py <root> --apply --confirm-delete <name>` in a terminal of their own |
| a shared file the plugin once shipped, unedited | `delete?` — the project reads the shared tree instead, once a human confirms |
| a shared file the project edited | kept as an override, with a hint: it no longer receives the plugin's changes, and nothing tells you when it falls behind |

A changed or non-regular file where the update expected one stops the run with
exit 3. The dry run shows every decision; `--apply` writes them. A weight
mirror that was in sync stays in sync (`state.py weight --mirror` regenerates
it); one that was already stale stays flagged.

## Schema version and migrations

`.ai/VERSION` carries the project's schema; a project initialised before the
file existed is schema 0, and the current schema is **10**. Migrations under
`skills/project-update/migrations/` run in order before anything is merged —
they move, add, edit and propose deletions, all inside the same dry run — and
the version is written last, only once they have finished. A conflict *from a
migration*, or a deletion it proposed and nobody confirmed, holds `.ai/VERSION`
where it is, and `/rr-status` keeps reporting the project as behind; an
ordinary merge conflict does not. Every migration is idempotent.

| Schema | Migration | What it does to a project | The human's part |
|---|---|---|---|
| 1 | `0001_schema_version` | writes `.ai/VERSION` | — |
| 2 | `0002_task_journal` | adds the task journal and the schema-2 state keys; backfills the journal from the old history, marked `backfilled` | — |
| 3 | `0003_context_diet` | removes the `## SDLC workflow` section from the instruction files when it matches the shipped bytes; an edited one becomes a hint, the original kept under `.ai/reports/project-update-<date>/original/` | merge an edited section by hand |
| 4 | `0004_deterministic_gates` | adds the diff, sensor and test-run state keys | — |
| 5 | `0005_runtimes_and_plans` | adds the handoff and cross-vendor-review keys | — |
| 6 | `0006_shared_files` | the router gains `## Shared files`; every unedited copy of a shared file is proposed for deletion, edited ones are reported as overrides. Deletes nothing while any installed home lacks the shared file it would fall back to, and holds the version at 5 until the deletion is confirmed | install the plugin for every runtime, commit `.ai/`, read the `delete?` list, confirm with no task in flight |
| 7 | `0007_weight_model` | creates `.ai/policies/weight.json`, carrying over the project's edits to the old risk-tier table, which is left in place; a task in flight keeps its old surface | — |
| 8 | `0008_renames` | `claude-agentic` → `riskrails` in the managed-block markers and the router's routes | — |
| 9 | `0009_state_file` | moves `.ai/state/current.json` to `.ai/state/state.json`; a `current.json` beside an existing `state.json` is a conflict | resolve that conflict if it appears |
| 10 | `0010_dialog_switch` | creates `.ai/policies/dialog.json` with the dialog on; never overwrites it | decide on the dialog (`"enabled": false` turns it off) and amend constitution C5 if you keep it |

Every machine of a team upgrades the plugin before a project at a newer schema
is committed; an older plugin refuses such a project with exit 2.

## Rolling back a migration

Commit `.ai/` before the run — the update says so when the tree is dirty —
then:

```bash
git restore --source=<commit before the migration> --staged --worktree -- .ai
```

That also reverts everything else under `.ai/` committed since. To keep
reports and project notes, restore only `.ai/VERSION`, `.ai/AGENTS.md` and the
paths `migration.json` lists, and keep the project off `--apply` until the
plugin is downgraded, because a new plugin plans the migration again. Without
a commit, the originals under `.ai/reports/project-update-<date>/original/`
bring deleted files back (`migration.json` lists them), and nothing else: write
the schema back by hand (`printf '9\n' > .ai/VERSION`), or an older plugin
refuses the project. Roll projects back before installing a plugin older than
the shared tree.

## Adopting another AI tool's layout

A project that already carries another tool's structure — Spec Kit
(`.specify/`, `specs/`), Kiro (`.kiro/`), Cursor (`.cursorrules`,
`.cursor/rules/`), Copilot (`.github/copilot-instructions.md`), AI-DLC, or a
`CLAUDE.md` / `AGENTS.md` too large to load on every turn — is adopted with:

```bash
/rr-setup --adopt         # dry run: every file mapped through adopt-map.json, nothing written
```

The dry run maps every file through `skills/project-update/adopt-map.json`;
`--adopt --diff` prints the unified diff; `--adopt --apply` moves the content
into `docs/sdlc/` and `.ai/`, keeps each original under
`.ai/reports/adopt-<date>/original/`, records the decisions in
`decisions.json`, and passes two checks on disk: no line lost (normalised —
blank lines and bare headings ignored, whitespace, list markers and case
folded; a rewritten line must appear in the "dropped / rewritten because …"
list), and no reference left pointing at an old path. A file no row maps stops
the run until a human decides. `--mode coexist` leaves the files where they
are and only routes to them; `--tool` limits the run to the tools named;
`--split proposal|fallback` handles an oversized instruction file. The foreign
files are deleted by a separate `--adopt --cleanup`, on a committed tree, and
only with `--apply --confirm-delete <name>` typed by a human in a terminal
outside Claude Code or Codex. `/rr-status` says when a structure is waiting,
or came back after an adopt.

The same flag reads the project's **own** toolbox — its skills, hooks, agents
and scripts — into `.ai/policies/toolbox.md` and router rows in
`.ai/AGENTS.md`, so the pipeline uses them instead of walking around them.
