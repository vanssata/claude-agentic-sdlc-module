# Spec: Compact project memory — bounded files in git, bounded context, optional local history

Intent: carried in this document (`## Intent` below). The on-record brainstorm is
`docs/sdlc/intent/compact-project-memory.questions.md` (Q1, Q2). The light plan
written from the first discussion, `docs/sdlc/plans/optional-local-memory-optimization.md`,
is an input: its "Цел и приети решения" are adopted below as decisions P1–P10;
`/rr-plan` on this spec supersedes the rest of that file.

Status: 2026-10-28, written through `/rr-spec` after a three-round brainstorm
in session, the recorded Q1–Q6, and one architect pass on STRONG. The developer
answered Q3–Q6 on 2026-10-28 (Decisions taken) and raised no correction. Ready
for `/rr-plan`. Line numbers cite the working tree of 2026-10-28
(`skills/ai-task/state.py` is unchanged against HEAD there).
This is the first of two tasks: the second refreshes
`docs/sdlc/specs/direct-mode-diet.md` (verify runs and reviews per task, where
the hours go) and is out of scope here.

## Intent

### Problem

Measured in this repository on 2026-10-28:

| | |
|---|---|
| files under `.ai/` | 675, of which 429 tracked by git |
| `.ai/reports/` | 59 task directories, 404 tracked files, 14 MB |
| of those, verify logs (`*.log`) | 135 files, 11.5 MB — committed by tasks before D4 moved logs to `.ai/state/logs/` |
| markdown (task.md, review-report.md, questions.md, review-ledger.md …) | 154 files, 1.0 MB |
| journals `events.jsonl` | 53 files, 0.8 MB, 2 235 lines; 1.5 KB min, 10.7 KB median, 60 KB max per task |
| `.ai/state/logs/` (git-ignored by its own `.gitignore`) | 215 files, 6.8 MB |
| `.ai/project/known-risks.md` | 146 KB, one file, read whole on every append |

Four problems sit behind those numbers.

1. **Files grow with every task.** A closed task leaves 2 to 30 files in git
   (tests-suite-N.log in 62 tasks, events.jsonl 52, tests-e2e-N.log 50,
   state.json 31, questions.md 30, task.md 25, sensors.json 23,
   review-ledger.md 23, lint.log 21, review-report.md 17). Newer tasks leave
   two (events.jsonl, task.md) since D4, but the count is still proportional to
   the number of tasks, and the old logs are still in the tree.
2. **Duplicate task folders are a matter of time.** The id is
   `T-YYYY-MM-DD-NNN` with NNN = the number of local report directories for the
   day + 1 (`skills/ai-task/state.py:446-452`). Two developers on two machines
   the same day both get `-001`; the directories collide on merge. The id
   shape is validated loosely (`TASK_ID_RE`, `state.py:1021`), so a new shape
   is cheap, but every old id must stay valid and referable.
3. **The record is four fifths process trace.** Of 2 235 journal lines, 1 756
   are trace (handoff_written 780, field_set 233, verify_run 209,
   step_started 191, stage_started 178, step_done 165) and 479 carry a decision
   or a fact worth keeping across tasks (task_started 52, task_closed 52,
   tier_set 52, weight_set 21, mode_set 3, plan_registered 30, scope_change 34,
   question_asked 28, question_answered 28, gate_requested 30,
   gate_approved 30, review_verdict 19, findings_closed 6, human_set 13,
   note 78, runtime_handoff 2, tier_raised 1).
4. **Nothing returns a bounded slice of the past.** The handoff frames the task
   in flight only. To learn what was decided about a file, an agent greps 59
   directories or opens known-risks.md whole; `rr-build`, `rr-review` and
   `rr-ship` append to that file and read 146 KB (about 40 k tokens) to do so.

**What a database does and does not buy.** Measured on three recent tasks:

| task | mode | active hours | verify runs | tokens | of which cache reads |
|---|---|---|---|---|---|
| T-2026-10-27-003 | guarded | 0.9 | 14 | 30.0M | 29.7M |
| T-2026-10-27-007 | full | 2.0 | 27 | 69.2M | 68.6M |
| T-2026-10-28-007 | guarded | 0.2 | 11 | 3.8M | 3.8M |

The whole suite is 651 tests in about 183 s; hooks cost 15–120 ms per tool
call over 150–200 calls a session; a journal is 10 KB. Reading files is not
where the hours go. Context volume per model call is, together with verify
runs and reviews (the second task). A local store therefore earns its place
only by making the slice that enters the context small and exact, and by
making search over a large history possible; it is not promised to speed up
anything else (P4, the benchmark decides numbers).

### Outcome (testable)

- **O1 Bounded files.** 100 closed tasks by two developers over a year add at
  most one package file per developer per period to the constant `.ai/` set
  (about 26 files today without `reports/`): about 8 files at the quarterly
  default, 24 at monthly periods (OQ5). Once cleanup is on (P7, §D6) no file
  in git is created per task; until then the per-task directory stays as the
  cross-check copy the validator reads.
- **O2 No loss of who, what, how, why, when.** For every closed task, every
  decision-bearing event (the 17 kinds in Problem 3) with its actor, time,
  runtime and the original wording of human answers and approvals is
  recoverable from git alone, in a fresh clone, without a server or anyone's
  local database; `state.py show <id>` renders it. The process trace is kept
  locally and is not promised from git (Q1).
- **O3 No duplicate ids.** An id no longer depends on how many report
  directories a machine holds: two clones that start different tasks on the
  same day get different ids; the same slug started in the same minute on
  two clones is reported as a conflict at import, never silently renamed;
  importing the same package twice adds nothing; a colliding legacy id is
  reported before migration.
- **O4 Bounded context.** At task start one command returns the decisions,
  residual risks and verdicts that touch the task's files, within a stated
  token budget, with source ids, with the same relevant results in file mode
  and in database mode. No skill reads `known-risks.md` or a report
  directory whole.
- **O5 Local search.** `state.py search` answers over the whole local history;
  at 1 000 and 10 000 synthetic tasks within budgets fixed after the baseline
  measurement (P4), never before.
- **O6 Check before push.** A push whose commits close a task without a
  compact record, or carry an invalid package, a lost record, a duplicate
  seal, or a raw log under `.ai/reports/`, is stopped locally with the exact
  fix printed; per-task directories of sealed tasks are refused only once
  cleanup is on (P7). The same validator runs in CI or on a server.
- **O7 Opt-in, reversible.** With the mode off every existing command writes
  the same files with the same output (characterization tests pin it) and no
  package, database or git hook is created. Two things change in files mode
  too, because they fix files-mode defects: the task id shape (O3, OQ1) and
  the read-only `recall` and `memory risk` commands the skills use instead of
  reading `known-risks.md` whole (O4, OQ2). `memory enable` installs the
  hook; `disable` keeps the packages and the local data.
- **O8 Legacy keeps working.** Old ids and old journals stay readable;
  `tools/journal-summary.py`, `skills/rr-status/status.py` and
  `skills/usage-report/usage-report.py` keep their answers.
- **O9 Hooks unchanged.** Nothing here runs in a per-tool-call hook; the
  budgets in `docs/hook-performance.md` hold.

### Affected users and systems

- Developers using RiskRails in a project with the mode on — two or more on
  one repository, on different machines; this repository first.
- `skills/ai-task/state.py` (`next_task_id`, the `recall` and `memory`
  subparsers, one call after `archive_v7`, the `risk_recorded` event), the
  new `memory_format.py`, `memory_compact.py`, `memory_sync.py`,
  `memory_store.py` beside it; `skills/ai-task/sensors.py` (one exclusion);
  `hooks/memory-pre-push.py` and `hooks/ai-path-guard-defaults.json` with the
  guard characterization golden; `tools/journal-summary.py`,
  `skills/rr-status/status.py`, `skills/usage-report/usage-report.py`;
  `tools/benchmark-memory.py`; `docs/local-memory.md`, `docs/architecture.md`,
  the `.ai/state/README.md` and `safety.md` templates under `skills/ai-init/`;
  the SKILL.md of rr-build, rr-review, rr-ship and rr-plan;
  `tests/test_end_to_end.py`. Staged for a human edit, outside a run:
  `.ai/policies/security.md:59-61`, `.ai/AGENTS.md:33-35`, `.ai/state/README.md`.
  Migrated once: `.ai/project/known-risks.md` and the 135 committed logs.
  Not touched: `install.sh` (a stub that exits 2, `install.sh:1-18`),
  `bin/riskrails.js` (already ships every `hooks/*.py`),
  `skills/ai-init/templates/gitignore.snippet` (already ignores `.ai/local/`);
  no `skills/project-update` migration is needed because an absent
  `memory.json` already means files mode.
- Codex runs the same `state.py`; the pre-push hook is runtime-neutral.

### Constraints and non-goals

Constraints:

- Python 3 standard library only, as all of `state.py` (its docstring,
  `state.py:9`); `sqlite3` is stdlib, FTS5 is detected and its absence
  degrades with a stated reason. Offline. Atomic writes as `state.py` does
  them (temp file + `os.replace`, `flock` where it already locks).
- C5 and non-negotiable 3: no agent commits, pushes, merges or deploys; the
  pre-push hook runs inside the human's push. An imported historical approval
  never authorises a current action.
- C1, C2: legacy behaviour gets a characterization test before it changes;
  old journals and ids stay readable.
- C3, C4: the history-access interface is its own refactoring step, verified
  before the backend; each step names its files.
