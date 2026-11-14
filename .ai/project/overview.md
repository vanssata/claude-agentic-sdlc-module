# Project overview

Labels: KNOWN FACT (file:line) · INFERENCE (what it rests on) · UNKNOWN (what would answer it) · RISK (what could go wrong). Surveyed 2026-11-14 (full depth, `/rr-setup`).

## What this system does

- KNOWN FACT: `riskrails` 4.2.0 is a plugin for Claude Code and Codex. It ships hooks that guard git, protected paths and a task's scope, skills that drive a weight-based task pipeline (plan → build → verify → review → ship), agent templates, and a Python state machine (`package.json:2-4`, `skills/ai-task/state.py`).
- KNOWN FACT: Two install routes: the npm bin `riskrails` (`bin/riskrails.js`, 1578 lines), which writes `~/.claude` and `~/.codex`, and the plugin manifests (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `hooks/hooks.json`, `hooks/codex-hooks.json`).
- KNOWN FACT: This repository runs its own pipeline: `.ai/` (schema stamp `.ai/VERSION` = 12), `.ai/policies/`, `docs/sdlc/`.

## Stack

- KNOWN FACT: Python 3 (stdlib only; hooks run as `python3 -I -S`, `hooks/hooks.json:21`). CI tests 3.11–3.13; 3.10 is excluded because the suite is red there (`.github/workflows/tests.yml:25`).
- KNOWN FACT: Node ≥ 18 for the installer only, with no npm dependencies (`package.json:11-13`).
- KNOWN FACT: Shell: `hooks/project-scaffold.sh`, `hooks/lib/ai-hook-common.sh`, `skills/ai-init/scaffold-ai.sh`, `install.sh` (a wrapper that prints the npx line and exits 2).

## How it runs

- KNOWN FACT: In a user's session, as hooks on PreToolUse / PostToolUse / Stop / SessionStart / UserPromptSubmit / PreCompact / Subagent* events (`hooks/hooks.json`, `codex/hooks.json`). The skills shell out to `python3 <home>/skills/ai-task/state.py`.
- KNOWN FACT: Release: a version bump merged to `main` triggers `.github/workflows/npm-publish.yml` (detect → verify → publish, with provenance, environment `npm`).

## Repository layout

| Path | Holds |
|---|---|
| `hooks/` | runtime hooks (`ai-guard.py`, `runtime-gate.py`, `context-guard.py`, `dialog-gate.py`, `cap-large-read.py`), `hooks/guard/` (the guard library), git pre-push `memory-pre-push.py` |
| `skills/` | one directory per skill; `skills/ai-task/` holds `state.py`, `rr_state/` (the state machine), `weight.py`, `sensors.py`, `memory_*.py` |
| `skills/project-update/` | `update.py`, `rr_update/`, `render_instructions.py`, `history/blobs/` (generated) |
| `ai/` | the shared policy tree, installed to `~/.claude/riskrails/ai/` |
| `agents/` | agent templates (`*.md.tmpl`); `agents/superseded/reviewer.md` is still an installer input |
| `bin/` | `riskrails.js` (installer), `menu.js`, `claude-1m` |
| `profiles/`, `scripts/` | plan tables (model ladder per plan) and the Codex config merge/render scripts |
| `tests/` | 65 `test_*.py`, `run_suite.py` (parallel runner), harnesses, `fixtures/` (golden: `guard-characterization/golden.txt`) |
| `tools/` | `build-template-history.py`, `golden-diff.py`, `sync-version.py`, `changelog-section.py`, `state-partition.py`, `benchmark-memory.py`, `journal-summary.py` |
| `docs/` | user docs, `docs/sdlc/` (constitution, intent, specs, plans) |
| `files/`, `site/` | git-ignored: evidence bundles and the gh-pages worktree |

## Team and process context

- INFERENCE: one maintainer (all commits by one author; `package.json:9`). Releases go through PRs to `main`.
- UNKNOWN: whether `main` has branch protection and required checks. Answer: `gh api repos/vanssata/claude-agentic-sdlc-module/branches/main/protection`.

## Unknowns

- UNKNOWN: whether README's "1423 tests" is current. Running `verify_command` and counting answers it.
- UNKNOWN: whether stale `__pycache__` files for removed modules (`hooks/__pycache__/fable-gate.cpython-314.pyc`, `codex-model-gate…`) can still be picked up. They are untracked (`git ls-files` holds no `.pyc`), and hooks run with `-I`.
