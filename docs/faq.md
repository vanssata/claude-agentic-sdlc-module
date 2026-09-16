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

By design: the verification command runs after the last step, not after each
one. A step's own single test may run in between when it is cheap, and a
bugfix shows its failing test first. Running a full suite per step multiplied
the slowest part of a task by the number of steps and found nothing the final
run would not.

## Where is Fable used on Max?

Only on `architect`, and only when installed with `--fable yes` (the default on
Max). The session itself is Opus 5 [1m], `ai-expert` escalates by inheriting
it, and every reader and reviewer runs on Sonnet or Opus. Design questions
outside a task are the one place a stronger model changes the outcome enough
to pay for.

## How do I get the fully delegated pipeline back?

Set `"pipeline_profile": "team"` in `.ai/policies/risk-tiers.json`. Every stage
then goes to its agent at every tier, as in the tables in `docs/agents.md`. You
can also delegate a single stage in `solo` without switching: say so in the
request, or hit one of the `delegate_anyway_when` triggers.

## Why is the session model `opusplan` on Pro?

Opus consumes the usage window far faster than Sonnet, and the main session
re-reads its whole context every turn, so the session model is the largest cost
lever there is. `opusplan` spends Opus where it changes the outcome — the plan —
and Sonnet on implementing it. Because a subagent that omits `model:` would
inherit Sonnet outside plan mode, the installer pins `model: opus` on
`ai-expert` and `architect` for this plan. Prefer Opus everywhere? Set `model` to
`opus` in `~/.claude/settings.json` and reinstall with `--plan pro`; nothing else
changes.

## Where does the verification command come from?

`.ai/policies/testing.md`, section **Verification**. `/ai-init` asks for it;
if it is empty when a task reaches TEST, the task takes the command from the
project `CLAUDE.md` or the CI config and writes it there. One command, one
healthy-output example — that is the feedback loop the playbook asks for.

## I reinstalled the plugin. Why does my project still follow the old rules?

The installer updates `~/.claude/`. A project's `.ai/`, `docs/sdlc/` templates
and `CLAUDE.md` block are copies made when it was initialised. Run
`/project-update` in the project — or `/ai-init` again, which does the same.
Files you never edited are replaced, edited ones are merged keeping your edits,
and a real conflict is never overwritten: the plugin's version lands in
`.ai/local/plugin-update/` and the skill merges it with you. Policy JSON changes
are shown key by key and applied only after you confirm.

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
session on Sol at `high` and keeps Astra as the EXPERT escalation, one named
trigger away. If you want it back, set `model` in `~/.codex/config.toml`; the
installer will set it again on the next run, so change `profiles/codex.json`
instead if you want the decision to stick.

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
