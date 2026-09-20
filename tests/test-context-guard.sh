#!/usr/bin/env bash
# context-guard.py: on UserPromptSubmit it warns once per 10k band and holds a
# prompt back once past the block threshold, both derived from autoCompactWindow;
# on PreCompact it writes a snapshot and prints the summary instructions; on
# SessionStart:compact it puts the snapshot back. It fails open everywhere.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

GUARD="$PLUGIN_ROOT/hooks/context-guard.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# Isolate from the developer's own ~/.claude: settings, state and env.
export HOME="$TMP/home" CLAUDE_CONFIG_DIR="$TMP/home/.claude"
export AI_CONTEXT_GUARD_STATE="$TMP/state"
unset CLAUDE_CODE_AUTO_COMPACT_WINDOW AI_CONTEXT_WARN_TOKENS AI_CONTEXT_BLOCK_TOKENS
mkdir -p "$CLAUDE_CONFIG_DIR" "$TMP/project/src"
PROJECT="$TMP/project"
T="$TMP/transcript.jsonl"

set_window() {   # set_window <tokens> [model] — the model decides the cap below
    jq -n --argjson w "$1" --arg m "${2:-}" \
        '{autoCompactWindow:$w} + (if $m == "" then {} else {model:$m} end)' \
        > "$CLAUDE_CONFIG_DIR/settings.json"
}
reset_state() { rm -rf "$AI_CONTEXT_GUARD_STATE"; }

# Transcript lines, in the compact form Claude Code writes (no spaces after ':').
usage() {       # usage <input> <cache_read> <cache_write> [isSidechain]
    jq -nc --argjson i "$1" --argjson r "$2" --argjson w "$3" --argjson s "${4:-false}" \
        '{type:"assistant",isSidechain:$s,message:{role:"assistant",content:[{type:"text",text:"ok"}],
          usage:{input_tokens:$i,cache_read_input_tokens:$r,cache_creation_input_tokens:$w,output_tokens:50}}}'
}
user() { jq -nc --arg t "$1" '{type:"user",message:{role:"user",content:$t}}'; }
tool() { jq -nc --arg n "$1" --argjson i "$2" '{type:"assistant",message:{role:"assistant",content:[{type:"tool_use",id:"t1",name:$n,input:$i}]}}'; }
boundary() { jq -nc '{type:"system",subtype:"compact_boundary",compactMetadata:{trigger:"auto",preTokens:101000,postTokens:14000}}'; }
context_of() { usage 10 "$(( $1 - 20 ))" 10 > "$T"; }     # a transcript whose context is <tokens>

prompt() {      # prompt <text> [session] -> hook stdout
    jq -nc --arg p "$1" --arg s "${2:-s1}" --arg t "$T" --arg c "$PROJECT" \
        '{hook_event_name:"UserPromptSubmit",session_id:$s,transcript_path:$t,cwd:$c,prompt:$p}' | "$GUARD"
}
event() {       # event <hook_event_name> [source] -> hook stdout
    jq -nc --arg e "$1" --arg src "${2:-}" --arg t "$T" --arg c "$PROJECT" \
        '{hook_event_name:$e,session_id:"s1",transcript_path:$t,cwd:$c,source:$src,trigger:"auto"}' | "$GUARD"
}
expect_silent() { [ -z "$1" ] && pass "$2" || fail "$2" "expected no output, got: $(printf '%s' "$1" | head -c 200)"; }
expect_warn() {
    if [ "$(printf '%s' "$1" | jq -r '(.systemMessage | type) + "/" + (.hookSpecificOutput.additionalContext | type) + "/" + (.decision // "none")' 2>/dev/null)" = "string/string/none" ]; then
        pass "$2"
    else fail "$2" "expected a warning, got: $(printf '%s' "$1" | head -c 200)"; fi
}
expect_block() {
    [ "$(printf '%s' "$1" | jq -r '.decision // "none"' 2>/dev/null)" = block ] && pass "$2" \
        || fail "$2" "expected decision=block, got: $(printf '%s' "$1" | head -c 200)"
}
contains() { case "$1" in *"$2"*) pass "$3";; *) fail "$3" "missing: $2";; esac; }
lacks()    { case "$1" in *"$2"*) fail "$3" "unexpected: $2";; *) pass "$3";; esac; }

