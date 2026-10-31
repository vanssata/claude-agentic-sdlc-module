# Spec: Small OOP modules — the framework, the settings registry, the first extractions (ADR 0001)

Intent: `docs/sdlc/intent/project-settings-dialog.questions.md` (Q1–Q14, 2026-10-30). This is part 1 of 2 (Q13=A);
part 2, `docs/sdlc/specs/project-settings-dialog.md`, starts as soon as this one closes and depends on nothing else.

## Intent

**Problem.** New features keep landing in monoliths — `skills/ai-task/state.py` 5230 lines,
`skills/project-update/update.py` 1972 — and their tests can only be run as a whole. Project settings have no
registry: nothing lists which exist, which module owns them, or which a project has confirmed.

**Outcome (testable).**
- M-O1 A `modules/<id>/` package layout exists — a manifest, a facade as the only import surface, its own `tests/` —
  with a template and a layout test that every module passes.
- M-O2 Module tests run when the task's diff touches the module, in CI on every push, never in e2e.
- M-O3 The `settings` module is the first new module: the registry, stores, confirmations and audit that part 2's
  dialog needs, with no caller-visible behaviour yet.
- M-O4 Parts of `state.py` and of `update.py` move into modules with no behaviour change: both files get smaller and
  the moved code is tested in its own module.
- M-O5 The module-disable flag exists but does nothing; no shipped module is disableable; a test-only module proves the
  flag (Q12).
- M-O6 ADR 0001 records the decision; `ROADMAP.md` names the next moves.

**Affected users and systems.** Every developer of a project with `.ai/` through the installer (`modules/` is shipped
and protected); `state.py`, `update.py`, `tests/run_suite.py`, CI, `bin/riskrails.js`, `package.json`,
`hooks/ai-path-guard-defaults.json`. No user project's files, decisions or gates change.

**Constraints and non-goals.** C3: every extraction is a refactoring task of its own, no behaviour change, never in
the same task as a feature. No dialog, no `start` gate, no migration, no SessionStart line — those are part 2. Module
disabling is not implemented. Stdlib only.

**Open questions.** none blocking; see `## Open questions`.

### Decisions taken

| Q | Question | Answer |
|---|---|---|
| Q2 | Which settings exist | **X** — a registry of settings, each declared by the module that uses it (`dialog.enabled`, `verify_command`, `e2e_command`, modules on/off), extensible later |
| Q3 | How a setting is known to be new | **A** — id + version; `.ai/policies/settings.json` holds the confirmations |
| Q4 | When module tests run | **A** — verify on the task's diff; never in e2e; CI on every push |
| Q5 | Where modules live | **A** — `modules/<name>/`, installed to `<home>/riskrails/modules/`, facade + manifest + `tests/` |
| Q7 | The unimplemented disable flag | **B** — read; `false` only warns; shown "(not effective yet)" |
| Q8 | `dialog.json` | **A** — stays; the `dialog` module declares it; `settings.json` holds only confirmations and `modules.*` |
| Q12 | Disableable new modules | **A** — none of the new modules is disableable; a separate test-only module carries the flag (supersedes Q9) |
| Q13 | Specs | **A** — two specs: (1) the modular split — only `settings` as a new module, plus extractions from `state.py` and one more large file; (2) the dialogs, run right after (1) |
| OQ-M1 | Next extraction after T2/T3 | **A** — the dialog and consent readers (2026-10-31): one `modules/dialog` reader replaces the two copies in `hooks/guard/dialog.py` and `state.py`; stdlib only, found by the same `sys.path` probe as every module, since hooks run under `python3 -I -S` and never import `skills/ai-task`. `setup.py` (B) follows later |

## Requirements

Each: outcome · test (`file::name`) · step.

- **M1 Manifest** (M-O1). `modules/<id>/module.json`: `id` `^[a-z][a-z0-9_]*$` equal to the dir name; `version` int ≥1;
  `title` ≤60; `can_disable` bool; `settings` list — each a unique `id`, `version` ≥1,
  `kind` ∈ {`bool`, `command`, `module_toggle`}, `required`, `header` ≤12, `title` ≤200, a `store` in the allowlist.
  A bad manifest raises `ManifestError("<file>: <field>: <why>")`.
  `modules/settings/tests/test_settings_spec.py::test_invalid_manifest_names_file_and_field`. S3.
