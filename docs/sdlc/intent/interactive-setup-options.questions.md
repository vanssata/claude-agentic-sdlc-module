# Questions — interactive-setup-options
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Where should choosing plans and options become interactive?
asked: 2026-11-10T23:20:32Z · stage: intent
A. Both — the npx installer gets a terminal menu (runtime, plan, fable, context) and /rr-setup gets the native dialog for the project's options (survey depth, runtime, verify command, memory) (recommended)
B. Only the npx installer (terminal menu); /rr-setup keeps asking in prose
C. Only /rr-setup (native dialog); the installer keeps its typed prompts and flags
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-10T23:21:11Z

## Q2. Today 'memory enable [--index sqlite]' is the human's route: from an agent it exits 5 and must be typed in a terminal. How should /rr-setup configure memory and the SQLite index?
asked: 2026-11-10T23:21:11Z · stage: intent
A. A dialog question in /rr-setup — off / packages / packages + SQLite index; the human's pick runs 'memory enable' through the dialog route (as approve does), author and period prefilled from git and the default (recommended)
B. /rr-setup sets only the per-developer SQLite index (local, git-ignored) from the dialog; turning packages mode on stays a terminal command
C. No question — the SQLite index is on by default whenever packages mode is on and the SQLite build allows it; mode stays a terminal command
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-10T23:22:06Z

## Q3. docs/sdlc/specs/project-settings-dialog.md (settings registry, SETTINGS_MISSING gate on start, SessionStart detection) was specified on 2026-10-30 and never built; its modules/ layout does not exist in 4.0. How does this work relate to it?
asked: 2026-11-10T23:22:06Z · stage: intent
A. Small and standalone — reuse the R36 command-choice dialog as it is; /rr-setup shows its options as dialog picks that run existing commands; no registry, no gate on start; the old spec stays parked (recommended)
B. This spec supersedes project-settings-dialog — take its registry and SETTINGS_MISSING gate, re-derived for the 4.0 layout, and mark the old spec superseded
C. Build project-settings-dialog first as written, then add the installer menu and the memory question on top
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-10T23:23:50Z

## Q4. The installer (bin/riskrails.js) has zero npm dependencies and reads answers synchronously as typed text. What should its menu be?
asked: 2026-11-10T23:23:56Z · stage: intent
A. A built-in arrow-key menu (raw-mode stdin, no dependency): each plan on its own line with a one-line description, detected/previous plan preselected, Enter confirms; then fable, context and statusline the same way; flags, --yes and a non-TTY skip it unchanged (recommended)
B. A numbered list (type 1-6, Enter keeps the proposed one) — no raw mode, works in every terminal, same descriptions
C. Add a prompt library (@inquirer/prompts or similar) as the first dependency
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-10T23:27:18Z

## Q5. Which /rr-setup choices go into the dialog, and when is it shown?
asked: 2026-11-10T23:27:18Z · stage: intent
A. Four, in one dialog at the start of a fresh setup — runtime (auto/claude/codex/both), survey depth (light/full), verify_command (the survey's proposal / other), memory (off / packages / packages + SQLite); on an already set-up project only the ones not yet configured, plus '/rr-setup --options' to reopen all (recommended)
B. The same four, but only on a fresh setup; changing them later stays manual
C. Only memory + SQLite and survey depth; runtime and verify_command stay as they are today
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-10T23:58:57Z