# ------------------------------------------------------------ fails open
assert_fails_open "$GUARD" "empty stdin"
assert_fails_open "$GUARD" "malformed JSON" '{not json'
assert_fails_open "$GUARD" "a JSON array instead of an object" '[1,2]'
assert_fails_open "$GUARD" "an event it does not handle" '{"hook_event_name":"PreToolUse","tool_name":"Read"}'
assert_fails_open "$GUARD" "UserPromptSubmit without a transcript" '{"hook_event_name":"UserPromptSubmit","session_id":"s1","prompt":"hi"}'
assert_fails_open "$GUARD" "UserPromptSubmit with a missing transcript file" \
    "{\"hook_event_name\":\"UserPromptSubmit\",\"session_id\":\"s1\",\"prompt\":\"hi\",\"transcript_path\":\"$TMP/nope.jsonl\"}"
printf 'garbage\n{"type":"assistant"}\n\n' > "$T"
expect_silent "$(prompt hi)" "a transcript with no usage in it is silent"

# ------------------------------------------------------------ thresholds follow autoCompactWindow
set_window 133000        # compaction near 100k: warn from 80k, block from 120k
reset_state; context_of 79000;  expect_silent "$(prompt hi)" "window 133000: 79k is silent"
reset_state; context_of 80000;  out=$(prompt hi); expect_warn "$out" "window 133000: 80k warns"
contains "$out" "80k tokens" "the warning names the context size"
reset_state; context_of 119000; expect_warn "$(prompt hi)" "window 133000: 119k still only warns"
reset_state; context_of 120000; out=$(prompt hi); expect_block "$out" "window 133000: 120k holds the prompt back"
contains "$out" "/compact" "the block reason says what to run"

# Claude Code caps the window at the model's own ("capped to ... by model" in
# /autocompact), so the same 300 000 setting means two different things.
set_window 300000        # on a 200k model: capped to 200k, compaction near 167k, warn from 133.6k
reset_state; context_of 133000; expect_silent "$(prompt hi)" "window 300000 on a 200k model: 133k is silent"
reset_state; context_of 134000; expect_warn "$(prompt hi)" "window 300000 on a 200k model: capped, so 134k already warns"

set_window 300000 'opus[1m]'   # not capped: compaction near 267k, warn from 213.6k, block from 320.4k
reset_state; context_of 200000; expect_silent "$(prompt hi)" "window 300000 on a [1m] model: 200k is silent"
reset_state; context_of 214000; expect_warn "$(prompt hi)" "window 300000 on a [1m] model: 214k warns"
reset_state; context_of 321000; expect_block "$(prompt hi)" "window 300000 on a [1m] model: 321k holds the prompt back"

# The default is the Max profile's 800 000, which on a 200k model is capped to
# 200 000: compaction near 167k, so the warning starts at 133.6k, not at 80k.
rm -f "$CLAUDE_CONFIG_DIR/settings.json"
reset_state; context_of 133000; expect_silent "$(prompt hi)" "no settings.json: the Max default applies, capped"
reset_state; context_of 134000; expect_warn "$(prompt hi)" "no settings.json: the Max default applies"
set_window 1000
reset_state; context_of 134000; expect_warn "$(prompt hi)" "a window under the reserve falls back to the default"
echo '{broken' > "$CLAUDE_CONFIG_DIR/settings.json"
reset_state; context_of 134000; expect_warn "$(prompt hi)" "an unreadable settings.json falls back to the default"

