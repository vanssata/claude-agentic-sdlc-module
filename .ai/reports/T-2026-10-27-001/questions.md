# Questions — T-2026-10-27-001
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. CI matrix 3.10-3.13: on Python 3.10 the existing suite is red (test-install-dry-run.sh, test-usage-report.sh, test-instruction-budget.sh, test_imports: tomllib is 3.11+); none of the new twins fail. How should 3.10 enter the matrix?
asked: 2026-10-27T07:38:13Z · stage: implementation
context: .github/workflows/tests.yml:14; scripts/merge-codex-config.py:31; scripts/render-codex-agents.py:165
A. Matrix 3.10-3.13 as asked; 3.10 job red until a separate task fixes those suites; record in known-risks.md
B. Matrix 3.11-3.13 now; record the 3.10 gap in known-risks.md; 3.10 joins in the task that fixes it (recommended)
C. Matrix 3.10-3.13 with 3.10 as continue-on-error (reports, does not block); record in known-risks.md
X. Other — answer as `X: <text>`
[Answer]: B — by vanssa via prose at 2026-10-27T07:40:13Z
