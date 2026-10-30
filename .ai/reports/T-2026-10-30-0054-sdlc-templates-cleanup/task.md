# T-2026-10-30-0054-sdlc-templates-cleanup — rr-setup --update: plugin supplies the sdlc TEMPLATE.md files, proposes deleting old logs and stale unclosed tasks; three templates refreshed

feature · guarded · started 2026-10-30T00:54:41Z · claude

## Weight

```
scope          2  skills/ai-init/templates/.ai/policies/security.md referenced from 161 files
behaviour      1  keyword 'transition' in skills/ai-init/templates/.ai/policies/testing.md
reversibility  0  git revert returns everything
domain         1  UNKNOWN — neither measured nor declared
novelty        1  UNKNOWN — neither measured nor declared
coverage       0  2 of 2 code files have a test
W 5 → guarded   hints none · unknown domain, novelty · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
batch: on by Ivan Kakurov at 2026-10-30T00:54:41Z — /rr-build-all: обнови трите templates, TEMPLATE.md от плъгина, чистене при rr-setup

## Plan

files: skills/project-init/templates/sdlc-README.md, skills/ai-init/templates/.ai/policies/security.md, skills/ai-init/templates/.ai/policies/testing.md, hooks/project-scaffold.py, tests/fixtures/scaffold-port/project-scaffold.sh, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py, skills/project-update/update.py, tests/test_project_update.py, skills/rr-spec/SKILL.md, skills/rr-plan/SKILL.md, skills/rr-setup/SKILL.md, docs/sdlc/README.md, docs/sdlc/intent/TEMPLATE.md, docs/sdlc/specs/TEMPLATE.md, docs/sdlc/plans/TEMPLATE.md, docs/sdlc/adr/TEMPLATE.md, skills/project-update/history/index.json, skills/project-update/history/blobs/**, tests/test_merge_migration.py, README.md
tests: tests/test_project_update.py, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py
- s1 · skills/project-init/templates/sdlc-README.md, skills/ai-init/templates/.ai/policies/security.md, skills/ai-init/templates/.ai/policies/testing.md · no tests · done
- s2 · hooks/project-scaffold.py, tests/fixtures/scaffold-port/project-scaffold.sh, tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py · tests/test_scaffold_idempotency.py, tests/test_scaffold_differential.py · done
- s3 · skills/project-update/update.py, tests/test_project_update.py · tests/test_project_update.py · done
- s4 · skills/rr-spec/SKILL.md, skills/rr-plan/SKILL.md, skills/rr-setup/SKILL.md · no tests · done · after s3
- s5 · docs/sdlc/README.md, docs/sdlc/intent/TEMPLATE.md, docs/sdlc/specs/TEMPLATE.md, docs/sdlc/plans/TEMPLATE.md, docs/sdlc/adr/TEMPLATE.md, skills/project-update/history/index.json, skills/project-update/history/blobs/** · no tests · done · after s1
amended 2026-10-30T00:58:44Z: +tests/test_merge_migration.py — s3: the scaffold/update no longer creates docs/sdlc/*/TEMPLATE.md; CREATED at :26 lists them
amended 2026-10-30T01:09:36Z: +README.md — testing.md: the README test count is measured from verify's Ran N line and updated in the same commit (979 -> 1009)

## Questions

none

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | suite | 0 | 3b1ee06eb | .ai/state/logs/T-2026-10-30-0054-sdlc-templates-cleanup/suite-1.log | no |
| 2 | e2e | 0 | 3b1ee06eb | .ai/state/logs/T-2026-10-30-0054-sdlc-templates-cleanup/e2e-2.log | no |
| 3 | step | 0 | b6b6922c0 | .ai/state/logs/T-2026-10-30-0054-sdlc-templates-cleanup/step-3.log | no |
| 4 | e2e | 0 | b6b6922c0 | .ai/state/logs/T-2026-10-30-0054-sdlc-templates-cleanup/e2e-4.log | no |

suite passing · e2e passing · suite runs 1

## Review

### Pass 1 — BALANCED, pass

```
## FINDINGS
- [MEDIUM] M1 update.py:1042-1062,1099-1101 — cleanup treats "no task_closed in the journal" as unclosed; T-2026-10-28-010 (gate approved, committed 520e065) and -012 (committed ee33d0d) would be proposed for deletion from 2026-11-04; a torn task_closed line also reads as unclosed; the archived logs/<id>/state.json result is never consulted. Direction: state.json result authoritative; exclude gate_approved journals or list them apart. in_scope: yes
- [MEDIUM] M2 update.py:1556-1558, deletion_hint :1118 — comment and hint say git rolls back a [cleanup] deletion; .ai/state/logs/** is git-ignored and keep_original is skipped, so log and abandoned-task state.json deletion is unrecoverable. Direction: say so in the rows and rr-setup text; fix the comment; keep the abandoned task's state.json. in_scope: yes
- [MEDIUM] M3 update.py:1037,1110-1112, rr-setup/SKILL.md:138-146 — one --confirm-delete confirms migration, [sdlc] and [cleanup] deletions together; a schema migration cannot be settled without accepting the irreversible cleanup. Direction: separate opt-in for [cleanup]. in_scope: yes
- [LOW] L1 sdlc-README.md:24-27 (and docs/sdlc/README.md) — template path relative to the plugin install, intent.md omitted, ADR template has no usable pointer. in_scope: yes
- [LOW] L2 update.py:1118-1122 — "commit .ai/ first" hint fires on nearly every run because of [cleanup] items. in_scope: yes
- [LOW] L3 tests/test_project_update.py:1585-1678 — unpinned: no original/ copy for [cleanup], legacy current.json / unreadable state.json protection, detail-only abandonment, symlink skip, CRLF TEMPLATE.md, torn task_closed line. in_scope: yes
- [LOW] L4 update.py:1074 — malformed RISKRAILS_NOW raises ValueError, exit 1 read as "update pending". in_scope: yes
- [INFO] I1 update.py:1083-1090,1586 — symlinked reports/logs <id> dir lets a confirmed apply delete outside the project. in_scope: no
- [INFO] I2 update.py:745-760 — every dry run/--check hashes every closed task's logs. in_scope: no
## VERDICT
verdict: pass
scope_assessment: within the plan plus the recorded amendment (tests/test_merge_migration.py); no refactoring mixed in; M1-M3 are design gaps for the register or a follow-up.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| README.md | +1 −1 | Edit |
| docs/sdlc/README.md | +5 −3 | Edit |
| docs/sdlc/adr/TEMPLATE.md | +0 −29 | Delete |
| docs/sdlc/intent/TEMPLATE.md | +0 −35 | Delete |
| docs/sdlc/plans/TEMPLATE.md | +0 −25 | Delete |
| docs/sdlc/specs/TEMPLATE.md | +0 −30 | Delete |
| hooks/project-scaffold.py | +1 −5 | Edit |
| skills/ai-init/templates/.ai/policies/security.md | +7 −1 | Edit |
| skills/ai-init/templates/.ai/policies/testing.md | +5 −0 | Edit |
| skills/project-init/templates/sdlc-README.md | +20 −14 | Edit |
| skills/project-update/history/blobs/079a91f976ad69b5cf49ccb9a28849576e4735ddd9485fc26599e528a69fd2f4 | +30 −0 | New |
| skills/project-update/history/blobs/0ef4a360c76da290173dea0f8073949cb0f8113710a38df95acae5d96bdd1286 | +123 −0 | New |
| skills/project-update/history/blobs/6a3be0e624e5ad91e44d08857b7183ee53b7903e1e8d56ff196dbc9dde271e4a | +75 −0 | New |
| skills/project-update/history/index.json | +6 −3 | Edit |
| skills/project-update/update.py | +156 −10 | Edit |
| skills/rr-plan/SKILL.md | +3 −1 | Edit |
| skills/rr-setup/SKILL.md | +6 −1 | Edit |
| skills/rr-spec/SKILL.md | +4 −2 | Edit |
| tests/fixtures/scaffold-port/project-scaffold.sh | +1 −4 | Edit |
| tests/test_merge_migration.py | +7 −2 | Edit |
| tests/test_project_update.py | +95 −0 | Edit |
| tests/test_scaffold_idempotency.py | +5 −2 | Edit |

+550 −168 lines, 22 files

## Verdict

close: closed
facts: (a) green — documents only since run 1 (1 files: README.md); doc_tests green in run 3 on b6b6922c0 · (b) green — 22 changed files, all in the task's files
gate: none
confirm: none
handoffs: 5 · suite runs: 1 · review passes: 1
