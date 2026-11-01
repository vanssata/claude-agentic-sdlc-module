# T-2026-10-31-1957-close-the-five — Close the five statusline risks from the T-2026-10-31-1841 review (a8d3, d7ec, de9a, c7fa, 8080), each pinned by a test

bugfix · guarded · started 2026-10-31T19:57:06Z · claude

## Weight

```
scope          2  bin/riskrails.js referenced from 140 files
behaviour      2  installer restore changes what an update writes into settings.json; path guard gains a deny (dec
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        0  fixes inside existing functions, existing test files (declared)
coverage       1  1 of 2 code files have a test
W 6 → guarded   hints none · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: bin/riskrails.js, hooks/runtime-gate.py, hooks/ai-path-guard-defaults.json, tests/test_runtime_gate_fable.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py, CHANGELOG.md, README.md, docs/installation.md
tests: tests/test_runtime_gate_fable.py, tests/test_runtime_gate.py, tests/test_ai_path_guard.py
- s1 · bin/riskrails.js, tests/test_runtime_gate_fable.py · tests/test_runtime_gate_fable.py · done
- s2 · bin/riskrails.js, tests/test_runtime_gate_fable.py · tests/test_runtime_gate_fable.py · done
- s3 · tests/test_runtime_gate_fable.py · tests/test_runtime_gate_fable.py · done
- s4 · hooks/ai-path-guard-defaults.json, tests/test_ai_path_guard.py · tests/test_ai_path_guard.py · done
- s5 · hooks/runtime-gate.py, tests/test_runtime_gate.py · tests/test_runtime_gate.py · done
- s6 · CHANGELOG.md, README.md, docs/installation.md · no tests · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | a91e673f3 | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-1.log | yes |
| 2 | step | 1 | 2e709162f | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-2.log | yes |
| 3 | step | 1 | 78d47f023 | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-3.log | yes |
| 4 | step | 0 | 6209fff15 | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-4.log | no |
| 5 | step | 1 | 11177760e | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-5.log | yes |
| 6 | step | 0 | 39e546056 | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-6.log | no |
| 7 | step | 1 | 9a4e16dbc | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-7.log | yes |
| 8 | step | 1 | 299071075 | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-8.log | yes |
| 9 | step | 0 | ff58ccf2a | .ai/state/logs/T-2026-10-31-1957-close-the-five/step-9.log | no |
| 10 | suite | 0 | 623ac9d50 | .ai/state/logs/T-2026-10-31-1957-close-the-five/suite-10.log | no |

suite passing · e2e not_applicable (installer and statusline only: no task flow reaches e2e) · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 bin/riskrails.js:628-631 (+ 'on' branch at ~652-668 and 'moved' branch at ~641) — `wrapped()` now returns '' for an unparsable `--then` tail, so `saved` is empty. The run still overwrites `line.command` with the plain WANT, which drops the user's malformed tail. The message then reads "set the plugin's statusline (...)", or on the moved path just "moved the fable-gate wrapper...". Before the fix the raw tail was printed and recorded. Scenario: a hand-edited `--then 'unterminated` line is replaced and the install never says a user command was replaced. Nothing is recorded; only the dated settings.json backup holds the text (and the second run the same day overwrites that backup). The recorded `replaced` is protected, which was the goal, but the user loses the notice. Suggested direction: print the raw tail in the message without recording it. in_scope: yes
- [LOW] L2 bin/riskrails.js:~689-692 (`persist()` before the settings write) — the restore is now one-shot on `record.mode`, and `persist()` writes `mode: own` before `settings.json.tmp` is written and renamed. If that write throws (ENOSPC, EACCES), the record already says own, so the retry no longer restores the replaced command. Before the fix the retry would have. The window is narrow and the command is still in `record.replaced`. in_scope: yes
- [INFO] I1 hooks/ai-path-guard-defaults.json:41 (the new pattern) — a CLAUDE_CONFIG_DIR home is covered, because hooks/guard/paths.py:781-784 anchors it with the `.claude/` prefix. A `--home` install whose dir is not named `.claude` is also covered when the guard runs with `CLAUDE_CONFIG_DIR` set to it. test_13b only runs with `CLAUDE_CONFIG_DIR=""`, so that route is not pinned by the test. in_scope: no
- [INFO] I2 bin/riskrails.js:~718 — in the gate-off branch, `shSplit(rest)` is not wrapped in try/catch, so a malformed tail would throw. Both callers (lines 731 and 1205) pass `'on'`, so the branch is unreachable today. in_scope: no

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +11 −0 | Edit |
| README.md | +1 −1 | Edit |
| bin/riskrails.js | +4 −2 | Edit |
| docs/installation.md | +1 −1 | Edit |
| hooks/ai-path-guard-defaults.json | +3 −2 | Edit |
| hooks/runtime-gate.py | +5 −3 | Edit |
| tests/test_ai_path_guard.py | +21 −0 | Edit |
| tests/test_runtime_gate.py | +21 −0 | Edit |
| tests/test_runtime_gate_fable.py | +32 −0 | Edit |

+99 −9 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on 623ac9d50 (run 10) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
