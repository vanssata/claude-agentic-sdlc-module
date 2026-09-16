## 1. Goal

Extend the existing `claude-agentic` repository into one backward-compatible dual-runtime module that auto-detects Claude Code and/or Codex, installs only the applicable integration, routes routine model workload to Sonnet/Terra, keeps Opus/Sol for strong reasoning, escalates only to Fable 5.1/Astra, and exposes the same complete `.ai` engineering pipeline in both runtimes.

## 2. Approach

Keep `.ai/**`, the pipeline state machine, risk tiers, workflow contracts, and most skill bodies provider-neutral, then add thin Claude and Codex adapters for configuration, agent format, hooks, and global instructions. Claude keeps its proven Haiku/Sonnet → Opus → Fable routing in `profiles/pro.json`, `profiles/max.json`, and `CLAUDE.snippet.md`; Codex gets Terra → Sol → Astra through a new profile, generated TOML custom agents, a managed `AGENTS.md` block, and Codex hook registration. This follows Codex's documented custom-agent precedence and hook model: custom agents can pin model/effort, project or skill instructions can request delegation, and `Agent`, `Bash`, and `apply_patch` can be observed by hooks ([Subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents), [Hooks](https://developers.openai.com/codex/hooks)).

The installer remains the canonical host setup path because Codex plugins can package the shared skills, but host-level custom agents and the user's default `model` still require deliberate local configuration. Auto-detection checks each executable/config home independently; `--target auto|claude|codex|both` remains available as an override, and the existing `--plan` and `--fable` Claude behavior stays compatible.

## 3. File Changes

### New files

- **Create** `.codex-plugin/plugin.json` — valid Codex plugin manifest exposing the shared skills with the repository name retained for Git/history continuity.
- **Create** `AGENTS.snippet.md` — managed global Codex instructions containing the Terra/Sol/Astra dispatch matrix, escalation triggers, fan-out limits, context hygiene, and the full `.ai` pipeline contract.
- **Create** `profiles/codex.json` — machine-readable Codex profile: main session `gpt-5.6-sol` at high effort, default subagents `gpt-5.6-terra` at medium, STRONG `gpt-5.6-sol` high, EXPERT `gpt-6-astra` xhigh, and a bounded concurrency default.
- **Create** `codex/hooks.json` — Codex lifecycle registration for the shared guards plus the Codex EXPERT availability gate; match `Bash`, `apply_patch|Edit|Write`, and `Agent` with Codex-compatible events.
- **Create** `scripts/render-codex-agents.py` — render the existing `agents/*.md` prompt bodies into Codex custom-agent TOML files using `profiles/codex.json`, avoiding duplicated prompt bodies.
- **Create** `scripts/merge-codex-config.py` — atomically update only the managed top-level model/reasoning keys and `[agents]` keys in `~/.codex/config.toml`, preserving comments, unrelated tables, plugin configuration, and a backup.
- **Create** `hooks/codex-model-gate.py` — remember Astra rate-limit/model-unavailable failures from Codex subagents and rewrite later EXPERT launches to Sol until the TTL expires; expose `status`, `clear`, and deterministic test controls.
- **Create** `skills/ai-init/templates/AGENTS.block.md` and `skills/ai-init/templates/AGENTS.minimal.md` — Codex equivalents of the current project instruction templates.
- **Create** `skills/project-init/templates/AGENTS.md` and `skills/project-init/templates/project-config.toml` — Codex project scaffold without Claude-only paths.
- **Create** `skills/usage-report/prices.json` — isolated, dated provider/model price metadata so token parsing is not coupled to hard-coded rates.
- **Create** `tests/test-codex-agent-render.sh` — validate every rendered TOML agent, required fields, model/effort assignments, and read-only sandboxes.
- **Create** `tests/test-codex-install.sh` — exercise Codex-only dry-run/real install, config preservation, backup behavior, managed block idempotency, and Sol default selection.
- **Create** `tests/test-dual-runtime-install.sh` — verify auto-detection and explicit target selection across Claude-only, Codex-only, both, and neither.
- **Create** `tests/test-codex-model-gate.sh` — fixture-driven Astra failure, TTL, rewrite, expiry, status, and fail-open coverage.
- **Create** `tests/test-codex-usage-report.sh` — synthetic Codex rollout fixtures for turn usage, cached tokens, model attribution, project/session grouping, and subagent attribution.
- **Create** `tests/fixtures/codex-hooks/*.json` — representative Codex `Bash`, `apply_patch`, and `Agent` hook payloads, including allowed and denied paths.
- **Create** `docs/sdlc/plans/dual-runtime-agentic-routing.md` — checked-in copy of this approved plan so a later Sonnet, Opus, or Sol session can execute it without reconstructing scope.

