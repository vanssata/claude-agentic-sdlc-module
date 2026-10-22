# Review ledger — T-2026-10-21-001

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| diff on 2ff557755: 2 files / 121 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 2ff557755: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| duplicates on 2ff557755: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| diff on 0bdb7a3d8: 2 files / 261 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 0bdb7a3d8: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 0bdb7a3d8: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 0bdb7a3d8: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| R1 probes (one segment over 32 KB with the state file in chunk 2; loop + symlinked dir across batches; mv wording in batch 2) | manager, Bash through the real guard | NOT RUN: the path guard refused the probe command (its text names the state file); not reworded | re-review R1 |
| tests/test-ai-path-guard.sh:309-311 still says "one realpath and one loose_hits for every candidate on the line"; R1 made it one per 32 KB batch | manager, read | INFERENCE: stale comment, LOW | re-review R1 |
| R1: no clock-free unit larger than one 32 KB chunk plus one candidate; chain ×400 + state file: HEAD 5.2 s, R1 6.3 s | reviewer, scratchpad HEAD/R1 guards, p9.sh | CONFIRMED (HIGH closed) | re-review R1 |
| R1: early deny prompt when later segments add candidates (state file + `rm x;` ×20000: 0.36 s, own reason) | test suite + p9.sh | CONFIRMED | re-review R1 |
| R1: early deny becomes `WHY_WORK_CAP` when later segments add no candidates (`rm -f;` ×150000: HEAD 1.15 s control-file reason, R1 5.0 s work cap; `rm <-f×2000> y;` ×200: 1.13 s vs 5.1 s) | reviewer, p3.sh, p10.sh | DEFECT, open (HIGH-1) | re-review R1 |
| R1: parse pass linear (`rm x;` ×2000→16000: 0.77→5.97 s) | reviewer, p7.sh | CONFIRMED (LOW closed) | re-review R1 |
| R1: E2BIG deny→allow (cwd 1524 chars, `rm` of 1500 files: HEAD deny 0.52 s work cap, R1 allow 2.2 s); known-risks:152 "not measured / unreachable" inference refuted | reviewer, p8.sh | DEFECT, open (HIGH-2, human decision Q1) | re-review R1 |
| R1: chunk-spanning `hits` index, later-chunk fallback, `per_seg`/`seg_first` across batches, `mv` wording in batch ≥2, pending glob order, classify 64 cap across batches all match HEAD | reviewer, p4.sh, p5.sh | CONFIRMED | re-review R1 |
| R1: shared globals between `mover_check`/`mover_resolve` and the parse loop | reviewer, read | CONFIRMED clean | re-review R1 |
| tests/test-ai-path-guard.sh:309-311 comment stale | reviewer, read | CONFIRMED, LOW | re-review R1 |
| Amplifying symlink: one 400-byte candidate makes `realpath -m` run 13 s; guard 13.4 s on HEAD and R1 (past the 10 s timeout) | reviewer, p6.sh | CONFIRMED, outside task, known-risks | re-review R1 |
| tests on 18957fcc7: verify_command exit 0 in 375s, run 3, log .ai/reports/T-2026-10-21-001/tests-suite-3.log | sensors.py tests | CONFIRMED | sensor |
| diff on 18957fcc7: 2 files / 286 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 18957fcc7: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 18957fcc7: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 18957fcc7: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| R2: the three pass-2 HIGH-1 inputs (`rm -f;` ×150000, `mv a;` ×150000, `rm <-f×2000> y;` ×200) deny with the control-file reason, R2 1.18–1.32 s against HEAD 0.93–1.14 s | reviewer, q1.sh | CONFIRMED | re-review R2 |
| R2: one later segment of 30 quote-heavy 4 KB operands (123 KB): HEAD ctl 0.29 s; R1 and R2 `WHY_WORK_CAP` 5.2–6.0 s; batch-aligned variant HEAD ctl 4.46 s, R2 work cap 5.23 s | reviewer, q2.sh, q3.sh | DEFECT, open (HIGH-1 residual, human decision Q2) | re-review R2 |
| R2: deny order and reason across a batch edge (control file, vendor, pending glob, symlink loop, `mv` wording; segments 276–280) match HEAD | reviewer, q5.sh | CONFIRMED | re-review R2 |
| R2: text-only batch edges keep the classify 64 cap, the glob order and the loop fallback as on HEAD | reviewer, q6.sh, q7.sh, r2dbg | CONFIRMED | re-review R2 |
| R2: `mover_check` at the top of the loop sees no half-built batch, clobbers nothing the iteration still uses, and leaves the here-string stdin intact | reviewer, read + q7.sh probe | CONFIRMED | re-review R2 |
| HIGH-2 test input crosses ARG_MAX on HEAD (2,434,893 bytes or more against 2,097,152; HEAD deny with work cap, R2 allow) | reviewer, arithmetic + q8.sh | CONFIRMED | re-review R2 |
| New test 2's reason check is not a reliable pin on R1 (R1 ctl 5.28 s this run); the timed 3000 ms case is | reviewer, q1.sh | CONFIRMED, LOW | re-review R2 |
| The new 3000 ms budgets have about 2.3× margin over R2's 1.2–1.3 s | reviewer, q1.sh | CONFIRMED | re-review R2 |
| R3: pass-3 HIGH-1 inputs (123 KB quote segment; 16+ctl+8 quote segments) deny with the control-file reason, R3 0.20–0.30 s | reviewer, q2.sh, q3.sh on r3/ | CONFIRMED | re-review R3 |
| R3: control file, then one segment of 5000–5300 short operands under a 1.5–3.3K cwd: HEAD 0.11 s control-file reason; R2/R3 5.4–6.0 s `WHY_WORK_CAP` (flush bounds text, not candidate absolute-path bytes; `mover_check` resolves the whole batch first) | reviewer, u1.sh–u3.sh | DEFECT, open (HIGH-1 residual, human decision Q3) | re-review R3 |
| Building the absolute paths of 16000 operands under a 4 KB cwd alone takes 5.5 s (bg_BG.UTF-8) / 1.9 s (C); with `${AI_CWD%/}` computed once, 1.2 s / 0.47 s | manager, bash micro-benchmark | CONFIRMED, same class as HIGH-1 | re-review R3 |
| R3: new strip equals the old loops in C, POSIX and 6 UTF-8 setups on 30,000 words each, with backslash and brackets in the alphabet | reviewer, s3.sh | CONFIRMED | re-review R3 |
| Old loop returns garbage on words starting with `\303\\` (bash 5.3.9 `${w%?}`); R3 is correct; unreachable through jq | reviewer, s4.sh plus jq check | CONFIRMED, INFO | re-review R3 |
| `quote_tail`'s `local LC_ALL=C` restores the locale, export state and matching behaviour; no `qrun`/`quoted` leak or collision | reviewer, s1.sh, s2.sh, grep | CONFIRMED | re-review R3 |
| Deny order/reason, pending glob, loop fallback, `mv` wording and classify cap 64 across the pre-parse flush match HEAD (221 cases) | reviewer, v5.sh–v9.sh | CONFIRMED | re-review R3 |
| `quote_tail` costs about 20 µs per call; no new parse step costs more than linear time | reviewer, u4.sh | CONFIRMED | re-review R3 |
| R4: pass-4 inputs (state file + `rm` ×2000–6000 under a 1.5/3.3 KB cwd; `mv` ×5300) deny with the control-file reason in 118–208 ms (HEAD 87–118 ms) | reviewer, u1-r4.sh–u3-r4.sh | CONFIRMED (pass-4 HIGH closed) | re-review R4 |
| R4: the pre-build estimate bounds the real batch increment at `:941` (proof plus 1814 fuzzed segments over locales, cwd and HOME; 0 violations, max ratio 0.991) | reviewer, r4i/ + w1.sh | CONFIRMED | re-review R4 |
| R4: deny order and reason, pending glob, loop fallback, `mv` wording and classify cap 64 across the pre-build flush match HEAD (260 cases, 243 flushes fired) | reviewer, x1.sh, x1d.sh, x2.sh | CONFIRMED | re-review R4 |
| R4: a pre-build flush clobbers none of the current segment's state (`verb` local; no other shared name written) | reviewer, read + grep | CONFIRMED | re-review R4 |
| R4: about 3.8 µs more per mover segment with no candidates; `rm -f;` ×90000 HEAD 6/6 allow (mean 4.65 s), R4 1/6 work-cap deny; ×95000 R4 2/3 deny, R3 1/3 | reviewer, x7.sh, x8.sh | DEFECT, open (HIGH by brief rule; fail-closed clock margin; human decision Q4) | re-review R4 |
| R4: shapes that flush before every segment cost the same as HEAD (`cp a <4K dest>;` ×200: 3603 against 3611 ms), above R3 (2798 ms) | reviewer, x5.sh | CONFIRMED, INFO | re-review R4 |
| R4: no further shape outside the stated residual in about 10 minutes | reviewer, x6.sh | CONFIRMED (none found) | re-review R4 |
| lint on 0908c6974: pylint $(git ls-files '*.py') exited 12, log .ai/reports/T-2026-10-21-001/lint.log | sensors.py lint | DEFECT, open | sensor |
| diff on 0908c6974: 2 files / 371 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 0908c6974: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 0908c6974: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 0908c6974: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
