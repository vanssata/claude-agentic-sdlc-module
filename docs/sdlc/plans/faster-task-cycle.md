# Plan: Faster task cycle — parallel suite, fewer reruns, bounded review

Intent: none on file (the spec carries it) · Spec: `docs/sdlc/specs/faster-task-cycle.md`

Decisions this plan rests on, recorded in `docs/sdlc/intent/faster-task-cycle.questions.md`:
Q1=C, Q2=A, Q3=A, Q4=B, Q5=A (spec) and, answered 2026-10-29 at planning: **Q6=A** (a
documents-only change zeroes behaviour, domain and novelty), **Q7=A** (user-project templates
are a follow-up task), **Q8=B** (reviewer cap ~40 tool calls in light and guarded, ~80 in full),
**Q9=A** (the documents rule in `close` ships in this batch). Flagged concerns 1–13 are
accepted as the spec's design records them; 8 and 10 are Q6 and Q7.

Shape: one light task **1F** first (a refactoring, C3), then **one `/rr-build-all` task** of
rows 1–5, declared full (`start --mode full --by <name>`, C6: row 2b weakens a refusal and
row 4 lowers modes). After close, two human rows **G1**, **G2**, then the measurement **M**.

## Spec → plan

| Spec | Plan | Why |
|---|---|---|
| row 2 tests: `test_ai_task_state`, `test_ai_task_sensors`, `test_ai_status_root` | plus `tests/test_skills_surface.py` in row 2's files and tests | R8's proof is a grep there |
| `weigh(root, files, declared, goal, policy)` "in state.py (:1020, :3481)" | does not exist yet (`grep -n "def weigh" state.py` is empty); row 4 introduces it as the wrapper of both `weight.compute` call sites | spec names a function the code lacks |
| the document predicate (D4) in row 2 and predicate P in row 4 | one function `is_document(path, policy)` in state.py, written by row 2, consumed by row 4 | one definition of "document" |
| reviewer cap "about 40 tool calls" | ~40 in light and guarded, ~80 in full | Q8=B |
| tests of rows 2 and 4 against "the repo's weight.json" | every test builds its policy in a temp root, with or without the `documents` key | G2 edits the repo's table after close and must flip no test |

## Files that change

| Path | Change |
|---|---|
| `tests/test_ai_task_state.py` | 1F: `Project` fixture (:59-91) — shim and template repo; rows 2, 4: `TestDocumentsOnly`, `TestRescore` cases |
| `tests/run_suite.py` | new — the parallel runner (Interfaces in the spec) |
| `tests/test_run_suite.py`, `tests/fixtures/run-suite/**` | new — one fixture file per fail-safe case, the parity test |
| `README.md:853-859`, `CONTRIBUTING.md:29-36` | the runner line beside the `unittest discover` oracle; the suite count |
| `skills/ai-task/state.py` | row 2: `is_document`, `NEVER_DOCUMENTS`, `documents_cover`, one call in `two_facts` (:3990), `facts.documents`; row 4: `weigh` wrapper (:1020, :3481), `documents_only` rule, `rescore_v7` (:3595) raise |
| `skills/ai-task/sensors.py:204` | `TESTING_FIELDS` gains `doc_tests` |
| `tests/test_ai_task_sensors.py` | `doc_tests` is read |
| `tests/test_weight.py` | `TestDocumentsOnly` through the `weight` CLI |
| `tests/test_skills_surface.py` | greps for R8, R11, R15 texts |
| `skills/rr-review/SKILL.md` | §2 the bound in the brief; §4 MEDIUM/LOW → register; `review … && close` after `pass` only |
| `skills/rr-build-all/SKILL.md` | §5 :145 the same policy; the chains |
| `skills/rr-build/SKILL.md` | §3/§4 `step-done <id> && verify --scope all` after the last step |
| `skills/rr-ship/SKILL.md` | §1 the documents path and its chain |
| `agents/ai-reviewer.md.tmpl:50-51,63-64` | the bound replaces "Verify by execution…" |
| `docs/weight.md:66-69` | one bullet: the documents-only zero, off without the key |
| `.ai/project/known-risks.md` | concerns 4 and 12 as risks (`memory risk add`) |
| human, after close | `.ai/policies/testing.md` (G1), `.ai/policies/weight.json` (G2) |

