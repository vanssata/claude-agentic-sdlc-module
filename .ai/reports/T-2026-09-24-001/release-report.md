# Release report — T-2026-09-24-001

**Goal.** Give `usage-report.py` an on-disk incremental parse cache keyed by
path + mtime + size, so a rescan reads only the new lines; bump the project
version to 2.0.2.

**Tier.** Started T2, re-scored T3 by the diff budget (421 lines > 400) while
closing step 1.2. Base commit `6ca0369`.

## What changed

| File | What |
|---|---|
| `skills/usage-report/usage-report.py` | the cache: `cache_path` (resolved once), `cache_open`, `cache_flush` (atomic, 0600 in a 0700 directory, temp file cleaned in a `finally`), `_head_sig`, `_state_ok`, `claude_valid`/`codex_valid`, `_num`, `fold_file`; the parsers fold through it; `--no-cache` |
| `tests/test-usage-report.sh` | 29 new assertions: the cache's behaviour, its guards, `--today` across a UTC midnight, `--task` with a relative cache path, non-string identifiers |
| `tests/test-codex-usage-report.sh` | 5 new assertions: the same on a rollout file, plus an unterminated last record over three rescans |
| `skills/usage-report/SKILL.md` | "The parse cache": where it lives, what it guarantees, what it costs |
| `README.md` | version 2.0.2, the assertion count, and a Known-risks entry for what the mtime+size key assumes |
| `.codex-plugin/plugin.json` | 2.0.0 → 2.0.2 |

Deliberately preserved: every number the report prints. Verified md5-identical
output against `git show HEAD:` on a 1,100-file corpus for `--all`, `--provider
codex --all`, `--session` and `--today`, cached and uncached.

## Verification

`bash tests/run-all.sh` — 25 suites, **2,163 assertions, 0 failed, exit 0**.
`pylint $(git ls-files '*.py')` — **10.00/10, exit 0** (the repository's CI gate).
The e2e suite (`tests/test-end-to-end.sh`) runs inside `run-all.sh` and is green.

The recorded `state.py test-run` could not be used: this repository has no
`.ai/policies/testing.md` at all, so the tests, lint and typecheck sensors are
UNAVAILABLE and the verification command was run directly. That is why the
Pylint blocker below reached a review rather than a sensor.

## Reviews

Four adversarial reviews on the STRONG tier, all verified by execution;
`review-report.md` has them in full.

- Round 1: BLOCKER — a cache entry was handed to the other runtime's fold.
- Round 2: the fix held, but three of its guards survived mutation with a green
  suite, and a cached state was validated on only one path.
- Round 3 (human-authorised, the policy allows two): finding 7 had been recorded
  as fixed and was not — `abspath` resolves per call and `--task` chdirs.
- Round 4: the remediation's own `global` statements broke the Pylint gate, and
  one identifier had been left out of the normalisation, crashing a report that
  `main` renders. Both fixed; suite and lint green afterwards.

Every guard the cache rests on is now pinned by a mutation the suite catches:
the version check, the state shape check, the contents validators, the head
signature, the per-day slots, the tail `deepcopy`, and the memoised cache path.

**Security:** not applicable, with a reason in the journal — no auth, secrets or
personal data; the cache's permissions and temp-file handling were reviewed.

## Known risks carried out of this task

1. A rewrite that keeps the first 256 bytes and grows the file would resume from
   a stale offset (README, Known risks; `--no-cache` is the escape hatch).
2. A malformed transcript line — a bare array, a string, a numeric timestamp —
   crashes the report. `main` does this too; not introduced here, not fixed here.
3. `_num("1e5")` is 0: a string-formatted float token count is silently lost.
4. `kind` and the shape check are mutually redundant for the cross-fold case, so
   neither is individually pinned; the guarantee is structural.
5. This repository's `.ai/` has no `policies/`, `VERSION` or `AGENTS.md`
   (`/project-update --check`: `schema 0 -> 5, 53 files`), which is why three
   sensors are UNAVAILABLE and `test-run` refuses. Outside this task.
6. Untracked `claude-agentic.code-workspace` is not in `.gitignore`.

## Process notes a human should see

- Step R1 and step R3 were closed with `state.py step-done --force`: a
  remediation's scope is every finished step, so its diff is measured from the
  base tree and no split makes one 400-line file fit the 250-line step budget.
  Both forced closes are journalled with their reason.
- The traceability sensor is RED: steps 1 and 1.3 named no tests of their own.
  The tests exist — they are step 1.2 — but the plan never linked them.
- Remediation round 3 was authorised by Ivan in their own terminal after the
  policy's two rounds were spent.

## Rollback

Nothing is committed. `git checkout -- skills/usage-report tests README.md
.codex-plugin/plugin.json` returns the tree to `6ca0369`. After a commit, one
`git revert` of that commit; the cache file is not part of the repository and
can be deleted at `~/.cache/claude-agentic/usage-report.json`.
