# Plan: WP5 — Runtimes and plans

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp5-runtimes-and-plans.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Tier **T3** (spec header: plugin infrastructure shared by both runtimes and every install; no
payments, auth or customer data; the only project change is a `patch_state` migration). Scope
**feature**. No `ai-security` review. The package would become T4 only if `handoff --to --launch`
were built; it is not (OQ2).

All seven open questions were settled with the user on 2026-09-21, and flagged concerns 4–7 were
accepted the same day. The answers that shape the work, repeated so no reviewer re-opens them:
**max20 keeps `direct_mode.max_tier: T2`** (OQ1), **no headless launch — the command is printed**
(OQ2), **no guard file changes; the path-guard rule for `runtime-gate.py` is a separate task** (OQ3),
**runtime-gate and the statusline wrapper on every Claude plan** (OQ4), **`data.tty` on
`runtime_handoff`** (OQ5), **`by_workflow: {"refactoring": "codex"}` on Claude profiles, `{}` on
Codex** (OQ6), and **Codex's own `max_concurrent_threads_per_session` stays** (concern 1).

Twelve steps, twelve commits. Each step names the only files it may touch; anything else is
`SCOPE_CHANGE_REQUIRED` and an amendment to this plan. Step tests run the suites the step names;
`bash tests/run-all.sh` runs **once**, at step 12. There is no e2e suite (`e2e_command: none`) — the
install dry runs inside `run-all.sh` stand in for it.

Verified before planning (2026-09-21):

- Nothing in `skills/`, `hooks/`, `scripts/` or `install.sh` reads `review_model`, `model_tiers` or
  `codex_model` — the `risk-tiers.json` sweep changes prose that models read, not code.
- Readers of `agents/<name>.md` by path: `install.sh:512` (the install loop), `install.sh:637` (the
  audit — installed names, unaffected), `scripts/render-codex-agents.py:94` via each Codex role's
  `source` (`profiles/codex-*.json`, `"ai-reviewer.md"` …), `tests/test-merge-migration.sh:77`,
  `tests/test-install-dry-run.sh:88` (installed names, unaffected). Twelve plain `.md` files are
  renamed; `ai-expert` and `architect` are `.md.tmpl` already.
- The gate names also appear in `.pylintrc:25`, `settings.fable.json`, `codex/hooks.json`,
  `install.sh:304-312, 614-626, 848, 925-929`, `tests/run-all.sh`, `skills/ai-status/SKILL.md`,
  `instructions/routing.md`, `hooks/ai-path-guard-defaults.json:36` (frozen — the shim keeps it
  valid) and seven files under `docs/`.
- `state.py` exit codes in use: 1, 2, 4, 5, 6; 7 is free. `MUTATING_COMMANDS` (`state.py:147`) and
  `claim_runtime` (`:358`) are where the pending-handoff refusal hooks in.

## Files that change

### New

| Path | Why |
|---|---|
| `scripts/resolve-profile.py` | R1/I1: the single resolver — `inherits`, plan/label/fable overrides, `--print settings\|agentic`; stdlib |
| `profiles/max20.json` | R1: `claude_agentic` only, `inherits: "max"`, the max20 budgets |
| `hooks/runtime-gate.py` | R5, R7–R9, R19/I3, I6: one gate for both runtimes |
| `settings.gate.json` | I6: renamed from `settings.fable.json`, merged on every Claude install |
| `skills/project-update/migrations/0005_runtimes_and_plans.py` | R17/I10 |
| `tests/test-profiles.sh` | R1, R2, R16 (tier ↔ Codex role agreement) |
| `tests/test-runtime-gate.sh` | R5 (new parts), R7, R8, R9, R19 |
| `tests/test-shared-prompts-model-free.sh` | R15/I8 |
| `tests/fixtures/project-update/schema-v4/` | R17: a task in flight at schema 4 |
| `tests/fixtures/project-update/` conflict fixture for `review_model` | R21 |

### Renamed

