---
name: sdlc-intent
description: SDLC stage 1 — turn a rough idea into docs/sdlc/intent/<slug>.md (problem, outcome, affected users & systems, constraints, open questions) through a short one-question-at-a-time brainstorm. Use when starting a feature, "write an intent", "let's define what we want", before any spec or code.
argument-hint: <topic or one-line idea>
---

# /sdlc-intent $ARGUMENTS

Produce `docs/sdlc/intent/<slug>.md`. This stage answers **what** and **why** only; anything about
**how** goes to `/sdlc-spec`.

## Steps

1. **Prerequisites** — if `docs/sdlc/intent/TEMPLATE.md` is missing, run `/project-init` first.
   Derive `<slug>` from the topic (kebab-case, ≤ 5 words). If `docs/sdlc/intent/<slug>.md` already
   exists, offer to refine it instead of starting over.

2. **Brainstorm** — if the `superpowers:brainstorming` skill is available, invoke it with the topic;
   it already asks one question at a time and explores alternatives. Otherwise do the same yourself:
   - ask exactly one question per turn, prefer multiple-choice;
   - cover, in order: the problem and its evidence → the observable outcome → who/what is affected →
     constraints and non-goals → what is still unknown;
   - stop as soon as each template section can be filled with something concrete; five to eight
     questions is typical.
   Look at the repo (bounded reads, `grep -n`) before asking things the code already answers.

3. **Write** — copy `docs/sdlc/intent/TEMPLATE.md` to `docs/sdlc/intent/<slug>.md`, replace
   `{{TITLE}}`, fill every section. Keep outcomes testable ("a user can …", "p95 < …"), keep
   design out. Open questions that block the spec are marked **(blocking)**.

4. **Confirm** — show the file, ask for corrections in one round, apply them.

5. **Hand-off** — end with:
   - suggested commit: `git add docs/sdlc/intent/<slug>.md && git commit -m "intent: <title>"`;
   - next step: `/sdlc-spec docs/sdlc/intent/<slug>.md`.
