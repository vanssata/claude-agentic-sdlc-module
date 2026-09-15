#!/usr/bin/env bash
# Idempotent .ai/ scaffold for claude-agentic.
#   scaffold-ai.sh [project-dir] [--runtime auto|claude|codex|both]   (default: $PWD, auto)
#
# Never overwrites an existing file. Run it as often as you like: it creates what
# is missing, reports what it created, and leaves everything else alone. That
# matters because .ai/ is meant to be edited by humans after /ai-init fills it.
#
# There is exactly one `.ai/` tree however many agent runtimes the project uses:
# the policies, risk tiers and task state are shared. Only the instruction file
# that points at it differs — CLAUDE.md for Claude Code, AGENTS.md for Codex.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TPL="${CLAUDE_AGENTIC_TEMPLATES:-$HERE/templates}"
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

if [ ! -d "$TPL/.ai" ]; then
  echo "scaffold-ai: templates not found at $TPL (run claude-agentic/install.sh)" >&2
  exit 1
fi

# ---------------------------------------------------------------- runtimes
# What the project already declares wins; a project that declares nothing gets
# the runtime this copy of the plugin was installed for.
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
  *) echo "scaffold-ai: --runtime must be auto|claude|codex|both (got '$RUNTIME')" >&2; exit 2;;
esac

created=()

# Copy the .ai/ tree, file by file, skipping anything that already exists.
while IFS= read -r src; do
  rel="${src#"$TPL"/}"
  dst="$ROOT/$rel"
  [ -e "$dst" ] && continue
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  created+=("$rel")
done < <(find "$TPL/.ai" -type f | sort)

# .gitignore: append once, detected by the first real entry.
GI="$ROOT/.gitignore"
if ! grep -qsF '.ai/state/*.json' "$GI" 2>/dev/null; then
  { [ -s "$GI" ] && [ -n "$(tail -c1 "$GI")" ] && echo; cat "$TPL/gitignore.snippet"; } >> "$GI"
  created+=(".gitignore (appended)")
fi

# The instruction file: create a minimal one if absent, then append the managed
# block once. An existing file is never replaced — only appended to.
PROJECT_ESC=$(printf '%s' "$PROJECT" | sed -e 's/[\/&\\]/\\&/g')
instruction_file() {  # instruction_file <name> <minimal-template> <block-template>
  local md="$ROOT/$1"
  if [ ! -e "$md" ]; then
    sed -e "s/{{PROJECT}}/$PROJECT_ESC/g" "$TPL/$2" > "$md"
    created+=("$1")
  fi
  if ! grep -qsF '<!-- claude-agentic:start -->' "$md" 2>/dev/null; then
    { [ -s "$md" ] && [ -n "$(tail -c1 "$md")" ] && echo; echo; cat "$TPL/$3"; } >> "$md"
    created+=("$1 (agent workflow block appended)")
  fi
}
if [ "$DO_CLAUDE" = 1 ]; then instruction_file CLAUDE.md CLAUDE.minimal.md CLAUDE.block.md; fi
if [ "$DO_CODEX"  = 1 ]; then instruction_file AGENTS.md AGENTS.minimal.md AGENTS.block.md; fi

if [ ${#created[@]} -eq 0 ]; then
  echo "scaffold-ai: nothing to do in $ROOT (already scaffolded)"
else
  echo "scaffold-ai: created in $ROOT:"
  printf '  %s\n' "${created[@]}"
fi
