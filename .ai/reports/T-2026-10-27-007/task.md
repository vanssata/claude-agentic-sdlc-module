# T-2026-10-27-007 — Redesign 3.5: npx riskrails (bin/riskrails.js) replaces install.sh, plugin manifests for both runtimes, hook entries switched to ai-guard.py, guard shims and the five install shell suites deleted, npm publish/version denied; version 3.0.0

feature · full · started 2026-10-27T21:14:12Z · claude

## Weight

```
scope          2  install.sh referenced from 256 files
behaviour      2  changes install (C6): what lands in ~/.claude/settings.json, hooks.json, config.toml (declared)
reversibility  0  git revert returns everything
domain         1  installer merges user settings; adds an npm deny (declared)
novelty        2  package.json is a dependency manifest; hint +1
coverage       1  5 of 6 code files have a test
W 8 → full   hints novelty +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/install_harness.py, tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, package.json, bin/riskrails.js, install.sh, tests/test-install-dry-run.sh, tests/test-dual-runtime-install.sh, tests/test-codex-install.sh, tests/test-profiles.sh, tests/test-shared-tree.sh, tests/run-all.sh, settings.common.json, codex/hooks.json, hooks/ai-git-guard.sh, hooks/ai-path-guard.sh, hooks/ai-scope-guard.sh, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_end_to_end.py, tests/test_guard_characterization.py, tests/test-guard-characterization.sh, .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, .agents/plugins/marketplace.json, hooks/hooks.json, hooks/codex-hooks.json, tests/test_install_routes.py, hooks/guard/git.py, hooks/ai-git-guard-defaults.json, tests/fixtures/guard-characterization/golden.txt, README.md, tests/test-scaffold-idempotency.sh, .ai/project/known-risks.md, tests/guard_harness.py, tests/test_merge_migration.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py, tests/test-runtime-gate-fable.sh, hooks/ai-path-guard-defaults.json, hooks/guard/common.py, skills/ai-task/sensors.py, skills/ai-task/state.py, .ai/policies/testing.md
tests: tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, tests/test_suite_parity.py, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_guard_characterization.py, tests/test_install_routes.py, tests/test_guard_differential.py, tests/test_scaffold_idempotency.py
- s1 · tests/install_harness.py, tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py · tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, tests/test_suite_parity.py · done
- s2 · package.json, bin/riskrails.js, install.sh, tests/install_harness.py, tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, tests/test-install-dry-run.sh, tests/test-dual-runtime-install.sh, tests/test-codex-install.sh, tests/test-profiles.sh, tests/test-shared-tree.sh, tests/run-all.sh · tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, tests/test_suite_parity.py · done
- s3 · settings.common.json, codex/hooks.json, bin/riskrails.js, hooks/ai-git-guard.sh, hooks/ai-path-guard.sh, hooks/ai-scope-guard.sh, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_end_to_end.py, tests/test_guard_characterization.py, tests/test-guard-characterization.sh, tests/install_harness.py, tests/test_install_dry_run.py, tests/test_dual_runtime_install.py, tests/test_codex_install.py, tests/test_profiles.py, tests/test_shared_tree.py, tests/run-all.sh · tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_scope_guard.py, tests/test_guard_characterization.py, tests/test_install_dry_run.py, tests/test_codex_install.py, tests/test_dual_runtime_install.py · done
- s4 · .claude-plugin/plugin.json, .claude-plugin/marketplace.json, .codex-plugin/plugin.json, .agents/plugins/marketplace.json, hooks/hooks.json, hooks/codex-hooks.json, bin/riskrails.js, package.json, tests/test_install_routes.py, tests/install_harness.py · tests/test_install_routes.py, tests/test_install_dry_run.py, tests/test_codex_install.py · done
- s5 · hooks/guard/git.py, hooks/ai-git-guard-defaults.json, tests/fixtures/guard-characterization/golden.txt, tests/test_ai_git_guard.py, tests/test_guard_characterization.py · tests/test_ai_git_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py · done
- s6 · README.md, tests/test-scaffold-idempotency.sh, tests/run-all.sh, .ai/project/known-risks.md · tests/test_scaffold_idempotency.py, tests/test_suite_parity.py · done
amended 2026-10-27T21:27:44Z: +tests/guard_harness.py — s3: the shims are gone, so the guard suites run 'python3 -I -S hooks/ai-guard.py --only <check>' (the shims' exact command); run() must take a command list
amended 2026-10-27T21:42:28Z: +tests/test_merge_migration.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py, tests/test-runtime-gate-fable.sh — whole-suite verify (run 9): these four still run 'bash install.sh', now the npx wrapper that exits 2; they switch to 'node bin/riskrails.js', nothing else changes
amended 2026-10-27T22:21:22Z: +hooks/ai-path-guard-defaults.json — Review pass 1 (blockers_open), re-plan of s4 accepted by the human: H2 — the plugin route moves the guard code and state.py into <home>/plugins/cache/<m>/riskrails/<ver>/, which no protected pattern covers; the plugin cache dir joins protected_config_patterns and installed_plugins.json joins task_protected_patterns. Same batch fixes B1 (skills keep scripts, only SKILL.md withheld), H1 (plugin active only when recorded user-scope and enabled), M1, M2, L2, L5, L6 in bin/riskrails.js and, accepted too, M3/L1 in hooks/guard/git.py.
amended 2026-10-27T22:53:31Z: +hooks/guard/common.py, skills/ai-task/sensors.py, skills/ai-task/state.py, .ai/policies/testing.md — Review pass 1, human asked to fix the remaining findings: L3 — runtime_hook_config must search the home whose plugin cache holds the guard first (common.py); L4 — stale references to the deleted shims and 'install.sh' in sensors.py/state.py docstrings and messages and in testing.md's suite rows

## Questions

[questions.md](questions.md) — 0 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | afbfe162d | .ai/state/logs/T-2026-10-27-007/step-1.log | no |
| 2 | step | 0 | cb34e23a0 | .ai/state/logs/T-2026-10-27-007/step-2.log | no |
| 3 | step | 1 | 264fac431 | .ai/state/logs/T-2026-10-27-007/step-3.log | no |
| 4 | step | 0 | 5911b4ffe | .ai/state/logs/T-2026-10-27-007/step-4.log | no |
| 5 | step | 0 | 2522e7124 | .ai/state/logs/T-2026-10-27-007/step-5.log | no |
| 6 | step | 1 | 005dc4faf | .ai/state/logs/T-2026-10-27-007/step-6.log | yes |
| 7 | step | 0 | 3f7b0e9a6 | .ai/state/logs/T-2026-10-27-007/step-7.log | no |
| 8 | step | 0 | fe452915a | .ai/state/logs/T-2026-10-27-007/step-8.log | no |
| 9 | suite | 1 | fe452915a | .ai/state/logs/T-2026-10-27-007/suite-9.log | no |
| 10 | step | 1 | 7edc544a4 | .ai/state/logs/T-2026-10-27-007/step-10.log | no |
| 11 | step | 0 | c0ecaed85 | .ai/state/logs/T-2026-10-27-007/step-11.log | no |
| 12 | suite | 0 | c0ecaed85 | .ai/state/logs/T-2026-10-27-007/suite-12.log | no |
| 13 | e2e | 0 | c0ecaed85 | .ai/state/logs/T-2026-10-27-007/e2e-13.log | no |
| 14 | step | 2 | 766e1d4de | .ai/state/logs/T-2026-10-27-007/step-14.log | yes |
| 15 | step | 1 | 766e1d4de | .ai/state/logs/T-2026-10-27-007/step-15.log | yes |
| 16 | step | 1 | 2e9e93da3 | .ai/state/logs/T-2026-10-27-007/step-16.log | no |
| 17 | step | 0 | 72908b4cc | .ai/state/logs/T-2026-10-27-007/step-17.log | no |
| 18 | suite | 0 | 592c2da2f | .ai/state/logs/T-2026-10-27-007/suite-18.log | no |
| 19 | e2e | 0 | 592c2da2f | .ai/state/logs/T-2026-10-27-007/e2e-19.log | no |
| 20 | step | 1 | 48f36c771 | .ai/state/logs/T-2026-10-27-007/step-20.log | yes |
| 21 | step | 0 | ee9ff6d77 | .ai/state/logs/T-2026-10-27-007/step-21.log | no |
| 22 | suite | 0 | ee9ff6d77 | .ai/state/logs/T-2026-10-27-007/suite-22.log | no |
| 23 | e2e | 0 | ee9ff6d77 | .ai/state/logs/T-2026-10-27-007/e2e-23.log | no |
| 24 | suite | 0 | 12a8550a8 | .ai/state/logs/T-2026-10-27-007/suite-24.log | no |
| 25 | e2e | 0 | 12a8550a8 | .ai/state/logs/T-2026-10-27-007/e2e-25.log | no |

suite passing · e2e passing · suite runs 5

## Review

### Pass 1 — STRONG, blockers_open

```
## FINDINGS

