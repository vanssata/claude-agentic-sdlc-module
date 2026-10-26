# Questions — T-2026-10-26-003
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Deleting ai/agents/{context,implementer,planner,release,risk,security,tester}.md breaks migration 0006: require_shared refuses (exit 2) when a project's unedited copy has no fallback in ai/. How should s2 proceed?
asked: 2026-10-26T10:45:58Z · stage: implementation
context: skills/project-update/update.py:458-472, skills/project-update/migrations/0006_shared_files.py:136-154
A. Keep the seven role files in ai/ unchanged (dead text, nothing names them); s2 only adds reviewer.md §Security; record their deletion in known-risks.md for 2.6/3.x, with an update.py rule for retired shared files (recommended)
B. Delete them and add a RETIRED set to skills/project-update/update.py: require_shared skips a retired path, so 0006 drops the unedited copy with nothing to fall back to; plus a test-project-update case (widens scope into the migration engine)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-26T13:11:36Z

## G1. Approve T-2026-10-26-003 for implementation? (gate: human_approval)
asked: 2026-10-26T13:41:14Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via terminal at 2026-10-26T17:43:18Z
