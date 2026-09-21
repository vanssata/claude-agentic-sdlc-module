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

echo "== an unknown target is rejected"
stub claude codex
out=$(run bad-target --target everything); rc=$?
[ $rc -ne 0 ] && pass "--target everything is rejected" || fail "unknown target should fail" "$out"

echo "== an existing config directory counts as a present runtime"
stub
mkdir -p "$TMP/dir-detect/codex"
out=$(env -i HOME="$TMP/dir-detect/home" PATH="$BIN:$BASE_PATH" \
      CLAUDE_DIR="$TMP/dir-detect/claude" CODEX_DIR="$TMP/dir-detect/codex" \
      bash "$INSTALL" --target auto 2>&1)
wrote "$TMP/dir-detect/codex" && pass "an existing ~/.codex is enough to detect Codex" || fail "should have detected Codex from its directory" "$out"
wrote "$TMP/dir-detect/claude" && fail "Claude must stay undetected" || pass "Claude stays undetected"

echo "== dry run writes nothing for either runtime"
stub claude codex
out=$(run dry --target both --plan max --fable yes --dry-run)
wrote "$TMP/dry/claude" && fail "a dry run wrote to the Claude tree" || pass "the Claude tree is untouched"
wrote "$TMP/dry/codex" && fail "a dry run wrote to the Codex tree" || pass "the Codex tree is untouched"
printf '%s' "$out" | grep -c >/dev/null '== claude:' && pass "the dry run has a Claude section" || fail "no Claude section" "$out"
printf '%s' "$out" | grep -c >/dev/null '== codex:' && pass "the dry run has a Codex section" || fail "no Codex section" "$out"
printf '%s' "$out" | grep -c >/dev/null '{{' && fail "the dry run left an unrendered placeholder" || pass "every placeholder is rendered"

summary "dual-runtime install"
