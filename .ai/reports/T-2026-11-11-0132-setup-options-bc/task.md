# T-2026-11-11-0132-setup-options-bc — Interactive setup options, plan tasks B and C: memory enable through a dialog pick, and the /rr-setup options dialog

feature · full · started 2026-11-11T01:32:06Z · claude

## Weight

```
scope          2  tests/test_memory_pre_push.py referenced from 8 files
behaviour      2  C6: allows a deny — memory enable from an agent exits 5 today (memory_cmd.py:42-50) and passes a
reversibility  0  git revert returns everything
domain         2  authorization: after B a dialog pick lets the agent run memory enable, which switches a committe
novelty        1  a new opener (decision open --kind setup) and setup.py options built on R36's existing gate, led
coverage       1  3 of 8 code files have a test
W 8 → full   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-11-11T01:32:06Z — /rr-build-all docs/sdlc/plans/interactive-setup-options.md

## Plan

files: tests/test_memory_pre_push.py, skills/ai-task/rr_state/labels.py, hooks/guard/dialog.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, docs/local-memory.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, skills/project-update/history/blobs/*, docs/sdlc/specs/command-choice-dialog.md, skills/rr-setup/setup.py, tests/test_setup.py, skills/rr-setup/scaffold_ai.py, skills/ai-init/scaffold-ai.sh, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py, skills/ai-task/rr_state/dialog_cmd.py, skills/ai-task/rr_state/cli.py, tests/fixtures/state/partition.json, skills/ai-task/rr_state/memory_cmd.py, tests/test_dialog_consent.py, skills/rr-setup/SKILL.md, tests/test_skills_surface.py, README.md, CHANGELOG.md, tests/test_regenerate.py, tests/fixtures/state/goldens/help.txt, docs/sdlc/specs/interactive-setup-options.md, docs/sdlc/plans/interactive-setup-options.md
tests: tests/test_memory_pre_push.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_state_layout.py, tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_memory_risks.py, tests/test_rename.py, tests/test_no_size_tokens.py, tests/test_setup.py, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py, tests/test_dialog_consent.py, tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py
- B1 · tests/test_memory_pre_push.py · tests/test_memory_pre_push.py · done
- B2 · skills/ai-task/rr_state/labels.py, hooks/guard/dialog.py, tests/test_dialog_gate.py, tests/test_dialog_contract.py · tests/test_dialog_gate.py, tests/test_dialog_contract.py, tests/test_state_layout.py · done
- B4 · docs/local-memory.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/index.json, skills/project-update/history/blobs/*, docs/sdlc/specs/command-choice-dialog.md · tests/test_project_update.py, tests/test_regenerate.py, tests/test_shared_tree.py, tests/test_memory_risks.py, tests/test_rename.py, tests/test_no_size_tokens.py · done
- C3 · skills/rr-setup/setup.py, tests/test_setup.py · tests/test_setup.py · done
- C5 · skills/rr-setup/scaffold_ai.py, skills/ai-init/scaffold-ai.sh, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py · tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py · done
- C1 · skills/ai-task/rr_state/dialog_cmd.py, skills/ai-task/rr_state/cli.py, tests/test_dialog_gate.py, tests/fixtures/state/partition.json · tests/test_dialog_gate.py, tests/test_state_layout.py · done · after B2
- B3 · skills/ai-task/rr_state/memory_cmd.py, tests/test_memory_pre_push.py, tests/fixtures/state/partition.json · tests/test_memory_pre_push.py, tests/test_state_layout.py · done · after B1, B2, C1
- C4 · skills/rr-setup/setup.py, tests/test_setup.py · tests/test_setup.py · done · after C1, C3
- C2 · tests/test_dialog_consent.py · tests/test_dialog_consent.py · done · after C1, B3
- C6 · skills/rr-setup/SKILL.md, tests/test_skills_surface.py · tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_shared_prompts_model_free.py · done · after C4, C5
amended 2026-11-11T01:51:22Z: +tests/test_regenerate.py — B4: the safety.md template edit makes an untouched v3.1.0 copy regenerate; test_regenerate pins safety.md as unchanged since 3.1.0, so it moves to the regenerate tuple (a fact about the shipped history, not a weakened test)
amended 2026-11-11T02:24:00Z: +tests/fixtures/state/goldens/help.txt — C1: the new --spec option of 'decision' is part of 'state.py decision --help', which this golden records; re-recorded with UPDATE_GOLDENS=1, only the decision --help block moves
amended 2026-11-11T02:59:53Z: +docs/sdlc/specs/interactive-setup-options.md, docs/sdlc/plans/interactive-setup-options.md — proof rows name TestOptions:: for tests that C4 placed in TestOptionsOpen/TestOptionsOpenOutcomes (pylint R0904 caps a class at 20 methods); the ids are corrected, nothing else

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-11-11-0132-setup-options-bc for implementation? (gate: human_approval)
asked: 2026-11-11T03:32:36Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via terminal at 2026-11-11T08:22:18Z

## Q1. Another session edited this checkout at 10:11, after close asked for approval: skills/project-update/update.py (outside this task), skills/rr-setup/SKILL.md around line 197-202 and tests/test_regenerate.py (TestKept and a new test). Approve was refused because the tree moved. How are the two changes separated?
asked: 2026-11-11T08:15:04Z · stage: implementation
A. The other fix moves to its own worktree or branch and its hunks leave this checkout; then this session runs verify and close again (recommended)
B. The other fix is committed first with only its own hunks; then this session runs verify and close again
C. Wait; I say when the tree holds only this task's change
X. Other — answer as `X: <text>`
[Answer]: A — by Ivan Kakurov via dialog at 2026-11-11T08:19:40Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 49c4bfa54 | .ai/state/logs/T-2026-11-11-0132-setup-options-bc/suite-1.log | no |
| 2 | e2e | 0 | 49c4bfa54 | .ai/state/logs/T-2026-11-11-0132-setup-options-bc/e2e-2.log | no |
| 3 | step | 0 | 8beba9a2b | .ai/state/logs/T-2026-11-11-0132-setup-options-bc/step-3.log | no |
| 4 | e2e | 0 | 8beba9a2b | .ai/state/logs/T-2026-11-11-0132-setup-options-bc/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — STRONG, pass (focus security)

```
## FINDINGS

