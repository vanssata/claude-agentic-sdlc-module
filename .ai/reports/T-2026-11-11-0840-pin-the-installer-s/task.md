# T-2026-11-11-0840-pin-the-installer-s — Pin the installer's typed plan prompts with pty characterization tests and extract pickClaudePlan and pickCodexPlan without changing any output

refactoring · guarded · started 2026-11-11T08:40:37Z · claude

## Weight

```
scope          2  README.md referenced from 125 files
behaviour      1  keyword 'state machine' in README.md
reversibility  0  git revert returns everything
domain         0  installer plan question only; no money, tax, identity or personal data is written; the account f
novelty        1  pty tests exist (tests/test_profile_detect.py:423 opens one for stdin only); driving a prompt th
coverage       2  0 of 1 code files have a test
W 6 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_install_menu.py, README.md, bin/riskrails.js
tests: tests/test_install_menu.py
- s1 · tests/test_install_menu.py, README.md · tests/test_install_menu.py, tests/test_no_fallbacks.py · done
- s2 · bin/riskrails.js · tests/test_install_menu.py, tests/test_install_dry_run.py, tests/test_profiles.py, tests/test_codex_install.py, tests/test_dual_runtime_install.py, tests/test_shared_tree.py, tests/test_install_routes.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 253bfcf01 | .ai/state/logs/T-2026-11-11-0840-pin-the-installer-s/step-1.log | no |
| 2 | step | 0 | e0c2f3b7b | .ai/state/logs/T-2026-11-11-0840-pin-the-installer-s/step-2.log | no |
| 3 | step | 0 | 16e4e16bd | .ai/state/logs/T-2026-11-11-0840-pin-the-installer-s/step-3.log | no |
| 4 | suite | 0 | 16e4e16bd | .ai/state/logs/T-2026-11-11-0840-pin-the-installer-s/suite-4.log | no |
| 5 | e2e | 0 | 16e4e16bd | .ai/state/logs/T-2026-11-11-0840-pin-the-installer-s/e2e-5.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 tests/test_install_menu.py:129 — Two precedence edges of the extracted blocks are not pinned. (a) `claude_team` with no seat and a recorded plan: the `prev || detected` proposal must beat the `from === 'team'` branch in `pickClaudePlan`. No test covers it. (b) `--target both` on a pty asks Claude's question and then Codex's, in that order. The only `both` case is `--plan balanced-max`, which asks nothing. R2 did not change either edge (diff read), but Task A's `choose()` will plug into the same seams. · in_scope: yes
- [LOW] L2 tests/test_install_menu.py:69-71 — `on_terminal` writes the reply with a bare `os.write(master, …)`. If the child has exited before it read, so that nothing holds the slave and the master is already out of `streams`, the write can raise an uncaught OSError (EIO). The result is a test ERROR with a Python traceback instead of the terminal-text diagnostic. It needs a child that exits early (so not today's 13 tests) and it cannot hang. · in_scope: yes
- [INFO] I1 tests/test_install_menu.py:46-79 — fd and process handling is sound: slave closed after Popen, EIO/EOF drops the master, master closed in finally, timeout kills then Popen.__exit__ reaps, openpty failure raises SkipTest. No hang or leak risk. · in_scope: yes
- [INFO] I2 tests/test_install_menu.py:100-103 — Environment isolation holds: scratch HOME/CLAUDE_DIR/CODEX_DIR, SCRUB removes CLAUDE_CONFIG_DIR, CODEX_HOME, API/cloud variables and runtime markers; CLAUDE_PLUGIN_ROOT is not scrubbed and does not affect plan detection; --dry-run writes nothing. · in_scope: yes

Checked against the diff: no drift (five ask( literals unchanged; prev || detected, || proposed and the team ordering unchanged; parameters map correctly; no globals mutated; non-interactive branches untouched). The tests catch a reworded prompt, a removed || proposed, a precedence flip and --yes/flag changes. test_install_menu.py ran 3 times, 13 OK each. No scope creep.

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +1 −1 | Edit |
| bin/riskrails.js | +28 −16 | Edit |
| tests/test_install_menu.py | +216 −0 | New |

+245 −17 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 16e4e16bd (run 4) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
