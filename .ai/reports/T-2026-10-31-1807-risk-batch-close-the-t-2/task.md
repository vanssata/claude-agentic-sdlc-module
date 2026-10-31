# T-2026-10-31-1807-risk-batch-close-the-t-2 — Risk batch: close the T-1529 review leftovers (RecursionError pins and readers, reject atomicity) and the dialog-background follow-ups (opt-in limited to non-SDK entrypoints, one AI_UNATTENDED rule, consent pin, duplicate-question refusal, spec)

bugfix · full · started 2026-10-31T18:07:55Z · claude

## Weight

```
scope          2  skills/ai-task/weight.py referenced from 131 files
behaviour      2  narrows background_sessions to non-SDK entrypoints and changes how AI_UNATTENDED=0 reads on the 
reversibility  0  git revert returns everything
domain         0  developer tooling, no money, identity or personal data (declared)
novelty        0  same except-tuple widening as T-1529; the opt-in and AI_UNATTENDED readers already exist (declar
coverage       1  7 of 8 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-31T18:07:55Z — skills/CLAUDE.md: behaviour 2 on the approval path (AI_UNATTENDED, background_sessions) runs full: STRONG review and the gate

## Plan

files: skills/ai-task/state.py, skills/ai-task/weight.py, hooks/guard/dialog.py, hooks/runtime-gate.py, hooks/context-guard.py, hooks/update_notice.py, hooks/guard/paths.py, skills/project-update/adopt.py, docs/hooks.md, docs/sdlc/specs/command-choice-dialog.md, tests/test_ai_task_state.py, tests/test_runtime_gate.py, tests/test_context_guard.py, tests/test_update_notice.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py, /home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1807.md
tests: tests/test_ai_task_state.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_update_notice.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py
- s1 · skills/ai-task/state.py, skills/ai-task/weight.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s2 · hooks/context-guard.py, hooks/guard/dialog.py, hooks/update_notice.py, hooks/runtime-gate.py, tests/test_context_guard.py, tests/test_dialog_contract.py, tests/test_dialog_gate.py, tests/test_update_notice.py, tests/test_runtime_gate.py · tests/test_context_guard.py, tests/test_dialog_gate.py, tests/test_update_notice.py, tests/test_runtime_gate.py · done · after s1
- s3 · hooks/guard/dialog.py, skills/ai-task/state.py, hooks/runtime-gate.py, hooks/guard/paths.py, skills/project-update/adopt.py, tests/test_dialog_contract.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py, tests/test_ai_task_state.py · tests/test_dialog_contract.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py, tests/test_project_adopt.py · done · after s2
- s4 · skills/ai-task/state.py, tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_task_state.py · tests/test_dialog_consent.py, tests/test_dialog_gate.py · done · after s3
- s5 · docs/sdlc/specs/command-choice-dialog.md, docs/hooks.md · no tests · done · after s4
amended 2026-10-31T18:31:09Z: +/home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1807.md — the STRONG review's report is ~6 KB; the Bash guard refuses it inline and state.py review --report needs a file

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-31-1807-risk-batch-close-the-t-2 for implementation? (gate: human_approval)
asked: 2026-10-31T18:31:47Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-31T18:34:44Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | f01964814 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-1.log | yes |
| 2 | step | 0 | 05b6db0a5 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-2.log | no |
| 3 | step | 1 | bf81452eb | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-3.log | yes |
| 4 | step | 0 | b2f9c2f7f | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-4.log | no |
| 5 | step | 1 | f5de58402 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-5.log | yes |
| 6 | step | 0 | 75a965e4d | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-6.log | no |
| 7 | step | 1 | ac78a531b | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-7.log | yes |
| 8 | step | 0 | d661ea2b1 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/step-8.log | no |
| 9 | suite | 0 | b0207ccb8 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/suite-9.log | no |
| 10 | e2e | 0 | b0207ccb8 | .ai/state/logs/T-2026-10-31-1807-risk-batch-close-the-t-2/e2e-10.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS

- [LOW] L1 The duplicate check only covers `decision open`, so afd2 is only partly closed (`skills/ai-task/state.py:3051-3058`; the other path is `cmd_ask` → `offer_decision` → `open_decision`, `state.py:1663-1671`, `state.py:2796-2807`)  in_scope: yes
  why it matters: `ask` opens a "question" decision with `item["question"]` (plus context) as its text and has no twin check. Two pending questions with the same text create two open decisions with one question text. This can happen when two subagents return the same `QUESTIONS_NEEDED` item through `ask --batch`, or when a question is asked again while it is still pending. Claude's `tool_response.answers` is keyed by question text, and `hooks/guard/dialog.py:329-331` reads both as unanswerable. That is exactly the failure afd2 describes. Nothing is lost, because the questions stay on the `[Answer]:` file route, but the dialog fails and the Stop hook nags up to `stop_blocks_max`. The new `docs/hooks.md` sentence presents the rule as a `decision open` rule only, so this gap is not visible from the docs.
  suggested direction: Either move the twin check into `open_decision`, where `offer_decision` already turns a refusal into "no dialog" and the file route, or record the `ask` path as the remaining part of afd2 in the register.

- [LOW] L2 The `DECISION_DUPLICATE` message gives advice that fails when the twin belongs to another session or runtime (`skills/ai-task/state.py:3053-3057`, compare `state.py:2999-3002`)  in_scope: yes
  why it matters: The twin search covers every open decision in the project. `decision show` only shows decisions bound to this session and runtime. A realistic case: session A opened a commit decision and nobody answered it, then the user starts a new `claude` (new session id) on the same tree with the same commands. Session B is refused with exit 6 and told to "send it ('state.py decision show')". That show prints "no open decision", leaving fallback on a decision that belongs to another session as the only way out. Before this change, B's new decision was appended last and worked. So this is a small usability regression for stale cross-session decisions; it is not a safety problem.
  suggested direction: When the twin is not bound to this session and runtime, say so and point straight to `decision fallback --id …`, or name the twin's session in the message.

- [INFO] I1 The refusal is unnecessary on Codex (`state.py:3051`, `hooks/guard/dialog.py:292-294`)  in_scope: yes
  why it matters: Codex questions carry the decision id, so two equal question texts can be told apart there. The refusal is harmless but blocks something that would work. No action needed beyond knowing it.

- [INFO] I2 `paths.py` decodes the environment differently from the other readers (`hooks/guard/paths.py:1271`, `hooks/guard/common.py:60-61,546-548`)  in_scope: no
  why it matters: `paths.py` reads through `env_b`, which decodes as latin-1. `dialog.py`, `runtime-gate.py`, `state.py` and `adopt.py` read `os.environ` (UTF-8 with surrogateescape). `.strip()` therefore treats a lone 0xA0 byte, a UTF-8 non-breaking space or 0x85 differently. Only a deliberately built value reaches this, and the outcome is safe either way: `state.py`'s own check still decides `approve`. Inside the boundary this would be LOW.

- [INFO] I3 The SDK carve-out depends on how Claude Code sets `CLAUDE_CODE_ENTRYPOINT`, which is unverified (`hooks/guard/dialog.py:137-139`, `state.py:2441-2444`)  in_scope: no
  why it matters: As far as I recall, Claude Code keeps an entrypoint value it inherits. If so, a `claude -p` started from inside a CLI session would carry `cli` with `ATTENDED=0`, and the opt-in would still keep the dialog on with nobody to answer it. The intended case does work: this background session itself shows `CLAUDE_CODE_ENTRYPOINT=cli`, `CLAUDE_CODE_SESSION_ATTENDED=0`, and this repository's `dialog.json` has `background_sessions: true`. Inside the boundary this would be LOW.

- [INFO] I4 For `sdk-*` runs with the opt-in, the dialog-on behaviour is replaced by today's "off" route (`docs/hooks.md:190-192`, `tests/test_dialog_consent.py:312-313`)  in_scope: yes
  why it matters: Under an SDK host with the opt-in, a commit no longer needs a live pick (the test expects `allow`, an empty ledger). This is what the human chose and matches SDK hosts without the opt-in. `docs/hooks.md` says why the opt-in does not cover SDK entrypoints, but not that commits then go back to needing no pick. One clause would make it explicit.

- [INFO] I5 Some readers outside this batch still catch only `OSError`/`ValueError` (`skills/project-update/adopt.py:183,463,955,1314,1339,1916`; `skills/project-update/update.py:218,635,708,787,1205,1219,1247`)  in_scope: yes
  why it matters: These JSON readers are the same class of issue as 0cad but were not in its list. They are for the risk register, not this task.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved plan's file list and the eleven named risks. It contains no refactoring beyond the per-copy `ai_unattended()` helpers that spec R15 requires.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/hooks.md | +10 −2 | Edit |
| docs/sdlc/specs/command-choice-dialog.md | +7 −2 | Edit |
| hooks/guard/dialog.py | +14 −4 | Edit |
| hooks/guard/paths.py | +2 −1 | Edit |
| hooks/runtime-gate.py | +11 −4 | Edit |
| hooks/update_notice.py | +3 −3 | Edit |
| skills/ai-task/state.py | +30 −10 | Edit |
| skills/project-update/adopt.py | +7 −1 | Edit |
| tests/test_ai_path_guard.py | +4 −0 | Edit |
| tests/test_ai_task_state.py | +79 −7 | Edit |
| tests/test_dialog_consent.py | +21 −0 | Edit |
| tests/test_dialog_contract.py | +47 −8 | Edit |
| tests/test_project_adopt.py | +3 −0 | Edit |
| tests/test_runtime_gate.py | +11 −2 | Edit |
| tests/test_update_notice.py | +28 −0 | Edit |

+277 −44 lines, 15 files

## Verdict

close: closed
facts: (a) green — suite green on b0207ccb8 (run 9) · (b) green — 15 changed files, all in the task's files
gate: requested G1 at 2026-10-31T18:31:47Z; approved by Ivan Kakurov at 2026-10-31T18:34:44Z via terminal
confirm: none
handoffs: 14 · suite runs: 1 · review passes: 1
