# Spec: RiskRails (formerly claude-agentic) redesign — job-named commands, weight-based risk, one language

Intent: `docs/sdlc/intent/claude-agentic-redesign.md`

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Written 2026-10-25 on branch `new-refactor` (HEAD `1b388ac`). Design by the `architect` agent from the intent,
the second analysis §6–§8 (Claude Doc https://claude.ai/artifact/UqxcHvZhP1Nn7xaLhnkiDm, rev 15, extracted to
the git-ignored `files/second-analysis-2026-10-24.extract.md`; line numbers "second analysis :N" refer to that
file), the first analysis `docs/redesign-analysis-2026-10-24.md` §3–§4, `docs/sdlc/specs/direct-mode-diet.md`,
`.ai/policies/risk-tiers.json`, `.ai/policies/testing.md`, `skills/ai-task/state.py`, `hooks/*`,
`settings.common.json`, `codex/hooks.json`, `install.sh`, `skills/project-update/`, `agents/*.md.tmpl`,
`tests/`, `skills/usage-report/usage-report.py`, `.ai/AGENTS.md`, `instructions/stub.md`, and the installed
superpowers 7.0.1 manifests. Not read: `.ai/state/*`, `.ai/reports/**`. Policy pass and flagged concerns by
the session.

Vocabulary: the three modes are written **light / guarded / full** (recommendation; the developer decides,
OQ3). "Today's rules" = `.ai/rules/hooks.md`, `.ai/rules/skills.md`, constitution C6. Every requirement names
the intent outcome it serves (quoted) and the phase it lands in.

Corrections taken on 2026-10-25 (the one review round of `/sdlc-spec`): **OQ11 = yes** — the state file is
renamed `current.json` → `state.json` (R34); **the plugin is named RiskRails** (R35) — display name `RiskRails`,
machine name `riskrails`. Both renames land in one refactoring task of their own, 3.4b, after the path-guard
rewrite and before the installer, so the npm package is first published under its final name. Until 3.4b,
text below that names `claude-agentic` or `current.json` means the current identifiers.

## Requirements

Each: testable (test file / case / measurement), intent outcome it serves (quoted ≤ 8 words), phase.

- **R1 Command surface.** Seven skills, lifecycle order: `setup`, `spec`, `plan`, `build`, `review`, `ship`,
  `status`. The ten old names (`ai-init ai-audit ai-status ai-task project-init project-update sdlc-intent
  sdlc-spec sdlc-plan usage-report`) stay for one version as alias skills whose first line prints
  `deprecated → /<new>` and whose body is one `Read` of the new SKILL.md. Test: `tests/test_skills_surface.py`
  — exactly 17 `skills/*/SKILL.md`, each alias ≤ 12 lines with a description ≤ 80 bytes, each new skill
  ≤ 300 lines and a description ≤ 1024 bytes. Outcome: "six commands named by the job". Phase 1 (aliases
  for `status`), phase 2 (the rest).
- **R2 Weight.** `state.py weight --files … [--goal …] [--declare axis=n:"evidence"]…` computes six axes from
  `.ai/policies/weight.json` and prints ≤ 7 lines (6 axes + verdict), `--json` for machines. Test:
  `tests/test_weight.py` scores the 11 cases of the table in SQ1 and asserts the mode of each; a case
  where the session declares below the deterministic hint asserts the hint wins. Outcome: "logical weight
  in at most seven lines". Phase 2.
- **R3 Modes.** `weight.json.modes` decides plan shape, reviewer tier, human stops, suite scope; `close`
  enforces them. Test: `tests/test_ai_task_state.py::TestModes` — light closes without a review when both
  facts are green; guarded refuses `close` until one `review` verdict exists; full refuses until the gate is
  approved; full+irreversible requires `approve --confirm "<operation>"`. Outcome: "picks one of three
  modes automatically". Phase 2.
- **R4 Size never gates.** No `diff_budget`, `step-split`, `DIFF_BUDGET_EXCEEDED`, `over_budget`, `rescore`
  sensor. Lines/files appear once, in `task.md` §Changes, plus one advisory line when a plan has > 8 steps.
  Test: `tests/test_ai_task_state.py::test_size_is_reported_not_gated` closes a 2 000-line, 40-file fixture
  task in light mode; `tests/test_no_size_tokens.py` greps `skills/ hooks/ ai/ instructions/` for the five
  tokens. Outcome: "Lines and files are reported, never gating". Phase 1 (gate off), phase 2 (code gone).
- **R5 Light = three calls, ≈ 400 lines of policy.** `start`, `verify`, `close`. Test: `tests/test_end_to_end.py`
  counts `state.py` invocations on the light path (= 3); `tests/test_instruction_budget.py` measures
  `skills/build/SKILL.md` + `weight.json` + the Verification block of `testing.md` ≤ 400 lines. Outcome:
  "A light task is three state.py calls". Phase 2.
- **R6 Two facts decide the review.** `close` requires a model review only when (a) the last `verify` is not
  green on the current tree hash, or (b) the tree diff since `base_tree` contains a file outside the task's
  files. `sensors.py` shrinks to `diff` (tree snapshot + file list) and `run` (command runner); `bite`,
  `duplicates`, `traceability`, `plan_sections`, `lint`, `typecheck`, `rescore`, `detect` are deleted.
  Test: `tests/test_ai_task_state.py::TestTwoFacts` (4 cases: green/green → no review; stale tree → review;
  out-of-scope file → review; red suite → review). Outcome: "Two deterministic facts decide". Phase 2.
- **R7 One artefact.** `.ai/reports/<task-id>/task.md`, sections in §Interfaces, written only by `state.py`.
  Test: `tests/test_ai_task_state.py::test_task_md_sections` after an e2e run; phase 3: the guard denies an
  agent write to it (fixture + golden). Outcome: "One artefact per task in the repository". Phase 2 (file),
  phase 3 (questions/review folded in, guard rule).
- **R8 Three control files.** The state file (`current.json`, `state.json` from task 3.4b — R34), `events.jsonl`, `task.md`. `sensors.json`, `review-ledger.md`,
  `tests-*.log` under `reports/` go away in phase 2 (logs move to `.ai/state/logs/`, git-ignored);
  `questions.md` and `review-report.md` fold into `task.md` in phase 3 step 4 together with the guard rule.
  Test: `tests/test_end_to_end.py` lists `reports/<id>/` after close: phase 2 = {events.jsonl, task.md,
  questions.md?, review-report.md?}; phase 3 = {events.jsonl, task.md}. Outcome: "Three control files".
- **R9 `/setup` adopts and requires `verify_command`.** `skills/setup/setup.py check` exits 1
  `VERIFY_COMMAND_MISSING` when `testing.md` has no `verify_command:` line or it is `none`; `--adopt` writes
  `.ai/policies/toolbox.md` (inventory with links, no copies) and router rows. Test: `tests/test_setup.py`
  on a fixture shaped like new-shop (`.claude/{skills,rules,agents,hooks}`, `bin/*.sh`). Outcome: "/setup
  adopts an existing project toolbox". Phase 2.
- **R10 One weight table, one mirror.** `weight.json` (≤ 80 lines, no `_comment`) and `weight.md` generated
  by `state.py weight --mirror` carrying `sha256:` of the JSON; README and docs link. Test:
  `tests/test_weight.py::test_mirror_fresh`; `tests/test_shared_prompts_model_free.py` gains a grep that
  the strings `light ≤` / `guarded 3` appear in no file but `weight.json`, `weight.md`, `docs/weight.md`.
  Outcome: "lives in one file with one generated mirror". Phase 2.
- **R11 Agents ≤ 8.** Six templates: `Explore`, `log-reader`, `ai-discovery`, `ai-reviewer` (with a
  `focus: security` brief), `architect`, plus `ai-implementer` only if the developer keeps it (SQ3). Test:
  `tests/test_codex_agent_render.py` renders exactly the shipped list; no `-strong`/`-balanced` twins.
  Outcome: "Agents go from 14 to 7 or 8". Phase 2.
- **R12 One PreToolUse process, byte-identical.** `hooks/ai-guard.py` answers Read/Edit/Write/MultiEdit/
  NotebookEdit/Bash (Codex: Bash/apply_patch/Edit/Write) with the git, path and scope checks as modules;
  `tests/fixtures/guard-characterization/golden.txt` unchanged at the port's base commit. Test:
  `tests/test_guard_characterization.py` (ported) — every run byte-identical; the three `.sh` guards become
  exec shims so `settings.common.json`/`codex/hooks.json` entries do not change in that task. Outcome: "The
  plugin is one language". Phase 3 step 1.
- **R13 Suites translated case by case.** Each `tests/test-<x>.sh` → `tests/test_<x>.py` with the same case
  names (the `pass "…"` strings become test method names/docstrings), inputs and expectations; a drop is
  listed in the task's `task.md` with the reason "shell mechanics". Test: `tests/test_suite_parity.py`
  compares the case-name sets while both files exist; the `.sh` is deleted in the same step once the twin
  is green on the same tree. Outcome: "The test suite is Python too". Phase 3 step 3.
- **R14 Latency.** One `ai-guard.py` call: Bash 1 KB ≤ 40 ms, Edit/Write ≤ 25 ms, Read ≤ 25 ms, a 20 KB
  `sh -c` line ≤ 100 ms (bash today: 1 645 ms); median of 5, scaled by `AI_TIMED_FACTOR` (default 1, CI
  may set 3). Test: `tests/test_guard_characterization.py::TestTimed` with the 20 KB fixture — it fails on
  the shell tree before the port. Outcome: "Hook latency does not regress". Phase 3 step 1.
- **R15 Stdlib only, 3.10+.** Test: `tests/test_imports.py` scans `hooks/ skills/ tests/ tools/ scripts/` for
  non-stdlib imports (`sys.stdlib_module_names`); CI matrix 3.10–3.13. Outcome: "python3 is the only one".
  Phase 3.
- **R16 `npx riskrails`.** Node 18+ stdlib, same flags as `install.sh:3-4` plus `--home`/`--codex-home`
  (env `CLAUDE_DIR`/`CODEX_DIR` honoured), idempotent, installs `.py` hooks only; `install.sh` becomes a
  wrapper that prints the `npx` line and exits 2. Test: the five install suites ported
  (`test_install_dry_run`, `test_dual_runtime_install`, `test_codex_install`, `test_profiles`,
  `test_shared_tree`) drive `bin/riskrails.js`. Outcome: "One install command for both runtimes".
  Phase 3 step 5.
- **R17 Plugin manifests, identical effective tree.** `.claude-plugin/plugin.json`, `.claude-plugin/
  marketplace.json`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `hooks/hooks.json`.
  Test: `tests/test_install_routes.py` installs (a) `npx` alone and (b) plugin-cache + `npx` into scratch
  homes and asserts equal effective inventories (hook command → file sha, skill → sha, agents, profile.json,
  managed block, settings keys) and that no hook command appears twice. Outcome: "The two routes must leave
  an identical tree". Phase 3 step 5.
- **R18 Old journals readable.** `weight_set` is the new event; `tier_set {tier: <T-label>, mode, w}` is
  still emitted for one version; `usage-report --task` prints `mode` when present, else `tier`. Test:
  `tests/test_usage_report.py` with a schema-6 and a schema-7 journal fixture. Outcome: "Old journals must
  stay readable". Phase 2.
- **R19 Codex best effort.** Every public `state.py` command and `weight` run under `AI_RUNTIME=codex`; agents
  render from the one template set; a Codex-only failure in the suite is a finding, not a gate for a
  Claude-side change (recorded in `task.md`, `close` not blocked). Test: `tests/test_end_to_end.py` runs the
  light path twice (claude, codex payloads). Outcome: "Codex is best effort". Phase 2.
- **R20 `max_suite_runs` 2.** Third `verify --scope suite|all` exits 6 `SUITE_BUDGET`; `--by <human>` from a
  terminal passes and journals `human_set`. Test: `tests/test_ai_task_state.py::test_suite_budget`. Phase 1
  (number in the shipped template), phase 2 (`verify` refusal text).
- **R21 Handoff at boundaries.** `handoff.md` is written at `start`, first green `verify`, `review` verdict,
  `close`, and on PreCompact; `status` renders it on demand without writing. Test: e2e counts
  `handoff_written` ≤ 5 on the guarded path. Outcome: "handoff.md is written at phase boundaries". Phase 2.
