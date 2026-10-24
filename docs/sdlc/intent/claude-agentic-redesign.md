# Intent: claude-agentic redesign — job-named commands, weight-based risk, auto-selected depth

<!-- Stage 1 of the SDLC flow. Say WHAT and WHY. Leave HOW to the spec. -->

Evidence and the full proposal: `docs/redesign-analysis-2026-10-24.md` (Bulgarian). This
intent is the entry point for the next session; the analysis holds the numbers and the
reasoning behind every line below. Written on 2026-10-24 from an analysis session, not from
a `state.py ask --topic` brainstorm, so **Decisions taken** lists the analysis' conclusions
that the developer has read, and **Open questions** what the spec stage must settle.

## Problem

- The command surface is confusing: ten skills in three overlapping families with four
  prefixes (`ai-`, `sdlc-`, `project-`, `usage-`). Setup has three entry points, planning has
  two chains and four planning agents, and `docs/faq.md` has to explain which command to
  use. Names say the implementation layer, not the job.
- Risk classification collapses to T4 and T4 means three to five STRONG reviews. Of the 23
  tasks journaled in this repository, 9 are T4 with the same trigger sentence ("a process
  every Bash call runs through"); T-2026-10-21-001 cost 25.4M tokens and five review passes
  for 51 lines. No code computes a tier; a model reads a seven-row table.
- The tier *feels* locked to lines and files, and the feeling is accurate: `diff_budget`
  is the only number in the policy, it is printed on every `step-done`, lives in four
  copies and blocks `skipped_green`.
- The sensor machinery never paid off: 32 `review-gate` calls, 0 `skipped_green`; `bite`
  unavailable in 18 of 18 `sensors.json`, `lint` unavailable in 16, `traceability` red in 15.
- Seven tiers describe four behaviours; a small task takes 7–9 `state.py` calls and about
  1 700 lines of prose to run; the tier table exists in six places and `ai/agents/manager.md`
  contradicts the other six files on where direct mode ends.
- In the production shop (`/Store/Projects/new-shop-2019`) the pipeline was used for one
  afternoon (6 tasks on 2026-09-10, two commits carrying ~34 000 lines of snapshot JSON for
  ~300 lines of code, `testing.md` with no verify command). What the developer used for three
  months instead is a hand-built toolbox: 158 plan-mode plans, 10 job-named skills, 4 sonnet
  reader agents, 13 directory rules, 4 guard hooks totalling 166 lines, 380 helper scripts, a
  file-change table as the release summary.

- Across the whole machine (see **Evidence from every project** below): 84 tasks, 83 of them in
  September 2026; T4 on 13 of 19 tasks in productEditorApp and 6 of 6 in the Learning Workbench;
  39 `review-gate` calls in three projects with 0 `skipped_green`; five of seven `.ai/` trees
  behind the plugin; hand-written skills, rules and plan-mode plans are what developers kept using.

## Proposed outcome

- A developer sees six commands named by the job, in lifecycle order, after
  https://skills.addy.ie/: `/setup`, `/spec`, `/plan`, `/build`, `/review`, `/status`
  (plus `/ship` for the hand-over). No FAQ entry is needed to pick one. Old names print the
  new name for one version.
- `/build` prints the change's **logical weight** in at most seven lines (behaviour change,
  blast radius, data and contracts, sensitive domain, reversibility, test coverage of the
  touched path, familiarity), each with evidence, and from it picks one of three modes
  automatically: **light**, **guarded**, **full**. Path floors for payments, auth and infra
  stay deterministic; re-scoring only raises; lowering is a human's written decision.
- Lines and files are reported, never gating: no `diff_budget` gate, no `step-split`, no
  `DIFF_BUDGET_EXCEEDED`, no `over_budget` rule.
- A light task is three `state.py` calls and reads about 400 lines of policy; a guarded task
  gets one plan-mode plan and at most two review passes; a full task runs the whole SDLC.
- Two deterministic facts decide whether a model reviews: the verify result on the current
  tree and the scope guard. `bite`, `duplicates`, `traceability`, `plan_sections`, lint and
  typecheck as gate inputs are gone.
- One artefact per task in the repository (`task.md` with the weight, the plan, the verify
  result, the verdict and a File / Change / New-Edit-Delete table). Tree snapshots stay in
  git-ignored state. Three control files (`state.json`, `events.jsonl`, `task.md`) instead of
  eight, so the path guard has fewer rules to defend.
- `/setup` adopts an existing project toolbox (skills, rules, agents, hooks, scripts) instead
  of generating a knowledge base, and refuses to finish without a `verify_command`.
- The tier table, now the weight table, lives in one file with one generated mirror; README
  and docs link to it. Agents go from 14 to 7 or 8.

## Affected users & systems

