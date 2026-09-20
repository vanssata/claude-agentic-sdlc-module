# Plan: WP3 — Context diet

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp3-context-diet.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Tier **T3** (spec I10: shared services — `install.sh` and `update.py` are shared by every
project and both runtimes; characterization required before changing legacy behaviour).
Scope **feature** with a **refactor** first step. No `ai-security` review: no auth, no
secrets, no personal data — the only new write path outside `.ai/` is migration 0003, and
it is covered by R12/R13 and step 6's fixture.

All ten spec concerns were shown to the user on 2026-09-20 and **accepted**; all six spec
open questions were answered as specified. Do not re-open them. Two of them shape the work
and are repeated here so a reviewer does not flag them: **0003 strips the section from a
user-owned root file** (original kept), and **`.ai/rules/` rendering is in WP3**, step 7.

Nine steps, nine commits. Each step names the only files it may touch; anything else is
`SCOPE_CHANGE_REQUIRED` and an amendment to this plan. Step tests are scoped; the full
suite runs once, at step 9.

## Files that change

### New

| Path | Why |
|---|---|
| `instructions/stub.md` | R1: the one source of every always-loaded stub, all scopes and runtimes |
| `instructions/runtimes.json` | R1/I1: per-runtime vocabulary (`FILE`, `HOME`, `RUNTIME_NAME`, `NEW_CONTEXT`, `MULTI_EDIT`, `TRUST`, `NOTES_DIR`) |
| `instructions/routing.md` | R17: the long-form model ladder, context-guard thresholds, launcher, guard list, Codex spawn rules — installed, read on demand |
| `skills/project-update/render_instructions.py` | R1/I5: `render`, `build`, `measure`, `constitution`; imported by `update.py`, called by path from `install.sh` |
| `skills/project-update/migrations/0003_context_diet.py` | R12/I9: the one structural change the walk cannot make |
| `skills/ai-init/templates/GEMINI.block.md`, `GEMINI.minimal.md`, `junie-guidelines.block.md`, `junie-guidelines.minimal.md` | R14: two more render targets, build artefacts |
| `skills/project-init/templates/GEMINI.md`, `junie-guidelines.md`, `constitution.md` | R14/R10 |
| `skills/ai-init/templates/.ai/rules/README.md` | R9: the format; no rule is shipped |
| `tests/test-instruction-budget.sh` | R2–R6, R9, R10 |
| `tests/fixtures/project-update/schema-v2/` | R12: the migration fixture |
| `tests/fixtures/instructions/rules-project/` | R9: the rules round trip |

### Edited

| Path | What changes |
|---|---|
| `install.sh` | `render_claude_files` / `codex_render` call the renderer; both dry runs print `routing.md`; apply installs `$CLAUDE_DIR/claude-agentic/routing.md` and `$CODEX_DIR/claude-agentic/routing.md`; the size line after `managed_block`; the Codex 16 KiB advisory (I6) |
| `skills/project-update/update.py` | `INSTRUCTION_FILE` / `RUNTIME_MAP` / `PROJECT_INIT_MAP` gain Gemini, Junie and the constitution; `project_runtimes` detects four; new `rules_update`; budget and constitution hints; the `MigrationContext` helpers of I9 and the original-copy rule for migration edits outside `.ai/` |
| `skills/ai-init/scaffold-ai.sh` | `--runtime` accepts a comma list; four block/minimal pairs; `.ai/rules/` created |
| `hooks/project-scaffold.sh` | `put`s the new skeletons and `docs/sdlc/constitution.md`; the skeletons lose `## SDLC workflow` |
| `skills/ai-init/templates/{CLAUDE,AGENTS}.{block,minimal}.md`, `skills/project-init/templates/{CLAUDE,AGENTS}.md` | regenerated build artefacts of `build` |
| `skills/ai-init/templates/.ai/AGENTS.md` | becomes the router (I3), 4 792 → ≈ 2 400 B |
| `skills/ai-task/SKILL.md` | §1 gains the stage diagram and the evidence-label pointer that leave the router |
| `skills/sdlc-spec/SKILL.md`, `skills/sdlc-plan/SKILL.md`, `agents/ai-planner.md` | R11: read `docs/sdlc/constitution.md` first, cite `C<n>`, print the absent-line and continue |
| `skills/ai-init/SKILL.md` | step 4 fills C6+ from the survey |
| `hooks/ai-path-guard-defaults.json` | R15: `task_protected_patterns` gains `.ai/rules/`, `.claude/rules/`, `docs/sdlc/constitution.md` |
| `skills/project-update/history/` (+ `index.json`) | rebuilt by `tools/build-template-history.py` at steps 3, 4 and 5 |
| `tests/run-all.sh` | lists `test-instruction-budget.sh` |
| `tests/test-install-dry-run.sh`, `test-codex-install.sh`, `test-project-update.sh`, `test-scaffold-idempotency.sh` | the amendments of spec I8 |
| `tests/test-guard-characterization.sh` golden | additive records only (R15) |
| `README.md`, `docs/faq.md`, `docs/hooks.md`, `skills/project-update/SKILL.md` | the new shape; "Writing a migration" gains the helpers |
| `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` | spec concern 2: amend the Gemini/Junie bullet to say *project* stubs; mark WP3 done |