set_window 133000 'opus[1m]'
reset_state; context_of 200000
expect_silent "$(CLAUDE_CODE_AUTO_COMPACT_WINDOW=300000 prompt hi)" "CLAUDE_CODE_AUTO_COMPACT_WINDOW wins over settings.json"
set_window 133000
reset_state; context_of 50000
expect_warn "$(AI_CONTEXT_WARN_TOKENS=40000 prompt hi)" "AI_CONTEXT_WARN_TOKENS sets the warn threshold in tokens"
expect_block "$(AI_CONTEXT_BLOCK_TOKENS=45000 prompt hi)" "AI_CONTEXT_BLOCK_TOKENS sets the block threshold in tokens"
reset_state; context_of 130000
expect_warn "$(AI_CONTEXT_BLOCK_TOKENS=0 prompt hi)" "AI_CONTEXT_BLOCK_TOKENS=0 turns blocking off, warnings stay"
reset_state; context_of 90000
expect_silent "$(AI_CONTEXT_WARN_TOKENS=0 prompt hi)" "AI_CONTEXT_WARN_TOKENS=0 turns warnings off"
reset_state; context_of 130000
expect_block "$(AI_CONTEXT_WARN_TOKENS=0 prompt hi)" "with warnings off the block still applies"
reset_state; context_of 90000
expect_warn "$(AI_CONTEXT_WARN_TOKENS=abc prompt hi)" "a non-numeric override is ignored"

# ------------------------------------------------------------ the session's model
# UserPromptSubmit carries no model; SessionStart may. The record it leaves is
# what tells a 1M session from a 200k one below 200k of context, where the size
# itself proves nothing.
session_start_model() {   # session_start_model <model> -> writes the record
    jq -nc --arg m "$1" --arg t "$T" --arg c "$PROJECT" \
        '{hook_event_name:"SessionStart",session_id:"s1",transcript_path:$t,cwd:$c,
          source:"startup",model:$m}' | "$GUARD" >/dev/null
}

reset_state; set_window 800000
context_of 200000; expect_warn "$(prompt hi)" "no model record: 800k is capped to the 200k model window"
session_start_model 'opus[1m]'
[ "$(cat "$AI_CONTEXT_GUARD_STATE/s1.model" 2>/dev/null)" = 'opus[1m]' ] \
    && pass "SessionStart records the session's model" || fail "SessionStart did not record the model"
context_of 200000; expect_silent "$(prompt hi)" "with the record, the same 200k context is silent on [1m]"
context_of 614000; expect_warn "$(prompt hi)" "and warns from 613k, as an 800k window should"

reset_state; set_window 800000
context_of 250000; expect_silent "$(prompt hi)" "without a record, a context already past 200k proves a [1m] model"

reset_state
session_start_model ''
[ ! -e "$AI_CONTEXT_GUARD_STATE/s1.model" ] \
    && pass "a SessionStart without a model records nothing" || fail "an empty model was recorded"
set_window 133000

# ------------------------------------------------------------ once per band, once per prompt
reset_state; context_of 81000
expect_warn   "$(prompt one)"   "first prompt in the 80k band warns"
expect_silent "$(prompt two)"   "second prompt in the same band is silent"
context_of 89000
expect_silent "$(prompt three)" "still the same band"
context_of 91000
expect_warn   "$(prompt four)"  "the next 10k band warns again"
expect_warn   "$(prompt five s2)" "another session has its own state"

reset_state; context_of 125000
expect_block  "$(prompt 'deploy it')" "past the limit the prompt is held back"
expect_silent "$(prompt 'deploy it')" "the same prompt again goes through"
expect_block  "$(prompt 'deploy it')" "which confirms that one send only: a third time it is held back again"
expect_silent "$(prompt 'deploy it')" "and goes through on its repeat"
expect_block  "$(prompt 'and now this')" "a new prompt is held back again"
expect_block  "$(prompt 'something else')" "a different prompt does not count as a confirmation"
expect_silent "$(prompt 'something else')" "its repeat does"

# ------------------------------------------------------------ what counts as the context
reset_state
{ usage 10 124000 10; boundary; user "continue"; } > "$T"
expect_silent "$(prompt hi)" "after a compaction boundary the old size no longer counts"
{ usage 10 124000 10; boundary; user "continue"; usage 10 15000 10; } > "$T"
expect_silent "$(prompt hi)" "the first response after a compaction sets the new size"
reset_state; context_of 125000; expect_block "$(prompt hi)" "(setup) blocked at 125k"
{ usage 10 124000 10; boundary; usage 10 15000 10; } > "$T"
expect_silent "$(prompt other)" "back under the threshold: silent"
[ ! -e "$AI_CONTEXT_GUARD_STATE/s1.json" ] && pass "and the session marker is removed" || fail "and the session marker is removed"

