# Dialog probe

Nobody has run the approval dialog under Claude Code Remote Control, the
desktop app or the web. This is the checklist for the person who does, after
the release: fill one table per surface with `yes`, `no` or a note.

A `no` is not fixed here. It becomes the next spec.

Setup, on each surface: install the release (`npx riskrails@<version> --yes`),
restart the session, then in a repository with `.ai/` start a task whose mode
needs an approval, or open any decision (`state.py decision show` lists what is
open).

## Where each fact is read

- **Attended and session id.** The dialog is off when the session is reported
  unattended (`CLAUDE_CODE_SESSION_ATTENDED=0`) or the payload carries no
  session id; the switch is described in [hooks.md](hooks.md), lines 186-193,
  and read in `hooks/guard/dialog.py` (`effective_switch`).
- **The pick.** The consent ledger, `.ai/state/consent.jsonl`: a `pick` line
  after you answer, a `use` line once the picked command ran.
- **The decision.** `.ai/state/decision.json`, `state.py decision show`.
- **The statusline segment.** `hooks/runtime-gate.py` (`task_segment`).
- **`/rr-status`.** Its first line, "waiting on you".

## Remote Control

| Check | yes / no | Note |
|---|---|---|
| The session is reported attended (`CLAUDE_CODE_SESSION_ATTENDED` is not `0`) | | |
| The session carries a session id | | |
| The question dialog renders | | |
| Your pick is recorded in the consent ledger (a `pick` line) | | |
| The picked command then passes, once | | |
| A reply in the chat reaches the same session ("ask me again" sends the dialog again) | | |
| The statusline segment is visible (`waiting on you: D1`) | | |
| `/rr-status` shows "waiting on you" on its first line | | |

## Desktop app

| Check | yes / no | Note |
|---|---|---|
| The session is reported attended (`CLAUDE_CODE_SESSION_ATTENDED` is not `0`) | | |
| The session carries a session id | | |
| The question dialog renders | | |
| Your pick is recorded in the consent ledger (a `pick` line) | | |
| The picked command then passes, once | | |
| A reply in the chat reaches the same session ("ask me again" sends the dialog again) | | |
| The statusline segment is visible (`waiting on you: D1`) | | |
| `/rr-status` shows "waiting on you" on its first line | | |

## Web

| Check | yes / no | Note |
|---|---|---|
| The session is reported attended (`CLAUDE_CODE_SESSION_ATTENDED` is not `0`) | | |
| The session carries a session id | | |
| The question dialog renders | | |
| Your pick is recorded in the consent ledger (a `pick` line) | | |
| The picked command then passes, once | | |
| A reply in the chat reaches the same session ("ask me again" sends the dialog again) | | |
| The statusline segment is visible (`waiting on you: D1`) | | |
| `/rr-status` shows "waiting on you" on its first line | | |
