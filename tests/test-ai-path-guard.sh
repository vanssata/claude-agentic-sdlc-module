#!/usr/bin/env bash
# ai-path-guard: fixtures plus the "no .ai/ means no guard" property.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/ai-path-guard.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"

mkdir -p "$ROOT"/{.ai/state,.ai/policies,src,config,var,migrations} \
         "$ROOT"/{.claude/agents,.codex,vendor/acme/pkg,node_modules/foo}
printf 'SECRET=1\n' > "$ROOT/.env"
printf 'SECRET=\n'  > "$ROOT/.env.example"
printf '{}\n'       > "$ROOT/.ai/state/current.json"
printf '{}\n'       > "$ROOT/.ai/policies/path-guard.json"
printf 'x\n'        > "$ROOT/src/Service.php"
printf 'x\n'        > "$ROOT/var/dump-2026-09-01.sql"
printf 'x\n'        > "$ROOT/migrations/Version20260101.sql"
printf 'x\n'        > "$ROOT/.claude/agents/ai-reviewer.md"
printf 'x\n'        > "$ROOT/vendor/acme/pkg/AGENTS.md"
printf 'x\n'        > "$ROOT/vendor/acme/pkg/.cursorrules"
printf 'x\n'        > "$ROOT/node_modules/foo/CLAUDE.md"
printf 'x\n'        > "$ROOT/node_modules/foo/index.js"
ln -sf ../.env "$ROOT/config/link.txt"

echo "== ai-path-guard (project with .ai/)"
for f in "$PLUGIN_ROOT"/tests/fixtures/path-guard/*.json; do
    run_fixture "$GUARD" "$f" "$ROOT"
done

echo "== ai-path-guard (codex payloads: apply_patch and shell)"
mkdir -p "$ROOT/.codex/hooks"
printf '{}\n' > "$ROOT/.codex/hooks/ai-git-guard.json"
run_codex_fixtures "$GUARD" path "$ROOT"

echo "== ai-path-guard (malformed input fails open)"
assert_fails_open "$GUARD" "empty payload is allowed" ""
assert_fails_open "$GUARD" "payload that is not JSON is allowed" "not json at all"
assert_fails_open "$GUARD" "apply_patch with no command is allowed" \
    "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"apply_patch",cwd:$r,tool_input:{}}')"
assert_fails_open "$GUARD" "a patch with no file headers is allowed" \
    "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"apply_patch",cwd:$r,tool_input:{command:"*** Begin Patch\n*** End Patch"}}')"

echo "== ai-path-guard (the runtime lock is tied to a task, not permanent)"
# decide <description> <expected> <payload> — the guard's decision on one payload.
decide() {
    local name="$1" expect="$2" out decision
    out=$(printf '%s' "$3" | "$GUARD" 2>&1)
    if [ -z "$out" ]; then decision=allow
    else decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"' 2>/dev/null || echo malformed); fi
    if [ "$decision" = "$expect" ]; then pass "$name"
    else fail "$name" "expected $expect, got $decision${out:+ — $(printf '%s' "$out" | head -c 200)}"; fi
}
edit_agent=$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:($r+"/.claude/agents/ai-reviewer.md")}}')

printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide "stage=implementation: editing an agent definition is denied" deny "$edit_agent"
printf '{"current_stage":"done","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide "stage=done: the same edit is allowed again" allow "$edit_agent"
rm -f "$ROOT/.ai/state/current.json"
decide "no task at all: the same edit is allowed" allow "$edit_agent"
printf 'not json\n' > "$ROOT/.ai/state/current.json"
decide "a state file that does not parse counts as in flight" deny "$edit_agent"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (approval cannot be granted from an agent shell)"
# Not a fixture: the shared root always has a state file, and the point of this
# rule is that it is armed by the task rather than standing permanently.
approve_cmd=$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"python3 /home/u/.claude/skills/ai-task/state.py --root . approve --by ivan"}}')
rm -f "$ROOT/.ai/state/current.json"
decide "no task in flight: state.py approve is none of the guard's business" allow "$approve_cmd"
printf '{"current_stage":"human_approval","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide "with a task in flight the same call is denied" deny "$approve_cmd"
out=$(printf '%s' "$approve_cmd" | AI_UNATTENDED=1 "$GUARD" 2>&1)
[ -z "$out" ] && pass "AI_UNATTENDED in the hook's own environment lets a launcher through" \
    || fail "the unattended launcher should be allowed" "$out"
out=$(printf '%s' "$approve_cmd" | "$GUARD" 2>&1)
printf '%s' "$out" | grep -q "Approval happens outside the agent" \
    && pass "and the deny text teaches the human what to do" || fail "WHY_APPROVE is missing" "$out"
printf '%s' "$out" | grep -q "AI_UNATTENDED=1 in the launcher" \
    && pass "including the unattended route and what it costs" || fail "the unattended route should be named"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (project WITHOUT .ai/ — every guard must be inert)"
BARE="$TMP/bare"; mkdir -p "$BARE"; printf 'SECRET=1\n' > "$BARE/.env"
out=$(jq -nc --arg r "$BARE" '{hook_event_name:"PreToolUse",tool_name:"Read",cwd:$r,tool_input:{file_path:($r+"/.env")}}' | "$GUARD")
if [ -z "$out" ]; then pass "no .ai/: reading .env is not blocked"; else fail "no .ai/: reading .env should not be blocked" "$out"; fi

summary "ai-path-guard"
