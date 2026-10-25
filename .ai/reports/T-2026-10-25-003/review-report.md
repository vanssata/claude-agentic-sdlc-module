# Review report — T-2026-10-25-003 (redesign 1.1–1.4)

## Pass 1 — ai-reviewer, STRONG (opus), bounded (T4 direct mode)

Inputs: `git diff HEAD -M` plus the untracked files, the tests the task names,
`.ai/policies/safety.md`, the guards' `*-defaults.json`, the plan
(`docs/sdlc/plans/claude-agentic-redesign.md` §Phase 1). The deferred leftovers
already in `.ai/project/known-risks.md` were excluded. No ledger or
`sensors.json` existed, so nothing was inherited.

VERDICT: pass — no BLOCKER, no HIGH. Recorded as `review_status: passed`.

### FINDINGS

- **M1** MEDIUM, in_scope: yes — `install.sh` (the config.toml step). `backup_file`
  ran on every non-empty `config.toml` before `merge-codex-config.py --no-backup`;
  HEAD's script wrote `config.toml.bak` only when the merge changed something. A
  second Codex install on the same day replaced `backups/<date>/config.toml` with
  installer output and lost the user's original model and `[agents]` values; the
  summary line "backups/<date>/config.toml holds the old one" became false.
  Reproduced by the reviewer on both trees.
- **L1** LOW, in_scope: yes — `/ai-status` promises that `/status` does not keep:
  template `risk-tiers.md:2` (a stale mirror hash "reported by /ai-status"), `:42`
  and `ai/policies/model-routing.md:22,106` ("shows all four" tiers),
  `skills/project-update/SKILL.md:185`, `skills/project-update/update.py:856,1571,1580`
  comments. A stale mirror is no longer reported anywhere.
- **L2** LOW, in_scope: yes — `sweep_bak` did not look in `bin/`, so a
  `bin/claude-1m.bak` from an older Max install survived.
- **L3** LOW, in_scope: yes — `status.py` printed the goal, the first risk and
  the event detail raw; a multi-line value broke the twenty-line bound (R31).
- **L4** LOW, in_scope: yes — `skills/ai-task/sensors.py:1304` still appends "the
  diff re-scores to T<n>" for every T4+ task; it only duplicates "tier T<n> is
  above T3" and records a re-score that no longer happens.
- **L5** LOW, in_scope: yes — neither dry run announces the retire/sweep moves
  into `backups/<date>/`.
- **I1** INFO, in_scope: no (moved to yes by the manager, as a regression of the
  new helper) — `backup_file` used `cp -r`, which saves a symlinked `CLAUDE.md`,
  `settings.json`, `AGENTS.md` or `config.toml` as a link to the file that is then
  rewritten; HEAD's plain `cp` saved the content.
- **I2** INFO — with the template cap at 2 and no `--by` override until 2.2a, an
  `--env-retry` or a findings-closing run can need a third suite run that exits
  6. The spec's interim (R20), not a defect.
- **I3** INFO — `/status` ships before gate G1/OQ9 (a possible collision with a
  built-in `/status`); `/ai-status` works either way. Plan sequencing.

Examined and clean (reviewer): `set -euo pipefail` paths in the new helpers;
ordering of sweep → retire → settings/hooks.json merge → shim retire; Codex
re-trust reminder and `detect_runtime`; no live `DIFF_BUDGET_EXCEEDED` or tier
raise left; hint de-duplication (bites: removing it fails the sensors suite);
`status.py` against the real state shape and `find_ai_root`; the retargeted
gate suites lose only the shim-only asserts; the cap case and R4 phase 1 fail on
the pre-change tree.

### Disposition

| Finding | Action | Where |
|---|---|---|
| M1 | fixed in R2 — the pre-merge copy is backed up only when the merge changed the file | `install.sh` (config.toml step), test in `tests/test-codex-install.sh` ("a second install the same day keeps the original in the backup") |
| I1 | fixed in R2 — `cp -L` for a file, `cp -r` for a directory | `install.sh` `backup_file`, test "a symlinked AGENTS.md is backed up as its content" |
| L2 | fixed in R2 — `bin/*.bak` swept | `install.sh` `sweep_bak`, test "bin/claude-1m.bak is swept too" |
| L3 | fixed in R2 — every free-text value collapsed to one line | `skills/status/status.py` `one_line`, test "every line starts with its key" |
| L1, L4, L5, I2, I3 | deferred | `.ai/project/known-risks.md`, last entry |

Verification after R2: `state.py test-run --scope all` — suite run 3 green
(`tests-suite-3.log`, every suite 0 failed), e2e run 2 green (`tests-e2e-2.log`).
No re-review: the verdict was `pass`, and no BLOCKER was fixed.
