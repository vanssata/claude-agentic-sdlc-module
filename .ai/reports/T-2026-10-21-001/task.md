# T-2026-10-21-001 — release summary (T4, bugfix, solo direct mode)

path guard: the movers pass resolves and checks in 32 KB batches, not one realpath per segment (known-risks)

Plan: `~/.claude/plans/merry-tickling-moonbeam.md`, approved in plan mode. The
approach changed during remediation R1 (below): the plan's one `realpath` for
the whole line became one per 32 KB chunk, checked in batches. R2 fixed what
the scoped re-review of R1 found. R3, a third round the human opened in their
own terminal ("close HIGH-1 fully"), fixed what the re-review of R2 found. R4,
a fourth round opened the same way (Q3 = A), fixed what the re-review of R3
found. R1 is already committed by the human as `3d923d5`.

## What changed
- `hooks/ai-path-guard.sh`, the movers block only (`:693-947`):
  - Mover segments are parsed into a batch until the segment text read and the
    candidates made fill `MOVER_CHUNK` (32 KB, `:713`).
  - The test sits at the top of the parse loop (`:846`), before the segment
    is parsed. A segment that makes no candidate counts too (R2). A segment
    that would take the batch's text past 32 KB is parsed only after the batch
    is checked (R3).
  - A second test runs before a segment's candidates are built (`:902-904`,
    R4). It checks the batch when an upper bound of their absolute paths would
    take it past 32 KB. Each source makes at most two candidates and the
    destination one, none longer than the longer of cwd and HOME, plus the
    destination, plus the source.
  - The cwd prefix is computed once (`cwd_slash`, `:839`, R4).
  - `mover_check` keeps its own `verb`.
  - The quote runs at both ends of an operand or a destination are stripped in
    one step each, not one character at a time (R3, `:886-887`, `:916-917`).
    The trailing run is stripped bytewise by `quote_tail` (`:830`). Under a
    UTF-8 locale an invalid byte makes a pattern match by bytes, while
    `${#…}` counts characters.
  - `mover_check` (`:772`) then resolves the batch and checks its segments in
    order. The check body is HEAD's, re-indented. The `mv` "move of" test uses
    the segment's own first candidate.
  - `mover_resolve` (`:730`) makes one `realpath` and one `loose_hits` per
    32 KB of candidates, each step on the 6 s clock.
  - When a chunk's `realpath` drops a line (a symlink loop), that batch falls
    back to HEAD's path: each segment on its own, one candidate at a time, with
    the same `work_cap classify` counts.
  - A 4097-character glob operand sets `pending` (`:865`). It is denied after
    the segments before it are checked (`:946`), as on HEAD.
  - Index loops replace array slices, so the parse pass is linear.
- `tests/test-ai-path-guard.sh`, T-2026-10-21-001 block:
  - timed cases:
    - `rm x; ` ×1000 + `rm -f a.txt` is allowed within 2 s;
    - `rm x; ` ×1000 + the state file is denied within 2 s, with the
      control-file reason;
    - 400 symlink-chain segments + the state file are denied within 8 s;
    - the state file before `rm x; ` ×20000 is denied within 2 s, with the
      control-file reason;
    - R2: the state file before `rm -f; ` ×150000 is denied within 3 s, with
      the control-file reason;
    - R2: the state file before `rm <-f ×2000> y; ` ×200 is denied within 3 s,
      with the control-file reason;
  - R3: the state file before one 123 KB segment of 30 quote-padded operands
    is denied within 2 s, with the control-file reason;
  - R3: the state file among 24 quote-padded segments is denied within 2 s,
    with the control-file reason;
  - R4: the state file before an `rm` of 5000 operands under a 3.3 KB cwd is
    denied within 2 s, with the control-file reason;
  - R4: the state file before an `mv` of 3000 sources into a 4 KB destination
    is denied within 2 s, with the control-file reason;
  - R2: `rm` of 1500 files under a 1600-character cwd is allowed. This pins
    the accepted change below.
  - R3, characterization:
    - quote runs of both kinds around an `rm` operand still deny;
    - so do quote runs around a `cp -t` destination in the state directory;
    - an operand of quotes only names no file.
  - characterization, passing on HEAD:
    - deny order with a 4097-character glob operand, in both orders;
    - a later segment's `mv` destination still reads "copy or move into";
    - a symlink loop beside a symlinked state directory, in both orders.
  - The block's header comment now describes batches (re-review LOW).
- `.ai/project/known-risks.md`:
  - "Many mover segments … 6 s clock" is fixed, with its measurements and the
    accepted change;
  - new open entries:
    - `shell_segments` is quadratic on one long segment;
    - one amplifying symlink keeps `realpath -m` past the hook timeout;
    - `realpath`'s line count can balance while its lines are misaligned;
    - the token pass strips quotes one character at a time (R3, outside the
      movers pass).
