# T-2026-10-30-1708-low-findings — fix the LOW review findings of the tracked-ignored hint, the weight mirror and the release wording

bugfix · guarded · started 2026-10-30T17:08:57Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 239 files
behaviour      1  keyword 'workflow' in .github/workflows/npm-publish.yml
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data; report wording, a read-only hint and the weight-mirror fall
novelty        0  the hint, weight_mirror and the release recipe exist; each fix narrows or rewords them (declared
coverage       1  1 of 2 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T17:08:57Z — /rr-build-all: fix all open LOW findings (risks L1-L6 of T-2026-10-30-1632/1645, L2/L3 of T-2026-10-30-1347)

## Plan

files: skills/project-update/update.py, tests/test_project_update.py, .github/workflows/npm-publish.yml, tools/sync-version.py
tests: tests/test_project_update.py, tests/test_release.py
- s1 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s2 · .github/workflows/npm-publish.yml, tools/sync-version.py · tests/test_release.py · done
- s3 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done · after s1

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 1 | 5e04b27dc | .ai/state/logs/T-2026-10-30-1708-low-findings/suite-1.log | no |
| 2 | suite | 0 | cbe8dd1cb | .ai/state/logs/T-2026-10-30-1708-low-findings/suite-2.log | no |
| 3 | e2e | 0 | cbe8dd1cb | .ai/state/logs/T-2026-10-30-1708-low-findings/e2e-3.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
No BLOCKER or HIGH. 11 weight_mirror and tracked tests run by the reviewer: OK.
- [MEDIUM] M1 The stale-mirror hint tells the human to run `weight --mirror`, which overwrites a hand-edited weight.md (skills/project-update/update.py:~886, stale_mirror_hint) in_scope: yes — the hint fires whenever the header sha256 differs from the JSON on disk, including a text-merged, hand-edited mirror; it repeats every run and its only advice replaces the edits without saying so. Update never overwrites such a mirror itself, so the invariant holds. Direction: say "this replaces any hand edits in weight.md" and test the hand-edited-and-stale case.
- [LOW] L1 skills/rr-setup/SKILL.md:173-175 still tells the agent to hand the human `git rm --cached -- <path>` (old shape; composing from <path> brings back the glob issue) in_scope: yes (file outside the task) — follow-up.
- [LOW] L2 Release wording incomplete: tests/test_release.py:2,5 say "five version fields"/"the five places"; tools/sync-version.py:9 "The places:" in_scope: yes — follow-up.
- [LOW] L3 `except Exception` in weight_mirror also swallows renderer programming errors silently (update.py:868) in_scope: yes — fallback is safe; optional: name the exception class in a hint.
- [INFO] I1 The stale hint compares to the pre-update weight.json on disk, not the JSON this run leaves; a mirror made stale by this run is hinted only next run.
- [INFO] I2 xargs on empty input runs `git rm --cached --` and fails harmlessly; not reached in the normal flow; cwd-relative as before.

## EXAMINED AND CLEAN
Printed commands (literal-pathspecs, shlex.quote, NUL-safe form, escaped display incl. surrogates, NBSP, U+2028, bidi); invariants (hints only, --check 0, --apply writes nothing, no crash outside git, no forged line); cap and "N more" count; project below a git root; other consumers of the wording (only rr-setup SKILL.md); tests not weakened (OSError test fails on the old except); stale-hint mechanics (raw-byte sha256, regex bounded, text-merge branch only); scope: only the four task files.
Not reached: manual stale-hint run against a real project; branch-protection check names.

## VERDICT
verdict: pass_with_findings
scope_assessment: stayed inside the four approved files; tests/test_release.py and rr-setup/SKILL.md wording are follow-ups.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .github/workflows/npm-publish.yml | +1 −1 | Edit |
| skills/project-update/update.py | +51 −15 | Edit |
| tests/test_project_update.py | +168 −33 | Edit |
| tools/sync-version.py | +4 −4 | Edit |

+224 −53 lines, 4 files

## Verdict

close: closed
facts: (a) green — suite green on cbe8dd1cb (run 2) · (b) green — 4 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
