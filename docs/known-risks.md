# Known risks

What version 3.0 knowingly does **not** protect against. Each entry says what
can happen, why it was left that way, what limits the damage and what you
should do. None is a secret. Each was found in a review or a spec, then
accepted or deferred with a written reason in the record named under
**Source**. The project's own open findings, sixty-odd on 2026-10-30, are in
the compact record: `state.py memory risks` lists them.

## The guards are a tripwire, not a sandbox

**Risk.** Every guard rule is a regex over a command line or a path. A process
that wants to get past it can do so: read `.env` through a Python one-liner
the scanner does not recognise, build a command from variables, pipe base64
into a shell, or use a tool that is not on the hook path at all.
**Why it stays.** A real boundary needs an OS-level sandbox. A hook that runs
before a tool call cannot be one. The guards exist to stop the *honest
mistake* — reading `.env` to check a value, editing one file too many.
**Limits.** The scanner catches the common obfuscations: quoted flags,
`--opt=value`, top-level `sh -c` and `eval`, interpreter one-liners that
mention a secret or a control file, and commands over 4 KB that name a guarded
path.
**What to do.** Keep production secrets off the developer machine, turn on
server-side branch protection, and review every diff before merge. Those are
the real backstops.
**Source.** `docs/hooks.md`, "What these guards are, and are not";
`.ai/policies/safety.md`, the threat model.

## Human approval can be forged by a determined process

