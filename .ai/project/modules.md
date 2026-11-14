# Modules

Mode is what `state.py weight` gives. Hooks and skills changes are weighed by their effect on a user project's decisions (constitution C6, CLAUDE.md "Changes under hooks/ / skills/").

## Guard library

- **Purpose**: allow/deny each tool call. Checks, in order: decision, git, paths, scope.
- **Lives in**: `hooks/ai-guard.py`, `hooks/guard/` (`common.py` payload; `ere.py` POSIX ERE with glibc semantics; `git.py`; `paths.py` + `paths_bash/classify/fs/interp/movers/human.py`; `scope.py`; `dialog.py`; `decision.py`)
- **Owns the data**: none; reads `.ai/policies/path-guard.json`, the consent ledger, the decision file, `state.json` (scope)
- **Tests**: `test_ai_git_guard`, `test_ai_path_guard`, `test_ai_scope_guard` (5 tests, 136 lines), `test_guard_characterization` (golden + `TestTimed`), `test_guard_differential`, `test_guard_layout`, `test_ere_unit`
- **Notes**: the golden `tests/fixtures/guard-characterization/golden.txt` is byte-compared and re-recorded only with `tools/golden-diff.py --record`. Behaviour 0 = golden byte-identical. INFERENCE: the scope guard's dedicated suite is thin (5 tests); the golden may cover more.

## Runtime, dialog and context gates

- **Lives in**: `hooks/runtime-gate.py` (1275 lines: subagent model routing, ask/allow), `hooks/dialog-gate.py` (records picks, re-prompts on Stop), `hooks/context-guard.py` (829 lines: context thresholds, handoff, update notice via `hooks/update_notice.py`)
- **Tests**: `test_runtime_gate{,_codex,_fable}`, `test_dialog_gate` (`TestGateFastPath` runs serially), `test_dialog_consent`, `test_dialog_contract`, `test_context_guard`, `test_update_notice`

## Task state machine

- **Purpose**: the task lifecycle, its budgets and the human gate.
- **Lives in**: `skills/ai-task/state.py` (73-line shim) → `skills/ai-task/rr_state/` (`cli`, `start`, `steps`, `verify`, `review`, `close`, `gate`, `gate_cmd`, `dialog`, `dialog_cmd`, `ledger`, `questions*`, `journal`, `locks`, `policy`, `profile`, `report*`, `handoff`, `runtime`, `labels`, `task`, `fs`)
- **Owns the data**: `.ai/state/*`, `.ai/reports/<task>/`, `.ai/state/logs/<task>/`
- **Tests**: `test_ai_task_state`, `test_state_characterization`, `test_state_layout`, `test_task_id`, `test_ai_status_root`, `test_end_to_end` (`AI_E2E=1`)
- **Notes**: `_v7` suffixes (`cmd_close_v7`, `load_v7`), and `task.load` and `load_v7` both exist. There are two stage fields: `stage` (build/verify/review/ship/done) and `current_stage` (implementation/done). `close` in full mode exits 0 after only *requesting* the gate (`close.py:92-118`): the task is still open at stage `ship`.

## Weight and sensors

- **Lives in**: `skills/ai-task/weight.py`, `weight_overlay.py`, `sensors.py` (measurement only, never writes), `rr_state/policy.py`
- **Tests**: `test_weight`, `test_ai_task_sensors`
- **Notes**: there is a fourth mode, `full_irreversible`, and the `tier_set` event and `MODE_TIER` are old-tier remnants. Docstrings say `weight.json`, but the project file is `weight.project.json`.

## Project memory

- **Lives in**: `skills/ai-task/memory_*.py` (store, format, compact, export, sync, verify, cleanup, migrate, packages, risks, config, hook, io, status); command `rr_state/memory_cmd.py`; git hook `hooks/memory-pre-push.py`
- **Owns the data**: `.ai/memory/`, `.ai/local/memory/`, `.ai/policies/memory.json` (schema 1)
- **Tests**: 11 `test_memory_*`, `test_benchmark_memory`

## Setup and update

- **Lives in**: `skills/rr-setup/setup.py` (846 lines), `scaffold_ai.py`; `skills/ai-init/scaffold-ai.sh`; `hooks/project-scaffold.py`; `skills/project-update/update.py` → `rr_update/` (`apply`, `kept`, `gate`, `weights`, `paths`, `shared`, `cli`), `render_instructions.py`, `history/blobs/`
- **Tests**: `test_setup`, `test_project_update` (`test_history_covers_every_template`), `test_update_*`, `test_scaffold_*`, `test_regenerate`, `test_rename`
- **Notes**: a change to a shipped template or `ai/` must run `tools/build-template-history.py` in the same task.

## Installer

- **Lives in**: `bin/riskrails.js`, `bin/menu.js`, `profiles/*.json`, `scripts/{merge-codex-config,render-codex-agents,resolve-profile}.py`, `settings.common.json`, `settings.gate.json`, `codex/hooks.json`, `.claude-plugin/`, `.codex-plugin/`, `.agents/`
- **Tests**: `test_install_*` (incl. `test_install_routes`: plugin hook files equal the npx registrations, `:335`), `test_dual_runtime_install`, `test_codex_install`, `test_profiles`, `test_profile_detect`, `test_shared_tree`, `test_codex_agent_render`

## Usage report and status

- **Lives in**: `skills/usage-report/usage-report.py` (reads `~/.claude/projects` transcripts, tolerant of bad lines), `skills/rr-status/status.py`
- **Tests**: `test_usage_report`, `test_codex_usage_report`
