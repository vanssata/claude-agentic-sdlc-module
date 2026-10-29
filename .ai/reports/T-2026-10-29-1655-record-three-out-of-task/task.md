# T-2026-10-29-1655-record-three-out-of-task — Record three out-of-task risks from T-2026-10-28-2221; correct the G4 cause

feature · guarded · started 2026-10-29T16:55:34Z · claude

## Weight

```
scope          2  .ai/project/known-risks.md referenced from 192 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  no payment, auth or secret path (declared)
novelty        0  memory risk add and a three-line text fix, both done before (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T16:55:34Z — /rr-build-all ~/.claude/plans/known-risks-from-T-2026-10-28-2221.md

## Plan

files: .ai/project/known-risks.md, docs/sdlc/specs/direct-mode-diet.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/61ed0a26-a5da-4b21-85df-9b09f56c3e93/scratchpad/review-1.md
tests: none
- s1 · .ai/project/known-risks.md · no tests · done
- s2 · docs/sdlc/specs/direct-mode-diet.md · no tests · done
amended 2026-10-29T17:18:23Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/61ed0a26-a5da-4b21-85df-9b09f56c3e93/scratchpad/review-1.md — the review report holds backticks and .ai/reports/ paths beside python3, which the interpreter tripwire refuses on a heredoc; the report goes to state.py review from this file

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. Risk 3 (the guard false deny) is refused by that same guard: its text holds a literal dollar-paren next to an interpreter call. How is it recorded?
asked: 2026-10-29T16:56:50Z · stage: implementation
A. you run the command from the chat in your own terminal, text unchanged (recommended)
B. the agent records it with the substitution described in words, no literal dollar-paren
C. leave risk 3 out of known-risks.md
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-29T16:58:21Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 1dec20a1a | .ai/state/logs/T-2026-10-29-1655-record-three-out-of-task/suite-1.log | no |
| 2 | suite | 1 | 1dec20a1a | .ai/state/logs/T-2026-10-29-1655-record-three-out-of-task/suite-2.log | no |
| 3 | suite | 0 | 4727f9555 | .ai/state/logs/T-2026-10-29-1655-record-three-out-of-task/suite-3.log | no |
| 4 | e2e | 0 | 4727f9555 | .ai/state/logs/T-2026-10-29-1655-record-three-out-of-task/e2e-4.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS

- [LOW] L1 Second new entry's `Where` has broken backtick spans — `.ai/project/known-risks.md:776`  in_scope: yes
  why it matters: the line renders as `` `…events.jsonl (last: gate_approved`, `2026-10-28T20:02:36Z); .ai/reports/…-012/events.jsonl (last: handoff_written after gate_requested`, `21:40:51Z)` `` — code spans close mid-prose, so the timestamps and the second path render as wrong text; every other `Where` is a clean path span. Caused by the shell quoting of `--where`. Facts correct; only rendering wrong.
  suggested direction: two path spans, last events in prose outside them.

- [LOW] L2 `Label` of two new entries omits the labels used in the body — `.ai/project/known-risks.md:~782` and `:~795`  in_scope: yes
  why it matters: the "T-2026-10-28-010 and -012…" entry says `Label: KNOWN FACT` but its body also holds an UNKNOWN (how the state was cleared); the guard entry says `Label: KNOWN FACT` but holds an INFERENCE (the cause). The flaky-test entry above uses `KNOWN FACT (…), INFERENCE (cause)`. The body text labels each claim honestly; only the summary line understates.
  suggested direction: `KNOWN FACT (journals), UNKNOWN (cause)` and `KNOWN FACT (deny), INFERENCE (cause)`.

- [LOW] L3 "Related to the entries at :210 and :581" cites heading line numbers — `.ai/project/known-risks.md:~796`  in_scope: yes
  why it matters: both are correct today (`:210` "Interpreter tripwire residuals after M2/L4", `:581` "Path guard after R22: what it no longer refuses, accepted"), and appending kept them stable, but any edit above them shifts them. `:581` is also only loosely related (what the path guard no longer refuses, not the tripwire's false denies); `:210` is the apt one.
  suggested direction: cite the heading titles instead of line numbers.

- [LOW] L4 The `->` argument rests on text not in the repository — `docs/sdlc/specs/direct-mode-diet.md` G4 INFERENCE and the guard entry  in_scope: yes
  why it matters: the text says `->` cannot match `WRITE_REDIR_RE` because "a space follows `",`". But `WRITE_REDIR_RE` (`hooks/guard/paths.py:168`) is `>[>|]?[[:space:]]*['"]?[^…]*\.ai/(state|reports)/` — it tolerates spaces after `>`; the claim only holds if no `.ai/state/` or `.ai/reports/` path follows in the same non-space run. The refused command itself is not recorded, so the reader cannot check it. It is labelled INFERENCE "from the regexes, not run", so honest — but weaker than "cannot match" reads.
  suggested direction: quote the refused command, or soften "cannot match" to "does not match in that command".

