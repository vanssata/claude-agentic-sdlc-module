# Review report — T-2026-10-15-001

Adversarial review by `ai-reviewer` on the STRONG tier, over the working-tree
`git diff` after the suite (27 suites, 2,612 assertions) and the e2e run were
green. The reviewer ran every finding against the new guard and against a copy
of the HEAD guard.

**Verdict: pass.** 0 BLOCKER, 0 HIGH, 6 MEDIUM, 2 LOW, 4 INFO. Scope: stayed
inside the plan; no refactoring alongside; no test weakened.

## Findings and what was done

| # | Severity | Finding | Disposition |
|---|----------|---------|-------------|
| 1 | MEDIUM | `TOKEN_END` loses its `&`: bash 5.2+ enables `patsub_replacement`, so `&` in the replacement of `${loose//\$/$TOKEN_END}` becomes the matched text. `rm -rf $SH/ai&& echo` and `rm -rf $SH/ai&` were allowed. `<` and `>` were also missing from the class (`rm -rf $SH/ai>/dev/null` allowed). | **Fixed (R2)**: the boundary is spliced in with a loop, never a pattern substitution; `<>` added; no-space `&&` and `>` cases added to the shared-tree loop. |
| 2 | MEDIUM | The destination pass forks `abs_path`, `classify` twice and `real_path` per candidate: `mv` of 20 files into a directory took 310 ms against a 110 ms budget. | **Fixed (R2)**: one in-process `matches_joined` per candidate; the forking classify runs only on a hit, and `realpath` only when the candidate exists. |
| 3 | MEDIUM | Prose false denies: a `;`, newline-separated line or heredoc body that starts with `rm`/`cp`/`mv` is treated as a command (`echo "step 2; rm -f .ai/state/current.json"`, a commit message, a heredoc writing a test script). Same class as the existing `writers` rule, now reaching the common verbs. | Residual, recorded in known-risks (a). Quote- and heredoc-aware segmentation is its own task. |
| 4 | MEDIUM | A verb not at the start of a segment is not seen: `for f in …; do cp "$f" .claude/agents/; done`, `if …; then cp …`, `(cp …)`, `$(cp …)`, `FOO=1 cp …`, `time cp …`, `{ rm -rf $SH/ai; }`, backslash-newline continuations. | Residual, recorded in known-risks (a). |
| 5 | MEDIUM | Parent directories of every directory-shaped pattern are not matched: `rm -rf ~/.claude/claude-agentic/`, `rm -rf .claude/hooks`, `rm -rf .ai/state/`, `mv .claude /tmp/x`, `cp -r src/agents .claude/`, `rsync -a /tmp/evil/ .claude/`. The known-risks (a) residual named only the bare `.ai/<dir>`. | Residual, known-risks (a) reworded so "fixed" is not overstated. |
| 6 | LOW | `-t` glued to other short flags (`cp -rt DIR src`) or attached (`-tDIR`) is read as a source. | Residual, recorded. |
| 7 | LOW | rsync: a remote path still matches the unanchored pattern (`user@host:proj/.claude/agents/`), and an option with a separate value at the end (`--exclude X`, `-e ssh`) becomes the destination. | Residual, recorded. |
| 8 | INFO | `how="move of"` only changes wording; wording right in every case checked. | None. |
| 9 | INFO | The redirect-stripping sed can eat a digit glued to a redirect (`y2>/dev/null` → `y`). Harmless with the current patterns. | Recorded. |
| 10 | INFO | `WHY_TASK` still says "policies and workflows"; the defaults' `_comment` was updated, the message was not. | Recorded; rewording it re-records every WHY_TASK golden entry, left for the human. |
| 11 | INFO | Outside this task, on HEAD too: `ln -sf /tmp/evil.md .claude/agents/x.md` is allowed (`writers` checks ln's first argument only); unnormalised paths (`$SH/./ai`, `$SH//ai`, `cd $SH && rm -rf ai`) skip the pre-filter. | Recorded. |

## Examined and clean (reviewer)

Fixtures 51–54 are ALLOW on HEAD and DENY on the new guard; 55 and 56 ALLOW on
both. The golden diff is exactly the claimed set. Correctly denied: `-t DIR`,
`--target-directory[=]DIR`, `--`, `-T`, `install -D`, quoted destinations, `~`
and `$HOME`, `rm .ai/state/*.json`, `mv $SH/ai $SH/ai.old`, `rsync --delete …
$SH/ai`, `cp -a /tmp/new/. $SH/ai`. No false denies on ordinary cp/mv with
`2>&1`, pipes, `&&`, `;`, quoted paths with spaces, `tar`, `grep "rm -f …"`.
The movers gate adds no measurable cost to commands without cp/mv/install/rsync.
`.ai/agents/` behaves as intended. `hooks/lib/` unchanged.

## Re-review

No BLOCKER was fixed, so no scoped re-review (`.ai/policies` direct-mode rule).
