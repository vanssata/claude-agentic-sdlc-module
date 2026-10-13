# Discovery C — duplicated rules, done criteria, skill anatomy, docs, prose-pinning tests (T-2026-10-13-001)

## 1. Non-negotiable rules, every restatement
- A "production behaviour is the source of truth": stub.md:25,:40; CLAUDE.md:30 (root, hand-written); templates/.ai/AGENTS.md:10 (= live); safety.md:8 (live + template); docs/faq.md:259. Not in routing.md, manager.md, agents/*.tmpl, README, ai-task Rules (which has "written down, not fixed" :626).
- B "step names its files / SCOPE_CHANGE_REQUIRED": stub.md:26,:43; CLAUDE.md:32; templates/.ai/AGENTS.md:12-14; safety.md:32; ai-task/SKILL.md:259,:323,:342,:624; ai-implementer.md.tmpl:3,:26; tooling.md:80; risk-tiers.md:112 (template :116); docs/faq.md:35,:54,:260; docs/agents.md:72; docs/hooks.md:298; README.md:495.
- C "no agent commits/pushes/merges/deploys": stub.md:27 (global only); routing.md:48,:132; templates/.ai/AGENTS.md:15-16; safety.md:22; release.md:20-22; manager.md:42,:62-64; ai-task/SKILL.md:482-486,:627; docs/faq.md:114,:261; ai-release.md.tmpl:28-29.
- D "verify once to the end, fix as one batch": stub.md:28,:49; CLAUDE.md:34; routing.md:41,:123; templates/.ai/AGENTS.md:17-20; testing.md:53 (canonical long form); model-routing.md:29; risk-tiers.md:58 (template :59); docs/risk-tiers.md:28; README.md:400-402; manager.md:24; ai-task/SKILL.md:98,:153-164,:181,:384,:404,:455,:613-617; review-economy.md:72.
- E "never mix refactoring with feature": stub.md:25; templates/.ai/AGENTS.md:21-22; testing.md:15; workflows/refactoring.md:30,:35; docs/workflows.md:37; ai-planner.md.tmpl:62. Not in CLAUDE.md or ai-task Rules.
- F evidence labels: templates/.ai/AGENTS.md:23-25; safety.md:50; ai-discovery.md.tmpl:34; ai-context.md.tmpl:45; ai-init/SKILL.md:140; docs/workflows.md:64.
- INFERENCE: canonical long form = safety.md; short form = .ai/AGENTS.md "Non-negotiable"; stub.md is the sole source of rendered blocks (render_instructions.py build --check; test-instruction-budget.sh:13-19). testing.md "Reading a failure" is D's home.
- RISK: root CLAUDE.md:28-36 is hand-written, not rendered from stub.md.

## 2. Done criteria by file
- testing.md:32-49 three scopes; :53-58 batch, two rounds; :69 never edit a test to pass; :73-117 commands. Template copy 93 lines vs live 129.
- release.md:5-22 gate list; :35-41 what blocks a release. Template 37 lines.
- review-economy.md:169-178 nothing skipped, no cheaper reviewer; :149-163 §8 skip conditions.
- ai-task/SKILL.md: :153-173 (direct step 4), :183-187 (step 6), :380-409 TEST, :411-461 review, :473-480 RELEASE REPORT short form, :482-519 HUMAN APPROVAL.
- templates/release-report.md:1-52 (20 fields; template copy 33 lines); ai-release.md.tmpl:16-29; manager.md:24.
- INFERENCE: no single definition of done; split across testing.md, release.md, ai-task Rules :609-627, template fields. RISK: "open risks" (SKILL.md:475) vs `known_risks` (template) wording.

## 3. review-economy.md (live 179, template 136 — drifted)
- Sections: one rule :13; §1 probe :20; §2 ledger :46; §3 batch/scoped re-review :72; §4 parallel dimensions :90; §5 second attempt :108; §6 cheap facts :125; §7 record :138; §8 sensors may replace :147; will not trade away :169.
- Orchestration-flavoured: §1 :20-44, §4 :90-106, §3 :72-88, §6 :125-136, :171-178. Mechanics state.py review-gate implements (must stay): §2 :46-70, §8 :147-167. §5, §7 discipline.
- KNOWN FACT: ai-task/SKILL.md:441-449 restates probe/ledger/scoped re-review/one reviewer per pass. UNKNOWN: whether state.py/sensors.py read review-economy text.

## 4. Skill anatomy
- All have name + description; argument-hint on ai-audit, sdlc-spec, sdlc-intent, sdlc-plan, ai-init, ai-task, project-update; missing on usage-report, project-init, ai-status.
- ai-task (~628): 0 :31, 1a :115, 1 :193, Questions :521, context :585, Rules :607; support state.py, sensors.py.
- ai-init (257): rule :26, Steps :34, Rules :247; scaffold-ai.sh (109); templates risk-tiers.json 569, risk-tiers.md 127, review-economy.md 136.
- project-update (283): 1-8 :27-154, Rules :220, Writing a migration :234; adopt.py, update.py, render_instructions.py, history/index.json, migrations.
- ai-status (248): Steps :19, Rules :245. ai-audit (136): rule :29, Steps :35, Rules :130; rubric 122. usage-report (138): What it reads :38, Reading :118; usage-report.py. project-init (49): Steps :18, Rules :45. sdlc-spec (57): :12,:18,:37, no Rules. sdlc-intent (66): Steps only. sdlc-plan (37): Steps only.
- KNOWN FACT: no skill has When to use / Verification headings; closest are Rules and Steps.

## 5. Approval checkpoints
- ai-task/SKILL.md:121-125 (T3 plan mode = plan approval), :144, :186, :293, :298-300, :482-519. README.md:357,:369,:376,:455-458. docs/risk-tiers.md:25,:72. manager.md:62-64. docs/workflows.md: none.
- INFERENCE: two checkpoints today (plan-mode accept at T3; human_approval stage at the end); no "single checkpoint" concept named.

## 6. README and docs/sdlc
- README "## Known risks" :517-722 (13 subsections); "## Migrating from claude-routing" :723-752; Tests :753; Documentation :776; Contributing :790.
- Links: README.md:5 badge, :43, :48; CONTRIBUTING.md:61,:77; SECURITY.md:30,:38 (prose); README.md:621 cites a wp5 spec. No anchors in docs/, skills/, install.sh.
- docs/sdlc/: README.md, constitution.md, intent/adaptive-cross-runtime-sdlc.md, specs wp1-wp6, plans wp1-wp6 + dual-runtime-agentic-routing.md, 4 TEMPLATE.md. No work-package status recorded; INFERENCE wp1-wp6 finished (migrations 0001-0005, adopt suite, commits #48/#50). UNKNOWN: wp6 OQ6 closed.
- References to docs/sdlc/specs|plans: plan headers :4; intent :213; README.md:621,:788,:315-317; docs/ai-sdlc-adoption-plan.md:42,:55-56; docs/workflows.md:83; sdlc-spec, sdlc-plan, ai-audit rubric :28,:36; project-init templates; project-scaffold.sh:85-86; update.py:73-74; adopt-map.json:23-48; tests/test-project-adopt.sh (fixtures), test-ai-task-state.sh, test-instruction-budget.sh (counts only). .ai/reports/T-2026-09-21-001/state.json.

## 7. Prose/structure-pinning tests
- run-all.sh:11-17 literal 25-suite list; missing file skipped (:18).
- test-instruction-budget.sh: build --check drift (:13-40); project blocks ≤2048 B (:94-104,:111-120); global ≤2560 B (:255); required phrases in global stub (:125-131): `/ai-task <request>`, `.ai/AGENTS.md`, `SCOPE_CHANGE_REQUIRED`, `/ai-init`, `human approval`, `source of truth`, `one batch`, `routing.md`; no model name (:135-141); constitution ≤15 principles/≤4096 B, sdlc-spec/sdlc-plan/ai-planner.tmpl mention constitution (:143-159); router template must not contain 'ADVERSARIAL REVIEW' (:186), every backticked path exists (:165-185), ≤4096 B (:191-193); ai-task/SKILL.md must contain 'ADVERSARIAL REVIEW' (:197); rules rendering :200+; Codex 32 KiB :290+.
- test-shared-prompts-model-free.sh: forbids model names in stub.md, routing.md, agents/*.tmpl, skills/**/*.md (except project-update/history), ai-init and project-init templates (:16-27); rendered blocks model-free (:38-55).
- test-ai-status-root.sh: awk-extracts the 3-space-indented ```bash block in ai-status step 1 containing `AI_PROJECT=`, compares with find_ai_root (:17-28).
- test-end-to-end.sh: needs scaffold templates and risk-tiers.json (:25-27).
- test-guard-characterization.sh + golden.txt: pins guard deny texts.
- test-install-dry-run.sh:170-176 lists skills/*/SKILL.md install must copy; :135 agent frontmatter.
- No skill-frontmatter lint exists (scripts/ has 3 files; pylint.yml Python only; tests.yml runs run-all.sh).

## Open questions
- Canonical: safety.md (long) or .ai/AGENTS.md (short)?
- review-economy.md live vs template drift: diff before editing.
