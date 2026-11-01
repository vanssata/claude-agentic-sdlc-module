# T-2026-11-01-2022-open-decision-checks-the — open_decision checks the twin before DECISION_LIMIT; record_migration and three_way's policy leaf read RecursionError as malformed (review L1+L2 of T-2026-10-31-2046)

bugfix · guarded · started 2026-11-01T20:22:41Z · claude

## Weight

```
scope          2  tests/test_ai_task_state.py referenced from 55 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  plugin tooling, no auth/data/payments (declared)
novelty        0  reorder of an existing block and widening two except clauses (declared)
coverage       0  2 of 2 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_ai_task_state.py, tests/test_project_update.py, skills/ai-task/state.py, skills/project-update/update.py, CHANGELOG.md, tests/test_memory_risks.py
tests: tests/test_ai_task_state.py, tests/test_project_update.py
- s1 · tests/test_ai_task_state.py, tests/test_project_update.py · tests/test_ai_task_state.py, tests/test_project_update.py · done
- s2 · skills/ai-task/state.py, skills/project-update/update.py, CHANGELOG.md · tests/test_ai_task_state.py, tests/test_project_update.py, tests/test_dialog_gate.py · done · after s1
amended 2026-11-01T20:31:40Z: +tests/test_memory_risks.py — Q1=A: the >10 floor counts this repo's live open risks; closing 4f78/9085 leaves 10 — lower it to a non-vacuity bound

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. test_memory_risks asserts this repo's live risk record has >10 open risks; closing 4f78 and 9085 (+ adding L1 b4c0) leaves exactly 10, so the suite is red. How to proceed?
asked: 2026-11-01T20:30:28Z · stage: implementation
context: tests/test_memory_risks.py:32
A. amend tests/test_memory_risks.py into the task and lower the floor to a non-vacuity bound (assertGreater(len(risks), 0)) — the check only proves the parser is not vacuous (recommended)
B. keep both risks open until a separate task fixes the test; close the task without the risk closes
C. leave it to you — you change the test or the record outside the agent
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-11-01T20:31:38Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 1a9ce9c3a | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/step-1.log | yes |
| 2 | step | 0 | dd1e5c0b8 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/step-2.log | no |
| 3 | suite | 0 | dd1e5c0b8 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/suite-3.log | no |
| 4 | e2e | 0 | dd1e5c0b8 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/e2e-4.log | no |
| 5 | suite | 1 | 50b3fa8f9 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/suite-5.log | no |
| 6 | suite | 0 | f0a29c046 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/suite-6.log | no |
| 7 | e2e | 0 | f0a29c046 | .ai/state/logs/T-2026-11-01-2022-open-decision-checks-the/e2e-7.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 The second new project-update test builds its fixture with `json.dumps` of a 3000-deep dict, and that probably fails on Python 3.11 (`tests/test_project_update.py`, `DEEP_POLICY_LEAF`, the `range(3000)` loop followed by `json.dumps(deep)`)  in_scope: yes
  why it matters: `.github/workflows/tests.yml` runs on Python 3.11, 3.12 and 3.13. The test passed here on 3.14 only. On 3.11 the C encoder counts against the 1000-frame recursion limit, so `json.dumps(deep)` should raise RecursionError in the test's own setup subprocess. That prints a Traceback, and the test fails for a reason unrelated to the fix. 3.12 may behave the same, depending on its C recursion limit. Only 3.14 was available, so I could not run this. The sibling tests all build deep JSON as a string (`"[" * 200000 + "]" * 200000`), which does not have this problem.
  suggested direction: build `ours` as a string, for example `'{"k":' * N + '{}' + '}' * N`. Then the only recursion in play is the parser's and `flatten`'s.

- [LOW] L1 `record_migration` now silently replaces a too-deep `migration.json` with a fresh record (`skills/project-update/update.py:1782-1788`)  in_scope: yes
  why it matters: Before, a too-deep record made `--apply` crash with a Traceback. Now the `ops` and `deletions` of the earlier aborted run are dropped and the file is overwritten, with no warning to the user. This is identical to how a malformed record (ValueError) already behaved, so it is consistent, and only a hand-made file can be that deep, because the tool's own output is never deep. The test does not assert `from`/`to`, only that `ops` and `deletions` are empty.
  suggested direction: accept as is, or print one line saying the previous record was unreadable.

- [INFO] I1 A twin with invalid options or labels now says DECISION_DUPLICATE instead of CONSENT_LABEL_INVALID or "2 to 4 options"  in_scope: yes
  why it matters: This is the trade-off you accepted. I found no caller that depends on the old order, and the message is accurate: the twin is open either way. Exit code is 6 and nothing is written. `docs/hooks.md:201` already documents the duplicate refusal and does not mention an order.

## VERDICT
verdict: pass_with_findings
scope_assessment: Inside the plan. The reorder in `open_decision` and the two catch clauses in `update.py` are minimal, and the messages are unchanged. M1 is a test-portability fix and does not change the product code.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +1 −0 | Edit |
| skills/ai-task/state.py | +16 −15 | Edit |
| skills/project-update/update.py | +2 −2 | Edit |
| tests/test_ai_task_state.py | +14 −0 | Edit |
| tests/test_memory_risks.py | +2 −1 | Edit |
| tests/test_project_update.py | +51 −0 | Edit |

+86 −18 lines, 6 files

## Verdict

close: closed
facts: (a) green — suite green on f0a29c046 (run 6) · (b) green — 6 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 3 · review passes: 1
