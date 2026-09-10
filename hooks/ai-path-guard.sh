#!/usr/bin/env bash
# claude-agentic: sensitive-path guard (PreToolUse on Read|Edit|Write|NotebookEdit|Bash).
#
# Opt-in by construction: it exits immediately unless the project has a .ai/
# directory, so installing the plugin changes nothing in repos that never ran
# /ai-init.
#
# Two jobs:
#   1. Keep production secrets and data dumps out of the model context.
#   2. Stop the agent from editing the guards' own configuration or the task
#      state file (those are written by state.py or by a human, never by an edit).
#
# This is defence-in-depth against ordinary agent behaviour, NOT a security
# boundary: a determined process can still read a file through an interpreter.
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/ai-hook-common.sh
. "$HOOK_DIR/lib/ai-hook-common.sh"

read_payload

case "$AI_TOOL" in
    Read|Edit|Write|MultiEdit|NotebookEdit|Bash) ;;
    *) allow ;;
esac

AI_ROOT=$(find_ai_root "$AI_CWD") || allow

DEFAULTS="$HOOK_DIR/ai-path-guard-defaults.json"
PROJECT="$AI_ROOT/.ai/policies/path-guard.json"

DENY_PATTERNS=$( { json_strings "$DEFAULTS" '.deny_patterns'; json_strings "$PROJECT" '.deny_patterns'; } | sort -u)
ALLOW_PATTERNS=$( { json_strings "$DEFAULTS" '.allow_patterns'; json_strings "$PROJECT" '.allow_patterns'; } | sort -u)
PROTECTED_PATTERNS=$( { json_strings "$DEFAULTS" '.protected_config_patterns'; json_strings "$PROJECT" '.protected_config_patterns'; } | sort -u)

[ -n "$DENY_PATTERNS$PROTECTED_PATTERNS" ] || allow
INTERESTING_PATTERNS=$(printf '%s\n%s\n' "$DENY_PATTERNS" "$PROTECTED_PATTERNS" | grep -v '^$')
# Anchor-free copy used only as a cheap pre-filter over a whole command line,
# where a path is surrounded by spaces rather than by the start of the string.
# Dropping anchors can only widen a pattern, so the pre-filter never hides a
# path the precise per-argument pass would have caught.
LOOSE_PATTERNS=$(printf '%s\n' "$INTERESTING_PATTERNS" | sed -e 's/^(\^|\/)//' -e 's/^\^//' -e 's/\$$//')

WHY_SENSITIVE=$'\n\nProduction secrets and data dumps must not enter the model context.\nIf this path is genuinely safe (a .dist/.example file, a fixture), add a regex to\n"allow_patterns" in .ai/policies/path-guard.json. See .ai/policies/security.md.'
WHY_PROTECTED=$'\n\nThese files are the guard configuration and the task state. State is written by\nskills/ai-task/state.py; policy files are edited by a human outside an agent run,\nso a change to them is reviewable. See .ai/policies/safety.md.'

# classify <abs-path> -> prints "sensitive:<pattern>", "protected:<pattern>" or
# nothing. One joined grep decides whether the path is interesting at all; only
# then is the per-pattern pass run, to name the pattern in the deny message.
classify() {
    local p="$1" hit
    matches_joined "$p" "$INTERESTING_PATTERNS" || return 0
    if printf '%s\n' "$ALLOW_PATTERNS" | matches_any "$p" >/dev/null; then
        return 0
    fi
    if hit=$(printf '%s\n' "$PROTECTED_PATTERNS" | matches_any "$p"); then
        printf 'protected:%s\n' "$hit"; return 0
    fi
    if hit=$(printf '%s\n' "$DENY_PATTERNS" | matches_any "$p"); then
        printf 'sensitive:%s\n' "$hit"; return 0
    fi
}

# check_path <literal> <verb> — test both the literal and the resolved path, so a
# symlink pointing at .env is caught even though its own name looks harmless.
check_path() {
    local literal="$1" verb="$2" abs real verdict pattern kind
    abs=$(abs_path "$literal")
    real=$(real_path "$literal")
    for candidate in "$abs" "$real"; do
        verdict=$(classify "$candidate")
        [ -n "$verdict" ] || continue
        kind="${verdict%%:*}"; pattern="${verdict#*:}"
        if [ "$kind" = protected ]; then
            case "$verb" in
                read) continue ;;   # reading the state or a policy file is fine
            esac
            deny "Refusing to $verb a claude-agentic control file: $literal (matched: $pattern)$WHY_PROTECTED"
        else
            deny "Refusing to $verb a sensitive path: $literal (matched: $pattern)$WHY_SENSITIVE"
        fi
    done
}

