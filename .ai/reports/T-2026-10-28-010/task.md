# T-2026-10-28-010 — R36 7d2: the consuming half of the dialog hooks — open-decision gate bound to its session, git consent rule, path-guard pass-through for a live pick, automatic fallback, Codex matcher on reinstall, 7d1 review L1-L4

feature · full · started 2026-10-28T19:02:37Z · claude

## Weight

```
scope          2  tests/test_guard_characterization.py referenced from 12 files
behaviour      2  a live pick lets through git commit/push and state.py approve, verify --by, review --by, start -
reversibility  0  git revert returns everything
domain         2  authorization: changes who may approve, commit and override budgets in every user project with t
novelty        1  the ledger reader and gate follow 7c/7d1 interfaces already in the tree; no new dependency (decl
coverage       1  4 of 8 code files have a test
W 8 → full   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/fixtures/guard-characterization/golden.txt, hooks/guard/dialog.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_dialog_consent.py, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/guard_harness.py, tests/fixtures/git-guard/22-git-commit-no-consent.json, tests/fixtures/git-guard/23-git-commit-consent.json, tests/fixtures/git-guard/24-git-push-main-with-consent.json, tests/fixtures/git-guard/25-git-commit-no-verify-with-consent.json, tests/fixtures/git-guard/26-git-commit-consent-quoted.json, tests/fixtures/path-guard/*-consent-*.json, tests/fixtures/codex-hooks/*-consent-*.json, hooks/guard/decision.py, hooks/ai-guard.py, hooks/dialog-gate.py, hooks/guard/git.py, hooks/guard/paths.py, skills/ai-task/state.py, tests/test_ai_task_state.py, .ai/project/known-risks.md, bin/riskrails.js, tests/test_codex_install.py, tests/fixtures/dialog/consent/*.json
tests: tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_ai_task_state.py, tests/test_codex_install.py
- s1-characterize · tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/fixtures/guard-characterization/golden.txt · tests/test_guard_characterization.py, tests/test_guard_differential.py · done
- s2-7d1-lows · hooks/guard/dialog.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py · tests/test_dialog_gate.py, tests/test_dialog_contract.py · done
- s3-tests-first · tests/test_dialog_consent.py, tests/test_dialog_gate.py, tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/guard_harness.py, tests/fixtures/git-guard/22-git-commit-no-consent.json, tests/fixtures/git-guard/23-git-commit-consent.json, tests/fixtures/git-guard/24-git-push-main-with-consent.json, tests/fixtures/git-guard/25-git-commit-no-verify-with-consent.json, tests/fixtures/git-guard/26-git-commit-consent-quoted.json, tests/fixtures/path-guard/*-consent-*.json, tests/fixtures/codex-hooks/*-consent-*.json, tests/fixtures/guard-characterization/golden.txt · tests/test_dialog_consent.py, tests/test_dialog_gate.py · done
- s4-gate · hooks/guard/decision.py, hooks/guard/dialog.py, hooks/ai-guard.py, hooks/dialog-gate.py · tests/test_dialog_gate.py, tests/test_dialog_consent.py, tests/test_dialog_contract.py · done
- s5-git-paths · hooks/guard/git.py, hooks/guard/paths.py · tests/test_ai_git_guard.py, tests/test_ai_path_guard.py, tests/test_dialog_consent.py, tests/test_guard_characterization.py · done
- s6-state-fallback-session · skills/ai-task/state.py, tests/test_ai_task_state.py, .ai/project/known-risks.md · tests/test_ai_task_state.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py · done
- s7-codex-matcher · bin/riskrails.js, tests/test_codex_install.py · tests/test_codex_install.py, tests/test_install_routes.py · done
amended 2026-10-28T19:08:19Z: +tests/fixtures/dialog/consent/*.json — consent cases need a project with dialog.json, decision.json and a ledger; the git-guard/path-guard/codex-hooks fixture dirs are run stateless by test_ai_git_guard, test_ai_path_guard and the golden corpus, where a 'deny without consent' case would be allowed

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-28-010 for implementation? (gate: human_approval)
asked: 2026-10-28T19:45:43Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-10-28T20:02:36Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 33a37fe6f | .ai/state/logs/T-2026-10-28-010/step-1.log | no |
| 2 | step | 1 | 4f24f230b | .ai/state/logs/T-2026-10-28-010/step-2.log | yes |
| 3 | step | 0 | 775c5b48a | .ai/state/logs/T-2026-10-28-010/step-3.log | no |
| 4 | step | 1 | 0374dc330 | .ai/state/logs/T-2026-10-28-010/step-4.log | yes |
| 5 | step | 1 | 26c69fe8d | .ai/state/logs/T-2026-10-28-010/step-5.log | no |
| 6 | step | 1 | 2fabc23d2 | .ai/state/logs/T-2026-10-28-010/step-6.log | no |
| 7 | step | 0 | 07e9bb88b | .ai/state/logs/T-2026-10-28-010/step-7.log | no |
| 8 | step | 0 | 6d9621fee | .ai/state/logs/T-2026-10-28-010/step-8.log | no |
| 9 | step | 1 | b8df03cd8 | .ai/state/logs/T-2026-10-28-010/step-9.log | yes |
| 10 | step | 0 | f76e1c62d | .ai/state/logs/T-2026-10-28-010/step-10.log | no |
| 11 | suite | 0 | f76e1c62d | .ai/state/logs/T-2026-10-28-010/suite-11.log | no |
| 12 | e2e | 0 | f76e1c62d | .ai/state/logs/T-2026-10-28-010/e2e-12.log | no |
| 13 | step | 0 | 4e2b1d8ae | .ai/state/logs/T-2026-10-28-010/step-13.log | no |
| 14 | suite | 0 | 4e2b1d8ae | .ai/state/logs/T-2026-10-28-010/suite-14.log | no |
| 15 | e2e | 0 | 4e2b1d8ae | .ai/state/logs/T-2026-10-28-010/e2e-15.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass_with_findings (focus security)

```
## FINDINGS