I found no BLOCKER and no HIGH. All findings below are `in_scope: yes`, since full mode has no boundary.

- [LOW] L1 (authorization, docs) `docs/local-memory.md:46`: the doc says "Only `/rr-setup` opens that decision". That is false. `decision open --kind setup` can be called by the model from any session, at any time, in any task (`rr_state/dialog_cmd.py:66-68`). `command-choice-dialog.md:72` says this correctly ("the only other one the model may call").
  why it matters: this is the page a human reads to learn who can turn packages mode on. It understates who can ask for it. The control itself still holds: only the human's pick of a label that visibly reads `… memory enable` grants anything.
  fix direction: say that the model may open the setup decision, and that only the human's pick of the shown command enables memory.

- [LOW] L2 (authorization, consistency) `hooks/guard/dialog.py:559-563`: `memory enable` is now a human-only verb with a dialog route, but `guarded()` and `HUMAN_VERB_RE` do not match it. So while a pick is live, a mismatched `memory enable` (for example with `--index sqlite` added) gets DECISION_PENDING and does not void the picks. `approve` gets CONSENT_MISMATCH. I challenged decision 1 and it holds for safety: state.py's `dialog_pick` binds the exact argv, the realpath of this state.py, the session, an open decision and single use. `test_enable_pick_used_once` pins that 5 argv variants and another project are each refused with exit 5 and leave the pick unspent. The gate's docstring "a human-only state.py command" is now incomplete, and R36.8's "a deviation voids consent" signal is lost for this verb. No test pins either behaviour at the gate.
  why it matters: no grant is widened. An agent that strays from the pick keeps it and can retry, which `approve` does not allow.
  fix direction: either add `memory\s+enable` to HUMAN_VERB_RE (with its contract fixture), or record in R36.8 and known-risks that memory enable is deliberately not voiding.

