# Plan: Compact project memory — bounded files in git, bounded context, optional local history

Intent: carried in the spec (`## Intent`); questions on record in
`docs/sdlc/intent/compact-project-memory.questions.md` · Spec: `docs/sdlc/specs/compact-project-memory.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Written 2026-10-28 on `new-refactor` (HEAD `c3462a9`, the spec's commit). This is a programme plan: each
row of **Order of work** is one `/rr-build` task, which writes its own step-level plan (inline, plan mode or
written, by the mode `state.py weight` computes) and ends at human approval. No agent commits (C5). The
spec's R1–R27, A1–A12 and §D1–§D15 are the source; this plan fixes the order, names the files per task,
records where it departs from the spec's suggested order and why, and maps every requirement to its proof.

## Decisions taken before planning (2026-10-28, developer)

- **Q1–Q6** as recorded in the spec's *Decisions taken*: only what shows who, what, how and why per task
  goes to git (Q1); packages with unique names, no merge driver (Q2 = A); the new id in files mode too, with
  a short, clear slug (Q3 = X, "накъв слъг на задачата кратък но ясен"); `recall` and `memory risk` in files
  mode too (Q4 = A); the SQLite index only past the measured threshold (Q5 = A); period `quarter` (Q6 = A).
- **Flagged concerns.** FC3–FC7 are resolved inside the spec. FC1, FC2 and FC8–FC13 were explicitly accepted
  by the developer on 2026-10-28 ("приемам всички"), with these consequences:
  - FC1: aligning root `CLAUDE.md` and root `AGENTS.md` (the two corrections, the word "pushes") is the
    developer's edit outside any task; no row below touches those files.
  - FC2: M8 fixes the template `.ai/state/README.md` and `docs/architecture.md`; the project's own
    `.ai/state/README.md` is the developer's edit at G1.
  - FC8: `.ai/policies/security.md:59-61` and `.ai/AGENTS.md:33-35` are the developer's edits at gate G1,
    from text M5 stages in its `task.md` §Changes.
  - FC9: the three defects (`archive_v7`'s non-atomic `state.json` write, `actor: hook` on agent notes,
    `.ai/state/consent.jsonl` outside the ignore snippet) are recorded by M8 with `state.py memory risk add`
    (files mode), not fixed by any row here (C1).
  - FC10–FC13: accepted as stated (19 top-level CLI names; the first git hook, with `--no-verify` the
    human's escape only; JSONL in PR diffs; a byte-based token estimate).
- **V5 scope (plan finding, accepted).** As written in the spec (§D10), V5 would refuse every push in this
  repository until the 59 legacy tasks are migrated, because none has a seal. V5 applies to ids matching
  `NEW_ID_RE` and to legacy ids that already have a seal in a package; unmigrated legacy tasks are listed by
  `state.py memory status`, never by the hook. M7 amends the one line in §D10 and this repository turns
  packages mode on only at G2, after the migration.

## Executed as one task (T-2026-10-28-011, developer 2026-10-28)

The developer asked for every row at once, with one verification run at the end and one review. Answers
given before `start`:

- **M2 without its refactoring (C3).** `memory_store.FileHistory` is new code that only the new commands
  read; `journal-summary.py`, `status.py` and `usage-report.py` are not moved onto it. Their answers are
  pinned by goldens recorded from the tree before the change (`tests/test_memory_characterization.py`,
  `AI_GOLDEN_ROOT`), and `usage-report --task` gains only the R20 fallback (the moved journal, then the
  seal's window). Moving the three tools onto `History` is a later refactoring task of its own.
- **M10 unconditionally** — G3 below records the numbers anyway.
- **One whole-suite run and one e2e run at the end**; each new test module ran alone while written, and
  M3's failing test ran once with `--expect fail` (C2).

Decided while building, each pinned by a test:

- **A4 against R1.** R1 caps the disambiguator at `-9`, so "1 000 starts in one minute with one goal give
  1 000 ids" cannot hold; the test proves the property behind it — no two starts ever share an id: one
  goal gives 9 ids and then exit 2 naming `--slug`, and 1 000 slugs in one minute give 1 000 ids.
- **Recall's continuation is `state.py recall --files … --offset N`**, not `memory search --files`: search
  orders by time and could not continue a tiered list. `recall` gained `--offset`.
- **The recall header names the backend** (`index none|sqlite`), so R11's byte identity holds for the
  items and the counts: the token count covers the items and the continuation line, and the packing
  reserves the widest header any backend prints.
- **V5 checks that every kept line of a committed closed journal is an entry's `src`**; it does not
  re-compact a changed sealed task from its blobs. **V4 is not checked for a key with a recorded
  conflict**, because which entries belong to which seal is not knowable from the lines.
- **A redaction entry carries `replacement`** (the rewritten line's rid) besides `target`, so V4 maps the
  new rid back when it recomputes the seal's digest.
- **`migrate --move-logs` takes the human route**, like `cleanup`.

## Departures from the spec's suggested order

1. **Spec steps 4 and 5 are one task, M4.** The record format has no deliverable of its own, and dropping
   an approval is behaviour 2 under C6 for the pair, so one full-mode task with one STRONG review costs
   less than two tasks of which one would be reviewed twice.
2. **Spec step 9 (guard patterns) is folded into M5**, the first writer of `.ai/memory/`: R19 must hold from
   the first export, so the pattern and its golden land in the task that creates the directory.
3. **Spec steps 8 and 10 are one task, M6.** Recall's first tier is open risks; the `risk` kind, its parser
   and `memory risk add|close` are exercised through the recall and search tests.
4. **Spec steps 16 and 17 are one task, M12.** The end-to-end walk is the pack's acceptance (A1,
   branch-per-task) and needs every command to exist.
5. **The human-staged policy edits of spec step 12 become gate G1 after M5**, not part of M8:
   `security.md` must name `.ai/memory/` before the first package is pushed.
6. **Spec step 3's "CHANGELOG note"**: this repository has no changelog file; the id shape is documented by
   `start --help` (M3) and `docs/local-memory.md` (M8).
7. **The migration (M9) precedes `memory enable` in this repository (G2)** because of the V5 scope above.
8. **`FsReader` is defined in `memory_compact.py` (M4) and re-exported by `memory_sync.py` (M5)**, so M4
   depends on no module that does not exist yet; `GitTreeReader` stays in `memory_sync.py` (M7). The
   spec's §D14 lists both readers under `memory_sync`; the public names are unchanged.

## Files that change

Grouped by task; "new" / "edit" / "delete". Fixtures are listed by directory. No row edits `install.sh`,
`bin/riskrails.js` or `skills/ai-init/templates/gitignore.snippet` (spec FC3). No row creates a
`skills/project-update` migration or a template `memory.json`: an absent file is files mode, and
`memory enable` writes the project's copy, which `/rr-setup --update` must leave alone (see Risks).

| Task | Files |
|---|---|
| M1 | new `tools/benchmark-memory.py`, `tests/test_benchmark_memory.py` |
| M2 | new `tests/test_memory_characterization.py`, `tests/fixtures/memory/legacy-reports/**` (copies of `.ai/reports/` directories of each legacy shape: pre-WP2 state-only, backfilled, questions, gate, review, v7, multi-instance), `skills/ai-task/memory_store.py` (`History`, `FileHistory` over legacy directories, `open_history`), `tests/test_memory_store.py`; edit `tools/journal-summary.py`, `skills/usage-report/usage-report.py`, `skills/rr-status/status.py` (read through `History`, byte-identical output) |
| M3 | edit `skills/ai-task/state.py` (`next_task_id`, `start --slug`, help text), `tests/test_ai_task_state.py` (id assertions); new `skills/ai-task/memory_format.py` (`new_task_id`, `slug_of`, `NEW_ID_RE`, `LEGACY_ID_RE` only), `tests/test_task_id.py` |
| M4 | edit `skills/ai-task/memory_format.py` (`FORMAT`, `KINDS`, `REQUIRED`, `KEEP_RULES`, `classify`, `canonical`, `make_rid`, `seal_digest`, `validate`, `package_name`, `parse_package_name`, `parse_package`, `period_of`, `est_tokens`, `redact`, `render_line`, `render_task_md`); new `skills/ai-task/memory_compact.py` (`compact_task`, `split_instances`, `parse_task_md`, `excerpt`, `FsReader`), `tests/test_memory_format.py`, `tests/test_memory_compact.py`, `tests/fixtures/memory/{canonical,journals}/**` |
| M5 | new `skills/ai-task/memory_sync.py` (`MemoryConfig`, `load_config`, `after_close`, `export`, `verify` for `--all` and ids, `open_batch`, the outbox and the lock), `tests/test_memory_sync.py`; edit `skills/ai-task/state.py` (`memory status\|export\|verify\|show`, the call after `archive_v7` when `mode == "packages"`, lazy import), `skills/ai-task/sensors.py` (R26), `hooks/ai-path-guard-defaults.json` (two patterns), `tests/fixtures/guard-characterization/**` (golden re-recorded, additive), `tests/test_ai_task_state.py`, `tests/test_ai_task_sensors.py` |
| G1 | — (human: `.ai/policies/security.md:59-61`, `.ai/AGENTS.md:33-35`, `.ai/state/README.md:19-21`, from the text M5 stages) |
| M6 | edit `skills/ai-task/memory_store.py` (`recall`, `search`, `risks` over `FileHistory`), `skills/ai-task/memory_format.py` (`rank_recall`, `match_search`, `tokenize`, the path matcher), `skills/ai-task/memory_compact.py` (`parse_known_risks`), `skills/ai-task/memory_sync.py` (`risk_add`, `risk_close`, the files-mode append and amend), `skills/ai-task/state.py` (`recall`, `memory search\|risk\|risks`; `risk_recorded` in `EVENT_TYPES` and `FORGEABLE_EVENTS`); new `tests/test_memory_recall.py`, `tests/test_memory_risks.py` |
| M7 | new `hooks/memory-pre-push.py`, `tests/test_memory_pre_push.py`; edit `skills/ai-task/memory_sync.py` (`validate_range`, `GitTreeReader`, `install_hook`, `remove_hook`, checks V1–V6, V8, V9), `skills/ai-task/state.py` (`memory enable\|disable`, `memory verify --range`), `docs/sdlc/specs/compact-project-memory.md` (the V5 scope line in §D10), any inventory test that pins `hooks/*.py` (see Risks) |
| M8 | edit `skills/rr-build/SKILL.md`, `skills/rr-review/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/rr-plan/SKILL.md` (`recall` at task start; `memory risk add\|close` instead of appending `known-risks.md`), `docs/architecture.md`, `skills/ai-init/templates/.ai/state/README.md`, `skills/ai-init/templates/.ai/policies/safety.md` (the memory toggles take the human route), `skills/project-update/history/<ver>/…` through `tools/build-template-history.py`, `README.md` (one paragraph); new `docs/local-memory.md`; tests `tests/test_skills_surface.py`, `tests/test_instruction_budget.py`, `tests/test_project_update.py` |
| M9 | edit `skills/ai-task/memory_sync.py` (`migrate_report`, `migrate_apply`, `migrate_risks`, `move_logs`), `skills/ai-task/state.py` (`memory migrate`); new `tests/test_memory_migration.py`, `tests/fixtures/memory/migration/**` |
| G2 | — (human, this repository: `memory migrate --report`, `--apply`, `--apply --risks`, `--move-logs --confirm-delete <author>`; two commits; then `memory enable --period quarter`, a third commit with `.ai/policies/memory.json`) |
| G3 | — (human: the Q5 threshold on M1's baseline and M6's timings decides M10) |
| M10 | edit `skills/ai-task/memory_store.py` (`SqliteHistory`, `refresh`, `rebuild`, FTS5 detection), `skills/ai-task/state.py` (`memory rebuild`, `--index` on `enable`), `tools/benchmark-memory.py` (index build and query), `tests/test_memory_store.py`, `docs/local-memory.md` (the measured budgets) |
| M11 | edit `skills/ai-task/memory_sync.py` (`cleanup`, `restore`, `redact`, boundary B6), `skills/ai-task/state.py` (`memory cleanup\|restore\|redact`, `memory verify --fresh-clone`), `hooks/memory-pre-push.py` (V7); new `tests/test_memory_cleanup.py` |
| M12 | edit `skills/ai-task/memory_sync.py` (`pack`), `skills/ai-task/state.py` (`memory pack`), `tests/test_memory_sync.py` (A1), `tests/test_end_to_end.py` (enable → start → close → record → pre-push → fresh clone → show) |
| G4 | — (human: `cleanup: true` in `.ai/policies/memory.json` and `memory cleanup --all --confirm-delete <author>` once §D6 holds) |

## Order of work

Each row is one `/rr-build` task or a human act outside a run. **Mode**: the value expected from C6 and the
`.ai/policies/weight.json` rows; the one `state.py weight` computes on the row's files wins, and raising it
is free. **Consumes / Produces**: the exact names neighbouring tasks rely on (spec §D14 and §I1–§I6).
**Proof**: the task's own check, on top of `verify_command` once to the end and `e2e_command` once
(`.ai/policies/testing.md:87-89`).

- **M1 Benchmark baseline.** Expected guarded (a new tool, behaviour 0; novelty 1). Workflow feature.
  Consumes: —. Produces: `tools/benchmark-memory.py --tasks 100,1000,10000 --seed N [--journal-kb K] --json`
  and `generate(n, seed, journal_kb)`, the seeded synthetic histories that A2 and A5 reuse. Proof: two runs
  with the same seed print the same sizes and counts; the report separates cold and warm, build and query,
  bytes returned. The developer copies the baseline numbers into `docs/local-memory.md` at M8 and decides
  G3 from them.
- **M2 Characterization and the History refactor.** Expected guarded. Workflow refactoring (C3): no output
  changes. Step order inside the task: 2a the characterization tests and fixtures, green on today's tree
  (C2); 2b `memory_store.FileHistory` over legacy directories, and `journal-summary.py`, `usage-report.py
  --task`, `status.py` reading through it. Consumes: —. Produces: `History` (`tasks()`, `entries(key)`,
  `raw_journal(task_id)`, `task_window(task_id)`, `risks(status)`; `recall` and `search` arrive in M6),
  `FileHistory(root, cfg=None)` (the `MemoryConfig` argument arrives with M5; until then the class reads
  legacy directories only), `open_history(root)`, `tests/fixtures/memory/legacy-reports/**`. Proof: A11 —
  the three tools' outputs equal their goldens byte for byte before and after 2b; legacy ids are valid
  (R2).
- **M3 Task id with a slug.** Expected guarded, behaviour 1. Workflow bugfix: the first step is the failing
  test (C2) — two roots started the same day get the same id, and a deleted report directory makes
  `next_task_id` reuse an id (`state.py:446-452`, `:1664-1666`). Consumes: —. Produces:
  `memory_format.new_task_id(now, slug) -> str`, `slug_of(goal) -> str`, `NEW_ID_RE`, `LEGACY_ID_RE`;
  `state.py start --slug S`; the local disambiguator `-2`, `-3`, … up to 9, then exit 2 naming `--slug`.
  Proof: `tests/test_task_id.py` (R1: the shape, Cyrillic transliteration, whole words within 24
  characters, `task` when nothing is left, the disambiguator, 1 000 starts in one minute with one goal
  give 1 000 ids, legacy ids still accepted); M2's goldens stay green except the id (A6).
- **M4 Record format and compaction.** **Expected full** (C6: a compaction that drops an approval, an
  answer or a scope change is behaviour 2), one STRONG review. Workflow feature. Consumes: `FileHistory`
  (M2), `NEW_ID_RE`/`LEGACY_ID_RE` (M3). Produces: the §I1 envelope and kinds, `KEEP_RULES[1]`,
  `canonical(obj) -> bytes`, `make_rid(entry) -> str`, `seal_digest(rids) -> str`,
  `validate(entry) -> list[str]`, `package_name(period, author, batch=None)`, `parse_package_name(name)`,
  `parse_package(data) -> (header, entries, errors)`, `period_of(ts, period)`, `est_tokens(text)`,
  `redact(text)`, `render_line(entry, seal)`, `render_task_md(entries) -> list[str]`;
  `compact_task(reader, task_id, sources="close"|"tracked") -> Compaction(entries, seal, coverage,
  problems)`, `split_instances(events)`, `parse_task_md(text)`, `excerpt(log_text, expected_fail, limit)`,
  `FsReader(root)`. Proof: A3 on the fixtures (export, import, export byte-identical; every required field
  per kind; coverage 100 %; answers, notes and why texts byte-equal to their sources; a 6 KB answer survives
  the journal's 4 KB truncation through task.md); an unknown event is kept; the canonical-bytes golden; a
  one-off run over the 59 real directories reports coverage 100 % (its output goes into the task's
  `task.md`). **Riskiest row with M5.**
- **M5 Export at close, the first CLI, the guard.** **Expected full** (it changes what a user project
  commits; the guard pattern is behaviour 1). Workflow feature. Consumes: M4. Produces:
  `MemoryConfig`, `load_config(root)`, `after_close(root, task_id)`, `export(root, ids|"pending") ->
  ExportResult`, `verify(root, scope) -> list[Finding]` for `--all` and ids, `open_batch(root, cfg)`,
  `.ai/local/memory/{outbox/,lock,batches.json,config.json}`, the package header (§I2),
  `state.py memory status|export|verify|show`, the `record:` close line (§D5), the two guard patterns, the
  `sensors.snapshot_tree` exclusion (R26). The task stages, in its `task.md` §Changes, the exact text for
  G1. Proof: A6 (files mode writes the same files with the same output; `.ai/memory/` and
  `.ai/local/memory/` absent after every command); A9 for B1–B5 with `AI_MEMORY_CRASH_AT`; A4's merge
  part (two clones, plain `git merge`, no conflict under `.ai/memory/`, rid set equals the union, re-import
  adds nothing); A7's golden diff additive only; a forged approval entry for the task in flight leaves
  `close` requesting the gate (R19); two sessions closing two tasks at once serialise on the lock; a
  read-only `.ai/memory/` makes close print the `memory:` failure line, keep the outbox and exit 0.
- **G1 (human, after M5).** Apply the staged edits: `.ai/policies/security.md:59-61` (packages and
  `.ai/memory/` as evidence inputs and as always read-only for an agent), `.ai/AGENTS.md:33-35`
  (`memory.json` among the policy files), `.ai/state/README.md:19-21` (the archived state lives in
  `.ai/state/logs/`). Tick here: `[x]`. The text, staged by T-2026-10-28-011:
  - `.ai/policies/security.md:59-61`, the first sentence becomes: "Always read-only for an agent: the
    task's state under `.ai/state/`, its `task.md` and `events.jsonl`, `.ai/policies/*.json`, the compact
    record under `.ai/memory/` and `.ai/local/memory/` (written by `state.py` alone), and the installed
    guards — their hooks, engine and `skills/ai-task/` under `.claude/` and `.codex/`." Add after the
    paragraph: "A review's evidence for a closed task is its record — `state.py memory show <id>` and
    `recall` — once cleanup has moved the report directory; an approval in the record authorises nothing."
  - `.ai/AGENTS.md:33-35`: "`coding.md`, `safety.md` and `security.md`" becomes "`coding.md`,
    `safety.md`, `security.md` and, once a human ran `state.py memory enable`, `memory.json`".
  - `.ai/state/README.md:19-21`: the template's new paragraph (`skills/ai-init/templates/.ai/state/README.md`,
    "When a task closes, `state.py close` writes the final state to `.ai/state/logs/<task-id>/state.json` …").
- **M6 Recall, search, risk records.** Expected guarded (read-only commands, behaviour 0; the new journal
  event is forgeable-protected). Workflow feature. Consumes: M4, M5. Produces: `state.py recall --files …
  [--budget N] [--kinds …] [--all-risks] [--json]` with the §I4 header and line forms and the `--json`
  shape; `state.py memory search QUERY [--kind] [--by] [--file] [--task] [--since] [--until] [--limit]
  [--offset] [--json]`; `state.py memory risk add|close`, `state.py memory risks`; `rank_recall(candidates,
  files, budget, max_items)`, `match_search(entry, tokens, filters)`, `tokenize(text)`,
  `parse_known_risks(text) -> (risks, leftovers)`; the `risk_recorded` event, refused by `state.py event`.
  Proof: A2 for `FileHistory` (budgets 300, 1 500, 5 000 on M1's 10 000-task history: bytes ≤ budget × 3.5,
  `more` correct; recall over the legacy fixture equals recall over packages migrated from it); A12's
  parser half (rendering parsed `known-risks.md` entries reproduces each section byte for byte); the
  files-mode append and the amend refusal of `risk add` when `known-risks.md` is outside the task's files
  (C4); a `--budget` smaller than one line gives the header and the `more` count, exit 0; the recall header
  names the excluded task in flight.
- **M7 Pre-push validator, enable and disable.** **Expected full** (it changes install and what a push may
  carry). Workflow feature. Consumes: M4, M5. Produces: `hooks/memory-pre-push.py` with the §I5 contract
  (hook form, `--range`, `--tree`; exit 0/1/3; stderr lines `memory-pre-push: <ref>: V<n>: <path>[:<line>]:
  <what> — fix: <command>`, at most 40, then the summary), `validate_range(repo, old, new, local) ->
  list[Finding]` with V1–V6, V8, V9 (V7 arrives in M11), `GitTreeReader(repo, sha)`, `install_hook(root)
  -> "installed"|"current"|"foreign"|"hookspath"`, `remove_hook(root)`, the shim of §D10,
  `state.py memory enable [--author] [--period] [--index]` and `memory disable` (human route, exit 5
  otherwise), `memory verify --range OLD..NEW`; the V5 scope line amended in the spec. Proof: A8 (every
  scenario listed there, in temporary repositories; the 59-task repository validates in under 500 ms as a
  sanity bound); A10 for `enable` and `disable`; a package with CRLF or a BOM is a V1 finding naming the
  line and the fix; the hook exits 0 with no output when `memory.json` is absent at T.
- **M8 Skill and documentation text.** Expected light (prose; `tests/test_instruction_budget.py` bounds
  it). Workflow feature. Consumes: M6, M7 (the commands the text names). Produces: `rr-plan` and
  `rr-build` call `recall` at task start with the task's files; `rr-build`, `rr-review`, `rr-ship` record
  and close risks with `memory risk` (R12); `docs/local-memory.md` (setup, the id shape, packages, the
  hook, CI recipe, recovery, limits, the M1 baseline numbers); `docs/architecture.md` and the state README
  template say where the archived state and the record live (FC2); `safety.md` template names the memory
  toggles as human-route commands; the three FC9 risks recorded with `memory risk add`. Proof:
  `tests/test_skills_surface.py`, `tests/test_instruction_budget.py`, `tests/test_project_update.py`
  (template history rebuilt); `grep -rn known-risks.md skills/rr-*/SKILL.md` shows only the `memory risk`
  wording.
- **M9 Migration of tasks, risks and logs.** **Expected full** (a migration of what a project commits).
  Workflow feature. Consumes: M4 (`sources="tracked"`), M7 (`GitTreeReader`), M6 (`parse_known_risks`).
  Produces: `state.py memory migrate --report | --apply [--risks] | --move-logs --confirm-delete NAME`
  (§D12: report to `.ai/local/memory/migration-report.md`; backup
  `.ai/local/memory/backup-<UTC>.tar`; batches grouped by `closed_at` period with `source: migration`;
  keys already sealed skipped; the risks step replaces `known-risks.md` with a stub of at most 10 lines
  pointing to `state.py memory risks --md` (OQ4); `--move-logs` prints the `git rm --cached` line and
  writes `.ai/local/memory/logs-to-rm.txt`). Proof: the report on the migration fixture (keys, instance
  splits, directory name against the `task` field, kept and dropped counts, the logs with bytes, risk
  entries parsed and unparsed, duplicate titles); `--apply` twice adds nothing; two clones of the fixture
  produce identical rids; A12 (rendering the migrated risks reproduces the file's sections byte for byte);
  a task with incomplete coverage is reported, not exported.
- **G2 (human, this repository, after M9).** `state.py memory migrate --report`, read it; `--apply`, then
  `--apply --risks`, one commit (`memory: migrate 59 tasks and known-risks.md into packages`); `--move-logs
  --confirm-delete <author>` and the printed `git rm --cached`, a second commit (`memory: drop 135 committed
  verify logs from the tree`, C3); then `state.py memory enable --period quarter`, a third commit with
  `.ai/policies/memory.json` and `memory status` showing the hook `installed`. Tick here: `[x]`.
- **G3 (human).** From M1's baseline and M6's timings: if `FileHistory` recall p95 exceeds 300 ms or search
  exceeds 1 s at 1 000 tasks, M10 runs; otherwise M10 is skipped and this line records the numbers and the
  decision (Q5). Tick here: `[x]` — numbers (`tools/benchmark-memory.py`, seed 1, 4 KB journals): at 1 000
  tasks FileHistory recall 129–165 ms and search 118–148 ms, under the threshold; at 10 000, 1.4–1.6 s and
  1.3–1.6 s, the index 0.73 s and 0.31 s. M10 ran anyway, unconditionally, by the developer's decision of
  2026-10-28 (T-2026-10-28-011); the index stays opt-in (`--index sqlite`).
- **M10 SQLite index** (only past G3). Expected guarded (a local, derived store). Workflow feature.
  Consumes: M5, M6. Produces: `SqliteHistory(root, cfg)` with `refresh()` and `rebuild()`, the §I3 DDL
  (`PRAGMA user_version=1`, WAL, `busy_timeout=5000`, FTS5 as a prefilter only, detected on `:memory:`),
  `state.py memory rebuild`, `--index none|sqlite` on `enable` and in `.ai/local/memory/config.json`,
  `AI_MEMORY_NO_FTS=1` for tests, `memory status` lines for the index and FTS5. Proof: A2's differential
  (byte-identical recall and search across `FileHistory`, `SqliteHistory`, `SqliteHistory` without FTS5
  on 200 seeded file sets); A5 (budgets written into `docs/local-memory.md` and asserted ×
  `AI_TIMED_FACTOR`); a busy writer makes recall fall back to files and say so; deleting the index file
  loses nothing (`rebuild` reproduces it).
- **M11 Cleanup, restore, redact.** **Expected full** (irreversible on the tree; the gate of §D6).
  Workflow feature. Consumes: M5, M7. Produces: `state.py memory cleanup ID…|--all --confirm-delete NAME`
  (human route; the R22 conditions; boundary B6 as `os.replace(.ai/reports/<id>, .ai/state/logs/<id>/report)`
  with a copy, verify and remove fallback across filesystems), `memory restore ID…|--all`, `memory redact
  RID --field F --why TEXT` (human route; the `redaction` entry and the rewritten line), `memory verify
  --fresh-clone`, check V7 in the hook, `usage-report --task` falling back to the seal's window after
  cleanup (R20). Ships with `cleanup: false`. Proof: A9 for B6 and `--fresh-clone` exits 0; the restore
  round-trip (a clone without the raw files gets a rendered `task.md` marked "restored from record" and an
  `events.jsonl` with `data.restored: true`); A10 for `cleanup` and `redact`; V2 accepts a redacted rid;
  the cross-filesystem case with `.ai/state/logs` on another mount.
- **M12 Pack and end to end.** Expected guarded. Workflow feature. Consumes: everything above. Produces:
  `state.py memory pack --period P --confirm-delete NAME` (human route; own author, closed periods,
  canonical order, rid set preserved, batches removed), and `tests/test_end_to_end.py` walking enable →
  start → close → record → pre-push → fresh clone → show under `AI_E2E=1`. Proof: A1 (long-lived branches:
  at most 8 tracked files under `.ai/memory/` and no closed task's `.ai/reports/T-*` directory with
  `cleanup: true`; branch per task after `pack`: at most 8 plus the current quarter's batches; the monthly
  counts printed, at most 24); V2's rid-superset check over a pack; `verify_command` once to the end, then
  `e2e_command` once.
- **G4 (human, after M11 and ten real closes in packages mode).** `state.py memory verify --all` and
  `--fresh-clone` both exit 0; set `cleanup: true` in `.ai/policies/memory.json`; run `memory cleanup --all
  --confirm-delete <author>`; commit. From then on close cleans up its own task. Tick here: `[ ]`.

## Risks

**Riskiest rows: M4 and M5.** M4 can lose a decision silently (C6, behaviour 2): its proof is the coverage
accounting over every fixture and the one-off run over the 59 real directories, and cleanup stays off
until G4, so the committed per-task directories remain the cross-check that V5 compares on every push. M5
touches the close path every task ends with: its proof is the crash injection at each boundary and the
files-mode characterization (A6). Neither can move earlier: M4 needs M2's fixtures and M3's id regexes; M5
needs M4. M4 is already the split of spec steps 4 and 5 into one reviewable unit; splitting it further
would review the format twice.

What could break, and how it would show:

- **`next_task_id` callers.** Only `next_task_id` knows the id shape (`state.py:446-452`); the `T-*` glob
  in `tools/journal-summary.py:30` still matches; the path-guard pattern `.ai/reports/[^/]+/` still
  matches. A script of the developer's that parses `-NNN` breaks: `docs/local-memory.md` says so.
- **The guard and `state.py`'s own writes.** `.ai/memory/` and `.ai/local/memory/` join
  `protected_config_patterns`, so the path guard refuses an agent's direct write there while `state.py`
  commands (the only writers) pass, as they do today for `.ai/state/`. M5 re-records the guard golden and
  the characterization suite proves the diff is additive (A7). If a `state.py memory export` were refused,
  it would show as a deny in the journal on the first close — the M5 e2e case runs close through the real
  hook.
- **`sensors.snapshot_tree` and fact (b).** An export while another task is in flight changes the tree
  under `.ai/memory/`; without R26 that task's fact (b) turns red at close. M5 adds the exclusion with a
  test; in files mode the directory is absent and hashes do not change.
- **Inventory tests pinning `hooks/*.py`.** A test that enumerates the hooks directory (the install and
  Codex suites) fails when `memory-pre-push.py` appears; M7 updates it. The installer copies the file into
  the runtime homes, which is harmless: it is a git hook, not a runtime hook, and `context-guard.py` is
  unchanged (R18).
- **V5 against legacy ids.** Scoped as decided above; without the scoping the first push after `enable`
  would list 59 findings.
- **Order of G2.** `enable` before the migration would make every push fail V5 for the legacy tasks and
  export new closes beside unmigrated directories; the plan puts `enable` last in G2.
- **`.ai/policies/memory.json` and `/rr-setup --update`.** The update merges managed policy files and hashes
  `risk-tiers.json`; `memory.json` is project-owned and must not be treated as a shipped template. No
  template is created; `tests/test_project_update.py` gains a case in M8 that an existing `memory.json`
  survives `--update` untouched.
- **Two local processes.** Two sessions closing at once serialise on `.ai/local/memory/lock` (`flock`,
  skipped where `fcntl` is absent, as `state.py` already does); the SQLite side uses `BEGIN IMMEDIATE` and
  `busy_timeout`. On a platform without `fcntl` the batch write is last-writer-wins within one clone;
  `docs/local-memory.md` says so.
- **Cross-filesystem B6.** `os.replace` fails with `EXDEV` when `.ai/state/logs` is a symlink to another
  mount; M11 falls back to copy, verify, remove, and tests it.
- **Clock skew.** The minute in the id comes from the machine's clock; a wrong clock only misorders ids
  and raises the chance of a same-minute same-slug conflict, which import reports (R9).
- **Slug derivation.** A goal with only Cyrillic or punctuation transliterates or falls back to `task`;
  M3 tests both; `start --slug` is the escape.
- **Hand-edited packages.** CRLF, a BOM or a reflowed line make V1 findings that name the line and the
  fix; nothing is merged or repaired silently.
- **Codex parity.** One `state.py`; the hook depends on no runtime; recall and close under
  `AI_RUNTIME=codex` are compared in M6 and M5.
- **Suite time.** Each task adds unittest files; the e2e walk runs only under `AI_E2E=1`
  (`testing.md:134`), and the 10 000-task histories are generated once per test module and cached in the
  test temp dir.
- **`state.py` size.** 4 321 lines today; every memory behaviour lives in `memory_*` modules and `state.py`
  gains subparsers and one call site, imported lazily (`state.py:80-83`).

**Review focus** — the five inputs the spec implies but no acceptance criterion exercises, each pinned by
the task that owns the code: (1) a goal of only Cyrillic or punctuation → `slug_of` transliterates or
returns `task` (M3); (2) `.ai/memory/` unwritable at close → the `memory:` failure line, the outbox kept,
exit 0 (M5); (3) a package with CRLF or a BOM → V1 names the line and the fix (M7); (4) B6 across
filesystems → copy, verify, remove (M11); (5) `recall --budget` below one line → header plus `more`, exit 0
(M6).

## Proof (tests)

`verify_command` (`bash tests/run-all.sh`) once to the end and `e2e_command` (`AI_E2E=1 python3 -I -m
unittest discover -s tests -p test_end_to_end.py`) once close every task, through `state.py verify --scope
all`. Per requirement:

| R | Proof | Task |
|---|---|---|
| R1 | `tests/test_task_id.py`: shape, transliteration, 24-character cut, `task` fallback, disambiguator, 1 000 ids in one minute | M3 |
| R2 | `tests/test_memory_characterization.py` (legacy ids valid; goldens) and `test_task_id.py` legacy cases | M2, M3 |
| R3 | `tests/test_memory_compact.py`: coverage equals lines on every fixture; unknown event kept | M4 |
| R4 | `test_memory_compact.py`: verbatim fields byte-equal to task.md §Questions and the G block; the 6 KB answer | M4 |
| R5 | `test_memory_compact.py`: excerpt size, `expected_fail` lines first, redaction, local pointer | M4 |
| R6 | `tests/test_memory_sync.py`: close appends entries and seal; `cleanup: true` leaves no per-task file (with M11) | M5, M11 |
| R7 | `test_memory_sync.py`: per-branch batches, rotation on period and size; A1 after `pack` | M5, M12 |
| R8 | `tests/test_memory_pre_push.py` V2; `tests/test_memory_cleanup.py` redaction | M7, M11 |
| R9 | `test_memory_sync.py`: re-import adds nothing; two seals kept as `conflict`, shown by `verify` and `show` | M5 |
| R10 | `tests/test_memory_recall.py`: tiers, budget, `more`, excluded task in flight | M6 |
| R11 | `test_memory_recall.py` (file mode) and `tests/test_memory_store.py` differential on 200 seeded file sets | M6, M10 |
| R12 | `tests/test_skills_surface.py` and a grep over `skills/rr-*/SKILL.md`; `tests/test_memory_risks.py` | M8, M6 |
| R13 | `test_memory_recall.py`: filters, paging, offline | M6 |
| R14 | `test_memory_pre_push.py`: A8 scenarios, blobs not the working tree | M7 |
| R15 | `test_memory_characterization.py` A6: same files, same output, no memory directories | M2, M5 |
| R16 | A10 in `test_memory_pre_push.py`, `test_memory_cleanup.py`, `test_memory_sync.py` (`pack`) | M7, M11, M12 |
| R17 | `test_memory_pre_push.py`: foreign hook kept, `core.hooksPath` respected, idempotent reinstall, `disable` | M7 |
| R18 | A7: no hook imports `memory_`; the hook budget tests and the dialog fast-path test unchanged | M5, M7 |
| R19 | guard golden additive; the forged-approval case in `test_memory_sync.py` | M5 |
| R20 | A11 goldens in `test_memory_characterization.py`; `usage-report --task` after cleanup | M2, M11 |
| R21 | `memory verify --fresh-clone` and `show` identity in `test_memory_cleanup.py`; `show` identity across clones in `test_memory_sync.py` | M11, M5 |
| R22 | `test_memory_cleanup.py`: every R22 condition refuses cleanup when false; ships `cleanup: false` | M11 |
| R23 | `AI_MEMORY_CRASH_AT=B2..B5` in `test_memory_sync.py`, `B6` in `test_memory_cleanup.py` | M5, M11 |
| R24 | A12 in `tests/test_memory_migration.py`; parser half in `test_memory_risks.py` | M9, M6 |
| R25 | `test_memory_migration.py`: report first, backup, tracked-only rids identical across clones, sealed keys skipped, logs moved and the `git rm` line printed | M9 |
| R26 | `tests/test_ai_task_sensors.py`: tree hash unchanged by `.ai/memory`; fact (b) unchanged by an export | M5 |
| R27 | `tests/test_benchmark_memory.py`: seeded determinism, the report's fields; G3 reads it | M1 |

## Rollback

Every row is one commit on the branch: `git revert <sha>` undoes it, in reverse order where a later row
depends on it. `memory disable` sets files mode, removes only our hook and keeps the packages and the local
data; closed tasks whose directories are still in the tree read as today. The migration's two commits
revert independently: reverting the log removal restores the 135 logs; reverting the packages commit
restores `known-risks.md` and leaves the local backup tarball in place. `memory restore --all` brings
cleaned-up directories back from `.ai/state/logs/<id>/report/`; a clone that never had them gets the
rendered, marked reconstruction (§D13). The SQLite index is a file to delete. The id change needs no data
rollback: old ids stay valid, and a task started with the new shape keeps it after a revert, because
`TASK_ID_RE` accepts both.
