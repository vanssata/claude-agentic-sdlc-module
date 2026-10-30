# RiskRails

[![Version](https://img.shields.io/badge/version-3.0.1-d2f878?labelColor=101210)](https://github.com/vanssata/claude-agentic-sdlc-module/releases/tag/v3.0.1)
[![Runtimes](https://img.shields.io/badge/runtimes-Claude%20Code%20%7C%20Codex-d2f878?labelColor=101210)](docs/routing.md)
[![Known risks](https://img.shields.io/badge/known%20risks-documented-d2f878?labelColor=101210)](docs/known-risks.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-d2f878?labelColor=101210)](LICENSE)

**Let an AI agent work on your legacy production code without the agent
widening its own scope, reading a production secret, force-pushing or
deploying.**

**RiskRails** (`riskrails`) is a plugin for **Claude Code and Codex**, built for
codebases with undocumented business rules, old workarounds and behaviour
customers rely on today. Each change is **weighed** on six axes and runs in one
of three modes — light, guarded, full — so a typo fix stays a one-line edit and
a payment change gets a written plan, an adversarial review and a human's
approval. Risky actions are stopped by a hook, not by a polite request in a
prompt.

```bash
npx riskrails@3.0.1   # detects Claude Code, Codex or both (Node 18+, python3)
```

Then, in any project: `/rr-setup` once, and `/rr-build <what you want>` for
every change.

**What you get**

- **Guards, not guidelines.** One hook on every tool call refuses an edit
  outside the task's files, a read of a production secret, a force push, a
  push to a protected branch, a deploy command, `npm publish`. No agent merges
  or deploys; a commit, a push or an approval runs only as the command you
  picked in the runtime's own dialog, verbatim, once — or you run it yourself.
- **Weight, not ceremony.** Scope, reversibility and coverage are measured
  from the tree; behaviour, domain and novelty are declared with evidence. The
  sum picks the mode, the mode picks who plans, who reviews and whether you
  sign off. The mode only rises during a task; lowering it is yours.
- **Deterministic gates.** `state.py` measures and refuses; no model decides
  whether a step stayed in scope, whether the suite is green on this tree, or
  whether a budget is spent. Every decision is in a journal a human can read.
- **Cheap by default.** Readers on the cheapest model, the session on the one
  that thinks, the top tier only on a named trigger, one short always-loaded
  file per runtime. `/rr-status --cost` shows where the tokens went, at zero
  model cost.
- **One `.ai/` tree for both runtimes.** Start a task in Claude Code and finish
  it in Codex; the knowledge base, the policies, the task state and the compact
  record of every closed task are shared.

Tuned for **one developer who knows the codebase**, on a Claude Pro, Max or
Team plan, or a ChatGPT Plus or Pro plan, following the
[AI-native SDLC playbook](https://claude.com/blog/the-ai-native-sdlc-playbook).

**Version 3.0.1.** The guards have limits: read [Known risks](docs/known-risks.md)
before relying on them. What is decided but not built is in [ROADMAP.md](ROADMAP.md).

## Upgrade to 3.0

3.0 renames the plugin from `claude-agentic` to `riskrails`, replaces the risk
tiers with the weight and the three modes, replaces the `/ai-*` and `/sdlc-*`
commands with `/rr-*`, ports the guards to one Python process, and moves the
task state to `.ai/state/state.json`. The old names stay as aliases for this
version. Step by step, in this order:

1. **Commit every project's `.ai/`** before anything else; the update tells you
   when the tree is dirty, and `git restore` is the rollback.
2. **Close or abandon tasks in flight.** A task started by 2.x is refused by
   the new commands as `old surface`; finish it with the version that started
   it, or drop it with `python3 ~/.claude/skills/ai-task/state.py close
   --abandon`. Check with `/rr-status`.
3. **Update the home** on every machine, for every runtime:

   ```bash
   npx riskrails@3.0.1              # or: npx -y riskrails@latest --yes
   ```

   It moves `<home>/claude-agentic/` to `<home>/riskrails/` and leaves a
   symlink at the old path for one version, replaces the old hook entries with
   `ai-guard.py` and `runtime-gate.py`, retires the old agents and shim files
   to `backups/<date>/`, and rewrites the managed block. Restart the runtime.
   In Codex, open `/hooks` and **trust the changed entries** — until you do,
   nothing is enforced. `--dry-run` shows all of it first.
4. **Update each project:**

   ```
   /rr-setup --update               # dry run first; read it; then --apply
   ```

   Four migrations run inside the dry run, in order, before the merge:
   `0007` creates `.ai/policies/weight.json`, carrying over the project's
   edits to its risk-tier table; `0008` renames the managed-block markers and
   the router's routes; `0009` moves `current.json` to `state.json`; `0010`
   creates `.ai/policies/dialog.json` with the dialog on. Edited markdown is
   three-way merged, JSON policies key by key with a confirmation per key;
   `delete?` proposals are left for you to confirm. The schema becomes 10.
5. **Decide two things the migrations cannot.** Keep the dialog (then amend
   constitution C5 as `0010` hints) or set `"enabled": false`; and tune the
   weight table — `domain.modules`, `customer_visible`, `hot_paths`,
   `needs_step`, `irreversible` — then `state.py weight --mirror`.
6. **Verify**: `/rr-status` shows schema 10 and no task in flight; a
   `/rr-build` on a small change runs light and closes on the two facts.
   Commit `.ai/`.

Every machine of a team upgrades the plugin before a project at schema 10 is
committed; an older plugin refuses such a project. Rollback and the full
migration table are in [docs/project-update.md](docs/project-update.md); the
home-side details in [docs/installation.md](docs/installation.md).

## Install

```bash
npx riskrails@3.0.1                       # detects Claude Code, Codex, or both; proposes the detected plan
npx riskrails@3.0.1 --target codex        # auto | claude | codex | both
npx riskrails@3.0.1 --plan max --fable no # pro | team-pro | team-max | max | max20 | balanced-max
npx riskrails@3.0.1 --codex-plan plus     # plus | pro | balanced-max
npx riskrails@3.0.1 --context economy     # the plan's compaction window; the context guard also blocks
npx riskrails@3.0.1 --dry-run             # print what would be written, write nothing
npx -y riskrails@latest --yes             # update in place, keeping the recorded plan
```

Pin the version: the hooks it installs see every command an agent runs. It
installs the managed block, the plan's settings and limits, the five agents
with their tiers baked in, the hooks, the skills, the shared tree at
`<home>/riskrails/ai/` and the resolved profile; re-running it updates in
place with dated backups. The plugin route (`/plugin install riskrails`)
carries the skills and hooks only — run `npx` as well. Every option, every
limit it sets and what loads on every turn: [docs/installation.md](docs/installation.md).

## Use

The same commands in both runtimes:

| You want to | Run |
|---|---|
| set up `.ai/` in a project, or bring it up to the installed plugin | `/rr-setup`, `/rr-setup --update` |
| move another AI tool's files, or the project's own toolbox, into this layout | `/rr-setup --adopt` |
| score the repository against the twelve plays | `/rr-setup --audit` |
| turn an idea into intent, requirements and design | `/rr-spec <idea>` |
| plan a spec into tasks, or one task into a mode and a start | `/rr-plan <spec or task>` |
| do the work, or resume it | `/rr-build <request>` (no task in flight: it runs `/rr-plan` first) |
| run a whole plan as one task | `/rr-build-all docs/sdlc/plans/<slug>.md` |
| review the change | `/rr-review` — guarded and full, or when `close` asks |
| close the task, get the human's approval | `/rr-ship` |
| see where the task stands, or what it cost | `/rr-status`, `/rr-status --cost` |

The old names — `/ai-init`, `/ai-task`, `/ai-status`, `/ai-audit`,
`/project-init`, `/project-update`, `/sdlc-intent`, `/sdlc-spec`,
`/sdlc-plan`, `/usage-report` — are aliases for one version.

### Three modes

`state.py weight` scores six axes 0–2 — scope, behaviour, reversibility,
domain, novelty, coverage — and the sum W picks the mode. The table is the
project's `.ai/policies/weight.json`; reversibility or domain at 2 is full
whatever W is ([docs/weight.md](docs/weight.md)).

| Mode | When | Plan | Review | Human stops |
|---|---|---|---|---|
| **light** | W ≤ 2 | inline: files, test, rollback | only when a fact at close is red | none |
| **guarded** | W 3–7 | plan mode, which you accept | one pass on BALANCED | the plan |
| **full** | W ≥ 8, or reversibility or domain = 2 | written; `architect` on STRONG when the design is open | one pass on STRONG, security focus when domain = 2 | the plan, and the tree at close |

A `full_irreversible` task (both hard axes at 2, or `DROP`, `TRUNCATE`,
`DELETE FROM` in the diff) is approved with `approve --confirm <operation>` in
your own terminal. `verify` and `close` re-score the two hard axes from the
real diff; a mode never drops during a task.

### The two facts

`close` measures, never asks: (a) a green whole-suite `verify` on the tree as
it is now; (b) every changed file inside the task's files. Green and green in
light mode closes the task. Tests run once, to the end, with the log under
`.ai/state/logs/`, and every failure is fixed as one batch; two whole-suite
runs are the budget, and the third is your decision.

### The dialog

With `.ai/policies/dialog.json` on (the default), the approval at close, a
budget refusal and a guarded `git commit` or `git push` come to you as a
question in the runtime's own dialog. The pick is recorded by a hook and the
command runs once, verbatim; a command that is not the pick is refused as
`CONSENT_REQUIRED`. Off, the same decisions are commands you run in your own
terminal.

### Batch — one task for a whole plan

`/rr-build-all docs/sdlc/plans/<slug>.md` runs every row of a programme plan as
the steps of one task: the ready rows go to parallel implementers on
BALANCED (a step's `after` serializes the dependent ones), the suite runs once,
every failure is fixed by parallel fixers as one batch, one review at the
mode's tier, its findings fixed as one batch, then tests and the review again
until it passes. After three failed review passes the next verdict is yours.

### The record

A closed task's who, what, how and why travel as a compact record: `state.py
memory enable` (yours, in a terminal) switches a project to packages mode, in
which `close` appends the task's entries to a per-developer batch under
`.ai/memory/` and a pre-push hook validates them; `state.py recall --files …`
gives an agent what the record holds about the files it is about to touch,
within a token budget. Task ids are `T-YYYY-MM-DD-HHMM-<slug>`
([docs/local-memory.md](docs/local-memory.md)).

## The guards

| Hook | Where | Does |
|---|---|---|
| `ai-guard.py` — **git** | every repository, both runtimes | refuses force push, remote branch delete, history rewrite, push or merge to a protected branch, `gh pr merge`, `--no-verify`, staging a secret, production deploy commands, `npm publish`; a `git commit` or `push` that is not the dialog's pick |
| `ai-guard.py` — **paths** | where `.ai/` exists | refuses reading or writing `.env`, `secrets/`, keys, dumps, production logs; writing the task state, the journal, `task.md`, the policies' JSON, the compact record, the installed guards; the human-only `state.py` and `update.py` commands from an agent |
| `ai-guard.py` — **scope** | during an implementation step | refuses editing a file the step does not name, with `SCOPE_CHANGE_REQUIRED` |
| `ai-guard.py` — **decision** | while a decision is open | holds every tool until the dialog is answered or settled in the terminal |
| `cap-large-read.py` | Claude Code | refuses an unbounded `Read` over 4 000 lines or 250 KB; a `limit` within the budget passes |
| `context-guard.py` | both | warns from 80% of the compaction point, snapshots before a compaction, injects the handoff at session start, checks plan drift |
| `runtime-gate.py` | both | sends the top model's launches one tier down during an outage or at 90% of the weekly limit; asks before an EXPERT launch past the budget |
| `dialog-gate.py` | both | records your picks from the runtime's dialog; holds the turn while a decision is open |

Every path of a Codex `apply_patch` is checked on its own. The guards are
regex over a command line or a path — a tripwire for the honest mistake, **not
a security boundary**; the real backstops are branch protection, secrets off
the developer machine and human review. Every rule, its configuration and
how a change is proved behaviour-preserving: [docs/hooks.md](docs/hooks.md).

## Model tiers

The prompts name tiers; the installed profile says which model each tier is on
your plan and runtime (`state.py profile --tier STRONG`).

| Tier | Claude Code | Codex | Does |
|---|---|---|---|
| FAST | `haiku`, low | Terra, low | reading and running: `Explore`, `log-reader` |
| BALANCED | `sonnet` | Terra, medium | discovery with judgement (`ai-discovery`), the guarded review, batch implementers |
| STRONG | `opus`, high | Sol, high | the full review, security review, `architect` in `/rr-spec` |
| EXPERT | Fable 5.1 [1m] on `architect`; Opus without Fable | Astra | what STRONG could not settle |

The session implements — Opus 5.5 [1m] on Max, `opusplan` on Pro, Sol on Codex
— and the expensive tiers run one at a time on a named trigger. Plans,
budgets, the runtime gate and the Codex differences: [docs/routing.md](docs/routing.md).

## Known risks

What 3.0 knowingly does not protect against, each with why it stays and what
to do: [docs/known-risks.md](docs/known-risks.md).

| Risk | In one line |
|---|---|
| The guards are a tripwire, not a sandbox | a determined process gets past a regex |
| Human approval can be forged by a determined process | a pty, or a written ledger, can approve; every approval is journalled |
| The deletion gate stops a command, not a script | run `--confirm-delete` in a terminal of your own |
| `AI_UNATTENDED=1` turns the human gates off | export it only in a launcher, never in a shell |
| Three hooks are less protected than the guards | review hook diffs by hand |
| The compaction snapshot runs `git` in the working directory | do not run agents in repositories you do not trust |
| Codex runs only hooks you re-approved | open `/hooks` after every upgrade |
| Codex facts are observed, not guaranteed | grep the journals for `missed_reroute` after a Codex upgrade |
| The dialog switch is read in two places | when the dialog and the terminal disagree, use the terminal |
| Budgets and quota are advice, not limits | read the quota with its `stale` field |
| `--adopt` edge cases fail safe, not smoothly | adopt on a committed tree, keep `original/` |
| The usage report's parse cache trusts mtime and size | `--no-cache` when a number surprises you |

## Tests

```bash
python3 -I tests/run_suite.py --serial test_guard_characterization.TestTimed --serial test_dialog_gate.TestGateFastPath
python3 -I -m unittest discover -s tests -p 'test_*.py'      # CI's serial oracle, same test ids
AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py
```

Fifty-six suites, 1022 tests, about 75 seconds in parallel. The guards against JSON fixtures for both runtimes and a
golden of 1 341 recorded decisions, byte for byte, with timed cases that hold
the hot path under its budget; the state machine, the weight, the batch loop,
the dialog contract and the documents rule; the compact record and its
pre-push validator; the installer for every plan and `--target`, the Codex
agent renderer and the `config.toml` merge against a fixture full of
third-party settings; `/rr-setup --update` against projects scaffolded from
the oldest shipped templates and edited by hand; `--adopt` against Spec Kit,
Kiro and Cursor fixtures; and an end-to-end run that installs both runtimes
into scratch directories, drives one task through the guards from Claude and
then from Codex, and proves both see the same state. No suite reads or writes
the developer's real `~/.claude` or `~/.codex`.

## Documentation

| File | About |
|---|---|
| [docs/getting-started.md](docs/getting-started.md) | the first hour: install, `/rr-setup`, a light and a full task, a batch build, the update, the bill |
| [docs/installation.md](docs/installation.md) | every installer option, what it installs per runtime, what loads on every turn, the limits it sets, the 2.x home-side upgrade |
| [docs/project-update.md](docs/project-update.md) | shared versus project-owned files, how a file is updated, the migrations and their rollback, `--adopt` |
| [docs/architecture.md](docs/architecture.md) | how the pieces fit: the installed home, `.ai/`, the pipeline, the state, the hooks, the two adapters |
| [docs/weight.md](docs/weight.md) | the six axes, the three modes, what is measured and what is declared, tuning the table |
| [docs/workflows.md](docs/workflows.md) | feature, bugfix, refactoring, hotfix, investigation |
| [docs/agents.md](docs/agents.md) | the five agents, their contracts, the escalation ladder |
| [docs/routing.md](docs/routing.md) | the tiers per plan and runtime, the runtime gate, the Codex differences |
| [docs/hooks.md](docs/hooks.md) | every rule the guards enforce, their configuration and limits |
| [docs/hook-performance.md](docs/hook-performance.md) | the hot path's budget and how a change is proved behaviour-preserving |
| [docs/local-memory.md](docs/local-memory.md) | the compact record: task ids, packages, recall, the pre-push check, migration |
| [docs/known-risks.md](docs/known-risks.md) | what the guards do not protect against, and what to do about it |
| [docs/faq.md](docs/faq.md) | why something was blocked, and how to change it |
| [docs/sdlc/README.md](docs/sdlc/README.md) | the spec → plan → build artefacts in a project |
| [ROADMAP.md](ROADMAP.md) | what is decided but not built; the open rows |

## Contributing, security and license

- [CONTRIBUTING.md](CONTRIBUTING.md): setup, tests, how a guard change is proved, how a change gets merged
- [SECURITY.md](SECURITY.md): what counts as a vulnerability and how to report one privately
- [LICENSE](LICENSE): MIT
