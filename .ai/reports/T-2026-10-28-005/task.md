# T-2026-10-28-005 — Runtime-default context with an opt-in economy mode, and model + context use in the Claude and Codex statusline

feature · guarded · started 2026-10-28T15:39:04Z · claude

## Weight

```
scope          2  profiles/max.json referenced from 8 files
behaviour      2  changes what the installer writes into settings.json and when context-guard holds a prompt back 
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  new flags on existing installer/statusline paths (declared)
coverage       1  2 of 5 code files have a test
W 7 → guarded   hints none · unknown domain · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: profiles/max.json, profiles/pro.json, scripts/resolve-profile.py, scripts/merge-codex-config.py, hooks/context-guard.py, hooks/runtime-gate.py, bin/riskrails.js, bin/claude-1m, instructions/routing.md, README.md, docs/hooks.md, tests/test_profiles.py, tests/test_context_guard.py, tests/test_install_dry_run.py, tests/test_runtime_gate.py, tests/test_codex_install.py
tests: tests/test_profiles.py, tests/test_context_guard.py, tests/test_install_dry_run.py, tests/test_runtime_gate.py, tests/test_codex_install.py
- s1 · profiles/max.json, profiles/pro.json, scripts/resolve-profile.py, tests/test_profiles.py · tests/test_profiles.py · in_progress
- s2 · hooks/context-guard.py, tests/test_context_guard.py · tests/test_context_guard.py · pending
- s3 · bin/riskrails.js, bin/claude-1m, instructions/routing.md, tests/test_install_dry_run.py · tests/test_install_dry_run.py · pending
- s4 · hooks/runtime-gate.py, bin/riskrails.js, tests/test_runtime_gate.py, tests/test_install_dry_run.py · tests/test_runtime_gate.py, tests/test_install_dry_run.py · pending
- s5 · scripts/merge-codex-config.py, bin/riskrails.js, tests/test_codex_install.py · tests/test_codex_install.py · pending
- s6 · README.md, docs/hooks.md · tests/test_instruction_budget.py · pending

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

+0 −0 lines, 0 files

## Verdict

close: abandoned
facts: (a) not measured · (b) not measured
gate: none
confirm: none
handoffs: 1 · suite runs: 0 · review passes: 0
