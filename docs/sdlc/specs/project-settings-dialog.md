# Spec: Project settings and every recorded question in the dialog

Intent: `docs/sdlc/intent/project-settings-dialog.questions.md` (Q1–Q14, 2026-10-30). Part 2 of 2 (Q13=A): it starts
as soon as `docs/sdlc/specs/small-oop-modules.md` closes, and needs nothing else — the `modules/` layout, the
installer, the `settings` registry/stores/confirmations/audit and the extracted `modules/questions` come from part 1.
Builds on R36 (`docs/sdlc/specs/command-choice-dialog.md`): its gate, ledger and renderer are reused; its recorder
changes only for free text (D-free, pending Q14).

## Intent

**Problem.** A project's RiskRails settings are set by hand or by the agent asking in prose, nothing tells a project
that the plugin added one, and every recorded question — task questions, spec and plan brainstorms — is typed as
`1A` in chat instead of picked.

**Outcome (testable).**
- O1 `/rr-setup` (fresh, and standalone `/rr-setup --settings`) shows the project's settings in the native dialog as a
  series of questions; the human picks; the agent cannot set a setting itself.
- O2 With unconfirmed (or drifted) required settings, `setup.py check` exits `SETTINGS_MISSING` and `state.py start`
  refuses a new task; reads and `/rr-status` keep working.
- O3 `/rr-setup --update` and `--adopt` offer to change settings and show the dialog with new ones marked.
- O4 At session startup a setting id/version the project has not confirmed makes SessionStart tell the agent to show
  the dialog; otherwise SessionStart adds nothing.
- O5 Every recorded question (`state.py ask`, `ask --topic`) goes through the dialog; past the dialog's limits it is
  split into logical groups and pages sent one after another.
- O6 A free-text answer can be given in the dialog without the agent ever supplying the text (Q14, pending).
- O7 Dialog off, Codex unverified or unattended: today's output, byte for byte.

**Affected users and systems.** Every developer of a project with `.ai/`: a new gate on `start`, migration 0012, a new
way of answering every question. `skills/ai-task/state.py`, `skills/rr-setup/setup.py` and `SKILL.md`,
`skills/project-update/update.py` and its migrations, `hooks/context-guard.py`, `hooks/guard/paths.py`,
`hooks/guard/dialog.py` (free text only), `skills/rr-spec|rr-plan|rr-build/SKILL.md`, `modules/settings`, a new
`modules/question_flow`.

**Constraints and non-goals.** Hooks cannot render UI; only the model sends the dialog. No new module is disableable
(Q12). No existing code moves (part 1 did the moves; C3). Codex takes the terminal route until `request_user_input`
is verified (R36 Q6).

**Open questions.** Q14 (free text) is pending and blocks only step S9; see `## Open questions`.

### Decisions taken

| Q | Question | Answer |
|---|---|---|
| Q1 | What the "TUI dialog" is | **A** — the runtime's native dialog as in R36; a hook records the pick; the agent cannot write `.ai/policies/*.json` |
| Q2 | Which settings | **X** — a registry, each setting declared by its module; extensible later (part 1) |
| Q3 | Detecting a new setting | **A** — id + version vs `.ai/policies/settings.json`; SessionStart silent otherwise |
| Q6 | How hard it binds | **A** — `check` exits `SETTINGS_MISSING`, `start` refuses; reads and `/rr-status` work |
| Q7 | Disable flag | **B** — read, only warns, shown "(not effective yet)" (only on the test-only module, Q12) |
| Q8 | `dialog.json` | **A** — stays; declared by the `dialog` module |
| Q10 | Does `drifted` block `start` | **A** — it blocks |
| Q11 | Which questions | **A** — every recorded question, settings as a series; past the limits, logical groups in sequence |
| Q12 | Disableable modules | **A** — none of the new modules (supersedes Q9) |
| Q13 | Two specs | **A** — this is part 2, run right after part 1 |
| Q14 | Free text | *pending* — the agent's proposal is D-free (§Design) |

## Requirements

Each: outcome · test (`file::name`) · step.

### Settings dialog

