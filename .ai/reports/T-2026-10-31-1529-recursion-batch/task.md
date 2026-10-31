# T-2026-10-31-1529-recursion-batch — RecursionError batch: the hooks' and state.py's remaining JSON readers take the malformed-JSON path; ledger and state.json pins (risks 7d54, 46a2, f714, 35d8)

bugfix · guarded · started 2026-10-31T15:29:55Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         1  "consent.jsonl reader of the git guard and the decision gate: a too-deep line now takes the torn
novelty        0  "same except-tuple pattern as T-2026-10-31-1414 and 1423" (declared)
coverage       0  5 of 5 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T15:29:55Z — /rr-build-all: close the risks of T-2026-10-31-1423 (7d54, 46a2, f714, 35d8) as one batch, no refactoring

## Plan

files: hooks/guard/dialog.py, hooks/dialog-gate.py, hooks/context-guard.py, hooks/runtime-gate.py, skills/ai-task/state.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
tests: tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_ai_task_state.py, tests/test_profile_detect.py
- s1 · hooks/guard/dialog.py, hooks/dialog-gate.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py · tests/test_dialog_contract.py, tests/test_dialog_gate.py · done
- s2 · hooks/context-guard.py, tests/test_context_guard.py · tests/test_context_guard.py · done
- s3 · hooks/runtime-gate.py, tests/test_runtime_gate.py · tests/test_runtime_gate.py · done
- s4 · skills/ai-task/state.py, tests/test_ai_task_state.py, tests/test_profile_detect.py · tests/test_ai_task_state.py, tests/test_profile_detect.py · done

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. R-reject-with-an-unreadable-decision-json-5580: with the dialog on and decision.json malformed or too deep, 'reject' writes rejected_at and then exits 1 'decision.json is unreadable' (close_gate/retire_approvals). This is a behaviour change, not part of this batch. Which way?
asked: 2026-10-31T15:30:02Z · stage: implementation · by: agent
context: state.py cmd_reject -> close_gate/retire_approvals -> read_decisions; found by T-2026-10-31-1423 s1
A. reject reads decision.json before writing rejected_at (separate task)
B. leave as is and accept the risk
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-31T15:49:43Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 1fba9e8c7 | .ai/state/logs/T-2026-10-31-1529-recursion-batch/suite-1.log | no |
| 2 | e2e | 0 | 1fba9e8c7 | .ai/state/logs/T-2026-10-31-1529-recursion-batch/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 tests/test_runtime_gate.py (test_17, "transcript and rollout lines" sub-test): the deep rollout case does not pin the rollout_limits catch in hooks/runtime-gate.py:567. bad_event = '"token_count" "rate_limits" ' + ("[" * 60000 ...) — json.loads parses the string "token_count" first and stops with JSONDecodeError: Extra data; the [ run is never reached. Delete RecursionError from rollout_limits and the test stays green. Fix direction: a nested object holding the markers, e.g. {"type":"token_count","rate_limits":[[[... at ~69000+ [, fitting the 64 KB tail or raising ROLLOUT_TAIL in the test.
- [MEDIUM] M2 tests/test_ai_task_state.py test_deep_state_files_read_as_malformed_ones: the session.json half is vacuous — decision show never calls read_session (detect_runtime state.py:272 is reached only when --runtime, AI_RUNTIME, install location and CLAUDECODE all give nothing; DialogBase sets CLAUDECODE=1 and AI_RUNTIME, :172/:93). Reverting the read_session catch (state.py:246) leaves the suite green (static finding). Fix direction: detect_runtime with runtime=None and a clean env (pattern at :1309) or call state_mod.read_session(root) directly; compare deep with malformed.
- [MEDIUM] M3 skills/ai-task/state.py:1025, :1874, :3211: a deep .ai/policies/weight.json is not handled like a malformed one — the three call weight.load_policy(root) (weight.py:47 bare json.load) and catch (OSError, ValueError) only; malformed gives die("cannot read the weight table") at :1025/:3211 and {} at :1874; deep gives a traceback. Policy file a human edits, not state. Fix direction: RecursionError in those three tuples plus one deep-weight.json test, or record as a risk.
- [LOW] L1 skills/ai-task/state.py:386: the catch in load() wraps apply_defaults(json.load(fh)), not only the parse; a real RecursionError in apply_defaults would read as "state.json is unreadable". Harmless today. Direction: none needed; strictly, parse first then apply defaults outside the try.
- [LOW] L2 tests/test_ai_task_state.py same test, consent.jsonl part: checked only for no Traceback, not compared with a malformed line; test_ledger_valid_deep_valid is the strong pin, so this part is redundant. Drop it or compare with a malformed line.
- [INFO] I1 the other ValueError-only sites (:990, :1056, :1212, :2440, :2481, :3595) are not file-fed JSON parses; only :1025, :1874, :3211 are (M3).

## EXAMINED AND CLEAN
Enumeration of every json.load/json.loads in the five code files; fail-open vs fail-closed parity per reader; catch width (only L1); 35d8 state left untouched; f714 pin test_ledger_valid_deep_valid breaks on either catch removed; tests pinning their own catch (context-guard readers, runtime-gate profile/load/import_legacy/claude_code_version/last_transcript_model/project_task, dialog-gate Stop tests, codex adapt_response, journal/sealed_task/quota/json_object/jwt/event --data/ask --batch/plan-file); no existing assertion edited; isolation; speed (1165 tests in 75.8s); hooks rules — no new deny, no weakened refusal. Out of scope: reject write ordering (Q1=A). Not reached: dynamic repro of M2/M3.

VERDICT: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/context-guard.py | +10 −10 | Edit |
| hooks/dialog-gate.py | +1 −1 | Edit |
| hooks/guard/dialog.py | +2 −2 | Edit |
| hooks/runtime-gate.py | +9 −9 | Edit |
| skills/ai-task/state.py | +8 −8 | Edit |
| tests/test_ai_task_state.py | +117 −1 | Edit |
| tests/test_context_guard.py | +97 −0 | Edit |
| tests/test_dialog_contract.py | +15 −0 | Edit |
| tests/test_dialog_gate.py | +37 −0 | Edit |
| tests/test_profile_detect.py | +35 −0 | Edit |
| tests/test_runtime_gate.py | +71 −0 | Edit |

+402 −31 lines, 11 files

## Verdict

close: closed
facts: (a) green — suite green on 1fba9e8c7 (run 1) · (b) green — 11 changed files, all in the task's files
gate: none
confirm: none
handoffs: 7 · suite runs: 1 · review passes: 1
