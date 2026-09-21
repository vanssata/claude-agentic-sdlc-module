# Plan: WP6 — `project-update --adopt`

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` ·
Spec: `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp6-adopt.md`

<!-- Stage 3. Concrete, ordered steps the main session executes one at a time. -->

Tier **T3** (spec header: plugin infrastructure shared by both runtimes; no auth, payments or
customer data; no schema step; the guard golden file stays byte-identical). Scope **feature**.
No `ai-security` review. The T5-class deletion is handled by the human gate of R13, outside the
agent, not by re-tiering.

Every flagged concern (1–13) and OQ1–OQ11 were accepted as recommended on 2026-09-22. OQ6 (real
format samples) is the only open item and is **step 1** of this plan. The answers that shape the
work, repeated so no reviewer re-opens them: **split approval in chat** (OQ1), **`human_present()`
for the cleanup gate, `unattended` recorded and shown** (OQ2), **WP1's `--confirm-delete` gets the
same human check now** (OQ3), **`original/` committed, 1 MiB per file** (OQ4), **all eight
fixtures** (OQ5), **flatten `specs/NNN-x/spec.md` to `docs/sdlc/specs/NNN-x.md`** (OQ7), **Kiro
`requirements.md` to `intent/`** (OQ8), **no `.ai/` refuses with exit 5** (OQ9), **`--adopt --check`
is a second line, plain `--check` unchanged** (OQ10), **lines without an alphanumeric character are
ignorable** (OQ11).

The spec lives on branch `spec/wp6-adopt` (commit `1eeb377`), not yet on `main`. Merge that branch
before step 1 so the spec path above resolves.

## Files that change

| Path | Change | Why |
|---|---|---|
| `skills/project-update/adopt.py` | **new** | detection, planning onto `Plan`, transforms, normaliser, both checks, proposal validation, the record, the cleanup plan (spec Components) |
| `skills/project-update/adopt-map.json` | **new** (data) | the mapping table I2, verified against real samples in step 1 |
| `skills/project-update/update.py` | edit | `human_present()`, `clean_tree()`, the human check on `--confirm-delete` (OQ3), `--check --budget` (R21), the `--adopt` family of flags, exit codes 4 and 5, the D5 `hint` in the plain dry run, `tool` on plan items so `report` tags `[speckit]` |
| `skills/project-update/SKILL.md` | edit | new §8 "Adopting a foreign structure" (I12); the Rules list gains "never pass `--confirm-delete` yourself" |
| `skills/ai-status/SKILL.md` | edit | step 7 gets the second line from `--adopt --check` (I11) and `(deleted unattended)` |
| `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp3-context-diet.md` | edit (one sentence) | R13 becomes "never, except by an approved `--adopt`" (concern 3) |
| `tests/test-project-update.sh` | edit | line 432 section runs under `AI_UNATTENDED=1`; a refusal case with stdin from `/dev/null`; a `--check --budget` case; the D5 hint case |
| `tests/test-project-adopt.sh` | **new** | R20: every fixture through a path with a space and one without; row coverage; exit codes; idempotency; checks; cleanup |
| `tests/fixtures/adopt/{speckit,kiro,cursor,copilot,aidlc,junie-gemini,large-claude-md,large-agents-md}/` | **new** | one fixture per foreign structure, each with a `README.md` naming the format assumption and its source; `split-proposal.json` where a split applies |
| `tests/run-all.sh` | edit | registers `test-project-adopt.sh` |
| `README.md` | edit (short) | one paragraph on `--adopt` under the `/project-update` section |

Not touched, on purpose: every hook and guard file, `tests/test-guard-characterization.sh`,
`.ai/VERSION` handling, `skills/project-update/migrations/`, `state.py`, every policy JSON, every
profile. `update.py` may pass 1 200 lines (concern 13); if pylint's module-size check fires,
`human_present` and `clean_tree` move into `adopt.py` in the same step.

## Order of work

Each step is one commit and leaves `tests/run-all.sh` green. Tests are run once, to the end, after
the last step; a step runs only the scoped file it names.

1. **Verify the format assumptions and write the fixtures (OQ6, concern 1).** For each of Spec Kit,
   Kiro, AI-DLC, Cursor and Copilot, read the tool's public repository or documentation with the
   built-in browser and record in `tests/fixtures/adopt/<tool>/README.md`: the layout, the
   frontmatter keys, the source URL and the date. Build the eight fixtures from those facts (a
   handful of files each; the two `large-*` fixtures carry a >2048 B instruction file with the
   shipped block and a canned `split-proposal.json`; `junie-gemini` carries both instruction files
   at the small size). Write `adopt-map.json` from the spec's I2, corrected where a sample
   disagrees, and note every correction in the README. Also create `.ai/` in each fixture the way
   `schema-v4` does, so a fixture is "current" for R5.
   *Proof:* the READMEs exist and cite a source; `python3 -c 'import json; json.load(open("skills/project-update/adopt-map.json"))'`.
   No behaviour changes.

2. **Human gates in `update.py` (OQ3, R5's building blocks).** Add `human_present()` (duplicated
   from `state.py:876-879` with a comment) and `clean_tree(root)` (`git status --porcelain
   --untracked-files=all`, list arguments, `check=False`). Make `--apply --confirm-delete NAME`
   refuse with exit 5 and `ADOPT_REFUSED` on the first stdout line when `human_present()` is false.
   Amend `tests/test-project-update.sh:432-443` to export `AI_UNATTENDED=1`, and add one case
   `python3 "$UPDATE" "$S3" --apply --confirm-delete tester </dev/null` with `AI_UNATTENDED` unset
   expecting exit 5 and the untouched file. Register exit code 5 in the module docstring.
   *Proof:* `bash tests/test-project-update.sh`.
   **This is the one WP1 behaviour change**; it lands first so every later step is tested under the
   final gate.

3. **`--check --budget` (R21).** In `main()`, when both flags are given, measure each root
   instruction file with `render_instructions.measure`: block over `_budgets.project` or whole file
   over `_budgets.skeleton` prints one line per offender and exits 1. Plain `--check` output is
   byte-identical (assertions at `tests/test-project-update.sh:69,102,188`).
   *Proof:* two new cases in `tests/test-project-update.sh` (a small file exits 0, a padded one
   exits 1); the three existing `--check` assertions still pass.

4. **`adopt.py` core: table, detection, dry-run plan, report lines (R1–R4, R18, R23).** Load and
   validate `adopt-map.json` (unknown transform or bad glob → exit 2, as a bad migration
   registry). `detect(root, table)`: signatures at the root only, `.ai/` skipped, nested signatures
   listed `unmapped`. A matcher where `*` stops at `/` and `**` crosses it, first row wins.
   `plan_adopt` adds items to the shared `Plan` with `migration=None` and a new `tool` field
   (`Plan.add` gains `tool=None`; `report` prints `[tool]` before the note when set) for the
   transforms `copy`, `append-section`, `rule` (frontmatter rewrite, `dest: auto` rule), `drop`
   and `ignore`. `decisions.json` (I6) is read when present and its `unmapped` entries settle rows.
   The secret hint (I7) runs over every source. New flags `--adopt`, `--mode` (default `migrate`),
   `--tool`; the new report lines `detect`, `adopt`, `dropped`, `ignored`, `unmapped`, `hint` in
   I3's layout; the summary tail counts `unmapped`. The dry run writes nothing; `unmapped` exits 4.
   *Proof:* the first half of `tests/test-project-adopt.sh`: each of speckit, kiro, cursor,
   copilot, aidlc through a dry run, both path variants; a sha of the whole tree before and after
   is equal; a row that matches nothing in its own fixture fails the test; the `.kiro/hooks` file
   exits 4; a nested `packages/x/.cursor/rules/` exits 4; the secret line prints `file:line` and
   not the value; `--mode coexist` must be spelled out.

5. **The two checks, router rows, the record and `--adopt --check` (R9–R12, R14, R16, I7–I11).**
   `normalise`, `check_lines` over `plan.final` with `dropped.jsonl` entries generated by the
   transforms (`by: transform:<name>`, whole-file `drop` as one `"line":"*"` record with a sha);
   `check_refs` with the hard and warn scopes of I8 (compiled alternation, `git ls-files`, NUL
   check, 20 MiB cap) and the inverted "every linked path exists" in coexist; router rows appended
   after the last row of the routing table in `.ai/AGENTS.md`, idempotent by text, coexist rows
   with the "kept in place" suffix; `record()` producing `adopt.json`, `report.md` and
   `dropped.jsonl` under `.ai/reports/adopt-<date>/`, merged by source path on the same day;
   `--adopt --check` printing exactly one of I11's five lines, `regenerated` from a sha mismatch.
   In the dry run the checks run on `plan.final` and print the two `check` lines and `cleanup?`.
   *Proof:* the second half of `tests/test-project-adopt.sh`: `check no-line-lost PASS` on every
   fixture; a fixture with a deliberately unmapped line in `dropped.jsonl` fails with the `file:line`
   list; a stale `@.cursorrules` reference planted in `.ai/policies/x.md` fails no-dangling, the
   same reference in `src/README.md` is a warning only; coexist writes only router rows and
   `adopt.json`; `--adopt --check` exit 0/1 for each of the five lines.

6. **`--adopt --apply`: the R5 gates, originals, idempotency, the D5 hint (R5, R6, R15, R16).**
   Before `apply(plan)`: not a git tree, dirty tree outside the three allowed prefixes,
   `current.json` short of `done`, plain `--check` would exit 1, or no `.ai/` → exit 5 with the
   reason and the command to run first. Every moved or rewritten source goes through
   `keep_original` (`update.py:981`), skipped over 1 MiB or with a NUL in the first 8 KiB and listed
   `original-skipped (git has it)`; the total is printed and recorded. After the write the two
   checks run **on disk** and `adopt.json.checks` gets `checked_at`. A second `--adopt` on the
   result prints `0 automatic` and writes nothing; an interrupted apply resumes through
   `apply_item`'s `expect` preconditions. The plain dry run gains a `hint` line for detection and
   for regeneration. `rules_update(plan, runtimes)` runs in the same plan so nested rule blocks
   render for new `.ai/rules/` files.
   *Proof:* `tests/test-project-adopt.sh`: each R5 refusal by exit code and first stdout line; a
   fixture applied twice; a kill between two items simulated by planting a half-written destination
   and re-running; `original/` mode preserved; a 1 MiB + 1 byte file skipped; the plain dry run of
   an adopted fixture shows no conflict on `.ai/AGENTS.md` after the router rows; changing a source
   makes `--adopt --check` say `regenerated`.

7. **The instruction-file transform: split candidate, request, proposal, fallback, diff (R7, R8,
   R17, R19; concern 3).** ← **riskiest step.** Candidate = whole file with the block re-rendered
   from the shipped template over `_budgets.skeleton`; the source is the file minus the block (or
   minus only the markers when the block was edited, WP3 R13's case). `--split-request` writes I4
   with the outline and the allow-list and nothing else; `load_proposal` validates I5 (sha, 1-based
   inclusive non-overlapping ranges covering every line outside the block, allow-list, `dirs` on
   `.ai/rules/`, non-empty `why`, keep budget) and exits 4 with the reason; `--split fallback`
   moves every line outside the block verbatim to `.ai/policies/adopted/<file-slug>.md` with one
   router row; `--diff` prints `difflib.unified_diff` per target; one proposal per `source_sha` is
   reused. The four instruction files are never listed for cleanup. Add the one sentence to WP3
   R13 in its spec. The moved lines into `.ai/project/overview.md` append under a generated heading.
   *Proof:* `large-claude-md` and `large-agents-md` reach the same destinations from their canned
   proposals (parity, R19); a proposal with a gap, an overlap, a wrong sha, a disallowed dest and an
   over-budget keep each exit 4 naming the reason; the fallback produces `PASS` on both checks;
   `junie-gemini` at the small size lists no `split?`; a hand-edited block goes through the split
   and ends with the shipped block; the resulting file is under `_budgets.skeleton`
   (`--check --budget` exits 0); `bash tests/test-shared-prompts-model-free.sh` is untouched by this
   step because no SKILL text changes yet.

8. **Cleanup (R13, R14's refusal).** `plan_cleanup` reads the latest `adopt.json`, refuses (exit 5)
   on a source sha mismatch, in coexist, or when R12 does not hold; recomputes both checks on the
   current tree; lists exactly the `cleanup: true` sources as `delete?` items. `--apply
   --confirm-delete NAME` requires `human_present()` and writes `cleanup.{confirmed_by, at,
   unattended, tty}` before the first removal; removal reuses the migration deletion path so the
   "nothing else in this file removes a file" docstring at `update.py:449` stays true after being
   amended to name the two callers.
   *Proof:* `tests/test-project-adopt.sh`: a cleanup dry run lists the right set; `--apply
   --confirm-delete` with stdin from `/dev/null` and no `AI_UNATTENDED` exits 5; with
   `AI_UNATTENDED=1` it deletes, `adopt.json.cleanup.unattended` is true, and `original/` still
   holds every file; a source changed after adopt makes cleanup refuse; coexist cleanup prints
   `coexist keeps the foreign files`; `--adopt --check` afterwards says "up to date" and a
   reappearing `.cursorrules` says `regenerated`.

9. **The two SKILL flows, `/ai-status`, README, registration (I11, I12, C-parity).** Write
   `skills/project-update/SKILL.md` §8 with tier names only (BALANCED, once, in the session when
   `max_parallel_agents` is 1, else one subagent; Pro, Plus and `AI_UNATTENDED` use the fallback;
   never pass `--confirm-delete` yourself; hand the human the full command). Add the second line
   to `skills/ai-status/SKILL.md` step 7. Add the README paragraph. Register the new test in
   `tests/run-all.sh`. Run pylint on 3.11–3.13 locally for `adopt.py` and `update.py`
   (`pylint $(git ls-files '*.py')`).
   *Proof:* `bash tests/test-shared-prompts-model-free.sh` (no model name in the new SKILL text),
   `bash tests/test-ai-status-root.sh`, then **the single full run** `bash tests/run-all.sh` and
   `pylint`; every failure fixed as one batch.

## Risks

**What could this break?**

- **WP1's `--confirm-delete` path** (step 2): the existing test at lines 432–443 passes today only
  because a local run has a TTY; under CI it would fail after the gate. Mitigation: the test section
  exports `AI_UNATTENDED=1` in the same commit, and the new refusal case redirects stdin from
  `/dev/null` so a terminal run cannot pass by accident (spec risk 5).
- **`Plan.add` and `report`** are shared with every migration. Adding `tool=None` as a keyword with a
  default keeps every existing caller; `report` prints `[tool]` only when set, so the `schema-v*`
  fixtures' output stays byte-identical (`tests/test-project-update.sh` asserts on exact lines).
- **The plain `--check` line** is read by `/ai-status` and asserted three times. Nothing in step 4–8
  touches that branch; `--adopt --check` is a separate branch taken before it (OQ10).
- **`.ai/AGENTS.md` is plugin-owned and three-way merged.** Router rows are project edits to it;
  the next plain dry run must see them as "ours" and keep them, not as a conflict. Step 6's proof
  runs the plain dry run on an adopted fixture and asserts no `conflict` line.
- **An edited managed block** (step 7) is replaced after its lines move out. That is the one place
  this package contradicts WP3 R13's literal text; the spec amends R13 and the original is kept.
- **Deleting under `.claude/` or `.codex/`** (Spec Kit commands, step 8) happens only outside a
  task, where WP7's `task_protected_patterns` is not armed. Step 8's proof runs with no
  `current.json`; a second case with a `current.json` at stage `plan` asserts exit 5 before any
  removal.
- **The warn-scope scan** on a large repository. Bounded by `git ls-files`, the NUL check, the
  20 MiB cap and one compiled alternation (spec risk 4).
- **`update.py` module size** under pylint (concern 13). If `too-many-lines` fires it is not in the
  disabled list; `human_present` and `clean_tree` move to `adopt.py` in that step, with the import
  updated.
- **Format assumptions** (concern 1) are the largest unknown and sit in step 1 on purpose: every
  later step is built against verified fixtures, and R4's `unmapped` fails loudly in the field.

**Riskiest step:** 7, the instruction-file transform. It cannot move earlier because it needs the
checks (5) and the apply gates (6); it is already split from the proposal *production* (a SKILL
concern, step 9) and from cleanup (8). The fallback path is proven before the proposal path inside
the step so a broken validator never blocks a project.

## Proof (tests)

| Req | Proof |
|---|---|
| R1 | `test-project-adopt.sh`: one `detect` line per tool with counts on every fixture; a fixture with no signature prints `no foreign structure detected`, exit 0 |
| R2 | tree sha before and after the dry run, `--split-request` excepted, on every fixture |
| R3 | `--mode coexist` absent → `mode: migrate` in the dry-run header; `--mode` with another value → argparse exit 2 |
| R4 | `.kiro/hooks/x.json` and `packages/x/.cursor/rules/a.mdc` listed `unmapped`, exit 4; settled by `decisions.json` → exit 0 |
| R5 | five refusal cases, each exit 5 with `ADOPT_REFUSED` on stdout line 1 |
| R6 | `original/` present with mode; the >1 MiB and the NUL file listed `original-skipped`; the byte total in `adopt.json.original_bytes` |
| R7 | `--split-request` writes only `split-request.json`; the same proposal is reused on a second run (mtime unchanged); `--diff` output contains `---`/`+++` for each target |
| R8 | `large-*` fixtures list `split?`; `--apply` with neither proposal nor fallback → exit 4; fallback → one `.ai/policies/adopted/` file and one router row |
| R9 | a proposal cannot carry text (schema rejects a `text` key); every destination line traced to a source or generated line by the check |
| R10 | `check no-line-lost PASS` on all eight fixtures; a planted miss → `FAIL: 1 line(s) of <src>`, exit 4 |
| R11 | a planted hard-scope reference → FAIL, exit 4; a warn-scope reference → PASS with `1 warning(s)`; coexist with a missing linked path → FAIL |
| R12 | `adopt.json.checks.*.checked_at` set after apply; `--adopt --check` says `incomplete` when a check is forced to fail |
| R13 | cleanup lists only `cleanup: true` sources; stdin `/dev/null` → exit 5; `AI_UNATTENDED=1` → deleted with `unattended: true`; sha mismatch → exit 5 |
| R14 | coexist: only `.ai/AGENTS.md` and `adopt.json` change; `--cleanup` → exit 5 with the message |
| R15 | second `--adopt` prints `0 automatic`, tree sha unchanged; interrupted apply completes |
| R16 | changed source → `regenerated` from `--adopt --check`, from the plain dry run `hint`, and via `test-ai-status-root.sh` |
| R17 | the four instruction files never appear in the cleanup list; their block is the shipped one after the split |
| R18 | a planted `src/app.py` mentioning `.cursorrules` is neither a source nor a destination, only a warning |
| R19 | `large-claude-md` and `large-agents-md` produce the same destination set; `test-shared-prompts-model-free.sh` passes |
| R20 | every fixture has `README.md` with a `Source:` line; `run_fixture` executes each under `$TMP/with space/` and `$TMP/plain/` |
| R21 | `--check --budget` exit 0 and 1 cases in `test-project-update.sh`; the three existing `--check` assertions untouched |
| R22 | `pylint $(git ls-files '*.py')` clean under 3.11, 3.12, 3.13 (CI matrix in `.github/workflows/pylint.yml`) |
| R23 | the planted `API_KEY=…` line prints `hint <file>:<line>` and the value string is absent from stdout |

Verification command, once, after step 9: `bash tests/run-all.sh` and `pylint $(git ls-files '*.py')`.

## Rollback

- **The plugin:** revert the merge commit of the WP6 branch. `adopt.py` and `adopt-map.json` are
  new files; the `update.py` edits are additive flags plus the `--confirm-delete` gate, so a revert
  restores WP1's behaviour exactly. No migration, no schema bump, no `.ai/VERSION` change: a project
  updated by the reverted plugin is unaffected.
- **A project that ran `--adopt --apply`:** nothing was committed by the tool. `git checkout -- . &&
  git clean -fd -e .ai/reports/` restores the tree; `.ai/reports/adopt-<date>/original/` holds every
  moved file with its mode when the tree had already been committed.
- **A project that ran `--cleanup`:** the deletion happened on a clean tree, so `git checkout --
  <path>` restores each file, and `original/` is a second copy. `adopt.json.cleanup` names who
  confirmed and when.
- **Step 2 alone** (the human gate on `--confirm-delete`): if it blocks a legitimate headless
  deletion, `AI_UNATTENDED=1` is the documented switch and no code revert is needed.
