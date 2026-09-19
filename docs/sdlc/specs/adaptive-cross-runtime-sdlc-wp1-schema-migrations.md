# Spec: WP1 — project schema version and structural migrations in `/project-update`

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work package 1 of 7)

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Scope: the mechanism that lets every later work package reach projects initialised
before it — a schema version in `.ai/VERSION`, ordered idempotent migrations run by
`update.py` before the three-way merge, and template history that follows a moved file.
WP1 ships one migration (`0001`, which only records the version). Content migrations
(questions/handoff/events files, stub instruction files, diff budgets, scopes) belong to
their own packages; `--adopt` is WP6 and builds on the primitives defined here.

Design produced by the `architect` agent (2026-09-20); file:line references are to the
tree at `ff558e8`.

## Current state (verified)

- `update.py` builds a `Plan` of `{action, target, note, content, conflict_copy, policy}`
  items (`update.py:189-200`) and `apply()` writes them one after another, with no
  preconditions and no atomicity (`update.py:391-402`).
- `build_plan` walks only the *current* templates (`update.py:359-369`). A renamed template
  therefore orphans the project's old file and creates a fresh new one; the user's edits
  never reach the merge.
- `three_way` and `block_update` read the disk directly (`update.py:211-214`, `282-283`); only
  `gitignore_update` consults the plan first (`update.py:316-318`).
- `history/index.json` is `{ "<set>/<rel>": [sha, ...] }` with 65 keys, all still present in
  the templates: no rename has ever been tracked.
- The test rebuilds "oldest templates" from `versions[0]` of every key
  (`tests/test-project-update.sh:30-40`) and asserts the summary lines `^0 automatic, 1 conflict`
  and `^0 automatic, 0 conflict` (`:97`, `:126`, `:139`).
- `install.sh:390-404` copies skill directories whole, so a new `migrations/` directory ships
  to both runtimes without installer changes.
- `templates/.ai/policies/risk-tiers.json:3` has `"version": 2`, a per-file content version
  unrelated to the tree schema.

## Requirements

| # | Requirement (testable) | Intent outcome |
|---|---|---|
| R1 | `detect_version(root)` returns `None` when `.ai/` is absent, `0` when `.ai/` exists without `.ai/VERSION`, else the integer in the file. A docs/sdlc-only project behaves as today and runs no migrations. | Existing projects: "a project carries a schema version"; decision 7 |
| R2 | Migrations are discovered from `skills/project-update/migrations/NNNN_slug.py`, numbered contiguously from `0001`, with `module.VERSION == NNNN`. A gap, duplicate or mismatch fails a test and makes `update.py` exit 2. | "ordered" migrations |
| R3 | The dry run lists every migration operation as a plan line and writes nothing; the existing checksum assertion stays green. | "all inside the existing dry run" |
| R4 | Plan and apply order: migration operations → `.ai/VERSION` → three-way merge → managed block → `.gitignore`. | "before the three-way merge" |
| R5 | A second `--apply` prints `0 automatic` and changes no file. A run interrupted after any operation completes cleanly on the next run. | "idempotent"; constraint "keeps its guarantees" |
| R6 | A file edited at an old path and moved by a migration is merged at the new path with the edit kept, because the history lookup for the new key includes the old key's blobs. | "template history follows renames" |
| R7 | `move` keeps a copy of the source under `.ai/reports/project-update-<YYYY-MM-DD>/original/<path>`. `delete` is only listed (`delete?`) unless `--apply --confirm-delete NAME` is given; who and when are then recorded in `migration.json`. | "nothing deleted without approval"; base for adopt's gated cleanup |
| R8 | A `.ai/VERSION` newer than the plugin's `CURRENT`, or unreadable, exits 2 having written nothing; `--check` says why. | keeps `project-update`'s guarantees |
| R9 | A migration's change to `.ai/policies/*.json` produces `policy` lines (via `leaf_changes`) and counts in "policy change(s) to confirm"; the VERSION write does not. | policy files stay human-confirmed |
| R10 | With a task in flight, migrations see the parsed `current.json` and may change it only through `ctx.patch_state(fn)`, which writes atomically and records `schema_migrated`. A v0 fixture with an in-flight task updates and `state.py get` still parses. | "a task in flight survives a schema migration with defaults" |
| R11 | `templates/.ai/VERSION` equals `CURRENT`; a freshly scaffolded project reports `0 automatic`. | fresh and old projects converge |
| R12 | Every key in `history/index.json` is a current template, the source of some migration's `MOVES`, or listed in `RETIRED`; otherwise the test fails. | closes the silent-orphan gap |
| R13 | `--check` exits 1 for a pending migration and names it (`schema 0 -> 1`); `/ai-status` needs no change. | existing projects can see they are behind |
| R14 | Claude-only, Codex-only and dual-runtime fixtures receive `.ai/VERSION` identically; migrations contain no runtime branch. | both runtimes at parity |
| R15 | `tests/fixtures/project-update/schema-v<N>/` is an overlay on the "oldest templates" build; `schema-v0` ships with WP1. | "every migration gets a fixture" |

