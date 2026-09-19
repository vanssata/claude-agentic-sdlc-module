# claude-agentic

Host-wide model, effort and context routing for **Claude Code and Codex**, plus
agentic engineering infrastructure for **existing production codebases** — the
kind with legacy code, undocumented business rules, historical workarounds and
behaviour that customers depend on right now.

It gives a machine and a repository four things:

1. **Routing** — model, effort, fallback, compaction and output limits for the
   detected runtime and plan, plus the tier rules that keep fact collection cheap
   and pay only for thinking.
2. **`.ai/`** — a knowledge base and a policy set that says what agents may and
   may not do in this repository. One tree, shared by both runtimes.
3. **A pipeline** — discovery, context, impact, risk classification, plan,
   implementation, test, adversarial review, security review, release report,
   human approval — with the gates each risk tier requires.
4. **Hooks** that enforce the parts that matter, so an agent cannot quietly widen
   its scope, read a production secret, force-push, or deploy — plus a per-runtime
   escalation gate that sends EXPERT agents one tier down while the top model is
   rate-limited or unreachable.

The design goal is asymmetry: **it should be harder for an agent to damage the
project than to make a small, well-defined change safely.**

The defaults are tuned for **one developer who knows the codebase, on a Pro or
Team Pro plan**, following the [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook):
the developer's knowledge is the first source of context, one verification
command is the feedback loop, plan mode is where the expensive model is spent,
and a subagent is spawned only where a second context window buys something.
A fully delegated `team` profile is one JSON key away.

