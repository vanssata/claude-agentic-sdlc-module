# T-2026-10-31-1841-ship-the-whole-two-line — Ship the whole two-line statusline with the plugin: runtime-gate statusline renders the model, effort and context line (--context) and a second line (--line: user@host:cwd | branch | 5h/7d limits | cost); every install and update writes it, replacing a user's own statusLine unless --statusline own

feature · full · started 2026-10-31T18:41:50Z · claude

## Weight

```
scope          2  hooks/runtime-gate.py matches hot_paths hooks/**
behaviour      2  changes what the installer writes into the user's settings.json statusLine (replaces a user's ow
reversibility  0  git revert returns everything
domain         0  developer tooling, no money, identity or personal data (declared)
novelty        1  a second line renderer is new; the wrapper and the installer's statusLine merge exist (declared)
coverage       1  1 of 2 code files have a test
W 6 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-31T18:41:50Z — skills/CLAUDE.md and hooks/CLAUDE.md: a change to install runs full: STRONG review and the gate

## Plan

files: hooks/runtime-gate.py, bin/riskrails.js, tests/test_runtime_gate.py, tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_install_routes.py, docs/installation.md, docs/hooks.md, README.md, /home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1841.md
tests: tests/test_runtime_gate.py, tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_install_routes.py
- s1 · hooks/runtime-gate.py, tests/test_runtime_gate.py, tests/test_runtime_gate_fable.py · tests/test_runtime_gate.py, tests/test_runtime_gate_fable.py · done
- s2 · bin/riskrails.js, tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_install_routes.py · tests/test_runtime_gate_fable.py, tests/test_install_dry_run.py, tests/test_install_routes.py · done · after s1
- s3 · docs/installation.md, docs/hooks.md, README.md · no tests · done · after s2
amended 2026-10-31T18:53:00Z: +/home/vanssa/.claude/jobs/cf6a72cf/tmp/review-1841.md — the STRONG review's report is ~8 KB; the Bash guard refuses it inline and state.py review --report needs a file

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-31-1841-ship-the-whole-two-line for implementation? (gate: human_approval)
asked: 2026-10-31T19:01:59Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-31T19:06:49Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | a097cd0de | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-1.log | yes |
| 2 | step | 1 | c4f4bb229 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-2.log | no |
| 3 | step | 1 | e60199b21 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-3.log | yes |
| 4 | step | 1 | 5af50164a | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-4.log | no |
| 5 | step | 0 | 51aef4bb0 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-5.log | no |
| 6 | suite | 0 | a28eb4069 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/suite-6.log | no |
| 7 | e2e | 0 | a28eb4069 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/e2e-7.log | no |
| 8 | step | 1 | 883056720 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-8.log | yes |
| 9 | step | 1 | a3780a9fc | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-9.log | no |
| 10 | step | 1 | aa3da5884 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-10.log | no |
| 11 | step | 0 | 79343600e | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/step-11.log | no |
| 12 | suite | 0 | a91e673f3 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/suite-12.log | no |
| 13 | e2e | 0 | a91e673f3 | .ai/state/logs/T-2026-10-31-1841-ship-the-whole-two-line/e2e-13.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, blockers_open

```
## FINDINGS

- [BLOCKER] B1 The "your old command is kept in the settings.json backup" promise only holds on the first install of a day. The documented undo, `--statusline own`, then overwrites that only copy and does not bring the command back (`bin/riskrails.js:1137` backupFile → `:727-735`, `:626-640`). in_scope: yes
  why it matters: `claudeApply` runs `backupFile(SETTINGS)` on every run, before `statuslineGate`. `backupFile` begins with `rmrf(bak)`, and its own comment says "A second run on the same day replaces that copy". The likely sequence: (1) the user runs `npx riskrails` and sees "replaced your statusline command: bash ~/.claude/statusline-command.sh (settings.json is in backups/2026-10-31/)". (2) The same day they run `npx riskrails --statusline own` to get it back. The backup now holds the already-replaced `… --context --line`. `statuslineGate` sees `ours`, and `tail()` strips both flags, so `rest=''`. It writes `PREFIX --context` with no `--then`, and reports "added the model and the context use to the statusline wrapper (your command is unchanged)". The user's command is now gone from settings.json and from the backup; it survives only in terminal scrollback. The human chose "always replace" because the dated backup was the safety net, and the docs make the same promise (`docs/installation.md:169` "the settings.json backup keeps it"). test_16 checks the backup before the re-install, never after it, so the suite cannot see this.
  suggested direction: Store the replaced command where a later run cannot overwrite it (a write-once record under `riskrails/`, or a backup that is written only if absent). Make `--statusline own` restore it as `--then` when the current command is exactly the plugin's. Pin it with a test: install, re-install the same day, then `--statusline own`, and the original command is back.

