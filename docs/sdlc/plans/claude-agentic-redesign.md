# Plan: RiskRails (formerly claude-agentic) redesign — job-named commands, weight-based risk, one language

Intent: `docs/sdlc/intent/claude-agentic-redesign.md` · Spec: `docs/sdlc/specs/claude-agentic-redesign.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Written 2026-10-25 on `new-refactor` (HEAD `0491b7d`). This is a programme plan: each row of **Order of
work** is one `/ai-task`, which writes its own step-level plan (inline, plan mode or written, by its tier or
mode) and ends at human approval. No agent commits (C5). The spec's §Design table is the source; this plan
fixes the order, names the files per task, and records where it departs from the table and why.

**Status (2026-10-29): done.** Every agent row, 1.1–3.6, is closed (the last, 3.3e + 3.6, by
T-2026-10-29-1035); G0, G1, G2, 2.H, 3.H and 3.H2 are ticked below. One human item stays open: 2.H's
`safety.md` sentence.

## Decisions taken before planning (2026-10-25, developer)

- **OQ1–OQ7:** every bracketed recommendation accepted — seven commands (`/setup /spec /plan /build /review
  /ship /status`), `/build` (not `/task`), modes light / guarded / full, superpowers variant B, three mode
  words with a `tier_set` compat event for one version, no `ai-implementer` (six agent templates), team
  profile documented with slow-tagged tests and abrites-staging-v2 inventoried by `/setup --adopt`.
- **FC-B1:** rules map by *effect*: T4-class effects (allow a deny, change approval or install) score
  behaviour 2 and land in full by their weight, not by a label. The compat `tier_set` label is
  cost-equivalent: light → T2, guarded → T4, full → T5, full_irreversible → T6, for report continuity only.
  Both statements go into `docs/weight.md` (task 2.1) and into the 2.H rewording.
- **FC-A1…A7, B2…B5, C1…C4, D1…D9, S1…S6:** each is closed by the "Proposed:" line the spec gives it
  (including light ≤ 2 for D2, plugin-only as a degraded mode for D5, and for A5 the human publishes while the
  git guard denies `npm publish`).
- **OQ8, OQ9, OQ10:** manual precondition gates G0, G1 and G2 in **Order of work**.
- **G1 / OQ9 (2026-10-26, developer): option A, one `rr-` prefix for all seven.** `/plan`, `/review` and
  `/status` are built-in in Claude Code 2.1.310 and Codex 0.164.0 (`/review` is Claude Code's alias of
  `code-review`); `/setup`, `/spec`, `/build`, `/ship` are free. A `:` cannot be in a skill name (Codex
  accepts `^[a-z0-9-]+$`), so `riskrails:<name>` would exist only as a Claude Code plugin namespace. The
  seven are **`rr-setup rr-spec rr-plan rr-build rr-review rr-ship rr-status`**; every `/setup` … `/status`
  in this plan and in the spec means its `rr-` name. The bare `status` skill shipped in 1.4 is removed in
  2.3, with no alias (it shadows the built-in in both runtimes); `ai-status` becomes an alias of
  `rr-status` until 2.6. R1's count is unchanged: `status` is renamed, not kept beside its new name.
  Open for 2.3: an install that already has `~/.claude/skills/status/` or `~/.codex/skills/status/` keeps
  it after a reinstall unless the installer removes the directory it shipped.

## Departures from the spec's task table (this plan's corrections, one review round)

1. **2.2 is split into 2.2a (add) and 2.6 (remove).** `coding.md` says dead code is deleted only in a task
   about deleting it. Also, `/ai-task` keeps calling the old `state.py` subcommands until task 2.3 rewrites the
   skill text: deleting them in 2.2 would break the pipeline that runs 2.3 itself. 2.2a adds the new surface
   next to the old one. 2.6 deletes the 19 subcommands and the `sensors.py` checks after 2.3, under the new
   modes.
2. **3.3 is split into four tasks, 3.3a–3.3d.** 18 suites in one task is more than `steps_advice_over: 8`
   allows. The five install suites port in 3.5, because R16 has them drive `bin/riskrails.js`, which only
   exists there. So **`tests/lib.sh` is deleted in 3.5, not in 3.3**.
3. **The Python test runner lands in 2.1, not 3.3.** The first `tests/test_*.py` file ships in 2.1, and it
   reaches the verification command only if `tests/run-all.sh` runs it. So 2.1 adds one
   `python3 -I -m unittest discover` line to `run-all.sh`.
4. **E2E stays out of `verify_command`, and 3.H is split.** 3.H says `verify_command: python3 -I -m
   unittest discover tests`, but `testing.md:81` says `verify_command` must exclude e2e.
   `tests/test_end_to_end.py` therefore skips unless `AI_E2E=1` is set. `e2e_command` becomes
   `AI_E2E=1 python3 -I -m unittest tests.test_end_to_end` (3.H). Until 3.H, the last line of
   `tests/test-end-to-end.sh` runs that same command (added in 2.2a). The five install `.sh` suites live until
   3.5, so `verify_command` can only leave `run-all.sh` after 3.5: that edit is a second human row, 3.H2.
5. **R24's assertion anchor is `weight_set`, not `plan_registered`.** §Interfaces removes `plan_registered`,
   so the e2e case counts 0 `question_asked` after `weight_set`.
6. **The 3.4 fold.** R7/R8 fold `questions.md` and `review-report.md` into `task.md` "together with the guard
   rule". That puts `skills/ai-task/state.py` in 3.4's files, as step 1, before the `paths.py` rewrite.

## Global constraints (every task inherits these)

- Python stdlib only, 3.10+ (`sys.stdlib_module_names`); Node 18+ stdlib only, `"dependencies": {}`.
- Every Python entry point runs as `python3 -I` (hooks may add `-S`). Fixtures from client projects are
  synthetic, never copied journals (FC-S4).
- Weight: six axes 0–2; `W = Σ`; light ≤ 2, guarded 3–7, full ≥ 8 or reversibility = 2 or domain = 2;
  UNKNOWN = 1. A declared value may only raise a measured one; re-scoring is upward only, on reversibility and
  domain only.
- `weight` output ≤ 7 lines; `--long` ≤ 20. `/status` ≤ 20 lines. `weight.json` ≤ 80 lines, no `_comment`.
- `max_suite_runs` 2; `review_rounds_max` 2; `remediation_rounds` 2.
- Skills: new ≤ 300 lines, description ≤ 1024 B; alias ≤ 12 lines, description ≤ 80 B, first line
  `deprecated → /<new>`. Global managed block ≤ 2560 B; SessionStart total ≤ 10 KB.
- Guard latency (median of 5 × `AI_TIMED_FACTOR`): Bash 1 KB ≤ 40 ms, Edit/Write/Read ≤ 25 ms, 20 KB `sh -c`
  ≤ 100 ms. The guard always exits 0, never prints a traceback, and returns deny JSON or nothing.
- The golden (`tests/fixtures/guard-characterization/golden.txt`) is byte-identical through 3.1–3.3. It is
  re-recorded only in 3.4 (rules), 3.4b (names and paths only, every decision unchanged) and 3.5 (additive
  `npm` deny).
- The repo's own `.ai/policies/*`, `.ai/rules/*`, `docs/sdlc/constitution.md` and `CLAUDE.md` change only in
  the human rows 2.H and 3.H. Shipped templates change inside a task, with `tools/build-template-history.py`
  run in that same task.
- Names (from 3.4b): display `RiskRails`, machine `riskrails`; history (`docs/sdlc/**`, `.ai/reports/**`,
  journals, `files/`) is not renamed.

## Review focus (inputs the spec implies but no requirement test exercises)

1. **A user project with a task in flight is upgraded twice** (0007, then 0008, with `/setup --update` run
   between tasks or not at all). Expected: the task resumes in its mode, the scope guard stays armed, and no
   state is lost. Owner: 2.2a (`TestMigration0007::test_in_flight_state` runs 0007 then 0008 on one
   fixture) and 3.4b (`TestMigration0008::test_after_0007_in_flight`).
2. **The installer meets a hand-edited `~/.claude/settings.json`** that has foreign hooks, a non-ASCII
   `statusMessage`, and an entry equal to an old claude-agentic command. Expected: foreign keys survive,
   there is exactly one `ai-guard.py` entry, and a dated `backups/` copy exists. Owner: 3.5
   (`test_install_routes::test_foreign_keys_survive`).
3. **A declared file that does not exist yet, or a basename that is a common word** (`index`, `utils`).
   Expected: `weight` scores a new file scope 0 and behaviour 0, bounds the common word by the grep budget
   (UNKNOWN = 1, not 2), and never raises a traceback. Owner: 2.1 (`test_weight::test_new_file`,
   `test_common_word_basename`).
4. **The guard receives a malformed or non-UTF-8 payload, or an unknown `tool_name`.** Expected: allow
   silently, exit 0 (fail open outside the domain), as the shell guards do today. Owner: 3.1
   (`test_guard_characterization::test_malformed_payload`), with a matching golden case.
5. **`close` runs on a tree changed after the last green `verify`** (the human edits a file and resumes).
   Expected: the stale-tree fact requires a review or a fresh `verify`; `close` never archives silently. Owner:
   2.2a (`TestTwoFacts::test_human_edit_after_verify`).

## Files that change

Grouped by task; "new" / "edit" / "delete". Fixtures and history files are listed by directory.

| Task | Files |
|---|---|
| 1.1 | edit `skills/ai-init/templates/.ai/policies/risk-tiers.json`, `risk-tiers.md`; new `skills/project-update/history/<ver>/…` (by `tools/build-template-history.py`); edit `tests/test-project-update.sh`, `tests/test-ai-task-state.sh` (cap case) |
| 1.2 | edit `skills/ai-task/state.py`, `skills/ai-task/sensors.py`, `skills/ai-task/SKILL.md`, template `risk-tiers.json` + `.md`, history/; edit `tests/test-ai-task-state.sh`, `tests/test-ai-task-sensors.sh`, `tests/test-end-to-end.sh` |
| 1.3 | delete `hooks/fable-gate.py`, `hooks/codex-model-gate.py`, `tests/test-fable-gate.sh`, `tests/test-codex-model-gate.sh`; edit `settings.common.json`, `codex/hooks.json`, `install.sh` (retire the seven 2026-09-02 installed agents + Codex twins the way `reviewer.md` is retired at `install.sh:656-663`; `.bak` → `backups/<date>/`), `tests/run-all.sh`, install suites |
| 1.4 | new `skills/status/status.py`, `skills/status/SKILL.md`; edit `skills/ai-status/SKILL.md` (alias); edit `tests/test-ai-status-root.sh` |
| G0 | — (human: OQ10) |
| 2.1 | new `skills/ai-task/weight.py`, `skills/ai-init/templates/.ai/policies/weight.json`, `docs/weight.md`, `tests/test_weight.py`, `tests/fixtures/weight/`; edit `skills/ai-task/state.py` (`weight` subcommand only), `tests/run-all.sh` (unittest line) |
| 2.2a | edit `skills/ai-task/state.py` (new surface beside the old), `skills/ai-task/sensors.py` (`snapshot_tree`, `diff_files` exposed; nothing deleted), `skills/status/status.py` (delegates to `state.py status`), `skills/usage-report/usage-report.py`; new `skills/project-update/migrations/0007_weight_model.py`, `tests/fixtures/project-update/schema-v6/`, `tests/test_ai_task_state.py`, `tests/test_end_to_end.py`, `tests/test_usage_report.py`, `tests/test_project_update.py` (`TestMigration0007`); edit `tests/test-end-to-end.sh` (last line runs the Python e2e) |
| 2.H | human: `.ai/rules/hooks.md`, `.ai/rules/skills.md`, `docs/sdlc/constitution.md` C6, `CLAUDE.md` lesson 2, `.ai/policies/safety.md` blocker sentence, repo `.ai/policies/weight.json` via `update.py --apply` |
| G1 | — (human: OQ9) |
| 2.3 | new `skills/rr-{setup,spec,plan,build,review,ship}/SKILL.md`, `ai/using-riskrails.md`, `tests/test_skills_surface.py`, `tests/test_instruction_budget.py`; move `skills/status/` to `skills/rr-status/` (no `status` left; `skills/ai-status/SKILL.md` points at `rr-status`), the nine old `skills/*/SKILL.md` → aliases, `ai/workflows/*` (merged), `ai/agents/manager.md` (delete; replaced by `using-riskrails.md`), `instructions/stub.md`, `skills/ai-init/templates/.ai/AGENTS.md`, history/, `tests/test-shared-prompts-model-free.sh` (grep for `light ≤` / `guarded 3`) |
| 2.4 | delete `agents/{ai-context,ai-expert,ai-implementer,ai-indexer,ai-planner,ai-release,ai-risk,ai-security,ai-tester}.md.tmpl` and the matching `ai/agents/*.md`; edit `agents/ai-reviewer.md.tmpl`, `ai/agents/reviewer.md` (§Security from `security.md`), `scripts/render-codex-agents.py`, `hooks/runtime-gate.py`, `profiles/*.json`, `install.sh` enumerations; edit `tests/test-codex-agent-render.sh`, `test-runtime-gate.sh`, `test-profiles.sh` |
| 2.5 | new `skills/setup/setup.py`, `tests/test_setup.py`, `tests/fixtures/setup/new-shop-like/`; edit `skills/setup/SKILL.md`, `skills/project-update/adopt-map.json`, `tests/test-project-adopt.sh` |
| 2.6 | edit `skills/ai-task/state.py` (19 subcommands removed), `skills/ai-task/sensors.py` (≈ 300 lines left); new `tests/test_no_size_tokens.py`; edit `tests/test-ai-task-state.sh`, `tests/test-ai-task-sensors.sh` (cases of removed commands dropped, each listed in `task.md` with its reason) |
| 3.1 | new `hooks/ai-guard.py`, `hooks/guard/{__init__,common,git,paths,scope,ere}.py`, `tests/test_guard_characterization.py`, `tests/test_ere_unit.py`, `tests/test_guard_differential.py`, `tests/test_suite_parity.py`, `tests/test_imports.py`, `tests/fixtures/guard-port/` (frozen shell copies), the 20 KB timed fixture; edit `hooks/ai-{git,path,scope}-guard.sh` → exec shims, `tests/test-guard-characterization.sh` (+timed) |
| 3.2 | new `hooks/project-scaffold.py`, `skills/setup/scaffold_ai.py`, `tests/test_scaffold_idempotency.py`; edit `hooks/project-scaffold.sh`, `skills/ai-init/scaffold-ai.sh` → shims |
| 3.3a | guards: `tests/test-ai-{git,path,scope}-guard.sh`, `test-context-guard.sh`, `test-runtime-gate.sh` → `.py`; edit `.github/workflows/tests.yml` (matrix 3.10–3.13), `tests/run-all.sh` |
| 3.3b | state: `test-ai-task-state.sh`, `test-ai-task-sensors.sh`, `test-end-to-end.sh`, `test-ai-status-root.sh` → merged into or created as `.py`; `run-all.sh` |
| 3.3c | update: `test-project-update.sh`, `test-project-adopt.sh`, `test-merge-migration.sh`, `test-migration-0006.sh` → `.py`; `run-all.sh` |
| 3.3d | rest: `test-codex-agent-render.sh`, `test-codex-usage-report.sh`, `test-usage-report.sh`, `test-instruction-budget.sh`, `test-shared-prompts-model-free.sh` → `.py`; `run-all.sh` |
| 3.H | human: `.ai/policies/testing.md` Verification block + `:121-158` project specifics |
| 3.4 | step 1: edit `skills/ai-task/state.py` (questions and review into `task.md`), `tests/test_ai_task_state.py`, `tests/test_end_to_end.py`; step 2: edit `hooks/guard/paths.py`, `hooks/ai-path-guard-defaults.json`, `tests/fixtures/path-guard/`, golden, `.ai/project/known-risks.md`, `tests/test_ai_path_guard.py` |
| G2 | — (human: OQ8) |
| 3.4b | per spec table row 3.4b, plus new `skills/project-update/migrations/0008_renames.py`, `tests/test_rename.py`, `tests/fixtures/project-update/schema-v7/` |
| 3.5 | new `package.json`, `bin/riskrails.js`, `.claude-plugin/{plugin,marketplace}.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `hooks/hooks.json`, `hooks/codex-hooks.json`, `tests/test_install_routes.py`, five `tests/test_{install_dry_run,dual_runtime_install,codex_install,profiles,shared_tree}.py`; edit `settings.common.json`, `codex/hooks.json`, `install.sh` (wrapper, exit 2), `hooks/guard/git.py` (+ `npm publish`/`npm version` deny, separate step), golden (additive), README install section; delete the three `.sh` guard shims, the five install `.sh` suites, `tests/lib.sh` |
| 3.H2 | human: `.ai/policies/testing.md` `verify_command` |
| 3.6 | edit `.gitignore` (`.ai/reports/`), `docs/*`, `README.md` (links `weight.md`; FAQ entry removed), `docs/hook-performance.md`; delete `tests/run-all.sh`, `tests/test-end-to-end.sh` (wrapper), `.github/workflows/tests.yml` call to `run-all.sh` → unittest |

## Order of work

Each row is one `/ai-task` (or a human act outside a run). **Tier/mode**: before 2.H, the T-label under
today's rules (`.ai/rules/hooks.md:6`, `skills.md:6`, C6); from 2.H on, the mode `state.py weight` computes on
the row's files (the expected value is shown; the computed one wins). **Proof**: the task's own check, on
top of `verify_command` once to the end and `e2e_command` once.

### Phase 1 — numbers, deletions, `/status` (old rules)

- **G0 (human, before 1.1).** OQ10: the three open tasks on the production machine (ArgoCD 09-14, oroCRM
  09-30-002, abrites-site-v2 10-22-001) are closed. Tick here: `[x]`.
- **1.1 `max_suite_runs` 5 → 2 in the shipped template.** T2, workflow feature. Consumes: —. Produces: the
  template number that 0007's `min(old, 2)` relies on. Proof: `test-project-update.sh` (template history
  rebuilt), the cap case in `test-ai-task-state.sh`.
- **1.2 Size and paths stop gating.** **T4**, one STRONG review, `review_rounds_max` 2. `over_budget` no
  longer blocks `skipped_green`; `path_scopes.min_tier` is ignored and printed as a hint; `step-split` stays
  but is not demanded. Proof: R4 phase 1 — `test-ai-task-state.sh` closes a 2 000-line, 40-file fixture task
  without a size refusal; `test-ai-task-sensors.sh`; e2e.
- **1.3 Shims, stale agents, `.bak`.** **T4** (install; FC-A4 bootstrap price). Workflow refactoring
  (deletion only). Proof: R29 phase 1 — the install suites assert the two hooks, the seven agents and every
  `*.bak` are absent and `backups/<date>/` exists; `test-runtime-gate.sh` green.
- **1.4 `/status` as a script + `ai-status` alias.** T2. Produces: `status.py [--root] [--cost]`, ≤ 20 lines
  (R31); reads `current.json`, `events.jsonl` and `risk-tiers.json` directly until 2.2a. Proof:
  `test-ai-status-root.sh` + a line-count case.

### Phase 2 — the weight model (old rules until 2.H)

- **2.1 `weight.json` + `weight.py` + `state.py weight` (read-only).** T3. Produces
  `weight.compute(root: Path, files: list[str], declared: dict[str, tuple[int, str]], goal: str = "") -> Weight`,
  where `Weight` holds `w`, `axes`, `hints`, `unknown`, `evidence`, `mode`. Produces the CLI
  `state.py weight --files … [--goal] [--declare axis=n:"why"]… [--json|--long|--mirror]` and the
  template `weight.json` exactly as §Interfaces. `docs/weight.md` carries the FC-B1 text. Proof: R2, R10 —
  `tests/test_weight.py`: the 13 SQ1 rows, each asserting its mode;
  `test_declaration_below_measurement_is_replaced`; `test_mirror_fresh`; `test_grep_budget`;
  `test_new_file`; `test_common_word_basename`. Before close: FC-D4 — score three synthetic file lists
  shaped like real productEditorApp and Learning Workbench tasks; all land in guarded.
- **2.2a New state surface beside the old (riskiest task; see Risks).** **T4**, the last task under the old
  rules, one STRONG review. Adds `start` (+ `--amend`, `--mode --by`), `step-done`, `verify` (`--scope`,
  `--expect fail`, re-score up, `SUITE_BUDGET`, Codex-only red is a finding), `review`, `close` (two facts,
  mode table, gate), `status`, `ask`, `answer`; `task.md` writer; handoff at the five boundaries;
  `weight_set`, `weight_raised`, `mode_set`, `verify_run`, `review_verdict` events plus the `tier_set` compat
  event; migration 0007 with `patch_state` for a task in flight. The old subcommands keep working and are
  not edited. Consumes: `weight.compute` (2.1). Produces: the §Interfaces `state.py` surface and the
  schema-7 state keys. Proof: R3, R4 (phase 2), R5 (three calls), R6 (`TestTwoFacts`, 4 cases + Review
  focus 5), R7, R8 (phase 2 listing), R18, R19, R20, R21, R23, R24, R25, R26, R27, R33 — test names as in
  the spec, in the new `tests/test_*.py` files; e2e on both runtimes.
- **2.H (human, outside a run).** Reword `.ai/rules/hooks.md`, `skills.md`, C6 and `CLAUDE.md` lesson 2 to
  modes, using FC-B1's effect wording. Add the `safety.md` sentence: "doubt on reversibility or domain is a
  blocker; other doubt is written to `task.md` and the work continues". Run
  `python3 -I skills/project-update/update.py --apply` (migration 0007 on this repository). Check:
  `/status` shows schema 7. `[x]` 2026-10-29: `.ai/rules/hooks.md:5-6`, `skills.md:5`, constitution C6 and
  `CLAUDE.md` lesson 2 weigh by modes; `/rr-status` shows schema 8 (0007 and 0008 applied). Open: the
  `safety.md` sentence is not in `.ai/policies/safety.md:77-80` ("When in doubt") — the human's edit.
- **G1 (human, before 2.3).** OQ9: no built-in or installed-plugin collision for `/plan`, `/review`,
  `/status`, `/setup`, `/spec`, `/build`, `/ship`, or a decision to document `riskrails:<name>`. `[x]`
  2026-10-26: three collide; decided `rr-<name>` for all seven and no bare `status` (Decisions, G1 / OQ9).
- **2.3 Skill text: seven skills, nine aliases, `using-riskrails.md`.** Expected guarded (behaviour 1 hint
  for pipeline + scope 2). Skills call only the 2.2a surface. Proof: R1, R5 (≤ 400 lines), R10 (model-free
  grep), R28 (`test_session_start_cost` ≤ 10 KB), R32.
- **2.4 Agents 14 → 5 templates, budgets out of `runtime-gate.py`.** Expected guarded (W ≈ 4). Proof: R11
  (the render lists exactly `Explore`, `log-reader`, `ai-discovery`, `ai-reviewer`, `architect`, with no
  `-strong`/`-balanced` twins; see the note below), R29 phase 2 (`test-runtime-gate.sh` keeps outage cases
  only; `test-profiles.sh` asserts `budgets.fan_out` and `budgets.direct_mode` are gone).
- **2.5 `/setup`: survey, check, adopt-own, superpowers line.** Expected guarded (reversibility 1). Proof: R9
  (`VERIFY_COMMAND_MISSING` exit 1; `toolbox.md` and router rows on the new-shop-shaped fixture), R28
  (prints the `enabledPlugins` line and never writes it), `test-project-adopt.sh`.
- **2.6 Remove the 19 old subcommands and the `sensors.py` checks.** Expected guarded (scope 2, behaviour 1).
  Workflow refactoring (deletion only). Precondition: `grep -rn` over `skills/ hooks/ ai/ instructions/`
  finds no caller of a removed name except the alias texts. Proof: R4 phase 2 (`test_no_size_tokens.py`),
  R6 (`sensors.py` exposes only `snapshot_tree`, `diff_files`, `run`), every removed `.sh` case listed in
  `task.md`.

> **Note on R11's count.** The spec lists "`Explore`, `log-reader`, `ai-discovery`, `ai-reviewer` (with a
> `focus: security` brief), `architect`" as "six templates". That is five files plus a brief. 2.4 ships
> **five** templates. `test_codex_agent_render` asserts exactly those five. If a sixth was meant, name it at
> this plan's review.

### Phase 3 — one language, final name, installer

- **3.1 Guard port: one process, exec shims.** Expected guarded (scope 2, novelty 1). Workflow refactoring.
  The golden must stay byte-identical. Proof: R12 (golden byte-identical at the base commit), R14 (`TestTimed`:
  the 20 KB case fails on the shell tree before the port, then passes), R15 (`test_imports.py`),
  `test_guard_differential.py` against the frozen shell copies, Review focus 4.
- **3.2 Scaffold port.** Expected light/guarded. Proof: both scaffold suites green on the same tree.
- **3.3a–3.3d Suite ports, four tasks.** Expected light (tests only). Each `.sh` is deleted in the same task
  once its twin is green on the same tree. Proof: R13 (`test_suite_parity.py`: the `.sh` case names are a
  subset of the `.py` names; a drop is listed in `task.md` with "shell mechanics"); `run-all.sh` green after
  each task; CI matrix 3.10–3.13 in 3.3a.
- **3.H (human, outside a run, after 3.3d).** In `testing.md`: `e2e_command: AI_E2E=1 python3 -I -m
  unittest tests.test_end_to_end`, `single_test: python3 -I -m unittest tests.test_<name>`, and `:121-158`
  project specifics. `verify_command` stays `bash tests/run-all.sh`, because the five install `.sh` suites
  live until 3.5. Until 3.H, `tests/test-end-to-end.sh` survives 3.3b as a one-line wrapper that execs the
  Python e2e. Check: `/status`. `[x]` — `e2e_command` in `.ai/policies/testing.md:89`.
- **3.H2 (human, after 3.5).** `verify_command: python3 -I -m unittest discover tests` (e2e skips itself
  without `AI_E2E`). `tests/run-all.sh` and the e2e wrapper are then deleted in 3.6. `[x]` 2026-10-29
  (T-2026-10-29-1035): `verify_command: python3 -I -m unittest discover -s tests -p 'test_*.py'`
  (`testing.md:87`).
- **3.4 Fold + path-guard rule rewrite.** **Full** (behaviour 2, domain 2), with a security-focus STRONG
  review. Step 1 folds questions and review into `task.md` (R7, R8 phase 3). Step 2 rewrites `paths.py`
  (R22): secrets denied for read and write; agent writes to `.ai/state/**`, `reports/<id>/{events.jsonl,
  task.md}`, `.ai/policies/**` during a task, `.claude/settings*.json` and the guards' config denied;
  `approve` / `set --by` / `--confirm-delete` denied; top-level operator split only; > 4 KB denied in one
  sentence. Golden re-recorded, a fixture for every remaining deny, the `sh -c` bypass recorded in
  `known-risks.md` (SQ13). Proof: `test_ai_path_guard.py` + new fixtures, `test_guard_characterization.py`,
  e2e listing = {events.jsonl, task.md}.
- **G2 (human, before 3.4b).** OQ8: `npm view riskrails` (free, or use `@<owner>/riskrails`) and a web and
  trademark search for "RiskRails". `[x]` — closed by vanssata, 2026-10-27: unscoped `riskrails`, npm user
  `ikakarov`, org `vanssata`. Published: `npm view riskrails` → `3.0.0`, maintainer `ikakarov`, repository
  `vanssata/claude-agentic-sdlc-module` (checked 2026-10-29).
- **3.4b Renames (`state.json`, RiskRails).** **Full** (reversibility 2 via the migrations hint). Workflow
  refactoring. Proof: R34 (`test_reads_legacy_state_name`, `TestMigration0008` with a task in flight, a
  path-guard fixture for each name), R35 (`test_rename.py` allow-list; markers rewritten with the user's text
  byte-identical; new install home + symlink), Review focus 1, and a scripted golden check: every changed
  line contains an old name or path and its decision is unchanged.
- **3.4c State file move (R34's contract half).** Expected guarded. After a release has shipped 3.4b: a
  migration moves `.ai/state/current.json` to `state.json` (MOVES), `state.py` starts new tasks in
  `state.json`; readers already take either. Proof: `TestMigration0009` with a task in flight; a revert
  check that 3.4b's code still arms on the moved file.
- **3.5 `npx riskrails`, manifests, entries switched, shims and `lib.sh` deleted.** **Full** (W 8). Proof:
  R16 (five install suites ported, driving `bin/riskrails.js`), R17 (`test_install_routes`: equal effective
  inventories, no duplicate hook command, Review focus 2), risk 6 (`test_codex_install` asserts the `/hooks`
  trust message), the `npm` deny as its own step with an additive golden. Manual: on-screen `/hooks` trust in
  Codex. The human publishes (FC-A5) with 2FA and provenance, and the docs print `npx riskrails@<version>`
  (FC-S1).
- **3.6 Cleanup.** Expected light. Proof: R30 (`test_scaffold_idempotency.py` asserts the shipped
  `gitignore.snippet` unchanged), `test_shared_prompts_model_free.py`, a link check over `README.md` and
  `docs/`.

**Riskiest task: 2.2a.** It changes the approval path and ships a migration into user projects. It is the
last task tiered by the old labels, and every later task runs through what it adds. It moved as far forward
as its one dependency (2.1) allows. It was split so that adding the surface (2.2a) and deleting the old one
(2.6) are separate approvals, and the old pipeline keeps working between them. **The riskiest task for the
user's safety is 3.4**, because it allows what was denied. It cannot move earlier (it needs the port), so it
gets a fixture for every remaining deny and a security-focus review.

## Risks

The spec's §Risks 1–18 stand, with their tests. This plan adds the risks of its own ordering and answers the
two questions.

**What could this break?**

| # | What breaks | Where | How we notice | Mitigation in this plan |
|---|---|---|---|---|
| P1 | The pipeline running 2.3 calls a subcommand 2.2 removed | callers: `skills/ai-task/SKILL.md`, `ai/workflows/*`, `context-guard.py`, `status.py` | the 2.3 task fails at its first `state.py` call | 2.2 split; 2.6's caller-grep precondition |
| P2 | A user project mid-task meets 0007 (then 0008) | migrations, other environments | `TestMigration0007::test_in_flight_state`, Review focus 1 | `patch_state` maps tier → mode, `unknown: ["migrated"]`; `state.py` fills defaults in memory |
| P3 | Python tests written in phase 2 never run | config: `tests/run-all.sh`, `verify_command` | a deliberately red `test_weight` case fails `run-all.sh` in 2.1 | the unittest line in `run-all.sh` lands in 2.1 |
| P4 | E2E runs twice, or inside the fast loop | `testing.md:81` | the `verify_command` duration doubles; the e2e journal shows two runs | `AI_E2E` skip; 3.H wording |
| P5 | The golden drifts inside a "refactoring" | 3.1–3.3, 3.4b | a byte diff of the golden at the task's base | golden frozen except in 3.4, 3.4b (scripted name-only check) and 3.5 (additive) |
| P6 | Codex guards silently skipped after the entries change | other environment: Codex `trusted_hash` | `test_codex_install` trust message; manual `/hooks` | entries change only in 3.5; shims keep commands identical in 3.1–3.4b |
| P7 | The installer drops a user's own hooks or permissions | config: `~/.claude/settings.json`, `config.toml` | `test_install_routes::test_foreign_keys_survive` | Node merge keeps a dated backup; Review focus 2 |
| P8 | The production machine's open tasks keep old guards armed against new rules | other environments | G0 unticked | G0 gates phase 1 |
| P9 | Human rows 2.H/3.H are late, and later tasks are tiered by stale wording | policy | `/status` schema ≠ 7 at 2.3's start | 2.3's first check is schema 7; tasks after 2.H read the mode from `weight` |
| P10 | The R11 count is ambiguous (five vs six templates) | 2.4 | this plan's review round | the note under 2.4 |

**Which step is riskiest, and can it move earlier or be split?** 2.2a, as above: split (2.2a / 2.6) and as
early as 2.1 allows. Phase 3's riskiest, 3.4, is split into a fold step and a rule step inside one task, so
a review can reject the rule step and keep the fold. It cannot precede 3.1.

## Proof (tests)

| Req | Test / command | Task |
|---|---|---|
| R1 | `tests/test_skills_surface.py` (17 SKILL.md, byte and line caps) | 1.4 (status alias), 2.3 |
| R2 | `tests/test_weight.py` — SQ1 rows, hint-wins case | 2.1 |
| R3 | `test_ai_task_state.py::TestModes` | 2.2a |
| R4 | 1.2: size-fixture case in `test-ai-task-state.sh`; `test_size_is_reported_not_gated` (2.2a); `test_no_size_tokens.py` (2.6) | 1.2, 2.2a, 2.6 |
| R5 | `test_end_to_end.py` light path = 3 calls (2.2a); `test_instruction_budget.py` ≤ 400 lines (2.3) | 2.2a, 2.3 |
| R6 | `TestTwoFacts` (4 + Review focus 5); `sensors.py` surface check | 2.2a, 2.6 |
| R7 | `test_task_md_sections`; guard denies agent write to `task.md` | 2.2a, 3.4 |
| R8 | e2e `reports/<id>/` listing: phase 2 set, then {events.jsonl, task.md} | 2.2a, 3.4 |
| R9 | `tests/test_setup.py` | 2.5 |
| R10 | `test_weight::test_mirror_fresh`; model-free grep | 2.1, 2.3 |
| R11 | `test-codex-agent-render.sh` (→ `.py` in 3.3d) renders exactly the shipped list | 2.4 |
| R12 | `test_guard_characterization.py` golden byte-identical | 3.1 |
| R13 | `test_suite_parity.py` | 3.1 (created), 3.3a–d, 3.5 |
| R14 | `TestTimed` (1 KB, Edit/Write/Read, 20 KB; fails on the shell tree first) | 3.1 |
| R15 | `test_imports.py`; CI matrix 3.10–3.13 | 3.1, 3.3a |
| R16 | five ported install suites drive `bin/riskrails.js` | 3.5 |
| R17 | `test_install_routes.py` | 3.5 |
| R18 | `test_usage_report.py` (schema-6 and schema-7 journals) | 2.2a |
| R19 | e2e light path under `claude` and `codex` payloads; Codex-only red is recorded, not refused | 2.2a |
| R20 | template number (1.1); `test_suite_budget` (2.2a) | 1.1, 2.2a |
| R21 | e2e `handoff_written` ≤ 5 on the guarded path | 2.2a |
| R22 | `test_ai_path_guard.py` + new fixtures; characterization | 3.4 |
| R23 | `TestMigration0007` on `schema-v6/` (task in flight; no "claude"/"codex" in the source) | 2.2a |
| R24 | e2e: 0 `question_asked` after `weight_set` | 2.2a |
| R25 | `test_amend` | 2.2a |
| R26 | `DROP TABLE` fixture → full_irreversible at `verify` | 2.2a |
| R27 | `test_mode_override` | 2.2a |
| R28 | `/setup` superpowers line (`test_setup`); `test_session_start_cost` ≤ 10 KB | 2.5, 2.3 |
| R29 | install suites: files absent (1.3); `test-runtime-gate.sh` outage-only, `test-profiles.sh` keys gone (2.4) | 1.3, 2.4 |
| R30 | `test_scaffold_idempotency.py` snippet unchanged | 3.6 |
| R31 | `test-ai-status-root.sh` + ≤ 20 lines | 1.4 |
| R32 | `test_instruction_budget.py` (stub wording; block ≤ 2560 B) | 2.3 |
| R33 | `test_expect_fail` | 2.2a |
| R34 | `test_reads_legacy_state_name`, `TestMigration0008`, path-guard fixtures for both names | 3.4b |
| R35 | `test_rename.py`, `TestMigration0008` markers, install suites (home + symlink) | 3.4b |

Every task: `verify_command` once, to the end, then `e2e_command` once; failures fixed as one batch; output
shown in `task.md`.

## Rollback

- **Before merge:** every task ends at human approval with nothing committed by an agent. Rejecting it means
  `git restore` / `git clean` of the task's named files, done by the human.
- **After merge, code tasks** (1.1–1.4, 2.1, 2.3–2.6, 3.1–3.3d, 3.6): `git revert <commit>`. Each is one
  commit and leaves the tree green. Reverting 2.6 restores the old subcommands, and the aliases still
  resolve.
- **2.2a / migration 0007:** the move keeps `risk-tiers.json` (original kept), and the old subcommands still
  exist until 2.6. A revert of 2.2a plus restoring `.ai/VERSION` 6 returns a project. A project with a
  task in flight after 0007 keeps `tier` readable through the in-memory defaults. Do not revert 2.2a after
  2.6 without reverting 2.6 first.
- **2.H / 3.H / 3.H2:** the human reverts their own policy commits. `/status` confirms the schema.
- **3.4:** revert the commit. The golden returns with it. The old deny set is the 3.1 port's, which stays.
- **3.4b / migration 0008:** the state file does not move in 3.4b (expand/contract, review H1, Q2=B): every
  task stays in `current.json`, which the reverted code reads, so no guard disarms. 0008 renames only the
  markers and routes; a project that ran it is returned by restoring `.ai/VERSION` 7 and its instruction
  files' and `.ai/AGENTS.md`'s marker and route lines (`git restore` of those files, or the `[0008]` items in
  `.ai/reports/project-update-<date>/original/`) — the old `update.py` refuses schema 8 until then. The
  installer's symlink at the old home stays valid; re-running the old installer recreates the old home.
- **3.4c / the state-file move:** shipped only after a release has carried 3.4b's two-name readers, so a
  revert of 3.4c leaves `state.json` readable by every guard.
- **3.5:** `install.sh` from the previous tag still installs, and the shims are restorable from the parent
  commit. A published npm version cannot be unpublished after 72 h: mark it with `npm deprecate
  riskrails@<v> "<reason>"` (human) and publish a fix. Plugin manifests are removed by reverting; users
  `/plugin uninstall riskrails`.
- **Installer merges:** every merge writes `backups/<date>/` first. Restoring that file is the rollback for a
  bad `settings.json`/`config.toml` merge.
