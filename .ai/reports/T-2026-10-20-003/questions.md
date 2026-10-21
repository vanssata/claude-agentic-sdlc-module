# Questions — T-2026-10-20-003
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Review pass 4 passed with 2 MEDIUM + 1 LOW (BLOCKER 5 untested; comment/known-risks still claim quoted blanks and the old follow-on cut; known-risks line refs off by one). How are they handled?
asked: 2026-10-21T10:15:23Z · stage: implementation
context: .ai/reports/T-2026-10-20-003/review-report.md (Pass 4)
A. You write R4 (timed test for the ' sh 2>\'' padding + a multibyte variant, a pin that bash 2>'/tmp/a b' -c stays allowed, comment :413/:421/:440 and known-risks Status/Where wording and line refs, one line in CLAUDE.md about pinning every regex-timing blocker with a timed test); the agent verifies: own test file, step-done R4, suite, e2e; no re-review (no BLOCKER fixed) (recommended)
B. The agent writes R4 (same content, tests and text only, no regex change), then verifies the same way; CLAUDE.md is added to R4's allowed files
C. Leave them open: list the three findings in the release summary and go to human approval as is
X. Other — answer as `X: <text>`
[Answer]: B — by ikakarov via prose at 2026-10-21T10:27:17Z

## G1. Approve T-2026-10-20-003 for implementation? (gate: human_approval)
asked: 2026-10-21T10:40:46Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via terminal at 2026-10-21T10:42:06Z
