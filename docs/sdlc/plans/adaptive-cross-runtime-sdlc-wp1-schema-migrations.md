# Plan: WP1 — project schema version and structural migrations in `/project-update`

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work package 1 of 7) ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp1-schema-migrations.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Risk tier **T3** (spec, "Policy conformance"). This repository has no `.ai/`, so `/ai-task`
does not apply: the main session builds one step at a time, and `ai-reviewer` on `opus` reviews
each step before its commit. Tests: each step runs the suite it names; `tests/run-all.sh` runs
once, to the end, after step 9.

## Files that change

| Path | New / edit | Why | Step |
|---|---|---|---|
| `skills/project-update/update.py` | edit | `Plan` virtual tree; `detect_version`, `SchemaError`, `MigrationContext`, `run_migrations`; `History(root, renames)`; `apply` preconditions, originals, delete gate, exit 3; `--confirm-delete`; report schema line and summary suffixes; `sys.dont_write_bytecode = True` so importing migrations never writes `__pycache__` into an installed plugin | 1, 3, 4, 5, 6 |
| `skills/project-update/migrations/__init__.py` | new | registry: `load()`, `CURRENT`, `renames()`, `template_key()`, `RETIRED`; loads `NNNN_slug.py` by path (`importlib.util.spec_from_file_location`, since the names start with digits); honours `CLAUDE_AGENTIC_MIGRATIONS` | 2 |
| `skills/project-update/migrations/0001_schema_version.py` | new | the proving migration: `VERSION = 1`, `TITLE`, `MOVES = []`, `plan(ctx)` does nothing | 2 |
| `skills/ai-init/templates/.ai/VERSION` | new | `1\n`; fresh scaffolds start current (R11) | 7 |
| `skills/ai-init/scaffold-ai.sh` | edit | **not in the spec** — copy `.ai/VERSION` only when `.ai/` did not exist before the run (see Risks, 1) | 7 |
| `skills/ai-init/templates/.ai/AGENTS.md` | edit | table row for `VERSION` (flagged concern 10) | 7 |
| `skills/ai-init/templates/.ai/state/README.md` | edit | name `update.py` `patch_state` as the second atomic writer (OQ4, flagged concern 3) | 7 |
| `skills/project-update/history/index.json`, `history/blobs/*` | rebuilt | by `tools/build-template-history.py`, after the three template edits above are committed | 7 |
| `hooks/ai-path-guard.sh` | edit | `WHY_PROTECTED` text (`:49`) names `update.py` as well as `state.py`; message only, no logic change | 7 |
| `tests/test-project-update.sh` | edit | old-template build skips `ai-init/.ai/VERSION` (step 7); new sections for R1–R15 (step 8) | 7, 8 |
| `tests/fixtures/project-update/schema-v0/` | new | overlay on the oldest-templates build: the files a pre-schema project carries. The in-flight task is created by `state.py` in the test — `ai-path-guard` refuses any other writer of `.ai/state/*.json`, fixtures included (R10, R15) | 8 |
| `tests/fixtures/project-update/migrations-synthetic/` | new | `0001` create, `0002` move of an edited file whose template moves with it, `0003` policy edit + text edit + `patch_state` + proposed delete. The "next" templates are built in the test from the current ones, so the fixture satisfies R12 | 8 |
| `tests/fixtures/project-update/migrations-{invalid,badmoves,undeclared,escape,bad-content}/` | new | one registry per rejection: VERSION mismatch, a MOVES pair leaving the project, an undeclared move, an operation outside the project, content that is not bytes | 8 |
| `tests/fixtures/project-update/migrations-broken/` | new | a gap (`0001`, `0003`) and a `VERSION` mismatch, for R2 exit 2 | 8 |
| `tests/test-install-dry-run.sh` | edit | `:88-97` list gains `skills/project-update/migrations/__init__.py` and `0001_schema_version.py` | 8 |
| `tests/test-scaffold-idempotency.sh` | edit | a second `scaffold-ai.sh` run over a v0 tree does not create `.ai/VERSION` | 8 |
| `skills/project-update/SKILL.md` | edit | schema line in the dry run; `--confirm-delete NAME` is typed by the human only, never passed by the agent (OQ2); exit 3 and the re-run recovery; `migration.json` | 9 |
| `README.md` (`170-201`), `docs/faq.md` (`150-158`) | edit | update now has a schema step; `.ai/VERSION` versus `risk-tiers.json` `"version"` (flagged concern 6) | 9 |