Untouched: `hooks/**` (golden byte-identical), `skills/ai-task/weight.py` (300-line cap),
`skills/ai-init/templates/**` (Q7), `.github/workflows/tests.yml` (serial oracle stays).

## Order of work

### 1F — `tests/test_ai_task_state.py` fixture (own light task, before the batch)

Files: `tests/test_ai_task_state.py`. Tests: itself. Workflow: refactoring (C3). Rollback: `git revert`.

- [ ] Measure before: `time python3 -I -m unittest discover -s tests -p test_ai_task_state.py` (174 tests; record the seconds), then 20× `Project()` and 20× `state.py status` in a scratch script, script entry vs a cached-bytecode shim (`python3 -I -c "import sys; sys.argv[0]=STATE; sys.path.insert(0, D); import state; state.main()"`).
- [ ] If the shim saves ≥ 30 % per call: `Project.run` (:77-91) uses it only when `state_py == STATE`; one test keeps the script entry.
- [ ] A template repository per `(name, files)` key, built once per module; `shutil.copytree` per test into `self.root` (same `git init` result: one commit "init").
- [ ] Prove: 174 ids (`python3 -I -c 'import unittest;print(unittest.TestLoader().discover("tests","test_ai_task_state.py").countTestCases())'`); `git diff -U0 tests/test_ai_task_state.py | grep '^-.*assert'` prints nothing; the file time after, in the task report (target ≤ 40 s; the number, not the target, is the deliverable — concern 2).
- [ ] `$STATE verify --scope step --files tests/test_ai_task_state.py`, then `verify --scope all`.

### Row 1 — Runner

Files: `tests/run_suite.py`, `tests/test_run_suite.py`, `tests/fixtures/run-suite/**`, `README.md`, `CONTRIBUTING.md`.
Tests: `tests/test_run_suite.py`.
Consumes: nothing. Produces: the CLI in the spec's Interfaces, exactly; `collect(start, pattern) -> list[str]`, `read_result(path) -> dict | None`, `summarize(results, serial_results) -> (text, exit_code)`.

