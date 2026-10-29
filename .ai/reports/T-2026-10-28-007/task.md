# T-2026-10-28-007 — Fix L3 (status_line comments lost in merge-codex-config.py) and L4 (profile set drops economy context; installer_command drops --context economy)

bugfix · guarded · started 2026-10-28T16:39:58Z · claude

## Weight

```
scope          2  tests/test_profile_detect.py referenced from 6 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  plugin config/profile files; no auth, secrets, data or payments (declared)
novelty        0  follows existing resolver/context and status_items patterns from 14974cc (declared)
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, tests/test_profile_detect.py, scripts/merge-codex-config.py, tests/test_codex_install.py, .ai/project/known-risks.md
tests: tests/test_profile_detect.py, tests/test_codex_install.py
- s1 · skills/ai-task/state.py, tests/test_profile_detect.py · tests/test_profile_detect.py · done
- s2 · scripts/merge-codex-config.py, tests/test_codex_install.py · tests/test_codex_install.py · done
- s3 · .ai/project/known-risks.md · no tests · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 8e9cf81f4 | .ai/state/logs/T-2026-10-28-007/step-1.log | yes |
| 2 | step | 0 | 93d58823e | .ai/state/logs/T-2026-10-28-007/step-2.log | no |
| 3 | step | 1 | 6cc5d6384 | .ai/state/logs/T-2026-10-28-007/step-3.log | yes |
| 4 | step | 1 | 118aab17d | .ai/state/logs/T-2026-10-28-007/step-4.log | no |
| 5 | step | 0 | d042ded42 | .ai/state/logs/T-2026-10-28-007/step-5.log | no |
| 6 | suite | 0 | 8bbdeeab0 | .ai/state/logs/T-2026-10-28-007/suite-6.log | no |
| 7 | e2e | 0 | 8bbdeeab0 | .ai/state/logs/T-2026-10-28-007/e2e-7.log | no |
| 8 | step | 1 | dcbffdbba | .ai/state/logs/T-2026-10-28-007/step-8.log | yes |
| 9 | step | 1 | 1a3f51821 | .ai/state/logs/T-2026-10-28-007/step-9.log | yes |
| 10 | suite | 0 | 0dcba89e7 | .ai/state/logs/T-2026-10-28-007/suite-10.log | no |
| 11 | e2e | 0 | 0dcba89e7 | .ai/state/logs/T-2026-10-28-007/e2e-11.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 skills/ai-task/state.py:722 — `context_mode()` assumes `prof["context"]` is a dict. For a hand-edited `profile.json` with `"context": "economy"` (or a list) it raises AttributeError. I ran it: `context_mode({'context':'economy'})` gives `'str' object has no attribute 'get'`. `profile_detect` and `cmd_profile_set` both call it, so both now crash with a traceback on a record they handled before this change. The installer always writes a dict, and the file is not a normal input. Fix direction: `isinstance(..., dict)` guard. — in_scope: yes
- [INFO] I1 skills/ai-task/state.py:832-836 — `except (OSError, ValueError)` does not catch the TypeError an older resolver raises for `context=`. The comment's premise holds (only a newer resolver writes an economy record), so this needs a resolver downgrade under an economy record, which no session produces. — in_scope: no (LOW if it ever happened)
- [INFO] I2 scripts/merge-codex-config.py:211-213 — `append_items` on a one-line array with inner spaces gives `[ "a" , "x", "y"]`. It is valid TOML and parses to the wanted list; the layout is only slightly untidy. — in_scope: yes

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +2 −2 | Edit |
| scripts/merge-codex-config.py | +69 −1 | Edit |
| skills/ai-task/state.py | +18 −7 | Edit |
| tests/test_codex_install.py | +21 −3 | Edit |
| tests/test_profile_detect.py | +42 −5 | Edit |

+152 −18 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on 0dcba89e7 (run 10) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
