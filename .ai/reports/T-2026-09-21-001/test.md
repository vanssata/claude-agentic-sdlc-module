# Verification — T-2026-09-21-001

Verification command (plan, after step 9): `bash tests/run-all.sh` and `pylint $(git ls-files '*.py')`.
No e2e suite exists in this repository (no `.ai/policies/testing.md`, no `e2e_command`).

| Run | Result |
|---|---|
| `bash tests/run-all.sh` after step 9 and after the first remediation batch | 25/26 suites pass; 2126 checks passed. 1 FAIL: `test-context-guard.sh` "no snapshot and no transcript: silent" |
| same case on a clean `git worktree` of `main` | fails identically → pre-existing, not a WP6 regression; spun off as its own task |
| `bash tests/test-project-adopt.sh` after the final remediation (`7a193b2`) | 240 passed, 0 failed |
| `bash tests/test-project-update.sh` | 176 passed, 0 failed |
| `bash tests/test-ai-status-root.sh` | 16 passed, 0 failed |
| `bash tests/test-shared-prompts-model-free.sh` | 13 passed, 0 failed |
| `pylint $(git ls-files '*.py')` | 10.00/10 on local Python 3.14; 3.11–3.13 left to the CI matrix (`.github/workflows/pylint.yml`) |

Not re-run after the two final LOW fixes (adopt.py `plan_cleanup` / `cleanup_report_md` and their
test only): the full `run-all.sh`. The adopt suite and pylint were.
