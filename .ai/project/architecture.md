# Architecture

## Style

- KNOWN FACT: Three layers that share on-disk formats, not code calls. **Hooks** decide allow/deny per tool call (`hooks/*.py`, library `hooks/guard/`). The **state machine** (`skills/ai-task/state.py` → `rr_state/cli.py:73`) records a task's lifecycle. **Skills** are prose that orchestrates both. **Installer and update** (`bin/riskrails.js`, `skills/project-update/`) put them in place.
- INFERENCE: Hooks and the state machine are deliberately decoupled: a hook never imports `rr_state` and reads only its files (decision file, consent ledger, `state.json`). This rests on the per-module docstrings and the `hooks/guard/` imports. A full import trace was not done.

## Entry points

| Trigger | Script | Can refuse | Runtime |
|---|---|---|---|
| PreToolUse `*` / `.*` | `hooks/ai-guard.py` → checks decision, git, paths, scope (`:32,62-71`) | deny JSON, always exit 0 | both |
| PreToolUse `Read` | `hooks/cap-large-read.py` | deny JSON (`:50-54`) | Claude only |
| Pre/PostToolUse `Agent` (Codex `^Agent$\|spawn_agent$`), SubagentStart/Stop | `hooks/runtime-gate.py` | allow/ask JSON (`:384,770,976`) | both |
| PostToolUse `AskUserQuestion` / `request_user_input`; Stop | `hooks/dialog-gate.py` | Stop `{"decision":"block"}` (`:70`), capped by `stop_blocks_max` | both |
| UserPromptSubmit, PreCompact, SessionStart | `hooks/context-guard.py` | `{"decision":"block"}` (`:679`) | both |
| Notification `auth_success` | `hooks/context-guard.py` | — | Claude only |
| Setup `init` | `hooks/project-scaffold.sh` → `project-scaffold.py` | — | Claude only |
| StopFailure `rate_limit\|model_not_found` | `runtime-gate.py` via `settings.gate.json` | — | Claude, npx Fable install only (`hooks/hooks.json:2`) |
| git pre-push | `hooks/memory-pre-push.py`, written by `state.py memory enable` (`memory_hook.py:45-46`) | exit 3 / stderr | git |
| CLI | `state.py` verbs (`rr_state/cli.py:26-186`), `update.py`, `setup.py`, `status.py`, `usage-report.py` | exit codes | — |

## Request and message flow

- KNOWN FACT: Tool call → `ai-guard.py` reads stdin JSON → `decision` check first (an open dialog decision blocks every tool, `hooks/guard/decision.py:30,45`) → git (`guard/git.py`) → paths (`guard/paths*.py`) → scope (`guard/scope.py:329`). The first Deny wins and prints `permissionDecision: deny`.
- KNOWN FACT: Task lifecycle: `start` (`rr_state/start.py:104`; weight → mode, arms the scope guard, stage `build`) → `step-done` / `steps` (`steps.py:21,71`) → `verify` (`verify.py:156`, budget at `:171`) → `review` (`review.py:72`, verdict checks `:49-68`) → `close` (`close.py:55`; owes per mode `:21-52`; in full it requests the gate `:92-118`) → `approve` (human only, `gate_cmd.py:14`) → `close` again → `archive_v7` (`close.py:128`, stage `done`, memory after close).
- KNOWN FACT: Dialog: `state.py decision` opens a decision. The agent sends the JSON via AskUserQuestion. `dialog-gate.py` records the pick in the ledger, and the git check allows only the picked command, verbatim, once (`hooks/guard/dialog.py:40,538-541`).

## Module boundaries

- KNOWN FACT: `hooks/guard/dialog.py` (hook side) and `skills/ai-task/rr_state/dialog.py` (state side) share a name and a ledger format but no code.
- RISK: The shared formats (decision file, consent ledger `.ai/state/consent.jsonl`, `state.json` schema 7) are parsed on both sides. A format change on one side can silently break the other.
- KNOWN FACT: `AI_UNATTENDED` is interpreted in at least five places (`runtime-gate.py:955`, `guard/dialog.py:122`, `guard/paths.py:119`, `rr_update/gate.py:19`, `rr_state/fs.py:79`). RISK: they can drift.

