# How agents work in this repository

One `.ai/` tree serves every runtime — same pipeline, same tiers, same scope rule
— and one task state under `state/`, so a task started in one runtime resumes in
the other. Read the non-negotiables below, then only the row for what you are doing.
Everything else loads on demand; nothing here is worth reading twice.

## Non-negotiable (read even if you read nothing else)

1. Production behaviour is the source of truth. Code that looks wrong may be
   load-bearing: document what you find, change only what the task asked for.
2. A change runs through `/rr-plan` and `/rr-build` (`using-riskrails.md`).
   The task names the files it may touch; an edit outside them is refused —
   answer `SCOPE_CHANGE_REQUIRED` and widen the task in place with
   `state.py start --amend --files "+<path>" --why "…"`, never around the guard.
3. No agent commits, pushes, merges or deploys. Approval is given by a human,
   outside the agent.
4. Verify before reporting done: the verification command once, to the end,
   every failure fixed as one batch, the output shown. Run it through
   `state.py verify --scope all` — it caps the runs, keeps the log out of the
   context, and a green exit code needs no agent to interpret it.
5. A refactoring changes no behaviour and is never mixed with a feature; legacy
   behaviour without a test gets a characterization test first.
6. Everything written into `project/` carries an evidence label — KNOWN FACT
   with `file:line`, INFERENCE with what it came from, UNKNOWN, RISK. An
   inference is never written as a fact.
7. `docs/sdlc/constitution.md` is this project's own list of principles. Cite
   them as `C<n>` in a spec, a plan or a review; say so in one line if it is
   absent, and carry on.

## Shared files

This `.ai/` holds `project/`, `rules/`, `state/`, `reports/`, `VERSION` and, in
`policies/`, `risk-tiers.json`, `risk-tiers.md`, `path-guard.json`, `testing.md`,
`coding.md`, `safety.md` and `security.md`. Every other path below ships with the
plugin at `<home>/riskrails/ai/<path>`; `<home>` is `~/.claude`, or
`$CODEX_HOME` (default `~/.codex`). A file at the same path here overrides it and
stops receiving its changes; `<home>/riskrails/ai-path <path>` prints the
copy that applies.

## Doing X → read Y

| Doing | Read |
|---|---|
| anything, first | `policies/safety.md` |
| which command when, the three modes | `using-riskrails.md` |
| starting or resuming a task | `state.py handoff --print`, then `/rr-build` (no task: `/rr-plan`) |
| the weight, the mode, who reviews, what a human approves | `policies/weight.json` (`policies/weight.md` mirrors it) |
| choosing an agent or a tier | `policies/model-routing.md` |
| writing code under `<dir>/` | `policies/coding.md`; `rules/<slug>.md` for that directory |
| tests | `policies/testing.md` — Verification: the three commands, run by `state.py verify` |
| finishing a step, verifying, recording a review, closing | `state.py step-done`, `verify`, `review`, `close` — the measurements are deterministic and the refusals name the way out |
| schema, data, migrations | `policies/database.md`, `policies/production.md` |
| auth, secrets, personal data, payments | `policies/security.md` |
| git, release | `policies/git.md`, `policies/release.md` |
| feature / bugfix / refactoring / hotfix / investigation | `workflows.md`, the section of that name |
| acting as a role | `agents/<role>.md` |
| an artefact | `templates/<artefact>.md` → `reports/<task-id>/` |
| understanding the system | `project/overview.md`, then `project/*.md` |
| principles, intent, spec, plan, decisions | `docs/sdlc/constitution.md`, `docs/sdlc/` |
| the project is behind the plugin | `/project-update` (`VERSION` is this tree's schema) |

## Keeping this directory true

`project/` describes the system as it was last surveyed. When you discover that it
is wrong, fix it in the same task — a knowledge base nobody trusts is worse than
none. Re-run `/ai-init` after a large change to refresh it.
