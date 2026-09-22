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
| `skills/project-update/update.py` | edit | imports `human_present()`/`clean_tree()` from `adopt.py`, the human check on `--confirm-delete` (OQ3), the `--check --budget` branch (R21), the `--adopt` family of flags, `rules_update(..., planned=None)` (HIGH 5), the adopt `report_dir`, exit codes 4 and 5, the D5 `hint` in the plain dry run, `tool` on plan items so `report` tags `[speckit]` |
| `skills/project-update/SKILL.md` | edit | new §8 "Adopting a foreign structure" (I12); the existing "never pass `--confirm-delete` yourself" rule (`SKILL.md:78-79`, `:159`) is referenced from §8, not repeated |
| `skills/ai-status/SKILL.md` | edit | step 7 gets the second line from `--adopt --check` (I11) and `(deleted unattended)` |
| `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp3-context-diet.md` | edit (one sentence) | R13 becomes "never, except by an approved `--adopt`" (concern 3) |
| `tests/test-project-update.sh` | edit | `AI_UNATTENDED=1` on the confirmed deletions at lines 435 and 482; a refusal case with stdin from `/dev/null`; a `--check --budget` case; the D5 hint case |
| `tests/test-project-adopt.sh` | **new** | R20: every fixture through a path with a space and one without; row coverage; exit codes; idempotency; checks; cleanup |
| `tests/fixtures/adopt/{speckit,kiro,cursor,copilot,aidlc,junie-gemini,large-claude-md,large-agents-md}/` | **new** | one fixture per foreign structure, each with a `README.md` naming the format assumption and its source; `split-proposal.json` where a split applies |
| `tests/run-all.sh` | edit | registers `test-project-adopt.sh` |
| `tests/test-ai-status-root.sh` | edit | two phrase checks for the `--adopt --check` line and `(deleted unattended)` (plan-review HIGH 8) |
| `skills/project-update/render_instructions.py` | edit | `DEFAULT_BUDGETS` fallback in `budgets()` when `instructions/runtimes.json` is not installed (plan-review HIGH 3) |
| `README.md` | edit (short) | one paragraph on `--adopt` under the `/project-update` section |

Not touched, on purpose: every hook and guard file, `tests/test-guard-characterization.sh`,
`.ai/VERSION` handling, `skills/project-update/migrations/`, `state.py`, every policy JSON, every
profile. `update.py` may pass 1 200 lines (concern 13). pylint will not say so: `too-many-lines`
is C0302 and `.pylintrc:12-13` disables every `C` message. The trigger is therefore explicit:
**every new function goes into `adopt.py`**; `update.py` gains only flag parsing, the calls into
`adopt`, the `--confirm-delete` gate and the `--check --budget` branch. `human_present` and
`clean_tree` live in `adopt.py` from the start and `update.py` imports them (plan-review LOW).

## Order of work

Each step leaves `tests/run-all.sh` green and is one reviewable unit; the human commits (or not)
between steps — no agent commits. Tests are run once, to the end, after the last step; a step runs
only the scoped file it names.

