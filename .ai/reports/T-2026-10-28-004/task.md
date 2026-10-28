# T-2026-10-28-004 — state.py prepares decisions, reads the consent ledger and takes the dialog route for approve and the --by commands (R36 step 7c)

feature · full · started 2026-10-28T12:39:23Z · claude

## Weight

```
scope          2  skills/rr-ship/SKILL.md referenced from 135 files
behaviour      2  changes the approval path: approve, verify --by, review --by, start --mode and profile set accep
reversibility  0  git revert returns everything
domain         2  authorization boundary: the agent session may run approve on a recorded human pick; spec section
novelty        1  a new decision/consent mechanism in state.py, stdlib only, no new dependency or manifest (declar
coverage       0  1 of 1 code files have a test
W 7 → full   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/ai-task/state.py, skills/rr-ship/SKILL.md, skills/rr-build/SKILL.md, skills/rr-review/SKILL.md, tests/test_ai_task_state.py, tests/test_skills_surface.py, tests/test_profile_detect.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/fixtures/dialog/ledger/**, tests/fixtures/dialog/payload-golden/**
tests: tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py, tests/test_skills_surface.py
- s1 · skills/ai-task/state.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/fixtures/dialog/ledger/**, tests/fixtures/dialog/payload-golden/**, tests/test_ai_task_state.py · tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_ai_task_state.py · done
- s2 · skills/ai-task/state.py, tests/test_ai_task_state.py, tests/test_profile_detect.py · tests/test_ai_task_state.py, tests/test_profile_detect.py · done
- s3 · skills/rr-ship/SKILL.md, skills/rr-build/SKILL.md, skills/rr-review/SKILL.md, tests/test_skills_surface.py · tests/test_skills_surface.py · done

## Questions

[questions.md](questions.md) — 1 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 46d2c3ffc | .ai/state/logs/T-2026-10-28-004/step-1.log | no |
| 2 | step | 0 | 239cd9d50 | .ai/state/logs/T-2026-10-28-004/step-2.log | no |
| 3 | step | 0 | 0a33d150f | .ai/state/logs/T-2026-10-28-004/step-3.log | no |
| 4 | step | 1 | e1f4eb131 | .ai/state/logs/T-2026-10-28-004/step-4.log | no |
| 5 | step | 0 | 1f1064787 | .ai/state/logs/T-2026-10-28-004/step-5.log | no |
| 6 | suite | 0 | 1f1064787 | .ai/state/logs/T-2026-10-28-004/suite-6.log | no |
| 7 | e2e | 0 | 1f1064787 | .ai/state/logs/T-2026-10-28-004/e2e-7.log | no |
| 8 | suite | 0 | 1a238607d | .ai/state/logs/T-2026-10-28-004/suite-8.log | no |
| 9 | e2e | 0 | 1a238607d | .ai/state/logs/T-2026-10-28-004/e2e-9.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass_with_findings (focus security)

```
## FINDINGS

- [HIGH] H1 (authorization) A dialog pick is not bound to the gate, tree or open decision it was offered for: `dialog_pick` accepts any live pick whose label equals argv, and an approve label is the same string for every gate of the project — `skills/ai-task/state.py:2625-2648`, `:3706-3717`, `cmd_approve :2091` — in_scope: yes
  attack: close opens D1 for tree ad903950a; the human picks approve (C1); the agent runs `reject` itself (no route needed), edits a file, verify/review/close → G2 is requested and D2 opened for tree 819617f4f; the agent runs D1's approve label → "approved by Rita Human (via dialog)"; the next close archives the task on a tree the human never saw. Every step is an ordinary pipeline command. Only the 7d PreToolUse gate (fail-open, "not the security boundary") would stop it. Related: read_decisions tells the human to delete decision.json, but a dropped decision's picks stay usable until they expire.
  direction: accept a pick only while its decision is still open and was opened for this command's gate and current tree (record gate_id in the approval decision); settle/supersede an open approval decision when its gate is rejected or re-requested.

- [MEDIUM] M1 Once the first pick of a decision expires, is voided or comes from another session, every later pick of that decision is dead — `state.py:2365-2376` (`live_picks`) — in_scope: yes
  scenario: the chain is sorted by order; a re-offer's picks restart at order 1, so the old order-1 pick sorts first and hits `break`. An expired C1 plus a fresh C2 gives exit 5 APPROVAL_REFUSED; the same for C1 from an old session. Breaks R36.8's "the decision reopens" and a resume in a new session. The contract fixtures have no re-offer case, so 7d1's reader would copy this. Fails closed (usability, not security).
  direction: chain only the latest offer's picks, or skip dead picks instead of break; add a fixture case.

