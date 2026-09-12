<!-- claude-agentic:start -->
# Model allocation by task and scope (host-wide)

Applies everywhere a model can be chosen: the Agent tool's `model`/`effort`, `.claude/agents/*.md` frontmatter, Workflow `agent()` calls, scheduled jobs. **The session runs {{SESSION_MODEL}} at `{{DEFAULT_EFFORT}}`; agents default to Sonnet, and STRONG and EXPERT agents are paid for only on a named trigger.** Facts are collected cheaply; the expensive tiers are for adversarial review, high-risk decisions and what a cheaper tier could not settle — never for fact collection.

| Tier | Model | Effort | Role |
|---|---|---|---|
| FAST | `haiku` | `low` | verbatim extraction, file and symbol inventories, listings, counting, running a command and reporting its output (`ai-indexer`) |
| BALANCED — default for agents | `sonnet` | `low`–`medium` | discovery, context compression, planning up to T2, tests, release assembly, mechanical edits (`Explore`, `Plan`, `general-purpose`, `log-reader`, `ai-discovery`, `ai-context`, `ai-risk`, `ai-planner`, `ai-tester`, `ai-release`, `ai-implementer`) |
| STRONG | `opus` | `high` | the Opus triggers below (`ai-reviewer`, `ai-security`, `architect`; `ai-risk`/`ai-planner` with `model: opus`) |
| EXPERT | `{{EXPERT_MODEL}}` | `{{EXPERT_EFFORT}}` | the EXPERT triggers below (`ai-expert`; `architect` with `model: {{EXPERT_MODEL}}`) |

The main session itself runs {{SESSION_MODEL}} at `{{DEFAULT_EFFORT}}` and does the implementation; the tiers above are for agents.

## Opus (STRONG) — only on one of these triggers

1. **Review** of a finished change before a commit is proposed: `ai-reviewer`. Add `ai-security` for authentication, authorization, secrets, payments, personal data, webhooks, and any T4/T5 change.
2. **Risk and plan**: `ai-risk` on Sonnet answered T3+ or `confidence: uncertain` — re-run it with `model: opus`; `ai-planner` with `model: opus` at T3/T4.
3. **Root cause** after a first diagnosis in the session already failed once (the fix did not hold, or competing hypotheses remain), or a bug in concurrency, retries/idempotency, caching or data integrity.
4. **Reversible design** with two or more viable options that are costly to change later — module structure, service boundaries, a library choice: `architect`.

## {{EXPERT_MODEL_HUMAN}} (EXPERT) — only on one of these triggers

1. **T5**: a migration, infrastructure or production-architecture decision — `ai-expert` plans it.
2. **STRONG could not settle it**: Opus answered `confidence: uncertain`, or two Opus results contradict each other (plan against review).
3. **Irreversible design** with several viable options — core data model, public API or event contract, service split: `ai-expert`, or `architect` with `model: {{EXPERT_MODEL}}`.
4. **Final check** of a T5 plan, or of a production-incident root cause, before a human acts on it.

## Rules for the expensive tiers

- Name the trigger when escalating ("Opus — root cause, second failed fix"). No trigger, no escalation: never "just in case", never the whole fleet. An agent may raise a tier; only the user lowers one.
- One Opus or EXPERT agent per question, and one EXPERT agent per task unless the user asks for more. Never fan out on them: a sweep of three or more parallel agents runs on `haiku` or `sonnet`.
- Collect first, cheaply. Haiku and Sonnet gather the facts; the expensive agent then gets a compact brief — the `ai-context` summary, `file:line` facts, the question and the options — never "explore the repository".
- Never retry a failed *thinking* task on a cheaper model; downgrading is for mechanical work. An overload is not a failure: `fallbackModel` moves any agent to {{FALLBACK_MODEL}} on its own.
- Every subagent pays its own start-up (system prompt and tools written to cache). Spawn one to keep hundreds of lines of reading out of the main context, not for what one `grep` answers.
- Forks (`subagent_type: 'fork'`) always inherit the session model — never pass `model` there.
- Every `.claude/agents/*.md` and every Workflow `agent()` call declares `model:` and `effort:` explicitly. An omitted `model:` resolves to `CLAUDE_CODE_SUBAGENT_MODEL` (Sonnet), never the tier the role needs.
- Readers, scouts and runners never go above `effort: low`. Final synthesis and anything the user reads stays in the main session.

# Model routing ({{PLAN}} plan)

- Session model is {{SESSION_MODEL}}; the harness falls back to {{FALLBACK_MODEL}}. Implement code yourself in the main conversation; `ai-implementer` is for mechanical pattern-copying steps or when the user asks.
- Do not switch a running session to a stronger model for one hard question: each model has its own cache, so `/model` re-reads the whole conversation uncached at the new price. Send the question to `architect` or `ai-expert` with a brief. Switch the main model only in a fresh session dedicated to design, and back to {{SESSION_MODEL}} afterwards.
{{PLAN_SPECIFIC_ROUTING}}
- `{{DEFAULT_EFFORT}}` is the default effort. {{EFFORT_RULE}}
- Delegate logs, test output, CI/CD and kubectl/helm output to `log-reader`. Never read raw logs in the main context.

# Context hygiene

The main session re-reads its whole context every turn, so context length — more than model choice — is the largest cost.

- Do not pull a file longer than ~{{READ_LINES}} lines into the main context. A hook refuses an unbounded `Read` of a larger file; pass an explicit `limit` when you genuinely need it, or send a subagent.
- Never `cat` logs, test output, migrations, lockfiles or generated code into the main context.
- Search with `grep -n` and read the hits, instead of reading whole files to search them.
- Prefer one subagent that returns twenty lines over five tool calls whose output stays in context all session.
- `/clear` when switching tasks. Auto-compaction fires near {{COMPACT_WINDOW}} tokens, but a compacted session is a summary of the old task, not a clean start.
- The prompt cache expires after an idle hour, and the next turn writes the whole context again at twice the input price. Before a long break in a large session, `/compact` it or finish the task and `/clear`.
- Prefer deterministic tools — `rg`, `git`, `jq`, the framework CLI, the test runner — over asking a model to infer what they answer exactly.
- `/usage-report` shows where the tokens went, at zero model cost.

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
