# T-2026-10-29-1724-t-1-safety-md-blocker — T.1 safety.md blocker sentence (redesign 2.H) and LOW L1-L4 of T-2026-10-29-1655

feature · guarded · started 2026-10-29T17:24:26Z · claude

## Weight

```
scope          2  .ai/policies/safety.md referenced from 147 files
behaviour      2  keyword 'workflow' in .ai/project/known-risks.md; hint +1
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  no code file declared
W 6 → guarded   hints behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T17:24:26Z — /rr-build-all: Т.1 and the LOW findings in one go, verify after all corrections

## Plan

files: .ai/policies/safety.md, docs/sdlc/plans/claude-agentic-redesign.md, .ai/project/known-risks.md, docs/sdlc/specs/direct-mode-diet.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-1.md
tests: none
- s1 · .ai/policies/safety.md, docs/sdlc/plans/claude-agentic-redesign.md · no tests · done
- s2 · .ai/project/known-risks.md, docs/sdlc/specs/direct-mode-diet.md · no tests · done
amended 2026-10-29T17:37:48Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/377a1cbf-20d9-4432-b414-11b12faadc56/scratchpad/review-1.md — review report goes to state.py review --report - from a file; heredoc of review text trips the guard

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 5d7d58bc4 | .ai/state/logs/T-2026-10-29-1724-t-1-safety-md-blocker/suite-1.log | no |
| 2 | suite | 0 | 5168e1a61 | .ai/state/logs/T-2026-10-29-1724-t-1-safety-md-blocker/suite-2.log | no |
| 3 | e2e | 0 | 5168e1a61 | .ai/state/logs/T-2026-10-29-1724-t-1-safety-md-blocker/e2e-3.log | no |
| 4 | suite | 0 | b74a58ed3 | .ai/state/logs/T-2026-10-29-1724-t-1-safety-md-blocker/suite-4.log | no |
| 5 | e2e | 0 | b74a58ed3 | .ai/state/logs/T-2026-10-29-1724-t-1-safety-md-blocker/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS

- [MEDIUM] M1 Plan's 2.H row still says the sentence is open, contradicting the status line just edited (`docs/sdlc/plans/claude-agentic-redesign.md:192-194`)  in_scope: yes
  why it matters: the diff changed only the status line (:13-14, "went in on 2026-10-29"). The 2.H row, ticked `[x]` 2026-10-29, still ends "Open: the `safety.md` sentence is not in `.ai/policies/safety.md:77-80` ("When in doubt") — the human's edit." That is now false, and a reader of the row gets the opposite of the status line. The goal said to update what "said that item was still open"; one of the two places was missed. The same row also carries the pre-change line cite :77-80, which is now :77-82.
  suggested direction: replace the "Open: …" sentence in the 2.H row with "the `safety.md` sentence went in on 2026-10-29 (T-2026-10-29-1724)".

- [LOW] L1 L4 fix: new wording "only when a path follows it in the same run of non-space characters" is itself slightly wrong (`.ai/project/known-risks.md:787`, `docs/sdlc/specs/direct-mode-diet.md:224-226`)  in_scope: yes
  why it matters: `WRITE_REDIR_RE` (`hooks/guard/paths.py:168`) is `>[>|]?[[:space:]]*['"]?[^[:space:]'"|;&<>]*\.ai/(state|reports)/`. The `[[:space:]]*` after `>` lets whitespace separate the `>` from the path, so `-> .ai/state/x` matches. The path need only be in the run that starts after the `>` and any spaces, not "the same run" as `->`. I tried to run a one-line check, but the guard refused my command because it contained `-> .ai/state/a`. That is consistent with the regex reading, though I could not get a clean regex run. The claim stays correctly hedged (INFERENCE, "not run"), and the direction is far better than "cannot match". The finding L4 is closed in substance, but the new text under-describes the match.
  suggested direction: say "when a `.ai/state/` or `.ai/reports/` path follows it (spaces after `>` are allowed) with no quote, space, `|`, `;`, `&`, `<` or `>` in between".

- [LOW] L2 New safety.md sentence is appended with no blank line, to the paragraph whose first words are "Stop and ask." (`.ai/policies/safety.md:79-82`)  in_scope: yes
  why it matters: markdown renders it as one paragraph: "Stop and ask. An agent that pauses … incident. Doubt on reversibility or domain is a blocker; other doubt is written to `task.md` and the work continues." The unqualified "Stop and ask" still comes first, and the narrowing reads as a footnote to it. A reader taking the first sentence literally gets the old rule. It does not contradict the rest: `skills/rr-build/SKILL.md:143-147` lists the real blockers as a guard refusal, a re-score to reversibility or domain 2, and a false plan assumption. The new sentence is the policy-side counterpart, and "blocker" in `security.md:33` is a finding severity, a different sense. The text matches the plan's quoted wording (`redesign.md:189-190`) apart from the capital D and the period. Putting it on its own line or paragraph, or rewording "Stop and ask" to "On a blocker, stop and ask", would remove the ambiguity. Rewording is a human policy choice, so I note it only.
  suggested direction: blank line before the new sentence, at minimum.

- [INFO] I1 Shipped template not updated (`skills/ai-init/templates/.ai/policies/safety.md:68`)  in_scope: yes
  why it matters: the template's "When in doubt" lacks the sentence, so new projects keep "Stop and ask" unqualified while this repository has the narrowed rule. The plan (2.H) scopes this to "this repository", so this is not a defect. It is a drift to record if it is not already a known risk.

- [INFO] I2 Stale cross-references to the old state (`docs/sdlc/specs/claude-agentic-redesign.md:729,785,936`)  in_scope: yes
  why it matters: the spec describes "the residual conflict FC-A3" and says `safety.md` "gains one human-written sentence … in 2.H". Both are history of a closed task, and the sentence is now agent-written on the developer's instruction. The plan's "on the developer's instruction" wording makes the provenance honest. Nothing to fix.

## EXAMINED AND CLEAN
- L1 (broken backtick spans, `known-risks.md:776`): now two clean path spans with the last-event details in prose outside them. Closed.
- L2 (labels): `Label: KNOWN FACT (journals), UNKNOWN (cause)` and `KNOWN FACT (deny), INFERENCE (cause)` match the bodies and the flaky entry's style. Closed.
- L3 (line-number cross-refs): "Interpreter tripwire residuals after M2/L4" (`known-risks.md:210`) and "Path guard after R22: what it no longer refuses, accepted" (:581) both exist as headings, verbatim. The clause "covers what the guard allows, not its false denies" is accurate for :581-589 (the Status text there is about what the guard no longer refuses). Closed.
- L4: the old overstated "cannot match" is gone from both places. The new text matches `paths.py:168` except for the nuance in L1 above. It marks the unknown (the command was not kept) as UNKNOWN. Both files are consistent with each other. The spec still cites :160-161 and :1229-1235 (unchanged by this diff).
- Flaky-test entry (`known-risks.md:748`): `suite-1.log` has `FAIL: test_two_exports_at_once_serialise_on_the_lock` and `AssertionError: 'T-2026-10-29-1728-beta' not found in []`, `FAILED (failures=1, skipped=5)`. The new occurrence and the quoted string match. Earlier counts were inherited from the previous review.
- Verify logs: suite-2.log ends "OK" and e2e-3.log is green (one `tail` call errored on its syntax, so only suite-2 and e2e-3 were read in a second pass). The task.md table lists suite-1 exit 1 (the flaky test), suite-2 exit 0, e2e-3 exit 0.
- Contradiction grep ("When in doubt", "blocker", "real blocker") across `.ai/policies`, the constitution and the rr-* skills: no contradicting text found. `rr-build` §5 and `rr-plan:88` are consistent with the new sentence (the old "stop and ask" survives only as the parent sentence, see L2).
- Scope: `git diff HEAD --stat` shows exactly the 4 declared files; there is no code and no test change. The diff is 13+/9-. known-risks edits are limited to the three entries named in the brief plus the flaky-entry occurrence list, and the spec edit is limited to the G4 bullet. No scope creep. Markdown in known-risks and the spec renders; no line-number shift above :776 (the L1/L2/L4 edits are same-line or append-only, so the spec's cites into known-risks stay valid; the spec cites known-risks by heading, not number, for the changed entries).

## VERDICT
verdict: pass_with_findings
scope_assessment: the change stayed inside the approved plan: the four declared files, docs only, with the 2.H sentence and L1-L4 as asked. M1 (a missed second place in the plan that still says the item is open) is the one fix that should be made before close. L1 and L2 are optional polish.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/policies/safety.md | +1 −0 | Edit |
| .ai/project/known-risks.md | +5 −5 | Edit |
| docs/sdlc/plans/claude-agentic-redesign.md | +4 −4 | Edit |
| docs/sdlc/specs/direct-mode-diet.md | +5 −2 | Edit |

+15 −11 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on b74a58ed3 (run 4) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 3 · review passes: 1
