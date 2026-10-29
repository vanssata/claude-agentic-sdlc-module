# Plan: Guarded commands and decisions in the runtime's dialog (R36)

Intent: `docs/sdlc/intent/command-choice-dialog.questions.md` · Spec: `docs/sdlc/specs/command-choice-dialog.md`
· Redesign requirement R36 in `docs/sdlc/specs/claude-agentic-redesign.md:196`.

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time; each row is later one task
     planned with `/rr-plan` and run with `/rr-build`. The plan argues from the spec; executors read both. -->

**Goal.** A guarded command (`approve`, `reject`, `git commit`, `git push`, `verify --by`, `review --by`, a lowering
`start --mode`, `profile set`) or a decision is offered in the runtime's native dialog, prepared only by
`state.py`, recorded only from the harness's `tool_response`, and let through verbatim, once, in its window,
session and order; with the project switch off nothing changes.

**Architecture.** `state.py` owns `.ai/state/decision.json` and builds the dialog JSON. A new PostToolUse/Stop hook
`hooks/dialog-gate.py` writes `.ai/state/consent.jsonl`. The one-process PreToolUse guard `hooks/ai-guard.py`
gains a first check `decision` (the gate), the git guard a consent rule, the path guard a pass-through; a shared
module `hooks/guard/dialog.py` holds the switch, the ledger and the label rules. `context-guard.py` is the first
consumer (plan drift). Python 3 stdlib only; hooks run under `python3 -I -S`.

## Decisions taken before planning

- **D1 Order of migrations** (developer, 2026-10-28): the redesign's 3.4c (state-file move, migration 0009,
  `docs/sdlc/plans/claude-agentic-redesign.md:247-250`) ships before 7f; the dialog switch is migration **0010**.
  Migrations stay contiguous (`skills/project-update/migrations/README.md:3-6`).
- **D2 OQ5 accepted** (developer, 2026-10-28): drift is per user, the switch per project; the same drift gates in
  one project and warns in another. `drift-ack.json` is per user and silences the fingerprint everywhere. One
  entry in `.ai/project/known-risks.md` (task 7e).
- **D3 Flagged concerns accepted as written** (developer, 2026-10-28): C1 Stop blocks at most `stop_blocks_max`
  (2) times per human turn; C2 Codex stays off for good when spike 7.0 is negative (Q6); B5
  `PROFILE_NEEDS_INSTALLER` uses exit 6; OQ2 an API-key account is `unsupported`, no `api` profile.
- **D4 The switch goes on last.** The scaffold template `dialog.json` and migration 0010 move from the spec's
  step 7c to 7f, so no project has the dialog on before the hooks (7d) exist and the texts (7f) agree with the
  mechanism (spec risk 12, flagged A2). Tests of 7c–7e write their own `dialog.json` into the scratch project.
- **D5 7d is two tasks.** 7d1 is the inert half (ledger module, recorder, Stop, registrations, payload fields):
  with the dialog off or no decision open it changes no decision and the golden is byte-identical. 7d2 is the
  consuming half (gate, consent rule, pass-through, forgery test). A reviewer can reject one without the other,
  and each review reads half the diff (T-2026-10-21-001 cost 25.4M tokens on one 51-line guard change).
- **D6 One detection source.** 7a makes `bin/riskrails.js` call `state.py profile detect --json` instead of its own
  `detectClaudePlan`/`codexDetectPlan` (`bin/riskrails.js:326-347`, `:1146-1164`); the Python port is the only
  copy. The installer already needs python3 for `scripts/resolve-profile.py`.
- **D7 Codex "api" signal.** `codexDetectPlan` reads the JWT `chatgpt_plan_type` from `auth.json`; it has no
  `auth_mode`. `profile detect` reports `unsupported` for Codex when `auth.json` has `OPENAI_API_KEY` and no
  `tokens`, or `auth_mode` present and not `chatgpt`; both cases get a fixture in 7a.

## Departures from the spec's step table

| Spec | Plan | Why |
|---|---|---|
| 7c writes the template `dialog.json` and the migration | 7f | D4 |
| 7d one task | 7d1 + 7d2 | D5 |
| 7c "state.py keeps its own small ledger reader" | kept; `tests/test_dialog_contract.py` feeds both readers the same fixtures | spec design item 2 |
| migration "next free after 0008 and 3.4c" | 0010, after 3.4c ships | D1 |

## Global constraints

Copied from the spec; every task's requirements include them.

- Off is today byte-for-byte: with `.ai/policies/dialog.json` missing or `enabled:false`,
  `tests/fixtures/guard-characterization/golden.txt` has an empty diff; new fixtures are additive only (R36.2, R36.23).
- A pick never lifts another git rule: history, protected push, publish, deploy, merge, secrets, `--no-verify`
  stay denied with a pick (R36.9).
- Label rules (R36.4): one simple command, no `;` `&` `|` newline backtick `$(` `<` `>`; ≤ 400 printable
  characters; starts with `git commit`, `git push <remote> <branch>`, `…state.py … approve|reject|profile set|verify --by|review --by|start --mode … --by`, or `npx riskrails@<v> … --yes`.
