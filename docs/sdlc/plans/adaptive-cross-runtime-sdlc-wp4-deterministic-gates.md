# Plan: WP4 — Deterministic gates

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp4-deterministic-gates.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Tier **T3** (spec header: `state.py` and the shipped `risk-tiers.json` are shared by every
initialised project and both runtimes). Scope **feature**. No `ai-security` review — no
authentication, no authorization decision, no personal data — but the adversarial review must
treat the skip rule (R8/R9) as the change's blast radius, because a false green removes a review.

All ten spec concerns and all eight open questions were settled with the user on 2026-09-20.
Four of those answers shape the work and are repeated here so no reviewer re-opens them:
**bite is required for the T2 skip** (`required_from: "T2"`), **`review-economy.md` is amended
in this change** to admit decision 6, **a tier raised after implementation records
`plan_review: superseded` and carries on**, and **the human condition on `risk` / `triage` /
`remediate` belongs to WP4**. T0/T1 stay without a state file and therefore without a gate;
`profiles/*.json` are untouched (WP5 owns them).

Nine steps, nine commits. Each step names the only files it may touch; anything else is
`SCOPE_CHANGE_REQUIRED` and an amendment to this plan. Step tests are scoped to the new suite's
sections; `bash tests/run-all.sh` runs **once**, at step 9. There is no e2e suite in this
repository (`e2e_command: none`) — the install dry runs in `run-all.sh` are the closest thing and
they run there.

Verified before planning: `install.sh:438` copies `skills/*/` wholesale, so `sensors.py` ships
with no installer change — only the `chmod +x` list at `install.sh:461` gains it, in step 1.

## Files that change

### New

| Path | Why |
|---|---|
| `skills/ai-task/sensors.py` | R6/I3: every measurement — `diff`, `rescore`, `snapshot`, `detect`, `run`, `check`, `bite`, `report`. Stdlib, `git`, and the commands written in `testing.md`; never a state writer |
| `skills/project-update/migrations/0004_deterministic_gates.py` | R14/I7: schema 4 state defaults, `MOVES = []`, `patch_state` only |
| `tests/test-ai-task-sensors.sh` | R2–R12: ten sections, scratch repository under a path containing a space |
| `tests/fixtures/project-update/schema-v3/` | R14: a task at `implementation` with no `diff` key |

### Edited