Untouched: `install.sh` (`cp -r` of skill directories carries `migrations/` to both runtimes),
`skills/ai-status/` (R13), `skills/ai-task/state.py`.

## Order of work

One step = one commit. Each step ends green on the suite it names.

1. **Refactor only — `Plan` virtual tree.** Add `Plan.exists(target)`, `Plan.read(target)`
   (`final` first, then disk, `None` when removed or absent), `Plan.remove(target)`,
   `Plan.removed`. Route `three_way` (`update.py:210-214`), `fix_mirror` (`:269-270`),
   `block_update` (`:282-283`), `gitignore_update` (`:315-318`), the `create`-kind check in
   `build_plan` (`:349`, `:366`) and the testing.md hint (`:374-376`) through them. No
   behaviour change.
   *Proof:* `bash tests/test-project-update.sh` green, and a golden harness (scratchpad, not
   committed) that builds fixtures P, P2, P4, P5 and P3 the way the test does, captures dry-run
   output, `--apply` output, `--check` exit code and the resulting tree's `md5sum`, with the temp
   path normalised — run on `HEAD` before the edit and after it, `diff` empty.
2. **Registry.** `migrations/__init__.py` and `0001_schema_version.py`. `update.py` does not
   import it yet.
   *Proof:* `python3 -c` imports the registry by path: `CURRENT == 1`, `renames() == {}`;
   pointing `CLAUDE_AGENTIC_MIGRATIONS` at a temp dir with a gap raises `SchemaError`;
   `pylint skills/project-update/migrations` clean (see Risks, 6).
3. **Schema detection and the VERSION item (split out of the spec's step 3).**
   `detect_version`, `SchemaError`, exit 2 on unreadable or newer (R8); `build_plan` adds
   `create|update .ai/VERSION "schema N [0001]"` for `v < CURRENT`; the walk skips `.ai/VERSION`;
   `schema 0 -> 1` header line; `--check` names the schema (R13); registry errors exit 2 (R2).
   `run_migrations` exists but only calls `m.plan(ctx)` with a read-only context.
   *Proof:* `bash tests/test-project-update.sh` green (existing assertions unchanged); a v0 temp
   project dry run shows the schema line and `create .ai/VERSION`; `--check` exits 1 with
   `schema 0 -> 1`.
4. **⚠ Riskiest — `MigrationContext` operations.** `create`, `move`, `edit_text`, `edit_json`
   (with `policy = leaf_changes`, R9), `patch_state` (planned only here), `delete` (listed as
   `delete?`); the idempotency table from the spec; `migration` / `src` / `reason` on items;
   `move` refuses a pair not in `MOVES`; summary suffix `N deletion(s) awaiting --confirm-delete`
   only when non-zero; the in-flight-task hint (flagged concern 9).
   Why it is riskiest: it changes what every later reader of the plan sees (`read` through
   the overlay, `removed` paths) for every project, and a mistake shows up as a silent wrong
   merge, not a crash. It sits after the byte-identical refactor and before any write-side
   change, so it can be reviewed as planning only — `apply` still ignores the new actions.
   *Proof:* `bash tests/test-project-update.sh` green; synthetic migrations (step 8's fixture,
   written now in scratchpad) dry-run lists each operation once, writes nothing (checksum).
5. **`History(root, renames)`.** `versions(key)` returns the old keys' blobs, then the new
   key's, following `registry.renames()` through `template_key` (`.ai/**` → `ai-init/.ai/**`;
   `PROJECT_INIT_MAP` / `RUNTIME_MAP` targets → `project-init/<template>`).
   *Proof:* `bash tests/test-project-update.sh` green; the synthetic edited-file move dry-runs as
   `move` + `merge "your edits kept"` (R6).
6. **Write side.** `apply(plan, confirm_delete=None)`: each item records the `sha` of what it
   read; `apply` re-checks it on disk, copies originals to
   `.ai/reports/project-update-<YYYY-MM-DD>/original/<path>` before a move or delete, performs
   `move`, runs `delete?` only with `--confirm-delete NAME`, writes `current.json` for
   `patch_state` atomically (temp + `os.replace`, `history` entry `schema_migrated`), writes
   `migration.json` only when an original was kept (OQ1), and on a violation prints the spec's
   abort line and exits 3. `--confirm-delete` without `--apply` is an argparse error.
   *Proof:* `bash tests/test-project-update.sh` green; synthetic fixture applies, a second
   `--apply` prints `0 automatic`; a run killed after the first move (inject via a synthetic
   migration whose second op targets a read-only dir) aborts with exit 3 and the next run
   completes (R5).
