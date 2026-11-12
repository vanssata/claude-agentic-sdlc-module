# Plan: Small OOP modules — WP5, `hooks/guard/paths.py` becomes the path-guard entry and sibling `paths_*` rule modules

Spec: `docs/sdlc/specs/small-oop-modules.md` (§Work packages row 5: "already a package: split
`paths.py` into rule groups", "byte-identical guard golden", the CLAUDE.md `SH_WORD`/`SH_RE`
invariant; R1–R16 read for `paths.py`, R13, R15) · Programme: `docs/sdlc/plans/small-oop-modules.md`
· Consumes: WP4 (`9bb5625`, #72), closed · Written 2026-11-12 on `refactor/wp5-guard-paths`
(from `origin/main` `9bb5625`). **Started** 2026-11-12 as task
T-2026-11-11-2211-wp5-hooks-guard-paths-py via `/rr-build-all`.

Kind: **refactoring** (C3) — no guard decision, deny text, cap or clock changes; the guard golden
stays byte-identical (`hooks/CLAUDE.md`: behaviour 0). A bug found while moving is recorded with
`state.py memory risk add` and left in place (R12).

## Weight, measured (2026-11-12, `state.py weight` over the 18 paths below, not journaled)

```
scope 2 (hooks/guard/paths.py matches hot_paths hooks/**) · behaviour 1 (hint: keyword 'workflow'
in CONTRIBUTING.md; declared 0: "refactoring: every guard decision and deny text unchanged, the
guard golden byte-identical") · reversibility 0 · domain 0 (declared: "moves path-guard code
verbatim between modules; no rule, pattern, cap or message changes") · novelty 0 (declared: "the
WP1-WP4 pattern on a fifth file; guard/ is already a package") · coverage 2 (0 of 9 code files
have a test by name)  →  W 5 → guarded
```

Guarded: this file is the plan the human accepts; `verify --scope all` (it runs e2e itself); one
human stop at `/rr-ship`. Constitution cited: C1 (the golden records today's decisions), C2 (the
golden exists; the copy check is added before the cut-over), C3 (refactoring, nothing mixed), C4
(files per step), C5 (commits are the human's), C6 (weighed by effect on a user project: the one
effect that could reach one is a guard that **fails open** on a moved name — below, Risks).

**Model routing for this task (the developer's instruction, 2026-11-12):** the workers are
BALANCED — every implementer and fixer a `general-purpose` agent with `model: sonnet` (Sonnet
5.5), effort `high` (the programme's instruction of 2026-10-31); the thinking is STRONG — this
plan and every conclusion by the session (Opus 5.5), and the review by one `ai-reviewer` with
`model: opus`, recorded `--tier STRONG`. Guarded asks for BALANCED; `state.py review` refuses a
tier below the mode's, not one above (`rr_state/review.py`, the `REVIEW_TIERS.index` check), so
the mode stays guarded and no approval gate is added. Fable (EXPERT) is not a review tier of
`state.py review`; it is not used.

Spec flagged concerns that bear on WP5, as for WP4: **FC1** (scope guard vs SDLC writing — this
file was written with no task in flight), **FC8** (`NORMALISE` can hide a diff — not reached: WP5
records no new golden; the guard golden's own normalisation is untouched), **FC9** (behaviour 0,
large diff — the copy check below proves the move node for node; the review reads the s2 diff
first), **FC11** (ROADMAP not updated). Committing this plan is the human's acceptance of them
and of D1–D6.

## What is there (KNOWN FACT, grep and `ast` 2026-11-12)

- `hooks/guard/paths.py`: 1 543 lines; 82 top-level assignments, 12 top-level `def`, 3 classes —
  `LoopError(OSError)` (`:281`), `PathGuard` (`:637-1484`, 848 lines, 36 methods, the
  `too-many-public-methods` disable), `MoverState` (`:1487-1497`). 0 `__file__`, 0 `global`.
  The longest pieces: `shell_segments` (`:366-634`, 269 lines), `PathGuard.check_bash`
  (`:1350-1484`, 135), `PathGuard.movers` (`:1011-1139`, 129).
- **Importers.** `hooks/ai-guard.py:70` imports the check by name, `__import__("guard." + name,
  fromlist=["check"])` → `guard.paths.check`. `tests/test_ere_unit.py:19,205`: `from guard import
  … paths`, `paths.find_print`. Nothing else under `hooks/`, `skills/`, `tools/` or `tests/`
  imports a name of `guard.paths` (the `paths` of `rr_update` is another module).
- **By path.** `tests/test_install_dry_run.py:421` and `tests/test_codex_install.py:228` list the
  installed guard files; `tests/test_no_fallbacks.py:142` excuses `/project-update` in
  `hooks/guard/paths.py` (`WHY_TASK`, `:53`) and fails on a stale row or an unexcused file
  (`test_the_allow_list_is_not_stale`, `test_no_legacy_tokens`). By text, unchanged: the
  `.claude/hooks/guard/paths.py` payload of `tests/fixtures/path-guard/105-*.json` and golden
  lines 243, 246 (an installed path, still a file); `hooks/ai-guard.py:14` "(guard/paths.py)"
  (stays true); `docs/dialog-spike.md:206` (a dated spike, a stale line number already).
- **Installer.** `bin/riskrails.js:796` (Claude) and `:1474` (Codex) copy `hooks/guard/*.py` by
  glob: new modules ship with no installer edit. `hooks/ai-path-guard-defaults.json:39`
  (`(^|/)\.(claude|codex)/hooks/(guard|lib)/`) protects every installed file of the package.
- **Fail-open.** `hooks/ai-guard.py:69-93`: any exception but `Deny` raised by a check ends the
  run with exit 0 and no output — a `NameError`, `ImportError` or `AttributeError` in moved code
  allows the call and skips the scope check after it.
- **Proof that exists.** `tests/fixtures/guard-characterization/golden.txt` (3 089 lines, the
  1 341 recorded decisions, run through `ai-guard.py --only paths`), `tests/test_guard_differential.py`
  (the frozen shell guards beside the port), `tests/test_ai_path_guard.py` with
  `tests/fixtures/path-guard/*.json`, `TestTimed` (median of 5: Read/Edit/Write 25 ms, Bash 1 KB
  40 ms, the 20 KB `sh -c` fixture 100 ms).
- **`SH_WORD`/`SH_RE`** are names of the retired shell guard (`hooks/ai-path-guard.sh`); the port
  does not re-parse a `sh -c` string (`:1378-1379`, R22/SQ13). What the invariant asks of this
  task is that no regex text moves: every constant is compared node for node (D6) and pinned by
  value hash (s0).
- **pylint** (4.0.8, the repo's `.pylintrc`, probe 2026-11-12): `self._x` inside a module-level
  function is W0212 `protected-access` (9.33/10 on the probe); importing a `_name` from a sibling
  is not reported. `C` is off, so a moved function needs no docstring.

## Decisions taken in this plan (each from the spec, cited)

- **D1 `paths.py` stays the entry** (R13: keep the path of an entry invoked by path — here by
  module name). It keeps its docstring (plus one sentence naming the rule modules, R11) and holds
  `PathGuard` — the state of one tool call: `__init__`; the clock and caps (`clock_ok`,
  `work_cap`, `work_clock`); the task memo (`_state_file`, `_task_line`, `task_in_flight`); the
  per-tool dispatcher `check` — the method table (D2) and `check(ctx)`. Under 200 lines;
  re-exports nothing (Q25). `PathGuard`'s docstring names its invariant (R4): the work counters
  against their caps and the clock, and the task memo, for one call.
- **D2 Methods move as functions with `self` first, bound by a method table.** A rule module
  defines `def classify(self, path):` with today's body, dedented; `PathGuard`'s body binds
  `classify = paths_classify.classify`. Dispatch through `self.` is unchanged, so a method that
  calls one in another module goes through the instance as today; nothing is inherited (R4).
  *Rejected*: mixins (`class PathGuard(Classify, Movers, …)`) — inheritance, R4; functions over a
  guard argument (`classify(g, path)`) — `self.`→`g.` in the 28 moved bodies and every call site rewritten,
  an edit per method the golden alone would have to catch, where D2's bodies can be compared node
  for node; the class whole in one module beside split-out constants (~870 lines) — the class is
  the bulk, and there are no rule groups.
- **D3 The rename map.** Five helpers that moved code calls through `self` lose their underscore,
  as W0212 would cost the score and `.pylintrc` gains no disable (R7): `_mode`→`loc_mode`,
  `_loc_pat`→`loc_pat`, `_loc_text`→`loc_text`, `_from_loc`→`from_loc`,
  `_roots_under`→`roots_under` — the definitions and every `self.<old>` use. `_state_file` and
  `_task_line` stay private (called only inside the class). The map is recorded in
  `partition.json`; the copy check applies it and nothing else.
- **D4 From-imports between the guard modules** (`from guard.paths_base import T, WHY_TASK`), the
  package's style (`paths.py:22`, `from guard.common import …`): every body stays as it is. The
  rule of R6 that keeps attribute lookups so a patch reaches its caller has no subject here — no
  suite patches a name of `guard.paths` (the one patch of a guard module is `guard.git.check`,
  `tests/test_guard_characterization.py:570`). A `_name` is imported only where the map needs it
  (none today: each private name lives with all its users). `T = text_to_b` moves to
  `paths_base` once; the others import `T`.
- **D5 The importers.** `tests/test_ere_unit.py` imports `paths_fs` and calls
  `paths_fs.find_print`; `tests/test_no_fallbacks.py:142`'s row names `hooks/guard/paths_base.py`,
  where `WHY_TASK` now lives (the path only — the reason and tokens unchanged: a row naming where
  a text lives, the kind of edit R6 allows); the two install suites list the eight new files (R9).
  Every other test hunk is refused (R6), and the review reads every test hunk first.
- **D6 Proof of the move.** No new golden (spec WP table: the guard golden exists). The new
  proof is the **copy check**: `move_problems(source_text, base)` in `tests/test_guard_layout.py`
  parses today's `paths.py` and each module, and fails unless every moved node — constant,
  function, class, and each method as a top-level function — is equal to its source node
  (`canon` of the `ast`, so indentation does not count) after D3's map, and every source name has
  exactly one home. In the copy phase it runs on the `paths.py` on disk; after the cut-over the
  s3 implementer and the reviewer run it once against `git show HEAD:hooks/guard/paths.py` (no
  commit is made during the task, so `HEAD` is the pre-WP5 tree) and the output goes in
  `task.md`. It is not a permanent test of bodies: a later guard fix must not have to edit a
  fixture. What stays permanent is WP4's: homes, signatures, constant value hashes, layers,
  imports.

## Module map (indicative; `tests/fixtures/guard/partition.json` from s0 is the authority)

All in `hooks/guard/`, imported as `guard.<name>` (`hooks/` is on `sys.path` by `ai-guard.py`).
`.m` is a `PathGuard` method moved as a function (D2); ~lines without imports and docstrings.

| Layer | Module | Holds | ~lines | core/shell |
|---|---|---|---|---|
| 0 | `paths_base` | `T`, `Q`, `END`, `VAR`, `SEGMENT`, the eight `WHY_*` texts (`CONFIRM_DELETE`, `SENSITIVE`, `PROTECTED`, `TASK`, `APPROVE`, `WORK_CAP`, `HUMAN`, `PICK`) | 50 | core |
| 0 | `paths_fs` | `LoopError`, `realpath_m`, `find_print`, `lexnorm`, `cd_physical`, `anchor_list` | 115 | shell (lexnorm core) |
| 0 | `paths_shell` | `_KEYWORDS`, `_FLAGGED`, `_ASSIGN`, `_SPECIAL_OUT`/`_D`/`_A`, `shell_segments` (the awk segmenter) | 275 | core |
| 1 | `paths_human` | the `--confirm-delete` rule (`CONFIRM_DEL`, `CONFIRM_CLEAN`, `CONFIRM`, `APPLY`, `HEAD`, `SEP`, `CONFIRM_RE`, `.confirm_delete`) and the human-only `state.py` rules (`ARGS`, `VERB`, `BOUND`, `APPROVE_RE`, `PROFILE_SET_*`, `BY_TOK`, `MODE_LIGHT`, `SKIP`, `HUMAN_BY_*`, `START_LIGHT_*`, `state_verb_re`, `DIALOG_GATE_RE`, `.dialog_consent`) | 70 | core + shell |
| 1 | `paths_interp` | interpreter one-liners and in-place edits: `INTERP_RE`, `CONTROL_TEXT_RE`, `INPLACE_RE`, the text-tool words (`_TEXT_TOOLS` … `_GIT_CFG`, `_tool_word`, `shell_sink`, `_plain_text_tool`, `text_tool_segment`), `EVAL_WORD_RE`, `SECRET_TEXT_RE`, the `WRITE_*` patterns and `FIRST_ARG`, `.inplace_edit`, `.interpreter_text` | 130 | core + shell |
| 1 | `paths_classify` | `TOKEN_END`, `.load_patterns`, `.build_loose`, `.setup_anchors`, `.anchor_rels`, `.anchored_hit`, `.unanchored_hit`, `.classify`, `.check_path` | 170 | shell |
| 1 | `paths_movers` | `MOVERS`, `MOVER_VERBS`, `REMOVE_VERBS`, `MOVER_CHUNK`, `GLOBBY`, `_SED1`, `_SED2`, `_FIND_PRUNE_*`, `MoverState`, `.cover_init`, `.realpath_m_arg`, `.sort_u`, `.roots_under`, `.covers_work`, `.covers_protected`, `.loose_hits`, `.movers`, `.loc_mode`, `.loc_pat`, `.loc_text`, `.from_loc`, `.mover_resolve`, `.mover_check` | 345 | shell |
| 2 | `paths_bash` | `VERBS_RE`, `READERS`, `COPIERS`, `WRITERS`, `REMOVERS`, `MODES`, `DDWRITE`, `INPLACE`, `LN_RE`, `LN_SRC_RE`, `LONG_CMD`, `LONG_TRIGGER_RE`, `FETCHERS`, `.check_bash` | 150 | shell |
| 3 | `paths` (entry) | D1 | 90 + table | shell |

**Deviation at implementation** (2026-11-12, the session, after step s1): `phys_path` stays a
`PathGuard` method in `paths.py`. It reads no `self`; as a module function with `self` first it
is pylint W0613 `unused-argument` (9.99/10), and R7 allows no new disable. So nine methods stay in
the class and 27 are bound by the table; the entry also imports `paths_fs`. `partition.json` and
the layout test say so. The node-for-node move proof is one-shot: `--moved-from HEAD` ran in
s2 and in the review (`task.md`, review pass 1); after the commit the golden is what stays.

Every name of today's file has one home above (`ast`, 2026-11-12: none left over). Import edges
by name (no cycle on paper; s0 proves it): `paths_classify` ← `paths_base`, `paths_fs`;
`paths_movers` ← `paths_base`, `paths_fs`; `paths_interp` ← `paths_base`, `paths_shell`;
`paths_human` ← `paths_base`; `paths_bash` ← `paths_base`, `paths_shell`, `paths_human` (the gate
patterns), `paths_movers` (`GLOBBY`); `paths` ← all. A comment block above a constant (`:68`,
`:78`, `:84-90`, `:119-122`, `:146-162`) moves with it, word for word. Calls between methods cross
modules only through `self` (D2), so they are no import edge.

## Order of work

| Step | Files | Tests (step scope) | After |
|---|---|---|---|
| s0 | new `tests/fixtures/guard/partition.json` (every top-level name and every `PathGuard` method → one module, layer, core/shell label, kind; a function's signature, a constant's value hash; D3's rename map; the module import edges; the entry's names); new `tests/test_guard_layout.py` — phase-aware like `tests/test_memory_layout.py`: **single** (no `paths_*` module exists): the partition against `paths.py`, every name once and vice versa, kinds, signatures, value hashes, edges acyclic and downward on paper, no `global`; **copy** (some exist, `paths.py` whole): each present module is exactly its partition names, and `move_problems` (D6) on the `paths.py` on disk; **final** (`paths.py` is D1): entry under 200 lines defining only `PathGuard` and `check`, no re-export; the eight modules present and each the partition's; the method table binds exactly the moved methods, each to its home's function (an unbound method would fail open, Risks); the real import graph acyclic and downward; R4 (three classes, the bases `OSError` and none; no `ABC`/`Protocol`/`staticmethod`; no `global`; no `__file__`); R15 (no import of `rr_state`, `state` or `skills/` from `hooks/guard/`); sizes printed, 600 advisory. A synthetic-tree test shows each final check can fail. Helpers may be copied from `tests/test_memory_layout.py` (`canon`, `hash_of`, `statement_names`, …); it is not imported | `tests/test_guard_layout.py` | — |
| s1 ⚠ | the copy phase: new `hooks/guard/{paths_base,paths_fs,paths_shell,paths_human,paths_interp,paths_classify,paths_movers,paths_bash}.py`, each a docstring (its rule group, the core/shell labels — R16, "moved from paths.py in WP5, unchanged"), its from-imports (D4), its names copied from `paths.py` with their comments, methods dedented as functions, D3's map applied; `paths.py` not edited. Done by a script over `ast` line ranges, not by hand | `tests/test_guard_layout.py` (copy phase: `move_problems` empty), `pylint` on the eight files by name (untracked files are not in `git ls-files`) | s0 |
| s2 ⚠ | the cut-over: `hooks/guard/paths.py` becomes D1 (every moved name deleted; the imports of the eight modules; the method table); `tests/test_ere_unit.py`, `tests/test_no_fallbacks.py`, `tests/test_install_dry_run.py`, `tests/test_codex_install.py` (D5); `tests/test_guard_layout.py` only if its final phase needs a fix. The eight modules are **not** in this step's files: a needed change there is `SCOPE_CHANGE_REQUIRED`. The RESULT carries `move_problems` against `git show HEAD:hooks/guard/paths.py` (empty) and the R8 medians | `tests/test_guard_layout.py`, `tests/test_guard_characterization.py`, `tests/test_guard_differential.py`, `tests/test_ai_path_guard.py`, `tests/test_ai_scope_guard.py`, `tests/test_ai_git_guard.py`, `tests/test_ere_unit.py`, `tests/test_no_fallbacks.py`, `tests/test_install_dry_run.py`, `tests/test_codex_install.py`; `pylint $(git ls-files '*.py') hooks/guard/paths_*.py` | s1 |
| s3 | docs (R11): `docs/architecture.md` (a paragraph on the path guard's entry and its rule modules, beside the `state.py`/`update.py`/memory paragraphs), `CONTRIBUTING.md` (where the guard code lives; that `test_guard_layout` and the golden prove a move), `docs/known-risks.md:49,72` (the confirm gate's source is `hooks/guard/paths_human.py`) | `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` | s1 |

s0 alone first; s1 is one implementer (eight files, ~1 400 lines, by layer — a module's import
of a lower one must resolve for pylint), fewer handoffs than four layer steps; s2 and s3 in
parallel. A test edit in s2 is import lines, qualified names, the KEEP row's path and the
installed lists only — never an assertion, an expected text or a fixture (R6); the implementer's
`## RESULT` says so. Then `verify --scope all` once (it runs e2e itself), fixes as one batch, one
STRONG review, `/rr-ship`.

## Risks

- **A moved name that does not resolve fails open** (C6, the one effect that reaches a user
  project): `ai-guard.py` turns a `NameError`, `ImportError` or `AttributeError` into an allow,
  and the scope check after `paths` never runs. A missing import, a method left out of the table
  or a typo in the map would pass every test that does not reach that line. Closed three ways:
  pylint on every new file (E0602 `undefined-variable`, E0401 `import-error`, W0611
  `unused-import`; 10.00/10), the layout test's table check (the bound methods are exactly the
  moved ones), and the golden plus the path-guard fixtures through the real hook.
- **s2 is the riskiest step** (⚠): the entry and four suites change at once. It cannot move
  earlier (the table has nothing to bind before s1) and is not split (a half-bound class fails
  open). Its proof: `move_problems` against `HEAD`, the golden, the differential test, the
  path-guard fixtures; the review reads the s2 diff first.
- **Timing** (R8): every tool call imports the path guard; eight more modules mean eight more
  file lookups and `.pyc` loads. `TestTimed` holds the budgets; the medians of 20 runs of
  `ai-guard.py` on a Read and on the 1 KB Bash payload of `TestTimed`, before and after, within
  10 %, go in `task.md`.
- **A comment that does not move** (the AST does not see comments): the review reads each
  module beside the source ranges; the comment blocks named under the module map are the ones
  that explain a rule.
- **Installed copies**: a hand copy of `hooks/guard/` without the new modules fails open on the
  first `import`. Only a hand copy reaches it (both installers glob the directory). Accepted, as
  WP4's partial-install message was.
- **The record** (`state.py recall`): open items on `paths.py` — the `sh -c` bypass accepted in
  `known-risks.md` (R22/SQ13), the 8-per-segment cap's wording, the `>|` split — stay as they
  are (R12), pinned by the golden.
- **A fifth layout test** repeats the partition scanner (`test_state_layout`, `test_update_layout`,
  `test_memory_layout`, now `test_guard_layout`). A shared helper is a separate refactoring (C3),
  not this task; the copy of the helpers is the accepted cost.

## Proof

| Req | Proof |
|---|---|
| R1 entry contract | `tests/test_guard_characterization.py` byte-identical; `tests/test_guard_differential.py`; `tests/test_ai_path_guard.py`; `ai-guard.py` unchanged |
| R2 entry small, no re-exports | layout test (final): under 200 lines, `PathGuard` and `check` only |
| R3, R10, R16 | layout test against `partition.json`; the real import graph |
| R4 classes, no `global` | layout test: three classes, bases `OSError` and none, no `global` |
| R5 golden | the guard golden exists and is unchanged (`git diff --stat` of `tests/fixtures/guard-characterization/`); `move_problems` empty in the copy phase and against `HEAD` after s2 |
| R6 importers own the names | `tests/test_ere_unit.py` imports `paths_fs`; no other importer; test hunks are D5's only |
| R6a | no `__file__` in `hooks/guard/paths*.py` (none today) |
| R7 lint | `pylint $(git ls-files '*.py') hooks/guard/paths_*.py` 10.00/10 |
| R8 not slower | the medians in `task.md`; `TestTimed` |
| R9 installed | `tests/test_install_dry_run.py`, `tests/test_codex_install.py` list the eight files |
| R11 docs | s3, read by the review |
| R12 risks met | `state.py memory risks` lists what s1–s2 found |
| R14 rollback | below |
| R15 hook isolation | layout test: no import of `rr_state`/`state` under `hooks/guard/` |

## Rollback

`git revert` of the task's commit restores the single file (R14); no state, schema, policy,
template or installer change, so nothing is migrated back. The installed copy follows with
`npx riskrails`; the eight extra files an older install keeps are imported by nothing. The
partition and the layout test may stay after a revert — they describe the layout.

## Start — later, not now

```bash
$STATE start --goal "WP5: hooks/guard/paths.py becomes the path-guard entry and sibling paths_* rule modules; behaviour unchanged" \
  --workflow refactoring \
  --files "<every file of s0–s3>" --tests "<every step's tests>" \
  --declare 'behaviour=0:"refactoring: every guard decision and deny text unchanged, the guard golden byte-identical"' \
  --declare 'domain=0:"moves path-guard code verbatim between modules; no rule, pattern, cap or message changes"' \
  --declare 'novelty=0:"the WP1-WP4 pattern on a fifth file; guard/ is already a package"' \
  --plan-file <scratchpad>/steps.json --batch --by "Ivan Kakurov" \
  --why "/rr-build-all docs/sdlc/plans/small-oop-modules-wp5.md"
```

`steps.json`: s0 `[]`, s1 `after [s0]`, s2 `after [s1]`, s3 `after [s1]`; `tests: []` on every
step (a shared test serialises steps), the implementer runs its step's tests itself.
Preconditions: no task in flight (`state.py status`: none on 2026-11-12), the human has committed
this plan; FC1/FC8/FC9/FC11 and D1–D6 accepted.
