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

## How to resume

1. Read `docs/redesign-analysis-2026-10-24.md` (sections 1, 2a and 3; 4 for phasing).
2. Check `/ai-status` and `git log` for the state of direct-mode-diet tasks 2–4.
3. `/sdlc-spec docs/sdlc/intent/claude-agentic-redesign.md` to turn this into a spec, or
   `/ai-task` for phase 1 once the diet is closed.
4. `tools/journal-summary.py <project-root> [--timeline T-…]` reproduces every journal
   number quoted in the analysis, for this repository and for `/Store/Projects/new-shop-2019`.