- C6: a compaction that drops an approval, a scope change or a human answer
  is behaviour 2 — the cleanup stays disabled until recovery is proven (P7).
- Non-negotiable 6: a risk record carries its evidence label.
- The scope guard, the handoff and `status` keep reading the live state and
  the task's own journal while a task is in flight; compaction happens at
  close.
- The summary is extracted deterministically, without a model; an optional
  model-edited text is a separate option and never alters original decisions
  or authorship (P6).

Non-goals: a vector or graph database; a remote backend in this version
(later, through the same interface, P9); rewriting git history; speeding up
tests or analysers; changing the weight, review or verify policy (second
task); keeping the whole conversation or all raw logs in git (Q1).

### Open questions

See `## Open questions` at the end; none blocks the plan.

### Decisions taken

From `docs/sdlc/intent/compact-project-memory.questions.md`, in the order asked:

- **Q1** — "Трябва ли нов разработчик да възстановява пълната история кой какво
  кога е решил само от Git clone, без сървър и без чужда локална база?" —
  answered X by vanssa via prose at 2026-10-28T17:42:40Z: "Не е необходима
  цялата история. По задача трябва да се пази само необходимото, за да се види
  кой какво как и защо е направил. Желателна е проверка преди push за
  оптимизирана история. Трябва да се оцени дали локална база ускорява
  процесите."
- **Q2** — "Как да се групират в Git сбитите записи на приключените задачи?" —
  **A**: packages with unique names, one file per developer per period or
  batch, a new file when the period changes, no merge driver. Rejected by the
  developer: B, one `.ai/ledger.jsonl` per project merged with
  `merge=union` (depends on a merge driver not every hosting applies; line
  order after a union merge is not guaranteed); C, one directory with two
  files per task (readable in a PR, grows with every task).
- **Q3** — "Новият формат на номера на задачата да важи и във файловия
  режим?" — answered X by vanssa in session, 2026-10-28: "накъв слъг на
  задачата кратък но ясен". Read as: yes, in both modes, and the id carries
  a short, clear slug of the task instead of six random characters. The
  shape that follows is the session's call (§D2):
  `T-YYYY-MM-DD-HHMM-<slug>`, the minute kept so that two developers who
  pick the same slug on the same day still get different ids.
- **Q4** — `recall` and `memory risk` in files mode too — **A**: yes,
  read-only commands plus skill text, behaviour 0.
- **Q5** — the SQLite index only past a measured threshold — **A**: built
  when FileHistory recall p95 exceeds 300 ms or search exceeds 1 s at 1 000
  tasks in the baseline.
- **Q6** — period default — **A**: quarter, about 8 files a year for two
  developers.

From the plan's "Цел и приети решения", adopted as written:

- **P1** The mode is optional per project; file mode stays the default.
- **P2** Local work needs no internet, account, server or external model.
- **P3** SQLite holds the operational history and the indexes; the database
  and its temporary files are outside git.
- **P4** Measurement first (`tools/benchmark-memory.py`, 100 / 1 000 / 10 000
  tasks, cold and warm, index build and query, context size returned); no
  percentage is promised before the baseline, and the database does not speed
  up tests or analysers.
- **P5** Git carries compact records of closed tasks grouped in packages; not
  the whole conversation nor all raw logs — essential decisions, motives,
  authorship, times, results and the necessary evidence. A hash of a deleted
  log is not evidence; the needed excerpt goes into the record or points to a
  kept artifact.
- **P6** Key human decisions and approvals keep their original wording; a
  missing reason is marked as unrecorded, never invented; extraction is
  deterministic.
- **P7** Cleanup after close is the riskiest stage and stays disabled until
  recovery from a package is proven; on incomplete data or failure the
  originals stay.
- **P8** A pre-push validator, installed by setup when the mode is on: fast,
  no network, no model, changes no files, prints the exact fix; existing hooks
  are kept and not duplicated; the same validator can run server-side or as a
  CI condition. It checks structure and coverage, not the semantic accuracy
  of a free summary.
- **P9** A remote backend for teams comes later through the same interface,
  with explicit conflict rules; no silent fallback to independent local state.
- **P10** No vector or graph database; no rewriting of git commits; the
  optimisation is of the tool's history, not of the code's.

From the session, recorded here as the session's proposals and accepted into
the design by the developer's choice to proceed:

- **S1** A bounded recall command (`state.py recall`) replaces reading
  `known-risks.md` and report directories at task start; same relevant
  results in both modes.
- **S2** `known-risks.md` entries become a record kind with an evidence label;
  migrating the existing file is its own step.
- **S3** Hooks never touch the database; the database is derived and
  rebuildable from the packages plus the local raw data. The session proposed
  filling it at step boundaries too; the architect pass rejected that part:
  no reader needs the task in flight in the index (recall excludes it, the
  handoff and status read the live files), and a write at `step-done` would
  make the index a second, stale copy of live data. The index is filled at
  export (close), on `memory rebuild` and by the refresh `recall` runs before
  it answers (§D7).
- **S4** The 135 committed `.log` files leave the tree by a plain `git rm` in
  the migration; history is kept (P10).
- **S5** The speed question from Q1 is answered by the measurements above: a
  database does not cut the hours; context volume does. The claim in this
  spec is bounded context and search, nothing else.
- **S6** Two separate tasks: this spec, then a refresh of
  `docs/sdlc/specs/direct-mode-diet.md` against today's numbers.

## Requirements

Outcome tags: O1 bounded files · O2 no loss · O3 no duplicate ids · O4
bounded context · O5 local search · O6 check before push · O7 opt-in · O8
legacy · O9 hooks unchanged. `§D…` and `§I…` refer to Design and Interfaces.

- **R1 (O3)** A new task id is `T-YYYY-MM-DD-HHMM-<slug>`: UTC date and
  minute, then a slug of 3 to 24 characters, `[a-z0-9]` words joined by
  `-`. `start --slug S` gives it; without the flag it is derived
  deterministically from the goal (casefold, Cyrillic transliterated, whole
  words while they fit, `task` when nothing is left). It depends on neither
  folder count, host nor user. If the id already exists as a report
  directory, a local raw directory or a sealed key, `start` appends `-2`,
  `-3`, … (at most 9, then exit 2 naming `--slug`). Evidence of the defect:
  `skills/ai-task/state.py:446-452`, `:1664-1666`. It applies in both modes
  (Q3).
- **R2 (O3, O8)** Legacy ids (`^T-\d{4}-\d{2}-\d{2}-\d{3}$`) and every id
  `valid_task_id` accepts stay valid for `start --task-id`, `memory show`,
  `recall`, `usage-report --task` and `journal-summary`. A characterization
  test pins this before R1 lands.
- **R3 (O2)** Close-time extraction is deterministic. Every source journal
  line is accounted for exactly once: as the `src` of an entry, summarised
  into a seal array, or counted as dropped by a versioned rule (KEEP_RULES
  v1, §D3). An event type the rules do not know is kept as
  `note/unknown-event` with its raw data. Each entry carries the actor
  exactly as its source line has it, the runtime, the ts and `by`.
- **R4 (O2)** Human wording is stored byte for byte from its source: question
  and option texts, answer text, approval note, rejection why, override why,
  confirm text. task.md §Questions is the source where the journal lacks the
  text (`state.py:1489-1491`, `:2119`). A text missing at the source is
  `null` and its field is listed in `unrecorded`. Nothing is paraphrased.
- **R5 (O2)** Evidence: every `expected_fail` run, the last full suite and
  the last e2e run (or its not-applicable reason) keep a deterministic,
  redacted log excerpt of at most `excerpt_max_bytes`. The full log is a
  local pointer, never a hash alone (P5).
- **R6 (O1)** In packages mode, close appends the task's entries and its seal
  to the developer's open batch under `.ai/memory/` (§D4). With
  `cleanup: true` no per-task file stays in the tree after close.
- **R7 (O1)** One package file per (developer, period, batch). A batch is
  never appended to on two branches. Rotation happens on a new period or
  above `package_max_bytes`. `memory pack` folds a closed period's batches
  into one file per developer.
- **R8 (O2)** Packages are append-only: a record (`rid`) never disappears or
  changes. The only exception is a human `redaction` entry (§D10).
  `memory pack` preserves the rid set.
- **R9 (O3)** Re-import or re-export adds nothing (rid = content hash). Two
  different seals for one key are kept side by side as a `conflict`, shown
  by `memory verify` and `memory show`, never merged.
- **R10 (O4)** `state.py recall --files … [--budget N]` returns only the open
  risks, residual findings, human and agent decisions, scope changes and
  task one-liners that touch those files, each with its source id, within
  the budget. The remainder is counted and the next command named. The task
  in flight is excluded and the header says so.
- **R11 (O4, O5)** Recall and search give byte-identical output from
  FileHistory, SqliteHistory with FTS5 and SqliteHistory without FTS5.
  Ranking and matching are one pure function shared by all backends.
- **R12 (O4)** No skill reads `known-risks.md` or a report directory whole.
  rr-build, rr-review and rr-ship record and close risks with
  `state.py memory risk add|close` in both modes
  (`skills/rr-build/SKILL.md:60,121`, `skills/rr-review/SKILL.md:52,97`,
  `skills/rr-ship/SKILL.md:94`).
- **R13 (O5)** `state.py memory search` filters by kind, author, time range,
  file and task, pages with `--offset`, and works offline over all local
  history. Its budgets come from the baseline (P4).