## Design

### Components

| Component | Responsibility | Interface |
|---|---|---|
| `migrations/__init__.py` (registry) | Discover, validate, order modules; derive the rename map | `load()`, `CURRENT`, `renames()`, `template_key(target)`, `RETIRED` |
| `migrations/0001_schema_version.py` | Proving migration: no operations; the framework's VERSION write is its whole effect | `VERSION=1`, `TITLE`, `MOVES=[]`, `plan(ctx)` |
| `update.py: detect_version` | R1, R8 | `detect_version(root) -> None \| int`, raises `SchemaError` |
| `update.py: MigrationContext` | Overlay-aware reads and operation recording for one migration | see Interfaces |
| `update.py: run_migrations` | Run `v < m.VERSION <= CURRENT`, append the VERSION item, tag every item with its migration | `run_migrations(plan, root, state)` |
| `update.py: Plan` (extended) | The virtual tree: content overlay plus removals; every reader goes through it | `exists`, `read`, `remove`, `final`, `removed`, `report_dir` |
| `update.py: History` (extended) | Version lookup that follows the rename chain | `History(root, renames)`, `versions(key)` |
| `update.py: apply` (extended) | Preconditions, originals, delete gate, abort | `apply(plan, confirm_delete=None)`, exit 3 on abort |
| `templates/.ai/VERSION` | Fresh scaffolds start current | `1\n` |

A migration module is shaped like a Doctrine migration — numbered, it records operations
against a schema object — without a `down()`: the originals under `.ai/reports/.../original/`
are the way back.

### Data flow

```
main ─► detect_version(root) ─► None → today's branch (docs/sdlc only, or exit 2)
                                int  → registry.load(); v > CURRENT → exit 2
build_plan:
  1. state = parsed .ai/state/current.json or None (read only)
  2. for m with v < m.VERSION <= CURRENT:
        m.plan(MigrationContext(plan, m))      # items, plan.final, plan.removed
  3. add create|update .ai/VERSION "schema CURRENT"  (only if v < CURRENT)
  4. template walk (skips .ai/VERSION, owned by step 3);
     three_way / block_update / gitignore_update read through plan.exists / plan.read;
     History(HISTORY, registry.renames()) supplies the chain for moved keys
report ─► "schema" header, items, hints, summary
apply  ─► per item: precondition → original copy → write / move; violation → exit 3
```

**Version 0 versus not initialised.** `.ai/` absent means not initialised (unchanged: exit 2
unless `docs/sdlc/` exists). `.ai/` present without `VERSION` is version 0 — the state of
every project scaffolded before WP1. No marker is needed: `scaffold-ai.sh` always creates
the whole tree.

**Merge after a move.** `move(src, dst)` sets `plan.final[dst] = read(src)` and removes `src`
from the virtual tree. When the walk reaches the template at `dst`, "ours" is the user's old
file and `history.versions(key(dst))` returns the old key's blobs followed by the new key's,
so the closest base is found and `git merge-file` keeps the edit. The chain is derived from
`MOVES` through `template_key`: `.ai/**` → `ai-init/.ai/**`; targets in
`PROJECT_INIT_MAP` / `RUNTIME_MAP` (`update.py:44-56`) → `project-init/<template>`; anything
else has no history. `ctx.move` refuses a pair not declared in the module's `MOVES`.

