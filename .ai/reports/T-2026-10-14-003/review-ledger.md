# Review ledger — T-2026-10-14-003

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on de51e05dd: verify_command exit 0 in 280s, run 1, log .ai/reports/T-2026-10-14-003/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on de51e05dd: 3 files / 49 lines (T2 task budget 15 / 400) | sensors.py diff | CONFIRMED | sensor |
| rescore on de51e05dd: T2 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on de51e05dd: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on de51e05dd: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |

## Manager probe (scaffold-ai.sh instruction_file, before the review)

Run through the real script with `--runtime codex` on a prepared AGENTS.md.

| input | outcome |
|---|---|
| legacy `Codex-agentic` / `codex-agentic` full pair | nothing appended; file left byte-for-byte (tests/test-scaffold-idempotency.sh) |
| legacy start marker only (half pair) | nothing appended — same shape as the old current-pair check, which also looked at the start marker alone |
| legacy end marker only | block appended (as before for a current end-only file) |
| rule marker only `claude-agentic:rule:foo:start` | block appended — the regex needs `agentic:start -->` directly, so rule markers do not count as the block (unchanged) |
| CRLF legacy pair | nothing appended |
| legacy pair after a current pair | nothing appended; both left in place (same residual as T-2026-10-14-002) |
| no marker | block appended (unchanged) |
| residual (d) `update.py` budget hint | not reproducible: `budget_hints` reads `plan.read(name)` = the planned content; `block_update` runs first and plans a rename on every legacy path, so the hint sees the current pair. Pinned by the new test in tests/test-project-update.sh; no code change. |
