<!-- stub: scope=doc runtime=none -->
<!-- The long-form reference installed beside the stub, at
     {{HOME}}/riskrails/routing.md, and read on demand — never at session start.
     Same directive syntax as instructions/stub.md; rendered per runtime and per plan
     by install.sh. Nothing here may be needed to work safely: what an agent must know
     without reading a file belongs in the stub. -->

<!-- stub: runtime=claude -->
# Model routing ({{PLAN}} plan)

<!-- stub: runtime=claude -->
Facts are collected cheaply; thinking is paid for. Session model {{SESSION_MODEL}}, fallback {{FALLBACK_MODEL}}, default effort `{{DEFAULT_EFFORT}}`.

<!-- stub: runtime=claude -->
| Tier | Model / effort | Used for |
|---|---|---|
| FAST | `{{FAST_MODEL}}` / `{{FAST_EFFORT}}` | reading and running: file search, listings, counting, logs and test output, running a command and reporting it (`Explore`, `log-reader`) |
| BALANCED | `{{BALANCED_MODEL}}` / `low`–`{{BALANCED_EFFORT}}` | discovery with judgement, the review in guarded mode (`ai-discovery`, `ai-reviewer` in guarded mode) |
| STRONG | `{{STRONG_MODEL}}` / `{{STRONG_EFFORT}}` | the review in full mode, adversarial and security review (`ai-reviewer`, with a `focus: security` brief when domain is 2) |
| EXPERT | {{EXPERT_ROW}} | design (`architect`), only when STRONG said it cannot settle the question |

<!-- stub: runtime=claude -->
{{PLAN_SPECIFIC_ROUTING}}
- Every agent definition and Workflow `agent()` call declares `model:` and `effort:`. Readers and runners never go above `low`. Forks inherit the session and take no `model`.
- Five or more parallel agents never run on `{{STRONG_MODEL}}`. Escalate one task at a time on a stated trigger, never the whole fleet; never retry a failed thinking task on a cheaper model.
- {{EFFORT_RULE}}
- Planning, the weight, the test run and the release are the session's work, not an agent's: `/rr-plan`, `state.py weight`, `state.py verify`, `/rr-ship`.
- Implement in the main session. Delegate reading: logs and test output to `log-reader`, wide searches to `Explore` — both on `{{FAST_MODEL}}`. Nothing below T4 runs on `{{STRONG_MODEL}}`. The conclusion a human reads is written here, never delegated.
- Split code reading by how many hops it needs. A lookup — where X is, one route, service id, config key or template — goes to `Explore` on `{{FAST_MODEL}}`. A trace of how the *installed* third-party code behaves (`vendor/`, `node_modules/`: decorators, compiler passes, service or template overrides, event subscribers) goes to a BALANCED reader at `low` — `ai-discovery`, or `Explore` spawned with `model: {{BALANCED_MODEL}}` where there is no `.ai/` — because a FAST reader stops at the first plausible match, and there a wrong answer reads like a right one.

<!-- stub: runtime=claude -->
# Context hygiene

<!-- stub: runtime=claude -->
- Search with `grep -n` and read the hits. No unbounded `Read` over ~{{READ_LINES}} lines — a hook refuses it, and a `limit` larger than that budget is refused too. Never `cat` logs, lockfiles, migrations or generated code.
- A file too large to open is read by the cheapest model, never here: send `Explore` (code) or `log-reader` (logs, test output) and take back only the relevant excerpt with `file:line` — never the file.
- Tools and MCP servers are context too, in every turn, used or not. Default off: `enableAllProjectMcpServers: false`, a project enables only what nearly every task needs, a task names anything extra in one line and turns it off again, and deferred tools are loaded in one batched call. See `.ai/policies/tooling.md`.
- One subagent returning twenty lines beats five tool calls whose output stays in context all session.
- Deterministic tools first: `rg`, `git`, `jq`, the framework CLI, the test runner.
- `/clear` between tasks, and after every task that ran a review. Compaction near {{COMPACT_WINDOW}} tokens is a summary of the old task, not a clean start; until then every turn re-reads the whole history.
- `context-guard` measures the context on every prompt: a one-line warning from {{CONTEXT_WARN}} tokens, {{CONTEXT_BLOCK}}. When its note says the prompt starts a different task, suggest `/clear` before doing the work. Before a compaction it saves the edited files, the latest instructions verbatim, the todo list and the git state, and hands them back afterwards as "Session state before compaction": trust that block over the summary where they differ, and re-read a file before editing it rather than relying on what the summary says it contains.
- Run tests once, to the end, and fix every failure as one batch. Never one failure, one fix, one run.
- `/usage-report` shows where the tokens went, at zero model cost; `--provider both` puts Codex next to Claude Code.

<!-- stub: runtime=claude -->
# Guards

