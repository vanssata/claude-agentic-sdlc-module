# T-2026-10-25-008 — review

## Pass 1 — ai-reviewer, STRONG (opus), full diff · verdict: blockers_open

Reviewed the working tree after suite run 2 (green) and e2e run 1 (green). The
reviewer's experiment scripts are in /tmp/rev008/ (outside the repository).

FINDINGS
[BLOCKER] B1 skills/ai-task/state.py:3924 (cmd_approve_v7 `approved_tree=current_tree(root)`) + :3777-3781 (gate_approved_for) — an approval binds to the tree at `approve` time, not the tree close put up (`gate.tree`); close never checks a full_irreversible approval's --confirm against the current `weight.operations`. Scenario: full task, close opens the gate, agent writes `DROP TABLE users;` into a migration while the gate is open, human approves without --confirm (mode still "full"), close re-scores to full_irreversible, a fresh `verify --scope suite`, close archives "closed (full_irreversible)" with gate.confirm None. in_scope: yes
[HIGH] H1 skills/project-update/migrations/0007_weight_model.py:121-131 — convert() copies sensors.tests.{timeout_seconds,env_retries,log_max_bytes,max_suite_runs} and remediation_rounds from an unedited risk-tiers.json over the project's own weight.json values (never compared with the shipped ones). Scenario: weight.json with max_suite_runs 1, timeout 3600, remediation_rounds 4 comes out of 0007 with 2/1800/2 — edits lost, the suite budget loosened. in_scope: yes
[HIGH] H2 skills/ai-task/state.py:3664-3667, :3755 — the verdict is never checked against the FINDINGS block state.py parses, and --report is optional although the spec writes `--report -`. Scenario: `review --verdict pass` with stdin "[BLOCKER] B1 … in_scope: yes" records passed with findings ['B1']; close archives with the BLOCKER open; `review --verdict pass` with no report also closes a guarded task. in_scope: yes
[MEDIUM] M1 skills/ai-task/state.py:3538-3543, :3579 — `--e2e not-applicable` overwrites a recorded failing e2e. in_scope: yes
[MEDIUM] M2 skills/ai-task/state.py:3771 — e2e status is not tied to a tree: e2e green on X, edit to Y, suite green on Y, close passes without e2e on Y. in_scope: yes
[MEDIUM] M3 skills/ai-task/state.py:3503 — a run's tree is snapshotted after the command, not before; an edit during a run is credited as tested. in_scope: yes
[MEDIUM] M4 skills/ai-task/state.py:3516-3519, :3735 — the R19 waiver is symmetric; the spec waives a Codex-only failure. A red under claude after a green under codex is waived. in_scope: yes
[MEDIUM] M5 skills/ai-task/state.py:2865-2925 vs :3777 — the questions --sync file route grants human_approval but never fills gate.approved_by/approved_tree, so close re-opens a gate (G2, G3 …) for ever. in_scope: yes
[MEDIUM] M6 skills/ai-task/state.py:3211, :3913 — operations are stored as regex source ('ALTER .* DROP') and --confirm is a literal substring match against it: a human's "ALTER TABLE users DROP COLUMN email" is refused; the printed hint asks for the regex. in_scope: yes
[MEDIUM] M7 skills/ai-task/state.py:3347 + hooks/ai-scope-guard.sh — `start --files " , "` exits 0 with allowed_files [], which disarms the scope guard for the task. in_scope: yes
[MEDIUM] M8 skills/ai-task/state.py:3756, :3781 — outside git, tree None: `review.tree == tree` is None == None (a review stands for ever), and gate_approved_for needs a truthy tree (full mode loops on the gate). in_scope: yes
[LOW] L1 skills/ai-task/state.py:3864, :3953-3960 — task.md §Questions depends on os.path.exists(questions.md); a review text containing ``` breaks the §Review fence. in_scope: yes
[LOW] L2 skills/ai-task/state.py:3800-3801 — close says "review required" when only e2e is owed. in_scope: yes
[LOW] L3 skills/ai-task/state.py:2528 — the old-surface handoff header falls back to 0007's `mode` (cosmetic). in_scope: yes
[INFO] I1 state.py:3363-3376 — `close --abandon` then `start` takes the abandoned task's edits into the new base tree (same as the old done --abandon + init). in_scope: yes
[INFO] I2 state.py:3756-3768 — per R6 a review on the current tree replaces a red fact (a) in every mode, so a red suite closes after a pass verdict; the review's tree is taken at record time. Spec-conformant; for the risk register. in_scope: yes
[INFO] I3 state.py:3200-3212, 0007:105-118 — irreversible_content is case-sensitive (lowercase `drop table` never reaches full_irreversible); 0007 maps project-added auth scopes to a +1 hint, non-prod infra to needs_step, unknown scopes below T5 are dropped without a hint. in_scope: no
[INFO] I4 sensors.py:297-308 — with .ai/ in a subdirectory of the git top level, diff_files paths are top-level-relative while task files are root-relative: fact (b) always red, rescore reads wrong paths. in_scope: no

VERDICT blockers_open

Examined and clean (reviewer): D1 (no old body edited; routing only on schema 7; old-only and new-only commands refuse each other; guard_rejected skipped only for schema 7), D2 (synthetic step "task" read by the scope guard; only hole M7), the human-only paths (approve exit 5, open gate blocks close/verify with 4, lowering --mode needs human_route, SUITE_BUDGET/REVIEW_BUDGET 6), fact (a) excluding narrowed, expected_fail and exit-None runs, re-score never lowering and keeping a human-lowered mode, 0007 idempotence and the in-flight patch, status.py fallback, usage-report on both journals, the two shell-suite adaptations.

## Next

Fixing B1, H1, H2 and M1–M8 is one remediation batch, then one verification run, then one scoped re-review. Both remediation rounds and both suite runs of this task are spent (R1, R2; suite runs 1 and 2), so the third round is the human's decision.

## Remediation R3 (opened by the human, 2026-10-26)

| Finding | Fix | Pinned by |
|---|---|---|
| B1 | an approval counts only for `gate.tree` (the tree close put up) and only when granted after the request; `approve` refuses when the tree moved under the gate; full_irreversible needs a confirm naming every operation | `TestReviewPass1::test_an_approval_is_for_the_tree_close_put_up` |
| H1 | 0007 carries a scalar only when the old table changed it and weight.json still holds the shipped value | `TestMigration0007::test_a_projects_own_weight_values_survive` |
| H2 | `review` needs a FINDINGS block; an in-scope BLOCKER forces blockers_open, an in-scope HIGH forbids pass, a VERDICT line must match | `::test_a_verdict_must_agree_with_its_findings` |
| M1 | `--e2e not-applicable` refuses while an e2e run is red on this tree | `::test_a_red_e2e_is_not_declared_away` |
| M2 | e2e status is tied to `e2e_tree`; close owes e2e on the current tree | `TestTwoFacts::test_human_edit_after_verify` (now asserts "verify required" before `verify --scope e2e`) |
| M3 | a run's tree is snapshotted before and after; a moved tree stands for none | `::test_a_run_whose_tree_moved_stands_for_no_tree` |
| M4 | only a red under Codex on a tree green elsewhere is waived, in either order | `::test_a_red_under_claude_is_never_waived`, `TestSurface::test_red_then_green_across_runtimes_is_a_finding` |
| M5 | the file route closes the gate through `human_approval`; close fills `gate.approved_by` | `::test_the_questions_file_route_closes_a_full_task` |
| M6 | operations are keywords (DROP, ALTER); confirm names each as a word | `::test_confirm_names_an_alter_in_the_humans_words` |
| M7, M8 | `start` refuses an empty file list and a tree outside git | `::test_start_refuses_an_empty_scope_and_a_tree_without_git` |
| L1 | §Questions from the journal; a fence longer than any backtick run | `::test_task_md_fences_a_report_that_quotes_code` |
| L2 | close exits 2 with "verify required" when only e2e is owed | `test_human_edit_after_verify` |
| L3, I1, I2 | no change: cosmetic / same as the old surface / spec-conformant | — |
| I3, I4 | `.ai/project/known-risks.md` | — |

Each `TestReviewPass1` test failed on `state.py` from R3's tree_before (915410c11) and passes after. H1's pre-fix failure is the reviewer's own run (/tmp/rev008/m1.py); the pre-fix end-to-end check from this session was refused by the path guard and not reworded.

## Pass 2 — ai-reviewer, STRONG (opus), scoped to R3 · verdict: pass_with_findings

CLOSES
B1 closed · H1 closed · H2 closed (BLOCKER/HIGH and missing report; see N4) · M1 NOT closed · M2 closed · M3 closed · M4 NOT closed · M5 closed · M6 closed · M7 closed · M8 closed (start refusal pinned; the on_tree guard is unreachable now) · L1 closed · L2 closed

- M1 not closed: e2e_na refuses only on the same tree (state.py:3556-3557); e2e red, a whitespace edit, `verify --scope suite`, then `verify --scope e2e --e2e not-applicable` exits 0 and a guarded task closes with e2e failing.
- M4 not closed: only "green, then red" is one-way (state.py:3786-3788); claude red (run 1) then codex green (run 2) on one tree gives fact (a) green and close passes.

FINDINGS
[HIGH] N1 skills/ai-task/state.py:3554-3560 + :3832-3834 — with `e2e_command: none`, after any edit following an e2e not-applicable, close asks for `verify --scope e2e`; run_v7 runs `none`, which records exit None as a failing e2e on this tree; e2e_na then treats exit None as red and refuses `--e2e not-applicable` and the `verify --scope all` none branch; `verify --scope all` hits SUITE_BUDGET. Dead end (the same refusal hits a real e2e environment failure, exit None). in_scope: yes
[MEDIUM] N2 skills/ai-task/state.py:3535-3537 — a red not under codex on a tree green elsewhere records no finding any more (claude red, codex green: closes, the red only in the run table). in_scope: yes
[LOW] N3 skills/ai-task/state.py:3605, :3614 -> :3559 — `verify --scope all --e2e not-applicable` runs the whole suite before e2e_na refuses; die() exits before save(), the run is unrecorded and its log name reused. in_scope: yes
[LOW] N4 skills/ai-task/state.py:3658 — VERDICT_LINE_RE reads only `^VERDICT <x>`; the shipped reviewer writes `## VERDICT` / `verdict: <x>` (ai/agents/reviewer.md:49), so the VERDICT-line check never fires on the shipped format. in_scope: yes
[LOW] N5 skills/ai-task/state.py:70-74 — the usage docstring still shows `[--report -|FILE]` as optional and `--confirm "<operation>"`. in_scope: yes
[INFO] N6 state.py:3506-3515 — a suite that writes an untracked, non-ignored artifact (.coverage, junit.xml) moves the tree on every run: no run ever stands for a tree. in_scope: no
[INFO] N7 state.py:3213 — a project-added irreversible_content pattern whose match starts with whitespace raises IndexError; one starting with punctuation yields a keyword confirm can never name. in_scope: no