- [BLOCKER] B1 `bin/riskrails.js:956`, `bin/riskrails.js:1226` (`retireOwnSkills`) together with `skills/rr-build/SKILL.md:13-16` (the same loop is in rr-plan, rr-review, rr-ship, rr-setup and rr-spec). On the plugin route, npx moves every `~/.claude/skills/<name>` (and the Codex ones) into backups. The skills then look for their install root with `for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do [ -d "$AI_HOME/skills/rr-build" ] && break; done`. Neither directory has the skill any more, so the loop ends on `~/.codex`, and `STATE=python3 ~/.codex/skills/ai-task/state.py` fails with "can't open file … [Errno 2]", exit 2. I ran this on a scratch plugin-route home. Every `rr-*` skill and `$AI_HOME/riskrails/ai-path` breaks on the route README.md:141 documents ("/plugin install riskrails … Run npx riskrails as well"). `tests/test_install_routes.py` compares skill-tree hashes, so it never notices that a skill cannot find its own scripts. · in_scope: yes

- [HIGH] H1 `bin/riskrails.js:811-820` (`pluginCache`). Any version directory under `<home>/plugins/cache/*/riskrails/` counts as an active plugin. Nothing checks `installed_plugins.json`, `enabledPlugins` or the install scope. Scenario: a plugin that is disabled, installed at project scope, or uninstalled with its cache left behind. Run npx and it deletes every one of its own hook entries, `ai-guard.py` included ("removed: the hook entries the riskrails plugin now runs"), and retires all skills. Result: no git, path or scope guard in any project. Verified: after an npx install, I created a bare `plugins/cache/mkt/riskrails/3.0.0/hooks/hooks.json` and re-ran npx; `settings.json` ended with `hooks: {}` and an empty `skills/`. · in_scope: yes

