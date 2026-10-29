# T-2026-10-29-1636-shorten-c5-and-c6-in-the — Shorten C5 and C6 in the constitution to under 200 B each, meaning unchanged

refactoring · guarded · started 2026-10-29T16:36:11Z · claude

## Weight

```
scope          2  docs/sdlc/constitution.md referenced from 134 files
behaviour      1  keyword 'state machine' in docs/sdlc/constitution.md
reversibility  0  git revert returns everything
domain         0  project doc; no money, identity or personal data (declared)
novelty        0  render_instructions.py constitution check already defines the 200 B cap (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: docs/sdlc/constitution.md, .ai/project/known-risks.md
tests: tests/test_instruction_budget.py
- s1 · docs/sdlc/constitution.md · tests/test_instruction_budget.py · done
amended 2026-10-29T16:43:18Z: +.ai/project/known-risks.md — record review I3 (C5 wording drift outside scope) as a risk

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | ab3f2c5d0 | .ai/state/logs/T-2026-10-29-1636-shorten-c5-and-c6-in-the/step-1.log | no |
| 2 | suite | 0 | ab3f2c5d0 | .ai/state/logs/T-2026-10-29-1636-shorten-c5-and-c6-in-the/suite-2.log | no |
| 3 | e2e | 0 | ab3f2c5d0 | .ai/state/logs/T-2026-10-29-1636-shorten-c5-and-c6-in-the/e2e-3.log | no |
| 4 | suite | 0 | 28423e6cf | .ai/state/logs/T-2026-10-29-1636-shorten-c5-and-c6-in-the/suite-4.log | no |
| 5 | e2e | 0 | 28423e6cf | .ai/state/logs/T-2026-10-29-1636-shorten-c5-and-c6-in-the/e2e-5.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 C5 (Q1): "a command a human picked in the dialog the harness records" reads as the harness recording the dialog; the original made the pick the recorded thing ("picked … as recorded by the harness"), and the harness enforces the recorded pick. Slightly looser. Fix within cap: "…a command a human picked in the dialog, as the harness recorded; else a human runs it outside." (199 B). Dropping "runtime's" loses little. — in_scope: yes
- [LOW] L2 C5 (Q2): "else a human runs it outside" drops the object of "outside"; context makes "outside the agent" the only sensible reading; CLAUDE.md:35 uses the same short form ("a human outside"). Readability only; no room in the cap to restore it alongside L1. — in_scope: yes
- [INFO] I1 C6 (Q3): wording is semantically equivalent; examples preserved; "behaviour 2" matches docs/weight.md:123; the original also named no axis. No meaning change. — in_scope: yes
- [INFO] I2 Measured C5 194 B, C6 198 B — both within the 200 B cap. — in_scope: yes
- [INFO] I3 Wording drift outside the one file in scope: docs/sdlc/specs/command-choice-dialog.md:354-356 quotes the old "Amended C5" text; instructions/routing.md:49 and instructions/stub.md phrase the rule longer ("or the human runs them outside the agent"); skills/project-init/templates/constitution.md:10 has a third variant with no "runtime's" and no "as recorded by the harness" — the template new projects receive lacks the harness-recorded condition entirely. No test pins C5 wording (only tests/test_migration_0010.py:81 mentions C5, as a hint-line check). Follow-up, not a fix. — in_scope: no

## VERDICT
verdict: pass_with_findings
Recommendation: apply the L1 wording if the author wants the "recorded pick" semantics exact. Not a blocker; the gate is enforced mechanically by the harness, not by this sentence.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +10 −0 | Edit |
| docs/sdlc/constitution.md | +2 −2 | Edit |

+12 −2 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 28423e6cf (run 4) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
