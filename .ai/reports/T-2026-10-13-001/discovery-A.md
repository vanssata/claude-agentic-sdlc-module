# Discovery A — ai-init / project-update machinery (T-2026-10-13-001)

## 1. ai-init: what is copied
- KNOWN FACT: scaffold-ai.sh copies every file under templates/.ai/ into <project>/.ai/, skipping existing files (skills/ai-init/scaffold-ai.sh:75-84). Template root: $CLAUDE_AGENTIC_TEMPLATES or <skill>/templates (:15).
- KNOWN FACT: .ai/VERSION skipped when .ai/ already exists (:70-80; tests/test-scaffold-idempotency.sh:47).
- KNOWN FACT: appends gitignore.snippet (:86-91); creates instruction files from *.minimal.md + *.block.md, block appended once by start marker (:93-111). Runtimes: claude, codex, gemini, junie (:108-111).
- KNOWN FACT: template inventory under templates/.ai/: policies/ (production, coding, database, git, release, context-management, model-routing, review-economy, safety, security, testing, tooling, risk-tiers.json, risk-tiers.md, path-guard.json); agents/ (tester, context, discovery, implementer, manager, planner, release, reviewer, risk, security); workflows/ (5); templates/ (6); AGENTS.md, VERSION (=5), state/README.md, rules/README.md, reports/.gitkeep, project/*.md (10).
- KNOWN FACT: project-specific = never overwritten by update.py: .ai/project/**, .ai/reports/** create-only (update.py:918-921); VERSION owned by migration (:913); state/, rules/ only a README. Everything else (policies, agents, workflows, templates, .ai/AGENTS.md) goes through three-way merge (:922).
- INFERENCE: risk-tiers.json, path-guard.json, coding.md, testing.md are edited per project (ai-init/SKILL.md:82,155,181-188,218).
- RISK: policy files mix shared text and project-filled fields: testing.md (verify_command, step_test_command, e2e_command, lint_command, typecheck_command; update.py:928-939), risk-tiers.json (pipeline_profile). Moving shared policies strands these values unless split out.

## 2. project-update
- KNOWN FACT: update.py dry-run by default; --apply, --check, --check --budget, --confirm-delete; manages .ai/** and docs/sdlc/*/TEMPLATE.md by three-way update plus the managed block (update.py:1-41). .ai/project/**, instruction files, .claude/settings.json, .codex/config.toml: created when missing, never updated (:28-29).
- KNOWN FACT: three_way() update.py:574-628: absent → create; equals template → nothing; equals any history version → replace; JSON → merge_json per key against closest base (:596-621); text → merge_text (git merge-file, :207) against closest base (:623-628); conflict leaves file, plugin copy to plan.local_dir (:1112-1113).
- KNOWN FACT: risk-tiers.md carries sha256 of risk-tiers.json; update.py normalises/re-syncs it (:579-580, 631-649); /ai-status checks it (ai-status/SKILL.md:155-160).
- KNOWN FACT: managed block: block_update() update.py:652-684; markers at update.py:66 and render_instructions.py:38-39; text from TEMPLATES["ai-init"]/<runtime>.block.md (:656); appended when markers missing (:663-667); file created from *.minimal.md + block if absent (:657-661).
- KNOWN FACT: block text originates in instructions/stub.md (routing.md for the long reference); render_instructions.py build renders *.block.md and skeletons; install.sh and update.py import the renderer (render_instructions.py:1-21, 33-36). tests/test-instruction-budget.sh fails when committed templates differ from the render (:264-268).
- KNOWN FACT: update.py also runs rules_update (:925) rendering .ai/rules/<slug>.md into per-directory rule blocks.
- KNOWN FACT: adopt.py = update.py --adopt; maps Spec Kit, Kiro, Cursor, Copilot, AI-DLC, Junie, Gemini, oversized CLAUDE.md/AGENTS.md; exits 4/5; --confirm-delete human gate (adopt.py:1-48); writes .ai/policies/adopted/ and .ai/rules/ (project-update/SKILL.md:182,198).
- KNOWN FACT: migrations 0001-0005 (0001 no-op; 0002 journal; 0003 context diet; 0004 gate keys; 0005 handoff keys), all MOVES=[]; contiguous numbering, CURRENT from file names (migrations/__init__.py:3-16,60; update.py:863); env CLAUDE_AGENTIC_MIGRATIONS.
- KNOWN FACT: history/index.json maps <set>/<relpath> → sha256 list; history/blobs/<sha> content versions; History class update.py:155-190; env CLAUDE_AGENTIC_HISTORY (:58). tools/build-template-history.py walks every git ref for the two template trees (:12-45); test-project-update.sh fails when history is stale (:10-11).
- RISK: relocation/rename of templates goes through migrations.renames()/MOVES or RETIRED (migrations/__init__.py:22-30), else edited copies become conflicts.
- RISK: removing shared policies from the template tree leaves project copies on disk; deletion path is delete? items with --confirm-delete (update.py:11-13; adopt.py:30-48).

## 3. Reads of policy/agent/workflow/template files from the project tree (all project-relative)
- ai-task/SKILL.md: :10 agents/manager.md; :11 policies/safety.md; :76 workflows/<wf>.md; :89,:204 risk-tiers.json; :136,:258 tooling.md; :150,:154,:358 testing.md; :240 templates/impact-report.md; :276 templates/implementation-plan.md; :449 review-economy.md.
- ai-status/SKILL.md: :138,:159-160 risk-tiers.json/.md; :152 testing.md; :219 .ai/policies/; :170-187 update.py via $AI_HOME (plugin-relative).
- ai-init/SKILL.md: :82,:155 testing.md, coding.md; :186,:218 risk-tiers.json; :41,:47 scripts via $AI_HOME.
- project-update/SKILL.md: :54-59,:118,:130,:182,:198,:229.
- state.py: :569 risk-tiers.json (pipeline_profile, direct_mode_cap); :1191 message naming testing.md; :225 comment on $AI_HOME. UNKNOWN: all testing.md reads in state.py.
- sensors.py: :363 root/.ai/policies/risk-tiers.json; :536 testing.md; :81 diff-classification lists .ai/policies/**, .ai/workflows/** as "policy"; :852,:1269,:1405,:1470-1474 message text; :162 .ai/ locates root.
- hooks/ai-path-guard.sh: :44 reads $AI_ROOT/.ai/policies/path-guard.json merged with $HOOK_DIR/ai-path-guard-defaults.json (:43); :95-100 messages. ai-scope-guard.sh reads only state/current.json (:29). ai-git-guard.sh :109 message only; UNKNOWN whether it reads a project policy.
- agents/*.tmpl "Read first, when they exist: .ai/policies/..., .ai/agents/<role>.md": ai-security:11; ai-context:14-15; ai-tester:37; ai-expert:16; ai-implementer:11-12,40; ai-risk:3,13-14; ai-release:13-14; ai-discovery:14-15; ai-planner:14-16; ai-reviewer:14-16.
- INFERENCE: nothing resolves a policy via CLAUDE_PLUGIN_ROOT; hooks use $HOOK_DIR, skills $AI_HOME; policy reads are project-relative.
- RISK: most policy reads are prose to the model; moving policies means rewriting SKILL.md texts, *.tmpl agents and stub/block text.
- RISK: path-guard task_protected_patterns cover .ai/policies, .ai/workflows in the project; plugin-root policies fall outside that guard.

## 4. Hooks reading risk-tiers.json / path-guard.json
- KNOWN FACT: ai-path-guard.sh:44 optional project path-guard.json ([ -f ], allow if nothing loaded :53,:79); unions defaults with project lists (deny_patterns, allow_patterns, protected_config_patterns, task_protected_patterns, dependency_instruction_patterns; :64-71).
- KNOWN FACT: ai-scope-guard.sh reads neither. sensors.py:363-367 reads project risk-tiers.json, defaults missing WP4 keys (:56,:103). state.py:569 pipeline_profile, fallback "solo".
- KNOWN FACT: ai-task/SKILL.md:89, ai-status/SKILL.md:138 read it with jq, default "team".
- INFERENCE: path-guard.json and pipeline_profile need a project-side location; hooks degrade gracefully if missing.

## 5. Tests
- test-project-update.sh: scaffolds from oldest templates via history blobs, hand-edits, asserts update brings project current without losing edits; --check format (:77); schema 0→current with task in flight (:173-260); 0003 context diet and block merge (:266,:278); synthetic migrations via CLAUDE_AGENTIC_MIGRATIONS (:371-391); --confirm-delete pty gate (:464); RETIRED rename chains (:544); budget without instructions/ (:671). Fails when history stale.
- test-project-adopt.sh: update.py --adopt over tests/fixtures/adopt/ (Spec Kit, Kiro, Cursor, Junie-Gemini, large-claude-md, large-agents-md); no-line-lost, gates, coexist, split proposals, --cleanup, interrupt/resume.
- test-scaffold-idempotency.sh: scaffold twice changes nothing; pre-VERSION project stays schema 0 (:2-4,:47-49).
- test-merge-migration.sh: claude-routing absorption; :77 asserts installed templates declare a tier.
- test-instruction-budget.sh: templates equal stub.md render (:21 hand-edit caught, :34 build); per-file byte budgets; Codex 32 KiB note (:287-289); advisory downstream budget (:305-306).
- test-install-dry-run.sh: install.sh rendering per plan/fable combination; idempotent real install; pins twelve tier agents (:116-118).
- UNKNOWN: which assertions name specific policy paths.

## 6. .ai/VERSION
- KNOWN FACT: template VERSION = 5; plugin schema = highest migration (update.py:863). Nothing bumps it automatically (migrations/__init__.py:3-16; project-update/SKILL.md:237). update.py writes project VERSION last (:884-886), holds it back on conflict/unconfirmed delete (:874-880); refuses project > CURRENT exit 2 (:864-866). detect_version :280-294; /ai-status relays --check (ai-status/SKILL.md:172-181). Distinct from "version" inside risk-tiers.json.
- RISK: with plugin-root policies the schema describes only state keys, journal and layout (what 0002/0004/0005 really change).

## Open questions
- Which shared files stay project-owned: risk-tiers.json (pipeline_profile, overrides), path-guard.json, testing.md (commands), coding.md (specifics), .ai/agents/*.md (role overrides)?
- Existing projects' copies: delete, leave, or migration 0006 with MOVES?