- [INFO] I1 The second new entry states "UNKNOWN how the state was cleared" — `.ai/project/known-risks.md:~778`  in_scope: yes
  `.ai/reports/T-2026-10-28-010/task.md` `## Verdict` (:~126) records "close: open — the human approves in their own terminal, then 'state.py close' again", and commit 520e065 ("close record (approved)") added the `gate_approved` event — a concrete lead that the final `state.py close` was never re-run after approval. Not a contradiction; a starting point for the investigation.

## EXAMINED AND CLEAN
- `hooks/guard/paths.py` cites: `WRITE_WORD_RE` :160-161 (contains `` ` `` and `\$\(`, so `$(` counts as a write indicator); `WRITE_REDIR_RE` :168; `interpreter_text` :1217, called as `self.interpreter_text(cmd)` at :1264 with the whole command after the segment split — "scans the whole line" holds. :1229-1235 covers `pscan` through the condition; `scan` (:1228), `if is_interp:` (:1227) and the `raise` (:1236) fall just outside — trivial imprecision. The gate is `CONTROL_TEXT_RE` (:147, `.ai/state/` or `.ai/reports/`) + `INTERP_RE`, matching "read-only one-liner on `.ai/reports/`".
- `usage-report.py:693` is exactly `end = max(c …) if any(closed) else dt.datetime.now(dt.timezone.utc)` — matches the "no `task_closed` → now" claim.
- The two journals: -010 ends with `gate_approved` at 2026-10-28T20:02:36.348Z; -012 ends with `gate_requested` 21:40:51.609Z then `handoff_written` (detail `close`) 21:40:51.610Z; neither holds `task_closed` (count 0 both). Correct.
- Occurrence counts in the flaky entry: `/usr/bin/grep -l 'FAIL: test_two_exports_at_once'` over `.ai/state/logs/*/suite-*.log` returns exactly five logs: 0852 suite-1, 1035 suite-1, 1145 suite-3, 1655 suite-1, 1655 suite-2 — matches; that entry's `Label` line untouched.
- Line shift: the known-risks.md diff is one same-length-line edit at :748 plus a pure append at EOF (`@@ -745,7 +745,7 @@`); no existing line number moved; the spec's `:63…:589` cites are safe.
- Spec scope: `git diff HEAD` on direct-mode-diet.md is a single hunk inside the G4 bullet; the KNOWN FACT lines about the tests (:704-722, :799) unchanged; matches plan s2.
- Structure: new entries follow the same `##` heading / blank / Found·Where·What could go wrong·How likely·Suggested fix·Status·Label fields as the neighbouring C5 entry; file ends with a newline; `git status` shows only the two task files plus the task's report directory.
- KNOWN FACT vs INFERENCE: within bodies every claim is labelled honestly; the guard entry and the spec both say "from the regexes, not run"; the second entry flags its cause UNKNOWN.

## VERDICT
verdict: pass
scope_assessment: the change stayed inside the approved plan — only the two named files changed, the spec edit is limited to G4, new entries appended, the flaky-entry edit only adds occurrence counts that match the logs. Only LOW/INFO rows open; none changes the verdict.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +31 −1 | Edit |
| docs/sdlc/specs/direct-mode-diet.md | +13 −7 | Edit |

+44 −8 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 4727f9555 (run 3) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 6 · suite runs: 3 · review passes: 1
