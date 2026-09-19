#!/usr/bin/env bash
# fable-gate.py: records Fable unavailability from StopFailure / PostToolUse /
# the statusline, rewrites model: fable -> opus on PreToolUse:Agent while the
# record lives, and fails open. Then the installer: the gate is registered only
# on a Fable install, and a later non-Fable install strips it again.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GATE="$PLUGIN_ROOT/hooks/fable-gate.py"
INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# Isolate from the developer's own ~/.claude: agents, state and env.
export HOME="$TMP/home" CLAUDE_CONFIG_DIR="$TMP/home/.claude"
export CLAUDE_FABLE_GATE_STATE="$TMP/state/fable-gate.json"
unset CLAUDE_PROJECT_DIR CLAUDE_FABLE_GATE CLAUDE_CODE_SUBAGENT_MODEL
mkdir -p "$CLAUDE_CONFIG_DIR/agents" "$TMP/project/.claude/agents"
printf -- '---\nname: ai-expert\n# model: pinned\nmodel: fable\neffort: xhigh\n---\nbody\n' > "$CLAUDE_CONFIG_DIR/agents/ai-expert.md"
printf -- '---\nname: ai-reviewer\nmodel: opus\neffort: high\n---\nbody\n' > "$CLAUDE_CONFIG_DIR/agents/ai-reviewer.md"
printf -- '---\nname: architect\nmodel: opus\n---\nbody\n' > "$CLAUDE_CONFIG_DIR/agents/architect.md"
printf -- '---\nname: architect\nmodel: fable\n---\nproject override\n' > "$TMP/project/.claude/agents/architect.md"

now() { date +%s; }
reset_state() { rm -f "$CLAUDE_FABLE_GATE_STATE"; }
set_marker() { mkdir -p "$(dirname "$CLAUDE_FABLE_GATE_STATE")"; jq -n --argjson u "$1" '{unavailable:{until:$u,reason:"rate_limit",source:"test"}}' > "$CLAUDE_FABLE_GATE_STATE"; }
marker_active() { python3 "$GATE" status | grep -q '^active'; }