| Path | Why |
|---|---|
| `agents/{Explore,ai-context,ai-discovery,ai-implementer,ai-indexer,ai-planner,ai-release,ai-reviewer,ai-risk,ai-security,ai-tester,log-reader}.md` → `.md.tmpl` | R16: frontmatter `model: {{<TIER>_MODEL}}`, `effort: {{<TIER>_EFFORT}}` |
| `settings.fable.json` → `settings.gate.json` | I6 |

### Edited

| Path | What changes |
|---|---|
| `profiles/{pro,max,codex-plus,codex-pro}.json` | R1, R2: the `claude_agentic` object; Codex roles' `source` → `.md.tmpl`; `ai-reviewer-balanced` role (R20) |
| `install.sh` | R3, R4, R16, R18, I5, I6: `PROFILE_NAME` beside `TIER`, `organizationRateLimitTier`, propose/confirm, strip `claude_agentic`, write `profile.json`, `RENDER_*_MODEL/_EFFORT` from `tiers`, render every agent template, register runtime-gate on every install and remove old gate entries, install the shims |
| `scripts/render-codex-agents.py` | R16, R20: read `.md.tmpl`, strip placeholders from the body it keeps |
| `hooks/fable-gate.py`, `hooks/codex-model-gate.py` | R5: six-line `os.execv` shims |
| `codex/hooks.json` | I6: commands → `runtime-gate.py`, plus `SubagentStart`/`SubagentStop` |
| `.pylintrc` | the standalone-hook note names `runtime-gate.py` |
| `instructions/routing.md` | R15, R16: placeholders only |
| `skills/ai-task/state.py` | R10–R13/I4: `profile`, `handoff --to`, exit 7, `cross_vendor_review`, `quick` cap, advisory line, `apply_defaults` |
| `skills/ai-task/SKILL.md` | §0 resume after a handoff, the T2 review on BALANCED (`ai-reviewer-balanced` on Codex), tier names instead of models |
| `skills/usage-report/usage-report.py`, `skills/usage-report/SKILL.md` | R14/I9 |
| `skills/ai-status/SKILL.md` | gate/quota/preferred runtime from `runtime-gate.py status` and `state.py profile`; no model table |
| `skills/project-update/update.py` | R21: one conflict hint |
| `skills/ai-init/templates/**`, `skills/project-init/templates/**`, `skills/sdlc-spec/SKILL.md`, `skills/project-init/SKILL.md`, agent bodies | R15: the model-name sweep |
| `skills/ai-init/templates/.ai/VERSION` | R17: 4 → 5 |
| `tools/build-template-history.py` output | template history rebuilt after the template sweep (WP1 contract) |
| `tests/run-all.sh` | the three new suites |
| `tests/test-install-dry-run.sh`, `test-codex-install.sh`, `test-codex-agent-render.sh`, `test-merge-migration.sh`, `test-ai-task-state.sh`, `test-usage-report.sh`, `test-project-update.sh`, `test-instruction-budget.sh` | additive assertions; `test-merge-migration.sh:77` loops over the installed agents instead of the source `.md` files |
| `docs/hooks.md`, `architecture.md`, `getting-started.md`, `agents.md`, `hook-performance.md`, `README.md` | the gate, the plans, `handoff --to`, budgets |
| `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` | row 5 marked done at step 12 |

### Untouched on purpose

`hooks/ai-*.sh`, `hooks/lib/`, `hooks/*-defaults.json` (R6 — the characterization golden stays
byte-identical), `hooks/context-guard.py`, `hooks/cap-large-read.py`, every model id and effort of an
existing tier (R18), Codex's `max_concurrent_threads_per_session`.

## Order of work