- [HIGH] H1 `--statusline own` is not remembered, so the documented update command silently undoes the opt-out every time (`bin/riskrails.js:64,96`; `hooks/update_notice.py:32`; `README.md:85`). in_scope: yes
  why it matters: `--plan` and `--context` are recorded in `riskrails/profile.json`, and `--yes` reuses them. `STATUSLINE` is never recorded. A user who chose `own` and then runs the update the update notice tells them to run (`npx -y riskrails@latest --yes`) reaches the `ours && !OWN && rest.startsWith('--then')` branch, and their wrapped command is replaced. The notice is surfaced to the agent too, so the replacement can happen inside an agent's tool output that the human never reads. Combined with B1, the backup is also lost after a second run that day. Nothing in installation.md or the usage text says `own` has to be passed again on every update.
  suggested direction: Record `statusline` in profile.json the way `context` is, and let a recorded `own` stand unless `--statusline riskrails` is given explicitly. Otherwise, document that the flag must be repeated.

- [LOW] L1 The messages are wrong when going from the plugin's statusline back to `own` (`bin/riskrails.js:636-639`). in_scope: yes
  why it matters: Applying `own` to `PREFIX --context --line` drops `--line` but reports "added the model and the context use … (your command is unchanged)". With `--statusline-context no` it reports only "removed the model and context line", although the prompt line is removed too. In both cases the user has no command to be "unchanged".
  suggested direction: Branch the message on whether `--line` was dropped and whether a `--then` command exists.

- [LOW] L2 The docs and usage text still describe the old `--statusline-context` behaviour, and the update section still says "wrapper" (`bin/riskrails.js:25-27`, `docs/installation.md:169`, `docs/installation.md:190`). in_scope: yes
  why it matters: "`--statusline-context no` adds nothing and removes nothing" is now false for Claude. Under the default it still writes `--line`, and it removes `--context` from an existing line, as test_16 asserts. The update list at installation.md:190 says "the statusline wrapper is rewritten"; in fact a user's command is replaced.
  suggested direction: Reword both to say what each flag does under `riskrails` and under `own`.

- [LOW] L3 No CHANGELOG entry for a default that replaces user config, and `npx riskrails@3.1.0 --statusline own` is shown although 3.1.0 rejects the flag (`README.md:128`, `docs/installation.md:37`; CHANGELOG.md has no Unreleased section). in_scope: yes (CHANGELOG is outside the plan's file list, so record it rather than widen the step)
  why it matters: Anyone who copies the README line today against the published 3.1.0 gets "unknown option: --statusline" and exit 2. The behaviour change that most affects users is not announced.
  suggested direction: Add an Unreleased/3.2.0 entry and bump the doc pins at release; this is a separate change.

- [INFO] I1 The off branch of `statuslineGate` cannot run (`bin/riskrails.js:651-662`). in_scope: yes
  why it matters: The only callers are `:695` (dry run) and `:1169` (apply), both with `'on'`. `'moved'` is set internally. `C.GATE==='off'` (Fable off, Pro plans) only drops the StopFailure hook (`:515`, `:1151`). So `--fable no` and Pro installs never delete or unwrap the statusline. The tail-regex change there cannot run, and it has no test.
  suggested direction: Leave it. Note it as dead code for a later cleanup task; do not remove it in this change.

- [INFO] I2 Any exception in `second_line` drops the whole second line, not just the faulty part (`hooks/runtime-gate.py:1222-1227`). in_scope: no
  why it matters: `json.loads` accepts `NaN`/`Infinity`. With `used_percentage: NaN`, `round()` raises ValueError and the cwd, branch and cost are all lost (I probed this: only the `--then` output remained). The fail-open contract holds: line 1 and `--then` are intact. Claude Code never sends NaN, so this is LOW at most inside the boundary.
  suggested direction: Use `math.isfinite` on `pct` and `cost`.

- [INFO] I3 Differences from the bash original (`hooks/runtime-gate.py:1135-1137,1203-1208`). in_scope: yes
  why it matters: Nothing on the shipped payload; listed for the record. Rounding matches: Python `round()` and glibc `printf '%.0f'` both round half to even on the binary value (12.5→12, 13.5→14, 2.5→2, probed); `%.2f` for the cost is identical. `%a` stays English, because Python never calls setlocale; bash forced `LC_TIME=C`. The differences: the effort is shown only when there is a model name; the user comes from `$USER`, where bash used `whoami`; the cwd fallback is the physical `getcwd`, not `pwd`; an epoch in milliseconds drops the reset time. A hung git now costs at most 2 s × 2 calls; the bash script had no timeout. A detached HEAD or a non-repo directory spawns git twice, the same as bash. A missing cwd is skipped (probed).
  suggested direction: None needed.

- [INFO] I4 The replaced command is echoed to stdout (`bin/riskrails.js:622,632,645`). in_scope: yes
  why it matters: A statusline command with an inline token (for example a `curl -H Authorization…`) is written into the terminal, and into an agent's context if an agent runs the installer. The human decision asked for it to be printed; noted for the risk register.
  suggested direction: None needed for this task.

## VERDICT
verdict: blockers_open
scope_assessment: The change stayed inside the plan's files; CHANGELOG (L3) is outside them and should go to a release task. The behaviour matches the human decision ("always replace", printed, backed up), with two exceptions. The backup half of that decision fails on any second same-day run, and the `own` escape hatch neither restores the command nor persists (B1, H1). Per CLAUDE.md, B1 closes only with a test that installs, re-installs the same day, then runs `--statusline own`, and finds the original command back.
```

### Pass 2 — STRONG, pass

```
## FINDINGS

- [MEDIUM] M1 The restore keeps happening on later runs, so a command the user deliberately removed comes back on the next update (`bin/riskrails.js:600,651`)  in_scope: yes
  why it matters: `replaced` is never cleared or marked as used. The rule is `restore = OWN && !rest && kept`, and it fires on every run where the mode is own and the plugin's line has no `--then`. Sequence: (1) a default install replaces X and records `replaced: X`; (2) `--statusline own` restores X; (3) the user removes the `--then 'X'` by hand (or uses Claude Code's `/statusline`) to keep only the quota check; (4) the next `npx -y riskrails@latest --yes` keeps own, sees a bare line and silently puts X back ("restored your statusline command…"). A second path breaks idempotence outright: start with `{mode: riskrails, replaced: X}` in the record and no `statusLine` in settings (the user deleted it); `--statusline own` adds the bare check, and the same command again restores X, so two identical runs give different results. This is the mirror image of H1: an update overrides something the user chose, and an agent can trigger it through the update notice.
  suggested direction: Make the restore one-shot: clear `replaced` (or record `restored_at`) once it has been restored, or restore only when `--statusline own` is given explicitly (STATUSLINE_GIVEN). Pin it with a test: own, remove `--then`, `--yes`, and the line stays bare.

