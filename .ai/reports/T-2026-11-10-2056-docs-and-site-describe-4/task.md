# T-2026-11-10-2056-docs-and-site-describe-4 — Docs and site describe 4.0.0: no adopt, migrations or alias commands; M3, L3, L7 of T-2026-11-03-2046 closed

bugfix · guarded · started 2026-11-10T20:56:15Z · claude

## Weight

```
scope          2  tests/test_no_fallbacks.py referenced from 7 files
behaviour      1  keyword 'state machine' in site/compare.html
reversibility  0  git revert returns everything
domain         0  documentation and a static site; no payment, auth or data path (declared)
novelty        0  edits existing pages and an existing token table (declared)
coverage       0  no code file declared
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_no_fallbacks.py, docs/hooks.md, docs/project-update.md, docs/known-risks.md, skills/rr-setup/SKILL.md, CHANGELOG.md, site/index.html, site/demo.html, site/compare.html, site/storage.html, docs/faq.md, docs/installation.md, README.md
tests: tests/test_no_fallbacks.py
- s1 · tests/test_no_fallbacks.py · tests/test_no_fallbacks.py · done
- s2 · docs/hooks.md, docs/project-update.md, docs/known-risks.md, skills/rr-setup/SKILL.md, CHANGELOG.md · tests/test_no_fallbacks.py, tests/test_skills_surface.py, tests/test_project_update.py, tests/test_shared_tree.py, tests/test_instruction_budget.py · done · after s1
- s3 · site/index.html, site/demo.html, site/compare.html, site/storage.html · no tests · done
amended 2026-11-10T20:56:35Z: +docs/faq.md, docs/installation.md — s2: the same L7 refusal wording (test_no_fallbacks 'refused before 3.1.0' bites on both)
amended 2026-11-10T21:03:37Z: +README.md — review M1: README.md:62-64 carries the same refusal wording L7 fixes elsewhere

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 769c7654a | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/step-1.log | yes |
| 2 | step | 1 | 4bb8abf05 | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/step-2.log | no |
| 3 | step | 0 | 32940308a | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/step-3.log | no |
| 4 | suite | 0 | 32940308a | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/suite-4.log | no |
| 5 | e2e | 0 | 32940308a | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/e2e-5.log | no |
| 6 | suite | 0 | 5ae1e4e21 | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/suite-6.log | no |
| 7 | e2e | 0 | 5ae1e4e21 | .ai/state/logs/T-2026-11-10-2056-docs-and-site-describe-4/e2e-7.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [HIGH] H1 The site tells a pre-3.1.0 project to go through `npx riskrails@4.0.0` first; the version is 3.1.0 (`site/index.html:236`) in_scope: yes
  - Every other text says `npx riskrails@3.1.0` (CHANGELOG, installation.md, project-update.md, SKILL.md, README, `LAST_MIGRATING_VERSION = "3.1.0"` at update.py:62). A reader following the card installs 4.0.0, which converts nothing. The 4.0 cards are new in this diff.
- [HIGH] H2 The `[rules]` description is incomplete, and SKILL.md step 5 sends the human to a place the update deletes (`skills/rr-setup/SKILL.md:152` and `:169`, `docs/project-update.md:52`) in_scope: yes
  - `rule_sources()` (update.py:914-923, called at :1393) proposes EVERY `.ai/rules/<slug>.md` as `delete?` ("[rules] rule sources are not kept by an update: the rendered blocks go with it"); KEPT (update.py:107) has no `.ai/rules/`. The new text describes only the second kind (rendered file whose source is gone, update.py:1250-1257), and step 5 lists `.ai/rules/` among files the update keeps.
  - Confirm mechanics are right: `[rules]` rows are `delete?`, settled by `--confirm-delete`. `split` rows exist (update.py:826, :844) and apply in phase 0 ungated; asking first is a skill convention.
- [MEDIUM] M1 README.md still says a project last updated by an older riskrails "is refused with the version that still converts it" (`README.md:62-64`) in_scope: yes
  - Only the old-shape detectors refuse. The token regex does not match README's wording.
- [MEDIUM] M2 `site/index.html:263-265` still describes the 2.x upgrade as 3.0 did, linking README `#upgrade-to-30`, which no longer exists (`site/index.html:263`) in_scope: yes
  - 4.0 converts nothing; a 2.x tree is refused (exit 6 on `current.json`).
- [MEDIUM] M3 The site says `npx riskrails@4.0.0` is installable, and no page says it is unpublished (`site/index.html:40`, `:250`, `:259-261`) in_scope: yes
  - npm serves 3.2.2; the unpushed-site plan is the only mitigation and is not recorded as a gate.
- [LOW] L1 `docs/installation.md:70` still says `/skills` lists the eight skills "plus the deprecated aliases" (`docs/installation.md:70`) in_scope: yes
  - 4.0 removed the aliases; no token catches it.
- [LOW] L2 The refusal wording differs in detail between files (`docs/faq.md:235-236`, `skills/rr-setup/SKILL.md:124-127`) in_scope: yes
  - None mentions that `check_kept` also exits 6 for an unparsable `weight.project.json`, `verification.md`, `.codex/config.toml` or `weight.json`; the KEPT_UNREADABLE row covers it generally.
- [LOW] L3 The new test tokens miss the regressions this task fixed (`tests/test_no_fallbacks.py:69-82`) in_scope: yes
  - Scope is docs/, skills/rr-setup/ and README only; tokens are literal phrases and miss H1, M1, M2. No stale allow-list rows.
- [INFO] I1 Site demo and compare claims checked out (`site/compare.html:76-91`) in_scope: no

## VERDICT
verdict: pass_with_findings
```

closed by a green run: H1, H2

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +1 −1 | Edit |
| README.md | +4 −2 | Edit |
| docs/faq.md | +2 −1 | Edit |
| docs/hooks.md | +2 −2 | Edit |
| docs/installation.md | +3 −3 | Edit |
| docs/known-risks.md | +3 −3 | Edit |
| docs/project-update.md | +12 −5 | Edit |
| skills/rr-setup/SKILL.md | +17 −11 | Edit |
| tests/test_no_fallbacks.py | +12 −0 | Edit |

+56 −28 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on 5ae1e4e21 (run 6) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
