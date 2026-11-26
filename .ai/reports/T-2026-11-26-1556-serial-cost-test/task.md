# T-2026-11-26-1556-serial-cost-test — Run the flaky wall-clock test test_cost_with_100_decisions serially in the suite command

bugfix · guarded · started 2026-11-26T15:56:31Z · claude

## Weight

```
scope          2  .ai/policies/verification.md referenced from 91 files
behaviour      2  keyword 'workflow' in .ai/policies/verification.md; hint +1
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 6 → guarded   hints behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_release.py, .ai/policies/verification.md, .github/workflows/tests.yml, .github/workflows/npm-publish.yml, README.md, CONTRIBUTING.md, .ai/project/modules.md, .ai/project/dependencies.md
tests: tests/test_release.py
- s1 · tests/test_release.py · tests/test_release.py · done
- s2 · .ai/policies/verification.md, .github/workflows/tests.yml, .github/workflows/npm-publish.yml, README.md, CONTRIBUTING.md · tests/test_release.py · done · after s1
amended 2026-11-26T16:07:23Z: +.ai/project/modules.md, .ai/project/dependencies.md — review I1: project docs on serial timed tests are incomplete/stale (dependencies.md:26 says release runs factor 1)

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 2418a4015 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/step-1.log | yes |
| 2 | step | 0 | 8061f3164 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/step-2.log | no |
| 3 | suite | 1 | 8061f3164 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/suite-3.log | no |
| 4 | step | 0 | d16a50d54 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/step-4.log | no |
| 5 | step | 2 | d16a50d54 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/step-5.log | no |
| 6 | step | 0 | d16a50d54 | .ai/state/logs/T-2026-11-26-1556-serial-cost-test/step-6.log | no |

suite failing · e2e not_run · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 CONTRIBUTING.md:50 says the first command is `verify_command` in `.ai/policies/testing.md`, but the command lives in `.ai/policies/verification.md:4`. The diff did not introduce the wrong pointer, and the prose around it is otherwise accurate. Only the added line sits next to it. — CONTRIBUTING.md:50 — in_scope: yes
- [INFO] I1 `.ai/project/modules.md:16` notes that `TestGateFastPath` runs serially, and `.ai/project/dependencies.md:26` is a risk note about `AI_TIMED_FACTOR`. Neither mentions the new serial method. Both are descriptive, not enforced by any test, and I left them alone. — .ai/project/modules.md:16 — in_scope: no
- [INFO] I2 This test is now a serial entry. If it is renamed, `check_serial` fails with exit 2 ("matches no test"). That is loud, not silent, so it is the safe direction. — tests/run_suite.py:~285 — in_scope: no

No BLOCKER, HIGH or MEDIUM.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the stated scope (one serial argument propagated to every copy of the suite command, plus its pin). I did not run the whole suite, only the two test files above through `run_suite.py`.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/policies/verification.md | +1 −1 | Edit |
| .ai/project/dependencies.md | +2 −1 | Edit |
| .ai/project/modules.md | +1 −1 | Edit |
| .github/workflows/npm-publish.yml | +1 −1 | Edit |
| .github/workflows/tests.yml | +1 −1 | Edit |
| CONTRIBUTING.md | +11 −5 | Edit |
| README.md | +1 −1 | Edit |
| tests/test_release.py | +2 −1 | Edit |

+20 −12 lines, 8 files

## Verdict

close: abandoned
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 2 · suite runs: 1 · review passes: 1