- `README.md:805`: 2,616 → 2,904 assertions, measured. The old figure was
  stale before this task.

## Deliberately preserved
- Every decision and reason on lines that HEAD decides within its clock, with
  one accepted exception (below). This is checked by:
  - the characterization cases;
  - `tests/test-guard-characterization.sh`, byte-identical;
  - the first reviewer's 42 multi-segment probes against HEAD;
  - the re-reviewer's HEAD-against-R1 probes across batch boundaries.
- Deny order: an earlier segment's deny comes first, then a later segment's
  long-glob deny.
- The symlink-loop fallback and its counts.
- **Accepted change (Q1 = A, human):** one segment whose candidates pass
  `ARG_MAX` is now checked candidate by candidate.
  - On HEAD, `realpath` failed with E2BIG and the line was denied by the work
    cap. A line with nothing protected in it is now allowed.
  - Measured by the re-reviewer, with a cwd of 1524 characters: `rm` of 1500
    files went from deny in 0.52 s to allow in 2.2 s.

## Measurements (scratchpad probe, HEAD 2f7f9f7 → after)

Rows are `rm x; ` ×N + tail, or the segment shown.

| Line | HEAD | After |
|---|---|---|
| ×100 + `rm -f a.txt` | allow 0.68 s | allow 0.08 s |
| ×300 + `rm -f a.txt` | allow 1.98 s | allow 0.15 s |
| ×1000 + `rm -f a.txt` | **deny (clock)** 5.8 s | allow 0.29 s |
| ×1000 + the state file | deny (clock) 6.0 s | deny (control file) 0.30 s |
| ×3000 + `rm -f a.txt` | deny (clock) 6.0 s | allow 0.78 s |
| ×8000 + `rm -f a.txt` | deny (clock) 5.4 s | allow 1.9 s |
| `rm d/<3 KB>N; ` ×600 | deny (clock) 5.3 s | allow 4.0 s |
| `rm chain/<c/ ×2000>xN; ` ×400 | deny (clock) 5.2 s | deny (clock) 6.6 s |
| the state file; `rm x; ` ×20000 | deny (control file) 0.24 s | deny (control file) 0.30 s |
| the state file; `rm -f; ` ×150000 | deny (control file) 1.15 s | deny (control file) 1.37 s (R1: 5.2 s, work cap) |
| the state file; `rm <-f ×2000> y; ` ×200 | deny (control file) 1.13 s | deny (control file) 1.30 s (R1: 5.9 s, work cap) |
| the state file; one `rm` segment of 30 × `a""…` (123 KB) | deny (control file) 0.29 s | deny (control file) 0.31 s (R2: 5.8 s, work cap) |
| 16 × `rm a""…;`, the state file, 8 more | deny (control file) 4.46 s | deny (control file) 0.20 s (R2: 6.0 s, work cap) |
| the state file; `rm` of 5000 operands, cwd 3.3 KB | deny (control file) 0.11 s | deny (control file) 0.20 s (R3: 6.0 s, work cap) |
| the state file; `mv` of 3000 sources into a 4 KB destination | — | deny (control file) 0.16 s (R3: 6.0 s, work cap) |

What is left: an earlier deny waits for at most the parse of 32 KB of later
text and the build and resolve of about 32 KB of later candidates. The reason
can still change only where HEAD's own work before that deny is already within
that much of the 6 s clock.

The HEAD figures in the last six rows are from the re-reviewers' probes; the
after figures are from the suite.

The new quote strip gives the same result as the old loops on 30000 random
operands in each of C, C.UTF-8 and bg_BG.UTF-8. The operands used multibyte
characters, invalid bytes, `*` and `[`. It takes 1 ms instead of 260 ms on the
worst 4 KB operand.

## Verification
- Step tests after R4:
  - `tests/test-ai-path-guard.sh` 421/0;
  - `test-ai-scope-guard.sh` 25/0;
  - `test-ai-git-guard.sh` 40/0;
  - `test-guard-characterization.sh` 1/0.
- The new failing tests were shown failing first:
  - on HEAD, 4 failures: `rm x; ` ×1000 + `rm -f a.txt` was denied in 5.4 s,
    and the state-file deny took 6.0 s with `WHY_WORK_CAP`;
  - on the whole-line version, 3 failures: the chain took 33.7 s, and the early
    deny took 5.6 s with `WHY_WORK_CAP`;
  - on R1, 4 failures: the two new early denies took 5.2 s and 5.9 s with
    `WHY_WORK_CAP`;
  - on R2, 4 failures: the two quote-padded denies took 5.8 s and 6.0 s with
    `WHY_WORK_CAP`;
  - on R3, 4 failures: the long-cwd and long-destination denies took 6.0 s
    and 6.0 s with `WHY_WORK_CAP`.