- Window: `window_seconds` default 120, bounds 30–600; `stop_blocks_max` 2 (R36.7, R36.13).
- Question ≤ 1200 characters, header ≤ 12, 2–4 options, safe option first, `multiSelect:true` only for command
  lists; ≤ 4 open decisions per call (R36.3).
- `askUserQuestionTimeout` is rendered nowhere (R36.20).
- `.ai/state/consent.jsonl`: O_APPEND, one write ≤ 4096 B, lock file `.ai/state/consent.lock` opened `O_EXCL`,
  stale after 2 s (R36.6). No email, account id or token is written anywhere (spec §S).
- `full_irreversible` approval never takes the dialog (R36.10).
- Hooks stay stdlib-only under `python3 -I -S`; a hook fails open except the git consent rule (R36.9) and
  `state.py approve` (fail closed).
- Every registration change lands in both routes' sources (`settings.common.json`, `codex/hooks.json`) and both
  plugin files (`hooks/hooks.json`, `hooks/codex-hooks.json`); `tests/test_install_routes.py::test_plugin_hook_files_are_the_npx_registrations` and `::test_equal_effective_inventories` pin equality.
- Each task is weighed by `state.py weight`; the spec expects `--declare behaviour=2:"changes the approval path"`
  for 7b–7f (C6, `hooks/CLAUDE.md:4`). 7.0 moves no decision; 7a is a refactor (C3).

## Review focus

Inputs the spec implies but no requirement tests; each has its test added to the owning task below.

1. **A picked git command that another git rule then denies** (`git commit --no-verify` picked by a human):
   the gate appends `use` before the rule denies, so the decision settles with no command run. Expected: the deny
   text says the pick was consumed and a new decision is needed. → 7d2 `test_denied_after_use_settles_and_explains`.
2. **A label with quotes** (`git commit -m "it's done" -- a.py`): Claude Code passes the Bash string verbatim; the
   match is equality after strip, `shlex` only for `state.py` labels. Expected: round-trips. → 7c
   `test_label_with_quotes_round_trips`, 7d2 fixture `git-commit-consent-quoted`.
3. **A decision opened while a subagent runs in the same session**: the gate would deny the subagent's every tool.
   Expected: the gate skips payloads carrying the subagent marker spike 7.0 pins. → 7.0 fixture
   `subagent-pretooluse.json`, 7d2 `test_gate_skips_subagent`.
4. **No `session_id` in the payload** (an older runtime, a Codex build): a pick cannot be bound. Expected: the
   effective switch is off for that call (off route), never a pick without a session. → 7d1
   `test_effective_switch_matrix` row `no_session_id`.
5. **A stale lock** (a hook killed between `O_EXCL` and unlink): the next writer must not hang or lose the line.
   Expected: a lock older than 2 s is taken over, the line lands. → 7d1 `test_stale_lock_taken_over`.

## Files that change

