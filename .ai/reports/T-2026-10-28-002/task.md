# T-2026-10-28-002 — Port the installer's Claude and Codex plan detection to state.py profile detect and make bin/riskrails.js call it, with identical detection results

refactoring · guarded · started 2026-10-28T11:36:51Z · claude

## Weight

```
scope          2  bin/riskrails.js referenced from 70 files
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  installer plan detection only; no user-project module, no guard decision (declared)
novelty        0  ports two existing JS functions; the installer already runs python3 -I scripts (bin/riskrails.js
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, bin/riskrails.js, tests/test_profile_detect.py, tests/fixtures/profile/claude-cases.json, tests/fixtures/profile/codex-cases.json
tests: tests/test_profile_detect.py
- s1 · tests/test_profile_detect.py, tests/fixtures/profile/claude-cases.json, tests/fixtures/profile/codex-cases.json · tests/test_profile_detect.py · done
- s2 · skills/ai-task/state.py · tests/test_profile_detect.py · done
- s3 · bin/riskrails.js · tests/test_install_dry_run.py, tests/test_codex_install.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 9bfbc1844 | .ai/state/logs/T-2026-10-28-002/step-1.log | yes |
| 2 | step | 0 | cd193ea64 | .ai/state/logs/T-2026-10-28-002/step-2.log | no |
| 3 | step | 0 | 4016e612c | .ai/state/logs/T-2026-10-28-002/step-3.log | no |
| 4 | suite | 0 | 4016e612c | .ai/state/logs/T-2026-10-28-002/suite-4.log | no |
| 5 | e2e | 0 | 4016e612c | .ai/state/logs/T-2026-10-28-002/e2e-5.log | no |
| 6 | step | 0 | a9588a11d | .ai/state/logs/T-2026-10-28-002/step-6.log | no |
| 7 | suite | 0 | a9588a11d | .ai/state/logs/T-2026-10-28-002/suite-7.log | no |
| 8 | e2e | 0 | a9588a11d | .ai/state/logs/T-2026-10-28-002/e2e-8.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 Non-string JSON values stringify differently from JS String(): Python `js_str` falls back to `str()` for floats (1.0 → "1.0" vs JS "1"), big ints (>2^53), lists (JS comma-join: ['max'] → "max", Python "['max']") and dicts (JS "[object Object]", Python repr — a dict {'a':'max'} as org/seat flips classification: JS plan ''/"team", Python max/team-max because the repr contains "max"). Codex chatgpt_plan_type ['pro'] → JS "pro", Python "['pro']"; {} → JS "[object object]". Codex chatgpt_plan_type [] is truthy in JS (loop stops, returns ''), falsy in Python (continues to next token/file, may return "pro"). Differential run (old JS from HEAD vs state.py profile detect --json), 216 cases, 45 diffs, all of these kinds. Not a regression for real data (strings; int/bool/null match), but breaks "identical" and the fixtures do not pin it. Fix: mirror JS in js_str, or state the departure. — skills/ai-task/state.py:550-558, 603-612 — in_scope: yes
- [LOW] L2 JWT body decoding stricter than Node's Buffer.from(x,'base64url'): a stray non-alphabet character (`*`) in the body, an embedded newline, invalid UTF-8 bytes (Node substitutes U+FFFD; Python UnicodeDecodeError → ''), and an out-of-range element gave a plan in JS and '' in Python (4 cases). Standard alphabet, padded, missing padding, len%4==1, trailing `!!` all matched. Real JWTs unaffected. — skills/ai-task/state.py:597 — in_scope: yes
- [LOW] L3 `profile detect` silently ignores --field, --tier and --other (e.g. `profile detect --other` exits 0 reporting the own runtime); at HEAD these were argparse errors. Fix: die on them in cmd_profile_detect. — skills/ai-task/state.py:522-526, 683 — in_scope: yes
- [INFO] I1 ~/.claude.json containing the literal `null`: old JS threw an uncaught TypeError (account.oauthAccount outside the try), crashing the installer; the port reports "unknown". Benign behaviour change. Array/string/number/bool/{} files, oauthAccount null/array/string/number/bool, top-level organizationType only, BOM, invalid JSON all matched. — in_scope: yes
- [INFO] I2 Failure semantics changed by construction: a python3 crash/non-zero → {} via allowFail + try/catch → "undetected" → interactive "Could not detect plan" prompt, or die(...,1) without --plan and no previous install. python3 is already a hard prerequisite; stderr inherited. No crash path found on real input. — bin/riskrails.js:327-333 — in_scope: yes
- [INFO] I3 `python3 -I state.py` writes skills/ai-task/__pycache__ into SRC (npx cache or plugin cache) on first run; harmless, git-ignored. — in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: inside the approved step 7a; only the two accepted departures (`org`/`raw` in `live`, rr-status untouched). For every string-valued input and realistic file shape, detection and installer messages are identical to HEAD. Diffs are limited to non-string JSON values (L1) and non-standard JWT bodies (L2), neither pinned by a test.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| bin/riskrails.js | +11 −47 | Edit |
| skills/ai-task/state.py | +204 −1 | Edit |
| tests/fixtures/profile/claude-cases.json | +51 −0 | New |
| tests/fixtures/profile/codex-cases.json | +24 −0 | New |
| tests/test_profile_detect.py | +200 −0 | New |

+490 −48 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on a9588a11d (run 7) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
