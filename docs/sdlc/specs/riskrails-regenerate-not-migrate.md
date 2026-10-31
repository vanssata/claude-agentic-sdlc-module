# Spec: riskrails regenerates its own files — no adopt, no migrations, no legacy fallbacks

Intent: `docs/sdlc/intent/riskrails-regenerate-not-migrate.md`

Labels: **KF** = KNOWN FACT (file:line), **INF** = INFERENCE (from what), **UNK** = UNKNOWN. Paths are repo-relative.
Design by the `architect` agent on the STRONG tier, 2026-10-31; policy pass by the session.

### Decisions taken

From `docs/sdlc/intent/riskrails-regenerate-not-migrate.questions.md`, in the order asked (all by Ivan Kakurov, 2026-10-31),
after Q25 A and Q26 A of `docs/sdlc/intent/small-oop-modules.questions.md`:

- Q1 → **A**: kept = Q26's set (`.ai/project/`, `.ai/reports/`, `.ai/memory/`, `.ai/state/`, `docs/sdlc/`, the project settings)
  plus the human's choices: `.ai/policies/dialog.json`, the text outside the managed block, `.claude/settings.json`,
  `.codex/config.toml`. Deleted and regenerated: `path-guard.json`, `coding.md`, `safety.md`, `security.md`, `.ai/AGENTS.md`,
  `.ai/VERSION`, `.ai/rules/`, the managed block, `.ai/local/` caches. (F5, F7 qualify this.)
- Q2 → **A**: mixed files are split; the project part lives in `.ai/policies/weight.project.json` and
  `.ai/policies/verification.md`, which the update never touches; the shipped part is read from the plugin only; the current mixed
  files are split once by this task's update. (F2 flags the one-time split.)
- Q3 → **A**: delete the SKILL.md-only alias directories and the alias SKILL.md of the code-holding ones; those stay at their paths
  (a rename is a refactoring, C3, its own task); the installer gets a retire list. (F3 corrects the list for `ai-audit`.)
- Q4 → **A**: every kept file is checked by its own reader before anything is deleted; one unreadable file refuses the whole update,
  naming the file, the reason and the last riskrails version with migrations; nothing is deleted or written.

### Evidence base

- KF update.py imports `migrations`, `adopt` (update.py:59-62); env fallback `CLAUDE_AGENTIC_<name>` (:64-66); shared tree fallback
  `claude-agentic/ai` (:78-81); `LEGACY_STATE_FILE` (:90, :99-105, :1243); `CREATE_ONCE` dialog.json (:96); legacy markers (:117-124);
  shared set loaded from `migrations/0006_shared_files.py` (:264-276); `detect_version` (:445-462); `MigrationContext` (:481-770);
  `run_migrations` (:772-802); `three_way` (:943-1004); `block_update` merges via history (:1066-1113); `shared_update` gated on schema 6
  (:1116-1164); `rules_update(planned=)` for adopt (:1439-1457); schema ladder in `build_plan` (:1597-1629, :1660-1665); main uses
  `adopt.placeholder_name/human_gate/refuse/budget_offenders/state_line` (:2040-2111).
- KF `adopt.py` is imported only by update.py and is 2 219 lines (intent:11); `skills/rr-setup/setup.py:28` reads `adopt-map.json`
  (MAP_FILE) to exclude foreign-tool roots from the own toolbox (:13, :96) — a dependency the deletion must cut.
- KF installer: `installSkills` rmrf's then copies every SHIPPED skill dir (bin/riskrails.js:764-771), so files dropped inside a
  still-shipped dir (adopt.py, migrations/) vanish; a dir the plugin stopped shipping is never removed — the only retire is
  `retire(root,'skills/status')` (:763). Plugin route installs dirs without SKILL.md (:767). Q25's premise holds for files, not dirs.
- KF `skills/ai-audit/` is NOT SKILL.md-only: it holds `templates/play-scoring-rubric.md`, `templates/ai-sdlc-adoption-plan.md`, read by
  `/rr-setup --audit` (rr-setup/SKILL.md:248, :262). Q3's premise is wrong for ai-audit.
- KF the project half lives in mixed files beyond Q2's two: coding.md template "/ai-init fills the project-specific half"
  (templates/.ai/policies/coding.md:3, `## Project specifics` :28); testing.md `## Project specifics` (:128); path-guard.json is wholly
  project additions, "a human changes it" (templates/.ai/policies/path-guard.json:2; security.md:72); `.ai/rules/<slug>.md` are the
  project's, "no rule ships with the plugin" (templates/.ai/rules/README.md:23); `.ai/local/memory/config.json` holds the clone's memory
  choices (memory_sync.py:79); `.ai/policies/memory.json` is written by a human's `state.py memory enable` (.ai/AGENTS.md:36).
