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
grep -q "Approval happens outside the agent" <<<"$out" \
    && pass "and the deny text teaches the human what to do" || fail "WHY_APPROVE is missing" "$out"
grep -q "AI_UNATTENDED=1 in the launcher" <<<"$out" \
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
grep -q "outside Claude Code or Codex" <<<"$out" && grep -q "terminal" <<<"$out" \
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

echo "== ai-path-guard (a backslash-newline does not split the gate rules)"
printf '{"current_stage":"human_approval","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
decide "state.py \\⏎approve --by x is denied" deny "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"python3 /home/u/.claude/skills/ai-task/state.py \\\napprove --by x"}}')"
decide "python3 \\⏎context-guard.py is denied" deny "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"python3 \\\n/home/u/.claude/hooks/context-guard.py"}}')"
# Spellings the T-2026-10-15-003 reviews found past APPROVE_RE.
for c in "python3 /h/state.py --root \"/Store/Claude Plugins/p\" approve --by x" \
         "python3 /h/state.py --root '/a b' approve --by x" \
         "python3 /h/state.py \"approve\" --by x" "python3 /h/state.py -- approve --by x" \
         "S=/h/state.py; (\$S approve --by x)" "echo \$(\$S approve --by x)" "echo \`\$S approve --by x\`"; do
    decide "denied: $c" deny "$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')"
done
for c in "grep -n approve skills/ai-task/state.py" "python3 /h/state.py get --field human_approval"; do
    decide "allowed: $c" allow "$(jq -nc --arg r "$ROOT" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')"
done
decide "but grep x \\⏎context-guard.py is a read, not a run" allow "$(jq -nc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
    tool_input:{command:"grep -n APPROVE_RE \\\nhooks/context-guard.py"}}')"
printf '{}\n' > "$ROOT/.ai/state/current.json"

echo "== ai-path-guard (--confirm-delete is denied from a cwd with no .ai/)"
NOAI="$TMP/no-ai-here"; mkdir -p "$NOAI"
decide "update.py /abs/p --apply --confirm-delete x from a cwd without .ai/ is denied" deny \
    "$(jq -nc --arg r "$NOAI" --arg p "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:("python3 /home/u/.claude/skills/project-update/update.py " + $p + " --apply --confirm-delete x")}}')"
for c in "ls -la" "python3 /home/u/.claude/skills/project-update/update.py $ROOT --apply" "cat README.md"; do
    decide "still allowed without .ai/: $c" allow "$(jq -nc --arg r "$NOAI" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')"
done
# A variable head after ; & | ( or a backtick (T-2026-10-15-003 security review).
for c in "U=/x/update.py; true;\$U --apply --confirm-delete bob" "true&&\$U --apply --confirm-delete bob" \
         "(\$U --apply --confirm-delete bob)" "echo \$(\$U --apply --confirm-delete bob)" \
         "echo \`\$U --apply --confirm-delete bob\`"; do
    decide "denied without .ai/: $c" deny "$(jq -nc --arg r "$NOAI" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')"
done
decide "and a Write there stays none of the guard's business" allow \
    "$(jq -nc --arg r "$NOAI" '{hook_event_name:"PreToolUse",tool_name:"Write",cwd:$r,tool_input:{file_path:($r+"/x.txt")}}')"

echo "== ai-path-guard (a padded line cannot outrun the hook timeout)"
for unit in a 'a '; do
    # Through stdin: one exec argument is capped at 128 KB, so --arg would fail.
    pad() { printf '%*s' 200000 '' | sed "s/ /$unit/g" | head -c 200000; }
    long_hit=$(pad | jq -Rc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:("python3 update.py . --apply " + . + " --co x")}}')
    long_miss=$(pad | head -c 20000 | jq -Rc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,
        tool_input:{command:("echo " + .)}}')
    [ "${#long_hit}" -gt 200000 ] || fail "the padded payload was not built" "${#long_hit} bytes"
    t0=$(date +%s%N)
    decide "a 200 KB line ('$unit' padding) holding update and --co is denied" deny "$long_hit"
    ms=$(( ($(date +%s%N) - t0) / 1000000 ))
    [ "$ms" -lt 1000 ] && pass "and within a second (${ms} ms)" || fail "the long-line deny took ${ms} ms"
    decide "a 20 KB line ('$unit' padding) without them is allowed" allow "$long_miss"
done
# The variable head needs no `update` on the long line (security review).
var_hit=$( { printf 'U=/x/update.py\n'; for i in $(seq 8000); do printf '$U --co '; done; printf '; $U --apply --confirm-delete bob'; } \
    | jq -Rsc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:.}}')
t0=$(date +%s%N)
decide "a 64 KB line of \$U --co … --apply is denied" deny "$var_hit"
ms=$(( ($(date +%s%N) - t0) / 1000000 ))
[ "$ms" -lt 1000 ] && pass "and within a second (${ms} ms)" || fail "the variable-head deny took ${ms} ms"
# A minified line full of --color and the word update is not a confirmed deletion (review).
css=$( { printf "cat > dist/app.min.css <<'EOF'\n"; for i in $(seq 600); do printf 'function update(){}:root{--color-%d:#fff}' "$i"; done; printf '\nEOF'; } \
    | jq -Rsc --arg r "$NOAI" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:.}}')
decide "a 25 KB minified CSS heredoc naming update and --color is allowed" allow "$css"
# T-2026-10-15-004 (known-risks: "The path guard is quadratic on long lines"):
# ere_match hands a line over 4096 characters to grep, and the forking work
# per path and per token is capped, so no padded command outruns the timeout.
timed() {   # timed <name> <expect> <payload> <max-ms>
    local t0 ms
    t0=$(date +%s%N)
    decide "$1" "$2" "$3"
    ms=$(( ($(date +%s%N) - t0) / 1000000 ))
    [ "$ms" -lt "$4" ] && pass "and within $4 ms (${ms} ms)" || fail "$1 took ${ms} ms" "budget $4 ms"
}
bash_stdin() { jq -Rsc --arg r "$ROOT" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:.}}'; }
pad_a() { printf '%*s' "$1" '' | tr ' ' a; }
names() { for i in $(seq 3000); do printf ' file%d.txt' "$i"; done; }
words() { for i in $(seq "$1"); do printf ' w%d' "$i"; done; }
timed "a 40 KB echo is allowed" allow "$(printf 'echo %s' "$(pad_a 40000)" | bash_stdin)" 1000
timed "a 40 KB sh -c string is allowed" allow "$(printf "sh -c '%s'" "$(pad_a 40000)" | bash_stdin)" 1000
timed "a 200 KB echo followed by cat .env is denied" deny "$(printf 'echo %s; cat .env' "$(pad_a 200000)" | bash_stdin)" 1000
timed "rm -f of 3000 files and a task state file is denied" deny "$(printf 'rm -f%s .ai/state/current.json' "$(names)" | bash_stdin)" 5000
out=$(printf 'rm -f%s' "$(names)" | bash_stdin)
t0=$(date +%s%N); printf '%s' "$out" | "$GUARD" >/dev/null 2>&1; ms=$(( ($(date +%s%N) - t0) / 1000000 ))
[ "$ms" -lt 5000 ] && pass "rm -f of 3000 ordinary files is decided within 5 s (${ms} ms)" || fail "rm -f of 3000 files took ${ms} ms"
timed "a 200 KB argument glued to a protected path is denied" deny "$(printf 'echo %s/.ai/state/current.json' "$(pad_a 200000)" | bash_stdin)" 1000
timed "a 200 KB argument beside a frozen path, with no task, is allowed" allow "$(printf 'echo %s .claude/settings.json' "$(pad_a 200000)" | bash_stdin)" 1000
rm -f "$ROOT/.ai/state/current.json"
cap=$(printf 'ls%s' "$(for i in $(seq 300); do printf ' .claude/agents/x%d.md' "$i"; done)" | bash_stdin)
decide "ls of 300 frozen paths is denied by the work cap" deny "$cap"
printf '%s' "$cap" | "$GUARD" | grep -q 'names more paths than the guard can check' \
    && pass "and the deny says why" || fail "the work-cap deny names its reason"
