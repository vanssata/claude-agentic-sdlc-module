# SDLC artefacts

Work that needs a written intent and design before any code follows
**spec → plan → build**. Each stage has a skill that produces one file here,
and the next stage reads it.

```
 /rr-spec <idea | intent/<slug>.md>  →  docs/sdlc/specs/<slug>.md    (## Intent, requirements, design, Flagged concerns)
        │                               docs/sdlc/intent/<slug>.questions.md  (the brainstorm, recorded by state.py)
 /rr-plan specs/<slug>.md            →  docs/sdlc/plans/<slug>.md    (files that change, order, risks, proof, rollback)
        │
 /rr-build  — one row at a time (each row is one task, weighed and started by /rr-plan)
 /rr-build-all plans/<slug>.md — the whole plan as one task: parallel implementers, one review loop
```

| Folder | Produced by | Contains |
|---|---|---|
| `intent/` | `/rr-spec`'s brainstorm (`state.py ask --topic`) | `<slug>.questions.md`, one question at a time with the answer on record; an `intent/<slug>.md` written by hand is accepted instead of the brainstorm |
| `specs/` | `/rr-spec`, `architect` on STRONG | `## Intent` (problem, outcome, affected users and systems, constraints, decisions taken), requirements, design; ends with **Flagged concerns**, which a human resolves or accepts before planning |
| `plans/` | `/rr-plan` | Files that change / Order of work / Risks / Proof (every requirement to a test or command) / Rollback; each row carries its files and its *Consumes* line |
| `adr/` | you, or `architect` | Architecture Decision Records (MADR style) |
| `constitution.md` | `/rr-setup`, then you | the principles the project does not negotiate, cited as `C<n>` in specs, plans and reviews; at most 15 lines |

Each folder holds a `TEMPLATE.md`; the skills copy it and fill it in. Commit
the artefacts with the code they describe, so the reasoning survives the pull
request. A task's own record — weight, plan, questions, verify runs, review,
verdict — is not here but in `.ai/reports/<task-id>/task.md`, written by
`state.py`.
