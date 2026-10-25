# Runtimes and model routing

One provider-neutral core, two thin runtime adapters, and the model each tier
resolves to on each plan.

## One module, two runtimes

`.ai/**`, the pipeline state machine, the risk tiers, the workflow contracts and
the skill bodies are provider-neutral. The runtime-specific part is a thin
adapter: where the files go, what an agent definition looks like, how hooks are
registered, and which model each tier resolves to.

| | Claude Code | Codex |
|---|---|---|
| install root | `~/.claude/` | `~/.codex/` |
| instruction file | `CLAUDE.md` | `AGENTS.md` |
| settings | `settings.json` (deep-merged) | `config.toml` (six managed keys) |
| agents | `agents/*.md`, YAML frontmatter | `agents/*.toml`, rendered from the same prompts |
| hooks | `settings.json` `hooks` block | `hooks.json` |
| edits arrive as | `Edit` / `Write`, one file | `apply_patch`, possibly many files |
| FAST | `haiku` | `gpt-5.6-terra` (Terra) |
| BALANCED | `sonnet` | `gpt-5.6-terra` (Terra) |
| STRONG | `opus` | `gpt-5.6-sol` (Sol) |
| EXPERT | Fable 5.1, or Opus 5 with `--fable no` | `gpt-6-astra` (Astra) |
| session | Opus 5.5 [1m] (`claude-opus-5-5[1m]`, 1M window) at `medium` by default on Max, `/model opus` for a 200k session (Sonnet on Pro) | Sol at `high` |

A repository can carry both instruction files over one `.ai/` tree. The task
state is `.ai/state/current.json` either way, so a task started in one runtime
resumes in the other.

Five files make that resume real, and every one of them is provider-neutral:

| File | Written by | Holds |
|---|---|---|
| `.ai/state/current.json` | `state.py`, `update.py` | the task: stage, step, risk tier, approval |
| `.ai/reports/<task-id>/events.jsonl` | `state.py` | the journal — one append-only line per event, with the runtime that emitted it |
| `.ai/reports/<task-id>/questions.md` | `state.py` | the open questions, each with an `[Answer]:` line a human fills in |
| `.ai/state/handoff.md` | `state.py`, rendered | thirty lines a session reads first: where the task is, what it may touch, what is pending |
| `.ai/reports/<task-id>/sensors.json` | `state.py review-gate` | what each deterministic sensor measured, and on which tree |
| `.ai/reports/<task-id>/tests-<scope>-<n>.log` | `state.py test-run` | the full test output, so it never reaches a context window |
| `.ai/state/session.json` | `context-guard.py` | which runtime is driving and when the human last took a turn |

A task also moves on purpose: `state.py handoff --to codex` (or `--to claude`)
hands it over, prints the command to resume it there and runs nothing; until the
other runtime resumes it, a state change (and `init --force`) from anywhere else
exits 7. `--for review` asks the other vendor for a T5+ review; its verdict never
clears the owner's own `blockers_open`, and moving the task again cancels an
open request. `init`, `quick` and `risk` print a
`preferred runtime:` line when the plan's table (refactoring → Codex on Claude
plans) or the quota rule points at the other runtime — advice only.

A subagent that needs a decision **returns** `QUESTIONS_NEEDED` instead of
asking; the manager writes the question into `questions.md`, a human answers it
there or in the session, and `state.py questions --sync` puts the answer back
into the state. The journal is what `/ai-status` and `/usage-report` read, at
zero model cost — no model is involved in writing or reading any of these files.

## Model tiers

Each plan is one file in `profiles/`: the runtime's own settings plus a
`claude_agentic` object with the tier table (which model and effort each of FAST,
BALANCED, STRONG and EXPERT is on that plan), the budgets (how many agents may run
at once and how many of them on STRONG, how far direct mode reaches, whether EXPERT
runs without asking, and a token figure per tier) and the preferred runtime per
workflow. `max20.json` is `max.json` with larger budgets; `balanced-max.json` is `max.json`
with the session pinned to Opus 5.5, no Fable and EXPERT at `high` — only the
session runs the strong model, every agent keeps its cheap tier. The installer writes the
resolved object to `<home>/claude-agentic/profile.json`; `runtime-gate` enforces the
fan-out and EXPERT budgets by asking, `state.py profile --tier <TIER>` prints a
tier's model, and `/usage-report --task <id>` compares a task's tokens with its
plan's figure — reported, never enforced. The prompts themselves name tiers only;
`tests/test-shared-prompts-model-free.sh` keeps it that way.

