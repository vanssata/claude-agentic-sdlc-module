# Plan: Parallel light workers, native plan mode, simplify before close, review limit lift, plan rename

Spec: `docs/sdlc/specs/parallel-light-workers.md` · Decisions: `docs/sdlc/intent/parallel-light-workers.questions.md`
(Q1–Q6) and the spec's D7–D22.

Status: written 2026-11-26, not yet accepted. Branch `spec/parallel-light-workers` (`de29904`).

**How it runs.** Each row below is **one `/rr-build` task**, not one `/rr-build-all` batch. Two reasons. First,
WP2 and WP7 are behaviour 2 and need `start --mode full`, a STRONG review and the gate of their own. Second,
WP1 is a refactoring and must not share a task with a feature (C3). Rows that touch disjoint files may run in
parallel worktrees under `/Store/claude-agentic-wt`, a path without spaces, because the suite is red under
"/Store/Claude Plugins/".

**Model routing.** Implementers and fixers run on BALANCED (`sonnet`). Suite and log output goes to `log-reader`
on FAST (`haiku`). The session takes every decision. The review runs at each task's mode tier: full uses STRONG
(`opus`), guarded uses BALANCED.

**Flagged concerns of the spec.** Shown to ikakarov on 2026-11-26. The following are resolved by D7–D22: FC1,
FC2–FC4, FC5, FC6, FC10, FC11 and FC15. The following are accepted as stated in the spec ("Приемам всички",
2026-11-26) and carried into Risks below: FC7, FC8, FC9, FC12, FC13, FC14, the unknowns and the cost.

## Files that change

| Area | Files | What |
|---|---|---|
| spike | `docs/plan-mode-spike.md` (new) | WP0 findings: KNOWN with evidence, or UNKNOWN |
| shared procedures | `ai/workers.md` (new), `ai/agents/simplifier.md` (new), `skills/project-update/history/` (regenerated) | Waves/Fixers/Research; simplifier brief |
| skill texts | `skills/rr-build-all/SKILL.md`, `skills/rr-build/SKILL.md`, `skills/rr-plan/SKILL.md`, `skills/rr-spec/SKILL.md`, `skills/rr-review/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/rr-setup/SKILL.md`, `ai/using-riskrails.md` | choice points, plan mode, simplify, review lift, both behaviours (R23) |
| routing texts | `instructions/routing.md`, `instructions/stub.md` | single-session vs workers, Codex fan-out wording (FC2–FC4) |
| state machine | `skills/ai-task/rr_state/choices.py` (new), `questions.py`, `questions_cmd.py`, `start.py`, `task.py`, `policy.py`, `review.py`, `steps.py`, `handoff.py`, `report.py`, `journal.py`, `dialog_cmd.py`, `cli.py`, `profile.py`, `skills/ai-task/state.py` (usage) | §Interfaces of the spec |
| setup | `skills/rr-setup/setup.py` | `workers --set`, option keys, paging |
| profiles | `profiles/ultra.json` (new, from `max20.json`), `profiles/max20.json` (delete), `profiles/max.json`, `profiles/pro.json`, `profiles/codex-pro-200.json` (from `codex-pro.json`), `profiles/codex-pro-100.json`, `codex-pro-500.json`, `codex-go.json`, `codex-free.json`, `codex-business.json` (new), `profiles/codex-plus.json`, `profiles/codex-models.json` (new, WP8) | ids, aliases, `riskrails.workers.level` |
| resolver, installer | `scripts/resolve-profile.py`, `bin/riskrails.js`, `bin/wizard.js`, `hooks/context-guard.py` (names map `:501`) | aliases, menus, detection |
| tests | `tests/test_profiles.py`, `test_profile_detect.py`, `test_install_*.py`, `tests/fixtures/profile/claude-cases.json`, `tests/fixtures/install/non-tty.golden`, `test_setup.py`, `test_project_update.py`; new `tests/test_choices.py`, `tests/test_review_unlimited.py`, `tests/test_workers_cap.py`, `tests/test_plan_doc.py` | per row |
| docs | `docs/known-risks.md` (FC7, FC9, FC12), `CHANGELOG.md`, `README.md` (plan names) | per row |

## Order of work

Every row ends with `state.py verify --scope all` once, run to the end, and then `e2e_command` once
(`.ai/policies/verification.md:4,6`). A row that touches `ai/` or a shipped template runs
`tools/build-template-history.py` in the same task. *Consumes* lists the rows a row needs merged first.

