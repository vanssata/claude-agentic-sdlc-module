# T-2026-11-01-2252-move-actions-checkout — Move actions/checkout, setup-node, setup-python to their Node 24 majors (v7) in the four workflows

feature · guarded · started 2026-11-01T22:52:00Z · claude

## Weight

```
scope          2  .github/workflows/tests.yml referenced from 23 files
behaviour      1  keyword 'workflow' in .github/workflows/generator-generic-ossf-slsa3-publish.yml
reversibility  0  git revert returns everything
domain         1  npm-publish.yml is the release/publish pipeline (declared)
novelty        0  version bump of existing pins, same style (declared)
coverage       0  no code file declared
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: .github/workflows/tests.yml, .github/workflows/pylint.yml, .github/workflows/npm-publish.yml, .github/workflows/generator-generic-ossf-slsa3-publish.yml, tests/test_release.py
tests: tests/test_release.py
- s1 · tests/test_release.py · tests/test_release.py · done
- s2 · .github/workflows/tests.yml, .github/workflows/pylint.yml, .github/workflows/npm-publish.yml, .github/workflows/generator-generic-ossf-slsa3-publish.yml · tests/test_release.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 88a4928c1 | .ai/state/logs/T-2026-11-01-2252-move-actions-checkout/step-1.log | yes |
| 2 | step | 0 | a2d321eb8 | .ai/state/logs/T-2026-11-01-2252-move-actions-checkout/step-2.log | no |
| 3 | suite | 0 | a2d321eb8 | .ai/state/logs/T-2026-11-01-2252-move-actions-checkout/suite-3.log | no |
| 4 | e2e | 0 | a2d321eb8 | .ai/state/logs/T-2026-11-01-2252-move-actions-checkout/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [INFO] I1 The @v7 tags for actions/checkout, actions/setup-node and actions/setup-python, and their input semantics, cannot be checked from the repo. If a tag does not exist, the workflow fails at "Set up job". I confirmed only that the 13 lines are consistent and that tests/test_release.py pins the same tag. in_scope: no
- [INFO] I2 .github/workflows/generator-generic-ossf-slsa3-publish.yml:63 still uses slsa-framework/slsa-github-generator@v1.4.0, which runs its own pinned actions and may still hit the Node 20 deprecation. This is out of scope by plan and should go in the risk register. in_scope: no

No in-scope findings.

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/generator-generic-ossf-slsa3-publish.yml | +1 −1 | Edit |
| .github/workflows/npm-publish.yml | +5 −5 | Edit |
| .github/workflows/pylint.yml | +2 −2 | Edit |
| .github/workflows/tests.yml | +5 −5 | Edit |
| tests/test_release.py | +2 −2 | Edit |

+15 −15 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on a2d321eb8 (run 3) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
