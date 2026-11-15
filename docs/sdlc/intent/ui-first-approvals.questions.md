# Questions — ui-first-approvals
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Scope for one build cycle: which proposals of the 2026-11-15 UI analysis go in?
asked: 2026-11-15T11:25:39Z · stage: intent
A. the dialog-first texts and fallbacks (2), picker-first questions (6), statusline task line (7), status first line (8), plain-language dialog texts + glossary (9), update via dialog (10), docs gaps (12), installer I1-I6, and the remaining human verbs in the dialog (4) (recommended)
B. only behaviour 0-1 items, no new dialog labels
C. everything including full_irreversible in the dialog (5) and the one-reader switch (3)
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q2. full_irreversible --confirm and the single reader of the dialog switch: in this spec?
asked: 2026-11-15T11:25:40Z · stage: intent
A. no - both stay as they are, listed as follow-ups; full_irreversible keeps the terminal on purpose (recommended)
B. yes, both
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q3. Installer wizard technique
asked: 2026-11-15T11:25:40Z · stage: intent
A. zero-dependency ANSI on the existing Node menu child (bin/menu.js), colour gated by isTTY, NO_COLOR and TERM=dumb; non-TTY output byte-identical (recommended)
B. an npm prompt library
C. a Python curses installer
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q4. Where does the per-task knowledge file (where problems appeared and where not) live?
asked: 2026-11-15T11:25:40Z · stage: intent
A. docs/sdlc/specs/ui-first-approvals.lessons.md, beside the spec, one row per step, in the task's files (recommended)
B. .ai/reports/<task-id>/lessons.md
C. the journal only
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q5. How is the release version raised?
asked: 2026-11-15T11:25:40Z · stage: intent
A. 4.3.0 (minor), as the last step on this same branch feat/ui-first-approvals: tools/sync-version.py 4.3.0 plus the CHANGELOG section, so merging the one PR to main auto-releases (recommended)
B. a separate chore/release-4.3.0 PR after the feature PR merges
C. 5.0.0
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q6. The live Remote Control / desktop / web probe of the dialog needs a human: does it block the build?
asked: 2026-11-15T11:25:40Z · stage: intent
A. no - the spec ships a probe checklist and a recorded-payload doc for the human to fill after the release; the design must not depend on its result (recommended)
B. yes, probe first
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q7. Who builds, who reads logs, who decides?
asked: 2026-11-15T11:25:40Z · stage: intent
A. /rr-build-all in one cycle: implementer and fixer subagents on sonnet in parallel where the import graph allows, log-reader on haiku for every suite and CI log, the session model decides the plan, the conflicts and every fix-or-defer; one review at the mode's tier (recommended)
B. the session implements
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:25:40Z

## Q8. After the architect's design: the binding .ai/policies/safety.md:30-33 says the memory verbs have no dialog route, and --confirm-delete's typed name is the audit trail (hooks/guard/paths_base.py:16-21) - the same argument that keeps full_irreversible on the terminal (Q2). What does item (4) of Q1 carry?
asked: 2026-11-15T11:46:26Z · stage: intent
A. only 'batch on --by' (reversible, lowers rigor); the npx pick is spent and the install decision is added for (10); memory disable/cleanup/pack/redact/move-logs and update.py --confirm-delete stay terminal-only and become a follow-up spec with the policy change, after the Remote Control probe (recommended)
B. all of them, with a human edit of safety.md before the review
C. batch on and memory disable
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:46:27Z

## Q9. Uninstall (I5) and the wizard wiring are the largest installer steps: what if their wave is red after one fixer batch?
asked: 2026-11-15T11:46:26Z · stage: intent
A. both stay in scope; if the uninstall step is still red after one fixer batch the session defers it (the flag is not registered, its planner and tests stay), records it in the lessons file and the CHANGELOG, and the cycle goes on (recommended)
B. uninstall out of scope from the start
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-11-15T11:46:27Z
