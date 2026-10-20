# Review ledger — T-2026-10-20-002

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| tests on 6e0c00b37: verify_command exit 0 in 334s, run 1, log .ai/reports/T-2026-10-20-002/tests-suite-1.log | sensors.py tests | CONFIRMED | sensor |
| diff on 6e0c00b37: 2 files / 69 lines (T4 task budget 30 / 800) | sensors.py diff | CONFIRMED | sensor |
| rescore on 6e0c00b37: T4 — scopes: docs, source, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 6e0c00b37: steps with no test named: 1 | sensors.py traceability | DEFECT, open | sensor |
| duplicates on 6e0c00b37: 0 blocks >= 8 lines repeat | sensors.py duplicates | CONFIRMED | sensor |
| traceability red is the quick record: step 1 names tests/test-ai-path-guard.sh as a file, not as a test; the 31 new deny cases failed at HEAD (295 passed, 31 failed) and pass after (326 passed, 0 failed) | manager, bash tests/test-ai-path-guard.sh before/after | CONFIRMED (bite shown by hand) | manager probe |
| IFS split /bin/sh-c-rm of the state file on U+1680, U+2000, U+2006, U+2008, U+200A, U+2028, U+2029, U+205F, U+3000: deny under LC_ALL=C, LC_ALL=POSIX and exported LC_ALL=en_US.UTF-8; HEAD allows all 27 | manager, scratchpad probe2.sh, new vs HEAD guard | CONFIRMED | manager probe |
| bash/zsh with multibyte blanks between options (`bash<U+3000>-c<U+3000>'rm state'`, `zsh<U+2003>-e<U+2003>-c<U+2003>'rm state'`): deny (HEAD allow) | manager, probe2.sh | CONFIRMED | manager probe |
| no over-deny on ordinary multibyte text: `git push<U+3000>-c<U+3000>x; rm -f a.txt`, Japanese text with U+3000 plus `sh -c 'rm -f a.txt'`, `sh -c 'rm -f ./データ/x.txt'` all allow (as HEAD) | manager, probe2.sh | CONFIRMED | manager probe |
| characterization golden (1221 guard runs) byte-identical; padded timed cases 0.25 s / 0.33 s | tests/test-guard-characterization.sh, tests/test-ai-path-guard.sh | CONFIRMED | manager probe |
| slow residual, one run each, `; rm -f a.txt`: 200 KB allow 1.8→1.4 s; 400 KB deny 6.6 s→allow 4.4 s; 800 KB deny 8.1→8.7 s; eval 800 KB deny 8.8→8.9 s | manager, scratchpad measure.sh | CONFIRMED (800 KB unchanged within noise; still open in known-risks) | manager probe |
| sh_string keeps HEAD's order: emptiness checked before quote stripping, so `sh -c ''` adds the same lines as before | manager, code reading | INFERENCE, not probed | manager probe |
