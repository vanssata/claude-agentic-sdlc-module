# Review report — T-2026-10-21-001

## Pass 2 — scoped STRONG re-review of R1 (tree 8fe3e99 against 2ff5577 and HEAD 2f7f9f7)

Asked for by the human before gate G1. `ai-reviewer` on opus. The reviewer
compared copies of HEAD and R1 in the session scratchpad; probes went through the
`st -> .ai/state` symlink, so no command text named a protected path.
`bash tests/test-ai-path-guard.sh`: 399 passed, 0 failed.

Verdict: **blockers_open** — 2 HIGH, 1 LOW, 2 INFO (both older than this task).

### Findings
- **HIGH-1: an early deny still waits, and gets `WHY_WORK_CAP`, when the later segments add few or no candidates**
  (`hooks/ai-path-guard.sh:892`, `:903`, `:906`)
  - Cause: the batch is checked only when candidate bytes reach 32 KB, or at
    the end of the line. These segments add nothing to the batch but still cost
    parse time:
    - `rm -f` and `mv a` make no candidate and `continue` at `:892`;
    - an option-heavy segment adds one small candidate.
  - Measured:

    | Input | HEAD | R1 |
    |---|---|---|
    | `rm st/current.json; ` + `rm -f; ` ×150000 + `rm y` | deny 1152 ms, control-file reason | deny 5011 ms, `WHY_WORK_CAP` |
    | `rm st/current.json; ` + `mv a; ` ×150000 | deny 1004 ms, control-file reason | deny 5562 ms, `WHY_WORK_CAP` |
    | `rm st/current.json; ` + `rm <-f ×2000> y; ` ×200 | deny 1130 ms, control-file reason | deny 5136 ms, `WHY_WORK_CAP` |

  - Direction: also check the batch on parse work, not only on candidate bytes.
- **HIGH-2: lines HEAD denied through the E2BIG fallback are now allowed**
  (`hooks/ai-path-guard.sh:728-747`)
  - Cause: HEAD made one `realpath` per segment. Past ARG_MAX that call got
    E2BIG, fell back to one candidate at a time with `work_cap classify`, and
    denied at 65. R1's 32 KB chunks never reach E2BIG, so every candidate is
    checked.
  - Measured, with a cwd of 1524 characters:

    | Input | HEAD | R1 |
    |---|---|---|
    | `rm` of 1500 files (a 10 KB command) | deny 516 ms, `WHY_WORK_CAP` | allow 2156 ms |
    | `rm` of 2500 files | deny 704 ms | allow 3731 ms |
    | `mv` of 1500 sources | deny 535 ms | allow 2573 ms |

  - Not a bypass: only lines whose candidates are all checked and clean change
    from deny to allow.
  - `.ai/project/known-risks.md:152` calls the change intended and says it was
    not measured; that inference is refuted.
  - **Needs a human decision: Q1.**
- **LOW: stale comment.** `tests/test-ai-path-guard.sh:309-311` still says one
  `realpath` for every candidate on the line.
- **INFO, outside the task: one candidate can keep `realpath -m` past the 10 s timeout, on HEAD and R1 alike.**
  - Setup: a symlink `d -> c/…(×2000)/.` and a 400-byte operand
    `d/d/…(×200)/x`.
  - Measured: `realpath -m` alone takes 13.3 s; through the guard, HEAD takes
    13.4 s and R1 13.6 s.
  - Goes to known-risks.
- **INFO, outside the task, reasoned and not run: a shifted `reals[]` can hide a symlink.**
  - `:741` checks only how many lines `realpath` returned. Inside one chunk, a
    symlink loop drops a line and a target with a newline adds one, so the
    count still balances and the `reals` between them are misaligned.
  - HEAD has the same weakness within one segment; R1 also allows it across
    the segments of one chunk.
  - Goes to known-risks.

### The first pass's findings
- HIGH, a unit the clock cannot stop: **closed**. No unit is larger than one
  32 KB chunk plus one candidate. Chain ×400 + the state file: HEAD 5.2 s,
  R1 6.3 s.