- KF the testing-field reader is `sensors.read_commands` with **eight** fields (sensors.py:207-245), not five; also read/written by
  setup.py (:29, :36, :308, :512-518) and update.py hints (:1684-1696).
- KF weight.py reads the project's weight.json whole, else the shipped one (weight.py:41-50; SHIPPED :26-27); this repo's table differs
  from the shipped one in `tests`, `batch`, `documents` (.ai/policies/weight.json:186-223 vs template :42-43).
- KF history/index.json answers "was this ever shipped" from hashes alone (update.py:254-258); weight.json has 2 historic versions
  (history/index.json:195-198).
- KF version 3.1.0 in package.json:3 and both plugin manifests; CHANGELOG 3.1.0 = schema 10→11, migration 0011 (CHANGELOG.md:5-26).
  UNK whether 3.1.0 is published on npm (memory records 3.0.0 published).
- KF weight per C6: weight.json:205 "changes how user projects are installed or migrated" = guarded-band behaviour example with
  behaviour 2; skills/CLAUDE.md:3 "behaviour 2 … changes install and migration … start --mode full --by <name>"; weight.json:209
  "a migration that rewrites user trees" is a `full` example; hooks/CLAUDE.md:3 removing a fallback the guard reads = behaviour 2.

## Requirements

R1 (Q26) `update.py` has no `--adopt --mode --tool --split-request --split --diff --cleanup`; each exits 2 (argparse). Proof:
   `tests/test_project_update.py::TestCli.test_removed_flags`.
R2 (Q26) Deleted paths: `skills/project-update/{adopt.py,adopt-map.json,migrations/}`, `tests/test_project_adopt.py`,
   `tests/fixtures/adopt/`, `tests/test_migration_0006.py`, `tests/test_migration_0010.py`, `tests/test_migration_0011.py`, migration
   fixtures `tests/fixtures/project-update/{migrations-*,schema-v*,risk-tiers,shared-old}`, adopt cases of `tests/test_shared_tree.py`
   and `tests/test_rename.py`. Proof: `tests/test_no_fallbacks.py::test_removed_paths_absent` (literal list).
R3 (Q26, Q1) `--update --apply` (with a human's `--confirm-delete`) leaves every GENERATED target (D2) byte-equal to its template, the
   managed block byte-equal to `<RT>.block.md` between the markers. Proof: `tests/test_regenerate.py::TestGenerated` on four fixture
   trees: fresh scaffold, a 3.1.0 tree (schema 11), an edited 3.1.0 tree, a dual-runtime tree.
R4 (Q1) Every KEPT path (D2) is sha-identical before and after any `--update` run, including all bytes outside the managed block of
   CLAUDE.md/AGENTS.md/GEMINI.md/.junie/guidelines.md. Proof: `TestKept.test_kept_byte_identical` (same four trees).
R5 Idempotence: a second `--apply` plans nothing, `--check` exits 0, `git status --porcelain` is empty. Proof: `TestIdempotent`.
R6 The dry run writes nothing (tree sha unchanged) and prints one row per `create/regenerate/regenerate?/delete/delete?/split` with its
   reason; an edited file's row names the lines it loses and the `original/` path. Proof: `TestDryRun`.
R7 Human gate: a GENERATED file whose sha is in no shipped version, and every removal without a replacement, is `regenerate?`/`delete?`
   until `--apply --confirm-delete NAME` from a human (update.py:1587 gate semantics unchanged); its original goes to
   `.ai/reports/project-update-<date>/original/<path>` (keep_original, :1765). Proof: `TestGate`.
R8 The guard's `--confirm-delete` deny stays: path-guard fixtures 45–50 and codex-hooks 41 kept byte-identical (their `--adopt` text is
   inert payload; paths.py:68, :1264 match the flag, not adopt); guard golden byte-identical. Proof: `test_ai_path_guard`,
   `test_guard_characterization` unchanged.
R9 (Q2) `weight.py load_policy(root)` = the plugin's table (SHIPPED) with `.ai/policies/weight.project.json` overlaid (dicts merge,
   anything else replaces); returns `(policy, [shipped, project])`; a broken overlay raises ValueError naming the file. Proof:
   `tests/test_weight.py::TestOverlay`.
R10 (Q2) `.ai/policies/verification.md` is the only source of the eight TESTING_FIELDS for `sensors.read_commands` (state.py verify,
   close, policy.py:342), `setup.py check|verify --set`, and update's empty-field hints. Proof: `test_ai_task_sensors::TestVerificationFile`,
   `test_setup::TestVerifySet`.
