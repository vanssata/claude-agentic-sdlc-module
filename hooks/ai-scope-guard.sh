#!/usr/bin/env bash
# RiskRails: task-scope guard (PreToolUse on Edit|Write|NotebookEdit, and on
# apply_patch in Codex).
# A shim: the rules live in hooks/ai-guard.py (guard/scope.py), one Python process
# for all three guards. This file keeps the command each runtime registered
# working until the registrations name ai-guard.py itself.
#
# Inert unless .ai/state/state.json (or the legacy current.json) exists and its stage is "implementation".
# Fail-open, like every guard: no python3, or no ai-guard.py beside this file,
# allows (exit 0) rather than blocking the tool.
HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)" || exit 0
[ -f "$HOOK_DIR/ai-guard.py" ] && command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -I -S "$HOOK_DIR/ai-guard.py" --only scope
