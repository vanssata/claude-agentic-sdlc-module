#!/usr/bin/env bash
# usage-report.py: one API response is written as several transcript lines that
# repeat the same message id and usage — it must be counted once, not per line.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SCRIPT="$PLUGIN_ROOT/skills/usage-report/usage-report.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/proj/sess1/subagents"
export USAGE_REPORT_CACHE="$TMP/suite-cache.json"   # the corpus runs cached

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

echo "== --task: one task's window, tokens per runtime and the plan budget (R14)"
H="$TMP/home"; P="$TMP/project"; T=T-2026-09-01-001
mkdir -p "$H/.claude/claude-agentic" "$P/.ai/reports/$T"
python3 "$PLUGIN_ROOT/scripts/resolve-profile.py" max --fable yes --print agentic > "$H/.claude/claude-agentic/profile.json"
{
  printf '{"ts":"2026-09-01T10:00:00.000Z","task":"%s","event":"task_started","actor":"agent","runtime":"claude","data":{}}\n' "$T"
  printf '{"ts":"2026-09-01T10:05:00.000Z","task":"%s","event":"tier_set","actor":"agent","runtime":"claude","data":{"tier":"T2"}}\n' "$T"
  printf '{"ts":"2026-09-01T10:10:00.000Z","task":"%s","event":"tier_raised","actor":"agent","runtime":"claude","data":{"from":"T2","to":"T3"}}\n' "$T"
  printf '{"ts":"2026-09-01T11:00:00.000Z","task":"%s","event":"task_closed","actor":"agent","runtime":"claude","data":{}}\n' "$T"
} > "$P/.ai/reports/$T/events.jsonl"
before=$(sha256sum "$P/.ai/reports/$T/events.jsonl")
TR="$H/.claude/projects/$(printf '%s' "$P" | sed 's/[^A-Za-z0-9]/-/g')"; mkdir -p "$TR"
tline() {  # tline <ts> <id> <in> <out> <cache_read>
    printf '{"timestamp":"%s","message":{"id":"%s","model":"claude-opus-5","usage":{"input_tokens":%s,"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":%s}}}\n' "$@"
}
{ tline 2026-09-01T09:59:00Z before 5000000 0 0
  tline 2026-09-01T10:30:00Z in1 400000 100000 1500000
  tline 2026-09-01T10:45:00.5Z in2 0 0 400000
  tline 2026-09-01T11:30:00Z after 9000000 0 0; } > "$TR/sess.jsonl"
out=$(CLAUDE_CONFIG_DIR="$H/.claude" CODEX_HOME="$H/.codex" python3 "$SCRIPT" --task "$T" --project "$P" 2>&1)
printf '%s' "$out" | grep -q "^task $T tier T3 window 2026-09-01T10:00:00+00:00..2026-09-01T11:00:00+00:00" \
    && pass "the window runs from task_started to task_closed, the tier is the final one" || fail "task header" "$out"
printf '%s' "$out" | grep -q '^claude   tokens in 400,000 cache 1,900,000 out 100,000 total 2,400,000' \
    && pass "only the calls inside the window count, per provider" || fail "window tokens" "$out"
printf '%s' "$out" | grep -q 'budget max T3 6.0M · used 2.4M (40%)' \
    && pass "the runtime's plan budget for the final tier, and the share used" || fail "budget line" "$out"
[ "$(sha256sum "$P/.ai/reports/$T/events.jsonl")" = "$before" ] && pass "the journal is only read" || fail "the journal changed"
out=$(CLAUDE_CONFIG_DIR="$H/.claude" CODEX_HOME="$H/.codex" python3 "$SCRIPT" --task T-none --project "$P" 2>&1); rc=$?
[ $rc = 1 ] && printf '%s' "$out" | grep -q 'no journal for T-none' && pass "an unknown task exits 1 and says why" || fail "unknown task" "rc=$rc $out"

echo "== identifiers that are not strings do not take the report down with them"
# A transcript that writes message.id, requestId, response_id or a turn id as a
# number: main reports the file, so the cache's stored rows must too.
NS="$TMP/numid"; mkdir -p "$NS"
printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":12345,"model":"claude-sonnet-5","usage":{"input_tokens":0,"output_tokens":100000,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' > "$NS/a.jsonl"
nout=$(USAGE_REPORT_CACHE="$TMP/numid-cache.json" python3 "$SCRIPT" --root "$NS" 2>&1)
printf '%s' "$nout" | grep -q 'TOTAL  \$1.00' && pass "a numeric message id is reported, not a traceback" || fail "numeric message id" "$nout"
[ "$(USAGE_REPORT_CACHE="$TMP/numid-cache.json" python3 "$SCRIPT" --root "$NS" 2>&1)" = "$nout" ] \
    && pass "and the entry it wrote is served back, not rejected every run" || fail "numeric id, warm run"