| # | Step | Files it may touch | Proves |
|---|---|---|---|
| 1 | **Profiles and the resolver** — `claude_agentic` in the four profiles with the I1 table values, `max20.json`, `resolve-profile.py` (`inherits` deep merge with arrays replaced, `--plan`/`--label`/`--fable` overrides, `--print settings\|agentic`), `test-profiles.sh` | `profiles/*.json`, `scripts/resolve-profile.py`, `tests/test-profiles.sh`, `tests/run-all.sh` | R1, R2 |
| 2 | **Install: plans and `profile.json`** — `PROFILE_NAME` (pro\|max\|max20) beside the untouched `TIER`, `--plan max20`, `organizationRateLimitTier` detection, tty propose/confirm (Enter accepts; an earlier `profile.json` is the default), non-tty prints the detection on stderr, `claude_agentic` stripped before the jq merge, `profile.json` written for both runtimes and listed by `--dry-run`, the I5 dry-run header | `install.sh`, `tests/test-install-dry-run.sh`, `tests/test-codex-install.sh`, fixture `.claude.json` files under `tests/fixtures/` | R3, R4, R18 (settings half) |
| 3 | **Agent templates** *(broadest)* — the twelve renames with tier placeholders, `RENDER_<TIER>_MODEL/_EFFORT` exported from the resolved `tiers`, `install.sh:512` renders every `*.md.tmpl` into `<name>.md`, `render-codex-agents.py` reads `.md.tmpl`, Codex roles' `source` updated, `ai-reviewer-balanced` in both Codex profiles, `routing.md` placeholders, `test-merge-migration.sh:77` pointed at the rendered agents | `agents/*.md*`, `install.sh`, `scripts/render-codex-agents.py`, `profiles/codex-*.json`, `instructions/routing.md`, `tests/test-install-dry-run.sh`, `tests/test-codex-agent-render.sh`, `tests/test-merge-migration.sh`, `tests/test-profiles.sh`, `tests/test-instruction-budget.sh` | R16, R18, R20 |
| 4 | **Runtime-gate: parity core** ***(riskiest — see Risks)*** — `runtime-gate.py` reproducing both gates' behaviour (Fable→Opus reroute, EXPERT→STRONG rewrite, `status\|clear\|set\|statusline`, TTLs), new env names before old, one-time import of `fable-gate.json`/`codex-model-gate.json`, the two shims. Before writing: re-check the Codex hook facts (`ask` unsupported, `SubagentStart`) against the Codex CLI 0.146 docs and one live `codex` hook run; record the result in the commit message | `hooks/runtime-gate.py`, `hooks/fable-gate.py`, `hooks/codex-model-gate.py`, `tests/test-runtime-gate.sh`, `tests/run-all.sh`, `.pylintrc` | R5 (both old suites **unchanged**), R6 |
| 5 | **Runtime-gate: quota** — statusline ledger on Claude (Fable mark only when `profile.json.fable`), newest-rollout `token_count` on Codex (three newest day dirs, last 64 KB, ≤ once per 60 s), `quota --json`, `stale` | `hooks/runtime-gate.py`, `tests/test-runtime-gate.sh` | R7 |
| 6 | **Runtime-gate: budgets and `model_fallback`** — EXPERT count keyed by task id and `ask` (allow + `additionalContext` on Codex and under `AI_UNATTENDED=1`), the `SubagentStart`/`SubagentStop` running-agent ledger with `_AGENT_TTL`, the fan-out `ask`, `model_fallback` through `state.py --root R event` with a 3 s timeout, fail-open everywhere | `hooks/runtime-gate.py`, `tests/test-runtime-gate.sh` | R8, R9, R19 |
| 7 | **Registration** — `settings.fable.json` → `settings.gate.json` (`SubagentStart`/`SubagentStop` added), merged on every Claude install with its Fable branch driven by `profile.json.fable`; every existing `fable-gate` / `codex-model-gate` entry in `settings.json` and `hooks.json` **replaced**, not left beside the new one; `statusline_gate` writes `runtime-gate.py statusline`; `codex/hooks.json` commands renamed; install summary text (`install.sh:925-929`). Measure one PreToolUse:Agent call (OQ4 cost) and record it | `settings.gate.json`, `settings.fable.json`, `codex/hooks.json`, `install.sh`, `tests/test-install-dry-run.sh`, `tests/test-codex-install.sh`, `tests/test-dual-runtime-install.sh` | R4 (gate half), I6 |
| 8 | **`state.py`** — `profile` (read-only, `--tier` prints this runtime's id), `handoff --to [--for] [--why]` with the three refusals, `pending_to` and exit 7 `RUNTIME_HANDOFF_PENDING` in the `claim_runtime` path, `cross_vendor_review` recorded and closed by `set review_status` under the receiving runtime, `quick` exit 7 `DIRECT_MODE_CAP`, the advisory line in `init`/`quick`/`risk` and `handoff.md` (≤ 30 lines), `apply_defaults`; `ai-task/SKILL.md` §0 and the T2-review wording | `skills/ai-task/state.py`, `skills/ai-task/SKILL.md`, `tests/test-ai-task-state.sh` | R10, R11, R12, R13 |
| 9 | **Migration 0005** — `patch_state` defaults, `.ai/VERSION` 4 → 5, the `schema-v4/` fixture, additive assertions | `skills/project-update/migrations/0005_runtimes_and_plans.py`, `skills/ai-init/templates/.ai/VERSION`, `tests/fixtures/project-update/schema-v4/`, `tests/test-project-update.sh` | R17 |
| 10 | **Reports and the hint** — `usage-report.py --task/--budgets`, the `usage-report` and `ai-status` SKILLs, the `update.py` `risk-tiers.json` conflict hint and its fixture | `skills/usage-report/*`, `skills/ai-status/SKILL.md`, `skills/project-update/update.py`, `tests/test-usage-report.sh`, `tests/test-project-update.sh`, `tests/fixtures/project-update/` | R14, R21 |
| 11 | **The model-name sweep** — `test-shared-prompts-model-free.sh` written first and seen red, then every hit in the I8 scope converted by the sweep rules (on `sonnet` → on BALANCED; per-call choice → `$STATE profile --tier …`; `review_model` → tier names; `model_tiers.*` lose `model`/`codex_model`), the `risk-tiers.md` mirror sha refreshed, template history rebuilt | the I8 shared-prompt scope, `tools/build-template-history.py` output, `tests/test-shared-prompts-model-free.sh`, `tests/run-all.sh`, `tests/test-scaffold-idempotency.sh` | R15 |
| 12 | **Docs and close** — the six docs, intent row 5, then `bash tests/run-all.sh` once, to the end; `git diff --stat main -- hooks/ai-*.sh hooks/lib hooks/*-defaults.json tests/fixtures/guard-characterization*` empty | `docs/*.md`, `README.md`, `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` | R6, all |

Order rationale: tables before readers (1 before 2, 3, 6, 8); the installer's plan plumbing before
the templates it renders (2 before 3); the gate's **parity** before any new gate behaviour (4 before
5, 6), so the two unchanged old suites prove the rename on its own; registration (7) only after the
gate is complete, so no install ever ships a half gate on a plan that never had one; state and
migration after the code that defines the final state shape (8 before 9 — migrating twice
otherwise); the sweep (11) late, because steps 3 and 8 rewrite much of the same prose and the grep
test is the final word on it.

