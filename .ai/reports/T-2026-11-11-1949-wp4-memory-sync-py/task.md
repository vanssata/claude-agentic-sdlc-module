# T-2026-11-11-1949-wp4-memory-sync-py — WP4: memory_sync.py becomes the pre-push validator entry and sibling memory_* modules; behaviour unchanged

refactoring · guarded · started 2026-11-11T19:49:13Z · claude

## Weight

```
scope          1  skills/ai-task/memory_sync.py not measured (over 10 files)
behaviour      1  keyword 'workflow' in CONTRIBUTING.md
reversibility  0  git revert returns everything
domain         0  "moves packages-mode memory code; the validator entry path, shim candidates and exit codes 0/1/3
novelty        0  "the WP1/WP3 pattern on a third file; the sibling-module pattern of memory_store/compact/format"
coverage       1  4 of 14 code files have a test
W 3 → guarded   hints none · unknown scope · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-11-11T19:49:13Z — /rr-build-all docs/sdlc/plans/small-oop-modules-wp4.md

## Plan

files: tests/fixtures/memory/partition.json, tests/test_memory_layout.py, tests/test_memory_sync_characterization.py, tests/fixtures/memory/goldens/sync/**, skills/ai-task/memory_io.py, skills/ai-task/memory_config.py, skills/ai-task/memory_packages.py, skills/ai-task/memory_verify.py, skills/ai-task/memory_hook.py, skills/ai-task/memory_risks.py, skills/ai-task/memory_cleanup.py, skills/ai-task/memory_migrate.py, skills/ai-task/memory_export.py, skills/ai-task/memory_status.py, skills/ai-task/memory_sync.py, skills/ai-task/rr_state/memory_cmd.py, skills/ai-task/rr_state/close.py, skills/rr-setup/setup.py, tests/test_memory_sync.py, tests/test_memory_store.py, tests/test_memory_cleanup.py, tests/test_memory_pre_push.py, tests/test_install_dry_run.py, docs/architecture.md, CONTRIBUTING.md, docs/sdlc/plans/small-oop-modules-wp4.md, tests/fixtures/state/partition.json
tests: tests/test_memory_layout.py, tests/test_memory_sync_characterization.py, tests/test_memory_characterization.py, tests/test_memory_sync.py, tests/test_memory_store.py, tests/test_memory_cleanup.py, tests/test_memory_pre_push.py, tests/test_memory_migration.py, tests/test_memory_risks.py, tests/test_memory_recall.py, tests/test_setup.py, tests/test_state_layout.py, tests/test_install_dry_run.py, tests/test_instruction_budget.py
- s0 · tests/fixtures/memory/partition.json, tests/test_memory_layout.py · tests/test_memory_layout.py · done
- s1 · tests/test_memory_sync_characterization.py, tests/fixtures/memory/goldens/sync/** · tests/test_memory_sync_characterization.py · done
- s2 · skills/ai-task/memory_io.py, skills/ai-task/memory_config.py, skills/ai-task/memory_packages.py, skills/ai-task/memory_verify.py, skills/ai-task/memory_hook.py, skills/ai-task/memory_risks.py, skills/ai-task/memory_cleanup.py, skills/ai-task/memory_migrate.py, skills/ai-task/memory_export.py, skills/ai-task/memory_status.py · no tests · done · after s0, s1
- s3 · skills/ai-task/memory_sync.py, skills/ai-task/rr_state/memory_cmd.py, skills/ai-task/rr_state/close.py, skills/rr-setup/setup.py, tests/test_memory_sync.py, tests/test_memory_store.py, tests/test_memory_cleanup.py, tests/test_memory_pre_push.py, tests/test_install_dry_run.py, tests/test_memory_layout.py · tests/test_memory_characterization.py, tests/test_memory_migration.py, tests/test_memory_risks.py, tests/test_memory_recall.py, tests/test_setup.py, tests/test_state_layout.py · done · after s2, s0
- s4 · docs/architecture.md, CONTRIBUTING.md, docs/sdlc/plans/small-oop-modules-wp4.md · tests/test_instruction_budget.py · done · after s2
amended 2026-11-11T20:10:17Z: +tests/fixtures/state/partition.json — s3 SCOPE_CHANGE_REQUIRED: D3 renames memory_cmd's third argument sync->mem; the WP1 partition pins the 16 action signatures as (…, sync, …), so test_state_layout fails; signature strings only, lazy fields stay as the plan says

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | f8f4e9790 | .ai/state/logs/T-2026-11-11-1949-wp4-memory-sync-py/suite-1.log | no |
| 2 | suite | 0 | 1d2bb55cf | .ai/state/logs/T-2026-11-11-1949-wp4-memory-sync-py/suite-2.log | no |
| 3 | e2e | 0 | 1d2bb55cf | .ai/state/logs/T-2026-11-11-1949-wp4-memory-sync-py/e2e-3.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass

```
FINDINGS
- [LOW] L1 `tests/test_memory_sync_characterization.py:98` GIT_NOISE regex `(error|hint|To) ` (used with `.match`) has no colon, so it does not drop git's `error: ` / `hint: ` lines as the docstring (:63-66) says. It drops only lines starting `To ` or `error `/`hint ` with no colon. Evidence: `goldens/sync/validator.txt:455` keeps `error: failed to push some refs to '<TMP>/remote.git'`.
  in_scope: yes
  Effect: this hides nothing, because it erases less than documented. But the golden now carries git's own wording, which depends on the git version and so can go red on a different git for no reason of ours. The docstring is also wrong about the rule. Fix one or the other.
