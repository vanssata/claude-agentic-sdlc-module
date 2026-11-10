# Verification — this project's commands
<!-- Yours. Read by state.py verify and close, setup.py check, update.py hints; /rr-setup --update never rewrites it. -->

verify_command:      python3 -I tests/run_suite.py --serial test_guard_characterization.TestTimed --serial test_dialog_gate.TestGateFastPath
step_test_command:   python3 -I tests/run_suite.py {files}
e2e_command:         AI_E2E=1 python3 -I -m unittest discover -s tests -p test_end_to_end.py
lint_command:        pylint $(git ls-files '*.py')
doc_tests:           tests/test_memory_risks.py tests/test_rename.py tests/test_no_size_tokens.py tests/test_instruction_budget.py tests/test_skills_surface.py tests/test_shared_prompts_model_free.py tests/test_project_update.py tests/test_shared_tree.py
typecheck_command:   none
healthy_output:      unittest prints "Ran N tests" and ends with "OK" (or "OK (skipped=N)")
                     and exit 0. pylint ends with "rated at 10.00/10".
runtime:             the fast suite ~1.5 min parallel (tests/run_suite.py); CI's serial unittest discover ~5 min; the
                     e2e suite ~7 s; pylint ~5 s; any single suite seconds, except the install and
                     adopt suites, which scaffold scratch trees and take tens of seconds.
single_test:         python3 -I -m unittest discover -s tests -p test_<name>.py

## Project specifics

The suites are Python `unittest` modules, `tests/test_*.py`, self-contained: each
scaffolds what it needs into a temporary directory and removes it on exit.
`tests/guard_harness.py` holds the fixture runners for the hook payloads under
`tests/fixtures/`. `tests/` is not a package, so a module is addressed with
`discover -s tests -p test_<name>.py`, never `tests.test_<name>`. Since 3.5 the
install suites are Python on `tests/install_harness.py`, and since 3.3e the runtime-gate
suites are `tests/test_runtime_gate_{fable,codex}.py`; no `.sh` suite is left.

`verify_command` is one `unittest discover` over every `tests/test_*.py`, so a new
suite runs without being listed. `test_end_to_end.py` skips itself without
`AI_E2E`, so `verify_command` excludes it and `e2e_command` is its only run.

**A step names its own suites, by hand, in `allowed_files`-style paths.** There
is no mechanical map from a source file to its tests; the useful ones are:

| Touching | Run |
|---|---|
| `skills/usage-report/**` | `tests/test_usage_report.py`, `tests/test_codex_usage_report.py` |
| `hooks/ai-guard.py`, `hooks/guard/**` | `tests/test_ai_path_guard.py`, `tests/test_ai_scope_guard.py`, `tests/test_ai_git_guard.py`, `tests/test_guard_characterization.py`, `tests/test_guard_differential.py`, `tests/test_ere_unit.py` |
| `skills/ai-task/state.py`, `weight.py` | `tests/test_ai_task_state.py`, `tests/test_ai_status_root.py`, `tests/test_weight.py` |
| `skills/ai-task/sensors.py` | `tests/test_ai_task_sensors.py` |
| `skills/project-update/**`, `skills/rr-setup/**`, `hooks/project-scaffold.*` | `tests/test_project_update.py`, `tests/test_merge_migration.py`, `tests/test_regenerate.py`, `tests/test_no_fallbacks.py`, `tests/test_scaffold_idempotency.py`, `tests/test_scaffold_differential.py`, `tests/test_setup.py` |
| `bin/riskrails.js`, `profiles/**`, `scripts/resolve-profile.py` | `tests/test_install_dry_run.py`, `tests/test_profiles.py`, `tests/test_codex_install.py`, `tests/test_dual_runtime_install.py`, `tests/test_shared_tree.py`, `tests/test_install_routes.py` |
| `hooks/runtime-gate.py`, `hooks/context-guard.py` | `tests/test_runtime_gate.py`, `tests/test_context_guard.py`, `tests/test_runtime_gate_fable.py`, `tests/test_runtime_gate_codex.py` |
| `agents/**`, `codex/**`, `instructions/**`, `skills/*/SKILL.md` | `tests/test_codex_agent_render.py`, `tests/test_shared_prompts_model_free.py`, `tests/test_instruction_budget.py`, `tests/test_skills_surface.py` |

CI runs two workflows on every push and pull request: `.github/workflows/tests.yml`
(the fast suite, then the e2e suite, both through `unittest discover`) and `.github/workflows/pylint.yml`
(`pylint $(git ls-files '*.py')` on Python 3.11, 3.12 and 3.13, with no
`--exit-zero` and no `--fail-under` — a single warning fails it). `.pylintrc` is
the config; the house convention for an unavoidable warning is an inline
`# pylint: disable=<name>` with the reason next to it, not a change to `.pylintrc`.

Required tools: `jq`, `python3`, `git` — the CI workflow checks them first. The
test count quoted in `README.md` under **Tests** is measured, not estimated: the
"Ran N tests" line of `verify_command`.
It changes with almost every task; update it in the same commit.