1. **Verify the format assumptions and write the fixtures (OQ6, concern 1).** For each of Spec Kit,
   Kiro, AI-DLC, Cursor and Copilot, read the tool's public repository or documentation with the
   built-in browser and record in `tests/fixtures/adopt/<tool>/README.md`: the layout, the
   frontmatter keys, the source URL and the date. Build the eight fixtures from those facts (a
   handful of files each; the two `large-*` fixtures carry a >2048 B instruction file with the
   shipped block and a canned `split-proposal.json`; `junie-gemini` carries both instruction files
   at the small size). Write `adopt-map.json` from the spec's I2, corrected where a sample
   disagrees, and note every correction in the README.
   **Fixtures are stored encoded** (plan-review BLOCKER 1): the path guard
   (`hooks/ai-path-guard-defaults.json`) denies writes to `.cursorrules`, `.cursor/rules/`,
   `.claude/commands/`, `.github/copilot-instructions.md`, `.junie/`, `.codex/prompts/`, `.ai/**`
   anywhere in the tree, fixtures included. Every path component that starts with `.` is stored
   with a `dot-` prefix instead (`dot-cursorrules`, `dot-cursor/rules/a.mdc`,
   `dot-github/copilot-instructions.md`). The instruction files are encoded too, so Claude Code or
   Codex never loads a fixture's 2 KB+ `CLAUDE.md` while working in the fixture directory
   (re-review LOW): `CLAUDE.md` → `fixture-CLAUDE.md`, likewise `AGENTS.md` and `GEMINI.md`;
   other files without a leading dot (`aidlc-docs/`) are stored as they are. Checked on 2026-09-22 by feeding both forms
   to `hooks/ai-path-guard.sh`: the literal form is denied, the `dot-` form is allowed. No fixture
   carries `.ai/`: `run_fixture` (step 4) copies the fixture to `$TMP`, renames every `dot-`
   component back to `.` and every `fixture-` prefix off, scaffolds `.ai/` from the current templates the way
   `tests/test-project-update.sh:574-576` does, and runs `git init`, `git config user.email
   t@example.com`, `git config user.name t` (as `tests/test-end-to-end.sh:18`) and `git commit`
   there, so a
   fixture is "current" and clean for R5 and never goes stale (also closes review MEDIUM 9). The
   planted `API_KEY=` line (R23) is written by the test, not committed.
   Fixture content is written for this repository from the documented layout, not copied from
   upstream samples (licence): the README cites the source, the files only reproduce its shape.
   *Proof:* the READMEs exist and cite a source; `python3 -c 'import json; json.load(open("skills/project-update/adopt-map.json"))'`;
   `find tests/fixtures/adopt -name '.*' -o -name CLAUDE.md -o -name AGENTS.md -o -name GEMINI.md`
   prints nothing.
   No behaviour changes.

2. **Human gates (OQ3, R5's building blocks).** Add to a new `adopt.py` `human_present()` (duplicated
   from `skills/ai-task/state.py:876-879` — the repo copy; the installed one has none — with a
   comment) and `clean_tree(root)` (`git status --porcelain -z --untracked-files=all`, list
   arguments, `check=False`). Make `--apply --confirm-delete NAME` refuse with exit 5 and
   `ADOPT_REFUSED` on the first stdout line when `human_present()` is false. The gate runs **after**
   argparse validation, so `tests/test-project-update.sh:433-434` (no `--apply`, empty name) still
   exit 2.
   **Both existing confirmed deletions get the variable on the command itself** (plan-review
   BLOCKER 2): `AI_UNATTENDED=1 python3 "$UPDATE" … --apply --confirm-delete tester` at
   `tests/test-project-update.sh:435` and `AI_UNATTENDED=1 python3 "$UPDATE" … --apply
   --confirm-delete "Ivan"` at `:482` (the rules-gate section). No `export`: it would leak into the
   rest of the script and hide the next caller that forgets it. A `grep -n 'confirm-delete'
   tests/*.sh` at the start of the step lists every caller; each gets the same treatment or a
   comment saying why not. Add one case `python3 "$UPDATE" "$S3" --apply --confirm-delete tester
   </dev/null` with `AI_UNATTENDED` unset, expecting exit 5, `ADOPT_REFUSED` on line 1 and the
   untouched file. Register exit code 5 in the module docstring, which gains an exit-code section
   and `--confirm-delete` on its usage line.
   *Proof:* `bash tests/test-project-update.sh` from the agent's shell (no TTY), so a run that
   passes only on a terminal cannot slip through.
   **This is the one WP1 behaviour change**; it lands first so every later step is tested under the
   final gate.

