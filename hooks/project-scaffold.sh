#!/usr/bin/env bash
# Idempotent project scaffold: the shared SDLC folders plus the layout of every
# agent runtime the project uses. Never overwrites an existing file.
#   project-scaffold.sh [project-dir] [--runtime auto|claude|codex|both]
# (default: $PWD, auto)
# Also wired as a Claude Code Setup hook (matcher "init"); it reads the hook JSON on stdin only to
# pick up cwd when no argument is given.
#
# docs/sdlc/** and .gitignore are shared and are created once. Only the
# provider-specific layer — .claude/** with CLAUDE.md, .codex/** with AGENTS.md —
# is duplicated, and only for the runtimes in scope.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL="${AI_PROJECT_TEMPLATES:-${CLAUDE_ROUTING_TEMPLATES:-$HERE/../skills/project-init/templates}}"
ROOT=""
RUNTIME="${AI_RUNTIMES:-auto}"
while [ $# -gt 0 ]; do
  case "$1" in
    --runtime) RUNTIME="${2:?missing value for --runtime}"; shift 2;;
    --runtime=*) RUNTIME="${1#*=}"; shift;;
    *) ROOT="$1"; shift;;
  esac
done
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

# ---------------------------------------------------------------- runtimes
# What the project already declares wins; a project that declares nothing gets
# the runtime this copy of the plugin was installed for, so scaffolding from a
# Codex session does not leave a stray CLAUDE.md behind (and the reverse).
DO_CLAUDE=0 DO_CODEX=0
case "$RUNTIME" in
  claude) DO_CLAUDE=1;;
  codex)  DO_CODEX=1;;
  both)   DO_CLAUDE=1; DO_CODEX=1;;
  auto)
    if [ -e "$ROOT/CLAUDE.md" ] || [ -d "$ROOT/.claude" ]; then DO_CLAUDE=1; fi
    if [ -e "$ROOT/AGENTS.md" ] || [ -d "$ROOT/.codex" ];  then DO_CODEX=1;  fi
    if [ "$DO_CLAUDE" = 0 ] && [ "$DO_CODEX" = 0 ]; then
      case "$HERE" in *"/.codex/"*) DO_CODEX=1;; *) DO_CLAUDE=1;; esac
    fi;;
  *) echo "project-scaffold: --runtime must be auto|claude|codex|both (got '$RUNTIME')" >&2; exit 2;;
esac

created=()
PROJECT_ESC=$(printf '%s' "$PROJECT" | sed -e 's/[\/&\\]/\\&/g')
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

# ---------------------------------------------------------------- shared SDLC
put sdlc-README.md         docs/sdlc/README.md
put intent.md              docs/sdlc/intent/TEMPLATE.md
put spec.md                docs/sdlc/specs/TEMPLATE.md
put plan.md                docs/sdlc/plans/TEMPLATE.md
put adr.md                 docs/sdlc/adr/TEMPLATE.md

# ---------------------------------------------------------------- per runtime
if [ "$DO_CLAUDE" = 1 ]; then
  put project-settings.json  .claude/settings.json
  put memory-README.md       .claude/memory/README.md
  keep .claude/plans
  keep .claude/agents
  keep .claude/skills
  put CLAUDE.md              CLAUDE.md "s/{{PROJECT}}/$PROJECT_ESC/g"
fi
if [ "$DO_CODEX" = 1 ]; then
  put project-config.toml    .codex/config.toml "s/{{PROJECT}}/$PROJECT_ESC/g"
  put memory-README.md       .codex/memory/README.md
  keep .codex/plans
  keep .codex/agents
  keep .codex/skills
  put AGENTS.md              AGENTS.md "s/{{PROJECT}}/$PROJECT_ESC/g"
fi

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
