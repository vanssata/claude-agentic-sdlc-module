# T-2026-10-26-003 — Redesign 2.4: agents from 14 to 5 templates (Explore, log-reader, ai-discovery, ai-reviewer, architect), no -strong/-balanced twins; budgets.fan_out and budgets.direct_mode out of runtime-gate.py and the profiles

feature · full · started 2026-10-26T10:41:01Z · claude

## Weight

```
scope          2  agents/ai-context.md.tmpl referenced from 108 files
behaviour      2  weight.json:204 — install.sh retires nine agents and four Codex twins into backups/ (changes how
reversibility  0  git revert returns everything
domain         0  plugin tooling, no auth/payments/personal data (declared)
novelty        0  removal along the plan's 2.4 row; retire mechanism already exists at install.sh:569 (declared)
coverage       1  3 of 4 code files have a test
W 5 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by Ivan Kakurov at 2026-10-26T10:41:01Z — skills/CLAUDE.md: a behaviour-2 change starts in full to keep a STRONG review and the gate; chosen by the human 2026-10-26

## Plan

files: agents/ai-context.md.tmpl, agents/ai-expert.md.tmpl, agents/ai-implementer.md.tmpl, agents/ai-indexer.md.tmpl, agents/ai-planner.md.tmpl, agents/ai-release.md.tmpl, agents/ai-risk.md.tmpl, agents/ai-security.md.tmpl, agents/ai-tester.md.tmpl, agents/ai-reviewer.md.tmpl, profiles/balanced-max.json, profiles/codex-balanced-max.json, profiles/codex-plus.json, profiles/codex-pro.json, profiles/max.json, profiles/max20.json, profiles/pro.json, scripts/render-codex-agents.py, tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh, ai/agents/context.md, ai/agents/implementer.md, ai/agents/planner.md, ai/agents/release.md, ai/agents/risk.md, ai/agents/security.md, ai/agents/tester.md, ai/agents/reviewer.md, tests/test-shared-tree.sh, skills/project-update/history/index.json, hooks/runtime-gate.py, skills/usage-report/usage-report.py, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/fixtures/codex-hooks/30-agent-expert-launch.json, tests/fixtures/codex-hooks/32-subagent-stop-rate-limit.json, tests/fixtures/codex-hooks/33-subagent-stop-uncertain.json, install.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh, instructions/routing.md, ai/policies/model-routing.md, ai/policies/release.md, ai/templates/review-report.md, ai/templates/task-context.md, tests/test-instruction-budget.sh, .ai/project/known-risks.md, skills/project-update/history/blobs/40c0f81e7a110e3bc5094211e67cb6681dcc2953e81f81d7f07f0ab740640c53, skills/project-update/history/blobs/478efa93d2bd83c7c88ece72ce75cb8724ba77eccf3092541cbdbe0073be35d0, skills/project-update/history/blobs/7e5c824bb71fe5353ec8a67827145b8fbc22ecd902ade1ad3005fafeed4ffb71, skills/project-update/history/blobs/7ea8030588599b173150b9844a578a46b2669f3f8531cfd1d3843c6c1dd3c9ec, skills/project-update/history/blobs/7f713c6ecd00bc2379deda511d8bda786341dbe5f5187f3b899302d904fed6bc, skills/project-update/history/blobs/871d3d7dbeef4d7d438e9357c9bbd135f15c92c54d32e98d85aeef444e47acc0, skills/project-update/history/blobs/94da08ac6945d5614cc7918d450aab94f3aa8a929a1c8f9fa9a0a9ac51176287, skills/project-update/history/blobs/95093beb120fc6c8de08af38bed4bea5fcbc9f13e3a79782ee9cec6487c75d3f, skills/project-update/history/blobs/a213099429aff491b00e885c8d556465be2405072efbb9a3a297890a15a5b4ca, skills/project-update/history/blobs/c51cfbdea69f184f4905f351b3fd29d02429691335b71d34349a3dce829e5026, skills/project-update/history/blobs/d03d201fa398ed152e7bd9c8d2be71538c4540a870bedb4b1a8f9308345524c9, skills/project-update/history/blobs/d7146a591898984115124c83174a2c93cc080ad594f132f3d89c8b41b006c805, skills/project-update/history/blobs/e1765d5260a1a87a7fba94c55d225578b7851c5c5f9531c421029e83980097f8
tests: tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh, tests/test-shared-tree.sh, tests/test-project-update.sh, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh, tests/test-instruction-budget.sh
- s1 · agents/ai-context.md.tmpl, agents/ai-expert.md.tmpl, agents/ai-implementer.md.tmpl, agents/ai-indexer.md.tmpl, agents/ai-planner.md.tmpl, agents/ai-release.md.tmpl, agents/ai-risk.md.tmpl, agents/ai-security.md.tmpl, agents/ai-tester.md.tmpl, agents/ai-reviewer.md.tmpl, profiles/balanced-max.json, profiles/codex-balanced-max.json, profiles/codex-plus.json, profiles/codex-pro.json, profiles/max.json, profiles/max20.json, profiles/pro.json, scripts/render-codex-agents.py, tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh · tests/test-codex-agent-render.sh, tests/test-profiles.sh, tests/test-ai-task-state.sh · done
- s2 · ai/agents/context.md, ai/agents/implementer.md, ai/agents/planner.md, ai/agents/release.md, ai/agents/risk.md, ai/agents/security.md, ai/agents/tester.md, ai/agents/reviewer.md, tests/test-shared-tree.sh, skills/project-update/history/index.json · tests/test-shared-tree.sh, tests/test-project-update.sh · done
- s3 · hooks/runtime-gate.py, skills/usage-report/usage-report.py, tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh, tests/fixtures/codex-hooks/30-agent-expert-launch.json, tests/fixtures/codex-hooks/32-subagent-stop-rate-limit.json, tests/fixtures/codex-hooks/33-subagent-stop-uncertain.json · tests/test-runtime-gate.sh, tests/test-runtime-gate-codex.sh, tests/test-runtime-gate-fable.sh, tests/test-usage-report.sh · done
- s4 · install.sh, tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh · tests/test-install-dry-run.sh, tests/test-codex-install.sh, tests/test-merge-migration.sh · done
- s5 · instructions/routing.md, ai/policies/model-routing.md, ai/policies/release.md, ai/templates/review-report.md, ai/templates/task-context.md, tests/test-instruction-budget.sh, .ai/project/known-risks.md, skills/project-update/history/index.json · tests/test-instruction-budget.sh, tests/test-project-update.sh · done
amended 2026-10-26T10:45:15Z: +skills/project-update/history/blobs/40c0f81e7a110e3bc5094211e67cb6681dcc2953e81f81d7f07f0ab740640c53, skills/project-update/history/blobs/478efa93d2bd83c7c88ece72ce75cb8724ba77eccf3092541cbdbe0073be35d0, skills/project-update/history/blobs/7e5c824bb71fe5353ec8a67827145b8fbc22ecd902ade1ad3005fafeed4ffb71, skills/project-update/history/blobs/7ea8030588599b173150b9844a578a46b2669f3f8531cfd1d3843c6c1dd3c9ec, skills/project-update/history/blobs/7f713c6ecd00bc2379deda511d8bda786341dbe5f5187f3b899302d904fed6bc, skills/project-update/history/blobs/871d3d7dbeef4d7d438e9357c9bbd135f15c92c54d32e98d85aeef444e47acc0, skills/project-update/history/blobs/94da08ac6945d5614cc7918d450aab94f3aa8a929a1c8f9fa9a0a9ac51176287, skills/project-update/history/blobs/95093beb120fc6c8de08af38bed4bea5fcbc9f13e3a79782ee9cec6487c75d3f, skills/project-update/history/blobs/a213099429aff491b00e885c8d556465be2405072efbb9a3a297890a15a5b4ca, skills/project-update/history/blobs/c51cfbdea69f184f4905f351b3fd29d02429691335b71d34349a3dce829e5026, skills/project-update/history/blobs/d03d201fa398ed152e7bd9c8d2be71538c4540a870bedb4b1a8f9308345524c9, skills/project-update/history/blobs/d7146a591898984115124c83174a2c93cc080ad594f132f3d89c8b41b006c805, skills/project-update/history/blobs/e1765d5260a1a87a7fba94c55d225578b7851c5c5f9531c421029e83980097f8 — tools/build-template-history.py: the seven retired ai/agents/*.md keys are no longer shared, so their shipped versions get blobs (skills/CLAUDE.md: an ai/ change rebuilds the history)

## Questions

[questions.md](questions.md) — 0 pending

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | bf6b178a8 | .ai/state/logs/T-2026-10-26-003/step-1.log | no |
| 2 | step | 0 | 2c8960196 | .ai/state/logs/T-2026-10-26-003/step-2.log | no |
| 3 | step | 1 | 800f6bf6a | .ai/state/logs/T-2026-10-26-003/step-3.log | no |
| 4 | step | 0 | 738145a49 | .ai/state/logs/T-2026-10-26-003/step-4.log | no |
| 5 | step | 1 | cfa1a0942 | .ai/state/logs/T-2026-10-26-003/step-5.log | no |
| 6 | step | 1 | 382a9f232 | .ai/state/logs/T-2026-10-26-003/step-6.log | no |
| 7 | step | 0 | 3d348336f | .ai/state/logs/T-2026-10-26-003/step-7.log | no |
| 8 | step | 0 | 091b0260d | .ai/state/logs/T-2026-10-26-003/step-8.log | no |
| 9 | suite | 0 | 091b0260d | .ai/state/logs/T-2026-10-26-003/suite-9.log | no |
| 10 | e2e | 0 | 091b0260d | .ai/state/logs/T-2026-10-26-003/e2e-10.log | no |
| 11 | suite | 0 | 199a6e2b7 | .ai/state/logs/T-2026-10-26-003/suite-11.log | no |
| 12 | e2e | 0 | 199a6e2b7 | .ai/state/logs/T-2026-10-26-003/e2e-12.log | no |

suite passing · e2e passing · suite runs 2

## Review

### Pass 1 — STRONG, pass

```
## FINDINGS

