# T-2026-10-29-0755-plan-drift-7e — Command choice dialog — step 7e plan drift (R36.16 --open, R36.18)

feature · full · started 2026-10-29T07:55:18Z · claude

## Weight

```
scope          2  hooks/context-guard.py matches hot_paths hooks/**
behaviour      2  a new gate at SessionStart: plan drift opens a decision (declared)
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  2 of 2 code files have a test
W 6 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by vanssa at 2026-10-29T07:55:18Z — /rr-build-all docs/sdlc/plans/command-choice-dialog.md (row 7e only; 3.4c, H1, 7f out of scope)
batch: on by vanssa at 2026-10-29T07:55:18Z — /rr-build-all docs/sdlc/plans/command-choice-dialog.md (row 7e only; 3.4c, H1, 7f out of scope)

## Plan

files: hooks/context-guard.py, skills/ai-task/state.py, settings.common.json, hooks/hooks.json, codex/hooks.json, hooks/codex-hooks.json, .ai/project/known-risks.md, tests/test_context_guard.py, tests/test_profile_detect.py, nextStep.md
tests: tests/test_context_guard.py, tests/test_profile_detect.py, tests/test_install_routes.py, tests/test_codex_install.py, tests/test_dialog_gate.py
- s7e · hooks/context-guard.py, skills/ai-task/state.py, settings.common.json, hooks/hooks.json, codex/hooks.json, hooks/codex-hooks.json, .ai/project/known-risks.md, tests/test_context_guard.py, tests/test_profile_detect.py · tests/test_context_guard.py, tests/test_profile_detect.py, tests/test_install_routes.py, tests/test_codex_install.py, tests/test_dialog_gate.py · done
amended 2026-10-29T08:25:02Z: +nextStep.md — approved night plan: nextStep.md in the repo root lists the human's commands (gate, commits, H1, 2.H, 3.H2, memory G1/G2, FC5)

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-29-0755-plan-drift-7e for implementation? (gate: human_approval)
asked: 2026-10-29T08:24:21Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]:

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 0126b764b | .ai/state/logs/T-2026-10-29-0755-plan-drift-7e/suite-1.log | no |
| 2 | e2e | 0 | 0126b764b | .ai/state/logs/T-2026-10-29-0755-plan-drift-7e/e2e-2.log | no |
| 3 | suite | 0 | 861a6881a | .ai/state/logs/T-2026-10-29-0755-plan-drift-7e/suite-3.log | no |
| 4 | e2e | 0 | 861a6881a | .ai/state/logs/T-2026-10-29-0755-plan-drift-7e/e2e-4.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS

- [HIGH] H1 A `plan_drift` decision opened in one session is reused by every later session, and no later session can answer it; the decision is never closed when it goes stale (`skills/ai-task/state.py:835-839`, `hooks/context-guard.py:483-490`) in_scope: yes
  why: `open_drift` returns any open `plan_drift` with the same fingerprint whatever session it is bound to. s2's `decision show --id D1` filters by session (state.py:2853-2856) and dies exit 1; the hook falls back to the dialog-off warning; guard `bound()` (hooks/guard/dialog.py:400-404) leaves s2 ungated; D1 stays in decision.json for good. Same staleness when drift resolves (status `same`) or is acked elsewhere. No multi-session test.
  fix: reuse only when its `session` is the caller's, else fall it back before opening a new one; when `--open` sees a non-drift status, fall back the runtime's open `plan_drift` decisions. Pin with a two-session SessionStart test.
- [MEDIUM] M1 The ack matches on the fingerprint alone and ignores which plan was kept (`skills/ai-task/state.py:784`) in_scope: yes
  fix: match only when fingerprint and `kept == installed.plan`; test that changes only profile.json after an ack.
- [MEDIUM] M2 With the dialog off there is no route to "Keep": a deliberate plan choice is warned about at every SessionStart, in every project and every directory without `.ai/` (`hooks/context-guard.py:737-741`, `skills/ai-task/state.py:854-858`) in_scope: yes
  fix: human decision on the spec — a human-route terminal ack (e.g. `profile detect --ack` behind `human_route()`), or record the gap in known-risks.md next to D2.
- [LOW] L1 UserPromptSubmit records `account_mtime` before detection runs, so a failed check is never retried for that mtime; `--open` dies exit 1 when decision.json is unreadable, breaking R36.16 "0 always" (`hooks/context-guard.py:611-614`) in_scope: yes
  fix: write account_mtime only after detect returns parseable JSON; `--open` degrades to read-only when decision.json cannot be read.
- [LOW] L2 With no payload `session_id`, the hook passes "unknown" while `effective_switch` treats a missing id as off (`hooks/context-guard.py:730,763` vs `hooks/guard/dialog.py:125`) in_scope: yes
  fix: pass session=None when the payload has none.
- [LOW] L3 A non-object under a runtime key in drift-ack.json crashes every `profile detect` with AttributeError (`skills/ai-task/state.py:784`, `read_drift_ack`) in_scope: yes
  fix: isinstance(..., dict) on the per-runtime entry.
- [LOW] L4 Text drift: systemMessage names the installed plan by raw id but the live one through `names`; module docstring still says "three Claude Code events" (`hooks/context-guard.py:476-490`, `:1-55`); `bin/riskrails.js:1200` lists context-guard's events without Notification (out of scope) in_scope: yes
- [INFO] I1 The recheck fires on any `~/.claude.json` write (INFERENCE); with drift and dialog off the warning repeats per prompt; ~70 ms per recheck with no drift. in_scope: yes
- [INFO] I2 The model can clear the drift gate with `decision fallback` (R36.15); no ack is written; asked again later. No route lets the model write the ack. in_scope: yes
- [INFO] I3 drift-ack.json read-modify-write is atomic (os.replace) but unlocked; concurrent Claude/Codex keep could lose an entry; `open_decision` takes no lock (pre-existing). in_scope: yes

Examined and clean: no-drift output byte-identical; fail-open; session id via env; switch consistency apart from L2; decision shape; ack write and shape; §S no account data stored; Notification; Codex parity; test hermeticity; install route; known-risks labels; no model bypass of the ack.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the plan's file list (7 of 9; the two Codex files deliberately unchanged). The `prompt_warning` split preserves behaviour. No test weakened. No BLOCKER. H1 and M1 are untested gaps, each with the test that would pin it. M2 needs a human decision on the spec.
```

closed by a green run: H1

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on 861a6881a (run 3) · (b) green — 7 changed files, all in the task's files
gate: requested G1 at 2026-10-29T08:24:21Z; approved by - at - via -
confirm: none
handoffs: 4 · suite runs: 2 · review passes: 1
