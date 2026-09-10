#!/usr/bin/env bash
# Idempotent .ai/ scaffold for claude-agentic.
#   scaffold-ai.sh [project-dir]     (default: $PWD)
#
# Never overwrites an existing file. Run it as often as you like: it creates what
# is missing, reports what it created, and leaves everything else alone. That
# matters because .ai/ is meant to be edited by humans after /ai-init fills it.
set -euo pipefail

TPL="${CLAUDE_AGENTIC_TEMPLATES:-$HOME/.claude/skills/ai-init/templates}"
ROOT="${1:-}"
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

# CLAUDE.md: create a minimal one if absent, then append the managed block once.
MD="$ROOT/CLAUDE.md"
if [ ! -e "$MD" ]; then
  PROJECT_ESC=$(printf '%s' "$PROJECT" | sed -e 's/[\/&\\]/\\&/g')
  sed -e "s/{{PROJECT}}/$PROJECT_ESC/g" "$TPL/CLAUDE.minimal.md" > "$MD"
  created+=("CLAUDE.md")
fi
if ! grep -qsF '<!-- claude-agentic:start -->' "$MD" 2>/dev/null; then
  { [ -s "$MD" ] && [ -n "$(tail -c1 "$MD")" ] && echo; echo; cat "$TPL/CLAUDE.block.md"; } >> "$MD"
  created+=("CLAUDE.md (agent workflow block appended)")
fi

if [ ${#created[@]} -eq 0 ]; then
  echo "scaffold-ai: nothing to do in $ROOT (already scaffolded)"
else
  echo "scaffold-ai: created in $ROOT:"
  printf '  %s\n' "${created[@]}"
fi