**Risk.** `state.py approve` refuses to run without a terminal on stdin, and
the path guard refuses it from an agent session. An obfuscated invocation that
gets past the regex and also allocates a pseudo-terminal can still grant the
approval. With the dialog on, the approval is the human's pick in the runtime's
own question tool; the gate records that pick in `.ai/state/consent.jsonl` and
runs the command once — a process that writes the ledger itself is past the
same regex.
**Why it stays.** The same regex limit as above. The check makes self-approval
deliberate and visible, not impossible.
**Limits.** `approve` refuses when no gate was requested, and a changed tree
invalidates an approval. Every approval is journalled with who, when and how
(`via: terminal`, `dialog` or `unattended`); the ledger is write-protected by
the path guard and dropped from the compact record, so the pick id survives
only on the approval it produced.
**What to do.** Read the task's `task.md` §Verdict, or `state.py consent
audit`, before you merge a full-mode change. An approval you do not remember
giving is a finding.
**Source.** WP2 security review; `docs/sdlc/specs/command-choice-dialog.md`
§Open questions; `hooks/guard/paths.py`, `hooks/guard/dialog.py`.

## The deletion gate stops an agent's command, not an agent's script

**Risk.** `--confirm-delete` of `update.py` (`--apply`, and `--adopt --cleanup
--apply`) is refused two ways: the path guard denies an agent `Bash` command
that runs `update.py` with `--apply` and any prefix of `--confirm-delete`, in
every directory; and `adopt.py` refuses the flag whenever an agent-session
marker (`CLAUDECODE`, or Codex's `CODEX_THREAD_ID`, `CODEX_SESSION_ID`,
`CODEX_CI`, `CODEX_SANDBOX`, `CODEX_SANDBOX_NETWORK_DISABLED`,
`CODEX_VERSION`) is in its environment, even with a terminal on stdin. The hook
matches spellings, so a script file written with the Write tool, arguments held
in a variable, command substitution, `xargs`, inline `-c` code that imports
`update.py`, or a renamed copy of it are past it. Each still needs the markers
unset plus a pty, or `AI_UNATTENDED=1`, to pass `adopt.py`, which is
deliberate, not an honest mistake.
**Why it stays.** The hook sees a command line, not what a file it runs will do.
**Limits.** The record says why the gate passed: `adopt.json` `cleanup.via` and
`migration.json` `deletions[].via` are `terminal` or `unattended`. A human
typing through Claude Code's `!` prefix, or in a shell started from an agent
session, is refused too — that shell carries the markers.
**What to do.** Run `--confirm-delete` in a terminal of your own. A `via:
unattended` on a run nobody launched unattended is a finding.
**Source.** WP6 finding F3, `.ai/reports/T-2026-09-27-003/`;
`hooks/guard/paths.py`, `skills/project-update/adopt.py` (`human_gate`).

## `AI_UNATTENDED=1` turns the human gates off

**Risk.** With `AI_UNATTENDED=1` in its environment, any process passes the
human-present check: the approval gate, the dialog gate, the deletion gates of
`update.py`, the human-only `state.py` routes. Those can then approve a task or
delete files with no human at the keyboard.
**Why it stays.** CI jobs, cron and scripted batches have no human to take a
turn. Without the variable they could not run at all.
**Limits.** It never hides. The approval is recorded as `unattended` in the
state and the journal, `adopt.json` and `migration.json` record `via:
unattended` before the first file is removed, and `/rr-status` names every such
event.
**What to do.** Export it only in the environment of a launcher, never in an
interactive shell, where it silently disables the gates for every session the
shell starts. Check `/rr-status` after an unattended run.
**Source.** `.ai/reports/T-2026-09-21-001/release.md`, "Residual accepted
risk"; `skills/rr-ship/SKILL.md`.

## Three hooks are less protected than the guards

**Risk.** The path guard refuses writes to the guard engine (`hooks/ai-*`,
`hooks/guard/`, `hooks/lib/`), to `runtime-gate.py` and to `skills/ai-task/`
under `.claude/` or `.codex/`. It does **not** protect `context-guard.py`,
`dialog-gate.py` or `cap-large-read.py` by name. An agent could edit those and
so change the compaction snapshot, the session record, what a pick records, or
the read cap.
**Why it stays.** The three guards were frozen first so the characterization
golden could prove the port moved no decision; protection for the rest is an
additive rule of its own.
**Limits.** The installed copies live under `~/.claude` or `~/.codex`, outside
any project, and a change to them shows up in `npx riskrails --dry-run`. On
Codex an edited hook entry loses its trust and stops running until you
re-approve it. `dialog-gate.py` never denies, so editing it cannot lift a rule.
**What to do.** Treat an unexpected diff under `hooks/` like a change to CI
configuration.
**Status.** Open; `ROADMAP.md` §2.
**Source.** WP5 OQ3; `hooks/ai-path-guard-defaults.json`.

## The compaction snapshot runs `git` in the working directory

**Risk.** Before a compaction, `context-guard.py` runs `git branch
--show-current` and `git status --short` in the session's directory. A hostile
repository can make those calls run its own code through its local git
configuration (`core.fsmonitor`, for example).
**Why it stays.** It is the same exposure as any shell prompt that shows the git
branch.
**Limits.** Only under Claude Code, only on compaction, with your own user
rights. It gives no more than opening the repository in a git-aware shell.
**What to do.** Do not run agent sessions inside repositories you do not trust.
**Source.** WP2 security review; `hooks/context-guard.py` (`build_snapshot`).

## Codex runs only hooks you re-approved

**Risk.** Codex keeps each hook approval as a hash of the whole `hooks.json`
entry. After an upgrade changes an entry — a new matcher, a renamed command —
Codex **skips that hook** until you approve it again in `/hooks`. Until then
the guard, the runtime gate, the dialog gate or the context guard is simply not
running under Codex, and nothing on screen says so.
**Why it stays.** This is Codex's trust model. A plugin cannot and should not
approve itself.
**What to do.** After every `npx riskrails` that touches Codex, open `/hooks`
in Codex and approve the changed entries. The installer ends with that
reminder.
**Source.** `docs/hooks.md`, "Two runtimes, one set of rules".

## Codex facts are observed, not guaranteed

**Risk.** Codex's multi-agent v2 launches agents as `collaborationspawn_agent`;
a role's pinned model beats a model given at launch; a Codex hook cannot ask
the user a question; the question tool is `request_user_input`. All were
established by live probes and one documentation page, and Codex changes
quickly. A future release can make the reroute, the budget check or the dialog
silently miss.
**Limits.** On Codex these rules degrade to "allow and explain" by design,
never to a block, and the dialog falls back to the terminal route. The
`SubagentStart` backstop journals `missed_reroute` when an EXPERT agent starts
during an outage anyway.
**What to do.** After a Codex upgrade, grep the journals for `missed_reroute`;
any line means the reroute stopped matching. `docs/dialog-spike.md` holds the
recorded Codex payloads to compare against.
**Source.** WP5 spec, accepted concern 6; `docs/sdlc/specs/command-choice-dialog.md`.

## The dialog switch is read in two places

**Risk.** The hooks read `.ai/policies/dialog.json` and the installed
`profile.json` to decide whether the dialog is on; `state.py` reads the same
files on its own. Across sessions, and on a Codex install whose profile names
no question tool, the two can disagree: `close` prints `DIALOG_PENDING` while
the gate treats the decision as off, or the reverse. With the dialog off there
is no route to "Keep" a mode a re-score raised.
**Why it stays.** Found by the STRONG review of the dialog tasks and recorded
as C1 risks; the fix is a spec question (one switch, one reader).
**Limits.** The fallback is always the terminal command `close` prints; a pick
never lifts a git rule; an unanswered offer falls back within one tool call.
**What to do.** When `DIALOG_PENDING` and the terminal command disagree, use
the terminal. `"enabled": false` in `dialog.json` turns the dialog off for the
project.
**Source.** `state.py memory risks`, the dialog entries of 2026-10-28.

## Budgets and quota are advice, not limits

**Risk.** Several numbers can be off, and none of them ever blocks work.
Codex quota comes only from the rollouts of a past or running session; Claude's
only while a session with the statusline runs. A `SubagentStop` lost to a crash
leaves a running-agent entry behind for up to 30 minutes. The EXPERT launch
count per task never shrinks, and declined launches count too. The per-task
token figures in `profile.json` are reported by `/rr-status --cost`, never
enforced.
**What to do.** `runtime-gate.py clear` empties the count after a crash. Read
the quota with its `stale` and `resets_at` fields, not as a hard figure.
**Source.** WP5 spec, accepted concerns 1, 3 and 4; `hooks/runtime-gate.py`.

## `--adopt` edge cases fail safe, not smoothly

Three low-severity cases from the WP6 review were accepted; each fails closed
rather than losing data. An interrupted apply's `planned_writes` excuses those
paths from the clean-tree check and never decides what is written or deleted.
On resume, `original/<file>` is reused, so edits made between the crash and the
resume are not in the saved original — git still has the committed version. In
a monorepo subdirectory an interrupted apply cannot resume until you commit; it
refuses rather than guesses. Two things have not been tried by hand: `--adopt`
on a real Spec Kit or Cursor project (the suites use fixtures), and a cleanup
run in a real terminal.
**What to do.** Run `--adopt` on a clean, committed tree, read the dry run
first, and keep `original/` until you have checked the result.
**Source.** `.ai/reports/T-2026-09-21-001/review.md`, the LOW rows.

## The usage report's parse cache trusts mtime and size

**Risk.** `usage-report.py` keeps each transcript's parse state on disk, keyed
by path, mtime and size, and folds only the bytes past the offset it stopped
at. A file rewritten rather than appended to — same path, larger, same first
256 bytes — would be resumed from a stale offset and double-counted.
**Why it stays.** The alternative is hashing every transcript on every run,
the work the cache exists to avoid. Transcripts are append-only in both
runtimes.
**Limits.** A shrunk file, one whose first block changed, or one whose stored
state is not the shape this version folds, is parsed from zero. The cache is a
report's cache: a wrong number is a wrong number in a report, not a wrong
change to a repository.
**What to do.** `--no-cache` reports without it. Deleting
`~/.cache/riskrails/usage-report.json` rebuilds it.
**Source.** `skills/usage-report/SKILL.md`, "The parse cache".
