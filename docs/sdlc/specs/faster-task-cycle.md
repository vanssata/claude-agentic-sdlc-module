# Spec: Faster task cycle — parallel suite, fewer reruns, bounded review

Intent: none on file. This document carries its own intent (below); the
evidence is `docs/time-analysis-2026-10-23-29.md` and the brainstorm record
`docs/sdlc/intent/faster-task-cycle.questions.md`.

## Intent

**Problem.** Over 23–29 Oct 2026 the median task took 51 min from `start` to
`close`. 9.5 min of that is the whole test suite (905 unittest tests, 319 s,
one serial process, run 2.2 times per task) and about 11 min is the review.
Nine of 22 after-fix suite reruns were bought by MEDIUM/LOW review findings;
documentation-only edits after the last green run force another 300 s run
because `two_facts` wants a whole-suite run on the tree as it is now. 30 of
31 tasks ran guarded or full although many changed only `.md` files. Two
reviewers spent 90 and 44 min on experiments of their own in a scratchpad.

**Outcome (testable).**
- `verify_command` finishes in under 120 s on this machine (today 319 s),
  with the same test ids as `unittest discover` and ten consecutive green runs.
- `verify.suite_runs` per task in `.ai/state/logs/*/state.json` drops below
  today's median of 2 for the tasks that follow.
- No test is deleted, skipped or weakened.
- A review has an upper bound on its own tool use and runs nothing but the
  named tests.

**Affected.** This repository's pipeline only: `tests/`, `skills/ai-task/state.py`
and `sensors.py`, the rr-* skill texts, the reviewer agent template,
`README.md`, `CONTRIBUTING.md`, `docs/weight.md`. `.ai/policies/testing.md`
and `.ai/policies/weight.json` change too, but by the human after the task
closes (see Flagged concerns 1). User projects are untouched: both new rules
are off while their policy key and line are absent.

**Constraints and non-goals.**
- stdlib only (`python3 -I`), no pytest, no new dependency (Q2).
- The guard golden stays byte-identical; nothing under `hooks/` changes.
- The fixture refactor of `tests/test_ai_task_state.py` is a refactoring and
  therefore its own light task before the batch (C3), not a row of it.
- Not in scope: shipping the two new policy keys to user-project templates,
  a new `rr-status --cost` sensor, a tier change for reviews.

**Open questions.** Listed at the end; four are the human's, none blocks the
plan except the `doc_tests` list, which row 2 confirms by measurement.

### Decisions taken

From `docs/sdlc/intent/faster-task-cycle.questions.md`, in the order asked:

- **Q1 = C.** Step 2 is both: text (rr-review, testing.md: MEDIUM/LOW
  findings are recorded with `state.py memory risk add`, not fixed in the task)
  and `state.py` (`close` accepts a scoped verify when the diff since the last
  green whole-suite run touches only documents).
- **Q2 = A.** Parallel runner `tests/run_suite.py`, stdlib only, one process
  per test file, merged unittest output, exit 1 on any red, `TestTimed` run
  serially after the parallel phase.
- **Q3 = A.** The reviewer bound is text only, in `skills/rr-review/SKILL.md`
  and `agents/ai-reviewer.md.tmpl`: diff plus the named tests, no scratchpad
  experiments, about 40 tool calls.
- **Q4 = B.** A new light example in `weight.json` for this repository plus a
  deterministic rule in `state.py weight`: a documents-only change scores
  behaviour 0; the human raises it with `--declare`.
- **Q5 = A.** Step 5 is text only (chained commands in rr-build / rr-review /
  rr-ship); acceptance is `verify_command` < 120 s and `suite_runs` per task.

## Requirements

Each names the step (1–5) and the outcome it serves.

- **R1 (1, <120 s).** `tests/run_suite.py` runs every `tests/test_*.py` in its
  own `python3 -I` process, concurrently, and prints a merged unittest-shaped
  tail (`Ran N tests in Xs`, then `OK` / `OK (skipped=N)` / `FAILED (...)`),
  which `healthy_output` in testing.md:92-93 and the README count depend on.
  Proof: new `tests/test_run_suite.py` on fixtures `tests/fixtures/run-suite/`.
- **R2 (1).** No test lost: `run_suite.py --collect` prints the same ids as
  `TestLoader().discover("tests", "test_*.py")`; on the real suite both print
  the same N. Proof: a parity test in `test_run_suite.py`.
