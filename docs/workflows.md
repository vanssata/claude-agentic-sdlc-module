# Workflows

Five kinds of change. The kind is named at `state.py start --workflow <kind>`
(`/rr-plan` classifies the request and says which); the **mode** — light,
guarded, full — comes from the weight ([weight.md](weight.md)) and decides how
deep each part goes. Every kind runs the same path: `/rr-plan`, `/rr-build`,
`/rr-review` when the mode or a red fact asks, `/rr-ship`. The kind only adds
what follows. The binding text is `workflows.md` in the shared tree; this page
is the summary.

## feature

New behaviour someone asked for; the default.

- The plan states what stays the same, not only what changes. A feature that
  quietly alters existing behaviour is the most common source of regressions.
- New code paths get their negative cases tested: not authorised, not found,
  invalid input, the external system down.
- A new dependency is a decision with its own line in the plan, and raises the
  novelty axis.

## bugfix

Something behaves wrongly; the goal is the smallest change that fixes it and
nothing else.

- **The failing test comes first, and is shown failing** (C2):
  `state.py verify --scope step --files <the test> --expect fail` before the
  fix. `expected fail: … it bites` is the proof; a test that passes without the
  fix does not bite — rewrite it, not the code.
- Find out *why* the bug exists first. Behaviour somebody depends on is a
  requirements conflict, not a bug: it goes back to the human.
- A bug in a payment, tax or identity path is still full mode.
- The same bug in three places: fix the one reported, record the others with
  `state.py memory risk add`.

## refactoring

The shape of code changes; what it does does not. The most dangerous kind in a
legacy codebase, because success is invisible.

```
characterization test → refactor → identical behaviour verified → (another task) the feature
```

- **Never** combined with a feature change (C3): a plan holding both is two
  tasks.
- Characterization tests are the first step, before anything moves; the same
  tests, unchanged, pass at the end. A test that must change is a sign
  behaviour changed — stop and say so.
- Renaming what appears in a string — a service id, template, queue, route or
  column name — is a migration, not a rename.
- The plan is reviewed before the edit whatever the mode; the review looks for
  behaviour drift. "Cleaner" alone needs a human to confirm it is worth it.

## hotfix

Production is broken now. Each part gets shorter; none disappears.

- The mode is the weight of the code touched, never of the urgency.
- The smallest change that stops the bleeding, with a test that reproduces the
  incident. The real fix, the cleanup and the missing tests become follow-up
  tasks, written down before the hotfix is approved.
- e2e runs only when the incident is in a flow it covers; the rollback line is
  mandatory.
- Record the trigger, the detection and what would have caught it earlier as a
  risk. Never disable a test or a check to ship it; if CI is the obstacle, a
  human decides that, explicitly.

## investigation

A question, not a change — "why does this happen", "where is this handled",
"can we do X". The deliverable is an answer with evidence, written by the
session.

- Nothing is edited, not a comment. An investigation registers no task; one
  that concludes something should change becomes a new task.
- Every claim is labelled and cited: KNOWN FACT with `file:line`, INFERENCE
  with what it rests on, UNKNOWN with what would settle it. Documentation and
  code that disagree are both reported.
- When the question is "what would it take", say the mode the change would
  weigh: `state.py weight --files … --goal …`.
- Findings worth acting on go into the record with `state.py memory risk add`.
  Say what you could not determine.

## Choosing

Named by the request, confirmed by the code. "Add", "support", "allow" is a
feature; "broken", "wrong", "fails" a bugfix; "clean up", "extract", "rename" a
refactoring; "production is down" a hotfix; "why", "where", "could we" an
investigation. A request that mixes two is two tasks, and `/rr-plan` says so
before `start`.

## Where the SDLC skills fit

`/rr-spec` and the programme plan from `/rr-plan` come before a task when the
work needs a written intent and design first: the spec records the brainstorm,
the requirements and the flagged concerns; the plan maps every requirement to
the files that change and the test that proves it; each row then becomes one
task through `/rr-plan` and `/rr-build`, or the whole plan one task through
`/rr-build-all`. The workflow kind is still named per task — a programme plan
usually mixes features with a characterization-first refactoring, and they stay
separate rows.
