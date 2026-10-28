# Weight — how heavy a change is, measured

A task's mode (light, guarded, full) comes from its **weight**: six axes, 0 to 2
each, summed. The table is one file, `.ai/policies/weight.json`; the plugin ships
its default at `skills/ai-init/templates/.ai/policies/weight.json`, and a project
without its own reads that one. Beside the JSON sits `weight.md`, a generated
mirror carrying the JSON's `sha256:`. Never edit the mirror; edit the JSON and run
`state.py weight --mirror`. This page is the prose: why each rule is what it is.

```
state.py weight --files "a,b" [--goal "…"] [--declare axis=n:"evidence"]… [--json|--long]
```

Seven lines, one per axis plus the verdict. `--long` adds the evidence lists
(per-file reference counts, hints, replaced declarations), ≤ 20 lines. `--json`
gives the machine form. It needs no task and writes nothing. Since task 2.1 it
only prints; it decides nothing until the new `start`/`close` surface (task 2.2a)
records it.

```
scope          2  hooks/ai-path-guard.sh matches hot_paths hooks/**
behaviour      1  changes an existing path, limited (declared)
reversibility  0  git revert returns everything
domain         0  no money, identity or personal data (declared)
novelty        0  SH_RE family exists (declared)
coverage       0  1 of 1 code files have a test
W 3 → guarded   hints none · unknown none · light ≤2 · guarded 3–7 · full ≥8 or reversibility/domain=2
```

## The axes

| Axis | 0 | 1 | 2 | Measured by |
|---|---|---|---|---|
| scope | no references, leaf template | referenced from 1–5 files | > 5 files, or a `hot_paths` match | reference count of each declared file |
| behaviour | adds or presents | changes the output of an existing path, limited | changes a process: state machine, async, ordering, transaction | the session; keyword and new-file floors |
| reversibility | `git revert` returns everything | a step is needed (cache, config, deploy, sync) | data, schema, infra or an external write | `needs_step` / `irreversible` globs |
| domain | none | customer-visible, no money | money, tax, fiscal, identity/auth, personal data | `modules` / `customer_visible` globs, else the session |
| novelty | the pattern exists in the repo | adaptation | new mechanism, dependency or framework feature | the session; a manifest among the files → ≥ 1 |
| coverage | tests cover and bite | partial | none → characterization first (C2) | a test file named after each declared code file |

`W = Σ axes`. The modes, with the numbers read from `weight.json.modes`:
light ≤ 2, guarded 3–7, full ≥ 8, or reversibility = 2, or domain = 2. When
both reversibility and domain are 2, the mode is full_irreversible: three
human stops, and the confirmation names the operation.

**Why light ≤ 2 and not ≤ 3.** At ≤ 3, a regex fix in a hot guard script (scope 2 +
behaviour 1) and an ArgoCD `env/dev` manifest (reversibility 1 + scope 1 +
behaviour 1) would be light, and both analyses want them planned. At ≤ 2, every
case in the spec's SQ1 table lands where it should, and no other case moves.
`tests/test_weight.py::TestSQ1` scores all thirteen rows.

## What is measured, and what is declared

- **A measurement is a floor.** The session may raise any axis with
  `--declare axis=n:"evidence"`. A declaration below a measurement is replaced
  by the measurement, and `--long` says so. Scope is never declared alone. It
  is the only deterministic pre-diff proxy for blast radius, and an optimistic
  model is the risk this table exists to remove.
- **UNKNOWN scores 1** (`rules.unknown_scores`) and is listed on the verdict
  line. Behaviour, novelty and (outside the module globs) domain are the
  session's to declare. Left undeclared, each costs one point, so declaring is
  cheaper than not declaring.
- **Floors the session cannot go under.** A `behaviour.keywords` word in the goal,
  or in a declared file that exists, makes behaviour ≥ 1. A dependency manifest
  among the files makes novelty ≥ 1.
- **Zeros nobody needs to declare.** If every declared file is new, behaviour
  is 0: nothing existing changes. If every declared file matches
  `coverage.test_globs`, behaviour, domain and novelty are 0: a test-only
  change presents nothing to users.
- **Hints raise by one, once per axis** (`rules.hint_raises_by`,
  `hint_raises_once_per_axis`). A hint raises the measurement, and a declaration
  below it is replaced. So an auth-shaped path cannot be declared down to 0.

## Scope: references, not lines