- [HIGH] H2 `hooks/ai-path-guard-defaults.json` (`protected_config_patterns`). The plugin route moves the guard code, its hook registration and `state.py` to `~/.claude/plugins/cache/<m>/riskrails/<ver>/`, and no protected pattern covers that path. In a `.ai/` project, the full guard allows each of these: Edit of `…/plugins/cache/…/hooks/guard/git.py`, Edit of `…/skills/ai-task/state.py`, Write of `…/hooks/ai-guard.py`, Edit of `…/hooks/hooks.json`, and `sed -i … …/hooks/guard/git.py`. It denies the same edits to `~/.claude/hooks/guard/git.py` and `~/.claude/skills/ai-task/state.py`. Verified by running both through `hooks/ai-guard.py`. On this route an agent can disable the guard or the human-approval path in `state.py`. The fix needs a file outside the plan's list, so it is a SCOPE_CHANGE. · in_scope: yes

- [MEDIUM] M1 `bin/riskrails.js:962-985`, `:1237-1247`. With an invalid `settings.json` (`{"a": 1,, }`), npx prints "not valid JSON; left alone", then "merged: settings.json" and "Done (Claude Code).", and exits 0. It also retires the three shims, and no guard is registered. HEAD's `install.sh` exited 5 on the same file (jq parse error, verified from a `git archive HEAD` copy). The new known-risks entry says "Same tree, different message", but the exit code changed too. A scripted install now reports success with no guards in place. · in_scope: yes

- [MEDIUM] M2 `bin/riskrails.js:817`. The plugin version is the bytewise-last directory name, so `3.9.0` sorts after `3.10.0`. Verified: with both present, npx printed "riskrails 3.9.0 (mkt)" and read the stale directory's `hooks.json`. Hooks the old file lacks get registered a second time by npx, or hooks it has that the live version dropped are left out. Claude Code keeps the previous version directory for a while after an update. · in_scope: yes

