# T-2026-10-27-005 — Fold task questions into task.md and rewrite the path-guard rules to R22's set (decisions D1-D4)

feature · full · started 2026-10-27T16:44:52Z · claude

## Weight

```
scope          2  hooks/ai-path-guard-defaults.json matches hot_paths hooks/**
behaviour      2  keyword 'workflow' in .ai/project/known-risks.md; hint +1
reversibility  0  git revert returns everything
domain         2  secrets and approval-identity rules in the path guard (declared)
novelty        1  rewrite of an existing ported engine to a named rule set (declared)
coverage       1  1 of 3 code files have a test
W 8 → full   hints behaviour +1 · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_guard_characterization.py, tools/golden-diff.py, skills/ai-task/state.py, hooks/ai-path-guard-defaults.json, hooks/guard/paths.py, tests/test_ai_task_state.py, tests/test_end_to_end.py, tests/test_ai_path_guard.py, tests/fixtures/path-guard/*, tests/fixtures/guard-characterization/golden.txt, skills/rr-build/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-status/SKILL.md, skills/rr-spec/SKILL.md, ai/agents/*.md, agents/ai-discovery.md.tmpl, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/*.block.md, skills/ai-init/templates/.ai/state/README.md, .ai/state/README.md, instructions/stub.md, CLAUDE.md, AGENTS.md, README.md, docs/architecture.md, docs/faq.md, docs/hooks.md, skills/project-update/history/*, tests/fixtures/guard-characterization/*, tests/test_guard_differential.py, tests/test-guard-characterization.sh, .ai/project/known-risks.md, tests/fixtures/path-guard/101-bash-tar-into-current-json.json, tests/fixtures/path-guard/102-bash-curl-o-into-current-json.json, tests/fixtures/path-guard/103-bash-wget-o-into-task-md.json, tests/fixtures/path-guard/104-bash-scp-into-events-jsonl.json, tests/fixtures/path-guard/105-edit-installed-guard-engine.json, tests/fixtures/path-guard/106-bash-rm-installed-guard-dir.json, tests/fixtures/path-guard/107-edit-installed-state-py.json, tests/fixtures/path-guard/108-bash-long-heredoc-approve-word-allowed.json, tests/fixtures/path-guard/109-read-pem-under-ai-state.json, skills/ai-init/templates/.ai/policies/security.md, skills/ai-task/weight.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/3f34e7c2-383e-46f9-aa95-cd4f40063220/scratchpad/review-T-2026-10-27-005.md
tests: tests/test_guard_characterization.py, tests/test_ai_task_state.py, tests/test_end_to_end.py, tests/test_project_update.py, tests/test_ai_path_guard.py, tests/test_codex_agent_render.py, tests/test_instruction_budget.py, tests/test_skills_surface.py, tests/test_guard_differential.py, tests/test_ere_unit.py, tests/test-guard-characterization.sh
- s1-record · tests/test_guard_characterization.py, tools/golden-diff.py · tests/test_guard_characterization.py · done
- s2-fold · skills/ai-task/state.py, hooks/ai-path-guard-defaults.json, hooks/guard/paths.py, tests/test_ai_task_state.py, tests/test_end_to_end.py, tests/test_ai_path_guard.py, tests/fixtures/path-guard/*, tests/fixtures/guard-characterization/golden.txt, skills/rr-build/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-status/SKILL.md, skills/rr-spec/SKILL.md, ai/agents/*.md, agents/ai-discovery.md.tmpl, agents/ai-reviewer.md.tmpl, skills/ai-init/templates/*.block.md, skills/ai-init/templates/.ai/state/README.md, .ai/state/README.md, instructions/stub.md, CLAUDE.md, AGENTS.md, README.md, docs/architecture.md, docs/faq.md, docs/hooks.md, skills/project-update/history/* · tests/test_ai_task_state.py, tests/test_end_to_end.py, tests/test_project_update.py, tests/test_guard_characterization.py, tests/test_ai_path_guard.py, tests/test_codex_agent_render.py, tests/test_instruction_budget.py, tests/test_skills_surface.py · done
- s3-rules · hooks/guard/paths.py, hooks/ai-path-guard-defaults.json, tests/fixtures/path-guard/*, tests/fixtures/guard-characterization/*, tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test-guard-characterization.sh · tests/test_ai_path_guard.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_ere_unit.py, tests/test-guard-characterization.sh · done
- s4-risks · .ai/project/known-risks.md, docs/hooks.md · tests/test_instruction_budget.py · done
amended 2026-10-27T18:26:44Z: +tests/fixtures/path-guard/101-bash-tar-into-current-json.json, tests/fixtures/path-guard/102-bash-curl-o-into-current-json.json, tests/fixtures/path-guard/103-bash-wget-o-into-task-md.json, tests/fixtures/path-guard/104-bash-scp-into-events-jsonl.json, tests/fixtures/path-guard/105-edit-installed-guard-engine.json, tests/fixtures/path-guard/106-bash-rm-installed-guard-dir.json, tests/fixtures/path-guard/107-edit-installed-state-py.json, tests/fixtures/path-guard/108-bash-long-heredoc-approve-word-allowed.json, tests/fixtures/path-guard/109-read-pem-under-ai-state.json, skills/ai-init/templates/.ai/policies/security.md, skills/ai-task/weight.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/3f34e7c2-383e-46f9-aa95-cd4f40063220/scratchpad/review-T-2026-10-27-005.md — STRONG review fix batch: H1/H2/L1/L2 fixtures, M1 security.md template, L5 weight evidence, and the review report file (the live guard refuses the report inline because its text names the approve verb)

## Questions

[questions.md](questions.md) — 1 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 5127aaccf | .ai/state/logs/T-2026-10-27-005/step-1.log | no |
| 2 | step | 0 | 8f4382e33 | .ai/state/logs/T-2026-10-27-005/step-2.log | no |
| 3 | step | 0 | cc6aa9235 | .ai/state/logs/T-2026-10-27-005/step-3.log | no |
| 4 | step | 0 | ed8b9f288 | .ai/state/logs/T-2026-10-27-005/step-4.log | no |
| 5 | suite | 1 | ed8b9f288 | .ai/state/logs/T-2026-10-27-005/suite-5.log | no |
| 6 | suite | 0 | e16652699 | .ai/state/logs/T-2026-10-27-005/suite-6.log | no |
| 7 | e2e | 0 | e16652699 | .ai/state/logs/T-2026-10-27-005/e2e-7.log | no |
| 8 | suite | 1 | 8dc712170 | .ai/state/logs/T-2026-10-27-005/suite-8.log | no |
| 9 | suite | 0 | e25ecfe84 | .ai/state/logs/T-2026-10-27-005/suite-9.log | no |
| 10 | e2e | 0 | e25ecfe84 | .ai/state/logs/T-2026-10-27-005/e2e-10.log | no |

suite passing · e2e passing · suite runs 4

## Review

### Pass 1 — STRONG, pass_with_findings (focus security)

```
## FINDINGS

