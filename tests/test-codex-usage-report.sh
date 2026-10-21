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
export USAGE_REPORT_CACHE="$TMP/suite-cache.json"   # the corpus runs cached

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

# terra: $2/MTok in, $12/MTok out, cache read 0.1x, cache write 1.25x; sol: $4 in, $20 out.
echo "== the per-response counter is billed, not the running total"
{
    meta t /work t '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage r1 turn1 1000000 0 0 100000   9000000 9000000
    usage r2 turn1 1000000 0 0 100000  99000000 99000000
} > "$S/2026/09/01/rollout-2026-09-01T10-00-00-t.jsonl"
# 2 x (1M in @ $2 + 100k out @ $12) = $4.00 + $2.40 = $6.40
out=$(run)
grep -q 'TOTAL  \$6.40' <<<"$out" \
    && pass "each response is billed once, from usage and not from the running totals" \
    || fail "expected TOTAL \$6.40" "$out"
grep -q 'gpt-5.6-terra (medium)' <<<"$out" \
    && pass "the model and effort come from the turn context" || fail "model not resolved" "$out"

echo "== cached input is not billed twice"
{
    meta t2 /work t2 '"cli"'
    turn  turn1 gpt-5.6-terra medium /work
    usage r1 turn1 1000000 900000 0 0
} > "$S/2026/09/01/rollout-2026-09-01T11-00-00-t2.jsonl"
rm "$S/2026/09/01/rollout-2026-09-01T10-00-00-t.jsonl"
# input_tokens includes the cached part: 100k fresh @ $2 + 900k cached @ $0.20 = $0.38
out=$(run)
grep -q 'TOTAL  \$0.38' <<<"$out" \
    && pass "cached tokens are charged at the cache rate, not the full input rate" \
    || fail "expected TOTAL \$0.38" "$out"
grep -qE '^codex +gpt-5.6-terra \(medium\) +100,000 ' <<<"$out" \
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
grep -q 'TOTAL  \$2.00' <<<"$out" \
    && pass "a resumed thread replaying a response does not double-bill it" \
    || fail "expected TOTAL \$2.00" "$out"