- The ARG_MAX allow passes on R1. HEAD's deny on that line rests on the
  re-reviewer's measurement. The path guard refused the manager's own fixture
  write for it, and the command was not reworded.
- `bash tests/run-all.sh`: suite run 5, exit 0 in 384 s, 27 suites, 2904 passed,
  0 failed (`tests-suite-5.log`).
- `bash tests/test-end-to-end.sh`: e2e run 5, exit 0 (`tests-e2e-5.log`).

## Review
- Pass 1: `ai-reviewer` on STRONG (Opus 5.5) reviewed the whole-line version.
  Verdict `blockers_open`: no BLOCKER, 1 HIGH, 1 MEDIUM, 1 LOW.
  - HIGH: the whole-line `realpath` was a unit the clock could not stop.
  - MEDIUM: an early segment's deny waited for the whole line, and its reason
    became `WHY_WORK_CAP`.
  - LOW: `${cands[@]:first}` made the parse pass quadratic.
  - All three were fixed in R1.
- Pass 2: a scoped STRONG re-review of R1, at the human's request before gate
  G1 (`review-report.md`). Verdict `blockers_open`: 2 HIGH, 1 LOW, 2 INFO.
  - The first pass's HIGH and LOW are closed. Its MEDIUM was only partly
    closed.
  - HIGH-1: segments that make no candidates still delayed an early deny.
    Fixed in R2 and pinned.
  - HIGH-2: the ARG_MAX deny → allow. The human accepted it (Q1 = A); it is
    pinned and recorded.
  - LOW: the stale test comment. Fixed in R2.
  - The 2 INFO findings are older than this task. They are new open
    known-risks entries.
- Pass 3: a scoped STRONG re-review of R2, at the human's request. Verdict
  `blockers_open`. R2 introduced no regression, and HIGH-1's three inputs are
  closed.
  - HIGH: HIGH-1 was still open for one later segment that is slow to parse.
    The cause was the per-character quote strip.
  - The human answered "close HIGH-1 fully" and opened R3, the third round,
    in their own terminal. R3 fixed this, and tests pin it.
  - LOW: the option-heavy reason check does not reliably fail on R1. Its
    timed case does. Left as it is.
- Pass 4: a scoped STRONG re-review of R3. Verdict `blockers_open`. R3
  introduced no regression, and the quote shape is closed.
  - HIGH: HIGH-1 was still open for a later segment with many candidates under
    a long cwd. The batch was bounded by text, not by absolute-path bytes.
  - The human chose round R4 (Q3 = A) and opened it. R4 fixed this, and tests
    pin it.
- Pass 5: a scoped STRONG re-review of R4. Verdict `blockers_open`.
  - Pass 4's HIGH is closed, and HIGH-1 is closed. No further shape was found
    outside the stated residual.
  - The estimate was shown to be an upper bound, by a proof and by 1814 fuzzed
    segments.
  - Order and reason across the flush matched HEAD in 260 cases.
  - Open, HIGH by the brief's rule: a clock margin that fails closed. The
    estimate costs about 3.8 µs per mover segment with no candidates.
    `rm -f;` ×90000 is HEAD allow 6/6, R4 deny 1/6.
  - The human accepted it (Q4 = A). It is recorded as an open known risk.
- `review_status` stays `blockers_open`, and it is not cleared. The one open
  item is the accepted fail-closed margin above.
- Security review: not applicable. No authentication, authorization or
  personal data is involved. The guard is a backstop, and its deny side is
  preserved.

## Open
- Sensors:
  - `tests` is STALE: after suite run 5, only the Q4 entry in
    `.ai/project/known-risks.md` changed (docs). The code, the tests and
    README are identical to run 5's tree.
  - `lint` is red. `pylint` was installed during the task and reports 3
    warnings in Python files this task did not touch: `sensors.py:409`,
    `update.py:264` and `build-template-history.py:39`. This is an existing
    failure, not fixed here.
  - `traceability` is red: the inline `quick` step names no test.
- Process: the path guard refused two manager commands, and neither was
  reworded:
  - a probe whose text named the state file;
  - a fixture write of a scratchpad `.ai/policies/path-guard.json`.
  The re-reviewer's probes and its copies of HEAD and R1 are in the session
  scratchpad.
- Accepted residual (Q4 = A): batched movers cost a few µs more per segment,
  which matters near the clock on lines of about 540 KB with no candidates.
  It fails closed only. It is a new open known-risks entry.
- Four open known-risks entries are older than this task, each its own hooks
  task:
  - `shell_segments` is quadratic on one long segment;
  - one amplifying symlink can keep `realpath -m` past the hook timeout;
  - `realpath`'s line count can balance while its lines are misaligned;
  - the token pass strips quotes one character at a time.

## Rollback
`git revert` the R2–R4 commit, then `3d923d5` (R1, committed by the human).
There is no migration and no state format change.
