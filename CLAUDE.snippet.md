<!-- claude-agentic:start -->
# Model allocation by task and scope (host-wide)

Applies everywhere a model can be chosen: the Agent tool's `model`/`effort`, `.claude/agents/*.md` frontmatter, Workflow `agent()` calls, scheduled jobs. **Facts are collected cheaply; thinking is paid for.** The expensive tier is for design, synthesis, adversarial review and the conclusions a human reads — never for fact collection.

| Tier | Model | Effort | Role |
|---|---|---|---|
| FAST | `haiku` | `low` | verbatim extraction, file and symbol inventories, listings, counting, running a command and reporting its output (`ai-indexer`) |
| BALANCED | `sonnet` | `low`–`medium` | read-only discovery needing judgment, context compression, normal planning, tests, release assembly (`Explore`, `log-reader`, `ai-discovery`, `ai-context`, `ai-tester`, `ai-release`), and mechanical pattern-copying edits |
| STRONG | `opus` | `high` | risk classification at T3+, high-risk planning, adversarial review, security review (`ai-reviewer`, `ai-security`, `ai-planner`/`ai-risk` with a `model: opus` override) |
| EXPERT | omit `model:` — inherits the session ({{SESSION_MODEL}}) | inherit; `{{EXPERT_EFFORT}}` for the hardest verify/judge stages | design and root-cause analysis (`architect`), and `ai-expert` when STRONG has said it cannot settle the question |

- Fan-out width sets the tier: a sweep of five or more parallel agents is never on the session model. A single deep dive may inherit.
- Escalate one task at a time, on a stated trigger — not the whole fleet, and never "just in case". Never retry a failed *thinking* task on a cheaper model; downgrading is for mechanical work.
- Forks (`subagent_type: 'fork'`) always inherit the session model — never pass `model` there.
- Every `.claude/agents/*.md` and every Workflow `agent()` call declares `model:` and `effort:` explicitly. Without them a scout thinks like an architect at the session's cost.
- Readers, scouts and runners never go above `effort: low`. Final synthesis and anything the user reads stays in the main session.

# Model routing ({{PLAN}} plan)

- Session model is {{SESSION_MODEL}}; the harness falls back to {{FALLBACK_MODEL}}. Never pin `model: fable` or `model: opus` for the thinking tier — omit `model:` so `architect`, `ai-expert` and `Plan` inherit the session and the fallback comes free.
{{PLAN_SPECIFIC_ROUTING}}
- `{{DEFAULT_EFFORT}}` is the default effort. {{EFFORT_RULE}}
- Delegate logs, test output, CI/CD and kubectl/helm output to `log-reader`. Never read raw logs in the main context.
- Implement code yourself in the main conversation. `ai-implementer` is for mechanical pattern-copying steps or when the user asks.

# Context hygiene

The main session re-reads its whole context every turn, so context length — not model choice — is the largest cost.

- Do not pull a file longer than ~{{READ_LINES}} lines into the main context. A hook refuses an unbounded `Read` of a larger file; pass an explicit `limit` when you genuinely need it, or send a subagent.
- Never `cat` logs, test output, migrations, lockfiles or generated code into the main context.
- Search with `grep -n` and read the hits, instead of reading whole files to search them.
- Prefer one subagent that returns twenty lines over five tool calls whose output stays in context all session.
- `/clear` when switching tasks. Auto-compaction fires near {{COMPACT_WINDOW}} tokens, but a compacted session is a summary of the old task, not a clean start.
- Prefer deterministic tools — `rg`, `git`, `jq`, the framework CLI, the test runner — over asking a model to infer what they answer exactly.

# Agentic pipeline (takes precedence in any repository with `.ai/`)

`.ai/AGENTS.md` is the entry point and `.ai/policies/` are binding. **Production behaviour is the source of truth**: document the problems you find outside the current task, do not fix them.

- Work runs through `/ai-task <request>`: discovery → context → impact → risk tier → plan → plan review → implementation → test → adversarial review → security review → release report → human approval. Stages get lighter for small changes; **none is skipped**.
- The tier in `.ai/policies/risk-tiers.json` decides who plans, who reviews and whether a human approves. Payments, tax, fiscal, authentication, authorization, order state transitions and customer data are **T4**; migrations, infrastructure and production architecture are **T5**. An agent may raise a tier; only a human lowers one.
- Each implementation step names the files it may touch. An edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED` and have the plan amended rather than widening scope quietly.
- Legacy behaviour with no test gets a characterization test **first**. Never combine a refactoring with a feature change.
- Run `ai-reviewer` after a change and before proposing a commit; `ai-security` as well for T4/T5 and anything touching auth or personal data.
- `architect` is for design questions outside a task, or in a repository without `.ai/`. Inside a task, `ai-planner` plans and `ai-expert` is the escalation.
- Three hooks enforce this. `ai-git-guard` runs in **every** repository: no force push, no history rewrite, no push or merge to a protected branch, no `--no-verify`, no staging a secret, no production deploy. `ai-path-guard` and `ai-scope-guard` activate only where `.ai/` exists.
- No agent commits, merges or deploys on its own initiative. The pipeline ends at human approval.

# Project layout & SDLC

- A repository with no `.ai/` gets `/ai-init` first: it surveys the codebase, writes `.ai/`, and runs the `docs/sdlc/` scaffold as well. `/project-init` alone is for a repo that wants only the SDLC layout. `/ai-audit` scores an existing setup against the twelve AI-native SDLC plays.
- `/ai-task` is the default route for a change. Work that needs a written intent and specification first goes `/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan`, and then hands the plan to `/ai-task` for the build.
- SDLC artefacts live in `docs/sdlc/`, decisions in `docs/sdlc/adr/`, project notes in `.claude/memory/`, task artefacts and the audit trail in `.ai/reports/<task-id>/`.
<!-- claude-agentic:end -->