- **R22 Path-guard rule rewrite after the port.** `hooks/guard/paths.py` ≈ 250 lines: deny secrets (read +
  write), deny agent writes to `.ai/state/**`, `reports/<id>/{events.jsonl,task.md}`, `.ai/policies/**`
  during a task, `.claude/settings*.json`, the guards' own config; deny `approve`/`set --by`/
  `--confirm-delete` invocations; reads of non-secrets always allowed; top-level operator splitting only
  (no `sh -c`/`eval` re-parse); a command > 4 KB denied with one sentence. Golden re-recorded; the ported
  suite plus new fixtures pin every deny that remains. Test: `tests/test_ai_path_guard.py` (ported) + new
  cases; `tests/test_guard_characterization.py`. Phase 3 step 4.
- **R23 Migration 0007.** `risk-tiers.json` → `weight.json` (move, original kept), `tier` → `mode` + `weight`
  in an in-flight state, `examples` → `modes.<mode>.examples`, `path_scopes` → `domain.modules` / `hints` /
  `reversibility.*`, `max_suite_runs` → min(old, 2), `risk-tiers.md` → `delete?`, `.ai/VERSION` 6 → 7.
  Test: `tests/test_project_update.py::TestMigration0007` on fixture `schema-v6/` (one with a task in
  flight); migration source contains neither "claude" nor "codex". Phase 2 (ships with the state.py
  surface).
- **R24 Questions once.** `/plan` collects questions; during `/build` only a real blocker stops: a guard
  refusal, a re-score to reversibility/domain = 2, or a plan assumption proven false. Test: e2e guarded path
  journals 0 `question_asked` after `plan_registered`. Phase 2.
- **R25 Scope amended in place.** `state.py start --amend --files "+a,+b" --why "…"` extends the task's
  files, journals `scope_change`, never returns to a plan stage. Test: `test_ai_task_state.py::test_amend`.
  Outcome: "SCOPE_CHANGE_REQUIRED should amend the step in place". Phase 2.
- **R26 Re-score only up.** At `verify` and `close`, reversibility and domain are recomputed from the tree
  diff; a raise changes the reviewer tier and the gate, journals `weight_raised`, never restarts; other
  axes are not recomputed. Test: fixture whose diff adds `DROP TABLE` to a migration → full+irreversible at
  `verify`. Phase 2.
- **R27 Override.** `start --mode <m> --by <who>`: raising is free; lowering needs a terminal or
  `AI_UNATTENDED=1` (WP2 human condition) and is journaled `mode_set {from, to, by}`. Test:
  `test_ai_task_state.py::test_mode_override`. Phase 2.
- **R28 Superpowers measured.** `/setup` prints whether superpowers is enabled and, for variant A, the exact
  `enabledPlugins` line (never writes it). `tests/test_instruction_budget.py::test_session_start_cost`
  measures managed blocks + handoff (≤ 30 lines) + `using-superpowers` (3.6 KB) and fails over 10 KB. Phase 2.
- **R29 Removals.** `hooks/fable-gate.py`, `hooks/codex-model-gate.py`, the seven 2026-09-02 agents and their
  Codex twins, every `.bak` (one dated `backups/` directory instead), `profiles/*.claude_agentic.budgets.
  {fan_out,direct_mode}` and the `DIRECT_MODE_CAP` exit; `runtime-gate.py` keeps the outage reroute and
  `expert.without_asking`. Test: install suites assert the files are absent; `test_runtime_gate.py` keeps
  its outage cases only. Phase 1 (files), phase 2 (budgets).
- **R30 Reports out of this repository's git.** `.gitignore` gains `.ai/reports/` here only; the shipped
  `gitignore.snippet` is unchanged (user projects keep `task.md` tracked). Test: `tests/test_scaffold_
  idempotency.py` asserts the snippet. Phase 3 step 6.
- **R31 `/status` is a script.** `skills/status/status.py` ≤ 20 output lines (root, task, mode, stage,
  files, verify, review, questions, schema, `--cost` delegates to `usage-report.py`). Test:
  `tests/test_ai_status_root.py` (ported) + line count. Phase 1.
- **R32 Readers with judgement on BALANCED.** `instructions/stub.md` says: runners and verbatim extraction on
  FAST; readers that judge on BALANCED; global block ≤ 2560 B still holds. Test: `test_instruction_budget.py`.
  Phase 2.
- **R33 C2 evidence without `bite`.** `verify --scope step --files <t> --expect fail` records
  `expected_fail: true`; the bugfix workflow text requires it before the fix. Test:
  `test_ai_task_state.py::test_expect_fail`. Phase 2.

- **R34 State file `current.json` → `state.json`** (OQ11, developer, 2026-10-25; split expand/contract by
  review H1 of T-2026-10-27-006, Q2=B, 2026-10-27). **Task 3.4b (expand):** `state.py`,
  `hooks/guard/{scope,paths}.py`, `context-guard.py`, `runtime-gate.py`, `status.py`, `sensors.py`, `adopt.py`
  and `update.py` read `state.json` first and `current.json` otherwise, and `state.py` writes the file where it
  is (a new task starts in `current.json`); the scope guard arms on either and the path guard denies agent
  writes to both. Nothing moves, so reverting 3.4b disarms no guard. Test:
  `test_ai_task_state.py::test_reads_legacy_state_name`; scope and path guard tests for each name; path-guard
  fixtures for a write to each name (denied). **Task 3.4c (contract), after a release ships 3.4b:** a migration
  moves the file in user projects and `state.py` starts new tasks in `state.json`. Test: a migration test with a
  task in flight. Outcome: "Three control files (`state.json`, `events.jsonl`, `task.md`)". Phase 3 steps 4b, 4c.
- **R35 Plugin name RiskRails** (developer, 2026-10-25). Display name `RiskRails`, machine name `riskrails`
  everywhere a name is an identifier (npm and plugin names are lowercase); the full map is **Names** in
  §Interfaces. For one version `update.py` and the renderer recognise the old markers and rewrite them on
  `/setup --update`, the installer moves the old install home and leaves a symlink, old env names are read
  when the new ones are unset. Test: `tests/test_rename.py` greps `hooks/ skills/ ai/ instructions/ agents/
  scripts/ profiles/ settings.common.json codex/` for `claude-agentic|claude_agentic|CLAUDE_AGENTIC` outside an
  allow-list of compat readers; `TestMigration0008` rewrites the markers in a fixture `CLAUDE.md` and leaves
  the user's text byte-identical; install suites assert the new home and the symlink. Outcome: "One install
  command for both runtimes" (published once, under its final name). Phase 3 step 4b, before 3.5.
- **R36 Guarded commands and decisions in the runtime's dialog** (developer, 2026-10-28; spec
  `docs/sdlc/specs/command-choice-dialog.md`, Q1–Q8 in `docs/sdlc/intent/command-choice-dialog.questions.md`).
  With `.ai/policies/dialog.json` `enabled:true`, a command the agent may not run itself (`approve`, `reject`,
  `git commit`/`git push`, `verify --by`, `review --by`, a lowering `start --mode`, `profile set`) and a plan or
  review decision are offered through the runtime's native dialog (`AskUserQuestion`; Codex `request_user_input`
  only on a version spike 7.0 verifies, else off), prepared solely by `state.py decision`, option text = the
  command verbatim, `multiSelect` only for command lists. A PostToolUse hook records the harness's `tool_response`
  into `.ai/state/consent.jsonl`; the git guard, the path guard and the `state.py` human route let that command
  through verbatim, once, within 120 s, same session, in order; anything else is `CONSENT_MISMATCH` and voids the
  picks. While a decision is open the PreToolUse gate (matcher `*`) denies every other tool and Stop blocks, at
  most twice per turn. Off (file missing, `enabled:false`, `AI_UNATTENDED`, a subagent, unverified Codex) is
  today's behaviour byte-for-byte; the scaffold and the migration both write on, the migration printing one line
  that says so (Q9, 2026-10-28). First consumer: plan drift,
  `state.py profile detect` (ported from `bin/riskrails.js`, a C3 refactor) at SessionStart, on `auth_success`
  and on an account-file mtime change; `profile set <plan>` same tier only, otherwise it prints the `npx riskrails`
  line. `askUserQuestionTimeout` is never rendered. C5 is amended by the human: "No agent merges or deploys; an
  agent commits, pushes or approves only by running, verbatim and once, a command a human picked in the
  runtime's dialog as recorded by the harness — otherwise a human runs it outside the agent." Test:
  `tests/test_dialog_gate.py`, `tests/test_dialog_consent.py::test_model_cannot_forge_consent`,
  `tests/test_profile_detect.py`, additive golden fixtures in `test_ai_git_guard.py` and `test_ai_path_guard.py`,
  `tests/test_guard_characterization.py` with an empty diff while the dialog is off, `tests/test_instruction_budget.py`.
  Outcome: "the human never leaves the session for a gate". Behaviour 2, full mode for every step. Phase 3
  step 7 (7.0 spike, 7a–7f), after 3.5.

## Design

**Components and responsibilities (one each).**

| Component | Responsibility | Public interface |
|---|---|---|
| `skills/{setup,spec,plan,build,review,ship,status}/SKILL.md` | the seven jobs, ≤ 300 lines each, steps only; policies are references | slash commands, §Interfaces |
| `skills/<old>/SKILL.md` ×10 | alias for one version | prints `deprecated → /<new>`, reads the new skill |
| `ai/using-riskrails.md` (≤ 60 lines) | replaces `ai/agents/manager.md` and the router prose: when which command, the three modes, the three nevers | read by `/build`, linked from `.ai/AGENTS.md` |
| `skills/ai-task/weight.py` (≤ 300 lines) | pure computation: axes from `weight.json` + declared files + session declarations; no state write | `compute(root, files, declared) -> Weight`; CLI via `state.py weight` |
| `skills/ai-task/state.py` | the only writer of `current.json`, `events.jsonl`, `task.md`, `handoff.md`; mode enforcement | 9 model-facing + 2 human + 3 internal subcommands |
| `skills/ai-task/sensors.py` (≈ 300 lines left) | tree snapshot/diff and the capped command runner | `snapshot_tree`, `diff_files`, `run` |
| `.ai/policies/weight.json` + generated `weight.md` | the one risk table | schema §Interfaces |
| `hooks/ai-guard.py` + `hooks/guard/{common,git,paths,scope,ere}.py` | one PreToolUse process, three checks | stdin JSON → stdout deny JSON / silence |
| `hooks/project-scaffold.py`, `skills/setup/scaffold_ai.py`, `skills/setup/setup.py` | scaffold (Setup hook + CLI), `.ai/` scaffold, survey/adopt-own/check | `setup.py survey|scaffold|adopt|check` |
| `skills/project-update/update.py` + `migrations/0007_weight_model.py` | schema migrations and foreign-tool adopt (unchanged engine) | `--check/--apply/--adopt` as today |
| `skills/status/status.py` | read-only ≤ 20-line status; `--cost` delegates | `status.py [--root] [--cost]` |
| `package.json`, `bin/riskrails.js` | install both runtimes; calls the Python scripts it ships | `npx riskrails [flags]` |
| `.claude-plugin/*`, `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json`, `hooks/hooks.json` | what the plugin format can carry: skills + hooks | `/plugin`, `/plugins` |
| `tests/test_*.py` + `tests/run-all.sh` (wrapper until the last `.sh` dies) | the specification | `python3 -I -m unittest discover tests` |

**Data flow.**

```
 /plan ──► state.py weight ──reads──► weight.json, declared files, git grep ──► 7 lines + mode
    │                                                                          │
    └──► state.py start --files --mode(auto) ──writes──► current.json, events.jsonl, task.md §Weight §Plan
 /build ─► edits (ai-guard.py: path+scope checks read current.json.files)
    │    ─► state.py verify --scope all ─► sensors.run(verify_command) ─► current.json.verify, task.md §Verify
    │                                   └► re-score reversibility/domain from tree diff (up only)
 /review ► ai-reviewer (BALANCED guarded / STRONG full) ─► state.py review --verdict --report - ─► task.md §Review
 /ship ──► state.py close ─► facts: verify green on tree? diff ⊆ files? ─► mode table ─► archive | gate
    │                                                                 human: state.py approve --by (outside)
 /status ► status.py ─reads─► current.json, events.jsonl, weight.json (never writes)
 context-guard.py ─PreCompact─► state.py handoff --reason precompact (one of the five writes)
 npx / plugin ─► ~/.claude|~/.codex: hooks/ai-guard.py, skills/, agents/ (rendered), ai/, profile.json, block
 /setup --update ─► update.py (migration 0007: risk-tiers.json → weight.json, tier → mode)
```