**Policy confirmation.** `ctx.edit_json(".ai/policies/x.json", fn)` emits an `update` item
with `policy = leaf_changes(before, after)` (`update.py:165-185`). The later merge sees the
migrated content as "ours"; both items are listed, and the later write was computed from the
overlay. `SKILL.md` step 3 needs no new logic.

**Failure and idempotency.** Every operation is idempotent:

| Operation | Target state | Result |
|---|---|---|
| `create` | target exists | skipped |
| `move` | `src` absent | skipped |
| `move` | `src` and `dst` equal (crash between write and remove) | finished silently |
| `move` | `src` and `dst` differ | `conflict` item |
| `edit_*` | `fn` returns its input | no-op |
| `delete` | target absent | skipped |

The VERSION write is the last migration item, so an abort leaves the version unchanged and
the next run re-plans from disk. `apply` re-checks each precondition on disk, copies
originals first, and on a violation prints
`project-update: aborted at <action> <target>: <why> — nothing after it was written; run the dry run again`
and exits 3. There is no rollback: originals plus idempotent operations make a re-run the
recovery.

### Alternatives rejected

- **A rename table in `history/index.json` or `history/renames.json`, written by
  `build-template-history.py`.** The test iterates the index as `key → versions` and splits
  on `/` (`tests/test-project-update.sh:35-39`), and a table next to `MOVES` is a second
  source of truth that drifts.
- **Renames derived from `git log --follow -M`.** Similarity heuristics miss a rename with a
  rewrite, cannot express a split, and a rename without a migration must fail a test (R12),
  not be tracked silently.
- **One `migrate.py` with an `if version < N:` chain.** One module per version gives
  ordering, per-version fixtures and `MOVES` for free.
- **A `.ai/VERSION` template picked up by the three-way walk.** It would mark a v0 project
  current without running its migrations; VERSION must be owned by the migration step and
  excluded from the walk.
- **Reusing `"version"` in `risk-tiers.json`.** That file is human-owned policy that needs
  confirmation and may be in conflict; the user chose `.ai/VERSION`.

## Interfaces

### `.ai/VERSION`

One line: a decimal integer and LF, e.g. `1\n`. Parsed with `re.fullmatch(r"\d+", text.strip())`;
anything else raises `SchemaError(".ai/VERSION is not a schema number: <repr>")`.

### Migration module

```python
VERSION = 1                                         # equals the NNNN prefix
TITLE = "record the schema version in .ai/VERSION"  # one line, shown in the dry run
MOVES: list[tuple[str, str]] = []                   # project-relative (src, dst); static
def plan(ctx: "MigrationContext") -> None: ...
```

`MigrationContext`

- read side, overlay-aware: `exists(path) -> bool`, `read(path) -> bytes | None`,
  `read_json(path) -> Any | None`, `state: dict | None`, `runtimes: list[str]`,
  `version_from: int`, `root: str`;
- operations, each recording into the plan: `create(path, content: bytes)`, `move(src, dst)`,
  `edit_text(path, fn: bytes -> bytes)`, `edit_json(path, fn: obj -> obj)`,
  `patch_state(fn: dict -> dict)`, `delete(path, reason: str)`.

Registry: `load() -> list[module]` (raises `SchemaError` on gap, duplicate or mismatch),
`CURRENT: int` (0 when empty), `renames() -> dict[str, list[str]]`, `RETIRED: list[str]`,
directory `os.environ.get("CLAUDE_AGENTIC_MIGRATIONS", <skill>/migrations)` so tests can
supply synthetic migrations.

### Plan items

`action ∈ {create, update, merge, conflict, move, delete?}`; new fields
`migration: int | None`, `src: str | None` (move), `reason: str | None` (delete).
`Plan.report_dir = ".ai/reports/project-update-<YYYY-MM-DD>"`, created only when an original
is written.

### CLI

