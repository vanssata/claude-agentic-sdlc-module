# Changelog

Notable changes to RiskRails (npm package `riskrails`). Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [SemVer](https://semver.org/).

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

[3.1.0]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v3.0.1...v3.1.0
[3.0.1]: https://github.com/vanssata/claude-agentic-sdlc-module/compare/v2.0.2...v3.0.1
