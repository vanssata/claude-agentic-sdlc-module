# Spec: Guarded commands and decisions in the runtime's dialog (R36)

Intent: `docs/sdlc/intent/command-choice-dialog.questions.md` (brainstorm record, Q1–Q8, 2026-10-27/28).
Redesign requirement: **R36** in `docs/sdlc/specs/claude-agentic-redesign.md`. Working copy with comments:
https://claude.ai/artifact/BNau8j9pzD2dF7GEcY4xKp.

## Intent

**Problem.** Every command the agent may not run itself — the human's `approve`/`reject`, `git commit`/`git push`,
`verify --by`, `review --by`, lowering `start --mode` — is printed as text and the human opens another terminal
and pastes it. Decisions ("strong or light review?", "keep plan max or switch to max20?") are typed as prose.
The human leaves Claude Code / Codex for every gate.

**Outcome (testable).**
- O1 When a guarded command or a decision is needed, the session shows the runtime's native selection dialog
  (Claude Code `AskUserQuestion`; Codex `request_user_input`) with numbered or checkbox options.
- O2 Nothing is typed: the human picks with the arrow keys and the agent runs or records the pick.
- O3 A project-level switch turns the dialog off; off is today's behaviour byte-for-byte (the human runs the
  command in their own terminal).
- O4 Plan drift (installed `profile.json` differs from the live account) is the first consumer of the dialog.
- O5 Codex gets the same native dialog or behaves as off. No typed numbers, no pasted `!` lines anywhere.

**Affected users and systems.** Every developer of a project with `.ai/`; the plugin's guards (`hooks/ai-guard.py`,
`hooks/guard/git.py`, `hooks/guard/paths.py`), `skills/ai-task/state.py`, `hooks/context-guard.py`, the installer
`bin/riskrails.js`, the rendered settings/hook registrations for both runtimes, the constitution (C5) and every
instruction text that repeats it.

**Constraints and non-goals.** Hooks cannot render UI in either runtime; only the model calls the dialog tool.
Ordinary Bash keeps running as today (Q4). No `askUserQuestionTimeout` (Q3). Not in scope: an `api` plan profile
(reported as `unsupported`, see A3), a typed-number fallback (Q6), a user-level switch (Q8).

**Open questions.** See `## Open questions` below; none blocks the plan except the Codex spike (7.0).

### Decisions taken

| Q | Question | Answer |
|---|---|---|
| Q1 | Option text | **A** — the command itself, verbatim, as it will run; no label hides a command |
| Q2 | Keeping the model from skipping the dialog | **A** — PreToolUse denies every tool but the dialog and the settle command; Stop blocks until settled |
| Q3 | `askUserQuestionTimeout` | **A** — absent, never rendered by the installer |
| Q4 | Which commands get the dialog | **A** — only commands the agent may not run itself (approve, commit, push, the `--by` forms) plus plan and review decisions |
| Q5 | Who runs a picked guarded command | **A** — the agent runs it; the gate moves into the harness: PostToolUse records the pick from `tool_response`, the guards allow a one-shot verbatim match; C5 amended |
| Q6 | Codex without `request_user_input` | **X** — the same native dialog or nothing: unavailable means the project behaves as switched off and the human types in their own terminal |
| Q7 | Plan-drift detection | **A** — in this spec, as the first consumer of the dialog |
| Q8 | The switch | **A** — project-level setting; off means the human must run the command in another terminal |
| Q9 | OQ1: the migration in existing projects | **A** — turns the dialog on (`enabled:true`) and prints one line saying so and how to turn it off (2026-10-28) |

## Requirements

Outcome tags: O1 dialog shown · O2 nothing typed, agent runs/records the pick · O3 project switch, off = today ·
O4 plan drift first consumer · O5 Codex parity or off. Steps 7.0–7f are the delivery order in §Design.

- **R36.1 Project switch** (developer, 2026-10-28). `.ai/policies/dialog.json`. The dialog is on only when
  `enabled` is true, the runtime's dialog tool is available (R36.19), `AI_UNATTENDED` is unset and this is the main
  session (not a subagent). Missing or unreadable file = off. The agent cannot flip it: the file is already under
  `(^|/)\.ai/policies/[^/]*\.json$` (`hooks/ai-path-guard-defaults.json:31`). New projects are scaffolded with
  `true`, and existing projects get `true` from the migration (next free number after 0008 and 3.4c), which
  prints one line saying the dialog is now on and how to turn it off (Q9, developer, 2026-10-28; C6 makes this
  behaviour 2 for every updated project, accepted). Test: `tests/test_dialog_gate.py::test_effective_switch_matrix`;
  `tests/test_migration_00NN.py::test_writes_enabled_and_prints`. O3. Step 7c.
- **R36.2 Off changes nothing.** With the file missing or `enabled:false`: every guard golden record is
  byte-identical; `close` prints the terminal `approve` command as today (`skills/rr-ship/SKILL.md:46-55`); a
  plain `git commit` is not refused; no Stop gate, no deny-all gate. Test: `tests/test_guard_characterization.py`
  (empty golden diff); `tests/test_ai_task_state.py::test_close_prints_terminal_command_when_dialog_off`. O3. 7c, 7d.
