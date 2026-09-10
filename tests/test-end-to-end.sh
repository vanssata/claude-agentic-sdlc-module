#!/usr/bin/env bash
# The whole thing, wired together the way it runs in practice: install into a
# scratch CLAUDE_DIR, scaffold a throwaway repository, then drive one task
# through the state machine while the guards are armed against it.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
DIR="$TMP/claude"; REPO="$TMP/shop"
mkdir -p "$DIR" "$REPO/src/Payment" "$REPO/src/Order" "$REPO/tests/Payment"

echo "== install"
CLAUDE_DIR="$DIR" bash "$PLUGIN_ROOT/install.sh" --plan max --fable yes >/dev/null 2>&1
[ -f "$DIR/skills/ai-init/scaffold-ai.sh" ] && pass "installed into a scratch CLAUDE_DIR" || fail "install failed"

echo "== scaffold a project"
git -C "$REPO" init -q -b main
git -C "$REPO" config user.email t@example.com; git -C "$REPO" config user.name t
printf '<?php class Gateway {}\n'       > "$REPO/src/Payment/Gateway.php"
printf '<?php class LegacyGateway {}\n' > "$REPO/src/Payment/LegacyGateway.php"
printf '<?php class OrderProcessor {}\n' > "$REPO/src/Order/OrderProcessor.php"
printf 'SECRET=live_key_do_not_read\n'  > "$REPO/.env"
git -C "$REPO" add src && git -C "$REPO" commit -qm "initial"

CLAUDE_AGENTIC_TEMPLATES="$DIR/skills/ai-init/templates" bash "$DIR/skills/ai-init/scaffold-ai.sh" "$REPO" >/dev/null
[ -f "$REPO/.ai/AGENTS.md" ] && pass ".ai/ scaffolded into the project" || fail "scaffold failed"
[ -f "$REPO/.ai/policies/risk-tiers.json" ] && pass "the risk tiers are in place" || fail "risk tiers missing"

S() { python3 "$DIR/skills/ai-task/state.py" --root "$REPO" "$@"; }
PATH_GUARD="$DIR/hooks/ai-path-guard.sh"
SCOPE_GUARD="$DIR/hooks/ai-scope-guard.sh"
GIT_GUARD="$DIR/hooks/ai-git-guard.sh"

decide() {  # decide <guard> <tool> <json-tool_input>
    local out
    out=$(jq -nc --arg r "$REPO" --arg t "$2" --argjson i "$3" \
        '{hook_event_name:"PreToolUse",tool_name:$t,cwd:$r,tool_input:$i}' | "$1")
    if [ -z "$out" ]; then echo allow; else
        printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"'
    fi
}

echo "== the path guard is now live in this project"
[ "$(decide "$PATH_GUARD" Read '{"file_path":"'"$REPO"'/.env"}')" = deny ] \
    && pass "reading .env is refused once the project has .ai/" || fail ".env should be refused"
[ "$(decide "$PATH_GUARD" Read '{"file_path":"'"$REPO"'/src/Payment/Gateway.php"}')" = allow ] \
    && pass "reading source is unaffected" || fail "source reads should be allowed"

echo "== a task through the pipeline"
TASK=$(S init --goal "add a handling fee to the payment gateway" --workflow feature)
case "$TASK" in T-*) pass "task $TASK started at discovery";; *) fail "init failed" "$TASK";; esac

S stage context --note "context summary written" >/dev/null
S stage impact_analysis >/dev/null
S stage risk_classification >/dev/null
S risk T4 --note "payments: T4 by default" >/dev/null
[ "$(S get --field risk_tier)" = T4 ] && pass "classified T4" || fail "tier should be T4"

TIERS="$REPO/.ai/policies/risk-tiers.json"
[ "$(jq -r '.tiers.T4.security_review' "$TIERS")" = true ] \
    && pass "the tier table demands a security review for T4" || fail "T4 should require security review"
[ "$(jq -r '.tiers.T4.human_approval' "$TIERS")" = true ] \
    && pass "and human approval" || fail "T4 should require human approval"

