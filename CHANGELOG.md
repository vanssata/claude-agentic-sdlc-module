# Changelog

Notable changes to RiskRails (npm package `riskrails`). Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

## [4.2.0] — 2026-11-13

A task seal that changed many files fits one line again (#74), the agent record is local by default, and a version bump merged to `main` is tagged, published and released by CI.

### Fixed
- `memory export` wrote the seal of a task that changed many files over `LINE_MAX_BYTES`, which `memory redact` could not reach and which blocked every push (#74). A seal whose `changes` list makes it too long now keeps the longest prefix of `changes` that fits and says so in `changes_truncated {rows, added, deleted}` and `truncated`; only `changes` is capped, so a seal whose other fields (a huge `files` list) are over the limit still needs a redact. An over-long line already in a package is read and kept, so V1 names it with the `state.py memory redact <rid> --field <field>` that shortens it.

### Changed
- The agent record is local by default: a new project's `.gitignore` ignores `.ai/memory/` and `.ai/reports/`; `.ai/project/` stays in git. The record is shared exactly when git does not ignore `.ai/memory/`. `state.py memory enable --share git` (the human's own terminal, no dialog route) opts in and installs the pre-push hook; `--share local` opts out. For a local record the pre-push hook exits 0 and `memory verify --fresh-clone` exits 2; `--range` and `--tree` (the CI form) still validate what the checked commits carry.
- **Upgrade:** `/rr-setup --update` appends the two ignore lines to an existing project, unless the negations are already there, and prints a hint. Files git already tracks stay tracked, and while the ignore lines are in, the pre-push hook no longer checks pushes of them: untrack them with `git rm -r --cached --ignore-unmatch .ai/memory .ai/reports` (yours to run; on every other clone, copy the two directories aside before pulling that commit), or keep sharing with `state.py memory enable --share git`.

### Added
- Automatic release: a version bump (`package.json`) merged to `main` is tested, tagged `vX.Y.Z`, published to npm and released on GitHub, with this file's section for the version as the notes (`tools/changelog-section.py`; a missing or empty section fails the release). Pushing a tag by hand still works. The header of `.github/workflows/npm-publish.yml` says how to recover after a red verify.

## [4.1.0] — 2026-11-11

The installer asks with arrow-key menus on a terminal, and `/rr-setup` asks its choices — project memory and its SQLite index among them — in one dialog.

### Added
- On a terminal the installer asks each question as a menu — runtime, plan, Fable, context, statusline, Codex plan — with the proposal highlighted: the detected or recorded runtime, plan, statusline and Codex plan, and the defaults Fable `yes` and context `default`; ↑/↓ (or k/j), Home/End or 1–9 move, Enter confirms, Esc, q or Ctrl-C stop with nothing written (exit 130). A flag skips its menu; `--yes` or no terminal asks nothing and prints what 4.0.1 printed; `RISKRAILS_MENU=off` (or `TERM=dumb`) brings back the typed plan question. New `bin/menu.js`, no npm dependency.
- `/rr-setup` asks its choices in one dialog before any work: runtime, survey depth, `verify_command` and project memory, only the ones not set yet; `/rr-setup --options` asks them all again. With the dialog off, an unattended run or an unverified Codex tool the questions stay prose. New: `setup.py options --json|--open [--all] [--skip KEY]`, and `state.py decision open --kind setup --spec FILE|-`, which opens all of a round's decisions or none; settling one prints `SETUP_PICK key=value`.
- Project memory from setup: off, packages, or packages with the SQLite index. A picked `state.py memory enable` runs through the dialog route — verbatim, once, inside the pick window, in the same session — and prints `memory: via dialog (consent C<n>, decision D<n>)`. `disable`, `cleanup`, `pack`, `redact` and `migrate --move-logs` have no dialog route.
- `scaffold-ai.sh --runtime none`: `.ai/` and its `.gitignore` lines, no instruction file.

### Changed
- On a terminal with the menu on and no detected Claude plan, Enter installs the highlighted plan (`team-pro` for a Team org, else `pro`) instead of exiting. Without a terminal, or with `RISKRAILS_MENU=off`, it still exits as before.
- The consent-label allowlists (`rr_state/labels.py`, `hooks/guard/dialog.py`) accept `state.py memory enable [--author S] [--period P] [--index none|sqlite]` and no other `memory` verb; `docs/local-memory.md`, the `safety.md` template and the R36 spec say so.

## [4.0.1] — 2026-11-11

The first 4.0 on npm. `v4.0.0` was tagged but never published: its release verify failed on a clean checkout. Everything under 4.0.0 below applies; install `npx riskrails@4.0.1`.

### Fixed
- Three fixture files of `tests/fixtures/regenerate/v3.1.0-edited/` were hidden by the fixture's own `.gitignore` and never committed, so `test_regenerate` failed on a fresh clone. They are tracked now, and `tests/test_fixtures_tracked.py` fails when any fixture file is ignored by git.

## [4.0.0] — 2026-11-04 [not published]

Breaking. riskrails regenerates a project's files from the plugin and converts nothing. **Run `/rr-setup --update` in each project right after installing 4.0** (install 4.0.1: this version was not published): until then the project's old shapes are not read, so a project weighs without its `domain.modules` (lighter), finds no `verify_command`, and a task still in the old `current.json` is not scope-guarded. Reinstall both routes you use, `npx riskrails@4.0.0` and the plugin install: they are separate copies.

A tree that still holds an old shape (`current.json` without `state.json`, `risk-tiers.json` without a weight table, an old `claude-agentic` or `Codex-agentic` marker) is refused (`KEPT_UNREADABLE`, exit 6, naming the file); any other older tree is regenerated without the conversions it missed. So a project last updated before 3.1.0 goes through 3.1.0 first: install `npx riskrails@3.1.0`, run `/rr-setup --update` with it, then install 4.0.0 and run it again.

### Removed
- `/rr-setup --adopt`, `adopt.py`, `adopt-map.json` and the `--mode`, `--tool`, `--split-request`, `--split`, `--diff` and `--cleanup` flags of `update.py` (they exit 2). A project's own toolbox is no longer inventoried into `policies/toolbox.md`.
- The migrations `0001` to `0011` and the schema ladder. `.ai/VERSION` is 12.
- The one-version fallbacks: the `current.json` reads, the `CLAUDE_AGENTIC_*` environment names, the old `claude-agentic` home and markers, `dependency_instruction_patterns`, the runtime-gate `LEGACY` and `--as` names and the `CLAUDE_FABLE_GATE*` variables, and the claude-routing / "Model allocation" block migration.
- The alias skills `ai-status`, `sdlc-intent`, `sdlc-plan` and `sdlc-spec`, and the `SKILL.md` of `ai-task`, `project-update`, `ai-init`, `project-init`, `usage-report` and `ai-audit` (their code and templates stay: the `rr-*` skills read them). Use `/rr-setup`, `/rr-setup --update`, `/rr-setup --audit`, `/rr-build`, `/rr-spec`, `/rr-plan`, `/rr-status` and `/rr-status --cost`. The installer moves `skills/{status,ai-status,sdlc-intent,sdlc-plan,sdlc-spec}` out of the home into `backups/<date>/skills/` (the dry run prints a `retire:` line first).
- `skills/project-update/migrations/**` from the weight hints.

### Changed
- `/rr-setup --update` regenerates: a file that is a version the plugin once shipped is replaced; an edited one is a `regenerate?` row that waits for `--confirm-delete` (exit 5, `CONFIRM_REFUSED`, without a human), and its original is copied to `.ai/reports/project-update-<date>/original/` first.
- The weight is the plugin's table plus `.ai/policies/weight.project.json`, the project's own changes laid over it; `weight.md` is rendered from both. `.ai/policies/verification.md` is the only source of `verify_command`, `step_test_command` and `e2e_command`. A project that still has the mixed `weight.json` and `testing.md` gets the two files split out of them once, by the first `/rr-setup --update`.
- The shared stubs `ai/workflows/{feature,bugfix,hotfix,investigation,refactoring}.md` and `ai/agents/manager.md` are removed; the shared set is 25 files.
- The template history is rebuilt; the README test count and the router template (`weight.md` and `weight.project.json`) follow.

### Kept
- The installer's fable-gate sites stay: the statusline wrapper rewrite, the replacement of fable-gate hook entries by runtime-gate, and the retirement of the `fable-gate.py` shim. A settings file written before the runtime gate would otherwise keep a hook that points at a retired file, an error on every tool call. The `fable-gate=` label of the dry run stays with them.

## [3.2.2] — 2026-11-02

### Changed
- CI and release workflows use `actions/checkout@v7`, `actions/setup-node@v7` and `actions/setup-python@v7`, which run on Node.js 24 (GitHub deprecated Node.js 20 for actions). Nothing shipped in the package changed.

## [3.2.1] — 2026-11-02

3.2.0 was tagged but never published: its release job failed before the publish step. 3.2.1 is the first published version with the changes listed under 3.2.0.

### Fixed
- The full test suite is green again on Python 3.12, the release Python. Three state.py tests depended on the Python version or the checkout path: the partition's value hashes (now `ast.unparse`), argparse's usage wrapping, and the byte offset `ledger_pos`. Nothing shipped changed.

### Changed
- The smoke gate on every pull request also runs `test_state_layout.py` and `test_state_characterization.py` on Python 3.11, 3.12 and 3.13.

## [3.2.0] — 2026-11-01 (not published)

### Changed
- The plugin's two-line statusline replaces your statusline command by default. The replaced command is printed, kept in `~/.claude/riskrails/statusline.json` and in the dated settings.json backup; `--statusline own` restores it once, on the run that switches to own.

### Fixed
- `decision open` names an open twin (DECISION_DUPLICATE) before the four-question limit, so a twin at the limit takes one round trip, not two; `update --apply` reads a too-deep `migration.json`, and a too-deep policy unchanged since install, as malformed instead of tracebacking.
- Installer: `--statusline own` restores the replaced command only on the switch to own; a `--then` you removed by hand no longer comes back on the next update.
- Installer: a malformed `--then` tail is no longer recorded over the command already kept in `riskrails/statusline.json`.
- Path guard: `.claude/riskrails/statusline.json` is protected config — an agent's Write or Edit is denied, in a task or not.
- Statusline: a NaN or infinite percentage, cost or context size skips that part only; the rest of both lines is still printed.
- Quota record: a NaN or infinite weekly or 5-hour percentage is no reading; it is no longer stored in `runtime-gate.json`.
- Dialog: a second open decision with the same question text is refused in every opener, not only `decision open` — a repeated `state.py ask` stays on the `[Answer]:` file route instead of opening a twin the dialog cannot answer. A twin another session opened names `decision fallback --id` instead of saying to send it.
- `/rr-setup --update` and `--adopt`: a JSON file nested too deeply to parse takes the same path as malformed JSON (skipped, a conflict, or a refusal that names the file) instead of a traceback.

## [3.1.0] — 2026-10-30

Project schema 10 → 11: run `/rr-setup --update` after upgrading.

### Changed
- `/rr-setup --update` re-renders `.ai/policies/weight.md` from `weight.json` instead of merging it — no more conflict on every update.
- `/rr-setup --update` proposes cleanup of closed-task logs and stale task records (`[cleanup]` rows); nothing is deleted without `--apply --confirm-cleanup NAME`.
- The SDLC `TEMPLATE.md` files (intent, spec, plan, ADR) come from the plugin; a project's own copy still wins.
- `testing.md` gains `bite_codes` (default `1`) so `verify --expect fail` works with pytest, phpunit, cargo.
- CI in two tiers: smoke on pull requests, the full suite on release tags; lint fails on errors or a score under 9.9.
- Texts speak of modes instead of T0–T6 and name the `/rr-*` commands. Python 3.11 is the stated floor.

### Fixed
- Path guard: human-only `--by` forms (`verify`, `review`, `reject`, `start --mode light`) and `--confirm-cleanup` are denied to the agent; `--mode` abbreviations and a leading BOM no longer slip past.
- `state.py`: the documents rule, light weighing of non-document globs, atomic writes on abandon and archive, `status` re-reading questions.
- `update.py`: router sections stay in place, symlinked targets are re-checked before delete, bad `RISKRAILS_NOW` exits 2.
- `sensors.py` handles a project below the git top level; `setup.py` skips links that resolve outside the project.
- The update notice records `checked_at` before fetching and caps the read.
- Deterministic CI: directory order, bash 5.2 output and timing budgets (`AI_TIMED_FACTOR`).

### Removed
- `.ai/policies/risk-tiers.json` and `risk-tiers.md`. Migration 0011 proposes deleting your copies (originals kept under `.ai/reports/project-update-<date>/original/`); confirm each with `--apply --confirm-delete NAME` in your own terminal.

## [3.0.1] — 2026-10-30

- Releases run from a `vX.Y.Z` tag: tests, npm publish with provenance, GitHub Release; `tools/sync-version.py` keeps the manifests in step.
- A SessionStart notice reports a newer `riskrails` on npm.
- pylint errors and fresh-checkout test failures fixed.

## [3.0.0]

- Renamed from `claude-agentic` to `riskrails`.
- Risk tiers replaced by the weight and three modes (light, guarded, full); `/ai-*` and `/sdlc-*` become `/rr-*` (old names kept as aliases).
- Guards in one Python process; task state in `.ai/state/state.json`. See "Upgrade to 3.0" in the README.

[4.2.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v4.1.0...v4.2.0
[4.1.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v4.0.1...v4.1.0
[4.0.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.2.2...v4.0.1
[4.0.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.2.2...v4.0.0
[3.2.2]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.2.1...v3.2.2
[3.2.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.0.1...v3.1.0
[3.0.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v2.0.2...v3.0.1
