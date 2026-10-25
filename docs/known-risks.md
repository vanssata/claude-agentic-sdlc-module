# Known risks

What version 2.0.2 knowingly does **not** protect against. Each entry says what
can happen, why it was left that way, what limits the damage, and what you should
do. None is a secret. Each was found in a review or a spec, then accepted or
deferred with a written reason in the file named under **Source**.

## The guards are a tripwire, not a sandbox

**Risk.** Every guard rule is a regex over a command line or a path. A process
that wants to get past it can do so. It can read `.env` through a Python
one-liner, build a command from variables, pipe base64 into a shell, or use a
tool that is not on the hook path at all.
**Why it stays.** A real boundary needs an OS-level sandbox. A hook that runs
before a tool call cannot be one. The guards exist to stop the *honest mistake*,
like reading `.env` to check a value or editing one file too many.
**Limits.** A tripwire catches the common obfuscations (quoted flags,
`--opt=value`, interpreter one-liners that mention `.ai/state/` or
`.ai/reports/`).
**What to do.** Keep production secrets off the developer machine, turn on
server-side branch protection, and review every diff before merge. Those are the
real backstops.
**Source.** `docs/hooks.md`, "What these guards are, and are not".

## Human approval can be forged by a determined process

**Risk.** `state.py approve` refuses to run without a terminal on stdin, and the
path guard refuses it from an agent session. An obfuscated invocation that gets
past the regex and also allocates a pseudo-terminal (a pty) can still grant the
approval.
**Why it stays.** This is the same regex limit as above. The check is there to
make self-approval deliberate and visible, not impossible.
**Limits.** `approve` also refuses when no gate was ever requested
(`gate_requested` in the journal). Every approval is journalled with who, when
and how (`via: terminal`).
**What to do.** Read `state.py events` for the approval before you merge a
T4–T6 change. An approval you do not remember giving is a finding.
**Source.** WP2 security review. `hooks/ai-path-guard.sh`, `docs/hooks.md`.

## The deletion gate stops an agent's command, not an agent's script

**Risk.** `--confirm-delete` of `/project-update` (plain `--apply` and
`--adopt --cleanup --apply`) is refused two ways: the path guard denies an agent
Bash command that runs `update.py` with `--apply` and any prefix of
`--confirm-delete`, and `adopt.py` refuses the flag whenever an agent-session
marker (`CLAUDECODE`, or Codex's `CODEX_THREAD_ID`, `CODEX_SESSION_ID`,
`CODEX_CI`, `CODEX_SANDBOX`, `CODEX_SANDBOX_NETWORK_DISABLED`,
`CODEX_VERSION`) is in its
environment, even with a terminal on stdin — an agent can open one with
`script`. The hook matches spellings, so any spelling it does not recognise is
past it: a script file written with the Write tool, arguments held in a
variable, command substitution (`$(…)`, backticks), arguments fed through
`xargs` or stdin, inline `-c` code that imports or runs `update.py`, a glob or a
renamed copy of it — and a session whose working directory has no `.ai/` above
it, where the path guard does not run at all. Each of those still needs the
markers unset (plus a pty) or `AI_UNATTENDED=1` on the command itself to pass
`adopt.py`, which is deliberate, not an honest mistake. A run with the markers
stripped under a pty records `via: terminal`, and `adopt.json` /
`migration.json` are not write-protected, so `via` is a record, not a proof.
**Why it stays.** Same regex limit as above: the hook sees a command line, not
what a file it runs will do.
**Limits.** The record says why the gate passed: `adopt.json` `cleanup.via` and
`migration.json` `deletions[].via` are `terminal` or `unattended`. A human
typing through Claude Code's `!` prefix, or in a shell started from an agent
session, is refused too — that shell carries the markers.
**What to do.** Run `--confirm-delete` in a terminal of your own. A `via:
unattended` on a run nobody launched unattended is a finding.
**Source.** WP6 finding F3, `.ai/reports/T-2026-09-27-003/`.
`hooks/ai-path-guard.sh`, `skills/project-update/adopt.py` (`human_gate`).

## `AI_UNATTENDED=1` turns the human gates off

**Risk.** With `AI_UNATTENDED=1` in its environment, any process passes the
human-present check. That covers the approval gate and the deletion gates of
`/project-update --confirm-delete` and `--adopt --cleanup`. Those can then
approve a task or delete files with no human at the keyboard.
**Why it stays.** CI jobs, cron and scripted batches have no human to take a
turn. Without the variable they could not run at all.
**Limits.** It never hides. The approval is recorded permanently as
`unattended: true` in the state and the journal, `adopt.json` records
`cleanup.unattended: true` and `cleanup.via: unattended` before the first file
is removed, `migration.json` records `via: unattended` per deletion, the report prints
`deleted unattended`, and `/ai-status` names every such event.
**What to do.** Export it only in the environment of a launcher, never in an
interactive shell. There it silently disables the gates for every session the
shell starts. Check `/ai-status` after an unattended run.
**Source.** `.ai/reports/T-2026-09-21-001/release.md`, "Residual accepted
risk". `docs/hooks.md`.

## The routing hooks are less protected than the guards

**Risk.** The path guard protects the three guards' own configuration and the
shim `codex-model-gate.py` by name. It does **not** yet protect `runtime-gate.py`
or `context-guard.py`. An agent could edit those two hooks, and so change the
EXPERT reroute, the quota records or the session and compaction snapshot.
**Why it stays.** WP5 froze the guard files, so that the characterization golden
file proves no guard behaviour changed. Protection for both hooks was split off
as its own additive task.
**Limits.** The installed copies live under `~/.claude` or `~/.codex`, outside
any project, and a change to them shows up in `install.sh --dry-run`. On Codex an
edited hook entry loses its trust and stops running until you re-approve it.
**What to do.** Treat an unexpected diff under `hooks/` like a change to CI
configuration. Until the follow-up lands, review hook changes by hand.
**Status.** Open, planned as a follow-up (WP5 OQ3).
**Source.** `docs/sdlc/specs/adaptive-cross-runtime-sdlc-wp5-runtimes-and-plans.md`, concern 2 and OQ3.

