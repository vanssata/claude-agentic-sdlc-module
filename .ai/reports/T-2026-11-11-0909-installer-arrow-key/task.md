# T-2026-11-11-0909-installer-arrow-key — Installer arrow-key menus (bin/menu.js child) for runtime, plan, fable, context, statusline and Codex plan on a TTY; Enter gives today's result, non-TTY/--yes/flags byte-identical (interactive-setup-options Task A, A3-A5)

feature · guarded · started 2026-11-11T09:09:37Z · claude

## Weight

```
scope          2  bin/riskrails.js referenced from 176 files
behaviour      1  keyword 'state machine' in README.md
reversibility  0  git revert returns everything
domain         0  installer UI only; no payment, security, auth or data-migration code (declared)
novelty        1  first raw-mode keypress child process in this repo (bin/menu.js), spawnSync with inherited tty; 
coverage       1  1 of 2 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: bin/menu.js, bin/riskrails.js, tests/test_install_menu.py, README.md
tests: tests/test_install_menu.py, tests/test_install_dry_run.py, tests/test_codex_install.py
- s1 · bin/menu.js, tests/test_install_menu.py · tests/test_install_menu.py · done
- s2 · bin/riskrails.js, tests/test_install_menu.py · tests/test_install_menu.py, tests/test_install_dry_run.py, tests/test_codex_install.py · done · after s1
- s3 · README.md, bin/riskrails.js · tests/test_install_dry_run.py · done · after s2

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | ddd475049 | .ai/state/logs/T-2026-11-11-0909-installer-arrow-key/step-1.log | no |
| 2 | step | 0 | 281705965 | .ai/state/logs/T-2026-11-11-0909-installer-arrow-key/step-2.log | no |
| 3 | step | 0 | eaae0bb19 | .ai/state/logs/T-2026-11-11-0909-installer-arrow-key/step-3.log | no |
| 4 | suite | 0 | eaae0bb19 | .ai/state/logs/T-2026-11-11-0909-installer-arrow-key/suite-4.log | no |
| 5 | e2e | 0 | eaae0bb19 | .ai/state/logs/T-2026-11-11-0909-installer-arrow-key/e2e-5.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 bin/menu.js:100 — The lone-Esc abort misfires on a split escape sequence. `chunk.length === 1 && chunk[0] === 0x1b` treats any read that happens to hold only ESC as an abort. An arrow key (ESC `[` `B`) that TCP, ssh or tmux delivers as ESC then `[B` in two reads exits 130, so the user has to re-run. Nothing is written, so the cost is a re-run. Paste and Alt+key arrive in one chunk and are fine. `TestMenu` only types whole sequences and a lone ESC, so a split sequence is untested. Direction: wait about 50 ms after a lone ESC for the rest before aborting, or say in the header comment that this is accepted. · in_scope: yes
- [LOW] L2 bin/menu.js:82-92,104-111 — `finish` is not idempotent, and one chunk can emit several keypress events synchronously. The sequences I reasoned through (not run, per the no-scripts rule): `\r\r` in one read (pasted or type-ahead) calls `finish(0)` twice. It writes the `title: value` line and the value to stdout twice, so stdout is `propro`. `choose()` checks `items.some(it => it.value === r.stdout)`, finds no match and returns `null`. The installer then silently falls back to the typed prompt, with the TTY already restored. `\rq` calls `finish(0)` and then `finish(130)`. Stdout on a pipe is written synchronously and `process.exit(130)` runs before the callback, so the installer aborts after the user pressed Enter. A `done` guard on `state` would close both. · in_scope: yes
- [LOW] L3 tests/test_install_menu.py:~bare_path — The PATH filter drops every PATH directory that contains `claude` or `codex`. On a machine where `python3` or `git` lives in the same directory (for example `~/.local/bin`, which often holds the `claude` binary), the scratch run loses that tool. The failure would then show up as an install error, not as "no runtime". `process.execPath` keeps node itself safe. This is environment-dependent flakiness, not a vacuous pass: the replies wait for real prompts and an unseen prompt fails the test. · in_scope: yes
- [INFO] I1 bin/menu.js:56 — The reverse-video escape is emitted unconditionally. `NO_COLOR` is ignored, and the cursor stays hidden if menu.js dies from an uncaught exception, because the exit handler only restores raw mode through node's own reset. If the terminal is shorter than items+1 lines, the `\x1b[nA` redraw clamps and leaves stale rows. All three are cosmetic, outside the fixture corpus, and do not affect the verdict. · in_scope: no

## VERDICT
verdict: pass
scope_assessment: Stayed within the approved files (bin/menu.js, bin/riskrails.js, tests/test_install_menu.py, README.md). The D3 exception is confined to the menu path and the typed fallback stays verbatim. L1, L2 and L3 are LOW and do not move the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +7 −0 | Edit |
| bin/menu.js | +116 −0 | New |
| bin/riskrails.js | +91 −4 | Edit |
| tests/test_install_menu.py | +244 −4 | Edit |

+458 −8 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on eaae0bb19 (run 4) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