- **R3 (1).** Fail-safe: exit 1 on a failure, error, import error, crash,
  timeout, missing or unparseable result, or unexpected success; never exit 0
  without a parsed result for every file; no fail-fast (testing.md:53-55).
  Proof: one fixture per case. A false green here is BLOCKER-class (CLAUDE.md):
  each case is pinned by a test before the runner becomes `verify_command`.
- **R4 (1).** `test_guard_characterization.TestTimed` (tests/test_guard_characterization.py:581)
  is excluded from the parallel phase and run alone afterwards; the serial id
  list is data (`--serial`), `AI_TIMED_FACTOR` is passed through, never set.
  Proof: a fixture serial case asserts no sibling is alive (lock file).
- **R5 (1).** A per-file timeout kills the child's process group; SIGTERM or
  SIGINT kills every child and exits 1. Proof: a hang fixture with `--timeout 2`.
- **R6 (1, acceptance).** Measured, not unit-tested: under 120 s, ten
  consecutive green runs, `git status --porcelain` unchanged after a run.
- **R7 (own task 1F).** `tests/test_ai_task_state.py` keeps its 174 ids,
  `git diff -U0 | grep '^-.*assert'` is empty, the file time is reported before
  and after; target ≤ 40 s (see Design d and Flagged concerns 2).
- **R8 (2a).** rr-review §4, rr-build-all §5 and testing.md say: MEDIUM and
  LOW findings go to `memory risk add`; only a BLOCKER, a HIGH or a regression
  buys an `--after-fix` run. Proof: grep in `test_skills_surface.py`.
- **R9 (2b).** `close` grants fact (a) through the documents rule D1–D5
  (Design b). Proof: `TestDocumentsOnly` in `test_ai_task_state.py`, one case
  per predicate and per refusal that must survive.
- **R10 (2b, C2).** Characterization first, in a project without the
  `documents` key and the `doc_tests` line: an edit to `README.md` after a green
  run still exits 2 "the tree changed after the last verify"; red on this tree
  still refuses; the R19 Codex cases are unchanged. These tests stay green
  after the feature.
- **R11 (3).** The bound text is present in `agents/ai-reviewer.md.tmpl` and
  rr-review §2. Proof: `test_codex_agent_render.py`,
  `test_shared_prompts_model_free.py`, `test_skills_surface.py`.
- **R12 (4).** With a `documents` table, a documents-only change weighs
  `scope/0/0/0/0/0`; a goal keyword still gives behaviour 1; a pipeline hint
  still adds 1; `--declare behaviour=n` replaces 0. Proof: `TestDocumentsOnly`
  in `tests/test_weight.py` through the `state.py weight` CLI.
- **R13 (4).** After `start --amend` adds a non-document and the diff contains
  it, `verify` or `close` restores the zeroed axes upward and raises the mode
  with a `weight_raised` event. Proof: `TestRescore` in `test_ai_task_state.py`.
- **R14 (4, C2).** Characterization: without the key, scoring is unchanged;
  `test_argocd_dev_manifest` in `test_weight.py` is unchanged.
- **R15 (5).** The chaining text keeps every skill under the 400-line cap
  (`test_instruction_budget.py:68-74`).
- **R16 (outcome).** `verify.suite_runs` per task is read from
  `.ai/state/logs/*/state.json` over the next tasks and reported in the plan.

## Design

### (a) `tests/run_suite.py`

- A `ThreadPoolExecutor` with `--jobs` workers (default `os.cpu_count()`, 32
  here). Each worker spawns `python3 -I run_suite.py --child FILE --result
  TMP/FILE.json [--exclude ID]…` with `start_new_session=True`, stdin
  `DEVNULL`, stdout and stderr to `TMP/FILE.log` (files, not pipes: no
  deadlock with many children). The child runs
  `TestLoader().discover(start, pattern=basename, top_level_dir=start)`, the
  same semantics as `discover -s tests -p FILE`, drops excluded ids, runs
  `TextTestRunner(failfast=False)`, writes a JSON result.
- Longest-first scheduling with file size as the proxy. Phase 2 runs each
  serial id alone (`--child --only ID`).
