# T-2026-10-27-001 — redesign 3.3a: port the five guard shell suites to Python twins (TWIN_OF, parity), delete each .sh once its twin is green, CI matrix 3.10-3.13, update run-all.sh

refactoring · guarded · started 2026-10-27T07:13:40Z · claude

## Weight

```
scope          2  tests/test-ai-git-guard.sh referenced from 66 files
behaviour      1  keyword 'workflow' in tests/test-ai-scope-guard.sh
reversibility  0  git revert returns everything
domain         0  test harness and CI config; no auth, payments, data or install paths (declared)
novelty        0  pattern established by 3.1/3.2 (TWIN_OF, unittest, run-all python discover) (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/guard_harness.py, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test-ai-git-guard.sh, tests/test-ai-path-guard.sh, tests/test-ai-scope-guard.sh, tests/test-context-guard.sh, tests/test-runtime-gate.sh, tests/run-all.sh, .github/workflows/tests.yml, docs/hooks.md, .ai/project/known-risks.md
tests: tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_context_guard.py, tests/test_runtime_gate.py, tests/test_suite_parity.py
- s1 · tests/guard_harness.py, tests/test_ai_git_guard.py, tests/test-ai-git-guard.sh, tests/run-all.sh · tests/test_ai_git_guard.py, tests/test_suite_parity.py · done
- s2 · tests/test_ai_path_guard.py, tests/test-ai-path-guard.sh, tests/run-all.sh, tests/guard_harness.py · tests/test_ai_path_guard.py, tests/test_suite_parity.py · done
- s3 · tests/test_ai_scope_guard.py, tests/test-ai-scope-guard.sh, tests/run-all.sh, tests/guard_harness.py · tests/test_ai_scope_guard.py, tests/test_suite_parity.py · done
- s4 · tests/test_runtime_gate.py, tests/test-runtime-gate.sh, tests/run-all.sh, tests/guard_harness.py · tests/test_runtime_gate.py, tests/test_suite_parity.py · done
- s5 · tests/test_context_guard.py, tests/test-context-guard.sh, tests/run-all.sh, tests/guard_harness.py · tests/test_context_guard.py, tests/test_suite_parity.py · done
- s6 · .github/workflows/tests.yml, docs/hooks.md · tests/run-all.sh · done
amended 2026-10-27T07:40:13Z: +.ai/project/known-risks.md — Q1=B: record the Python 3.10 gap (existing suites red on 3.10) as a known risk

## Questions

[questions.md](questions.md) — 0 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 0e4d4e96c | .ai/state/logs/T-2026-10-27-001/step-1.log | no |
| 2 | step | 0 | 338827716 | .ai/state/logs/T-2026-10-27-001/step-2.log | no |
| 3 | step | 0 | 1604942fe | .ai/state/logs/T-2026-10-27-001/step-3.log | no |
| 4 | step | 1 | 038121050 | .ai/state/logs/T-2026-10-27-001/step-4.log | no |
| 5 | step | 1 | acadeb1a2 | .ai/state/logs/T-2026-10-27-001/step-5.log | no |
| 6 | step | 0 | 02de32219 | .ai/state/logs/T-2026-10-27-001/step-6.log | no |
| 7 | step | 1 | 16ce9891e | .ai/state/logs/T-2026-10-27-001/step-7.log | no |
| 8 | step | 0 | fb77c6832 | .ai/state/logs/T-2026-10-27-001/step-8.log | no |
| 9 | suite | 0 | f0ad11860 | .ai/state/logs/T-2026-10-27-001/suite-9.log | no |
| 10 | e2e | 0 | f0ad11860 | .ai/state/logs/T-2026-10-27-001/e2e-10.log | no |
| 11 | suite | 0 | 841495407 | .ai/state/logs/T-2026-10-27-001/suite-11.log | no |
| 12 | e2e | 0 | 841495407 | .ai/state/logs/T-2026-10-27-001/e2e-12.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 .ai/policies/testing.md:142,147 — the binding "Touching -> Run" table still names the five deleted shell suites: row 142 (`hooks/ai-*-guard.sh`) lists `tests/test-ai-path-guard.sh`, `test-ai-scope-guard.sh`, `test-ai-git-guard.sh`; row 147 lists `tests/test-runtime-gate.sh`, `tests/test-context-guard.sh`. A step that follows the table for a guard/runtime-gate/context-guard change names files that no longer exist (row 147 was already stale for `test-fable-gate.sh`). The task updated `docs/hooks.md:613` but not this table; the Python twins are reachable only through `run-all.sh`'s `unittest discover`. — in_scope: yes
- [LOW] L2 tests/test_runtime_gate.py (test_09, the `e6` case "a twin file whose name Codex would not register is not used") — `self.assertIsNone(upd(out))` is weaker than the shell's `[ "$(upd "$out")" = null ]` only in that the shell failed when the gate printed nothing? No: `upd ""` → `{}` → `null` in the shell too; but in the twin `upd("")` is also None, so a gate that prints nothing for that payload passes. Its siblings e5/e7 also assert the context text; e6 does not. No mutant of the 282 gate mutants exposed it. — in_scope: yes
- [LOW] L3 tests/test_ai_path_guard.py:~203-225 (test_07, "reading, diffing, linting and testing the hook files stays allowed" and "a writer's name in prose…") — each list of 6 / 3 commands sits in a single subTest with assertEqual inside the loop; the first refused command ends the loop, so the report names one command where the shell named every one. A regression is still caught. Separately, `tests/run-all.sh` now reports a twin failure as `FAILED: unittest`, not by the suite name the five shell suites had — the failing suite must be read from the log. — in_scope: yes
- [INFO] I1 tests/test_ai_git_guard.py (divergence 1) — confirmed harmless: the four Codex payloads (force push, git status, argocd sync, apply_patch) do not depend on the branch or on `.env.example`; the fixtures and the wildcard-add section each still run on a real checkout; the wildcard-add case now runs on main, where it still allows the .env.example add — the only loss is the feature-branch combination. Multiset of 40 guard calls (payload, env, cwd state) equals the shell's; only the order differs. — in_scope: yes
- [INFO] I2 tests/guard_harness.py `run` (divergences 3, 6) — merging stderr is the same as lib.sh `run_fixture`/`decide` (`2>&1`); only the git suite's `expect()` and a few `grep` checks read stdout alone in the shell, so the twin is equal or stricter there. `timed()` measures `subprocess.run` + the decision parse without jq start-up — a few ms looser against 500–8000 ms budgets; all 34 budgets match the shell's (32 by regex plus the 500 ms and a 1000 ms it missed). — in_scope: yes
- [INFO] I3 tests/test_ai_path_guard.py (test_05) — the second `says(...)` re-runs the guard where the shell reused one output: 617 guard calls vs 616 — harmless. In "140 KB of U+3000 ' sh 2>x' words and rm -f a.txt are allowed" the shell's `jq -Rsc` produced a payload with U+FFFD at pipe-chunk boundaries (108-character difference in the JSON); the twin sends the intended payload and passes on it. — in_scope: yes
- [INFO] I4 divergences 2, 4, 5 — checked, none is a gap. 2: the chained test_NN_ sections fail loudly, not silently; one run in isolation (e.g. runtime-gate test_09) fails because test_07 starts the task the later sections read — no false pass. 4: `sys.executable` is the same interpreter as `python3` under -I. 5: see the recorder row under EXAMINED AND CLEAN. — in_scope: yes
- [INFO] I5 tests/test_guard_characterization.py `TestTimed.test_budgets` (pre-existing, not part of this change) — fails (3 cases, 25/40 ms medians) when two `run-all.sh` runs share the machine: `bash tests/run-all.sh` with 3.13 first on PATH failed that way beside the 3.11 run; green when rerun alone. The new twins carry their own wall-clock budgets (500–8000 ms), so CI jitter can touch them too. — in_scope: no

## EXAMINED AND CLEAN
- Recorder method: the guard replaced by a stdin recorder in scratch plugin copies, each deleted shell (`git show HEAD:`) and its twin run against it. Git 40 vs 40 calls, identical payload, env (HOME, CLAUDE_CONFIG_DIR, CODEX_HOME, AI_UNATTENDED, LC_ALL), cwd and current.json (parsed). Scope 25 vs 25 identical. Path 616 vs 617, identical apart from I3, including backslashes, $'…', U+ code points, decide_t/decide_home/write_home env, LC_ALL=C, AI_UNATTENDED.
- Mutation parity: context-guard.py 111 mutants agree; runtime-gate.py 282 agree but m0026 (exist_ok True->False) killed by the twin only; guard/git.py 55 agree; guard/scope.py 166 agree; guard/paths.py 90 of 416 sampled agree. Nothing the shell killed survives in a twin.
- Deny-all hook: every shell decide failure has a matching twin failure (only a tmp.XXX vs tmpXXX label difference); the allow-expectations exist and can fail.
- Parity labels: all `pass "…"` literals of the five shells appear in their twins, except the declared SHELL_MECHANICS.
- Python versions: each twin green via discover on 3.10, 3.11, 3.13, 3.14; path and context twins under LC_ALL=C LANG=C; runtime-gate twin under env -i; full run-all green with 3.11 first, and with 3.13 first when run alone (I5). The known-risks claim that the twins pass on 3.10 holds.
- Gate env isolation, section order, quota/import/budget/model_fallback/missed_reroute/parallel/fail-open assertions match the shell one for one; jq -e truthiness cases map correctly.
- Context twin: transcript key order and compact separators as jq; hostile session id stray-file check, 5.5 MB lines, stale snapshot, Codex runtime, eight concurrent writers, hanging state.py, settings/DEFAULT_WINDOW checks all present.
- run-all.sh and CI: only the five suites left the shell list; twins run through the existing discover; guard_harness.py is not collected. tests.yml valid (3.11–3.13, fail-fast false, setup-python@v5 with the matrix variable). docs/hooks.md:613 correct.
- known-risks entry: "twins pass on 3.10" confirmed; per-suite 3.10 failure counts not checked.
- Scope: only tests, CI, docs/hooks.md, known-risks.md changed.

## VERDICT
verdict: pass_with_findings
scope_assessment: inside the approved plan (tests and CI only); the only gap is the stale file names in .ai/policies/testing.md (L1), documentation drift, not a behaviour change.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +9 −0 | Edit |
| .github/workflows/tests.yml | +7 −3 | Edit |
| docs/hooks.md | +1 −1 | Edit |
| tests/guard_harness.py | +70 −0 | New |
| tests/run-all.sh | +3 −3 | Edit |
| tests/test-ai-git-guard.sh | +0 −70 | Delete |
| tests/test-ai-path-guard.sh | +0 −832 | Delete |
| tests/test-ai-scope-guard.sh | +0 −119 | Delete |
| tests/test-context-guard.sh | +0 −454 | Delete |
| tests/test-runtime-gate.sh | +0 −364 | Delete |
| tests/test_ai_git_guard.py | +107 −0 | New |
| tests/test_ai_path_guard.py | +958 −0 | New |
| tests/test_ai_scope_guard.py | +127 −0 | New |
| tests/test_context_guard.py | +605 −0 | New |
| tests/test_runtime_gate.py | +608 −0 | New |

+2495 −1846 lines, 15 files

## Verdict

close: closed
facts: (a) green — suite green on 841495407 (run 11) · (b) green — 15 changed files, all in the task's files
gate: none
confirm: none
handoffs: 6 · suite runs: 2 · review passes: 1
