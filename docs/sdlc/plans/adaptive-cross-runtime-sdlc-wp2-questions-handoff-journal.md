# Plan: WP2 — Questions file, handoff, event journal, human-turn approval

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work package 2 of 7) ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp2-questions-handoff-journal.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Risk tier **T4** (spec header; raised from the intent's T3 on 2026-09-20 — the deliverable *is*
an authorization control). Schema `.ai/VERSION` 1 → 2. Depends on WP1 (PRs #15, #16, merged).

This repository has no `.ai/`, so `/ai-task` does not apply: the main session builds one step at
a time and `ai-reviewer` on `opus` reviews each step before its commit. T4 also makes
`ai-security` mandatory — it runs once, over steps 1–7 together, before step 11. Tests: each step
runs the suite it names; `bash tests/run-all.sh` and `pylint $(git ls-files '*.py')` run **once,
to the end**, after step 11, with every failure fixed as one batch.

All seven open flagged concerns were accepted as the spec states them (user, 2026-09-20); see
**Spec flagged concerns** under Risks. Concern 6's sync was chosen at the wider scope: the code
**and** the compaction window (step 0b).

## Files that change

| Path | New / edit | Why | Step |
|---|---|---|---|
| `hooks/context-guard.py` | edit | 0a: adopt the installed 412-line version — `user_settings()`, `session_model()`, `model_window()`, `compact_window(session_id, ctx)`, `thresholds(session_id, ctx)`, the `SessionStart` model record. 0b: `DEFAULT_WINDOW` 133000 → 800000. 5: `hook_runtime()`, `ai_root(cwd)`, `write_session()`, `handoff_block()`, `HANDOFF_INJECT_MAX_CHARS`, SessionStart on every source, PreCompact embeds `handoff.md`, UserPromptSubmit writes `last_prompt_at` | 0a, 0b, 5 |
| `profiles/max.json` | edit | `autoCompactWindow` 133000 → 800000 (capped by Claude Code at the model's own window: 167k on a 200k model, 767k on `[1m]`) | 0b |
| `README.md` | edit | `:146`, `:147`, `:311` — the window rows and the "compacting near 100k" sentence; later, the questions/handoff/journal paragraph and the schema-2 note | 0b, 11 |
| `bin/claude-1m` | edit | the docstring's "the 133 000 that keeps an `opus` session near 100k" is no longer the settings value; the variable still outranks settings.json for one process | 0b |
| `skills/ai-task/state.py` | edit | the whole of I1: runtime detection, `emit()`, `events`, `event`, `note`, `done --abandon`, v2 defaults in `load()`, questions, the pending block, the gate, `reject`, `handoff`, `resume_point` | 1, 2, 3, 4, 6 |
| `tests/test-ai-task-state.sh` | edit | new sections for R1–R3, R5, R8–R11, R13, R17; the journal concurrency case | 1, 2, 3, 4, 6 |
| `tests/test-end-to-end.sh` | edit | `:156` — `approve` under a pipe now exits 5; the call runs with `AI_UNATTENDED=1` and the archived state is asserted to carry `unattended: true` | 3 |
| `settings.common.json` | edit | `SessionStart` matcher `"compact"` → `"startup|resume|clear|compact"` | 5 |
| `tests/test-context-guard.sh` | edit | the model-record case (0a); the window cases (0b); the matcher assertion, the session.json cases, the handoff injection cases, the "injects nothing without `.ai/`" property (5) | 0a, 0b, 5 |
| `hooks/ai-path-guard-defaults.json` | edit | three `protected_config_patterns`: questions, journal, handoff | 7 |
| `hooks/ai-path-guard.sh` | edit | `WHY_APPROVE`; the `APPROVE_RE` rule **before** the Bash fast path (`:201`) | 7 |
| `tests/fixtures/path-guard/2[2-7]-*.json` | new | 22 edit questions.md (deny), 23 read questions.md (allow), 24 redirect into questions.md (deny), 25 `state.py approve` (deny), 26 `get --field approved_plan` (allow), 27 `note … "approve"` (allow) | 7 |
| `tests/fixtures/codex-hooks/40-bash-state-approve.json` | new | the same deny under a Codex shell payload | 7 |
| `tests/test-ai-path-guard.sh` | edit | fixture 28 cannot be a fixture file (the shared root always has a state file): the no-task-in-flight allow goes in the `decide` block with the other task-lifecycle cases | 7 |
| `tests/fixtures/guard-characterization/golden.txt` | rebuilt | `--record`; R16 requires the diff to have no `-` lines | 7 |
| `skills/project-update/migrations/0002_task_journal.py` | new | `VERSION = 2`, `MOVES = []`, `ctx.patch_state(_add_defaults)` + `ctx.create(".ai/reports/<task_id>/events.jsonl", _backfill(state))`; no occurrence of "claude" or "codex" | 8 |
| `skills/ai-init/templates/.ai/VERSION` | edit | `1` → `2` | 8 |
| `skills/ai-init/templates/gitignore.snippet` | edit | `.ai/state/handoff.md` (`.ai/state/*.json` already covers `session.json`) | 8 |
| `skills/ai-init/templates/.ai/state/README.md` | edit | the v2 key list; `context-guard.py` named as a third writer, of `session.json` only; `handoff.md` and where the journal lives | 8 |
| `tests/test-project-update.sh` | edit | fixture `schema-v1`: a v1 project with a task at `implementation` works before and after `--apply` | 8 |
| `tests/fixtures/project-update/schema-v1/` | new | overlay on the v1 templates build; the in-flight task is created by `state.py` inside the test, never written by the fixture | 8 |
| `install.sh` | edit | `codex_hook_files` gains `hooks/context-guard.py`; the "Codex has no compaction events" comment is replaced by the fact that it has both, and that the transcript snapshot stays Claude-only | 9 |
| `codex/hooks.json` | edit | `UserPromptSubmit` (5), `PreCompact` (15), `SessionStart` (15, same matcher), all `"$HOME/.codex/hooks/context-guard.py"` | 9 |
| `tests/test-codex-install.sh` | edit | `:72` installed-file list gains `hooks/context-guard.py`; the three new registrations are asserted once each | 9 |
| `tests/test-install-dry-run.sh` | edit | `:132`, `:157` window assertions (0b); the Codex list (9) | 0b, 9 |
| `agents/{ai-discovery,ai-context,ai-risk,ai-planner,ai-implementer,ai-reviewer,ai-security,ai-release}.md` | edit | the `QUESTIONS_NEEDED` block of I9 | 10 |
| `skills/ai-init/templates/.ai/agents/{discovery,context,risk,planner,implementer,reviewer,security,release}.md`, `.../manager.md` | edit | the same block, mirrored | 10 |
| `skills/ai-task/SKILL.md` | edit | §0 starts with `$STATE handoff --print`; a new **Questions** section (convert → render → `answer`, never edit the file); PLAN converts open questions with `ask`; PLAN REVIEW calls `stage human_approval` only after plan and review were shown; HUMAN APPROVAL prints the exact terminal command and stops | 10 |
| `skills/ai-status/SKILL.md` | edit | step 3 reads `events --last 8` (falling back to `history[]`); `owner_runtime` vs this session, `resume_point`, pending questions, the age of `handoff.md`, any `gate_approved` with `data.unattended`; under Codex, say the deny rule needs `/hooks` trust (concern 3) | 10 |
| `skills/usage-report/SKILL.md` | edit | document the journal and the `task_started`/`task_closed` window; the per-task token budget stays WP4 | 10 |
| `skills/sdlc-intent/SKILL.md` | edit | the brainstorm runs through `ask --topic <slug>` / `answer --topic <slug>`; a `## Decisions taken` section from `questions --topic <slug> --format md` | 10 |
| `skills/project-init/templates/intent.md`, `docs/sdlc/intent/TEMPLATE.md` | edit | the `## Decisions taken` heading with a comment naming its source | 10 |
| `skills/project-update/history/index.json`, `history/blobs/*` | rebuilt | `tools/build-template-history.py`, after each template-editing commit | 8, 10 |
| `docs/hooks.md` | edit | the three new protected paths, the approve rule and `WHY_APPROVE`, `session.json`, the `AI_UNATTENDED` warning (concern 5), the Codex trust asymmetry (concern 3) | 11 |
| `docs/hook-performance.md` | edit | one measured line for the new regex and the per-prompt `session.json` write | 11 |
| `docs/faq.md`, `docs/architecture.md` | edit | schema 2; where questions, the journal and the handoff live; why approval cannot be granted by the agent | 11 |

Untouched on purpose: `hooks/ai-git-guard.sh` (intent constraint; R16 asserts it byte-identical),
`hooks/ai-scope-guard.sh` (spec alternative 3 — the edit-blocking widening is WP4),
`hooks/fable-gate.py` (its installed/repo drift is unrelated to WP2), `profiles/pro.json`
(300000 is already above the 200k model cap, so the cap decides there either way).

## Order of work

One step = one commit, except where an A/B pair is named. Each step ends green on the suite it
names. Branch: `feat/wp2-questions-handoff-journal`.

0. **a — Adopt the installed `context-guard.py`.** Bring `user_settings()`, `session_model()`,
   `model_window()`, the `(session_id, ctx)` signatures of `compact_window`/`thresholds`, the
   `MODEL_WINDOW`/`MODEL_WINDOW_1M` constants and the SessionStart model record into the repo
   copy, with its docstring. Nothing about WP2 yet.
   *Why first:* the installed copy is 412 lines against the repo's 378 (verified on this machine).
   Building step 5 on the repo copy and running `install.sh` would silently roll the model logic
   back (spec concern 6).
   *Proof:* `bash tests/test-context-guard.sh` green with a new case — a `SessionStart` payload
   carrying `model: "opus[1m]"` writes the `.model` file, and a later prompt at 700k neither warns
   nor blocks where a 200k session would have.

   **b — Raise the compaction window to 800000.** `profiles/max.json`, `DEFAULT_WINDOW`, the
   README rows and the `claude-1m` docstring, plus the two `test-install-dry-run.sh` assertions
   and the `test-context-guard.sh` "default window is the Max profile's" check.
   *Not part of WP2* — it changes what every Max install compacts at. It is its own commit,
   placed first so it can be reverted alone, and `DEFAULT_WINDOW` moves with the profile so the
   invariant that test pins stays meaningful. On a 200k model `min(800000, 200000)` means
   compaction near 167k, a warning from 133k and a hold-back from 200k.
   *Proof:* `bash tests/test-context-guard.sh`, `bash tests/test-install-dry-run.sh`.

1. **Journal core in `state.py`.** `runtime()` with the I10 precedence (`--runtime` > `AI_RUNTIME`
   > `session.json.runtime` > `CLAUDECODE` > `unknown`) and the global `--runtime` flag;
   `emit(state, event, detail, data)` = today's `record()` **plus** one journal line under
   `.ai/reports/<task_id>/events.jsonl` (`os.open` with `O_WRONLY|O_APPEND|O_CREAT`, `os.write`,
   `fcntl.flock` where `fcntl` imports, ≤ 4096 bytes, `detail` cut at 500 and `data.error` at
   1000); the `events` reader and the `event` command for hooks; `note decision|rejected|failed`;
   `done --abandon`; `owner_runtime` / `runtime_handoff` on every mutating command; the v2
   defaults of I6 applied in `load()` in memory and persisted by `save()`. Every existing
   `record()` call site becomes `emit()` with its typed `data`, including `from` on `field_set`
   and `tier_set`. `history[]` keeps its exact shape and is not capped.
   *Proof:* `bash tests/test-ai-task-state.sh` green (existing assertions unchanged) plus new
   cases — R8: two processes appending 200 lines each give 400 parseable lines; R9: a task run
   end to end has `len(events) == len(history)` for the mapped types; R10: a mutating command
   with `--runtime codex` after a claude-owned task emits `runtime_handoff{via:resume}`;
   `bash tests/test-end-to-end.sh`.

2. **The questions file.** `ask` (single and `--batch`), `answer` (`Q1=B`, `X:"text"`,
   `--prose "1B 2A 3: text"`), `questions [--pending] [--sync] [--format md|prose|json]`, the I2
   grammar as one regex per line, the `[Answer]:` trailer parsed back and ignored on re-sync, and
   `_pending(root, state)` re-parsing the file on every stage-moving command — exit 4 with the
   exact stderr of I1, state byte-identical. `--topic <slug>` resolves its root from `docs/sdlc/`
   and writes `docs/sdlc/intent/<slug>.questions.md`, emits no journal event and blocks nothing.
   *Implementation note:* `main()` today calls `find_root(args.root)` unconditionally and `die`s
   without `.ai/`. Topic mode must branch before that call, or R17's "with or without `.ai/`"
   is impossible.
   *Proof:* new sections in `tests/test-ai-task-state.sh` — R1 (`ask` then `questions --format
   json` round-trips the question), R2 (`cmp` the question block before and after a `--sync` that
   picks up a hand-edited `[Answer]: B`), R3 (each of the nine blocked commands exits 4 and
   `current.json` is byte-identical; each of the eleven unblocked ones exits 0), R5 (`ask` under
   `AI_UNATTENDED=1` ends with `WAITING_FOR_ANSWERS <file> <ids>`), R17 (a fixture with
   `docs/sdlc/` and **no** `.ai/` completes ask → answer → render).

3. **⚠ Riskiest — the gate: request, terminal and unattended routes.** `stage human_approval`
   appends gate question `G1`, sets `human_approval.requested_at` and emits
   `gate_requested{gate,requested_at}`. `approve` succeeds only when (a) `os.isatty(0)` **or**
   `AI_UNATTENDED` is set in its own environment, (b) a `gate_requested` event exists for this
   task, and (c) no **non-gate** question is pending — otherwise exit 5 with the exact stderr of
   I1 (two texts: the general one, and the "no gate was requested" one). `reject --by --why`
   emits `gate_rejected` and leaves the stage where it is. Under the flag the event and the state
   carry `unattended: true`.
   *Why it is riskiest:* it is the one change that alters **what the control decides** — the line
   that made this T4. A mistake either locks the human out of their own pipeline or lets the
   agent through. It is deliberately split: the terminal and unattended routes land here, the
   file route in step 6, so each is reviewed on its own.
   *Spec delta this step resolves:* R3 blocks `done` and `close` on a pending question, and
   `stage human_approval` leaves `G1` pending — so a granted approval would block the very next
   command. `approve` and `reject` therefore **write `G1`'s `[Answer]:` line** (`A`, or
   `B: <why>`) with the command's trailer. They are the gate's `answer`; R2's "only writers" rule
   is read as being about `Q*` ids, and `answer` still refuses a `G*` id with the I2 message.
   *Proof:* new cases — `approve` under a pipe exits 5 and the state is byte-identical;
   under `pty.spawn` exits 0 and emits `gate_approved{via:terminal, tty:true, actor:"human"}`;
   under `AI_UNATTENDED=1` exits 0 with `via:unattended, unattended:true`; with no
   `gate_requested` event it exits 5 with the second text; with a pending `Q2` it exits 5 and
   with only `G1` pending it does not. `bash tests/test-end-to-end.sh` with `:156` amended.

4. **`handoff.md`.** `handoff [--print] [--reason stage|precompact|manual|session-start]` renders
   the six parts of I4 from the state, the journal (`note` events newest first), `questions.md`
   (pending ids) and `session.json` (the last prompt, omitted under `AI_HANDOFF_NO_PROMPT=1`);
   ≤ 30 lines by construction; empty sections print `- none`; emits `handoff_written{reason,
   lines}`; rewritten by every stage-moving command; `resume_point` maintained on `step` /
   `step-done` / `stage`; `archive` deletes the file.
   *Proof:* R6 — a task with 10 notes and 8 recorded prompts renders `wc -l` ≤ 30; each of the six
   headings is present; `archive` removes it; `handoff --print` on a task with no `session.json`
   prints `> none recorded`.

5. **`context-guard.py` — session.json, injection, both runtimes.** `hook_runtime()` (from the
   script's own location, then `AI_HOOK_RUNTIME`), `ai_root(cwd)` walking up with an
   `os.getcwd()` fallback, `write_session()` (tmp + `os.replace`), `handoff_block(root)` shelling
   out to `state.py handoff --print` with a 3 s timeout and an empty result on failure,
   `HANDOFF_INJECT_MAX_CHARS = 8000`. SessionStart runs on **every** source: it writes
   `session.json{runtime, session_id, source, started_at}` and, when a task is in flight, injects
   the frame of I7.3; on Claude with a fresh snapshot file it prepends that frame to the snapshot.
   PreCompact runs `handoff --reason precompact` first, then builds the snapshot with
   `handoff.md` verbatim in place of the `current.json` dump. UserPromptSubmit keeps today's
   measurement and adds `last_prompt_at = now` and `last_prompt` (≤ 800 chars) when a task is in
   flight. `settings.common.json`'s SessionStart matcher widens to
   `startup|resume|clear|compact`. **No decision branches on a payload key** (R7): `source` is
   recorded and never read back, `cwd` falls back to `os.getcwd()`, and the transcript snapshot is
   still gated on a fresh snapshot file.
   *Proof:* `bash tests/test-context-guard.sh` — the existing "SessionStart:`<source>` injects
   nothing" cases stay green because that fixture project has no `.ai/`; the matcher assertion
   becomes `startup|resume|clear|compact`; new cases with a `.ai/` project and a task in flight
   assert the frame on each of the four sources, a payload carrying **neither** `source` nor `cwd`
   behaving identically, `session.json` being written atomically with the right `runtime` under
   `AI_HOOK_RUNTIME=codex`, `last_prompt_at` advancing on a prompt, `AI_HANDOFF_NO_PROMPT=1`
   omitting the text, and the guard failing open when `state.py` is missing or hangs.

6. **The gate's file route (R13).** `questions --sync` on an `[Answer]: A` filled into `G1`
   grants approval with `via:file` — but only when `session.json.last_prompt_at ≥
   human_approval.requested_at`, or `AI_UNATTENDED` is set. With no `session.json` the file route
   is refused and the message names the terminal route.
   *Why here:* it is the only requirement that depends on the hook's `session.json`, which step 5
   introduces.
   *Proof:* new cases — sync with no `session.json` refuses; with a `last_prompt_at` **before**
   `requested_at` refuses; after recording a prompt, grants and emits
   `gate_approved{via:file, actor:"human"}`.

7. **The path guard.** Three `protected_config_patterns` (questions, journal, handoff — write
   denied, `Read` allowed, shell readers denied, existing `WHY_PROTECTED` text); `WHY_APPROVE`
   naming the terminal command, the `[Answer]:` route, `AI_UNATTENDED` and
   `.ai/policies/safety.md`; the `APPROVE_RE` rule placed **before** the Bash fast path at
   `:201`, gated on `[ -z "${AI_UNATTENDED:-}" ] && task_in_flight`.
   *Placement is the whole point:* `state.py` lives in the plugin, not under `.ai/`, so
   `python3 …/skills/ai-task/state.py --root . approve --by ivan` matches no `LOOSE_PATTERNS`
   entry and the fast path would `allow` and return before any later rule ran. `task_in_flight()`
   is consulted only after the regex matches, so the common case pays one in-process `ere_match`
   and no extra process.
   *Proof:* `bash tests/test-ai-path-guard.sh` with fixtures 22–27 and the no-task case in the
   `decide` block; `bash tests/test-ai-scope-guard.sh`; then
   `bash tests/test-guard-characterization.sh --record` and **R16**: `git diff` of
   `golden.txt` has no `-` lines, `git diff --stat hooks/ai-git-guard.sh` is empty, and
   `grep -c 'WHY_PROTECTED\|WHY_TASK\|WHY_SENSITIVE\|WHY_VENDOR' hooks/ai-path-guard.sh` is
   unchanged.

8. **Schema 2 and the migration.** *Commit A:* `migrations/0002_task_journal.py`,
   `templates/.ai/VERSION` → `2`, the `gitignore.snippet` line, the state `README.md` rewrite,
   and the `schema-v1` fixture plus its sections in `test-project-update.sh`. *Commit B:*
   `python3 tools/build-template-history.py` and the rebuilt index — it reads committed trees, so
   it must follow A (WP1 plan, Risks 3).
   *Proof:* `bash tests/test-project-update.sh` — R14: a v1 project with a task at
   `implementation` answers `state.py get` before **and** after `--apply`; the backfilled journal
   has exactly `len(history)` lines, each with `data.backfilled: true`; a second `--apply` prints
   `^0 automatic`; `grep -in 'claude\|codex' skills/project-update/migrations/0002_*.py` is empty;
   `bash tests/test-scaffold-idempotency.sh`, `bash tests/test-ai-path-guard.sh`.

9. **Codex parity.** `install.sh`'s `codex_hook_files` gains `hooks/context-guard.py` and the
   stale comment is replaced; `codex/hooks.json` registers it on the three events;
   `test-codex-install.sh`'s installed-file list and registration assertions;
   `test-install-dry-run.sh`'s Codex list.
   *Proof:* `bash tests/test-codex-install.sh` (the `PreToolUse` count stays 4; the three new
   events are registered once each and are not duplicated by a second install),
   `bash tests/test-install-dry-run.sh`, `bash tests/test-dual-runtime-install.sh`. The Codex
   `SessionStart` payload fixture recorded here **confirms** the shape; nothing gates on it
   (spec concern 7).

10. **Agent and skill contracts.** *Commit A:* the `QUESTIONS_NEEDED` block in the eight agent
    definitions, their eight `templates/.ai/agents/*.md` mirrors and `.ai/agents/manager.md`; the
    `ai-task`, `ai-status`, `usage-report` and `sdlc-intent` skills; `project-init/templates/
    intent.md` and `docs/sdlc/intent/TEMPLATE.md`. *Commit B:* the history rebuild again, for the
    templates A touched.
    *Proof:* `grep -c 'QUESTIONS_NEEDED' agents/*.md skills/ai-init/templates/.ai/agents/*.md`
    is 1 on each of the seventeen files; `grep -n 'handoff --print' skills/ai-task/SKILL.md`;
    `grep -n 'events --last' skills/ai-status/SKILL.md`; `bash tests/test-codex-agent-render.sh`,
    `bash tests/test-ai-status-root.sh`, `bash tests/test-project-update.sh`.

11. **Docs, then the gate.** `docs/hooks.md` (the three protected paths, the approve rule,
    `session.json`, the `AI_UNATTENDED` warning of concern 5 and the Codex trust asymmetry of
    concern 3), `docs/hook-performance.md` (one measured line, strace recipe), `README.md`,
    `docs/faq.md`, `docs/architecture.md`.
    *Proof:* `grep -n 'AI_UNATTENDED' docs/hooks.md` shows the warning; then **once, to the end:**
    `bash tests/run-all.sh` and `pylint $(git ls-files '*.py')`, every failure fixed as one batch,
    one re-run. `ai-security` runs over steps 1–7 before this step's commit.

**Riskiest step: 3** (the gate), split so the terminal leg and the file leg are reviewed
separately. Step 7 is the second-riskiest — it is the one that can silently change an existing
deny message — which is why R16's additive-only golden check is its own gate.

## Risks

**What could this break?**

1. **Every `state.py` command starts writing a journal line.** `emit()` replaces `record()` at
   every call site, so a failure to create `.ai/reports/<task_id>/` breaks commands that work
   today. `init` and `quick` create the directory before the first `emit()`; every other command
   creates it lazily with `exist_ok=True`. A journal append that fails must never fail the
   command — the state write is the contract, the journal is best-effort (concern 10).
   Noticed by: `tests/test-ai-task-state.sh` and `tests/test-end-to-end.sh`.
2. **`load()` returning more keys changes `state.py get` output.** Anything asserting the full
   JSON document, and `/ai-status`'s reading of it, sees five new keys. `update.py` reads
   `current.json` directly rather than through `state.py`, so `patch_state`'s `after == self.state`
   comparison is unaffected — but only because of that; a future reader that goes through
   `state.py` would see defaults that are not on disk. Stated in the state `README.md` (step 8).
3. **The gate blocks the pipeline's own last commands.** Resolved in step 3 (`approve`/`reject`
   write `G1`'s answer). Without it `S approve && S done` — the sequence
   `tests/test-end-to-end.sh:156-157` and `skills/ai-task/SKILL.md:337-339` both use — exits 4 on
   `done`.
4. **`tests/test-end-to-end.sh` cannot approve any more.** Its `S approve --by "the human"` runs
   with stdin piped, which is exactly what step 3 refuses. The call takes `AI_UNATTENDED=1` and
   the archived-state assertion gains `unattended == true`, so the test proves the flag is
   recorded rather than hiding it.
5. **The path-guard rule fires on a command that only mentions the word.** `state.py get --field
   approved_plan` and `state.py note decision "approve the invoice flow"` must pass; fixtures 26
   and 27 exist for exactly these. Conversely `$STATE approve` unexpanded and a quoted absolute
   path must be caught — both branches of `APPROVE_RE`. Noticed by: fixtures 25–27 and
   `codex-hooks/40`.
6. **The characterization golden changes a record instead of adding one.** The three new patterns
   widen `LOOSE_PATTERNS`, so more commands reach the per-token pass — but no corpus path lies
   under `.ai/reports/` or is `.ai/state/handoff.md`, so no path's *named* pattern moves and no
   existing verdict flips. R16 is the check, not the argument: any `-` line in the golden diff
   stops the step.
7. **`SessionStart` now runs on every source, in both runtimes.** Four times as many invocations,
   each with one `os.path.exists` and, only with a task in flight, one `state.py` subprocess at a
   3 s timeout inside a 15 s hook timeout. It must fail open exactly as today: an unreadable
   payload, a missing `state.py`, a hang, or a project without `.ai/` all inject nothing.
   Noticed by: the fail-open cases in `tests/test-context-guard.sh`, which already cover the
   shape.
8. **The per-prompt `session.json` write puts user text in the project tree** (concern 9,
   accepted). It is gitignored by `.ai/state/*.json`, capped at 800 characters, path-guarded, and
   opt-out with `AI_HANDOFF_NO_PROMPT=1`. The write is atomic, so a hook killed mid-write never
   leaves a half file for `state.py handoff` to read.
9. **`.ai/VERSION` becomes 2, so an older installed plugin exits 2 on an updated project** —
   WP1's R8, by design. Rollback means reinstalling the newer plugin, never editing `.ai/VERSION`
   by hand.
10. **Step 0b changes every Max install's compaction point** from near 100k to near 167k, and it
    has nothing to do with WP2. It is its own commit, first, revertable alone. `bin/claude-1m`
    still works — `CLAUDE_CODE_AUTO_COMPACT_WINDOW` outranks `settings.json` for one process —
    but its reason for existing is now the per-model cap rather than a different number, and its
    docstring says so.
11. **Two history rebuilds (steps 8 and 10).** `build-template-history.py` reads committed trees;
    a template edited but not committed is missing from the index and the "history covers every
    current template" assertion in `test-project-update.sh` fails. Hence the A/B pair in both
    steps, and `test-project-update.sh` is in the proof of both.
12. **pylint runs over every tracked `.py`.** `state.py` roughly triples; the house `.pylintrc`
    disables the convention and design-limit checks, but `state.die` is registered under
    `never-returning-functions` and any new `die`-like helper needs the same entry.
    `0002_task_journal.py` follows `0001`'s shape. Run pylint in step 1, not only at the end.
13. **Both runtimes, one script.** `context-guard.py` is installed to `~/.claude/hooks/` and now
    to `~/.codex/hooks/` by the same `install_file`; `hook_runtime()` derives the runtime from its
    own location, so a single file behaves correctly in both without a payload key. Noticed by:
    `tests/test-dual-runtime-install.sh` and the `AI_HOOK_RUNTIME` cases in step 5.
14. **Callers of `state.py`:** `skills/ai-task/SKILL.md`, `skills/ai-status/SKILL.md`,
    `tests/test-end-to-end.sh`, `tests/test-project-update.sh` (the in-flight fixture) and now
    `hooks/context-guard.py`. Exit codes 0/1/2 keep their meaning; 4 and 5 are new. Every caller
    that runs a stage-moving command must be able to explain exit 4 — step 10 is where the
    skills learn to.

**Spec flagged concerns — disposition (all accepted by the user, 2026-09-20):**

| # | Disposition |
|---|---|
| 1 | Settled in the spec: twenty flat event types |
| 2 | Settled in the spec: the rule lives in the path guard, armed by `task_in_flight()` (step 7) |
| 3 | Accepted as a permanent gap; `/ai-status` says it out loud under Codex (step 10) and `docs/hooks.md` states it (step 11) |
| 4 | Accepted: prose rendering everywhere without a picker, and for any question over four options |
| 5 | Accepted: written into `docs/hooks.md` as a warning against exporting it interactively (step 11) |
| 6 | Resolved by step 0a, at the wider scope the user chose — 0b takes the window with it |
| 7 | Settled in the spec: no behaviour depends on the payload; the Codex fixture in step 9 confirms |
| 8 | Settled in the spec: T4; R19's sections are below |
| 9 | Accepted: recorded by default, `AI_HANDOFF_NO_PROMPT=1` opts out (step 4 and step 5) |
| 10 | Accepted: journal durability is best-effort; Risks 1 makes "nothing depends on it" concrete |
| 11 | Settled in the spec: topic questions live in `docs/sdlc/intent/<slug>.questions.md` |
| 12 | Accepted: a stage-level guarantee only; widening the scope guard stays WP4 |
| new | Risks 3 — `approve`/`reject` write `G1`'s answer line; the spec does not say who closes the gate question |
| new | Risks 2 — `load()`'s in-memory defaults make `get` disagree with the file until `save()` |

## Proof (tests)

Final gate `bash tests/run-all.sh` and `pylint $(git ls-files '*.py')` once, after step 11.

| Req | Test / command | Step |
|---|---|---|
| R1 | `ask` then `questions --format json` round-trips question, options and recommendation | 2 |
| R2 | hand-edit `[Answer]: B`, `questions --sync`; `cmp` the question block before/after; the journal has `question_answered{via:"file"}` | 2 |
| R3 | each of `stage triage plan step step-done remediate approve done close` exits 4 with the I1 text and leaves `current.json` byte-identical; `get set risks modules note ask answer questions handoff events archive` and `done --abandon` exit 0 | 2 |
| R4 | `tests/test-ai-path-guard.sh` fixtures 22–24; `grep -n 'questions --pending' skills/ai-status/SKILL.md`; no `cat`/`tail` of the file anywhere in the skills | 7, 10 |
| R5 | every agent file carries the block once; `ask` under `AI_UNATTENDED=1` prints `WAITING_FOR_ANSWERS <file> <ids>` as its last stdout line | 2, 10 |
| R6 | a task with 10 notes and 8 prompts: `state.py handoff --print \| wc -l` ≤ 30; the six headings present; `archive` deletes the file | 4 |
| R7 | `tests/test-context-guard.sh` with a payload carrying `source` and `cwd`, and one carrying neither — identical output; `.ai/` present → the frame, absent → nothing | 5 |
| R8 | two processes × 200 appends → 400 parseable lines, no interleaving inside a line | 1 |
| R9 | existing state tests green; `len(journal) == len(history)` over a full run; backfill line count equals history length | 1, 8 |
| R10 | `--runtime codex` on a mutating command after a claude-owned task emits `runtime_handoff{via:"resume"}` and sets `owner_runtime`; `handoff --help` has no `--to` | 1, 4 |
| R11 | `approve` under a pipe exits 5; under `pty.spawn` exits 0; without `gate_requested` exits 5 with the second text; with a pending `Q2` exits 5; under `AI_UNATTENDED=1` exits 0 with `unattended: true` | 3 |
| R12 | fixtures 25, 26, 27, the no-task allow in the `decide` block, `codex-hooks/40`; the rule precedes `:201` | 7 |
| R13 | `--sync` on `G1` before a recorded prompt refuses; after one, grants with `via:"file"`; with no `session.json`, refuses | 6 |
| R14 | `schema-v1` fixture: `state.py get` exits 0 before and after `--apply`; `.ai/VERSION` is `2`; a second `--apply` is `0 automatic` | 8 |
| R15 | `bash tests/test-codex-install.sh` — `context-guard.py` installed and registered once on each of the three events | 9 |
| R16 | `git diff tests/fixtures/guard-characterization/golden.txt` has no `-` lines; `git diff --stat hooks/ai-git-guard.sh` empty; `WHY_*` texts unchanged | 7 |
| R17 | a fixture with `docs/sdlc/` and no `.ai/` completes ask → answer → render; no `events.jsonl` is created; no stage is blocked | 2 |
| R18 | `bash tests/run-all.sh`; `grep -rn 'Agent(\|subagent\|model:' skills/ai-task/state.py` empty | 11 |
| R19 | this file has **Rollback**, **Monitoring** and **Idempotency and retry**; `ai-security` ran | 11 |

## Rollback

- **Before merge:** each step is its own commit on `feat/wp2-questions-handoff-journal`; revert
  the step's commit. Step 0b reverts alone and is unrelated to the rest. Steps 8 and 10 revert as
  A/B pairs — reverting A without B leaves a history index naming a template that no longer
  exists, and `test-project-update.sh` says so.
- **After merge, the plugin:** revert the merge commit and reinstall (`install.sh`). This removes
  the three `codex/hooks.json` registrations and the widened `SessionStart` matcher; a stale
  registration left behind in a user's `~/.codex/hooks.json` points at a `context-guard.py` that
  still exists and still fails open, so nothing breaks while it is cleaned up by hand.
- **After merge, a project at schema 2:** there is no down migration. Reinstalling a pre-WP2
  plugin makes `update.py` exit 2 on that project (WP1 R8, by design) — the fix is to reinstall
  the newer plugin, not to edit `.ai/VERSION`. To neutralise WP2 in a project without downgrading:
  delete `.ai/state/handoff.md` and `.ai/reports/<id>/questions.md` (the pending block is computed
  from the file, so removing it unblocks every stage), and leave `events.jsonl` — it is an
  append-only audit trail that nothing depends on. `current.json` keeps the five new keys; the
  pre-WP2 `state.py` ignores unknown keys and the pre-WP2 scope guard reads only
  `approved_plan`, so a task in flight survives the downgrade.
- **The golden file:** `tests/test-guard-characterization.sh --record` re-records it from whatever
  the guards do; after a revert, re-record and confirm the diff against the pre-WP2 golden is
  empty in **both** directions.
- **Step 0b specifically:** reverting restores `autoCompactWindow` 133000 and `DEFAULT_WINDOW`
  133000 together. A user whose own `~/.claude/settings.json` sets 800000 explicitly is
  unaffected either way — that value outranks the profile.

## Monitoring

Nothing here emits metrics; what a human can see is what `/ai-status` and `/usage-report` read out
of the journal, at zero model cost.

- **`/ai-status`** (step 10) gains, for the task in flight: `owner_runtime` against this session's
  runtime — and a warning when they differ; `resume_point`; pending question ids and their file;
  the age of `.ai/state/handoff.md` (stale means the hooks are not running); the last eight
  journal events via `state.py events --last 8`, falling back to `history[]` when no journal
  exists; and **any `gate_approved` whose `data.unattended` is true, called out as such** —
  that line is the one signal that an approval did not come from a human at a terminal. Under
  Codex it also states that the `state.py approve` deny rule only exists once hooks are trusted
  via `/hooks` (concern 3).
- **`/usage-report`** (step 10) documents the journal and uses the `task_started` → `task_closed`
  window to attribute per-task duration, and counts `gate_approved{via:"unattended"}` across
  tasks. The per-task **token** budget stays WP4; no field is reserved for it here.
- **`docs/hook-performance.md`** (step 11) gets one measured line for the new `ere_match` on the
  Bash path and the per-prompt `session.json` write, taken with the strace recipe already in that
  file, so the 6-processes / 62 ms budget stays a number rather than a claim.
- **What is deliberately not monitored:** the journal is best-effort (concern 10). A missing line
  is not an alert and no check treats the journal as complete.

## Idempotency and retry

- **Migration 0002.** `ctx.patch_state(_add_defaults)` sets keys only when absent and returns the
  same object when nothing changed, so `update.py` records no item and a re-run prints
  `0 automatic`. `ctx.create()` is a no-op when the target exists, so the backfilled
  `events.jsonl` is written once and never appended to twice. A run interrupted between the two
  leaves `.ai/VERSION` at 1 (WP1 writes it last), and the next `--apply` completes both.
- **The journal append.** `os.open(O_WRONLY|O_APPEND|O_CREAT)` + a single `os.write` of one
  complete line under `fcntl.flock(LOCK_EX)` where `fcntl` imports. Appends are not deduplicated
  and are not meant to be: an event recorded twice is a visible duplicate, never a corrupt line.
  A failed append never fails the command that emitted it, and readers skip unparseable lines and
  report the count on stderr.
- **`questions --sync`.** Parses the file, rewrites only `[Answer]:` lines whose parsed value
  differs from what the state holds, and leaves the question text byte-identical (R2). Running it
  twice emits `question_answered` once: the second run finds nothing changed. A trailer written by
  a previous run is parsed back and ignored, so syncing an already-synced file is a no-op.
- **`approve`.** Re-running it on an already-granted gate is a no-op that prints the existing
  grant rather than emitting a second `gate_approved` — the journal must show one approval per
  gate, or the `unattended` signal above is unreadable.
- **`handoff`.** A pure function of the state, the journal and `session.json`, written atomically
  (tmp + `os.replace`); rendering it twice gives the same file except its timestamp line.
- **`ask --batch`.** Appends `Q<n>` blocks with ids allocated from the highest existing id in the
  file, so a retry after a crash adds new questions rather than renumbering the old ones. A batch
  file submitted twice therefore duplicates its questions — that is visible in the file and is
  the honest failure, not a silent merge.
