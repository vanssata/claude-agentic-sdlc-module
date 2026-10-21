# Review report — T-2026-10-20-003 (T4, ai-reviewer on STRONG, pass 1, tree 6f2811827)

Verdict: **blockers_open**. Scope: the three approved files, nothing else touched.
Probe files: `$CLAUDE_JOB_DIR/tmp/rv/` (cases-r, cases-r2, cases-f, cases-g, cases-s, cases-t, pad1-3, time.sh, mk.py).

## BLOCKER 1 — deny→allow regression against HEAD 21faea3 (`hooks/ai-path-guard.sh:414-415`)
KNOWN FACT (probe, both trees). The quoted command word `(['"]|\\)?…sh['"]?` and the redirection SH_OPT let an
earlier argument start the leftmost match; `-exec`/`-execdir` satisfy the `-c` cluster; the string group becomes
`sh -c '…' \;`, unquoted, which `sh_string` does not strip and `segments_of` reads only one layer of.
HEAD deny → new allow, each with `'rm -f .ai/state/current.json'`:
`find . -name 'sh' -exec sh -c`, `find . -name "bash" -exec bash -c … {} \;`, `find . -type d -name "sh" -exec bash -c`,
`find . -iname 'sh' -execdir sh -c`, `find . -path '*/sh' -exec sh -c`, `find "sh" -execdir bash -c`,
`find . -name 'sh' -o -exec sh -c`, `find . -name sh 2>/dev/null -exec sh -c`, `find bin/sh 2>/dev/null -exec sh -c`,
`sudo -u 'sh' -c x bash -c`. Real `find -exec sh -c` runs the string. The unquoted `find . -name sh -exec sh -c` is
allowed on HEAD too (older gap, widened here).

## BLOCKER 2 — super-linear `[[ =~ ]]`, padded line past the 10 s hook timeout (`:414-415`, called from `sh_string:425`)
KNOWN FACT (measured). Any argument-taking SH_OPT whose argument is the next `sh` word makes every `sh` a match start
that scans to the end of the line. Regex alone at 100 KB, line ending ` X sh -c 'rm y'`: ` sh >` 4.0 s (HEAD 4 ms),
` sh <` 4.3 s, ` >/sh` 3.9 s, ` sh -O` 3.6 s, ` sh &>` 3.4 s, ` sh -o` 3.3 s, ` bash 2>` 2.5 s, ` sh --rcfile` 1.6 s;
200 KB ` sh 2>` 13.0 s (quadratic). Whole hook, `echo` + ` sh 2>`×33333 + ` X sh -c x; rm -f <state>`: new 14.4 s,
HEAD 0.73 s. The 6 s clock in `segments_of` cannot interrupt one regex call. The Status line's "linear" holds only
for the shapes it measured.