agent_call() {  # agent_call <tool_input-json> [cwd] [transcript] -> hook stdout
    jq -nc --argjson i "$1" --arg c "${2:-$TMP/elsewhere}" --arg t "${3:-}" \
        '{hook_event_name:"PreToolUse",tool_name:"Agent",cwd:$c,tool_input:$i}
         + (if $t == "" then {} else {transcript_path:$t} end)' | python3 "$GATE"
}
routed_model() {  # routed_model <tool_input-json> [cwd] [transcript] -> the model after the hook, or "unchanged"
    local out; out=$(agent_call "$@")
    if [ -z "$out" ]; then echo unchanged; else printf '%s' "$out" | jq -r '.hookSpecificOutput.updatedInput.model // "malformed"'; fi
}
expect_route() {  # expect_route <expected> <tool_input-json> <label> [cwd] [transcript]
    local got; got=$(routed_model "$2" "${4:-}" "${5:-}")
    [ "$got" = "$1" ] && pass "$3" || fail "$3" "expected $1, got $got"
}
stop_failure() {  # stop_failure <error> [extra-json]
    local extra='{}'; [ $# -ge 2 ] && extra="$2"
    jq -nc --arg e "$1" --argjson x "$extra" \
        '{hook_event_name:"StopFailure",cwd:"/nowhere",error:$e} + $x' | python3 "$GATE"
}

echo "== PreToolUse:Agent with no record"
reset_state
expect_route unchanged '{"subagent_type":"ai-expert","prompt":"p","description":"d"}' "a pinned Fable agent runs on Fable while Fable is available"
expect_route unchanged '{"subagent_type":"general-purpose","model":"fable","prompt":"p"}' "an explicit model: fable is left alone"

echo "== PreToolUse:Agent while Fable is unavailable"
set_marker $(( $(now) + 600 ))
expect_route opus '{"subagent_type":"ai-expert","prompt":"p","description":"d"}' "ai-expert (frontmatter model: fable) is routed to opus"
expect_route opus '{"subagent_type":"general-purpose","model":"fable","prompt":"p"}' "an explicit model: fable is routed to opus"
expect_route opus '{"subagent_type":"x","model":"fable[1m]","prompt":"p"}' "fable[1m] is routed too"
expect_route unchanged '{"subagent_type":"ai-reviewer","prompt":"p"}' "an Opus agent is untouched"
expect_route unchanged '{"subagent_type":"Explore","model":"sonnet","prompt":"p"}' "a Sonnet agent is untouched"
expect_route unchanged '{"subagent_type":"fork","model":"fable","prompt":"p"}' "a fork is untouched (it ignores model)"
expect_route unchanged '{"subagent_type":"architect","prompt":"p"}' "user-level architect (opus) is untouched"
expect_route opus '{"subagent_type":"architect","prompt":"p"}' "a project-level architect pinned to fable wins over the user one, and is routed" "$TMP/project"

echo "== CLAUDE_CODE_SUBAGENT_MODEL: last since Claude Code 2.1.251, first before it"
transcript() {  # transcript <claude-code-version> -> path of a transcript written by that version
    printf '%s\n' "{\"type\":\"user\",\"version\":\"$1\",\"message\":{\"content\":\"the \\\"version\\\":\\\"9.9.9\\\" in a message is not one\"}}" \
        '{"type":"summary"}' > "$TMP/transcript-$1.jsonl"
    echo "$TMP/transcript-$1.jsonl"
}
CLAUDE_CODE_SUBAGENT_MODEL=fable expect_route opus '{"subagent_type":"no-definition","prompt":"p"}' "an agent with no definition falls back to CLAUDE_CODE_SUBAGENT_MODEL"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "a frontmatter model: fable outranks CLAUDE_CODE_SUBAGENT_MODEL=sonnet, and is routed"
CLAUDE_CODE_SUBAGENT_MODEL=fable expect_route unchanged '{"subagent_type":"no-definition","model":"sonnet","prompt":"p"}' "the call's own model: sonnet outranks CLAUDE_CODE_SUBAGENT_MODEL=fable, and stays on Sonnet"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route opus '{"subagent_type":"no-definition","model":"fable","prompt":"p"}' "the call's own model: fable outranks CLAUDE_CODE_SUBAGENT_MODEL=sonnet, and is routed"
CLAUDE_CODE_SUBAGENT_MODEL=fable expect_route unchanged '{"subagent_type":"ai-reviewer","prompt":"p"}' "a frontmatter model: opus outranks CLAUDE_CODE_SUBAGENT_MODEL=fable"
for v in 2.1.251 2.1.276 2.2.0 3.0.0; do
    CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "Claude Code $v: the frontmatter outranks the variable" "" "$(transcript "$v")"
    CLAUDE_CODE_SUBAGENT_MODEL=fable expect_route unchanged '{"subagent_type":"x","model":"sonnet","prompt":"p"}' "Claude Code $v: the call's own model outranks the variable" "" "$(transcript "$v")"
done
for v in 2.1.219 2.1.250 2.0.76 1.0.128; do
    CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route unchanged '{"subagent_type":"ai-expert","prompt":"p"}' "Claude Code $v: the variable outranks the frontmatter, so nothing runs on Fable" "" "$(transcript "$v")"
    CLAUDE_CODE_SUBAGENT_MODEL=fable expect_route opus '{"subagent_type":"x","model":"sonnet","prompt":"p"}' "Claude Code $v: the variable outranks the call's own model" "" "$(transcript "$v")"
done
CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "an unreadable transcript means the current order" "" "$TMP/no-such-transcript.jsonl"
printf 'not json\n{"version":"garbage"}\n{"version":7}\n' > "$TMP/transcript-bad.jsonl"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "a transcript with no usable version means the current order" "" "$TMP/transcript-bad.jsonl"
expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "with the variable unset an old Claude Code changes nothing" "" "$(transcript 2.1.219)"

out=$(agent_call '{"subagent_type":"ai-expert","prompt":"keep me","description":"keep","run_in_background":true}')
printf '%s' "$out" | jq -e '.hookSpecificOutput.updatedInput | .prompt == "keep me" and .description == "keep" and .run_in_background == true and .subagent_type == "ai-expert"' >/dev/null \
    && pass "every other Agent input field is preserved" || fail "updatedInput lost fields" "$out"
printf '%s' "$out" | jq -e '.hookSpecificOutput | .hookEventName == "PreToolUse" and .permissionDecision == "allow" and (.additionalContext | test("opus")) and (.permissionDecisionReason | test("rate_limit"))' >/dev/null \
    && pass "the output is a well-formed PreToolUse decision that tells Claude and the user why" || fail "malformed PreToolUse output" "$out"

out=$(jq -nc '{hook_event_name:"PreToolUse",tool_name:"Read",tool_input:{file_path:"/x",model:"fable"}}' | python3 "$GATE")
[ -z "$out" ] && pass "a non-Agent tool is ignored" || fail "a non-Agent tool should be ignored" "$out"
CLAUDE_FABLE_GATE=off expect_route unchanged '{"subagent_type":"ai-expert","prompt":"p"}' "CLAUDE_FABLE_GATE=off disables the rewrite"
CLAUDE_FABLE_GATE_FALLBACK=sonnet expect_route sonnet '{"subagent_type":"ai-expert","prompt":"p"}' "the fallback model is configurable"

echo "== the record expires on its own"
set_marker $(( $(now) - 1 ))
expect_route unchanged '{"subagent_type":"ai-expert","prompt":"p"}' "an expired record no longer routes Fable agents"
reset_state
stored=$(python3 - "$GATE" <<'PY'
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("gate", sys.argv[1])
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
gate.mark(2000000000.9, "test", "test")
print(json.load(open(gate.STATE))["unavailable"]["until"])
PY
)
[ "$stored" = 2000000001 ] && pass "a fractional expiry is rounded up, never ending the record early" \
    || fail "until should round up to 2000000001" "$stored"

echo "== StopFailure records unavailability"
reset_state
stop_failure rate_limit '{"last_assistant_message":"API Error: 429 rate limit for claude-fable-5-1"}'
marker_active && pass "a rate_limit that names Fable records it" || fail "rate_limit naming fable should record"
expect_route opus '{"subagent_type":"ai-expert","prompt":"p"}' "the next Fable agent is routed to opus"
until=$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")  # rounded up, so up to TTL + 1 s
[ $(( until - $(now) )) -gt 3000 ] && [ $(( until - $(now) )) -le 3601 ] && pass "rate_limit holds for CLAUDE_FABLE_GATE_TTL (1h)" || fail "rate_limit ttl wrong: $(( until - $(now) ))s"

reset_state
stop_failure model_not_found '{"agent_type":"ai-expert"}'
marker_active && pass "model_not_found in an agent pinned to fable records it" || fail "model_not_found for ai-expert should record"
until=$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")
[ $(( until - $(now) )) -gt 20000 ] && pass "model_not_found holds longer (6h)" || fail "model_not_found ttl wrong"

reset_state
printf '%s\n' '{"message":{"model":"claude-sonnet-5"}}' '{"message":{"model":"claude-fable-5-1"}}' > "$TMP/transcript.jsonl"
stop_failure rate_limit "$(jq -nc --arg p "$TMP/transcript.jsonl" '{transcript_path:$p}')"
marker_active && pass "a rate_limit in a transcript last served by Fable records it" || fail "transcript attribution failed"

reset_state
agent_call '{"subagent_type":"ai-expert","prompt":"p"}' >/dev/null
stop_failure rate_limit
marker_active && pass "a rate_limit right after a Fable agent launched is attributed to it" || fail "launch-window attribution failed"

reset_state
stop_failure rate_limit '{"last_assistant_message":"429 for claude-sonnet-5"}'
marker_active && fail "a Sonnet rate limit must not disable Fable" || pass "a rate_limit with no sign of Fable is ignored"
jq -n --argjson t $(( $(now) - 3600 )) '{last_fable_launch:$t}' > "$CLAUDE_FABLE_GATE_STATE"
stop_failure rate_limit
marker_active && fail "an old Fable launch must not be blamed" || pass "a Fable launch outside the window is not blamed"
reset_state
stop_failure authentication_failed '{"last_assistant_message":"fable"}'
marker_active && fail "authentication errors are account-wide" || pass "authentication_failed does not route to Opus (Opus would fail too)"
stop_failure overloaded '{"last_assistant_message":"fable overloaded"}'
marker_active && fail "overload is fallbackModel's job" || pass "overloaded is left to fallbackModel"

set_marker $(( $(now) + 20000 ))
stop_failure rate_limit '{"last_assistant_message":"fable 429"}'
[ "$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")" -gt $(( $(now) + 19000 )) ] \
    && pass "a shorter record never shortens a longer one" || fail "a later rate_limit shortened the record"

echo "== PostToolUse:Agent records a fallback off Fable"
reset_state
post() { jq -nc --argjson i "$1" --argjson r "$2" '{hook_event_name:"PostToolUse",tool_name:"Agent",cwd:"/nowhere",tool_input:$i,tool_response:$r}' | python3 "$GATE"; }
post '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-fable-5-1"}'
marker_active && fail "a Fable agent that ran on Fable must not record" || pass "a Fable agent that stayed on Fable records nothing"
post '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-fable-5-1","modelsUsed":["claude-fable-5-1","claude-opus-5"]}'
marker_active && pass "a mid-run swap off Fable (modelsUsed) records it" || fail "modelsUsed swap should record"
until=$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")
[ $(( until - $(now) )) -le 901 ] && pass "an overload fallback holds only briefly (15 min)" || fail "overload ttl too long"
reset_state
post '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"async_launched","resolvedModel":"claude-opus-5"}'
marker_active && pass "a Fable agent that started on Opus records it" || fail "resolvedModel fallback should record"
reset_state
post '{"subagent_type":"ai-reviewer","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-sonnet-5"}'
marker_active && fail "a non-Fable agent must not record" || pass "a fallback on a non-Fable agent is ignored"

reset_state
post_at() {  # post_at <claude-code-version> <tool_input-json> <tool_response-json>
    jq -nc --argjson i "$2" --argjson r "$3" --arg t "$(transcript "$1")" \
        '{hook_event_name:"PostToolUse",tool_name:"Agent",cwd:"/nowhere",transcript_path:$t,tool_input:$i,tool_response:$r}' | python3 "$GATE"
}
CLAUDE_CODE_SUBAGENT_MODEL=sonnet post_at 2.1.219 '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-sonnet-5"}'
marker_active && fail "an old Claude Code running a Fable agent on the variable's Sonnet must not record" || pass "before 2.1.251 a Fable agent the variable sent to Sonnet is not a fallback"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet post_at 2.1.276 '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-opus-5"}'
marker_active && pass "since 2.1.251 a Fable agent that started on Opus records it, whatever the variable says" || fail "the variable hid a fallback off Fable"
reset_state
CLAUDE_CODE_SUBAGENT_MODEL=sonnet post '{"subagent_type":"ai-expert","prompt":"p"}' '{"status":"completed","resolvedModel":"claude-sonnet-5"}'
marker_active && fail "with no version, Sonnet may be the variable's doing: it must not record" || pass "with no readable version a disputed agent is not blamed on Fable"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet stop_failure model_not_found '{"agent_type":"ai-expert"}'
marker_active && fail "with no version, a disputed agent's StopFailure must not record" || pass "with no readable version StopFailure does not attribute a disputed agent to Fable"
CLAUDE_CODE_SUBAGENT_MODEL=sonnet stop_failure model_not_found "$(jq -nc --arg p "$(transcript 2.1.276)" '{agent_type:"ai-expert",transcript_path:$p}')"
marker_active && pass "since 2.1.251 StopFailure attributes a Fable-pinned agent to Fable, whatever the variable says" || fail "the variable hid a Fable agent from StopFailure"

echo "== statusline: weekly limit nearly used"
reset_state
reset_at=$(( $(now) + 7200 ))
jq -nc --argjson r "$reset_at" '{rate_limits:{seven_day:{used_percentage:93.5,resets_at:$r}}}' | python3 "$GATE" statusline
marker_active && pass "93.5% of the weekly limit routes Fable to Opus" || fail "weekly threshold should record"
[ "$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")" = "$reset_at" ] && pass "until the weekly reset (epoch)" || fail "reset time not honoured"
reset_state
iso=$(date -u -d "@$(( $(now) + 5000 ))" +%Y-%m-%dT%H:%M:%SZ)
jq -nc --arg r "$iso" '{rate_limits:{seven_day:{used_percentage:99,resets_at:$r}}}' | python3 "$GATE" statusline
[ "$(jq -r .unavailable.until "$CLAUDE_FABLE_GATE_STATE")" -gt $(( $(now) + 4000 )) ] && pass "an ISO resets_at is understood" || fail "ISO reset not parsed"
reset_state
jq -nc '{rate_limits:{seven_day:{used_percentage:40}}}' | python3 "$GATE" statusline
marker_active && fail "40% must not route" || pass "below the threshold nothing is recorded"
out=$(printf '{"model":{"id":"x"}}' | python3 "$GATE" statusline)
[ -z "$out" ] && [ ! -e "$CLAUDE_FABLE_GATE_STATE" ] && pass "statusline mode prints nothing and tolerates missing rate_limits" || fail "statusline mode should be silent"

echo "== fails open"
for bad in 'not json' '[]' '{"hook_event_name":"PreToolUse","tool_name":"Agent","tool_input":"string"}' ''; do
    out=$(printf '%s' "$bad" | python3 "$GATE"); rc=$?
    [ $rc -eq 0 ] && [ -z "$out" ] && pass "malformed input '${bad:0:20}' is allowed silently" || fail "malformed input should fail open" "rc=$rc out=$out"
done
set_marker $(( $(now) + 600 ))
chmod 000 "$CLAUDE_FABLE_GATE_STATE"
out=$(agent_call '{"subagent_type":"ai-expert","prompt":"p"}'); rc=$?
chmod 600 "$CLAUDE_FABLE_GATE_STATE"
[ $rc -eq 0 ] && pass "an unreadable state file never breaks an Agent call" || fail "unreadable state should fail open"
printf '{broken' > "$CLAUDE_FABLE_GATE_STATE"
expect_route unchanged '{"subagent_type":"ai-expert","prompt":"p"}' "a corrupt state file means Fable is tried"

echo "== CLI"
reset_state
python3 "$GATE" status | grep -q '^inactive' && pass "status reports inactive" || fail "status inactive"
python3 "$GATE" set 120 manual test >/dev/null && marker_active && pass "set records a manual window" || fail "set failed"
python3 "$GATE" clear >/dev/null && ! marker_active && pass "clear re-enables Fable" || fail "clear failed"
python3 "$GATE" bogus >/dev/null 2>&1; [ $? -eq 2 ] && pass "an unknown command exits 2" || fail "unknown command exit code"

echo "== statusline --then: the user's statusline runs unchanged behind the check"
reset_state
high=$(jq -nc --argjson r $(( $(now) + 7200 )) '{model:{display_name:"Sonnet"},rate_limits:{seven_day:{used_percentage:95,resets_at:$r}}}')
out=$(printf '%s' "$high" | python3 "$GATE" statusline --then 'jq -r .model.display_name | sed "s/^/[model] /"')
[ "$out" = "[model] Sonnet" ] && pass "the inner command gets the same stdin and its output passes through" || fail "inner statusline output wrong" "$out"
marker_active && pass "and the weekly check still recorded 95%" || fail "wrapped statusline should still record"
out=$(printf '%s' "$high" | python3 "$GATE" statusline --then 'echo partial; exit 3'); rc=$?
[ "$rc" = 3 ] && [ "$out" = "partial" ] && pass "the inner command's exit code is passed through" || fail "exit code not propagated" "rc=$rc out=$out"
reset_state
out=$(printf '%s' "$high" | CLAUDE_FABLE_GATE=off python3 "$GATE" statusline --then 'echo still-here')
[ "$out" = "still-here" ] && ! marker_active && pass "CLAUDE_FABLE_GATE=off skips the check but keeps the statusline" || fail "gate off should still run the statusline" "$out"
out=$(printf 'garbage' | python3 "$GATE" statusline --then 'cat')
[ "$out" = "garbage" ] && pass "unparseable input still reaches the user's statusline" || fail "garbage input should pass through" "$out"
out=$(printf '%s' "$high" | python3 "$GATE" statusline --then 'echo "$HOME" | grep -q . && printf "%s|%s" "a b" '"'"'c"d'"'")
[ "$out" = 'a b|c"d' ] && pass "quoting inside the inner command survives" || fail "inner quoting broken" "$out"

# ------------------------------------------------------------------ installer
settings_has_gate() {  # settings_has_gate <settings.json> <event> -> 0 if registered
    jq -e --arg e "$2" '[.hooks[$e][]?.hooks[]?.command] | any(test("fable-gate"))' "$1" >/dev/null
}
gate_count() { jq '[.hooks[]?[]?.hooks[]? | select(.command | test("fable-gate"))] | length' "$1"; }

echo "== installer: dry runs per install option"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --fable yes --dry-run 2>&1)
printf '%s' "$out" | grep -q 'fable-gate=on' && pass "--plan max --fable yes: the gate is on" || fail "max+fable should enable the gate" "$out"
printf '%s' "$out" | grep -q 'fable-gate.py status' && pass "--plan max --fable yes: CLAUDE.md explains the gate and the Opus re-run" || fail "the block should mention the gate"
printf '%s' "$out" | grep -q '"matcher": "rate_limit|model_not_found"' && pass "--plan max --fable yes: StopFailure is matched on the two unavailability errors" || fail "StopFailure matcher missing"
for opt in "max no" "pro no" "pro yes"; do
    set -- $opt
    out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan "$1" --fable "$2" --dry-run 2>&1)
    printf '%s' "$out" | grep -q 'fable-gate=off' && pass "--plan $1 --fable $2: the gate is off" || fail "--plan $1 --fable $2 should not enable the gate" "$out"
    printf '%s' "$out" | grep -q 'fable-gate.py status' && fail "--plan $1 --fable $2 must not describe the gate" || pass "--plan $1 --fable $2: CLAUDE.md does not mention the gate"