Flags: `--apply`, `--check` (existing); `--confirm-delete NAME` (new, only with `--apply`).
Exit codes: 0 ok; 1 behind (`--check`); 2 not a project, templates missing, VERSION
unreadable or newer, registry invalid; 3 apply aborted.

Dry run (same `%-9s %-*s  %s` layout as today):

```
project-update: /path (dry run, nothing written; --apply to write)
  schema    0 -> 1  (1 migration: 0001 record the schema version in .ai/VERSION)
  create    .ai/VERSION                schema 1 [0001]
  move      .ai/old.md -> .ai/new.md   [0002] original kept under .ai/reports/project-update-2026-09-20/original/
  delete?   .ai/foo.md                 [0003] <reason>; needs --apply --confirm-delete NAME
  ...existing lines...
3 automatic, 0 conflict(s), 2 policy change(s) to confirm, 1 deletion(s) awaiting --confirm-delete
```

Suffixes appear only when non-zero, so the existing summary assertions hold. `--check`:
`project is behind the installed plugin: schema 0 -> 1, 3 file(s) to update — run /project-update`.

### `migration.json` (in `report_dir`, only when originals were written)

```json
{"from": 0, "to": 3, "applied_at": "<UTC>",
 "ops": [{"action": "move", "src": "...", "dst": "...", "migration": 2}],
 "deletions": [{"path": "...", "confirmed_by": "NAME", "at": "<UTC>"}]}
```

### `history/index.json`

Unchanged. Rename knowledge lives in `MOVES`; `History(root, renames)` reads it at lookup.

## Implementation order

Each step is its own `/ai-task` step with the files it may touch; step 1 is a pure
refactor and lands green before any feature.

1. **Refactor only:** `Plan.exists / read / remove`; route `three_way`, `block_update`,
   `gitignore_update` and the testing.md hint (`update.py:374-376`) through them.
   Proof: `tests/run-all.sh` green, `test-project-update.sh` output byte-identical.
2. Registry `migrations/__init__.py` and `0001_schema_version.py`.
3. `detect_version`, `MigrationContext` and its operations, `run_migrations`, VERSION excluded
   from the walk, the `schema` line and summary suffixes.
4. `History(root, renames)` chain lookup.
5. `apply` preconditions, originals, `--confirm-delete`, exit 3, `migration.json`.
6. `templates/.ai/VERSION`, the `.ai/AGENTS.md` template table row, rebuilt history index.
7. Tests: R1, R5, R8, R10, R12–R15 in `test-project-update.sh`;
   `tests/fixtures/project-update/schema-v0/`, `tests/fixtures/project-update/migrations-synthetic/`
   (a move, an edited-file move, a delete, a policy edit, a `patch_state`);
   `migrations/__init__.py` added to `test-install-dry-run.sh:88-97`.
8. Docs: `skills/project-update/SKILL.md` (schema line, `--confirm-delete` typed by the human
   only, report), README `170-201`, `docs/faq.md:150-158`, state README note on `patch_state`.

## Policy conformance

- **Global `~/.claude/CLAUDE.md`, "deterministic tools first":** migrations are Python standard
  library plus `git merge-file`, as today; no model call inside `update.py`.
- **"Never mix a refactoring with a feature change":** implementation step 1 is a separate,
  byte-identical refactor.
- **"Legacy behaviour without a test gets a characterization test first":** the existing
  `test-project-update.sh` assertions are kept unchanged and act as the characterization of
  today's output; step 1 must leave them byte-identical.
- **"Tests run once, to the end, failures fixed as one batch":** verification is
  `tests/run-all.sh` once after the last step.
- **"No agent commits, merges or deploys" / nothing deleted without approval (user decision,
  memory `adopt-migrate-default`):** `delete` never runs without `--confirm-delete NAME`;
  moves keep originals; nothing is committed.
- **Plugin-owned files change only via the skills (memory `plugin-owned-files-via-skills`):**
  the only writer is `update.py`, invoked by `/project-update` (and by `/ai-init`,
  `/project-init` when run again).
- **`project-update` guarantees (`skills/project-update/SKILL.md`):** dry run first, untouched
  replaced, edited three-way merged, conflicts never overwritten (a diverged move becomes a
  `conflict`), policy JSON confirmed (R9), a task in flight asked about first (unchanged
  step 1), project-owned paths untouched.
