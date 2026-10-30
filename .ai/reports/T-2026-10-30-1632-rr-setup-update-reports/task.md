# T-2026-10-30-1632-rr-setup-update-reports — rr-setup --update reports a tracked-but-ignored ledger under .ai/state with the git rm --cached command for the human, and the release recipe stops using commit -am

bugfix · guarded · started 2026-10-30T16:32:41Z · claude

## Weight

```
scope          2  tests/test_project_update.py referenced from 46 files
behaviour      1  keyword 'workflow' in .github/workflows/npm-publish.yml
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data; a git hygiene report and a workflow comment (declared)
novelty        0  the hint mechanism (plan.hints, deletion_hint) and git_dirty_ai already exist in update.py; the 
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T16:32:41Z — /rr-build-all ~/.claude/plans/consent-ledger-untrack.md

## Plan

files: tests/test_project_update.py, skills/project-update/update.py, skills/rr-setup/SKILL.md, .github/workflows/npm-publish.yml
tests: tests/test_project_update.py::TestProjectUpdate::test_tracked_but_ignored_state_file_is_reported, tests/test_release.py
- s1 · tests/test_project_update.py · tests/test_project_update.py::TestProjectUpdate::test_tracked_but_ignored_state_file_is_reported · done
- s2 · skills/project-update/update.py · tests/test_project_update.py::TestProjectUpdate::test_tracked_but_ignored_state_file_is_reported · done · after s1
- s3 · skills/rr-setup/SKILL.md, .github/workflows/npm-publish.yml · tests/test_release.py · done · after s2

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | b3cd1deae | .ai/state/logs/T-2026-10-30-1632-rr-setup-update-reports/suite-1.log | no |
| 2 | e2e | 0 | b3cd1deae | .ai/state/logs/T-2026-10-30-1632-rr-setup-update-reports/e2e-2.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [MEDIUM] M1 The hint prints the path raw inside a copy-paste shell command, so a hostile or odd file name can inject output and shell syntax (`skills/project-update/update.py:1250-1254`)  in_scope: yes
  why it matters: I reproduced this in a scratch repo. I tracked `.ai/state/n<LF>l; touch pwn #.jsonl` (it matches `.ai/state/*.jsonl`). The report printed a fake `hint` continuation line, followed by `git rm --cached -- .ai/state/n<LF>l; touch pwn #.jsonl` inside backticks. A path with a space (`a b.jsonl`) also prints a command that untracks the wrong paths (`.ai/state/a` and `b.jsonl`). Anyone who clones a repo can plant such a name, and the output is read by an agent and a human. SKILL.md tells the agent to relay `git rm --cached -- <path>` to the human. The `-z` parsing is correct, but it makes the raw bytes reach stdout and the command line. The change declares "no crash", and it does not crash, but the printed command is wrong or unsafe for any name that needs quoting.
  suggested direction: Build the command with `shlex.quote(path)`. Escape control characters in the display (for example `repr`-style or `\n`) so a name cannot start a new `hint` line. Add one test case with a space in the name and one with a newline.
- [LOW] L1 The test never exercises a path that needs quoting, and it does not cover a project root that is a subdirectory of a work tree or `--apply` (`tests/test_project_update.py:1428-1461`)  in_scope: yes
  why it matters: M1 would pass this test. The test covers the main case (positive hint, `--check` exit 0, negative after `git rm --cached`, and no git at all), and the negative case is real: the file stays on disk and is ignored. I ran the subdirectory case by hand and it works, because `ls-files` paths are relative to `-C root`. That case is unpinned. "`--apply` writes nothing for it" is also unpinned, although the code adds no plan item. My manual `--apply` run and a rerun gave exit 0 and "up to date".
  suggested direction: Add the subdirectory-root and odd-name assertions to the same test, if cheap. The test's `self.env` copies the whole `os.environ`, so a stray `GIT_DIR` would leak in. This is the same as the existing git tests, so it is not blocking.
