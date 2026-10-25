# Installation

Everything `install.sh` does, per runtime: options, what it writes, what loads on
every turn, and the limits it sets. The short version is in the
[README](../README.md#quick-start).


```bash
./install.sh                       # detects Claude Code, Codex, or both, and updates each
./install.sh --target codex        # auto | claude | codex | both
./install.sh --dry-run             # print what would be written, write nothing

# Claude-side options. The plan is detected from ~/.claude.json (organizationRateLimitTier
# tells Max 5x from 20x) and, on a terminal, proposed for you to confirm with Enter:
./install.sh --plan pro            # Pro: opusplan session, opus pinned for EXPERT
./install.sh --plan team-pro       # Team, Standard seat: the pro profile with the Team label
./install.sh --plan team-max       # Team, Premium seat: the max profile, Fable on architect
./install.sh --plan max            # Max 5x: Opus 5.5 [1m] session (1M window by default), Fable only on architect
./install.sh --plan max20          # Max 20x: max's settings, larger budgets (6 agents, EXPERT without asking)
./install.sh --plan max --fable no # no Fable anywhere; architect inherits the Opus session
./install.sh --plan balanced-max   # BalancedMax: only the session is strong (Opus 5.5, 200k); readers on Haiku,
                                   # judgement on Sonnet, reviews on Opus, EXPERT at high, no Fable, no xhigh;
                                   # also picks the Codex balanced-max profile (Sol session, readers on Luna)

# Codex-side options (the ChatGPT plan is auto-detected from ~/.codex/auth.json):
./install.sh --codex-plan plus     # Plus: Sol at medium, three agent threads, Astra at high, no xhigh
./install.sh --codex-plan pro      # Pro: Sol at high, six agent threads, Astra at xhigh for ai-expert
./install.sh --codex-plan balanced-max  # Pro's budgets, Sol session, FAST readers on Luna, Astra at high
```

`--target auto` installs for each runtime whose CLI is on `PATH`, and asks for
that runtime's plan only. A `~/.claude` or `~/.codex` directory without its CLI
is skipped with a one-line note — `--target both` includes it anyway, which is
also the way in when the CLI exists but is not on this shell's `PATH` (an IDE
extension's bundled binary, `sudo` without `~/.local/bin`). If it
finds neither CLI it stops and tells you which `--target` to name; it never
guesses one.

Restart the runtime afterwards.

- **Claude Code**: `/skills` should list `ai-init`, `ai-audit`, `ai-task` and
  `ai-status`; `/hooks` should list the three guards.
- **Codex**: `/hooks` shows the hooks — **and you must review and trust them
  there before they run.** Codex does not execute a non-managed hook until it has
  been trusted, so until you do, nothing is being enforced.

Re-running the installer updates in place: it backs up what it replaces, never
duplicates a hook entry, and never overwrites your edits to `ai-git-guard.json`.

## What it installs

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

## What loads on every turn

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

## Editing `config.toml` safely

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

## Limits it sets

| Limit | Value | Default |
|---|---|---|
| `bashOutputMaxChars` (Claude) | 75 000 | 30 000 |
| `taskOutputMaxChars` (Claude) | 80 000 | — |
| `MAX_MCP_OUTPUT_TOKENS` (Claude) | 40 000 | 25 000 |
| `cap-large-read.py` (Claude) | refuses an unbounded `Read` over 4 000 lines or 250 KB | no limit |
| `autoCompactWindow` (Claude) | 800 000 on Max and Team Max, 300 000 on Pro and Team Pro. Claude Code caps it at the model's own window, so one setting means compaction near 167k on a 200k model and near 767k on a `[1m]` one; on Pro the cap decides, at 167k | the model window |
| `claude-1m [opus\|fable]` (Claude, Max and Team Max) | pins one session to `opus[1m]`, or to `fable[1m]` (Fable 5.1), at launch. The large window comes from the per-model cap, not from the launcher, so `/model opus[1m]` reaches it too; `CLAUDE_1M_COMPACT_WINDOW` exports `CLAUDE_CODE_AUTO_COMPACT_WINDOW` for that process alone to compact *earlier* than 767k | `/model` only, and the same cap applies |
| `context-guard.py` (both runtimes) | warns from 80% of the point where compaction fires and holds a prompt back once from 120% — 133k and 200k on a 200k Max session, 613k and 920k on a `[1m]` one; `AI_CONTEXT_WARN_TOKENS` / `AI_CONTEXT_BLOCK_TOKENS` set them in tokens, `0` turns one off | no guard |
| `model` (Claude) | `opusplan` on Pro and Team Pro: Opus in plan mode, Sonnet when executing; `claude-opus-5-5[1m]` (Opus 5.5, 1M window) by default on Max, Max 20x and Team Max, `opus` (200k) per task through `/model`; `claude-opus-5-5` (200k) on BalancedMax | Sonnet 5 on Pro |
| `effortLevel` (Claude) | `medium` on both plans; agents raise it per task | — |
| `model` (Codex) | `gpt-5.6-sol` at `high` on Pro, `medium` on Plus; subagents `gpt-5.6-terra` at `medium` | — |
| `max_concurrent_threads_per_session` (Codex) | 6 on Pro, 3 on Plus | runtime default |
| `ai-expert` effort (Codex) | `xhigh` on Pro, `high` on Plus; `xhigh` is never used on Plus | — |

The Read guard is a guardrail, not a cage: an explicit `limit` always goes
through, so reading something large stays possible but has to be deliberate.


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
