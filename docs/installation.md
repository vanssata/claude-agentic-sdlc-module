# Installation

One command installs RiskRails into Claude Code, Codex, or both. Pin the
version: `npx riskrails` alone runs whatever was published last, and the hooks
it installs see every command an agent runs.

```bash
npx riskrails@3.0.1                       # detects Claude Code, Codex, or both, and updates each
npx riskrails@3.0.1 --target codex        # auto | claude | codex | both
npx riskrails@3.0.1 --dry-run             # print what would be written, write nothing
npx riskrails@3.0.1 --home ~/alt-claude   # another Claude home (--codex-home for Codex)
# The installer does not read CLAUDE_CONFIG_DIR or CODEX_HOME: with a home other than
# ~/.claude or ~/.codex, pass it with --home / --codex-home (or CLAUDE_DIR / CODEX_DIR).

# Claude-side options. The plan is detected from ~/.claude.json (organizationRateLimitTier
# tells Max 5x from 20x; a Team account by its seat) and, on a terminal, proposed for you
# to confirm with Enter; --yes takes the detection, or the plan recorded last time, without asking:
npx riskrails@3.0.1 --plan pro            # Pro: opusplan session, opus pinned for STRONG and EXPERT
npx riskrails@3.0.1 --plan team-pro       # Team, Standard seat: the pro profile with the Team label
npx riskrails@3.0.1 --plan team-max       # Team, Premium seat: the max profile, Fable on architect
npx riskrails@3.0.1 --plan max            # Max 5x: Opus 5.5 [1m] session, Fable only on architect
npx riskrails@3.0.1 --plan max20          # Max 20x: max's settings, EXPERT twice per task without asking
npx riskrails@3.0.1 --plan max --fable no # no Fable anywhere; architect inherits the Opus session
npx riskrails@3.0.1 --plan balanced-max   # BalancedMax: only the session is strong (Opus 5.5, 200k); readers on Haiku,
                                          # judgement on Sonnet, reviews on Opus, EXPERT at high, no Fable, no xhigh;
                                          # also picks the Codex balanced-max profile (Sol session, readers on Luna)

# Codex-side options (the ChatGPT plan is read from ~/.codex/auth.json; unknown means pro, and says so):
npx riskrails@3.0.1 --codex-plan plus     # Plus: Sol at medium, three agent threads, Astra at high, no xhigh
npx riskrails@3.0.1 --codex-plan pro      # Pro: Sol at high, six agent threads, Astra at xhigh
npx riskrails@3.0.1 --codex-plan balanced-max  # Pro's budgets, Sol session, FAST readers on Luna, Astra at high

# Context (both runtimes):
npx riskrails@3.0.1 --context economy     # the plan's compaction window (800 000 Max, 300 000 Pro); the guard also blocks
npx riskrails@3.0.1 --context default     # the default: each runtime's own window and compaction; the guard only warns
npx riskrails@3.0.1 --statusline-context no  # no model and context line in the statusline (default yes)
```

Node 18 or newer and `python3` on `PATH` are required; the installer stops
with one line when either is missing. From a checkout, `node bin/riskrails.js`
takes the same flags. `./install.sh` only prints the `npx` line and exits 2.

**Which runtimes.** `--target auto` installs for each runtime whose CLI is on
`PATH`, and asks for that runtime's plan only. A `~/.claude` or `~/.codex`
directory without its CLI is skipped with a one-line note; `--target both`
includes it anyway, which is also the way in when the CLI exists but is not on
this shell's `PATH` (an IDE extension's bundled binary, `sudo` without
`~/.local/bin`). Naming `--home` alone installs Claude only, `--codex-home`
alone Codex only. If it finds neither CLI it stops and tells you which
`--target` to name; it never guesses one.

**Updating.** The same command updates in place: it backs up what it replaces
under `<home>/backups/<date>/`, never duplicates a hook entry, and never
overwrites your edits to `ai-git-guard.json`. The short form, for a machine
that already has a plan recorded:

```bash
npx -y riskrails@latest --yes              # in a terminal
! npx -y riskrails@latest --yes            # inside Claude Code or the Codex CLI
```

`--yes` keeps the recorded plan without a prompt; `-y` skips npx's own install
prompt. Then `/rr-setup --update` in each project ([project-update.md](project-update.md)).

Restart the runtime afterwards.

- **Claude Code**: `/skills` lists `rr-setup`, `rr-spec`, `rr-plan`,
  `rr-build`, `rr-build-all`, `rr-review`, `rr-ship` and `rr-status`, plus the
  deprecated aliases; `/hooks` lists `ai-guard.py`, the one guard command.
- **Codex**: `/hooks` shows the hooks — **and you must review and trust them
  there before they run.** Codex does not execute a non-managed hook until it
  has been trusted, so until you do, nothing is being enforced.

## The plugin route

