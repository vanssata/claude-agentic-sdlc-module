# T-2026-11-13-1726-close-track-c-s-m1-and — Close track C's M1 and M2: an empty CHANGELOG section fails the release gate, and the workflow header says how to recover after a red verify

bugfix · guarded · started 2026-11-13T17:26:28Z · claude

## Weight

```
scope          2  tests/test_release.py referenced from 36 files
behaviour      1  keyword 'workflow' in the goal
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        0  the script and its tests exist; one condition and a comment (declared)
coverage       2  0 of 1 code files have a test
W 6 → guarded   hints none · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_release.py, tools/changelog-section.py, .github/workflows/npm-publish.yml
tests: tests/test_release.py
- s1 · tests/test_release.py, tools/changelog-section.py · tests/test_release.py · done
- s2 · .github/workflows/npm-publish.yml · tests/test_release.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 6c2f2212b | .ai/state/logs/T-2026-11-13-1726-close-track-c-s-m1-and/step-1.log | yes |
| 2 | step | 0 | 8450c9ac6 | .ai/state/logs/T-2026-11-13-1726-close-track-c-s-m1-and/step-2.log | no |
| 3 | step | 0 | 20791b5f1 | .ai/state/logs/T-2026-11-13-1726-close-track-c-s-m1-and/step-3.log | no |
| 4 | suite | 0 | 20791b5f1 | .ai/state/logs/T-2026-11-13-1726-close-track-c-s-m1-and/suite-4.log | no |
| 5 | e2e | 0 | 20791b5f1 | .ai/state/logs/T-2026-11-13-1726-close-track-c-s-m1-and/e2e-5.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The header recipe covers only a red run on main, not a red run from a hand-pushed tag (.github/workflows/npm-publish.yml:14-17) in_scope: yes — If a tag-triggered run goes red, vX.Y.Z already exists on the remote at the red commit, so tagging the fix commit fails locally or is rejected by the remote until the remote tag is deleted. Suggested: one clause saying to delete the existing remote tag first.
- [LOW] L2 A section holding only `### Added` and no items, or only an HTML comment, still passes the gate (tools/changelog-section.py:64) in_scope: yes — The goal (heading followed straight by the next heading) is closed; the degenerate-content case needs a content heuristic. Leave as a known limit.
- [INFO] I1 The tag-run path never checks that the tagged commit is on main (.github/workflows/npm-publish.yml:60-62, 117-118) in_scope: yes — pre-existing; "merge the fix to main" is a human convention, not a check.
- [INFO] I2 The test pins the empty-section behaviour, not every empty-section shape (tests/test_release.py:312-318) in_scope: yes — whitespace-only body before the next heading; end-of-file and CRLF take the same empty-body path, harmless.

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +5 −0 | Edit |
| tests/test_release.py | +8 −0 | Edit |
| tools/changelog-section.py | +4 −1 | Edit |

+17 −1 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 20791b5f1 (run 4) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
