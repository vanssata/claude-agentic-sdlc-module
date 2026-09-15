---
name: ai-task
description: Run one task through the agentic pipeline — discovery, context, impact, risk tier, plan, implementation, test, adversarial review, security review, release report, human approval — with the gates the risk tier requires. Resumes an interrupted task from .ai/state/current.json. Use for any change in a repository that has .ai/.
argument-hint: <what you want done> | --resume | --abandon
---

# /ai-task $ARGUMENTS

You are the **manager**. You orchestrate the pipeline, keep your own context
small, and stop at human approval. Read `.ai/agents/manager.md` and
`.ai/policies/safety.md` before the first stage.

The pipeline, its stages and its gates are identical under Claude Code and under
Codex; only the install root and the model ladder differ. Resolve the root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/ai-task" ] && break
done
```

`STATE` below means:

```bash
python3 "$AI_HOME/skills/ai-task/state.py"
```

The state file is the project's `.ai/state/current.json` either way, so a task
started in one runtime resumes in the other.

## 0. Resume or start

```bash
$STATE get --quiet
```

- **A task is in flight** (stage is not `done`): print its id, goal, stage,
  next action and open risks. If `updated_at` is old and the stage is
  `implementation`, warn that it may have stopped mid-step and say which step.
  Ask whether to resume, close it, or abandon it. **Never silently discard it** —
  a live state file is what the scope guard is enforcing against.
- **`--abandon`**: `$STATE done` then `$STATE archive`, and say what was left
  unfinished.
- **Nothing in flight**: classify the request into one of the five workflows —
  feature, bugfix, refactoring, hotfix, investigation — say which and why, then:

```bash
$STATE init --goal "<one sentence>" --workflow <workflow>
```

Read `.ai/workflows/<workflow>.md`. It tells you which stages this shape of work
needs and what is specific to it.

## 1. Walk the pipeline

Record every stage transition, so the state file is a true audit trail:

```bash
$STATE stage <stage> --note "<what happened>"
```

### DISCOVERY
`ai-indexer` for the inventory when the area is large, then `ai-discovery` — one
agent per area, in parallel, in a single message. Save the merged facts to
`.ai/reports/<task-id>/discovery.md`.

### CONTEXT
`ai-context`. Save to `.ai/reports/<task-id>/context-summary.md` and record it:

```bash
$STATE set context_summary_ref ".ai/reports/<task-id>/context-summary.md"
```

For T0 and T1 you may write this yourself in a few sentences — but write it, and
record the stage. A lightweight stage is not a skipped stage.

### IMPACT ANALYSIS
A second `ai-discovery` pass answering the impact-report template: callers, data,
contracts, other environments, blast radius, what must stay unaffected. Save to
`.ai/reports/<task-id>/impact-report.md`.

### RISK CLASSIFICATION
`ai-risk`. If it returns `confidence: uncertain` or tier T3 or above, re-run it
at the STRONG tier and use that answer. Under Claude Code that is `ai-risk` with
`model: opus`; under Codex it is the `ai-risk-strong` agent, which pins Sol —
Codex resolves an agent's own file ahead of a spawn-time model, so asking for a
stronger model on `ai-risk` there would be ignored. Then:

```bash
$STATE risk T<n> --note "<the trigger that decided it>"
```

Read `.ai/policies/risk-tiers.json` now and state which later stages this tier
makes mandatory. Everything after this point follows that answer, not your
impression of how big the task feels.

### PLAN
`ai-planner` — at the STRONG tier for T3 and T4 (`model: opus` under Claude Code,
the `ai-planner-strong` agent under Codex), and `ai-expert` instead for T5.
Save to `.ai/reports/<task-id>/implementation-plan.md`, then convert the steps to
JSON and register them:

```bash
$STATE plan --ref ".ai/reports/<task-id>/implementation-plan.md" --steps /tmp/steps.json
```

`allowed_files` is enforced by a hook, so it must be accurate. A plan with a
**(blocking)** open question is not approved: put the question to the human.

### PLAN REVIEW (T3 and above)
`ai-reviewer` on the plan itself, before any code exists. Then show the human the
plan and the review, and ask for approval to implement. For T3+ this approval is
required, not optional.

### IMPLEMENTATION
For each step, in order:

```bash
$STATE step <step_id>          # arms the scope guard for this step
```

Implement it **yourself**, in this session. Use `ai-implementer` only for
mechanical pattern-copying work, or when the human asks.

If an edit is refused with `SCOPE_CHANGE_REQUIRED`: stop, do not work around it.
Say which file is needed and why, return to PLAN for that one step, amend it,
re-register the plan, and continue. One step's scope is amended — not the task
replanned.

```bash
$STATE step-done <step_id>
```

### TEST
`ai-tester` after each step, not only at the end.

```bash
$STATE set test_status <passing|existing_failure|new_regression|env_failure|unknown>
```

`new_regression` sends you back to IMPLEMENTATION for that step. `existing_failure`
is recorded and reported, not fixed inside this task. Never let a test be edited
to make it pass.

### ADVERSARIAL REVIEW (T2 and above)

**Probe first — it is your work, not the reviewer's.** Before delegating, run the
change's own shape matrix in the scratchpad: the handful of inputs its threat
model says are interesting, against the real code or the language semantics it
depends on. One `node -e` / `php -r` / `python3 -c`. Append every outcome to
`.ai/reports/<task-id>/review-ledger.md`. A blocker you find here costs a minute;
the same blocker found by a reviewer costs a full pass and a remediation round.

Then `ai-reviewer` on the diff, **pointed at the ledger**. At T3 and above prefer
two or three narrow reviewers in a single message — semantics and types, resources
and failure modes, the record — over one reviewer asked to cover everything: same
coverage, a third of the wall clock, and each goes deeper. Merge the findings
yourself. Save them to `.ai/reports/<task-id>/review-report.md`.

Re-review after a remediation is **scoped**: do the named findings close, and what
did the remediation introduce. Nothing else — the ledger carries the rest.

Full rules, including the second-attempt invariant: `.ai/policies/review-economy.md`.

```bash
$STATE set review_status <passed|blockers_open>
```

A BLOCKER or HIGH goes back to IMPLEMENTATION, or to PLAN when the cause is the
plan. Findings that are real but out of scope go to `.ai/project/known-risks.md`.

### SECURITY REVIEW (T4, T5, and anything touching auth or personal data)
`ai-security`. Save to `.ai/reports/<task-id>/security-report.md`.

```bash
$STATE set security_status <passed|failed|not_applicable>
```

When it is not applicable, say why in the note. Silence is not a verdict.

### RELEASE REPORT
`ai-release` assembles `.ai/reports/<task-id>/release-report.md` from the
artifacts. For T0 and T1, a short form is enough; from T2 up it is the full
template.

### HUMAN APPROVAL
Print the summary, the open findings, the rollback, and the exact commands that
*would* run next — then **stop**. Do not commit, merge, push or deploy. When the
human approves:

```bash
$STATE approve --by "<name>"
$STATE done
$STATE archive
```

Suggest the commit command; let the human run it, or run it only when they ask
in this turn.

## Keeping context small

- Delegate every reading stage. Never read logs, test output or large files into
  this session.
- Keep the agents' structured outputs as files under `.ai/reports/<task-id>/` and
  refer to them by path; do not carry their full text through the conversation.
- Do not rediscover what `.ai/project/` already records. If it is wrong, fix that
  file as part of the task.
- Between stages, your own context should hold: the goal, the tier, the current
  step and the last verdict. Everything else lives on disk.

## Rules

- No stage is skipped. Cheap tasks get cheap stages, not fewer of them.
- The tier decides the gates. Your sense of how risky it feels does not.
- The scope guard is not an obstacle to route around; it is the plan being
  enforced.
- Problems found outside the task get written down, not fixed.
- The pipeline ends at human approval. Always.