7. **Templates and history.** Commit A: `templates/.ai/VERSION`, `scaffold-ai.sh` guard,
   `.ai/AGENTS.md` row, state README note, `ai-path-guard.sh` message, test's old-template build
   skips `ai-init/.ai/VERSION`. Commit B: `python3 tools/build-template-history.py` (it reads
   committed trees, so it must run after commit A) and the rebuilt index.
   *Proof:* `bash tests/test-project-update.sh` (P3 fresh project `0 automatic, 0 conflict`;
   history covers every template), `bash tests/test-scaffold-idempotency.sh`,
   `bash tests/test-ai-path-guard.sh`.
8. **Tests.** New sections in `test-project-update.sh` for R1, R2, R5, R8, R10, R12, R13, R14,
   R15, plus R3/R4/R6/R7/R9 over the synthetic fixture; the fixtures; the install dry-run list;
   the scaffold idempotency case.
   *Proof:* `bash tests/test-project-update.sh`, `bash tests/test-install-dry-run.sh`.
9. **Docs.** `SKILL.md`, README, FAQ.
   *Proof:* `grep -n 'schema' skills/project-update/SKILL.md README.md docs/faq.md` shows the
   new text; then **once, to the end:** `bash tests/run-all.sh` and
   `pylint $(git ls-files '*.py')`; every failure fixed as one batch, one re-run.

## Risks

**What could this break?**

1. **`/ai-init` or `/project-init` run again on a v0 project would skip every migration.**
   `ai-init/SKILL.md:47` runs `scaffold-ai.sh` before `/project-update`, and `scaffold-ai.sh:58-66`
   copies every missing file — it would write `.ai/VERSION = 1` into a v0 tree, and
   `update.py` would then see the project as current. The spec does not cover this. Fix in
   step 7: `scaffold-ai.sh` copies `.ai/VERSION` only when `.ai/` did not exist at the start
   of the run. Noticed by: the new `test-scaffold-idempotency.sh` case.
2. **The oldest-templates fixture becomes v1.** Once `ai-init/.ai/VERSION` is in the history,
   `versions[0]` puts it into `$OLD`, and every existing section (P, P2, P4, P5) is scaffolded
   at schema 1 — the v0 path would never be tested. Step 7 makes the old build skip that key
   (flagged concern 7, R15).
3. **History rebuild order.** `build-template-history.py` reads `git rev-list`/`ls-tree`, so a
   template edited but not committed is missing from the index and the "history covers every
   current template" check fails. All three template edits land in commit A, the rebuild in
   commit B.
4. **Silent wrong merge through the overlay (step 4).** A reader that still opens the disk
   directly would merge against pre-migration content. Step 1 removes every direct read in the
   planning path; the reviewer checks with `grep -n 'os.path.exists\|read(os.path.join(plan.root' update.py`
   that none remain outside `Plan`.
5. **`--check` output changes for v0 projects.** Every existing v0 project reports "behind"
   once, even when its files are current. Intended (R13), but `/ai-status` and any CI that
   greps `--check` will see it; the message still starts `project is behind the installed plugin`.
6. **pylint in CI** (`.github/workflows/pylint.yml` runs over every tracked `.py`): module names
   `0001_schema_version.py` fail `invalid-name`. Add a module-level disable in each migration
   (or a `.pylintrc` pattern) in step 2, not at the end.
7. **Callers of `update.py`:** `/project-update`, `/ai-init` and `/project-init` reruns; exit
   codes 0/1/2 keep their meaning, 3 is new and only on `--apply`. `SKILL.md` must tell the
   agent what exit 3 means (step 9).
8. **Both runtimes:** installed by the same `cp -r`; R14 fixtures cover Claude-only, Codex-only
   and dual.

**Riskiest step:** step 4 (split from the spec's step 3 so detection and the VERSION item land
first; kept planning-only so the write side in step 6 is reviewed separately).

**Spec flagged concerns — disposition this plan assumes:**

| # | Disposition |
|---|---|
| 1 | Accepted: this plan is pointed at the WP1 spec explicitly |
| 2 | Accepted for WP1: no migration deletes; `SKILL.md` forbids the agent passing `--confirm-delete` (OQ2); enforcement is WP2 |
| 3 | Resolved by OQ4: state README and path-guard message amended in step 7 |
| 4 | Accepted: not transactional; preconditions + VERSION last + idempotent re-run |
| 5 | Resolved by R12 test in step 8 |
| 6 | Resolved in docs, step 9 |
| 7 | Resolved in step 7 (Risks 2) |
| 8 | Accepted for WP1; WP6 revisits |
| 9 | Hint in step 4; rule for migration authors in `SKILL.md` |
| 10 | Resolved in steps 7 and 9 |
| new | Risks 1 — `scaffold-ai.sh` guard, not in the spec |