- **D1 Options** (O1, O3). One single-select decision per setting. Option 1 is always
  `Not now — leave <id> unconfirmed` (effect `defer`). `bool`: `On …` / `Off …`, the current one "(current)".
  `command`: `Keep: <value>`, plus for e2e `none — this project has no e2e suite`. `module_toggle`:
  `On` / `Off (not effective yet)`. Prefix `[new] `, `[updated v1→v2] ` or `[changed since confirmed] `; nothing to
  offer → skipped with a reason. `modules/settings/tests/test_settings_options.py::test_option_table`, `::test_marks`,
  `::test_no_value_skipped`. S2.
- **D2 Series** (O1, Q11). Settings pass through the question flow (D12): one group per module in registry order;
  `dialog.enabled` in the last group. `test_settings_options.py::test_groups_by_module_dialog_last`. S2, S6.
- **D3 Apply** (O1). `apply_pick` refuses a stale `setting_v` and any value the spec did not offer; with a task in
  flight a value change writes nothing (`SETTINGS_FROZEN`), a keep is allowed; value first, then the confirmation.
  `test_settings_apply.py::test_stale_version_refused`, `::test_in_flight_frozen_keep_allowed`,
  `::test_value_then_confirmation`. S2.
- **D4 Notice** (O4). `session_line()` is `""` when nothing is pending, there is no `.ai/`, or `.ai/VERSION` < 12;
  otherwise one line ≤400 chars. `test_settings_notice.py::test_silent_when_confirmed`,
  `::test_line_names_ids_and_command`. S2.
- **D5 Migration 0012** (O2). Template `settings.json`, template `VERSION` 12, `0012_project_settings.py`: creates the
  file when absent, never overwrites, idempotent, a task in flight untouched, nothing pre-confirmed.
  `tests/test_migration_0012.py::test_creates_once`, `::test_existing_kept`, `::test_task_in_flight_survives`,
  existing `test_history_covers_every_template`. S3.
- **D6 Open** (O1). `state.py settings open [--all] [--id ID]…`: dialog on → the head group of `setting` decisions,
  `DIALOG_PENDING` + JSON + the settle order; dialog off → the terminal `settings confirm` command. Exit 1 nothing
  pending; 1 `SETTINGS_FROZEN` with a task in flight; 6 `DECISION_LIMIT`.
  `tests/test_settings_cli.py::test_open_prints_dialog_json`, `::test_open_dialog_off_terminal_route`,
  `::test_open_refused_in_flight`, `::test_open_nothing_pending`. S4.
- **D7 Settle** (O1). `decision settle` applies a recorded `set` pick through the facade (`SETTLE_EFFECT` gains `set`);
  no CLI takes a value from the agent. `test_settings_cli.py::test_settle_applies_recorded_pick_only`,
  `tests/test_dialog_contract.py::test_setting_choice_recorded_by_both_readers`. S4.
- **D8 Terminal route** (O1, O7). `state.py settings confirm --by NAME (--keep ID | --set ID=VALUE)… | --keep-all`
  passes `human_route` or exits 5 `APPROVAL_REFUSED`; the path guard denies it from an agent session; `decision
  fallback` on a setting prints it. `test_settings_cli.py::test_confirm_refused_in_agent_session`,
  `::test_confirm_unattended_records_via`, `::test_fallback_prints_confirm`;
  `tests/test_ai_path_guard.py::test_settings_confirm_is_the_humans`. S4.
- **D9 Start gate** (O2, Q10). `.ai/VERSION` ≥12 and `missing()` non-empty (drift included) → `start` exits 8
  `SETTINGS_MISSING`, writes nothing; `--amend`, `status`, reads unaffected; facade not importable → warning, start
  proceeds. `test_settings_cli.py::test_start_refused_until_confirmed`, `::test_start_refused_on_drift`,
  `::test_amend_status_unaffected`, `::test_schema_below_12_ungated`;
  `tests/test_end_to_end.py::test_fresh_project_confirms_settings_then_starts`. S5.
