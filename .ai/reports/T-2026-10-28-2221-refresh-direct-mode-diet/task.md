# T-2026-10-28-2221-refresh-direct-mode-diet — Refresh direct-mode-diet spec against today's measured numbers

feature · guarded · started 2026-10-28T22:21:03Z · claude

## Weight

```
scope          2  docs/sdlc/specs/direct-mode-diet.md referenced from 33 files
behaviour      1  keyword 'workflow' in docs/sdlc/specs/direct-mode-diet.md
reversibility  0  git revert returns everything
domain         0  developer-tool spec; no money, identity or personal data (declared)
novelty        0  same kind of edit as earlier spec status refreshes; measurement reads existing events.jsonl (dec
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: docs/sdlc/specs/direct-mode-diet.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/9a2baabc-5c6b-4dee-a09a-da19c039571c/scratchpad/diet-measure.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/9a2baabc-5c6b-4dee-a09a-da19c039571c/scratchpad/review-1.md
tests: none
- s1 · docs/sdlc/specs/direct-mode-diet.md · no tests · done
- s2 · docs/sdlc/specs/direct-mode-diet.md · no tests · done · after s1
amended 2026-10-28T22:24:03Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/9a2baabc-5c6b-4dee-a09a-da19c039571c/scratchpad/diet-measure.py — s1 measurement script, read-only towards the repo; the plan places it in the session scratchpad so every number in the new section can be re-run
amended 2026-10-28T22:45:54Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/9a2baabc-5c6b-4dee-a09a-da19c039571c/scratchpad/review-1.md — the reviewer's report is passed to state.py review from a file: the guard refuses the 4850-character heredoc and names this way out

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | ce298b9c6 | .ai/state/logs/T-2026-10-28-2221-refresh-direct-mode-diet/suite-1.log | no |
| 2 | e2e | 0 | ce298b9c6 | .ai/state/logs/T-2026-10-28-2221-refresh-direct-mode-diet/e2e-2.log | no |
| 3 | suite | 0 | 17f08154b | .ai/state/logs/T-2026-10-28-2221-refresh-direct-mode-diet/suite-3.log | no |
| 4 | e2e | 0 | 17f08154b | .ai/state/logs/T-2026-10-28-2221-refresh-direct-mode-diet/e2e-4.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 — docs/sdlc/specs/direct-mode-diet.md, G5 bullet ("the weight table put 1 of 27 tasks in light") — Wrong denominator. The 27 is the closed, non-abandoned after cohort, and it includes the 6 tier-surface tasks (T-2026-10-25-003 … -008). Those have W UNKNOWN in the script's per-task table and never went through the weight table. On the weight surface it is 1 of 21 closed tasks, or 1 of 26 counting the abandoned and unclosed ones. The "1 of 27" is a KNOWN FACT label on a mis-stated fraction. — in_scope: yes
- [MEDIUM] M2 — direct-mode-diet.md, Q1 closing note, last bullet — The INFERENCE rests on a false clause: "its subject names the closed HIGH-1". `git log -1 e393224` gives the subject "path guard: an earlier movers deny no longer waits for later segments' text, quotes or paths (known-risks)". Neither the subject nor the body contains "HIGH-1". The body says "remediations R2-R4 of the batched movers pass" and "Accepted (Q1 = A)/(Q4 = A)". "HIGH-1 closed" appears only in the journal's stage_started detail. The timing is right: the close is 10:55:27Z = 13:55:27 +0300, the commit is 13:55:37, so ten seconds. The inference may still hold through R2–R4 and the Q1/Q4 wording, but the stated basis is wrong. — in_scope: yes
- [MEDIUM] M3 — direct-mode-diet.md, "Where the time goes now", first bullet — "tokens follow the mode, not the size of the change" is labelled KNOWN FACT, but it is a correlation read off medians of n=11 against n=9. No correlation was computed. `+N −M lines` is a weak size proxy (it includes fixtures and generated files; the max is 10526). The 57 % (480.3M of 840.7M) includes T-2026-10-28-011's 131.9M, which the RISK bullet admits also contains part of -012. The 011 window overlaps -012, and the script prints that overlap. So 011's 6 denies are inflated the same way, and the Method text does not say so. All of these figures reproduce from the script (55.9/7.9 = 7.1, 188.2/840.7 = 22 %). The label and the claim are the problem, not the arithmetic. — in_scope: yes
- [MEDIUM] M4 — direct-mode-diet.md, G1 — "not met as written" and "the new labels put hook and skill changes no lower than before" overreach. G1's own text exempts changes that allow what was denied, change the approval path, or change install and migration. The script never classifies behaviour. The note itself says five of the eleven full tasks were raised by the behaviour-2 rule (`hooks/CLAUDE.md`, `skills/CLAUDE.md`), which is the exemption. The other six weight-table fulls are unexamined against it. The counts reproduce (24 = 1 T3 + 5 T4 + 6 full→full + 5 guarded→full + 7 guarded→guarded). The verdict needs the evidence label INFERENCE or UNKNOWN, with the exempt count stated. — in_scope: yes
- [LOW] L1 — direct-mode-diet.md, per-task table, rows "step runs 4 (16)" and "scope amendments … 38 in all" — The after medians over 27 include 6 tier-surface tasks that structurally journal 0 of both. The weight-surface medians are higher (guarded step 4, full step 8). The last "What the numbers do not show" bullet warns the rows "do not compare", but the table itself does not mark the median as diluted. — in_scope: yes
- [LOW] L2 — direct-mode-diet.md, G5, "made 19 journaled calls" — A call is counted as a distinct event timestamp, ms-resolution. The 7 notes sit in two same-second bursts (4 at 10:56:57, 3 at 11:23:49) and may each be one scripted invocation. The breakdown reconciles as 6 + 2 + 7 + 2 + start + close = 19, but 19 is an upper bound on calls, not a count. — in_scope: yes
- [LOW] L3 — direct-mode-diet.md, G6 and G4 — G6 "met" says seven known-risks entries are "accepted (2026-10-22…)". I confirmed the 7 literal matches at 63, 90, 165, 179, 186, 193, 207. But :63 is a section heading, and :90 and :165 read "fixed … residual accepted". `.ai/project/known-risks.md:210` ("Interpreter tripwire residuals after M2/L4") is still `Status: open`. `:581` (accepted 2026-10-27) supersedes parts of the path-guard entries after R22. G6 says nothing on either. G4 "met" sits beside this task's own refused read-only one-liner, which is a literal counterexample to G4's text. That is hedged as "pinned spellings, with a residual", so it is acceptable but borderline. — in_scope: yes
- [INFO] I1 — direct-mode-diet.md, "What the numbers do not show", first bullet, and the G4 scratchpad-Write and one-liner deny claims — These need `~/.claude/projects` transcripts and mtimes, and the live denies of this task. I could not check them inside the bounded inputs. The script reads the installed `~/.claude/skills/usage-report/usage-report.py`; `diff -q` shows it is identical to the repo copy. — in_scope: no

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| docs/sdlc/specs/direct-mode-diet.md | +235 −2 | Edit |

+235 −2 lines, 1 files

## Verdict

close: closed
facts: (a) green — suite green on 17f08154b (run 3) · (b) green — 1 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
