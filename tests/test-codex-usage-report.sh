#!/usr/bin/env bash
# The Codex half of usage-report.py. Codex does not repeat a response across
# lines the way Claude Code does, but it does write three token counters into
# every record — one for the response, two running totals — and summing the
# wrong one silently multiplies the bill. These fixtures pin which one is read,
# where the model name comes from, and how a spawned thread is attributed.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SCRIPT="$PLUGIN_ROOT/skills/usage-report/usage-report.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
S="$TMP/sessions"; mkdir -p "$S/2026/09/01"

meta() {  # meta <thread-id> <cwd> <session-id> <source-json>
    jq -nc --arg id "$1" --arg cwd "$2" --arg sid "$3" --argjson src "$4" \
      '{type:"session_meta",timestamp:"2026-09-01T10:00:00.000Z",
        payload:{id:$id,session_id:$sid,cwd:$cwd,source:$src,originator:"test"}}'
}
turn() {  # turn <turn-id> <model> <effort> <cwd>
    jq -nc --arg t "$1" --arg m "$2" --arg e "$3" --arg cwd "$4" \
      '{type:"turn_context",timestamp:"2026-09-01T10:00:01.000Z",
        payload:{turn_id:$t,model:$m,effort:$e,cwd:$cwd}}'
}
usage() {  # usage <response-id> <turn-id> <in> <cached> <cache-write> <out> [running-in] [running-out]
    # The running totals default to something absurd on purpose: if the parser
    # ever reads them instead of `usage`, the expected cost is off by miles.
    jq -nc --arg r "$1" --arg t "$2" \
      --argjson i "$3" --argjson ci "$4" --argjson cw "$5" --argjson o "$6" \
      --argjson ri "${7:-99000000}" --argjson ro "${8:-99000000}" \
      '{type:"token_usage_record",timestamp:"2026-09-01T10:00:02.000Z",
        payload:{response_id:$r,turn_id:$t,thread_id:"t",session_id:"t",
          usage:{input_tokens:$i,cached_input_tokens:$ci,cache_write_input_tokens:$cw,output_tokens:$o,total_tokens:($i+$o)},
          turn_token_usage:{input_tokens:$ri,cached_input_tokens:0,cache_write_input_tokens:0,output_tokens:$ro,total_tokens:($ri+$ro)},
          thread_token_usage:{input_tokens:$ri,cached_input_tokens:0,cache_write_input_tokens:0,output_tokens:$ro,total_tokens:($ri+$ro)}}}'
}

run() { python3 "$SCRIPT" --provider codex --root "$S" --all "$@" 2>&1; }

# terra: $1/MTok in, $5/MTok out, cache read 0.1x, cache write 2x.
echo "== the per-response counter is billed, not the running total"
{
    meta t /work t '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage r1 turn1 1000000 0 0 100000   9000000 9000000
    usage r2 turn1 1000000 0 0 100000  99000000 99000000
} > "$S/2026/09/01/rollout-2026-09-01T10-00-00-t.jsonl"
# 2 x (1M in @ $1 + 100k out @ $5) = $2.00 + $1.00 = $3.00
out=$(run)
printf '%s' "$out" | grep -q 'TOTAL  \$3.00' \
    && pass "each response is billed once, from usage and not from the running totals" \
    || fail "expected TOTAL \$3.00" "$out"
printf '%s' "$out" | grep -q 'gpt-5.6-terra (medium)' \
    && pass "the model and effort come from the turn context" || fail "model not resolved" "$out"

echo "== cached input is not billed twice"
{
    meta t2 /work t2 '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage r1 turn1 1000000 900000 0 0
} > "$S/2026/09/01/rollout-2026-09-01T11-00-00-t2.jsonl"
rm "$S/2026/09/01/rollout-2026-09-01T10-00-00-t.jsonl"
# input_tokens includes the cached part: 100k fresh @ $1 + 900k cached @ $0.10 = $0.19
out=$(run)
printf '%s' "$out" | grep -q 'TOTAL  \$0.19' \
    && pass "cached tokens are charged at the cache rate, not the full input rate" \
    || fail "expected TOTAL \$0.19" "$out"
printf '%s' "$out" | grep -qE '^codex +gpt-5.6-terra \(medium\) +100,000 ' \
    && pass "and the IN column shows fresh input only" || fail "IN column wrong" "$out"