- **D10 setup.py and update.py** (O2, O3). `setup.py check`: `VERIFY_COMMAND_MISSING` (1) first, then
  `SETTINGS_MISSING` (8). `setup.py settings [--json]`: read-only, exit 0, marks NEW / UPDATED / drifted.
  `update.py` dry run and `--apply`: `settings: N new or updated (<ids>) — /rr-setup --update shows the dialog`.
  `tests/test_setup.py::test_check_settings_missing_exit_8`, `::test_settings_status_marks`;
  `tests/test_project_update.py::test_settings_pending_hint`. S7.
- **D11 SessionStart** (O4). `source=startup` only, an `.ai/` root, no task in flight: pending settings add the context
  line and a `systemMessage`; otherwise byte-identical to today. `tests/test_context_guard.py::test_settings_line`,
  `::test_silent_when_confirmed`, `::test_silent_on_resume_and_in_flight`. S8.

### Every recorded question

- **D12 Groups** (O5). Pending questions beyond the free decision slots (`DECISIONS_MAX` − open) are queued in groups:
  an explicit `--group <name>` (or `"group"` in `--batch`) first, else the order asked; a group never exceeds the free
  slots, a larger one is split in order; only the head group is open; settling its last decision opens the next and
  prints `DIALOG_PENDING`. `modules/question_flow/tests/test_question_flow_groups.py::test_explicit_groups_kept`,
  `::test_large_group_split_in_order`, `::test_next_group_opens_after_last_settle`. S1, S6.
- **D13 Pages** (O5). A question with more options than one dialog question holds (4, `Not now` first) is paged:
  `Not now`, the first options, `More options → <n>/<m>` (effect `next_page`); the recommended option on page 1;
  replaces today's ">3 options stays on the file route" (`skills/ai-task/state.py:1621-1622`).
  `test_question_flow_paging.py::test_pages_cover_every_option_once`, `::test_recommended_on_first_page`,
  `::test_next_page_effect`. S1, S6.
- **D14 Topic questions** (O5). `ask --topic` offers each question as a `question` decision with `task: null`,
  `topic: <slug>`; settle answers through `cmd_answer(topic=<slug>)`; today only task questions are offered
  (`state.py:1620-1631`). `tests/test_question_flow_cli.py::test_topic_question_offered_and_settled`. S6.
- **D15 Off route** (O7). Dialog off, Codex unverified or unattended: `ask` prints exactly today's output (prose, file
  route, `WAITING_FOR_ANSWERS`). `test_question_flow_cli.py::test_dialog_off_output_byte_identical`. S6.
- **D16 Free text** (O6, pending Q14). See D-free in §Design. `tests/test_dialog_free_text.py::test_other_text_recorded_when_allowed`,
  `::test_other_text_declined_when_not_allowed`, `::test_text_limits`, `::test_command_text_needs_echo_confirm`,
  `::test_agent_cannot_supply_text`. S9 (spike S9.0 first).
- **D17 Skills** (O1, O5). `rr-setup` (Setup step 5, the end of `--update` and `--adopt`, a new `--settings` section,
  `argument-hint`), `rr-spec`, `rr-plan`, `rr-build`: after `ask` or `settings open`, send the dialog it prints, settle,
  one group at a time. `tests/test_skills_surface.py` (extended). S10.

## Design

### What exists (reused)

- Recorder `hooks/guard/dialog.py:record` (`:518-570`), kind-agnostic; a single-select answer must equal an offered
  label, else `decline` and the text is not stored (`choose`, `:573-591`).
- `open_decision` (`state.py:2616-2648`), limits `DECISIONS_MAX=4`, `HEADER_MAX=12`, `QUESTION_MAX=1200`,
  `LABEL_MAX=400` (`:2306-2307`); `dialog_payload` (`:2657-2672`); `print_dialog` (`:2675-2682`).
- `decision settle` (`:2940-2975`) → `apply_choice` (`:2978-2988`); precedents for a write-effect choice: question
  `answer` (`:1620-1631`), `plan_drift` `ack` (`:2981-2982`).
- `effective_switch` (`hooks/guard/dialog.py:114-125`), `dialog_on` (`state.py:2333-2348`); `human_route`
  (`state.py:1071-1093`); the path guard (`hooks/guard/paths.py:82-108`); SessionStart `on_session_start`
  (`hooks/context-guard.py:759-800`).