## Risks

**Step 4 is the riskiest.** It replaces two hooks that sit on every Agent launch, one of which
(`fable-gate`) the installed `~/.claude/CLAUDE.md` tells the user to run by name. It was split out
of the spec's single gate step (parity 4 / quota 5 / budgets 6 / registration 7) so that a
regression shows up against the two old suites before anything new is layered on, and it cannot
move earlier than step 1 only because the Fable branch reads `profile.json`. Mitigations: the old
suites run **unchanged** through the shims; the gate always exits 0 and never denies; any exception
falls open; `AI_RUNTIME_GATE=off` (and the old names) disable it.

**Step 3 is the broadest** — every agent every user installs is re-rendered. R18 is its guard: the
existing frontmatter assertions for every `--plan` and `--codex-plan` stay, and the step adds one
that diffs the rendered frontmatter of all fourteen agents against today's output captured before
the rename.

| What could break | How it is noticed |
|---|---|
| A settings merge leaks `claude_agentic` into `settings.json` | step 2: `test-install-dry-run.sh` asserts `jq 'has("claude_agentic")'` is false on every plan's rendered snippet |
| Two gates fire after an upgrade (old `fable-gate.py` entry + new `runtime-gate.py` entry → the shim runs the gate twice, double-counting agents) | step 7 replaces old entries instead of appending; `test-install-dry-run.sh` installs over a fixture `settings.json` holding the old entries and asserts exactly one gate command per event; same for `hooks.json` in `test-codex-install.sh` |
| A missed reader of `agents/<name>.md` (concern 5) | fails loudly with file-not-found; step 3 greps `agents/.*\.md\b` over `install.sh scripts tests skills` before committing; `test-codex-agent-render.sh` renders ≥ 17 agents |
| The rendered model of an agent changes (R18) | the frontmatter diff in step 3; `test-merge-migration.sh:84-85` and `test-install-dry-run.sh:104-114` unchanged |
| runtime-gate adds latency on plans that never had a gate (OQ4) | step 7 times one PreToolUse:Agent call; `docs/hook-performance.md` records it; a regression beyond the existing gate's cost is a stop-and-ask |
| Codex hook facts are wrong (concern 6) | step 4 re-checks them first; R8/R19 degrade to allow + explain on Codex by construction, so a wrong fact costs a missing question, not a block |
| The running-agent count drifts (concern 4) | TTL 30 min, `runtime-gate.py clear`; the suite covers a lost `SubagentStop` expiring |
| An old statusline line or hand-written settings entry still calls `fable-gate.py` | the shim execs runtime-gate with argv and stdin intact; `test-fable-gate.sh` exercises exactly those entry points |
| The pending-handoff refusal blocks a legitimate owner | exit 7 only for a runtime ≠ `pending_to`; `handoff --to <self>` takes it back explicitly; pending questions never block; `test-ai-task-state.sh` covers each |
| A task in flight meets schema 5 | `apply_defaults` in memory plus 0005 on disk; the `schema-v4/` fixture asserts a mutating command succeeds before and after migrating |
| The sweep changes a template a project has edited | the three-way walk keeps edits; a `risk-tiers.json` conflict prints the R21 hint; nothing in code reads `review_model` (verified) |
| The detection proposes the wrong plan | it is only proposed on a tty and confirmed; `--plan` skips it; non-tty prints it on stderr; tty path is a manual check below |
| `pylint` on 3.11–3.13 flags new Python | `check=` on subprocess, context-managed handles, no unused parameters; CI runs it |

