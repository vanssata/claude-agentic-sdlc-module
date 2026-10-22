# Questions — T-2026-10-21-001
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## G1. Approve T-2026-10-21-001 for implementation? (gate: human_approval)
asked: 2026-10-21T14:30:19Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via terminal at 2026-10-22T08:12:53Z

## Q1. R1 allows clean lines HEAD denied with WHY_WORK_CAP because one segment's realpath hit E2BIG (cwd 1524 chars, rm of 1500 files: HEAD deny 0.52 s, R1 allow 2.2 s). Accept this change?
asked: 2026-10-22T08:44:02Z · stage: human_approval
context: hooks/ai-path-guard.sh:728-747; .ai/project/known-risks.md:152; review-report.md HIGH-2
A. Accept: every candidate is now checked; correct known-risks.md:152 with the measurements and pin the allow with a test (recommended)
B. Regression: restore HEAD's outcome, a segment whose candidates pass ARG_MAX is denied by the work cap
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-22T08:57:08Z

## Q2. R2 re-review: HIGH-1 residual — one later segment slow to parse (quote-strip :876-877, ~0.27 s per 4 KB operand of ""x2047) delays an early deny: HEAD deny 0.29 s control-file reason, R2 deny 6.0 s WHY_WORK_CAP. Decision stays deny. A third remediation round needs you. How to proceed?
asked: 2026-10-22T09:26:21Z · stage: implementation
context: hooks/ai-path-guard.sh:829,876-877; review-report.md pass 3
A. Accept the residual: record it in known-risks (deny stays deny; only reason and latency change; root cause the quadratic quote strip, older than this task, its own T4 task) and go to approval (recommended)
B. Third round R3, opened by you in your terminal: flush the batch before parsing any segment over 4 KB and pin the 123 KB input; then suite, e2e and one more scoped re-review
X. Other — answer as `X: <text>`
[Answer]: X: Затвори HIGH-1 напълно — by ikakarov via prose at 2026-10-22T09:30:29Z

## Q3. R3 re-review: HIGH-1 open in a further shape — a later segment with many candidates under a long cwd (rm/mv x5000-5300, cwd 1.5-3.3 KB): HEAD deny 0.11 s control-file reason, R3 5.4-6.0 s WHY_WORK_CAP. Decision stays deny. A fourth round needs you. How to proceed?
asked: 2026-10-22T10:10:16Z · stage: implementation
context: hooks/ai-path-guard.sh:775,841,914; review-report.md pass 4
A. Round R4, opened by you: before a later segment's candidates are built, check the batch when an upper bound of their absolute-path bytes would take it past 32 KB; compute the cwd prefix once. An earlier deny then waits for at most 32 KB of later text and about one chunk; the residual is recorded (recommended)
B. Accept the residual: record it in known-risks and go to approval
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-22T10:10:38Z

## Q4. R4 re-review: HIGH-1 closed (pass-4 shapes 0.12-0.21 s, control-file reason; no further shape found). Open: fail-closed clock margin - the estimate costs ~3.8 us per mover segment with no candidates; rm -f; x90000 (540 KB): HEAD allow 4.65 s, R4 1/6 work-cap deny (R3 already 1/3 at x95000). How to proceed?
asked: 2026-10-22T10:52:36Z · stage: implementation
context: hooks/ai-path-guard.sh:897-904; review-report.md pass 5
A. Accept: deny side only, on lines of ~540 KB of operandless mover segments; record it in known-risks and go to approval (recommended)
B. Round R5, opened by you: run the estimate only when the segment has sources and the batch holds a segment; then suite, e2e and one more scoped re-review
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-22T10:53:38Z

## G2. Approve T-2026-10-21-001 for implementation? (gate: human_approval)
asked: 2026-10-22T10:54:35Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via terminal at 2026-10-22T10:54:46Z
