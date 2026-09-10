# claude-agentic

Host-wide model, effort and context routing for Claude Code, plus agentic
engineering infrastructure for **existing production codebases** — the kind with
legacy code, undocumented business rules, historical workarounds and behaviour
that customers depend on right now.

It gives a machine and a repository four things:

1. **Routing** — model, effort, fallback, compaction and output limits for the
   detected plan, plus the tier rules that keep fact collection cheap and pay
   only for thinking.
2. **`.ai/`** — a knowledge base and a policy set that says what agents may and
   may not do in this repository.
3. **A pipeline** — discovery, context, impact, risk classification, plan,
   implementation, test, adversarial review, security review, release report,
   human approval — with the gates each risk tier requires.
4. **Five hooks** that enforce the parts that matter, so an agent cannot read a
   whole 20 000-line file into context, quietly widen its scope, read a
   production secret, force-push, or deploy.

The design goal is asymmetry: **it should be harder for an agent to damage the
project than to make a small, well-defined change safely.**

> This plugin absorbs the former `claude-routing`. Installing it migrates that
> plugin's managed `CLAUDE.md` block into its own, so the two never coexist; see
> [Migrating from claude-routing](#migrating-from-claude-routing).

## Install

```bash
./install.sh                       # auto-detects the plan from ~/.claude.json
./install.sh --plan max            # Max 5x and 20x share this profile
./install.sh --plan max --fable no # Opus at the EXPERT tier instead of Fable
./install.sh --plan pro            # Opus is the top tier on Pro
./install.sh --dry-run             # print what would be written, write nothing
```

Restart Claude Code afterwards. `/skills` should list `ai-init`, `ai-audit`,
`ai-task` and `ai-status`; `/hooks` should list the three guards.

Re-running the installer updates in place: it backs up what it replaces to
`*.bak`, never duplicates a hook entry, and never overwrites your edits to
`~/.claude/hooks/ai-git-guard.json`.

### What it installs

| Source | Target | Purpose |
|---|---|---|
| `profiles/{pro,max}.json` + `settings.common.json` | deep-merged into `~/.claude/settings.json` | model, fallback, effort, compaction, output limits and the hook registrations |
| `CLAUDE.snippet.md` | a managed block in `~/.claude/CLAUDE.md` | the rules, between `<!-- claude-agentic:start/end -->`, with the plan's numbers filled in |
| `agents/ai-*.md` | `~/.claude/agents/` | the ten pipeline agents |
| `agents/ai-expert.md.tmpl` | `~/.claude/agents/ai-expert.md` | the escalation agent, effort rendered per plan |
| `agents/{architect,Explore,log-reader}.md` | `~/.claude/agents/` | design, fast search, log reading |
| `hooks/*` | `~/.claude/hooks/` | five hooks, the shared library and the guards' default config |
| `skills/*/` | `~/.claude/skills/` | `/ai-init`, `/ai-audit`, `/ai-task`, `/ai-status`, `/project-init`, `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan` |

### Limits it sets

| Limit | Value | Claude Code default |
|---|---|---|
| `bashOutputMaxChars` | 75 000 | 30 000 |
| `taskOutputMaxChars` | 80 000 | — |
| `MAX_MCP_OUTPUT_TOKENS` | 40 000 | 25 000 |
| `cap-large-read.py` | refuses an unbounded `Read` over 4 000 lines or 250 KB | no limit |
| `autoCompactWindow` | 600 000 on Max, 180 000 on Pro | the model window |

The Read guard is a guardrail, not a cage: an explicit `limit` always goes
through, so reading something large stays possible but has to be deliberate.

## Use

```bash
/ai-init                 # in a project: survey it, build .ai/ and docs/sdlc/
/ai-task <what you want> # run one change through the pipeline
/ai-status               # where does the current task stand
/ai-audit                # score the repo against the twelve AI-SDLC plays
```

For work that needs a written intent and specification before any code:

```bash
/sdlc-intent <topic>                     # docs/sdlc/intent/<slug>.md
/sdlc-spec docs/sdlc/intent/<slug>.md    # docs/sdlc/specs/<slug>.md
/sdlc-plan docs/sdlc/specs/<slug>.md     # docs/sdlc/plans/<slug>.md
/ai-task build the plan in docs/sdlc/plans/<slug>.md
```

`/project-init` scaffolds only the SDLC layout, for a repository that does not
want the agentic pipeline.

`/ai-init` reads the codebase and writes `.ai/`. It does not touch application
code — not a rename, not a formatting fix. Problems it finds are documented in
`.ai/project/known-risks.md`, not fixed.

## Risk tiers

Every task is classified before it is planned. The tier decides who plans it, who
reviews it, and whether a human signs it off.

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

## Model tiers

| Tier | Runs on | Does |
|---|---|---|
| FAST | `haiku`, low | inventories, listings, counting (`ai-indexer`) |
| BALANCED | `sonnet`, medium | discovery, context, planning, tests, release (`Explore`, `log-reader`, most `ai-*`) |
| STRONG | `opus`, high | risk at T3+, high-tier planning, adversarial review, security |
| EXPERT | the session model | design (`architect`) and what STRONG could not settle (`ai-expert`) |

On a Max plan with Fable enabled, EXPERT is Fable 5.1 [1m] at `xhigh` effort; with
`--fable no` it is Opus 5 [1m]; on Pro it is Opus 5. `ai-expert.md` omits `model:`
on purpose, so the session's own fallback chain applies to it too.

There is no LOCAL tier: Claude Code has no local-model backend. The work it would
have done is done by deterministic tools and by `ai-indexer` on the cheapest
model, and nothing in the design depends on a local model existing.

## The guards

| Hook | Where | Does |
|---|---|---|
| `cap-large-read.py` | every session | refuses an unbounded `Read` of a large file; an explicit `limit` passes |
| `project-scaffold.sh` | `Setup:init` | creates the `docs/sdlc/` and `.claude/` layout on `/init` |
| `ai-git-guard` | **every repository** | refuses force push, remote branch delete, history rewrite, push or merge to a protected branch, `gh pr merge`, `--no-verify`, staging a secret, production deploy commands |
| `ai-path-guard` | only where `.ai/` exists | refuses reading or writing `.env`, `secrets/`, keys, dumps, production logs; and edits to the guards' own config or the task state |
| `ai-scope-guard` | only during an implementation step | refuses editing a file the approved step does not name, with the `SCOPE_CHANGE_REQUIRED` signal |

They are regex-based and run on every matching tool call. That makes them
defence-in-depth against ordinary agent mistakes — **not a security boundary**. A
determined process can still read a file through an interpreter. The real
backstops are human review and server-side branch protection.

## Migrating from claude-routing

This plugin absorbed `claude-routing`. Run `./install.sh` once and it:

- writes the routing settings itself, from the same `profiles/` — nothing about
  your model, effort or limits changes;
- **removes the `<!-- claude-routing:start/end -->` block** from
  `~/.claude/CLAUDE.md` and writes one `claude-agentic` block carrying both sets
  of rules (56 lines, against the 99 the two blocks used);
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

Eight suites, 224 assertions: the three guards against JSON fixtures, the state
machine, scaffold idempotency, installer rendering for all three plan
combinations, the migration off `claude-routing`, and an end-to-end run that
installs into a scratch directory, scaffolds a throwaway repository and drives a
T4 task through the guards.

## Documentation

| File | About |
|---|---|
| `docs/getting-started.md` | the first hour: install, `/ai-init`, a worked T1 and T4 task |
| `docs/architecture.md` | how the pieces fit: `.ai/`, the pipeline, state, hooks |
| `docs/agents.md` | the roster, contracts and when each agent runs |
| `docs/hooks.md` | every rule the guards enforce, their configuration and limits |
| `docs/risk-tiers.md` | how classification works and how to tune it |
| `docs/workflows.md` | the five workflows and how one is chosen |
| `docs/faq.md` | why something was blocked, and how to change it |
