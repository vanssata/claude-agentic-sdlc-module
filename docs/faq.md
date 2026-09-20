# FAQ

## Something was blocked and I think it should not have been

Read the refusal: every deny names the rule and the pattern that matched, and
says what to do instead.

- **A sensitive path** — if the path really is safe (a `.dist` file, a fixture),
  add a regex to `allow_patterns` in `.ai/policies/path-guard.json`. Widening the
  allow list is the supported way; working around the guard is not.
- **Out of scope** — the current step does not name that file. Amend the step in
  the plan and re-register it, or finish the step first. That is the entire point
  of the guard.
- **A git operation** — adjust `ai-git-guard.json` in your runtime's hooks
  directory (`protected_branches`, `deploy_patterns`, or the per-repository allow
  lists). It is your file; the installer never overwrites it. Each runtime has its
  own copy, so edit both if you use both.
- **A whole `apply_patch` rejected over one file** — that is the rule, not a bug.
  A patch is checked path by path, and one out-of-scope or protected file rejects
  all of it. Split the patch; do not widen the step to make the patch fit.

## How do I widen scope in the middle of a step?

Have the agent report `SCOPE_CHANGE_REQUIRED` with the file it needs and why,
then amend that one step in the plan and re-register it:

```bash
python3 "$AI_HOME/skills/ai-task/state.py" plan --ref <plan> --steps steps.json
python3 "$AI_HOME/skills/ai-task/state.py" step <step_id>
```

where `$AI_HOME` is `~/.claude` or `~/.codex` — the two copies are the same
script and both write the project's `.ai/state/current.json`.

One step is amended, not the whole task replanned.

## How do I turn a guard off for one repository?

The path and scope guards are already off in any repository without `.ai/`. The
git guard is global by design, but takes per-repository escape hatches:

```json
{ "allow_force_push_repos": ["my-sandbox"],
  "allow_protected_push_repos": ["my-notes"] }
```

in `ai-git-guard.json`, matched against the repository's directory name.

## Why does the pipeline never commit or deploy?

Because the failure mode of an agent that can deploy is unbounded, and the cost of
a human typing one command is not. The pipeline ends at a release report and an
approval; the commands that would run next are printed, not executed.

If you ask for a commit in your own message, the agent commits. That is a person
deciding, which is the distinction that matters.

## Why did `/ai-task` not spawn any agents?

Because the project's `pipeline_profile` is `solo` and the tier was T0–T2:
direct mode. Every stage still ran, in a line each (at T2 the `state.py quick`
record shows them in `history[]`; at T0/T1 there is no state file at all — the
commit message is the record), but the session did them inline: your request plus `grep -n` was the discovery, the trigger
table was the risk classification, the verification command was the test. A
subagent costs its own context window, and for a change you could describe in
one sentence it buys nothing. From T2 the review is always a separate context,
and from T3 planning is too.

## Why was there no plan, and why did the scope guard not fire?

T0 and T1 have no plan stage — `stages_required` in `risk-tiers.json` says so.
The scope guard arms only for a registered step, so for those tiers the scope
is the line where the session says which files it will touch, and the
verification run at the end. From T2 there is always a registered step list,
and the guard is live.

## Why did the tests run only once?

The full suite did. By design there are three scopes, and each runs at its own
moment: a step runs **only the tests its plan step names**, through
`step_test_command` scoped to the files it touched; the verification command
runs **once, after the last step**; the e2e suite runs **once after that**, at
the end of the task. A bugfix still shows its failing test first.

Running the full suite per step multiplied the slowest part of a task by the
number of steps and found nothing the final run would not — and the e2e suite
is slower still, so it runs once, at the end, when there is a finished change
for it to exercise. What a step does need is its own tests, immediately: a
regression in the code you just wrote is cheapest to fix while you are still
in it.

## What if the project has no e2e suite?

Write `e2e_command: none` in `.ai/policies/testing.md`. An empty line means
"not written down yet", and the next task will go looking for it.

## Where is Fable used on Max?

Only on `architect`, and only when installed with `--fable yes` (the default on
Max and Team Max). The session itself is Opus 5 with the 200k window (`opus[1m]` per task, through `claude-1m`), `ai-expert` is pinned
to `opus` at `xhigh`, and every reader and reviewer runs on Sonnet or Opus. Design questions
outside a task are the one place a stronger model changes the outcome enough
to pay for.

## How do I get the fully delegated pipeline back?

Set `"pipeline_profile": "team"` in `.ai/policies/risk-tiers.json`. Every stage
then goes to its agent at every tier, as in the tables in `docs/agents.md`. You
can also delegate a single stage in `solo` without switching: say so in the
request, or hit one of the `delegate_anyway_when` triggers.

