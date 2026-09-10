#!/usr/bin/env bash
# Idempotent project scaffold: SDLC folders + .claude/ layout. Never overwrites an existing file.
# Usage: project-scaffold.sh [project-dir]      (default: $PWD)
# Also wired as a Claude Code Setup hook (matcher "init"); it reads the hook JSON on stdin only to
# pick up cwd when no argument is given.
set -euo pipefail

TPL="${CLAUDE_ROUTING_TEMPLATES:-$HOME/.claude/skills/project-init/templates}"
ROOT="${1:-}"
if [ -z "$ROOT" ] && [ ! -t 0 ]; then
  ROOT=$(python3 -c 'import json,sys
try: print(json.load(sys.stdin).get("cwd",""))
except Exception: print("")' 2>/dev/null || true)
fi
ROOT="${ROOT:-$PWD}"
ROOT="$(cd "$ROOT" && pwd)"
PROJECT="$(basename "$ROOT")"

if [ ! -d "$TPL" ]; then
  echo "project-scaffold: templates not found at $TPL (run claude-agentic/install.sh)" >&2
  exit 1
fi

created=()
put() {  # put <template> <target> [sed-expr]
  local src="$TPL/$1" dst="$ROOT/$2"
  [ -e "$dst" ] && return 0
  mkdir -p "$(dirname "$dst")"
  if [ -n "${3:-}" ]; then sed -e "$3" "$src" > "$dst"; else cp "$src" "$dst"; fi
  created+=("$2")
}
keep() {  # keep <dir>  -> dir/.gitkeep
  local d="$ROOT/$1"
  [ -e "$d/.gitkeep" ] && return 0
  mkdir -p "$d"; : > "$d/.gitkeep"; created+=("$1/.gitkeep")
}

put sdlc-README.md         docs/sdlc/README.md
put intent.md              docs/sdlc/intent/TEMPLATE.md
put spec.md                docs/sdlc/specs/TEMPLATE.md
put plan.md                docs/sdlc/plans/TEMPLATE.md
put adr.md                 docs/sdlc/adr/TEMPLATE.md
put project-settings.json  .claude/settings.json
put memory-README.md       .claude/memory/README.md
keep .claude/plans
keep .claude/agents
keep .claude/skills
PROJECT_ESC=$(printf '%s' "$PROJECT" | sed -e 's/[\/&\\]/\\&/g')
put CLAUDE.md              CLAUDE.md "s/{{PROJECT}}/$PROJECT_ESC/g"

# .gitignore: append the snippet only if its first real entry is absent
GI="$ROOT/.gitignore"
if ! grep -qsF '.claude/settings.local.json' "$GI" 2>/dev/null; then
  { [ -s "$GI" ] && [ -n "$(tail -c1 "$GI")" ] && echo; cat "$TPL/gitignore.snippet"; } >> "$GI"
  created+=(".gitignore (appended)")
fi

if [ ${#created[@]} -eq 0 ]; then
  echo "project-scaffold: nothing to do in $ROOT (already scaffolded)"
else
  echo "project-scaffold: created in $ROOT:"
  printf '  %s\n' "${created[@]}"
fi
