#!/usr/bin/env bash
# ai-path-guard: fixtures plus the "no .ai/ means no guard" property.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/ai-path-guard.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"

mkdir -p "$ROOT"/{.ai/state,.ai/policies,src,config,var,migrations} \
         "$ROOT"/{.claude/agents,.claude/rules,.codex,vendor/acme/pkg,node_modules/foo} \
         "$ROOT"/{.ai/rules,docs/sdlc}
printf 'SECRET=1\n' > "$ROOT/.env"
printf 'SECRET=\n'  > "$ROOT/.env.example"
printf '{}\n'       > "$ROOT/.ai/state/current.json"
printf '{}\n'       > "$ROOT/.ai/policies/path-guard.json"
printf 'x\n'        > "$ROOT/src/Service.php"
printf 'x\n'        > "$ROOT/var/dump-2026-09-01.sql"
printf 'x\n'        > "$ROOT/migrations/Version20260101.sql"
printf 'x\n'        > "$ROOT/.claude/agents/ai-reviewer.md"
printf 'x\n'        > "$ROOT/.ai/rules/payment.md"
printf 'x\n'        > "$ROOT/.claude/rules/payment.md"
printf 'x\n'        > "$ROOT/docs/sdlc/constitution.md"
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

echo "== ai-path-guard (the context guard is the runtime's to run, not the work's)"
hookrun=$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"python3 /home/u/.claude/hooks/context-guard.py"}}')
decide "with a task in flight, running it by hand is denied" deny "$hookrun"
out=$(printf '%s' "$hookrun" | AI_UNATTENDED=1 "$GUARD" 2>&1)
[ -z "$out" ] && pass "and AI_UNATTENDED lets a launcher through" || fail "the launcher should be allowed" "$out"
rm -f "$ROOT/.ai/state/current.json"
decide "with no task it is none of the guard's business" allow "$hookrun"
printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
# Reading, diffing, linting and testing these files is the ordinary work of the
# repository they live in, and none of it may be refused.
for c in "grep -n APPROVE_RE /home/u/.claude/hooks/context-guard.py" \
         "wc -l /home/u/.claude/hooks/context-guard.py" \
         "pylint /home/u/.claude/hooks/context-guard.py" \
         "git diff hooks/context-guard.py" \
         "bash tests/test-ai-path-guard.sh" \
         "diff hooks/context-guard.py /home/u/.claude/hooks/context-guard.py"; do
    out=$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:$c}}' | "$GUARD" 2>&1)
    [ -z "$out" ] || fail "'$c' must not be refused" "$(printf '%s' "$out" | head -c 160)"
done
pass "reading, diffing, linting and testing the hook files stays allowed"
for c in "grep -rn touch $ROOT/.ai/policies/path-guard.json" \
         "echo touch $ROOT/.ai/state/current.json" \
         "git log --grep chmod -- $ROOT/.ai/state/current.json"; do
    out=$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:$c}}' | "$GUARD" 2>&1)
    [ -z "$out" ] || fail "'$c' names a writer word, it does not run one" "$(printf '%s' "$out" | head -c 160)"
done
pass "and a writer's name in prose or a flag is not a write"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (--confirm-delete is a human's, not an agent's — F3)"
confirm_cmd=$(jq -c '.payload' "$PLUGIN_ROOT/tests/fixtures/path-guard/45-bash-update-confirm-delete.json" | sed "s|__ROOT__|$ROOT|g")
rm -f "$ROOT/.ai/state/current.json"
decide "no task in flight: still denied, a deletion needs no task to be irreversible" deny "$confirm_cmd"
printf '{}\n' > "$ROOT/.ai/state/current.json"
out=$(printf '%s' "$confirm_cmd" | AI_UNATTENDED=1 "$GUARD" 2>&1)
[ -z "$out" ] && pass "AI_UNATTENDED in the hook's own environment lets a launcher through" \
    || fail "the unattended launcher should be allowed" "$out"
out=$(printf '%s' "$confirm_cmd" | "$GUARD" 2>&1)
printf '%s' "$out" | grep -q "outside Claude Code or Codex" && printf '%s' "$out" | grep -q "terminal" \
    && pass "and the deny text names the terminal outside Claude Code or Codex" || fail "WHY_CONFIRM_DELETE is missing" "$out"
# Spellings the review found one token away from the fixtures (T-2026-09-27-003 review).
for c in "python3 -m \"update\" . --apply --confirm-delete x" "python3 -m 'update' . --apply --confirm-delete x" \
         "python3 -um update . --apply --confirm-delete x" "python3 -Bm update . --apply --confirm-delete x" \
         "python3 skills/project-update/update.py . --apply 2>&1 --confirm-delete x" \
         "python3 skills/project-update/update.py . --apply &>/tmp/o --confirm-delete x"; do
    decide "denied: $c" deny "$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')"
