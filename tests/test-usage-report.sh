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

summary "usage-report"
