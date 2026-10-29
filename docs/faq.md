# FAQ

Why something was blocked, why a stage ran or did not, and how to change it.

## Something was blocked and I think it should not have been

Read the reason first: every refusal names the rule and the way out.

- **`SCOPE_CHANGE_REQUIRED`** — the file is not in the task's files. Widen the
  task in place, `state.py start --amend --files "+<path>" --why "…"`; it is
  journaled, the task is not re-planned. A file that belongs to a different
  change is recorded with `state.py memory risk add` and left for its own task.
- **A secret** (`.env`, `secrets/`, a key, a dump) — refused for read and
  write everywhere under `.ai/`. A test fixture that trips it goes into
  `allow_patterns` of the project's `.ai/policies/path-guard.json`
  (`.env.example`, `fixtures/*.sql` and `migrations/*.sql` are allowed
  already).
- **A control file** (`.ai/state/`, `task.md`, `events.jsonl`,
  `.ai/policies/*.json`, the installed hooks) — write-refused always; the
  policies and the runtime settings also while a task is in flight. Edit them
  between tasks, in your own editor.
- **A git command** — force push, a protected branch, `--no-verify`, a deploy
  command, `npm publish`. The list and the per-repository exemptions are in
  `~/.claude/hooks/ai-git-guard.json` ([hooks.md](hooks.md)).
- **`CONSENT_REQUIRED`** — a `git commit` or `git push` that was not the
  command you picked in the dialog. Pick it, or run it yourself.
- **`DECISION_PENDING`** — a decision is open in the dialog; answer it, or
  settle it in your terminal with the command the message prints.

A guard's refusal is not a hint to reword the command. If the rule is wrong
for your repository, change the rule.

## Why did my task's mode go up by itself?

`verify` and `close` re-score reversibility and domain from the real diff. A
hunk that reaches `**/Payment/**`, a migration that matches
`irreversible_content` (`DROP`, `TRUNCATE`, `DELETE FROM`, `ALTER … DROP`,
`RENAME`), a file in `config/` — the re-score prints the axis that moved and
the mode rises. It never falls during a task; lowering it is yours, from your
own terminal (`start --mode light --by <name>` is refused from an agent).

## Why was there no review?

Light mode: `close` runs a review only when one of the two facts is red. A
green suite on this tree and every change inside the task is the review for
a W ≤ 2 change. Guarded and full always get one pass, and the mode is the
weight's — `--mode guarded --by <name>` on `start` raises it for free when you
want a review anyway.

## `verify` refused to run the suite again

Two whole-suite runs are the budget per task (`tests.max_suite_runs` in
`weight.json`; eight in a batch task). The third exits 6 `SUITE_BUDGET` and
prints the command; running it is yours, from your terminal or as the pick in
the dialog. The budget exists because "one failure, one fix, one run" is the
expensive loop: read the log, classify every failure, fix the regressions as
one batch, run once more with `--after-fix "<what the batch fixed>"`.

## `close` says `verify required` although the suite was green

The tree changed after the green run — an edit, a formatter, a generated
file. `close` compares tree hashes, not timestamps. Run `verify --scope all`
again, or, when only documents changed since the green run and `testing.md`
names `doc_tests`, the scoped command `close` prints.

## `close` exits 4

A question is pending. `step-done`, `verify`, `close` and `approve` all wait
for it. Answer in the conversation (`state.py answer Q1=B`) or on the
`[Answer]:` line of `.ai/reports/<task-id>/task.md` §Questions followed by
`state.py questions --sync`. Never on the human's behalf.

## Why does the pipeline never commit, merge or deploy?

Because the commit is the point where a human reads the diff, and the guards
exist to keep that reading honest. `/rr-ship` writes the commit message and
suggests the command; with the dialog on, the command you pick runs once,
verbatim; otherwise you run it. `gh pr merge`, a push to a protected branch
and every deploy command are refused from an agent whatever the mode.

## Why did `/rr-build` not spawn any agents?

Because the session implements, and a light task needs nothing read that
`grep -n` cannot find. Agents are for reading a lot (`Explore`,
`log-reader`), judging a lot (`ai-discovery`), arguing (`ai-reviewer`) and
design (`architect`); each runs on a named trigger ([agents.md](agents.md)).
A batch build is the exception: its implementers and fixers are subagents.

## How do I get a review on STRONG for a guarded task?

Raise the mode: `state.py start … --mode full --by <name>`. Raising is free
and journaled; the review, the written plan and the approval gate follow.

## Where does the verification command come from?

From `.ai/policies/testing.md`, which `/rr-setup` proposes and you confirm.
`verify_command` must run the whole fast suite without fail-fast and exclude
e2e; `e2e_command` runs once at the end of a guarded or full task, or is
`none`. If the block is empty, `/rr-build` takes the command from CI or the
project's instruction file, says so, and asks you to write it down.

## What if the project has no e2e suite?

Write `e2e_command: none`. An empty line means "not written down yet" and the
next task goes looking for it. A task whose change reaches no e2e flow passes
`verify --scope all --e2e not-applicable "<why>"`.

## I reinstalled the plugin. Why does my project still follow the old rules?

Because a project owns its copies: `weight.json`, `testing.md`, the router,
the managed block. `/rr-setup --update` brings them up — migrations first,
then a three-way merge that keeps every edit — and `/rr-status` says when a
project is behind ([project-update.md](project-update.md)). The shared files
under `<home>/riskrails/ai/` update with the plugin unless the project
overrides one.

## My `CLAUDE.md` block got much shorter. Where did the rules go?

