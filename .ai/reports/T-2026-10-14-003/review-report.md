# Review T-2026-10-14-003 (adversarial, T2 bugfix)

Reviewed against the repo's own `.ai/` contract. Sensor rows and the manager probe table in review-ledger.md are inherited, not re-derived.

## FINDINGS

- [LOW] The third scaffold assertion is named "the file is left as it was" but checks only that the legacy start marker and the line `keep this.` are still there (`tests/test-scaffold-idempotency.sh:153-154`).
  Failing input: a scaffold that rewrites the instruction file but keeps those two strings, such as one that renames the markers or drops other lines, passes this check. It also passes before the fix, so it pins nothing new. The "one block" and "not reported as appended" assertions carry the fix; this one overstates its claim.
  Direction: compare a sha256 of the file before and after, as the same file already does at lines 139-140.

- [LOW] The new either-spelling test counts any `<!-- [Cc]odex-agentic:start -->` anywhere in the file as the block (`skills/ai-init/scaffold-ai.sh:105`).
  Failing input: an AGENTS.md or CLAUDE.md that only mentions the legacy start marker, as a code example or half a pair. The scaffold appends nothing. I ran `/project-update --apply` on such a file (`# mine`, a lone `<!-- Codex-agentic:start -->` and a stray line). `update.py` `find_block` requires both markers, so it appended a current block and left the stray marker.
  Impact: this is the same end state `/ai-init` gave before the change, and the old check did the same thing for a lone current start marker. It is not a regression, and the manager already listed the half-pair row. It is a cosmetic mismatch between "scaffold looks for the start marker" and "update looks for the pair", and it is accepted and unchanged in shape.
  Direction: none needed. Optionally add a line to known-risks.

- [INFO] Traceability is red because the inline step named no test, and the lint sensor is unavailable. Both are inherited from the ledger. The tests do exist and I ran them (see below). I recommend no action beyond recording it.

No BLOCKER, HIGH or MEDIUM.

## EXAMINED AND CLEAN

1. **Grep equivalence and portability** (`scaffold-ai.sh:105`).
   - `-E` with the alternation `(claude-agentic|[Cc]odex-agentic)` is a plain ERE with no GNU-only syntax. `<`, `!`, `-` and `>` are literals in ERE. It also matched under `busybox grep -E`.
   - For a current pair it is the same literal match as the old `-F` check.
   - `<!-- claude-agentic:rule:foo:start -->` does not match (run: `nomatch`), because the name must be followed directly by `:start -->`.
   - A CRLF line matches.
   - The regex is character-for-character the one in `render_instructions.LEGACY_MARKER_RE`, so the scaffold and `update.py` agree on the spelling set (`Codex-agentic`, `codex-agentic`).

2. **Leaving the legacy file untouched** is the right behaviour.
   - The scaffold's contract is append-only, and rewriting an existing file would break it.
   - `install.sh` `managed_block` is a different tool, one whose job is to update the block.
   - I ran the real chain: the scaffold on a legacy AGENTS.md changed nothing in it, then `update.py` planned "managed block kept (legacy Codex-agentic markers renamed)", and `--apply` left exactly 1 current pair and 0 legacy markers.
   - The scaffold never reports the file as touched in this case.

3. **Residual (d) is not reproducible.** I traced every path.
   - `budget_hints` runs after `block_update` and reads through `plan.read`, which prefers `plan.final`.
   - `block_update` has these paths:
     - File absent: it creates a current-marker file.
     - No block found: it appends a current block.
     - Legacy with `ours == tpl`: it adds an update with current markers.
     - Replaced, merged, or kept as edited: each adds an update with `text[:s] + new_block + text[e:]`, and `new_block` comes from `tpl` or from `current_markers(...)`.
     - Conflict: it is reachable only when `legacy` is false, because the `new_block is None and legacy` branch comes first. The file then has current markers on disk.
     - File in `plan.removed`: `plan.read` returns None, so the hint skips it.
   - A half pair or a mismatched-spelling pair makes `find_block` return None in both places, so there is no block and no hint.
   - `block_of` and `block_update` share `render_instructions.find_block`, so they cannot disagree about which block is first. The only difference is bytes versus str decoded with "replace", which affects only invalid UTF-8 offsets and not which pair is picked.
   - The known-risks text for (d) is accurate.

4. **Mutation: the budget-hint test is a real pin, not a tautology.**
   - It passed before any code change, which is expected for a no-code finding.
   - In a scratch copy (`$SP/repo`, not the working tree) I changed `budget_hints` to read the file from disk instead of `plan.read`.
   - The test then went red on "the hint blames the project for the plugin's own block". It guards the dependency the (d) closure relies on.
   - The edited-block half also passes: `sed -i '3a'` inserts after the start marker on line 3, the block is no longer the shipped bytes, and the hint says "trimming it is yours".

5. **The scaffold test fails without the fix.** With HEAD's `scaffold-ai.sh` in the scratch copy: `60 passed, 4 failed`, the "one block" and "reported as appended" assertions for both spellings. With the fix, 64 passed, 0 failed.

6. **No state leaks.**
   - `tests/test-scaffold-idempotency.sh` already exports `CLAUDE_AGENTIC_TEMPLATES` for the whole file, and the new test uses unique `$TMP/legacy-<name>` directories and adds no new export.
   - In `tests/test-project-update.sh`, `CLAUDE_AGENTIC_TEMPLATES="$PT"` is set inline on the two `update.py` invocations only, and the earlier global export was unset at line 495.
   - `$TMP/padded-tpl` is read only by those two invocations, since nothing else references `$PT`.
   - The test creates a fixed-name `$TMP/padded-legacy` and `$TMP/padded-tpl` (`rm -rf` on the template) inside the per-run `mktemp -d`, removed by the EXIT trap.
   - `sed -i` touches only `$PB/AGENTS.md`, a file the test owns.
   - The two dry runs write nothing, so the second run sees the original legacy file.
   - Nothing globs `$TMP/*`.

7. **Suite results** (run by me): `test-scaffold-idempotency.sh` 64/0 and `test-project-update.sh` 196/0 on the working tree. The full suite and e2e were measured by the sensor and inherited.

8. **Scope and checks.**
   - `git status` shows only the 4 declared files, plus the untracked report directory.
   - No test was weakened or skipped, and no lint or type level was lowered.
   - `known-risks.md` edits touch only items (c) and (d), and their status text matches the code.
   - Nothing under `vendor/` or `node_modules/`.

## VERDICT
verdict: passed
scope_assessment: Stayed inside the plan: one grep changed in `scaffold-ai.sh` plus a comment, two tests, and the (c)/(d) status text in known-risks.md; no other file touched, no production behaviour changed beyond the intended either-spelling check.
