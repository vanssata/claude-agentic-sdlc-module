# T-2026-10-30-1645-m1-quote-hint — fix M1: quote the path in the tracked-ignored hint

bugfix · guarded · started 2026-10-30T16:45:23Z · claude

## Weight

```
scope          2  skills/project-update/update.py referenced from 237 files
behaviour      1  keyword 'workflow' in tests/test_project_update.py
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  1 of 1 code files have a test
W 5 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/project-update/update.py, tests/test_project_update.py
tests: tests/test_project_update.py
- s1 · tests/test_project_update.py · tests/test_project_update.py · done
- s2 · skills/project-update/update.py · tests/test_project_update.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 2d68a5016 | .ai/state/logs/T-2026-10-30-1645-m1-quote-hint/step-1.log | yes |
| 2 | step | 0 | 5279d93c4 | .ai/state/logs/T-2026-10-30-1645-m1-quote-hint/step-2.log | no |
| 3 | suite | 0 | 5279d93c4 | .ai/state/logs/T-2026-10-30-1645-m1-quote-hint/suite-3.log | no |
| 4 | e2e | 0 | 5279d93c4 | .ai/state/logs/T-2026-10-30-1645-m1-quote-hint/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [LOW] L4 shlex.quote does not stop git pathspec globbing: `git rm --cached -- '<quoted>'` still reads `* ? [ ]` in the name as a glob (default pathspec magic), and the xargs form passes the same names as pathspecs; a tracked-ignored `.ai/state/a[bc].jsonl` or `.ai/state/*` would also untrack matching siblings. Same class as the space defect M1 closes, unpinned. Not executed (the guard refused creating such files under .ai/state) — rests on git's documented pathspec behaviour. Fix direction: `git --literal-pathspecs rm --cached -- …` in both commands (or `:(literal)` prefix), plus one glob-named test case. — skills/project-update/update.py:1253-1254 — in_scope: yes
- [LOW] L5 The NUL-safe command is broader than the single hint it sits on: it untracks every tracked-ignored file under .ai/state, not just the odd-named one (including ones that also got their own quoted `git rm` hint). It never touches a tracked-but-not-ignored file and the end state is identical to running all hints, so it's acceptable — but the hint text doesn't say "all of them". Fix direction: word the hint accordingly, or accept and note. — skills/project-update/update.py:1254 — in_scope: yes
- [LOW] L6 The test asserts the command strings only, never executes them; a regression in the NUL-safe command's correctness (flags, pathspec, cwd) would pass. A mutation restoring the raw name, quoting wrong, dropping escaping, or always taking the xargs branch does fail the test, so the "no raw name, no forged line" invariant is pinned. Fix direction (optional): run the printed xargs command in the test repo and assert the index emptied. — tests/test_project_update.py:1463-1486 — in_scope: yes
- [INFO] I1 Display ambiguity: a literal backslash+`n` (printable) and a real newline both display as `\n`. Harmless: the printable name takes the exact shlex-quoted command, the newline name takes the NUL-safe command, nothing is mis-untracked; cost is only that the escaped display can't tell the user which it is. — skills/project-update/update.py:1252 — in_scope: yes
- [INFO] I2 The NUL-safe command is cwd-relative, like the old one: `.ai/state` and paths resolve against cwd. From a subdirectory ls-files matches nothing and GNU xargs (no `-r`) runs `git rm --cached --` once with no paths → usage error, never a wrong untrack. For a project nested in a parent work tree, `-C plan.root` lists root-relative paths and the command run from that root is correct; a nested root that isn't its own repo behaves as before. Fails safe; a "run from the project root" note would help. Pre-existing. — skills/project-update/update.py:1254 — in_scope: no
- [INFO] I3 Non-UTF-8 names decode to U+FFFD (printable) → prints `git rm --cached -- '…�…'`, which matches nothing → git errors, nothing untracked. Already recorded as L3, out of scope. Also confirmed `isprintable()` escapes NBSP, U+3000, U+200B and bidi controls (U+202E) — correctly routed to the NUL-safe form; Cyrillic shown as-is and quoted (shlex's safe set is ASCII-only). — skills/project-update/update.py:1248 — in_scope: no

## VERDICT
verdict: pass_with_findings

Read the diff and the code path; did not run the suite (inherited green suite+e2e from the ledger, didn't re-derive). Scope held: only `tracked_ignored_hint`, the `shlex` import, and the new test changed.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| skills/project-update/update.py | +8 −3 | Edit |
| tests/test_project_update.py | +25 −0 | Edit |

+33 −3 lines, 2 files

## Verdict

close: closed
facts: (a) green — suite green on 5279d93c4 (run 3) · (b) green — 2 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 1 · review passes: 1