done
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --dry-run 2>&1)
printf '%s' "$out" | grep -q 'fable-gate=on' && pass "--plan max (fable auto) turns the gate on" || fail "fable auto on max should enable the gate"

echo "== installer: real installs per option"
D="$TMP/c-max-yes"; mkdir -p "$D"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
for ev in PreToolUse PostToolUse StopFailure; do
    settings_has_gate "$D/settings.json" "$ev" && pass "max+fable registers fable-gate on $ev" || fail "max+fable: $ev missing"
done
jq -e '.hooks.PreToolUse[] | select(.hooks[0].command | test("fable-gate")) | .matcher == "Agent"' "$D/settings.json" >/dev/null \
    && pass "the PreToolUse entry matches the Agent tool" || fail "PreToolUse matcher should be Agent"
[ -x "$D/hooks/fable-gate.py" ] && pass "fable-gate.py is installed executable" || fail "fable-gate.py not executable"
grep -qxF 'model: fable[1m]' "$D/agents/architect.md" && pass "architect keeps model: fable[1m] (the gate reroutes at run time)" || fail "architect should stay pinned to fable[1m]"
grep -qE '^model:' "$D/agents/ai-expert.md" && fail "ai-expert must inherit the Opus session on max" || pass "ai-expert inherits the session model on max"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(gate_count "$D/settings.json")" = 3 ] && pass "a re-install does not duplicate the gate's three entries" || fail "gate duplicated: $(gate_count "$D/settings.json")"

