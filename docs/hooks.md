# The hooks

Every rule the hooks enforce, where each one runs, and how a project tunes it.
The hooks are what makes a rule a rule: an instruction file asks, a hook
refuses.

| Hook | Runtimes | Events | Does |
|---|---|---|---|
| `ai-guard.py` | both | `PreToolUse` on every tool (Claude matcher `*`, Codex `.*`) | one process, four checks in order — **decision**, **git**, **paths**, **scope**; the first refusal wins |
| `cap-large-read.py` | Claude | `PreToolUse:Read` | refuses an unbounded `Read` of a large file |
| `context-guard.py` | both | `UserPromptSubmit`, `PreCompact`, `SessionStart` (`startup\|resume\|clear\|compact`); Claude also `Notification:auth_success` | measures the context, snapshots before a compaction, injects the handoff at session start, records the session, checks plan drift |
| `runtime-gate.py` | both | `PreToolUse` / `PostToolUse` on `Agent` (Codex `^Agent$\|spawn_agent$`), `SubagentStart`, `SubagentStop`; Claude with Fable also `StopFailure`; the statusline | reroutes the top model during an outage, asks before an EXPERT launch or past the fan-out, records the quota |
| `dialog-gate.py` | both | `PostToolUse:AskUserQuestion` (Codex `request_user_input`), `Stop` | records the human's picks from the runtime's own dialog; holds the turn while a decision is open |
| `project-scaffold.sh` | Claude | `Setup:init` | creates `docs/sdlc/` and the runtime layout on `/init`; never overwrites |
| `memory-pre-push.py` | both | a git `pre-push` hook, not a runtime hook | validates the compact record before it travels (`docs/local-memory.md`) |

All of them read the tool payload on stdin and print nothing when they allow.
A refusal is a JSON decision on stdout with exit 0, so the runtime shows the
reason and the agent can answer it. Every hook fails **open** on an internal
error — a broken hook never locks a session — with two deliberate exceptions
that fail closed: the git consent rule when the consent ledger cannot be read,
and `state.py approve` from an agent. The hooks run with `python3 -I -S`, so a
module planted in the working directory is never imported.

## Two runtimes, one set of rules

