---
name: rr-review
description: One adversarial review of the task's change, at the tier its mode sets — BALANCED in guarded, STRONG in full, security-focused when the domain axis is 2, and in light only when close reports a red fact. A fresh ai-reviewer reads the diff with bounded inputs, returns FINDINGS and a VERDICT, and state.py records them; in-scope BLOCKER and HIGH findings are fixed as one batch, closed by a green verify or one scoped re-review. The pass past the budget is the human's. Use on "/rr-review", "review this", after /rr-build in guarded or full mode, or when close says a review is required.
argument-hint: [B1,H1 … — a scoped re-review of these findings]
---

# /rr-review $ARGUMENTS

One reviewer, one pass, on a context that did not write the code. Resolve the
install root once:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/skills/rr-review" ] && break
done
STATE="python3 $AI_HOME/skills/ai-task/state.py"
```

## 1. Which review

`$STATE status` gives the mode, the axes and the review so far.

| Mode | Review | Tier |
|---|---|---|
| light | only when `close` exits 2 with `review required` (a red fact) | BALANCED |
| guarded | one | BALANCED |
| full, full_irreversible | one; briefed with the security focus when the domain axis is 2 | STRONG |

`review` refuses a tier below the mode's. Two passes per task are the budget
(`review_rounds_max`): one full review and one scoped re-review. The pass past
it exits 6 `REVIEW_BUDGET` — the next verdict is the human's, from their own
terminal, with the command it prints, or the pick in the dialog (`DIALOG_PENDING`,
then the picked command verbatim, once). Never a third pass.

## 2. Brief one `ai-reviewer`

Spawn exactly one `ai-reviewer` at the tier above — under Claude Code with
`model: $($STATE profile --tier <TIER>)`; under Codex its agent file's model is
the tier, so name the tier in the brief. Give it paths, not pasted text:

- the goal, the mode and the workflow (`$STATE status`);
- the change: `git diff` against the task's base plus new files
  (`git status --short`), and the task's files from `.ai/reports/<task-id>/task.md`;
- the tests the task named, and the last `verify` result and log path;
- in full mode with domain 2: the security focus — authentication,
  authorisation, secrets, personal and payment data, input validation,
  injection — and record the pass with `--focus security`.

**Bounded inputs in light and guarded:** the goal, the diff, the named tests,
and the project's own threat model (`.ai/policies/safety.md`, the guards'
defaults, the test fixtures). A finding that needs anything outside them comes
back `[INFO]` with `in_scope: no`; write it into `.ai/project/known-risks.md`
as one entry — it never opens a fix. You may move a finding to
`in_scope: yes`, never the other way. **In full mode** the reviewer's own "look
for" list applies unbounded.

Before you delegate, probe the change yourself for a minute: the few inputs its
own threat model makes interesting, through the real code, and hand the
reviewer what you saw — it starts where you stopped.

## 3. Record the verdict

The reviewer returns `## FINDINGS` (`- [BLOCKER] B1 …`, `[HIGH] H1`, `[MEDIUM]`,
`[LOW]`, `[INFO]`, each with `in_scope: yes|no`) and `## VERDICT`
(`verdict: pass | pass_with_findings | blockers_open`). Pass both through
verbatim:

```bash
$STATE review --verdict <verdict> --tier <BALANCED|STRONG> [--focus security] --report - <<'EOF'
<the reviewer's FINDINGS and VERDICT, unchanged>
EOF
```

`review` checks the verdict against the findings: an in-scope BLOCKER is
`blockers_open`, an in-scope HIGH is not a `pass`. It keeps the text in the
task's record (`task.md`), so there is no separate report to write.

## 4. After the verdict

- **pass:** `/rr-ship`.
- **pass_with_findings:** fix every in-scope HIGH (and the MEDIUMs worth it) in
  one batch, then
  `$STATE verify --scope all --after-fix "H1,H2: <one line>"` and
  `$STATE review --closes "H1,H2"`. The findings close on that green run, on a
  tree the fix changed — no second review.
- **blockers_open:** fix every BLOCKER and HIGH together, `verify --scope all
  --after-fix "…"`, then **one scoped re-review** (`/rr-review B1,H1`): brief a fresh `ai-reviewer`
  with the named findings and the fix's diff only — do they close, and what did
  the fix introduce — and record it as above. Never one finding, one fix, one
  re-review at a time.

The `verify` after a fix is often the task's third whole-suite run: past
`tests.max_suite_runs` it exits 6 `SUITE_BUDGET`, and that run is the human's,
from their own terminal, with the command it prints, or the pick in the dialog.

A finding whose cause is the plan goes back to `/rr-plan` for that part only. A
real problem outside the task goes into `.ai/project/known-risks.md`. A mistake
this repository has seen before — the second time a review flags it — gets one
line in the project instruction file, in this task.