for opt in "max no" "pro no"; do
    set -- $opt
    D="$TMP/c-$1-$2"; mkdir -p "$D"
    CLAUDE_DIR="$D" bash "$INSTALL" --plan "$1" --fable "$2" >/dev/null 2>&1
    [ "$(gate_count "$D/settings.json")" = 0 ] && pass "--plan $1 --fable $2 registers no gate hook" || fail "--plan $1 --fable $2 registered the gate"
    jq -e '.hooks.StopFailure' "$D/settings.json" >/dev/null && fail "--plan $1 --fable $2 left an empty StopFailure list" || pass "--plan $1 --fable $2 adds no StopFailure event"
    grep -qE '^model: fable' "$D/agents/architect.md" && fail "--plan $1 --fable $2 must not pin fable on architect" || pass "--plan $1 --fable $2 leaves no agent on fable"
done

echo "== installer: switching Fable off strips the gate and nothing else"
D="$TMP/c-switch"; mkdir -p "$D"
jq -n '{hooks:{PostToolUse:[{matcher:"Agent",hooks:[{type:"command",command:"my-agent-logger.sh"}]}],
                StopFailure:[{matcher:"rate_limit",hooks:[{type:"command",command:"notify-me.sh"}]}]}}' > "$D/settings.json"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(gate_count "$D/settings.json")" = 3 ] && pass "fable yes adds the gate next to the user's own hooks" || fail "gate not added alongside user hooks"
