#!/usr/bin/env bash
# D3 (T-2026-10-13-004, plan rev 2 Step 7): a human retires the 29 shared files
# from the ai-init template tree. From here on they ship only under ai/ and
# /ai-init no longer copies them. Recoverable from git (git checkout HEAD -- …).
#
# Phase 1 compares every one of the 29 with its ai/ copy and collects every
# difference; any difference prints them all and exits 1 before anything is
# removed (L2). Phase 2 removes the 29 and lists them.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TPL=skills/ai-init/templates/.ai
SRC=ai

SHARED=(
    policies/production.md
    policies/database.md
    policies/git.md
    policies/release.md
    policies/context-management.md
    policies/tooling.md
    policies/model-routing.md
    policies/review-economy.md
    agents/context.md
    agents/discovery.md
    agents/implementer.md
    agents/manager.md
    agents/planner.md
    agents/release.md
    agents/reviewer.md
    agents/risk.md
    agents/security.md
    agents/tester.md
    workflows/feature.md
    workflows/bugfix.md
    workflows/hotfix.md
    workflows/investigation.md
    workflows/refactoring.md
    templates/task-context.md
    templates/impact-report.md
    templates/review-report.md
    templates/release-report.md
    templates/architecture-decision.md
    templates/implementation-plan.md
)

[ "${#SHARED[@]}" -eq 29 ] || { echo "refused: the list holds ${#SHARED[@]} paths, not 29" >&2; exit 1; }

# Phase 1: compare all, remove nothing.
problems=()
for rel in "${SHARED[@]}"; do
    if [ ! -f "$SRC/$rel" ]; then
        problems+=("missing in $SRC/: $rel")
    elif [ ! -f "$TPL/$rel" ]; then
        problems+=("missing in $TPL/: $rel")
    elif ! cmp -s "$SRC/$rel" "$TPL/$rel"; then
        problems+=("differs: $SRC/$rel vs $TPL/$rel")
    fi
done
extra=$(cd "$SRC" && find . -type f | sed 's|^\./||' | sort | comm -23 - <(printf '%s\n' "${SHARED[@]}" | sort))
[ -z "$extra" ] || while IFS= read -r f; do problems+=("in $SRC/ but not in the list: $f"); done <<< "$extra"
for keep in policies/safety.md policies/security.md; do
    [ -f "$TPL/$keep" ] || problems+=("project-owned file absent from $TPL/: $keep")
done

if [ "${#problems[@]}" -gt 0 ]; then
    echo "refused: nothing removed; ${#problems[@]} problem(s):" >&2
    printf '  %s\n' "${problems[@]}" >&2
    exit 1
fi
echo "phase 1: all 29 byte-identical to $SRC/"

# Phase 2: remove.
for rel in "${SHARED[@]}"; do
    rm -- "$TPL/$rel"
    echo "removed: $TPL/$rel"
done
echo "phase 2: removed 29; safety.md and security.md kept"
echo "undo: git checkout HEAD -- $TPL"
echo "next: tell the agent to continue — it writes 0006, the update.py wiring and the tests"
