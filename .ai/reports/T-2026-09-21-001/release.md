# Release report — T-2026-09-21-001

**WP6: `project-update --adopt`** — detect, migrate/coexist and clean up foreign AI-tool
structures (Spec Kit, Kiro, Cursor, Copilot, AI-DLC, Gemini/Junie, large instruction files).

Tier **T3**. Repo `claude-native/claude-agentic`, branch `feat/wp6-adopt`, range
`af58bcb..7a193b2` (10 commits, `e81dad6`..`7a193b2`). Workflow: `feature`.

## Summary

No open BLOCKER or HIGH. All 5 BLOCKER/HIGH/MEDIUM findings from adversarial review round 1
were closed and re-verified in round 2 (verdict: pass). One pre-existing test failure exists
on `main`, unrelated to this change (`test-context-guard.sh`, see Tests). One accepted residual
risk carries forward from the plan and review: `AI_UNATTENDED=1` can satisfy `human_present()`
for an agent, mitigated by audit (`cleanup.unattended: true`, `/ai-status` line) rather than
prevented (see Residual risk below).

## What changed

New CLI surface on `skills/project-update/update.py` / new `skills/project-update/adopt.py`:
`--adopt [--mode migrate|coexist] [--tool <name>] [--split-request] [--split] [--diff] [--apply]
[--check] [--cleanup]`. New exit codes: **4** (`unmapped`/check failure/no proposal or fallback/
proposal validation failure), **5** (`ADOPT_REFUSED` — the human gate, and the five R5 refusal
cases). WP1's existing `--confirm-delete` path now shares the same human gate
(`human_present()`), added in step 2 — this is a behaviour change to existing WP1 code, not new
surface, and existing tests were updated (`AI_UNATTENDED=1` inline, not exported, on the two
existing confirmed-deletion calls in `tests/test-project-update.sh:435,482`) so they keep
passing headless. `--check --budget` is a new flag combination on plain (non-adopt) `--check`.

Per commit:

- `e81dad6` step 1 — 8 fixtures (`tests/fixtures/adopt/{speckit,kiro,cursor,copilot,aidlc,
  junie-gemini,large-claude-md,large-agents-md}/`) verified against real tool formats, each with
  a `README.md` naming its format assumption and source; `adopt-map.json`.
- `ab1d591` step 2 — `human_present()`/`clean_tree()` in `adopt.py`; `--confirm-delete` human
  gate, exit 5.
- `44d63ed` step 3 — `--check --budget`; `DEFAULT_BUDGETS` fallback in `render_instructions.py`
  for an installed plugin without `~/.claude/instructions/runtimes.json`.
- `62e85c4` step 4 — `adopt.py` core: detection table, dry-run plan, report lines.
- `897e473` step 5 — no-line-lost / no-dangling-reference checks, router rows in
  `.ai/AGENTS.md`, `--adopt --check`.
- `a22eb5f` step 6 — `--adopt --apply`: R5 refusal gates, bounded `original/` (1 MiB/file cap),
  phased resumable writes, the adopt record, D5 hint on the plain dry run.
- `ef57e40` step 7 — instruction-file split: split-request, proposal validation (R9), fallback
  path, `--diff`, no-line-added check.
- `ce41a72` step 8 — `--adopt --cleanup`: record/sha/task-in-flight/clean-tree gates, checks
  recomputed before deletion, human-confirmed removal only.
- `54b40df` step 9 — SKILL.md §8 "Adopting a foreign structure", `/ai-status` `--adopt --check`
  second line, README paragraph, `test-project-adopt.sh` registered in `tests/run-all.sh`.
- `7a193b2` review remediation — `safe_rel()` applied to every record path; cleanup deletes only
  tracked, re-found sources; `decisions.json` copy destinations checked against an allow-list;
  `state_line` degrades instead of raising on a malformed record; cleanup keeps prior deletions
  in `cleanup.history` instead of overwriting them.

`git diff --stat af58bcb..HEAD`: 84 files changed, 3506 insertions(+), 24 deletions(-) — the
bulk is the 8 new fixture trees and the new `tests/test-project-adopt.sh` (725 lines); code
changes are `adopt.py` (new), `update.py` (edit, flags/gates only per plan), plus small edits to
`render_instructions.py`, `SKILL.md` (project-update and ai-status), `README.md`,
`tests/run-all.sh`, `tests/test-ai-status-root.sh`, `tests/test-project-update.sh`.

## Behaviour preserved

Specifically checked, and how:

- **Plain `--check` line read by `/ai-status`**: untouched branch (`--adopt --check` is a
  separate branch taken before it); asserted by the three pre-existing exact-line assertions in
  `tests/test-project-update.sh`, unchanged, still passing.
