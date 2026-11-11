# T-2026-11-10-2301-site-warm-look — Site (gh-pages worktree): keep the signal-box concept, repaint it with the Claude Design palette, make the motion slower and quieter; the route-map look goes

feature · guarded · started 2026-11-10T23:01:25Z · claude

## Weight

```
scope          2  site/assets/rr.css referenced from 253 files
behaviour      1  keyword 'transition' in site/assets/rr.css
reversibility  0  git revert returns everything
domain         0  "static HTML/CSS on gh-pages, git-excluded from main (.git/info/exclude:19), ships in no package
novelty        0  "same mechanism as T-2026-11-10-2238-site-route-map: the look block re-points tokens" (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: site/assets/rr.css, site/assets/rr.js, site/index.html, site/compare.html, site/demo.html, site/storage.html
tests: none

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2301-site-warm-look/suite-1.log | no |
| 2 | e2e | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2301-site-warm-look/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 rr.css:209,214,148 (warm light): Clay `--red` #D97757 as small bold text on sheet/paper is about 3.1:1 on #FFF and 3.0:1 on #FAF9F5, under 4.5:1. It affects `.alt .con h4` (13px), `td.no`, and `.chip.r` on the white `.mode`. Classic #E2412C is about 4.2:1, so this is a regression. Dark OS is fine (4.9 to 5.6). in_scope: yes
- [MEDIUM] M2 rr.css:332: sheet `--grn` #558A42 is about 4.1:1 on white and 3.9:1 on paper, so `.alt .pro h4`, `td.yes` and `.chip.g` are under 4.5. In dark OS the sheet override is not re-tuned, so it is about 3.7:1 on #262624 and 4.25:1 on #1A1918. in_scope: yes
- [LOW] L1 rr.css:333-334: Clay on #FAF9F5 is about 2.98:1 for `.sheet .h2 em`. That is large text, just under 3:1. `.fact .n` on white is 3.1 and passes. Both are hard-coded, so dark OS works (5+). in_scope: yes
- [LOW] L2 rr.css:324: panel `--grn` #788C5D on `--en` #262624 is about 4.1:1 (en2 4.5, en3 5.0). That covers the 15px hero label and the `.chip.g` on panels. It is borderline for small text. in_scope: yes
- [LOW] L3 rr.css:325 vs :18: `--c-files`/`--c-idx` are set in the warm light block with higher specificity than the root dark override. The root dark values (#BA800A/#2A9E74) are therefore dead in warm, and the warm dark block does not reset them. In dark OS `--c-idx` #558A42 on #1A1918 is only about 4.25:1, and these are bar fills with a legend. Cosmetic. in_scope: yes
- [LOW] L4 rr.css:353 vs :183: `html[data-look="warm"] .rv` has specificity (0,2,1) and overrides `.rung`'s `border-color/background .3s` transition. `.rung.rv` hover therefore snaps instead of easing in warm. The classic `.rv` rule already did the same, so this is old. in_scope: yes
- [LOW] L5 rr.css:355-356: the hover lift and shadow now also apply to `.card`, `.fact` and `.mode`, which had no hover before. This is new interactivity on non-links and sits oddly with "quieter". The shadow is invisible on dark panels and sheets. in_scope: yes
- [INFO] I1 demo.html:53: the noscript text has an inline `color:#AAB6AF`, a cool grey that does not follow `--dim` in warm. It is only visible with JS off. in_scope: yes
- [INFO] I2 rr.css:26: the `:focus-visible` outline is `--yel` #C9A82D, about 2.3:1 on white sheets. Classic was worse (1.8), so this is pre-existing. in_scope: no
- [INFO] I3 benchmark.html, catalog.html and v1.html are meta-refresh stubs with no CSS. They are unaffected. in_scope: yes

## VERDICT
verdict: pass_with_findings
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|

+0 −0 lines, 0 files

## Verdict

close: closed
facts: (a) green — suite green on 8f6bb97f5 (run 1) · (b) green — 0 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
