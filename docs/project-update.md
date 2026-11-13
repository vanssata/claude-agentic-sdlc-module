# Updating a project

`npx riskrails` updates the runtime home — `~/.claude/` or `~/.codex/` — and
with it the shared tree at `<home>/riskrails/ai/`. A project does not copy the
shared files; it reads them from there. What a project owns stays in the
project and is brought up to the installed plugin with one command:

```bash
/rr-setup --update        # dry run, apply; regenerate? and delete? rows wait for a human
```

Under the skill it is `skills/project-update/update.py <root>` (dry run),
`--apply`, and `--check` to see whether the project is behind. `/rr-status`
says so too, and `update.py --check --budget` exits 1 when a root instruction
file is over its byte budget.

## Shared files and project-owned files

The shared tree holds the policies, agent contracts, workflows and templates
that are the same in every project (25 files on 2026-11-04). A project reads
`<home>/riskrails/ai/<path>` unless it has a regular file at the same path
under `.ai/`, which then **overrides** the shared one and stops receiving its
changes; `<home>/riskrails/ai-path <path>` prints the copy that applies. What a
project owns:

| Project-owned | What it is |
|---|---|
| `.ai/project/*.md` | the knowledge base `/rr-setup` surveyed |
| `.ai/policies/weight.project.json` | the project's changes to the plugin's weight table, laid over it; `weight.md` beside it is generated |
| `.ai/policies/dialog.json` | the dialog switch |
| `.ai/policies/path-guard.json` | the project's additions to the path guard |
| `.ai/policies/verification.md` | the Verification commands, the only source of `verify_command` and the rest; kept |
| `.ai/policies/testing.md`, `coding.md`, `safety.md`, `security.md` | generated from the plugin; the project's own half of `coding.md` is the human's |
| `.ai/policies/memory.json` | present once a human ran `state.py memory enable` |
| `.ai/AGENTS.md`, `.ai/rules/`, `.ai/VERSION` | the router, the scoped rules, the schema number |
| `.ai/state/`, `.ai/reports/`, `.ai/memory/` | the task in flight, the closed tasks, the compact record; the last two are local (git-ignored) by default |
| `docs/sdlc/`, the managed block in `CLAUDE.md` / `AGENTS.md` | the SDLC artefacts, the always-loaded rules |

The plugin ships every version of every project-owned template it has ever
installed (`skills/project-update/history/`, built from git by
`tools/build-template-history.py`; the shared files keep only their hashes
there). That is how the update tells files apart.

## How a file is updated

| The project file is | What happens |
|---|---|
| missing | created |
| a version the plugin once shipped (its hash is in the history) | `regenerate` — replaced; nobody edited it |
| generated, but edited | `regenerate?` — waits for a human's `--confirm-delete`; the original is first copied to `.ai/reports/project-update-<date>/original/` |
| `weight.md` | rendered from the plugin's table with `weight.project.json` laid over it |
| a rule source `.ai/rules/<slug>.md` | `delete?` (`[rules]`): an update does not keep rule sources; confirming deletes it and its rendered blocks, and until then the rule stays rendered |
| a rendered rule file whose source is gone or no longer sets `paths:` | `delete?` (`[rules]`), once a human confirms |
| `.ai/project/**`, `.ai/reports`, `.ai/memory`, `.ai/state`, `docs/sdlc`, `verification.md`, `weight.project.json`, `dialog.json`, `CLAUDE.md` outside the block, `.claude/settings.json` | kept, never rewritten; `.ai/reports` and `.ai/memory` are local by default: the update appends their two ignore lines to `.gitignore` and prints the untrack command for files git already tracks |
| a file the update keeps but cannot read | `KEPT_UNREADABLE`, exit 6: nothing is written until it is fixed or removed |
| a shared file the plugin once shipped, unedited | `delete?` — the project reads the shared tree instead, once a human confirms |
| a shared file the project edited | kept as an override, with a hint: it no longer receives the plugin's changes, and nothing tells you when it falls behind |

A project that still carries the mixed `testing.md` and `weight.json` of a 3.x tree gets `verification.md` (the command lines of `testing.md`, verbatim) and `weight.project.json` (what its `weight.json` changed against the plugin's table) once, when they are absent. That split is the only conversion left.

Old run logs of closed tasks, and the files of abandoned or long-idle (7 days) unclosed tasks, are proposed as `[cleanup]` deletions; they never run on their own. They are settled only by `update.py <root> --apply --confirm-cleanup <name>`, typed by a human in a terminal of their own — `--confirm-delete` does not settle them. A row under git-ignored `.ai/state/` is marked "not recoverable through git".

A file under `.ai/state/` that git tracks although an ignore rule lists it gets a hint: the rule has no effect on a tracked file, so every run leaves the tree dirty. The hint prints the `git rm --cached` command that untracks it (the file stays on disk); the update itself changes nothing. Ten files get their own hint, and one more line counts the rest.

The dry run shows every decision; `--apply` writes them. `update.py` exits:

| Exit | Means |
|---|---|
| 0 | done; with `--check`, the project is current |
| 1 | `--check`: an update is pending; `--check --budget`: a root instruction file is over its budget |
| 2 | usage error (a removed flag, such as the adopt flag, also exits 2), missing templates, or an `.ai/VERSION` that cannot be read or is newer than the plugin |
| 3 | an apply aborted part-way — a changed or non-regular file where the update expected one; nothing after the failing item was written |
| 5 | refused: `--confirm-delete` or `--confirm-cleanup` without a human (`CONFIRM_REFUSED`) |
| 6 | a file the update keeps cannot be read (`KEPT_UNREADABLE`); nothing written |

## Schema version

`.ai/VERSION` carries the project's schema; the current one is **12**. riskrails
4.0 contains no migrations and reads no schema ladder. It refuses a tree that
still holds one of the old shapes it detects literally — the task-state file of
a riskrails before 3.4b without `state.json`, the risk-tier policy of one before
2.2 without a weight table, or a managed-block marker of one before 3.4b in an
instruction file — with `KEPT_UNREADABLE` (exit 6), naming the file. Any other older tree is
regenerated, and a conversion it never received (the dialog switch in `dialog.json`,
the retirement of `risk-tiers`) is simply not made. So a project last updated by a
riskrails before 3.1.0 goes through 3.1.0 first: install it
(`npx riskrails@3.1.0`), run `/rr-setup --update` with it, then install 4.0 and
run `/rr-setup --update` again, right after the install: until then the
project's old shapes (a task in the old state file, a weight without its
overlay) are not read. Every machine of a team upgrades the plugin before a
project at a newer schema is committed; an older plugin refuses such a project
with exit 2.

## Rolling back

Commit `.ai/` before the run — the update says so when the tree is dirty —
then:

```bash
git restore --source=<commit before the run> --staged --worktree -- .ai
```

That also reverts everything else under `.ai/` committed since. Without a
commit, the originals under `.ai/reports/project-update-<date>/original/`
bring replaced or deleted files back, and nothing else. From 4.2 `.ai/reports/`
is git-ignored, so those originals exist only on the machine that ran the
update. Roll projects back
before installing a plugin older than the shared tree.
