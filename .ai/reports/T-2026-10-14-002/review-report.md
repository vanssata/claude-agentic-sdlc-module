# Review — T-2026-10-14-002 (ai-reviewer, BALANCED, model sonnet)

Inherited (ledger, not re-derived): suite/e2e green, diff 7 files/159 lines, T2, duplicates 0, manager probe rows. Open sensor row: traceability (1 step names no test).

## FINDINGS
- [MEDIUM] `skills/ai-init/scaffold-ai.sh:103` still looks only for the current marker (`grep -qsF '<!-- claude-agentic:start -->'`). On an AGENTS.md/CLAUDE.md that carries a legacy Codex-agentic pair, /ai-init appends a second block - the exact doubling this task removes elsewhere. The goal says "every managed-block lookup"; this one is outside the 7 files and is not recorded as a residual in known-risks. Document it (or SCOPE_CHANGE_REQUIRED); do not fix here.
- [LOW] `skills/project-update/update.py:1110-1116` - block_of now returns a legacy block (it returned None before), so a pristine legacy block over the project budget is compared verbatim with the shipped bytes. The markers differ, so the hint says "it was edited here, so the plugin will not rewrite it: trimming it is yours". That is false: --apply renames and rewrites it. Needs current_markers on the block before the compare. Only fires when the block exceeds the budget.
- [LOW] `install.sh:157-163` vs `install.sh:622`. `block_size` takes the earliest of either spelling by regex alternation; find_block and `managed_block` prefer the current pair. With a legacy pair above a current pair, block_size measures the legacy one while managed_block updates the current one (reproduced with the regex on a two-pair file). Display only.
- [LOW] `install.sh:157-163` - behaviour change for the CURRENT pair: the old code sliced `end + 26`, but the end marker is 27 chars, so it dropped the final `>`. The new match includes it, so the printed "managed block N B" is 1 B larger than before. It is now correct (matches `render_instructions measure`) but nobody asked for it, and no test pins the number.
- [LOW] `install.sh:812` - the "routing rules outside the managed block" warning still strips only the current pair, so legacy-pair text is scanned as "outside". Warning only; same class as the scaffold gap.
- [INFO] Same residuals as the ledger: a second legacy pair, or a pair whose two markers differ in case, stays in place.

## EXAMINED AND CLEAN
- find_block `end_marker` derivation: `start.rfind(colon)+1` gives "start -->"/"end -->", so ":start -->" becomes ":end -->". It is correct for str and bytes. Run on CRLF bytes, non-ASCII str, legacy end-before-start (the search starts after the start match), reversed current pair (empty slice, same as old block_of).
- Current-pair path in block_of/find_block is the old logic (find both, half a pair gives None, no order check): same outcome for measure, adopt budget_offenders, adopt 705/721, update 1110/1560.
- update.py: `find_block = render_instructions.find_block` is bytes-in/bytes-out; the callers at 419/884-892 keep bytes markers and `START.encode()` compare. `import render_instructions` precedes use (line 56).
- adopt.Candidate: found[2]/found[3] are str markers; the line scan and `current_markers` compare are consistent. For the current pair current_markers is a no-op, so `edited` is unchanged. `text.replace(block, shipped)` (adopt.py:733) uses the verbatim slice, so legacy replacement works.
- install.sh heredoc: the `python3 - <<'PY'` heredoc is quoted, so `(?P=name)` is safe. `block_size` is inside `python3 -c '...'` with no single quote and `\1` intact. The managed_block guard `start not in text and end not in text` matches find_block's half-pair rule.
- Tests: `fail` always returns 0 when given a second arg, so the `&& fail "x" "$out" || pass` chain in test-project-update.sh does not double-count; the new asserts are not tautological (they check the output, the marker count and the note text). No test weakened or skipped.

## VERDICT
verdict: passed
scope_assessment: stayed inside the 7 planned files; the only unrequested behaviour change is the block_size +1 B correction. The scaffold-ai.sh gap should be logged as a residual.