reset_state
{ usage 10 85000 10; usage 5 1000 5 true; } > "$T"
expect_warn "$(prompt hi)" "a subagent (sidechain) response is not the session's context"
reset_state
{ usage 10 85000 10; usage 0 0 0; } > "$T"
expect_warn "$(prompt hi)" "a synthetic zero-usage entry is skipped"
reset_state
{ usage 30000 30000 30000; } > "$T"
expect_warn "$(prompt hi)" "input, cache read and cache write are summed"
reset_state
{ usage 10 85000 10; echo '{"type":"assistant","message":{"usage":'; echo 'not json at all'; } > "$T"
expect_warn "$(prompt hi)" "a torn last line does not hide the context"
reset_state
{
    usage 10 85000 10
    printf '{"type":"user","message":{"role":"user","content":[{"type":"tool_result","tool_use_id":"t1","content":"'
    head -c 5500000 /dev/zero | tr '\0' x
    printf '"}]}}\n'
} > "$T"
expect_warn "$(prompt hi)" "a 5 MB line of tool output after the last response does not hide it"
reset_state
{ usage 10 85000 10; head -c 5500000 /dev/zero | tr '\0' x; } > "$T"
expect_warn "$(prompt hi)" "nor does one that is still being written"
reset_state; context_of 85000
out=$(jq -nc --arg t "$T" '{hook_event_name:"UserPromptSubmit",session_id:"../../etc/x",transcript_path:$t,prompt:"hi"}' | "$GUARD")
expect_warn "$out" "a hostile session id still works"
[ -z "$(find "$TMP" -path "$AI_CONTEXT_GUARD_STATE" -prune -o -name '*.json' -newer "$T" -print | grep -v settings.json)" ] \
    && pass "and writes nothing outside the state directory" || fail "and writes nothing outside the state directory"

# ------------------------------------------------------------ PreCompact: snapshot + instructions
reset_state
git -C "$PROJECT" init -q -b feat/snapshot 2>/dev/null
echo x > "$PROJECT/src/new.py"
mkdir -p "$PROJECT/.ai/state"; echo '{"task":"T-42","step":3}' > "$PROJECT/.ai/state/current.json"
{
    user "<system-reminder>
injected rules
</system-reminder>
Fix the export and keep the CSV header order"
    jq -nc '{type:"user",isMeta:true,message:{role:"user",content:"meta caveat must not appear"}}'
    jq -nc '{type:"user",isCompactSummary:true,message:{role:"user",content:"old summary must not appear"}}'
    jq -nc '{type:"user",isSidechain:true,message:{role:"user",content:"subagent brief must not appear"}}'
    jq -nc '{type:"user",message:{role:"user",content:[{type:"tool_result",tool_use_id:"t1",content:"tool output must not appear"}]}}'
    jq -nc '{type:"user",message:{role:"user",content:[{type:"tool_result",tool_use_id:"t2",content:"ok"},{type:"text",text:"text beside a tool result must not appear"}]}}'
    user "Explain why <command-name>/model</command-name> shows up in the transcript"
    user "<command-message>ai-task</command-message> <command-name>/ai-task</command-name> <command-args>round the totals</command-args>"
    user "<local-command-stdout>stdout must not appear</local-command-stdout>"
    user "<command-name>/model</command-name> <command-message>model</command-message> <command-args></command-args>"
    user "<command-name>/ai-task</command-name> <command-message>ai-task</command-message> <command-args>add the VAT column</command-args>"
    jq -nc '{type:"user",message:{role:"user",content:[{type:"text",text:"[Request interrupted by user]"}]}}'
    jq -nc '{type:"user",message:{role:"user",content:[{type:"text",text:"And write a test for it"}]}}'
    tool Edit "{\"file_path\":\"$PROJECT/src/export.py\"}"
    tool Write "{\"file_path\":\"$PROJECT/src/new.py\"}"
    tool Read "{\"file_path\":\"$PROJECT/src/only-read.py\"}"
    tool Edit "{\"file_path\":\"/etc/outside.conf\"}"
    tool MultiEdit "{\"file_path\":\"$PROJECT/src/multi.py\"}"
    tool NotebookEdit "{\"notebook_path\":\"$PROJECT/notes/report.ipynb\"}"
    tool Edit "{\"file_path\":\"$PROJECT/src/export.py\"}"
    tool TodoWrite '{"todos":[{"content":"old list","status":"completed"}]}'
    tool TodoWrite '{"todos":[{"content":"write the test","status":"in_progress"},{"content":"update docs","status":"pending"}]}'
    usage 10 101000 10
} > "$T"

