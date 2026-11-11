---
name: rr-setup
description: Set up and maintain the .ai/ layer of an existing production codebase. With no flag, scaffold docs/sdlc/, the runtime directory and .ai/, ask the open options (memory, runtimes, survey depth, verify command) in one dialog, survey the code into .ai/project/ (light or full), write the Verification commands, the weight table's project entries and the constitution — read-only towards application code. --options asks them all again; --update regenerates a project's files from the installed plugin (a copy that is a shipped version is replaced, an edited one waits for the human, the project's own files are kept); run it right after installing a new riskrails; --audit scores the repository against the twelve plays and writes docs/ai-sdlc-adoption-plan.md. Use on "/rr-setup", "set up this project", "analyse this project for AI work", "update the rules", "обнови правилата", "audit our AI setup", or when /rr-status says the project is behind.
argument-hint: [--survey light|full] | --options | --update [--apply] | --audit [context]
---

# /rr-setup $ARGUMENTS

Resolve the install root once; the skill is the same under Claude Code and Codex:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-setup" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
UPDATE="python3 $AI_HOME/skills/project-update/update.py $PWD"
SETUP="python3 $AI_HOME/skills/rr-setup/setup.py"
```

`--options`, `--update` and `--audit` go to their sections below; anything else
is **Setup**. In every mode: no application code changes — not a rename, not a
formatting fix. Problems you find are written down, never fixed. Never read
`.env`, secrets, dumps or production logs. Do not commit; suggest the `git add`.

## Setup

0. **Options.** Project memory, the runtimes, the survey depth and `verify_command`
   are asked once, in one dialog, before any work; the picks feed steps 1, 3 and 5.

   ```bash
   "$AI_HOME/skills/ai-init/scaffold-ai.sh" "$PWD" --runtime none   # 0a
   $SETUP options --open    # 0b; --options adds --all, a given --survey adds --skip survey
   ```

   **0a** makes `.ai/` (so `.ai/policies/dialog.json`) and its `.gitignore` lines, with no
   instruction file and no runtime directory; only this script takes `none`
   (`project-scaffold.sh` refuses it). If its output does **not** list
   `.ai/project/overview.md`, the project was set up before.

   **0b** prints one of three first lines:
   - `OPTIONS_DIALOG D<n> …`, then state.py's `DIALOG_PENDING` line and a JSON: send that
     JSON exactly as printed with the dialog tool the line names (AskUserQuestion; Codex:
     request_user_input).
   - `OPTIONS_FALLBACK <why>`: nothing was opened. Ask the numbered questions after it in
     chat as printed, the answers being the picks; show its `memory is the human's` line
     as printed and never run it.
   - `OPTIONS_NONE`: nothing to ask.

   Exit 6 (no first line, the reason on stderr): `DECISION_LIMIT` or `DECISION_DUPLICATE`
   means a decision is already open — settle every one first (`$STATE decision show` and
   send it, or `$STATE decision fallback --id <Dn> --why "<why>"`), then run 0b once more.
   Any other refusal, or a second one: ask the questions of steps 1, 3 and 5 in prose and,
   in a git work tree, give the human for their own terminal, with `$AI_HOME` and `$PWD`
   substituted: `python3 "<home>/skills/ai-task/state.py" --root "<project>" memory enable
   --period quarter [--index sqlite]`.

   **0c** — the human answers. After a dialog, a memory command they picked is run first,
   at once, verbatim and alone; it prints `memory: via dialog (consent C<n>, decision D<n>)`
   and its pick settles its decision. Then `$STATE decision settle --id <Dn>` for each other
   decision: it prints `D<n> settled: <label> (set)` and `SETUP_PICK <key>=<value>`, after
   a decline `SETUP_PICK <key>=`. Apply each pick where its step needs it:
   - `runtime=<v>` → step 1's two scaffolds with `--runtime <v>`;
   - `verify=<cmd>` → `$SETUP verify --set "<cmd>"` after step 2; `keep` and `edit` → nothing;
   - `survey=light` or `full` → step 3's depth; `keep` → no new survey;
   - `memory=off` or `keep` → nothing: a picked command already ran.

   An empty value (`verify=` is "Not now"; any key after a decline) or `other` → the step
   as it was without the dialog: step 1 passes `auto`, step 3 surveys `light`, step 5 asks
   in chat.
1. **Scaffold.** Both scripts are idempotent, never overwrite, and print what
   they created; note it, 0a's too. They take `--runtime auto|claude|codex|both`
   (`auto` follows `CLAUDE.md`/`.claude/` and `AGENTS.md`/`.codex/`); pass the
   `runtime` pick, else `auto` — `both` when the repository is worked on from
   both runtimes.

   ```bash
   "$AI_HOME/hooks/project-scaffold.sh" "$PWD" --runtime <pick>      # docs/sdlc/, the runtime dir, .gitignore
   "$AI_HOME/skills/ai-init/scaffold-ai.sh" "$PWD" --runtime <pick>  # the instruction file; .ai/ is 0a's
   ```

   If 0a did **not** create `.ai/project/overview.md`, the project was set up
   before: run **--update** below, then ask whether the survey should be
   refreshed; a refresh never overwrites a `.ai/project/` file a human edited
   without saying so first. If 0a and this step together created only an
   instruction file (no `.ai/` wanted), fill its Commands / Conventions /
   Architecture from the manifests — one line per command, five sentences of
   architecture — and stop.
2. **Stack.** `$SETUP survey` first: the project's own toolbox
   (`.claude/{skills,commands,rules,agents,hooks}`, `.codex/*`, `bin/*.sh`,
   Makefile targets) with each item's purpose, the guards a project hook
   already covers, a proposed `verify_command`, and the superpowers line. It
   runs nothing and writes nothing. Then a handful of `ls` and `grep -n` calls,
   not a delegation:
   `composer.json`, `package.json`, `Makefile`, `pyproject.toml`, `go.mod`,
   compose files, CI config, `Chart.yaml`/`argocd/`, test and lint configs
   (`phpunit.xml*`, `phpstan.neon*`, `playwright.config.*` …). For Symfony or
   Sylius also: bundles, entities, state machines, Messenger, event
   subscribers, payment, shipping, tax, promotions, ERP or fiscal integrations.
   Then write the `verify=<cmd>` pick, if any (0c).
3. **Survey.** The depth is the `survey` pick or `--survey light|full`. `light`,
   the default, is for a developer who knows the project: ask for a ten-minute
   brain dump (entry points, modules that matter, integrations,
   unwritten business rules, areas nobody dares touch), confirm
   each claim with `grep -n`, then fan out exactly **two** `ai-discovery` agents
   in one message: (1) legacy, risks and code that looks unused; (2) tests,
   CI/CD, data and configuration — how secrets are supplied, never their
   values. `full`, for a codebase new to you: one `Explore` for the
   inventory, then six `ai-discovery` agents in one message — entry points;
   domain modules; integrations and their failure handling; business rules and
   legacy; tests and CI/CD; data and configuration. Hand each the slice of the
   inventory it needs. Each agent runs on its own tier; do not move it.
4. **Write `.ai/project/`.** Keep every label verbatim — KNOWN FACT with
   `file:line`, INFERENCE with what it rests on, UNKNOWN with what would answer
   it, RISK with what could go wrong. Where documentation and code disagree,
   write `Documented behaviour / Observed behaviour / Evidence / Risk` and do
   not resolve it.
5. **Policies.** Fill the project sections of `.ai/policies/coding.md` and
   `testing.md` only if 0a created them. The **Verification** block of
   `testing.md` is the feedback loop every task runs:
   - `verify_command` — the fast suite to the end, the e2e group **excluded**;
   - `step_test_command` — the same runner on given paths (`{files}`);
   - `e2e_command` — the end-to-end suite, or `none` when there is none;
   - two or three lines of what healthy output looks like.

   `verify_command` comes from the human: the `verify=<cmd>` pick is their yes,
   written at the end of step 2; without one, show the one `$SETUP survey`
   proposed, ask, and only after a yes in chat write it with
   `$SETUP verify --set "<command>"` (exit 3: one is already set — the human
   edits it). `$SETUP check` then exits 0; `VERIFY_COMMAND_MISSING` (exit 1)
   means setup is not finished, and the report says so.

   Copy them under `## Verification` in the project instruction file. Shared
   policies (`database.md`, `tooling.md`, `release.md` …) live in
   `<home>/riskrails/ai/` and are never written there; when the project has
   something to say in one, copy the whole file that
   `"$AI_HOME/riskrails/ai-path" policies/<name>.md` prints to
   `.ai/policies/<name>.md` and fill that copy — it is now an override. Check
   that `.claude/settings.json` keeps `"enableAllProjectMcpServers": false` and
   that each server in a checked-in `.mcp.json` sits in `enabledMcpjsonServers`
   only if it earned it, else in `disabledMcpjsonServers`; say what you found.
6. **Weight table.** The plugin ships the table; this codebase's own paths go in
   `.ai/policies/weight.project.json`, laid over it: `domain.modules` (money,
   identity, personal data), `domain.customer_visible`, `scope.hot_paths`,
   `reversibility.needs_step` and `irreversible`, and one or two `examples` per
   mode. The JSON is the human's to edit (the path guard refuses yours);
   `--update` renders `weight.md` from the table and the overlay. The
   thresholds are not this skill's to move.
7. **Constitution.** Fill `docs/sdlc/constitution.md`: C1–C5 ship prefilled;
   C6 onwards are one line each, drawn from what the code and tests already
   enforce. Leave a slot empty rather than write a platitude; at most fifteen.
   `python3 "$AI_HOME/skills/project-update/render_instructions.py" constitution
   docs/sdlc/constitution.md` checks the cap. Show the list for confirmation.
8. **Assessment.** Write `.ai/project/initial-assessment.md` yourself (a human
   reads it): overview, architecture, important modules, critical business
   areas, legacy hotspots, high-risk integrations, test and CI maturity,
   security observations, missing documentation, areas agents must not touch
   casually, the weight-table entries you chose, recommended next improvements —
   recommendations only, none implemented. When the survey found a toolbox,
   name each toolbox item the project keeps using; they stay where they are.
9. **Report.** Files created (a tree from the scaffold output, 0a's too), surprising
   findings, the modes and what puts a change in each, the safety restrictions
   in force (hooks versus policy), the tooling the workflows reuse, assumptions,
   unresolved questions and who can answer them, the survey's superpowers
   line as printed (the `enabledPlugins` line is the human's to add — never
   write it), and the suggested first task:
   `/rr-plan <it>`. Claim nothing was validated that was not run. Suggest
   `git add .ai .gitignore docs/sdlc` plus the instruction files created.

## --options

Reopens every option on a set-up project: 0a, then `$SETUP options --open --all`, then
send, settle and apply as in step 0 — a `survey` pick runs steps 3–4 at that depth, as a
refresh (step 1), and a `verify` command is written at once. Say what changed and stop;
no other step reruns. A project 0a just scaffolded (it listed
`.ai/project/overview.md`) continues as the plain **Setup**.

## --update

The script regenerates; you show it, confirm what is owed, and merge what it
cannot. It converts nothing but the one split. A tree that still holds an old
shape it detects (the pre-3.4b task state without `state.json`, the risk-tier
policy without a weight table, a pre-3.4b block marker) is refused with `KEPT_UNREADABLE` (exit 6); a
project last updated before 3.1.0 goes through `npx riskrails@3.1.0` first. Run it right after a new
riskrails is installed: until then the project's old shapes are not read.

1. `$STATE status`: with a task in flight, say that updating policies mid-task
   can change what the rest of it needs, and ask whether to finish it first.
2. `$UPDATE` — the dry run; show it as is. Up to date and no hint: say so, stop.
   A `regenerate` is a file that matches a version the plugin once shipped and is
   replaced; a `regenerate?` or `delete?` is a proposal for the human (step 4); a
   `create` is a file the project lacks. A project that still has the mixed
   `testing.md` and `weight.json` gets `verification.md` and `weight.project.json`
   split out of them once.
3. A `split` row writes `verification.md` or `weight.project.json`, which humans
   own from then on: say in one plain sentence what it carries out of
   `testing.md` or `weight.json`, and ask, unless `$ARGUMENTS` holds `--apply`.
4. `$UPDATE --apply`. Exit 3 stopped on a changed, non-regular or unwritable
   file and names it; nothing after it was written — run the dry run again.
   Exit 6 (`KEPT_UNREADABLE`): a file the update keeps cannot be read; nothing was
   written — name it, the human fixes or removes it, then run again.
   **A `regenerate?` and a `delete?` are the human's.** Never pass `--confirm-delete` or `--confirm-cleanup`, not even with
   `--apply`. Give them, with `$AI_HOME` and `$PWD` substituted, for their own
   terminal (the `!` prefix is refused):
   `python3 "<home>/skills/project-update/update.py" "<project>" --apply --confirm-delete "<your name>"`.
   Exit 5 (`CONFIRM_REFUSED`) means an agent session ran it; it wrote nothing.
   Every file replaced or deleted that way is first copied under
   `.ai/reports/project-update-<date>/original/`. Two kinds are housekeeping:
   `[rules]` — every rule source `.ai/rules/<slug>.md` (an update does not keep
   them; confirming deletes the source and its rendered blocks with it) and a
   rendered rule file whose source is gone or no longer sets `paths:`, both
   settled by `--confirm-delete`; `[cleanup]` —
   the `*.log` files of closed tasks, and the report and log files of an
   abandoned task (its `state.json` stays) or of one unclosed for more than seven
   days (never the task in flight; and none when `.ai/state/state.json` is unreadable).
   `--confirm-delete` does not settle `[cleanup]` rows, and the rows differ by kind:
   files under `.ai/state/logs/` are git-ignored and git cannot restore them; files
   under `.ai/reports/` are usually tracked, and the row says "tracked: git can restore
   a committed copy" or, when git holds no committed copy, "uncommitted" — then
   commit `.ai/` first (the hint says so), and an `original/` copy is kept as for any
   other deletion. They have their own command, the human's too, never passed by the agent:
   `python3 "<home>/skills/project-update/update.py" "<project>" --apply --confirm-cleanup "<your name>"`.
   Show both groups as printed. Rollback is git:
   `git restore --source=<commit before> --staged --worktree -- .ai`, before
   the plugin itself is rolled back.
5. A `regenerate?` row: the project edited a file the plugin generates. Read
   its reason; anything project-specific in it belongs in a file the update keeps
   (`.ai/project/`, `weight.project.json`, `verification.md`, the instruction
   file outside the managed block — not `.ai/rules/`, whose sources are `[rules]`
   rows too) — say where, the human moves it,
   then confirms. Never edit the generated file to dodge the row.
6. Hints. `verify_command is empty`: show `$SETUP survey`'s proposal, ask for
   the one command and what a green run ends with, write it with
   `$SETUP verify --set`, and fill the rest of the Verification block. `the managed block is N B`:
   *edited here* — offer to move the project's lines out of the markers; *the
   plugin ships it that size* — a plugin bug, report it. A constitution over
   fifteen principles or 4096 B: offer to move policy into `.ai/policies/`.
   `that rule is not rendered`: name the `.ai/rules/` file and what it lacks
   (`paths:` and a body). `overrides the plugin's shared copy`: offer to diff
   each and delete those that add nothing. `tracked by git but ignored`: show the line as printed and give
   the human the command it prints, exactly as printed, plus a commit, for their
   own terminal (never rebuilt from the path; only the xargs form untracks every
   such file under `.ai/state`, a printed `rm --cached -- <path>` one file; a
   second machine runs the same before its next pull, else a modify/delete
   conflict); never run it yourself.
7. `$UPDATE --check` and `git diff --stat`; say what changed, what you merged
   and what is the human's. Suggest `git add -A .ai docs/sdlc .gitignore` plus
   the runtime directories and instruction files.

## --audit

The only file written is `docs/ai-sdlc-adoption-plan.md`; everything else is
read-only, and the plan builds on what exists rather than replacing it.

1. **Context.** Read `.ai/project/overview.md` if it exists; otherwise ask once:
   what the project is, team size and who decides product and architecture, the
   CI/CD and staging, the tracker, hard constraints. Do not invent it.
2. **Inventory**, with `Explore` and, where judgement is needed, `ai-discovery`:
   instruction files at the root and nested (and whether `CLAUDE.md` and
   `AGENTS.md` agree), runtime config (`.claude/settings*.json`,
   `.codex/config.toml`, hooks, skills, agents), CI workflows, branch protection
   (`gh api …/protection` when authenticated, else **unverified**), test, build
   and lint entry points, `REVIEW.md`, `docs/sdlc/`, `docs/adr/`, `.ai/`. Each:
   exists / partial / missing, and one line on quality.
3. **Score** the twelve plays 0–3 from
   `$AI_HOME/skills/ai-audit/templates/play-scoring-rubric.md`, citing file and
   line; **unverified** rather than a guess, with what would settle it. This is
   judgement: do it in the session, from step 2's evidence.
4. **Three phases** of about two weeks, in dependency order: instruction file,
   skills, feedback loop, hooks, planning first; subagents and evals after the
   instruction file and feedback loop; the PR review loop after evals; CI/CD
   after the review loop and hooks; closing the loop last. Each item: the play
   and target score, the files with a sketch, the owner role, prerequisites,
   governance, one leading and one lagging metric with its data source.
5. **Guardrails**, separately, each with its minimal fix: permissions wider than
   intended, hooks bypassable or agent-editable, secrets reachable (also through
   Bash), tests editable during a fix, stale or contradictory instruction files,
   a guardrail present in one runtime and absent in the other, and — without
   `.ai/` — that only the global git guard applies.
6. Copy `$AI_HOME/skills/ai-audit/templates/ai-sdlc-adoption-plan.md` to
   `docs/ai-sdlc-adoption-plan.md`, fill it (about four pages), and say plainly
   what you could not verify.
