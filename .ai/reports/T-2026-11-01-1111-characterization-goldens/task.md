# T-2026-11-01-1111-characterization-goldens — Characterization goldens erase the run's own date so test_guarded passes on any day

bugfix · guarded · started 2026-11-01T11:11:28Z · claude

## Weight

```
scope          2  tests/test_state_characterization.py referenced from 10 files
behaviour      1  keyword 'workflow' in tests/fixtures/state/goldens/guarded.txt
reversibility  0  git revert returns everything
domain         0  tests only
novelty        0  tests only
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_state_characterization.py, tests/fixtures/state/goldens/guarded.txt
tests: tests/test_state_characterization.py
- s1 · tests/test_state_characterization.py, tests/fixtures/state/goldens/guarded.txt · tests/test_state_characterization.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 7c1c42a49 | .ai/state/logs/T-2026-11-01-1111-characterization-goldens/step-1.log | yes |
| 2 | step | 0 | 3abf1b825 | .ai/state/logs/T-2026-11-01-1111-characterization-goldens/step-2.log | no |
| 3 | suite | 0 | 3abf1b825 | .ai/state/logs/T-2026-11-01-1111-characterization-goldens/suite-3.log | no |
| 4 | e2e | 0 | 3abf1b825 | .ai/state/logs/T-2026-11-01-1111-characterization-goldens/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 Test coverage gap: nothing pins that a date other than the run's own stays visible through the real pipeline. The unit test `test_run_dates_are_exact` covers it only on a synthetic string, where 2026-01-02 survives. The goldens do not show it: after the rule, the only dates left are the pinned commit date and `<DATE>`. The rule would also hide a state.py regression that prints today's date where a different date belongs, for example an expiry date or a commit date. That is the stated trade-off of an exact rule, and the docstring says so. No action needed. in_scope: yes
- [INFO] I1 The rule is a plain `str.replace` with no token boundary. A run date glued to digits or letters would be rewritten too. No golden does this, and the NORMALISE regexes and task-id replacement run first, so ISO timestamps become `<TS>` and task ids `<IDn>` before the date step. A date inside a task id that is not in `task_ids()` would turn into `T-<DATE>-…`. That is still stable and would still show the change. in_scope: yes

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| tests/fixtures/state/goldens/guarded.txt | +3 −3 | Edit |
| tests/test_state_characterization.py | +21 −3 | Edit |

+24 −6 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 3abf1b825 (run 3) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
