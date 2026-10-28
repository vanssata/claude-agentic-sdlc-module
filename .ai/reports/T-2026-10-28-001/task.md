# T-2026-10-28-001 — Spike 7.0: record real AskUserQuestion, Stop, Notification, subagent PreToolUse and Codex request_user_input hook payloads as fixtures under tests/fixtures/dialog/ and write docs/dialog-spike.md naming the fields tasks 7a-7f rely on and the Codex version list for R36.19

feature · light · started 2026-10-28T10:44:17Z · claude

## Weight

```
scope          0  tests/fixtures/dialog/claude/ask-single.json is new
behaviour      0  every declared file is new
reversibility  0  git revert returns everything
domain         0  test fixtures and a doc; touches no user-project module and nothing customer-visible (declared)
novelty        1  new payload shapes from two runtimes not yet in the repo, no new dependency; whether Codex fires
coverage       0  no code file declared
W 1 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/fixtures/dialog/claude/ask-single.json, tests/fixtures/dialog/claude/ask-multi.json, tests/fixtures/dialog/claude/ask-other.json, tests/fixtures/dialog/claude/ask-esc.json, tests/fixtures/dialog/claude/stop.json, tests/fixtures/dialog/claude/stop-hook-active.json, tests/fixtures/dialog/claude/auth-success.json, tests/fixtures/dialog/claude/subagent-pretooluse.json, tests/fixtures/dialog/codex/request-single.json, tests/fixtures/dialog/codex/request-multi.json, tests/fixtures/dialog/codex/request-cancel.json, tests/fixtures/dialog/codex/pretooluse.json, tests/fixtures/dialog/codex/posttooluse.json, tests/fixtures/dialog/codex/NEGATIVE.md, docs/dialog-spike.md, tests/fixtures/dialog/claude/notification-permission-prompt.json, tests/fixtures/dialog/codex/request-other.json
tests: python3 -I -c "import glob, json, sys;fs=glob.glob('tests/fixtures/dialog/**/*.json', recursive=True);[json.load(open(p)) for p in fs];print(len(fs), 'fixtures parse')"
amended 2026-10-28T11:07:11Z: +tests/fixtures/dialog/claude/notification-permission-prompt.json — the TUI session recorded the Notification envelope as permission_prompt, not auth_success; the shape is pinned under its real type and auth-success.json stays open
amended 2026-10-28T11:19:29Z: +tests/fixtures/dialog/codex/request-other.json — Codex recorded the Other answer form (None of the above + user_note); the plan named only single, multi and cancel, and multi and cancel were not produced by the runtime or the human

## Questions

[questions.md](questions.md) — 0 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 167e91048 | .ai/state/logs/T-2026-10-28-001/step-1.log | no |
| 2 | suite | 0 | 635e7ac7e | .ai/state/logs/T-2026-10-28-001/suite-2.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/dialog-spike.md | +172 −0 | New |
| tests/fixtures/dialog/claude/ask-esc.json | +47 −0 | New |
| tests/fixtures/dialog/claude/ask-multi.json | +82 −0 | New |
| tests/fixtures/dialog/claude/ask-other.json | +82 −0 | New |
| tests/fixtures/dialog/claude/ask-single.json | +74 −0 | New |
| tests/fixtures/dialog/claude/notification-permission-prompt.json | +23 −0 | New |
| tests/fixtures/dialog/claude/stop-hook-active.json | +27 −0 | New |
| tests/fixtures/dialog/claude/stop.json | +27 −0 | New |
| tests/fixtures/dialog/claude/subagent-pretooluse.json | +31 −0 | New |
| tests/fixtures/dialog/codex/posttooluse.json | +26 −0 | New |
| tests/fixtures/dialog/codex/pretooluse.json | +41 −0 | New |
| tests/fixtures/dialog/codex/request-other.json | +42 −0 | New |
| tests/fixtures/dialog/codex/request-single.json | +42 −0 | New |

+716 −0 lines, 13 files

## Verdict

close: closed
facts: (a) green — suite green on 635e7ac7e (run 2) · (b) green — 13 changed files, all in the task's files
gate: none
confirm: none
handoffs: 9 · suite runs: 1 · review passes: 0
