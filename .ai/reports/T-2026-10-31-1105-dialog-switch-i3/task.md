# T-2026-10-31-1105-dialog-switch-i3 — dialog switch: one rule for hooks and state.py; a session that cannot be bound fails closed for commit/push consent (1096 + 43ae-I3)

feature · guarded · started 2026-10-31T11:05:46Z · claude

## Weight

```
scope          2  docs/dialog-spike.md referenced from 11 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         1  "tightens the commit/push consent rule only; approve, policies and AI_UNATTENDED unchanged" (dec
novelty        0  "bugfix in existing code paths" (declared)
coverage       0  3 of 3 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T11:05:46Z — /rr-build-all ~/.claude/plans/dialog-cluster-decisions.md item 3 (1096 + 43ae-I3)

## Plan

files: docs/dialog-spike.md, hooks/guard/dialog.py, hooks/guard/git.py, skills/ai-task/state.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py
tests: tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py, tests/test_ai_task_state.py
- s1 · docs/dialog-spike.md · tests/test_dialog_contract.py · done
- s2 · hooks/guard/dialog.py, hooks/guard/git.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py · tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py · done
- s3 · skills/ai-task/state.py, tests/test_dialog_contract.py · tests/test_dialog_contract.py, tests/test_ai_task_state.py · done · after s2, s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 2d60d56c0 | .ai/state/logs/T-2026-10-31-1105-dialog-switch-i3/suite-1.log | no |
| 2 | suite | 0 | 2d60d56c0 | .ai/state/logs/T-2026-10-31-1105-dialog-switch-i3/suite-2.log | no |
| 3 | e2e | 0 | 2d60d56c0 | .ai/state/logs/T-2026-10-31-1105-dialog-switch-i3/e2e-3.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS

No BLOCKER and no HIGH. Off path and the main session with a live pick unchanged; effective_switch is True only for "on" (the old True set minus the env-mismatch case); callers hooks/dialog-gate.py:90, hooks/guard/decision.py:51, hooks/guard/paths.py:1307 treat closed as off. Suite taken from suite-2.log (1132 tests, OK, skipped=5).

- [LOW] L1 The closed-deny text contradicts itself (hooks/guard/git.py:268-270, WHY_CONSENT at git.py:30)  in_scope: yes
  why it matters: says "The human runs this command in their own terminal" then appends WHY_CONSENT, which tells the agent to open a decision, send the dialog and run the pick — a subagent cannot. Also says "a subagent, or no session to bind a pick to" while it also fires on a session-id mismatch. test_unbound_calls_are_refused checks only the prefix and "terminal".
  suggested direction: drop WHY_CONSENT from the closed branch or give it its own tail; name the mismatch case.
- [LOW] L2 The contract test does not cross the payload axis with the env axis (tests/test_dialog_contract.py:112-146)  in_scope: yes
  why it matters: not tautological, but has_session sets env id and payload id together; payload-id-without-env and env-without-payload, where the sides can diverge (hooks "on" for Codex payload; state.py None without the shell variable), are untested. Divergence fails safe (pick unbound → commit denied) but is undocumented.
  suggested direction: add the off-diagonal rows with the expected divergence, or narrow the docstring.
- [INFO] I1 The doc extrapolates the spike to hook events it did not record (docs/dialog-spike.md, row "The hook's own environment carries it")  in_scope: yes
  why it matters: recorded SessionStart, UserPromptSubmit, PreToolUse, Stop; PostToolUse (where dialog-gate.py records the pick) and Notification not recorded. A differing PostToolUse env id would silently drop the pick and lock the main session out. claude --resume correctly UNKNOWN; same lockout risk (terminal route still works).
  suggested direction: note PostToolUse as unrecorded in Open item 4, or record it next spike.
- [INFO] I2 An exception in consent now denies where it used to allow (hooks/guard/git.py:260-263)  in_scope: no
  why it matters: except Exception went from on=False (allow) to "closed" (deny). Reachable via RecursionError from a deeply nested dialog.json/profile.json (readers catch OSError, ValueError only); then a truly-off commit is denied. Matches "this one rule fails closed"; shape no session produces.
  suggested direction: accept, or catch RecursionError in the two readers.
- [INFO] I3 Codex subagent detection depends on agent_id only (hooks/guard/dialog.py:123-137)  in_scope: yes
  why it matters: Codex hooks carry no session env; fixtures tests/fixtures/codex-hooks/32-34 show agent_id on subagent Stop; on a subagent's PreToolUse not shown in the spike — an open fact, not a defect.
  suggested direction: record in the next Codex spike.

## EXAMINED AND CLEAN
Off path order of checks; non-commit tool calls; main session with live pick; deny reasons distinguishable; gate and ledger write nothing when closed; dialog_on vs switch_state comment-only; doc numbers (29+13=42); scope seven files, no weakened test. Not reached: raw spike recordings (outside repo); targeted tests not re-run.

VERDICT: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/dialog-spike.md | +28 −0 | Edit |
| hooks/guard/dialog.py | +35 −15 | Edit |
| hooks/guard/git.py | +7 −3 | Edit |
| skills/ai-task/state.py | +11 −6 | Edit |
| tests/test_dialog_consent.py | +50 −0 | Edit |
| tests/test_dialog_contract.py | +69 −0 | Edit |
| tests/test_dialog_gate.py | +47 −0 | Edit |

+247 −24 lines, 7 files

## Verdict

close: closed
facts: (a) green — suite green on 2d60d56c0 (run 2) · (b) green — 7 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
