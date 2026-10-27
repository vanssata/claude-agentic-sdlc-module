# Testing policy

Tests describe behaviour. Coverage percentage is a side effect, not a goal.

## Characterization first

Before changing behaviour that is not covered by a test — which is most legacy
behaviour — write a test that passes against the code **as it is today**. That
test is the definition of what must not break. Only then change the code.

```
characterization test → refactor → verify identical behaviour → feature change
```

Never do those in one step, and never in one commit.

## What to consider, by kind of change

| Change touches | Also test |
|---|---|
| a shared service | the existing callers, not only the new one |
| money, tax, fiscal | rounding, currency, negative and zero amounts, refunds |
| a state machine | every transition that is now reachable, and the ones that must stay unreachable |
| an async consumer | retry, double delivery, out-of-order delivery, poison message |
| an external integration | timeout, 500, malformed response, partial write |
| a write path | idempotency, concurrency, transaction boundaries |
| authorization | the negative case, for every role |
| a public API or event | the old shape still works |

## Three scopes, three moments

A task runs tests three times at most, and each run has its own scope. Nothing
else runs in between.

| When | What runs | Command |
|---|---|---|
| after each implementation step, before `step-done` | **only the tests the plan named for that step** — the files it touched, their direct callers' tests | `step_test_command` |
| once, after the **last** step | the full fast suite — unit and integration, no e2e | `verify_command` |
| once, at the **end of the task**, after the full suite is green | the end-to-end suite | `e2e_command` |

- A step never runs the full suite, and **never** runs e2e. If the plan named
  no test for a step, nothing runs for it.
- A step's tests are scoped by path or filter, not by `--stop-on-failure`: the
  scoped run still goes to the end, and its failures are fixed inside that step.
- The e2e suite runs **once per task**, at the very end, never per step. Skip it
  at T0/T1, and when the change cannot reach a flow the e2e suite covers — say
  which, in one line; silence is not a verdict.
- A failure in a step's own tests is fixed in that step, before `step-done`;
  the batch rule below is for the two end-of-task runs.

## Reading a failure

**Run to the end, then fix as one batch.** The verification command runs with
no fail-fast flag and is never interrupted at the first failure. Collect every
failure, classify each one, fix all the new regressions in a single remediation
step (`state.py remediate`), and run the command once more. One failure never
sends the task back to the start: the plan, the tier and the finished steps
stand. At most two remediation rounds; a third means the human decides.

Classify before fixing. The four answers are:

- **EXISTING TEST FAILURE** — it failed before this change too. Say so, do not
  fix it inside this task.
- **NEW REGRESSION** — this change broke it. Fix the code, not the test.
- **TEST ENVIRONMENT FAILURE** — database, fixtures, network, container. Say what
  is missing.
- **UNKNOWN** — you could not tell. Say what you tried.

**Never edit a test to make it pass when production behaviour changed
unexpectedly.** A test that suddenly disagrees with the code is evidence, and
deleting evidence is the worst available option.

## Verification

Three commands, one per scope. `verify_command` proves the project is healthy;
`step_test_command` proves one step is; `e2e_command` proves the whole flow
still works. Keep each to one command — chain the pieces in a Makefile or
composer script if there are several — and make sure none of them stops at the
first failure (`--stop-on-failure`, `-x`, `--bail`, `failfast` are off).

`verify_command` must **exclude** the e2e suite: it is the fast loop run after
the last step and again after a remediation batch. `e2e_command` runs once, at
the end of the task. A bugfix still shows its new failing test first — that one
test only, through `single_test`.

```
verify_command:      bash tests/run-all.sh
step_test_command:   bash -c 'rc=0; for t in {files}; do case "$t" in *.py) python3 -I -m unittest discover -s tests -p "${t##*/}" ;; *) bash "$t" ;; esac || rc=1; done; exit $rc'
e2e_command:         AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py
lint_command:        pylint $(git ls-files '*.py')
typecheck_command:   none
healthy_output:      run-all.sh ends with "all suites passed" and exit 0; each suite prints
                     "<name>: N passed, 0 failed". pylint ends with "rated at 10.00/10".
                     unittest ends with "OK" (or "OK (skipped=N)") and exit 0.
runtime:             run-all.sh ~4-5 min (the CI job measures 4m21s); test-end-to-end.sh
                     ~7 s; pylint ~5 s; any single suite seconds, except the install and
                     adopt suites, which scaffold scratch trees and take tens of seconds.
single_test:         python3 -I -m unittest discover -s tests -p test_<name>.py
                     (the five install suites and test-shared-tree.sh stay
                     bash tests/test-<name>.sh until 3.5)
```