S stage plan >/dev/null
cat > "$TMP/steps.json" <<'JSON'
[
  { "step_id": "1", "description": "add the fee to the gateway",
    "allowed_files": ["src/Payment/Gateway.php", "tests/Payment/*.php"],
    "forbidden_files": ["src/Payment/LegacyGateway.php"],
    "forbidden_reason": "legacy gateway behaviour is frozen for this task",
    "required_tests": ["tests/Payment/FeeTest.php"] }
]
JSON
S plan --ref ".ai/reports/$TASK/implementation-plan.md" --steps "$TMP/steps.json" >/dev/null
S stage plan_review >/dev/null
S stage implementation >/dev/null
S step 1 >/dev/null
pass "plan registered and step 1 armed"

echo "== the scope guard enforces the step"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Payment/Gateway.php"}')" = allow ] \
    && pass "editing an allowed file is permitted" || fail "allowed file should be editable"
[ "$(decide "$SCOPE_GUARD" Write '{"file_path":"'"$REPO"'/tests/Payment/FeeTest.php","content":"x"}')" = allow ] \
    && pass "writing the required test is permitted" || fail "test file should be writable"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Order/OrderProcessor.php"}')" = deny ] \
    && pass "editing an out-of-scope file is refused" || fail "out-of-scope edit should be refused"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Payment/LegacyGateway.php"}')" = deny ] \
    && pass "editing a forbidden file is refused" || fail "forbidden file should be refused"

out=$(jq -nc --arg r "$REPO" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:($r+"/src/Order/OrderProcessor.php")}}' | "$SCOPE_GUARD")
printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason' | grep -q SCOPE_CHANGE_REQUIRED \
    && pass "the refusal carries the SCOPE_CHANGE_REQUIRED signal" || fail "signal missing" "$out"

echo "== finishing the task"
S step-done 1 >/dev/null
S stage test >/dev/null;             S set test_status passing >/dev/null
S stage adversarial_review >/dev/null; S set review_status passed >/dev/null
S stage security_review >/dev/null;  S set security_status passed >/dev/null
S stage release_report >/dev/null
S stage human_approval >/dev/null
S approve --by "the human" >/dev/null
S done >/dev/null
[ "$(S get --field current_stage)" = done ] && pass "the task reached done" || fail "task should be done"

echo "== the scope guard disarms when no step is current"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Order/OrderProcessor.php"}')" = allow ] \
    && pass "out-of-scope edits are free again once the task closes" || fail "guard should disarm"

echo "== the git guard still refuses the dangerous half"
[ "$(decide "$GIT_GUARD" Bash '{"command":"git push --force origin main"}')" = deny ] \
    && pass "force push is refused" || fail "force push should be refused"
[ "$(decide "$GIT_GUARD" Bash '{"command":"git push origin main"}')" = deny ] \
    && pass "pushing to main is refused" || fail "push to main should be refused"
[ "$(decide "$GIT_GUARD" Bash '{"command":"git add ."}')" = deny ] \
    && pass "'git add .' with an untracked .env is refused" || fail "secret staging should be refused"
[ "$(decide "$GIT_GUARD" Bash '{"command":"git status"}')" = allow ] \
    && pass "ordinary git commands are unaffected" || fail "git status should be allowed"

echo "== the audit trail survives"
ARCHIVED=$(S archive)
[ -f "$ARCHIVED" ] && pass "the closed task is archived under .ai/reports/" || fail "archive failed"
jq -e '.history | length >= 12' "$ARCHIVED" >/dev/null && pass "its history records every stage" || fail "history too short"
jq -e '.human_approval.granted == true' "$ARCHIVED" >/dev/null && pass "and who approved it" || fail "approval not recorded"

echo "== no application code was touched by any of this"
changed=$(git -C "$REPO" status --porcelain -- src | wc -l)
[ "$changed" = 0 ] && pass "src/ is untouched" || fail "src/ was modified" "$(git -C "$REPO" status --porcelain -- src)"

summary "end-to-end"