- Skills: `ai-init`, `ai-audit`, `ai-status`, `ai-task`, `project-init`, `project-update`,
  `sdlc-intent`, `sdlc-spec`, `sdlc-plan`, `usage-report` (renamed, merged or removed).
- `skills/ai-task/state.py` (28 → 4 public subcommands), `skills/ai-task/sensors.py` (about
  1 000 lines removed), `skills/project-update/update.py` (migration 0007: renames, tier →
  mode mapping, aliases).
- `.ai/policies/risk-tiers.json` schema v4 (`weight`, `modes`), its mirror, the templates
  under `skills/ai-init/templates/`, `ai/workflows/*.md` (merged into one), `ai/agents/*.md`,
  `agents/*.md.tmpl`, `instructions/stub.md` and `routing.md`, README, `docs/`.
- Hooks only in the optional third phase (`hooks/ai-path-guard.sh`, consolidation into one
  PreToolUse process); `tests/test-guard-characterization.sh` golden must stay byte-identical
  for any performance-only change.
- User projects on both runtimes (Claude Code and Codex) through `/project-update`.

## Constraints

- `docs/sdlc/specs/direct-mode-diet.md` tasks 2–4 finish first (task 1 is commit `4b3b9e1`);
  this redesign builds on its decisions (two review passes, `close` as the direct-mode exit,
  `test-run --scope all`, the project-local tier examples).
- Provider-neutral: every public `state.py` command and the weight computation work under
  Codex; agents render from the same templates.
- No agent commits, pushes or deploys; a guard refusal is never worked around.
- A golden-file change in the characterization suite is a rule change, never a performance
  change.
- Old journals must stay readable: `tier` remains a field, holding the computed weight, so
  `/status --cost` and `/usage-report` keep working across the rename.

## Out of scope

- Hook consolidation and the Python port of the path guard (phase 3, optional).
- Changing the guards' rules themselves (what is denied) beyond the diet's §4.
- A local model; the LOCAL tier stays unavailable.
- New product features for user projects (deploy skills, QA scripts): `/setup` adopts what a
  project has, it does not author shop-specific tooling.

## Decisions taken

From the analysis, read by the developer on 2026-10-24 (not a brainstorm; no
`<slug>.questions.md` exists yet):

- Three named modes (light / guarded / full) replace numbered tiers; names do not renumber
  (the shop still carries the earlier six-tier numbering).
- Weight is computed from the seven questions with evidence; the model (`ai-risk`) is called
  only on `uncertain` or a tie. Path floors stay deterministic.
- `diff_budget` stops gating entirely; size is reported only.
- Sensors reduce to the verify result and the scope guard.
- One artefact per task; snapshots never in `reports/`.
- Commands are named by the job; `/build` is the router.
- `/setup` adopts an existing toolbox and requires `verify_command`.
- Readers with judgement run on BALANCED; FAST is for running a command and verbatim
  extraction only.
- `/status --cost` reads `events.jsonl`; `settings.common.json` raises `cleanupPeriodDays`.

## Open questions

- Exact point values and thresholds of the seven weight questions, and whether question 2
  (blast radius) is measured by `grep` caller counts or declared by the session with
  evidence **(blocking)** — the spec must fix the table before `state.py weight` is written.
- Whether `ai-security` stays a separate agent or becomes a `focus: security` brief of
  `ai-reviewer` in full mode.
- Whether `ai-implementer` survives (no journaled use in 23 tasks).
- The command name for the implementation step: `/build` (addy) or `/task` (continuity).
- How `/setup --adopt` maps a project's own skills, rules and hooks into the policy files
  without copying them into `.ai/`.
- Where the alias layer lives for one version: skill frontmatter stubs, or `update.py`
  printing the new name on first use.
- Phase 1 scope: whether the merged `workflows.md` and the prose diet ship with the weight
  model or after it.

## Evidence from every project on this machine (2026-10-24)

Inventory of `/Store/Projects/*`, `/Store/ProjectToBuild/*`, `/Store/Ideas/*` plus the Claude Code
prompt history (`~/.claude/history.jsonl`, 1 253 prompts). Seven projects have `.ai/`; six ever ran
`/ai-task`. Numbers reproduce with `tools/journal-summary.py <root>`.