- **R36.3 Only `state.py` prepares a decision.** A dialog produces consent only for an open decision in
  `.ai/state/decision.json`, written solely by `state.py`. Openers: `close` (approval), `ask` (Q/G questions), the
  SUITE_BUDGET and REVIEW_BUDGET refusals and a lowering `start --mode` (the "human sets it" decisions),
  `profile detect --open` (plan drift), and `decision open --kind commit` — the only opener the model may call.
  Question text ≤ 1200 characters and self-contained (task, goal, mode/W, tree sha, verify, review verdict and
  open finding labels, rollback; or installed vs live plan), because the modal hides earlier output. Header
  ≤ 12 characters; 2–4 options; the safe option first ("Not now …" / "Keep …"). Command options: the label is the
  command verbatim with absolute quoted paths. `multiSelect:true` only for command lists (commit + push);
  single-select for decisions. Up to 4 open decisions become up to 4 questions in one call. Test:
  `tests/test_dialog_gate.py::test_payload_golden` (approval, commit, drift, question, two open). O1, O2. 7c.
- **R36.4 What counts as a command label.** One simple command: no `;` `&` `|`, newline, backtick, `$(`, `<`, `>`.
  ≤ 400 printable characters. Must start with an allowed form: `git commit`, `git push <remote> <branch>`,
  `…state.py … approve|reject|profile set|verify --by|review --by|start --mode --by`, or
  `npx riskrails@<v> … --yes`. The same check runs at `decision open`, in the PreToolUse check on the dialog tool
  and in the recorder. If any label contains `", "` (a joined multi-select answer would be ambiguous) the decision
  is shown as one single-select question per command. Test: `::test_label_validator`,
  `::test_ambiguous_multiselect_splits`. O2. 7c.
- **R36.5 The dialog call must match the prepared one.** While a decision is open, PreToolUse on the dialog tool
  denies any input not canonically equal to `decision show` and puts the expected JSON in the reason; it appends
  an `offer` line. With no decision open the dialog is allowed but never produces consent. Test:
  `::test_dialog_input_must_match`, `::test_free_dialog_never_consents`. O1. 7d.
- **R36.6 Consent comes from `tool_response`.** PostToolUse on the dialog tool (`hooks/dialog-gate.py`) reads the
  answers from `tool_response` (produced by the harness, never by the model); for each question of an open
  decision an answer exactly equal to an offered label appends a `pick` (one per command for multi-select,
  `order` = offered order); an empty answer, "Other"/free text or an ambiguous join appends a `decline` and the
  text is not stored; labels are validated again (R36.4); it writes only `.ai/state/consent.jsonl`: O_APPEND, one
  write ≤ 4096 B, under a portable `O_EXCL` lock file. Test: `::test_pick_from_tool_response`,
  `::test_other_text_is_decline`. O2. 7d.
- **R36.7 A pick is used verbatim, once, in its window, session and order.** Live while unused and not voided,
  same `session_id`, now ≤ `expires_at` (pick time + `window_seconds`, default 120, bounds 30–600; for a
  multi-pick the next window restarts when the previous pick is used). A command matches when it equals the label
  after stripping leading/trailing whitespace; nothing else is normalised. Only the next live pick in `order` can
  match. PreToolUse appends `use` for every pick it lets through, except `state.py` invocations, which consume
  their own pick after the argv check (R36.10). Test: `::test_once`, `::test_window_and_chain`,
  `::test_other_session`, `::test_order`. O2. 7d.
- **R36.8 When the model runs something else.** A guarded command (git commit/push, or a human-only `state.py`
  command) that does not match the next live pick is denied with `CONSENT_MISMATCH` listing the picked labels;
  every live pick of that decision is voided and the decision reopens. An unguarded command outside the gate runs
  as today and leaves the picks live. Test: `::test_mismatch_voids_all_picks`. O2. 7d.
- **R36.9 Git guard consent rule (dialog on only).** Runs after every existing rule (history, protected push,
  publish, deploy, merge, secrets, `--no-verify`); a pick never lifts those. `COMMIT_PUSH_RE` (`git.py:53`) without
  a live matching pick is denied with `CONSENT_REQUIRED` and a new frozen `WHY_CONSENT`. A ledger read error
  means deny: this one rule fails closed. Test: additive golden fixtures in `tests/test_ai_git_guard.py`:
  `git-commit-no-consent`, `git-commit-consent`, `git-push-main-with-consent` (still denied),
  `git-commit-no-verify-with-consent` (still denied). O2. 7d.
