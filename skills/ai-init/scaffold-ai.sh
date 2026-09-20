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
DO_CLAUDE=0 DO_CODEX=0 DO_GEMINI=0 DO_JUNIE=0
# `both` is the two runtimes that carry the pipeline; a comma list names any of
# the four; `auto` takes what the project already declares.
[ "$RUNTIME" = both ] && RUNTIME="claude,codex"
if [ "$RUNTIME" = auto ]; then
  if [ -e "$ROOT/CLAUDE.md" ] || [ -d "$ROOT/.claude" ]; then DO_CLAUDE=1; fi
  if [ -e "$ROOT/AGENTS.md" ] || [ -d "$ROOT/.codex" ];  then DO_CODEX=1;  fi
  if [ -e "$ROOT/GEMINI.md" ] || [ -d "$ROOT/.gemini" ]; then DO_GEMINI=1; fi
  if [ -d "$ROOT/.junie" ]; then DO_JUNIE=1; fi
  if [ "$DO_CLAUDE" = 0 ] && [ "$DO_CODEX" = 0 ] && [ "$DO_GEMINI" = 0 ] && [ "$DO_JUNIE" = 0 ]; then
    case "$HERE" in *"/.codex/"*) DO_CODEX=1;; *) DO_CLAUDE=1;; esac
  fi
else
  old_ifs="$IFS"; IFS=,
  for one in $RUNTIME; do
    case "$one" in
      claude) DO_CLAUDE=1;;
      codex)  DO_CODEX=1;;
      gemini) DO_GEMINI=1;;
      junie)  DO_JUNIE=1;;
      *) echo "scaffold-ai: --runtime must be auto|both or a comma list of claude,codex,gemini,junie (got '$one')" >&2; exit 2;;
    esac
  done
  IFS="$old_ifs"
fi

created=()

# A project that already has .ai/ carries a schema version this scaffold must not
# invent: writing .ai/VERSION here would tell /project-update that every migration
# has already run. Only a fresh tree starts at the shipped schema.
[ -d "$ROOT/.ai" ] && HAD_AI=1 || HAD_AI=0

# Copy the .ai/ tree, file by file, skipping anything that already exists.
while IFS= read -r src; do
  rel="${src#"$TPL"/}"
  dst="$ROOT/$rel"
  [ -e "$dst" ] && continue
  [ "$rel" = ".ai/VERSION" ] && [ "$HAD_AI" = 1 ] && continue
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
  mkdir -p "$(dirname "$md")"
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
if [ "$DO_GEMINI" = 1 ]; then instruction_file GEMINI.md GEMINI.minimal.md GEMINI.block.md; fi
if [ "$DO_JUNIE"  = 1 ]; then instruction_file .junie/guidelines.md junie-guidelines.minimal.md junie-guidelines.block.md; fi

if [ ${#created[@]} -eq 0 ]; then
  echo "scaffold-ai: nothing to do in $ROOT (already scaffolded)"
else
  echo "scaffold-ai: created in $ROOT:"
  printf '  %s\n' "${created[@]}"
fi