- MEDIUM, an early deny comes late with the wrong reason: **partly closed**.
  It is fixed when the later segments add candidates (0.36 s with its own
  reason) and still open when they add none (HIGH-1).
- LOW, the parse pass is quadratic: **closed**. `rm x; ` ×2000…16000 takes
  0.77…5.97 s, which is linear.

### Examined and clean (HEAD and R1 side by side)
- the chunk-spanning `hits[3 * at + r]` index;
- a fallback that starts in a later chunk;
- `per_seg` and `seg_first` across batches;
- the `mv` wording in batch 2 and later;
- the order of the pending long-glob deny across batches;
- the classify cap of 64 across a batch boundary;
- the globals shared between `mover_check`, `mover_resolve` and the parse loop;
- operands over 32 KB or over `MAX_ARG_STRLEN`.

Probe scripts are `p2.sh`…`p10.sh` in the session scratchpad.

## Pass 3 — scoped STRONG re-review of R2 (working tree against 8fe3e99)

Asked for by the human (choice A). The reviewer ran `ai-reviewer` on opus and
probed copies of HEAD, R1 and R2 in the scratchpad (`q1.sh`…`q8.sh`).

Verdict: **blockers_open**. HIGH-1 still has one residual case, and R2
introduced no regression.

### Findings
- **HIGH: HIGH-1 is still open for one later segment that is slow to parse**
  (`hooks/ai-path-guard.sh:829`, `:876-877`)
  - Cause: the batch is checked only at the top of the parse loop, so one
    segment is the smallest unit. The quote-strip loops at `:876-877` cost
    about 0.27 s per 4 KB operand, and nothing in them checks the clock.
  - Measured: `rm st/current.json; rm` + 30 × (` a` + `""`×2047), one later
    segment of 123 KB.

    | Guard | Decision | Time | Reason |
    |---|---|---|---|
    | HEAD | deny | 0.29 s | control file |
    | R1 | deny | 5.2 s | `WHY_WORK_CAP` |
    | R2 | deny | 6.0 s | `WHY_WORK_CAP` |

  - Batch-aligned variant (16 such segments, the control file, 8 more): HEAD
    deny 4.46 s with the control-file reason; R2 deny 5.23 s with
    `WHY_WORK_CAP`.
  - In every case the decision stays deny; only its reason and its time
    change.
  - R2 did not cause this: R1 has it too.
- **LOW: one new reason check does not reliably fail on R1.** The check on the
  option-heavy case (`tests/test-ai-path-guard.sh:367-371`) depends on whether
  R1 crosses 6 s. The 3000 ms timed case pins it.
- **INFO: the 3000 ms budgets are not flaky.** R2 takes 1.18–1.32 s, against
  HEAD's 0.93–1.14 s.

### Closed and clean
- Pass 2's three HIGH-1 inputs are denied with the control-file reason in
  1.2–1.3 s.
- Across a batch edge, 50 cases match HEAD in decision, order and reason:
  - the control file, a vendor deny and the pending glob;
  - a symlink loop and the `mv` wording;
  - batch edges made by segment text alone;
  - the classify cap of 64 across an edge.
- No half-built batch is seen, nothing the iteration uses is clobbered, and the
  loop's stdin is left intact.
- The HIGH-2 test crosses ARG_MAX on HEAD: 2,434,893 bytes or more against
  2,097,152.

## Pass 4 — scoped STRONG re-review of R3 (tree 064f7ee against 18957fc)

Verdict: **blockers_open**. HIGH-1 is still open in a further shape. R3
introduced no regression.

