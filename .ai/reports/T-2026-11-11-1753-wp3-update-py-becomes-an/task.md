# T-2026-11-11-1753-wp3-update-py-becomes-an — WP3: update.py becomes an entry (CLI only, no re-exports) and rr_update/; behaviour unchanged

refactoring · guarded · started 2026-11-11T17:53:04Z · claude

## Weight

```
scope          1  skills/project-update/update.py not measured (over 10 files)
behaviour      1  keyword 'workflow' in CONTRIBUTING.md
reversibility  0  git revert returns everything
domain         0  "moves the project updater code; human_gate and the guard spelling unchanged" (declared)
novelty        0  "the WP1/WP1b pattern applied to a second file" (declared)
coverage       1  10 of 19 code files have a test
W 3 → guarded   hints none · unknown scope · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-11-11T17:53:03Z — /rr-build-all docs/sdlc/plans/small-oop-modules-wp3.md

## Plan

files: tests/fixtures/update/partition.json, tests/test_update_layout.py, tests/test_update_characterization.py, tests/fixtures/update/goldens/, skills/project-update/rr_update/__init__.py, skills/project-update/rr_update/paths.py, skills/project-update/rr_update/files.py, skills/project-update/rr_update/history.py, skills/project-update/rr_update/gate.py, skills/project-update/rr_update/siblings.py, skills/project-update/rr_update/kept.py, skills/project-update/rr_update/plan.py, skills/project-update/rr_update/weights.py, skills/project-update/rr_update/blocks.py, skills/project-update/rr_update/shared.py, skills/project-update/rr_update/rules.py, skills/project-update/rr_update/cleanup.py, skills/project-update/rr_update/hints.py, skills/project-update/rr_update/build.py, skills/project-update/rr_update/apply.py, skills/project-update/rr_update/report.py, skills/project-update/rr_update/cli.py, skills/project-update/update.py, tests/test_project_update.py, tests/test_shared_tree.py, tests/test_regenerate.py, tests/test_rename.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, docs/architecture.md, CONTRIBUTING.md, skills/project-update/SKILL.md
tests: tests/test_update_layout.py, tests/test_update_characterization.py, tests/test_project_update.py, tests/test_shared_tree.py, tests/test_regenerate.py, tests/test_rename.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, tests/test_instruction_budget.py
- s0 · tests/fixtures/update/partition.json, tests/test_update_layout.py · tests/test_update_layout.py · done
- s1 · tests/test_update_characterization.py, tests/fixtures/update/goldens/ · tests/test_update_characterization.py · done
- s2a · skills/project-update/rr_update/__init__.py, skills/project-update/rr_update/paths.py, skills/project-update/rr_update/files.py, skills/project-update/rr_update/history.py, skills/project-update/rr_update/gate.py, skills/project-update/rr_update/siblings.py · tests/test_update_layout.py · done · after s0, s1
- s2b · skills/project-update/rr_update/kept.py, skills/project-update/rr_update/plan.py, skills/project-update/rr_update/weights.py, skills/project-update/rr_update/blocks.py, skills/project-update/rr_update/shared.py, skills/project-update/rr_update/rules.py, skills/project-update/rr_update/cleanup.py, skills/project-update/rr_update/hints.py · tests/test_update_layout.py · done · after s2a, s0
- s2c · skills/project-update/rr_update/build.py, skills/project-update/rr_update/apply.py, skills/project-update/rr_update/report.py · tests/test_update_layout.py · done · after s2b, s0, s2a
- s3 · skills/project-update/rr_update/cli.py, skills/project-update/update.py, tests/test_project_update.py, tests/test_shared_tree.py, tests/test_regenerate.py, tests/test_rename.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py, tests/test_update_layout.py · tests/test_update_characterization.py, tests/test_update_layout.py, tests/test_project_update.py, tests/test_shared_tree.py, tests/test_regenerate.py, tests/test_rename.py, tests/test_no_fallbacks.py, tests/test_install_dry_run.py · done · after s2c, s0, s1, s2a, s2b
- s4 · docs/architecture.md, CONTRIBUTING.md, skills/project-update/SKILL.md · tests/test_instruction_budget.py · done · after s3

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | b27fe43dc | .ai/state/logs/T-2026-11-11-1753-wp3-update-py-becomes-an/suite-1.log | no |
| 2 | e2e | 0 | b27fe43dc | .ai/state/logs/T-2026-11-11-1753-wp3-update-py-becomes-an/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS

- [LOW] L1 The missing-package `except ImportError` is wider than its message (`skills/project-update/update.py:55-58`) in_scope: yes — `from rr_update import cli` wraps the whole import chain; a missing `render_instructions.py`, a partly copied package or an ImportError from a bug inside any module all exit with "rr_update/ is missing beside update.py: re-run `npx riskrails`". At HEAD a missing render_instructions gave a traceback naming the file. A working install is not touched. Direction: catch ModuleNotFoundError with exc.name == "rr_update" only, or print exc.
- [LOW] L2 `entry_uses_in` can still miss a real load of the entry (`tests/test_update_layout.py:441-466`) in_scope: yes — the RUNNERS skip is sound for today's suites; open paths: keyword args (`load(path=UPDATE)`), `runpy.run_path(UPDATE)[...]` subscripted, a loader constant not named UPDATE. None exists today. Direction: scan call.keywords or record the limitation in the docstring.
- [LOW] L3 REPORT_HASH hides the mode of migration.json (`tests/test_update_characterization.py`, NORMALISE / MIGRATION) in_scope: yes — mode column reads `-~`; a change of its executable bit is invisible; content changes other than timestamps, dates and the entry path still show. Direction: keep the real mode, normalise only the hash.
- [INFO] I1 render_instructions needs the entry's sys.path setup, so rr_update cannot be imported cold (`rr_update/{cli,blocks,kept,hints,rules}.py`) in_scope: yes — same coupling as at HEAD; matters only if a later change imports rr_update from another process.
- [INFO] I2 `files` → `files_of` in rr_update/cleanup.py, `paths` → `leaf_paths` in rr_update/weights.py in_scope: yes — avoid shadowing module names; call sites pair up.
- [INFO] I3 The goldens depend on the Python and git versions they were recorded on (`tests/fixtures/update/goldens/help.txt`) in_scope: no — portability risk for the register.

## EXAMINED AND CLEAN

1. Test hunks (R6): import lines, qualified names, patch targets, one expected-path swap in test_no_fallbacks/test_rename (the entry → rr_update/kept.py), two expected files in test_install_dry_run; no assertion, expected text or fixture changed; `upaths.SHARED = …` still reaches every reader (shared.py:22,25,49,74; history.py:73,82,84).
2. NORMALISE: exact UPDATE_PY, ROOT, TMP, PLUGIN_ROOT, RUN_DATE; regex USAGE, ISO_TS; no pattern matches a path. Key proof: the characterization test and goldens run against `git archive HEAD` with the old 1733-line entry pass (10 OK), so the goldens are HEAD's behaviour.
3. Cut-over: docstring byte-identical; cli.main differs from HEAD's main only by qualification; --help matches; dont_write_bytecode before the package import; mode 100755; HERE/SKILLS/HISTORY/TEMPLATES/PLUGIN_HOME same; sibling() via paths.SKILLS, one _MODULES memo; tomllib once in kept.py.
4. Module bodies: 72 top-level def/class names identical; line multisets match modulo qualifiers and I2; every alias.attr resolves; no undefined name; no `from rr_update.x import name`.
5. test_update_layout is not vacuous (see L2 for RUNNERS).
6. Installer copies the skill dir whole; package.json covers skills/; chmodX right; nothing in hooks/, skills/, bin/ imports the entry or rr_update; guard texts name the entry, still correct.
7. human_gate, placeholder_name, refuse moved unchanged into gate.py; golden covers exit 5.
8. Docs accurate (a cosmetic tree-glyph nit).
Not reached: runtime exercise of every path beyond the goldens and the green suite; no mutation testing.

## VERDICT

verdict: pass
scope_assessment: Inside the approved plan, pure move and qualification, no behaviour change found; edits confined to the task files; test edits satisfy R6. No finding blocks.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| CONTRIBUTING.md | +6 −0 | Edit |
| docs/architecture.md | +26 −0 | Edit |
| skills/project-update/rr_update/__init__.py | +1 −0 | New |
| skills/project-update/rr_update/apply.py | +188 −0 | New |
| skills/project-update/rr_update/blocks.py | +38 −0 | New |
| skills/project-update/rr_update/build.py | +96 −0 | New |
| skills/project-update/rr_update/cleanup.py | +194 −0 | New |
| skills/project-update/rr_update/cli.py | +102 −0 | New |
| skills/project-update/rr_update/files.py | +106 −0 | New |
| skills/project-update/rr_update/gate.py | +60 −0 | New |
| skills/project-update/rr_update/hints.py | +115 −0 | New |
| skills/project-update/rr_update/history.py | +117 −0 | New |
| skills/project-update/rr_update/kept.py | +120 −0 | New |
| skills/project-update/rr_update/paths.py | +108 −0 | New |
| skills/project-update/rr_update/plan.py | +123 −0 | New |
| skills/project-update/rr_update/report.py | +51 −0 | New |
| skills/project-update/rr_update/rules.py | +178 −0 | New |
| skills/project-update/rr_update/shared.py | +74 −0 | New |
| skills/project-update/rr_update/siblings.py | +37 −0 | New |
| skills/project-update/rr_update/weights.py | +171 −0 | New |
| skills/project-update/update.py | +8 −1682 | Edit |
| tests/fixtures/update/goldens/apply.txt | +304 −0 | New |
| tests/fixtures/update/goldens/errors.txt | +204 −0 | New |
| tests/fixtures/update/goldens/help.txt | +28 −0 | New |
| tests/fixtures/update/goldens/plan.txt | +134 −0 | New |
| tests/fixtures/update/partition.json | +1038 −0 | New |
| tests/test_install_dry_run.py | +2 −1 | Edit |
| tests/test_no_fallbacks.py | +1 −1 | Edit |
| tests/test_project_update.py | +11 −11 | Edit |
| tests/test_regenerate.py | +22 −19 | Edit |
| tests/test_rename.py | +1 −1 | Edit |
| tests/test_shared_tree.py | +22 −22 | Edit |
| tests/test_update_characterization.py | +468 −0 | New |
| tests/test_update_layout.py | +921 −0 | New |

+5075 −1737 lines, 34 files

## Verdict

close: closed
facts: (a) green — suite green on b27fe43dc (run 1) · (b) green — 34 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 1 · review passes: 1