> This plugin absorbs the former `claude-routing`. Installing it migrates that
> plugin's managed `CLAUDE.md` block into its own, so the two never coexist; see
> [Migrating from claude-routing](#migrating-from-claude-routing).

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
| session | Opus 5 (200k window) at `medium`, `opus[1m]` per task (Sonnet on Pro) | Sol at `high` |

A repository can carry both instruction files over one `.ai/` tree. The task
state is `.ai/state/current.json` either way, so a task started in one runtime
resumes in the other.

## Install

```bash
./install.sh                       # detects Claude Code, Codex, or both, and updates each
./install.sh --target codex        # auto | claude | codex | both
./install.sh --dry-run             # print what would be written, write nothing

# Claude-side options (the plan is auto-detected from ~/.claude.json):
./install.sh --plan pro            # Pro: opusplan session, opus pinned for EXPERT
./install.sh --plan team-pro       # Team, Standard seat: the pro profile with the Team label
./install.sh --plan team-max       # Team, Premium seat: the max profile, Fable on architect
./install.sh --plan max            # Max 5x and 20x: Opus 5 session (200k window), Fable only on architect
./install.sh --plan max --fable no # no Fable anywhere; architect inherits the Opus session

# Codex-side options (the ChatGPT plan is auto-detected from ~/.codex/auth.json):
./install.sh --codex-plan plus     # Plus: Sol at medium, three agent threads, Astra at high, no xhigh
./install.sh --codex-plan pro      # Pro: Sol at high, six agent threads, Astra at xhigh for ai-expert
```

`--target auto` installs for each runtime it finds — the CLI on `PATH`, or an
existing install directory. If it finds neither it stops and tells you which
`--target` to name; it never guesses one.

Restart the runtime afterwards.

- **Claude Code**: `/skills` should list `ai-init`, `ai-audit`, `ai-task` and
  `ai-status`; `/hooks` should list the three guards.
- **Codex**: `/hooks` shows the hooks — **and you must review and trust them
  there before they run.** Codex does not execute a non-managed hook until it has
  been trusted, so until you do, nothing is being enforced.

Re-running the installer updates in place: it backs up what it replaces, never
duplicates a hook entry, and never overwrites your edits to `ai-git-guard.json`.

### What it installs

| Source | Claude target | Codex target |
|---|---|---|
| `profiles/{pro,max}.json` + `settings.common.json` | deep-merged into `settings.json` | — |
| `profiles/codex-{plus,pro}.json` | — | six managed keys in `config.toml` |
| `CLAUDE.snippet.md` / `AGENTS.snippet.md` | a managed block in `~/.claude/CLAUDE.md` | a managed block in `~/.codex/AGENTS.md` |
| `agents/*.md` | `~/.claude/agents/` | rendered to `~/.codex/agents/*.toml` |
| `agents/{ai-expert,architect}.md.tmpl` | the EXPERT-tier agents, model line and effort rendered per plan | `ai-expert.toml` pinned to Astra, `architect.toml` to Sol |
| `hooks/*` | `~/.claude/hooks/` — six hooks, `fable-gate` on a Fable install, the shared library and the guards' default config | `~/.codex/hooks/` + `codex/hooks.json` |
| `skills/*/` | `~/.claude/skills/` | `~/.codex/skills/` |

The skills are `/ai-init`, `/ai-audit`, `/ai-task`, `/ai-status`, `/project-init`,
`/project-update`, `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan` and
`/usage-report`, identical in both runtimes.

The Codex install is a strict subset in two places: `cap-large-read.py` is not
installed there, because Codex's read tool is not on the hook path, and neither
is `context-guard.py`, which reads Claude Code's transcript and compaction
events. The read rule is still written into `AGENTS.md`; it is just not
mechanical there.

`profiles/codex-{plus,pro}.json` is the machine-readable routing contract, one
file per ChatGPT plan — session model and effort, thread cap,
`[agents]` defaults, the four tiers and every role's tier and sandbox mode. Both
the agent renderer and the config merge read it, so there is one place to change
a Codex routing decision.

### Editing `config.toml` safely

There is no comment-preserving TOML writer in the standard library, so
`scripts/merge-codex-config.py` edits the six managed keys line by line, then
parses the file before and after and refuses to write unless the *only* keys that
differ are the six it manages. Your comments, `[projects.*]`, `[mcp_servers.*]`,
`[marketplaces.*]` and every other setting survive; a malformed file aborts the
merge and is left untouched. The previous version is kept as `config.toml.bak`.

**One accepted change to your defaults:** the Codex session is set to Sol at
`high`, not Astra. Astra stays available as the EXPERT escalation. This is the
whole point of the routing — the session model is the largest single cost, and
it should not be the most expensive model by default.

### Limits it sets

| Limit | Value | Default |
|---|---|---|
| `bashOutputMaxChars` (Claude) | 75 000 | 30 000 |
| `taskOutputMaxChars` (Claude) | 80 000 | — |
| `MAX_MCP_OUTPUT_TOKENS` (Claude) | 40 000 | 25 000 |
| `cap-large-read.py` (Claude) | refuses an unbounded `Read` over 4 000 lines or 250 KB | no limit |
| `autoCompactWindow` (Claude) | 133 000 on Max and Team Max, 300 000 on Pro and Team Pro. Compaction fires about 33k under the window, so near 100k and 267k | the model window |
| `context-guard.py` (Claude) | warns from 80% of the point where compaction fires and holds a prompt back once from 120% — 80k and 120k on Max; `AI_CONTEXT_WARN_TOKENS` / `AI_CONTEXT_BLOCK_TOKENS` set them in tokens, `0` turns one off | no guard |
| `model` (Claude) | `opusplan` on Pro and Team Pro: Opus in plan mode, Sonnet when executing; `opus` (200k window) on Max and Team Max, `opus[1m]` available per task | Sonnet 5 on Pro |
| `effortLevel` (Claude) | `medium` on both plans; agents raise it per task | — |
| `model` (Codex) | `gpt-5.6-sol` at `high` on Pro, `medium` on Plus; subagents `gpt-5.6-terra` at `medium` | — |
| `max_concurrent_threads_per_session` (Codex) | 6 on Pro, 3 on Plus | runtime default |
| `ai-expert` effort (Codex) | `xhigh` on Pro, `high` on Plus; `xhigh` is never used on Plus | — |

The Read guard is a guardrail, not a cage: an explicit `limit` always goes
through, so reading something large stays possible but has to be deliberate.

## Use

The same commands in both runtimes:

```bash
/ai-init                 # in a project: survey it, build .ai/ and docs/sdlc/
/ai-task <what you want> # run one change through the pipeline
/ai-status               # where does the current task stand, on which models
/ai-audit                # score the repo against the twelve AI-SDLC plays
/usage-report            # what it cost, from local transcripts, at zero model cost
```

### Updating a project after the plugin changes

`install.sh` updates `~/.claude/`; the rules a project carries in `.ai/`,
`docs/sdlc/` and its `CLAUDE.md` block are copies, and stay as they were. Pull
the new ones in with:

```bash
/project-update          # dry run, confirm the policy changes, apply, merge conflicts
```

Running `/ai-init` or `/project-init` again in an initialised project does the
same. `/ai-status` says when a project is behind.

The plugin ships every version of every template it has ever installed
(`skills/project-update/history/`, built from git by
`tools/build-template-history.py`). That is how the update tells files apart:

| The project file is | What happens |
|---|---|
| missing | created |
| a version the plugin once shipped | replaced — nobody edited it |
| edited, markdown | three-way merged against the closest shipped version; every edit kept |
| edited, JSON policy | merged key by key; the project's value wins wherever both changed |
| edited where the plugin changed the same lines | left alone; the plugin's version goes to `.ai/local/plugin-update/` for a merge |
| `.ai/project/**`, `CLAUDE.md` outside the block, `.claude/settings.json` | never touched |

Changes to `.ai/policies/*.json` are listed per key and need a confirmation
before they are applied. A risk-tier mirror that was in sync stays in sync; one
that was already stale stays flagged.

Changed a template? Run `tools/build-template-history.py` and commit the result;
the test suite fails until you do.

For work that needs a written intent and specification before any code:

```bash
/sdlc-intent <topic>                     # docs/sdlc/intent/<slug>.md
/sdlc-spec docs/sdlc/intent/<slug>.md    # docs/sdlc/specs/<slug>.md
/sdlc-plan docs/sdlc/specs/<slug>.md     # docs/sdlc/plans/<slug>.md
/ai-task build the plan in docs/sdlc/plans/<slug>.md
```

`/project-init` scaffolds only the SDLC layout, for a repository that does not
want the agentic pipeline. Both scaffolds take `--runtime auto|claude|codex|both`
and default to what the project already declares.

`/ai-init` reads the codebase and writes `.ai/`. It does not touch application
code — not a rename, not a formatting fix. Problems it finds are documented in
`.ai/project/known-risks.md`, not fixed. By default it runs a **light** survey:
it asks you for what you know, confirms it with `grep`, and sends only two
discovery agents to the places memory is least reliable — legacy and risks,
tests and data. `/ai-init --survey full` fans out six agents for a codebase new
to you. Either way it ends with the test commands written into
`.ai/policies/testing.md` — the scoped one a step runs, the full verification
command, and the e2e suite — which every later task runs before reporting
done.

It also writes `.ai/policies/tooling.md`: which MCP servers this repository
enables for every task and why, which stay off, and how a single task asks for
one. The default is none. A connected server is in the system prompt of every
turn whether a task calls it or not, so the scaffolded `.claude/settings.json`
ships with `enableAllProjectMcpServers: false` and an empty
`enabledMcpjsonServers`. The same file holds the reading rule: a file too large
to open is read by the cheapest model — `Explore` for code, `log-reader` for
logs — which hands back the matching ranges with `file:line`, never the file.

## Risk tiers

Every task is classified before it is planned. The tier decides who plans it, who
reviews it, and whether a human signs it off. It does not depend on the runtime.

| Tier | Covers | Plan review | Adversarial review | Security review | Human approval |
|---|---|---|---|---|---|
| T0 | documentation, comments | no | no | no | no |
| T1 | formatting, an isolated admin screen | no | no | no | no |
| T2 | a normal isolated feature | no | yes | no | no |
| T3 | shared domain behaviour, orders, workflows, async | yes | yes | when auth or personal data | yes |
| T4 | payments, accounting, tax, fiscal, auth, order state, customer data | yes | yes | yes | yes |
| T5 | migrations, infrastructure, production architecture | yes | yes | yes | yes |

The machine-readable source of truth is `.ai/policies/risk-tiers.json`, which
`/ai-init` copies into each project so the tiers can be tuned to that codebase.

### Who does each stage: the pipeline profile

The tier decides *whether* a stage runs; `pipeline_profile` in the same file
decides *who* runs it. The default is `solo`, which has two modes: **direct**
for T0–T2 — no pipeline ceremony, no report files, cheap readers only, one
`sonnet` review at T2 — and **sdlc** for T3–T5, the full pipeline:

| Tier | `solo` delegates to a subagent | `team` delegates |
|---|---|---|
| T0, T1 | nothing — direct mode, no state file: say which files, edit, verify (T1) | discovery, test |
| T2 | the adversarial review, on `sonnet`; the plan is a few lines in the conversation, recorded by one `state.py quick` call | everything except implementation |
| T3 | plan, plan review, adversarial review — on `opus` | everything except implementation |
| T4 | plus security review and the release report | everything except implementation |
| T5 | plus discovery and impact; the plan goes to `ai-expert` | everything except implementation |

In `solo`, discovery, context, impact and risk come from the request plus
`grep -n`; below T3 they are a few lines in the conversation, from T3 they are
recorded stage by stage. Tests run in three scopes: a step runs **only the
tests it names**, the verification command runs **once, after the last step, to
the end** (no fail-fast flag; the failing test first for a bugfix), and the
**e2e suite runs once after that**, at the end of the task — never per step.
Every failure of the two end-of-task runs is then fixed as **one batch** in a
`state.py remediate` step before one more run — at most two rounds, then the
human decides. Review
findings are handled the same way. Below T3 the release report is the commit
message. A subagent is still sent on a stated trigger: an unfamiliar
area, an `UNKNOWN` the plan depends on, a non-obvious T3+ classification, or
verification output too long to read inline. Switch to `team` by editing the
key. No stage is ever skipped; the profile only changes who does it.

## Model tiers

| Tier | Claude Code | Codex | Does |
|---|---|---|---|
| FAST | `haiku`, low | Terra, low | reading and running: file search, inventories, logs, test output (`Explore`, `log-reader`, `ai-tester`, `ai-indexer`) |
| BALANCED | `sonnet` | Terra, medium | discovery, context, planning up to T2, mechanical edits, release, the T2 review (`ai-discovery`, `ai-context`, `ai-implementer`, `ai-release`) |
| STRONG | `opus`, high | Sol, high | adversarial and security review, T3/T4 risk and planning, root cause after a first diagnosis failed, reversible design (`ai-reviewer`, `ai-security`, `architect`) |
| EXPERT | the session model (Opus 5) on Max, `opus` pinned on Pro; Fable 5.1 [1m] on `architect` only | Astra, `xhigh` | T5, irreversible design, what STRONG could not settle |

The main session does the implementation itself. Every agent definition pins its
own `model:` — most of them the BALANCED tier — and `CLAUDE_CODE_SUBAGENT_MODEL` is
deliberately not set: before Claude Code v2.1.251 it overrides the frontmatter and
the per-call model, which put every agent on Sonnet. A STRONG or EXPERT agent runs
only when a named trigger fires; the triggers are listed in `.ai/policies/model-routing.md`.

On a Max plan the session runs Opus 5 with the 200k window at `medium` effort,
compacting near 100k tokens (`autoCompactWindow` 133 000) — `opus[1m]` stays in `availableModels` for a task
that genuinely needs it — and escalates from there: `ai-expert` omits `model:` and inherits it, so the session's fallback
chain applies to it too. Fable 5.1 [1m] is pinned on `architect` alone, at
`xhigh`, for design questions outside a task; nothing else ever runs on it, and
`fable-gate` sends it to Opus while Fable is rate-limited or its weekly limit is
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
mechanism. Every rendered Codex agent writes an explicit `model` and
`model_reasoning_effort` for the same reason: an omitted `model` falls back to the
Terra `[agents]` default, which is not the tier a reviewer needs.

Why route this way: in measured usage, over 80% of the cost was the main session
re-reading its context (cache read and write), not output, so the session model is
the lever that matters. `/usage-report` shows the split on your machine, across
both runtimes.

There is no LOCAL tier: neither runtime has a local-model backend. The work it
would have done is done by deterministic tools and by `ai-indexer` on the cheapest
model, and nothing in the design depends on a local model existing.

## The guards

| Hook | Runtimes | Where | Does |
|---|---|---|---|
| `ai-git-guard` | both | **every repository** | refuses force push, remote branch delete, history rewrite, push or merge to a protected branch, `gh pr merge`, `--no-verify`, staging a secret, production deploy commands |
| `ai-path-guard` | both | only where `.ai/` exists | refuses reading or writing `.env`, `secrets/`, keys, dumps, production logs; and edits to the guards' own config or the task state |
| `ai-scope-guard` | both | only during an implementation step | refuses editing a file the approved step does not name, with the `SCOPE_CHANGE_REQUIRED` signal |
| `cap-large-read.py` | Claude only | every session | refuses an unbounded `Read` of a large file; an explicit `limit` passes |
| `project-scaffold.sh` | Claude only | `Setup:init` | creates the `docs/sdlc/` and runtime layout on `/init` |
| `context-guard.py` | Claude only | `UserPromptSubmit` / `PreCompact` / `SessionStart:compact` | reads the context size from the transcript: warns once per 10k from 80% of the compaction point, holds a prompt back once from 120% (the same prompt again passes). Before a compaction it writes a snapshot — edited files, latest instructions verbatim, todo list, git state, `.ai/` task state — and tells the summary what to keep; after it, the snapshot goes back into the context. Fails open |
| `fable-gate.py` | Claude, Max with Fable only | `StopFailure` / `PreToolUse:Agent` / the statusline | records a Fable rate limit, model-not-found or a nearly used weekly limit, and rewrites `model: fable` (the `architect` agent) to `opus` until the reset |
| `codex-model-gate.py` | Codex only | `PreToolUse`/`PostToolUse:Agent`, `SubagentStop` | the same idea for Astra: records a rate limit or unavailability and rewrites an Astra launch to Sol at `high` until it expires |

The three shared guards see Codex's `apply_patch` as well. One `apply_patch` can
touch many files, so every `*** Add/Update/Delete File:` and `*** Move to:` path
in the patch is checked separately — a single out-of-scope or protected file
rejects the whole patch. Split the patch rather than widening the step.

Codex has no `StopFailure` event, so `codex-model-gate` attributes a failure at
`SubagentStop` instead, and only when the evidence points at an EXPERT agent:
the agent's name in the text, an explicit expert `model`, an agent file pinned to
the expert model, or an expert launch inside the last five minutes.

They are regex-based and run on every matching tool call. That makes them
defence-in-depth against ordinary agent mistakes — **not a security boundary**. A
determined process can still read a file through an interpreter, and a tool that
is not on the hook path is not gated at all. The real backstops are human review
and server-side branch protection.

## Migrating from claude-routing

This plugin absorbed `claude-routing`. Run `./install.sh` once and it:

- writes the routing settings itself, from the same `profiles/` — nothing about
  your model, effort or limits changes;
- **removes the `<!-- claude-routing:start/end -->` block** from
  `~/.claude/CLAUDE.md` and writes one `claude-agentic` block carrying both sets
  of rules;
- also removes an older unmarked `# Model allocation by task and scope` section,
  if one predates the plugins;
- **retires `agents/reviewer.md`** to `reviewer.md.superseded`, because
  `ai-reviewer` replaces it — adversarial, tier-aware, and reading the project's
  own policies. If you edited that file, it is left alone and the conflict is
  reported instead;
- keeps every other hook, agent and settings key you have, including ones no
  plugin owns.

Where the two disagreed, the agentic layer wins:

| Question | Answer |
|---|---|
| Who reviews a change before commit? | `ai-reviewer`, not `reviewer` |
| Where does a change start? | `/ai-task`. The `/sdlc-*` chain is for work needing a written intent and spec first, then hands its plan to `/ai-task` |
| Who designs? | `ai-planner` inside a task, `ai-expert` on escalation. `architect` is for design questions outside a task, or in a repository without `.ai/` |
| Which init? | `/ai-init`, which runs the SDLC scaffold too. `/project-init` is the SDLC layout alone |

The old `claude-routing` directory can be deleted once you have installed this
one; nothing references it any more.

## Tests

```bash
bash tests/run-all.sh
```

Sixteen suites, 663 assertions. The guards against JSON fixtures in both runtimes (including
`apply_patch` payloads that touch several files at once); the state machine and
its `triage` call; scaffold idempotency for one runtime, the other, and both
over a single `.ai/` tree; installer rendering for every plan combination and
every `--target`; the Codex agent renderer, asserting each role's *effective*
model and effort; the `config.toml` merge against a fixture full of third-party
settings, and its refusal on a malformed file; the migration off
`claude-routing`; `/project-update` against a project scaffolded from the oldest
shipped templates and edited by hand, for a Claude and for a Codex project; an
end-to-end run that installs both runtimes into scratch directories, scaffolds a
throwaway repository, drives a T4 task through the guards from Claude and then
from Codex, and proves both see the same state; the usage report for both
runtimes; and both escalation gates through every event.

No suite reads or writes the developer's real `~/.claude` or `~/.codex`.

## Documentation

| File | About |
|---|---|
| `docs/getting-started.md` | the first hour: install, `/ai-init`, a worked T1 and T4 task |
| `docs/architecture.md` | how the pieces fit: `.ai/`, the pipeline, state, hooks, the two adapters |
| `docs/agents.md` | the roster, contracts and when each agent runs |
| `docs/hooks.md` | every rule the guards enforce, their configuration and limits |
| `docs/risk-tiers.md` | how classification works and how to tune it |
| `docs/workflows.md` | the five workflows and how one is chosen |
| `docs/faq.md` | why something was blocked, and how to change it |
| `docs/sdlc/plans/dual-runtime-agentic-routing.md` | the approved plan this dual-runtime support was built from |
