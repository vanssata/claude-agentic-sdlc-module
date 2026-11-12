# T-2026-11-12-1826-auto-tag-release — A version bump merged to main is tagged, published to npm and announced as a GitHub Release by npm-publish.yml, with the CHANGELOG section in the notes

feature · guarded · started 2026-11-12T18:26:54Z · claude

## Weight

```
scope          2  tests/test_release.py referenced from 33 files
behaviour      1  keyword 'workflow' in .github/workflows/npm-publish.yml
reversibility  0  git revert returns everything
domain         0  CI release plumbing; the npm environment gate and its permissions stay as they are (declared)
novelty        1  a new trigger, a detect job and one new stdlib tool; no new dependency or action (declared)
coverage       2  0 of 1 code files have a test
W 6 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/test_release.py, .github/workflows/npm-publish.yml, tools/changelog-section.py
tests: tests/test_release.py
- s1 · tests/test_release.py · tests/test_release.py · done
- s2 · .github/workflows/npm-publish.yml, tools/changelog-section.py · tests/test_release.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 953762c5f | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/step-1.log | yes |
| 2 | step | 0 | e7b3f63df | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/step-2.log | no |
| 3 | suite | 1 | e7b3f63df | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/suite-3.log | no |
| 4 | suite | 1 | 682d36edb | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/suite-4.log | no |
| 5 | suite | 0 | 681082374 | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/suite-5.log | no |
| 6 | e2e | 0 | 681082374 | .ai/state/logs/T-2026-11-12-1826-auto-tag-release/e2e-6.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS

No BLOCKER and no in-scope HIGH. I ran one snippet (the tool on an empty section) and read the diff and the test file. I did not run the test file, GitHub or npm.

- [MEDIUM] M1 Recovery after a failed `verify` is not documented, and a rerun cannot fix it (`.github/workflows/npm-publish.yml:1-12`, `:78-138`)  in_scope: yes
  what happens: A bump commit X goes red in `verify` (CHANGELOG section missing, flaky gate). The fix is a later commit Y that does not touch `package.json`, so the `paths: [package.json]` filter starts nothing. "Re-run" reuses SHA X and fails again. The only ways out are a manual tag on Y or a dummy `package.json` edit.
  why it matters: This is the failure the new CHANGELOG gate makes likely, and the header only says "a push that changes package.json without a new version releases nothing". It does not say that a failed release is recovered by pushing the tag by hand. That route works, because the tag-event run does the same detect, verify and publish.
  suggested direction: Add two lines to the header comment: after a red run, fix on main, then `git tag vX.Y.Z <fix-commit>` and push it.

- [MEDIUM] M2 An empty CHANGELOG section passes the gate (`tools/changelog-section.py:60-64`, verify step `:102-103`)  in_scope: yes
  what happens: I ran it on `## [1.0.0]` followed straight by `## [0.9.0]`. It exits 0 and prints a lone newline. The gate "has a section for this version" is green and the Release goes out with the static text and nothing else. A bare heading is enough to defeat the gate.
  why it matters: The gate's stated purpose is that the notes carry the version's changes, and it is cheap to defeat by accident. No test pins either behaviour.
  suggested direction: Exit 1 when the trimmed body is empty, and add a test case for it.

- [LOW] L1 Two small tool gaps: the concurrency group changed for the manual route, and a non-UTF-8 CHANGELOG gives the wrong exit code (`tools/changelog-section.py:55-59`; workflow `:31-33`)  in_scope: yes
  what happens: A non-UTF-8 CHANGELOG raises `UnicodeDecodeError`, which is not an `OSError`. The tool dies with a traceback and exit 1 ("no section") instead of 2. The gate still fails, so it is red either way.
  why it matters: Before, the group was `release-<ref_name>`, so each tag ran independently. Now it is a single group `release`. GitHub keeps one pending run and cancels the older pending runs, even with `cancel-in-progress: false`. With a run waiting on `npm` approval, plus two or more later tag or package.json pushes, a middle release is silently dropped. It is rare, and the human intended the single group.
  suggested direction: Mention it in the header comment, and catch `UnicodeDecodeError` too.

- [LOW] L2 Prerelease on main is released like a stable (`npm-publish.yml:182-186`, `:228`)  in_scope: yes
  what happens: A `1.2.3-rc.1` bump on main publishes under dist-tag `next`, and the tag and Release are created. The `next` branch itself pre-existed on main. `gh release create` is called without `--prerelease`, and the notes tell readers to run `npx riskrails@latest`, which does not install the rc.
  why it matters: Watchers are notified of a "latest" release that `@latest` does not give them. For an rc you will usually want an explicit decision.
  suggested direction: Pass `--prerelease` for `*-*` versions, or state in the header that prereleases are released automatically.