- [ ] Fixtures `tests/fixtures/run-suite/` (no `__init__.py`, so `discover -s tests` never descends into them — the parity test proves it): `test_green.py` (two passing tests), `test_fail.py`, `test_error.py`, `test_import_error.py` (top-level `import no_such_module_xyz`), `test_crash.py` (`os._exit(3)` inside a test — no result file), `test_hang.py` (`time.sleep(600)`), `test_unexpected_success.py` (`@expectedFailure` that passes), `test_skip.py` (one `skipTest`), `test_serial.py` (`class TestTimed`, `test_alone`: asserts `RUN_SUITE_ALIVE_DIR` holds no `alive-*` file). Every parallel fixture test writes `alive-<pid>` into `RUN_SUITE_ALIVE_DIR` on entry and removes it on exit (R4: the environment passes through unchanged).
- [ ] `tests/test_run_suite.py` — each runs `python3 -I tests/run_suite.py --start tests/fixtures/run-suite <files…>` in a subprocess with a fresh `RUN_SUITE_ALIVE_DIR`: `test_green_exits_0_with_unittest_tail` (`Ran 3 tests in`, last line `OK (skipped=1)` with `test_skip.py`); `test_failure_exits_1` (`FAILED (failures=1)`, `==== FAIL test_fail.py (exit 1) ====` after the per-file lines); `test_error_exits_1`; `test_import_error_exits_1`; `test_crash_without_result_exits_1` (line `FAIL  test_crash.py` names the missing result); `test_unexpected_success_exits_1`; `test_timeout_kills_the_group` (`--timeout 2`, `TIME  test_hang.py … timed out after 2s`, exit 1, no `sleep` child left: `pgrep -f run_suite.py --child` empty); `test_sigterm_kills_children_and_exits_1`; `test_garbled_result_is_red` (`read_result` on a truncated JSON → `None`; a run whose child wrote one exits 1); `test_serial_runs_alone_after_the_parallel_phase` (`--serial test_serial.TestTimed`, line `serial ok  test_serial.TestTimed  1 test`); `test_serial_id_matching_nothing_is_usage` (exit 2); `test_literal_files_placeholder_is_usage` (`{files}` → exit 2); `test_jobs_below_one_is_usage`; `test_no_fail_fast` (fail + green files → both lines printed, `Ran` counts both); `test_collect_matches_discover` (R2: `--collect` on `tests/` equals `TestLoader().discover("tests", "test_*.py")` ids, sorted); `test_default_serial_is_the_timed_class` (the default `--serial` constant is `test_guard_characterization.TestTimed` and `--collect` lists that id); `test_writes_nothing_in_the_repository` (`git status --porcelain` before == after a fixture run).
- [ ] Run: `python3 -I -m unittest discover -s tests -p test_run_suite.py` — expected: every test errors with `No such file` / exit 2.
- [ ] Implement `tests/run_suite.py` per the spec's Design (a) and Interfaces: `ThreadPoolExecutor(--jobs)`, one `python3 -I run_suite.py --child FILE --result TMP/FILE.json [--exclude ID]… [--only ID]…` per file with `start_new_session=True`, stdin `DEVNULL`, stdout+stderr to `TMP/FILE.log`; child = `TestLoader().discover(start, pattern=basename(FILE), top_level_dir=start)` minus excluded ids, `TextTestRunner(failfast=False)`, JSON `{file, tests, failures, errors, skipped, unexpected_successes, expected_failures, seconds, exit}`; longest-first by file size; phase 2 `--only ID` per serial id; `TMP = mkdtemp()`, removed at exit; on timeout `os.killpg(pgid, SIGKILL)`; SIGTERM/SIGINT handler kills every group and exits 1; red sections last, then the unittest tail. A positional FILE may be a path: its basename is the pattern, its directory must be `--start`.
- [ ] Run the module's tests — expected: all pass.
- [ ] Real suite: `python3 -I tests/run_suite.py --collect | wc -l` equals discover's count; `python3 -I tests/run_suite.py` prints `Ran <N> tests in <s>s` then `OK`, exit 0; `git status --porcelain` unchanged. Record the seconds in the task report (the first R6 number).
- [ ] `README.md:853-859`, `CONTRIBUTING.md:29-36`: the runner as the local command, `unittest discover` kept as CI's serial oracle; "Fifty-six suites, <N> tests".
- [ ] `$STATE verify --scope step --files tests/test_run_suite.py`.

### Row 2 — Findings policy (2a) + the documents rule in `close` (2b)

Files: `skills/rr-review/SKILL.md`, `skills/rr-build-all/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/ai-task/state.py`, `skills/ai-task/sensors.py`, `tests/test_ai_task_state.py`, `tests/test_ai_task_sensors.py`, `tests/test_skills_surface.py`, `.ai/project/known-risks.md`.
Tests: `tests/test_ai_task_state.py`, `tests/test_ai_task_sensors.py`, `tests/test_ai_status_root.py`, `tests/test_skills_surface.py`.
Consumes: nothing (1F is closed before the batch). Produces: `is_document(path, policy) -> bool` (D4: matches `policy["documents"]["globs"]`, matches neither `documents.except` nor `NEVER_DOCUMENTS = (".ai/policies/**",)` nor `coverage.code_globs` nor `test_globs`, all through `weight.match`); `documents_cover(root, state, policy, tree) -> (ok: bool, why: str, facts: dict | None)`; `sensors.read_commands(root)["doc_tests"]`.

