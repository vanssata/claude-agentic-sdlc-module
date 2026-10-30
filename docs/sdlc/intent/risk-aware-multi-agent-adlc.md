# Intent: Risk-aware multi-agent ADLC — an optional module

<!-- Stage 1 of the SDLC flow. Say WHAT and WHY. Leave HOW to the spec. -->

**Status: BLOCKED — next task after `docs/sdlc/specs/small-oop-modules.md` closes its last
work package.** Written 2026-10-31 by the session (Fable) from the developer's prompt
"INTENT: Risk-Aware Multi-Agent ADLC Evolution" (same day), restructured against the
repository as it is; the prompt's §13 deliverables 1–3 (capability assessment, gap analysis,
risks and conflicts) are in this file, deliverables 4–10 belong to the spec and plan and are
not written until the block lifts. It absorbs ROADMAP §1 "Agentic SDLC modes" (the
`agentic-sdlc-modes` brainstorm, Q1 = Hybrid) as its autonomy section. Decisions on record:
`docs/sdlc/intent/small-oop-modules.questions.md` Q5 (order) and Q8 (this file, no spec yet).

## Problem

- RiskRails runs one task at a time in one working tree. `/rr-build-all` already dispatches
  up to three implementers in parallel, but they share the tree, the task's single scope
  guard and one journal; two steps that name one file are serialised, and a step's edit of
  another step's file is recorded (`own`/`others`), not refused (`batch-build.md` FC3, FC4).
- Verification is bound to the tree loosely: `close` measures a green whole-suite verify "on
  the tree as it is now" and a changed tree invalidates an approval, but no review or verify
  record carries the tree hash it was measured on, and a cross-vendor review is never
  recorded for a schema-7 task (open risk, found 2026-10-26).
- Recovery is handoff-based: `.ai/state/handoff.md` plus `/rr-build-all --resume`. There is
  no record of a failed attempt that the next attempt reads, no per-step retry count, and an
  interrupted implementer leaves a half-edited tree the resume logic infers from `git status`.
- Measurement is cost only: `/rr-status --cost` and `usage-report` read the transcripts;
  nothing counts first-pass acceptance, review iterations, human stops per task, or recovery
  success. The redesign analysis counted those by hand from 65 journals.
- Impact analysis is file-based: `state.py recall --files` lists the register's risks for the
  task's files; nothing finds the callers or tests of a changed function before the plan.
- Legacy projects (the production shop, ERP and payment integrations, shared databases) are
  the stated audience, and the audience least served by "more agents": they need the guard,
  the characterization test and the human gate to hold while more than one agent works.

## Proposed outcome

Observable once the module ships and is switched on; every one is false today.

- O1 Two implementers can run on steps that touch disjoint files without seeing each
  other's edits until integration, and an edit outside a step's files is refused per
  implementer, not per task.
- O2 Every `verify` and `review` record names the tree hash it measured; `close` refuses a
  verdict whose hash is not the tree's, and says which record is stale.
- O3 An interrupted step resumes from a recorded attempt (what was tried, the error text,
  the count), and the budget of attempts per step is a policy number, not a loop's memory.
- O4 `/rr-status` prints, from the journal alone: first-pass acceptance, review and fix
  rounds, human stops, recovery events and cost per accepted task, for one task and for a
  range of dates.
- O5 With the module off (one policy key), every command, file and refusal behaves as the
  3.x line does; the suites that pin today's behaviour stay green unchanged.
- O6 A documented dogfooding run — one real plan of this repository through the module —
  exists with its journal and its numbers next to the same plan run the old way.

## Capability assessment (what exists, 2026-10-31, from the code)

