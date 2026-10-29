# T-2026-10-29-2304-testmigration0009-red-on — TestMigration0009 red on a fresh checkout: fixture copies keep mtime, git stat cache misses the VERSION change

bugfix · guarded · started 2026-10-29T23:04:18Z · claude

## Weight

```
scope          2  tests/test_project_update.py referenced from 27 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  0  git revert returns everything
domain         0  tests only
novelty        0  tests only
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_project_update.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-2.md
tests: tests/test_project_update.py
amended 2026-10-29T23:07:37Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/b302022a-2f89-4b22-b000-5257ad0b21d6/scratchpad/review-2.md — review report file for state.py review --report

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 0386e958e | .ai/state/logs/T-2026-10-29-2304-testmigration0009-red-on/step-1.log | yes |
| 2 | step | 0 | 9238343cf | .ai/state/logs/T-2026-10-29-2304-testmigration0009-red-on/step-2.log | no |
| 3 | suite | 0 | 9238343cf | .ai/state/logs/T-2026-10-29-2304-testmigration0009-red-on/suite-3.log | no |
| 4 | e2e | 0 | 9238343cf | .ai/state/logs/T-2026-10-29-2304-testmigration0009-red-on/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The comment at tests/test_project_update.py:508-510 says "in the same second"; the collision needs an identical timestamp (here 00:37:55.188349164 on v6, v7, v8 — coarse kernel timestamps within one checkout). Fix correct either way; wording: "the same timestamp tick".
- [INFO] I1 to_schema_7 is reached through TestMigration0007.setUp (~431); its schema-7 VERSION has the same timestamp and size as the committed schema-6 one, so copy_function=shutil.copy there is needed, not cosmetic.

## EXAMINED AND CLEAN
Race removal (fresh mtime differs from the committed entry's, git re-hashes); racy-git direction safe; shutil.copy overwrite keeps inode and mode; every other copytree site checked — none copies a same-size file over a committed tree and relies on git (commits only at 111, 185, 443, 519, 1602); no test asserts preserved mtimes; scope is two call sites plus one comment; bite in step-1.log (errors=3 with forced equal mtimes).

## VERDICT
verdict: pass
scope_assessment: inside scope; only the two fixture-copy sites, no production code or assertions changed.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| tests/test_project_update.py | +7 −2 | Edit |

+7 −2 lines, 1 files

## Verdict

close: closed
facts: (a) green — suite green on 9238343cf (run 3) · (b) green — 1 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
