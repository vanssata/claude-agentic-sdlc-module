#!/usr/bin/env bash
# Every test in this plugin. Exits non-zero if any suite fails.
set -uo pipefail
cd "$(dirname "$0")"

for tool in jq python3 git; do
    command -v "$tool" >/dev/null 2>&1 || { echo "missing required tool: $tool" >&2; exit 1; }
done

FAILED=""
for suite in test-guard-characterization.sh \
             test-scaffold-idempotency.sh test-install-dry-run.sh \
             test-end-to-end.sh test-merge-migration.sh test-project-update.sh test-project-adopt.sh test-usage-report.sh \
             test-runtime-gate-fable.sh \
             test-codex-agent-render.sh test-codex-install.sh test-dual-runtime-install.sh \
             test-runtime-gate-codex.sh test-codex-usage-report.sh test-instruction-budget.sh \
             test-profiles.sh test-shared-prompts-model-free.sh test-shared-tree.sh \
             test-migration-0006.sh; do
    [ -f "$suite" ] || continue
    printf '\n--- %s\n' "$suite"
    bash "$suite" || FAILED="$FAILED $suite"
done

# The Python suites (tests/test_*.py), one process; the e2e module skips itself without AI_E2E.
printf '\n--- python3 -m unittest discover\n'
python3 -I -m unittest discover -s . -p 'test_*.py' || FAILED="$FAILED unittest"

printf '\n'
if [ -n "$FAILED" ]; then
    printf 'FAILED:%s\n' "$FAILED"
    exit 1
fi
printf 'all suites passed\n'
