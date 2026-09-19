#!/usr/bin/env bash
# codex-model-gate.py: an EXPERT agent must fall back to STRONG while the expert
# model cannot serve the account — and must NOT fall back because an agent gave a
# poor answer. Both halves are tested here; the second one is the reason the gate
# matches explicit capacity signals instead of the word "error".
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GATE="$PLUGIN_ROOT/hooks/codex-model-gate.py"
FIX="$PLUGIN_ROOT/tests/fixtures/codex-hooks"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# A scratch Codex home whose custom agents pin the same models the installer does.
HOME_DIR="$TMP/codex"
mkdir -p "$HOME_DIR/agents"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$HOME_DIR/agents" >/dev/null
printf 'model = "gpt-5.6-sol"\n\n[agents]\ndefault_subagent_model = "gpt-5.6-terra"\n' > "$HOME_DIR/config.toml"

STATE="$TMP/state.json"
gate() {  # gate [args...] < payload
    CODEX_HOME="$HOME_DIR" CODEX_MODEL_GATE_STATE="$STATE" "$GATE" "$@"
}
feed() {  # feed <fixture> — send one fixture payload to the gate, print stdout
    jq -r '.payload' "$FIX/$1" | sed "s|__ROOT__|$TMP|g" | gate
}
reset() { rm -f "$STATE"; }

echo "== an inactive gate stays out of the way"
reset
out=$(feed 30-agent-expert-launch.json)
[ -z "$out" ] && pass "an expert launch is not rewritten while the model is available" || fail "should be silent" "$out"
gate status | grep -q '^inactive' && pass "status reports inactive" || fail "status should report inactive"

echo "== an availability failure activates the gate"
reset
feed 32-subagent-stop-rate-limit.json >/dev/null
gate status | grep -q '^active: gpt-6-astra -> gpt-5.6-sol' && pass "a rate limit on the expert model activates the gate" \
    || fail "the gate should be active" "$(gate status)"
gate status | grep -q 'rate_limit' && pass "status names the reason" || fail "status should name the reason"
gate status | grep -q 'SubagentStop' && pass "status names the source" || fail "status should name the source"

echo "== while active, an expert launch is rewritten to STRONG"
out=$(feed 30-agent-expert-launch.json)
[ -n "$out" ] && pass "the gate answers the launch" || fail "the gate should answer"
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision')" = allow ] \
    && pass "the launch is allowed, not blocked" || fail "the decision should be allow" "$out"
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = "gpt-5.6-sol" ] \
    && pass "the model is rewritten to Sol" || fail "updatedInput.model should be gpt-5.6-sol" "$out"
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model_reasoning_effort')" = high \
  ] && pass "the effort is rewritten to high" || fail "updatedInput effort should be high" "$out"
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.agent_type')" = "ai-expert" ] \
    && pass "the rest of the spawn arguments are preserved" || fail "agent_type was lost" "$out"
printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext' | grep -q "is gpt-5.6-sol's, not gpt-6-astra's" \
    && pass "the agent is told whose answer it is about to give" || fail "the context should name both models" "$out"

echo "== a BALANCED launch is never rewritten"
out=$(feed 31-agent-balanced-launch.json)
[ -z "$out" ] && pass "an ai-discovery launch is untouched while the gate is active" || fail "should be silent" "$out"

echo "== repeated launches keep being rewritten"
out=$(feed 30-agent-expert-launch.json)
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = "gpt-5.6-sol" ] \
    && pass "a second launch is rewritten too" || fail "the gate should stay active" "$out"

echo "== a poor answer is not an availability failure"
reset
feed 33-subagent-stop-uncertain.json >/dev/null
gate status | grep -q '^inactive' && pass "confidence: uncertain does not activate the gate" || fail "the gate must not activate on a weak answer" "$(gate status)"

echo "== a failure attributed to another tier does not activate the gate"
reset
feed 34-subagent-stop-balanced-rate-limit.json >/dev/null
gate status | grep -q '^inactive' && pass "a Terra rate limit leaves the expert tier alone" || fail "the gate must not activate for another model" "$(gate status)"