- [LOW] L2 The wording says "ignored by .gitignore", but `ls-files -ci --exclude-standard` also honours `.git/info/exclude` and the user's global `core.excludesFile` (`skills/project-update/update.py:1238, 1250`)  in_scope: yes
  why it matters: A file ignored only by a per-machine or global rule is reported as a `.gitignore` problem. That is a cosmetic mismatch in the message. The failure is bounded because the hint is read-only.
  suggested direction: Say "ignored by git" or "an ignore rule", or leave as is.
- [LOW] L3 The hint prints one long line per file with no cap, and the invalid-UTF-8 decode uses `replace` (`skills/project-update/update.py:1245-1254`)  in_scope: yes
  why it matters: If a project tracks many ignored files under `.ai/state`, the report floods. Each line repeats about 150 characters of boilerplate. A non-UTF-8 name decodes to U+FFFD, so the printed command points at a path that does not exist. This is an unlikely shape.
  suggested direction: Optional. Print the boilerplate once and then the list, or use `os.fsdecode`.
- [LOW] L4 The workflow wording is not consistent with the tool text around it (`.github/workflows/npm-publish.yml:4`, line 47)  in_scope: yes
  why it matters: The new comment says "four files, five version keys". That matches `FILES` in `tools/sync-version.py`, which lists exactly those four files. But line 47 still says "five version files", and the sync-version docstring says "five places". A reader of the release recipe sees both counts.
  suggested direction: Optional wording alignment. The recipe's `git commit -m ... -- <4 files>` is correct, and the path-limited commit also skips unrelated staged changes.
- [INFO] I1 Nothing further to flag on the scope questions you listed. Details are under EXAMINED AND CLEAN.

## EXAMINED AND CLEAN
- **Exit codes, `--check` and `--apply`:** the hint is a plain `plan.hints.append`, with no `plan.add`. By hand, `--check` returned rc=0 and printed "project matches the installed plugin" while the hints printed. `--apply` ran and a rerun showed "up to date". The helper is called after `gitignore_update` and touches nothing else, so there is no merge or migration change.
- **Not in a work tree, or git missing:** `OSError`/`SubprocessError` makes it return, and a nonzero exit (not a repo) makes it return. `stderr` goes to `DEVNULL`. The no-git test case covers the "no crash" claim. I did not run the missing-git-binary path, but `FileNotFoundError` is an `OSError`, so it is covered by the `except`.
- **Project root as a subdirectory of a work tree:** I ran it with `sub/` inside a repo at the parent. The pathspec `.ai/state` resolves relative to `-C root`, and the hint paths are root-relative. They are correct for `git rm --cached` from the project root.
- **`-z` and `core.quotePath`:** `-z` disables quoting. Non-ASCII (`é.jsonl`) printed correctly, and the spaces and newline names were found. The only defect is how they are printed (M1).
- **Project-init-only branch:** the hint does not belong there. A project with only `docs/sdlc` has no `.ai/state`, and `.ai/` projects always take the `has_ai` branch.
- **Hint placement:** it runs once and reaches the output through the existing `plan.hints` print loop. The no-pending-updates path prints hints too, which is the intent.
- **SKILL.md sentence:** it fits the numbered list at the `--update` step. It gives the line as printed and the human runs the command. It adds the second-machine modify/delete note and says "never run it yourself", consistent with the no-agent-commit rule.
- **Workflow comment:** the four named files match `FILES` in `tools/sync-version.py`. `git commit -am` is gone from the recipe. The only remaining `commit -am` is in `docs/sdlc/specs/command-choice-dialog.md`, which is a consent-guard spec and not part of this change.
- **Scope creep:** none. The four files match the plan, and there is no refactor.
- not reached (budget): pylint is not installed in this environment, so I could not run it. I did not re-run the suite and inherited the green suite and e2e from the task's Verify table.

## VERDICT
verdict: pass_with_findings
scope_assessment: The change stayed inside the plan (4 files, the declared behaviour=1 hint only). M1 should be fixed in the same batch, because it is a small `shlex.quote` and display-escape change plus a test row.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +3 −2 | Edit |
| skills/project-update/update.py | +22 −0 | Edit |
| skills/rr-setup/SKILL.md | +4 −1 | Edit |
| tests/test_project_update.py | +35 −0 | Edit |

+64 −3 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on b3cd1deae (run 1) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