### Deleted

| Path | When |
|---|---|
| `CLAUDE.snippet.md`, `AGENTS.snippet.md` | step 3, once `instructions/stub.md` is their single source |

## Order of work

**Step 1 — the renderer, byte-identical (refactor).**
Files: `instructions/stub.md`, `instructions/runtimes.json`,
`skills/project-update/render_instructions.py`, `install.sh`.
`stub.md` holds today's two snippets **verbatim** under `scope=global runtime=claude` and
`scope=global runtime=codex` directives; `render_instructions.py` implements `render` only;
`install.sh:296-300` and `:743-763` call it instead of `render()`. No text changes.
Proof: `bash tests/test-install-dry-run.sh && bash tests/test-codex-install.sh &&
bash tests/test-fable-gate.sh`, plus a temporary `cmp` of the old `render()` output against
the new one for all seven plan combinations (removed at step 3). A refactor: the rendered
bytes must not move.

**Step 2 — `build` and the drift check.**
Files: `skills/project-update/render_instructions.py`, `tests/test-instruction-budget.sh`,
`tests/run-all.sh`, `instructions/stub.md`.
`stub.md` gains the `scope=project|skeleton|skeleton-sdlc` groups that reproduce today's
four block/minimal templates and the two project-init skeletons byte-identically; `build`
writes them; `build --check` exits 1 on drift. The new suite contains the drift assertion
only — no budgets yet. Proof: `python3 skills/project-update/render_instructions.py build
--check` exit 0; `bash tests/test-instruction-budget.sh`;
`bash tests/test-scaffold-idempotency.sh`.

**Step 3 — the diet. ⚠ riskiest step.**
Files: `instructions/stub.md`, `instructions/routing.md`, `instructions/runtimes.json`,
`skills/ai-init/templates/{CLAUDE,AGENTS}.{block,minimal}.md`,
`skills/project-init/templates/{CLAUDE,AGENTS}.md`, `install.sh`,
`tests/test-instruction-budget.sh`, `tests/test-install-dry-run.sh`,
`tests/test-codex-install.sh`, `tests/test-project-update.sh`,
`skills/project-update/history/`, `CLAUDE.snippet.md`, `AGENTS.snippet.md` (deleted).
The split table of the spec's Design section is executed exactly: the stub becomes the text
of spec I2, everything marked "moves" goes to `routing.md`, everything marked "dies" is
deleted. `install.sh` installs `routing.md` to `$CLAUDE_DIR/claude-agentic/routing.md` and
`$CODEX_DIR/claude-agentic/routing.md` and prints the size line. The budget assertions and
the R5 phrase checklist are switched on; the six suites are amended per spec I8. History is
rebuilt. Proof: `bash tests/test-instruction-budget.sh && bash tests/test-install-dry-run.sh
&& bash tests/test-codex-install.sh && bash tests/test-fable-gate.sh &&
bash tests/test-project-update.sh && bash tests/test-merge-migration.sh`.
This step alone is revertable: it touches no engine code.

**Step 4 — router and constitution.**
Files: `skills/ai-init/templates/.ai/AGENTS.md`,
`skills/ai-init/templates/.ai/rules/README.md`,
`skills/project-init/templates/constitution.md`, `skills/project-update/update.py`
(`PROJECT_INIT_MAP` only), `hooks/project-scaffold.sh`, `skills/ai-task/SKILL.md`,
`skills/sdlc-spec/SKILL.md`, `skills/sdlc-plan/SKILL.md`, `agents/ai-planner.md`,
`skills/ai-init/SKILL.md`, `skills/project-update/history/`.
The router is spec I3; every rule that leaves it must already exist in `policies/safety.md`,
`tooling.md` or `context-management.md` — verify each by `grep -n` before deleting it, and
if one is *not* there, that is `SCOPE_CHANGE_REQUIRED`, not a silent new policy file (R8).
The stage diagram lands in `skills/ai-task/SKILL.md` §1. The constitution is `create`-kind
with C1–C5 prefilled. Proof: `bash tests/test-scaffold-idempotency.sh`;
`python3 skills/project-update/render_instructions.py constitution
skills/project-init/templates/constitution.md`; the router path check inside
`tests/test-instruction-budget.sh`.