- **R14 (O6)** `hooks/memory-pre-push.py` checks the pushed commits' blobs
  (`git cat-file`), never the working tree. Checks, output, exit codes and
  per-ref behaviour are in §D10. It runs as a git hook locally and with
  `--range` in CI.
- **R15 (O7)** With `.ai/policies/memory.json` absent or `mode: "files"`:
  no `.ai/memory/`, no `.ai/local/memory/`, no database, no git hook. Every
  existing command writes the same files with the same output, pinned by
  characterization tests. Exceptions: R1 and the new read-only commands
  (OQ1, OQ2).
- **R16 (C5)** `memory enable`, `disable`, `cleanup`, `pack` and `redact`
  require `human_route()` as `approve` does; otherwise exit 5.
- **R17 (O7)** The pre-push hook is installed only where the hooks path
  (`git rev-parse --git-path hooks`) has no `pre-push` and `core.hooksPath`
  is unset. A foreign hook is never edited; the exact lines to add are
  printed. Reinstall is idempotent through a marker line. `disable` removes
  only our own hook.
- **R18 (O9)** No per-tool-call hook imports `memory_*` or opens SQLite.
  `hooks/context-guard.py` is unchanged. The guard golden only gains the new
  protected-path cases (R19). `docs/hook-performance.md:34-45` holds.
- **R19 (C5)** `.ai/memory/` and `.ai/local/memory/` join
  `protected_config_patterns`, so the agent may never write them.
  `state.py` never reads a package to grant or refuse anything. An approval
  entry renders as "historical — authorises nothing now".
- **R20 (O8)** `journal-summary.py`, `status.py` and `usage-report.py --task`
  keep today's answers, through the History interface introduced as a pure
  refactor (C3). After cleanup `usage-report --task` falls back to the seal's
  `started_at` and `closed_at`.
- **R21 (O2)** A fresh clone rebuilds the index from packages alone, and
  `memory show` gives the same output for every task as in the clone that
  exported it.
- **R22 (C6)** Cleanup ships disabled (`cleanup: false`). It runs for a task
  only when that task's seal is in a package in the working tree, its digest
  matches, its coverage is complete with zero skipped lines, and
  `memory verify --all` was green when the human set `cleanup: true`.
  Cleanup moves files to the local raw store; it never deletes them.
- **R23 (O2)** Crash and fault injection at each boundary B1–B6 (§D5),
  followed by a re-run, leaves the same final state and never deletes early.
- **R24 (O8, S2)** `known-risks.md` converts to `risk` entries losslessly:
  rendering the migrated entries reproduces its sections byte for byte.
  Every risk carries an evidence label (non-negotiable 6); an entry without
  one is labelled `RISK` with `label_derived: true`.
- **R25 (O1, S4)** The migration reports first (keys, splits, collisions,
  kept and dropped counts, logs), then makes a local backup, converts closed
  legacy tasks from git-tracked sources only (so every clone produces
  identical rids), skips keys already sealed, moves the 135 committed `.log`
  files into `.ai/state/logs/<id>/legacy/` and prints the `git rm --cached`
  for the human.
- **R26** `sensors.snapshot_tree` also leaves out `.ai/memory` (beside
  `.ai/state` and `.ai/reports`, `skills/ai-task/sensors.py:123-124`), so an
  export while another task is in flight does not turn that task's fact (b)
  red. In files mode the directory is absent and tree hashes do not change.
- **R27 (P4)** `tools/benchmark-memory.py` measures before any store exists:
  100, 1 000 and 10 000 seeded synthetic tasks, long journals included; it
  reports time, files read, bytes returned, storage, cold and warm, build and
  query apart. The SQLite step proceeds only past the Q5 threshold.

### Acceptance criteria

- **A1 (O1)** Two-clone simulation with a bare remote
  (`tests/test_memory_sync.py`): 100 closes by two authors over 12 months,
  quarterly periods, `cleanup: true`. Long-lived branches: at most 8 tracked
  files under `.ai/memory/` and no `.ai/reports/T-*` directory of a closed
  task. Branch per task: after `memory pack` of the closed quarters, at most
  8 files plus the current quarter's batches. The test also prints the
  monthly counts (at most 24).
- **A2 (O4)** For budgets 300, 1 500 and 5 000 over a synthetic history of
  10 000 tasks: output bytes ≤ budget × 3.5, `more` correct, output
  byte-identical across FileHistory, SqliteHistory and SqliteHistory without
  FTS5 on 200 seeded file sets; recall over the legacy fixture in files mode
  equals recall over the packages migrated from it.
- **A3 (O2)** Over a fixture copy of this repository's reports (pre-WP2,
  backfilled, questions, gate, review, v7, multi-instance) and, once, all 59
  real directories: export, import, export is byte-identical; every required
  field per kind is present; coverage is 100 %; answers, notes and why texts
  are byte-equal to their sources.
- **A4 (O3)** Two clones close tasks concurrently and merge with plain
  `git merge`, no driver: no conflict under `.ai/memory/`, the rid set equals
  the union, re-import adds nothing. 1 000 `start` calls in one minute with
  the same goal give 1 000 distinct ids through the local disambiguator; the
  same slug started in the same minute in two clones is reported as a
  `conflict` at import; legacy ids stay accepted.
- **A5 (O5)** The benchmark runs search and recall at 1 000 and 10 000
  tasks; the budgets are written into `docs/local-memory.md` after the
  baseline and asserted × `AI_TIMED_FACTOR`.
- **A6 (O7)** Files-mode characterization: the outputs and file lists of
  `start`, `verify`, `close`, `handoff` and `status` are unchanged except the
  id (Q3), and `.ai/memory/` and `.ai/local/memory/` are absent after every
  command.
- **A7 (O9)** The guard golden diff is additive only; no hook file imports
  `memory_`; the dialog fast-path test and the hook budget tests are
  unchanged.
- **A8 (O6)** Pre-push scenarios in temporary repositories: valid push;
  invalid package (V1); rid loss (V2); duplicate seal (V3); bad digest (V4);
  closed task without record (V5); a log under reports (V6); a closed-task
  directory with cleanup on (V7); new branch; deletion; tag; three refs at
  once; foreign hook kept and snippet printed; `core.hooksPath` respected;
  reinstall idempotent; mode off gives exit 0 with no output; the 59-task
  repository validates in under 500 ms as a sanity bound, the budget fixed
  after the baseline.
- **A9 (O2)** Crash injection at B1–B6 followed by a re-run gives the
  expected final state, and no file disappears before its seal is verified;
  `memory verify --fresh-clone` exits 0.
- **A10 (C5)** `memory enable`, `disable`, `cleanup`, `pack` and `redact`
  exit 5 without `human_route`; a forged approval entry changes nothing.
- **A11 (O8)** `journal-summary.py`, `status.py` and `usage-report --task`
  equal their characterization goldens before and after the History
  refactor, and `usage-report --task` still answers after cleanup.
- **A12 (R24)** Rendering the migrated risks reproduces each section of
  `known-risks.md` byte for byte.

## Design

This section carries what the plan and its reviewers must not reopen; the
architect's working notes are folded into it.

### §D1 Authority per mode

| data | files mode | packages mode | SQLite index |
|---|---|---|---|
| task in flight | `state.json`, `.ai/reports/<id>/{events.jsonl,task.md}` | the same, unchanged | never |
| closed task | `.ai/reports/<id>/` (committed) | the package entries (git); `.ai/reports/<id>/` is a cross-check copy until cleanup | derived only |
| process trace, logs, archived state | `.ai/state/logs/<id>/` (local) | the same, plus `report/` after cleanup | derived only |
| risks | `.ai/project/known-risks.md` | `risk` entries; known-risks.md becomes a stub (OQ4) | derived only |

There are never two independently edited copies. Deleting the index loses
nothing; it is rebuilt from the packages and the local raw data.

### §D2 Task id

`T-2026-10-28-1739-compact-memory`: the date and minute keep the ids of one
day in order beside the legacy ones, and the slug says what the task is (Q3:
"кратък но ясен"). The slug is `[a-z0-9]+(-[a-z0-9]+)*`, 3 to 24 characters,
from `start --slug` or derived from the goal by one pure function in
`memory_format.py` (`slug_of(goal)`): casefold, transliterate Cyrillic with a
fixed table, keep `[a-z0-9]`, join with `-`, take whole words while they fit,
`task` when nothing is left. The id satisfies `TASK_ID_RE`, so the path-guard
patterns `.ai/reports/[^/]+/` still match. Uniqueness: locally, `start`
checks the report directories, the local raw store and the sealed keys and
appends `-2`, `-3`, … on a hit; across clones, two developers would have to
start the same slug in the same UTC minute, and that case surfaces at import
as a `conflict`, never as a rename. Legacy keys are `(task_id, inst)`: a
legacy journal holding several `task_started` segments (the way id reuse
shows up today) splits into instances 1..n, and the migration report lists
each split. Rejected for this choice: six random characters (the architect's
proposal, collision-free but opaque; the developer asked for a readable
slug) and the slug without the minute (same-day same-slug collisions across
machines would stay silent until import).

### §D3 The compact record (format 1)

Each closed task becomes N entries plus one **seal** (`kind: "task"`, the
highest `seq`). One JSON object per line; the line is the canonical form
(`sort_keys`, `separators=(",",":")`, `ensure_ascii=False`, LF). The rid is
`"r1-" + sha256(line without rid)[:24]`. The seal's `digest` is the sha256 of
the sorted rids of the other entries, so a partial export is detectable.

What Q1 requires per task, and where it is mandatory:

| Q1 | kept in |
|---|---|
| who | `actor`, `by`, `runtime` on every entry; seal `people{started_by, humans[]}`, `runtimes[]`; answer, approval and override carry their own by/via/actor |
| what | seal `goal`, `workflow`, `result`, `files[]`, `changes[{path,status,added,deleted,binary}]`, `code{base_commit,base_tree,final_tree}` |
| how | seal `mode`, `w`, `axes`, `steps[]`, `stages[[stage,ts]]`, `verify_runs[[n,scope,exit,tree,expected_fail]]`, `facts{a,b}`; the `weight`, `scope`, `verify`, `review` entries |
| why | `question` (verbatim question, options, answer), `approval` (note, why), `override.why`, `scope.why`, `note` (decision, rejected, failed, with why or error), `review.findings` |
| when | `ts` on every entry; seal `started_at`, `closed_at`; answer `at`; approval `requested_at`, `at` |

KEEP_RULES v1 (`memory_format.KEEP_RULES[1]`), one row per journal event:

| journal event | rule |
|---|---|
| task_started, task_closed | seal fields |
| weight_set, weight_raised, tier_raised | `weight` |
| tier_set | schema < 7: `weight` with `change: legacy_tier`; schema 7: summarised (compat duplicate, `state.py:3255`) |
| mode_set, human_set | `override` |
| plan_registered, scope_change | `scope` |
| question_asked + question_answered | one `question` per qid, merged with task.md §Questions |
| gate_requested + gate_approved or gate_rejected | one `approval` per gate_id, merged with the G block |
| review_verdict + findings_closed | `review` per pass, findings parsed from the FINDINGS block |
| verify_run | every run into seal `verify_runs`; evidence runs (R5) into `verify` with an excerpt |
| note, field_set, plan_drift, review_budget_refused, legacy | `note` (`note_kind` = data.kind, `field`, or the event) |
| runtime_handoff | `handoff` |
| risk_recorded (new) | `risk` |
| stage_started, step_started, step_done | summarised into seal `stages[]`, `steps[]` |
| handoff_written, schema_migrated, model_fallback, missed_reroute, decision_*, consent_* | dropped, counted in `counts.dropped{event:n}`; a dialog pick id survives as `pick` on the approval, answer or override it produced |
| unknown type | `note` with `note_kind: unknown-event` and `raw` |

Kept in git: all human texts, verbatim and uncapped. Agent texts (goal, why,
note, finding) are capped at 2 000 characters and listed in `truncated`. Each
evidence run keeps an excerpt of at most 1 KB: the last 12 non-empty lines,
ANSI stripped, with up to 10 `FAIL:` or `ERROR:` lines first for
`expected_fail` runs, passed through a fixed redaction regex set. Pointed to
(local): full logs, the full review report, the raw journal with its trace,
the archived `state.json`, the dialog trace; `src` pointers look like
`events.jsonl:14`, `task.md#Q2`, `state.json#verify.runs[9]`,
`log:.ai/state/logs/<id>/suite-10.log`. Never kept: prompts
(`session.json`), handoff texts, transcripts. There is no stored summary:
the "кратко резюме" of plan §4 is the rendered `memory show` view, derived
on demand, so no model text and no second copy exist.

Sources per field: at close, `state.json` (local), then task.md, then the
journal. In migration mode (R25) only tracked files: the journal, task.md, a
legacy task's committed `state.json`, committed logs. A torn line is counted
in `counts.skipped` and blocks cleanup for that task.

### §D4 Package files

- Path `.ai/memory/<period>.<author>.<batch>.jsonl` for a batch,
  `.ai/memory/<period>.<author>.jsonl` for a pack; the directory is flat.
  Period is `YYYY-MM`, `YYYY-Qn` or `YYYY` (config, OQ5). Author is the slug
  from local config (default the slug of `$USER`, the same value as `--by`,
  `state.py:4206`). Batch is four random base32 characters. Line 1 is the
  header; entries follow.
- Open batch: `.ai/local/memory/batches.json` maps `{"<branch>": "<file>"}`
  (`HEAD@<sha8>` when detached). Export appends to the branch's open batch
  when the file is in the working tree, its header matches the author, its
  period is the current one and its size is under `package_max_bytes`;
  otherwise it opens a new batch. A branch never appends to another branch's
  batch, so merging two branches only adds files; two clones of one
  developer have separate bookkeeping and so separate names.
