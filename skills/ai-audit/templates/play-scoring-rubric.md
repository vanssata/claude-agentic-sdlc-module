# The twelve plays, and how to score them

Score each play 0–3. Cite the file and line that justifies the score. When you
cannot verify something from the repository, write **unverified** and say what
would settle it — never guess a score.

| Score | Meaning |
|---|---|
| **0** | absent |
| **1** | ad hoc — happens when someone remembers |
| **2** | in place but not enforced — documented or configured, nothing stops you skipping it |
| **3** | enforced and measured — a hook, a CI gate or branch protection makes it happen, and there is evidence it does |

## 1. Capture as intent.md

Work starts from a written statement of the problem and the desired outcome,
committed to the repository, before any design or code.

Look for: `docs/sdlc/intent/`, `intent/`, an issue template that captures
problem/outcome, a `/sdlc-intent`-style skill.

## 2. Requirements and design (spec.md, policies as skills)

The intent becomes a spec with numbered, testable requirements and a design;
organisational policies are expressed as skills the agent loads, not as prose
nobody reads.

Look for: `docs/sdlc/specs/`, ADRs, `.claude/skills/` encoding conventions,
`.ai/policies/`.

## 3. Plan mode as default, plan.md committed

Non-trivial work is planned before it is written, and the plan is committed so a
reviewer can see what was intended, not only what happened.

Look for: committed plans, `.claude/plans/`, a documented convention that plan
mode is the default.

## 4. CLAUDE.md

One page, current, specific to this repository: commands, conventions,
architecture, the mistakes that keep recurring. Not a tutorial, not a duplicate
of the README.

Look for: root `CLAUDE.md`, nested ones, length, staleness, contradictions with
the code.

## 5. Skills as institutional knowledge

The things a new engineer would need to be told are written as skills the agent
loads automatically, rather than repeated in every prompt.

Look for: `.claude/skills/`, plugin skills, whether they are used or vestigial.

## 6. Parallel sessions and subagents

Read-heavy work is delegated to cheap agents; the expensive session does design
and synthesis. Agent definitions declare their model and effort.

Look for: `.claude/agents/`, `~/.claude/agents/`, `model:` and `effort:` in their
frontmatter, evidence of fan-out in the workflow docs.

## 7. Feedback loop

One command verifies the project. A bug becomes a failing test first.
"Done" means verified, not "the model said so".

Look for: a single `make test` / `composer qa` / `npm run verify` entry point,
whether it runs lint, static analysis and tests together, and whether the
convention of a failing test first is written anywhere.

## 8. Continuous evals in CI

Changes to `CLAUDE.md`, `.claude/` or `.ai/` are themselves tested: a CI job
checks that the agent configuration still produces the intended behaviour.

Look for: a workflow triggered on those paths, eval fixtures, `claude -p` in CI.

## 9. AI in the PR review loop

An automated review runs on every pull request with a defined set of passes and
severities, and its output is visible to the reviewer.

Look for: a review workflow, `REVIEW.md`, severity conventions, whether findings
are posted to the PR or discarded.

## 10. Hooks as approval gates

The rules that matter are enforced by hooks, not by asking politely. Distinguish
build-time guardrails (formatting, linting) from approval gates (what an agent
may not do at all).

Look for: `.claude/settings.json` hooks, `~/.claude/hooks/`, whether a hook can be
disabled by editing a file the agent can write, managed settings.

## 11. CI/CD integration

The agent participates in the pipeline in a sandboxed way, and the rollback path
has been rehearsed rather than described.

Look for: `claude -p` steps in CI, what credentials they get, deployment
mechanism, an actual rollback procedure and evidence it was tested.

## 12. Closing the loop

Production signals come back into the intent: incidents are detected
deterministically, classified into tiers, and written back into the requirements
that produced them.

Look for: alerting configuration, a `bands.yaml`-style tier definition, evidence
that an incident ever updated an intent or a spec.
