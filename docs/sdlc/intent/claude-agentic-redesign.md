# Intent: claude-agentic redesign — job-named commands, weight-based risk, auto-selected depth

<!-- Stage 1 of the SDLC flow. Say WHAT and WHY. Leave HOW to the spec. -->

Evidence and the full proposal: `docs/redesign-analysis-2026-10-24.md` (Bulgarian, this
machine) and the second analysis "claude-agentic — анализ и опростяване (2026-10-24)",
a Claude Doc at https://claude.ai/artifact/UqxcHvZhP1Nn7xaLhnkiDm (Bulgarian, the other
machine: 65 journals in seven `.ai/` roots, 582 transcripts, hook timings — see **Second
analysis** below). This intent is the entry point for the next session; the analysis holds the numbers and the
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

- The second analysis, on the production machine, measures the same shape at a larger scale:
  about 22 000 tokens of procedure loaded before the first edit, 185 human stops in 65 tasks
  (T4 median 5.6 per task, T2 zero), 34 of 44 tasks running the full suite two to five times,
  10 of 18 tier raises caused by line or file counts, 43 % of tasks at T4+, 11 % of all spend on
  the plugin maintaining itself, about 1 100 refused tool calls, and three mandatory process
  systems competing in one session (this plugin, superpowers v7 with its "MUST invoke" banner,
  built-in plan mode and `/code-review`). Hooks cost 16–41 ms per call and are not the problem.
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

Confirmed or sharpened by the second analysis (2026-10-24, read by the developer):

- Size is never an input: `diff_budget`, the `diff` and `rescore` sensors and `step-split`
  for budget go away; the only effect of size is the advice "the plan has nine steps, consider
  splitting".
- Paths become hints that may raise one axis by one point, never a floor on the mode. (This
  supersedes "path floors stay deterministic" above — see the open question on floors.)
- An unknown axis scores 1, not 2, and is listed as UNKNOWN in the plan; "take the higher" is
  removed. Re-scoring during a task happens only on reversibility and domain, raises the review
  tier, and never restarts the task or waits for a human.
- Questions are collected once, at planning; during build only a real blocker stops.
- `max_suite_runs` 5 → 2; a third run needs a human decision.
- `handoff.md` is written at phase boundaries and before compaction, not on every state change
  (1 730 events → about 5 per task).
- Remove: `hooks/fable-gate.py`, `hooks/codex-model-gate.py`, the seven agents from
  2026-09-02 and their Codex twins, every `.bak` next to a live file (one dated `backups/`
  directory instead), `.ai/reports/**` from the plugin's own git history going forward.
- `runtime-gate` keeps only the outage reroute; fan-out budgets go.
- Codex is best effort: one source (`agents/*.md.tmpl`, skills), rendered at install, no
  `-strong`/`-balanced` twins; Codex is not a gate for a change on the Claude side.
