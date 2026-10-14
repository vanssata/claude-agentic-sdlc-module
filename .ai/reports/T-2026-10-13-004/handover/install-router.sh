#!/usr/bin/env bash
# HO1 (T-2026-10-13-004, plan rev 2 Step 6): a human installs the router that
# gains the "## Shared files" section. The template is frozen for the agent, so
# this script is the only writer. It refuses unless the template is still the
# committed one, and unless the new router is that template plus the section.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TPL=skills/ai-init/templates/.ai/AGENTS.md
NEW=.ai/reports/T-2026-10-13-004/handover/router.md

if ! git show "HEAD:$TPL" | cmp -s - "$TPL"; then
    echo "refused: $TPL differs from HEAD — someone already changed it; inspect with git diff" >&2
    exit 1
fi
[ -f "$NEW" ] || { echo "refused: $NEW is missing" >&2; exit 1; }

# An insertion, not a rewrite: every line of the old router survives in order,
# and the only added lines are the section, placed right before the table.
added=$(diff "$TPL" "$NEW" | grep -c '^>' || true)
removed=$(diff "$TPL" "$NEW" | grep -c '^<' || true)
[ "$removed" -eq 0 ] || { echo "refused: the new router removes or rewrites $removed line(s)" >&2; exit 1; }
[ "$(grep -c '^## Shared files$' "$NEW")" -eq 1 ] || { echo "refused: '## Shared files' must appear exactly once" >&2; exit 1; }
after=$(awk '/^## Shared files$/{f=1;next} f&&/^## /{print;exit}' "$NEW")
[ "$after" = "## Doing X → read Y" ] || { echo "refused: the section must sit right before '## Doing X → read Y' (found: $after)" >&2; exit 1; }
if awk '/^## Shared files$/{f=1;next} f&&/^## /{exit} f' "$NEW" | grep -q '^|'; then
    echo "refused: the section has a line starting with '|'" >&2; exit 1
fi
size=$(wc -c < "$NEW")
[ "$size" -le 4096 ] || { echo "refused: the new router is $size B > 4096" >&2; exit 1; }

cp "$NEW" "$TPL"
echo "installed: $TPL (+$added lines, $size B)"
echo "next: tell the agent to continue — it rebuilds history (tools/build-template-history.py) and runs the Step 6 tests"