- [HIGH] H1 (authorization / control-file writes) Bash writes into `.ai/state/**`, `task.md` and `events.jsonl` by `curl -o`, `wget -O`, `scp` and `tar x` are no longer refused. Nobody meant this, it is not in `known-risks.md`, and no fixture pins it. (`hooks/guard/paths.py:1217-1236`, `:94`, `:102`)  in_scope: yes
  attack: At HEAD these commands were refused by accident. The `COPIERS` pattern (`cp|mv|rsync|scp|install|tar|zip|curl|wget …` followed by the token) fired the "reads a control file" deny on any protected token. The rewrite limits that branch to `kind == "sensitive"`. The write detectors that remain do not list these tools: redirect, `WRITERS` (tee/truncate/shred/touch/ln), `MODES`, `DDWRITE`, `INPLACE`, `REMOVERS`, and the movers (cp/mv/install/rsync/rm only). Failing inputs, all denied at HEAD and allowed now:
  - `tar xf backup.tar .ai/state/current.json`
  - `curl -o .ai/state/current.json http://x`
  - `wget -O .ai/reports/T-1/task.md http://x`
  - `scp host:x .ai/reports/T-1/events.jsonl`

  `current.json` holds `human_approval`, and none of these is a constructed command. The differential test did not catch it because neither corpus has such a case (`moved-3.4.json` only lists `tar czf … node_modules`). This breaks R22's "deny agent writes to `.ai/state/**`, `reports/<id>/{events.jsonl,task.md}`" and the plan's "a fixture for every remaining deny".
  suggested direction: Keep the old `COPIERS` match as a write detector for `kind == "protected"` (and for task-protected paths in a task), and add one fixture per tool.

