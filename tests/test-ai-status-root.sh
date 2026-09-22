#!/usr/bin/env bash
# /ai-status resolves the project the same way the guards do.
#
# Step 1 of skills/ai-status/SKILL.md carries an executable walk up the
# directory tree. It exists so a reader can see WHICH .ai/ governs the directory
# they are in — a .ai/ in an ancestor, or in $HOME, silently arms the path and
# scope guards for every repository below it, and that is not visible from
# anywhere else. The walk is only worth anything while it agrees with
# find_ai_root in hooks/lib/ai-hook-common.sh, so this suite runs the snippet
# straight out of the skill and compares the two, case by case.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SKILL="$PLUGIN_ROOT/skills/ai-status/SKILL.md"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# The fenced bash block of step 1, taken from the skill rather than copied here.
awk '/^   ```bash$/ {inblock=1; buf=""; next}
     inblock && /^   ```$/ {if (buf ~ /AI_PROJECT=/) printf "%s", buf; inblock=0; next}
     inblock {sub(/^   /, ""); buf = buf $0 "\n"}' "$SKILL" > "$TMP/snippet.sh"

echo "== the walk is where the skill says it is"
if grep -q 'AI_PROJECT=' "$TMP/snippet.sh" && grep -q 'find_ai_root' "$SKILL"; then
    pass "step 1 carries the walk and names find_ai_root as its source"
else
    fail "step 1 no longer carries the walk" "extracted: $(head -c 120 "$TMP/snippet.sh")"
    summary "ai-status project root"; exit
fi

# The inner directory is a real repository, so a walk that stopped at the git
# root — the tempting shortcut, and the wrong one — is caught here rather than
# in someone's terminal.
mkdir -p "$TMP/outer/repo/src/deep" "$TMP/bare/src" "$TMP/outer/.ai" "$TMP/outer/repo/.ai"
git -C "$TMP/outer/repo" init -q -b main
git -C "$TMP/bare" init -q -b main

# resolved <dir> — what each of the two implementations answers, one per line.
resolved() {
    ( cd "$1" && bash -c '
        set -uo pipefail
        . "$1/hooks/lib/ai-hook-common.sh"
        . "$2"
        printf "%s\n" "$AI_PROJECT"
        AI_CWD=$PWD
        find_ai_root "$PWD" || printf "\n"
      ' _ "$PLUGIN_ROOT" "$TMP/snippet.sh" 2>/dev/null )
}

check() {  # check <label> <dir> <expected, relative to TMP, or EMPTY>
    local label="$1" dir="$2" expect="$3" out status guard
    out=$(resolved "$dir")
    status=$(printf '%s' "$out" | sed -n 1p); guard=$(printf '%s' "$out" | sed -n 2p)
    status=${status#"$TMP"/}; guard=${guard#"$TMP"/}
    [ -n "$status" ] || status=EMPTY
    [ -n "$guard" ] || guard=EMPTY
    if [ "$status" != "$guard" ]; then
        fail "$label: the skill and the guard disagree" "skill=$status guard=$guard"
    elif [ "$status" != "$expect" ]; then
        fail "$label: both agree on the wrong root" "got=$status expected=$expect"
    else
        pass "$label ($status)"
    fi
}

echo "== the skill and find_ai_root resolve the same root"
check "its own .ai/ at the repository root" "$TMP/outer/repo"          outer/repo
check "its own .ai/, from a subdirectory"   "$TMP/outer/repo/src/deep" outer/repo
rm -rf "$TMP/outer/repo/.ai"
check "a .ai/ inherited from an ancestor"   "$TMP/outer/repo"          outer
check "inherited, from a subdirectory"      "$TMP/outer/repo/src/deep" outer
check "no .ai/ anywhere above"              "$TMP/bare/src"            EMPTY

echo "== the warning cases are spelled out, not left to judgement"
for phrase in "ancestor of" "is \`\$HOME\`" "never ran \`/ai-init\`"; do
    if grep -qF "$phrase" "$SKILL"; then pass "step 1 still covers: $phrase"
    else fail "step 1 no longer covers: $phrase" "the warning that makes an inherited root visible is gone"; fi
done

# The status report is where a project learns what its always-loaded block
# costs: install.sh says it once, at install time, and never again for a
# project's own files. If the step goes, nobody is told.
echo "== the report names what loads on every turn"
if grep -q 'render_instructions.py' "$SKILL" && grep -q 'measure .*--block --budget 2048' "$SKILL"; then
    pass "the budget step measures the project block against 2048 B"
else
    fail "the instruction-budget step no longer measures the block" \
         "expected a render_instructions.py measure --block --budget 2048 call"
fi
for phrase in "GEMINI.md" ".junie/guidelines.md" "docs/sdlc/constitution.md" "OVER"; do
    if grep -qF "$phrase" "$SKILL"; then pass "the budget step covers: $phrase"
    else fail "the budget step no longer covers: $phrase"; fi
done

# R16: a regenerated or unattended-deleted foreign structure must reach the
# report; without the second line of step 7 nobody is told.
echo "== the plugin-version step carries the adopt line"
for phrase in "--adopt --check" "(deleted unattended)"; do
    if grep -qF -- "$phrase" "$SKILL"; then pass "step 7 covers: $phrase"
    else fail "step 7 no longer covers: $phrase"; fi
done

summary "ai-status project root"