out=$(CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable no 2>&1)
[ "$(gate_count "$D/settings.json")" = 0 ] && pass "a later --fable no removes every gate entry" || fail "gate left behind: $(gate_count "$D/settings.json")"
printf '%s' "$out" | grep -q 'removed: fable-gate hooks' && pass "the removal is reported" || fail "removal should be reported" "$out"
jq -e '[.hooks.PostToolUse[].hooks[].command] | index("my-agent-logger.sh")' "$D/settings.json" >/dev/null \
    && pass "the user's own PostToolUse:Agent hook survives" || fail "user PostToolUse hook lost"
jq -e '[.hooks.StopFailure[].hooks[].command] | index("notify-me.sh")' "$D/settings.json" >/dev/null \
    && pass "the user's own StopFailure hook survives" || fail "user StopFailure hook lost"
[ "$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$D/settings.json")" = 4 ] \
    && pass "the four guards stay registered" || fail "guards changed on fable off"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(gate_count "$D/settings.json")" = 3 ] && pass "switching Fable back on restores the gate" || fail "gate not restored"

D="$TMP/c-pro-after-max"; mkdir -p "$D"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
CLAUDE_DIR="$D" bash "$INSTALL" --plan pro >/dev/null 2>&1
[ "$(gate_count "$D/settings.json")" = 0 ] && pass "moving from max to pro removes the gate" || fail "gate left after pro install"
jq -e '.hooks | has("StopFailure") | not' "$D/settings.json" >/dev/null && pass "and drops the StopFailure event it alone used" || fail "empty StopFailure left behind"
jq -e 'has("statusLine") | not' "$D/settings.json" >/dev/null && pass "and removes the statusline the Fable install added" || fail "gate statusline left after pro install"

