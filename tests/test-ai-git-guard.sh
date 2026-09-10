#!/usr/bin/env bash
# ai-git-guard: fixtures in a scratch repo, plus the branch-resolution cases that
# only make sense with a real checked-out branch.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/ai-git-guard.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/repo"
mkdir -p "$ROOT/src/Payment"
git -C "$ROOT" init -q -b main
git -C "$ROOT" config user.email test@example.com
git -C "$ROOT" config user.name test
printf 'x\n' > "$ROOT/src/Payment/Gateway.php"
git -C "$ROOT" add src && git -C "$ROOT" commit -qm init

# Make sure the guard reads the shipped defaults, not a config the developer
# running the tests happens to have installed.
export HOME="$TMP/home"; mkdir -p "$HOME/.claude/hooks"

echo "== ai-git-guard (fixtures, on branch main)"
for f in "$PLUGIN_ROOT"/tests/fixtures/git-guard/*.json; do
    run_fixture "$GUARD" "$f" "$ROOT"
done

run_cmd() {  # run_cmd <command> -> prints allow|deny
    local out
    out=$(jq -nc --arg r "$ROOT" --arg c "$1" \
        '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}' | "$GUARD")
    if [ -z "$out" ]; then echo allow; else
        printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"'
    fi
}
expect() {  # expect <expected> <command> <label>
    local got; got=$(run_cmd "$2")
    [ "$got" = "$1" ] && pass "$3" || fail "$3" "expected $1, got $got"
}

echo "== ai-git-guard (branch resolution)"
expect deny  "git push"                     "bare 'git push' while on main is denied"
expect deny  "git push origin HEAD"         "'git push origin HEAD' while on main is denied"
expect deny  "git push origin main"         "explicit push to main is denied"
expect deny  "git merge feature/x"          "merging into main is denied"
expect deny  "git reset --hard origin/main" "hard reset on main is denied"

git -C "$ROOT" checkout -q -b feature/payment-fee
expect allow "git push"                        "bare 'git push' on a feature branch is allowed"
expect allow "git push origin HEAD"            "'git push origin HEAD' on a feature branch is allowed"
expect allow "git merge main"                  "merging main INTO a feature branch is allowed"
expect allow "git reset --hard origin/feature/payment-fee" "hard reset on a feature branch is allowed"
expect deny  "git push origin feature/x:main"  "pushing a feature branch onto main is denied"

echo "== ai-git-guard (wildcard add sees what git would stage)"
printf 'SECRET=1\n' > "$ROOT/.env"
expect deny  "git add ."                    "'git add .' with an untracked .env is denied"
expect deny  "git add -A"                   "'git add -A' with an untracked .env is denied"
rm -f "$ROOT/.env"
printf 'SECRET=\n' > "$ROOT/.env.example"
expect allow "git add ."                    "'git add .' with only .env.example is allowed"

echo "== ai-git-guard (outside a git repo)"
NOREPO="$TMP/plain"; mkdir -p "$NOREPO"
out=$(jq -nc --arg r "$NOREPO" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:"echo hello"}}' | "$GUARD")
[ -z "$out" ] && pass "a non-git command outside a repo is allowed" || fail "should allow" "$out"

summary "ai-git-guard"
