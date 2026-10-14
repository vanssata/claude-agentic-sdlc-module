# Release report: T-2026-10-13-004

task: T-2026-10-13-004 (feature). Shared `.ai/` policies, agent contracts, workflows and templates load from the plugin root; the project copy becomes an override. Migration 0006 deletes unedited shared copies behind `--confirm-delete`. History blobs are removed. `/ai-init` copies only project-owned files.
risk_level: T6 (breaking cut-over plus three destructive operations: D1, D2, D3)

summary:
- Nothing is committed, pushed or deployed. Everything below is uncommitted in the working tree.
- Open BLOCKER/HIGH: none. The initial review had one BLOCKER, and re-review 1 added another (router_merge silenced edited routers). Both were fixed (R1, R2), and re-review 2 passed. The security review passed with no blockers.
- Not verified: the plan requires pylint 10.00, and pylint is not installed on this machine. Lint is UNAVAILABLE, so that requirement is unproven.
- Sensors at close:
  - tests: STALE. The README count and the known-risks/review text were edited after suite run 3 (docs only). Suite run 3 itself is green.
  - lint: UNAVAILABLE (see above).
  - duplicates: RED, pre-existing. It comes from the QUESTIONS_NEEDED block already at HEAD.
  - plan_sections: RED. The rev2 plan lacks the template's headings.
  - diff budget: over the advisory budget (131 files / 6,633 lines per the sensor). Most of it is the 90 blob deletions.
- Remediation:
  - R1 (Q7=B, chosen by the human) covers the ai-init "Project specifics" BLOCKER, shared set = 29, the router recurring conflict, and related items.
  - R2 fixes the re-review blocker in router_merge.
- Deliberate test-expectation changes (2):
  - test-migration-0006: the R7 conflict became a quiet merge. The reviewer judged this legitimate.
  - test-project-update S8: restored to 2 conflicts, which is stronger than HEAD.
- Residual accepted risks (a)-(v) are in known-risks.md.

