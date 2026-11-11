# Spec: Interactive setup options — installer menu, /rr-setup dialog, memory + SQLite from setup

Written 2026-11-11 against 4.0.1 (`066a761`). Brainstorm: `docs/sdlc/intent/interactive-setup-options.questions.md`
(Q1–Q5). Builds on R36 (`docs/sdlc/specs/command-choice-dialog.md`): its gate, ledger and recorder are reused
unchanged; one opener and one allowed command are added. `docs/sdlc/specs/project-settings-dialog.md` stays
parked (Q3).

## Intent

**Problem.**
1. `npx riskrails` asks for the plan as typed text (`ask()`, `bin/riskrails.js:249`; Claude `:397-406`, Codex
   `:1275-1282`); runtime, fable, context and statusline are flags only (`:93-99`). Nobody sees the choices.
2. `/rr-setup` asks runtime, survey depth and `verify_command` in prose (`skills/rr-setup/SKILL.md` steps 1, 3, 5)
   and never offers project memory.
3. Packages-mode memory and its SQLite index need `state.py memory enable --author … --period … [--index sqlite]`
   typed in a terminal outside the agent; from an agent it exits 5 (`rr_state/memory_cmd.py:42-50`,
   `docs/local-memory.md:35-44`). That is the "extra prompt" the request wants gone.

**Outcome (testable).**
- O1 On a TTY the installer's runtime, plan, fable, context, statusline and Codex plan are chosen with arrow keys
  and Enter, each preselected; nothing is typed.
- O2 With the matching flag, `--yes` or a non-TTY stdin: stdout, stderr and the written files are byte-identical
  to 4.0.1.
- O3 Ctrl-C, Esc or no raw mode: the terminal is restored; an abort writes nothing; no raw mode falls back to
  the typed prompt.
- O4 A fresh `/rr-setup` shows one native dialog of up to four questions before any work and applies the picks.
- O5 On a set-up project only the unset options are asked; none unset → no dialog; `/rr-setup --options` asks all.
- O6 A memory pick turns packages mode on (optionally with the SQLite index) through R36 — verbatim, once, in
  the window, same session. Every other agent route to `memory enable` still exits 5.
- O7 Dialog off, Codex tool unverified, unattended, or the decision limit reached: today's prose plus the memory
  terminal command; nothing is enabled, no decision is written.

**Affected users and systems.** Everyone who installs (`bin/riskrails.js`, new `bin/menu.js`); every project
running `/rr-setup` (`skills/rr-setup/SKILL.md`, `setup.py`, `scaffold_ai.py`); the dialog
(`rr_state/dialog_cmd.py`, `cli.py`, `labels.py`, `hooks/guard/dialog.py` allowlist copy);
`rr_state/memory_cmd.py`; `docs/local-memory.md`, the `safety.md` template and its history.

**Constraints and non-goals.** Zero npm dependencies (Q4). No settings registry, no gate on `start`, no
SessionStart detection (Q3). `memory disable|cleanup|pack|redact|migrate --move-logs` stay terminal-only.
`hooks/ai-path-guard.sh` `SH_WORD`/`SH_RE` are not touched. Hooks cannot render UI; only the model sends the dialog.

**Open questions.** OQ1 (author source) **(blocking** step C4 only**)**; OQ2–OQ5 not blocking. See `## Open questions`.

### Decisions taken

| Q | Question | Answer |
|---|---|---|
| Q1 | Where choosing becomes interactive | **A** — both: a terminal menu in the npx installer, the native dialog in `/rr-setup` |
| Q2 | Memory and the SQLite index from `/rr-setup` | **A** — a dialog question off / packages / packages + SQLite; the pick runs `memory enable` through the dialog route, as `approve` does; author and period prefilled |
| Q3 | Relation to `project-settings-dialog` | **A** — small and standalone; reuse R36 as is; no registry, no gate on `start`; the old spec stays parked |
| Q4 | The installer's menu | **A** — built-in arrow-key menu, raw-mode stdin, no dependency; flags, `--yes` and non-TTY unchanged |
| Q5 | Which `/rr-setup` choices, and when | **A** — runtime, survey depth, `verify_command`, memory in one dialog on a fresh setup; only unset ones later; `/rr-setup --options` reopens all |

## Requirements

Each: outcome · test (`file::name`) · files.

