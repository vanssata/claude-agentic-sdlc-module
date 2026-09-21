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