- [MEDIUM] M1 Claude EXPERT tier silently collapses to STRONG on max/team-max `--fable no` and balanced-max now that `ai-expert` is gone, with a stale comment still claiming the old pinning (`install.sh:349-356`, `profiles/max.json` tiers.EXPERT)  in_scope: yes
  why it matters: `ai-expert` pinned `opus` at `xhigh` on those plans; the only EXPERT agent is now `architect`, which inherits the session at `high` — EXPERT = opus/high = the STRONG reviewer, and under a Sonnet session EXPERT is Sonnet. `profiles/max.json` still declares EXPERT `opus`/`xhigh`, `ai/policies/model-routing.md:18` says "xhigh where the plan allows it", and the gate asks before an "EXPERT" `architect` launch that runs on STRONG/Sonnet. `EXPERT_MODEL_LINE`, `RENDER_EXPERT_MODEL_LINE` and Claude's `EXPERT_EFFORT` (install.sh:340-355, 402-403) are now dead.
  suggested direction: either accept it in writing (known-risks + fix the stale comment/dead vars/EXPERT row for max/balanced-max) or pin `architect` to opus/`${EXPERT_EFFORT}` when Fable is off, as `ai-expert` was.
- [MEDIUM] M2 Codex EXPERT questions are now "a spawn with no agent named" (`instructions/routing.md:64`, `ai/policies/model-routing.md:43-46`), which has no read-only sandbox and no prompt contract  in_scope: yes
  why it matters: the retired `ai-expert.toml` carried `sandbox_mode = "read-only"` and a fixed "does not implement" body; a role-less `spawn_agent` gets the parent's sandbox (normally workspace-write) and only the session's ad-hoc brief, so the most expensive agent can now edit the tree during a T6/irreversible-design question — contradicting "the session implements", untested and unrecorded. (The reroute itself still works.)
  suggested direction: make the routing text require `sandbox_mode`/read-only (or a brief clause) on the EXPERT spawn if Codex accepts it per call; otherwise record in known-risks that Codex EXPERT spawns are no longer read-only.
