# claude-agentic

**Risk-tiered agentic SDLC for Claude Code and Codex. Let an AI agent work on
legacy production code without the agent widening its own scope, reading a
production secret, force-pushing or deploying.**

[![Version](https://img.shields.io/badge/version-2.0.2-E39B6B?labelColor=221A15)](https://github.com/vanssata/claude-agentic-sdlc-module/releases/tag/v2.0.2)
[![Runtimes](https://img.shields.io/badge/runtimes-Claude%20Code%20%7C%20Codex-E39B6B?labelColor=221A15)](#quick-start)
[![Tests](https://img.shields.io/badge/tests-27%20suites-E39B6B?labelColor=221A15)](#tests)
[![Known risks](https://img.shields.io/badge/known%20risks-documented-E39B6B?labelColor=221A15)](#known-risks)
[![License: MIT](https://img.shields.io/badge/license-MIT-E39B6B?labelColor=221A15)](LICENSE)

`claude-agentic` is a plugin for codebases with undocumented business rules,
old workarounds and behaviour customers rely on today. Every change gets a risk
tier from what it reaches, and the tier decides the ceremony: a typo fix stays a
one-line edit, a payment change gets a plan, tests, an adversarial review, a
security review and your sign-off. Risky actions are stopped by a hook, not by a
polite request in a prompt.

[Site](https://vanssata.github.io/claude-agentic-sdlc-module/) ·
[Demo](https://vanssata.github.io/claude-agentic-sdlc-module/demo.html) ·
[Wiki](https://github.com/vanssata/claude-agentic-sdlc-module/wiki) ·
[Docs](docs/)

```
  SET UP          DEFINE           TASK                                         OBSERVE
 ┌────────┐     ┌─────────┐     ┌──────────────────────────────────────────┐   ┌─────────┐
 │ survey │ ──▶ │ intent  │ ──▶ │ triage ▶ tier ▶ plan ▶ build ▶ verify ▶  │ ─▶│ status  │
 │ the    │     │ spec    │     │ review ▶ YOUR APPROVAL                   │   │ cost    │
 │ repo   │     │ plan    │     │   (no agent commits, pushes or deploys)  │   │         │
 └────────┘     └─────────┘     └──────────────────────────────────────────┘   └─────────┘
  /ai-init      /sdlc-intent     /ai-task <what you want>                       /ai-status
  /ai-audit     /sdlc-spec        T0–T4 direct mode · T5–T6 full pipeline       /usage-report
                /sdlc-plan
```

## Commands

Ten commands, the same in both runtimes.

| What you're doing | Command | Key principle |
|---|---|---|
| Start on a codebase | `/ai-init` | Survey, document, never touch application code |
| Score an existing AI setup | `/ai-audit` | Gaps with citations, before adding process |
| Make one change | `/ai-task <request>` | The tier decides the gates, not your impression |
| See where a task stands | `/ai-status` | State is a file, read at zero model cost |
| Agree the problem first | `/sdlc-intent <topic>` | One question at a time, before any code |
| Write the design | `/sdlc-spec <intent>` | The project's conventions are policy |
| Order the work | `/sdlc-plan <spec>` | Files, order, proof and rollback per step |
| Pull in plugin changes | `/project-update` | Untouched files replaced, edits always kept |
| Scaffold the SDLC layout only | `/project-init` | `docs/sdlc/` without the pipeline |
| See what it cost | `/usage-report` | Tokens and cost from local transcripts |

A change starts at `/ai-task`. The `/sdlc-*` chain is for work that needs a
written intent and spec first; its plan is then handed to `/ai-task`.

## Quick Start

```bash
git clone https://github.com/vanssata/claude-agentic-sdlc-module.git
cd claude-agentic-sdlc-module && ./install.sh   # detects Claude Code, Codex or both
```

Then, in any project: `/ai-init` once, and `/ai-task <what you want>` for every
change.

**Claude Code.** The plan is read from `~/.claude.json` and proposed for you to
confirm. Override it with `--plan pro | team-pro | team-max | max | max20 |
balanced-max`, and `--fable no` to keep Fable off `architect`. Restart, then
`/skills` should list `ai-init`, `ai-audit`, `ai-task` and `ai-status`, and
`/hooks` the three guards.

**Codex.** The ChatGPT plan is read from `~/.codex/auth.json`; override it with
`--codex-plan plus | pro | balanced-max`. Restart, open `/hooks` and **trust the
hooks there**: Codex runs no hook you have not approved, so until you do, nothing
is enforced.

**Both.** `./install.sh --target both` installs into each home even when a CLI is
not on this shell's `PATH`; `--dry-run` prints what would be written. Re-running
updates in place, backs up what it replaces and never duplicates a hook entry.

Full options, what is written where, what loads on every turn and the limits it
sets: [docs/installation.md](docs/installation.md).

> This plugin absorbs the former `claude-routing`. Installing it migrates that
> plugin's managed `CLAUDE.md` block into its own; see
> [Migrating from claude-routing](docs/installation.md#migrating-from-claude-routing).

## How a task runs

The tier comes from the **scope** of the change — a process, a migration,
money, identity, infrastructure — never from how many files or lines it
touches. When two tiers are arguable, the higher wins.

| Tier | Covers | How it runs (`solo` profile) | Review | Human approval |
|---|---|---|---|---|
| T0 | documentation, comments | direct: name the files, edit | — | — |
| T1 | formatting, a label, a template tweak | direct, then the verification command | — | — |
| T2 | an isolated screen or form, a new field | direct, one `state.py quick` record | the sensors; a BALANCED model only when one is red | — |
| T3 | CRUD and presentation: a new resource with its screens | direct, one `state.py quick` record | the sensors; a BALANCED model only when one is red | — |
| T4 | shared processes: orders, workflows, async, integrations, config | direct; the plan is written in plan mode and **you approve it** before any edit | always, STRONG | yes |
| T5 | payments, accounting, tax, auth, order state, customer data | full pipeline: STRONG risk and plan, plan review, security review, release report | STRONG + security | yes |
| T6 | infrastructure, migration strategy, destructive data migrations | full pipeline; discovery delegated, the plan goes to EXPERT | STRONG + security | yes |

Every tier ends the same way: the verification command **once, to the end**,
the e2e suite once after it, and every failure fixed as **one batch** in a
`state.py remediate` step — at most two rounds, then the human decides.

Before any model reviews, `state.py review-gate` measures the change: the
recorded suite result, your linter and type checker, the diff against the
tier's budget, the tier **re-scored from the real diff**, step-to-test
traceability, repeated blocks, and whether the named tests **fail without the
change**. Up to T3, all green is the review (`skipped_green`). A tool nobody
wrote down is `unavailable`, not green. A re-score only ever raises: a diff that
reached `**/Payment/**` is T5 from then on, and only a human lowers a tier.

A review returns `pass`, `pass_with_findings` (an in-scope HIGH, no BLOCKER) or
`blockers_open`. A task gets two review passes — one full, one scoped — and the
next verdict is yours.

Tuning, the `team` profile and the classification rules:
[docs/risk-tiers.md](docs/risk-tiers.md). The five workflows — feature, bugfix,
refactoring, hotfix, investigation — are in [docs/workflows.md](docs/workflows.md).

## All 10 Commands

### Set up — make the repository legible to an agent

| Command | What it does | Use when |
|---|---|---|
| [`/ai-init`](skills/ai-init/SKILL.md) | Surveys the codebase and writes `.ai/` — knowledge base, policies, risk tiers, test commands — and an initial assessment. Light survey by default; `--survey full` fans out six readers | Before the first `/ai-task` in a repository |
| [`/ai-audit`](skills/ai-audit/SKILL.md) | Scores the repository 0–3 against the twelve plays of the AI-native SDLC playbook and writes `docs/ai-sdlc-adoption-plan.md` | You already have an AI setup and want to know what is missing |
| [`/project-init`](skills/project-init/SKILL.md) | Scaffolds `docs/sdlc/` and the runtime directory, for Claude Code, Codex, Gemini or Junie | You want the SDLC layout without the agentic pipeline |
| [`/project-update`](skills/project-update/SKILL.md) | Brings `.ai/`, the managed block and templates up to date; three-way merges edited files; `--adopt` moves Spec Kit, Kiro, Cursor or Copilot setups in | After reinstalling the plugin, or when `/ai-status` says the project is behind |

### Define — agree what to build before any code

| Command | What it does | Use when |
|---|---|---|
| [`/sdlc-intent`](skills/sdlc-intent/SKILL.md) | A one-question-at-a-time brainstorm into `docs/sdlc/intent/<slug>.md`: problem, outcome, affected users, constraints, open questions | Starting a feature whose problem is not yet agreed |
| [`/sdlc-spec`](skills/sdlc-spec/SKILL.md) | Turns an intent into a requirements and design spec that applies the project's conventions and ends with flagged concerns | The intent is agreed and the design is not |
| [`/sdlc-plan`](skills/sdlc-plan/SKILL.md) | Turns intent + spec into an ordered plan: files, order of work, risks, proof, rollback | The spec is agreed; hand the plan to `/ai-task` |

### Build — one change, with the gates its tier requires

| Command | What it does | Use when |
|---|---|---|
| [`/ai-task`](skills/ai-task/SKILL.md) | Classifies the change, runs it in direct mode (T0–T4) or through the full pipeline (T5–T6), verifies once, reviews, and stops at your approval. `--resume`, `--abandon` | Every change in a repository that has `.ai/` |

### Observe — where it stands and what it cost

| Command | What it does | Use when |
|---|---|---|
| [`/ai-status`](skills/ai-status/SKILL.md) | The task's stage, step, allowed files, test and review status, open risks; what each tier resolves to on this plan; the quota; whether the project is behind | "Where are we", "why did a guard fire here" |
| [`/usage-report`](skills/usage-report/SKILL.md) | Tokens and cost per session, day, project, model and task, for both runtimes, at zero model cost | "What did this cost", "which model spent the most" |

## Agents

The session implements. Every other role is an agent with its own context
window, a pinned tier and an output contract; a STRONG or EXPERT agent runs only
on a named trigger, one at a time. Contracts: [docs/agents.md](docs/agents.md).

| Agent | Tier | Role | Runs |
|---|---|---|---|
| `Explore` | FAST | finds files and code, returns `file:line` excerpts | whenever a file is not found in a few `grep` calls |
| `log-reader` | FAST | reads logs and test output, returns the errors and a diagnosis | long output, never into the session |
| `ai-indexer` | FAST | file listings, symbols, git-log summaries | before a discovery fan-out |
| `ai-tester` | FAST | classifies a red run: new regression, existing, environment | only when a run is red |
| `ai-discovery` | BALANCED | traces an area: callers, tests, configuration, hidden coupling | T6, or an unfamiliar area |
| `ai-context` | BALANCED | compresses discovery into one task context | T5–T6 |
| `ai-implementer` | BALANCED | one mechanical, pattern-copying step | when asked |
| `ai-release` | BALANCED | assembles the release report from the task's files | T5–T6 |
| `ai-reviewer` | BALANCED / STRONG | adversarial review that assumes the change is wrong | T2–T3 on a red sensor; always from T4 |
| `ai-risk` | STRONG | assigns exactly one tier and names the trigger | T5–T6 |
| `ai-planner` | STRONG | steps, files per step, tests, rollback, risks | T5 |
| `ai-security` | STRONG | auth, secrets, personal data, injection, webhooks | T5–T6, or any diff touching auth or personal data |
| `architect` | STRONG / EXPERT | design questions outside a task | on request |
| `ai-expert` | EXPERT | last resort: T6 and what STRONG could not settle | asks before it starts |

## Model tiers

Prompts name tiers, never models. Each plan in `profiles/` resolves them.

| Tier | Claude Code | Codex | Does |
|---|---|---|---|
| FAST | `haiku`, low | Terra, low | reading and running |
| BALANCED | `sonnet` | Terra, medium | discovery, context, mechanical edits, the T2/T3 review |
| STRONG | `opus`, high | Sol, high | review from T4, T5 risk and planning, security |
| EXPERT | `opus` at `xhigh`; Fable 5.1 on `architect` only | Astra, `xhigh` | T6, irreversible design |
| session | Opus 5.5 [1m] on Max, `opusplan` on Pro | Sol at `high` on Pro, `medium` on Plus | implementation |

Over 80% of measured cost was the session re-reading its context, so the session
model is the lever that matters. `runtime-gate` sends the top model's launches
one tier down while it is rate-limited and asks before an EXPERT launch or a
fan-out past the plan's budget. Every plan and both adapters:
[docs/routing.md](docs/routing.md).

## The guards

| Hook | Runtimes | Refuses |
|---|---|---|
| `ai-git-guard` | both, every repository | force push, remote branch delete, history rewrite, push or merge to a protected branch, `gh pr merge`, `--no-verify`, staging a secret, production deploys |
| `ai-path-guard` | both, where `.ai/` exists | reading or writing `.env`, `secrets/`, keys, dumps, production logs; edits to the guards' config, the task state, the journal, the questions file or the handoff; `state.py approve` from an agent session; `cp`/`mv`/`install`/`rm` onto protected paths, including through `sh -c` and `eval` |
| `ai-scope-guard` | both, during a step | editing a file the approved step does not name — `SCOPE_CHANGE_REQUIRED` |
| `cap-large-read.py` | Claude | an unbounded `Read` over 4 000 lines or 250 KB; an explicit `limit` passes |
| `context-guard.py` | both | nothing — it warns near compaction, snapshots what to keep, and injects the handoff on session start |
| `runtime-gate.py` | both | nothing — it reroutes, asks and journals |

The guards are regex over a command line or a path: **a tripwire against the
honest mistake, not a sandbox**. Every rule and its limits: [docs/hooks.md](docs/hooks.md).

## How it works

```
your-project/
├── CLAUDE.md / AGENTS.md     one short managed block, the rules an agent is unsafe without
├── .ai/
│   ├── AGENTS.md             a router: one row per job → the policy that answers it
│   ├── project/              what /ai-init learned, every line labelled
│   │                         KNOWN FACT (file:line) · INFERENCE · UNKNOWN · RISK
│   ├── policies/             risk-tiers.json, path-guard.json, testing.md, safety.md …
│   ├── rules/<slug>.md       rules scoped to the directories they name
│   ├── state/                current.json · handoff.md · session.json   (written by state.py only)
│   └── reports/<task-id>/    events.jsonl · questions.md · sensors.json · tests-*.log · review-report.md
└── docs/sdlc/                constitution.md · intent/ · specs/ · plans/ · adr/
```

Shared policies, agent contracts, workflows and templates are installed once
under `<home>/claude-agentic/ai/` and read from there; a file at the same path
under `.ai/` overrides it. `<home>/claude-agentic/ai-path <path>` prints the
copy that applies.

- **Guards, not guidelines.** What must not happen is refused by a hook. What
  should happen is a policy the agent reads on demand.
- **Tier by scope, not size.** The ceremony scales with what a change reaches,
  and the real diff can only raise the tier.
- **Sensors before reviewers.** Deterministic measurements run first; a model
  reviews only what they could not settle.
- **Files, not chat.** State, journal, questions and handoff are plain files no
  model writes or reads. A task started in Claude Code resumes in Codex:
  `state.py handoff --to codex`.
- **The pipeline ends with you.** No agent commits, pushes, merges or deploys.
  Approval is given in your own terminal.

## Project structure

| Path | Purpose |
|---|---|
| `skills/` | the ten commands; `skills/ai-task/state.py` is the state machine |
| `agents/` | agent templates, rendered per runtime with each tier's model |
| `ai/` | the shared tree: policies, agent contracts, workflows, templates |
| `hooks/` | the guards, the context guard and the runtime gate |
| `profiles/` | one file per plan: settings, tier table, budgets |
| `instructions/` | the managed block (`stub.md`) and the routing reference |
| `codex/`, `.codex-plugin/` | the Codex hook registration and plugin manifest |
| `scripts/`, `tools/`, `bin/` | profile resolution, Codex config merge, template history, `claude-1m` |
| `tests/` | the suites `tests/run-all.sh` runs |
| `docs/` | the reference documentation |

## Known risks

What version 2.0.2 knowingly does **not** protect against, each with why it
stays, what limits the damage and what to do: [docs/known-risks.md](docs/known-risks.md).

| Risk | In one line |
|---|---|
| [The guards are a tripwire, not a sandbox](docs/known-risks.md#the-guards-are-a-tripwire-not-a-sandbox) | a determined process gets past a regex |
| [Human approval can be forged by a determined process](docs/known-risks.md#human-approval-can-be-forged-by-a-determined-process) | an obfuscated call under a pty can approve; every approval is journalled |
| [The deletion gate stops an agent's command, not an agent's script](docs/known-risks.md#the-deletion-gate-stops-an-agents-command-not-an-agents-script) | run `--confirm-delete` in a terminal of your own |
| [`AI_UNATTENDED=1` turns the human gates off](docs/known-risks.md#ai_unattended1-turns-the-human-gates-off) | export it only in a launcher, never in an interactive shell |
| [The routing hooks are less protected than the guards](docs/known-risks.md#the-routing-hooks-are-less-protected-than-the-guards) | review hook diffs by hand |
| [The compaction snapshot runs `git` in the working directory](docs/known-risks.md#the-compaction-snapshot-runs-git-in-the-working-directory) | do not run agents in repositories you do not trust |
| [Codex runs only hooks you re-approved](docs/known-risks.md#codex-runs-only-hooks-you-re-approved) | re-trust `/hooks` after every install |
| [Codex facts are observed, not guaranteed](docs/known-risks.md#codex-facts-are-observed-not-guaranteed) | check `missed_reroute` after a Codex upgrade |
| [Budgets and quota are advice, not limits](docs/known-risks.md#budgets-and-quota-are-advice-not-limits) | nothing here ever blocks work |
| [`--adopt` edge cases fail safe, not smoothly](docs/known-risks.md#--adopt-edge-cases-fail-safe-not-smoothly) | adopt on a clean, committed tree |
| [The usage report's parse cache trusts mtime and size](docs/known-risks.md#the-usage-reports-parse-cache-trusts-mtime-and-size) | `--no-cache` settles a surprising number |

## Why claude-agentic?

Agents are good at small, well-defined changes and dangerous on code whose rules
live in nobody's head. Asking an agent nicely to stay in scope does not survive
a long session; a hook does. Uniform ceremony fails the other way: a full
pipeline for a label change teaches everyone to skip it.

So the plugin makes the risk explicit and the gates proportional. It is tuned
for **one developer who knows the codebase, on a Pro or Max plan**, following
the [AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook);
a fully delegated `team` profile is one JSON key away. And it is cheap by
default: readers on the cheapest model, the strong model only where being wrong
is expensive, and `/usage-report` to check.

## Tests

```bash
bash tests/run-all.sh
```

Twenty-seven suites, 3,185 assertions: the guards against JSON fixtures in both
runtimes (including multi-file `apply_patch` payloads), the state machine,
scaffold idempotency, installer rendering for every plan and `--target`, the
Codex agent renderer, the `config.toml` merge, `/project-update` against the
oldest shipped templates, an end-to-end run that drives a T5 task from Claude
and then from Codex over one state, the usage report, and both escalation gates.
No suite reads or writes your real `~/.claude` or `~/.codex`.

## Documentation

| File | About |
|---|---|
| [docs/getting-started.md](docs/getting-started.md) | the first hour: install, `/ai-init`, a worked T1 and T4 task |
| [docs/installation.md](docs/installation.md) | every installer option, what it writes, what loads per turn, the limits it sets |
| [docs/architecture.md](docs/architecture.md) | how the pieces fit: `.ai/`, the pipeline, state, hooks, the two adapters |
| [docs/routing.md](docs/routing.md) | the two runtimes, the plans and the model each tier resolves to |
| [docs/risk-tiers.md](docs/risk-tiers.md) | how classification works and how to tune it |
| [docs/workflows.md](docs/workflows.md) | the five workflows and how one is chosen |
| [docs/agents.md](docs/agents.md) | the roster, contracts and when each agent runs |
| [docs/hooks.md](docs/hooks.md) | every rule the guards enforce, their configuration and limits |
| [docs/hook-performance.md](docs/hook-performance.md) | what the guards cost per tool call and how a change is proved behaviour-preserving |
| [docs/project-update.md](docs/project-update.md) | updating a project, migrations, rollback, `--adopt` |
| [docs/known-risks.md](docs/known-risks.md) | what the plugin does not protect against |
| [docs/faq.md](docs/faq.md) | why something was blocked, and how to change it |

The [wiki](https://github.com/vanssata/claude-agentic-sdlc-module/wiki) is the
practical guide; the [site](https://vanssata.github.io/claude-agentic-sdlc-module/)
has the catalog, the interactive tier router and the demo.

## Contributing, security and license

- [CONTRIBUTING.md](CONTRIBUTING.md): setup, tests, and how a change gets merged
- [SECURITY.md](SECURITY.md): what counts as a vulnerability and how to report
  one privately
- [LICENSE](LICENSE): MIT
