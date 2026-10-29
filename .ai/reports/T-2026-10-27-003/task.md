# T-2026-10-27-003 — Redesign 3.3c: port the update-side shell suites to Python twins with R13 parity and delete the .sh

refactoring · guarded · started 2026-10-27T09:00:18Z · claude

## Weight

```
scope          2  tests/test-merge-migration.sh referenced from 79 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  test files only, no auth/data/payments (declared)
novelty        0  same pattern as 3.3a/3.3b twins (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_merge_migration.py, tests/test-merge-migration.sh, tests/run-all.sh, tests/test_migration_0006.py, tests/test-migration-0006.sh, tests/test_project_update.py, tests/test-project-update.sh, tests/test_project_adopt.py, tests/test-project-adopt.sh, .ai/project/known-risks.md
tests: tests/test_merge_migration.py, tests/test_migration_0006.py, tests/test_project_update.py, tests/test_project_adopt.py, tests/test_suite_parity.py
- s1 · tests/test_merge_migration.py, tests/test-merge-migration.sh, tests/run-all.sh · tests/test_merge_migration.py, tests/test_suite_parity.py · done
- s2 · tests/test_migration_0006.py, tests/test-migration-0006.sh, tests/run-all.sh · tests/test_migration_0006.py, tests/test_suite_parity.py · done
- s3 · tests/test_project_update.py, tests/test-project-update.sh, tests/run-all.sh · tests/test_project_update.py, tests/test_suite_parity.py · done
- s4 · tests/test_project_adopt.py, tests/test-project-adopt.sh, tests/run-all.sh, .ai/project/known-risks.md · tests/test_project_adopt.py, tests/test_suite_parity.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | a77b4121c | .ai/state/logs/T-2026-10-27-003/step-1.log | no |
| 2 | step | 0 | 5fec5152f | .ai/state/logs/T-2026-10-27-003/step-2.log | no |
| 3 | step | 0 | f22a182fa | .ai/state/logs/T-2026-10-27-003/step-3.log | no |
| 4 | step | 0 | 29ccadb24 | .ai/state/logs/T-2026-10-27-003/step-4.log | no |
| 5 | step | 1 | e257c1557 | .ai/state/logs/T-2026-10-27-003/step-5.log | no |
| 6 | step | 0 | ec178fc3e | .ai/state/logs/T-2026-10-27-003/step-6.log | no |
| 7 | step | 0 | 5ab1bc1f8 | .ai/state/logs/T-2026-10-27-003/step-7.log | no |
| 8 | step | 1 | fa12b5a4f | .ai/state/logs/T-2026-10-27-003/step-8.log | no |
| 9 | step | 0 | e72e0708b | .ai/state/logs/T-2026-10-27-003/step-9.log | no |
| 10 | step | 0 | f0b46fabd | .ai/state/logs/T-2026-10-27-003/step-10.log | no |
| 11 | suite | 0 | f0b46fabd | .ai/state/logs/T-2026-10-27-003/suite-11.log | no |
| 12 | e2e | 0 | f0b46fabd | .ai/state/logs/T-2026-10-27-003/e2e-12.log | no |
| 13 | suite | 0 | 6a037a4a6 | .ai/state/logs/T-2026-10-27-003/suite-13.log | no |
| 14 | e2e | 0 | 6a037a4a6 | .ai/state/logs/T-2026-10-27-003/e2e-14.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 tests/test_migration_0006.py:90,117,254,308,638 (also tests/test_project_update.py:507,562,614) — every git subprocess in the 0006 twin (`tracked()`, `git()`/`commit()`, `git init` in `v5_project`, `git show HEAD:<f>`, `git diff --quiet`) runs without the pinned HOME (no `env=`), while test-migration-0006.sh did `export HOME="$W/home"` before any git call. Verified: with a global ~/.gitconfig carrying `core.hooksPath` and a failing pre-commit hook, `HOME=<that> python3 -I tests/test_migration_0006.py TestMigration0006.test_r6_symlinked_router_stops_the_run` dies in v5_project with CalledProcessError on the "schema 5" commit; the original shell suite with the same HOME runs green. Same exposure to core.autocrlf / init.templateDir etc., which can change what "byte-identical original", "exec bit restored" and "git checkout restores the tree" prove (or make them error). The new known-risks.md entry claims "every subprocess runs with a pinned HOME", which is false for these; it also claims CLAUDE_AGENTIC_SHARED is pinned everywhere, but test_merge_migration.py's Env strips it rather than pinning. — in_scope: yes
- [LOW] L1 tests/test_migration_0006.py:72-74 — `per()` can never substitute: `BASENAME + '"$d")'` evaluates to `$(basename ""$d")` (doubled quote), labels contain `$(basename "$d")`. Ran it: text returned unchanged. All four per-router subTests carry the same literal title `$(basename "$d"): …`, so a failing r3 vs r4 subtest is indistinguishable (assertion message is only `out` or nothing). Assertions intact; R13 satisfied by BASENAME. — in_scope: yes
- [LOW] L2 tests/test_project_adopt.py:1038-1039 — "without CLAUDE_AGENTIC_TEST the stop switch is ignored" is vacuous (as the known-risks entry admits). Confirmed by mutation: removing the CLAUDE_AGENTIC_TEST gate in adopt.test_stop_after leaves both the HEAD shell suite and the twin green — the planted record already makes .ai/reports/ non-empty. Faithfully ported but could be made to bite for free (e.g. assert status is not "partial"). — in_scope: yes
- [INFO] I1 tests/fixtures/adopt/README.md:5, tests/fixtures/project-update/schema-v5/README.md:7, tests/fixtures/instructions/rules-project/README.md:3 — fixture READMEs still name the deleted suites as the builders of their fixtures; the new known-risks "Where" list omits them. Wrong-name reader, no wrong verdict. — in_scope: yes
- [INFO] I2 tests/@TMP@/scan/d1..d20 — empty directory tree left in the checkout (created 09:16 during the task) by pre-existing tests/test_ai_path_guard.py:397 (3.3a), which does os.makedirs("%s/scan/d%d" % (tmp, i)) with a literal `@TMP@` as tmp. Not in this diff; git hides empty dirs. — in_scope: no

## VERDICT
verdict: pass_with_findings
scope_assessment: Stayed inside the approved plan — tests and run-all.sh only, plus the known-risks entry; no shipped code, no .ai/policies/ change. Translation is faithful on every point probed; the one substantive regression is M1 (unpinned git env in the 0006 twin and the contradicting known-risks claim).
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +10 −0 | Edit |
| tests/run-all.sh | +2 −3 | Edit |
| tests/test-merge-migration.sh | +0 −89 | Delete |
| tests/test-migration-0006.sh | +0 −458 | Delete |
| tests/test-project-adopt.sh | +0 −1094 | Delete |
| tests/test-project-update.sh | +0 −856 | Delete |
| tests/test_merge_migration.py | +205 −0 | New |
| tests/test_migration_0006.py | +651 −0 | New |
| tests/test_project_adopt.py | +1480 −0 | New |
| tests/test_project_update.py | +1081 −2 | Edit |

+3429 −2502 lines, 10 files

## Verdict

close: closed
facts: (a) green — suite green on 6a037a4a6 (run 13) · (b) green — 10 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