- **Both runtimes at parity:** one `update.py`, installed by `cp -r` for both; R14.
- **Risk tier:** WP1 changes the update engine that writes into every user project → T3
  (full pipeline, `opus` review). Deletion support is inert in WP1 (no migration deletes), so
  it does not raise the tier; the first migration that deletes does.
- **Decision 7 (`.ai/VERSION`, missing = 0):** R1, Interfaces.

## Flagged concerns

1. **The skill writes one spec per intent; this intent needs seven.** This spec takes the
   intent slug plus `-wp1-schema-migrations`. `/sdlc-plan` must be pointed at this file
   explicitly. Alternative: split the intent into seven intents — not done, to keep the
   decisions in one place.
2. **Policy JSON and deletion gates are only as strong as the skill text.** The path guard
   inspects the Bash command text, not what `update.py` writes (`hooks/ai-path-guard.sh:102-111`);
   confirmation of policy changes lives in `SKILL.md:44-54`, and `--apply` in `$ARGUMENTS`
   skips it (`:53-54`). `--confirm-delete NAME` has the same weakness: an agent could pass
   it. The intent's decision 8 (approval outside the agent) is not enforced by WP1. It
   becomes enforceable when WP2 settles open question 2 of the intent; until then, no
   migration may delete (so the gap is inert).
3. **A second sanctioned writer of task state.** `templates/.ai/state/README.md:3-4` and
   `ai-path-guard.sh:48-49` say only `state.py` writes state; `patch_state` in `update.py`
   contradicts that. Both texts must be amended when the first migration uses it. The
   alternative, a `state.py migrate` subcommand, adds a runtime dependency across skills.
4. **`apply()` is already non-atomic** (`update.py:391-402`): a crash today leaves a
   half-updated tree. WP1 improves this (preconditions, VERSION last, idempotent re-run) but
   does not make it transactional.
5. **Silent orphaning exists today** (`update.py:359-369`): any template renamed before WP1
   lands would already have lost edits. None has been (all 65 keys current), and R12 prevents
   it from now on.
6. **Two meanings of "version".** `risk-tiers.json` `"version": 2` is a per-file content
   version; `.ai/VERSION` is the tree schema. Documentation must name the difference.
7. **Fixture construction will break after the first real rename.** The test builds v0 from
   `versions[0]` of every key (`tests/test-project-update.sh:30-40`), so both old and new
   paths would appear; the `schema-v0` overlay must remove the destination path (R15).
8. **Originals under `.ai/reports/` are committed** (the `.gitignore` snippet ignores only
   `.ai/state/*.json` and `.ai/local/`). A large move could bloat the repository. Accepted
   for WP1 because they are written only on move or delete; WP6 (`adopt`) must revisit the
   size of what it keeps.
9. **A move of a path named in `approved_plan.steps[].allowed_files` would break the scope
   guard mid-task.** Rule for migration authors: such a migration must `patch_state` the
   paths; WP1 prints a hint when a task is in flight and a migration is pending.
10. **Documentation is stale after WP1:** README `183-201`, `docs/faq.md:150-158` and the
    `.ai/AGENTS.md` template table (`25-33`) describe the update without a schema.

## Open questions

Questions 1–4 were answered by the user on 2026-09-20; the spec's defaults stand.

| # | Question | Decision |
|---|---|---|
| 1 | Report directory for a version-only migration? | No — `report_dir` is written only when an original is kept |
| 2 | May the agent pass `--confirm-delete`? | The CLI accepts it; `SKILL.md` forbids the agent from passing it; enforcement comes with WP2 (intent OQ2) |
| 3 | Schema and migrations for docs/sdlc-only projects (no `.ai/`)? | None; behaviour unchanged |
| 4 | Who patches task state during a migration? | `update.py`, same atomic write as `state.py:101-109`, history entry `schema_migrated`; the state README and `ai-path-guard.sh:48-49` are amended to name it |

Still open: intent OQ1 (Codex picker and session-start hook) — not relevant to WP1, owner: WP2 spec.
