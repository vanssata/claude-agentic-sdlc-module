# Questions — T-2026-10-13-004
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. History blobs are the merge base for three_way (update.py:574) and block_update (update.py:652). Files still merged in a project after this task: risk-tiers.json, risk-tiers.md, path-guard.json, testing.md, coding.md, the managed instruction block, docs/sdlc/*/TEMPLATE.md. What replaces the removed blobs?
asked: 2026-10-13T16:13:39Z · stage: impact_analysis
context: skills/project-update/update.py:58,152,574,652,858,902,922; history/ = index.json + 198 blobs, 1.1 MB
A. Keep history/index.json (sha256 of every shipped version, all keys — 0006 needs them for the identical-to-shipped check) and keep blobs only for the files that are still merged; drop the blobs of the shared files that leave the project. Three-way merge keeps working where users edit. (recommended)
B. Remove every blob; keep index.json hashes only. Still-merged files become create-only: an unedited copy (hash matches) is replaced, an edited one is left and the new template is written beside it as <file>.new for the user to merge.
C. Remove history/ entirely; 0006 compares only against the current template, so copies edited by any older plugin version are kept as overrides instead of deleted.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T16:15:39Z

## Q2. The global and project instruction blocks say 'read .ai/AGENTS.md first'. Where does the .ai/AGENTS.md router live after the move?
asked: 2026-10-13T16:13:39Z · stage: impact_analysis
context: instructions/stub.md, templates/.ai/AGENTS.md, test-instruction-budget.sh router checks
A. It stays in the project (project-owned, merged like the other kept files) and is rewritten as a short router: project files in .ai/, shared files at the plugin path, a project copy of a shared file overrides it. The block text is unchanged. (recommended)
B. It moves to the plugin; the block points at the plugin path, and .ai/ in the project holds only project-owned files.
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-13T16:15:39Z

## Q3. How do skills and subagents find a shared file (e.g. policies/safety.md) once it lives in the plugin?
asked: 2026-10-13T16:13:39Z · stage: impact_analysis
context: agents/*.tmpl Read-first lines; skills/*/SKILL.md; discovery-A §3
A. install.sh writes the shared tree to <home>/claude-agentic/ai/ and renders that absolute path into agents/*.md and routing.md; skills use the existing $AI_HOME resolution. One prose rule everywhere: read .ai/<path> when the project has it, else <plugin>/ai/<path>.
B. As A, plus a small resolver script (ai-path <rel> prints the effective path, project override first) that skills, agents and tests call, so the override rule lives in code and is testable. (recommended)
X. Other — answer as `X: <text>`
[Answer]: B — by ikakarov via prose at 2026-10-13T16:15:39Z

## Q4. OQ1 (plan): should Step 3 add (^|/)\.(claude|codex)/claude-agentic/(ai/|ai-path$) to task_protected_patterns in hooks/ai-path-guard-defaults.json? Guard code and deny texts stay unchanged; only guard data changes.
asked: 2026-10-13T16:35:52Z · stage: plan
context: .ai/reports/T-2026-10-13-004/implementation-plan.md (Open questions)
A. Add it — the shared policies leave the project's frozen .ai/policies, so the installed tree gets the same protection (recommended)
B. Leave guards untouched; record the unguarded installed tree as known-risk (c)
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-14T07:10:18Z

## Q5. OQ3 (plan review H2): Gemini/Junie instruction stub (instructions/stub.md:46, frozen) says 'follow .ai/policies/safety.md'; 0006 would delete it. What happens to those runtimes?
asked: 2026-10-14T07:26:55Z · stage: plan
context: .ai/reports/T-2026-10-13-004/plan-review.md (H2)
A. 0006 keeps .ai/policies/safety.md and security.md in the project (not deleted) (recommended)
B. Unfreeze the stub and point it at the shared tree
C. Delete them and record the risk in known-risks.md
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-14T07:28:06Z

## Q6. install.sh --target both writes the Codex routing.md into ~/.claude (install.sh:423,:932,:730; live on this machine). Step 3 renders the shared path into that file. How to handle it?
asked: 2026-10-14T07:26:55Z · stage: plan
context: .ai/reports/T-2026-10-13-004/plan-review.md (H3)
A. Separate bugfix task first, this task waits for it (recommended)
B. Keep the shared path out of routing.md in this task
C. Widen Step 3 to fix install.sh here
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via prose at 2026-10-14T07:28:06Z

## G1. Approve T-2026-10-13-004 for implementation? (gate: human_approval)
asked: 2026-10-14T08:09:30Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via terminal at 2026-10-14T08:10:32Z

## Q7. Remediation R1 scope: which review/security findings are fixed in this task (one batch), the rest going to known-risks?
asked: 2026-10-14T13:09:13Z · stage: implementation
context: .ai/reports/T-2026-10-13-004/review-report.md, security-report.md; files: skills/ai-init/SKILL.md, skills/project-update/{update.py,SKILL.md,migrations/0006_shared_files.py}, README.md, .ai/project/known-risks.md, tests/test-migration-0006.sh
A. BLOCKER (ai-init SKILL.md: project specifics go to a deliberate .ai/ override, never the shared tree) + security MEDIUM (shared_update/require_shared limited to the 29) + rollback text MEDIUM + doc LOWs (c),(e),(m); router-conflict MEDIUM, CRLF LOW, apply-time symlink LOW to known-risks
B. A plus the router-conflict MEDIUM (three_way no-op when ours already has the section once; R4 + appended-non-negotiable fixtures) and the CRLF anchor LOW (recommended)
C. BLOCKER only; everything else to known-risks
X. Other — answer as `X: <text>`
[Answer]: B — by ikakarov via prose at 2026-10-14T13:19:04Z

## G2. Approve T-2026-10-13-004 for implementation? (gate: human_approval)
asked: 2026-10-14T13:50:02Z · stage: human_approval
A. Approve
B. Reject — answer as `B: <reason>`
X. Other — answer as `X: <text>`
[Answer]: A — by ikakarov via terminal at 2026-10-14T13:54:47Z