| Prompt asks for | Exists | Where | Gap |
|---|---|---|---|
| dependency-aware plan execution | yes | `steps --ready`, `after` ids, cycle check, shared-file ordering (`state.py:3329-3425`) | no `blocks` vs `related` distinction; ready = all `after` done |
| parallel implementers | yes, ≤ 3 on BALANCED | `/rr-build-all` §3, `batch.parallel`, `batch.tier` | one tree; per-task scope guard |
| isolation (worktrees) | no | — | O1 |
| conflict detection | partial | steps sharing a file are serialised at `start`; `step_done` records `own`/`others` | no refusal, no merge step |
| deterministic state machine | yes | `state.py` (schema 7/11), journal `events.jsonl`, `task.md` | keep as the only controller |
| recovery / resume | partial | `handoff.md`, `--resume`, `git status` compare | O3 |
| bounded loops | yes | `SUITE_BUDGET`, `REVIEW_BUDGET`, `batch.review_rounds_max`, `max_suite_runs` | per-step attempt budget missing |
| risk → ceremony | yes | six axes → light / guarded / full; reviewer tier by mode; human stops by mode | risk does not yet pick isolation or parallelism |
| model tiers, provider-neutral | yes | FAST / BALANCED / STRONG / EXPERT; `profile.json`; `runtime-gate` | cross-vendor reviewer route unrecorded |
| deterministic tests before review | yes | `verify --scope all` before `review` is accepted; red verify blocks | — |
| findings → scoped fixes → re-verify | yes | `review --closes`, `--after-fix`, MEDIUM/LOW to the register | — |
| verification bound to git state | partial | `current_tree`, approval invalidated by a changed tree | O2: hash on every record |
| human approval gates | yes | full mode gate, dialog, `consent.jsonl`, `AI_UNATTENDED` visible | keep; never weakened |
| adversarial review | yes | `ai-reviewer`, fresh context, diff-only brief | independence not measured |
| impact analysis | partial | `recall --files`, weight `scope` axis counts references | callers/tests of a changed symbol |
| metrics | cost only | `usage-report`, `/rr-status --cost` | O4 |
| benchmark | no | — | see Prior art: no fair harness exists for workflows |
| traceability | partial | spec → plan rows → task → journal; plan "Proof" per requirement | requirement id not carried into `events.jsonl` |

## What this intent changes against the 2026-10-31 prompt, and why

- **Models become tiers.** The prompt names Fable, Opus, Sonnet and Astra; the project's
  rule is "tiers, never models" (`routing.md`; `test_skills_surface` fails a skill text that
  names a model). Responsibilities map: intent and design → the session or EXPERT on a
  trigger; planning and architectural review → STRONG; parallel implementation and fixes →
  BALANCED; a second vendor's reviewer → an optional EXPERT-cross route, recorded in the
  journal, used only where the weight asks for it.
- **Nothing new orchestrates.** The prompt's "orchestrator" is `/rr-build-all` plus
  `state.py`; every capability above is an addition to a step's record, a policy key or a
  `state.py` check — no second state, no service, no broker (prompt §14, kept).
- **Benchmark scaled down.** Comparing against competing SDLC workflows needs a harness that
  does not exist (Prior art); the first benchmark is self-comparison — the same plan of this
  repository run the old way and through the module — with the numbers taken from the
  journal. Superiority claims wait for results, as the prompt itself demands.
- **Blocked, by design.** The module is optional and lands after the large files are split;
  building worktree isolation into a 5 256-line `state.py` is the kind of change the split
  exists to make reviewable.

## Reduced scope — what the spec should design (candidates, not decisions)

1. **Isolation as a step property.** `batch.isolation: none | worktree` in the policy; with
   `worktree`, an implementer gets `git worktree add` on a branch per step, and the scope
   guard reads the step id from the worktree's state so the refusal is per implementer.
   Integration is one serial step in the session: fast-forward or rebase onto the task
   branch, the suite once, a conflict → that step re-opened with the conflict text in its
   attempt record (escalation ladder: auto → one agent attempt → human).
2. **Tree hash on every record.** `verify`, `review` and `approve` write `tree:` (`git
   write-tree` over the index plus a hash of the untracked files the suite touched); `close`
   compares and names the stale record. Fail closed on a missing field.
