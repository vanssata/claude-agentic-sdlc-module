# Spec: UI-first approvals and an installer wizard (4.3.0)

## Intent

**Problem.** A user without a terminal — Claude Code Remote Control, the desktop
app, the web — meets dead ends. The approval dialog exists (R36,
`command-choice-dialog.md`) and carries `approve`, `reject`, commit, push,
`verify|review|start --by`, `memory enable` and `npx riskrails@<v>`
(`skills/ai-task/rr_state/labels.py:45-97`), but: the Stop hook's last word is
"Settle it in your terminal" (`hooks/dialog-gate.py:63-65`); refusals name the
terminal first even with the dialog on (`hooks/guard/git.py:273-276`,
`paths_base.py:39-57`, `rr_state/questions_cmd.py:137`); `batch on` has no dialog
route (`rr_state/steps.py:93-109`); the update notice names a terminal
(`hooks/update_notice.py:97-98`) although its label is already allowed; nothing
shows "what is waiting on me" (the statusline has model, context, limits, cost —
`hooks/runtime-gate.py:1208-1213`); and the installer asks one reverse-video menu
after another with no colour, no back, no review before writing and no uninstall
(`bin/menu.js:50-58`, `bin/riskrails.js:270-299`, `:845-853`).

Second, added by Q10: nothing tells an agent under this platform to write the
simplest code that works. The implementer contract speaks of files, behaviour
and tests only (`ai/agents/implementer.md:32-39`); neither reviewer list names
padding (`ai/agents/reviewer.md:7-23`, `agents/ai-reviewer.md.tmpl:68`); a new
dependency is checked only under the security focus
(`agents/ai-reviewer.md.tmpl:101`); the coding policy a project receives has no
line on what a function is (`skills/ai-init/templates/.ai/policies/coding.md`).
The record holds no case of padded code — the rules are preventive, and cheap.

**Outcome (testable).**
- With the dialog on, a user takes every routine human decision of a task from
  the runtime's question dialog; every message that reaches the human names a
  way out that needs no terminal, before the terminal one.
- A user sees, in the statusline and in the first line of `/rr-status`, whether
  the task waits on them and for what.
- On a TTY the installer is one coloured step wizard with back, a review screen
  before any write, and an uninstall; without a TTY or with `--yes` its output
  is byte-identical to 4.2.0.
- An implementer is told to write the simplest version and not to add a
  dependency; a reviewer reports padding and an unplanned dependency; in full
  mode the human sees, before approving, the places to read first.

**Affected.** End users of both runtimes; `hooks/`, `skills/ai-task/rr_state/`,
`skills/rr-build`, `skills/rr-spec`, `skills/rr-status`, `bin/`, `docs/`; by Q10
also `ai/agents/`, `agents/ai-reviewer.md.tmpl`, `skills/ai-init/templates/`,
`skills/rr-ship`.

**Constraints and non-goals.** `package.json` `dependencies` stay `{}`. Hooks
keep `python3 -I -S` and never import `rr_state`. With the dialog off, and under
`AI_UNATTENDED`, every byte is today's. Not here: `full_irreversible --confirm`,
the memory verbs other than `enable`, `update.py --confirm-delete` (all keep the
terminal), the single reader of the dialog switch (`docs/known-risks.md:160-170`),
removing values from Codex `config.toml` on uninstall, translations.

**Open questions.** None blocking; see the last section.

### Decisions taken

Recorded in `docs/sdlc/intent/ui-first-approvals.questions.md`. The file says
"by vanssa via prose"; in fact the session model chose every answer, on Ivan's
instruction of 2026-11-15 that decisions are this model's. Ivan can overturn any
of them by answering the question again.

- Q1 scope, one build cycle: dialog-first texts, picker-first questions, the
  statusline segment, the status first line, plain words in the dialog plus a
  glossary, the update through the dialog, the docs gaps, installer I1–I6, and
  the remaining human verbs in the dialog — narrowed by Q8.
