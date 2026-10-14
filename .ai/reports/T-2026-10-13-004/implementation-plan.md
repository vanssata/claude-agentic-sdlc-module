# Implementation plan: T-2026-10-13-004
author: ai-expert (EXPERT tier), 2026-10-13. Decisions: Q2(001)=A, Q3(001)=A, Q1(004)=A, Q2(004)=A, Q3(004)=B.

goal: Shared .ai/ files (10 policies + agents/10 + workflows/5 + templates/6 = 31) ship in the plugin at <home>/claude-agentic/ai/ and are read from there; a project copy overrides. /ai-init copies only project-owned files. Migration 0006 deletes unedited copies (gated), reports edited ones as overrides; VERSION 5→6. History keeps every hash, bytes only for still-merged files.

current_behaviour: scaffold-ai.sh:75-84 copies all of templates/.ai/; update.py:905-922 three-way merges all of it (except project/, reports/, VERSION) with history/blobs as base (:574-628); agents/skills read .ai/... project-relative; history/ = index.json + 198 blobs.

desired_behaviour: template tree = policies/{risk-tiers.json,risk-tiers.md,path-guard.json,testing.md,coding.md}, project/, rules/, state/, reports/, AGENTS.md, VERSION. Shared sources in repo ai/; install.sh copies to <home>/claude-agentic/ai/ (Claude and Codex), renders the absolute path into agents and routing.md, installs <home>/claude-agentic/ai-path. Resolution everywhere: project .ai/<path> if present, else <shared>/<path>. 0006 proposes delete? for each project copy whose sha256 is a shipped version; edited → override hint. index.json keeps all keys/shas; blobs only where a still-merged key references them.

