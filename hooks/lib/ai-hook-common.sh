#!/usr/bin/env bash
# Shared helpers for the claude-agentic PreToolUse guards.
# Sourced, never executed directly. Every guard follows the same contract as
# hooks/cap-large-read.py: read the hook payload from stdin, and
# either exit 0 silently (allow) or print a deny JSON object and exit 0.
#
# Both runtimes are supported. Claude Code and Codex send the same PreToolUse
# envelope (`tool_name`, `tool_input`, `cwd`, `hook_event_name`) and accept the
# same deny object, but they name their tools differently: Codex performs every
# file edit through one `apply_patch` call whose `tool_input.command` is the
# patch text, where Claude sends Edit/Write/MultiEdit with a `file_path`.
# read_payload normalises the tool name and target_paths reads both shapes, so
# each guard keeps one set of rules rather than one per provider.
#
# Fail-open policy: a guard that cannot parse its input must allow. These hooks
# are defence-in-depth against ordinary agent mistakes, not a security boundary;
# a broken guard must never make the tool unusable.
#
# This file runs on nearly every tool call, so it is written for process count
# rather than for readability: one jq per payload, ere_match instead of
# `printf | grep -qE`, parameter expansion instead of dirname. Before changing
# any of that, read docs/hook-performance.md — it carries the measurements, the
# invariants a refactor must preserve, and how to prove with
# tests/test-guard-characterization.sh that behaviour did not move.

set -uo pipefail

AI_PAYLOAD=""
AI_TOOL=""
AI_TOOL_RAW=""
AI_CWD=""
AI_EVENT=""
AI_COMMAND=""
AI_COMMAND_OK=""

# read_payload — slurp stdin once and extract the fields every guard needs.
# AI_TOOL_RAW is what the runtime sent; AI_TOOL is that name mapped onto the
# Claude vocabulary the guards' case statements are written in.
#
# One jq call reads every field, because each process costs milliseconds and
# this runs on nearly every tool call. It covers the normal payload — a single
# JSON object whose fields are strings. Anything else takes the field-by-field
# path below, which is the reference behaviour the fast path reproduces.
read_payload() {
    AI_PAYLOAD=$(cat)
    [ -n "$AI_PAYLOAD" ] || exit 0
    command -v jq >/dev/null 2>&1 || exit 0
    local fields
    fields=$(printf '%s' "$AI_PAYLOAD" | jq -rn '
        def plain(v): v == null or v == false or (v | type) == "string";
        def sh(v): (v // "") | @sh;
        [inputs]
        | if length == 1 and (.[0] | type) == "object"
             and plain(.[0].tool_name) and plain(.[0].cwd) and plain(.[0].hook_event_name)
          then .[0]
               | "AI_TOOL_RAW=\(sh(.tool_name)) AI_CWD=\(sh(.cwd)) AI_EVENT=\(sh(.hook_event_name))"
                 + (if .tool_input == null or .tool_input == false then " AI_COMMAND=\(sh(null)) AI_COMMAND_OK=1"
                    elif (.tool_input | type) == "object" and plain(.tool_input.command)
                    then " AI_COMMAND=\(sh(.tool_input.command)) AI_COMMAND_OK=1"
                    else "" end)
          else "SLOW" end' 2>/dev/null) || exit 0
    if [ "$fields" = SLOW ]; then
        AI_TOOL_RAW=$(printf '%s' "$AI_PAYLOAD" | jq -r '.tool_name // empty' 2>/dev/null) || exit 0
        AI_CWD=$(printf '%s' "$AI_PAYLOAD" | jq -r '.cwd // empty' 2>/dev/null)
        AI_EVENT=$(printf '%s' "$AI_PAYLOAD" | jq -r '.hook_event_name // empty' 2>/dev/null)
    else
        eval "$fields"
        # $(jq -r ...) drops trailing newlines; the fast path must as well.
        AI_TOOL_RAW=$(chomp_all "$AI_TOOL_RAW")
        AI_CWD=$(chomp_all "$AI_CWD")
        AI_EVENT=$(chomp_all "$AI_EVENT")
        [ -z "$AI_COMMAND_OK" ] || AI_COMMAND=$(chomp_all "$AI_COMMAND")
    fi
    [ -n "$AI_CWD" ] || AI_CWD="$PWD"
    case "$AI_TOOL_RAW" in
        apply_patch)                 AI_TOOL=Edit ;;   # Codex: one call, many files
        shell|exec_command|local_shell) AI_TOOL=Bash ;;
        *)                           AI_TOOL="$AI_TOOL_RAW" ;;
    esac
}

