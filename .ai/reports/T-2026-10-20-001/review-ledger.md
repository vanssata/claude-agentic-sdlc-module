# Review ledger — T-2026-10-20-001

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on 0922a06d8: verify_command exit 0 in 312s, run 1, log .ai/reports/T-2026-10-20-001/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on 0922a06d8: 2 files / 57 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 0922a06d8: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 0922a06d8: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 0922a06d8: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| the 7 new tests fail at HEAD (bite, by hand): 6 fails — 6000 sh -c / eval and both 100000-segment cases on time (13.4 s, 12.9 s, 6.5 s, 6.5 s), 100000 + rm a.txt and 65 sh -c on verdict | manual run of tests/test-ai-path-guard.sh before the fix (273 passed, 6 failed) | CONFIRMED | manager probe |
| original probe table after the fix: every row ≤ 0.5 s except the 200 KB single strings (1.1–1.7 s, out of scope); verdicts as planned | scratchpad probe.sh | CONFIRMED | manager probe |
| a candidate with nothing after `eval`/`-c` (`eval  ;` ×100000 + rm a.txt) was uncounted: clock deny at 5.6 s; now counted, deny by the cap in 0.85 s | inline probe | FIXED in step 1 | manager probe |
| `rm x;` ×300 allow 2.0 s, ×1000 clock deny 5.1 s: per-segment realpath fork in the movers pass, older than this task | inline probe | RISK, recorded in known-risks.md | manager probe |
| deny-side variants (bash -lc, /bin/sh -c, find -exec sh -c, eval "…") naming a control file: not re-probed here (the live path guard refuses the probe command itself); covered by the existing sh -c / eval tests, all green | — | UNVERIFIED by probe | manager probe |