# Prose is not counted (STRONG review): only tokens that hit the pre-filter.
timed "a 300-word heredoc that mentions .env.example is allowed" allow \
    "$(printf "cat > docs/setup.md <<'EOF'\ncopy .env.example first.%s\nEOF" "$(words 300)" | bash_stdin)" 3000
timed "a 300-word commit message that mentions .env.example is allowed" allow \
    "$(printf 'git commit -m "copy .env.example%s"' "$(words 300)" | bash_stdin)" 3000
# A padded mover operand (STRONG review BLOCKER: the operand grep was quadratic in UTF-8).
timed "rm -f of a 200 KB operand and the task state file is denied" deny \
    "$(printf 'rm -f %s/.ai/state/x.json .ai/state/current.json' "$(pad_a 200000)" | bash_stdin)" 2000
# A deny reason over 128 KB still denies (review HIGH: jq --arg could not exec).
timed "cp of a 140 KB-named file and another into .ai/state/ is denied" deny \
    "$(printf 'cp %s.json x.json .ai/state/' "$(pad_a 140000)" | bash_stdin)" 3000
# A long glob collapses to a short path (review HIGH).
STATECWD=$(jq -nc --arg r "$ROOT/.ai/state" --arg c "echo hi > [$(pad_a 4200 | tr a c)]urrent.json; echo .env.example" \
    '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')
decide "a redirect into a 4200-character glob for current.json is denied" deny "$STATECWD"
# One operand that does not resolve must not unresolve the rest (review HIGH).
mkdir -p "$ROOT/lnk"; ln -sfn "$ROOT/.ai/state" "$ROOT/lnk/st"; ln -sfn loopB "$ROOT/lnk/loopA"; ln -sfn loopA "$ROOT/lnk/loopB"
loop=$(jq -nc --arg r "$ROOT/lnk" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:"mv current.json loopA/x .env.example st/"}}')
decide "mv into a symlinked state directory beside a symlink loop is denied" deny "$loop"
# Work nobody counts is on the clock too (re-review BLOCKER: 25000 plain operands, 14 s).
many=$(for i in $(seq 25000); do printf ' /f%d' "$i"; done)
timed "mv of 25000 sources and the task state file is denied" deny "$(printf 'mv%s .ai/state/current.json /d' "$many" | bash_stdin)" 8000
out=$(printf 'mv%s /d' "$many" | bash_stdin)
t0=$(date +%s%N); printf '%s' "$out" | "$GUARD" >/dev/null 2>&1; ms=$(( ($(date +%s%N) - t0) / 1000000 ))
[ "$ms" -lt 8000 ] && pass "mv of 25000 plain sources is decided within 8 s (${ms} ms)" || fail "mv of 25000 sources took ${ms} ms"
# Inside every count the work is still bounded by the clock (review HIGH: 11.4 s).
WC="$TMP/worst"; mkdir -p "$WC/.ai/policies"
for i in $(seq 16); do mkdir -p "$WC/d$i/.claude/agents"; for j in $(seq 50); do : > "$WC/d$i/.claude/agents/a$j.md"; done; done
worst="rm -f$(for i in $(seq 63); do printf ' .claude/agents/x%d.md' "$i"; done); rm -rf$(for i in $(seq 16); do printf ' d%d' "$i"; done); rm -f .ai/policies/path-guard.json"
timed "63 frozen operands, 16 full directory scans and a policy file are denied" deny \
    "$(jq -nc --arg r "$WC" --arg c "$worst" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}')" 8000
timed "cat .env.example and 60 more tokens is allowed (the cap does not reach normal lines)" allow \
    "$(printf 'cat .env.example%s' "$(words 60)" | bash_stdin)" 3000
# The movers caps: 64 operands that need classify, 16 directory scans.
frozen() { for i in $(seq "$1"); do printf ' .claude/agents/x%d.md' "$i"; done; }
rm -f "$ROOT/.ai/state/current.json"
decide "rm -f of 30 frozen paths with no task is allowed" allow "$(printf 'rm -f%s' "$(frozen 30)" | bash_stdin)"
printf 'rm -f%s' "$(frozen 70)" | bash_stdin | "$GUARD" | grep -q 'names more paths than the guard can check' \
    && pass "rm -f of 70 frozen paths is denied by the work cap" || fail "rm -f of 70 frozen paths is denied by the work cap"
mkdir -p "$TMP/scan"; for i in $(seq 20); do mkdir -p "$TMP/scan/d$i"; done
dirs() { for i in $(seq "$1"); do printf ' %s/scan/d%d' "$TMP" "$i"; done; }
decide "rm -rf of 16 directories is allowed" allow "$(printf 'rm -rf%s' "$(dirs 16)" | bash_stdin)"
decide "rm -rf of 17 directories is denied by the work cap" deny "$(printf 'rm -rf%s' "$(dirs 17)" | bash_stdin)"
# T-2026-10-20-001 (known-risks: padded sh -c segments): segments_of re-reads
# at most 64 sh -c / eval strings, and every segment loop is on the clock.
rep() { local i; for i in $(seq "$2"); do printf '%s' "$1"; done; }
timed "6000 sh -c segments and rm of the task state file are denied" deny \
    "$( { rep 'sh -c x; ' 6000; printf 'rm -f .ai/state/current.json'; } | bash_stdin)" 2000
timed "6000 eval segments and rm of the task state file are denied" deny \
    "$( { rep 'eval x; ' 6000; printf 'rm -f .ai/state/current.json'; } | bash_stdin)" 2000
decide "64 sh -c segments and rm -f a.txt are allowed" allow \
    "$( { rep 'sh -c x; ' 64; printf 'rm -f a.txt'; } | bash_stdin)"
{ rep 'sh -c x; ' 65; printf 'rm -f a.txt'; } | bash_stdin | "$GUARD" | grep -q 'names more paths than the guard can check' \
    && pass "65 sh -c segments and rm -f a.txt are denied by the work cap" \
    || fail "65 sh -c segments and rm -f a.txt are denied by the work cap"
{ rep 'sh -c x; ' 63; printf "sh -c 'rm -f .ai/state/current.json'"; } | bash_stdin | "$GUARD" \
    | grep -q 'removal of a claude-agentic control file' \
    && pass "the 64th sh -c string is still read: its rm of the state file is denied" \
    || fail "the 64th sh -c string is still read: its rm of the state file is denied"