- **R36.10 `state.py` dialog route.** `human_route()` returns `("dialog","")` when a live pick's label, split with
  `shlex`, has `realpath(script) == realpath(__file__)` and its remaining tokens equal `sys.argv[1:]`; it appends
  `use` under the lock. Callers: `approve` (sets `gate.via="dialog"`), `verify --by`, `review --by`, lowering
  `start --mode --by`, `profile set`. A `full_irreversible` approval never uses the dialog: `--confirm` must be in
  the human's own words, so the terminal command is offered as today. Journal:
  `gate_approved.data={via:"dialog",consent,decision,tool_use_id}`. Test:
  `tests/test_ai_task_state.py::test_approve_via_dialog`, `::test_dialog_argv_must_equal_label`,
  `::test_irreversible_stays_terminal`. O2. 7c.
- **R36.11 Path guard.** Dialog on: `APPROVE_RE` (`paths.py:85`) and the new `PROFILE_SET_RE` and `HUMAN_BY_RE`
  (the `--by` forms of `verify`, `review`, `start`) let through a command equal to the next live pick in the same
  session; otherwise today's deny and the frozen `WHY_APPROVE` stay. New in both modes: a Bash command naming
  `dialog-gate.py` from an agent session is denied (the route for forging a hook call). Test: additive golden
  fixtures in `tests/test_ai_path_guard.py`. O2. 7d.
- **R36.12 Gate while a decision is open.** While `decision.json` has an unsettled decision, the ai-guard
  PreToolUse denies every tool except (1) the dialog tool (R36.5), (2) a Bash command equal to the next live pick,
  (3) `state.py decision show|settle|fallback`. Reason: `DECISION_PENDING D<n>` plus the JSON to send. The Claude
  matcher becomes `*`; with no decision open the check costs one `stat`. On error the gate fails open: it is not
  the security boundary (R36.9 and R36.10 are). Test: `::test_gate_denies_all_but_three`,
  `::test_gate_fast_path` (a `timed` case on a Grep payload, ≤ 15 ms × `AI_TIMED_FACTOR`). O1. 7d.
- **R36.13 Stop.** An unsettled decision makes the Stop hook return `{"decision":"block","reason":…JSON…}`. Loop
  breaker: at most `stop_blocks_max` (2) blocks per decision per human turn; the counter resets at
  UserPromptSubmit; `stop_hook_active` is honoured. After that the turn ends with a `systemMessage` naming the
  terminal escape; the PreToolUse gate stays. Test: `::test_stop_blocks_twice_then_releases`. O1. 7d.
- **R36.14 Settling a decision.** (a) all its command picks are used; (b) `decision settle --id D` applies a
  recorded choice pick (defer, keep, or a question's answer written through the `answer` code path into task.md
  `[Answer]:`) or a recorded decline; (c) a human in a terminal runs `decision settle --id D --pick N` (terminal or
  unattended route only). `state.py` prunes settled decisions on every run and deletes the file when none are
  open. Test: `test_ai_task_state.py::test_decision_settle_choice`, `::test_settle_pick_needs_terminal`. O2. 7c.
- **R36.15 Fallback to the off route.** `decision fallback --id D --why "…"`: the model may run it; it only
  downgrades to the off route, prints the terminal commands and removes the decision. Automatic when an `offer`
  has neither `pick` nor `decline` by the next PreToolUse (the recorder is not running, e.g. an untrusted Codex
  hook) or when the dialog stops being on. Journal `decision_fallback`. Test:
  `::test_fallback_prints_terminal_commands`, `::test_offer_without_pick_falls_back`. O3, O5. 7c, 7d.
- **R36.16 `profile detect`.** A port of `detectClaudePlan` and `codexDetectPlan` (`bin/riskrails.js:324-345`,
  `:1087-1105`); read-only unless `--open`. Status ∈ `same|drift|unknown|no_profile|acknowledged|unsupported`.
  Installed `balanced-max` with live max or max20 is `same`; an unknown Team seat or a missing/renamed
  `oauthAccount` field is `unknown`, never `drift`; `api` comes only from explicit signals (Codex `auth_mode` is an
  API key; Claude has no `oauthAccount` and has `ANTHROPIC_API_KEY`, `CLAUDE_CODE_USE_BEDROCK` or
  `CLAUDE_CODE_USE_VERTEX`) and reports `unsupported` (A3). Fingerprint = sha256 of the plan-bearing fields only;
  no email, ids or tokens stored. Test: `tests/test_profile_detect.py` ports the cases in
  `tests/test_install_dry_run.py:225-285` and `tests/test_codex_install.py:211` verbatim. O4. 7a — a refactor
  (the installer then calls `state.py`), its own task (C3).