echo "== the record expires"
reset
gate set 60 "test" >/dev/null  # expiry is simulated below; a 1 s record can lapse before status reads it
gate status | grep -q '^active' && pass "a manual record activates the gate" || fail "set should activate the gate"
python3 - "$STATE" <<'PY'
import json, sys, time
path = sys.argv[1]
data = json.load(open(path))
data["unavailable"]["until"] = int(time.time()) - 5
json.dump(data, open(path, "w"))
PY
gate status | grep -q '^inactive' && pass "an expired record stops applying" || fail "the record should have expired"
out=$(feed 30-agent-expert-launch.json)
[ -z "$out" ] && pass "an expert launch runs on the expert model again after expiry" || fail "should be silent after expiry" "$out"
reset
stored=$(CODEX_HOME="$HOME_DIR" CODEX_MODEL_GATE_STATE="$STATE" python3 - "$GATE" <<'PY'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("gate", sys.argv[1])
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
gate.mark(2000000000.9, "test", "test")
print(json.load(open(gate.STATE))["unavailable"]["until"])
PY
)
[ "$stored" = 2000000001 ] && pass "a fractional expiry is rounded up, never ending the record early" \
    || fail "until should round up to 2000000001" "$stored"

echo "== clear re-enables the expert model early"
gate set 3600 "manual" >/dev/null
gate clear | grep -q cleared && pass "clear reports what it did" || fail "clear should report"
gate status | grep -q '^inactive' && pass "clear deactivates the gate" || fail "clear should deactivate"

echo "== an explicit model on the spawn wins over the agent file"
reset
gate set 3600 "manual" >/dev/null
out=$(jq -nc --arg r "$TMP" '{hook_event_name:"PreToolUse",tool_name:"Agent",cwd:$r,
      tool_input:{agent_type:"ai-discovery",model:"gpt-6-astra",prompt:"x"}}' | gate)
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model')" = "gpt-5.6-sol" ] \
    && pass "an explicit expert model on a cheap agent is still gated" || fail "an explicit model must be honoured" "$out"
out=$(jq -nc --arg r "$TMP" '{hook_event_name:"PreToolUse",tool_name:"Agent",cwd:$r,
      tool_input:{agent_type:"ai-expert",model:"gpt-5.6-terra",prompt:"x"}}' | gate)
[ -z "$out" ] && pass "an explicit cheap model on the expert agent is left alone" || fail "should be silent" "$out"

echo "== context-only mode explains without rewriting"
out=$(CODEX_MODEL_GATE_MODE=context bash -c "jq -r '.payload' '$FIX/30-agent-expert-launch.json' | sed 's|__ROOT__|$TMP|g' | CODEX_HOME='$HOME_DIR' CODEX_MODEL_GATE_STATE='$STATE' '$GATE'")
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput // "none"')" = none ] \
    && pass "context mode does not rewrite the spawn arguments" || fail "context mode should not rewrite" "$out"
printf '%s' "$out" | jq -e '.hookSpecificOutput.additionalContext' >/dev/null \
    && pass "context mode still explains the fallback" || fail "context mode should explain"

echo "== the gate can be turned off entirely"
out=$(CODEX_MODEL_GATE=off bash -c "jq -r '.payload' '$FIX/30-agent-expert-launch.json' | sed 's|__ROOT__|$TMP|g' | CODEX_HOME='$HOME_DIR' CODEX_MODEL_GATE_STATE='$STATE' '$GATE'")
[ -z "$out" ] && pass "CODEX_MODEL_GATE=off disables the rewrite" || fail "off should disable the gate" "$out"

echo "== malformed input fails open"
for bad in "" "not json" "[]" '{"hook_event_name":"PreToolUse"}' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"oops"}' \
           '{"hook_event_name":"SubagentStop"}' '{"hook_event_name":"Nonsense","tool_name":"Agent"}'; do
    out=$(printf '%s' "$bad" | gate 2>&1); rc=$?
    if [ $rc -eq 0 ] && [ -z "$out" ]; then
        pass "fails open on: ${bad:-<empty>}"
    else
        fail "should fail open on: ${bad:-<empty>}" "exit $rc, output: $out"
    fi
done

echo "== an unwritable state directory does not break a spawn"
out=$(CODEX_HOME="$HOME_DIR" CODEX_MODEL_GATE_STATE=/proc/cannot/write.json \
      bash -c "jq -r '.payload' '$FIX/30-agent-expert-launch.json' | sed 's|__ROOT__|$TMP|g' | '$GATE'" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "a state write failure still exits 0" || fail "should exit 0" "$out"

echo "== the CLI reports usage for an unknown command"
out=$(gate wibble 2>&1); rc=$?
[ $rc -eq 2 ] && pass "an unknown command exits 2" || fail "expected exit 2" "$out"
printf '%s' "$out" | grep -q 'usage:' && pass "it prints usage" || fail "should print usage"

summary "codex-model-gate"