| Tier | Claude Code | Codex | Does |
|---|---|---|---|
| FAST | `haiku`, low | Terra, low | reading and running: file search, inventories, logs, test output (`Explore`, `log-reader`, `ai-tester`, `ai-indexer`) |
| BALANCED | `sonnet` | Terra, medium | discovery, context, planning up to T3, mechanical edits, release, the T2/T3 review (`ai-discovery`, `ai-context`, `ai-implementer`, `ai-release`) |
| STRONG | `opus`, high | Sol, high | adversarial and security review (from T4), T5 risk and planning, root cause after a first diagnosis failed, reversible design (`ai-reviewer`, `ai-security`, `architect`) |
| EXPERT | the session model (Opus 5) on Max, `opus` pinned on Pro; Fable 5.1 [1m] on `architect` only | Astra, `xhigh` | T6, irreversible design, what STRONG could not settle |

The main session does the implementation itself. Every agent definition pins its
own `model:` — most of them the BALANCED tier — and `CLAUDE_CODE_SUBAGENT_MODEL` is
deliberately not set: before Claude Code v2.1.251 it overrides the frontmatter and
the per-call model, which put every agent on Sonnet. A STRONG or EXPERT agent runs
only when a named trigger fires; the triggers are listed in `policies/model-routing.md` of the shared tree.

On a Max plan the session runs Opus 5.5 [1m] by default at `medium` effort,
compacting near 767k tokens (`autoCompactWindow` 800 000, uncapped on a 1M model)
— `/model opus` gives a 200k session that compacts near 167k, cheaper per turn for
a small task — and escalates from there: `ai-expert` pins `opus` at `xhigh`, so a session switched to
Sonnet (the JetBrains agent's Model setting, or `/model`) cannot weaken the last-resort tier. Fable 5.1 [1m] is pinned on `architect` alone, at
`xhigh`, for design questions outside a task; nothing else ever runs on it, and
`runtime-gate` sends it to Opus while Fable is rate-limited or its weekly limit is
nearly used. `--fable no` leaves `architect` on the Opus session as well.

Team accounts map by seat: a Standard seat installs as `team-pro` and gets the
Pro profile, a Premium seat installs as `team-max` and gets the Max profile with
Fable on `architect`. The installer reads the seat from `~/.claude.json` and
falls back to `team-pro` when it cannot tell; `--plan team-max` overrides.

On Pro and Team Pro the session model is `opusplan`:
Opus 5 in plan mode, Sonnet 5 when executing. That is the playbook's "plan mode"
play priced for a $20 plan — the expensive model is spent on the plan, and the
cheaper one on typing it out. Because a subagent that omits `model:` would
inherit Sonnet outside plan mode, the installer pins `model: opus` on
`ai-expert` and `architect` for this plan. `log-reader`, `ai-tester` and
`ai-release` run at `low` effort: they read and report, they do not think.

Under Codex the ChatGPT plan chooses the profile. On Pro the session runs Sol
at `high` with six agent threads and `ai-expert` runs Astra at `xhigh`. On Plus
the usage window is a fraction of Pro's, so the session runs Sol at `medium`,
three agent threads, and `ai-expert` runs Astra at `high` — `xhigh` stays off
everywhere. The plan is read from `chatgpt_plan_type` in `~/.codex/auth.json`;
`--codex-plan plus|pro` overrides it, and an install that cannot tell assumes
Pro and says so.

**One difference worth knowing.** Under Claude Code you escalate by spawning
`ai-risk` or `ai-planner` with `model: opus`. Codex resolves an agent's own file
*ahead* of the model asked for at spawn time, so that would silently be ignored —
the Codex roster therefore carries dedicated `ai-risk-strong` and
`ai-planner-strong` agents that pin Sol. Same tier, same trigger, different
mechanism. `ai-expert-strong` is the third: the runtime gate reroutes an
`ai-expert` launch to it while the EXPERT model is unavailable. Every rendered Codex agent writes an explicit `model` and
`model_reasoning_effort` for the same reason: an omitted `model` falls back to the
Terra `[agents]` default, which is not the tier a reviewer needs.

Why route this way: in measured usage, over 80% of the cost was the main session
re-reading its context (cache read and write), not output, so the session model is
the lever that matters. `/usage-report` shows the split on your machine, across
both runtimes.

There is no LOCAL tier: neither runtime has a local-model backend. The work it
would have done is done by deterministic tools and by `ai-indexer` on the cheapest
model, and nothing in the design depends on a local model existing.