| # | Row | Kind · mode | Files | Proof | Consumes |
|---|---|---|---|---|---|
| 1 | **WP0 spike.** Live checks with the human:<br>• EnterPlanMode/ExitPlanMode and its response<br>• Bash, hooks, subagents and `state.py ask --topic` inside Claude plan mode<br>• Codex `/plan`, its sandbox and `request_user_input`<br>• Claude's max parallel Task calls and Codex's threads<br>• `/simplify`: available, and on which model<br>• the Codex CLI model list | investigation · light | `docs/plan-mode-spike.md` | every check KNOWN with evidence, or UNKNOWN | — |
| 2 | **WP1 refactoring.** Move rr-build-all §3 Waves and §4 Fixers into `ai/workers.md` verbatim; rr-build-all points to it; rebuild history | refactoring · light | `ai/workers.md`, `skills/rr-build-all/SKILL.md`, `skills/project-update/history/` | `git diff` shows only moves; `test_project_update` green | — |
| 3 | **WP2 plan rename** ⚠ riskiest. Steps:<br>s1 characterization tests for today's detection and drift (C2)<br>s2 `ultra.json`, the codex-pro-100/200/500, go, free and business profiles; ALIASES in `resolve-profile.py`<br>s3 `profile.py`: PLAN_PROFILES, PLAN_ALIASES, normalisation, SAME_TIER, detection tables<br>s4 `riskrails.js` and `wizard.js` menus<br>s5 the `context-guard.py` names, README, CHANGELOG<br>s6 re-record the goldens | feature · **full**, `behaviour=2:"installer and resolver accept ultra and codex pro-100/200/500/go/free/business; max20 resolves to ultra by alias; an old codex pro reports drift and the human picks"` | profiles, resolver, installer, `profile.py`, `context-guard.py`, the profile and install tests, goldens | new tests:<br>• a max20 install on an ultra account reports `same`<br>• `profile set max20` resolves to ultra<br>• drift-ack `kept: max20` is acknowledged<br>• Codex `pro` reports drift and offers 3 choices<br>• go has level low and free has workers off<br>Also `test_profiles`, `test_profile_detect` and `test_install_*` green | — |
| 4 | **WP7 review limit lift.** Steps:<br>s1 tests for each refusal path (before the budget is spent; no pick → exit 5; unattended → refused); pin the guard denial of `review --unlimited --by` without a pick<br>s2 the `review.py` flag and the D_b decision<br>s3 the handoff, report and steps lines, and the `review_budget_lifted` event<br>s4 rr-review, rr-build-all and `using-riskrails.md` text (FC1: the lift is the human's), history | feature · **full**, `behaviour=2:"REVIEW_BUDGET can be lifted for one task by the human's pick; later passes record ordinary verdicts"` | `review.py`, `journal.py`, `handoff.py`, `report.py`, `steps.py`, `state.py`, `skills/rr-review/SKILL.md`, `skills/rr-build-all/SKILL.md`, `ai/using-riskrails.md`, history, `tests/test_review_unlimited.py` | `test_review_unlimited`:<br>• later passes are checked by `verdict_matches_findings`<br>• the batch budget is lifted too<br>• SUITE_BUDGET is unchanged | 2 (rr-build-all text) |
| 5 | **WP3 cap.** Steps:<br>s1 characterization test of `policy.py:103-105`<br>s2 `riskrails.workers.level` in every profile<br>s3 `workers_cap`: the level map, the overlay `batch.parallel`, the runtime clamp<br>s4 `cap` in `steps --json`; rr-build-all reads it | feature · guarded | `policy.py`, `steps.py`, profiles, `skills/rr-build-all/SKILL.md`, `tests/test_workers_cap.py` | low/medium/xhigh give 2/4/6; max gives the runtime limit; this repo's overlay 5 wins for batch; Codex clamps and prints why | 3, 4 |
| 6 | **WP4a choices.** Steps:<br>s1 `choices.py` and the `choice show/ask/set` CLI<br>s2 the `key:` line; a keyed answer records the pick<br>s3 `start --from-topic/--choice`; `apply_defaults_v7`<br>s4 `setup.py workers --set` with workers, research, simplify and `workers_level`; SETUP_VALUES; option paging<br>s5 the `choice_set` event and the handoff line | feature · guarded | `choices.py`, `questions.py`, `questions_cmd.py`, `start.py`, `task.py`, `cli.py`, `dialog_cmd.py`, `journal.py`, `handoff.py`, `state.py`, `skills/rr-setup/setup.py`, `tests/test_choices.py`, `tests/test_setup.py` | table tests over the Q1 matrix (ask/on/off × first stage, later stage, every):<br>• a task in flight resolves to off (R21)<br>• `TASK_IN_FLIGHT` exits 3<br>• `workers_level` is one 4-option decision<br>• a pick carries through `--from-topic` (D13)<br>• Codex free asks no workers question | 5 |
| 7 | **WP4b skill texts and both behaviours.** Steps:<br>s1 `ai/workers.md` §Research<br>s2 rr-spec, rr-plan, rr-build and rr-build-all call `choice ask` per stage<br>s3 `instructions/routing.md`, `stub.md` and the rr-setup text describe single session and workers, chosen by setting (R23)<br>s4 history | feature · light | `ai/workers.md`, the 5 skill texts, `instructions/routing.md`, `instructions/stub.md`, history | grep finds no unconditional "Implement it yourself" or "the session implements"; `test_project_update` green | 6 |
| 8 | **WP5 native plan mode.** Steps:<br>s1 `start --plan-doc PATH\|-` with tests<br>s2 the rr-plan, rr-spec and `using-riskrails.md` flows for Claude and Codex, with the WP0 fallbacks; history | feature · guarded | `start.py`, `task.py`, `state.py`, `skills/rr-plan/SKILL.md`, `skills/rr-spec/SKILL.md`, `ai/using-riskrails.md`, history, `tests/test_plan_doc.py` | the plan doc is copied with its sha256; `test_project_update` green | 1, 7 |
| 9 | **WP6 simplify before close.** Steps:<br>s1 the `simplify` key and the `workers.json` default<br>s2 `ai/agents/simplifier.md`<br>s3 rr-ship §0 text; history; FC7 in `known-risks.md` | feature · guarded | `choices.py`, `ai/agents/simplifier.md`, `skills/rr-ship/SKILL.md`, `skills/rr-build/SKILL.md`, `docs/known-risks.md`, history, `tests/test_choices.py` | a pending simplify makes `close` exit 4; `simplify=off` asks nothing; the tree before and after is recorded | 6, 8 |
| 10 | **WP8 Codex model ids.** Steps:<br>s1 `profiles/codex-models.json` from the installed Codex CLI, with version and date<br>s2 the ids in the profiles; re-render the goldens. Skipped if the CLI lists no models (D17) | feature · light | `profiles/codex-*.json`, `profiles/codex-models.json`, `tests/test_profiles.py`, goldens | `test_profiles` fails on any id not on the list | 1, 3 |

Parallel tracks: rows 1, 2 and 3 have disjoint files and can run at once. Row 4 waits for row 2. After that the
rows run in order: 5 → 6 → 7 → 8 → 9, because they share `policy.py`, `steps.py`, `start.py` and the skill texts.
Row 10 can run any time after rows 1 and 3.

## Risks

1. **⚠ Row 3, the rename, is the riskiest.** It touches every install. If the Python port and `riskrails.js`
   disagree, two installers report different plans. A stale `drift-ack.json` or `profile.json` can hold `max20`
   or `pro`. *Noticed by:* the `claude-cases.json` parity fixture and the goldens. *Mitigation:* row 3 runs first
   among the features, with characterization tests before any edit.
2. **Row 4 weakens a refusal.** A wrong condition would let an agent lift the budget itself. *Mitigation:* the
   tests are written first (s1), the existing guard rule `paths_human.py:42` is pinned by a test, and unattended
   runs are refused (D12).
3. **Parallel writers in one tree.** Undeclared side-effect files and shared test resources can clash.
   *Mitigation:* steps that share a file stay ordered; `workers=off` is the escape hatch; the same risk already
   exists in batch.
4. **Plan-mode unknowns (FC8).** If WP0 shows that Bash or `state.py` writes are blocked in plan mode, row 8
   takes the fallback: questions are recorded right after leaving plan mode. Row 8 consumes row 1 for this
   reason.
5. **Simplify after review (FC6, FC7).** The reviewer does not see simplify's edits, and pre-existing lines may
   be refactored; only the brief limits this. Both are recorded in `known-risks.md`, and the rerun `verify` is
   the only check on those edits.
6. **Topic mode reads `.ai/` (FC9).** `workers.json` is read-only there; the deviation from `cli.py:193` is
   documented in row 6's code comment and in `known-risks.md`.
7. **Cost.** Up to 6 BALANCED workers on Ultra, 4 on Max, plus research and simplify agents. The shipped default
   is `ask`; `/rr-status --cost` shows where tokens went.
8. **Missed history rebuild.** Rows 2, 4, 7, 8 and 9 touch `ai/`. If the rebuild is skipped,
   `test_history_covers_every_template` goes red, so a missed rebuild shows up in the suite.
9. **Rendered `~/.claude/CLAUDE.md` stays old** until the installer is re-run after row 7. That re-run is a
   human step.

## Proof (tests)

| Requirement | Proof |
|---|---|
| R1, R2, R5, R21 | `tests/test_choices.py`, `tests/test_setup.py` (row 6) |
| R3, R4, R6, R24 | `tests/test_choices.py` Q1 matrix and `--from-topic` cases (row 6) |
| R7, R10, R11 | `tests/test_workers_cap.py`, `tests/test_profiles.py` (rows 3, 5) |
| R8, R9 | `ai/workers.md` text, shown by a `test_project_update` history check; e2e run of a 2-step disjoint task with workers on (row 7) |
| R12, R13 | `tests/test_profile_detect.py`, `tests/test_profiles.py`, `tests/test_install_*.py` (row 3) |
| R14 | `tests/test_profiles.py` model allowlist (row 10) |
| R15, R16, R17 | `tests/test_plan_doc.py` (row 8); skill text against `docs/plan-mode-spike.md` (row 1) |
| R18 | `tests/test_choices.py` simplify cases: `close` exit 4, `off` asks nothing (row 9) |
| R19, R22 | `tests/test_review_unlimited.py` (row 4) |
| R20 | `handoff` and `status` golden lines (rows 4, 6) |
| R23 | grep check in row 7; `test_project_update` |

## Rollback

Each row is one merge: `git revert <merge>`. Row 3 needs care: reverting it brings back `max20.json` and
`codex-pro.json`, and a machine already re-installed on `ultra` reports drift until the installer is re-run.
Row 4 reverts cleanly because `review.unlimited` is an additive state field that older code ignores.