- [LOW] L3 (personal data / committed policy) `skills/rr-setup/SKILL.md:54-55`: the "any other refusal" fallback tells the agent to hand the human `memory enable --period quarter [--index sqlite]` unconditionally. `setup.py fallback_lines` and `memory_decision` (setup.py:597-617) correctly drop `--period` once memory.json exists. Under `--options` (`--all`) on a packages project with period `month`, the SKILL text hands over a command that rewrites the committed `period` for every teammate (`memory_sync.enable`: `if period: policy["period"] = period`).
  why it matters: the human runs it themselves, but the agent was told to give them a command that does more than the question asked.
  fix direction: make the SKILL say `--period quarter` only when memory.json is absent, as R16 does.

- [LOW] L4 (audit logging) `skills/ai-task/rr_state/memory_cmd.py:101-104`: an agent-run `memory enable` through a pick switches a committed, team-wide mode and writes `.git/hooks/pre-push`. Its only records are a stdout line and the git-ignored local `consent.jsonl` (`use`, by "state.py memory"). The use is mirrored into a task journal only if a task is in flight and a DIALOG_SYNC command runs later; `memory` is not in `cli.py:22`. `approve` through the dialog writes a journal line with `pick_data`. During `/rr-setup` there is usually no task, so nothing committed says who authorised the switch.
  why it matters: `consent audit` still works locally, but after the fact a teammate cannot see from the repository that the agent ran it on a pick.
  fix direction: record it as a known risk, or add a journal/ledger-mirrored event when there is a task.

- [LOW] L5 (input validation, robustness) `rr_state/dialog_cmd.py:173-186` with `rr_state/labels.py:14`: the memory command label holds the project's absolute path, so a project path containing any LABEL_FORBIDDEN character (`& ; | < > $(` and the others), or a path long enough to push the label past 400 characters, fails `validate_label`. `setup_open` then refuses the whole spec with exit 6 before any write, so the runtime, survey and verify questions are lost too, and the SKILL drops to prose. This fails closed, so it is not a security issue, and no test pins it.
  fix direction: when the memory label would fail, have setup.py leave memory out of the dialog (fallback line only) and still open the other three.

- [INFO] I1 (consent binding, defence in depth) `rr_state/dialog.py:444-447`: `dialog_pick` accepts any live pick whose label parses as this state.py's argv. It does not check that the picked option's kind is `command`. Today the only model-supplied choice labels are setup's, and `check_setup_labels` (dialog_cmd.py:206-208) refuses any that `label_argv` parses or that start with python3/git/npx. That check is the only barrier between a "nothing runs" choice and a grant. It is pinned by `test_setup_spec_rejects_foreign_command`; I also confirmed that `ask` choice labels are "A — …" and the other openers' choices are fixed text.
  why it matters: if that one check regresses, a choice pick would grant approve or memory enable.
  fix direction: in `dialog_pick`, also require that the decision's option `n` for this pick is `kind: command`.

- [INFO] I2 (injection) `skills/rr-setup/SKILL.md:63` with `dialog_cmd.py:131-135`: a verify value may be any printable string of up to 200 characters, as long as it appears as a backtick span of its label. The SKILL applies it as `$SETUP verify --set "<cmd>"`, so a value with `"`, `$`, `\` would break the quoting or be expanded in the agent's shell at setup time. setup.py's own candidates are fixed templates (`setup.py:118-124`) and never contain those characters. Only a hand-built spec reaches this, which the `safety.md` threat model accepts.
  fix direction: either refuse `$ " \` in verify values in the opener, or have the SKILL pass the value via `shlex.quote`/stdin.

- [INFO] I3 (authorization surface) `rr_state/memory_sync.py:1048-1065`: the agent with a pick now installs an executable `.git/hooks/pre-push`. The shim it writes runs the first of several `$HOME/...` candidates and goes into the common hooks dir of all worktrees (or of a parent monorepo when `.ai/` sits in a subdirectory). The behaviour itself predates this change; only who can trigger it is new. `core.hooksPath` and a foreign hook are respected.

