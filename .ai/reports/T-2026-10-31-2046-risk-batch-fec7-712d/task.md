# T-2026-10-31-2046-risk-batch-fec7-712d — risk batch: fec7, 712d, e3ae, d4d1 fixed with tests; c6a1 accepted; ef4a, dc71 ticketed

bugfix · guarded · started 2026-10-31T20:46:30Z · claude

## Weight

```
scope          2  hooks/runtime-gate.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  plugin internals (declared)
novelty        0  each fix follows a pattern already in the tree (offer_decision refusal, the RecursionError pins 
coverage       0  4 of 4 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: hooks/runtime-gate.py, skills/ai-task/state.py, skills/project-update/adopt.py, skills/project-update/update.py, tests/test_runtime_gate.py, tests/test_ai_task_state.py, tests/test_project_update.py, tests/test_project_adopt.py, CHANGELOG.md
tests: tests/test_runtime_gate.py, tests/test_ai_task_state.py, tests/test_project_update.py, tests/test_project_adopt.py
- s1 · hooks/runtime-gate.py, tests/test_runtime_gate.py · tests/test_runtime_gate.py · done
- s2 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s3 · skills/project-update/adopt.py, skills/project-update/update.py, tests/test_project_update.py, tests/test_project_adopt.py · tests/test_project_update.py, tests/test_project_adopt.py · done
- s4 · CHANGELOG.md · no tests · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 4e522969a | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-1.log | yes |
| 2 | step | 0 | 559d2d67f | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-2.log | no |
| 3 | step | 1 | fc82968f9 | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-3.log | yes |
| 4 | step | 0 | fcc00d6ee | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-4.log | no |
| 5 | step | 0 | fcc00d6ee | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-5.log | no |
| 6 | step | 1 | ccf23a896 | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-6.log | yes |
| 7 | step | 0 | 2bc29d05b | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/step-7.log | no |
| 8 | suite | 0 | aadb74f25 | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/suite-8.log | no |
| 9 | e2e | 0 | aadb74f25 | .ai/state/logs/T-2026-10-31-2046-risk-batch-fec7-712d/e2e-9.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 (resources/failure modes) A twin check that now runs after the DECISION_LIMIT, option and label checks changes only the message, not the exit code (`skills/ai-task/state.py:2722-2751`, was `:3051-3058`)  in_scope: yes
  why it matters: With 4 questions open and a twin, `decision open` answers "DECISION_LIMIT — N questions are open" instead of DUPLICATE. Both exit 6 in `decision_open`, and `offer_decision` prints either one on the file route. The caller does nothing different, so I do not count this as a regression. The one cost is that after the human settles one decision to make room, the next try hits DUPLICATE. That is a second round trip, and the hint for it is correct. The old order checked the twin before the label validation too, so a twin with an invalid label now reports the label error first. That is harmless.
  suggested direction: Accept as is. Optionally put the twin check first in `open_decision`, which restores the old order and keeps the twin message ahead of the limit message.

- [LOW] L2 (resources/failure modes) The d4d1 fix leaves unguarded `json.loads` calls in `update.py` that a too-deep file would still crash (`skills/project-update/update.py:957-958` and `:1784-1787`)  in_scope: yes
  why it matters: Your list of readers is closed. These two sit next to it and catch only `ValueError`.
  - `:957-958`: the policy-leaf path. It is reached only when `ours` equals a historic template, so a deep file cannot get there in practice.
  - `:1784-1787`: `record_migration` reading `migration.json`. A hand-made deep `migration.json` would give a RecursionError traceback in `update --apply`.
  `:799` is not exposed, because `planned` is derived from a `raw` that already parsed at `:787`.
  suggested direction: Record the `:1784` reader in the risk register as a sibling of d4d1, or add `RecursionError` there in a follow-up. It is not a blocker for this batch.

- [INFO] I1 (state-machine, behaviour) `ask`, the budget, `start --mode` and `close` now route a twin to the file route. The old code opened a second, unanswerable decision. The new message ends "before opening it again", which reads oddly on that route (`skills/ai-task/state.py:2747`)  in_scope: yes
  why it matters: Cosmetic only. A stale same-text decision left open from an earlier task now blocks the dialog for a new `ask` until someone runs `decision fallback`. That is the intended trade, and the stderr line names the way out.

## EXAMINED AND CLEAN
- **Your question (1), callers of `open_decision`.** There are four call sites and all of them handle a refusal.
  - `offer_decision` (`:2817`) prints "no dialog — …" and returns None. Its callers are `ask` (`:1664`), mode (`:3644`), the budget (`:4037`), the review (`:4175`) and `offer_approval` (`:4375`). The caller prints the terminal text on None, so a twin is not silently lost.
  - `open_drift` (`:878`) does the same, and it settles stale drifts before opening.
  - `decision_open` (`:3068`) calls `die(why, 6)`.
  No other caller exists.
- **Your question (2), session None.** Every path into `open_decision` first requires `dialog_on(root)` to be truthy. That needs a session id, so own `session` is never None. A twin with `session` None (legacy or hand-edited) is classified "another session". That is correct, because `decision show` cannot list it. Both None cannot occur.
- **Your question (3), readers.** I grepped every `json.load` and `json.loads` in the two files. All the adopt readers on your list are guarded: `load_table:184`, `load_decisions:464`, `_state_line:956`, `read_record:1315`, `task_in_flight:1340`, `find_proposal:1917`. All the update readers are guarded too:
  - `History.__init__:219`
  - `task_journal:1209` and `:1222`
  - `cleanup_update:1250`
  - `run_migrations:790` raises SchemaError "nested too deeply to parse — inspect it by hand".
  The existing guards at `:638`, `:714-729` and `:973-982` are unchanged. The only escapes are the two in L2, which are outside your list. `load_table`/`load_decisions` raise TableError, which their callers already catch.
- **Your question (4), do the tests pin each fix.**
  - fec7: `test_18` covers NaN, "inf", "NaN", Infinity and -Infinity in both fields. It asserts the record is not written when neither field is finite, and that the finite field survives. It would fail on the old `number()`, where `float("nan")` passed through.
  - 712d: `test_a_twin_ask_takes_the_file_route` asserts exit 0, "Q2 asked", no DIALOG_PENDING, the stderr line, and only D1 open. The old code opened D2.
  - e3ae: the other-session test asserts `decision fallback --id D1` is named and "send it" is absent. The same-session branch is also asserted to say "send it". Together they pin both branches of the session comparison.
  - d4d1: both tests probe every reader with 100000 `[` in a subprocess run with `-I` and compare exact return values. The `want` dict includes the TableError, None and SchemaError outcomes, and the update test checks the SchemaError text with a regex. A reader that still escaped would put a "Traceback:" string in `out`, which differs from the `want` dict, so the test fails. You report the new readers fail without the fix (10 failures).
- **`number()` consumers.** The other use at `runtime-gate.py:576` (`window_minutes`) does `or 0`, so None is harmless. The nested `number` at `:1142` is a separate function. `math` is already imported.
- **Guards.** Nothing is loosened. The change only adds refusals (twin on every opener) and drops non-finite readings. No `.ai/` policy or template file is in the diff, so no template-history rebuild is needed.
- **Scope.** No refactoring. The one move (the twin check from `decision_open` into `open_decision`) is the fix itself.
- **Not reached (budget):** I did not run the suite. I inherited the green `verify --scope all` (suite-8.log, e2e-9.log) and the fail-before-fix results from your brief. I did not check a concurrent double-open. The twin check reads `decisions.json` without a lock, exactly as the old check in `decision_open` did, so the race is not new.

## VERDICT
verdict: pass_with_findings
scope_assessment: Inside the plan. Four risks, each with a test that failed first and no guard loosened. The only structural move is the twin check, which is required by 712d/e3ae. The two LOW rows are cosmetic or sit outside the listed readers.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +3 −0 | Edit |
| hooks/runtime-gate.py | +2 −1 | Edit |
| skills/ai-task/state.py | +16 −9 | Edit |
| skills/project-update/adopt.py | +6 −6 | Edit |
| skills/project-update/update.py | +6 −4 | Edit |
| tests/test_ai_task_state.py | +27 −0 | Edit |
| tests/test_project_adopt.py | +59 −0 | Edit |
| tests/test_project_update.py | +63 −0 | Edit |
| tests/test_runtime_gate.py | +24 −0 | Edit |

+206 −20 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on aadb74f25 (run 8) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
