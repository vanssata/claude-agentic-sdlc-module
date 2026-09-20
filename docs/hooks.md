# The hooks

| Hook | Claude Code | Codex |
|---|---|---|
| `ai-git-guard` | yes | yes |
| `ai-path-guard` | yes | yes |
| `ai-scope-guard` | yes | yes |
| `cap-large-read.py` | yes | **no** — no hookable read tool |
| `project-scaffold.sh` | yes (`Setup:init`) | **no** — no equivalent event |
| `context-guard.py` | yes | yes — everything but the transcript snapshot |
| `fable-gate.py` | on a Fable install | — |
| `codex-model-gate.py` | — | yes |

Three of them come from the routing half and are not guards:

- **`cap-large-read.py`** (`PreToolUse:Read`) refuses an unbounded `Read` of a
  file over 4 000 lines or 250 KB. It does not cap what can be read — it insists
  that reading something large is deliberate, because the main session re-reads
  its whole context every turn, so one 500 KB read is paid for again on every
  later turn. An explicit `limit` always passes. Thresholds come from
  `AI_READ_MAX_LINES`/`AI_READ_MAX_BYTES`, or the older
  `CLAUDE_READ_MAX_LINES`/`CLAUDE_READ_MAX_BYTES`.
  **Codex has no counterpart**, because its read tool is not on the hook path.
  The rule is written into `~/.codex/AGENTS.md` instead, where it is policy rather
  than enforcement — which is worth knowing when you rely on it.
- **`project-scaffold.sh`** (`Setup:init`) creates the `docs/sdlc/` and runtime
  layout when `/init` runs. It never overwrites. Under Codex, run it by hand:
  `~/.codex/hooks/project-scaffold.sh "$PWD"`.
- **`context-guard.py`** (`UserPromptSubmit`, `PreCompact`, `SessionStart`)
  watches the context size, snapshots what a compaction must not lose, and —
  the part that matters here — writes `.ai/state/session.json` and injects the
  handoff. It is **not** a guard and refuses nothing, but the approval gate
  reads what it writes, which is why `ai-path-guard` refuses to let an agent run
  it by hand (below). Installed on both runtimes; only the transcript-derived
  snapshot stays Claude-only.

The three guards share `hooks/lib/ai-hook-common.sh` and one contract: read the
payload from stdin, exit 0 silently to allow, or print

```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"…"}}
```

and exit 0 to refuse. The deny shape is identical in both runtimes. They **fail
open**: a guard that cannot parse its input allows the call.

## Two runtimes, one set of rules

The guards' rules are written once. `ai-hook-common.sh` normalises what arrives
first, so no rule has to know which runtime it is in:

| Codex sends | The guards see |
|---|---|
| `apply_patch` | `Edit`, plus every path in the patch body |
| `shell`, `exec_command`, `local_shell` | `Bash` |

`apply_patch` is the one that changes behaviour rather than naming. A single call
can add, update, delete and move many files, so the paths are extracted from its
`*** Add File:`, `*** Update File:`, `*** Delete File:` and `*** Move to:`
headers and each is checked separately. **One out-of-scope or protected file
rejects the whole patch** — split it rather than widening the step. The patch text
also arrives in `tool_input.command`, which is where a shell command lives for
`Bash`; the guards only treat that field as a command when the tool really is a
shell, so a patch body is never parsed as a command line.

**Codex will not run these hooks until you trust them.** A non-managed hook has
to be reviewed and approved through `/hooks` first. Until you do, everything
below describes rules that are installed but not being applied.

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

Configuration: `~/.claude/hooks/ai-git-guard.json` and
`~/.codex/hooks/ai-git-guard.json`. The installer seeds each one once from the
shipped defaults and **never overwrites it**, so your edits survive a re-install.
Each runtime has its own copy, so edit both if you want the same local rule in
both. `protected_branches` and `deploy_patterns` are the ones you will want to
adjust; `allow_force_push_repos` and `allow_protected_push_repos` take repository
names as an escape hatch.