echo "== a spawned thread is attributed to subagents, by name"
rm "$S/2026/09/01/rollout-2026-09-01T13-00-00-t4.jsonl"
{
    meta sub /work parent '{"subagent":{"other":"ai-reviewer"}}'
    turn  turnS gpt-5.6-sol high /work
    usage rs turnS 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T14-00-00-sub.jsonl"
# terra 1M in = $2.00, sol 1M in = $4.00 -> total $6.00, subagents $4.00 (67%)
out=$(run)
grep -q 'TOTAL  \$6.00' <<<"$out" && pass "both threads are counted" || fail "expected TOTAL \$6.00" "$out"
grep -q 'SUBAGENTS  \$4.00 (67% of total)' <<<"$out" \
    && pass "the spawned thread is reported as a subagent" || fail "subagent share wrong" "$out"
grep -q 'ai-reviewer' <<<"$out" \
    && pass "and named, so the report says which agent spent it" || fail "agent name missing" "$out"

echo "== a string-form subagent source is recognised too"
printf '%s\n' "$(meta sub2 /work parent2 '{"subagent":"review"}')" \
              "$(turn turnR gpt-5.6-sol high /work)" \
              "$(usage rr turnR 1000000 0 0 0)" \
    > "$S/2026/09/01/rollout-2026-09-01T15-00-00-sub2.jsonl"
out=$(run)
grep -q 'review' <<<"$out" && pass "{\"subagent\":\"review\"} is recognised" || fail "string form missed" "$out"

echo "== the cost column is labelled an estimate while the rates are unverified"
verified=$(jq -r '.codex.rates_verified' "$PLUGIN_ROOT/skills/usage-report/prices.json")
if [ "$verified" = false ]; then
    grep -q 'ESTIMATE for codex' <<<"$out" \
        && pass "an unverified price table is declared, not presented as fact" || fail "estimate note missing" "$out"
else
    grep -q 'ESTIMATE for codex' <<<"$out" \
        && fail "rates are verified but the report still calls them an estimate" \
        || pass "verified rates are reported without the estimate note"
fi

echo "== --today filters by the record timestamp"
out=$(run --today)
grep -q 'no usage records matched' <<<"$out" \
    && pass "a day with no records reports nothing rather than everything" || fail "--today did not filter" "$out"

echo "== the provider is sniffed from the directory when it is not given"
out=$(python3 "$SCRIPT" --root "$S" --all 2>&1)
grep -q '^codex ' <<<"$out" && pass "rollout-*.jsonl is recognised as Codex" || fail "sniff failed" "$out"

echo "== an empty directory is not an error"
mkdir -p "$TMP/empty"
out=$(python3 "$SCRIPT" --provider codex --root "$TMP/empty" --all 2>&1)
grep -q 'no usage records matched' <<<"$out" && pass "an empty root says so" || fail "empty root mishandled" "$out"

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
grep -q 'gpt-5.6-terra' <<<"$out" && pass "and the good records are still counted" || fail "good records lost" "$out"

echo "== a usage record with no turn context falls back to the last model seen"
{
    meta t10 /work t10 '"cli"'
    turn  turnA gpt-5.6-sol high /work
    usage rA unknown-turn 1000000 0 0 0
} > "$S/2026/09/01/rollout-2026-09-01T17-00-00-t10.jsonl"
out=$(python3 "$SCRIPT" --provider codex --root "$S" --all 2>&1)
grep -q 'gpt-5.6-sol (high)' <<<"$out" \
    && pass "an unannounced turn is attributed to the thread's last model, not to 'unknown'" \
    || fail "fallback model missing" "$out"

echo "== --provider both reads neither runtime's records into the other"
CL="$TMP/claude-proj"; mkdir -p "$CL"
printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"m1","model":"claude-sonnet-5","usage":{"input_tokens":1000000,"output_tokens":0,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' > "$CL/s.jsonl"
out=$(python3 "$SCRIPT" --root "$CL" --all 2>&1)
grep -q '^claude ' <<<"$out" && pass "a Claude directory is sniffed as Claude" || fail "claude sniff failed" "$out"
grep -q '^codex ' <<<"$out" && fail "Claude records must not be attributed to codex" || pass "and produces no codex rows"

echo "== the incremental parse cache, on a rollout file"
# A rollout file is appended to for as long as the thread lives, so the cache
# earns its keep here — and must report exactly what an uncached run reports.
C="$TMP/cache.json"; R="$S/2026/09/01/rollout-2026-09-01T18-00-00-t11.jsonl"
{ meta t11 /work t11 '"cli"'; turn turnC gpt-5.6-sol high /work
  usage rc1 turnC 1000000 0 0 0; } > "$R"
ccached() { USAGE_REPORT_CACHE="$C" python3 "$SCRIPT" --provider codex --root "$S" --all 2>&1; }
cplain()  { USAGE_REPORT_CACHE="" python3 "$SCRIPT" --provider codex --root "$S" --all 2>&1; }

cold=$(ccached)
[ "$cold" = "$(cplain)" ] && pass "a cold run reports what an uncached run reports" || fail "cold run differs" "$cold"
chmod 000 "$R"
[ "$(ccached)" = "$cold" ] && pass "an unchanged rollout file is not read again at all" || fail "an unchanged rollout was re-read"
chmod 644 "$R"
usage rc2 turnC 2000000 0 0 0 >> "$R"
[ "$(ccached)" = "$(cplain)" ] && pass "an appended rollout file is folded from the offset, not from zero" || fail "append" "$(ccached)"

# A rollout file whose last record has no newline after it, and no response_id:
# the record is keyed by its position, so a state that folded the tail into
# itself would append a new key on every rescan and the bill would grow.
NL="$TMP/nonl"; mkdir -p "$NL"; NC="$TMP/nonl-cache.json"
{ meta t12 /work t12 '"cli"'; turn turnD gpt-5.6-sol high /work
  usage rd1 turnD 1000000 0 0 0; } > "$NL/rollout-nonl.jsonl"
usage "" turnD 1000000 0 0 0 | tr -d '\n' | sed 's/"response_id":"",//' >> "$NL/rollout-nonl.jsonl"
ncached() { USAGE_REPORT_CACHE="$NC" python3 "$SCRIPT" --provider codex --root "$NL" --all 2>&1; }
one=$(ncached); two=$(ncached); three=$(ncached)
ref=$(USAGE_REPORT_CACHE="" python3 "$SCRIPT" --provider codex --root "$NL" --all 2>&1)
[ "$one" = "$ref" ] && pass "an unterminated last record is reported, cached or not" || fail "unterminated record" "$one"
[ "$two" = "$one" ] && [ "$three" = "$one" ] && pass "and it is not folded into the stored state: three rescans, one bill" || fail "unterminated record grew on a rescan" "$three"

echo "== malformed rollout lines are skipped"
MD="$TMP/malformed"; mkdir -p "$MD"
{
    echo '[]'; echo '"a string"'; echo 'null'
    echo '{"type":"session_meta","payload":"not an object"}'
    echo '{"type":"turn_context","payload":["x"]}'
    echo '{"type":"token_usage_record","payload":{"usage":"not an object"}}'
    echo '{"type":"token_usage_record","timestamp":12345,"payload":{"response_id":"rx","usage":{"output_tokens":"1e5"}}}'
    meta m /work m '"cli"'
    turn  turnM gpt-5.6-terra medium /work
    usage rM turnM 1000000 0 0 0
} > "$MD/rollout-m.jsonl"
out=$(USAGE_REPORT_CACHE="" python3 "$SCRIPT" --provider codex --root "$MD" --all 2>&1); rc=$?
# rM: 1M in @ $2 = $2.00; rx: 1e5 out @ $12 = $1.20, its non-string timestamp read as none.
[ $rc = 0 ] && grep -q 'TOTAL  \$3.20' <<<"$out" && pass "wrong-shaped records are skipped; an exponent count and a numeric timestamp still fold" || fail "malformed rollout" "rc=$rc $out"

echo "== cache writes are billed at the published 1.25x of input"
CW="$TMP/cachewrite"; mkdir -p "$CW"
{
    meta w /work w '"cli"'
    turn  turnW gpt-5.6-terra medium /work
    usage rW turnW 0 0 1000000 0
} > "$CW/rollout-w.jsonl"
out=$(USAGE_REPORT_CACHE="" python3 "$SCRIPT" --provider codex --root "$CW" --all 2>&1)
# 1M cache write on terra: 1M x $2 x 1.25 = $2.50
grep -q 'TOTAL  \$2.50' <<<"$out" && pass "1M cache-write tokens on terra cost \$2.50" || fail "cache write multiplier" "$out"

echo "== every Codex family resolves to its own row, not a shorter key"
fam=$(python3 - "$SCRIPT" "$PLUGIN_ROOT/skills/usage-report/prices.json" <<'PY3'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("ur", sys.argv[1])
ur = importlib.util.module_from_spec(spec); spec.loader.exec_module(ur)
p = ur.load_prices()["codex"]
fams = json.load(open(sys.argv[2]))["codex"]["families"]
bad = [f"{k}->{p.family(k)}" for k in fams if p.family(k) != k]
bad += [f"{k}-x->{p.family(k + '-x')}" for k in fams if p.family(k + "-x") != k]
print(" ".join(bad) or "ok")
PY3
)
[ "$fam" = ok ] && pass "each family key, and a suffixed name, prices as itself" || fail "family resolution" "$fam"

summary "codex usage-report"
