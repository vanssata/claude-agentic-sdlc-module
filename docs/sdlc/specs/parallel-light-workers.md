# Spec: Parallel light workers, native plan mode, simplify before close, review limit lift, plan rename

## Intent

**Problem.** Every stage (intent, spec, plan, build) runs on the session model alone; only `/rr-build-all` fans out
(`skills/rr-build-all/SKILL.md:71-84`). Plan mode is named for guarded (`.ai/policies/weight.md:19`) but no skill
enters it. A task closes without a simplify pass. A spent review budget offers only a human verdict
(`skills/ai-task/rr_state/review.py:84-110`), never more passes. The plan profiles carry old names (`max20`, Codex `pro`).

**Outcome.** (as amended by decisions 7–15)
- A user can pick, as an optional extra step, parallel light-model workers (Claude: Sonnet writes, Haiku reads;
  Codex: the profile's BALANCED/FAST) for intent/spec/plan, for implementation, and a deep-research sweep —
  every decision stays with the session model.
- Guarded and full planning, and the intent/spec brainstorm, run inside the runtime's native plan mode.
- Before every close the user is asked Simplify / Skip.
- When the review budget is spent the user can lift it for that task.
- Plan profiles use the current names (Claude Pro/Max/Ultra; Codex Free/Go, Plus, Pro 100/200/500, Business).

**Affected.** Skills rr-spec, rr-plan, rr-build, rr-build-all, rr-review, rr-ship, rr-setup; `state.py`
(`rr_state/` choices, review, policy, start, steps, handoff, journal, profile); profiles; installer
(`bin/riskrails.js`, wizard); `hooks/context-guard.py` names; shipped `ai/` templates and `instructions/`.

**Constraints and non-goals.** Entirely optional (shipped default `ask`); scope guard unchanged; no worktree
per worker; no new hook; no guessed model ids; no change to SUITE_BUDGET.

**Open questions.** See §Open questions; none is blocking for WP0–WP1.

### Decisions taken

From `docs/sdlc/intent/parallel-light-workers.questions.md`:

1. **Q1 — how often the workers choice is asked:** a combination. Project default `workers`/`research` =
   `ask|on|off` (shipped `ask`). Under `ask`, one question at the task's first stage: workers for the whole task /
   current model for the whole task / ask every stage / workers + save as project default; stored in task state.
   Later stages re-ask only under "every", else print one line with how to change it. Deep research: same layers,
   but under `ask` it is asked at every stage.
2. **Q2 — where workers write:** same tree; only steps with disjoint files run in parallel; the session integrates
   and decides (A).
3. **Q3 — review budget spent:** a new option in the existing dialog lifts the limit for this task only; journaled;
   later verdicts are ordinary (A).
4. **Q4 — simplify:** ask Simplify / Skip; Claude `/simplify`, Codex the same pass on BALANCED; edits inside the
   task's files; verify reruns (A).
5. **Q5 — plan mode:** guarded and full plan inside native plan mode (full: the written plan drafted there,
   approved via ExitPlanMode); intent/spec brainstorm in plan mode, read-only; light stays inline (A).
6. **Q6 — cap:** from the plan profile, overridable in project settings; Claude pro 2, max 8, ultra 12; Codex
   plus 2, pro-100 8, pro-200 12, pro-500 12. Rename profiles to the current plan names; refresh Codex model ids.

Spec review round (ikakarov, 2026-11-26), overriding the above where they differ:

7. **Simplify placement (FC6):** stays as Q4 says — before close, in every mode; FC6 is closed.
8. **Review-limit lift (FC1):** the lift is the human's decision; the "never a third pass" lines are rewritten so.
9. **Single session vs workers (FC2–FC4):** chosen at the choice point, and also settable at project
   initialisation (`/rr-setup`); rules, routing text and the rendered CLAUDE.md block describe both behaviours,
   the one that applies chosen by the setting.
10. **Light-mode stops (FC5):** accepted as mitigated.
11. **Caps (FC10):** back to the norms — Claude ultra 6, max 4, pro 2; Codex pro-200/pro-500 6, pro-100 4, plus 2.
12. **Unattended lift (FC15):** refused — confirmed.
13. **OQ4:** yes — a pick made at intent carries to every row-task of the programme plan.
14. **OQ5:** yes — `max_parallel` is a `--options` question. (superseded by D21: a level)
15. **OQ6:** no — an old Codex `pro` install is not aliased to `pro-200`; the human picks pro-100/200/500.

Remaining open questions delegated to the spec author by ikakarov ("прецени ти", 2026-11-26):

16. **OQ1:** Codex `free`/`go` (go amended by D20) get a profile with `max_parallel` 1 — the workers and research questions are not
    asked there (one line says why). `business` inherits `pro-100` (cap 4). `pro-100` and `pro-500` inherit
    `pro-200`'s token budgets unchanged (INFERENCE: budgets cap one task, not the plan's quota).