- [INFO] I4 (consent display) Free `question`, `header` and command `description` text in a setup spec can mislabel the memory command, for example a header "Runtime". The label is still the full `python3 <abs state.py> --root <abs project> memory enable …`. This is concern B1 in the spec and within the threat model; `consent audit` shows the pick afterwards.

- [INFO] I5 Known risks 5(a)–(e): I agree with each as out of scope and correctly characterised. For (e): ties at one `at` resolve by the hook's `rounds` dict order, which is the first ledger appearance of each decision in question order, which is decision.json order. This holds for Claude (`tool_response.questions` order) and for Codex (questions keyed by id).

## EXAMINED AND CLEAN

- Inherited: there is no review-ledger.md and no sensors.json for this task, so nothing was inherited. Your probes (bare, full and any-order forms; a repeated option, `--perio`, `memory disable` and a dash author refused; `--root`/`--runtime`/`-I` accepted by the allowlist; the hook copy's form-only `state.py` check; `author_slug` blocking path traversal) I took as given and did not repeat.
- authentication / authorization: `human_route` order is unchanged (terminal, then unattended, then dialog only with `allow_dialog`). Only `memory_enable` passes `allow_dialog=True`; disable, cleanup, pack, redact and move-logs do not (`memory_cmd.py:42-49,102`). `test_disable_stays_terminal` pins it with forged picks. A pick from another session is excluded (`live_picks` session filter). A pick in another project's ledger cannot be used: the label's `--root` picks the ledger. A settled, withdrawn or fallen-back decision drops out through `valid_decisions` and the ledger's `settled`.
- consent binding: realpath of the ENTRY, an exact argv list, live inside the window, spent under `ledger_lock` before `sync.enable` runs, then `prune_decisions`. A second run is refused (test). Bash expansion (`~`, `$X`, globs, braces) of a label always changes argv relative to the shlex split, so it fails closed. The gate compares the label string exactly; `-I` or an env prefix is DECISION_PENDING while pending.
- Setup opener, input validation: the shape is exact, schema is an int but not a bool, 1–4 decisions, keys unique, 2–4 options, a per-key vocabulary, values printable and ≤200, descriptions ≤QUESTION_MAX, the spec ≤256 KiB and depth-capped, and a lone surrogate is refused before any write. `setup_command_why` requires literally `python3`, an absolute path whose realpath is ENTRY, `--root` with an absolute realpath equal to root, and then `memory enable`: no second `--root`, no `--runtime`, no interpreter flags (pinned by 15 subtests). Command options appear only under the memory key. Choice labels cannot parse as commands. Atomic open with withdrawal is pinned by `test_setup_open_withdraws_what_it_opened`.
- `--spec FILE` reading an arbitrary file: error texts echo no file content (JSON errors give positions; shape errors are fixed text; label excerpts appear only once the shape is valid).
- Recorder and gate: the widened hook `validate_label` is used only in `choose` (`hooks/guard/dialog.py:680`). No other hook rule lets a `memory enable` through; I grepped hooks/. A git pick's consent applies only to labels starting with `git`, which setup choices cannot.
- `decision settle --pick` stays terminal-only (`human_route()` without root, so no dialog route). A setup command option is refused there. A decline prints `SETUP_PICK key=`.
- Personal data (A2/D1): the author shown is `cfg.author`, the same as what enable writes without `--author`. Its source order matches `MemoryConfig.author` (memory_sync.py:98-99). No git user.name is used. Mirrored ledger events carry no labels or questions.
- setup.py: subprocesses run `-I -B`, the label quoting equals `rr_state.labels.state_label`, `--skip` is restricted to `choices=OPTION_KEYS`, `options --json` writes nothing (`consent` is not a DIALOG_SYNC command), and `fallback_lines` strips the prefix correctly.
- Scaffold `--runtime none` returns an empty set and is a whole value only. The `test_regenerate` move is justified by the template change and its history blob; the test was not weakened. The partition.json and help golden edits are mechanical.
- Tests run: `python3 -I tests/run_suite.py tests/test_memory_pre_push.py tests/test_dialog_contract.py` passed (43 tests).
- Dependencies: none added (setup.py uses stdlib hashlib, importlib, subprocess, shlex).
- Secrets: none read or written; the SQLite index is local.
- not reached (budget): a live end-to-end Codex `request_user_input` round with four options (OQ2); the CHANGELOG/README wording beyond README:168.

## VERDICT

verdict: pass

One line of reasoning: the authorization change (memory enable on a dialog pick) is bound in state.py to the exact argv, ENTRY, root, session, window, an open decision and single use, and pinned negatively. The setup opener is stricter than the spec, and no opener other than setup can offer a memory-enable label. The findings are documentation, consistency and defence-in-depth (L1–L5, I1–I5).

scope_assessment: the change stayed inside the approved plan. The amendments for test_regenerate, the help.txt golden and the spec/plan proof ids are recorded with reasons. `--skip` adds a little beyond the interface list but implements the spec's own "a given --survey removes the survey question".

ai_context_safety: no sensitive path was read during this review. I read no .env, credentials or home-directory secrets.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CHANGELOG.md | +8 −0 | Edit |
| README.md | +3 −2 | Edit |
| docs/local-memory.md | +12 −3 | Edit |
| docs/sdlc/plans/interactive-setup-options.md | +6 −5 | Edit |
| docs/sdlc/specs/command-choice-dialog.md | +20 −7 | Edit |
| docs/sdlc/specs/interactive-setup-options.md | +3 −3 | Edit |
| hooks/guard/dialog.py | +14 −2 | Edit |
| skills/ai-init/scaffold-ai.sh | +2 −1 | Edit |
| skills/ai-init/templates/.ai/policies/safety.md | +4 −3 | Edit |
| skills/ai-task/rr_state/cli.py | +1 −1 | Edit |
| skills/ai-task/rr_state/dialog_cmd.py | +183 −6 | Edit |
| skills/ai-task/rr_state/labels.py | +14 −2 | Edit |
| skills/ai-task/rr_state/memory_cmd.py | +7 −4 | Edit |
| skills/project-update/history/blobs/8ec171f0fbdf38cc6996d496f01491fd1f21f04a435a118ad979b127a8be06f1 | +85 −0 | New |
| skills/project-update/history/index.json | +2 −1 | Edit |
| skills/rr-setup/SKILL.md | +75 −19 | Edit |
| skills/rr-setup/scaffold_ai.py | +8 −2 | Edit |
| skills/rr-setup/setup.py | +370 −4 | Edit |
| tests/fixtures/state/goldens/help.txt | +2 −1 | Edit |
| tests/fixtures/state/partition.json | +16 −6 | Edit |
| tests/test_dialog_consent.py | +144 −1 | Edit |
| tests/test_dialog_contract.py | +76 −0 | Edit |
| tests/test_dialog_gate.py | +423 −2 | Edit |
| tests/test_memory_pre_push.py | +211 −0 | Edit |
| tests/test_regenerate.py | +2 −2 | Edit |
| tests/test_scaffold_differential.py | +44 −1 | Edit |
| tests/test_scaffold_idempotency.py | +51 −1 | Edit |
| tests/test_setup.py | +836 −0 | Edit |
| tests/test_skills_surface.py | +100 −1 | Edit |

+2722 −80 lines, 29 files

## Verdict

close: closed
facts: (a) green — documents only since run 1 (1 files: README.md); doc_tests green in run 3 on 8beba9a2b · (b) green — 29 changed files, all in the task's files
gate: requested G1 at 2026-11-11T03:32:36Z; approved by Ivan Kakurov at 2026-11-11T08:22:18Z via terminal
confirm: none
handoffs: 11 · suite runs: 1 · review passes: 1