## Where state lives

- KNOWN FACT: In a user project: `.ai/state/state.json` (task, schema 7, `rr_state/task.py:192`), `.ai/state/session.json` (hook sidecar; unreadable reads as `{}`, `fs.py:72-89`), `.ai/state/consent.jsonl` + `consent.lock`, `.ai/state/handoff.md`, `.ai/reports/<task>/events.jsonl` (journal, flock append), `.ai/reports/<task>/task.md`, `.ai/state/logs/<task>/` (archive), `.ai/memory/` (record), `.ai/local/memory/index.sqlite3` (optional index). All writes go through a temp file and `os.replace`.
- KNOWN FACT: On the user's machine: `~/.claude` / `~/.codex` (settings, hooks, skills), `~/.claude/riskrails/ai/` (shared policies), `<home>/backups/<date>/`.

## Cross-cutting mechanisms

- KNOWN FACT: Weight: six axes 0–2 (`skills/ai-task/weight.py:206`) → mode light / guarded / full / full_irreversible (`weight.py:239-247`). The plugin table is overlaid by `.ai/policies/weight.project.json` (`weight_overlay.py`).
- KNOWN FACT: Fail-open doctrine. `ai-guard.py` allows on unparseable input or any non-Deny exception (`:21-23,85-93`), and so does `dialog-gate.py` (`:99-100`). The documented fail-closed exceptions: the git consent rule denies commit/push when the ledger is unreadable (`ai-guard.py:24-26`), and `approve` refuses without a pick or a terminal.

## Contradictions found

Documented behaviour: CLAUDE.md:5 names `SH_WORD`/`SH_RE` in `hooks/ai-path-guard.sh` and the invariant "no piece of a word crosses the blank after a match start's `sh`".
Observed behaviour: `hooks/ai-path-guard.sh` no longer exists; the guard is ported to `hooks/guard/paths*.py` (`paths.py:1`). Neither identifier occurs in `hooks/` or `tests/` (grep 2026-11-14).
Evidence: `CLAUDE.md:5`; `grep -rn 'SH_WORD|SH_RE' hooks tests` returns nothing.
Risk: the invariant has no named code or test to attach to, so a future edit cannot tell what it must preserve.
Resolved (T-2026-11-14-1222): CLAUDE.md:5 now names the regexes as retired in R22 (`710a2aa`) and points to what holds today — top-level splitting in `hooks/guard/paths_bash.py:70-71`, the `LONG_CMD` refusal at `:33,49`, and the timed cases at `tests/test_ai_path_guard.py:398-413`.

Documented behaviour: the user memory note says a 5000+ char command naming a state.py verb is refused.
Observed behaviour: the threshold is `LONG_CMD = 4096` (`hooks/guard/paths_bash.py:33`, applied `:49`). `docs/hooks.md:125-129` documents it, written "4 096" (a grep for "4096" missed it); only the memory note was wrong, and it has since been corrected.
Evidence: `paths_bash.py:33`; pinned by `tests/test_ai_path_guard.py:405,413`.
Risk: agents size their commands from the wrong number.

Documented behaviour: `docs/hooks.md:124` says top-level `sh -c '…'` and `eval` segments "are split and each one checked".
Observed behaviour: `hooks/guard/paths_bash.py:70-71` splits top-level segments only; the string a `sh -c` or `eval` runs is not re-parsed for the movers (R22, SQ13; accepted in known-risks.md). The token scan still sees its words.
Evidence: `docs/hooks.md:124`; `paths_bash.py:70-72`.
Risk: a reader of docs/hooks.md expects the mover check inside a `sh -c` string. Not resolved: docs/hooks.md is outside this task.

Documented behaviour: `.ai/policies/verification.md:27` says verify is "one unittest discover".
Observed behaviour: `verify_command` is `tests/run_suite.py` (`verification.md:4`), a parallel runner.
Evidence: `verification.md:4,27`.
Risk: low; stale prose.