- **R36.17 `profile set <plan> [--runtime]`.** Human route only (terminal, unattended, dialog). Same tier
  (max↔max20, pro↔team-pro, max↔team-max, Codex plus↔pro when config and agents render the same): write
  `<home>/riskrails/profile.json` through the installed `resolve-profile.py`, assert agent frontmatter and
  settings fragment unchanged, stamp `set_by`. Across tiers: exit 6 `PROFILE_NEEDS_INSTALLER` and print
  `npx riskrails@<plugin_version> --target <rt> --plan <p> --yes` (also `detect`'s `command`). The installer
  copies `profiles/` and `scripts/resolve-profile.py` into `<home>/riskrails/`; the plugin route reads them from
  `${CLAUDE_PLUGIN_ROOT}`. Test: `test_profile_detect.py::test_set_same_tier`, `::test_set_cross_tier_refuses`;
  `tests/test_install_routes.py` inventories include the new files. O4. 7b.
- **R36.18 When drift is checked.** `context-guard.py` runs `state.py profile detect --open --json` at
  SessionStart (both runtimes), on `Notification` matcher `auth_success` (Claude), and on UserPromptSubmit when
  the account file's mtime changed since the last check (both). Drift with the dialog on: open the decision,
  `systemMessage` + `additionalContext` with the dialog JSON (a Notification only opens the decision; the next
  PreToolUse or prompt carries the JSON). Dialog off or no `.ai/`: `systemMessage` + `additionalContext` with the
  terminal command, no gate. "Keep" writes the fingerprint to `<home>/riskrails/drift-ack.json`. Test:
  `tests/test_context_guard.py::test_drift_session_start_on`, `::_off`, `::_no_ai`, `::test_auth_success_opens`,
  `::test_ack_silences`. O4. 7e.
- **R36.19 Codex parity.** The dialog is on for Codex only when `profile.json.dialog.tool ==
  "request_user_input"`. The installer writes that value only for a Codex version on the list verified in spike
  7.0 (PreToolUse and PostToolUse fire for the tool outside plan mode; fixtures pinned); otherwise `null` = off.
  One adapter `hooks/guard/dialog.py` maps both runtimes' tools to one shape. No typed-number fallback anywhere.
  Test: `tests/test_codex_install.py::test_dialog_tool_only_on_verified_version`,
  `test_dialog_gate.py::test_codex_adapter_fixture`. O5. 7.0, 7d.
- **R36.20 No dialog timeout.** `askUserQuestionTimeout` is absent from every rendered settings.json (every plan,
  both routes). Test: `tests/test_install_routes.py::test_no_ask_timeout`; `tests/test_profiles.py`. O1. 7d.
- **R36.21 C5 and the instruction texts.** C5 is replaced by the §Interfaces sentence; the human edits it outside
  the run. The global line in `instructions/stub.md`, the project `CLAUDE.md` template, `skills/rr-ship/SKILL.md`
  §2 and `.ai/policies/safety.md` say the same, conditional on the switch. The 2048/2560 B budgets hold; the
  template history is rebuilt. Test: `tests/test_instruction_budget.py`;
  `test_dialog_gate.py::test_c5_text_everywhere` (the old sentence has 0 hits outside history). O2. 7f.
- **R36.22 The model cannot forge consent.** `tests/test_dialog_consent.py::test_model_cannot_forge_consent`:
  (a) Write/Edit/MultiEdit, a redirect, `tee`, `cp` or an interpreter one-liner aimed at `consent.jsonl` or
  `decision.json` — denied; (b) `… | python3 …/dialog-gate.py` — denied; (c) a PostToolUse payload whose
  `tool_name` is not the dialog tool — no line written; (d) answers that are not offered labels of an open
  decision — `decline` only; (e) labels containing `&&`, `$(` or a newline — no pick; (f) a pick from another
  session, expired, used or out of order — denied; (g) a dialog with no decision open — no pick; (h) `approve`
  with a live pick but argv ≠ label — exit 5; (i) a hand-appended `pick` line (standing in for a constructed
  command) — `consent audit` reports `mismatch` because its `tool_use_id` is not in the transcript fixture. O2. 7d.
- **R36.23 Characterization first (C2).** Before 7c/7d touch a guard path, today's decisions for approve, commit,
  push and the `--by` forms are pinned; afterwards the golden diff must be additive only. Test:
  `tests/test_guard_characterization.py`, `tests/test_guard_differential.py`. 7c.
- **R36.24 Audit trail.** The ledger is the source of truth; `state.py` mirrors new ledger lines into the task
  journal when a task is in flight (`decision_opened`, `consent_recorded`, `consent_used`, `consent_voided`,
  `decision_declined`, `decision_settled`, `decision_fallback`, `plan_drift`). `consent [--json]` lists live picks;
  `consent audit` checks each pick's `tool_use_id` against its `transcript_path` (`ok|mismatch|unverifiable`).
  Test: `test_ai_task_state.py::test_ledger_mirrored`, `::test_consent_audit`. O2. 7c.

## Design

**Components, one job each.**
1. `.ai/policies/dialog.json` — the switch; a human edits it; protected by the path guard.
2. `skills/ai-task/state.py` — the only writer of `decision.json`; builds the dialog JSON per runtime; commands
   `decision`, `consent`, `profile detect|set`; the `dialog` branch of `human_route()`; mirrors the ledger into the
   journal. It keeps its own small ledger reader rather than importing the hooks' module (precedent:
   AGENT_MARKERS, `state.py:614-617`); a contract test feeds both readers the same fixtures.
3. `hooks/guard/dialog.py` (new) — effective switch; decision reader; ledger read/append/lock; label validation;
   Claude/Codex tool-shape adapter; canonical comparison of dialog JSON.