- [MEDIUM] M3 `hooks/guard/git.py:51-52`. I confirm every case you listed: allowed are `npm publish;`, `npm 'publish'`, `npm --workspace a version minor`, `npm version --no-git-tag-version patch`, `npm pkg set version=9.9.9`, `pnpm publish`, and the correct ones are correct. Also allowed, all verified through the guard: `npm publish&&echo`, `/usr/bin/npm publish` (the cheap prefilter needs `npm` after a blank or operator), `npm -w a version patch`, `npm version -m "x" patch`, and npm 9.2.0's abbreviations and alias, `npm publ` / `npm vers patch` / `npm verison patch`. I checked that npm resolves them with `npm publ --help` → "Publish a package" and `npm vers --help` → "Bump a package version". The first two are the realistic agent forms. A version bump with a flag before the new version contradicts the s5 decision, which allows "bare `npm version` and its flags" and nothing more. It is not HIGH because plain `npm publish` and `npm version <new>` are caught, and publishing still needs the human's 2FA token. · in_scope: yes

- [LOW] L1 `hooks/guard/git.py:51`. Harmless commands are denied: `npm run publish`, `npm install publish`, `npm search publish`, `npm help publish`, `npm --dry-run publish`, and a double-quoted `echo "… npm publish …"`. It fails closed, but a project with a `publish` script cannot run it. · in_scope: yes

- [LOW] L2 `bin/riskrails.js:767`. `SHIM_RE` is not anchored at the end. A user's own `/opt/mine/hooks/ai-scope-guard.sh.wrapper` entry was removed from `settings.json` (verified). Anchor it on the closing quote or end of the command. · in_scope: yes

- [LOW] L3 `hooks/guard/common.py:526` together with the Codex plugin route (reasoned, not run). `runtime_hook_config` looks in `hook_dir` first, then `~/.claude/hooks`, then `~/.codex/hooks`. In the plugin cache, `hook_dir` has no `ai-git-guard.json`. So on the Codex plugin route, with both runtimes installed, Claude's copy of the git-guard config wins over Codex's. On the npx route the Codex guard reads its own copy, so the two routes behave differently. · in_scope: yes

- [LOW] L4 Stale references to the deleted shims and to `bash install.sh`, none of them executed: `README.md:621,652`; `hooks/ai-git-guard-defaults.json:2` (`_comment`); `.ai/policies/testing.md:143` (`hooks/ai-*-guard.sh` row); `skills/ai-task/sensors.py:188`, `skills/ai-task/state.py:2010`; `tests/test_shared_prompts_model_free.py:9`, `tests/test_merge_migration.py:8` (docstrings). · in_scope: yes

- [LOW] L5 `bin/riskrails.js:586-597`, `:1186-1196`. The dry run does not mention retiring the shims or retiring every skill on the plugin route; it prints only `retire: skills/status`. Its `hooks:` line lists `hooks.json`, `codex-hooks.json`, `AGENTS.md` and `CLAUDE.md`, none of which are installed. · in_scope: yes

- [LOW] L6 `bin/riskrails.js:798-801`. A hooks event value that is valid JSON but not an array (`"PreToolUse": {}`) throws a TypeError with a stack trace after the backup is taken. A `settings.json` of `[]` is replaced wholesale by the snippet. · in_scope: yes

- [INFO] I1 Not verified by execution: whether Codex expands `${CLAUDE_PLUGIN_ROOT}` in `hooks/codex-hooks.json` (the codex 0.164.0 binary contains the string `CLAUDE_PLUGIN_ROOT`, consistent with support); whether older Claude Code versions accept `.claude-plugin/plugin.json` naming the standard `hooks/hooks.json` (installed 2.1.312 logs "names the standard hooks/hooks.json, which loads on its own; loaded once"; older ones may reject it as a duplicate). · in_scope: yes

- [INFO] I2 The installer still ignores `CLAUDE_CONFIG_DIR` and `CODEX_HOME` (only `CLAUDE_DIR`, `CODEX_DIR`, `--home` and `--codex-home`), the same as HEAD's `install.sh`. The hooks and the plugin cache do honour `CLAUDE_CONFIG_DIR`. This was there before the change; it belongs in documentation, not this task. · in_scope: yes