| R | O | Requirement | Test | Files |
|---|---|---|---|---|
| R1 | O2 | Characterization (C2): today's typed prompts on a pty (Enter confirms, a typed value, Codex) and the non-TTY stderr lines; green before the change and under `RISKRAILS_MENU=off` after | `tests/test_install_menu.py::TestTypedPrompt::*` | test only |
| R2 | O1 | Pure key reducer: ↑/k, ↓/j stop at the ends; Home/End; 1–9 jump; Enter returns the value; Ctrl-C/Esc/q abort | `::TestReducer::test_keys` | `bin/menu.js` |
| R3 | O1 | Claude plan menu: six plans, one line and one note each; preselect previous install, else detected, else `team-pro` for a Team org, else `pro`; Enter alone gives today's proposal | `::TestMenu::test_plan_enter_confirms`, `::test_plan_arrow_down` | `bin/riskrails.js` |
| R4 | O1 | Codex plan menu, same rules | `::test_codex_plan` | `bin/riskrails.js` |
| R5 | O1 | Runtime menu (claude / codex / both, detected set preselected) only when `--target`, `--home`, `--codex-home` are all absent and a runtime is detected; none detected → today's exit 1 | `::test_runtime_menu` | `bin/riskrails.js` |
| R6 | O1 | Fable menu only on max tiers except balanced-max; context preselects `default`; statusline preselects the recorded mode; each skipped by its own flag (new `FABLE_GIVEN`, `CONTEXT_GIVEN`, `TARGET_GIVEN`) | `::test_option_menus_and_flags` | `bin/riskrails.js` |
| R7 | O3 | Abort: exit 130, `riskrails: aborted — nothing was written`, `stty -g` equal before and after, home untouched | `::test_abort_restores_terminal` | `bin/menu.js`, `bin/riskrails.js` |
| R8 | O3 | `RISKRAILS_MENU=off\|0`, `TERM=dumb` or menu child exit 3 → today's typed prompt, verbatim | `::test_menu_off_typed_prompt` | `bin/riskrails.js` |
| R9 | O5 | `setup.py options --json`: read-only facts for the four options | `tests/test_setup.py::TestOptions::test_fresh_all_unset`, `::test_detects_configured`, `::test_writes_nothing` | `skills/rr-setup/setup.py` |
| R10 | O4 | `setup.py options --open`, dialog on: prints `OPTIONS_DIALOG …` and the dialog JSON; the memory decision is opened first | `::test_open_prints_dialog` | `setup.py` |
| R11 | O4 | `state.py decision open --kind setup --spec`: validates, opens all decisions or none | `tests/test_dialog_gate.py::test_setup_spec_opens_atomically`, `::test_setup_spec_rejects_foreign_command` | `rr_state/dialog_cmd.py`, `cli.py` |
| R12 | O4 | Settling a setup choice prints `SETUP_PICK key=value`; a decline prints `key=` | `::test_setup_settle_prints_pick` | `dialog_cmd.py` |
| R13 | O6 | `memory enable` — and no other `memory` verb — accepted by both label allowlists | `test_dialog_gate.py::test_label_validator`, `test_dialog_contract.py::test_both_label_rules_agree` | `rr_state/labels.py`, `hooks/guard/dialog.py` |
| R14 | O6 | Enable through a pick runs and prints `via dialog`; other argv → 5; second run → 5; `disable/cleanup/pack/redact` → 5. Characterization first: enable with the dialog on and no pick → 5 | `tests/test_memory_pre_push.py::test_enable_refused_dialog_on_no_pick`, `::test_enable_via_dialog_pick`, `::test_enable_pick_used_once`, `::test_disable_stays_terminal` | `rr_state/memory_cmd.py` |
| R15 | O6 | In a four-question round with the memory command picked, the memory label is the next live pick and passes the gate | `tests/test_dialog_consent.py::test_setup_round_memory_first` | test only |
| R16 | O6 | Prefill: author per OQ1; `--period quarter` only while `memory.json` is absent; memory not offered outside a git work tree | `test_setup.py::TestOptions::test_memory_labels_prefilled`, `::test_no_git_no_memory` | `setup.py` |
| R17 | O7 | Fallback on: no `dialog.json`; Codex tool null; `AI_UNATTENDED=1`; `CLAUDE_CODE_SESSION_ATTENDED=0` | `::test_dialog_off_fallback` | `setup.py` |
| R18 | O4 | `scaffold-ai.sh --runtime none` creates `.ai/` and `.gitignore`, no instruction file | `tests/test_scaffold_idempotency.py::test_runtime_none` | `skills/rr-setup/scaffold_ai.py` |
| R19 | O4, O5 | `SKILL.md`: step 0, the order picks are applied in, `--options` | `tests/test_skills_surface.py::test_rr_setup_options_flow` | `skills/rr-setup/SKILL.md` |
| R20 | O6 | Docs say a memory pick in the dialog is a human route | doc tests; `test_project_update.py::test_history_covers_every_template` | `docs/local-memory.md`, template `safety.md` + history, `command-choice-dialog.md` |