- [MEDIUM] M2 `prune_decisions` never settles a decision that has an unused pick from an earlier round, and `decision settle` then refuses it — `state.py:2559-2571`, `:2747-2765` — in_scope: yes
  scenario: D1 has an expired C1, then C2 picked and used; D1 stays in decision.json and `decision settle --id D1` dies "nothing is recorded"; under 7d the gate and Stop hook keep blocking on an approval already granted until `decision fallback`.
  direction: a decision is done when its latest offer's picks are used; ignore voided/expired picks.

- [MEDIUM] M3 The approval question states "rollback: git revert" for every task — `state.py:2662` (`task_facts`) — in_scope: yes
  scenario: reversibility 2 with domain < 2 is mode full (not full_irreversible), so it gets the dialog, and the human is told it reverts with git revert while its own weight says it does not; the click-through mitigation rests on the facts in the question.
  direction: derive the rollback line from state["weight"]["axes"]["reversibility"] and its evidence.

- [LOW] L1 `sync_dialog` runs before `guard_pending`, so an exit-4 refusal can now write files — `state.py:4243-4246`, docstring `:1852-1854` — in_scope: yes
  scenario: with new ledger lines the refused command saves current.json (ledger_pos, updated_at), appends journal lines, may rewrite decision.json; nothing is authorized, but "exit 4 leaves the state byte-identical" is now false and untested.

- [LOW] L2 `validate_label` is looser than R36.4 and than the labels state.py builds — `state.py:2167`, `:2217`, `:2255-2257` — in_scope: yes
  scenario: any `*/python3` and any `*/state.py` pass (`/tmp/x/python3 /tmp/y/state.py approve`); the push form accepts `+feat` (a force push; git.py FORCE_RE does not catch `+`, pre-existing), `src:dst`, `HEAD:main`. 7d reuses this check.
  direction: interpreter exactly python3/python, script this state.py's realpath, push branch without `+` and `:`.

- [LOW] L3 The O_EXCL lock's stale takeover races — `state.py:2286-2298`
  scenario: two waiters both see a stale lock; A removes and recreates, B's os.remove deletes A's fresh lock, both proceed; the finally removes the lock even after another process took it over. Only after a crashed writer.

- [LOW] L4 `decision settle` without --pick applies the last recorded choice pick with no session/expiry/void check, and a choice pick wins over a later decline — `state.py:2747-2759`
  scenario: a "Not now" from an earlier offer settles a decision later re-offered and answered; choice picks grant nothing.

- [LOW] L5 `ask --gate` opens a dialog decision for a G question, but apply_choice → cmd_answer refuses G ids — `state.py:1487-1498`, `:2770-2773`, `:1509-1510`

- [LOW] L6 decision.json read-modify-write outside the lock (open_decision, settle_decision, prune_decisions): two sessions can lose an update or reuse next_decision_id — `state.py:2456-2481`, `:2538-2544`

- [LOW] L7 The mirror cursor assumes consent.jsonl only grows — `state.py:2589-2613`
  scenario: a shorter replacement mirrors nothing until it grows past the old offset, then starts mid-line; a failed save after the journal append re-mirrors lines.

- [INFO] I1 Off route: `start` now always writes "dialog": {"ledger_pos": N} into current.json, even with the switch off — `state.py:3167` — in_scope: yes
- [INFO] I2 Session binding is an environment variable the agent can set; the live --by verbs have no path-guard rule until 7d's HUMAN_BY_RE — `state.py:2200` — in_scope: yes. Only lets one session consume another session's pick; belongs in known-risks next to C1.

## VERDICT
verdict: pass_with_findings
scope_assessment: inside the plan's files and accepted departures; H1 and M1/M2 are defects in this task's own code.
ai_context_safety: no sensitive path read; probes only in the scratchpad.
```

closed by a green run: H1

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on 1a238607d (run 8) · (b) green — 25 changed files, all in the task's files
gate: requested G1 at 2026-10-28T13:17:59Z; approved by - at - via -
confirm: none
handoffs: 4 · suite runs: 2 · review passes: 1