The same files are installed under `~/.claude/hooks/` and `~/.codex/hooks/`
(`hooks/hooks.json` and `hooks/codex-hooks.json` carry the registrations; the
installer merges them into `settings.json` and Codex's `hooks.json`). The guard
normalises the payload first: Codex's `apply_patch` becomes an `Edit`,
`shell` / `exec_command` / `local_shell` become `Bash`. One `apply_patch` can
touch many files, so every `*** Add/Update/Delete File:` and `*** Move to:`
path in the patch is checked on its own — a single refused path rejects the
whole patch; split the patch rather than widening the step.

Two differences stay. Codex's read tool is not on the hook path, so
`cap-large-read.py` is Claude-only and the read rule is prose there. And Codex
runs a hook only after you have **reviewed and trusted it in `/hooks`**; after
an upgrade changes an entry, that entry is skipped until you trust it again,
and nothing on screen says so.

## What these guards are, and are not

A guard is a regular expression over a command line or a path, run on every
matching tool call. That makes it defence-in-depth against an ordinary mistake:
reading `.env` to check a value, editing one file too many, a `--force` typed
out of habit. It is **not a security boundary**. A process that wants to get
past it can build the command from variables, pipe through base64 or use a tool
that is not on the hook path. The real backstops are server-side branch
protection, secrets kept off the developer machine and human review of every
diff. Each accepted gap is written down in [known-risks.md](known-risks.md).

## The git check — every repository

Runs on `Bash` in every repository, with or without `.ai/`. A cheap prefilter
(`git`, `gh`, `argocd`, `helm`, `kubectl`, `terraform`, `dep`, `deployer`,
`cap`, `flyctl`, `fly`, `vercel`, `netlify`, `npm`) keeps every other command
off the path. Prose is stripped before matching, so a commit message that
mentions `--force` is not a force push. The rules, in order:

1. **Staging a secret.** `git add` of a path matching
   `sensitive_staging_patterns` — `.env` and its `.local|prod|production|staging|live`
   variants, `secrets/`, `credentials/`, `id_rsa|dsa|ecdsa|ed25519`,
   `*.pem|p12|pfx|jks|keystore`, `.aws/credentials`, `auth.json`, dumps and
   exports in `.sql|.sql.gz|.csv`. `git add .`, `-A`, `--all` and `*` ask
   `git status --porcelain --untracked-files=all` what they would stage.
2. **Force push**: `-f`, `--force`, `--force-with-lease`, `--force-if-includes`.
   A repository listed in `allow_force_push_repos` (by directory name) is exempt.
3. **Remote branch delete**: `push --delete` / `-d`, or `push origin :branch`.
4. **History rewrite**: `filter-branch`, `filter-repo`, `push --mirror`.
5. **Push to a protected branch** — the target from the refspec, or the current
   branch for a bare `git push`; `protected_branches` defaults to `main`,
   `master`, `production`, `prod`, `stable`, `release/*`, `hotfix/*`.
   `allow_protected_push_repos` exempts a repository.
6. **Merge while on a protected branch**, `gh pr merge`, and `git reset --hard`
   on a protected branch.
7. **`--no-verify`** (or `-n`) on `commit` and `push`.
8. **Production deploy commands** (`deploy_patterns`): `argocd app
   sync|rollback|delete`; `helm upgrade|install|rollback|uninstall|delete …`
   naming `prod`, `production` or `live`; `kubectl --context …prod|production|live`;
   `kubectl delete|drain|cordon namespace|node|deployment`; `dep|deployer deploy
   prod`; `cap production deploy`; `terraform apply|destroy`; `fly|flyctl
   deploy`; `vercel|netlify deploy|--prod`.
9. **`npm publish`** and **`npm version`** — a release is a human's command.
10. **Consent.** With the dialog switch on (`.ai/policies/dialog.json`), a
    `git commit` or `git push` runs only as the next live pick the human made
    in the runtime's dialog, verbatim; anything else is refused as
    `CONSENT_REQUIRED`. A pick never lifts rules 1–9.

**Configuration.** The installer copies `hooks/ai-git-guard-defaults.json` to
`~/.claude/hooks/ai-git-guard.json` and `~/.codex/hooks/ai-git-guard.json`
once and never overwrites them, so a local edit survives a re-install; each
runtime has its own copy. The tunables are `protected_branches`,
`deploy_patterns`, `sensitive_staging_patterns`, `allow_force_push_repos` and
`allow_protected_push_repos`. An empty list falls back to the shipped default
for that key. The shared policy `policies/git.md` says the same rules in prose
for the agent.

## The path check — where `.ai/` exists

Runs on `Read`, `Edit`, `Write`, `MultiEdit`, `NotebookEdit` and `Bash`, and
is inert outside a project with `.ai/` above the working directory — with one
exception, the `--confirm-delete` rule below, which holds everywhere. Patterns
are POSIX extended regular expressions over the absolute path, both the literal
path and its resolved one, so a symlink to a secret is caught, and creating one
(`ln -s`) is refused too.

Four lists, from `hooks/ai-path-guard-defaults.json` unioned with the
project's `.ai/policies/path-guard.json`; `allow_patterns` wins over every other
list:

| List | On | Shipped default |
|---|---|---|
| `deny_patterns` — secrets | read **and** write | `.env` and its `.local|prod|production|staging|live` variants, `secrets/`, `credentials/`, `.ssh/`, `id_rsa|dsa|ecdsa|ed25519`, `*.pem|p12|pfx|jks|keystore`, `.aws/credentials`, `.docker/config.json`, `kubeconfig` / `.kube/config`, dumps and exports in `.sql|.sql.gz|.sql.bz2|.csv|.xlsx`, any `*.sql|*.sql.gz`, production logs under `var/log/`, `auth.json` |
| `allow_patterns` | lifts a deny | `.env.dist|example|sample|test|template`, docs and templates under `secrets/`, `migrations/*.sql|.php`, `tests/*.sql`, `fixtures/*.sql|.csv` |
| `protected_config_patterns` — the pipeline's own files | write refused, read allowed | `.ai/state/` (the task state, the handoff, the consent ledger), `.ai/reports/<id>/task.md`, `questions.md`, `events.jsonl`, `adopt.json`, `migration.json`; `.ai/policies/*.json`; the compact record `.ai/memory/` and `.ai/local/memory/`; the installed guards and their configuration (`.claude/hooks/ai-*`, `.codex/hooks/ai-*`, `runtime-gate.py`, `hooks/guard/`, `hooks/lib/`), `skills/ai-task/` (where `state.py` lives) and the plugin cache `plugins/cache/*/riskrails` |
| `task_protected_patterns` — the rules a run is judged by | write refused only while a task is in flight (`.ai/state/state.json` exists and has not reached `done`) | `.claude/settings*.json`, `.codex/config.toml`, `.claude/plugins/installed_plugins.json`, `.ai/policies/`, the shared tree `<home>/riskrails/ai/` and its `ai-path` resolver |

A project's `dependency_instruction_patterns`, from an older policy file, is
read as `deny_patterns`.

**Shell commands.** A `Bash` command is scanned as text once a loose match
says it names a guarded path or a `state.py` / `update.py` verb. Top-level
`sh -c '…'` and `eval` segments are split and each one checked; interpreter
one-liners (`python3|perl|ruby|node|php -c|-e`) are scanned for a secret
reference or a write to a control file. A command over 4 096 characters that
names a guarded path or such a verb is refused outright ("Refusing a
N-character shell command …"), as is a single token over 4 096 characters that
carries a glob or an expansion, and a `--co…` / `--ap…` line over 16 384
characters. A shell `mv`, `cp` or `rm` of a directory that holds a control
file or a runtime configuration is refused as a whole.

**Human-only commands.** These are refused from an agent session and pass
only as the dialog's pick, or under `AI_UNATTENDED=1`:

- `state.py approve …` while a task is in flight;
- `state.py profile set …` and any `state.py … --by <name>` verdict while the
  dialog is on and no pick covers it;
- `update.py --apply --confirm-delete …` — in every directory, `.ai/` or not;
  `adopt.py`'s own `human_gate()` refuses it a second time when an agent
  marker is in the environment;
- running `hooks/dialog-gate.py` from a shell, unconditionally.

**Fast path.** A path that matches none of the lists exits in one in-process
regex pass; the timed cases in `tests/test_guard_characterization.py` keep an
`Edit`, `Write` or `Read` inside the step under 25 ms and a 1 KB `Bash`
command under 40 ms ([hook-performance.md](hook-performance.md)).

## The scope check — during an implementation step

Runs on `Edit`, `Write`, `MultiEdit` and `NotebookEdit` (an `apply_patch`
arrives as an `Edit`). It reads `.ai/state/state.json` (or the legacy
`current.json`) and acts only while `current_stage` is `implementation` and a
step is current: a write to a file the step does not name in `allowed_files`,
or names in `forbidden_files`, is refused with `SCOPE_CHANGE_REQUIRED` in the
reason. Globs use extended-glob syntax. The answer is never to reword the
write: widen the task in place with `state.py start --amend --files "+<path>"
--why "…"`, which is journaled, or leave the file for its own task.

## The decision check — while a decision is open

The first check `ai-guard.py` runs, on every tool, and only when the dialog
switch is on and `.ai/state/decision.json` holds a decision of this session.
While it does, every tool is refused with `DECISION_PENDING …` except: the
dialog tool itself, when its questions are the ones `state.py` prepared; a
`Bash` command equal to the next live pick (a git pick is handed to the git
check); and `state.py decision show|settle|fallback`. A guarded command that is
not the next live pick voids the picks (`CONSENT_MISMATCH`). An offer the human
never answered makes the gate run `state.py decision fallback` and refuse once.

## dialog-gate — the human's picks

`state.py` opens a decision — the approval at close, a budget refusal, a
guarded git command — by writing `.ai/state/decision.json`; the runtime's own
question tool (`AskUserQuestion` on Claude, `request_user_input` on Codex) shows
it. `dialog-gate.py` on `PostToolUse` records the answer as a pick or a decline
in `.ai/state/consent.jsonl` and prints nothing. On `Stop`, while a decision is
open, it blocks the turn with `DECISION_PENDING <ids> — call <tool> with exactly
this JSON, then run the picked command verbatim`, at most `stop_blocks_max`
times (default and maximum 2) per decision per human turn, then ends the turn
with a `systemMessage` naming the terminal command (`state.py decision settle
--id … --pick <n>`, or `decision fallback`). It never denies a tool and exits 0
always.

The switch is `.ai/policies/dialog.json` (`enabled`, `window_seconds` 120
clamped to 30–600, `stop_blocks_max`), written on by `/rr-setup --update`
(migration 0010) and off by setting `"enabled": false`. The gate is inert under
`AI_UNATTENDED=1`, when `CLAUDE_CODE_SESSION_ATTENDED=0`, inside a subagent,
without a session id, or when the installed profile's `dialog.tool` is not the
runtime's question tool. Option labels are at most 400 characters and may not
contain `; & | $( < >`, a backtick or a newline, so a pick can be run verbatim.

## cap-large-read — Claude only

Refuses an unbounded `Read` of a file over 4 000 lines or 250 KB
(`AI_READ_MAX_LINES`, `AI_READ_MAX_BYTES`; the older `CLAUDE_READ_MAX_*` names
still work). An explicit `limit` up to the line budget passes; a larger one is
refused too, naming the budget. Images, PDFs and notebooks are skipped. The
rule exists because a large file read into the context is paid for on every
later turn; the cheap reader (`Explore`, `log-reader`) returns the `file:line`
excerpts instead.

## context-guard — context, compaction, session

One file for both runtimes; it reads its own location to know which one it is
in.

- **`UserPromptSubmit`**: reads the context size from the transcript and warns
  once per 10k tokens from 80% of the point where compaction fires (133k on a
  200k session, 773k on a `[1m]` one). With `--context economy`, or a window
  you set yourself, it also holds a prompt back once from 120% — sending the
  same prompt again goes through. By default it never blocks.
  `AI_CONTEXT_WARN_TOKENS` / `AI_CONTEXT_BLOCK_TOKENS` set the thresholds in
  tokens; `0` turns one off. When the prompt starts a different task, it says
  so and suggests `/clear`.
- **`PreCompact`**: writes a snapshot — edited files, the latest instructions
  verbatim, the todo list, the git state, the `.ai/` task state — and tells the
  summary what to keep; after the compaction the snapshot comes back as
  "Session state before compaction", which a resumed session trusts over the
  summary. The snapshot is built from a Claude transcript and is Claude-only.
- **`SessionStart`**: writes `.ai/state/session.json` (runtime, prompt count,
  last human turn) and, with a task in flight, injects `handoff.md` and the
  pending questions. Codex has the same three events, so the handoff crosses.
- **`Notification:auth_success`** (Claude): after a login, checks whether the
  account's plan drifted from the installed profile and opens the
  `profile set` decision; `drift-ack.json` silences a known drift.

Before a compaction it runs `git branch --show-current` and `git status
--short` in the working directory — see [known-risks.md](known-risks.md).

## runtime-gate — the model ladder, enforced

One hook for both runtimes, registered on the agent-launch events and wrapped
around the statusline (`runtime-gate.py statusline --then '<your command>'`).

- **Reroute.** While the top model is rate-limited or unreachable, a launch
  that asks for it goes one tier down: Fable → Opus on Claude; on Codex an
  EXPERT launch is rewritten to STRONG — to a `<role>-strong` twin when one is
  installed, otherwise by setting the model and effort on the call — because a
  Codex agent file's pinned model beats the model asked for at launch. The
  outage is learned from `StopFailure`
  (`rate_limit|model_not_found`, Claude with Fable) or from the error text at
  `PostToolUse` / `SubagentStop`, and held for a TTL: 1 h after a rate limit,
  6 h after a model-not-found, 15 min after an overload
  (`AI_RUNTIME_GATE_TTL`, `_NOT_FOUND_TTL`, `_OVERLOAD_TTL`). Every reroute is
  journaled as `model_fallback`; an EXPERT child that starts during an outage
  anyway is journaled as `missed_reroute`.
- **Budgets.** Before an EXPERT launch, or a launch past the plan's fan-out,
  it asks on Claude and explains on Codex (a Codex hook cannot ask).
  `expert.max_per_task` and the agent counts come from
  `<home>/riskrails/profile.json`; a running-agent entry expires after 30
  minutes (`AI_RUNTIME_GATE_AGENT_TTL`) if its `SubagentStop` was lost.
- **Quota.** The statusline payload (Claude) and the newest rollout (Codex)
  record the weekly usage; from `WEEKLY_PCT` 90 (`AI_RUNTIME_GATE_WEEKLY_PCT`)
  every Fable launch goes to Opus until the reset. `runtime-gate.py status`
  shows the gate, `clear` re-enables the top model early and empties the agent
  count, `quota --json` prints the record with its `stale` and `resets_at`
  fields.
- State lives in `<home>/state/runtime-gate.json`; `AI_RUNTIME_GATE=off`
  disables the hook. The older `CLAUDE_FABLE_GATE_*` and `CODEX_MODEL_GATE_*`
  variables are still read.

Codex has no `StopFailure`, so a failure there is attributed at
`SubagentStop`, and only when the evidence points at an EXPERT agent: its name
in the text, an explicit expert `model`, an agent file pinned to the expert
model, or an expert launch inside the last five minutes.

## Turning a guard off for one repository

- A git rule: edit `~/.claude/hooks/ai-git-guard.json` (and the Codex copy) —
  `allow_force_push_repos`, `allow_protected_push_repos`, or a narrower
  pattern list.
- A path rule: the project's `.ai/policies/path-guard.json` adds
  `allow_patterns`; it cannot remove a shipped deny, because the lists are
  unioned.
- The dialog: `"enabled": false` in `.ai/policies/dialog.json`.
- The scope guard: it is the plan; widen the task with `start --amend`.

A hook removed from `settings.json` or `hooks.json` is simply gone — the
installer puts it back on the next run.

## Testing them

```bash
python3 -I tests/run_suite.py tests/test_ai_git_guard.py tests/test_ai_path_guard.py tests/test_ai_scope_guard.py
python3 -I -m unittest discover -s tests -p test_guard_characterization.py
python3 -I tools/golden-diff.py            # which golden records moved against HEAD
```

The fixtures under `tests/fixtures/{git,path,scope}-guard/` and
`tests/fixtures/codex-hooks/` are JSON payloads for both runtimes.
`tests/fixtures/guard-characterization/golden.txt` holds 1 341 recorded
decisions — exit code and full deny text — and
`test_guard_characterization.py` compares the guard against it byte for byte,
so a performance change or a port proves it moved no decision. A deliberate
rule change re-records with `tools/golden-diff.py --record` and the diff is
read record by record; `hooks/CLAUDE.md` says how such a change is weighed.
`tests/test_dialog_gate.py`, `test_dialog_consent.py`, `test_context_guard.py`
and `test_runtime_gate_{fable,codex}.py` cover the other hooks; no suite reads
or writes the real `~/.claude` or `~/.codex`.
