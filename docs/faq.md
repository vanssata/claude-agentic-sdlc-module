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
- **Runtime configuration, while a task is in flight** — settings, agent and
  skill definitions, commands, hooks and the pipeline's policies are frozen for
  the length of a run, so a task cannot change the rules it is being judged by.
  Reading them is allowed. Finish or archive the task (`state.py close`) and the
  same edit goes through; if it genuinely belongs inside the run, it belongs in
  the plan, not in a side edit.
- **An instruction file inside `vendor/` or `node_modules/`** — a `CLAUDE.md` or
  `.cursorrules` that came with a package is data, not an instruction, and the
  next install overwrites it. If you really need to read one, add a regex to
  `allow_patterns` and say why. Ordinary source inside a dependency is not
  affected.
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

## `step-done` refused my step. Now what?

It printed which of the two it was and the command that answers it.

`DIFF_BUDGET_EXCEEDED` means the step changed more than its tier's budget
allows — not that the work is wrong, but that it has become two steps and would
be reviewed as one. `SCOPE_CHANGE_REQUIRED` means it touched a file the plan did
not give it. Both leave the step in progress, so nothing is lost:

```bash
python3 "$AI_HOME/skills/ai-task/state.py" step-split <step_id> --files "<the other concern>"
```

The moved files become a sibling step that inherits the tree the original
started from, and the original is told they are no longer its business — which
the scope guard reads too. Then finish the original and run `step <new_id>`.

The budgets live in `.ai/policies/risk-tiers.json` under `diff_budget`, and
they are a project's to adjust, like the triggers. `--force` exists for when a
refusal is genuinely wrong; it records the step anyway, and the record shows
that it was forced.

## Why did my task's risk tier go up by itself?

Because the diff reached something the tier did not predict. After every step
the task's changed files are matched against `path_scopes` — `**/Payment/**`,
`**/Security/**`, `**/migrations/**`, `config/**` and so on — and the highest
`min_tier` among them wins, as does one tier more when the task is over its
budget. A tier is a guess made before the work; this is the correction after it.

It only ever goes up. `downgrade_rule` has always said that only a human lowers
a tier, in writing; now `state.py risk T2` from an agent exits 5 and prints the
command for a human to run in their own terminal, with `--by`.

If a raise is wrong for your project, the scope patterns are yours to narrow.

## Why was there no adversarial review on my T2 change?

Because every deterministic sensor was green and the tier allowed it — the
intent's decision 6, and `review-economy.md` §8. `state.py review-gate` records
that as `review_status: skipped_green`, and `.ai/reports/<task-id>/sensors.json`
says exactly what was measured and on which tree.

"All green" is narrow on purpose: the suite passed **on this tree**, the
project's linter and type checker passed (or say `none` in `testing.md`), the
diff is inside its budget, the re-scored tier is still T2 or lower, every
finished step named a test that exists, no block of eight lines is repeated,
and the named tests **fail when the change is reverted**. That last one is the
point: a suite that never reaches the change passes just as green before it as
after, and a review skipped on that would have been skipped on nothing.

Anything missing is `unavailable`, which keeps the review. Nobody can assert
the skip either — `state.py set review_status skipped_green` is refused.

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

## Why can't I run the suite a sixth time?

Because `sensors.max_suite_runs` says five, and a sixth run is not the next
move — the human deciding what is happening is. `state.py test-run` counts the
runs, writes each one's full output to `.ai/reports/<task-id>/tests-suite-<n>.log`
and prints six lines. A green run needs no agent at all: exit 0 is the verdict.
A red one goes to `ai-tester`, which reads the log file and never re-runs
anything; one `--env-retry` is allowed, and only after a failure was classified
as an environment failure.

## What if the project has no e2e suite?

Write `e2e_command: none` in `.ai/policies/testing.md`. An empty line means
"not written down yet", and the next task will go looking for it.

## Where is Fable used on Max?

Only on `architect`, and only when installed with `--fable yes` (the default on
Max and Team Max). The session itself is Opus 5 [1m] by default (`/model opus` for a 200k session), `ai-expert` is pinned
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

## My `CLAUDE.md` block got much shorter. Where did the rules go?

Nowhere — they moved off the always-loaded path. What stays in the managed block
is what an agent is unsafe without: production behaviour as the source of truth,
`/ai-task` and `.ai/AGENTS.md`, the scope rule and `SCOPE_CHANGE_REQUIRED`, no
commit / push / merge / deploy, verify before reporting done, the context rules,
and tiers rather than model names. Everything else is one hop away:

- **the model ladder, the context-guard thresholds, the launcher, the guard
  list** → `~/.claude/claude-agentic/routing.md` (`~/.codex/` under Codex),
  installed beside the block and read when a routing question actually comes up;
- **the pipeline's procedure** → `/ai-task` itself, and the project's
  `.ai/AGENTS.md`, which is now a router: one row per job, pointing at the
  policy under `.ai/policies/` that answers it;
- **the project's own non-negotiables** → `docs/sdlc/constitution.md`, cited as
  `C<n>` by `/sdlc-spec`, `/sdlc-plan` and `ai-planner`;
