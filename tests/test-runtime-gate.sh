#!/usr/bin/env bash
# runtime-gate.py: the one gate behind both old names (R5). The old suites prove
# the behaviour through the shims; this one proves what is new — the AI_RUNTIME_GATE
# names winning over the old ones, the runtime read from the home the hook runs
# from, the one-time import of an old gate's state, and failing open.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SRC_GATE="$PLUGIN_ROOT/hooks/runtime-gate.py"
FIX="$PLUGIN_ROOT/tests/fixtures/codex-hooks"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
export HOME="$TMP/home"
unset CLAUDE_CONFIG_DIR CODEX_HOME CLAUDE_PROJECT_DIR CLAUDE_CODE_SUBAGENT_MODEL
for v in $(env | sed -n 's/^\(\(AI_RUNTIME_GATE\|CLAUDE_FABLE_GATE\|CODEX_MODEL_GATE\)[A-Z_]*\)=.*/\1/p'); do unset "$v"; done

# One installed copy per runtime, where install.sh puts them.
CL="$HOME/.claude"; CX="$HOME/.codex"
mkdir -p "$CL/hooks" "$CL/agents" "$CX/hooks" "$CX/agents"
for d in "$CL/hooks" "$CX/hooks"; do cp "$PLUGIN_ROOT"/hooks/{runtime-gate,fable-gate,codex-model-gate}.py "$d/"; done
printf -- '---\nname: architect\nmodel: fable[1m]\n---\nbody\n' > "$CL/agents/architect.md"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$CX/agents" >/dev/null
printf 'model = "gpt-5.6-sol"\n\n[agents]\ndefault_subagent_model = "gpt-5.6-terra"\n' > "$CX/config.toml"

claude_call() { jq -nc '{hook_event_name:"PreToolUse",tool_name:"Agent",cwd:"/nonexistent",tool_input:{subagent_type:"architect",prompt:"p"}}' | "$@"; }
codex_call() { jq -r '.payload' "$FIX/30-agent-expert-launch.json" | sed "s|__ROOT__|$TMP|g" | "$@"; }

echo "== the runtime is the home the hook runs from"
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^inactive: model: fable' && pass "~/.claude/hooks -> Claude Code" || fail "claude copy should speak Fable"
python3 "$CX/hooks/runtime-gate.py" status | grep -q '^inactive: EXPERT agents run on gpt-6-astra' && pass "~/.codex/hooks -> Codex" || fail "codex copy should speak EXPERT"
python3 "$CL/hooks/runtime-gate.py" set 600 test >/dev/null
[ -f "$CL/state/runtime-gate.json" ] && pass "state in <home>/state/runtime-gate.json" || fail "claude state file missing"
[ ! -e "$CX/state/runtime-gate.json" ] && pass "and the other runtime's state is untouched" || fail "codex state written by a claude call"
out=$(claude_call python3 "$CL/hooks/runtime-gate.py")
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = opus ] && pass "a Fable launch is rewritten to opus" || fail "claude reroute" "$out"
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision')" = allow ] && pass "with allow, never deny" || fail "decision should be allow"
python3 "$CL/hooks/runtime-gate.py" clear >/dev/null
python3 "$CX/hooks/runtime-gate.py" set 600 test >/dev/null
out=$(codex_call python3 "$CX/hooks/runtime-gate.py")
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = gpt-5.6-sol ] && pass "an EXPERT spawn is rewritten to STRONG" || fail "codex reroute" "$out"
python3 "$CX/hooks/runtime-gate.py" clear >/dev/null

echo "== the shims name their runtime wherever they sit"
python3 "$PLUGIN_ROOT/hooks/codex-model-gate.py" status 2>/dev/null | grep -q '^inactive: EXPERT' \
    && pass "codex-model-gate.py outside ~/.codex is still Codex" || fail "codex shim lost its runtime"
python3 "$CX/hooks/fable-gate.py" status | grep -q '^inactive: model: fable' \
    && pass "fable-gate.py inside ~/.codex is still Claude Code" || fail "fable shim lost its runtime"

