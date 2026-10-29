# T-2026-10-29-1746-info-i1-i2-of-t-2026-10 — INFO I1/I2 of T-2026-10-29-1724: ai-init template safety.md gains the 2.H blocker sentence; redesign spec records 2.H done

feature · guarded · started 2026-10-29T17:46:16Z · claude

## Weight

```
scope          2  skills/ai-init/templates/.ai/policies/safety.md referenced from 149 files
behaviour      1  keyword 'workflow' in docs/sdlc/specs/claude-agentic-redesign.md
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 5 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T17:46:16Z — /rr-build-all: fix the INFO findings too

## Plan

files: skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, docs/sdlc/specs/claude-agentic-redesign.md, skills/project-update/history/blobs/e9adb7a9905eb719ac78ab96671f055da53e5001810f5ad6d6c94306b0323fe7, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-2.md
tests: tests/test_project_update.py
- s1 · skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json · tests/test_project_update.py · done
- s2 · docs/sdlc/specs/claude-agentic-redesign.md · no tests · done
amended 2026-10-29T17:46:36Z: +skills/project-update/history/blobs/e9adb7a9905eb719ac78ab96671f055da53e5001810f5ad6d6c94306b0323fe7 — blob written by tools/build-template-history.py for the safety.md template
amended 2026-10-29T17:52:35Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-2.md — review report goes to state.py review --report - from a file

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 0a5b4e745 | .ai/state/logs/T-2026-10-29-1746-info-i1-i2-of-t-2026-10/suite-1.log | no |
| 2 | e2e | 0 | 0a5b4e745 | .ai/state/logs/T-2026-10-29-1746-info-i1-i2-of-t-2026-10/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The template and the repo policy still differ beyond this sentence (`skills/ai-init/templates/.ai/policies/safety.md` vs `.ai/policies/safety.md`)  in_scope: yes
  why it matters: `diff` shows the repo file has a "The guards' threat model" paragraph (repo lines 53-61) that the template lacks. The 2.H sentence is now byte-identical in both files, so I1 is closed as stated. The template's new paragraph sits at lines 73-74 and the repo's at the end of the file. The earlier gap predates this task. It is not a defect of the change, only a limit on "template matches policy".
  suggested direction: none for this task. Decide separately whether the threat-model paragraph belongs in the shipped template.
- [INFO] I1 Existing user projects with an edited `safety.md` get a gated conflict, not a silent overwrite  in_scope: yes
  why it matters: `project-update` three-way-merges `.ai/policies/safety.md`. A project that appended text at the end of the file will hit a conflict on the new trailing paragraph. An untouched copy is replaced, which `tests/test_project_update.py:862` already pins (it compares against the current template, not a fixed hash). This is the normal, intended behaviour of a template change. `.ai/rules/skills.md:7` and plan line 83 both allow a shipped template to change inside a task together with `tools/build-template-history.py`. I found no migration or test that pins a hash of the `safety.md` template. The old hashes appear only in `history/index.json`, in `.ai/reports/T-2026-10-28-011/task.md`, and in stale worktree copies under `.claude/worktrees/`.
  suggested direction: none.

## EXAMINED AND CLEAN
- **Template text.** The added paragraph is "Doubt on reversibility or domain is a blocker; other doubt is written to `task.md` and the work continues." It is a separate paragraph after "When in doubt", and it matches `.ai/policies/safety.md` word for word. The line wrap differs trivially.
- **Blob and index.** `sha256sum` of the working-tree template equals the new blob's filename `e9adb7a9…`, and the blob content is identical to the template.
  - The index entry is appended last under `ai-init/.ai/policies/safety.md`, after the three earlier versions.
  - `build-template-history.py` deliberately includes the working tree "so uncommitted template edits are covered before the commit", so an index entry for uncommitted content is by design. `tests/test_project_update.py:773` (`test_history_covers_every_template`) requires exactly this.
  - `build-template-history.py --dry-run` reports 0 blobs would be deleted and 148 kept, so there are no orphans and no stale blobs.
  - The diff touches only that one index key. The tool was not re-run, to keep the review read-only. The verify logs (suite and e2e) are green on tree 0a5b4e745.
- **Rules and constitution.**
  - `.ai/rules/skills.md:7` is satisfied: the tool was run in the same task.
  - Plan line 83 says shipped templates change inside a task. The template path is not a protected `.ai/policies` path.
  - The repo's own `.ai/policies/safety.md` change belongs to the previous task, T-2026-10-29-1724.
  - Behaviour 1 is right for a text change to a template: no `state.py` refusal moves and the merge itself is unchanged, so it is not behaviour 2 under C6. The weight W 5, guarded, is consistent.
- **Spec notes.** The FC-A3 note (~:788) and the item 7 note (~:940) are dated 2026-10-29 and cite T-2026-10-29-1724 and T-2026-10-29-1746.
  - Both say the sentence is agent-written on the developer's instruction. That matches the 1724 review's own wording ("the sentence is now agent-written on the developer's instruction").
  - Both name the repo policy and the template. The item 7 note says "the `ai-init` template in T-2026-10-29-1746", which is accurate.
  - The original text was left in place and the notes were appended, so history is preserved. The only other lines touched are the two notes.
- **Scope.** `git diff HEAD --stat` shows 3 tracked files (+10/-3) plus the blob, which equals the declared file list. There is no refactoring, no code change, and no test edited or weakened.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the plan: s1 touched the template, the index and the blob, and s2 touched the spec notes. Both INFOs from the 1724 review are closed against the real files. No finding raises the verdict above pass.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/sdlc/specs/claude-agentic-redesign.md | +5 −2 | Edit |
| skills/ai-init/templates/.ai/policies/safety.md | +3 −0 | Edit |
| skills/project-update/history/blobs/e9adb7a9905eb719ac78ab96671f055da53e5001810f5ad6d6c94306b0323fe7 | +74 −0 | New |
| skills/project-update/history/index.json | +2 −1 | Edit |

+84 −3 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on 0a5b4e745 (run 1) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
