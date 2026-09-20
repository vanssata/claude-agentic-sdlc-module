#!/usr/bin/env bash
# claude-agentic: git and deployment safety guard (PreToolUse on Bash).
# Runs in both runtimes: Claude Code's Bash tool and Codex's shell tool arrive as
# the same normalised `Bash` call, and Codex's apply_patch is not a shell command
# at all, so it is allowed through here and handled by the other two guards.
#
# GLOBAL: this one is not gated on .ai/. The operations it refuses — rewriting
# shared history, pushing straight to a protected branch, staging a secret,
# bypassing hooks, running a production deploy — are wrong in any repository,
# and they are exactly the ones that cannot be undone from a chat session.
#
# What it does NOT do: judge whether a change weakens tests or static analysis.
# That is not a property of a git command; ai-reviewer and ai-release check it.
#
# Every rule is line-scoped and word-boundary anchored, so a command mentioned
# inside a heredoc body or a commit message is never mistaken for an invocation.
#
# It runs on every Bash call, so rules are matched in-process (ere_match) rather
# than one grep per rule, and git is asked for the branch or the repository name
# only by a rule that needs it.
set -uo pipefail

HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)"
# shellcheck source=lib/ai-hook-common.sh
. "$HOOK_DIR/lib/ai-hook-common.sh"

read_payload
[ "$AI_TOOL" = Bash ] || allow

cmd=$(bash_command)
[ -n "$cmd" ] || allow

# Rules match against the command with prose removed; the secret-staging rule
# below still reads $cmd, because a path is an argument, never a message.
cmd_rules=$(strip_prose "$cmd")

# Cheap exit for the overwhelming majority of commands.
ere_match '(^|[|;&[:space:]])(git|gh|argocd|helm|kubectl|terraform|dep|deployer|cap|flyctl|fly|vercel|netlify)([[:space:]]|$)' "$cmd_rules" || allow

DEFAULTS="$HOOK_DIR/ai-git-guard-defaults.json"
CONFIG=$(runtime_hook_config ai-git-guard.json) || CONFIG="$DEFAULTS"

# load_lists <file> <prefix> — every list this guard reads from one config file,
# in one jq call. <prefix>_<key> receives exactly what `json_strings <file> .<key>`
# prints: each string element followed by a newline.
LIST_KEYS=(protected_branches deploy_patterns sensitive_staging_patterns allow_force_push_repos allow_protected_push_repos)
load_lists() {
    local file="$1" prefix="$2" key
    for key in "${LIST_KEYS[@]}"; do printf -v "${prefix}_${key}" '%s' ""; done
    [ -f "$file" ] || return 0
    eval "$(jq -r --arg prefix "$prefix" '
        . as $doc | $ARGS.positional[]
        | "\($prefix)_\(.)+=" + ([$doc[.] // [] | .[]? | select(type == "string") | . + "\n"] | add // "" | @sh)
        ' "$file" --args "${LIST_KEYS[@]}" 2>/dev/null)"
}
load_lists "$CONFIG" CFG
if [ "$CONFIG" = "$DEFAULTS" ]; then
    for key in "${LIST_KEYS[@]}"; do v="CFG_$key"; printf -v "DEF_$key" '%s' "${!v}"; done
else
    load_lists "$DEFAULTS" DEF
fi

read_list() {  # read_list <key> — project config first, shipped defaults as fallback
    local cfg="CFG_$1" def="DEF_$1" out
    out=$(chomp_all "${!cfg}")
    [ -n "$out" ] || out=$(chomp_all "${!def}")
    printf '%s\n' "$out"
}

PROTECTED=$(read_list protected_branches)
DEPLOYS=$(read_list deploy_patterns)
SENSITIVE=$(read_list sensitive_staging_patterns)

allowed_repo() {  # allowed_repo <key> — an escape hatch a human sets per repo
    local list="CFG_$1" repo name
    repo=$(basename "$(git -C "$AI_CWD" rev-parse --show-toplevel 2>/dev/null || echo "$AI_CWD")")
    while IFS= read -r name; do
        [ "$name" = "$repo" ] && return 0
    done <<< "${!list%$'\n'}"
    return 1
}

current_branch=""
CURRENT_BRANCH_KNOWN=""
load_current_branch() {  # the checked-out branch, asked of git once and only when needed
    [ -n "$CURRENT_BRANCH_KNOWN" ] && return 0
    current_branch=$(git -C "$AI_CWD" branch --show-current 2>/dev/null || true)
    CURRENT_BRANCH_KNOWN=1
}

is_protected() {  # is_protected <branch>
    local branch="$1" pattern
    [ -n "$branch" ] || return 1
    while IFS= read -r pattern; do
        [ -n "$pattern" ] || continue
        ere_match "^${pattern}$" "$branch" && return 0
    done <<< "$PROTECTED"
    return 1
}

git_subcommand() {  # the first non-flag word after `git`
    printf '%s' "$cmd" | sed -nE 's/.*(^|[|;&[:space:]])git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*([a-z-]+).*/\3/p' | head -1
}

WHY_HISTORY=$'\n\nRewriting or force-pushing shared history destroys other people\'s work and cannot\nbe undone from here. If this really is needed, a human does it after agreeing with\nwhoever else has the branch checked out.'
WHY_PROTECTED=$'\n\nProtected branches change through a reviewed pull request, not through a push\nfrom an agent session. Open a PR, or ask the human to run this push themselves.'
WHY_DEPLOY=$'\n\nProduction deployments are a human action with a human on the hook for the\nrollback. The pipeline ends at the release report and human approval; see\n.ai/policies/release.md.'

# ---------------------------------------------------------------- 1. secrets in a commit
if ere_match '(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]|$)' "$cmd"; then
    # explicit path arguments: every word, split on whitespace and | ; & ( )
    words=()
    IFS=$' \t\n' read -r -d '' -a words <<< "${cmd//[|;&()]/ }"
    for token in "${words[@]}"; do
        case "$token" in -*|git|add|stage|.|"*") continue ;; esac
        if hit=$(printf '%s\n' "$SENSITIVE" | matches_any "$token"); then
            deny "Refusing to stage what looks like a secret: $token (matched: $hit)

A credential committed once stays in the history even after it is deleted. Add
the path to .gitignore, or stage the files you meant one by one."
        fi
    done

    # wildcard adds: ask git what would actually be staged
    if ere_match '(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]+-[^[:space:]]+)*[[:space:]]+(\.|-A|--all|\*)([[:space:]]|$)' "$cmd" \
       || ere_match '(^|[|;&[:space:]])git[[:space:]]+(add|stage)[[:space:]]+(-A|--all)([[:space:]]|$)' "$cmd"; then
        while IFS= read -r path; do
            # drop the two status columns and the space; a rename keeps its destination
            [ "${#path}" -lt 3 ] || path="${path:3}"
            case "$path" in *" -> "*) path="${path##*" -> "}" ;; esac
            [ -n "$path" ] || continue
            if hit=$(printf '%s\n' "$SENSITIVE" | matches_any "$path"); then
                deny "Refusing a wildcard 'git add': it would stage $path (matched: $hit)