echo "== new names win over the old ones"
out=$(AI_RUNTIME_GATE_STATE="$TMP/new.json" CLAUDE_FABLE_GATE_STATE="$TMP/old.json" python3 "$CL/hooks/runtime-gate.py" set 60 x)
[ -f "$TMP/new.json" ] && [ ! -e "$TMP/old.json" ] && pass "AI_RUNTIME_GATE_STATE before CLAUDE_FABLE_GATE_STATE" || fail "state name precedence"
CLAUDE_FABLE_GATE_STATE="$TMP/old.json" python3 "$CL/hooks/runtime-gate.py" set 60 x >/dev/null
[ -f "$TMP/old.json" ] && pass "the old name still works alone" || fail "old state name ignored"
AI_RUNTIME_GATE_STATE="$TMP/new.json" CLAUDE_FABLE_GATE_FALLBACK=sonnet AI_RUNTIME_GATE_FALLBACK=haiku \
    claude_call python3 "$CL/hooks/runtime-gate.py" | jq -e '.hookSpecificOutput.updatedInput.model == "haiku"' >/dev/null \
    && pass "AI_RUNTIME_GATE_FALLBACK before CLAUDE_FABLE_GATE_FALLBACK" || fail "fallback precedence"
out=$(AI_RUNTIME_GATE=off CLAUDE_FABLE_GATE=on AI_RUNTIME_GATE_STATE="$TMP/new.json" claude_call python3 "$CL/hooks/runtime-gate.py")
[ -z "$out" ] && pass "AI_RUNTIME_GATE=off disables it" || fail "AI_RUNTIME_GATE=off ignored" "$out"
out=$(CODEX_MODEL_GATE=off AI_RUNTIME_GATE_STATE="$TMP/new-cx.json" codex_call python3 "$CX/hooks/runtime-gate.py")
[ -z "$out" ] && pass "CODEX_MODEL_GATE=off still disables the Codex side" || fail "old off switch ignored" "$out"
CODEX_MODEL_GATE_STATE="$TMP/cx-old.json" CLAUDE_FABLE_GATE_STATE="$TMP/wrong.json" python3 "$CX/hooks/runtime-gate.py" set 60 x >/dev/null
[ -f "$TMP/cx-old.json" ] && [ ! -e "$TMP/wrong.json" ] && pass "each runtime reads only its own old names" || fail "old names crossed runtimes"

echo "== an old gate's state is imported once (I3)"
rm -rf "$CL/state"; mkdir -p "$CL/state"
jq -n --argjson u $(( $(date +%s) + 600 )) '{unavailable:{until:$u,reason:"rate_limit",source:"StopFailure"},last_fable_launch:1}' > "$CL/state/fable-gate.json"
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^active: Fable -> opus' && pass "a live fable-gate record carries over" || fail "fable-gate state not imported"
jq -e '.imported_from == "fable-gate.json" and (.unavailable.reason == "rate_limit") and (has("last_fable_launch") | not)' "$CL/state/runtime-gate.json" >/dev/null \
    && pass "only the outage record is imported, and the import is recorded" || fail "imported state wrong" "$(cat "$CL/state/runtime-gate.json")"
python3 "$CL/hooks/runtime-gate.py" clear >/dev/null
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^inactive' && pass "once: clear is not undone by a second import" || fail "the old record was imported again"
rm -rf "$CX/state"; mkdir -p "$CX/state"
jq -n --argjson u $(( $(date +%s) + 600 )) '{unavailable:{until:$u,reason:"model_unavailable",source:"SubagentStop"}}' > "$CX/state/codex-model-gate.json"
python3 "$CX/hooks/runtime-gate.py" status | grep -q '^active: gpt-6-astra -> gpt-5.6-sol' && pass "a live codex-model-gate record carries over" || fail "codex-model-gate state not imported"

echo "== quota: Claude Code from the statusline (R7)"
rm -rf "$CL/state" "$CL/claude-agentic"
NOW=$(date +%s)
jq -nc --argjson r $((NOW + 86400)) '{rate_limits:{seven_day:{used_percentage:42.5,resets_at:$r},five_hour:{used_percentage:7}}}' \
    | python3 "$CL/hooks/runtime-gate.py" statusline --then 'cat >/dev/null; echo LINE' | grep -qx LINE \
    && pass "the statusline still prints the user's own line" || fail "statusline output lost"