**Manual checks** (not automatable, done once before the PR): the tty propose/confirm path of
`install.sh` with and without an earlier `profile.json`; one live `codex` session showing the gate's
`additionalContext` on a second concurrent launch under `codex-plus`; a real `handoff --to codex`
and back on a scratch project.

## Proof (tests)

| R | Proof |
|---|---|
| R1 | `test-profiles.sh`: every profile has `claude_agentic` with the three keys; `max20.json` holds only it; resolved(max20) minus `claude_agentic` `jq -S` equals `max.json` minus it |
| R2 | `test-profiles.sh`: pro/team-pro/codex-plus `1 / serial`; `max_parallel_on_strong ≤ 4` everywhere; Codex `max_parallel_agents ≤ max_concurrent_threads_per_session` |
| R3 | `test-install-dry-run.sh`: `--plan max20` label and snippet equal to `--plan max`'s; fixture `.claude.json` with `default_claude_max_20x` → max20, `max_5x` → max, non-tty detection on stderr; tty path manual |
| R4 | `test-install-dry-run.sh`, `test-codex-install.sh`: `profile.json` printed by `--dry-run`, nothing written; no `claude_agentic` in `settings.json` or `config.toml` |
| R5 | `test-fable-gate.sh`, `test-codex-model-gate.sh` **byte-unchanged** and green; `test-runtime-gate.sh` for new env names and the one-time state import |
| R6 | `test-guard-characterization.sh` green; the `git diff --stat` at step 12 empty |
| R7 | `test-runtime-gate.sh`: a statusline payload and a rollout fixture each give the `quota --json` shape; an old `seen_at` and a past `resets_at` give `stale` |
| R8 | `test-runtime-gate.sh`: Claude `ask` with reason; Codex allow + `additionalContext`; `AI_UNATTENDED=1` allow on both; never `deny` |
| R9 | `test-runtime-gate.sh`: fixture project with a task → one `model_fallback` line, actor `hook`; no task → none; broken `state.py` → allow |
| R10 | `test-ai-task-state.sh`: the three state fields, the journal line with `data.tty`, `handoff.md` line, the printed command not run; each refusal exits 2; exit 7 from the old owner; first command from `pending_to` clears with no second event |
| R11 | `test-ai-task-state.sh`: T4 `--for review` record, `done` with `by_runtime`; T2 allowed and noted |
| R12 | `test-ai-task-state.sh` with fake `CLAUDE_CONFIG_DIR`/`CODEX_HOME`: the line appears only when the other runtime is installed and named; `handoff.md` ≤ 30 lines |
| R13 | `test-ai-task-state.sh`: `quick --tier T3` under solo on a pro fixture exits 7 `DIRECT_MODE_CAP`; no profile file → exit 0 |
| R14 | `test-usage-report.sh`: `--task` prints tier, window, per-provider totals and `%`; `--budgets` prints the tables; the journal untouched |
| R15 | `test-shared-prompts-model-free.sh` green; every `--plan` dry-run block model-free and `routing.md` without `{{` |
| R16 | `test-profiles.sh` (template tier = Codex role tier), `test-install-dry-run.sh` (installed `model:` = resolved `tiers[tier].model` per plan), `test-instruction-budget.sh` |
| R17 | `test-project-update.sh`: `schema-v4/` reaches 5, second run `0 automatic`, `--check` 1 then 0, migration text names neither runtime |
| R18 | existing assertions in `test-install-dry-run.sh`, `test-codex-agent-render.sh`, `test-merge-migration.sh`; the step-3 frontmatter diff |
| R19 | `test-runtime-gate.sh`: start/stop pairs, `ask` at the fan-out and on-strong limits, a lost stop expiring, allow + explain on Codex |
| R20 | `test-codex-agent-render.sh`: `ai-reviewer-balanced.toml` read-only on BALANCED in both Codex profiles |
| R21 | `test-project-update.sh`: the edited-`review_model` fixture prints the one hint; no other output changes |