`/plugin install riskrails` (Claude Code) or the Codex plugin directory
installs the skills and the hooks from `hooks/hooks.json`. Run `npx riskrails`
as well: the plugin format cannot carry the agents, the plan profile, the
managed block or the settings. When the runtime records the plugin as installed
and enabled (Claude Code: `installed_plugins.json` at user scope and
`enabledPlugins`; Codex: `[plugins."riskrails@<marketplace>"] enabled = true`
in `config.toml`), `npx` registers none of the plugin's hooks and installs the
skills without their `SKILL.md`, so nothing loads or runs twice and the skills
still find their scripts under `~/.claude/skills/`. A plugin cache folder by
itself changes nothing: `npx` installs everything. With the plugin alone there
is no `ai-reviewer` agent, so a task whose mode needs a review has nothing to
run it with.

## What it installs

| Source | Claude target | Codex target |
|---|---|---|
| `profiles/*.json` + `settings.common.json` | the plan's settings deep-merged into `settings.json` (model, effort, fallback, limits, hooks) | six managed keys in `config.toml` |
| `profiles/*.json`, resolved by `scripts/resolve-profile.py` | `~/.claude/riskrails/profile.json`: the tier table, the budgets, the dialog tool | `~/.codex/riskrails/profile.json` |
| `instructions/stub.md` | a managed block in `~/.claude/CLAUDE.md` | a managed block in `~/.codex/AGENTS.md` |
| `instructions/routing.md` | `~/.claude/riskrails/routing.md`, read on demand | `~/.codex/riskrails/routing.md` |
| `agents/*.md.tmpl` | `~/.claude/agents/*.md`, each tier's model and effort baked in from the plan | `~/.codex/agents/*.toml`, rendered by `scripts/render-codex-agents.py`, model and effort pinned per role |
| `hooks/*` | `~/.claude/hooks/`: `ai-guard.py` and `guard/`, `cap-large-read.py`, `context-guard.py`, `runtime-gate.py`, `dialog-gate.py`, `project-scaffold.sh`, `memory-pre-push.py`, the two defaults files, `ai-git-guard.json` seeded once | `~/.codex/hooks/` (no `cap-large-read.py`, no scaffold hook) + `hooks.json` |
| `skills/*/` | `~/.claude/skills/` | `~/.codex/skills/` |
| `ai/` | `~/.claude/riskrails/ai/`, the shared tree, and `riskrails/ai-path`, the resolver | `~/.codex/riskrails/ai/`, `riskrails/ai-path` |
| `bin/claude-1m` | `~/.claude/bin/claude-1m` on Max, linked from `~/.local/bin` when that exists | — |

The Codex install is a strict subset in one place: `cap-large-read.py` is not
installed there, because Codex's read tool is not on the hook path; the read
rule is prose in `AGENTS.md`. `context-guard.py`, `runtime-gate.py`,
`dialog-gate.py` and the guard are installed on both — Codex has
`UserPromptSubmit`, `PreCompact`, `SessionStart`, the agent events and `Stop`
too, so the handoff, the pending questions and the picks cross unchanged. One
file serves both; it reads its own location to know which runtime it is in.

`profiles/codex-{plus,pro,balanced-max}.json` is the machine-readable routing
contract, one file per ChatGPT plan — session model and effort, thread cap,
`[agents]` defaults, the four tiers and every role's tier and sandbox mode.
Both the agent renderer and the config merge read it, so there is one place to
change a Codex routing decision. [routing.md](routing.md) has the tables.

## What loads on every turn

Context length is the running cost: an always-loaded instruction file is
re-read on every turn of every task. So the plugin keeps exactly one
always-loaded file per runtime, and it is short.

| Where | What it is | Budget |
|---|---|---|
| `~/.claude/CLAUDE.md`, `~/.codex/AGENTS.md` | the managed block: the rules an agent is unsafe without | 2 560 B |
| a project's `CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `.junie/guidelines.md` | the same block, project scope | 2 048 B |
| `~/.claude/riskrails/routing.md` | the model ladder, the context-guard thresholds, the guard list — read when a routing question comes up | — |
| a project's `.ai/AGENTS.md` | a router: one row per job, pointing at the policy that answers it | advisory 4 096 B |
| `docs/sdlc/constitution.md` | the principles the project does not negotiate, cited as `C<n>` | 15 lines, 4 096 B |
| `.ai/rules/<slug>.md` | a rule scoped to the directories it names, rendered into their instruction files by `/rr-setup --update` | — |

All of the block text comes from one source, `instructions/stub.md`, rendered
per scope and runtime by `skills/project-update/render_instructions.py`; the
committed templates are build artefacts and `render_instructions.py build
--check` fails the suite on drift. The installer prints what the block costs
after every install (`managed block 1 903 B (budget 2 560), file 8 457 B — the
rest is yours`) and never touches the rest of the file; `/rr-status` prints the
same line for a project. The budget is advisory downstream — the plugin
measures, it does not refuse a file it does not own.

