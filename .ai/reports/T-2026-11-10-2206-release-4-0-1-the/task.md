# T-2026-11-10-2206-release-4-0-1-the — Release 4.0.1: the version and pins move to 4.0.1, the changelog says 4.0.0 was tagged but never published

feature · guarded · started 2026-11-10T22:06:39Z · claude

## Weight

```
scope          2  package.json referenced from 47 files
behaviour      1  keyword 'workflow' in .ai/memory/2026-Q4.vanssa.5emr.jsonl
reversibility  0  git revert returns everything
domain         0  no code path changes (declared)
novelty        2  package.json is a dependency manifest; hint +1
coverage       0  no code file declared
W 5 → guarded   hints novelty +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, CHANGELOG.md, README.md, docs/getting-started.md, docs/installation.md, .ai/memory/2026-Q4.vanssa.5emr.jsonl
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 9d44f17f2 | .ai/state/logs/T-2026-11-10-2206-release-4-0-1-the/step-1.log | no |
| 2 | suite | 0 | 9d44f17f2 | .ai/state/logs/T-2026-11-10-2206-release-4-0-1-the/suite-2.log | no |
| 3 | e2e | 0 | 9d44f17f2 | .ai/state/logs/T-2026-11-10-2206-release-4-0-1-the/e2e-3.log | no |
| 4 | step | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2206-release-4-0-1-the/step-4.log | no |
| 5 | e2e | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2206-release-4-0-1-the/e2e-5.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 CHANGELOG 4.0.1 "Fixed" bullet 2 claims a change 4.0.1 does not contain (`CHANGELOG.md:13`) in_scope: yes
  - The docs commit e711b96 is an ancestor of the v4.0.0 tag e2263ef; `git diff e2263ef origin/main` touches only the fixture's three files, tests/test_fixtures_tracked.py and report/memory files. v4.0.0 already carried this text. Drop the bullet, or say the docs 4.0.0 shipped are unchanged.
- [LOW] L1 The 4.0.1 heading date is 2026-11-11 while the 4.0.0 entry keeps 2026-11-04 (`CHANGELOG.md:7,15`) in_scope: yes
  - Cosmetic; 4.0.0 was never released. Optional.
- [LOW] L2 The README badge and the CHANGELOG [4.0.1] link point at v4.0.1 before the tag exists (`README.md:3`) in_scope: yes
  - Same as the 3.2.2 pattern (R-readme-release-badge-404s-until-the-tag-eb9a); resolves once the tag is pushed.
- [INFO] I1 site/*.html still pins npx riskrails@4.0.0 and "Version 4.0.0" (`site/index.html:18`) in_scope: no
  - site/ is untracked and git-excluded, not part of this release; a deploy would show an unpublished version.
- [INFO] I2 No pin a user would run is left outside site/ (`CHANGELOG.md:15-17`) in_scope: yes
  - The CHANGELOG 4.0.0 body still says `npx riskrails@4.0.0` (E404); consider "(use 4.0.1)" there.

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .claude-plugin/marketplace.json | +2 −2 | Edit |
| .claude-plugin/plugin.json | +1 −1 | Edit |
| .codex-plugin/plugin.json | +1 −1 | Edit |
| CHANGELOG.md | +11 −2 | Edit |
| README.md | +11 −11 | Edit |
| docs/getting-started.md | +1 −1 | Edit |
| docs/installation.md | +18 −18 | Edit |
| package.json | +1 −1 | Edit |

+46 −37 lines, 8 files

## Verdict

close: closed
facts: (a) green — documents only since run 2 (1 files: CHANGELOG.md); doc_tests green in run 4 on 8f6bb97f5 · (b) green — 8 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 1
