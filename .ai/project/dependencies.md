# Dependencies

## Runtime platform

- KNOWN FACT: Python 3 stdlib only. Hooks run `python3 -I -S` (`hooks/hooks.json:21`). CI covers 3.11, 3.12 and 3.13, and 3.10 is red (`.github/workflows/tests.yml:25`). The nightly `full` job runs on 3.12 only.
- KNOWN FACT: Node ≥ 18 (`package.json:11`), no dependencies (`:13`). CI uses Node 22.
- KNOWN FACT: optional sqlite FTS for the memory index, with a fallback when it is unavailable (`memory_store.py:287,333-341`).
- KNOWN FACT: `fcntl` for the journal lock, with an O_APPEND-only fallback when it is missing (`rr_state/journal.py:10-12`). INFERENCE: weaker on Windows.

## Dependencies that carry behaviour

- KNOWN FACT: the host runtimes' hook contracts (Claude Code event names and payloads; Codex `hooks.json` and the trust model). A runtime change in event names or payload shape changes guard decisions.
- KNOWN FACT: CI pins `pylint 4.0.8` (`pylint.yml:27`).

## Patched or forked packages

- None.

## Frontend build

- None. `site/` is a separate gh-pages worktree, git-ignored here.

## Upgrade landmines

- RISK: golden and hash outputs depend on the Python version. Release 3.2.0 failed on 3.12 while `main` was green (`tests.yml:29-30`).
- RISK: `TestTimed` uses `AI_TIMED_FACTOR=3` nightly (`tests.yml:57`) but 1 in release verify (`npm-publish.yml:118`), so a slow runner can fail a release.
