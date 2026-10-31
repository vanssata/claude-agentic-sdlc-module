# T-2026-10-30-2236-risk-burndown-b4-user — Risk burndown B4: user-facing messages name /rr-setup instead of /project-update and /ai-init (adopt.py, migration 0003, state.py status schema line)

bugfix · full · started 2026-10-30T22:36:49Z · claude

## Weight

```
scope          2  skills/project-update/adopt.py referenced from 80 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  2  skills/project-update/migrations/0003_context_diet.py matches needs_step **/migrations/**; hint 
domain         0  plugin tooling messages (declared)
novelty        0  the /rr-setup rename already done elsewhere (declared)
coverage       1  2 of 3 code files have a test
W 6 → full   hints reversibility +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T22:36:49Z — /loop risk burndown B4 (plan ~/.claude/plans/risk-burndown-loop-2026-10-31.md)

## Plan

files: skills/project-update/adopt.py, skills/project-update/migrations/0003_context_diet.py, tests/test_project_adopt.py, tests/test_project_update.py, skills/ai-task/state.py, tests/fixtures/memory/goldens/files-mode.txt, tests/fixtures/memory/goldens/status-py.txt, tests/test_memory_characterization.py, skills/rr-status/status.py, tests/test_ai_status_root.py
tests: tests/test_project_adopt.py, tests/test_project_update.py, tests/test_memory_characterization.py, tests/test_ai_task_state.py
- s1 · skills/project-update/adopt.py, skills/project-update/migrations/0003_context_diet.py, tests/test_project_adopt.py, tests/test_project_update.py · tests/test_project_adopt.py, tests/test_project_update.py · done
- s2 · skills/ai-task/state.py, tests/fixtures/memory/goldens/files-mode.txt, tests/fixtures/memory/goldens/status-py.txt, tests/test_memory_characterization.py · tests/test_memory_characterization.py, tests/test_ai_task_state.py · done
amended 2026-10-30T22:40:40Z: +skills/rr-status/status.py — R-...-6fc8: status.py:84 keeps its own schema_line copy with 'behind: run /project-update' (shown when no task is in flight); same golden status-py.txt line 4
amended 2026-10-30T22:47:02Z: +tests/test_ai_status_root.py — B4 review L2: pin the /rr-setup wording of status.py's no-.ai/ message

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-30-2236-risk-burndown-b4-user for implementation? (gate: human_approval)
asked: 2026-10-30T22:49:57Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-10-30T22:51:04Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 9074861d9 | .ai/state/logs/T-2026-10-30-2236-risk-burndown-b4-user/suite-1.log | no |
| 2 | e2e | 0 | 9074861d9 | .ai/state/logs/T-2026-10-30-2236-risk-burndown-b4-user/e2e-2.log | no |
| 3 | suite | 0 | 799058456 | .ai/state/logs/T-2026-10-30-2236-risk-burndown-b4-user/suite-3.log | no |
| 4 | e2e | 0 | 799058456 | .ai/state/logs/T-2026-10-30-2236-risk-burndown-b4-user/e2e-4.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M1 Renaming `REVIEW_LINE` breaks the clean-up rewrite of adopt reports written by earlier versions (`skills/project-update/adopt.py:1585`, used at `:1781`)  in_scope: yes
  why it matters: `cleanup_report_md` only removes the "please review" line from `report.md` if it is an exact match for the current `REVIEW_LINE`. Released versions v2.0.2 to v3.1.0 wrote ``Run `/project-update --adopt --cleanup` to review; a human confirms the deletion.`` (checked with `git show v3.1.0:` and `git show v2.0.2:`). A project adopted on any of those versions and cleaned up after upgrading to this one will still say "run ... to review; a human confirms the deletion" in its committed `report.md`, right above the new `## Cleanup` section that records the files as already deleted. That is the defect manual-check WP6 found (`.ai/reports/manual-check-wp6-adopt-2026-09-22/findings.md:160-162`), and the `.replace` at `:1781` was added to fix it. This change brings it back for every report written before the rename.
  suggested direction: keep the old text as a legacy constant and replace both the old and new lines in `cleanup_report_md`, with a test that seeds a `report.md` containing the old line and asserts it is rewritten.
- [LOW] L1 The only test of `REVIEW_LINE` is a negative check with nothing positive behind it, so the B4 edit to it proves nothing (`tests/test_project_adopt.py:1378`)  in_scope: yes
  why it matters: `assertFalse(any("Run `/rr-setup --adopt --cleanup` to review" in body(p) for p in glob(...)))` passes if the code and test strings disagree, if the line was never written, or if the glob finds nothing. No test checks that `report.md` contains `REVIEW_LINE` before clean-up or "The deletion is recorded under Cleanup below." after it. The negative check at `:1031` (`"run /rr-setup --adopt --apply again" not in out`) has the same problem: no version of `adopt.py` ever printed "apply again", so it can never fail.
  suggested direction: assert `adopt.REVIEW_LINE` is present before clean-up and the replacement sentence is present after it, plus `assertTrue(paths)` on the glob.
