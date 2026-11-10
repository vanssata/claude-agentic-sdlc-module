# Workflow: bugfix

Something behaves wrongly. The goal is the smallest change that fixes it without
changing anything else.

| Stage | Who | Notes |
|---|---|---|
| DISCOVERY | `ai-discovery` | reproduce first: find the exact path that produces the symptom |
| CONTEXT | `ai-context` | include the *correct* behaviour and where it is defined |
| IMPACT ANALYSIS | `ai-discovery` | who else depends on the current, wrong behaviour |
| RISK CLASSIFICATION | `ai-risk` | a bug in a payment path is still T4 |
| PLAN | `ai-planner` | failing test first, then the fix |
| IMPLEMENTATION | the session | the failing test is its own step |
| TEST | `ai-tester` | the new test fails before the fix and passes after |
| ADVERSARIAL REVIEW | `ai-reviewer` | T2 and above |
| SECURITY REVIEW | `ai-security` | if the bug was a security bug, always |
| RELEASE REPORT | `ai-release` | |
| HUMAN APPROVAL | the human | |

## Specific to this workflow

- **Write the failing test first.** A bugfix without a test that failed before it
  is a bugfix nobody can prove.
- Find out *why* the bug exists before fixing it. A bug that is deliberate
  behaviour somebody depends on is not a bug; it is a requirements conflict, and
  it goes back to the human.
- Resist the urge to fix the surrounding code. Note it, fix the bug.
- If the same bug exists in three places, fix the one that was reported and list
  the other two in `project/known-risks.md`.
