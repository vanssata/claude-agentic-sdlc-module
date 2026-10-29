# Runtimes and model routing

The tiers are the contract; the models are the implementation. A task names
tiers — FAST, BALANCED, STRONG, EXPERT — and the installed profile says which
model each tier is on this plan and this runtime. `state.py profile --tier
STRONG` prints it; `/rr-status` shows all four; the shared prompts name no
model, and `tests/test_shared_prompts_model_free.py` keeps it that way.

## One module, two runtimes

`.ai/**`, `state.py`, the weight table, the workflows and the skill bodies are
provider-neutral. The runtime-specific part is a thin adapter: where the files
go, what an agent definition looks like, how hooks are registered, which model
each tier resolves to.

| | Claude Code | Codex |
|---|---|---|
| install root | `~/.claude/` | `~/.codex/` |
| instruction file | `CLAUDE.md` | `AGENTS.md` |
| settings | `settings.json` (deep-merged) | `config.toml` (managed keys only) |
| agents | `agents/*.md`, YAML frontmatter | `agents/*.toml`, rendered from the same templates |
| hooks | `settings.json` `hooks` block | `hooks.json`, trusted in `/hooks` |
| edits arrive as | `Edit` / `Write`, one file | `apply_patch`, possibly many files |
| the human's dialog | `AskUserQuestion` | `request_user_input` |
| FAST | `haiku` | Terra (`gpt-5.6-terra`); Luna on BalancedMax |
| BALANCED | `sonnet` | Terra |
| STRONG | `opus` | Sol (`gpt-5.6-sol`) |
| EXPERT | Fable 5.1 [1m] on `architect`; Opus without Fable | Astra (`gpt-6-astra`) |
| session | Opus 5.5 [1m] at `medium` on Max; `opusplan` on Pro | Sol at `high` on Pro, `medium` on Plus |

A repository can carry both instruction files over one `.ai/` tree. The task
state is `.ai/state/state.json` either way, so a task started in one runtime
resumes in the other: `state.py handoff --to codex` (or `--to claude`) hands
it over, prints the command to resume it there and runs nothing; until the
other runtime resumes it, every state change from anywhere else exits 7
`RUNTIME_HANDOFF_PENDING`. Six files make that resume real, all written by
`state.py` or a hook, none by a model:

| File | Holds |
|---|---|
| `.ai/state/state.json` | the task: mode, stage, step, files, verify runs, review, gate |
| `.ai/reports/<task-id>/events.jsonl` | the journal — one append-only line per event, with the runtime that emitted it |
| `.ai/reports/<task-id>/task.md` | the task record: weight, plan, questions with their `[Answer]:` lines, verify, review, changes, verdict |
| `.ai/state/handoff.md` | at most thirty lines a session reads first: where the task is, what it may touch, what is pending |
| `.ai/state/session.json` | which runtime is driving, the prompt count, when the human last took a turn |
| `.ai/state/logs/<task-id>/` | the full test output, so it never reaches a context window; not committed |

## Model tiers

| Tier | Claude Code | Codex | Does |
|---|---|---|---|
| FAST | `haiku`, `low` | Terra, `low` | reading and running: file search, inventories, logs, test output (`Explore`, `log-reader`) |
| BALANCED | `sonnet`, `low`–`medium` | Terra, `medium` | discovery with judgement (`ai-discovery`), the review in guarded mode, the implementers and fixers of a batch build |
| STRONG | `opus`, `high` | Sol, `high` | the review in full mode, security review, `architect` in `/rr-spec`, root cause after a BALANCED diagnosis failed |
| EXPERT | `opus` at `xhigh` on Max; Fable 5.1 [1m] on `architect`; `opus` at `high` on Pro | Astra, `xhigh` on Pro, `high` on Plus | what STRONG could not settle: an irreversible design with several viable options |

The main session does the implementation itself, and the planning, the weight,
the test run and the release are its work too. Every agent definition pins its
own model, and `CLAUDE_CODE_SUBAGENT_MODEL` is deliberately not set. A STRONG
or EXPERT agent runs only on a named trigger, one at a time, never a fleet;
three or more parallel agents run on FAST or BALANCED; a failed reasoning task
is never retried on a cheaper model. The triggers and the escalation ladder
are in `policies/model-routing.md` of the shared tree.

