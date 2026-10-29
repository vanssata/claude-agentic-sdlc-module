# Spec: Direct-mode diet — faster tasks, fewer gates, one review

Intent: none on file. This document carries its own intent (below); it was
written from the 2026-10-22 assessment of the plugin as a project, at the
developer's request, for points 1–5 of that assessment. Point 6 (a skills-first
restructuring of `/ai-task`) is out of scope here.

Status (2026-10-29): tasks 1–4 of §Order of work are shipped — task 1
`4b3b9e1` (2026-10-22), task 2 `ef6e9a1` (its commit names it part A), task 3
`ada69e3` (T-2026-10-22-002) with its M2/L4 follow-up `ee838dc`
(T-2026-10-25-001), task 4 `e2841c4` (T-2026-10-25-002). Q1 is closed. The
same week the redesign (`docs/sdlc/specs/claude-agentic-redesign.md`) replaced
the tiers T0–T6 with weight and three modes, so G1, G2 and G5 name a surface
that no longer exists. What the tasks since then cost, and a verdict per goal,
are in §Measured after. §1–§5 and every D-, R- and G- identifier stay as
written below; new requirements go to a spec of their own.

Status (2026-10-22): approved in substance by the developer on 2026-10-22 (decisions D2a,
D3b-shipped, D4b, D4c below), after one builder check. One question is open
(§Open questions). Nothing in it is implemented. Line numbers cite HEAD
`3d923d5` unless marked "working tree"; the working tree carries the
uncommitted edits of T-2026-10-21-001 and drifts.

## Intent and why

The plugin is slow on its own repository, manages risk more strictly than the
risk warrants, and loses focus. Measured on the task in flight when this was
written (T-2026-10-21-001, a bugfix to `hooks/ai-path-guard.sh`):

| | |
|---|---|
| net change | 51 lines in 4 files (working tree) |
| calendar time | ~20 h, ~18 h of it waiting on gate G1 |
| agent time | ~2 h; task still open after step R4, a review owed |
| full-suite runs | 3 × ~375 s |
| STRONG reviews | 3 (one review, two re-reviews), a fourth decided |
| tokens | 25.4M, 127 % of the task's own T4 budget; 25.0M of them cache reads |
| guard denies against the agent itself | 2 in the journal (`events.jsonl:44,54`); 3 in the assessment session (a read-only one-liner, this spec's rewrite in the repository and in the scratchpad while step R4 was open); 1 `cat` of a policy file in the builder check |

Since 2026-10-01, 10 of 24 commits are the path guard tending itself. In
`.ai/project/known-risks.md` the entry for T-2026-10-21-001 alone is a
1,100-word paragraph; four path-guard entries are still open, each found by a
review of a fix to an earlier one. In this repository the sensors have never
replaced a review: every `review-gate` call recorded `lint: unavailable` and
`bite: unavailable` (`events.jsonl:16,31,62`).

Three causes, each with its own section below:

1. The tier table, written for a production e-commerce codebase, is applied to
   a developer tool where almost everything is "a process other code runs
   through", so almost everything is T4 (§1).
2. The sensors cannot be green here, so the review skip the policy promises at
   T2/T3 never happens (§2).
3. A review that found no BLOCKER still leaves `review_status = blockers_open`,
   which only another review can clear, and nothing caps reviews per task; the
   reviewer is told to invent inputs without bound (§3).

Two more cost attention rather than tokens: the path guard denies the agent's
own read-only commands and treats the plugin's own templates and fixtures as
control files (§4), and direct mode takes seven to nine `state.py` calls for a
change that needs three, while any open step blocks every unrelated write,
scratchpad included (§5).

## Measured after (2026-10-29)

The numbers above came from one task. These come from every task since,
against every task before. The developer chose the scope on 2026-10-29:
measurement and status only, with cohorts by date.

**Method.** Two cohorts by task id, both measured by the same script:

- *Before*: T-2026-10-13-001 … T-2026-10-22-002, 17 tasks, all on the tier
  surface (T0–T6).
- *After*: T-2026-10-25-003 … T-2026-10-28-012, 32 tasks. Six of them
  (T-2026-10-25-003 … -008) are still on the tier surface. The other 26 are
  on the weight surface (light, guarded, full; `state.py` schema 7).

The diet's own tasks, T-2026-10-25-001 and -002, are in neither cohort. The
script is `python3 -I diet-measure.py <repo>`. Per the plan it lives in the
session scratchpad, not in the repository. It reads only these sources:

- `.ai/reports/<id>/events.jsonl` gives:
  - the time from `task_started` to `task_closed`;
  - the human wait, as the union of `gate_requested→gate_approved` and
    `question_asked→question_answered`;
  - suite, step and e2e runs (`verify_run`; on the tier surface,
    `field_set test_status` with `scope: suite`). A run is red when its exit is
    non-zero and it was not an `expected_fail`;
  - review passes, from `review_verdict`. The tier surface has no such event,
    so a pass there is the larger of two counts: the `## Pass N` and
    `## Re-review` headings in `review-report.md`, and the `review_status`
    transitions (a `passed` right after `passed_with_findings` closes findings
    and does not count as a pass);
  - `scope_change` events;
  - journaled `state.py` calls, counted as distinct timestamps other than
    `handoff_written`.
- Tokens: `usage-report.py --task <id>` over the local Claude Code transcripts.
- Lines changed: the `+N −M lines` line of a weight-surface `task.md`.
- Guard denies: every `PreToolUse:<tool> hook error:` tool result in the
  local transcripts (subagents included, one per `tool_use_id`) inside the
  task's window. The journal does not record a deny against the agent.

Token and deny windows are by time, so they count any other session inside
them. Of the closed tasks, only T-2026-10-28-011 overlaps another (-012).

Medians are over the tasks that closed and were not abandoned: 16 of 17
before, 27 of 32 after. In the after cohort 3 tasks were abandoned, and
T-2026-10-28-010 and -012 have no `task_closed` event.

| per task, median (max) | before, 16 | after, 27 | T-2026-10-21-001 (§Intent) |
|---|---|---|---|
| calendar time, h | 1.1 (116.2) | 1.0 (8.9) | 21.3 |
| human wait (gates, questions), h | 0.1 (18.0); 35.5 in all | 0.0 (6.5); 9.2 in all | 18.0 |
| agent time, upper bound, h | 0.7 (116.0) | 0.7 (8.9) | 3.3 |
| full-suite runs | 2.5 (5); 6 of 40 red | 2 (5); 12 of 65 red | 5 |
| step runs | not journaled | 4 (16); 0 in the six tier-surface tasks | not journaled |
| review passes | 2 (5); 32 in all | 1 (2); 29 in all | 5, all STRONG |
| journaled `state.py` calls | 17.5 (83) | 19 (61) | 47 |
| scope amendments (`scope_change`) | 1 in all | 38 in all; 0 in the six tier-surface tasks | 0 |
| tokens, M | UNKNOWN | 24.3 (131.9) | 25.4 (§Intent) |
| guard denies against the agent | UNKNOWN | 3 (14); 112 in all | see §Intent |

The after cohort by mode. Both tier-surface rows are tier labels, not modes:

| after | n | calendar h | agent ≤ h | review passes | lines changed | tokens M | denies |
|---|---|---|---|---|---|---|---|
| light | 1 | 0.7 | 0.5 | 0 | 716 | 8.9 | 2 |
| guarded | 11 | 0.4 (8.9) | 0.4 (8.9) | 1 each, BALANCED | 1653 (8487) | 7.9 (53.4) | 2 (8) |
| full | 9 | 1.8 (7.0) | 1.1 (2.5) | 1 (2), STRONG | 1627 (10526) | 55.9 (131.9) | 4 (14) |
| T4, tier surface | 5 | 0.4 (8.4) | 0.4 (8.4) | 1 (2), STRONG | UNKNOWN | 4.5 (76.9) | 4 (8) |
| T3, tier surface | 1 | 0.5 | 0.5 | 1, BALANCED | UNKNOWN | 10.9 | 7 |

**Where the time goes now.**

- KNOWN FACT: full is 9 of 27 tasks and 480.3M of 840.7M tokens (57 %).
  Without T-2026-10-28-011, whose window also covers -012, it is 49 %.
  Guarded is 11 tasks and 188.2M (22 %).
- KNOWN FACT: the median guarded and full task change about the same number
  of lines, 1653 against 1627. The full one costs about seven times the
  tokens: 55.9M against 7.9M, or 43.2M against 7.9M without -011.
- INFERENCE: tokens follow the mode more than the size. These are medians
  of 11 and 9 tasks, and no correlation was computed. `+N −M lines` is a
  weak proxy for size, since it counts fixtures and generated files. Full
  adds a STRONG review and more steps.
- KNOWN FACT: human wait is 9.2 h over 27 tasks. One task,
  T-2026-10-26-003, holds 6.5 h of it: a 2.4 h question and a 4.0 h gate.
  Before, T-2026-10-21-001 waited 17.7 h on one gate.
- INFERENCE: the agent-time column is an upper bound. Two windows hold
  17.3 h of its 40.0 h: T-2026-10-26-007 (8.9 h) and T-2026-10-25-008
  (8.4 h). Both run overnight, 22:16–07:07 and 22:43–07:09 UTC. Before,
  T-2026-10-15-004 shows 116 h (2026-10-15 to 2026-10-20) and
  T-2026-10-22-002 66 h. The journal cannot tell idle time from work.
- KNOWN FACT, the 112 denies after, by kind:

  | kind | denies |
  |---|---|
  | scope | 30 |
  | write to a control file | 27 |
  | interpreter one-liner | 17 |
  | read of a control file | 11 |
  | `state.py approve` from an agent | 9 |
  | over-long command | 8 |
  | a human-only or destructive verb | 5 |
  | a sensitive path | 5 |

  This task added one of each of the first and third kinds on 2026-10-29.
  The first was a `Write` to the session scratchpad. That is the scope
  guard's reach, which §Goals keeps out of this spec. The second is under G4
  below.

**Goals.** Each verdict carries an evidence label:

- **G1: met in substance on the weight surface (INFERENCE); not met by
  label.**
  - KNOWN FACT: 24 after tasks touch `hooks/`, `skills/`, `agents/`,
    `scripts/` or `ai/`, abandoned ones excluded. Six are tier surface: one
    T3, five T4. The other 18 are on the weight surface: none light, seven
    guarded, eleven full. Six of the full ones came from the weight table.
    Five were raised from guarded, by the developer or by the
    `hooks/CLAUDE.md` and `skills/CLAUDE.md` behaviour-2 rule.
  - KNOWN FACT, from `weight_set`: 12 of the 18 score behaviour 2 or
    reversibility 2. Eleven of those 12 ran full and one guarded
    (T-2026-10-28-003). The other six score behaviour 1 and reversibility 0
    (T-2026-10-26-004 … -007, T-2026-10-28-002, -007), and all six ran
    guarded.
  - INFERENCE: those 12 are G1's own exemption, read through C6 (allowing a
    deny, changing approval or install scores behaviour 2). Guarded's
    ceremony, one BALANCED review and no human gate, is what G1 wanted from
    T3. By that reading, every non-exempt change ran at what G1 asked for.
  - KNOWN FACT: by the compat label (`MODE_TIER`,
    `skills/ai-task/state.py:2956`) guarded is T4. By that label, 1 of 24 is
    T2/T3 (the tier-surface T3).
  - UNKNOWN: whether the exemption covers the six tier-surface tasks, which
    record no axes. Before, 5 of 15 such tasks were T2/T3; their exemption
    is not classified.
