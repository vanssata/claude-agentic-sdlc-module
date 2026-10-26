---
name: rr-spec
description: Turn a rough idea into one file, docs/sdlc/specs/<slug>.md — an `## Intent` section (problem, outcome, affected users and systems, constraints, decisions taken) from a short one-question-at-a-time brainstorm recorded through state.py, then requirements and design from the architect agent on the STRONG tier, checked against the project's constitution, instruction files, skills and ADRs, ending with explicitly flagged concerns (especially contradicting policies). Accepts an existing docs/sdlc/intent/<slug>.md instead of the brainstorm. Use when starting a feature, "write the spec", "let's define what we want", "design this", before any plan or code.
argument-hint: <topic or one-line idea> | <path to docs/sdlc/intent/<slug>.md>
---

# /rr-spec $ARGUMENTS

Output: `docs/sdlc/specs/<slug>.md`, one file that says **what** and **why**
(`## Intent`) and then **how** (requirements, design, interfaces, concerns).
Nothing here edits code. Resolve the install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-spec" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

## 1. Prerequisites

`docs/sdlc/specs/TEMPLATE.md` exists, else run `/rr-setup` first. Derive
`<slug>` from the topic (kebab-case, at most five words). If
`docs/sdlc/specs/<slug>.md` exists, offer to refine it instead of starting over.
When `$ARGUMENTS` is a path to an intent file, read it fully — it is small by
design — and skip to step 3 with it as the intent.

## 2. Brainstorm, on the record

Every question to the human goes through `state.py`, so the brainstorm survives
a compaction, a `/clear` and a change of runtime. Topic questions live in
`docs/sdlc/intent/<slug>.questions.md` — with or without `.ai/` — and block
nothing:

```bash
$STATE ask --topic <slug> "<one line>" --option "A: <text>" --option "B: <text>" --recommend A
$STATE answer --topic <slug> Q1=B              # or --prose "1B", or Q1=X:"free text"
```

If `superpowers:brainstorming` is available, let it drive the conversation; the
questions and answers still go through `ask` and `answer`. Otherwise:

- one question per turn, multiple choice where possible (two to six options,
  A first; never write "(recommended)" into an option — that is `--recommend`);
- in order: the problem and its evidence → the observable outcome → who and what
  is affected → constraints and non-goals → what is still unknown;
- look at the code (`grep -n`, bounded reads) before asking what it answers;
- stop when each part of the intent can be filled with something concrete —
  five to eight questions is typical.

Never hand-edit the questions file; a human may fill an `[Answer]:` line
themselves, and the file is the record.

## 3. Policies the spec must honour

1. `docs/sdlc/constitution.md`, this project's principles `C1`…`C<n>`: cite the
   ones a decision rests on. If it is absent, say so in one line and go on.
2. The repo-root instruction files (`CLAUDE.md`, `AGENTS.md` — when both exist,
   note any disagreement as a concern) and the global one of this runtime.
3. Project skills and agents: only their `description:` lines
   (`grep -n '^description:'`), opening one only when it applies.
4. `docs/sdlc/adr/*.md`: accepted decisions are binding; note their numbers.
5. Plugin skills whose description matches the stack.

## 4. Design

Delegate to `architect` on the STRONG tier
(`model: $($STATE profile --tier STRONG)` under Claude Code; under Codex the
agent file's model is the tier). Give it the intent, the policy list, and ask for
Requirements (numbered, testable, each naming the outcome it satisfies), Design
(components, data flow, at least two alternatives rejected), Interfaces (exact
shapes) and Risks. It writes no code. Only an EXPERT trigger from
`<home>/claude-agentic/routing.md` — an irreversible data-model or API
decision — moves this to the top tier.

## 5. Write

Copy `docs/sdlc/specs/TEMPLATE.md` to `docs/sdlc/specs/<slug>.md`, replace
`{{TITLE}}` and `{{SLUG}}`. Replace the template's `Intent:` line with:

```markdown
## Intent

Problem · Outcome (testable: "a user can …", "p95 < …") · Affected users and
systems · Constraints and non-goals · Open questions ((blocking) where they block
the plan)

### Decisions taken
```

— or, when an intent file was given, keep the line pointing at it. Fill
`### Decisions taken` from `docs/sdlc/intent/<slug>.questions.md`: each answered
question with the option chosen, in the order asked. It stops the plan from
reopening a settled question. Then fill every template section from the
architect's output and your policy pass, listing each policy in **Policy
conformance** with one line on how the design honours it.

**Flagged concerns** is mandatory and last: policy against policy, policy
against intent, requirements that cannot be met, assumptions the intent left
open, security and data-protection questions. Write `none` only when the list is
genuinely empty, and say why. Contradictions are never resolved silently.

## 6. Confirm and hand off

Show **Flagged concerns** first, then the rest; take one round of corrections.
Suggest `git add docs/sdlc/specs/<slug>.md docs/sdlc/intent/<slug>.questions.md`
and a commit `spec: <title>` — the questions file is the evidence behind the
decisions. Next: `/rr-plan docs/sdlc/specs/<slug>.md`.
