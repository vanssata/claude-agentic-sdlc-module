---
name: ai-task
description: Run one task through the agentic pipeline with the gates its risk tier requires. In the default solo profile T0–T2 run in direct mode (name the files, edit, one verification run at the end, failures fixed as one batch, one sonnet review at T2) and T3–T5 run the full SDLC pipeline — discovery, context, impact, risk tier, plan, plan review, implementation, test, adversarial review, security review, release report, human approval. Resumes an interrupted task from .ai/state/current.json. Use for any change in a repository that has .ai/.
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
the stages that go to a subagent. `solo`, the default, has two modes:

- **direct** (T0–T2): no ceremony. You name the files, edit, run each step's
  own scoped tests, then the verification command once at the end and the e2e
  suite once after it, and fix every failure as one batch.
  The only subagents are cheap readers (`Explore`, `log-reader`) and, at T2,
  one `ai-reviewer` on `sonnet`. Nothing runs on `opus` below T3.
- **sdlc** (T3–T5): the full pipeline below, recorded stage by stage, with the
  delegations the profile lists.

Decide the tier **first**, from the trigger table, before anything else; when
two tiers are arguable take the higher. Until it is known, act as for T2.

## 1a. Direct mode — T0, T1, T2

Skip `$STATE init` above for T0–T2; direct mode has its own single call.

1. **Tier and files.** Take the entry points from the request; confirm them with
   `grep -n`. Say the tier, the trigger and the files you will touch, in one to
   five lines. At T2 that is the plan. Use `Explore` (haiku) when a file is not
   found in a few `grep` calls, never a six-agent fan-out — and when a file is
   too large to open, that reader brings back the excerpt, not the file.
   If this task needs a tool or MCP server the project does not enable by
   default, say so here in one line and turn it off when the task ends:

   ```
   tools_for_this_task: <server-or-tool> — <why> — <when it goes off again>
   ```

   Most tasks need none. See `.ai/policies/tooling.md`.
2. **Record — T2 only.** One call arms the scope guard and writes the audit
   trail; T0 and T1 keep no state file at all, the commit is the record:

   ```bash
   $STATE quick --goal "<one sentence>" --workflow <workflow> --tier T2 --files "<a>,<b>" --note "<trigger>"
   ```

3. **Implement**, yourself, in this session. `ai-implementer` (sonnet, low) only
   for a mechanical pattern-copy the human asks for. When you finish a piece of
   work, run **only its own tests** — `step_test_command` from
   `.ai/policies/testing.md` scoped to the files you just touched — and fix
   those failures there. Never the full suite mid-edit, never e2e. A bugfix
   shows its failing test first, that one test.
4. **Verify once, to the end.** Run the verification command from
   `.ai/policies/testing.md` with no fail-fast flag, through `tail -40`, or
   through `log-reader` when the output is long. T0 runs nothing. Collect
   **every** failure, classify each (new regression, existing, environment),
   then fix all new regressions in **one** remediation step and run once more:

   ```bash
   $STATE step-done 1 && $STATE remediate --files "<failing tests>" --note "<n> regressions"   # T2
   ```

   At T0/T1 there is no state: just fix the batch and re-run. Two rounds at
   most; a third means the human decides. One failure never restarts the task.

   Then, **once**, after the fast suite is green: `e2e_command`. T0 and T1 skip
   it. At T2 run it when the change can reach a flow the e2e suite covers; when
   it cannot, say so in one line instead. It never runs inside step 3.

   ```bash
   $STATE set e2e_status <passing|failing|not_applicable>   # T2
   ```
5. **Review — T2 only.** After the tests pass, one `ai-reviewer` with
   `model: sonnet` over `git diff`, no ledger and no probe. Fix BLOCKER and
   HIGH findings as one batch (`$STATE remediate`), re-run the verification
   command, and ask for one scoped re-review only when a BLOCKER was fixed.
6. **Close.** Print what changed, the verification command and its result, the
   review verdict and the rollback (`git revert`), as the commit message body.
   Then stop for the human. At T2: `$STATE close`.

That is the whole path. The sections below are for T3 and above, and for the
`team` profile.

## 1. Walk the pipeline

Record every stage transition, so the state file is a true audit trail:

```bash
$STATE stage <stage> --note "<what happened>"
```

### TRIAGE — discovery, context, impact and risk

**solo, T0–T2:** direct mode, section 1a. If a task that started as T2 turns
out to be T3+, say so, `$STATE close` the quick record and start it here.

**`team` below T3:** record the four stages in one call and go on to PLAN:

```bash
$STATE triage T<n> --note "<the trigger>" --context "<entry points, callers, what must stay unaffected — a few lines>"
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

If the task needs a tool or MCP server beyond what the project enables by
default, record it now, once, as `tools_for_this_task: <server-or-tool> — <why>
— <when it goes off again>` in the task record, and disable it again when the
task closes (`.ai/policies/tooling.md`). Agents keep the tool list their
definition gives them; an agent short of a tool answers `SCOPE_CHANGE_REQUIRED`.

Now state which later stages the tier makes mandatory and which of them this
profile delegates. Everything after this point follows that answer, not your
impression of how big the task feels.

### PLAN — only when the tier needs one

**T0–T2 in solo:** handled in direct mode (1a). **`team` below T3:** a short
numbered list of steps, each with its files, registered with:

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

For each step in order:

```bash
$STATE step <step_id>          # arms the scope guard for this step
```

Implement it **yourself**, in this session. Use `ai-implementer` only for
mechanical pattern-copying work, or when the human asks.

If an edit is refused with `SCOPE_CHANGE_REQUIRED`: stop, do not work around it.
Say which file is needed and why, return to PLAN for that one step, amend it,
re-register the plan, and continue. One step's scope is amended — not the task
replanned.

Close the step with **its own tests only** — the ones the plan named for it,
through `step_test_command` scoped to that step's files (`$STATE step` prints
them). Not the full suite, not e2e: those belong to the end of the task. The
scoped run still goes to the end, and its failures are fixed inside the step —
no `remediate` step for them. If the plan named no test for the step, nothing
runs.

```bash
$STATE step-done <step_id>
```

### TEST — the step's tests inside the step, the suite once, e2e once

After the **last** step, not after each one. Run the verification command from
the **Verification** section of `.ai/policies/testing.md`; if that section is
empty, take it from the project `CLAUDE.md` or the CI config and write it into
`testing.md` as part of this task, so the next task has it. Run it **to the
end** — no fail-fast flag, no stopping at the first red test. Pipe the output
through `tail -40`; when more than that matters, hand the full output to
`log-reader` (haiku) and take back the list of failures; use `ai-tester`
(haiku) in the `team` profile or when the test setup is unfamiliar.

Only the step's own scoped tests run during a step — never the full suite and
never e2e. For a bugfix the failing test is written and **shown failing**
before the fix — that one test, not the suite.

```bash
$STATE set test_status <passing|existing_failure|new_regression|env_failure|unknown>
```

**Fix as one batch.** Classify every failure first. Then open **one**
remediation step whose scope is every finished step plus the failing tests,
fix all the new regressions in it, and run the verification command once more:

```bash
$STATE remediate --files "<failing test files>" --note "<n> regressions: <one line each>"
… fix them all …
$STATE step-done R1
```

A remediation never re-triages or re-plans: the tier, the plan and the finished
steps stand. Two rounds at most; a third round means the human decides.
`existing_failure` is recorded and reported, not fixed inside this task. Never
let a test be edited to make it pass.

**E2E — once, at the end of the task.** After the fast suite is green and
before the adversarial review, run `e2e_command` from `testing.md`, once, to
the end, output through `tail -40` or `log-reader`. It never runs inside a step
and never twice. Skip it when the change cannot reach a flow it covers and say
which, in one line; at T4/T5 it is not skipped, and its result goes into the
release report. Its failures are classified and fixed as one batch, like the
suite's.

```bash
$STATE set e2e_status <passing|failing|not_applicable>
```

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

Every BLOCKER and HIGH is fixed together, in one `$STATE remediate` step, then
the verification command runs once and one scoped re-review closes the named
findings — never one finding, one fix, one re-review at a time. A finding whose
cause is the plan goes back to PLAN for that step only. Findings that are real but out of scope go to `.ai/project/known-risks.md`.
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

**solo, T3:** write the short form yourself: what changed, what was
deliberately preserved, the verification command and its result, the review
verdict, the rollback (usually one `git revert`), open risks. It becomes the
commit message body and is appended to `task.md`. (T0–T2 wrote it in direct
mode, step 6.) **T4, T5, and `team` from T2 up:**
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
- One tool call where one will do: `quick` below T3, `triage` instead of four
  `stage` calls, one `task.md` instead of four report files, one verification
  run and one e2e run instead of one per step, one `remediate` step instead of
  one per failure.
- Never read logs, test output or large files into this session. `grep -n`
  first and read the ranges that matched; past that, `tail`, then a FAST reader
  on the cheapest model — `log-reader` for output, `Explore` for code — which
  returns the excerpt with `file:line`, never the file.
- Tools and MCP servers are context too. Anything the task does not name stays
  off, and deferred tools are loaded in one batched call, not one per tool.
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
  Cheap tasks get cheap stages, not skipped ones: in direct mode they are a
  line each, not a file each.
- Failures are fixed in batches. One red test or one review finding never
  restarts the task, re-runs the suite on its own, or re-opens the plan. A
  step's own scoped tests are the exception: they are fixed in that step.
- A step runs its own tests, and only those. The full suite runs once after the
  last step; the e2e suite runs once after that. Never per step.
- Nothing below T3 runs on `opus`. Readers and runners are `haiku`; the T2
  review is `sonnet`; STRONG is paid for from T3. Large files are read by the
  cheapest model, and only the relevant part comes back.
- Tools and MCP servers are off unless the task named them, and go off again
  when it closes.
- The tier decides the gates. Your sense of how risky it feels does not.
- The scope guard is not an obstacle to route around; it is the plan being
  enforced.
- Problems found outside the task get written down, not fixed.
- The pipeline ends at human approval. Always.