| Project | `.ai/` schema | tasks | when | tiers | review-gate | local toolbox |
|---|---|---|---|---|---|---|
| claude-agentic (this repo) | 6 | 24 | Sep–Oct | T2 9, T4 9 | 32 calls, 0 skipped | none |
| new-abrv2-desginsystem | 5 | 21 | Sep only | T2 9, T3 7, T4 3 | 1 call, red (`bite` unavailable, `tests` stale) | 1 plan; 9 `scope_change` events |
| productEditorApp | none (pre-5) | 19 | Sep only | **T4 13 of 19**, feature workflow, median 104 min | none recorded | 13 SDLC docs |
| SyliusSlider | 5 | 7 | Sep 6, Oct 1 | T2 6 | 6 calls, 6 red: `lint`/`typecheck`/`tests` green, `bite` unavailable 5/5, `traceability` red 4/5 | 3 agents, 4 hooks, 1 skill |
| Personal Learning Assistant Workbench | none | 7 | Sep only | **T4 6 of 6**, median 169 min | none | 2 plans |
| new-shop-2019 | none | 6 | one afternoon, Sep 10 | T3 6 (old table) | none | 158 plans, 10 skills, 4 agents, 13 rules, 4 hooks |
| abr-v1 | none | 0 | — | — | — | 3 skills, 3 hooks, 57 commits |
| vanssa-site | none | 0 | — | — | — | 2 skills |

What the whole machine says:

- **Adoption was a September burst, not a habit.** 84 tasks in total; 83 of them in September 2026,
  one in October outside this repository. Prompt history agrees: `/ai-task` was typed 4 times in
  new-abrv2 (173 prompts there), 6 times in productEditorApp (83 prompts), 0 times in SyliusSlider,
  abr-v1, breezy-bg and the shop. The most typed plugin commands are `/project-update` and
  `/project-init`, i.e. maintenance of the plugin itself, not work.
- **T4 inflation is not local to this repo.** productEditorApp 13 of 19 and the Learning Workbench
  6 of 6 landed on T4; new-abrv2 has 3. Everywhere the trigger is the generic "changes a process"
  row. Only SyliusSlider, a small bugfix stream, stayed at T2.
- **The sensor gate never produced `skipped_green` anywhere**: 39 `review-gate` calls across three
  projects, 0 skips. In SyliusSlider the project's own checks were green every time and the gate
  still went red on `bite` (the step command takes no `{files}` placeholder) and `traceability`.
  The gate fails on plumbing, never on code.
- **Five of seven `.ai/` trees are behind the plugin** (no `VERSION`, or schema 5); none of the
  user projects received the direct-mode diet. The knowledge base is written once by `/ai-init`
  and never updated; the directory rules and skills the developer writes by hand are what stay
  alive (new-shop: 13 rules, 10 skills; abr-v1: 3 skills, 3 hooks; SyliusSlider: 3 agents, 4 hooks).
- **Plan mode is the planner the developer actually uses**: 158 plans in the shop, `/plan` typed 12
  times in breezy-bg, 2 in SyliusSlider; `/sdlc-intent` and `/sdlc-spec` were typed 3 times in
  this repo and 3 in a learning project, nowhere else.
- **Scope friction shows up where the pipeline was used most**: new-abrv2 journals 9
  `scope_change` events in 8 journaled tasks — plans that named the wrong files, amended mid-step.
- **Cross-runtime is real but thin**: five projects carry `.codex/`; the pipeline journals show
  two runtime handoffs in total, both in this repository.

