# Review ledger — T-2026-10-25-001

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on a1dee72ac: verify_command exit 0 in 311s, run 1, log .ai/reports/T-2026-10-25-001/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| lint on a1dee72ac: pylint $(git ls-files '*.py') exited 12, log .ai/reports/T-2026-10-25-001/lint.log | sensors.py lint | DEFECT, open | sensor |
| diff on a1dee72ac: 2 files / 71 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on a1dee72ac: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on a1dee72ac: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on a1dee72ac: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |

## Manager probe (before the STRONG review)
Scratch root, the hook at the working tree vs HEAD ada69e3 (same probe, `ai-path-guard-defaults.json` beside each).
- `perl -ni`, `ruby -Ku -i -pe` → deny on both (cluster with no-arg switches; generic option before `-i`).
- `perl -wle`, `perl -lane`, `ruby -ne '…/i/…'` → allow on both (no `i` in a no-arg cluster).
- `json.load(open(…)).copy()` → allow on both; `read_text().replace('\n', ' ')` → deny at HEAD, allow now (M2).
- `Path('.ai/state/x').copy(Path('/tmp/y'))` → allow at HEAD, deny now: a false deny on a copy out of the state, like `shutil.copy`; in known-risks.
- `php -r "fopen(…, 'w')"` → allow on both: `INTERP_RE` has no `-r`; older than this task, in known-risks.
- `open(…,'r+')`, `open(f'…', 'w')` → deny on both.
- In-process `WRITE_MODE_RE` at ~4 KB, pads `(a, b),` `open(` `open(a` `,` `(` `open(((` `new (a,` `(a)` `open (a)` `new a` `open a ` `open(x(y)`: all miss, 2–28 ms. The 40 KB grep case is pinned in the test file (289 ms, budget 1000).