timed "100000 one-word segments and rm -f a.txt are allowed" allow \
    "$( { rep 'x;' 100000; printf 'rm -f a.txt'; } | bash_stdin)" 3000
timed "100000 one-word segments and rm of the task state file are denied" deny \
    "$( { rep 'x;' 100000; printf 'rm -f .ai/state/current.json'; } | bash_stdin)" 3000
# T-2026-10-21-001 (known-risks: many mover segments reach the 6 s clock): the
# movers pass checks its segments in batches, one realpath and one loose_hits
# per 32 KB of candidates, not one per segment, and every decision keeps its
# reason and its place.
timed "1000 rm segments and rm -f a.txt are allowed" allow \
    "$( { rep 'rm x; ' 1000; printf 'rm -f a.txt'; } | bash_stdin)" 2000
timed "1000 rm segments and rm of the task state file are denied" deny \
    "$( { rep 'rm x; ' 1000; printf 'rm -f .ai/state/current.json'; } | bash_stdin)" 2000
out=$( { rep 'rm x; ' 1000; printf 'rm -f .ai/state/current.json'; } | bash_stdin | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "1000 rm segments: the deny names the control file, not the work cap" "$(head -c 200 <<<"$out")"
globop="$(pad_a 4097)*"
out=$(printf 'rm -f .ai/state/current.json; rm -f %s' "$globop" | bash_stdin | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "a control-file deny comes before a later segment's long glob operand deny" \
    || fail "a control-file deny comes before a later segment's long glob operand deny" "$(head -c 200 <<<"$out")"
out=$(printf 'rm -f %s; rm -f .ai/state/current.json' "$globop" | bash_stdin | "$GUARD")
grep -q 'operand that holds a glob or expansion character' <<<"$out" \
    && pass "a long glob operand deny comes before a later segment's control-file deny" \
    || fail "a long glob operand deny comes before a later segment's control-file deny" "$(head -c 200 <<<"$out")"
out=$(printf 'rm x; mv a.txt .ai/state/current.json' | bash_stdin | "$GUARD")
grep -q 'copy or move into a claude-agentic control file' <<<"$out" \
    && pass "a later segment's mv destination is still a copy or move into, not a move of" \
    || fail "a later segment's mv destination is still a copy or move into, not a move of" "$(head -c 200 <<<"$out")"
for c in "mv loopA/x y; mv current.json .env.example st/" "mv current.json .env.example st/; mv loopA/x y"; do
    out=$(jq -nc --arg r "$ROOT/lnk" --arg c "$c" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}' | "$GUARD")
    grep -q 'claude-agentic control file' <<<"$out" \
        && pass "$c: a symlink loop in one segment does not hide a symlinked state directory in another" \
        || fail "$c: a symlink loop in one segment does not hide a symlinked state directory in another" "$(head -c 200 <<<"$out")"
done
# Its STRONG review: one realpath for the whole line was a unit the clock could
# not stop (400 segments of a symlink chain ran past 20 s; HEAD denied by the
# clock in 5.1 s), and an early segment's deny waited for the whole line (HEAD
# 0.2 s with the control-file reason, then 5.8 s with the work cap's).
mkdir -p "$ROOT/chain"; ln -sfn . "$ROOT/chain/c"
chain="chain/$(rep c/ 2000)x"
timed "400 rm segments of a 4 KB symlink chain and rm of the task state file are denied" deny \
    "$( { rep "rm $chain; " 400; printf 'rm -f .ai/state/current.json'; } | bash_stdin)" 8000
pl=$( { printf 'rm -f .ai/state/current.json; '; rep 'rm x; ' 20000; printf 'rm y'; } | bash_stdin)
timed "rm of the task state file before 20000 rm segments is denied" deny "$pl" 2000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before 20000 rm segments: the deny names the control file" "$(head -c 200 <<<"$out")"
# Its re-review: a batch was checked only when its candidates filled 32 KB, so
# segments that add none (`rm -f;`) or one behind thousands of options left an
# early deny waiting for the end of the line (HEAD 1.1 s with the control-file
# reason, then 5 s with the work cap's). One segment past ARG_MAX, which HEAD
# denied by the work cap once its realpath failed with E2BIG, is checked
# candidate by candidate now: allowed when none of them is protected.
pl=$( { printf 'rm -f .ai/state/current.json; '; rep 'rm -f; ' 150000; printf 'rm y'; } | bash_stdin)
timed "rm of the task state file before 150000 rm segments with no operand is denied" deny "$pl" 3000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before 150000 operandless rm segments: the deny names the control file" "$(head -c 200 <<<"$out")"
pl=$( { printf 'rm -f .ai/state/current.json; '; rep "rm $(rep '-f ' 2000)y; " 200; } | bash_stdin)
timed "rm of the task state file before 200 rm segments of 2000 options is denied" deny "$pl" 3000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before 200 option-heavy rm segments: the deny names the control file" "$(head -c 200 <<<"$out")"
deep="$ROOT/$(for i in 1 2 3 4 5 6 7 8; do pad_a 200; printf /; done)"; mkdir -p "$deep"
decide "rm of 1500 files under a 1600-character cwd is allowed: past ARG_MAX, every candidate is checked" allow \
    "$(printf 'rm%s' "$(words 1500)" | jq -Rsc --arg r "${deep%/}" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:.}}')"
# Its second re-review: a later segment slow to parse still held an early deny.
# Stripping quotes one character at a time cost 0.27 s per 4 KB operand of
# `""`: the state file before one 123 KB segment of 30 such operands was denied
# by HEAD in 0.29 s with the control-file reason, by R2 in 6.0 s with the work
# cap's. The strip is linear now, and a segment that would take the batch's text
# past 32 KB is parsed only after the batch is checked.
qop="a$(rep '""' 2047)"
pl=$( { printf 'rm -f .ai/state/current.json; rm'; rep " $qop" 30; } | bash_stdin)
timed "rm of the task state file before a 123 KB segment of quote-padded operands is denied" deny "$pl" 2000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before a 123 KB quote-padded segment: the deny names the control file" "$(head -c 200 <<<"$out")"
pl=$( { rep "rm $qop; " 16; printf 'rm -f .ai/state/current.json; '; rep "rm $qop; " 8; } | bash_stdin)
timed "rm of the task state file among 24 quote-padded rm segments is denied" deny "$pl" 2000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file among 24 quote-padded segments: the deny names the control file" "$(head -c 200 <<<"$out")"
decide "rm of the task state file inside runs of both quote kinds is denied" deny \
    "$(printf '%s' "rm \"'\".ai/state/current.json\"'\"" | bash_stdin)"
decide "cp -t into the state directory inside runs of both quote kinds is denied" deny \
    "$(printf '%s' "cp -t \"'\".ai/state\"'\" current.json" | bash_stdin)"
