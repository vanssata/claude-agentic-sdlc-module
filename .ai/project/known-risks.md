# Known risks

<!-- Findings that are real but out of scope for the task that found them. This
     is where "do not fix it, write it down" lands. A human turns entries here
     into their own tasks. -->

<!--
## <short title>

- **Found**: date, by which task
- **Where**: `file:line`
- **What could go wrong**:
- **How likely / how bad**:
- **Suggested fix**: one sentence, not a plan
- **Status**: open / ticketed / accepted / fixed
-->

## `state.py approve` accepts a pty as a human

- **Found**: 2026-09-27, by T-2026-09-27-003 (WP6 F3)
- **Where**: `skills/ai-task/state.py:876-879` (`human_present()`)
- **What could go wrong**: an agent that gets past the path guard's approve regex and opens a pty (`script -qec …`) passes the terminal check and grants its own T3+ approval. `--confirm-delete` now also refuses under an agent-session marker (`adopt.human_gate()`); approve does not.
- **How likely / how bad**: needs a deliberate bypass of the hook; the approval is journalled with `via`. Bad when it happens: the one gate the pipeline may not close itself.
- **Suggested fix**: give `state.py` the same marker check as `adopt.human_gate()`.
- **Status**: open

## The approve rule is read line by line, so a backslash-newline splits it

- **Found**: 2026-09-27, by the plan review of T-2026-09-27-003
- **Where**: `hooks/ai-path-guard.sh` (`APPROVE_RE`, `HOOKRUN_RE`), `hooks/lib/ai-hook-common.sh:227-237` (`ere_match` per line)
- **What could go wrong**: `python3 …/state.py \` newline `approve --by x` is one command to the shell and two lines to the rule, so the hook allows it; `state.py`'s own tty check is then the only line.
- **How likely / how bad**: deliberate obfuscation; same class as the documented regex limit.
- **Suggested fix**: join backslash-newlines before matching, as the `--confirm-delete` rule does.
- **Status**: open

## The `--confirm-delete` hook rule needs `.ai/` in the session's cwd

- **Found**: 2026-09-27, security and adversarial review of T-2026-09-27-003
- **Where**: `hooks/ai-path-guard.sh:40` (`find_ai_root "$AI_CWD" || allow` runs before every rule)
- **What could go wrong**: a session opened in a parent directory runs `update.py /abs/project --apply --confirm-delete X`; only `adopt.human_gate()` refuses it, and an agent adding `AI_UNATTENDED=1` inline passes with `via: unattended`.
- **How likely / how bad**: needs the agent to type `AI_UNATTENDED=1` itself (the refusal no longer suggests it under a marker); irreversible deletion, originals kept under `.ai/reports/`.
- **Suggested fix**: evaluate the `--confirm-delete` rule before the `.ai/` opt-in, since it needs no project policy.
- **Status**: open

## `adopt.json` / `migration.json` carry the deletion audit but are agent-writable

- **Found**: 2026-09-27, security review of T-2026-09-27-003
- **Where**: `hooks/ai-path-guard-defaults.json` (protects only `questions.md` and `events.jsonl` under `.ai/reports/`); records written at `skills/project-update/adopt.py` (`cleanup_run`) and `update.py` (`deletions`)
- **What could go wrong**: `cleanup.via` / `deletions[].via` can be rewritten with the Write tool after the fact.
- **How likely / how bad**: deliberate tampering; the audit trail loses its weight.
- **Suggested fix**: add `.ai/reports/[^/]+/(adopt|migration)\.json$` to the protected patterns, or also journal the deletion into a protected file.
- **Status**: open

## The `--confirm-delete` hook regex is quadratic on very long lines

- **Found**: 2026-09-27, security review of T-2026-09-27-003
- **Where**: `hooks/ai-path-guard.sh` (`CONFIRM_RE`)
- **What could go wrong**: a ~120 KB padded line takes ~13 s, past the 10 s hook timeout; if the runtime treats a timeout as non-blocking the command runs (inferred, not observed). `adopt.py`'s marker check still refuses.
- **How likely / how bad**: deliberate padding only.
- **Suggested fix**: deny or skip the ERE for a line over a fixed length that contains both `update` and `--co`.
- **Status**: open

## tests/test-project-update.sh is red on the uncommitted tier-model v2 tree (found 2026-10-13, outside T1 task on test-runtime-gate.sh)
- **Where**: `tests/test-project-update.sh:79,90,109,114` against `skills/ai-init/templates/.ai/policies/risk-tiers.json` as delivered after T-2026-10-13-002 closed (post-close JSON hand-over at 17:58, after its last suite run at 17:40).
- **What could go wrong**: KNOWN FACT — at HEAD the file passes 179/0; on the working tree it fails 4: the fixture's edit to `tiers.T4.examples` now collides with the template's new T4 examples, so `--check` reports `2 need a manual merge` where the test pins `1`, the second `--apply` is not clean, and the mirror hash is not carried forward. INFERENCE — the fixture was written for the old tier table and needs the v2 shape, or the template's T4 examples should not overlap the fixture's edit.
- **How likely / how bad**: certain; blocks a green `bash tests/run-all.sh` until fixed.
- **Suggested fix**: update the fixture in `test-project-update.sh` (and the expected counts) to the seven-tier template; verify with the full suite once before committing the tier-model v2 work.
- **Status**: open
