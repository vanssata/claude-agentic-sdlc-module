# Questions — command-choice-dialog
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. What text does a selectable command option carry?
asked: 2026-10-27T21:59:18Z · stage: intent
A. the command itself, verbatim, as it will run (recommended)
B. a human label with the command hidden behind it
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T21:59:19Z

## Q2. While a human decision is pending (plan drift, approval), how is the model kept from skipping the dialog?
asked: 2026-10-27T21:59:18Z · stage: intent
A. PreToolUse denies every tool but the dialog and the settle command; Stop blocks until settled (recommended)
B. additionalContext instruction only, repeated on each UserPromptSubmit
C. instruction once at SessionStart
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T21:59:19Z

## Q3. askUserQuestionTimeout in settings.json?
asked: 2026-10-27T21:59:18Z · stage: intent
A. absent, never rendered by the installer (recommended)
B. set to 10m
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T21:59:19Z

## Q4. Which commands get the [ ] dialog?
asked: 2026-10-27T21:59:19Z · stage: intent
A. only commands the agent may not run itself (approve, commit, push, human_set) plus plan and review decisions (recommended)
B. every command that mutates files or git
C. every Bash command
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T22:17:46Z

## Q5. After the human picks a guarded command in the dialog, who runs it?
asked: 2026-10-27T21:59:19Z · stage: intent
A. the agent runs it; the gate moves into the harness (C5 amended; PostToolUse records the pick, the guards allow a one-shot verbatim match)
B. the agent prints a '! <cmd>' line and the human pastes it; C5 unchanged (recommended)
C. A for git commit, B for approve
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T22:17:46Z

## Q6. Codex when request_user_input is unavailable outside plan mode?
asked: 2026-10-27T21:59:19Z · stage: intent
A. numbered list in text, the human answers with the number, recorded by state.py answer (recommended)
B. '! <cmd>' line only
X. Other — answer as `X: <text>`
[Answer]: X: the same native dialog (request_user_input) or nothing: when it is unavailable the project behaves as if the dialog were switched off and the human types in their own terminal; no typed numbers, no pasted lines — by vanssa via prose at 2026-10-27T22:17:46Z

## Q7. Plan-drift detection (install.sh logic moved to state.py profile detect/set, SessionStart + auth_success) in this spec?
asked: 2026-10-27T21:59:19Z · stage: intent
A. yes, as the first consumer of the dialog (recommended)
B. separate spec
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T22:18:41Z

## Q8. Is the dialog switchable, and at what level?
asked: 2026-10-27T22:17:46Z · stage: intent
A. project-level setting; off means the human must run the command in another terminal (recommended)
B. user-level setting
C. always on
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T22:17:46Z

## Q9. OQ1: does the migration turn the dialog on in existing projects?
asked: 2026-10-27T23:22:08Z · stage: intent
A. yes, enabled:true, the migration prints one line saying the dialog is on and how to turn it off
B. no, enabled:false with a printed hint (recommended)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T23:22:08Z

## Q10. G1 (OQ3): is dialog.tool request_user_input enabled for Codex >= 0.165.0 (spike 7.0 evidence)?
asked: 2026-10-28T11:53:53Z · stage: intent
context: docs/dialog-spike.md:160-164
A. yes, the Codex version list is >= 0.165.0 (recommended)
B. no, the list is empty; dialog.tool stays null for Codex
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T11:53:56Z