echo "== installer: the weekly check is on by default through the statusline"
PREFIX='"$HOME/.claude/hooks/fable-gate.py" statusline'
ORIG='bash ~/.claude/statusline-command.sh --flag "two words" '"'"'single'"'"
H="$TMP/h-wrap"; D="$H/.claude"; mkdir -p "$D"
jq -n --arg c "$ORIG" '{statusLine:{type:"command",command:$c,padding:1}}' > "$D/settings.json"
out=$(CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes --dry-run 2>&1)
printf '%s' "$out" | grep -q 'statusline: would have wrapped' && pass "the dry run says it would wrap the statusline" || fail "dry run should announce the wrap" "$out"
[ "$(jq -r .statusLine.command "$D/settings.json")" = "$ORIG" ] && pass "and the dry run leaves it alone" || fail "dry run changed the statusline"
out=$(CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes 2>&1)
cmd=$(jq -r .statusLine.command "$D/settings.json")
case "$cmd" in "$PREFIX --then "*) pass "a Fable install wraps an existing statusline command";; *) fail "statusline not wrapped" "$cmd";; esac
printf '%s' "$out" | grep -q 'statusline: wrapped' && pass "the wrap is reported" || fail "wrap not reported" "$out"
[ "$(jq -r .statusLine.padding "$D/settings.json")" = 1 ] && pass "other statusLine fields are kept" || fail "statusLine padding lost"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(jq -r .statusLine.command "$D/settings.json")" = "$cmd" ] && pass "a re-install does not wrap twice" || fail "statusline double-wrapped" "$(jq -r .statusLine.command "$D/settings.json")"