- Expected counts: long-lived branches give one file per developer per period
  (Q2's case); branch-per-task gives one file per branch with closes until
  `memory pack`.
- `memory pack --period P`: run by a human on the default branch for a period
  that has ended, over the running author's own batches only; writes
  `<P>.<author>.jsonl` in canonical order (seal `closed_at`, key, seq), rids
  deduplicated, and removes those batches. Two developers never write the
  same pack file; the validator's rid-superset check (V2) proves nothing was
  lost.
- A merge conflict anyway (a cherry-pick, say): keep both sides' lines in any
  order and drop the markers. No reader depends on line order;
  `memory verify` checks the result; `docs/local-memory.md` says so.

### §D5 Close-time pipeline (packages mode; files mode returns after `archive_v7`)

`cmd_close_v7` → `archive_v7`, both unchanged → `memory_sync.after_close`:

| boundary | step | crash here, then re-run |
|---|---|---|
| B1 | archive done, state removed | closed, not exported: `memory status` lists it, the next `close` exports it (at most 5 pending), pre-push V9 stops a push |
| B2 | `compact_task` → `.ai/local/memory/outbox/<key>.jsonl` (tmp + replace) | no outbox: compact again, deterministic, same rids |
| B3 | export under `flock(.ai/local/memory/lock)`: read the batch, add the rids it lacks, write tmp, fsync, `os.replace` | before the replace the package is unchanged; after it the re-run finds every rid present and does nothing |
| B4 | read back: parse the package, compare the seal digest with the outbox, delete the outbox | a failure keeps the outbox; close prints `memory: export of <id> failed (<reason>) — the task is closed; 'state.py memory export <id>' retries` and exits 0 |
| B5 | index import (`index: sqlite` only), one `BEGIN IMMEDIATE` | sets `meta.stale`; the next recall refreshes or falls back to a file scan |
| B6 | cleanup (`cleanup: true` only): `os.replace(.ai/reports/<id>, .ai/state/logs/<id>/report)` | atomic on one filesystem; source gone and destination present means done |

Close prints `record: .ai/memory/<file> (+N entries, <id> sealed, coverage L/L lines)`.
Fault injection: `AI_MEMORY_CRASH_AT=B2..B6`, test-only, read only by `memory_sync`.

### §D6 Deferred cleanup and the recovery proof

v1 ships with `cleanup: false`: per-task directories are still committed, and
the validator cross-checks them against the record on every push (V5).
Recovery is proven when `memory verify --all` exits 0 (every task with both a
committed journal and a seal has complete coverage and a matching digest),
`memory verify --fresh-clone` exits 0 (a local clone into a temp dir, rebuilt
from packages only, gives identical `show` output for every key), and at
least 10 tasks have closed in packages mode. Then the human sets
`cleanup: true` and runs `memory cleanup --all --confirm-delete <author>`
(human route); from then on close cleans up its own task (B6). Nothing is
ever deleted from the local raw store in v1.

### §D7 The History interface (`memory_store.py`)

A `History` protocol with one pure ranker and one pure matcher shared by all
backends. **FileHistory** parses `.ai/memory/*.jsonl`, plus legacy
`.ai/reports/T-*` without a seal through `memory_compact` in tracked mode,
plus `known-risks.md` through its parser. **SqliteHistory** is
`.ai/local/memory/index.sqlite3`: WAL, `busy_timeout=5000`, writers on
`BEGIN IMMEDIATE`, `PRAGMA user_version=1`, a mismatch means rebuild. Refresh
compares `(path, size, mtime_ns)` and hashes only a changed file. A busy
writer or any error makes recall and search fall back to FileHistory, and
the header says so. FTS5 is detected by creating a virtual table on
`:memory:`; without it, `meta.fts5=0`, a full scan, the same results, and
`memory status` says "FTS5 unavailable in this SQLite <ver>: search scans;
results identical, slower". Where FTS5 exists it only prefilters candidates;
the Python matcher decides.

### §D8 Recall, search, show

- Touching: an entry's own paths are the seal's files ∪ changes,
  `scope.added`, `risk.where`, `finding.where` (`:line` stripped); entries
  without paths inherit the seal's. Two paths match on equality, on
  `fnmatch` either way when either side has a glob, or on containment of a
  directory prefix either way.
- Tiers, in order: open risks; unresolved review findings (BLOCKER > HIGH >
  MED > LOW > INFO); human decisions (answers whose actor is human or whose
  `by` is a human name, overrides, approval notes, rejections); agent notes
  (decision, rejected, failed); scope changes with why; task one-liners;
  accepted or ticketed risks. Within a tier: ts descending, then rid.
  Superseded entries and fixed risks are excluded and counted.
- Budget: `ceil(utf8_bytes / 3.5)` tokens, deterministic and conservative for
  ASCII. Default 1 500 (OQ9), maximum 8 000, at most 40 items, one line per
  item of at most 300 characters, built only from fields that both tracked
  and close sources provide (this is what makes R11 hold across modes).
- Search: tokens `[^\W_]+`, casefolded (matching unicode61); an entry matches
  when every query token is a prefix of one of its tokens and the filters
  hold; order ts descending then rid; no bm25, because file mode cannot
  reproduce it.
- Show: a key renders as Markdown (default) or JSON; an approval line ends
  "(historical — authorises nothing now)"; a task in flight renders through
  the adapter under "in flight — live state"; conflicting seals render as
  version a and version b.

### §D9 Risk records

`memory risk add` with a task in flight emits the new `risk_recorded`
journal event (in `FORGEABLE_EVENTS`, so `memory risk` is its only writer),
compacted at close; with no task in flight it writes a standalone entry
(`task: null`) to the open batch. `memory risk close RKEY --status … --why …`
appends a `risk` entry with `supersedes`. In files mode `risk add` appends
the existing template (`known-risks.md:7-16`) plus a `**Label**:` line and
`risk close` rewrites that entry's `Status` line; if a task is in flight and
`.ai/project/known-risks.md` is not among its files, the command refuses and
names `start --amend --files "+.ai/project/known-risks.md" --why "…"` (C4,
and it avoids a red fact (b)). The rkey is
`R-<slug(title)[:40]>-<sha256(title)[:4]>`; the migration reports duplicate
titles.

### §D10 Pre-push validator

- Inputs: git passes `argv[1]` (remote) and `argv[2]` (url); stdin carries
  `<lref> <lsha> <rref> <rsha>` lines. CI uses `--range OLD..NEW` or
  `--tree REV`.
- Per ref: a deletion (lsha all zeros) or a `refs/tags/*` ref is skipped;
  rsha known locally gives O = rsha; a new branch (rsha zeros) gives O = the
  merge-base of lsha with `refs/remotes/<remote>/HEAD`, else the nearest
  `refs/remotes/<remote>/*`, else none (structure checks only); T = lsha.
  Several refs are checked one by one and the findings grouped per ref.
- Mode: the hook reads `.ai/policies/memory.json` from T (`git show`). An
  absent file or files mode means exit 0 with no output.
- Checks, with one `ls-tree`, one `diff --name-status O T -- .ai` and one
  `cat-file --batch` for every blob:
  - V1 every package changed in O..T parses: header, JSON, schema per kind,
    rid equal to the hash, lines ≤ 64 KB, name matching its header;
  - V2 rids(O) ⊆ rids(T) ∪ redacted(T);
  - V3 each key has one seal, or seals chained by `supersedes`; a new-shape
    key with two unchained seals is refused; a legacy duplicate is allowed
    when a `conflict` entry records it;
  - V4 each seal's `entries` count and digest match its key's entries;
  - V5 every `.ai/reports/<id>/events.jsonl` at T containing `task_closed`,
    for an id matching `NEW_ID_RE` or a legacy id that already has a seal in
    a package, has a seal at T, and each of its kept lines is the `src` of an
    entry (an unmigrated legacy task is listed by `state.py memory status`,
    never by the hook — plan, "V5 scope");
  - V6 no `*.log` added under `.ai/reports/` in O..T; nothing under
    `.ai/local/` or `.ai/state/logs/` and no `*.sqlite3*` in T;
  - V7 with `cleanup: true`, no `.ai/reports/<id>/` of a sealed task is added
    or kept in T; a task in flight (no `task_closed`) may be pushed;
  - V8 a package between `package_max_bytes` and twice that warns; above
    twice it is refused;
  - V9 (local runs only) no `.ai/local/memory/outbox/*` exists; one that does
    means an export is pending.
- Output (stderr): `memory-pre-push: <ref>: V<n>: <path>[:<line>]: <what> — fix: <exact command>`,
  at most 40 lines, then `… N more — state.py memory verify --range <O>..<T>`,
  then `checked <k> packages, <m> tasks in <ms> ms`.
- Exit codes: 0 ok; 1 findings, the push stops; 3 validator error, fail
  closed, the message names `memory verify` and that the human may use
  `git push --no-verify` (the agent cannot: `hooks/guard/git.py:219`). No
  python3 or no validator script: the shim prints one warning and exits 0,
  because that is an unchecked push, not a finding.
- Redaction (a secret in an excerpt): `memory redact <rid> --field <f> --why "…"`
  (human route) appends a `redaction` entry and rewrites the target line with
  the field set to `"[redacted]"`; the line gets a new rid and the old one is
  listed in `redacted(T)`, which is what V2 allows.
- Install: `memory enable` writes the shim below to
  `$(git rev-parse --git-path hooks)/pre-push` (`chmod 755`); it refuses to
  write and prints a snippet instead when `core.hooksPath` is set or a
  foreign hook exists (the snippet saves stdin to a temp file and feeds it to
  both the validator and the user's hook, because pre-push stdin can be read
  only once); `install_hook` returns `installed|current|foreign|hookspath`.

```sh
#!/bin/sh
# riskrails-memory-pre-push 1 — written by 'state.py memory enable'; 'state.py memory disable' removes it
for v in "<abs path of hooks/memory-pre-push.py at enable time>" "$HOME/.claude/hooks/memory-pre-push.py" "${CODEX_HOME:-$HOME/.codex}/hooks/memory-pre-push.py"; do
  [ -f "$v" ] && exec python3 -I "$v" "$@"
done
echo "riskrails memory: validator not found — this push is not checked" >&2; exit 0
```

The validator finds `memory_sync` and `memory_format` at
`<own dir>/../skills/ai-task/`, the same layout in a checkout, `~/.claude`,
`~/.codex` and the plugin cache; the installer needs no change.

### §D11 Configuration

Project level, committed: `.ai/policies/memory.json` (§I6), edited by a human
through `memory enable|disable`; the agent may never write it (the
`.ai/policies/*.json` guard). Turning the mode on switches every teammate's
next close (OQ7). An unknown higher `schema` makes `memory` commands exit 2,
while close still archives in files mode with a warning; a newer pre-push
catches the gap. Per developer, git-ignored: `.ai/local/memory/config.json`
(author, index) — the index is a local choice because the database is local
and derived.

### §D12 Migration (`state.py memory migrate`, not a `project-update` migration)

An absent `memory.json` already means files mode, so `.ai/VERSION` stays and
no `0009` is needed; the commands reuse the framework's contracts (report
first, originals kept, deletion only with `--confirm-delete NAME`).

1. `--report` (read-only) writes `.ai/local/memory/migration-report.md`: per
   directory the keys (instances split), directory name against the
   journal's `task` field, journal absent (state-only, pre-WP2: compacted
   from `state.json` `history[]` as `source: migration`, `actor: migration`),
   backfilled lines; per kind the kept and dropped counts; the 135 logs with
   bytes; known-risks entries parsed and unparsed, duplicate titles; keys
   already sealed (skipped).
2. `--apply` first writes `.ai/local/memory/backup-<UTC>.tar` of
   `.ai/reports/` and `known-risks.md` (stdlib `tarfile`), then converts
   every closed task into batches grouped by its `closed_at` period (author
   = the migrating developer, `source: migration`), ends with read-back and
   the coverage report; a task with incomplete coverage is reported, not
   exported.
3. `--apply --risks`, a separate step: converts known-risks.md to `risk`
   entries, verifies the byte-for-byte rendering, replaces the file with a
   stub (OQ4).
4. `--move-logs --confirm-delete <author>` (human route): moves the 135
   `.log` files into `.ai/state/logs/<id>/legacy/` and prints
   `git rm --cached --quiet --pathspec-from-file=.ai/local/memory/logs-to-rm.txt`
   for the human; its own commit, under C3.

### §D13 Rollback

`memory disable` sets mode `files`, removes our hook only, keeps the packages
and all local data. Closed tasks whose directories are still in the tree
read as today. For tasks already cleaned up, `memory restore <id>|--all`
moves `.ai/state/logs/<id>/report/` back; a clone that never had the raw
files gets a rendered `task.md` marked "restored from record" plus an
`events.jsonl` rebuilt from the entries, each line with its stored `actor`
and `data.restored: true` — as in migration 0002, a reconstruction is never
passed off as observation. Raw logs come back only from the local backup or
from git history.

### §D14 Modules (names as in the plan)

- `skills/ai-task/memory_format.py`, pure, no I/O: `FORMAT`, `KINDS`,
  `REQUIRED`, `KEEP_RULES`, `classify`, `canonical`, `make_rid`,
  `seal_digest`, `validate`, `package_name`, `parse_package_name`,
  `parse_package`, `period_of`, `new_task_id`, `NEW_ID_RE`, `LEGACY_ID_RE`,
  `slug_of`, `est_tokens`, `redact`, `render_line`, `render_task_md`,
  `rank_recall`, `match_search`, `tokenize`. The rankers live here so the
  validator and both backends import one copy.
- `skills/ai-task/memory_compact.py`: `compact_task(reader, task_id, sources="close"|"tracked")`
  → `Compaction(entries, seal, coverage, problems)`, `split_instances`,
  `parse_task_md`, `excerpt`, `parse_known_risks`; `reader` is `FsReader` or
  `GitTreeReader`.
- `skills/ai-task/memory_sync.py`: `load_config`, `after_close`, `export`,
  `verify`, `validate_range`, `open_batch`, `pack`, `cleanup`, `restore`,
  `redact`, `migrate_report`, `migrate_apply`, `move_logs`, `install_hook`,
  `remove_hook`, `GitTreeReader`, `FsReader`.
- `skills/ai-task/memory_store.py`: the `History` protocol (`tasks`,
  `entries`, `raw_journal`, `task_window`, `recall`, `search`, `risks`),
  `FileHistory`, `SqliteHistory` with `refresh` and `rebuild`,
  `open_history`. In the refactoring step this is FileHistory over legacy
  directories only.
