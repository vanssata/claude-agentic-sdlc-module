---
name: rr-setup
description: Set up and maintain the .ai/ layer of an existing production codebase. With no flag, scaffold docs/sdlc/, the runtime directory and .ai/, survey the code into .ai/project/ (light or full), write the Verification commands, the weight table's project entries and the constitution — read-only towards application code. --update regenerates a project's files from the installed plugin (a copy that is a shipped version is replaced, an edited one waits for the human, the project's own files are kept); run it right after installing a new riskrails; --audit scores the repository against the twelve plays and writes docs/ai-sdlc-adoption-plan.md. Use on "/rr-setup", "set up this project", "analyse this project for AI work", "update the rules", "обнови правилата", "audit our AI setup", or when /rr-status says the project is behind.
argument-hint: [--survey light|full] | --update [--apply] | --audit [context]
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

`--update` and `--audit` go to their sections below; anything else
is **Setup**. In every mode: no application code changes — not a rename, not a
formatting fix. Problems you find are written down, never fixed. Never read
`.env`, secrets, dumps or production logs. Do not commit; suggest the `git add`.

## Setup

1. **Scaffold.** Both scripts are idempotent, never overwrite, and print what
   they created; note it. They take `--runtime auto|claude|codex|both` (`auto`
   follows `CLAUDE.md`/`.claude/` and `AGENTS.md`/`.codex/`); pass `both` when
   the repository is worked on from both runtimes.

   ```bash
   "$AI_HOME/hooks/project-scaffold.sh" "$PWD"       # docs/sdlc/, the runtime dir, .gitignore
   "$AI_HOME/skills/ai-init/scaffold-ai.sh" "$PWD"   # .ai/
   ```

   If `.ai/project/overview.md` was **not** created, the project was set up
   before: run **--update** below, then ask whether the survey should be
   refreshed; a refresh never overwrites a `.ai/project/` file a human edited
   without saying so first. If only an instruction file was created (no `.ai/`
   wanted), fill its Commands / Conventions / Architecture from the manifests —
   one line per command, five sentences of architecture — and stop.
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
3. **Survey.** `--survey light` is the default, for a developer who knows the
   project: ask for a ten-minute brain dump (entry points, modules that matter,
   integrations, unwritten business rules, areas nobody dares touch), confirm
   each claim with `grep -n`, then fan out exactly **two** `ai-discovery` agents
   in one message: (1) legacy, risks and code that looks unused; (2) tests,
   CI/CD, data and configuration — how secrets are supplied, never their
   values. `--survey full`, for a codebase new to you: one `Explore` for the
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
   `testing.md` only if step 1 created them. The **Verification** block of
   `testing.md` is the feedback loop every task runs:
   - `verify_command` — the fast suite to the end, the e2e group **excluded**;
   - `step_test_command` — the same runner on given paths (`{files}`);
   - `e2e_command` — the end-to-end suite, or `none` when there is none;
   - two or three lines of what healthy output looks like.

   `verify_command` comes from the human: show the one `$SETUP survey`
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
9. **Report.** Files created (a tree from the scaffold output), surprising
   findings, the modes and what puts a change in each, the safety restrictions
   in force (hooks versus policy), the tooling the workflows reuse, assumptions,
   unresolved questions and who can answer them, the survey's superpowers
   line as printed (the `enabledPlugins` line is the human's to add — never
   write it), and the suggested first task:
   `/rr-plan <it>`. Claim nothing was validated that was not run. Suggest
   `git add .ai .gitignore docs/sdlc` plus the instruction files created.

## --update

The script regenerates; you show it, confirm what is owed, and merge what it
cannot. It converts nothing: a project last updated by a riskrails before 3.1.0
is refused with the version that still converts it. Run it right after a new
riskrails is installed: until then the project's old shapes are not read.

1. `$STATE status`: with a task in flight, say that updating policies mid-task
   can change what the rest of it needs, and ask whether to finish it first.
2. `$UPDATE` — the dry run; show it as is. Up to date and no hint: say so, stop.
   A `regenerate` is a file that matches a version the plugin once shipped and is
   replaced; a `regenerate?` or `delete?` is a proposal for the human (step 4); a
   `create` is a file the project lacks. A project that still has the mixed
   `testing.md` and `weight.json` gets `verification.md` and `weight.project.json`
   split out of them once.
3. Lines marked `policy` change `.ai/policies/*.json`, which humans own: explain
   each in one plain sentence and ask, unless `$ARGUMENTS` holds `--apply`.
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
   `[sdlc]` — an unedited `docs/sdlc/*/TEMPLATE.md`, which the plugin
   now supplies (an edited one stays as the project's override); `[cleanup]` —
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
5. A `conflict` line: the project file was edited here and changed upstream.
   Markdown, or the managed block (inside the markers only): read both, keep
   everything project-specific, take the plugin's rules and structure, edit the
   project file, delete the copy. A JSON policy: show both values for each
   listed path and say which the plugin expects and why; the human edits it.
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