## Design

### What exists (reused, KNOWN)

- `human_route` (`rr_state/dialog.py:18-40`): terminal → unattended → dialog (only with `allow_dialog` and a live
  `dialog_pick`, `:427-456`) → refuse. A pick's label must be this `state.py` plus exactly `sys.argv[1:]`; it is
  spent before the command acts.
- R36 round: `open_decision` (2–4 options, `DECISIONS_MAX=4`, `dialog.py:108,216-264`) → `print_dialog` →
  PreToolUse denies any other payload (`hooks/guard/decision.py:73-81`) → PostToolUse records pick/decline, free
  text is a decline (`hooks/guard/dialog.py:598-671`) → while pending the gate passes only the dialog tool, the
  next live pick and `decision show|settle|fallback`.
- Label allowlist, two copies pinned equal (`rr_state/labels.py:45-52`, `hooks/guard/dialog.py:222-239`,
  `tests/test_dialog_contract.py:84-99`): approve, reject, `profile set`, `verify --by`, `review --by`,
  `start --mode --by`, `git commit`, `git push`, `npx riskrails@<v> … --yes`.
- `memory_sync.enable` (`memory_sync.py:1082-1101`): author = `--author`, else local config, else slug(`$USER`);
  period written only when given (default `quarter`); index default `none`.
- "Configured" signals: `verify_command` set (`setup.py:347-357`); runtime = an instruction file or runtime dir
  exists (`scaffold_ai.py:149-158`); memory = `.ai/policies/memory.json` exists; survey — nothing recorded.
- The dialog exists only once `.ai/policies/dialog.json` does, i.e. after `scaffold-ai.sh`.
- Installer tests run with stdin `/dev/null` (`tests/install_harness.py:34-44`); the typed prompts are untested.

### (a) Installer menu

`choose(id, items, initial)` in `bin/riskrails.js`. Menu off → today's `ask()` branch, verbatim. Otherwise
`spawnSync(process.execPath, [bin/menu.js])`, stdio `['inherit','pipe','inherit']`, the spec in
`RISKRAILS_MENU_SPEC`. The child sets raw mode, uses `readline.emitKeypressEvents`, draws on stderr; on Enter it
erases the menu, prints one line in today's form (`plan: max (detected from …)`), writes the value to stdout,
exits 0; abort 130; no raw mode 3. Order: runtime, plan, fable, context, statusline, Codex plan.
**Rule: Enter through every menu gives today's result for that run.**

### (b) /rr-setup options dialog