## Why is the session model `opusplan` on Pro and Team Pro?

Opus consumes the usage window far faster than Sonnet, and the main session
re-reads its whole context every turn, so the session model is the largest cost
lever there is. `opusplan` spends Opus where it changes the outcome — the plan —
and Sonnet on implementing it. Because a subagent that omits `model:` would
inherit Sonnet outside plan mode, the installer pins `model: opus` on
`ai-expert` and `architect` for this plan. Prefer Opus everywhere? Set `model` to
`opus` in `~/.claude/settings.json` and reinstall with `--plan pro`; nothing else
changes.

## Which plan does a Team account get?

It depends on the seat. A Standard seat has Pro's models and limits, so it
installs as `team-pro` and gets the Pro profile. A Premium seat has Max's, so it
installs as `team-max` and gets the Max profile, Fable on `architect` included.
The installer reads the seat from `~/.claude.json`; when it cannot tell, it
uses `team-pro` and says so — pass `--plan team-max` for a Premium seat.

## What changes between ChatGPT Plus and Pro under Codex?

The Plus usage window is a fraction of Pro's, so `profiles/codex-plus.json`
runs the session on Sol at `medium`, caps agent threads at three and runs
`ai-expert` on Astra at `high`; `xhigh` is never used. `profiles/codex-pro.json`
keeps Sol at `high`, six threads and Astra at `xhigh` for `ai-expert`. The plan
is read from `chatgpt_plan_type` in `~/.codex/auth.json`; `--codex-plan plus|pro`
overrides it.

## Where does the verification command come from?

`.ai/policies/testing.md`, section **Verification**. It holds three commands:
`step_test_command` (a scoped subset, for one step), `verify_command` (the full
fast suite, e2e excluded) and `e2e_command` (once, at the end of a task).
`/ai-init` asks for them; if one is empty when a task reaches TEST, the task
takes it from the project `CLAUDE.md` or the CI config and writes it there.
One command per scope, one healthy-output example — that is the feedback loop
the playbook asks for.

## I reinstalled the plugin. Why does my project still follow the old rules?

The installer updates `~/.claude/`. A project's `.ai/`, `docs/sdlc/` templates
and `CLAUDE.md` block are copies made when it was initialised. Run
`/project-update` in the project — or `/ai-init` again, which does the same.
Files you never edited are replaced, edited ones are merged keeping your edits,
and a real conflict is never overwritten: the plugin's version lands in
`.ai/local/plugin-update/` and the skill merges it with you. Policy JSON changes
are shown key by key and applied only after you confirm.

If the tree layout itself changed since your project was initialised, the dry
run opens with a `schema 0 -> N` line: migrations run first, in order, moving or
adding files before anything is merged. A file that moves takes your edits with
it, and the original is kept under `.ai/reports/project-update-<date>/`. A
migration can *propose* a deletion; it never performs one. Confirming it is
yours to type, in your own terminal, because an agent is not allowed to:

```bash
python3 "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/skills/project-update/update.py" . --apply --confirm-delete "<your name>"
```

(under Codex, `${CODEX_HOME:-$HOME/.codex}` instead — the skill prints the path
it resolved.)

Until you run that — or delete the file yourself — the schema version stays
where it is and the project keeps reporting as behind. There is no way to
decline a proposed deletion and carry on. `.ai/VERSION` is the schema of the `.ai/`
tree; the `"version"` inside `.ai/policies/risk-tiers.json` is that one file's
content version, and the two are unrelated.

## Do I have to run `/ai-init` before `/ai-task`?

Yes. Without `.ai/` there are no policies, no tier table, no state directory and
no path or scope guard — `/ai-task` would be a name for improvisation.

## What happened to claude-routing?

It is part of this plugin now, and the routing it did for Claude Code is one half
of what this does for two runtimes. Installing this one migrates its managed
`CLAUDE.md` block into a single block carrying both sets of rules, and retires
the `reviewer` agent that `ai-reviewer` replaces. Your model, effort and limits
do not change — they come from the same `profiles/`. The old directory can be
deleted afterwards.

## Which do I use, `/ai-task` or the `/sdlc-*` skills?

`/ai-task` for a change. The `/sdlc-*` chain when the work needs a written intent
and specification agreed before any code exists; it ends by handing its plan to
`/ai-task`, which runs the pipeline and the tier's gates as usual.

## When do I still use `architect`?

For a design question that is not a task — "how should we structure this", "what
are the options" — and in repositories that have no `.ai/`. Inside a task,
`ai-planner` plans and `ai-expert` handles what it cannot settle.

## Why is there no local model?

Neither runtime has a local-model backend. The work a LOCAL tier would have done —
indexing, listing, summarising git history — is done by deterministic tools and by
`ai-indexer` on the cheapest hosted model. Nothing depends on a local model
existing, so one can be added later without redesigning anything.

