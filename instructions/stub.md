<!-- stub: scope=doc runtime=none -->
<!-- The one source of every always-loaded instruction stub, for every scope and every
     runtime. install.sh and render_instructions.py render it into the managed block of a
     global or project instruction file, and `build` regenerates the committed templates
     from it. Nothing else may carry this prose.
     A directive line is an HTML comment whose first word is `stub:`, carrying
     `scope=global,project` and `runtime=claude,codex`. It covers the lines that follow it
     until the next directive line or a blank line; a group with no directive is selected
     for every scope and every runtime, and this group's scope=doc matches no request.
     scope   = global | project | skeleton | skeleton-sdlc
     runtime = claude | codex | gemini | junie | *
     {{X}} resolves from instructions/runtimes.json first, then from RENDER_X.
     Every line here is read on every turn of every session: it is paid for per token,
     per turn. Anything that is not needed to work safely belongs in routing.md, in a
     project policy, or nowhere. -->

<!-- stub: scope=global runtime=claude,codex -->
# claude-agentic ({{PLAN_LABEL}} plan)

<!-- stub: scope=global runtime=claude,codex -->
Rules for every repository; everything else loads on demand. `{{HOME}}/claude-agentic/routing.md` has the model ladder, the context-guard thresholds and the launcher; a project's `.ai/AGENTS.md` routes to its policies.

<!-- stub: scope=global runtime=claude,codex -->
- With `.ai/`: read `.ai/AGENTS.md` first, run every change through `/ai-task <request>`, treat `.ai/policies/` as binding; `/project-update` after a plugin reinstall. Without `.ai/`: `/ai-init` first.
- Production behaviour is the source of truth: document problems outside the task, do not fix them. Never mix a refactoring with a feature change.
- Each step names the files it may touch; an edit outside them is refused — answer `SCOPE_CHANGE_REQUIRED`, do not widen the step.{{MULTI_EDIT}}
- No agent commits, pushes, merges or deploys; the pipeline ends at human approval, given outside the agent. A guard's refusal is not a hint to reword.{{TRUST}}
- Verify before reporting done: the verification command once, to the end, every failure fixed as one batch, output shown.
- Context: `grep -n`, then read the hits; never `cat` logs, lockfiles or generated code; a file over ~{{READ_LINES}} lines is read by a FAST reader (`Explore`, `log-reader`) that returns `file:line` excerpts, never the file. Deterministic tools first. {{NEW_CONTEXT}} between tasks. `/usage-report` shows where tokens went.
- Models are tiers, not names: readers and runners on FAST at `low`; the session implements; STRONG and EXPERT only on a named trigger, one agent at a time, never a fleet on the top tier; a failed thinking task is never retried on a cheaper model.
- On compaction keep decisions and their reasons, rejected options, exact paths and names, failed attempts with the error text, open questions and the latest instruction verbatim; trust `.ai/state/handoff.md`{{SNAPSHOT}} over the summary.

<!-- stub: scope=project runtime=* -->
## AI agent workflow

<!-- stub: scope=project runtime=* -->
This repository runs an agentic pipeline under `.ai/`. Read `.ai/AGENTS.md` first: it routes to the policies, workflows and rules, which load on demand; `.ai/policies/` is binding.

<!-- stub: scope=project runtime=* -->
- Production behaviour is the source of truth: document problems outside the task, do not fix them.

<!-- stub: scope=project runtime=claude,codex -->
- A change runs through `/ai-task <request>`; `/ai-status` shows where it stands. Each step names the files it may touch — an edit outside them is refused: answer `SCOPE_CHANGE_REQUIRED`.{{MULTI_EDIT}}

<!-- stub: scope=project runtime=gemini,junie -->
- Changes run through the pipeline (`/ai-task` in Claude Code or Codex); without it, follow `.ai/policies/safety.md`, touch only the files the current task names, and answer questions in prose or by filling the file.

<!-- stub: scope=project runtime=* -->
- Verify before reporting done: `verify_command` from `.ai/policies/testing.md` once, to the end, then `e2e_command` once; every failure fixed as one batch; show the output.
- No agent commits, merges or deploys; approval is given by a human outside the agent. When a review flags the same mistake twice, the correction goes into this file.
- Files, not chat, carry decisions: `.ai/reports/<task-id>/questions.md` (answer by filling `[Answer]:`), `.ai/state/handoff.md` (read first when resuming), `docs/sdlc/constitution.md` (this project's principles).

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
# {{PROJECT}}

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- Project instructions for {{RUNTIME_NAME}}. Keep it short: only what the agent cannot infer from the code. -->

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
## Commands

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- Build, test, lint, run. One line each. -->

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
## Verification

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- The one command that proves the project is healthy. Run it before reporting any task done, and show the output. -->

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
## Conventions

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- Naming, layering, error handling, commit style. Things a reviewer would flag. -->

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
## Architecture

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- Five sentences: entry points, main modules, where state lives, how requests flow. -->

<!-- stub: scope=skeleton-sdlc runtime=* -->
## Workflow

<!-- stub: scope=skeleton-sdlc runtime=* -->
`/sdlc-intent` → `/sdlc-spec` → `/sdlc-plan` → `/ai-task`; artefacts in `docs/sdlc/`. Run `/ai-init` if there is no `.ai/`.

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
## Things {{RUNTIME_NAME}} gets wrong

<!-- stub: scope=skeleton,skeleton-sdlc runtime=* -->
<!-- Recurring mistakes and their corrections. Grow this list from code review. -->