# chomp_all <string> — the string without trailing newlines, as $(...) returns it.
chomp_all() {
    local s="$1"
    printf '%s' "${s%"${s##*[!$'\n']}"}"
}

# runtime_hook_config <basename> — the live (user-owned) config for a guard.
# It sits next to the guard itself, because the installer puts a copy in each
# runtime's own hooks directory. The runtime homes are searched afterwards so a
# guard invoked straight from a checkout still finds an installed config.
runtime_hook_config() {
    local name="$1" d
    for d in "$HOOK_DIR" "${CLAUDE_CONFIG_DIR:-$HOME/.claude}/hooks" "${CODEX_HOME:-$HOME/.codex}/hooks"; do
        [ -n "$d" ] || continue
        if [ -f "$d/$name" ]; then printf '%s\n' "$d/$name"; return 0; fi
    done
    return 1
}

# payload_field <jq-path> — read one field from the payload, empty on failure.
payload_field() {
    printf '%s' "$AI_PAYLOAD" | jq -r "$1 // empty" 2>/dev/null
}

# bash_command — the command text of a Bash tool call. Empty for Codex's
# apply_patch, whose `command` holds a patch rather than a shell command.
bash_command() {
    [ "$AI_TOOL" = Bash ] || return 0
    if [ -n "$AI_COMMAND_OK" ]; then printf '%s' "$AI_COMMAND"; return 0; fi
    payload_field '.tool_input.command'
}

# patch_paths — the files a Codex apply_patch call touches, read from the patch
# headers. "*** Move to:" is included, because the destination is written too.
patch_paths() {
    payload_field '.tool_input.command' | sed -nE \
      's/^\*\*\* (Add|Update|Delete) File: (.*)$/\2/p; s/^\*\*\* Move to: (.*)$/\1/p'
}

# target_paths — every file path a write/read tool call refers to, one per line.
target_paths() {
    printf '%s' "$AI_PAYLOAD" | jq -r '
        [ .tool_input.file_path?, .tool_input.notebook_path?, .tool_input.path?,
          (.tool_input.edits? // [] | .[]?.file_path?) ]
        | map(select(type == "string" and . != "")) | .[]' 2>/dev/null
    [ "$AI_TOOL_RAW" = apply_patch ] && patch_paths
    return 0
}

# ere_escape <string> — quote a literal so it can be embedded in an ERE.
ere_escape() {
    local s="$1" out="" c i
    for (( i = 0; i < ${#s}; i++ )); do
        c="${s:i:1}"
        case "$c" in
            '['|']'|'\\'|'.'|'*'|'^'|'$'|'('|')'|'{'|'}'|'?'|'+'|'|') out+="\\$c" ;;
            *) out+="$c" ;;
        esac
    done
    printf '%s' "$out"
}

# strip_prose <command> — remove the parts of a shell command that are prose
# rather than instruction: heredoc bodies and commit-message arguments. Rules
# match against the result, so "git commit -m 'never git push --force'" is a
# commit, not a force push. Path-bearing rules still read the original command.
strip_prose() {
    # Both rewrites need a heredoc ("<<") or a message flag ("-m", which
    # "--message" contains); without either the command is already prose-free.
    case "$1" in
        *'<<'*|*-m*) ;;
        *) printf '%s' "$1"; return 0 ;;
    esac
    printf '%s' "$1" | python3 -c '
import re, sys
cmd = sys.stdin.read()
# heredoc bodies: <<EOF ... EOF / <<-"EOF" ... EOF
for m in list(re.finditer(r"<<-?\s*[\"\x27]?([A-Za-z_][A-Za-z0-9_]*)[\"\x27]?", cmd)):
    marker = m.group(1)
    end = re.search(r"^\s*" + re.escape(marker) + r"\s*$", cmd[m.end():], re.M)
    if end:
        cmd = cmd[: m.end()] + cmd[m.end() + end.end():]
# message arguments
cmd = re.sub(r"(-m|--message)(=|\s+)([\"\x27])(?:(?!\3).)*\3", r"\1 MSG", cmd, flags=re.S)
cmd = re.sub(r"(-m|--message)(=|\s+)\$\((?:[^()]|\([^()]*\))*\)", r"\1 MSG", cmd, flags=re.S)
sys.stdout.write(cmd)
'
}

allow() { exit 0; }

# deny <reason> — emit the PreToolUse deny object and stop the tool call.
deny() {
    jq -nc --arg reason "$1" \
      '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$reason}}'
    exit 0
}

# find_ai_root [dir] — nearest ancestor of dir holding a .ai/ directory.
# Prints the root and returns 0, or returns 1 when the project has not opted in.
find_ai_root() {
    local d="${1:-$AI_CWD}"
    [ -n "$d" ] || return 1
    d=$(cd "$d" 2>/dev/null && pwd) || return 1
    while [ -n "$d" ] && [ "$d" != "/" ]; do
        if [ -d "$d/.ai" ]; then printf '%s\n' "$d"; return 0; fi
        d="${d%/*}"; [ -n "$d" ] || d=/      # dirname, without a process
    done
    [ -d "/.ai" ] && { printf '/\n'; return 0; }
    return 1
}

# abs_path <path> — absolute path, relative to the payload cwd, without requiring
# the file to exist. Symlinks are NOT resolved here; use real_path for that.
abs_path() {
    local p="$1"
    case "$p" in
        /*) printf '%s\n' "$p" ;;
        *)  printf '%s\n' "${AI_CWD%/}/$p" ;;
    esac
}

# real_path <path> — fully resolved path when it exists, else the absolute path.
real_path() {
    local p
    p=$(abs_path "$1")
    if [ -e "$p" ]; then
        realpath "$p" 2>/dev/null || printf '%s\n' "$p"
    else
        printf '%s\n' "$p"
    fi
}

# json_strings <file> <jq-path> — newline-separated array of strings from a JSON
# file; silent when the file is missing or malformed.
json_strings() {
    [ -f "$1" ] || return 0
    jq -r "${2} // [] | .[]? | select(type==\"string\")" "$1" 2>/dev/null || true
}

# ere_match <ERE> <subject> — `printf '%s' "$subject" | grep -qE "$ERE"` without
# the two processes. grep matches line by line, so a multi-line subject is tested
# one line at a time: a bracket expression such as [^;&|]* must not match across
# a newline, and ^ and $ anchor at each line. An empty subject has no lines and
# never matches; an invalid pattern never matches, as grep's error does not.
ere_match() {
    local re="$1" subject="$2" line
    [ -n "$subject" ] || return 1
    case "$subject" in
        *$'\n'*) ;;
        *) { [[ $subject =~ $re ]]; } 2>/dev/null; return ;;
    esac
    while IFS= read -r line; do
        { [[ $line =~ $re ]]; } 2>/dev/null && return 0
    done <<< "${subject%$'\n'}"
    return 1
}

# matches_any <string> — reads ERE patterns from stdin (one per line) and prints
# the first one that matches the subject; returns 1 when none does.
# Patterns are tested one at a time on purpose: the matching pattern is quoted
# back to the user in the deny message, which is what makes a deny actionable.
matches_any() {
    local subject="$1" pattern
    while IFS= read -r pattern; do
        [ -n "$pattern" ] || continue
        if ere_match "$pattern" "$subject"; then
            printf '%s\n' "$pattern"
            return 0
        fi
    done
    return 1
}

# matches_joined <string> <patterns> — fast pre-check against all patterns at
# once (one match instead of N). Use it to decide whether the slower
# matches_any pass is worth running. The join is what `paste -sd'|'` produced.
matches_joined() {
    local subject="$1" joined="${2%$'\n'}"
    joined="${joined//$'\n'/|}"
    [ -n "$joined" ] || return 1
    ere_match "$joined" "$subject"
}