- From part 1: `modules/settings` (registry, stores, confirmations, audit, flags), `modules/questions`.

### Components

`modules/settings` gains:

| File | Responsibility |
|---|---|
| `options.py` | `OptionStrategy` Protocol: `BoolOptions`, `CommandOptions`, `ToggleOptions` by kind; `DecisionSpecBuilder` → runtime-neutral dicts |
| `apply.py` | `SettingApplier` (validate → write value → confirm) |
| `notice.py` | `SessionNotice` |

New `modules/question_flow` (`can_disable: false`):

| File | Responsibility |
|---|---|
| `model.py` | `Question`, `Page`, `Group` (frozen dataclasses) |
| `paging.py` | `OptionPager`: pages of (slot − 2) options plus `Not now` and `More options →`, recommended first |
| `grouping.py` | `GroupPlanner`: explicit groups, then order asked; splits by the free slots |
| `queue.py` | `QueueStore` Protocol, `JsonQueueStore` (`.ai/state/question-queue.json`; topics `docs/sdlc/intent/<slug>.queue.json`) |
| `flow.py` | `QuestionFlow(planner, pager, queue)`: `.open(questions, free_slots)` → the head group's decision specs; `.after_settle(decision)` → next page, next group, or none |
| `__init__.py` | facade, `API = 1` |

`state.py` stays the only writer of `decision.json` and of the questions files; `question_flow` writes only its queue
file.

### Data flow

- **Settings, fresh setup.** Scaffold (`settings.json` empty, `VERSION` 12) → survey, `setup.py verify --set` as
  today → `check` exits 8 → `state.py settings open` → `settings.decision_specs` → `question_flow.open` → head group via
  `open_decision(kind="setting")` → `DIALOG_PENDING` → AskUserQuestion (PreToolUse checks equality) → the human picks
  (PostToolUse records) → `decision settle --id Dn` → `apply_choice` → `settings.apply_pick` (value, then
  confirmation) → `question_flow.after_settle` → next group … → `check` exits 0.
- **`--update` / `--adopt`.** After `--apply`, `setup.py settings`: pending → `settings open` with marks; none → a
  "change settings?" question; yes → `settings open --all`. **Standalone `--settings`:** `settings open --all`.
- **SessionStart.** `settings.session_line` → `additionalContext`; never opens a decision (that would gate every tool —
  the rejected Q6=C).
- **Start gate.** In `cmd_start` (`state.py:3451-3471`) after the in-flight check, before weighing.
- **Any `ask`.** The questions are recorded as today (task.md / `<slug>.questions.md` stay the record); dialog on →
  `question_flow.open` → head group opened; each settle → answer recorded → `after_settle` → next page or group.
- **Off route.** `settings open` prints `settings confirm …`; `ask` prints today's output.

### D-free: free text through the dialog (the agent's proposal, pending Q14)

The requirement to meet: the text is the human's, the harness records it, the agent never supplies it (C5, Q1).

1. **Declared, not default.** A question or setting carries `free_text: true` (task/topic questions: on, since `X: …`
   exists today; settings: only `command` kinds). Otherwise "Other" stays a decline, as in R36.
2. **Recorded by the hook from `tool_response`.** When the human's answer equals no offered label and the decision
   allows free text, the recorder stores `{"kind":"text","text":<verbatim>,"sha256":…}` in the pick instead of a
   decline. The model writes the tool's input, never its response, and the ledger is under `.ai/state/` where the
   path guard refuses the agent; so the text can only be what the human typed.
3. **Limits.** One line, ≤400 characters, printable, no control characters, no NUL; anything else is a decline whose
   settle line points at the chat/file route.
