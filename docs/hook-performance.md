# Hook performance — the hot path

The three shell guards (`ai-git-guard`, `ai-path-guard`, `ai-scope-guard`) are the
only part of claude-agentic that runs on **every** tool call, at every risk tier,
including the T0 work the pipeline never touches. A session makes 150–200 tool
calls; a guard that costs 150 ms costs the user half a minute of pure waiting per
task, and nobody sees it in a token report.

So the guards are measured, not estimated, and the measurement is written down
here.

## The rule that comes first

**The rules are the product. How a rule is evaluated is an implementation detail
that may be optimised freely — as long as the decisions do not move.**

Every change made for speed is proved behaviour-preserving by
`tests/test-guard-characterization.sh`: 721 guard runs — every fixture payload,
~120 shell commands aimed at each individual rule, the file tools, the Codex
payloads, malformed input, a protected and a feature branch, the shipped defaults
and user/project overrides — compared with
`tests/fixtures/guard-characterization/golden.txt` byte for byte, **exit code and
full deny text**. A deny that names a different pattern is a failure.

A performance change may not edit that test or re-record its golden file. If the
golden file has to move, the change was not a performance change; it is a rule
change, and it goes through review as one.

```bash
bash tests/test-guard-characterization.sh            # must be byte-identical
bash tests/test-guard-characterization.sh --record   # only after a deliberate rule change
```

## The budget

Per guard, per tool call, on a project that has opted in (`.ai/` present):

| Guard | processes | wall clock |
|---|---|---|
| `ai-git-guard`, Bash call | ≤ 8 (≤ 12 for a rule that asks git) | ≤ 120 ms |
| `ai-path-guard`, Bash call | ≤ 8 | ≤ 110 ms |
| `ai-path-guard`, file tool | ≤ 8 | ≤ 110 ms |
| `ai-scope-guard`, file tool | ≤ 8 | ≤ 80 ms |
| any guard, project without `.ai/` | ≤ 4 | ≤ 50 ms |

Processes are the number that must not regress: it is deterministic and portable.
Wall clock is machine-dependent and is a sanity bound, not a contract — the
figures below were taken on a 32-core Linux 7.0 box with bash 5.3, where a bare
`bash -c 'exit 0'` costs 3 ms, `jq -n 1` 4 ms and `python3 -c pass` 15 ms.

## Measured, 2026-09-20

| Call | processes | ms |
|---|---|---|
| `ai-git-guard`, `git status` | 6 | 85 |
| `ai-git-guard`, `git push` (asks git for the branch) | 10 | 112 |
| `ai-path-guard`, `git status` (nothing interesting on the line) | 6 | 68 |
| `ai-path-guard`, `cat .env` — denied | 8 | 101 |
| `ai-path-guard`, Read a normal file | 8 | 88 |
| `ai-path-guard`, Edit a normal file | 8 | 97 |
| `ai-path-guard`, Edit with no `.ai/` | 4 | 45 |
| `ai-scope-guard`, Edit inside the step | 6 | 62 |
| `ai-scope-guard`, Edit outside the step — denied | 7 | 68 |
| `ai-scope-guard`, Edit with no `.ai/` | 4 | 44 |

Two rounds of work got there.

**Round 1 — `ai-git-guard` and `ai-path-guard`** (`perf/guard-hook-process-count`).
They ran on nearly every Bash call and spent their time on processes, not on work:
74 per Bash call (22 `grep`, 14 `jq`, plus `tr`/`sed`/`dirname`/`paste`).
`read_payload` now reads every field in one `jq` call; `ere_match` replaces
`printf | grep -qE` in-process, keeping grep's line-by-line semantics so a bracket
expression still cannot match across a newline; `find_ai_root` walks up with
parameter expansion; `strip_prose` calls python only for a command that actually
has a heredoc or a message flag; the path guard's six `jq` calls and three sorts
for the pattern lists became one `jq` per file and one `sort -u` (the sort stays,
because its locale order decides which pattern a deny message quotes).
74 → 25 processes per Bash call; `git status` 212 → 46 ms, `git push` 214 → 63 ms,
an Edit in an `.ai/` project 127 → 82 ms.

**Round 2 — `ai-scope-guard`** (WP8). It was the one guard left on the old shape:
seven `jq` calls against the state file and a `python3 -c` **per path per pattern
list** for glob matching. The state file is now read by one `jq` call that emits
every field it needs — each list value tagged with its list and split on newlines
exactly as `jq -r '.allowed_files[]?'` printed it, the plan's reason last so a
multi-line reason survives — and `match_glob` uses bash's own pattern matching,
which has the fnmatch semantics the plan globs want (`*` crosses `/`, `[!x]`
negates). `dirname` is gone from the `HOOK_DIR` line, as it already was in the
path guard.
15 → 6 processes per Edit, 158 → 62 ms; a denied edit 16 → 7 and 162 → 68 ms.
`tests/test-guard-characterization.sh` passed unchanged across the whole change.

## How to measure

There is no bench script in the repository on purpose — a number recorded once and
never re-run is worse than no number. Measure with `strace`, counting only
*successful* `execve` calls, because bash probes every `PATH` entry and those
failures are not processes:

```bash
printf '%s' "$PAYLOAD" | strace -f -e trace=execve hooks/ai-path-guard.sh 2>&1 >/dev/null \
  | grep 'execve(' | grep -vc 'ENOENT'
```

and take wall clock over at least 40 runs, never one:

```bash
time (for i in $(seq 40); do printf '%s' "$PAYLOAD" | hooks/ai-path-guard.sh >/dev/null; done)
```

A payload is the PreToolUse envelope the runtime sends; the fixtures under
`tests/fixtures/` are real ones.

## What is deliberately not done

- **Porting the Python hooks to a compiled language, or shipping per-platform
  binaries.** The remaining floor is interpreter startup (a few ms for bash and
  jq, ~15 ms for python). Trading cross-platform simplicity and readability for
  that is refused.
- **Parsing the payload JSON in bash.** Same trade, worse: a hand-written JSON
  parser in bash is a correctness risk on the one code path that must never
  break.
- **A resident guard daemon.** A background process that has to be started,
  found, versioned and killed is a much larger operational surface than the
  milliseconds it saves.
- **Caching a decision between calls.** The inputs (the command, the state file,
  the policy files) change under the guard's feet; a stale allow is exactly the
  failure the guards exist to prevent.

## Where the remaining cost is

Roughly half of an armed guard's wall clock is now interpreter startup — its own
bash plus the one or two `jq` calls it cannot avoid (`read_payload`, and
`target_paths` or the pattern lists). The rest is the guard's own matching, which
runs in-process. A guard in a project **without** `.ai/` is already at the floor:
bash, one `jq` for the payload, and an exit.

That is the accepted end state. The next meaningful saving would be one of the
four refused items above.
