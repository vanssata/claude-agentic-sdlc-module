# Review ledger — T-2026-10-14-002

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on cd54c368b: verify_command exit 0 in 292s, run 1, log .ai/reports/T-2026-10-14-002/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on cd54c368b: 7 files / 159 lines (T2 task budget 15 / 400) | sensors.py diff | CONFIRMED | sensor |
| rescore on cd54c368b: T2 — scopes: source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on cd54c368b: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on cd54c368b: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |

## Manager probe (render_instructions.find_block, before the review)

| input | outcome |
|---|---|
| lowercase `codex-agentic` pair, bytes | found; offsets in bytes, markers returned as bytes |
| CRLF legacy pair | found; the block keeps its CRLF line ends |
| `Codex-agentic:start` with `codex-agentic:end` | None — a pair must match its own spelling (same as the old update.find_block) |
| two legacy pairs in one file | the first pair; the second is left in place (same class as T-2026-10-14-001's "current then legacy") |
| non-ASCII text before the pair, str and bytes | both slice the block correctly in their own units |
| adopt Candidate on a pristine legacy block | `edited` is False after current_markers; `text.replace(block, shipped)` works on the verbatim slice (tests/test-project-update.sh: no `split?` hint) |
| install.sh managed_block on a legacy pair | renamed then updated in place, note "renamed the legacy Codex-agentic markers"; reinstall keeps one block (tests/test-codex-install.sh) |
