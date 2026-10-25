# Review ledger — T-2026-10-25-007

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on 1383d3a9e: verify_command exit 0 in 337s, run 1, log .ai/reports/T-2026-10-25-007/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| lint on 1383d3a9e: pylint $(git ls-files '*.py') exited 12, log .ai/reports/T-2026-10-25-007/lint.log | sensors.py lint | DEFECT, open | sensor |
| diff on 1383d3a9e: 3 files / 46 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 1383d3a9e: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| duplicates on 1383d3a9e: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| tests on 1383d3a9e: verify_command exit 0 in 337s, run 1, log .ai/reports/T-2026-10-25-007/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| lint on 1383d3a9e: pylint $(git ls-files '*.py') exited 12, log .ai/reports/T-2026-10-25-007/lint.log | sensors.py lint | DEFECT, open | sensor |
| diff on 1383d3a9e: 3 files / 46 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 1383d3a9e: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| duplicates on 1383d3a9e: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |

## Manager probe (parse_rule, real code)

- `./lib`→`lib`, `lib//x`→`lib/x`, `lib/./y`→`lib/y`, `lib/.//./z/`→`lib/z`; `./`, `.`, `./.`, `././`→`.`
- `//x`, `a/../b`, `a/b/..` still refused (raw check runs before normpath); `~x`, `lib\\x` pass through unchanged (as before)
- `[./lib, lib, lib/, ./lib/., b]`→`['lib', 'b']`: duplicates dropped, first-seen order kept
- lint red: 3 pylint findings, none on a changed line (`sensors.py:408`, `update.py:268`, `build-template-history.py:39`) — pre-existing