## HIGH — options that take an argument after `-c` are allowed; record and comment say they are handled (`:405`, known-risks `:138`)
KNOWN FACT (probe; manager's ledger row). `bash -c -o posix`, `-c +o posix`, `-c -O extglob`, `-c +O extglob`,
`-c -eo pipefail`, `-c -e -o pipefail`, `-c 2>/dev/null -o posix`, `-c --rcfile /dev/null`, each with the state-file
`rm`, are allowed; real bash runs the string. Not a regression (HEAD allowed them) but inside the stated goal, and
the record marks the class fixed. Cause: glibc reports `-o` as the short-cluster alternative and `posix '…'` as the string.

## MEDIUM — the Status line claims redirection spellings the hook does not deny (known-risks `:138`; `shell_segments:376-377`)
`sh -c >|/dev/null '…'` allowed: `shell_segments` splits at the `|` before `sh_string` sees it.
`sh -c 2>"$HOME"/x '…'`, `sh -c 2>/tmp/"x" '…'` allowed (mixed-quote target; SH_WORD is one quoted or one bare run);
same class as the manager's LOW `sh -c 2>/tmp/x\ y '…'`.

## LOW — new allow→deny on prose quoting the newly read spellings
`grep -n "bash -o posix -c 'rm -f <state>'" docs/x.md`, `echo "use 'bash' -c 'rm -f <state>' never"`,
`echo sh -c -- 'rm -f <state>'`. Extends the accepted deny-side class in known-risks. 22 ordinary commands
(`grep 'bash' -c`, `git log --grep 'bash' -c`, `docker run … 'sh' -c 'make test'`, `ps -C 'bash' -c`, …) allow on both trees.

## LOW — tests pin neither BLOCKER nor the after-`-c` placement (`tests/test-ai-path-guard.sh:330-344`)
The 18 deny cases fail on HEAD and pass here; no case for `find … 'sh' … -exec sh -c`, a padded ` sh 2>` line, or `bash -c -o posix`.

## Examined and clean
Characterization golden byte-identical (1221 runs). No regression on `-ec`, `-lc`, `$'…'`, `/usr/bin/env bash -c`,
`docker exec … sh -c`, `ssh -o 'x' host sh -c`, trailing redirections, `-c` inside the string. Candidate
`grep -aE` stays 4–8 ms at 200 KB; all super-linear cost is in bash's `[[ =~ ]]`.

# Pass 2 — scoped re-review of R1 (ai-reviewer on STRONG, tree 6716dc12a)

Verdict: **blockers_open**. Probe files: `$CLAUDE_JOB_DIR/tmp/rv3/`.
Pass-1 findings: BLOCKER 1 closed; BLOCKER 2 closed for every shape pass 1 named, open as a class (below);
HIGH closed for the named shapes; MEDIUM closed; both LOWs closed (prose accepted, tests pin the named cases).

## BLOCKER 3 — deny→allow vs HEAD: 9 or more short options before `-c` (`hooks/ai-path-guard.sh:424`, `{0,8}`)
KNOWN FACT (probe, both trees, rv3/c1.txt, c3.txt): `bash -e ×9 -c '…'`, `bash -e -u -x -v -e -u -x -v -e -c '…'`,
`sh -a -b -e -f -h -m -u -v -x -c '…'`, 20 × `-e`, each with the state-file `rm`: HEAD deny, R1 allow. HEAD's
`($SH_BLANK+-[A-Za-z]+)*` was unbounded; the bound makes the regex (and the candidate grep) fail. Real bash runs it.

## BLOCKER 4 — quadratic `[[ =~ ]]` on a multibyte-blank padding (`:420` SH_WORD with `:402` SH_BLANK)
KNOWN FACT (measured). Unit `U+3000 sh U+3000 -o U+3000 x`: 1.4 s at 98 KB, 2.8 s at 140 KB, 11.5 s at 280 KB
(HEAD 9 ms), 46 s at 560 KB; `U+3000 sh U+3000 2>x` 9.0 s at 220 KB. Whole hook, ×20000 + `X sh -c x; rm -f <state>`:
16.7 s deny (WHY_WORK_CAP), HEAD 1.2 s; with `rm -f a.txt` 13.4 s, HEAD 1.4 s. Cause: in C locale the bare piece
`[^[:space:]'"\\]` takes the bytes of U+3000 and the other multibyte SH_BLANKs, so a word runs across them to the end
of the line from every `sh` start; the bounds count words, not bytes.

## LOW — 10 or more `sh -c`/`bash -c` in one segment deny (`:469-471`), with WHY_WORK_CAP's wording
`find . -name '*.tmp' -exec sh -c 'rm -f "$1"' _ {} \; …` with 10 `-exec sh -c`; `docker run --rm img bash -c '…'`
holding 10 shell words: HEAD allow → R1 deny in 0.11 s. Nine allow on both.

## LOW — Status line claims
(a) "no deny → allow" holds for the 184 cases only (BLOCKER 3); (b) "6–28 ms on every padding" true as worded, not for
multibyte padding; (c) a further bare string is cut to its first word with its quotes and backslashes kept, so
`-exec sh -c rm\ -f\ <S>`, `rm" -f <S>"`, `"rm -f "<S>` stay allowed, as on HEAD — "as bash runs it" overstates;
(d) `sh -c 'echo; bash -c "rm -f <S>"'`: HEAD allow, R1 deny (settled).

## INFO — open on both trees
5+ words after `-c` (`bash -c -e -u -x -v -o pipefail '…'`), `bash -co pipefail '…'`, three nested layers.

# Pass 3 — scoped re-review of R2 (ai-reviewer on STRONG, tree 1dfee67a0)

The full report was lost with the session; its result, as the handoff recorded it: BLOCKER 3 and BLOCKER 4 closed;
new **BLOCKER 5** — super-linear `[[ =~ $SH_RE ]]` from `SH_WORD` (introduced in R1) on a backslash+quote padding,
past the 10 s hook timeout. The manager reconstructed the shape in pass 4's ledger rows: ` sh 2>\''` repeated
(R2: 11.4 s at 198 KB regex alone, whole hook 10.3 s). R3 (human): `SH_NB` and `SH_WORD`, `hooks/ai-path-guard.sh:427-428`
— a quoted piece holds no ASCII or multibyte blank.

# Pass 4 — scoped re-review of R3 (ai-reviewer on STRONG, tree 38b26a535)

BLOCKER 5 closed. No super-linear padding found on R3; no deny→allow vs HEAD 21faea3. Verdict: **passed**.

## MEDIUM — BLOCKER 5 is pinned by no test; the same mistake as pass 1's LOW (`tests/test-ai-path-guard.sh:358-376`)
The timed cases pin ` sh 2>` and the two U+3000 paddings (BLOCKERs 2, 4), not the backslash+quote shape; R3 changed
no test. ` sh 2>\''` regex alone: R2 1846 ms at 90 KB, R3 8 ms. The next `SH_WORD` edit (blanks back inside quotes)
brings the timeout back with the suite green — BLOCKERs 2, 4 and 5 all came from this one regex. Direction: a timed
deny case (` sh 2>\''` ×~22000 + rm of the state file, under 2000 ms) and a multibyte variant. Second occurrence:
the correction belongs in the project `CLAUDE.md`.

## MEDIUM — comment and record still say a quoted piece may hold a blank; the narrowing is not recorded as open; the follow-on cut description is now false (`hooks/ai-path-guard.sh:413-414`, `:421-423`, `:440-441`; `.ai/project/known-risks.md:138`)
(a) `:413` and the Status line: "one word of bare, quoted and backslashed pieces", unbounded; R3's limit and the
BLOCKER 5 measurement are recorded nowhere (the comment does record BLOCKERs 2 and 4's timings).
(b) "Still open" does not name what R3 gave up — HEAD allow, R2 deny, R3 allow, bash runs the string:
`bash 2>'/tmp/a b' -c`, `bash -c 2>"/tmp/a b"`, `bash -o 'pos ix' -c`, each + `'rm -f <S>'`; also a quoted piece
holding a stray E1–E3 byte that is not valid UTF-8 (R2's `'[^']*'` took it; HEAD allows too).
(c) `sh_string` (`:440-441`) and the record say the string is "cut to its first word, its quotes and backslashes kept":
no longer — `rm" -f S"` R2 → `rm" -f S"`, R3 → `rm`; `a'b c'd e` R2 → `a'b c'd`, R3 → `a`. `rm" -f <S>"` stays allowed,
now because of the cut point. Decisions unchanged on 12 follow-on cases (`>S`, `"$(rm …)"`, `$(rm …)`, backticks,
`;rm`, glued `';rm …'`, after `bash 2>x -c 'echo'` and after `find … -exec`): HEAD = R2 = R3.
Direction: narrow comment and Status to "a quoted piece holds no blank", add the quoted-blank target/name to
"Still open" with BLOCKER 5 as the reason, pin `bash 2>'/tmp/a b' -c 'rm …'` as allowed (as U+2007 is).

