## RESOLUTION
decision: Revised plan below: 9 steps, no blocking question. The main decisions:
(1) **H1 (router).** The router change becomes an insertion: a prose `## Shared files` section placed before an unchanged `## Doing X → read Y` table. It ships in its own compatible step (Step 6). In 0006, the first planned operation makes the router name the shared tree (create, replace, insert or append). `apply` stops at the first failing item (update.py:1053-1064), so no deletion can land while the router is unwritten. `three_way` treats a router merge that does not have the section exactly once as a conflict.
(2) **Q5=A** is implemented as: `safety.md` and `security.md` stay project-owned (scaffolded, three-way merged, blobs kept). They are not in `ai/` and not in 0006. The shared set is 29 files, not 31.
(3) **H3** is precondition P2 of Step 3.
(4) **M2** is enforced as exit 2 with nothing written when a file 0006 would delete is missing from the local shared tree, or from another installed home of a runtime the project declares.

why_strong_was_insufficient: The previous plan, written by this tier, assumed two things it never tested: a router rewrite merges cleanly into edited or adopted routers, and the frozen Gemini/Junie stub can lose its target. Q5's answer can be read two ways, and only one of them keeps the stub's reason true.

reasoning:
- **Why H1 broke.** The reviewer's `git merge-file` probe shows the failure comes from rewriting the table that adopt appends to. Leaving the table and anchor heading byte-identical removes the overlapping hunk, so edited and adopted routers normally merge.
- **What 0006 adds.** The plugin's own section, the way `block_update` appends the managed block (update.py:665). It does not pattern-match the human's prose, so the router never depends on a clean merge.
- **What gets used instead of holding.** Item ordering plus apply's abort semantics, not holding VERSION. A hold would leave projects at schema 5 indefinitely.
- **Why Q5 must mean project-owned.** `/ai-init` will copy only project-owned files, so "shared but exempt from deletion" gives every new Gemini/Junie project no `safety.md`. That defeats the stated reason for Q5. It would also freeze existing copies (M6).

rejected:
- Holding VERSION on a router conflict: projects get stuck, and the plain-update deletions would need the same guard anyway.
- Replacing the shipped table when it appears verbatim: this is exactly the case that fails when the last row is edited (H1).
- Q5 as "shared but exempt": see above.
- Per-file stuck conflicts for M2: 29 misleading "need a manual merge" lines.
- Keeping overrides merged against shipped bases: needs the blobs Q1=A drops.
- `protected_config` for the installed tree: its deny text, "guard configuration and the task state", is frozen and would be wrong for this tree (OQ-B).

residual_risk:
- OQ-A: if the human meant the other reading of Q5, Steps 2 and 7 change.
- The G-M8 read-probe result is unknown until a human runs it and may add a settings step.
- On a router with its heading renamed, the section is appended at the end: correct, but less visible.
- The `three_way` router guard is a special case, like the risk-tiers mirror.
- The must-bite sensor may flag `test-project-update.sh` (see Risks).

revisit_when:
- The human rejects OQ-A.
- G-M8 reports a prompt or a refusal.
- Gemini/Junie gain a shared-tree install path.
- The H3 bugfix changes how routing.md is rendered.

---

# Implementation plan: T-2026-10-13-004 (revision 2)
author: ai-expert (EXPERT tier), 2026-10-14. Supersedes revision 1 (2026-10-13). Inputs: plan-review.md (H1-H3, M1-M9, L1-L7), task-context.md, impact-report.md, questions.md. Decisions: Q1=A, Q2=A, Q3=B, Q4=A, Q5=A (project-owned reading, OQ-A), Q6=A.

goal: The shared .ai/ files ship in the plugin at `<home>/claude-agentic/ai/` and are read from there; a project copy at the same path overrides. They are 29 files:
- 8 policies: production, database, git, release, context-management, tooling, model-routing, review-economy
- agents/ (10), workflows/ (5), templates/ (6)

/ai-init copies only project-owned files. Migration 0006 first makes the project router name the shared tree. It then proposes deleting unedited copies (gated) and reports edited copies as overrides. VERSION goes 5→6. History keeps every hash, and bytes only for still-merged files.

current_behaviour:
- scaffold-ai.sh:75-84 copies all of templates/.ai/.
- update.py:905-922 three-way merges all of it, with history/blobs as the base (:574-628).
- The router names policies/workflows/agents/templates relative to .ai/.
- The Gemini/Junie block names `.ai/policies/safety.md` (stub.md:46).
- history/ is index.json plus 198 blobs.

desired_behaviour:
- **Template tree.** `.ai/` holds:
  - policies/{risk-tiers.json, risk-tiers.md, path-guard.json, testing.md, coding.md, safety.md, security.md}
  - project/, rules/, state/, reports/, AGENTS.md, VERSION
- **Shared tree.** The repo's `ai/` holds the 29. install.sh copies it to `<home>/claude-agentic/ai/` (Claude and Codex), installs `<home>/claude-agentic/ai-path`, and renders the absolute path into the agents and routing.md.
- **Resolution.** Project `.ai/<path>` when it is a regular file, else `<shared>/<path>`. `ai-path` walks up to find `.ai/`.
- **Router.** Unchanged table and anchor heading, plus a `## Shared files` section.
- **0006.** Uses a static list of 29 paths and plans the router operation first. Then, per copy:
  - `delete?` when the bytes are shipped (CRLF-normalised), the target is safe and every installed home has the fallback;
  - an override hint when the copy is edited;
  - a hint, never a deletion, for a symlink or a path outside the project.
- **Plain update at schema 6.** Shared copies identical to a shipped version are offered `delete?` again; edited ones get one override hint.
- **History.** index.json keeps every key and sha; blobs exist only where a non-shared key references them.

