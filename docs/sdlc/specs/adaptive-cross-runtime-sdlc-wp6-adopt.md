# Spec: WP6 — `project-update --adopt`

Intent: `docs/sdlc/intent/adaptive-cross-runtime-sdlc.md` (work-package table, row 6)

<!-- Stage 2. Requirements and design derived from the intent, checked against project conventions. -->

Depends on **WP1** (`Plan`, `apply`, `apply_item`, `keep_original`, the `delete?` gate and
`--confirm-delete`, exit codes 0–3 — PR #15, #16) and **WP3** I11 (`render_instructions.py`,
`block_of`, `INSTRUCTION_FILE`, the router row form I3, `.ai/rules/<slug>.md` I4, `_budgets` —
PR #23). Reuses WP2's `human_present()` condition (`skills/ai-task/state.py:876-879`) for the
deletion gate. **WP4 and WP5 are untouched**: no state key, no policy JSON, no profile, no
migration, no guard rule.

Recommended tier: **T3**, as in the intent's table. The cleanup path is the T5-class deletion; it is
handled by an outside-the-agent gate (R13), not by re-tiering the task. Nothing raises the tier: no
auth, payments or customer data, no schema step, and the guard golden file stays byte-identical. The
one change to WP1 behaviour (a human check on `--confirm-delete`, OQ3) tightens an approval boundary
rather than crossing it. **No EXPERT trigger fires**: `adopt.json` is a report and `adopt-map.json`
is data, both revisable; nothing is irreversible before the human-gated cleanup, and the originals
are kept even then.

Outcome labels used below: **AD1** mapping table for foreign structures · **AD2** `migrate` default,
`coexist` opt-in, the result 100 % adapted · **AD3** splitting a large instruction file is the only
model step (BALANCED, once per project, shown as a diff, applied after approval) · **AD4**
no-line-lost check · **AD5** no-dangling-reference check · **AD6** deletion is a separate step, after
both checks, after human approval with who and when; originals copied to
`.ai/reports/adopt-<date>/original/`; the report · **D4, D5, D8** the intent's decisions ·
**C-dry, C-clean, C-app, C-idem, C-parity, C-fixture, C-plans** the intent's constraints (dry run
first, clean tree, no application code, idempotent, both runtimes at parity, a fixture per foreign
structure, works on all five subscriptions).

## Requirements

