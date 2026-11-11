# Plan: Small OOP modules — WP3, `update.py` becomes an entry and `rr_update/`

Spec: `docs/sdlc/specs/small-oop-modules.md` (§Work packages row 3; R1–R16 read for `update.py`,
R13) · Programme: `docs/sdlc/plans/small-oop-modules.md` · Consumes: WP1b (`d566465`, #64/#66)
and the regenerate-not-migrate task (`66ca2b0`), both closed · Written 2026-11-11.
**Not started**: `state.py start` runs after the human accepts this plan and commits it.

Kind: **refactoring** (C3) — no flag, output line, exit code or file written changes. A bug
found while moving is recorded with `state.py memory risk add` and left in place (R12).

## Weight, measured (2026-11-11, `state.py weight`, not journaled)

```
scope 2 (update.py referenced from 245 files) · behaviour 0 (declared: "refactoring: every
flag, output line and exit code pinned by a new characterization golden (C3)") ·
reversibility 0 · domain 0 (declared: "moves the project updater's code; its confirm gate
(human_gate) and the guard's update.py spelling are unchanged") · novelty 0 (declared: "the
WP1/WP1b pattern applied to a second file") · coverage 0  →  W 2 → light
```

**Light, as measured** — Ivan Kakurov, 2026-11-11, declined raising it to guarded. **But
`start` measured again over all 33 files: W 3 → guarded** (scope unmeasured over 10 files → 1;
behaviour 1, the hint `workflow` in `CONTRIBUTING.md`; coverage 1), so the task ran guarded
with one BALANCED review (pass). Done: T-2026-11-11-1753-wp3-update-py-becomes-an, closed
2026-11-11. The open flagged concerns that bear on WP3
(FC1, FC8, FC9, FC11) were accepted by Ivan Kakurov on 2026-11-11, with the mitigations under
Risks. It runs as one task through `/rr-build-all` (`--batch`).

## What is there (KNOWN FACT, grep 2026-11-11)

- `skills/project-update/update.py`: 1 733 lines, 68 `def`, 4 classes (`SchemaError`,
  `History`, `Plan`, `Abort`), one `__file__` (`:58`, `HERE`), one process memo (`_MODULES`,
  `:432`), `sys.dont_write_bytecode = True` before its sibling import (`:57`),
  `import render_instructions` from `HERE` (`:60`), `find_block = render_instructions.find_block`
  (`:145`). Constants read from the environment at import: `TEMPLATES`, `HISTORY`, `SHARED`
  (`:76-86`).
- **Importers** (R6: the generated list) —
  `tests/test_project_update.py`: `import update` inside the `SWAP` (`:1021`) and
  `DEEP_READERS` (`:1128`) snippets — `build_plan`, `apply`, `Abort`, `check_kept`,
  `cleanup_update`, `History`, `Plan`, `SchemaError`, `task_journal`; `:180` loads the entry by
  path for its docstring (stays: the entry keeps the docstring).
  `tests/test_shared_tree.py`: `SHARED_SET` snippet (`:58`), `HELPERS` (`:67`, `import update as
  U`) — `SHARED` (read and **assigned**, `:114-119`), `HISTORY`, `History`, `unsafe_path`,
  `git_dirty_ai`, `shared_files`, `sha`, `require_shared`, `project_runtimes`, `SchemaError`.
  `tests/test_regenerate.py:41` (`load("update_under_test", UPDATE)`) — `is_kept`,
  `find_block`, `LAST_MIGRATING_VERSION`, `GENERATED`, `CREATE_ONLY`, `CREATE_ONLY_DIRS`,
  `NOT_COPIED`, `SHARED_SET`, `INSTRUCTION_FILE`, `History`, `HISTORY`.
- **By path, unchanged by this task**: `bin/riskrails.js:927` (`chmodX` of the entry),
  `hooks/guard/paths.py:46,1261,1359` (the deny texts and the `update.py --apply
  --confirm-delete` refusal — the spec's "path guard spelling unchanged"),
  `skills/ai-task/weight.py:43` (loaded by `update.py` by path through `sibling`),
  `tests/test_instruction_budget.py:109`, the CLI runs of the three suites.
- **Literal allow lists that name the file**: `tests/test_rename.py:20` (`OLD_MARKERS`) and
  `tests/test_no_fallbacks.py:131` (`claude-agentic`, `current.json`) — they follow the
  literals to the module that owns `OLD_MARKERS` / `old_shapes`.
- **Installed list**: `tests/test_install_dry_run.py:413-417` gains `rr_update/__init__.py` and
  `rr_update/cli.py` (R9); the installer copies the skill directory whole.
- No byte-level golden of `update.py`'s output exists: `tests/test_regenerate.py` asserts rows
  and file contents over `tests/fixtures/regenerate/{fresh,v3.1.0,v3.1.0-edited,dual}`.

## Decisions taken in this plan (each from the spec, cited)

- **D1 `HERE` is the one path constant** (R6a for this file). `rr_update/paths.py` sets
  `HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` — the skill directory,
  the same value as today in a checkout and an install — and it is the only `__file__` under
  `rr_update/` (layout test). It is computed, not set by the entry, because `HISTORY`,
  `TEMPLATES` and `SHARED` are import-time values today and stay so.
- **D2 Environment constants stay import-time module attributes** of `paths`, read by the code
  as `paths.SHARED` at call time, so `test_shared_tree.py`'s assignment becomes `paths.SHARED =
  …` and keeps reaching the caller (R6).
- **D3 `find_block` is not re-exported** (Q25): `blocks.py` calls `render_instructions.find_block`,
  and `tests/test_regenerate.py` imports `render_instructions` for it.
- **D4 The entry**: docstring unchanged byte for byte, `sys.dont_write_bytecode = True` and
  `sys.path.insert(0, HERE)` before any import of `rr_update` (no `__pycache__` in an install,
  R9), a missing package prints one line naming `npx riskrails` (R2), then `cli.main()`. Under
  100 lines, no re-exports.
- **D5 Classes**: the four stay as they are (`History` holds the history index, `Plan` the
  plan's invariant, two exceptions) — R4's rule, nothing added. `_MODULES` stays the one memo,
  in `siblings.py`; no `global` (layout test).

## Module map (indicative; `tests/fixtures/update/partition.json` from s0 is the authority)

| Layer | Module | Holds (today's lines) | core/shell |
|---|---|---|---|
| 0 | `paths` | `env`, `HERE`, `SKILLS`, `TEMPLATES`, `HISTORY`, `SHARED`, the file constants, `GENERATED`…`KEPT`, `is_kept`, `SHARED_SET`, `RULES_*`, `RUNTIME_MAP`, `SDLC_CREATE`, `INSTRUCTION_FILE`, `LAST_MIGRATING_VERSION`, exit constants (`:61-164`) | core + constants |
| 0 | `files` | `utc_now`, `sha`, `read`, `dump_json`, `unsafe_path`, `git_dirty_ai`, `git_states` (`:181-325`) | shell |
| 1 | `history` | `SchemaError`, `History`, `shared_files`, `undeclared_shared`, `template_version`, `project_version`, `project_runtimes` | shell |
| 1 | `gate` | `AGENT_MARKERS`, `ai_unattended`, `human_gate`, `placeholder_name`, `refuse` (`:328-378`) | shell |
| 1 | `siblings` | `_MODULES`, `sibling`, `weight_module`, `weight_overlay`, `shipped_weight` | shell |
| 2 | `kept` | `OLD_MARKERS`, `check_kept`, `old_shapes`, `kept_refusal` | shell |
| 2 | `plan` | `Plan`, `lost_lines`, `patterns_of`, `edited_note`, `regenerate` | core |
| 3 | `weights` | `effective_weight`, `weight_md`, `split_testing`, `leaves`, `split_weight`, `listed`, `unwritten`, `split_once` | core/shell |
| 3 | `blocks`, `shared`, `rules` | `block_update`; `require_shared`, `shared_update`; `rule_sources`, `rendered_rules`, `nested_tree`, `unwalked_dir`, `_frozen_block`, `rules_update` | shell |
| 3 | `cleanup` | `local_cache`, `task_journal`, `cleanup_update`, `deletion_hint`, `tracked_ignored_hint` | shell |
| 3 | `hints` | `budget_offenders`, `gitignore_update`, `budget_hints`, `constitution_hint`, `verification_hints` | core/shell |
| 4 | `build` | `PHASE`, `build_plan` | shell |
| 5 | `apply` | `Abort`, `current_sha`, `check`, `default_mode`, `write_file`, `keep_original`, `record_run`, `apply`, `apply_item`, `prune_empty` | shell |
| 6 | `report`, `cli` | `report`; `main` (parser and dispatch) | shell |

## Order of work

| Step | Files | Tests (step scope) | After |
|---|---|---|---|
| s0 | new `tests/fixtures/update/partition.json` (every top-level def and constant → one module, core/shell label, layer); new `tests/test_update_layout.py` (phase-aware partition check, import graph: no cycle, no upward edge, nothing imports `cli` or the entry; no `global`; one `__file__`, in `paths.py`; no `import update` left in `tests/`; R15 crossing; sizes printed, 600 advisory) | `tests/test_update_layout.py` | — |
| s1 | new `tests/test_update_characterization.py`, new `tests/fixtures/update/goldens/` — `--help`; dry run, `--check`, `--check --budget` on each of the four regenerate trees; `--apply` on a copy of `v3.1.0` (stdout, exit, a sha256 listing of the tree after); exits 2 (bad flags, no templates, newer `.ai/VERSION`), 5 (`--confirm-delete` from an agent session) and 6 (an unreadable kept file). `NORMALISE`: the scratch path, the date in `project-update-<date>`, timestamps — the entry path an exact token. **Its own commit, on the untouched tree.** | `tests/test_update_characterization.py` | — |
| s2 ⚠ | the copy phase: new `skills/project-update/rr_update/{__init__,paths,files,history,gate,siblings,kept,plan,weights,blocks,shared,rules,cleanup,hints,build,apply,report}.py`, the defs copied from `update.py` with their calls qualified by module (`files.sha()`, `paths.SHARED`), `json.dump` / `os.replace` kept as module attributes (R6); `update.py` not edited | `tests/test_update_layout.py`, pylint on the new files | s0, s1 |
| s3 ⚠ | the cut-over: new `rr_update/cli.py`; `skills/project-update/update.py` shrinks to the entry of D4; the importers move to the owners — `tests/test_project_update.py` (the two snippets), `tests/test_shared_tree.py` (two snippets, `paths.SHARED`), `tests/test_regenerate.py` (`:41` and the `U.` names); `tests/test_rename.py:20`, `tests/test_no_fallbacks.py:131` follow the literals; `tests/test_install_dry_run.py:413-417` (R9); `tests/test_update_layout.py` in its final phase | `tests/test_update_characterization.py`, `tests/test_update_layout.py`, `tests/test_project_update.py`, `tests/test_shared_tree.py`, `tests/test_regenerate.py`, `tests/test_rename.py`, `tests/test_no_fallbacks.py`, `tests/test_install_dry_run.py` | s2 |
| s4 | docs (R11): `docs/architecture.md`, `CONTRIBUTING.md` (where the updater's code lives), `skills/project-update/SKILL.md` only if it names internals | `tests/test_instruction_budget.py` | s3 |

s0 and s1 in parallel. s2 may split into its layers (0–1, 2–3, 4–6) for parallel implementers;
it creates files only, so the scope guard has nothing to serialise. A test edit in s3 is
import lines, qualified names and patch targets only — never an assertion, an expected text
or a fixture (R6); the implementer's `## RESULT` says so and the review reads every test hunk
first. Then `verify --scope all` once (it runs e2e itself), fixes as one batch, `/rr-ship`; a
review only if `close` reports a red fact (light).

## Risks

- **s3 is the riskiest step** (⚠): the entry, three suites and three allow lists change in one
  commit. It cannot move earlier (the importers have nowhere to point before s2), and it is not
  split: an intermediate tree with half the importers moved has no owner for the other half.
  The golden (s1) and the three suites are its proof; a review, if `close` asks for one, reads
  the cut-over diff first.
- **A moved constant read as a copy** (`from rr_update.paths import SHARED`) silently ignores
  the test's assignment — `test_shared_tree.py` would then pass against the real tree. R6's
  rule and a layout-test grep for `from rr_update.<mod> import` close it.
- **`__pycache__` in an install**: a package imported before `sys.dont_write_bytecode` writes
  `rr_update/__pycache__`. D4 orders the entry; `tests/test_install_dry_run.py` checks the list.
- **`HERE` drift** (D1): the history index, templates and the shared tree are found from it; the
  golden's `--apply` run on `v3.1.0` fails if any of them is looked up from `rr_update/`.
- **`NORMALISE` can hide a diff** (FC8): reviewed with the golden commit; the first question is
  what it erases.
- **The record**: `state.py recall` on these files returns 16 items; most name line numbers of
  the migrating `update.py` that the regenerate task deleted. Two residuals still describe live
  code (`keep_original` on a second same-day regenerate; a raw path inside a copy-paste hint).
  They stay as they are (R12); the golden pins them.
- The guard's refusal matches the text `update.py --apply --confirm-delete`; the code gate
  (`gate.human_gate`) is unchanged and is what holds. Nothing new becomes runnable by path:
  `rr_update/cli.py` has no `__main__`.

## Proof

| Req | Proof |
|---|---|
| R1 entry contract | `tests/test_update_characterization.py` green after s3, byte for byte; `test_exit_codes_in_the_docstring` |
| R2 package, entry small, no re-exports | `tests/test_update_layout.py` (entry line count, imports only `rr_update.cli`) |
| R3, R10, R16 | `tests/test_update_layout.py` against `partition.json` |
| R4 classes, no `global` | `tests/test_update_layout.py` grep |
| R6 importers own the names | the three suites green, assertions untouched; layout test fails on `import update` in `tests/` |
| R6a one path constant | layout test: one `__file__`, in `paths.py` |
| R7 lint | `pylint $(git ls-files '*.py')` 10.00/10 inside `verify` |
| R8 not slower | median of 20 runs of `update.py --check` on `fresh`, before and after, within 10 % — in the task report |
| R9 installed | `tests/test_install_dry_run.py` |
| R11 docs | s4, read by the review |
| R14 rollback | below |

## Rollback

`git revert` of the task's commits restores the single file (R14); no state, schema or policy
file changes.

## Start — later, not now

```bash
$STATE start --goal "WP3: update.py becomes an entry (CLI only, no re-exports) and rr_update/; behaviour unchanged" \
  --workflow refactoring \
  --files "<every file of s0–s4>" --tests "<every step's tests>" \
  --declare 'behaviour=0:"refactoring: every flag, output line and exit code pinned by a new characterization golden (C3)"' \
  --declare 'domain=0:"moves the project updater code; human_gate and the guard spelling unchanged"' \
  --declare 'novelty=0:"the WP1/WP1b pattern applied to a second file"' \
  --plan-file <scratchpad>/steps.json --batch --by "Ivan Kakurov" \
  --why "/rr-build-all docs/sdlc/plans/small-oop-modules-wp3.md"
```
