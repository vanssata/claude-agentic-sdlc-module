# Release policy

## The gate

```
implementation
  → lint
  → static analysis
  → unit tests
  → integration tests
  → regression tests
  → security checks
  → adversarial review
  → staging
  → smoke tests
  → HUMAN APPROVAL
  → production
```

Everything up to and including the release report is the agent's work. Everything
after human approval is a person's. **No agent deploys to production**, and no
agent merges the pull request that leads there.

## The release report

Assembled by the session at `/rr-ship` from the task's own artifacts under
`.ai/reports/<task-id>/`, using the template in `.ai/templates/release-report.md`.
It exists so that the human approving the change can see, in one page, what
changed, what deliberately did not, what was tested, what was reviewed, what
could go wrong, and how to undo it.

A report that says "no known risks" for a guarded or full change is a report that was not
written carefully.

## What blocks a release

- an open BLOCKER or HIGH finding from `ai-reviewer`, including its
  `focus: security` pass;
- a new regression in the last `state.py verify` run;
- a destructive database operation without its own named approval;
- a guarded or full change with no rollback section;
- an unanswered blocking question in the plan.

## Project specifics

<!-- How this project actually deploys: the pipeline, the environments, who
     triggers a release, where the smoke tests live, how a rollback is performed
     and whether it has ever been rehearsed. -->