- **a rule that only applies in one directory** → `.ai/rules/<slug>.md`, which
  `/project-update` renders into that directory's instruction file.

An always-loaded file is re-read on every turn of every task, so its size is a
tax on every task, including the ones it has nothing to do with. The budget is
2 048 B for a project block and 2 560 B for the global one; `install.sh` prints
what yours costs after every install, and `/ai-status` prints it for a project.
Both are advisory for a file the plugin does not own: it measures, it never
trims your text.

Existing projects are migrated by schema 3, which removes the `## SDLC workflow`
section the plugin used to write into the root instruction file — only when it
is still verbatim what the plugin shipped, and the original is kept under
`.ai/reports/project-update-<date>/original/`. A block you edited inside the
markers is never rewritten; you get a hint saying so instead, and a second one
naming the byte count whenever the block is over budget.

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

This matters most for one rule: the deny that stops an agent session from
running `state.py approve`. Under Claude Code it is enforced; under an untrusted
Codex install the approval gate is policy, not enforcement. Nothing in the
plugin can approve a hook for you — that is the point of the review — so trust
them right after installing. `/ai-status` says whether you have.

## Why does Codex have `ai-risk-strong`, `ai-planner-strong` and `ai-expert-strong`?

Because Codex resolves a value in an agent's own file *ahead* of the value passed
when the agent is spawned. "Run `ai-risk` on a stronger model" is silently ignored
there, so the STRONG re-run is a separate agent that pins Sol. Under Claude Code
the same escalation is `model: opus` on the ordinary agent. Same tier, same
trigger. `ai-expert-strong` exists for the same reason in the other direction:
while the EXPERT model is rate-limited or unreachable, the runtime gate cannot
move `ai-expert` by rewriting its `model`, so it rewrites `agent_type` to the
twin, which pins Sol.

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

No. `.ai/policies/*.json`, `.ai/state/*.json`, `.ai/state/handoff.md`, the task's
`questions.md` and `events.jsonl`, and the guards' own files are refused by the
path guard. A human edits them, outside an agent run, where the change shows up
in review. An agent that can rewrite its own constraints does not have
constraints.

## Where do the questions, the journal and the handoff live?

With the task, and each has one writer:

| File | Written by | For |
|---|---|---|
| `.ai/reports/<task-id>/questions.md` | `state.py ask` / `answer` / `questions --sync` | decisions a human has to make |
| `.ai/reports/<task-id>/events.jsonl` | `state.py emit` | the append-only journal `/ai-status` and `/usage-report` read |
| `.ai/state/handoff.md` | `state.py handoff` | the thirty lines a session reads first after a `/clear` or a compaction |
| `.ai/state/session.json` | `hooks/context-guard.py` | which runtime is driving, and when you last took a turn |

`questions.md` and `events.jsonl` are archived with the task; `handoff.md` and
`session.json` are git-ignored, because they describe a session and not the
repository. You edit the `[Answer]:` lines in `questions.md` by hand — that is
what it is for — and then tell the session to run `state.py questions --sync`.
Nothing else in there is yours to edit, and the guard enforces it.

## A subagent asked me a question and then stopped. Why?

Because a subagent has no user to ask. It returns `QUESTIONS_NEEDED` with the
question instead of guessing, the manager writes it into `questions.md`, and the
stage commands exit 4 while a question is pending. The alternative — a subagent
that invents the answer it needed — is how a plan quietly ends up built on an
assumption nobody made.

## Why can the agent not approve its own plan?

Because then it is not an approval. At T3+ the pipeline stops at a gate, and the
gate has exactly two doors. Run, in **your own terminal**:

```bash
python3 <plugin>/skills/ai-task/state.py --root . approve --by "<your name>"
```

`approve` checks for a TTY, so the same line run through the agent's shell exits
5 and changes nothing. Or set `[Answer]: A` on the gate's question in
`.ai/reports/<task-id>/questions.md` and tell the session to run `state.py
questions --sync`; that door opens only behind a turn you actually took —
`context-guard.py` records it in `.ai/state/session.json`, and the path guard
refuses to let an agent run that hook by hand. And `state.py approve` from an
agent session is refused outright.

## How do I approve in CI, where there is no human?

Export `AI_UNATTENDED=1` in the environment your launcher starts the run in. It
turns off both deny rules and lets `approve` succeed without a terminal.

Two things to know. **Do not export it in an interactive shell** — every session
that inherits it runs without the gate, for as long as the shell lives, and
nothing will remind you. And it does not hide: the approval is recorded as
`via: "unattended"`, `unattended: true` in the state and in the journal,
permanently, and `/ai-status` calls out any such approval. The gate can be
turned off; it cannot be turned off quietly.

## What is schema 2?

`.ai/VERSION`. Schema 2 adds the journal, the questions file, the handoff and
the keys that go with them (`owner_runtime`, `resume_point`, `questions`,
`handoff`, and the gate's fields under `human_approval`). `/project-update`
migrates an existing project: the keys are added only where absent, and the
journal is backfilled from `history[]` with every backfilled line marked as
such. A task in flight keeps working before and after. Running it twice changes
nothing the second time.