- [LOW] L1 Dry-run prints the `architect.md` head twice (`install.sh:501-504`)  in_scope: yes
  why it matters: the `ai-expert` preview was renamed to `architect.md` next to the existing `architect.md` block; the `effort: xhigh` grep passes on either copy, so the duplicate is invisible to tests.
  suggested direction: drop one of the two blocks.
- [LOW] L2 The Codex roster test now compares role keys only, not full role specs (`tests/test-codex-agent-render.sh`)  in_scope: yes
  why it matters: it used to diff the whole `.roles` object, catching a tier/sandbox drift in codex-plus; the three profiles' `.roles` are still byte-identical, so the assertion is weaker for no reason.
  suggested direction: restore the full `.roles` diff, keep codex-balanced-max in the loop.
- [LOW] L3 Shared policy states something Codex cannot do (`ai/policies/model-routing.md:17`)  in_scope: yes
  why it matters: BALANCED row says "the review in guarded mode (`ai-reviewer`)", but Codex `ai-reviewer` is pinned to STRONG (decision 4) and the same file says a named agent runs on its pinned tier. Line 27's "in `solo`, T0–T4 run in direct mode … one STRONG review at T4" is also still old tier vocabulary.
  suggested direction: add "(STRONG under Codex)" to the BALANCED-review cell; leave the direct-mode sentence to the 2.6 deferral list.