- **M2 Layout** (M-O1). Every `modules/*` dir, `_template` included: `module.json`, `__init__.py` with `API = <int>`,
  ≥1 `tests/test_<id>_*.py`; no `.py` over 300 lines, facade ≤150; stdlib only; no module imports another's internals;
  `state.py`, `update.py`, `setup.py`, `hooks/*.py` import only `modules.<id>`; test basenames unique across `tests/`
  and `modules/*/tests`. `tests/test_modules_layout.py::test_every_module_follows_template`,
  `::test_callers_import_only_facades`, `::test_basenames_unique`. S2.
- **M3 Selection** (M-O2). `run_suite.py --modules none|auto|all|only`; `none` (default) runs exactly today's
  selection; `auto` = modules with a path in `sensors.py --root . diff --format json`, all of them (with a line saying
  so) when the diff is unavailable; each module file runs with its own `tests/` as start; a FILE under
  `modules/*/tests` is accepted; a duplicate basename exits 2. `tests/test_run_suite.py::test_modules_none_is_todays_selection`,
  `::test_auto_touched_only`, `::test_auto_without_diff_runs_all`, `::test_module_file_arg_own_start`. S2.
- **M4 CI and e2e** (M-O2). `e2e_command` unchanged. `.github/workflows/modules.yml` runs `--modules only` on every push
  and PR, Python 3.11–3.13. `test_modules_layout.py::test_ci_runs_modules_on_every_push`. S2.
- **M5 Install** (Q5). npm `files` gains `modules/`; `installShared` (`bin/riskrails.js:771-789`) copies it to
  `<home>/riskrails/modules` atomically (`.new` then rename) without `tests/`, `_template/`, `__pycache__`, on both
  runtimes (`:1078`, `:1338`); the dry run lists it. `tests/test_install_routes.py::test_modules_installed_without_tests`,
  `tests/test_install_dry_run.py::test_lists_modules`. S4.
- **M6 Protection.** `"(^|/)\\.(claude|codex)/riskrails/modules/"` joins `protected_config_patterns`
  (`hooks/ai-path-guard-defaults.json`). `tests/test_ai_path_guard.py::test_installed_modules_protected` (golden
  re-recorded). S4.
- **M7 Registry** (Q2). Discovers `modules/*/module.json`, skipping dirs starting `_` or `.`, sorted by id; duplicate
  setting id → `RegistryError`; a `can_disable: true` module gets a synthesized `modules.<id>.enabled`
  (`module_toggle`, v1, not required). `test_settings_registry.py::test_skips_template_and_sorts`,
  `::test_duplicate_setting_id_refused`, `::test_can_disable_synthesizes_toggle`. S3.
- **M8 Shipped manifests** (Q8, Q12). `modules/settings` (`"settings": []`), `modules/dialog` (`dialog.enabled`),
  `modules/verification` (`verify_command`, `e2e_command`), all `can_disable: false`; each a manifest and a facade
  ≤20 lines; no existing code moves into them. `test_settings_registry.py::test_shipped_modules_not_disableable`. S3.
- **M9 Test-only module** (Q12, M-O5). `tests/fixtures/modules/sample_optional/` (manifest `can_disable: true`, a
  facade, its own test) is loaded only through an injected `DirectoryManifestSource`; never installed, never seen by
  the default registry. `test_settings_registry.py::test_sample_optional_only_through_injected_source`,
  `tests/test_install_routes.py::test_fixture_modules_not_installed`. S3.
- **M10 Stores** (Q8). Allowlist in code: `json_key` only for `.ai/policies/dialog.json` and `.ai/policies/settings.json`;
  `testing_field` only for the Verification fields (`sensors.TESTING_FIELDS`, `skills/ai-task/sensors.py:207-209`),
  read by `sensors.read_commands`' rule. Writes atomic, one key or line, column padding kept; a missing file or line is
  refused. `test_settings_stores.py::test_locator_outside_allowlist_refused`, `::test_write_changes_only_one_key_or_line`;
  `tests/test_settings_contract.py::test_dialog_reader_agrees_with_both_dialog_policy`,
  `::test_testing_reader_agrees_with_sensors`. S3.
