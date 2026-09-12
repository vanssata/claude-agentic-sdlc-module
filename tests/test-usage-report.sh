#!/usr/bin/env bash
# usage-report.py: one API response is written as several transcript lines that
# repeat the same message id and usage — it must be counted once, not per line.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SCRIPT="$PLUGIN_ROOT/skills/usage-report/usage-report.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/proj/sess1/subagents"

line() {  # line <id> <model> <out> <cache_read>
    printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"%s","model":"%s","usage":{"input_tokens":0,"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":%s}}}\n' "$@"
}

echo "== a response split over three lines is counted once"
{
    line msg_a claude-sonnet-5 10 1000000     # thinking block
    line msg_a claude-sonnet-5 10 1000000     # text block
    line msg_a claude-sonnet-5 100000 1000000 # tool_use block, final output count
} > "$TMP/proj/sess1.jsonl"
# sonnet: 1M cache read * $2 * 0.1 = $0.20; 100k output * $10 = $1.00
out=$(python3 "$SCRIPT" --root "$TMP/proj" 2>&1)
printf '%s' "$out" | grep -q 'TOTAL  \$1.20' && pass "duplicated lines are billed once, at the final output count" || fail "expected TOTAL \$1.20" "$out"

echo "== subagent transcripts are reported as their own share"
line msg_b claude-opus-5 0 1000000 > "$TMP/proj/sess1/subagents/agent-x1.jsonl"   # $0.50
out=$(python3 "$SCRIPT" --root "$TMP/proj" 2>&1)
printf '%s' "$out" | grep -q 'TOTAL  \$1.70' && pass "the subagent response is added once" || fail "expected TOTAL \$1.70" "$out"
printf '%s' "$out" | grep -q 'SUBAGENTS  \$0.50 (29% of total)' && pass "the subagent share is reported" || fail "expected SUBAGENTS \$0.50" "$out"

summary "usage-report"