**Not enforced here:** "do not weaken a test or a static-analysis level to make a
check pass" is not a property of a git command. It is checked by `ai-reviewer`
and reported by `ai-release`, and it is stated in `.ai/policies/git.md`.

## ai-path-guard — where `.ai/` exists

Registered on `Read`, `Edit`, `Write`, `NotebookEdit` and `Bash` — and on
`apply_patch` under Codex, where the `Read` half does not apply because reads are
not hookable there. Its first act is
to look for a `.ai/` directory above the working directory; without one it exits
immediately, which is why it can be registered globally and still be invisible in
repositories that never opted in.

It refuses four kinds of path:

**Sensitive** — `.env` and its environment variants, `secrets/`, `credentials/`,
`.ssh/`, private keys and certificates, cloud credential files, `.sql` dumps and
customer exports, production logs. Allowed back in: `.env.example` and friends,
migrations, fixtures, test SQL.

**Control files** — `.ai/state/*.json`, `.ai/state/handoff.md`,
`.ai/reports/<task-id>/questions.md`, `.ai/reports/<task-id>/events.jsonl`,
`.ai/policies/*.json`, and the guards' own scripts and configuration under
`~/.claude/hooks/ai-*` and `~/.codex/hooks/ai-*` (including
`codex-model-gate.py`). Reading them is fine; writing them is not. State is
written by `state.py`; policy is edited by a human, outside an agent run, where
the change is reviewable.

The three added with schema 2 are protected for the same reason the state file
is — each is an input to a decision, not a document. `questions.md` carries the
`[Answer]:` line that can *grant the approval gate*, so an agent that could edit
it could approve its own plan. `events.jsonl` is the audit trail: an append-only
journal that can be rewritten is not one. `handoff.md` is what the next session
reads before anything else, so a writable handoff is a way to plant instructions
for a future session. All three are written by `state.py` alone — `ask`,
`answer`, `questions --sync`, `emit` and `handoff` — and all three stay
**readable**, because reading them is how the work gets done.

**Runtime configuration, while a task is in flight** — `.claude/settings*.json`,
`.claude/agents/`, `skills/`, `commands/`, `hooks/`, `plugins/`, the `.codex/`
equivalents and `config.toml`, and the pipeline's own `.ai/policies/`,
`.ai/workflows/`, `.ai/templates/` and `.ai/AGENTS.md`, plus the other runtimes'
instruction files (`.cursorrules`, `.cursor/rules/`, `.github/copilot-instructions.md`,
`.junie/guidelines.md`). The rule sources join them: `.ai/rules/` and the
`.claude/rules/` copies rendered from it are instructions for a directory, and
`docs/sdlc/constitution.md` is what the spec and the plan are judged against — a
task that could rewrite either could widen its own scope or drop the principle
it is failing. Reading is fine; writing is refused **only while an
`/ai-task` run owns the project** — `.ai/state/current.json` exists and has not
reached `done`. A run may not edit the rules it is being judged by; `state.py
close` archives the task and the same files become ordinary files again. A state
file that does not parse counts as in flight, because refusing to unlock the
configuration on the strength of a corrupt file costs nothing.

**Instruction files inside a dependency** — a `CLAUDE.md`, `AGENTS.md`,
`GEMINI.md`, `.cursorrules`, `copilot-instructions.md` or the like under
`vendor/`, `node_modules/`, `Pods/`, `site-packages/`, `third_party/` and
friends. Both reading and writing are refused, always. Such a file is
third-party text that arrived with a package: it is **data**, it carries no
authority over the task, and the next install overwrites it anyway. Ordinary
source inside a dependency is untouched — the rule is about instruction files,
not about the directory.

Both the literal path and its `realpath` are checked, so a symlink pointing at
`.env` is caught. `ln -s .env public/x` is refused at creation time, because the
link does not exist yet when the guard runs.

For `Bash`, the guard extracts every argument-looking token and only complains
when the token is genuinely an argument of a reading, copying or redirecting
command — a path mentioned inside a message or a heredoc is left alone. There is
a fast path: if nothing on the command line looks interesting, the guard exits
after a single `grep`, which keeps it at tens of milliseconds even on a
200-argument command.

