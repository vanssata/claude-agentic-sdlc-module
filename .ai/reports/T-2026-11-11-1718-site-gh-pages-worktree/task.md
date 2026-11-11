# T-2026-11-11-1718-site-gh-pages-worktree — Site (gh-pages worktree): the 4.1 installer and setup cards say what --yes, no terminal and the prose fallback do (closes review L1, L2 of T-2026-11-11-1545)

feature · guarded · started 2026-11-11T17:18:35Z · claude

## Weight

```
scope          2  site/index.html referenced from 13 files
behaviour      1  keyword 'async' in site/index.html
reversibility  0  git revert returns everything
domain         0  static HTML on gh-pages, git-excluded from main (.git/info/exclude:19), ships in no package (dec
novelty        0  two sentences in the What's new cards (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: site/index.html
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | bb039d2f5 | .ai/state/logs/T-2026-11-11-1718-site-gh-pages-worktree/suite-1.log | no |

suite passing · e2e not_applicable (static HTML on the gh-pages worktree; no e2e flow reads site/) · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [LOW] L1 The installer sentence drops `TERM=dumb` and the "prints what 4.0.1 printed" clause that the CHANGELOG bullet carries (`site/index.html:244`) in_scope: yes
  - CHANGELOG 4.1.0 says "`RISKRAILS_MENU=off` (or `TERM=dumb`) brings back the typed plan question". The card names only the env var.
  - The omission is not false, and a card can be shorter than a changelog. Optional.
- [LOW] L2 The setup sentence omits the "unverified Codex tool" case (`site/index.html:245`) in_scope: yes
  - The CHANGELOG lists three causes for prose: dialog off, an unattended run, an unverified Codex tool. The card names two.
  - What the card says is accurate. A Codex user may still meet prose without having switched anything off.
- [INFO] I1 The two new sentences match the CHANGELOG `## [4.1.0]` bullets (`site/index.html:244-245`) in_scope: yes
  - "`--yes` or no terminal asks nothing" matches the Added bullet.
  - "`RISKRAILS_MENU=off` brings back the typed plan question" matches it too, and fixes the old "ask as in 4.0" wording.
  - "With the dialog off or in an unattended run the questions stay prose" is a strict subset of the CHANGELOG sentence.
  - The `Changed` bullet (Enter installs the highlighted plan on a terminal with no detected plan) is not on the card. It was not in the goal.
- [INFO] I2 HTML is well-formed (`site/index.html:244-245`) in_scope: yes
  - I ran a tag-balance parse over the whole file: no mismatched or unclosed tags.
  - The diff is exactly 2 lines, in the `gh-pages` worktree, and `<code>` tags are closed in both paragraphs.
  - I did not render the page.

## VERDICT
verdict: pass
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: closed
facts: (a) green — suite green on bb039d2f5 (run 1) · (b) green — 0 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
