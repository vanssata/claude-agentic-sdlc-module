# Dialog spike (7.0) — recorded hook payloads for the command-choice dialog

Task T-2026-10-28-001, spec `docs/sdlc/specs/command-choice-dialog.md` (R36), plan
`docs/sdlc/plans/command-choice-dialog.md` step 7.0. Fixtures only: nothing in hooks, `state.py` or the
installer changes here. Every claim below carries one of the labels from `.ai/policies/safety.md`.

**Status 2026-10-28.** Complete for the plan's purpose: Claude Code recorded in print and TUI mode (eight fixtures in
`tests/fixtures/dialog/claude/`), Codex recorded in three TUI sessions (four fixtures in `tests/fixtures/dialog/codex/`).
What stays open is listed under *Open*; none of it blocks 7a–7f.

## How the payloads were recorded

- A throw-away recorder (`record.sh`, scratch only, not in the repo) dumps the hook's stdin to one file per
  event and the `CLAUDE_*`/`CODEX_*` environment to a sidecar. On `Stop` it exits 2 once, so the second `Stop`
  of the same turn carries `stop_hook_active: true`.
- Claude Code 2.1.312 took the hooks from `claude --settings <file>`, so no settings file of the user was
  edited (the path guard freezes them during a task). Registered: PreToolUse, PostToolUse, PostToolUseFailure,
  Stop, SubagentStop, Notification, UserPromptSubmit, all without a matcher.
  - Print mode: `claude -p --model haiku --settings <hooks.json> --allowedTools "Agent,Bash(echo:*),AskUserQuestion"`;
    the prompt spawned a general-purpose subagent that ran `echo`, called AskUserQuestion once, stopped.
  - TUI: `claude --model haiku --settings <hooks.json>`, permission mode `auto`; the human answered four
    AskUserQuestion dialogs (single, multi, Other, Esc) in two rounds.
- Codex (0.164.0 standalone here; the rollouts say 0.165.0, see its section) reads project hooks from `<cwd>/.codex/hooks.json` and runs them only after a human trusts them
  in `/hooks`; `codex exec --dangerously-bypass-hook-trust` would skip that step and was refused by this
  session's permission layer, so a Codex recording is the human's TUI run.

## Fixture format

```json
{ "case": "<one sentence>", "runtime": "claude|codex", "runtime_version": "2.1.312",
  "entrypoint": "TUI (claude --settings <hooks>), permission_mode auto", "recorded": "2026-10-28",
  "placeholders": { "__ROOT__": "...", "__HOME__": "...", "__PROJECT_SLUG__": "...", "__SCRATCHPAD__": "..." },
  "payload": { ...the hook's stdin, verbatim except the placeholders... } }
```

`cwd` → `__ROOT__` (the convention of `tests/guard_harness.py:52`), the home prefix → `__HOME__`, the project
slug under `~/.claude/projects/` → `__PROJECT_SLUG__`, `scratchpad_dir` → `__SCRATCHPAD__`. Ids
(`session_id`, `prompt_id`, `tool_use_id`, `agent_id`) are kept as recorded. `ask-esc.json` adds an `observed`
field because no payload exists for the event it pins. The environment sidecars are **not** committed: they
carry `CLAUDE_CODE_MESSAGING_TOKEN`.

## Claude Code 2.1.312 — recorded

| Fixture | Event | What it pins |
|---|---|---|
| `claude/ask-single.json` | PostToolUse AskUserQuestion | `tool_response.answers = {"<question>": "A"}` |
| `claude/ask-multi.json` | PostToolUse AskUserQuestion | two ticks → `"A, B"` (labels joined with `, `) |
| `claude/ask-other.json` | PostToolUse AskUserQuestion | Other with text → the text is one more `, `-joined item (`"A, B, C,   "`) |
| `claude/ask-esc.json` | PreToolUse AskUserQuestion | Esc: this is the last hook that fires; `observed` holds the transcript's rejection text |
| `claude/notification-permission-prompt.json` | Notification | `notification_type`, `message`; the envelope `auth_success` will share |
| `claude/stop.json` | Stop | `stop_hook_active: false`, `last_assistant_message`, `background_tasks`, `session_crons` |
| `claude/stop-hook-active.json` | Stop | the same turn after a Stop hook exited 2: `stop_hook_active: true` |
| `claude/subagent-pretooluse.json` | PreToolUse (Bash, inside a subagent) | `agent_id`, `agent_type` present |

**Envelope.**
- **KNOWN FACT** Every payload carries `session_id`, `transcript_path`, `cwd`, `prompt_id`, `permission_mode`,
  `effort.level`, `hook_event_name`; TUI payloads add `scratchpad_dir`. Tool events add `tool_name`,
  `tool_input`, `tool_use_id`; PostToolUse adds `tool_response` and `duration_ms`.
