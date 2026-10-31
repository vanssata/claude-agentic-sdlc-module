# T-2026-10-31-0010-dialog-43ae-8fec — Dialog cluster task 1 — 43ae-I4 + 8fec

bugfix · guarded · started 2026-10-31T00:10:54Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in skills/ai-task/state.py
reversibility  0  git revert returns everything
domain         0  no approval route or policy changes (declared)
novelty        0  bugfix in existing code paths (declared)
coverage       0  2 of 2 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-31T00:10:54Z — /rr-build-all ~/.claude/plans/dialog-cluster-decisions.md items 4-I4 and 2

## Plan

files: skills/ai-task/state.py, hooks/guard/dialog.py, tests/test_ai_task_state.py, tests/test_dialog_gate.py
tests: tests/test_ai_task_state.py, tests/test_dialog_gate.py
- s1 · skills/ai-task/state.py, tests/test_ai_task_state.py · tests/test_ai_task_state.py · done
- s2 · skills/ai-task/state.py, hooks/guard/dialog.py, tests/test_dialog_gate.py · tests/test_dialog_gate.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 7d59334df | .ai/state/logs/T-2026-10-31-0010-dialog-43ae-8fec/suite-1.log | no |
| 2 | e2e | 0 | 7d59334df | .ai/state/logs/T-2026-10-31-0010-dialog-43ae-8fec/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
No BLOCKER, no HIGH. Mode guarded, BALANCED. Did not re-run the suite (inherited green suite-1.log, 1116 tests OK); did not check out the pre-fix tree — "fails before" claims are from reading the code.

- [MEDIUM] M1 Lost end-to-end coverage of the "duplicate question text -> decline why=ambiguous" path (`tests/test_dialog_gate.py:478`)  in_scope: yes
  The old `test_duplicate_question_text_is_ambiguous` ran `dialog.record` and asserted `[("offer", None), ("decline", "ambiguous")]`. The rewrite is legitimate for its original premise (a split no longer yields shared text), but the new test drives the recorder with a hand-made `same` payload whose texts match no offered question, so `record()` returns no lines at all and the test only asserts "no pick". It never reaches the `texts.count(...) > 1` -> `[""]` -> decline path in `record()`. The `adapt_response` unit assertion `[[""],[""]]` is kept. `grep ambiguous tests/test_dialog_gate.py` shows only :141, :411, :478; none pins the duplicate-text decline through `record()`. The path is still reachable: two open decisions with the same question text and the same header and labels collide in `by_key`; nothing tests that it declines instead of mis-attributing.
  suggested direction: a case with two distinct decisions sharing question text (not a split), asserting the `offer` + `decline ambiguous` lines; or keep the old assertion with a payload that matches an offered key.

- [LOW] L1 The new chmod 0444 tests assume a non-root user (`tests/test_ai_task_state.py` `read_only_ledger`, ~2138-2159)  in_scope: yes
  As root (uid 0), O_WRONLY on a 0444 file succeeds: the settle line is written, the decision is pruned, the tests fail falsely red. This session is uid 1000, so it passes here. No `geteuid` skip or `os.access` precondition; repo precedent without a root skip exists (`test_memory_sync.py:189`), but root CI containers would break it. On a non-root tree both tests fail pre-fix (suppress(OSError) swallowed the PermissionError and the decision was removed).
  suggested direction: `skipIf(os.geteuid() == 0)`, or assert `not os.access(path, os.W_OK)` first.

- [LOW] L2 The two `part_question` copies are checked for equality in only one case (`hooks/guard/dialog.py:201-210` vs `skills/ai-task/state.py:2657`)  in_scope: yes
  The gate (`hooks/guard/decision.py:67-73`) compares the model's tool input to `dialog.dialog_payload`, built from `offered()`; the model's text comes from `state.py decision show`, built by state's `dialog_payload`. Any divergence makes the gate deny a correct payload (DECISION_PENDING loop) rather than fail quietly. No divergence found in the code: same suffix format, cut and n<2 rule; dialog.py adds `or ""` for a missing question (harmless); n and i come from the same per-decision decision_parts / dialog_questions logic; the [:DECISIONS_MAX] slice is applied after parts are built and open_decision caps the total at 4, so the slice cannot cut part i of n. Only `test_split_suffix_keeps_question_within_max` compares the two copies, on one long-question Claude case; nothing checks Codex or a short question. Codex split questions also get the suffix (not needed for id-keyed matching; harmless and consistent, and consistency matters because the gate compares text).
  suggested direction: parametrise the equality assert over short, long, empty and codex.

- [LOW] L3 A decision that cannot be settled now stays open (`skills/ai-task/state.py:2749-2757`)  in_scope: yes (a notice, not a defect)
  With an unwritable ledger, prune_decisions retries on every sync_dialog run — the intended fix (43ae-I4); no loop, one failed append per run. It keeps occupying one of the DECISIONS_MAX slots, so `decision open` can refuse for lack of room until the ledger is writable; `decision settle` cannot clear it either (also needs the ledger). Gate unaffected while the switch is off (effective_switch false → allow); switch later on → the kept decision is pending again, arguably correct. The all-picks-used branch is consistent with `pending()` in dialog.py:420, which already excludes such a decision. No change needed beyond documenting it.

## EXAMINED AND CLEAN
- settle_written vs old `contextlib.suppress(OSError), ledger_lock(root)`: same exception class around the same lock-and-append; ledger_lock timeout, makedirs failure, line over LEDGER_LINE_MAX, short write, open failure are all OSError → False; non-OSError still propagates; lock wait unchanged; settle entry dicts byte-identical in both branches.
- settled / already-settled branch untouched, data["open"] rewriting unchanged; keep.remove only on success; the len(keep) != len(...) write unchanged.
- Unsplit payloads: part_question returns the question as-is for n<2 in both copies; Codex ids and labels unchanged; goldens and Codex tests green in the log.
- Truncation: QUESTION_MAX - len(suffix) keeps the total ≤ 1200; boundary tested; unsplit long question untouched.
- QUESTION_MAX = 1200 duplicated in dialog.py matches state.py:2307; drift caught by the test's equality assert.
- Scope: four files, no unrelated edits; adapt_response docstring updated; no docs/consumers reference the old shared text (grep).
- `test_split_multiselect_parts_are_recorded_per_part` pins 8fec end to end: two picks, options 2 and 3, no decline.

## VERDICT
scope_assessment: inside the approved task and files; nothing about pruning changed beyond gating removal on a successful settle write.
VERDICT: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| hooks/guard/dialog.py | +15 −2 | Edit |
| skills/ai-task/state.py | +27 −9 | Edit |
| tests/test_ai_task_state.py | +23 −0 | Edit |
| tests/test_dialog_gate.py | +45 −7 | Edit |

+110 −18 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on 7d59334df (run 1) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