### Existing implementation and configuration

- **Modify** `install.sh:1-159,211-398` — split runtime detection/render/install into Claude and Codex branches; add `--target`, `CLAUDE_DIR`, and `CODEX_DIR` test overrides; skip absent runtimes; render/install Codex agents; merge Codex config/hooks; install shared skills/scripts; write the managed `AGENTS.md` block; preserve all current Claude migration and Fable-gate behavior.
- **Modify** `CLAUDE.snippet.md:2-78` — align wording with the shared dual-runtime policy while retaining Claude model names and exact Claude escalation behavior.
- **Modify** `settings.common.json:1-57` and `hooks/ai-git-guard-defaults.json:1-35` / `hooks/ai-path-guard-defaults.json:1-33` — make comments and protected paths provider-aware and cover both `.claude/hooks/ai-*` and `.codex/hooks/ai-*`.
- **Modify** `agents/ai-risk.md:12-18` and `agents/ai-reviewer.md:14-20` — resolve project instructions through `CLAUDE.md` or `AGENTS.md`; keep the rest of the shared role contracts unchanged.
- **Modify** `hooks/lib/ai-hook-common.sh:1-148` — normalize Claude/Codex tool names, locate the active runtime config root, extract paths from Codex `apply_patch` payloads, and emit the common blocking output accepted by both hook runtimes.
- **Modify** `hooks/ai-git-guard.sh:1-35`, `hooks/ai-path-guard.sh:1-37`, and `hooks/ai-scope-guard.sh:1-80` — accept Codex `apply_patch` and unified `Bash` events, use runtime-neutral config discovery, and preserve the existing fail-open contract.
- **Modify** `hooks/cap-large-read.py:1-60` — accept neutral limit environment variables with Claude aliases retained, and document which Codex read-like tool inputs it can enforce.
- **Modify** `hooks/project-scaffold.sh:1-58` — scaffold `.claude/**`, `.codex/**`, or both according to detected/explicit runtimes while creating shared `docs/sdlc/**` only once.
- **Modify** `skills/ai-init/scaffold-ai.sh:1-57` — create/append `CLAUDE.md` and/or `AGENTS.md` without overwriting user content and keep the shared `.ai/**` scaffold idempotent.
- **Modify** `skills/ai-init/templates/.ai/AGENTS.md:1-75`, `skills/ai-init/templates/.ai/agents/manager.md:1-45`, `skills/ai-init/templates/.ai/policies/model-routing.md:1-100`, and `skills/ai-init/templates/.ai/policies/safety.md:1-70` — describe both agent runtimes and the two equivalent model ladders while preserving one source of truth for risk and scope.
- **Modify** `skills/ai-audit/SKILL.md:30-110`, `skills/ai-audit/templates/ai-sdlc-adoption-plan.md:1-75`, and `skills/ai-audit/templates/play-scoring-rubric.md:20-105` — audit either or both provider layouts and instruction files.
- **Modify** `skills/ai-init/SKILL.md:14-166`, `skills/ai-task/SKILL.md:7-201`, `skills/ai-status/SKILL.md:6-75`, and `skills/project-init/SKILL.md:6-37` — replace hard-coded `~/.claude` commands with runtime-resolved installed paths and use provider-neutral spawn/delegation language.
- **Modify** `skills/sdlc-spec/SKILL.md:12-70` and `skills/sdlc-plan/SKILL.md:12-55` — read the active instruction/config layer and store approved plans in the active provider plan directory.
- **Modify** `skills/project-init/templates/CLAUDE.md:1-30`, `skills/project-init/templates/gitignore.snippet:1-5`, `skills/project-init/templates/memory-README.md:1-22`, and `skills/project-init/templates/spec.md:15-25` — keep Claude wording accurate while making shared artifacts aware of the Codex sibling layout.
- **Modify** `skills/usage-report/SKILL.md:1-40` and `skills/usage-report/usage-report.py:1-186` — add `--provider auto|claude|codex|both`, parse Codex `token_count` rollouts and `turn_context` model data, retain Claude message-id deduplication, distinguish main/subagent usage, and report per-provider totals plus an explicitly approximate API-equivalent cost.
- **Modify** `README.md:1-215`, `docs/architecture.md:1-135`, `docs/agents.md:1-85`, `docs/getting-started.md:1-125`, `docs/hooks.md:1-200`, `docs/faq.md:1-115`, and `docs/workflows.md:1-85` — document dual-runtime installation, the two routing ladders, runtime detection/overrides, Codex hook trust, config backups, fallback behavior, and verification.
- **Modify** `tests/test-install-dry-run.sh:1-130`, `tests/test-end-to-end.sh:1-150`, `tests/test-merge-migration.sh:1-125`, `tests/test-scaffold-idempotency.sh:1-105`, `tests/test-ai-git-guard.sh:1-110`, `tests/test-ai-path-guard.sh:1-65`, `tests/test-ai-scope-guard.sh:1-100`, `tests/test-usage-report.sh:1-60`, and `tests/run-all.sh:1-25` — retain Claude regression coverage, add provider-neutral assertions and Codex suites, and run the complete matrix.