- [LOW] L3 `gh release view` failing for another reason reads as "no release" (`:64`, `:207`)  in_scope: yes
  what happens: On an auth, rate-limit or network error, `detect` sets `release=true` where a Release already exists. On attempt 1, `verify` then fails at "not on registry yet", before anything is published. On a rerun, `publish` skips the upload, the tag step passes, and `gh release create` fails with "already exists". Both end red with nothing wrongly published. I checked this and it is the safe direction.
  suggested direction: None needed. Optionally distinguish "release not found" from other errors.

- [LOW] L4 Tests that pin less than they claim (`tests/test_release.py:145-228`)  in_scope: yes
  what happens: I checked the first-occurrence order checks you asked about (`"npm publish"`, `"exit 0"`, `"gh release create"`). In `publish` each of these strings first occurs in the real command, not in a comment, so those pass for the right reason. The gaps:
  - `publish` having no `if:` (for example `always()`) is not asserted. That is the gating property that matters most, and only `needs: [detect, verify]` is checked.
  - `notes.md` receiving the changelog output and being the `--notes-file` is not checked, only that the tool name appears before `gh release create`.
  - The `release=false` logic (tag at another commit, release exists) and the awk annotated-tag parse are asserted by substring only, never run, although the awk snippet is easy to run against fake `ls-remote` output.
  - Nothing covers an empty section, CRLF, or `--file` pointing at a directory.
  suggested direction: Add a negative assertion `assertNotRegex(self.publish, r"(?m)^\s+if:")`, and run the awk snippet on canned input.

- [INFO] I1 `paths:` and `tags:` in one `push` trigger (`:25-29`)  in_scope: no
  what happens: I could not verify, without network access, how GitHub evaluates `paths` for tag pushes. My recollection is that path filters are not applied to tag pushes, but I am not certain. If I am wrong, the manual tag route, which must keep working, would stop firing.
  why it matters: This is the highest-impact unknown for the task's "manual route must keep working" requirement. It needs one real dry tag push, or a check of the GitHub docs.

- [INFO] I2 `GITHUB_SHA` against the peeled tag commit on an annotated manual tag (`:190-200`)  in_scope: no
  what happens: The new "Create the tag" step compares `TAGGED` (the peeled commit) with `GITHUB_SHA`, and exits 1 on a mismatch. This is after `npm publish` has already uploaded. If `GITHUB_SHA` were the tag object rather than the commit for an annotated tag event, the manual route would publish and then fail. As I remember it, it is the commit, so this should be fine. It needs one real annotated-tag run to confirm.

- [INFO] I3 Injection (the area you asked about) is clean (`:51-62`, `:102-103`, `:133`)  in_scope: yes
  what happens: The bash `[[ =~ ]]` whole-string test runs before anything is written to `$GITHUB_OUTPUT`. `$` is anchored at the end of the string, and the test runs the newline case. `TAG` reaches shell words only through `env`, so there is no `${{ }}` inside a `run:` (`test_no_needs_expression_inside_a_run_script` pins this). The tool's stdout goes to `/dev/null` in `verify` and to a file in `publish`, so a `::command::` in the CHANGELOG is never echoed to the log. The tool's own version check is `fullmatch`, and it uses `startswith`, not a regex or path built from the version. A prerelease heading `## [4.1.0-rc.1]` is not matched for version `4.1.0`, because the `]` closes the heading. CHANGELOG content reaches the release notes as markdown only.

## VERDICT
verdict: pass_with_findings
scope: the change stayed inside the plan (workflow, tool, test file). Gating holds as designed: `publish` is skipped when `verify` is skipped or fails, and `verify` and `publish` both check out the same `github.sha`. The tag is created at `GITHUB_SHA`, the same commit as the npm upload. Permissions: `detect` and `verify` have `contents: read`; only `publish` has write. A double run (merge plus a manual tag) is safe: the second run sees the existing Release and skips, and `GITHUB_TOKEN` pushes do not re-trigger the workflow.
Not reached (budget): I did not run `tests/test_release.py` and made no network calls.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +88 −15 | Edit |
| tests/test_release.py | +140 −5 | Edit |
| tools/changelog-section.py | +69 −0 | New |

+297 −20 lines, 3 files

## Verdict

close: closed
facts: (a) green — suite green on 681082374 (run 5) · (b) green — 3 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 3 · review passes: 1
