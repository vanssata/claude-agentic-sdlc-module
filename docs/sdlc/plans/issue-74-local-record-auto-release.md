# Plan: issue #74, a local record by default, automatic tag and release

Three tracks with disjoint files, one task and one branch each, so they can run in
parallel worktrees. Source: GitHub issue #74 and the decisions of 2026-11-12.

- **A — bugfix #74.** `memory export` wrote a task seal whose `changes` was 110–150 KB.
  `parse_package` skipped every line over `LINE_MAX_BYTES` (65 536) unparsed, so the
  export's read-back lost the seal (V9 stayed), V1 advised a `git checkout` that restored
  the same line, and `memory redact` could not find the rid.
- **B — a local record by default.** `.ai/memory/` (the seals) and `.ai/reports/` (task
  logs) are git-ignored by default; git keeps configuration (`policies/`, `rules/`,
  `project/`, `VERSION`, `AGENTS.md`). Sharing through git is an explicit opt-in.
- **C — automatic tag and release.** A version bump merged to `main` is tagged, published
  to npm and announced as a GitHub Release whose notes carry the CHANGELOG section.

## Who does what

| Role | Tier → model / effort | Work |
|---|---|---|
| Thinking — the session | the session model | the plan, `state.py weight` and `start`, the implementers' briefs, checking the red proof, `verify`, integration, `/rr-ship`. Never delegated. |
| Thinking — review | BALANCED → `ai-reviewer`, sonnet / medium (all three tracks weighed guarded) | one adversarial review per track |
| Thinking — escalation | STRONG, then EXPERT (`architect`) | only if a review returns `confidence: uncertain` on B's design (shared = read from git) |
| Writing code | BALANCED → `general-purpose`, sonnet / medium | one implementer per track in its worktree: tests, code, documents. Never calls `state.py`. |
| Reading and running | FAST → `Explore`, `log-reader`, haiku / low | lookups; reading a red suite log |

Never more than one agent above BALANCED at a time.

## Layout

```
A  fix/74-seal-over-line-max      ─┐
B  feat/local-record-by-default    ─┼─ PR and merge (the human) ─ I integration ─ 4.1.1, the first automatic release
C  feat/auto-tag-release           ─┘
```

- `git worktree add ../claude-agentic-wt/<a|b|c> -b <branch> main`. `.ai/state/` is
  git-ignored, so each worktree carries its own task.
- The whole suite (`verify --scope all`) runs in one worktree at a time: `TestTimed` and
  `TestGateFastPath` measure wall-clock time. Step tests may run in parallel.
- Shared files — `CHANGELOG.md`, the #74 sentence in `docs/local-memory.md`, untracking this
  repository's own record — belong to step I only.
- Run serially in one tree, the order is A, B, C, I.

## Files that change

| Track | Files |
|---|---|
| A | `skills/ai-task/memory_compact.py`, `memory_format.py`, `memory_verify.py`; `tests/test_memory_compact.py`, `test_memory_format.py`, `test_memory_cleanup.py`, `test_memory_sync.py`; `docs/sdlc/specs/compact-project-memory.md`; this plan |
| B | `skills/ai-init/templates/gitignore.snippet`; `skills/ai-task/memory_io.py`, `memory_hook.py`, `memory_sync.py`, `memory_status.py`, `rr_state/cli.py`, `rr_state/memory_cmd.py`; `skills/project-update/rr_update/hints.py`; `skills/rr-setup/setup.py`, `SKILL.md`; `tests/test_memory_pre_push.py`, `test_project_update.py`, `test_setup.py`, `test_update_characterization.py`; `docs/local-memory.md`, `docs/getting-started.md`, `docs/project-update.md`; `.gitignore` |
| C | `.github/workflows/npm-publish.yml`; `tools/changelog-section.py` (new); `tests/test_release.py` |
| I | `CHANGELOG.md`; `docs/local-memory.md` (one sentence) |