- **M11 Confirmations** (Q3). `JsonConfirmationStore`: missing or unreadable = nothing confirmed; unknown keys kept;
  record `{v, value, by, via ∈ dialog|terminal|unattended, pick, at}`.
  `test_settings_confirmations.py::test_unreadable_reads_as_none`, `::test_preserves_unknown_keys`. S3.
- **M12 Audit** (Q3, Q10). States `unset`, `new`, `updated`, `drifted`, `no_value`, `confirmed`; `missing()` = required
  ids not `confirmed` (drift included, Q10). `test_settings_audit.py::test_state_table`, `::test_drifted_is_missing`. S3.
- **M13 Disable flag** (Q7, M-O5). `module_enabled()` always True; `false` prints one stderr warning "disabling not
  implemented yet"; `false` on a `can_disable: false` module is noted "cannot be disabled; ignored".
  `test_settings_flags.py::test_disable_flag_only_warns` (on `sample_optional`), `::test_core_module_flag_ignored`. S3.
- **M14 Extraction: questions file** (M-O4, C3). The pure questions-file code of `state.py` — `read_lines`,
  `question_lines`, `with_preamble`, `parse_answer_body`, `parse_questions`, `is_pending`, `one_line`, `answer_line`,
  `question_block`, `render_prose`, `render_md`, `render_questions`, `parse_prose`, `prose_id`, `unquote`,
  `parse_assignment` (`skills/ai-task/state.py:1187-1513`, `question_lock` and `write_questions` stay) — moves into
  `modules/questions/` as `QuestionsParser`, `QuestionsRenderer`, `AnswerParser`; `state.py` keeps the same names as
  one-line wrappers over the facade. Errors still go through `die` (the module raises `QuestionsError`, the wrapper
  turns it into `die`). Characterization first: `modules/questions/tests/test_questions_characterization.py` pins
  parse → render round trips and every `die` message on today's tree, then passes unchanged after the move; the whole
  existing suite is green before and after. S5.
- **M15 Extraction: three-way merge** (M-O4, C3). The pure merge code of `update.py` — `closest`, `text_ratio`,
  `merge_text`, `flatten`, `json_score`, `merge_json`, `dump_json`, `leaf_changes` (`skills/project-update/update.py:359-442`)
  and the pure core of `three_way` (`:876-930`, file I/O stays in `update.py`) — moves into `modules/merge/` as
  `TextMerger`, `JsonMerger`; `update.py` keeps wrappers. Characterization first:
  `modules/merge/tests/test_merge_characterization.py` on today's tree; `tests/test_merge_migration.py` and
  `tests/test_project_update.py` green before and after. S6.
- **M16 Sizes** (M-O4). After S5 and S6, `state.py` and `update.py` are each smaller by the moved lines minus the
  wrappers; `tests/test_modules_layout.py::test_extracted_functions_are_wrappers` checks each moved name is a wrapper
  of ≤3 lines. S5, S6.
- **M17 ADR and ROADMAP** (M-O6). `docs/sdlc/adr/0001-small-oop-modules.md` (*proposed*), the `ROADMAP.md` additions.
  doc_tests. S1.

## Design

### Layout

```
modules/
  README.md                 the rules of M2 and the copy steps (≤80 lines)
  __init__.py               empty
  _template/                module.json, __init__.py (API = 1), core.py, tests/test_template_core.py
  settings/                 spec.py registry.py stores.py confirmations.py audit.py flags.py __init__.py tests/
  dialog/                   module.json, __init__.py (≤20 lines), tests/
  verification/             module.json, __init__.py (≤20 lines), tests/
  questions/                parser.py renderer.py answers.py __init__.py tests/   (extracted, S5)
  merge/                    text.py json_merge.py __init__.py tests/              (extracted, S6)
tests/fixtures/modules/sample_optional/   test-only, never installed (M9)
```

### `settings` components

