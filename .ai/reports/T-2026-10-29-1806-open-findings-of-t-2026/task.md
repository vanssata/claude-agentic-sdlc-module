# T-2026-10-29-1806-open-findings-of-t-2026 — Open findings of T-2026-10-29-1756 (L1 full_irreversible, I1 T4+ in risk-tiers, I2 old phrase in history docs) and T-2026-10-29-1655 I1 (lead for the unclosed journals)

feature · guarded · started 2026-10-29T18:06:23Z · claude

## Weight

```
scope          2  .ai/policies/safety.md referenced from 153 files
behaviour      2  keyword 'workflow' in .ai/project/known-risks.md; hint +1
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 6 → guarded   hints behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T18:06:23Z — /rr-build-all: fix L1, I1, I2 and every other open finding before the commit; safety.md L1 edited just before start (policy frozen during a task)

## Plan

files: .ai/policies/safety.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, docs/sdlc/plans/direct-mode-diet-policy-texts.md, docs/sdlc/specs/command-choice-dialog.md, docs/sdlc/specs/direct-mode-diet.md, .ai/project/known-risks.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-4.md, skills/project-update/history/blobs/ae5ce131d6bae401199ff32d8c3dc4d8aec188010a9111624ac64506e2116ff4, skills/project-update/history/blobs/7f78b0a2316af323f939b37e743cdbd354b2fac7bb5273ad7ad3da8e9238e7cc, docs/sdlc/intent/faster-task-cycle.questions.md
tests: tests/test_project_update.py
- s1 · .ai/policies/safety.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json · tests/test_project_update.py · done
- s2 · docs/sdlc/plans/direct-mode-diet-policy-texts.md, docs/sdlc/specs/command-choice-dialog.md, docs/sdlc/specs/direct-mode-diet.md · no tests · done
- s3 · .ai/project/known-risks.md · no tests · done
amended 2026-10-29T18:06:23Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-4.md — review report via --report - from a file
amended 2026-10-29T18:07:11Z: +skills/project-update/history/blobs/ae5ce131d6bae401199ff32d8c3dc4d8aec188010a9111624ac64506e2116ff4, skills/project-update/history/blobs/7f78b0a2316af323f939b37e743cdbd354b2fac7bb5273ad7ad3da8e9238e7cc — build-template-history: new blob for the template; the uncommitted intermediate blob of T-2026-10-29-1756 is dropped
amended 2026-10-29T18:37:23Z: +docs/sdlc/intent/faster-task-cycle.questions.md — written at 20:17 by state.py ask from another session (faster-task-cycle Q1), not by this task; included on the developer's pick so close can measure; not part of this task's commit

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | adfe63ea6 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/suite-1.log | no |
| 2 | suite | 0 | - | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/suite-2.log | no |
| 3 | e2e | 0 | 255a98424 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/e2e-3.log | no |
| 4 | suite | 1 | 4d767d459 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/suite-4.log | no |
| 5 | suite | 1 | 4d767d459 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/suite-5.log | no |
| 6 | suite | 0 | 4d767d459 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/suite-6.log | no |
| 7 | e2e | 0 | 4d767d459 | .ai/state/logs/T-2026-10-29-1806-open-findings-of-t-2026/e2e-7.log | no |

suite passing · e2e passing · suite runs 5

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 Missing comma in the flaky-test list, so the "KNOWN FACT" sentence reads as a run-on (`.ai/project/known-risks.md:749`)  in_scope: yes
  why it matters: the text now says "...suites 1 and 2 (twice in a row) T-2026-10-29-1724 suite 1 (...) and T-2026-10-29-1806 suite 1". Dropping the old "and" before -1724 left no separator after "(twice in a row)". It is cosmetic and the facts are right.
  suggested direction: put a comma after "(twice in a row)".
- [INFO] I1 Decision on 1756 I1 (leave "T4+" and `ai-risk` in risk-tiers.md): sound. in_scope: yes
  why it matters: the risk-tiers.md and risk-tiers.json pairs carry the same wording (JSON line 41 in the repo copy and the template, "T4 or above … (ai-risk on STRONG)"; md template:104, repo:120). Rewording only the md would make the pair disagree, and the file is tier vocabulary throughout, with `ai-risk` also at md:45 and :61. The retirement entry already exists, and the new bullet is accurate: `ai-risk` is in `REMOVED_AGENTS` (tests/test_skills_surface.py:34) and `agents/` has no such file. The bullet sits after "Status: open", which is harmless, and the entry's own "ai-risk-strong" claim is not affected.
- [INFO] I2 In `docs/sdlc/plans/direct-mode-diet-policy-texts.md` the patch text itself still says "T4+" (line 167). in_scope: yes
  why it matters: that is intended, because the patch is kept as applied. The dated note at :355-357 says so. Nothing to fix.

## EXAMINED AND CLEAN
- L1 text: `state.py:4140` gates `mode in ("full","full_irreversible")`, so "in full and full_irreversible mode" is accurate. `cmp` shows the template and `.ai/policies/safety.md` byte-identical (same blob hash 70a71a3).
- History: `index.json` appends exactly one hash, `ae5ce131…`. It equals `sha256sum` of the template file, and the blob file exists. Blob `7f78b0a2…` is gone from the directory. `tools/build-template-history.py --dry-run` reports "0 blobs would be deleted, 149 kept, 31 shared keys". `git status` under `skills/project-update` shows only the index change and the new blob.
- Plan-file patches: I extracted patch:A and patch:B with the file's own `part()` awk before (HEAD) and after, and the sha256 of each is identical. The note sits after the closing fence of patch A (line 353), as plain text with no `diff` fence or patch marker. It renders as an ordinary paragraph before the "Part B" heading.
- Quoted note text matches: the patch does say "the human gate at T4+" (line 167). The spec `command-choice-dialog.md:399` keeps its original quote and gets a parenthetical dated note. `direct-mode-diet.md:783` gets a dated "(since redesign 2.H …)" aside, and that line says "gate at T4", not the T4+ phrase.
- Scope of the three doc edits: they are notes only, and no historical quote was rewritten.
- 1655 I1 lead, all points verified:
  - Commit 520e065 exists and is titled "T-2026-10-28-010: close record (approved)".
  - It adds `gate_approved` to `.ai/reports/T-2026-10-28-010/events.jsonl`.
  - `task.md:128` reads `close: open — the human approves in their own terminal, then 'state.py close' again`.
  - The journal's last event is `gate_approved` at 20:02:36Z, with no `task_closed`.
  - "Most likely never run" is correctly worded as an inference, and -012 "stops at gate_requested" matches the entry's existing "Where" text.
- Flaky-test entry: `suite-1.log` shows `FAIL: test_two_exports_at_once_serialise_on_the_lock`, `AssertionError: 'T-2026-10-29-1811-beta' not found in []`, 905 tests, 1 failure. This matches the new text. `suite-2.log` is OK (skipped=5) and `e2e-3.log` is OK (5 tests).
- Scope creep: none. Every changed file is on the task's list, and `docs/time-analysis-2026-10-23-29.md` and `.ai/reports/*` were untouched by this review.
- Markdown: the new paragraph in the template's safety.md matches the repo copy and renders normally. The known-risks bullets are well-formed.
- I did not re-derive the 1756 paragraph content (the brief marks it closed). I only checked that it is byte-identical in the template and the repo copy.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the plan. It fixes the L1 wording, records the retirement, adds the dated notes, adds the two known-risks facts and refreshes the history. It reworded no historical quote and left the `T4+` and `ai-risk` mirror text in `risk-tiers.md` as is. One LOW (a missing comma) is cosmetic and does not change the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +3 −2 | Edit |
| docs/sdlc/intent/faster-task-cycle.questions.md | +11 −0 | New |
| docs/sdlc/plans/direct-mode-diet-policy-texts.md | +4 −0 | Edit |
| docs/sdlc/specs/command-choice-dialog.md | +2 −1 | Edit |
| docs/sdlc/specs/direct-mode-diet.md | +2 −1 | Edit |
| skills/ai-init/templates/.ai/policies/safety.md | +2 −2 | Edit |
| skills/project-update/history/blobs/7f78b0a2316af323f939b37e743cdbd354b2fac7bb5273ad7ad3da8e9238e7cc | +0 −84 | Delete |
| skills/project-update/history/blobs/ae5ce131d6bae401199ff32d8c3dc4d8aec188010a9111624ac64506e2116ff4 | +84 −0 | New |
| skills/project-update/history/index.json | +1 −1 | Edit |

+109 −91 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on 4d767d459 (run 6) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 5 · review passes: 1