case "$AI_TOOL" in
    Read)
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            check_path "$f" read
        done < <(target_paths)
        ;;
    Edit|Write|MultiEdit|NotebookEdit)
        while IFS= read -r f; do
            [ -n "$f" ] || continue
            check_path "$f" write
        done < <(target_paths)
        ;;
    Bash)
        cmd=$(bash_command)
        [ -n "$cmd" ] || allow

        # Fast path: if nothing in the whole command line looks interesting, stop
        # here. This keeps the common case to a single grep instead of one pass
        # per argument, which matters because the hook runs on every Bash call.
        matches_joined "$cmd" "$LOOSE_PATTERNS" \
            || printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])(ln|eval)([[:space:]]|$)' \
            || allow

        # Word-boundary anchored, like vendor-write-guard.sh: a path mentioned
        # inside a heredoc body or a commit message is not a command argument.
        readers='(^|[|;&[:space:]])(cat|bat|less|more|head|tail|strings|xxd|od|hexdump|base64|nl|tac|rev)([[:space:]]+-[^[:space:]]+)*[[:space:]]+'
        copiers='(^|[|;&[:space:]])(cp|mv|rsync|scp|install|tar|zip|curl|wget)([[:space:]]+[^;&|[:space:]]+)*[[:space:]]+'

        # Every argument-looking token in the command, minus flags.
        while IFS= read -r token; do
            [ -n "$token" ] || continue
            case "$token" in -*) continue ;; esac
            verdict=$(classify "$(abs_path "$token")")
            [ -n "$verdict" ] || verdict=$(classify "$(real_path "$token")")
            [ -n "$verdict" ] || continue
            kind="${verdict%%:*}"; pattern="${verdict#*:}"

            # Only complain when the token is actually an argument of a command
            # that reads, copies or redirects it — not when it is quoted prose.
            esc=$(ere_escape "$token")
            if printf '%s' "$cmd" | grep -qE "${readers}[\"']?${esc}" \
               || printf '%s' "$cmd" | grep -qE "${copiers}[\"']?${esc}" \
               || printf '%s' "$cmd" | grep -qE "<[[:space:]]*[\"']?${esc}"; then
                if [ "$kind" = protected ]; then
                    deny "Refusing a shell command that reads a claude-agentic control file: $token (matched: $pattern)$WHY_PROTECTED"
                fi
                deny "Refusing a shell command that would expose a sensitive path: $token (matched: $pattern)$WHY_SENSITIVE"
            fi

            # Writing to a protected control file through the shell.
            if [ "$kind" = protected ] \
               && printf '%s' "$cmd" | grep -qE ">>?[[:space:]]*[\"']?${esc}"; then
                deny "Refusing a shell redirect into a claude-agentic control file: $token$WHY_PROTECTED"
            fi
        done < <(printf '%s\n' "$cmd" | tr ' \t\n|;&()<>' '\n' | sed 's/^["'\'']*//; s/["'\'']*$//' | grep -v '^$' | sort -u)

        # A symlink whose target is sensitive: the link does not exist yet at
        # hook time, so the realpath check above cannot see it.
        if printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])ln([[:space:]]+-[^[:space:]]+)*[[:space:]]'; then
            src=$(printf '%s' "$cmd" | sed -nE 's/.*(^|[|;&[:space:]])ln([[:space:]]+-[^[:space:]]+)*[[:space:]]+([^[:space:];&|]+).*/\3/p')
            if [ -n "$src" ] && verdict=$(classify "$(abs_path "$src")") && [ -n "$verdict" ]; then
                deny "Refusing to create a symlink to a sensitive path: $src$WHY_SENSITIVE"
            fi
        fi

        # Obfuscated access: an interpreter one-liner or an eval that mentions a
        # sensitive-looking literal. Documented as a tripwire, not a boundary.
        if printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])(python3?|perl|ruby|node|php)([[:space:]]+-[^[:space:]]+)*[[:space:]]+-(c|e)([[:space:]]|$)' \
           || printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])eval([[:space:]]|$)'; then
            if printf '%s' "$cmd" | grep -qE '\.env|secrets?/|credentials?|id_rsa|\.pem|\.aws'; then
                deny "Refusing an interpreter one-liner that references a sensitive path.$WHY_SENSITIVE"
            fi
        fi
        ;;
esac

allow
