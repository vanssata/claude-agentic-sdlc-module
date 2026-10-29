# T-2026-10-29-1756-low-l1-of-t-2026-10-29 — LOW L1 of T-2026-10-29-1746: ai-init safety.md template gains the guards' threat model paragraph (T4+ worded as full mode)

feature · guarded · started 2026-10-29T17:56:59Z · claude

## Weight

```
scope          2  .ai/policies/safety.md referenced from 151 files
behaviour      1  pipeline; hint +1
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 5 → guarded   hints behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T17:56:59Z — /rr-build-all: fix the LOW finding too; edits made just before start (policy file is frozen during a task)

## Plan

files: .ai/policies/safety.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, skills/project-update/history/blobs/7f78b0a2316af323f939b37e743cdbd354b2fac7bb5273ad7ad3da8e9238e7cc, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-3.md
tests: tests/test_project_update.py
- s1 · .ai/policies/safety.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, skills/project-update/history/blobs/7f78b0a2316af323f939b37e743cdbd354b2fac7bb5273ad7ad3da8e9238e7cc · tests/test_project_update.py · done
amended 2026-10-29T17:56:59Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-3.md — review report via --report - from a file

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | fbd35c898 | .ai/state/logs/T-2026-10-29-1756-low-l1-of-t-2026-10-29/suite-1.log | no |
| 2 | e2e | 0 | fbd35c898 | .ai/state/logs/T-2026-10-29-1756-low-l1-of-t-2026-10-29/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 "in full mode" is slightly loose: it also covers full_irreversible (`skills/ai-task/state.py:4140` gates both). Accurate for the gate itself, and `docs/weight.md` and `skills/rr-ship/SKILL.md` say "full mode" the same way. (`.ai/policies/safety.md:57`, `skills/ai-init/templates/.ai/policies/safety.md:57`)  in_scope: yes
  why it matters: a reader could take it to exclude full_irreversible. No behaviour changes.
  suggested direction: leave as is, or write "in full mode (and full_irreversible)" if exactness matters.
- [INFO] I1 Old tier wording "T4+" still ships in `skills/ai-init/templates/.ai/policies/risk-tiers.md:104` ("`ai-risk` on STRONG when a T4+ classification…"). The repo copy `.ai/policies/risk-tiers.md:120` has it too. risk-tiers.md is a legacy tier vocabulary file, so this is consistent with the wider tier scaffolding. It is the same class of leftover as the phrase this task replaced, but it is not part of this task.  in_scope: no
  why it matters: it would carry the old label if risk-tiers.md is meant to follow 2.H. I rate it LOW.
  suggested direction: record it as a separate follow-up, not here.
- [INFO] I2 Three planning documents keep the old phrase "the human gate at T4+": `docs/sdlc/plans/direct-mode-diet-policy-texts.md:167`, `docs/sdlc/specs/command-choice-dialog.md:399` and `docs/sdlc/specs/direct-mode-diet.md:783`. They are historical records and are not shipped to user projects, so leave them.  in_scope: no
  why it matters: none for users.

## EXAMINED AND CLEAN
- **Accuracy of "full mode".** `state.py close` requests the human gate only when `mode in ("full","full_irreversible")` (`state.py:4140`). `skills/rr-ship/SKILL.md` §2 is titled "The human's approval (full mode)". Light and guarded modes close without it, so the phrase is correct. (`MODE_TIER` maps guarded to the old T4. That is why "T4+" was wrong, since guarded does not gate.)
- **Paragraph fit for a user project.** The paragraph names only the guards and `state.py consent audit`. The guards (`hooks/`) and `state.py` (`skills/ai-task/`) ship with the plugin and run in user projects. `state.py consent` exists (`state.py:2290` and following), and `rr-ship/SKILL.md:88` documents `$STATE consent [audit]`. Nothing in the paragraph is repo-private.
- **Byte identity.** `cmp` reports the repo policy and the template identical. The template diff against HEAD is only the paragraph insert. The repo diff is only the phrase swap.
- **History index and blob.**
  - sha256 of the new template is 7f78b0a2…, which equals the new last entry of `ai-init/.ai/policies/safety.md` in `index.json` (5 entries, hash present once).
  - The previous last entry, e9adb7a9…, equals the sha256 of the HEAD template, so the chain is continuous.
  - The blob exists and its content hashes to its own name.
  - The diff of `index.json` is one appended line.
- **Impact on `/rr-setup --update`.**
  - A project whose safety.md still matches an older template hash, which is now in the history, counts as untouched and is replaced with the new text (`tests/test_project_update.py:862`).
  - A project that edited the file keeps its edits through the project-update machinery. This change adds a hash and does not touch that logic.
  - `policies/safety.md` stays a scaffolded, project-owned file, not shared (`tests/test_shared_tree.py:224` and following).
- **Tests that pin the text.** None pin the paragraph or the phrase (grep of `tests/` found only existence and equality checks). The suite and e2e logs are green: suite `OK (skipped=5)`, e2e `Ran 5 tests … OK`. I did not re-run them.
- **Other shipped uses of the old wording.** Searched `ai/`, `instructions/`, `skills/*/templates`, `skills/*/SKILL.md`, `hooks/`, `docs/weight.md`, `.ai/policies`, `.ai/workflows` and `.ai/agents` for `T4+` and "human gate". The only hits are risk-tiers.md (I1) and the phrase just changed.
- **Scope.** `docs/time-analysis-2026-10-23-29.md` and earlier reports were not touched by the task.

## VERDICT
verdict: pass
scope_assessment: Stayed inside the plan. Two policy files, one history index entry and one blob, all consistent. No code, tests or other templates were touched. Only the LOW and INFO rows above remain.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: closed
facts: (a) green — suite green on fbd35c898 (run 1) · (b) green — 0 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