decide "an operand of quotes only names no file" allow "$(printf '%s' "rm '\"\"' a.txt" | bash_stdin)"
# Its third re-review: the batch was bounded by text, not by the absolute paths
# a segment's candidates make. Under a 3.3 KB cwd one later `rm` of 5000 short
# operands (29 KB of text) made 16 MB of them, built and resolved before the
# earlier deny was checked (HEAD 0.11 s with the control-file reason, R3 5.6 s
# with the work cap's). A destination multiplies every source the same way.
deep2="$ROOT/$(for i in $(seq 16); do pad_a 200; printf /; done)"; mkdir -p "$deep2"
pl=$(printf 'rm -f %s/.ai/state/current.json; rm%s' "$ROOT" "$(words 5000)" \
    | jq -Rsc --arg r "${deep2%/}" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:.}}')
timed "rm of the task state file before an rm of 5000 operands under a 3.3 KB cwd is denied" deny "$pl" 2000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before 5000 operands under a 3.3 KB cwd: the deny names the control file" "$(head -c 200 <<<"$out")"
pl=$( { printf 'rm -f .ai/state/current.json; mv'; words 3000; printf ' d/%s' "$(pad_a 4000)"; } | bash_stdin)
timed "rm of the task state file before an mv of 3000 sources into a 4 KB destination is denied" deny "$pl" 2000
out=$(printf '%s' "$pl" | "$GUARD")
grep -q 'removal of a claude-agentic control file' <<<"$out" \
    && pass "and the deny names the control file, not the work cap" \
    || fail "the state file before 3000 sources into a 4 KB destination: the deny names the control file" "$(head -c 200 <<<"$out")"
# T-2026-10-20-002 (known-risks: the candidate filter and its regex ran in two
# locales): both are bytewise, and the regex names the UTF-8 bytes of the 15
# multibyte characters glibc's [[:space:]] matches, so a line that splits
# /bin/sh, -c and the string on one of them through IFS is read in any locale.
sh_ifs() { printf "set -- '/bin/sh%s-c%srm -f %s'; IFS='%s'; \$1" "$1" "$1" "$2" "$1"; }
for b in 1680:'\xe1\x9a\x80' 2000:'\xe2\x80\x80' 2001:'\xe2\x80\x81' 2002:'\xe2\x80\x82' \
         2003:'\xe2\x80\x83' 2004:'\xe2\x80\x84' 2005:'\xe2\x80\x85' 2006:'\xe2\x80\x86' \
         2008:'\xe2\x80\x88' 2009:'\xe2\x80\x89' 200A:'\xe2\x80\x8a' 2028:'\xe2\x80\xa8' \
         2029:'\xe2\x80\xa9' 205F:'\xe2\x81\x9f' 3000:'\xe3\x80\x80'; do
    cp=${b%%:*} u=$(printf "${b#*:}")
    decide "IFS=U+$cp running /bin/sh -c 'rm of the task state file' is denied" deny \
        "$(sh_ifs "$u" .ai/state/current.json | bash_stdin)"
    decide "echo of /bin/sh -c 'rm of the task state file' with U+$cp blanks is denied" deny \
        "$(printf "echo /bin/sh%s-c%s'rm -f .ai/state/current.json'" "$u" "$u" | bash_stdin)"
    decide "IFS=U+$cp running /bin/sh -c 'rm -f a.txt' is allowed" allow "$(sh_ifs "$u" a.txt | bash_stdin)"
done
LC_ALL=C decide "under LC_ALL=C, IFS=U+3000 running /bin/sh -c 'rm of the task state file' is denied" deny \
    "$(sh_ifs $'\xe3\x80\x80' .ai/state/current.json | bash_stdin)"
# U+2007 is not in that set: like IFS=, it stays out of reach (known-risks).
decide "IFS=U+2007 is not a blank: its /bin/sh -c split is allowed, as before" allow \
    "$(sh_ifs $'\xe2\x80\x87' .ai/state/current.json | bash_stdin)"
# T-2026-10-20-003 (known-risks: sh -c spellings segments_of does not read): a
# long option, -o/-O and its name, --, -, -e or a redirection beside -c, and a
# quoted or backslashed command word all still run the string.
for p in "bash --norc -c" "bash -o posix -c" "bash +o posix -c" "bash -O extglob -c" \
         "bash -eo pipefail -c" "bash --rcfile /dev/null -c" "sh -c --" "sh -c -" "sh -c -e" \
         "sh -c 2>/dev/null" "sh -c 2> /dev/null" "sh -c >/dev/null 2>&1" "sh -c &>/dev/null" \
         "sh </dev/null -c" "'sh' -c" '"bash" -c' '\sh -c' "'/bin/sh' -c"; do
    decide "$p 'rm of the task state file' is denied" deny \
        "$(printf "%s 'rm -f .ai/state/current.json'" "$p" | bash_stdin)"
done
for p in "bash --norc -c" "bash -o posix -c" "sh -c --" "sh -c 2>/dev/null" "'sh' -c" '\sh -c'; do
    decide "$p 'rm -f a.txt' is allowed" allow "$(printf "%s 'rm -f a.txt'" "$p" | bash_stdin)"
done
decide "sh -c 'x' 2>/dev/null is allowed" allow "$(printf "sh -c 'x' 2>/dev/null" | bash_stdin)"
decide "sh -c echo -n hi is allowed" allow "$(printf 'sh -c echo -n hi' | bash_stdin)"
# Its review: a name after -c, a target of quoted and bare pieces, and a match
# that begins at an argument (-exec is a cluster with a c) all still deny.
for p in "bash -c -o posix" "bash -c +O extglob" "bash -c -eo pipefail" "bash -c -e -o pipefail" \
         "bash -c 2>/dev/null -o posix" 'sh -c 2>"$HOME"/x' 'sh -c 2>/tmp/x\ y' \
         "find . -name 'sh' -exec sh -c" "find . -name sh 2>/dev/null -exec sh -c" \
         "find . -path '*/sh' -exec bash -c" "sudo -u 'sh' -c x bash -c"; do
    decide "$p 'rm of the task state file' is denied" deny \
        "$(printf "%s 'rm -f .ai/state/current.json'" "$p" | bash_stdin)"
done
decide "a bash -c inside a sh -c string, rm of the task state file, is denied" deny \
    "$(printf "sh -c 'echo; bash -c \"rm -f .ai/state/current.json\"'" | bash_stdin)"
decide "bash -c -o posix 'rm -f a.txt' is allowed" allow "$(printf "bash -c -o posix 'rm -f a.txt'" | bash_stdin)"
decide "find -name 'sh' -exec sh -c 'rm -f a.txt' is allowed" allow \
    "$(printf "find . -name 'sh' -exec sh -c 'rm -f a.txt' \\\\;" | bash_stdin)"
timed "200 KB of ' sh 2>' words and rm of the task state file are denied" deny \
    "$( { printf echo; rep ' sh 2>' 33333; printf ' X sh -c x; rm -f .ai/state/current.json'; } | bash_stdin)" 2000
# Its second pass: a flag that takes no word is not counted before -c, as on
# HEAD; a word stops at a multibyte blank, not only at an ASCII one, and keeps
# the other characters whose first byte a multibyte blank shares.
for p in "bash $(rep '-e ' 9)-c" "bash -e -u -x -v -e -u -x -v -e -c" "sh -a -b -e -f -h -m -u -v -x -c" \
         "bash $(rep '-e ' 20)-c" "bash -o posix $(rep '-e ' 9)-O extglob -c" \
         $'bash 2>/tmp/\xe2\x80\xa6\xe3\x81\x82\xe2\x86\x92\xe1\x9a\x81x -c'; do
    decide "$p 'rm of the task state file' is denied" deny \
        "$(printf "%s 'rm -f .ai/state/current.json'" "$p" | bash_stdin)"
