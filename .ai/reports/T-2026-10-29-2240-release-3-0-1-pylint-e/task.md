# T-2026-10-29-2240-release-3-0-1-pylint-e — Release 3.0.1: pylint E clean, versions synced, CI release workflow to the npm registry, update-available notice

feature · guarded · started 2026-10-29T22:40:12Z · claude

## Weight

```
scope          2  hooks/ai-guard.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in the goal
reversibility  0  git revert returns everything
domain         1  a CI workflow that releases the package to the registry (declared)
novelty        2  package.json is a dependency manifest; hint +1
coverage       1  4 of 8 code files have a test
W 7 → guarded   hints novelty +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T22:40:12Z — /rr-build-all: points 1,2,4 of the release check (2 handed to the README task), registry release 3.0.1, update notice

## Plan

files: hooks/ai-guard.py, hooks/guard/decision.py, hooks/guard/git.py, hooks/guard/dialog.py, tests/test_dialog_gate.py, tools/golden-diff.py, package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, tools/sync-version.py, tests/test_release.py, .github/workflows/npm-publish.yml, hooks/context-guard.py, hooks/update_notice.py, tests/test_update_notice.py, tests/test_context_guard.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-1.md, bin/riskrails.js, tests/test_codex_install.py
tests: tests/test_guard_characterization.py tests/test_dialog_gate.py tests/test_ai_git_guard.py tests/test_release.py tests/test_install_routes.py tests/test_update_notice.py tests/test_context_guard.py
- s1 · hooks/ai-guard.py, hooks/guard/decision.py, hooks/guard/git.py, hooks/guard/dialog.py, tests/test_dialog_gate.py, tools/golden-diff.py · tests/test_guard_characterization.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py · done
- s2 · package.json, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, tools/sync-version.py, tests/test_release.py · tests/test_release.py, tests/test_install_routes.py · done
- s3 · .github/workflows/npm-publish.yml, tests/test_release.py · tests/test_release.py · done · after s2
- s4 · hooks/context-guard.py, hooks/update_notice.py, tests/test_update_notice.py · tests/test_update_notice.py, tests/test_context_guard.py · done
amended 2026-10-29T22:43:11Z: +tests/test_context_guard.py — s4 follow-up: its SessionStart runs with a temp riskrails/ home would spawn a real registry fetch; the test env sets RISKRAILS_NO_UPDATE_CHECK=1 (isolation, no assertion changes)
amended 2026-10-29T22:53:40Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-1.md — the review report file state.py review --report reads; the worktree sandbox refuses stdin to python
amended 2026-10-29T22:54:46Z: +bin/riskrails.js, tests/test_codex_install.py — H1: Codex hook list must ship update_notice.py; installed version from profile.json; installed-layout test

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | c85a40fef | .ai/state/logs/T-2026-10-29-2240-release-3-0-1-pylint-e/suite-1.log | no |
| 2 | suite | 0 | c85a40fef | .ai/state/logs/T-2026-10-29-2240-release-3-0-1-pylint-e/suite-2.log | no |
| 3 | e2e | 0 | c85a40fef | .ai/state/logs/T-2026-10-29-2240-release-3-0-1-pylint-e/e2e-3.log | no |
| 4 | suite | 0 | 0386e958e | .ai/state/logs/T-2026-10-29-2240-release-3-0-1-pylint-e/suite-4.log | no |
| 5 | e2e | 0 | 0386e958e | .ai/state/logs/T-2026-10-29-2240-release-3-0-1-pylint-e/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [HIGH] H1 Update notice never fires on the installer's layouts (hooks/context-guard.py:753, hooks/update_notice.py:41, bin/riskrails.js:1283) in_scope: yes. Claude npx copies hooks to ~/.claude/hooks/, so plugin_root=~/.claude and ~/.claude/.claude-plugin/plugin.json does not exist: installed_version None, notice always empty. Codex: codexHookFiles() is a fixed four-file list, update_notice.py is never installed, the import raises and is swallowed. Direction: installed version from <home>/riskrails/profile.json plugin_version (bin/riskrails.js:301), manifest as fallback; add update_notice.py to the Codex hook list; an installed-layout test.
- [MEDIUM] M1 test_no_installer_directory_spawns_nothing is vacuous (tests/test_update_notice.py:112): passes with or without the isdir guard.
- [MEDIUM] M2 A failed Release step cannot be recovered by a rerun (.github/workflows/npm-publish.yml:86-90, :42-52): verify stops at already-on-registry; a publish-only rerun fails with 403 before the release step.
- [LOW] L1 sync-version accepts prereleases and the workflow has no dist-tag (tools/sync-version.py:24, npm-publish.yml:90): v3.1.0-rc.1 ships as latest.
- [LOW] L2 The refresh child can hang and pile up (hooks/update_notice.py:101): urlopen timeout is per socket op, read unbounded, checked_at not written before the fetch.
- [LOW] L3 Dead skipTest (tests/test_release.py:137).
- [LOW] L4 NODE_AUTH_TOKEN fallback unverified (npm-publish.yml:89): empty string versus unset with OIDC.
- [INFO] I1 The release gate runs the suite on a fresh checkout (npm-publish.yml:36), in_scope: no: the recorded TestMigration0009 fresh-checkout failure blocks the first tag.
- [INFO] I2 Actions pinned by tag, not SHA; pylint unpinned; a tag on any commit triggers.
- [INFO] I3 RISKRAILS_REGISTRY_URL accepts file:// and any urllib scheme; user env only, response reduced to strict X.Y.Z.

## EXAMINED AND CLEAN
SessionStart output byte-identical with no notice; startup only; fail-open; no network on the hook path; detached child; home resolution; version compare; cache corruption; atomic cache write; no expression injection; job order and least privilege; npm@11 >= 11.5.1; repository URL; sync-version matches exactly 5 keys; behaviour 0 of the pylint fixes; test isolation; no scope creep.

## VERDICT
verdict: pass_with_findings
scope_assessment: inside the approved plan; the one real gap is H1.
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .claude-plugin/marketplace.json | +2 −2 | Edit |
| .claude-plugin/plugin.json | +1 −1 | Edit |
| .codex-plugin/plugin.json | +1 −1 | Edit |
| .github/workflows/npm-publish.yml | +117 −0 | New |
| bin/riskrails.js | +1 −1 | Edit |
| hooks/ai-guard.py | +1 −1 | Edit |
| hooks/context-guard.py | +27 −1 | Edit |
| hooks/guard/dialog.py | +3 −1 | Edit |
| hooks/update_notice.py | +135 −0 | New |
| package.json | +1 −1 | Edit |
| tests/test_codex_install.py | +1 −1 | Edit |
| tests/test_context_guard.py | +3 −2 | Edit |
| tests/test_release.py | +142 −0 | New |
| tests/test_update_notice.py | +192 −0 | New |
| tools/golden-diff.py | +1 −1 | Edit |
| tools/sync-version.py | +84 −0 | New |

+712 −13 lines, 16 files

## Verdict

close: closed
facts: (a) green — suite green on 0386e958e (run 4) · (b) green — 16 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 3 · review passes: 1