## Can I use this from Codex as well as Claude Code?

Yes, and from both over the same repository. `./install.sh` detects what you have
and installs for each; `--target auto|claude|codex|both` overrides it. The `.ai/`
tree, the pipeline, the tiers and the task state are shared — a task started in
one runtime resumes in the other. What differs is the install root, the
instruction file (`CLAUDE.md` / `AGENTS.md`) and which model each tier resolves
to. See the table at the top of the README.

## The installer changed my Codex model from Astra to Sol

Deliberately. The session model is the largest single cost in a long session —
most of it is re-reading context, not generating output — so the routing puts the
session on Sol at `high` (`medium` on Plus) and keeps Astra as the EXPERT escalation, one named
trigger away. If you want it back, set `model` in `~/.codex/config.toml`; the
installer will set it again on the next run, so change `profiles/codex-pro.json`
(or `codex-plus.json`) instead if you want the decision to stick.

## Will installing overwrite my `config.toml`?

No. Six keys are managed: `model`, `model_reasoning_effort`, and four under
`[agents]`. The merge edits those lines in place, then parses the file before and
after and **refuses to write** unless the only keys that differ are those six.
Comments, `[projects.*]`, `[mcp_servers.*]`, `[marketplaces.*]` and everything
else survive; a malformed file aborts the merge untouched. The previous version
is kept as `config.toml.bak`.

## Why do the Codex guards not seem to do anything?

Almost certainly because they have not been trusted yet. Codex does not run a
non-managed hook until you review and approve it in `/hooks`. Until then they are
installed and inert.

## Why does Codex have `ai-risk-strong` and `ai-planner-strong`?

Because Codex resolves a value in an agent's own file *ahead* of the value passed
when the agent is spawned. "Run `ai-risk` on a stronger model" is silently ignored
there, so the STRONG re-run is a separate agent that pins Sol. Under Claude Code
the same escalation is `model: opus` on the ordinary agent. Same tier, same
trigger.

## Why are my MCP servers off in this project?

Because every connected server is in the system prompt of every turn, used or
not, and the context is re-read each turn. The scaffolded `.claude/settings.json`
sets `enableAllProjectMcpServers: false`, so a checked-in `.mcp.json` is a
catalogue rather than a start-up list. Put a server in `enabledMcpjsonServers`
when nearly every task in the repository needs it, and record why in
`.ai/policies/tooling.md`. For a server one task needs, enable it, write one
`tools_for_this_task:` line in the task record, and turn it off when the task
closes.

## Why did Claude send a subagent to read one file?

Because the file was too large to read into the session. Over ~4000 lines or
~250KB the `cap-large-read` hook refuses an unbounded `Read` — and a `limit`
larger than that budget, since it costs the same. The file is then read by the
cheapest model: `Explore` for code, `log-reader` for logs and test output, both
on `haiku`. What comes back is the matching ranges with `file:line` and one line
on why each matters — never the file. Paying the session model to scroll through
a file is the most expensive way to do the cheapest job in the pipeline.

## Why is there no large-read cap under Codex?

Its read tool is not on the hook path, so there is nothing to hook. The rule is
written into `~/.codex/AGENTS.md`, which makes it policy rather than enforcement.
Worth knowing before you rely on it: under Codex, context hygiene is something the
agent follows, not something the harness imposes.

## The Codex costs in `/usage-report` look wrong

The token columns are measured; the dollar column for Codex is an estimate. The
report says so under the total, because `skills/usage-report/prices.json` has
`rates_verified: false` for that provider — the numbers there are scaled to the
tier each model serves, not published rates. Check them against the current price
list, update the file, and flip the flag; the parser does not need touching.

## Why does the main session implement instead of a subagent?

The session already holds the plan and the context; handing a step to a subagent
means rebuilding both. And the property that matters — that only the step's files
change — comes from a hook, not from which process makes the edit.

`ai-implementer` exists for mechanical pattern-copying work and for when you ask
for it.

## The risk tier looks too high for what I want to do

Say so. Tiers are raised by an agent and lowered by a human, in writing, in the
task record. That asymmetry is deliberate: an agent that can talk itself down a
tier has no tier system.

## `/ai-status` says the risk-tier mirror is stale

`risk-tiers.json` changed and `risk-tiers.md` did not. The JSON is the source of
truth, so nothing is broken — update the markdown and the sha256 comment in its
first line when you get a moment.

## Can an agent edit these policies?

No. `.ai/policies/*.json`, `.ai/state/*.json` and the guards' own files are
refused by the path guard. A human edits them, outside an agent run, where the
change shows up in review. An agent that can rewrite its own constraints does not
have constraints.