| File | Responsibility |
|---|---|
| `spec.py` | `SettingSpec`, `ModuleManifest` (frozen dataclasses, `ModuleManifest.load`), `ManifestError`, `ManifestSource` Protocol, `DirectoryManifestSource(dir)` |
| `registry.py` | `SettingsRegistry(source)`: `.specs()`, `.get(id)`, synthesized toggles |
| `stores.py` | `ValueStore` Protocol, `JsonKeyStore`, `TestingFieldStore`, `StoreFactory` (type → class + allowlist; a new store is a new class) |
| `confirmations.py` | `Confirmation`, `ConfirmationStore` Protocol, `JsonConfirmationStore(root)` |
| `audit.py` | `SettingStatus`, `SettingsAudit(registry, factory, confirmations)`: `.statuses()`, `.missing()` |
| `flags.py` | `ModuleFlags`: `module_enabled` |
| `__init__.py` | the facade, the only wiring point; services depend on Protocols; tests inject fakes |

Part 2 adds `options.py`, `apply.py`, `notice.py` to this module.

### Callers and imports

Callers find the package with `for base in (R, R/riskrails): if base/modules/__init__.py exists → sys.path.insert(0, base)`,
R being the caller's tree root (`STATE_PY`'s for hooks); no environment override. After S5/S6, `state.py` and
`update.py` **require** `modules/questions` and `modules/merge`: a missing package is an `ImportError` at start-up,
which the installer prevents by shipping `modules/` in the same atomic step (M5) and the plugin route by carrying the
repo tree.

### Module tests

`modules/<id>/tests/test_<id>_*.py`; `tests/` is not a package; each file puts the repo root on the path and imports
`modules.<id>` (and may import its own internals). Contract tests against the monoliths live in `tests/`
(`test_settings_contract.py`), so module tests never import `state.py`. Selection M3, CI M4; `verify_command` gains
`--modules auto` only through human step G1.

### Extraction method (S5, S6 — the template for every later move)

1. Characterization test in the target module's `tests/`, run on today's tree, green.
2. Move the code verbatim into classes; the old names become wrappers; no signature, message or exit code changes.
3. The characterization test and the whole existing suite green, unchanged.
4. One extraction per task (C3), reviewed as a refactoring: "behaviour unchanged" is the only claim.

### Alternatives rejected

1. **Extract the decision ledger (`state.py:2319-3050`) first.** It is the R36 gate's core and has a second copy in
   `hooks/guard/dialog.py`; moving it while part 2 changes it would mix the refactor with the feature.
2. **Extract profile detection (`state.py:616-800`).** It reads runtime credential files; a first extraction should not
   touch secrets handling.
3. **Share `modules/questions` with `memory_compact.py` now.** `memory_compact.py:20` must not import state.py and has
   its own `parse_questions_lines` (`:76`); unifying the two is a later refactoring row, not this one.
4. **Sub-packages per skill / a pip package / growing the monoliths.** Rejected by Q5.
5. **`sample_optional` shipped under `modules/`.** It would appear in every project's dialog as a toggle that does
   nothing (Q12 asked for a test-only module).

### ADR 0001 (`docs/sdlc/adr/0001-small-oop-modules.md`, from `ai/templates/architecture-decision.md`)

Status *proposed*, 2026-10-30, decider Ivan Kakurov. **Context:** `state.py` 5230 lines, `update.py` 1972; R36 alone
added `state.py:2300-2990`; readers copied across hooks and state.py (`hooks/guard/dialog.py:67`, `state.py:2319`).
**Options:** keep the monoliths; sub-packages per skill; one pip/npm package; shared `modules/<id>/` (chosen).
**Decision:** new functionality is a `modules/<id>/` with `module.json`, `__init__.py` as the only import surface
(`API` int), one responsibility per class behind Protocols, stdlib only, files ≤300 lines, tests in
`modules/<id>/tests/` run by verify when the diff touches the module, by CI on every push, never by e2e; e2e tests the
end result only; callers import facades only; installed to `<home>/riskrails/modules`. Existing code moves by the
extraction method above, one module per refactoring task (C3). **Consequences:** features stop growing the monoliths;
per-module tests / duplicate readers until each move; plugin cache and `<home>` can skew; the monoliths now depend on
`modules/` being installed. **Revisit when** the first three moves are done, a module needs a non-stdlib dependency,
or install skew causes an incident.

### ROADMAP.md additions