- **Plain `update.py` dry-run/apply output on a project with no foreign structure**: byte-
  identical — `Plan.add`/`report` gained `tool=None` as a keyword default so `report` only prints
  `[tool]` when set; the `schema-v*` fixtures' exact-line assertions in
  `tests/test-project-update.sh` are unchanged and pass.
- **Hooks and guards**: not touched by any commit in range (verified against the plan's "Files
  that change" table and `git diff --stat`, no path under `hooks/` appears); `.ai/path-guard`
  defaults are not modified by this change (the plan-review BLOCKER 1 about the guard denying
  fixture paths was resolved by moving fixtures to non-matching names, not by editing the guard).
- **No migration, no schema bump, no `.ai/VERSION` change**: no path under
  `skills/project-update/migrations/` or `.ai/VERSION`-handling code appears in the diff.
- **`test-guard-characterization.sh` golden file**: not in the changed-files list; not exercised
  by this task's scope.
- **`.ai/AGENTS.md` plugin-owned three-way merge**: step 6's proof runs the plain dry run on an
  adopted fixture and asserts no `conflict` line, so router rows added by adopt are seen as
  "ours" on the next plain run (per plan Risks and `tests/test-project-adopt.sh`).

## Tests (from `.ai/reports/T-2026-09-21-001/test.md`, verbatim results)

Verification command per plan, run once after step 9: `bash tests/run-all.sh` and
`pylint $(git ls-files '*.py')`. No e2e suite exists in this repository (no
`.ai/policies/testing.md`, no `e2e_command`).

| Run | Result |
|---|---|
| `bash tests/run-all.sh` after step 9 and after the first remediation batch | 25/26 suites pass; 2126 checks passed. 1 FAIL: `test-context-guard.sh` "no snapshot and no transcript: silent" |
| same case on a clean `git worktree` of `main` | fails identically → pre-existing, not a WP6 regression; spun off as its own task |
| `bash tests/test-project-adopt.sh` after the final remediation (`7a193b2`) | 240 passed, 0 failed |
| `bash tests/test-project-update.sh` | 176 passed, 0 failed |
| `bash tests/test-ai-status-root.sh` | 16 passed, 0 failed |
| `bash tests/test-shared-prompts-model-free.sh` | 13 passed, 0 failed |
| `pylint $(git ls-files '*.py')` | 10.00/10 on local Python 3.14; 3.11–3.13 left to the CI matrix (`.github/workflows/pylint.yml`) |

**Not re-run** after the two final LOW fixes (`adopt.py` `plan_cleanup` / `cleanup_report_md`
and their test only): the full `run-all.sh`. The adopt suite and pylint were re-run and pass.
This is stated as-is, not softened: full `run-all.sh` has not been confirmed green against the
exact `HEAD` (`7a193b2`); only the narrower adopt suite and pylint have.

## Reviews (from `.ai/reports/T-2026-09-21-001/`)

**Plan review** (`plan-review.md`, ai-reviewer opus, T3) — verdict **REJECT, revise plan text**:
2 BLOCKER (path-guard fixture-name collisions; `--confirm-delete` breaks headless under step 2's
new gate), 6 HIGH, 9 MEDIUM, several LOW. All were revised into the plan before implementation
began (plan text states "Every flagged concern (1–13) and OQ1–OQ11 were accepted as recommended
on 2026-09-22").

**Plan re-review** (`plan-rereview.md`, scoped, opus) — verdict **approve-with-changes**: new
HIGH A (Gemini/Junie scaffolds falsely detected as foreign), MEDIUM B (resume allow-list too
narrow; `rules_update` phase), MEDIUM C (path under two tools' roots), plus several LOW, folded
into the plan before step 1 began.

**Adversarial code review** (`review.md`, ai-reviewer STRONG/opus high, range
`af58bcb..54b40df` then remediation `7a193b2`):

- Round 1 — verdict **blockers_open**:
  - BLOCKER: `--adopt --cleanup` deleted any path named in the committed `adopt.json`,
    including `../x`, absolute paths, or a tracked non-source, with an absolute path deleted
    with no copy kept — **closed**: `safe_rel()` on every record path; cleanup deletes only
    sources the recompute maps with `cleanup: true`.
  - HIGH: cleanup deleted a git-ignored binary or >1 MiB source that `original/` had skipped —
    unrecoverable — **closed**: cleanup now refuses any target `git ls-files` does not track.
  - HIGH: a `decisions.json` `copy` destination was unchecked, allowing apply to write outside
    the project — **closed**: `decision_dest_ok()` allow-list, otherwise exit 4.
  - MEDIUM: a malformed `decisions.json`/record turned dry run, apply and `--adopt --check` into
    a traceback — **closed**: `state_line` degrades to one line, exit 1.
  - MEDIUM: a second cleanup reset `cleanup.deleted`, losing audit trail — **closed**:
    `cleanup.history` keeps prior entries.
  - LOW (accepted, not fixed): partial record's `planned_writes` excuses those paths from the
    dirty-tree gate — only excuses dirt, never chooses what is written/deleted.
  - LOW (accepted): `original/<file>` reused on resume, so edits made between crash and resume
    are not captured in it — fails safe, git holds committed state.
  - LOW (accepted): in a monorepo subdirectory, `git status` paths are repo-relative, so an
    interrupted apply cannot resume without a commit first — fails closed, not destructively.
- Round 2 (re-verification) — verdict **pass**: all five BLOCKER/HIGH/MEDIUM closed on re-run of
  the reproductions. Two new LOW found in the remediation itself, both fixed in `7a193b2`:
  `report.md` had credited every deletion to the last run (now lists every run); a record entry
  without `path` raised `KeyError` in `plan_cleanup` (now skipped).
- Not re-raised by design: an agent can satisfy `human_present()` with `AI_UNATTENDED=1` — plan
  Risks accepted this; recorded as `cleanup.unattended: true` and shown by `/ai-status`.

No `ai-security` review ran — per plan (T3, no auth/payments/customer data, no schema step).

## Database / API changes

None. New CLI flags on an internal plugin skill (`project-update`) only. No schema, no
migration, no `.ai/VERSION` change, no network-facing API.

## Monitoring

None added. Visibility is `/ai-status`'s existing second-line mechanism: step 7 now also prints
the `--adopt --check` result and `(deleted unattended)` when `cleanup.unattended: true`.

## Rollback (from the plan, executable)

- **The plugin merge**: revert the merge commit of `feat/wp6-adopt`. `adopt.py` and
  `adopt-map.json` are new files; `update.py` edits are additive flags plus the
  `--confirm-delete` gate, so a revert restores WP1's behaviour exactly. No migration, no schema
  bump, no `.ai/VERSION` change — a project already updated by the reverted plugin is
  unaffected.
- **A project that ran `--adopt --apply`**: nothing was committed by the tool. `git checkout --
  . && git clean -fd -e .ai/reports/` restores the tree; `.ai/reports/adopt-<date>/original/`
  holds every moved file with its mode if the tree had already been committed.
- **A project that ran `--cleanup`**: deletion happened only on a clean tree, so `git checkout
  -- <path>` restores each file, and `original/` is a second copy. `adopt.json.cleanup` names
  who confirmed and when.
- **Step 2 alone (the `--confirm-delete` human gate)**: if it blocks a legitimate headless
  deletion, `AI_UNATTENDED=1` is the documented switch — no code revert needed.

"Revert the commit" alone is not sufficient here: rollback of a project that already ran
`--apply` or `--cleanup` requires the `git checkout`/`clean` steps above, not just reverting the
plugin merge, because those commands acted on a separate project's working tree, not this repo.

## Manual checks (a person must verify; no test covers these)

- Run `--adopt` on a real Spec Kit or Cursor project outside this repository's fixtures, to
  confirm real-world layouts still match `adopt-map.json` beyond the 8 verified fixtures.
- Run `--adopt --cleanup` yourself in a terminal at least once (not headless/`AI_UNATTENDED=1`)
  to confirm the human-gate prompt behaves as expected interactively.
- Confirm the CI pylint matrix passes on Python 3.11, 3.12 and 3.13 (`.github/workflows/
  pylint.yml`) — only 3.14 was checked locally (10.00/10).
- Confirm `bash tests/run-all.sh` is green on `HEAD` (`7a193b2`) exactly — the last full run
  predates the final two LOW fixes in the remediation commit.
- Spot-check `/ai-status` output on a project that has run `--cleanup` with
  `AI_UNATTENDED=1`, to confirm the `(deleted unattended)` line actually renders.

## Residual accepted risk

`AI_UNATTENDED=1` satisfies `human_present()` for an agent — the human gate on
`--confirm-delete` and `--cleanup` can be bypassed by any process, not only a human at a
terminal. This is not prevented, only audited: `adopt.json.cleanup.unattended: true` is written
before the first removal, `report.md` prints `deleted unattended`, and `/ai-status` shows
`(deleted unattended)`. Accepted in the plan's Risks section and left un-reopened by both
adversarial review rounds ("not re-raised by design").

## Human approval required: yes

Approving **the merge of `feat/wp6-adopt` into `main`**. The plan header's dependency on the
spec branch is already satisfied: `spec/wp6-adopt` (commit `1eeb377`) is an ancestor of both
`main` and `HEAD` (checked with `git merge-base --is-ancestor`), so nothing has to be merged
first. No migration and no deploy step exist for this change (plugin skill
code only), so no separate migration or deploy approval applies.
