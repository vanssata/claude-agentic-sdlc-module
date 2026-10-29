# Questions — redesign-3-6
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Q1: tests/test-runtime-gate-fable.sh (397 lines) and tests/test-runtime-gate-codex.sh (168) on tests/lib.sh were never ported (no 3.3 row took them; tests/test_runtime_gate.py has 16 cases and defers to them in its docstring). 3.H2 sets verify_command to 'python3 -I -m unittest discover tests', and 3.6 deletes run-all.sh, the only runner of these two suites. How do they survive?
asked: 2026-10-29T10:33:07Z · stage: intent
context: plan docs/sdlc/plans/claude-agentic-redesign.md:229-230,257; testing.md:87,127-133
A. a new row 3.3e before 3.H2 ports both to Python twins on install/guard harness (tests only, light), deletes the .sh and lib.sh; then 3.H2, then 3.6 (recommended)
B. keep run-all.sh as verify_command running the two .sh + unittest; 3.H2 is dropped, 3.6 deletes only test-end-to-end.sh
C. accept the loss: delete the two suites in 3.6 without twins
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose at 2026-10-29T10:33:57Z

## Q2. Q2: row 3.6 git-ignores .ai/reports/ in this repository, but 421 report files are tracked and every close record is committed there (the T-2026-10-29-0852 one is pending now); compact-project-memory (packages mode, M5/M11) is the later answer to report growth. Does 3.6 keep the .gitignore line?
asked: 2026-10-29T10:33:08Z · stage: intent
context: plan :136; spec docs/sdlc/specs/claude-agentic-redesign.md:282
A. drop it from 3.6; the reports stay tracked until the memory packages mode is switched on here (recommended)
B. keep it: .ai/reports/ ignored, the tracked files untracked with git rm --cached by the human
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose at 2026-10-29T10:33:57Z

## Q3. Q3: the close record of T-2026-10-29-0852 (.ai/reports/T-2026-10-29-0852-r36-rest/task.md, events.jsonl) is uncommitted. Commit it before the new task starts, so its diff is not counted against the new task's files?
asked: 2026-10-29T10:33:08Z · stage: intent
A. yes, the human commits it first (git add .ai/reports/T-2026-10-29-0852-r36-rest && git commit -m 'T-2026-10-29-0852: close record (approved)') (recommended)
B. start anyway
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via prose at 2026-10-29T10:33:57Z