- Q2 `full_irreversible --confirm` and the one-reader switch: not here.
- Q3 installer: zero-dependency ANSI on the existing Node menu child.
- Q4 the knowledge file: `docs/sdlc/specs/ui-first-approvals.lessons.md`.
- Q5 release: 4.3.0, the last step on this branch (`feat/ui-first-approvals`,
  cut from `main`), so the one PR's merge auto-releases.
- Q6 the live Remote Control probe is the human's, after the release; nothing
  in the design depends on its result.
- Q7 build: `/rr-build-all`, one cycle — sonnet implementers and fixers in
  parallel, haiku `log-reader` for every log, the session decides.
- Q8 (after the design) the dialog gains **only `batch on --by`**. The binding
  `.ai/policies/safety.md:30-33` says the memory verbs have no dialog route, and
  `--confirm-delete`'s typed name is the audit trail
  (`hooks/guard/paths_base.py:16-21`) — the argument that keeps
  `full_irreversible` on the terminal. One rule for all: an irreversible
  deletion keeps the terminal; a reversible lowering of rigor may be picked.
- Q9 uninstall stays in scope; still red after one fixer batch, it is deferred
  (flag not registered, planner and tests kept) and the cycle goes on.
- Q10 (Ivan's own answer, 2026-11-15, option B) tight code, from a reading of
  `LearnPrompt/andrej-karpathy-skills` (MIT; ideas reworded, no text copied):
  K1 simplest version first, K2 the reviewer looks for padding, K3 the
  dependency question, K4 and K5 three lines in the coding policy template, K6
  the places to read before approving — all in 4.3.0. K13, the platform's own
  diet, is the next step, for 4.4.0. Rejected, each with its reason in the
  session of that day: a size cap or diff-size sensor (removed on purpose,
  `tests/test_no_size_tokens.py`), a dependency audit in the core, a stop after
  N regressions (the budgets do it), a "must not require" line (non-goals do
  it), the skills as a layer of their own, a word cap on CLAUDE.md entries.

## Requirements

Axis in brackets (CLAUDE.md, C6). "Pick": a live pick of this session that
equals the command, run verbatim, once, inside the window. "Dialog off": today's
bytes. O1–O4 are the four outcomes above.

**Dialog (O1)**
- **R1 [2]** Both label twins (`rr_state/labels.py`, `hooks/guard/dialog.py`)
  accept `batch on --by S [--why S]` and refuse every other new form. Proof:
  `tests/test_dialog_contract.py` (twin equality, argv parity),
  `tests/test_dialog_gate.py`.
- **R2 [2]** `batch on --by`, dialog on, no pick: opens a decision (header
  "Batch"), prints the §Interfaces refusal, exits 5; the picked command passes
  with `via dialog` and `batch_set` carries the consent id. Proof:
  `tests/test_dialog_batch.py` (new).
- **R3 [2]** An `npx` pick is spent when it runs, as a git pick is, so its
  decision settles. C2: the failing test first, on today's tree, in
  `tests/test_dialog_consent.py`; if it is green there, no code changes and the
  lessons file says so.
- **R4 [2]** `decision open --kind install --command "npx riskrails@X.Y.Z --yes"`
  offers the update; exit 6 `INSTALL_DURING_TASK` while a task is in flight;
  refused with the dialog off as `--kind commit` is. Proof:
  `tests/test_dialog_human_verbs.py` (new).
- **R5 [0]** Still refused, one negative test each: any of the above without the
  pick, a pick run twice, after its window, from another session or a subagent;
  `approve` of `full_irreversible`; every memory verb but `enable`;
  `update.py --confirm-delete`; `decision settle --pick`; a pick lifting a git
  rule. Proof: `test_dialog_human_verbs.py::TestStillRefused`.
- **R6 [1]** Hook texts name the dialog first when it is on: the Stop hook's
  fallback, `CONSENT_REQUIRED`, the `approve` refusal, the budgets-mismatch
  line. The golden is re-recorded and `tools/golden-diff.py` shows reason text
  only, no allow/deny flip. Proof: `tests/test_dialog_first_hooks.py` (new).
- **R7 [1]** `state.py` refusals (batch, `start`, `verify`, `review`, the gate,
  gate questions, `close` for `full_irreversible`) name the dialog first when it
  is on. Proof: `tests/test_dialog_first_state.py` (new), table-driven: on —
  "dialog" before "terminal"; off — equal to today's constant.
- **R8 [1]** The update notice names the dialog first; SessionStart never opens
  a decision. Proof: `tests/test_update_notice.py`.
- **R9 [0]** What the dialog shows is in plain words (question text and each
  option's description); the agent-facing tokens (`DIALOG_PENDING`,
  `SUITE_BUDGET`) stay. Proof: `test_dialog_first_state.py::TestPlainWords`.
- **R10 [0]** `rr-build` §5 and `rr-spec` §2 put `ask` questions through the
  question tool when no decision is pending, and relay with `answer --via
  picker`; the file stays the record. Proof: `tests/test_picker_first_texts.py`
  (new), `tests/test_instruction_budget.py`.

**Visibility (O2)**
- **R11 [0]** Statusline segment (§Interfaces). No task and no open decision:
  byte-identical line; at most 10 ms more with 100 decisions. Proof:
  `tests/test_statusline_task.py` (new, with a `timed` case).
- **R12 [0]** With a task in flight or an open decision, `/rr-status` line 1 is
  `waiting on …`; otherwise the output is today's; `--json` gains `waiting`;
  the 20-line cap holds. Proof: `tests/test_ai_status_root.py`.

**Installer (O3)**
- **R13 [0]** Non-TTY and `--yes` stdout and stderr are byte-identical to 4.2.0.
  The golden is recorded on today's tree before any `bin/` edit. Proof:
  `tests/test_install_non_tty.py`, `tests/fixtures/install/non-tty.golden`.
- **R14 [0]** Colour goes to stderr only, and only with a TTY, empty `NO_COLOR`
  and `TERM` not `dumb`; a 4.2.0 menu spec draws byte-identically. Proof:
  `tests/test_install_menu.py`.
- **R15 [0]** Wizard: stepper, back, a description of the highlighted option,
  runtime checkboxes. Enter through every step, then Install, gives the same
  file tree as `--yes`. Proof: `tests/test_install_wizard.py` (pure),
  `tests/test_install_wizard_pty.py`.
- **R16 [0]** A review screen before any write: Install / Back / Cancel; Cancel
  exits 130 and the home is unchanged. Proof: the pty test.
- **R17 [0]** The final box names the next step and the equivalent flag command;
  that command with `--dry-run` prints the review's text. Proof: the pty test.
- **R18 [2, install]** `--uninstall`: on a seeded home every pre-existing file
  comes back equal except the printed "kept" items; nothing is deleted, only
  moved under `backups/`; idempotent. Proof: `tests/test_install_uninstall.py`,
  `tests/test_install_uninstall_plan.py`.
- **R19 [0]** A backup never overwrites another. Proof:
  `tests/test_install_backups.py`.

**Docs, record, release**
- **R20 [0]** `docs/glossary.md` (one page), `docs/dialog-probe.md` (the Remote
  Control / desktop / web checklist the human fills), `docs/installation.md`
  (uninstall, supported OS), `docs/faq.md` ("a pending decision holds every
  tool"), README: a wizard recording script and its placeholder;
  `docs/known-risks.md` updated for the install decision. A step that touches a
  shipped template or `ai/` runs `tools/build-template-history.py`.
- **R21 [0]** The lessons file has one row per step, written as the build goes.
  Its "review findings" cell counts the `padding:` findings on that step's
  files — "padding 0" is written, not left out.
- **R22 [0]** `tools/sync-version.py 4.3.0` and a `## [4.3.0]` CHANGELOG
  section; `sync-version.py --check` green.

**Tight code (Q10, O4)** — texts only; no guard decision and no `state.py`
refusal moves. Exact wording: §Interfaces. Proof for R23–R27:
`tests/test_tight_code_texts.py` plus the `doc_tests`.
- **R23 [0]** `ai/agents/implementer.md`, "While implementing": the simplest
  version that passes the step's tests; nothing a requirement or a failing test
  does not ask for.
- **R24 [0]** Both reviewer lists (`ai/agents/reviewer.md`,
  `agents/ai-reviewer.md.tmpl` "Look for") name padding: only in the lines the
  change added, last in the list and on a first pass only; MEDIUM at most,
  three findings at most, each titled `padding:` and naming what to delete. It
  never buys an `--after-fix` run.
- **R25 [0]** The implementer does not add a dependency: the standard library
  or a short function first, else `SCOPE_CHANGE_REQUIRED`. Both reviewer lists
  name a dependency without its line in the plan — outside the security focus
  too.
- **R26 [0]** `skills/ai-init/templates/.ai/policies/coding.md`, "General":
  one function one thing; inputs in, result out, IO at the edge; an error
  message says what failed, what was expected, what was found and the way out.
  The file's conventions still win in existing code.
  `tools/build-template-history.py` runs in the same step.
- **R27 [0]** In full mode the reviewer's output ends with `## READ FIRST` — at
  most five `file:line` and what it could not verify — and `/rr-ship` §2 shows
  those lines with the summary. `state.py review` is unchanged: it reads
  FINDINGS and the verdict line only (`rr_state/review.py:47-63`).
- **R28 [0]** `ROADMAP.md` names the next step, for 4.4.0: the platform's own
  diet — design limits in `.pylintrc` and the modules over 600 lines — as a
  refactoring of its own (C3), with the sizes measured on 2026-11-15.

## Design

**Labels and the human route.** Each twin holds the rule for `batch on` as data;
`test_dialog_contract.py` compares the two and feeds both the same generated
argv. `human_route` is unchanged; `cmd_batch` passes `allow_dialog=True` and, on
a refusal with the dialog on, opens its own decision as `start.py:160-166` does.
`decision open --kind install` is model-callable and validated strictly; the
decision gate (`hooks/guard/decision.py`) spends the `npx` pick.

**Texts.** One helper in `rr_state/dialog.py`, `human_refusal(what, cmd, why,
decision)`: with a decision it returns the dialog-first text, without one `None`
and the site prints today's string — so dialog-off bytes cannot move. Hooks get
dialog-on variants of the same constants beside the existing ones.
`labels.describe(argv)` gives each offered command its plain-words description.

**Questions.** Skill text only: `ask` already offers a question with up to
three options in the dialog (`questions_cmd.py:114-125`) and `answer --via
picker` exists (`cli.py:98`). The rule added: if `ask` printed `DIALOG_PENDING`,
send that; else, with no decision pending (a free question-tool call is denied
while one is, `decision.py:73-78`), use the question tool and relay.

**Statusline and status.** `runtime-gate.py` reads `.ai/state/state.json` and
the decisions with plain JSON, no guard import; `report.py` builds line 1 from
the pending decisions, the gate and the questions it already parses.

**Installer.** New pure modules: `bin/ansi.js` (the colour gate), `bin/wizard.js`
(`steps`, `flags`, `reviewLines`, `finalBox`), `bin/uninstall.js`
(`planUninstall`, `applyUninstall` with the installer's helpers injected).
`bin/menu.js` gains the stepper, back (exit 4), a help line and multi-select.
In `riskrails.js` the wizard runs after runtime detection when the menu is on,
sets every choice and its `*_GIVEN` flag, and the old menus never ask. The
review text comes from a child run of the installer itself with the chosen
flags and `--dry-run`, so the review and the dry run cannot drift. No code
moves out of `riskrails.js` (C3).

**Alternatives rejected.**
- Deriving the allowlist from the callers of `human_route`: hooks cannot import
  `rr_state`, and a future human-only verb would become pickable unreviewed.
- `permissionDecision: "ask"` instead of the dialog: the click is not in
  `consent.jsonl`, Codex has no `ask`, and an auto permission mode may pass it
  with nobody there.
- SessionStart opening the install decision: a pending decision holds every
  tool, so every session after a release would start blocked.
- An npm prompt library or a Python installer: `dependencies` stay `{}`; the
  Python installer was rejected in the redesign (`claude-agentic-redesign.md:165`).
- Time-stamping every backup: breaks R13 and the assertions that pin
  `backups/<date>`.
- Uninstall restoring whole files from a backup: loses edits made since install.
- Back by re-running `claudeRender`: it mutates state and asks its own menus.

### Build protocol (Q7)

Mode: `start --mode full --by <name> --declare behaviour=2:"a dialog pick passes
batch on; npx picks are spent; the install decision; --uninstall"` — the human's
pick in the dialog.

| Who | Model | Does |
|---|---|---|
| the session | this model | the plan, wave dispatch, every conflict and fix-or-defer, the lessons rows, s16 |
| implementers, fixers | sonnet | one step each, inside its files, its own tests |
| `log-reader` | haiku | every suite, golden-diff and CI log: `file:line` excerpts, never the log |
| `ai-reviewer` | the mode's tier | one review, focus list: R1, R3, R4, R18 |

Rules that keep one cycle honest: a step's tests run before it reports; a
failure goes to one fixer batch per wave; a thinking task that failed is not
retried on a cheaper model; the whole suite runs once, after the last wave.

The steps, their files and their order are the plan's:
`docs/sdlc/plans/ui-first-approvals.md`, **Order of work** — seventeen steps in six waves,
at most five agents at once.

### Tight code (Q10)

Six sentences in four texts the agents already read, and one section in the
reviewer's output. Nothing is measured and nothing gates: the implementer is
told, the reviewer reports, the human reads. The reviewer is the only
enforcement, so R23 without R24 would be a wish.

- **Where.** The implementer and the reviewer contracts are shared files
  (`ai/agents/`), read from the plugin by every project that has not overridden
  them — the change reaches them with the install. The coding policy is a
  project file: a new project gets the lines from the template; an existing
  one through `/rr-setup --update`, which replaces an unedited copy and leaves
  an edited one for the human.
- **A dependency** is already a decision with its own line in the plan
  (`ai/workflows.md:17`). R25 adds the question that comes before the decision
  and gives the implementer the refusal it already has; no new signal.
- **`READ FIRST`** is the reviewer's, not the session's: `/rr-ship` §3 allows
  no new opinion, so the list of places comes from the one agent that read the
  system. Full mode only — that is where a human approves a tree.
- **This build is the first measurement.** The installed plugin is 4.2.0 and a
  policy is frozen during a task, so the session carries the Q10 sentences in
  its own briefs: every implementer brief of this plan holds the two
  implementer lines and the three coding lines, and the reviewer's brief holds
  the two list items and `READ FIRST`. Seventeen steps written under the rules
  and one review that counts `padding:` findings give the number the record
  lacks. The count is of findings, never of lines: no size is measured.
- **Exit.** The 4.4.0 spec reads that number first. No `padding:` finding in
  4.3.0 or in the tasks up to then: R24's item is reconsidered — kept as it
  is only with a reason written there.

Rejected:
- A diff-size or line-growth sensor: removed in the redesign because the number
  distorted the picture (`docs/redesign-analysis-2026-10-24.md:53-55`); a test
  forbids its names.
- A `/rr-minimal` skill, or the source skills installed as they are: one more
  trigger and one more text to read, for rules that fit in six sentences.
- A function-size limit in the template: a number invites the split that the
  "three call sites" rule exists to prevent.
- Padding as a HIGH finding: it would buy a suite run and a review round for a
  matter of taste.

## Interfaces

**Label.** After `python3 … state.py [--root R] [--runtime T]`:
`batch on --by S [--why S]` — each option once, as two words, a value non-empty
and not starting with `-`.

**`decision open --kind install`.** Header "Install"; options "Not now — keep
`<v>`", then the label. Question: "Install RiskRails X.Y.Z (installed `<v>`)? It
rewrites the hooks, skills and settings under `<home>`; restart the session
afterwards."

**Refusal with a decision** (exit code unchanged):
`APPROVAL_REFUSED — <what> is the human's. Ask them in the dialog: send
DIALOG_PENDING <D> (printed above), then run the command they pick, verbatim,
once. Or they run, in their own terminal:\n  <cmd>\nRefused because <why>.`

**Budget questions.** "The test suite has run `<n>` times; this task allows
`<m>`. Run it once more?" · "`<n>` review passes so far; this task allows `<m>`.
The next verdict is yours."

**Stop hook fallback.** `DECISION_PENDING <ids> is still open. Reply in this
chat (for example "ask me again") and the session sends you the dialog; or
settle it in your terminal: <command>`. A new prompt resets the per-turn count.

**Update notice.** `RiskRails <l> is available (installed <v>). Say "update
RiskRails" and the session asks you in the dialog — or run npx -y
riskrails@latest --yes in a terminal; then /rr-setup --update in each project.`

**Statusline segment**, on `--line` after the branch: `<task> · <mode> ·
<stage>`, and when something waits ` waiting on you: D3 D4 Q2 G1` (at most three
ids per kind, then `+n`); no task but open decisions: `riskrails · waiting on
you: D3`.

**Status line 1.** One of: `waiting on you: D3 Approve, D4 Commit — the dialog
('state.py decision show' sends it again)` · `waiting on you: gate G1 — approve
in the dialog ('state.py close' offers it) or in your own terminal` · `waiting
on you: Q2, Q4 — answer in the dialog or the chat, or fill [Answer]: in
<task.md>` · `waiting on the agent: <stage> — <next action>`. With no task and no open decision the output is
today's. `--json`: `"waiting": {"on": "you|agent|nobody",
"decisions": [], "gate": null, "questions": []}`.

**Installer.** `--uninstall`, allowed only with `--target`, `--home`,
`--codex-home`, `--dry-run`, `--yes` (else exit 2); without a TTY it needs
`--yes` or `--dry-run`. `NO_COLOR` non-empty turns colour off; `TERM=dumb` or
`RISKRAILS_MENU=off|0` gives today's typed prompts. Installer exits: 0, 1 error,
2 usage, 130 cancelled with nothing written. Menu child: 0 pick, 3 no terminal,
4 back, 130 abort; new spec keys `help`, `multi`, `checked`, `step`, `back`,
`color`.

Keys: ↑/k ↓/j move · Home/End · 1–9 jump · Space toggles (runtimes) · Enter or →
confirms · ←, h or Backspace back · Esc, q, Ctrl-C abort.

```
 step 3 of 6 · runtimes › plan › [context] › statusline › codex plan › review

  context
  ❯ default   each runtime's own context window and compaction
    economy   the plan's autoCompactWindow; a prompt past 120% is held back

  ↑/↓ move   ← back   Enter next   Esc cancel
```

Review: "Review — nothing is written until you pick Install", the dry run's
text, `same as: <command>`, then Install / Back / Cancel. Equivalent command:
`npx riskrails@<ver> --target <t> [--plan P --fable F --statusline S]
[--codex-plan P] --context C --yes`.

**Uninstall.** Moved under `backups/<stamp>/`, never deleted: the agents, hook
files, skills, `riskrails/`, `bin/claude-1m`. Edited after a backup: our hook
entries removed, `statusLine` restored from `statusline.json`, other settings
keys removed only where equal to the snippet the recorded plan renders, the
managed block removed. Kept and printed: settings keys that differ, Codex
`config.toml`, the plugin, every project's `.ai/`.

**Backup stamp**, per home per run: `backups/<YYYY-MM-DD>/` when it does not
exist, else `backups/<YYYY-MM-DD>T<HHMMSS>/`, else the same with `-2`, `-3`.

**Lessons file.** `| step | files | agent / model | first try green | problems
(error text, at most two lines) | what fixed it | review findings | tokens |
what the base behaviour should change |` — "none" is a finding too.

**Tight-code texts** (R23–R27), as they are added.

`ai/agents/implementer.md`, under "While implementing":

```markdown
- Write the simplest version that passes the step's tests. A branch, an option,
  a parameter or a layer is added only when a requirement or a failing test
  asks for it.
- A new dependency is not yours to add. Ask first whether the standard library
  or one function of about fifty lines does the job; when it does not, return
  `SCOPE_CHANGE_REQUIRED` naming the manifest and the reason.
```

`ai/agents/reviewer.md` "Look specifically for" and
`agents/ai-reviewer.md.tmpl` "Look for", the same two items in each list's own
punctuation:

```markdown
- padding, last and on a first pass only, in the lines this change added: an
  abstraction with one implementation, an option nobody sets, a block or a test
  that repeats another, lines no requirement and no test asks for — MEDIUM at
  most, three findings at most, each titled `padding:` and naming what to
  delete;
- a new dependency without its line in the plan, or one the standard library
  or a short function would replace;
```

`agents/ai-reviewer.md.tmpl` "Output", after VERDICT, full mode only:

```markdown
## READ FIRST
- <file:line> — <why a human reads this before approving>   # at most five
unverified: <what the review could not check, and what would check it>   # or: none
```

`skills/ai-init/templates/.ai/policies/coding.md`, at the end of "General":

```markdown
- A function does one thing and its name says which. When the name needs
  "and", split it.
- Inputs come in as parameters and the result goes out as the return value;
  files, the network and the clock stay at the edge, in the caller.
- An error message says what failed, what was expected, what was found, and
  the way out.

In existing code the file's conventions win; the last three lines hold for the
functions you add.
```

`skills/rr-ship/SKILL.md` §2: "Show the human the summary (§3), the review's
`READ FIRST` lines, the open findings, the rollback, and that command
**verbatim**".

## Policy conformance

- **C1.** Dialog off and `AI_UNATTENDED`: today's bytes, pinned by R7's off
  cases and R13's golden.
- **C2.** R3 starts with the failing test; s5 records the installer's
  characterization golden before s10 touches `bin/`.
- **C3.** No code moves out of `riskrails.js`; the new modules are additions.
- **C4.** Sixteen steps with disjoint files per wave; scope grows by `--amend`.
- **C5.** Every new route is a command the human picked, run verbatim, once;
  no agent approves, merges or deploys. The release is the human's merge.
- **C6 and CLAUDE.md.** Behaviour 2 is declared for exactly four effects and
  the task starts in full mode. Each moved refusal has a positive test and its
  negatives (R5) — a BLOCKER is closed by a test. No new pattern over command
  text is added to the bash guard; if a step adds one, it adds its `timed`
  case beside `tests/test_ai_path_guard.py:398-413`.
- **`.ai/policies/safety.md`.** Untouched: the memory verbs and deletions keep
  the terminal (Q8). The threat model stands — a pick is recorded, not proven.
- **Testing policy.** `state.py verify --scope all` once, after the last wave.
- **Tight code (R23–R28).** C3: K13 is a refactoring and stays out of this
  feature — R28 only names it. C6: texts only, behaviour 0. The new coding
  lines sit under the template's first rule, the file's conventions, and beside
  "no new abstraction until three call sites" (`coding.md:9-12`), which they
  do not replace. `tests/test_no_size_tokens.py` stands: no size is named, no
  size gates. `tests/test_instruction_budget.py` stands: the added lines are
  inside the budgets or the step reports the number.

## Flagged concerns

1. **Recorded as the human's, decided by the model.** `state.py answer` wrote
   "by vanssa via prose" for Q1–Q9. `ROADMAP.md:39-42` already asks for a
   self-answer's own `via`; until it exists, this spec's note is the only trace.
2. **Remote Control is unverified.** No doc mentions it and nobody has run the
   dialog there. If the session is reported unattended
   (`CLAUDE_CODE_SESSION_ATTENDED=0`) or without a session id, the dialog is off
   (`docs/hooks.md:186-193`) and none of O1 reaches that user; "Reply in this
   chat" assumes a prompt reaches the same session. `docs/dialog-probe.md` asks
   exactly these; a "no" becomes the next spec, not a fix here.
3. **Policy against intent.** The intent wants approvals without a shell; the
   binding safety policy keeps the memory verbs on the terminal. Resolved in
   favour of the policy (Q8), so a terminal-less user still cannot run `memory
   disable|cleanup|pack|redact`, `--confirm-delete` or approve a
   `full_irreversible` task. The glossary and the FAQ say so.
4. **R3 is a bug found by reading.** Only `git.py:284`, `decision.py:91` and
   `dialog.py:448` append a `use`; no test has shown an `npx` pick stays
   pending. The failing test decides.
5. **The two switch readers** (`docs/known-risks.md:160-170`) now also cover
   the install decision and `batch on`; their fallback is still "use the
   terminal". Accepted, written into the known-risks entry by s15.
6. **Size.** Seventeen steps, about 3k changed lines and one review is at the
   edge of one cycle. The pre-agreed cut is uninstall (Q9); the next is the wizard's
   review screen (s13), never a dialog step. Of the Q10 texts, R27 is cut
   first: it is the only one that changes what the reviewer returns.
7. **`fix/ere-lazy-compile`** (`5e0a2a8`) is not on `main` and edits the guard.
   Ivan chose on 2026-11-15 to merge it first (PR #82) and rebase this branch
   before the task starts.
8. **Uninstall leaves Codex `config.toml` values** — `merge-codex-config.py` has
   no remove mode. Printed as kept; a follow-up.
9. **Q10 answers a problem the record does not show.** No lesson, risk or
   review in this repository reports padded code; the measured cost follows the
   mode, not the size (`docs/sdlc/specs/direct-mode-diet.md:135-141`).
   Answered, with Ivan, on 2026-11-15: this build is the first measurement —
   the briefs carry the rules, the review counts `padding:` findings, the
   lessons rows record the count (R21), and the 4.4.0 spec reads it first
   (§Design, Exit). What stays open: there is no number from before the rules.
   A reading of the last three merged diffs against the same list would give
   one; not done, because 4.3.0 gives the first number anyway.
10. **Policy against policy, inside one file.** "Follow the conventions of the
    file" and "a function does one thing" disagree in a file of long functions,
    and this repository's own `.pylintrc` switches every design limit off as
    house style. Answered: conventions win in existing code, the new lines
    hold for added functions, and the reviewer reports padding only in the
    lines the change added — a rule the diff can check. What stays open: this
    repository's compact house style is not written in its `coding.md`
    "Project specifics"; that file is frozen during the task and is Ivan's to
    extend after the release.
11. **The reviewer may spend its budget on taste.** Answered: padding is the
    last item, never in place of another, on a first pass only — a re-review
    after remediation keeps its two questions — three findings at most, none
    above MEDIUM, none buys a run. If reviews still grow longer, the cap drops
    to one.
12. **This project's own `.ai/policies/coding.md`** is identical to the
    template and is frozen during the task, and the installed plugin is 4.2.0.
    Answered for the build: the session's briefs carry every Q10 sentence
    (§Design), so 4.3.0 is written and reviewed under the new rules without a
    policy edit. The project's copy receives the three lines when Ivan runs
    `/rr-setup --update` after the release. Adding them by hand before the
    start was rejected: a copy that differs from the future template by one
    byte is an edited copy for `project-update`, and waits for the human.
13. **The source is unverified.** The skills attribute their rules to Andrej
    Karpathy with like counts and post links nobody here checked, and the
    repository is derived from another. Answered: no rule rests on the
    attribution. No shipped text carries the name; the CHANGELOG credits the
    repository as what was read, not as an authority; nothing is quoted, so
    its MIT licence asks for nothing. The original posts were not checked —
    the result would change no line here.

## Open questions

- How many installer suites run two installs in one day and pin
  `backups/<date>`? s10 counts them before it changes the stamp. Owner: s10.
- May `report.py`'s layer import the ledger reader (`docs/architecture.md:106`)?
  Owner: s12.
- Follow-up spec, after the probe: the memory verbs and `--confirm-delete` in
  the dialog, with the policy change. Owner: Ivan.
- Which suites or goldens pin the bytes of `ai/agents/implementer.md`,
  `ai/agents/reviewer.md`, the reviewer template or the coding template
  (`tests/test_shared_tree.py`, the installer's dry-run lists, the
  `project-update` history)? Owner: s17, counted before the first edit.
- Does Codex install its own copy of the reviewer text, apart from
  `agents/ai-reviewer.md.tmpl`? Owner: s17; a second copy gets the same lines.
- Follow-up spec for 4.4.0, the platform's diet (K13, R28): which design limits
  come back in `.pylintrc` and in what order the modules over 600 lines are
  split (`hooks/runtime-gate.py` 1275, `bin/riskrails.js` 1578 first). Owner:
  Ivan, after the release.