`step_test_command` may contain `{files}`, which is replaced by the paths the
step names; without it the paths are appended. The placeholder is what lets
`sensors.py` run a step's own tests for the "test must bite" check, so a runner
that only takes a `--filter` gets `bite: unavailable` rather than a wrong answer.

`lint_command` and `typecheck_command` are read by the deterministic sensors,
never by a model. They decide, together with the test run, whether a T2 change
can skip its model review (`risk-tiers.json`, `sensors`). A **missing** line is
`unavailable` and keeps the review; only the literal `none`, written by a human,
says the project has no such tool. `sensors.py detect` proposes the exact line
from the config files it finds, and never runs what it detected.

If the project has no e2e suite, write `e2e_command: none` and say so — an
empty line is read as "not written down yet" and the next task will go looking
for it. Say which group, tag or directory marks the e2e tests and how
`verify_command` excludes them, so a step's scoped run and the fast suite stay
free of them.

## Project specifics

The suites are Python `unittest` modules, `tests/test_*.py`, self-contained: each
scaffolds what it needs into a temporary directory and removes it on exit.
`tests/guard_harness.py` holds the fixture runners for the hook payloads under
`tests/fixtures/`. `tests/` is not a package, so a module is addressed with
`discover -s tests -p test_<name>.py`, never `tests.test_<name>`. Until 3.5 the
install suites (`test-install-dry-run.sh`, `test-profiles.sh`, `test-codex-install.sh`,
`test-dual-runtime-install.sh`, `test-runtime-gate-*.sh`, `test-shared-tree.sh`)
are still bash on `tests/lib.sh`.

`tests/run-all.sh` runs the remaining `.sh` suites from a literal list, then every
`test_*.py` in one `unittest discover`, so a new Python suite runs without being
listed; a new `.sh` suite does not. `test_end_to_end.py` skips itself without
`AI_E2E`, so `verify_command` excludes it and `e2e_command` is its only run.

**A step names its own suites, by hand, in `allowed_files`-style paths.** There
is no mechanical map from a source file to its tests; the useful ones are:

| Touching | Run |
|---|---|
| `skills/usage-report/**` | `tests/test_usage_report.py`, `tests/test_codex_usage_report.py` |
| `hooks/ai-guard.py`, `hooks/guard/**`, `hooks/ai-*-guard.sh` | `tests/test_ai_path_guard.py`, `tests/test_ai_scope_guard.py`, `tests/test_ai_git_guard.py`, `tests/test_guard_characterization.py`, `tests/test_guard_differential.py`, `tests/test_ere_unit.py` |
| `skills/ai-task/state.py`, `weight.py` | `tests/test_ai_task_state.py`, `tests/test_ai_status_root.py`, `tests/test_weight.py` |
| `skills/ai-task/sensors.py` | `tests/test_ai_task_sensors.py` |
| `skills/project-update/**`, `skills/rr-setup/**`, `hooks/project-scaffold.*` | `tests/test_project_update.py`, `tests/test_merge_migration.py`, `tests/test_project_adopt.py`, `tests/test_scaffold_idempotency.py`, `tests/test_scaffold_differential.py`, `tests/test_setup.py` |
| `install.sh`, `profiles/**`, `scripts/resolve-profile.py` | `tests/test-install-dry-run.sh`, `tests/test-profiles.sh`, `tests/test-codex-install.sh`, `tests/test-dual-runtime-install.sh` |
| `hooks/runtime-gate.py`, `hooks/context-guard.py` | `tests/test_runtime_gate.py`, `tests/test_context_guard.py`, `tests/test-runtime-gate-fable.sh`, `tests/test-runtime-gate-codex.sh` |
| `agents/**`, `codex/**`, `instructions/**`, `skills/*/SKILL.md` | `tests/test_codex_agent_render.py`, `tests/test_shared_prompts_model_free.py`, `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` |

CI runs two workflows on every push and pull request: `.github/workflows/test.yml`
(`bash tests/run-all.sh`) and `.github/workflows/pylint.yml`
(`pylint $(git ls-files '*.py')` on Python 3.11, 3.12 and 3.13, with no
`--exit-zero` and no `--fail-under` — a single warning fails it). `.pylintrc` is
the config; the house convention for an unavoidable warning is an inline
`# pylint: disable=<name>` with the reason next to it, not a change to `.pylintrc`.

Required tools: `jq`, `python3`, `git` — `run-all.sh` refuses without them. The
assertion count quoted in `README.md` under **Tests** is measured, not estimated:
`bash tests/run-all.sh | grep -oE "[0-9]+ passed" | awk "{s+=\$1} END {print s}"`.
It changes with almost every task; update it in the same commit.
