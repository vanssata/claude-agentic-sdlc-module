#!/usr/bin/env bash
# Shared harness for the guard tests. Each fixture is a JSON file:
#   { "case": "...", "expect": "allow" | "deny", "payload": { ...hook stdin... } }
# The literal __ROOT__ inside a payload is replaced with the scratch project path.
set -uo pipefail

PLUGIN_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0
FAIL=0

fail() { FAIL=$((FAIL + 1)); printf '  FAIL  %s\n' "$1"; [ -n "${2:-}" ] && printf '        %s\n' "$2"; }
pass() { PASS=$((PASS + 1)); printf '  ok    %s\n' "$1"; }

# run_fixture <guard-script> <fixture.json> <root>
run_fixture() {
    local guard="$1" fixture="$2" root="$3"
    local name expect payload out decision
    name=$(jq -r '.case' "$fixture")
    expect=$(jq -r '.expect' "$fixture")
    payload=$(jq -c '.payload' "$fixture" | sed "s|__ROOT__|$root|g")

    out=$(printf '%s' "$payload" | "$guard" 2>&1)
    if [ -z "$out" ]; then
        decision=allow
    else
        decision=$(printf '%s' "$out" | jq -r '.hookSpecificOutput.permissionDecision // "malformed"' 2>/dev/null || echo malformed)
    fi

    if [ "$decision" = "$expect" ]; then
        pass "$(basename "$fixture"): $name"
    else
        fail "$(basename "$fixture"): $name" "expected $expect, got $decision${out:+ — $(printf '%s' "$out" | head -c 200)}"
    fi
}

# run_codex_fixtures <guard-script> <guard-key> <root> — the Codex payloads for
# one guard. They live in one directory because they share a schema, and each
# suite picks its own out of it, reusing the project tree that suite built.
run_codex_fixtures() {
    local guard="$1" key="$2" root="$3" f
    for f in "$PLUGIN_ROOT"/tests/fixtures/codex-hooks/*.json; do
        [ -e "$f" ] || continue
        [ "$(jq -r '.guard // ""' "$f")" = "$key" ] || continue
        run_fixture "$guard" "$f" "$root"
    done
}

# assert_fails_open <guard-script> <description> — malformed input must exit 0
# and print nothing, so a broken payload never makes the tool unusable.
assert_fails_open() {
    local guard="$1" name="$2" input="${3-}" out rc
    out=$(printf '%s' "$input" | "$guard" 2>&1); rc=$?
    if [ $rc -eq 0 ] && [ -z "$out" ]; then
        pass "$name"
    else
        fail "$name" "exit $rc, output: $(printf '%s' "$out" | head -c 200)"
    fi
}

summary() {
    printf '\n%s: %d passed, %d failed\n' "$1" "$PASS" "$FAIL"
    [ "$FAIL" -eq 0 ]
}