R11 (Q2, concern F2) One-time split, only when the new file is absent: verification.md ← the field lines of testing.md copied verbatim
   (+ continuation lines, + `## Project specifics` verbatim); weight.project.json ← leaves of the old weight.json differing from that
   leaf in every shipped version (lists whole); uncarried leaves listed. With the new file present the old file's content is never
   read again. Proof: `TestSplitOnce` (run twice; second run no `split` row).
R12 (Q4) Before any write, each kept file passes its own reader (D4); one failure → exit 6, stdout line 1 `KEPT_UNREADABLE`, the exact
   text of Interfaces I3, nothing written or deleted (tree sha unchanged). Proof: `TestRefusal`, one subTest per reader and old shape.
R13 (Q4) The refusal names `riskrails@3.1.0` from one constant `LAST_MIGRATING_VERSION`. Proof: `TestRefusal.test_names_version`.
R14 (Q1) `.ai/policies/dialog.json`, `.ai/policies/memory.json` absent stay absent, present stay byte-identical. Proof: `TestKept`.
R15 Managed block per declared runtime (project_runtimes, update.py:185): rewritten between markers; no block → appended; no file →
   minimal + block (block_update's create/append, :1071-1081, kept). Proof: `TestBlock`.
R16 Rules: `.ai/rules/README.md` regenerated; `<slug>.md` sources kept (A3); rule blocks and `.claude/rules/*.md` re-rendered and taken
   back as today (rules_update without `planned`). Proof: existing rules cases of test_project_update.py, minus legacy markers.
R17 Shared set = constant `SHARED_SET` in update.py (replaces 0006's tuple) equal to the `ai/` tree; a project copy identical to a
   shipped version → `delete?`; an edited one stays, one hint (A5). Proof: `test_shared_tree` set-equality case, `TestShared`.
R18 `.ai/local/plugin-update/` is removed; `.ai/local/memory/` is never touched. Proof: `TestKept.test_local_memory_untouched`.
R19 (Q3) `skills/{ai-status,sdlc-intent,sdlc-plan,sdlc-spec}/` deleted; SKILL.md deleted in `ai-task, project-update, ai-init,
   project-init, usage-report, ai-audit` (ai-audit keeps templates/, F3). Proof: `test_skills_surface` expected set.
R20 (Q3) Installer `RETIRED_SKILLS` moves `status, ai-status, sdlc-intent, sdlc-plan, sdlc-spec` from `<home>/skills/` to
   `backups/<date>/skills/` on both runtimes; dry run prints one `retire:` line listing them. Proof: `test_install_dry_run`,
   `test_install_routes` (an install over a tree holding them).
R21 Every REMOVE row of the inventory (D8) is gone. Proof: `tests/test_no_fallbacks.py::test_no_legacy_tokens` — tokens
   `CLAUDE_AGENTIC_`, `claude-agentic`, `claude_agentic`, `current.json`, `LEGACY_STATE`, `LEGACY_REVIEW`, `OLD_START`, `--adopt`,
   `adopt.py`, `adopt-map`, `migrations/`, `one version`, `/ai-task`, `/ai-init`, `/project-update`, `/project-init`, `/ai-status`,
   `/ai-audit`, `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan`, `/usage-report` over skills/ hooks/ bin/ scripts/ ai/ agents/ instructions/
   codex/ profiles/ tests/ README.md docs/ (minus docs/sdlc/, history/, CHANGELOG.md, docs/redesign-analysis-*, docs/time-analysis-*),
   allow-list = the KEEP rows with a reason each, and a stale-entry check like test_rename.py:86-88.
R22 test_rename.py: ALLOWED shrinks to the KEEP rows; `test_env_names_new_first_then_old` deleted (it pins the removed fallback).
R23 Only `RISKRAILS_<name>` is read (update.py env, scripts/ai-path, scaffold_ai.py:215); every test env switched. Proof: R21 token.
R24 (OQ4) Old shapes fail closed, never read: weight.py raises when `.ai/policies/weight.json` exists and weight.project.json does not;
   `sensors.command_for` refuses when testing.md has a filled `verify_command` and verification.md is absent; scope/path guard deny an
   edit when `current.json` exists and `state.json` does not. Each message names `/rr-setup --update`. Proof: new cases in test_weight,
   test_ai_task_state, test_ai_scope_guard; golden re-recorded (behaviour 1).
R25 `/rr-status` schema line compares `.ai/VERSION` with `skills/ai-init/templates/.ai/VERSION`, not the migrations dir
   (status.py:70-84). Proof: `test_ai_status_root`.
R26 Text: rr-setup/SKILL.md (description, argument-hint, `--adopt` section, `--update` steps 2-6), docs/project-update.md, README,
   docs/{installation,getting-started,faq,architecture,hooks,known-risks}.md, ai/using-riskrails.md:21, instructions/routing.md,
   rr-*/SKILL.md alias mentions, templates naming alias commands, the router template's Shared files + rows; CHANGELOG entry
   (breaking). Proof: R21 + test_skills_surface, test_instruction_budget, test_shared_prompts_model_free.
R27 `tools/build-template-history.py` runs in the same task (skills/CLAUDE.md:5). Proof: `test_history_covers_every_template`.
R28 `--check --budget` output unchanged (budget_offenders moved from adopt.py into update.py). Proof: existing budget cases.
R29 Exit 5 prints `CONFIRM_REFUSED` (OQ10); exit 4 is never emitted again. Proof: `TestGate.test_refused_token`.
R30 verify_command once, e2e_command once, green; README test count updated (testing.md:166-169).

## Design

D1 Principle: **detect, refuse, never convert.** The only conversion is the one-time split (F2); every other old shape is detected by a
   literal check and refused (exit 6 in update, a refusal in weight/sensors/guard), never read or rewritten.

D2 Inventory (code constants in update.py; `KEPT` and `GENERATED` are disjoint, tested):
   KEPT: `.ai/project/**`, `.ai/reports/**`, `.ai/memory/**`, `.ai/state/**`, `docs/sdlc/**`, `.ai/policies/{weight.project.json,
   verification.md,dialog.json,memory.json}`, `.ai/rules/<slug>.md` (A3), `.ai/local/memory/**` (A4), edited shared overrides (A5),
   bytes outside managed blocks, `.claude/settings.json`, `.codex/config.toml`, `.gitignore` (append-only, update.py:1525).
   GENERATED (from `skills/ai-init/templates/`): `.ai/AGENTS.md`, `.ai/VERSION`, `.ai/policies/{path-guard.json,coding.md,safety.md,
   security.md,testing.md,weight.md}`, `.ai/rules/README.md`, `.ai/state/README.md`, `.ai/reports/.gitkeep`, `<rt>/memory/README.md`,
   each managed block. `.ai/project/*` templates: created when missing only (today, :1667-1670).
   REMOVED: `.ai/local/plugin-update/**`, the old `.ai/policies/weight.json` after its split (A2), unedited shared copies.
   FOREIGN: everything else — never read, never listed.
D3 Flow of `--update`: `locate` (no .ai/ nor docs/sdlc → exit 2) → `version_guard` (.ai/VERSION > template VERSION → exit 2, today's
   :1607 rule) → `inventory` → `check_kept` (D4; any failure → exit 6, nothing written) → `plan`: `split_once` → `regenerate` →
   `shared` → `block` per runtime → `rules` → `local` → `gitignore`, `cleanup_update` (A6), hints → `--check` one line | dry run report
   | `apply`. Apply order: split writes → creates/regenerates → confirmed deletions → `.ai/VERSION` last (an abort leaves "behind");
   per-item sha preconditions and exit 3 unchanged (update.py:1722, :1809); a re-run heals.
D4 Kept readers: state.json → JSON object (the reader update.py:783-791 uses today); weight.project.json → JSON object, `version` 1,
   overlay passes load_policy's axes/modes check; verification.md → UTF-8 text (sensors.read_commands); dialog.json, memory.json →
   JSON object; .claude/settings.json → JSON object; .codex/config.toml → `tomllib.loads` (3.11 floor, CHANGELOG:15). Old-shape
   detectors (literal, no parsing): `current.json` without `state.json`; `<!-- claude-agentic:` or `<!-- Codex-agentic:` in an instruction
   file or rule block; `risk-tiers.json` without `weight.json`/`weight.project.json`. Not checked: memory (its own `memory verify`),
   project/, reports/, docs/sdlc/ (update reads no format there). A task in flight stays a hint (today :800), not a refusal (C1).
D5 Regenerate rule per GENERATED target: absent → `create`; equal → nothing; sha ∈ history hashes of its key → `regenerate`
   (automatic); else → `regenerate?` (R7 gate, original kept). path-guard.json's row also prints the count of non-empty
   deny/allow patterns it drops (F5). The managed block applies the same rule to the block bytes against `ai-init/<RT>.block.md` hashes.
D6 What of update.py survives: Plan (minus `schema/held`), apply/apply_item/check/write_file/keep_original/prune_empty/Abort, report
   (record under `.ai/reports/project-update-<date>/`), rules_update (minus `planned`), rendered_rules, nested_tree, unwalked_dir,
   _frozen_block, gitignore_update, budget_hints, constitution_hint, cleanup_update, task_journal, deletion_hint, tracked_ignored_hint,
   git_states, git_dirty_ai, unsafe_path, require_shared (lifted out of MigrationContext), project_runtimes and the maps; History keeps
   `versions/hashes` without `renames/chain`. Gone: three_way, merge_text/json, closest, scores, router_merge, put_section,
   split_shared_section, weight_mirror/stale_mirror_hint (weight.md is always rendered from shipped+overlay), MigrationContext,
   run_migrations, detect_version, CREATE_ONCE, state_file, renamed_markers, declared_shared. Moved in from adopt.py: human_gate,
   placeholder_name, refuse (token CONFIRM_REFUSED), budget_offenders. INF: update.py shrinks to roughly 1 300 lines (from 2 147).
D7 history/ stays: index.json decides `regenerate` vs `regenerate?` (D5) and shared-copy deletion; blobs of weight.json give the
   split its base values (F2). No merge reads blobs any more; pruning the other blobs is a tools/ change for WP3, not here.
D8 Removal inventory (R = remove, K = keep with reason):
   A --adopt: R adopt.py, adopt-map.json; update.py:62, :2008-2021, :2040-2111; rules_update `planned` :1444-1457; setup.py:28 MAP_FILE →
     R, its foreign roots become constant `FOREIGN_ROOTS` in setup.py (survey output unchanged; INF from setup.py:96); rr-setup/SKILL.md:3-4,
     20, 110-111, 172-173, 183-230. `setup.py adopt` (own toolbox, :472-542) → OQ3.
   B migrations: R migrations/ (13 files); update.py:59-60, :87, :96, :264-276, :445-462, :481-802, :895-1063, :1091-1113, :1121-1124,
     :1597-1629, :1660-1665, :2115-2128; status.py:76-82; scaffold_ai.py:222 comment.
   C R35 old name: R update.py:64-66, :74-81, :117-124, :583-584; render_instructions.py:50-55, :422, :458-475, :499; scaffold_ai.py:31
     (alternation), :215; scripts/ai-path:23; scripts/resolve-profile.py:43; rr_state/profile.py:25-28; rr_state/dialog.py:167, :182
     (comments); hooks/runtime-gate.py:130-132; usage-report.py:584-586; bin/riskrails.js:304, :351, :711-721 (+ calls :1045, :1335),
     :810-813 (+ :682, :1324), :835-846. K hooks/ai-path-guard-defaults.json:48 (a deny; removing it weakens a refusal, gains nothing);
     K gitignore.snippet line 1 ×2 (projects match the header verbatim, test_rename.py:37-39).
   D R34 current.json: R update.py:89-105, :1243; rr_state/fs.py:62-71; memory_store.py:17; sensors.py:353; status.py:8, :39-41;
     hooks/guard/scope.py:6, :336-338; hooks/guard/paths.py:674-677; hooks/context-guard.py:394; hooks/runtime-gate.py:917;
     agents/ai-reviewer.md.tmpl:57; templates/.ai/state/README.md:48 (replaced by R24's fail-closed checks).
   E aliases and one-version stubs: R skills/{ai-status,sdlc-intent,sdlc-plan,sdlc-spec}/; SKILL.md ×6 (R19); ai/workflows/{feature,
     bugfix,hotfix,investigation,refactoring}.md and ai/agents/manager.md (each :4 "stays one version") + their SHARED entries
     (0006:64, :71-75); ai/using-riskrails.md:21; bin/riskrails.js:763 → RETIRED_SKILLS (+ dry-run lines :679, :1321).
   F listed, default OUT (OQ9): hooks/guard/paths.py:724-725 `dependency_instruction_patterns` (a deny reader); runtime-gate.py:79,
     :98-99, :169-172, :219-223, :1112, :1187-1188 (fable-gate / codex-model-gate names, `--as`); bin/riskrails.js:825-834 (claude-routing,
     "Model allocation") + tests/test_merge_migration.py. K memory_format.py:74, memory_store.py:329, memory_compact.py:801 — readers of
     KEPT data (.ai/reports, .ai/memory), not plugin-version fallbacks.
D9 Order of work (plan input; each line one task or step, each verified by its R):
   1 readers first: weight.py overlay + fail-closed (R9, R24a), sensors/setup on verification.md (R10, R24b), templates for both new
     files, router template; verify: test_weight, test_ai_task_sensors, test_setup green.
   2 update.py regenerate: D2-D7, split_once, check_kept, CLI (R1, R3-R18, R28, R29); delete adopt/migrations and their tests (R2);
     verify: test_project_update, test_regenerate, test_shared_tree.
   3 fallbacks C, D (R21-R23, R24c, R25); hooks golden re-recorded once; verify: guard suites + test_no_fallbacks.
   4 aliases, stubs, installer retire list, docs, CHANGELOG, history rebuild (R19, R20, R26, R27); verify: R30.

Rejected alternatives:
- X1 Regenerate everything with no gate (delete edited files outright). Rejected: loses human text silently (coding.md project half,
  path-guard patterns, router rows), makes `--confirm-delete` and its guard rule dead — an approval path removed (behaviour 2, C5 spirit).
- X2 Drop history/ and gate every differing file. Rejected: every plugin text change becomes a human confirmation in every project on
  every release; humans rubber-stamp a list that long.
- X3 Keep the split as migration 0012 in migrations/. Rejected: keeps the ladder (registry, VERSION semantics) alive — Q26.
- X4 Fallback readers in hooks/weight/sensors "for one more version". Rejected by Q25; D1's fail-closed detection costs one existence
  check and never weakens a guard.
- X5 Overlay that concatenates lists (project examples appended to shipped ones). Rejected: a project could never drop a shipped item,
  and the split would have to subtract lists; replace-whole is deterministic.

### Risks

1 Data loss of human text in GENERATED files (coding.md and testing.md project halves, path-guard.json patterns, `.ai/AGENTS.md` rows
  appended by `setup.py adopt` or past adopt runs, e.g. this repo's .ai/AGENTS.md:63). Mitigation: D5 gate + original/ copy + the row
  names the lines lost; testing.md's half moves to verification.md (R11); coding.md's stays a loss until OQ2.
2 Weight lighter between plugin install and `--update`: the old weight.json's `domain.modules` would be ignored, a payments change could
  weigh light. Mitigation: R24a refusal (weight cannot be computed until the split ran).
3 Scope guard inert for a task sitting in current.json once the fallback goes (scope.py:336-340 returns). Mitigation: R24c deny; the
  update refuses the same shape (D4).
4 verify finds no command before the split. Mitigation: R24b names `/rr-setup --update`.
5 Shared overrides (`.ai/` copy of a shared path, AGENTS.md "Shared files"): unedited → `delete?`; edited → kept, hint; an edited copy of
  a deleted stub (ai/workflows/*.md) becomes an orphan — hint names it. require_shared refuses deleting a copy whose fallback is missing
  in any declared runtime's home (kept from MigrationContext, update.py:559).
6 Uncommitted `.ai/` edits (git_dirty_ai, :301): git is not the only rollback any more — original/ holds every gated loss; the
  "commit .ai/ first" hint stays (:1307-1316).
7 Dual-runtime projects: one block per declared instruction file; both homes must hold the new shared tree (require_shared); skew when
  the plugin route updated SKILL.md text but `npx riskrails` did not reinstall the scripts (old update.py still has --adopt) —
  CHANGELOG and rr-setup say "reinstall both".
8 Leftover alias dirs on the npx route keep loading as commands until RETIRED_SKILLS runs (R20). INF: the plugin route ships a fresh
  versioned cache, so dropped dirs vanish there.
9 Weight axis (C6, CLAUDE.md rule 2, weight.json:205, skills/CLAUDE.md:3, hooks/CLAUDE.md:3): this changes how user projects are installed
  and updated and removes a fallback a guard reads → **behaviour 2**, plainly — not for being "a process", for the effect; deleting
  user files → reversibility hint (weight.json:209). Start with `start --mode full --by Ivan`, declare behaviour=2, STRONG review + gate.
10 Large test deletion lowers the count and can hide lost coverage: each deleted test maps to a removed behaviour (R2 list); the guard
  `--confirm-delete` fixtures stay (R8).
11 Downgrade: 3.1.0 on a regenerated tree refuses (VERSION newer, update.py:1607-1609) — KF, the documented order in I3 is safe.
12 The old-shape detectors (D4) are themselves residue of the past; they are four literals, deleted by a later human decision.

## Interfaces

I1 CLI after the change:
   `update.py [project-dir] [--apply [--confirm-delete NAME] [--confirm-cleanup NAME]] [--check [--budget]]`
   Removed: `--adopt --mode --tool --split-request --split --diff --cleanup`. Exit: 0 done / current; 1 `--check` pending or over budget;
   2 usage, templates missing, `.ai/VERSION` unreadable or newer than the plugin; 3 apply aborted; 4 retired, never reused; 5
   `CONFIRM_REFUSED` (a `--confirm-*` without a human); 6 `KEPT_UNREADABLE`. `--check` with an unreadable kept file prints I3's first
   line and exits 6. Row actions: `create regenerate regenerate? delete delete? split` + `[cleanup]` rows unchanged.
I2 `.ai/policies/weight.project.json` (created by the split or by a human; the update never writes it again):
   ```json
   {"version": 1,
    "_comment": "Yours. weight.py lays it over the plugin's weight table: objects merge, any other value replaces. /rr-setup --update never rewrites it.",
    "domain": {"modules": ["**/Payment/**"]}, "scope": {"hot_paths": ["hooks/**"]},
    "tests": {"max_suite_runs": 5}, "documents": {"globs": ["**/*.md"], "except": ["skills/**"]},
    "examples": {"light": ["this repository: …"]}}
   ```
   `.ai/policies/verification.md` (template shipped with empty values; the update creates it only when absent):
   ```
   # Verification — this project's commands
   <!-- Yours. Read by state.py verify and close, setup.py check, update.py hints; /rr-setup --update never rewrites it. -->
   verify_command:      <one command, no fail-fast>
   step_test_command:   <runner {files}>
   e2e_command:         <command | none>
   lint_command:        <command | none>
   typecheck_command:   <command | none>
   single_test:         <command>
   doc_tests:           <paths | none>
   bite_codes:          1
   healthy_output:      <what a green run ends with>
   ## Project specifics
   ```
I3 Refusal (stdout; one line per failing file, then the rest verbatim):
   ```
   KEPT_UNREADABLE: <path>: <reason>
   project-update: nothing was deleted or written. This version regenerates its own files and no longer converts older ones.
   Install riskrails@3.1.0 (npx riskrails@3.1.0), run /rr-setup --update with it, then install this version and run /rr-setup --update again.
   ```
I4 Installer: `const RETIRED_SKILLS = ['status', 'ai-status', 'sdlc-intent', 'sdlc-plan', 'sdlc-spec'];` and in installSkills
   `for (const n of RETIRED_SKILLS) retire(root, \`skills/${n}\`);` (replaces :763); dry run:
   `retire:  skills/{status,ai-status,sdlc-intent,sdlc-plan,sdlc-spec}, into backups/<date>/ if present`. Files removed inside a still-
   shipped dir need no entry (rmrf+copy, :770-771).

## Policy conformance

- Constitution `docs/sdlc/constitution.md` (C1–C6; C7–C10 are placeholders). No `docs/sdlc/adr/` — no ADR binds this spec.
- Instruction files: root `CLAUDE.md`, root `AGENTS.md`, global `~/.claude/CLAUDE.md` (RiskRails rules); project agents/skills under
  `.claude/` — none apply.
- C1: production behaviour is removed only where Q25/Q26 decided; everything else (cleanup rows, task-in-flight hint, gitignore, gate)
  is kept as is; fail-closed checks prevent silent changes in old projects.
- C2: removed behaviour needs no characterization test; new refusals (R12, R24) each start with a failing test; deleting tests is
  declared (weight.json:198 "deleting … a test … declare behaviour=1").
- C3: behaviour removal only — no rename of ai-task/project-update (Q3), no update.py split (WP3).
- C4: D9 names files per step; ai-audit's templates widen Q3's list — recorded here, not discovered mid-step.
- C5: `--confirm-delete`/`--confirm-cleanup` stay human-only; the agent never runs them.
- C6: behaviour 2 (Risk 9).
- CLAUDE.md (root): BLOCKER closed by a pinning test — R12/R24 have tests; the weighting rule is respected by naming the effect.
- AGENTS.md (root) vs CLAUDE.md: AGENTS.md carries none of CLAUDE.md's "Things Claude Code gets wrong" — a Codex session misses the
  weighting rule; outside this task (kept text).
- .ai/AGENTS.md: its row "the project is behind | /project-update (VERSION is this tree's schema)" and Shared files list (risk-tiers.*)
  are stale; the regenerated router (R26) fixes the template, this repo's copy is regenerated by its own update.
- .ai/policies/testing.md: verify_command + e2e_command once (R30); README count updated; `doc_tests` (testing.md:96) names no
  deleted suite (test_rename, test_shared_tree, test_project_update all stay); the step-test table row for skills/project-update/**
  (testing.md:154) loses test_project_adopt.py and gains test_regenerate.py, test_no_fallbacks.py — a human edits it (policy file).
- weight.json / skills/CLAUDE.md:5: history rebuilt in the same task (R27).

## Open questions

OQ1 (Ivan) `.ai/rules/<slug>.md`: keep the project's rule sources (A3) or delete per Q1's letter?
OQ2 (Ivan) coding.md `## Project specifics` and path-guard.json: split them too (`coding.project.md`; path-guard.json KEPT like dialog.json),
    or regenerate behind the gate (design default)?
OQ3 (Ivan) `setup.py adopt` (own toolbox → toolbox.md + router rows): deleted with `--adopt` (Q26's letter) or kept under another verb?
OQ4 (Ivan) R24's fail-closed refusals add denies (behaviour 1, golden re-recorded): accept, or remove the fallbacks bare?
OQ5 (Ivan) `[cleanup]` rows inside KEPT dirs: keep in `--update` (default) or move out?
OQ6 (Ivan, release) Confirm `npm view riskrails versions` lists 3.1.0 and this release's number (A8).
OQ7 (Ivan) `docs/sdlc/README.md`: frozen (A7) or GENERATED?
OQ8 (Ivan) Edited shared overrides: KEPT (A5) or deleted behind the gate?
OQ9 (Ivan) Group F fallbacks (dependency_instruction_patterns, runtime-gate legacy names and state import, installer claude-routing /
    "Model allocation" migration): this task, or a later one (default)?
OQ10 (Ivan) Exit-5 token `ADOPT_REFUSED` → `CONFIRM_REFUSED`?
OQ11 (Ivan) `.ai/local/memory/`: confirm it is not a riskrails cache (A4).
OQ12 (spec author) One task in four steps (D9) or four tasks, each full mode?

## Flagged concerns

F1 policy vs intent — Q25's premise "an install replaces every plugin file" holds for files inside shipped dirs (rmrf+copy,
   bin/riskrails.js:770-771) but not for dirs: dropped skill dirs stay (only skills/status is retired, :763). Hence R20.
F2 "no migrations" vs Q2's one-time split: the split IS a conversion. Narrowest form chosen: runs only when the new file is absent;
   verbatim line copy for verification.md; leaf-diff against shipped versions for weight.project.json; uncarried leaves listed; the old
   weight.json removal is human-gated; code deleted in the next release, whose refusal then names this release.
F3 Q3 premise wrong: ai-audit holds templates/ read by /rr-setup --audit (SKILL.md:248, :262) — delete its SKILL.md only.
F4 C3: this task removes behaviour; any rename (ai-task → rr-*, project-update → rr-setup, the update.py split) stays out.
F5 Security: Q1 regenerates path-guard.json, which holds only a human's deny/allow additions (template :2) — dropping deny_patterns
   weakens a guard (behaviour 2); mitigated by D5's gate and the row's pattern count, not removed — OQ2.
F6 C1: removing fallbacks breaks projects still on old shapes (current.json, legacy markers, pre-0007 weight, testing-only commands);
   answered by D1 fail-closed + exit 6, never by silent misbehaviour.
F7 Q1 vs data: `.ai/rules/` listed as regenerated, but its `<slug>.md` are project-authored (README.md:23); `.ai/local/` listed as caches,
   but `.ai/local/memory/config.json` is the clone's choice. Design keeps both (A3, A4) — OQ1, OQ11.
F8 Q1 vs Q2: Q1 says weight.json is "regenerated", Q2 says the shipped part is read from the plugin only — design has no project
   weight.json (A2).
F9 Q26 lists the path-guard `--confirm-delete` fixtures for deletion, but the deny they pin stays (the new update deletes) — kept (R8).
F10 Q2 names five *_command lines; the reader has eight fields (sensors.py:207-209) — verification.md carries all eight.
F11 Q1 says KEPT files are never deleted, yet `[cleanup]` rows delete under .ai/reports and .ai/state/logs (update.py:1228-1304),
   human-gated by `--confirm-cleanup` — kept as today (A6), OQ5.
F12 Dependency: deleting adopt-map.json breaks setup.py survey (MAP_FILE :28) — FOREIGN_ROOTS constant (D8 A).
F13 UNK: 3.1.0 on npm. If unpublished, I3 names a version a user cannot install.

Assumptions: A1 the "Nothing" tick reads as "nothing else" (intent:25-26, Q1 A). A2 no project weight.json after the split; the router
points at weight.md (effective table). A3 `.ai/rules/<slug>.md` KEPT, README regenerated. A4 only `.ai/local/plugin-update/` is
riskrails' cache. A5 edited shared overrides KEPT (a human's override, rr-setup/SKILL.md:84-89). A6 `[cleanup]` stays. A7 `docs/sdlc/README.md`
is never updated again (docs/sdlc/ KEPT). A8 the release is a semver major (4.0.0) — breaking removals.