17. **OQ2:** WP8 takes the Codex model ids from the installed Codex CLI (its model list/picker) at implementation
    time, recorded with CLI version and date in `profiles/codex-models.json`; third-party pages are not a source.
    If the CLI does not list them, WP8 is skipped and today's ids stay.
18. **OQ3:** yes — `workers.json` gains `simplify: ask|on|off` (shipped `ask`), asked in setup; `off` removes the
    stop, which also answers FC5 for light mode.
20. **OQ1 amended (ikakarov):** Codex `go` gets the workers of the entry Pro tier — cap 2, like Claude `pro` and
    Codex `plus`; only `free` stays at 1 with no workers question.
21. **Worker level (ikakarov):** the number of workers is configured as a level, not a raw number:
    `none` (0 — single session, workers off) · `low` (2) · `medium` (4) · `xhigh` (6) · `max` (the most the
    runtime the task runs in allows: Codex `agents.max_concurrent_threads_per_session`; Claude's parallel-agent
    limit as WP0 measures it). Replaces the `max_parallel` number of D14. (Levels narrowed to four by D22.)
22. **Four levels (ikakarov):** so the level fits one dialog decision, it has exactly four values —
    `low` (2) · `medium` (4) · `xhigh` (6) · `max` (runtime limit). `none` is dropped: a single session is
    `workers=off`, already its own setup question. "Plan default" is not an option either: the plan profile
    carries a default *level* (Claude pro, Codex go/plus → low; Claude max, Codex pro-100/business → medium;
    Claude ultra, Codex pro-200/pro-500 → xhigh), preselected as the recommendation. Codex `free` has workers off.
19. **FC11:** this account reports `organizationRateLimitTier default_claude_max_5x` → plan `max` (new naming
    Max), cap 4; detection is right, the memory note saying Max 20x was stale.

## Requirements