mkdir -p "$H/.claude"; printf '#!/usr/bin/env bash\ncat >/dev/null; printf "my-statusline %%s" "$*"\n' > "$H/.claude/statusline-command.sh"
reset_state
out=$(printf '%s' "$high" | HOME="$H" bash -c "$cmd")
[ "$out" = "my-statusline --flag two words single" ] && pass "the installed wrapper runs the original statusline with its arguments intact" || fail "installed wrapper output wrong" "$out"
marker_active && pass "and records the weekly limit through the installed hook" || fail "installed wrapper did not record"

out=$(CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable no 2>&1)
[ "$(jq -r .statusLine.command "$D/settings.json")" = "$ORIG" ] && pass "--fable no restores the original command byte for byte" || fail "original statusline not restored" "$(jq -r .statusLine.command "$D/settings.json")"
printf '%s' "$out" | grep -q 'statusline: restored' && pass "the restore is reported" || fail "restore not reported" "$out"

H="$TMP/h-none"; D="$H/.claude"; mkdir -p "$D"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(jq -r .statusLine.command "$D/settings.json")" = "$PREFIX" ] && pass "with no statusline, a Fable install adds the bare check" || fail "bare statusline not added" "$(jq -c .statusLine "$D/settings.json")"
out=$(printf '%s' "$high" | HOME="$H" bash -c "$(jq -r .statusLine.command "$D/settings.json")")
[ -z "$out" ] && pass "which prints nothing" || fail "bare statusline should be silent" "$out"
CLAUDE_DIR="$D" bash "$INSTALL" --plan max --fable no >/dev/null 2>&1
jq -e 'has("statusLine") | not' "$D/settings.json" >/dev/null && pass "--fable no removes the statusline it added" || fail "added statusline not removed"

for opt in "max no" "pro no"; do
    set -- $opt
    H="$TMP/h-$1-$2"; D="$H/.claude"; mkdir -p "$D"
    jq -n --arg c "$ORIG" '{statusLine:{type:"command",command:$c}}' > "$D/settings.json"
    CLAUDE_DIR="$D" bash "$INSTALL" --plan "$1" --fable "$2" >/dev/null 2>&1
    [ "$(jq -r .statusLine.command "$D/settings.json")" = "$ORIG" ] && pass "--plan $1 --fable $2 leaves the statusline untouched" || fail "--plan $1 --fable $2 changed the statusline"
done

summary "fable-gate"