done
decide "but && still ends the segment" allow "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"python3 update.py . --apply && echo --confirm-delete"}}')"
# Reading the flag, running the dry runs, and every other --co… option stay allowed.
for c in "grep -n confirm-delete /home/u/.claude/skills/project-update/update.py" \
         "grep -n -- --confirm-delete /home/u/.claude/skills/project-update/update.py" \
         "python3 /home/u/.claude/skills/project-update/update.py . --adopt --cleanup" \
         "python3 /home/u/.claude/skills/project-update/update.py . --apply" \
         "ls --color" "foo --config x" 'git commit -m "adopt: gate"' \
         'cd "$ROOT" && pytest --co -q' '"$PY" -m pytest --co' "pytest tests/test_update.py --co" \
         "python3 tools/db_update.py --confirm" \
         "sed -n 1,5p update.py | grep -- --confirm-delete" \
         'git commit -m "update.py: --confirm-delete"'; do
    out=$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:$c}}' | "$GUARD" 2>&1)
    [ -z "$out" ] && pass "allowed: $c" || fail "'$c' must not be refused" "$(printf '%s' "$out" | head -c 160)"
done

echo "== ai-path-guard (the installed shared tree is frozen during a task, readable always)"
# T-2026-10-13-004, Q4=A: <home>/claude-agentic/ai/ and ai-path are the rules a
# run is judged by, like the policies they replace.
for home in .claude .codex; do
    SH="$TMP/user/$home/claude-agentic"
    tool() { jq -nc --arg r "$ROOT" --arg t "$1" --arg p "$2" '{hook_event_name:"PreToolUse",tool_name:$t,cwd:$r,tool_input:{file_path:$p}}'; }
    bash_cmd() { jq -nc --arg r "$ROOT" --arg c "$1" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}'; }
    printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
    decide "$home in a task: Write to the shared tree is denied" deny "$(tool Write "$SH/ai/policies/git.md")"
    decide "$home in a task: Edit of the shared tree is denied" deny "$(tool Edit "$SH/ai/policies/git.md")"
    decide "$home in a task: Write to ai-path is denied" deny "$(tool Write "$SH/ai-path")"
    decide "$home in a task: Read of the shared tree is allowed" allow "$(tool Read "$SH/ai/policies/git.md")"
    decide "$home in a task: running ai-path is allowed" allow "$(bash_cmd "$SH/ai-path policies/git.md")"
    decide "$home in a task: a sibling file is not frozen by this rule" allow "$(tool Write "$SH/ai-path.notes")"
    # T-2026-10-15-001 (known-risks a): the whole tree, replaced or removed in
    # one shell command, with nothing inside ai/ named on the line.
    decide "$home in a task: rm -rf of the bare shared tree is denied" deny "$(bash_cmd "rm -rf $SH/ai")"
    decide "$home in a task: the same rm followed by && is denied" deny "$(bash_cmd "rm -rf $SH/ai && echo done")"
    decide "$home in a task: and with no space before the && (review: patsub_replacement ate the &)" deny "$(bash_cmd "rm -rf $SH/ai&& echo done")"
    decide "$home in a task: and with a redirect glued to the path" deny "$(bash_cmd "rm -rf $SH/ai>/dev/null")"
    decide "$home in a task: mv over the bare shared tree is denied" deny "$(bash_cmd "mv $TMP/new $SH/ai")"
    decide "$home in a task: cp -r of a directory named ai into the home is denied" deny "$(bash_cmd "cp -r $TMP/new/ai $SH/")"
    decide "$home in a task: install into the shared tree is denied" deny "$(bash_cmd "install -m 644 $TMP/x $SH/ai/policies/git.md")"
    decide "$home in a task: cp to a sibling that merely starts with ai is allowed" allow "$(bash_cmd "cp $TMP/x $SH/ai-notes")"
    rm -f "$ROOT/.ai/state/current.json"
    decide "$home no task: Write to the shared tree is allowed" allow "$(tool Write "$SH/ai/policies/git.md")"
    decide "$home no task: Write to ai-path is allowed" allow "$(tool Write "$SH/ai-path")"
    decide "$home no task: rm -rf of the shared tree is the guard's business only in a task" allow "$(bash_cmd "rm -rf $SH/ai")"
