# Adversarial review — T-2026-09-21-001 (WP6 `project-update --adopt`)

Reviewer: ai-reviewer, STRONG tier, effort high. Range `af58bcb..54b40df` (steps 1–9), then the
remediation in `7a193b2`, re-verified by the same reviewer against its own reproductions.

## Round 1 — verdict: blockers_open

| Sev | Finding | Status |
|---|---|---|
| BLOCKER | `--adopt --cleanup` deleted any path named in the committed `adopt.json` (`../x`, absolute, or a tracked non-source); an absolute path was deleted with no copy kept | closed: `safe_rel()` on every record path; cleanup deletes only sources the recompute maps with `cleanup: true`; `remove_confirmed` re-checks |
| HIGH | cleanup deleted a git-ignored binary/>1 MiB source that `original/` had skipped ("git has it") — unrecoverable | closed: cleanup refuses any target `git ls-files` does not track |
| HIGH | a `decisions.json` `copy` destination was unchecked — apply wrote outside the project | closed: `decision_dest_ok()` (I5 allow-list or `docs/sdlc/{intent,specs,plans}/`); otherwise unmapped, exit 4 |
| MEDIUM | a malformed `decisions.json`/record turned the plain dry run, plain `--apply` and `--adopt --check` into a traceback | closed: `state_line` degrades to one `adopt state unreadable (…)` line, exit 1 |
| MEDIUM | a second cleanup reset `cleanup.deleted` — audit trail lost | closed: `deleted` kept, earlier who/when in `cleanup.history` |
| LOW | a partial record's `planned_writes` excuses those paths from the dirty-tree gate | accepted — it only excuses dirt, never chooses what is written or deleted |
| LOW | `original/<file>` is reused on resume, so edits made between crash and resume are not in it | accepted — fails safe; git holds the committed state |
| LOW | in a monorepo subdirectory `git status` paths are repo-relative, so an interrupted apply cannot resume without a commit | accepted — fails closed, not destructively |

## Round 2 (re-verification) — verdict: pass

All five BLOCKER/HIGH/MEDIUM closed on re-run of the reproductions. Two new LOW from the
remediation, both fixed in `7a193b2`: `report.md` credited every deletion to the last run (now
lists every run), and a record entry without `path` raised `KeyError` in `plan_cleanup` (now skipped).

Examined and clean: split-proposal validation (no model text reaches a destination), apply
phasing, cleanup gates, plain `update.py` behaviour for projects without a foreign structure.

Not re-raised by design: an agent can satisfy `human_present()` with `AI_UNATTENDED=1` (plan
Risks, accepted; recorded as `cleanup.unattended: true` and shown by `/ai-status`).
