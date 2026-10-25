# Review ledger — T-2026-10-25-004

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on a74a7d907: verify_command exit 0 in 336s, run 1, log .ai/reports/T-2026-10-25-004/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| lint on a74a7d907: pylint $(git ls-files '*.py') exited 12, log .ai/reports/T-2026-10-25-004/lint.log | sensors.py lint | DEFECT, open | sensor |
| diff on a74a7d907: 8 files / 874 lines (T3 task budget 30 / 800) — budget: over — 874 lines > 800 (advisory) | sensors.py diff | CONFIRMED | sensor |
| rescore on a74a7d907: T3 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on a74a7d907: 1/1 finished steps name tests that exist | sensors.py traceability | CONFIRMED | sensor |
| duplicates on a74a7d907: 35 block(s) of >= 8 lines appear twice: skills/ai-init/templates/.ai/policies/weight.json:2 ~ skills/project-update/history/blobs/7f3859c34035fe32abf937eebdd724 | sensors.py duplicates | DEFECT, open | sensor |
| bite on a74a7d907: must_fail: 1 test(s), exit 1 at base; tree restored a74a7d907 | sensors.py bite | CONFIRMED | sensor |

## Manager probe (2026-10-25, before the BALANCED review)

| input | outcome | label |
|---|---|---|
| `--files /etc/passwd` | accepted, normalised to `../../../etc/passwd`, read and scored scope 1 | PROBE: outside-root path read |
| `--files ../../etc/passwd` | scored "is new" (resolved against root, not cwd) — inconsistent with the absolute form | PROBE: outside-root inconsistency |
| `--files does/not/exist.py`, `--files index` | scope 0 / behaviour 0, "is new", no traceback | ok (Review focus 3) |
| `--declare colour=2:x`, `domain=9:x` | refused with the axis list, exit 1 | ok |
| `--declare scope=0:none` on a measured scope 2 | measured 2 kept | ok |
| non-UTF-8 file outside root | no traceback; basename `bin` "referenced from 98 files" | PROBE: common-word bound did not trip (share < 25%) |
| sensor `lint` red | pylint warnings only in sensors.py:408, update.py:264, build-template-history.py:39 — untouched by this task | pre-existing, out of scope |
| sensor `duplicates` red | template ↔ its own history blob (content-addressed copy by design) | sensor false positive |
