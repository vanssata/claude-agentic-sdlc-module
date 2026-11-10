# T-2026-11-10-2156-every-fixture-file-the — Every fixture file the suite reads is tracked by git, so test_regenerate passes on a clean checkout (the v4.0.0 release verify)

bugfix · light · started 2026-11-10T21:56:24Z · claude

## Weight

```
scope          2  tests/fixtures/regenerate/v3.1.0-edited/.ai/local/plugin-update/.ai/policies/coding.md reference
behaviour      0  tests only
reversibility  0  git revert returns everything
domain         0  tests only
novelty        0  tests only
coverage       0  no code file declared
W 2 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_fixtures_tracked.py, tests/fixtures/regenerate/v3.1.0-edited/.ai/local/memory/config.json, tests/fixtures/regenerate/v3.1.0-edited/.ai/local/plugin-update/.ai/policies/coding.md, tests/fixtures/regenerate/v3.1.0-edited/.ai/state/state.json
tests: tests/test_fixtures_tracked.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 4f81293e2 | .ai/state/logs/T-2026-11-10-2156-every-fixture-file-the/step-1.log | yes |
| 2 | step | 0 | 2ac2e0a01 | .ai/state/logs/T-2026-11-10-2156-every-fixture-file-the/step-2.log | no |
| 3 | suite | 0 | 2ac2e0a01 | .ai/state/logs/T-2026-11-10-2156-every-fixture-file-the/suite-3.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| tests/fixtures/regenerate/v3.1.0-edited/.ai/local/memory/config.json | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/local/plugin-update/.ai/policies/coding.md | +1 −0 | New |
| tests/fixtures/regenerate/v3.1.0-edited/.ai/state/state.json | +4 −0 | New |
| tests/test_fixtures_tracked.py | +30 −0 | New |

+36 −0 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on 2ac2e0a01 (run 3) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 2 · suite runs: 1 · review passes: 0