| Task | Files |
|---|---|
| 3.4c | per `docs/sdlc/plans/claude-agentic-redesign.md:247-250` (migration `0009`) — prerequisite, its own plan |
| 7.0 | new `tests/fixtures/dialog/claude/{ask-single,ask-multi,ask-other,ask-esc,stop,stop-hook-active,auth-success,subagent-pretooluse}.json`, `tests/fixtures/dialog/codex/{request-single,request-multi,request-cancel,pretooluse,posttooluse}.json` (or `codex/NEGATIVE.md`), `docs/dialog-spike.md` |
| 7a | edit `skills/ai-task/state.py` (`cmd_profile_detect`, parser at `:3109`), `bin/riskrails.js:326-347`, `:1146-1164`, `:349-`, `:1166-` (call the port), `skills/rr-status/SKILL.md` (surface line); new `tests/test_profile_detect.py`, `tests/fixtures/profile/{claude-*.json,codex-*.json}`; `tests/test_install_dry_run.py`, `tests/test_codex_install.py` unchanged and green |
| 7b | edit `state.py` (`cmd_profile_set`, `human_route()` caller), `bin/riskrails.js` (copy `profiles/`, `scripts/resolve-profile.py` to `<home>/riskrails/`; write `dialog.tool`, `set_by`), `tests/test_install_routes.py` (inventory), `tests/test_codex_install.py` (`test_dialog_tool_only_on_verified_version`), `tests/test_install_dry_run.py` (`test_no_ask_timeout`), `tests/test_profiles.py`; `tests/test_profile_detect.py` (+ `set`) |
| 7c | edit `state.py` (`cmd_decision`, `cmd_consent`, `human_route()`, `cmd_close_v7:2704-2723`, `cmd_approve_v7`, `cmd_verify`, `cmd_review`, `cmd_start`, `EVENT_TYPES:84`, `FORGEABLE_EVENTS:96`, parser `:3068-3176`), `skills/rr-ship/SKILL.md` (§Interfaces commands only), `skills/rr-build/SKILL.md`, `skills/rr-review/SKILL.md` (the `--by` lines become "or the pick"); new `tests/test_dialog_contract.py`, `tests/fixtures/dialog/ledger/*.jsonl`, `tests/fixtures/dialog/payload-golden/*.json`; edit `tests/test_ai_task_state.py`, `tests/test_skills_surface.py` |
| 7d1 | new `hooks/guard/dialog.py`, `hooks/guard/decision.py`, `hooks/dialog-gate.py`, `tests/test_dialog_gate.py`, `tests/guard_harness.py` (`hook_output()` decoder); edit `hooks/guard/common.py:321-354` (`Payload.session_id`, `.transcript_path`, `.tool_use_id`), `hooks/ai-guard.py:25-32` (`decision` check, fast path only), `hooks/context-guard.py:464` (`session.json.prompt_count`), `hooks/hooks.json`, `settings.common.json`, `codex/hooks.json`, `hooks/codex-hooks.json`, `docs/hook-performance.md` |
| 7d2 | edit `hooks/ai-guard.py:17-20` (docstring), `hooks/guard/decision.py` (the gate), `hooks/guard/dialog.py`, `hooks/guard/git.py:17-27,59,244` (`WHY_CONSENT`, rule 9), `hooks/guard/paths.py:82-90,1192-1206` (`PROFILE_SET_RE`, `HUMAN_BY_RE`, `DIALOG_GATE_RE`, pass-through), `state.py` (automatic fallback R36.15), `.ai/project/known-risks.md`; new `tests/test_dialog_consent.py`, fixtures `tests/fixtures/git-guard/22-…25-*.json`, `tests/fixtures/path-guard/*-consent-*.json`, `tests/fixtures/codex-hooks/*-consent-*.json`; edit `tests/test_dialog_gate.py`, `tests/test_ai_git_guard.py`, `tests/test_ai_path_guard.py` |
| 7e | edit `hooks/context-guard.py:464-608` (drift at SessionStart, UserPromptSubmit mtime, Notification `auth_success`), `state.py` (`profile detect --open`, `drift-ack.json`), registrations ×4 (Notification, Claude only), `.ai/project/known-risks.md` (D2); edit `tests/test_context_guard.py`, `tests/test_profile_detect.py` |
| H1 | human: `docs/sdlc/constitution.md:10` (C5 → the §Interfaces sentence), `.ai/policies/safety.md:46-50` (guard + ledger), `~/.claude/CLAUDE.md` global line |
| 7f | new `skills/ai-init/templates/.ai/policies/dialog.json`, `skills/project-update/migrations/0010_dialog_switch.py`, `tests/test_migration_0010.py`; edit `instructions/stub.md:27,50`, `skills/ai-init/templates/{CLAUDE,AGENTS,GEMINI,junie-guidelines}.block.md` (rebuilt), `skills/project-init/templates/constitution.md:10`, `skills/rr-ship/SKILL.md:46-59`, `README.md:33`, `AGENTS.md:35`, `CLAUDE.md:38`, `instructions/routing.md:49,133`, `.ai/AGENTS.md:16-17`, `skills/ai-init/templates/.ai/AGENTS.md:16-17`, `docs/architecture.md:221`, `.ai/policies/testing.md` (if a budget line names the terminal), template history via `tools/build-template-history.py`; edit `tests/test_instruction_budget.py`, `tests/test_dialog_gate.py` (`test_c5_text_everywhere`), `tests/test_rename.py` allow-list if the old sentence is listed |

Never edited: `skills/project-update/history/blobs/*`, `tests/fixtures/guard-port/*`, the existing golden
lines, `hooks/ai-path-guard-defaults.json` (`.ai/state/` and `.ai/policies/*.json` are already protected, lines
27 and 31).

## Order of work

Each task: `/rr-plan <task>` → weight → `start` → `/rr-build` → `/rr-review` → `/rr-ship`. The suite is
`verify_command: bash tests/run-all.sh` (`.ai/policies/testing.md:87`) once per task, then `e2e_command` once.
7.0 can run in parallel with 3.4c; everything else is sequential.

- **3.4c State file move** (redesign plan, migration 0009). Expected guarded. Prerequisite of 7f only (D1); it may
  land anywhere before 7f.

- **7.0 Spike — fixtures only.** Expected light (no code, no guard decision moves). Record real payloads with a
  throw-away PostToolUse/Stop hook that `cat`s stdin to a file: AskUserQuestion `tool_input` + `tool_response` for
  single-select, multi-select (two ticks), "Other" with text, Esc/cancel; Stop with and without
  `stop_hook_active`; Notification `auth_success`; a PreToolUse payload issued from inside a subagent (the marker
  for review focus 3); `tool_use_id` and `transcript_path` presence. Codex: the same for `request_user_input`
  outside plan mode on the installed version, or `codex/NEGATIVE.md` naming the version tried and what did not
  fire. `docs/dialog-spike.md` lists the fields each later task relies on and the Codex version list for
  R36.19. **Gate G1 (human):** OQ3 — the Codex list is empty or not; empty means `dialog.tool` is `null` for
  Codex in 7b and the Codex fixtures of 7d1/7d2 assert "off". Proof: the fixtures parse as JSON;
  `tests/test_dialog_gate.py` of 7d1 loads them unchanged.

