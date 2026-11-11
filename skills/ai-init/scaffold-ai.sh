#!/usr/bin/env bash
# Idempotent .ai/ scaffold for RiskRails.
#   scaffold-ai.sh [project-dir] [--runtime auto|claude|codex|both|none]   (default: $PWD, auto)
#   none: .ai/ and .gitignore only, no instruction file; a whole value, never part of a comma list
#
# A shim: the scaffold lives in skills/rr-setup/scaffold_ai.py and reads its
# templates from this directory. This file keeps every caller's command working.
SRC="${BASH_SOURCE[0]}"
case "$SRC" in */*) SRC="${SRC%/*}" ;; *) SRC=. ;; esac
HERE="$(cd "${SRC:-/}" && pwd)" || exit 1
exec python3 -I "$HERE/../rr-setup/scaffold_ai.py" "$@"