### Two rules that run before the fast path

Everything above is about paths. Two rules are about a **command**, and they are
evaluated before the fast path rather than after it — deliberately, and at a
measured cost of two in-process regex matches per `Bash` call and no extra
process (`docs/hook-performance.md`). The reason is that `state.py` and
`context-guard.py` live in the *plugin*, not under `.ai/`, so
`python3 …/skills/ai-task/state.py --root . approve` matches nothing in the
guard's pattern lists: the fast path would have allowed it and returned before
any later rule ran.

**`state.py approve` from an agent session is refused.** The approval of a plan
at T3+ is the one decision the pipeline may not make for itself, and a gate an
agent can close is not a gate. The deny names the two ways a human closes it:

```bash
python3 <plugin>/skills/ai-task/state.py --root . approve --by "<name>"
```

run in **their own terminal** (the command checks for a TTY, so the same line
run through the agent's shell — a pipe — exits 5 and changes nothing), or the
`[Answer]: A` line on the gate's question in `.ai/reports/<task-id>/questions.md`,
after which the session runs `state.py questions --sync`. The file route is the
weaker of the two and knows it: it is accepted only behind a human turn —
`last_prompt_at` in `.ai/state/session.json`, from the same session the plan was
presented in, after the gate was requested.

**Running `hooks/context-guard.py` by hand is refused too**, and only that one
hook, because only that one writes state: `session.json` is the evidence the
file route rests on, so an agent that could run the hook could mint the human
turn it needs and then answer its own gate. Reading, diffing, linting and
testing the file are untouched — the rule fires only in command position. Both
rules are inert unless a task is in flight.

There is a third, cheaper route to the same place, and it is closed by the
interpreter tripwire further down: `python3 -c 'open(".ai/state/session.json",
"w")…'` writes the human turn without going through a file tool at all. Any
interpreter one-liner or `eval` that mentions `.ai/state/` or `.ai/reports/` is
refused for that reason. Like the rest of the tripwire it is a tripwire, not a
wall.

**`AI_UNATTENDED=1` turns both off**, because an unattended run has no human to
take a turn. It is for a launcher — CI, a cron job, a scripted batch — that
exports it in the *environment it starts the run in*. Do not export it in an
interactive shell: it disables the gate for every session that inherits it, for
as long as the shell lives, and nothing will remind you. What it does not do is
hide: an approval taken this way is recorded in the state and in the journal as
`via: "unattended"`, `unattended: true`, permanently, and `/ai-status` calls out
any such approval by name. That is the trade — the gate can be turned off, but
not quietly.

**Under Codex, both rules exist only once you trust the hooks.** A non-managed
hook is listed but not run until it is reviewed and approved through `/hooks`.
Until then `state.py approve` from a Codex agent session is refused by nothing,
and the gate is policy rather than enforcement. This asymmetry is accepted, not
fixed: nothing in the plugin can approve a hook on the user's behalf, and a
runtime that made it possible would have a worse problem than this one. Trust
the hooks after installing, and `/ai-status` says so under Codex.

Configuration: `hooks/ai-path-guard-defaults.json` (shipped, do not edit) unioned
with `.ai/policies/path-guard.json` (per project), in five lists —
`deny_patterns`, `allow_patterns`, `protected_config_patterns`,
`task_protected_patterns` and `dependency_instruction_patterns`. Allow wins over
every one of the others. When the guard refuses something it should not,
**widen the allow list** — do not route around it.

A path is classified against those lists in a fixed order: allow, then
protected, then dependency, then task, then deny. That matters when you add
patterns of your own, because the first list to match decides — and `protected`,
`task` and `dependency` each permit reads that `deny_patterns` would have
refused. A `task_protected_patterns` regex loose enough to also cover an `.env`
would therefore *weaken* an existing secret-read rule rather than add to it.
Keep a new pattern narrow enough that it cannot reach a path another list
already covers. The shipped lists do not overlap.

The dependency rule recognises a dependency by directory name (`vendor/`,
`node_modules/`, `third_party/`, `Pods/`, …), so a first-party directory using
one of those names has its own instruction files refused too. Projects laid out
that way should put the owned paths in `allow_patterns`.

## ai-scope-guard — during an implementation step

Registered on `Edit`, `Write`, `NotebookEdit` and `apply_patch`. It does nothing unless
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

## fable-gate — Max and Team Max with Fable only

On Max or Team Max with `--fable yes`, `architect` is pinned to `model: fable[1m]` — the one
agent that runs on Fable; the session and every other agent stay on Opus.
`fallbackModel` moves such an agent to Opus when Fable is **overloaded** — but a
rate limit, a used-up usage limit, or a model the account cannot reach
(`model_not_found`) never triggers that switch: the agent just fails, and so does
the next one. `fable-gate.py` closes the gap at run time.

| Event | Does |
|---|---|
| `StopFailure` (`rate_limit\|model_not_found`) | when the failure is Fable's, records Fable as unavailable — 1 h for a rate limit, 6 h for model-not-found |
| `PostToolUse:Agent` | a Fable agent that `resolvedModel`/`modelsUsed` show fell back: recorded for 15 min, so the next ones skip the failed attempt |
| `PreToolUse:Agent` | while a record is live, returns `updatedInput` with `model: opus` for any agent that would run on Fable — resolved in Claude Code's order: an explicit `model`, then the definition's frontmatter (project before user), then `CLAUDE_CODE_SUBAGENT_MODEL`. Before Claude Code 2.1.251 (the JetBrains ACP adapter still bundles 2.1.219) the variable came first and overrode both; hooks are given no version, so the gate reads it from the `version` of the newest record in the payload's `transcript_path`, and only when the variable and the rest disagree about Fable. With no readable version the reroute assumes the current order — a wrong guess there costs nothing, because an old Claude Code lets the variable override the rewritten `model` just as it overrode the original, while the opposite wrong guess would let a pinned Fable agent launch during an outage and turn a Sonnet call into an Opus one; `PostToolUse` and `StopFailure` do not guess, and leave an agent the two orders disagree on out of the record. On an old Claude Code with the variable itself set to Fable no rewrite can take effect, so unset the variable — and tells Claude (`additionalContext`) and you (`permissionDecisionReason`) why |

A failure is Fable's when its message names Fable, the failing agent's definition
pins Fable, the transcript was last served by Fable, or a Fable agent launched in
the last five minutes. Authentication, billing and account errors are ignored:
they are account-wide, and Opus would fail the same way.

The record lives in `~/.claude/state/fable-gate.json` and expires on its own, so
Fable is tried again after the reset. The gate never blocks an agent and fails
open on any error. When an agent was already running on Fable and failed, the
managed `CLAUDE.md` block has the main session re-run that brief once on Opus.

```bash
~/.claude/hooks/fable-gate.py status          # active until …, or inactive
~/.claude/hooks/fable-gate.py clear           # try Fable again now
~/.claude/hooks/fable-gate.py set 3600 reason # route to Opus for an hour
```

**The weekly limit — on by default.** Claude Code gives the statusline, not
hooks, the account's `rate_limits`, so the installer wires the check through the
statusline. On a Fable install your `statusLine` command becomes

```
"$HOME/.claude/hooks/fable-gate.py" statusline --then '<your original command>'
```

The gate reads the input, then runs your command on the same input and passes
its output and exit code through — what you see does not change. With no
statusline configured, the installer adds the bare check, which prints nothing.
At `CLAUDE_FABLE_GATE_WEEKLY_PCT` (90) percent of `rate_limits.seven_day` used,
Fable agents go to Opus until `resets_at`. The limit is account-wide, not
Fable's own, so this is a spend guard rather than an availability check.

Re-installing never wraps twice; `--fable no` or a Pro or Team Pro install puts your
original command back byte for byte, or removes the statusline it added. If
`/statusline` later rewrites the command, re-run the installer to wire the
check again. To keep the statusline but skip every check, set
`CLAUDE_FABLE_GATE=off`.

Tuning: `CLAUDE_FABLE_GATE=off` disables it; `CLAUDE_FABLE_GATE_TTL`,
`_NOT_FOUND_TTL`, `_OVERLOAD_TTL`, `_LAUNCH_WINDOW`, `_WEEKLY_PCT`, `_FALLBACK` and
`_STATE` override the defaults.

An install with `--fable no`, or on Pro or Team Pro, does not register the gate, and removes
the entries a previous Fable install left — your own hooks on the same events
stay, and the statusline is unwrapped.

## codex-model-gate — Codex only

The same problem as `fable-gate`, one tier up the Codex ladder. `ai-expert` is
pinned to `gpt-6-astra`; when Astra is rate-limited or the account cannot reach
it, the agent fails, and so does the next one. The gate records that and sends
EXPERT launches to Sol at `high` until it expires. On Plus `ai-expert` is
already at `high` rather than `xhigh`; the fallback model is the same.

| Event | Does |
|---|---|
| `SubagentStop` | when the failure text names a rate limit, an unavailable model or an overload **and** the failure is attributable to an EXPERT agent, records Astra as unavailable — 1 h for a rate limit or overload, 6 h for model-not-found |
| `PostToolUse:Agent` | marks a completed expert launch, so an immediately following failure can be attributed |
| `PreToolUse:Agent` | while a record is live, returns `permissionDecision: "allow"` with `updatedInput` carrying `model: gpt-5.6-sol` and `model_reasoning_effort: high`, and says in `additionalContext` that the answer is Sol's, not Astra's |

**Why `SubagentStop`.** Codex has no `StopFailure` event, so there is no signal
that says "this agent failed for this reason". The gate therefore only marks the
record when the evidence actually points at an EXPERT agent: the expert agent's
name in the text, an explicit expert `model` in the payload, an agent file pinned
to the expert model, or an expert launch within the last five minutes. The
matching is deliberately narrow — rate limit, quota, 429, model-not-found,
no-access, overloaded, 503, capacity. A bare "error" or "failed" does not count,
because a gate that trips on any failure would keep the whole EXPERT tier
downgraded for an hour over an unrelated bug.

To resolve which model a launch would use, it checks the explicit `model` first,
then the agent's own file (project `.codex/agents/` before `~/.codex/agents/`),
then `default_subagent_model` in `config.toml` — the same precedence Codex itself
applies.

The record lives in `$CODEX_HOME/state/codex-model-gate.json` and expires on its
own. The gate never blocks an agent and fails open on any error.

```bash
~/.codex/hooks/codex-model-gate.py status          # active until …, or inactive
~/.codex/hooks/codex-model-gate.py clear           # try Astra again now
~/.codex/hooks/codex-model-gate.py set 3600 reason # route to Sol for an hour
```

Tuning: `CODEX_MODEL_GATE=off` disables it. `CODEX_MODEL_GATE_MODE=context`
makes it annotate instead of rewriting, for when you would rather see the failure
than have the model quietly changed under you.

There is no weekly-limit equivalent: Codex does not expose the account's usage
window to a hook the way Claude Code's statusline does.

## Testing them

```bash
bash tests/run-all.sh
```

`tests/test-fable-gate.sh` and `tests/test-codex-model-gate.sh` drive each gate
through every event with synthetic payloads — including malformed input, an
unwritable state directory, expiry and explicit-model precedence — and install
each plan and `--fable` option into scratch directories, including switching
Fable off and on again.

Each guard has a fixture suite: a JSON payload plus the expected decision, run
through the real script. `tests/fixtures/codex-hooks/` holds the Codex ones,
including `apply_patch` payloads that touch several files at once. Adding a rule
means adding a fixture — including one that proves the rule does **not** fire
where it should not, which is the half that gets forgotten.

`tests/test-guard-characterization.sh` is the other half: it pins the exact
behaviour of all three guards — exit code and full deny text, byte for byte —
against a golden file, so a change made purely for speed can be proved to change
nothing. See `docs/hook-performance.md` for what the guards cost per tool call,
the budget they are held to, and what is deliberately not optimised.