4. `hooks/ai-guard.py` (PreToolUse, one process) — a new first check `decision` (the gate) on every tool; the
   consent rule in `git.py`; the consent pass-through and the two new rules in `paths.py`.
5. `hooks/dialog-gate.py` (new) — PostToolUse recorder on the dialog tool and the Stop blocker; never denies a tool.
6. `hooks/context-guard.py` — drift triggers (SessionStart, UserPromptSubmit, Notification `auth_success`); shells
   out to `state.py` as it already does for `handoff`.
7. `bin/riskrails.js` — calls `state.py profile detect` (7a); copies `profiles/` and the resolver (7b); writes
   `profile.json.dialog.tool`; registers the new hook entries.

**(a) Approval in `/rr-ship`, full mode, dialog on.**
1. The agent runs `state.py close`; both facts green; the gate is requested for tree T.
2. `close` opens decision D7 (kind approval): 1 "Not now", 2 the `approve` command, 3 the `reject` command. It
   prints the facts, `DIALOG_PENDING D7` and the dialog JSON; exit code unchanged.
3. The agent calls AskUserQuestion with that JSON; PreToolUse checks it equals the prepared JSON, appends `offer`.
4. The human picks 2 with the arrow keys; the harness returns `tool_response`; PostToolUse appends `pick C12`.
5. The agent runs the label in Bash; the gate passes it (next live pick); the path guard's `APPROVE_RE` passes it
   (verbatim, same session).
6. `state.py approve` finds the gate open and the tree unchanged; `human_route()` sees no tty but a dialog pick
   whose label equals argv; it appends `use C12`, grants via `dialog`, settles D7.
7. `close` runs again and archives the task. Picking 1: the agent runs `decision settle --id D7`; the gate stays
   open in the state, tools are released, the agent stops.

**(b) Commit after a task.**
1. `rr-ship` tells the agent to run `state.py decision open --kind commit --command "git commit -m '…' -- a.py
   b.py" --command "git push origin feat/x"`.
2. `state.py` validates both (R36.4) and writes a multi-select question with the task, files, diffstat, branch,
   remote.
3. The human ticks both; PostToolUse records C13 (order 1) and C14 (order 2).
4. The commit runs: existing git rules pass, the consent rule matches C13, appends `use`; C14's window restarts.
5. The push runs: the protected-branch rule still applies first; matches C14; the decision settles.
6. `git commit -am …` instead: `CONSENT_MISMATCH`, C13 and C14 voided, new dialog needed. A failed commit still
   uses its pick; a retry needs a new decision.

**(c) Plan drift at SessionStart.**
1. `context-guard.py` runs `state.py profile detect --open --json`: installed `max`, live `max20`
   (`organizationRateLimitTier default_claude_max_20x`), no ack, `render: profile`.
2. Dialog on: opens D9 with 1 "Keep max …" and 2 `python3 …/state.py profile set max20 --runtime claude`; the hook
   returns `systemMessage` + `additionalContext` with the dialog JSON; every tool is gated.
3. The human picks 2; the agent runs it verbatim.
4. `profile set` takes the dialog route, rewrites profile.json (budgets only), uses the pick, settles D9.
5. Picking 1 writes `drift-ack.json`; the fingerprint is not asked again.
6. After `/login`, `auth_success` repeats step 1; Codex re-checks when `auth.json`'s mtime changes.

**Why the model cannot forge consent.** The answer is not the model's: it writes only `tool_input`; the harness
builds `tool_response` from the human's selection and the recorder reads only that. The model cannot choose what
is offered: question and options must equal what `state.py` prepared (R36.5), and its only opener accepts plain
`git commit`/`git push`; a pick never lifts another git rule. The model cannot write a record: both files are under
`.ai/state/` (protected), no command line writes a pick, invoking the hook script is denied, labels cannot chain
commands, a pick is one-shot, short-lived, session- and order-bound, and `state.py` checks argv against the label a
second time. **What remains:** a constructed command (`sh -c` writing the ledger, a hook path behind a variable)
is outside the guards' threat model (`safety.md:46-50`); it goes into `known-risks.md` and `consent audit` detects
it afterwards. The old route was the same class: "A terminal alone is not enough — an agent can open a pty"
(`state.py:628-629`), and the agent markers are environment variables an agent can unset. Click-through: a human
can pick without reading; mitigations are the facts in the question, the safe option first, `full_irreversible`
staying in the terminal, `via:"dialog"` in the journal, and the project switch.

**Rejected alternatives.**
1. The human pastes a `!` line — still typing; the `!` shell carries the agent markers so `human_route()` refuses
   it anyway (`state.py:614`); Codex has no equivalent.
2. Instructions only — nothing stops the model running an unpicked command and no harness record exists (Q2, Q5).
3. A user-level switch — approval policy belongs to the repository: reviewable, versioned, same for every
   developer; the guards already read project policy (Q8).
4. PreToolUse `permissionDecision: "ask"` as consent — "Don't ask again" persists an allow rule (silent approvals
   from then on); `bypassPermissions` changes its meaning; no record `state.py` can check; cannot offer choice
   decisions.
