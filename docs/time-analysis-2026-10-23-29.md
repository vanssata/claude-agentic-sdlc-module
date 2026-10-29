# Where the time goes — transcript analysis, 2026-10-23 … 2026-10-29

Status: analysis, nothing changed. Written 2026-10-29 from the Claude Code
transcripts of this project (115 sessions, 81 subagent transcripts) and the
`state.json` of the 31 tasks closed in the period (`.ai/state/logs/T-2026-10-2*/`).
Every number below was computed from those files; the scripts that produced them
are not in the repository.

Method: for every `tool_use` in a transcript the wall time is the gap to its
`tool_result`; session totals come from the `cost-state` record Claude Code
writes (`totalDuration`, `totalAPIDuration`, `totalToolDuration`); per-task
figures come from `verify.runs[].duration_s`, `created_at` and `closed_at`.
Per-file suite timings come from running each `tests/test_*.py` on its own on
2026-10-29 (six in parallel).

## 1. The budget

| Component | Minutes in the period | Note |
|---|---|---|
| Session wall | 6 762 | 68 % is human wait or sessions left open (six sessions idle 5–12 h) |
| API / model time, main thread + agents | 1 535 | 12 058 assistant messages in main threads, ~7.6 s each |
| Tools, main thread | 643 | 64 % of it is test commands |
| ↳ test commands | 412 | 1 434 runs in main threads, 494 more inside subagents |
| ↳ whole suite (`verify --scope all`) | 249 | 59 real runs, median 247 s, max 380 s |
| Subagents, wall | 622 | 41 reviews = 450 min; 3 architect runs = 76 min |
| Dialogs to the human (AskUserQuestion) | 266 | 35 dialogs; one alone is 145 min; median 69 s |

A typical task, median from `start` to `close`: **51 min**, of which 9.5 min is
the whole suite and about 11 min the review. Planning before `start` adds a
median 6 min. Token cost for the period: $604 (Opus $503, Fable $114, Sonnet
$30).

Per day:

| Day | Sessions | Wall min | API min | Tool min | Test runs | $ |
|---|---|---|---|---|---|---|
| 10-24 | 7 | 261 | 103 | 47 | 37 | 38 |
| 10-25 | 31 | 1 116 | 325 | 104 | 296 | 133 |
| 10-26 | 13 | 2 198 | 225 | 174 | 374 | 98 |
| 10-27 | 21 | 1 106 | 345 | 145 | 607 | 133 |
| 10-28 | 33 | 1 525 | 433 | 91 | 392 | 167 |
| 10-29 | 10 | 557 | 104 | 83 | 222 | 35 |

## 2. Tests: the suite is serial and runs more than once per task

The number of tests is not the cost by itself. The cost is a serial suite run
two to three times per task.

**The suite.** `verify_command` is `python3 -I -m unittest discover -s tests -p
'test_*.py'`: 905 tests, 319 s, one process. Measured file by file (55 files,
sum 359 s), the ten slowest files are 70 % of the time:

| File | Seconds | Tests | Why |
|---|---|---|---|
| test_ai_task_state.py | 86 | 174 | `git init` + commits + a state.py subprocess per test |
| test_memory_store.py | 25 | 7 | |
| test_project_adopt.py | 23 | 41 | |
| test_ai_path_guard.py | 23 | 21 | |
| test_memory_sync.py | 21 | 25 | |
| test_context_guard.py | 18 | 20 | |
| test_memory_recall.py | 16 | 10 | |
| test_install_dry_run.py | 15 | 23 | |
| test_memory_pre_push.py | 12 | 23 | |
| test_memory_cleanup.py | 12 | 9 | |

The longest file sets the floor for a parallel run: about 90 s instead of 319 s.
One file cannot run in parallel with the others:
`test_guard_characterization.TestTimed.test_budgets` asserts hook latency
budgets of 25–40 ms and fails under CPU contention (measured: 56 ms against a
40 ms budget with six files running). It has to run alone.

**Runs per task.** `suite_runs` over the 31 tasks: 15 tasks ran it twice, 8
three times, 3 four or five times, 3 never, 2 once. 54 of 69 whole-suite runs
were green; 10 of 28 first runs were red. Of the 22 `--after-fix` reruns:

