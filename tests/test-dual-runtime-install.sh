#!/usr/bin/env bash
# install.sh --target: auto-detection must install each runtime only where that
# runtime exists, an explicit --target must override detection, and a host with
# neither runtime must fail loudly instead of writing a half-configured tree.
#
# PATH is reduced to /usr/bin:/bin plus a scratch bin/, so the developer's own
# claude and codex executables (typically in ~/.local/bin) are invisible here.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
BIN="$TMP/bin"; mkdir -p "$BIN"
BASE_PATH="/usr/bin:/bin"

stub() {  # stub <name>...  — put fake runtimes on the scratch PATH
    rm -f "$BIN"/*
    for name in "$@"; do
        printf '#!/bin/sh\nexit 0\n' > "$BIN/$name"
        chmod +x "$BIN/$name"
    done
}

# run <case> <extra args...> — fresh scratch homes, never created up front, so
# "the directory exists" cannot be mistaken for "the runtime is installed".
run() {
    local name="$1"; shift
    C="$TMP/$name/claude" X="$TMP/$name/codex"
    mkdir -p "$TMP/$name"
    env -i HOME="$TMP/$name/home" PATH="$BIN:$BASE_PATH" \
        CLAUDE_DIR="$C" CODEX_DIR="$X" \
        bash "$INSTALL" "$@" 2>&1
}

wrote() { [ -d "$1" ] && [ -n "$(ls -A "$1" 2>/dev/null)" ]; }

echo "== only claude present"
stub claude
out=$(run claude-only --target auto --plan max --fable yes)
wrote "$TMP/claude-only/claude" && pass "auto installed Claude" || fail "Claude should have been installed" "$out"
wrote "$TMP/claude-only/codex" && fail "auto must not touch Codex when it is absent" || pass "Codex is left untouched"
printf '%s' "$out" | grep -c >/dev/null 'detected runtime: claude$' && pass "the detected runtime is reported" || fail "expected 'detected runtime: claude'" "$out"

echo "== only codex present"
stub codex
out=$(run codex-only --target auto)
wrote "$TMP/codex-only/codex" && pass "auto installed Codex" || fail "Codex should have been installed" "$out"
wrote "$TMP/codex-only/claude" && fail "auto must not touch Claude when it is absent" || pass "Claude is left untouched"
printf '%s' "$out" | grep -c >/dev/null 'Enter plan' && fail "a Codex-only install must not ask for a Claude plan" || pass "no Claude plan is asked for"

echo "== both present"
stub claude codex
out=$(run both --target auto --plan max --fable yes)
wrote "$TMP/both/claude" && pass "auto installed Claude" || fail "Claude missing" "$out"
wrote "$TMP/both/codex" && pass "auto installed Codex" || fail "Codex missing" "$out"
printf '%s' "$out" | grep -c >/dev/null 'Done (Claude Code)' && pass "the Claude summary is printed" || fail "no Claude summary" "$out"
printf '%s' "$out" | grep -c >/dev/null 'Done (Codex)' && pass "the Codex summary is printed" || fail "no Codex summary" "$out"

echo "== a leftover directory is not an installed runtime"
stub claude
mkdir -p "$TMP/dir-only/codex"
out=$(run dir-only --target auto --plan max --fable yes </dev/null)
wrote "$TMP/dir-only/claude" && pass "auto installed Claude" || fail "Claude should have been installed"
if wrote "$TMP/dir-only/codex"; then fail "a codex directory without a codex executable must be left alone"
else pass "the Codex directory is left untouched"; fi
if grep -q 'codex plan\|ChatGPT plan' <<<"$out"; then fail "no Codex plan may be asked for or chosen"
else pass "no Codex plan is asked for"; fi
printf '%s' "$out" | grep -c >/dev/null 'no codex on PATH — skipped' \
    && pass "the skip is reported with its reason" || fail "expected the skip note" "$(printf '%s' "$out" | head -3)"
printf '%s' "$out" | grep -c >/dev/null -- '--target both' \
    && pass "the note names the override" || fail "the note should suggest --target both"

# A path with a space is one path, in the note as everywhere else.
stub claude
mkdir -p "$TMP/dir only spaced/codex"
out=$(run "dir only spaced" --target auto --plan max --fable yes </dev/null)
grep -qF "codex: $TMP/dir only spaced/codex found but no codex on PATH" <<<"$out" \
    && pass "the note keeps a path with spaces whole" || fail "the note split the path" "$(printf '%s' "$out" | head -3)"

stub
mkdir -p "$TMP/dirs-only/claude" "$TMP/dirs-only/codex"
out=$(run dirs-only --target auto </dev/null); rc=$?
[ $rc -ne 0 ] && grep -q 'No supported runtime' <<<"$out" \
    && pass "directories alone are no runtime: it stops and says so" || fail "expected 'No supported runtime'" "$(printf '%s' "$out" | head -3)"
if grep -q 'Enter plan\|codex plan\|ChatGPT plan' <<<"$out"; then fail "nothing may be asked for"
else pass "no plan is asked for"; fi

echo "== neither present"
stub
out=$(run neither --target auto); rc=$?
[ $rc -ne 0 ] && pass "a host with no runtime exits non-zero" || fail "expected a non-zero exit" "$out"
wrote "$TMP/neither/claude" && fail "nothing may be written when no runtime is found" || pass "nothing is written"
wrote "$TMP/neither/codex" && fail "nothing may be written when no runtime is found" || pass "no Codex tree either"
printf '%s' "$out" | grep -c >/dev/null -- '--target claude' && pass "the error names the override" || fail "the error should suggest --target" "$out"

echo "== an explicit target overrides detection"
stub codex
out=$(run explicit-claude --target claude --plan max --fable yes)
wrote "$TMP/explicit-claude/claude" && pass "--target claude installs Claude with no claude executable" || fail "should install Claude" "$out"
wrote "$TMP/explicit-claude/codex" && fail "--target claude must leave Codex alone even when Codex is present" || pass "--target claude leaves Codex alone"

stub claude
out=$(run explicit-codex --target codex)
wrote "$TMP/explicit-codex/codex" && pass "--target codex installs Codex with no codex executable" || fail "should install Codex" "$out"
wrote "$TMP/explicit-codex/claude" && fail "--target codex must leave Claude alone" || pass "--target codex leaves Claude alone"

stub
out=$(run explicit-both --target both --plan pro)
wrote "$TMP/explicit-both/claude" && pass "--target both installs Claude without detection" || fail "should install Claude" "$out"
wrote "$TMP/explicit-both/codex" && pass "--target both installs Codex without detection" || fail "should install Codex" "$out"

# Each runtime renders its own routing.md; one shared temp file meant the
# second render (Codex) overwrote the first before Claude's was installed.
CR="$TMP/explicit-both/claude/claude-agentic/routing.md"
XR="$TMP/explicit-both/codex/claude-agentic/routing.md"
has() { grep -q "$2" "$1" 2>/dev/null; }
CLAUDE_MARK='^# Model routing (.* plan)$' CODEX_MARK='^# Model allocation by task'
if has "$CR" "$CLAUDE_MARK" && ! has "$CR" "$CODEX_MARK"; then pass "Claude's routing.md is the Claude text"
else fail "Claude's routing.md is not the Claude text" "$(grep -n '^# ' "$CR" 2>&1)"; fi
if has "$XR" "$CODEX_MARK" && ! has "$XR" "$CLAUDE_MARK"; then pass "Codex's routing.md is the Codex text"
else fail "Codex's routing.md is not the Codex text" "$(grep -n '^# ' "$XR" 2>&1)"; fi

# The shared .ai/ tree (T-2026-10-13-004): each home gets its own copy and its
# own resolver, and its routing.md names that home's tree, never the other's.
for home in claude codex; do
    H="$TMP/explicit-both/$home"
    other=$([ "$home" = claude ] && echo codex || echo claude)
    diff -r "$PLUGIN_ROOT/ai" "$H/claude-agentic/ai" >/dev/null 2>&1 \
        && pass "$home: claude-agentic/ai equals ai/" || fail "$home: claude-agentic/ai differs from ai/" "$(diff -rq "$PLUGIN_ROOT/ai" "$H/claude-agentic/ai" 2>&1)"
    [ -x "$H/claude-agentic/ai-path" ] && pass "$home: ai-path is executable" || fail "$home: ai-path is missing or not executable"
    has "$H/claude-agentic/routing.md" "$H/claude-agentic/ai/" \
        && pass "$home: routing.md names its own shared tree" || fail "$home: routing.md does not name $H/claude-agentic/ai/"
    has "$H/claude-agentic/routing.md" "$TMP/explicit-both/$other/claude-agentic/ai" \
        && fail "$home: routing.md names the $other tree" || pass "$home: routing.md does not name the $other tree"
    out=$(cd "$TMP" && "$H/claude-agentic/ai-path" --root "$TMP" policies/git.md 2>&1)
    [ "$out" = "$H/claude-agentic/ai/policies/git.md" ] && pass "$home: the installed resolver finds its own tree" || fail "$home: installed resolver" "$out"
    ls "$H/claude-agentic" | grep -q '^ai\.\(new\|old\)$' && fail "$home: a temp tree was left behind" || pass "$home: no temp tree left behind"
done

# A reinstall over a tree someone edited backs that tree up, then replaces it.
C="$TMP/explicit-both/claude"
printf 'local edit\n' >> "$C/claude-agentic/ai/policies/git.md"
out=$(run explicit-both --target both --plan pro)
grep -q '^local edit$' "$C/backups/$(date +%F)/claude-agentic/ai/policies/git.md" 2>/dev/null \
    && pass "reinstall backs up an edited shared tree" || fail "no backup of the edited shared tree" "$out"
diff -r "$PLUGIN_ROOT/ai" "$C/claude-agentic/ai" >/dev/null 2>&1 \
    && pass "reinstall restores the shipped shared tree" || fail "reinstall left the edited tree"

echo "== an unknown target is rejected"
stub claude codex
out=$(run bad-target --target everything); rc=$?
[ $rc -ne 0 ] && pass "--target everything is rejected" || fail "unknown target should fail" "$out"

echo "== dry run writes nothing for either runtime"
stub claude codex
out=$(run dry --target both --plan max --fable yes --dry-run)
wrote "$TMP/dry/claude" && fail "a dry run wrote to the Claude tree" || pass "the Claude tree is untouched"
wrote "$TMP/dry/codex" && fail "a dry run wrote to the Codex tree" || pass "the Codex tree is untouched"
printf '%s' "$out" | grep -c >/dev/null '== claude:' && pass "the dry run has a Claude section" || fail "no Claude section" "$out"
printf '%s' "$out" | grep -c >/dev/null '== codex:' && pass "the dry run has a Codex section" || fail "no Codex section" "$out"
printf '%s' "$out" | grep -c >/dev/null '{{' && fail "the dry run left an unrendered placeholder" || pass "every placeholder is rendered"

summary "dual-runtime install"
