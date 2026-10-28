# T-2026-10-28-008 — R36 step 7d1: the inert hook half of the dialog — consent-ledger module, PostToolUse recorder, Stop blocker, payload fields, decision fast path and registrations in both routes; off or no decision open changes no decision

feature · guarded · started 2026-10-28T17:02:26Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      2  registers hooks on every tool and on Stop in every installed user project (C6, plan row 7d1 expe
reversibility  0  git revert returns everything
domain         1  writes the consent ledger an approval path will later trust (7d2); no secrets or auth handled (d
novelty        1  new hook entry point and Stop/PostToolUse events; ledger rules mirror state.py's 7c reader (decl
coverage       1  3 of 7 code files have a test
W 7 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: hooks/guard/dialog.py, hooks/guard/decision.py, hooks/dialog-gate.py, hooks/guard/common.py, hooks/ai-guard.py, hooks/context-guard.py, settings.common.json, codex/hooks.json, hooks/hooks.json, hooks/codex-hooks.json, bin/riskrails.js, docs/hook-performance.md, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/guard_harness.py, tests/test_context_guard.py, tests/test_codex_install.py, .ai/project/known-risks.md
tests: tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_context_guard.py, tests/test_codex_install.py, tests/test_install_routes.py
- s1 · hooks/guard/dialog.py, hooks/guard/common.py, tests/guard_harness.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py · tests/test_dialog_gate.py, tests/test_dialog_contract.py · in_progress
- s2 · hooks/dialog-gate.py, hooks/guard/decision.py, hooks/ai-guard.py, hooks/context-guard.py, tests/test_dialog_gate.py, tests/test_context_guard.py · tests/test_dialog_gate.py, tests/test_context_guard.py · pending
- s3 · settings.common.json, codex/hooks.json, hooks/hooks.json, hooks/codex-hooks.json, bin/riskrails.js, tests/test_codex_install.py, docs/hook-performance.md, tests/test_dialog_gate.py · tests/test_dialog_gate.py, tests/test_codex_install.py, tests/test_install_routes.py · pending
amended 2026-10-28T17:05:44Z: +.ai/project/known-risks.md — hooks/CLAUDE.md: a behaviour-2 hook task runs as full; known-risks.md records the duplicate-question-text ambiguity found in 7c's split payload

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|

suite not_run · e2e not_run · suite runs 0

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/guard/dialog.py | +465 −0 | New |

+465 −0 lines, 1 files

## Verdict

close: abandoned
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 1 · suite runs: 0 · review passes: 0