Not touched by B: `rr_state/labels.py`, `hooks/guard/dialog.py` (the approval path),
`memory_verify.py` (A's), `tests/memory_harness.py`.

## Order of work

### A — bugfix #74 (W 4, guarded)

| Step | Who | What | After |
|---|---|---|---|
| A1 | sonnet | the four failing tests | start |
| A1v | session | `verify --scope step --expect fail`, `step-done` | A1 |
| A2 | sonnet | the fix | A1v |
| A2v | session | `verify --scope step`, `step-done` | A2 |
| A3 | sonnet | the spec row | A2v |
| A4 | session | `verify --scope all`, e2e | A3 |
| A5 | `ai-reviewer` (sonnet) | review; BLOCKER and HIGH fixed as one batch, each pinned by a test | A4 |
| A6 | session | `/rr-ship` | A5 |

- **Tests (C2).** A 1500-row `changes` table gives a seal of at most `LINE_MAX_BYTES` that
  validates, keeps a prefix of the rows, names `changes` in `truncated` and carries
  `changes_truncated = {rows, added, deleted}`; a seal under the limit is byte-identical to
  today's. An over-long valid line is an error **and** an entry (`_line`, `_over`). A task
  with 1500 changed files exports, reads back and passes the hook. A repository already
  stuck (a committed over-long seal, a pending outbox): `export --pending` clears the
  outbox, V1 names `memory redact <rid> --field changes`, the redaction works, `verify`,
  the hook and `memory show` pass.
- **Fix.** `memory_compact._seal`: when the canonical line passes the limit and `changes`
  is a non-empty list, keep the longest prefix that fits, name the field in `truncated`,
  record the totals in `changes_truncated`; deterministic, one place for close, migrate and
  the index. `memory_format.parse_package`: an over-long line stays a V1 error and is parsed
  anyway; a valid entry is kept with the private key `_over` (the precedent is "not in
  canonical form"). `memory_format.render_task_md`: a `changes` that is not a list falls
  back to `files`. `memory_verify.check_packages`: for such a line the fix text is
  `shorten it: 'state.py memory redact <rid> --field <largest field> --why "…"'`; every
  other V1 text stays byte-identical, so no golden is re-recorded.

### B — a local record by default (W 6, guarded; behaviour 2 by C6)

**Decision: "shared" is read from git, not from a new policy key.** The record is local
exactly when `.ai/memory/` is git-ignored. The schema of `memory.json` does not move, and
the test projects of `tests/memory_harness.py` (no such ignore lines) stay shared, so
today's tests and goldens describe the opt-in path unchanged.

| Step | Who | What | After |
|---|---|---|---|
| B1 | sonnet | the tests | start |
| B1v | session | `verify --scope step --expect fail`, `step-done` | B1 |
| B2 | sonnet | the code | B1v |
| B2v | session | `verify --scope step`, `step-done` | B2 |
| B3 | sonnet | documents and this repository's `.gitignore` | B2v |
| B4 | session | `verify --scope all`, e2e | B3 |
| B5 | `ai-reviewer` (sonnet) | review; one fix batch | B4 |
| B6 | session | `/rr-ship` | B5 |

- `gitignore.snippet` gains `.ai/memory/` and `.ai/reports/`.
- `memory_io.shared(root)`: `git check-ignore -q --no-index .ai/memory/x`; exit 1 is shared.
- `memory enable --share git|local`: `git` appends `!.ai/memory/` and `!.ai/reports/` to
  `.gitignore`, `local` appends the two ignore lines; append only. The pre-push hook is
  installed only for a shared record, otherwise our own hook is removed. `--share` has no
  dialog route: the consent-label allowlists stay as they are.
- A local record: `enable` prints `record: local — …`, `memory status` prints
  `pre-push: not needed — the record is local (.ai/memory/ is git-ignored)`, the validator
  exits 0 silently (V9 included), `memory verify --fresh-clone` exits 2 saying a fresh
  clone has none.
- `/rr-setup --update` (`hints.gitignore_update`) skips a line whose `!` negation is in the
  file, and when it appends one of the two lines prints the untrack command
  (`git rm -r --cached --ignore-unmatch .ai/memory .ai/reports`, the human's) and the way
  to keep sharing.
- The `/rr-setup` memory question no longer says "committed … checked by a pre-push hook".
- Documents: the "Two modes" table and a new "Sharing through git" section in
  `docs/local-memory.md`; "commit `.ai/`" in the getting-started, project-update and
  `/rr-setup` texts means the configuration.

### C — automatic tag and release (W 6, guarded)

| Step | Who | What | After |
|---|---|---|---|
| C1 | sonnet | the tests in `tests/test_release.py` (the smoke list) | start |
| C1v | session | `verify --scope step --expect fail`, `step-done` | C1 |
| C2 | sonnet | the workflow and the tool | C1v |
| C2v | session | `verify --scope step`, `step-done` | C2 |
| C3 | session | `verify --scope all`, e2e | C2v |
| C4 | `ai-reviewer` (sonnet) | review: a rerun after a partial failure, a double run (merge plus a manual tag), script injection through the version | C3 |
| C5 | session | `/rr-ship` | C4 |

- `on`: tags `v*.*.*` as before, plus `branches: [main]` with `paths: [package.json]`;
  `concurrency.group: release`.
- Job `detect` (`contents: read`): the tag is the pushed tag, or `v<package.json version>`,
  checked against a version regex. `release=false` when a GitHub Release for the tag exists,
  or the tag exists on another commit; otherwise `true`. A merge without a new version is a
  green no-op; a rerun after a partial failure goes on.
- `verify`: needs `detect`; `$TAG` through `env`, never `${{ }}` inside a script; a new gate
  that `CHANGELOG.md` has a section for the version.
- `publish` (`environment: npm`, as before): npm publish, then the tag is created when it
  is missing, then the Release — the static text plus the CHANGELOG section. A tag pushed
  with `GITHUB_TOKEN` starts no second run; a manual tag still works.
- `tools/changelog-section.py X.Y.Z [--file PATH]`: the body of `## [X.Y.Z]` up to the next
  `## [`; exit 1 when absent, exit 2 for an invalid version.

### I — integration (after the three merges; documents)

1. `CHANGELOG.md` `[Unreleased]`: Fixed (#74), Changed (a local record by default, with the
   upgrade note), Added (automatic tag and release).
2. `docs/local-memory.md`: the sentence on `changes_truncated` and the new V1 hint.
3. This repository, the human's command and its own commit, last so that no file tracked by
   branches A and C stays behind:
   `git rm -r --cached --quiet .ai/memory .ai/reports`.
4. Release 4.1.1 — `python3 tools/sync-version.py 4.1.1`, a `## [4.1.1]` section, a PR, a
   merge — is the live proof of track C.

## Risks

- A: a seal over the limit because of a huge `files` list is not cut; it is repairable with
  `memory redact … --field files`, and V1 now says so. A redacted list field is a string.
  `json.loads` of a deeply nested line raises `RecursionError`, today too.
- B: a team that shares the record through git becomes local at the next
  `/rr-setup --update` until someone runs `memory enable --share git`; the update says so.
  Files git already tracks stay tracked until a human untracks them. `memory migrate` reads
  tracked reports only. One developer's `core.excludesFile` can make the record local for
  that developer alone. **Riskiest step: B2** — the validator's silent exit must apply only
  to an ignored record.
- C: an `npm` environment restricted to tags refuses a run from `main` (GitHub → Settings →
  Environments → `npm`); a human who also pushes the tag by hand gets a second run, which
  `detect` and the constant concurrency group turn into a no-op.

## Proof (tests)

| Requirement | Proof |
|---|---|
| A: no seal over the limit; small seals unchanged | `tests/test_memory_compact.py`, `tests/test_memory_sync.py` |
| A: an over-long line is visible to read-back and redact | `tests/test_memory_format.py`, `tests/test_memory_cleanup.py` |
| A: V1 names the working fix | `tests/test_memory_cleanup.py` |
| B: local by default, no hook, no V9 | `tests/test_memory_pre_push.py` |
| B: opt-in restores today's behaviour | `tests/test_memory_pre_push.py`, the unchanged memory goldens |
| B: scaffold and update write the ignore lines, respect the negation | `tests/test_setup.py`, `tests/test_project_update.py`, `tests/test_update_characterization.py` |
| C: triggers, `detect`, gates, order, notes | `tests/test_release.py` |
| C: the tool | `tests/test_release.py` |
| every track | `state.py verify --scope all`, then e2e, once, in that track's worktree |

## Rollback

`git revert` of a track's merge. A: seals already written with `changes_truncated` stay
valid for 4.1.0 readers. B: the appended `.gitignore` lines stay in user projects until
removed by hand; nothing is deleted from disk. C: the tag trigger is untouched, so the
manual release keeps working.
