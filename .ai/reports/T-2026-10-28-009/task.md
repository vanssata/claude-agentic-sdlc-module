# T-2026-10-28-009 — R36 step 7d1: the inert hook half of the dialog — consent-ledger module, PostToolUse recorder, Stop blocker, payload fields, decision fast path and registrations in both routes; off or no decision open changes no decision

feature · full · started 2026-10-28T17:06:11Z · claude

## Weight

```
scope          2  hooks/guard/dialog.py matches hot_paths hooks/**
behaviour      2  registers hooks on every tool and on Stop in every installed user project (C6, plan row 7d1 expe
reversibility  0  git revert returns everything
domain         1  writes the consent ledger an approval path will later trust (7d2); no secrets or auth handled (d
novelty        1  new hook entry point and Stop/PostToolUse events; ledger rules mirror state.py's 7c reader (decl
coverage       1  3 of 7 code files have a test
W 7 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-28T17:06:11Z

## Plan

files: hooks/guard/dialog.py, hooks/guard/decision.py, hooks/dialog-gate.py, hooks/guard/common.py, hooks/ai-guard.py, hooks/context-guard.py, settings.common.json, codex/hooks.json, hooks/hooks.json, hooks/codex-hooks.json, bin/riskrails.js, docs/hook-performance.md, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/guard_harness.py, tests/test_context_guard.py, tests/test_codex_install.py, .ai/project/known-risks.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/c5d28dfa-92c4-472a-939f-2111ad61371f/scratchpad/review-1.md, hooks/guard/paths.py, tests/fixtures/path-guard/1*-dialog-gate-*.json, tests/fixtures/guard-characterization/golden.txt, tests/fixtures/guard-characterization/moved-3.4.json
tests: tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_context_guard.py, tests/test_codex_install.py, tests/test_install_routes.py
- s1 · hooks/guard/dialog.py, hooks/guard/common.py, tests/guard_harness.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, .ai/project/known-risks.md · tests/test_dialog_gate.py, tests/test_dialog_contract.py · done
- s2 · hooks/dialog-gate.py, hooks/guard/decision.py, hooks/ai-guard.py, hooks/context-guard.py, tests/test_dialog_gate.py, tests/test_context_guard.py · tests/test_dialog_gate.py, tests/test_context_guard.py · done
- s3 · settings.common.json, codex/hooks.json, hooks/hooks.json, hooks/codex-hooks.json, bin/riskrails.js, tests/test_codex_install.py, docs/hook-performance.md, tests/test_dialog_gate.py · tests/test_dialog_gate.py, tests/test_codex_install.py, tests/test_install_routes.py · done
amended 2026-10-28T17:32:20Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/c5d28dfa-92c4-472a-939f-2111ad61371f/scratchpad/review-1.md — the STRONG review report is too long for an inline command; state.py review --report reads it from this scratch file (not in git)
amended 2026-10-28T18:00:42Z: +hooks/guard/paths.py, tests/fixtures/path-guard/1*-dialog-gate-*.json, tests/fixtures/guard-characterization/golden.txt — Q1=A: review H1 — R36.11's deny on a Bash command that runs dialog-gate.py lands in 7d1; additive path-guard fixtures and their golden records
amended 2026-10-28T18:09:35Z: +tests/fixtures/guard-characterization/moved-3.4.json — H1 fix (Q1=A): the new dialog-gate deny moves three path-guard decisions against the frozen shell guards on purpose; test_guard_differential's documented list of deliberate moves names them

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## Q1. H1: a Bash command that pipes a forged answer into dialog-gate.py writes a pick today; where does the deny land?
asked: 2026-10-28T17:34:43Z · stage: implementation
context: hooks/dialog-gate.py:74-98; spec R36.11, R36.22(b); plan D5
A. in 7d1 — pull R36.11's 'Bash naming dialog-gate.py -> deny' into this task (amend: hooks/guard/paths.py, tests/test_ai_path_guard.py, additive path-guard fixtures and golden entries; behaviour 1) (recommended)
B. stays in 7d2 — record the window in known-risks.md and the rule that 7d1 is never merged or released without 7d2
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-28T18:00:00Z

## G1. Approve T-2026-10-28-009 for implementation? (gate: human_approval)
asked: 2026-10-28T18:15:55Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]:

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 00becdccb | .ai/state/logs/T-2026-10-28-009/step-1.log | no |
| 2 | step | 0 | a24918385 | .ai/state/logs/T-2026-10-28-009/step-2.log | no |
| 3 | step | 1 | 22d376f01 | .ai/state/logs/T-2026-10-28-009/step-3.log | no |
| 4 | step | 0 | 78632e4c7 | .ai/state/logs/T-2026-10-28-009/step-4.log | no |
| 5 | suite | 1 | 78632e4c7 | .ai/state/logs/T-2026-10-28-009/suite-5.log | no |
| 6 | suite | 0 | e33d95dc5 | .ai/state/logs/T-2026-10-28-009/suite-6.log | no |
| 7 | e2e | 0 | e33d95dc5 | .ai/state/logs/T-2026-10-28-009/e2e-7.log | no |
| 8 | step | 0 | 99f143a98 | .ai/state/logs/T-2026-10-28-009/step-8.log | no |
| 9 | suite | 1 | 99f143a98 | .ai/state/logs/T-2026-10-28-009/suite-9.log | no |
| 10 | step | 0 | 9736fc356 | .ai/state/logs/T-2026-10-28-009/step-10.log | no |
| 11 | suite | 0 | 4b461cd8a | .ai/state/logs/T-2026-10-28-009/suite-11.log | no |
| 12 | e2e | 0 | 4b461cd8a | .ai/state/logs/T-2026-10-28-009/e2e-12.log | no |

suite passing · e2e passing · suite runs 4

## Review

### Pass 1 — STRONG, pass_with_findings

```
## FINDINGS
- [HIGH] H1 hooks/dialog-gate.py:74-98, hooks/guard/dialog.py:387-434 — 7d1 ships a consent-ledger writer reachable by a plain, named Bash command, with its deny deferred to 7d2. Ran: ai-guard ALLOWS `echo {} | python3 hooks/dialog-gate.py` and `python3 -I -S "$HOME/.claude/hooks/dialog-gate.py" < /tmp/x.json`; piping a forged PostToolUse (any session_id, empty tool_use_id, any transcript_path) into dialog-gate.py wrote `offer` + `pick` C1/C2 to consent.jsonl. The equivalent redirect / interpreter one-liner is DENIED today, so before 7d1 forging a pick needed a constructed command and now it does not. Completion: today's ai-guard ALLOWS `state.py … verify --by`, `review --by`, `start --mode <lower> --by`, `profile set`, `reject` (ran); their only protection is human_route(), and 7c's dialog_pick() (state.py:2654) accepts a live pick before the agent-marker refusal. The agent can open such a decision itself (SUITE_BUDGET refusal, a lowering `start --mode`), forge the pick, run the command — lowering its own mode or overriding the suite budget with no human. `approve` stays stopped by the path guard's APPROVE_RE until 7d2. In-model per the spec itself (§Design "invoking the hook script is denied", R36.11, R36.22(b)), not a "constructed command". Reachability: only with a human-enabled .ai/policies/dialog.json; D4 says no template before 7f, but this machine's ~/.claude/riskrails/profile.json already carries dialog.tool; no known-risks entry records the interim window (the two added entries cover other risks). Direction: pull R36.11's "Bash naming dialog-gate.py → deny" (behaviour 1, additive golden) into 7d1, or record the window in known-risks and make sure 7d1 is never released without 7d2. — in_scope: yes
- [MEDIUM] M1 hooks/ai-guard.py:59-68 — a missing or broken guard/decision.py disables git/paths/scope for every tool. `__import__("guard.decision")` sits outside the per-check try; ImportError/SyntaxError reaches the outer except → return 0. Ran: on a copy of hooks/ with guard/decision.py deleted, and with a syntax error, `git push --force origin main` went DENY → ALLOW. Realistic via a skewed install: claudeApply writes hooks/*.py (incl. ai-guard.py) before guard/*.py, Codex the same; an interrupted install or a hand-copied new ai-guard.py silently disables every guard. Contradicts decision.py's own "git, paths and scope must still run"; test_later_checks_still_run covers only the healthy module. Direction: wrap the decision check's import+call in its own broad try that continues. — in_scope: yes
- [MEDIUM] M2 hooks/guard/dialog.py:37-38,158 — on the plugin route the recorder rejects every state.py pick. STATE_PY is derived from the hook's location; on the Claude plugin route hooks run from ${CLAUDE_PLUGIN_ROOT} (plugin cache) while skills run $AI_HOME/skills/ai-task/state.py (npx keeps the scripts; bin/riskrails.js:886-891, rr-build/SKILL.md:13-16); likewise a Codex session in a dual install (AI_HOME resolves to ~/.claude first). Ran: with repo hooks, validate_label('python3 /home/vanssa/.claude/skills/ai-task/state.py --root /p approve --by ivan') returns an error; the repo path returns None. Effect: every approve / verify|review --by / profile set pick there is recorded as decline "label" — fails closed but R36.10 never works. The pin adds no security: dialog_pick() already checks realpath(label script) == its own __file__. test_label_rule_matches_state_py uses the repo STATE for both sides. Direction: hook checks the label's form only (python3, -I/-S, basename state.py, allowed subcommand); path identity stays state.py's. — in_scope: yes
- [LOW] L1 hooks/guard/dialog.py:138-143 — label rule looser than state.py's on Unicode: str.isalnum() vs the ASCII PUSH_REF_RE / NPX_PACKAGE_RE. Ran: `git push origin mäin`, `git push origin ma٣in`, `npx riskrails@１.0 --yes` accepted by hooks, rejected by state.py. The contract test covers live_picks, not validate_label. Only a decision not from state.py reaches it. Direction: same ASCII regexes; validate_label into the contract test. — in_scope: yes
- [LOW] L2 hooks/guard/dialog.py:410 — record() accepts a payload with no tool_use_id / transcript_path. Ran: two identical payloads with tool_use_id "" merged into one round, chain [C1 o1, C3 o1, C2 o2, C4 o2]; after C1 is used the next live pick is a second "git commit" (C3) instead of push (C2). Such picks also make `consent audit` report unverifiable instead of mismatch (state.py:2879), weakening R36.22(i). Real payloads always carry both (spike); only a forged payload reaches it. Direction: write nothing when tool_use_id or transcript_path is empty. — in_scope: yes
- [LOW] L3 hooks/guard/dialog.py:216-223 — the question key leaves out option descriptions, so a dialog with misleading descriptions still records picks. Ran: a pick recorded for a command whose description read "CANCEL - nothing runs". Within R36.6 as written, but it rests on 7d2's R36.5 PreToolUse check, which fails open by design (R36.12) and, on old Codex installs, never fires on request_user_input (kept matcher, known-risks). Direction: include descriptions in the key, or add the dependency to the Codex-matcher known risk. — in_scope: yes
- [LOW] L4 hooks/guard/dialog.py:423-433 — a round's lines are written one at a time under the lock; an OSError mid-round (e.g. the 4096-byte refusal) leaves `offer` plus only the first picks, a partial consent round. Direction: size-check every line before the first write. — in_scope: yes
- [INFO] I1 hooks/guard/dialog.py:106-117, dialog-gate.py:45-71 — hooks' switch and state.py's disagree on Codex: hooks turn on from profile.json dialog.tool alone; state.py's dialog_on also needs CODEX_THREAD_ID (unverified). The hooks ignore decision.runtime/session: a decision opened by one Claude session Stop-blocks every other session, and the Codex runtime, in the same root; on Codex the agent is pointed at a route its state.py may treat as off. The Codex Stop output shape (decision: block) is not in the spike. — in_scope: yes
- [INFO] I2 docs/hook-performance.md new row — the "12.5 ms before 7d1" baseline is misleading: before 7d1 Grep/Glob/MCP spawned no ai-guard at all; the real added cost is one whole ~13 ms process per non-file tool call. — in_scope: yes
- [INFO] I3 hooks/context-guard.py:525-529 — prompt_count now written whenever a task is in flight, even with the dialog off; a new key in session.json, no reader affected (read_session, human_turn checked); with no task, session.json created holding only prompt_count — harmless. — in_scope: yes
- [INFO] I4 tests/test_codex_install.py:361 — narrowing the -gate.py count is justified (mergeHooks dedupes by command string), but no test now pins that a reinstall does not double dialog-gate.py. — in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside plan row 7d1: every file is the plan's, and the test edits adapt pinned literals without weakening them. H1 is a sequencing gap between D5 (deny in 7d2) and what 7d1 makes reachable, not scope creep. M1 and M2 are defects inside 7d1's own files.
```

closed by a green run: H1

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on 4b461cd8a (run 11) · (b) green — 25 changed files, all in the task's files
gate: requested G1 at 2026-10-28T18:15:55Z; approved by - at - via -
confirm: none
handoffs: 9 · suite runs: 4 · review passes: 1
