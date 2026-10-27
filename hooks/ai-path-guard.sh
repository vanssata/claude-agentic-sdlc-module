#!/usr/bin/env bash
# RiskRails: sensitive-path guard (PreToolUse on Read|Edit|Write|NotebookEdit|Bash;
# in Codex on Bash|apply_patch).
# A shim: the rules live in hooks/ai-guard.py (guard/paths.py), one Python process
# for all three guards. This file keeps the command each runtime registered
# working until the registrations name ai-guard.py itself.
#
# Opt-in by construction: inert unless the project has a .ai/ directory, except
# the --confirm-delete rule. Fail-open, like every guard: no python3, or no
# ai-guard.py beside this file, allows (exit 0) rather than blocking the tool.
HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)" || exit 0
[ -f "$HOOK_DIR/ai-guard.py" ] && command -v python3 >/dev/null 2>&1 || exit 0
exec python3 -I -S "$HOOK_DIR/ai-guard.py" --only paths