- `hooks/memory-pre-push.py`: argv and stdin parsing, ref resolution,
  `validate_range`, printing, exit codes; no `state.py` import.
- `tools/benchmark-memory.py`: `generate(n, seed, journal_kb)`, the
  measurements, `--json`.
- `state.py`: the `recall` and `memory` subparsers; one call after
  `archive_v7` when `mode == packages`; `risk_recorded` in `EVENT_TYPES` and
  `FORGEABLE_EVENTS`; `next_task_id` per R1; `memory_*` imported lazily as
  `weight` and `sensors` are (`state.py:80-83`). `sensors.py`: the R26
  exclusion.

### §D15 Alternatives rejected

Besides Q2's B and C, rejected by the developer:

1. One JSON line per task: a 20–60 KB line is unreviewable in a PR, and loss
   or duplication becomes all or nothing; per-entry lines plus a seal give
   line-level diffs and detect partial loss.
2. Markdown as the canonical record: readable in a PR, but round-tripping
   verbatim answers needs the whole grammar of task.md §Questions
   (`state.py:122-142`), and a reviewer's edit can break the parse silently.
   Trade-off accepted: PR reviewers read JSONL lines (Bulgarian stays
   readable through `ensure_ascii=False`); `memory show <id>` gives the
   prose locally.
3. JSONL plus a committed rendered `.md`: two copies that drift, twice the
   files; rejected under the plan's "две независимо променяни копия".
4. git notes: zero files in the tree, but notes are not fetched by default,
   hosting UIs hide them, merging them needs a strategy, and a plain clone
   would not recover the history (fails O2).
5. An orphan branch: needs a second push the agent may not do, is not
   reviewed with the PR, is absent from a default clone.
6. A committed SQLite file, or SQLite as the authority: binary merges, P3
   broken, two writable copies.
7. A batch named after the branch: branch names leak into history, need
   slugging, and a rename splits a batch.
8. `start` printing recall itself: changes `start`'s output in files mode
   (R15) and costs every start; the skills call `recall` instead.
9. Ranking by bm25: file mode cannot reproduce it (R11); newest first within
   fixed tiers is what an agent at task start needs.
10. Hash chains or signatures on packages: the threat model is an agent's
    mistakes, not a constructed attack; the path guard and rid integrity
    suffice for v1.

### Risks and their pins

| # | risk | mitigation | pinned by |
|---|---|---|---|
| 1 | compaction silently drops an approval, an answer or a scope change (C6, behaviour 2) | unknown events kept by default, the drop list versioned, every line accounted for (R3), V5 cross-checks the committed journal on every push while cleanup is off, cleanup gated (R22) | `test_memory_compact.py`: coverage equals lines on every fixture; approval and answer fields equal their sources |
| 2 | verbatim text lost to the 4 KB journal truncation (`state.py:280-284`) or the 500-character detail cap | text never taken from `detail`; task.md §Questions is the fallback; otherwise `null` plus `unrecorded` | a 6 KB answer fixture |
| 3 | import duplicates | rid is a content hash, `INSERT OR IGNORE`, one seal per key (V3) | re-import adds 0 rows; export, import, export byte-identical |
| 4 | a package merged out of order, or both sides of a conflict kept | no reader depends on line order; V2 compares rid sets, V4 checks digests | shuffled-lines fixture |
| 5 | FTS5 missing | detected; FTS only prefilters; the scan gives identical results | `AI_MEMORY_NO_FTS=1` differential test |
| 6 | a developer with the mode off pulls packages | read commands see them; files-mode close writes none; once the policy turns the mode on the next close exports and `status` reports the missing hook | two-clone test |
| 7 | an agent "approves" by writing a record | protected paths (R19); no gate reads packages; `risk_recorded` is forgeable-protected | a forged approval for the task in flight leaves `close` requesting the gate |
| 8 | recall stale against the live state | the task in flight is excluded and the header says so; refresh before every answer; guards and gates never read recall | index-stale test |
| 9 | migration collisions: reused ids, multi-task journals, directory name differing from the `task` field | instance split, report first, sealed keys skipped, tracked-only sources make rids deterministic across clones | a journal with two `task_started` |
| 10 | Codex parity | one `state.py`; the hook depends on no runtime; shared skill text | recall and close under `AI_RUNTIME=codex` identical |
| 11 | a secret pushed inside an excerpt | fixed redaction regexes, size cap, `excerpt_max_bytes: 0` turns excerpts off, human `memory redact` | secret-pattern fixture |
| 12 | one developer on two branches shares a batch | per-branch bookkeeping, so branches never share a file | worktree test |
| 13 | packing conflicts | own author only, closed periods only, rid-superset check | pack test |
| 14 | `archive_v7` writes a torn `state.json` (`state.py:3879-3881`) | compaction refuses that task and keeps the originals; known risk, not fixed here (C1) | torn-file fixture |
| 15 | agent notes stamped `actor: hook` (`state.py:1001-1002`) | copied as stored, never raised; known risk | — |
| 16 | the new id breaks a human's habit or script | only `next_task_id` knows the shape; the `T-*` glob in `journal-summary.py:30` still matches; CHANGELOG note | `test_task_id.py` |
| 17 | pre-push slow on a large history | only changed blobs plus one `ls-tree`, read with `cat-file --batch`; the budget comes from the benchmark | timed case × `AI_TIMED_FACTOR` |

### Suggested order for `/rr-plan`

The architect's 17 steps, each naming its files, with the mode C6 gives them:
1 benchmark baseline (guarded) · 2a characterization tests of
journal-summary, usage-report `--task`, status, the files-mode close file
list and legacy ids, passing on today's tree; 2b the History refactor with
byte-identical output (C3) · 3 the task-id bugfix, failing test first (C2) ·
4 format · 5 compaction (full: dropping an approval is behaviour 2) · 6 the
sensors exclusion · 7 export at close plus status/verify/show/export (full:
it changes what a user project commits) · 8 recall and search over files ·
9 guard patterns, golden additive only · 10 the risk kind · 11 pre-push plus
enable/disable (full: it changes install) · 12 skill and doc text, with the
human-staged edits to `security.md`, `.ai/AGENTS.md`, `.ai/state/README.md`
· 13 migration of tasks and logs (full), the log removal its own commit ·
14 the SQLite index, only past the OQ3 threshold · 15 cleanup, restore,
redact (full; stays `cleanup: false` until §D6 holds) · 16 pack · 17 end to
end, `verify_command` once to the end then `e2e_command`
(`.ai/policies/testing.md:87-89`).

## Interfaces

### §I1 Entry envelope (every kind)

| field | type | required | notes |
|---|---|---|---|
| v | int | yes | 1 |
| rid | str | yes | `r1-` + 24 lowercase hex |
| task | str or null | yes | null only for `risk` and `redaction` outside a task |
| inst | int ≥ 1 | yes | legacy split instance |
| seq | int ≥ 0 | yes | the seal is the highest |
| kind | str | yes | task, weight, override, scope, question, approval, verify, review, note, handoff, risk, conflict, redaction |
| ts | str | yes | ISO-8601 UTC, the source's precision |
| actor | str | yes | human, agent, hook, migration or unknown, copied from the source |
| by | str or null | yes | |
| runtime | str | yes | claude, codex or unknown |
| src | [str] | yes, ≥ 1 | pointers (§D3) |
| unrecorded | [str] | no | fields absent at the source |
| truncated | [str] | no | agent fields cut at 2 000 characters |
| supersedes | str | no | rid |

Required fields per kind:

- `task` (the seal): result, goal, workflow, mode, w, axes, started_at,
  closed_at, files, steps, stages, changes, code, facts, verify_runs,
  counts{lines, skipped, dropped}, people, runtimes, entries, digest, source,
  schema, version; optional legacy_tier.
- `weight`: change, w, mode, axes, from, to, lines.
- `override`: what, from, to, via, why; optional pick.
- `scope`: change (plan or amend), added, why; optional steps.
- `question`: qid, stage, question, context, options[{key, text}],
  recommended, answer{choice, text, by, via, at, actor} or null.
- `approval`: gate_id, requested_at, decision (approved, rejected, pending),
  at, via, unattended, tty, note, why, tree, confirm, operations; optional
  pick.
- `verify`: n, scope, exit, tree, command, duration_s, expected_fail,
  after_fix, why, excerpt, log.
- `review`: pass, tier, focus, verdict, findings[{label, severity, where,
  text, in_scope}], closed[{labels, by_run}], report.
- `note`: note_kind, text, why, error; optional raw.
- `handoff`: from, to, via, reason.
- `risk`: rkey, title, where, label (`KNOWN FACT`, `INFERENCE`, `UNKNOWN`,
  `RISK`), what, likelihood, fix, status (open, ticketed, accepted, fixed),
  status_why, found_by, text; optional label_derived.
- `conflict`: key, rids, reason. `redaction`: target, field, why.

Three lines of one task in a batch file, abridged:

```json
{"actor":"agent","answer":{"actor":"agent","at":"2026-10-28T18:28:25Z","by":"vanssa","choice":"A","text":null,"via":"prose"},"by":"vanssa","inst":1,"kind":"question","options":[{"key":"A","text":"Пакети с уникални имена: …"},{"key":"B","text":"Един файл за проект, …"}],"qid":"Q2","question":"Как да се групират в Git сбитите записи на приключените задачи?","recommended":"A","rid":"r1-3f…","runtime":"claude","seq":3,"src":["events.jsonl:31","task.md#Q2"],"stage":"build","task":"T-2026-10-28-1825-compact-memory","ts":"2026-10-28T18:28:25.004Z","unrecorded":["answer.text"],"v":1}
{"actor":"human","at":"2026-10-29T09:02:11Z","by":"vanssa","confirm":null,"decision":"approved","gate_id":"G1","inst":1,"kind":"approval","note":null,"operations":[],"requested_at":"2026-10-29T08:55:40Z","rid":"r1-9a…","runtime":"claude","seq":7,"src":["events.jsonl:58","events.jsonl:61","task.md#G1"],"task":"T-2026-10-28-1825-compact-memory","tree":"0dcba89e7…","ts":"2026-10-29T09:02:11.310Z","tty":true,"unattended":false,"unrecorded":["note"],"v":1,"via":"terminal","why":null}
{"actor":"agent","by":null,"closed_at":"2026-10-29T09:03:00Z","digest":"sha256:…","entries":11,"kind":"task","result":"closed","seq":11,"started_at":"2026-10-28T18:25:02Z","task":"T-2026-10-28-1825-compact-memory","…":"…","v":1}
```

### §I2 Package format

- File name: `^(?P<period>\d{4}(?:-\d{2}|-Q[1-4])?)\.(?P<author>[a-z0-9][a-z0-9-]{0,31})(?:\.(?P<batch>[0-9a-hjkmnp-tv-z]{4}))?\.jsonl$`
- Line 1, the header:
  `{"author":"vanssa","batch":"k3q7","created":"2026-10-28T19:02:11Z","format":1,"period":"2026-Q4","pkg":"riskrails-memory"}`
  (`batch` is null for a pack). Then the entries, ordered by key, then seq,
  the seal last per key. UTF-8, LF, no BOM.
- Task ids: new `^T-\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9]+(?:-[a-z0-9]+)*$` (the
  slug 3–24 characters, an optional `-<n>` disambiguator counted inside it),
  legacy `^T-\d{4}-\d{2}-\d{2}-\d{3}$`; any `TASK_ID_RE` id is still accepted.

### §I3 SQLite DDL, outline (`.ai/local/memory/index.sqlite3`)

```sql
PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON; PRAGMA user_version=1;
CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);  -- schema, fts5, sqlite_version, built_at, keep_rules, stale
CREATE TABLE packages(path TEXT PRIMARY KEY, size INTEGER, mtime_ns INTEGER, sha256 TEXT, author TEXT, period TEXT, entries INTEGER);
CREATE TABLE tasks(key TEXT PRIMARY KEY, task_id TEXT NOT NULL, inst INTEGER NOT NULL, started_at TEXT, closed_at TEXT,
                   result TEXT, mode TEXT, w INTEGER, workflow TEXT, goal TEXT, seal_rid TEXT, source TEXT NOT NULL);
CREATE INDEX tasks_closed ON tasks(closed_at);
CREATE TABLE entries(rid TEXT PRIMARY KEY, key TEXT, seq INTEGER, kind TEXT NOT NULL, ts TEXT NOT NULL, actor TEXT, by TEXT,
                     runtime TEXT, status TEXT, superseded INTEGER NOT NULL DEFAULT 0, text TEXT NOT NULL, json TEXT NOT NULL,
                     package TEXT, line INTEGER);  -- text = the search fields joined; json = the canonical line
CREATE INDEX entries_key ON entries(key, seq);
CREATE INDEX entries_kind_ts ON entries(kind, ts);
CREATE INDEX entries_by_ts ON entries(by, ts);
CREATE TABLE entry_files(rid TEXT NOT NULL REFERENCES entries(rid) ON DELETE CASCADE, path TEXT NOT NULL, own INTEGER NOT NULL,
                         PRIMARY KEY(rid, path));
CREATE INDEX entry_files_path ON entry_files(path);
CREATE TABLE conflicts(key TEXT, rid_a TEXT, rid_b TEXT, reason TEXT, PRIMARY KEY(key, rid_a, rid_b));
CREATE TABLE raw_events(task_id TEXT, line INTEGER, ts TEXT, event TEXT, actor TEXT, runtime TEXT, stage TEXT,
                        detail TEXT, data TEXT, PRIMARY KEY(task_id, line));  -- trace of CLOSED tasks only
CREATE INDEX raw_events_ts ON raw_events(ts);
-- only when FTS5 is available:
CREATE VIRTUAL TABLE entries_fts USING fts5(text, content='entries', content_rowid='rowid', tokenize='unicode61 remove_diacritics 0');
```

One transaction per package file, `INSERT OR IGNORE` on rid. A package that
disappears drops only the rids found in no other package. The index is never
the only copy of anything.

### §I4 CLI

Exit codes: 0 ok · 1 findings · 2 usage, not enabled, or newer schema · 3
aborted with nothing half-written · 5 human route required. `--json` where
listed. `recall` and `memory` are not in `TASK_COMMANDS`, `MUTATING_COMMANDS`
or `BLOCKING_COMMANDS` (`state.py:147,158,164`), so a pending question never
blocks them. Close output gains one `record:` line (§D5).

```
state.py recall --files "a,b,dir/**" [--budget 1500] [--kinds risk,review,decision,scope,task] [--all-risks] [--json]
  # Recall — 3 files · 9 of 23 items · ~1 140/1 500 tokens · packages 4 + legacy 59 · index none · current task T-… excluded
  - [risk open RISK] hooks/guard/paths.py:120 — <title> (R-…; found T-2026-10-21-001)
  - [finding MED residual] skills/ai-task/state.py:722 — <text> (T-2026-10-28-007 L1, BALANCED, 2026-10-28)
  - [answer human] T-…/Q2 — "<question>" → A "<option>" by vanssa via file, 2026-10-28
  - [decision agent] T-… — <text> — because <why>
  - [task] T-2026-10-28-007 · 2026-10-28 · guarded · closed — <goal> (5 files)
  … 14 more: state.py memory search --files "a,b,dir/**" --offset 9
  (no match: "# Recall — 3 files · nothing recorded for these files", exit 0)
state.py memory status [--json]     mode, period, author, index, fts5, open batch, packages n/bytes, closed-not-exported, pre-push installed|current|foreign|hookspath|absent, cleanup
state.py memory enable [--author SLUG] [--period month|quarter|year] [--index none|sqlite]      (human route)
state.py memory disable                                                                         (human route)
state.py memory export [ID…|--pending]
state.py memory verify [--all|ID…|--range OLD..NEW|--fresh-clone] [--json]
state.py memory show ID [--md|--json] [--entry RID]
state.py memory search QUERY [--kind K] [--by NAME] [--file PATH] [--task ID] [--since DATE] [--until DATE] [--limit 20] [--offset 0] [--json]
state.py memory risk add --title T --where "path:line,…" --label "RISK|INFERENCE|UNKNOWN|KNOWN FACT" --what TEXT [--likely TEXT] [--fix TEXT] [--status open]
state.py memory risk close RKEY --status fixed|accepted|ticketed --why TEXT
state.py memory risks [--status open|all] [--md|--json]
state.py memory migrate --report | --apply [--risks] | --move-logs --confirm-delete NAME
state.py memory rebuild
state.py memory cleanup ID…|--all --confirm-delete NAME          (human route)
state.py memory restore ID…|--all
state.py memory pack --period P --confirm-delete NAME            (human route)
state.py memory redact RID --field F --why TEXT                  (human route)
```

The `--json` form of recall:
`{"schema":1,"files":[…],"budget":N,"used":N,"items":[{"rid","kind","task","ts","line","src"}],"more":N,"next":"…","source":{"packages":N,"legacy":N,"index":"none|sqlite","fts5":bool,"fallback":bool}}`.

### §I5 Pre-push contract

```
memory-pre-push.py <remote> <url>  < "<lref> <lsha> <rref> <rsha>\n"…      (git hook)
memory-pre-push.py --range OLD..NEW [--repo DIR]                           (CI / server; V9 off)
memory-pre-push.py --tree REV [--repo DIR]                                 (structure only)
stderr: one line per finding (§D10); exit 0 / 1 / 3; never writes a file; no network; at most 4 git processes per ref
```

CI recipe (`docs/local-memory.md`): `npx riskrails@<v> --target claude --home "$RUNNER_TEMP/rr" --yes`,
then `python3 -I "$RUNNER_TEMP/rr/hooks/memory-pre-push.py" --range origin/main..HEAD`.

### §I6 Config keys, new event, new guard patterns

```json
// .ai/policies/memory.json — committed, human-edited (absent = files mode)
{"schema": 1, "mode": "files|packages", "period": "quarter", "package_max_bytes": 1048576,
 "cleanup": false, "excerpt_max_bytes": 1024, "keep_rules": 1,
 "recall": {"budget_tokens": 1500, "max_items": 40}}
// .ai/local/memory/config.json — per developer, git-ignored
{"schema": 1, "author": "vanssa", "index": "none|sqlite"}
// .ai/local/memory/batches.json — bookkeeping
{"schema": 1, "open": {"new-refactor": "2026-Q4.vanssa.k3q7.jsonl"}}
```

New journal event `risk_recorded` with
`data {rkey, title, where, label, what, likelihood, fix, status, status_why, supersedes}`,
added to `EVENT_TYPES` and `FORGEABLE_EVENTS`. New guard patterns
`(^|/)\.ai/memory/` and `(^|/)\.ai/local/memory/` in `protected_config_patterns`.

## Policy conformance