echo "== a relative cache path resolves to one directory, not two (--task)"
# task_report chdirs into the project for the parsers and back again before the
# flush. If the path is resolved per call, the cache is read in one directory
# and written in another and never warms: the second run re-reads the
# transcript, which is what the unreadable file below turns into a failure.
Z="$TMP/relcwd"; mkdir -p "$Z"
( cd "$Z" && USAGE_REPORT_CACHE=relcache.json CLAUDE_CONFIG_DIR="$H/.claude" CODEX_HOME="$H/.codex" \
    python3 "$SCRIPT" --task "$T" --project "$P" > /dev/null 2>&1 )
warm=$( cd "$Z" && chmod 000 "$TR/sess.jsonl"
        USAGE_REPORT_CACHE=relcache.json CLAUDE_CONFIG_DIR="$H/.claude" CODEX_HOME="$H/.codex" \
          python3 "$SCRIPT" --task "$T" --project "$P" 2>&1; chmod 644 "$TR/sess.jsonl" )
printf '%s' "$warm" | grep -q '^claude   tokens in 400,000 cache 1,900,000 out 100,000 total 2,400,000' \
    && pass "the second --task run reads the cache it wrote, transcript untouched" \
    || fail "a relative cache path did not warm under --task" "$warm"
[ ! -e "$P/relcache.json" ] && pass "and nothing is dropped into the project directory" || fail "a cache file was written inside the project"

echo "== --budgets prints each installed plan's tables"
mkdir -p "$H/.codex/claude-agentic"
python3 "$PLUGIN_ROOT/scripts/resolve-profile.py" codex-plus --fable no --print agentic > "$H/.codex/claude-agentic/profile.json"
out=$(CLAUDE_CONFIG_DIR="$H/.claude" CODEX_HOME="$H/.codex" python3 "$SCRIPT" --budgets 2>&1)
printf '%s' "$out" | grep -q '^claude: Max (max)' && printf '%s' "$out" | grep -q '^codex: Plus (plus)' \
    && pass "both runtimes' plans are listed" || fail "budgets header" "$out"
printf '%s' "$out" | grep -q 'fan-out        1 agents, 1 on STRONG/EXPERT, serial' && pass "with the fan-out" || fail "fan-out line" "$out"
printf '%s' "$out" | grep -q 'tokens / task  T0 0.4M  T1 0.8M  T2 2M  T3 6M  T4 10M  T5 16M' && pass "and the token table" || fail "token table" "$out"
out=$(CLAUDE_CONFIG_DIR="$TMP/none" CODEX_HOME="$TMP/none" python3 "$SCRIPT" --budgets 2>&1); rc=$?
[ $rc = 1 ] && pass "no profile installed: exit 1" || fail "budgets without a profile: rc=$rc"