5. HMAC-signed consent records — the key lives under the same uid, so the model can read it; same barrier class
   plus key management.
6. A hook that adds a `*` matcher to settings only while a decision is pending — edits settings from inside a run
   (the path guard freezes `.claude/**`), fires ConfigChange, and Codex reloads config only on restart.
7. `profile set` that always runs npx — contradicts Q7; the npx cache is ephemeral; npx stays for cross-tier only.

**Delivery order** (each step a full-mode task, `--declare behaviour=2:"changes the approval path"`):
**7.0 spike** (fixtures only: AskUserQuestion `tool_input`/`tool_response` incl. multi-select, Other and Esc; the
Stop payload with `stop_hook_active`; the `auth_success` payload; `tool_use_id`; whether Codex `request_user_input`
fires hooks outside plan mode) · **7a** detection refactor (C3) · **7b** `profile set` + installer copies ·
**7c** `state.py` decision/consent, `human_route`, migration, template · **7d** hooks and registrations ·
**7e** drift triggers · **7f** texts (C5 and safety.md edited by the human).

## Interfaces

**`.ai/policies/dialog.json`** (the scaffold template and the migration both write it as below, Q9):
```json
{ "version": 1, "enabled": true, "window_seconds": 120, "stop_blocks_max": 2 }
```
**`.ai/state/decision.json`** (only `state.py` writes it; deleted when no decision is open):
```json
{ "version": 1, "open": [ { "id": "D7", "kind": "approval|commit|question|human_set|plan_drift",
  "task": "T-2026-10-28-002", "runtime": "claude", "tree": "3f2a1c9…", "opened_at": "…Z", "opened_by": "close",
  "header": "Approve", "multi_select": false, "question": "<≤1200 chars, facts + the ask>",
  "options": [ {"n":1,"kind":"choice","effect":"defer","label":"Not now — leave the gate open"},
               {"n":2,"kind":"command","label":"python3 /home/vanssa/.claude/skills/ai-task/state.py --root /Store/x approve --by 'Ivan Kakurov'"},
               {"n":3,"kind":"command","label":"python3 … --root /Store/x reject --by 'Ivan Kakurov' --why 'rejected in the dialog'"} ] } ] }
```
**`.ai/state/consent.jsonl`** (append-only; ≤ 4096 B per line):
```
{"v":1,"type":"offer","decisions":["D7"],"session":"…","tool_use_id":"toolu_…","at":"…"}
{"v":1,"type":"pick","id":"C12","decision":"D7","option":2,"order":1,"label":"<verbatim>","session":"…","tool_use_id":"toolu_…","transcript":"<transcript_path>","runtime":"claude","at":"…","expires_at":"…"}
{"v":1,"type":"use","id":"C12","by":"git-guard|gate|state.py approve","at":"…"}
{"v":1,"type":"void","ids":["C13","C14"],"why":"mismatch","command_sha":"sha256:…","at":"…"}
{"v":1,"type":"decline","decision":"D7","why":"empty|other_text|ambiguous","at":"…"}
{"v":1,"type":"settle","decision":"D7","pick":"C12|null","effect":"approved|defer|ack|answered|declined|fallback","at":"…"}
```
**AskUserQuestion input** (the output of `decision show --json`; options in file order):
`{"questions":[{"question":"…","header":"Approve","multiSelect":false,"options":[{"label":"Not now — leave the gate open","description":"nothing runs"},{"label":"<cmd>","description":"the session runs exactly this, once"},…]}]}`
For Codex the same internal shape goes through the adapter into `request_user_input`'s arguments (pinned in 7.0).

**Hook outputs.**
- Gate or consent deny (existing `deny_json`, both runtimes):
  `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"<text>"}}`
  where `<text>` is one of:
  - `DECISION_PENDING D7 — the human decides first. Call AskUserQuestion with exactly the JSON below; until it is answered only that call, a command the human picked (verbatim) and state.py decision show|settle|fallback run.\n<json>`
  - `CONSENT_REQUIRED — 'git commit' and 'git push' run only as a command the human picked in the dialog.` + `WHY_CONSENT` (new, frozen)
  - `CONSENT_MISMATCH — the human picked:\n  <label>\nThis command differs, so the pick is void. Open the decision again.`
- PostToolUse: `{"hookSpecificOutput":{"hookEventName":"PostToolUse","additionalContext":"Picked: <label>. Run it verbatim now."}}` or nothing.
- Stop: `{"decision":"block","reason":"DECISION_PENDING D7 …<json>"}`; on release:
  `{"systemMessage":"RiskRails: D7 is still open; tools stay blocked. Answer the dialog, or in your terminal: python3 …/state.py --root … decision settle --id D7 --pick 1"}`.
- SessionStart drift: `{"systemMessage":"RiskRails: this account is Max 20x; RiskRails is installed for Max. The session asks before anything else.","hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"DIALOG_PENDING D9 …<json>"}}`.

