# Business rules

The deliberate refusals. Each looks like friction an agent could "improve" away.

## No agent merges, deploys or publishes

- **Rule**: an agent never merges, deploys or runs `npm publish` / `npm version`. It commits or pushes only with the command a human picked in the dialog, run verbatim and once.
- **Enforced in**: `hooks/guard/git.py:46-69,184-247` (PUSH_RE, FORCE, NO_VERIFY, NPM_PUBLISH_RE, COMMIT_PUSH_RE); pick ledger `hooks/guard/dialog.py:40,538-541`. If the ledger is unreadable, commit/push is denied (`hooks/ai-guard.py:24-26`, R36.9).
- **Tests**: `tests/test_ai_git_guard.py`, `test_dialog_gate.py`, `test_dialog_contract.py`
- **Label**: KNOWN FACT

## Human-only verbs

- **Rule**: `approve`, `profile set`, the `--by` forms of verify/review/reject, and `start --mode light --by` (when the dialog is off) are a human's. An agent may run one only when it is the next live pick.
- **Enforced in**: `hooks/guard/paths_human.py:27-54`; state side `skills/ai-task/rr_state/dialog.py:30,69,84` (human_route, the isatty check); `gate_cmd.py:36`. A hand-filled `[Answer]: A` does not authorize the gate (`rr_state/gate.py:26-40`).
- **Exceptions**: `AI_UNATTENDED` set (see Risk in architecture.md about its five copies).
- **Tests**: `tests/test_ai_path_guard.py`, `test_dialog_consent.py`
- **Label**: KNOWN FACT

## Destructive update confirmations are the human's

- **Rule**: `update.py --confirm-delete` / `--confirm-cleanup` are refused from an agent, in any argparse prefix form.
- **Enforced in**: `hooks/guard/paths_human.py:13-21,68-83`; `skills/project-update/rr_update/gate.py:19-45` → `CONFIRM_REFUSED` exit 5 (`rr_update/paths.py:13`)
- **Tests**: `tests/test_ai_path_guard.py:388`, `tests/test_project_update.py`
- **Label**: KNOWN FACT

## Long commands are denied unread

- **Rule**: a Bash command over 4096 characters that names a trigger (approve, `--by`, `--confirm-*`, `state.py`, `update.py`) or a guarded path is denied without parsing.
- **Enforced in**: `hooks/guard/paths_bash.py:33,49-51`
- **Tests**: `tests/test_ai_path_guard.py:225` (timed), `:405,413`
- **Label**: KNOWN FACT

Documented behaviour: the user memory note says "5000+ char".
Observed behaviour: 4096.
Evidence: `paths_bash.py:33`.
Risk: commands between 4097 and 5000 chars are refused unexpectedly.

## Protected paths

- **Rule**: `.ai/policies/` (including `weight.project.json`), the guards' own configuration and the decision/consent files are not agent-writable.
- **Enforced in**: `hooks/guard/paths*.py` with `.ai/policies/path-guard.json`; `dialog-gate.py` run from a shell is denied (`paths_bash.py:52`, DIALOG_GATE_RE `paths_human.py:60`)
- **Tests**: `tests/test_ai_path_guard.py`
- **Label**: KNOWN FACT

## Scope

- **Rule**: while a task is in flight, an edit outside its step's files is refused (`SCOPE_CHANGE_REQUIRED`); scope grows only through `start --amend`.
- **Enforced in**: `hooks/guard/scope.py:178,329`
- **Tests**: `tests/test_ai_scope_guard.py` (5 tests), the golden
- **Label**: KNOWN FACT

## Budgets

- **Rule**: whole-suite verify runs per task are capped (`tests.max_suite_runs`; code fallback 2, this project 5, batch 12). Review rounds past `review_rounds_max` exit 6 (`REVIEW_BUDGET`) and the next pass is the human's.
- **Enforced in**: `rr_state/policy.py:117-122`, `verify.py:171`; `review.py:84-105`
- **Tests**: `tests/test_weight.py`
- **Label**: KNOWN FACT
- **Note**: `docs/faq.md:52` (two runs) describes the plugin default; the project overlay overrides it.

## Review verdicts must agree with findings

- **Rule**: a verdict that disagrees with the report's VERDICT line is rejected, as is a verdict other than `blockers_open` while an in-scope BLOCKER exists, or `pass` with a HIGH. A reviewer tier below the mode's reviewer is refused.
- **Enforced in**: `rr_state/review.py:49-68,106-109`
- **Tests**: UNKNOWN (no dedicated file found). Grep `blockers_open` in `tests/` to answer it.
- **Label**: KNOWN FACT (code), UNKNOWN (pin)

## Mode lowering needs a human

- **Rule**: starting a task in a lower mode than its weight gives needs a human route (exit 5); `--mode` and `--batch` need `--by`.
- **Enforced in**: `rr_state/start.py:158-170`
- **Label**: KNOWN FACT

## Full mode needs human approval to close

- **Rule**: in full and full_irreversible, close requests the gate and archives only after `approve` from a human. full_irreversible needs `approve --confirm` naming the operations.
- **Enforced in**: `rr_state/close.py:92-118`, `gate_cmd.py:14-53,101`
- **Label**: KNOWN FACT

## The SH_WORD/SH_RE invariant

Documented behaviour: CLAUDE.md:5 says the `SH_WORD`/`SH_RE` regexes of `hooks/ai-path-guard.sh` were deleted in R22 (`710a2aa`). In their place, `hooks/guard/paths_bash.py` splits top-level segments only, and a `sh -c`/`eval` string is not re-parsed. It also refuses unread a command over `LONG_CMD` = 4096 characters that names a guarded path or a gate verb. A new pattern over command text gets its own `timed` case.
Observed behaviour: matches. Splitting is at `paths_bash.py:70-72` (`paths_shell.py` `shell_segments`) and the 4096-character refusal at `:33,49`. The timed cases are at `tests/test_ai_path_guard.py:402-405`: a 40 KB `sh -c` string is allowed, and a 20 KB `sh -c` string that runs `state.py approve` is denied by the 4 KB rule.
Evidence: `paths_bash.py:33,49,70-72`; `tests/test_ai_path_guard.py:398-413`; fixture `tests/fixtures/path-guard/73-bash-sh-c-rm.json`.
Risk: the regexes that BLOCKERs 2, 4 and 5 of T-2026-10-20-003 came from no longer exist. A movers check inside a `sh -c` string is not made (fixture 73), and known-risks.md accepts this (R22, SQ13).
