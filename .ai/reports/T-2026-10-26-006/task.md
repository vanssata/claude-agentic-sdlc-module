# T-2026-10-26-006 — redesign 3.1: port the three PreToolUse guards to one Python process (hooks/ai-guard.py + hooks/guard/) behind exec shims, golden byte-identical

refactoring · guarded · started 2026-10-26T19:37:27Z · claude

## Weight

```
scope          2  .ai/project/known-risks.md referenced from 144 files
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         1  security guard hooks for user projects, fail-open preserved (declared)
novelty        1  new ERE->re translation layer and locale emulation (declared)
coverage       1  7 of 11 code files have a test
W 6 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: .ai/project/known-risks.md, hooks/ai-git-guard.sh, hooks/ai-guard.py, hooks/ai-path-guard.sh, hooks/ai-scope-guard.sh, hooks/guard/__init__.py, hooks/guard/common.py, hooks/guard/ere.py, hooks/guard/git.py, hooks/guard/paths.py, hooks/guard/scope.py, install.sh, tests/fixtures/guard-characterization/sh-c-20k.txt, tests/fixtures/guard-port/**, tests/test-codex-install.sh, tests/test-guard-characterization.sh, tests/test-install-dry-run.sh, tests/test_ere_unit.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_imports.py, tests/test_suite_parity.py, .ai/reports/T-2026-10-26-006/review-findings.md
tests: tests/test-ai-git-guard.sh, tests/test-ai-path-guard.sh, tests/test-ai-scope-guard.sh, tests/test-codex-install.sh, tests/test-guard-characterization.sh, tests/test-install-dry-run.sh, tests/test_ere_unit.py, tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test_imports.py, tests/test_suite_parity.py
- s1 · tests/fixtures/guard-port/**, tests/fixtures/guard-characterization/sh-c-20k.txt, tests/test-guard-characterization.sh, tests/test_imports.py, tests/test_suite_parity.py · tests/test-guard-characterization.sh, tests/test_imports.py, tests/test_suite_parity.py · done
- s2 · hooks/guard/__init__.py, hooks/guard/ere.py, hooks/guard/common.py, tests/test_ere_unit.py · tests/test_ere_unit.py · done
- s3 · hooks/guard/git.py, hooks/guard/scope.py · tests/test_ere_unit.py · done
- s4 · hooks/guard/paths.py · tests/test_ere_unit.py · done
- s5 · hooks/ai-guard.py, hooks/ai-git-guard.sh, hooks/ai-path-guard.sh, hooks/ai-scope-guard.sh, install.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test_guard_characterization.py, tests/test_guard_differential.py, .ai/project/known-risks.md · tests/test_guard_characterization.py, tests/test_guard_differential.py, tests/test-guard-characterization.sh, tests/test-ai-git-guard.sh, tests/test-ai-path-guard.sh, tests/test-ai-scope-guard.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh · done
amended 2026-10-26T22:01:09Z: +.ai/reports/T-2026-10-26-006/review-findings.md — the reviewer's findings name guarded paths in prose; the live path guard refuses them in a heredoc, so the verbatim report goes to review --report as a file

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | 924051e27 | .ai/state/logs/T-2026-10-26-006/step-1.log | yes |
| 2 | step | 1 | 924051e27 | .ai/state/logs/T-2026-10-26-006/step-2.log | no |
| 3 | step | 0 | a1eec30cd | .ai/state/logs/T-2026-10-26-006/step-3.log | no |
| 4 | suite | 0 | f41f8d640 | .ai/state/logs/T-2026-10-26-006/suite-4.log | no |
| 5 | e2e | 0 | f41f8d640 | .ai/state/logs/T-2026-10-26-006/e2e-5.log | no |
| 6 | step | 0 | e1e1893b8 | .ai/state/logs/T-2026-10-26-006/step-6.log | no |
| 7 | suite | 0 | 21a718a4b | .ai/state/logs/T-2026-10-26-006/suite-7.log | no |
| 8 | e2e | 0 | 21a718a4b | .ai/state/logs/T-2026-10-26-006/e2e-8.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
- [HIGH] H1 hooks/guard/common.py:624 (ere_escape) — The port "fixes" a quirk of the shell guard, so decisions move. The shell's ere_escape (lib/ai-hook-common.sh:137) lists '\\' in a single-quoted case pattern; that is two characters, so a single backslash in a token is never escaped. The port's escape set is a one-character string containing a backslash, so it escapes it. For a token with a backslash the shell builds a pattern in which \c means c and matches the unescaped spelling; the port matches the literal backslash, so the reader, writer, mode and remover checks start to fire. Repro (project with .ai/, state in flight, cwd = project root): `cat secrets/` + `\` + `db.txt`: shell allows, port denies "Refusing a shell command that would expose a sensitive path: secrets/\\db.txt"; tee, touch, `echo x >`, `sed -i s/a/b/` and cat on `.ai/state/` + `\` + `current.json`: shell allows each, port denies each; `cat` + `\` + `\` + `.ssh/id_rsa`: shell allows, port denies; `ln -s .ai/state/` + `\` + `current.json x`: both deny, messages differ (shell "Refusing to create a symlink to a sensitive path", port "Refusing a shell command that writes a claude-agentic control file"); a user deny_patterns line `x` (from "x\ny") with `cat x\ny`: shell allows, port denies. Same under C and C.UTF-8, Python 3.10 and 3.14. Dropping the backslash from the set in a scratch copy gave 0 diffs over 15 further fuzz batches (4500 pairs each). Impact: no golden or differential case has a backslash in a token; every divergence is an added deny, but the task is behaviour 0 and an added deny is behaviour 1 (hooks/CLAUDE.md). Fix: reproduce the shell's set (no backslash), or declare behaviour=1 with golden cases; either way add a differential case with a backslash token. — in_scope: yes
- [MEDIUM] M1 hooks/guard/scope.py:200-238 (Glob.expand) — The "Allowed for this step" list in the SCOPE_CHANGE_REQUIRED deny differs when a plan glob contains a trailing slash or //. Decision unchanged, message text moves. Cause 1: a literal middle component is existence-checked only when it is the last part, and a trailing / makes the real last part "", so `*/gone/` is never checked. Cause 2: a doubled slash collapses to one. Repro: allowed_files ["fixtures/*/nonexistent/"], cwd tests/: shell `  - fixtures/*/nonexistent/`, port `  - fixtures/adopt/nonexistent/` and so on, one line per directory; ["fixtures/*/lib/"]: shell fixtures/guard-port/lib/, port every fixtures/<dir>/lib/; ["fixtures//g*"]: shell fixtures//git-guard, port fixtures/git-guard; ["*/nonexistent/"]: shell as written, port lists directories. Same under C, C.UTF-8, en_US.UTF-8, en_GB.utf8, bg_BG.utf8. Fix: check every literal component, keep // as written; differential cases for `*/x/` and `a//b*`. — in_scope: yes
- [MEDIUM] M2 hooks/guard/ere.py (search, via common.py Matcher.ere_match) — Python re backtracks exponentially on user ERE patterns that glibc runs linearly, and nothing bounds it. Repro: .ai/policies/path-guard.json {"deny_patterns":["(a+)+$"]}, Bash `cat ` + a×30 + b: shell 0.05 s, port still running at 20 s. ere.search("(a|aa)+$", "a"*40+"b"), (x+x+)+y on 40 x's and (a?){30}a{30} on 30 a's all exceed 5 s; (a*)*b and ([a-z]+)+@ are fine. The leading-min-0 strip and the literal prefilter do not cover these. The hang runs to the hook timeout, then the tool is allowed (fail-open) after an unbounded stall on every call. Applies to every user pattern list (deny_patterns, protected_branches, deploy_patterns, sensitive_staging_patterns). Shipped defaults and corpus fine; timed cases pass. Fix: translate nested unbounded quantifiers into a form that cannot blow up, or stop at the 6 s clock inside the search; at minimum a timed case with a nested-quantifier pattern and a known-risks entry. — in_scope: yes
- [LOW] L1 hooks/guard/common.py:137 (Clock), hooks/ai-guard.py:58 — Clock.__init__(self, start=START) binds START at import, so ctx.clock = common.Clock() gives every check the process-start clock, not its own; contradicts the new known-risks entry and the Context docstring. Unreachable through the shims (always --only); matters only in the unregistered no-flag mode. — in_scope: yes
- [INFO] I1 hooks/guard/common.py:165-178 (parse_stream) — a payload starting with a UTF-8 BOM: jq parses it (and denies, e.g. a Read of a dotenv file); the port allows. No Claude Code or Codex session emits a BOM. — in_scope: no (inside the boundary it would be MEDIUM)
- [INFO] I2 Payload / jq_field_r — a NUL (\u0000) inside a JSON string field: the shell prints bash "ignored null byte" warnings on stderr, the port is silent; two scope cases with a NUL in notebook_path also differed. — in_scope: no
- [INFO] I3 hooks/guard/common.py (env_b("HOME")) — with HOME unset the frozen path and git guards abort at lib/ai-hook-common.sh:94 under set -u ("HOME: unbound variable") and fail open; the port decides normally and denies, e.g. git add of a dotenv file. Strictly safer, still a difference. — in_scope: no
- [INFO] I4 hooks/guard/scope.py (_parse) / ere.py — contrived forms still differ: an unterminated extglob such as `!(a|b)**(.`; POSIX-invalid `\<*`, `\>?`, `\b+` (glibc rejects, port accepts); `[^ab](^(a|))` on a string with a newline. Not listed in the accepted known-risks entry. — in_scope: no
- [INFO] I5 R15 (tests/test_imports.py) — states 3.10+ and fails on 3.10: scripts/merge-codex-config.py:31 and scripts/render-codex-agents.py:165 import tomllib (3.11+). Predates the task. — in_scope: no

## VERDICT
verdict: pass_with_findings
scope_assessment: the change stayed inside the approved plan (three exec shims, ai-guard.py plus guard/, install copy loops and tests, frozen reference fixtures, one known-risks entry; no guard text or default edited). The goal says behaviour 0, but H1 (undeclared extra denies on backslash tokens) and M1 (deny message text) show it is not fully behaviour 0; M2 is a regression for user-supplied patterns glibc handled in linear time.
```

closed by a green run: H1

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +18 −0 | Edit |
| hooks/ai-git-guard.sh | +9 −216 | Edit |
| hooks/ai-guard.py | +92 −0 | New |
| hooks/ai-path-guard.sh | +11 −1376 | Edit |
| hooks/ai-scope-guard.sh | +10 −120 | Edit |
| hooks/guard/__init__.py | +1 −0 | New |
| hooks/guard/common.py | +627 −0 | New |
| hooks/guard/ere.py | +592 −0 | New |
| hooks/guard/git.py | +227 −0 | New |
| hooks/guard/paths.py | +1466 −0 | New |
| hooks/guard/scope.py | +384 −0 | New |
| install.sh | +10 −3 | Edit |
| tests/fixtures/guard-characterization/sh-c-20k.txt | +1 −0 | New |
| tests/fixtures/guard-port/ai-git-guard-defaults.json | +28 −0 | New |
| tests/fixtures/guard-port/ai-git-guard.sh | +221 −0 | New |
| tests/fixtures/guard-port/ai-path-guard-defaults.json | +65 −0 | New |
| tests/fixtures/guard-port/ai-path-guard.sh | +1380 −0 | New |
| tests/fixtures/guard-port/ai-scope-guard.sh | +125 −0 | New |
| tests/fixtures/guard-port/lib/ai-hook-common.sh | +285 −0 | New |
| tests/test-codex-install.sh | +11 −1 | Edit |
| tests/test-guard-characterization.sh | +41 −0 | Edit |
| tests/test-install-dry-run.sh | +11 −1 | Edit |
| tests/test_ere_unit.py | +191 −0 | New |
| tests/test_guard_characterization.py | +609 −0 | New |
| tests/test_guard_differential.py | +196 −0 | New |
| tests/test_imports.py | +68 −0 | New |
| tests/test_suite_parity.py | +91 −0 | New |

+6770 −1717 lines, 27 files

## Verdict

close: closed
facts: (a) green — suite green on 21a718a4b (run 7) · (b) green — 27 changed files, all in the task's files
gate: none
confirm: none
handoffs: 4 · suite runs: 2 · review passes: 1
