#!/usr/bin/env bash
# Idempotent project scaffold: the shared SDLC folders plus the layout of every
# agent runtime the project uses. Never overwrites an existing file.
#   project-scaffold.sh [project-dir] [--runtime auto|claude|codex|both]
# (default: $PWD, auto)
# Also wired as a Claude Code Setup hook (matcher "init"); it reads the hook JSON on stdin only to
# pick up cwd when no argument is given.
#
# A shim: the scaffold lives in hooks/project-scaffold.py. This file keeps the
# Setup registration and every caller's command working.
HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)" || exit 1
exec python3 -I "$HOOK_DIR/project-scaffold.py" "$@"
