# Questions — T-2026-10-27-006
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. tests/fixtures/scaffold-port/scaffold-ai.sh (frozen in 3.2) does not know the riskrails marker, so test_scaffold_differential fails in 69 cases: the frozen shell appends a second block. How do we keep the differential?
asked: 2026-10-27T19:58:09Z · stage: implementation
context: tests/fixtures/scaffold-port/scaffold-ai.sh:105; decision 2A covered guard-port, not scaffold-port
A. patch the frozen scaffold copies rename-only (marker regex + install hint), each changed line holding the old name, like the golden (recommended)
B. keep them frozen; the differential runs the frozen copy on templates with the old markers and maps its output to the new names
C. retire test_scaffold_differential now — it proved the 3.2 port, and 3.5 deletes the shims anyway
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-27T20:04:18Z

## Q2. H1: after a git revert of 3.4b, a project already on state.json + VERSION 8 silently loses its scope guard and task-protected paths (HEAD reads only current.json and refuses schema 8). How do we make the way back safe?
asked: 2026-10-27T20:33:08Z · stage: implementation
context: docs/sdlc/plans/claude-agentic-redesign.md:344; spec R34 says 'Migration 0008 moves the file' — B changes that, so it is a spec amendment
A. keep the design; rewrite the plan's Rollback with an exact per-project restore (move state.json back to current.json, VERSION 7) and a reverse-0008 script under tools/, tested on a migrated fixture
B. expand/contract — 3.4b ships only the both-name readers and the RiskRails rename, no file move; the move (0008's MOVES and save()'s removal of current.json) waits for a later task, after a version has shipped the readers (recommended)
C. correct only the Rollback text (manual steps), no script
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via prose at 2026-10-27T20:52:34Z

## G1. Approve T-2026-10-27-006 for implementation? (gate: human_approval)
asked: 2026-10-27T21:03:28Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]:
