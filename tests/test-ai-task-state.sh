#!/usr/bin/env bash
# state.py: a full task round-trip, the validation rules, and the failure modes
# that must be loud rather than silent.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATE="$PLUGIN_ROOT/skills/ai-task/state.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"; mkdir -p "$ROOT/.ai/state" "$ROOT/.ai/reports"
S() { python3 "$STATE" --root "$ROOT" "$@"; }

echo "== state.py round trip"
TASK=$(S init --goal "add a payment fee" --workflow feature 2>&1)
case "$TASK" in T-*) pass "init prints a task id ($TASK)";; *) fail "init should print a task id" "$TASK";; esac

[ "$(S get --field current_stage)" = discovery ] && pass "a new task starts at discovery" || fail "should start at discovery"

S stage context >/dev/null
[ "$(S get --field current_stage)" = context ] && pass "stage advances" || fail "stage should advance"

S risk T4 --note "touches payments" >/dev/null
[ "$(S get --field risk_tier)" = T4 ] && pass "risk tier is recorded" || fail "risk tier should be recorded"

cat > "$TMP/steps.json" <<'JSON'
[
  { "step_id": "1", "description": "add the fee calculator",
    "allowed_files": ["src/Payment/*.php"], "forbidden_files": ["src/Payment/LegacyGateway.php"],
    "required_tests": ["tests/Payment/FeeTest.php"] },
  { "step_id": "2", "description": "wire it into checkout",
    "allowed_files": ["src/Checkout/*.php"] }
]
JSON
S plan --ref ".ai/reports/$TASK/implementation-plan.md" --steps "$TMP/steps.json" >/dev/null
[ "$(S get --field approved_plan.ref)" = ".ai/reports/$TASK/implementation-plan.md" ] && pass "plan ref recorded" || fail "plan ref should be recorded"

S step 1 >/dev/null
[ "$(S get --field approved_plan.current_step_id)" = 1 ] && pass "current step is set" || fail "current step should be set"

S step-done 1 >/dev/null
[ "$(S get --field approved_plan.current_step_id)" = "" ] && pass "current step cleared when the step is done" || fail "current step should clear"
S get --field completed_steps | grep -q '"1"' && pass "completed step is listed" || fail "completed step should be listed"

S set test_status passing >/dev/null
[ "$(S get --field test_status)" = passing ] && pass "test_status is settable" || fail "test_status should be settable"

S risks --add "legacy gateway path untested" >/dev/null
S get --field open_risks | grep -q legacy && pass "open risks are recorded" || fail "open risks should be recorded"

S approve --by "the human" >/dev/null
S get --field human_approval | grep -q '"granted": true' && pass "approval is recorded with who granted it" || fail "approval should be recorded"

S done >/dev/null
[ "$(S get --field current_stage)" = done ] && pass "task can be closed" || fail "task should close"

echo "== history is an audit trail"
n=$(S get --field history | jq 'length')
[ "$n" -ge 10 ] && pass "history recorded $n events" || fail "history should record every transition" "got $n"
S get --field history | jq -e '.[] | select(.event=="human_approval")' >/dev/null \
  && pass "history contains the approval event" || fail "history should contain the approval"

echo "== validation and failure modes"
out=$(S stage nonsense 2>&1); [ $? -ne 0 ] || true
printf '%s' "$out" | grep -q "stage must be one of" && pass "an unknown stage is rejected" || fail "unknown stage should be rejected" "$out"

out=$(S risk T9 2>&1 || true)
printf '%s' "$out" | grep -q "risk tier must be one of" && pass "an unknown risk tier is rejected" || fail "unknown tier should be rejected" "$out"

out=$(S set test_status green 2>&1 || true)
printf '%s' "$out" | grep -q "must be one of" && pass "an invalid test_status is rejected" || fail "invalid status should be rejected" "$out"

out=$(S step 99 2>&1 || true)
printf '%s' "$out" | grep -q "no step '99'" && pass "an unknown step id is rejected" || fail "unknown step should be rejected" "$out"

echo "== archive and re-init"
ARCHIVED=$(S archive)
[ -f "$ARCHIVED" ] && pass "archive writes the closed task under .ai/reports/" || fail "archive should write a file" "$ARCHIVED"
[ ! -f "$ROOT/.ai/state/current.json" ] && pass "archive clears current.json" || fail "archive should clear current.json"

S init --goal "second task" --workflow bugfix >/dev/null
S stage implementation >/dev/null
out=$(S init --goal "third task" --workflow bugfix 2>&1 || true)
printf '%s' "$out" | grep -q "still at stage" && pass "starting a second task over a live one is refused" || fail "should refuse to clobber a live task" "$out"
S init --goal "third task" --workflow bugfix --force >/dev/null && pass "--force starts a fresh task anyway" || fail "--force should work"

echo "== a corrupt state file is loud, not silently replaced"
printf 'not json at all' > "$ROOT/.ai/state/current.json"
out=$(S get 2>&1 || true)
printf '%s' "$out" | grep -q "unreadable" && pass "a corrupt state file reports the problem" || fail "corrupt state should be loud" "$out"

echo "== no .ai/ at all"
out=$(python3 "$STATE" --root "$TMP" get 2>&1 || true)
printf '%s' "$out" | grep -q "run /ai-init first" && pass "a project without .ai/ says what to do" || fail "should point at /ai-init" "$out"

summary "state.py"
