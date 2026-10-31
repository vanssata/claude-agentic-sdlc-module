# Intent: riskrails regenerates its own files — no adopt, no migrations, no legacy fallbacks

Decided by Ivan Kakurov on 2026-10-31 (Q25, Q26 of `docs/sdlc/intent/small-oop-modules.questions.md`).
Input for `/rr-spec` → `docs/sdlc/specs/riskrails-regenerate-not-migrate.md`. Not a refactoring:
behaviour is removed (C3), so it is its own spec, plan and task, never mixed into a
small-oop-modules WP.

## Problem

The plugin carries code whose only job is the past: `--adopt` translates foreign AI-tool
layouts (`skills/project-update/adopt.py`, 2 219 lines; `adopt-map.json`), eleven migrations
rewrite an older riskrails `.ai/` in place (`skills/project-update/migrations/0001–0011`,
1 063 lines), and fallbacks keep old names alive (`CLAUDE_AGENTIC_TEST`, `LEGACY_REVIEW_LINE`,
the legacy `current.json`, the deprecated alias skills, …). Every change has to keep them
working; WP2 and WP3 of small-oop-modules would have split 2 219 + part of 2 146 lines of it.

## Proposed outcome

- `--adopt` (and `/rr-setup --adopt`) does not exist: code, map, flag, skill text, tests,
  fixtures (`tests/fixtures/adopt/`, `tests/test_project_adopt.py`, the adopt parts of
  `tests/test_migration_0006.py`, `tests/test_shared_tree.py`, `tests/test_rename.py`, the path
  guard fixtures for `--confirm-delete`). A foreign tool's files are left as they are.
- `--update` does not migrate. It **deletes the riskrails files of the project and generates
  the current ones**; `migrations/` and the schema-version ladder go.
- **What survives the delete** (Q26, the developer's picks; the "Nothing" tick read as "nothing
  else" — INFERENCE, to be confirmed in the spec's first question):
  - `.ai/project/` — the survey;
  - the project settings — `.ai/policies/testing.md` Verification commands, the project
    entries of `.ai/policies/weight.json`, `docs/sdlc/constitution.md`;
  - history and memory — `.ai/reports/`, `.ai/memory/`, `.ai/state/`, `docs/sdlc/`.
  Everything else riskrails wrote (`.ai/AGENTS.md`, `.ai/VERSION`, the shipped policies and
  rules, the managed block in the root instruction files, `.ai/local/` caches) is deleted and
  regenerated.
- Fallbacks for old plugin versions are removed (the former WP-L): `CLAUDE_AGENTIC_TEST`,
  `LEGACY_REVIEW_LINE`, the legacy `current.json`, the legacy marker pair, the deprecated alias
  skills (`ai-task`, `ai-init`, `project-update`, `sdlc-*`, …) — the full list is the spec's,
  from a grep for "legacy", "deprecated", "before 3.", "one version".
- No shim or re-export in the plugin's code (Q25): an install replaces every plugin file.

## Affected users & systems

Every project with `.ai/` that runs `--update` from an older version; anyone who used
`--adopt`. The installer (`bin/riskrails.js`) already replaces the plugin's own files (the
developer's statement, Q25 — the spec verifies it, including stale files of removed skills).

## Constraints

- The kept data is never deleted and never rewritten by an update; a kept file whose format
  the new version cannot read is reported, not converted (no migration by the back door).
- The path names `skills/ai-task/state.py` and `update.py` stay as the current CLI (Q25) unless
  the spec decides to rename the alias-named directories — then the 109 callers move with them.
- C5: the human runs commits and approvals.

## Out of scope

Splitting `update.py` into modules (small-oop-modules WP3, after this task, on the smaller file).

## Open questions for the spec

1. Confirm the kept set (Q26's contradictory tick).
2. A project setting written inside a file riskrails regenerates (e.g. the project entries of
   `weight.json` beside the shipped ones): kept by splitting the file, or by a merge that reads
   only the project section?
3. The deprecated alias skills: delete the directories, and does `skills/ai-task/` (the home of
   `state.py`) get a new name in the same task?
4. A project whose `.ai/` is older than the kept files' format: refuse with a message, or
   regenerate and leave the kept files for the human?
