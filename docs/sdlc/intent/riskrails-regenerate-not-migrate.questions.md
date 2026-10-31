# Questions — riskrails-regenerate-not-migrate
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->

## Q1. Which project files survive the delete in --update (Q26's contradictory tick)? The intent's set omits files that hold a human's choice: .ai/policies/dialog.json (missing = dialog off, update.py:96), path-guard.json, coding/safety/security.md edits, the text outside the managed block in CLAUDE.md/AGENTS.md/GEMINI.md/.junie, .claude/settings.json and .codex/config.toml (created once, update.py:141-146).
asked: 2026-10-31T21:17:38Z · stage: intent
A. Q26's set plus the human's choices: dialog.json, the text outside the managed block, .claude/settings.json and .codex/config.toml; path-guard.json, coding/safety/security.md, AGENTS.md, VERSION, rules/, the managed block, .ai/local/ are deleted and regenerated (recommended)
B. exactly Q26's set; every other riskrails-written file is regenerated, the managed block is rewritten in place, and the dry run lists every file whose content differs from the shipped one before it is deleted
C. Q26's set plus any riskrails file the project changed (content differs from every shipped version): kept as it is, not merged, and reported
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-31T21:20:49Z

## Q2. A project setting lives inside a file riskrails regenerates: weight.json's project entries (the documents/tests globs, the 'this repository:' examples) sit inside the shipped table (weight.py:44 reads the project file whole, else the shipped one), and the five *_command lines sit in testing.md's ## Verification beside shipped prose. How do they survive?
asked: 2026-10-31T21:21:07Z · stage: intent
A. split the files — the shipped part is read from the plugin only, the project part lives in a file of its own the update never touches (.ai/policies/weight.project.json overlaid by weight.py; .ai/policies/verification.md holding the commands, read by state.py verify); the current mixed files are split once by this task's update and never again (recommended)
B. no split — the update reads only the project section out of the old file (named keys of weight.json, the ## Verification block of testing.md), regenerates the file from the template and writes the section back verbatim; an unreadable section is reported and the old file kept
C. weight.json and testing.md become wholly the project's: created once, never regenerated; a newer shipped version is reported as a hint, never applied
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-31T21:25:00Z

## Q3. The deprecated alias skills: five are a SKILL.md only (ai-audit, ai-status, sdlc-intent, sdlc-plan, sdlc-spec); five also hold the plugin's code (ai-task: state.py, rr_state/, weight.py, memory_*; project-update: update.py, render_instructions.py, history/; ai-init and project-init: the templates, scaffold-ai.sh; usage-report: usage-report.py), called by path from 145, 75 and 43 files. The installer never removes a skill directory the plugin stopped shipping (bin/riskrails.js:760-784). What goes, and does the code move?
asked: 2026-10-31T21:25:00Z · stage: intent
A. delete the five SKILL.md-only directories and the alias SKILL.md of the other five; those five stay as code directories under their current paths (no rename here — a move is a refactoring, C3, its own task); the installer gets a retire list that removes the deleted directories from an install (recommended)
B. delete every alias and move the code in this task to the rr-* names (ai-task → rr-build, project-update → rr-setup, …), all 260+ callers edited, plus the installer's retire list
C. as A, and the code moves to one directory without a SKILL.md (skills/riskrails-lib/) in a follow-up refactoring task named by this spec
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-31T21:25:58Z

## Q4. A project older than the kept files' format (e.g. .ai/state/current.json before 0009, a pre-0007 weight.json, no dialog.json before 0010): with the schema ladder gone (.ai/VERSION read by detect_version, update.py:445), what does --update do?
asked: 2026-10-31T21:25:58Z · stage: intent
A. check every kept file with its own reader before anything is deleted (state.json, weight.project.json, verification.md, dialog.json, settings); one unreadable file refuses the whole update with the file, the reason and 'install riskrails@<last version with migrations>, run --update, then this one' — nothing deleted or written (recommended)
B. regenerate anyway; the kept files stay untouched and each one the new version cannot read is reported for the human to fix
C. keep .ai/VERSION as a floor only: below the minimum schema the update refuses with the same message as A; at or above it, no per-file check
X. Other — answer as `X: <text>`
[Answer]: A — by vanssa via prose at 2026-10-31T21:34:49Z