> **Next — small modules (ADR 0001).** Decided 2026-10-30 (`docs/sdlc/adr/0001-small-oop-modules.md`; intent
> project-settings-dialog Q5, Q13): all functionality moves out of `state.py`, `update.py` and `setup.py` into small,
> light, object-oriented `modules/<id>/` packages — one responsibility per class, a facade as the only import, a
> manifest, and their own functional tests; the end-to-end suite tests only the end result. One module per
> refactoring task, never mixed with a feature (C3). Done first: `questions`, `merge`. Next (OQ-M1 = A, 2026-10-31):
> the dialog and consent readers (two copies today; stdlib only, reachable from hooks under `python3 -I -S` by the
> module `sys.path` probe), then the verification commands (`sensors.read_commands`, `setup.py verify` and survey),
> weight, the journal, memory (and `memory_compact.py`'s own questions parser).

§2 row: `| Module disable | task | modules.<id>.enabled (settings.json) and can_disable (manifest) are read but do nothing: false prints "disabling not implemented yet"; no shipped module is disableable; tests/fixtures/modules/sample_optional proves the flag | intent project-settings-dialog Q7, Q12 |`

### Delivery order — three tasks (C3)

| Task | Step | Files | Weight |
|---|---|---|---|
| **T1 framework + settings** (feature) | S1 | `docs/sdlc/adr/0001-small-oop-modules.md`, `ROADMAP.md` | light |
| | S2 | `modules/__init__.py`, `modules/README.md`, `modules/_template/**`, `tests/test_modules_layout.py`, `tests/run_suite.py`, `tests/test_run_suite.py`, `.github/workflows/modules.yml` | guarded |
| | S3 | `modules/settings/**`, `modules/dialog/**`, `modules/verification/**`, `tests/fixtures/modules/sample_optional/**`, `tests/test_settings_contract.py` | guarded (no caller) |
| | S4 | `package.json`, `bin/riskrails.js`, `hooks/ai-path-guard-defaults.json`, `tests/test_install_routes.py`, `tests/test_install_dry_run.py`, `tests/test_ai_path_guard.py` + golden | full — behaviour 2: npx installs `modules/` |
| **T2 extract questions** (refactoring) | S5 | `modules/questions/**`, `skills/ai-task/state.py`, `tests/test_modules_layout.py` | guarded, `--kind refactoring` |
| **T3 extract merge** (refactoring) | S6 | `modules/merge/**`, `skills/project-update/update.py`, `tests/test_modules_layout.py` | guarded, `--kind refactoring` |

Each task: `verify_command` once to the end, then `e2e_command` once. Human step after T1: **G1** `testing.md` —
`verify_command` gains `--modules auto`, a Touching row `modules/** → modules/<id>/tests/`.

## Interfaces

**`module.json`** (verification; dialog has `dialog.enabled`, settings has `"settings": []`):

```json
{"id":"verification","version":1,"title":"Verification commands","can_disable":false,
 "settings":[{"id":"verify_command","version":1,"kind":"command","required":true,"header":"Verify",
   "title":"the fast suite every task runs, e2e excluded","allow_none":false,
   "store":{"type":"testing_field","field":"verify_command"}},
  {"id":"e2e_command","version":1,"kind":"command","required":true,"header":"E2E",
   "title":"the end-to-end suite, run once at the end of a task","allow_none":true,
   "store":{"type":"testing_field","field":"e2e_command"}}]}
```

Dialog's setting: `{"id":"dialog.enabled","version":1,"kind":"bool","required":true,"header":"Dialog","default":true,"store":{"type":"json_key","file":".ai/policies/dialog.json","key":"enabled"},"labels":{"true":"On — pick commit, push and approval in the dialog (recommended)","false":"Off — the human runs them in a terminal"}}`.

**`.ai/policies/settings.json`** (written by part 2; read here): `{ "version": 1, "confirmed": {}, "modules": {} }`,
a confirmation `{"v":1,"value":true,"by":"Ivan Kakurov","via":"dialog","pick":"C31","at":"2026-10-30T15:02:11Z"}`.

**Facade, `modules/settings/__init__.py`** (`API = 1`, plain data):

```python
def status(root: str) -> list[dict]      # {id,version,module,title,required,state,current,confirmed,note}
def missing(root: str) -> list[str]      # required, state != confirmed; [] when .ai/VERSION < 12
def pending(root: str) -> list[str]      # state in unset|new|updated|drifted
def module_enabled(root: str, module_id: str) -> bool
```

**Facades of the extractions** (`API = 1`): `modules.questions` — `parse(lines, src) -> dict`,
`render(questions, fmt) -> list[str]`, `parse_prose(text) -> dict`, `parse_assignment(text) -> tuple`;
`modules.merge` — `merge_text(base, ours, theirs) -> tuple[str, bool]`, `merge_json(base, ours, theirs) -> tuple[dict, list]`,
`leaf_changes(a, b) -> list`. Exact signatures follow the moved functions, unchanged.

**CLI.** `run_suite.py … --modules none|auto|all|only` (default `none`). Nothing else changes.

## Policy conformance

- **C1** No user-visible behaviour changes: `--modules` defaults to today; extractions keep every name, message and
  exit code; `settings` has no caller.
- **C2** No bugfix; the characterization tests pin legacy behaviour before it moves.
- **C3** Three tasks: one feature (T1), two refactorings (T2, T3), each alone.
- **C4** Each step names its files.
- **C5** Untouched: nothing here commits, approves or opens a dialog.
- **C6** Only S4 (install) is behaviour 2 for user projects: full mode, STRONG review.
- **CLAUDE.md** "Never mix a refactoring with a feature" (C3); "a BLOCKER closed only with a test" — every requirement
  names one.
- **`.ai/policies/testing.md`** unchanged until G1; pylint 10.00/10.
- **ADRs** none exist; ADR 0001 is the first.

## Open questions

- none open. **OQ-M1** (owner: Ivan Kakurov) — after T2/T3, `setup.py` (547 lines) or the dialog readers? —
  **closed 2026-10-31: A, the readers** (see Decisions taken); the readers are duplicated today and `settings` would
  add a third copy (concern 3), while `setup.py` is duplicated nowhere. `setup.py` is the move after them.

## Flagged concerns

### A. Policy vs intent

1. **"Only settings as a new module"** (Q13) vs the shipped `dialog` and `verification` manifests and the extracted
   `questions` and `merge`: `dialog` and `verification` are declarations (a manifest and a ≤20-line facade) the
   registry needs, and `questions`/`merge` are moves of existing code, not new functionality. If Q13 meant literally
   one directory, M8 collapses into `modules/settings/manifests/*.json`.
2. **The disable flag is never visible in a real project** (Q12): only the test-only module is disableable, so the
   "(not effective yet)" toggle of Q7=B shows in no real dialog until the first optional module ships.

### B. Policy vs policy, or inside this design

3. **C3 duplication.** `settings` adds a third `dialog.json` reader and a second testing-field reader/writer;
   `test_settings_contract.py` pins them until the readers move. Found, not fixed: `setup.py verify_value`
   (`skills/rr-setup/setup.py:307-317`) keeps a trailing comment, `sensors.read_commands` strips it; the module
   follows sensors.
4. **The monoliths now depend on `modules/`.** A half-installed tree (old `modules/`, new `state.py`) breaks
   start-up; M5's atomic copy and the facade `API` int guard it, and a wrapper raises a clear `ImportError` message.
5. **Q4 "CI on every push"** vs `.github/workflows/tests.yml:7-9` (main only): a separate `modules.yml`.
6. **`testing.md` is frozen during a task**: `--modules auto` waits for G1.

### C. Requirements that cannot be fully satisfied

7. **"e2e only the end result"** holds for module tests; the existing `tests/` suites still test inside the
   monoliths until each move.

### D. Risks

8. **Hidden callers of the moved names** (`skills/ai-task/memory_compact.py` has its own parser; tests may reach in):
   wrappers keep every name, and T2/T3's whole-suite run is the proof.
9. **pylint** `too-few-public-methods` on Protocols: inline disables with the reason.

### S. Security and data protection

10. No environment override of the modules dir; the store allowlist is in code: a forged manifest cannot redirect
    writes to `weight.json` or `path-guard.json`.
11. Installed modules are protected (M6); without it, editing `<home>/riskrails/modules` would bypass the guards
    once part 2 routes policy writes through it.
