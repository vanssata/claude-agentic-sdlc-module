# Legacy areas

## Shell-to-Python guard port

- **Lives in**: `hooks/guard/` (`git.py` ← `ai-git-guard.sh`, `paths.py` ← `ai-path-guard.sh`, `scope.py` ← `ai-scope-guard.sh`, `common.py` ← `hooks/lib/ai-hook-common.sh`)
- **Why**: performance and testability (redesign 3.5). The `.sh` shims are retired by the installer (`bin/riskrails.js:979-982`).
- **Test coverage**: characterization golden + `test_guard_differential`
- **What must not change**: the golden, byte for byte, unless a declared behaviour 1 re-records it.
- **Label**: KNOWN FACT

Documented behaviour: CLAUDE.md:5 names `hooks/ai-path-guard.sh` and `SH_WORD`/`SH_RE` as retired (deleted in R22, `710a2aa`) and states what holds now: `hooks/guard/paths_bash.py` splits top-level segments only and refuses unread a command over `LONG_CMD` = 4096 characters that names a guarded path or a gate verb.
Observed behaviour: matches; the file and both identifiers are gone.
Evidence: `hooks/guard/paths.py:1`; `paths_bash.py:33,49,70-72`.
Risk: none open; see business-rules.md, "The SH_WORD/SH_RE invariant".

## Old task schema and project shapes

- **Lives in**: `rr_state/task.py:196,354` (schema < 7 → `old_surface_refusal`); `skills/project-update/rr_update/kept.py:115` (`KEPT_UNREADABLE`, exit 6); `rr_update/paths.py:11` (`LAST_MIGRATING_VERSION = "3.1.0"`); `rr_update/weights.py:170` (old weight table split); `skills/rr-status/status.py:114` (pre-schema-7 counters)
- **Test coverage**: `tests/fixtures/regenerate/{fresh,v3.1.0,v3.1.0-edited,dual}` via `test_update_characterization.py:97`, `test_regenerate.py`
- **Safe change shape**: do not touch; the refusal is the contract ("go through npx riskrails@3.1.0 first").

## Legacy memory

- **Lives in**: `skills/ai-task/memory_migrate.py:92,181`, `memory_store.py:224-245` (legacy report dirs), `memory_compact.py:613,867` (`legacy_tier` seal, read by `usage-report.py:659`)
- **Label**: KNOWN FACT

## Old tier names

- **Lives in**: `rr_policy.MODE_TIER`, the `tier_set` journal event ("compat", `rr_state/start.py:212`), `docs/weight.md` (old tiers section)
- **What must not change**: journals of old tasks still carry `tier_set`.

## Legacy env names

- `hooks/cap-large-read.py:24-36` accepts `CLAUDE_READ_MAX_LINES` / `CLAUDE_READ_MAX_BYTES`.

## Code that looks unused

- `agents/superseded/reviewer.md`: still used. The installer compares it to a stale installed copy (`bin/riskrails.js:1170`).
- `hooks/memory-pre-push.py`: not in any `hooks.json` because it is a git pre-push hook, written by `state.py memory enable`.
- `hooks/update_notice.py`: not registered because it is imported by `context-guard.py:743-755`.
- `hooks/project-scaffold.py`: reached via `hooks/project-scaffold.sh:14`.
- `hooks/__pycache__/fable-gate.cpython-314.pyc`, `codex-model-gate.cpython-314.pyc`: no matching source. They are untracked (`git ls-files` lists no `.pyc`), local leftovers only.
- Not done: a function-level dead-code search. Dynamic dispatch hides callers from grep: `set_defaults(func=…)` at `rr_state/cli.py:137`, the command strings in hook JSON, and the regex strings built in `paths_human.py`.