- [LOW] L2 The sweep missed an old name in a file B4 edited: `status.py` still prints "/ai-init sets one up" (`skills/rr-status/status.py:165`)  in_scope: yes
  why it matters: `state.py` already says "run /rr-setup first" for the same no-`.ai/` case (pinned at `tests/test_ai_task_state.py:2039`). `/rr-status` with no `.ai/` still sends users to the deprecated alias, so the two status tools now disagree.
  suggested direction: same wording as `state.py`'s message, pinned in `tests/test_ai_status_root.py`.
- [INFO] I1 Old command names still left outside B4's file list  in_scope: yes
  why it matters: these are user-facing and belong in a later burndown: `skills/ai-init/templates/.ai/AGENTS.md:61` (router row `/project-update`, shipped into every project); `skills/ai-task/state.py:1922` `RESUME_COMMAND` (`claude -p '/ai-task'`, pinned at `tests/test_ai_task_state.py:1913`); `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp6-adopt.md:424-426` and `wp3-context-diet.md:455` still quote the old message text. All the aliases still forward, so nothing breaks.
  suggested direction: put them on the risk register; do not widen B4.
- [INFO] I2 `/rr-setup --adopt --cleanup` and `/rr-setup --adopt --apply` are not arguments `rr-setup` declares  in_scope: yes
  why it matters: `skills/rr-setup/SKILL.md:4` has `argument-hint: ... --adopt [--mode coexist]`. The `--adopt` section never reads `--apply` or `--cleanup` from `$ARGUMENTS`; step 6 asks "apply?" and step 8 shows `$UPDATE --adopt --cleanup`. The agent still gets to the right step, and the old `/project-update` hint (`[--apply] [--adopt [--mode coexist]]`) had the same gap, so the rename keeps the old meaning and adds no new defect. `/rr-setup --update --apply` is handled (`SKILL.md:133`). The mapping is right: `/project-update` forwarded as `--update $ARGUMENTS`, so `/rr-setup --adopt` is more accurate than the alias was.
  suggested direction: optionally add `--cleanup` and `--apply` under `--adopt` in the `argument-hint`, or have the hints name the `update.py` flags; this is a separate change.

## EXAMINED AND CLEAN
- **Schema line.** No code parses the `/project-update` suffix. `schema_line` is only called inside `state.py` (`:4501`, `:4565`) and `status.py` (`:121`, `:152`). The tests match the prefix only (`tests/test_ai_status_root.py:116`, `:165`), and `skills/rr-status/SKILL.md:23` keys on `— behind`, which is unchanged. Both copies (`state.py:4585`, `status.py:84`) are byte-identical and match `update.py:2097` ("— run /rr-setup --update").
- **Golden files.** `files-mode.txt` and `status-py.txt` differ only on the four `schema:` lines, so the hand edits hide no other drift. Suite run 1 has 1096 tests OK with 5 skipped. e2e is OK. Both ran on tree `9074861d9`, per `events.jsonl`.
- **Migration 0003.** `ctx.hint` (`update.py:604`) only adds to an in-memory list, removing duplicates within one run. Nothing stores or compares the hint text, and no test or checksum covers the 0003 file text, so idempotency is unaffected. The new wording matches `update.py:1142` and `:1594` ("run /rr-setup --update again"). `tests/test_project_update.py:1332` matches only the prefix.
- **`state_line` suffixes** ("— run /rr-setup --adopt"). They are consumed only as printed hints (`update.py:2077`), and the tests match prefixes only ("foreign structure detected: cursor").
- **Mappings of the gate and clean-up hints:** `/ai-init` to `/rr-setup`, `/ai-task` to `/rr-build`, `/project-update --apply` to `/rr-setup --update --apply`. All are correct against the alias forwarders in `skills/{project-update,ai-init,ai-task}/SKILL.md`.
- **Scope.** All B4 hunks are inside the plan's file list, with `status.py` added by the recorded amendment. No refactoring or logic change is mixed in. The B1 and B2 hunks were not reviewed, as the brief asked.
- No ledger or `sensors.json` exists for this task, so there were no rows to inherit.
- Not reached (budget): none. About 22 calls were used, and nothing was run beyond reading the logs.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved plan and its recorded amendment (`status.py`). No BLOCKER or HIGH findings. M1 is a backward-compatibility regression for adopt reports written by v2.0.2 to v3.1.0 and should be fixed with a test that seeds the legacy line. L1 and L2 are a vacuous test and a missed old name in a file this task touched.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/ai-task/state.py | +1 −1 | Edit |
| skills/project-update/adopt.py | +18 −15 | Edit |
| skills/project-update/migrations/0003_context_diet.py | +1 −1 | Edit |
| skills/rr-status/status.py | +2 −2 | Edit |
| tests/fixtures/memory/goldens/files-mode.txt | +2 −2 | Edit |
| tests/fixtures/memory/goldens/status-py.txt | +2 −2 | Edit |
| tests/test_ai_status_root.py | +2 −0 | Edit |
| tests/test_project_adopt.py | +33 −3 | Edit |

+61 −26 lines, 8 files

## Verdict

close: closed
facts: (a) green — suite green on 799058456 (run 3) · (b) green — 8 changed files, all in the task's files
gate: requested G1 at 2026-10-30T22:49:57Z; approved by Ivan Kakurov at 2026-10-30T22:51:04Z via dialog
confirm: none
handoffs: 6 · suite runs: 2 · review passes: 1
