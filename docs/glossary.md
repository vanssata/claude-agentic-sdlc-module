# Glossary

The words a person meets in the dialog, the statusline and `/rr-status`.

**Decision.** Something only you may settle: the approval at close, a budget
refusal, a guarded `git commit` or `git push`, starting a task in a higher
mode, `batch on`, the install. It has an id (`D3`) and comes to you as a
question in the runtime's own dialog.

**Dialog.** The question box the runtime shows (`AskUserQuestion` in Claude
Code). It is on by default and off with `"enabled": false` in
`.ai/policies/dialog.json`; off, every decision is a command you run in your
own terminal ([hooks.md](hooks.md), the dialog gate).

**Pick.** Your answer in the dialog. If it is a command, a hook records it in
the consent ledger and the agent then runs that command, verbatim, once. A
command that is not your pick is refused (`CONSENT_REQUIRED`).

**Consent ledger.** `.ai/state/consent.jsonl`: one line per offer, pick, use
and settle. It is how the gate knows a command was picked by you and has not
been used yet.

**Gate.** Two things share the word. The *approval gate* (`G1`) is the
human's approval of a full-mode task at close. The *decision gate* holds every
tool while a decision is open ("waiting on you", below).

**Mode.** How much process a task gets: `light` (inline plan, no review unless
a fact is red), `guarded` (a plan you accept, one review) or `full` (a written
plan, a STRONG review, and your approval of the tree). `full_irreversible` is
full plus a typed confirmation. See [weight.md](weight.md).

**Weight.** The score `state.py weight` computes from six axes (scope,
behaviour, reversibility, domain, novelty, coverage); the sum picks the mode.
A mode never drops during a task.

**Step.** One row of a task's plan: the files it may touch and the tests that
prove it. An edit outside the step's files is refused (`SCOPE_CHANGE_REQUIRED`).

**Batch.** `/rr-build-all`: every row of a programme plan run as the steps of
one task. `state.py batch on --by <you>` switches it on and is a decision you
can pick in the dialog.

**Budget.** What a task may spend before a human decides. Suite runs: how many
times `verify` may run the whole suite (`SUITE_BUDGET`). Review passes: how
many reviews may fail before the next verdict is yours (`REVIEW_BUDGET`). Past
either, a decision asks whether to go on.

**Verify.** `state.py verify`: runs the project's verification command and
records the result. Close needs a green one on the tree as it is.

**Review.** One adversarial read of the change by a fresh agent, at the tier
the mode sets; it returns findings and a verdict.

**Approve.** `state.py approve`: your sign-off of a full-mode task, after
reading the tree. An agent cannot do it; you give it as a pick in the dialog
or in your own terminal.

**Waiting on you.** The task, or a pending decision, needs your answer. While
a decision is open the guard denies every tool except the dialog, the picked
command and `state.py decision show|settle|fallback`. The statusline shows
`waiting on you: D3 Q2 G1` (decisions, questions, the gate) and `/rr-status`
opens with a line that says what.

## What still needs a terminal

Not everything has a dialog route. These stay in your own terminal:

- every `state.py memory` verb except `enable` (`disable`, `cleanup`, `pack`,
  `redact`);
- `update.py --confirm-delete`, which deletes files and is confirmed by a
  typed name;
- approving a `full_irreversible` task, `state.py approve --confirm <operation>`.

An irreversible deletion keeps the terminal; a reversible lowering of rigor may
be picked.
