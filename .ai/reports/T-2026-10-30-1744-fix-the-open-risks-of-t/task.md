# T-2026-10-30-1744-fix-the-open-risks-of-t — fix the open risks of T-2026-10-30-1708 (M1, L1, L2, L3, I2, deep-nested weight.json)

bugfix · guarded · started 2026-10-30T17:44:34Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 241 files
behaviour      1  keyword 'messenger' in skills/rr-setup/SKILL.md
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data; hint wording, docstrings and an update-tool crash path (dec
novelty        0  each fix narrows or rewords an existing hint, docstring or except clause (declared)
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T17:44:34Z — /rr-build-all: open risks of T-2026-10-30-1708 (M1, L1, L2, L3, I2, deep-nested weight.json)

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, skills/rr-setup/SKILL.md, tests/test_release.py, tools/sync-version.py
tests: tests/test_project_update.py, tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_release.py
- s1 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · skills/rr-setup/SKILL.md · tests/test_skills_surface.py, tests/test_instruction_budget.py · done
- s3 · tests/test_release.py, tools/sync-version.py · tests/test_release.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 7bcb6001a | .ai/state/logs/T-2026-10-30-1744-fix-the-open-risks-of-t/suite-1.log | no |
| 2 | e2e | 0 | 7bcb6001a | .ai/state/logs/T-2026-10-30-1744-fix-the-open-risks-of-t/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 The first `except RecursionError` in `three_way` (json.loads of ours/theirs/bases) is not pinned by any test (`skills/project-update/update.py:927`) in_scope: yes — the only deep test nests 3000 levels; json.loads succeeds there and flatten raises, caught by the second try (line 934). Deleting the first clause leaves the suite green. json.loads raises RecursionError at ~150000 levels. Direction: add a ~200000-level case expecting the same "nested too deeply" conflict.
- [LOW] L1 The RecursionError added to the "unchanged since it was installed" branch is unreachable and untested (`update.py:913`) in_scope: yes — that branch runs only when ours equals a shipped template version, never deeply nested. Direction: drop it or test it.
- [LOW] L2 Recursion handling does not cover every recursion on the policy-JSON path (`update.py:681-688`, `update.py:629`) in_scope: yes — edit_json (migration 0007) calls copy.deepcopy (RecursionError at 50000 levels, uncaught); edit_json/read_json catch ValueError only; dump_json(merged) at line 940 is outside both try blocks (json.dumps RecursionError at 50000 levels on a non-policy target with empty history). Direction: catch RecursionError in edit_json/dump_json, or record as out of reach.
- [LOW] L3 rr-setup wording does not match what the code prints (`skills/rr-setup/SKILL.md:174-177`, `update.py:1285-1298`) in_scope: yes — an ordinary name prints a single-file command; only unsafe-name and overflow hints print the NUL-safe command that untracks everything. Direction: say the printed command is relayed verbatim and, where it is the xargs form, it untracks all such files.
- [LOW] L4 The new L3 hint can accompany other hints and fires on invalid JSON (`update.py:868-874`) in_scope: yes — invalid weight.json gives JSONDecodeError hint on top of the "not valid JSON" conflict, plus possibly the stale-mirror hint advising a regenerate that would fail. Direction: suppress the stale hint when the render raised, or pin that both do not appear.
- [INFO] I1 The `-r` portability claim holds (GNU, busybox support -r; BSD/macOS accept it as a no-op).
## VERDICT
verdict: pass_with_findings
scope_assessment: stayed inside the approved plan (five files); one unreachable RecursionError clause (L1). Deep-JSON fix covers flatten, merge_json and leaf_changes in three_way, not migrations' edit_json nor dump_json on a non-policy target; the json.loads-depth branch is untested (M1).
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/update.py | +19 −8 | Edit |
| skills/rr-setup/SKILL.md | +4 −3 | Edit |
| tests/test_project_update.py | +58 −3 | Edit |
| tests/test_release.py | +2 −2 | Edit |
| tools/sync-version.py | +1 −1 | Edit |

+84 −17 lines, 5 files

## Verdict

close: closed
facts: (a) green — suite green on 7bcb6001a (run 1) · (b) green — 5 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
