#!/usr/bin/env bash
# claude-agentic: git and deployment safety guard (PreToolUse on Bash).
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
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
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
printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])(git|gh|argocd|helm|kubectl|terraform|dep|deployer|cap|flyctl|fly|vercel|netlify)([[:space:]]|$)' || allow

CONFIG="$HOME/.claude/hooks/ai-git-guard.json"
[ -f "$CONFIG" ] || CONFIG="$HOOK_DIR/ai-git-guard-defaults.json"
DEFAULTS="$HOOK_DIR/ai-git-guard-defaults.json"

read_list() {  # read_list <jq-path> — project config first, shipped defaults as fallback
    local out
    out=$(json_strings "$CONFIG" "$1")
    [ -n "$out" ] || out=$(json_strings "$DEFAULTS" "$1")
    printf '%s\n' "$out"
}

PROTECTED=$(read_list '.protected_branches')
DEPLOYS=$(read_list '.deploy_patterns')
SENSITIVE=$(read_list '.sensitive_staging_patterns')

REPO_NAME=$(basename "$(git -C "$AI_CWD" rev-parse --show-toplevel 2>/dev/null || echo "$AI_CWD")")
allowed_repo() {  # allowed_repo <jq-path> — an escape hatch a human sets per repo
    json_strings "$CONFIG" "$1" | grep -qxF "$REPO_NAME"
}

is_protected() {  # is_protected <branch>
    local branch="$1" pattern
    [ -n "$branch" ] || return 1
    while IFS= read -r pattern; do
        [ -n "$pattern" ] || continue
        printf '%s' "$branch" | grep -qE "^${pattern}$" && return 0
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
if printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]|$)'; then
    # explicit path arguments
    while IFS= read -r token; do
        [ -n "$token" ] || continue
        case "$token" in -*|git|add|stage|.|"*") continue ;; esac
        if hit=$(printf '%s\n' "$SENSITIVE" | matches_any "$token"); then
            deny "Refusing to stage what looks like a secret: $token (matched: $hit)

A credential committed once stays in the history even after it is deleted. Add
the path to .gitignore, or stage the files you meant one by one."
        fi
    done < <(printf '%s\n' "$cmd" | tr ' \t\n|;&()' '\n' | grep -v '^$')

    # wildcard adds: ask git what would actually be staged
    if printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+(add|stage)([[:space:]]+-[^[:space:]]+)*[[:space:]]+(\.|-A|--all|\*)([[:space:]]|$)' \
       || printf '%s' "$cmd" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+(add|stage)[[:space:]]+(-A|--all)([[:space:]]|$)'; then
        while IFS= read -r path; do
            [ -n "$path" ] || continue
            if hit=$(printf '%s\n' "$SENSITIVE" | matches_any "$path"); then
                deny "Refusing a wildcard 'git add': it would stage $path (matched: $hit)

Add that path to .gitignore first, or stage the files you meant explicitly."
            fi
        done < <(git -C "$AI_CWD" status --porcelain --untracked-files=all 2>/dev/null | sed -E 's/^.{3}//' | sed -E 's/^.* -> //')
    fi
fi

# ---------------------------------------------------------------- 2. force push
if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)' \
   && printf '%s' "$cmd_rules" | grep -qE '(^|[[:space:]])(-f|--force|--force-with-lease(=[^[:space:]]*)?|--force-if-includes)([[:space:]]|$)'; then
    allowed_repo '.allow_force_push_repos' \
      || deny "Refusing a force push (--force and --force-with-lease alike).$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 3. deleting a remote branch
if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*(--delete|-d)([[:space:]]|$)' \
   || printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|[:space:]]+[[:space:]]+:[^[:space:]]+'; then
    deny "Refusing to delete a remote branch.$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 4. history rewriting
if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+filter-branch([[:space:]]|$)' \
   || printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git-?filter-repo([[:space:]]|$)' \
   || printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+push[[:space:]]+[^;&|]*--mirror([[:space:]]|$)'; then
    deny "Refusing to rewrite repository history (filter-branch / filter-repo / --mirror push).$WHY_HISTORY"
fi

# ---------------------------------------------------------------- 5. protected branches
current_branch=$(git -C "$AI_CWD" branch --show-current 2>/dev/null || true)

if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?push([[:space:]]|$)'; then
    # `git push <remote> <refspec>` — take the refspec's destination when present,
    # otherwise the push targets whatever is checked out (this is what makes
    # `git push origin HEAD` on main impossible to slip through).
    target=$(printf '%s' "$cmd_rules" | sed -nE 's/.*git[[:space:]]+(-[^[:space:]]+[[:space:]]+)*push([[:space:]]+--?[a-z-]+(=[^[:space:]]+)?)*[[:space:]]+[^-][^[:space:];&|]*[[:space:]]+([^[:space:];&|]+).*/\4/p' | head -1)
    target="${target##*:}"          # src:dst refspec -> dst
    target="${target#refs/heads/}"
    case "$target" in HEAD|"") target="$current_branch" ;; esac

    if is_protected "$target"; then
        allowed_repo '.allow_protected_push_repos' \
          || deny "Refusing to push directly to the protected branch '$target'.$WHY_PROTECTED"
    fi
fi

if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+merge([[:space:]]|$)' && is_protected "$current_branch"; then
    deny "Refusing to merge into '$current_branch', which is a protected branch.$WHY_PROTECTED"
fi

if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])gh[[:space:]]+pr[[:space:]]+merge([[:space:]]|$)'; then
    deny "Refusing to merge a pull request. Merging is the reviewer's call, not the agent's.$WHY_PROTECTED"
fi

if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+reset[[:space:]]+[^;&|]*--hard' && is_protected "$current_branch"; then
    deny "Refusing 'git reset --hard' while '$current_branch' is checked out.

A hard reset on a protected branch throws away commits and uncommitted work with
no way back. Check out a working branch first."
fi

# ---------------------------------------------------------------- 6. bypassing hooks
if printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+[^;&|]*(--no-verify|-n[[:space:]]+--)' \
   && printf '%s' "$cmd_rules" | grep -qE '(^|[|;&[:space:]])git[[:space:]]+([^;&|]*[[:space:]])?(commit|push)([[:space:]]|$)'; then
    deny "Refusing '--no-verify'.

The pre-commit and pre-push hooks are the project's own quality gate. If they
fail, the fix is the code, not the flag. If a hook is broken, say so and let a
human decide."
fi

# ---------------------------------------------------------------- 7. production deploys
while IFS= read -r pattern; do
    [ -n "$pattern" ] || continue
    if printf '%s' "$cmd_rules" | grep -qE "$pattern"; then
        deny "Refusing to run a deployment or infrastructure-mutating command.

Matched pattern: $pattern$WHY_DEPLOY"
    fi
done <<< "$DEPLOYS"

allow
