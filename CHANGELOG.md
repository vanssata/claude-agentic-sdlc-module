# Changelog

Notable changes to RiskRails (npm package `riskrails`). Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

## [Unreleased]

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

[3.2.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.2.0...v3.2.1
[3.2.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.1.0...v3.2.0
[3.1.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.0.1...v3.1.0
[3.0.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v2.0.2...v3.0.1
