#!/usr/bin/env bash
# RiskRails is installed with npx since 3.0.0; this script only says how.
#   npx riskrails@<version> [--target auto|claude|codex|both] [--plan …] [--fable …]
#                           [--codex-plan …] [--dry-run] [--home DIR] [--codex-home DIR]
# From a checkout, `node bin/riskrails.js` takes the same flags. The 2.0.x install.sh is
# at the v2.0.2 tag. Exits 2, so a script that still calls this one stops instead of
# believing it installed something.
set -u
SRC="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(sed -n 's/^  "version": "\([^"]*\)",$/\1/p' "$SRC/package.json" 2>/dev/null)
{
  echo "install.sh no longer installs RiskRails. Run:"
  echo
  echo "  npx riskrails@${VERSION:-latest}${*:+ $*}"
  echo
  echo "or, from this checkout: node bin/riskrails.js${*:+ $*}"
} >&2
exit 2