- Nothing is written inside the repository; `TMP` is `mkdtemp`. `__pycache__`
  is git-ignored, so `run_v7`'s tree check (state.py:3653-3662) stays still.
- Output: one line per file, the serial lines, then for each red file
  `==== FAIL <file> (<why>) ====` + its full log + `==== end <file> ====`,
  then the unittest summary. Red sections come last because `cap_log`
  (sensors.py:243-259) keeps head and tail. The log already lands in
  `.ai/state/logs/<task>/suite-N.log`; the agent greps `^==== FAIL`.
- Rejected: pytest-xdist (Q2); `xargs -P` over discover (no merged count, no
  TestTimed exclusion, bash-only); fork-based multiprocessing in one
  interpreter (shared module state); per-class sharding (kept as the next
  lever if R6 fails).

### (b) The documents rule in `close`

Hooks into one branch only: `elif not here:` of `two_facts`
(state.py:3990-3992), "no whole-suite run on this tree at all". It calls
`documents_cover(root, state, policy, tree)`; all five must hold:

- **D1.** Both switches on: `policy["documents"]["globs"]` non-empty and
  `read_commands(root)["doc_tests"]` non-empty and not `none`. Otherwise the
  rule is unavailable and today's refusal text stands.
- **D2.** G = the last run with `full_suite(r)` (state.py:3632), an exit and a
  tree. G is green and no full-suite run on G's tree is red under any runtime
  (stricter than R19 on purpose: the R19 block is not touched, C3).
- **D3.** `diff_files(root, G.tree, tree)` is non-empty and not None. A
  rename shows as D+A (sensors.py:167-178), so `.py → .md` fails D4.
- **D4.** Every path is a document: matches `documents.globs`, matches
  neither `documents.except` nor the hard floor `NEVER_DOCUMENTS =
  (".ai/policies/**",)`, and matches neither `coverage.code_globs` nor
  `test_globs`. Matching through `weight.match`.
- **D5.** S = the last `--scope step` run, not `expected_fail`, on this tree,
  with `n > G.n`, whose files contain every `doc_tests` entry; S is green.

When D1–D4 hold and D5 fails, the refusal is actionable: `only documents
changed since run G (k files): 'verify --scope step --files "<doc_tests>"'`.
Recorded: `facts.documents = {since_run, since_tree, run, paths[≤20], tests}`
and the "why" text in task.md.

Untouched: the no-tree, no-runs and "red on this tree" branches, fact (b),
e2e on this tree (state.py:4054), `review --closes` (still needs a full
suite, 3963-3967), the suite budget.

Rejected: accepting any scoped run (a `.md` edit can turn the suite red —
`tests/test_memory_risks.py:24-29` re-renders known-risks.md byte for byte);
grepping test files for the document's basename (hits harness files, misses
tree walkers like `test_rename.py:44`); a new `--scope docs`; extending the
rule to e2e (`test_end_to_end.py` reads repo docs).

### (c) Behaviour 0 in `weight`

Location: `weigh(root, files, declared, goal, policy)` in state.py (called at
:1020 and :3481). `weight.py` is at its 300-line cap (`test_weight.py:374`),
so the rule lives in state.py, as the precedent at :3219-3222 does.

Predicate P: at least one concrete file; every file is a document (D4) or a
test (`test_globs`); at least one is a document. When P holds: `compute` runs
on a policy copy with `behaviour.keywords = []` (file text no longer counts,
so a README containing "workflow" does not score); behaviour, domain and
novelty still in `unknown` become 0 with evidence "documents only" (behaviour
1 if the goal has a keyword); the mode is recomputed with `mode_for`
(:3107-3121); `weight.documents_only.zeroed` records what each axis would
have had. Hints and `--declare` still apply inside `compute`.

Re-score: `start --amend` does not re-weigh (:3574-3592) and `rescore_weight`
raises only reversibility and domain (:3268); `rescore_v7` therefore gains:
if `documents_only` is set and the diff has a path outside P, restore the
zeroed axes upward, emit `weight_raised` "a non-document changed (<path>)",
raise the mode.

The "this repository:" examples in weight.json are read by no code (only
rr-setup/SKILL.md:96 mentions them): they guide the session; the `documents`
table is the deterministic part.