- **7a `profile detect` — a refactor (C3).** Expected guarded; `--declare behaviour=0:"detection results identical
  for every existing installer fixture"`.
  1. `tests/test_profile_detect.py`: port `tests/test_install_dry_run.py:225-285` and `tests/test_codex_install.py:207-235` cases verbatim as fixtures under `tests/fixtures/profile/`; add `claude-api-key.json`, `codex-api-key.json`, `codex-auth-mode-other.json` → `unsupported`; `claude-no-oauth.json` → `unknown`; `balanced-max` installed with live `max20` → `same`. Run: fails, no subcommand.
  2. `state.py`: `cmd_profile_detect(args, root)`; parser `profile detect [--runtime R] [--json] [--open]` under the existing `profile` parser (`:3109`); `--open` is parsed but refused with `die("--open needs state.py decision (task 7c)", 1)` until 7c. Output per spec §Interfaces (`status`, `installed`, `live`, `render`, `command`, `decision: null`). Fingerprint = sha256 over the sorted plan-bearing fields only. Exit 0 always. It needs no `.ai/` (same route as `profile`, `:3164-3169`).
  3. `bin/riskrails.js`: `detectClaudePlan()` and `codexDetectPlan()` become one `detectPlan(runtime)` that runs `python3 -I <SRC>/skills/ai-task/state.py profile detect --runtime <rt> --json` and maps `live.plan`/`live.from`; the two bodies are deleted. `stderr "detected plan:"` text unchanged.
  4. Run `tests/test_install_dry_run.py`, `tests/test_codex_install.py` unchanged → green is the refactor's proof.
  Proof: R36.16.

- **7b `profile set` and the installed profiles.** Expected full (behaviour 2: changes what is installed).
  1. Tests first: `test_profile_detect.py::test_set_same_tier` (max→max20 rewrites `profile.json` budgets only; `set_by.via` is `unattended` under `AI_UNATTENDED=1`; agent frontmatter and settings fragment byte-identical), `::test_set_cross_tier_refuses` (exit 6, `PROFILE_NEEDS_INSTALLER`, prints `npx riskrails@<plugin_version> --target claude --plan pro --yes`), `::test_set_refused_in_agent` (markers set, no pick → exit 5); `tests/test_install_routes.py` inventories include `riskrails/profiles/*.json`, `riskrails/scripts/resolve-profile.py`; `tests/test_codex_install.py::test_dialog_tool_only_on_verified_version`; `tests/test_install_dry_run.py::test_no_ask_timeout` (grep every rendered settings.json for `askUserQuestionTimeout` → none).
  2. `state.py`: `cmd_profile_set(args, root)`; `human_route()` unchanged this task (the `dialog` branch is 7c); same-tier table `{max, max20}`, `{pro, team-pro}`, `{max, team-max}`, Codex `{plus, pro}` when the rendered config and agents are equal; resolver path: `<home>/riskrails/scripts/resolve-profile.py`, else `${CLAUDE_PLUGIN_ROOT}/scripts/resolve-profile.py`.
  3. `bin/riskrails.js`: copy `profiles/` and `scripts/resolve-profile.py` into `<home>/riskrails/` (both runtimes); `agenticProfile()` adds `dialog: {tool}` (`"AskUserQuestion"` for Claude; Codex from the 7.0 list, else `null`) and `set_by: {via:"installer", at}`.
  Proof: R36.17, R36.19 (installer half), R36.20.

