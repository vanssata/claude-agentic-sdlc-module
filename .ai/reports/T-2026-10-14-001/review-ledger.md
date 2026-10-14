# Review ledger — T-2026-10-14-001

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on 5f2746ee4: verify_command exit 0 in 314s, run 1, log .ai/reports/T-2026-10-14-001/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on 5f2746ee4: 2 files / 91 lines (T2 task budget 15 / 400) | sensors.py diff | CONFIRMED | sensor |
| rescore on 5f2746ee4: T2 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 5f2746ee4: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 5f2746ee4: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |

## Manager probe (find_block, before the review)

| input | outcome |
|---|---|
| no markers / legacy start only / legacy end before start / current start with legacy end | None — falls to the pre-existing "managed block appended" path, as before this change |
| legacy pair `Codex-agentic` and lowercase `codex-agentic` | found, both markers, block renamed to the current pair |
| current pair followed by a legacy pair | the current pair wins; the legacy pair is left in place (odd file, out of scope) |
| edited legacy block whose three-way merge fails | markers renamed, edit kept, note "kept as edited"; the next run sees an edited current block and conflicts with the plugin's copy beside it (tested) |
| tests on 852cfd34c: verify_command exit 0 in 287s, run 2, log .ai/reports/T-2026-10-14-001/tests-suite-2.log | sensors.py tests | CONFIRMED | sensor |
| diff on 852cfd34c: 2 files / 107 lines (T2 task budget 15 / 400) | sensors.py diff | CONFIRMED | sensor |
| rescore on 852cfd34c: T2 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 852cfd34c: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 852cfd34c: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