## LOW — known-risks line refs one behind since `SH_NB` was added (`.ai/project/known-risks.md:137-138`)
`SH_WORD` `:427`→`:428`, `SH_FLAG` `:428`→`:429`, `SH_ARG` `:429`→`:430`, `SH_OPT` `:430`→`:431`, `SH_COPT` `:431`→`:432`,
`SH_RE` (Where and Status) `:432`→`:433`, `segments_of` `:460`→`:461`; name `SH_NB` `:427`. Still right: `SH_MB` `:426`, `:384-485`.

## INFO — the R2→R3 narrowing is acceptable, not a regression against production
768 generated commands (bash, sh, `'sh'`, `\sh`, `/bin/sh`, two `find -exec`, `sudo -u 'sh'` × 12 quoted-blank
target/name shapes incl. U+3000 in quotes, `-eo "pos ix"`, `--rcfile 'a b'`, before/after `-c`, 4 string forms),
whole hook HEAD/R2/R3: 122 allow/allow/allow, 630 allow/deny/allow, 16 deny/deny/deny; none deny on HEAD and allow
on R3. The plan's spellings still deny (`2>"$HOME"/x`, `2>/tmp/x\ y`). Record it as a deliberate limit (MEDIUM above).

## Examined and clean
BLOCKER 5 shapes, regex alone: ` sh 2>\''` 9 ms at 200 KB, 20 ms at 900 KB; nine other ASCII shapes 8–13 ms at
200 KB; multibyte (`\<U+3000>'`, U+2000, U+3000-separated) 9–24 ms up to 1.1 MB; linear 200→900 KB; each matches only
at its tail. Why linear: only `\\.` carries a word across a blank and needs `\` right before it, while a match start
needs a blank right after `sh['"]?` — no word runs past a start's command word. Structured fuzzer (finds R2 at
59–82 ms at 20 KB): nothing ≥ 25 ms in 1800 units on R3. Whole hook ~200 KB: 0.68–1.6 s over 11 shapes; 257 KB
U+3000 case 3.7 s vs HEAD 3.5 s (existing long-line path). `^$SH_WORD` cut anchored and linear; the candidate grep
and `[[ =~ ]]` share one regex. Probes: scratchpad `fuzz.sh`, `fuzz2.sh`, `hookt.sh`, `where.sh`, `diff.log`.
