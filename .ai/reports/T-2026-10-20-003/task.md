# T-2026-10-20-003 — release summary (T4, bugfix, solo direct mode)

path guard: segments_of reads the sh -c spellings SH_RE misses (known-risks)

## What changed
- `hooks/ai-path-guard.sh`:
  - `SH_RE` now reads what bash takes before `-c`:
    - any number of flags;
    - at most 8 options that take a word: `-o`/`-O` and a name, a redirection and its target, `--rcfile`/`--init-file` and a file, a long option.
  - After `-c` it reads at most 4 words: flags, `-o` and a name, redirections.
  - The command word may be quoted or backslashed (`'sh'`, `"bash"`, `\sh`).
  - `segments_of` reads every `sh -c` in a segment, not only the leftmost. At most 8 more per segment, under the same budget of 64 and 6 s.
  - In `SH_WORD`, only a backslashed piece of a word holds a blank, ASCII or multibyte. Every padding found so far is now linear.
- `tests/test-ai-path-guard.sh`:
  - allow → deny cases for each spelling, plus the review cases;
  - timed paddings for BLOCKERs 2, 4 and 5 (200 KB and 140 KB, 2000 ms each), each of which fails on the tree before its fix;
  - `bash 2>'/tmp/a b' -c …` pinned as allowed, as on HEAD.
- `.ai/project/known-risks.md`: the Status of "`sh -c` spellings `segments_of` does not read" now records what is fixed, what stays open, and the timings.
- `CLAUDE.md`: one correction line. A BLOCKER is closed only with a test that pins it, and a regex timing blocker only with a `timed` case.

## Deliberately preserved
- Nothing denied on HEAD 21faea3 is allowed now. This was checked by probe on 184 commands (pass 1 and 2 cases) and 768 more (quoted-blank targets and names, pass 4).
- These stay open, as on HEAD:
  - the `IFS` split;
  - a word glued to a quote (`rm' -f …'`);
  - indirection (`$x`, `"$@"`, `r\m`);
  - `>|` next to `-c`;
  - more than 8 or 4 option words.
- A quoted target or name holding a blank (`bash 2>'/tmp/a b' -c`) is not read. HEAD does not read it either. Reading it is what made BLOCKER 5's padding super-linear.

## Verification
- `bash tests/run-all.sh`: run 5, exit 0 in 360 s (`tests-suite-5.log`).
- `bash tests/test-end-to-end.sh`: run 5, exit 0 (`tests-e2e-5.log`).
- `tests/test-ai-path-guard.sh`: 384 passed, 0 failed.

## Review
- `ai-reviewer` on STRONG ran 4 passes and found 5 BLOCKERs:
  1. `find 'sh' -exec` went from deny to allow;
  2. the hook ran past its timeout on a ` sh 2>` padding;
  3. 9 or more flags before `-c` went from deny to allow;
  4. the hook ran past its timeout on a U+3000 padding;
  5. the hook ran past its timeout on a ` sh 2>\''` padding.
- All five are closed. Pass 4 verdict: **passed**.
- Pass 4's 2 MEDIUM and 1 LOW were fixed in R4 (tests and text only, no regex change). No re-review followed, because no BLOCKER was involved.
- Remediation took 4 rounds. Rounds 3 and 4 went past the policy limit of 2 and were authorised by the human with `--by`. R2 and R3 were written by the human.
- Security review: not applicable. The guard is defence-in-depth (see the file header), with no authentication, authorization or personal data involved. Its deny → allow surface was covered by the adversarial passes.
- Full report: `.ai/reports/T-2026-10-20-003/review-report.md`. Ledger: `review-ledger.md`.

## Open
- Sensors:
  - `lint`: unavailable (`pylint` is not installed, and no Python changed).
  - `traceability`: red. The inline `quick` step names no test. This is a process gap, not a gap in the diff.
- Hook line references in other known-risks entries are stale (lines moved during this task).

## Rollback
`git revert <commit>`. One commit, no migration, no state format change.