| # | Requirement (testable) | Satisfies |
|---|---|---|
| R1 | `update.py ROOT --adopt` detects every foreign structure named in `adopt-map.json` (I2) and prints one `detect` line per tool with its file count. A project with none prints `no foreign structure detected` and exits 0. | AD1 |
| R2 | The adopt dry run lists every source → destination with its transform and writes **nothing**: the tree is byte-identical before and after. Only `--apply`, `--split-request` and `--cleanup --apply` write. | C-dry |
| R3 | `--mode migrate` is the default. `--mode coexist` must be spelled out. | AD2, user decision 2026-09-19 |
| R4 | A detected file that no row matches is listed `unmapped`. The run exits **4** (`ADOPT_INCOMPLETE`), and nothing is applied until `decisions.json` (I6) settles it. A wrong format assumption therefore fails loudly and never loses a line silently. Foreign signatures found below the root (for example `packages/x/.cursor/rules/`) are `unmapped` too. | AD1, AD4 |
| R5 | `--adopt --apply` refuses (exit **5**, `ADOPT_REFUSED`, with the reason and the command to run first) when: the root is not a git work tree; `git status --porcelain --untracked-files=all` lists anything outside `.ai/reports/adopt-*/`, `.ai/state/` and `.ai/local/`; `.ai/state/current.json` holds a task whose `current_stage` is not `done` (the same arming rule as WP7's `task_protected_patterns`); the plain `--check` (`update.py:1155-1174`) would exit 1; or the project has no `.ai/` (run `/ai-init` first). | C-clean, "a task in flight is asked about first" |
| R6 | Every moved or rewritten source is first copied to `.ai/reports/adopt-<date>/original/<path>` via `keep_original` (`update.py:981`), with its mode kept. A file over 1 MiB, or binary (a NUL byte in the first 8 KiB), is not copied; it is listed `original-skipped (git has it)`. The report prints the total size copied. | AD6, WP1 concern 8 |
| R7 | Splitting a root instruction file is the only model step, and the tool never calls a model. `--split-request` writes `split-request.json` (I4); the session writes `split-proposal.json` (I5), which carries line ranges and never text. The tool validates coverage, the destination allow-list, `source_sha` and the keep budget, prints the unified diff on `--diff`, and applies it only with `--apply`. There is one proposal per `source_sha`: a matching proposal is reused and never re-requested. | AD3 |
| R8 | A root instruction file is a split candidate when, with its block re-rendered from the shipped template, the whole file exceeds `_budgets.skeleton` (2048 B, `instructions/runtimes.json`). The keep budget is `_budgets.skeleton` minus the shipped block's size. `--split fallback` (or `"split": "fallback"` in `decisions.json`) moves every line outside the block verbatim to `.ai/policies/adopted/<file-slug>.md` and adds one router row, with no model. `--apply` on a candidate with neither a proposal nor the fallback exits 4. | AD3, C-plans |
| R9 | No line is added. Every non-ignorable line of every file adopt writes comes from a source line, from a generated heading, frontmatter line or router row, or from content the destination already had. A violation exits 4. For a split this holds by construction, because the proposal carries no text. | AD3, D8 (a model cannot write instructions) |
| R10 | No-line-lost (I7): the set of normalised lines of every migrated source is a subset of the destination set plus `dropped.jsonl`. Every rewritten line (a frontmatter key, a demoted heading) is in `dropped.jsonl` with a reason. A failure prints `check no-line-lost FAIL: N line(s) of <src> — <report path>` and exits 4. | AD4, D4 |
| R11 | No-dangling-reference (I8): no old path is referenced anywhere in the hard scope, and a reference found elsewhere is only a warning. A failure exits 4. In coexist the check is inverted: every linked foreign path must exist. | AD5, AD2 "100 % adapted" |
| R12 | An adoption is `complete` only when R10 and R11 pass on the tree as written. `adopt.json.checks` records both with `checked_at`. Otherwise `--adopt --check` says `incomplete` and exits 1. | AD4, AD5 "not complete until both pass" |
| R13 | Cleanup is a separate invocation, `--adopt --cleanup`, offered in the report only when R12 holds. It lists exactly the sources whose row has `cleanup: true`. It **recomputes R10 and R11 at cleanup time** against the current tree, and refuses with exit 5 if any source's sha differs from `adopt.json`. It deletes only with `--apply --confirm-delete NAME` and only when `human_present()` holds. `confirmed_by`, `at`, `unattended` and `tty` are written to `adopt.json.cleanup` before the first file is removed. | AD6, D8, user decision 2026-09-19 |
| R14 | Coexist writes only router rows (I9) and `adopt.json` with `mode: coexist`. It moves nothing. `--cleanup` in coexist exits 5 with `coexist keeps the foreign files`. | AD2 |
| R15 | Idempotent: a second `--adopt` on an adopted, unchanged tree prints `0 automatic` and writes nothing. An interrupted `--apply` completes on the next run, with the same `check`/`expect` preconditions as `apply_item` (`update.py:1046-1085`). | C-idem, WP1 R5 |
| R16 | Regeneration (D5): a source whose sha differs from `adopt.json`, or one that reappears after cleanup, is reported as `regenerated` by `--adopt --check` (exit 1), as a `hint` line in the plain `project-update` dry run, and by `/ai-status`. Nothing changes by itself. | D5 |
| R17 | `CLAUDE.md`, `AGENTS.md`, `GEMINI.md` and `.junie/guidelines.md` are sources only for their content outside the managed block, and only when they are split candidates (R8). They remain destinations: the block is re-rendered from the shipped template. They are never listed for cleanup. | out of scope, item 3 (a stub for all four runtimes) |
| R18 | Application code is never a source or a destination. Sources come only from table rows and `decisions.json`; destinations only from the allow-list (I5, I6). Other tracked files are read only for R11's warnings. | C-app |
| R19 | Both runtimes: one script and one SKILL flow. The large-`AGENTS.md` fixture reaches the same result as the large-`CLAUDE.md` one. The SKILL text names tiers only; it is inside the scope of `tests/test-shared-prompts-model-free.sh`. | C-parity |
| R20 | Fixtures `tests/fixtures/adopt/{speckit,kiro,cursor,large-claude-md,large-agents-md,copilot,aidlc,junie-gemini}/` each carry a README naming the format assumption and its source, and a canned `split-proposal.json` where a split applies. `tests/test-project-adopt.sh` runs every fixture through a path with a space and one without. A row that matches nothing in its own fixture fails the test. | C-fixture, CI |
| R21 | `update.py --check --budget` exits 1 when any root instruction file is over budget: its block over `_budgets.project`, or the whole file over `_budgets.skeleton`. Plain `--check` is unchanged (`tests/test-project-update.sh:102`). | WP3 concern 6 |
| R22 | pylint is clean on 3.11–3.13: an explicit `check=` on every `subprocess.run`, context-managed handles and no unused parameters. Stdlib only, and `git` is invoked with list arguments only. | CI |
| R23 | Every source line matching the secret pattern of I7 prints a `hint` naming `file:line`, and nothing more. The value itself is never printed. | data protection (concern 8) |

## Design

### Components

| Component | Responsibility | Interface |
|---|---|---|
| `skills/project-update/adopt.py` (new; imported by `update.py` like `render_instructions`, `update.py:39`) | detection, planning onto the shared `Plan`, the transforms, the normaliser, both checks, proposal validation, the record, the cleanup plan | `detect(root, table)`, `plan_adopt(plan, detected, opts)`, `normalise(line)`, `check_lines(sources, dests, dropped)`, `check_refs(root, old_paths, hard, warn)`, `load_proposal(path, source_bytes)`, `record(plan, result)`, `plan_cleanup(root, record)` |
| `skills/project-update/adopt-map.json` (new, data) | the mapping table (I2) | loaded once and validated; an unknown transform or a bad glob exits 2, like a bad migration registry |
| `update.py` (extended) | CLI flags, exits 4 and 5, `human_present()`, `clean_tree()`, the D5 hint in the plain dry run, `--check --budget`, the human check on `--confirm-delete` | `main()` |
| `Plan`, `apply`, `keep_original`, `report` (`update.py:495, 1025, 981, 1088`) | unchanged writers. Adopt items carry `migration=None` and a new `tool` field, so that `report` can tag `[speckit]`. | as today |
| `.ai/reports/adopt-<date>/` | the record: `adopt.json`, `report.md`, `dropped.jsonl`, `split-request.json`, `split-proposal.json`, `decisions.json`, `original/` | I4–I6, I10 |
| `skills/project-update/SKILL.md` §8 (new) | the flow the session follows | I12 |
| `skills/ai-status/SKILL.md` step 7 | a second line, from `--adopt --check` | I11 |
| `tests/test-project-adopt.sh`, `tests/fixtures/adopt/**` | R20 | — |

### Data flow

```
--adopt            detect(table) ─► plan_adopt ─► [proposal? validate] ─► items on Plan ─► checks on plan.final ─► report
--split-request    detect ─► split-request.json (outline, allow-list, keep budget)   ─► the session writes split-proposal.json
--diff             as the dry run, then difflib.unified_diff(before, plan.final) per target
--apply            R5 gates ─► apply(plan) [keep_original ─► write] ─► checks on DISK ─► adopt.json + report.md + dropped.jsonl
--cleanup          latest adopt.json ─► sha match ─► both checks recomputed on disk ─► list delete? items
--cleanup --apply --confirm-delete NAME     human_present() ─► adopt.json.cleanup{who, when} ─► remove each path
```

**Ordering with WP1 R4.** Adopt runs only once the project is current (R5), so the migrations,
`.ai/VERSION` and the three-way walk have already run, in an earlier invocation. An
`--adopt --apply` run contains only adopt items plus `rules_update(plan, runtimes)`
(`update.py:697`), so nested rule blocks for new `.ai/rules/` files render in the same run. Adopt
never reads or writes `.ai/VERSION`, so WP1 R5a is untouched. Router rows are ordinary edits to
`.ai/AGENTS.md`, which the next three-way walk keeps like any project edit.

**The instruction-file transform.** The source is the file minus the managed block when the block is
the shipped one; when the block was edited (WP3 R13's conflict case), the source is the file minus
only the markers, so the human's edits inside the block go through the split too. The result is the
shipped block from `INSTRUCTION_FILE[rt][1]` (`update.py:74-80`) plus the kept lines, within the
keep budget (R8). This is the path out that WP3 concern 5 left for a fat, hand-edited block
(concern 3).

**The model step (AD3).** `update.py` stays deterministic. It writes a request with no text, and the
session produces the proposal at the BALANCED tier: in the session itself when the profile allows one
agent (`state.py profile --field budgets.fan_out.max_parallel_agents` prints 1), otherwise one BALANCED subagent returns the JSON. The
proposal is a list of line ranges with destinations, so the model routes lines and cannot write any.
The tool materialises the content from the source, checks the ranges cover every line, and shows the
diff. Pro, Plus and headless runs default to the deterministic fallback (R8).

### Alternatives considered and rejected

1. **Adopt as migration `0006_adopt.py`.** Migrations run on every project, once per schema, and hold
   `.ai/VERSION` on a conflict or a `delete?` (`update.py:846-852`). Adoption is opt-in, per tool,
   repeatable after regeneration, and has a model step. Tying it to VERSION would block every later
   migration on an unfinished adoption.
2. **A standalone `adopt.py` with its own CLI.** It would duplicate `Plan`, `apply`,
   `keep_original` and `report`, and need a second SKILL flow per runtime. That is a parity risk for
   no gain.
3. **A proposal that carries text** (the model writes destination files, or JSON with bodies). This
   opens instruction smuggling, and no-line-lost would have to trust the model's copy. Line ranges
   make the model unable to add or alter a line, so R9 holds structurally.
4. **The mapping table in Python.** Correcting a wrong format assumption would need a code change
   under pylint CI. JSON lets the plan fix patterns and lets the test enumerate rows. The transforms
   stay code, as a fixed enum.
5. **Gitignoring `original/`.** A clone would lose the record the deletion was approved against. The
   size is capped instead (R6).
6. **A journal event `adoption_applied`.** It has no consumer beyond `/ai-status`, which reads
   `adopt.json`, and WP2's rule forbids growing the vocabulary without one. Adopt also refuses to run
   inside a task (R5), so there is no `<task-id>` to journal under.
7. **Multiset no-line-lost.** It is stricter but noisy on duplicated boilerplate. The intent says
   "present", so a set suffices. Duplicates are counted in the report as information.
8. **Refusing any existing `current.json`.** A task at stage `done` that was never archived would
   block adoption for good. Stage `done` counts as no task, as in WP7.

### Risks

1. **The foreign formats are assumptions** (concern 1). Mitigation: R4's `unmapped` is loud; plan step
   1 replaces each fixture with a real sample and records its source and date in the README; a row
   that matches nothing in its fixture fails the test.
2. **`dirs:` derived from a glob can put a rule in the wrong directory.** Mitigation: the derived
   `dirs:` is printed on the plan line, rules load on demand, and `paths:` keeps the original glob.
3. **Router rows conflict with a later template change.** Mitigation: rows go after the table's last
   row, the smallest merge hunk, and the walk's `conflict` path applies as for any edit.
4. **The warn-scope scan is slow on a large repository.** Mitigation: `git ls-files` only, text files
   only (NUL check), a 20 MiB per-file cap, and one compiled alternation of all old paths in one pass.
5. **The `--confirm-delete` human check breaks `tests/test-project-update.sh:432-443`.** Mitigation:
   that section sets `AI_UNATTENDED=1`, and a new case proves the refusal with stdin from
   `/dev/null`. Without the redirect, a local run from a terminal would pass the TTY check by
   accident.
6. **The fallback split fattens `.ai/policies/adopted/`** with a whole file. Mitigation: one router
   row, and the report says so; it is still better than an always-loaded 6 KB file, and a later
   `--adopt` after the human trims it re-adopts nothing (the sha is recorded).
7. **A foreign file regenerated after cleanup** (the other tool ran again). Mitigation: R16 is
   sha-based and independent of the cleanup state.
8. **Two adoptions on one day with a changed proposal.** Mitigation: proposals are keyed by
   `source_sha`, and `adopt.json` merges by source path and never records a source twice.

## Interfaces

### I1 CLI and exit codes (`update.py`)

```
update.py ROOT --adopt [--mode migrate|coexist] [--tool speckit,cursor,…]   # dry run, writes nothing
update.py ROOT --adopt --check                                                # one line, exit 0/1
update.py ROOT --adopt --split-request                                        # writes split-request.json only
update.py ROOT --adopt --diff                                                 # unified diff of the dry run
update.py ROOT --adopt --apply [--split proposal|fallback]                    # default: the proposal if present, else exit 4
update.py ROOT --adopt --cleanup                                              # dry: recompute the checks, list delete?
update.py ROOT --adopt --cleanup --apply --confirm-delete NAME                # human_present() required
update.py ROOT --check --budget                                               # R21
```

Exit codes 0, 1, 2 and 3 keep today's meaning (`update.py:1143-1184`). New: **4
`ADOPT_INCOMPLETE`** (unmapped, a missing or invalid proposal, a failed check, a `conflict` on a
destination) and **5 `ADOPT_REFUSED`** (not git, a dirty tree, a task in flight, the project behind
the plugin, no `.ai/`, cleanup in coexist, `--confirm-delete` without a human). The token is on the
first line of stdout, as `state.py` does with its own codes.

`human_present()` in `update.py` is `os.isatty(0) or bool(os.environ.get("AI_UNATTENDED"))`,
duplicated from `state.py:876-879` with a comment rather than imported across skills. It now guards
WP1's `--confirm-delete` too (OQ3). `clean_tree(root)` runs
`subprocess.run(["git", "-C", root, "status", "--porcelain", "--untracked-files=all"], check=False,
capture_output=True, text=True)`; a non-zero exit code means "not a git work tree".

### I2 `adopt-map.json` — the initial table

Every `source` below is an **assumption until plan step 1 verifies it against a real sample**
(concern 1).

```json
{"version": 1,
 "tools": {
  "speckit": {"signature": [".specify/"],
              "roots": [".specify/", "specs/", "memory/constitution.md",
                        ".claude/commands/speckit*", ".github/prompts/speckit*", ".codex/prompts/speckit*",
                        ".gemini/commands/speckit*", ".cursor/commands/speckit*"]},
  "kiro":    {"signature": [".kiro/"], "roots": [".kiro/"]},
  "aidlc":   {"signature": ["aidlc-docs/"], "roots": ["aidlc-docs/", ".aidlc/", ".amazonq/rules/"]},
  "cursor":  {"signature": [".cursorrules", ".cursor/rules/"], "roots": [".cursorrules", ".cursor/"]},
  "copilot": {"signature": [".github/copilot-instructions.md", ".github/instructions/"],
              "roots": [".github/copilot-instructions.md", ".github/instructions/"]},
  "junie":   {"signature": [".junie/guidelines.md"], "roots": []},
  "gemini":  {"signature": ["GEMINI.md"], "roots": []},
  "claude":  {"signature": ["CLAUDE.md"], "roots": []},
  "codex":   {"signature": ["AGENTS.md"], "roots": []}
 },
 "rows": [
  {"tool":"speckit","source":".specify/memory/constitution.md","dest":"docs/sdlc/constitution.md","transform":"append-section","cleanup":true},
  {"tool":"speckit","source":"memory/constitution.md","dest":"docs/sdlc/constitution.md","transform":"append-section","cleanup":true},
  {"tool":"speckit","source":"specs/*/spec.md","dest":"docs/sdlc/specs/{dir}.md","transform":"copy","cleanup":true,"router":"an adopted Spec Kit spec"},
  {"tool":"speckit","source":"specs/*/plan.md","dest":"docs/sdlc/plans/{dir}.md","transform":"copy","cleanup":true,"router":"an adopted Spec Kit plan"},
  {"tool":"speckit","source":"specs/*/tasks.md","dest":"docs/sdlc/plans/{dir}-tasks.md","transform":"copy","cleanup":true},
  {"tool":"speckit","source":"specs/*/*.md","dest":"docs/sdlc/specs/{dir}-{stem}.md","transform":"copy","cleanup":true},
  {"tool":"speckit","source":".specify/templates/**","transform":"drop","why":"Spec Kit templates; docs/sdlc/*/TEMPLATE.md replace them","cleanup":true},
  {"tool":"speckit","source":".specify/scripts/**","transform":"drop","why":"Spec Kit tool machinery; the skills replace it","cleanup":true},
  {"tool":"speckit","source":"*/**/speckit*","transform":"drop","why":"Spec Kit agent commands; they call .specify/ and the sdlc skills replace them","cleanup":true},
  {"tool":"kiro","source":".kiro/steering/*.md","dest":"auto","transform":"rule","cleanup":true,"frontmatter":{"paths":"fileMatchPattern","always":"inclusion=always"}},
  {"tool":"kiro","source":".kiro/specs/*/requirements.md","dest":"docs/sdlc/intent/{dir}.md","transform":"copy","cleanup":true,"router":"an adopted Kiro requirement"},
  {"tool":"kiro","source":".kiro/specs/*/design.md","dest":"docs/sdlc/specs/{dir}.md","transform":"copy","cleanup":true},
  {"tool":"kiro","source":".kiro/specs/*/tasks.md","dest":"docs/sdlc/plans/{dir}.md","transform":"copy","cleanup":true},
  {"tool":"kiro","source":".kiro/settings/**","transform":"ignore","why":"Kiro tool configuration"},
  {"tool":"aidlc","source":"aidlc-docs/inception/**/*.md","dest":"docs/sdlc/intent/aidlc-{rel}.md","transform":"copy","cleanup":true},
  {"tool":"aidlc","source":"aidlc-docs/construction/**/*.md","dest":"docs/sdlc/plans/aidlc-{rel}.md","transform":"copy","cleanup":true},
  {"tool":"aidlc","source":".aidlc/rules/*.md","dest":".ai/policies/adopted/aidlc-{stem}.md","transform":"copy","cleanup":true,"router":"a rule adopted from AI-DLC"},
  {"tool":"aidlc","source":".amazonq/rules/**/*.md","dest":".ai/policies/adopted/aidlc-{stem}.md","transform":"copy","cleanup":true,"router":"a rule adopted from AI-DLC"},
  {"tool":"cursor","source":".cursorrules","dest":".ai/policies/adopted/cursorrules.md","transform":"copy","cleanup":true,"router":"anything, first (rules adopted from Cursor)"},
  {"tool":"cursor","source":".cursor/rules/**/*.mdc","dest":"auto","transform":"rule","cleanup":true,"frontmatter":{"paths":"globs","always":"alwaysApply=true","title":"description"}},
  {"tool":"cursor","source":".cursor/*","transform":"ignore","why":"Cursor tool configuration (mcp.json and the like)"},
  {"tool":"copilot","source":".github/copilot-instructions.md","dest":".ai/policies/adopted/copilot-instructions.md","transform":"copy","cleanup":true,"router":"anything, first (rules adopted from Copilot)"},
  {"tool":"copilot","source":".github/instructions/*.instructions.md","dest":"auto","transform":"rule","cleanup":true,"frontmatter":{"paths":"applyTo"}},
  {"tool":"junie","source":".junie/guidelines.md","transform":"instruction-file","cleanup":false},
  {"tool":"gemini","source":"GEMINI.md","transform":"instruction-file","cleanup":false},
  {"tool":"claude","source":"CLAUDE.md","transform":"instruction-file","cleanup":false},
  {"tool":"codex","source":"AGENTS.md","transform":"instruction-file","cleanup":false}
 ]}
```

Matching: rows are tried in order and the first match wins. `*` does not cross `/`; `**` does.
`{dir}` is the source's parent directory name, `{stem}` the file stem, and `{rel}` the path under the
root with `/` replaced by `-`. A file under a tool's `roots` that no row matches is `unmapped` (R4).
A tool is detected only by its `signature`, so a plain `specs/` without `.specify/` is never a
source. An `ignore` row never covers a path under a rule-bearing directory: `.cursor/*` leaves
`.cursor/rules/sub/` to the rule row, or to `unmapped`. `.ai/` is skipped by `detect` entirely.
`.github/` is never a root, only the exact paths above.

`dest: "auto"` for `rule` means `.ai/rules/<slug>.md` when at least one glob has a literal leading
directory (which becomes `dirs:`), and otherwise `.ai/policies/adopted/<tool>-<slug>.md` with
`paths:` kept in the frontmatter and a router row.

Transforms (a fixed enum in `adopt.py`):
- `copy`: the destination is absent or identical, otherwise `conflict`.
- `append-section`: appends `\n## Adopted from <src>\n\n<body>`, idempotent by heading. It prints a
  hint when the constitution passes 15 principles (WP3 R10).
- `rule`: rewrites the frontmatter, keeps the body verbatim, and logs the rewritten keys to
  `dropped.jsonl`.
- `instruction-file`: see the Design section and R7/R8.
- `drop`: writes nothing and logs every file with the row's `why`.
- `ignore`: not a source, never deleted, listed `ignored`.

### I3 Report lines (the `%-9s %-*s  %s` layout of `update.py:1112`)

```
project-update: /p (adopt dry run, nothing written; --apply to write)
  detect    speckit                        .specify/ (5), specs/ (6), memory/constitution.md, .claude/commands/ (8)
  adopt     specs/001-auth/spec.md -> docs/sdlc/specs/001-auth.md   [speckit] copy
  adopt     .cursor/rules/pay.mdc -> .ai/rules/pay.md               [cursor] rule: globs -> paths:, dirs: [src/Payment]
  adopt     memory/constitution.md -> docs/sdlc/constitution.md     [speckit] append-section (hint: 41 lines, at most 15)
  router    .ai/AGENTS.md                  +2 row(s)
  split?    CLAUDE.md                      6412 B outside the block, keep budget 939 B; needs --adopt --split-request or --split fallback
  dropped   .specify/scripts/ (4 files)    [speckit] Spec Kit tool machinery; the skills replace it
  ignored   .cursor/mcp.json               [cursor] Cursor tool configuration
  unmapped  .kiro/hooks/x.json             [kiro] no mapping row — settle it in .ai/reports/adopt-2026-09-22/decisions.json
  hint      .cursorrules:14                looks like a secret (value not shown)
  check     no-line-lost                   PASS (312 lines, 9 rewritten -> dropped.jsonl) | FAIL: 3 line(s) of .cursorrules
  check     no-dangling                    PASS (2 warning(s) outside the new structure) | FAIL: .ai/policies/coding.md:12 -> .cursorrules
  cleanup?  10 file(s) offered after both checks pass: --adopt --cleanup
14 automatic, 0 conflict(s), 1 split awaiting a proposal, 1 unmapped
```

### I4 `split-request.json` (written by `--split-request`)

```json
{"version":1,"source":"CLAUDE.md","source_sha":"sha256:…","lines":188,"block":[3,41],
 "outline":[{"line":43,"heading":"## Conventions"},{"line":97,"heading":"## Payments"}],
 "keep_budget_bytes":939,
 "allowed_dest":[".ai/policies/adopted/<slug>.md",".ai/rules/<slug>.md",".ai/project/<slug>.md","docs/sdlc/constitution.md"],
 "proposal":".ai/reports/adopt-2026-09-22/split-proposal.json"}
```

The request carries no text. The session reads the source with its own read tool, which gives the
line numbers.

### I5 `split-proposal.json` (written by the session, validated by the tool)

```json
{"version":1,"source":"CLAUDE.md","source_sha":"sha256:…",
 "keep":[[1,2],[42,48]],
 "moves":[{"lines":[49,96],"dest":".ai/policies/adopted/conventions.md","heading":"Conventions adopted from CLAUDE.md"},
          {"lines":[97,140],"dest":".ai/rules/payment.md","dirs":["src/Payment"],"paths":["src/Payment/**"]},
          {"lines":[141,180],"dest":".ai/project/overview.md"}],
 "dropped":[{"lines":[181,188],"why":"repeats rule 4 of the managed block"}]}
```

Validation, where any failure exits 4 with its reason:
- `source_sha` matches the file on disk.
- Ranges are 1-based, inclusive and non-overlapping, and together they cover every line outside the
  block (outside the markers only, when the block was edited).
- Every `dest` matches `allowed_dest`, and an `.ai/rules/` destination carries `dirs`.
- Every `dropped.why` is non-empty.
- The kept bytes fit in `keep_budget_bytes`.

`.ai/project/overview.md` already exists in the scaffold; moved lines are appended there under a
generated heading.

### I6 `decisions.json` (the human's decisions, written by the session after a "yes" in chat)

```json
{"version":1,"split":"proposal",
 "unmapped":{".kiro/hooks/x.json":{"action":"drop","why":"Kiro agent hook; no equivalent here"},
             "specs/001-auth/contracts/api.yaml":{"action":"copy","dest":"docs/sdlc/specs/001-auth-contracts/api.yaml"}}}
```

`split` is `proposal` or `fallback`. A `copy` destination obeys the I5 allow-list plus
`docs/sdlc/{intent,specs,plans}/`.

### I7 No-line-lost and the secret hint

`normalise(line)`:
- `strip()` the line.
- Return `None` (ignorable) when the line is empty, a bare heading (`^#{1,6}\s`), or has no
  alphanumeric character (`---`, code fences, `|---|`). This last case is concern 2.
- Otherwise strip one list marker (`^([-*+]|\d+[.)])\s+`, then `^\[[ xX]\]\s+`), collapse whitespace
  to one space, and `casefold()`.

The **source set** is the union over every source whose transform is `copy`, `append-section`,
`rule`, `instruction-file` or `drop`. The **destination set** is the normalised lines of every file
adopt writes, the whole file rather than the delta: `plan.final` in the dry run, and the disk after
`--apply` and at cleanup. The check is `source − destination − dropped == ∅`.

`dropped.jsonl` holds one object per line:

```json
{"source":".cursor/rules/pay.mdc","line":3,"text":"globs: src/Payment/**","reason":"rewritten: globs -> paths:","by":"transform:rule"}
{"source":".specify/scripts/bash/common.sh","line":"*","sha":"sha256:…","reason":"Spec Kit tool machinery; the skills replace it","by":"transform:drop"}
```

`by` is `transform:<name>`, `proposal` or `decision`. A whole-file `drop` is one record with
`"line":"*"` and the file's sha, which pins every line of it. A router row is generated, not a
source line. A frontmatter line that became `paths:` is logged by the transform. The report prints
the counts and the first 20 misses with `file:line`.

The **secret hint** (R23) matches
`(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*\S{8,}` and `-----BEGIN [A-Z ]*PRIVATE KEY`.
It prints `file:line` only.

### I8 No-dangling-reference

**Old paths** are every source whose row has `cleanup: true`, plus every tool `roots` entry. The
reference pattern for a path `P` (and for `./P`) is
``(^|[\s`"'(@=:,])\.?/?P(?=$|[\s`"')>,:;])``. It covers backticks, `](P)` links, `@P` imports and
bare mentions. A directory root matches every path below it.

**Hard scope (FAIL):**
- `.ai/**`, minus `.ai/reports/adopt-*/`, `.ai/state/` and `.ai/local/`;
- `docs/sdlc/**`;
- the four `INSTRUCTION_FILE` paths (`update.py:74-80`) and nested `<dir>/CLAUDE.md|AGENTS.md` files
  that carry a rule block;
- the runtime directories an agent executes from: `.claude/**`, `.codex/**`, `.gemini/**`,
  `.junie/**`, `.github/prompts/**` and `.github/instructions/**`.

A command there that still reads the old structure is a dependency, not a mention.

**Warn scope:** every other `git ls-files` path, text files only (NUL check), minus the sources and
roots themselves.

In **coexist**, the old paths are the linked foreign files, and the check is "every linked path
exists". The output is `check no-dangling FAIL: <file>:<line> -> <old path>`.

### I9 Router rows (`.ai/AGENTS.md`, the form of WP3 I3)

A row is `| <row.router, or "an adopted <tool> <kind>"> | <dest>, … |`. Destinations under `.ai/` are
written relative to it (`policies/adopted/cursorrules.md`), others relative to the repository
(`docs/sdlc/specs/`). There is one row per (tool, destination directory). Rows are appended after
the last `| … | … |` line of the `## Doing X → read Y` table, and are idempotent by their exact
text. In coexist, a row points at the foreign path and ends with
`(kept in place; its globs are not applied by this runtime)`.

### I10 `adopt.json` (in `.ai/reports/adopt-<YYYY-MM-DD>/`)

Runs on the same day merge into one record. The latest record is the greatest directory name.

```json
{"version":1,"mode":"migrate","adopted_at":"<UTC>","plugin_schema":5,
 "tools":{"speckit":{"files":20},"cursor":{"files":4}},
 "sources":[{"path":"specs/001-auth/spec.md","sha":"sha256:…","tool":"speckit","transform":"copy",
             "dest":"docs/sdlc/specs/001-auth.md","dest_sha":"sha256:…","original":"original/specs/001-auth/spec.md","cleanup":true}],
 "dropped":9,"ignored":[".cursor/mcp.json"],"unmapped":[],"original_bytes":48213,
 "split":{"CLAUDE.md":{"by":"proposal","proposal_sha":"sha256:…","kept_bytes":880,"moves":3,"dropped":1}},
 "checks":{"no_line_lost":{"status":"pass","checked_at":"<UTC>","lines":312,"missing":0},
           "no_dangling":{"status":"pass","checked_at":"<UTC>","hard":0,"warn":2}},
 "cleanup":{"offered":true,"confirmed_by":null,"at":null,"unattended":null,"tty":null,"deleted":[]}}
```

`report.md` is the human rendering, in the intent's order: what was detected, where each piece went,
what was dropped and why, what was ignored or left unmapped, the checks, and what is proposed for
deletion. WP1's `migration.json` is untouched; it has different fields, and adopt is not a schema
step.

### I11 `/ai-status`, step 7 (plugin version), a second line

`python3 "$AI_HOME/skills/project-update/update.py" "$PWD" --adopt --check` prints exactly one of:

| Line | Exit |
|---|---|
| `no foreign structure detected` | 0 |
| `adopted <date>: speckit, cursor — up to date; 10 file(s) await cleanup` | 0 |
| `foreign structure detected: speckit (20 files), cursor (4) — run /project-update --adopt` | 1 |
| `foreign files regenerated since the adopt of <date>: .cursorrules — run /project-update --adopt` | 1 |
| `adoption of <date> incomplete: no-line-lost FAIL — run /project-update --adopt` | 1 |

`/ai-status` adds `(deleted unattended)` when `cleanup.unattended` is true. The plain dry run adds
the detection and regeneration text as a `hint` line (D5). Plain `--check` output is unchanged
(OQ10).

### I12 `skills/project-update/SKILL.md` §8, the flow (tiers only)

1. **Preconditions.** `state.py get --quiet` shows no task short of `done`, `git status` is clean,
   and `$UPDATE --check` exits 0. Otherwise stop and say which one failed.
2. Run `$UPDATE --adopt` and show its output as is.
3. For each `unmapped` file, ask the human and write `decisions.json`.
4. For a `split?` line:
   - On a `pro` or `plus` plan (`state.py profile --field plan`), or under `AI_UNATTENDED`, use
     `--split fallback`.
   - Otherwise run `--adopt --split-request` and produce the proposal **once**, at the BALANCED tier:
     in the session when `state.py profile --field budgets.fan_out.max_parallel_agents` prints 1, else one BALANCED subagent that returns
     the JSON. Write the JSON, never text.
5. Run `$UPDATE --adopt --diff` and ask "apply?".
6. Run `$UPDATE --adopt --apply` and show the two `check` lines. On a FAIL, read `dropped.jsonl`,
   amend the proposal or the decisions, and run it again. Never edit a destination by hand to make a
   check pass.
7. Point at `report.md`. Suggest `git add` of the new structure and the report directory. Do not
   commit.
8. **Cleanup.** Never pass `--confirm-delete` yourself. Give the human
   `python3 <abs>/update.py <abs> --adopt --cleanup --apply --confirm-delete "<your name>"` with the
   paths filled in, to run in their own terminal. Offer `--mode coexist` only when the team still
   uses the other tool.

## Policy conformance

This repository has no project `CLAUDE.md` or `AGENTS.md`, no `.claude/` or `.codex/` skills or
agents, and no ADRs under `docs/sdlc/adr/`. The binding sources are the global instructions, the
intent's constraints and decisions, the user decision of 2026-09-19 (memory `adopt-migrate-default`)
and the settled decisions of the WP1–WP5 specs. No plugin skill (Symfony UX, PHP) matches this
stack.

| Policy | How the design honours it |
|---|---|
| Global — deterministic tools first; a new check replaces a model step | Detection, planning, both checks, proposal validation and cleanup are stdlib Python and `git`. The one model step routes lines and writes none (R7, R9). |
| Global — tier names only in shared prompts | SKILL §8 says BALANCED; R19 keeps it in the scope of the model-free grep. |
| Global — five or more parallel agents never on the STRONG tier; implementation in the main session | At most one BALANCED subagent, once per project; everything else runs in the session. |
| Global — no agent commits, merges or deploys | Adopt never commits (SKILL §8 step 7); cleanup deletes files but commits nothing. |
| Global and memory — plugin-owned files change only through the skills | The only writer is `update.py`, invoked by `/project-update`. Router rows and new rules are written by it, never by hand (SKILL §8 step 6). |
| Memory `adopt-migrate-default` — migrate by default; deletion a separate step after approval; the new structure 100 % adapted and verified first | R3, R13, R12; the hard scope of R11 includes the runtime directories, so a command that still reads the old tree fails the check. |
| Intent AD3 — the only model step, BALANCED, once, diff, approval | R7 and R8 (one proposal per `source_sha`), `--diff` before `--apply`, in-chat approval (OQ1). |
| Intent AD4/AD5/AD6 and D4 | R10 and I7 (the normaliser follows D4, plus concern 2), R11 and I8, R13, and the report in the intent's order (I10). |
| Intent D5 — regenerated foreign files: detect, warn, offer, nothing by itself | R16 and I11. |
| Intent D8 — the agent never approves | Cleanup requires `human_present()` (R13); SKILL §8 step 8 forbids passing `--confirm-delete`; WP1's flag gets the same check (OQ3). |
| Intent C-dry, C-idem, C-app, C-clean | R2, R15, R18, R5. |
| Intent C-parity, C-fixture, C-plans | R19, R20 (eight fixtures), R8 (fallback on Pro, Plus and headless runs). |
| `project-update` guarantees (`skills/project-update/SKILL.md`) | Dry run first; `copy` never overwrites a differing destination (`conflict`); a task in flight refuses adopt (R5); the plain walk and `--check` are unchanged. |
| WP1 R4, R5, R5a, R7 | Adopt runs after the walk, never touches `.ai/VERSION`, reuses `keep_original` and `apply_item`, and its deletion gate is `--confirm-delete` extended with the human check. |
| WP2 — the vocabulary grows only with a consumer | No new event type (alternative 6). |
| WP3 I3, I4, I11, R13, concerns 5 and 6 | Router rows in I3's form, `.ai/rules/` in I4's form, `block_of` and `INSTRUCTION_FILE` reused, R21 for `--check --budget`, and the instruction-file transform as the path out for a fat edited block (concern 3). |
| WP7 — foreign instruction files are task-protected only mid-task | Adopt refuses mid-task (R5), so the guard and adopt never disagree. The guard files are unchanged. |
| Intent — guard rules unchanged, characterization byte-identical | No hook or guard file changes; `tests/test-guard-characterization.sh` is untouched. |
| Data protection | No personal data is created. Secrets already in tracked foreign files are pointed at by R23 and never printed. `original/` duplicates only what git already holds, because the tree is clean. No security review at T3. |
| Memory — pylint clean on 3.11–3.13; tests through a path with a space and one without; run tests once to the end | R22 and R20; one `tests/run-all.sh` at the end of the task. |

## Flagged concerns

Reviewed with the user on 2026-09-22: every concern below is accepted as stated, and OQ1–OQ11
were answered with the recommendation ("accept all"). Concern 2 is settled by OQ11, concern 4
by OQ1, concern 5 by OQ2, concern 6 by OQ3 and concern 7 by OQ4.

1. **Every foreign-format fact is an assumption.** This covers Spec Kit (`.specify/` against
   `memory/`, and its agent-command locations), Kiro (`inclusion`, `fileMatchPattern`, `.kiro/hooks`),
   the AI-DLC layout (`aidlc-docs/`, `.amazonq/rules/`), Cursor `.mdc` keys and nested
   `.cursor/rules/`, and Copilot `applyTo`. None of it was checked against a real repository in this
   stage. The plan's first step must verify each one against a public sample and record where it
   came from. The design already fails loudly on a wrong assumption (`unmapped`, R4) and never loses
   a line silently.
2. **Decision 4 against the normaliser.** D4 ignores blank lines and bare headings. I7 also ignores
   lines with no alphanumeric character (`---`, code fences, table rules); without that, every
   frontmatter fence and code fence would need a `dropped` entry. This goes one step beyond the
   decision's wording, so it needs the user's nod (OQ11). The alternative is to log them as
   `rewritten: punctuation`.
3. **WP3 R13 ("an edited managed block is never overwritten") against the instruction-file
   transform.** Adopt replaces an edited block with the shipped one after moving the human's lines
   out. It does so only under a proposal or fallback the human approved, and with the original kept.
   This is the path out that WP3 concern 5 asked for, but it contradicts R13's "never" literally.
   This spec amends WP3 R13 to read "never, except by an approved `--adopt`". The plan adds that
   sentence to the WP3 spec.
4. **Split approval is in chat, not outside the agent.** Nothing is deleted and the original is kept,
   so the design treats it like today's policy confirmation in `/project-update`, not as a D8 gate.
   If the user wants D8 here, `--adopt --apply` needs `human_present()` too, which makes every
   adoption a terminal action (OQ1).
5. **`AI_UNATTENDED` on a T5-class deletion.** Parity with WP2 and WP4 says to reuse
   `human_present()`. The intent's "who and when" is then a name supplied by the launcher, recorded
   with `unattended: true` for good and shown by `/ai-status` (OQ2).
6. **WP1's `--confirm-delete` has no human check today** (`update.py:1134-1138`). Adding one is a WP1
   behaviour change carried in WP6's row: the same two lines, plus one test amendment with stdin from
   `/dev/null` (OQ3).
7. **The originals copy against WP1 concern 8.** It is committed on purpose (alternative 5) and
   capped at 1 MiB per file. A Spec Kit project with many specs carries two copies of each spec until
   cleanup, and one after it. If the user prefers to rely on git history, `original/` becomes
   gitignored and the intent's sentence must be amended (OQ4).
8. **Secrets in foreign sources.** `.cursorrules` or steering files can embed tokens, and
   `original/` duplicates them. The tree is clean, so the file is already in git and nothing new is
   exposed. R23 points at the line without printing it, and `ai-git-guard`'s staged-secret rule
   remains the last line of defence.
9. **A model proposal cannot smuggle text, but it can misroute a line**, for example a payment rule
   into `.ai/project/overview.md`. No deterministic check can judge placement. The mitigation is the
   diff shown before apply and the human's "yes".
10. **Coexist does not apply Cursor, Kiro or Copilot globs** under Claude Code or Codex. The linked
    rules are readable but not applied by path, and the router row says so (I9).
11. **Foreign tools install commands into the runtime directories** (`.claude/commands/speckit*`,
    `.github/prompts/`, and others). Left behind, they would read a deleted `.specify/` after cleanup.
    The table makes them `drop` sources with `cleanup: true`, and I8 puts the runtime directories in
    the hard scope. Deleting under `.claude/` or `.codex/` happens only outside a task, where
    WP7's rule is not armed, and only behind the human gate.
12. **Nested foreign structures in a monorepo** (`packages/x/.cursor/rules/`) are detected and listed
    `unmapped` (R4), but no row maps them in this package. The human settles each one in
    `decisions.json`, or a later row adds them.
13. **`update.py` grows past 1 200 lines** even with `adopt.py` separate (flags, gates, the hint, the
    budget check). That is acceptable. The plan may move `human_present` and `clean_tree` into
    `adopt.py` if pylint's module-size warning fires.

## Open questions

| # | Question | Recommendation | Owner | Status |
|---|---|---|---|---|
| OQ1 | Split approval: a "yes" in chat, like policy confirmation, or D8 outside the agent? | In chat: nothing is deleted, the originals are kept and the diff is shown. | user | **accepted as recommended** (2026-09-22) |
| OQ2 | The cleanup gate: `human_present()` (a TTY or `AI_UNATTENDED`, recorded), or a TTY only? | `human_present()`, for parity with `approve` and `remediate`; `unattended: true` is shown by `/ai-status`. | user | **accepted as recommended** (2026-09-22) |
| OQ3 | Add the same human check to WP1's `--confirm-delete` now? | Yes; amend `tests/test-project-update.sh:432` with `AI_UNATTENDED=1`, and add a refusal case with stdin from `/dev/null`. | user | **accepted as recommended** (2026-09-22) |
| OQ4 | `original/` committed with a cap, or gitignored? | Committed, 1 MiB per file, the total printed. | user | **accepted as recommended** (2026-09-22) |
| OQ5 | Fixtures: the four the intent names, or all eight? | All eight. Each is a handful of files, and AI-DLC, Copilot, the Junie/Gemini duality and the Codex `AGENTS.md` parity case are where assumptions hide. | user | **accepted as recommended** (2026-09-22) |
| OQ6 | Real samples for Spec Kit, Kiro, AI-DLC, Cursor and Copilot. | Taken from each tool's public repository in the plan's first step; until then the README says "assumed". | factual (plan) | open — plan step 1 |
| OQ7 | Destination naming: flatten `specs/NNN-x/spec.md` to `docs/sdlc/specs/NNN-x.md`? | Flatten; it matches the one-file-per-slug convention of `docs/sdlc/`. | user | **accepted as recommended** (2026-09-22) |
| OQ8 | Kiro `requirements.md` to `docs/sdlc/intent/` or to `specs/`? | `intent/` | user | **accepted as recommended** (2026-09-22) |
| OQ9 | A project with `docs/sdlc/` but no `.ai/`: run adopt? | Refuse with exit 5 and "run /ai-init first", because adopt needs the router and `.ai/rules/` to exist. | user | **accepted as recommended** (2026-09-22) |
| OQ10 | Fold `--adopt --check` into the plain `--check` output? | No. That keeps the assertions at `tests/test-project-update.sh:69,102,188` untouched, and `/ai-status` gets a second line. | user | **accepted as recommended** (2026-09-22) |
| OQ11 | Accept that lines without an alphanumeric character are ignorable, one step beyond D4 (concern 2)? | Yes | user | **accepted as recommended** (2026-09-22) |
| OQ12 | Intent open questions 1 and 2 were settled in WP2. Nothing is carried. | — | — | settled |
