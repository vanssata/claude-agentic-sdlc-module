# T-2026-10-31-0028-state-py-profile-ack — state.py profile ack: terminal route to keep a drifted plan with the dialog off (32ee)

feature · guarded · started 2026-10-31T00:28:46Z · claude

## Weight

```
scope          2  tests/test_profile_detect.py referenced from 11 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         1  unknown (declared)
novelty        0  reuses human_route, profile_detect, write_drift_ack (declared)
coverage       0  2 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, tests/test_profile_detect.py, hooks/context-guard.py, tests/test_context_guard.py, docs/hooks.md, docs/sdlc/specs/command-choice-dialog.md
tests: tests/test_profile_detect.py, tests/test_context_guard.py
- s1 · skills/ai-task/state.py, tests/test_profile_detect.py · tests/test_profile_detect.py · done
- s2 · hooks/context-guard.py, tests/test_context_guard.py · tests/test_context_guard.py · done · after s1
- s3 · docs/hooks.md, docs/sdlc/specs/command-choice-dialog.md · no tests · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 37904b759 | .ai/state/logs/T-2026-10-31-0028-state-py-profile-ack/step-1.log | no |
| 2 | step | 0 | 636cf0261 | .ai/state/logs/T-2026-10-31-0028-state-py-profile-ack/step-2.log | no |
| 3 | suite | 0 | db067d0f4 | .ai/state/logs/T-2026-10-31-0028-state-py-profile-ack/suite-3.log | no |
| 4 | e2e | 0 | db067d0f4 | .ai/state/logs/T-2026-10-31-0028-state-py-profile-ack/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 No test runs `profile ack` for codex (`tests/test_profile_detect.py`, class ProfileAck: every case is `--runtime claude`). The code is runtime-generic: `write_drift_ack(runtime, …)` and `drift_ack_path(runtime)` go through `runtime_home(runtime)`, which uses CODEX_HOME. The detect `ack` string for codex is pinned only by the `check_cases` endswith assertion. A codex ack write, its `acknowledged` round-trip and the claude/codex entry independence in drift-ack.json are untested. The `unsupported` status exit 1 is also untested; the `status != "drift"` branch covers it by construction. in_scope: yes
  why it matters: a regression in the codex path (a wrong home, or `data[runtime]` clobbering the other runtime's entry) would pass the suite.
  suggested direction: add one codex drift-then-ack case that asserts the claude entry is untouched.

- [LOW] L2 The Bash path guard does not cover `profile ack` (`hooks/guard/paths.py:91`, PROFILE_SET_RE, `hooks/guard/paths.py:1370`). With the dialog on, `profile set` from an agent session is denied by the guard before it reaches `state.py`. `profile ack` is not, so the only barrier is `human_route()` inside `state.py` (exit 5 when an agent marker is set, `test_ack_refused_in_agent`). This matches `profile set` with the dialog off, and the human decided there is no dialog route, so it is consistent. `human_route` checks AI_UNATTENDED before the markers, so an unattended run inside an agent session can ack. The brief says the human decided that. The agent cannot set AI_UNATTENDED inline: the guard reads it from the hook's own environment (`paths.py:1270`). in_scope: yes
  why it matters: the worst case is an agent silencing a plan-drift notice for one account fingerprint, and `drift-ack.json` is deletable. The ack is bound to the exact fingerprint and installed plan (`acknowledged()`).
  suggested direction: no change needed; note the asymmetry in the guard comment at `paths.py:84` if you want it recorded.

- [INFO] I1 An open plan_drift decision stays open after a terminal ack until the next `detect --open` settles it as stale (`open_drift`, `state.py:857-860`). The docstring says so. With status `acknowledged`, `detect_drift` returns None, so the context-guard injects no notice and no stale DIALOG_PENDING reaches the model. A late dialog pick of Keep would only rewrite the same ack entry. in_scope: yes (no action)

- [INFO] I2 In-scope check of the weight rule in `skills/CLAUDE.md`: adding a human-only verb whose route includes AI_UNATTENDED touches the approval-path family. The brief says the human decided AI_UNATTENDED may ack, same as `profile set`. It writes only a per-user silence marker and does not move an approval, so I found nothing to flag. in_scope: no

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the plan: six files, additive field, one new verb on the existing human route, dialog-on behaviour unchanged. The decisions the human closed (no dialog route, AI_UNATTENDED may ack) are implemented as stated and not re-litigated.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/hooks.md | +2 −1 | Edit |
| docs/sdlc/specs/command-choice-dialog.md | +4 −3 | Edit |
| hooks/context-guard.py | +4 −1 | Edit |
| skills/ai-task/state.py | +37 −4 | Edit |
| tests/test_context_guard.py | +11 −0 | Edit |
| tests/test_profile_detect.py | +86 −0 | Edit |

+144 −9 lines, 6 files

## Verdict

close: closed
facts: (a) green — suite green on db067d0f4 (run 3) · (b) green — 6 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