**Each plan is one file in `profiles/`**: the runtime's own settings plus a
`riskrails` object with the tier table, the budgets and the dialog tool.
`max20.json` inherits `max.json` with larger budgets; `balanced-max.json`
inherits it with the session pinned to Opus 5.5 (200k), no Fable and EXPERT at
`high`. `scripts/resolve-profile.py` resolves the inheritance and writes
`<home>/riskrails/profile.json`; `runtime-gate` reads the budgets from there.

### Claude Code

| Plan | Session | FAST | BALANCED | STRONG | EXPERT / `architect` | Compaction |
|---|---|---|---|---|---|---|
| `pro`, `team-pro` | `opusplan` at `medium`: Opus in plan mode, Sonnet when executing | haiku | sonnet | opus `high` | opus `high`, pinned, so a Sonnet session cannot weaken it | the model window; 300 000 with `--context economy` |
| `max`, `team-max` | Opus 5.5 [1m] at `medium` | haiku | sonnet | opus `high` | opus `xhigh`; `architect` on `fable[1m]` at `xhigh` | the model window, near 967k; 800 000 with economy |
| `max20` | as `max` | | | | EXPERT twice per task without asking | as `max` |
| `balanced-max` | Opus 5.5 (200k) | haiku | sonnet | opus `high` | opus `high`; `architect` inherits the session, no Fable | near 167k |

`--fable no` on Max leaves `architect` on the Opus session. `/model opus` in a
Max session gives a 200k window, cheaper per turn for a small task; `claude-1m
opus|fable` pins the 1M window at launch. Team accounts map by seat: Standard →
`team-pro`, Premium → `team-max`; the installer reads the seat from
`~/.claude.json` and falls back to `team-pro` when it cannot tell.

Why the session matters most: in measured usage over 80% of the cost was the
main session re-reading its context, not output, so the session model and the
context length are the levers. `/rr-status --cost` shows the split on your
machine, across both runtimes.

### Codex

| Plan | Session | Threads | FAST | BALANCED | STRONG | EXPERT |
|---|---|---|---|---|---|---|
| `plus` | Sol `medium` | 3 | Terra `low` | Terra `medium` | Sol `high` | Astra `high`; `xhigh` never |
| `pro` | Sol `high` | 6 | Terra `low` | Terra `medium` | Sol `high` | Astra `xhigh`, twice per task without asking |
| `balanced-max` | Sol `high` | 6 | Luna `low` | Terra `medium` | Sol `high` | Astra `high` |

The plan is read from `chatgpt_plan_type` in `~/.codex/auth.json`;
`--codex-plan` overrides it, and an install that cannot tell assumes Pro and
says so. Every rendered Codex agent writes an explicit `model`,
`model_reasoning_effort` and `sandbox_mode = "read-only"`, because an omitted
`model` falls back to the Terra `[agents]` default.

**One difference worth knowing.** Codex resolves an agent's own file *ahead*
of the model asked for at spawn time. So "the same agent on a stronger model"
cannot work there: a named agent runs on the tier its file pins, and the
`ai-reviewer` file pins STRONG — a guarded-mode review on Codex therefore runs
on Sol, where Claude Code runs it on Sonnet. An EXPERT question on Codex is a
spawn with no agent named and the EXPERT model on the call. Same tier, same
trigger, different mechanism.

## The runtime gate

`runtime-gate.py` keeps the ladder honest at run time ([hooks.md](hooks.md)):
while the top model is rate-limited or unreachable, a launch that asks for it
goes one tier down (Fable → Opus; on Codex an EXPERT launch is rewritten to
STRONG); from 90% of the weekly limit every Fable launch goes to Opus until the
reset; an EXPERT launch beyond `expert.max_per_task` asks on Claude and
explains on Codex. `runtime-gate.py status` shows the gate, `clear` re-enables
the top model early. A reroute inside a task is journaled as `model_fallback`,
and every artefact that names a tier names the model that ran — a gate may
have sent an agent down a tier.

## No LOCAL tier

Neither runtime has a local-model backend. The work a local model would have
done — indexing, repetitive inspection — is done by deterministic tools (`rg`,
`git`, `jq`, the framework CLI) and by `Explore` on the cheapest hosted model.
Nothing in the design depends on a local model existing; one would slot in at
FAST.