q=$(python3 "$CL/hooks/runtime-gate.py" quota --json)
printf '%s' "$q" | jq -e --argjson r $((NOW + 86400)) '.runtime == "claude" and .weekly_pct == 42.5 and .five_hour_pct == 7
        and .resets_at == $r and .source == "statusline" and .stale == false and (.seen_at > 0)
        and (keys == ["five_hour_pct","resets_at","runtime","seen_at","source","stale","weekly_pct"])' >/dev/null \
    && pass "quota --json has the seven keys from the statusline payload" || fail "claude quota shape" "$q"
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^inactive' && pass "42% used marks nothing" || fail "below the threshold must not mark"
python3 "$CL/hooks/runtime-gate.py" quota | grep -q 'weekly 42%, 5-hour 7%' && pass "quota prints one readable line" || fail "quota text" "$(python3 "$CL/hooks/runtime-gate.py" quota)"

mkdir -p "$CL/claude-agentic"; printf '{"plan":"max","fable":false}' > "$CL/claude-agentic/profile.json"
jq -nc '{rate_limits:{seven_day:{used_percentage:95}}}' | python3 "$CL/hooks/runtime-gate.py" statusline
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^inactive' && pass "fable: false — 95% records the quota but marks no Fable outage" || fail "Fable mark without Fable"
python3 "$CL/hooks/runtime-gate.py" quota --json | jq -e '.weekly_pct == 95' >/dev/null && pass "and the quota is still recorded" || fail "quota not recorded on a non-Fable plan"
printf '{"plan":"max","fable":true}' > "$CL/claude-agentic/profile.json"
jq -nc '{rate_limits:{seven_day:{used_percentage:95}}}' | python3 "$CL/hooks/runtime-gate.py" statusline
python3 "$CL/hooks/runtime-gate.py" status | grep -q '^active: Fable' && pass "fable: true — 95% marks Fable unavailable" || fail "Fable mark missing"
python3 "$CL/hooks/runtime-gate.py" clear >/dev/null

jq '.quota.seen_at = 1000' "$CL/state/runtime-gate.json" > "$TMP/s.json" && mv "$TMP/s.json" "$CL/state/runtime-gate.json"
python3 "$CL/hooks/runtime-gate.py" quota --json | jq -e '.stale == true' >/dev/null && pass "a reading older than 24 h is stale" || fail "old seen_at not stale"
jq --argjson n "$NOW" '.quota.seen_at = $n | .quota.resets_at = ($n - 60)' "$CL/state/runtime-gate.json" > "$TMP/s.json" && mv "$TMP/s.json" "$CL/state/runtime-gate.json"
python3 "$CL/hooks/runtime-gate.py" quota --json | jq -e '.stale == true' >/dev/null && pass "a reading past its reset is stale" || fail "past resets_at not stale"
rm -rf "$CL/state"
python3 "$CL/hooks/runtime-gate.py" quota --json | jq -e '.stale == true and .weekly_pct == null' >/dev/null && pass "no reading at all is stale" || fail "empty quota"

rm -rf "$CL/state"
jq -nc '{rate_limits:{seven_day:{used_percentage:30}}}' | CLAUDE_FABLE_GATE_STATE="$TMP/legacy-q.json" python3 "$CL/hooks/runtime-gate.py" statusline
[ ! -e "$TMP/legacy-q.json" ] && jq -e '.quota.weekly_pct == 30' "$CL/state/runtime-gate.json" >/dev/null \
    && pass "a state named by the old variable gets no quota; the ledger stays in runtime-gate.json" || fail "quota written into the legacy-named state"