## Editing `config.toml` safely

There is no comment-preserving TOML writer in the standard library, so
`scripts/merge-codex-config.py` edits the managed keys line by line, then
parses the file before and after and refuses to write unless the *only* keys
that differ are the ones it manages. Your comments, `[projects.*]`,
`[mcp_servers.*]`, `[marketplaces.*]` and every other setting survive; a
malformed file aborts the merge and is left untouched. The previous version is
kept under `backups/<date>/`.

**One accepted change to your defaults:** the Codex session is set to Sol
(`high` on Pro, `medium` on Plus), not Astra. Astra stays available as the
EXPERT escalation. The session model is the largest single cost, and it should
not be the most expensive model by default.

## Limits it sets

| Limit | Value | Default |
|---|---|---|
| `bashOutputMaxChars` (Claude) | 75 000 | 30 000 |
| `taskOutputMaxChars` (Claude) | 80 000 | — |
| `MAX_MCP_OUTPUT_TOKENS` (Claude) | 40 000 | 25 000 |
| `cap-large-read.py` (Claude) | refuses an unbounded `Read` over 4 000 lines or 250 KB; a `limit` up to 4 000 passes | no limit |
| `enableAllProjectMcpServers` (Claude) | `false` — a project enables the servers it needs | all |
| `autoCompactWindow` (Claude) | not set by default: each runtime keeps its own compaction, near 167k on a 200k model and near 967k on a `[1m]` one. With `--context economy`: 800 000 on Max and Team Max, 300 000 on Pro and Team Pro, capped by Claude Code at the model's own window. A re-install without economy removes the value it wrote, only when it still equals the plan's | the model window |
| `claude-1m [opus\|fable]` (Claude, Max and Team Max) | pins one session to `opus[1m]` or `fable[1m]` at launch. `CLAUDE_1M_COMPACT_WINDOW` exports `CLAUDE_CODE_AUTO_COMPACT_WINDOW` for that process alone, to compact earlier | `/model` only |
| `context-guard.py` (both) | warns from 80% of the compaction point — 133k on a 200k session, 773k on a `[1m]` one — and never holds a prompt back. With `--context economy`, or a window you set yourself, it also holds a prompt back once from 120% | no guard |
| statusline (both) | the model and the context use: in Claude Code one line before your own (`Opus 5.5 [1m] · 123k/1000k (12%)`); in Codex `model-with-reasoning` and `context-used` appended to a `[tui] status_line` you set. `--statusline-context no` adds nothing | the runtime's own |
| `model` (Claude) | `opusplan` on Pro and Team Pro; `claude-opus-5-5[1m]` on Max, Max 20x and Team Max; `claude-opus-5-5` (200k) on BalancedMax | Sonnet on Pro |
| `effortLevel` (Claude) | `medium`; agents raise it per task | — |
| `model` (Codex) | `gpt-5.6-sol` at `high` on Pro, `medium` on Plus; FAST agents `gpt-5.6-terra` (Luna on BalancedMax) | — |
| `max_concurrent_threads_per_session` (Codex) | 6 on Pro and BalancedMax, 3 on Plus | runtime default |
| `expert.max_per_task` | 1 on Pro, Max and BalancedMax, asked every time; 2 on Max 20x and Codex Pro, without asking | — |

The Read guard is a guardrail, not a cage: an explicit `limit` within the
budget goes through, so reading something large stays possible but has to be
deliberate.

## Upgrading from 2.x (`claude-agentic`)

`npx riskrails` does the home-side move itself:

- `<home>/claude-agentic/` is renamed to `<home>/riskrails/` and a symlink is
  left at the old path for one version; if `riskrails/` already exists, the old
  directory goes to `backups/<date>/`.
- the hook entries that named `ai-git-guard.sh`, `ai-path-guard.sh`,
  `ai-scope-guard.sh`, `fable-gate.py` or `codex-model-gate.py` are replaced
  by `ai-guard.py` and `runtime-gate.py`; the old files are retired to
  `backups/<date>/`; the statusline wrapper is rewritten; stale `*.bak` files
  are swept into the same backup folder;
- the agents of the old roster (`ai-context`, `ai-expert`, `ai-implementer`,
  `ai-indexer`, `ai-planner`, `ai-release`, `ai-risk`, `ai-security`,
  `ai-tester` and the Codex `*-strong` twins) are retired; `reviewer.md` from
  `claude-routing` is renamed `.superseded` when it is the shipped one;
- the `<!-- claude-agentic:start/end -->` block in `~/.claude/CLAUDE.md` and
  `~/.codex/AGENTS.md` becomes a `riskrails` block; an older `claude-routing`
  block, or an unmarked `# Model allocation by task and scope` section, is
  removed on the way.

Every other hook, agent and settings key you have is kept, including ones no
plugin owns. The project side is a migration: [README.md](../README.md),
"Upgrade to 3.0".