3. **Attempt records.** `step_attempt` journal type: step, n, outcome, error excerpt (≤ 500
   bytes), tree hash. `steps --ready` skips a step past `batch.attempts_max`; the human
   reopens it. Resume reads the last attempt instead of inferring from `git status`.
4. **Metrics from the journal.** `status --metrics [--since]` derives first-pass acceptance,
   review/fix rounds, human stops, recovery events, cost per accepted task (cost from
   `usage-report`); no LLM estimate anywhere.
5. **Autonomy modes (from ROADMAP §1).** AI / Hybrid / Manual decide *who answers a
   question*, never a gate: a self-answer gets its own `via: agent` in the journal; approval,
   a lower mode, a run past a budget, `--confirm-delete`, `memory pack|cleanup` stay human in
   every mode. `/rr-build-all` in Hybrid answers a question that has `--recommend` and stops
   on one that has not.
6. **Impact hint before a plan.** `recall --symbols` (or the weight's `scope` axis) lists the
   callers and tests of changed functions from `grep`, as a hint printed at `start`, never a
   gate (redesign R4).
7. **Cross-vendor review route.** `review --tier EXPERT-cross` records the vendor in the
   journal; chosen by the weight only for domain = 2 or reversibility = 2, off by default.

Everything is behind one switch, `orchestration.enabled` (or the `batch` section's key the
spec prefers), default off; with it off the code paths are the 3.x paths and the goldens of
`small-oop-modules` stay byte-identical.

## Prior art (research 2026-10-31, nine web searches, snippets and READMEs, not code)

- Readiness and dependencies: Beads — four relation types, only `blocks` gates `bd ready`,
  cycle detection, hash ids (https://beads.gascity.com/core-concepts/dependencies); Claude Code
  agent teams — a pending task with unresolved dependencies cannot be claimed,
  `TaskCreated`/`TaskCompleted` hooks block with exit 2 (https://code.claude.com/docs/en/agent-teams).
- Isolation and merge-back: Overstory — worktree per worker, FIFO merge queue, a four-tier
  resolver auto → referee agent → human, and the note that conflicts are the normal case
  (https://github.com/hazat/overstory); SwarmGit, agent-queue (`flock` merge lock), mergetrain
  (gates before push). No project found that declares file scopes up front — RiskRails already
  does, which is the thing to keep.
- Verification bound to a commit: guildless (`testedCommit` must equal HEAD, fail closed,
  https://github.com/guildless-ai/guildless); ao-orchestrator (`commit-ok` needs gates, review,
  an unedited plan and a measurement matching the tree, https://pypi.org/project/ao-orchestrator/0.5.0/).
- Recovery: Ralph loops — fresh agent per pass, state only in git and `prd.json`, no memory
  of failed attempts (https://rywalker.com/research/ralph); pyralph adds retry with the error
  fed back. The lesson: write every failed attempt into the state.
- Cross-model review: claude-code-cross-review and hyperskills cross-model-review (one vendor
  writes, the other reviews); only a blind-spot argument, no measured catch rate.
- Metrics: SWE-Bench+ cost per resolved instance (https://arxiv.org/pdf/2410.06992); a 2026
  comparison of an orchestrator-with-subagents scaffold against SWE-agent on SWE-bench
  Verified/Pro (https://arxiv.org/pdf/2606.25514). No reproducible harness compares
  *workflows* on first-pass acceptance or human interventions — the gap the benchmark here
  would fill, starting with self-comparison.
- Not covered by the search (not ruled out): Codex multi-agent, OpenHands, Roo/Cline, Spec
  Kit, Kiro, AI-DLC, LangGraph, CrewAI, AutoGen.

## Affected users & systems

The task state machine (after the split: `rr_state/steps.py`, `verify.py`, `review.py`,
`close.py`, `report.py`, `journal.py`), `hooks/guard/scope.py` (per-worktree state lookup),
`/rr-build-all` and `/rr-status` skill texts, `.ai/policies/weight.json` (`batch` section or
a new `orchestration` key, rendered into `weight.md`), `ai/agents/implementer.md` (the
worktree contract), `docs/architecture.md`, `docs/workflows.md`. User projects: nothing until
they switch the key on; the schema may need one migration for the new policy key.

## Constraints

- Optional, default off, one switch; off means the 3.x behaviour, pinned by the goldens.
- One state machine, one journal, one scope rule (constitution C4; prompt §10, §14).
- No external service, database or broker; `git` and the standard library.
- No gate weakened: the human stops, budgets, `--confirm-delete`, the approval invalidated by
  a changed tree, the deny rules of the guards (prompt §3 "never weaken"; ROADMAP §4).
- Tiers, never model names, in every skill and agent text.
- Measurements come from `events.jsonl` and the transcripts, never from a model's estimate.
- Codex: the same contract, degrade to "allow and explain" where its spawn facility differs.

## Out of scope

A new orchestration framework; a second state store; microservices; agents that duplicate
`implementer`, `ai-reviewer`, `architect`; an observability stack; a LOCAL model tier; a
sandbox (ROADMAP §4); competitive benchmarks before a fair harness exists; `bin/riskrails.js`.

## Risks and architectural conflicts seen now

- A per-worktree scope guard changes where the guard reads its state — a change to a deny's
  input is behaviour 2 under C6: full mode, STRONG review, the guard golden byte-identical
  with the switch off.
- Worktrees and the hooks: the guards find `.ai/` by walking up from `cwd`. If the state is
  copied into the worktree there are two writers; if it is shared, the step id is ambiguous.
  The spec settles this first.
- The dialog gate and `consent.jsonl` are per machine and per session; a parallel implementer
  must never reach a human-only route — the agent markers refuse it today, keep that.
- Codex parallelism is observed, not guaranteed (Known risks); the module's contract names
  the tier and the step, not the mechanism.
- Metrics from the journal are only as good as the vocabulary; a new event type is a change
  to `EVENT_TYPES`, which `memory_compact` and the goldens read.
- Blocking everything until the split closes (Q5) delays this by six work packages.

## Decisions taken

- Operating mode for this work: **Hybrid** — `agentic-sdlc-modes` Q1 = B (developer,
  2026-10-29).
- Order: after the risk burndown in flight and after `small-oop-modules` WP1–WP6 —
  `small-oop-modules` Q5 (developer instruction 2026-10-31).
- Form now: intent only; spec and plan after the block lifts — `small-oop-modules` Q8.
- Optional module, one switch, default off — developer instruction 2026-10-31 ("опционален
  модул").

## Open questions (for the spec stage)

- **(blocking)** Where a worktree's step finds its state: shared `.ai/state` through the main
  tree, or a per-worktree copy with one writer. Decides the guard change and its weight.
- Whether `orchestration` is a new policy file or keys under `batch`; migration needed?
- Which weight signals pick isolation and parallelism (scope ≥ 1 and files disjoint?).
- The self-answer `via` value and what Hybrid does on a question without `--recommend` in
  `/rr-build-all` (ROADMAP §1, carried).
- The minimal tree hash: `git write-tree` alone misses untracked files the suite writes
  (`moved_detail` exists for that); what the hash covers.
- Proposed ADRs to write with the spec: ADR-0001 "one state machine; isolation is a step
  property", ADR-0002 "verification records carry the tree hash and fail closed".

## How to pick it up (after the block)

```bash
/rr-spec docs/sdlc/intent/risk-aware-multi-agent-adlc.md
/rr-plan docs/sdlc/specs/risk-aware-multi-agent-adlc.md
/rr-build-all docs/sdlc/plans/risk-aware-multi-agent-adlc.md   # or /rr-build, row by row
```