Add that path to .gitignore first, or stage the files you meant explicitly."
            fi
        done < <(git -C "$AI_CWD" status --porcelain --untracked-files=all 2>/dev/null)
    fi
fi

# ---------------------------------------------------------------- 2. force push
if ere_match '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)' "$cmd_rules" \
   && ere_match '(^|[[:space:]])(-f|--force|--force-with-lease(=[^[:space:]]*)?|--force-if-includes)([[:space:]]|$)' "$cmd_rules"; then
    allowed_repo allow_force_push_repos \
      || deny "Refusing a force push (--force and --force-with-lease alike).$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 3. deleting a remote branch
if ere_match '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*(--delete|-d)([[:space:]]|$)' "$cmd_rules" \
   || ere_match '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|[:space:]]+[[:space:]]+:[^[:space:]]+' "$cmd_rules"; then
    deny "Refusing to delete a remote branch.$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 4. history rewriting
if ere_match '(^|[|;&[:space:]])git[[:space:]]+filter-branch([[:space:]]|$)' "$cmd_rules" \
   || ere_match '(^|[|;&[:space:]])git-?filter-repo([[:space:]]|$)' "$cmd_rules" \
   || ere_match '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*--mirror([[:space:]]|$)' "$cmd_rules"; then
    deny "Refusing to rewrite repository history (filter-branch / filter-repo / --mirror push).$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 5. protected branches
if ere_match '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)' "$cmd_rules"; then
    # `git push <remote> <refspec>` — take the refspec's destination when present,
    # otherwise the push targets whatever is checked out (this is what makes
    # `git push origin HEAD` on main impossible to slip through). The first line
    # that has a refspec wins.
    refspec_re='.*git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([[:space:]]+--?[a-z-]+(=[^[:space:]]+)?)*[[:space:]]+[^-][^[:space:];&|]*[[:space:]]+([^[:space:];&|]+).*'
    target=""
    while IFS= read -r line; do
        if [[ $line =~ $refspec_re ]]; then target="${BASH_REMATCH[4]}"; break; fi
    done <<< "${cmd_rules%$'\n'}"
    target="${target##*:}"          # src:dst refspec -> dst
    target="${target#refs/heads/}"
    case "$target" in HEAD|"") load_current_branch; target="$current_branch" ;; esac

    if is_protected "$target"; then
        allowed_repo allow_protected_push_repos \
          || deny "Refusing to push directly to the protected branch '$target'.$WHY_PROTECTED"
    fi
fi

if ere_match '(^|[|;&[:space:]])git[[:space:]]+merge([[:space:]]|$)' "$cmd_rules" \
   && load_current_branch && is_protected "$current_branch"; then
    deny "Refusing to merge into '$current_branch', which is a protected branch.$WHY_PROTECTED"
fi

if ere_match '(^|[|;&[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)' "$cmd_rules"; then
    deny "Refusing to merge a pull request. Merging is the reviewer's call, not the agent's.$WHY_PROTECTED"
fi

if ere_match '(^|[|;&[:space:]])git[[:space:]]+reset[[:space:]]+[^;&|]*--hard' "$cmd_rules" \
   && load_current_branch && is_protected "$current_branch"; then
    deny "Refusing 'git reset --hard' while '$current_branch' is checked out.

A hard reset on a protected branch throws away commits and uncommitted work with
no way back. Check out a working branch first."
fi

# ---------------------------------------------------------------- 6. bypassing hooks
if ere_match '(^|[|;&[:space:]])git[[:space:]]+[^;&|]*(--no-verify|-n[[:space:]]+--)' "$cmd_rules" \
   && ere_match '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?(commit|push)([[:space:]]|$)' "$cmd_rules"; then
    deny "Refusing '--no-verify'.

The pre-commit and pre-push hooks are the project's own quality gate. If they
fail, the fix is the code, not the flag. If a hook is broken, say so and let a
human decide."
fi

# ---------------------------------------------------------------- 7. production deploys
while IFS= read -r pattern; do
    [ -n "$pattern" ] || continue
    if ere_match "$pattern" "$cmd_rules"; then
        deny "Refusing to run a deployment or infrastructure-mutating command.

Matched pattern: $pattern$WHY_DEPLOY"
    fi
done <<< "$DEPLOYS"

allow
