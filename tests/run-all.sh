#!/usr/bin/env bash
# Every test in this plugin. Exits non-zero if any suite fails.
set -uo pipefail
cd "$(dirname "$0")"

for tool in jq python3 git; do
    command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool" >&2; exit 1; }
done

FAILED=""
for suite in test-ai-path-guard.sh test-ai-scope-guard.sh test-ai-git-guard.sh \
             test-ai-task-state.sh test-scaffold-idempotency.sh test-install-dry-run.sh \
             test-end-to-end.sh test-merge-migration.sh test-usage-report.sh; do
    [ -f "$suite" ] || continue
    printf '\n--- %s\n' "$suite"
    bash "$suite" || FAILED="$FAILED $suite"
done

printf '\n'
if [ -n "$FAILED" ]; then
    printf 'FAILED:%s\n' "$FAILED"
    exit 1
fi
printf 'all suites passed\n'
