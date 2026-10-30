# Plan: Register batch 2 — the rest of the mechanical fixes and the risk-tiers retirement

Status: accepted 2026-10-30 by Ivan Kakurov (decisions below); run by `/rr-build-all`.

Source: the 70 open entries of `state.py memory risks` after commit 4fd3bd8, measured on HEAD by four
read-only discovery passes (areas A guard/dialog, B state.py/routing, C update/templates/texts,
D CI/tests). `#N` is the entry's number in that listing.

## Decisions (human, 2026-10-30)

| Q | Pick |
|---|---|
| Scope | Every mechanical fix below, plus the retirement of `risk-tiers.json`/`.md` with migration 0011 (#20, #50, #58, #62). Own-design entries stay in the register. |
| Bite codes (#6) | A new `testing.md` key `bite_codes`, default `1`, read by sensors.py; `verify --expect fail` bites only on those exit codes. The shipped template documents it with examples (pytest `1,2`, phpunit `1,2`, cargo `101`). This repository's `.ai/policies/testing.md` is the human's. |
| CI (#14) | A `full` job in `tests.yml` on `schedule` and `workflow_dispatch`, the release command; `smoke` unchanged. |
| False denies (#7, #36) | Accepted; they stay recorded. |
| Recommended defaults taken | #4 skip the upload only when the registry's `gitHead` equals `GITHUB_SHA` (3.0.0 and 3.0.1 carry one), empty → warn and skip; #5 keep the hint and `original/` for tracked or dirty `.ai/reports/` targets, rr-setup worded per target kind; #24 rr-review §2: the session runs a timed probe, not the reviewer; #42 I5/#45 declare the Python 3.11 floor; #52 skip links resolving outside the root; #61 fix `split_shared_section`, restore r7's byte-identical assertion. |

## Order of work

| Step | Entries | Files | Tests | After |
|---|---|---|---|---|
| guard | #2 `--mode` abbreviations in MODE_LIGHT; #3 a timed ~4000-char `start … --by` case on the Python path; #42 I1 strip one leading BOM in `parse_stream` | `hooks/guard/paths.py`, `hooks/guard/common.py`, `tests/test_ai_path_guard.py`, `tests/fixtures/guard-characterization/**` | `test_ai_path_guard`, `test_guard_characterization`, `test_guard_differential`, `test_dialog_consent` | — |
| state | #9 atomic old-surface abandon; #46 irreversible keyword from the first `[A-Za-z]+` run; #6 `bite_codes`; #18 `--files` takes commas and blanks; #22 a trailing `# …` comment on a testing.md field; #8 state.py's `/ai-init` message; the template `testing.md` documents `bite_codes` | `skills/ai-task/state.py`, `skills/ai-task/sensors.py`, `tests/test_ai_task_state.py`, `tests/test_ai_task_sensors.py`, `skills/ai-init/templates/.ai/policies/testing.md`, `skills/project-update/history/**` | `test_ai_task_state`, `test_ai_task_sensors`, `test_weight`, `test_project_update` | — |
| usage | #41 an unclosed task's window ends at its last event, labelled | `skills/usage-report/usage-report.py`, `tests/test_usage_report.py` | `test_usage_report` | — |
| update | #5; #11 an unreadable state.json counts as a task in flight; #61; #70 (n) `unsafe_target` re-checked before a delete; #8/#59 `/project-update` messages → `/rr-setup --update` | `skills/project-update/update.py`, `skills/rr-setup/SKILL.md`, `tests/test_project_update.py`, `tests/test_migration_0006.py` | `test_project_update`, `test_migration_0006` | — |
| texts | #23 the pass verdict recorded once; #30 the MEDIUM/LOW register rule for every verdict; #24 the session's timed probe | `skills/rr-review/SKILL.md`, `skills/rr-build-all/SKILL.md` | `test_skills_surface`, `test_instruction_budget` | — |
| setup | #52; #43 stale shell-suite names in two comments | `skills/rr-setup/setup.py`, `tests/test_setup.py`, `skills/project-update/render_instructions.py` | `test_setup`, `test_instruction_budget` | — |
| instr | #1 `stub.md:50` keeps "outside" and "correction" within the budgets; renders rebuilt | `instructions/stub.md`, `skills/ai-init/templates/{CLAUDE,AGENTS,GEMINI,junie-guidelines}.block.md`, `skills/project-update/history/**` | `test_instruction_budget`, `test_project_adopt`, `test_project_update` | state |
| consent | #33 `.ai/state/*.jsonl` in the ignore snippet | `skills/ai-init/templates/gitignore.snippet`, `skills/project-update/history/**` | `test_project_update` | instr |
| ci | #4; #14 | `.github/workflows/npm-publish.yml`, `.github/workflows/tests.yml`, `tests/test_release.py` | `test_release` | — |
| notice | #16 checked_at written before the fetch, the read capped; #17 the test patches the spawn and fails when the isdir guard goes | `hooks/update_notice.py`, `tests/test_update_notice.py` | `test_update_notice`, `test_context_guard` | — |
| docs | #42 I5/#45 the Python 3.11 floor stated | `README.md`, `docs/installation.md` | `test_skills_surface` | — |
| retire | #20/#50/#58/#62 migration 0011: stop shipping `risk-tiers.{json,md}`, propose their deletion in a project (human `--confirm-delete`), the router template row, the texts that name removed commands, nothing reads `risk-tiers.json` any more (state.py `DIRECT_MODE_CAP` and friends), history rebuilt | `skills/project-update/migrations/**`, `skills/ai-init/templates/.ai/**`, `skills/project-update/update.py`, `skills/ai-task/state.py`, `ai/policies/review-economy.md`, `skills/project-update/history/**`, `tests/test_migration_0011.py`, `tests/test_project_update.py`, `tests/test_migration_0006.py`, `tests/test_ai_task_state.py`, `tests/fixtures/**`, `docs/**` | `test_migration_0011`, `test_project_update`, `test_migration_0006`, `test_ai_task_state`, `test_project_adopt`, `test_scaffold_idempotency`, `test_install_dry_run` | update, state, consent |

Bugfixes get a test that fails before the fix. A guard regex change gets a timed case at a measured
size on the Python path (≤ 4096 characters). Template and `ai/` edits run `tools/build-template-history.py`.

### Batch end
`verify --scope all` once; failures fixed as one batch; one STRONG review; findings fixed as one
batch; README test count; close; the human approves.

## Closed without code (obsolete on HEAD 4fd3bd8)
#21, #28, #37, #39, #55, #57, #67, #69. After the docs step: #45 and #42 I5.

## Out of this plan (stay in the register)
Own design: #10, #19, #27, #29, #32, #34 I3, #35, #38, #40, #47, #49, #51, #53, #54, #56, #63, #65, #68.
Accepted: #7, #36 (this plan), #26, #48. Human: #12, #13, #25, #31, #60. Records kept: #34 I1/I2, #44,
#64, #66, #70.

## Risks
- `skills/project-update/history/**` is written by state, instr, consent and retire; `start` orders them.
- Migration 0011 changes install and migration (behaviour 2); a project's deletion stays the human's.
- `instructions/stub.md` sits at the adopt keep-budget; #1 must stay byte-neutral.

## Rollback
`git revert` of the commit. A project that already ran 0011 with `--confirm-delete` keeps the files
under `original/` as every migration deletion does.
