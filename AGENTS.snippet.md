<!-- claude-agentic:start -->
# Model allocation by task and scope (host-wide)

Applies everywhere a model can be chosen: an explicit spawn request, a custom agent file under `~/.codex/agents/` or `.codex/agents/`, the `[agents]` defaults in `config.toml`, and any skill that asks for delegation. **The session runs {{SESSION_MODEL}} at `{{SESSION_EFFORT}}`; subagents default to {{BALANCED_MODEL}}, and STRONG and EXPERT agents are paid for only on a named trigger.** Facts are collected cheaply; the expensive tiers are for adversarial review, high-risk decisions and what a cheaper tier could not settle — never for fact collection.

| Tier | Model | Effort | Role |
|---|---|---|---|
| FAST | `{{FAST_MODEL_ID}}` | `low` | verbatim extraction, file and symbol inventories, listings, counting, running a command and reporting its output (`ai-indexer`, `Explore`, `ai-discovery`, `log-reader`) |
| BALANCED — default for agents | `{{BALANCED_MODEL_ID}}` | `medium` | context compression, planning up to T2, tests, release assembly, mechanical edits (`ai-context`, `ai-risk`, `ai-planner`, `ai-tester`, `ai-release`, `ai-implementer`) |
| STRONG | `{{STRONG_MODEL_ID}}` | `high` | the {{STRONG_MODEL}} triggers below (`ai-reviewer`, `ai-security`, `architect`, `ai-risk-strong`, `ai-planner-strong`) |
| EXPERT | `{{EXPERT_MODEL_ID}}` | `{{EXPERT_EFFORT}}` | the EXPERT triggers below (`ai-expert`) |

The main session itself runs {{SESSION_MODEL}} at `{{SESSION_EFFORT}}` and does the implementation; the tiers above are for agents.

## {{STRONG_MODEL}} (STRONG) — only on one of these triggers

1. **Review** of a finished change before a commit is proposed: `ai-reviewer`. Add `ai-security` for authentication, authorization, secrets, payments, personal data, webhooks, and any T4/T5 change.
2. **Risk and plan**: `ai-risk` on {{BALANCED_MODEL}} answered T3+ or `confidence: uncertain` — re-run it as `ai-risk-strong`; use `ai-planner-strong` at T3/T4.
3. **Root cause** after a first diagnosis in the session already failed once (the fix did not hold, or competing hypotheses remain), or a bug in concurrency, retries/idempotency, caching or data integrity.
4. **Reversible design** with two or more viable options that are costly to change later — module structure, service boundaries, a library choice: `architect`.

## {{EXPERT_MODEL}} (EXPERT) — only on one of these triggers

1. **T5**: a migration, infrastructure or production-architecture decision — `ai-expert` plans it.
2. **STRONG could not settle it**: {{STRONG_MODEL}} answered `confidence: uncertain`, or two STRONG results contradict each other (plan against review).
3. **Irreversible design** with several viable options — core data model, public API or event contract, service split: `ai-expert`.
4. **Final check** of a T5 plan, or of a production-incident root cause, before a human acts on it.

## Rules for the expensive tiers

- Name the trigger when escalating ("{{STRONG_MODEL}} — root cause, second failed fix"). No trigger, no escalation: never "just in case", never the whole fleet. An agent may raise a tier; only the user lowers one.
- One {{STRONG_MODEL}} or EXPERT agent per question, and one EXPERT agent per task unless the user asks for more. Never fan out on them: a sweep of three or more parallel agents runs on {{FAST_MODEL}}.
- Collect first, cheaply. {{FAST_MODEL}} gathers the facts; the expensive agent then gets a compact brief — the `ai-context` summary, `file:line` facts, the question and the options — never "explore the repository".
- Never retry a failed *thinking* task on a cheaper model; downgrading is for mechanical work.
- Every subagent pays its own start-up. Spawn one to keep hundreds of lines of reading out of the main context, not for what one `rg` answers.
- Ask for a named agent (`ai-reviewer`, `ai-discovery`, …) rather than "spawn a subagent". A spawn with no agent named resolves to `agents.default_subagent_model` — {{BALANCED_MODEL}} — never the tier the role needs.
- Readers, scouts and runners never go above `low` effort. Final synthesis and anything the user reads stays in the main session.
- At most {{MAX_THREADS}} agent threads run at once (`agents.max_concurrent_threads_per_session`). Write-heavy work is not fanned out: parallel agents editing the same tree create conflicts.

# Model routing (Codex)