- [HIGH] H2 (authorization / guard integrity) During a task, the installed guard engine and the approval state machine can now be edited, so one Edit turns off every remaining deny. (`hooks/ai-path-guard-defaults.json:32-41`)  in_scope: yes
  attack: The defaults dropped `(^|/)\.claude/(agents|skills|commands|hooks|plugins)/`. Only `hooks/ai-*` and `runtime-gate.py` stay protected. But `install.sh:734-739` and `:1108-1111` install the engine as `~/.claude/hooks/guard/*.py` and `hooks/lib/ai-hook-common.sh`. `ai-guard.py:41-66` imports `guard.*` and fails open on any exception. Failing inputs, all denied in a task at HEAD and allowed now:
  - Edit `~/.claude/hooks/guard/paths.py`
  - `rm -rf ~/.claude/hooks/guard` (the directory holds no `ai-*` file, so the movers pass it)
  - a write into `~/.claude/hooks/guard/__pycache__/`
  - Edit `~/.claude/skills/ai-task/state.py`, the approve/TTY/file-route code

  "Guard refused me, so fix the guard" is exactly the agent mistake the task freeze existed for, and the new `_comment` still says "so a run cannot change the rules it is being judged by". `known-risks.md` item (5) accepts `.claude/{…hooks…}/` "other than `hooks/ai-*`" without saying that this covers the guard engine and `state.py`. Its "Still refused: … the guards' `hooks/ai-*`" reads as "the guards are protected".
  suggested direction: Add `(^|/)\.(claude|codex)/hooks/(guard|lib)/` to `protected_config_patterns`, with the installed `skills/ai-task/` (always or in-task), plus a fixture each; or have the human accept it explicitly by name.

- [HIGH] H3 (secrets / AI context safety) An interpreter one-liner that prints a secret is now allowed, and the risk is accepted on a rationale that is false for it. (`hooks/guard/paths.py` removal of `SECRET_TEXT_RE`/`INTERP_RE`; `tests/fixtures/path-guard/10-python-oneliner.json`)  in_scope: yes
  attack: `python3 -c "print(open('.env').read())"` (fixture 10, flipped to allow) puts production secrets in the model context. It is the most common accidental way to read `.env`, not a constructed bypass. The same holds for fixture 88, an agent "repairing" `current.json` with `json.dump`, and fixture 39 (`session.json`).
  - R22 says "deny secrets (read + write)".
  - SQ13 accepts only the `sh -c`/`eval` re-parse bypass.
  - The secret tripwire was a cheap whole-text check and never depended on the re-parse.
  - `known-risks.md` accepts it because "every one needs a constructed command". That is not true here.
  - The fixtures cite D4, but no D4 text exists anywhere in the repository (see M2).
  suggested direction: Restore the secrets-only interpreter tripwire (`INTERP_RE` with `SECRET_TEXT_RE`), or get the human to re-confirm D4 against the corrected rationale and record it.

