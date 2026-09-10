# Workflows

`/ai-task` classifies the request into one of five shapes and follows
`.ai/workflows/<shape>.md`. The shape does not change which stages exist — it
changes what each stage pays attention to.

## feature

New behaviour someone asked for. The default.

The thing that goes wrong: a feature quietly changes an existing behaviour. So
the plan states what must stay the same, not only what changes, and the review
looks for drift rather than only for bugs.

## bugfix

Something behaves wrongly; fix it with the smallest possible change.

**Write the failing test first.** A bugfix without a test that failed before it is
a bugfix nobody can prove. Then find out *why* the bug exists — a "bug" that turns
out to be deliberate behaviour someone depends on is a requirements conflict, and
it goes back to the human rather than being fixed.

Resist fixing the surrounding code. If the same bug exists in three places, fix
the reported one and list the other two in `.ai/project/known-risks.md`.

## refactoring

Changing shape without changing behaviour. The most dangerous workflow in a
legacy codebase, because success is invisible.

The order is not negotiable:

```
characterization test → refactor → verify identical behaviour → (a different task) feature change
```

A test that has to be modified during a refactoring means behaviour changed —
stop and say so. Renaming something that appears in a string (a service id, a
queue name, a route name, a column) is not a rename, it is a migration. Plan
review is required whatever the tier, because "this is cleaner" is not a
justification for risk.

## hotfix

Production is broken now. Stages get shorter; none disappears.

Urgency lowers the *depth* of a stage, never its existence, and the risk tier is a
property of the code being touched, not of how loudly someone is asking. The
hotfix is the smallest change that stops the bleeding; the real fix, the cleanup
and the missing test become follow-up tasks, **written down before the hotfix is
approved** so they do not evaporate when the incident closes.

Never disable a test or a check to get a hotfix out. If CI is the obstacle, a
human decides that explicitly.

## investigation

A question, not a change. The deliverable is an answer with evidence.

There is no implementation stage. Nothing is edited — not a comment, not a
formatting fix. Every claim is labelled and cited: KNOWN FACT with `file:line`,
INFERENCE with what it rests on, UNKNOWN with what would settle it.

If the investigation concludes something should change, that is a **new task**
with its own plan and approval.

## Choosing

`/ai-task` says which workflow it picked and why. Correct it if it picked wrong —
the difference between "bugfix" and "refactoring" in particular changes whether
characterization tests are mandatory.

## Where the SDLC skills fit

`/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan` is a documentation chain, not a
sixth workflow. Use it when the work needs a written problem statement and an
agreed design before anyone touches code — a new subsystem, a change several
people must agree on, anything a reviewer will ask "why" about in six months.

It produces `docs/sdlc/plans/<slug>.md`. Hand that to `/ai-task`, which then runs
the same pipeline as any other task, with the tier's gates. The intent and the
spec become the context the discovery stage would otherwise have to reconstruct.

For an ordinary change, skip it. `/ai-task` writes its own plan.
