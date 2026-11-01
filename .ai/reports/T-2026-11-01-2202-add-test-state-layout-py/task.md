# T-2026-11-01-2202-add-test-state-layout-py — Add test_state_layout.py and test_state_characterization.py to the smoke gate so a Python-version drift in them shows on every PR, not first at release

feature · guarded · started 2026-11-01T22:02:28Z · claude

## Weight

```
scope          2  .github/workflows/tests.yml referenced from 20 files
behaviour      1  keyword 'workflow' in tests/test_release.py
reversibility  0  git revert returns everything
domain         0  CI configuration (declared)
novelty        0  two more names in an existing list (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: .github/workflows/tests.yml, tests/test_release.py
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | d54c0caec | .ai/state/logs/T-2026-11-01-2202-add-test-state-layout-py/step-1.log | no |
| 2 | suite | 0 | d54c0caec | .ai/state/logs/T-2026-11-01-2202-add-test-state-layout-py/suite-2.log | no |
| 3 | e2e | 0 | d54c0caec | .ai/state/logs/T-2026-11-01-2202-add-test-state-layout-py/e2e-3.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The new workflow comment says the two files' goldens/hashes "depend on the Python"; the docstring (tests/test_state_characterization.py:35) says they depend on the Python and git. git on ubuntu-latest is unpinned, so a git-version drift would now also fail the smoke job on every PR — the full and release jobs already run these files on the same runner image, so no new class of exposure, just earlier. Wording nit; no change needed. in_scope: yes
- [INFO] I1 Local 3.11–3.14 runs are green, but the CI runner's own 3.11/3.13 patch versions and git version were not exercised (the prior release run proved 3.12 only). The first PR run is the real check. in_scope: yes

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/tests.yml | +3 −0 | Edit |
| tests/test_release.py | +2 −1 | Edit |

+5 −1 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on d54c0caec (run 2) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