out=$(event PreCompact)
contains "$out" "word for word" "PreCompact prints the summary instructions"
lacks "$out" "{" "as plain text, not JSON"
SNAP="$AI_CONTEXT_GUARD_STATE/s1.md"
if [ -f "$SNAP" ]; then pass "PreCompact writes the snapshot"; else fail "PreCompact writes the snapshot"; touch "$SNAP"; fi
snap=$(cat "$SNAP")
contains "$snap" "Fix the export and keep the CSV header order" "a prompt is kept verbatim, without the injected reminder"
lacks    "$snap" "injected rules" "the reminder itself is dropped"
contains "$snap" "/ai-task add the VAT column" "a slash command with arguments is kept as an instruction"
lacks    "$snap" "- /model" "a bare slash command is not"
contains "$snap" "- Explain why <command-name>/model</command-name> shows up in the transcript" "a prompt that quotes the command tags is kept whole"
contains "$snap" "/ai-task round the totals" "the older wrapper order, message first, is read as well"
contains "$snap" "And write a test for it" "a prompt sent as a text block is kept"
lacks    "$snap" "must not appear" "meta, summary, sidechain, tool results and command output are left out"
lacks    "$snap" "Request interrupted" "an interruption marker is not an instruction"
contains "$snap" "- src/export.py" "edited files are listed relative to the project"
contains "$snap" "- /etc/outside.conf" "a file outside the project keeps its full path"
contains "$snap" "- src/new.py" "a file created with Write is listed"
contains "$snap" "- src/multi.py" "and one changed with MultiEdit"
contains "$snap" "- notes/report.ipynb" "and a notebook, by its notebook_path"
lacks    "$snap" "only-read.py" "a file that was only read is not listed"
[ "$(printf '%s\n' "$snap" | grep -c -- '- src/export.py')" = 1 ] && pass "a file edited twice is listed once" || fail "a file edited twice is listed once"
[ "$(printf '%s\n' "$snap" | grep -n -- '^- ' | grep -m1 -n 'src/export.py' | cut -d: -f1)" -gt \
  "$(printf '%s\n' "$snap" | grep -n -- '^- ' | grep -m1 -n 'outside.conf' | cut -d: -f1)" ] \
    && pass "the most recently edited file comes last" || fail "the most recently edited file comes last"
contains "$snap" "[in_progress] write the test" "the latest todo list is kept"
lacks    "$snap" "old list" "an earlier todo list is not"
contains "$snap" "branch: feat/snapshot" "the git branch is recorded"
contains "$snap" "?? src/" "and the git status"
contains "$snap" '"task": "T-42"' "the .ai task state is included"

big=$(python3 -c 'print("x" * 5000)')
long=$(python3 -c 'print("d" * 300)')
{
    for i in 1 2 3 4 5 6 7; do user "prompt number $i $big"; done
    for i in $(seq 1 45); do tool Edit "{\"file_path\":\"/srv/$long/file-$i.py\"}"; done
    usage 10 101000 10
} > "$T"
event PreCompact >/dev/null
snap=$(cat "$SNAP")
lacks    "$snap" "prompt number 2 " "only the latest prompts are kept"
contains "$snap" "prompt number 7 " "the newest prompt is among them"
[ "$(printf '%s\n' "$snap" | grep -c "^- prompt number")" = 5 ] && pass "five of them" || fail "five of them"
lacks    "$snap" "$big" "a long prompt is cut"
lacks    "$snap" "file-5.py" "only the latest edited files are kept"
contains "$snap" "snapshot truncated" "an oversized snapshot is cut and says so"
[ "${#snap}" -le 12100 ] && pass "the snapshot is capped in size" || fail "the snapshot is capped in size" "${#snap} chars"

