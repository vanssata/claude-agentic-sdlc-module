# Questions — parallel-light-workers
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Workers choice (intent/plan, implement, deep research): how often is it asked?
asked: 2026-11-26T12:53:03Z · stage: intent
A. At each stage, every time — one question per stage, no memory (recommended)
B. Once per task at the first stage; the pick carries to later stages, changeable
C. A project default in settings, asked only when unset
X. Other — answer as `X: <text>`
[Answer]: X: Combination: project default workers/research = ask|on|off (shipped ask); when ask, one question at the task's first stage (workers whole task / current model whole task / ask every stage / workers + save as project default), pick stored in task state; later stages ask again only under 'ask every stage', else print one line with how to change it. Deep research: same layers, but under ask it is asked at every stage. — by ikakarov via picker at 2026-11-26T12:56:49Z

## Q2. Implementation with workers: where do workers write code?
asked: 2026-11-26T12:56:49Z · stage: intent
A. Same tree, only steps with disjoint files run in parallel; the main model integrates and decides (recommended)
B. Each worker in its own git worktree; the main model merges the results
C. Workers only draft patches/diffs; the main model applies every edit
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via picker at 2026-11-26T12:57:40Z

## Q3. Review budget spent: what does 'continue without a limit' do?
asked: 2026-11-26T12:57:40Z · stage: intent
A. A new option in the existing REVIEW_BUDGET dialog: lift the cap for this task only; every further verdict is still a normal reviewer verdict; recorded in the journal (recommended)
B. Same, but it adds N more passes (e.g. +3) instead of removing the cap
C. A project setting review_rounds_max = unlimited
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via picker at 2026-11-26T12:58:32Z

## Q4. Simplify before close: what runs and what after?
asked: 2026-11-26T12:58:32Z · stage: intent
A. Ask before close (Simplify / Skip); Claude runs the /simplify skill, Codex the same pass via a BALANCED code-simplifier prompt; edits stay inside task files; then verify reruns before close (recommended)
B. Simplify only reports suggestions; the human picks which to apply
C. Only in guarded/full mode, never in light
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via picker at 2026-11-26T12:59:46Z

## Q5. Native plan mode (Claude EnterPlanMode/ExitPlanMode, Codex /plan): where is it the base?
asked: 2026-11-26T12:59:51Z · stage: intent
A. Plan in guarded and full (full: the written plan file is drafted inside plan mode, approved via ExitPlanMode); intent/spec brainstorm also inside plan mode (read-only); light stays inline (recommended)
B. Every mode including light
C. Plan only; intent/spec stay as today
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via picker at 2026-11-26T13:00:50Z

## Q6. How many parallel workers at most?
asked: 2026-11-26T13:00:50Z · stage: intent
A. Set by the plan profile (e.g. max20: 6, max: 4, pro: 2; Codex profiles their own), overridable in project settings (recommended)
B. A fixed cap of 4 everywhere
C. No cap; the main model decides
X. Other — answer as `X: <text>`
[Answer]: X: Cap from the plan profile, overridable in project settings; Max and Ultra get double the option-A values: Claude pro 2, max 8, ultra 12; Codex plus 2, pro-100 8, pro-200 and pro-500 12. Also rename the plan profiles to the current plan names of Claude (Pro, Max = former Max 5x, Ultra = former Max 20x) and Codex (Free/Go, Plus, Pro 100/200/500, Business) and refresh the Codex model ids. — by ikakarov via picker at 2026-11-26T13:04:31Z