At `/plan` there is no diff, so "changed symbols" do not exist yet. For each
declared file, `weight.py` counts the files that contain its identifier. The
identifier is the basename without extension, as a whole word, through `git grep
-lwI` (or a walk when there is no git). A template or config file (`.twig`,
`.yaml`, `.json`, …) is loaded by its path, so its repo-relative path is the
needle. The file itself and the test files are not counted. The bands are
`[0, 5]`: 0 refs → 0, 1–5 → 1, more → 2. A `hot_paths` match is 2 whatever the
count.

The limits are deliberate (FC-D1):

- **The grep budget.** Scope is measured on the first ten declared files, within
  five seconds for all of them. A file past either limit is UNKNOWN (1), never
  2.
- **A common word is not a reference.** If an identifier appears in more than a
  quarter of a tree of twenty files or more (`index`, `utils`, `state`), the
  count measures the word, not the file's callers. The file scores UNKNOWN (1).
- **A file called only through configuration under-counts.** Declare scope
  upward when you know its callers.
- **Scope is not re-scored after the work.** A raise there would only move light
  to guarded once the work is done. Re-scoring is upward only, and only on
  reversibility and domain, the two hard axes (`rules.rescore_axes`), from the
  real diff at `verify`/`close`. That lands with task 2.2a.

## Reversibility and domain

Both are measured from paths now. Re-scoring (2.2a) adds content: a diff hunk in
a `needs_step` file that matches `irreversible_content` raises reversibility to 2.
The shipped `irreversible_content` list is SQL-shaped (FC-D3). A repository
whose irreversible operations are file deletions in user trees adds its own
pattern (this one would add `delete(`). Otherwise such a migration is full,
not full_irreversible.

**Known edge.** Hints add to a measurement, so a template under `templates/**`
(customer-visible, domain 1) whose name is auth-shaped (`login*`, hint +1)
reaches domain 2, and therefore full. The spec's font-in-login case is light
because its template sits in a theme directory that `customer_visible` does
not list. A project whose login templates live under `templates/` and that
wants font changes there to be light narrows its `customer_visible` or its
hint paths. This is recorded for the 2.H policy reword.

## Modes and the old tiers (FC-B1)

Two statements, both true, for different purposes:

1. **Rules map by effect.** A change that the old table put at T4 *because of
   what it does* (it allows what was denied, or changes approval or install)
   scores behaviour 2, and lands in full by its weight, not by a label.
2. **The compat `tier_set` label is cost-equivalent**, for report continuity
   only: light → T2, guarded → T4, full → T5, full_irreversible → T6. It is
   journaled for one version beside the mode, so token reports across the
   change still compare. It never decides a gate.

## Batch — one task for a whole plan (sdlc-lite)

`/rr-build-all` runs a programme plan as one task (`docs/sdlc/specs/batch-build.md`). The
mode stays the weight's — a whole-plan task usually lands in full by its scope — and the
table gains one section the loop reads instead of the two budgets above:

```json
"batch": {"default": false, "review_rounds_max": 3, "max_suite_runs": 8, "parallel": 3, "tier": "BALANCED"}
```

- **`review_rounds_max` 3, not 2.** The standard two passes are one full review and one scoped
  re-review of one row's change. A batch task's fix batch spans many files and several
  subagents, so every pass is a full one, and the developer's rule — "after three failed
  reviews, a human" — is the fourth pass refused: `REVIEW_BUDGET`, exactly as today.
- **`max_suite_runs` 8.** One run after the last step, one after its fix batch, and up to two
  per review round for three rounds. Past it, `SUITE_BUDGET` is the human's run.
- **`parallel` 3, `tier` BALANCED.** Three or more agents at once never run above BALANCED
  (`model-routing.md`, "Fan-out"); the reviewer keeps the mode's tier.
- **`default` false.** A project turns the loop on for every task with it; `start --batch
  --by` turns it on for one task, `--no-batch` off. A table without the section runs with these
  numbers (`BATCH_DEFAULTS` in `state.py`); `/rr-setup --update` adds it.

What the loop does not change: the scope guard, the two facts, the e2e rule, the gate in full
mode, and "the mode only rises". `state.py batch off --by … --why …` returns a task to the
standard budgets, counting what it already spent; `batch on` during a task lowers the rigor
and is the human's, from their own terminal.

## Changing the table

Edit `.ai/policies/weight.json`, then run `state.py weight --mirror` and commit
both. `tests/test_weight.py::test_mirror_fresh` fails while the shipped mirror is
stale. Lowering a measured axis, or a mode, for one task is a human's act:
`--mode … --by <name>` (task 2.2a), journaled.