- Session model is {{SESSION_MODEL_ID}} at `{{SESSION_EFFORT}}`. Implement code yourself in the main conversation; `ai-implementer` is for mechanical pattern-copying steps or when the user asks.
- Do not switch a running session to a stronger model for one hard question. Send the question to `architect` or `ai-expert` with a brief instead, and keep the session where it is.
- `xhigh` is allowed only for `ai-expert` and verify/judge stages on {{EXPERT_MODEL}}; `max` and `ultra` stay off. Readers never go above `low`.
- `codex-model-gate` checks {{EXPERT_MODEL}} at run time. After a rate-limit or model-unavailable failure from an {{EXPERT_MODEL}} subagent, the gate sends every EXPERT launch to {{STRONG_MODEL}} until the record expires, and says so in the agent's context. `~/.codex/hooks/codex-model-gate.py status` shows the gate; `clear` re-enables {{EXPERT_MODEL}} early. An ordinary low-confidence or wrong answer never activates it.
- `medium` is the default effort for agents. Raise to `high` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; above `high` only per the rule above.
- Delegate logs, test output, CI/CD and kubectl/helm output to `log-reader`. Never read raw logs in the main context.

# Context hygiene

The main session re-reads its whole context every turn, so context length — more than model choice — is the largest cost.

- Do not pull a file longer than ~{{READ_LINES}} lines into the main context. Read the ranges you need, or send a subagent.
- Never `cat` logs, test output, migrations, lockfiles or generated code into the main context.
- Search with `rg -n` and read the hits, instead of reading whole files to search them.
- Prefer one subagent that returns twenty lines over five tool calls whose output stays in context all session.
- Start a new thread when switching tasks. A compacted session is a summary of the old task, not a clean start.
- Prefer deterministic tools — `rg`, `git`, `jq`, the framework CLI, the test runner — over asking a model to infer what they answer exactly.
- `/usage-report` shows where the tokens went, at zero model cost. `--provider both` reports Codex and Claude Code side by side.

# Agentic pipeline (in any repository with `.ai/`)

`.ai/AGENTS.md` is the entry point, `.ai/policies/` are binding, and **production behaviour is the source of truth**: document problems outside the task, do not fix them.

- A change runs through `/ai-task <request>`. `.ai/policies/risk-tiers.json` sets the tier (T0–T5) and the `pipeline_profile`. In the default `solo` profile the developer's knowledge is the first source of context; T0–T2 triage in one `state.py triage` call, T0/T1 have no plan (say which files, edit, verify), T2 gets a short inline step list, and a subagent is spawned only where the tier needs a second context window: review at T2+, planning at T3+ (`ai-planner-strong`), security at T4+. Tests run once, after the last step, not per step.
- Payments, tax, fiscal, auth, order state transitions and customer data are T4; migrations, infrastructure and production architecture are T5. An agent may raise a tier; only a human lowers one.
- Each step names the files it may touch; an edit outside them is refused — answer `SCOPE_CHANGE_REQUIRED` and amend the step. One `apply_patch` is checked file by file, so a patch that reaches outside the step is refused whole. Legacy behaviour without a test gets a characterization test first. Never mix a refactoring with a feature change.
- Verify before reporting done: run the verification command from `.ai/policies/testing.md` (or the project `AGENTS.md`) and show its output. A bugfix starts with the failing test.
- When a review flags the same mistake a second time, the correction goes into the project `AGENTS.md`.
- `architect` is for design questions outside a task, or in a repository without `.ai/`. Inside a task, `ai-planner`/`ai-planner-strong` plans and `ai-expert` is the escalation.
- `ai-git-guard` runs in every repository: no force push, history rewrite, push or merge to a protected branch, `--no-verify`, staged secret or production deploy. `ai-path-guard` and `ai-scope-guard` arm only where `.ai/` exists. All three see `Bash` and `apply_patch`; run `/hooks` once after installing to review and trust them, or they are skipped. No agent commits, merges or deploys on its own; the pipeline ends at human approval.
- A repository without `.ai/` gets `/ai-init` first; one that has it gets `/project-update` after the plugin is reinstalled (running `/ai-init` or `/project-init` again does the same). `/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan` when a written intent and spec must exist before code; the plan then goes to `/ai-task`. Artefacts live in `docs/sdlc/`, decisions in `docs/sdlc/adr/`, project notes in `.codex/memory/`, task audit trails in `.ai/reports/<task-id>/`. A repository may carry both `CLAUDE.md` and `AGENTS.md`: one `.ai/` tree, one task state, two runtimes.
<!-- claude-agentic:end -->