affected_components:
- New: `ai/**`, `scripts/ai-path`, `0006_shared_files.py`.
- install.sh, scripts/render-codex-agents.py, instructions/routing.md.
- hooks/ai-path-guard-defaults.json (data only).
- 10 `agents/ai-*.md.tmpl`, skills/ai-task/SKILL.md.
- The router template, plus 29 template files removed and the VERSION template.
- skills/project-update/{update.py, SKILL.md, history/**}, skills/ai-init/SKILL.md, tools/build-template-history.py.
- Tests, README/CONTRIBUTING/docs, .ai/project/known-risks.md.

explicitly_unaffected:
- Hook code and deny texts (test-guard-characterization.sh stays byte-identical).
- state.py, sensors.py.
- runtime-gate.py, profiles/**, resolve-profile.py, merge-codex-config.py (task B); ai-task split (task C).
- instructions/stub.md and the rendered *.block.md / *.minimal.md.
- skills/project-init/**; migrations 0001-0005 and migrations/__init__.py; render_instructions.py, adopt.py, scaffold-ai.sh.
- settings.common.json, unless G-M8 fails.
- The safety.md and security.md templates.
- docs/sdlc/**, .github/workflows/**.
- This repo's own .ai/ (a human migrates it after close).

## Preconditions and gates
- **P1.** Baseline `bash tests/run-all.sh` is green at the base commit, with the log under the report dir. The review confirmed test-project-update 179/0 and test-project-adopt 311/0 at 8c9cf1b; known-risks.md:63-68 no longer reproduces.
- **P2 (H3, Q6=A), gates Step 3.** The separate bugfix that gives claude_render and codex_render distinct routing temp files (install.sh:423, :932, :730 at 8c9cf1b) is merged into this task's base.
  - Check: run `install.sh --target both --plan max --codex-plan plus --dry-run` into scratch homes. The Claude section's routing.md must not contain "Model routing (Codex)".
  - If not met: Step 3 does not start (Steps 1-2 may).
  - That task owns the fix, its test and its known-risk entry. install.sh line numbers here are at 8c9cf1b; after the bugfix, locate by function name.
- **G-M8 (human), gates Step 7.** The read probe recorded in m8-read-probe.md (see Step 4).
- **Order:** 1 → 2 → [P2] 3 → 4 → 5 → 6 (HO1) → [G-M8] 7 (D3) → 8 (D2) → 9.

## G — forbidden in every step
- hooks/** (Step 3 may touch only hooks/ai-path-guard-defaults.json), .github/**
- instructions/stub.md
- skills/ai-init/templates/*.block.md, skills/ai-init/templates/*.minimal.md, skills/ai-init/templates/gitignore.snippet
- skills/ai-init/templates/.ai/policies/{safety,security}.md, skills/ai-init/scaffold-ai.sh
- skills/project-init/**
- skills/ai-task/{state.py,sensors.py}
- skills/project-update/migrations/{__init__.py,000[1-5]_*.py}, skills/project-update/{render_instructions.py,adopt.py}
- profiles/**, scripts/{resolve-profile.py,merge-codex-config.py}
- settings.common.json
- docs/sdlc/**, tests/fixtures/guard-characterization/**
- This repo's .ai/** except .ai/reports/T-2026-10-13-004/** and .ai/project/known-risks.md (Step 9).

Scope-guard note: patterns are bash globs. `*` crosses `/` and braces are not expanded, so the JSON lists every path literally.

## Steps

### Step 1 — characterization: move hand edits off shared keys (test-only)
- description: test-project-update.sh fixtures stop depending on shared files. The behaviour it asserts is unchanged.
- allowed_files: tests/test-project-update.sh, tests/fixtures/project-update/migrations-synthetic/0002_move.py, tests/fixtures/project-update/migrations-synthetic/0003_edits.py, tests/fixtures/project-update/shared-old/
- forbidden_files: G. forbidden_reason: product files are not touched by a characterization step.
- required_behaviour:
  - Project P (:58-67, :94-101). Counts at :79, :110, :114 stay unchanged.
    - "Conflict": the feature.md row edit becomes an edit of line 4 of .ai/state/README.md. It differs between the oldest blob and current (reviewer-verified). The conflict-copy assertion follows. There is no AGENTS.md fallback.
    - "Untouched replaced": bugfix.md becomes .ai/policies/safety.md. The implementer confirms in index.json that it has ≥2 versions with oldest ≠ current; otherwise use .ai/AGENTS.md.
    - "Missing recreated": rm templates/review-report.md becomes rm .ai/policies/security.md.
  - Synthetic move (:372-377, :401-441, 0002/0003): .ai/workflows/bugfix.md→fix.md becomes .ai/policies/coding.md→.ai/policies/code-style.md. The never-existed pair stays; --files and the 0003 allowed_files rename follow.
  - shared-old/ (no `.ai/` anywhere in a path, because of the frozen-path guard):
    - oldest shipped bytes of workflows/feature.md, agents/manager.md, and of the shared policy with the most versions in index.json;
    - AGENTS.v5.md, the router template at the base commit (the last schema-5 router);
    - SOURCES.txt (key, sha256, commit).
- behaviour_that_must_not_change: every product file; assertion count and verbs.
- required_tests: tests/test-project-update.sh (must pass at base).
- step_tests: step_test_command with tests/test-project-update.sh
- rollback: git revert (test-only).

### Step 2 — shared tree, byte-identical copy (additive)
- allowed_files: ai/, tests/test-shared-tree.sh (new), tests/test-shared-prompts-model-free.sh, tests/run-all.sh
- required_behaviour:
  - Copy with cp from skills/ai-init/templates/.ai/: ai/policies/{production,database,git,release,context-management,tooling,model-routing,review-economy}.md, ai/agents/<10>.md, ai/workflows/<5>.md, ai/templates/<6>.md.
  - No safety.md or security.md (Q5=A); no .json.
  - test-shared-tree.sh:
    - the file set equals a literal list of 29;
    - each file is byte-identical to its template copy (temporary; flipped in Step 7);
    - safety.md and security.md are absent.
  - The model-free scope() (:16-21) adds `find ai -type f`.
  - run-all.sh lists the new suite.
- behaviour_that_must_not_change: scaffold, update and install output.
- required_tests: tests/test-shared-tree.sh, tests/test-shared-prompts-model-free.sh
- rollback: git revert.

### Step 3 — install tree, resolver, rendered path, guard data (additive) [requires P2]
- allowed_files: install.sh, scripts/ai-path (new), scripts/render-codex-agents.py, instructions/routing.md, hooks/ai-path-guard-defaults.json, tests/test-shared-tree.sh, tests/test-install-dry-run.sh, tests/test-codex-agent-render.sh, tests/test-dual-runtime-install.sh, tests/test-codex-install.sh, tests/test-ai-path-guard.sh
- forbidden_files: G, with hooks/ narrowed to hooks/*.sh, hooks/*.py, hooks/lib/, hooks/ai-git-guard-defaults.json.
- required_behaviour:
  - **Install order.** claude_apply and codex_apply install the shared tree *before* install_skills, so a new update.py never exists without its tree.
  - **L3, no rm -rf window.** Copy ai/ to a sibling temp directory, rename the old tree aside, rename the new one into place, then remove the old. A tree that differs from ai/ is first backed up to `<home>/backups/claude-agentic-ai/` (the install_skills pattern, :532-547). Install `<home>/claude-agentic/ai-path` with +x.
  - **Dry run** prints `   shared:  claude-agentic/ai (29 files), claude-agentic/ai-path` in the would-install list (:508-515, :946-952). It never prints it between `== CLAUDE.md managed block:` and `== routing.md`.
  - **Rendering.**
    - RENDER_AI_SHARED and RENDER_AI_RESOLVER are exported to render_claude_files (:400-412) and codex_render_files (:906-927).
    - render-codex-agents.py takes `--ai-shared PATH` (default: the expanded `${CODEX_HOME:-~/.codex}/claude-agentic/ai`), substituted before the `{{` check (:110). install.sh:904 passes it.
    - routing.md gets one line per runtime naming {{AI_SHARED}}/, the override rule and `{{AI_RESOLVER}} <path>`.
  - **scripts/ai-path** (python3, stdlib only):
    - Usage: `ai-path [--root DIR] <path>` and `ai-path --tree-hash`.
    - Strips a leading `.ai/`. Exit 2 on an absolute path or a `..` component.
    - Root: `--root`, else walk up from $PWD to the first directory holding `.ai/` (state.py:187-195 semantics, M5). No project found: exit 1, reason on stderr, nothing on stdout.
    - Prints `<root>/.ai/<path>` only when it is a regular file; a directory is never an override (L5). Else prints `<shared>/<path>` when it exists. Else exit 1 with a reason.
    - Shared tree: $CLAUDE_AGENTIC_SHARED, else <script dir>/ai, else <script dir>/../ai.
    - `--tree-hash` prints the sha256 of the sorted `<sha256>  <relpath>` lines of the shared tree (M7: a release report can name the policy text in force).
  - **Q4=A.** Append `(^|/)\.(claude|codex)/claude-agentic/(ai/|ai-path$)` to task_protected_patterns. Guard code and deny texts are unchanged.
- required_tests:
  - test-shared-tree.sh (resolver):
    - override wins; fallback; missing = 1; traversal = 2; absolute = 2;
    - from a subdirectory, the project override is found (M5);
    - no project = 1; a directory at the path is not an override (L5);
    - installed layout works;
    - --tree-hash is stable and changes on a one-byte edit.
  - test-install-dry-run.sh: the shared line is present and outside the block/routing span; routing.md renders fully for both runtimes.
  - test-codex-agent-render.sh: --ai-shared substitution and its default.
  - test-dual-runtime-install.sh: a real `--target both` install into scratch homes.
    - Each home's routing.md names its own `<home>/claude-agentic/ai` and not the other's (depends on P2).
    - Each home's tree is `diff -r` equal to ai/.
    - ai-path is executable in each home.
  - test-codex-install.sh: only its installed-file expectations change, if it pins them.
  - test-ai-path-guard.sh (M7):
    - task in flight: Write/Edit to `<scratch>/.claude/claude-agentic/ai/policies/git.md` and to `ai-path` are denied; Read of the same file is allowed; running ai-path through Bash is allowed;
    - no task in flight: all allowed.
  - test-guard-characterization.sh: stays byte-identical to golden.txt (L7).
  - test-shared-prompts-model-free.sh, test-instruction-budget.sh, test-profiles.sh: green.
- behaviour_that_must_not_change: hook code and deny texts; every other install output line; scaffolds.
- rollback: git revert, then reinstall the previous build. A leftover `<home>/claude-agentic/ai{,-path}` is harmless.

### Step 4 — consumers resolve shared paths (prompt, compatible)
- allowed_files: agents/ai-context.md.tmpl, agents/ai-discovery.md.tmpl, agents/ai-expert.md.tmpl, agents/ai-implementer.md.tmpl, agents/ai-planner.md.tmpl, agents/ai-release.md.tmpl, agents/ai-reviewer.md.tmpl, agents/ai-risk.md.tmpl, agents/ai-security.md.tmpl, agents/ai-tester.md.tmpl, skills/ai-task/SKILL.md, tests/test-install-dry-run.sh, tests/test-shared-tree.sh, tests/test-codex-agent-render.sh, .ai/reports/T-2026-10-13-004/m8-read-probe.md
- required_behaviour:
  - Agents: the "Read first" lines name paths relative to .ai/ with one rule: "project `.ai/<path>` when it exists, else `{{AI_SHARED}}/<path>`; `.ai/` paths inside them resolve the same way".
  - ai-task/SKILL.md: one rule paragraph after the AI_HOME block, using `"$AI_HOME/claude-agentic/ai-path" <path>`; lines :10-11 follow it.
  - No model names. ADVERSARIAL REVIEW stays. Frontmatter and other placeholders are unchanged.
  - m8-read-probe.md: a checklist for the human.
- **G-M8 (human, before Step 7; M8).** After installing this additive build, record allowed / prompted / refused for:
  - a Claude Code main session (default permission mode) doing a Read of `~/.claude/claude-agentic/ai/policies/git.md`;
  - a foreground subagent and a background subagent doing the same;
  - Bash `ai-path policies/git.md` with a task in flight;
  - Codex `--sandbox read-only` and `--sandbox workspace-write` reading `~/.codex/claude-agentic/ai/policies/git.md` and running ai-path.

  Any "prompted" or "refused" means SCOPE_CHANGE_REQUIRED: the plan gains a step adding a read rule to settings.common.json (and the Codex config if needed) before Step 7.
- required_tests:
  - rendered agents (both runtimes) contain the absolute shared path and no `{{` (test-codex-agent-render.sh, test-install-dry-run.sh, test-shared-tree.sh);
  - test-shared-prompts-model-free.sh, test-instruction-budget.sh.
- rollback: git revert; reinstall.

### Step 5 — update.py helpers (added, not wired)
- allowed_files: skills/project-update/update.py, tests/test-shared-tree.sh
- required_behaviour: all runtime and plugin wording lives in update.py, never in 0006 (test-project-update.sh:490-491). Helpers to add:
  - SHARED = $CLAUDE_AGENTIC_SHARED, else dirname(SKILLS)/claude-agentic/ai, else dirname(SKILLS)/ai.
  - shared_files() returns {".ai/<rel>": bytes}.
  - History.hashes(key): every sha along chain(key) from index.json; needs no blob.
  - MigrationContext.template(path): the current shipped bytes for that path; SchemaError if missing.
  - MigrationContext.is_shipped(path, data): sha256 of the raw bytes, or of the bytes with CRLF→LF (L4), is in hashes(key).
  - MigrationContext.require_shared(paths) (M2). Evaluated lazily, for the given paths only.
    - Each path must exist in SHARED.
    - For each runtime the project declares among claude and codex, find its home ($HOME/.claude, ${CODEX_HOME:-$HOME/.codex}). If that home is not this plugin's home and has skills/project-update/, each path must exist in `<home>/claude-agentic/ai/`.
    - Otherwise raise SchemaError naming the home, the missing count and the install.sh command (exit 2, nothing written).
    - A home absent on this machine is not checked.
  - MigrationContext.unsafe_target(path) (M9): returns a reason when the path is a symlink or its realpath leaves realpath(root).
  - MigrationContext.override_note(path): "overrides the plugin's shared copy and no longer receives its changes — diff against <SHARED>/<rel>; `ai-path <rel>` shows which applies; delete it when it adds nothing".
  - git_dirty_ai(root) (M4): non-empty `git status --porcelain -- .ai` (ignored paths excluded); False outside a work tree.
- behaviour_that_must_not_change: build_plan output for every fixture.
- required_tests:
  - tests/test-shared-tree.sh, as Python unit checks:
    - classify current / old / edited / CRLF bytes;
    - hashes() on a history copy without blobs/;
    - require_shared with HOME at scratch: no home → ok; codex home with the plugin but no tree → SchemaError; partial tree → SchemaError naming the count; full tree → ok;
    - unsafe_target on a symlinked directory and a symlinked file;
    - template().
  - Kept green: tests/test-project-update.sh, tests/test-merge-migration.sh, tests/test-project-adopt.sh, tests/test-scaffold-idempotency.sh.
- rollback: git revert.

### Step 6 — router gains the "## Shared files" section (prompt, compatible; human hand-over HO1)
- allowed_files: .ai/reports/T-2026-10-13-004/handover/router.md, .ai/reports/T-2026-10-13-004/handover/install-router.sh, skills/ai-init/templates/.ai/AGENTS.md (written by the human), skills/project-update/history/index.json, skills/project-update/history/blobs/, tests/test-instruction-budget.sh, tests/test-shared-tree.sh
- order:
  1. The agent writes router.md and install-router.sh (`set -euo pipefail`; abort unless the template equals `git show HEAD:skills/ai-init/templates/.ai/AGENTS.md`; then cp).
  2. The human runs `bash .ai/reports/T-2026-10-13-004/handover/install-router.sh`.
  3. The agent runs `python3 tools/build-template-history.py` (adds one blob, deletes none).
  4. Step tests.
- router constraints (these remove H1's root cause):
  - Non-negotiables, the `## Doing X → read Y` heading line, every table row and `## Keeping this directory true` stay byte-identical.
  - One new section, `## Shared files`, sits immediately before the routing heading. It is prose only: no line starts with `|`, so `adopt.add_router_rows` keeps appending to the routing table. It says:
    - this .ai/ holds project/, rules/, state/, reports/, VERSION and policies risk-tiers.json, risk-tiers.md, path-guard.json, testing.md, coding.md, safety.md, security.md;
    - every other path in the table ships at `<home>/claude-agentic/ai/<path>` (`<home>` is `~/.claude`, or `$CODEX_HOME`, default `~/.codex`);
    - a file at the same path under .ai/ overrides it and stops receiving its changes;
    - `<home>/claude-agentic/ai-path <path>` prints the copy that applies.
  - The intro (:3-6) may be shortened to stay ≤4096 B. No ADVERSARIAL REVIEW.
- required_tests:
  - test-instruction-budget.sh:
    - the probe also accepts `$PLUGIN_ROOT/ai/$probe`;
    - the section appears exactly once, before the routing heading, with no `|` line in it;
    - ≤4096 B.
  - test-shared-tree.sh: add_router_rows on a scaffolded new router places rows after the routing table.
  - Kept green: test-project-update.sh, test-project-adopt.sh (:660), test-merge-migration.sh, test-scaffold-idempotency.sh.
- rollback: git revert (template, blob, index). Projects that merged the new router keep a rule that is still true, because their copies exist and override.

### Step 7 — cut-over and migration 0006 (BREAKING; D3 human hand-over; defines D1) [requires G-M8]
- allowed_files:
  - Human (D3): the 29 skills/ai-init/templates/.ai/... paths (JSON).
  - Agent: .ai/reports/T-2026-10-13-004/handover/cutover.sh, .ai/reports/T-2026-10-13-004/m3-byte-sweep.log, skills/ai-init/templates/.ai/VERSION, skills/project-update/migrations/0006_shared_files.py, skills/project-update/update.py, skills/project-update/SKILL.md, skills/ai-init/SKILL.md, tools/build-template-history.py, skills/project-update/history/index.json, skills/project-update/history/blobs/, tests/test-project-update.sh, tests/test-scaffold-idempotency.sh, tests/test-instruction-budget.sh, tests/test-shared-tree.sh, tests/test-migration-0006.sh (new), tests/run-all.sh, tests/fixtures/project-update/schema-v5/
- order:
  1. The agent writes cutover.sh (`set -euo pipefail`).
     - Phase 1 compares all 29 `ai/<rel>` files with their template copies and collects every difference. Any difference → print them all and exit 1 before removing anything (L2).
     - Phase 2 removes the 29 and lists them.
  2. **D3:** the human runs `bash .ai/reports/T-2026-10-13-004/handover/cutover.sh`. Recoverable from git.
  3. The agent writes code and tests, bumps VERSION 5→6, and runs `python3 tools/build-template-history.py` (adds, deletes none).
  4. Step tests; the byte-sweep output is saved to m3-byte-sweep.log.
- 0006_shared_files.py (VERSION=6, MOVES=[]). No lowercase "claude" or "codex" anywhere in the file, docstring included (L1).
  - SHARED = a literal tuple of the 29 paths (M1). safety.md and security.md are never in it.
  - **Router first (H1)**, one operation planned before any deletion:
    - absent → `ctx.create` with `ctx.template`;
    - has a `## Shared files` line → nothing;
    - is a shipped version → `ctx.edit_text` to the template;
    - otherwise → insert the template's section (cut like 0003's `_section`) before the line that follows it in the template, when the router has that line; else append it at the end (block_update precedent). Note: "[0006] Shared files section added; your router edits kept".
  - Then, for each SHARED path that exists:
    - `unsafe_target` → hint, never deleted (M9);
    - not `is_shipped` → `hint(override_note)`;
    - otherwise it is a candidate.
  - Candidates → `ctx.require_shared(candidates)` (M2), then `ctx.delete(path, "identical to a version the plugin shipped; its shared copy applies")`. These stay `delete?` until --confirm-delete, and VERSION is held meanwhile (update.py:874-880).
- update.py wiring:
  - **three_way router guard (H1):** a merge of .ai/AGENTS.md whose result does not contain the `## Shared files` line exactly once is a conflict (project file kept, copy in the local dir).
  - **Plain update at schema 6, when 0006 is not pending (M6).** Applies to each `shared_files()` path the project has:
    - shipped, safe, and the router has the section → `delete?`/`delete` with the same gate (reason "[shared] identical to a shipped version");
    - an installed home lacks the file → hint only;
    - edited copies → one aggregated hint using override_note.
  - Deletions proposed while `git_dirty_ai` → hint "commit .ai/ first: git is this migration's rollback" (M4).
  - `shipped_ai_files()` (:1127) maps the shared tree to `.ai/<rel>`.
  - The docstring at :22-29 is updated.
- build-template-history.py: SETS gains `ai/` under the prefix "ai-init/.ai"; keys are unchanged.
- SKILL.md:
  - project-update: documents 0006 and the override rule, including that overrides stop merging (M6). Ordering: install.sh in every home, commit .ai/, dry run, then a human runs `update.py <proj> --apply --confirm-delete <name>` in a terminal with no task in flight. Rollback: git first.
  - ai-init: one sentence.
- required_tests:
  - test-project-update.sh:
    - the OLD builder (:37-49) skips keys whose path is under ai/;
    - staleness (:18-35) and key accounting (:523-560) walk ai/ as ai-init/.ai/;
    - shared keys are derived from the ai/ tree, not from a literal (bite).
  - test-scaffold-idempotency.sh (:21-25): the 29 are absent from a scaffold; safety.md and security.md are present.
  - test-instruction-budget.sh: the ai/ probe, if not already added in Step 6.
  - test-shared-tree.sh: flipped to "no path in both trees"; 0006.SHARED equals the ai/ set (M1).
  - test-migration-0006.sh (new). HOME and CLAUDE_AGENTIC_SHARED are pinned. Fixtures are committed git repos built from the scaffold, ai/ copies, shared-old/ and schema-v5/VERSION.
    - Router fixtures:
      - R1 shipped v5 router → replaced;
      - R2 AGENTS.v5.md plus two rows from `adopt.add_router_rows` (production shape);
      - **R3 AGENTS.v5.md with its last table row edited plus the two adopt rows** (the edited row and the adopt rows survive);
      - R4 routing heading renamed → section appended; the three_way guard leaves exactly one section;
      - R5 router missing → created first;
      - R6 router is a symlink → the confirmed apply exits 3 at the router item and every shared copy is still present.
    - Invariants over R1-R5: after a confirmed run, every router has the section exactly once; in every dry run the router item precedes the first `delete?`.
    - Dry run and gate:
      - the dry run writes nothing;
      - --check prints `schema 5 -> 6, … N deletion(s) a human must confirm, the schema stays at 5 until they are settled`;
      - plain --apply keeps VERSION 5 (the router is written);
      - CLAUDECODE=1 without a tty exits 5;
      - `AI_UNATTENDED=1 --confirm-delete tester` deletes exactly the shipped copies, keeps originals with their modes, records confirmed_by/via in migration.json, and sets VERSION 6;
      - a second run makes 0 changes and prints the override hint.
    - Other cases:
      - Edited (one byte) → override.
      - CRLF → deleted, original kept byte-identical (L4).
      - A project-only workflow and policies/adopted/x.md are untouched.
      - A Gemini-declaring fixture: safety.md and security.md are never named and are still present (Q5).
    - M2:
      - CLAUDE_AGENTIC_SHARED=/nonexistent → exit 2, nothing written;
      - local tree minus one file → exit 2 naming it;
      - declared codex with `$HOME/.codex/skills/project-update` but no tree → exit 2 naming the home;
      - no ~/.codex at all → proceeds.
    - M9: a symlinked `.ai/workflows` pointing outside the project → hint, outside files intact; a symlinked file → hint.
    - L5: an empty .ai/agents/ remains; ai-path still resolves to the shared copy.
    - M6: on a migrated project, a re-added shipped copy → `delete? [shared]`; an edited copy → hint; VERSION stays 6.
    - M4: a dirty .ai/ → commit-first hint.
    - **M3 byte sweep:** every shipped version of every shared key in history/blobs is classified `delete?`, and one flipped byte makes it an override. Prints "byte sweep: K keys, V versions …"; the output goes to m3-byte-sweep.log.
    - **Rollback rehearsal (M4):**
      - The git route restores every file byte- and exec-bit-identical, router included, and VERSION 5.
      - A 0001-0005-only registry (CLAUDE_AGENTIC_MIGRATIONS) gives --check exit 0/1 on the restored tree and exit 2 on the migrated one.
      - The new plugin re-plans the same `delete?` list.
      - The jq fallback, looped over every project-update-* directory, restores the deletions and leaves the router new (asserted, to document the limit).
  - run-all.sh lists the new suite.
  - Kept green: test-project-adopt.sh (unmodified, since Q5=A keeps security.md at :623), test-merge-migration.sh.
- behaviour_that_must_not_change: project-owned merges and the mirror sync; block_update; 0001-0005; --check line shapes; the delete gate; guard texts; stub and blocks; adopt flows.
- diff: over the advisory budget and not splittable (the migration must retire its templates in the same release, update.py:472-474). Report it; do not split.
- rollback: a single git revert. Projects already at schema 6 roll back first, through the git route, because the reverted plugin refuses schema 6 (exit 2).

### Step 8 — drop blobs referenced only by shared keys (DESTRUCTIVE, D2)
- precondition: m3-byte-sweep.log from Step 7 shows every shared version classified (M3).
- allowed_files: tools/build-template-history.py, skills/project-update/history/blobs/, tests/test-project-update.sh, tests/test-shared-tree.sh, tests/test-migration-0006.sh, .ai/reports/T-2026-10-13-004/d2-blobs.txt. index.json is deliberately not listed: it must stay byte-identical.
- required_behaviour:
  - Permanent keep rule in the tool: a blob is written only if a key outside the shared set references it. Shared keys are `ai-init/.ai/<rel>` with `ai/<rel>` present.
  - `--dry-run` writes d2-blobs.txt. **D2:** the human approves "delete these N blobs" before the real run.
- required_tests:
  - staleness: non-shared current templates have hash and blob; shared ones have hash only; no blob is referenced only by shared keys;
  - in test-migration-0006.sh the byte sweep becomes a hash sweep through History.hashes; shared-old/ keeps the byte-level path;
  - rehearsal: `git show HEAD:skills/project-update/history/blobs/<sha> | sha256sum` equals the name for each dropped blob, and the D count equals N;
  - kept green: test-merge-migration.sh, test-project-adopt.sh.
- rollback: git revert restores the blobs.

### Step 9 — docs and known risks
- allowed_files: README.md, CONTRIBUTING.md, docs/agents.md, docs/architecture.md, docs/faq.md, docs/getting-started.md, docs/hooks.md, docs/workflows.md, .ai/project/known-risks.md
- required_behaviour:
  - README :249-294 and :366 updated; overrides stop merging (M6); rollback is git first.
  - Known-risks entries:
    - (a) Guard Bash write detection misses rm/mv/cp destinations on frozen paths (ai-path-guard.sh:273-337).
    - (b) .ai/agents/ is not task-protected (defaults.json:46) and is now an override path.
    - (c) The installed tree is guarded only while a task is in flight and only in .ai/ projects (M7). This is parity with the installed agents/skills; `ai-path --tree-hash` is available.
    - (d) Deny and comment text naming files that become shared: hooks/ai-git-guard.sh:109 names policies/release.md, and project-init project-config.toml:14 names policies/tooling.md. Both are reached through the router.
    - (e) Gemini/Junie-only machines have no shared tree. safety.md and security.md stay local (Q5=A); 27 files are unreachable for those runtimes.
    - (f) This repo's overrides shadow what it ships.
    - (g) stub.md:24 and :37 "treat .ai/policies/ as binding" now covers only 7 local files (L6).
    - (h) Edited overrides get no upstream changes, and "behind" cannot be detected once the bases are dropped (M6).
    - (i) Homes absent on this machine are unchecked (M2).
    - (j) The jq rollback restores deletions only (M4).
    - (k) Two-rename install window (L3).
    - (l) Plain --check says "matches" while a `[shared] delete?` waits (same as for rules).
  - README assertion count: taken from the end-of-task verify log, because a step never runs the full suite. It is written as a one-line README change after the green run.
- required_tests: none (docs). step_tests: none.
- rollback: git revert.

## End-of-task verification
- verify_command: `bash tests/run-all.sh`, once, to the end; failures fixed as one batch. New Python (0006, update.py) must keep pylint at 10.00. `scripts/ai-path` has no .py suffix, so pylint does not see it.
- e2e_command: `bash tests/test-end-to-end.sh`, once afterwards (the install → scaffold flow is reached).

## Compatibility strategy
- **Install first is safe:** the tree and resolver are additive, and copies stay as same-byte overrides until 0006.
- **The Step 6 router is true before and after 0006.**
- **Without --confirm-delete:** 0006 writes the router and holds VERSION at 5; copies stay.
- **Old plugin against VERSION 6:** exit 2 "update the plugin" (update.py:864-866, --check :1274-1277). M2 refuses to delete while an installed home lacks the tree.
- **Old /ai-init** that re-adds copies: they are re-offered `delete?` (M6).
- **Gemini/Junie:** safety.md and security.md stay local (Q5=A).
- **Teams:** every machine upgrades the plugin before VERSION 6 is committed.
- **Unaffected:** state.py, sensors.py and hooks.

## Migration impact
- No locks: apply checks the sha per file, exits 3 on a mismatch, and a re-run recovers. Run with no task in flight.
- Size: ≤29 deletions plus 1 router write per project; seconds.
- Order: plugin release → install.sh in every home → commit .ai/ → dry run → the human runs `update.py <proj> --apply --confirm-delete <name>` in a terminal → the human commits.
- This repo (post-close, human): ./install.sh; commit; dry run. Expect the router insert, `delete?` for unedited copies, override hints (including policies/review-economy.md), and the schema held at 5. Then confirm; one follow-up task per remaining override.
- Destructive operations, each needing a named approval:
  - **D1** — 0006 deletion, per project, human --confirm-delete.
  - **D2** — Step 8 blob removal; the human approves the listed N.
  - **D3** — Step 7 cutover.sh; the human runs it; everything is compared before anything is removed; recoverable from git.
  - HO1 (Step 6 router) is a non-destructive hand-over.

## Rollback
**Project — git is primary (M4).** It needs .ai/ committed before the run; update.py hints when it is not.

    git restore --source=<commit before the migration> --staged --worktree -- .ai

Then keep the project off `/project-update --apply` until the plugin is downgraded or the decision is revisited, because the new plugin re-plans 0006.

**Fallback (no commit) restores deletions only.** The router keeps its section, which is true and harmless while copies exist, and other merges stay.

    for R in .ai/reports/project-update-*; do jq -r '.ops[]|select(.action=="delete" and .migration==6)|.path' "$R/migration.json" 2>/dev/null | while IFS= read -r p; do mkdir -p "$(dirname "$p")"; cp -p "$R/original/$p" "$p"; done; done
    printf '5\n' > .ai/VERSION

**Plugin:** one git revert per step commit, newest first; Step 7 is a single revert; the Step 8 revert restores the blobs. Roll projects back before downgrading below Step 7. A leftover `<home>/claude-agentic/ai{,-path}` is harmless.

## Observability
- **Working:**
  - install prints `shared: claude-agentic/ai (29 files)`;
  - `ai-path` and `--tree-hash` print;
  - the dry run shows `update .ai/AGENTS.md [0006] …` before `delete? … [0006]`, and `N deletion(s) awaiting --confirm-delete`;
  - after confirmation, migration.json has deletions[] with confirmed_by/via, VERSION is 6, and --check says "project matches".
- **Failing:**
  - exit 2 "shared tree at <home> lacks N file(s) — run install.sh";
  - ai-path exit 1;
  - old plugin "says schema 6";
  - a persistent override hint;
  - the commit-first hint;
  - a router conflict from the three_way guard.

## Risks
- Prose path resolution is not enforced by code; rendered absolute paths and ai-path mitigate.
- Unconfirmed copies shadow newer shared versions until a human confirms.
- **Bite sensor:** `tests/test-project-update.sh` is named by Step 1 (characterization, must pass at base) and by Step 7. The final file runs at base and is designed to pass there (shared keys derive from ai/). A RED is still possible; classify it, do not edit the test.
- Step 7 size.
- The router special case in three_way.
- G-M8 depends on a human.
- Overlap with tasks B and C (install.sh, ai-task SKILL.md): mind the merge order.
- install.sh line numbers shift after the H3 bugfix.

## Open questions
None is blocking.
- **OQ-A (confirm at plan approval).** Q5=A is read as "safety.md and security.md stay project-owned". The other reading (shared, but exempt from deletion) gives new Gemini/Junie projects no safety.md and freezes existing copies. If that reading was meant, Steps 2 and 7 change to 31 files plus a 0006 exemption.
- **OQ-B (M7).** Promote the installed-tree pattern to protected_config_patterns? Default no. Q4=A was answered; the protected deny text is frozen and wrong for this tree; and installed agents/skills have the same task-only protection.
- **OQ-C.** Two hand-overs (HO1, D3) instead of one. Default: two, so the router is reviewed apart from the destructive cut-over.
- **OQ-D (M2).** Exit 2 for the whole update, rather than per-file holds. Default: exit 2.
- **Carried defaults from revision 1:**
  - frozen template paths are written through a human hand-over (OQ2);
  - the blob keep rule also keeps project/**, the gitignore snippets, the skeleton/minimal templates and safety/security (OQ4);
  - the source lives at the repo-root `ai/` (OQ5).

---

## Changelog (finding → where it is handled)
| Finding | Where |
|---|---|
| H1 | Step 6 (the router change is an insertion; table and anchor unchanged; section without a table); Step 7 (0006 router operation first; apply-abort ordering; three_way guard; fixtures R1-R6, including R3 = adopt rows plus an edited last row; invariants); Rollback (rehearsal includes the router) |
| H2 / Q5 | Scope: safety.md and security.md stay project-owned (goal, desired_behaviour, G list); Step 2 file list (29); Step 7 Gemini fixture; known risk (e); OQ-A |
| H3 / Q6 | Precondition P2 gating Step 3; the Step 3 dual-runtime assertion is this task's feature test; the bugfix task owns the fix and its known-risk entry |
| M1 | Step 7: literal SHARED in 0006; test-shared-tree.sh equality with ai/ |
| M2 | Step 5 `require_shared` (per file, other installed homes, exit 2); Step 7 fixtures; known risk (i); OQ-D |
| M3 | Step 7 byte sweep plus m3-byte-sweep.log; Step 8 precondition and hash sweep |
| M4 | Rollback (git primary; jq fallback limited and looped); Step 5/7 commit-first hint; Step 7 rehearsal with router and registry checks |
| M5 | Step 3: ai-path walks up to `.ai/`; subdirectory and no-project tests |
| M6 | Step 7: override_note wording, plain-update `delete? [shared]`, SKILL.md; Step 9 README; "behind" detection deferred because it needs the bases Q1=A drops (known risk h) |
| M7 | Q4=A kept; Step 3 guard tests (Read and ai-path allowed in a task, writes denied); `ai-path --tree-hash`; known risk (c); OQ-B |
| M8 | Step 4 checklist plus the G-M8 human gate before Step 7; settings.common.json stays forbidden unless the gate fails (SCOPE_CHANGE) |
| M9 | Step 5 `unsafe_target`; Step 7 hint, never delete; symlink fixtures |
| L1 | Step 7 0006 wording rule (test-project-update.sh:490-491 enforces it) |
| L2 | Step 7 cutover.sh in two phases |
| L3 | Step 3 sibling temp plus rename; tree installed before skills; known risk (k) |
| L4 | Step 5 CRLF normalisation; Step 7 fixture |
| L5 | Step 3 (a directory is not an override); Step 7 fixture |
| L6 | Step 9 known risk (g) |
| L7 | Step 3 names test-guard-characterization.sh |
| Also | test-project-adopt.sh:623 needs no change (Q5=A keeps security.md); revision 1's AGENTS.md fallback for the Step 1 conflict is dropped |

---

## Steps JSON for `state.py plan --steps`
Fields: step_id, kind, description, allowed_files, forbidden_files, forbidden_reason, required_tests. `rollback` is an extra field; state.py keeps unknown fields and ignores them.

```json
[
{"step_id":"1","kind":"characterization","description":"Characterization (test-only): test-project-update.sh hand edits move to project-owned keys (conflict -> .ai/state/README.md line 4; untouched-replaced -> .ai/policies/safety.md; missing-recreated -> rm .ai/policies/security.md); synthetic move becomes .ai/policies/coding.md -> code-style.md; new fixture tests/fixtures/project-update/shared-old/ (oldest feature.md, manager.md, most-versioned shared policy, AGENTS.v5.md, SOURCES.txt; no .ai/ in paths). Counts at :79, :110, :114 unchanged.","allowed_files":["tests/test-project-update.sh","tests/fixtures/project-update/migrations-synthetic/0002_move.py","tests/fixtures/project-update/migrations-synthetic/0003_edits.py","tests/fixtures/project-update/shared-old/"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2: frozen, owned by tasks B/C, or out of task; this repo's .ai/ is migrated by a human after close","required_tests":["tests/test-project-update.sh"],"rollback":"git revert (test-only)"},
{"step_id":"2","kind":"implementation","description":"Shared tree, byte-identical copy (additive): ai/ gets 8 policies (production, database, git, release, context-management, tooling, model-routing, review-economy), agents/10, workflows/5, templates/6 = 29, copied with cp; never safety.md/security.md (Q5=A). New tests/test-shared-tree.sh (file set = literal 29, byte-identical to template copies, no .json); model-free scope adds ai/; run-all lists the suite.","allowed_files":["ai/","tests/test-shared-tree.sh","tests/test-shared-prompts-model-free.sh","tests/run-all.sh"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2","required_tests":["tests/test-shared-tree.sh","tests/test-shared-prompts-model-free.sh"],"rollback":"git revert"},
{"step_id":"3","kind":"implementation","description":"REQUIRES P2 (H3 bugfix merged). Install tree, resolver, rendered path, guard data (additive): install.sh installs ai/ to <home>/claude-agentic/ai before install_skills via sibling temp + rename (L3), backup of a differing tree, ai-path +x; dry-run shared line outside block/routing span; RENDER_AI_SHARED/RENDER_AI_RESOLVER; render-codex-agents.py --ai-shared; routing.md line; scripts/ai-path (upward .ai/ search M5, directory is not an override L5, --tree-hash M7); Q4=A pattern in task_protected_patterns. Tests incl. --target both per-home routing.md and guard in-task Read/ai-path allowed, Write denied; guard characterization byte-identical (L7).","allowed_files":["install.sh","scripts/ai-path","scripts/render-codex-agents.py","instructions/routing.md","hooks/ai-path-guard-defaults.json","tests/test-shared-tree.sh","tests/test-install-dry-run.sh","tests/test-codex-agent-render.sh","tests/test-dual-runtime-install.sh","tests/test-codex-install.sh","tests/test-ai-path-guard.sh"],"forbidden_files":["hooks/*.sh","hooks/*.py","hooks/lib/","hooks/ai-git-guard-defaults.json",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2; hook code and deny texts stay unchanged (only guard data changes)","required_tests":["tests/test-shared-tree.sh","tests/test-install-dry-run.sh","tests/test-codex-agent-render.sh","tests/test-dual-runtime-install.sh","tests/test-codex-install.sh","tests/test-ai-path-guard.sh","tests/test-guard-characterization.sh","tests/test-shared-prompts-model-free.sh","tests/test-instruction-budget.sh","tests/test-profiles.sh"],"rollback":"git revert; reinstall previous build; leftover <home>/claude-agentic/ai and ai-path harmless"},
{"step_id":"4","kind":"implementation","description":"Consumers resolve shared paths (prompt, compatible): 10 agent templates state the rule 'project .ai/<path> when it exists, else {{AI_SHARED}}/<path>'; ai-task SKILL.md rule paragraph using $AI_HOME/claude-agentic/ai-path; no model names; ADVERSARIAL REVIEW stays. Writes the G-M8 read-probe checklist; the human fills it before Step 7 (prompted/refused -> SCOPE_CHANGE_REQUIRED for a settings step).","allowed_files":["agents/ai-context.md.tmpl","agents/ai-discovery.md.tmpl","agents/ai-expert.md.tmpl","agents/ai-implementer.md.tmpl","agents/ai-planner.md.tmpl","agents/ai-release.md.tmpl","agents/ai-reviewer.md.tmpl","agents/ai-risk.md.tmpl","agents/ai-security.md.tmpl","agents/ai-tester.md.tmpl","skills/ai-task/SKILL.md","tests/test-install-dry-run.sh","tests/test-shared-tree.sh","tests/test-codex-agent-render.sh",".ai/reports/T-2026-10-13-004/m8-read-probe.md"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2; settings.common.json only through an amended step if G-M8 fails","required_tests":["tests/test-codex-agent-render.sh","tests/test-install-dry-run.sh","tests/test-shared-tree.sh","tests/test-shared-prompts-model-free.sh","tests/test-instruction-budget.sh"],"rollback":"git revert; reinstall"},
{"step_id":"5","kind":"implementation","description":"update.py helpers, added not wired: SHARED resolution, shared_files(), History.hashes(), MigrationContext.template/is_shipped (CRLF-normalised, L4)/require_shared (per file, other installed declared homes, SchemaError exit 2, M2)/unsafe_target (symlink or outside root, M9)/override_note (M6), git_dirty_ai (M4). Runtime wording lives here, never in 0006. build_plan output unchanged.","allowed_files":["skills/project-update/update.py","tests/test-shared-tree.sh"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2","required_tests":["tests/test-shared-tree.sh","tests/test-project-update.sh","tests/test-merge-migration.sh","tests/test-project-adopt.sh","tests/test-scaffold-idempotency.sh"],"rollback":"git revert"},
{"step_id":"6","kind":"implementation","description":"HUMAN HAND-OVER HO1. Router gains a prose '## Shared files' section immediately before '## Doing X -> read Y'; heading line, every table row, non-negotiables and the last section are byte-identical (insertion, not rewrite: H1 root cause); no '|' line in the section; <=4096 B. Agent writes handover/router.md and install-router.sh; the human runs it; the agent rebuilds history (adds one blob). Tests: section once and placed, adopt rows land in the routing table.","allowed_files":[".ai/reports/T-2026-10-13-004/handover/router.md",".ai/reports/T-2026-10-13-004/handover/install-router.sh","skills/ai-init/templates/.ai/AGENTS.md","skills/project-update/history/index.json","skills/project-update/history/blobs/","tests/test-instruction-budget.sh","tests/test-shared-tree.sh"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2; the router template is frozen for the agent and written by the human hand-over","required_tests":["tests/test-instruction-budget.sh","tests/test-shared-tree.sh","tests/test-project-update.sh","tests/test-project-adopt.sh","tests/test-merge-migration.sh","tests/test-scaffold-idempotency.sh"],"rollback":"git revert (template, blob, index); projects that merged the section keep a rule that stays true"},
{"step_id":"7","kind":"implementation","description":"BREAKING. REQUIRES G-M8. DESTRUCTIVE D3 (human runs handover/cutover.sh: compares all 29 before removing any, L2). Defines D1. Migration 0006 (VERSION 6, literal SHARED of 29, M1; no lowercase runtime words, L1): router operation first (create / keep / replace-if-shipped / insert-before-anchor / append), then per copy unsafe->hint (M9), edited->override hint, shipped->require_shared (M2)->delete (gated). update.py: three_way router guard (section exactly once), plain-update delete? [shared] + aggregated override hint (M6), commit-first hint (M4), shipped_ai_files maps ai/, docstring. VERSION 5->6, history SETS maps ai/ (adds, deletes none). SKILL.md docs. New test-migration-0006.sh: router fixtures R1-R6 incl. adopted + edited last row, invariants, gate, Gemini (Q5), M2, M9, L4, L5, M6, M4, M3 byte sweep -> m3-byte-sweep.log, git-route rollback rehearsal. Over the advisory diff budget, not splittable.","allowed_files":["skills/ai-init/templates/.ai/policies/production.md","skills/ai-init/templates/.ai/policies/database.md","skills/ai-init/templates/.ai/policies/git.md","skills/ai-init/templates/.ai/policies/release.md","skills/ai-init/templates/.ai/policies/context-management.md","skills/ai-init/templates/.ai/policies/tooling.md","skills/ai-init/templates/.ai/policies/model-routing.md","skills/ai-init/templates/.ai/policies/review-economy.md","skills/ai-init/templates/.ai/agents/context.md","skills/ai-init/templates/.ai/agents/discovery.md","skills/ai-init/templates/.ai/agents/implementer.md","skills/ai-init/templates/.ai/agents/manager.md","skills/ai-init/templates/.ai/agents/planner.md","skills/ai-init/templates/.ai/agents/release.md","skills/ai-init/templates/.ai/agents/reviewer.md","skills/ai-init/templates/.ai/agents/risk.md","skills/ai-init/templates/.ai/agents/security.md","skills/ai-init/templates/.ai/agents/tester.md","skills/ai-init/templates/.ai/workflows/feature.md","skills/ai-init/templates/.ai/workflows/bugfix.md","skills/ai-init/templates/.ai/workflows/hotfix.md","skills/ai-init/templates/.ai/workflows/investigation.md","skills/ai-init/templates/.ai/workflows/refactoring.md","skills/ai-init/templates/.ai/templates/task-context.md","skills/ai-init/templates/.ai/templates/impact-report.md","skills/ai-init/templates/.ai/templates/review-report.md","skills/ai-init/templates/.ai/templates/release-report.md","skills/ai-init/templates/.ai/templates/architecture-decision.md","skills/ai-init/templates/.ai/templates/implementation-plan.md",".ai/reports/T-2026-10-13-004/handover/cutover.sh",".ai/reports/T-2026-10-13-004/m3-byte-sweep.log","skills/ai-init/templates/.ai/VERSION","skills/project-update/migrations/0006_shared_files.py","skills/project-update/update.py","skills/project-update/SKILL.md","skills/ai-init/SKILL.md","tools/build-template-history.py","skills/project-update/history/index.json","skills/project-update/history/blobs/","tests/test-project-update.sh","tests/test-scaffold-idempotency.sh","tests/test-instruction-budget.sh","tests/test-shared-tree.sh","tests/test-migration-0006.sh","tests/run-all.sh","tests/fixtures/project-update/schema-v5/"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2; the 29 template paths are removed only by the human-run cutover.sh (D3)","required_tests":["tests/test-migration-0006.sh","tests/test-shared-tree.sh","tests/test-project-update.sh","tests/test-scaffold-idempotency.sh","tests/test-instruction-budget.sh","tests/test-project-adopt.sh","tests/test-merge-migration.sh"],"rollback":"single git revert; roll projects at schema 6 back first through the git route"},
{"step_id":"8","kind":"implementation","description":"DESTRUCTIVE D2. Precondition: m3-byte-sweep.log from Step 7. build-template-history.py keep rule made permanent: a blob is written only if a non-shared key references it; index.json byte-identical (not in allowed_files); --dry-run list -> d2-blobs.txt; the human approves 'delete these N blobs' before the real run. Byte sweep replaced by a hash sweep; staleness: shared keys hash only; rehearsal against git HEAD.","allowed_files":["tools/build-template-history.py","skills/project-update/history/blobs/","tests/test-project-update.sh","tests/test-shared-tree.sh","tests/test-migration-0006.sh",".ai/reports/T-2026-10-13-004/d2-blobs.txt"],"forbidden_files":["skills/project-update/history/index.json","hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2; index.json must stay byte-identical","required_tests":["tests/test-project-update.sh","tests/test-shared-tree.sh","tests/test-migration-0006.sh","tests/test-merge-migration.sh","tests/test-project-adopt.sh"],"rollback":"git revert restores the blobs"},
{"step_id":"9","kind":"implementation","description":"Docs and known risks: README :249-294, :366 (shared tree, overrides stop merging, git-first rollback), CONTRIBUTING, docs; known-risks entries (a)-(l) of plan rev 2. README assertion count taken from the end-of-task verify log as a one-line change after the green run. step_tests: none.","allowed_files":["README.md","CONTRIBUTING.md","docs/agents.md","docs/architecture.md","docs/faq.md","docs/getting-started.md","docs/hooks.md","docs/workflows.md",".ai/project/known-risks.md"],"forbidden_files":["hooks/",".github/","instructions/stub.md","skills/ai-init/templates/*.block.md","skills/ai-init/templates/*.minimal.md","skills/ai-init/templates/gitignore.snippet","skills/ai-init/templates/.ai/policies/safety.md","skills/ai-init/templates/.ai/policies/security.md","skills/ai-init/scaffold-ai.sh","skills/project-init/","skills/ai-task/state.py","skills/ai-task/sensors.py","skills/project-update/migrations/__init__.py","skills/project-update/migrations/000[1-5]_*.py","skills/project-update/render_instructions.py","skills/project-update/adopt.py","profiles/","scripts/resolve-profile.py","scripts/merge-codex-config.py","settings.common.json","docs/sdlc/","tests/fixtures/guard-characterization/",".ai/policies/",".ai/agents/",".ai/workflows/",".ai/templates/",".ai/AGENTS.md"],"forbidden_reason":"G list of plan rev 2","required_tests":[],"rollback":"git revert"}
]
```

## Notes for the caller
- **Memory was not saved.** This run had no Write tool, so the decision is not in `~/.claude/agent-memory/ai-expert/`. Suggested entry: "claude-agentic T-2026-10-13-004 plan rev 2 (2026-10-14): Q5=A means safety.md/security.md are project-owned (29 shared files); H1 is solved by a router insertion plus 0006 planning the router first; M2 is exit 2; Q4=A is kept with protected_config rejected because its deny text is frozen."
- **Facts checked at HEAD and relied on above:**
  - The scope guard matches with bash `[[ == ]]`: `*` crosses `/`, braces are not expanded, and a forbidden match beats an allowed one (hooks/ai-scope-guard.sh:85-121).
  - `apply` stops at the first failing item (update.py:1053-1064).
  - A migration conflict without a copy has a precedent in `edit_json` (update.py:432).
  - `block_update` appends a block when its markers are missing (update.py:665).
  - Task-protected paths still allow reads (ai-path-guard.sh:169-174).
  - The protected deny text is "guard configuration and the task state" (:96).
- **Files read for this revision** (all under `/Store/Claude Plugins/claude-agentic/`):
  - Report dir: `.ai/reports/T-2026-10-13-004/{implementation-plan.md, plan-review.md, questions.md, task-context.md, impact-report.md}`, `.ai/templates/implementation-plan.md`.
  - Code: `skills/project-update/{update.py, adopt.py, migrations/__init__.py, migrations/0003_context_diet.py}`, `tools/build-template-history.py`, `hooks/{ai-scope-guard.sh, ai-path-guard.sh, ai-path-guard-defaults.json}`, `install.sh`, `instructions/stub.md`, `skills/ai-init/templates/.ai/AGENTS.md`.
  - Tests and policy: `tests/test-project-update.sh`, `tests/test-project-adopt.sh`, `tests/test-instruction-budget.sh`, `tests/test-shared-prompts-model-free.sh`, `.ai/policies/testing.md`.
  - Outside the repo: `/home/ikakarov/.claude/skills/ai-task/state.py` (cmd_plan:794-822) and `sensors.py` (bite:1030-1137).