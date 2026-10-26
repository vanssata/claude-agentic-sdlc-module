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
STATE_FILE="$REPO/.ai/state/current.json"
S start --goal "add a handling fee to the payment gateway" --workflow feature \
  --files "src/Payment/Gateway.php,tests/Payment/*.php" --tests tests/Payment/FeeTest.php \
  --declare behaviour=1:"a fee on every payment" --declare novelty=0:"an existing gateway" >/dev/null 2>&1 \
  && pass "start registers the task and arms the scope guard" || fail "start failed"
TASK=$(jq -r .task_id "$STATE_FILE")
[ "$(jq -r .mode "$STATE_FILE")" = full ] && pass "a payment path weighs in at full mode" \
  || fail "src/Payment/** should be domain 2" "$(jq -c .weight.lines "$STATE_FILE")"

echo "== the scope guard enforces the step"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Payment/Gateway.php"}')" = allow ] \
    && pass "editing an allowed file is permitted" || fail "allowed file should be editable"
[ "$(decide "$SCOPE_GUARD" Write '{"file_path":"'"$REPO"'/tests/Payment/FeeTest.php","content":"x"}')" = allow ] \
    && pass "writing the required test is permitted" || fail "test file should be writable"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Order/OrderProcessor.php"}')" = deny ] \
    && pass "editing an out-of-scope file is refused" || fail "out-of-scope edit should be refused"
[ "$(decide "$SCOPE_GUARD" Edit '{"file_path":"'"$REPO"'/src/Payment/LegacyGateway.php"}')" = deny ] \
    && pass "a file beside the task's, unnamed, is refused" || fail "an unnamed file should be refused"

out=$(jq -nc --arg r "$REPO" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:($r+"/src/Order/OrderProcessor.php")}}' | "$SCOPE_GUARD")
printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason' | grep -q SCOPE_CHANGE_REQUIRED \
    && pass "the refusal carries the SCOPE_CHANGE_REQUIRED signal" || fail "signal missing" "$out"

echo "== the same task, from Codex"
# A second runtime installed over the same project must land on the same state
# file and enforce the same step — the pipeline is shared, only the adapter differs.
CDIR="$TMP/codex"; mkdir -p "$CDIR"
CODEX_DIR="$CDIR" bash "$PLUGIN_ROOT/install.sh" >/dev/null 2>&1
[ -f "$CDIR/hooks/ai-scope-guard.sh" ] && pass "installed into a scratch CODEX_DIR" || fail "codex install failed"
[ -f "$CDIR/agents/ai-reviewer.toml" ] && pass "the Codex agent roster is rendered" || fail "codex agents missing"
[ -e "$CDIR/hooks/cap-large-read.py" ] && fail "cap-large-read has no Codex counterpart" || pass "no Claude-only hook is installed into Codex"
# Codex has UserPromptSubmit, PreCompact and SessionStart, so the context guard
# crosses: the handoff, the questions and session.json are the same on both
# sides. What does not cross is the transcript-derived snapshot, which is built
# from a Claude transcript — the script knows which runtime it is in from its
# own location.
[ -e "$CDIR/hooks/context-guard.py" ] && pass "the context guard is installed into Codex too" || fail "context-guard should be installed into Codex"
[ "$(jq '[.hooks | to_entries[] | .value[] | .hooks[] | .command | select(test("context-guard"))] | length' "$CDIR/hooks.json")" = 3 ] \
    && pass "and registered on its three events there" || fail "expected three Codex registrations" "$(jq -c '.hooks | keys' "$CDIR/hooks.json")"

CODEX_SCOPE="$CDIR/hooks/ai-scope-guard.sh"
CODEX_PATH="$CDIR/hooks/ai-path-guard.sh"
CODEX_GIT="$CDIR/hooks/ai-git-guard.sh"

# The state the Claude half of this test wrote is the state Codex reads.
python3 "$CDIR/skills/ai-task/state.py" --root "$REPO" status | grep -q "^task: $TASK" \
    && pass "Codex reads the task the Claude session started" || fail "state is not shared between runtimes"
python3 "$CDIR/skills/ai-task/state.py" --root "$REPO" status --json | jq -e '.mode == "full"' >/dev/null \
    && pass "and the same mode" || fail "mode should be shared" "$(python3 "$CDIR/skills/ai-task/state.py" --root "$REPO" status --json)"