- **7c `state.py` decisions, consent, the dialog route.** Expected full (behaviour 2: changes the approval path).
  Interfaces produced (7d/7e consume them): `decision show|open|settle|fallback`, `consent [audit]`,
  `profile detect --open`; `.ai/state/decision.json` and `consent.jsonl` shapes exactly as spec §Interfaces;
  `human_route() -> ("dialog", "")`; journal events `decision_opened consent_recorded consent_used consent_voided
  decision_declined decision_settled decision_fallback plan_drift` added to `EVENT_TYPES` and to
  `FORGEABLE_EVENTS` (only `state.py` writes them; `event` refuses them).
  1. Tests first, in `tests/test_ai_task_state.py` (harness `Project.run()`, `:77-91`; the dialog route is reached with the agent markers present plus a ledger fixture): `test_close_opens_approval_decision_when_dialog_on` (prints `DIALOG_PENDING D1` + JSON; exit code unchanged), `test_close_prints_terminal_command_when_dialog_off`, `test_approve_via_dialog` (`gate.via == "dialog"`, `gate_approved.data.{via,consent,decision,tool_use_id}`), `test_dialog_argv_must_equal_label` (exit 5), `test_irreversible_stays_terminal`, `test_decision_open_commit_validates_labels` (exit 6 `CONSENT_LABEL_INVALID`), `test_decision_settle_choice`, `test_settle_pick_needs_terminal`, `test_fallback_prints_terminal_commands`, `test_ledger_mirrored`, `test_consent_audit` (`ok|mismatch|unverifiable` against a transcript fixture), `test_two_opens_do_not_clobber` (two `decision open` in a row → two entries), `test_label_with_quotes_round_trips` (review focus 2), `test_four_open_max`. In `tests/test_dialog_gate.py` (created here with the payload half; 7d1 adds the hook half): `test_payload_golden` (approval, commit, drift, question, two open → `tests/fixtures/dialog/payload-golden/`), `test_label_validator`, `test_ambiguous_multiselect_splits`. `tests/test_dialog_contract.py`: both readers (state.py's and, from 7d1, `hooks/guard/dialog.py`'s) agree on `tests/fixtures/dialog/ledger/*.jsonl`; this task asserts the state.py side only.
  2. `state.py`: `open_decision(root, state, kind, header, question, options, multi) -> str`; `cmd_decision`; `cmd_consent`; `human_route()` gains the `dialog` branch **before** the agent-marker refusal (`:633-641`): `next_live_pick()` whose label `shlex.split` → `realpath(argv0) == realpath(__file__)` and the rest `== sys.argv[1:]` → append `use`, return `("dialog","")`. Callers set `via`: `cmd_approve_v7`, `cmd_verify:2379`, `cmd_review:2493`, `cmd_start:2132`, `cmd_profile_set`. `cmd_close_v7:2704-2723` opens the approval decision instead of printing the command when the switch is on (`effective_switch`, a small local copy of 7d1's rule); the SUITE_BUDGET (`:2374`) and REVIEW_BUDGET (`:2488`) refusals and `request_gate` (`:1555`) open a `human_set`/`question` decision. Pruning on every run; `decision.json` deleted when none open. The ledger reader is state.py's own ≤ 60 lines (spec design item 2).
  3. Skills: `rr-ship` §Interfaces lists the new commands; the "You cannot approve" paragraph (`:57-59`) is left for 7f.
  Proof: R36.3, R36.4, R36.10, R36.14, R36.15 (state half), R36.24.

- **7d1 Hooks — the inert half.** Expected full (behaviour 2 by registration change; the golden is unchanged).
  Interfaces produced: `hooks/guard/dialog.py` — `effective_switch(root, runtime, payload) -> bool`,
  `read_decisions(root) -> list[dict]`, `next_live_pick(root, session_id, now) -> dict | None`,
  `ledger_append(root, line: dict) -> None`, `validate_label(label) -> str | None`, `canonical(obj) -> str`,
  `dialog_tool(runtime) -> str | None`, `adapt_response(runtime, payload) -> list[list[str]]`, constants
  `LABEL_MAX = 400`, `WINDOW = (120, 30, 600)`, `STOP_BLOCKS_MAX = 2`, `LOCK_STALE_S = 2.0`.
  `common.Payload` gains `session_id`, `transcript_path`, `tool_use_id` (empty string when absent).
  1. Tests first, `tests/test_dialog_gate.py` (hook half; harness gains `hook_output(out) -> dict` decoding PostToolUse/Stop/SessionStart shapes beside `decision()`): `test_effective_switch_matrix` (enabled × tool available × `AI_UNATTENDED` × subagent × `no_session_id` → on only for the one row), `test_pick_from_tool_response` (7.0 fixtures single and multi), `test_other_text_is_decline` (text not stored), `test_esc_is_decline`, `test_free_dialog_never_consents`, `test_stale_lock_taken_over`, `test_line_over_4096_refused`, `test_codex_adapter_fixture` (or the NEGATIVE assertion), `test_stop_blocks_twice_then_releases` (`stop_block` lines keyed by `session.json.prompt_count`), `test_gate_fast_path` (`timed`: a Grep payload with no `decision.json` ≤ 15 ms × `AI_TIMED_FACTOR`, factor from `tests/test_guard_characterization.py:563-567`), `test_registrations_equal_in_both_routes`. `tests/test_dialog_contract.py` now runs the hooks' reader too.
  2. `hooks/guard/dialog.py`, `hooks/dialog-gate.py` (`main()`: `hook_event_name` PostToolUse → record; Stop → block or release; anything else → exit 0 silent; never a deny), `common.Payload` fields, `ai-guard.py`: `CHECKS = ("decision","git","paths","scope")`, `TOOLS["decision"] = None` (every tool), `guard/decision.py` with only the `stat` fast path (`Allow` when no `decision.json`); `context-guard.py on_prompt` increments `prompt_count` in `session.json`.
  3. Registrations in all four files: PreToolUse ai-guard matcher `*` (Codex `.*`); PostToolUse `AskUserQuestion` (Codex `^request_user_input$`) → `dialog-gate.py` timeout 5; Stop → `dialog-gate.py` timeout 5. `docs/hook-performance.md` gets a row for the `*` matcher's non-Bash tools (B4).
  4. `bash tests/run-all.sh`: golden diff empty.
  Proof: R36.6, R36.7 (ledger half), R36.13, R36.19 (adapter), R36.12 (fast path).

- **7d2 Hooks — the consuming half. Riskiest step.** Expected full (behaviour 2: allows what was denied).
  1. **Characterization first (R36.23, C2):** confirm `tests/test_guard_characterization.py` and
     `tests/test_guard_differential.py` pin today's approve / commit / push / `--by` decisions (add cases if any is
     missing; golden re-recorded additively, in a separate first commit).
  2. Tests first: `tests/test_dialog_consent.py::test_model_cannot_forge_consent` (a)–(i) exactly as R36.22;
     `tests/test_dialog_gate.py`: `test_dialog_input_must_match` (reason carries the expected JSON, appends `offer`),
     `test_gate_denies_all_but_three`, `test_gate_skips_subagent` (review focus 3), `test_once`,
     `test_window_and_chain`, `test_other_session`, `test_order`, `test_mismatch_voids_all_picks`,
     `test_offer_without_pick_falls_back`, `test_denied_after_use_settles_and_explains` (review focus 1),
     `test_gate_fails_open_on_error`; golden fixtures `tests/fixtures/git-guard/22-git-commit-no-consent.json`
     (deny `CONSENT_REQUIRED` + `WHY_CONSENT`), `23-git-commit-consent.json` (allow), `24-git-push-main-with-consent.json`
     (still denied, protected), `25-git-commit-no-verify-with-consent.json` (still denied),
     `26-git-commit-consent-quoted.json` (review focus 2); path-guard fixtures: approve with pick (allow),
     approve without (deny, `WHY_APPROVE`), `profile set` with/without, `verify --by` with/without, a Bash line
     naming `dialog-gate.py` (deny, both modes); Codex twins under `codex-hooks/`. The ledger read error fixture
     (unreadable `consent.jsonl`) → `CONSENT_REQUIRED`.
  3. Code: `guard/decision.py` full gate (`DECISION_PENDING D<n>` + JSON; allows the dialog tool only when
     `canonical(tool_input) == canonical(decision show)`, the next live pick's Bash verbatim, and `state.py
     decision show|settle|fallback`; appends `use` for a git pick, `offer` for the dialog call; a missing `offer`
     follow-up triggers `state.py decision fallback` R36.15); `git.py` rule 9 after rule 8 (`:230`), `WHY_CONSENT`
     frozen beside `WHY_DEPLOY` (`:17-27`), fails closed on a ledger read error; `paths.py` `PROFILE_SET_RE`,
     `HUMAN_BY_RE`, `DIALOG_GATE_RE`, pass-through in `check_bash` before `:1202`; `ai-guard.py:17-20` docstring
     names the two exceptions; `known-risks.md` entries: constructed-command forgery (spec §S), the fifth copy of the
     `state.json`/`current.json` fallback (C1), `SETBY_RE` for the removed verb (flagged A8).
  4. `bash tests/run-all.sh`; golden diff additive only (`git diff --stat tests/fixtures/guard-characterization/golden.txt` shows only `+` lines).
  Proof: R36.5, R36.7, R36.8, R36.9, R36.11, R36.12, R36.15 (hook half), R36.22, R36.23.

- **7e Plan drift — the first consumer.** Expected full (behaviour 2: a new gate at SessionStart).
  1. Tests first, `tests/test_context_guard.py`: `test_drift_session_start_on` (`systemMessage` + `additionalContext` with `DIALOG_PENDING D<n>`, decision opened), `test_drift_session_start_off` (terminal command, no decision), `test_drift_no_ai` (warning only), `test_auth_success_opens` (Notification only opens; next prompt carries the JSON), `test_prompt_rechecks_on_mtime_change`, `test_ack_silences` (`drift-ack.json` fingerprint), `test_detect_within_3s` (the inner `run()` timeout, `:272`); `tests/test_profile_detect.py::test_open_writes_decision` and `::test_same_opens_nothing`.
  2. `state.py profile detect --open` (opens kind `plan_drift`: option 1 "Keep <installed> …" effect `ack`, option 2 the `profile set` label); "Keep" writes `<home>/riskrails/drift-ack.json` per spec; `context-guard.py`: SessionStart and `auth_success` call `state_py("profile detect --open --json")`; UserPromptSubmit compares the account file's mtime with `session.json.account_mtime`.
  3. Registrations ×4: Notification `auth_success` → `context-guard.py` timeout 15 (Claude only; Codex files unchanged but the equality test must still pass — the inventory compares per runtime).
  4. `known-risks.md`: D2.
  Proof: R36.16 (`--open`), R36.18.

- **H1 Human, before 7f starts.** Edit outside any run (R36.21, `hooks/CLAUDE.md`): `docs/sdlc/constitution.md:10`
  → the amended C5 from spec §Interfaces; `.ai/policies/safety.md:46-50` → "approval rests on a guard plus a
  ledger; a constructed command is outside the threat model and `consent audit` detects it afterwards";
  `~/.claude/CLAUDE.md` → the global stub line from spec §Interfaces. 7f's `test_c5_text_everywhere` fails until
  this is done; the agent answers `SCOPE_CHANGE_REQUIRED` rather than editing them.

- **7f Switch on and the texts.** Expected full (behaviour 2: changes install and migration for every project).
  1. Tests first: `tests/test_migration_0010.py::test_writes_enabled_and_prints` (a schema-9 project: `dialog.json` exactly `{ "version": 1, "enabled": true, "window_seconds": 120, "stop_blocks_max": 2 }`, one hint line naming the file and `enabled:false`; idempotent on a second run; a project that already has the file is untouched), `::test_in_flight_state` (a task in flight survives); `tests/test_dialog_gate.py::test_effective_switch_matrix` row "scaffolded project is on"; `tests/test_dialog_gate.py::test_c5_text_everywhere` (the sentences "No agent commits, merges or deploys; approval is given by a human outside the agent", "No agent commits, pushes, merges or deploys; the pipeline ends at human approval, given outside the agent", "You cannot approve" have 0 hits outside `skills/project-update/history/`, `tests/fixtures/`, `docs/sdlc/`, `.ai/reports/`); `tests/test_instruction_budget.py` (2560 B global, 2048 B project, the safe-alone phrases `:260-267`, tiers never models).
  2. `skills/ai-init/templates/.ai/policies/dialog.json`; `skills/project-update/migrations/0010_dialog_switch.py` (`VERSION = 10`, `MOVES = []`, `plan(ctx)` uses `ctx.template(".ai/policies/dialog.json")` and `ctx.hint(...)`); texts per the Files table, each conditional on the switch ("… or the human runs them outside the agent"); `tools/build-template-history.py` in the same task (`skills/CLAUDE.md`); `tests/test_rename.py` allow-list only if the old sentence is listed there.
  3. `bash tests/run-all.sh`, then `e2e_command`.
  Proof: R36.1, R36.2 (text half), R36.21.

## Risks

| # | What breaks | Where | How we notice | Mitigation in this plan |
|---|---|---|---|---|
| P1 | The golden drifts: an existing deny changes text or an allow appears | 7d2 | `tests/test_guard_characterization.py`, `test_guard_differential.py`; `git diff` of golden shows a `-` line | R36.23 first commit of 7d2; only `+` lines allowed; 7d1 proves an empty diff before any consuming code |
| P2 | Every tool call pays for the `*` matcher | 7d1 | `test_gate_fast_path` (`timed`, 15 ms × factor); `docs/hook-performance.md` row | fast path is one `stat`; the gate module is imported lazily like the others (`ai-guard.py:54-64`) |
| P3 | Texts and mechanism disagree: the model refuses to run a pick, or runs a commit while CLAUDE.md forbids it | 7d2 → 7f | the model answers with the old sentence; `test_c5_text_everywhere` | D4: no project is on before 7f; H1 precedes 7f; 7c–7e tests turn the switch on only in scratch projects |
| P4 | Codex hooks silently skipped after new entries (trust hash) | 7d1, 7e | `tests/test_codex_install.py` trust message; `/hooks` in Codex | automatic fallback (R36.15): an `offer` with no `pick` by the next PreToolUse → off route |
| P5 | A pick cannot be bound (no `session_id`, no `tool_use_id`) | 7d1 | `test_effective_switch_matrix` `no_session_id` | off route for that call; never a pick without a session |
| P6 | A consumed pick whose command another rule denies leaves a settled decision and no commit | 7d2 | `test_denied_after_use_settles_and_explains` | deny text names the consumed pick and the reopen command |
| P7 | Fifth copy of the `state.json`/`current.json` fallback; `SETBY_RE` guards a removed verb | 7d1, 7d2 | review | C1: recorded in `known-risks.md`, not fixed |
| P8 | Migration numbering collides with 3.4c | 7f | `tests/test_project_update.py` contiguity | D1: 3.4c (0009) before 7f (0010) |
| P9 | A decision opened while a subagent runs denies the subagent's tools | 7d2 | `test_gate_skips_subagent` | 7.0 pins the subagent marker; unknown marker = the spike is incomplete, 7d2 does not start |
| P10 | Click-through approval | 7c | — (human) | facts in the question, safe option first, `full_irreversible` stays terminal, `via:"dialog"` in the journal, the project switch |
| P11 | `profile set` cannot find `profiles/` in the plugin-cache route | 7b | `tests/test_install_routes.py` inventories; `test_set_same_tier` from a `${CLAUDE_PLUGIN_ROOT}` layout | two lookup paths pinned in 7b step 2 |
| P12 | The installer's detection and the Python port disagree | 7a | `tests/test_install_dry_run.py`, `tests/test_codex_install.py` unchanged | D6: the JS calls the port; its own bodies are deleted |
| P13 | Spike negative for Codex: parity never arrives | 7.0 | `codex/NEGATIVE.md` | D3/C2 accepted; `dialog.tool` `null`; Codex fixtures assert "off" |
| P14 | Each full-mode task costs a STRONG review on a large diff | all | `/rr-status --cost` | D5 split; tests before code; one verify run per task |

## Proof (tests)

| Requirement | Test | Task |
|---|---|---|
| R36.1 | `test_dialog_gate.py::test_effective_switch_matrix`; `test_migration_0010.py::test_writes_enabled_and_prints` | 7d1, 7f |
| R36.2 | `test_guard_characterization.py` (empty golden diff); `test_ai_task_state.py::test_close_prints_terminal_command_when_dialog_off` | 7d1, 7c |
| R36.3 | `test_dialog_gate.py::test_payload_golden`; `test_ai_task_state.py::test_four_open_max`, `::test_two_opens_do_not_clobber` | 7c |
| R36.4 | `::test_label_validator`, `::test_ambiguous_multiselect_splits`; `test_ai_task_state.py::test_decision_open_commit_validates_labels`, `::test_label_with_quotes_round_trips` | 7c |
| R36.5 | `::test_dialog_input_must_match`, `::test_free_dialog_never_consents` | 7d2, 7d1 |
| R36.6 | `::test_pick_from_tool_response`, `::test_other_text_is_decline`, `::test_esc_is_decline`, `::test_stale_lock_taken_over`, `::test_line_over_4096_refused` | 7d1 |
| R36.7 | `::test_once`, `::test_window_and_chain`, `::test_other_session`, `::test_order` | 7d2 |
| R36.8 | `::test_mismatch_voids_all_picks`, `::test_denied_after_use_settles_and_explains` | 7d2 |
| R36.9 | `tests/fixtures/git-guard/22–26` via `test_ai_git_guard.py`; the unreadable-ledger fixture | 7d2 |
| R36.10 | `test_ai_task_state.py::test_approve_via_dialog`, `::test_dialog_argv_must_equal_label`, `::test_irreversible_stays_terminal` | 7c |
| R36.11 | path-guard consent fixtures via `test_ai_path_guard.py`; `dialog-gate.py` deny fixture | 7d2 |
| R36.12 | `::test_gate_denies_all_but_three`, `::test_gate_skips_subagent`, `::test_gate_fails_open_on_error`; `::test_gate_fast_path` | 7d2, 7d1 |
| R36.13 | `::test_stop_blocks_twice_then_releases` | 7d1 |
| R36.14 | `test_ai_task_state.py::test_decision_settle_choice`, `::test_settle_pick_needs_terminal` | 7c |
| R36.15 | `::test_fallback_prints_terminal_commands`; `test_dialog_gate.py::test_offer_without_pick_falls_back` | 7c, 7d2 |
| R36.16 | `tests/test_profile_detect.py` (ported cases + api/unknown/same); `::test_open_writes_decision`, `::test_same_opens_nothing` | 7a, 7e |
| R36.17 | `test_profile_detect.py::test_set_same_tier`, `::test_set_cross_tier_refuses`, `::test_set_refused_in_agent`; `test_install_routes.py` inventories | 7b |
| R36.18 | `test_context_guard.py::test_drift_session_start_on/_off/_no_ai`, `::test_auth_success_opens`, `::test_prompt_rechecks_on_mtime_change`, `::test_ack_silences`, `::test_detect_within_3s` | 7e |
| R36.19 | `test_codex_install.py::test_dialog_tool_only_on_verified_version`; `test_dialog_gate.py::test_codex_adapter_fixture` | 7b, 7d1 |
| R36.20 | `test_install_dry_run.py::test_no_ask_timeout`; `test_profiles.py` | 7b |
| R36.21 | `test_instruction_budget.py`; `test_dialog_gate.py::test_c5_text_everywhere` | 7f |
| R36.22 | `tests/test_dialog_consent.py::test_model_cannot_forge_consent` (a)–(i) | 7d2 |
| R36.23 | `test_guard_characterization.py`, `test_guard_differential.py` (cases added before 7d2's code) | 7d2 |
| R36.24 | `test_ai_task_state.py::test_ledger_mirrored`, `::test_consent_audit` | 7c |
| contract | `tests/test_dialog_contract.py` (both ledger readers, same fixtures) | 7c, 7d1 |
| O1–O5 | `e2e_command` after 7f: a scratch project, dialog on, `close` → `DIALOG_PENDING`, a replayed `tool_response` → `approve` via dialog; the same with `enabled:false` → today's output | 7f |

## Rollback

- Any task: `git revert <task commit>`; the suite is green on the reverted tree because every task leaves the
  repository working and the golden additive.
- 7d1/7d2 in an installed home: `/rr-setup --update` or `npx riskrails@<previous>` re-renders the registrations;
  until then the hooks fail open (gate) or deny `git commit` (consent rule) only while a project has `enabled:true`.
- 7f in a user project: the human sets `"enabled": false` in `.ai/policies/dialog.json` (one line, in their own
  editor; the agent cannot). A plugin revert leaves the file inert: no reader, no effect.
- Plan drift (7e): delete `<home>/riskrails/drift-ack.json` to be asked again; `profile set` is undone by
  `profile set <previous>` (same tier) or the printed `npx` command.