echo "== the incremental parse cache reads only what it has not read before"
# Every case here asserts the cached run against the same run with the cache
# off: the cache may change what is read, never what is reported.
C="$TMP/cache.json"; CP="$TMP/cproj"; mkdir -p "$CP"
cline() {  # cline <id> <out>
    printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"%s","model":"claude-sonnet-5","usage":{"input_tokens":0,"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' "$@"
}
cached() { USAGE_REPORT_CACHE="$C" python3 "$SCRIPT" --root "$CP" 2>&1; }
poison() {  # poison <state-json> [version]
    python3 - "$C" "$CP/s.jsonl" "$1" "${2:-2}" <<'PY2'
import json, os, sys
cache, path, state, version = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
st = os.stat(path)
json.dump({"version": version, "files": {os.path.abspath(path): {
    "kind": "claude", "mtime": st.st_mtime, "size": st.st_size,
    "offset": st.st_size, "head": "0" * 16,
    "state": json.loads(state)}}}, open(cache, "w"))
PY2
}
plain()  { USAGE_REPORT_CACHE="" python3 "$SCRIPT" --root "$CP" 2>&1; }

{ cline c1 100000; cline c2 100000; } > "$CP/s.jsonl"
cold=$(cached)
[ "$cold" = "$(plain)" ] && pass "a cold run reports what an uncached run reports" || fail "cold run differs" "$cold"
[ "$(jq -r '.files | to_entries[0].value | "\(.offset) \(.size)"' "$C")" = "$(stat -c '%s %s' "$CP/s.jsonl")" ] \
    && pass "the whole file is recorded as folded" || fail "offset/size not the file's size" "$(cat "$C" | head -c 200)"

chmod 000 "$CP/s.jsonl"
[ "$(cached)" = "$cold" ] && pass "an unchanged transcript is not read again at all" || fail "an unchanged transcript was re-read"
chmod 644 "$CP/s.jsonl"

cline c3 100000 >> "$CP/s.jsonl"
[ "$(cached)" = "$(plain)" ] && pass "an appended transcript is folded from the offset, not from zero" || fail "append" "$(cached)"

printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"c4","model":"claude-son' >> "$CP/s.jsonl"
[ "$(cached)" = "$(plain)" ] && pass "a half-written last line is not folded" || fail "partial line" "$(cached)"
printf 'net-5","usage":{"input_tokens":0,"output_tokens":100000,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' >> "$CP/s.jsonl"
[ "$(cached)" = "$(plain)" ] && pass "and is counted once once it is complete" || fail "completed line" "$(cached)"

# Grown *and* different from the first byte: without the head check this one
# resumes from the old offset and bills the old records again.
before=$(stat -c %s "$CP/s.jsonl")
{ cline dd1 200000; cline dd2 200000; cline dd3 200000; cline dd4 200000
  cline dd5 200000; cline dd6 200000; cline dd7 200000; } > "$CP/s.jsonl"
[ "$(stat -c %s "$CP/s.jsonl")" -gt "$before" ] && pass "the rewrite fixture is larger than what it replaced" || fail "rewrite fixture is not larger"
[ "$(cached)" = "$(plain)" ] && pass "a rewritten transcript is parsed from zero, not resumed" || fail "rewrite" "$(cached)"
cline e1 100000 > "$CP/s.jsonl"                                          # shrunk
[ "$(cached)" = "$(plain)" ] && pass "a truncated transcript is parsed from zero" || fail "truncate" "$(cached)"

rm "$CP/s.jsonl"; cline f1 100000 > "$CP/other.jsonl"; cached > /dev/null
[ "$(jq -r '.files | keys | length' "$C")" = 1 ] && pass "a transcript that is gone is dropped from the cache" || fail "stale entry kept" "$(cat "$C" | head -c 200)"

printf 'not json at all' > "$C"
[ "$(cached)" = "$(plain)" ] && pass "an unreadable cache is ignored, not fatal" || fail "corrupt cache" "$(cached)"
# A perfectly well-formed entry for this very file, under another version
# number and with numbers of its own: if the version is not checked, the report
# quotes them.
cline v1 100000 > "$CP/s.jsonl"
poison '{"n": 1, "recs": {"v9": {"*": ["2026-09-01", "2026-09-01T10:00:00Z", "claude-sonnet-5", 0, 900000, 0, 0]}}}' 999
[ "$(cached)" = "$(plain)" ] && pass "a cache written by another version is ignored" || fail "version mismatch" "$(cached)"

# --today reads a per-day slot out of the fold state; a cached state must serve
# it exactly as a fresh one does.
tline_at() {  # tline_at <ts> <id> <out>
    printf '{"timestamp":"%s","message":{"id":"%s","model":"claude-sonnet-5","usage":{"input_tokens":0,"output_tokens":%s,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}\n' "$@"
}
TD="$TMP/today"; mkdir -p "$TD"
now=$(date -u +%Y-%m-%dT%H:%M:%SZ); yst=$(date -u -d yesterday +%Y-%m-%dT%H:%M:%SZ)
tcached() { USAGE_REPORT_CACHE="$TMP/today-cache.json" python3 "$SCRIPT" --root "$TD" --today 2>&1; }
tplain()  { USAGE_REPORT_CACHE="" python3 "$SCRIPT" --root "$TD" --today 2>&1; }
# Yesterday's block is the larger one, so the per-day winner and the overall
# winner are different rows: a parser that keeps one winner per response and
# filters afterwards reports nothing for today, and $1.00 is what separates the
# two implementations. Comparing cached against uncached cannot: both would lose
# the slots together.
{ tline_at "$yst" straddle 300000; tline_at "$now" straddle 100000; } > "$TD/s.jsonl"
first=$(tcached)
printf '%s' "$first" | grep -q 'TOTAL  \$1.00' && pass "--today bills today's own winner, not the response's largest block" || fail "--today total" "$first"
[ "$first" = "$(tplain)" ] && pass "--today off a cold cache picks the same slot as an uncached run" || fail "--today cold" "$first"
[ "$(tcached)" = "$(tplain)" ] && pass "--today off a warm cache picks the same slot" || fail "--today warm" "$(tcached)"
tline_at "$now" later 100000 >> "$TD/s.jsonl"
[ "$(tcached)" = "$(tplain)" ] && pass "--today after an append picks the same slot" || fail "--today append" "$(tcached)"

# A transcript whose last line has no newline after it: the record still counts,
# and it counts once, cached or not.
NL="$TMP/nonl"; mkdir -p "$NL"
ncached() { USAGE_REPORT_CACHE="$TMP/nonl-cache.json" python3 "$SCRIPT" --root "$NL" 2>&1; }
nplain()  { USAGE_REPORT_CACHE="" python3 "$SCRIPT" --root "$NL" 2>&1; }
cline n1 100000 > "$NL/s.jsonl"
printf '{"timestamp":"2026-09-01T10:00:00Z","message":{"id":"n2","model":"claude-sonnet-5","usage":{"input_tokens":0,"output_tokens":100000,"cache_creation_input_tokens":0,"cache_read_input_tokens":0}}}' >> "$NL/s.jsonl"
out=$(ncached)
printf '%s' "$out" | grep -q 'TOTAL  \$2.00' && pass "a last line with no newline is still counted" || fail "unterminated last line" "$out"
[ "$(ncached)" = "$out" ] && [ "$(nplain)" = "$out" ] && pass "and counted once on a rescan, cached or not" || fail "unterminated last line, rescan" "$(ncached)"

# The other runtime's fold state must never be handed to this one.
X="$TMP/xprov"; mkdir -p "$X"; XC="$TMP/xprov-cache.json"
printf '{"type":"session_meta","timestamp":"2026-09-01T10:00:00Z","payload":{"id":"tx","session_id":"tx","cwd":"/w","source":"cli"}}\n' > "$X/rollout-x.jsonl"
printf '{"type":"token_usage_record","timestamp":"2026-09-01T10:00:02Z","payload":{"response_id":"rx","turn_id":"t","usage":{"input_tokens":1000000,"cached_input_tokens":0,"cache_write_input_tokens":0,"output_tokens":0}}}\n' >> "$X/rollout-x.jsonl"
USAGE_REPORT_CACHE="$XC" python3 "$SCRIPT" --provider codex --root "$X" --all > /dev/null 2>&1
out=$(USAGE_REPORT_CACHE="$XC" python3 "$SCRIPT" --provider claude --root "$X" --all 2>&1); rc=$?
[ $rc = 0 ] && ! printf '%s' "$out" | grep -qi 'Traceback' \
    && pass "a cache entry from the other runtime's fold is a miss, not a crash" || fail "cross-provider cache entry" "rc=$rc $out"
out=$(USAGE_REPORT_CACHE="$XC" python3 "$SCRIPT" --provider codex --root "$X" --all 2>&1)
printf '%s' "$out" | grep -q '^codex ' && pass "and the runtime that owns the directory still reports it" || fail "codex after a claude read" "$out"
# Two guards reject that entry, and the load-bearing one is the shape check:
# the two folds' states have disjoint key sets, so `kind` is the cheap first cut
# and cannot be pinned on its own by any state this program can produce. What is
# pinned here is that an entry records the fold that wrote it.
[ "$(jq -r '.files | to_entries[0].value.kind' "$XC")" = "codex" ] \
    && pass "an entry records the fold that wrote it" || fail "entry kind" "$(cat "$XC" | head -c 200)"

cline g1 100000 > "$CP/s.jsonl"      # the prune case above removed it
# Two layers, and each needs an entry the other one would not stop.
# 1. The wrong shape, on a file that has not changed: nothing is folded, so only
#    the shape check stands between the state and the report.
poison '{"n": 0, "recs": "not a dict"}'
[ "$(cached)" = "$(plain)" ] && pass "a wrong-shaped state is dropped before it is used, unchanged file and all" || fail "wrong-shaped state" "$(cached)"
# 2. The right shape, rubbish inside it, on a file the fold will not touch:
#    only a check on the records themselves stands between it and the report.
poison '{"n": 0, "recs": {"m": "not a bucket"}}'
[ "$(cached)" = "$(plain)" ] && pass "a state with rubbish in an untouched record is dropped too" || fail "unfoldable state" "$(cached)"
poison '{"n": 0, "recs": {"m": {"*": ["2026-09-01", "t", "claude-sonnet-5", 0, "not a count", 0, 0]}}}'
[ "$(cached)" = "$(plain)" ] && pass "and so is a record whose token counts are not numbers" || fail "bad row" "$(cached)"

rm -f "$C"; USAGE_REPORT_CACHE="$C" python3 "$SCRIPT" --root "$CP" --no-cache > /dev/null 2>&1
[ ! -e "$C" ] && pass "--no-cache neither reads nor writes the cache" || fail "--no-cache wrote the cache"

summary "usage-report"
