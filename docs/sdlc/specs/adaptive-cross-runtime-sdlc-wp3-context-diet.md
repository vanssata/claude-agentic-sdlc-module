# Spec: WP3 — Context diet

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work-package table, row 3)

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Depends on **WP1** (schema version `.ai/VERSION`, ordered idempotent migrations inside the
dry run, template history following renames — closed, PR #15/#16) and **WP2** (questions
file, `handoff.md`, `events.jsonl`, `owner_runtime`, approval outside the agent — closed,
PR #22). **WP6** (`project-update --adopt`) consumes this spec's interfaces; see I11.

Recommended tier: **T3** (the intent says T2–T3; see I10 for the trigger).

Tags used below: **CD1/CD2/CD3** are the three "Context diet" bullets of the intent,
**P2** is Problem 2, **EX** the "Existing projects" outcome, **C-…** a Constraint,
**OOS** the out-of-scope line that makes Gemini/Junie/Cursor stub-only.

## Requirements

| # | Requirement (testable) | Satisfies |
|---|---|---|
| R1 | Every always-loaded instruction file the plugin writes — the global `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` managed blocks, and the project `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `.junie/guidelines.md` (block and skeleton) — is rendered from **one** source, `instructions/stub.md`, by `skills/project-update/render_instructions.py`. No other file in the repository contains stub prose. | CD1, P2 |
| R2 | The committed project templates (`skills/ai-init/templates/*.block.md`, `*.minimal.md`, `skills/project-init/templates/{CLAUDE,AGENTS,GEMINI,junie-guidelines}.md`) are byte-equal to `render_instructions.py build` output. `build --check` exits 1 and names the drifted file otherwise. | CD1 |
| R3 | Hard budgets in the suite: a project managed block ≤ 2 048 B; a freshly scaffolded project instruction file (skeleton + block, project name `proj`) ≤ 2 048 B; a global managed block ≤ 2 560 B for every plan / fable / codex-plan combination the install tests already enumerate. Exceeding one fails `tests/test-instruction-budget.sh`. | CD1 |
| R4 | The budget is measured on **rendered output** — the bytes between `<!-- claude-agentic:start -->` and `<!-- claude-agentic:end -->`, plus the whole file for R3's second clause. The user's own global file is never measured for pass/fail: `install.sh` prints one size line, and for Codex one advisory line above 16 KiB (half of Codex's 32 KiB project-doc limit). No exit code, no edit outside the block. | CD1, C-plugin-owned |
| R5 | The stub alone keeps an agent safe. It names: production behaviour as the source of truth; `/ai-task` and `.ai/AGENTS.md`; the scope rule and `SCOPE_CHANGE_REQUIRED`; no commit / push / merge / deploy and approval outside the agent; verify before done, once, to the end, one batch; the context rules in one bullet; tiers not model names in one bullet; and where the rest lives. Proof: a phrase checklist in the budget test. | CD1 |
| R6 | `instructions/stub.md` names no concrete model (`haiku\|sonnet\|opus\|fable\|gpt-\|terra\|sol\|astra`); tiers only. `instructions/routing.md` (rendered, loaded on demand) may still carry today's literal tier table — WP5 replaces those with profile placeholders and owns the repo-wide grep. | C-abstract-tiers |
| R7 | `.ai/AGENTS.md` is a router: a numbered **Non-negotiable** list of ≤ 7 lines, a `\| Doing \| Read \|` table whose every `Read` cell is a path that exists in the scaffold or a skill name, and one closing section. No pipeline diagram — that lives only in `skills/ai-task/SKILL.md`. Test: every path in the table exists after `scaffold-ai.sh`. | CD2 |
| R8 | Rules that leave `.ai/AGENTS.md` land in an existing policy (`safety.md` already carries the scope rule and the evidence labels; `tooling.md` and `context-management.md` carry tools and large files). WP3 creates no new policy file and deletes none. | CD2 |
| R9 | `.ai/rules/<slug>.md` (frontmatter `dirs:` required, `paths:` optional) is the one source of per-directory rules. `update.py` renders it into `<dir>/CLAUDE.md` and `<dir>/AGENTS.md` managed blocks for the runtimes the project declares, and into `.claude/rules/<slug>.md` when `paths:` is set and Claude is declared. The round trip is idempotent, text outside the markers survives, and a rendered copy whose source is gone becomes a `delete?` proposal (WP1's gate). | CD2, C-parity |
| R10 | `docs/sdlc/constitution.md` is scaffolded from `skills/project-init/templates/constitution.md` with kind `create` (never overwritten): lines `C<n>. …`, five plugin defaults prefilled, slots to 15. `render_instructions.py constitution FILE` exits 1 above 15 principles or 4 096 B — hard for the shipped template (test), advisory for a project (`update.py` dry run and `/ai-status`). | CD3 |
| R11 | `/sdlc-spec` step 2 reads the constitution first and cites `C<n>` in Policy conformance; `agents/ai-planner.md` gains it in "Read first" and each step's risks cite the `C<n>` it touches. Both print `constitution: none (docs/sdlc/constitution.md absent — /project-update creates it)` when it is absent, and continue. Neither injects it anywhere else. | CD3 |
| R12 | Migration `skills/project-update/migrations/0003_context_diet.py` (`VERSION = 3`, `MOVES = []`) removes the verbatim shipped `## SDLC workflow` section from each present root instruction file (the original kept under `.ai/reports/project-update-<date>/original/`), hints on an edited managed block, is idempotent, mentions neither "claude" nor "codex", and never holds `.ai/VERSION`. Fixture: `tests/fixtures/project-update/schema-v2/`. | EX, C-update-guarantees |
| R13 | A managed block hand-edited inside the markers is never overwritten: today's `block_update` conflict path applies (project file kept, plugin stub in `.ai/local/plugin-update/<file>`), listed on every run, plus a permanent hint naming the byte count and the fix. | C-no-overwrite |
| R14 | `GEMINI.md` and `.junie/guidelines.md` receive a block and a skeleton only — no `.gemini/` or `.junie/` runtime layer, no skills, no hooks. They are detected by file/directory presence in `scaffold-ai.sh`, `hooks/project-scaffold.sh` and `update.py`; `--runtime` accepts a comma list (`claude,codex,gemini,junie`; `both` stays `claude,codex`). Claude-only, Codex-only and dual fixtures reach schema 3 identically. | OOS, C-parity |
| R15 | `hooks/ai-path-guard-defaults.json` `task_protected_patterns` gains `.ai/rules/`, `.claude/rules/` and `docs/sdlc/constitution.md`. The `WHY_*` texts are unchanged and the characterization golden changes only by added records. | C-guard-rules-stay |
| R16 | Every new check is stdlib Python or bash; nothing in WP3 spawns a model; `tests/run-all.sh` stays green with the amendments in I8. The budget test builds its scratch project under a path containing a space. | C-deterministic |
| R17 | The long-form global guidance leaves the stub for `$CLAUDE_DIR/claude-agentic/routing.md` and `$CODEX_DIR/claude-agentic/routing.md`, rendered from `instructions/routing.md` at install time, per plan. Install dry runs print it; the existing assertions on plan-specific text move to that file. | P2 |

## Design

### Current state (measured, 2026-09-20)

- `install.sh:114-124` `render()` substitutes `{{X}}` from `RENDER_X`. `:296-300` renders
  `CLAUDE.snippet.md` (6 794 B, 48 lines); `:743-763` renders `AGENTS.snippet.md`
  (10 321 B, 75 lines). `:427-464` `managed_block` replaces the block wholesale and
  migrates a predecessor's block and an unmarked legacy section (`:441-450`). `:587-589`
  and `:852-853` write the two global files. Installed today: `~/.claude/CLAUDE.md`
  is 8 457 B, essentially all block.
- `skills/ai-init/scaffold-ai.sh:81-96` builds the skeleton from `*.minimal.md`
  (`{{PROJECT}}` via `sed`) and appends `*.block.md` once; `:43-54` is
  `--runtime auto|claude|codex|both`. `hooks/project-scaffold.sh:73-95` writes
  `skills/project-init/templates/CLAUDE.md` / `AGENTS.md`, each carrying a
  `## SDLC workflow` section that duplicates the block — so a fresh project's
  instruction file is ≈ 2.4 KB before a human writes a word.
- `skills/project-update/update.py:51-67` holds `PROJECT_INIT_MAP`, `RUNTIME_MAP` and
  `INSTRUCTION_FILE` for two runtimes; `:81-84` `project_runtimes` detects by file or
  directory; `:548-580` `block_update` is absent → append, shipped → replace, edited →
  three-way merge, unmergeable → `conflict` with `conflict_copy`; `:599-664` `build_plan`
  runs migrations, holds the version only for items with `migration is not None`
  (`:625-637`), walks project-init only when `docs/sdlc/` exists, then walks `.ai/`.
- `skills/ai-init/templates/.ai/AGENTS.md` (4 792 B, 102 lines) repeats
  `policies/safety.md` (the rule `:6-27`, scope `:29-44`, evidence labels `:46-59`) and
  parts of `tooling.md` / `context-management.md`, and carries the stage diagram that
  `skills/ai-task/SKILL.md:149-361` already owns. The template tree is 54 files,
  2 801 lines.
- Suites that grep stub content, and therefore constrain the diet:
  `tests/test-install-dry-run.sh:29,41,47,141-143,155,158`,
  `tests/test-codex-install.sh:45-46,118-120`, `tests/test-fable-gate.sh:248,254`,
  `tests/test-project-update.sh:91,134`, `tests/test-scaffold-idempotency.sh:82`,
  `tests/test-merge-migration.sh:64`. Migrations are grepped for `claude|codex`
  (`test-project-update.sh:374`). A path containing a space is already a test concern
  (`tests/test-ai-task-state.sh:595-599`).
- `hooks/ai-path-guard-defaults.json:38-51` protects `.ai/(policies|workflows|templates)/`
  and `.ai/AGENTS.md` during a task — not `.ai/rules/`, not the constitution.
- No `GEMINI.md` or `.junie` handling exists anywhere except the path guard's dependency
  patterns.

### Components

| Component | Responsibility |
|---|---|
| `instructions/stub.md` | The one source of every always-loaded stub, all scopes and runtimes (I1) |
| `instructions/runtimes.json` | The per-runtime vocabulary the stub interpolates (I1) |
| `instructions/routing.md` | Long-form model ladder, context-guard thresholds, launcher, guard list, Codex spawn rules — global only, on demand; rendered per plan |
| `skills/project-update/render_instructions.py` | Parse, select, substitute, measure, build, rules, constitution check (I5); imported by `update.py`, called by path from `install.sh` |
| `skills/ai-init/templates/*.{block,minimal}.md`, `skills/project-init/templates/*.md` | Committed build artefacts; scaffold mechanics unchanged (R2) |
| `install.sh` | Renders the global blocks and `routing.md` from `$SRC/instructions/`; prints sizes (I6) |
| `skills/ai-init/templates/.ai/AGENTS.md` | The router (I3) |
| `skills/ai-init/templates/.ai/rules/README.md` | The format of per-directory rules; no rule is shipped (I4) |
| `skills/project-init/templates/constitution.md` | The constitution template (I7) |
| `update.py` additions | Four instruction files, `rules_update`, budget and constitution hints (I5, I9) |
| `migrations/0003_context_diet.py` | The one structural change the walk cannot make (I9) |
| `tests/test-instruction-budget.sh` | Proof of R2–R6, R9, R10 (I8) |

### Data flow

1. **Author time.** Edit `instructions/stub.md` → `render_instructions.py build`
   regenerates the eight project templates → `tools/build-template-history.py` → commit.
   `build --check` in the test keeps them honest; `build` refuses to write a template
   that is over budget.
2. **Install time.** `render_instructions.py render --scope global --runtime claude
   --kind block` and `--kind routing` read `RENDER_*` from the environment exactly as
   `render()` does → `managed_block` (unchanged) and `install_file` into
   `$CLAUDE_DIR/claude-agentic/routing.md`; Codex the same into `$CODEX_DIR`. The size
   line is printed from the written file.
3. **Scaffold time.** `project-scaffold.sh` writes the skeleton (now without the SDLC
   section); `scaffold-ai.sh` appends the block. Both from committed templates — no
   renderer call in a scaffolded project. `--runtime` lists split on commas; `auto`
   detects `CLAUDE.md|.claude/`, `AGENTS.md|.codex/`, `GEMINI.md|.gemini/`, `.junie/`.
4. **Update time.** detect version → migrations (0003) → VERSION → project-init walk
   (constitution as `create`) → `.ai/` walk (router replaced or merged, `.ai/rules/README.md`
   created) → `block_update` per declared runtime (now four) → `rules_update` → gitignore
   → hints (per-file budget, constitution cap). Apply is unchanged except that an original
   is copied before any migration edit outside `.ai/`.
5. **Session time.** The stub is all that loads. In an `.ai/` repository the agent reads
   the router, then only the row for what it is doing; `/ai-task` carries the procedure;
   `state.py handoff --print` (WP2) is the resume pointer. Nothing new is injected at
   SessionStart.

### The split of today's stub content

| Today (`CLAUDE.snippet.md` / `AGENTS.snippet.md`) | Stays in the stub | Moves to (on demand) | Dies |
|---|---|---|---|
| Tier table with model names; Codex tier table and trigger lists | one bullet: tiers not names, readers FAST/`low`, STRONG/EXPERT on a named trigger, one at a time, never retried cheaper | `routing.md`; project `.ai/policies/model-routing.md` | — |
| `PLAN_SPECIFIC_ROUTING`, `claude-1m`, `fable-gate`, `codex-model-gate`, `opusplan`, `max_concurrent_threads`, agent-file precedence, "name the agent" | — | `routing.md` (plan-rendered) | — |
| "every agent declares model/effort; forks inherit" | — | `routing.md` | — |
| Context-hygiene intro prose | — | — | dies (rationale) |
| grep first, no unbounded read, never `cat` logs, large file → FAST reader with `file:line`, deterministic tools first | one bullet | `routing.md`; project `context-management.md` | — |
| MCP and tool defaults, `enableAllProjectMcpServers`, `--strict-mcp-config` | — | `routing.md`; project `tooling.md` | — |
| "one subagent returning twenty lines" | — | `routing.md` | — |
| `/clear` (Codex: a new thread) between tasks; compaction is a summary | half a bullet | `routing.md` | — |
| context-guard thresholds, snapshot semantics, "Session state before compaction" | one clause (trust the handoff and the snapshot over the summary) | `routing.md` | — |
| tests once, to the end, one batch | in the verify bullet | — | — |
| `/usage-report` | five words | `routing.md` | — |
| `# Summary instructions` | one bullet, no heading | — | the heading |
| Pipeline intro: entry point, policies binding, production truth | bullets 1–2 | — | — |
| `/ai-task`, tiers, direct vs SDLC, `state.py quick`, the three test scopes, T4/T5 examples, bugfix starts with a failing test, characterization | `/ai-task` and the verify bullet | router non-negotiables; `risk-tiers.json`; `testing.md`; `skills/ai-task/SKILL.md` | globally: dies |
| scope rule, refactor ≠ feature | bullets | — | — |
| "same mistake twice → correction into this file" | project stub only | — | globally: dies |
| guard list (force push, protected branch, `--no-verify`, secrets, deploy); `/hooks` trust; `apply_patch` per file | "a guard's refusal is not a hint"; the Codex trust and `apply_patch` clauses | `routing.md` | — |
| `/ai-init`, `/project-update`, the dual-runtime note, the SDLC flow, artefact paths | `/ai-init` first, `/project-update` after a reinstall | the router; the project-init skeleton's `## Workflow` | the rest, globally |

Projected sizes (hand-counted from the exact drafts in I2; the test is the arbiter):

| Artefact | Today | Projected | Budget |
|---|---|---|---|
| global Claude block (Team Max, longest label) | 6 794 source → 8 457 installed | **1 903** | 2 560 |
| global Codex block (ChatGPT Plus) | 10 321 | **≈ 2 035** | 2 560 |
| project Claude block | 1 835 | **1 107** | 2 048 |
| project Codex block | 2 369 | **1 206** | 2 048 |
| project Gemini / Junie block | — | ≈ 1 100 | 2 048 |
| ai-init skeleton / project-init skeleton | 544 / ≈ 1 000 | ≈ 660 / ≈ 790 | — |
| fresh scaffolded `CLAUDE.md` / `AGENTS.md` (`proj`) | ≈ 2 400 | ≈ 1 900 / ≈ 2 000 | 2 048 |
| `.ai/AGENTS.md` router | 4 792 | ≈ 2 400 | advisory 4 096 |

The Codex fresh file lands within ~50 B of its budget; the skeleton's `## Verification`
comment is the trim point if the real count comes in high.

### Alternatives rejected

1. **Structured data (JSON/YAML) plus per-runtime renderers.** Prose inside a data file is
   unreadable in review and in diffs, and two renderers drift. One markdown file with
   comment directives keeps the source readable as markdown and the renderer under 200 lines.
2. **A conditional mini-language inside `install.sh`'s `render()`** (`{{#if codex}}`). That
   adds a template language to a bash function also used for agent files; the
   directive-per-line form needs no parser state beyond "the current selector".
3. **Rendering project stubs at scaffold and update time, with no committed templates.**
   `block_update`'s merge and `history/index.json` depend on shipped versions being files;
   rendering would need a history of rendered outputs — a second history. Committed
   artefacts plus a drift check leave WP1's machinery untouched.
4. **`@`-importing `routing.md` from the stub.** Claude Code would load it every turn, which
   is the problem being solved.
5. **Holding `.ai/VERSION` on an edited managed block.** It would block every later migration
   (WP4's diff budgets, WP5's tables) on a cosmetic conflict in a file outside `.ai/`. A fat
   block is safe, only large. A permanent hint, the `/ai-status` line and WP6's adopt are
   the path out.
6. **Hand-kept nested `CLAUDE.md` / `AGENTS.md`, no `.ai/rules/`.** Two hand-kept copies break
   parity; source-plus-render is what the agent files already do (`scripts/render-codex-agents.py`).
7. **The constitution under `.ai/`.** The intent fixes `docs/sdlc/`; it is a human document
   read by `/sdlc-spec`, which works in a repository with no `.ai/`.
8. **Global `GEMINI.md` / `.junie` stubs written by `install.sh`.** The installer targets
   runtimes it can detect and configure; those two get project-level stubs only, which is
   what "a rendered stub and the prose questionnaire" means.

### Implementation order

Each item is one `/ai-task` step naming its own files; the full suite runs once at the end.

1. **Refactor, byte-identical.** `render_instructions.py` (`render` only) and
   `instructions/stub.md` holding today's two snippets verbatim under
   `scope=global runtime=claude|codex` directives; `install.sh:296-300,743-763` call it.
   Proof: `tests/run-all.sh` green unchanged, plus a temporary `cmp` of the old `render()`
   output against the new one, removed at step 3.
2. **`build` and the drift check.** Today's block, minimal and project-init skeletons
   regenerated byte-identically from the source; `tests/test-instruction-budget.sh` with
   only the drift assertion; added to `run-all.sh`. Proof: `build --check` exit 0, history
   test green.
3. **The diet.** New `stub.md`, `routing.md`, `runtimes.json`; regenerated templates; the
   budget assertions switched on; the test amendments of I8. `CLAUDE.snippet.md` and
   `AGENTS.snippet.md` are deleted here.
4. **Router and constitution.** `.ai/AGENTS.md` (I3), `.ai/rules/README.md`,
   `constitution.md` template plus `PROJECT_INIT_MAP` and the `project-scaffold.sh` entry,
   `skills/ai-task/SKILL.md` §1 gains the stage diagram and the evidence-label pointer,
   `skills/sdlc-spec/SKILL.md`, `skills/sdlc-plan/SKILL.md`, `agents/ai-planner.md`,
   `skills/ai-init/SKILL.md` step 4 (fill C6+ from the survey); rebuild the history.
5. **Four runtimes.** `INSTRUCTION_FILE` / `RUNTIME_MAP` / `project_runtimes`, both
   scaffolds' `--runtime`, the Gemini and Junie templates; scaffold and update tests.
6. **Migration 0003** plus the `MigrationContext` helpers, originals for edits outside
   `.ai/`, the `schema-v2` fixture and its tests (I9).
7. **Rules rendering** (`rules_update`, `delete?` for a stale copy) plus a fixture; the path
   guard patterns with fixtures and an additive golden re-record.
8. **Reporting and docs.** `install.sh` size lines, the `/ai-status` budget line, `update.py`
   hints, `README.md`, `docs/faq.md`, `docs/hooks.md`, `skills/project-update/SKILL.md`
   ("Writing a migration" gains the new helpers).
9. `tests/run-all.sh` once (it contains `test-end-to-end.sh`).

## Interfaces

### I1 `instructions/stub.md` and `instructions/runtimes.json`

Directive line: `<!-- stub: scope=global,project runtime=claude,codex -->`, with
`scope` ∈ `global|project|skeleton|skeleton-sdlc` and `runtime` ∈ `claude|codex|gemini|junie|*`.
**A directive covers the lines that follow it until the next directive line or a blank
line**; a group with no directive is selected everywhere. Directive lines are removed,
three or more newlines collapse to two, and `--kind block` wraps the output in the
`claude-agentic:start` / `end` markers. `{{X}}` resolves from `runtimes.json` first
(`FILE`, `HOME`, `RUNTIME_NAME`, `NEW_CONTEXT`, `MULTI_EDIT`, `TRUST`, `NOTES_DIR`), then
from `RENDER_X` / `--var K=V` (`PLAN_LABEL`, `READ_LINES`, …). An unresolved `{{` is exit 1
with the line number.

```json
{"claude": {"FILE": "CLAUDE.md", "HOME": "~/.claude", "RUNTIME_NAME": "Claude Code",
            "NEW_CONTEXT": "`/clear`", "MULTI_EDIT": "", "TRUST": "",
            "NOTES_DIR": ".claude/memory/"},
 "codex":  {"FILE": "AGENTS.md", "HOME": "~/.codex", "RUNTIME_NAME": "Codex",
            "NEW_CONTEXT": "a new thread",
            "MULTI_EDIT": " One `apply_patch` is checked file by file: a patch that reaches outside the step is refused whole.",
            "TRUST": " Run `/hooks` once after installing to trust the guards, or they are skipped.",
            "NOTES_DIR": ".codex/memory/"},
 "gemini": {"FILE": "GEMINI.md", "HOME": "~/.gemini", "RUNTIME_NAME": "Gemini", "…": "…"},
 "junie":  {"FILE": ".junie/guidelines.md", "HOME": "~/.junie", "RUNTIME_NAME": "Junie", "…": "…"}}
```

### I2 The rendered stubs

Exact text; the byte counts in the Design section are of these. Global, Claude
(`scope=global runtime=claude`). Codex swaps `HOME` and `NEW_CONTEXT`, appends
`MULTI_EDIT` to bullet 3 and `TRUST` to bullet 4, and drops the "Session state" clause,
which is Claude-only (WP2).

```
<!-- claude-agentic:start -->
# claude-agentic ({{PLAN_LABEL}} plan)

Rules for every repository; everything else loads on demand. `{{HOME}}/claude-agentic/routing.md` has the model ladder, the context-guard thresholds and the launcher; a project's `.ai/AGENTS.md` routes to its policies.

- With `.ai/`: read `.ai/AGENTS.md` first, run every change through `/ai-task <request>`, treat `.ai/policies/` as binding; `/project-update` after a plugin reinstall. Without `.ai/`: `/ai-init` first.
- Production behaviour is the source of truth: document problems outside the task, do not fix them. Never mix a refactoring with a feature change.
- Each step names the files it may touch; an edit outside them is refused — answer `SCOPE_CHANGE_REQUIRED`, do not widen the step.{{MULTI_EDIT}}
- No agent commits, pushes, merges or deploys; the pipeline ends at human approval, given outside the agent. A guard's refusal is not a hint to reword.{{TRUST}}
- Verify before reporting done: the verification command once, to the end, every failure fixed as one batch, output shown.
- Context: `grep -n`, then read the hits; never `cat` logs, lockfiles or generated code; a file over ~{{READ_LINES}} lines is read by a FAST reader (`Explore`, `log-reader`) that returns `file:line` excerpts, never the file. Deterministic tools first. {{NEW_CONTEXT}} between tasks. `/usage-report` shows where tokens went.
- Models are tiers, not names: readers and runners on FAST at `low`; the session implements; STRONG and EXPERT only on a named trigger, one agent at a time, never a fleet on the top tier; a failed thinking task is never retried on a cheaper model.
- On compaction keep decisions and their reasons, rejected options, exact paths and names, failed attempts with the error text, open questions and the latest instruction verbatim; trust `.ai/state/handoff.md` and the guard's "Session state before compaction" over the summary.
<!-- claude-agentic:end -->
```

Project block (`scope=project`). Gemini and Junie replace bullet 2 with: "Changes run
through the pipeline (`/ai-task` in Claude Code or Codex); without it, follow
`.ai/policies/safety.md`, touch only the files the current task names, and answer questions
in prose or by filling the file."

```
<!-- claude-agentic:start -->
## AI agent workflow

This repository runs an agentic pipeline under `.ai/`. Read `.ai/AGENTS.md` first: it routes to the policies, workflows and rules, which load on demand; `.ai/policies/` is binding.

- Production behaviour is the source of truth: document problems outside the task, do not fix them.
- A change runs through `/ai-task <request>`; `/ai-status` shows where it stands. Each step names the files it may touch — an edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED`.{{MULTI_EDIT}}
- Verify before reporting done: `verify_command` from `.ai/policies/testing.md` once, to the end, then `e2e_command` once; every failure fixed as one batch; show the output.
- No agent commits, merges or deploys; approval is given by a human outside the agent. When a review flags the same mistake twice, the correction goes into this file.
- Files, not chat, carry decisions: `.ai/reports/<task-id>/questions.md` (answer by filling `[Answer]:`), `.ai/state/handoff.md` (read first when resuming), `docs/sdlc/constitution.md` (this project's principles).
<!-- claude-agentic:end -->
```

Skeleton (`scope=skeleton`, shared by ai-init's `*.minimal.md` and, with the extra
`## Workflow` section under `scope=skeleton-sdlc`, by project-init): `# {{PROJECT}}`, one
comment, then `## Commands`, `## Verification`, `## Conventions`, `## Architecture`,
`## Things {{RUNTIME_NAME}} gets wrong`, each with its one-line comment. `## Workflow` is
"`/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan` → `/ai-task`; artefacts in `docs/sdlc/`. Run
`/ai-init` if there is no `.ai/`." `{{PROJECT}}` substitution stays the scripts' `sed` /
`replace`.

### I3 `.ai/AGENTS.md` — the router

```
# How agents work in this repository
<one paragraph: one .ai/ tree for both runtimes, one task state; read the row for what you are doing>

## Non-negotiable (read even if you read nothing else)
1. Production behaviour is the source of truth …
2. /ai-task; each step names its files; SCOPE_CHANGE_REQUIRED
3. No commit / push / merge / deploy; approval outside the agent
4. Verify once, to the end, every failure as one batch
5. Refactoring ≠ feature; legacy without a test gets a characterization test first
6. Evidence labels in project/
7. docs/sdlc/constitution.md is this project's own list; cite C<n>

## Doing X → read Y
| Doing | Read |
| anything, first | `policies/safety.md` |
| starting or resuming a task | `state.py handoff --print`, then the `/ai-task` skill |
| deciding the tier, who reviews, what a human approves | `policies/risk-tiers.json` (`risk-tiers.md` mirrors it) |
| choosing an agent or a tier | `policies/model-routing.md`, `policies/review-economy.md` |
| a large file, logs, a tool or MCP server | `policies/context-management.md`, `policies/tooling.md` |
| writing code under `<dir>/` | `policies/coding.md`; `rules/<slug>.md` for that directory |
| tests | `policies/testing.md` — Verification: the three commands |
| schema, data, migrations | `policies/database.md`, `policies/production.md` |
| auth, secrets, personal data, payments | `policies/security.md` |
| git, release | `policies/git.md`, `policies/release.md` |
| feature / bugfix / refactoring / hotfix / investigation | `workflows/<kind>.md` |
| acting as a role | `agents/<role>.md`; the manager is `agents/manager.md` |
| an artefact | `templates/<artefact>.md` → `reports/<task-id>/` |
| understanding the system | `project/overview.md`, then `project/*.md` |
| principles, intent, spec, plan, decisions | `docs/sdlc/constitution.md`, `docs/sdlc/{intent,specs,plans,adr}/` |
| the project is behind the plugin | `/project-update` (`VERSION` is this tree's schema) |

## Keeping this directory true   <two sentences, as today>
```

A row is `| <situation, verb first> | <path or skill, comma-separated> |`; the test
resolves every backticked path against the scaffold. WP6 appends rows in the same form
for adopted content.

### I4 `.ai/rules/<slug>.md`

```
---
dirs: [src/Payment, tests/Payment]      # required: nested CLAUDE.md / AGENTS.md managed blocks
paths: ["src/Payment/**"]               # optional: also .claude/rules/<slug>.md (Claude path-scoped)
---
# Payment rules
- …
```

The rendered block is `<!-- claude-agentic:rule:payment:start -->` … `:end` inside
`<dir>/CLAUDE.md` (runtime `claude`) and `<dir>/AGENTS.md` (`codex`), created if absent.
`.claude/rules/payment.md` is the frontmatter `paths:` plus the body, with the first line
`<!-- generated from .ai/rules/payment.md by /project-update — edit that file -->`. Only
files whose slug has a source are managed; a removed source yields
`delete? <file> [rules] source .ai/rules/<slug>.md is gone`.

### I5 `render_instructions.py` CLI

Standard library only; never shells out.

```
render_instructions.py render  --scope global|project|skeleton|skeleton-sdlc --runtime R --kind block|skeleton|routing
                               [--source DIR] [--var K=V …] [--out FILE]      # RENDER_* env honoured
render_instructions.py build   [--check] [--source DIR] [--templates DIR] [--project-init DIR]
render_instructions.py measure FILE… [--block|--whole] [--budget BYTES]       # prints "<file> <kind> N B"; exit 1 over budget
render_instructions.py constitution FILE [--max-lines 15] [--max-bytes 4096]
```

Exit codes: 0 ok, 1 drift / over budget / unresolved placeholder, 2 usage. `update.py`
imports it for `measure`, `rules` and `constitution`; `install.sh` calls it by path from
`$SRC`.

### I6 `install.sh`

`render_claude_files` and `codex_render` call `render … --kind block` and `--kind routing`.
The dry runs print the block, then `== routing.md (on demand):` and the file. Apply adds
`mkdir -p "$CLAUDE_DIR/claude-agentic"` and `install_file "$TMP/routing.md"
"$CLAUDE_DIR/claude-agentic/routing.md"` (Codex likewise), and after `managed_block`:

```
CLAUDE.md: managed block 1 903 B (budget 2 560), file 8 457 B — the rest is yours
```

Codex adds, only above 16 KiB: `AGENTS.md is 34 120 B; Codex reads at most 32 KiB of
project docs — consider a project .ai/`. No new flags.

### I7 `docs/sdlc/constitution.md`

```
# Constitution — {{PROJECT}}
<!-- The 10–15 principles this project does not negotiate, one line each, numbered C1…;
     /sdlc-spec and the planner cite them. Under 15: what is not here lives in .ai/policies/. -->
C1. Production behaviour is the source of truth; what looks wrong may be load-bearing.
C2. A bugfix starts with the failing test; legacy behaviour gets a characterization test before it changes.
C3. A refactoring changes no behaviour and is never mixed with a feature.
C4. Every step names its files; scope grows only by amending the plan.
C5. No agent commits, merges or deploys; a human approves outside the agent.
C6. <!-- project principle — filled by /ai-init from the survey, confirmed by you -->
…C10 slots
```

### I8 `tests/test-instruction-budget.sh` and the amendments

Sections, in order: `build --check`; the project block `measure --block ≤ 2048` per
runtime; a scaffold into `"$TMP/with space/proj"` with `--runtime claude,codex,gemini,junie`
→ `wc -c < "$file"` ≤ 2048 per file and the R5 phrase checklist; real installs into
`"$TMP/with space/claude"` and `…/codex` for `max yes`, `max no`, `pro`, `team-max yes`,
`team-pro`, `--codex-plan plus|pro` → the bytes between the markers ≤ 2560 and `routing.md`
present (a dry run is not enough: the blocks carry plan values); a fixture
`~/.claude/CLAUDE.md` of 20 KiB of user text → the size line is printed, exit 0, the text
outside the block byte-identical; the rules round trip on
`tests/fixtures/instructions/rules-project/`; `constitution` on the shipped template; the
model-name grep on `stub.md`. Failure text:

```
over budget: CLAUDE.md block is 2 301 B, budget 2 048 B (project)
  — trim instructions/stub.md or move the rule to routing.md / a policy
```

Hard fail; `run-all.sh` lists the suite.

Amendments: `test-install-dry-run.sh:29,41,47` stay (the dry run prints `routing.md`, whose
heading keeps `# Model routing ({{PLAN}} plan)`); `:141-142,155,158` grep
`$DIR/claude-agentic/routing.md`; `:143` becomes `grep -q 'On compaction keep' "$DIR/CLAUDE.md"`;
`:88-100`'s list gains `claude-agentic/routing.md` and
`skills/project-update/render_instructions.py`. `test-codex-install.sh:45-46` stay,
`:118-119` grep `$DIR/claude-agentic/routing.md`. `test-fable-gate.sh:248,254` stay.
`test-project-update.sh:91,134` grep `.ai/state/handoff.md` (a v3-only phrase) instead of
`pipeline_profile`. `test-scaffold-idempotency.sh:17-19`'s file count follows the tree;
`:82` and `test-merge-migration.sh:64` stay.

### I9 Migration 0003 and the `MigrationContext` additions

Helpers, additive to WP1's contract: `ctx.instruction_files() -> list[str]` (present files
for the project's runtimes, via `INSTRUCTION_FILE` and `project_runtimes`);
`ctx.shipped(path) -> list[bytes]` (every history version of the template behind a project
path, through `template_targets` / `RETIRED`); `ctx.block_status(path) ->
"none"|"shipped"|"edited"`; `ctx.hint(text)`. `apply` copies an original before any
migration `update` whose target is outside `.ai/`.

```python
VERSION = 3
TITLE = "move the pipeline text out of the instruction files (context diet)"
MOVES = []

def plan(ctx):
    for path in ctx.instruction_files():
        text = ctx.read(path)
        section = _shipped_workflow_section(text, ctx.shipped(path))
        if section:
            ctx.edit_text(path, lambda t: t.replace(section, b"", 1))
        elif b"\n## SDLC workflow" in text:
            ctx.hint("%s: the SDLC workflow section was edited; it duplicates the managed "
                     "block — merge it by hand" % path)
        if ctx.block_status(path) == "edited":
            ctx.hint("%s: the managed block was edited here, so the plugin's stub cannot "
                     "replace it; move your lines below the block and run /project-update "
                     "again" % path)
```

Detects schema 2, a root instruction file carrying the shipped section, and an edited
block. Rewrites the section only, on a verbatim match. Never touches user text elsewhere,
an edited block, or `.ai/AGENTS.md` (the walk merges it; a conflict leaves the router in
`.ai/local/plugin-update/.ai/AGENTS.md`). Never holds `.ai/VERSION` — it produces no
`conflict` and no `delete?` item. Dry-run lines:

```
update CLAUDE.md [0003] SDLC workflow section removed (now in the managed block)
update CLAUDE.md managed block replaced (unchanged since it was installed)
```

Fixture `schema-v2/`: `.ai/VERSION` = `2`, built by a `v2_project()` helper from the oldest
templates for both runtimes, plus a `GEMINI.md` with no block, an `AGENTS.md` with a line
inserted inside the block, and a `.ai/AGENTS.md` with an appended section. Assertions: the
section is gone and the user's notes kept in `CLAUDE.md`; the original is under
`.ai/reports/project-update-*/original/CLAUDE.md`; the `AGENTS.md` block is untouched with
a copy in `.ai/local/plugin-update/AGENTS.md`; the `GEMINI.md` block is appended; VERSION is
`3`; a second run reports `0 automatic, 2 conflict`; `--check` exits 0 with the budget hint.

### I10 Tier

**T3.** Trigger from `skills/ai-init/templates/.ai/policies/risk-tiers.json:220-248`:
`label: shared domain behaviour`, examples `shared services` — `update.py` and `install.sh`
are shared by every project and both runtimes — together with
`characterization_tests: required before changing legacy behaviour` (the existing suites
are that characterization, and step 1 is byte-identical). Precedent: WP1 was T3 for the
same engine, and `skills/ai-task/SKILL.md:86` says to take the higher tier when two are
arguable. T2 would hold only if WP3 changed template text alone; it also adds a migration,
a renderer on the install path, two new instruction-file targets and a guard pattern. No
security review: no auth, no personal data.

### I11 What WP5 and WP6 consume

**WP5**: `instructions/stub.md` is already model-free; `instructions/routing.md` keeps the
literal tier table from `CLAUDE.snippet.md:8-10` and the `{{*_MODEL}}` placeholders from the
Codex snippet. WP5 turns those literals into placeholders fed from the profile tier tables
and scopes its grep to `instructions/stub.md`, `agents/`, `skills/` and `templates/`.

**WP6**: `render_instructions.py render --scope project --runtime R --kind block` writes the
stub that replaces a large hand-written file; `measure` is the acceptance check of the
split; the router row form (I3) is where "doing X → read Y" rows are appended;
`.ai/rules/<slug>.md` (I4) is the destination for `.cursor/rules/*.mdc` globs;
`INSTRUCTION_FILE` names the four targets; `block_status` answers "is this block ours".

## Policy conformance

The repository has no root `CLAUDE.md` or `AGENTS.md` of its own — it *is* the plugin, and
`CLAUDE.snippet.md` / `AGENTS.snippet.md` are what it installs elsewhere. `docs/sdlc/adr/`
is empty, so no accepted ADR binds this spec. The policies below are the user's global
`~/.claude/CLAUDE.md`, the intent's Constraints, and the shipped `.ai/` policy templates
that this work edits.

| Policy | How the design honours it |
|---|---|
| Model routing: readers FAST, implementation in the main session, nothing below T3 on `opus` | WP3 spawns no model at all. Design was done once by `architect` (EXPERT, pinned); implementation is main-session edits with `ai-reviewer` at the tier. |
| Context hygiene: instructions are re-read every turn | This is the whole deliverable: 6 794 + 10 321 B of always-loaded source become ≈ 1 903 + 2 035 B, with the remainder one deliberate read away. |
| New checks are deterministic; a new check replaces a model step | `render_instructions.py`, the budget test and the drift check are stdlib Python and bash. None adds a model step; `build --check` replaces reviewer attention on template drift. |
| Plugin-owned files change only through the skills | Templates become build artefacts of `build`; hand-editing one is caught by `build --check`. The one exception — migration 0003 editing a user-owned root file — is verbatim-only with the original kept (flagged concern 1). |
| `project-update` guarantees: dry run, replace untouched, three-way merge, never overwrite a conflict, a task in flight is asked about | 0003 runs inside the existing dry run and adds no new apply path; R13 keeps the conflict path; the walk is unchanged; `MOVES = []` so the history machinery is untouched. |
| Runtime parity | One source, four render targets; Claude-only, Codex-only and dual fixtures must reach schema 3 identically (R14). Gemini and Junie get stub and prose only, per the intent's out-of-scope line. |
| Abstract tiers in shared prompts | R6; `routing.md` is the only rendered file still naming models, and it is WP5's to convert. |
| Guard rules stay as they are; the characterization golden is byte-stable | R15 adds patterns only; the golden grows by added records and the `WHY_*` texts do not move. |
| Both suites stay green; every migration gets a fixture project | R16, I8, and the `schema-v2` fixture in I9. |
| No agent commits, merges or deploys | Unchanged; the stub keeps the rule as bullet 4, so it survives the diet. |
| A test that touches the repository's own path is run through a path with no space before it is trusted (WP2's lesson) | Inverted and made permanent: the budget test *carries* the space into CI (`"$TMP/with space/…"`), and the renderer never shells out. |

## Flagged concerns

1. **Migration 0003 edits a file the user owns.** "Plugin-owned files change only through
   the skills" implies the converse — a root `CLAUDE.md` is the user's. 0003 deletes a
   section from it. Mitigations: the match is verbatim against a shipped template version,
   the original is copied under `.ai/reports/project-update-<date>/original/`, the step is
   idempotent, and it appears in the dry run before anything is written. Precedent exists
   (`install.sh:441-450` already migrates an unmarked legacy section in the global file).
   **If you would rather not**, the step degrades to a hint and every pre-WP3 project keeps
   ~500 B of duplicated text for ever. Open question 4.
2. **The intent says the global `GEMINI.md` and `.junie/guidelines.md` are stubs rendered
   from one source, and also that those tools are not full runtimes.** Resolved here as
   *project* stubs only — `install.sh` writes no global Gemini or Junie file, because the
   installer targets runtimes it can also configure. The intent's wording should be amended
   to match, or this decision reversed. Open question 2.
3. **A rule that an agent needed outside `/ai-task` may be cut.** The split table accounts
   for every sentence of both snippets and R5 pins eight phrases, but "accounted for" is not
   "still reachable in the moment it is needed". Mitigation: step 3 lands the global stub
   well before step 6 migrates projects, so the new stub is lived with for a while; anything
   missing goes back inside the budget.
4. **The Codex fresh-file projection is within ~50 B of 2 048 B.** If the real count exceeds
   it, the skeleton's `## Verification` comment is trimmed. `build` refuses to write an
   over-budget template, so this cannot land silently — but it may cost a round of trimming
   during implementation.
5. **Hand-edited managed blocks keep the fat stub for ever.** Alternative 5 refuses to hold
   `.ai/VERSION` for them, so those projects still advance to schema 3 while their block
   stays large. A permanent hint, an `/ai-status` line and WP6's adopt are the path out; no
   check forces it. Accepted deliberately — holding the version would block WP4 and WP5
   migrations on a cosmetic conflict.
6. **`test-project-update.sh:102` asserts that `--check` exits 0 when only a hand merge is
   left**, which means an over-budget *project* never fails `--check` — only the plugin's
   own templates are hard-failed. A stricter `--check --budget` is left to WP6. This is a
   real gap between "a test enforces the budget" (the intent's wording) and what a
   downstream project experiences: downstream, the budget is a hint.
7. **Two unverified platform assumptions**, both checked during implementation, both
   degrading safely: that `.claude/rules/*.md` supports `paths:` frontmatter (if not, R9
   loses an optional output; nested `CLAUDE.md` remains the mechanism), and that
   `# Summary instructions` is not a heading Claude Code treats specially (if it is, the
   heading costs 25 B and fits). Open question 6.
8. **Codex's nested `AGENTS.md` loads on the cwd chain, not per touched file.** Parity for
   `.ai/rules/` is therefore parity of *source*, not of loading behaviour: under Codex the
   router row is the on-demand path. This is a genuine behavioural difference between the
   runtimes that the design cannot remove.
9. **Auto-enrolling `GEMINI.md` and `.junie/guidelines.md`** writes a ≈ 1.1 KB block into
   files of teams who may not want it. It is listed in the scaffold output and an explicit
   `--runtime` list overrides `auto`. Open question 2.
10. **Scope size.** Nine steps across `install.sh`, `update.py`, two scaffolds, the template
    tree, the guard defaults and six test suites. Steps 7 (rules rendering) and 5 (Gemini and
    Junie) are the separable ones if the task needs to be cut; the diet itself is steps 1–4
    and 6. Open question 5.

## Open questions

**All settled by the user on 2026-09-20** — every one as specified. Do not re-litigate
them in the plan or in review.

| # | Question | Answer (2026-09-20) | Owner |
|---|---|---|---|
| 1 | Budget semantics: project = managed block ≤ 2 048 B **and** fresh skeleton+block ≤ 2 048 B, both hard; global = block only, hard in the tests, a size line in `install.sh`. Block-only for projects frees ~700 B but lets the skeleton grow back. | **as stated**: block **and** fresh skeleton+block, both hard | settled |
| 2 | Auto-enrol `GEMINI.md` / `.junie/guidelines.md` when present, like `CLAUDE.md` today — or only with an explicit `--runtime gemini,junie`? Explicit means existing Gemini/Junie projects get nothing from `/project-update` until someone passes the flag. | **auto-enrol when present**; explicit `--runtime` overrides | settled |
| 3 | Constitution defaults: ship C1–C5 prefilled from the binding policies, or an empty numbered skeleton? Prefilled means every project cites the same five; empty means an unfilled file until `/ai-init` runs. | **prefilled** C1–C5 | settled |
| 4 | Does 0003 strip the verbatim `## SDLC workflow` section from the user-owned root file (original kept), or only hint? | **strip it**, original kept under `.ai/reports/…/original/` | settled |
| 5 | Is `.ai/rules/` rendering part of WP3 (step 7, separable) or deferred to WP6? Deferring leaves a router row pointing at a format nothing renders. | **in WP3**, step 7 | settled |
| 6 | The compaction rule as a bullet, or kept under a `# Summary instructions` heading? Pending the documentation check in concern 7. | **bullet**, no `# Summary instructions` heading (pending the doc check in concern 7) | settled |
| 7 | Carried from the intent, still open and **not** WP3's: open question 2 of the intent (how "outside the agent" is enforced) was settled in WP2; intent open question 1 (Codex's native question picker) was settled in WP2's spec. Nothing from the intent remains open for WP3. | — | — |
