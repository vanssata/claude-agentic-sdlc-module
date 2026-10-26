#!/usr/bin/env bash
# The shared prompts name tiers, never models (WP5 R15, I8). A model is a plan's
# choice: profiles/*.json decide it, install.sh renders it, and at run time
# `state.py profile --tier <TIER>` prints it. A model name written into a prompt
# is wrong on every other plan and every other runtime, so the prompts carry
# FAST / BALANCED / STRONG / EXPERT and the placeholders that install fills in.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

cd "$PLUGIN_ROOT" || exit 1
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# The shared-prompt scope (I8). profiles/, install.sh, scripts/, hooks/, tests/,
# docs/, README.md, prices.json, the frozen history and agents/superseded/ are
# out of it on purpose: that is where models are *supposed* to be named.
scope() {
    printf '%s\n' instructions/stub.md instructions/routing.md
    ls agents/*.md.tmpl
    find skills -name '*.md' -not -path 'skills/project-update/history/*'
    find skills/ai-init/templates skills/project-init/templates -type f
    find ai -type f
}

hits() {  # hits <file...> -> file:line:text for every I8 pattern
    grep -HnEi '\b(haiku|sonnet|opus|opusplan|fable)\b' "$@"
    grep -HnE '\b(Terra|Sol|Astra)\b' "$@"
    grep -HnE 'gpt-[0-9]|claude-(opus|sonnet|haiku|fable)-' "$@"
}

echo "== no model name in the shared prompts"
files=$(scope | sort -u)
found=$(hits $files 2>/dev/null | sort -u)
if [ -z "$found" ]; then
    pass "the shared-prompt scope ($(printf '%s\n' $files | wc -l) files) names no model"
else
    fail "model names in shared prompts ($(printf '%s\n' "$found" | wc -l) lines)" "$(printf '%s\n' "$found" | head -40)"
fi

echo "== the mode thresholds live in the weight table alone (R10)"
# A threshold copied into a prompt goes stale the day weight.json changes. Only
# the table, its generated mirror and docs/weight.md (outside this scope) say it.
found=$(grep -HnE 'light ≤|guarded 3' $files 2>/dev/null | grep -vE '^[^:]*/policies/weight\.(json|md):' | sort -u)
[ -z "$found" ] && pass "no shared prompt restates a mode threshold" \
    || fail "mode thresholds outside weight.json / weight.md" "$(printf '%s\n' "$found" | head -10)"
grep -qE 'light ≤|guarded 3' <<<"light ≤2 · guarded 3–7" && pass "and the pattern catches the weight line's wording" \
    || fail "the R10 pattern no longer matches the weight line"

echo "== the rendered global block is model-free on every plan"
for plan in pro team-pro team-max max max20; do
    out=$(CLAUDE_DIR="$TMP/none" bash install.sh --target claude --plan "$plan" --dry-run 2>/dev/null)
    block=$(printf '%s\n' "$out" | sed -n '/^== CLAUDE.md managed block:/,/^== routing.md/p' | sed '1d;$d')
    [ -n "$block" ] || { fail "--plan $plan: no managed block in the dry run"; continue; }
    printf '%s\n' "$block" > "$TMP/block-$plan"
    b=$(hits "$TMP/block-$plan" 2>/dev/null)
    [ -z "$b" ] && pass "--plan $plan: the CLAUDE.md block names no model" || fail "--plan $plan: models in the block" "$(printf '%s' "$b" | head -5)"
    routing=$(printf '%s\n' "$out" | sed -n '/^== routing.md (on demand)/,/^== profile.json/p')
    grep -q '{{' <<<"$routing" && fail "--plan $plan: routing.md has an unrendered placeholder" || pass "--plan $plan: routing.md renders completely"
done
for plan in plus pro; do
    out=$(CODEX_DIR="$TMP/none-cx" bash install.sh --target codex --codex-plan "$plan" --dry-run 2>/dev/null)
    block=$(printf '%s\n' "$out" | sed -n '/^== AGENTS.md managed block:/,/^== routing.md/p' | sed '1d;$d')
    printf '%s\n' "$block" > "$TMP/cblock-$plan"
    b=$(hits "$TMP/cblock-$plan" 2>/dev/null)
    [ -z "$b" ] && pass "--codex-plan $plan: the AGENTS.md block names no model" || fail "--codex-plan $plan: models in the block" "$(printf '%s' "$b" | head -5)"
done

summary "shared prompts model-free"