| Trigger of the rerun | Runs | Minutes |
|---|---|---|
| review findings MEDIUM/LOW only | 9 | ~40 |
| review findings with HIGH or BLOCKER | 6 | ~24 |
| real regressions after the first run | 5 | ~22 |
| other | 2 | ~10 |

`rr-review` asks for "every in-scope HIGH (and the MEDIUMs worth it)"; in
practice MEDIUM and LOW findings were fixed in-task and each fix bought a
whole-suite run.

**The "tree moved" rule.** `two_facts` in `state.py` (around line 3990) wants a
green whole-suite run on the tree as it is now; any edit after the last run,
including one in a `.md`, owes a fresh 300 s run. Seen in the transcripts:
session 7520bc68 at 11:10 ran `cat >> .ai/project/known-risks.md … && verify
--scope all` (300 s) for one appended paragraph; session f5004fb2 at 16:43 ran
`start --amend … && verify --scope all` (327 s) for a LOW finding about the
wording of C5.

**Documentation tasks burn mostly in the suite.** T-2026-10-29-1636 (C5/C6
shortened): 13 min total, 10.7 min suite. T-2026-10-29-1655 (three risks
recorded): 24 min, 15.9 suite. T-2026-10-28-007: 12 min, 6.4 suite.

## 3. Reviews and the rest

- **30 of 31 tasks were guarded or full** (one light), so a review ran every
  time. Median review 7 min, mean 11 min, median 65 messages and ~75 k output
  tokens per review (3.0 M in total, 1.9 M of them thinking).
- **Two Sonnet reviewers were out of scale.** Session 4d466ac5, "Review guard
  port 3.1": 90 min, 80 Bash calls, 77 min inside shell experiments in its
  scratchpad, one command 582 s. Session 92dd5015, "Review 3.3a suite port":
  44 min, mutation runs under `scratchpad/mut`. Together 134 of the 450 review
  minutes. Sonnet reviews were not faster than Opus ones (717 s vs 616 s mean).
- **Tool-call count.** About 5 900 tool calls in main threads, 954 of them to
  state.py (~30 per task). Every call also costs one model turn (~8 s), so the
  chain of commands weighs more than the commands themselves.
- **Edit latency.** Median 2.8 s per Edit (746 edits, 82 min). The PreToolUse
  hooks take 0.01 s on a sample payload; the time is in the harness, not the
  guard. Minor.
- **Human dialogs** are not a process problem: 266 min, but 145 of them is one
  dialog left open (session 914679c5, Q1 of step s2); the median wait is 69 s.

## 4. What to change, by minutes saved per task

1. **Run `verify_command` in parallel by file.** 319 s → ~90 s; at 2.2 runs per
   task about 8 min saved. Needs a runner (pytest-xdist or a short script that
   runs one `unittest discover -p <file>` per process), with `TestTimed` kept
   serial and alone. Longer term: let `test_ai_task_state.py` share its git
   fixture across tests (86 s → well under 20 s).
2. **Stop rerunning the whole suite for MEDIUM/LOW fixes and documentation-only
   edits.** Nine of the 22 reruns, plus the model turns around them. A
   candidate rule for `close`: when the diff since the last green run touches
   only non-code files, accept `verify --scope step` or `--files` for it. This
   changes production behaviour of state.py and is recorded here as a proposal
   only.
3. **Bound the reviewer.** Read the diff, run the named tests, no experiments
   in the scratchpad, a tool budget (about 40 calls). The two outliers alone
   are 134 of 450 minutes.
4. **Weight.** With 30 of 31 tasks in guarded or full, the mode is a constant,
   not a tier. Documentation and test-only changes as light would save the
   review (~11 min) and one whole-suite run each. CLAUDE.md already notes the
   over-scoring for hooks, skills and state.py; the data shows it for `.md`
   changes too.
5. **Fewer separate steps.** `step-done && verify --scope all` in one command
   is already common; the same for review → verify → close saves ~8 s of model
   time per avoided call. Secondary.

With 1–3 in place the median task should fall from 51 min to roughly 30–35
min without removing a single test.