## What changed while building it

- Step 3 absorbed three of step 7's items (`templates/.ai/VERSION`, the `scaffold-ai.sh`
  guard, the test's oldest-templates skip) plus the history rebuild: without them the
  "a fresh project is up to date" assertion fails between steps 3 and 7.
- Step 4 added a rule the spec did not have: `.ai/VERSION` is held while a migration item is
  unsettled (a conflict, or an unconfirmed `delete?`). Spec R5a.
- Step 5 turned `RETIRED` from a list into `{old key: successor | None}`, because a
  `project-init` template renamed on disk changes its history key with no project path to
  move, and a plain list would sanction the lost merge base instead of repairing it.
- Step 6 made every write atomic, mode-preserving and symlink-refusing after a review found
  that the first atomic-write attempt could be redirected through a planted `<target>.tmp`.

## Proof (tests)

All in `tests/test-project-update.sh` unless named; final gate `bash tests/run-all.sh` once.

| Req | Test / command |
|---|---|
| R1 | temp dirs: no `.ai/` + `docs/sdlc/` → no schema line, today's output; `.ai/` without VERSION → `schema 0 -> 1`; VERSION `1` → none |
| R2 | `CLAUDE_AGENTIC_MIGRATIONS=fixtures/.../migrations-broken` → exit 2; registry check that the shipped dir numbers contiguously from `0001` and `VERSION == prefix` |
| R3 | synthetic dry run lists `move`, `delete?`, `update`; tree checksum unchanged (existing pattern `:60-64`) |
| R4 | synthetic dry run: line order `schema`, migration items, `.ai/VERSION`, three-way items, managed block, `.gitignore` |
| R5 | synthetic `--apply` twice → second prints `^0 automatic`, checksum unchanged; abort case → exit 3, re-run completes |
| R6 | edited file at the old path → at the new path after apply, edit present, new template section present |
| R7 | original exists under `.ai/reports/project-update-*/original/`; `delete?` listed and file kept without the flag; with `--apply --confirm-delete tester` the file is gone and `migration.json` has `confirmed_by: tester` |
| R8 | VERSION `99` and VERSION `abc` → exit 2, checksum unchanged; `--check` prints the reason |
| R9 | `policy` lines for the `0004` edit; summary counts them; no `policy` line for `.ai/VERSION` |
| R10 | `schema-v0` fixture with `state.py init` task → apply → `python3 skills/ai-task/state.py get --root $P` exits 0; history has `schema_migrated` |
| R11 | `cmp templates/.ai/VERSION` against `CURRENT`; fresh project (P3) `^0 automatic, 0 conflict` (existing `:139`) |
| R12 | every `history/index.json` key is a current template, a `MOVES` source, or in `RETIRED` |
| R13 | v0 `--check` → exit 1, output contains `schema 0 -> 1` |
| R14 | Claude-only (P), Codex-only (P4), dual (P5) each get `.ai/VERSION` = `1`; `grep -n 'claude\|codex' migrations/0*.py` empty |
| R15 | `schema-v0/` overlay applied on the oldest-templates build; `.ai/VERSION` absent before update |
| step 1 | golden harness `diff` empty (byte-identical refactor) |
| install | `bash tests/test-install-dry-run.sh` — migrations files installed |
| lint | `pylint $(git ls-files '*.py')` |

## Rollback

- **Before merge:** each step is its own commit on `feat/wp1-schema-migrations`; revert the
  step's commit. Step 1 can stay on its own — it is a pure refactor.
- **After merge:** revert the merge commit and reinstall the plugin (`install.sh`). Projects
  already updated keep `.ai/VERSION = 1`; the pre-WP1 `update.py` never reads it and never walks
  it (it is not among its templates), so they keep working. WP1 ships no move or delete, so no
  project file was relocated; had one been, the original is under
  `.ai/reports/project-update-<date>/original/`.
- **Later caveat:** once a WP ships schema 2, reinstalling an older plugin makes `update.py`
  exit 2 on those projects (R8, by design); rollback then means reinstalling the newer plugin,
  not editing `.ai/VERSION` by hand.