mkpatch() {  # mkpatch <path> [second-path] -> one apply_patch payload, one or two files
    printf '*** Begin Patch\n*** Update File: %s\n@@\n-old\n+new\n' "$1"
    [ -n "${2:-}" ] && printf '*** Update File: %s\n@@\n-old\n+new\n' "$2"
    printf '*** End Patch\n'
}
ap() {  # ap <guard> <patch-text>
    local out
    out=$(jq -nc --arg r "$REPO" --arg c "$2" \
        '{hook_event_name:"PreToolUse",tool_name:"apply_patch",cwd:$r,tool_input:{command:$c}}' | "$1")
    if [ -z "$out" ]; then echo allow; else
        printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"'
    fi
}

[ "$(ap "$CODEX_SCOPE" "$(mkpatch "$REPO/src/Payment/Gateway.php")")" = allow ] \
    && pass "an in-scope apply_patch is permitted" || fail "in-scope patch should be allowed"
[ "$(ap "$CODEX_SCOPE" "$(mkpatch "$REPO/src/Order/OrderProcessor.php")")" = deny ] \
    && pass "an out-of-scope apply_patch is refused" || fail "out-of-scope patch should be refused"
[ "$(ap "$CODEX_SCOPE" "$(mkpatch "$REPO/src/Payment/Gateway.php" "$REPO/src/Order/OrderProcessor.php")")" = deny ] \
    && pass "one out-of-scope file rejects the whole patch" || fail "mixed patch should be refused"
[ "$(ap "$CODEX_SCOPE" "$(mkpatch "$REPO/src/Payment/LegacyGateway.php")")" = deny ] \
    && pass "an unnamed file is refused through apply_patch too" || fail "an unnamed file should be refused"

out=$(jq -nc --arg r "$REPO" --arg c "$(mkpatch "$REPO/src/Order/OrderProcessor.php")" \
    '{hook_event_name:"PreToolUse",tool_name:"apply_patch",cwd:$r,tool_input:{command:$c}}' | "$CODEX_SCOPE")
printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecisionReason' | grep -q SCOPE_CHANGE_REQUIRED \
    && pass "and the Codex refusal carries the same signal" || fail "signal missing" "$out"

[ "$(ap "$CODEX_PATH" "$(mkpatch "$REPO/.env")")" = deny ] \
    && pass "the path guard refuses a patch that touches .env" || fail ".env patch should be refused"
[ "$(decide "$CODEX_GIT" Bash '{"command":"git push --force origin main"}')" = deny ] \
    && pass "the git guard refuses a force push from Codex as well" || fail "force push should be refused"

echo "== finishing the task"
# The full path to the gate needs a verify_command this fixture does not have;
# tests/test_end_to_end.py and test_ai_task_state.py::TestGate drive it.
S close --abandon >/dev/null && [ ! -f "$STATE_FILE" ] \
  && pass "close --abandon ends the task" || fail "the task should be closed"

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
ARCHIVED="$REPO/.ai/state/logs/$TASK/state.json"
[ -f "$ARCHIVED" ] && jq -e '.result == "abandoned"' "$ARCHIVED" >/dev/null \
    && pass "the closed task's state is kept under .ai/state/logs/" || fail "archive failed"
jq -se '.[-1].event == "task_closed" and .[-1].data.abandoned == true' "$REPO/.ai/reports/$TASK/events.jsonl" >/dev/null \
    && pass "and the journal says how it ended" || fail "task_closed missing"
[ -f "$REPO/.ai/reports/$TASK/task.md" ] && pass "and task.md is the record" || fail "task.md missing"

echo "== no application code was touched by any of this"
changed=$(git -C "$REPO" status --porcelain -- src | wc -l)
[ "$changed" = 0 ] && pass "src/ is untouched" || fail "src/ was modified" "$(git -C "$REPO" status --porcelain -- src)"

echo "== the schema-7 surface: tests/test_end_to_end.py (light = three calls, both runtimes; guarded boundaries)"
# discover, not `-m unittest tests.test_end_to_end`: -I keeps the cwd off sys.path.
out=$(AI_E2E=1 python3 -I -m unittest discover -s "$PLUGIN_ROOT/tests" -p test_end_to_end.py 2>&1); rc=$?
[ $rc = 0 ] && grep -q '^OK$' <<<"$out" && ! grep -q 'skipped' <<<"$out" \
  && pass "test_end_to_end.py: $(grep -oE '^Ran [0-9]+ tests?' <<<"$out")" || fail "test_end_to_end.py" "$out"

summary "end-to-end"