- [ ] Characterization (R10, C2) in `class TestDocumentsOnly(Base)`: `test_without_the_key_a_document_edit_after_green_still_refuses` — `start`, green `verify --scope all`, write `README.md`, `close` → exit 2, stdout has `the tree changed after the last verify`; `test_without_the_key_red_on_this_tree_refuses` — `the suite is red on this tree`. Run: green today; they stay green after 2b because the scratch project has no `documents` key.
- [ ] `tests/test_ai_task_sensors.py::test_read_commands_reads_doc_tests` (`doc_tests: tests/test_a.py tests/test_b.py` → that string). Run → fails (key absent). Add `"doc_tests"` to `TESTING_FIELDS` (sensors.py:204). Run → passes.
- [ ] Feature tests (R9) in `TestDocumentsOnly`, the scratch project's `weight.json` carrying the spec's `documents` table and `testing.md` carrying `doc_tests: tests/test_docs.py`: D1 `test_globs_without_doc_tests_is_off`, `test_doc_tests_none_is_off` (old text); D2 `test_no_green_full_run_is_off`, `test_red_full_run_on_g_tree_under_another_runtime_refuses`; D4 `test_a_code_file_in_the_diff_refuses`, `test_a_policy_path_refuses_even_when_globs_match` (`.ai/policies/x.md`), `test_except_glob_refuses`, `test_rename_py_to_md_refuses` (D+A); D5 `test_without_a_scoped_run_the_refusal_names_the_command` (exit 2, text `only documents changed since run <G> (<k> files): 'verify --scope step --files "tests/test_docs.py"'`), `test_scoped_run_missing_a_doc_test_refuses`, `test_scoped_run_expected_fail_refuses`, `test_scoped_run_before_g_refuses` (`n ≤ G.n`); green path `test_green_doc_tests_after_g_closes` — `close` goes on, `state.json` has `facts.documents = {since_run, since_tree, run, paths, tests}`, `task.md` names the documents rule; `test_e2e_is_still_owed_on_this_tree` (`verify required`); `test_review_closes_still_needs_a_full_suite` (:3963-3967 unchanged). Run → the D5 green path and refusal texts fail.
- [ ] Implement `is_document`, `NEVER_DOCUMENTS`, `documents_cover` in state.py; `two_facts` (:3990) calls it inside `elif not here:` only; `cmd_close_v7` stores `facts["documents"]` and writes the why line into task.md. Nothing else in `two_facts` moves (R19 block, red branches, fact (b)). Run → passes.
- [ ] 2a text: rr-review §4 (:84-93) — `pass_with_findings` fixes in-scope HIGHs only; each MEDIUM and LOW is one `$STATE memory risk add` (amend `.ai/project/known-risks.md` into the task if missing); only a BLOCKER, a HIGH or a regression buys an `--after-fix` run. rr-build-all §5 (:145) the same. `tests/test_skills_surface.py::test_medium_and_low_findings_go_to_the_register`: both files contain `memory risk add` within the `pass_with_findings` bullet and no longer contain `the MEDIUMs worth it`. Test first (fails), then the text.
- [ ] `doc_tests` confirmation: `grep -ln 'ROOT\b\|os\.walk\|README\|docs/\|\.ai/project' tests/test_*.py` — the files that read repository documents or walk the tree; the list goes into the task report under this step for G1 (spec proposal: `test_memory_risks`, `test_rename`, `test_no_size_tokens`, `test_instruction_budget`, `test_skills_surface`, `test_shared_prompts_model_free`, `test_end_to_end`).
- [ ] Risks: `$STATE memory risk add` for concern 12 (runner exit 2 counts as a bite under `--expect fail`, state.py:3795) and concern 4 (a doc-reading test left off `doc_tests` lets a close through red; CI's serial oracle catches it).
- [ ] `$STATE verify --scope step --files "tests/test_ai_task_state.py tests/test_ai_task_sensors.py tests/test_ai_status_root.py tests/test_skills_surface.py"`.

### Row 3 — Reviewer bound

Files: `agents/ai-reviewer.md.tmpl`, `skills/rr-review/SKILL.md`.
Tests: `tests/test_codex_agent_render.py`, `tests/test_shared_prompts_model_free.py`, `tests/test_skills_surface.py`, `tests/test_instruction_budget.py`.
Consumes: row 2 (shares `skills/rr-review/SKILL.md`, `tests/test_skills_surface.py`).

- [ ] `tests/test_skills_surface.py::test_the_reviewer_is_bounded`: the template contains `step_test_command`, `40 tool calls`, `80`, `not reached (budget)`, and not `Verify by execution where execution is possible`; rr-review §2 names the cap for the mode. Run → fails.
- [ ] `agents/ai-reviewer.md.tmpl:50-51` → read the diff; run only the named tests through `step_test_command`; no scripts, mutation or timing loops in a scratchpad or temp dir; about 40 tool calls in light and guarded, about 80 in full; then FINDINGS and VERDICT, and `not reached (budget): …` under EXAMINED AND CLEAN. `:63-64`: full mode keeps the unbounded "look for" list but the call cap holds. rr-review §2: the cap in the brief.
- [ ] Run the four tests: `python3 -I tests/run_suite.py tests/test_codex_agent_render.py tests/test_shared_prompts_model_free.py tests/test_skills_surface.py tests/test_instruction_budget.py` — expected `OK`. Then `$STATE verify --scope step --files "<the four>"`.

### Row 4 — Weight: the documents rule

Files: `skills/ai-task/state.py`, `tests/test_weight.py`, `tests/test_ai_task_state.py`, `docs/weight.md`.
Tests: `tests/test_weight.py`, `tests/test_ai_task_state.py`.
Consumes: row 2 (`is_document`; shares state.py and `test_ai_task_state.py`). Produces: `weigh(root, files, declared, goal, policy)` replacing both `weight.compute` calls (state.py:1020, :3481); `state["weight"]["documents_only"] = {"zeroed": {behaviour, domain, novelty}}`.

- [ ] Characterization (R14, C2) in `tests/test_weight.py::TestDocumentsOnly(TestCLI)`: a temp root whose `weight.json` is the repo's table **without** `documents` — `weight --files README.md --goal "fix a typo"` scores behaviour, domain, novelty UNKNOWN 1, mode guarded; `test_argocd_dev_manifest` untouched. Green now and after.
- [ ] Feature tests (R12), temp root **with** the spec's `documents` table: `test_documents_only_scores_zero` (`README.md`, `docs/x.md` → behaviour/domain/novelty 0, evidence `documents only`, light when scope ≤ 2, `--json` shows `documents_only.zeroed`); `test_goal_keyword_still_scores_one` (goal "the workflow"); `test_file_text_keyword_does_not_score` (README containing "workflow" → 0); `test_a_hint_still_adds_one` (a `hints` entry on `docs/**`); `test_declare_replaces_zero` (`--declare behaviour=1:"…"`); `test_docs_plus_tests_still_zero`; `test_docs_plus_code_is_unchanged` (a `.py` → UNKNOWN 1); `test_policy_path_is_not_a_document`. Run → fail.
- [ ] Implement `weigh` in state.py: predicate P (at least one concrete file; every file `is_document` or matches `test_globs`; at least one document) → `weight.compute` on a policy copy with `behaviour.keywords = []` for file text (the goal keyword still applies), axes still `unknown` become 0 with "documents only", mode from `mode_for` (:3107), `documents_only.zeroed` recorded; both call sites use it. Run → pass.
- [ ] R13 in `tests/test_ai_task_state.py::TestRescore::test_a_non_document_after_amend_raises_the_zeroed_axes`: `start --files README.md` (policy with the key) → light; `start --amend --files +src/widget.py --why …`; edit it; `verify --scope all` prints `re-score: behaviour 0 → 1 … a non-document changed (src/widget.py)`, journal has `weight_raised`, mode guarded; the same at `close`. Run → fails. `rescore_v7` (:3595): when `documents_only` is set and the diff has a path with `not is_document(path) and not test`, restore each zeroed axis upward, emit, raise the mode. Run → passes.
- [ ] `docs/weight.md:66-69`: one bullet after "Zeros nobody needs to declare" — with a `documents` table, a change whose files are all documents or tests scores behaviour, domain and novelty 0; without the key nothing changes; `--declare` raises.
- [ ] `$STATE verify --scope step --files "tests/test_weight.py tests/test_ai_task_state.py"`.

### Row 5 — Chaining

Files: `skills/rr-build/SKILL.md`, `skills/rr-review/SKILL.md`, `skills/rr-ship/SKILL.md`, `skills/rr-build-all/SKILL.md`.
Tests: `tests/test_instruction_budget.py`, `tests/test_skills_surface.py`.
Consumes: rows 2, 3, 4 (shared skill files; the documents path of row 2).

- [ ] `tests/test_skills_surface.py::test_the_chains_are_named`: rr-build §4 has `step-done <id> && $STATE verify --scope all` (after the last step only); rr-review §4 has `--verdict pass` … `&& $STATE close` and says `pass` only (concern 13); rr-ship §1 has `verify --scope step --files "<doc_tests>" && $STATE verify --scope e2e && $STATE close`; rr-build-all §4/§6 the same. Run → fails.
- [ ] The texts; rr-ship §1 (:27-42) gains the documents row: `2 verify required` with `only documents changed since run …` → that chain.
- [ ] `python3 -I tests/run_suite.py tests/test_instruction_budget.py tests/test_skills_surface.py` → `OK` (rr-build + weight.json + Verification ≤ 400 lines, :68-74). `$STATE verify --scope step --files "tests/test_instruction_budget.py tests/test_skills_surface.py"`.

### Batch end

- [ ] `$STATE verify --scope all` with today's serial `verify_command` (concern 1: the task closes on the old command; ~300 s), then `verify --scope e2e`; review on STRONG (full); `/rr-ship`; the human approves.

### G1 — human, after close: `.ai/policies/testing.md`

`verify_command: python3 -I tests/run_suite.py`; `step_test_command: python3 -I tests/run_suite.py {files}`; `doc_tests:` the list row 2 confirmed; `runtime:` "~1.5 min parallel"; under "Reading a failure" the MEDIUM/LOW sentence; under "Three scopes" the documents moment (spec Interfaces). Commit as the dialog picks.

### G2 — human, after G1: `.ai/policies/weight.json`

The `documents` table and the light example from the spec's Interfaces. No test reads the repo's table for these rules (Spec → plan, last row).

### M — measurement (R6, R16), a documents-only task of its own

`for i in $(seq 10); do /usr/bin/time -f %e python3 -I tests/run_suite.py >/dev/null || echo RED; done; git status --porcelain` — ten greens, each < 120 s, nothing changed. Over the following tasks: `jq .verify.suite_runs .ai/state/logs/*/state.json` — the median against today's 2. Both numbers go into Proof below.

## Risks

| # | What breaks | Where | How we notice | Mitigation |
|---|---|---|---|---|
| P1 **riskiest** | a false green: the runner exits 0 with a lost, crashed or garbled file | row 1 | R3 fixtures, one per case; `test_no_fail_fast`; parity count | pinned before the runner becomes `verify_command` (G1 after M's first look); CI keeps the serial oracle |
| P2 | flakes under 32 parallel processes (concern 5; the `test_memory_sync` race fixed today by T-2026-10-29-1913 is the shape) | after G1 | a red file with no regression behind it | the serial list is data: add the id; `--jobs cpu/2` for step runs; the time budgets stay as they are |
| P3 | 2b lets a red close through | row 2 | `test_scoped_run_missing_a_doc_test_refuses`, the D4 floor | D1–D5 all required; `NEVER_DOCUMENTS`; e2e and `review --closes` untouched; full mode review |
| P4 | `doc_tests` drift (concern 4) | after G1 | CI serial run, next task's full suite | risk recorded in row 2; row 2's grep is the list's source |
| P5 | `review … && close` after a non-pass verdict (concern 13) | row 5 | `test_the_chains_are_named` | the text allows the chain for `pass` only |
| P6 | the task's own runs stay serial (~300 s × ≥ 2) and the three implementers' step runs stay serial | batch | time | accepted (concern 1); no contention during the task because G1 comes after it |
| P7 | G2 flips a test that read the repo's table | after G2 | `test_weight.py` red on a docs-only commit | every row-2/row-4 test builds its policy in a temp root |
| P8 | `start --amend` on a documents-only task hides a code change | row 4 | `TestRescore` R13 | `rescore_v7` restores the axes upward at `verify` and `close` |
| P9 | the 400-line cap (`test_instruction_budget.py:74`) | rows 3, 5 | that test | the texts replace sentences, never add paragraphs |
| P10 | this task's own review is the installed reviewer, unbounded (concern 11) | batch | review time | accepted; reinstall after close |

Riskiest step is row 1; it is already first and nothing consumes it inside the task (G1 does, after M).

## Proof (tests)

| R | Proof |
|---|---|
| R1 | `test_run_suite.py` green/fail/skip tails |
| R2 | `test_collect_matches_discover`; `--collect \| wc -l` on the real suite |
| R3 | one fixture test per case: fail, error, import error, crash, timeout, garbled result, unexpected success; `test_no_fail_fast` |
| R4 | `test_serial_runs_alone_after_the_parallel_phase`, `test_default_serial_is_the_timed_class` |
| R5 | `test_timeout_kills_the_group`, `test_sigterm_kills_children_and_exits_1` |
| R6 | M: ten runs < 120 s, `git status --porcelain` empty — numbers: 2026-10-29, `verify_command` (with its two `--serial`), 32 CPUs: ten greens, 979 tests, 72.96–73.76 s, median 73.44 s; porcelain unchanged. A first attempt without the `--serial` flags found two tests still on the pre-migration layout (fixed in T-2026-10-29-2125) and `TestGateFastPath` over budget when run in parallel |
| R7 | 1F: 174 ids, no `-.*assert` line, seconds before/after in its report |
| R8 | `test_medium_and_low_findings_go_to_the_register` |
| R9 | `TestDocumentsOnly` in `test_ai_task_state.py`, one case per predicate |
| R10 | the two characterization tests, green before and after |
| R11 | `test_the_reviewer_is_bounded`; `test_codex_agent_render.py`, `test_shared_prompts_model_free.py` stay green |
| R12 | `TestDocumentsOnly` in `test_weight.py` via the CLI |
| R13 | `TestRescore::test_a_non_document_after_amend_raises_the_zeroed_axes` |
| R14 | `test_without_the_key…` in `test_weight.py`; `test_argocd_dev_manifest` unchanged |
| R15 | `test_instruction_budget.py:68-74` |
| R16 | M: `suite_runs` median over the following tasks — baseline 2 (38 tasks to T-2026-10-29-2006); after: T-2026-10-29-2125 used 3 (one environment rerun: `TestGateFastPath` 15.1 ms against 15; one after the plan edit, which `close` did not take as documents-only). Open until more tasks close: `jq .verify.suite_runs .ai/state/logs/*/state.json` |

Verification: `verify_command` once to the end, then `e2e_command`; the batch's STRONG review.

## Rollback

`git revert` of the batch commit (and of 1F's, separately). G1 and G2 are two human edits:
restoring the old `testing.md` lines and dropping the `documents` table turns both rules off,
with the code still present and inert (D1 and P both require the key).
