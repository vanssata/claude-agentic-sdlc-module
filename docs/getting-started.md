# Getting started

The first hour: install, set up a project, a small task end to end, a
dangerous one, then the audit, the update and the bill.

## 1. Install

```bash
npx riskrails@3.0.1          # detects Claude Code, Codex or both; proposes the plan it detected; Enter confirms
```

Node 18+ and `python3` are needed. The installer writes the managed block into
`~/.claude/CLAUDE.md` (or `~/.codex/AGENTS.md`), the plan's settings, the five
agents with their tiers baked in, the hooks, the skills and the shared tree
under `<home>/riskrails/`, and prints what the block costs. Restart the
runtime. In Claude Code, `/skills` lists the `rr-*` skills and `/hooks` lists
`ai-guard.py`; in Codex, open `/hooks` and **trust the entries** — until you
do, nothing is enforced. Every option, every limit and the plugin route are in
[installation.md](installation.md).

## 2. Set up a project

```
/rr-setup
```

In a repository, `/rr-setup` scaffolds `docs/sdlc/` and `.ai/`, surveys the
code into `.ai/project/` — a light survey by default: it asks what you know,
confirms it with `grep` and sends two `ai-discovery` agents to the places
memory is least reliable, legacy and risks, tests and data; `--survey full`
sends six for a codebase new to you — and never touches application code. It
ends with three things only you can give it:

- the **Verification commands** in `.ai/policies/testing.md`:
  `verify_command` (the fast suite, no fail-fast), `step_test_command` (with
  `{files}`), `e2e_command` or `none`, which every later task runs before
  reporting done; the skill proposes them from the project's own configuration
  and writes them only after you say yes;
- the **weight table** in `.ai/policies/weight.json`: the money, identity and
  personal-data modules, the customer-visible paths, the hot paths, the
  directories that need a migration step, the irreversible ones — followed by
  `state.py weight --mirror`;
- the **constitution** in `docs/sdlc/constitution.md`: the principles the
  project does not negotiate, at most fifteen lines, cited as `C<n>` from then
  on.

The project's `CLAUDE.md` or `AGENTS.md` gets the managed block once; the rest
of the file stays yours. `.ai/policies/dialog.json` ships on, so approvals and
guarded git commands come to you as a question in the runtime's own dialog.
Commit `.ai/`, `docs/sdlc` and `.gitignore`.

A repository that already carries Spec Kit, Kiro, Cursor or Copilot files, or
an oversized instruction file, starts with `/rr-setup --adopt` instead
([project-update.md](project-update.md)).

## 3. A small task, end to end

```
/rr-build fix the typo in the checkout button label
```

1. No task is in flight, so `/rr-plan` runs first: it classifies the request
   (a bugfix), names the files, recalls what the record holds about them, and
   weighs them — six lines and a verdict:

   ```
   scope          0  1 reference
   behaviour      0  a label (declared)
   reversibility  0  git revert returns everything
   domain         1  templates/** is customer-visible
   novelty        0  nothing new (declared)
   coverage       1  no test names the file
   W 2 → light
   ```

2. **Light**: the plan is inline — the file, the test, the rollback in a few
   lines — and `state.py start` registers the task and arms the scope guard.
   Nobody stops.
3. The session edits. A write to any other file is refused with
   `SCOPE_CHANGE_REQUIRED`; the answer is `start --amend --files "+<path>"
   --why "…"`, journaled.
4. `state.py verify --scope all` runs `verify_command` once, to the end, with
   the log under `.ai/state/logs/`; a light task runs no e2e.
5. `/rr-ship` → `state.py close` measures the two facts — the suite is green on
   this tree, every changed file is inside the task — and closes without a
   review. It writes the commit message body from `task.md` and suggests the
   commit, which is yours: with the dialog on, the `git commit` you pick runs
   once, verbatim.

Three `state.py` calls, no agent, no gate. `/rr-status` at any point shows
where it stands in twenty lines.

## 4. A dangerous task, end to end

```
/rr-build add a 3% surcharge to card payments
```

1. `/rr-plan` weighs it: `src/Payment/**` is in the project's `domain.modules`,
   so domain is 2 — **full**, whatever the sum. It asks every question the
   plan depends on now, in the conversation or on record, writes the plan —
   steps, files, tests, what stays the same, risks, rollback — and, when the
   design is open, sends `architect` on STRONG for it. You read the plan and
   accept it before `start`.
2. `/rr-build` works step by step inside the plan: each step's own tests
   (`verify --scope step`), `step-done` measures what the step changed, then
   the suite once and e2e once, every failure fixed as one batch. `verify`
   re-scores reversibility and domain from the real diff; the mode can only
   rise.
3. `/rr-review` sends one `ai-reviewer` on STRONG with `focus: security`,
   bounded to about eighty tool calls. BLOCKER and HIGH findings in scope are
   fixed as one batch and closed by a green verify or one scoped re-review;
   MEDIUM and LOW go into the record.
4. `/rr-ship` → `close` records the gate and stops: the facts, and the way to
   approve. In the dialog you pick the approval; `close` runs again and
   archives the task. A tree that changed after the approval invalidates it.
5. The commit is yours. Nothing merged, nothing deployed.

A migration that drops a column, or a production manifest, is
`full_irreversible`: the approval is `state.py approve --confirm <operation>`
in your own terminal, never the dialog.

## 5. A whole plan as one task

```
/rr-spec checkout-redesign                     # brainstorm on record, spec with Flagged concerns
/rr-plan docs/sdlc/specs/checkout-redesign.md  # the programme plan: rows with files, tests, dependencies
/rr-build-all docs/sdlc/plans/checkout-redesign.md
```

Every row becomes a step; the ready ones go to parallel implementers on
BALANCED, the suite runs once, parallel fixers take the failures as one batch,
one review at the mode's tier, its findings fixed, then tests and the review
again until it passes. After three failed review passes the next verdict is
yours.

## 6. Audit what you already have

```
/rr-setup --audit
```

Scores the repository against the twelve plays of the AI-native SDLC and
writes `docs/ai-sdlc-adoption-plan.md` — what is in place, what is missing,
in which order to add it. It writes nothing else.

## 7. After the plugin changes

```bash
npx -y riskrails@latest --yes   # the home: settings, hooks, agents, the shared tree
```

```
/rr-setup --update              # the project: a dry run, then --apply; migrations first, then the merge
```

`/rr-status` says when a project is behind the installed plugin. In Codex,
re-trust the changed hook entries in `/hooks`.

## 8. See what it cost

```
/rr-status --cost
```

Reads the local transcripts of both runtimes — never the API — and shows
tokens and cost per task, session, model and tier, with the plan's per-task
figure beside it for comparison. Zero model cost.

## Where to go next

- [weight.md](weight.md) — the six axes, the three modes, tuning the table
- [workflows.md](workflows.md) — feature, bugfix, refactoring, hotfix, investigation
- [hooks.md](hooks.md) — every rule the guards enforce
- [routing.md](routing.md) — the tiers per plan and runtime
- [faq.md](faq.md) — why something was blocked, and how to change it
