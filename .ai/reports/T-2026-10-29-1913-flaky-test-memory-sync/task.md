# T-2026-10-29-1913-flaky-test-memory-sync — flaky test_memory_sync TestConcurrency: deterministic interleaving, assert the L5 contract (sealed or already, each key sealed once)

bugfix · guarded · started 2026-10-29T19:13:38Z · claude

## Weight

```
scope          2  tests/test_memory_sync.py referenced from 9 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 5 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_memory_sync.py, .ai/project/known-risks.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-5.md, docs/sdlc/intent/faster-task-cycle.questions.md
tests: tests/test_memory_sync.py
amended 2026-10-29T19:21:00Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-5.md — review report via --report - from a file
amended 2026-10-29T19:29:27Z: +docs/sdlc/intent/faster-task-cycle.questions.md — changed by another session (faster-task-cycle questions) during this task; included on the developer's pick so close can measure; not part of this task's commit

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | - | .ai/state/logs/T-2026-10-29-1913-flaky-test-memory-sync/suite-1.log | no |
| 2 | e2e | 0 | 34a694a13 | .ai/state/logs/T-2026-10-29-1913-flaky-test-memory-sync/e2e-2.log | no |
| 3 | suite | 0 | 7e7795cb4 | .ai/state/logs/T-2026-10-29-1913-flaky-test-memory-sync/suite-3.log | no |
| 4 | e2e | 0 | 7e7795cb4 | .ai/state/logs/T-2026-10-29-1913-flaky-test-memory-sync/e2e-4.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 Stale label in the known-risks entry (`.ai/project/known-risks.md`, the entry's `Label` line, ~:752). The Status now states the cause as KNOWN FACT, but the line below still reads "KNOWN FACT (failure, isolated passes), INFERENCE (cause)". "What could go wrong" also still says INFERENCE for the cause. in_scope: yes
  suggested direction: change the Label to "KNOWN FACT (failure, cause, fix)".
- [LOW] L2 The edited test now covers only the fully overlapping interleaving (`tests/test_memory_sync.py:~300-337`). in_scope: yes
  why it matters: the barrier forces `[0,2]`; the staggered `[1,1]` case is no longer seen. Sequential cases pinned at `tests/test_memory_sync.py:50, 90, 106, 121`. Small risk.
  suggested direction: accept, or note it in the test comment.
- [INFO] I1 The 3/3, 5/5 idle and 5/5 loaded figures come from the developer; the reviewer ran the new test 3 times (pass, 0.67 s each).

## EXAMINED AND CLEAN
- Diagnosis right (memory_sync.py :362-390, :413-415); contract L5 (record_lines :466-477, cleanup :538); the original assertion came in 6d277f8 and was stricter than the fix it exercised — a legitimate correction, not an edit to make the test pass.
- Mutation run: removing `already.append(key)` at :415 makes TestConcurrency FAIL (file restored, skills/ clean).
- Interception via mock.patch.object(ms, "crash") works; no hang (Barrier timeout 30, BrokenBarrierError caught into errors); [0, 2] deterministic; scope: test file + known-risks status only.

## VERDICT
verdict: pass_with_findings
scope_assessment: stayed inside the approved plan (test file plus the known-risks entry). No production code was touched.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +2 −2 | Edit |
| docs/sdlc/intent/faster-task-cycle.questions.md | +4 −4 | Edit |
| tests/test_memory_sync.py | +25 −7 | Edit |

+31 −13 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 7e7795cb4 (run 3) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 8 · suite runs: 2 · review passes: 1