4. **Applied by settle.** A question: `answer Q<n>=X:"<text>"` (exactly today's free answer). A `command` setting: a
   second, echo-back decision — `Use exactly: <text>` / `Not now` — so the human sees the verbatim command before it
   becomes executable; only that pick writes it.
5. **Spike first (S9.0).** Pin the Claude Code `tool_response` shape for "Other" (the recorder already compares the
   answer to labels, so the text is present) with a recorded fixture; Codex stays off until verified.

Rejected for free text: (a) the agent types the text into `settle --text` — the agent would supply the value; (b) the
human edits `settings.json` — the path guard and Q1 rule it out for the agent, and it is today's file route anyway;
(c) storing the text without the echo-back for commands — a typo becomes an executable `verify_command` unseen.

### Alternatives rejected

1. **A hook applies the pick.** It would give the recorder write power over policy files; settle-applies-choice is
   R36's pattern.
2. **`setup.py` opens decisions.** Two writers of `decision.json` (`next_decision_id`, `state.py:2634`).
3. **Command labels `state.py settings set X=Y`.** Needs `validate_label` in both copies (`state.py`,
   `dialog.py:130-172`) and a new path-guard rule.
4. **A renderer inside a module.** It must equal `dialog_payload` byte for byte (`hooks/guard/decision.py:76`).
5. **Several questions in one AskUserQuestion call** — the gate checks the call against one prepared payload
   (`decision.py:73-81`); kept for later.
6. **Dropping `Not now` to fit four options** — a forced pick is click-through consent.
7. **Opening every group past `DECISIONS_MAX`** — the cap is R36's.
8. **Survey candidates as options** — `setup.py` and `adopt-map.json` are unprotected; loading them into the process
   that writes policy is code injection.

### Delivery order

| Step | Files | Weight |
|---|---|---|
| S1 | `modules/question_flow/**` | guarded (no caller) |
| S2 | `modules/settings/{options.py,apply.py,notice.py,__init__.py,tests/…}` | guarded (no caller) |
| S3 | `skills/ai-init/templates/.ai/policies/settings.json`, `templates/.ai/VERSION`, `skills/project-update/migrations/0012_project_settings.py`, the history output of `tools/build-template-history.py`, `tests/test_migration_0012.py` | full — behaviour 2: migration 0012 |
| S4 | `skills/ai-task/state.py` (settings open/confirm, `SETTLE_EFFECT`, `apply_choice`, fallback), `hooks/guard/paths.py`, `tests/test_settings_cli.py`, `tests/test_dialog_contract.py`, `tests/test_ai_path_guard.py` | full — behaviour 2: dialog picks write project policy |
| S5 | `state.py` (start gate), `tests/test_settings_cli.py`, `tests/test_end_to_end.py`, red harnesses via `start --amend` | guarded (behaviour 1) |
| S6 | `state.py` (`ask` → flow, topic decisions, `next_page`, `after_settle`, `--group`), `tests/test_question_flow_cli.py`, `tests/test_dialog_contract.py` | full — behaviour 2: every question answered in the dialog |
| S7 | `skills/rr-setup/setup.py`, `skills/project-update/update.py` (hint), `tests/test_setup.py`, `tests/test_project_update.py` | guarded |
| S8 | `hooks/context-guard.py`, `tests/test_context_guard.py` | guarded |
| S9 | after Q14=A: S9.0 spike fixture; `hooks/guard/dialog.py` (recorder), `state.py` (text settle, echo-back), `tests/test_dialog_free_text.py` | full — behaviour 2: the recorder stores human text |
| S10 | `skills/rr-setup/SKILL.md`, `skills/rr-spec/SKILL.md`, `skills/rr-plan/SKILL.md`, `skills/rr-build/SKILL.md`, `tests/test_skills_surface.py`, the README test count | light |

Then `verify_command` once to the end, then `e2e_command` once.

## Interfaces

**Facade additions, `modules/settings`:**

```python
def decision_specs(root: str, *, which: str = "pending", ids: tuple = ()) -> tuple[list[dict], list[str]]
def apply_pick(root: str, setting_id: str, setting_v: int, value, *, by: str, via: str, pick: str | None,
               in_flight: bool) -> tuple[bool, str]
def confirm(root: str, *, keep: list[str], set_values: dict, by: str, via: str, in_flight: bool) -> tuple[list[str], list[str]]
def terminal_command(root: str, state_py: str, ids: list[str]) -> str
def session_line(root: str, state_py: str) -> str
```

**Facade, `modules/question_flow`:**

```python
def open(root: str, scope: str, specs: list[dict], free_slots: int) -> list[dict]   # scope: "task" | "topic:<slug>" | "settings"
def after_settle(root: str, scope: str, decision: dict, effect: str) -> list[dict]  # next page / group, or []
def queued(root: str, scope: str) -> list[str]
```

**CLI.**

```
state.py settings open [--all] [--id ID]...        model   0 · 1 nothing pending · 1 SETTINGS_FROZEN · 6 DECISION_LIMIT
state.py settings confirm --by NAME [--keep ID]... [--set ID=VALUE]... [--keep-all]   human   0 · 2 · 5 APPROVAL_REFUSED · 1 SETTINGS_FROZEN
state.py ask … [--group NAME]                       + the head group's DIALOG_PENDING when the dialog is on
state.py start …                                    + 8 SETTINGS_MISSING
setup.py settings [--root DIR] [--json]             read-only, 0
setup.py check   [--root DIR]                       0 · 1 VERIFY_COMMAND_MISSING · 8 SETTINGS_MISSING
```

**Messages.** `start`:

```
SETTINGS_MISSING — the human has not confirmed: verify_command (new), dialog.enabled (changed since confirmed). A new task starts once they are confirmed:
  dialog:   python3 <home>/skills/ai-task/state.py --root <p> settings open   (send the dialog it prints)
  terminal: python3 <home>/skills/ai-task/state.py --root <p> settings confirm --by "<name>" --keep verify_command --keep dialog.enabled
```

After each settle with more queued: `next: group 2/3 opened — send the dialog below` + `DIALOG_PENDING`.

**SessionStart** (last sentence only when `missing()` is non-empty):

```json
{"systemMessage":"RiskRails: 2 project settings to confirm (verify_command new, e2e_command updated).",
 "hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"SETTINGS_PENDING verify_command e2e_command — before other work run: python3 /home/u/.claude/skills/ai-task/state.py --root /p settings open, then send the dialog it prints. Until they are confirmed, state.py start refuses a new task (SETTINGS_MISSING)."}}
```

**`decision.json` entry** (Claude; payload by the existing `dialog_payload`):

```json
{"id":"D21","kind":"setting","setting":"verify_command","setting_v":1,"module":"verification","task":null,"runtime":"claude",
 "group":"verification 1/2","free_text":true,"header":"Verify","multi_select":false,
 "question":"[new] verify_command — the fast suite every task runs, e2e excluded.\nCurrent: python3 -I tests/run_suite.py",
 "options":[{"n":1,"kind":"choice","effect":"defer","label":"Not now — leave verify_command unconfirmed"},
            {"n":2,"kind":"choice","effect":"set","value":"python3 -I tests/run_suite.py","label":"Keep: python3 -I tests/run_suite.py"}]}
```

A free-text pick (D-free): `{"pick":"C40","decision":"D21","kind":"text","text":"python3 -I tests/run_suite.py --modules auto","sha256":"…"}`.

**Migration `0012_project_settings.py`.** `VERSION=12`, `TITLE="project settings: the confirmations file"`,
`MOVES=[]`; `settings.json` exists → nothing; else `create` from the template (pattern `0010_dialog_switch.py:20-30`)
and the hint "settings.json is new: the human confirms the project's settings in the dialog (/rr-setup --settings);
until then state.py start refuses a new task (SETTINGS_MISSING). Unattended runs: state.py settings confirm
--keep-all --by <name>"; with a task in flight also "the task continues; the next start needs the settings".

## Policy conformance

- **C1** Off route byte-identical (D15); `setup.py verify --set`, the survey and R36 unchanged; the gate is opt-in by
  schema (`.ai/VERSION` ≥12).
- **C2** No bugfix in scope.
- **C3** No code moves here; part 1 did the moves.
- **C4** Each step names its files; red harnesses join S5 only through `start --amend`.
- **C5** A setting or an answer changes only from a pick the harness recorded, or from the human's terminal through
  `human_route`; free text only from `tool_response` (D-free).
- **C6** S3, S4, S6, S9 are behaviour 2: full mode, STRONG review each.
- **CLAUDE.md** every requirement names its test; files carry the decisions (the questions file, this spec).
- **`.ai/policies/testing.md`** unchanged; pylint 10.00/10.
- **`.ai/policies/safety.md`** the `AI_UNATTENDED` route for `settings confirm` is `approve`'s accepted risk
  (`safety.md:53-61`), recorded `via: unattended`.
- **R36 spec** single writer of `decision.json`; Codex off until verified; the recorder's change is limited to D-free.
- **ADR 0001** (part 1) new logic in `modules/settings` and `modules/question_flow`; callers through facades.

## Open questions

- **Q14** (owner: Ivan Kakurov) Free text in the dialog: D-free (A) or chat/file only (B)? Blocks only S9.

## Flagged concerns

### A. Policy vs intent

1. **`testing.md` is not locked outside a task** (`hooks/ai-path-guard-defaults.json:47`) and `setup.py verify --set`
   is agent-run (kept, C1); `drifted` blocking `start` (Q10) is what keeps the human's confirmation binding.
2. **Who writes.** The hook records; the agent-run `decision settle` writes the setting or answer from that record
   only. With D-free the recorder also stores human text — a wider recorder than R36's (concern 6).
3. **"First session start"** is read as `source=startup`, silent while a task is in flight; a setting kept deferred is
   mentioned at every startup.
4. **The disable flag is visible in no real project** (Q12): only the test-only module of part 1 carries it.

### B. Policy vs policy, or inside this design

5. **C6.** Four behaviour-2 steps (S3, S4, S6, S9), four STRONG reviews; `/rr-plan` may split S6 and S9 into a second
   task.
6. **R36 recorder.** R36 decided "Other" is a decline and the text is not stored; D-free reverses that for declared
   questions. It needs Q14 and a contract test that undeclared questions still decline.
7. **"One question per turn"** in `rr-spec` becomes "one group per dialog".
8. **Single writer.** The opener stays in `state.py`; `setup.py` stays read-only.

### C. Requirements that cannot be fully satisfied

9. **AskUserQuestion limits**: 4 questions per call, 2–4 options, 12-character header — met by groups and pages, at
   the price of more dialogs per brainstorm.
10. **Codex**: `request_user_input` unverified → terminal route (R36 Q6).
11. **Survey candidates are not options**: the dialog confirms the current value, `none`, or (D-free) a typed command.
12. **Unattended launchers and CI scaffolds** must run `settings confirm --keep-all --by …` once, or `start` refuses.

### D. Assumptions the intent left open

- A1 exit 8 `SETTINGS_MISSING` in both CLIs.
- A2 `start` gates only on required settings.
- A3 `settings open` refuses with a task in flight; `apply_pick` refuses a mid-task value change.
- A4 the `--update` "change settings?" question is an ordinary recorded question (D14), not a new decision kind.
- A5 facades return dicts.

### E. Risks

13. **Fixture breakage**: template-based harnesses (`tests/test_end_to_end.py:192`) hit the gate; S5 amends them in.
14. **Settle order**: `dialog.enabled` off first would make `prune_decisions` fall the rest back; it is in the last
    group and the output prints the order.
15. **Queue drift**: a queue file left by an abandoned brainstorm; `queued()` is shown by `/rr-status`, and the queue
    is rebuilt from the questions file when they disagree (the questions file is the record).
16. **Version skew** plugin cache vs `<home>`: hooks use `STATE_PY`'s tree.

### S. Security and data protection

17. Free text (D-free) is stored verbatim in the git-tracked questions file and the ledger: the same class as today's
    `X: …` answers; a secret typed into "Other" would be committed — the settle line warns when the text matches the
    secret patterns of `hooks/ai-path-guard-defaults.json`.
18. A typed command becomes executable only after the echo-back pick (D-free 4).
18b. Topic records live in `docs/sdlc/intent/`, which no guard protects (only `.ai/state/` is, path-guard defaults
    `:27`): the agent could edit a topic's `[Answer]:` line today, a rule of `rr-spec` only. Topic picks are therefore
    also written to the ledger (`.ai/state/consent.jsonl`, protected), so the dialog's record is the one that cannot
    be forged; the file is the readable copy. Found, not fixed.
19. The installed `modules/` is protected (part 1, M6): a forged module cannot redirect policy writes.
20. `by` names in `settings.json` are the same class of personal data as the journals.