done
decide "bash with 9 -e before -c and 'rm -f a.txt' is allowed" allow \
    "$(printf "bash %s-c 'rm -f a.txt'" "$(rep '-e ' 9)" | bash_stdin)"
u=$'\xe3\x80\x80'
timed "140 KB of U+3000 ' sh -o x' words and rm of the task state file are denied" deny \
    "$( { printf echo; rep "${u}sh$u-o${u}x" 10000; printf ' X sh -c x; rm -f .ai/state/current.json'; } | bash_stdin)" 2000
timed "140 KB of U+3000 ' sh 2>x' words and rm -f a.txt are allowed" allow \
    "$( { printf echo; rep "${u}sh${u}2>x" 13000; printf ' X sh -c x; rm -f a.txt'; } | bash_stdin)" 2000
# Its fourth pass: a quoted piece holds no blank. With one, ` sh 2>\''` (\' is
# escaped outside a quote, closes '…', is literal in "…") kept every start's
# target quoted to the end of the line: 11.4 s at 200 KB. A quoted target with
# a blank is therefore not read, as on HEAD (known-risks).
timed "200 KB of ' sh 2>' words each followed by \\'' and rm of the task state file are denied" deny \
    "$( { printf echo; rep " sh 2>\\''" 22000; printf ' X sh -c x; rm -f .ai/state/current.json'; } | bash_stdin)" 2000
timed "140 KB of the same with U+3000 blanks and rm -f a.txt are allowed" allow \
    "$( { printf echo; rep "${u}sh${u}2>\\''" 11000; printf ' X sh -c x; rm -f a.txt'; } | bash_stdin)" 2000
decide "bash 2>'/tmp/a b' -c 'rm of the task state file' is allowed, as on HEAD" allow \
    "$(printf "bash 2>'/tmp/a b' -c 'rm -f .ai/state/current.json'" | bash_stdin)"

echo "== ai-path-guard (the installed shared tree is frozen during a task, readable always)"
# T-2026-10-13-004, Q4=A: <home>/claude-agentic/ai/ and ai-path are the rules a
# run is judged by, like the policies they replace.
# The installed tree is anchored to the runtime's home (direct-mode-diet D4b):
# the guard is given the test home as its own, and every expectation stands.
decide_t() { HOME="$TMP/user" CLAUDE_CONFIG_DIR='' CODEX_HOME='' decide "$@"; }
for home in .claude .codex; do
    SH="$TMP/user/$home/claude-agentic"
    tool() { jq -nc --arg r "$ROOT" --arg t "$1" --arg p "$2" '{hook_event_name:"PreToolUse",tool_name:$t,cwd:$r,tool_input:{file_path:$p}}'; }
    bash_cmd() { jq -nc --arg r "$ROOT" --arg c "$1" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$r,tool_input:{command:$c}}'; }
    printf '{"current_stage":"implementation","task_id":"T-1"}\n' > "$ROOT/.ai/state/current.json"
    decide_t "$home in a task: Write to the shared tree is denied" deny "$(tool Write "$SH/ai/policies/git.md")"
    decide_t "$home in a task: Edit of the shared tree is denied" deny "$(tool Edit "$SH/ai/policies/git.md")"
    decide_t "$home in a task: Write to ai-path is denied" deny "$(tool Write "$SH/ai-path")"
    decide_t "$home in a task: Read of the shared tree is allowed" allow "$(tool Read "$SH/ai/policies/git.md")"
    decide_t "$home in a task: running ai-path is allowed" allow "$(bash_cmd "$SH/ai-path policies/git.md")"
    decide_t "$home in a task: a sibling file is not frozen by this rule" allow "$(tool Write "$SH/ai-path.notes")"
    # T-2026-10-15-001 (known-risks a): the whole tree, replaced or removed in
    # one shell command, with nothing inside ai/ named on the line.
    decide_t "$home in a task: rm -rf of the bare shared tree is denied" deny "$(bash_cmd "rm -rf $SH/ai")"
    decide_t "$home in a task: the same rm followed by && is denied" deny "$(bash_cmd "rm -rf $SH/ai && echo done")"
    decide_t "$home in a task: and with no space before the && (review: patsub_replacement ate the &)" deny "$(bash_cmd "rm -rf $SH/ai&& echo done")"
    decide_t "$home in a task: and with a redirect glued to the path" deny "$(bash_cmd "rm -rf $SH/ai>/dev/null")"
    decide_t "$home in a task: mv over the bare shared tree is denied" deny "$(bash_cmd "mv $TMP/new $SH/ai")"
    decide_t "$home in a task: cp -r of a directory named ai into the home is denied" deny "$(bash_cmd "cp -r $TMP/new/ai $SH/")"
    decide_t "$home in a task: install into the shared tree is denied" deny "$(bash_cmd "install -m 644 $TMP/x $SH/ai/policies/git.md")"
    decide_t "$home in a task: cp to a sibling that merely starts with ai is allowed" allow "$(bash_cmd "cp $TMP/x $SH/ai-notes")"
    rm -f "$ROOT/.ai/state/current.json"
    decide_t "$home no task: Write to the shared tree is allowed" allow "$(tool Write "$SH/ai/policies/git.md")"
    decide_t "$home no task: Write to ai-path is allowed" allow "$(tool Write "$SH/ai-path")"
    decide_t "$home no task: rm -rf of the shared tree is the guard's business only in a task" allow "$(bash_cmd "rm -rf $SH/ai")"
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
grep -q 'current\.json\|session\.json' <<<"$out" && pass "in a task: the deny names the file found under the directory" \
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

echo "== ai-path-guard (reads and roots — direct-mode-diet §4a, §4b)"
# §4a: a one-liner that names .ai/state/ or .ai/reports/ is denied only when the
# command also shows a write indicator; an eval keeps the old rule. The state
# file is {} here, so a task is in flight throughout this section.
mkdir -p "$ROOT/.ai/reports/T-1"
for c in "python3 -c \"import json; print(json.load(open('.ai/state/current.json'))['current_stage'])\"" \
         "python3 -c \"print(open('.ai/reports/T-1/events.jsonl', 'r').read().count('gate'))\"" \
         "python3 -c \"import pathlib; print(pathlib.Path('.ai/state/current.json').read_text())\"" \
         "python3 -c \"import json; print(json.dumps(json.load(open('.ai/state/current.json')), indent=2))\" | head -20" \
         "perl -e 'open(my \$f, \"<\", \".ai/state/current.json\"); print <\$f>'" \
         "node -e \"console.log(require('fs').readFileSync('.ai/state/current.json', 'utf8'))\"" \
         "ruby -e 'puts File.read(\".ai/state/current.json\")'"; do
    decide_home "a read-only one-liner is allowed: $c" allow "$c"
