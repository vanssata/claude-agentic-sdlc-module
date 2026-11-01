# T-2026-11-01-2205-release-3-2-1-the — Release 3.2.1: the version bump and docs for the tree with the Python 3.12 test fix, since v3.2.0 was tagged but never published

feature · guarded · started 2026-11-01T22:05:13Z · claude

## Weight

```
scope          2  package.json referenced from 36 files
behaviour      1  keyword 'state machine' in README.md
reversibility  0  git revert returns everything
domain         0  release metadata (declared)
novelty        2  package.json is a dependency manifest; hint +1
coverage       0  no code file declared
W 5 → guarded   hints novelty +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, CHANGELOG.md, README.md, docs/getting-started.md, docs/installation.md
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | c84a45cbb | .ai/state/logs/T-2026-11-01-2205-release-3-2-1-the/step-1.log | no |
| 2 | suite | 0 | c84a45cbb | .ai/state/logs/T-2026-11-01-2205-release-3-2-1-the/suite-2.log | no |
| 3 | e2e | 0 | c84a45cbb | .ai/state/logs/T-2026-11-01-2205-release-3-2-1-the/e2e-3.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 README badge and Release link point at releases/tag/v3.2.1, which does not exist until the human pushes the tag and the Release job completes — same as every release (3.2.0 did the same); expected, 404 window ends at release. in_scope: yes
- [INFO] I1 README heading "Upgrade to 3.1" / "From 3.0.x: update the home (npx riskrails@3.2.1 …)" were already that way in 3.2.0 — not a regression, nothing to do. in_scope: yes
- [INFO] I2 [3.2.0] heading now "— 2026-11-01 (not published)"; nothing in the repo parses CHANGELOG.md, npm-publish.yml has no changelog check; the [3.2.0] link-reference is unchanged and resolves. in_scope: yes

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .claude-plugin/marketplace.json | +2 −2 | Edit |
| .claude-plugin/plugin.json | +1 −1 | Edit |
| .codex-plugin/plugin.json | +1 −1 | Edit |
| CHANGELOG.md | +12 −1 | Edit |
| README.md | +12 −12 | Edit |
| docs/getting-started.md | +1 −1 | Edit |
| docs/installation.md | +18 −18 | Edit |
| package.json | +1 −1 | Edit |

+48 −37 lines, 8 files

## Verdict

close: closed
facts: (a) green — suite green on c84a45cbb (run 2) · (b) green — 8 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
