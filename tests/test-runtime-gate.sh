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

echo "== budgets: EXPERT asks (R8)"
rm -rf "$CL/state" "$CX/state"
RESOLVE="$PLUGIN_ROOT/scripts/resolve-profile.py"
python3 "$RESOLVE" max --fable yes --print agentic > "$CL/claude-agentic/profile.json"
python3 "$RESOLVE" codex-plus --fable no --print agentic > "$CX/claude-agentic/profile.json" 2>/dev/null \
    || { mkdir -p "$CX/claude-agentic"; python3 "$RESOLVE" codex-plus --fable no --print agentic > "$CX/claude-agentic/profile.json"; }
PROJ="$TMP/proj"; mkdir -p "$PROJ/.ai"
python3 "$PLUGIN_ROOT/skills/ai-task/state.py" --root "$PROJ" init --goal g --workflow feature >/dev/null 2>&1
TASK=$(jq -r .task_id "$PROJ/.ai/state/current.json")
launch() {  # launch <home-hook> <subagent_type> [session] [model] -> stdout
    jq -nc --arg a "$2" --arg s "${3:-s1}" --arg m "${4:-}" --arg c "$PROJ" \
        '{hook_event_name:"PreToolUse",tool_name:"Agent",session_id:$s,cwd:$c,
          tool_input:({subagent_type:$a,prompt:"p"} + (if $m == "" then {} else {model:$m} end))}' | python3 "$1"
}
decision() { jq -r '.hookSpecificOutput.permissionDecision // "none"' 2>/dev/null <<<"${1:-{\}}"; }
out=$(launch "$CL/hooks/runtime-gate.py" ai-expert)
[ "$(decision "$out")" = ask ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("EXPERT agents run only when asked on Max")' >/dev/null \
    && pass "max: an EXPERT launch asks, with the reason" || fail "max EXPERT should ask" "$out"
out=$(launch "$CL/hooks/runtime-gate.py" ai-reviewer)
[ -z "$out" ] && pass "max: a STRONG launch within the fan-out goes through silently" || fail "STRONG launch should be silent" "$out"
out=$(AI_UNATTENDED=1 launch "$CL/hooks/runtime-gate.py" architect)
[ "$(decision "$out")" = none ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | test("unattended")' >/dev/null \
    && pass "AI_UNATTENDED=1: allowed and explained, never asked" || fail "unattended EXPERT" "$out"
python3 "$RESOLVE" max20 --fable yes --print agentic > "$CL/claude-agentic/profile.json"
rm -rf "$CL/state"
o1=$(launch "$CL/hooks/runtime-gate.py" ai-expert); o2=$(launch "$CL/hooks/runtime-gate.py" ai-expert); o3=$(launch "$CL/hooks/runtime-gate.py" ai-expert)
[ -z "$o1$o2" ] && pass "max20: two EXPERT launches in a task need no question" || fail "max20 first two should be silent" "$o1$o2"
[ "$(decision "$o3")" = ask ] && printf '%s' "$o3" | jq -e --arg t "$TASK" '.hookSpecificOutput.permissionDecisionReason | test($t)' >/dev/null \
    && pass "max20: the third asks, naming the task" || fail "max20 third EXPERT should ask" "$o3"
jq -e --arg t "$TASK" '.expert_launches[$t] == 3' "$CL/state/runtime-gate.json" >/dev/null && pass "the count is keyed by the task id" || fail "expert_launches not keyed by task"
out=$(jq -r '.payload' "$FIX/30-agent-expert-launch.json" | sed "s|__ROOT__|$TMP|g" | python3 "$CX/hooks/runtime-gate.py")
[ "$(decision "$out")" != ask ] && [ "$(decision "$out")" != deny ] \
    && printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | test("Codex cannot ask")' >/dev/null \
    && pass "codex-plus: an EXPERT spawn is allowed and explained, never asked" || fail "codex EXPERT budget" "$out"

echo "== budgets: running agents and the fan-out (R19)"
python3 "$RESOLVE" max --fable yes --print agentic > "$CL/claude-agentic/profile.json"
rm -rf "$CL/state"
sub() {  # sub <hook> <Start|Stop> <agent_type> <agent_id> [session]
    jq -nc --arg e "Subagent$2" --arg a "$3" --arg i "$4" --arg s "${5:-s1}" \
        '{hook_event_name:$e,session_id:$s,agent_type:$a,agent_id:$i}' | python3 "$1"
}
G="$CL/hooks/runtime-gate.py"
sub "$G" Start Explore a1; sub "$G" Start log-reader a2; sub "$G" Start ai-tester a3
out=$(launch "$G" ai-indexer)
[ "$(decision "$out")" = ask ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("3 agent\\(s\\) already running, the Max fan-out is 3")' >/dev/null \
    && pass "max: a fourth parallel launch asks" || fail "fan-out ask" "$out"
out=$(launch "$G" ai-indexer s2)
[ -z "$out" ] && pass "running agents are counted per session" || fail "another session should not count" "$out"
sub "$G" Stop Explore a1
out=$(launch "$G" ai-indexer)
[ -z "$out" ] && pass "a SubagentStop frees a slot" || fail "stop did not free a slot" "$out"
sub "$G" Stop log-reader a2; sub "$G" Stop ai-tester a3
sub "$G" Start ai-reviewer r1; sub "$G" Start ai-security r2
out=$(launch "$G" ai-reviewer)
[ "$(decision "$out")" = ask ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.permissionDecisionReason | test("STRONG/EXPERT")' >/dev/null \
    && pass "max: a third STRONG agent asks (max_parallel_on_strong 2)" || fail "on-strong ask" "$out"
out=$(launch "$G" ai-reviewer s1 sonnet)
[ -z "$out" ] && pass "the same agent with model: sonnet counts as BALANCED and goes through" || fail "explicit model should decide the tier" "$out"
jq '.running_agents.s1 |= map(.started_at = 1000)' "$CL/state/runtime-gate.json" > "$TMP/s.json" && mv "$TMP/s.json" "$CL/state/runtime-gate.json"
out=$(launch "$G" ai-reviewer)
[ -z "$out" ] && pass "an entry older than the agent TTL (a lost SubagentStop) no longer counts" || fail "stale entries still counted" "$out"
rm -rf "$CX/state"
sub "$CX/hooks/runtime-gate.py" Start ai-indexer c1 cs
out=$(launch "$CX/hooks/runtime-gate.py" Explore cs)
[ "$(decision "$out")" = none ] && printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext | test("fan-out is 1 and serial")' >/dev/null \
    && pass "codex-plus: a second parallel launch is allowed and explained" || fail "codex fan-out" "$out"
sub "$CX/hooks/runtime-gate.py" Stop ai-indexer c1 cs
jq -e '.running_agents | has("cs") | not' "$CX/state/runtime-gate.json" >/dev/null && pass "codex SubagentStop removes the entry too" || fail "codex stop"

echo "== model_fallback is journaled on a rewrite (R9)"
ln -sfn "$PLUGIN_ROOT/skills" "$CL/skills"          # where install.sh puts state.py
python3 "$RESOLVE" max --fable yes --print agentic > "$CL/claude-agentic/profile.json"
rm -rf "$CL/state"; python3 "$G" set 600 rate_limit >/dev/null
EV="$PROJ/.ai/reports/$TASK/events.jsonl"
before=$(grep -c '"model_fallback"' "$EV" 2>/dev/null || true)
out=$(AI_UNATTENDED=1 launch "$G" architect)
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = opus ] && pass "architect rerouted to opus" || fail "reroute missing" "$out"
after=$(grep -c '"model_fallback"' "$EV")
[ $((after - before)) = 1 ] && pass "exactly one model_fallback line" || fail "expected one model_fallback line, got $((after - before))"
tail -1 "$EV" | jq -e '.actor == "hook" and .data.agent == "architect" and .data.from == "fable[1m]" and .data.to == "opus" and .data.reason == "rate_limit"' >/dev/null \
    && pass "actor hook, {agent, from, to, reason}" || fail "model_fallback line" "$(tail -1 "$EV")"
out=$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Agent",session_id:"s9",cwd:"/nonexistent",tool_input:{subagent_type:"architect",prompt:"p"}}' | AI_UNATTENDED=1 python3 "$G")
[ "$(grep -c '"model_fallback"' "$EV")" = "$after" ] && pass "no task at cwd, no line" || fail "a line was written for another cwd"
mkdir -p "$TMP/broken/skills/ai-task"; printf 'import sys\nsys.exit(3)\n' > "$TMP/broken/skills/ai-task/state.py"
out=$(CLAUDE_CONFIG_DIR="$TMP/broken" AI_RUNTIME_GATE_STATE="$CL/state/runtime-gate.json" AI_UNATTENDED=1 launch "$G" architect s1 'fable[1m]'); rc=$?
[ $rc = 0 ] && [ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = opus ] \
    && pass "a broken state.py: the launch is still rerouted, exit 0" || fail "broken state.py broke the gate" "rc=$rc $out"
python3 "$G" clear >/dev/null

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

echo "== parallel hooks do not lose each other's writes (WP5 review)"
LS="$TMP/lock-state.json"; rm -f "$LS"
ev() { jq -nc --arg e "$1" --arg id "$2" '{hook_event_name:$e,session_id:"par",agent_id:$id,agent_type:"Explore",cwd:"/nonexistent"}' \
       | AI_RUNTIME_GATE_STATE="$LS" python3 "$CL/hooks/runtime-gate.py" >/dev/null; }
for i in $(seq 1 20); do ev SubagentStart "a$i" & done; wait
n=$(jq '.running_agents.par | length' "$LS")
[ "$n" = 20 ] && pass "20 parallel SubagentStart record 20 agents" || fail "parallel starts recorded $n of 20"
for i in $(seq 1 20); do ev SubagentStop "a$i" & done
AI_RUNTIME_GATE_STATE="$LS" python3 "$CL/hooks/runtime-gate.py" set 600 rate_limit >/dev/null & wait
[ "$(jq '.running_agents.par // [] | length' "$LS")" = 0 ] && pass "20 parallel SubagentStop leave none running" || fail "stops left $(jq -c '.running_agents' "$LS")"
jq -e '.unavailable.until' "$LS" >/dev/null && pass "an outage recorded during the stops survives" || fail "outage record lost in the race"

echo "== settings that do not parse or do not fit keep the default"
out=$(AI_RUNTIME_GATE_AGENT_TTL=30m AI_RUNTIME_GATE_STATE="$LS" python3 "$CL/hooks/runtime-gate.py" status 2>&1); rc=$?
[ $rc -eq 0 ] && pass "AGENT_TTL=30m does not crash the gate" || fail "bad number crashed (rc $rc)" "$out"
python3 "$CL/hooks/runtime-gate.py" set 600 test >/dev/null
out=$(AI_RUNTIME_GATE_FALLBACK=gpt-5.6-sol claude_call python3 "$CL/hooks/runtime-gate.py")
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = opus ] \
    && pass "a Codex model in the shared FALLBACK is ignored by Claude" || fail "Claude took a Codex fallback" "$out"
out=$(AI_RUNTIME_GATE_CLAUDE_FALLBACK=sonnet AI_RUNTIME_GATE_FALLBACK=haiku claude_call python3 "$CL/hooks/runtime-gate.py")
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = sonnet ] \
    && pass "AI_RUNTIME_GATE_CLAUDE_FALLBACK wins over the shared name" || fail "per-runtime name ignored" "$out"
python3 "$CL/hooks/runtime-gate.py" clear >/dev/null

echo "== the shims stay shims"
for s in fable-gate codex-model-gate; do
    n=$(wc -l < "$PLUGIN_ROOT/hooks/$s.py")
    [ "$n" -le 20 ] && pass "$s.py is $n lines" || fail "$s.py grew to $n lines"
    grep -q 'os.execv' "$PLUGIN_ROOT/hooks/$s.py" && pass "$s.py execs runtime-gate.py" || fail "$s.py does not exec"
done

summary "runtime-gate"