done
for c in "python3 -c \"open('.ai/state/current.json', 'w').write('{}')\"" \
         "python3 -c \"open('.ai/reports/T-1/notes.md', mode='a').write('x')\"" \
         "python3 -c \"import pathlib; pathlib.Path('.ai/state/x.json').open('w').write('{}')\"" \
         "python3 -c \"open(\\\".ai/state/x.json\\\", \\\"wb\\\")\"" \
         "python3 -c \"import os; os.open('.ai/state/x.json', os.O_WRONLY | os.O_CREAT)\"" \
         "python3 -c \"import pathlib; pathlib.Path('.ai/state/x.json').write_text('{}')\"" \
         "python3 -c \"import pathlib; pathlib.Path('.ai/state/x.json').write_bytes(b'{}')\"" \
         "python3 -c \"import json; m='w'; json.dump({}, open('.ai/state/x.json', m))\"" \
         "python3 -c \"import os; os.replace('/tmp/x', '.ai/state/current.json')\"" \
         "python3 -c \"import os; os.remove('.ai/state/current.json')\"" \
         "python3 -c \"import shutil; shutil.copy('/tmp/x', '.ai/state/current.json')\"" \
         "python3 -c \"import os; os.truncate('.ai/state/current.json', 0)\"" \
         "python3 -c \"import pathlib; pathlib.Path('.ai/state/x.json').touch()\"" \
         "python3 -c \"import os; os.unlink('.ai/state/current.json')\"" \
         "python3 -c \"import os; os.rename('/tmp/x', '.ai/state/current.json')\"" \
         "python3 -c \"import os; os.symlink('/tmp/x', '.ai/state/current.json')\"" \
         "python3 -c \"import subprocess; subprocess.run(['rm', '.ai/state/current.json'])\"" \
         "python3 -c \"import os; os.system('rm .ai/state/current.json')\"" \
         "perl -e 'open(my \$f, \">\", \".ai/state/current.json\")'" \
         "perl -e 'open(F, \">>.ai/reports/T-1/events.jsonl\")'" \
         "perl -e 'open(F, \"+<\", \".ai/state/current.json\")'" \
         "perl -e 'system(\"rm\", \".ai/state/current.json\")'" \
         "perl -e '\`rm .ai/state/current.json\`'" \
         "ruby -e 'File.write(\".ai/state/current.json\", \"{}\")'" \
         "ruby -e 'File.delete(\".ai/state/current.json\")'" \
         "ruby -e 'IO.write(\".ai/state/current.json\", \"{}\")'" \
         "ruby -e 'require \"fileutils\"; FileUtils.rm(\".ai/state/current.json\")'" \
         "node -e \"require('fs').writeFileSync('.ai/state/current.json', '{}')\"" \
         "node -e \"const fs = require('fs'); fs.appendFileSync('.ai/reports/T-1/events.jsonl', 'x')\"" \
         "node -e \"const fs = require('fs'); fs.rmSync('.ai/state/current.json')\"" \
         "node -e \"const fs = require('fs'); fs.copyFileSync('/tmp/x', '.ai/state/current.json')\"" \
         "node -e \"const fs = require('fs'); fs.mkdirSync('.ai/reports/T-9')\"" \
         "node -e \"require('child_process').execSync('rm .ai/state/current.json')\"" \
         "python3 -c 'print(1)'; php -r 'file_put_contents(\".ai/state/current.json\", \"{}\");'" \
         "python3 -c 'print(1)'; php -r 'copy(\"/tmp/x\", \".ai/state/current.json\");'" \
         "python3 -c 'print(\"{}\")' > .ai/reports/T-1/notes.md" \
         "python3 -c 'print(\"{}\")' >> .ai/reports/T-1/notes.md" \
         "python3 -c 'print(\"{}\")' | tee -a .ai/reports/T-1/notes.md" \
         "eval \"cat .ai/state/current.json\""; do
    decide_home "a writing one-liner is denied: $c" deny "$c"