<!-- stub: runtime=claude -->
- `ai-git-guard` runs in every repository: no force push, history rewrite, push or merge to a protected branch, `--no-verify`, staged secret or production deploy. `ai-path-guard` and `ai-scope-guard` arm only where `.ai/` exists. No agent merges or deploys; commit, push and approval run only as the command the human picked in the dialog, as the harness recorded — verbatim, once — or the human runs them outside the agent.
- `context-guard` measures the context on every prompt and holds a prompt back once at the block threshold above, when there is one; its "Session state before compaction" block and `.ai/state/handoff.md` are what a resumed session trusts over the summary.

<!-- stub: runtime=codex -->
# Model allocation by task and scope (host-wide, ChatGPT {{CODEX_PLAN}} plan)

<!-- stub: runtime=codex -->
Applies everywhere a model can be chosen: an explicit spawn request, a custom agent file under `~/.codex/agents/` or `.codex/agents/`, the `[agents]` defaults in `config.toml`, and any skill that asks for delegation. **The session runs {{SESSION_MODEL}} at `{{SESSION_EFFORT}}`; subagents default to {{BALANCED_MODEL}}, and STRONG and EXPERT agents are paid for only on a named trigger.** Facts are collected cheaply; the expensive tiers are for adversarial review, high-risk decisions and what a cheaper tier could not settle — never for fact collection.

<!-- stub: runtime=codex -->
| Tier | Model | Effort | Role |
|---|---|---|---|
| FAST | `{{FAST_MODEL_ID}}` | `{{FAST_EFFORT}}` | verbatim extraction, file and symbol inventories, listings, counting, logs and test output, running a command and reporting it (`Explore`, `log-reader`) |
| BALANCED — default for agents | `{{BALANCED_MODEL_ID}}` | `{{BALANCED_EFFORT}}` | discovery with judgement, at `low` (`ai-discovery`) |
| STRONG | `{{STRONG_MODEL_ID}}` | `{{STRONG_EFFORT}}` | the {{STRONG_MODEL}} triggers below (`ai-reviewer`, `architect`) |
| EXPERT | `{{EXPERT_MODEL_ID}}` | `{{EXPERT_EFFORT}}` | the EXPERT triggers below: a spawn with no agent named and `model` set to `{{EXPERT_MODEL_ID}}`, with a brief |

<!-- stub: runtime=codex -->
The main session itself runs {{SESSION_MODEL}} at `{{SESSION_EFFORT}}` and does the implementation; the tiers above are for agents. Planning, the weight, the test run and the release are the session's work: `/rr-plan`, `state.py weight`, `state.py verify`, `/rr-ship`.

<!-- stub: runtime=codex -->
## {{STRONG_MODEL}} (STRONG) — only on one of these triggers

<!-- stub: runtime=codex -->
1. **Review** of a finished change before a commit is proposed: `ai-reviewer`. Brief it with `focus: security` for authentication, authorization, secrets, payments, personal data, webhooks — a full-mode task whose domain is 2.
2. **Plan**: a full-mode plan whose design is open — `architect`. The session plans everything else, and the weight is `state.py weight`, never an agent.
3. **Root cause** after a first diagnosis in the session already failed once (the fix did not hold, or competing hypotheses remain), or a bug in concurrency, retries/idempotency, caching or data integrity.
4. **Reversible design** with two or more viable options that are costly to change later — module structure, service boundaries, a library choice: `architect`.

<!-- stub: runtime=codex -->
## {{EXPERT_MODEL}} (EXPERT) — only on one of these triggers

<!-- stub: runtime=codex -->
1. **T6**: a migration, infrastructure or production-architecture decision — the session plans it and puts the open decision to EXPERT.
2. **STRONG could not settle it**: {{STRONG_MODEL}} answered `confidence: uncertain`, or two STRONG results contradict each other (plan against review).
3. **Irreversible design** with several viable options — core data model, public API or event contract, service split: an EXPERT spawn with the options as its brief.
4. **Final check** of a T6 plan, or of a production-incident root cause, before a human acts on it.

<!-- stub: runtime=codex -->
## Rules for the expensive tiers