echo "== quota: Codex from the newest rollout (R7)"
rm -rf "$CX/state"
old_day="$CX/sessions/2026/09/19"; new_day="$CX/sessions/2026/09/21"; mkdir -p "$old_day" "$new_day"
tc() {  # tc <weekly> <five_hour> <resets> <iso-timestamp>
    jq -nc --argjson w "$1" --argjson f "$2" --argjson r "$3" --arg t "$4" \
        '{timestamp:$t,type:"event_msg",payload:{type:"token_count",info:{},rate_limits:{limit_id:"codex",
          primary:{used_percent:$f,window_minutes:300,resets_at:($r - 3600)},
          secondary:{used_percent:$w,window_minutes:10080,resets_at:$r}}}}'
}
ISO=$(date -u -d "@$NOW" +%Y-%m-%dT%H:%M:%S.000Z)
{ tc 10 1 $((NOW + 9000)) "$ISO"; } > "$old_day/rollout-old.jsonl"
touch -d '2 days ago' "$old_day/rollout-old.jsonl"
{ tc 50 20 $((NOW + 9000)) "$ISO"; printf '{"type":"response_item","payload":{}}\n'; tc 73 36 $((NOW + 7200)) "$ISO"; printf '{"type":"event_msg","payload":{"type":"agent_message"}}\n'; } > "$new_day/rollout-new.jsonl"
q=$(python3 "$CX/hooks/runtime-gate.py" quota --json)
printf '%s' "$q" | jq -e --argjson r $((NOW + 7200)) --argjson n "$NOW" '.runtime == "codex" and .weekly_pct == 73 and .five_hour_pct == 36
        and .resets_at == $r and .source == "rollout" and .seen_at == $n and .stale == false' >/dev/null \
    && pass "the last token_count of the newest rollout: secondary is weekly, primary is 5-hour" || fail "codex quota" "$q"
tc 99 99 $((NOW + 7200)) "$ISO" >> "$new_day/rollout-new.jsonl"
python3 "$CX/hooks/runtime-gate.py" quota --json | jq -e '.weekly_pct == 73' >/dev/null \
    && pass "the rollout is read at most once a minute" || fail "rollout re-read within 60 s"
jq '.quota_checked_at = 0' "$CX/state/runtime-gate.json" > "$TMP/s.json" && mv "$TMP/s.json" "$CX/state/runtime-gate.json"
python3 "$CX/hooks/runtime-gate.py" quota --json | jq -e '.weekly_pct == 99' >/dev/null \
    && pass "and again once the minute is up" || fail "rollout not re-read after 60 s"
head -c 70000 /dev/zero | tr '\0' 'x' > "$new_day/rollout-pad.jsonl"; printf '\n' >> "$new_day/rollout-pad.jsonl"
tc 5 5 $((NOW + 7200)) "$ISO" > "$TMP/early.jsonl"; cat "$TMP/early.jsonl" "$new_day/rollout-pad.jsonl" > "$new_day/rollout-big.jsonl"; rm "$new_day/rollout-pad.jsonl"
jq '.quota_checked_at = 0' "$CX/state/runtime-gate.json" > "$TMP/s.json" && mv "$TMP/s.json" "$CX/state/runtime-gate.json"
python3 "$CX/hooks/runtime-gate.py" quota --json | jq -e '.weekly_pct == 99' >/dev/null \
    && pass "only the last 64 KB is read: a newest file with no token_count there changes nothing" || fail "read beyond 64 KB"
rm -rf "$CX/sessions" "$CX/state"
python3 "$CX/hooks/runtime-gate.py" quota --json | jq -e '.stale == true and .source == null' >/dev/null \
    && pass "no rollout: unknown and stale" || fail "codex quota without rollouts"

echo "== fails open, never denies"
for input in '' 'not json' '[]' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"x"}'; do
    for g in "$CL/hooks/runtime-gate.py" "$CX/hooks/runtime-gate.py"; do
        out=$(printf '%s' "$input" | AI_RUNTIME_GATE_STATE=/proc/cannot/write.json python3 "$g" 2>&1); rc=$?
        [ $rc -eq 0 ] && [ -z "$out" ] || fail "$(basename "$(dirname "$(dirname "$g")")"): input '$input' -> exit $rc: $out"
    done
done
pass "malformed input and an unwritable state exit 0 silently on both runtimes"
python3 "$CL/hooks/runtime-gate.py" wibble >/dev/null 2>&1; rc=$?
[ $rc -eq 2 ] && pass "an unknown command exits 2" || fail "expected exit 2, got $rc"
grep -q '"deny"' "$SRC_GATE" && fail "runtime-gate.py must never emit deny" || pass "the gate has no deny path"

echo "== the shims stay shims"
for s in fable-gate codex-model-gate; do
    n=$(wc -l < "$PLUGIN_ROOT/hooks/$s.py")
    [ "$n" -le 20 ] && pass "$s.py is $n lines" || fail "$s.py grew to $n lines"
    grep -q 'os.execv' "$PLUGIN_ROOT/hooks/$s.py" && pass "$s.py execs runtime-gate.py" || fail "$s.py does not exec"
done

summary "runtime-gate"