Rejected: negating `code_globs` (zeroes YAML, Twig, XML and un-calibrates
`test_argocd_dev_manifest`, `test_weight.py:115-119`); implementing in
weight.py (the cap is a spec number); examples only (Q4 = A: today's 30/31).

### (d) `tests/test_ai_task_state.py` fixture (own task 1F)

`git init` is not the main cost: 492 `state.py` subprocess call sites against
174 tests, `Base.setUp` only builds `Project()` (tests/test_ai_task_state.py:59-62).
So: measure first (20× `Project()`, 20× `state.py status`, script vs a
cached-bytecode shim). Apply a shim in `Project.run` (:77-91) if it saves
≥ 30 % per call: `python3 -I -c "import sys; sys.argv[0]=STATE;
sys.path.insert(0, D); import state; state.main()"`, only when `state_py ==
STATE`; one test keeps the script entry. Then a template repo per
`(name, files)` key, built once per module, `shutil.copytree` per test.

Rejected: in-process `main()` (`RUNTIME` is a module global, :164; env,
isatty and stdout differ); one project per class (tests mutate state).

## Interfaces

**`tests/run_suite.py`**

```
python3 -I tests/run_suite.py [FILE…] [--start DIR=tests] [--pattern GLOB=test_*.py]
                              [--jobs N=cpu_count] [--timeout S=600] [--serial ID]… [--collect]
```

Default serial id `test_guard_characterization.TestTimed`; an id matches
`id == ID` or `id.startswith(ID + ".")`. Exit 0 green; 1 any red, timeout,
crash, missing or garbled result, interrupted; 2 usage (unknown or non-test
file including a literal `{files}`, no test files, a serial id matching
nothing, `--jobs` < 1). Environment passed through unchanged. Internal
`--child FILE --result PATH [--exclude ID]… [--only ID]…`.

```
run_suite: 56 files, 32 jobs, serial after: test_guard_characterization.TestTimed
ok    test_ai_task_state.py   174 tests  61.0s
FAIL  test_weight.py           63 tests   2.1s  failures=1 errors=0
TIME  test_x.py                timed out after 600s
serial ok  test_guard_characterization.TestTimed  1 test  1.9s
==== FAIL test_weight.py (exit 1) ==== … ==== end test_weight.py ====
----------------------------------------------------------------------
Ran 921 tests in 97.3s

FAILED (failures=1, errors=1)
```

**`.ai/policies/testing.md`** (human, after close, gate G1)

```
verify_command:      python3 -I tests/run_suite.py
step_test_command:   python3 -I tests/run_suite.py {files}
doc_tests:           tests/test_memory_risks.py tests/test_rename.py tests/test_no_size_tokens.py tests/test_instruction_budget.py tests/test_skills_surface.py tests/test_shared_prompts_model_free.py tests/test_project_update.py tests/test_shared_tree.py
```

Plus: `runtime:` becomes "~1.5 min parallel"; under "Reading a failure": "A
review's MEDIUM and LOW findings are recorded with `state.py memory risk
add`, not fixed in the task; only a BLOCKER, a HIGH or a regression buys an
`--after-fix` run."; under "Three scopes": the fourth moment, "after a green
suite, a documents-only edit runs `doc_tests` (step scope), not the suite".
`sensors.TESTING_FIELDS` (sensors.py:204) gains `doc_tests`. The `doc_tests`
list is a proposal; row 2 confirms it by grepping tests for repo-path reads
and tree walks.

**`.ai/policies/weight.json`** (human, after close, gate G2)

```json
"documents": {"globs": ["**/*.md", "docs/**/*.json", ".ai/**/*.json"],
              "except": ["skills/**", "hooks/**", "agents/**", "instructions/**", "codex/**", "ai/**"]}
```

Appended to `examples.light`: "this repository: a change whose files are all
documents (weight.json `documents`) or all tests — none of hooks/, skills/,
state.py; it measures behaviour, domain, novelty 0; deleting, skipping or
loosening a test, or re-recording the guard golden, is not one: declare
behaviour=1".

The hard floor in state.py is `.ai/policies/**` and `.ai/rules/**`. `ai/**` (the
plugin's shared tree, read by every user project and hash-pinned by
`tests/test_project_update.py`) is in `except` so it never counts as documents
(review H1 of T-2026-10-29-2006).

**state.json**: `facts.documents {since_run, since_tree, run, paths, tests}`;
`weight.documents_only {zeroed: {behaviour, domain, novelty}}`;
`verify.runs[]` unchanged; `weight_raised` events reused.

**Skill and agent text**

- rr-review §4 (:84-93): `pass_with_findings` fixes in-scope HIGHs only;
  MEDIUM/LOW each get `memory risk add` (amend `.ai/project/known-risks.md`
  into the task if missing). §2: the bound goes into the brief.
- rr-build-all §5 (:145): the same.
- rr-ship §1 (:27-42): the documents path and its chain.
- `agents/ai-reviewer.md.tmpl` :50-51 ("Verify by execution…") becomes: read
  the diff; run only the named tests through `step_test_command`; no scripts,
  mutation or timing loops in a scratchpad or temp dir; about 40 tool calls,
  then return FINDINGS/VERDICT and list `not reached (budget): …` under
  EXAMINED AND CLEAN.
- Chains (row 5): `$STATE step-done <id> && $STATE verify --scope all`;
  `$STATE review --verdict pass … && $STATE close` only for `pass`;
  `$STATE verify --scope step --files "<doc_tests>" && $STATE verify --scope e2e && $STATE close`.

## Plan rows (input to `/rr-plan`)

Before the batch, its own light task: **1F** `tests/test_ai_task_state.py`
(R7). Then one `/rr-build-all` task, declared full mode:

| Row | Files | Tests | After |
|---|---|---|---|
| 1 Runner | `tests/run_suite.py`, `tests/test_run_suite.py`, `tests/fixtures/run-suite/**`, `README.md` (:853-859), `CONTRIBUTING.md` (:29-36) | `test_run_suite.py` | – |
| 2 Findings policy + documents close | `skills/rr-review/SKILL.md`, `skills/rr-build-all/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/ai-task/state.py`, `skills/ai-task/sensors.py`, `tests/test_ai_task_state.py`, `tests/test_ai_task_sensors.py`, `.ai/project/known-risks.md` | `test_ai_task_state.py`, `test_ai_task_sensors.py`, `test_ai_status_root.py` | – (characterization first) |
| 3 Reviewer bound | `agents/ai-reviewer.md.tmpl`, `skills/rr-review/SKILL.md` | `test_codex_agent_render.py`, `test_shared_prompts_model_free.py`, `test_skills_surface.py`, `test_instruction_budget.py` | 2 |
| 4 Weight documents rule | `skills/ai-task/state.py`, `tests/test_weight.py`, `tests/test_ai_task_state.py`, `docs/weight.md` (:66-69) | `test_weight.py`, `test_ai_task_state.py` | 2 (characterization first) |
| 5 Chaining | `skills/rr-build/SKILL.md`, `skills/rr-review/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/rr-build-all/SKILL.md` | `test_instruction_budget.py`, `test_skills_surface.py` | 2, 3, 4 |

After close, the human, outside any run: **G1** testing.md lines, then
measure R6; **G2** weight.json.

## Policy conformance

- **C1** production behaviour is the source of truth: both new rules are off
  without the human's key and line; the runner's parity test proves discover
  semantics; nothing else changes behaviour.
- **C2** failing test first: R10 and R14 characterize `close` and `weight`
  before rows 2 and 4 change them; every R3 fail-safe case is a fixture.
- **C3** no refactoring mixed in: 1F is its own task; no state.py block is
  restructured, the documents rule is one new call in one branch.
- **C4** every row names its files; `known-risks.md` is in the task's files.
- **C5** no agent merges, deploys or edits a policy: G1 and G2 are the
  human's, commit only as picked in the dialog.
- **C6** a plugin change is weighed by its effect on user projects: 2b weakens
  a refusal and row 4 lowers modes, both behaviour 2, so the batch task is
  declared full (`start --mode full --by <name>`, STRONG review, gate).
- **Repo CLAUDE.md**: a BLOCKER closes only with a test that pins it (R3);
  weight by effect on user projects (C6 above).
- **testing.md**: no fail-fast anywhere (R3); three scopes kept, with the
  documents exception recorded in G1's text.
- **Guard golden**: nothing under `hooks/` changes; the existing light example
  at weight.json:197 already covers performance work that keeps it identical.
- **ADRs**: none exist.
- **~/.claude/CLAUDE.md** "verify once, to the end": unchanged for code
  diffs; the documents exception is G1's text.

## Flagged concerns

1. **Policies cannot be edited by the agent, including the template copies.**
   The path guard protects `.ai/policies/*.json` always and `.ai/policies/`
   while a task is in flight (hooks/ai-path-guard-defaults.json:31,47,
   hooks/guard/paths.py:43-54), by absolute path, so
   `skills/ai-init/templates/.ai/policies/*` is caught too; rr-build-all:173
   says a policy is frozen during a task. Hence G1 and G2 are the human's,
   after close, and the task's own suite runs use the old serial command once
   more. The task would otherwise close on the runner it built.
2. **The fixture premise is weaker than the report said.** 492 subprocess
   call sites, not `git init`, dominate `test_ai_task_state.py`; "well under
   20 s" probably needs in-process calls, which C3 and `RUNTIME` as a module
   global forbid. 1F reports the measured number; the < 120 s acceptance rests
   on the runner plus 32 cores (inferred ~95–100 s without 1F).
3. **Economics of 2b.** After row 1 a full run costs ~60–100 s, not 300 s, so
   the documents rule saves about a minute per documents-only rerun while still
   weakening a refusal (behaviour 2). Q1 = C stands; the human may re-weigh it
   after row 1 is measured.
4. **`doc_tests` drift.** A doc-reading test left off the list can let a close
   go through red; it surfaces in CI (serial oracle,
   `.github/workflows/tests.yml:31`) or in the next task's full suite.
5. **Contention.** `tests/test_ai_path_guard.py:343-344` has a 100 ms budget
   with no factor; `test_memory_pre_push.py:229` and `test_ere_unit.py:104,119`
   are tight. rr-build-all runs up to 3 implementers whose step runs also use
   the runner: up to 3 × `--jobs` processes. Mitigation: the serial list is
   data, add an id after a flake; consider `--jobs cpu/2` for step runs.
6. **Orphans.** state.py's timeout kills only the shell (sensors.py:285-291);
   the runner's own timeout (600 s < 1800 s) plus `killpg` covers it.
7. **Under-weighting.** Test-only changes, including test weakening and golden
   re-records, are already scored zero by weight.py:169-170,186-188; this
   predates the task and the example text says to declare. Optional: a
   behaviour hint plus a `hot_paths` entry for
   `tests/fixtures/guard-characterization/**`.
8. **Intent gap (the human's).** Behaviour 0 alone does not make a documents
   change light: domain and novelty stay UNKNOWN and score 1 each
   (weight.py:239-240, docs/weight.md:59-62). The design zeroes all three,
   mirroring the tests-only rule. If refused, the light example must tell the
   session to declare them 0 and docs tasks stay guarded more often.
9. **Policy vs policy.** Repo CLAUDE.md, ~/.claude/CLAUDE.md ("verify_command
   once, to the end") and testing.md:32-33 ("three times at most, nothing in
   between") are contradicted for documents-only diffs; G1's text records the
   exception explicitly rather than silently.
10. **Templates and user projects.** Left unchanged in this task: no template
    history rebuild, no weight.md mirror (test_weight.py:360-370; weight.md
    cannot show `documents` without touching weight.py's cap). Both rules stay
    off for user projects. `/rr-setup --update` keeps this repo's policy edits
    (three-way merge keeps ours, update.py:40-44, merge_json:343-359).
    Shipping to users is a follow-up task.
11. **This task's own review** is done by the installed ai-reviewer (user
    scope), not bounded by row 3 until reinstall.
12. **Exit 2 counts as a bite.** `--expect fail` treats runner exit 2 as a
    bite (state.py:3795), as today's exit 5 does. Record in known-risks.
13. **Chain hazard.** `review` exits 0 for every verdict (state.py:3884-3949)
    and close counts `passed_with_findings` as reviewed (:4032); `review &&
    close` is allowed only after `pass`.

## Open questions

- (human) Extend the auto-zero to domain and novelty as designed, or behaviour
  only? — concern 8.
- (human) Confirm the `doc_tests` list after row 2's grep.
- (human) Templates now or as a follow-up? — concern 10.
- (human) Does the 40-call cap also apply in full mode, where the "look for"
  list is unbounded (ai-reviewer.md.tmpl:63-64)?
- (plan) Whether 1F's measured time makes the < 120 s acceptance comfortable
  or whether per-class sharding is needed — concern 2.