## 4. Implementation Steps

### Task 1: Freeze the routing contract and generate Codex agents

1. Add `profiles/codex.json` with the selected routing: Sol/high main session, Terra/medium default subagent, Terra/low for indexing/discovery/log reading, Terra/medium for mechanical implementation/testing/context/release, Sol/high for architecture/review/security and T3/T4 strong planning, Astra/xhigh only for T5, irreversible decisions, a failed STRONG cycle, or a final critical check.
2. Implement `scripts/render-codex-agents.py` to consume `agents/*.md` and `agents/ai-expert.md.tmpl`, strip Claude frontmatter, preserve the shared instruction body, and emit valid TOML with `name`, `description`, `developer_instructions`, model, effort, and `sandbox_mode`.
3. Add dedicated strong Codex variants for risk/planning during rendering so Codex custom-agent precedence cannot pin an escalated call back to Terra; verify this in `tests/test-codex-agent-render.sh`.
4. Add `AGENTS.snippet.md` with named dispatch triggers and the rule that expensive agents never fan out; a broad sweep stays on Terra, while only one Sol/Astra agent answers a given decision.

### Task 2: Add safe dual-runtime installation

1. Refactor `install.sh:21-62` so `--target auto` independently detects `claude` and `codex` executables/config homes, does not ask for a Claude plan during Codex-only setup, and reports an actionable no-runtime result.
2. Preserve the existing Claude branch in `install.sh:64-398` byte-for-behavior: plan detection, Fable choice, backups, migration from `claude-routing`, settings merge, statusline gate, agents, hooks, skills, and managed `CLAUDE.md`.
3. Implement `scripts/merge-codex-config.py` and call it from the Codex branch to atomically set Sol/high and the `[agents]` defaults without changing existing MCP servers, plugins, projects, permissions, comments, or unrelated keys.
4. Install generated agents into `$CODEX_DIR/agents`, shared skills into `$CODEX_DIR/skills`, shared guard scripts into `$CODEX_DIR/hooks`, merge `codex/hooks.json` into `$CODEX_DIR/hooks.json` without duplicate commands, and replace exactly one managed block in `$CODEX_DIR/AGENTS.md`.
5. Make `--dry-run` print separate Claude/Codex sections and guarantee no writes; test Codex-only, Claude-only, both, explicit target overrides, repeated installs, user-edited files, and backups in `tests/test-codex-install.sh` and `tests/test-dual-runtime-install.sh`.

### Task 3: Make guards enforce the same boundaries in both runtimes

1. Extend `hooks/lib/ai-hook-common.sh:18-45` to normalize payloads and extract paths from standard file fields plus Codex patch headers.
2. Register the git/path/scope guards in `codex/hooks.json`; map `apply_patch` to write semantics, keep shell checks on `Bash`, and keep every parse/error path fail-open.
3. Extend protected-config defaults to both runtime directories and run every existing Claude fixture plus new Codex fixtures against the same scripts.
4. Add `hooks/codex-model-gate.py`: on an Astra subagent availability/rate-limit failure, record an expiring state; on the next `PreToolUse:Agent`, rewrite only EXPERT/Astra work to Sol and add visible context explaining the fallback; never downgrade ordinary reasoning failures.
5. Test gate attribution, false positives, malformed input, expiry, manual clear, and repeated launches in `tests/test-codex-model-gate.sh`.

