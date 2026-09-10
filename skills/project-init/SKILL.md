---
name: project-init
description: Scaffold a repo for Claude Code and the AI-Native SDLC flow — creates docs/sdlc/ (intent/specs/plans/adr with templates), .claude/{settings.json,memory,plans,agents,skills}, .gitignore entries and a CLAUDE.md skeleton, then fills CLAUDE.md from the codebase. Use when a project has no .claude/ directory, on "/init", "set up this project", "scaffold", "инициализирай проекта".
---

# /project-init

Idempotent project bootstrap. Safe to run again: existing files are never overwritten.

## Steps

1. **Scaffold** — run the shared script (same one the `Setup` hook uses) and capture its output:

   ```bash
   "$HOME/.claude/hooks/project-scaffold.sh" "$PWD"
   ```

   It creates only what is missing and prints the list. Note whether `CLAUDE.md` is in that list.

2. **Fill `CLAUDE.md`** — only if the script just created it (otherwise leave the user's file alone and skip to step 3). Apply the built-in `/init` reasoning to replace the placeholder comments in **Commands / Conventions / Architecture**:
   - Detect the stack from what exists at the repo root: `composer.json` (PHP/Symfony/Sylius — read `scripts`, `require`), `package.json` (`scripts`), `Makefile` (targets), `pyproject.toml`, `go.mod`, `Chart.yaml` / `charts/` / `argocd/` (Helm/ArgoCD), `docker-compose*.yml`, `.github/workflows` / `.gitlab-ci.yml`.
   - Use `grep -n` and bounded reads; do not pull large files into context. Delegate a wide survey to `Explore` (Sonnet, low effort) if the repo is big.
   - Commands: build, test, lint/QA, run — one line each, copied from the manifests, not invented.
   - Conventions: what the linters/config already enforce (ECS/PHPStan level, ESLint config, commit hooks) plus visible naming/layout patterns.
   - Architecture: five sentences max — entry points, main modules, where state lives, request flow.
   - Leave **SDLC workflow** as written and **Things Claude gets wrong** empty.

3. **Report** — print a tree of what was created (from step 1's output), what was filled in, and remind the user:
   - feature work starts with `/sdlc-intent <topic>`;
   - `.claude/settings.local.json` and `.claude/memory/local/` are git-ignored, everything else is meant to be committed.

## Rules

- Never overwrite an existing `CLAUDE.md`, `.claude/settings.json` or `.gitignore` content; the script appends/creates only.
- Do not commit; suggest `git add docs/sdlc .claude CLAUDE.md .gitignore` instead.
- If the scaffold script is missing, tell the user to run `claude-agentic/install.sh`.
