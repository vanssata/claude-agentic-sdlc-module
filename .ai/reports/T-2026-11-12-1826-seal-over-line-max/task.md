# T-2026-11-12-1826-seal-over-line-max — Fix #74: a task seal never exceeds LINE_MAX_BYTES (changes capped at build), an over-long valid line stays visible to read-back and redact, and the V1 hint names memory redact

bugfix · guarded · started 2026-11-12T18:26:54Z · claude

## Weight

```
scope          2  tests/test_memory_cleanup.py referenced from 7 files
behaviour      1  keyword 'workflow' in docs/sdlc/specs/compact-project-memory.md
reversibility  0  git revert returns everything
domain         0  memory record plumbing; no auth, payment or personal data (declared)
novelty        0  extends the existing truncated marker and the parser precedent of error plus entry (canonical-fo
coverage       1  2 of 3 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_memory_compact.py, tests/test_memory_format.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py, skills/ai-task/memory_compact.py, skills/ai-task/memory_format.py, skills/ai-task/memory_verify.py, docs/sdlc/specs/compact-project-memory.md, docs/sdlc/plans/issue-74-local-record-auto-release.md
tests: tests/test_memory_compact.py, tests/test_memory_format.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py
- s1 · tests/test_memory_compact.py, tests/test_memory_format.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py · tests/test_memory_compact.py, tests/test_memory_format.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py · done
- s2 · skills/ai-task/memory_compact.py, skills/ai-task/memory_format.py, skills/ai-task/memory_verify.py · tests/test_memory_compact.py, tests/test_memory_format.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py · done · after s1
- s3 · docs/sdlc/specs/compact-project-memory.md, docs/sdlc/plans/issue-74-local-record-auto-release.md · no tests · done · after s2

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 60a9cc77e | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/step-1.log | yes |
| 2 | step | 0 | c65975dc9 | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/step-2.log | no |
| 3 | suite | 1 | 043d492cb | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/suite-3.log | no |
| 4 | suite | 1 | 043d492cb | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/suite-4.log | no |
| 5 | suite | 0 | 043d492cb | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/suite-5.log | no |
| 6 | e2e | 0 | 043d492cb | .ai/state/logs/T-2026-11-12-1826-seal-over-line-max/e2e-6.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 `_fit_changes` drops every `changes` row even when cutting cannot make the line fit (skills/ai-task/memory_compact.py:884-900)  in_scope: yes
  What happens: I ran it with `changes` of 10 small rows and a `files` list of 70000 bytes. It returned `changes == []` and set `changes_truncated` and `truncated=[..., "changes"]`, and the line is still over the limit. The first early return only checks "over the limit"; it never checks whether emptying `changes` would get under it.
  Why it matters: the recorded change table is thrown away for nothing, and V1 plus redact will name `files` anyway. The task text calls the zero-row case intended, but here it loses data with no gain.
  Direction: when the line is still over with `changes == []`, leave the seal as it was.

- [LOW] L2 `memory pack` now fails with a misleading message when a period holds an over-long entry (skills/ai-task/memory_cleanup.py:196-209)  in_scope: yes
  What happens: before this change the over-long line was silently left out of the packed file, and the old batches were deleted. Now the entry is kept in the packed data. `parse_package` on the packed data then returns the over-long error, `errors` is non-empty, and pack raises "the pack does not hold the batches' rid set — batches kept". That is safer than before. But `atomic_write` of the target has already happened, so a new target file holding the over-long line can sit beside the batches, with the same rids in both.
  Why it matters: the message is wrong (the rid set does hold), and pack is blocked until redact. No test covers this. Duplicate rids across files appear to be tolerated, since consumers dedupe by rid, and the same stray-file pattern exists for other errors.
  Direction: pack should name the over-long line and run redact first, or check for it before writing.

- [LOW] L3 Test gaps  in_scope: yes
  - No test of the exact-fit boundary or the guard loop, and no non-ASCII or escaped-path rows in the new tests. I ran that case by hand: 3000 rows with `ü`, `日本語`, quotes and `\n` gave 65480 bytes, and 2000 rows of `é`*100 gave 65393. The arithmetic is in bytes everywhere (`canonical` returns UTF-8 bytes, `parse_package` counts `raw` bytes), so the code is correct. It is just not pinned.
  - No test that V1's fix text for a non-over-long error, or for an over-long line that is invalid JSON or an invalid entry, is byte-identical. By construction it is: `fix` only changes when `line in over and what.startswith("line is ")`.
  - The TestRedact test passes through the export step with or without `_fit_changes`. With the old compaction the seal gets the same rid, so `not missing` drops the outbox. With the new compaction the rid differs, so the `already` path drops it. The `already` path (memory_export.py:87) is therefore not pinned on its own. The redact, V1-hint and read-back parts do fail without `parse_package` or `check_packages`. `_fit_changes` is pinned only by `TestSealSize`.

- [INFO] I1 Over-long lines are now fully `json.loads`'d and canonicalised (skills/ai-task/memory_format.py:296-300)  in_scope: no
  What happens: a package line of tens of MB, or a line over 64 KB nested deeper than about 1000 levels, used to be skipped and now reaches `json.loads` and `canonical`. A deep line raises RecursionError, which is not a `ValueError` and is not caught. It can crash the pre-push validator and every `load_packages` caller instead of giving a V1 finding.
  Why it matters: this is the residual the plan already accepts. A short, deeply nested line (under 64 KB) already crashes the same way, so the exposure is only wider by size. It needs a hostile or corrupt package, which is outside the fixtures.

- [INFO] I2 Visible over-long entries and the existing consumers  in_scope: yes
  The extra entries are harmless here. `_over` and `_line` start with `_`, so `strip_private` removes them before `memory_export.py:148` re-renders `current`, `memory_cleanup.py:157/166/194`, `memory_store.py:193/433` and `memory_risks.py:81`. `_over` never reaches a written file. An over-long seal also does not add a V3 or V4 finding. The same-key logic dedupes by rid. In a stuck repository, recompaction now gives a different rid (a truncated seal), so `export` takes the `already` branch at memory_export.py:87 and does not append a second seal. The exact-entry-count V4 check was already satisfied for that seal.

- [INFO] I3 Redacted `changes` is a string  in_scope: yes
  `render_task_md` is fixed (memory_format.py:694) and line 391 tolerates it, because `isinstance(c, dict)` skips every character. I found no other consumer of `seal["changes"]` under skills/ or hooks/. Clean.

## VERDICT
verdict: pass_with_findings

The findings above are all LOW or INFO, so there is no BLOCKER or HIGH. The change keeps every seal valid before it unchanged: the early return is byte-identical, and `truncated` is only re-sorted when `changes` is cut. Header or non-dict lines over the limit never reach `over` or `_over`.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/sdlc/plans/issue-74-local-record-auto-release.md | +197 −0 | New |
| docs/sdlc/specs/compact-project-memory.md | +8 −3 | Edit |
| skills/ai-task/memory_compact.py | +25 −0 | Edit |
| skills/ai-task/memory_format.py | +7 −3 | Edit |
| skills/ai-task/memory_verify.py | +12 −4 | Edit |
| tests/test_memory_cleanup.py | +35 −0 | Edit |
| tests/test_memory_compact.py | +38 −0 | Edit |
| tests/test_memory_format.py | +27 −0 | Edit |
| tests/test_memory_sync.py | +22 −0 | Edit |

+371 −10 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on 043d492cb (run 5) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 3 · review passes: 1
