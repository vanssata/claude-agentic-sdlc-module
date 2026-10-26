#!/usr/bin/env bash
# claude-agentic: git and deployment safety guard (PreToolUse on Bash).
# A shim: the rules live in hooks/ai-guard.py (guard/git.py), one Python process
# for all three guards. This file keeps the command each runtime registered
# working until the registrations name ai-guard.py itself.
#
# GLOBAL: not gated on .ai/ — the operations it refuses are wrong in any
# repository. Fail-open, like every guard: no python3, or no ai-guard.py beside
# this file, allows (exit 0) rather than blocking the tool.
HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)" || exit 0
[ -f "$HOOK_DIR/ai-guard.py" ] && command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -I -S "$HOOK_DIR/ai-guard.py" --only git
