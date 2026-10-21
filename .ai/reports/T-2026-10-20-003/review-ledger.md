# Review ledger — T-2026-10-20-003

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on 6f2811827: verify_command exit 0 in 343s, run 1, log .ai/reports/T-2026-10-20-003/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on 6f2811827: 2 files / 27 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 6f2811827: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 6f2811827: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 6f2811827: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| no deny→allow regression on 57 probe commands, HEAD 21faea3 (git archive) vs this tree: redirections to the state file before/after/around -c, `\bash`, `"/bin/bash"`, `env`/`timeout`/`nice`/`sudo`/`find -exec` wrappers, `-cx`/`-xc`, zsh/dash/ksh, `git -c`, `ssh -c`, `grep -c sh`, `echo sh -c ok` | manager probe (scratchpad probe.sh, fixture project) | CONFIRMED | manager |
| SH_OPT works "before or after the -c cluster" (code comment `hooks/ai-path-guard.sh:405`, known-risks Status) | manager probe: `bash -c -o posix '…'`, `bash -c +o posix`, `bash -c -O extglob`, `bash -c -eo pipefail`, `bash -c --rcfile /dev/null`, `bash -c -e -o posix`, `bash -c 2>/dev/null -o posix`, each with `'rm -f .ai/state/current.json'`, are **allowed**; real bash runs the string in all (`bash -c -O extglob 'echo RAN1'` prints RAN1). Cause, LC_ALL=C `[[ =~ ]]`: after -c nothing anchors the option group, glibc takes `-o` as the short-cluster alternative `[-+][A-Za-z]*` and `posix '…'` becomes the string; `sh_string` strips no quote and the inner segment's verb is `posix`. Before -c it works because `-c` must follow. | DEFECT, open | manager |
| a redirection target with a backslash-escaped blank (`sh -c 2>/tmp/x\ y '…'`) | manager probe: allowed — `SH_WORD` has no `\` escape | DEFECT, open (low) | manager |
| `bash --rcfile <state file> -c …`, `sh -o <state file> -c …`, `sh -c '…' _ <state file>` | manager probe: allowed on HEAD and on this tree alike — unchanged, out of this task | CONFIRMED (unchanged) | manager |
| tests on 6716dc12a: verify_command exit 0 in 345s, run 2, log .ai/reports/T-2026-10-20-003/tests-suite-2.log | sensors.py tests | CONFIRMED | sensor |
| diff on 6716dc12a: 2 files / 82 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 6716dc12a: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 6716dc12a: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 6716dc12a: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| R1 on 6716dc12a: no deny→allow vs HEAD 21faea3 on 184 probe commands (manager cases + every reviewer case file r, r2, f, g, s, t); all of review BLOCKER 1 deny again; HIGH cases (`bash -c -o posix`, `+O extglob`, `-eo pipefail`, `-e -o pipefail`, `2>/dev/null -o posix`, `-O extglob -O nullglob`) deny | manager probe, `$J/all.txt` → `all-head.out` / `all-fix3.out` | CONFIRMED | manager R1 |
| R1 regex alone, 200 KB, every review padding + ` sh -c`, ` sh 'x'`, ` sh -o sh`, ` \x`: 6–28 ms | `rv/time.sh rv/re-fix.sh` | CONFIRMED | manager R1 |
| R1 whole hook, padded, HEAD → this tree: ` sh 2>`×33333 deny 0.76→0.72 s; ` 2>/sh` 0.74→0.72; ` sh -c`×33333 allow 1.2 → deny 1.2 (8-per-segment cap); ×66666 allow 3.7 → deny 3.8; ` sh -c 'x'`×20000 allow 0.77 → deny 0.84; `sh -c x; `×6000 deny 0.28→0.39; `sh -c '<400 KB>'` allow 4.2→4.2 | manager probe, one run each | CONFIRMED | manager R1 |
| R1 suite exit 0 (run 2, 345 s), e2e exit 0, characterization golden byte-identical (1221 runs); `tests/test-ai-path-guard.sh` 368 passed | test-run | CONFIRMED | manager R1 |
| `sh -c 'echo; bash -c "rm -f <state>"'` HEAD decision | not measured (the probe one-liner was refused by the live guard) | UNKNOWN | manager R1 |
| traceability red: the inline `quick` step names no test | plan metadata, not the diff | DEFECT, open (process) | manager R1 |
| tests on 1dfee67a0: verify_command exit 0 in 385s, run 3, log .ai/reports/T-2026-10-20-003/tests-suite-3.log | sensors.py tests | CONFIRMED | sensor |
| diff on 1dfee67a0: 2 files / 106 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 1dfee67a0: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 1dfee67a0: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 1dfee67a0: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| R3 (human, `SH_NB`/`SH_WORD` `hooks/ai-path-guard.sh:427-428`: a quoted piece holds no blank, no multibyte blank): BLOCKER 5 shape is ` sh 2>\''` — `\'` is escaped from outside, closes from inside '…', is literal inside "…", the next `'` re-opens, so every start's word stays quoted to the end of the line | manager probe, scratchpad `probe.sh` (SH_* lines only, LC_ALL=C) | CONFIRMED | manager R3 |
| R3 regex alone, 198 KB ` sh 2>\''`: R2 11441 ms → R3 11 ms; 286 KB U+3000 variant: 17942 → 14 ms; 36–52 KB ` sh 2>\""`, ` sh -o \''`, ` sh 2>\'"'\""`: R2 384–579 ms → R3 7–12 ms | manager probe, one run each | CONFIRMED | manager R3 |
| R3 whole hook, 198 KB, cwd = this repo: ` sh 2>\''` + rm of the state file R2 deny 10.3 s → R3 deny 0.75 s; + rm -f a.txt R2 deny 9.9 s (time cap) → R3 allow 0.77 s; U+3000 variant 14.4 / 13.9 s → 1.37 / 1.43 s, same decisions | manager probe, scratchpad `h/{r2,r3}` copies + defaults link | CONFIRMED | manager R3 |
| R3 deny→allow vs R2 (not vs HEAD): a redirection target or -o name with a blank inside quotes — `bash 2>'/tmp/a b' -c`, `bash 2>"/tmp/a b" -c`, `bash -c 2>'/tmp/a b'`, `bash -o 'pos ix' -c`, each + `'rm -f <state>'` — HEAD allow, R2 deny, R3 allow; comment `:413` ("quoted … pieces") and known-risks Status still claim them, Status line refs now off by one (SH_WORD `:428`) | manager probe, scratchpad `cmp.sh` | DEFECT, open | manager R3 |
| a word glued to a quote, `sh -c rm' -f <state>'` (also `rm" …"`, after `find -name 'sh' -exec`, after `sudo -u 'sh' -c x`, as a second sh -c in a segment) | manager probe: allow on HEAD, R2 and R3 alike — unchanged, out of this task | CONFIRMED (unchanged) | manager R3 |
| R3 suite exit 0 (run 4, 392 s), e2e exit 0 (run 4); `tests/test-ai-path-guard.sh` 379 passed; no test added for BLOCKER 5 | test-run | CONFIRMED | manager R3 |
| tests on 38b26a535: verify_command exit 0 in 392s, run 4, log .ai/reports/T-2026-10-20-003/tests-suite-4.log | sensors.py tests | CONFIRMED | sensor |
| diff on 38b26a535: 2 files / 107 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 38b26a535: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 38b26a535: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 38b26a535: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| BLOCKER 5 closes on R3: ` sh 2>\''` 9 ms at 200 KB, 20 ms at 900 KB; multibyte variants 9–24 ms up to 1.1 MB, each matching only at the tail | reviewer pass 4, `probe.sh` + `where.sh` | CONFIRMED | 4 |
| no other super-linear padding on R3: structured fuzzer (finds R2 at 59–82 ms at 20 KB) found nothing ≥ 25 ms in 1800 units | reviewer pass 4, `fuzz2.sh` | CONFIRMED | 4 |
| whole hook on R3 at ~200 KB: 0.68–1.6 s over 11 shapes; 257 KB U+3000 case 3.7 s, HEAD 3.5 s | reviewer pass 4, `hookt.sh` | CONFIRMED | 4 |
| no deny→allow HEAD→R3 over 768 quoted-blank commands (122 aaa / 630 ada / 16 ddd) | reviewer pass 4, `cmp.sh` corpus `diff.log` | CONFIRMED | 4 |
| the R3 follow-on cut is no longer the first shell word (`rm" -f S"` → `rm`); decisions unchanged on 12 follow-on cases | reviewer pass 4, direct `^$SH_WORD` + `cmp.sh` | DEFECT (record and comment), open | 4 |
| BLOCKER 5 has no test; repeats pass-1 LOW | reviewer pass 4, `tests/test-ai-path-guard.sh:358-376` | DEFECT, open | 4 |
| known-risks line refs off by one (`:427`–`:432`, `:460`) | reviewer pass 4, grep | DEFECT, open | 4 |
| R4 (agent, Q1=B: tests and text only, regexes byte-identical to R3): `tests/test-ai-path-guard.sh` 384 passed; new timed cases ` sh 2>\''` ×22000 + state file deny 729 ms, U+3000 ×11000 + a.txt allow 562 ms (R2 copy: 10.3 s and 3.6 s, so both bite); suite exit 0 (run 5, 360 s), e2e exit 0 (run 5) | test-run + manager probe | CONFIRMED | manager R4 |