**Phasing and task order.** Each row is its own `/ai-task` under TODAY's rules until 2.2 lands and the human
has reworded `.ai/rules/*.md` and C6 to modes (a policy edit, outside a run). Tier reasoning follows
`hooks.md:6`, `skills.md:6`, C6. Precondition for everything: the four open tasks closed (intent :203-205).

| # | Task (one `/ai-task`) | Files it may touch | Tier today | Verification |
|---|---|---|---|---|
| 1.1 | `max_suite_runs` 5 → 2 in the shipped template; `tools/build-template-history.py` | `skills/ai-init/templates/.ai/policies/risk-tiers.json`, `risk-tiers.md`, history/ | T2 (data; the repo's own `.ai/policies/` copy is human-edited) | `test-project-update.sh`, `test-ai-task-state.sh` cap case |
| 1.2 | Size and paths stop gating: `over_budget` no longer blocks `skipped_green`; `path_scopes.min_tier` ignored (hint printed); `step-split` kept but not demanded | `state.py`, `sensors.py`, `skills/ai-task/SKILL.md`, template `risk-tiers.json`+md, history/ | **T4** (weakens a refusal, changes when approval is requested) — one STRONG review, `review_rounds_max` 2 | `test-ai-task-state.sh`, `test-ai-task-sensors.sh`, e2e |
| 1.3 | Delete shims, seven stale agents + Codex twins, `.bak` → `backups/2026-10-25/`; `settings.common.json` fable entries | `hooks/fable-gate.py`, `hooks/codex-model-gate.py`, `agents/`, `codex/`, `install.sh` enumerations, `tests/test-fable-gate.sh`, `test-codex-model-gate.sh`, `run-all.sh` | **T4** (install change by `skills.md:6`; by C6 it moves no decision — the bootstrap price) | install suites, `test-runtime-gate.sh` |
| 1.4 | `/status` as a script + alias skill `ai-status` → `status` | `skills/status/`, `skills/ai-status/SKILL.md`, `tests/test-ai-status-root.sh` | T2 | `test-ai-status-root.sh` |
| 2.1 | `weight.json` schema + `weight.py` + `state.py weight` (read-only) + mirror + `docs/weight.md` | `skills/ai-task/weight.py`, `state.py` (one subcommand), template `weight.json`, `docs/`, `tests/test-ai-task-state.sh` | T3 (adds a check that decides nothing yet) | `test_weight` cases SQ1 |
| 2.2 | New state surface: `start/verify/review/close/status/ask/answer`, modes enforced, two facts, handoff at boundaries, `task.md`, remove 19 subcommands, `sensors.py` cut, migration 0007 | `state.py`, `sensors.py`, `migrations/0007_*.py`, fixtures `schema-v6/`, `tests/test-ai-task-state.sh`, `test-ai-task-sensors.sh`, `test-project-update.sh`, `test-end-to-end.sh`, `usage-report.py` | **T4** (approval path and migration) — the last task under the old rules | all four suites + e2e both runtimes |
| 2.H | Human, outside a run: reword `.ai/rules/hooks.md`, `skills.md`, C6, `CLAUDE.md` to modes; `safety.md` blocker sentence; repo `.ai/policies/weight.json` via `/setup --update` | policy files | — | `/status` shows schema 7 |
| 2.3 | Skills text: seven SKILL.md, nine remaining aliases, `using-riskrails.md`, `workflows.md` merged, `review-economy.md`/`tooling.md`/`context-management.md` out of the per-task list, `stub.md` BALANCED readers, `.ai/AGENTS.md` template rows, history/ | `skills/*/SKILL.md`, `ai/`, `instructions/`, templates | light/guarded (text) | `test_skills_surface`, `test_instruction_budget`, model-free grep |
| 2.4 | Agents 14 → 6 (+ security focus brief), Codex render without twins, `runtime-gate.py` budgets removed, `profiles/*` keys | `agents/`, `ai/agents/`, `scripts/render-codex-agents.py`, `hooks/runtime-gate.py`, `profiles/` | guarded (W≈4: scope 2, behaviour 1, novelty 1) | `test_codex_agent_render`, `test_runtime_gate`, `test_profiles` |
| 2.5 | `/setup`: `setup.py survey|check`, adopt-own rows in `adopt-map.json`, `toolbox.md`, superpowers report line | `skills/setup/`, `skills/project-update/adopt-map.json`, fixtures | guarded (reversibility 1: writes `testing.md` Verification line with confirmation; `update.py` untouched) | `test_setup`, `test-project-adopt` |
| 3.1 | Port: `hooks/guard/*.py` + `hooks/ai-guard.py`; `.sh` guards → exec shims; timed cases | `hooks/`, `tests/test-guard-characterization.sh` (+timed), `tests/test_guard_characterization.py`, `test_ere_unit.py`, `test_guard_differential.py`, frozen shell copies under `tests/fixtures/guard-port/` | guarded (scope 2, novelty 1; golden identical → no decision moves) | golden byte-identical, timed, differential |
| 3.2 | Port `project-scaffold.sh`, `scaffold-ai.sh` → Python; shims keep the Setup entry | `hooks/project-scaffold.py`, `skills/setup/scaffold_ai.py`, `tests/test-scaffold-idempotency.sh` + `.py` | light/guarded (W 2–3) | both scaffold suites green on the same tree |
| 3.3 | Suites: one `.sh` → one `.py` per step (28 steps), `run-all.sh` wrapper runs `unittest discover` + the surviving `.sh`; last step deletes `lib.sh` | `tests/**`, `.github/workflows/test.yml` | light (tests only; coverage 0) | `test_suite_parity` per step; `run-all.sh` green after each |
| 3.H | Human: `testing.md` Verification → `python3 -I -m unittest discover tests`, `e2e_command: python3 -I -m unittest tests.test_end_to_end`, `single_test`; `.ai/policies/testing.md:121-158` project specifics | policy file | — | `/status` |
| 3.4 | Path-guard rule rewrite (R22); new fixtures; golden re-recorded | `hooks/guard/paths.py`, `hooks/ai-path-guard-defaults.json`, `tests/fixtures/path-guard/`, golden, `known-risks.md` | **full** (behaviour 2, domain 2 — secrets/identity rules, allows what was denied) | ported suites + new fixtures; one STRONG review |
| 3.4b | Renames, a refactoring task of its own (C3): `current.json` → `state.json` (R34) and claude-agentic → RiskRails / `riskrails` (R35); migration `0008_renames.py`; golden re-recorded only for path and name strings — every deny decision identical | `skills/ai-task/state.py`, `hooks/guard/*`, `hooks/*.py`, `hooks/ai-path-guard-defaults.json`, `skills/status/`, `skills/project-update/` (+ `migrations/0008_renames.py`, renderer), `instructions/`, `ai/`, `agents/`, `scripts/`, `profiles/`, `install.sh`, `settings.common.json`, `codex/`, `tests/**`, `README.md`, `docs/` (not `docs/sdlc/`) | **full** (reversibility 2 via the migrations hint: rewrites managed blocks and moves the state file in user projects) | all suites; a scripted check that every changed golden line contains an old name or path and its decision is unchanged; install suites for the new home and the symlink |
| 3.5 | `npx riskrails` + manifests + entries switched to `.py` + shims deleted + `install.sh` wrapper + `test_install_routes` + git-guard `npm publish` deny (separate step, golden additive) | `package.json`, `bin/`, `.claude-plugin/`, `.codex-plugin/`, `.agents/`, `hooks/hooks.json`, `settings.common.json`, `codex/hooks.json`, `install.sh`, five install suites, README install section | **full** (behaviour 2, novelty 2, reversibility 1, scope 2 = 7 + install hint → 8) | five suites + routes suite; on-screen Codex `/hooks` trust line |
| 3.6 | Cleanup: `.ai/reports/` git-ignored here, docs/README rewritten to link `weight.md`, FAQ entry removed, `docs/hook-performance.md` numbers | `.gitignore`, `docs/`, `README.md` | light | `test_shared_prompts_model_free`, link check |

Bootstrap note: 1.2, 1.3 and 2.2 are T4 under today's rules because `skills.md:6` names install and
approval literally; C6 would place 1.3 at T2. Running them as T4 with `review_rounds_max` 2 (already
shipped) bounds the cost to one STRONG review each. The spec should say so rather than argue the tier.

**Alternatives rejected.**

Weight model. (a) Seven questions with asymmetric points (first analysis §3.2: 0/2, 0–2, 0/1/3, 0/4, 0/2/4,
0–2, 0/1; light ≤ 2, guarded 3–6, full ≥ 7 or Q4 = 4 or Q3 = 3 or Q5 = 4) — rejected: four hard triggers
and a 4-point domain reproduce "any path near auth is full" (the font case scores 4 → full when Q4 fires on
the path floor it keeps); it also needs `path_scopes` floors, which both analyses then remove. (b) Keep
seven tiers and only fix the examples (the diet's §1) — rejected: the intent's own evidence (9 of 23 T4
with one trigger sentence; T4 in 13/19 and 6/6 elsewhere) shows the table is read, not computed; no number
of examples makes a model compute. (c) Six axes exactly as the second analysis (light ≤ 3) — adjusted, not
rejected: at ≤ 3 the guard regex fix (scope 2 + behaviour 1) and an ArgoCD dev manifest (reversibility 1 +
scope 1 + behaviour 1) land in light, which contradicts the analysis' own target of `plan` for both; light
≤ 2 fixes both without moving any other case (SQ1 table).

Command surface. (a) Nine + `/task` (second analysis §6.1) — rejected: `/test` is a `state.py verify` call
with no human judgement, `/cost` is `status --cost`, and `/task` duplicates `/build`'s router; each extra
skill costs a description in every session's context. (b) Six exactly (intent) — rejected: `/ship` carries
the only human gate in full mode and the release summary; folding it into `/build` hides the stop. (c) Keep
`ai-task` as the name — rejected: the family prefix is the problem statement; `/ai-task` stays as an alias.

Port strategy. (a) Port guard by guard, three Python processes — rejected: three JSON parses and three
policy loads per Bash call stay; the intent decided one process. (b) Rewrite rules and port at once —
rejected by C3 and by the intent's constraint (:131-134): a golden change is then unattributable. (c)
Replace the golden with a differential against bash — rejected as the only proof: bash stays installed for
one task only; the golden is the durable spec. Kept as a second layer during 3.1 (frozen shell copies).

Installer / plugin split. (a) Plugin format only — rejected: agents need the plan's model names
(`{{STRONG_MODEL}}` placeholders, `agents/ai-reviewer.md.tmpl:6-7`), `profile.json`, the managed block,
`config.toml` and `settings.json` merges have no plugin equivalent; `plugin.json` carries `skills` and
`hooks` only (superpowers and jev-sentinel manifests read here). (b) Python installer (`python3 -m
claude_agentic`) — rejected by the intent (out of scope: `npx` starts Node). (c) Keep `install.sh` beside
`npx` — rejected: two installers that must leave one tree is the drift the suite exists to prevent;
`install.sh` only prints the `npx` line.

### Decisions on the intent's open questions

**SQ1 (blocking) — the weight table, and how blast radius is measured.** Six axes 0–2 as in the second
analysis §6.2, with ONE change: `light ≤ 2` (not ≤ 3). Blast radius (scope) is **measured by `weight.py`**
from the declared files (reference count of each file's identifier across the repo, `git grep -lwI`, bands
0 / 1–5 / > 5, plus `hot_paths`), **never declared alone**: a declared value may only raise it. Why not grep
over changed symbols: at `/plan` time there is no diff, so "changed symbols" do not exist yet; the
file-identifier count is the only deterministic pre-diff proxy, and the re-score at `verify`/`close` over
the real diff raises reversibility and domain (the two hard axes) — scope is not re-scored because a raise
there would only move light → guarded after the work is done, which is the behaviour the intent removes.
Why not declared-with-evidence alone: first analysis risk 1 (an optimistic model); evidence: 10 of 18 tier
raises were about size, none about a wrong declaration, but zero deterministic axes would make the table a
prose table again (C1 of the problem statement). Constitution: C4 (the declared files are the plan), C2
(coverage 2 → characterization first). Validation (scope/behaviour/reversibility/domain/novelty/coverage):

| Case | Axes | W | Mode | Target | OK |
|---|---|---|---|---|---|
| font in `login.html.twig` (new-shop 09-23-009; was T3→T4) | 0/0/0/0+1 hint/0/0 (template, coverage n/a) | 1 | light | quick | yes |
| Odoo VAT module, 401 lines (oddo 10-09-002; was T4→T5) | 2/1/0/2 (`account.*`)/1/1 | 7, domain=2 | full | full | yes |
| enum fixture `Migrations/Data/` (oroCRM 09-30-002; was T4→T5×3) | 1/1/0+1 needs_step/1/0/1 | 5 | guarded | plan | yes; no repeated raises (no DML content) |
| 1 733-line generated DDL in a test fixture (oroCRM 09-30-001; was T2→T5) | 0/0/0/0/0/0 (tests only) | 0 | light | quick | yes |
| regex fix `ai-path-guard.sh` (T-2026-10-21-001; was T4, 21 h, 6 questions) | 2/1/0/0/0/0 | 3 | guarded | plan (W≈4 there) | yes |
| migration 0006 deleting user `.ai/` files (agentic 10-13-004; T6) | 2/2/2/0/1/1 | 8, rev=2 | full; `irreversible_content` `delete(` (this repo's list) → full_irreversible | full+irreversible | yes |
| ArgoCD manifest `env/dev` (T6 by `k8s/**`) | 1/1/1 needs_step/0/0/0 | 3 | guarded | plan | yes |
| ArgoCD `env/prod` + secret | 1/1/2 irreversible/2 (`**/secret*` module)/0/0 | 6, both hard | full_irreversible | full | yes |
| project `CLAUDE.md` (oddo, oroCRM; was T2→T3) | 0–1/0/0/0/0/0 +1 behaviour hint | 1–2 | light | quick | yes |
| productEditorApp feature (new screen, field, additive migration; INFERENCE from intent :307) | 1/1/1/1/1/1 | 6 | guarded | guarded, not full | yes; worst realistic 1/2/1/1/2/2 = 9 → full, which C2 justifies |
| Learning Workbench feature (Python, tests exist; intent :309) | 1/1/0/0/1/1 | 4 | guarded | guarded | yes |
| three lines in `Payment/` (first analysis §3.2) | -/-/-/2/-/- | — | full | full | yes |
| test-only or message-text change | 0/0/0/0/0/0 | 0 | light | light | yes |

Adjustment made: at `light ≤ 3` the regex fix and the ArgoCD dev manifest would be light; at `≤ 2` every
case lands as both analyses intend and no other case moves. Phase-3 self-check under the table: 3.1 port
W 3 guarded; 3.4 rewrite behaviour 2 + domain 2 → full; 3.5 installer W 8 → full; migration 0007
reversibility 1 + migrations hint → 2 → full. These are the tasks that deserve full.

**SQ2 — `ai-security`.** Becomes a `focus: security` brief of `ai-reviewer` in full mode when domain = 2
(identity, personal data, money); the checklist moves from `ai/agents/security.md` into
`ai/agents/reviewer.md` §Security. Evidence: 19 security reports in 65 tasks, all at T5+, same STRONG model
and the same inputs as the adversarial review; one agent fewer to render on Codex. Otherwise: keep the
template, 7 agents.

**SQ3 — `ai-implementer`.** Removed: no journaled use in 23 tasks, the global rule says the session
implements, and full mode under superpowers variant B uses `subagent-driven-development`'s implementer. If
the developer keeps it (pattern-copy on request), it is the seventh template; nothing else changes.

**SQ4 — `/build` or `/task`.** Developer decides; recommended `/build` (job-named, matches addy; `/task`
collides with the runtime's Task/Agent vocabulary and with `<task-id>`). `/ai-task` stays an alias either
way; choosing `/task` renames one directory and the alias target.

**SQ5 — `/setup --adopt` for a project's own toolbox.** Inventory, not copies: `setup.py survey` lists
`.claude/{skills,rules,agents,hooks}`, `.codex/*`, `bin/*.sh`, Makefile targets; writes
`.ai/policies/toolbox.md` (one line per item: path, purpose from its first comment/frontmatter, KNOWN FACT
label) and appends router rows to `.ai/AGENTS.md` (`| <job> | \`/<skill>\` |`). Hooks: a project hook with
the same job as a plugin guard is kept and noted (the plugin's is not installed into the project); a missing
guard is reported. `verify_command`: proposed from `composer.json`/`Makefile`/`package.json` scripts
(`sensors.py detect` logic moves here) and written into `testing.md` only after the human confirms in chat
(`/setup` runs outside a task, so the file is not frozen). `.ai/project/` is created only with `--knowledge-base`.
Constitution: C1 (the toolbox is production behaviour).

**SQ6 — alias layer.** Skill-frontmatter stubs (`skills/<old>/SKILL.md`, ≤ 12 lines, description ≤ 80 B),
not `update.py`: Codex has no first-use hook, both runtimes read SKILL.md, and the stub costs ~80 B of
context per old name. Migration 0007 only rewrites router rows and blocks in project files. Removed in the
version after.

**SQ7 — phase 1 scope.** Merged `workflows.md` and the prose diet ship WITH the weight model (task 2.3),
not in phase 1: the prose names modes. Phase 1 is numbers, deletions, `/status`, one alias.

**SQ8 — six or nine commands.** Developer decides; recommended seven (`/setup /spec /plan /build /review
/ship /status`), with `/test` → `state.py verify` (no human judgement, so no skill) and `/cost` →
`/status --cost`; no `/task` because `/build` routes. Choosing nine adds two ≤ 30-line skills and two
descriptions to every session.

**SQ9 — mode names.** Developer decides; recommended light / guarded / full: `plan` collides with the
`/plan` command, plan mode and the old `state.py plan`; `quick` collides with the old `state.py quick` in
every journal. Choosing quick / plan / full changes strings in `weight.json`, the stub, skills and docs only.

**SQ10 — weight table.** Six axes (SQ1), threshold adjusted.

**SQ11 — path floors.** Demoted: `path_scopes` floors go; the deterministic part survives as
`domain.modules` (axis 2 — money, identity, personal data, by project list) and `reversibility.irreversible`
(prod/infra), both hard axes that force full; everything else is a one-point hint, once per axis. Confirmed
by the cases: the font (hint, not floor) is light, `Payment/` is still full.

**SQ12 — superpowers.** Developer decides; recommended **B** (delegate when present, one fallback line per
command, `/setup` reports presence and prints — never writes — the `enabledPlugins` line). Reasons: A writes
into the user-owned `.claude/settings.json` (safety.md: config is edited by humans) and absorbing two skills
is a copy to maintain; the intent's mapping table (:390-407) already names the delegation per command.
Combined SessionStart cost today: `using-superpowers` 3.6 KB + global block ≤ 2.5 KB + project block ≤ 2 KB
+ handoff ≤ 30 lines (~1.5 KB, only with a task in flight) ≈ 9.6 KB worst case (~2.4k tokens), measured by
R28's test with a 10 KB ceiling. Choosing A: `/build` gains two sections (≈ 80 lines) and `/setup` writes the
line after a chat confirmation.

**SQ13 — path-guard rewrite: `sh -c`/`eval` segmentation.** Drop the recursive re-parse of `sh -c`/`eval`
strings; keep top-level splitting on `; && || |` and newlines so the `approve`/`set --by`/`--confirm-delete`
and control-file rules stay line-scoped; a command > 4 KB is denied with one sentence. The bypass
`bash -c "state.py approve …"` is accepted in `known-risks.md` under the threat model (safety.md:46-50:
agent mistakes, not constructed commands). T-2026-10-22-002's fixes are the interim on the shell engine and
are carried into the Python port byte-identical (3.1), then simplified in 3.4.

**SQ14 — plugin format vs `npx`.** The plugin format carries skills and hooks (manifests read: superpowers
`plugin.json` has none of agents/settings; `.codex-plugin/plugin.json` supports `skills` and `hooks` paths).
It cannot express the managed block, `profile.json`, the `ai/` shared tree, agents rendered per plan, or the
`settings.json`/`config.toml` merges — `npx` does those. Plugin-only is a supported degraded mode for light
and guarded (guards + skills + `state.py`); full mode stops with the `npx` line. npm name availability:
unverifiable offline — **left open**; fallback `@<owner>/riskrails`. Migrations run from `/setup --update`
in each project, never from `npx` (it does not know the projects).

**SQ15 — T0–T6 labels.** Developer decides; recommended: three mode words everywhere, a `tier_set` compat
event with the T-label for one version (R18), no T-label in `task.md` or `/status`.

**SQ16 — team profile and abrites-staging-v2.** Developer decides; recommended: team profile stays
documented and installable, its install-suite cases move behind `AI_TEST_SLOW=1`; abrites-staging-v2's six
guards are inventoried by `/setup --adopt` (toolbox rows, no copies) and the `ai-tools` branch is abandoned
after the inventory is committed by the human.

**SQ17 — `SCOPE_CHANGE_REQUIRED` in place.** `start --amend` (R25); the scope guard re-reads
`current.json.files` on the next call; nine amendments in eight tasks is the normal case.

### Risks

| # | Risk | L | I | Mitigation | Test that catches it |
|---|---|---|---|---|---|
| 1 | Session under-declares behaviour/novelty/domain (first analysis risk 1) | high | med | measured values win over declarations; UNKNOWN = 1; hints raise; re-score up at verify/close; the review brief lists refuted hints as its first check | `test_weight::test_declaration_below_measurement_is_replaced`; e2e fixture with a DML hunk added after `start` → `weight_raised` |
| 2 | Coverage = 2 on untested legacy apps pushes every feature +2 → more full than intended | med | med | guarded band is 3–7 (five points wide); coverage counts only `code_globs` files; `/setup` proposes `coverage.map` | productEditorApp-like fixture in `test_weight` scores guarded |
| 3 | Port passes the golden but a suite case (not in the golden) changes meaning | med | high | both suites run on the same tree until the twin is green; frozen shell copies + differential during 3.1 | `test_suite_parity`, `test_guard_differential` |
| 4 | Python start-up eats the latency budget (interpreter ≈ 15–20 ms) | med | med | `python3 -I -S`, lazy regex compile, `subprocess` only when git is asked, one process instead of three | `TestTimed` 1 KB and 20 KB cases, median of 5 |
| 5 | One process registered under three matchers runs three times | med | low | exactly one PreToolUse entry with the union matcher; dispatch inside | install suites count `ai-guard.py` entries == 1 per runtime |
| 6 | Codex `trusted_hash` invalidated by a changed hook command → guards silently skipped | med | high | shims first (3.1), entries switched only in 3.5 with the on-screen `/hooks` trust line in the installer output | `test_codex_install` asserts the trust message; manual `/hooks` check at 3.5 |
| 7 | `npm` name `riskrails` taken, or "RiskRails" already used by another product | med | low | scoped fallback; `package.json.name` decided before 3.5 | none automatic — manual `npm view` by the human |
| 8 | Plugin cache + `npx` both install hooks → double execution | med | med | `npx` detects the cache and skips skills/hooks; routes suite | `test_install_routes::test_no_duplicate_hook_command` |
| 9 | Migration 0007 meets a task in flight with `tier` | med | med | `patch_state` maps tier → mode and marks weight UNKNOWN; `state.py` fills defaults in memory for unmigrated states (WP2 pattern) | `TestMigration0007::test_in_flight_state` on `schema-v6/` |
| 10 | 17 skill descriptions per session during the alias version | high | low | alias descriptions ≤ 80 B; new ones ≤ 1024 B | `test_skills_surface` byte caps |
| 11 | `/plan`, `/review` collide with a built-in or another plugin's command | med | low | document `riskrails:<name>` namespaced invocation; `/setup` prints collisions it detects in `~/.claude/plugins` | manual at the start of 2.3 |
| 12 | Old journals/`usage-report` break on the rename | low | med | compat `tier_set` for one version; reader accepts both | `test_usage_report` with v6 and v7 fixtures |
| 13 | Human edits (rules, C6, `testing.md`, `safety.md`) block the plan mid-way | high | low | 2.H and 3.H are explicit plan rows with the exact text; tasks before them do not depend on the new wording | `/status` shows schema 7 and the new `verify_command` |
| 14 | Superpowers' "MUST invoke" banner pulls the session into a foreign process in full mode | med | med | variant B maps each command to one superpowers skill; `review_rounds_max` 2 overrides theirs; measured SessionStart cost | `test_session_start_cost` ≤ 10 KB |
| 15 | Losing `bite` loses "the test reaches the change" | low | med | `verify --expect fail` for bugfix (C2); coverage axis | `test_expect_fail`; e2e bugfix path |
| 16 | 1.2/1.3/2.2 run as T4 under the old rules and cost three STRONG reviews again | med | med | `review_rounds_max` 2 already shipped; one bundled task each; plan reviewed in plan mode by the human | journal of each task: `review_verdict` count ≤ 2 |
| 17 | The guarded re-score to full after the work is done surprises the developer | low | low | re-score touches only reversibility/domain; `weight_raised` prints the diff hunk that caused it | e2e fixture with a late `DROP` |
| 18 | `git grep -lwI` on a huge monorepo is slow at `/plan` | low | low | cap at 10 declared files, `--max-count`, 5 s budget → UNKNOWN (=1) | `test_weight::test_grep_budget` |

## Interfaces

**Commands.**

```
/setup [--update] [--adopt [--tool LIST]] [--light]      survey + scaffold | migrate (update.py) | adopt foreign or own toolbox
                                                         ends with setup.py check: VERIFY_COMMAND_MISSING → exit 1, says so
/spec <idea | intent path>                               one file docs/sdlc/specs/<slug>.md (intent + spec); questions via ask --topic
/plan <request | spec path> [--files a,b]                weight (7 lines) → mode → plan shaped by mode → state.py start
/build [<request>] [--mode light|guarded|full] [--by X]  no task → /plan first; edits under the scope guard; verify; review per mode
/review [--focus security] [--scoped]                    one pass at the mode's tier → state.py review; max review_rounds_max
/ship                                                    task.md §Changes + §Verdict; full: gate (approve outside); close; suggests /clear
/status [--cost [--task ID]]                             status.py; --cost delegates to usage-report.py
aliases (one version): /ai-init /ai-audit → /setup; /project-init /project-update → /setup [--update];
  /sdlc-intent /sdlc-spec → /spec; /sdlc-plan → /plan; /ai-task → /build; /ai-status → /status; /usage-report → /status --cost
```

**`state.py` subcommands** (`--root` as today; exit codes shared: 0 ok · 2 review required · 4 QUESTIONS_PENDING
· 5 refused (no human / rejected / pending handoff) · 6 budget or scope (`SUITE_BUDGET`, `REVIEW_BUDGET`,
`SCOPE_CHANGE_REQUIRED`, first line token) · 7 RUNTIME_HANDOFF_PENDING).

```
model-facing (9)
 weight   --files "a,b" [--goal …] [--declare behaviour=1:"why"]… [--json|--long|--mirror]     read-only; exit 0
 start    --goal … --workflow feature|bugfix|refactoring|hotfix|investigation --files "a,b"
          [--tests "t"] [--mode M --by WHO] [--plan-file PATH | --steps "id:files:tests;…"] [--task-id] 
          --amend --files "+c" --why "…"                                                      creates task; mode = weight unless --mode
 step-done <id>                                                                               guarded/full multi-step only
 verify   --scope step|suite|e2e|all [--files …] [--expect fail] [--e2e not-applicable "why"] [--after-fix "what"] [--by WHO]
                                                                                              runs, records, re-scores up; exit 0/1; 6 SUITE_BUDGET
 review   --verdict pass|pass_with_findings|blockers_open --tier BALANCED|STRONG [--focus security] --report -   (stdin FINDINGS block)
          --closes "H1,M2"                                                                    appends task.md §Review; 6 REVIEW_BUDGET
 close    [--abandon]                                      finishes open steps, two facts, mode table, gate or archive; 2/4/5/6
 status   [--json]                                         what status.py prints (status.py shells to it)
 ask      [question] [--option …] [--recommend …] [--gate] [--topic SLUG]
 answer   [Q1=A …] [--prose …] [--topic SLUG]
 decision show [--id D] [--json] | open --kind commit --command C… | settle --id D [--pick N] | fallback --id D --why …
                                                           R36 (phase 3 step 7); --pick is terminal/unattended only
human-only (3, terminal, AI_UNATTENDED=1, or a dialog pick under R36; path guard denies the literal invocation from an agent)
 approve  --by WHO [--confirm "<operation>"] [--note]      --confirm required for full+irreversible; never via the dialog
 reject   --by WHO --why …
 profile set <plan> [--runtime R]                           R36; same tier only, else 6 PROFILE_NEEDS_INSTALLER
internal (5, called by hooks/skills, undocumented in SKILL.md)
 handoff  [--print] [--reason stage|precompact|manual|session-start] [--to RT] [--for continue|review]
 event    TYPE [--detail] [--data JSON]                     hooks only
 profile  [--field] [--tier] [--json]
 profile detect [--runtime R] [--json] [--open]             R36; context-guard at SessionStart / auth_success
 consent  [--json] | audit [--json]                         R36; the consent.jsonl ledger, read-only
removed (19): init get stage risk triage quick plan remediate step review-gate test-run step-split set risks modules
              questions note events done archive   (remediate → verify --after-fix; set → review/approve; done+archive → close)
```

**`weight.json`** (shipped at `skills/ai-init/templates/.ai/policies/weight.json`; ≤ 80 lines; prose in `docs/weight.md`).

```
{ "version": 1,
  "axes": {
    "scope":         {"measure": "references", "bands": [0, 5], "hot_paths": ["hooks/**", "src/Shared/**"]},
    "behaviour":     {"measure": "session", "keywords": ["workflow","transition","state machine","messenger","queue","async","transaction"]},
    "reversibility": {"measure": "paths+content", "needs_step": ["**/migrations/**","**/Migrations/**","config/**","k8s/**","**/env/**"],
                      "irreversible": ["**/prod/**","**/production/**","deploy/**","**/*.deploy.*"],
                      "irreversible_content": ["DROP ", "TRUNCATE", "DELETE FROM", "ALTER .* DROP", "RENAME"]},
    "domain":        {"measure": "modules+session", "modules": ["**/Payment/**","**/Tax/**","**/Invoice/**","**/Security/**","**/account/**"],
                      "customer_visible": ["templates/**","**/Shop/**","**/Resources/views/**"]},
    "novelty":       {"measure": "session", "manifests": ["composer.json","requirements*.txt","package.json","pyproject.toml","Gemfile"]},
    "coverage":      {"measure": "tests-map", "code_globs": ["**/*.php","**/*.py","**/*.js","**/*.ts","**/*.sh"],
                      "test_globs": ["tests/**","spec/**","**/*Test.php","**/*.test.*","**/*.spec.*","**/test_*.py"], "map": {}}
  },
  "hints": [ {"paths": ["**/login*","**/Security/**","**/*Auth*"], "axis": "domain", "note": "auth-shaped path"},
             {"paths": ["skills/project-update/migrations/**"], "axis": "reversibility", "note": "touches user trees"},
             {"paths": [".ai/policies/**",".claude/**",".codex/**","CLAUDE.md","AGENTS.md"], "axis": "behaviour", "note": "pipeline"},
             {"paths": ["composer.json","package.json","requirements*.txt"], "axis": "novelty", "note": "dependency manifest"} ],
  "modes": {
    "light":   {"max_w": 2, "plan": "inline", "review": "on_red_fact", "reviewer": "BALANCED", "human_stops": 0, "suite": "verify", "e2e": false},
    "guarded": {"max_w": 7, "plan": "plan_mode", "review": "one", "reviewer": "BALANCED", "human_stops": 1, "suite": "verify+e2e", "e2e": true},
    "full":    {"min_w": 8, "hard_axes": ["reversibility","domain"], "plan": "written", "review": "one",
                "reviewer": "STRONG", "security_focus_when": "domain=2", "human_stops": 2, "suite": "verify+e2e", "e2e": true},
    "full_irreversible": {"when": "reversibility=2 and domain=2, or irreversible_content", "human_stops": 3, "confirm_names_operation": true}
  },
  "rules": {"unknown_scores": 1, "hint_raises_by": 1, "hint_raises_once_per_axis": true, "rescore_axes": ["reversibility","domain"],
            "rescore_direction": "up", "lower_by": "human", "steps_advice_over": 8},
  "review_rounds_max": 2, "remediation_rounds": 2,
  "tests": {"max_suite_runs": 2, "timeout_seconds": 1800, "env_retries": 1, "log_max_bytes": 2097152},
  "examples": {"light": ["…"], "guarded": ["…"], "full": ["…"]} }
```

Axis table (points 0 / 1 / 2 and the measurement rule `weight.py` applies; the session may only RAISE a
measured value, with one evidence line; a declared value below the measurement is replaced by it):

| Axis | 0 | 1 | 2 | Measurement |
|---|---|---|---|---|
| scope | no references, leaf template | referenced from 1–5 files | > 5 files, or a `hot_paths` match | for each declared file, `ident` = basename without extension (templates/config: repo-relative path); count files containing `ident` as a whole word (`git grep -lwI`, Python walk fallback), excluding the file itself and `test_globs`; max over files; bands `[0,5]` |
| behaviour | adds or presents | changes the output of an existing path, limited | changes a process: state machine, async, ordering, transaction | session declares; `weight.py` hint: every declared file new → 0; a `keywords` match in the goal or in an existing declared file → ≥ 1 |
| reversibility | `git revert` returns everything | a step is needed (cache, config, deploy, sync) | data/schema/infra/external write | `needs_step` glob → 1; `irreversible` glob → 2; at re-score, a diff hunk in a `needs_step` file matching `irreversible_content` → 2 |
| domain | none | customer-visible, no money | money, tax, fiscal, identity/auth, personal data | `modules` match → 2; `customer_visible` match → 1; else session declares with evidence; a `hints[axis=domain]` match adds 1 |
| novelty | the pattern exists in the repo | adaptation | new mechanism, dependency or framework feature | session declares; a `manifests` file among the declared files → ≥ 1 (+1 hint → 2 when the manifest diff adds a package at re-score) |
| coverage | tests cover and bite | partial | none → characterization first (C2) | over declared files matching `code_globs`: a test file whose name contains `ident` or a `map` entry exists → covered; all → 0, some → 1, none → 2; no code file declared → 0 |

`W = Σ axes`; `light ≤ 2`, `guarded 3–7`, `full ≥ 8 or reversibility = 2 or domain = 2`;
`full_irreversible` as above. UNKNOWN → 1 and listed. `--mode` overrides, journaled with `--by`.

**`weight` output — ≤ 7 lines, chosen over ≤ 20.** Six axes plus one verdict fit the intent's bullet
literally, read without scrolling in a chat, and the verdict line carries the thresholds so no policy
needs opening; `--long` (≤ 20) adds the evidence lists, `--json` the machine form. Worked example
(T-2026-10-21-001):

```
scope          2  hooks/ai-path-guard.sh referenced from 71 files; hot_paths hooks/**
behaviour      1  changes an existing path, limited — regex running time; golden byte-identical (declared)
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data (declared)
novelty        0  SH_RE family exists; no new dependency
coverage       0  tests/test-guard-characterization.sh names hooks/ai-path-guard.sh; timed case added
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

**State (`.ai/state/state.json` from task 3.4b, `current.json` before it — OQ11 decided yes, R34).**

```
{ "schema": 7, "task_id", "goal", "workflow", "mode": "light|guarded|full|full_irreversible",
  "weight": {"w": 3, "axes": {"scope": 2, …}, "hints": [], "unknown": [], "evidence": {axis: "…"}, "tree": "<sha>", "computed_at"},
  "mode_override": {"from", "to", "by", "why", "ts"} | null,
  "stage": "plan|build|verify|review|ship|done", "files": ["…"], "tests": ["…"],
  "steps": [{"id", "files", "tests", "status", "tree_before", "tree_after"}],
  "diff": {"base_tree"}, "verify": {"status", "suite_runs": 1, "runs": [{"n","scope","exit","tree","log","ts","expected_fail"}]},
  "review": {"status": "not_started|passed_with_findings|blockers_open|passed|not_required", "passes": 1, "tier", "findings": ["H1",…]},
  "gate": {"requested_at", "approved_by", "via", "confirm"} | null, "questions_pending": 0,
  "owner_runtime", "handoff": {"pending_to"}, "created", "updated" }
```

**`events.jsonl`**: WP2 keys unchanged (`ts task event actor runtime stage detail data`). New types:
`weight_set {w, mode, axes, hints, unknown}`, `weight_raised {axis, from, to, mode_from, mode_to, evidence}`,
`mode_set {from, to, by}`, `verify_run {n, scope, exit, tree, log, expected_fail}`, `review_verdict {verdict,
tier, pass_n, labels}`, `scope_change {added, why}` (existing). Compat for one version: `tier_set {tier:
"T2|T4|T5|T6", mode, w}` with light → T2, guarded → T4, full → T5, full_irreversible → T6 (the diet's
"T4 = one STRONG review" row is where guarded's cost sits for the old budget tables); `usage-report.py:665`
reads `data.mode or data.tier`, prints `mode <m> (tier <T>)`. Removed types: `stage_started`, `plan_registered`
(replaced by `weight_set`), `field_set` (no `set`), `gate_*` kept.

**`task.md`** (`.ai/reports/<task-id>/task.md`, written by `state.py` only, appended per event):

```
# <task-id> — <goal>                      workflow · mode · started · runtime
## Weight                                 the 7 lines verbatim; override line; re-score lines appended
## Plan                                   steps: id · files · tests; "amended <ts>: +file — why" lines
## Questions                              phase 3 (phase 2: link to questions.md); Q<n>/G<n>, options, [Answer]: line (human edits)
## Verify                                 | n | scope | exit | tree | log | expected_fail |
## Review                                 per pass: tier, verdict, FINDINGS block ([HIGH] H1 … in_scope: yes|no)
## Changes                                | File | Change | New/Edit/Delete |  (from tree diff at close; +N −M lines, F files)
## Verdict                                close result · gate requested/approved by/at · confirm text · handoffs · suite runs
```

**`hooks/ai-guard.py`** — entry registered once per runtime; dispatches on `tool_name`:

```
hooks/ai-guard.py            main(): read stdin → payload (UTF-8, errors=replace); AI_TOOL normalised (apply_patch → Edit,
                             shell → Bash); runs git.check (Bash), paths.check (all), scope.check (Edit-like) in that order;
                             first deny wins; exit 0 always; no output = allow
hooks/guard/common.py        payload parsing, path extraction (file_path/notebook_path/path/edits[].file_path, apply_patch headers),
                             deny() → {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny",
                             "permissionDecisionReason": …}} compact JSON like jq -nc, runtime from __file__ (.codex) or AI_HOOK_RUNTIME
hooks/guard/git.py           port of ai-git-guard.sh (rules as module constants)
hooks/guard/paths.py         port of ai-path-guard.sh (phase 3.1), rewritten (3.4)
hooks/guard/scope.py         port of ai-scope-guard.sh (reads current.json.files ∪ steps[].files when stage == build)
hooks/guard/ere.py           POSIX ERE → re translator (glibc semantics, invalid → never matches), lazy compile
stdin:  {"tool_name","tool_input":{…},"cwd","hook_event_name","session_id"?}   (Claude Code and Codex send the same envelope)
stdout: nothing (allow) | one deny JSON line; stderr: nothing; exit 0 (fails open outside the domain, never a traceback)
```

**Hook registration.** `settings.common.json`: one PreToolUse entry `{"matcher": "Read|Edit|Write|MultiEdit|
NotebookEdit|Bash", "hooks": [{"type": "command", "command": "\"$HOME/.claude/hooks/ai-guard.py\"", "timeout": 10,
"statusMessage": "Checking git, paths and scope"}]}` replacing the three at :29-60 (3.5); `cap-large-read.py`,
`context-guard.py`, `runtime-gate.py`, `project-scaffold.py` entries unchanged in shape. `codex/hooks.json`:
`{"matcher": "Bash|apply_patch|Edit|Write", … "$HOME/.codex/hooks/ai-guard.py"}` replacing :5-37. Plugin route
`hooks/hooks.json`: same entries with `"${CLAUDE_PLUGIN_ROOT}/hooks/ai-guard.py"` (format as superpowers'
`hooks/hooks.json`).

**`package.json`**: `{"name": "riskrails" (fallback `@<owner>/riskrails` if taken — unverified offline),
"version": "<plugin version>", "bin": {"riskrails": "bin/riskrails.js"}, "engines": {"node": ">=18"},
"files": ["bin/","hooks/","skills/","agents/","ai/","instructions/","profiles/","scripts/","codex/",
"settings.common.json",".claude-plugin/",".codex-plugin/"], "dependencies": {}}`. Flags of `npx riskrails`:
`--target auto|claude|codex|both  --plan pro|team-pro|team-max|max|max20|balanced-max  --fable auto|yes|no
--codex-plan plus|pro|balanced-max  --dry-run  --home DIR  --codex-home DIR  --yes  --version`; non-tty behaves as
`install.sh` does today (detection used, printed on stderr). It shells to `python3 -I scripts/resolve-profile.py`,
`scripts/merge-codex-config.py`, `scripts/render-codex-agents.py`, `skills/project-update/render_instructions.py`;
JSON merges (settings, hooks.json) are done in Node (port of the jq merge; no duplicate command). When a plugin
cache `~/.claude/plugins/cache/*/riskrails/<ver>/` exists it skips skills and hooks and registers nothing twice.

**Manifests.**

```
.claude-plugin/plugin.json      {"name":"riskrails","version":…,"description":…,"author":{"name":"Ivan Kakurov"},
                                 "homepage":…,"repository":…,"license":…,"keywords":[…],"skills":"./skills/","hooks":"./hooks/hooks.json"}
.claude-plugin/marketplace.json {"name":"riskrails","owner":{"name":…},"metadata":{"description":…,"version":…},
                                 "plugins":[{"name":"riskrails","source":{"source":"url","url":"<repo>.git"},"version":…,"strict":true}]}
.codex-plugin/plugin.json       {"name","version","description","author","skills":"./skills/","hooks":"./hooks/codex-hooks.json",
                                 "interface":{"displayName":"RiskRails","shortDescription":…,"category":"Developer Tools"}}
.agents/plugins/marketplace.json {"name":"riskrails","interface":{"displayName":…},
                                 "plugins":[{"name":"riskrails","source":{"source":"local","path":"./"},
                                 "policy":{"installation":"AVAILABLE","authentication":"ON_INSTALL"},"category":"productivity"}]}
```

Agents, `profile.json`, the managed block, `ai/`, `config.toml`/`settings.json` merges and migrations stay with
`npx` (and `/setup --update` for migrations). Plugin-only install = supported degraded mode for light and
guarded; `/build` in full mode without `~/.claude/agents/ai-reviewer.md` prints the `npx` line and stops.

**Names (R35, from task 3.4b; old form recognised for one version).**

| What | Today | From 3.4b |
|---|---|---|
| display name | claude-agentic | RiskRails |
| npm package, bin, plugin, marketplace | — | `riskrails` (`npx riskrails`) |
| skill namespace | `claude-agentic:<skill>` | `riskrails:<skill>` |
| install home | `~/.claude/claude-agentic/`, `$CODEX_HOME/claude-agentic/` | `~/.claude/riskrails/`, `$CODEX_HOME/riskrails/`; symlink at the old path for one version |
| managed-block markers | `<!-- claude-agentic:start -->` / `:end` | `<!-- riskrails:start -->` / `:end` |
| rule markers | `claude-agentic:rule:<slug>:start` / `:end` | `riskrails:rule:<slug>:start` / `:end` |
| env vars | `CLAUDE_AGENTIC_{TEMPLATES,SHARED,MIGRATIONS,TEST}` | `RISKRAILS_{…}`; old name read when the new one is unset |
| profile key | `claude_agentic` | `riskrails` |
| state file | `.ai/state/current.json` | `.ai/state/state.json` (R34) |
| not renamed | `.ai/`, the repository directory and git remote, history (`docs/sdlc/*/claude-agentic-*.md`, `.ai/reports/**`, journals, `files/`) | — |

**Migration `0008_renames.py`** (`VERSION = 8`, task 3.4b): `MOVES = [(".ai/state/current.json", ".ai/state/state.json")]`
(in flight or not); managed-block and rule markers rewritten in the project's `CLAUDE.md`/`AGENTS.md` with the text
around the block untouched; `.ai/AGENTS.md` router rows naming `claude-agentic/ai-path` → `riskrails/ai-path`.

**Migration `0007_weight_model.py`** (`VERSION = 7`, `MOVES = [(".ai/policies/risk-tiers.json", ".ai/policies/weight.json")]`):

| From | To |
|---|---|
| `tiers.<T>.examples[]` | `examples.light` (T0–T2), `examples.guarded` (T3–T4), `examples.full` (T5–T6) |
| `path_scopes[scope ∈ payments, money, tax, invoice, identity, customer_data, personal_data].paths` | `axes.domain.modules` |
| `path_scopes[scope ∈ auth, security].paths` | `hints[axis=domain]` |
| `path_scopes[scope ∈ infra, k8s, deploy, production].paths` | `reversibility.irreversible` when the glob contains `prod`, else `reversibility.needs_step` |
| `path_scopes[scope ∈ migrations, schema, config].paths` | `reversibility.needs_step` |
| `path_scopes[scope ∈ pipeline].paths` → `hints[axis=behaviour]`; `dependencies` → `hints[axis=novelty]`; `tests`, `docs`, `source` | dropped |
| `review_rounds_max`, `remediation_rounds` | carried; `sensors.tests.*` → `tests.*` with `max_suite_runs = min(old, 2)` |
| `diff_budget`, `sensors.{required_for_skip,lint,typecheck,bite,duplicates}`, `pipeline_profile(s)`, `model_tiers`, `escalation_*`, `downgrade_rule`, `remediation_rule` | dropped (prose moves to `docs/weight.md`) |
| `risk-tiers.md` | `delete?` (only with `--confirm-delete`); `weight.md` created by `weight --mirror` |
| `current.json.tier` (task in flight) | `patch_state`: `mode` by the T-label map, `weight: {w: null, axes: {}, unknown: ["migrated"]}` |
| router rows in `.ai/AGENTS.md` naming `/ai-task`, `risk-tiers.json`, `review-gate` | `edit_text` to `/build`, `weight.json`, `state.py close` (original kept; block conflicts are walk conflicts) |
| old skill names in project `CLAUDE.md`/`AGENTS.md` managed blocks | re-rendered block (walk), not a migration op |

## Policy conformance

Read for this pass: `docs/sdlc/constitution.md` (C1–C6; C7–C10 are empty placeholders), repo `CLAUDE.md` and
`AGENTS.md` (both exist and describe the same project — one disagreement, FC-B6), the global
`~/.claude/CLAUDE.md` (this runtime; `~/.codex/AGENTS.md` not read — not the runtime in use), `.ai/AGENTS.md`,
`.ai/policies/{safety,testing,coding,security}.md`, `.ai/policies/risk-tiers.json` (the "this repository:"
examples, :218/:246/:278), `.ai/rules/{hooks,skills}.md`, `docs/sdlc/specs/direct-mode-diet.md` (its four tasks
are committed: `4b3b9e1`, `ef6e9a1`, `ee838dc`, `e2841c4` — the intent's constraint :125 is met). No
`.claude/skills/`, `.claude/agents/`, `.codex/skills/` or `.codex/agents/` exist in this repository. No ADRs
exist (`docs/sdlc/adr/` holds only `TEMPLATE.md`), so none binds. Plugin skills matching the stack:
`superpowers` 7.0.1 (installed user-wide) — the subject of SQ12; the Symfony UX skills do not apply (no PHP here).

| Policy | How the design honours it |
|---|---|
| C1 production behaviour is the source of truth | the port is byte-identical on the golden before any rule moves (R12, task 3.1); `/setup --adopt` inventories a project's own toolbox instead of replacing it (SQ5) |
| C2 failing test first, characterization before change | coverage axis = 2 forces characterization first; `verify --expect fail` replaces `bite` as the bugfix evidence (R33); the 20 KB `timed` case fails on the shell tree before the port (R14) |
| C3 refactoring never mixed with a feature | port (3.1–3.3), rule rewrite (3.4) and the two renames (3.4b) are separate tasks; the `.sh` guards become exec shims so registrations do not change inside the port; entries switch with the installer task (3.5) |
| C4 every step names its files; scope grows only by amending | each task row names its files; `start --amend` amends in place and journals `scope_change` (R25) — scope still grows only by an explicit amendment |
| C5 no agent commits, merges, deploys; human approves outside | full mode's gate stays `approve --by` outside the agent; "solo approval in chat" from the second analysis is not adopted (FC-A1); `npm publish` is a human act and the git guard gains a deny for it (FC-A5) |
| C6 tier a plugin change by its effect on a user project's decisions | every phase task is tiered under today's rules in the Design table; the new weight scores this repository's own tasks by the same axes (SQ1 self-check) |
| `CLAUDE.md` lesson 1: a BLOCKER closes only with a pinning test; `timed` case for regex running time | R14's timed case; R22's rewrite re-records the golden and adds a fixture per remaining deny; risks table names the test for each risk |
| `CLAUDE.md` lesson 2: hooks/skills/`state.py` are not T4 for being a process | tasks 1.4, 2.3, 3.1–3.3, 3.6 are T2/light-guarded; only the literal T4 triggers of `skills.md:6` are T4 (1.2, 1.3, 2.2) |
| `.ai/AGENTS.md` / `safety.md`: policy files are human-edited; state written only by `state.py`/`update.py` | the repo's own `.ai/policies/*`, `.ai/rules/*`, C6 and `CLAUDE.md` change only in the human rows 2.H and 3.H; shipped templates change in tasks with `tools/build-template-history.py` (skills.md:7) |
| `safety.md` threat model (agent mistakes, not constructed commands) | SQ13 drops `sh -c`/`eval` re-parse and records the bypass in `known-risks.md` under that model |
| `safety.md` "when in doubt, stop and ask" | R24 defines a real blocker; the residual conflict is FC-A3 |
| `testing.md` verify once, to the end, one batch; three commands | `verify --scope all` once; `max_suite_runs` 2 (R20); `run-all.sh` stays a valid `verify_command` during the port; the human swaps it in 3.H |
| `coding.md` one logical change per step; no new abstraction before three call sites; dead code deleted only in a task about deleting it | removals are their own tasks (1.3, 2.4); `hooks/guard/*` modules have three callers (one per runtime/route) before the split |
| `security.md` checklist (secrets, command execution, dependencies) | path guard keeps the secrets deny (R22); `npx` installer has `dependencies: {}` and shells only to shipped scripts with `python3 -I`; supply-chain questions in FC-S1–S3 |
| `.ai/rules/hooks.md`, `skills.md` (T2/T3/T4 definitions) | used verbatim to tier phase 1–2; reworded to modes by the human in 2.H (FC-A4) |
| Global `~/.claude/CLAUDE.md` (session implements; STRONG/EXPERT only on a named trigger; no agent commits; verify once) | `ai-implementer` removed (SQ3); full mode uses one STRONG review; no fleet; FAST-vs-BALANCED readers is FC-A2 |
| `direct-mode-diet.md` decisions (two review passes, `close` as the exit, `test-run --scope all`, project tier examples) | `review_rounds_max` 2 carried; `close` stays the exit; `verify --scope all` is `test-run --scope all` renamed; `examples` migrate to `modes.<mode>.examples` (R23) |
| Memory: in the Bash tool `grep` is ugrep | timing measurements for R14 run inside the Python test (`time.perf_counter`), never through the shell's `grep` function |

## Open questions

Owner of each: the developer, unless stated. The architect's recommendation is in brackets; SQ numbers refer
to **Decisions on the intent's open questions** above.

- OQ1 (SQ8) Command surface: seven (`/setup /spec /plan /build /review /ship /status`) or nine plus `/task`.
  [seven]
- OQ2 (SQ4) `/build` or `/task` for the implementation command. [`/build`]
- OQ3 (SQ9) Mode names: light / guarded / full or quick / plan / full. [light / guarded / full — `plan` and
  `quick` already mean other things]
- OQ4 (SQ12) Superpowers: variant A (disabled in `.ai/` projects, two skills absorbed into `/build`) or B
  (delegated from each command, fallback line when absent). [B; `/setup` never writes `enabledPlugins`]
- OQ5 (SQ15) T0–T6: three mode words only, with a `tier_set` compat event for one version? [yes] — and which
  T↔mode map (FC-B1).
- OQ6 (SQ3) Keep `ai-implementer` as a seventh agent template? [no]
- OQ7 (SQ16) Team profile: documented, slow-tagged tests? abrites-staging-v2: inventory with `--adopt`, then
  abandon the `ai-tools` branch? [yes to both]
- OQ8 npm package name `riskrails` free or scoped `@<owner>/riskrails` — check with `npm view riskrails`
  before task 3.4b; and whether "RiskRails" is already the name of another product or a registered mark (a
  web and trademark search). Unverified.
- OQ9 Do `/plan`, `/review` or `/status` collide with a built-in Claude Code / Codex command or another
  installed plugin's skill? Manual check before task 2.3 (risk 11).
- OQ10 The three open tasks on the production machine (ArgoCD 09-14, oroCRM 09-30-002, abrites-site-v2
  10-22-001) — closed? This repository's T-2026-10-22-002 is committed (`ada69e3`) and no task is in flight
  here; the other three cannot be checked from this machine. Precondition for phase 1 (intent :203-205).
- OQ11 **Decided 2026-10-25 (developer): yes** — `current.json` → `state.json`, in task 3.4b (R34). Was:
  whether to rename in task 3.4 or never (Contradictions §17). [the architect recommended never,
  unless it rides with 3.4]

## Flagged concerns

Grouped: **A** policy vs intent (or vs the second analysis), **B** policy vs policy or inside this design,
**C** requirements that cannot be fully satisfied, **D** assumptions the intent left open, **S** security
and data protection. The architect's full contradiction list (23 items, with `file:line` on both sides) is
kept verbatim after the groups; the groups below are the ones a human must decide or accept.

### A. Policy vs intent

- **FC-A1 — "Solo approval is a chat answer" (second analysis §6.3) vs C5** (constitution :10, the WP2
  `approve` rule). Cannot satisfy both. Proposed: plan-mode acceptance in guarded mode is not a C5 approval
  (nothing leaves the branch); full's gate stays `state.py approve --by` outside the agent. The second
  analysis' metric "stops guarded 0" is therefore not met (FC-C1).
- **FC-A2 — "Readers with judgement on BALANCED" (intent :178-180) vs global `~/.claude/CLAUDE.md` "readers
  and runners on FAST at `low`"** (rendered from `instructions/stub.md:29`). The global file is the user's
  private instruction; its managed part is rendered by this plugin. Proposed: the stub changes in task 2.3
  (R32); until it is re-rendered the installed rule holds. The user's personal lines outside the managed
  block are not touched.
- **FC-A3 — "Questions collected once, only a real blocker stops" (intent :193) vs `safety.md:67-70` "When
  in doubt, stop and ask".** Proposed: R24 defines a blocker (guard refusal, re-score of reversibility or
  domain to 2, a plan assumption proven false), and the human adds one sentence to `safety.md` in 2.H. Until
  that sentence exists, the stricter rule (`safety.md`) wins.
- **FC-A4 — T2/T3/T4 vocabulary in binding policy** (C6 :11, `.ai/rules/hooks.md:6`, `skills.md:6`,
  `CLAUDE.md` lesson 2, `risk-tiers.json` "this repository:" examples) vs the rename. The spec cannot edit
  these files (human-edited, task-protected). Proposed: human row 2.H with exact text. **Bootstrap
  consequence:** tasks 1.2, 1.3 and 2.2 are T4 under today's literal wording (`skills.md:6` names install and
  the approval path) even though C6 would put 1.3 at T2; they cost one STRONG review each.
- **FC-A5 — Publishing to npm (intent :84) vs C5 "no agent deploys".** A publish is outward-facing and
  irreversible (a version number cannot be reused). Proposed: the human publishes; task 3.5 adds an `npm
  publish`/`npm version` deny to the git guard as a separate, additive step (T3, golden re-recorded).
- **FC-A6 — `/setup` adopts instead of a knowledge base (intent :73-74) vs `.ai/AGENTS.md` item 6 and
  "Keeping this directory true … re-run `/ai-init`"** (:62-66). Proposed: `.ai/project/` becomes opt-in
  (`--knowledge-base`); item 6 stays (it binds only what is written); the closing section points to `/setup
  --update`. The template change runs `tools/build-template-history.py` in the same task.
- **FC-A7 — `verify_command` changes during the port (intent :80-81) vs `testing.md` is human-edited**
  (`testing.md:87`, `:121` "every suite is a bash script"). Proposed: `bash tests/run-all.sh` stays valid as a
  wrapper over `unittest discover` plus the surviving `.sh` until the last one is gone; the human swaps the
  line in 3.H.

### B. Policy vs policy, or inside this design

- **FC-B1 — Two different T↔mode maps in this design.** The compat event (Interfaces, `events.jsonl`) maps
  light → T2, guarded → T4, full → T5, full_irreversible → T6; the 2.H reword of the rules maps T2 → light,
  T3 → guarded, T4 → full. The second analysis says guarded ≈ T3–T4, full ≈ T4–T6. These cannot all hold:
  under the 2.H map a guard change that "allows what was denied" (today T4) is full, under the compat map T4
  is guarded. **Must be decided before task 2.2.** Recommendation: rules map by *effect* (T4-class effects —
  allow a deny, change approval/install — score behaviour 2 and land in full by their weight, not by a
  label), and the compat label is cost-equivalent (guarded → T4) for report continuity only; say both in
  `docs/weight.md`.
- **FC-B2 — Guarded mode has one human stop (plan-mode acceptance) in this design; the second analysis'
  target is 0 stops for `plan`.** The intent's outcome ("a guarded task gets one plan-mode plan") implies the
  stop. Proposed: keep the stop; it is the plan-mode approval the developer already uses (158 plans in
  new-shop). Metric target for guarded becomes ≤ 1.
- **FC-B3 — Repo `CLAUDE.md` and `AGENTS.md` disagree:** the two "Things Claude Code gets wrong" lessons
  (BLOCKER needs a pinning test; tier by effect, not by being a process) are absent from `AGENTS.md`'s "Things
  Codex gets wrong". A Codex session on this repository does not see them. Out of this spec's scope to fix
  (production-behaviour rule); recorded here for the human — one copy, or a shared include rendered into
  both.
- **FC-B4 — `superpowers`' "MUST invoke a skill before any response" (SessionStart banner) vs this module's
  own process rules and the user's instruction priority.** In the session that wrote this spec (2026-10-25) the banner and
  the `/sdlc-spec` skill overlapped; the user instruction won, as superpowers itself says. The redesign must not
  rely on that precedence silently: SQ12 (variant B) maps each command to exactly one superpowers skill and
  R28 measures the combined SessionStart cost (≈ 9.6 KB worst case, ceiling 10 KB).
- **FC-B5 — `max_suite_runs` is a policy number** (`risk-tiers.json:599`) vs phase 1 changing it. The shipped
  template changes in task 1.1; this repository's own copy changes only by the human, outside a run.

### C. Requirements that cannot be fully satisfied

- **FC-C1 — Second analysis metrics.** "Stops quick/plan: 0" (FC-A1, FC-B2) and "procedure tokens ≤ 6 000"
  are not provable by this design before phase 2 lands; R5 measures lines of policy (≤ 400), not tokens.
  Proposed: measure tokens with `/usage-report` on the first five guarded tasks after 2.3 and record them in
  `task.md`; not a gate.
- **FC-C2 — Per-guard latency budgets (intent :141-144) cannot be measured once three guards are one
  process.** Proposed: one budget per event kind (R14: Bash 1 KB ≤ 40 ms, Edit/Write/Read ≤ 25 ms, 20 KB ≤ 100
  ms). This is stricter than the sum of today's three guards (the runtime runs them in parallel, so today's
  wall time ≈ the slowest, ≈ 40 ms); Python start-up (≈ 15–20 ms) leaves little margin — risk 4.
- **FC-C3 — "Agents 14 → 7 or 8" vs "22 → 7"** count different things (templates vs installed files with
  twins and `.bak`). Six templates satisfy both readings; the number in docs will be "six agent templates".
- **FC-C4 — "state.py 28 → 4 public subcommands" (intent :98) cannot carry weight, review verdicts, questions
  and status.** Proposed: 9 model-facing + 2 human-only + 3 internal; the light path still uses three calls
  (R5).

### D. Assumptions the intent left open

- **FC-D1 — Blast radius is a pre-diff proxy.** Scope is measured by references to each declared file's
  identifier (`git grep -lwI`) because no diff exists at `/plan`. A file whose basename is a common word
  (`index`, `base`, `utils`) over-counts; a file called through configuration under-counts. Scope is not
  re-scored after the work (deliberately). Accepted limitation; test `test_grep_budget` and a common-word
  fixture should pin the behaviour.
- **FC-D2 — Threshold adjusted from the second analysis.** Light is W ≤ 2, not ≤ 3, so that the guard regex
  fix and an ArgoCD `env/dev` manifest land in guarded as both analyses intend. Every other validation case
  is unchanged. The developer should confirm the change.
- **FC-D3 — The migration-0006 validation case reaches full_irreversible only through a project-configured
  `irreversible_content` pattern** (`delete(`) in this repository's `weight.json`; with the shipped defaults it
  is full (reversibility 2), not full_irreversible. The shipped default list is SQL-shaped; repositories whose
  irreversible operations are file deletions in user trees must add their own pattern.
- **FC-D4 — The productEditorApp and Learning Workbench cases are INFERENCE** (scored from the intent's
  descriptions, not from their journals). The intent requires they land in guarded; the worst realistic
  productEditorApp feature (new mechanism, no tests) scores 9 → full, which C2 justifies. Before task 2.1
  closes, score three real journaled tasks from each project with `state.py weight` on their file lists.
- **FC-D5 — Plugin-only install is a degraded mode** (skills + hooks + `state.py`, no rendered agents, no
  managed block, no `profile.json`). Full mode stops with the `npx` line. Whether this is acceptable to a
  user who installs from `/plugin` alone is a product decision.
- **FC-D6 — Codex best effort.** A Codex-only red suite is a finding, not a `close` refusal; that needs
  `verify` to classify failures by suite name (`test_codex_*`), a small new rule in `state.py`. Codex
  `trusted_hash` invalidation when hook commands change (risk 6) can silently disable the guards in Codex
  until the user re-trusts in `/hooks`.
- **FC-D7 — The design file's earlier memory of `hooks/lib/ai_os.py`/`ai_ere.py`** does not match the branch:
  `hooks/lib/` holds only `ai-hook-common.sh`. The port starts from zero Python guard code; the estimate for
  phase 3 should assume that.

- **FC-D8 — The RiskRails rename reaches further than a name** (R35): 98 tracked files today, 40 lines of the
  guard golden, the managed-block markers in every user project's `CLAUDE.md`/`AGENTS.md`, the install home,
  four env vars and the profile key. It is a refactoring (C3) but it changes install and migration, so it is
  a full-mode task with a compat version. Not verified: that npm `riskrails` is free and that no other product
  or mark is called RiskRails (OQ8). The repository directory, the git remote, this spec's and the intent's
  slugs and the evidence bundle keep the old name (history); renaming the repository is the developer's
  separate decision.
- **FC-D9 — The `state.json` rename overrides the architect's recommendation** (Contradictions §17). Its cost:
  58 golden lines and 4 path-guard fixtures name `current.json`, so the golden is re-recorded, and every user
  project with a task in flight needs the move. Mitigation: never inside the port (3.1) or the rule rewrite
  (3.4) — it rides only in the rename task 3.4b, where the golden diff is checked to touch only path strings.

### S. Security and data protection

- **FC-S1 — `npx riskrails` runs whatever is the latest published version** and installs hooks that see
  every tool call. Docs and the `install.sh` wrapper should print a version-pinned line
  (`npx riskrails@<version>`); npm publishing should use 2FA and provenance. Owner: developer.
- **FC-S2 — The installer merges `~/.claude/settings.json`, `~/.codex/config.toml` and `hooks.json`.** A
  malformed merge can drop the user's own hooks or permissions. The Node merge must keep a dated backup in
  one `backups/` directory (the intent's `.bak` decision) and the routes suite must assert foreign keys
  survive.
- **FC-S3 — The path-guard rewrite (3.4) allows what was denied** (reads always allowed except secrets; no
  `sh -c` re-parse). The threat model accepts constructed bypasses, but the secrets deny must keep its
  fixtures; it is a full-mode task with a security-focus review.
- **FC-S4 — Evidence from client projects.** The bundle (`files/claude-agentic-bundle-2026-10-24.zip`) and
  the extract `files/second-analysis-2026-10-24.extract.md` hold journals and task descriptions from client
  repositories (oroCRM, abrites, oddoAbries, new-shop). `files/` is git-ignored (`.gitignore:12`). Test
  fixtures for `test_weight` must be synthetic (file lists and goals rewritten), never copied journals.
- **FC-S5 — `AI_UNATTENDED=1` still turns the gates off** (README known risk), and R27 lets it lower a mode.
  Unchanged by this design; stays a documented risk.

- **FC-S6 — Two state-file names during the compat version.** If the path guard protected only `state.json`,
  a stale `current.json` from an old install could be written by an agent and then read by the old-name
  fallback; if the scope guard armed only on one name, it could disarm mid-task. R34 requires both names
  protected and either name arming the guard, with a fixture for each.

### Contradictions found by the architect (verbatim, with sources)

Line numbers labelled "second analysis :N" refer to `files/second-analysis-2026-10-24.extract.md`.

Each: side A (file:line) vs side B (file:line) → what the spec proposes.

1. **`state.py` 28 → 4** (intent :98; first analysis :215-217) vs **≈ 10** (second analysis :719) → 9
   model-facing + 2 human + 3 internal (Interfaces); four cannot carry weight, review, ask/answer, status.
2. **Agents 14 → 7 or 8** (intent :76; first analysis :211-213) vs **22 → 7** (second analysis :716-717,
   counts installed files incl. `.bak` and Codex twins) → 6 templates (SQ2, SQ3); both numbers satisfied.
3. **Path floors deterministic** (intent :60-61, first analysis :245-246) vs **hints** (intent :188-189,
   second analysis :635) → hints; the deterministic residue is `domain.modules` + `reversibility.irreversible`.
4. **Light = three `state.py` calls** (intent :64) vs **quick = no state** (second analysis :615) → three
   calls: the scope guard needs `current.json.files` and `/status --cost` needs the journal.
5. **Solo approval is a chat answer** (second analysis :543, :688) vs **C5** (constitution :10) and the WP2
   `approve` rule (`WHY_APPROVE`, `ai-path-guard.sh:162`) → plan-mode acceptance (guarded) is not a C5
   approval because nothing leaves the branch; full's gate stays `approve --by` outside the agent; no chat
   route to a gate. Cannot satisfy the second analysis literally.
6. **Readers with judgement on BALANCED** (intent :178-180; first analysis :317-318) vs **global
   `~/.claude/CLAUDE.md` "readers and runners on FAST at `low`"** (rendered from `instructions/stub.md:29`)
   → the stub text changes in 2.3 (R32); until then the installed rule holds.
7. **Questions collected once, only a real blocker stops** (intent :193; second analysis :687) vs
   **`safety.md:67-70` "When in doubt, stop and ask"** → the spec defines a real blocker (R24); `safety.md`
   gains one human-written sentence ("doubt on reversibility or domain is a blocker; other doubt is written
   to `task.md` and the work continues") in 2.H.
8. **T2/T3/T4 labels** in C6 (constitution :11), `.ai/rules/hooks.md:6`, `skills.md:6`, `CLAUDE.md` "Things
   Claude Code gets wrong" vs the rename → human rewords in 2.H with the map T2 → light, T3 → guarded,
   T4 → full; the spec cannot edit these files (policy, task-protected).
9. **`/setup` adopts instead of a knowledge base** (intent :73-74; first analysis :306-309) vs
   **`.ai/AGENTS.md:23-25` item 6** (evidence labels in `project/`) and **:62-66 "Keeping this directory
   true" / "Re-run `/ai-init`"** → `project/` becomes optional (`--knowledge-base`); item 6 stays (it binds
   only what is written); the closing section says `/setup --update`; template change runs
   `build-template-history.py` in the same task (skills.md:7).
10. **`verify_command` changes during the port** (intent :80-81, :219) vs **`testing.md` is human-edited**
    (safety.md; `task_protected_patterns` `.ai/policies/`; `testing.md:121` "Every suite is a bash script")
    → `run-all.sh` stays a valid `verify_command` as a wrapper until the last `.sh` dies; one human edit (3.H).
11. **Per-guard latency budgets** (intent :141-144) vs **one process** (intent :80-81, :215-217) → one
    budget per event kind (R14); the Bash budget equals the slowest guard today because the runtime ran the
    three in parallel.
12. **Publishing to npm** (intent :84) vs **C5 "no agent deploys"** → the human publishes; the git guard
    gains an `npm publish`/`npm version` deny as a separate additive step in 3.5 (T3 by hooks.md:6, golden
    additive), not accepted silently.
13. **`/build` is the router** (intent :177; first analysis :268-279) vs **`/task` is the chain and
    `/plan` computes the weight** (second analysis :521-524, :556-559) → `/plan` computes, `/build` routes
    (calls `/plan` when no task exists); no `/task`.
14. **`/plan` writes `plan.md` in full** (second analysis :524) vs **one artefact** (intent :69-71) → plan
    is `task.md` §Plan.
15. **Three control files** (intent :70-71; first analysis :321-323 lists `handoff.md` and `questions.md`
    as removed) vs the WP2 approval-by-file route (human edits `[Answer]:` in a guard-protected file) and
    `handoff.md` read by `context-guard.py:376-399` → questions move into `task.md` §Questions, which only
    `state.py` writes and the guard protects (phase 3); `handoff.md` stays as a state-side render target
    (git-ignored, `.gitignore:9`), written five times per task.
16. **Fan-out budgets go** (intent :200) vs **`runtime-gate.py:1117-1123` reads `budgets.fan_out`** and
    **`DIRECT_MODE_CAP` exit 7 on `budgets.direct_mode.max_tier`** (WP5) → both removed in 2.4; `expert.
    without_asking` and the outage reroute stay; `profiles/*.json` lose the two keys.
17. **`state.json`** (intent :70) vs **`current.json` read literally by `ai-scope-guard.sh:29`**, the path
    guard patterns and `context-guard.py` → **overridden by the developer on 2026-10-25 (OQ11 yes): renamed
    in task 3.4b (R34), a rename task of its own; the architect's original answer follows.** The name stays `current.json`: a rename moves a guard decision
    (when the scope guard arms) for no function and would force a golden change inside the port (C3). The
    spec calls it "the state file"; a rename can ride with 3.4 if wanted.
18. **Diet D3c "direct mode (T0–T4)" bounded reviewer inputs** (`direct-mode-diet.md:374-384`) vs modes
    → bounded in light and guarded, unbounded in full; the reviewer brief says so in mode words (2.4).
19. **Intent :106 "thirty `tests/*.sh`"** vs the tree: 28 `test-*.sh` + `lib.sh` + `run-all.sh`; golden
    "1047 runs" in earlier notes vs 1236 `###` now → the port's baseline is HEAD at 3.1's start, whatever
    the count.
20. **Superpowers facts** (intent :265-275: "not installed here") vs `~/.claude/settings.json:189`
    (`superpowers@superpowers-marketplace: true`) and this repo's `.claude/settings.json` = `{}` → settled
    in the intent's own update; the decision is per plugin (SQ12).
21. **"Codex is not a gate"** (intent :202-203) vs **`testing.md` `verify_command` runs the Codex suites**
    → they stay in the runner; a Codex-only red is a finding in `task.md`, not a `close` refusal (R19) —
    which needs `verify` to classify by suite name (`test_codex_*`), a small rule in `state.py`.
22. **Earlier design memory for the os-independent intent** (shims, `hooks/lib/ai_os.py`, `ai_ere.py`) vs
    **the branch** (`hooks/lib/` holds only `ai-hook-common.sh`) → the port starts from that design, not from
    code; module names here are `hooks/guard/*.py` to avoid implying the old files exist.
23. **`max_suite_runs` is a policy number** (`risk-tiers.json:599`, human-edited per safety.md) vs **phase 1
    changes it** (second analysis :777) → the shipped template changes in 1.1 (agent-editable, history
    rebuilt); this repository's own copy changes by the human, outside a run.
