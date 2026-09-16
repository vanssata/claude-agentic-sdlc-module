---
name: ai-task
description: Run one task through the agentic pipeline — discovery, context, impact, risk tier, plan, implementation, test, adversarial review, security review, release report, human approval — with the gates the risk tier requires and the delegation the project's pipeline_profile allows (solo by default, stages up to T2 inline). Resumes an interrupted task from .ai/state/current.json. Use for any change in a repository that has .ai/.
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

Read `.ai/workflows/<workflow>.md`. It tells you what is specific to this shape
of work.

Then read the profile:

```bash
jq -r '.pipeline_profile // "team"' .ai/policies/risk-tiers.json
```

The stages are the same in every profile; the profile decides **who does each
one**. `pipeline_profiles.<profile>.delegated_stages[<tier>]` in that file lists
the stages that go to a subagent. Every other stage you do yourself, inline, in a
few lines — and you record it. `solo`, the default, is written for one developer
who knows this codebase: their request is the first source of context,
deterministic tools are the second, and a subagent is spawned only where a
second context window buys something. Until the tier is known, act as for T2.

## 1. Walk the pipeline

Record every stage transition, so the state file is a true audit trail:

```bash
$STATE stage <stage> --note "<what happened>"
```

### TRIAGE — discovery, context, impact and risk

**solo, T0–T2:** take the entry points from the request — if it names none, ask
one question rather than searching the repository. Confirm each with `grep -n`,
follow the callers with `grep -rn`, and check what `.ai/project/` already
records. Decide the tier from the trigger table in `.ai/policies/risk-tiers.json`
and name the trigger; when two tiers are arguable, take the higher. Then record
all four stages in one call:

```bash
$STATE triage T<n> --note "<the trigger>" --context "<entry points, callers, what must stay unaffected — a few lines>"
```

No report file below T2. For T2, start `.ai/reports/<task-id>/task.md` with
that context in the fixed shape of `.ai/templates/task-context.md`, at most ~30
lines with `file:line` for every fact, and record its path:

```bash
$STATE set context_summary_ref ".ai/reports/<task-id>/task.md"
```

**T3 and above, or `team`:** the stages run one at a time and are recorded one
at a time. `ai-discovery` — one agent per area in parallel, after `ai-indexer`
when the area is large — into `discovery.md`; `ai-context` for the summary; a
second `ai-discovery` pass for `.ai/templates/impact-report.md`; `ai-risk` with
`model: opus` for the tier (`ai-risk-strong` under Codex, whose agent files
outrank a spawn-time model), re-run when it says `confidence: uncertain`.
In `solo` you may still write context and impact yourself at T3 when the area
is one you know; the risk call at STRONG is not optional there.

```bash
$STATE risk T<n> --note "<the trigger that decided it>"
```

Delegate below T3 only on a trigger from `delegate_anyway_when`: one
`ai-discovery` for an area the developer says is unfamiliar, or for an
`UNKNOWN` the plan depends on. Never the six-agent fan-out — that is
`/ai-init`'s job, once.

Now state which later stages the tier makes mandatory and which of them this
profile delegates. Everything after this point follows that answer, not your
impression of how big the task feels.

### PLAN — only when the tier needs one

**T0, T1:** no plan. Say in one line which files you will touch and go to
IMPLEMENTATION. The scope guard is not armed for these tiers; the line you
just wrote is the scope.

**T2 in solo:** a short numbered list of steps, each with its files, appended
to `task.md` — usually one to three steps. Use plan mode only when the change
spans several modules. Register it:

```bash
$STATE plan --ref ".ai/reports/<task-id>/task.md" --steps /tmp/steps.json
```

**T3 and T4:** `ai-planner` with `model: opus` (`ai-planner-strong` under
Codex), in plan mode. **T5:** `ai-expert`. Save to `.ai/reports/<task-id>/implementation-plan.md` following
`.ai/templates/implementation-plan.md`, register the steps as above.

`allowed_files` is enforced by a hook from T2 up, so it must be accurate. A
plan with a **(blocking)** open question is not approved: put the question to
the human.

### PLAN REVIEW (T3 and above)

`ai-reviewer` on the plan itself, before any code exists. Then show the human the
plan and the review, and ask for approval to implement. For T3+ this approval is
required, not optional.