Into files that load on demand. The block holds only the rules an agent is
unsafe without (2 048 B in a project, 2 560 B globally); `.ai/AGENTS.md`
routes every job to the policy that answers it; `routing.md` in the home holds
the model ladder. Everything you wrote outside the block is untouched.

## Why are my MCP servers off in this project?

A connected server is in the system prompt of every turn whether a task calls
it or not. The scaffolded `.claude/settings.json` sets
`enableAllProjectMcpServers: false`; a project enables what nearly every task
needs in `policies/tooling.md`, and a task names anything extra in one line and
turns it off again.

## Why did Claude send a subagent to read one file?

Because the file is over 4 000 lines or 250 KB and `cap-large-read.py` refused
the unbounded `Read`. The cheap reader returns the matching ranges with
`file:line`; an explicit `limit` within the budget passes when you really need
the range in the session. Codex has no read hook, so there the rule is prose.

## Why is the session model `opusplan` on Pro?

Opus in plan mode, Sonnet when executing: the expensive model is spent on the
plan, the cheaper one on typing it out. `architect` and `ai-reviewer` pin
`opus` so a Sonnet session cannot weaken them. On Max the session is Opus 5.5
[1m]; `/model opus` gives a 200k window, cheaper per turn for a small task.

## Where is Fable used?

On `architect` only, on Max with `--fable yes` (the default there), at
`xhigh`, for design questions. Nothing else ever runs on it; `runtime-gate`
sends it to Opus while Fable is rate-limited or the weekly limit is 90% used.
`--fable no` leaves `architect` on the Opus session.

## The installer changed my Codex model from Astra to Sol

By design: the session model is the largest single cost. Sol at `high` (Pro)
or `medium` (Plus) is the session; Astra stays the EXPERT escalation.
`config.toml` is edited key by key and the previous version kept under
`backups/<date>/` ([installation.md](installation.md)).

## Why do the Codex guards not seem to do anything?

Codex runs a hook only after you trusted it in `/hooks`, and an entry that
changed in an upgrade loses its trust. Open `/hooks` and approve. Nothing on
screen says a hook is skipped ([known-risks.md](known-risks.md)).

## Why is a guarded review on Codex running on Sol?

A Codex agent file's model beats the model asked for at launch, and the
`ai-reviewer` file pins STRONG. Claude Code passes the tier per call, so a
guarded review runs on Sonnet there ([routing.md](routing.md)).

## Can an agent edit these policies?

Not during a task: `.ai/policies/` and the runtime settings are
write-protected while a task is in flight, so a run cannot change the rules it
is judged by; `.ai/policies/*.json` and the installed guards are protected
always. Between tasks, in your editor, every file is yours — the weight table,
the path-guard additions, the dialog switch, `testing.md`.

## Where do the questions, the journal and the handoff live?

| What | Where | Written by |
|---|---|---|
| the task | `.ai/state/state.json` | `state.py` |
| the journal | `.ai/reports/<task-id>/events.jsonl` | `state.py`, the hooks through `event` |
| the record | `.ai/reports/<task-id>/task.md` | `state.py`, rendered; questions answered on the `[Answer]:` lines |
| the handoff | `.ai/state/handoff.md` | `state.py`, thirty lines, injected at session start |
| the session | `.ai/state/session.json` | `context-guard.py` |
| the decision and the picks | `.ai/state/decision.json`, `consent.jsonl` | `state.py`, `dialog-gate.py` |
| the compact record | `.ai/memory/` | `close`, in packages mode ([local-memory.md](local-memory.md)) |

## A subagent asked me a question and then stopped. Why?

It did not ask; it returned `QUESTIONS_NEEDED` and stopped, which is the
contract. The session records the questions (`state.py ask --batch`), you
answer, and the work resumes with the answer in the brief.

## Why can the agent not approve its own plan?

Because the point of full mode is a human reading the tree before it is
committed. `approve` refuses without a terminal on stdin and is refused from
an agent session by the path guard; the dialog's pick is yours to make and is
consumed once. `AI_UNATTENDED=1` is the one way around it, for CI, and it
stamps every approval `unattended`.

## How do I approve in CI, where there is no human?

Export `AI_UNATTENDED=1` in the job's environment — never in an interactive
shell — and read `/rr-status` afterwards: it names every unattended approval
and deletion.

## I moved a task to Codex and now Claude refuses every command

`handoff --to codex` hands the task over; until Codex resumes it, every state
change from elsewhere exits 7 `RUNTIME_HANDOFF_PENDING`. Resume it there with
the command the handoff printed, or take it back with `handoff --to claude`.

## `/rr-build` says `old surface`

The task was started by a plugin older than 3.0. The new commands refuse it;
`status`, `handoff` and `questions` still answer. Finish it with the version
that started it, or drop it with `state.py close --abandon`.

## What do the old command names do?

`/ai-task`, `/ai-init`, `/ai-status`, `/ai-audit`, `/project-init`,
`/project-update`, `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan` and
`/usage-report` are aliases of the `rr-*` skills for one version
(`ROADMAP.md`). `/ai-init` → `/rr-setup`, `/project-update` → `/rr-setup
--update`, `/ai-task` → `/rr-build`, `/sdlc-*` → `/rr-spec` and `/rr-plan`,
`/usage-report` → `/rr-status --cost`.

## What is `.ai/VERSION`?

The project's schema, 10 today; a project initialised before the file existed
is 0. Migrations under `skills/project-update/migrations/` bring it up during
`/rr-setup --update`, in order, inside the dry run, and the version is written
last ([project-update.md](project-update.md)). It is separate from the task
state's own schema (7), which `state.py` carries in `state.json`.
