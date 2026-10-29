# Questions — T-2026-10-28-001
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. The attended half needs your hands: run the two TUI recordings in /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/36a45d76-b246-4982-a232-23bf59984303/scratchpad/spike/HUMAN.md (Claude: AskUserQuestion x4, Stop, optional /login; Codex: request_user_input with and without --enable default_mode_request_user_input, hooks trusted via /hooks). Which do you run?
asked: 2026-10-28T10:56:26Z · stage: implementation
context: docs/dialog-spike.md: Open
A. both, then say 'recorded' (recommended)
B. Claude only; Codex gets codex/NEGATIVE.md from the measured flag fact (default_mode_request_user_input off by default)
C. neither; the task closes with the three print-mode fixtures and the ask-*/auth/codex items stay Open in docs/dialog-spike.md
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T10:57:54Z

## Q2. /rr-ship was called but the recording directory holds no TUI payloads yet (only the 18 print-mode files). Q1=A said both recordings are part of this task. Ship without them, or record first?
asked: 2026-10-28T10:59:09Z · stage: implementation
context: scratchpad/spike/out: 18 files, none newer than the print-mode run
A. record first — run HUMAN.md now; I stage, finish the doc, verify once, then close (recommended)
B. ship as is — the three print-mode fixtures and docs/dialog-spike.md with ask-*, auth_success and Codex marked Open (Codex gets NEGATIVE.md from the flag fact); supersedes Q1=A
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T11:00:07Z

## Q3. No Codex session ran for the spike: the only rollout today is from 00:26, before the task, and ~/.codex/config.toml holds no trust entry for the spike hooks. Run the Codex half now, or close Codex on the measured facts?
asked: 2026-10-28T11:07:26Z · stage: implementation
context: docs/dialog-spike.md: Codex section; plan P13
A. run it now — HUMAN.md section B (two sessions, /hooks trust first), then say 'recorded' (recommended)
B. NEGATIVE.md now — version 0.164.0, request_user_input outside plan mode only behind the under-development flag default_mode_request_user_input (off by default); hook firing for the tool stays UNKNOWN; dialog.tool null for Codex (OQ3 negative)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T11:17:04Z