- [LOW] L4 Legacy `running_agents`/`pending_launches` keys are now permanent in upgraded state files: `clear` stopped popping them (`hooks/runtime-gate.py:1084-1088`)  in_scope: yes
  why it matters: harmless (ignored), but nothing removes them any more, and `docs/hooks.md` still promises `clear` empties the count.
  suggested direction: keep popping the two legacy keys in `clear` for one release.
- [INFO] I1 The new known-risks entry understates its deferral as "a wrong pointer in prose, no behaviour" (`.ai/project/known-risks.md`, last entry)  in_scope: yes
  why it matters: `ai/policies/model-routing.md:27` still routes to `risk-tiers.json`, which names `ai-tester`, `ai-planner`, `ai-security`, `ai-release`, `ai-expert`; a session following it launches an agent this install no longer has and the call fails.
  suggested direction: reword "How likely / how bad" to say so.
- [INFO] I2 `retire()` moves a user-edited copy of any of the nine agents / four twins into backups without comparing it to the shipped version (`install.sh:541-548, 575-582`)  in_scope: yes
  why it matters: unlike the `reviewer.md` precedent (install.sh:718-726), edited copies are moved too; recoverable from `backups/<date>/agents/` and printed. No path retires a just-installed file.
  suggested direction: none for this task; mention it in the release note.

## VERDICT
verdict: pass
scope_assessment: The change stayed inside the approved plan and the human's four decisions. M1 and M2 are unrecorded consequences of the planned `ai-expert` removal; each needs a known-risks entry or a small follow-up, neither blocks.
```

## Changes

| File | Change | New/Edit/Delete |
|---|---|---|
| .ai/project/known-risks.md | +34 −1 | Edit |
| agents/ai-context.md.tmpl | +0 −67 | Delete |
| agents/ai-expert.md.tmpl | +0 −43 | Delete |
| agents/ai-implementer.md.tmpl | +0 −78 | Delete |
| agents/ai-indexer.md.tmpl | +0 −33 | Delete |
| agents/ai-planner.md.tmpl | +0 −87 | Delete |
| agents/ai-release.md.tmpl | +0 −53 | Delete |
| agents/ai-reviewer.md.tmpl | +25 −3 | Edit |
| agents/ai-risk.md.tmpl | +0 −66 | Delete |
| agents/ai-security.md.tmpl | +0 −65 | Delete |
| agents/ai-tester.md.tmpl | +0 −77 | Delete |
| ai/agents/reviewer.md | +33 −3 | Edit |
| ai/policies/model-routing.md | +17 −16 | Edit |
| ai/policies/release.md | +4 −3 | Edit |
| ai/templates/review-report.md | +1 −1 | Edit |
| ai/templates/task-context.md | +1 −1 | Edit |
| hooks/runtime-gate.py | +31 −137 | Edit |
| install.sh | +35 −31 | Edit |
| instructions/routing.md | +18 −17 | Edit |
| profiles/codex-balanced-max.json | +1 −82 | Edit |
| profiles/codex-plus.json | +1 −82 | Edit |
| profiles/codex-pro.json | +1 −82 | Edit |
| profiles/max.json | +3 −20 | Edit |
| profiles/max20.json | +0 −5 | Edit |
| profiles/pro.json | +3 −20 | Edit |
| scripts/render-codex-agents.py | +6 −6 | Edit |
| skills/project-update/history/index.json | +10 −5 | Edit |
| skills/usage-report/usage-report.py | +0 −5 | Edit |
| tests/test-ai-task-state.sh | +1 −1 | Edit |
| tests/test-codex-agent-render.sh | +22 −47 | Edit |
| tests/test-codex-install.sh | +13 −5 | Edit |
| tests/test-install-dry-run.sh | +24 −23 | Edit |
| tests/test-instruction-budget.sh | +1 −1 | Edit |
| tests/test-merge-migration.sh | +2 −1 | Edit |
| tests/test-profiles.sh | +13 −22 | Edit |
| tests/test-runtime-gate-codex.sh | +4 −0 | Edit |
| tests/test-runtime-gate-fable.sh | +0 −1 | Edit |
| tests/test-runtime-gate.sh | +38 −70 | Edit |
| tests/test-shared-tree.sh | +1 −1 | Edit |
| tests/test-usage-report.sh | +2 −1 | Edit |

+345 −1262 lines, 40 files

## Verdict

close: closed
facts: (a) green — suite green on 199a6e2b7 (run 11) · (b) green — 40 changed files, all in the task's files
gate: requested G1 at 2026-10-26T13:41:14Z; approved by vanssa at 2026-10-26T17:43:18Z via terminal
confirm: none
handoffs: 7 · suite runs: 2 · review passes: 1