- **KNOWN FACT** The subagent marker is in the payload: `agent_id` and `agent_type` are present on PreToolUse,
  PostToolUse and SubagentStop issued from inside a subagent and absent on the main session's payloads. The
  process environment of a hook is byte-identical inside and outside the subagent (`diff` of the sidecars),
  so there is no environment marker. Review focus 3 of the plan and `test_gate_skips_subagent` (7d2) key on
  `agent_id`.

**AskUserQuestion (TUI).**
- **KNOWN FACT** PreToolUse carries `tool_input.questions[]` (`question`, `header`, `options[].label`,
  `options[].description`, `multiSelect`). PostToolUse carries the same `questions` plus `answers`
  (`{"<question text>": "<answer>"}`) and `annotations` in **both** `tool_input` and `tool_response`: the
  runtime writes the answers back into the input. `duration_ms` is 0 or 1 — the human's wait is not counted.
- **KNOWN FACT** Single-select: the answer is the option `label`. Multi-select: the labels joined with `", "`.
  Other: the typed text is one more `", "`-joined item and the tool result wording changes from
  `Your questions have been answered: "<q>"="A".` to `The user answered: "<q>"="A, B, C,   ". Read the answers
  carefully — they may request clarification, changes, or that you not proceed …`. Recorded with whitespace
  text in a multi-select (`ask-other.json`); a single-select Other was not recorded (the human picked A).