done
# The indicator regex runs in-process up to 4096 characters (ere_match): a
# padded line of open( calls is the slow case for its [^)]* pieces.
for unit in 'open(' 'a'; do
    pad=$(rep "$unit" $(( 4000 / ${#unit} )))
    timed "a 4 KB one-liner padded with '$unit' that reads the state is allowed" allow \
        "$(printf "python3 -c \"print(open('.ai/state/current.json').read())\" # %s" "$pad" | bash_stdin)" 500
done

# §4b: the protected and task patterns are anchored to the project root and to
# the runtime homes. The same basenames are denied under the root and allowed in
# a tree outside it, in the plugin's templates and in a fixture tree.
SCRATCH="$TMP/scratch"; mkdir -p "$SCRATCH/.ai/state" "$SCRATCH/.ai/policies"
printf '{}\n' > "$SCRATCH/.ai/state/current.json"; printf '{}\n' > "$SCRATCH/.ai/policies/path-guard.json"
write_at() { jq -nc --arg r "$ROOT" --arg p "$1" '{hook_event_name:"PreToolUse",tool_name:"Write",cwd:$r,tool_input:{file_path:$p,content:"{}"}}'; }
for rel in .ai/state/current.json .ai/state/handoff.md .ai/reports/T-1/questions.md .ai/reports/T-1/events.jsonl \
           .ai/policies/path-guard.json .ai/policies/risk-tiers.json .ai/workflows/t3.md .ai/AGENTS.md \
           .claude/settings.json .claude/agents/x.md .claude/hooks/ai-x.sh .codex/config.toml .codex/hooks/ai-x.sh \
           docs/sdlc/constitution.md .github/copilot-instructions.md .junie/guidelines.md .cursor/rules/x.mdc .cursorrules; do
    decide "in a task: Write to $rel under the root is denied" deny "$(write_at "$ROOT/$rel")"
    decide "in a task: Write to $rel in a tree outside the root is allowed" allow "$(write_at "$SCRATCH/$rel")"
    decide "in a task: Write to $rel under the ai-init templates is allowed" allow "$(write_at "$ROOT/skills/ai-init/templates/$rel")"
    decide "in a task: Write to $rel under a fixture tree is allowed" allow "$(write_at "$ROOT/tests/fixtures/adopt/x/$rel")"
done
decide "Write through src/.. to the root's policy file is denied" deny "$(write_at "$ROOT/src/../.ai/policies/risk-tiers.json")"
decide "Write through //./ to the root's state file is denied" deny "$(write_at "$ROOT//.ai/./state/current.json")"
decide "Write through ../ out of the root is allowed" allow "$(write_at "$ROOT/../scratch/.ai/policies/path-guard.json")"
ln -sfn "$ROOT" "$TMP/rootlink"
decide "Write by the physical path while the cwd is a link to the root is denied" deny \
    "$(jq -nc --arg r "$TMP/rootlink" --arg p "$ROOT/.ai/policies/path-guard.json" '{hook_event_name:"PreToolUse",tool_name:"Write",cwd:$r,tool_input:{file_path:$p}}')"
decide "Write of a new state file through a link to the root is denied" deny "$(write_at "$TMP/rootlink/.ai/state/session-new.json")"
decide "Edit from cwd=src of the root's policy file is denied" deny \
    "$(jq -nc --arg r "$ROOT/src" --arg p "$ROOT/.ai/policies/path-guard.json" '{hook_event_name:"PreToolUse",tool_name:"Edit",cwd:$r,tool_input:{file_path:$p}}')"
decide_home "cat of a policy file outside the root is allowed" allow "cat $SCRATCH/.ai/policies/path-guard.json"
decide_home "cat of the root's policy file is still denied" deny 'cat .ai/policies/path-guard.json'
decide_home "cp into a state file outside the root is allowed" allow "cp /tmp/x $SCRATCH/.ai/state/current.json"
decide_home "a redirect into a state file outside the root is allowed" allow "echo '{}' > $SCRATCH/.ai/state/current.json"
decide_home "rm -rf of a .ai/ tree outside the root is allowed" allow "rm -rf $SCRATCH/.ai"
decide_home "a redirect through src/.. into the root's policy file is denied" deny 'echo x > src/../.ai/policies/path-guard.json'
decide_home "cp through src/.. onto the root's policy file is denied" deny 'cp /tmp/x src/../.ai/policies/risk-tiers.json'
decide_home "rm -rf .ai/state is still denied" deny 'rm -rf .ai/state'
# The home trees: ~/.claude/hooks/ai-* and the shared tree, by every spelling.
write_home() { HOME="$HOME_T" CLAUDE_CONFIG_DIR="${2-}" CODEX_HOME='' decide "$1" "$3" "$(write_at "$4")"; }
write_home "Write to ~/.claude/hooks/ai-* is denied" '' deny "$HOME_T/.claude/hooks/ai-path-guard.sh"
write_home "Write to ~/.codex/hooks/ai-* is denied" '' deny "$HOME_T/.codex/hooks/ai-git-guard.sh"
write_home "in a task: Write to ~/.claude/settings.json is denied" '' deny "$HOME_T/.claude/settings.json"
write_home "in a task: Write to ~/.claude/claude-agentic/ai/ is denied" '' deny "$HOME_T/.claude/claude-agentic/ai/policies/git.md"
write_home "Write to \$CLAUDE_CONFIG_DIR/hooks/ai-* is denied" "$TMP/cfg" deny "$TMP/cfg/hooks/ai-path-guard.sh"
write_home "in a task: Write to \$CLAUDE_CONFIG_DIR/settings.json is denied" "$TMP/cfg" deny "$TMP/cfg/settings.json"
write_home "Write to hooks/ai-* of a .claude/ that is no runtime home is allowed" '' allow "$SCRATCH/.claude/hooks/ai-x.sh"
decide_home "rm ~/.claude/hooks/ai-x is denied" deny 'rm ~/.claude/hooks/ai-x'
decide_home "rm -f \"\$HOME\"/.claude/hooks/ai-path-guard.sh is denied" deny 'rm -f "$HOME"/.claude/hooks/ai-path-guard.sh'
decide_home "echo x > ~/.claude/hooks/ai-path-guard.sh is denied" deny 'echo x > ~/.claude/hooks/ai-path-guard.sh'
decide_home "in a task: cp into ~/.claude/claude-agentic/ai/ is denied" deny 'cp /tmp/x ~/.claude/claude-agentic/ai/policies/git.md'
rm -rf "$TMP/rootlink"

echo "== ai-path-guard (review of T-2026-10-22-002: nested roots, reads HEAD allowed, missed writes)"
# B1: a cwd inside a nested .ai/ tree (a fixture, the ai-init templates, a
# worktree) must not unprotect the outer project's control files: every
# ancestor that holds .ai/ is a root. HEAD denied all of these.
NEST="$TMP/nest"; mkdir -p "$NEST/.ai/state" "$NEST/.ai/policies" "$NEST/.ai/reports/T-1" "$NEST/sub/fix/.ai/policies"
printf '{}\n' > "$NEST/.ai/state/current.json"; printf '{}\n' > "$NEST/.ai/policies/path-guard.json"
nest_tool() { jq -nc --arg c "$NEST/sub/fix" --arg t "$1" --arg p "$2" '{hook_event_name:"PreToolUse",tool_name:$t,cwd:$c,tool_input:{file_path:$p,content:"{}"}}'; }
nest_bash() { jq -nc --arg c "$NEST/sub/fix" --arg x "$1" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:$c,tool_input:{command:$x}}'; }
decide "cwd in a nested .ai/ tree: Write to the outer root's state file is denied" deny "$(nest_tool Write "$NEST/.ai/state/current.json")"
decide "cwd in a nested .ai/ tree: Write to the outer root's handoff is denied" deny "$(nest_tool Write "$NEST/.ai/state/handoff.md")"
decide "cwd in a nested .ai/ tree: Edit of the outer root's policy file is denied" deny "$(nest_tool Edit "$NEST/.ai/policies/path-guard.json")"
decide "cwd in a nested .ai/ tree: Write to the outer root's journal is denied" deny "$(nest_tool Write "$NEST/.ai/reports/T-1/events.jsonl")"
decide "cwd in a nested .ai/ tree: echo >> ../../.ai/state/handoff.md is denied" deny "$(nest_bash 'echo x >> ../../.ai/state/handoff.md')"
decide "cwd in a nested .ai/ tree: cp onto the outer root's policy file is denied" deny "$(nest_bash "cp /tmp/x $NEST/.ai/policies/path-guard.json")"
decide "cwd in a nested .ai/ tree: its own policy file is still the nearest root's" deny "$(nest_tool Write "$NEST/sub/fix/.ai/policies/path-guard.json")"
decide "cwd in a nested .ai/ tree: an ordinary file of the outer root is allowed" allow "$(nest_tool Write "$NEST/src.txt")"
# M1: reads of report files that HEAD allowed at the fast path stay allowed:
# incidental words (a count('a'), sys.stdout.write, re.compile, .copy(), a '|')
# are no write.
for c in "python3 -c \"print(open('.ai/reports/T-1/notes.md').read().count('a'))\"" \
         "python3 -c \"import sys; sys.stdout.write(open('.ai/reports/T-1/review-report.md').read())\"" \
         "python3 -c \"import re; r=re.compile('BLOCKER'); print(len(r.findall(open('.ai/reports/T-1/review-report.md').read())))\"" \
         "python3 -c \"import json; d=json.load(open('.ai/reports/T-1/sensors.json')).copy(); print(d)\"" \
         "python3 -c \"print('|'.join(open('.ai/reports/T-1/plan.md').read().split()))\"" \
         "ls .ai/reports/T-1/ && python3 -c \"import sys; sys.stdout.write('ok')\""; do
    decide_home "a read HEAD allowed stays allowed: $c" allow "$c"
done
# L1, L2: write spellings the first indicators missed.
for c in "ruby -e 'f = File.new(\".ai/state/handoff.md\", \"w\"); f.puts \"x\"'" \
         "python3 -c \"from pathlib import Path; Path('/tmp/c.json').replace('.ai/state/current.json')\"" \
         "python3 -c \"import fileinput; [print(l) for l in fileinput.input('.ai/state/handoff.md', inplace=True)]\"" \
         "python3 -c \"import io; io.FileIO('.ai/state/current.json', 'w')\"" \
         "perl -MFile::Slurp -e 'write_file(\".ai/state/handoff.md\", \"x\")'" \
         "perl -pi -e 's/a/b/' .ai/reports/T-1/notes.md" \
         "perl -i -pe 's/a/b/' .ai/reports/T-1/notes.md" \
         "ruby -i -pe 'sub(/a/, \"b\")' .ai/reports/T-1/notes.md"; do
    decide_home "a writing one-liner is denied: $c" deny "$c"
done

echo "== ai-path-guard (M2, L4 of T-2026-10-22-002)"
# M2: a switch that only starts with an in-place letter, a str.replace and a
# quoted 'a' after any comma are reads. HEAD denied the first five.
for c in "ruby -rdigest -e 'puts Digest::SHA256.hexdigest(File.read(\".ai/state/current.json\"))'" \
         "perl -mio -e 'print 1' .ai/reports/T-1/notes.md" \
         "python3 -c \"from pathlib import Path; print(Path('.ai/state/current.json').read_text().replace('a','b'))\"" \
         "python3 -c \"import json; d=json.load(open('.ai/state/current.json')); print(d.get('x', 'a'))\"" \
         "python3 -c \"print('x', '|y', open('.ai/state/current.json').read())\"" \
         "perl -Mstrict -e 'print 1' .ai/reports/T-1/notes.md" \
         "python3 -c \"print(', '.join(open('.ai/state/current.json').read().split()))\""; do
    decide_home "a read is allowed: $c" allow "$c"
done
# L4: Path.copy, copy_into and move_into (Python 3.14) write their target.
for c in "python3 -c \"from pathlib import Path; Path('/tmp/x').copy('.ai/state/current.json')\"" \
         "python3 -c \"from pathlib import Path; t='.ai/state/current.json'; Path('/tmp/x').copy(t, follow_symlinks=False)\"" \
         "python3 -c \"from pathlib import Path; Path('/tmp/x').copy_into('.ai/state/')\"" \
         "python3 -c \"from pathlib import Path; Path('/tmp/x').move_into('.ai/state/')\""; do
    decide_home "a writing one-liner is denied: $c" deny "$c"
done
# Writes that the tightened indicators must still see; ruby -r json -i is a
# miss on HEAD, the separate argument ended the option loop.
for c in "perl -pie 's/a/b/' .ai/reports/T-1/notes.md" \
         "perl -i.bak -pe 's/a/b/' .ai/reports/T-1/notes.md" \
         "perl -0777 -pi -e 's/a/b/' .ai/reports/T-1/notes.md" \
         "perl -I lib -i -pe 's/a/b/' .ai/reports/T-1/notes.md" \
         "ruby -i2 -pe 'sub(/a/, \"b\")' .ai/reports/T-1/notes.md" \
         "ruby -r json -i -pe 'sub(/a/, \"b\")' .ai/reports/T-1/notes.md" \
         "python3 -c \"import os; a='.ai/state/'; b='handoff.md'; print('x', file=open(os.path.join(a, b), 'w'))\"" \
         "node -e \"const fs=require('fs'); fs.openSync('.ai/state/current.json', 'a')\"" \
         "perl -e 'open my \$fh, \">\", \".ai/state/handoff.md\"; print \$fh \"x\"'" \
         "perl -e 'my \$f=\".ai/state/handoff.md\"; open(F, \">>\$f\"); print F \"x\"'" \
         "python3 -c \"from pathlib import Path; f=Path('.ai/state/handoff.md').open('w'); print('x', file=f)\"" \
         "python3 -c \"print('x', file=open('.ai/state/handoff.md', mode='w'))\"" \
         "python3 -c \"from pathlib import Path; p=Path('/tmp/c'); t=Path('.ai/state/current.json'); p.replace(str(t))\""; do
    decide_home "a writing one-liner is still denied: $c" deny "$c"
done
# Review of T-2026-10-25-001, H1, L1: the first-argument walk reads three
# levels of parens, quoted strings and new Class(; HEAD denied all of these.
for c in "python3 -c \"import os; open(os.path.join(os.getcwd(), '.ai/state/current.json'), 'w').close()\"" \
         "python3 -c \"from pathlib import Path; f=open(str(Path.cwd() / '.ai/reports/T-1/notes.md'), 'a'); print('x', file=f)\"" \
         "node -e \"const fs=require('fs'), path=require('path'); const fd=fs.openSync(path.join(process.cwd(), '.ai/state/current.json'), 'w'); fs.writeSync(fd, '{}')\"" \
         "ruby -e \"File.open(File.expand_path(File.join(Dir.pwd, '.ai/state/current.json')), 'w') { |f| f.puts 'x' }\"" \
         "php -c x.ini -e \"\\\$h = fopen(dirname(getcwd()) . '/.ai/reports/T-1/notes.md', 'a'); fprintf(\\\$h, 'x');\"" \
         "perl -MIO::File -e 'my \$fh = new IO::File(\".ai/reports/T-1/notes.md\", \"w\"); print \$fh \"x\"'" \
         "php -c x.ini -e \"\\\$f = new SplFileObject('.ai/state/current.json', 'w');\"" \
         "python3 -c \"print('x', file=open('.ai/reports/T-1/a,b.md', 'w'))\"" \
         "python3 -c \"print('x', file=open(\\\".ai/reports/T-1/n.md\\\", \\\"a\\\"))\"" \
         "python3 -c \"import os; from pathlib import Path; p=Path('/tmp/a'); p.replace(os.path.join('.ai/state/', 'b'))\"" \
         "perl -gpi -e 's/a/b/' .ai/reports/T-1/notes.md" \
         "perl -tpi -e 's/a/b/' .ai/reports/T-1/notes.md" \
         "ruby -vpi -e 'sub(/a/, \"b\")' .ai/reports/T-1/notes.md" \
         "ruby -E utf-8 -i -pe 'sub(/a/, \"b\")' .ai/reports/T-1/notes.md"; do
    decide_home "a writing one-liner is still denied: $c" deny "$c"
done
# L2: a copy.copy and a str.replace whose string holds a paren are reads.
for c in "python3 -c \"import copy, json; from pathlib import Path; d=copy.copy(json.loads(Path('.ai/state/current.json').read_text())); print(d)\"" \
         "python3 -c \"from pathlib import Path; print(Path('.ai/state/current.json').read_text().replace(')', ''))\""; do
    decide_home "a read is allowed: $c" allow "$c"
done
# The mode indicator walks the first argument with a nested group: a long line
# of commas and parens goes to grep (ere_match), measured at 40 KB.
pad=$(rep '(a, b),' 5800)
timed "a 40 KB one-liner of commas and parens that reads the state is allowed" allow \
    "$(printf "python3 -c \"print(open('.ai/state/current.json').read())\" # open(%s" "$pad" | bash_stdin)" 1000

echo "== ai-path-guard (project WITHOUT .ai/ — every guard must be inert)"
BARE="$TMP/bare"; mkdir -p "$BARE"; printf 'SECRET=1\n' > "$BARE/.env"
out=$(jq -nc --arg r "$BARE" '{hook_event_name:"PreToolUse",tool_name:"Read",cwd:$r,tool_input:{file_path:($r+"/.env")}}' | "$GUARD")
if [ -z "$out" ]; then pass "no .ai/: reading .env is not blocked"; else fail "no .ai/: reading .env should not be blocked" "$out"; fi

summary "ai-path-guard"