- [LOW] L2 `skills/ai-task/memory_hook.py:12` The section header "status, show" sits over `hook_state`, which is hook code. `memory_status.py` has no header at all, and `memory_hook.py:32` then opens "the git hook". Cosmetic and misleading.
  in_scope: yes
- [LOW] L3 `tests/fixtures/state/partition.json:280,354` `lazy` of `memory_modules` (`["memory_store","memory_sync"]`) and of `memory_after_close` (`["memory_sync"]`) now name a module that neither imports. Nothing reads `lazy` (`grep lazy tests/test_state_layout.py` is empty), so the false data is inert today, but a later WP that reads it will be misled. The plan accepted this. Deviation 4a (the 16 `signature` renames `sync`→`mem`) is correct and forced: `test_state_layout.py:167` compares those signatures against the code through `ast`, and it adds no behavioural expectation. I judge it acceptable under R6, but it should be recorded as a deliberate R6 exception.
  in_scope: yes
- [INFO] I1 `tests/test_memory_sync_characterization.py` LINE_ORDER (sorts .jsonl record lines) and BYTES (`N bytes`) are the only erasures that go beyond the plan's list. I judge neither hides a moved SELF, a changed file or a changed order a user sees. LINE_ORDER touches only the on-disk listing hash; stdout order (`show`, `export`, `verify`) is still pinned verbatim, and a package's header line stays first. BYTES hides only the printed size; the file content is still pinned by the listing hash. The docstring says "Nothing else is erased", and the docstring and `RULES` are kept consistent by `test_docstring_lists_every_rule`.
  in_scope: yes
- [INFO] I2 `skills/ai-task/rr_state/memory_cmd.py:24-45` An install missing any of the ten modules dies with the same text but names whichever import fails first. The plan accepted this.
  in_scope: no
- [INFO] I3 The two residuals the plan said stay (export skips keys that already have a seal; `memory enable` through a dialog pick leaves no committed record) are untouched and pinned by the golden. They are not new bugs.
  in_scope: no
VERDICT pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CONTRIBUTING.md | +12 −0 | Edit |
| docs/architecture.md | +28 −1 | Edit |
| docs/sdlc/plans/small-oop-modules-wp4.md | +5 −2 | Edit |
| skills/ai-task/memory_cleanup.py | +213 −0 | New |
| skills/ai-task/memory_config.py | +120 −0 | New |
| skills/ai-task/memory_export.py | +246 −0 | New |
| skills/ai-task/memory_hook.py | +139 −0 | New |
| skills/ai-task/memory_io.py | +113 −0 | New |
| skills/ai-task/memory_migrate.py | +187 −0 | New |
| skills/ai-task/memory_packages.py | +83 −0 | New |
| skills/ai-task/memory_risks.py | +84 −0 | New |
| skills/ai-task/memory_status.py | +75 −0 | New |
| skills/ai-task/memory_sync.py | +18 −1481 | Edit |
| skills/ai-task/memory_verify.py | +308 −0 | New |
| skills/ai-task/rr_state/close.py | +2 −2 | Edit |
| skills/ai-task/rr_state/memory_cmd.py | +76 −63 | Edit |
| skills/rr-setup/setup.py | +8 −7 | Edit |
| tests/fixtures/memory/goldens/sync/commands.txt | +596 −0 | New |
| tests/fixtures/memory/goldens/sync/migrate.txt | +267 −0 | New |
| tests/fixtures/memory/goldens/sync/refusals.txt | +381 −0 | New |
| tests/fixtures/memory/goldens/sync/validator.txt | +490 −0 | New |
| tests/fixtures/memory/partition.json | +865 −0 | New |
| tests/fixtures/state/partition.json | +16 −16 | Edit |
| tests/test_install_dry_run.py | +1 −0 | Edit |
| tests/test_memory_cleanup.py | +4 −3 | Edit |
| tests/test_memory_layout.py | +1030 −0 | New |
| tests/test_memory_pre_push.py | +13 −12 | Edit |
| tests/test_memory_store.py | +2 −2 | Edit |
| tests/test_memory_sync.py | +14 −11 | Edit |
| tests/test_memory_sync_characterization.py | +612 −0 | New |

+6008 −1600 lines, 30 files

## Verdict

close: closed
facts: (a) green — suite green on 1d2bb55cf (run 2) · (b) green — 30 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 2 · review passes: 1