echo "== a repeated response_id is counted once"
{
    meta t3 /work t3 '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage same turn1 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T12-00-00-t3.jsonl"
{
    meta t4 /work t4 '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage same turn1 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T13-00-00-t4.jsonl"
rm "$S/2026/09/01/rollout-2026-09-01T11-00-00-t2.jsonl"
out=$(run)
printf '%s' "$out" | grep -q 'TOTAL  \$1.00' \
    && pass "a resumed thread replaying a response does not double-bill it" \
    || fail "expected TOTAL \$1.00" "$out"

echo "== a spawned thread is attributed to subagents, by name"
rm "$S/2026/09/01/rollout-2026-09-01T13-00-00-t4.jsonl"
{
    meta sub /work parent '{"subagent":{"other":"ai-reviewer"}}'
    turn  turnS gpt-5.6-sol high /work
    usage rs turnS 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T14-00-00-sub.jsonl"
# terra 1M in = $1.00, sol 1M in = $5.00 -> total $6.00, subagents $5.00 (83%)
out=$(run)
printf '%s' "$out" | grep -q 'TOTAL  \$6.00' && pass "both threads are counted" || fail "expected TOTAL \$6.00" "$out"
printf '%s' "$out" | grep -q 'SUBAGENTS  \$5.00 (83% of total)' \
    && pass "the spawned thread is reported as a subagent" || fail "subagent share wrong" "$out"
printf '%s' "$out" | grep -q 'ai-reviewer' \
    && pass "and named, so the report says which agent spent it" || fail "agent name missing" "$out"

echo "== a string-form subagent source is recognised too"
printf '%s\n' "$(meta sub2 /work parent2 '{"subagent":"review"}')" \
              "$(turn turnR gpt-5.6-sol high /work)" \
              "$(usage rr turnR 1000000 0 0 0)" \
    > "$S/2026/09/01/rollout-2026-09-01T15-00-00-sub2.jsonl"
out=$(run)
printf '%s' "$out" | grep -q 'review' && pass "{\"subagent\":\"review\"} is recognised" || fail "string form missed" "$out"

echo "== the cost column is labelled an estimate while the rates are unverified"
verified=$(jq -r '.codex.rates_verified' "$PLUGIN_ROOT/skills/usage-report/prices.json")
if [ "$verified" = false ]; then
    printf '%s' "$out" | grep -q 'ESTIMATE for codex' \
        && pass "an unverified price table is declared, not presented as fact" || fail "estimate note missing" "$out"
else
    printf '%s' "$out" | grep -q 'ESTIMATE for codex' \
        && fail "rates are verified but the report still calls them an estimate" \
        || pass "verified rates are reported without the estimate note"
fi

echo "== --today filters by the record timestamp"
out=$(run --today)
printf '%s' "$out" | grep -q 'no usage records matched' \
    && pass "a day with no records reports nothing rather than everything" || fail "--today did not filter" "$out"

echo "== the provider is sniffed from the directory when it is not given"
out=$(python3 "$SCRIPT" --root "$S" --all 2>&1)
printf '%s' "$out" | grep -q '^codex ' && pass "rollout-*.jsonl is recognised as Codex" || fail "sniff failed" "$out"

echo "== an empty directory is not an error"
mkdir -p "$TMP/empty"
out=$(python3 "$SCRIPT" --provider codex --root "$TMP/empty" --all 2>&1)
printf '%s' "$out" | grep -q 'no usage records matched' && pass "an empty root says so" || fail "empty root mishandled" "$out"

echo "== malformed records are skipped, not fatal"
{
    printf 'not json at all\n'
    printf '{"type":"token_usage_record","payload":{}}\n'
    printf '{"type":"turn_context"}\n'
    printf '{}\n'
    meta t9 /work t9 '"cli"'
    turn  turn9 gpt-5.6-terra medium /work
    usage r9 turn9 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T16-00-00-t9.jsonl"
out=$(python3 "$SCRIPT" --provider codex --root "$S" --all 2>&1); rc=$?
[ $rc -eq 0 ] && pass "a corrupt transcript does not crash the report" || fail "exit $rc" "$out"
printf '%s' "$out" | grep -q 'gpt-5.6-terra' && pass "and the good records are still counted" || fail "good records lost" "$out"

echo "== a usage record with no turn context falls back to the last model seen"
{
    meta t10 /work t10 '"cli"'
    turn  turnA gpt-5.6-sol high /work
    usage rA unknown-turn 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T17-00-00-t10.jsonl"
out=$(python3 "$SCRIPT" --provider codex --root "$S" --all 2>&1)
printf '%s' "$out" | grep -q 'gpt-5.6-sol (high)' \
    && pass "an unannounced turn is attributed to the thread's last model, not to 'unknown'" \
    || fail "fallback model missing" "$out"

echo "== --provider both reads neither runtime's records into the other"
CL="$TMP/claude-proj"; mkdir -p "$CL"
printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"m1","model":"claude-sonnet-5","usage":{"input_tokens":1000000,"output_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' > "$CL/s.jsonl"
out=$(python3 "$SCRIPT" --root "$CL" --all 2>&1)
printf '%s' "$out" | grep -q '^claude ' && pass "a Claude directory is sniffed as Claude" || fail "claude sniff failed" "$out"
printf '%s' "$out" | grep -q '^codex ' && fail "Claude records must not be attributed to codex" || pass "and produces no codex rows"

summary "codex usage-report"