- [LOW] L4 The record write on the fable-gate 'moved' path is not tested (`bin/riskrails.js:643`; `tests/test_runtime_gate_fable.py:560`)  in_scope: yes
  why it matters: test_15 now checks that the old wrapper becomes `--context --line`, but not that `my-line.sh` lands in `riskrails/statusline.json`. On that path the record is the only copy left after a second install the same day, which is the B1 failure, and nothing pins it.
  suggested direction: Add one `read_json(.../riskrails/statusline.json)["replaced"] == "my-line.sh"` assertion to test_15.

- [INFO] I5 What used to be only a message now goes into the record, and a malformed tail is stored as-is (`bin/riskrails.js:628-629`)  in_scope: no
  why it matters: When `shSplit` throws (an unterminated quote in a hand-edited `--then` tail), `wrapped()` returns the whole `--then …` string. Before the fix this only reached a message; now it becomes `replaced` and overwrites the earlier good command, and a later `own` would restore `--then '--then …'`. No session produces that tail, and Claude Code could not run it anyway. Inside the boundary this would be LOW.
  suggested direction: When the parse fails, save nothing (`''`) rather than `rest`.

- [INFO] I6 A record that can later become executable sits in a path the path guard does not protect (`hooks/ai-path-guard-defaults.json:44-48`)  in_scope: yes
  why it matters: `settings.json` is in task_protected_patterns, but `~/.claude/riskrails/statusline.json` is in no list. Writing `{mode: own, replaced: <cmd>}` there turns the next `--yes` update into a write of `<cmd>` into `statusLine`, which runs on every render. This does not widen what is already open: `hooks/runtime-gate.py` is not protected either, and an agent with Bash can write settings.json through node or python. So it is a note for the risk register.
  suggested direction: When the guard defaults are next reviewed, consider adding `(riskrails|claude-agentic)/statusline\.json` to protected_config_patterns.

## VERDICT
verdict: pass
B1 and H1 close against the real code, each pinned by an assertion that failed before the fix. The remediation adds M1, a restore that can run more than once and undo a later choice by the user, plus L4 and two INFO notes. None of them is a BLOCKER or HIGH.
scope_assessment: the remediation stayed inside `bin/riskrails.js` statuslineGate and its usage comments, `tests/test_runtime_gate_fable.py` and `docs/installation.md`, as the brief describes; no refactoring was mixed in.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +1 −0 | Edit |
| bin/riskrails.js | +88 −18 | Edit |
| docs/hooks.md | +5 −1 | Edit |
| docs/installation.md | +5 −2 | Edit |
| hooks/runtime-gate.py | +99 −8 | Edit |
| tests/test_runtime_gate.py | +44 −4 | Edit |
| tests/test_runtime_gate_fable.py | +72 −23 | Edit |

+314 −56 lines, 7 files

## Verdict

close: closed
facts: (a) green — suite green on a91e673f3 (run 12) · (b) green — 7 changed files, all in the task's files
gate: requested G1 at 2026-10-31T19:01:59Z; approved by Ivan Kakurov at 2026-10-31T19:06:49Z via terminal
confirm: none
handoffs: 7 · suite runs: 2 · review passes: 2
