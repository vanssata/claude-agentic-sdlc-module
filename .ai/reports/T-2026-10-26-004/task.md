# T-2026-10-26-004 — redesign 2.5: /rr-setup gains setup.py survey|check|adopt|verify — own-toolbox inventory into toolbox.md and router rows, VERIFY_COMMAND_MISSING, superpowers report line

feature · guarded · started 2026-10-26T17:54:00Z · claude

## Weight

```
scope          2  skills/rr-setup/SKILL.md referenced from 125 files
behaviour      1  keyword 'workflow' in skills/project-update/adopt-map.json
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data; plugin tooling only (declared)
novelty        1  new script following adopt.py router-row and sensors.py read_commands patterns (declared)
coverage       0  1 of 1 code files have a test
W 4 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## Plan

files: skills/rr-setup/setup.py, skills/rr-setup/SKILL.md, skills/project-update/adopt-map.json, tests/test_setup.py, tests/fixtures/setup/**, tests/test-project-adopt.sh, .ai/project/known-risks.md
tests: tests/test_setup.py, tests/test-project-adopt.sh
- s1 · skills/project-update/adopt-map.json, tests/fixtures/setup/**, tests/test-project-adopt.sh · tests/test-project-adopt.sh · done
- s2 · skills/rr-setup/setup.py, tests/test_setup.py · tests/test_setup.py · done
- s3 · skills/rr-setup/SKILL.md · tests/test_skills_surface.py, tests/test_instruction_budget.py · done
amended 2026-10-26T18:17:57Z: +.ai/project/known-risks.md — review I1 (in_scope: no) is recorded there, as /rr-review requires

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 0 | c6a1565b5 | .ai/state/logs/T-2026-10-26-004/step-1.log | no |
| 2 | step | 1 | 5eaff8738 | .ai/state/logs/T-2026-10-26-004/step-2.log | no |
| 3 | suite | 0 | a6fe0b291 | .ai/state/logs/T-2026-10-26-004/suite-3.log | no |
| 4 | e2e | 0 | a6fe0b291 | .ai/state/logs/T-2026-10-26-004/e2e-4.log | no |
| 5 | suite | 0 | b02fec7d2 | .ai/state/logs/T-2026-10-26-004/suite-5.log | no |
| 6 | e2e | 0 | b02fec7d2 | .ai/state/logs/T-2026-10-26-004/e2e-6.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — BALANCED, pass_with_findings

```
## FINDINGS

- [MEDIUM] M1 skills/rr-setup/setup.py:111-121 (`frontmatter_description`) — YAML block-scalar descriptions taken literally: `description: >-` / `description: |` yield purpose `>-` / `|`; toolbox line `>- — KNOWN FACT <path>:3` and router row job `>-`. No test covers it. — in_scope: yes
- [MEDIUM] M2 skills/rr-setup/setup.py:348-366 (`router_rows`/`add_rows`) — duplicate router rows within one batch: the same skill mirrored under `.claude/skills` and `.agents/skills`/`.codex/skills`, or a skill and command with the same name, appends two identical `/name` rows (reproduced). — in_scope: yes
- [MEDIUM] M3 skills/rr-setup/setup.py:96-101 (`walk`) — `os.walk` does not follow symlinked directories; a symlinked skill directory is silently absent from survey, toolbox.md and router (reproduced), while symlinked files are listed. — in_scope: yes
- [LOW] L1 setup.py:366 — router dedupe is substring-in-whole-file on the last cell, so prose mentioning `/review` or `policies/toolbox.md` suppresses the row; match table rows' last cell exactly. — in_scope: yes
- [LOW] L2 setup.py:369-373, 44-49 (`write`, `read_text`) — CRLF files rewritten as LF; `os.replace` via `.tmp` replaces a symlinked target with a regular file, loses mode, leaves `.tmp` on error; `verify --set` drops the template comment (consistent with sensors.read_commands). — in_scope: yes
- [LOW] L3 setup.py:179-181, tests/test-project-adopt.sh:1091-1093 — final assertion `[ sha = before ] || [ -z dirt ]` is weaker than "changes no tracked file"; `make_targets` misses multi-target lines (`a b: c`); full-tree walk before anchored glob match. — in_scope: yes
- [INFO] I1 setup.py:154-161 — symlinked files under `.claude/hooks`/`bin` are read and their first comment written into toolbox.md (committed, reaches model context); a symlink outside the repo would leak a first-line comment; `.claude/hooks/*` includes dotfiles. Threat model covers agent mistakes, not hostile trees. — in_scope: no

## VERDICT
verdict: pass_with_findings
scope_assessment: Stayed within the approved 2.5 plan row; no creep. M1–M3 and the LOWs are inside-the-boundary gaps in the new inventory, untested; none is BLOCKER/HIGH.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +9 −0 | Edit |
| skills/project-update/adopt-map.json | +31 −0 | Edit |
| skills/rr-setup/SKILL.md | +32 −5 | Edit |
| skills/rr-setup/setup.py | +541 −0 | New |
| tests/fixtures/setup/new-shop-like/Makefile | +13 −0 | New |
| tests/fixtures/setup/new-shop-like/README.md | +8 −0 | New |
| tests/fixtures/setup/new-shop-like/bin/deploy.sh | +2 −0 | New |
| tests/fixtures/setup/new-shop-like/bin/run-tests.sh | +3 −0 | New |
| tests/fixtures/setup/new-shop-like/composer.json | +1 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/agents/php-reviewer.md | +6 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/commands/release-notes.md | +1 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/hooks/block-git-push.sh | +3 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/hooks/format-php.sh | +4 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/rules/doctrine.md | +7 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/skills/deploy-staging/SKILL.md | +6 −0 | New |
| tests/fixtures/setup/new-shop-like/dot-claude/skills/sylius-fixtures/SKILL.md | +6 −0 | New |
| tests/fixtures/setup/new-shop-like/fixture-CLAUDE.md | +4 −0 | New |
| tests/fixtures/setup/new-shop-like/fixture.json | +1 −0 | New |
| tests/test-project-adopt.sh | +15 −0 | Edit |
| tests/test_setup.py | +334 −0 | New |

+1027 −5 lines, 20 files

## Verdict

close: closed
facts: (a) green — suite green on b02fec7d2 (run 5) · (b) green — 20 changed files, all in the task's files
gate: none
confirm: none
handoffs: 3 · suite runs: 2 · review passes: 1