### IMPLEMENTATION

```bash
$STATE stage implementation
```

T0 and T1 have no steps: make the edit. From T2, for each step in order:

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

### TEST — the feedback loop, once

After the **last** step, not after each one. Run the verification command from
the **Verification** section of `.ai/policies/testing.md`; if that section is
empty, take it from the project `CLAUDE.md` or the CI config and write it into
`testing.md` as part of this task, so the next task has it. Pipe the output
through `tail -40`. When more than that matters, hand the full output to
`log-reader`; use `ai-tester` in the `team` profile or when the test setup is
unfamiliar.

During a step, run only that step's own single test (`single_test` in
`testing.md`) when it is cheap and the step touched logic. T0 runs nothing.

```bash
$STATE set test_status <passing|existing_failure|new_regression|env_failure|unknown>
```

For a bugfix the failing test is written and **shown failing** before the fix —
that one test, not the suite. `new_regression` sends you back to
IMPLEMENTATION; fix, then run the verification command again.
`existing_failure` is recorded and reported, not fixed inside this task. Never
let a test be edited to make it pass.

### ADVERSARIAL REVIEW (T2 and above)

One `ai-reviewer` on the diff — a fresh context that did not write the code —
with the model from `pipeline_profiles.<profile>.review_model[<tier>]`: `sonnet`
at T2 in solo, `opus` above. Save findings to
`.ai/reports/<task-id>/review-report.md`.

Before you delegate, probe the change yourself for a minute: the handful of
inputs its own threat model makes interesting, run through the real code in the
scratchpad, outcomes noted in `.ai/reports/<task-id>/review-ledger.md`. The
reviewer starts where you stopped. A re-review after a remediation is scoped —
do the named findings close, and what did the remediation introduce — never a
second full pass. One reviewer per pass; fan out narrow reviewers only at T4/T5
when the change is wide. Full rules: `.ai/policies/review-economy.md`.

```bash
$STATE set review_status <passed|blockers_open>
```

A BLOCKER or HIGH goes back to IMPLEMENTATION, or to PLAN when the cause is the
plan. Findings that are real but out of scope go to `.ai/project/known-risks.md`.
When a finding is a mistake this repository has seen before, add one line to the
project `CLAUDE.md` in this task: the second occurrence is when a correction
belongs there.

### SECURITY REVIEW (T4, T5, and anything touching auth or personal data)

`ai-security`. Save to `.ai/reports/<task-id>/security-report.md`.

```bash
$STATE set security_status <passed|failed|not_applicable>
```

When it is not applicable, say why in the note. Silence is not a verdict.

### RELEASE REPORT

**solo, T0–T3:** write the short form yourself: what changed, what was
deliberately preserved, the verification command and its result, the review
verdict, the rollback (usually one `git revert`), open risks. It becomes the
commit message body. At T0/T1 it exists only there and in the final message;
at T2/T3 append it to `task.md`. **T4, T5, and `team` from T2 up:**
`ai-release` fills the full template into
`.ai/reports/<task-id>/release-report.md`.

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

- Inline does not mean verbose: a stage you do yourself is a few lines, and
  below T2 not even a file — the state archive is the record.
- One tool call where one will do: `triage` instead of four `stage` calls, one
  `task.md` instead of four report files, one verification run instead of one
  per step.
- Never read logs, test output or large files into this session; `tail`, then
  `log-reader`.
- Keep the agents' structured outputs as files under `.ai/reports/<task-id>/`
  and refer to them by path; do not carry their full text through the
  conversation.
- Do not rediscover what `.ai/project/` already records. If it is wrong, fix that
  file as part of the task.
- Between stages, your own context should hold: the goal, the tier, the current
  step and the last verdict. Everything else lives on disk.

## Rules

- No required stage is skipped. `stages_required` per tier says which exist —
  T0 and T1 have no plan stage at all — and the profile decides who does each.
  Cheap tasks get cheap stages, not skipped ones.
- The tier decides the gates. Your sense of how risky it feels does not.
- The scope guard is not an obstacle to route around; it is the plan being
  enforced.
- Problems found outside the task get written down, not fixed.
- The pipeline ends at human approval. Always.