## The compaction snapshot runs `git` in the working directory

**Risk.** Before a compaction, `context-guard.py` runs `git branch --show-current`
and `git status --short` in the session's directory. A hostile repository can
make those calls run its own code through its local git configuration (for
example `core.fsmonitor`).
**Why it stays.** This predates the plugin's own work. It is the same exposure as
any shell prompt that shows the git branch.
**Limits.** It runs only under Claude Code, only on compaction, and with your
own user rights. It gives no more than opening the repository in a git-aware
shell already does.
**What to do.** Do not run agent sessions inside repositories you do not trust.
**Status.** Open.
**Source.** WP2 security review. `hooks/context-guard.py` (`build_snapshot`).

## Codex runs only hooks you re-approved

**Risk.** Codex keeps each hook approval as a hash of the whole `config.toml`
entry. After an upgrade changes an entry, for example the gate's matcher
`^Agent$|spawn_agent$`, Codex **skips that hook** until you approve it again in
`/hooks`. Until then the scope, path and git guards, or the runtime gate, are
simply not running under Codex, and nothing on screen says so.
**Why it stays.** This is how Codex's trust model works. A plugin cannot and
should not approve itself.
**What to do.** After every `./install.sh` that touches Codex, open `/hooks` in
Codex and approve the changed entries. The installer ends with that reminder.
**Source.** `docs/hooks.md`, runtime gate. `docs/installation.md`, "What it installs".

## Codex facts are observed, not guaranteed

**Risk.** Codex's multi-agent v2 launches agents as `collaborationspawn_agent`.
A role's pinned model beats a model given at launch, and a Codex hook cannot ask
the user a question. All three were established by live probes and one
documentation page, and Codex changes quickly. A future Codex release can make
the reroute or the fan-out check silently miss.
**Limits.** On Codex these rules degrade to "allow and explain" by design, never
to a block. The `SubagentStart` backstop journals `missed_reroute` when an
EXPERT agent starts during an outage anyway.
**What to do.** After a Codex upgrade, run `state.py events --type
missed_reroute`. Any line there means the reroute stopped matching.
**Source.** WP5 spec, accepted concern 6. PR #26.

## Budgets and quota are advice, not limits

**Risk.** Several numbers can be off, and none of them ever blocks work.
- **Quota signals can be stale.** Codex quota comes only from the rollouts of a
  past or running session. Claude's comes only while a session with the
  statusline runs.
- **The running-agent count can drift.** A `SubagentStop` lost to a crash leaves
  an entry behind for up to 30 minutes, which costs one extra question.
- **The EXPERT launch count per task never shrinks.** Declined launches count
  too.
- **On Pro/Plus, "strictly serial" is the plugin's rule, not Codex's.** Codex
  still allows 3 threads and can run a second agent after the gate has explained
  why it should not.

**What to do.** `runtime-gate.py clear` empties the count after a crash. Read
the quota with its `stale` and `resets_at` fields, not as a hard figure.
**Source.** WP5 spec, accepted concerns 1, 3 and 4. `hooks/runtime-gate.py`.

## `--adopt` edge cases fail safe, not smoothly

Three low-severity cases from the WP6 review were accepted. Each fails closed or
safe rather than losing data.
- An interrupted apply's `planned_writes` excuses those paths from the
  clean-tree check. It never decides what is written or deleted.
- On resume, `original/<file>` is reused, so edits made between the crash and
  the resume are not in the saved original. Git still has the committed version.
- In a monorepo subdirectory an interrupted apply cannot resume until you commit.
  It refuses rather than guesses.

Two things have not been tried by hand yet: `--adopt` on a real Spec Kit or
Cursor project (the tests use fixtures), and a cleanup run in a real terminal.
**What to do.** Run `--adopt` on a clean, committed tree, read the dry run
first, and keep `original/` until you have checked the result.
**Source.** `.ai/reports/T-2026-09-21-001/review.md`, the LOW rows.

## The usage report's parse cache trusts mtime and size

**Risk.** `usage-report.py` keeps each transcript's parse state on disk, keyed by
path, mtime and size, and folds only the bytes past the offset it stopped at. A
file that was rewritten rather than appended to — same path, larger, and the
same first 256 bytes — would be resumed from a stale offset, and the report
would count the old records together with the new ones.
**Why it stays.** The alternative is hashing every transcript on every run,
which is the work the cache exists to avoid. Transcripts are append-only in both
runtimes; a rewrite that also preserves the opening bytes is not a case either
runtime produces.
**Limits.** A shrunk file, one whose first block changed, or one whose stored
state is not the shape and contents this version folds, is parsed from zero.
Same mtime and size means the file is not read again — unless its last line had
no newline after it, which is re-read until it is complete — so an in-place
rewrite of exactly the same length is the other side of the same assumption.
The cache is a report's cache: nothing else reads it, and a wrong number is a
wrong number in a report, not a wrong change to a repository.
**What to do.** `--no-cache` reports without it, and tells you within one run
whether a surprising number came from the cache. Deleting
`~/.cache/claude-agentic/usage-report.json` rebuilds it from scratch.
**Source.** This entry; `skills/usage-report/SKILL.md`, "The parse cache".
