<!-- claude-agentic:start -->
# Model routing ({{PLAN}} plan)

Facts are collected cheaply; thinking is paid for. Session model {{SESSION_MODEL}}, fallback {{FALLBACK_MODEL}}, default effort `{{DEFAULT_EFFORT}}`.

| Tier | Model / effort | Used for |
|---|---|---|
| FAST | `haiku` / `low` | reading and running: file search, listings, counting, logs and test output, running a command and reporting it (`Explore`, `log-reader`, `ai-tester`, `ai-indexer`) |
| BALANCED | `sonnet` / `low`–`medium` | discovery with judgement, context compression, mechanical edits, release assembly, the T2 review (`ai-discovery`, `ai-context`, `ai-implementer`, `ai-release`, `ai-reviewer` at T2) |
| STRONG | `opus` / `high` | planning and plan review at T3+, adversarial review, security review (`ai-planner`, `ai-reviewer`, `ai-security`) |
| EXPERT | {{EXPERT_ROW}} | design (`architect`) and `ai-expert`, only when STRONG said it cannot settle the question |

{{PLAN_SPECIFIC_ROUTING}}
- Every agent definition and Workflow `agent()` call declares `model:` and `effort:`. Readers and runners never go above `low`. Forks inherit the session and take no `model`.
- Five or more parallel agents never run on `opus`. Escalate one task at a time on a stated trigger, never the whole fleet; never retry a failed thinking task on a cheaper model.
- {{EFFORT_RULE}}
- Implement in the main session. Delegate reading: logs and test output to `log-reader`, wide searches to `Explore` — both on `haiku`. Nothing below T3 runs on `opus`. The conclusion a human reads is written here, never delegated.

# Context hygiene

Context length, not model choice, is the largest cost: the session re-reads everything every turn.

- Search with `grep -n` and read the hits. No unbounded `Read` over ~{{READ_LINES}} lines — a hook refuses it; pass `limit` when you must. Never `cat` logs, lockfiles, migrations or generated code.
- One subagent returning twenty lines beats five tool calls whose output stays in context all session.
- Deterministic tools first: `rg`, `git`, `jq`, the framework CLI, the test runner.
- `/clear` between tasks, and after every task that ran a review. Compaction near {{COMPACT_WINDOW}} tokens is a summary of the old task, not a clean start; a session past ~150k tokens is paying for its history on every turn.
- Run tests once, to the end, and fix every failure as one batch. Never one failure, one fix, one run.
- `/usage-report` shows where the tokens went, at zero model cost; `--provider both` puts Codex next to Claude Code.

# Agentic pipeline (in any repository with `.ai/`)

`.ai/AGENTS.md` is the entry point, `.ai/policies/` are binding, and **production behaviour is the source of truth**: document problems outside the task, do not fix them.

- A change runs through `/ai-task <request>`. `.ai/policies/risk-tiers.json` sets the tier (T0–T5) and the `pipeline_profile`. In the default `solo` profile T0–T2 run in **direct mode**: name the files, edit, one verification run at the end, failures fixed as one batch, one `sonnet` review at T2, no report files (T2 is one `state.py quick` call so the scope guard is armed). The full SDLC pipeline — delegated plan, plan review, `opus` review, security at T4+, release report — runs from T3. Tests run once, after the last step, to the end, then one `state.py remediate` step fixes every regression together.
- Payments, tax, fiscal, auth, order state transitions and customer data are T4; migrations, infrastructure and production architecture are T5. An agent may raise a tier; only a human lowers one.
- Each step names the files it may touch; an edit outside them is refused — answer `SCOPE_CHANGE_REQUIRED` and amend the step. Legacy behaviour without a test gets a characterization test first. Never mix a refactoring with a feature change.
- Verify before reporting done: run the verification command from `.ai/policies/testing.md` (or the project `CLAUDE.md`) and show its output. A bugfix starts with the failing test.
- When a review flags the same mistake a second time, the correction goes into the project `CLAUDE.md`.
- `ai-git-guard` runs in every repository: no force push, history rewrite, push or merge to a protected branch, `--no-verify`, staged secret or production deploy. `ai-path-guard` and `ai-scope-guard` arm only where `.ai/` exists. No agent commits, merges or deploys on its own; the pipeline ends at human approval.
- A repository without `.ai/` gets `/ai-init` first; one that has it gets `/project-update` after the plugin is reinstalled (running `/ai-init` or `/project-init` again does the same). A repository may carry both `CLAUDE.md` and `AGENTS.md`: one `.ai/` tree, one task state, two runtimes. `/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan` when a written intent and spec must exist before code; the plan then goes to `/ai-task`. Artefacts live in `docs/sdlc/`, decisions in `docs/sdlc/adr/`, task audit trails in `.ai/reports/<task-id>/`.
<!-- claude-agentic:end -->