- **INFERENCE** The pick reader (7d1) cannot tell Other text from a label by position; it must compare each
  `", "`-split item against `options[].label` and treat any non-label item as Other → decline (R36, "Other text
  is a decline, text not stored"). Labels must therefore never contain `", "`; `state.py decision` (7c) owns that.
- **KNOWN FACT** Esc: PreToolUse fires, then **no** PostToolUse and **no** PostToolUseFailure (both registered).
  The transcript's tool_result is `The user doesn't want to proceed with this tool use. The tool use was
  rejected … STOP what you are doing and wait for the user to tell you how to proceed.` A decision closed by Esc
  therefore produces no event; it stays open until `window_seconds` passes (`.ai/policies/dialog.json`).
- **KNOWN FACT** `permission_mode` was `auto` in the TUI session and `default` in print mode; the dialog fired
  in `auto` without a permission prompt of its own. The two `permission_prompt` notifications of the session
  were for other tools.

**Print mode / unattended.**
- **KNOWN FACT** In print mode (`claude -p`, `CLAUDE_CODE_ENTRYPOINT=sdk-cli`) AskUserQuestion is not a tool:
  the call returns `Error: No such tool available: AskUserQuestion. AskUserQuestion is disabled for this
  session, in subagents as well as here.` and **no** hook fires for it.
- **KNOWN FACT** The hook environment in print mode has `CLAUDE_CODE_SESSION_ATTENDED=0` and
  `CLAUDE_CODE_ENTRYPOINT=sdk-cli`; `CLAUDE_CODE_SESSION_ID` equals the payload's `session_id`;
  `CLAUDE_PROJECT_DIR` equals `cwd`.
- **INFERENCE** An unattended session cannot consent through the dialog whatever the switch says: the tool is
  absent. The effective-switch matrix of 7d1 can read `CLAUDE_CODE_SESSION_ATTENDED` as the runtime's own
  unattended signal, with `AI_UNATTENDED` as the override.

**Stop and Notification.**
- **KNOWN FACT** A Stop hook that exits 2 makes the agent continue once; the next Stop has
  `stop_hook_active: true`. `last_assistant_message` is the text the agent stopped on.
- **KNOWN FACT** Notification payloads carry `notification_type` and `message` next to the envelope. Matchers
  the 2.1.312 binary knows: `permission_prompt`, `idle_prompt`, `auth_success`, `elicitation_dialog`,
  `agent_needs_input`, `agent_completed`, `elicitation_url_*`. `auth_success` itself was not recorded (no
  `/login` in the session); 7e should treat its `message` as *Open*.

## Codex — recorded (TUI, Default mode, three sessions)

| Fixture | Event | What it pins |
|---|---|---|
| `codex/pretooluse.json` | PreToolUse request_user_input | `tool_input.questions[]` with `header`, `id`, `question`, `options[]`; no `multiSelect` |
| `codex/request-single.json` | PostToolUse request_user_input | `tool_response` is a JSON **string**: `{"answers":{"<id>":{"answers":["A"]}}}` |
| `codex/request-other.json` | PostToolUse request_user_input | Other + text → `["None of the above", "user_note: <text>"]` |
| `codex/posttooluse.json` | PostToolUse Bash | the Codex envelope on an ordinary tool |

- **KNOWN FACT** PreToolUse and PostToolUse fire for `request_user_input` in Default mode (`permission_mode:
  "default"`) — recorded in three sessions (rollouts 13:06, 13:13 and 13:14 of 2026-10-28), two calls each.
  The envelope is `session_id`, `turn_id`, `transcript_path` (the rollout), `cwd`, `hook_event_name`, `model`,
  `permission_mode`, `tool_name`, `tool_input`, `tool_use_id` (`call_<hex>` for the dialog, `exec-<uuid>` for
  Bash); PostToolUse adds `tool_response` as a **string**, not an object. There is no `agent_id`, no
  `prompt_id`, no `effort`, no `scratchpad_dir`. The hook environment carries no `CODEX_*` variable.
- **KNOWN FACT** Answers are keyed by the question's `id` (`other_text`), not its text, and are always a list.
  A pick is the option `label`. Other is two items: the literal `"None of the above"` and `"user_note: <typed
  text>"`. Cancel was not recorded (the human did not cancel); `request-multi` does not exist: the tool has
  no multi-select field.
- **KNOWN FACT** The rollouts report `cli_version: 0.165.0`, while `codex --version` of the standalone install
  under `~/.codex/packages/standalone/releases/` prints 0.164.0 and `codex features list` there shows
  `default_mode_request_user_input` **under development, off by default**. The sessions therefore ran a
  different (newer) `codex` than the one on this shell's PATH; which binary the human's terminal resolved is
  *Open*.
- **INFERENCE** Session 3 (`01a18238`, 13:14) was started as plain `codex` without the flag: its first prompt is
  the launch command the human pasted into an already running Codex, and the model then ran that command as
  Bash (the nested Codex is `codex/…` session 3's PostToolUse Bash of 3.3 KB, not committed). In that session
  `request_user_input` was offered and both hooks fired. So on the CLI the human ran (0.165.0), the dialog
  works in Default mode **without** the flag. Session 1 (13:06) ran with `--enable
  default_mode_request_user_input` per the instructions; session 2 is unassigned.
- **Decision for R36.19 (G1, the human's):** the version list is not empty. Evidence supports `>= 0.165.0`
  (Default mode, hooks fire, no flag). 0.164.0 is **not** on the list: its flag is off by default and no
  session on it was recorded. The installer writes `dialog.tool: "request_user_input"` only for a version on
  the list; the adapter (`hooks/guard/dialog.py`, 7d1) parses the string `tool_response` and maps
  `"None of the above"`/`user_note:` to a decline, exactly as Claude's non-label item.
- **UNKNOWN** The cancel payload (Esc in Codex's dialog): whether PostToolUse fires with empty `answers`, or
  nothing fires as in Claude. The binary knows "request_permissions was cancelled before receiving a
  response"; `tui/src/bottom_pane/request_user_input` reads a "free-form answer" and a "selection". Settled by
  one more TUI run with Esc; until then 7d1 treats both shapes as a decline.

## Fields each later task relies on

| Task | Reads | Pinned by |
|---|---|---|
| 7c `state.py decision` | nothing from hooks; writes `header`, `question`, `options[].label` (no `", "` in a label) | `ask-*.json` (shape) |
| 7d1 gate fast path | `hook_event_name`, `tool_name`, `session_id`, `cwd`, `tool_use_id` | every fixture |
| 7d1 pick reader | PostToolUse `tool_response.questions[*]`, `tool_response.answers` split on `", "` against labels | `ask-single`, `ask-multi`, `ask-other` |
| 7d1 Esc / no event | nothing arrives after PreToolUse | `ask-esc.json` |
| 7d1 stop blocks | `stop_hook_active`, `session.json.prompt_count` (own) | `stop*.json` |
| 7d1 effective switch | `CLAUDE_CODE_SESSION_ATTENDED`, `AI_UNATTENDED`, tool availability, `agent_id` absent | `subagent-pretooluse.json`, this doc |
| 7d2 subagent skip | `agent_id` present ⇒ not the human's session | `subagent-pretooluse.json` |
| 7e drift / auth | Notification `notification_type`, `message` | `notification-permission-prompt.json`; `auth_success` *Open* |
| 7b installer | the Codex version list (`>= 0.165.0`, G1) | Codex section, `codex/*.json` |
| 7d1 Codex adapter | string `tool_response` → `answers[<id>].answers[]`; `None of the above`/`user_note:` = decline | `codex/request-*.json` |

## Open

1. Claude: Notification `auth_success` payload (`claude/auth-success.json`), a single-select Other.
2. Codex: the cancel (Esc) payload (`codex/request-cancel.json`); which `codex` binary the human's terminal
   resolves (rollouts say 0.165.0, the standalone install says 0.164.0); whether session 2 ran with the flag.
3. Gate G1 (human): confirm the version list `>= 0.165.0` (evidence above) before 7b writes it.

## Observations outside this task (not fixed here)

- **RISK** `hooks/guard/paths.py:1177` (`SECRET_TEXT_RE`) refused a command that only named a sidecar file
  ending in the four characters dot-e-n-v beside a `python3 -c`: the substring rule has no word boundary, so
  any filename or prose with that ending inside a one-liner's command text is a false positive. It fired twice
  in this task. Candidate for `.ai/project/known-risks.md`.
