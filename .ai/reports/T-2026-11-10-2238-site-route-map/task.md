# T-2026-11-10-2238-site-route-map — Site (gh-pages worktree): route-map look (light paper, navy, three coloured lines) with moderate motion and a modes board; classic look kept behind a switch

feature · guarded · started 2026-11-10T22:38:27Z · claude

## Weight

```
scope          2  site/assets/rr.css referenced from 250 files
behaviour      1  keyword 'transition' in site/assets/rr.css
reversibility  0  git revert returns everything
domain         0  "static HTML/CSS on gh-pages, git-excluded from main (.git/info/exclude:19), ships in no package
novelty        1  "first restyle since c205c3d; same files and mechanisms" (declared)
coverage       0  1 of 1 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: site/assets/rr.css, site/assets/rr.js, site/index.html, site/compare.html, site/demo.html, site/storage.html
tests: none

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2238-site-route-map/suite-1.log | no |
| 2 | e2e | 0 | 8f6bb97f5 | .ai/state/logs/T-2026-11-10-2238-site-route-map/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L1 assets/rr.css:357 (map block) and :149 (`.panel .chip.y`): yellow used as text on a light panel. In the map look `--yel` is #B77F00 and the hero panel is #F1EEE2, about 3:1. It affects the hero SVG label "GUARDED · W 3–7" (15px bold) and the `[data-mode]` chip when it reads "guarded". The hero's green and red labels and chips are also only about 3.9:1 on that panel. All of these are small bold text, below AA. Legible, but weaker than the classic look. in_scope: yes
- [LOW] L2 index.html:90-92 (+ rr.css `.chip.y`): the modes-board "Guarded" chip uses the hard-coded #B98500 on white, about 3.3:1 at 14px bold. It is the same colour as the existing table chips, so this is consistent but low. in_scope: yes
- [LOW] L3 assets/rr.js:59-71: the stagger is not scoped to the map look. In the classic look, `.cards`, `.levers`, `.facts` and the new `.modes` also get 0–350 ms of `transitionDelay`, a visible timing change on a look that was meant to stay intact. On a one-column mobile grid each later card waits up to 350 ms after entering view. The delay is cleared at 1000 ms, which is longer than the 350 ms + 600 ms transition, so nothing is left behind. `.bars` and non-grid parents skip the branch cleanly. No error found. in_scope: yes
- [LOW] L4 `<meta name="theme-color" content="#232B27">` (all four pages): the old dark-green colour is kept, but the map look's bar is navy on a paper page. This only affects the mobile browser chrome tint. in_scope: yes
- [LOW] L5 assets/rr.css (map block): the map look sets `color-scheme: light` and re-points every token that the OS-dark `:root` block sets. The consequence is that an OS-dark user gets light paper in the default look and dark only in classic. That is a behaviour change to the default look, not a bug. in_scope: yes
- [INFO] I1 `:is(.card,.fact,.mode,.lever)` transition override (map block): it drops the `.lever` border-color transition and sets the box-shadow transition on elements that never hover-shadow in classic. Cosmetic. in_scope: yes
- [INFO] I2 index.html:10 and the three sibling pages: the Archivo Narrow request is made in the classic look too, and Barlow stays loaded in the map look. One extra font request. Archivo Narrow is wider than Barlow Condensed, so nav and heading wrapping between 820 and 900px could change. Not rendered (not reached). in_scope: yes

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
