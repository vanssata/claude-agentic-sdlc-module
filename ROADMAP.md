# Roadmap

What RiskRails 3.0 ships is in [README.md](README.md). This file holds what is
decided but not built, what is open from the programmes that shipped, and what
is deliberately not planned. Dates are absolute; the record behind each row is
named so it can be checked.

Status: 2026-10-30, after the redesign (`docs/sdlc/plans/claude-agentic-redesign.md`,
every row closed on 2026-10-29), the dialog gate, batch build, compact project
memory and the faster task cycle.

## 1. Agentic SDLC modes — the unfulfilled intent

**The idea.** The SDLC skills (`/rr-spec`, `/rr-plan`, `/rr-build`,
`/rr-build-all`, `/rr-review`, `/rr-ship`) run in one of three operating modes,
chosen per specification. The weight-based risk gates — the mode light / guarded
/ full, the scope guard, the two facts at close, the approval gate — stay
mandatory in every one of them; what changes is **who answers the questions a
task raises**:

| Operating mode | Who decides |
|---|---|
| **AI** | the agent chooses and records every decision inside the allowed scope |
| **Hybrid** | the agent accepts and records its own justified proposals (the `--recommend` option of a question); it asks the human only when it has no proposal to accept |
| **Manual** | the process as it is today: a human answers every question and gives every confirmation |

**What is on record.** One question, asked on 2026-10-29 at the intent stage
and answered by the developer the same evening:
`docs/sdlc/intent/agentic-sdlc-modes.questions.md` — Q1 "which mode for this
specification", answer **B, Hybrid**. Nothing else exists: no
`docs/sdlc/intent/agentic-sdlc-modes.md`, no spec, no plan. A root file
`NextIntent.md` that pointed `/rr-build-all` at
`docs/sdlc/specs/agentic-sdlc-modes.md` was committed in `0142ec7` and removed
in `d80246c` the same day; the spec it named was never written.

**What it has to settle** (the spec's open questions, from the three nevers in
`ai/using-riskrails.md` and constitution C5):

- Where the operating mode lives: a key in `.ai/policies/` (per project), a
  `start` flag (per task), or both — and whether the dialog switch
  (`.ai/policies/dialog.json`) is the same switch or a second one.
- Which questions a Hybrid run may answer itself. A question carries
  `--recommend`; a self-answer needs its own `via` in the journal
  (`question_answered` today records `picker` or `prose`) so a human can tell
  afterwards what was decided without them.
- What stays human in every mode: approval of a full-mode tree, lowering a
  mode, running past `SUITE_BUDGET` or `REVIEW_BUDGET`, `--confirm-delete`,
  `memory pack`, `memory cleanup`. The AI mode cannot be a way around any of
  them.
- What `/rr-build-all` does with a pending question in AI and Hybrid mode: the
  loop today stops the task until a human answers.
- Weight: a change that moves who answers a question is behaviour 2 for a user
  project (C6), so the task runs in full mode with a STRONG review.

**How to pick it up.**

```bash
/rr-spec agentic-sdlc-modes            # intent + spec; the Q1 answer is already recorded
/rr-plan docs/sdlc/specs/agentic-sdlc-modes.md
/rr-build-all docs/sdlc/plans/agentic-sdlc-modes.md   # or /rr-build, row by row
```

## 2. Open rows from shipped programmes

Rows a human owns, or small tasks a review left behind. Each names its record.

| Row | Owner | What | Record |
|---|---|---|---|
| Memory G4 | human | after ten real closes in packages mode: `state.py memory verify --all` and `--fresh-clone` both exit 0, then `cleanup: true` in `.ai/policies/memory.json` and `memory cleanup --all --confirm-delete <author>` | `docs/sdlc/plans/compact-project-memory.md`, G4 |
| Memory M1, M9 | task (bugfix) | `memory_compact.py` loses or mis-attributes a journal line over 4 KB (`{"truncated": true}`); `export` skips the repair of a sealed key with a missing entry | `.ai/reports/T-2026-10-28-011/task.md`, review pass 2 |
| Dialog OQs | spec | an API-key account: its own `profiles/api.json` or `unsupported`; plan drift is per user while the dialog switch is per project; `window_seconds` 120 against pre-commit hooks that run before the push | `docs/sdlc/specs/command-choice-dialog.md`, §Open questions |
| `--adopt` by hand | human | `/rr-setup --adopt` on a real Spec Kit or Cursor project, and a `--cleanup` run in a real terminal; the suites use fixtures | README, Known risks |
| Shared policy texts | task (docs) | `ai/policies/model-routing.md` and `ai/policies/review-economy.md` still describe tiers T0–T6, `pipeline_profile` and `risk-tiers.json`; the project files were rewritten by the redesign, the shared ones were not | this file, 2026-10-30 |
| Routing hooks under the path guard | task | `runtime-gate.py` and `context-guard.py` are not protected by name the way the three guards' configuration is | README, Known risks; WP5 OQ3 |

## 3. Open risks in the record

Sixty-three risks are open in the project record on 2026-10-30; `state.py
memory risks` lists them, `state.py recall --files <paths>` shows the ones that
touch the files of a task. The ones that shape the next work:

- `state.py` still reads the task state in several places through a
  `state.json` / `current.json` fallback (migration 0009 moved the file; the
  copies are listed as a C1 risk, not fixed).
- The hooks' dialog switch and `state.py`'s can disagree on Codex and across
  sessions; with the dialog off there is no route to "Keep".
- A task glob beside documents weighs light at `start`; the documents rule
  ignores a red full-suite run after the green one when the tree is unknown.
- The Claude EXPERT tier collapses to STRONG without Fable (`--fable no`).
- `test_gate_fast_path` is red under the parallel runner's default job count;
  `verify_command` runs it serially for that reason.
- The suite is red on Python 3.10, so CI starts at 3.11.

## 4. Not planned

- **A LOCAL model tier.** Neither runtime has a local-model backend; the work
  it would do is done by deterministic tools and `Explore` on the FAST tier.
  Nothing depends on one existing.
- **A sandbox.** The guards are regex hooks over tool calls — a tripwire for
  the honest mistake, not a security boundary. The backstops stay server-side
  branch protection, secrets off the developer machine and human review.
- **An agent that approves.** Approval, a lower mode, a run past a budget and
  a confirmed deletion are a human's, from their own terminal or as the command
  they picked in the dialog. No operating mode in §1 changes that.
- **The old command names past one version.** `/ai-task`, `/ai-init`,
  `/ai-status`, `/ai-audit`, `/project-init`, `/project-update`,
  `/sdlc-intent`, `/sdlc-spec`, `/sdlc-plan` and `/usage-report` are aliases of
  the `/rr-*` skills in 3.x and go away in the next major version, together
  with the `<home>/claude-agentic` symlink and the `current.json` fallback.
