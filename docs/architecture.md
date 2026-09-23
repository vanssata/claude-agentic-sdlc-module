# Architecture

Five moving parts: host-wide routing settings, a knowledge base on disk, a
pipeline that runs in a session, a state file that connects them, and hooks that
make the boundaries real.

Everything below is the same under Claude Code and under Codex except where it
says otherwise. The runtime-specific part is deliberately thin — see
[The two adapters](#the-two-adapters) at the end.

## The routing layer

`install.sh` writes the settings a session runs on: the session model, its
fallback behaviour, the default effort and the output caps. Agent models are pinned
in each agent definition, never through `CLAUDE_CODE_SUBAGENT_MODEL`.

Under Claude Code that is a deep merge into `~/.claude/settings.json` from
`profiles/{pro,max}.json` plus `settings.common.json`. Under Codex it is six
managed keys in `~/.codex/config.toml` — `model`, `model_reasoning_effort`, and
four under `[agents]` — taken from `profiles/codex-{plus,pro}.json`, one file
per ChatGPT plan, which is also what the agent renderer reads, so a Codex routing decision has exactly one home.

It also writes one managed block into the global instruction file —
`~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md` — carrying the tier table, the
effort rules, the context hygiene rules and the pipeline rules. The two blocks
say the same things with the models of their runtime substituted in.

This half used to be a separate plugin. It is here because the two were giving
contradictory instructions — which agent reviews, where a change starts, who
designs — and a rule that exists twice in two places is a rule nobody follows.
The same reasoning is why there is one module for both runtimes rather than two
that drift.

## The knowledge base

`/ai-init` writes `.ai/` into the project. It is committed, and it is meant to be
edited by humans afterwards — the scaffold never overwrites an existing file.

```
.ai/
  AGENTS.md            the entry point: read this first
  project/             what this system IS, discovered from the code
  policies/            what agents may and may not do here (incl. tooling/MCP)
  agents/              the role contract for each pipeline agent
  workflows/           feature, bugfix, refactoring, hotfix, investigation
  templates/           the shape of every artifact a task produces
  state/current.json   the task in flight (NOT committed)
  reports/<task-id>/   that task's artifacts (committed — the audit trail)
```

There is exactly one `.ai/` tree however many runtimes the project uses. Only the
instruction file that points at it differs — `CLAUDE.md`, `AGENTS.md`, or both —
and `scaffold-ai.sh --runtime both` creates both over the same tree.

The split matters: the installed agent definitions (`~/.claude/agents/*.md`,
`~/.codex/agents/*.toml`) are **static** and identical in every project, so their
prompts stay cache-friendly; `.ai/agents/*.md` and `.ai/policies/*.md` are the
**project layer** they read at the start of a run. Nothing dynamic — a ticket, a
diff, test output — is ever read from disk by an agent; it arrives in the prompt.

## The pipeline

```
REQUEST
  → DISCOVERY            ai-indexer, then ai-discovery in parallel per area
  → CONTEXT              ai-context, one structured summary
  → IMPACT ANALYSIS      ai-discovery again, this time on blast radius
  → RISK CLASSIFICATION  ai-risk, one tier from risk-tiers.json
  → PLAN                 ai-planner (STRONG at T3/T4, ai-expert at T5)
  → PLAN REVIEW          ai-reviewer, T3 and above
  → IMPLEMENTATION       the session itself, one step at a time
  → TEST                 step tests in each step; the suite once after the last
                         step, then e2e once (ai-tester in team)
  → ADVERSARIAL REVIEW   ai-reviewer, T2 and above
  → SECURITY REVIEW      ai-security, T4 and T5
  → RELEASE REPORT       ai-release
  → HUMAN APPROVAL       the pipeline stops here, always
```

The manager is the **main session**, not a subagent. Neither runtime has a cheap
orchestrator process, and an orchestrator that cannot see the conversation is
worse than none. What keeps the session's context small is that reading is
delegated or bounded, and every artifact is written to a file and referred to by
path.

Stages are lightweight for a T0 change and heavy for a T5 one. None is skipped —
that judgement is exactly what risk classification exists to replace.

## Who does a stage: the pipeline profile

`pipeline_profile` in `.ai/policies/risk-tiers.json` decides who runs each
stage, never whether it runs. The default, `solo`, is for one developer who
knows the codebase — the setting the playbook describes for a team of one to
five: CLAUDE.md, plan mode and a feedback loop, with light review. It runs
T0–T3 in direct mode (no ceremony, cheap readers, one `sonnet` review at T2,
one `opus` review and a plan-mode plan the human approves at T3) and the full
pipeline from T4.

- Discovery, context, impact and risk come from the request plus `grep -n`,
  and up to T2 are recorded in one `state.py triage` call — four audit-trail
  entries, one round trip. `ai-risk` on `opus` only when a T3+ answer is not
  obvious.
- T0 and T1 have no plan stage: the session says which files it will touch and
  edits. T2 gets a short inline step list in a single `task.md`; `ai-planner`
  on `opus` from T3, `ai-expert` at T5.
- Tests come in three scopes: a step runs only the tests its plan step names
  (`step_test_command`, scoped to its files), the project's verification
  command runs once after the last step, and the e2e suite runs once after
  that, at the end of the task. Output piped through `tail`; `log-reader` when
  it is long.
- The adversarial review is always a subagent from T2 up — a context that did
  not write the code — on `sonnet` at T2 and `opus` above.
- Security review at T4/T5 is unchanged. The release report is inline up to T3
  and becomes the commit message body.

Each subagent costs its own context window and a system prompt; in `solo` the
pipeline spawns none for a T1 change and one for a T2 change, against nine or
ten in `team`. That is the whole difference, and it is the difference between a
task that fits a Pro or Plus usage window and one that does not.

## Why the session implements

The original design has a separate Implementer agent. Here the main session
implements, for two reasons: it already holds the plan and the context, so
handing a step to a subagent means re-establishing both; and the property that
actually matters — that only the step's files change — is enforced by a hook
rather than by which process makes the edit.

`ai-implementer` still exists, for mechanical pattern-copying work and for when
you ask for it explicitly.

## The state file

`.ai/state/current.json` is written by `skills/ai-task/state.py`, atomically —
and, during a schema migration, by `skills/project-update/update.py` the same
way.
It holds facts, never transcripts:

```
task_id · goal · workflow · risk_tier · current_stage · affected_modules
context_summary_ref · approved_plan { ref, current_step_id, steps[] }
completed_steps · test_status · e2e_status · review_status · security_status · open_risks
next_action · human_approval · created_at · updated_at · history[]
owner_runtime · resume_point · questions { file, pending[] } · handoff { file, written_at, reason }
human_approval { …, requested_at, gate_id, requested_session, rejected_at, via, unattended }
```

The last two lines are schema 2 (`.ai/VERSION`). Migration
`skills/project-update/migrations/0002_task_journal.py` adds those keys to an
existing project and backfills a journal from `history[]`, marking every
backfilled line so nobody mistakes reconstruction for observation.

It does three jobs at once:

- **survival** — a task resumes after `/clear`, a crash, or a day off;
- **enforcement** — `ai-scope-guard` derives the current step's allowed files
  from it, so the plan is not advice;
- **audit** — `history[]` records every stage transition with a timestamp, and
  `state.py archive` moves the finished record into `.ai/reports/<task-id>/`,
  where it is committed alongside the change it describes.

It is git-ignored on purpose: it describes a session, not the repository.

### Four files around it

The state file answers "where is the task". Schema 2 adds four files that answer
questions a single JSON document was the wrong shape for, and each has exactly
one writer:

| File | Written by | Answers |
|---|---|---|
| `.ai/reports/<task-id>/events.jsonl` | `state.py emit` | what happened, in order, and **which runtime** did it |
| `.ai/reports/<task-id>/questions.md` | `state.py ask` / `answer` / `questions --sync` | what the pipeline needs a human to decide |
| `.ai/state/handoff.md` | `state.py handoff` | what a session that has just lost its context needs first |
| `.ai/state/session.json` | `hooks/context-guard.py` | which runtime is driving, and when the human last took a turn |

**The journal** is append-only: one complete line per `os.write`, under
`flock`, never rewritten — and not writable by the actor it audits: `state.py
event`, the command a hook uses to add a line, refuses the gate and lifecycle
types, because those are emitted by the transition that earns them. A journal an
agent can author is not an audit trail. It is deliberately **best-effort** — a journal append
that fails never fails the command that emitted it, because the state write is
the contract and the journal is the record of it. Readers skip an unparseable
line and say how many they skipped. Nothing treats the journal as complete, and
no alert depends on it; what it buys is `/ai-status` and `/usage-report` reading
a task's history at zero model cost.

**The questions file** is how a subagent asks without being able to ask. A
subagent has no user; the eight agent contracts therefore tell it to **return**
`QUESTIONS_NEEDED` with the question rather than guess, and the manager writes
it into `questions.md`, where a human fills in an `[Answer]:` line. `state.py
questions --sync` parses the file, writes the answers back into the state, and
leaves the question text byte-identical. A pending question blocks the stage
commands with exit 4: the pipeline stops on an unanswered question instead of
picking an answer for itself.

**The handoff** is derived — a pure function of the state, the journal and
`session.json`, thirty lines, rewritten on every stage change and injected by
`context-guard.py` at a session start or after a compaction. Because it is
derived, nothing about it may fail a task: a handoff that cannot be rendered is
a missing convenience, not a broken run.

**Approval is the one thing none of this can grant.** At T3+ the pipeline stops
at a gate that only a human closes — from their own terminal, where `approve`
checks for a TTY, or by answering the gate's question in `questions.md`, which
is accepted only behind a human turn recorded in `session.json` by a hook the
agent is forbidden to run. `ai-path-guard` refuses `state.py approve` from an
agent session outright. An unattended launcher can set `AI_UNATTENDED=1` and
skip all of it — and the approval is then stamped `unattended` in the state and
in the journal, for ever, where `/ai-status` reads it out. See
[hooks.md](hooks.md) for the rules themselves.

## The hooks

Registered once per runtime — in `~/.claude/settings.json`, in
`~/.codex/hooks.json`:

| Hook | Event | Scope | Armed by | Runtimes |
|---|---|---|---|---|
| `ai-git-guard` | `PreToolUse:Bash` | every repository | always | both |
| `ai-path-guard` | `PreToolUse` on reads and writes | this project | the presence of `.ai/` | both |
| `ai-scope-guard` | `PreToolUse` on writes | this step | `current_stage == "implementation"` and a current step | both |
| `cap-large-read.py` | `PreToolUse:Read` | every session | always | Claude |
| `project-scaffold.sh` | `Setup:init` | a new project | `/init` | Claude |
| `runtime-gate.py` | `PreToolUse`/`PostToolUse:Agent`, `SubagentStart`/`SubagentStop`, `StopFailure` (Fable) | the top tier, the plan's budgets, the quota | always; budgets only with `profile.json` | both (`fable-gate.py`, `codex-model-gate.py` are shims) |
| `context-guard.py` | `UserPromptSubmit`, `PreCompact`, `SessionStart` | the session's context, and `session.json` | always | both — snapshot Claude-only |

The path and scope guards check for their arming condition in their first few
lines and exit silently otherwise, which is why they can be registered globally
and still change nothing in a repository that never ran `/ai-init`.

All three share `hooks/lib/ai-hook-common.sh` and the same contract: read the
payload from stdin, exit 0 silently to allow, or print a deny object and exit 0.
They **fail open** — a guard that cannot parse its input allows the call, because
these are defence-in-depth, and a broken guard must never make the tool unusable.

Under Codex there is one extra thing they must do first. The runtime calls its
tools by different names, and one of them edits several files at once, so
`ai-hook-common.sh` normalises before any rule runs: `apply_patch` becomes
`Edit`, `shell`/`exec_command`/`local_shell` become `Bash`, and the paths inside
an `apply_patch` body are extracted from its `*** Add/Update/Delete File:` and
`*** Move to:` headers so each one is checked on its own. The guards' rules are
written once and see the same shapes in both runtimes.

Two Codex facts shape the rest. Its hooks must be reviewed and trusted through
`/hooks` before they run at all — until you do, nothing is enforced, including
the rule that keeps an agent from running `state.py approve`. The plugin cannot
close that gap for you: approving a hook is the user's act by design, and a
runtime where a plugin could do it would have the larger problem. `/ai-status`
says so under Codex, and the installer ends with the same reminder. And its read
tool is not on the hook path, which is why `cap-large-read.py` has no Codex
counterpart; the rule is written into `AGENTS.md` instead of being mechanical.

## Cost

Context length, not model choice, dominates the cost of a session, so:

- the main session delegates reading and keeps summaries, not output;
- in the `solo` profile the fan-out happens once, in `/ai-init`, and a task
  spawns an agent only where the tier needs a second context window;
- where discovery does fan out, it is on the cheapest tier, and `ai-indexer`
  runs first so each agent gets a file list instead of globbing the repository;
- on Pro and Team Pro the session model is `opusplan`, so Opus is paid for the
  plan and Sonnet for the implementation; on Max and Team Max the session is
  Opus 5 and Fable is spent only on `architect`; under Codex the Plus profile
  keeps the session at `medium`, three threads and no `xhigh`;
- below T2 a task writes no report files and runs the test suite once;
- a file too large to open is read by the cheapest model, which returns the
  matching ranges with `file:line` rather than the file;
- tools and MCP servers are off by default — they sit in the system prompt of
  every turn whether a task calls them or not — and are enabled per project
  only when nearly every task needs them, per task otherwise
  (`.ai/policies/tooling.md`);
- artifacts live on disk and are referenced by path between stages.

The expensive tier is reserved for design, adversarial review and the conclusions
a human reads.

## The two adapters

Everything above is provider-neutral. What is not:

| Concern | Claude Code | Codex |
|---|---|---|
| install root | `~/.claude/` | `~/.codex/` |
| settings | deep merge into `settings.json` | six managed keys in `config.toml` |
| instruction block | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| agent definition | Markdown + YAML frontmatter | one TOML file per agent |
| hook registration | a `hooks` block in settings | `hooks.json`, trusted via `/hooks` |
| model ladder | haiku → sonnet → opus → Fable/Opus | Terra → Terra → Sol → Astra |

Two consequences are worth naming, because they are not cosmetic.

**Agent precedence is inverted.** Codex resolves a value written in an agent's own
file *ahead* of the value passed when it is spawned. Asking for a stronger model
at spawn time therefore does nothing there. The renderer handles this by writing
an explicit `model` and `model_reasoning_effort` into every agent — an omitted
`model` would fall back to the Terra `[agents]` default — and by emitting
`ai-risk-strong` and `ai-planner-strong`, which pin Sol, for the T3/T4 re-runs
that Claude Code does with `model: opus` — and `ai-expert-strong`, which the
runtime gate reroutes `ai-expert` to, by `agent_type`, while the EXPERT model
is unavailable. `tests/test-codex-agent-render.sh`
asserts each role's *effective* model, not the one that was requested.

**There is no `StopFailure`.** On Claude Code `runtime-gate` learns about a Fable rate limit
from a dedicated failure event. Codex has no such event, so there it
watches `SubagentStop` and marks the gate only when the evidence actually points
at an EXPERT agent: its name in the text, an explicit expert `model`, an agent
file pinned to the expert model, or an expert launch inside the last five minutes.
Both sides then do the same thing — rewrite an EXPERT launch to the tier below,
say so in the agent's context, and expire on their own. The budget checks differ
in one way: Codex parses `ask` but does not support it, so where Claude Code asks,
Codex allows the launch and explains it in `additionalContext`.

`config.toml` gets one more piece of care. There is no comment-preserving TOML
writer in the standard library, so `scripts/merge-codex-config.py` edits the
managed lines surgically, then parses the file before and after and refuses to
write unless the only keys that differ are the ones it manages. That check, not
the editing, is the safety contract.
