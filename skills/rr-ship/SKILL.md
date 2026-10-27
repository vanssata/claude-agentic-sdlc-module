---
name: rr-ship
description: Close the task — state.py close measures the two facts (a green whole-suite verify on the tree as it is now; every changed file inside the task's files), applies the mode table and either archives the task or, in full mode, requests the human's approval and prints the exact approve command for their own terminal. Writes the commit message body and suggests the commit; never commits, pushes or approves. Use on "/rr-ship", "close the task", "ship it", "ready for approval", after /rr-build or /rr-review.
argument-hint: [--abandon]
---

# /rr-ship $ARGUMENTS

Resolve the install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-ship" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

`--abandon` drops the task: `$STATE close --abandon` archives it without the
checks. Say what was left unfinished, and stop.

## 1. Close

```bash
$STATE close
```

It finishes an open step, re-scores reversibility and domain from the diff, and
measures the two facts: **(a)** a green whole-suite `verify` on the tree as it is
now; **(b)** every file changed since the task began is inside the task's files.
Then the mode table decides:

| Exit | Means | Do |
|---|---|---|
| 0, `closed` | archived: `task.md` holds the changes and the verdict | §3 |
| 0, `ready for approval` | full mode: the gate is requested | §2 |
| 2 `review required` | light with a red fact, or guarded/full without its review | `/rr-review` |
| 2 `verify required` | e2e owed, or not on this tree | `$STATE verify --scope all` (or `--scope e2e`, or `--e2e not-applicable "<why>"`) |
| 4 | a question is pending | show it; §4 |
| 5 `APPROVAL_REFUSED` | rejected, and nothing changed since | address the rejection, `verify --scope all`, close again |

An edit after `verify` moves the tree: fact (a) goes red and `close` says so.
Run `verify --scope all` once more rather than arguing with it.

## 2. The human's approval (full mode)

`close` prints the facts and the command, with absolute paths:

```
approve in your own terminal, then run close again:
  python3 /home/…/skills/ai-task/state.py --root /path/to/project approve --by "<name>"
```

Show the human the summary (§3), the open findings, the rollback, and that
command **verbatim** — paths absolute and quoted, because they paste it into
their own shell, where `$AI_HOME` is not set. Then **stop**.

- **You cannot approve.** `approve` refuses without a terminal on stdin or
  `AI_UNATTENDED` in its own environment — neither of which a tool call from this
  session has — and the path guard denies it. Never try another route.
- **full_irreversible:** the command carries
  `--confirm "<what it does, naming DROP …>"`; the human names every operation
  the re-score found, in their own words.
- The approval covers the tree `close` presented. An edit after it means the
  human rejects (`reject --by "<name>" --why "the tree changed"`) and the next
  `close` asks again.
- An unattended launcher that exports `AI_UNATTENDED=1` approves as an audit
  mark (`unattended: true` in the journal), not as a quieter gate.

When the human says they approved: `$STATE close` again archives the task. A
rejection is theirs too (`reject --by … --why …`); the reason is journaled, and
the work changes before the next `close`.

## 3. The commit message

Write the body from `.ai/reports/<task-id>/task.md` — no new opinion:

- what changed, and what was deliberately left as it was;
- the verification command and its result (suite and e2e);
- the review verdict, with any finding left open and why;
- the rollback: `git revert <commit>`, plus anything a revert does not undo;
- open risks, pointing at `.ai/project/known-risks.md`.

Suggest the commit command — `git add` of the task's files and its
`.ai/reports/<task-id>/`, then `git commit` with that body — for the human to
run. You never commit, push, merge or deploy.

## 4. Pending questions

A pending question blocks `close` (exit 4). The human answers in the
conversation — record it with `$STATE answer Q1=B` or `--prose "1B"` — or fills
the `[Answer]:` line in `.ai/reports/<task-id>/task.md` §Questions themselves, which
is then the record. Never edit that file, never answer for them.

## 5. After

Suggest `/clear` before the next task: what this one needs later is in
`task.md` and the journal, not in the conversation.
