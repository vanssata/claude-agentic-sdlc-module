# T-2026-10-28-003 — Add state.py profile set (same-tier plan switch on the human route) and make the installer copy profiles/ and resolve-profile.py into <home>/riskrails/ and write profile.json dialog.tool and set_by (R36.17, R36.19 installer half, R36.20)

feature · guarded · started 2026-10-28T12:04:38Z · claude

## Weight

```
scope          2  bin/riskrails.js referenced from 72 files
behaviour      2  changes what is installed in every user home (profiles, resolver, profile.json dialog.tool/set_b
reversibility  0  git revert returns everything
domain         1  installer output and plan budgets in the user home; no guard decision, nothing customer-visible 
novelty        1  first writer of profile.json besides the installer; Codex version probe for the dialog tool is n
coverage       1  1 of 2 code files have a test
W 7 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, tests/test_profile_detect.py, bin/riskrails.js, tests/test_install_routes.py, tests/test_codex_install.py, tests/test_install_dry_run.py, tests/test_profiles.py, .ai/project/known-risks.md
tests: tests/test_profile_detect.py, tests/test_install_routes.py, tests/test_codex_install.py, tests/test_install_dry_run.py, tests/test_profiles.py
- s1 · skills/ai-task/state.py, tests/test_profile_detect.py · tests/test_profile_detect.py · done
- s2 · bin/riskrails.js, tests/test_install_routes.py, tests/test_codex_install.py, tests/test_install_dry_run.py, tests/test_profiles.py · tests/test_install_routes.py, tests/test_codex_install.py, tests/test_install_dry_run.py, tests/test_profiles.py · done
amended 2026-10-28T12:26:05Z: +.ai/project/known-risks.md — rr-review: the out-of-scope finding I1 is recorded in known-risks.md, as the review skill requires

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | de62dffd7 | .ai/state/logs/T-2026-10-28-003/step-1.log | yes |
| 2 | step | 0 | 4aad34820 | .ai/state/logs/T-2026-10-28-003/step-2.log | no |
| 3 | step | 1 | 717fba49c | .ai/state/logs/T-2026-10-28-003/step-3.log | yes |
| 4 | step | 1 | a76cae705 | .ai/state/logs/T-2026-10-28-003/step-4.log | no |
| 5 | step | 0 | 15f65b26e | .ai/state/logs/T-2026-10-28-003/step-5.log | no |
| 6 | suite | 0 | 15f65b26e | .ai/state/logs/T-2026-10-28-003/suite-6.log | no |
| 7 | e2e | 0 | 15f65b26e | .ai/state/logs/T-2026-10-28-003/e2e-7.log | no |
| 8 | suite | 0 | 505024a63 | .ai/state/logs/T-2026-10-28-003/suite-8.log | no |
| 9 | e2e | 0 | 505024a63 | .ai/state/logs/T-2026-10-28-003/e2e-9.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 skills/ai-task/state.py:~733 (`installer_command`) — The command is built by string formatting, and `plugin_version` comes from the installed profile.json unquoted. It is printed as the exit-6 refusal and is also `profile detect`'s `command`, which R36.3 and R36.4 later put in front of the human or the dialog as the command to approve. Setting `plugin_version` to `1; rm -rf ~` makes the refusal print `npx riskrails@1; rm -rf ~ --target claude ...`. A profile.json with no version, or the installer's `unknown` fallback, gives `riskrails@unknown`, which npx cannot fetch. Only the user's own home writes this file, so the risk is low. Quote the version with `shlex.quote` and drop `unknown`. · in_scope: yes
- [LOW] L2 skills/ai-task/state.py:~796 and `load_resolver` (~763) — Malformed input ends in a traceback instead of `die`: a profile.json with a non-string `plan` (a list) raises `TypeError` at `have not in plans`; a broken `resolve-profile.py` raises an uncaught `SyntaxError` from `exec_module`, outside the `except (OSError, ValueError)`; a profile.json with no `plan` prints "None → max also changes settings.json…" instead of calling the profile unreadable. Nothing is written in any of these cases. · in_scope: yes
- [LOW] L3 skills/ai-task/state.py:~764 (`load_resolver`) — `spec_from_file_location` + `exec_module` writes bytecode, so `<home>/riskrails/scripts/__pycache__` (or one in the plugin cache or checkout) appears after one `profile set` and is never cleaned; the installer copies only the single file. A `sys.dont_write_bytecode` guard around the import would stop it. · in_scope: yes
- [LOW] L4 tests — Untested branches of `cmd_profile_set`: the settings half of `rendered(old) != rendered(new)` (the tiers test edits only `riskrails.tiers`, so a tiers-only comparison stays green); the "no resolve-profile.py" exit-1 refusal; the fallback to the legacy `claude-agentic/profile.json`; a team plan (`max` → `team-max`). `test_set_same_tier` does not check that settings and agent frontmatter are byte-identical, though the code compares settings. The covered refusals (exit 6, exit 5, no profile, unknown plan, no plan) all fail correctly. · in_scope: yes
- [LOW] L5 bin/riskrails.js:~725 — The dry-run "shared:" line still reads `riskrails/ai (31 files), riskrails/ai-path` and does not list `riskrails/profiles/*` or `riskrails/scripts/resolve-profile.py`; the dry-run tests do not cover it. Real runs for both runtimes do copy them (`test_installed_profiles_and_resolver`, byte-equal). · in_scope: yes
- [INFO] I1 bin/riskrails.js:45-46 vs skills/ai-task/state.py:436 — The installer picks its home from `CLAUDE_DIR`/`CODEX_DIR` or `--home`/`--codex-home`; state.py uses `CLAUDE_CONFIG_DIR`/`CODEX_HOME`. After `npx riskrails --home /x`, `profile set` and `read_profile` look in `~/.claude`, so they write another home's profile.json or fail with "no plan profile". The mismatch predates this task, but `set` is the first writer that depends on it. · in_scope: no
- [INFO] I2 skills/ai-task/state.py:~818 — `set` keeps only `plugin_version` and `dialog`, and only when present, so a pre-change profile.json without `dialog` still has none after `set` and the dialog stays off until the next `npx riskrails`. Diffed against a fresh `--plan max20` install, the profile.json files are identical except `set_by.via`; `fable` round-trips. · in_scope: yes
- [INFO] I3 bin/riskrails.js:296-304 (`codexDialogTool`) — The version probe runs `codex` from the installer's PATH, not the human's terminal (spike Open #2; PATH 0.164.0 against sessions on 0.165.0). A pre-release such as `0.165.0-alpha.1` counts as 0.165.0. A failed or timed-out probe turns the dialog off, which fails safe. The comparison and the test table are correct. · in_scope: yes
- [INFO] I4 skills/ai-task/state.py:39 — The module docstring still reads `state.py profile [--field …]`, with no `detect`, `set`, `--runtime` or exit 6; exit 6 also means SUITE_BUDGET and the review-round limit elsewhere. · in_scope: yes
- [INFO] I5 docs/sdlc/intent/command-choice-dialog.questions.md — Outside the task's files but harmless: it only adds Q10 and the G1 record of the human's answer A (`>= 0.165.0`), which `CODEX_DIALOG_SINCE = [0,165,0]` relies on. docs/dialog-spike.md "Open" item 3 still lists G1 as unconfirmed. · in_scope: no
- [INFO] I6 skills/ai-task/state.py:~763 (`load_resolver`) — On the plugin route the installed `<home>/riskrails/{scripts,profiles}` is tried before `CLAUDE_PLUGIN_ROOT`, so after a plugin upgrade without `npx riskrails` the older resolver is used. This matches the older `plugin_version` in profile.json and `test_the_installed_resolver_wins`: consistent, and stale by design. · in_scope: yes

## VERDICT
verdict: pass_with_findings
(No in-scope BLOCKER or HIGH. The LOW findings cover robustness, a missing pycache guard, test-coverage gaps and dry-run visibility.)
scope_assessment: The change stayed inside the task's files; docs/sdlc/intent/command-choice-dialog.questions.md is outside them but only records the human's G1 answer; the T-002 detect port was touched only where set and the installer rely on it.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +6 −0 | Edit |
| bin/riskrails.js | +20 −1 | Edit |
| skills/ai-task/state.py | +103 −9 | Edit |
| tests/test_codex_install.py | +22 −0 | Edit |
| tests/test_install_dry_run.py | +13 −0 | Edit |
| tests/test_install_routes.py | +37 −1 | Edit |
| tests/test_profile_detect.py | +141 −3 | Edit |
| tests/test_profiles.py | +6 −0 | Edit |

+348 −14 lines, 8 files

## Verdict

close: closed
facts: (a) green — suite green on 505024a63 (run 8) · (b) green — 8 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 2 · review passes: 1
