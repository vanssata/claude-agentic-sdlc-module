# Adversarial review — T-2026-10-13-004 (ai-reviewer, STRONG)

Verdict: blockers_open

- BLOCKER — skills/ai-init/SKILL.md:176 (also :158-160): "In tooling.md, fill Project specifics" is unconditional; tooling.md (and database.md, release.md) are shared and still carry `## Project specifics` placeholders (ai/policies/tooling.md:42,101; database.md:38; release.md:43). With no override, ai-path resolves to <home>/claude-agentic/ai/policies/tooling.md, unprotected outside a task: /ai-init in project A writes A's MCP servers into the policy every project reads (reverted silently by the next install), or creates a fragment override that hides the whole shared policy. Known risk (m) understates it. Cause: plan — the fill instruction was not moved with the files.
- MEDIUM — update.py:741-747 / 0006:99-107: edited routers (renamed routing heading; appended non-negotiable; edited last list line) get `conflict .ai/AGENTS.md` on every later --apply, because three_way drops the current template as a base. test-migration-0006 R4 does not assert it.
- MEDIUM — rollback text inconsistent: README, project-update SKILL.md ("git checkout HEAD -- .ai", useless after the post-migration commit), known-risks (j) disagree on VERSION; the test shows VERSION stays 6. Fallback must say `printf '5\n' > .ai/VERSION`.
- LOW — known risk (c): `install.sh --dry-run` does not show a changed installed tree; only the real install's backup line or `ai-path --tree-hash` does.
- LOW — known risk (e): 29 files unreachable, not 27 (plan typo).
- LOW — 0006:102: CRLF edited router: anchor `…\n` missed, section appended at end with LF (mixed endings).
- LOW — sensors.py:513-515 + risk-tiers.json unbudgeted docs scope: *.md never scope-checked; ai/** scores as docs/T0. Outside task: known-risks.
- INFO — router "every other path ships with the plugin" also covers adopt rows; README label `[shared]` vs `[0006]` at schema 5; `ai-path --root /nonexistent` exits 0; symlinked override honoured; hints name `ai-path` not on PATH; require_shared ignores CLAUDE_CONFIG_DIR and reads CODEX_HOME (install.sh uses CODEX_DIR); G-M8 row 2 inferred.
- INFO — duplicates sensor red is pre-existing (QUESTIONS_NEEDED block at HEAD).

Clean: 0006 ordering/gating, require_shared, unsafe_target, is_shipped, install.sh --target both run for real, ai-path edge cases, history rebuild byte-identical, scope, tests not weakened, most docs.

## Re-review 1 (after R1): blockers_open
- BLOCKER router_merge early return `t_rest in rests` silenced every edited router based on an older version (stale router reported up to date); BLOCKER S8 test changed to pin that silence. LOWs: renamed follow heading, CRLF merge path, git-restore reverts later .ai/ commits, known risk (m) residual, (i) line ref. Fixed in R2.

## Re-review 2 (after R2): passed
All named findings closed. Left open, recorded in known-risks (s)-(v):
- LOW put_section takes the first matching heading line, also inside a fenced block or a duplicated heading (update.py:841-843).
- LOW a section at the very end without a final newline glues onto the next heading (update.py:843).
- LOW one CRLF line switches the whole router to CRLF on merge (update.py:814,830).
- INFO changes to the template's `## Shared files` section never reach a router that has the section; a migration that changes the list must rewrite it.