### Findings
- **HIGH: an early deny still waits for the whole batch to be resolved when a later segment has many candidates**
  (`hooks/ai-path-guard.sh:841`, `:914`, `:775`)
  - Cause:
    - the pre-parse flush at `:841` bounds a segment's text, not the
      absolute-path bytes its candidates add at `:914`;
    - `mover_check` resolves every chunk of the batch before it checks
      segment 0 (`:775`).
  - Measured (`u1.sh`–`u3.sh`):

    | Input, after the state file | HEAD | R3 |
    |---|---|---|
    | `rm` ×5000, cwd 3349 characters | deny 0.11 s, control-file reason | deny 5.63 s, `WHY_WORK_CAP` |
    | `mv` ×5300, cwd 1524 characters | deny 0.11 s, control-file reason | deny 5.99 s, `WHY_WORK_CAP` (R2: 5.95 s) |

  - R1 and R2 have this too.
- **Manager's measurement, the same class:** building the absolute paths of
  16000 operands under a 4 KB cwd takes 5.5 s in bg_BG.UTF-8 and 1.9 s in C.
  `${AI_CWD%/}` is recomputed for every candidate; computed once, it takes
  1.2 s and 0.47 s.
- **INFO:** under bash 5.3.9 with UTF-8, the old loop returns random bytes for
  words that start with `\303\\`. R3 returns the correct result. The input
  cannot reach the hook: jq turns invalid UTF-8 into U+FFFD.

### Closed and clean
- The pass-3 inputs are denied in 0.20–0.30 s with the control-file reason.
- The new strip equals the old loops in C, POSIX and six UTF-8 setups, on
  30,000 words each. The alphabet included backslash, brackets, `!`, `^`, `-`,
  `*` and `?`.
- `quote_tail` restores the locale and its export state. Neither `qrun` nor
  `quoted` leaks or collides with another name.
- Across the pre-parse flush, 221 cases match HEAD in deny order and reason:
  the pending glob, the loop fallback, the `mv` wording and the classify cap
  of 64.
- `quote_tail` costs about 20 µs per call, and no parse step costs more than
  linear time.

## Pass 5 — scoped STRONG re-review of R4 (tree 0eedadbe against effa634)

Verdict: **blockers_open**. Pass 4's HIGH is closed. One open item remains: a
clock margin that fails closed.

### Findings
- **HIGH by the brief's rule; fails closed: the estimate block costs about 3.8 µs per mover segment with no candidates** (`hooks/ai-path-guard.sh:897-904`)
  - Measured (`x7.sh`, `x8.sh`): `rm -f;` ×N, short cwd, mean of several runs:

    | N | HEAD | R3 | R4 |
    |---|---|---|---|
    | 90000 | 4.65 s, 6/6 allow | 4.56 s, 6/6 allow | 5.15 s, 1/6 work-cap deny |
    | 95000 | 4.69 s, 3/3 allow | 5.18 s, 1/3 deny | 5.42 s, 2/3 deny |

  - Only lines of about 540 KB of mover segments with no candidates are
    affected.
  - A deny never becomes an allow.
  - R1–R3 already cost about 2 µs per segment more than HEAD.
- **INFO:** shapes that flush before every segment now cost the same as HEAD.
  `cp a <4 KB dest>;` ×200: HEAD 3.61 s, R3 2.80 s, R4 3.60 s.
- **INFO:** a pre-build flush resets `batch`, which drops the current
  segment's text count. That text is already parsed.

### Closed and clean
- Pass 4's inputs are denied with the control-file reason in 0.12–0.21 s.
  HEAD takes 0.09–0.12 s; R3 took 5.6–6.0 s.
- The estimate is an upper bound, shown by a proof and by 1814 fuzzed
  segments across:
  - all seven verbs;
  - `~`, `$HOME` and `${HOME}`;
  - `-t`, `--target-directory=` and `--`;
  - quote runs;
  - multibyte characters;
  - operands over 4096 characters;
  - the C and bg_BG.UTF-8 locales;
  - several cwd and HOME values.
  There were 0 violations.
- Deny order and reason, the pending glob, the loop fallback, the `mv`
  wording and the classify cap of 64 across the pre-build flush match HEAD.
  This held in 260 cases, and the flush fired 243 times.
- A flush clobbers none of the current segment's state.
- In about 10 minutes the reviewer found no further shape outside the stated
  residual.
