#!/usr/bin/env bash
# ai-path-guard: fixtures plus the "no .ai/ means no guard" property.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/ai-path-guard.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"

mkdir -p "$ROOT"/{.ai/state,.ai/policies,src,config,var,migrations}
printf 'SECRET=1\n' > "$ROOT/.env"
printf 'SECRET=\n'  > "$ROOT/.env.example"
printf '{}\n'       > "$ROOT/.ai/state/current.json"
printf '{}\n'       > "$ROOT/.ai/policies/path-guard.json"
printf 'x\n'        > "$ROOT/src/Service.php"
printf 'x\n'        > "$ROOT/var/dump-2026-09-01.sql"
printf 'x\n'        > "$ROOT/migrations/Version20260101.sql"
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

echo "== ai-path-guard (project WITHOUT .ai/ — every guard must be inert)"
BARE="$TMP/bare"; mkdir -p "$BARE"; printf 'SECRET=1\n' > "$BARE/.env"
out=$(jq -nc --arg r "$BARE" '{hook_event_name:"PreToolUse",tool_name:"Read",cwd:$r,tool_input:{file_path:($r+"/.env")}}' | "$GUARD")
if [ -z "$out" ]; then pass "no .ai/: reading .env is not blocked"; else fail "no .ai/: reading .env should not be blocked" "$out"; fi

summary "ai-path-guard"