3. **`--check --budget` (R21).** In `main()`, when both flags are given, measure each root
   instruction file: block over `_budgets.project` or whole file over `_budgets.skeleton` prints
   one line per offender and exits 1. `render_instructions.measure` prints every file and measures
   one kind per call, so it is not reused as is; the sizes come from `block_of` and a byte count
   in a small `budget_offenders(root, caps)` that returns only the offenders (plan-review LOW).
   Plain `--check` output is byte-identical: the assertions at
   `tests/test-project-update.sh:69,102,188` check only the exit code, so this step adds one
   exact-line assertion on the plain `--check` stdout of a current and of a behind project, taken
   from today's output before any code changes (plan-review MEDIUM 12).
   **Budgets must exist in an installed plugin** (plan-review HIGH 3): `DEFAULT_SOURCE` is
   `parents[2]` of the script (`render_instructions.py:66`), which in an install is `~/.claude/`,
   and `install.sh` never copies `instructions/`. `render_instructions.budgets()` gains a fallback:
   when `runtimes.json` is absent it returns a module constant `DEFAULT_BUDGETS` equal to today's
   `_budgets` (`global 2560, project 2048, skeleton 2048, skeleton-sdlc 2048`); a
   `runtimes.json` that exists but is malformed still raises. A test asserts the constant equals
   `jq ._budgets instructions/runtimes.json`, so the two cannot drift. `budget_hints`
   (`update.py:781-784`) then never goes silent for this reason. Step 7's split candidate and keep
   budget read budgets through the same call.
   *Proof:* two new cases in `tests/test-project-update.sh` (a small file exits 0, a padded one
   exits 1); one case that copies `skills/project-update/` alone into `$TMP/skills/` and runs
   `--check --budget` from there (exit 1 on the padded file, not a traceback); the drift assertion;
   the three existing `--check` assertions still pass.