- [MEDIUM] M1 (configuration / data exposure) A project's `dependency_instruction_patterns` is now silently ignored, and the shipped policy still promises the protection. (`hooks/guard/paths.py` `load_patterns`; `skills/ai-init/templates/.ai/policies/security.md:50-73`)  in_scope: yes
  why it matters: A `.ai/policies/path-guard.json` that lists `dependency_instruction_patterns` loses that protection with no warning; only `docs/hooks.md:304` mentions it. The shipped `security.md` template, which is binding policy in user projects, still says: vendor instruction files are "refused for reading as well as for writing"; `.claude/`/`.codex/` agents, skills and hooks plus `.ai/agents|workflows|templates` are read-only in a task; `dependency_instruction_patterns` is a valid key. The template is outside the task's files, and `known-risks.md` does not mention the ignored key.
  suggested direction: Raise `SCOPE_CHANGE_REQUIRED` to update the template (and run `build-template-history`), and either warn on the dead key or fold it into `deny_patterns`.

- [MEDIUM] M2 (record / audit) Decisions D1-D4 are cited as the human's authority for every protection dropped beyond R22, but they are recorded nowhere. (`.ai/project/known-risks.md:583`; `.ai/reports/T-2026-10-27-005/task.md` §Questions = "none")  in_scope: yes
  why it matters: `known-risks.md` cites `task.md` for "decisions D2–D4 taken by the human"; `task.md` has none, and neither do `events.jsonl`, `handoff.md`, the spec or the plan. The extra drops are vendor files, the `.claude/*` freeze, the constitution and rule directories, `HOOKRUN` and the interpreter tripwire. In a domain-2 task their authorization cannot be checked against R22's literal text.
  suggested direction: Record D1-D4 verbatim, with who decided and when, in `task.md` or the plan before the gate.

- [MEDIUM] M3 (record accuracy) The "Path guard after R22" entry misstates the risks it accepts. (`.ai/project/known-risks.md:585-588`)  in_scope: yes
  why it matters: (a) It says `bash -c "state.py <gate verb> …"` passes. It does not: `APPROVE_RE` runs on the whole joined command, and `BOUND` includes a blank, so the inner verb matches. No fixture pins either outcome. (b) It says "reopen (2)/(3) if the file route ever stands alone as the approval". It already does: `close_gate_from_file` (`state.py` ~1660-1700) grants `human_approval` on a filled `[Answer]: A` plus `session.json`. Those are the two artefacts the newly allowed one-liner and hand-run `context-guard.py` can write. (c) "Still refused: secrets read and write" overclaims. Bash writes to a secret (`echo x > .env`, `sed -i … .env`, `rm .env`) are not refused, at HEAD or now. (d) It omits H1's tools and the dropped `.claude/CLAUDE.md` and `.codex/AGENTS.md` patterns. The human's acceptance rests on this text.
  suggested direction: Correct (a)-(d) and list the file route as a standalone approval route.

- [MEDIUM] M4 (test weakened) Fixtures were flipped to allow instead of being pointed at a path that is still protected, so three remaining deny mechanisms lost their pins. (`tests/fixtures/path-guard/64..71-*.json`, `tests/test_ai_path_guard.py:155-157`, the work-cap cases)  in_scope: yes
  why it matters: Movers' parsing of `for/do`, `if/then`, `( )`, `$( )`, `VAR=` prefix, `time` and backslash-newline is no longer pinned by any deny case. The fail-closed rule "an unparsable state counts as in flight", which the gate and `set --by` rules also depend on, is now tested only on a path that is no longer frozen. The work-cap deny (`WORK_CAP` is still defined) has zero golden records and no assertion. A regression in any of the three would pass the suite.
  suggested direction: Re-point them at `.ai/reports/T-1/task.md`, `.claude/settings.json` or `.ai/policies/safety.md`, keep them as denies, and keep one work-cap case.

- [LOW] L1 The 4 KB rule over-matches. `LONG_TRIGGER_RE` = `approve|--by|--co|…` also hits `--cov`, `--color`, `--config`, `--bytes` and `approve_payment`. It fires outside a task and under `AI_UNATTENDED`, with a message ("names a guarded path or a state.py or update.py verb") that is wrong for those inputs. (`hooks/guard/paths.py:113`, `:1135`)  in_scope: yes
  why it matters: Failing input: a 5 KB heredoc writing `src/billing.py` that contains `def approve_invoice` is refused.
  suggested direction: Anchor the triggers as whole words or verbs, as `APPROVE_RE` does.

