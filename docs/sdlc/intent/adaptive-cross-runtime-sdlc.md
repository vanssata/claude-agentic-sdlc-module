# Intent: Adaptive, cross-runtime SDLC — file-backed decisions, small batches, migration of existing projects

<!-- Stage 1 of the SDLC flow. Say WHAT and WHY. Leave HOW to the spec. -->

Sources reviewed on 2026-09-19: AWS AI-DLC (`awslabs/aidlc-workflows`), DORA 2024/2025 and
Google engineering posts, Meta (ACH, Diff Risk Score, JiTTests), Nvidia AI red team,
GitHub Spec Kit, OpenAI harness engineering, Anthropic context engineering and multi-agent
cost findings, Stripe Minions, Shopify Roast, Airbnb test migration, METR, GitClear, Faros.

## Problem

1. **Decisions live in the chat.** Clarifying questions and their answers exist only in the
   conversation. `/clear`, compaction or a switch between Claude Code and Codex loses them,
   and nothing records who answered what. The same is true of "what was tried and
   rejected": it survives only as long as the session does.
2. **Always-loaded instructions are too large.** `~/.claude/CLAUDE.md` is ~8.5 KB and
   `AGENTS.snippet.md` ~10 KB (a third of Codex's 32 KiB project-doc limit), re-read every
   turn in every repository, although most of it matters only inside `/ai-task`.
3. **Speed is not bounded by batch size.** The tier is set before the code exists and is
   never checked against the real diff. Nothing caps how large a step may grow. Industry
   data (DORA 2024: −7.2 % stability; Faros 2026: review time +441 %, incidents per PR
   +243 %) names change size as the main way AI throughput destroys quality.
4. **The review is the first check, not the last.** Lint, type-check, plan completeness,
   step-to-test traceability and duplicate blocks are found by a paid model, or not at all.
5. **The human approval is a field.** `state.py approve --by` can be called by an agent;
   nothing ties it to an observed human turn.
6. **A task cannot change runtime.** One `.ai/` tree serves Claude Code and Codex, but the
   state does not say which runtime owns the task or where to resume, so OpenAI models
   cannot be the primary for some tasks and Claude for others, and a T4 change cannot be
   reviewed by the other vendor.
7. **Plans differ only by model, not by budget.** There is no Max 20x profile; Max 5x and
   Max 20x, and Codex Plus and Pro, differ in quota, which should drive fan-out and
   escalation, not model names.
8. **The guards' cost is untracked.** They are the only part of the system that runs on
   *every* tool call, and nobody was measuring them: `ai-git-guard` cost 148 ms per Bash
   call and `ai-path-guard` 96 ms, 74 processes per Bash call, 30–40 s of pure waiting in
   a 150–200-call session — wall-clock the user pays on every task, at every tier,
   including the T0 ones the pipeline never touches. Nothing in the repository stated a
   budget, and nothing proved that a change to a guard did not also change its decisions.
9. **Existing projects cannot follow.** `project-update` merges the content of files it
   knows. It has no structural migrations (move, split, new schema) and cannot take in a
   project shaped by another tool (Spec Kit, Kiro, AI-DLC, Cursor rules, a large
   hand-written `CLAUDE.md`). Every improvement above would reach new projects only.

## Proposed outcome

**Questions and continuity**

- Questions are written to `.ai/reports/<task-id>/questions.md` (multiple choice, a
  recommended option, `X. Other`, an `[Answer]:` tag) by a deterministic command before
  they are shown. The panel in use renders them: a native picker where the runtime has
  one, numbered prose answered as `1B 2A 3: text` everywhere else. Editing the file by
  hand is a valid third way. Every answer is written back to the file by a command, never
  free-hand by the agent.
- A stage does not advance while a question is pending. Pending questions are picked up
  by a new session and by the other runtime.
- A subagent never asks; it returns `QUESTIONS_NEEDED` and the main session asks. A
  headless run writes the file and stops with a "waiting for answers" result.
- `.ai/state/handoff.md` (≤ 30 lines: decisions with reasons, rejected options, failed
  attempts with the error text, next step, the user's latest instruction verbatim) is
  rewritten at every stage change and before compaction, and is the first thing a new
  session reads, in either runtime.
- An append-only `.ai/reports/<task-id>/events.jsonl` with one flat event type per command
  that changes state (`stage_started`, `question_answered`, `scope_change`, `tier_raised`,
  `gate_approved`, `runtime_handoff`, `model_fallback`, …; twenty in WP2, listed in its
  spec), readable by `/ai-status` and `/usage-report` at zero model cost. Flat, because a
  reader finds one with a single `grep` and no type exists without an emitter. A new type
  is added only when it has its own consumer; anything else reuses `field_set` or `note`.
  This is not AI-DLC's event taxonomy: there is no event that no command emits, and no
  gate per stage.

**Context diet**

- Every always-loaded instruction file (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
  `.junie/guidelines.md`, global and project) is a stub rendered from one source, within
  a byte budget that a test enforces (target ≤ 2 KB project, ≤ 2.5 KB global).
- `.ai/AGENTS.md` becomes a router ("doing X → read Y"); rules live in policies,
  per-directory instruction files, path-scoped rules and skills, loaded on demand.
  Pipeline procedure moves into `/ai-task`.
- `docs/sdlc/constitution.md` holds the 10–15 non-negotiable project principles, read by
  `/sdlc-spec` and the planner.

**Quality and cost gates, all deterministic**

- A per-tier diff budget (changed lines and files per step) in `risk-tiers.json`;
  exceeding it returns `SCOPE_CHANGE_REQUIRED` and the step is split.
- The tier is re-scored from the real diff after implementation (paths touched, file
  count, deleted tests, migrations, config). A higher result raises the tier; nothing
  lowers it but a human.
- Sensors run before any model review: lint, type-check, required plan sections,
  step-to-test traceability, duplicate blocks. The reviewer receives what already
  passed. An all-green T2 skips the model review on every plan (see decision 6).
- A red test is retried against the test output by the same tier up to N times;
  escalation happens only on `UNKNOWN`.
- At T3+ and for characterization tests, a new test must fail without the change.
- Scopes (`bugfix`, `refactor`, `feature`, `spike`) are a second axis next to the tier:
  the tier decides who reviews and approves, the scope decides which stages run and
  encodes "bugfix starts with a failing test" and "refactor changes no behaviour".
- An approval is accepted only when a human turn was observed after the plan was
  presented; unattended runs need an explicit environment flag and say so in the events.
- A token budget per task, per tier and per plan, reported by `/usage-report`.

**Runtimes and plans**

- The task state carries `owner_runtime` and a resume point; a `runtime_handoff` moves a
  task between Claude Code and Codex with nothing lost.
- A profile-level table names the preferred runtime per kind of task, so OpenAI models
  can be primary for some work (long mechanical implementation, mass refactoring, or
  while the Claude quota is ≥ 90 % used) and Claude for other work.
- T4+ may be reviewed by the other vendor when both subscriptions exist.
- Shared prompts name only abstract tiers (FAST / BALANCED / STRONG / EXPERT); concrete
  models appear only in `profiles/*.json`.
- A `max20` profile inherits `max` and changes budgets only (fan-out, how far direct mode
  reaches, whether EXPERT runs without asking). Plus vs Pro on Codex is treated the same
  way. Pro and Plus run strictly serially.
- `ai-path-guard` refuses writes to `.claude/`, `.codex/`, hooks and agent definitions
  during a task, and instruction files inside dependencies are treated as data.

**The hot path**

- The guards have a stated per-call budget and are measured against it, not estimated.
  The rules are the product; how they are evaluated is an implementation detail that may
  be optimised freely — as long as the decisions do not move.
- Any change to a guard is proved behaviour-preserving by a characterization suite that
  compares exit code **and full deny text** byte for byte against a golden file recorded
  from the previous revision. A deny that names a different pattern is a failure.
- The interpreter-startup floor (~20 ms) is accepted. The Python hooks are not ported to
  another language, and the payload JSON is not parsed in bash: both trade
  cross-platform simplicity for ~20 ms and are refused by default.

**Existing projects**

- A project carries a schema version. `project-update` runs ordered, idempotent
  migrations (detect / plan / apply, all inside the existing dry run) before the
  three-way merge, and the template history follows renames so a user's edits survive a
  moved file.
- `project-update --adopt` takes in foreign structures through a mapping table (Spec Kit,
  Kiro, AI-DLC docs, Cursor rules, Copilot / Junie / Gemini instruction files, a large
  hand-written `CLAUDE.md` or `AGENTS.md`).
- **`migrate` is the default mode.** Content is moved into the new structure and the
  result must be 100 % adapted: no file of the new structure refers to the old one, and
  nothing still has to be read from it. `coexist` (leave foreign files, link to them) is
  opt-in, for teams where others still use the other tool.
- Splitting a large instruction file is the only step that uses a model (BALANCED tier,
  once per project). It is shown as a diff and applied only after approval.
- A deterministic **no-line-lost check** proves that every meaningful line of every
  migrated source is present in a destination file or listed in an explicit "dropped
  because …" list. A second check proves there are no dangling references to the old
  paths. Adoption is not complete until both pass.
- **Deleting the old structure is a separate step, offered only after both checks pass,
  and executed only after explicit human approval** recorded with who and when. Until
  then the originals stay in place and a copy is kept under
  `.ai/reports/adopt-<date>/original/`. The report lists what was detected, where each
  piece went, what was dropped and why, and what is proposed for deletion.

## Affected users & systems

- The plugin's users on Claude Pro, Max 5x, Max 20x, Team seats, and on ChatGPT Plus and
  Pro through Codex; in the Claude and Codex CLIs, desktop apps, IDE extensions and the
  JetBrains AI chat.
- Plugin parts: `skills/ai-task/state.py`, `skills/ai-task`, `skills/project-update`
  (`update.py`, `history/`, new `migrations/`), `skills/project-init`, `skills/ai-init`
  templates, `skills/sdlc-*`, `skills/ai-status`, `skills/usage-report`, `hooks/`
  (`lib/ai-hook-common.sh`, `ai-git-guard`, `ai-path-guard`, `ai-scope-guard`,
  `context-guard`, a session-start hook, the model gates), `profiles/`, `CLAUDE.snippet.md`, `AGENTS.snippet.md`, `scripts/render-*`,
  `install.sh`, `agents/`, `tests/`, `docs/`.
- Every repository already initialised with `/ai-init` or `/project-init`, and
  repositories shaped by other tools.

## Constraints

- Works on all five subscriptions. Anything that costs tokens is off or serial by default
  on Pro and Plus; nothing may require a second subscription.
- New checks are deterministic (Python standard library, `git`, the project's own
  tools). A new check should replace a model step, not add one.
- Implementation stays in the main session; five or more parallel agents never run on
  `opus`; `xhigh` only where the profile already allows it.
- Plugin-owned files in a project change only through the skills, never by hand.
- `project-update` keeps its guarantees: dry run first, untouched files replaced, edited
  files three-way merged, real conflicts never overwritten, a task in flight is asked
  about first. A task in flight survives a schema migration with defaults.
- Adoption never touches application code, runs on a clean tree, never commits, never
  deletes without approval, and is idempotent.
- No agent commits, merges or deploys. Git guard **rules** stay as they are: performance
  work may change only how a rule is evaluated, never which calls it denies, and
  `tests/test-guard-characterization.sh` must stay byte-identical across the change.
- Both runtimes stay at parity and the existing test suites stay green; every migration
  and every foreign structure gets a fixture project.
- This is several tasks, not one: each work package goes through `/sdlc-spec` →
  `/sdlc-plan` → `/ai-task` on its own, in the dependency order of the plan.

## Out of scope

- AI-DLC's ideation and operation phases, its 33 stages, mob rituals, a gate after every
  stage, and a 99-event audit taxonomy.
- Full mutation testing; AI-share-of-code targets; agent fleets.
- Gemini CLI, Junie and Cursor as full runtimes (agents, hooks, state commands). They get
  a rendered stub and the prose questionnaire only.
- OS-level sandboxing and network egress control; only the path guard is extended.
- Changing the concrete models or effort levels of the existing tiers.
- Automatic deletion, automatic commits, or migration of application code.
- Rewriting the hooks in a compiled language, shipping per-platform binaries, or a
  resident guard daemon — the remaining per-call floor is interpreter startup and is
  accepted (see `docs/hook-performance.md`).

## Work packages

Each package runs `/sdlc-spec` → `/sdlc-plan` → `/ai-task` on its own; specs are named
`docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp<N>-<slug>.md`.

| WP | Package | Main files | Tier | Depends on | Status |
|---|---|---|---|---|---|
| 1 | Schema version and structural migrations | `skills/project-update/update.py`, new `migrations/`, `history/`, `tools/build-template-history.py`, `tests/test-project-update.sh`, `tests/test-merge-migration.sh` | T3 | — | **done** (PR #15, #16, merged 2026-09-20) — schema version in `.ai/VERSION`, ordered idempotent migrations inside the dry run, template history following renames, the delete gate and `migration.json`; spec and plan under `…-wp1-schema-migrations.md` |
| 2 | Questions file, handoff, event journal, human-turn approval | `skills/ai-task/state.py` (`ask`, `answer`, `questions`, `handoff`, `events.jsonl`, `owner_runtime`, approve outside the agent), `hooks/context-guard.py`, a session-start hook, `skills/ai-task/SKILL.md`, `skills/sdlc-intent` | **T4** (raised from T3, 2026-09-20: the deliverable is an authorization control) | 1 | spec done (`…-wp2-questions-handoff-journal.md`) — intent open questions 1 and 2 settled there; spec concerns 1, 2 and 8 answered by the user on 2026-09-20 |
| 3 | Context diet | `CLAUDE.snippet.md`, `AGENTS.snippet.md`, `skills/ai-init/templates/*.block.md` and `*.minimal.md`, `.ai/AGENTS.md` as a router, `constitution.md` template, byte-budget test, a migration for existing projects | T2–T3 | 1, 2 | not started |
| 4 | Deterministic gates | `risk-tiers.json` (diff budget, scopes), `state.py step-done` diff measurement, new `skills/ai-task/sensors.py`, tier re-scoring, retry rule in `ai-tester`, "test must bite" check | T3 | 1 (can run beside 3) | not started |
| 5 | Runtimes and plans | new `profiles/max20.json`, preferred-runtime and budget tables in every profile, `install.sh` plan detection + confirmation, `fable-gate` / `codex-model-gate` → `runtime-gate`, `state.py handoff --to`, grep test that shared prompts name no model | T3 | 2 | not started |
| 6 | `project-update --adopt` | `update.py --adopt`: detection, mapping table, `migrate` (default) / `coexist`, no-line-lost and no-dangling-reference checks, report, `--cleanup` behind approval; fixtures for Spec Kit, Kiro, Cursor, a large `CLAUDE.md` | T3 (deletion treated as T5 → approval) | 1, 3 | not started |
| 7 | Path guard hardening | `ai-path-guard`: `.claude/`, `.codex/`, hooks and agent files protected during a task; instruction files in `vendor/`, `node_modules/` are data | T2 | — (any time) | **done** (`feat/wp8-wp7-guard-hardening`) — `task_protected_patterns`, armed only while `.ai/state/current.json` is short of `done`, and `dependency_instruction_patterns`, read and write, always on; 9 fixtures, the task-lifecycle cases and 153 new characterization records |
| 8 | Guard hot-path cost | `hooks/lib/ai-hook-common.sh`, `hooks/ai-git-guard.sh`, `hooks/ai-path-guard.sh`, `hooks/ai-scope-guard.sh`, `tests/test-guard-characterization.sh`, `docs/hook-performance.md` | T2 (refactor scope: no behaviour change) | — (any time; land before 7, so the new rules are written against the fast path) | **done** — process-count work and the 721-run characterization suite (`perf/guard-hook-process-count`), then `ai-scope-guard` 15 → 6 processes and 158 → 62 ms with the golden file untouched (`feat/wp8-wp7-guard-hardening`); budget and measurements in `docs/hook-performance.md` |

Before WP4, measure a baseline with `/usage-report` on 5–10 real tasks: tokens per task,
review findings per 100 changed lines, share of tasks with a second `remediate`.

## Decisions taken (2026-09-20, answered by the user)

1. **Max 20x vs Max 5x:** `install.sh` detects the plan, proposes it and waits for a
   confirmation; `--plan max20` skips the question.
2. **Thresholds** (diff budget, retry count, token budget): fixed conservative defaults
   in `risk-tiers.json` and `profiles/*.json` from day one, calibrated later from
   `/usage-report`.
3. **Cross-vendor review:** manual by default — the system writes `handoff.md` and tells
   the user to open the other runtime and resume; a headless launch only behind an
   explicit flag.
4. **No-line-lost check:** normalised lines. Blank lines and bare headings are ignored;
   the rest is compared after normalising whitespace, list markers and case. A rewritten
   line must appear in the "dropped / rewritten because …" list.
5. **Foreign files regenerated after a migrate:** detect and warn in `/ai-status` and
   `project-update`, offer a new `--adopt`; nothing happens by itself.
6. **T2 with all sensors green skips the model review on every plan.** The sensors must
   include the passing test run, and the tier re-scored from the real diff must still be
   T2 or lower — otherwise the review runs. The spec must state what "all green" means
   when a project has no linter or type checker.
7. **Schema version:** a new one-line `.ai/VERSION`; a missing file means version 0.
8. **No provable human turn in a runtime:** approval happens outside the agent — the user
   runs `state.py approve` in their own terminal or fills `[Answer]:` in the file. The
   agent can never approve, in any runtime.

## Open questions

1. Does the current Codex (CLI, IDE, JetBrains ACP) expose a native question picker and a
   session-start hook? Factual; to be checked against the Codex documentation in the
   spec stage. If not, prose and the stub line are the only path there.
2. How is "outside the agent" enforced for `state.py approve` — a TTY check, an
   environment marker set by the hooks, or a token shown only to the user?
