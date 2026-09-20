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

2. **Brainstorm, on the record.** Every question you put to the human goes through `state.py`, so
   the brainstorm survives a compaction, a `/clear` and a change of runtime — and so the intent's
   decisions can be rendered rather than remembered. Resolve the install root as `/ai-task` does,
   then:

   ```bash
   STATE="python3 $AI_HOME/skills/ai-task/state.py"
   $STATE ask --topic <slug> "<one line>" --option "A: <text>" --option "B: <text>" --recommend A
   $STATE answer --topic <slug> Q1=B                  # or --prose "1B", or Q1:"free text"
   $STATE questions --topic <slug> --pending --format prose
   ```

   Topic questions live in `docs/sdlc/intent/<slug>.questions.md` — **always, with or without a
   `.ai/` directory**, so this stage works in a repository that has never run `/ai-init`. They
   block no command and emit no journal event: this is a conversation, not a gate.

   If the `superpowers:brainstorming` skill is available, invoke it with the topic to drive the
   conversation; the questions and answers still go through `ask` / `answer`. Otherwise do the same
   yourself:
   - ask exactly one question per turn, prefer multiple-choice (two to six options, A first);
   - cover, in order: the problem and its evidence → the observable outcome → who/what is affected →
     constraints and non-goals → what is still unknown;
   - stop as soon as each template section can be filled with something concrete; five to eight
     questions is typical.
   Look at the repo (bounded reads, `grep -n`) before asking things the code already answers.
   Never hand-edit the questions file — `state.py` writes it. A human may fill in an `[Answer]:`
   line themselves, and `$STATE questions --topic <slug> --sync` picks that up.

3. **Write** — copy `docs/sdlc/intent/TEMPLATE.md` to `docs/sdlc/intent/<slug>.md`, replace
   `{{TITLE}}`, fill every section. Keep outcomes testable ("a user can …", "p95 < …"), keep
   design out. Open questions that block the spec are marked **(blocking)**.

   Fill `## Decisions taken` from the brainstorm rather than retyping it:

   ```bash
   $STATE questions --topic <slug> --format md
   ```

   That is the answered questions with their chosen options, in the order they were asked. Paste it
   under the heading. It is what stops the spec stage from reopening a question that was already
   settled, and what tells a reader six months later *why* the intent says what it says.

4. **Confirm** — show the file, ask for corrections in one round, apply them.

5. **Hand-off** — end with:
   - suggested commit: `git add docs/sdlc/intent/<slug>.md docs/sdlc/intent/<slug>.questions.md &&
     git commit -m "intent: <title>"` — the questions file is committed with the intent, because it
     is the evidence behind `## Decisions taken`;
   - next step: `/sdlc-spec docs/sdlc/intent/<slug>.md`.