- [HIGH] H1 (authorization / usability of a human route) With the dialog on, `HUMAN_BY_RE` refuses every `state.py start … --mode <m> --by <name>` from the agent session. That includes raising the mode, which needs no human. It also stops the lowering route from ever opening its decision. Location: `hooks/guard/paths.py:97-100` (`HUMAN_BY_VERB` takes `start` unconditionally) and the deny at `paths.py:1255-1258`. — in_scope: yes
  ran: TestDecisionGate scratch, dialog on, no decision, no task. `python3 /p/skills/ai-task/state.py --root . start --mode full --by ivan "fix the guard"` returned deny, "Refusing a 'state.py … --by' verdict from an agent session … The command that needs it opened a decision". The same happened with the goal first and `--declare`.
  why it matters: `skills/rr-plan/SKILL.md:65-66` says "raising it is free (`--mode <m> --by "<name>"` on `start`)", and `hooks/CLAUDE.md` and `skills/CLAUDE.md` tell agents to start behaviour-2 tasks with `start --mode full --by <name>`. With the dialog on, that is refused. For lowering, `state.py` opens the "Mode" decision itself (`state.py:3224-3230`, `offer_decision` before it dies). The guard denies before `state.py` runs, so that decision is never opened and the R36.10 `start --mode --by` dialog route cannot be reached. `WHY_PICK` then says a decision was opened when none was. `verify --by` and `review --by` avoid this only because their decisions are opened by the run without `--by`.
  suggested direction: Let `start --mode --by` reach `state.py`, whose `human_route` already separates raising from lowering, or else make the deny open the decision. Add a dialog-on test for raising and one for lowering.

- [MEDIUM] M1 (input validation) The R36.9 consent rule reuses `COMMIT_PUSH_RE`. That regex matches any `git … commit|push` word, so with the dialog on it refuses ordinary git commands that cannot be given consent at all. Location: `hooks/guard/git.py:243-244`, `COMMIT_PUSH_RE` at `git.py:65`. — in_scope: yes
  ran: same scratch, dialog on, no pick. These were denied with CONSENT_REQUIRED:
  - `git stash push -u -m wip`
  - `git grep -n commit`
  - `git help commit`
  - `git commit --help`
  - `git push --dry-run origin feature`
  - `git log --format=%s -- commit`
  - `git rev-list --count HEAD -- push`
  - `gh pr create --title t --body "after this, git push origin x"`
  - `echo git commit`
  `git config --get remote.origin.push` was allowed.
  why it matters: none of these can become a pick. `validate_label` and `decision open` accept only `git commit …` and a 4-token `git push <remote> <branch>`. So with the dialog on they are refused permanently in the main session, with a WHY_CONSENT text that sends the agent down a route that refuses them too. The golden file does not catch this, because it runs with the dialog off.
  suggested direction: Anchor the consent rule on `git` plus its global options followed directly by the `commit`/`push` subcommand, as `validate_label` does. Add negative cases for `stash push`, `grep`, `help` and `--dry-run`.

- [MEDIUM] M2 (failure mode / fail-open contract) A failed automatic fallback denies every tool from then on, the gate's own escape commands included. Location: `hooks/guard/decision.py:60-62` (`fall_back` runs before the `decision_command` allowance) and `decision.py:99-112` (a non-zero `state.py` is still a Deny and nothing changes state). — in_scope: yes
  ran: copied `hooks/` to a scratch plugin root that has no `skills/ai-task/state.py`. Sent the dialog (offer appended), then Read, `state.py decision fallback --id D1 --why x` and `state.py decision show`. All three were denied with "DECISION_FALLBACK D1 … python3: can't open file …". The ledger still held only `['offer']`, so every later call repeats this.
  why it matters: R36.12 says the gate fails open on error. Here any `state.py` failure turns into a session-wide lockout: a missing script at `dialog.STATE_PY`, a held `consent.lock` making `settle_decision` raise, or a `state.py` that dies earlier. Even the agent's own `decision fallback` or `settle` is pre-empted. A timeout, by contrast, fails open.
  suggested direction: Treat a non-zero fallback as an error, so the call is allowed, or let `decision_command` through before the automatic fallback. Add a test with a fallback that fails.

