#!/usr/bin/env bash
# ai-scope-guard: fixtures plus the stage/state properties that must disarm it.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/ai-scope-guard.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"
mkdir -p "$ROOT/.ai/state"

write_state() {  # write_state <stage> [current_step_id]
    jq -n --arg stage "$1" --arg step "${2-1}" '{
      task_id: "T-2026-09-09-001",
      goal: "add a fee to the payment gateway",
      workflow: "feature",
      risk_tier: "T4",
      current_stage: $stage,
      approved_plan: {
        ref: ".ai/reports/T-2026-09-09-001/implementation-plan.md",
        current_step_id: $step,
        steps: [
          { step_id: "1",
            description: "add the fee calculation",
            allowed_files: ["src/Payment/*.php", "tests/Payment/*.php"],
            forbidden_files: ["src/Payment/LegacyGateway.php"],
            forbidden_reason: "legacy gateway behaviour is frozen for this task",
            status: "in_progress",
            required_tests: ["tests/Payment/GatewayTest.php"] }
        ]
      }
    }' > "$ROOT/.ai/state/current.json"
}

echo "== ai-scope-guard (stage = implementation)"
write_state implementation 1
for f in "$PLUGIN_ROOT"/tests/fixtures/scope-guard/*.json; do
    run_fixture "$GUARD" "$f" "$ROOT"
done

echo "== ai-scope-guard (codex apply_patch payloads)"
run_codex_fixtures "$GUARD" scope "$ROOT"
out=$(jq -r '.payload' "$PLUGIN_ROOT/tests/fixtures/codex-hooks/21-scope-apply-patch-out-of-scope.json" \
      | sed "s|__ROOT__|$ROOT|g" | "$GUARD")
printf '%s' "$out" | grep -q 'SCOPE_CHANGE_REQUIRED' \
    && pass "an out-of-scope patch is refused with the SCOPE_CHANGE_REQUIRED signal" \
    || fail "the Codex deny message must carry SCOPE_CHANGE_REQUIRED" "$out"
assert_fails_open "$GUARD" "a malformed Codex payload fails open" "{ not json"

echo "== ai-scope-guard (disarmed states)"
payload=$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:($r+"/src/Order/OrderProcessor.php")}}')

write_state plan 1
out=$(printf '%s' "$payload" | "$GUARD")
[ -z "$out" ] && pass "stage=plan: out-of-scope edit is not blocked" || fail "stage=plan should not block" "$out"

write_state implementation ""
out=$(printf '%s' "$payload" | "$GUARD")
[ -z "$out" ] && pass "no current_step_id: not blocked" || fail "missing step id should not block" "$out"

write_state implementation 99
out=$(printf '%s' "$payload" | "$GUARD")
[ -z "$out" ] && pass "unknown step id: fails open" || fail "unknown step id should fail open" "$out"

rm -f "$ROOT/.ai/state/current.json"
out=$(printf '%s' "$payload" | "$GUARD")
[ -z "$out" ] && pass "no state file: not blocked" || fail "missing state should not block" "$out"

BARE="$TMP/bare"; mkdir -p "$BARE/src"
out=$(jq -nc --arg r "$BARE" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:($r+"/src/x.php")}}' | "$GUARD")
[ -z "$out" ] && pass "no .ai/: not blocked" || fail "project without .ai/ should not block" "$out"

# The deny message must carry the literal signal the manager parses for.
write_state implementation 1
out=$(printf '%s' "$payload" | "$GUARD")
if printf '%s' "$out" | grep -q 'SCOPE_CHANGE_REQUIRED'; then
    pass "deny message contains the SCOPE_CHANGE_REQUIRED signal"
else
    fail "deny message must contain SCOPE_CHANGE_REQUIRED" "$out"
fi

summary "ai-scope-guard"
