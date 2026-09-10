# AI-native SDLC adoption plan

- Repository:
- Assessed on:
- Assessed by: Claude Code, `/ai-audit`
- Context supplied by:

## Inventory

<!-- What exists today. One row per item: exists / partial / missing, and one
     line on its quality. Cite the path. Mark anything you could not check as
     unverified, with what would settle it. -->

| Item | State | Note |
|---|---|---|
| `CLAUDE.md` (root) | | |
| nested `CLAUDE.md` files | | |
| `.claude/settings.json` | | |
| `.claude/settings.local.json` | | |
| `.claude/hooks/` | | |
| `.claude/skills/` | | |
| `.claude/agents/` | | |
| `.claude/commands/` | | |
| CI workflows | | |
| branch protection | | |
| test entry point | | |
| build entry point | | |
| lint / static analysis entry point | | |
| `REVIEW.md` | | |
| intent / spec / plan folders | | |
| ADRs | | |
| `.ai/` infrastructure | | |

## Gap scores

<!-- 0 absent · 1 ad hoc · 2 in place but not enforced · 3 enforced and measured.
     Every score cites the file that justifies it, or says unverified. -->

| # | Play | Score | Evidence |
|---|---|---|---|
| 1 | Capture as intent.md | | |
| 2 | Requirements and design | | |
| 3 | Plan mode default, plan.md committed | | |
| 4 | CLAUDE.md | | |
| 5 | Skills as institutional knowledge | | |
| 6 | Parallel sessions and subagents | | |
| 7 | Feedback loop | | |
| 8 | Continuous evals in CI | | |
| 9 | AI in the PR review loop | | |
| 10 | Hooks as approval gates | | |
| 11 | CI/CD integration | | |
| 12 | Closing the loop | | |

## Phase 1 (weeks 1–2)

<!-- Per item: the play it advances and the target score · exact files to create
     or change, with a sketch of their content · owner role · prerequisites ·
     governance (what is enforced, where the evidence is logged, who approves) ·
     one leading and one lagging metric with the data source. -->

## Phase 2 (weeks 3–4)

## Phase 3 (weeks 5–6)

## Guardrail fixes

<!-- Anything in the current AI configuration that is unsafe or has drifted, with
     the minimal fix for each: over-broad permissions, hooks that can be bypassed
     locally, secrets reachable by the agent, test files editable during a fix
     task, a CLAUDE.md that is stale, contradictory or longer than a page. -->

| Issue | Why it matters | Minimal fix | Owner |
|---|---|---|---|

## Open questions for the team

<!-- What the repository cannot answer: ownership, regulatory constraints,
     release authority, who approves what. One line each, with who can settle it. -->
