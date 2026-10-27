# T-2026-10-27-004 — 3.3d: the last five shell suites get Python twins with R13 parity and are deleted

refactoring · guarded · started 2026-10-27T10:33:09Z · claude

## Weight

```
scope          2  tests/test-shared-prompts-model-free.sh referenced from 79 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  test suites only; no security, data or money path (declared)
novelty        0  same pattern as 3.3a-3.3c (898816a, c0a250b, bb89ee0) (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_shared_prompts_model_free.py, tests/test-shared-prompts-model-free.sh, tests/test_codex_agent_render.py, tests/test-codex-agent-render.sh, tests/test_usage_report.py, tests/test-usage-report.sh, tests/test_codex_usage_report.py, tests/test-codex-usage-report.sh, tests/test_instruction_budget.py, tests/test-instruction-budget.sh, tests/run-all.sh, .ai/project/known-risks.md
tests: tests/test_shared_prompts_model_free.py, tests/test_codex_agent_render.py, tests/test_usage_report.py, tests/test_codex_usage_report.py, tests/test_instruction_budget.py, tests/test_suite_parity.py
- s1 · tests/test_shared_prompts_model_free.py, tests/test-shared-prompts-model-free.sh, tests/run-all.sh · tests/test_shared_prompts_model_free.py, tests/test_suite_parity.py · done
- s2 · tests/test_codex_agent_render.py, tests/test-codex-agent-render.sh, tests/run-all.sh · tests/test_codex_agent_render.py, tests/test_suite_parity.py · done
- s3 · tests/test_usage_report.py, tests/test-usage-report.sh, tests/run-all.sh · tests/test_usage_report.py, tests/test_suite_parity.py · done
- s4 · tests/test_codex_usage_report.py, tests/test-codex-usage-report.sh, tests/run-all.sh · tests/test_codex_usage_report.py, tests/test_suite_parity.py · done
- s5 · tests/test_instruction_budget.py, tests/test-instruction-budget.sh, tests/run-all.sh, .ai/project/known-risks.md · tests/test_instruction_budget.py, tests/test_suite_parity.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 18d95ecc1 | .ai/state/logs/T-2026-10-27-004/step-1.log | no |
| 2 | step | 0 | 2c284fe5b | .ai/state/logs/T-2026-10-27-004/step-2.log | no |
| 3 | step | 0 | 762c4092a | .ai/state/logs/T-2026-10-27-004/step-3.log | no |
| 4 | step | 0 | 95ce48fec | .ai/state/logs/T-2026-10-27-004/step-4.log | no |
| 5 | step | 0 | 9ee40549e | .ai/state/logs/T-2026-10-27-004/step-5.log | no |
| 6 | suite | 0 | ab8ab9acc | .ai/state/logs/T-2026-10-27-004/suite-6.log | no |
| 7 | e2e | 0 | ab8ab9acc | .ai/state/logs/T-2026-10-27-004/e2e-7.log | no |
| 8 | suite | 0 | bd196941b | .ai/state/logs/T-2026-10-27-004/suite-8.log | no |
| 9 | e2e | 0 | bd196941b | .ai/state/logs/T-2026-10-27-004/e2e-9.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS

- [MEDIUM] M1 known-risks entry claims the remaining suites are unowned, which is wrong for most (`.ai/project/known-risks.md:578`, "Not ported, and no plan row owns them") in_scope: yes
  Plan row 3.5 (line 134) creates tests/test_{install_dry_run,dual_runtime_install,codex_install,profiles,shared_tree}.py and deletes the five install .sh suites; row 3.6 (line 136) deletes tests/test-end-to-end.sh and run-all.sh; 3.1/3.2 already created twins for test-guard-characterization and test-scaffold-idempotency. The 3.H2 inference contradicts plan lines 226-230 (verify_command stays run-all.sh until 3.5; 3.H2 is after 3.5). Only test-runtime-gate-fable.sh and test-runtime-gate-codex.sh look unowned. Suggested: narrow the entry, cite 3.5/3.6, drop or correct the 3.H2 inference.

- [LOW] L1 inherited vacuous subTest (`tests/test_codex_usage_report.py`, "{\"subagent\":\"review\"} is recognised", assertIn("review", out)) in_scope: yes
  The corpus already holds an `ai-reviewer` thread, so "review" is in `out` even if the string form is never recognised. Run alone, the string-form record yields a `codex / review` row. Suggested: assert something only the string form produces. Nothing was dropped relative to the shell.

- [INFO] I1 `lines_of` uses splitlines(), which also breaks on \x0b \x0c \x85  ; only failure-message line numbers could skew; no such characters in scope today. in_scope: yes

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved plan (tests plus the risk register, no shipped code or policy change), and each twin was green before its suite was deleted. The two findings are in the register entry (M1) and one inherited vacuous check (L1); neither is a regression against the shell suites.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +10 −0 | Edit |
| tests/run-all.sh | +4 −4 | Edit |
| tests/test-codex-agent-render.sh | +0 −112 | Delete |
| tests/test-codex-usage-report.sh | +0 −239 | Delete |
| tests/test-instruction-budget.sh | +0 −370 | Delete |
| tests/test-shared-prompts-model-free.sh | +0 −67 | Delete |
| tests/test-usage-report.sh | +0 −253 | Delete |
| tests/test_codex_agent_render.py | +195 −0 | New |
| tests/test_codex_usage_report.py | +279 −0 | New |
| tests/test_instruction_budget.py | +373 −0 | Edit |
| tests/test_shared_prompts_model_free.py | +163 −0 | New |
| tests/test_usage_report.py | +395 −2 | Edit |

+1419 −1047 lines, 12 files

## Verdict

close: closed
facts: (a) green — suite green on bd196941b (run 8) · (b) green — 12 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
