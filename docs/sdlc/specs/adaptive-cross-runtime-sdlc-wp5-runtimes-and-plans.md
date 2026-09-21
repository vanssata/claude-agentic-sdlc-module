# Spec: WP5 — Runtimes and plans

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work-package table, row 5)

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Depends on **WP2** (`owner_runtime`, `resume_point`, `handoff.md`, the journal with
`runtime_handoff` and `model_fallback` already in its vocabulary, human-turn approval — PR #22).
Consumes **WP3** I11 (`instructions/routing.md` is the one rendered file still naming models; WP5
converts it and owns the repo-wide grep — PR #23) and **WP4** Q6 (per-plan token budgets were left
to WP5; profiles were untouched — PR #24). **WP6** is untouched.

Recommended tier: **T3**, as in the intent's table — plugin infrastructure shared by both runtimes
and every install; no payments, auth or customer data; the only project change is a `patch_state`
migration. It becomes **T4** only if a headless launch of the other vendor (`handoff --to --launch`)
is built here, because that crosses the human-approval boundary WP2 was raised to T4 for — this spec
defers it (OQ2, settled). No EXPERT trigger fired; all six open questions were answered by the user
on 2026-09-21.

Outcome labels used below: **RP1** owner runtime and `runtime_handoff` · **RP2** preferred runtime
per kind of task, and the ≥ 90 % quota rule · **RP3** T4+ reviewed by the other vendor · **RP4**
shared prompts name only tiers · **RP5** `max20` inherits `max`, budgets only; Plus/Pro the same;
Pro/Plus serial · **QC7** token budget per task/tier/plan in `/usage-report` · **D1–D3** the
intent's decisions 1–3.

## Requirements

| # | Requirement (testable) | Satisfies | Proof |
|---|---|---|---|
| R1 | Every file in `profiles/` carries one top-level `claude_agentic` object (I1) with `tiers`, `budgets`, `preferred_runtime`. `profiles/max20.json` holds only `claude_agentic` with `inherits: "max"`. `scripts/resolve-profile.py` resolves inheritance; resolved(max20) minus `claude_agentic` is canonically equal to `max.json` minus `claude_agentic`. | RP5, D2 | new `tests/test-profiles.sh` |
| R2 | `budgets.fan_out` is `max_parallel_agents: 1, serial: true` on pro, team-pro and codex-plus; `max_parallel_on_strong ≤ 4` on every profile; on Codex `max_parallel_agents ≤ agents.max_concurrent_threads_per_session`. | RP5, "five or more never on opus" | `test-profiles.sh` |
| R3 | `install.sh --plan max20` selects `profiles/max20.json`, label `Max 20x`, and its settings snippet equals `--plan max`'s. Detection reads `oauthAccount.organizationRateLimitTier` (`*max_20x*` → max20, `*max_5x*`/other max → max) beside today's `organizationType`/seat logic. On a tty without `--plan` the detected plan is **proposed and confirmed** (Enter accepts; a plan recorded in an earlier `profile.json` is the proposed default); `--plan`/`--codex-plan` skip every question; non-tty proceeds with the detection and prints it on stderr. | D1 | `tests/test-install-dry-run.sh` (non-tty and fixture `.claude.json` cases); tty path in the plan's manual checks |
| R4 | A Claude or Codex install writes `<home>/claude-agentic/profile.json` (I2); `--dry-run` prints it and writes nothing. `claude_agentic` never reaches `settings.json` or `config.toml`. | RP2, RP5 | `test-install-dry-run.sh`, `tests/test-codex-install.sh` |
| R5 | `hooks/runtime-gate.py` replaces `fable-gate.py` and `codex-model-gate.py`, which become exec shims. `tests/test-fable-gate.sh` and `tests/test-codex-model-gate.sh` pass **unchanged** against the shims; old env names and `status\|clear\|set\|statusline` keep working; an old state file is imported once. | RP2, parity | the two suites unchanged + new `tests/test-runtime-gate.sh` |
| R6 | `tests/test-guard-characterization.sh`'s golden file is byte-identical; WP5 modifies none of `hooks/ai-*.sh`, `hooks/lib/`, `hooks/*-defaults.json`. | constraint (guard rules frozen) | suite green; `git diff --stat` of the package |
| R7 | `runtime-gate.py quota --json` returns `{runtime, weekly_pct, five_hour_pct, resets_at, seen_at, source, stale}` — on Claude from the statusline wrapper (installed on every Claude plan), on Codex from the newest rollout's `token_count.rate_limits`. `stale` when older than 24 h or past `resets_at`. | RP2 | `test-runtime-gate.sh` with a statusline payload and a rollout fixture |
| R8 | With `budgets.expert.without_asking=false`, or above `max_per_task`, a PreToolUse:Agent launch of an EXPERT-tier agent returns `permissionDecision: "ask"` with the reason. Never a deny. Codex parses but does not support `ask` (only allow/deny), so on Codex the same condition allows and explains in `additionalContext`; so does `AI_UNATTENDED=1` on either runtime. | RP5 ("whether EXPERT runs without asking") | `test-runtime-gate.sh`, one case per runtime |
| R9 | When the gate rewrites a launch (Fable→Opus on Claude, EXPERT→STRONG on Codex) and `payload.cwd` is inside a project with a task in flight, exactly one `model_fallback{agent,from,to,reason}` line (actor `hook`) is journaled through `state.py event`; no task → no line; any failure → fail-open. | WP2 I3 ("emitted from WP5") | `test-runtime-gate.sh` (fixture project) |
| R10 | `state.py handoff --to <rt>` (I4) sets `owner_runtime`, `resume_point.runtime`, `handoff.pending_to`; journals `runtime_handoff{via: manual\|review}` with `data.tty` (OQ5); rewrites `handoff.md` with a `Handed to <rt>` line and prints the resume instruction (and the headless command, **not run**). Refuses: `--to` = owner, a closed task, a target whose home has no `skills/ai-task/state.py` (exit 2). A later mutating command from a runtime ≠ `pending_to` exits **7** `RUNTIME_HANDOFF_PENDING`; the first one from `pending_to` clears it with no second event. Pending questions do not block a handoff. | RP1, D3 | `tests/test-ai-task-state.sh` (amended) |
| R11 | `handoff --to X --for review` at tier ≥ `preferred_runtime.cross_vendor_review_from` (default T4) records `cross_vendor_review{from,to,tier,requested_at,status:"requested"}`; `set review_status …` run under runtime `to` marks it `done` with `by_runtime`. Below that tier it is allowed and noted. | RP3, D3 | `test-ai-task-state.sh` |
| R12 | `state.py init`/`quick`/`risk` print one advisory line `preferred runtime: <rt> (<reason>)` — only when the other runtime is installed and the table or the quota rule names it; `handoff.md` carries the same line (still ≤ 30 lines). Nothing moves automatically. | RP2, D3 | `test-ai-task-state.sh` with a fake `CLAUDE_CONFIG_DIR`/`CODEX_HOME` holding fixture `profile.json` files |
| R13 | `state.py quick --tier T<n>` exits 7 `DIRECT_MODE_CAP` when `pipeline_profile == solo` and T<n> > `budgets.direct_mode.max_tier`; no profile file → no cap. | RP5 ("how far direct mode reaches") | `test-ai-task-state.sh` |
| R14 | `usage-report.py --task <id>` prints the task window's tokens per provider, its final tier, the plan budget of each involved runtime and the percentage used; `--budgets` prints the tables. Read-only; budgets are reported, never enforced. | QC7, D2 | `tests/test-usage-report.sh` (amended) |
| R15 | `tests/test-shared-prompts-model-free.sh`: the I8 patterns find zero hits in the shared-prompt scope; the rendered global block of every `--plan` dry run is model-free, and `routing.md` renders with no `{{` left. | RP4, WP3 R6/I11 | new test + `test-install-dry-run.sh` |
| R16 | `instructions/routing.md` rows use `{{FAST_MODEL}}` … placeholders fed from `claude_agentic.tiers`. Every agent source is `agents/<name>.md.tmpl` with `model: {{<TIER>_MODEL}}` and `effort: {{<TIER>_EFFORT}}`; no agent source names a model. The tier in each template equals that role's `tier` in the Codex profiles, and each installed Claude agent's `model:` equals the resolved profile's `tiers[<tier>].model` for every `--plan`. | RP4, WP3 I11 | `test-profiles.sh`, `test-install-dry-run.sh`, `tests/test-instruction-budget.sh` |
| R17 | Migration `0005_runtimes_and_plans.py` (`patch_state` only) raises `.ai/VERSION` 4 → 5; a v4 fixture with a task in flight migrates with defaults; the migration names neither runtime. | constraint (task in flight survives) | `tests/test-project-update.sh` (fixture `schema-v4/`) |
| R18 | No model id or effort of an existing tier changes: `--plan pro\|team-pro\|team-max\|max` and `--codex-plan plus\|pro` render the same agent frontmatter, TOML and settings values as before. | out of scope ("changing models") | existing assertions in `test-install-dry-run.sh`, `test-codex-agent-render.sh` |
| R19 | `runtime-gate` counts running subagents per session: `SubagentStart` adds an entry, `SubagentStop` removes it, an entry older than `AI_RUNTIME_GATE_AGENT_TTL` (default 1800 s) expires. A PreToolUse:Agent launch with `running ≥ budgets.fan_out.max_parallel_agents`, or an agent on the STRONG/EXPERT tier with `running_strong ≥ max_parallel_on_strong`, returns `ask` on Claude and allow + `additionalContext` on Codex. Never a deny; any error fails open. | RP5 (fan-out), "five or more never on opus" | `test-runtime-gate.sh` (start/stop pairs, a lost stop expiring, both runtimes) |
| R20 | Codex renders `ai-reviewer-balanced` (`variant_of: ai-reviewer`, tier BALANCED, read-only) in both Codex profiles; `/ai-task` names it for the T2 review on Codex, as the Claude side already runs the T2 review on BALANCED. | RP4 parity | `tests/test-codex-agent-render.sh` |
| R21 | When the three-way walk leaves a conflict in `.ai/policies/risk-tiers.json` touching `review_model` or `model_tiers`, `project-update` prints one hint naming the tier vocabulary (`FAST/BALANCED/STRONG/EXPERT`) and `state.py profile --tier`. No other behaviour changes. | constraint (project-update guarantees) | `tests/test-project-update.sh` (fixture with an edited `review_model`) |

## Design

### Facts the design rests on

- Claude profiles are `settings.json` fragments: `jq -s '.[0] * .[1]'` with `settings.common.json`
  (`install.sh:230`), then merged into the user's settings (`install.sh:583-609`) — a new top-level
  key would leak into `settings.json`. Codex profiles already carry non-settings keys (`tiers`,
  `labels`, `roles`, `plan`, `plan_rule`) read field by field (`install.sh:766-783`,
  `scripts/render-codex-agents.py:79-82`).
- Plan detection: Claude from `~/.claude.json` `organizationType` + Team seat fields
  (`install.sh:173-199`); Codex from the JWT `chatgpt_plan_type` (`install.sh:717-740`). **The
  account also carries `oauthAccount.organizationRateLimitTier`** (`default_claude_max_20x` on this
  machine) — the 5x/20x marker the installer does not read yet.
- Codex rollouts carry `token_count` events with `rate_limits.primary`/`secondary`
  `{used_percent, window_minutes 300/10080}`; Claude's statusline payload carries the weekly and
  5-hour percentages (which is why `fable-gate.py statusline` wraps it today).
- `fable-gate.py` (PreToolUse/PostToolUse:Agent, StopFailure, `statusline --then`, state
  `~/.claude/state/fable-gate.json`, `CLAUDE_FABLE_GATE*`) is registered only on Max + Fable
  (`install.sh:304-312`, stripped otherwise at 614-626). `codex-model-gate.py`
  (PreToolUse/PostToolUse:Agent, SubagentStop, `CODEX_MODEL_GATE*`, `MODE=rewrite|context`) is
  registered in `codex/hooks.json`. The path guard protects `.codex/hooks/codex-model-gate.py` by
  name (`hooks/ai-path-guard-defaults.json:36`).
- `state.py`: `runtime_handoff` and `model_fallback` are already in `EVENT_TYPES`; `claim_runtime`
  emits `via: resume` (`state.py:358-368`); `cmd_event` is the hook entry; `handoff` takes only
  `--print/--reason`; exit codes 1, 2, 4, 5, 6 are taken.
- Model names in shared prompts today: `skills/ai-task/SKILL.md` (~12 lines),
  `skills/ai-status/SKILL.md` (a table), `sdlc-spec`, `project-init`, the `ai-init` templates
  (`risk-tiers.json` `review_model` and `model_tiers.*.model/codex_model`, `risk-tiers.md`,
  `model-routing.md`, `context-management.md`, five workflows, `manager.md`), ~15 lines in
  `agents/*.md` bodies, `instructions/routing.md:17-27`.
- Hook documentation, checked 2026-09-21: Codex PreToolUse `permissionDecision` supports allow and
  deny only (`ask` is parsed, not supported); both runtimes have `SubagentStart` and `SubagentStop`;
  Claude's PostToolUse fires for a background launch too, so launches are counted from
  `SubagentStart`, not from PostToolUse. Plan step 3 re-checks the Codex fact against
  `developers.openai.com` for Codex CLI 0.146.
- `install.sh` already renders `agents/ai-expert.md.tmpl` and `architect.md.tmpl` through
  `RENDER_*` placeholders (`install.sh:114-120, 334-335`); `scripts/render-codex-agents.py` reads
  only the body and takes the tier from the role (`:84-109`), and supports `variant_of`.
- Drift, verified 2026-09-21: the repo's `hooks/fable-gate.py` is **ahead of** the installed
  `~/.claude/hooks/fable-gate.py` (version-aware `CLAUDE_CODE_SUBAGENT_MODEL` handling), so the
  rename ships newer code and rolls nothing back. `context-guard.py` differs too; WP5 does not touch
  it, but the standing rule applies — dry-run `install.sh` and diff before a real install.

### Components

| Component | Responsibility |
|---|---|
| `profiles/*.json` + new `profiles/max20.json` | Per plan: the runtime settings (unchanged) and the plugin's own tables under one namespaced key `claude_agentic` (I1) |
| `scripts/resolve-profile.py` (new, stdlib) | Resolve `inherits` (deep merge, arrays replaced), apply plan/label/fable overrides, print the `settings` part or the `agentic` part — the single resolver for install.sh, state.py and tests |
| `install.sh` | Detect → propose → confirm the plan; strip `claude_agentic` before the settings merge; write `<home>/claude-agentic/profile.json` for each runtime; export `RENDER_*_MODEL/_EFFORT` for Claude from `tiers` (as the Codex branch already does); register runtime-gate on every install; install the shims |
| `hooks/runtime-gate.py` (new) | One process per Agent event: top-model availability reroute (Fable→Opus; EXPERT→STRONG), the quota ledger, the EXPERT ask/count, the running-agent count and fan-out ask (R19), `model_fallback` emission (I6) |
| `agents/*.md.tmpl` (all twelve renamed from `.md`) | Provider-neutral bodies; frontmatter names a tier placeholder only. Rendered by `install.sh` for Claude and by `render-codex-agents.py` (which learns to read `.md.tmpl`) for Codex |
| `skills/project-update/update.py` | One conflict hint for `risk-tiers.json` (R21); nothing else |
| `hooks/fable-gate.py`, `hooks/codex-model-gate.py` | Six-line shims: `os.execv(runtime-gate.py, argv)` with stdin intact — keeps statusline lines, old settings entries, the installed `CLAUDE.md`'s `fable-gate.py status`, and the protected path name alive |
| `skills/ai-task/state.py` | `profile` reader; `handoff --to`; the pending-handoff refusal; the cross-vendor review record; the direct-mode cap; the advisory line (I4) |
| `skills/usage-report/usage-report.py` | `--task` window + budget %, `--budgets` (I9) |
| `skills/ai-status/SKILL.md` | Reports gate, quota and preferred runtime by running `runtime-gate.py status` and `state.py profile` — no literal model table |
| `instructions/routing.md` | The long-form ladder, placeholders only |
| `skills/project-update/migrations/0005_runtimes_and_plans.py` | `patch_state` defaults for the new state keys (I10) |
| `tests/test-profiles.sh`, `test-runtime-gate.sh`, `test-shared-prompts-model-free.sh` | Proofs for R1–R2/R16, R5–R9, R15; added to `tests/run-all.sh` |

### Data flow

1. **Install.** `PLAN` picks `PROFILE_NAME` (pro | max | max20) while `TIER` stays pro | max, so
   every existing `[ "$TIER" = max ]` branch is untouched. `resolve-profile.py --print settings`
   feeds the existing jq merge; `--print agentic` is installed as
   `$CLAUDE_DIR/claude-agentic/profile.json` (beside `routing.md`) and
   `$CODEX_DIR/claude-agentic/profile.json`.
2. **Runtime reads.** `state.py` finds its home from `__file__`, reads
   `<home>/claude-agentic/profile.json`; the other runtime's home is `$CODEX_HOME|~/.codex` or
   `$CLAUDE_CONFIG_DIR|~/.claude`. There is no environment override: tests point
   `CLAUDE_CONFIG_DIR`/`CODEX_HOME` at a fake home, as the gate suites already do. No file ⇒ every
   budget check is a no-op (a project without a plugin install still works).
3. **Quota.** Claude: `runtime-gate.py statusline` stores `quota{…, source:"statusline"}` in
   `<home>/state/runtime-gate.json`; the Fable "unavailable" mark at ≥ `WEEKLY_PCT` applies only when
   `profile.json.fable` is true. Codex: the newest `rollout-*.jsonl` in the three newest day
   directories, last 64 KB, last `token_count` line; refreshed at most once per 60 s.
4. **Advice.** `preferred = by_workflow[workflow] or default`; if own quota ≥ `quota_pct`, the other
   runtime is installed and its quota is below it or unknown → the other, reason `quota NN% ≥ 90%`.
   Printed by `init/quick/risk`, one line in `handoff.md`. Nothing moves by itself (D3).
5. **Handoff.** `handoff --to codex` from Claude → `owner_runtime=codex`,
   `resume_point.runtime=codex`, `handoff.pending_to=codex`, journal
   `runtime_handoff{from:claude,to:codex,via:manual}`, `handoff.md` rewritten, the resume
   instruction printed. The next mutating command from codex clears `pending_to` silently; one from
   claude exits 7. `handoff --to claude` takes it back explicitly.
6. **Cross-vendor review (T4+).** `--for review` records `cross_vendor_review`; the receiving
   runtime's `/ai-task` §0 resumes at the adversarial-review stage, runs its own reviewer,
   `set review_status …` marks it done, then `handoff --to <from>`. Manual on both hops (D3).
7. **EXPERT ask.** PreToolUse:Agent resolves the agent's tier as the gates do today; EXPERT agents
   come from `tiers.EXPERT.agents`; the count is keyed by the task id in
   `<cwd>/.ai/state/current.json`. The same PreToolUse also checks the running-agent count kept by
   `SubagentStart`/`SubagentStop` (R19).
8. **`model_fallback`.** On a rewrite with a task in flight: `state.py --root R event
   model_fallback --data …` with a 3 s timeout; errors swallowed.
9. **Budgets report.** `usage-report.py --task` turns the SKILL's window approximation into a flag;
   each involved runtime (from `runtime_handoff` lines) contributes its own
   `budgets.tokens.per_task[tier]`.

### Alternatives rejected

**Where the plan tables live**
- *Sibling files* (`profiles/max.agentic.json`): two files per plan drift; Codex profiles already
  hold non-settings keys in one file.
- *Restructure Claude profiles into `{settings, agentic}`*: breaks the `jq -s` merge, every test
  that treats a profile as a fragment, and the settings diff users see.
- *jq-only inheritance inside `install.sh`*: `state.py`, `usage-report` and the tests need the same
  resolution; one stdlib resolver is the single source.

**The gate**
- *Keep both gates and add a third quota hook*: three processes per Agent event and three state
  files; the intent names the merge.
- *A shared `hooks/lib/gate_common.py` behind two thin gates*: hooks are installed and path-guarded
  as individual files; a library module is neither.
- *Rename without shims*: breaks the user's statusline line, settings entries between install runs,
  the installed `CLAUDE.md`'s instruction, and the WP7 protected pattern.

**`handoff --to`**
- *No pending state, rely on WP2's implicit `via: resume` takeover*: the old owner's next command
  silently undoes an explicit decision; the journal shows ping-pong.
- *A lock file the other runtime deletes*: a second writer of state.
- *`--launch` now*: a headless launch of the other vendor is a new trust boundary (an unattended
  agent could spawn it) and would lift the package to T4 — deferred; the command is printed (OQ2).

**The EXPERT budget**
- *Prose only*: not deterministic, and the intent calls it a budget.
- *`deny` above the budget*: blocks legitimate T5 and headless work. `ask` is chosen.

**The quota source**
- *Vendor usage APIs*: network and credentials, not deterministic offline.
- *Claude transcripts*: per-message usage, not the account's quota.
- *Scraping Codex `/status`*: interactive only.

**The grep test's scope**
- *Whole repository minus an allowlist*: `docs/` and `tests/` must name models.
- *The stub only* (WP3's status quo): `SKILL.md` files and templates are read by models on both
  runtimes, so the claim "shared prompts name only tiers" would stay untrue.

### routing.md and the model-name sweep

`routing.md` rows become `| FAST | \`{{FAST_MODEL}}\` / \`{{FAST_EFFORT}}\` | … |`; prose `opus` /
`haiku` becomes STRONG / FAST; `{{EXPERT_ROW}}` stays rendered by `install.sh`. Sweep rules: "on
`sonnet`" → "on BALANCED"; a per-call model choice becomes `$STATE profile --tier BALANCED` (prints
this runtime's concrete id); the `risk-tiers.json` template's `review_model` values become tier
names and `model_tiers.*` lose `model`/`codex_model` (keep `agent`, `effort`, `note`). Template edits
reach projects through the existing three-way walk (WP4 precedent), not through the migration.
Agent sources become `.md.tmpl` with tier placeholders (R16), so the only literal models left in
the tree are in `profiles/`, `install.sh` prose, `docs/`, `tests/` and the frozen history.

## Interfaces

### I1 `claude_agentic` in `profiles/*.json`

```json
"claude_agentic": {
  "inherits": null,
  "plan": "max", "label": "Max",
  "runtime": "claude",
  "tiers": {
    "FAST":     {"model": "haiku",  "effort": "low",    "agents": ["Explore","log-reader","ai-tester","ai-indexer"]},
    "BALANCED": {"model": "sonnet", "effort": "medium", "agents": ["ai-discovery","ai-context","ai-implementer","ai-release","ai-risk","ai-planner"]},
    "STRONG":   {"model": "opus",   "effort": "high",   "agents": ["ai-reviewer","ai-security"]},
    "EXPERT":   {"model": "opus",   "effort": "xhigh",  "agents": ["ai-expert","architect"],
                 "architect_model_with_fable": "fable[1m]"}
  },
  "budgets": {
    "fan_out":     {"max_parallel_agents": 3, "max_parallel_on_strong": 2, "serial": false},
    "direct_mode": {"max_tier": "T2"},
    "expert":      {"without_asking": false, "max_per_task": 1},
    "tokens":      {"unit": "total_tokens_millions",
                    "per_task": {"T0": 0.4, "T1": 0.8, "T2": 2, "T3": 6, "T4": 10, "T5": 16}}
  },
  "preferred_runtime": {
    "default": "same",
    "by_workflow": {"refactoring": "codex"},
    "quota_pct": 90,
    "cross_vendor_review_from": "T4"
  }
}
```

`max20.json` sets `inherits: "max"` and `runtime` is `codex` in `codex-*.json`. Codex profiles keep
their existing top-level `tiers`; `claude_agentic.tiers` is omitted there and the resolver reads the
existing one. `pro.json`: EXPERT effort `high`, no Fable key. `by_workflow` is `{}` in `codex-*.json`.
The `ai-planner` placement in BALANCED mirrors today's `codex-pro.json` `roles`; R16 asserts it
rather than this spec deciding it.

| plan (file) | fan_out agents / on_strong / serial | direct_mode max_tier | expert without_asking / max_per_task | tokens per task T0…T5 (M) |
|---|---|---|---|---|
| pro, team-pro (`pro.json`; plan/label overridden) | 1 / 1 / true | T2 | false / 1 | 0.2 0.4 1 3 5 8 |
| max, team-max (`max.json`; overridden) | 3 / 2 / false | T2 | false / 1 | 0.4 0.8 2 6 10 16 |
| max20 (`max20.json`, inherits max) | 6 / 4 / false | T2 (OQ1) | **true** / 2 | 0.8 1.6 4 12 20 32 |
| codex-plus | 1 / 1 / true | T2 | false / 1 | 0.2 0.4 1 3 5 8 |
| codex-pro | 6 / 2 / false | T2 | true / 2 | 0.8 1.6 4 12 20 32 |

`fan_out` is enforced by `runtime-gate` (R19) through `ask` on Claude and an explanation on Codex.
Codex's own `max_concurrent_threads_per_session` stays as it is (3 on Plus, 6 on Pro) — the
plugin's lower number is the one that asks.

Codex budgets mirror the Claude plan of similar price (Plus ↔ Pro, Pro ↔ Max 20x). The token
numbers are conservative placeholders scaled from the intent's measured baseline ($5–15 per
ordinary task); they are reported, never enforced (D2), and calibrated from `/usage-report`.

### I2 `<home>/claude-agentic/profile.json`

The resolved I1 plus `{"plan", "label", "runtime", "fable": bool, "plugin_version", "written_at"}`;
mode 0644; written only by `install.sh`; listed by `--dry-run`.

### I3 `<home>/state/runtime-gate.json`

```json
{"unavailable": {"until": 0, "reason": "", "source": "", "set_at": 0},
 "last_expert_launch": 0,
 "quota": {"weekly_pct": 93.5, "five_hour_pct": 12.0, "resets_at": 0, "seen_at": 0, "source": "statusline|rollout"},
 "expert_launches": {"T-2026-09-21-001": 1},
 "running_agents": {"<session_id>": [{"agent_id": "…", "tier": "STRONG", "started_at": 0}]}}
```

When absent and `fable-gate.json` or `codex-model-gate.json` exists, `unavailable` is imported once.

### I4 `state.py`

```
profile  [--field a.b.c] [--tier FAST|BALANCED|STRONG|EXPERT] [--other] [--json]   # read-only
handoff  [--print] [--reason …] [--to claude|codex [--for continue|review] [--why TEXT]]
quick    … --tier T<n>        # exit 7 "DIRECT_MODE_CAP T2 (plan pro): use init" when capped
```

State keys (schema 5): `handoff.pending_to: null|"claude"|"codex"`, `handoff.pending_since`,
`cross_vendor_review: null | {from, to, tier, requested_at, status: "requested"|"done", by_runtime}`.
Exit codes: 0; 2 misuse (same owner, closed task, target not installed); 4, 5, 6 unchanged; **7**
runtime/plan refusal, first token `RUNTIME_HANDOFF_PENDING` or `DIRECT_MODE_CAP`.

### I5 `install.sh`

`--plan pro|team-pro|team-max|max|max20` (existing aliases kept), `--codex-plan plus|pro`,
`--fable auto|yes|no` (auto = yes on max, max20, team-max), `--dry-run`, `--target`. Tty prompt:
`plan: max20 (Max 20x, detected from organizationRateLimitTier) — Enter to confirm, or type
pro/team-pro/team-max/max/max20:`; the Codex plan is confirmed the same way. Dry-run header:
`== claude: plan=max20 (Max 20x, max profile) fable=yes runtime-gate=on`.

### I6 `runtime-gate.py`

CLI `status | quota [--json] | clear | set <seconds> [reason] | statusline [--then <cmd>]`.
Events: Claude `PreToolUse:Agent`, `PostToolUse:Agent`, `SubagentStart`, `SubagentStop`,
`StopFailure(rate_limit|model_not_found)`; Codex `PreToolUse:Agent`, `PostToolUse:Agent`,
`SubagentStart`, `SubagentStop`. Env, new name before old before
default: `AI_RUNTIME_GATE=off` (`CLAUDE_FABLE_GATE`, `CODEX_MODEL_GATE`), `AI_RUNTIME_GATE_STATE`,
`_TTL`, `_NOT_FOUND_TTL`, `_OVERLOAD_TTL`, `_LAUNCH_WINDOW`, `_WEEKLY_PCT`, `_FALLBACK`, `_EXPERT`,
`_FALLBACK_EFFORT`, `_MODE`, `_AGENT_TTL`. Runtime is detected from the home the hook runs
from and the event payload; there is no runtime override variable. Registration: `settings.fable.json` renamed `settings.gate.json`, merged
on every Claude install (the Fable branch inside is driven by `profile.json.fable`); `codex/hooks.json`
commands renamed. Outputs: rewrite (`allow` + `updatedInput`), `ask` (Claude only), `additionalContext`; never
deny; always exit 0.

### I7 Events — WP2 vocabulary, no new type

- `runtime_handoff {"from","to","via":"manual"|"review"|"resume","reason","tier","tty":bool}`, actor `agent`.
  A quota-motivated move is `manual` with `data.reason`. `tty` is `os.isatty(0) and os.isatty(1)`
  when `handoff --to` ran (OQ5) — evidence of who moved the task, not an authorization.
- `model_fallback {"agent","from","to","reason":"rate_limit"|"model_not_found"|"overloaded"|"weekly_limit"}`,
  actor `hook`, via `state.py event`.

### I8 Grep test

Patterns: `\b(haiku|sonnet|opus|opusplan|fable)\b` (case-insensitive), `\b(Terra|Sol|Astra)\b`
(case-sensitive), `gpt-[0-9]`, `claude-(opus|sonnet|haiku|fable)-`.
**Shared-prompt scope**: `instructions/stub.md`, `instructions/routing.md`, `agents/*.md.tmpl` (frontmatter
and body), `skills/**/*.md`, `skills/ai-init/templates/**`,
`skills/project-init/templates/**`.
**Excluded explicitly**: `profiles/`, `install.sh`, `scripts/`, `hooks/`,
`tests/`, `docs/`, `README.md`, `skills/usage-report/prices.json`, `skills/project-update/history/**`
(frozen blobs), `agents/superseded/`. The installed `~/.claude/CLAUDE.md` is not in scope: its
managed block's source is checked, the rest is the user's (WP3's block-only rule).
Exit 1 lists `file:line`.

### I9 `usage-report.py`

`--task <task-id> [--root DIR] [--provider …]` → `task T-… tier T3 window <from>..<to>`, per
provider `tokens in/cache/out total`, `budget <plan> T3 6.0M · used 2.3M (38%)`; `--budgets` prints
each installed runtime's table. No journal write.

### I10 Migration `0005_runtimes_and_plans.py`

`VERSION = 5`, `MOVES = []`, `plan(ctx)` = `ctx.patch_state(...)` adding `handoff.pending_to`,
`handoff.pending_since`, `cross_vendor_review`. `state.py` fills the same defaults in memory, so a
task in flight works either way; the migration exists so `update.py --check` reports the project
as behind, `schema_migrated` lands in the journal, and a `schema-v4/` fixture exists (WP2/WP4
convention). Template `.ai/VERSION` → 5.

### Implementation order (for `/sdlc-plan`)

1. Resolver, `claude_agentic` in the four profiles, `max20.json`, `test-profiles.sh`.
2. `install.sh` (max20, detect/propose/confirm, strip, `profile.json`, `RENDER_*` from tiers,
   render every agent template), `agents/*.md` → `agents/*.md.tmpl` with tier placeholders,
   `render-codex-agents.py` reading `.md.tmpl`, `ai-reviewer-balanced` in both Codex profiles,
   `routing.md` placeholders, install and Codex render tests.
3. `runtime-gate.py`, shims, `settings.gate.json`, `codex/hooks.json`, install wiring,
   `test-runtime-gate.sh` (incl. the running-agent count); the two old gate suites unchanged; guard golden byte-identical; one
   PreToolUse:Agent call timed.
4. `state.py` (`profile`, `handoff --to`, exit 7, cross-vendor record, `quick` cap, advice line),
   `ai-task/SKILL.md` §0, migration 0005, template VERSION, `schema-v4/` fixture.
5. `usage-report.py --task/--budgets`, `usage-report` and `ai-status` SKILLs, the `risk-tiers.json`
   conflict hint in `update.py`.
6. The model-name sweep and `test-shared-prompts-model-free.sh`.
7. Docs (`docs/hooks.md`, `architecture.md`, `getting-started.md`, `agents.md`,
   `hook-performance.md`, `README.md`), then `bash tests/run-all.sh` once, to the end.

## Policy conformance

This repository has no project `CLAUDE.md`/`AGENTS.md`, no `.claude/` or `.codex/` skills or agents
and no ADRs under `docs/sdlc/adr/`; the binding sources are the global instructions, the intent's
constraints and the settled decisions of the WP1–WP4 specs. No plugin skill (Symfony UX, PHP)
matches this stack.

| Policy | How the design honours it |
|---|---|
| Global `CLAUDE.md` — tier routing (FAST/BALANCED/STRONG/EXPERT), `ai-expert` pins opus, `architect` pins `fable[1m]`, `max` off | The tables encode today's values; R18 proves no model or effort changes. |
| Global — five or more parallel agents never on opus | `max_parallel_on_strong ≤ 4` on every profile (R2), counted and enforced by `runtime-gate` (R19), even where `max_parallel_agents` is 6. |
| Global — fable-gate behaviour (≥ 90 % weekly → Opus, `status`/`clear`) | Kept verbatim inside runtime-gate; the old command names still work through the shims (R5). |
| Global — deterministic tools first; checks replace model steps | Resolver, quota, grep test, gate, cap are stdlib Python; budgets are read, not judged by a model. |
| Global — no agent commits, merges or deploys; the pipeline ends at human approval | `handoff --to` prints the other runtime's command and never runs it; approval stays WP2's human condition. |
| Intent — works on all five subscriptions, nothing needs a second one | No profile file or no other runtime ⇒ every new check is a no-op; advice appears only when the other runtime is installed. |
| Intent — token-costing things off or serial on Pro/Plus | `serial: true`, one agent, EXPERT asks (R2, R8). |
| Intent — guard rules unchanged, characterization byte-identical | runtime-gate is a model-routing hook, not a guard; no `ai-*` guard file changes (R6). |
| Intent — both runtimes at parity; every migration gets a fixture | One gate, one `profile.json` shape for both; `schema-v4/` fixture (R17). |
| Intent — plugin-owned files in projects change only through the skills | Template changes travel through `project-update`'s three-way walk; state keys through migration 0005. |
| Intent D1–D3 | R3 (propose + confirm, `--plan max20` skips); fixed defaults, reported not enforced (I1, R14); cross-vendor review manual, headless not built (R10, R11). |
| WP2 R10 — "nothing WP5 must undo"; the vocabulary grows only with a consumer | `handoff --to` extends `handoff`; `via: resume` untouched; no new event type (I7). |
| WP3 R6/I11 — WP5 converts `routing.md` and owns the grep | R15, R16, I8; the grep scope, including the `prices.json` and `history/**` exclusions that amend I11, is stated explicitly in I8. |
| WP4 Q6 — per-plan token budgets are WP5's | `budgets.tokens` (I1), reported by `/usage-report` (R14). |
| Data protection | No personal data is stored: `profile.json` holds plan names and tables, the gate state percentages and agent ids. The installer reads `organizationRateLimitTier` locally and writes nothing about the account. No security review at T3. |
| Memory — run tests once to the end; pylint clean in CI on 3.11–3.13 | One `run-all.sh` at the end; new Python uses `check=`, context-managed handles, no unused parameters. |

## Flagged concerns

Revised 2026-09-21 with the user: concerns 1, 6, 8, 9, 11 and 12 of the first draft were fixed in
the design (R16, R19–R21, I6, I8); 3, 4, 10, 13, 14 and 15 were closed — 3 by OQ4, 10 by OQ5, 13 by
correcting the memory note, 15 as the accepted consequence of OQ1, 4 and 14 as statements rather
than risks (the grep scope in I8, data protection in Policy conformance). What remains — 1 and 3
accepted as below, 2 settled by OQ3, and 4–7 accepted with the user on 2026-09-21 as risks the plan
carries with the mitigations named here:

1. **"Pro and Plus run strictly serially" is enforced by the plugin, not by Codex** (accepted,
   2026-09-21). `codex-plus.json` keeps `max_concurrent_threads_per_session: 3`; the plugin's
   `max_parallel_agents: 1` makes a second concurrent launch explain itself (R19), but Codex can still
   run it, because a Codex hook cannot ask. The user chose not to change the Codex setting.
2. **The renamed hook is less protected than the old name.** The path guard protects
   `.codex/hooks/codex-model-gate.py` by literal name; `runtime-gate.py` is only as protected as
   `context-guard.py` is today. Guard rules are frozen in this package, the shim keeps the protected
   name, and an additive rule for both hooks is a separate task (OQ3), created 2026-09-21.
3. **Quota signals can be stale** (accepted). Codex quota comes only from rollouts of a past or
   running session; Claude's only while a session with a statusline runs. Hence `stale`, `resets_at`
   and advice only — the quota never refuses anything.
4. **The running-agent count can drift.** A `SubagentStop` lost to a crash or a killed session leaves
   an entry behind; the TTL (30 min) bounds the damage to an extra question, never a block, and
   `runtime-gate.py clear` empties it. A subagent that genuinely runs longer than the TTL stops being
   counted — the budget errs towards letting work through.
5. **Twelve agent files are renamed to `.md.tmpl`.** Anything that reads `agents/<name>.md` from the
   repository by path — `render-codex-agents.py`, `install.sh`'s agent listing (`:414, :694`),
   tests, docs — must follow; a missed reader fails loudly (file not found), not silently. Installed
   agents keep their `.md` names, so users and the gate see no change. The history of the old paths
   stays in git.
6. **Codex hook facts come from one documentation page.** "`ask` is parsed but not supported" and the
   `SubagentStart` event were read on 2026-09-21; Codex moves fast. R8 and R19 therefore degrade to
   "allow and explain" on Codex by construction, and plan step 3 re-checks against the Codex CLI
   0.146 documentation and a live `codex` hook run.
7. **A new `project-update` output.** R21 adds one hint line on a specific conflict. It changes no
   decision of the walk, but `test-project-update.sh` asserts output, so the fixture set grows by one.

## Open questions

| # | Question | Recommendation | Owner | Status |
|---|---|---|---|---|
| OQ1 | For max20, `direct_mode.max_tier`: **T1** (the richer plan pays for a delegated review at T2) or **T2** (max20 differs from max only in fan-out and EXPERT)? The intent says max20 changes "how far direct mode reaches" but not in which direction. | T1 | user | **T2** — max20 differs from max in fan-out, EXPERT without asking and token budgets only (2026-09-21) |
| OQ2 | Defer `handoff --to --launch` (a headless run of the other vendor) to a later package, keeping WP5 at T3, and only print the command? | defer | user | **defer** — WP5 stays T3; the command is printed, never run (2026-09-21) |
| OQ3 | Protect `runtime-gate.py` (and `context-guard.py`) with an additive path-guard rule — in a WP7-style follow-up with an additive golden re-record, or inside WP5 (breaks "guard files untouched")? | follow-up | user | **follow-up** — a separate WP7-style task with an additive golden re-record; WP5 touches no guard file (2026-09-21) |
| OQ4 | Accept runtime-gate and the statusline wrapper on **every** Claude plan (first-draft concern 3), rather than only on Max + Fable as today? | accept | user | **accept** — runtime-gate and the statusline wrapper on every Claude plan; cost measured in plan step 3 (2026-09-21) |
| OQ5 | Record `data.tty` on `runtime_handoff` so the journal shows whether a human moved the task (first-draft concern 10)? | yes, small | user | **yes** — `data.tty` on `runtime_handoff` (I7) (2026-09-21) |
| OQ6 | Default `preferred_runtime.by_workflow` on Claude profiles: `{"refactoring": "codex"}` (the intent names mass refactoring as OpenAI work) or `{}`? Advice only, and only when Codex is installed. | `{"refactoring": "codex"}` | user | **`{"refactoring": "codex"}`** on Claude profiles, `{}` on Codex (2026-09-21) |
| OQ7 | Intent open question 1 (Codex question picker and session-start hook) was settled in WP2; intent open question 2 in WP2 as well. Nothing carried. | — | — | settled |
