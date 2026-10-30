# T-2026-10-29-2350-ci-in-two-tiers-smoke — CI in two tiers: smoke gate on pull requests, full parallel suite on release tags; Node before tests, full clone, AI_TIMED_FACTOR on runners

feature · guarded · started 2026-10-29T23:50:54Z · claude

## Weight

```
scope          2  .github/workflows/tests.yml referenced from 10 files
behaviour      1  keyword 'workflow' in .github/workflows/npm-publish.yml
reversibility  0  git revert returns everything
domain         1  the release gate before the registry upload (declared)
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 5 → guarded   hints none · unknown novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T23:50:54Z — /rr-build-all: option A plus fixes 1-3 after the failed v3.0.1 release run 40973600734

## Plan

files: .github/workflows/tests.yml, .github/workflows/npm-publish.yml, tests/test_release.py, tests/install_harness.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-3.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-4.md
tests: tests/test_release.py
- s1 · .github/workflows/tests.yml, .github/workflows/npm-publish.yml, tests/test_release.py · tests/test_release.py · done
amended 2026-10-29T23:56:54Z: +tests/install_harness.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-3.md — B1: the harness must resolve node against the runner's PATH, not the test's reduced PATH; review report file
amended 2026-10-30T00:00:17Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-4.md — review pass 2 report file

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 0fb3a1eaa | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/suite-1.log | no |
| 2 | e2e | 0 | 0fb3a1eaa | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/e2e-2.log | no |
| 3 | step | 1 | 81d8a15f1 | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/step-3.log | yes |
| 4 | step | 0 | 5b6eff114 | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/step-4.log | no |
| 5 | suite | 0 | 5b6eff114 | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/suite-5.log | no |
| 6 | e2e | 0 | 5b6eff114 | .ai/state/logs/T-2026-10-29-2350-ci-in-two-tiers-smoke/e2e-6.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, blockers_open

```
## FINDINGS
- [BLOCKER] B1 The setup-node fix does not fix the test_dual_runtime_install failure (.github/workflows/npm-publish.yml:48-51, tests/test_dual_runtime_install.py:25,89) in_scope: yes. install_harness.install() runs ["node", ...] with env PATH = self.bin + ":/usr/bin:/bin"; Python resolves node against that env PATH; setup-node installs under /opt/hostedtoolcache/node and adds it to the runner PATH only. Locally passes only because a node is in /usr/bin. The text test cannot catch it. Direction: resolve node from the runner's PATH in the harness, or put its directory on BASE_PATH; needs a file outside the step.
- [MEDIUM] M1 The job id test was renamed to smoke (.github/workflows/tests.yml:15): required check names change; if branch protection lists them, PRs wait forever.
- [MEDIUM] M2 PRs lose full-suite coverage (.github/workflows/tests.yml): node-, git- and bash-dependent regressions reach main unseen and surface only at a tag. Direction: record it, or run the full suite on a schedule / workflow_dispatch.
- [LOW] L1 AI_TIMED_FACTOR does not cover all wall-clock assertions (tests/test_ere_unit.py:104,119, tests/test_guard_differential.py:197): fixed 0.5 s / 2.0 s budgets now under run_suite parallelism can flake.
- [LOW] L2 AI_TIMED_FACTOR on the e2e step is a no-op (.github/workflows/npm-publish.yml:60-61).
- [INFO] I1 .ai/policies/testing.md:99,133 still describe CI as a serial unittest discover.

## EXAMINED AND CLEAN
YAML parses; SMOKE_FILES folding and splitting; matrix; run_suite exit codes, no fail-fast, serial handling, resources and temp dirs; fetch-depth: 0 fixes the git archive failure; AI_TIMED_FACTOR covers TestGateFastPath and TestTimed; smoke files absent from the failed run's failures; permissions and publish job untouched; pylint.yml still runs on PRs; test_release pins strings and order.

## VERDICT
verdict: blockers_open
scope_assessment: inside the declared files; objective B only partly met — B1 needs tests/test_dual_runtime_install.py or its harness, outside the step.
```

### Pass 2 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 tests.yml smoke job relies on the runner's preinstalled node and does not check for it (.github/workflows/tests.yml:34-38): an image without node would show as FileNotFoundError inside test cases, not a missing-tool line. Direction: add node to the tool loop or setup-node to the smoke job.
- [LOW] L2 shutil.which("node") or "node" falls back quietly (tests/install_harness.py:19, pin tests/test_release.py:~198): with no node the pin dies in realpath(None) with TypeError, not a clear message. Direction: assertIsNotNone(shutil.which("node")) first.
- [INFO] I1 The pin asserts INSTALLER[0] is absolute and equals which("node"); fails on the old code; would not catch a new harness bypassing INSTALLER; test_dual_runtime_install is the end-to-end proof. Adequate for guarded.

## EXAMINED AND CLEAN
B1 fix on ubuntu-24.04 with setup-node (riskrails.js never respawns node; python3 via /usr/bin is system 3.12; codex stubs are /bin/sh); only test_dual_runtime_install reduces PATH; run_suite --serial semantics equal verify_command; fetch-depth: 0 on the verify checkout, smoke files need no history; AI_TIMED_FACTOR order pinned; setup-node once and before the suite; SMOKE_FILES matches the test; no test weakened.

## VERDICT
verdict: pass
scope_assessment: inside the plan; B1 closed by an absolute node path plus a pin that failed before and passes after; no new blocker.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +14 −4 | Edit |
| .github/workflows/tests.yml | +11 −3 | Edit |
| tests/install_harness.py | +3 −1 | Edit |
| tests/test_release.py | +62 −1 | Edit |

+90 −9 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on 5b6eff114 (run 5) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 6 · suite runs: 2 · review passes: 2