- Before phase 1: close the four open tasks (ArgoCD 09-14, oroCRM 09-30-002,
  abrites-site-v2 10-22-001, this repo's T-2026-10-22-002), because they keep the guards
  armed in four repositories.

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
- **Command surface: six or nine.** This intent proposes `/setup /spec /plan /build /review
  /status` + `/ship`; the second analysis proposes nine plus `/task` (adds `/test` and `/cost`,
  keeps `/task` as the thin chain `plan → build → test → review → ship`). The spec must pick
  one list; the second analysis' is the more recent and the more complete.
- **Mode names**: light / guarded / full (this intent) or quick / plan / full (second analysis).
  Same three behaviours; pick one and use it in every file.
- **Weight table**: seven questions with evidence (this intent) or six axes scored 0–2
  (scope, behaviour, reversibility, domain, novelty, coverage; W = 0–12; quick ≤ 3, plan 4–7,
  full ≥ 8 or reversibility = 2 or domain = 2; "full + irreversible" when both are 2 or on
  DROP / data migration / prod infra). The six-axis table is concrete enough to implement
  (`weight.py` ≤ 300 lines, `weight.json` ≤ 80 lines) and was checked against nine real tasks;
  prefer it unless the spec finds a case it misclassifies.
- **Path floors**: keep them for payments, auth and infra (this intent) or demote every path to
  a one-point hint (second analysis: a font in `login.html.twig` is not auth, an enum fixture
  under `Migrations/Data/` is not a migration, in a GitOps repo everything is `k8s/**`). The
  second analysis' domain axis already covers money, tax, identity and personal data by a
  project-configured list, so the floors would be redundant; confirm in the spec.
- **Superpowers**: the two analyses disagree on the facts and the answer. This intent found it
  not installed here and recommends delegating each command's method to it when present. The
  second analysis found superpowers v7.0.0 active on the production machine with a 3.2 KB
  per-session banner, and recommends variant A: disable it in projects with `.ai/`
  (`enabledPlugins`) and absorb `systematic-debugging` and `test-driven-development` as
  sections of `/build`; variant B is calling its skills from `/spec`, `/plan`, `/review`.
  Decide per machine profile or once for the plugin.
- **Path guard rewrite** (second analysis §6.7): down to about 250 lines — deny secrets,
  write-deny on `.ai/state`, `events.jsonl`, `questions.md`; reads always allowed; no `sh -c` /
  `eval` segmentation; commands over 4 KB refused with one sentence; `task_protected_patterns`
  only for `.ai/policies` and `.claude/settings*.json`. This intent keeps the rewrite in the
  optional phase 3; the second analysis puts it in phase 3 too but as a must, with the
  characterization suite as the net for the deny decisions that remain. T-2026-10-22-002 is
  the interim fix on the current engine.
- **T0–T6 labels**: keep as an output label for report compatibility, or only the three mode
  words with a T-label in the journal for one version (second analysis' proposal).
- **Team profile and abrites-staging-v2**: nobody on either machine uses the team profile
  (proposal: documented, not tested on every run); abrites-staging-v2's pre-plugin `ai-tools`
  branch with six own guards: `--adopt` or abandon.

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

## Second analysis: the production machine (Claude Doc, 2026-10-24)

Source: "claude-agentic — анализ и опростяване (2026-10-24)", https://claude.ai/artifact/UqxcHvZhP1Nn7xaLhnkiDm
(tab `cd0cf1fc-6d89`, rev 13, about 58 KB; Export → Markdown gives the same text). It analyses
the plugin at commit `bb7d54f` (main, 2026-10-22) as installed on the other machine, with the
projects there: abrites-site-v2 (+ worktrees), abrites-staging-v2, new-shop-2019-v1-replica,
oroCRM, oddoAbries, ArgoCD, and the plugin itself. Local `main` since `bb7d54f` holds only this
intent and the first analysis (`e87e240`, `1b28852`, `c2a6bd7`); `new-refactor` has `main`
merged and carries the open task T-2026-10-22-002.

**Reference archive.** The doc's appendix D names `claude-agentic-bundle-2026-10-24.tar.gz`
(1.4 MB; also `.zip`, 2.0 MB) at `/Store/Claude Plugins/` on the other machine: a `git archive`
of the repo at `bb7d54f` (794 tracked files, no `*.log` under `.ai/reports/`), `evidence/events/`
with the 65 journals as `<project>__<task-id>.jsonl`, `evidence/journals.py`, `triggers.py`,
`scan_transcripts.py` (the scripts behind the numbers; the third runs only there),
`evidence/usage-report.txt`, `installed/profile.json` and `routing.md`, and a README. **It is
not on this machine** (searched the whole filesystem on 2026-10-24); copy it before the spec
needs to re-run the journal numbers, or re-run `tools/journal-summary.py` on the originals.

**Numbers that change the picture** (all measured; method and limits in the doc's appendix A):

| What | Measured |
|---|---|
| Procedure read before the first edit | ≈ 22 200 tokens: `ai-task/SKILL.md` 8 067, `risk-tiers.json` 6 406, `review-economy.md` 2 710, `routing.md` 1 692, `testing.md` 1 574, global `CLAUDE.md` 1 295 (every turn), … |
| Tasks with a journal | 65 in 7 roots, 61 closed; T2 38 %, T3 15 %, T4 34 %, T5 6 %, T6 3 % |
| Human stops | 185 (130 questions + 55 gates); T4 median 5.6 per task, T2 0; T3/T4 is the line between "runs" and "waits" |
| Tier raises | 18: 10 over the line/file budget, 4 scope pipeline (CLAUDE.md, policies), 3 scope migrations (same enum fixture three times), 1 scope auth (a font in `login.html.twig`) |
| Scope changes | 31; the file-level plan is almost always incomplete at step 1 |
| Test runs | 34 of 44 tasks ran the suite more than once; max 5 suite + 5 e2e in one task; one plugin run is 4–5 min |
| Reviews | 47 review reports, 76 ledgers, 19 security reports, 22 plan reviews |
| Refused tool calls / plan mode / compactions | ≈ 1 100 / ≈ 1 480 / ≈ 1 100 occurrences in transcripts |
| Cost (list-price equivalent, 11 weeks) | $4 609 Claude + $85 Codex (2 %); Opus 83 %, of it 99.6 % cache-read; plugin self-maintenance 11 %; from pipeline adoption on 2026-09-23 the median day went from under $47 to ≈ $200 |
| Hook latency (median of 5) | path-guard 36–41 ms, git-guard 16, scope-guard 19, cap-large-read 22, runtime-gate 38, context-guard 31; a 20 KB `sh -c` line 1 645 ms |
| Plugin inventory | 14 commands, 22 agents per runtime (+21/+18 `.bak`), 10 hooks, 30 `state.py` subcommands (2 812 lines), `sensors.py` 1 592, path guard 1 135, runtime-gate 1 265, `risk-tiers.json` 629 lines; 24 010 source lines; 29 test suites |
| Open tasks keeping guards armed | 4: ArgoCD (since 09-14, 551 h), oroCRM 09-30-002, abrites-site-v2 10-22-001 (T6 for a SQL-dump init), this repo 10-22-002 |

**Diagnosis in one line each** (doc §4): ceremony scales on the wrong variable (paths and
size, not weight); "take the higher" + floors + rescore systematically over-classify; three
mandatory process systems contradict each other; the surface confuses the human; the pipeline
does not obey its own test and review rules (a rule the model ignores under 22 000 tokens needs
to be a script); context is the cost and the plugin adds to it; the dual runtime doubles
everything for 2 % of use; the path guard is a tripwire at sandbox price.

**What it takes from skills.addy.ie** (doc §5): phase-named commands, SKILL.md ≤ 300 lines of
steps only, policies as references read on demand, a thin `/task` instead of a 662-line
conductor and a manager persona, descriptions ≤ 1 024 characters, scripts with ≤ 20 lines of
output for status / weight / sensors / release summary, `weight.json` ≤ 80 lines +
`docs/weight.md`, human checkpoints only at plan → build (full) and at `/ship`, fan-out only in
`/ship` for full. Not taken: addy has no risk model and no state; the weight and a thin
`current.json` + journal stay, and `/spec` is optional here.

**Its proposal in full** (doc §6; the open questions above record where it differs from this
intent):

- Nine commands + one: `/setup [--update|--adopt|--light]`, `/spec`, `/plan`, `/build [--mode]`,
  `/test`, `/review`, `/ship`, `/status`, `/cost [--task|--value]`, and `/task <request>` =
  plan → build → test → review → ship with the mode from the weight. Old names stay as aliases
  for one release; a 60-line `using-claude-agentic` replaces `manager.md` and the routing in
  `AGENTS.md`.
- Weight = six axes × 0–2, first four as deterministic as possible (`weight.py`), last two by
  the model with one line of reasoning each. Modes quick / plan / full, plus "full +
  irreversible" (the current T6 confirmation). `--mode` overrides everything and is journaled
  with `--by`.
- Fewer stops: one pause per mode; solo approval is a chat answer, `approve` outside the agent
  only for team and `AI_UNATTENDED`; sensors first, then one full + one scoped review as a rule
  in `/review`.
- Removals (doc §6.4): the sdlc-* and project-init commands as separate entries, `diff_budget`
  and size sensors, path floors, the two shim hooks, seven stale agents and 39 `.bak` files,
  agents `ai-context`, `ai-indexer`, `ai-risk`, `ai-planner`, `ai-release`, `ai-tester`,
  `ai-expert` (7 of 22 remain: Explore, log-reader, ai-discovery, ai-implementer on request,
  ai-reviewer, ai-security, architect), `state.py` 30 → ≈ 10 subcommands, `review-economy.md`,
  `tooling.md`, `context-management.md` out of the per-task reading list.
- Context diet (§6.5): global block ≤ 1 KB (now 5.2 KB with the personal rules), project block
  ≤ 0.8 KB, `/setup --update` warns on `CLAUDE.md`/`AGENTS.md` over 4 KB (ArgoCD 45 KB,
  new-shop 22 KB), `/task` suggests a 200k session for quick/plan.
- Guards (§6.7): git-guard, scope-guard (project paths only; plan mode scope = the whole
  task's files), cap-large-read and context-guard stay; path guard rewritten to ≈ 250 lines;
  runtime-gate keeps only the outage reroute. The README's known risks stay true after the
  rewrite.
- Rollout (§7): phase 1 "stop the bleeding" 1–2 days (`max_suite_runs` 2, size gating off,
  floors → hints, delete stale agents / `.bak` / shims, `/status` as a script, aliases); phase
  2 new surface, one week; phase 3 cleaning (path guard, agents 22 → 7, reports out of git,
  migration 0007 `risk-tiers.json` → `weight.json`), one week. Seven metrics with targets:
  procedure tokens ≤ 6 000, stops quick/plan 0 and full 2, one suite run (two with
  remediation), STRONG reviews ≈ 15 %, refused tool calls < 0.3 per 100 and none on reads,
  self-maintenance < 5 %, plan-task median < 1 h.

**Re-classification of real tasks under the six axes** (doc §6.2), the test cases the spec
must keep: font in `login.html.twig` T3→T4 becomes quick; Odoo VAT module 401 lines T4→T5
becomes full by domain, not by lines; oroCRM enum fixture T4→T5×3 becomes plan; 1 733-line
generated DDL in a test fixture T2→T5 becomes quick; the path-guard regex fix
(T-2026-10-21-001, 21 h, 6 questions) becomes plan; migration 0006 deleting user `.ai/` files
stays full + irreversible; an ArgoCD manifest in `env/dev` T6 becomes plan (`env/prod` + secret
→ full); a project `CLAUDE.md` T2→T3 becomes quick.

## How to resume

1. Read `docs/redesign-analysis-2026-10-24.md` (sections 1, 2a and 3; 4 for phasing) and the
   Claude Doc's §4–§8 (the link above; read it through the Claude Docs connector, not by fetch).
   Fetch `claude-agentic-bundle-2026-10-24.tar.gz` from the other machine if the journals there
   are needed again.
2. Check `/ai-status` and `git log` for the state of direct-mode-diet tasks 2–4.
3. `/sdlc-spec docs/sdlc/intent/claude-agentic-redesign.md` to turn this into a spec, or
   `/ai-task` for phase 1 once the diet is closed.
4. `tools/journal-summary.py <project-root> [--timeline T-…]` reproduces every journal
   number quoted in the analysis, for this repository and for `/Store/Projects/new-shop-2019`.
