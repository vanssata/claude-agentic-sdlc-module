# T-2026-10-28-011 — Compact project memory, programme plan M1-M12 in one task: task id with slug, compact record and packages exported at close, recall/search/risk records, pre-push validator with enable/disable, migration, SQLite index, cleanup/restore/redact, pack, skill and doc text; files mode unchanged

feature · full · started 2026-10-28T20:07:21Z · claude

## Weight

```
scope          2  skills/ai-task/sensors.py referenced from 245 files
behaviour      2  C6: a compaction that drops an approval, answer or scope change; changes what a user project com
reversibility  0  git revert returns everything
domain         1  path-guard protected patterns and secret redaction in log excerpts; no auth, payment or personal
novelty        1  new record format, package files and a git hook; no new dependency (sqlite3 is stdlib) (declared
coverage       1  6 of 9 code files have a test
W 7 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```
override: guarded → full by agent per skills/CLAUDE.md (behaviour 2 starts full) at 2026-10-28T20:07:21Z — programme plan expects full for M4, M5, M7, M9, M11; developer chose one task, one review

## Plan

files: tools/benchmark-memory.py, skills/ai-task/memory_format.py, skills/ai-task/memory_compact.py, skills/ai-task/memory_store.py, skills/ai-task/memory_sync.py, skills/ai-task/state.py, skills/ai-task/sensors.py, hooks/ai-path-guard-defaults.json, hooks/memory-pre-push.py, skills/usage-report/usage-report.py, skills/rr-build/SKILL.md, skills/rr-review/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-plan/SKILL.md, docs/architecture.md, docs/local-memory.md, README.md, skills/ai-init/templates/.ai/state/README.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/**, docs/sdlc/specs/compact-project-memory.md, tests/test_benchmark_memory.py, tests/test_memory_characterization.py, tests/test_memory_store.py, tests/test_task_id.py, tests/test_memory_format.py, tests/test_memory_compact.py, tests/test_memory_sync.py, tests/test_memory_recall.py, tests/test_memory_risks.py, tests/test_memory_pre_push.py, tests/test_memory_migration.py, tests/test_memory_cleanup.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_end_to_end.py, tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_project_update.py, tests/fixtures/memory/**, tests/fixtures/guard-characterization/**, docs/sdlc/plans/compact-project-memory.md, tests/memory_harness.py, tests/test_guard_characterization.py, .ai/project/known-risks.md, tests/test_dialog_gate.py, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/537cccdb-a241-4ee3-b84f-b239fb086162/scratchpad/review-1.md, /tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/537cccdb-a241-4ee3-b84f-b239fb086162/scratchpad/review-2.md
tests: tests/test_benchmark_memory.py, tests/test_memory_characterization.py, tests/test_memory_store.py, tests/test_task_id.py, tests/test_memory_format.py, tests/test_memory_compact.py, tests/test_memory_sync.py, tests/test_memory_recall.py, tests/test_memory_risks.py, tests/test_memory_pre_push.py, tests/test_memory_migration.py, tests/test_memory_cleanup.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py, tests/test_end_to_end.py
- s1-bench-history · tools/benchmark-memory.py, skills/ai-task/memory_store.py, tests/fixtures/memory/**, docs/sdlc/plans/compact-project-memory.md · tests/test_benchmark_memory.py, tests/test_memory_characterization.py, tests/test_memory_store.py · done
- s2-task-id · skills/ai-task/state.py, skills/ai-task/memory_format.py · tests/test_task_id.py, tests/test_ai_task_state.py · done
- s3-format-compact · skills/ai-task/memory_format.py, skills/ai-task/memory_compact.py, tests/fixtures/memory/** · tests/test_memory_format.py, tests/test_memory_compact.py · done
- s4-export-cli-guard · skills/ai-task/memory_sync.py, skills/ai-task/state.py, skills/ai-task/sensors.py, hooks/ai-path-guard-defaults.json, tests/fixtures/guard-characterization/** · tests/test_memory_sync.py, tests/test_ai_task_state.py, tests/test_ai_task_sensors.py · done
- s5-recall-search-risks · skills/ai-task/memory_store.py, skills/ai-task/memory_format.py, skills/ai-task/memory_compact.py, skills/ai-task/memory_sync.py, skills/ai-task/state.py · tests/test_memory_recall.py, tests/test_memory_risks.py · done
- s6-prepush-enable-migrate · hooks/memory-pre-push.py, skills/ai-task/memory_sync.py, skills/ai-task/state.py, docs/sdlc/specs/compact-project-memory.md, tests/fixtures/memory/** · tests/test_memory_pre_push.py, tests/test_memory_migration.py · done
- s7-index-cleanup-pack · skills/ai-task/memory_store.py, skills/ai-task/memory_sync.py, skills/ai-task/state.py, hooks/memory-pre-push.py, skills/usage-report/usage-report.py, tools/benchmark-memory.py · tests/test_memory_store.py, tests/test_memory_cleanup.py, tests/test_memory_sync.py, tests/test_end_to_end.py · done
- s8-docs-skills · skills/rr-build/SKILL.md, skills/rr-review/SKILL.md, skills/rr-ship/SKILL.md, skills/rr-plan/SKILL.md, docs/architecture.md, docs/local-memory.md, README.md, skills/ai-init/templates/.ai/state/README.md, skills/ai-init/templates/.ai/policies/safety.md, skills/project-update/history/** · tests/test_skills_surface.py, tests/test_instruction_budget.py, tests/test_project_update.py · done
amended 2026-10-28T20:14:53Z: +tests/memory_harness.py — one scratch-project harness shared by the eleven memory test modules instead of eleven copies
amended 2026-10-28T20:33:24Z: +tests/test_guard_characterization.py — R19/A7: the two new protected patterns need corpus cases so the re-recorded golden shows the additive deny
amended 2026-10-28T20:54:56Z: +.ai/project/known-risks.md — plan M8: the three FC9 defects are recorded with 'state.py memory risk add' (files mode here), not fixed (C1)
amended 2026-10-28T21:03:39Z: +tests/test_dialog_gate.py — suite run 2: the payload goldens normalise task ids with the legacy -NNN regex only; the new id shape (R1, Q3) leaves a tail. The normaliser learns the new shape; the goldens stay byte-identical
amended 2026-10-28T21:15:02Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/537cccdb-a241-4ee3-b84f-b239fb086162/scratchpad/review-1.md — the STRONG review report is too long for an inline command; it is staged as a file and passed to 'review --report' verbatim
amended 2026-10-28T21:33:57Z: +/tmp/claude-1000/-Store-ProjectToBuild-claude-agentic/537cccdb-a241-4ee3-b84f-b239fb086162/scratchpad/review-2.md — the scoped re-review report (pass 2) is staged as a file for 'review --report', verbatim

## Questions

<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->

## G1. Approve T-2026-10-28-011 for implementation? (gate: human_approval)
asked: 2026-10-28T21:48:56Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via terminal at 2026-10-28T21:52:32Z

## Verify

| n | scope | exit | tree | log | expected_fail |
|---|---|---|---|---|---|
| 1 | step | 1 | a1f9237b4 | .ai/state/logs/T-2026-10-28-011/step-1.log | yes |
| 2 | suite | 1 | 6f5de0339 | .ai/state/logs/T-2026-10-28-011/suite-2.log | no |
| 3 | suite | 1 | 51a629274 | .ai/state/logs/T-2026-10-28-011/suite-3.log | no |
| 4 | suite | 0 | 5ac11ce4b | .ai/state/logs/T-2026-10-28-011/suite-4.log | no |
| 5 | e2e | 0 | 5ac11ce4b | .ai/state/logs/T-2026-10-28-011/e2e-5.log | no |

suite passing · e2e passing · suite runs 3

## Review

### Pass 1 — STRONG, blockers_open

```
## FINDINGS

- [BLOCKER] B1 `tests/test_dialog_gate.py:62`: the new id shape breaks an existing suite module that the task did not name. `normalise()` replaces `T-\d{4}-\d{2}-\d{2}-\d{3}`. On a new id it matches only the first three digits of HHMM, so the output reads `<TASK>0-tweak-the-widget` where the golden has `<TASK>`. **Verified by running** `python3 -I -m unittest discover -s tests -p test_dialog_gate.py`: 58 tests, 2 failures (`approval differs from its golden`, among others). `verify_command` cannot go green as the tree stands.
  - Smallest fix: make the normaliser also match `T-\d{4}-\d{2}-\d{2}-\d{4}-[a-z0-9-]+`, as `tests/test_memory_characterization.py:43` already does. The file is outside the task's files, so this needs `start --amend` (SCOPE_CHANGE_REQUIRED).
  - in_scope: yes

- [HIGH] H1 `skills/ai-task/memory_sync.py:287-295,357-372` (with `memory_compact.py:381`): export is not idempotent. When an already-sealed key is compacted again from changed local sources, a degraded second seal and a permanent `conflict` entry are added to the append-only record. Because of the conflict, V3 and V4 are then switched off for that key (`memory_sync.py:515,525-526`). **Verified twice:**
  - **Restart of a task id.** `start` → `close --abandon` → `start --task-id <same id>` → `close`. The second close compacts instance 1 again without its state (`state = ctx["state"] if last else None`). It writes a second `#1` seal with `files: []` and prints "has two different seals — kept as a conflict". `memory verify` then says ok.
  - **Cleanup on.** After `light_task`, `memory export <id>` seals the task again from `.ai/state/logs` with `0 journal lines`, `W None` and history notes. `memory show` renders that degraded seal as the task's header.
  - Several commands tell people to run `memory export <id>` (V5's fix text, close's retry line), so this path will be taken.
  - Smallest fix: in `export`, skip any key that already has a seal in the working tree. A conflict should be recorded only for seals that arrived by merge, never by re-compaction.
  - in_scope: yes

- [MEDIUM] M1 `skills/ai-task/memory_compact.py:437-444,452,459-471,558-568`: a C6 loss or mis-attribution whenever `journal_line` has replaced a line's data with `{"truncated": true}` (a line over 4 KB). Only the question text falls back to task.md. **Verified by running:**
  - A 5 000-character `start --amend --why` gives a scope entry with `added: []` and `why: None`. The full text is still in the archived `state.json` `amendments`.
  - A 5 000-character `reject --why` splits into two entries. One is G1 with actor `agent`. The other is a phantom `G?` rejection with actor `human`, `by: None`, `why: None`.
  - A 6 KB answer leaves Q1 with actor `unknown`. It also creates a phantom question `""`, which recall prints as `[answer agent] <task>/ — "?" → - by - via -`.
  - `event note --detail "…"` without `--data` keeps `text: None`, so the detail is lost.
  - Effect: `docs/local-memory.md:71` ("Human wording is stored byte for byte") overclaims.
  - Smallest fix: attribute a gate or question line that has no id to the gate or question open at that point. Take scope and override from `state.amendments` / `state.mode_override` (close sources) or from task.md. Fall back to `detail` for notes.
  - in_scope: yes

- [MEDIUM] M2 `skills/ai-task/memory_format.py:451-460` (with `state.py` `memory_risk` close, `memory_store.py:274`): a risk added and fixed in the same task still shows as open in recall. **Verified by running:** `memory risk add` then `memory risk close <rkey> --status fixed` in one task, then `close`. `memory risks` reports 0 open, but `recall` prints `[risk open RISK] … (found <task>)` at tier 0.
  - Cause: `supersedes` points at the live rid, which uses `seq` = the journal line number and `inst` 1. The exported entry gets a different rid, and `candidate_items` does not dedupe by rkey the way `History.risks` does.
  - Smallest fix: keep only the latest entry per rkey in `candidate_items`.
  - in_scope: yes

- [MEDIUM] M3 `skills/ai-task/memory_format.py:461-469`: recall reports fixed findings as residual. An earlier pass's findings are "residual" unless `review --closes` names them, and `--closes` works only for `passed_with_findings` (`state.py:3689`). **Verified by running:** review `blockers_open` with B1, fix, review `pass`, approve, close. Recall's first non-risk line is `[finding BLOCKER residual] src/widget.py:1 — … B1`, and it will stay there.
  - Smallest fix: treat findings of a pass that a later pass of the same key supersedes (verdict `pass`) as resolved.
  - in_scope: yes

- [MEDIUM] M4 `skills/ai-task/memory_sync.py:126,256,432-445` and `:89-94`: a malformed `.ai/policies/memory.json` value makes `close` exit 1 with a traceback after the task has already been archived. This breaks B4 ("one printed line, close exits 0").
  - **Verified by running:** `{"schema":"1.0"}` → `ValueError: invalid literal for int()`, close exit 1. `{"period":"week"}` → `ValueError: period must be one of…`, close exit 1. In both cases the task is already in `.ai/state/logs`.
  - `{"recall": 5}` makes `recall` crash with `AttributeError: recall_budget`. `{"mode":"Packages"}` silently means files mode.
  - Smallest fix: validate types in `load_config` and raise `MemoryError_`, and catch `ValueError` in `after_close`.
  - in_scope: yes

- [MEDIUM] M5 `skills/ai-task/memory_sync.py:569,899`: the validator starts one `git cat-file --batch` process per committed journal. Spec §D10 says "one `cat-file --batch` for every blob" and P8 says "fast". **Verified by running:**
  - On a migrated clone of this repo, `strace` counts 59 git execs for 56 journals.
  - With 2 056 committed journals, `hooks/memory-pre-push.py --tree HEAD` takes 3.0 s, for each ref of each push. Extrapolated (not measured) to 10 000 tasks, that is about 15 s.
  - Smallest fix: `tree.read_many(journals)` once, then pass a dict lookup to `check_journals`.
  - in_scope: yes

- [MEDIUM] M6 `skills/ai-task/memory_sync.py:904-907`: V6 blocks any push of a repository that commits a `*.sqlite3` file anywhere. **Verified by running:** a committed `tests/fixtures/db/app.sqlite3` gives `V6: … local data is committed — fix: git rm --cached tests/fixtures/db/app.sqlite3`, exit 1. The spec literally says "no `*.sqlite3*` in T", so this is a spec-level false positive, and it stops honest pushes on every ref.
  - Smallest fix: limit the `.sqlite3` test to paths under `.ai/`.
  - in_scope: yes

- [MEDIUM] M7 `skills/ai-task/memory_sync.py:1107-1117`: `migrate --apply` writes one package per period and ignores `package_max_bytes`.
  - **Measured** on this repo: 51 Q4 tasks give a 524 KB `2026-Q4.vanssa.*.jsonl`, about 10 KB per task.
  - **Reasoned:** a project with more than about 200 legacy tasks in one period goes over twice the cap. V8 then refuses the push of the migration commit, and V8's fix text ("the next close opens a new batch; memory pack folds old ones") does not apply.
  - Smallest fix: rotate to a new batch name when the rendered package would exceed `package_max_bytes`.
  - in_scope: yes

- [MEDIUM] M8 `skills/ai-task/memory_sync.py:44-45,926-934`, `bin/riskrails.js:1283`: on a Codex-only install the pre-push check silently fails open.
  - `codexHookFiles()` is a fixed list of four hooks and does not include `memory-pre-push.py`. The skills tree is copied, so `VALIDATOR` resolves to `~/.codex/hooks/memory-pre-push.py`, which does not exist. With no `~/.claude/hooks/` copy either, the shim prints "this push is not checked" and exits 0. Meanwhile `memory enable` says `installed` and `memory status` says `current`.
  - The same applies on the plugin route once the versioned cache directory the shim names is replaced.
  - The spec's "the installer needs no change" (§D10) is wrong for Codex. **Reasoned from the installer code**, not run.
  - Smallest fix: add the validator to `codexHookFiles()`, and have `hook_state` report "validator missing" when none of the shim's paths exist.
  - in_scope: yes

- [LOW] L1 `skills/ai-task/memory_sync.py:517-519`: the V3 fix text for a new-shape key says "keep one seal". That is impossible, because V2 refuses the removal. **Verified:** after a same-id two-clone merge, the working way out is `memory export <id>`, which records the conflict. That push then succeeded.
  - Smallest fix: name `memory export <id>` in the fix text.
  - in_scope: yes

- [LOW] L2 `skills/rr-ship/SKILL.md:97-98`: the suggested commit still adds only the task's files and `.ai/reports/<id>/`. In packages mode V5 then refuses the push. V5's fix ("state.py memory export") is a no-op when the seal is only uncommitted, so it misleads. With cleanup on, the task.md that the PR body is built from has also moved.
  - Smallest fix: add `.ai/memory/` to the suggested `git add` in packages mode.
  - in_scope: yes

- [LOW] L3 `skills/ai-task/memory_sync.py:343-346`: two concurrent closes in one clone. The first takes both outbox files, so the second close prints neither a `record:` line nor a failure line, although its task is sealed. **Reasoned.**
  - Smallest fix: report keys that are already sealed as sealed.
  - in_scope: yes

- [LOW] L4 docs and templates:
  - `docs/local-memory.md:51` says enable-before-migration "would make every push fail V5 for the legacy tasks". V5 skips unsealed legacy ids (`memory_sync.py:572`).
  - The shipped templates `skills/ai-init/templates/.ai/policies/safety.md:33` and `.ai/state/README.md:24` point at `docs/local-memory.md`, which a user project does not have.
  - in_scope: yes

- [INFO] I1 `skills/ai-task/memory_format.py:71`: `decision_*` / `consent_*` lines are dropped, as spec §D3 says. That spec predates T-2026-10-28-010. Since then the human's commit and push consent is a dialog record, and only `pick` survives on approval, answer or override entries.
  - in_scope: yes

- [INFO] I2 `skills/ai-task/state.py` `memory_migrate` / `memory_restore`: these do not take the human route.
  - `migrate --apply [--risks]` replaces the committed `known-risks.md` with a stub (a backup tar is kept in `.ai/local`).
  - `restore` writes `.ai/reports/<id>/task.md` and `events.jsonl`, which are guard-protected paths.
  - This matches the plan's decision, which makes only `--move-logs` human-route. Plan G2 nevertheless calls the whole migration a human act.
  - in_scope: yes

## VERDICT
verdict: blockers_open
scope_assessment: The change stays inside the plan's "Executed as one task" decisions (M2 without the refactor, M10 included). The blocker is outside the named files: `tests/test_dialog_gate.py` needs a scope amendment. H1 and M1–M8 are inside the task's own modules.
```

### Pass 2 — STRONG, pass

```
## FINDINGS

- [MEDIUM] M9 (new, introduced by the H1 fix) `skills/ai-task/memory_sync.py:375-381` together with the V4/V5 fix text at `:592-595` — closed, but `export` now skips every key that already has a seal in the tree (`if key in sealed_here: continue`). That also skips the repair case: the seal is present, one of its entries is missing, and the sources are unchanged. Before the fix, re-compaction re-added the missing rids, which are deterministic, and that is exactly what V4 ("'state.py memory export <id>' re-exports it") and V5 tell the user to run. Run in a scratch repo (`scratchpad/probe12.py`):
  - Setup: enable, then `light_task`, then delete the `weight` line from the package and leave the seal in place.
  - `memory verify` reports V4 and V5.
  - `memory export <id>` exits 0 with "exported: +0 entries".
  - `memory verify` still reports V4 and V5, and `memory-pre-push --tree HEAD` exits 1.
  - The only way out left is `git checkout` of the package or `--no-verify`.
  - Smallest fix: skip only when the fresh compaction's seal rid differs from the stored seal's rid (changed sources, which is H1). When the rids are equal, write the outbox as before, and rid dedupe turns it into a pure repair. Pin it with a test: drop an entry, `export`, then `verify` is ok.
  in_scope: yes

- [MEDIUM] M1 `skills/ai-task/memory_compact.py:481-500` — not fully closed.
  - The listed cases are fixed. Scope `why` is recovered from state and capped to 2000 with `truncated:["why"]`. The 5 000-character reject gives one G1 entry (actor human, by vanssa, full `why`), with no phantom `G?`, and its shape matches the short-reject case (`probe10.py`). The 6 KB answer is a single Q1, the same shape as the short answer (`probe9.py`). A detail-only note keeps its detail.
  - Still open: a note written with `--data` whose line is cut and that has no detail. Re-running `probe1.py`, `event note --data '{"kind":"decision","text":"T"*5000}'` gives `text: None, note_kind: None, why: None` with no `unrecorded` and no `truncated`.
  - So the decision disappears from recall without a trace. That contradicts `docs/local-memory.md:76-78` ("a field that neither holds is listed in `unrecorded` — never filled in").
  - When the line has a detail, `note_kind` and `why` are also lost and not listed.
  - `test_cut_lines_are_recovered_never_invented` does not cover this input.
  - Smallest fix: when `cut_line(data)`, pass `unrecorded` = the note fields still None (`note_kind`, `text`, `why`) to `b.add("note", …)`, and add that case to the test.
  in_scope: yes

- [LOW] L5 (new, from H1/L3) `skills/ai-task/memory_sync.py:510-517`, `skills/ai-task/state.py:4357-4362` — the close and export output misstates which keys were newly sealed.
  - Restart of an id (`probe6.py`): the second close prints `record: …p472.jsonl (+3 entries, <id> sealed, coverage 5/5 lines)` for #1, which was sealed at the abandon, as well as the line for #2. `after_close` uses "already sealed" only when nothing at all was written.
  - `memory export <id>` on a sealed key prints `record: .ai/memory/- (<id>#1 sealed, coverage 0/0 lines)` (`probe4.py`). The path is a dash, and the coverage belongs to the discarded re-compaction.
  - In the two-clone case, `memory export` never says that it recorded a conflict, which is what L1's new fix text promises.
  - Smallest fix: return the already-sealed keys separately from the newly sealed ones, print "already sealed" for the former in both places, and print `result.conflicts` in `memory_export`.
  in_scope: yes

- [INFO] closed: B1. `test_dialog_gate.py` ran: 58 tests OK. The normaliser at line 62 matches both id shapes, and no golden changed.
  in_scope: yes
- [INFO] closed: H1. Re-ran the restart probe (`probe6.py`): seals #1 abandoned and #2 closed, no conflict, `verify` ok. Re-ran the cleanup export probe (`probe4.py`): no second seal, `verify` ok. Re-ran the two-clone probe (`probe3.py`): V3 appears, `export` records the conflict, `verify` ok, push 0. `test_memory_sync`: 24 tests OK. M9 and L5 above are what the fix introduced.
  in_scope: yes
- [INFO] closed: M2. `probe7.py` gives 0 open risks and recall shows no `[risk open]` line.
  in_scope: yes
- [INFO] closed: M3. `probe8.py`: recall shows no residual B1 after a later `pass`.
  in_scope: yes
- [INFO] closed: M4. `probe2.py`: all five malformed policies give close exit 0 with one line, the task is archived, and recall exits 2 with one line instead of a traceback.
  in_scope: yes
- [INFO] closed: M5. `validate_range` at `memory_sync.py:963` reads with one `read_many`, and `test_memory_pre_push` passes (23 tests OK).
  in_scope: yes
- [INFO] closed: M6. `:972` applies the `.sqlite3` rule under `.ai/` only.
  in_scope: yes
- [INFO] closed: M7. Rotation keeps whole tasks per batch (`:1195-1202`), and `test_memory_migration` passes (7 tests OK). Header bytes are not counted, but they can only trip the V8 warning, not the twice-the-cap failure.
  in_scope: yes
- [INFO] closed: M8. Ran a simulated Codex-only home (`probe11.py`): `~/.codex/skills/ai-task` only, no hooks. The shim falls through to `memory_sync.py` and runs it under `-I` (the module puts its own directory on `sys.path`). A clean push exits 0, and a dropped record exits 1 with V2/V4/V5. `hook_state` reports "validator missing" when no candidate exists.
  in_scope: yes
- [INFO] closed: L1. Seen in `probe3.py` output.
  in_scope: yes
- [INFO] closed: L2. `rr-ship/SKILL.md` adds `.ai/memory/` to the suggested commit.
  in_scope: yes
- [INFO] closed: L3. Reasoned: `:400-402`.
  in_scope: yes
- [INFO] closed: L4. `docs/local-memory.md:49-52` is corrected, and the templates point at "the plugin's".
  in_scope: yes
- [INFO] closed: I1, I2. Documented in `docs/local-memory.md` §Limits (`:208-214`), as the plan decided.
  in_scope: yes
- Also run and OK: `test_memory_compact`, `test_memory_recall`, `test_memory_characterization`, `test_memory_format`, `test_memory_risks`, `test_memory_cleanup`. `tests/run-all.sh` was not run.

## VERDICT
verdict: pass
scope_assessment: The fixes stay inside the task's files plus the amended `tests/test_dialog_gate.py`, and `bin/riskrails.js` is unchanged as FC3 says. M9 is a regression the H1 fix introduced in `export` itself. It sits within the task's modules and should be fixed with a pinning test before approval, even though by severity it does not move the verdict.
```

## Changes

measured at close

## Verdict

close: open — the human approves in their own terminal, then 'state.py close' again
facts: (a) green — suite green on 5ac11ce4b (run 4) · (b) green — 71 changed files, all in the task's files
gate: requested G1 at 2026-10-28T21:48:56Z; approved by vanssa at 2026-10-28T21:52:32Z via terminal
confirm: none
handoffs: 9 · suite runs: 3 · review passes: 2
