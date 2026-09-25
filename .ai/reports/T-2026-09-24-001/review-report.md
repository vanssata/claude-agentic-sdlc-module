# Review — T-2026-09-24-001 (usage-report incremental parse cache)

Two adversarial reviews on the STRONG tier, both verified by execution.

## Round 1 — verdict blockers_open

- BLOCKER  a cache entry written by one runtime's fold was handed to the other
           runtime's parser (`--root` with an explicit `--provider`, or a sniff
           that changes its answer): `KeyError: 'recs'`, and every later run on
           that directory crashed until the user deleted an undocumented file
           under `~/.cache`.  — FIXED (entries carry `kind`; CACHE_VERSION 2)
- HIGH     the head guard and the per-day slots both survived mutation with a
           green suite; the "rewritten" fixture shrank the file, so it only
           re-tested the shrink guard.  — head guard FIXED, per-day slots still
           open (see round 2)
- MEDIUM   both suites disabled the cache for the whole pre-existing corpus
           — FIXED (the corpus runs cached; the comparators opt out)
- MEDIUM   a last line with no trailing newline was dropped, with and without
           `--no-cache`  — FIXED (the tail is folded into a copy for the report
           and deliberately not into the stored state)
- MEDIUM   the cache file inherited the umask although it is derived from 0600
           transcripts  — FIXED (0600 file, 0700 directory on creation)
- LOW      type-confused cache aborted the report; leftover `.tmp`; SKILL.md
           overclaimed  — partly fixed, see round 2

## Round 2 (scoped re-review of the remediation) — verdict blockers_open

Open, in the order a fix should take them:

1. HIGH    `skills/usage-report/usage-report.py:230` — the resumed state is only
           validated while folding into it, and that fold is inside
           `if start < st.st_size`. An unchanged file (offset == size) hands a
           same-shape-wrong-contents state straight to `parse_claude`:
           `AttributeError: 'str' object has no attribute 'items'`. This is the
           original blocker's failure mode without the cross-runtime trigger.
2. HIGH    `tests/test-usage-report.sh:128` — the `--today` fixture makes today's
           line the larger one, so the per-day slot and the overall `"*"` winner
           are the same row. A faithful pre-fix mutant (filter-then-max) passes
           the suite. Reversing the fixture separates them.
3. HIGH    `tests/test-usage-report.sh:147` — removing the `copy.deepcopy` on the
           tail path leaves the suite green: the claude fold is idempotent per
           message id. On a Codex rollout whose last record has no `response_id`
           the total grows on every rescan ($2 → $4 → $6).
4. MEDIUM  `skills/usage-report/usage-report.py:230-237` — the broad `except` has
           no coverage: the test that names it is rejected by the mtime/size
           guard before any fold runs.
5. LOW     `os.makedirs(mode=0o700)` only applies to a directory it creates;
           SKILL.md states it unconditionally.
6. LOW     `README.md:663` "the file is not read at all" is false for a file
           whose last line is unterminated (offset < size with matching mtime).
7. LOW     a relative `USAGE_REPORT_CACHE` is read inside the project and written
           against the original cwd under `--task` (`os.chdir` in `task_report`).
8. LOW     the tmp file is `O_CREAT` without `O_EXCL`/`O_NOFOLLOW` and its name is
           predictable.

Confirmed closed in round 2, with mutants run against a copy of the tree: the
`kind` check (mutation fails the suite), the head signature (mutation fails the
suite), the cached corpus, the tail fix on the code side, the file mode, and the
read-only-directory path. Measured on the reviewer's own 966-transcript corpus:
cold 2.09 s, warm 0.26 s, uncached 1.93 s, 6.3 MB cache at mode 600, `--all` and
`--all --today` byte-identical cached versus uncached.

## The invariant behind the repeated failure

A cached state is trusted before it is proven foldable, and the cache tests
assert that a cached run agrees with an uncached run rather than asserting an
absolute expected value. A defect that degrades both runs identically is
therefore invisible to the suite — which is how the same class of finding
survived into the fix for it.

## Sensors

`sensors.json` and the ledger were measured on tree 70abb89b8 (4 files / 421
lines). The tree under review is 6 files / 472 lines, so every sensor row —
including the open traceability DEFECT, steps 1 and 1.3 naming no tests of their
own — predates the remediation and none was re-measured on it.

