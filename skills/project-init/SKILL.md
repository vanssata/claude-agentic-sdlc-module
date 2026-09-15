---
name: project-init
description: Scaffold a repo for Claude Code and/or Codex and the AI-Native SDLC flow — creates docs/sdlc/ (intent/specs/plans/adr with templates), the runtime directory (.claude/{settings.json,memory,plans,agents,skills} and/or .codex/{config.toml,memory,plans,agents,skills}), .gitignore entries and an instruction-file skeleton, then fills it from the codebase. Use when a project has no .claude/ or .codex/ directory, on "/init", "set up this project", "scaffold", "инициализирай проекта".
---

# /project-init

Idempotent project bootstrap. Safe to run again: existing files are never overwritten.

Resolve the install root once — the script is the same in both runtimes:

```bash
for AI_HOME in "${CLAUDE_CONFIG_DIR:-$HOME/.claude}" "${CODEX_HOME:-$HOME/.codex}"; do
  [ -d "$AI_HOME/hooks" ] && break
done
```

## Steps

1. **Scaffold** — run the shared script (same one the `Setup` hook uses) and capture its output:

   ```bash
   "$AI_HOME/hooks/project-scaffold.sh" "$PWD"
   ```

   It takes `--runtime auto|claude|codex|both`; `auto` follows what the project already declares and otherwise scaffolds for the runtime this copy was installed for. Pass `--runtime both` when the repo is worked on from both — `docs/sdlc/**` and `.gitignore` are shared and created once, only the runtime layer is duplicated.

   It creates only what is missing and prints the list. Note which instruction file — `CLAUDE.md`, `AGENTS.md` — is in that list; below, **the instruction file** means whichever one(s) it just created.

2. **Fill the instruction file** — only if the script just created it (otherwise leave the user's file alone and skip to step 3). When both were created, fill both with the same content; they differ only in the runtime-specific notes the templates already carry. Apply the built-in `/init` reasoning to replace the placeholder comments in **Commands / Conventions / Architecture**:
   - Detect the stack from what exists at the repo root: `composer.json` (PHP/Symfony/Sylius — read `scripts`, `require`), `package.json` (`scripts`), `Makefile` (targets), `pyproject.toml`, `go.mod`, `Chart.yaml` / `charts/` / `argocd/` (Helm/ArgoCD), `docker-compose*.yml`, `.github/workflows` / `.gitlab-ci.yml`.
   - Use `grep -n` and bounded reads; do not pull large files into context. Delegate a wide survey to `Explore` (Sonnet, low effort) if the repo is big.
   - Commands: build, test, lint/QA, run — one line each, copied from the manifests, not invented.
   - Conventions: what the linters/config already enforce (ECS/PHPStan level, ESLint config, commit hooks) plus visible naming/layout patterns.
   - Architecture: five sentences max — entry points, main modules, where state lives, request flow.
   - Leave **SDLC workflow** as written and the final section (**Things Claude gets wrong** / **Things the agent gets wrong**) empty.

3. **Report** — print a tree of what was created (from step 1's output), what was filled in, and remind the user:
   - feature work starts with `/sdlc-intent <topic>`;
   - `.claude/settings.local.json`, `.claude/memory/local/` and `.codex/memory/local/` are git-ignored, everything else is meant to be committed.

## Rules

- Never overwrite an existing instruction file, `.claude/settings.json`, `.codex/config.toml` or `.gitignore` content; the script appends/creates only.
- Do not commit; suggest `git add docs/sdlc` plus the runtime directories and instruction files it actually created instead.
- If the scaffold script is missing, tell the user to run `claude-agentic/install.sh`.