- **PLW-R1 (Q1, D18).** Project defaults in `.ai/policies/workers.json`: `workers`, `research`, `simplify` ∈
  `ask|on|off`, `workers_level` ∈ `low|medium|xhigh|max|null` (null = the plan profile's default level; D22). Missing file = ask/ask/null; bad value → shipped default with a warning.
- **PLW-R2 (Q1, D9, D14, D21).** `/rr-setup` (initialisation) and `/rr-setup --options` ask `workers` (single
  session / workers / ask each task), `research` (ask/on/off), `simplify` (ask/on/off) and `workers_level`
  (low / medium / xhigh / max — one four-option decision, the plan's level recommended; D22).
  No dialog call exceeds 4 questions; setup pages with `OPTIONS_NEXT`.
- **PLW-R3 (Q1).** Under `workers=ask` the first stage of a work item asks one four-option question (whole task on /
  whole task off / every stage / on + save default). Before `start` the pick lives in the topic questions file;
  after, in task state; journaled `choice_set`.
- **PLW-R4 (Q1).** Later stages re-ask only under "every" (three options); otherwise exactly one line with value,
  source and the change command.
- **PLW-R5 (Q1).** "Save as project default" writes `workers.json` only with no task in flight; else prints the
  command to run after close.
- **PLW-R6 (Q1).** Under `research=ask` the research question is asked at every stage (intent, spec, plan); on/off
  print one line. When both are owed at one stage they share one dialog call.
- **PLW-R7.** Workers write on BALANCED, read on FAST (`state.py profile --tier`); three or more parallel workers
  never above BALANCED; decisions stay with the session.
- **PLW-R8 (Q2).** Workers on at build: ready steps go in waves to implementer subagents in the same tree; only
  steps `start` left disjoint run together; only the session runs `state.py`; scope guard unchanged; procedure
  text shared with `/rr-build-all`; a light task gets one implementer.
- **PLW-R9 (Q2).** Workers on: a red suite or a review fix batch goes to fixers grouped by file; the session
  classifies every failure.
- **PLW-R10 (Q6, D11, D22).** Cap = `workers.json workers_level` (low 2 / medium 4 / xhigh 6 / max = runtime
  limit) → (batch task only) overlay `batch.parallel` → profile `riskrails.workers.level` → medium; Codex clamped to `agents.max_concurrent_threads_per_session`. Printed with
  its source by `choice show` and `steps --json`. The `batch.tier` refusal (`policy.py:103-105`) keeps its input.
- **PLW-R11 (D11).** Caps: Claude pro 2, max 4, ultra 6 (team-*, balanced-max inherit); Codex plus 2, pro-100 4,
  pro-200 6, pro-500 6, business 4 (inherits pro-100), go 2 (D20), free 1 — no workers or research question (D16).
  All within Codex's 6 threads. Expressed as profile levels (D22): 2 = low, 4 = medium, 6 = xhigh; free has
  workers off. A project level always overrides the profile's; every value is clamped to the runtime limit, and
  the clamp is printed.
- **PLW-R12 (Q6).** Claude plan ids `pro|team-pro|team-max|max|ultra|balanced-max`; `max20|max-20x|max_20x` alias
  `ultra` everywhere a plan is given or read (installer flags, `profile.json`, `drift-ack.json`, `profile set`).
  An old max20 install on an Ultra account reports `same`.
- **PLW-R13 (Q6, D15).** Codex plan ids `free|plus|pro-100|pro-200|pro-500|business|balanced-max`. An installed
  `pro` has no alias: it reports drift and the installer/drift dialog asks the human for pro-100, pro-200 or
  pro-500, keeping today's tables until they pick. Detection table-driven; unrecognised `chatgpt_plan_type`
  stays `unknown`.
- **PLW-R14 (Q6, D17).** No Codex model id enters a profile unless it is on a confirmed list with source and date
  (`profiles/codex-models.json`); the refresh is a separate data change after human confirmation.
- **PLW-R15 (Q5).** Guarded and full planning run inside plan mode; `start` only after approval; light inline.
  Claude: EnterPlanMode (or the human's Shift+Tab) → draft → ExitPlanMode; full: the plan is stored by
  `start --plan-doc`.
- **PLW-R16 (Q5).** Intent/spec brainstorm and design run inside plan mode, read-only; the spec file is written
  after leaving it. Questions recorded live through `state.py` if plan mode allows it (WP0), else in one batch
  right after leaving.
- **PLW-R17 (Q5).** Codex: one line asks the human to enter `/plan`; otherwise plan inline, read-only, accept via
  the existing dialog question. Never claim a plan mode not observed.
- **PLW-R18 (Q4, D7).** Every task asks Simplify / Skip as a keyed question right before close, in every mode. Claude `/simplify` (fallback: BALANCED
  simplifier brief); Codex the brief. Edits only in the task's files and own hunks; scope never amended for
  simplify; `verify --scope all` after; tree before/after recorded.
- **PLW-R19 (Q3, D8, D12).** At REVIEW_BUDGET the dialog gains a second decision "Review limit" offering
  `review --unlimited --by <name>`: human route only (terminal or dialog pick; unattended refused), only once the
  budget is spent; journaled `review_budget_lifted`; later passes ordinary verdicts checked by
  `verdict_matches_findings`; covers standard and batch budgets; SUITE_BUDGET untouched.
- **PLW-R20.** Handoff and status show workers/research picks, cap and source, review-limit state, simplify state;
  all survive `/clear` and a runtime switch.
- **PLW-R21 (C1).** A task in flight at upgrade resolves workers and research to off, with one line; never
  re-asked mid-task.
- **PLW-R22 (D8).** Policy text aligned: the review-budget lines say the lift is the human's decision (FC1).
- **PLW-R23 (D9).** Rules, `instructions/routing.md`, `instructions/stub.md` and the rendered CLAUDE.md /
  AGENTS.md block describe both behaviours — "the session implements" (single session) and "workers implement
  file-disjoint steps, the session decides" — and say which applies by the project's `workers` setting and the
  task's pick. Codex text drops "write-heavy work is not fanned out" for "only file-disjoint steps" and states
  BALANCED for implementers.
- **PLW-R24 (D13).** A pick recorded at a programme intent/spec carries to every row-task `start`ed from that plan
  (`start --from-topic`), unless the human changes it.

## Design

### Components

| Component | Responsibility | Interface |
|---|---|---|
| `.ai/policies/workers.json` (new, the human's) | project defaults | file |
| `rr_state/choices.py` (new) | resolve/record workers, research, simplify picks; sole writer of `state.choices` | `state.py choice show/ask/set` |
| `rr_state/questions.py`, `questions_cmd.py` | `key:` line on a question; a keyed answer calls `choices.record` | CLI unchanged |
| `rr_state/start.py` | import picks; store the written plan | `--from-topic`, `--choice`, `--plan-doc` |
| `rr_state/policy.py` | the cap | `workers_cap(root, policy, state, rt)`; `budget()` unchanged |
| `rr_state/review.py` | lift the review limit | `review --unlimited --by`; two-decision budget dialog |
| `steps.py`, `handoff.py`, `report.py`, `journal.py` | cap in `steps --json`; status lines; two events | §Interfaces |
| `rr_state/dialog_cmd.py`, `skills/rr-setup/setup.py` | setup keys, paging, writing `workers.json` | `SETUP_VALUES`, `workers --set` |
| `ai/workers.md` (new, shared) | Waves, Fixers, Research procedures and briefs | read by rr-build, rr-build-all, rr-plan, rr-spec |
| `ai/agents/simplifier.md` (new) | simplifier contract | brief for `/simplify` and the BALANCED pass |
| profile layer | ids, aliases, caps, detection | profiles/*.json, `resolve-profile.py` ALIASES, `profile.py`, `riskrails.js`, wizard, `context-guard.py:501` |

### Data flow

```
/rr-spec  intent ─ choice ask --kind workers,research --stage intent --topic S ─► questions.md (key: lines)
          spec   ─ choice ask --kind research --stage spec --topic S
/rr-plan  weight (inline) → guarded/full: EnterPlanMode → [research readers] → draft → ExitPlanMode
          start --from-topic S | --choice workers=on [--plan-doc PATH] ─► state.choices, plan.md, choice_set
/rr-build choice ask --kind workers --stage build → on: ai/workers.md Waves (cap from steps --json)
          → RESULT → step-done (session) → verify → red: Fixers
          choice ask --kind simplify --stage close → /simplify | BALANCED simplifier → verify --scope all
/rr-review REVIEW_BUDGET → [D_a verdict, unchanged] + [D_b review --unlimited] → review.unlimited
/rr-ship  close unchanged
```

### Key decisions

- **Where a pick lives.** Project default: `workers.json`. Before `start`: the topic questions file (keyed
  question — picker, prose, `[Answer]:`, `--sync` routes all work, no `.ai/` needed). After `start`:
  `state.choices`; `start --from-topic S` copies keyed answers (not `--topic`, which switches to topic mode,
  `cli.py:192`). Plan-first with no topic: question tool, then `start --choice workers=<v>`.
- **Dispatch is reused.** WP1 (refactoring, C3) moves `/rr-build-all` §3 Waves and §4 Fixers into
  `ai/workers.md`. `/rr-build` with workers on follows it but keeps standard budgets and the scoped re-review:
  workers change *who* implements, batch changes *rigor*.
- **Session sees results, not diffs.** The session reads `git diff --stat` and RESULT blocks; the reviewer reads
  the diff (FC12).
- **Plan mode.** Claude: `state.py weight` inline → EnterPlanMode (or Shift+Tab prompt) → readers → draft →
  ExitPlanMode → `start --plan-doc <plan path>` copies it to `.ai/reports/<id>/plan.md` with sha256. rr-spec:
  plan mode covers brainstorm and design; leave it before writing the file. Codex: one line to enter `/plan`;
  plan as a message; acceptance through the existing question; never asserted.
- **Simplify** runs right before close in every mode (D7). While pending, `close` exits 4 (existing rule).
- **Review limit.** `passes >= rounds and not review.unlimited`; `budget()` stays an int (`%d` callers safe);
  displays add "· limit lifted by X at pass N". No hook change: `hooks/guard/paths_human.py:42` already denies
  `review … --by` without the live pick.
- **Rename.** One alias map in `resolve-profile.py`, mirrored in `profile.py` and `riskrails.js`; plan
  normalised wherever compared (detection, `acknowledged()`, `SAME_TIER`, `prevPlan`, context-guard names).
  `profiles/ultra.json` replaces `max20.json`; `codex-pro.json` → `codex-pro-200.json`, plus `codex-pro-100.json`,
  `codex-pro-500.json` inheriting it. Codex `pro` is deliberately not aliased (D15): the human picks the tier.

### Alternatives rejected

1. Workers = `batch on` — brings batch budgets and full-pass reviews (`policy.py:115-123`); `batch on` mid-task is
   the human's (`steps.py:105-118`).
2. A `choices.json` sidecar — a second record of a human decision without the existing answer routes.
3. A fifth option in the REVIEW_BUDGET decision — impossible, the cap is 4 (`dialog.py:252`).
4. `review_rounds_max: unlimited` project setting — rejected by Q3; a standing policy, not a per-task pick.
5. A worktree per worker — rejected by Q2.
6. Cap = min(profile, project) — Q6 says the project overrides.
7. Stub `max20.json`/`codex-pro.json` inheriting the new files — two sources that drift.
8. Recording ExitPlanMode and refusing `start` without it — deferred: a hook change plus a new refusal not asked for.

## Interfaces

**`.ai/policies/workers.json`**
```json
{"version": 1, "workers": "ask", "research": "ask", "simplify": "ask", "workers_level": null}
```
Written by `setup.py workers --set workers=ask|on|off [research=…] [simplify=…] [workers_level=low|medium|xhigh|max|null]`; exit 3
`TASK_IN_FLIGHT` while a task runs; exit 2 on a bad value; `--update` never rewrites it.

**Profile key** `riskrails.workers.level` ∈ `low|medium|xhigh|max|off` (D22); `off` only for Codex free.

**`state.py`**
```
choice show [--json] [--topic SLUG]
choice ask  --kind workers[,research]|research|simplify --stage intent|spec|plan|build|close [--topic SLUG]
choice set  <kind>=<value> [--stage S] [--topic SLUG] --by NAME --why TEXT
start … [--from-topic SLUG] [--choice workers=on|off|every]… [--choice research=on|off] [--plan-doc PATH|-]
review --unlimited --by NAME
steps --json   → adds "cap": {"n": 4, "from": "project:medium|profile:max→medium|runtime", "clamped_by": null}
```
`choice ask` exits 0; first line `CHOICE workers=on source=… by=…` (+ change line) | `CHOICE_ASK Q<n> <kind>` |
`CHOICE_UNRECORDED <kind>`.

**Keyed questions.** `key:` line after `asked:`, `^key: ([a-z]+(\.[a-z]+)?)$`. `workers`: A on, B off, C every,
D on + save default. `workers.<stage>`: A on here, B off here, C on for the rest. `research.<stage>`: A on, B off.
`simplify`: A run, B skip. An `X:` answer leaves the key unresolved → `choice set`.

**Dialog texts.**
- Workers: "Workers for <slug>? Up to <n> parallel light-model workers (<BALANCED> writes code, <FAST> reads) do
  the work; every decision stays with this session." — A "Workers for the whole task", B "Current model for the
  whole task", C "Ask me at every stage", D "Workers for the whole task, and make it this project's default".
- Research: "Deep research before the <stage> of <slug>? Up to <n> parallel <FAST> readers; this session writes
  the conclusions." — A "Run deep research for this stage", B "Skip it".
- Simplify: "Simplify the change before close? Edits stay inside the task's files and its own lines; the
  suite runs again." — A "Simplify", B "Skip".
- D_b "Review limit": "Keep the limit — the next verdict stays mine" | command
  `state.py review --unlimited --by <name>` ("lifts the review limit for this task only; journaled").

**Task state, schema 7, additive** (`apply_defaults_v7`): `choices {workers {value, stage, by, via, at, source,
default_requested, stages{}}, research {stages{}}, simplify {value, by, via, at, tree_before, tree_after,
files_changed}}`; `review.unlimited null|{by, via, at, at_pass, budget_name, pick}`; `plan_doc null|{path, sha256,
from}`.

**Journal events** (to `EVENT_TYPES` and `FORGEABLE_EVENTS`): `choice_set {kind, value, stage, scope, source, by,
via}`, `review_budget_lifted {by, via, at_pass, budget_name, rounds}`.

**Setup.** `SETUP_VALUES += {"workers": ("session","workers","ask","keep"), "research": ("ask","on","off","keep"),
"workers_level": ("low","medium","xhigh","max")}` — exactly four options, one decision; the current value
(or the plan's level) is the recommendation, so no `keep` word is needed (D22)`; asked at initialisation and by `--options` (D9, D14); `options
--open` pages at 4. In `workers.json`, `workers: off|on|ask` stores single session / workers / ask.

## Policy conformance

- **C1** — tasks in flight at upgrade resolve to off (R21); old Claude plan names resolve through aliases (R12); an old Codex `pro` keeps today's tables until the human picks (R13).
- **C2** — WP2, WP3, WP7 start with characterization tests of today's detection, tier refusal and budget paths.
- **C3** — WP1 (moving Waves/Fixers to `ai/workers.md`) is a refactoring of its own, never mixed with a feature.
- **C4** — workers inherit the step's files; simplify never amends scope.
- **C5** — the review-limit lift is the human's pick through the dialog or terminal; agents never self-approve.
- **C6** — axes weighed by effect on a user project: WP2 (install/migration) and WP7 (weakens REVIEW_BUDGET,
  changes verdict transitions) are behaviour 2, `start --mode full`, STRONG review; WP3/WP4a/WP6/WP8 behaviour 1;
  WP1/WP4b/WP5 text behaviour 0.
- **CLAUDE.md (skills/)** — every change to `ai/` or a shipped template runs `tools/build-template-history.py`.
- **CLAUDE.md (models are tiers)** — workers resolve through `state.py profile --tier`; no model names hardcoded.
- **routing.md fan-out rule** — three or more parallel agents never above BALANCED (R7).

## Flagged concerns

- **FC1 — RESOLVED (D8).** Q3 vs "the pass past the budget is the human's". `using-riskrails.md:65-66`, `rr-review/SKILL.md:29-36`
  ("Never a third pass"), `rr-build-all/SKILL.md:155-157` conflict with unlimited reviews. Resolution proposed:
  the lift is itself the human's decision; rewrite those lines in WP7.
- **FC2–FC4 — RESOLVED (D9, R23):** both behaviours documented, chosen by setting.
- **FC2 — "the session implements" vs workers.** `instructions/routing.md:28`, `instructions/stub.md:30`,
  `rr-build/SKILL.md:57`, and the global `~/.claude/CLAUDE.md` RiskRails block ("the session implements"),
  which changes only on re-install.
- **FC3 — Codex "Write-heavy work is not fanned out"** (`instructions/routing.md:99`) vs Q2; reword to "only
  file-disjoint steps".
- **FC4 — Codex fan-out "on FAST"** (`routing.md:92`) already disagrees with rr-build-all's BALANCED dispatch and
  `model-routing.md:91`; align.
- **FC5 — ACCEPTED as mitigated (D10).** Light mode promises 0 human stops** (`weight.md:18`); shipped `ask` adds the workers question,
  per-stage research and simplify. Mitigated by batching workers+research into one call; a simplify default is OQ3.
- **FC6 — CLOSED (D7).** Simplify stays before close. Consequence: the simplify edits land after the review, so in
  guarded/full the reviewer does not see them; the rerun `verify` is the only check on them.
- **FC7 — simplify vs C3.** Simplifying pre-existing lines mixes a refactoring into a feature; enforced by the
  brief only (the guard is per file, not per hunk).
- **FC8 — brainstorm in plan mode vs "survives a compaction".** If plan mode blocks `state.py ask` writes, the
  questions are recorded right after leaving plan mode (WP0 decides).
- **FC9 — topic mode never touches `.ai/`** (`cli.py:193`); reading `workers.json` read-only is a deviation.
- **FC10 — RESOLVED (D11).** Caps 6/4/2 fit Codex's 6 threads (`codex-pro.json:9`); the clamp stays as a guard.
  The Claude parallel Task limit is still UNKNOWN.
- **FC11 — this machine's plan.** The installed profile is `max` (`~/.claude/riskrails/profile.json:3`) while
  memory records Max 20x. RESOLVED (D19): `default_claude_max_5x` → Max, cap 4.
- **FC12 — "integrates and decides" vs "never a subagent's diff"** (`rr-build-all/SKILL.md:104-106`): session
  reads `diff --stat` + RESULT; the reviewer reads the diff.
- **FC13 — this repo's `batch.parallel: 5`** (`.ai/policies/weight.project.json:9-13`) keeps capping batch tasks.
- **FC14 — SUITE_BUDGET** still stops each extra review-fix run; Q3 did not ask to lift it.
- **FC15 — CONFIRMED (D12).** Unattended route refused for the lift, unlike `human_route` elsewhere
  (`dialog.py:32-33`).
- **Unknowns (WP0 spike):** EnterPlanMode availability; whether Bash/hooks/subagents/`state.py` writes work in
  Claude plan mode; ExitPlanMode's response; Codex `/plan` entry, sandbox and `request_user_input`; `/simplify`
  availability and model; new plan strings in `~/.claude.json` and Codex `chatgpt_plan_type`; current Codex model
  ids (third-party sources only, Nov 2026).
- **Cost.** Up to 6 BALANCED workers on Ultra plus research and simplify agents; whether worker tokens count
  against the per-task token budget is UNKNOWN.

## Open questions

None open. OQ1 → D16, OQ2 → D17, OQ3 → D18, OQ4 → D13, OQ5 → D14, OQ6 → D15, FC11 → D19.

## Work packages

Each WP is its own `/rr-build` task, ending with `state.py verify --scope all` and the e2e run; any WP touching
`ai/` rebuilds template history.

| WP | Content | Axis |
|---|---|---|
| WP0 | Spike (investigation, `docs/plan-mode-spike.md`): plan-mode, Codex `/plan`, parallel limits, `/simplify` | — |
| WP1 | Move rr-build-all Waves/Fixers into `ai/workers.md` (refactoring) | 0 |
| WP2 | Plan rename, aliases, detection, installer, context-guard names (full, STRONG) | **2** |
| WP7 | `review --unlimited` + D_b decision (full, STRONG) | **2** |
| WP3 | Cap: profile key, `workers_level`, `steps --json`, Codex clamp | 1 |
| WP4a | `choice` command, keyed questions, `start --from-topic/--choice`, setup keys | 1 |
| WP4b | Skill text for workers/research, `ai/workers.md` Research; routing/stub/CLAUDE.md text with both behaviours (R23) | 0 |
| WP5 | Native plan mode as base; `start --plan-doc` | 0 + 1 |
| WP6 | Simplify question before close, `ai/agents/simplifier.md`, rr-ship text | 1 |
| WP8 | Codex model ids after G1 | 1 |

Order: WP0, WP1, WP2 in parallel worktrees under `/Store/claude-agentic-wt`; then WP7 → WP3 → WP4a → WP4b →
WP5 → WP6 → WP8 (shared files).