## VERDICT
verdict: blockers_open
scope_assessment: The change stays within the plan's files. The plugin route (s4) is incomplete, though: it breaks skill path resolution (B1), switches every guard off on a cache directory alone (H1), and leaves the moved guard code unprotected (H2). Fixing H2, and probably B1, needs files outside the step lists (`hooks/ai-path-guard-defaults.json`, `skills/rr-*/SKILL.md`), so those fixes need SCOPE_CHANGE_REQUIRED.
```

### Pass 2 — STRONG, pass

```
## FINDINGS
- [MEDIUM] M4 `bin/riskrails.js:681-693`, `:919-923`. **Introduced by the B1 fix; reasoned, not run.** On the plugin route each skill is now split in two. Its `SKILL.md` comes from the plugin cache, which `/plugin update` refreshes. Its scripts (`state.py`, `sensors.py`, `ai-path`, `update.py`) come from the npx copy under `~/.claude/skills/`, which changes only when npx runs again. The guard also runs from the cache. Nothing checks that the two versions match: `pluginLine` prints `plugin.version` and never compares it with `PLUGIN_VERSION` (`:280-281`). README:141-143 tells the user to run `npx riskrails@3.0.0`, a pinned version, so following it after a plugin update reinstalls the old scripts. Scenario: the plugin updates to a 3.x whose SKILL.md calls a new `state.py` subcommand or writes a new state shape. The skill then fails against the 3.0.0 `state.py`, the same kind of breakage as B1. Nothing is wrong today because 3.0.0 is the only version. Suggested direction: warn, or stop, when `plugin.version !== PLUGIN_VERSION`, and say in the README that npx must run again at the plugin's version after each plugin update. · in_scope: yes
- [LOW] L7 `bin/riskrails.js:584-585`, `:1258-1259`. **L5 is only partly closed; verified.** On a plugin-route home the dry run still prints the whole `settings.json` snippet with its hooks (Claude) and every `codex/hooks.json` entry under "merged into …/hooks.json" (Codex). Apply registers none of those hooks (the Codex `hooks.json` ends up `{"hooks": {}}`). The `plugin:` line contradicts the block printed just above it. Also, the Codex `hooks:` line leaves out `guard/*.py`, `lib/ai-hook-common.sh` and the two `*-defaults.json` files that apply installs (`:1278-1281`). · in_scope: yes
- [INFO] I3 **Plugin-route-only ways to switch the guard off for later sessions; verified through the plugin-cache `ai-guard.py`, no task in flight.** All of these are allowed: `claude plugin disable riskrails@riskrails`; a Write to `~/.claude/plugins/known_marketplaces.json`; a Write to `~/.claude/plugins/marketplaces/riskrails/hooks/guard/git.py` (the source the next update copies from). On the npx route nothing equivalent exists: the hook entries sit in `settings.json`, which is frozen during a task. A related case, reasoned: a user who disables the plugin after npx has run is left with no guard and no `SKILL.md` until npx runs again, because npx's detection is a snapshot. Both need deliberate action, which is outside the mistake threat model in `.ai/policies/safety.md`. They belong in `known-risks.md`, not in a remediation. · in_scope: yes
- [INFO] I4 `(npm publish)`, `$(npm publish)` and `` `npm publish` `` are allowed, verified. The git rules behave the same way: `(git push --force origin main)` is allowed too, because the boundary class `(^|[|;&[:space:]])` has no `(` or backtick. So `cd <cache>/hooks/guard && sed -i … git.py` is allowed on the plugin cache, and the same command against `~/.claude/hooks/guard` is allowed on the npx route. This class of gap was there before this task and is the same on both routes. Not raised as new. · in_scope: yes
- [INFO] closed: B1. Reproduced on scratch homes: npx install, then `make_plugin_cache` (user scope, enabled), then npx again, for both Claude and Codex. The rr-build loop resolves `AI_HOME` to `<home>/.claude` (or `.codex`). `state.py --help` exits 0, and `ai-path policies/safety.md` exits 0 when run from a `.ai/` project. The skill folders keep every script and lose only `SKILL.md`. `test_install_routes.py::assertSkillsResolve` now pins this.
- [INFO] closed: H1. `claudePlugin` (`riskrails.js:831-844`) needs a user-scope entry in `installed_plugins.json`, `enabledPlugins[key] === true` and an existing `installPath`. `codexPlugin` needs an enabled `[plugins."riskrails@m"]` table. The format matches the real `installed_plugins.json` (v2, an array of entries, `scope`/`installPath`, all under `plugins/cache`), read only. `test_a_cache_alone_is_not_an_active_plugin` passes: cache only (pass 1's scenario), project scope and disabled for Claude, cache only and disabled for Codex. My hand re-run of pass 1's bare-cache scenario was refused by the live path guard (a `cp` into a `.claude/plugins` path while the task is in flight). I did not work around it, so this one rests on the test, which I ran on the current tree.
- [INFO] closed: H2. The cached `ai-guard.py` denies, for both the Claude and the Codex cache: Edit of `hooks/guard/git.py`, also as `//` and `/./` path variants; Edit of `skills/ai-task/state.py`; `sed -i` on the cached guard and on `codex-hooks.json`; `cp` into the cache, and `echo >` the plugin's `hooks.json`; `mv` of the version folder and of the marketplace folder; `rm -rf` of `…/cache/riskrails`, `…/cache` and `~/.codex/plugins`. The npx-route guard also denies an Edit in the Claude cache. With `CLAUDE_CONFIG_DIR=<home>/cfg`, Edits of `cfg/plugins/cache/mkt/riskrails/…/git.py` and `…/state.py` are denied, because `paths.py:658-661` anchors that directory as `.claude/`. Read stays allowed. `test_ai_path_guard.py -k test_21` passes.
- [INFO] closed: M1, L6. `checkHomeJSON` (`riskrails.js:939-957`) runs before either runtime is touched and exits 5. `test_an_unreadable_home_file_stops_before_any_change` passes: 5 bad shapes × 2 runtimes, the file unchanged, the shim not retired, no `agents/` created. Not re-run by hand: a redirect into `.claude/settings.json` is refused during the task.
- [INFO] closed: M2. Claude takes `installPath` from the registry. Codex uses `compareVersions` (`:847-855`). `test_the_plugin_version_is_the_numerically_latest` passes.
- [INFO] closed: M3. All 11 forms pass 1 listed are now denied, verified through `hooks/ai-guard.py`: `npm publish;`, `npm 'publish'`, `--workspace a version minor`, `version --no-git-tag-version patch`, `publish&&echo`, `/usr/bin/npm publish`, `-w a version patch`, `version -m "x" patch`, `publ`, `vers patch`, `verison patch`. Also denied: `env`/`sudo`/`NODE_ENV=x npm publish`, `npm -C pkg publish`, `--registry https://r publish`. `npm ver` is not an npm 9.2.0 command, so allowing it is correct.
- [INFO] closed: L1. Verified: `npm run publish`, `npm install publish`, `npm help publish`, `npm --prefix pkg run publish`, `npm run version`, `npm view … version`, bare `npm version` and `npm version --json` are all allowed. `npm --dry-run publish` and the double-quoted echo are still denied; `known-risks.md` accepts both.
- [INFO] closed: L2. `SHIM_RE` now has the lookahead `(?=["'\s]|$)`. `test_foreign_keys_survive` asserts that `/opt/mine/hooks/ai-scope-guard.sh.wrapper` survives.
- [INFO] closed: L3. `common.py:523-536` searches the Codex home first when the realpath of `hook_dir` lies under the Codex home, and otherwise keeps the old order. Your probe showed the test fails without the fix. It passes on the current tree (`test_ai_git_guard.py`, 6/6). One contrived ordering edge remains: `CODEX_HOME` set to an ancestor of the Claude home. Not raised.
- [INFO] closed: L4. None of the listed files names a shim or `install.sh` any more. README:140 mentions `./install.sh` on purpose, to say it now only prints the `npx` line. The remaining mentions (`skills/usage-report/usage-report.py:24,613`, `docs/**`, shipped messages) are recorded in `known-risks.md` with owner 3.6.
- [INFO] partly closed: L5. The `hooks:` line no longer names `hooks.json`/`codex-hooks.json`/`AGENTS.md`/`CLAUDE.md`. The shim-retire line and the `(without SKILL.md …)` note are there. What is still wrong is L7 above.
- [INFO] I1 and I2 are still open as documented (`known-risks.md`, README Install section). The fixes did not make them worse.

## VERDICT
verdict: pass
scope_assessment: The fixes stay inside the amended plan: path-guard defaults for H2, `bin/riskrails.js` for B1, H1, M1, M2, L2, L5 and L6, `hooks/guard/git.py` for M3 and L1, and `common.py`, `sensors.py`, `state.py` and `testing.md` for L3 and L4. Every pass-1 finding with in_scope yes closes against the current tree. I re-ran `test_install_routes` (9), `test_ai_git_guard` (6) and `test_ai_path_guard -k test_21` here, all green. The B1 fix brought in a SKILL.md/script version-skew risk on plugin updates (M4) and left the plugin-route dry run partly inaccurate (L7). Neither moves the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .agents/plugins/marketplace.json | +20 −0 | New |
| .ai/policies/testing.md | +5 −6 | Edit |
| .ai/project/known-risks.md | +18 −0 | Edit |
| .claude-plugin/marketplace.json | +21 −0 | New |
| .claude-plugin/plugin.json | +21 −0 | New |
| .codex-plugin/plugin.json | +13 −9 | Edit |
| README.md | +54 −32 | Edit |
| bin/riskrails.js | +1375 −0 | New |
| codex/hooks.json | +3 −25 | Edit |
| hooks/ai-git-guard-defaults.json | +1 −1 | Edit |
| hooks/ai-git-guard.sh | +0 −14 | Delete |
| hooks/ai-path-guard-defaults.json | +4 −2 | Edit |
| hooks/ai-path-guard.sh | +0 −15 | Delete |
| hooks/ai-scope-guard.sh | +0 −15 | Delete |
| hooks/codex-hooks.json | +103 −0 | New |
| hooks/guard/common.py | +9 −3 | Edit |
| hooks/guard/git.py | +20 −2 | Edit |
| hooks/hooks.json | +122 −0 | New |
| install.sh | +14 −1260 | Edit |
| package.json | +15 −0 | New |
| settings.common.json | +3 −25 | Edit |
| skills/ai-task/sensors.py | +1 −1 | Edit |
| skills/ai-task/state.py | +5 −5 | Edit |
| tests/guard_harness.py | +9 −2 | Edit |
| tests/install_harness.py | +73 −0 | New |
| tests/run-all.sh | +2 −5 | Edit |
| tests/test-codex-install.sh | +0 −310 | Delete |
| tests/test-dual-runtime-install.sh | +0 −163 | Delete |
| tests/test-guard-characterization.sh | +0 −383 | Delete |
| tests/test-install-dry-run.sh | +0 −403 | Delete |
| tests/test-profiles.sh | +0 −101 | Delete |
| tests/test-runtime-gate-fable.sh | +21 −21 | Edit |
| tests/test-scaffold-idempotency.sh | +0 −158 | Delete |
| tests/test-shared-tree.sh | +0 −241 | Delete |
| tests/test_ai_git_guard.py | +45 −2 | Edit |
| tests/test_ai_path_guard.py | +35 −2 | Edit |
| tests/test_ai_scope_guard.py | +2 −2 | Edit |
| tests/test_codex_install.py | +608 −0 | New |
| tests/test_dual_runtime_install.py | +246 −0 | New |
| tests/test_end_to_end.py | +8 −9 | Edit |
| tests/test_install_dry_run.py | +757 −0 | New |
| tests/test_install_routes.py | +330 −0 | New |
| tests/test_instruction_budget.py | +6 −6 | Edit |
| tests/test_merge_migration.py | +3 −3 | Edit |
| tests/test_profiles.py | +194 −0 | New |
| tests/test_shared_prompts_model_free.py | +4 −4 | Edit |
| tests/test_shared_tree.py | +331 −0 | New |

+4501 −3230 lines, 47 files

## Verdict

close: closed
facts: (a) green — suite green on 12a8550a8 (run 24) · (b) green — 47 changed files, all in the task's files
gate: requested G1 at 2026-10-27T23:13:45Z; approved by vanssa at 2026-10-27T23:15:19Z via terminal
confirm: none
handoffs: 19 · suite runs: 5 · review passes: 2
