# The hooks

Five in total. Two come from the routing half and are not guards:

- **`cap-large-read.py`** (`PreToolUse:Read`) refuses an unbounded `Read` of a
  file over 4 000 lines or 250 KB. It does not cap what can be read — it insists
  that reading something large is deliberate, because the main session re-reads
  its whole context every turn, so one 500 KB read is paid for again on every
  later turn. An explicit `limit` always passes. Thresholds come from
  `CLAUDE_READ_MAX_LINES` and `CLAUDE_READ_MAX_BYTES`.
- **`project-scaffold.sh`** (`Setup:init`) creates the `docs/sdlc/` and
  `.claude/` layout when `/init` runs. It never overwrites.

The other three are the guards. They share `hooks/lib/ai-hook-common.sh` and one
contract: read the payload from stdin, exit 0 silently to allow, or print

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"…"}}
```

and exit 0 to refuse. They **fail open**: a guard that cannot parse its input
allows the call.

## What these guards are, and are not

They are **defence-in-depth against ordinary agent behaviour**. They stop the
mistake an agent makes while trying to be helpful: reading `.env` to check a
config value, editing one more file to finish a step, force-pushing to clean up a
messy branch.

They are **not a security boundary**. Every rule is a regex over a command line
or a path, and a determined process can read a file through an interpreter, build
a command from variables, or pipe base64 into a shell. There is a tripwire for
the most common obfuscations, and it is a tripwire, not a wall.

The real backstops are human review and server-side branch protection. Treat these
hooks as the thing that keeps an honest agent honest.

## ai-git-guard — every repository

Registered on `Bash`, active everywhere, whether or not the project uses `.ai/`.
The operations it refuses are wrong in any repository and are precisely the ones
that cannot be undone from a chat session.

| Rule | Refuses |
|---|---|
| secrets | `git add` of a path matching the sensitive list; for `git add .` / `-A` it asks `git status` what would actually be staged |
| force push | `--force`, `-f`, and `--force-with-lease` alike |
| branch delete | `git push origin --delete x`, `git push origin :x` |
| history rewrite | `filter-branch`, `filter-repo`, `push --mirror` |
| protected branch | push or merge to `main`, `master`, `production`, `prod`, `stable`, `release/*`, `hotfix/*` |
| pull request merge | `gh pr merge` |
| hook bypass | `--no-verify` on commit or push |
| destructive reset | `git reset --hard` while a protected branch is checked out |
| deployment | `argocd app sync`, `helm upgrade … prod`, `kubectl --context …prod`, `terraform apply`, `deployer deploy prod`, `cap production deploy`, `fly deploy`, `vercel --prod` |

**Branch resolution.** A bare `git push`, or `git push origin HEAD`, targets
whatever is checked out — so the guard asks `git branch --show-current` rather
than matching the string "main" in the command. `git push origin feature/x:main`
is resolved to its destination, `main`, and refused.

**Prose is stripped first.** Commit messages and heredoc bodies are removed before
any rule matches, so `git commit -m "stop force-pushing in the deploy script"` is
a commit, not a force push.

Configuration: `~/.claude/hooks/ai-git-guard.json`. The installer seeds it once
from the shipped defaults and **never overwrites it**, so your edits survive a
re-install. `protected_branches` and `deploy_patterns` are the ones you will want
to adjust; `allow_force_push_repos` and `allow_protected_push_repos` take
repository names as an escape hatch.

**Not enforced here:** "do not weaken a test or a static-analysis level to make a
check pass" is not a property of a git command. It is checked by `ai-reviewer`
and reported by `ai-release`, and it is stated in `.ai/policies/git.md`.

## ai-path-guard — where `.ai/` exists

Registered on `Read`, `Edit`, `Write`, `NotebookEdit` and `Bash`. Its first act is
to look for a `.ai/` directory above the working directory; without one it exits
immediately, which is why it can be registered globally and still be invisible in
repositories that never opted in.

It refuses two kinds of path:

**Sensitive** — `.env` and its environment variants, `secrets/`, `credentials/`,
`.ssh/`, private keys and certificates, cloud credential files, `.sql` dumps and
customer exports, production logs. Allowed back in: `.env.example` and friends,
migrations, fixtures, test SQL.

**Control files** — `.ai/state/*.json`, `.ai/policies/*.json`, and the guards' own
scripts and configuration under `~/.claude/hooks/ai-*`. Reading them is fine;
writing them is not. State is written by `state.py`; policy is edited by a human,
outside an agent run, where the change is reviewable.

Both the literal path and its `realpath` are checked, so a symlink pointing at
`.env` is caught. `ln -s .env public/x` is refused at creation time, because the
link does not exist yet when the guard runs.

For `Bash`, the guard extracts every argument-looking token and only complains
when the token is genuinely an argument of a reading, copying or redirecting
command — a path mentioned inside a message or a heredoc is left alone. There is
a fast path: if nothing on the command line looks interesting, the guard exits
after a single `grep`, which keeps it at tens of milliseconds even on a
200-argument command.

Configuration: `hooks/ai-path-guard-defaults.json` (shipped, do not edit) unioned
with `.ai/policies/path-guard.json` (per project). Allow wins over deny. When the
guard refuses something it should not, **widen the allow list** — do not route
around it.

## ai-scope-guard — during an implementation step

Registered on `Edit`, `Write` and `NotebookEdit`. It does nothing unless
`.ai/state/current.json` exists, its `current_stage` is `implementation`, and a
step is current.

It then matches the target against that step's `forbidden_files` (refused with the
reason from the plan) and its `allowed_files` (refused with the literal token
`SCOPE_CHANGE_REQUIRED`, which is what the manager watches for). Patterns are
shell globs, so a plan can say `src/Payment/*.php` the way a human would.

When a step is not found while the stage is `implementation`, the guard **allows**
and the inconsistency is surfaced by `/ai-task` on the next resume. A guard that
failed closed on its own state bug would strand the task.

This is the hook that makes the plan real. Without it, "the step may touch these
files" is a sentence in a document; with it, the sentence is enforced by the
harness, and widening scope requires amending the plan.

## Testing them

```bash
bash tests/run-all.sh
```

Each guard has a fixture suite: a JSON payload plus the expected decision, run
through the real script. Adding a rule means adding a fixture — including one that
proves the rule does **not** fire where it should not, which is the half that
gets forgotten.
