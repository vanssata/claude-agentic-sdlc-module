# Architecture

Five moving parts: host-wide routing settings, a knowledge base on disk, a
pipeline that runs in a session, a state file that connects them, and hooks that
make the boundaries real.

## The routing layer

`install.sh` writes the settings a session runs on: the model for the detected
plan, its fallback chain, the default effort, the compaction window, the output
caps, and `CLAUDE_CODE_SUBAGENT_MODEL`. It also writes one managed block into
`~/.claude/CLAUDE.md` carrying the tier table, the effort rules, the context
hygiene rules and the pipeline rules.

This half used to be a separate plugin. It is here because the two were giving
contradictory instructions — which agent reviews, where a change starts, who
designs — and a rule that exists twice in two places is a rule nobody follows.

## The knowledge base

`/ai-init` writes `.ai/` into the project. It is committed, and it is meant to be
edited by humans afterwards — the scaffold never overwrites an existing file.

```
.ai/
  AGENTS.md            the entry point: read this first
  project/             what this system IS, discovered from the code
  policies/            what agents may and may not do here
  agents/              the role contract for each pipeline agent
  workflows/           feature, bugfix, refactoring, hotfix, investigation
  templates/           the shape of every artifact a task produces
  state/current.json   the task in flight (NOT committed)
  reports/<task-id>/   that task's artifacts (committed — the audit trail)
```

The split matters: `agents/*.md` in `~/.claude/agents/` are **static** and
identical in every project, so their prompts stay cache-friendly; `.ai/agents/*.md`
and `.ai/policies/*.md` are the **project layer** they read at the start of a run.
Nothing dynamic — a ticket, a diff, test output — is ever read from disk by an
agent; it arrives in the prompt.

## The pipeline

```
REQUEST
  → DISCOVERY            ai-indexer, then ai-discovery in parallel per area
  → CONTEXT              ai-context, one structured summary
  → IMPACT ANALYSIS      ai-discovery again, this time on blast radius
  → RISK CLASSIFICATION  ai-risk, one tier from risk-tiers.json
  → PLAN                 ai-planner (opus at T3/T4, ai-expert at T5)
  → PLAN REVIEW          ai-reviewer, T3 and above
  → IMPLEMENTATION       the session itself, one step at a time
  → TEST                 ai-tester
  → ADVERSARIAL REVIEW   ai-reviewer, T2 and above
  → SECURITY REVIEW      ai-security, T4 and T5
  → RELEASE REPORT       ai-release
  → HUMAN APPROVAL       the pipeline stops here, always
```

The manager is the **main session**, not a subagent. Claude Code has no cheap
orchestrator process, and an orchestrator that cannot see the conversation is
worse than none. What keeps the session's context small is that every reading
stage is delegated and every artifact is written to a file and referred to by
path.

Stages are lightweight for a T0 change and heavy for a T5 one. None is skipped —
that judgement is exactly what risk classification exists to replace.

## Why the session implements

The original design has a separate Implementer agent. Here the main session
implements, for two reasons: it already holds the plan and the context, so
handing a step to a subagent means re-establishing both; and the property that
actually matters — that only the step's files change — is enforced by a hook
rather than by which process makes the edit.

`ai-implementer` still exists, for mechanical pattern-copying work and for when
you ask for it explicitly.

## The state file

`.ai/state/current.json` is written only by `skills/ai-task/state.py`, atomically.
It holds facts, never transcripts:

```
task_id · goal · workflow · risk_tier · current_stage · affected_modules
context_summary_ref · approved_plan { ref, current_step_id, steps[] }
completed_steps · test_status · review_status · security_status · open_risks
next_action · human_approval · created_at · updated_at · history[]
```

It does three jobs at once:

- **survival** — a task resumes after `/clear`, a crash, or a day off;
- **enforcement** — `ai-scope-guard` derives the current step's allowed files
  from it, so the plan is not advice;
- **audit** — `history[]` records every stage transition with a timestamp, and
  `state.py archive` moves the finished record into `.ai/reports/<task-id>/`,
  where it is committed alongside the change it describes.

It is git-ignored on purpose: it describes a session, not the repository.

## The hooks

Five, registered once in `~/.claude/settings.json`:

| Hook | Event | Scope | Armed by |
|---|---|---|---|
| `cap-large-read.py` | `PreToolUse:Read` | every session | always |
| `project-scaffold.sh` | `Setup:init` | a new project | `/init` |
| `ai-git-guard` | `PreToolUse:Bash` | every repository | always |
| `ai-path-guard` | `PreToolUse` on reads and writes | this project | the presence of `.ai/` |
| `ai-scope-guard` | `PreToolUse` on writes | this step | `current_stage == "implementation"` and a current step |

The path and scope guards check for their arming condition in their first few
lines and exit silently otherwise, which is why they can be registered globally
and still change nothing in a repository that never ran `/ai-init`.

All three share `hooks/lib/ai-hook-common.sh` and the same contract: read the
payload from stdin, exit 0 silently to allow, or print a deny object and exit 0.
They **fail open** — a guard that cannot parse its input allows the call, because
these are defence-in-depth, and a broken guard must never make the tool unusable.

## Cost

Context length, not model choice, dominates the cost of a session, so:

- the main session delegates reading and keeps summaries, not output;
- discovery fans out five or six agents at once, which is exactly why that
  fan-out is on the cheapest tier;
- `ai-indexer` runs first so each discovery agent gets a file list instead of
  globbing the repository itself;
- artifacts live on disk and are referenced by path between stages.

The expensive tier is reserved for design, adversarial review and the conclusions
a human reads.
