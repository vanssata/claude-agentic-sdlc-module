# T-2026-10-29-0852-r36-rest — R36 rest: 3.4c state file move, H1, 7f switch on and the texts

feature · full · started 2026-10-29T08:52:25Z · claude

## Weight

```
scope          2  skills/project-update/migrations/README.md referenced from 164 files
behaviour      2  keyword 'workflow' in AGENTS.md; hint +1
reversibility  2  skills/project-update/migrations/0009_state_file.py matches needs_step **/migrations/**; hint +1
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       1  2 of 4 code files have a test
W 9 → full   hints reversibility +1, behaviour +1 · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-29T08:52:25Z — /rr-build-all docs/sdlc/plans/command-choice-dialog.md (rows 3.4c, H1, 7f)

## Plan

files: skills/ai-task/state.py, skills/project-update/migrations/0009_state_file.py, skills/project-update/migrations/README.md, skills/project-update/update.py, tests/test_project_update.py, tests/test_ai_task_state.py, tests/fixtures/project-update/schema-v8/*, skills/ai-init/templates/.ai/policies/dialog.json, skills/project-update/migrations/0010_dialog_switch.py, tests/test_migration_0010.py, instructions/stub.md, skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md, skills/ai-init/templates/junie-guidelines.block.md, skills/project-init/templates/constitution.md, skills/rr-ship/SKILL.md, README.md, AGENTS.md, CLAUDE.md, instructions/routing.md, .ai/AGENTS.md, skills/ai-init/templates/.ai/AGENTS.md, docs/architecture.md, skills/project-update/history/index.json, skills/project-update/history/blobs/*, tests/test_instruction_budget.py, tests/test_dialog_gate.py, tests/test_rename.py, skills/ai-init/templates/.ai/VERSION, tests/fixtures/project-update/schema-v8/.ai/VERSION, tools/build-template-history.py, docs/sdlc/constitution.md, .ai/policies/safety.md, tests/test_end_to_end.py, tests/test_context_guard.py, tests/memory_harness.py, tests/test_memory_sync.py, tests/test_runtime_gate.py, tests/test_memory_characterization.py, tests/fixtures/memory/goldens/*, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/fb6f1136-0061-4c6d-89c8-e2ceb02b30ef/scratchpad/review-1.md, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/.ai/state/README.md, docs/faq.md, skills/rr-status/SKILL.md, skills/rr-plan/SKILL.md, .codex-plugin/plugin.json, .ai/project/known-risks.md
tests: tests/test_project_update.py, tests/test_ai_task_state.py, tests/test_migration_0010.py, tests/test_dialog_gate.py, tests/test_instruction_budget.py, tests/test_rename.py
- s1 · skills/ai-task/state.py, skills/project-update/migrations/0009_state_file.py, skills/project-update/migrations/README.md, skills/project-update/update.py, tests/test_project_update.py, tests/test_ai_task_state.py, tests/fixtures/project-update/schema-v8/* · tests/test_project_update.py, tests/test_ai_task_state.py · done
- s2 · skills/ai-init/templates/.ai/policies/dialog.json, skills/project-update/migrations/0010_dialog_switch.py, tests/test_migration_0010.py, instructions/stub.md, skills/ai-init/templates/CLAUDE.block.md, skills/ai-init/templates/AGENTS.block.md, skills/ai-init/templates/GEMINI.block.md, skills/ai-init/templates/junie-guidelines.block.md, skills/project-init/templates/constitution.md, skills/rr-ship/SKILL.md, README.md, AGENTS.md, CLAUDE.md, instructions/routing.md, .ai/AGENTS.md, skills/ai-init/templates/.ai/AGENTS.md, docs/architecture.md, skills/project-update/history/index.json, skills/project-update/history/blobs/*, tests/test_instruction_budget.py, tests/test_dialog_gate.py, tests/test_rename.py · tests/test_migration_0010.py, tests/test_dialog_gate.py, tests/test_instruction_budget.py, tests/test_rename.py · done · after s1
amended 2026-10-29T09:03:25Z: +skills/ai-init/templates/.ai/VERSION, tests/fixtures/project-update/schema-v8/.ai/VERSION, tools/build-template-history.py — 3.4c: migration 0009 raises the scaffold schema to 9 (VERSION) and needs the template history rebuilt; schema-v8 fixture needs .ai/VERSION
amended 2026-10-29T09:09:16Z: +docs/sdlc/constitution.md, .ai/policies/safety.md — H1: the human's own edits outside the agent (C5 amended, safety.md guard+ledger), R36.21
amended 2026-10-29T09:33:05Z: +tests/test_end_to_end.py, tests/test_context_guard.py, tests/memory_harness.py, tests/test_memory_sync.py, tests/test_runtime_gate.py, tests/test_memory_characterization.py, tests/fixtures/memory/goldens/* — suite-1: 10 regressions, all tests/goldens that read the task from the legacy .ai/state/current.json or pin plugin schema 8; 3.4c moves new tasks to state.json and 7f raises the schema to 10
amended 2026-10-29T09:52:56Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/fb6f1136-0061-4c6d-89c8-e2ceb02b30ef/scratchpad/review-1.md — the review report for state.py review --report: the shell guard parses quoted paths inside a heredoc as redirects
amended 2026-10-29T09:53:37Z: +agents/ai-reviewer.md.tmpl, skills/ai-init/templates/.ai/state/README.md, docs/faq.md, skills/rr-status/SKILL.md, skills/rr-plan/SKILL.md, .codex-plugin/plugin.json — review pass 1 M4/L5: shipped texts still name current.json or contradict amended C5
amended 2026-10-29T09:53:41Z: +.ai/project/known-risks.md — review M3: state-file move vs runtime homes on v2.x, recorded not fixed

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. G1/H1 is yours (before 7f): outside the agent edit (1) docs/sdlc/constitution.md:10 C5 -> the amended sentence of spec §Interfaces (docs/sdlc/specs/command-choice-dialog.md:354-356); (2) .ai/policies/safety.md:46-50 -> 'approval rests on a guard plus a ledger; a constructed command is outside the threat model and consent audit detects it afterwards'; (3) ~/.claude/CLAUDE.md -> the global stub line (spec :357-358). Done?
asked: 2026-10-29T09:05:36Z · stage: implementation
A. done (recommended)
B. not yet
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-29T09:08:44Z

## G1. Approve T-2026-10-29-0852-r36-rest for implementation? (gate: human_approval)
asked: 2026-10-29T10:02:48Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-29T10:28:37Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | cdcb8dfec | .ai/state/logs/T-2026-10-29-0852-r36-rest/suite-1.log | no |
| 2 | suite | 0 | f1e932734 | .ai/state/logs/T-2026-10-29-0852-r36-rest/suite-2.log | no |
| 3 | e2e | 0 | f1e932734 | .ai/state/logs/T-2026-10-29-0852-r36-rest/e2e-3.log | no |
| 4 | suite | 0 | d63dc06e8 | .ai/state/logs/T-2026-10-29-0852-r36-rest/suite-4.log | no |
| 5 | e2e | 0 | d63dc06e8 | .ai/state/logs/T-2026-10-29-0852-r36-rest/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS
- [HIGH] H1 A project whose human removed `.ai/policies/dialog.json` gets the dialog silently switched back on by the next `/project-update`. (`skills/project-update/update.py:1271` template walk → `three_way` → `create`; `0010_dialog_switch.py:22-24`) — Spec R36.1/R36.2 and `hooks/guard/dialog.py:10` define a missing file as off; the template walk re-creates any missing template file. Measured: a VERSION 10 scaffold without the file → dry run `create .ai/policies/dialog.json`, no 0010 hint, counted automatic, no `policy` line so /rr-setup --update never asks; with --apply the approval path is on again (opposite of R36.2) without R36.1's line. Direction: treat a missing dialog.json at schema ≥10 as the human's choice (skip it in the template walk past 0010), or make "off" mean enabled:false only and say so. — in_scope: yes
- [MEDIUM] M1 `skills/rr-ship/SKILL.md:3` (description: "never commits, pushes or approves") and `:104` (§3 "You never commit, push, merge or deploy") contradict the rewritten §2 — the A.2 refusal risk; test_c5_text_everywhere does not look for these. Direction: make them conditional on the switch, same words as §2. — in_scope: yes
- [MEDIUM] M2 Every updated project's own constitution still says "No agent commits, merges or deploys; a human approves outside the agent" (`update.py:125` constitution create-only) and 0010 turns the dialog on without saying so (`0010_dialog_switch.py:24`); block line allows a picked commit while C5 forbids it. Direction: 0010's hint says C5 in docs/sdlc/constitution.md should be amended when the dialog stays on. — in_scope: yes
- [MEDIUM] M3 The contract half (0009, `state.py start` → state.json, `state.py:226`) assumes every reader on the machine is ≥3.4b; v2.0.2 reads only current.json (`git show v2.0.2:skills/ai-task/state.py:205-206`). A dual-runtime project with Codex's home (or a plugin cache) on v2.x: its guards see no task after the move / any new start — silently disarmed; rollback to v2.x loses the task. update.py checks other homes for shared-file skew (`require_shared`, :482-514) but not this. Revert to 3.4b is fine (executed). Direction: refuse or hint when another installed home lacks the state.json reader. — in_scope: yes
- [MEDIUM] M4 Shipped text still names current.json as the task file: `agents/ai-reviewer.md.tmpl:55` (reviewer reads the mode from it), `skills/ai-init/templates/.ai/state/README.md:3,13,48`, `README.md:27-28,79,86` ("a later release moves it … this one already reads either" — now false), `docs/architecture.md:47,151`, `docs/faq.md:44`. Direction: update to state.json (legacy fallback where it matters), rebuild history. — in_scope: yes
- [LOW] L1 `tests/test_dialog_gate.py:964-967` TestC5Text narrower than R36.21: OLD lacks the old C5 sentence, the old .ai/AGENTS.md item and routing.md's "pipeline ends at human approval"; SKIP excludes all docs/sdlc/ (the constitution); git ls-files skips untracked. Direction: add them, narrow SKIP to docs/sdlc/{specs,plans,intent}/, include --others --exclude-standard. — in_scope: yes
- [LOW] L2 `tests/test_instruction_budget.py:265` safe-alone phrase moved to "the human runs them outside the agent" — pins only the fallback half. Direction: also assert "picked in the dialog" and "verbatim, once". — in_scope: yes
- [LOW] L3 `tests/test_project_update.py:563-569` test_state_json_already_there_is_untouched has no current.json and passes on the pre-change tree; the conflict branch is never run; `:571-594` "3.4b revert" imports today's state.py. Direction: add the both-files case (conflict, schema held at 8); run 3.4b's state.py from a git show copy. — in_scope: yes
- [LOW] L4 `update.py:1360-1365,1432` keep_original copies the git-ignored task state into `.ai/reports/project-update-<date>/original/.ai/state/current.json`, not ignored → `??` in git status; git add -A commits it; trips adopt's clean-status precondition. Direction: skip keep_original under .ai/state/ or ignore it. — in_scope: yes
- [LOW] L5 Shortened lines dropped qualifiers: project-block line (`instructions/stub.md:50` + 4 blocks) drops "verbatim, once"; `instructions/routing.md:49,133` drop it; scaffold C5 drops "as recorded by the harness". Unconditional texts remain: `skills/rr-status/SKILL.md:27-28`, `skills/rr-plan/SKILL.md:73-74`, `docs/architecture.md` ("refuses `state.py approve` … outright"), `docs/faq.md:475`, `.codex-plugin/plugin.json:24`. Direction: restore "verbatim, once" where bytes allow (CLAUDE.block is 1109 of 2048 B), make the listed lines conditional on the switch. — in_scope: yes
- [LOW] L6 0010 creates a policy file while a task is in flight, pinned as correct by `test_migration_0010.py::test_in_flight_state`; WHY_TASK (`hooks/guard/paths.py:48-54`) says policies are frozen during a task; Q9 accepted switch-on but not mid-task. Direction: hint when a task is in flight, or a `policy` line so /rr-setup asks. — in_scope: yes
- [INFO] I1 `tests/test_dialog_gate.py:306-316` test_scaffolded_project_is_on copies the template instead of running the scaffold (scaffold-ai.sh checked by hand: writes it, VERSION 10). — in_scope: yes
- [INFO] I2 The human's C5 (`docs/sdlc/constitution.md:10`, 229 B) exceeds the 200 B principle cap (`render_instructions.py:546`); constitution check exits 1 here; not new (C6 215 B). — in_scope: yes
- [INFO] I3 No lock between update.py's move and a concurrent `state.py save` (`update.py:1425-1458`, `state.py:422-433`); same class as patch_state today. — in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: inside the approved, amended plan; gaps are texts/tests the rows implied but did not list, plus one behavioural hole from the template walk (H1).
```

closed by a green run: H1

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on d63dc06e8 (run 4) · (b) green — 52 changed files, all in the task's files
gate: requested G1 at 2026-10-29T10:02:48Z; approved by Ivan Kakurov at 2026-10-29T10:28:37Z via terminal
confirm: none
handoffs: 8 · suite runs: 3 · review passes: 1