**Registrations** (`hooks/hooks.json`, `settings.common.json`; Codex: `codex/hooks.json`, `hooks/codex-hooks.json`).
- PreToolUse `ai-guard.py` matcher → `"*"` (Codex `.*`); command and timeout unchanged.
- PostToolUse `{"matcher":"AskUserQuestion","hooks":[{"type":"command","command":"python3 -I -S \"${CLAUDE_PLUGIN_ROOT}/hooks/dialog-gate.py\"","timeout":5}]}` (Codex `^request_user_input$`).
- Stop `[{"hooks":[{…dialog-gate.py,"timeout":5}]}]`.
- Notification `[{"matcher":"auth_success","hooks":[{"type":"command","command":"\"${CLAUDE_PLUGIN_ROOT}/hooks/context-guard.py\"","timeout":15}]}]` (Claude only).

**`state.py` commands** (shared exit codes unchanged; the first output line carries the token):
```
decision show [--id D] [--json]              model; dialog JSON of the open decisions (≤4)        0 | 1 none open
decision open --kind commit --command C…     model (commit only); prints the JSON                 0 | 6 CONSENT_LABEL_INVALID
decision settle --id D [--pick N]            model applies a recorded pick/decline; --pick = terminal/unattended only   0 | 5
decision fallback --id D --why "…"           model; off route: prints the terminal commands, removes D   0
consent [--json]                             read-only; live picks and the ledger tail             0
consent audit [--json]                       read-only; ok | unverifiable | mismatch per pick      0 | 1 mismatch
profile                                      unchanged reader (--field --tier --json)
profile detect [--runtime R] [--json] [--open]   0 always
profile set <plan> [--runtime R]             human route (terminal|unattended|dialog)              0 | 5 | 6 PROFILE_NEEDS_INSTALLER
```
`profile detect --json`:
`{"runtime":"claude","status":"drift","installed":{"plan":"max","profile":"max","plugin_version":"3.1.0"},"live":{"plan":"max20","from":"organizationRateLimitTier default_claude_max_20x","fingerprint":"sha256:9c…"},"render":"profile|installer","command":"python3 /home/vanssa/.claude/skills/ai-task/state.py profile set max20 --runtime claude","decision":"D9|null"}`
Plain text: `plan: installed max · account max20 (organizationRateLimitTier default_claude_max_20x) → drift` /
`fix: <command>`; `profile set`: `profile.json: max → max20 (claude); settings, agents and the managed block
unchanged`; across tiers: `PROFILE_NEEDS_INSTALLER — max → pro also changes settings.json and the agents: npx
riskrails@3.1.0 --target claude --plan pro --yes`.

**Additions to `profile.json`:** `"dialog":{"tool":"AskUserQuestion"|"request_user_input"|null}`,
`"set_by":{"via":"installer|terminal|dialog","at":"…"}`.
**`<home>/riskrails/drift-ack.json`:** `{"version":1,"claude":{"fingerprint":"sha256:…","kept":"max","at":"…","via":"dialog"},"codex":null}`.

**Amended C5 (one line):** "C5. No agent merges or deploys; an agent commits, pushes or approves only by running,
verbatim and once, a command a human picked in the runtime's dialog as recorded by the harness — otherwise a human
runs it outside the agent."
**Global stub line:** "No agent merges or deploys. Commit, push and approval run only as the command the human
picked in the dialog — verbatim, once — or the human runs them outside the agent."

## Policy conformance

- **C1** Production behaviour is the source of truth: `SETBY_RE` still guards the removed `set` while the live
  `--by` verbs have no path-guard rule — recorded in `known-risks.md`, not fixed here (R36.11 adds rules for the
  live verbs as part of the feature, not as a fix).
- **C2** R36.23 pins today's guard decisions before any guard path changes; the golden diff must be additive.
- **C3** 7a (moving detection from `bin/riskrails.js` to `state.py profile detect`) is a refactor and its own task.
- **C4** Each delivery step names its files (7.0–7f above).
- **C5** Amended by the human outside the run (R36.21); until then the texts and the mechanism disagree (risk 12).
- **C6** Changing approval in a user project is behaviour 2: every step runs in full mode with
  `--declare behaviour=2:"changes the approval path"`; estimated W 9.
- **Global and project `CLAUDE.md`** ("No agent commits, pushes …"): both lines must change with 7f or the model
  refuses to run a pick (Flagged A2).
- **`.ai/policies/safety.md`** threat model: unchanged in kind; must state that the dialog route rests on a guard
  plus a ledger (Flagged A3).
- **ADRs**: none accepted (`docs/sdlc/adr/` holds only the template).
- **Skills**: `rr-ship` §2 text changes (R36.21); `rr-build`/`rr-review` lines "from their own terminal" become
  conditional on the switch. No plugin skill matches the stack.

## Open questions

