---
name: sdlc-spec
description: SDLC stage 2 — read an intent file and produce docs/sdlc/specs/<slug>.md, a requirements and design spec that applies the project's CLAUDE.md conventions and available skills as organisational policy, and ends with explicitly flagged concerns (especially contradicting policies). Use after /sdlc-intent, "write the spec", "design this from the intent".
argument-hint: <path to docs/sdlc/intent/<slug>.md>
---

# /sdlc-spec $ARGUMENTS

Input: an intent file (default: the most recent `docs/sdlc/intent/*.md` if no argument).
Output: `docs/sdlc/specs/<slug>.md` with the same slug.

## The task, verbatim

> Read the attached intent.md and produce a requirements and design spec. Apply the organizational
> skills and conventions that apply to this project. Describe clearly any areas of concern,
> especially where you cannot satisfy contradicting policies.

## Organisational skills = what this project already says

Before designing, collect the policies the spec must conform to, in this order:

1. the repo-root instruction file — `CLAUDE.md` and/or `AGENTS.md`, whichever exist — and the
   global one of the runtime you are in (`~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md`), bounded reads.
   When a repo carries both, they describe the same project: read both and note any disagreement
   as a flagged concern;
2. `.claude/skills/*/SKILL.md` and `.claude/agents/*.md`, `.codex/skills/*/SKILL.md` and
   `.codex/agents/*.toml` in the repo — read only the frontmatter
   `description:` lines (`grep -n '^description:'`) and open a skill only if it applies;
3. `docs/sdlc/adr/*.md` — accepted decisions are binding, note their numbers;
4. plugin skills whose description matches the stack (e.g. Sylius/Symfony UX skills).

List them in **Policy conformance** with one line each on how the design honours them. When two
policies contradict each other or the intent, do **not** pick silently — put it in **Flagged concerns**.

## Steps

1. **Prerequisites** — the intent file exists and `docs/sdlc/specs/TEMPLATE.md` exists
   (else `/project-init`). Read the intent fully; it is small by design. Carry its open questions.
2. **Collect policies** as above.
3. **Design** — delegate to the `architect` subagent (it runs at the STRONG tier — Opus under
   Claude Code, Sol under Codex; escalate to the EXPERT agent only when an EXPERT trigger in the
   routing rules fires, e.g. an irreversible data-model or API
   decision). Give it: the intent text, the policy list, and the request to
   return Requirements (numbered, testable), Design (components, data flow, ≥2 alternatives
   rejected), Interfaces (exact shapes), Risks. Do not let it write code.
4. **Write** — copy `docs/sdlc/specs/TEMPLATE.md` to `docs/sdlc/specs/<slug>.md`, replace
   `{{TITLE}}`/`{{SLUG}}`, fill every section from the architect output plus your policy pass.
   Every requirement references the intent outcome it satisfies.
5. **Flagged concerns** — mandatory and last. Include: policy-vs-policy contradictions,
   policy-vs-intent contradictions, requirements you cannot satisfy, assumptions the intent left
   open, security/data-protection questions. Write `none` only if the list is genuinely empty and
   say why you believe that.
6. **Confirm** — show the concerns section first, then the rest; take one round of corrections.
7. **Hand-off** — suggested commit `git add docs/sdlc/specs/<slug>.md && git commit -m "spec: <title>"`
   and next step `/sdlc-plan docs/sdlc/specs/<slug>.md`.
