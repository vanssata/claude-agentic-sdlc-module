# Lessons of the task `ui-first-approvals`

Where problems appeared and where none did, one row per step, written as the
work goes — so the base workflow can be improved afterwards. "none" is a finding.

Task: not started · mode: full (planned) · branch: `feat/ui-first-approvals` · started: 2026-11-15

| step | files | agent / model | first try green | problems (error text, at most two lines) | what fixed it | review findings | tokens | what the base behaviour should change |
|---|---|---|---|---|---|---|---|---|
| analysis | read-only | 5 × Explore / haiku | yes | the skills reader reported "no statusline integration" because it searched `skills/` only, while the hooks reader found it in `hooks/runtime-gate.py`; no claim was wrong in the session's spot checks | – | – | 173k, 41 s wall | parallel haiku discovery with a `file:line` brief is enough for a survey; keep it |
| spec: questions | `docs/sdlc/intent/ui-first-approvals.questions.md` | session | yes | `state.py answer` recorded the model's own choices as "by vanssa via prose" | noted in the spec's Decisions taken and concern 1 | – | – | `answer` needs a `via` for a delegated self-answer (`ROADMAP.md:39-42`) |
| spec: questions | same | session | yes | `ask` reprints every earlier question on each call: seven asks printed 28 question blocks | – | – | about 6k of output | `ask` on a topic should print only the question it added, or take `--quiet` |
| spec: design | read-only | architect / opus | yes | found a binding policy (`safety.md:30-33`) against a decision taken before the design; scope narrowed (Q8) | the session decided, recorded as Q8 | – | 303k, 19 min | read the binding policies before the scope question, not after |