## Round 3 (final, authorised by the human) — verdict blockers_open

Seven of the eight round-2 findings closed with executable evidence. What the
round found, and what was then done inside the same step:

- **Finding 7 did not close.** `os.path.abspath` resolves against the current
  directory *at call time*, and `task_report` chdirs into the project for the
  parsers and back before the flush — so a relative `USAGE_REPORT_CACHE` was
  still read in one directory and written in another. The manager had recorded
  it as fixed; it was not. Now resolved once, at first use, from the directory
  the command was run in (`cache_path()`), with a `--task` case that makes the
  transcript unreadable on the second run so a cache that did not warm fails.
- **Two assertions could not detect their own mutation.** The version fixture
  was keyed on a path no run consults — and, worse, called a `poison()` helper
  defined *later* in the file, so it was passing on `command not found`. Both
  fixed; dropping the version check now fails the suite. The `kind` tag stays
  unpinned by design and the record says so: the two folds' key sets are
  disjoint, so the shape check rejects a cross-fold state first, and `kind` is
  the cheap first cut in front of it. The docstring was corrected to credit the
  shape check rather than `kind`.
- **Finding 4's justification was wrong.** The deleted `except` was unreachable
  for a bad *state*, but it also covered malformed *transcript lines*, which no
  validator touches. It is removed as out-of-scope hardening rather than as dead
  code: `git show HEAD:` crashes identically on those lines, so this is not a
  regression against main. See "Known risk carried out of this task" below.
- **LOW, fixed:** `mkstemp` gave every interrupted flush its own leftover copy
  of the cache — the cleanup now runs in a `finally`, not only on `OSError`.
- **LOW, fixed:** both folds normalise what they store (`_num`, `str(...)`), so
  a transcript with a numeric `response_id` or a float token count can no longer
  produce a state its own validator rejects — a permanent silent cache miss.
- **LOW, fixed:** SKILL.md's size estimate was optimistic (~180 bytes per
  response), and the warm run pays for the whole cache however little changed.

### Known risk carried out of this task

A malformed transcript line — a bare JSON array, a string, a numeric timestamp —
crashes the whole report. This is `main`'s behaviour too, not something this
change introduced, so it is written down here rather than fixed inside a task
about the cache.

## Round 4 (close-out) — what it found after the round-3 fixes

Six of the seven round-3 items closed with executed evidence, including the
memoised cache path (three mutants, each caught by the new `--task` case) and
the proof that the fold normalisation changes no reported number: md5-identical
output against `git show HEAD:` on a 1,100-file corpus, for `--all`, `--provider
codex --all`, `--session` and `--today`.

Two things it found that the remediation itself had introduced or missed, both
fixed afterwards in the same step:

- **BLOCKER, the repository's own Pylint job.** `global _CACHE_PATH` and
  `global _CACHE` (W0603) and the `lambda` closing over `default_thread`
  (W0640) made `pylint $(git ls-files '*.py')` exit 4, where HEAD scores
  10.00/10 — `.github/workflows/pylint.yml` runs it with no `--exit-zero`, so
  the push would have gone red. Fixed the way the rest of the repository does
  it: an inline `# pylint: disable=global-statement` on each global, and the
  loop variable bound as a lambda default. `pylint` now exits 0 at 10.00/10.
  Worth recording why it was missed: the lint sensor is UNAVAILABLE in this
  project (no `.ai/policies/testing.md`), so nothing in the pipeline ran it.
- **MEDIUM, a crash regression against main.** The normalisation round
  stringified every identifier except the claude record key, so a transcript
  with a numeric `message.id` or `requestId` died on `key.startswith("#")` —
  where `main` reports the file. Fixed at the point the key is chosen, pinned by
  a case asserting both the cold report and that the entry it writes is served
  back warm rather than rejected on every run. `_num` also now catches
  `OverflowError`, and the codex fold normalises `thread` and `cwd`.

Left as recorded, not fixed: `_num("1e5") → 0` (a string-formatted float token
count), and the fact that for the cross-fold scenario the `kind` tag and the
shape check are mutually redundant, so neither is individually pinned — the
guarantee there is structural (the two folds' key sets are disjoint), not
asserted.