- [LOW] L1 (consent forgery, R36.5) The dialog-call check compares only `tool_input.questions`. Other top-level keys pass, including `title` and `answers`. Location: `hooks/guard/decision.py:69-71`. — in_scope: yes
  ran: the exact questions plus `"title": "Safety check: the second option CANCELS the commit"` were allowed and an offer was appended. The exact questions plus model-supplied `answers` and `annotations` were also allowed. An extra key inside a question was denied.
  why it matters: R36.5 says "denies any input not canonically equal". The installed Claude Code 2.1.312 binary has an AskUserQuestion schema variant with `title: "Optional single-line heading shown above the questions"`. Its `shownCardInput` keeps `title` and drops `answers`, so a pre-filled `answers` is removed by the harness (checked in the binary, not run end to end). This is the same class as 7d1's L3 misleading-description finding, which this task fixed for descriptions only. A deliberately misleading title is outside the threat model, which is why this is LOW.
  suggested direction: Compare the whole `tool_input`, or allow only `questions` (and an absent or empty `metadata`).

- [LOW] L2 (dependencies / install) The Codex merge now replaces any group whose commands exactly equal a shipped group's (`bin/riskrails.js:1360`, `replace=true`). Codex skips a changed entry until it is reviewed in `/hooks`, and the installer prints only "merged: hooks.json". — in_scope: yes
  why it matters: on upgrade, the widened ai-guard entry stops git, paths, scope and the gate on Codex until the user re-trusts it. Nothing tells the user; only `known-risks.md` mentions it. Before this change the old, trusted entry kept running for Bash. User groups are untouched (test_17b; checked in `mergeHooks`).
  suggested direction: When a replaced group differs from the old one, print a "review the changed ai-guard entry once in /hooks, or Codex skips it" line, as the shim replacements already do.

- [LOW] L3 (race, R36.7 "once") The gate reads the next live pick outside the lock and then appends `use` under it (`decision.py:79-84`). `git.py:270-274` does the same check-and-append inside the lock. Two identical guarded calls running in parallel can both pass. — in_scope: yes. Not run, reasoned from the code: Claude runs non-read-only Bash calls one at a time, and Codex's parallel exec is unverified. Direction: re-read the pick inside `ledger_lock` before appending `use`.

- [LOW] L4 (input validation) `dialog.guarded()` matches prose, so `echo git commit` while picks are live voids them (CONSENT_MISMATCH). This only hurts the agent itself and fails safe. — in_scope: yes. You already probed this; I confirmed the regex. Direction: run `guarded` on the prose-stripped command.

- [INFO] I1 `dialog.decision_command` accepts any `<path>/state.py` by basename and `$STATE` (you probed this). Lifting it needs a planted script or variable, i.e. a constructed command. Inside the boundary it would be LOW. — in_scope: no
- [INFO] I2 These skip the consent rule entirely because they fail `CHEAP_RE`/`COMMIT_PUSH_RE`: `/usr/bin/git commit -m x`, `(git commit -m x)`, `"git" commit -m x` (all three ran and were allowed). This is the same prefix class as every existing git rule. Inside the boundary it would be MEDIUM. — in_scope: no
- [INFO] I3 Binding the gate and Stop depends on `state.py`'s session env equalling the hook payload's `session_id`. That is verified for a fresh Claude session; it is unverified for Codex (`CODEX_THREAD_ID`, already in known-risks) and for Claude after `/clear` or resume. A mismatch fails open: the gate does not see the decision, while the picks still bind to the payload session. — in_scope: no
- [INFO] I4 `prune_decisions` with the switch off (`state.py:2597-2601`) removes a decision even when the settle append's `OSError` is suppressed. The ledger can then hold a pick that is not settled, while decision.json no longer lists its decision. This only matters if the switch is turned back on within the pick window. — in_scope: no
- [INFO] I5 Esc on the dialog writes no ledger line, so the next tool call falls back automatically. This is consistent with R36.15 and fails safe. — in_scope: yes

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stays within the plan's row 7d2 plus the human-approved Q1 (session binding, including the `state.py` session and show filter) and Q2 (Codex merge in `bin/riskrails.js`). The plan's `tests/test_ai_git_guard.py`, `tests/test_ai_path_guard.py` and fixture files were replaced by the table in `tests/test_dialog_consent.py`, with the reason given in its docstring.
```

closed by a green run: H1

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on 4e2b1d8ae (run 14) · (b) green — 15 changed files, all in the task's files
gate: requested G1 at 2026-10-28T19:45:43Z; approved by Ivan Kakurov at 2026-10-28T20:02:36Z via terminal
confirm: none
handoffs: 5 · suite runs: 2 · review passes: 1
