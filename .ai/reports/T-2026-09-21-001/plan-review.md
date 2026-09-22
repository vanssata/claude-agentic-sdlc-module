# Plan review — WP6 (T3, ai-reviewer opus) — verdict: REJECT, revise plan text

BLOCKER
1. Path guard denies fixture paths (.cursorrules, .cursor/rules, .claude/commands, .github/copilot-instructions.md, .ai/rules, .ai/state/current.json, .junie, .codex/prompts, .ai/AGENTS.md, .ai/policies) — hooks/ai-path-guard-defaults.json. Fix: store fixtures under non-matching names (dot-cursorrules, _cursor/…) and materialise in $TMP in run_fixture, or human creates them.
2. tests/test-project-update.sh:482 second --confirm-delete call breaks under step 2 gate (no TTY in agent/CI). Fix: AI_UNATTENDED=1 inline on 435 and 482 (not export); gate after argparse checks (433/434 stay exit 2).

HIGH
3. render_instructions.DEFAULT_SOURCE (render_instructions.py:66) → ~/.claude/instructions/runtimes.json, not installed by install.sh; budget_hints swallows (update.py:781-784). Steps 3/7 fail in installed layout. Fix: defaults or ship budgets with skill; test from skills-only copy.
4. claude/codex/gemini/junie signatures detect in every project; scaffolds are ~55 B under 2048. Fix: instruction file detected only when split candidate; tests on fresh scaffolds; decide keep-budget accounting.
5. rules_update reads .ai/rules/ from disk (update.py:701-705), not plan.final → plain --check exits 1 after adopt apply. Fix: read planned content or second plan pass; test.
6. keep_original writes to project-update-<date> (update.py:985); originals only for migration items (:1071); deletion path writes migration.json, no size cap; later-day cleanup makes adopt-<newdate>/ without adopt.json become "latest". Fix: adopt report dir, adopt copier with limits, own removal, latest = greatest dir with adopt.json.
7. R15 resume vs R5 clean-tree gate conflict; item order can lose lines. Fix: allow dirt limited to planned destinations; write destinations before rewriting instruction files; test kill between item kinds.
8. tests/test-ai-status-root.sh is a phrase grep, not in step 9 allowed files. Fix: add it, with phrase checks.

MEDIUM
9. Fixture .ai/ "like schema-v4" = VERSION 4 + task in flight → fails R5; scaffold at test time (test-project-update.sh:574-576).
10. Step 5 proofs need step 6 apply — plant adopt.json or move proofs.
11. Informational report lines counted as automatic/pending (update.py:1089,1122,1154) → R15 "0 automatic" fails; mark informational.
12. Plain --check assertions (69,102,188) check exit code only — add exact-line assertion.
13. Spec Kit drop row */**/speckit* matches app code — restrict rows to tool roots; R18 case.
14. Proposal heading/paths/dirs = model text into destination; R9 lacks failing test.
15. Step 8: task-in-flight refusal, clean-tree gate, recompute-fail refusal missing from text/proof.
16. decisions.json / split-proposal.json only looked up in today's dir — search all adopt-*.
17. AI_UNATTENDED=1 lets an agent pass human_present(); state in Risks, surface unattended:true.

LOW
- C0302 disabled via .pylintrc (all C) — concern-13 trigger never fires. update.py:449 docstring already stale (rules_update:751-755 deletes) → three callers. Module docstring lacks exit codes and --confirm-delete. Cite skills/ai-task/state.py:876-879 (repo copy). measure() prints every file; two calls. Use git status --porcelain -z. "One commit per step" vs no-agent-commits. SKILL.md:78-79,:159 already has the --confirm-delete rule. Step 4 validator must accept instruction-file transform. Row-coverage mapping; `**/` zero dirs. Generate API_KEY at test time; no verbatim upstream samples.

Clean: line refs correct; Plan.add tool=None safe; model-free test scope; R1–R23 all have proof rows (gaps above); steps 2,3,7 scopes sufficient.