- **C1** Production behaviour is the source of truth: the close path,
  `archive_v7`, the journal contract and the handoff are unchanged; three
  defects found on the way are recorded as known risks, not fixed here
  (§Flagged concerns 9).
- **C2** Characterization tests (step 2a) precede every behaviour change; the
  id change (step 3) starts with its failing test.
- **C3** The History refactor (step 2b) changes no output; the removal of the
  committed logs is its own commit; no step mixes a refactoring with a
  feature.
- **C4** Every step names its files; `memory risk add` refuses rather than
  widening the scope (§D9).
- **C5** and non-negotiable 3: no command commits or pushes; the pre-push
  hook runs inside the human's push; `enable`, `disable`, `cleanup`, `pack`
  and `redact` take `human_route()`; an imported approval authorises nothing
  (R19).
- **C6** Steps 5, 7, 11, 13 and 15 run in full mode because of what they do
  to a project's decisions and installs, not because they are "a process".
- **Non-negotiable 2** (`.ai/AGENTS.md:12-15`): the work runs through
  `/rr-plan` and `/rr-build` from this spec.
- **Non-negotiable 4**: step 17 runs `verify_command` once to the end, then
  `e2e_command` (`.ai/policies/testing.md:87-89`); step tests are scoped
  (`testing.md:43-45`).
- **Non-negotiable 6**: R24, the evidence label on every risk record.
- **Global `CLAUDE.md`** (RiskRails rules): deterministic tools first (the
  extraction, the ranker and the validator are deterministic); context by
  slices (`recall`, bounded by tokens, replaces whole-file reads); no agent
  commits or pushes. **Project `CLAUDE.md`**: a BLOCKER is closed only with a
  test that pins it (the pins column of the architect's risk table); weigh
  by C6 (above). **Root `AGENTS.md`** states the same workflow lines
  (`AGENTS.md:32-35`); its gaps are a flagged concern, not a disagreement
  of policy.
- **`.ai/policies/security.md:59-61`** names `task.md` and `events.jsonl` as
  always read-only for an agent and as a review's evidence inputs. The
  design keeps `state.py` as their only writer (compaction at close moves,
  never edits, and only under R22) and adds `.ai/memory/` and
  `.ai/local/memory/` to the protected patterns (R19); the policy text itself
  is a human edit (§Flagged concerns 8).
- **`.ai/state/README.md`** contract (two writers of the state, journal
  append-only and best effort, handoff derived): unchanged; the README's
  stale line about the archived `state.json` is fixed in step 12.
- **`docs/hook-performance.md:34-45`**: R18, no per-tool-call hook changes;
  the only new hook is a git `pre-push`.
- **`docs/architecture.md:194-201`** ("a journal an agent can author is not
  an audit trail"): the record inherits that status; the design adds
  integrity (rid, seal digest, V2–V5) against an agent's mistakes, not
  signatures against an attacker (§D15 item 10).
- **Skills and agents**: `rr-build`, `rr-review`, `rr-ship` change the lines
  that append to `known-risks.md` (R12); `rr-plan` and `rr-build` call
  `recall` at task start (S1); no project agent file exists
  (`agents/` has no description lines). **ADRs**: none accepted
  (`docs/sdlc/adr/` holds only the template). **Plugin skills**: none
  matches this stack (Python stdlib, bash, git).
- **Stdlib only**: `sqlite3`, `tarfile`, `fcntl`, `hashlib`, `os.urandom`;
  FTS5 present on the development machine (SQLite 3.46.1), detected
  everywhere else.

## Flagged concerns

1. **Root `CLAUDE.md` and root `AGENTS.md` disagree in coverage.**
   `CLAUDE.md:21-26` carries two corrections (a BLOCKER needs a pinning
   test; weigh by C6) and `AGENTS.md:21-23` "Things Codex gets wrong" is
   empty, so Codex sessions miss both. Both root files say "No agent
   commits, merges or deploys" (`CLAUDE.md:38`, `AGENTS.md:35`) and omit
   "pushes", which `.ai/AGENTS.md:16` includes; that matters once a
   pre-push hook exists. A human aligns them outside this task.
2. **Stale documentation.** `.ai/state/README.md:19-21` (and the template)
   and `docs/architecture.md:174-177` say the archived `state.json` is
   committed under `.ai/reports/<id>/`; since D4 it is written to the
   ignored `.ai/state/logs/<id>/` (`state.py:3858-3887`). Step 12 fixes the
   template and `docs/architecture.md`; the project's own README is a human
   edit.
3. **The plan's file list is out of date.** It names `install.sh` (a stub
   that exits 2, `install.sh:1-18`; the installer is `bin/riskrails.js`,
   which already ships every `hooks/*.py`), `gitignore.snippet` (already
   ignores `.ai/local/`) and implies a `project-update` migration (none is
   needed, §D12). `/rr-plan` must not copy those entries.
4. **O6 against P7, resolved in this spec.** Refusing per-task directories
   at push (O6) contradicts keeping cleanup off (P7). V7 applies only once
   `cleanup: true`; until then the directories are pushed and serve as the
   validator's cross-check copy. O6 and O1 are worded accordingly.
5. **O7 "nothing changes in files mode", resolved by Q3 and Q4.** R1 (id
   shape) and R12 (skill text using `recall` and `memory risk`) change files
   mode; the developer chose both for files mode too, and O7 lists them as
   the two exceptions. The characterization suite (A6) pins everything else.
6. **O1 against Q2's wording, resolved by Q6.** Q2's accepted option says
   "около 12 файла на година" for two people; monthly periods give 24,
   quarterly about 8. The default is `quarter`.
7. **S3 partly rejected by the architect pass**: the index is not written at
   step boundaries (Decisions taken, S3). No reader needs it, and it would
   add I/O to a hot path.
8. **`.ai/policies/security.md:59-61` must change, and only a human may do
   it.** After cleanup a review's evidence inputs are the package entries
   and `memory show`, and `.ai/memory/` must be listed among the paths that
   are always read-only for an agent. The edit is staged in step 12 for the
   human, like `.ai/AGENTS.md:33-35` (list `memory.json` among the policy
   files).
9. **Recorded as known risks, not fixed here (C1):** `archive_v7` writes the
   archived `state.json` with a plain, non-atomic write
   (`state.py:3879-3881`); compaction refuses a torn file and keeps the
   originals. `state.py event` stamps `actor: hook` on agent notes
   (`state.py:1001-1002`); the record copies the actor as stored and never
   raises it. `.ai/state/consent.jsonl` (`state.py:2287-2288`) is not matched
   by the ignore snippet's `.ai/state/*.json`: `git check-ignore` confirms
   it is not ignored (the file does not exist on this tree yet; it belongs
   to the dialog work, T-2026-10-28-009).
10. **The CLI surface grows from 17 to 19 top-level names** (`recall`,
    `memory`). `tests/test_skills_surface.py` and the instruction budget
    tests bound the skill text that explains them.
11. **The first git hook this plugin installs.** `install.sh` installs none
    today; the pre-push shim is therefore the first thing RiskRails writes
    into `.git/hooks/`. R17 keeps it out of a foreign hook's way and makes
    the human's `git push --no-verify` the documented escape; the agent's
    is refused (`hooks/guard/git.py:219`).
12. **PR readability is traded for round-trip safety.** Reviewers see JSONL
    lines in a package diff, not prose (§D15 item 2). `memory show <id>`
    renders the prose locally; a hosted rendering is a later option, never
    a second committed copy.
13. **Recall estimates tokens, it does not count them.** `ceil(bytes/3.5)`
    is conservative for ASCII and roughly right for Cyrillic; the budget is
    a ceiling on bytes that enter the context, not a tokenizer guarantee.

## Open questions

Owner of every question: vanssa. OQ1, OQ2, OQ3 and OQ5 were asked as Q3–Q6
and answered on 2026-10-28 (Decisions taken); they stay here only as the
record of what was open. For the rest the recommendation is the default
`/rr-plan` uses until an answer says otherwise.

- **OQ1 = Q3, answered.** The new id in files mode too, and with a short,
  clear slug rather than random characters (R1, §D2).
- **OQ2 = Q4, answered A.** `recall` and `memory risk` work in files mode
  too.
- **OQ3 = Q5, answered A.** The SQLite index is built only when FileHistory
  recall p95 exceeds 300 ms or search exceeds 1 s at 1 000 tasks in the
  baseline; this is Q1's "да се оцени" made measurable.
- **OQ4** `known-risks.md` after migration: recommended a stub of at most 10
  lines pointing to `state.py memory risks --md`. A committed rendered view
  would be a second copy that a human edit overwrites.
- **OQ5 = Q6, answered A.** Period default `quarter`.
- **OQ6** Do teammates work branch-per-task? If yes, `memory pack` (step 16)
  is needed for O1; if only long-lived branches, it can wait. Recommended:
  ship it last either way.
- **OQ7** Mode at project level: recommended yes. A teammate's next close
  exports automatically and a missing hook shows in `status`; a
  per-developer opt-in would let one teammate's closes bypass the packages
  and V5 would refuse their pushes.
- **OQ8** Review text in git: recommended findings lines only (each at most
  2 000 characters), the full report local. The full text roughly doubles
  the package size.
- **OQ9** Recall default budget: recommended 1 500 tokens, below Codex's
  context injection of about 2 500 tokens; the value lives in `memory.json`.
- **OQ10** CI: recommended the documented npx temp-home recipe (§I5) and no
  new npx subcommand; a `memory-validate` subcommand in `bin/riskrails.js`
  would be a separate installer task.