Consequences for the proposal, on top of the new-shop lessons: the weight model must be
tested against productEditorApp and the Learning Workbench (both all-T4 feature streams on a solo
developer's own code) and must land them in `guarded`, not `full`; `/setup --update` must be able
to bring a schema-less `.ai/` forward in one run, since every user project is behind; and
`SCOPE_CHANGE_REQUIRED` should amend the step in place instead of returning to PLAN, because
nine amendments in eight tasks is the normal case, not the exception.

## Superpowers: how this module should use it, and the Codex side (checked 2026-10-24)

What was checked: https://claude.com/marketplace/plugins/superpowers, the `obra/superpowers`
repository (skills list, `using-superpowers`, `subagent-driven-development`, `hooks/`), this
module's own references, and both local installs. Two repository files returned HTTP 503 and are
unverified: `hooks/hooks.json` and `skills/using-superpowers/references/codex-tools.md`.

**State today.** Superpowers is not installed on this machine in either runtime
(`~/.claude/plugins/installed_plugins.json`, `~/.codex/config.toml`). The module mentions it in
exactly two optional lines: `skills/sdlc-intent/SKILL.md:34` ("if `superpowers:brainstorming` is
available, invoke it") and `skills/sdlc-plan/SKILL.md:19` (`superpowers:writing-plans` for step
granularity). Neither line has ever run here.

**What superpowers is.** Fifteen skills (MIT, Jesse Vincent): workflow — `brainstorming`,
`writing-plans`, `executing-plans`, `subagent-driven-development`, `dispatching-parallel-agents`,
`using-git-worktrees`, `requesting-code-review`, `receiving-code-review`,
`finishing-a-development-branch`; discipline — `test-driven-development`, `systematic-debugging`,
`verification-before-completion`; meta — `using-superpowers` (SessionStart hook injects it and makes
skill use mandatory before any response), `writing-skills`, `diagnosing-superpowers`. Each skill has
"red flags" and "common rationalizations" tables — the same anatomy as skills.addy.ie.

**Overlap with this module, by job.**

| Job | superpowers | claude-agentic today | Verdict |
|---|---|---|---|
| intent / design dialogue | `brainstorming` (one question at a time, before plan mode) | `/sdlc-intent` (same shape, plus `state.py ask --topic` for a durable record) | superpowers drives the dialogue; the module keeps the record |
| plan | `writing-plans` (bite-sized tasks, exact paths, verification step each) | `/sdlc-plan`, `ai-planner`, plan mode | identical goal; adopt its task format as the `guarded` plan shape (`allowed_files` is already "exact paths") |
| execute | `executing-plans` (inline, one final review), `subagent-driven-development` (fresh subagent per task, two-stage review, round cap, ledger) | direct mode (inline) and the full pipeline | the two superpowers modes map one-to-one onto `guarded` and `full`; their round cap and ledger are what `review-economy.md` reinvented |
| verify | `verification-before-completion`, `test-driven-development` | "verify once, to the end, one batch", bugfix shows the failing test first | same rules; superpowers has no `verify_command` record or test-run cap |
| review | `requesting-code-review`, `receiving-code-review` | `ai-reviewer`, `review-gate`, sensors | superpowers reviews by checklist, never by model-tier; the tier choice stays ours |
| isolation | `using-git-worktrees` | nothing | adopt: a `guarded`/`full` task in a worktree makes the scope guard and `git revert` trivial |
| finish | `finishing-a-development-branch` (merge / PR / keep / discard) | `/ship` + human approval | complementary: superpowers stops for pushes and merges too |
| risk | none | tiers, path floors, weight (proposed) | the one thing superpowers has no answer for; it is this module's reason to exist |
| guards | none (prompt discipline only) | three deterministic hooks | keep; superpowers relies on the model obeying |

**Recommendation.** Do not re-implement what superpowers ships. In the redesign, each of the six
commands names the superpowers skill it delegates its method to when the plugin is present, and
carries a short fallback when it is not — the pattern the two existing lines already use, made
systematic:

- `/spec` → `superpowers:brainstorming`, answers recorded through `state.py ask --topic`.
- `/plan` → `superpowers:writing-plans`; the module adds the weight and `allowed_files`.
- `/build` light → nothing extra; guarded → `executing-plans` inside `using-git-worktrees`;
  full → `subagent-driven-development`, with the module's `ai-reviewer`/`ai-security` as the
  reviewers and its round cap (2) overriding theirs.
- `/review` → `requesting-code-review` checklist as the reviewer brief; `receiving-code-review`
  for the remediation batch.
- `/ship` → `finishing-a-development-branch`, stopped before merge or push by `ai-git-guard`.
- always → `verification-before-completion`, `systematic-debugging` for the bugfix workflow.

What stays in this module: weight-based risk, path floors, the deterministic guards, the journal
and `verify_command`, the state machine's four public commands. A `/setup` check should report
whether superpowers is installed and, if not, print the install line for the runtime in use.

Two cautions. `using-superpowers` makes skill invocation mandatory "before ANY response" through
a SessionStart hook; our `context-guard` also writes at SessionStart and our stub is paid for on
every turn — measure the combined always-loaded cost with `tests/test-instruction-budget.sh`
before recommending both. And superpowers forbids parallel implementer subagents while this
module implements in the session; the mapping above keeps our rule (session implements) and uses
superpowers' implementer only in `full`.

**Codex.** There is no separate "superpowers for Codex": the same plugin installs in Codex from the
official plugin marketplace (`/plugins` in Codex CLI, search "superpowers"; the repo carries a
`.codex-plugin/` directory and a `references/codex-tools.md` tool mapping). This machine's
`~/.codex/config.toml` already registers `claude-plugins-official` as a marketplace, so the install
is one step there too. Skills follow the open `SKILL.md` format (agentskills.io), which Codex reads
natively; skills.addy.ie's set installs into Codex with `npx skills add addyosmani/agent-skills`.
The module's Codex adapter therefore needs no second integration: the same `superpowers:<skill>`
names resolve in both runtimes, and the fallback lines cover an install without it.

## How to resume

1. Read `docs/redesign-analysis-2026-10-24.md` (sections 1, 2a and 3; 4 for phasing).
2. Check `/ai-status` and `git log` for the state of direct-mode-diet tasks 2–4.
3. `/sdlc-spec docs/sdlc/intent/claude-agentic-redesign.md` to turn this into a spec, or
   `/ai-task` for phase 1 once the diet is closed.
4. `tools/journal-summary.py <project-root> [--timeline T-…]` reproduces every journal
   number quoted in the analysis, for this repository and for `/Store/Projects/new-shop-2019`.
