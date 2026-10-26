# Questions — T-2026-10-26-005
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. 'questions' is not old-surface-only: '--sync' is the only code that records an [Answer]: line filled in questions.md, and the only file route that approves or rejects the gate (close_gate_from_file). Remove it now, or keep it until phase 3 moves questions into task.md?
asked: 2026-10-26T18:31:53Z · stage: implementation
context: skills/ai-task/state.py:2447 cmd_questions, :2866 close_gate_from_file, :3069 OLD_ONLY excludes questions/note/events
A. remove all 19 as planned; the gate is approved only by 'approve' in a terminal (rr-ship/rr-status already say so); file answers still unblock (guard_pending re-reads the file) but are not journaled; C6 raises the mode to full (approval path changes)
B. keep 'questions' (--sync, --pending, --format) until phase 3, remove 18; nothing about approval changes and the task stays guarded; Q1 then needs no context-guard edit (recommended)
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via prose at 2026-10-26T18:33:42Z

## Q2. tests/test-ai-task-state.sh: about 950 of its 1627 lines test code that STAYS (the gate's file route, approve/reject attribution, ask/answer parsing, handoff.md, the journal, runtime ownership, WP5 handoff --to), but set the task up with removed commands (init, stage human_approval, get). Plain dropping leaves the approval code without those tests until 3.3b. What do we do with them?
asked: 2026-10-26T18:41:37Z · stage: implementation
context: tests/test-ai-task-state.sh:359-1313 (retained) vs :16-151, :1341-1626 (old surface)
A. port those cases now into tests/test_ai_task_state.py (start/close set-up, Python), drop them from the .sh, and 3.3b shrinks by that much; ~670 lines whose subject is a removed command are dropped and listed (recommended)
B. keep them in the .sh with the set-up rewritten to start/close; 3.3b still ports the file
C. drop them too and record the coverage gap in known-risks until 3.3b
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-26T18:45:34Z
