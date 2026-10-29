# T-2026-10-29-2234-rewrite-readme-and-docs — Rewrite README and docs for the refactored plugin (RiskRails 3.0), add ROADMAP.md with the unfulfilled Agentic SDLC intent and an Upgrade section

feature · light · started 2026-10-29T22:34:53Z · claude

## Weight

```
scope          2  README.md referenced from 112 files
behaviour      0  documents only
reversibility  0  git revert returns everything
domain         0  documents only
novelty        0  documents only
coverage       0  no code file declared
W 2 → light   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: README.md, ROADMAP.md, CONTRIBUTING.md, SECURITY.md, docs/getting-started.md, docs/agents.md, docs/faq.md, docs/architecture.md, docs/hooks.md, docs/workflows.md, docs/weight.md, docs/local-memory.md, docs/hook-performance.md, docs/risk-tiers.md, docs/sdlc/README.md, docs/installation.md, docs/routing.md, docs/project-update.md, docs/known-risks.md
tests: tests/test_memory_risks.py tests/test_rename.py tests/test_no_size_tokens.py tests/test_instruction_budget.py tests/test_skills_surface.py tests/test_shared_prompts_model_free.py tests/test_project_update.py tests/test_shared_tree.py
amended 2026-10-29T22:38:47Z: +docs/installation.md, docs/routing.md, docs/project-update.md, docs/known-risks.md — PR #54 (e571054 on origin/main) split README into these four pages; new-refactor never absorbed them — port their still-valid content so nothing is lost when new-refactor replaces main (request relayed by the release-3.0.1 session)

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 2 | 2e8dc737d | .ai/state/logs/T-2026-10-29-2234-rewrite-readme-and-docs/step-1.log | no |
| 2 | step | 0 | 2e8dc737d | .ai/state/logs/T-2026-10-29-2234-rewrite-readme-and-docs/step-2.log | no |
| 3 | suite | 0 | 2e8dc737d | .ai/state/logs/T-2026-10-29-2234-rewrite-readme-and-docs/suite-3.log | no |
| 4 | step | 0 | fd461d0fb | .ai/state/logs/T-2026-10-29-2234-rewrite-readme-and-docs/step-4.log | no |

suite passing · e2e not_required · suite runs 1

## Review

none yet

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CONTRIBUTING.md | +61 −40 | Edit |
| README.md | +242 −836 | Edit |
| ROADMAP.md | +109 −0 | New |
| SECURITY.md | +15 −14 | Edit |
| docs/agents.md | +85 −106 | Edit |
| docs/architecture.md | +150 −318 | Edit |
| docs/faq.md | +191 −456 | Edit |
| docs/getting-started.md | +128 −146 | Edit |
| docs/hook-performance.md | +68 −182 | Edit |
| docs/hooks.md | +285 −571 | Edit |
| docs/installation.md | +202 −0 | New |
| docs/known-risks.md | +217 −0 | New |
| docs/local-memory.md | +5 −4 | Edit |
| docs/project-update.md | +138 −0 | New |
| docs/risk-tiers.md | +0 −100 | Delete |
| docs/routing.md | +132 −0 | New |
| docs/sdlc/README.md | +18 −14 | Edit |
| docs/weight.md | +9 −9 | Edit |
| docs/workflows.md | +71 −56 | Edit |

+2126 −2852 lines, 19 files

## Verdict

close: closed
facts: (a) green — documents only since run 3 (1 files: README.md); doc_tests green in run 4 on fd461d0fb · (b) green — 19 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 0
