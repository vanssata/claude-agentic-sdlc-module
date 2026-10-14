# Security review — T-2026-10-13-004 (ai-security, STRONG)

Verdict: passed (no blockers).

## Findings
- MEDIUM — update.py:215-223 shared_files(), used by shared_update :822: the shared set is whatever is on disk in the installed tree (or $CLAUDE_AGENTIC_SHARED), not 0006's literal SHARED of 29. Reproduced: a tree with extra policies/security.md and VERSION makes a plain run offer `delete? .ai/VERSION [shared]` and `.ai/policies/security.md [shared]`. Human gate and "unedited" check still hold. Fix: restrict shared_update and require_shared to the declared set; extra installed files are a hint only.
- LOW — hooks/ai-path-guard-defaults.json:54: pattern needs `ai/` plus more path; the bare `<home>/claude-agentic/ai` dir or its parent never match (rm -rf/mv/cp -r of the whole tree). Risk (a) understated. Fix: `(ai(/|$)|ai-path$)` + negative test, in the hooks task.
- LOW — update.py:1260-1291: unsafe_target runs at plan time only; a parent dir swapped for a symlink between plan and os.remove is followed. Fix: re-run unsafe_target in apply_item before keep_original/os.remove.
- INFO — CLAUDE_AGENTIC_SHARED honoured in production (scripts/ai-path:24, update.py:67); require_shared then checks only that tree. Suggest gating behind CLAUDE_AGENTIC_TEST=1.
- INFO — custom CLAUDE_DIR/CODEX_DIR not covered by guard pattern; require_shared reads CODEX_HOME, install.sh writes CODEX_DIR.
- INFO — install_shared keeps one backup only (install.sh:570-579).
- Related to (b): ai-path without --root takes the nearest .ai/ upward; a nested .ai/ created mid-task can redirect resolution.

## Examined and clean
Human gate for --confirm-delete (update.py:1402-1415, ai-path-guard.sh:239-259, test-migration-0006.sh:82); guard denies writes into both installed trees (test-ai-path-guard 116/0); ai-path input validation; install_shared quoting and rm -rf targets; 0006 symlink/outside-root handling (test-migration-0006.sh:249-263); content TOCTOU re-hash (update.py:1147); deletion audit in migration.json; history keep rule; router guard (update.py:744-747); no secrets, no new deps.