`verify_command` for this repository is `bash tests/run-all.sh`; `step_test_command` is
`bash tests/<suite>.sh` for the suites the step names; `e2e_command: none`.

## Rollback

Every step is one commit and nothing runs outside a developer's checkout until a user reinstalls,
so `git revert` of the range restores the previous behaviour. Three things need saying:

- **An install made from WP5** has `runtime-gate.py`, the two shims, `settings.gate.json` entries
  and `claude-agentic/profile.json`. Re-running the previous `install.sh` puts the old gates back
  over the shims and re-registers them; the gate entries it does not know are left in
  `settings.json`, pointing at a file that no longer changes. The one-line clean-up is removing the
  `runtime-gate` entries (the old installer's own strip keys on `fable-gate`); `profile.json` is
  inert without WP5 code. No escape hatch needs a revert: `AI_RUNTIME_GATE=off` disables the gate
  outright.
- **A project migrated to schema 5** keeps `handoff.pending_to`, `handoff.pending_since` and
  `cross_vendor_review`; they are additive and ignored by schema-4 code, and `.ai/VERSION` reading
  `5` is reported by `/project-update --check` as "ahead" for a human to resolve. A task left with
  `pending_to` set simply stops being refused under the old code.
- **A stuck budget needs no revert.** Budgets live in `profile.json`; `expert.without_asking: true`,
  a larger `fan_out`, or a higher `direct_mode.max_tier` is one edit there, and deleting the file
  turns every budget check into a no-op.