out=$(jq -nc '{hook_event_name:"PreCompact",session_id:"s9"}' | "$GUARD")
contains "$out" "word for word" "without a transcript PreCompact still prints the instructions"
[ ! -e "$AI_CONTEXT_GUARD_STATE/s9.md" ] && pass "and writes no snapshot" || fail "and writes no snapshot"
out=$(AI_CONTEXT_GUARD_STATE=/proc/nope event PreCompact)
contains "$out" "word for word" "an unwritable state directory does not lose the instructions"

# ------------------------------------------------------------ SessionStart
{ user "Keep the API stable"; tool Edit "{\"file_path\":\"$PROJECT/src/api.py\"}"; usage 10 101000 10; } > "$T"
event PreCompact >/dev/null
out=$(event SessionStart compact)
ctx=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.additionalContext // ""' 2>/dev/null)
[ "$(printf '%s' "$out" | jq -r '.hookSpecificOutput.hookEventName' 2>/dev/null)" = SessionStart ] \
    && pass "SessionStart:compact answers as a SessionStart hook" || fail "SessionStart:compact answers as a SessionStart hook" "$out"
contains "$ctx" "Keep the API stable" "and puts the snapshot back into the context"
contains "$ctx" "src/api.py" "with the edited files"
for source in startup resume clear fork; do
    expect_silent "$(event SessionStart $source)" "SessionStart:$source injects nothing"
done

rm -f "$SNAP"
ctx=$(event SessionStart compact | jq -r '.hookSpecificOutput.additionalContext // ""')
contains "$ctx" "Keep the API stable" "without a snapshot it is rebuilt from the transcript"
event PreCompact >/dev/null
{ user "A newer instruction"; usage 10 20000 10; } > "$T"
touch -d '2 hours ago' "$SNAP"
ctx=$(event SessionStart compact | jq -r '.hookSpecificOutput.additionalContext // ""')
contains "$ctx" "A newer instruction" "a stale snapshot is not reused"
expect_silent "$(jq -nc '{hook_event_name:"SessionStart",source:"compact",session_id:"none"}' | "$GUARD")" \
    "no snapshot and no transcript: silent"

# ------------------------------------------------------------ the installer registers it
SNIPPET=$(jq -s '.[0] * .[1]' "$PLUGIN_ROOT/settings.common.json" "$PLUGIN_ROOT/profiles/max.json")
for ev in UserPromptSubmit PreCompact SessionStart; do
    [ "$(printf '%s' "$SNIPPET" | jq -r --arg e "$ev" '[.hooks[$e][]?.hooks[]?.command | select(test("context-guard"))] | length')" = 1 ] \
        && pass "settings: context-guard is registered once under $ev" || fail "settings: context-guard is registered once under $ev"
done
[ "$(printf '%s' "$SNIPPET" | jq -r '.hooks.SessionStart[] | select(.hooks[].command | test("context-guard")) | .matcher')" = compact ] \
    && pass "settings: SessionStart runs it for source=compact only" || fail "settings: SessionStart runs it for source=compact only"
[ -x "$GUARD" ] && pass "the hook is executable" || fail "the hook is executable"
[ "$(python3 - "$GUARD" "$PLUGIN_ROOT/profiles/max.json" <<'PY'
import json, re, sys
src = open(sys.argv[1], encoding="utf-8").read()
print(int(re.search(r"^DEFAULT_WINDOW = (\d+)", src, re.M).group(1)) == json.load(open(sys.argv[2]))["autoCompactWindow"])
PY
)" = True ] && pass "the hook's default window is the Max profile's" || fail "the hook's default window is the Max profile's"

summary "context-guard"
