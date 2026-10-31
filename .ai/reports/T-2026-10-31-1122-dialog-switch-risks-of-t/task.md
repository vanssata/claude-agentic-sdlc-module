# T-2026-10-31-1122-dialog-switch-risks-of-t — dialog switch risks of T-2026-10-31-1105: one profile path, closed-deny text, nested-file readers, contract off-diagonals, spike open items, test env isolation

bugfix · guarded · started 2026-10-31T11:22:08Z · claude

## Weight

```
scope          2  hooks/guard/git.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         1  commit/push consent: reads one profile path (stricter side), no route loosened for a parseable f
novelty        0  bugfixes in existing code paths and test isolation (declared)
coverage       0  3 of 3 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T11:22:08Z — /rr-build-all ~/.claude/plans/dialog-switch-i3-risks.md (six risks of T-2026-10-31-1105)

## Plan

files: hooks/guard/git.py, hooks/guard/dialog.py, tests/test_dialog_consent.py, skills/ai-task/state.py, tests/test_dialog_contract.py, docs/dialog-spike.md, tests/test_profile_detect.py
tests: tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
- s1 · hooks/guard/git.py, hooks/guard/dialog.py, tests/test_dialog_consent.py · tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py · done
- s2 · skills/ai-task/state.py, tests/test_dialog_contract.py · tests/test_dialog_contract.py, tests/test_ai_task_state.py · done · after s1
- s3 · docs/dialog-spike.md · tests/test_dialog_contract.py · done · after s2
- s4 · tests/test_profile_detect.py · tests/test_profile_detect.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 9f1818b12 | .ai/state/logs/T-2026-10-31-1122-dialog-switch-risks-of-t/suite-1.log | no |
| 2 | e2e | 0 | 9f1818b12 | .ai/state/logs/T-2026-10-31-1122-dialog-switch-risks-of-t/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 Consent loosening is real but scored behaviour 1, not declared behaviour 2 (hooks/guard/dialog.py:81, hooks/guard/dialog.py:107, skills/ai-task/state.py:2359, skills/ai-task/state.py:2381; weight block task.md:5-13)  in_scope: yes
  why it matters: on HEAD a deeply nested dialog.json/profile.json made switch_state raise RecursionError, consent()'s except Exception set "closed" and denied; now the file reads "off" and consent() allows the commit/push. hooks/CLAUDE.md names "allows what was denied" behaviour 2 (declare it, start full). Pinned by test (HEAD's test_too_deeply_nested_json_reads_as_malformed gives deny, new code allow). The route is no wider than a garbage/truncated file, already "off" via ValueError, and a constructed file is outside the safety threat model.
  suggested direction: record the decision and its reason as an accepted behaviour-2 effect, or have a human confirm the "treat as malformed" choice.
- [LOW] L1 dialog_on docstring has an over-long spliced sentence (skills/ai-task/state.py:2388-2393)
  suggested direction: re-wrap as separate paragraphs.
- [LOW] L2 closed-deny text names three causes; "closed" also fires on a payload that is not an object (hooks/guard/git.py:273-275, hooks/guard/dialog.py:123-139)
  suggested direction: none needed, or add "an unreadable call".
- [INFO] I1 Recursion depth varies with stack depth, so the two readers can disagree on a file near the limit (hooks/guard/dialog.py:81, skills/ai-task/state.py:2359)  in_scope: no
- [INFO] I2 read_profile still does not catch RecursionError (skills/ai-task/state.py:529-535)  in_scope: yes — other callers unchanged, outside the consent path.

## EXAMINED AND CLEAN
dialog_tool_verified mirrors hooks' dialog_tool; dialog_on only loses the legacy fallback (stricter side); read_profile/profile_file unchanged. New contract tests red on a git-archive HEAD copy (legacy row; RecursionError on nested), green now. test_profile_detect red on HEAD with ATTENDED=0, green now. WHY_CONSENT_CLOSED has no decision/dialog instruction; consent test red on HEAD. Off-diagonal rows (a) on/None (b) closed/dict (c) closed/dict match the code; seen set in test_session_ids_that_differ unused. All four readers handle RecursionError alike; no parseable file reads differently. Doc Open 5 matches hooks/dialog-gate.py:86-93; Open 6 backed by fixtures 32-34 subagent-stop-*. Suite log 1135 OK (5 skipped); seven plan files only; no weakened test. Not reached: own_runtime vs payload_runtime divergence (pre-existing).

VERDICT: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/dialog-spike.md | +11 −2 | Edit |
| hooks/guard/dialog.py | +2 −2 | Edit |
| hooks/guard/git.py | +7 −3 | Edit |
| skills/ai-task/state.py | +23 −4 | Edit |
| tests/test_dialog_consent.py | +40 −0 | Edit |
| tests/test_dialog_contract.py | +64 −20 | Edit |
| tests/test_profile_detect.py | +1 −1 | Edit |

+148 −32 lines, 7 files

## Verdict

close: closed
facts: (a) green — suite green on 9f1818b12 (run 1) · (b) green — 7 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