explicitly_unaffected: hooks/*.sh, hooks/*.py code and deny texts (test-guard-characterization.sh byte-identical); state.py, sensors.py, ai-path-guard.sh; runtime-gate.py, profiles/**, resolve-profile.py, merge-codex-config.py (task B); ai-task split, canonical rules (task C); instructions/stub.md and rendered *.block.md/*.minimal.md; skills/project-init/**, migrations 0001–0005, render_instructions.py, adopt.py, scaffold-ai.sh; docs/sdlc/**; .github/workflows/**.

## G — forbidden in every step
hooks/** (except Step 3 if OQ1=A), .github/workflows/**, instructions/stub.md, skills/ai-init/templates/*.{block,minimal}.md, skills/ai-init/templates/gitignore.snippet, skills/project-init/**, skills/ai-task/{state.py,sensors.py}, profiles/**, scripts/{resolve-profile.py,merge-codex-config.py}, skills/project-update/migrations/000[1-5]_*.py, skills/project-update/{render_instructions.py,adopt.py}, docs/sdlc/**, tests/fixtures/guard-characterization/**, this repo's .ai/** (except .ai/reports/T-2026-10-13-004/** and .ai/project/known-risks.md in Step 8).

Precondition: baseline `bash tests/run-all.sh` green at HEAD 8c9cf1b, log under the report dir; known-risks.md:63-68 (test-project-update.sh) confirmed fixed by 8c9cf1b, else stop.

## Step 1 — characterization (test-only)
files: tests/test-project-update.sh, tests/fixtures/project-update/migrations-synthetic/{0002_move.py,0003_edits.py}, tests/fixtures/project-update/shared-old/**
- Project P (:58-67, :94-101): hand edits move to project-owned keys, same meaning. Conflict: workflows/feature.md → a line of .ai/state/README.md differing between oldest blob and current (fallback .ai/AGENTS.md). "Untouched replaced": bugfix.md → the other of those two. "Missing recreated": rm templates/review-report.md → rm rules/README.md. Counts at :79, :110, :114 unchanged.
- Synthetic move (:372-377, :401-441, 0002/0003): .ai/workflows/bugfix.md→fix.md becomes .ai/policies/coding.md→.ai/policies/code-style.md; never-existed pair stays; --files and rename_step follow.
- shared-old/: oldest shipped bytes of workflows/feature.md, policies/safety.md, agents/manager.md from history/blobs, SOURCES.txt (key, sha). No `.ai/` in paths.
- must not change: product files; assertion count and verbs. Test: test-project-update.sh green.

## Step 2 — shared tree, byte-identical copy (additive)
files: ai/**, tests/test-shared-tree.sh (new), tests/test-shared-prompts-model-free.sh, tests/run-all.sh
- ai/{policies/{production,database,git,release,context-management,safety,tooling,security,model-routing,review-economy}.md, agents/<10>.md, workflows/<5>.md, templates/<6>.md} copied with cp.
- test-shared-tree.sh: file set equals the list; each byte-identical to skills/ai-init/templates/.ai/<rel> (temporary, flipped in Step 6); no .json under ai/. Model-free scope() (:16-21) adds `find ai -type f`; run-all lists the suite.
- must not change: scaffold, update, install output.

## Step 3 — install tree, resolver, rendered path (additive)
files: install.sh, scripts/ai-path (new), scripts/render-codex-agents.py, instructions/routing.md, tests/{test-shared-tree.sh,test-install-dry-run.sh,test-codex-agent-render.sh}; if OQ1=A also hooks/ai-path-guard-defaults.json, tests/test-ai-path-guard.sh
- claude_apply and codex_apply replace <home>/claude-agentic/ai/ from ai/ (differing tree backed up to <home>/backups/claude-agentic-ai/, install_skills pattern :532-547); install <home>/claude-agentic/ai-path +x.
- Dry run prints `   shared:  claude-agentic/ai (31 files), claude-agentic/ai-path` in the would-install list (:508-515, :946-952), never between `== CLAUDE.md managed block:` and `== routing.md`.
- RENDER_AI_SHARED / RENDER_AI_RESOLVER exported to render_claude_files (:400-412) and codex_render_files (:906-927); render-codex-agents.py --ai-shared PATH (default expanded ${CODEX_HOME:-~/.codex}/claude-agentic/ai), substitutes {{AI_SHARED}} before the placeholder check (:110); install.sh:904 passes it.
- routing.md: one line per runtime naming {{AI_SHARED}}/, the override rule, {{AI_RESOLVER}} <path>.
- scripts/ai-path [--root DIR] <path>: strips leading .ai/; exit 2 on absolute or `..`; prints <root>/.ai/<path> if it exists, else <shared>/<path>, else exit 1 with reason. Shared: $CLAUDE_AGENTIC_SHARED, else <dir>/ai, else <dir>/../ai. Root default $PWD.
- OQ1=A: add `(^|/)\.(claude|codex)/claude-agentic/(ai/|ai-path$)` to task_protected_patterns; deny texts unchanged.
- tests: resolver (override wins, fallback, missing=1, traversal=2, installed layout); scratch install per runtime gives tree identical to ai/; routing.md fully rendered.

## Step 4 — consumers resolve shared paths (prompt, compatible)
files: agents/*.md.tmpl, skills/ai-task/SKILL.md, tests/test-install-dry-run.sh, tests/test-shared-tree.sh
- 10 agents: "Read first" names paths relative to .ai/ with the rule "project .ai/<path> when it exists, else {{AI_SHARED}}/<path>; .ai/ paths inside them resolve the same way".
- ai-task/SKILL.md: one rule paragraph after the AI_HOME block using "$AI_HOME/claude-agentic/ai-path" <path>; :10-11 follow it; other references covered by the rule.
- No model names; ADVERSARIAL REVIEW stays; frontmatter/placeholders unchanged. Test: rendered agents contain absolute path, no `{{`.

## Step 5 — update.py helpers (added, not wired)
files: skills/project-update/update.py, tests/test-shared-tree.sh
- SHARED resolution ($CLAUDE_AGENTIC_SHARED, dirname(SKILLS)/claude-agentic/ai, dirname(SKILLS)/ai); shared_files(); History.hashes(key) from index.json following chain(); MigrationContext.shared_paths(), is_shipped(path,data), require_shared() (SchemaError naming path and install.sh), override_note(path). Runtime/plugin wording lives here (0006 names neither claude nor codex, test-project-update.sh:490-491).
- must not change: build_plan output. Tests: classify current/old/edited bytes; hashes() without blobs.

## Step 6 — cut-over (breaking; human hand-over for frozen paths)
files (human hand-over): skills/ai-init/templates/.ai/policies/{the 10}.md, skills/ai-init/templates/.ai/{agents,workflows,templates}/**, skills/ai-init/templates/.ai/AGENTS.md
files (agent): .ai/reports/T-2026-10-13-004/handover/{cutover.sh,router.md}, skills/ai-init/templates/.ai/VERSION, skills/project-update/migrations/0006_shared_files.py, skills/project-update/{update.py,SKILL.md}, skills/ai-init/SKILL.md, tools/build-template-history.py, skills/project-update/history/{index.json,blobs/*}, tests/{test-project-update.sh,test-scaffold-idempotency.sh,test-instruction-budget.sh,test-project-adopt.sh,test-shared-tree.sh,test-migration-0006.sh,run-all.sh}
order: (1) agent writes router.md and cutover.sh (set -euo pipefail; cmp each ai/<rel> with its template copy, abort on difference; rm the 31; cp router.md to templates/.ai/AGENTS.md). (2) human runs `bash .ai/reports/T-2026-10-13-004/handover/cutover.sh`. (3) agent: code, tests, VERSION 5→6, `python3 tools/build-template-history.py` (adds blobs, deletes none). (4) step tests.
- 0006 (VERSION=6, MOVES=[]): require_shared() first; for each shared path present: is_shipped → ctx.delete (delete? until --confirm-delete; VERSION held, update.py:874-880), else override hint. Paths outside the shared set untouched (policies/adopted/**, project workflows).
- update.py: shipped_ai_files() (:1127) includes shared tree; one overrides hint when 0006 not pending; hint when the other runtime home has skills/project-update but no claude-agentic/ai; docstring :22-29.
- build-template-history: SETS maps ai/ to prefix ai-init/.ai/ (keys kept).
- Router (Q2(004)=A): project files here; shared at <home>/claude-agentic/ai/; same-path copy overrides; `ai-path <path>` shows which; non-negotiables kept; ≤4096 B; no ADVERSARIAL REVIEW.
- Tests: test-project-update.sh OLD builder (:37-49) skips shared keys, staleness (:18-35) and key accounting (:523-560) walk ai/ as ai-init/.ai/, each changed count listed with its key; test-scaffold-idempotency.sh:21-25 shared paths absent from scaffold, present in ai/; test-instruction-budget.sh:176-177 also probes $PLUGIN_ROOT/ai/$probe; test-project-adopt.sh:623 removes .ai/rules/README.md instead of security.md; test-shared-tree.sh invariant "no path in both trees"; new test-migration-0006.sh: v5 fixture (current, old from shared-old/, edited, project-only workflow, policies/adopted/x.md); dry run writes nothing, --check prints `schema 5 -> 6, N deletion(s) a human must confirm, the schema stays at 5…`; plain --apply keeps 5; CLAUDECODE=1 without tty exits 5; AI_UNATTENDED=1 --confirm-delete tester deletes exactly the shipped copies, originals kept with modes, migration.json confirmed_by/via, VERSION 6, second run 0 changes + override hint; CLAUDE_AGENTIC_SHARED=/nonexistent exits 2 writing nothing; rollback rehearsal.
- SKILL.md: project-update documents 0006, override rule, ordering (install every home first), rollback; ai-init one sentence.
- must not change: project-owned merges and mirror sync; block_update; 0001–0005; --check line shapes; delete gate; guard texts; stub/blocks.
- Over the advisory diff budget; not splittable (update.py:472-474) — report, do not split.

## Step 7 — drop blobs of shared-only versions (destructive, approval D2)
files: tools/build-template-history.py, skills/project-update/history/{index.json,blobs/**}, tests/{test-project-update.sh,test-shared-tree.sh}
- tool --dry-run lists the N blobs; human approves "delete these N blobs" before the real run. Keep a blob referenced by any non-shared key; index.json byte-identical. Staleness test: non-shared current templates have hash+blob; shared have hash only; no blob referenced only by shared keys.
- rehearsal: `git show HEAD:…/blobs/<dropped sha> | sha256sum` equals name; `D` count in git status equals N.

## Step 8 — docs and known risks
files: README.md, CONTRIBUTING.md, docs/*.md (not docs/sdlc/**), .ai/project/known-risks.md
- README :249-294, :366 updated. Known risks: (a) guard Bash write detection misses rm/mv/cp destinations on frozen paths (ai-path-guard.sh:273-337); (b) .ai/agents/ not task-protected (defaults.json:46), now an override path; (c) installed tree unguarded (only if OQ1=B); (d) deny texts name .ai/policies/{safety,security,release}.md, reached via the router after migration; (e) Gemini/Junie-only machines have no shared tree; (f) this repo's overrides shadow what it ships.

## Verification
verify_command `bash tests/run-all.sh` once to the end; e2e `bash tests/test-end-to-end.sh` once after (install → scaffold flow is reached).

## Compatibility
Install first is safe (copies are overrides, same bytes). Migration per project needs a human; until --confirm-delete VERSION stays 5. Old plugin + VERSION 6: update.py exits 2 "update the plugin" (:864-866, --check :1274-1277); old agents read "when they exist" → soft degradation; old /ai-init re-adds the 31 copies → reported as overrides. state.py, sensors.py, hooks unaffected. Teams upgrade plugin before the VERSION 6 commit. Dual runtime: install both homes before confirming.

## Migration impact
No locks (apply checks sha per file, exit 3 on mismatch, re-run recovers); run with no task in flight. ≤31 files/project; seconds. Order: plugin release → install.sh every home → /project-update dry run → human `update.py <proj> --apply --confirm-delete <name>` → human commit.
This repo's .ai/ (post-close, human): ./install.sh; dry run (expect delete? for unedited, override hints incl. policies/review-economy.md, router update, schema held at 5); --apply --confirm-delete in a terminal, no task in flight; follow-up task per remaining override; human commits.
Destructive ops, each named approval: D1 0006 deletion (per project, --confirm-delete); D2 Step 7 blob removal; D3 cutover.sh removing 31 template copies (recoverable, cmp-checked).

## Rollback
Project (rehearsed in test-migration-0006.sh "rollback"):
    R=.ai/reports/project-update-<date>
    jq -r '.ops[]|select(.action=="delete" and .migration==6)|.path' "$R/migration.json" | while IFS= read -r p; do mkdir -p "$(dirname "$p")"; cp -p "$R/original/$p" "$p"; done
    printf '5\n' > .ai/VERSION
Git route: `git restore --source=<commit before> --staged --worktree -- .ai`. Test asserts byte+mode identical restore, VERSION 5, schema-5 registry --check exit 0/1 on restored and exit 2 on migrated, new plugin re-plans same delete? list. Fallback if migration.json untrusted: `cp -pR "$R/original/.ai/." .ai/`.
Plugin: one revert per step commit (Step 6 single revert); roll projects back before downgrading; leftover <home>/claude-agentic/ai{,-path} harmless. Blobs: git revert of Step 7.

## Observability
Working: install prints shared tree line; ai-path prints shared path; dry run `delete? … [0006]` and `N deletion(s) awaiting --confirm-delete`; after confirm migration.json deletions[] with confirmed_by/via, VERSION 6, --check "project matches". Failing: exit 2 "shared tree missing — run install.sh"; ai-path exit 1; old plugin "says schema 6"; persistent override hint; other-runtime hint.

## Risks
Prose path resolution not enforced (mitigated by rendered absolute paths, ai-path); stale unconfirmed copies shadow new versions; CRLF/stale index count as edited (safe); installed tree unguarded (OQ1); no shared files on Gemini/Junie-only; test changes could hide regressions (Step 1 on old code; Step 6 lists counts); overlap with tasks B/C; this repo dogfoods via overrides.

## Open questions
- OQ1 (blocking): add the installed-tree pattern to task_protected_patterns in Step 3? A add (recommended) / B leave, record known-risk (c).
- OQ2: human hand-over for frozen template paths (default) vs temporary allow_patterns.
- OQ3: Gemini/Junie-only: 0006 deletes as usual (default).
- OQ4: blob keep rule keeps also project/**, gitignore snippets, skeleton/minimal (read by 0003 via ctx.shipped()).
- OQ5: source at repo-root ai/ (default) vs manifest.