affected_modules: install.sh and `scripts/ai-path` (shared tree install and resolver); `hooks/ai-path-guard-defaults.json` (guard data); 10 agent templates and `scripts/render-codex-agents.py`; `skills/project-update` (`update.py`, migration 0006, history); `skills/ai-init` (SKILL.md, scaffolded templates, now 29 fewer shared copies); `instructions/routing.md`; `tools/build-template-history.py`; tests; docs (README, CONTRIBUTING, docs/*); `.ai/project/known-risks.md`.

files_changed: `git diff --stat HEAD` shows 161 files, +787/-6,480.
- 29 shared templates under `skills/ai-init/templates/.ai/` are deleted.
- 90 history blobs are deleted. The list is in d2-blobs.txt.
- Added: the shared `ai/` tree, tests (`test-shared-tree.sh`, `test-migration-0006.sh`), the `shared-old` fixture, and the handover scripts.
- The rest is modified: the files listed under affected_modules.
- Run `git status --short` for the exact list.

behaviour_changed:
- Shared policies, agents, workflows and templates resolve from `<home>/claude-agentic/ai/`. A project `.ai/<path>` wins when it exists.
- The router gains a `## Shared files` section.
- Migration 0006 (schema 5 -> 6) offers `delete?` for unedited shared copies. It acts only with `--confirm-delete`. Without the flag it writes the router and holds VERSION at 5.
- An old plugin against VERSION 6 exits 2 ("update the plugin").
- `/ai-init` scaffolds project-owned files only. The 7 project-owned policies stay binding.
- Edited overrides stop receiving upstream merges (risk h).

behaviour_preserved (what was checked, and how):
- Full suite, run 3: 27 suites, 2,560 assertions, 0 failed (tests-suite-3.log, "all suites passed").
- End-to-end, run 3: 41 passed, 0 failed (tests-e2e-3.log).
- Byte sweep (m3-byte-sweep.log): 29 keys, 90 versions, 11 rounds. Zero not deleted, and zero flipped that were not an override.
- G-M8 read probe (m8-read-probe.md): all 8 runtime/context rows were allowed. Claude Code and Codex (via `codex exec`) both read the shared copy where the project has no copy. The agent recorded the results at the human's request, so this is not a hand-filled check.
- Compatibility: the additive Steps 2-6 leave copies as same-byte overrides, so installing first is safe. The Step 6 router is true before and after 0006.
- Unchanged by design: state.py, sensors.py, hooks.
- Characterization test (Step 1): hand edits moved to project-owned keys, with counts unchanged.

database_changes: none (no database). File-level migration 0006 per project: at most 29 deletions plus 1 router write; seconds; no locks. Apply checks the sha per file, exits 3 on a mismatch, and a re-run recovers. Run with no task in flight. Reversible via git (see rollback). Without a commit, only the deletions are restorable.

api_changes: no events or payloads. Interfaces: new `scripts/ai-path` CLI (`--tree-hash`, `--root`); `.ai` schema VERSION 5 -> 6 (an old plugin refuses VERSION 6); agent prompts state the "project `.ai/<path>` else plugin `ai/<path>`" rule. Not backward compatible for the old plugin against a VERSION 6 project; this is intended and guarded.

configuration_changes: new env `CLAUDE_AGENTIC_SHARED` redirects the shared tree. Production code honours it, not just tests (risks o; the security review suggests gating it behind CLAUDE_AGENTIC_TEST=1, not done). New guard pattern in `hooks/ai-path-guard-defaults.json`. New `--confirm-delete <name>` flag on update.py. No feature flags.

external_integrations: none called. Codex was used only as a local `codex exec` for the read probe. `install.sh` writes to the Claude and Codex homes (Gemini/Junie get no shared tree, risk e).

tests: see behaviour_preserved. Re-run needed: the tests sensor is STALE because docs were edited after run 3, so re-run `verify_command` once to refresh it. Lint (pylint) was never run; pylint is not installed here. Failing: none. RED sensors are listed in summary.

security_review: passed, no blockers (security-report.md). Findings: 1 MEDIUM, 2 LOW, 3 INFO.
- The MEDIUM (shared set = whatever is on disk): R1 lists "shared set=29" as a fix; confirm in review-ledger.md.
- The symlink re-check at apply time (LOW) and the guard pattern for the bare `ai` directory (LOW) are accepted and recorded as risks (n), (a).

known_risks: `.ai/project/known-risks.md`, section "Shared tree (T-2026-10-13-004)", entries (a)-(v), all accepted and open unless marked. Most relevant:
- (a) guard misses rm/mv/cp destinations on frozen paths.
- (b) `.ai/agents/` is not task-protected.
- (f) this repo's own overrides shadow what it ships.
- (h) overrides cannot be detected as "behind".
- (j) the no-commit rollback restores deletions only.
- (k) two-rename install window.
- (s)-(u) router_merge edge cases.

monitoring: after deploy, watch these:
- install prints `shared: claude-agentic/ai (29 files)`.
- The dry run shows `update .ai/AGENTS.md [0006]` before `delete?`, and `N deletion(s) awaiting --confirm-delete`.
- After confirmation, `migration.json` has `deletions[]` with confirmed_by/via, VERSION is 6, and `--check` says "project matches".
- Failure signals: exit 2 "shared tree at <home> lacks N file(s)", `ai-path` exit 1, a persistent override hint, the commit-first hint, a router conflict from the three_way guard.

rollback:
- Plugin: `git revert` per step commit, newest first. Step 7 is a single revert. Reverting Step 8 restores the blobs. Before the commit exists, nothing needs reverting.
- Projects first, before downgrading the plugin below Step 7: `git restore --source=<commit before the migration> --staged --worktree -- .ai`. Then keep the project off `/project-update --apply` until the plugin is downgraded.
- No commit of `.ai/`: fallback restores deletions only, from `.ai/reports/project-update-<date>/original/`. Then `printf '5\n' > .ai/VERSION`. Router and other merges stay.
- A leftover `<home>/claude-agentic/ai{,-path}` is harmless.
- D3 cutover is recoverable from git.

manual_checks:
- Re-run `verify_command` and `e2e_command` once to refresh the STALE tests sensor.
- Run pylint on a machine that has it (required 10.00, never verified).
- Run `./install.sh` in every Claude and Codex home, and confirm the "29 files" line.
- Run the `/project-update` dry run in this repo. Expect the router insert, `delete?` for unedited copies, override hints (including `policies/review-economy.md`), and VERSION held at 5.
- Resolve each override with its own follow-up task.
- Check that a teammate's home has the shared tree before committing VERSION 6.
- After 0006, confirm a session in a project without `.ai/policies/git.md` still reads the shared copy.

review_findings: none open. Initial review: 1 BLOCKER (ai-init "Project specifics"), plus MEDIUM/LOW items. Re-review 1: 1 BLOCKER (router_merge silencing). Re-review 2: passed. All named findings closed. Left open as accepted risks (s)-(v). Ledger: review-ledger.md.

human_approval_required: yes
Approving, in order:
1. The merge: the commit of the working tree, including the deletion of the 29 template files and the 90 blobs (D2).
2. Running `./install.sh` in each home.
3. D1: in a terminal, per project, `update.py <proj> --apply --confirm-delete <name>` (this repo first, after the dry run).
Not approved by this report: any deploy beyond that; no deploy exists for this plugin.