4. **`adopt.py` core: table, detection, dry-run plan, report lines (R1–R4, R18, R23).** Load and
   validate `adopt-map.json` (unknown transform or bad glob → exit 2, as a bad migration
   registry; the validator accepts `instruction-file` from this step, implemented in step 7).
   `detect(root, table)`: signatures at the root only, `.ai/` skipped, nested signatures
   listed `unmapped`. **The four instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`,
   `.junie/guidelines.md`) follow one rule** (plan-review HIGH 4 and re-review A): the plugin
   scaffolds all four with its managed block (`scaffold-ai.sh:49-61,111`) and treats them as
   runtimes (`update.py:117-120`), so a bare signature would make every project "foreign".
   (a) A file **without** a managed block (`render_instructions.block_of` returns `None`) is
   foreign and detected by its signature. (b) A file **with** a managed block is the plugin's and
   is never `detect`ed as a tool; it only appears as `split?` when it is a split candidate.
   A candidate is a file whose whole size, with the block re-rendered from the shipped template,
   is over `_budgets.skeleton`; the scaffold's own lines outside the block count toward that size
   (they are what the budget was set for), so a fresh scaffold (≈1.9–2.0 KB) is not a candidate
   and a scaffold plus a few hundred bytes of project notes may become one — that is the intended
   signal, reported as `split?`, never as `unmapped`.
   A matcher where `*` stops at `/`, `**` crosses it and `**/` also matches zero directories,
   first row wins. **A row only ever matches files under its tool's `roots`** (plan-review
   MEDIUM 13): the Spec Kit drop row `*/**/speckit*` (spec I2, line 213) would otherwise match
   `src/lib/speckit_x.py`, make it a `cleanup: true` source and delete it at cleanup. The
   candidate set is the union of the detected tools' `roots`; each row is tried only against its
   own tool's candidates. **A file under two tools' roots** (re-review C: Spec Kit installs
   `.cursor/commands/speckit*`, which is under Cursor's `.cursor/`) is taken by the first detected
   tool, in table order, whose row matches it, and is `unmapped` only when no detected tool's row
   matches it.
   **Informational lines are not plan items** (plan-review MEDIUM 11): `report`
   (`update.py:1089`), the `--check` pending count (`:1154`) and the apply loop count every item
   whose action is not `conflict`/`delete?` as automatic. `detect`, `dropped`, `ignored`,
   `unmapped`, `hint`, `split?`, `check` and `cleanup?` therefore go to a separate
   `plan.adopt_notes` list printed by `adopt.report_notes(plan)` before the summary tail; only
   `adopt` (a write) and `delete?` are `Plan` items. That keeps R15's `0 automatic` true and the
   plain run's counts unchanged.
   `plan_adopt` adds items to the shared `Plan` with `migration=None` and a new `tool` field
   (`Plan.add` gains `tool=None`; `report` prints `[tool]` before the note when set) for the
   transforms `copy`, `append-section`, `rule` (frontmatter rewrite, `dest: auto` rule), `drop`
   and `ignore`. `decisions.json` (I6) is read when present and its `unmapped` entries settle rows.
   **Inputs are found in any record, not only today's** (plan-review MEDIUM 16):
   `decisions.json` is taken from the greatest `adopt-*` directory that has one, and a
   `split-proposal.json` from any `adopt-*` directory whose proposal `source_sha` matches the
   current file — so a decision taken before midnight UTC still holds after it.
   The secret hint (I7) runs over every source. New flags `--adopt`, `--mode` (default `migrate`),
   `--tool`; the new report lines `detect`, `adopt`, `dropped`, `ignored`, `unmapped`, `hint` in
   I3's layout; the summary tail counts `unmapped`. The dry run writes nothing; `unmapped` exits 4.
   *Proof:* the first half of `tests/test-project-adopt.sh`: each of speckit, kiro, cursor,
   copilot, aidlc through a dry run, both path variants; a sha of the whole tree before and after
   is equal; a row that matches nothing in its own fixture fails the test (the coverage map names
   the fixture for each row: `claude` → `large-claude-md`, `codex` → `large-agents-md`, `gemini` and
   `junie` → `junie-gemini`, every other tool → the fixture of the same name); a planted
   `src/lib/speckit_x.py` is neither a source nor a `delete?`; `decisions.json` in an
   `adopt-<yesterday>/` directory settles its row; a tree whose only detected rows are `ignore`
   prints the `ignored` lines and `0 automatic`; the `.kiro/hooks` file exits 4; a nested `packages/x/.cursor/rules/` exits 4; the secret line prints `file:line` and
   not the value; `--mode coexist` must be spelled out; a fresh scaffold for claude, codex, gemini,
   junie and claude+codex prints `no foreign structure detected` and exits 0; a `GEMINI.md`
   without a managed block is `detect`ed as gemini; a tree with both Spec Kit and Cursor has
   `.cursor/commands/speckit.plan.md` dropped by speckit and nothing `unmapped`; and the same scaffold with ~200 B
   of project notes appended lists `split?` for that file and still no `unmapped`.

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
   same reference in `src/README.md` is a warning only; the coexist dry run lists only router rows
   and `adopt.json` as writes; `--adopt --check` exit 0/1 for each of the five lines.
   **No proof here needs step 6's apply** (plan-review MEDIUM 10): the `--adopt --check` states
   that presuppose an applied adoption (`up to date`, `incomplete`, `regenerated`) are driven by a
   planted `adopt-<date>/adopt.json` (written by a `plant_record` test helper with the shape of
   I10) over a tree that already has the destinations; the on-disk coexist write is proven in step
   6.

6. **`--adopt --apply`: the R5 gates, originals, idempotency, the D5 hint (R5, R6, R15, R16).**
   Before `apply(plan)`: not a git tree, dirty tree outside the three allowed prefixes,
   `current.json` short of `done`, plain `--check` would exit 1, or no `.ai/` → exit 5 with the
   reason and the command to run first.
   **The adopt record has its own directory and its own copier** (plan-review HIGH 6):
   `plan.report_dir` is set to `.ai/reports/adopt-<date>/` for an adopt run (today it is always
   `project-update-<date>`, `update.py:507`). Originals go through a new
   `adopt.keep_original_bounded(plan, rel)`, not `keep_original` (`update.py:981-985`): same copy
   with mode, plus the 1 MiB and NUL-in-first-8-KiB skip listed `original-skipped (git has it)`.
   It is called for **every** adopt item that moves or rewrites a source, the rewritten `CLAUDE.md`
   / `AGENTS.md` included — the content path at `update.py:1071` copies originals only for
   migration items, so adopt cannot rely on it. The total is printed and recorded. Adopt never
   writes `migration.json`. "Latest record" everywhere (`--adopt --check`, cleanup, the D5 hint)
   means the greatest `adopt-*` directory **that contains `adopt.json`**.
   **Apply order and resume** (plan-review HIGH 7): items are applied in three phases — (1) every
   new destination and router row, (2) every rewrite of an instruction file, (3) nothing else; a
   source is never rewritten before every line it gives away exists at its destination. The R5
   clean-tree gate accepts a dirty tree when every dirty path is in `adopt.json.planned_writes`
   of the latest record with `status: partial`, so a re-run after an interruption is allowed and
   nothing else is (re-review B). `planned_writes` is every target of the plan — destinations,
   `.ai/AGENTS.md` (router rows), the rewritten instruction files, every `rules_update` output
   (`<dir>/CLAUDE.md`, `<dir>/AGENTS.md`, `.claude/rules/*.md`) and the record directory itself.
   `rules_update` items belong to phase 1, so after an interruption plain `--check` does not
   exit 1 for a reason the re-run is about to fix; the R5 gate "plain `--check` would exit 1" is
   evaluated with `planned_writes` excluded when resuming. `adopt.json` is written with
   `status: partial` and `planned_writes` before phase 1 and `status: applied` after the on-disk checks. `load_proposal`'s sha check
   compares against `adopt.json.sources[].sha` when the record is partial, so a source already
   rewritten in phase 2 is still recognised.
   After the write the two checks run **on disk** and `adopt.json.checks` gets `checked_at`. A
   second `--adopt` on the result prints `0 automatic` and writes nothing. The plain dry run gains
   a `hint` line for detection and for regeneration.
   **Nested rule blocks after apply** (plan-review HIGH 5): `rules_update` reads `.ai/rules/` from
   disk (`update.py:701-705`), so it cannot see files the same plan is about to create. Its
   signature becomes `rules_update(plan, runtimes, planned=None)`; when `planned` (a map
   `rel → text` of `.ai/rules/*.md` from `plan.final`) is given, `update.py` builds the rule list
   itself — the on-disk rules via `load_rules`, then each planned text through
   `render_instructions.parse_rule` replacing or adding by slug — so `render_instructions.py`
   is not touched in this step. Adopt passes it; the plain update passes nothing, so its behaviour and
   output are unchanged.
   *Proof:* `tests/test-project-adopt.sh`: each R5 refusal by exit code and first stdout line; a
   fixture applied twice; an interruption simulated by running phase 1 only (`ADOPT_STOP_AFTER=1`,
   read only when `CLAUDE_AGENTIC_TEST=1` is also set, and listed as test-only in the module
   docstring; `ADOPT_TODAY` in step 8 follows the same rule) and then a normal re-run — the second run is allowed past
   the clean-tree gate, completes and passes both checks; the same with `ADOPT_STOP_AFTER=2`; a dirty
   path that is *not* a planned destination still refuses; `original/` holds the rewritten
   `CLAUDE.md` with its mode; a 1 MiB + 1 byte file skipped; no `migration.json` under `adopt-*`;
   `--mode coexist --apply` changes only `.ai/AGENTS.md` and writes `adopt.json` (tree diff);
   a fixture that adopts a `.cursor/rules/*.mdc` with `globs:` has its nested block rendered and
   **plain `--check` exits 0 right after apply**; the plain dry run of an adopted fixture shows no
   conflict on `.ai/AGENTS.md` after the router rows; changing a source makes `--adopt --check` say
   `regenerated`.

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
   **No model text reaches a destination** (plan-review MEDIUM 14): I5's `heading` is accepted only
   when it is empty (the generated `Adopted from <src>, lines a–b` is used) or equal, byte for
   byte, to a heading in the request's `outline`; `paths` must each match at least one
   `git ls-files` entry; `dirs` must be existing directories of the tree; any other key, `text`
   included, is rejected. After the transform, `check_lines` also runs in the other direction
   for a split — every non-ignorable destination line must be a source line, a generated line or
   pre-existing destination content — and a violation exits 4 (R9).
   *Proof:* `large-claude-md` and `large-agents-md` reach the same destinations from their canned
   proposals (parity, R19); a proposal with a gap, an overlap, a wrong sha, a disallowed dest and an
   over-budget keep each exit 4 naming the reason; so do a proposal with a `text` key, a `heading`
   not in the outline, a `paths` glob that matches no tracked file and a `dirs` entry that does not
   exist; a destination with a planted line that comes from no source fails R9 with exit 4; the
   fallback produces `PASS` on both checks;
   `junie-gemini` at the small size lists no `split?`; a hand-edited block goes through the split
   and ends with the shipped block; the resulting file is under `_budgets.skeleton`
   (`--check --budget` exits 0); `bash tests/test-shared-prompts-model-free.sh` is untouched by this
   step because no SKILL text changes yet.

8. **Cleanup (R13, R14's refusal).** `plan_cleanup` reads the latest `adopt.json` and refuses
   (exit 5, `ADOPT_REFUSED` on line 1) on any of (plan-review MEDIUM 15): a source sha mismatch;
   coexist; R12 not holding in the record; **a task in flight** (`current.json` present and stage
   not `done`) — WP7's `task_protected_patterns` is not armed outside a task, so this is the only
   thing between a running task and a deletion under `.claude/`/`.codex/`; **a dirty tree**
   (`clean_tree`, no exceptions — the Rollback section's "deleted on a clean tree" depends on it);
   and **either check failing when recomputed on the current tree**. Otherwise it lists exactly
   the `cleanup: true` sources as `delete?` items. `--apply
   --confirm-delete NAME` requires `human_present()` and writes `cleanup.{confirmed_by, at,
   unattended, tty}` before the first removal. **Removal is adopt's own** (plan-review HIGH 6), not
   the migration deletion path: that path copies originals without the 1 MiB / NUL limits and
   writes `migration.json`, which I10 says adopt leaves alone. `adopt.remove_confirmed(plan, rel)`
   copies through `keep_original_bounded` into the **same** `adopt-<date>/` directory as the
   record it cleans up (not today's), so a cleanup on a later day never creates an `adopt-*`
   directory without `adopt.json`. The docstring at `update.py:449` is already stale
   (`rules_update:751-755` removes files too); it is rewritten to name all three places that
   remove a file — `Migration.delete`, `rules_update`, `adopt.remove_confirmed` — each behind a
   human confirmation or a block the plugin owns.
   *Proof:* `tests/test-project-adopt.sh`: a cleanup dry run lists the right set; `--apply
   --confirm-delete` with stdin from `/dev/null` and no `AI_UNATTENDED` exits 5; with
   `AI_UNATTENDED=1` it deletes, `adopt.json.cleanup.unattended` is true, and `original/` still
   holds every file; a cleanup run with a faked later date (`ADOPT_TODAY=`, test-only) writes into
   the original `adopt-<date>/` and creates no new directory; no `migration.json` appears; a source
   changed after adopt makes cleanup refuse; so do a `current.json` at stage `plan`, an untracked
   file anywhere in the tree, and a stale reference planted after adopt (no-dangling recomputed
   fails) — each exit 5 before any removal, the tree sha unchanged; coexist cleanup prints
   `coexist keeps the foreign files`; `--adopt --check` afterwards says "up to date" and a
   reappearing `.cursorrules` says `regenerated`.

9. **The two SKILL flows, `/ai-status`, README, registration (I11, I12, C-parity).** Write
   `skills/project-update/SKILL.md` §8 with tier names only (BALANCED, once, in the session when
   `max_parallel_agents` is 1, else one subagent; Pro, Plus and `AI_UNATTENDED` use the fallback;
   point at the existing `--confirm-delete` rule at `SKILL.md:78-79` rather than restating it;
   hand the human the full command). Add the second line
   to `skills/ai-status/SKILL.md` step 7, and to `tests/test-ai-status-root.sh` two phrase checks
   (`--adopt --check` and `(deleted unattended)`) so the R16 proof actually bites — today that test
   is a phrase grep over the SKILL and would pass without the new line (plan-review HIGH 8). Add
   the README paragraph. Register the new test in
   `tests/run-all.sh`. Run pylint on 3.11–3.13 locally for `adopt.py` and `update.py`
   (`pylint $(git ls-files '*.py')`).
   *Proof:* `bash tests/test-shared-prompts-model-free.sh` (no model name in the new SKILL text),
   `bash tests/test-ai-status-root.sh`, then **the single full run** `bash tests/run-all.sh` and
   `pylint`; every failure fixed as one batch.

## Risks

**What could this break?**

- **WP1's `--confirm-delete` path** (step 2): the two existing confirmed deletions
  (`tests/test-project-update.sh:435` and `:482`) have no terminal in the agent's shell or in CI,
  so they would exit 5 after the gate. Mitigation: `AI_UNATTENDED=1` on each of those two commands
  in the same step (never `export`ed), and the new refusal case redirects stdin from `/dev/null`
  so a terminal run cannot pass by accident (spec risk 5).
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
  removal (both are in step 8's text and proof, not only here).
- **An agent can satisfy `human_present()` by prefixing `AI_UNATTENDED=1`** (plan-review
  MEDIUM 17, recorded, OQ2 not reopened). The path guard's check on this applies only while a task
  is in flight and reads the hook's own environment, so nothing backs it up for cleanup outside a
  task. Residual risk, accepted: the deletion is still on a clean tree with `original/` kept, so it
  is recoverable, and it is never silent — `adopt.json.cleanup.unattended: true` is written before
  the first removal, `report.md` prints `deleted unattended` on the cleanup line, and `/ai-status`
  shows `(deleted unattended)` (step 9) until the next adopt. Both SKILL texts already forbid the
  agent to pass `--confirm-delete`; §8 adds that setting `AI_UNATTENDED` to do so is the same act.
- **The warn-scope scan** on a large repository. Bounded by `git ls-files`, the NUL check, the
  20 MiB cap and one compiled alternation (spec risk 4).
- **`update.py` module size** (concern 13): C0302 is disabled with all `C` messages, so pylint
  will never flag it; new code goes to `adopt.py` by rule (see *Not touched*), not on a pylint signal.
- **Format assumptions** (concern 1) are the largest unknown and sit in step 1 on purpose: every
  later step is built against verified fixtures, and R4's `unmapped` fails loudly in the field.

**Riskiest step:** 7, the instruction-file transform. It cannot move earlier because it needs the
checks (5) and the apply gates (6); it is already split from the proposal *production* (a SKILL
concern, step 9) and from cleanup (8). The fallback path is proven before the proposal path inside
the step so a broken validator never blocks a project.

## Proof (tests)

| Req | Proof |
|---|---|
| R1 | `test-project-adopt.sh`: one `detect` line per tool with counts on every fixture; a fixture with no signature and fresh scaffolds for claude, codex, gemini and junie print `no foreign structure detected`, exit 0; a `GEMINI.md` without a managed block is detected |
| R2 | tree sha before and after the dry run, `--split-request` excepted, on every fixture |
| R3 | `--mode coexist` absent → `mode: migrate` in the dry-run header; `--mode` with another value → argparse exit 2 |
| R4 | `.kiro/hooks/x.json` and `packages/x/.cursor/rules/a.mdc` listed `unmapped`, exit 4; settled by `decisions.json` (also from an older `adopt-*` directory) → exit 0; a file under two tools' roots matched by one of them is not `unmapped` |
| R5 | five refusal cases, each exit 5 with `ADOPT_REFUSED` on stdout line 1 |
| R6 | `original/` present with mode; the >1 MiB and the NUL file listed `original-skipped`; the byte total in `adopt.json.original_bytes` |
| R7 | `--split-request` writes only `split-request.json`; the same proposal is reused on a second run (mtime unchanged); `--diff` output contains `---`/`+++` for each target |
| R8 | `large-*` fixtures list `split?`; `--apply` with neither proposal nor fallback → exit 4; fallback → one `.ai/policies/adopted/` file and one router row |
| R9 | a proposal with a `text` key, a `heading` not in the outline, a `paths` glob matching no tracked file or a missing `dirs` entry → exit 4; a planted destination line from no source → exit 4 |
| R10 | `check no-line-lost PASS` on all eight fixtures; a planted miss → `FAIL: 1 line(s) of <src>`, exit 4 |
| R11 | a planted hard-scope reference → FAIL, exit 4; a warn-scope reference → PASS with `1 warning(s)`; coexist with a missing linked path → FAIL |
| R12 | `adopt.json.checks.*.checked_at` set after apply; `--adopt --check` says `incomplete` when a check is forced to fail |
| R13 | cleanup lists only `cleanup: true` sources; stdin `/dev/null` → exit 5; `AI_UNATTENDED=1` → deleted with `unattended: true`; sha mismatch, task in flight, dirty tree, a check failing on recompute → exit 5 before any removal; later-day cleanup writes into the original `adopt-<date>/` |
| R14 | coexist: only `.ai/AGENTS.md` and `adopt.json` change; `--cleanup` → exit 5 with the message |
| R15 | second `--adopt` prints `0 automatic`, tree sha unchanged; an apply stopped after phase 1 and after phase 2 completes on re-run; a dirty path outside `planned_writes` still refuses |
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
