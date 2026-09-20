# Spec: WP2 — Questions file, handoff, event journal, human-turn approval

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work package 2)
Risk tier: **T4** (raised from the intent's T3 by the user on 2026-09-20 — the deliverable *is* an
authorization control) · Depends on: WP1 (done, PR #15/#16) · Schema: `.ai/VERSION` 1 → 2

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

This package answers Problem 1 (decisions live in the chat), Problem 5 (the human approval is
a field) and the state half of Problem 6 (a task cannot change runtime). It builds nothing that
costs a token: every new command is standard-library Python, every new check is deterministic.

## Requirements

Tags name the intent outcome each requirement satisfies: **Q&C** = "Questions and continuity",
**GATE** = the approval bullet under "Quality and cost gates", **RT** = "Runtimes and plans",
**P1/P5/P6** = Problem items, **D3/D7/D8** = Decisions taken.

| # | Requirement | Satisfies | Proof |
|---|---|---|---|
| R1 | `state.py ask` creates or appends to `.ai/reports/<task-id>/questions.md` in the format of I2. The file is written by the command, never by the model. | Q&C, P1 | after `ask`, the file parses back to the same question through `questions --format json` |
| R2 | `answer` and `questions --sync` are the only writers of `[Answer]:` lines. A hand-edited `[Answer]: B` round-trips: `--sync` reports it, emits `question_answered{via:file}` and rewrites the line with the command's trailer without touching the question text. | Q&C | byte-compare the question block before/after `--sync` |
| R3 | A pending question blocks `stage`, `triage`, `plan`, `step`, `step-done`, `remediate`, `approve`, `done`, `close`: exit 4, `QUESTIONS_PENDING`, state unchanged. `get`, `set`, `risks`, `modules`, `note`, `ask`, `answer`, `questions`, `handoff`, `events`, `archive` and `done --abandon` are never blocked. | Q&C | new test: each blocked command exits 4 and `current.json` is byte-identical |
| R4 | Pending questions are re-injected at session start in both runtimes (I7) and listed by `/ai-status` through `state.py questions --pending` — never by `cat`/`tail` on the file, which the path guard denies. | Q&C | `test-ai-path-guard.sh` fixture 23/24; `ai-status` grep |
| R5 | A subagent never asks: every agent contract carries the `QUESTIONS_NEEDED` block (I9) and the main session converts it with `ask --batch`. Under `AI_UNATTENDED=1`, `ask` ends the turn with the literal line `WAITING_FOR_ANSWERS <file> <ids>`. | Q&C | last stdout line of `ask` under the flag |
| R6 | `.ai/state/handoff.md` is rendered only by `state.py handoff`, is ≤ 30 lines, carries the six named parts (I4), and is rewritten on every stage-moving command and on PreCompact. | Q&C, P1 | `wc -l` ≤ 30 after a task with 10 notes and 8 prompts |
| R7 | At `SessionStart`, `context-guard.py` injects the block of I7.3 when the cwd's `.ai/state/current.json` exists, and injects nothing otherwise — same script, same behaviour in Claude Code and Codex. **No decision depends on a payload key**: `source` is recorded and never branched on, `cwd` falls back to `os.getcwd()`, and the transcript snapshot is added when a fresh snapshot file exists. | Q&C, parity | `test-context-guard.sh` with a payload carrying `source`/`cwd`, and with one carrying neither |
| R8 | `.ai/reports/<task-id>/events.jsonl` receives one line per state change (schema I3), append-only; two concurrent appenders lose and interleave nothing. | Q&C | 2×200 appends from two processes → 400 parseable lines |
| R9 | `history[]` keeps its shape and keeps being written; migration 0002 backfills the journal from it; `state.py events` and `/ai-status` read the journal; `/usage-report` documents it. | Q&C | existing state tests green; backfill line count = history length |
| R10 | The state carries `owner_runtime` and `resume_point` (I6). A mutating command run under a different runtime emits `runtime_handoff{via:resume}` and takes ownership. `handoff` has no `--to` (that is WP5) and nothing WP5 must undo. | RT, P6 | new test: `--runtime codex` after a claude-owned task |
| R11 | `approve` succeeds only when (a) stdin is a TTY **or** `AI_UNATTENDED` is set in its own environment, (b) a `gate_requested` event exists for this task, and (c) no non-gate question is pending. Otherwise exit 5 with the message of I1. Under the flag, the event and the state carry `unattended:true`. | GATE, D8, P5 | `approve` under a pipe exits 5; under `pty.spawn` exits 0 |
| R12 | The invocation `state.py approve` / `$STATE approve` from an agent Bash call is denied by `ai-path-guard` in both runtimes while a task is in flight, unless `AI_UNATTENDED` is set in the hook's own environment. The check runs **before** the Bash fast path; `task_in_flight()` is consulted only after the regex matches. Cost: one in-process regex per Bash call, zero extra processes; one `jq` on a match. | GATE, D8 | fixtures 25–27 + `codex-hooks/40`, plus a no-task-in-flight fixture that allows |
| R13 | Filling `[Answer]: A` on gate question `G1` and running `questions --sync` grants approval with `via:file` — but only when `session.json.last_prompt_at ≥ human_approval.requested_at` (a human turn after the plan was presented), or `AI_UNATTENDED` is set. Without a `session.json`, the file route is refused and the terminal route is the only one. | GATE, D8 | new test: sync before/after a recorded prompt |
| R14 | `.ai/VERSION` becomes `2`; `migrations/0002_task_journal.py` adds every new key with defaults through `patch_state` and creates the backfilled journal. A v1 project with a task at `implementation` works before **and** after `update.py --apply`. | Constraints | fixture `schema-v1` in `test-project-update.sh` |
| R15 | `install.sh` installs `context-guard.py` into `~/.codex/hooks/`, and `codex/hooks.json` registers it on `UserPromptSubmit`, `PreCompact` and `SessionStart`. | parity | `test-codex-install.sh` |
| R16 | `tests/test-guard-characterization.sh` after `--record` differs from the committed golden **only by added records**; `ai-git-guard.sh` is byte-identical; every existing `WHY_*` text is unchanged. | Constraint 4 | `git diff` of the golden has no `-` lines |
| R17 | `/sdlc-intent` records its brainstorm through `ask --topic <slug>` / `answer --topic <slug>` into `docs/sdlc/intent/<slug>.questions.md` — with or without `.ai/` — and writes a `## Decisions taken` section from `questions --topic <slug> --format md`. Topic questions emit no journal events and never block a stage. | D3, P1 | new test: a fixture with `docs/sdlc/` and no `.ai/` completes ask → answer → render |
| R19 | The plan carries a **Rollback** section (schema 2 → 1, the hook registrations, the golden file), a **Monitoring** section (what `/ai-status` and `/usage-report` show about gates, pending questions and runtime ownership) and an explicit **Idempotency and retry** statement for the migration, the journal append and `questions --sync`. Security review is mandatory, not conditional. | T4 `extra_requirements` | `ai-release` checks the sections exist |
| R18 | Nothing in WP2 spawns a model. Every new command is stdlib Python; existing suites stay green with the extensions of D10. | Constraint 2 | full suite |

## Design

### Components

| Component | Responsibility |
|---|---|
| `state.py` — journal core | `emit(state, event, detail, data)` = today's `record()` **plus** one journal line; the `events` reader; runtime detection; in-memory defaults for a v1 state |
| `state.py` — questions | create/parse/sync `questions.md`; the pending check used by stage-moving commands |
| `state.py` — gate | `gate_requested` on `stage human_approval`; the outside-the-agent checks; `reject` |
| `state.py` — handoff | render `handoff.md` from state + journal + `session.json`; maintain `resume_point`; delete on `archive` |
| `state.py` — notes | record decisions / rejected options / failed attempts as journal events (the state does not grow) |
| `hooks/context-guard.py` | unchanged prompt measurement; **new:** write `session.json` on SessionStart and UserPromptSubmit, shell out to `state.py handoff` on PreCompact and SessionStart, and embed `handoff.md` in the snapshot in place of today's `current.json` dump |
| `hooks/ai-path-guard.sh` | **new:** three `protected_config_patterns` (questions, journal, handoff) and the `state.py approve` Bash rule |
| `migrations/0002_task_journal.py` | v1 → v2 defaults and the journal backfill |
| `skills/ai-task/SKILL.md`, `agents/*.md` and their `templates/.ai/agents/*.md` mirrors | the `QUESTIONS_NEEDED` → render → `answer` procedure, and the approval procedure |
| `skills/sdlc-intent`, `skills/ai-status`, `skills/usage-report` | brainstorm through `--topic`; read the journal at zero model cost |

### Data flow

1. **Ask → answer.** A subagent returns `## QUESTIONS_NEEDED` → the main session writes a
   batch file → `ask --batch` appends `Q<n>` blocks, sets `questions.pending`, emits
   `question_asked` per question and prints the prose rendering → Claude Code renders with
   `AskUserQuestion`; Codex and the stub runtimes print the numbered prose and the user replies
   `1B 2A 3: text` → `answer Q1=B …` or `answer --prose "…"` rewrites the file, emits
   `question_answered` and recomputes `pending` **from the file**. A hand edit is picked up by
   `questions --sync`.
2. **Blocking.** Every stage-moving command calls `_pending(root, state)`, which re-parses the
   file — the file is the truth, `questions.pending` is only a cache — and dies with exit 4.
3. **Approval.** `stage human_approval` appends gate question `G1`, sets
   `human_approval.requested_at`, emits `gate_requested` and renders the handoff. Route A: the
   human runs `approve` in their own terminal (TTY) → `gate_approved{via:terminal}`. Route B: the
   human fills `[Answer]: A`, tells the session (which advances `last_prompt_at`), the agent runs
   `questions --sync` → R13 → `gate_approved{via:file}`. Route C: a launcher exports
   `AI_UNATTENDED=1` → `gate_approved{via:unattended, unattended:true}`, visible as such for ever.
4. **Session start, either runtime.** The hook reads `cwd`, walks up to `.ai/`, writes
   `session.json{runtime, session_id, source, started_at}`, and — if a task is in flight — runs
   `state.py handoff --print` (timeout 3 s) and emits its stdout as `additionalContext`, capped at
   8 000 characters. On Claude `source=compact` this is prepended to the existing transcript
   snapshot.
5. **PreCompact.** The hook runs `handoff --reason precompact` (emits `handoff_written`), then
   builds the snapshot with `handoff.md` verbatim instead of the JSON dump.
6. **UserPromptSubmit.** Today's measurement, plus `session.json.last_prompt_at = now` and
   `last_prompt = <first 800 chars>` when a task is in flight — the evidence for R13.
7. **Runtime ownership.** Any mutating command computes the runtime (I10); a null
   `owner_runtime` is set, a different one emits `runtime_handoff` and takes over.
8. **Migration.** `update.py --apply` on a v1 project: `patch_state` adds the keys of I6,
   `create` writes the backfilled journal, `.ai/VERSION` becomes 2, the three-way merge carries the
   new `state/README.md` and the `.gitignore` line.

### Open question 1 — settled from the Codex documentation

- Codex CLI (2026) has lifecycle hooks: `SessionStart`, `SessionEnd`, `PreToolUse`, `PostToolUse`,
  `PermissionRequest`, `PreCompact`, `PostCompact`, `UserPromptSubmit`, `SubagentStart`,
  `SubagentStop`, `Stop`, `Interrupt`. `SessionStart` matches on `source` ∈
  `startup|resume|clear|compact` — the same shape Claude Code uses — is configured in
  `~/.codex/hooks.json` or `config.toml` (user), `<repo>/.codex/…` (project), a plugin bundle or
  `requirements.toml` (managed), and injects through `hookSpecificOutput.additionalContext` with an
  `additionalContextLimit` of about 2 500 tokens.
  **→ the session-start hook reaches full parity; one script serves both runtimes.**
- Codex has **no** native question picker or elicitation API, for hooks or for the agent.
  **→ question rendering is not parity.** One file, three renderings: the native picker where one
  exists (Claude Code), numbered prose `1B 2A 3: text` everywhere else, and hand-editing the file
  as the always-valid third way.
- Budget check: the ≤ 30-line handoff (≈ 3 000 chars ≈ 750 tokens) fits the Codex limit; the
  existing 12 000-char snapshot (≈ 3 000 tokens) does not. The two budgets agree only because the
  transcript-derived snapshot never crosses to Codex — it stays Claude-only, and the cross-runtime
  block is capped at 8 000 characters with the questions collapsed to one line when over budget.
  This is stated in the hook's docstring.

### Open question 2 — how "outside the agent" is enforced

| Candidate | Hot path | Both runtimes | Headless | Defeated by |
|---|---|---|---|---|
| (a) `os.isatty(0)` inside `approve` | 0 (one syscall, no hook) | yes — both tools pipe stdin | refused unless `AI_UNATTENDED`; recorded as unattended | `< /dev/tty`, `script -qc`, a pty, or the flag on its own command line |
| (b) env marker set by the hooks | 0 | **no** — hooks cannot set the tool's environment; `CLAUDECODE` is Claude-only and Codex has no stable equivalent | needs the same flag anyway | `env -u CLAUDECODE …` |
| (c) one-time token shown only to the user | 0 | **no** — no user-only channel on Codex; desktop/IDE rendering unknown | the launcher must mint it | reading the token from wherever it is stored |
| (d) PreToolUse deny of `state.py approve` | +1 in-process regex on Bash calls inside `.ai/` projects, 0 processes, < 1 ms | yes (Codex's shell arrives as `Bash`) — **but only after the user trusts hooks via `/hooks`** | allowed when `AI_UNATTENDED` is in the *hook's* environment, which the agent does not set | obfuscation (`bash -c "$(base64 -d …)"`, a script file, `eval`) |

**Decision: (a) + (d), plus the human-turn check for the file route (R13) and the precondition
that a `gate_requested` event exists.** (d) is the stronger primitive where it runs — it stops the
call before it executes, sees redirections and env prefixes, and its deny text teaches the human
what to do — but it does not exist on Codex until hooks are trusted. (a) exists everywhere and
costs nothing. (b) and (c) are rejected: not portable, and (c) adds a secret to manage.

**Residual risk, plainly:** an agent that deliberately obfuscates the invocation *and* allocates a
pty or prefixes `AI_UNATTENDED=1` can still approve. The journal then shows
`gate_approved{via:unattended}` or `{tty:true}` inside a session whose `session.json` says the run
was interactive; `/ai-status` flags that line and `/usage-report` counts it. What this does **not**
prevent: an adversarial model, a human who approves without reading, or approval of a plan that
was presented but not understood. It prevents the accidental and the honestly-mistaken cases —
which is what Problem 5 describes, and it matches the guards' own stated scope.

### `handoff.md` versus the context-guard snapshot

Both survive, with one owner each and no overlapping fact. `handoff.md` is the authoritative,
project-side, cross-runtime record, rendered by one deterministic command from facts the runtime
cannot lose (state, journal, `session.json`). The snapshot is the Claude-side, session-scoped
supplement derived from the transcript (files edited, todo list, git status, older prompts) that
`state.py` cannot know. Composition: the snapshot embeds `handoff.md` verbatim and drops its
`current.json` dump; the session-start block is `handoff.md` + pending questions in every runtime;
the transcript parts are added only on Claude `source=compact`.

### `history[]`, `/ai-status`, `/usage-report`

`history[]` is kept unchanged and written in parallel by `emit()` — so a task in flight survives
the migration untouched — and is not capped in WP2. `/ai-status` reads `state.py events --last 8`
(falling back to `history[]` when no journal exists) and gains: `owner_runtime` against this
session's runtime, `resume_point`, pending questions, the age of `handoff.md`, and any
`gate_approved` with `data.unattended` true. `/usage-report` documents the journal and uses
`task_started`/`task_closed` for per-task duration; the token budget per task is WP4 and is not
built here.

### Alternatives rejected

1. **A separate `session-start.py` hook.** One more process per SessionStart and PreCompact in each
   runtime, a second copy of the snapshot logic, two registrations. `context-guard.py` already owns
   all three events — the intent's "session-start hook" is a behaviour, not a file.
2. **Putting the approve rule in `ai-git-guard`.** The intent freezes git-guard rules; that guard is
   global rather than gated on `.ai/`, so the rule would fire in every repository. The path guard
   already models task-scoped protection (WP7).
3. **Blocking *edits* while a question is pending.** The intent says *stages* do not advance, not
   edits; a new deny text on every Edit is a behaviour change the scope guard should not grow here.
   The pre-existing gap (the scope guard is disarmed between steps) belongs to WP4.
4. **Answers stored in `current.json` with the markdown as a rendering.** Hand-editing must remain a
   valid answer path; two sources of truth would need reconciliation rules. The file is the truth,
   the state holds a cache.
5. **Sequence numbers in the journal.** Two appenders race on the counter; `O_APPEND` ordering plus
   a millisecond timestamp is enough for every reader WP2 defines.
6. **The hook writing `owner_runtime` into `current.json`.** That file has exactly two writers by
   contract and is protected by the path guard; the hook writes the `session.json` sidecar instead.
7. **Requiring `questions --sync` itself to run outside the agent.** That would collapse the
   intent's file route into the terminal route. It is protected by the path guard and the
   human-turn check instead, and its weaker status is documented.

## Interfaces

### I1 `state.py` CLI (additions; `--root` unchanged)

```
global:  --runtime claude|codex            # overrides AI_RUNTIME and detection (I10)
ask      "<question>" --option "A: text" [--option "B: text" …] [--recommend A]
         [--context TEXT] [--gate human_approval] [--topic SLUG]
ask      --batch FILE.json [--topic SLUG]  # [{question, options:[{key,text}], recommend?, context?}]
answer   Q1=B [Q2=X:"free text" …] [--by NAME] [--via picker|prose|file] [--topic SLUG]
answer   --prose "1B 2A 3: text" [--by NAME] [--topic SLUG]
questions [--pending] [--sync] [--format md|prose|json] [--topic SLUG]
approve  --by NAME [--note TEXT]
reject   --by NAME --why TEXT
note     decision|rejected|failed "<text>" (--why TEXT | --error TEXT)
handoff  [--print] [--reason stage|precompact|manual|session-start]
events   [--last N=20] [--type t1,t2] [--task ID] [--format lines|jsonl]
event    <type> [--detail TEXT] [--data JSON]     # for hooks; type must be in I3
done     [--abandon]
```

Exit codes: `0` ok · `1` validation / no task / unreadable state (today's `die`) · `2` argparse ·
`4` `QUESTIONS_PENDING` · `5` `APPROVAL_REFUSED`.

Exit 4, exact stderr:
`state.py: QUESTIONS_PENDING — 2 unanswered in .ai/reports/<id>/questions.md: Q2, Q3. Answer with 'state.py answer Q2=<letter> Q3=<letter>' or fill the [Answer]: lines and run 'state.py questions --sync'. Stage stays at plan.`

Exit 5, exact stderr:
`state.py: APPROVAL_REFUSED — approval happens outside the agent. Run in your own terminal:` /
`  python3 <abs path>/state.py --root <root> approve --by "<name>"` /
`or set [Answer]: A on G1 in .ai/reports/<id>/questions.md and tell the session to sync. An unattended run exports AI_UNATTENDED=1 in the launcher's environment; the journal then records the approval as unattended.`
When no gate was requested:
`state.py: APPROVAL_REFUSED — no gate was requested: run 'state.py stage human_approval' after presenting the plan.`

`ask` prints `Q3 Q4 asked → .ai/reports/<id>/questions.md` followed by the prose rendering; under
`AI_UNATTENDED` the last line is `WAITING_FOR_ANSWERS .ai/reports/<id>/questions.md Q3 Q4`.

### I2 `questions.md`

```
# Questions — T-2026-09-20-003
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Which rounding rule applies to the per-line fee?
asked: 2026-09-20T10:12:03Z · stage: plan · by: ai-planner via main session
context: src/Payment/FeeCalculator.php:42 — two rules coexist today
A. Round half up per line (recommended)
B. Round half even per order total
C. Truncate to the cent
X. Other — answer as `X: <text>`
[Answer]:

## G1. Approve T-2026-09-20-003 for implementation? (gate: human_approval)
asked: 2026-09-20T11:02:40Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other
[Answer]:
```

Grammar, one regex per line: heading `^## (Q|G)(\d+)\. (.+)$`; option
`^([A-W])\. (.+?)( \(recommended\))?$`; other `^X\. Other`; answer `^\[Answer\]:\s*(.*)$` with body
`LETTER( *[—:-] *text)? | X *: *text | text`. An empty body is pending; a letter that is not an
option makes `--sync` report `Q1: invalid choice 'F'` and stay pending. Once answered the line
reads `[Answer]: B — by ivan via prose at 2026-09-20T10:15:00Z`; the trailer is parsed back and
ignored on re-sync. `answer` refuses `G*` ids with
`G1 is a gate: run 'state.py approve' in your terminal or fill its [Answer]: line`. Prose tokens:
`(\d+)([A-W])` is a choice, `(\d+):` starts free text up to the next token. A `--topic` file has
`## Q` blocks only — no gates, no blocking.

### I3 `events.jsonl`

One object per line (`ensure_ascii=False`, no indent), ≤ 4 096 bytes (`detail` cut at 500 chars,
`data.error` at 1 000), written with `os.write` on `os.open(path, O_WRONLY|O_APPEND|O_CREAT, 0o644)`
under `fcntl.flock(LOCK_EX)` where `fcntl` imports. Readers skip unparseable lines and report the
count on stderr.

```json
{"ts":"2026-09-20T10:12:03.123Z","task":"T-2026-09-20-003","event":"stage_started",
 "actor":"agent","runtime":"claude","stage":"plan","detail":"context -> plan: planner done",
 "data":{"from":"context","to":"plan"}}
```

A journal line is written once and never rewritten, so a value not captured here is lost for every
task that ran before the day someone wants it. `field_set` and `tier_set` therefore record the
**previous** value in `from` beside the new one — the one thing in this schema that cannot be
backfilled. Token accounting is deliberately *not* here: `/usage-report` reads tokens from the
transcripts and correlates them by `task` and the `task_started`/`task_closed` window, so WP4 needs
no field reserved in advance, and no type exists without an emitter.

`actor` ∈ `agent|human|hook|migration|unknown` — `human` only for `gate_approved{via:terminal}`,
`question_answered{via:file}` and `gate_rejected`. `runtime` ∈ `claude|codex|unknown`.

Event types: `task_started{goal,workflow}` · `stage_started{from,to,note}` ·
`tier_set{tier,from,note,direction}` · `tier_raised{from,to,note}` · `plan_registered{ref,steps}` ·
`scope_change{step_id,added_files[],removed_files[]}` · `step_started{step_id,kind}` ·
`step_done{step_id}` · `field_set{field,from,value}` · `question_asked{id,options,recommended,gate?}` ·
`question_answered{id,choice,text?,via,by}` · `gate_requested{gate,requested_at}` ·
`gate_approved{by,via,unattended,tty}` · `gate_rejected{by,why}` ·
`note{kind,text,why?,error?}` · `handoff_written{reason,lines}` ·
`runtime_handoff{from,to,via}` · `model_fallback{agent,from,to,reason}` (emitted from WP5 through
`state.py event`) · `schema_migrated{version,title}` · `task_closed{abandoned}`.

Backfilled lines carry `data.backfilled:true` and `data.legacy_event`, mapping
`stage→stage_started`, `risk_classified→tier_set`, `plan_approved→plan_registered`,
`step_completed→step_done`, `remediation→step_started{kind:remediation}`,
`set|risk_added|risks_cleared|modules→field_set`, `human_approval→gate_approved{via:"legacy"}`,
anything else → `event:"legacy"`.

### I4 `handoff.md` — ≤ 30 lines by construction

```
# Handoff — T-2026-09-20-003 (feature, T3) · stage implementation · step 2/4 · owner claude · written 2026-09-20T10:12:03Z (stage)
Goal: <one line, ≤ 160 chars>
Next: <next_action>   ← resume point (step 2: src/Checkout/*.php)
Pending questions: none | Q2, Q3 — .ai/reports/T-…/questions.md
## Decisions (latest 3)
- <text> — because <why>
## Rejected (latest 3)
- <text> — because <why>
## Failed attempts (latest 3)
- <text> — error: <first 160 chars, newlines collapsed>
## Latest user instruction (verbatim, 2026-09-20T10:11:50Z, claude)
> <session.json.last_prompt, ≤ 300 chars, one line, or "none recorded">
```

Empty sections print `- none`. Sources: the state (`goal`, `current_stage`, `approved_plan`,
`next_action`, `owner_runtime`), the journal (`note` events, newest first), `questions.md` (pending
ids) and `session.json` (the last prompt). `archive` deletes it.

### I5 `.ai/state/session.json` — written by the hook, read by `state.py`

```json
{"runtime":"codex","session_id":"…","source":"startup","started_at":"…Z",
 "last_prompt_at":"…Z","last_prompt":"…≤800 chars…"}
```

Atomic write (tmp + `os.replace`) by `context-guard.py` only. Already covered by the path guard's
`\.ai/state/[^/]*\.json$` pattern and by the `.ai/state/*.json` gitignore line.

### I6 State shape v2 and the migration

New keys in `current.json`:

```
"owner_runtime": null | "claude" | "codex",
"resume_point":  null | {"stage","step_id","next_action","at","runtime"},
"questions":     {"file": ".ai/reports/<id>/questions.md", "pending": []},
"handoff":       {"file": ".ai/state/handoff.md", "written_at": null, "reason": null},
"human_approval": {…today…, "requested_at": null, "via": null, "unattended": false}
```

`load()` applies the same defaults in memory, so a v1 file works before the migration; `save()`
persists them. `skills/ai-init/templates/.ai/VERSION` → `2`.
`skills/project-update/migrations/0002_task_journal.py` follows the WP1 contract
(`VERSION`, `TITLE`, `MOVES = []`, `plan(ctx)`): `ctx.patch_state(_add_defaults)` (idempotent) and
`ctx.create(".ai/reports/<task_id>/events.jsonl", _backfill(state))`. The file must not contain the
words "claude" or "codex" — `test-project-update.sh` asserts that. `gitignore.snippet` gains
`.ai/state/handoff.md`; `templates/.ai/state/README.md` documents the new keys and names
`context-guard.py` as a third writer, of `session.json` only.

### I7 Hook registration

1. `settings.common.json`: the `SessionStart` matcher `"compact"` becomes
   `"startup|resume|clear|compact"`; same command, timeout 15. `UserPromptSubmit` and `PreCompact`
   unchanged.
2. `codex/hooks.json`: add `UserPromptSubmit` (timeout 5), `PreCompact` (15) and `SessionStart`
   (15, same matcher), all `"$HOME/.codex/hooks/context-guard.py"`. `install.sh`'s
   `codex_hook_files` gains `hooks/context-guard.py`; the comment claiming Codex has no compaction
   events is replaced by the fact that it has both, and that the transcript-derived snapshot stays
   Claude-only because the rollout format differs. The trust note in the file's description stays.
3. `context-guard.py` additions: `hook_runtime()` (from the script's own location, then
   `AI_HOOK_RUNTIME`), `ai_root(cwd)` walk-up with an `os.getcwd()` fallback, `write_session()`, and
   `handoff_block(root)` = `subprocess(["python3", STATE_PY, "--root", root, "--runtime", rt,
   "handoff", "--print", "--reason", reason])`, timeout 3, empty on failure. Injected frame:

```
# Task in flight — read this before anything else (written by state.py handoff, not by a model)
<handoff.md>
## Pending questions (2) — answer with `state.py answer …` or fill the file
<prose rendering, or one line when over budget>
Resume with: /ai-task --resume
```

   Constants: `HANDOFF_INJECT_MAX_CHARS = 8000`; `SNAPSHOT_MAX_CHARS = 12000` unchanged and
   Claude-compact-only.

### I8 Path guard

`ai-path-guard-defaults.json` → `protected_config_patterns` gains
`(^|/)\.ai/reports/[^/]+/questions\.md$`, `(^|/)\.ai/reports/[^/]+/events\.jsonl$` and
`(^|/)\.ai/state/handoff\.md$` — write denied, the Read tool allowed, shell readers denied, all
with the existing `WHY_PROTECTED` text. The Bash branch gains, **before** the existing fast path:

```bash
APPROVE_RE='(^|[|;&[:space:]])(python3?[[:space:]]+)?"?[^[:space:]"]*state\.py"?([[:space:]]+--(root|runtime)[[:space:]]+[^[:space:]]+)*[[:space:]]+approve([[:space:]]|$)|(^|[|;&[:space:]])"?\$\{?STATE\}?"?[[:space:]]+approve([[:space:]]|$)'
if ere_match "$APPROVE_RE" "$cmd" \
   && [ -z "${AI_UNATTENDED:-}" ] && task_in_flight; then
    deny "Refusing 'state.py approve' from an agent session.$WHY_APPROVE"
fi
```

**Placement matters and the first draft of this spec had it wrong.** The rule goes *before* the
Bash fast path (`ai-path-guard.sh:201`), not after it. `state.py` lives in the plugin, not under
`.ai/`, so a command like `python3 …/skills/ai-task/state.py --root . approve --by ivan` matches no
`LOOSE_PATTERNS` entry and the fast path would `allow` and return before any later rule ran. The
cost of that placement is one `ere_match` on every Bash call in an `.ai/` project; `task_in_flight()`
(WP7's lazy `jq` read, `ai-path-guard.sh:109-121`) is consulted only *after* the regex matches, so
the common case pays one regex and nothing else.

Gating on `task_in_flight()` is what makes this an extension of WP7's task-scoped protection rather
than a new standing rule: outside a task the guard is silent, and `state.py approve` without a task
in flight dies in `state.py` anyway (`load(root)` → "no task in flight"). The deny therefore fires
only where it can protect something.

`WHY_APPROVE` is a new string used only by this rule; it names the terminal command, the
`[Answer]:` route, the `AI_UNATTENDED` launcher variable and `.ai/policies/safety.md`. New
fixtures: `22-edit-questions-md` (deny), `23-read-questions-md` (allow),
`24-bash-redirect-into-questions` (deny), `25-bash-state-approve` (deny),
`26-bash-state-get-approved-plan` (allow — `approved_plan` has no word boundary),
`27-bash-state-note-approve-word` (allow), `28-bash-state-approve-no-task` (allow — no task in
flight), `codex-hooks/40-bash-state-approve` (deny).
Golden: about 27 added records, no changed record — no existing payload names these paths or
`state.py approve`, the three new patterns cannot become the *named* pattern for an existing path,
`WHY_PROTECTED/TASK/SENSITIVE/VENDOR` are untouched and `ai-git-guard.sh` is not edited.

### I9 Agent and skill contracts

Added to `agents/{ai-discovery,ai-context,ai-risk,ai-planner,ai-implementer,ai-reviewer,ai-security,ai-release}.md`,
their `templates/.ai/agents/*.md` mirrors and `.ai/agents/manager.md`:

```
## QUESTIONS_NEEDED
You never ask the user and never write .ai/reports/*/questions.md. When the work cannot
continue without a human decision, stop at that point and return, before any RESULT:
## QUESTIONS_NEEDED
- question: <one line>
  options: [ "A: <text>", "B: <text>" ]     # 2–6, A first; add "(recommended)" to one
  why_it_blocks: <one line>
  context: <file:line or report path>
Partial output that does not depend on the answer follows under its normal heading.
```

`skills/ai-task/SKILL.md`: §0 begins with `$STATE handoff --print` when a task is in flight; a new
"Questions" section carries the convert → render → `answer` procedure and forbids editing the file;
PLAN turns open questions into `ask` calls before the plan is registered; PLAN REVIEW runs
`$STATE stage human_approval` only after the plan and the review were shown; HUMAN APPROVAL prints
the exact terminal command, names the file alternative and stops — `$STATE done && $STATE archive`
run only after the human approved out of band.

### I10 Environment and config keys

`AI_UNATTENDED=1` (launcher environment: skips the TTY leg, disables the approve rule in any hook
that inherits it, and is recorded in the events) · `AI_RUNTIME=claude|codex` · `AI_HOOK_RUNTIME`
(tests only) · `AI_HANDOFF_NO_PROMPT=1` (omit `last_prompt`) · `AI_CONTEXT_GUARD_STATE` unchanged.
Runtime precedence in `state.py`: `--runtime` > `AI_RUNTIME` > `session.json.runtime` >
`CLAUDECODE` set → `claude` > `unknown`.

### I11 `/sdlc-intent`

Each brainstorm question becomes `ask --topic <slug>` / `answer --topic <slug>`, and the intent
gains a `## Decisions taken` section rendered from `questions --topic <slug> --format md`.
`project-init/templates/intent.md` gains that heading with a comment naming its source.

**Topic questions live in `docs/sdlc/intent/<slug>.questions.md`, always — with or without `.ai/`.**
An intent's questions belong to the document they serve, not to a task; `.ai/reports/<task-id>/`
holds task questions only. This keeps the boundary sharp rather than loose, removes the `sdlc-*`
skills' dependency on `.ai/` entirely, and needs no branch in the code: `--topic` resolves its root
from `docs/sdlc/`, every other mode from `find_root`. Topic questions never emit journal events —
without `.ai/` there is no journal, and one rule beats two — and never block a stage. The record is
the file: the `[Answer]:` trailer carries who answered, how and when.

## Policy conformance

| Policy | How this design honours it |
|---|---|
| Deterministic checks, no new model step (intent Constraints; `~/.claude/CLAUDE.md` "Context hygiene") | Every new command is stdlib Python. The questions file, the journal, the handoff and all three approval legs are deterministic. The only model involvement is *rendering* a question that already exists in a file. |
| Works on all five subscriptions; nothing token-costly by default | WP2 adds no agent, no fan-out and no model call. The handoff injected at session start (≤ 8 000 chars) replaces re-reading the state by hand and is smaller than what it saves. |
| Both runtimes stay at parity | The session-start hook, the journal, the questions file, the handoff and the state shape are identical. Two asymmetries remain and are flagged below: the native picker (Claude only) and the transcript snapshot (Claude only). |
| Git guard rules stay as they are; characterization is byte-exact | `ai-git-guard.sh` is not edited. The approve rule lives in the path guard, which WP7 already extended, and R16 requires an additive-only golden diff. |
| Guard hot-path budget (`docs/hook-performance.md`, WP8's 6 processes / 62 ms) | Added: one in-process regex **before the Bash fast path** plus three prefilter patterns, zero extra processes, < 1 ms; `task_in_flight()`'s `jq` runs only when that regex matches, which is never in normal work. `context-guard` gains one `os.path.exists` and a 1 KB atomic write per *prompt* (not per tool call), and one `state.py` subprocess on the rare PreCompact / SessionStart events. To be measured with the strace recipe and recorded in one line. |
| Hooks stay Python/bash; the payload JSON is not parsed in bash; ~20 ms interpreter startup accepted | No new language, no new hook script, no bash JSON parsing. |
| `project-update` guarantees; a task in flight survives a migration | Migration 0002 uses WP1's `patch_state` / `create`, is idempotent, and `load()` supplies the same defaults in memory so a v1 state works *before* the migration too. |
| Plugin-owned files change only through the skills | Everything ships as plugin files; a project receives them through `/project-update`. `state.py`, `update.py` and (for `session.json` only) `context-guard.py` are the sole writers of `.ai/state/`. |
| No agent commits, merges or deploys; the pipeline ends at human approval | The whole point of R11–R13: the agent can request a gate, print the command and stop. It cannot pass the gate. |
| Implementation stays in the main session; no `opus` fleet | This spec produces an ordered plan for the main session; nothing here fans out. |
| `/sdlc-*` flow, `docs/sdlc/` artefacts, `.ai/reports/<task-id>/` audit trail | The journal and the questions file live exactly where the audit trail already lives. |

No accepted ADR exists yet (`docs/sdlc/adr/` holds only the template), so none is cited. There is
no repo-root `CLAUDE.md`/`AGENTS.md` in this plugin repository; the shipped `CLAUDE.snippet.md` and
`AGENTS.snippet.md` are rendered artefacts and say nothing WP2 contradicts. The two skills whose
descriptions match this work (`ai-task`, `ai-status`) are amended by I9 rather than worked around.

## Flagged concerns

1. ~~**"About ten event types" versus twenty.**~~ **Settled 2026-09-20 by the user: twenty flat
   types.** A reader finds one with a single `grep` and no reader has to look at two fields; every
   type has a command behind it. The intent's wording was amended to match, with the rule that a
   new type is added only when it has its own consumer — anything else reuses `field_set` or
   `note`. Accepted cost: the vocabulary is append-only and will reach roughly 25 by WP5; every
   reader must carry a `default` branch for a type it does not know.
2. ~~**The approve rule is a new guard rule.**~~ **Settled 2026-09-20 by the user: it stays in the
   path guard, gated on `task_in_flight()`.** The intent's sentence freezes *git-guard* rules and
   speaks of *performance* work; WP2 is neither. Arming the rule only while a task is in flight
   makes it an extension of WP7's task-scoped protection rather than a new standing rule, and it is
   silent in a repository with no task. Accepted cost: one regex on every Bash call in an `.ai/`
   project (the rule must precede the fast path — see I8) and about 27 additive golden records,
   proved additive by R16.
3. **Enforcement is asymmetric between the runtimes, and parity is a stated constraint.** On Codex
   the deny rule only exists after the user trusts hooks via `/hooks`; until then the TTY leg and
   the contract are all there is, and the file route degrades to "terminal only" because no
   `session.json` proves a human turn. `/ai-status` must say so out loud in a Codex session. This
   is a real, permanent gap in what the system can *prove* about approvals on Codex.
4. **Question rendering cannot reach parity.** Codex has no picker; the prose path is a genuine
   downgrade in usability, not a stylistic choice. `AskUserQuestion` itself caps at four options,
   so a 5–6 option question degrades to prose on Claude too.
5. **`AI_UNATTENDED` is a blunt instrument.** Set by a launcher, it relaxes the approve rule for
   *every* Bash call in that session, not only for `approve`. That is the intended meaning of
   unattended, but it must be written into `docs/hooks.md` so nobody exports it casually in an
   interactive shell.
6. **The installed `context-guard.py` is ahead of this repository.** The installed copy carries
   `session_model` / `model_window` logic the repo's 378-line version does not. Building on the repo
   copy would silently roll it back on the next `install.sh`. Step 0 of the plan is to sync it in
   and add a test for the model recording; if that step is skipped, WP2 regresses WP-unrelated
   behaviour.
7. ~~**Codex payload shape is assumed, not observed.**~~ **Settled 2026-09-20 by the user: no
   behaviour depends on the payload.** `source` is read only to be written into `session.json`
   (absent → `"unknown"`); whether the transcript snapshot is added is decided, as today, by the
   presence of a fresh snapshot file (`SNAPSHOT_FRESH_SECONDS`); `cwd` falls back to `os.getcwd()`,
   which is where the hook process starts anyway. The fixture recorded at the Codex parity step
   becomes a confirmation, not a precondition. Accepted cost: the hook cannot behave differently on
   `clear` than on `resume` — nothing in this spec asks it to.
8. ~~**Tier.**~~ **Settled 2026-09-20 by the user: T4**, raised from the intent's T3. The line that
   decides it — and that WP4 and WP5 inherit — is the one the intent already draws for the guards:
   a change to *how* a control is evaluated stays low (WP8 was T2, WP7 was T2), a change to *what
   the control decides* does not. WP2 changes who may pass the approval gate. Practical delta: the
   model tier and the stage list do not move (both STRONG), the security review was already going
   to fire under T3's own condition ("authentication, authorization or personal data"), and
   characterization tests were already required by R16 — what T4 adds is R19's mandatory rollback,
   monitoring and idempotency sections. The intent's WP2 row was amended to T4.
9. **`last_prompt` puts user text into the project tree.** Gitignored, capped at 800 characters and
   path-guarded, but a prompt may contain a secret. `AI_HANDOFF_NO_PROMPT=1` opts out; the default
   is to record it, because "the user's latest instruction verbatim" is the single most valuable
   line in the handoff.
10. **Journal durability is best-effort.** `flock` is advisory and unavailable on some platforms;
    the design relies on `O_APPEND` ordering and tolerant readers, and is untested on network
    filesystems. This is acceptable for an audit trail, not for anything that must never lose a
    line — and nothing in WP2 is allowed to depend on it being lossless.
11. ~~**`--topic` questions need `.ai/`.**~~ **Settled 2026-09-20 by the user: they live in
    `docs/sdlc/intent/<slug>.questions.md`, always.** `find_root` stops being the boundary for the
    `sdlc-*` skills; the boundary becomes what the questions are *about*. Accepted cost: an intent
    brainstorm leaves no `events.jsonl` trail, by design — its audit is the file itself.
12. **A pending question blocks stages but not edits.** The scope guard is disarmed between steps
    today, so an agent can still edit while a question is open. Widening the scope guard was
    rejected here (alternative 3) and belongs to WP4's diff-budget work; until then the block is a
    stage-level guarantee only.

## Open questions

None blocking. Every question this spec raised was answered by the user on 2026-09-20:

| Question | Answer |
|---|---|
| Twenty event types or ten? | Twenty flat — one per command that changes state; a new type needs its own consumer. The intent was amended. |
| Is the approve rule a new guard rule? | It stays in the path guard, armed by `task_in_flight()`, placed before the Bash fast path. |
| T3 or T4? | **T4** — the deliverable *is* an authorization control. R19 adds the mandatory rollback, monitoring and idempotency sections. |
| Verify the Codex payload first? | Not needed: no behaviour depends on it. The fixture at the Codex step confirms rather than gates. |
| `--topic` without `.ai/`? | Topic questions live in `docs/sdlc/intent/<slug>.questions.md`, always; no journal events. |
| Per-task token budget | Stays in WP4. The journal captures `from` on `field_set` and `tier_set` — the only value that cannot be backfilled — and reserves nothing else. |

Carried forward, owned by later packages rather than by this one: the per-task token budget and the
scope guard's disarmed window between steps (both WP4, concerns 11 and 12), and the `.ai/AGENTS.md`
router that may revisit where instructions live (WP3).

*Intent open questions 1 and 2 are settled in the Design section and need no further owner.*