| Path | What changes |
|---|---|
| `skills/ai-init/templates/.ai/policies/risk-tiers.json` | R1/I1: `diff_budget`, `path_scopes`, `sensors`, `remediation_rounds`; `version` 2 → 3 |
| `skills/ai-init/templates/.ai/policies/risk-tiers.md` | R1: the mirror's new section and a fresh `sha256:` line |
| `skills/ai-init/templates/.ai/policies/testing.md` | I1: `lint_command:`, `typecheck_command:`, the `{files}` convention in `step_test_command` |
| `skills/ai-init/templates/.ai/policies/review-economy.md` | Q5/F3: the amendment admitting decision 6's skip, citing it as the authority |
| `skills/ai-init/templates/.ai/AGENTS.md` | R16: one router row pointing at the gates |
| `skills/ai-init/templates/.ai/VERSION` | R14: 3 → 4 |
| `skills/ai-task/state.py` | R2–R5, R9, R10/I2, I4: snapshots, the `step-done` gate, `step-split`, `test-run`, `review-gate`, the human conditions, `apply_defaults` |
| `skills/ai-task/SKILL.md` | the three places the gates fire: step loop, TEST, ADVERSARIAL REVIEW |
| `agents/ai-tester.md` | R11/I6: a log path in, no suite run, the bounded retry and the single-test check at base |
| `agents/ai-reviewer.md` | R13: the sensor rows are inherited facts, never re-derived |
| `skills/project-update/update.py` | I1: `lint_command` / `typecheck_command` in the `testing.md` hint list |
| `skills/ai-status/SKILL.md` | R16: one sensors line from `sensors.json` |
| `skills/ai-init/SKILL.md` | R7: the survey step runs `sensors.py detect` and proposes the two lines |
| `tools/build-template-history.py` output | R1: template history rebuilt after the policy change (WP1 contract) |
| `tests/run-all.sh` | the new suite in the list |
| `tests/test-project-update.sh` | R14: additive assertions for 0004 and the `schema-v3` fixture |
| `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` | Q1: "scopes" disambiguated (path scopes are WP4's); row 4 marked done at step 9 |
| `README.md`, `docs/faq.md` | what the gates are and how a project opts a sensor out |

### Untouched on purpose

`hooks/**` (no guard rule changes — `tests/test-guard-characterization.sh` and its golden stay
byte-identical), `profiles/*.json` (Q6, WP5), `install.sh` except the one `chmod +x` line.

## Order of work

| # | Step | Files it may touch | Proves |
|---|---|---|---|
| 1 | **`sensors.py` core** — `snapshot_tree` (temp `GIT_INDEX_FILE`, `git add -A`, drop `.ai/state` and `.ai/reports`, `write-tree`), `-z --numstat --no-renames` parsing with binary files, `exclude` and scope matching, budget evaluation; the `diff`, `rescore`, `snapshot`, `detect` subcommands | `skills/ai-task/sensors.py`, `tests/test-ai-task-sensors.sh`, `tests/run-all.sh`, `install.sh` (the `chmod +x` list only) | R6, R7, parts of R2/R4 |
| 2 | **Policy** — the I1 keys, `version` 2 → 3, the mirror section and its sha, the `testing.md` lines, the `update.py` hint list, template history rebuilt | `skills/ai-init/templates/.ai/policies/risk-tiers.{json,md}`, `.../testing.md`, `skills/project-update/update.py`, the history artefacts | R1 |
| 3 | **The diff gate** *(riskiest — see Risks)* — `apply_defaults` keys, snapshots at `init`/`quick`/`step`, the `step-done` measurement, exit 6 and the two tokens, re-scoring and `tier_raised`, `step-split`, step `kind`, and the R5 human conditions on `risk` / `triage` / `remediate` | `skills/ai-task/state.py`, `tests/test-ai-task-sensors.sh` | R2, R3, R4, R5 |
| 4 | **Runs** — `sensors.run_command`, `state.py test-run` with the cap, the one environment retry and the log files; `ai-tester`'s new contract and its Codex render | `skills/ai-task/state.py`, `skills/ai-task/sensors.py`, `agents/ai-tester.md`, `tests/test-ai-task-sensors.sh` | R10, R11 |
| 5 | **Static sensors** — lint, typecheck, traceability, duplicates, plan_sections, plus `check`, `report` and `sensors.json` | `skills/ai-task/sensors.py`, `tests/test-ai-task-sensors.sh` | R6, R8 (the sensor half) |
| 6 | **Bite** — revert from tree objects, the required-test run, byte-identical restore, `.ai/state/bite.lock`, `--restore`, and the per-kind expectation | `skills/ai-task/sensors.py`, `tests/test-ai-task-sensors.sh` | R12 |
| 7 | **The gate and the prompts** — `state.py review-gate`, `skipped_green` (and the refusal of `set review_status skipped_green`), the ledger rows, `review-economy.md`'s amendment, the `SKILL.md` and `ai-reviewer.md` wording, the `.ai/AGENTS.md` row, the `/ai-status` line, `/ai-init`'s `detect` step | `skills/ai-task/state.py`, `skills/ai-task/SKILL.md`, `agents/ai-reviewer.md`, `skills/ai-init/templates/.ai/policies/review-economy.md`, `skills/ai-init/templates/.ai/AGENTS.md`, `skills/ai-status/SKILL.md`, `skills/ai-init/SKILL.md`, `tests/test-ai-task-sensors.sh` | R8, R9, R13, R16 |
| 8 | **Migration 0004** — the state defaults, `.ai/VERSION` 3 → 4, the `schema-v3` fixture and the additive assertions | `skills/project-update/migrations/0004_deterministic_gates.py`, `skills/ai-init/templates/.ai/VERSION`, `tests/fixtures/project-update/schema-v3/`, `tests/test-project-update.sh` | R14 |
| 9 | **Docs and close** — `README.md`, `docs/faq.md`, the intent's "scopes" disambiguation and row 4, then `bash tests/run-all.sh` once, to the end | `README.md`, `docs/faq.md`, `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` | R15, R16 |

Order rationale: measurement before enforcement (1 before 3), policy before the code that reads
it (2 before 3), the cheap sensors before the one that touches the working tree (5 before 6), and
the skip rule last of the behaviour steps (7) so it is written against sensors that already work.
The migration is 8 because only then is the final state shape known; putting it earlier would
mean migrating twice.

## Risks

**Step 3 is the riskiest** and cannot move earlier — it is the first step that can *refuse* work.
A wrong budget or a wrong scope match turns `step-done` into a wall in every project on the next
`/project-update`. Mitigations: exit 6 is a new code, so nothing that reads exit 1 changes meaning;
the step stays `in_progress` on refusal, so no state is lost; `step-split` is written in the same
step, so the refusal always comes with the way out; and the non-git path returns `unavailable` and
exit 0, which is what `tests/test-ai-task-state.sh:39` already exercises.

| What could break | How it is noticed |
|---|---|
| A false green skips a T2 review (F1) | Every ambiguity resolves to red, `stale` or `unavailable`; `set review_status skipped_green` is refused; section 10 of the new suite asserts each blocking case |
| `bite` leaves a dirty tree after an interruption (F2) | `.ai/state/bite.lock` holds `tree_after`, a recovery line is printed before the run, `bite --restore` restores; the test kills a run mid-way and asserts the tree hash and `git status --porcelain` are identical |
| A task in flight meets schema 4 | `apply_defaults` fills the keys in memory and 0004 on disk; the `schema-v3` fixture asserts `step-done` exits 0 with `unavailable` for a task that started earlier |
| A snapshot is slow on a large tree | The temporary index starts as a copy of the real one, so only changed files are hashed; the new suite asserts ≤ 2 s on this repository, and it runs at step boundaries only |
| Existing tests lower a tier or remediate a third time (F9) | Step 3 greps the suites before editing; a hit gets `AI_UNATTENDED=1`, the way `approve` is already tested |
| The guard hot path regresses (WP8) | No hook is touched; step 9 asserts `git diff --stat` on the characterization golden is empty |
| `git` older than 2.23, a shallow clone, a pruned tree | `diff`, `rescore` and `bite` return `unavailable` with one line; nothing refuses |
| Re-scoring fights a large but harmless diff (F4) | `exclude`, the unbudgeted `docs` scope, and a raise costing a review rather than a refusal; decision 2 recalibrates from `/usage-report` |

## Proof (tests)

`tests/test-ai-task-sensors.sh`, ten sections, each named by the requirement it proves:

| R | Proof |
|---|---|
| R1 | `test-scaffold-idempotency.sh` (the mirror sha), `test-project-update.sh`, `test-merge-migration.sh`; a schema-v2 fixture run shows `merge … your edits kept` with the new keys present |
| R2 | section 1–3: `sensors.py diff --from <t1> --to <t2>` equals `git diff --numstat` on the fixture; a non-git root prints `unavailable` and exits 0 |
| R3 | section 4: over budget → exit 6 with `DIFF_BUDGET_EXCEEDED` and the step still `in_progress`; a file outside `allowed_files` → exit 6 with `SCOPE_CHANGE_REQUIRED`; `step-split` then makes the re-run pass |
| R4 | section 5: a diff touching `src/Payment/` raises T2 → T4 and emits `tier_raised`; a smaller diff never lowers |
| R5 | section 6: `risk T2` without a TTY → exit 5; with `AI_UNATTENDED=1` and `--by` → recorded in `risk_tier_lowered`; a third `remediate` → exit 5 |
| R6, R7 | section 3 and 8: `detect` proposes but never runs; `check` prints ≤ 12 lines; a moved tree marks results `stale` |
| R8 | section 10: each of red, `unavailable` and `stale` blocks the skip; `lint_command: none` is `not_applicable` and does not block; a missing line does block |
| R9 | section 10: T2 all green → `skipped_green` and exit 0; T3 → `review: required`; `set review_status skipped_green` refused |
| R10 | section 7: exit 0 sets `test_status` with the tree recorded; a sixth suite run → exit 6; `--env-retry` refused without a recorded environment classification; the log file exists and the printed output is ≤ 6 lines |
| R11 | `tests/test-codex-agent-render.sh` plus a grep asserting `ai-tester.md` names no `verify_command` run of its own |
| R12 | section 9: a feature test that fails at base → green; a test that never reaches the changed module → red; a characterization step that passes at base → green; the tree hash identical before and after; an interrupted run plus `--restore` leaves the tree identical |
| R13 | section 10: the ledger file contains one row per green or red sensor, each carrying the tree hash |
| R14 | `test-project-update.sh`: the `schema-v3` fixture reaches version 4, a second run is `0 automatic`, `--check` exits 1 then 0, and the migration text matches neither `claude` nor `codex` |
| R15 | `bash tests/run-all.sh` at step 9, to the end; `git diff --stat` on the characterization golden empty |
| R16 | `test-ai-status-root.sh` plus a grep for the sensors line |

`verify_command` for this repository is `bash tests/run-all.sh`; `step_test_command` is
`bash tests/<one suite>.sh`; `e2e_command: none`.

## Rollback

Every step is one commit and nothing runs outside a developer's checkout, so `git revert` of the
range restores the previous behaviour completely. Two things need saying:

- **A project already migrated to schema 4** keeps its extra state keys after a revert.
  They are additive and ignored by schema-3 code — `apply_defaults` overwrites nothing it finds —
  so the only visible consequence is `.ai/VERSION` reading `4` against a plugin that ships `3`,
  which `/project-update --check` reports as "ahead" and a human resolves. No migration is
  destructive and no file is deleted by this package.
- **A stuck gate needs no revert.** `sensors.skip_review_at_or_below` set to `"T0"` turns the skip
  off, a per-sensor entry removed from `required_for_skip` turns one sensor off, and raising a
  `diff_budget` number is a one-line edit in a project's own policy file. The escape hatch is the
  policy, not a rollback.