VERDICT pass_with_findings

Both review passes of this task are spent; the next verdict is the human's.

## Remediation R4 (2026-10-26)

| Finding | Fix | Pinned by |
|---|---|---|
| N1 | `e2e_command: none` is a declaration, never run: `verify --scope e2e` records not-applicable on every tree; close's e2e line names `--e2e not-applicable` after one | `TestReviewPass2::test_e2e_command_none_is_declared_on_every_tree` |
| M1 | the last e2e run decides on whatever tree it ran: red refuses not-applicable until an e2e run passes; a run that did not finish (exit None) is re-run, not declared away | `::test_a_red_e2e_is_not_declared_away_after_an_edit` |
| M4 | a non-Codex red is answered only by a later green under its own runtime; a Codex red is still waived by a green elsewhere, in either order | `::test_a_green_under_codex_does_not_answer_a_red_under_claude` |
| N2 | every cross-runtime disagreement on one tree goes into task.md's findings; a non-Codex red says close is blocked | same test |
| N3 | `--e2e not-applicable` is refused before the suite runs | `::test_a_refused_declaration_runs_no_suite` (no `suite-3.log`) |
| N4 | `VERDICT_LINE_RE` reads `VERDICT x`, `VERDICT: x`, `## VERDICT` + `verdict: x` | `::test_the_shipped_verdict_section_is_read` |
| N5 | usage docstring: `--report -\|FILE` required; `--confirm` names every operation | — |
| N6, N7 | `in_scope: no`: `.ai/project/known-risks.md` | — |

Each `TestReviewPass2` test failed with `state.py` from R4's tree_before (1c65ee0e1) swapped in, and passes after (54 passed).
