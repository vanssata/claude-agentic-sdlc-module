# T-2026-10-28-006 — Runtime-default context with an opt-in economy mode, and model + context use in the Claude and Codex statusline

feature · full · started 2026-10-28T15:39:48Z · claude

## Weight

```
scope          2  profiles/max.json referenced from 9 files
behaviour      2  changes what the installer writes into settings.json and context-guard stops holding a prompt ba
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  new flags on existing installer/statusline paths (declared)
coverage       1  2 of 5 code files have a test
W 7 → guarded   hints none · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by hooks/CLAUDE.md: behaviour 2 weakens a refusal at 2026-10-28T15:39:48Z

## Plan

files: profiles/max.json, profiles/pro.json, scripts/resolve-profile.py, scripts/merge-codex-config.py, hooks/context-guard.py, hooks/runtime-gate.py, bin/riskrails.js, bin/claude-1m, instructions/routing.md, README.md, docs/hooks.md, tests/test_profiles.py, tests/test_context_guard.py, tests/test_install_dry_run.py, tests/test_runtime_gate.py, tests/test_codex_install.py, tests/test-runtime-gate-fable.sh, tests/test_rename.py, .ai/project/known-risks.md
tests: tests/test_profiles.py, tests/test_context_guard.py, tests/test_install_dry_run.py, tests/test_runtime_gate.py, tests/test_codex_install.py
- s1 · profiles/max.json, profiles/pro.json, scripts/resolve-profile.py, tests/test_profiles.py · tests/test_profiles.py · done
- s2 · hooks/context-guard.py, tests/test_context_guard.py · tests/test_context_guard.py · done
- s3 · bin/riskrails.js, bin/claude-1m, instructions/routing.md, tests/test_install_dry_run.py · tests/test_install_dry_run.py · done
- s4 · hooks/runtime-gate.py, bin/riskrails.js, tests/test_runtime_gate.py, tests/test_install_dry_run.py · tests/test_runtime_gate.py, tests/test_install_dry_run.py · done
- s5 · scripts/merge-codex-config.py, bin/riskrails.js, tests/test_codex_install.py · tests/test_codex_install.py · done
- s6 · README.md, docs/hooks.md · tests/test_instruction_budget.py · done
amended 2026-10-28T15:46:27Z: +tests/test-runtime-gate-fable.sh — s4: its installer checks pin the statusline wrapper without --context and a silent bare wrapper; --statusline-context yes (default) changes both
amended 2026-10-28T15:54:43Z: +tests/test_rename.py, .ai/project/known-risks.md — Q1=A: drop the four stale ALLOWED entries left by 2996977 so the suite can go green; known-risks.md records it

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. The whole suite is red only on test_rename's stale allow-list (pre-existing since 2996977 Fix codex, outside this task). How do we get a green suite for close?
asked: 2026-10-28T15:53:13Z · stage: implementation
context: tests/test_rename.py:22, .ai/state/logs/T-2026-10-28-006/suite-8.log:241
A. Amend tests/test_rename.py into this task, drop the four stale ALLOWED entries, run the suite once more (last run in budget) (recommended)
B. Leave it for its own task; fix it there first, then resume this one and re-run verify
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T15:54:43Z

## G1. Approve T-2026-10-28-006 for implementation? (gate: human_approval)
asked: 2026-10-28T16:15:13Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via terminal at 2026-10-28T16:16:54Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | bb2c32066 | .ai/state/logs/T-2026-10-28-006/step-1.log | no |
| 2 | step | 0 | 279e0662f | .ai/state/logs/T-2026-10-28-006/step-2.log | no |
| 3 | step | 0 | f8456b533 | .ai/state/logs/T-2026-10-28-006/step-3.log | no |
| 4 | step | 0 | 6d4d68fbe | .ai/state/logs/T-2026-10-28-006/step-4.log | no |
| 5 | step | 0 | 7a1c2eb9e | .ai/state/logs/T-2026-10-28-006/step-5.log | no |
| 6 | step | 0 | ba3002f33 | .ai/state/logs/T-2026-10-28-006/step-6.log | no |
| 7 | step | 0 | 56fd3bcff | .ai/state/logs/T-2026-10-28-006/step-7.log | no |
| 8 | suite | 1 | 56fd3bcff | .ai/state/logs/T-2026-10-28-006/suite-8.log | no |
| 9 | suite | 0 | 26a22ae63 | .ai/state/logs/T-2026-10-28-006/suite-9.log | no |
| 10 | e2e | 0 | 26a22ae63 | .ai/state/logs/T-2026-10-28-006/e2e-10.log | no |
| 11 | step | 0 | 6ff89803a | .ai/state/logs/T-2026-10-28-006/step-11.log | no |
| 12 | suite | 0 | 15caaa968 | .ai/state/logs/T-2026-10-28-006/suite-12.log | no |
| 13 | e2e | 0 | 15caaa968 | .ai/state/logs/T-2026-10-28-006/e2e-13.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M1 hooks/context-guard.py:146-147 — configured_window() on the Codex hook reads Claude's CLAUDE_CODE_AUTO_COMPACT_WINDOW and ~/.claude/settings.json before Codex's own profile.json; a Codex default install still blocks when Claude has a window (reproduced: thresholds (133600, 200400)). Not a regression; no test for Codex default + Claude window. — in_scope: yes
- [MEDIUM] M2 bin/riskrails.js:627-629 — ownCompactWindow only removes the current plan's economy value; pro(300000)→max default keeps 300000 as if user-owned, so a [1m] session compacts near 267k and the guard blocks from ~320k; dry run silent. Previously a pro→max re-install overwrote it with 800000. — in_scope: yes
- [MEDIUM] M3 scripts/merge-codex-config.py:144-151,154-156 — with status_line absent, writing ["model-with-reasoning","context-used"] replaces Codex's built-in default item set (unconfirmed contents); a user who never configured it may lose items, contrary to "never removes" as documented. — in_scope: yes
- [LOW] L1 bin/riskrails.js:498 + instructions/routing.md:41,50 — default renders "from never (economy only) the prompt is held back once"; routing.md:50 still says the guard holds a prompt back at the block threshold, false in default mode. — in_scope: yes
- [LOW] L2 README.md:579 — hooks table still says context-guard holds a prompt back once from 120% unconditionally. — in_scope: yes
- [LOW] L3 scripts/merge-codex-config.py:160-162 — rewriting status_line drops trailing and in-array comments. — in_scope: yes
- [LOW] L4 scripts/resolve-profile.py:87 ↔ skills/ai-task/state.py:826-836 — state.py profile set rebuilds profile.json without keeping context, so an economy record flips to default; installer_command() (state.py:720) suggests a re-install without --context economy. — in_scope: yes
- [INFO] I1 scripts/merge-codex-config.py:136-140 — an explicit status_line = [] gets both items appended. — in_scope: yes
- [INFO] I2 bin/claude-1m:31-37 — a user's own autoCompactWindow (e.g. 400000) now applies to claude-1m sessions instead of the exported 800000. — in_scope: yes
## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +11 −0 | Edit |
| README.md | +12 −5 | Edit |
| bin/claude-1m | +15 −14 | Edit |
| bin/riskrails.js | +97 −28 | Edit |
| docs/hooks.md | +20 −5 | Edit |
| hooks/context-guard.py | +59 −20 | Edit |
| hooks/runtime-gate.py | +59 −12 | Edit |
| instructions/routing.md | +2 −2 | Edit |
| profiles/max.json | +3 −1 | Edit |
| profiles/pro.json | +3 −1 | Edit |
| scripts/merge-codex-config.py | +66 −0 | Edit |
| scripts/resolve-profile.py | +15 −3 | Edit |
| tests/test-runtime-gate-fable.sh | +18 −6 | Edit |
| tests/test_codex_install.py | +74 −0 | Edit |
| tests/test_context_guard.py | +68 −11 | Edit |
| tests/test_install_dry_run.py | +62 −13 | Edit |
| tests/test_profiles.py | +22 −0 | Edit |
| tests/test_rename.py | +0 −3 | Edit |
| tests/test_runtime_gate.py | +25 −0 | Edit |

+631 −124 lines, 19 files

## Verdict

close: closed
facts: (a) green — suite green on 15caaa968 (run 12) · (b) green — 19 changed files, all in the task's files
gate: requested G1 at 2026-10-28T16:15:13Z; approved by vanssa at 2026-10-28T16:16:54Z via terminal
confirm: none
handoffs: 9 · suite runs: 3 · review passes: 1