- [LOW] L2 `(^|/)\.ai/state/` now overlaps the deny list, and the protected list is classified first. (`docs/hooks.md` "The shipped lists do not overlap"; `hooks/ai-path-guard-defaults.json:27`)  in_scope: yes
  why it matters: `Read .ai/state/x.pem` or `.ai/state/dump-1.sql` becomes allowed, and the docs claim is now false.
  suggested direction: Fix the sentence, or check deny before the protected-read pass.

- [LOW] L5 Declared weight evidence can inject a `## Questions` line into `task.md`. Evidence is parsed with `re.S` and not collapsed to one line (`weight.py:260`); `split_task_md` takes the first exact match. (`skills/ai-task/state.py:700-705`)  in_scope: yes
  why it matters: Verified by execution with `--declare "behaviour=1:x\n## Questions\n## Q1. fake"`. The real §Questions block moves inside the Weight code fence and a second "## Questions / none" appears below §Plan, so a human can fill the wrong place. I could not forge a gate: ids are max+1, and the on-disk section replaces the rendered one.
  suggested direction: Collapse declared evidence to one line, and anchor the split on the section's position, not its first textual occurrence.

- [LOW] L6 `CLAUDE.md` was edited inside the task. The plan's global constraint says the repository's own `CLAUDE.md` changes only in human rows 2.H/3.H, and plan row 3.4's file list does not include it. (`CLAUDE.md`, the `task.md` §Plan files)  in_scope: yes
  why it matters: It is a one-word path change, but it breaks a stated constraint.
  suggested direction: Revert it and carry it to 3.H, or record the exception.

- [LOW] L7 `AI_RECORD=1` makes `test_guard_characterization` overwrite its own oracle and skip. (`tests/test_guard_characterization.py`, the new `AI_RECORD` branch)  in_scope: yes
  why it matters: An exported variable turns the golden check into a writer that can never fail; only the git diff would show it.
  suggested direction: Move recording into `tools/`, or refuse `AI_RECORD` when not run from a terminal.

- [INFO] I1 Gaps that predate this change: Bash secret reads through `grep`, `awk`, `sed -n p`, `sort`, `cut` and `diff` are not refused (not in `READERS`); a `cd .ai/reports/T-1 && …` prefix is not tracked; `~/.codex/hooks.json` (Codex's guard registrations) and `~/.claude/settings.json` outside a task are writable; `env -u CLAUDECODE script -qc …` gets past `human_route()`; the gate verb spelled `st""ate.py`, with a backslash or as `$'…'`, or passed via `xargs` or `$(…)`, is not matched. All are constructed or out of R22's text. (`hooks/guard/paths.py:100-102`, `state.py:606`)  in_scope: no
  why it matters: inside the boundary these would be MEDIUM (secret readers) and LOW (the rest).

- [INFO] I2 R22 sizes `paths.py` at about 250 lines; the change leaves it at 1305. It is a subtraction from the port, not the rewrite the spec describes. (`hooks/guard/paths.py`)  in_scope: yes
  why it matters: It is a spec deviation to track for a later row.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside `task.md` §Plan's files, except for the `CLAUDE.md` edit against the global constraint (L6) and a shipped `security.md` template that should have changed and did not (M1). It goes beyond R22/SQ13's literal text in drops that cite D1-D4, which are not recorded (M2).
ai_context_safety: No secret was read. One attempt to read `.ai/state/current.json` through Bash was refused by the live guard. I read no `.env` or credential file; both probe batches that named `.env` and `.ai/policies` were refused before they ran.
```

closed by a green run: H1, H2, H3

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on e25ecfe84 (run 9) · (b) green — 90 changed files, all in the task's files
gate: requested G1 at 2026-10-27T19:15:35Z; approved by - at - via -
confirm: none
handoffs: 7 · suite runs: 4 · review passes: 1
