# T-2026-10-20-002 — path guard: one locale for the `sh -c` candidate filter and its regex

Tier T4 (bugfix; `hooks/ai-path-guard.sh` is the guard every Bash call runs through). Plan approved in plan mode.

## What changed

- `hooks/ai-path-guard.sh` — `segments_of`'s regex match and quote stripping moved into `sh_string`, which runs under `local LC_ALL=C` and starts no process; the candidate grep keeps `LC_ALL=C`. `SH_BLANK` names the UTF-8 bytes of the 15 multibyte characters glibc's UTF-8 `[[:space:]]` matches (U+1680, U+2000–2006, U+2008–200A, U+2028, U+2029, U+205F, U+3000) beside ASCII `[[:space:]]`; `SH_RE`/`EVAL_RE` became globals using it; the string is `${BASH_REMATCH[-1]}`.
- `tests/test-ai-path-guard.sh` — 47 cases: for each of the 15 blanks, the `IFS` line removing the state file and the `echo` form are denied, the `rm -f a.txt` form is allowed; U+3000 under `LC_ALL=C` is denied; U+2007 stays allowed. The 31 deny cases failed before the fix (295 passed, 31 failed).
- `.ai/project/known-risks.md` — the "Allow side, one crafted shape" residual marked fixed with before/after measurements; slow-residual re-measurement; the indirection class and the invalid-`LC_ALL` stderr warning recorded; stale line references updated.

## Deliberately preserved

- Emptiness is checked before quote stripping, as before. `tests/test-guard-characterization.sh` (1221 guard runs) byte-identical.
- Non-blank `IFS` separators (`,`, U+2007, U+00A0) and indirection (`$x`, `"$@"`, `r\m`) stay allowed — open in known-risks.

## Verification

- `bash tests/run-all.sh` — run 1 exit 0 (334 s); after the review remediation run 2 exit 0 (429 s), "all suites passed".
- `bash tests/test-end-to-end.sh` — 41 passed, 0 failed (both runs).
- Padded cases: `sh -c x; ` ×6000 0.25 s, `x;` ×100000 0.33 s. Slow residual `sh -c '<400 KB>'; rm -f a.txt`: deny 6.6 s → allow 4.4 s.

## Review

STRONG `ai-reviewer` over `git diff`: pass, no BLOCKER/HIGH. Differential test of 305 commands in 5 locales found no deny→allow change. LOWs fixed in R1 (known-risks line refs, the indirection note, a comment that `SH_RE`/`EVAL_RE` are valid only under `LC_ALL=C`); the invalid-`LC_ALL` stderr warning accepted and recorded as a RISK. No `ai-security`: no auth or personal data touched.

## Rollback

`git revert <commit>`.
