# Review — T-2026-10-25-005 (T4, direct mode)

## Pass 1 — ai-reviewer, STRONG (opus), over `git diff`

### FINDINGS

- [MEDIUM] M1 — the rule *writer* still writes into nested trees; only the take-back is pruned now.
  `skills/project-update/update.py:1033-1051` (`render_instructions.rule_targets`,
  `render_instructions.py:398-401`) vs. take-back `update.py:1053-1061` (pruned `rendered_rules`). in_scope: yes.
  Scenario: submodule at `libs/sub` (`.git` file), rule `.ai/rules/sub.md` with `dirs: [libs/sub]` —
  `--apply` writes `libs/sub/CLAUDE.md`; when the rule later stops naming it, the block is never taken back,
  the dry run is silent and `--check` exits 0. Before the fix writer and take-back were symmetric.
  Shown in memory with the real functions; the on-disk `--apply` round trip was not run (path guard).
  Recorded in `.ai/project/known-risks.md` (open).
- [LOW] L1 — `tests/test-project-adopt.sh:112` ("nothing is detected") passes on the pre-fix tree:
  detection is root-anchored (`adopt.py:221-223`). Only line 113 pins the fix.
- [LOW] L2 — `tests/test-project-adopt.sh:106`: `git worktree add … 2>/dev/null` is unchecked; on failure
  `commit()` `git init`s a plain nested repo and the `.git`-file case goes untested.
- [INFO] I1 — this repository's `update.py . --check` still exits 1 for reasons outside the task
  (`create .ai/policies/weight.{json,md}`, conflicts in `safety.md`, `testing.md`); no worktree path remains.

### Examined and clean

New update assertions fail pre-fix (196/4) and pass post; adopt line 113 fails pre-fix (312/1); the root is
never pruned; a dangling `.git` symlink prunes (safe side); the other walks (`update.py:252,1202,1433`,
`render_instructions.py:366`, `adopt.py:437/1752/1881`) read plugin trees or report dirs; the no-dangling
scan uses `git ls-files` first. Scope: the 5 named files only, no test weakened.

### VERDICT

verdict: pass — M1 is MEDIUM: risk register, not remediation. L1 and L2 ride with M1's task.
