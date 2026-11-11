# Plan: Small OOP modules — WP4, `memory_sync.py` becomes the validator entry and sibling `memory_*` modules

Spec: `docs/sdlc/specs/small-oop-modules.md` (§Work packages row 4: "modules beside
`memory_store`, `memory_compact`, `memory_format`"; R1–R16 read for `memory_sync.py`, R13) ·
Programme: `docs/sdlc/plans/small-oop-modules.md` · Consumes: WP3 (`a4e37eb`, #71), closed ·
Written 2026-11-11. **Not started**: `state.py start` runs after the human accepts this plan
and commits it.

Kind: **refactoring** (C3) — no memory command's output, exit code or file written changes,
and the pre-push shim text written into a project's `.git/hooks/pre-push` stays byte for byte.
A bug found while moving is recorded with `state.py memory risk add` and left in place (R12).

## Weight, measured (2026-11-11, `state.py weight` over the 25 paths below, not journaled)

```
scope 2 (memory_sync.py referenced from 20 files) · behaviour 1 (hint: keyword 'workflow' in
CONTRIBUTING.md; declared 0: "every memory command's output, exit code and file written, and
the pre-push shim text, pinned by a new packages-mode golden (C3)") · reversibility 0 ·
domain 0 (declared: "the validator's entry path, shim candidates and exit codes 0/1/3
unchanged") · novelty 0 (declared: "the WP1/WP3 pattern on a third file") · coverage 1
(4 of 14 code files have a test)  →  W 4 → guarded
```

Guarded: this file is the plan the human accepts; one review on BALANCED; `verify --scope all`
(it runs e2e itself); one human stop at `/rr-ship`. Constitution cited: C1 (the golden records
today's behaviour, the two residuals below included), C2 (characterization first), C3
(refactoring, nothing mixed), C4 (files per step), C5 (commits are the human's), C6 (weighed by
effect on a user project: the one effect that could reach one is the shim's path, pinned by
D2). It runs as one task through `/rr-build-all` (`--batch`).

Spec flagged concerns that bear on WP4, as for WP3: **FC1** (scope guard vs SDLC writing — this
file was written with no task in flight), **FC8** (`NORMALISE` can hide a diff — the review
reads the list first), **FC9** (behaviour 0, large diff — the review reads the s3 diff first),
**FC11** (ROADMAP not updated). **Accepted for WP4 by Ivan Kakurov on 2026-11-11**, with the
mitigations under Risks; on the same day he chose D1 (the validator stays in `memory_sync.py`)
and D3 (a namespace of modules) over their rejected alternatives.

## What is there (KNOWN FACT, grep and `ast` 2026-11-11)

- `skills/ai-task/memory_sync.py`: 1 571 lines, 79 top-level `def`, 3 classes (`MemoryError_`,
  `MemoryConfig`, `GitTreeReader`), 2 namedtuples (`ExportResult`, `Finding`), 0 `global`.
  13 sections by comment header (`:71` configuration … `:1485` the pre-push entry).
- **Three `__file__`**: `:30` `sys.path.insert(0, dirname(abspath(__file__)))` (the shim runs it
  with `python3 -I`, which puts no script directory on `sys.path`), `:44` `VALIDATOR`
  (`../../hooks/memory-pre-push.py`), `:46` `SELF` ("the fallback validator: this module, run
  as a script").
- **Invoked by path**: `shim_candidates` (`:1011-1018`) writes `SELF`,
  `$HOME/.claude/skills/ai-task/memory_sync.py` and the Codex twin into every project's
  `.git/hooks/pre-push`; `hook_state` (`:723`) compares the installed shim with `shim_text()`.
  `:1570` `if __name__ == "__main__": sys.exit(pre_push_cli(...))`. Mode `100644` — no
  executable bit to keep (`python3 -I "$v"`).
- `:33` `from memory_compact import FsReader` (marked unused, but used at `:326`, `:791`).
  `:279` `random.SystemRandom()` — batch names cannot be seeded; the golden normalises them.
- **Importers** (R6, the generated list) —
  `hooks/memory-pre-push.py:23,28`: `memory_sync.pre_push_cli` (a git hook, not a runtime hook;
  unchanged by D1).
  `skills/ai-task/rr_state/memory_cmd.py:24-31`: `memory_modules()` lazily imports
  `memory_sync`, `memory_store`; 15 actions take it as `sync` and read 28 names
  (`load_config`, `MemoryError_`, `status_lines`, `enable`, `POLICY_REL`, `snippet_text`,
  `disable`, `export`, `record_lines`, `validate_range`, `rev`, `verify_fresh_clone`, `verify`,
  `format_finding`, `show`, `risk_add_files`, `risk_data`, `risk_close_files`,
  `standalone_risk`, `move_logs`, `migrate_apply`, `migrate_report`, `LOCAL_REL`, `MEMORY_REL`,
  `cleanup`, `restore`, `redact`, `pack`).
  `skills/ai-task/rr_state/close.py:168-171`: `memory_sync.after_close`, imported only when
  `memory.json` exists (files mode imports nothing).
  `skills/rr-setup/setup.py:503-512`: `sibling(AI_TASK, "memory_sync")` — `load_config`,
  `MemoryError_`, `DEFAULTS`; docstrings at `:443,480,497`.
  `tests/test_memory_sync.py:21`, `test_memory_store.py:21`, `test_memory_cleanup.py:20`,
  `test_memory_pre_push.py:20` (`import memory_sync as ms`): `load_config`, `export`, `crash`
  (**patched**, `test_memory_sync.py:310,326`), `subprocess` (**`ms.subprocess.run =`**,
  `test_memory_pre_push.py:279-289`), `VALIDATOR`, `SELF`, `HOOK_MARKER`, `POLICY_REL`,
  `local_path`, `validate_range`, `pack`, `cleanup_task`, `MemoryError_`.
- **By text, unchanged**: `docs/local-memory.md:227` (the shim runs `memory_sync.py` itself —
  stays true), `tests/test_setup.py:473` (an assertion message, R6: not edited),
  `tests/fixtures/state/partition.json:280,354` (`lazy` of `memory_modules` and
  `memory_after_close` — a derived field no phase-2 check reads, `grep -n lazy
  tests/test_state_layout.py` is empty; left stale, not in the files).
- **Golden**: `tests/fixtures/memory/goldens/` pins files mode only (`files-mode.txt`,
  `journal-summary.txt`, `status-py.txt`, `usage-report-task.txt`). Nothing pins packages mode
  byte for byte; the suites assert rows. WP4 needs its own (R13; the spec's note "packages mode
  `verify --fresh-clone`").
- **Installed list**: `tests/test_install_dry_run.py:405-420` names no memory module; the
  installer copies `skills/ai-task/` whole (`bin/riskrails.js:759-760`).

## Decisions taken in this plan (each from the spec, cited)

- **D1 `memory_sync.py` stays the validator: the entry and its own module** (R13: "keep the
  path of an entry invoked by path"). It keeps the docstring (plus one sentence naming the
  sibling modules, R11), the `sys.path` insert of its own directory before any sibling import,
  and the pre-push section — `_git_out`, `base_for_new_branch`, `pre_push`, `pre_push_cli`,
  `__main__` (`:1485-1571`). `hooks/memory-pre-push.py` is **not edited**: it imports
  `memory_sync.pre_push_cli` from its owner. Under 150 lines; it defines those four and
  nothing else; it re-exports nothing (Q25). *Rejected*: a 15-line entry plus a
  `memory_prepush.py` — it edits a hook shipped to every install for no gain.
- **D2 One path module.** `memory_io.py` sets `HERE = os.path.dirname(os.path.abspath(__file__))`,
  `VALIDATOR` from `HERE` by today's expression, and `SELF = os.path.join(HERE,
  "memory_sync.py")` — the entry's path, as today. It is the only `__file__` under the new
  modules (the entry's `sys.path` line is the other one, D1). If `SELF` pointed at
  `memory_io.py`, every new shim would `exec` a module with no `__main__` and let every push
  through unchecked, and `hook_state` would call every existing shim foreign; the golden's
  shim text (the plugin root as the exact token `<PLUGIN>`) and a layout assertion on
  `basename(SELF)` close it.
- **D3 `memory_cmd.py`**: `memory_modules()` imports, inside its one `try` (the same `die`
  text), the owner modules the commands use and returns `(mem, memory_store)`, `mem` a
  `types.SimpleNamespace` of **modules** (`mem.export.export(...)`, `mem.io.MemoryError_`).
  The action table and its signatures stay; the third argument is renamed `sync` → `mem`.
  Calls look the name up on the owner module at call time, so a test's patch reaches them.
  *Rejected*: a local `import` in each of the 15 actions — duplicated, and the presence check
  would move.
- **D4 `close.py`**: `import memory_export` in the same `try`; `memory_export.after_close`.
  **`setup.py`**: `sibling(AI_TASK, "memory_config")` and `sibling(AI_TASK, "memory_io")` in
  the same `try`; `memory_config.load_config`, `memory_config.DEFAULTS`,
  `memory_io.MemoryError_`; its three docstrings name the owner.
- **D5 Sibling imports by bare name** (`import memory_io as mio`), the precedent of
  `memory_compact` / `memory_store` (`:15`, `:14-15`): no own `sys.path` insert (the entry,
  `state.py`, `setup.sibling` and the hook put the directory there), and never `from memory_x
  import y` — `mio.crash`, `mio.subprocess`, `json.dump`, `os.replace`, `mc.FsReader` stay
  attribute lookups so the suites' patches reach them (R6).
- **D6 Classes and state**: the three classes and two namedtuples move as they are (R4; nothing
  added); no `global` (none today); the `fcntl` fallback moves with `locked` into `memory_io`.

## Module map (indicative; `tests/fixtures/memory/partition.json` from s0 is the authority)

| Layer | Module | Holds (today's lines) | ~lines | core/shell |
|---|---|---|---|---|
| 0 | `memory_io` | `HERE`, `POLICY_REL`, `MEMORY_REL`, `LOCAL_REL`, `PENDING_MAX`, `BATCH_CHARS`, `HOOK_MARKER`, `VALIDATOR`, `SELF`, `FINDINGS_MAX`, `ZERO_SHA`, `MemoryError_`, `now`, `crash`, `read_json`, `atomic_write`, `locked`, `git`, `current_branch`, `memory_dir`, `local_path`, `read_bytes` (`:25-68`, `:110-112`, `:183-241`) | 120 | shell |
| 1 | `memory_config` | `SCHEMA`, `DEFAULTS`, `author_slug`, `MemoryConfig`, `load_config`, `check_policy`, `mode_of` (`:71-180`) | 115 | core + shell |
| 1 | `memory_packages` | `load_packages`, `all_rids`, `seals_by_key`, `read_batches`, `write_batches`, `new_batch_name`, `open_batch` (`:242-310`) | 75 | shell |
| 2 | `memory_verify` | `Finding`, `kept_lines`, `check_packages`, `_belongs`, `check_journals`, `verify`, `verify_fresh_clone`, `format_finding`; `GitTreeReader`, `rev`, `policy_at`, `validate_range` (`:548-721`, `:883-1001`) | 300 | core + shell |
| 2 | `memory_hook` | `hook_state`, `hooks_path`, `shim_candidates`, `shim_text`, `shim_paths`, `snippet_text`, `install_hook`, `remove_hook`, `write_policy`, `enable`, `disable` (`:723-739`, `:1002-1111`) | 135 | core + shell |
| 2 | `memory_risks` | `risk_add_files`, `risk_close_files`, `risk_data`, `standalone_risk`, `append_entries` (`:807-882`) | 80 | shell |
| 3 | `memory_cleanup` | `cleanup_ready`, `cleanup_task`, `tree_digest`, `cleanup`, `restore`, `redact`, `pack` (`:1284-1484`) | 205 | shell |
| 3 | `memory_migrate` | `migration_plan`, `migrate_report`, `backup`, `migrate_apply`, `STUB`, `migrate_risks`, `move_logs` (`:1112-1283`) | 175 | shell |
| 4 | `memory_export` | `outbox_path`, `exportable`, `ExportResult`, `compact_for_export`, `write_outbox`, `read_outbox`, `export`, `record_lines`, `index_import`, `sealed_task_ids`, `pending_ids`, `after_close` (`:311-547`) | 240 | shell |
| 5 | `memory_status` | `status_lines`, `fts_line`, `unmigrated`, `show` (`:740-806`) | 70 | shell |
| 6 | `memory_sync` (entry) | D1: `_git_out`, `base_for_new_branch`, `pre_push`, `pre_push_cli`, `__main__` (`:1485-1571`) | 125 | shell |

The layers follow the name-level graph (`ast`, 2026-11-11): `after_close` calls `cleanup_task`
(export above cleanup); `cleanup` calls `verify`; `migrate_apply` calls `check_packages`,
`format_finding`, `append_entries`; `status_lines` calls `pending_ids` and `hook_state`;
`validate_range` calls `check_journals`/`check_packages`. No cycle on paper; s0 proves it.

## Order of work

| Step | Files | Tests (step scope) | After |
|---|---|---|---|
| s0 | new `tests/fixtures/memory/partition.json` (every top-level name of `memory_sync.py` → one module, layer, core/shell label); new `tests/test_memory_layout.py` (phase-aware partition check; import graph from the real `import` lines: no cycle, no upward edge, nothing imports `memory_sync`; no `global`; `__file__` only in `memory_io.py` and the entry's `sys.path` line; `basename(SELF) == "memory_sync.py"`; no `from memory_<x> import` / `from json import` / `from os import` in the new modules; no `import memory_sync` left in `tests/`; nothing under the new modules imports `hooks/`; sizes printed, 600 advisory) | `tests/test_memory_layout.py` | — |
| s1 | new `tests/test_memory_sync_characterization.py`, new `tests/fixtures/memory/goldens/sync/` — on a `memory_harness` git project with a bare remote: `memory enable` (stdout, exit, the written `.git/hooks/pre-push`), two light tasks closed (the export lines), `memory status`, `show` (md, `--json`), `export`, `verify --all`, `--fresh-clone`, `--range` (clean, and one tampered package → exit 1), `risk add` / `close`, `migrate` (report, `--apply --risks` on a `legacy-reports` copy; `--move-logs` from an agent session → exit 5), `cleanup`, `restore`, `redact`, `pack`, `disable`; the validator by path — `python3 -I skills/ai-task/memory_sync.py` and `hooks/memory-pre-push.py`, `--range`, `--tree`, the hook form on stdin, an unknown rev → exit 3; refusals with exit 2. After each: a listing of `.ai/memory/` and `.ai/local/memory/` (path + sha256 of the normalised content). `NORMALISE`: the scratch root, the plugin root as the exact token `<PLUGIN>`, timestamps, task ids, the period, the batch suffix, 40/64-hex shas, `in N ms`. **Its own commit, on the untouched tree**; green there, red on one deliberate edit (reverted, shown in the report) | `tests/test_memory_sync_characterization.py` | — |
| s2 ⚠ | the copy phase: new `skills/ai-task/{memory_io,memory_config,memory_packages,memory_verify,memory_hook,memory_risks,memory_cleanup,memory_migrate,memory_export,memory_status}.py`, the defs copied from `memory_sync.py` with their calls qualified by module (D5); `memory_sync.py` not edited | `tests/test_memory_layout.py`, pylint on the ten files | s0, s1 |
| s3 ⚠ | the cut-over: `skills/ai-task/memory_sync.py` shrinks to D1; the importers move to the owners — `skills/ai-task/rr_state/memory_cmd.py` (D3), `skills/ai-task/rr_state/close.py`, `skills/rr-setup/setup.py` (D4); `tests/test_memory_sync.py`, `test_memory_store.py`, `test_memory_cleanup.py`, `test_memory_pre_push.py` (import lines, qualified names, the `crash` patch and `subprocess.run` to `memory_io`); `tests/test_install_dry_run.py` (R9: `skills/ai-task/memory_sync.py`, `skills/ai-task/memory_io.py`); `tests/test_memory_layout.py` in its final phase | `tests/test_memory_sync_characterization.py`, `tests/test_memory_characterization.py`, `tests/test_memory_layout.py`, `tests/test_memory_sync.py`, `tests/test_memory_store.py`, `tests/test_memory_cleanup.py`, `tests/test_memory_pre_push.py`, `tests/test_memory_migration.py`, `tests/test_memory_risks.py`, `tests/test_memory_recall.py`, `tests/test_setup.py`, `tests/test_state_layout.py`, `tests/test_install_dry_run.py` | s2 |
| s4 | docs (R11): `docs/architecture.md` (`:19` "memory_*.py sibling modules, unchanged" becomes the map and the validator entry), `CONTRIBUTING.md` (where the memory code lives, how to run its tests) | `tests/test_instruction_budget.py` | s2 |

s0 and s1 in parallel; s3 and s4 in parallel. s2 is one implementer (ten files, ~1 450 lines,
serial by layer — a module's import of a lower one must resolve for pylint): fewer handoffs
than four layer steps chained by `after`. A test edit in s3 is import lines, qualified names
and patch targets only — never an assertion, an expected text or a fixture (R6); the
implementer's `## RESULT` says so and the review reads every test hunk first. Then
`verify --scope all` once (it runs e2e itself), fixes as one batch, one BALANCED review,
`/rr-ship`.

## Risks

- **s3 is the riskiest step** (⚠): the entry, three plugin importers and four suites change in
  one commit. It cannot move earlier (the importers have nowhere to point before s2) and is not
  split (a tree with half the importers moved has no owner for the other half). Its proof is
  the s1 golden, the files-mode golden and the ten memory suites; the review reads the s3 diff
  first.
- **The shim's path** (D2): a wrong `SELF` turns the pre-push check off in every project that
  runs `memory enable` afterwards, silently — the one effect here that would reach a user
  project's decisions (C6). Pinned three ways: the golden's shim text, `hook_state` in the
  golden's `memory status`, the layout assertion.
- **`-I` and `sys.path`**: the shim runs the entry as `python3 -I <path>`; the entry's own
  insert must come before `import memory_io`. The golden runs it exactly so; a run as `__main__`
  must never be imported a second time — nothing imports `memory_sync` (layout test).
- **A patch that stops reaching its caller**: `export` and `after_close` call `crash`; the
  interleaving test patches it (`test_memory_sync.py:326`). A module that wrote `from memory_io
  import crash` would make the crash-injection test pass for the wrong reason. D5 and the
  layout grep close it; the same for `json.dump` / `os.replace` and `subprocess.run`.
- **Files mode must stay import-free** (compact-memory R15): `close.py` imports only after the
  `memory.json` check; `memory_cmd` only inside a memory command. `memory_modules()` now imports
  ten modules where it imported two — R8 measures it.
- **A partial install's message**: `die("the memory modules are not installed beside state.py
  (%s)")` names whichever module is missing first; only a hand copy reaches it. Accepted.
- **`NORMALISE` can hide a diff** (FC8): the plugin root is an exact token, never a path
  regex — a generic one would hide a moved `SELF`. Reviewed with the golden commit.
- **The record** (`state.py recall`, 17 of 80 items): two bear on the code moved and stay as
  they are (R12), pinned by the golden — the MEDIUM residual at `memory_sync.py:375-381`
  (`export` skips every key that already has a seal) and the open risk at
  `memory_cmd.py:101-104` (`memory enable` through a pick leaves no committed record). The LOW
  residual on `tests/test_memory_sync.py:~300-337` (only the fully overlapping interleaving) is
  the test whose patch target moves; its assertions are not touched.
- **A fourth layout test** (`test_state_layout`, `test_update_layout`, now
  `test_memory_layout`, WP5 next) repeats the partition scanner. A shared helper is a separate
  refactoring (C3), not this task.

## Proof

| Req | Proof |
|---|---|
| R1 entry contract | `tests/test_memory_sync_characterization.py` green after s3, byte for byte; `tests/test_memory_characterization.py` (files mode) unchanged and green |
| R2 entry small, no re-exports | `tests/test_memory_layout.py`: entry under 150 lines, defines only D1's four, imports only `memory_io` / `memory_verify` from the siblings |
| R3, R10, R16 | `tests/test_memory_layout.py` against `partition.json` |
| R4 classes, no `global` | layout test: the three classes and two namedtuples only, no `global`, no `ABC`/`Protocol`/`staticmethod` |
| R5 golden | s1's commit: green on the untouched tree, red on one deliberate edit (shown in `task.md`) |
| R6 importers own the names | the four suites green, assertions untouched; layout test fails on `import memory_sync` in `tests/` and on `from memory_<x> import` in the modules |
| R6a one path constant | layout test: `__file__` only in `memory_io.py` and the entry's `sys.path` line; `basename(SELF) == "memory_sync.py"` |
| R7 lint | `pylint $(git ls-files '*.py')` 10.00/10 inside `verify` |
| R8 not slower | medians of 20 runs of `state.py memory status` and `python3 -I memory_sync.py --tree HEAD` on the golden project, before and after, within 10 % — in `task.md` |
| R9 installed | `tests/test_install_dry_run.py` |
| R11 docs | s4, read by the review |
| R12 risks met | `state.py memory risks` lists what s2–s3 found; no golden line edited except by `NORMALISE` |
| R14 rollback | below |
| R15 hook isolation | layout test: nothing under the new modules imports `hooks/`; `hooks/memory-pre-push.py` unchanged (`git diff --stat`) |

## Rollback

`git revert` of the task's commits restores the single file (R14); no state, schema, policy or
template changes, so nothing is migrated back. The installed copy follows with `npx riskrails`.
The golden (s1) and the partition (s0) may stay after a revert — they describe behaviour.

## Start — later, not now

```bash
$STATE start --goal "WP4: memory_sync.py becomes the pre-push validator entry and sibling memory_* modules; behaviour unchanged" \
  --workflow refactoring \
  --files "<every file of s0–s4>" --tests "<every step's tests>" \
  --declare 'behaviour=0:"refactoring: every memory command output, exit code and file written, and the pre-push shim text, pinned by a new packages-mode golden (C3)"' \
  --declare 'domain=0:"moves packages-mode memory code; the validator entry path, shim candidates and exit codes 0/1/3 unchanged"' \
  --declare 'novelty=0:"the WP1/WP3 pattern on a third file; the sibling-module pattern of memory_store/compact/format"' \
  --plan-file <scratchpad>/steps.json --batch --by "Ivan Kakurov" \
  --why "/rr-build-all docs/sdlc/plans/small-oop-modules-wp4.md"
```

`steps.json`: s0 `[]`, s1 `[]`, s2 `after [s0, s1]`, s3 `after [s2]`, s4 `after [s2]`; each
step's `tests: []` where steps would share one (a shared test serialises them), the implementer
runs its step's tests itself. Preconditions: no task in flight (`state.py status`: none on
2026-11-11), the human has committed this plan; FC1/FC8/FC9/FC11 accepted (2026-11-11).