done
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (.ai/agents/ is an override path, frozen like the policies)"
# T-2026-10-15-001 (known-risks b): a project copy under .ai/agents/ shadows the
# shared contract, so dropping one mid-task rewrites the reviewer's own rules.
agent_override() { jq -nc --arg r "$ROOT" --arg t "$1" '{hook_event_name:"PreToolUse",tool_name:$t,cwd:$r,tool_input:{file_path:($r+"/.ai/agents/reviewer.md")}}'; }
printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide "in a task: Write to .ai/agents/ is denied" deny "$(agent_override Write)"
decide "in a task: Read of .ai/agents/ is allowed" allow "$(agent_override Read)"
rm -f "$ROOT/.ai/state/current.json"
decide "no task: Write to .ai/agents/ is allowed" allow "$(agent_override Write)"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (parent directories and segmentation, in and out of a task — known-risks a1-a3)"
# T-2026-10-15-002: a directory above a protected file is the file, for a removal
# or a move; protected files count always, the frozen runtime only in a task.
printf '{}\n' > "$ROOT/.ai/state/session.json"
HOME_T="$TMP/user"; mkdir -p "$HOME_T/.claude/hooks" "$HOME_T/.claude/claude-agentic/ai/policies"
printf 'x\n' > "$HOME_T/.claude/hooks/ai-path-guard.sh"
printf 'x\n' > "$HOME_T/.claude/claude-agentic/ai/policies/git.md"
decide_home() {  # decide_home <description> <expected> <command> — HOME is the test home
    local name="$1" expect="$2" out decision
    out=$(jq -nc --arg r "$ROOT" --arg c "$3" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}' \
          | env -u CLAUDE_CONFIG_DIR -u CODEX_HOME HOME="$HOME_T" "$GUARD" 2>&1)
    if [ -z "$out" ]; then decision=allow
    else decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"' 2>/dev/null || echo malformed); fi
    if [ "$decision" = "$expect" ]; then pass "$name"
    else fail "$name" "expected $expect, got $decision${out:+ — $(printf '%s' "$out" | head -c 200)}"; fi
}
printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide_home "in a task: rm -rf ~/.claude/claude-agentic/ is denied" deny 'rm -rf ~/.claude/claude-agentic/'
decide_home "in a task: rm -rf \$HOME/.claude/claude-agentic is denied" deny 'rm -rf $HOME/.claude/claude-agentic'
decide_home "in a task: rm -rf \${HOME}/.claude is denied" deny 'rm -rf ${HOME}/.claude'
decide_home "in a task: rm -rf of a path with ./ and // in it is denied" deny 'rm -rf ~/.claude/./claude-agentic//ai'
decide_home "in a task: cp f.txt ~/ stays allowed" allow 'cp f.txt ~/'
# The STRONG review of T-2026-10-15-002: each of these was denied before the
# segmentation and must stay denied — a here-string or an arithmetic << is no
# heredoc, and a shell's -c string runs wherever the shell sits in the segment.
for c in $'read -r a b <<< "$x"\nrm -f .ai/state/current.json' $'grep foo <<<bar\nrm -f .ai/state/current.json' \
         $'read -r a <<< "$x"\nmv src/a.txt .claude/settings.json' $'read -r a <<< "$x"\nchmod 000 .ai/state/current.json' \
         $'echo $((1<<2))\nrm -f .ai/state/current.json' $'(( x <<= 1 ))\nrm -f .ai/state/current.json' \
         "/bin/sh -c 'cd /tmp; rm -f .ai/state/current.json'" "xargs sh -c 'true; rm -f .ai/state/current.json'" \
         "find . -exec sh -c 'true; rm -f .ai/state/current.json' \\;" "nice -n 5 bash -c 'true; rm -f .ai/state/current.json'" \
         "timeout 5 sh -c 'x; rm -f .ai/state/current.json'" "bash -c \$'true; rm -f .ai/state/current.json'"; do
    decide_home "in a task: still denied: ${c//$'\n'/⏎}" deny "$c"
done
out=$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:"rm -rf .ai/state"}}' | "$GUARD" 2>&1)
printf '%s' "$out" | grep -q 'current\.json\|session\.json' && pass "in a task: the deny names the file found under the directory" \
    || fail "the deny should name the protected file" "$out"
rm -f "$ROOT/.ai/state/current.json"
decide_home "no task: rm -rf .ai/state/ is still denied, it holds a control file" deny 'rm -rf .ai/state/'
decide_home "no task: { rm -f .ai/state/session.json; } is denied" deny '{ rm -f .ai/state/session.json; }'
decide_home "no task: rm -rf ~/.claude is denied, it holds the guard's own hooks" deny 'rm -rf ~/.claude'
decide_home "no task: rm -rf .claude is allowed, the runtime is frozen only in a task" allow 'rm -rf .claude'
decide_home "no task: mv .claude /tmp/x is allowed" allow 'mv .claude /tmp/x'
decide_home "no task: rm -rf ~/.claude/claude-agentic/ is allowed" allow 'rm -rf ~/.claude/claude-agentic/'
decide_home "no task: rm -rf vendor node_modules is allowed" allow 'rm -rf vendor node_modules'
rm -f "$ROOT/.ai/state/session.json"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (project WITHOUT .ai/ — every guard must be inert)"
BARE="$TMP/bare"; mkdir -p "$BARE"; printf 'SECRET=1\n' > "$BARE/.env"
out=$(jq -nc --arg r "$BARE" '{hook_event_name:"PreToolUse",tool_name:"Read",cwd:$r,tool_input:{file_path:($r+"/.env")}}' | "$GUARD")
if [ -z "$out" ]; then pass "no .ai/: reading .env is not blocked"; else fail "no .ai/: reading .env should not be blocked" "$out"; fi

summary "ai-path-guard"