### Task 4: Port the complete pipeline and scaffolds

1. Update `hooks/project-scaffold.sh:1-58` and `skills/ai-init/scaffold-ai.sh:1-57` to accept a runtime set and create one shared `.ai`/SDLC tree plus the applicable `.claude` and/or `.codex` project layers.
2. Add Codex project templates and preserve existing Claude templates; append managed workflow blocks once, never replace an existing `CLAUDE.md`, `AGENTS.md`, config, policy, or project note.
3. Convert hard-coded provider paths in `skills/ai-init/SKILL.md`, `skills/ai-task/SKILL.md`, `skills/ai-status/SKILL.md`, `skills/project-init/SKILL.md`, `skills/sdlc-spec/SKILL.md`, and `skills/sdlc-plan/SKILL.md` into runtime-resolved paths while retaining the same task-state commands and stage gates.
4. Update the shared `.ai` manager/model-routing/safety contracts so either runtime uses the same workflow and reports the actual model tier that ran.
5. Extend scaffold and end-to-end tests to prove both instruction files can coexist, the shared `.ai/state/current.json` still controls scope, and re-running either scaffold produces no content changes.

### Task 5: Add cross-provider workload measurement

1. Split price metadata from parsing into `skills/usage-report/prices.json`, retaining the effective-date notice and “API-equivalent, not subscription bill” label.
2. Refactor `skills/usage-report/usage-report.py:26-182` into Claude and Codex parsers with a common aggregate: Claude keeps response-id deduplication; Codex uses one final `token_count` record per turn, takes model/effort/project from the turn/session context, and identifies subagents from parent-thread metadata.
3. Add `--provider` selection and combined output showing calls/turns, input, cached input, cache write where available, output/reasoning tokens, active days, main-vs-subagent share, model share, and approximate cost.
4. Cover duplicates, malformed lines, missing pricing, model aliases, session prefixes, current project, `--all`, and mixed Claude+Codex totals with synthetic fixtures only.

### Task 6: Package, document, and preserve the execution plan

1. Add `.codex-plugin/plugin.json` with the shared skills directory and no undeclared MCP/app dependency; validate it with the plugin-creator validator.
2. Rewrite `README.md` and `docs/*.md` around the final dual-runtime behavior, including install examples, detection rules, model matrices, hook trust, fallback limits, and the fact that Codex main sessions now default to Sol by the user's choice.
3. Save this approved plan verbatim to `docs/sdlc/plans/dual-runtime-agentic-routing.md` before implementation changes begin, then keep it updated if the implementation scope changes.
4. Run the full suite and summarize the final Claude/Codex install matrix and any platform limitation that remains.

## 5. Acceptance Criteria

1. With only a fake `claude` runtime present, `install.sh --target auto` writes only under the supplied `CLAUDE_DIR`; with only `codex`, it writes only under `CODEX_DIR`; with both, it installs both; with neither, it exits non-zero without creating files.
2. Existing commands `install.sh --plan pro|max --fable auto|yes|no` continue to produce the same Claude session/EXPERT models, fallbacks, Fable gate registration, and migration behavior covered by the pre-existing tests.
3. A Codex install sets `model = "gpt-5.6-sol"` and `model_reasoning_effort = "high"`, enables agents, and sets Terra/medium as the subagent default while preserving every unrelated key and comment in a fixture config.
4. Every rendered Codex custom agent parses as TOML and contains `name`, `description`, and `developer_instructions`; readers/mechanical workers resolve to Terra, strong reviewers/designers to Sol, and the expert to Astra.
5. The routing instructions send broad parallel exploration and mechanical implementation to Terra/Sonnet, use Sol/Opus for complex diagnosis/design/review, and invoke Astra/Fable only for T5, irreversible decisions, an unresolved STRONG result, or a critical final check.
6. An Astra availability/rate-limit fixture causes later EXPERT launches to resolve to Sol until expiry; a normal low-confidence or incorrect answer does not activate the gate.
7. Claude and Codex hook fixtures deny the same protected git/deploy/path/scope operations, allow the same safe operations, and malformed hook input exits successfully without blocking.
8. Codex `apply_patch` outside the current approved step's file list is denied; an in-scope patch is allowed; the same existing Claude scope-guard cases remain unchanged.
9. Running either scaffold twice leaves all file checksums unchanged after the first run, and hand-edited `.ai`, `CLAUDE.md`, `AGENTS.md`, and provider config files survive.
10. The same `ai-task` state transitions, T0-T5 gates, review/security requirements, release report, and final human-approval stop work from both installed skill locations.
11. A synthetic mixed usage report counts each Claude response and Codex turn once, separates main/subagent usage, attributes every known model correctly, and labels unknown-price models without inventing a cost.
12. `bash tests/run-all.sh` exits 0, all Python files compile, all shell files pass `bash -n`, every JSON file parses with `jq`, generated TOML parses with Python `tomllib`, and the Codex plugin validator exits 0.
13. `docs/sdlc/plans/dual-runtime-agentic-routing.md` exists in Git with the approved scope so a new session can execute it directly.

