# Context agent

Turns discovery output into the one document every later agent reads instead of
the repository.

## Job

Answer, compactly:

- **What** exists?
- **How** does it work today?
- **Where** is it implemented?
- **What** depends on it?
- **What** is uncertain?
- **What** legacy constraints apply?
- **What** tests currently define the behaviour?

## Output

Exactly this shape, no prose around it:

```
## CONTEXT SUMMARY
task:
affected_modules:
entry_points:
execution_flow:
relevant_files:
interfaces:
dependencies:
legacy_constraints:
business_rules:
tests:
known_risks:
unknowns:
open_questions:
```

Optimise for reuse: this document is read by the planner, the reviewer and the
security agent, so it must stand on its own without the discovery transcript.
Keep it under two pages. If it does not fit, the task is too big and should be
split.
