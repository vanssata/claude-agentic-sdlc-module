# Workflow: investigation

A question, not a change. "Why does this happen?", "where is this handled?",
"can we do X?". The deliverable is an answer with evidence.

| Stage | Who | Notes |
|---|---|---|
| DISCOVERY | `ai-indexer`, then `ai-discovery` in parallel per area | read-only |
| CONTEXT | `ai-context` | the structured summary is often the deliverable itself |
| IMPACT ANALYSIS | `ai-discovery` | only if the question is "what would it take to…" |
| RISK CLASSIFICATION | `ai-risk` | so the answer carries the tier a change would have |
| REPORT | the session | written by the main session, not delegated |

There is no implementation stage. If the investigation concludes that something
should change, that is a **new task** with its own intent, plan and approval.

## Rules

- Nothing is edited. Not a comment, not a formatting fix.
- Every claim in the answer is labelled and cited: KNOWN FACT with `file:line`,
  INFERENCE with what it rests on, UNKNOWN with what would settle it.
- Contradictions between documentation and code are reported as both, not
  resolved by preference.
- Findings worth acting on go into `project/known-risks.md` so the next task can
  see them.
- Say what you could not determine. An investigation that hides its gaps is worse
  than one that admits them.
