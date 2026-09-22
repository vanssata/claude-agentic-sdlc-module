# claude-agentic

[![Version](https://img.shields.io/badge/version-2.0.0-d2f878?labelColor=101210)](https://github.com/vanssata/claude-agentic-sdlc-module/releases/tag/v2.0.0)
[![Runtimes](https://img.shields.io/badge/runtimes-Claude%20Code%20%7C%20Codex-d2f878?labelColor=101210)](#one-module-two-runtimes)
[![Known risks](https://img.shields.io/badge/known%20risks-documented-d2f878?labelColor=101210)](#known-risks)

**Version 2.0.0**, the version `.codex-plugin/plugin.json` carries. Read
[Known risks](#known-risks) before relying on the guards.

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
| session | Opus 5 (200k window) at `medium`, `opus[1m]` per task through `claude-1m` (Sonnet on Pro) | Sol at `high` |

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
exits 7. `--for review` asks the other vendor for a T4+ review; its verdict never
clears the owner's own `blockers_open`, and moving the task again cancels an
open request. `init`, `quick` and `risk` print a
`preferred runtime:` line when the plan's table (refactoring → Codex on Claude
plans) or the quota rule points at the other runtime — advice only.

A subagent that needs a decision **returns** `QUESTIONS_NEEDED` instead of
asking; the manager writes the question into `questions.md`, a human answers it
there or in the session, and `state.py questions --sync` puts the answer back
into the state. The journal is what `/ai-status` and `/usage-report` read, at
zero model cost — no model is involved in writing or reading any of these files.

## Install

```bash
./install.sh                       # detects Claude Code, Codex, or both, and updates each
./install.sh --target codex        # auto | claude | codex | both
./install.sh --dry-run             # print what would be written, write nothing

# Claude-side options. The plan is detected from ~/.claude.json (organizationRateLimitTier
# tells Max 5x from 20x) and, on a terminal, proposed for you to confirm with Enter:
./install.sh --plan pro            # Pro: opusplan session, opus pinned for EXPERT
./install.sh --plan team-pro       # Team, Standard seat: the pro profile with the Team label
./install.sh --plan team-max       # Team, Premium seat: the max profile, Fable on architect
./install.sh --plan max            # Max 5x: Opus 5 session (200k window), Fable only on architect
./install.sh --plan max20          # Max 20x: max's settings, larger budgets (6 agents, EXPERT without asking)
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
| `instructions/stub.md` | a managed block in `~/.claude/CLAUDE.md` | a managed block in `~/.codex/AGENTS.md` |
| `instructions/routing.md` | `~/.claude/claude-agentic/routing.md`, read on demand | `~/.codex/claude-agentic/routing.md`, read on demand |
| `agents/*.md.tmpl` | rendered to `~/.claude/agents/*.md`, each tier's model and effort from the plan (`ai-expert` and `architect` have their own model line) | rendered to `~/.codex/agents/*.toml`, the model pinned per role |
| `profiles/*.json` | the plan's settings, and its tier and budget tables (`claude_agentic`), resolved by `scripts/resolve-profile.py` into `~/.claude/claude-agentic/profile.json` | the same, into `~/.codex/claude-agentic/profile.json` |
| `hooks/*` | `~/.claude/hooks/` — six hooks, `runtime-gate` (the old `fable-gate`/`codex-model-gate` names are shims), the shared library and the guards' default config | `~/.codex/hooks/` + `codex/hooks.json` |
| `skills/*/` | `~/.claude/skills/` | `~/.codex/skills/` |

The skills are `/ai-init`, `/ai-audit`, `/ai-task`, `/ai-status`, `/project-init`,
`/project-update`, `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan` and
`/usage-report`, identical in both runtimes.

The Codex install is a strict subset in one place: `cap-large-read.py` is not
installed there, because Codex's read tool is not on the hook path. The read
rule is still written into `AGENTS.md`; it is just not mechanical there.
`context-guard.py` **is** installed on both — Codex has `UserPromptSubmit`,
`PreCompact` and `SessionStart` too, so the handoff, the pending questions and
`session.json` cross unchanged. What does not cross is the transcript-derived
snapshot: it is built from a Claude transcript and stays Claude-only. One file
serves both; it reads its own location to know which runtime it is in.

`profiles/codex-{plus,pro}.json` is the machine-readable routing contract, one
file per ChatGPT plan — session model and effort, thread cap,
`[agents]` defaults, the four tiers and every role's tier and sandbox mode. Both
the agent renderer and the config merge read it, so there is one place to change
a Codex routing decision.

### What loads on every turn

Context length is the running cost: an always-loaded instruction file is re-read
on every turn of every task, whether it is relevant or not. So the plugin keeps
exactly one always-loaded file per runtime, and it is short.

| Where | What it is | Budget |
|---|---|---|
| `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` | the managed block: the rules an agent is unsafe without | 2 560 B |
| a project's `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.junie/guidelines.md` | the same block, project scope | 2 048 B |
| `~/.claude/claude-agentic/routing.md` | the model ladder, the context-guard thresholds, the guard list — read when a routing question comes up | — |
| a project's `.ai/AGENTS.md` | a router: one row per job, pointing at the policy that answers it | advisory 4 096 B |
| `docs/sdlc/constitution.md` | the 10–15 principles the project does not negotiate, cited as `C<n>` by `/sdlc-spec` and the planner | 15 lines, 4 096 B |
| `.ai/rules/<slug>.md` | a rule scoped to the directories it names, rendered into their instruction files by `/project-update` | — |

All of the block text comes from one source, `instructions/stub.md`, rendered per
scope and runtime by `skills/project-update/render_instructions.py`; the committed
templates are build artefacts and `render_instructions.py build --check` fails the
suite on drift. `install.sh` prints what the block costs after every install
(`managed block 1 903 B (budget 2 560), file 8 457 B — the rest is yours`) and
never touches the rest of the file; `/ai-status` prints the same line for a
project. Downstream the budget is advisory — the plugin measures, it does not
refuse a file it does not own.

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
| `autoCompactWindow` (Claude) | 800 000 on Max and Team Max, 300 000 on Pro and Team Pro. Claude Code caps it at the model's own window, so one setting means compaction near 167k on a 200k model and near 767k on a `[1m]` one; on Pro the cap decides, at 167k | the model window |
| `claude-1m [opus\|fable]` (Claude, Max and Team Max) | pins one session to `opus[1m]`, or to `fable[1m]` (Fable 5.1), at launch. The large window comes from the per-model cap, not from the launcher, so `/model opus[1m]` reaches it too; `CLAUDE_1M_COMPACT_WINDOW` exports `CLAUDE_CODE_AUTO_COMPACT_WINDOW` for that process alone to compact *earlier* than 767k | `/model` only, and the same cap applies |
| `context-guard.py` (both runtimes) | warns from 80% of the point where compaction fires and holds a prompt back once from 120% — 133k and 200k on a 200k Max session, 613k and 920k on a `[1m]` one; `AI_CONTEXT_WARN_TOKENS` / `AI_CONTEXT_BLOCK_TOKENS` set them in tokens, `0` turns one off | no guard |
| `model` (Claude) | `opusplan` on Pro and Team Pro: Opus in plan mode, Sonnet when executing; `opus` (200k window) on Max and Team Max, `opus[1m]` per task, started with `claude-1m` | Sonnet 5 on Pro |
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
| moved by a migration | moved, with your edits merged at the new path; the original kept under `.ai/reports/project-update-<date>/` |
| proposed for deletion by a migration | listed as `delete?` and left alone until a human passes `--apply --confirm-delete NAME` |

The tree also carries a schema version in `.ai/VERSION`; the current one is
**3** (the context diet: the `## SDLC workflow` section the plugin used to write
into the root instruction file is removed, the original kept), and a project
initialised before the version existed is schema 0. Migrations under
`skills/project-update/migrations/` run in order before anything is merged —
they move, add, edit and propose deletions, all inside the same dry run — and
the version is written last, only once they are finished.

Changes to `.ai/policies/*.json` are listed per key and need a confirmation
before they are applied. A risk-tier mirror that was in sync stays in sync; one
that was already stale stays flagged. Nothing is deleted, and no version is
advanced, without the migration that asked for it finishing: a conflict *from a
migration*, or a deletion it proposed and nobody confirmed, holds `.ai/VERSION`
where it is, and `/ai-status` keeps reporting the project as behind. An ordinary
merge conflict does not.

Changed a template? Run `tools/build-template-history.py` and commit the result;
the test suite fails until you do.

A project that already carries another AI tool's structure — Spec Kit
(`.specify/`, `specs/`), Kiro (`.kiro/`), Cursor (`.cursorrules`,
`.cursor/rules/`), Copilot (`.github/copilot-instructions.md`), AI-DLC, or a
`CLAUDE.md`/`AGENTS.md` too large to load on every turn — is adopted with
`/project-update --adopt`. The dry run maps every file through
`skills/project-update/adopt-map.json` and writes nothing; `--apply` moves the
content into `docs/sdlc/` and `.ai/`, keeps each original under
`.ai/reports/adopt-<date>/original/`, and passes two checks on disk: no line
lost, no reference left pointing at an old path. A file no row maps stops the
run until a human decides. `--mode coexist` leaves the files where they are and
only routes to them. The foreign files are deleted by a separate
`--adopt --cleanup`, on a committed tree, and only with `--apply
--confirm-delete NAME` typed by a human. `/ai-status` says when a structure is
waiting, or came back after an adopt.

For work that needs a written intent and specification before any code:

```bash
/sdlc-intent <topic>                     # docs/sdlc/intent/<slug>.md
/sdlc-spec docs/sdlc/intent/<slug>.md    # docs/sdlc/specs/<slug>.md
/sdlc-plan docs/sdlc/specs/<slug>.md     # docs/sdlc/plans/<slug>.md
/ai-task build the plan in docs/sdlc/plans/<slug>.md
```

`/project-init` scaffolds only the SDLC layout, for a repository that does not
want the agentic pipeline. Both scaffolds take
`--runtime auto|claude|codex|gemini|junie|both` — or a comma list — and default
to what the project already declares: `CLAUDE.md`/`.claude/`, `AGENTS.md`/`.codex/`,
`GEMINI.md`/`.gemini/`, `.junie/`. Gemini and Junie get the rendered project stub
only; they are not full runtimes here.

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

Before any of those reviews, the deterministic gates measure the change itself.
`state.py step-done` counts what a step actually changed, between the tree the
step began with and the tree now: over the tier's diff budget or outside the
step's own files it exits 6 and asks for `state.py step-split`, never for the
work to be abandoned. The tier is then re-scored from the real diff — a change
that reached `**/Payment/**` is T4 from then on, and only a human, in their own
terminal, ever lowers a tier. `state.py test-run` owns the test runs, keeps
their output in a file and caps how many there may be. `state.py review-gate`
runs the sensor set — the recorded suite result, the project's own linter and
type checker, the diff, the re-score, step-to-test traceability, repeated
blocks, and whether the named tests **fail without the change** — and at T2,
with every one of them green, records `review_status: skipped_green`: the
sensors are the review. A tool nobody wrote down is `unavailable`, not green,
and keeps the review. From T3 the review always runs, with the sensor rows
already in the ledger so the reviewer does not re-derive them.

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

Each plan is one file in `profiles/`: the runtime's own settings plus a
`claude_agentic` object with the tier table (which model and effort each of FAST,
BALANCED, STRONG and EXPERT is on that plan), the budgets (how many agents may run
at once and how many of them on STRONG, how far direct mode reaches, whether EXPERT
runs without asking, and a token figure per tier) and the preferred runtime per
workflow. `max20.json` is `max.json` with larger budgets. The installer writes the
resolved object to `<home>/claude-agentic/profile.json`; `runtime-gate` enforces the
fan-out and EXPERT budgets by asking, `state.py profile --tier <TIER>` prints a
tier's model, and `/usage-report --task <id>` compares a task's tokens with its
plan's figure — reported, never enforced. The prompts themselves name tiers only;
`tests/test-shared-prompts-model-free.sh` keeps it that way.

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
compacting near 167k tokens (`autoCompactWindow` 800 000, capped at the model's own
window) — `opus[1m]` is for a task that genuinely needs it, and compacts near 767k
because the same setting is no longer capped there, whether it was started with
`claude-1m` or picked with `/model` — and escalates from there: `ai-expert` pins `opus` at `xhigh`, so a session switched to
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

## The guards

| Hook | Runtimes | Where | Does |
|---|---|---|---|
| `ai-git-guard` | both | **every repository** | refuses force push, remote branch delete, history rewrite, push or merge to a protected branch, `gh pr merge`, `--no-verify`, staging a secret, production deploy commands |
| `ai-path-guard` | both | only where `.ai/` exists | refuses reading or writing `.env`, `secrets/`, keys, dumps, production logs; edits to the guards' own config, the task state, the journal, the questions file or the handoff; and `state.py approve` from an agent session — approval is a human's to give |
| `ai-scope-guard` | both | only during an implementation step | refuses editing a file the approved step does not name, with the `SCOPE_CHANGE_REQUIRED` signal |
| `cap-large-read.py` | Claude only | every session | refuses an unbounded `Read` of a large file; an explicit `limit` passes |
| `project-scaffold.sh` | Claude only | `Setup:init` | creates the `docs/sdlc/` and runtime layout on `/init` |
| `context-guard.py` | both | `UserPromptSubmit` / `PreCompact` / `SessionStart:startup\|resume\|clear\|compact` | reads the context size from the transcript: warns once per 10k from 80% of the compaction point, holds a prompt back once from 120% (the same prompt again passes). Before a compaction it writes a snapshot — edited files, latest instructions verbatim, todo list, git state, `.ai/` task state — and tells the summary what to keep; after it, the snapshot goes back into the context. On every session start it writes `.ai/state/session.json` and, with a task in flight, injects `handoff.md` and the pending questions. The snapshot is Claude-only; everything else crosses to Codex. Fails open |
| `runtime-gate.py` | both, every plan | `PreToolUse`/`PostToolUse` on `Agent` (Codex: `spawn_agent`, or `collaborationspawn_agent` under multi-agent v2 — matcher `^Agent$\|spawn_agent$`), `SubagentStart`/`SubagentStop`, `StopFailure` (Fable installs), the statusline | sends the top model's launches one tier down while it is rate-limited or unreachable (Fable → Opus; on Codex `ai-expert` → `ai-expert-strong` by rewriting `agent_type`, since a role's pinned model beats the call's); asks before an EXPERT launch or a launch past the plan's fan-out (explains instead on Codex, which cannot ask); records the quota; journals `model_fallback`, and `missed_reroute` when an EXPERT child starts during an outage anyway. After an upgrade, re-trust the changed Codex entries in `/hooks`. `fable-gate.py` and `codex-model-gate.py` are shims that exec it |

The three shared guards see Codex's `apply_patch` as well. One `apply_patch` can
touch many files, so every `*** Add/Update/Delete File:` and `*** Move to:` path
in the patch is checked separately — a single out-of-scope or protected file
rejects the whole patch. Split the patch rather than widening the step.

Codex has no `StopFailure` event, so on Codex `runtime-gate` attributes a failure at
`SubagentStop` instead, and only when the evidence points at an EXPERT agent:
the agent's name in the text, an explicit expert `model`, an agent file pinned to
the expert model, or an expert launch inside the last five minutes.

They are regex-based and run on every matching tool call. That makes them
defence-in-depth against ordinary agent mistakes — **not a security boundary**. A
determined process can still read a file through an interpreter, and a tool that
is not on the hook path is not gated at all. The real backstops are human review
and server-side branch protection.

## Known risks

What version 2.0.0 knowingly does **not** protect against. Each entry says what
can happen, why it was left that way, what limits the damage, and what you should
do. None is a secret. Each was found in a review or a spec, then accepted or
deferred with a written reason in the file named under **Source**.

### The guards are a tripwire, not a sandbox

**Risk.** Every guard rule is a regex over a command line or a path. A process
that wants to get past it can do so. It can read `.env` through a Python
one-liner, build a command from variables, pipe base64 into a shell, or use a
tool that is not on the hook path at all.
**Why it stays.** A real boundary needs an OS-level sandbox. A hook that runs
before a tool call cannot be one. The guards exist to stop the *honest mistake*,
like reading `.env` to check a value or editing one file too many.
**Limits.** A tripwire catches the common obfuscations (quoted flags,
`--opt=value`, interpreter one-liners that mention `.ai/state/` or
`.ai/reports/`).
**What to do.** Keep production secrets off the developer machine, turn on
server-side branch protection, and review every diff before merge. Those are the
real backstops.
**Source.** `docs/hooks.md`, "What these guards are, and are not".

### Human approval can be forged by a determined process

**Risk.** `state.py approve` refuses to run without a terminal on stdin, and the
path guard refuses it from an agent session. An obfuscated invocation that gets
past the regex and also allocates a pseudo-terminal (a pty) can still grant the
approval.
**Why it stays.** This is the same regex limit as above. The check is there to
make self-approval deliberate and visible, not impossible.
**Limits.** `approve` also refuses when no gate was ever requested
(`gate_requested` in the journal). Every approval is journalled with who, when
and how (`via: terminal`).
**What to do.** Read `state.py events` for the approval before you merge a
T3–T5 change. An approval you do not remember giving is a finding.
**Source.** WP2 security review. `hooks/ai-path-guard.sh`, `docs/hooks.md`.

### `AI_UNATTENDED=1` turns the human gates off

**Risk.** With `AI_UNATTENDED=1` in its environment, any process passes the
human-present check. That covers the approval gate and the deletion gates of
`/project-update --confirm-delete` and `--adopt --cleanup`. Those can then
approve a task or delete files with no human at the keyboard.
**Why it stays.** CI jobs, cron and scripted batches have no human to take a
turn. Without the variable they could not run at all.
**Limits.** It never hides. The approval is recorded permanently as
`unattended: true` in the state and the journal, `adopt.json` records
`cleanup.unattended: true` before the first file is removed, the report prints
`deleted unattended`, and `/ai-status` names every such event.
**What to do.** Export it only in the environment of a launcher, never in an
interactive shell. There it silently disables the gates for every session the
shell starts. Check `/ai-status` after an unattended run.
**Source.** `.ai/reports/T-2026-09-21-001/release.md`, "Residual accepted
risk". `docs/hooks.md`.

### The routing hooks are less protected than the guards

**Risk.** The path guard protects the three guards' own configuration and the
shim `codex-model-gate.py` by name. It does **not** yet protect `runtime-gate.py`
or `context-guard.py`. An agent could edit those two hooks, and so change the
EXPERT reroute, the quota records or the session and compaction snapshot.
**Why it stays.** WP5 froze the guard files, so that the characterization golden
file proves no guard behaviour changed. Protection for both hooks was split off
as its own additive task.
**Limits.** The installed copies live under `~/.claude` or `~/.codex`, outside
any project, and a change to them shows up in `install.sh --dry-run`. On Codex an
edited hook entry loses its trust and stops running until you re-approve it.
**What to do.** Treat an unexpected diff under `hooks/` like a change to CI
configuration. Until the follow-up lands, review hook changes by hand.
**Status.** Open, planned as a follow-up (WP5 OQ3).
**Source.** `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp5-runtimes-and-plans.md`, concern 2 and OQ3.

### The compaction snapshot runs `git` in the working directory

**Risk.** Before a compaction, `context-guard.py` runs `git branch --show-current`
and `git status --short` in the session's directory. A hostile repository can
make those calls run its own code through its local git configuration (for
example `core.fsmonitor`).
**Why it stays.** This predates the plugin's own work. It is the same exposure as
any shell prompt that shows the git branch.
**Limits.** It runs only under Claude Code, only on compaction, and with your
own user rights. It gives no more than opening the repository in a git-aware
shell already does.
**What to do.** Do not run agent sessions inside repositories you do not trust.
**Status.** Open.
**Source.** WP2 security review. `hooks/context-guard.py` (`build_snapshot`).

### Codex runs only hooks you re-approved

**Risk.** Codex keeps each hook approval as a hash of the whole `config.toml`
entry. After an upgrade changes an entry, for example the gate's matcher
`^Agent$|spawn_agent$`, Codex **skips that hook** until you approve it again in
`/hooks`. Until then the scope, path and git guards, or the runtime gate, are
simply not running under Codex, and nothing on screen says so.
**Why it stays.** This is how Codex's trust model works. A plugin cannot and
should not approve itself.
**What to do.** After every `./install.sh` that touches Codex, open `/hooks` in
Codex and approve the changed entries. The installer ends with that reminder.
**Source.** `docs/hooks.md`, runtime gate. `README.md`, "What it installs".

### Codex facts are observed, not guaranteed

**Risk.** Codex's multi-agent v2 launches agents as `collaborationspawn_agent`.
A role's pinned model beats a model given at launch, and a Codex hook cannot ask
the user a question. All three were established by live probes and one
documentation page, and Codex changes quickly. A future Codex release can make
the reroute or the fan-out check silently miss.
**Limits.** On Codex these rules degrade to "allow and explain" by design, never
to a block. The `SubagentStart` backstop journals `missed_reroute` when an
EXPERT agent starts during an outage anyway.
**What to do.** After a Codex upgrade, run `state.py events --type
missed_reroute`. Any line there means the reroute stopped matching.
**Source.** WP5 spec, accepted concern 6. PR #26.

### Budgets and quota are advice, not limits

**Risk.** Several numbers can be off, and none of them ever blocks work.
- **Quota signals can be stale.** Codex quota comes only from the rollouts of a
  past or running session. Claude's comes only while a session with the
  statusline runs.
- **The running-agent count can drift.** A `SubagentStop` lost to a crash leaves
  an entry behind for up to 30 minutes, which costs one extra question.
- **The EXPERT launch count per task never shrinks.** Declined launches count
  too.
- **On Pro/Plus, "strictly serial" is the plugin's rule, not Codex's.** Codex
  still allows 3 threads and can run a second agent after the gate has explained
  why it should not.

**What to do.** `runtime-gate.py clear` empties the count after a crash. Read
the quota with its `stale` and `resets_at` fields, not as a hard figure.
**Source.** WP5 spec, accepted concerns 1, 3 and 4. `hooks/runtime-gate.py`.

### `--adopt` edge cases fail safe, not smoothly

Three low-severity cases from the WP6 review were accepted. Each fails closed or
safe rather than losing data.
- An interrupted apply's `planned_writes` excuses those paths from the
  clean-tree check. It never decides what is written or deleted.
- On resume, `original/<file>` is reused, so edits made between the crash and
  the resume are not in the saved original. Git still has the committed version.
- In a monorepo subdirectory an interrupted apply cannot resume until you commit.
  It refuses rather than guesses.

Two things have not been tried by hand yet: `--adopt` on a real Spec Kit or
Cursor project (the tests use fixtures), and a cleanup run in a real terminal.
**What to do.** Run `--adopt` on a clean, committed tree, read the dry run
first, and keep `original/` until you have checked the result.
**Source.** `.ai/reports/T-2026-09-21-001/review.md`, the LOW rows.

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

Twenty-five suites, 2,129 assertions. The guards against JSON fixtures in both runtimes (including
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
| `docs/hook-performance.md` | what the guards cost per tool call, the budget, and how a change is proved behaviour-preserving |
| `docs/risk-tiers.md` | how classification works and how to tune it |
| `docs/workflows.md` | the five workflows and how one is chosen |
| `docs/faq.md` | why something was blocked, and how to change it |
| `docs/sdlc/plans/dual-runtime-agentic-routing.md` | the approved plan this dual-runtime support was built from |