**Step 5 — four runtimes.**
Files: `skills/project-update/update.py` (`INSTRUCTION_FILE`, `RUNTIME_MAP`,
`project_runtimes`), `skills/ai-init/scaffold-ai.sh`, `hooks/project-scaffold.sh`,
`skills/ai-init/templates/GEMINI.*`, `junie-guidelines.*`,
`skills/project-init/templates/GEMINI.md`, `junie-guidelines.md`,
`instructions/stub.md` (the Gemini/Junie bullet-2 variant), `skills/project-update/history/`,
`tests/test-scaffold-idempotency.sh`, `tests/test-project-update.sh`,
`tests/test-instruction-budget.sh`.
`--runtime` splits on commas, `both` stays `claude,codex`, `auto` detects four. Proof:
`bash tests/test-scaffold-idempotency.sh && bash tests/test-project-update.sh &&
bash tests/test-instruction-budget.sh && bash tests/test-dual-runtime-install.sh`.

**Step 6 — migration 0003. ⚠ second-riskiest.**
Files: `skills/project-update/migrations/0003_context_diet.py`,
`skills/project-update/update.py` (the `MigrationContext` helpers of I9 and the
original-copy rule), `tests/fixtures/project-update/schema-v2/`,
`tests/test-project-update.sh`.
The section is matched **verbatim against a shipped history version** — never by a regex
over the user's prose. An edited block produces a hint, never a write. The migration emits
no `conflict` and no `delete?`, so it never holds `.ai/VERSION`. Proof:
`bash tests/test-project-update.sh && bash tests/test-merge-migration.sh`, and
`grep -Eil 'claude|codex' skills/project-update/migrations/0003_context_diet.py` must find
nothing (the existing convention, `test-project-update.sh:374`).

**Step 7 — `.ai/rules/` rendering and the guard patterns.**
Files: `skills/project-update/update.py` (`rules_update`),
`skills/project-update/render_instructions.py` (the rules renderer),
`hooks/ai-path-guard-defaults.json`, `tests/fixtures/instructions/rules-project/`,
`tests/test-ai-path-guard.sh`, `tests/test-guard-characterization.sh` (golden re-record),
`tests/test-instruction-budget.sh`, `tests/test-project-update.sh`.
Before this step, confirm against the Claude Code documentation whether
`.claude/rules/*.md` supports `paths:` frontmatter (spec concern 7). If it does not, the
`.claude/rules/` output is dropped and nested `CLAUDE.md`/`AGENTS.md` blocks are the whole
mechanism — a documented reduction, not a scope change. The golden file must grow by added
records only: `git diff tests/…/golden* | grep '^-'` must be empty apart from the header.
Proof: `bash tests/test-ai-path-guard.sh && bash tests/test-guard-characterization.sh &&
bash tests/test-project-update.sh && bash tests/test-instruction-budget.sh`.