<!-- stub: runtime=codex -->
- Name the trigger when escalating ("{{STRONG_MODEL}} — root cause, second failed fix"). No trigger, no escalation: never "just in case", never the whole fleet. An agent may raise a tier; only the user lowers one.
- One {{STRONG_MODEL}} or EXPERT agent per question, and one EXPERT agent per task unless the user asks for more. Never fan out on them: a sweep of three or more parallel agents runs on {{FAST_MODEL}}.
- Collect first, cheaply. {{FAST_MODEL}} gathers the facts; the expensive agent then gets a compact brief — the task's context summary, `file:line` facts, the question and the options — never "explore the repository".
- Never retry a failed *thinking* task on a cheaper model; downgrading is for mechanical work.
- Every subagent pays its own start-up. Spawn one to keep hundreds of lines of reading out of the main context, not for what one `rg` answers.
- Ask for a named agent (`ai-reviewer`, `ai-discovery`, …) rather than "spawn a subagent". A spawn with no agent named resolves to `agents.default_subagent_model` — {{BALANCED_MODEL}} — never the tier the role needs.
- Readers, scouts and runners never go above `low` effort. Final synthesis and anything the user reads stays in the main session.
- Split code reading by how many hops it needs. A lookup — where X is, one route, service id, config key or template — goes to `Explore` on {{FAST_MODEL}}. A trace of how the *installed* third-party code behaves (`vendor/`, `node_modules/`: decorators, compiler passes, service or template overrides, event subscribers) goes to `ai-discovery`, named, which runs on {{BALANCED_MODEL}} at `low` in a read-only sandbox. A FAST reader stops at the first plausible match, and there a wrong answer reads like a right one.
- At most {{MAX_THREADS}} agent threads run at once (`agents.max_concurrent_threads_per_session`). Write-heavy work is not fanned out: parallel agents editing the same tree create conflicts.

<!-- stub: runtime=codex -->
# Model routing (Codex)

<!-- stub: runtime=codex -->
- Session model is {{SESSION_MODEL_ID}} at `{{SESSION_EFFORT}}`. Implement code yourself in the main conversation.
- Do not switch a running session to a stronger model for one hard question. Send the question to `architect`, or to an EXPERT spawn, with a brief instead, and keep the session where it is.
{{CODEX_PLAN_RULE}} Readers never go above `low`.
- `runtime-gate` checks {{EXPERT_MODEL}} at run time. After a rate-limit or model-unavailable failure from an {{EXPERT_MODEL}} subagent, the gate sends every EXPERT launch to {{STRONG_MODEL}} until the record expires, and says so in the agent's context. `~/.codex/hooks/runtime-gate.py status` shows the gate; `clear` re-enables {{EXPERT_MODEL}} early. An ordinary low-confidence or wrong answer never activates it.
- `{{SUBAGENT_EFFORT}}` is the default effort for agents. Raise to `high` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; above `high` only per the rule above.
- Delegate logs, test output, CI/CD and kubectl/helm output to `log-reader`. Never read raw logs in the main context.

<!-- stub: runtime=codex -->
# Context hygiene

<!-- stub: runtime=codex -->
The main session re-reads its whole context every turn, so context length — more than model choice — is the largest cost.

<!-- stub: runtime=codex -->
- Do not pull a file longer than ~{{READ_LINES}} lines into the main context. Read the ranges you need, or send a FAST reader — `Explore` for code, `log-reader` for output — which returns only the relevant excerpt with `file:line`, never the file.
- Never `cat` logs, test output, migrations, lockfiles or generated code into the main context.
- Search with `rg -n` and read the hits, instead of reading whole files to search them.
- Prefer one subagent that returns twenty lines over five tool calls whose output stays in context all session.
- Start a new thread when switching tasks, and after every task that ran a review. A compacted session is a summary of the old task, not a clean start.
- Run tests once, to the end, and fix every failure as one batch. Never one failure, one fix, one run.
- Prefer deterministic tools — `rg`, `git`, `jq`, the framework CLI, the test runner — over asking a model to infer what they answer exactly.
- Tools and MCP servers are context too, in every turn, used or not. Default off: a project enables only what nearly every task needs, a task names anything extra in one line and turns it off again, and `--strict-mcp-config` beats disabling servers afterwards. See `.ai/policies/tooling.md`.
- `/usage-report` shows where the tokens went, at zero model cost. `--provider both` reports Codex and Claude Code side by side.

<!-- stub: runtime=codex -->
# Guards

<!-- stub: runtime=codex -->
- `ai-git-guard` runs in every repository: no force push, history rewrite, push or merge to a protected branch, `--no-verify`, staged secret or production deploy. `ai-path-guard` and `ai-scope-guard` arm only where `.ai/` exists. All three see `Bash` and `apply_patch`; run `/hooks` once after installing to review and trust them, or they are skipped. No agent merges or deploys; commit, push and approval run only as the command the human picked in the dialog — verbatim, once — or the human runs them outside the agent.
- `architect` is for design questions outside a task, in a repository without `.ai/`, and in a full-mode task whose design is open (`/rr-plan`). Otherwise the session plans, and an EXPERT spawn is the escalation.

<!-- stub: runtime=claude,codex -->
- Shared `.ai/` files — policies, agent contracts, workflows, templates — are installed once in `{{AI_SHARED}}/`. A project's own regular file at the same path under `.ai/` overrides it; `{{AI_RESOLVER}} <path>` prints the one to read.
