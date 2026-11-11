# T-2026-11-11-1545-site-gh-pages-worktree — Site (gh-pages worktree): version pins and install commands to the published 4.1.0, What's new in 4.1

feature · guarded · started 2026-11-11T15:45:29Z · claude

## Weight

```
scope          2  site/index.html referenced from 10 files
behaviour      1  keyword 'state machine' in site/compare.html
reversibility  0  git revert returns everything
domain         0  static HTML on gh-pages, git-excluded from main (.git/info/exclude:19), ships in no package (dec
novelty        0  same edit as T-2026-11-10-2227-site-4-0-1 (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: site/index.html, site/compare.html, site/demo.html, site/storage.html
tests: tests/test_release.py

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 78124a25c | .ai/state/logs/T-2026-11-11-1545-site-gh-pages-worktree/suite-1.log | no |

suite passing · e2e not_applicable (static HTML on the gh-pages worktree; no e2e flow reads site/) · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 The "Arrow-key installer" card says "`--yes`, no terminal or `RISKRAILS_MENU=off` ask as in 4.0" (`site/index.html:244`) in_scope: yes
  - CHANGELOG 4.1.0 says `--yes` or no terminal "asks nothing and prints what 4.0.1 printed". Only `RISKRAILS_MENU=off` (and `TERM=dumb`) "brings back the typed plan question".
  - "Ask as in 4.0" is therefore loose for `--yes` and for no terminal, which ask nothing. Suggested wording: "`--yes` or no terminal asks nothing; `RISKRAILS_MENU=off` brings back the typed plan question". It is not misleading enough to block.
- [LOW] L2 The "Setup asks once" card leaves out the fallback (`site/index.html:245`) in_scope: yes
  - CHANGELOG 4.1.0 says that with the dialog off, an unattended run, or an unverified Codex tool, the questions stay prose. The card reads as unconditional ("in one dialog before any work").
  - The same card calls it "survey depth"; the CHANGELOG says the same. That part is fine.
- [INFO] I1 No `v4.1.0` git tag exists in the main repo, so `git diff v4.0.1 v4.1.0` fails (the release commit is `a705de7`) in_scope: yes
  - I diffed `v4.0.1` against `a705de7` instead. The tag is not part of this task. `npm view riskrails version` returns 4.1.0, so the install pins are correct.

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: closed
facts: (a) green — suite green on 78124a25c (run 1) · (b) green — 0 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
