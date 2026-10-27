# T-2026-10-26-007 — Redesign 3.2: port project-scaffold.sh and scaffold-ai.sh to Python behind exec shims, no behaviour change

refactoring · guarded · started 2026-10-26T22:16:04Z · claude

## Weight

```
scope          2  hooks/project-scaffold.sh matches hot_paths hooks/**
behaviour      1  keyword 'workflow' in .ai/project/known-risks.md
reversibility  0  git revert returns everything
domain         0  project scaffolding; no secrets, auth, payments or data (declared)
novelty        1  repeats the 3.1 exec-shim port pattern on two new scripts (declared)
coverage       1  3 of 4 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: tests/fixtures/scaffold-port/project-scaffold.sh, tests/fixtures/scaffold-port/scaffold-ai.sh, tests/test_scaffold_differential.py, hooks/project-scaffold.sh, hooks/project-scaffold.py, skills/ai-init/scaffold-ai.sh, skills/rr-setup/scaffold_ai.py, tests/test_scaffold_idempotency.py, .ai/project/known-risks.md
tests: tests/test_scaffold_differential.py, tests/test_scaffold_idempotency.py, tests/test-scaffold-idempotency.sh, tests/test_suite_parity.py
- s1 · tests/fixtures/scaffold-port/project-scaffold.sh, tests/fixtures/scaffold-port/scaffold-ai.sh, tests/test_scaffold_differential.py · tests/test_scaffold_differential.py · done
- s2 · hooks/project-scaffold.sh, hooks/project-scaffold.py · tests/test_scaffold_differential.py, tests/test-scaffold-idempotency.sh · done
- s3 · skills/ai-init/scaffold-ai.sh, skills/rr-setup/scaffold_ai.py · tests/test_scaffold_differential.py, tests/test-scaffold-idempotency.sh · done
- s4 · tests/test_scaffold_idempotency.py, .ai/project/known-risks.md · tests/test_scaffold_idempotency.py, tests/test_suite_parity.py · done

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | 35eaa5072 | .ai/state/logs/T-2026-10-26-007/step-1.log | no |
| 2 | step | 0 | 7466b0d0d | .ai/state/logs/T-2026-10-26-007/step-2.log | no |
| 3 | step | 0 | 771ab857c | .ai/state/logs/T-2026-10-26-007/step-3.log | no |
| 4 | suite | 0 | 771ab857c | .ai/state/logs/T-2026-10-26-007/suite-4.log | no |
| 5 | e2e | 0 | 771ab857c | .ai/state/logs/T-2026-10-26-007/e2e-5.log | no |
| 6 | suite | 0 | 82048a5d7 | .ai/state/logs/T-2026-10-26-007/suite-6.log | no |
| 7 | e2e | 0 | 82048a5d7 | .ai/state/logs/T-2026-10-26-007/e2e-7.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS
Method: frozen scripts vs live shims through the test module's own harness (`run_variant`) on ~190 extra cases per script under C, en_US.UTF-8, C.UTF-8; six install-layout variants (symlinked .codex, symlinked ai-init, symlinked hooks, relative invocation); 17 PWD/symlink scenarios; and mutation testing of tests/test_scaffold_differential.py against a mutated copy of the port. The four named tests pass as-is. Everything listed as probed, plus the install-path/template-env/.gitignore/VERSION/managed-block/sort/mode/symlink items, matched except as below.

- [MEDIUM] M1 hooks/project-scaffold.py:80 and skills/rr-setup/scaffold_ai.py:84 (`logical_cd`) — `cd` reimplemented as normpath+isdir diverges from bash's `cd` in three ways, and it can write where bash refused, or refuse where bash went to HOME. in_scope: yes
  Repro 1: arg `<proj>/nonexist/..` → bash: `cd: …/nonexist/..: No such file or directory`, exit 1, empty tree; port: normalises to `<proj>` and scaffolds it (exit 0, full created list). Bash's cd checks that the component before `..` exists.
  Repro 2: arg `<proj>/f/..` where `f` is a regular file → bash: `Not a directory`, exit 1; port: scaffolds `<proj>`.
  Repro 3: leading-dash argument (`-x`, `-h`, `--runtimex`) → bash: `cd: -x: invalid option`, exit 2; port treats it as a relative path, so exit 1 (or exit 0 and scaffolds if a dir named `-x` exists; shell exits 2 there).
  Repro 4: arg `--` → bash `cd --` goes to `$HOME` and scaffolds it; port exits 1 `cd: --: No such file or directory`.
  None of these is in the known-risks entry (it lists only CDPATH and `cd -`). Repros 1–2 are the worse direction: a write where bash refused.
  Suggested direction: stat each component before `..`; refuse a leading `-` with exit 2 and bash's text (or add these as differential cases and record the remainder in the known-risks entry).

- [LOW] L1 hooks/project-scaffold.py:213 — reads `gitignore.snippet` unconditionally, before the marker check; the shell `cat`s it only when appending. in_scope: yes
  Repro: AI_PROJECT_TEMPLATES points to a template dir without `gitignore.snippet`, project already scaffolded (.gitignore contains `.claude/settings.local.json`). Frozen: exit 0 "nothing to do". Port: `project-scaffold: [Errno 2] No such file or directory: '…/gitignore.snippet'`, exit 1. (scaffold_ai.py:193 reads it inside the `if` — correct.)
  Suggested direction: read the snippet only when appending.

- [LOW] L2 test gap — the differential test is vacuous for several decisions. Mutations of a copy of the port that left the test green: swapping AI_PROJECT_TEMPLATES/CLAUDE_ROUTING_TEMPLATES precedence (no case sets both); removing the `\0` in the "last byte is NUL" newline rule (either script; no NUL case); removing `.rstrip("\n")` on the stdin cwd; disabling `logical_pwd` (inherited symlinked $PWD — every case runs with a physical PWD; the live code does match the shell for a symlinked PWD, checked in ten scenarios, only the pin is missing); the `find` symlink handling in `template_files` (top-level and per-file). Caught: chmod, bytes-vs-locale sort, .codex detection, VERSION skip, block regex, trailing comma, .gitkeep content, mkdir. in_scope: yes
  Suggested direction: cases for both template vars set, NUL tail on .gitignore and CLAUDE.md, cwd with trailing newline, symlinked cwd with `.`.

- [LOW] L3 — project name containing a newline (dir `a\nb`): shell → `sed: unterminated 's' command`, exit 1, and an empty docs/sdlc/constitution.md left behind; port → exit 0, name substituted. Arguably better, but a visible difference and untested. in_scope: yes

- [LOW] L4 skills/rr-setup/scaffold_ai.py:63 and hooks/project-scaffold.py:59 (`stdin_cwd`) — `cwd` in the hook JSON with a lone surrogate. `{"cwd":"\ud800"}`: old `print()` raised inside the try → fell back to $PWD and scaffolded (exit 0); port keeps the value, `os.fsencode` raises UnicodeEncodeError uncaught by main() → traceback, exit 1. `{"cwd":"\udce9"}` under en_US.UTF-8: old fell back the same way; port exits 1 `cd: \xe9: No such file or directory` (under C the shell also fails, with `$'\351'`). Contrived: Node-produced JSON doesn't emit a lone surrogate for a real dir. in_scope: yes

- [LOW] L5 — messages/stderr with the same exit codes: NUL as last byte of .gitignore/CLAUDE.md → bash prints `warning: command substitution: ignored null byte in input` on stderr, port silent. Failed writes (.gitignore is a directory, read-only target, .claude/plans is a file, mkdir under a 555 dir, umask 0277/0377/0500): the tool's message (`mkdir: Already exists`, `cp: cannot create …`) becomes `<name>: [Errno N] …`; exit code and created tree match. The failed-write class is accepted in known-risks; the NUL warning and the extra argument shapes are not named there. in_scope: yes

- [INFO] I1 skills/ai-init/scaffold-ai.sh (exec line) — the shim now depends on `../rr-setup/scaffold_ai.py` resolving via the kernel's physical `..`. If `ai-init` is a symlink to a dir whose parent has no `rr-setup`, it fails with python's "can't open file" (exit 2); the old script ran standalone. A copy/install of `ai-init` alone, or the shim without its .py, now breaks even with CLAUDE_AGENTIC_TEMPLATES set; hooks/project-scaffold.sh likewise needs its sibling .py. install.sh copies all skills and all hooks/*.py, so a normal install is fine; Codex still gets no project-scaffold.sh (already noted as pre-existing). in_scope: no

- [INFO] I2 — `python3 -I` ignores PYTHONIOENCODING/PYTHONUTF8, which the old `python3 -c` stdin parse honoured. in_scope: no

## VERDICT
verdict: pass_with_findings

No in-scope BLOCKER or HIGH. M1 is the worth-fixing item (pin it with differential cases or add it to the accepted-risk entry); L1 is a one-line fix; L2 means the differential test would stay green on several regressions in the named decisions, so it protects less than its docstring claims.

scope_assessment: change stays inside the plan's files; shims and frozen fixtures match the plan; no production code outside the plan touched.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +10 −0 | Edit |
| hooks/project-scaffold.py | +292 −0 | New |
| hooks/project-scaffold.sh | +6 −120 | Edit |
| skills/ai-init/scaffold-ai.sh | +6 −116 | Edit |
| skills/rr-setup/scaffold_ai.py | +303 −0 | New |
| tests/fixtures/scaffold-port/project-scaffold.sh | +128 −0 | New |
| tests/fixtures/scaffold-port/scaffold-ai.sh | +120 −0 | New |
| tests/test_scaffold_differential.py | +318 −0 | New |
| tests/test_scaffold_idempotency.py | +234 −0 | New |

+1417 −236 lines, 9 files

## Verdict

close: closed
facts: (a) green — suite green on 82048a5d7 (run 6) · (b) green — 9 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 2 · review passes: 1