- Step 0a `scaffold-ai.sh "$PWD" --runtime none` — creates `.ai/`, hence `dialog.json`, and no instruction file.
- Step 0b `$SETUP options --open [--all]`: setup.py computes the facts, builds the spec (texts + command labels
  naming this install's `state.py`), checks the dialog with `state.py consent --json`, pipes the spec to
  `state.py --root R decision open --kind setup --spec -`.
- Step 0c the agent sends the JSON; if a memory command was picked it runs that label first, verbatim; then
  `decision settle --id` per remaining decision and reads the `SETUP_PICK` lines.
- Applying: runtime → both scaffolds with `--runtime <v>`; survey → the depth of step 3; verify →
  `$SETUP verify --set` after step 2. "Not now", "other" or a decline → today's prose question at that step.

### (c) memory enable through the dialog

`memory_enable` calls `memory_human(…, allow_dialog=True)` → `dialog_pick` → `sync.enable` → prints the via
line. Nothing else in `memory_cmd.py` changes. Only setup opens that decision; a refused `memory enable` opens
nothing.

### Alternatives rejected

| Decision | Chosen | Rejected, because |
|---|---|---|
| Menu input | child process with keypress events | in-process raw `fs.readSync` — Esc is indistinguishable from arrow sequences, spins on EAGAIN, cannot restore the terminal when blocked · making the installer async — a refactor of a 1400-line script inside a feature (C3) · an npm prompt library — `"dependencies": {}`, supply chain (Q4) |
| Setup opener | setup.py builds the spec, state.py validates and writes | setup.py writes `decision.json` — second writer, breaks the entry check (`labels.py:77`) · state.py imports setup.py — ai-task would depend on the rr-setup skill · the skill sends its own AskUserQuestion — a free dialog consents to nothing and the gate denies it · a settings registry — Q3 |
| Memory route | `allow_dialog` on `enable` only, opened by setup | the refusal opens a decision (as `start --mode`) — any agent call would raise a project-wide question · `disable`/`cleanup` too — not decided, and `disable` removes the hook · a `--via-dialog` flag — argv identity already binds the pick |
| Fresh project | `--runtime none` first | runtime asked in prose — Q5 wants one dialog · scaffold with `auto`, add later — a created `CLAUDE.md` is never removed by a "codex" pick |

### Delivery order

Three tasks; each step runs `step_test_command` on its tests, each task ends with `verify --scope all`.

**Task A — installer (independent).**
A1 R1 characterization — `tests/test_install_menu.py`.
A2 refactoring, no behaviour change: extract `pickClaudePlan`/`pickCodexPlan` — `bin/riskrails.js` (own commit, C3).
A3 `bin/menu.js` + reducer tests.
A4 wire the menus — `bin/riskrails.js`, `tests/test_install_menu.py`.
A5 `README.md`, the header of `bin/riskrails.js` (it is the `--help` text).

**Task B — memory route (full mode, behaviour 2 — see concern A1).**
B1 characterization — `tests/test_memory_pre_push.py`.
B2 allowlists — `rr_state/labels.py`, `hooks/guard/dialog.py`, `tests/test_dialog_gate.py`,
`tests/test_dialog_contract.py`, `tests/fixtures/state/partition.json`.
B3 `rr_state/memory_cmd.py`, `tests/test_memory_pre_push.py`, `partition.json`.
B4 `docs/local-memory.md`, `skills/ai-init/templates/.ai/policies/safety.md`, `skills/project-update/history/**`
(via `tools/build-template-history.py`), `docs/sdlc/specs/command-choice-dialog.md`.

**Task C — setup options (after B).**
C1 `rr_state/dialog_cmd.py`, `rr_state/cli.py`, `tests/test_dialog_gate.py`, `partition.json`.
C2 pin only — `tests/test_dialog_consent.py`.
C3 `setup.py options --json`, `tests/test_setup.py`.
C4 `setup.py options --open`, tests (needs OQ1).
C5 `scaffold_ai.py`, the `scaffold-ai.sh` usage comment, `tests/test_scaffold_idempotency.py`.
C6 `skills/rr-setup/SKILL.md`, `tests/test_skills_surface.py`.

## Interfaces

### setup.py

```
setup.py options [--root DIR] [--all] --json     # read-only
setup.py options [--root DIR] [--all] --open
```

Exit 0 done · 2 usage · 6 state.py refused (its message passed through). First line of `--open`:
`OPTIONS_DIALOG D4 D5 D6 D7` | `OPTIONS_FALLBACK <why>` | `OPTIONS_NONE`.

```json
{"schema":1,"root":"/abs","git":true,"dialog":true,"ask":["memory","runtime","survey","verify"],
 "options":[
  {"key":"memory","state":"unset","current":null,"author":"vanssa","author_from":"local config","period":"quarter","fts5":true},
  {"key":"runtime","state":"unset","declared":[],"auto":"claude"},
  {"key":"survey","state":"unset"},
  {"key":"verify","state":"unset","proposal":{"command":"make test","from":"Makefile test"},"also":[]}]}
```

`state`: `unset` | `set` | `unavailable` (with `why`).

### state.py

`state.py decision open --kind setup --spec FILE|-`

```json
{"schema":1,"decisions":[{"key":"memory","header":"Memory","question":"…",
  "options":[{"kind":"choice","label":"Off — keep files mode","value":"off","description":"…"},
             {"kind":"command","label":"python3 <ENTRY> --root <R> memory enable …","description":"…"}]}]}
```

Checks: 1–4 decisions, fitting `DECISIONS_MAX` with those already open, else none opened; keys unique, in
{memory, runtime, survey, verify}; a choice `value` ≤ 200 printable characters; a command label passes
`validate_label` and is exactly `memory enable [--author S] [--period P] [--index none|sqlite]` with `--root`
this project; a choice label never starts with `python3`, `git` or `npx` and never equals a command (the gate
passes a Bash command equal to any pick). Exit 0 · 1 dialog off · 2 bad spec · 6 `CONSENT_LABEL_INVALID`,
`DECISION_LIMIT`, `DECISION_DUPLICATE`. Stored: `kind:"setup"`, `setup_key`, `options[].value`. Settle prints
`D5 settled: <label> (set)` then `SETUP_PICK runtime=both`. `memory enable` through a pick prints
`memory: via dialog (consent C12, decision D4)` first; the rest of its output is unchanged.

### Dialog texts

| Header | Question | Options (value, or the exact command) |
|---|---|---|
| Memory (opened first) | "Project memory for <name>: off keeps closed tasks only in .ai/reports/. packages also writes one compact committed file per developer per quarter under .ai/memory/, checked by a pre-push hook. Author <a> (from <src>), period quarter. Turn it on?" | "Off — keep files mode" `off` · `python3 <ENTRY> --root <R> memory enable --author <a> --period quarter` ("packages; installs .git/hooks/pre-push unless one exists or core.hooksPath is set") · the same `--index sqlite` ("plus a local, git-ignored SQLite index; FTS5 yes\|no — without it search scans: same results, slower") |
| Runtime | "Which agent runtimes work on <name>? The scaffold adds their instruction files and directories and never removes one." | "Auto — what the repository declares, else <installed>" `auto` · "Claude Code only" `claude` · "Codex only" `codex` · "Claude Code and Codex" `both` |
| Survey | "How deep should the first survey of <name> go?" | "Light — your 10-minute brain dump + 2 discovery agents" `light` · "Full — inventory + 6 discovery agents" `full` · with `--all` on a surveyed project "Keep the current survey" `keep` |
| Verify | "verify_command — the fast suite every task runs, e2e excluded. Proposed: `<cmd>` (from <src>)." | "Not now — ask me in chat" `` · "Use `<cmd>`" · at most one "Use `<also>`" · "Another — I type it in chat" `other`. Already set, with `--all`: "Keep `<current>`" · "Change — I edit it myself" |

Fallback (`OPTIONS_FALLBACK`): the four questions as numbered prose, then
`memory is the human's, in their own terminal: python3 <ENTRY> --root <R> memory enable --author <a> --period quarter [--index sqlite]`.

### /rr-setup and the scaffold

`argument-hint: [--survey light|full] | --options | --update [--apply] | --audit [context]`; a given `--survey`
removes the survey question. `scaffold-ai.sh --runtime none`: `.ai/` and `.gitignore` only.

### Installer

Keys ↑/k ↓/j Home End 1–9 Enter; Ctrl-C/Esc/q abort. `RISKRAILS_MENU=off|0` → typed prompt. Child spec
(internal): `{"title","items":[{"value","label","note"}],"initial"}`; child exit 0 / 130 / 3. Menus: runtime
claude/codex/both · plan pro/team-pro/team-max/max/max20/balanced-max with the notes of the header (`:8-16`) ·
fable yes/no · context default/economy · statusline riskrails/own · Codex plan plus/pro/balanced-max. Tests:
`pty.openpty()`, stdin and stderr on the slave, stdout on a pipe; skipped without a pty.

## Policy conformance

- **C1** — existing defects found (partial enable on a non-git directory; `--context economy` lost on reinstall;
  `memory enable` already runs under `AI_UNATTENDED`) are documented below, not fixed.
- **C2** — R1 and the first test of R14 are characterization tests written before the code they pin changes.
- **C3** — A2 is the only refactoring; its own step and commit, verified by A1.
- **C4** — every step above names its files.
- **C5** — memory is enabled only by a command the human picked in the dialog, run verbatim and once, as the
  harness recorded; no new commit, push, merge or deploy path.
- **C6** — task B allows what was denied and changes an approval path: behaviour 2, full mode. Task A moves no
  project decision and its non-TTY output is byte-identical: not behaviour 2 (the human weighs it).
- **Repo `CLAUDE.md`** — any BLOCKER closes with a test that pins it; `SH_WORD`/`SH_RE` untouched (no guard rule
  is needed: the refusal is state.py's exit 5). `AGENTS.md` and `CLAUDE.md` do not disagree on anything used here.
- **`.ai/policies/safety.md:30-32`** — "take the human route, as `approve` does": `approve` has the dialog route,
  so enable through a pick fits the sentence; the template text is still made explicit (R20).
- **Path guard** — the agent writes no `.ai/policies/*.json`; `memory.json` is written by `memory enable` itself.
- **ADRs** — `docs/sdlc/adr/` does not exist; none binding.

## Open questions

| # | Question | Owner | Blocks |
|---|---|---|---|
| OQ1 | Author prefill: Q2 said "from git", the code defaults to slug(`$USER`) and this repo's packages are `vanssa`, while `git config user.name` gives `ivan-kakurov`. Proposal: local config, else `$USER` (the code's own default, `--author` omitted), the value and its source shown in the question; git user.name not used | Ivan | **C4** |
| OQ2 | Does Codex's `request_user_input` cap the options per question below 4? A cap of 3 breaks the runtime question | Ivan (verify on Codex) | Codex only; fallback covers it |
| OQ3 | Should `--statusline-context` get a menu too? | Ivan | no |
| OQ4 | `--options` with `verify_command` already set: are "Keep" and "I edit it myself" enough? | Ivan | no |
| OQ5 | On a teammate's clone of a packages project, should setup ask for the per-developer SQLite index? Today that needs `memory enable --index sqlite` again | Ivan | no |

## Flagged concerns

### A. Policy vs intent

- **A1 Who can turn memory on changes (C5, C6, security).** After B, a session-bound dialog pick executed by the
  agent switches a committed, project-wide mode (every teammate's next close exports) and writes
  `.git/hooks/pre-push`. It fits C5 and `safety.md:30-32` but contradicts `docs/local-memory.md:35,44` ("the
  human, in a terminal outside the agent"), which B4 rewrites in the same task. Task B must run in full mode
  with a STRONG security-focused review and the human's approval.
- **A2 "Author from git" (Q2) contradicts the code** — OQ1. With git user.name one human becomes two authors
  here, and a real name lands in committed, pushed file names (data protection).
- **A3 "No extra prompts" is not fully met.** A free-text dialog answer is a decline
  (`hooks/guard/dialog.py:653-661`), so a `verify_command` other than the proposals is still typed in chat.

### B. Policy vs policy, or inside this design

- **B1 A new opener.** `decision open --kind setup` lets the model open decisions. Its choices run nothing, its
  commands are limited to `memory enable` of this `state.py` and root, a human must pick. Misleading choice text
  stays within the `safety.md` threat model; `consent audit` shows picks afterwards.
- **B2 Decision limit.** Four setup questions use all of `DECISIONS_MAX`; any other open decision makes the
  atomic open fail (exit 6) — the skill settles it first or falls back. Runtime has four values, so no
  "Not now"; `auto` is first.
- **B3 Pick order and window.** A pick lives 120 s and the gate passes only the next live pick; opening memory
  first makes its pick the earliest. That rests on ledger order (INFERENCE), pinned by R15.
- **B4 Unknown-plan branch changes on a TTY.** Today Enter on an undetected plan exits; the menu installs the
  highlighted row (`pro`). TTY only.

### C. Existing behaviour found, documented and not fixed (C1)

- `memory enable` on a non-git directory writes both config files, then exits 2 (`memory_sync.py:1048-1065`);
  setup offers memory only inside a git work tree.
- `human_route` returns "unattended" under `AI_UNATTENDED`, so `memory enable` already runs from an agent
  there; setup falls back to prose and never runs it.
- `--context` is not read from the previous install (`bin/riskrails.js:67`): Enter keeps `default`.

### D. Assumptions and unknowns

- Raw mode: Ctrl-C is a byte, handled by the child; a SIGKILLed child leaves the terminal raw — the parent
  prints a `stty sane` hint. The parent's paused stdin does not compete for bytes (INFERENCE, the pty test pins it).
- Windows: Node's console supports raw mode; mintty is non-TTY and takes today's path (INFERENCE; CI is Linux only).
- A Python without the `sqlite3` module at all: UNKNOWN; without FTS5 search scans with identical results
  (`memory_sync.py:764-767`) and the option text says so.
- `tests/test_scaffold_differential.py` and `tests/fixtures/state/partition.json` may need the new
  `--runtime none` and signatures (INFERENCE) — named in the steps' files.

### S. Security and data protection

- A1 and A2 above. No secret is read or written; the SQLite index is local and git-ignored
  (`.ai/local/memory/index.sqlite3`); the menu child receives only the option list through its environment.