## 6. Verification Steps

1. Run `bash -n install.sh hooks/*.sh hooks/lib/*.sh skills/ai-init/scaffold-ai.sh`.
2. Run `python3 -m py_compile hooks/*.py scripts/*.py skills/ai-task/state.py skills/usage-report/usage-report.py`.
3. Run `find . -name '*.json' -not -path './.git/*' -print0 | xargs -0 -n1 jq empty`.
4. Render Codex agents into a temporary directory and load each with `python3 -c 'import glob,tomllib; [tomllib.load(open(p,"rb")) for p in glob.glob(...)]'`.
5. Run `bash tests/run-all.sh`; the runner must include all old and new suites.
6. Run four scratch dry-runs with isolated `CLAUDE_DIR`, `CODEX_DIR`, and `PATH`: Claude only, Codex only, both, neither. Compare directory trees and assert no writes during `--dry-run`.
7. Run a real scratch dual install twice, compare checksums after the first/second runs, then verify custom user config content and managed blocks remain exactly once.
8. Run `python3 /home/vanssa/.codex/skills/.system/plugin-creator/scripts/validate_plugin.py .`.
9. Manual post-install check in fresh sessions: Claude `/skills` and `/hooks`; Codex `/hooks`, agent list, and an explicit three-agent smoke prompt. Confirm Terra handles exploration, Sol handles review, and a forced gate fixture routes Astra to Sol with a visible reason.
10. Run the usage report against synthetic fixtures first, then locally with `--provider both`; verify totals reconcile to the per-model rows and no conversation content is printed.

## 7. Risks & Mitigations

- **Codex TOML corruption or loss of user settings.** `scripts/merge-codex-config.py` will edit only an explicit managed key set, parse before and after, write atomically, keep a backup, and receive fixtures with comments, nested MCP/plugin/project tables, and pre-existing `[agents]`.
- **Custom-agent precedence silently defeats escalation.** Codex agent rendering will use separate strong/expert profiles where needed, and tests will assert the effective model of every role rather than only checking that a model string exists.
- **Claude and Codex hook payloads diverge.** The common parser will normalize provider-specific tool names/fields, fixtures will cover both schemas, and all unexpected formats retain the current fail-open behavior.
- **Two instruction files drift into conflicting policies.** `CLAUDE.snippet.md` and `AGENTS.snippet.md` will share the same tier names, triggers, risk gates, and pipeline sequence; tests will assert the key trigger phrases/model mappings in both.
- **Changing the user's current Codex Astra default is surprising.** This is an explicit accepted requirement: dry-run will show the exact Sol/high change, the installer will back up `config.toml`, and `--target claude` can leave Codex untouched.
- **Astra/Fable availability detection mistakes task failure for capacity failure.** Gates will trigger only on explicit rate-limit, overload, or model-unavailable signals, use a short TTL, expose status/clear commands, and never activate on ordinary reasoning uncertainty.
- **Provider-specific project files create duplicate state or policy.** Both adapters will point at one `.ai/state/current.json` and one `.ai/policies/**` tree; only presentation/config layers are duplicated.
- **Approximate prices become stale.** Prices move to dated data, unknown models remain unpriced, and every report clearly distinguishes measured tokens from approximate API-equivalent cost.