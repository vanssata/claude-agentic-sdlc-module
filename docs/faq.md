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
- **A git operation** — adjust `~/.claude/hooks/ai-git-guard.json`
  (`protected_branches`, `deploy_patterns`, or the per-repository allow lists).
  It is your file; the installer never overwrites it.

## How do I widen scope in the middle of a step?

Have the agent report `SCOPE_CHANGE_REQUIRED` with the file it needs and why,
then amend that one step in the plan and re-register it:

```bash
python3 ~/.claude/skills/ai-task/state.py plan --ref <plan> --steps steps.json
python3 ~/.claude/skills/ai-task/state.py step <step_id>
```

One step is amended, not the whole task replanned.

## How do I turn a guard off for one repository?

The path and scope guards are already off in any repository without `.ai/`. The
git guard is global by design, but takes per-repository escape hatches:

```json
{ "allow_force_push_repos": ["my-sandbox"],
  "allow_protected_push_repos": ["my-notes"] }
```

in `~/.claude/hooks/ai-git-guard.json`, matched against the repository's directory
name.

## Why does the pipeline never commit or deploy?

Because the failure mode of an agent that can deploy is unbounded, and the cost of
a human typing one command is not. The pipeline ends at a release report and an
approval; the commands that would run next are printed, not executed.

If you ask for a commit in your own message, the agent commits. That is a person
deciding, which is the distinction that matters.

## Why did `/ai-task` not spawn any agents?

Because the project's `pipeline_profile` is `solo` and the tier was T0 or T1.
Every stage still ran — look at `history[]` in the state file — but the session
did them inline: your request plus `grep -n` was the discovery, the trigger
table was the risk classification, the verification command was the test. A
subagent costs its own context window, and for a change you could describe in
one sentence it buys nothing. From T2 the review is always a separate context,
and from T3 planning is too.

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

## Do I have to run `/ai-init` before `/ai-task`?

Yes. Without `.ai/` there are no policies, no tier table, no state directory and
no path or scope guard — `/ai-task` would be a name for improvisation.

## What happened to claude-routing?

It is part of this plugin now. Installing this one migrates its managed
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

Claude Code has no local-model backend. The work a LOCAL tier would have done —
indexing, listing, summarising git history — is done by deterministic tools and by
`ai-indexer` on the cheapest hosted model. Nothing depends on a local model
existing, so one can be added later without redesigning anything.

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
