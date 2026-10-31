# T-2026-10-31-1650-dialog-background — dialog.json background_sessions: true keeps the dialog switch on when Claude Code marks the session unattended (CLAUDE_CODE_SESSION_ATTENDED=0, a background job with a live user); AI_UNATTENDED=1, subagents and session binding stay as they are; default off

feature · full · started 2026-10-31T16:50:19Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      2  "changes the approval path: the commit consent dialog opens in sessions Claude Code marks unatte
reversibility  0  git revert returns everything
domain         0  "developer tooling, no money or identity or personal data" (declared)
novelty        0  "the switch already reads dialog.json keys (window_seconds); one more key on the same readers" (
coverage       0  2 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-31T16:50:19Z — the user asked for a per-project setting; this project runs Claude Code background jobs with the human chatting live, where the dialog is off today

## Plan

files: hooks/guard/dialog.py, skills/ai-task/state.py, tests/test_dialog_contract.py, docs/hooks.md, /home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1650.md
tests: tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_dialog_consent.py
amended 2026-10-31T16:58:24Z: +/home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1650.md — the STRONG review's report is 8 KB; the Bash guard refuses it inline and asks for a file to pass to state.py review --report

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-31-1650-dialog-background for implementation? (gate: human_approval)
asked: 2026-10-31T17:13:16Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-31T17:14:08Z

## G2. Approve T-2026-10-31-1650-dialog-background for implementation? (gate: human_approval)
asked: 2026-10-31T17:40:04Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-31T17:41:06Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 84605ba1f | .ai/state/logs/T-2026-10-31-1650-dialog-background/step-1.log | yes |
| 2 | step | 1 | a08fea8ea | .ai/state/logs/T-2026-10-31-1650-dialog-background/step-2.log | no |
| 3 | step | 0 | 78baa914a | .ai/state/logs/T-2026-10-31-1650-dialog-background/step-3.log | no |
| 4 | suite | 0 | 3aee0f803 | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-4.log | no |
| 5 | e2e | 0 | 3aee0f803 | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-5.log | no |
| 6 | suite | 0 | 313cc2e0d | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-6.log | no |
| 7 | e2e | 0 | 313cc2e0d | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-7.log | no |
| 8 | suite | 1 | 313cc2e0d | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-8.log | no |
| 9 | suite | 0 | 313cc2e0d | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-9.log | no |
| 10 | e2e | 0 | 313cc2e0d | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-10.log | no |
| 11 | suite | 0 | fe72038ea | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-11.log | no |
| 12 | e2e | 0 | fe72038ea | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-12.log | no |
| 13 | suite | 0 | - | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-13.log | no |
| 14 | e2e | 0 | a2c023eea | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-14.log | no |
| 15 | suite | 0 | e6b928008 | .ai/state/logs/T-2026-10-31-1650-dialog-background/suite-15.log | no |
| 16 | e2e | 0 | e6b928008 | .ai/state/logs/T-2026-10-31-1650-dialog-background/e2e-16.log | no |

suite passing · e2e passing · suite runs 7

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS

- [HIGH] H1 The new test's subagent subcase depends on the reviewer's own home directory (`tests/test_dialog_contract.py:260-267`)  in_scope: yes
  why it matters: `root, _home = self.build(...)` throws away the scratch home, and neither `CLAUDE_CONFIG_DIR` nor `CODEX_HOME` is set. So `dialog.switch_state()` reads the real `~/.claude/riskrails/profile.json` and `~/.codex/riskrails/profile.json`. On this machine both name the verified tool (AskUserQuestion and request_user_input), so the test passes. Without them `dialog_tool()` returns None, the state is "off" instead of "closed", and the test fails. I reproduced this: `CLAUDE_CONFIG_DIR=/nonexistent-rr-review CODEX_HOME=/nonexistent-rr-review python3 -I tests/run_suite.py tests/test_dialog_contract.py` gives FAILED (failures=2), `'off' != 'closed' : a subagent stays closed under the opt-in`, for claude and codex. `test_dialog_gate.py` and `test_dialog_consent.py` stay green under the same environment (83 tests OK), so this task introduced the dependency. CI runners have no installed profile. Both the nightly or on-demand `full` job (`.github/workflows/tests.yml:73`) and the release job (`.github/workflows/npm-publish.yml:58`) run this file, so the release gate goes red. The "suite green" evidence (suite-4.log) only holds on a machine with RiskRails installed.
  suggested direction: run the subagent subcase inside the scratch home, with the same env and CLEAR handling as `check()`, or fold it into `check()` with an agent_id payload.

- [MEDIUM] M1 The opt-in also covers `claude -p` and the SDK, where the spike shows the dialog tool is absent (`hooks/guard/dialog.py:121-129`, `skills/ai-task/state.py:2429-2432`, `docs/dialog-spike.md:87-89`)  in_scope: yes
  why it matters: in an opted-in project, a `-p`/CI run is now "on". `offer_decision()` (`state.py:2784-2795`) prints dialog JSON instead of the terminal text. The decision gate then denies every tool of that session while the decision is open (`hooks/guard/decision.py:1-20, :106`). AskUserQuestion answers "No such tool" and no hook fires, so `unanswered_offer`/`fall_back` never triggers. The Stop hook blocks up to `stop_blocks_max` times. It does not hang: the clamp is ≤2, and `decision fallback` stays allowed. But a headless run spends turns and only gets out if the model runs the fallback itself. `docs/hooks.md:188-192` mentions the Stop hook but not the decision-gate denials. In an SDK host that answers AskUserQuestion programmatically, an answer from code is recorded as a human pick for commits and approvals. Before this change, the attended marker always ruled that out. The two cases can be told apart: the spike records `CLAUDE_CODE_ENTRYPOINT=sdk-cli` in print mode, and this review's own environment (a background job with the human live) has `CLAUDE_CODE_SESSION_ATTENDED=0` with `CLAUDE_CODE_ENTRYPOINT=cli`.
  suggested direction: limit the opt-in to non-SDK entrypoints, so `sdk-*` stays off, in both copies with a contract-matrix axis; or, if the human wants `-p`/SDK covered, say in docs/hooks.md that the opt-in trusts whatever answers the dialog there.

- [MEDIUM] M2 The feature rests on an unverified premise. No spike fixture captures a background session (`ATTENDED=0`, `ENTRYPOINT=cli`) (`tests/fixtures/dialog/claude/`, `docs/dialog-spike.md`)  in_scope: yes
  why it matters: the opt-in assumes three things in such sessions: AskUserQuestion is a real tool there, PostToolUse fires with the human's `tool_response`, and the hook payload's `session_id` equals `CLAUDE_CODE_SESSION_ID` in the hook environment. The spike checked the last one only for print mode. Background sessions also carry `CLAUDE_CODE_CHILD_SESSION` and `CLAUDE_CODE_BRIDGE_SESSION_ID`, which I saw in this environment. If the ids differ, the hooks are "closed" while `dialog_on()` returns a dict. state.py then opens decisions and prints dialog JSON, the recorder writes nothing, and every commit gets the closed CONSENT_REQUIRED. That fails closed but is worse than today's terminal route. If the tool is absent, M1 applies. The contract tests only prove that the two copies agree with each other, not that the runtime behaves this way.
  suggested direction: record one background-session spike (ask-single, posttooluse, stop payloads plus hook env) under `tests/fixtures/dialog/claude/` before relying on the opt-in, and pin the session-id equality.

- [LOW] L1 Nothing pins the stricter git path end to end (`tests/test_dialog_consent.py:137, :298`)  in_scope: yes
  why it matters: your probe is right as code: `git.py:250-290` goes through `switch_state`, so with the opt-in an `ATTENDED=0` commit needs a live pick. But the consent tests run with `CLAUDE_CODE_SESSION_ATTENDED=1`, and the only `=0` case is a subagent. If someone later bypasses `unattended()` in `consent()`, no test would catch it.
  suggested direction: add one ai-guard consent case with `ATTENDED=0` and the opt-in: a commit with no pick is denied, and a commit with the live pick is allowed.

- [LOW] L2 `tests/test_dialog_gate.py:384-387` was edited, but the plan's `files:` line lists only dialog.py, state.py, test_dialog_contract.py and docs/hooks.md; test_dialog_gate.py appears only under `tests:` (`.ai/reports/T-2026-10-31-1650-dialog-background/task.md` §Plan)  in_scope: yes
  why it matters: the edit is correct and needed, since the return shape changed. But it goes beyond the step's file list, which the project rules say should be refused with SCOPE_CHANGE_REQUIRED.
  suggested direction: record the file in the plan (a scope change) rather than leave it implicit.

- [LOW] L3 The spec does not mention the key. `docs/sdlc/specs/command-choice-dialog.md:54` (R36.1, the effective switch) and `:289` (the dialog.json schema) still describe the switch without `background_sessions`, and R36.1 does not name `CLAUDE_CODE_SESSION_ATTENDED` at all  in_scope: yes
  why it matters: the spec and the code now describe different switches on the approval path.
  suggested direction: amend R36.1 and the schema line in a follow-up; that file is outside this plan.

- [INFO] I1 `hooks/runtime-gate.py:988-992` does not honour the opt-in, and I think that is right  in_scope: yes
  why it matters: the key is named and documented for the command-choice dialog. runtime-gate's "ask" is a permission prompt, and nobody has verified it works in background sessions either. Not honouring the opt-in means allow-and-explain for an over-budget EXPERT launch, never a deny or a hang. Honouring it could leave an ask pending with nobody to answer it. The cost is that an opted-in background session still skips the EXPERT-budget ask.
  suggested direction: one sentence in docs/hooks.md that the opt-in is about the dialog only and the runtime gate still treats `ATTENDED=0` as unattended.

- [INFO] I2 Existing behaviour, not from this task: the dialog copies treat any non-empty `AI_UNATTENDED` as unattended (`dialog.py:127`, `state.py:2427`), while runtime-gate needs `== "1"` (`runtime-gate.py:992`). So `AI_UNATTENDED=0` turns the dialog off but not the runtime gate  in_scope: yes
  why it matters: two readers of the same variable disagree. The direction is fail-safe for the dialog. Recorded for the risk register, not for this task's remediation.
  suggested direction: one parsing rule for `AI_UNATTENDED` across hooks, in a separate task.

## VERDICT
verdict: pass_with_findings
scope_assessment: the task's hunks stay within dialog.py, state.py, test_dialog_contract.py and docs/hooks.md, except the needed edit to test_dialog_gate.py, which is not in the plan's `files:` line (L2). No refactoring is mixed in. The RecursionError hunks in these files belong to earlier uncommitted tasks and I read them only as context. H1 is a test defect that turns the release suite red on CI. M1 and M2 concern how far the opt-in reaches and whether its runtime premise holds, and both fail closed rather than open.
```

### Pass 2 — STRONG, pass

```
## FINDINGS

Scope: I reviewed only the human's edits to `.ai/policies/dialog.json` and `.ai/policies/weight.json`. I did not look at the `background_sessions` change again; it was already reviewed and its H1 is closed. To check the values I ran the real readers once against this tree:
- `hooks/guard/dialog.py` `dialog_policy` returned `{'window_seconds': 240, 'stop_blocks_max': 2, 'background_sessions': True}`.
- `state.py` `dialog_policy` returned `{'window_seconds': 240, 'background_sessions': True}`.
- `batch_policy(strict=True)` returned the new batch values with no refusal.
- `budget()` returned `(2, review_rounds_max)` and `(5, tests.max_suite_runs)` with batch off, and `(5, batch.review_rounds_max)` and `(12, batch.max_suite_runs)` with batch on.
- `sensors.tests_config` returned the new `tests` section.

- [LOW] L1 `stop_blocks_max: 4` silently acts as 2 (`.ai/policies/dialog.json:1`, `hooks/guard/dialog.py:31,117`)  in_scope: yes
  why it matters: `bounded("stop_blocks_max", 2, 0, STOP_BLOCKS_MAX=2)` clamps the value to at most 2 and gives no warning. `hooks/dialog-gate.py:59-63` therefore still ends the turn after 2 Stop blocks. The file says 4, but what runs is 2. `docs/hooks.md:180` does say "(default and maximum 2)", so this is documented, but nothing tells the person who edits the file. The earlier review's M1 counted on this cap of 2 to keep a headless opted-in run from looping, so raising the cap in code would be a behaviour change and not a fix for this value.
  suggested direction: the human either sets the value back to 2, so the file says what runs, or accepts it as written knowing it means 2. Do not raise the code cap to match.

- [LOW] L2 `tests.env_retries: 2` does nothing, because nothing reads the key (`.ai/policies/weight.json:189`)  in_scope: yes
  why it matters: `grep env_retries` finds no reader in `skills/ai-task/state.py`, `sensors.py` or `hooks/`. Its only code mention is migration 0007's `TEST_KEYS`, which copies keys and does not use them. Raising it from 1 to 2 changes no behaviour. A human who expects the suite to retry twice on an environment failure will not get that, and was not getting the one retry before either.
  suggested direction: note that the key is unread, in the risk register or the weight docs. No edit to the policy is needed.

- [LOW] L3 `.ai/policies/weight.md` is now stale and needs `state.py weight --mirror` (`.ai/policies/weight.md:3,32`)  in_scope: yes
  why it matters: line 3 records sha256 `3657d23a…`, which is `HEAD:.ai/policies/weight.json`. The file on disk now hashes to `58ee80ef…`. Line 32 still says `tests {"max_suite_runs": 2, "timeout_seconds": 1800, "env_retries": 1, …} · batch {… "review_rounds_max": 3, "max_suite_runs": 8, "parallel": 3 …}`. `.ai/AGENTS.md:49` tells agents that weight.md mirrors the JSON, so an agent that reads it will report the old budgets. Enforcement is not affected, because `state.py` reads the JSON. On the next `/rr-setup --update`, `update.py:906-924` will not re-render the mirror. It falls back to a three-way text merge and prints the stale-mirror hint.
  suggested direction: the human runs `state.py weight --mirror` (from the repo root, which writes `.ai/policies/weight.md`) as part of committing the policy edit. Only the project mirror needs it: `test_mirror_fresh` (`tests/test_weight.py:363-370`) checks the shipped template, which did not change.

- [INFO] I1 `tests.max_suite_runs` went from 2 to 5 during this task, after two over-budget runs had been approved (`.ai/policies/weight.json:187`, `.ai/reports/T-2026-10-31-1650-dialog-background/events.jsonl:25,26,29`)  in_scope: yes
  why it matters: the journal shows `human_set` for suite runs 3 and 4 past the budget. weight.json was edited at 19:08 and suite-11 ran at 19:10 with no `human_set`. `state.json` now has `suite_runs: 5`, which is exactly the new limit, so the next suite run will ask again. The human owns this change and is allowed to make it, but it changes the budget for every task in the project, not just this one. The task record should say it was a decision, so it does not read as a budget relaxed to get one task through.
  suggested direction: record the reason in the task's decisions, or in the commit message.

- [INFO] I2 `tests.timeout_seconds: 3600` makes no practical difference here (`.ai/policies/weight.json:188`, `skills/ai-task/state.py:3899`, `skills/ai-task/sensors.py:414`)  in_scope: yes
  why it matters: the value is valid and is passed straight through as the subprocess timeout. The suite takes about 81 s (`suite-11.log`: "Ran 1166 tests in 80.990s"). A foreground Bash call stops at 600 s anyway, which was already true with 1800. So the raise only matters for a verify run in the background. Values that do work: `window_seconds` 240 is inside 30–600 in both readers, which agree, and only `dialog.py:627` uses it, to set a pick's `expires_at`. `batch.parallel` 5 with tier BALANCED passes the `parallel >= 3` check in `state.py:3282`, and BALANCED maps to sonnet in the installed profile, so the rule that 5 or more parallel agents never run on opus holds.

- [INFO] I3 This repository is now opted in to `background_sessions`, so the earlier review's M1 and M2 apply to its own sessions (`.ai/policies/dialog.json:1`)  in_scope: yes
  why it matters: background, `-p` and SDK sessions in this repo now get the dialog instead of the terminal route. M1 is the `-p`/SDK reach of the opt-in; M2 is that no spike fixture has ever recorded a background session. Both fail closed and are already on record; turning the opt-in on here just makes them live for this project.

## VERDICT
verdict: pass
scope_assessment: the review covered only the two human-owned policy edits. All values parse and are within what their readers accept. Two values do not do what they say: `stop_blocks_max` 4 runs as 2 (L1), and `env_retries` is never read (L2). The project's `weight.md` mirror is stale (L3); the human should run `state.py weight --mirror`. Nothing is in_scope above LOW, and I edited nothing.
```

### Pass 3 — STRONG, pass by Ivan Kakurov

no FINDINGS block

### Pass 4 — STRONG, pass by Ivan Kakurov

no FINDINGS block

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/policies/dialog.json | +1 −1 | Edit |
| .ai/policies/weight.json | +6 −6 | Edit |
| .ai/policies/weight.md | +2 −2 | Edit |
| docs/hooks.md | +5 −1 | Edit |
| docs/sdlc/intent/small-oop-modules.questions.md | +50 −0 | Edit |
| docs/sdlc/specs/small-oop-modules.md | +153 −36 | Edit |
| hooks/guard/dialog.py | +15 −4 | Edit |
| skills/ai-task/state.py | +7 −2 | Edit |
| tests/test_dialog_contract.py | +41 −1 | Edit |
| tests/test_dialog_gate.py | +3 −1 | Edit |

+283 −54 lines, 10 files

## Verdict

close: closed
facts: (a) green — suite green on e6b928008 (run 15) · (b) RED — outside the task's files: .ai/policies/dialog.json, .ai/policies/weight.json, .ai/policies/weight.md, docs/sdlc/intent/small-oop-modules.questions.md, docs/sdlc/specs/small-oop-modules.md
gate: requested G2 at 2026-10-31T17:40:04Z; approved by Ivan Kakurov at 2026-10-31T17:41:06Z via terminal
confirm: none
handoffs: 22 · suite runs: 7 · review passes: 2