- **G2: not met; superseded.**
  - KNOWN FACT: none of the 49 journals holds `skipped_green`. They hold 30
    `sensors: required` events, all on the tier surface.
  - KNOWN FACT: schema 7 has no `review-gate`; `skipped_green` is in no Python
    file under `skills/ai-task/`. Its place is taken by light mode, where `close`
    decides from the two facts whether a review is owed (`ai/using-riskrails.md:30`,
    `skills/rr-build/SKILL.md:170`). One task took that path,
    T-2026-10-28-001, and it closed with no review.
- **G3: met.**
  - KNOWN FACT: no after task ran more than 2 review passes. Three ran
    exactly 2: T-2026-10-25-008, T-2026-10-27-007 and T-2026-10-28-011.
    Before, the most were 5 (T-2026-10-21-001) and 4 (T-2026-10-20-003).
  - KNOWN FACT: the cap is `review_rounds_max: 2` (`.ai/policies/weight.json:184`;
    3 for a batch task, `:214`). It is enforced by `state.py review`
    (`skills/ai-task/state.py:3802`).
- **G4: partly met.** The pinned spellings hold, but a command
  line that held a read-only one-liner beside a shell `$(…)` was refused in
  this task.
  - KNOWN FACT: `tests/test_ai_path_guard.py:704-722` allows seven read-only
    one-liners (python, perl, node, ruby) and denies the writing ones. `:799`
    allows a write under the ai-init templates during a task.
  - KNOWN FACT: on 2026-10-29, in this task, a command line with a
    read-only `python3 -I -c` that read `events.jsonl` was refused as "an
    interpreter one-liner that writes the task's own control files". It was not
    reworded; the check moved into the measurement script.
  - INFERENCE: from the regexes, not run: `WRITE_WORD_RE` counts `$(` as a
    write indicator (`hooks/guard/paths.py:160-161`) and `interpreter_text`
    scans the whole line (`:1229-1235`), so the unrelated shell part
    triggered the deny; `->` matches `WRITE_REDIR_RE` (`:168`) only when a
    `.ai/state/` or `.ai/reports/` path follows the `>` (spaces after it
    allowed) with no quote, space, `|`, `;`, `&`, `<` or `>` before the path;
    the command was not kept, so whether it did is UNKNOWN.
    Recorded in `.ai/project/known-risks.md` ("Guard
    denies a compound line …").
  - UNKNOWN: whether the 17 one-liner denies and 11 read denies after were
    reads.
- **G5: the shape is met; the minimum is not measured.**
  - KNOWN FACT: light is "plan inline, edit, `verify --scope all`, `close`"
    (`ai/using-riskrails.md:30`), so the minimum is three calls with `start`.
  - KNOWN FACT: the weight table put 1 of 21 closed weight-surface tasks in
    light (1 of 26 with the abandoned and unclosed ones).
  - KNOWN FACT: that task, T-2026-10-28-001 (W1), has 19 journaled
    timestamps: `start`, three questions with their answers, two scope
    amendments, seven notes, two runs and `close`. That is an upper bound on
    its calls, because the seven notes fall in two same-second bursts.
  - UNKNOWN: whether a light task with no questions makes three.
- **G6: met.**
  - KNOWN FACT: `.ai/policies/safety.md:53-57` states the threat model.
  - KNOWN FACT: `.ai/project/known-risks.md` names the acceptance
    `accepted (2026-10-22, docs/sdlc/specs/direct-mode-diet.md)` on seven
    lines: `:63` (a heading), `:90` and `:165` (the accepted residual of an
    entry that is otherwise fixed), and `:179`, `:186`, `:193`, `:207`.
  - KNOWN FACT: `:210`, "Interpreter tripwire residuals after M2/L4", still
    reads `Status: open`. `:581` (accepted 2026-10-27, T-2026-10-27-005)
    supersedes it, together with the older path-guard entries, after R22
    (`:589`).
  - INFERENCE from the 32 after goals (`task.md:1`): none is a
    pathological-input fix. The guard work after was the port
    (T-2026-10-26-006), its suites (T-2026-10-27-001), the R22 rules
    (T-2026-10-27-005) and the dialog gate (T-2026-10-28-010).

**What the numbers do not show.**

- UNKNOWN: tokens and denies before. No main transcript on this machine is
  dated 2026-10-04 … 2026-10-23 (file modification time). The one before
  window with tokens is T-2026-10-22-002, 40.5M. That window runs from
  2026-10-22 11:49 to 2026-10-25 06:05 UTC, but only its last day has
  transcripts. That day also holds other sessions, among them the redesign
  analysis of 2026-10-24. The number is neither the task's whole cost nor
  its own alone, so it is left out.
- RISK: `usage-report.py --task` ends an unclosed task's window at "now"
  (`skills/usage-report/usage-report.py:693`). That makes T-2026-10-28-010 and -012 UNKNOWN.
  T-2026-10-28-011's window (20:07–21:58) also covers the start of -012
  (20:38), so its 131.9M include some of -012.
- RISK: T-2026-10-28-010 and -012 have no `task_closed` event (010 ends at
  `gate_approved`, 012 at a `close` handoff). Yet no task was in flight on
  2026-10-29. This was found here and is outside this task.
- INFERENCE: the review count on the tier surface is reconstructed by the
  rule above. Twenty passes there have no recorded tier.
- KNOWN FACT: the cohorts did different work. Before was mostly path-guard
  hardening; after was the redesign programme. The table compares tasks,
  not changes of equal size: no before task records its lines changed. The
  tier surface journaled neither step runs nor scope amendments the way
  schema 7 does, so those two rows do not compare.

## Goals, non-goals, anti-goals

Goals (each testable; the test is named in §Design):

- G1. A change to `hooks/`, `skills/`, `agents/`, `scripts/`, `ai/` in this
  repository classifies T2 or T3 unless it allows what was denied, changes the
  approval path, or changes how user projects are installed or migrated.
- G2. In this repository `state.py review-gate` can answer `skipped_green`: lint
  is measured, the step names its tests, traceability and bite can measure.
- G3. At most one full model review and one scoped re-review per task, enforced
  by `state.py`, in both runtimes.
- G4. An interpreter one-liner that only reads `.ai/state/` or `.ai/reports/`
  is allowed; one that writes there stays denied. A path outside the resolved
  `.ai/` root and the installed home trees — a scratchpad fixture, the plugin's
  `skills/ai-init/templates/.ai/`, `tests/fixtures/**/.ai/` — is not a control
  file.
- G5. Direct mode at T2/T3 with a green run is three `state.py` calls: `quick`,
  `test-run --scope all`, `close`.
- G6. The open pathological-input findings against the path guard are accepted
  in writing, under a stated threat model, and open no further task.

Non-goals:

- Point 6 of the assessment: splitting `/ai-task` into small skills.
- T5 and T6 keep every stage, gate and the unbounded reviewer brief.
- The shipped `path_scopes` floors for user projects do not change; §1 is
  project-local.
- Guard performance work; the hook-performance budget is untouched.
- Removing any guard or the human approval at T4+.
- Review provenance. Today any session can `set review_status passed`
  (`state.py:1386-1415`); making `state.py` know that a review actually ran is
  a separate design. This spec does not widen that gap (§3a) and records it in
  `known-risks.md`.
- The scope guard's reach. While a step is current, `ai-scope-guard.sh` refuses
  every `Edit`/`Write` outside the step's files whatever the path
  (`hooks/ai-scope-guard.sh:71`), so one open step blocks a spec, a memory note
  or a scratchpad file. Observed twice while writing this; recorded in
  `known-risks.md` and left to a later design, because the fix touches the
  invariant the guard exists for (C4).

Anti-goals (the design has failed if any of these holds, even with green tests):

- A refusal that can be satisfied by rewording the refused command.
- A sensor that reports green without having measured.
- A new way for an agent to reach `review_status = passed` that today does not
  exist.
- More `state.py` subcommands than today (29). Calls per task go down; the
  surface does not go up.

## Constraints

- Constitution C1–C5 (`docs/sdlc/constitution.md`). C2 and C4 are load-bearing
  here: every change below ships with its failing test first, and every step
  names its files.
- `.ai/AGENTS.md` non-negotiables 1–7, in particular 4 (verify through
  `state.py test-run`) and 6 (evidence labels in `project/`).
- **Protected and frozen files.** `hooks/ai-path-guard-defaults.json:26-38`:
  any path matching `.ai/policies/*.json`, `.ai/state/*.json`,
  `.ai/reports/<id>/{questions.md,events.jsonl}` is write-denied to an agent
  always, task or no task. `:39-56`: `.ai/{AGENTS.md,CLAUDE.md}`,
  `.ai/{agents,policies,workflows,templates,rules}/`,
  `docs/sdlc/constitution.md` and the runtime's own configuration are frozen
  while a task is in flight. Policy "is edited by a human, outside an agent
  run, where the change is reviewable" (`docs/hooks.md:144-146`). The patterns
  match anywhere in a path, so until §4b lands the same holds for
  `skills/ai-init/templates/.ai/**`. Consequence: every edit to those files in
  this spec is **staged by the agent and applied by the human**, with no task
  open, in one commit (§Order of work, task 2).
- `docs/hook-performance.md:12-32`: a change that moves a guard decision is a
  rule change — the characterization golden is re-recorded with `--record` and
  the change is reviewed as a rule change. §4 is one.
- Shared-tree model: a project's `.ai/<path>` overrides the plugin's
  `ai/<path>`; this repository's `.ai/policies/*` are project files; the
  shipped defaults of `risk-tiers.{json,md}`, `safety.md`, `testing.md` and
  `AGENTS.md` are under `skills/ai-init/templates/.ai/`, and a change there
  goes through the template-history mechanism
  (`tools/build-template-history.py`, `tests/test-merge-migration.sh`) so
  `/project-update` can three-way merge it into user projects.
- Two runtimes read one `state.py`; §3 and §5 must behave the same under Codex.
- No agent commits; the approvals in §Order of work are given outside the
  agent.

## Requirements

- R1. (§1) The project's `risk-tiers.json` carries project-specific `examples`
  for T2, T3 and T4 that classify plugin changes by their effect on a user
  project's decisions; `risk-tiers.md` mirrors it; `.ai/rules/hooks.md` and
  `.ai/rules/skills.md` carry the rule for those directories; constitution C6
  states the principle; the project `CLAUDE.md` names the mistake once;
  `skills/ai-task/SKILL.md` says that a project's examples win over the generic
  row where they speak.
- R2. (§2a) `lint_command` in `.ai/policies/testing.md` runs and ends
  "rated at 10.00/10" on a clean tree; `sensors.py check` reports `lint: green`;
  a missing module is reported `unavailable`, not red.
- R3. (§2b) `state.py quick --tests "<a>,<b>"` writes `required_tests` on the
  one step; `traceability` and `bite` measure when it is given; nothing changes
  when it is absent.
- R4. (§3a) `review_status` gains `passed_with_findings`; a remediation that
  names the findings it closes, followed by a green suite run, moves it to
  `passed` without a re-review; `blockers_open` still needs one scoped
  re-review.
- R5. (§3b) `review_rounds_max` (default 2) in `risk-tiers.json`, shipped; the
  third review verdict written to a task exits 6 `REVIEW_BUDGET` and names the
  human way out.
- R6. (§3c) In direct mode (T0–T4) the reviewer's inputs are bounded to the
  task goal, the diff, its named tests and the project's fixture corpus and
  threat model; a finding needing an input outside them is `INFO` with
  `in_scope: no` and goes to `known-risks.md`, never to remediation.
- R7. (§4a) The control-files tripwire in `hooks/ai-path-guard.sh` ("Obfuscated
  access", HEAD `:1080-1093`) denies only when the one-liner also shows a
  write indicator; a read-only one-liner is allowed. Golden re-recorded; both
  cases pinned.
- R8. (§4b) A path outside the resolved `.ai/` root, that root's `.claude/` and
  `.codex/`, and the installed home trees is not classified `protected` or
  `task`; pinned by fixture for a scratchpad tree and for
  `skills/ai-init/templates/.ai/`.
- R9. (§4c) The open path-guard entries in `known-risks.md` listed in §4c are
  `Status: accepted` under one rationale, and `.ai/policies/safety.md` states
  the threat model the acceptance rests on.
- R10. (§5) `state.py test-run --scope all` runs the suite and, if green, the
  e2e command, recording both; `state.py remediate` finishes open steps
  itself; `state.py close` finishes every open step, runs the review gate,
  refuses when a review or a human gate is still owed, keeps its existing
  refusals (pending questions, rejection) and its escalation use, and
  otherwise archives. `step-done`, `set e2e_status` and `stage
  human_approval` leave the direct-mode text of `skills/ai-task/SKILL.md`.
- R11. Every requirement above ships with the test that pins it, in the suite
  file named in §Design; `tests/test-end-to-end.sh` walks the three-call path.

## Design

### §1 This repository is a developer tool, not a production process (project-local)

Where T4 comes from today. `path_scopes` (`risk-tiers.json:484-578`) gives
`hooks/`, `skills/`, `agents/`, `scripts/`, `ai/` no floor — they are scope
`source`. The T4 on T-2026-10-21-001 came from the trigger reading "a process
every Bash call runs through" (`events.jsonl:7`), which is the T4 row of the
table read literally (`risk-tiers.md:23`) and the sentence "a change to a
process is T4 … take the higher" (`skills/ai-task/SKILL.md:118-124`). Only
`.ai/policies/**`, `.ai/workflows/**`, `.claude/**`, `.codex/**`, `CLAUDE.md`,
`AGENTS.md` have a T4 floor (`pipeline`, `risk-tiers.json:486-496`). No code
reads `tiers.*.examples`; the tier is the session's reading of the table.

Decision D1 — classification rule for this repository. The tier of a plugin
change is what it does to a **user project's** decisions, never the fact that
plugin code is a process:

| Tier | In this repository |
|---|---|
| T0 | documentation, comments, `docs/**`, report files, `.ai/project/**` |
| T1 | tests only; a message's wording when no golden entry moves |
| T2 | a change that moves no guard decision and no `state.py` refusal: skill or agent text, `usage-report`, installer paths, performance work that keeps the golden byte-identical |
| T3 | a change that **adds** a decision or a refusal (a new deny, a new sensor, a new `state.py` check) or changes a deny's reason text, golden re-recorded |
| T4 | a change that **allows what was denied** or weakens a refusal, changes the approval path (`approve`, `questions --sync`, `AI_UNATTENDED`, `review_status` transitions), or changes how user projects are installed or migrated (`install.sh`, `project-update` merge, `tools/`) |
| T5, T6 | as shipped; none expected here |

Where it lives, in this order of authority. Items 1–5 are human-applied
(frozen files, §Constraints); item 6 is the one plugin-side sentence that makes
them binding:

1. `.ai/policies/risk-tiers.json` (project copy): the `examples` arrays of
   `tiers.T2`, `tiers.T3`, `tiers.T4` get the rows above as text. The file
   invites this: "Adjust the triggers to the project after /ai-init — the
   defaults are generic" (`risk-tiers.json:2`).
2. `.ai/policies/risk-tiers.md`: regenerated mirror, new hash in its header.
3. `.ai/rules/hooks.md`, `.ai/rules/skills.md`: the per-directory rule
   `.ai/AGENTS.md:49` already routes to ("writing code under `<dir>/` →
   `rules/<slug>.md`"): the table row for that directory, three lines each.
4. `docs/sdlc/constitution.md` C6: "This plugin is a developer tool. A change
   to its hooks, skills or state machine is classified by what it does to a
   user project's decisions — allow where it denied, change approval, change
   install — never by its being a process."
5. Project `CLAUDE.md`, "Things Claude Code gets wrong": one line naming
   T-2026-10-21-001 as the 51-line T4 that cost 25.4M tokens, with the rule.
6. `skills/ai-task/SKILL.md:118-124` (plugin, task 1): one added sentence —
   "A project's `examples` in `risk-tiers.json` refine the generic rows and win
   where they speak; 'take the higher' decides between two generic rows, never
   over a project example."

What does not change: the `pipeline` floor. `.ai/policies/**` and `CLAUDE.md`
stay T4 by scope, because an edit there changes what the agent itself does —
and the guard already reserves them for the human.

Rescore is safe: `step-done` only ever raises a tier from `path_scopes`
(`risk-tiers.md:138-140`); with `hooks/**` as `source` a T2 or T3 quick task
stays T2 or T3.

Test: none new — this section is policy text. After the human applies it,
`/ai-status` must report the mirror hash current; the builder names the suite
that asserts it, if one does.

Rejected: a `max_tier` ceiling per `path_scope`. The schema has floors only,
on purpose (`_path_scopes_comment`): a ceiling that a glob applies is how a
payment file in an odd directory gets T2.

### §2 Sensors that can be green

Facts. `required_for_skip` is tests, lint, typecheck, diff, rescore,
traceability, duplicates, bite (`sensors.py:119-120`); `bite` is required from
T2 (`sensors.py:125`). Here: `typecheck_command: none` (green as
not-applicable); `lint_command: pylint $(git ls-files '*.py')`
(`testing.md:90`). Until 2026-10-22 `pylint` was not installed in any form on
the development machine, so the sensor answered `unavailable` on every task
(exit 127, `sensors.py:908`); the same mapping reads `python3 -m pylint`
without the module (exit 1) as **red**, not `unavailable`. `quick` writes
`required_tests: []` on its one step (`state.py:1194`) and has no flag to fill
it (`state.py:2692-2696`), so `traceability` is red ("steps with no test named:
1") and `bite` is `unavailable` on every quick task.

D2a (environment, done) — lint that runs. The developer installed the system
package on 2026-10-22: `/usr/bin/pylint` 4.0.5, and `python3 -m pylint` finds
it too. `testing.md:90` stays as it is: `pylint` on `PATH` is exactly what
the line calls, and a missing binary is already `unavailable` by the exit-127
mapping. `CONTRIBUTING.md` gets one line: pylint comes from the distribution
package (`python3-pylint`), no `pip` needed. Rejected: `lint_command: none` —
the repository configured pylint (`.pylintrc`), so `none` would be the human
writing down something false.

D2a′ (plugin, task 4) — the lint sensor maps a missing module to
`unavailable`: exit 1 with "No module named" on the log's last lines, and the
equivalents for `npx`/`vendor/bin` runners, report `unavailable` with the
detail, never red. A red lint stays a lint failure. This is for user projects
whose line is the `python3 -m` form `detect` proposes (`sensors.py:143`).

D2b (plugin-wide) — `quick --tests`. New optional argument
`--tests "<path>[,<path>…]"` on `quick`; its value becomes the step's
`required_tests`. `remediate` already takes `--files` for the failing tests;
the builder confirms its step carries them as `required_tests` too, or adds
the same flag. `skills/ai-task/SKILL.md` §1a step 2 shows `--tests` in both
example lines and says: a bugfix always names its failing test (C2); a change
without a test leaves `--tests` out and keeps the review, which is the policy
working, not failing. When `--tests` is absent nothing changes against today.

Bite mechanics are not touched. The builder verifies on this repository's own
suite shape (`step_test_command` with `{files}`, `testing.md:88`) that a named
`tests/test-*.sh` is run at the base tree and reports red-without-change for a
real bugfix; the first candidate is the test added by T-2026-10-21-001.

Stale tests. `snapshot_tree` covers every path except `.ai/state` and
`.ai/reports` (`sensors.py:221-248`), so any edit after the recorded run makes
`tests: stale` (`events.jsonl:16,31`). Decision: nothing is exempted — an
exemption is a sensor that is green without measuring (anti-goal), and in this
repository a `.md` can fail a test (`tests/test-instruction-budget.sh` reads
`CLAUDE.md`). The recorded `test-run --scope all` is the last step that
changes the tree before `close`; anything derived from a run (the assertion
count `testing.md` says `README.md` carries) is written before the recorded
run, from the previous run's output or from the test files, and a wrong value
is a red run that says so. A slip costs one re-run and is visible.

Expected outcome, the whole point of this spec: at T2/T3 with the suite green on
the current tree, lint green, typecheck `none`, diff inside budget, rescore
≤ T3, traceability green, duplicates green and bite red-at-base,
`review-gate` writes `skipped_green` and no model reads the diff.

Tests: `tests/test-ai-task-state.sh` — `quick --tests a,b` writes
`required_tests`; `tests/test-ai-task-sensors.sh` — traceability green with
named tests, lint green with a stub `pylint` on the path, `unavailable` with
"No module named" at exit 1, `unavailable` at exit 127, red at exit 1 with a
lint message.

### §3 One review per task

Facts. The rule exists in prose three times: "ask for one scoped re-review only
when a BLOCKER was fixed" (`SKILL.md:193-194`), "one scoped re-review closes the
named findings — never one finding, one fix, one re-review at a time"
(`SKILL.md:468-470`), `review-economy.md` §3. Structurally it cannot hold:
`REVIEW_STATUS` is `not_started, in_progress, blockers_open, passed,
skipped_green` (`state.py:89`); a review that found HIGH but no BLOCKER has
only `blockers_open` to say so; `passed` is a review's verdict, so clearing
`blockers_open` needs another review (the journal's own words, `handoff.md`,
decision of 2026-10-22 09:13Z). Nothing counts reviews. Direct mode never
writes `review-report.md` (`SKILL.md:452` is the sdlc section), so a finding
has no durable id. The reviewer is briefed to assume the code is wrong and try
"very large, concurrent, repeated" inputs
(`agents/ai-reviewer.md.tmpl:10-12,53-64`); on a guard whose input is any
shell line that is a bottomless well — every pass on T-2026-10-20-003 and
T-2026-10-21-001 found a new HIGH built from an input no session produces (a
1524-character cwd, 150 000 `rm -f;` segments, a symlink that amplifies
`realpath`, a 123 KB operand of empty quotes).

D3a (plugin-wide) — a verdict for "findings, no blocker". `REVIEW_STATUS`
gains `passed_with_findings`. The reviewer's VERDICT line becomes
`verdict: pass | pass_with_findings | blockers_open`, mapped by the session.
In direct mode the session saves the reviewer's FINDINGS and VERDICT blocks to
`.ai/reports/<task-id>/review-report.md` (one file, appended per pass), which
gives every finding a label (`B1`, `H1`, `M2`…). Closing rules:

- `blockers_open`: unchanged — one remediation batch, verify once, one scoped
  re-review whose verdict closes.
- `passed_with_findings`: one remediation batch opened with
  `state.py remediate --files … --closes "<labels>"`; `remediate` refuses a
  label that is not in `review-report.md`. When the next `test-run --scope
  suite` (or `all`) is green on a tree after that remediation, `state.py` sets
  `review_status = passed` itself and journals `findings_closed` with the
  labels, the run and the tree. No re-review.
- `passed`: unchanged.

What this does not do: `set review_status passed` without a review is possible
today (`state.py:1386-1415`) and stays possible; the spec adds no second route
to `passed` that bypasses a review — `--closes` needs a report a review wrote.
Provenance is a non-goal and gets a `known-risks.md` entry.

D3b (plugin-wide, shipped default — developer's decision 2026-10-22) — the
budget. `review_rounds_max: 2` beside `remediation_rounds: 2`
(`risk-tiers.json:617`), in the shipped default
`skills/ai-init/templates/.ai/policies/risk-tiers.json` and in this
repository's copy: one full review plus one scoped re-review per task. Every
verdict written through `set review_status` by a review (and a cross-vendor
verdict, `state.py:1398-1410`) increments `state.reviews`; the write that would
exceed the budget exits 6 `REVIEW_BUDGET` with the way out: the human decides,
by `state.py approve --by <name>` at a gate or by `state.py set review_status
<value> --by <name>` — a new `--by` on `set`, journaled as a human decision like
`approve` is. An agent cannot pass `--by`; the path guard's existing approve
rule (`docs/hook-performance.md:107-116`) is extended to it by the same
pattern. The budget applies at every tier (my call, not the developer's):
after two rounds the way out is the human, exactly as `remediation_rounds`
already works; what T5/T6 keep unbounded is the reviewer's **input** (D3c),
not the number of passes. `/ai-status` prints `reviews: N of
review_rounds_max`.

D3c (plugin-wide, tier-aware) — the boundary. `agents/ai-reviewer.md.tmpl` and
the shared contract `ai/agents/reviewer.md` get a "Boundary" paragraph, and
`SKILL.md` ADVERSARIAL REVIEW a matching sentence: in direct mode (T0–T4) the
review's inputs are the task goal, the diff, the tests the step names, and the
project's own fixture corpus and threat model (`.ai/policies/safety.md`, the
`*-defaults.json` of the guards, `tests/fixtures/**` here). A finding that
needs an input outside them is reported as `INFO` with `in_scope: no`, the
session writes it to `known-risks.md` in one entry, and it never opens a
remediation. At T5/T6 the "Look for" list applies unbounded, as today. Every
finding carries `in_scope: yes|no`, the reviewer's own assessment, which the
session may override only towards `yes`.

D3d — re-review by request. A human may ask for a re-review at any time; it
counts against the budget, and when the budget is spent the answer is the
`REVIEW_BUDGET` text, not a review. This is the one behaviour the design takes
away from the human: unbounded re-reviews. It is deliberate and is the single
largest token line in the evidence.

Tests: `tests/test-ai-task-state.sh` — `set review_status passed_with_findings`
accepted; `remediate --closes H1` refused without a report, accepted with one,
then a green `test-run` moves to `passed` with the journal line; `set
review_status` a third time exits 6; `set … --by human` on the third passes
and journals `actor: human`; Codex payload path identical.
`tests/test-ai-path-guard.sh` — `set review_status … --by` from an agent is
denied like `approve`.

### §4 The guard denies mistakes, not reads; the hardening programme closes

Facts. `hooks/ai-path-guard.sh` "Obfuscated access" block (HEAD
`:1080-1093`, working tree `:1097-1110`): a one-liner (`python3 -c`,
`perl -e`, `ruby -e`, `node -e`, `php -r`… or `eval`) that **mentions**
`.ai/state/` or `.ai/reports/` is denied as "writes the task's own control
files"; the comment calls it "a tripwire, not a boundary". The assessment's
one-liner opened `events.jsonl` for reading and was denied; the journal shows
a probe denied for naming `current.json` (`events.jsonl:44`). One golden entry
pins this tripwire (`tests/fixtures/guard-characterization/golden.txt:405`)
and its fixture is a write, so it stays a deny under D4a; the other three
"interpreter one-liner" entries are the `.env` tripwire and are untouched.
Separately, a fixture `.ai/policies/path-guard.json` written **under the
scratchpad** was denied as a protected file (`events.jsonl:54`): the patterns
in `hooks/ai-path-guard-defaults.json:26-56` are anchored at any path segment
(`(^|/)\.ai/…`), so the plugin's own `skills/ai-init/templates/.ai/**` and
`tests/fixtures/**/.ai/**` are control files to the guard, and a `cat` of
`.ai/policies/path-guard.json` is denied by the reader rule (builder check,
2026-10-22).

D4a (plugin-wide) — read or write. The tripwire denies when the one-liner
mentions `.ai/state/` or `.ai/reports/` **and** shows a write indicator; a
one-liner with no write indicator is allowed. Write indicators, the builder's
exact regex: an `open(` with a mode containing `w`, `a`, `x` or `+`;
`write_text`, `write_bytes`, `json.dump(`, `os.replace`, `os.rename`,
`os.remove`, `os.unlink`, `shutil.`, `Path(...).unlink`, `truncate`; the
Perl/Ruby/Node/PHP equivalents (`open(... '>'`, `File.write`, `fs.write`,
`fs.rename`, `file_put_contents`, `unlink`, `rename`); a shell redirect `>`
or `>>` on the same segment whose target is under those paths. An `eval` keeps
the current rule (its body is opaque). The deny text does not change. Two new
fixtures pin a read-only one-liner (allow) and a `json.dump` one-liner (deny).

D4b (plugin-wide — developer's decision 2026-10-22: yes) — anchor
classification to the root. `protected_config` and `task_protected`
classification applies to paths under the resolved `.ai/` root of the
session's cwd, that root's `.claude/` and `.codex/`, and the installed home
trees (`~/.claude/hooks/ai-*`, `~/.claude/claude-agentic/`, the `~/.codex`
equivalents). A path elsewhere that merely looks like a control file — a
fixture tree in the scratchpad, `skills/ai-init/templates/.ai/`,
`tests/fixtures/**/.ai/`, a copy under `/tmp` — is `source`. Residual,
accepted by the developer: an agent in project A can write project B's
`.ai/state/` by absolute path and A's guard will not see it; B's guard would,
in B's session. Sensitive-file rules (`deny_patterns`: `.env`, keys) and
`dependency_instruction_patterns` stay unanchored: a secret is a secret
anywhere, and a vendored instruction file is third-party data anywhere. Side
effect worth having: the plugin's own templates become editable inside a
task, which task 4 relies on.

D4c (project-local, human-applied — developer's decision 2026-10-22: yes) —
accept the open pathological-input findings. The `known-risks.md` entries that
are still `Status: open` and are about the path guard's behaviour on
constructed input — at the time of writing: "`shell_segments` is quadratic on
one long segment", "One amplifying symlink keeps `realpath -m` past the hook
timeout", "`realpath`'s line count can balance while its lines are
misaligned", "The token pass strips quotes one character at a time" (if still
open when applied) — plus the residuals left in the two fixed entries "The
path guard is quadratic on long lines" (the `sh -c`/`eval` re-segmentation)
and "`sh -c` spellings `segments_of` does not read", get `Status: accepted
(2026-10-xx, docs/sdlc/specs/direct-mode-diet.md)` and one shared rationale
paragraph placed once, above the first of them. Entries already `fixed` are
not touched. Rationale, verbatim for the file:

> The guards defend against an agent's mistakes — a careless `rm`, a write to
> a frozen policy during a task, a commit with a secret — not against an agent
> that constructs a command to exhaust them. A command built to time the guard
> out is visible in the transcript and in the journal, and the human gate at
> T4+ is the boundary for anything that matters. Findings that need such a
> command are accepted here and do not open a task.

The same two sentences go into `.ai/policies/safety.md` as the guards' threat
model, so a future review has the sentence to cite instead of re-deriving the
risk. What happens when a guard exceeds the runtime's hook timeout (10 s,
`settings.common.json:46`) is the runtime's rule, not the guard's; the
acceptance does not claim it fails closed.

D4d — this is a rule change. D4a and D4b allow what was denied: by D1 they are
T4; the golden is re-recorded with `--record`; the diff of the golden is part
of the review (`docs/hook-performance.md:24-27`). The process-count budget of
`docs/hook-performance.md:36-44` is unchanged: both checks are in-process
regexes on the segments the guard already has; D4b adds one prefix comparison
per classified path and no process.

Tests: `tests/test-ai-path-guard.sh` — read-only one-liner allowed, write
one-liner denied, scratchpad `.ai/policies/x.json` write allowed from this
repository's cwd, `skills/ai-init/templates/.ai/policies/risk-tiers.json`
write allowed, the same basenames under the real root denied;
`tests/test-guard-characterization.sh` re-recorded, golden diff reviewed.

### §5 Three calls in direct mode

Facts. `SKILL.md:126-203` prescribes for T2–T4: `quick`, `test-run --scope
suite`, `test-run --scope e2e`, `step-done`, up to two `remediate`, `set
e2e_status`, `review-gate`, at T4 `stage human_approval`, then `close` —
seven to nine calls, each writing the handoff and a journal line (30 of the 65
events of T-2026-10-21-001 are `handoff_written`). `close` is `done` then
`archive` (`state.py:1381-1383, 2638-2664`); before it runs, `main()` refuses
it on pending questions (exit 4) and on a rejection not yet re-asked
(`guard_rejected`, exit 5, `state.py:2323-2345`); it is also the exit a quick
record takes when the task turns out to be T5+ (`SKILL.md:240-241`) and the
way to unfreeze policy files (`docs/faq.md:19-23`). `step-done` measures the
step diff, refuses `SCOPE_CHANGE_REQUIRED`, warns on budget and rescores
(`state.py:1001-1058`). `remediate` refuses while any step is `in_progress`
(`state.py:1219-1220`). `review-gate` runs the sensors and either writes
`skipped_green` or exits 2 "review required" (`state.py:1336-1378`); nothing
reads `sensors.json` back, and it is agent-writable. `test-run` runs one scope
and already writes `test_status` or `e2e_status` (`state.py:1265-1333`), which
makes the prescribed `set e2e_status` redundant.

D5a — `test-run --scope all`. Runs `verify_command`; if exit 0, runs
`e2e_command`; records both runs exactly as the two single-scope calls do, same
logs, same caps (`max_suite_runs` counts the suite part). A red suite stops
before e2e and prints what `--scope suite` prints today. `--files` is rejected
with `all`. `set e2e_status not_applicable` stays for the case the suite
cannot reach an e2e flow; `test-run --scope all --e2e not-applicable "<why>"`
is the one-call spelling of the same, and writes the same field and journal
line.

D5b — `close` is the direct-mode exit. In order, stopping at the first
refusal, each refusal naming the command that clears it; the existing exits 4
and 5 run first and are unchanged, and `close` on a task with no step done is
still the escalation exit:

1. For every step still `in_progress`, do what `step-done` does, with the same
   `SCOPE_CHANGE_REQUIRED` exit 6 and the same advisory budget line.
2. Run the review gate afresh (the sensors are deterministic tools and do not
   re-run the suite; no measurement is reused). Below or at
   `skip_review_at_or_below` with all green: `skipped_green`, continue.
   Otherwise, if `review_status` is not `passed` or `skipped_green`: exit 2
   "review required — run the tier's reviewer, `set review_status`, then
   `close` again" (or, after `passed_with_findings`, "run the suite once more";
   §3a).
3. If the tier has `human_approval: true` and no `gate_approved` for this
   task: request the gate (what `stage human_approval` does today), print the
   summary the human reads, exit 0 and stop. The human's `approve` is given
   outside; the next `close` passes this point.
4. `done`, then `archive`.

D5b′ — `remediate` finishes open steps. On a red run the three-call path has
step 1 still `in_progress`; `remediate` therefore first does step 1 of D5b for
every open step (same refusals), then opens the remediation step as today. The
refusal at `state.py:1219-1220` goes away; `step-done` stays for the sdlc
pipeline and the `team` profile.

D5c — the text. `SKILL.md` §1a steps 3–6 become: implement with step tests;
`test-run --scope all`; on failures `remediate` once and `test-run --scope
all` again; `close`. `AGENTS.md:51` (project copy, human-applied, and the
template `skills/ai-init/templates/.ai/AGENTS.md:51`) and the `solo` profile
strings `test`, `e2e`, `triage` in `risk-tiers.json:62-64` are reworded to the
same calls, and `risk-tiers.md` mirrors. The subcommand count stays 29; the
happy-path call count is 3 at T2/T3 and 5 at T4 (`quick`, `test-run`, `close`
→ review → `set review_status` → `close` → human `approve` → `close`).

Tests: `tests/test-ai-task-state.sh` — `test-run --scope all` records two
runs and skips e2e on a red suite; `remediate` finishes an open step first and
refuses on SCOPE_CHANGE_REQUIRED; `close` finishes an open step, refuses with
exit 2 when a review is owed, still exits 4 on a pending question and 5 after
a rejection, requests the gate at T4 (since redesign 2.H: in full and
full_irreversible mode) and archives after `approve`;
`tests/test-end-to-end.sh` — the three-call path on a fixture project with
green sensors ends in `skipped_green` and an archived state.

## Interfaces

New or changed, exact shapes:

```
state.py quick     --goal … --workflow … --tier T2|T3|T4 --files "a,b" [--tests "t1,t2"] [--note …]
state.py remediate --files "…" [--closes "H1,M2"] [--note …]      # finishes open steps first
state.py test-run  --scope step|suite|e2e|all [--files …] [--e2e not-applicable "<why>"]
state.py set       review_status not_started|in_progress|blockers_open|passed_with_findings|passed [--by <human>]
state.py close     # exits: 4 pending question, 5 rejected, 6 SCOPE_CHANGE_REQUIRED, 2 review required, 0 gate requested or archived
/ai-status         # adds "reviews: N of <review_rounds_max>"
```

`risk-tiers.json` (shipped default at
`skills/ai-init/templates/.ai/policies/risk-tiers.json`, and this repository's
`.ai/policies/` copy): top-level `"review_rounds_max": 2`. `REVIEW_STATUS`
list gains `passed_with_findings` after `blockers_open`. `state.json` gains
`reviews: <int>` (absent = 0) and, per remediation step, `closes: [labels]`.
Journal events: `findings_closed` (data: labels, run, tree),
`review_budget_refused` (data: reviews, max), `human_set` for `set --by`.
`.ai/reports/<task-id>/review-report.md` is written in direct mode too.

Reviewer output (`agents/ai-reviewer.md.tmpl`, `ai/agents/reviewer.md`):

```
- [HIGH] H1 <what is wrong> (`file:line`)  in_scope: yes|no
…
verdict: pass | pass_with_findings | blockers_open
```

Guard: no interface change; fixtures added and the golden re-recorded.
`testing.md` (project): unchanged. `known-risks.md`: `Status:` lines on the
open path-guard entries and one rationale paragraph; one new entry for review
provenance; one for the scope guard's reach. `safety.md`: one threat-model
paragraph. `constitution.md`: C6. `.ai/rules/hooks.md`, `.ai/rules/skills.md`:
new, three lines each. `CONTRIBUTING.md`: one line on pylint.

## Policy conformance

- C1: no deny that fires today on a real write stops firing; §4a narrows the
  tripwire to writes, §4b to the project's own trees, and both are pinned.
- C2: every section names the failing test it starts with; §2 makes the
  bugfix's test visible to the sensors.
- C3: §5 is a feature on `state.py`, not a refactoring, and ships alone; §4a
  and §4b are rule changes and ship alone with the golden.
- C4: §Order of work names the files of each task; this spec adds no file to
  any step the plan did not name.
- C5: the approvals in §Order of work are given outside the agent. §3d takes
  nothing from the human except unbounded re-reviews; `--by` keeps the
  override theirs; the policy diet is applied by the human, as the guard
  design intends.
- `docs/hook-performance.md`: the process budget is kept; the golden moves only
  through `--record` inside a reviewed rule change.
- `review-economy.md` §3: the design makes the policy enforceable; it does not
  change what the policy says.

## Flagged concerns

1. **The policy diet is your work, not the agent's.** `.ai/policies/*.json` is
   never agent-writable and the other policy files are frozen in any task, by
   design (`docs/hooks.md:144-146`). Task 2 therefore ends with a staged text
   file; applying it is one human commit with no task open. The upside: no T4
   gate, no STRONG review — you are the reviewer of your own policy.
2. **The diet pays the old price twice.** §3a lets a test run close a review
   verdict and §4 allows what was denied; by D1 both are T4, with plan mode,
   one STRONG review and the human gate. §3c ships first so those two reviews
   are bounded.
3. **`review_rounds_max` removes a human freedom.** After two verdicts the
   human can no longer ask the agent for a third review; they can only set the
   verdict with `--by`. Intended; the decision most worth reading twice.
4. **D4b narrows what the guard sees.** A write to another project's control
   files by absolute path passes the current project's guard. Accepted by the
   developer on 2026-10-22, because that project's own guard is the one that
   should decide, and because the alternative is treating the plugin's own
   templates and fixtures as control files.
5. **Acceptance under the hook timeout.** §4c accepts findings whose effect is
   a guard that exceeds the runtime's 10 s hook timeout. The runtime's
   behaviour on a timed-out PreToolUse hook is not asserted by this spec; if it
   proceeds with the call, a constructed command can bypass the guard, which
   the threat model in §4c says is out of scope. A policy decision, taken by
   the developer on 2026-10-22.
6. **Review provenance stays open.** `set review_status passed` with no review
   is possible today and after this spec. Recorded, not fixed.
7. **No intent file.** The template expects `docs/sdlc/intent/<slug>.md`; the
   developer asked for the design directly from the assessment, so the intent
   is §Intent above.
8. **Codex.** `set --by` must be denied for an agent under Codex too; the path
   guard's approve rule already covers `apply_patch` and `Bash` there. The
   builder extends the same rule, not a new one.
9. **The task in flight.** T-2026-10-21-001 is open (step R4 done, a review
   owed), holds uncommitted edits to `hooks/ai-path-guard.sh`,
   `tests/test-ai-path-guard.sh`, `known-risks.md` and `README.md` — files
   tasks 2 and 3 touch — and keeps the frozen files frozen. Its disposition is
   §Open questions Q1 and decides the golden baseline for task 3.

## Order of work

Four tasks, each its own `/ai-task`, in this order. Files per task are the
step's `allowed_files`; nothing else is touched. None can start before
T-2026-10-21-001 is closed (Q1).

1. **Reviewer boundary, verdict text, project examples sentence** — T3 (text;
   adds a verdict value in prose, moves no decision): `agents/ai-reviewer.md.tmpl`,
   `ai/agents/reviewer.md`, `skills/ai-task/SKILL.md` (§0 tier sentence and
   the ADVERSARIAL REVIEW section only), `ai/policies/review-economy.md`,
   `tests/test-shared-prompts-model-free.sh` if it asserts the template. §1
   item 6, §3c, §3d.
2. **Policy diet, staged** — T0 (one documentation file, no state file):
   the agent writes `docs/sdlc/plans/direct-mode-diet-policy-texts.md` holding
   the exact final text of every human-applied file: `.ai/policies/risk-tiers.json`
   (`examples`, `review_rounds_max`, profile strings), `.ai/policies/risk-tiers.md`
   (regenerated, new hash), `.ai/policies/safety.md` (threat model),
   `.ai/AGENTS.md:51`, `.ai/rules/hooks.md`, `.ai/rules/skills.md`,
   `docs/sdlc/constitution.md` (C6), `CLAUDE.md` (one line), `CONTRIBUTING.md`
   (pylint line), `.ai/project/known-risks.md` (statuses, rationale, provenance
   and scope-guard entries), and the same `review_rounds_max` and `AGENTS.md:51`
   edits for `skills/ai-init/templates/.ai/policies/risk-tiers.{json,md}` and
   `skills/ai-init/templates/.ai/AGENTS.md` with the template-history step the
   builder names. The human applies them with no task open and commits once.
   §1 items 1–5, §4c, the template side of §3b and §5c.
3. **Guard: reads and roots** — T4 (allows what was denied):
   `hooks/ai-path-guard.sh`, `tests/test-ai-path-guard.sh`,
   `tests/fixtures/path-guard/*` (new fixtures), `tests/test-guard-characterization.sh`
   re-recorded golden, `docs/hooks.md` (the tripwire's description). §4a, §4b.
   Goes before the state machine so that task 4 can edit the templates itself.
4. **State machine** — T4 by D1 (§3a lets a test run close a review verdict):
   `skills/ai-task/state.py`, `skills/ai-task/sensors.py` (D2a′ lint mapping,
   `closes` if it needs a sensor row), `skills/ai-task/SKILL.md` (§1a and §0
   text), `skills/ai-status/SKILL.md` (reviews line), `hooks/ai-path-guard.sh`
   and `hooks/ai-path-guard-defaults.json` (the `--by` rule, same pattern as
   `approve`), `tests/test-ai-task-state.sh`, `tests/test-ai-task-sensors.sh`,
   `tests/test-end-to-end.sh`, `tests/test-ai-path-guard.sh`. §2a′, §2b, §3a,
   §3b, §5.

Rollback for each: `git revert` of that task's commit; no data migration. A
state file written by task 4's `state.py` and read by the previous version
loses nothing (`reviews`, `closes` are extra keys); a `passed_with_findings`
value read by the old `REVIEW_STATUS` list is refused by `set` only, and
`/ai-status` prints it as unknown.

Verification per task: `verify_command` once, `e2e_command` once, through
`state.py test-run`. Task 4 is the one that changes `test-run` itself: its
suite runs on the tree with the new code, as every `state.py` change has.

## Left to the builder

- The exact write-indicator regex in §4a and the fixture texts.
- The finding-label format (`B1`, `H1`, `M2`…) and how `--closes` matches it
  against `review-report.md`.
- Where `reviews` and `closes` live in `state.json`, and the three journal
  event names, as long as `events --format jsonl` keeps printing them.
- Whether `remediate` already carries `required_tests` or needs `--tests`.
- Which existing suite, if any, asserts the `risk-tiers.md` mirror hash.
- The template-history step for the two template files, from
  `tests/test-merge-migration.sh`.
- The `CONTRIBUTING.md` wording for the pylint line.
- The one sentence for `CLAUDE.md` "Things Claude Code gets wrong".

## Decided (2026-10-22, developer)

- pylint: installed as the distribution package; `testing.md` unchanged (D2a).
- D4b anchoring: yes, with the stated residual.
- D4c threat-model sentence and acceptances: yes, as written.
- `review_rounds_max: 2`: shipped default, reaching user projects through
  `/project-update`.

## Open questions

- Q1 (owner: developer, closed 2026-10-29; the closing note follows the
  question) — T-2026-10-21-001. Finish it under the old rules
  (another STRONG re-review), close it as it stands, or abandon it. Recommended:
  close it as it stands, in your own terminal (`state.py set review_status
  passed`, `state.py close`, with a one-line note in `task.md` that the pending
  re-review is the loop this spec removes), and commit the working tree: the
  suite is green three times over and two STRONG reviews have read it. Task 3's
  golden baseline is then that commit. Nothing in §Order of work can start
  before this.

  Closed (2026-10-29), from the record. The task was finished under the old
  rules, not closed as it stood:
  - KNOWN FACT: `.ai/reports/T-2026-10-21-001/review-report.md` holds STRONG
    passes 2–5, four re-reviews after the first pass. Suite run 5 and e2e
    run 5 were green.
  - KNOWN FACT: the developer granted gate G2 from the terminal at
    2026-10-22T10:54:46Z (`events.jsonl:109`), and the task closed at
    10:55:27Z (`:110`).
  - KNOWN FACT: `053bf9a` (13:56 +0300) added its reports. Task 1 of
    §Order of work, `4b3b9e1`, followed at 14:35 the same day.
  - KNOWN FACT: its code is `e393224` (13:55 +0300), ten seconds after the
    close. The commit body names "T-2026-10-21-001, remediations R2-R4 of
    the batched movers pass (R1 is 3d923d5)".
