# T-2026-10-29-1035-redesign-3-6 — Redesign 3.3e + 3.6: runtime-gate suites ported, run-all.sh and the e2e wrapper gone, docs cleanup

feature · guarded · started 2026-10-29T10:35:18Z · claude

## Weight

```
scope          2  tests/test-runtime-gate-fable.sh referenced from 24 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  "tests, CI and docs only; no hook, guard or state code changes" (declared)
novelty        0  "ports of shell suites follow the 3.3a-3.3d twin pattern" (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T10:35:18Z — /rr-build-all docs/sdlc/plans/claude-agentic-redesign.md (rows 3.3e, 3.H2, 3.6; docs/sdlc/intent/redesign-3-6.questions.md Q1=A Q2=A Q3=A)

## Plan

files: tests/test_runtime_gate_fable.py, tests/test_runtime_gate_codex.py, tests/test-runtime-gate-fable.sh, tests/test-runtime-gate-codex.sh, tests/lib.sh, tests/test_runtime_gate.py, tests/guard_harness.py, tests/run-all.sh, tests/test-end-to-end.sh, .github/workflows/tests.yml, tests/test_end_to_end.py, CONTRIBUTING.md, README.md, docs/agents.md, docs/architecture.md, docs/faq.md, docs/getting-started.md, docs/hook-performance.md, docs/hooks.md, docs/local-memory.md, docs/risk-tiers.md, docs/weight.md, docs/workflows.md, .pylintrc, .ai/project/known-risks.md, .ai/policies/testing.md
tests: tests/test_runtime_gate_fable.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate.py, tests/test_scaffold_idempotency.py, tests/test_shared_prompts_model_free.py, tests/test_instruction_budget.py
- s1 · tests/test_runtime_gate_fable.py, tests/test_runtime_gate_codex.py, tests/test-runtime-gate-fable.sh, tests/test-runtime-gate-codex.sh, tests/lib.sh, tests/test_runtime_gate.py, tests/guard_harness.py · tests/test_runtime_gate_fable.py, tests/test_runtime_gate_codex.py, tests/test_runtime_gate.py · done
- s2 · tests/run-all.sh, tests/test-end-to-end.sh, .github/workflows/tests.yml, tests/test_end_to_end.py, CONTRIBUTING.md · tests/test_scaffold_idempotency.py · done · after s1
- s3 · README.md, docs/agents.md, docs/architecture.md, docs/faq.md, docs/getting-started.md, docs/hook-performance.md, docs/hooks.md, docs/local-memory.md, docs/risk-tiers.md, docs/weight.md, docs/workflows.md, .pylintrc, .ai/project/known-risks.md · tests/test_shared_prompts_model_free.py, tests/test_instruction_budget.py · done · after s1
amended 2026-10-29T11:26:30Z: +.ai/policies/testing.md — 3.H2: the human's own testing.md edit (Q1=A, Q2=A), applied by the human's patch in this task; no agent edited it

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. 3.H2 is yours: in .ai/policies/testing.md set verify_command to python3 -I -m unittest discover -s tests -p 'test_*.py' (e2e skips itself without AI_E2E), and update healthy_output/runtime (:92-96), single_test (:97-99), :127-133 (no .sh suites left: test-runtime-gate-* are now tests/test_runtime_gate_{fable,codex}.py, lib.sh gone), the :147 row, :151 (CI runs unittest), :157-159 (no run-all.sh; the README count is unittest's 'Ran N tests')
asked: 2026-10-29T10:43:33Z · stage: implementation
A. done (recommended)
B. not yet
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose at 2026-10-29T10:52:14Z

## Q2. 3.H2 is not in the tree: .ai/policies/testing.md:87 still reads 'verify_command: bash tests/run-all.sh', and s2 deleted tests/run-all.sh, so verify --scope all can only fail. Edit testing.md as Q1 described (verify_command: python3 -I -m unittest discover -s tests -p 'test_*.py'; :92-99, :127-133, :141-151, :157-159), then answer A
asked: 2026-10-29T10:56:26Z · stage: implementation
A. testing.md edited (recommended)
B. not yet
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose at 2026-10-29T11:05:00Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 4b9f00f74 | .ai/state/logs/T-2026-10-29-1035-redesign-3-6/suite-1.log | no |
| 2 | suite | 0 | 48f5b5c23 | .ai/state/logs/T-2026-10-29-1035-redesign-3-6/suite-2.log | no |
| 3 | e2e | 0 | 48f5b5c23 | .ai/state/logs/T-2026-10-29-1035-redesign-3-6/e2e-3.log | no |
| 4 | suite | 0 | de66cb213 | .ai/state/logs/T-2026-10-29-1035-redesign-3-6/suite-4.log | no |
| 5 | e2e | 0 | de66cb213 | .ai/state/logs/T-2026-10-29-1035-redesign-3-6/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 README.md:859 — the count line under **Tests** ("Twenty-seven suites, 2,904 assertions") is unmeasured and false now; run-all.sh's per-suite "N passed" lines produced it and no longer exist; last verify: "Ran 905 tests", 65 test_*.py modules. testing.md and CONTRIBUTING.md:55 say update it in the same commit. Direction: unittest's "Ran N tests" figure, or drop the number. in_scope: yes
- [LOW] L1 tests/test_runtime_gate_fable.py:500 — shell `jq -e '.hooks.StopFailure' && fail` fired on an empty list ([] truthy in jq); the port's assertFalse(... .get("StopFailure")) passes on []. A regression leaving `StopFailure: []` after --plan max/pro --fable no is no longer caught (:529 assertNotIn covers only max→pro). Direction: assertNotIn("StopFailure", hooks). in_scope: yes
- [LOW] L2 tests/test_runtime_gate_fable.py (test_02–04), tests/test_runtime_gate_codex.py (test_03–05, test_10–11) — order coupling through the active marker, same as the shell suite, documented in the docstrings; -k runs of single methods fail or pass vacuously; whole-file runs (single_test, step_test_command) are safe. Direction: per-method precondition, or accept. in_scope: yes
- [LOW] L3 .ai/project/known-risks.md:559, :582 — Status says "open for the testing.md rows (human, 3.H)" but the human's testing.md edit in this diff removed them; no entry is wrongly marked fixed. Direction: close those halves. in_scope: yes
- [LOW] L4 .github/workflows/tests.yml:30-33 — a failing fast-suite step now skips the e2e step; run-all.sh ran both and listed failures together. Direction: `if: ${{ !cancelled() }}` on e2e, or accept. in_scope: yes
- [LOW] L5 .ai/policies/testing.md:~140 (human-owned) — verify_command no longer checks required tools locally; "the CI workflow checks them first" is true only in CI; missing jq/node fails deep in the fable suite. Direction: skipUnless/setUpClass naming the tool. in_scope: yes (human's file)
- [INFO] I1 — test_suite_parity.py checks a pair only while the .sh twin exists; TWIN_OF inert. Label comparison vs git show HEAD: 121/121 fable, 32/32 codex labels present; exit codes, exact outputs, byte-for-byte rewrite preserved; set/clear exit codes in test_10_cli not asserted separately; suites more hermetic (env unset).
- [INFO] I2 (out of scope) — stale .sh references outside the task's files: .ai/rules/skills.md:7, skills/AGENTS.md:5, skills/CLAUDE.md:5 (tests/test-project-update.sh), skills/project-update/render_instructions.py:169, hooks/lib/ai-hook-common.sh:24, tests/fixtures/{adopt,instructions/rules-project}/README.md; docs/ai-sdlc-adoption-plan.md, docs/redesign-analysis-2026-10-24.md historical. Links in README/CONTRIBUTING/docs: none broken. FAQ removal is the plan's.
- [INFO] I3 (out of scope) — pylint here 9.98: hooks/ai-guard.py:83, hooks/guard/decision.py, tools/golden-diff.py:37 (import-error); task files clean; guard_harness.py/test_runtime_gate.py diffs docstring-only.
- [INFO] I4 — the test_memory_sync.py:320 known-risks entry matches suite-1.log.
## VERDICT
verdict: pass_with_findings (M1 should be fixed before commit; L1 is a one-line restore)
scope_assessment: inside the plan (3.3e, 3.6, Q1–Q3=A); .gitignore dropped per Q2; testing.md the human's; nothing outside the declared files.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/policies/testing.md | +16 −20 | Edit |
| .ai/project/known-risks.md | +14 −4 | Edit |
| .github/workflows/tests.yml | +4 −1 | Edit |
| CONTRIBUTING.md | +3 −2 | Edit |
| README.md | +2 −2 | Edit |
| docs/architecture.md | +1 −1 | Edit |
| docs/faq.md | +0 −6 | Edit |
| docs/hook-performance.md | +4 −4 | Edit |
| docs/hooks.md | +3 −3 | Edit |
| tests/guard_harness.py | +2 −2 | Edit |
| tests/lib.sh | +0 −63 | Delete |
| tests/run-all.sh | +0 −29 | Delete |
| tests/test-end-to-end.sh | +0 −3 | Delete |
| tests/test-runtime-gate-codex.sh | +0 −168 | Delete |
| tests/test-runtime-gate-fable.sh | +0 −397 | Delete |
| tests/test_end_to_end.py | +6 −6 | Edit |
| tests/test_runtime_gate.py | +2 −2 | Edit |
| tests/test_runtime_gate_codex.py | +243 −0 | New |
| tests/test_runtime_gate_fable.py | +624 −0 | New |

+924 −713 lines, 19 files

## Verdict

close: closed
facts: (a) green — suite green on de66cb213 (run 4) · (b) green — 19 changed files, all in the task's files
gate: none
confirm: none
handoffs: 10 · suite runs: 3 · review passes: 1