**Step 8 — reporting and docs.**
Files: `install.sh` (size lines), `skills/ai-status/*` (the budget line),
`skills/project-update/update.py` (hints), `README.md`, `docs/faq.md`, `docs/hooks.md`,
`skills/project-update/SKILL.md`, `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md`
(concern 2's amendment plus the WP3 status row), `tests/test-instruction-budget.sh`,
`tests/test-ai-status-root.sh`.
Proof: `bash tests/test-ai-status-root.sh && bash tests/test-instruction-budget.sh &&
bash tests/test-install-dry-run.sh`.

**Step 9 — verification.**
Files: none (fixes are attributed to the step that owns the file; a fix needed outside
every step's file list is an amendment).
`bash tests/run-all.sh` once, to the end, every failure fixed as one batch.
`test-end-to-end.sh` is inside it, so there is no separate e2e run.
Then `pylint` on the two new Python files at the level `update.py` already holds (10.00/10).

## Risks

**What could this break?**

1. **Every user's global instruction file**, on the next `install.sh`. `managed_block`
   replaces the block wholesale, so a user who reinstalls gets the short stub and loses
   nothing of their own text — but they lose guidance they had been relying on until they
   read `routing.md`. This is the intended change; the mitigation is that step 3 lands and
   is lived with before step 6 migrates any project.
2. **Six test suites grep stub text.** Spec I8 names every line. A missed one fails at the
   step that changes the text, not later.
3. **`project_runtimes` widening to four** changes which files `block_update` walks in an
   *existing* project: a repository that happens to contain a `GEMINI.md` now receives a
   block it did not have. Accepted by the user (open question 2); `--runtime` overrides,
   and the dry run shows it before anything is written.
4. **The history rebuild** runs three times (steps 3, 4, 5). A rebuild that drops a version
   silently breaks `block_update`'s "unchanged since installed" detection for existing
   projects, which would turn a clean replace into a conflict. `test-merge-migration.sh`
   and `test-project-update.sh` cover it; run both after every rebuild, not only at step 9.
5. **The guard golden** (step 7). A non-additive diff means a rule moved, which the intent
   forbids. The `grep '^-'` check is the gate.
6. **A task in flight** during a `/project-update` that runs 0003: WP1's rule already asks
   first, and 0003 adds no new apply path.
7. **Codex's 32 KiB project-doc limit** is only approached by files the plugin does not own;
   the advisory line is the whole intervention.

**Which step is riskiest, and can it move earlier or be split?**

**Step 3.** It deletes the two files that are today the only source of truth, rewrites the
text every user reads every turn, and amends six suites at once. It cannot move earlier —
steps 1 and 2 exist precisely so that step 3 is a *text* change against a renderer already
proven byte-identical. It can be split if it proves unwieldy (3a: `routing.md` extracted,
stub text unchanged apart from the pointer, suites untouched; 3b: the stub cut to I2 and
the budgets switched on) and the implementer should split it rather than carry a red suite
between commits.

**Step 6** is second: it is the only step that writes to a file the user owns. It is last
among the behavioural steps deliberately, so that everything it depends on — the templates,
the history, the four runtimes — is already in place and covered.

## Proof (tests)

| Requirement | Proved by |
|---|---|
| R1 one source | `test-instruction-budget.sh` drift section; `grep -rn` for stub prose outside `instructions/` finds nothing (step 3) |
| R2 no drift | `render_instructions.py build --check` exit 0, in the suite |
| R3 budgets | `test-instruction-budget.sh`: project block ≤ 2048, fresh scaffolded file ≤ 2048, global block ≤ 2560 over seven plan combinations |
| R4 measured on rendered output, user file never failed | the 20 KiB user-file fixture: exit 0, size line printed, text outside the block byte-identical |
| R5 the stub is safe alone | the eight-phrase checklist in `test-instruction-budget.sh` |
| R6 no model names | `grep -Ei 'haiku\|sonnet\|opus\|fable\|gpt-\|terra\|sol\|astra' instructions/stub.md` empty, in the suite |
| R7 router | every backticked path in the table resolves after `scaffold-ai.sh`; the router carries no stage diagram |
| R8 no new policy file | scaffold file count in `test-scaffold-idempotency.sh:17-19` |
| R9 rules | the round trip on `tests/fixtures/instructions/rules-project/`: render, re-render, idempotent; text outside the markers survives; a removed source yields `delete?` |
| R10 constitution | `render_instructions.py constitution` on the shipped template, in the suite |
| R11 spec and planner read it | `grep -n constitution` in `skills/sdlc-spec/SKILL.md`, `skills/sdlc-plan/SKILL.md`, `agents/ai-planner.md`, in the suite |
| R12 migration | the `schema-v2` fixture section of `test-project-update.sh` (section gone, original kept, VERSION 3, second run `0 automatic, 2 conflict`) |
| R13 conflicts never overwritten | the same fixture's `AGENTS.md` case plus `.ai/local/plugin-update/AGENTS.md` |
| R14 four runtimes | `test-scaffold-idempotency.sh` and `test-project-update.sh` reach schema 3 identically for Claude-only, Codex-only and dual |
| R15 guard | `test-ai-path-guard.sh` fixtures; `git diff` of the golden has no `-` lines |
| R16 deterministic, green, space in the path | `tests/run-all.sh` at step 9; the budget test scaffolds and installs under `"$TMP/with space/"` |
| R17 routing.md installed | `test-install-dry-run.sh` and `test-codex-install.sh` grep `$DIR/claude-agentic/routing.md` |

Verification command (step 9): `bash tests/run-all.sh`. There is no separate e2e command —
`test-end-to-end.sh` is a member of that suite.

## Rollback

Per step, before merge: each step is one commit touching a named file set, so
`git revert <sha>` is the unit. Step 3 is the only one whose revert restores deleted files
(`CLAUDE.snippet.md`, `AGENTS.snippet.md`); it is a clean revert because steps 1 and 2 leave
the renderer able to emit the old text from `stub.md`'s history.

After merge, for a user: re-running the previous `install.sh` rewrites the managed block to
the old text — `managed_block` replaces wholesale, so nothing accumulates. The stray
`$CLAUDE_DIR/claude-agentic/routing.md` is inert and can be deleted by hand.

After merge, for a project that already ran 0003: the original instruction file is under
`.ai/reports/project-update-<date>/original/`. Restoring it and setting `.ai/VERSION` back
to `2` returns the project to schema 2; `/project-update` will then offer 0003 again. No
data is lost at any point, because 0003 writes only after copying.

Not rollback-able by a revert: nothing. WP3 has no database change, no API change and no
state-shape change — WP1's `.ai/VERSION` and WP2's state schema 2 are untouched.
