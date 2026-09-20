# Spec: WP4 — Deterministic gates

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work-package table, row 4)

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Depends on **WP1** (schema version in `.ai/VERSION`, ordered idempotent migrations inside
the dry run, template history — closed, PR #15/#16). Reuses **WP2**'s journal, `handoff.md`
and human-condition machinery (PR #22) and **WP3**'s schema 3, `.ai/AGENTS.md` router and
`.ai/rules/` (PR #23). Runs beside WP3; **WP5** consumes the sensor verdict for its budget
tables, **WP6** is untouched.

Recommended tier: **T3** — the intent's table says T3, and the trigger is the same one that
carried WP3: `skills/ai-task/state.py` and the shipped `risk-tiers.json` are shared by every
initialised project and by both runtimes, so a wrong gate stops work everywhere.
`tests/test-ai-task-state.sh` is the characterization. No security review: no authentication,
no authorization decision, no personal data — but see F5, the gate does decide whether a
review stage runs.

Tags used below: **G1–G6** are the six deliverables of the intent's WP table row 4
(diff budget and scopes, diff measurement in `step-done`, `sensors.py`, tier re-scoring,
the `ai-tester` retry rule, "test must bite"); **D2** and **D6** are the intent's decisions
2 and 6; **C-…** a constraint; **BASE** the cost baseline measured on 2026-09-20
(~$5–15 per ordinary task session, $25–52 per WP-sized one, 24% of spend in subagents,
cache read dominating).

## Requirements

| # | Requirement (testable) | Satisfies |
|---|---|---|
| R1 | `skills/ai-init/templates/.ai/policies/risk-tiers.json` gains `diff_budget`, `path_scopes`, `sensors` and `remediation_rounds`; its `version` goes 2 → 3; `risk-tiers.md` gains a "Diff budget, scopes and sensors" section and a fresh `sha256:` line; `tests/test-scaffold-idempotency.sh` stays green. | G1, D2 |
| R2 | `state.py init` and `quick` record `diff.base_commit` and `diff.base_tree`; `step` records `steps[].tree_before`; `step-done` measures that step's diff from **tree objects**, never `git diff HEAD`, and records files, added, deleted, lines, unscoped and binary. Outside a git repository, or with an unreadable tree, it records `status: "unavailable"` and still exits 0. | G2, C-in-flight |
| R3 | `step-done` exits **6** with `DIFF_BUDGET_EXCEEDED …` when the step's counted lines or files exceed `diff_budget.per_step[<tier>]`, and with `SCOPE_CHANGE_REQUIRED …` when a changed file matches none of the step's `allowed_files`. The step stays `in_progress`. `state.py step-split <id> --files …` moves files to a sibling step that inherits `tree_before`; a re-run then measures the reduced set. | G1, G2 |
| R4 | At every `step-done` the task diff since `base_tree` is re-scored: `max(declared, path-scope tier, declared + 1 when over `per_task`)`. A higher result sets `risk_tier` and emits `tier_raised` with `note: "rescored: …"`; a lower result is recorded and **never applied** (`downgrade_rule`). | G4 |
| R5 | Lowering a recorded tier (`risk` / `triage`) and a remediation beyond `remediation_rounds` require WP2's human condition and `--by`; otherwise exit 5, the code WP2 already uses for a refused approval. The lowering is recorded in `risk_tier_lowered`. | G4, `downgrade_rule`, `remediation_rule` |
| R6 | New `skills/ai-task/sensors.py` — stdlib, `git`, and the commands written in `testing.md`, nothing else — implements `diff`, `rescore`, `tests`, `lint`, `typecheck`, `traceability`, `duplicates`, `plan_sections`, `bite` and `detect`. Every result carries the tree hash it was measured on; a result whose tree moved is `stale`. Printed output is ≤ 12 lines; full output goes to files. | G3, C-deterministic, BASE |
| R7 | `sensors.py detect` proposes `lint_command:` / `typecheck_command:` lines from marker files and **never runs a detected tool**. Only commands a human wrote into `testing.md` are executed. | G3, C-project-tools |
| R8 | "All green" (D6) = `risk_tier ≤ sensors.skip_review_at_or_below` **and** `diff.rescored_tier ≤` the same **and** every sensor in `sensors.required_for_skip` is `green` or `not_applicable` **on the current tree**. `red`, `unavailable` and `stale` each block. Lint and type-check are `not_applicable` only through a human-written `lint_command: none` / `typecheck_command: none`; a missing or empty line is `unavailable`, never green. | D6 |
| R9 | `state.py review-gate` is the only writer of `review_status = "skipped_green"`; `set review_status skipped_green` is refused. At T3 and above it never skips: it attaches the sensor rows to the evidence ledger and prints `review: required`. | D6, review-economy |
| R10 | `state.py test-run --scope step\|suite\|e2e` runs the command from `testing.md` to the end, writes the full output to `.ai/reports/<task-id>/tests-<scope>-<n>.log`, prints ≤ 6 lines, records `tests.runs[]` and sets `test_status` / `e2e_status` deterministically on exit 0. Suite runs are capped at `sensors.tests.max_suite_runs`; one environment retry per run, and only after a recorded environment classification. | G5, BASE |
| R11 | `agents/ai-tester.md` is invoked **only on a red run**, receives the log path, classifies, and never re-runs the suite. EXISTING is verified with `sensors.py run --scope single --at base` (one test at the base tree). UNKNOWN escalates one tier, once. The Codex render stays green. | G5 |
| R12 | `bite`: source files changed since `base_tree` are reverted in place from tree objects, the required tests run once, and the tree is restored byte-identically (asserted by tree hash). Feature, bugfix and hotfix tests must **fail** at base; refactoring steps and steps with `kind: "characterization"` must **pass** at base. A lock file and `bite --restore` recover an interrupted run. | G6, testing.md |
| R13 | Sensor outcomes are appended to `.ai/reports/<task-id>/review-ledger.md` as `CONFIRMED` / `DEFECT` rows carrying the tree hash, and `agents/ai-reviewer.md` names them as inherited facts it must not re-derive. | review-economy §2, §6 |
| R14 | Migration `skills/project-update/migrations/0004_deterministic_gates.py` (`VERSION = 4`, `MOVES = []`, `patch_state` only) adds the new state defaults; `apply_defaults` fills the same in memory, so a task in flight survives. Fixture `tests/fixtures/project-update/schema-v3/`. The migration text mentions neither "claude" nor "codex". | C-in-flight, WP1 contract |
| R15 | No hook changes. `tests/test-guard-characterization.sh` and its golden stay byte-identical; every existing suite stays green; the new `tests/test-ai-task-sensors.sh` builds its scratch repository under a path containing a space; both runtimes call the same `sensors.py`. | C-guard-rules-stay, C-parity |
| R16 | `/ai-status` prints one sensors line from `sensors.json`; `events.jsonl` carries enough (`skipped_green`, `step_started{kind: "remediation"}`) for `/usage-report` to count skipped reviews and remediation rounds per task, which is what D2 calibrates against. | D2, G3 |

## Design

### Components

| Component | Single responsibility |
|---|---|
| `risk-tiers.json` (+ `.md` mirror) | policy: budgets, path scopes, the sensor set, retry counts |
| `skills/ai-task/sensors.py` (new) | **measure**: pure functions over a root, a tree pair and a config; writes only `sensors.json`, test logs and ledger rows |
| `state.py` additions | **own every state write**: the snapshots, the `step-done` gate, `step-split`, `test-run`, `review-gate`, the human conditions |
| `.ai/reports/<task-id>/sensors.json` | the report the gate reads and `/ai-status` shows |
| `.ai/reports/<task-id>/tests-<scope>-<n>.log` | full test output — a file, never context |
| `migrations/0004_deterministic_gates.py` | schema 4 state defaults |
| `agents/ai-tester.md` | classify a red log; never run the suite |

Module boundary: `state.py` imports `sensors` from its own directory and calls functions;
`sensors.py` never imports `state.py` and never opens `current.json` for writing. `sensors.py`
shells out only to `git` (fixed argv, `--no-pager`, `-c core.quotepath=off`) and to the
commands written in `testing.md` (cwd = project root, timeout from the config, output to a file).

### Where each gate fires

1. **`init` / `quick`** — `snapshot_tree()`: copy the real index to a temporary `GIT_INDEX_FILE`,
   `git add -A`, drop `.ai/state` and `.ai/reports` from that index, `git write-tree`. Records
   `diff.base_commit` and `diff.base_tree`. The user's index and worktree are never touched.
2. **`step <id>`** — records `tree_before` if absent (a split sibling inherits it).
3. **`step-done <id>`** — `tree_after = snapshot_tree()`; `git diff --numstat --no-renames -z`
   between the two trees; unscoped files → `SCOPE_CHANGE_REQUIRED` (exit 6); over budget →
   `DIFF_BUDGET_EXCEEDED` (exit 6); otherwise record the step diff, re-score the task diff,
   raise the tier if higher, print one line each. The step becomes `done` only on exit 0.
4. **After the last step** — `test-run --scope suite`, then `--scope e2e`. Exit 0 sets the
   status deterministically; a red run hands `ai-tester` a log path.
5. **`review-gate`** — the static sensors on the current tree, then `bite` (the slow one),
   `sensors.json` and the ledger rows, then R8. T2 all green → `review_status = skipped_green`;
   otherwise `review: required — <blocking list>` and the manager delegates `ai-reviewer`
   exactly as today.

Nothing fires on a tool call: no new hook, no cost on WP8's hot path.

### Which model step each sensor replaces (C-replace-not-add)

- the T2 `ai-reviewer` on every plan when all green (D6) — the one BALANCED subagent of direct mode;
- `tail -40` / `log-reader` on every verification run — the session sees ≤ 6 lines, the log is a file;
- `ai-tester` on a green run — exit 0 is PASS, no agent at all;
- the reviewer's "record" dimension at T3+ (plan sections, step-to-test traceability) — CONFIRMED
  in the ledger before the reviewer starts, per review-economy §6.

### Alternatives rejected

1. **Sensors inside `state.py`** — it is 1 975 lines, uses no `subprocess`, and the sensors must
   run without a task (`/ai-status`, `detect` at `/ai-init`). A separate module keeps `state.py`
   the only state writer.
2. **Per-step diff as `git diff HEAD -- <allowed_files>`** — double-counts files shared by steps,
   misses untracked files, and counts a tree that was already dirty at `init`.
3. **`git stash create` for the snapshot** — tracked files only, no `-u` form.
4. **"Test must bite" by mutation** (language-specific, and full mutation testing is out of scope
   in the intent) **or by coverage** (needs a per-language coverage tool most projects lack) **or
   by revert in a separate worktree** (`vendor/`, `node_modules/`, `.venv` are ignored and absent
   there, so the tests cannot run). Chosen: revert in place from immutable tree objects, with a
   guaranteed restore path.
5. **Auto-running a detected linter** — `npx eslint .` downloads packages, a cold `phpstan` takes
   minutes, and a wrong guess is a false verdict.
6. **An absent linter counting as green** so that plain projects can skip — a false green skips a
   review; the explicit `none`, in a task-protected file, is the only opt-out (R8).
7. **A PostToolUse hook measuring the diff on every edit** — WP8's per-call budget forbids it.
8. **Migration 0004 rewriting `risk-tiers.json`** — `update.py`'s per-key JSON merge already takes
   template-only keys cleanly and re-hashes an in-sync mirror; 0004 is state defaults only.
9. **Sensor results inside `current.json`** — the scope guard reads that file on every write; it
   stays small, and the state holds only the verdict pointer.
10. **Automatic re-run of the suite on any red** — that is exactly the accidental second full run
    the intent forbids. One environment retry, after a recorded classification, under a hard cap.
11. **Per-step bite** — reverting one step's files while later steps stand breaks compilation and
    yields a trivially "biting" failure. Bite is task-level; traceability covers the per-step
    obligation.

## Interfaces

### I1 `risk-tiers.json` additions (`"version": 3`)

```json
"diff_budget": {
  "per_step": {"T0": {"max_lines": 300, "max_files": 15}, "T1": {"max_lines": 120, "max_files": 5},
               "T2": {"max_lines": 200, "max_files": 8},  "T3": {"max_lines": 250, "max_files": 10},
               "T4": {"max_lines": 150, "max_files": 6},  "T5": {"max_lines": 150, "max_files": 6}},
  "per_task": {"T0": {"max_lines": 600, "max_files": 30}, "T1": {"max_lines": 300, "max_files": 10},
               "T2": {"max_lines": 400, "max_files": 15}, "T3": {"max_lines": 800, "max_files": 30},
               "T4": {"max_lines": 400, "max_files": 15}, "T5": {"max_lines": 400, "max_files": 15}},
  "exclude": ["**/*.lock", "package-lock.json", "composer.lock", "**/__snapshots__/**", "**/*.snap",
              "**/*.min.*", "**/*.map", "**/generated/**", "**/*.generated.*",
              ".ai/state/**", ".ai/reports/**"],
  "unbudgeted_scopes": ["docs"]
},
"path_scopes": [
  {"scope": "pipeline",   "paths": [".ai/policies/**", ".ai/workflows/**", ".claude/**", ".codex/**", "CLAUDE.md", "AGENTS.md"], "min_tier": "T3"},
  {"scope": "tests",      "paths": ["tests/**", "spec/**", "**/*Test.php", "**/*.test.*", "**/*.spec.*", "**/test_*.py"], "min_tier": "T1"},
  {"scope": "docs",       "paths": ["docs/**", "**/*.md", "**/*.rst", "**/*.txt"], "min_tier": "T0"},
  {"scope": "migrations", "paths": ["**/migrations/**", "**/Migrations/**", "db/migrate/**"], "min_tier": "T5"},
  {"scope": "infra",      "paths": ["Dockerfile*", "docker-compose*", "k8s/**", "helm/**", "terraform/**", ".github/workflows/**"], "min_tier": "T5"},
  {"scope": "auth",       "paths": ["**/Security/**", "**/Auth/**", "**/auth/**"], "min_tier": "T4"},
  {"scope": "payments",   "paths": ["**/Payment/**", "**/Billing/**", "**/Tax/**", "**/Invoice/**"], "min_tier": "T4"},
  {"scope": "config",     "paths": ["config/**", ".env*"], "min_tier": "T3"},
  {"scope": "dependencies","paths": ["composer.json", "package.json", "pyproject.toml", "requirements*.txt", "go.mod"], "min_tier": "T3"}
],
"sensors": {
  "skip_review_at_or_below": "T2",
  "required_for_skip": ["tests", "lint", "typecheck", "diff", "rescore", "traceability", "duplicates", "bite"],
  "tests": {"timeout_seconds": 1800, "env_retries": 1, "max_suite_runs": 5, "log_max_bytes": 2097152},
  "lint": {"timeout_seconds": 600}, "typecheck": {"timeout_seconds": 600},
  "bite": {"timeout_seconds": 600, "required_from": "T2"},
  "duplicates": {"min_lines": 8, "ignore_scopes": ["tests", "docs"]}
},
"remediation_rounds": 2
```

`path_scopes` is **ordered, first match wins per file**: `pipeline` before `docs` so an
instruction file is pipeline, `tests` before `payments` so `tests/Payment/FeeTest.php` is a test.
`lines` = added + deleted after `exclude`; the `docs` scope is counted and reported but not
budgeted. Why these numbers are conservative (D2): they sit near the "small change" band the
review literature uses (~100 lines, defect detection falling off past ~400), T4/T5 are tighter
because those reviews read every line and a re-score never lowers a tier, T3 is wider because
shared-domain work legitimately reaches its callers. They are defaults a project adjusts after
`/ai-init`, exactly like the triggers, and D2 recalibrates them from `/usage-report`.

`testing.md` gains two lines and one convention:

```
lint_command:        # e.g. vendor/bin/php-cs-fixer fix --dry-run | ruff check . — write `none` if the project has none
typecheck_command:   # e.g. vendor/bin/phpstan analyse --no-progress | mypy . — `none` if the project has none
step_test_command:   # may contain {files}; without it the paths are appended
```

### I2 Task-state additions (schema 4)

```json
"diff": {"base_commit": null, "base_tree": null,
         "task": {"files": 0, "added": 0, "deleted": 0, "lines": 0, "excluded_lines": 0,
                  "unbudgeted_lines": 0, "tree": null, "measured_at": null, "status": "not_measured"},
         "rescored_tier": null, "rescore_reasons": [], "over_budget": false},
"sensors": {"file": ".ai/reports/<task-id>/sensors.json", "tree": null, "verdict": null, "checked_at": null},
"tests": {"runs": [], "suite_runs": 0},
"risk_tier_lowered": {"by": null, "at": null, "from": null}
```

Per step: `"kind": "implementation" | "characterization" | "remediation"` (default
`implementation`; `remediate` sets `remediation`), `"tree_before"`, and after `step-done`
`"diff": {"tree_after", "files", "added", "deleted", "lines", "unscoped": [], "binary": [], "status"}`.
A `tests.runs[]` entry is `{"n", "scope", "command", "tree", "exit", "duration_s", "log", "at", "env_retry"}`.
`REVIEW_STATUS` gains `skipped_green`; `SETTABLE["review_status"]` keeps the old four values.

### I3 `sensors.py` command surface

```
sensors.py diff     [--root R] [--from TREE] [--to TREE|--now] [--tier T2] [--allowed "a,b"]
sensors.py rescore  [--root R] [--from TREE] [--declared T2]
sensors.py snapshot [--root R]
sensors.py detect   [--root R]
sensors.py run      --scope step|suite|e2e|single [--files "…"] [--test NAME] [--at base|now] [--log FILE]
sensors.py check    [--root R] [--only lint,typecheck,…] [--no-bite] [--json FILE]
sensors.py bite     [--root R] [--restore]
sensors.py report   [--root R] [--json FILE]
```

Exit codes: 0 green or not applicable, 1 usage/internal error, 2 at least one red, 3 at least
one unavailable or stale and no red. The whole of a `check` print:

```
sensors @ 9f1c2ab (declared T2, rescored T2)
  tests         green    verify_command exit 0 in 41s, run 1/5, log tests-suite-1.log
  lint          n/a      lint_command: none (testing.md)
  typecheck     UNAVAIL  typecheck_command missing — detected phpstan.neon; add
                         "typecheck_command: vendor/bin/phpstan analyse --no-progress" to .ai/policies/testing.md
  diff          green    3 files / 87 lines (T2 step budget 8 / 200), task 3 / 87 (400), 0 unscoped
  rescore       green    T2 — scopes: tests, source
  traceability  green    1/1 steps name tests that exist
  duplicates    green    0 blocks >= 8 lines
  bite          green    2 required tests fail at base (exit 1 in 6s); tree restored 9f1c2ab
review: required — typecheck unavailable
```

Status vocabulary `green | red | unavailable | not_applicable | stale`, per sensor:

| Sensor | green | red | unavailable | not_applicable |
|---|---|---|---|---|
| `tests` | a suite run with `exit 0` whose tree is the current one | last suite run non-zero | no run on this tree, or `verify_command` missing | — |
| `lint` / `typecheck` | exit 0 | non-zero or timeout | line missing or empty, or the tool exits 127 | the line is `none` |
| `diff` | within `per_step` and `per_task`, no unscoped file | over budget or unscoped | not a git repository, tree gone | — |
| `rescore` | `rescored <= declared` | `rescored > declared` | diff unavailable | — |
| `traceability` | every implementation step that changed non-test, non-doc files names at least one test, and every named test resolves | a step changed source and names none, or a name resolves to nothing | plan missing | no source changed |
| `duplicates` | no window of `min_lines` normalised added lines recurring in a changed file outside `ignore_scopes` | at least one | diff unavailable | no added lines |
| `plan_sections` | the plan file carries every heading of the project's plan template | a heading missing | ref unreadable | inline plan |
| `bite` | the must-fail set exits non-zero at base and the must-pass set exits 0 | either breaks its expectation | no `{files}`-capable `step_test_command`, `git < 2.23`, timeout, or `tests` not green on this tree | no source changed, or an investigation workflow |

Discovery order for lint and type-check: the `testing.md` line → `none` → not applicable; a
value → run it; missing → `unavailable` plus the `detect` proposal derived from marker files
(`phpstan.neon*`, `psalm.xml`, `.php-cs-fixer*`, `eslint.config.*`, `tsconfig.json`, `ruff.toml`,
`mypy.ini`, `pyrightconfig.json`, `go.mod`, `Cargo.toml`, `package.json` scripts).

### I4 `state.py` additions

```
state.py step-done <id>     # measures, gates, re-scores; prints
                            #   step 2 diff: 3 files, +71/-16 = 87 lines (T2 budget 8/200) — ok
                            #   task diff: 5 files, 140 lines (T2 budget 15/400); rescored T2
                            # exit 6: DIFF_BUDGET_EXCEEDED step 2: 312 lines > 200 (T2). Split:
                            #         state.py step-split 2 --files "<subset>"
                            # exit 6: SCOPE_CHANGE_REQUIRED step 2 changed src/Legacy/Gateway.php
                            #         outside its files — amend the plan
state.py step-split <id> --files "a,b" [--note "…"]
state.py test-run --scope step|suite|e2e [--files "…"] [--env-retry]
state.py review-gate        # T2 all green -> review_status=skipped_green, exit 0, "review: skipped"
                            # otherwise exit 2, "review: required — <blocking>"
state.py risk|triage T<lower> --by "<name>"    # human condition or exit 5
state.py set review_status skipped_green       # refused: "written only by review-gate"
```

No new journal event types: `tier_raised` (re-score), `scope_change{kind: split|unscoped}`,
`field_set`, `step_started{kind: remediation}`, `note`. `handoff.md` gains at most one line,
inside WP2's 30-line cap.

### I5 `sensors.json` and the ledger rows

`sensors.json` carries `schema`, `task`, `tree`, `declared_tier`, `rescored_tier`, `checked_at`,
a `sensors` map of `{status, tree, detail, …}` per sensor, and
`verdict: {all_green, blocking: [...], review: "skipped" | "required"}`. Ledger rows appended by
`check`, one per green or red sensor, the tree hash inside the claim:

```
| lint clean on 9f1c2ab (vendor/bin/php-cs-fixer fix --dry-run) | sensors.py lint | CONFIRMED | sensor |
| required tests fail without the change on 9f1c2ab (exit 1)    | sensors.py bite | CONFIRMED | sensor |
```

### I6 `ai-tester` retry rule

The input is a log path and the run line; the agent reads the file, never pastes it, and never
runs `verify_command` itself. EXISTING is verified with a single test at the base tree
(`sensors.py run --scope single --test <name> --at base`), never a second suite run.
TEST ENVIRONMENT FAILURE names the missing thing and answers `retry: yes|no` — `yes` only for a
transient cause (port, lock, timeout, container not up), and the manager then runs
`test-run --scope suite --env-retry` once. NEW REGRESSION goes to one remediation batch as today.
UNKNOWN escalates to BALANCED once, with the same log; the FAST agent is never asked twice.

### I7 Migration `0004_deterministic_gates.py`

`VERSION = 4`, `MOVES = []`, `patch_state` only: the I2 keys with null defaults, and per step
`kind` (`R*` → `remediation`, otherwise `implementation`), `tree_before`, `diff`. Dry-run line
`update .ai/state/current.json [0004] task state migrated`. Fixture
`tests/fixtures/project-update/schema-v3/` holds a task at `implementation`; after `--apply` the
keys exist, `state.py step-done 2` exits 0 printing
`step 2 diff: unavailable (task started before schema 4)`, and a second run is `0 automatic`.
The I1 policy keys arrive through the normal walk, not through the migration.

## Policy conformance

- **`~/.claude/CLAUDE.md`, "a new check should replace a model step"** — the design names the four
  it replaces (§ *Which model step each sensor replaces*). Nothing new is added to the pipeline
  that a model must read: every sensor prints a line, not a log.
- **Context hygiene** — test output goes to a file and reaches the session as ≤ 6 lines; `sensors.py`
  never prints a diff; BASE says cache read dominates, so the gate's own footprint is the design's
  first constraint.
- **`.ai/policies/testing.md`** — three scopes, three moments are unchanged; `test-run` is a
  deterministic wrapper around the commands the policy already names, and bite honours the
  characterization rule (a characterization test must *pass* at base, a feature test must *fail*).
- **`.ai/policies/review-economy.md`** — §2, the ledger: sensors write rows, so the reviewer starts
  where they stopped; §6, cheap facts stay cheap: traceability and `file:line` drift leave the
  thinking tier. §"will not trade away" is the one real conflict — F5.
- **`risk-tiers.json` `downgrade_rule` and `remediation_rule`** — R4, R5 turn both from prose into
  an exit code, using WP2's human condition rather than a new mechanism.
- **Model routing** — WP4 adds no agent and changes no model or effort; the only prompt change is
  `ai-tester`'s input contract. No shared prompt names a model.
- **WP1's migration contract** — one numbered migration, `MOVES = []`, idempotent, inside the dry
  run, runtime-neutral text, `.ai/VERSION` owned by the walk, with a fixture.
- **WP8 / WP7 guards** — no hook is touched; the characterization golden stays byte-identical, and
  the gate fires at step boundaries, never per tool call.

## Flagged concerns

1. **F1 — the gate decides whether a review happens, so a false green is the whole risk of this
   package.** Every ambiguity therefore resolves to red or `unavailable`: a missing linter line is
   not green, a result measured on an older tree is `stale`, a tool that exits 127 is unavailable,
   and `set review_status skipped_green` is refused. The remaining hole is a human writing
   `lint_command: true` into `testing.md`; the file is task-protected (WP7), `/ai-status` prints
   the commands, and nothing else can be done deterministically. Accepted, stated here.
2. **F2 — "test must bite" reverts files in the working tree.** It runs once, after the suite is
   green, only over files changed since `base_tree`, from immutable tree objects, guarded by
   `.ai/state/bite.lock` holding `tree_after`, with `bite --restore` and a printed recovery line
   before the run. An interrupted run is the failure mode a test must cover explicitly (R12), and
   a project can keep bite out of the T2 skip with `bite.required_from: "T3"`.
3. **F3 — `review-economy.md` says "no review stage the tier requires is skipped", D6 says an
   all-green T2 skips the model review.** A direct contradiction between an existing project policy
   and an intent decision. The spec resolves it the only way it can be resolved: the intent wins,
   and the implementation **amends the policy text** in the same change, citing D6, rather than
   leaving two documents disagreeing. If you would rather keep the policy absolute, R8/R9 become a
   *narrowing* of the T2 review (the reviewer gets the sensor rows and only the dimensions the
   sensors do not cover) and the token saving is smaller.
4. **F4 — tier re-scoring can fight a legitimately large, low-risk diff.** Mitigated by `exclude`,
   the unbudgeted `docs` scope, and by a raise costing one review plus an approval rather than
   refusing the work; only a human may lower. Deliberately narrow scope patterns (`**/Payment/**`,
   never `**/*pay*`) keep the false-raise rate low, and D2 recalibrates from real data.
5. **F5 — a tier raised after implementation cannot add the plan review retroactively.** The design
   records `plan_review: superseded by the diff review` and applies every other gate of the higher
   tier. The alternative — closing and restarting the task at the higher tier — is more honest and
   much more expensive. Needs your call (Q4).
6. **F6 — T0 and T1 keep no state file**, so no deterministic gate fires there at all: a change a
   human called T1 that edits `src/Payment/` is caught by nothing in this package. Making T1 a
   `quick` record is a policy change outside WP4's scope (Q3).
7. **F7 — the defaults are heuristics on somebody else's repository.** Path scopes and budgets are
   written against Symfony/PHP, JS and Python layouts; a project with another layout gets noise
   until it edits the file. This is what D2 accepts, and `/ai-init` already adjusts the triggers —
   the survey step should adjust these too.
8. **F8 — two version counters** now move in the same change: `risk-tiers.json` `version` 2 → 3
   (the policy shape) and `.ai/VERSION` 3 → 4 (the project schema). They mean different things and
   are deliberately kept apart; `risk-tiers.md` must say so, or a future reader will unify them
   wrongly.
9. **F9 — enforcing `downgrade_rule` and the remediation cap (R5) changes existing behaviour.** A
   habit like `state.py risk T2` typed after an over-cautious T3 now needs `--by` and a human
   condition. It is what the rule has always said in prose; existing tests that lower a tier or
   remediate three times must be checked first (R15).
10. **F10 — "scopes" means two things in the intent.** The intent's bullet lists *kinds*
    (bugfix, refactor, feature, spike); the WP table row and this spec implement *path* scopes.
    The kind axis is read from the existing `workflow` field, and bite is the only place it bites.
    The intent wording should be amended, or the kind axis added explicitly (Q1).

## Open questions

All eight were put to the user on 2026-09-20 and settled; nothing in this spec is open.

| # | Question | Settled |
|---|---|---|
| Q1 | Path scopes vs the intent's kind scopes (F10) | **Path scopes are WP4's**; the kind axis is read from the existing `workflow` field and bites only in `bite`. The intent's wording is amended in the same change, and `spike` is not added to `WORKFLOWS` here. |
| Q2 | Is `bite` required for the T2 skip? | **Yes — `bite.required_from: "T2"`.** A green sensor set without it would mean a passing suite that may never reach the diff, which makes "all green" meaningless. The cost is one extra scoped test run, after the suite is already green. |
| Q3 | Do T0/T1 stay without a state file and therefore without a gate? | **Yes, unchanged.** A human called it T0/T1; making T1 a `quick` record is a policy change outside WP4 (F6 stays a stated limit). |
| Q4 | A tier raised after implementation | **Record `plan_review: superseded by the diff review` and carry on.** Every other gate of the higher tier applies — STRONG review, human approval, security at T4. The task is not closed and restarted. |
| Q5 | `review-economy.md` vs decision 6 | **The intent wins and the policy text is amended in the same change**, citing decision 6 as the authority. `review-gate` writes `skipped_green`; two documents are never left disagreeing. |
| Q6 | Budgets in `profiles/*.json` (decision 2 names them) | **WP4 leaves the profiles untouched.** Nothing in this package depends on a subscription; the per-plan token-budget tables are WP5's (intent row 5). |
| Q7 | The human condition on `risk` / `triage` / `remediate` (R5) | **In WP4.** `downgrade_rule` has always said it in prose, and re-scoring is what first gives an agent a motive to lower a tier. WP2's mechanism already exists. |
| Q8 | `ai-tester`'s Bash surface | **Narrowed**: reading logs and one single-test run at base. The suite is never run by the agent; `state.py test-run` owns every run and its cap. |