| # | Question | Owner |
|---|---|---|
| OQ1 | Resolved 2026-10-28 (Q9): the migration turns the dialog on in existing projects and prints one line saying so; the behaviour-2 effect on every updated project is accepted. | developer |
| OQ2 | `profiles/api.json`: does an API-key account get its own budgets (R37 candidate) or stay `unsupported`? | developer |
| OQ3 | Spike 7.0: does Codex `request_user_input` fire PreToolUse/PostToolUse outside plan mode, on which version? Negative = Codex off for good (Q6). | spike |
| OQ4 | `window_seconds` 120 (A2): long enough for pre-commit hooks before the push? | developer, after 7d |
| OQ5 | Plan drift is per user (`<home>/riskrails/profile.json`) but the switch is per project: the same drift gates in one project and only warns in another (A9). Accept or add a user-level drift switch? | developer |

## Flagged concerns

### A. Policy vs intent
1. `docs/sdlc/constitution.md:10` "C5. No agent commits, merges or deploys; a human approves outside the agent."
   vs Q5 — amended by the human (R36.21).
2. Global `~/.claude/CLAUDE.md` ("No agent commits, pushes, merges or deploys; the pipeline ends at human approval,
   given outside the agent"), project `CLAUDE.md` ("No agent commits, merges or deploys; approval is given by a
   human outside the agent") and `skills/rr-ship/SKILL.md:57-59` ("You cannot approve … Never try another route")
   all conflict with Q5. Ship with 7f.
3. `.ai/policies/safety.md:46-50`: guards defend "against an agent's mistakes … not against an agent that
   constructs a command"; "the human gate at T4+ is the boundary". Approval now rests on a guard plus a ledger —
   the same class as today's tty route (`state.py:628-629`), but safety.md must say so.
4. `hooks/ai-guard.py:17-19` "Fail-open … must never make a tool unusable" vs Q2's deny-all gate and the
   fail-closed consent rule (R36.9). Docstring to amend.
5. Q2 "Stop blocks until settled" vs Claude's `stop_hook_active` loop rule: at most twice per turn (R36.13).
6. Q7 "`profile set` … profile.json + agent frontmatter": a plan also sets settings.json `model` (read at session
   start only) and the managed block, and the installed home has no `profiles/`. Resolved: same tier only,
   otherwise the installer (R36.17).
7. The brief placed detection in `install.sh`; after 3.5 it is a stub and the logic is in `bin/riskrails.js`.
   Moving it is a refactor, its own task (7a, C3).
8. Q4 names "human_set" as `state.py set --by`; `set` was removed (redesign spec §Interfaces). `paths.py:87-90`
   `SETBY_RE` guards only `set`; the live verbs have no rule — outside this task (C1), record in `known-risks.md`.
9. Q8 per-project switch vs per-user plan drift (OQ5).
10. The intent implies on by default; C6 makes changing approval in a user project behaviour 2. The developer
    decided (Q9, 2026-10-28) that the migration turns it on anyway: every updated project changes its approval
    path on `/rr-setup --update`, announced by one printed line. The migration task carries `behaviour=2`.

### B. Policy vs policy, or inside this design
1. C6 + `hooks/CLAUDE.md` + `skills/CLAUDE.md`: behaviour 2, full mode for every step (W ≈ 9).
2. The redesign's `state.py` surface (model-facing 9 / internal 3) grows: `decision` becomes model-facing,
   `consent` internal, `profile` gains the human-only `set` — recorded in the redesign spec's §Interfaces.
3. `WHY_*` texts are frozen (WP2): `WHY_APPROVE` stays for the off route, the on route adds `WHY_CONSENT`; one
   file holds two truths selected by the switch.
4. Hook latency budget (R14) covers only Bash, Edit and Read; the tools the `*` matcher adds need their own row.
5. `PROFILE_NEEDS_INSTALLER` uses exit 6 ("budget or scope") as the token-carrying refusal class; 5 means a
   missing human.

### C. Requirements that cannot be fully satisfied
- "Stop blocks until settled" (Q2) — bounded to two blocks per turn by the runtime's loop rule.
- "Codex gets the same dialog" (Q6) — only if spike 7.0 is positive; otherwise Codex is permanently off.

### D. Assumptions the intent left open
- A1 (closed by Q9) migration writes `enabled:true`; A2 window 120 s chained; A3 no `api` profile, `unsupported` only warns;
  A4 every consent-producing dialog is prepared by `state.py` (a model-written commit dialog could misstate facts).

### S. Security and data protection
- Forgery by constructed command is accepted under the safety.md threat model; `consent audit` detects it after
  the fact (`tool_use_id` vs transcript).
- Click-through approval is a residual risk; `full_irreversible` never uses the dialog.
- The ledger stores labels, session ids and `tool_use_id`s only; the drift fingerprint hashes plan fields only;
  no email, account ids or tokens are written anywhere.
- Fail-open: a git-guard timeout lets a commit through ungated (no worse than today); `approve` fails closed in
  `state.py`; a gate error releases tools (UX loss only).
- Two sessions in one project: picks are session-bound and consumed under the `O_EXCL` lock (2 s stale timeout,
  Windows-safe).
- Codex hooks need re-trust in `/hooks` after new entries; the automatic fallback (R36.15) covers the gap.
