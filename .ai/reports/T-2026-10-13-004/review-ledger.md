# Review ledger — T-2026-10-13-004

<!-- Append-only. Every review agent reads this before it plans its
     own work; a CONFIRMED row is out of budget for later passes. -->

| claim | verified by | outcome | pass |
|---|---|---|---|
| diff on a9029181f: 131 files / 6444 lines (T6 task budget 15 / 400) — budget: over — 6444 lines > 400; 131 files > 15 (advisory) | sensors.py diff | CONFIRMED | sensor |
| rescore on a9029181f: T6 — scopes: docs, source, migrations, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on a9029181f: 9/9 finished steps name tests that exist | sensors.py traceability | CONFIRMED | sensor |
| duplicates on a9029181f: 4 block(s) of >= 8 lines appear twice: agents/ai-context.md.tmpl:52 ~ agents/ai-discovery.md.tmpl:50 | sensors.py duplicates | DEFECT, open | sensor |
| plan_sections on a9029181f: .ai/reports/T-2026-10-13-004/implementation-plan.rev2.md is missing: ## Files that change, ## Order of work, ## Proof | sensors.py plan_sections | DEFECT, open | sensor |

## Manager probe (before ai-reviewer), 2026-10-14
- ai-path from a subdirectory of a .ai/ project, no override: resolves to <home>/claude-agentic/ai/policies/git.md, exit 0.
- ai-path '../../etc/passwd': exit 2 ('..' refused). '/etc/passwd': exit 2 (absolute refused). Missing file: exit 1, names both roots.
- ai-path --tree-hash prints a sha256.
- Override probe not run: the path guard refuses writing any .ai/policies/ path while the task is in flight, even in the scratchpad (covered by tests/test-shared-tree.sh and test-migration-0006.sh).
- lint: pylint not installed on this machine (sensor UNAVAILABLE); py_compile of update.py, 0006, build-template-history.py, render-codex-agents.py ok. NOT a green lint.
- tests sensor STALE only because README's suite count was written after suite run 1 (plan Step 9: one-line change after the green run).
| diff on 59045ed6b: 131 files / 6633 lines (T6 task budget 15 / 400) — budget: over — 6633 lines > 400; 131 files > 15 (advisory) | sensors.py diff | CONFIRMED | sensor |
| rescore on 59045ed6b: T6 — scopes: docs, source, migrations, tests | sensors.py rescore | CONFIRMED | sensor |
| traceability on 59045ed6b: 11/11 finished steps name tests that exist | sensors.py traceability | CONFIRMED | sensor |
| duplicates on 59045ed6b: 4 block(s) of >= 8 lines appear twice: agents/ai-context.md.tmpl:52 ~ agents/ai-discovery.md.tmpl:50 | sensors.py duplicates | DEFECT, open | sensor |
| plan_sections on 59045ed6b: .ai/reports/T-2026-10-13-004/implementation-plan.rev2.md is missing: ## Files that change, ## Order of work, ## Proof | sensors.py plan_sections | DEFECT, open | sensor |
