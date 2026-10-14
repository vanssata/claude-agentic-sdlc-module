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
- **Status**: fixed — no longer reproduces at 8c9cf1b (179/0, T-2026-10-13-004 P1)

## Shared tree (T-2026-10-13-004): accepted risks (a)–(v)

The shared policies, agent contracts, workflows and templates moved to
`<home>/claude-agentic/ai/` (project copy = override). Plan rev 2 accepts the
following; each is open unless marked.

- **(a) Guard Bash write detection misses `rm`/`mv`/`cp` destinations on frozen paths.** `hooks/ai-path-guard.sh:273-337` matches copiers and readers by their source arguments; a destination on a task-protected path (now including `<home>/claude-agentic/ai/`) is not recognised. Worse for the shared tree: the protection pattern `(^|/)\.(claude|codex)/claude-agentic/(ai/|ai-path$)` (`hooks/ai-path-guard-defaults.json:54`) needs a path *inside* `ai/`, so `rm -rf …/claude-agentic/ai`, `mv <dir> …/claude-agentic/ai` or `cp -r <dir>/ai …/claude-agentic/` replace the whole tree unmatched even once destinations are classified (security review). Suggested fix: classify the last argument of `cp`/`mv`/`install` as a write target, and widen the pattern to `ai(/|$)` with a negative test on the bare directory, in one hooks task. Status: open.
- **(b) `.ai/agents/` is not task-protected and is now an override path.** `hooks/ai-path-guard-defaults.json:46` freezes `.ai/(policies|workflows|templates)/` only; an agent could drop `.ai/agents/reviewer.md` during a task and shadow the shared contract. Suggested fix: add `agents` to that pattern (guard data, its own task). Status: open.
- **(c) The installed tree is guarded only while a task is in flight and only in `.ai/` projects.** Parity with the installed agents and skills (M7). `ai-path --tree-hash` fingerprints the tree, and a real install prints `backup: claude-agentic/ai -> …` when the installed tree differed (it then restores it); `install.sh --dry-run` does **not** show a changed tree — it prints only the static file count. Status: accepted.
- **(d) Deny and comment text name files that became shared.** `hooks/ai-git-guard.sh:109` says `.ai/policies/release.md`; `skills/project-init/templates/project-config.toml:14` says `.ai/policies/tooling.md`. Both are frozen in this task and both files are reached through the router. Suggested fix: reword to `policies/release.md` / `policies/tooling.md` in a hooks task. Status: open.
- **(e) Gemini/Junie-only machines have no shared tree.** `install.sh` installs it only for Claude Code and Codex homes; `safety.md` and `security.md` stay project-owned (Q5=A), all 29 shared files (none of which is `safety.md` or `security.md`) are unreachable for those runtimes once 0006 deletes the copies. Status: accepted.
- **(f) This repository's own `.ai/` overrides shadow what it ships.** Its `.ai/policies|agents|workflows|templates` are edited copies; until a human runs 0006 here and resolves each override, sessions in this repo read the local versions, not `ai/`. Status: open, post-close human step.
- **(g) "treat `.ai/policies/` as binding" now covers only the 7 project-owned policies.** `instructions/stub.md:24` and `:37` (frozen). The router's `## Shared files` section carries the rule for the shared ones. Status: open (L6).
- **(h) Edited overrides get no upstream changes, and "behind" cannot be detected.** The history keeps only hashes of shared files (Q1=A), so there is no merge base; `/project-update` repeats an override hint on every run instead (M6). Status: accepted.
- **(i) Homes absent on this machine are unchecked.** `require_shared` (`skills/project-update/update.py`, `MigrationContext.require_shared`) checks every installed declared home; a teammate whose home lacks the tree is protected only by the old plugin's exit 2 on schema 6 (M2). Status: accepted.
- **(j) The no-commit rollback restores deletions only.** Without a commit of `.ai/`, the originals under `.ai/reports/project-update-<date>/original/` bring back the deleted copies, nothing else: `.ai/VERSION` stays 6 until a human writes `5` into it (README and `skills/project-update/SKILL.md` say so), and the router keeps its section. Git (`git restore --source=<commit before the migration> --staged --worktree -- .ai`) is the primary rollback; `update.py` hints when `.ai/` is dirty (M4). Status: accepted.
- **(k) Two-rename install window.** `install_shared` (`install.sh:565-588`) moves the old tree aside and the new one in; between the two `mv` calls there is no `ai/`. A reader in that instant fails and retries. Status: accepted (L3).
- **(l) Plain `--check` says "matches" while a `[shared] delete?` waits.** Same behaviour as for rules; only `--apply` lists it. Status: open.
- **(m) `/ai-init` told the agent to fill "Project specifics" in shared policies.** `skills/ai-init/SKILL.md` asked for project specifics in `database.md`, `tooling.md` and `release.md` (unconditionally for `tooling.md`); with no override, the resolver points at `<home>/claude-agentic/ai/`, unprotected outside a task, so one project's specifics would land in the policy every project reads. Status: fixed in the review remediation (R1): `/ai-init` now writes them only into a deliberate full-copy override under `.ai/policies/` and never into the shared tree. Residual: those three shared files still carry an empty `## Project specifics` placeholder, and `ai/policies/tooling.md:42` itself says "List what this project actually enables … under **Project specifics** below" — an agent reading the shared policy outside `/ai-init` is told to write into the shared file. Suggested fix: reword the shared text to name the project override (a change to `ai/`, its own task).
- **(n) The symlink check runs at plan time only.** `unsafe_target` (`skills/project-update/update.py`) is not repeated in `apply` before `os.remove`; a parent directory swapped for a symlink between plan and delete is followed (same process, same bytes required, needs write access to `.ai/`). Suggested fix: re-run `unsafe_target` just before `keep_original`/`os.remove`. Status: open.
- **(o) Environment and home detection.** `CLAUDE_AGENTIC_SHARED` is honoured outside tests (`scripts/ai-path`, `update.py`) and silently redirects every shared read; `require_shared` then checks only that tree. `require_shared` reads the Codex home from `CODEX_HOME` and ignores `CLAUDE_CONFIG_DIR`, while `install.sh` installs to `CLAUDE_DIR`/`CODEX_DIR`; a custom install location is also outside the guard pattern. Suggested fix: gate the variable behind `CLAUDE_AGENTIC_TEST=1`, and resolve homes the way `install.sh` does. Status: open.
- **(p) `ai-path` edge cases.** It takes the nearest `.ai/` above the working directory, so a nested `.ai/` created during a task (a plain `mkdir` is not detected) redirects resolution; `--root /nonexistent` exits 0 with the shared path; `os.path.isfile` follows a symlinked override that points outside the project. Status: open.
- **(q) `install_shared` keeps one backup only** (`install.sh`): a later install overwrites the previous backup of a customised tree. Status: accepted.
- **(r) Markdown is never scope-checked by the step diff.** `skills/ai-task/sensors.py:513-515` skips files in `unbudgeted_scopes` (docs) before the allowed-files check, so Step 9's README/docs change measured "0 files"; and `ai/**` scores as `docs`/T0, so a change to shipped policy text in this repository is neither re-scored nor scope-checked. Suggested fix: add `ai/**` to a pipeline scope and run the allowed-files check before the unbudgeted early exit. Status: open.
- **(s) `put_section` places the section before the first matching heading line** (`skills/project-update/update.py`, `put_section`), also one inside a fenced code block or a duplicated heading; the result passes the one-section guard silently. Needs a human edit that duplicates the follow heading. Status: open.
- **(t) A router section at the very end without a final newline** glues onto the next heading when the merge moves it (`put_section`). 0006 always writes the newline; needs a human to strip it. Status: open.
- **(u) One CRLF line makes `router_merge` rewrite the whole router in CRLF** (`crlf = b"\r\n" in ours`). Status: open.
- **(v) The template's `## Shared files` text never reaches a router that already has the section.** By design of `router_merge`; a future migration that changes the shared set must rewrite the section itself. Status: accepted.
