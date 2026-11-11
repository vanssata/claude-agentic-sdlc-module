# T-2026-11-11-1147-release-4-1-0-the — Release 4.1.0: the version and the npx pins move to 4.1.0 and the changelog's Unreleased becomes 4.1.0, with the installer menu added

feature · guarded · started 2026-11-11T11:47:44Z · claude

## Weight

```
scope          2  package.json referenced from 51 files
behaviour      1  keyword 'state machine' in README.md
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        2  package.json is a dependency manifest; hint +1
coverage       0  no code file declared
W 6 → guarded   hints novelty +1 · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, CHANGELOG.md, README.md, docs/getting-started.md, docs/installation.md
tests: tests/test_release.py
- s1 · package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json · tests/test_release.py · done
- s2 · CHANGELOG.md, README.md, docs/getting-started.md, docs/installation.md · tests/test_release.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 7b6d25d6c | .ai/state/logs/T-2026-11-11-1147-release-4-1-0-the/step-1.log | no |
| 2 | step | 0 | 709ac8a58 | .ai/state/logs/T-2026-11-11-1147-release-4-1-0-the/step-2.log | no |
| 3 | suite | 0 | 709ac8a58 | .ai/state/logs/T-2026-11-11-1147-release-4-1-0-the/suite-3.log | no |
| 4 | e2e | 0 | 709ac8a58 | .ai/state/logs/T-2026-11-11-1147-release-4-1-0-the/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 Changelog says every menu has "the detected or recorded choice highlighted", but the fable and context menus have neither (`CHANGELOG.md:13`, `bin/riskrails.js` fable and `askContext` in the 8f32901 diff) in_scope: yes
  - Fable always starts on `yes` (initial 0) and context on `default` (initial 0). Only runtime, plan, statusline and Codex plan use a detected or recorded value. Wording only; the README paragraph says the same.
- [LOW] L2 The D3 bullet "On a terminal with no detected Claude plan, Enter installs the highlighted plan instead of exiting" holds only while the menu is on (`CHANGELOG.md:21`) in_scope: yes
  - With `RISKRAILS_MENU=off` or `TERM=dumb` on a terminal, the typed prompt returns and Enter on an undetected plan still exits 2, as before. The Added bullet names those switches, so this is an ambiguity, not a false claim. Optionally add "with the menu on".
- [LOW] L3 `docs/installation.md` still describes the plan as "proposed for you to confirm with Enter" (around line 15), and `docs/getting-started.md` says "Enter confirms" (`docs/getting-started.md:9`) in_scope: yes
  - This is still true with the arrow-key menu, but neither file mentions the menu, the flags that skip it or `RISKRAILS_MENU`. Only README and CHANGELOG do. Not wrong, only thinner than the README.
- [INFO] I1 The README badge and the `[4.1.0]` compare link point at `v4.1.0` before the tag exists (`README.md:3`, `CHANGELOG.md:115`) in_scope: yes
  - This is the same known and accepted pattern as 4.0.1 (the 404 resolves when the tag is pushed). `v4.0.1` exists as a tag, so the compare range `v4.0.1...v4.1.0` is right.

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .claude-plugin/marketplace.json | +2 −2 | Edit |
| .claude-plugin/plugin.json | +1 −1 | Edit |
| .codex-plugin/plugin.json | +1 −1 | Edit |
| CHANGELOG.md | +7 −0 | Edit |
| README.md | +11 −11 | Edit |
| docs/getting-started.md | +1 −1 | Edit |
| docs/installation.md | +18 −18 | Edit |
| package.json | +1 −1 | Edit |

+42 −35 lines, 8 files

## Verdict

close: closed
facts: (a) green — suite green on 709ac8a58 (run 3) · (b) green — 8 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
