#!/usr/bin/env bash
# /status resolves the project the same way the guards do, and stays short.
#
# skills/status/status.py prints `root:` first. It exists so a reader can see
# WHICH .ai/ governs the directory they are in — a .ai/ in an ancestor, or in
# $HOME, silently arms the path and scope guards for every repository below it,
# and that is not visible from anywhere else. The line is only worth anything
# while it agrees with find_ai_root in hooks/lib/ai-hook-common.sh, so this
# suite compares the two, case by case. Then the length: at most twenty lines
# (redesign R31), with a task in flight and without one.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATUS="$PLUGIN_ROOT/skills/status/status.py"
ALIAS="$PLUGIN_ROOT/skills/ai-status/SKILL.md"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

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
        python3 -I "$2" | sed -n "s/^root: //p" | grep -v "^none" || printf "\n"
        AI_CWD=$PWD
        find_ai_root "$PWD" || printf "\n"
      ' _ "$PLUGIN_ROOT" "$STATUS" 2>/dev/null )
}

check() {  # check <label> <dir> <expected, relative to TMP, or EMPTY>
    local label="$1" dir="$2" expect="$3" out status guard
    out=$(resolved "$dir")
    status=$(printf '%s' "$out" | sed -n 1p); guard=$(printf '%s' "$out" | sed -n 2p)
    status=${status#"$TMP"/}; guard=${guard#"$TMP"/}
    [ -n "$status" ] || status=EMPTY
    [ -n "$guard" ] || guard=EMPTY
    if [ "$status" != "$guard" ]; then
        fail "$label: status.py and the guard disagree" "status=$status guard=$guard"
    elif [ "$status" != "$expect" ]; then
        fail "$label: both agree on the wrong root" "got=$status expected=$expect"
    else
        pass "$label ($status)"
    fi
}

echo "== status.py and find_ai_root resolve the same root"
check "its own .ai/ at the repository root" "$TMP/outer/repo"          outer/repo
check "its own .ai/, from a subdirectory"   "$TMP/outer/repo/src/deep" outer/repo
rm -rf "$TMP/outer/repo/.ai"
check "a .ai/ inherited from an ancestor"   "$TMP/outer/repo"          outer
check "inherited, from a subdirectory"      "$TMP/outer/repo/src/deep" outer
check "no .ai/ anywhere above"              "$TMP/bare/src"            EMPTY
out=$(python3 -I "$STATUS" --root "$TMP/outer/repo/src/deep")
[ "$(sed -n 's/^root: //p' <<<"$out")" = "$TMP/outer" ] \
    && pass "--root starts the same walk from another directory" || fail "--root" "$out"
out=$(cd "$TMP/bare/src" && python3 -I "$STATUS"); rc=$?
[ $rc = 1 ] && grep -q '^root: none' <<<"$out" \
    && pass "no .ai/ above: root: none, exit 1" || fail "no root" "rc=$rc $out"

echo "== no task in flight"
out=$(python3 -I "$STATUS" --root "$TMP/outer"); rc=$?
[ $rc = 0 ] && [ "$(wc -l <<<"$out")" -le 3 ] && grep -q '^task: none — no task in flight' <<<"$out" \
    && grep -q '^schema: project 0 · plugin [0-9]' <<<"$out" \
    && pass "root, no task in flight and schema: three lines" || fail "no-task output" "rc=$rc $out"

echo "== a populated task stays within twenty lines"
P="$TMP/proj"; mkdir -p "$P/src" "$P/.ai/policies"
git -C "$P" init -q -b main; git -C "$P" config user.email t@example.com; git -C "$P" config user.name t
printf 'base\n' > "$P/src/a.py"; git -C "$P" add -A; git -C "$P" commit -qm base
printf '{"sensors": {"tests": {"max_suite_runs": 2}}, "review_rounds_max": 2}\n' > "$P/.ai/policies/risk-tiers.json"
printf '6\n' > "$P/.ai/VERSION"
S() { env -u AI_UNATTENDED python3 "$PLUGIN_ROOT/skills/ai-task/state.py" --root "$P" "$@"; }
files=$(for i in $(seq 1 30); do printf 'src/f%d.py,' "$i"; done)
S quick --goal "$(printf 'a goal long enough to wrap\nand written over\nthree lines')" --workflow feature --tier T3 \
  --files "${files%,}" --note "fixture" >/dev/null 2>&1
S risks --add "first risk" >/dev/null; S risks --add "second risk" >/dev/null
S risks --add "$(printf 'a risk\nwritten over\nthree lines')" >/dev/null
S ask "one question" --option "A: yes" --option "B: no" >/dev/null 2>&1
S ask "two question" --option "A: yes" --option "B: no" >/dev/null 2>&1
out=$(python3 -I "$STATUS" --root "$P"); rc=$?
n=$(wc -l <<<"$out")
[ $rc = 0 ] && [ "$n" -le 20 ] && pass "a populated task: $n lines, at most 20" || fail "too long or failed" "rc=$rc n=$n $out"
for prefix in "root: $P" "task: T-" "tier: T3 · workflow feature" "stage: " "step: 1 (0 of 1 done) — files: src/f1.py" \
              "verify: tests not_run · suite runs 0/2" "review: " "questions: 2 pending" "risks: 3 open — first risk" "task: T-2026" \
              "schema: project 6 · plugin" "last event: "; do
    grep -qF -- "$prefix" <<<"$out" && pass "it shows: $prefix" || fail "missing: $prefix" "$out"
done
! grep -vqE '^[a-z ]+: ' <<<"$out" \
    && pass "a multi-line goal or risk stays on its own line (every line starts with its key)" || fail "a value wrapped onto its own line" "$out"
grep -q '(+26 more)' <<<"$out" && pass "a long file list is shortened, not wrapped" || fail "file list not shortened" "$out"

echo "== ai-status is an alias"
[ "$(wc -l < "$ALIAS")" -le 12 ] && pass "ai-status/SKILL.md is at most 12 lines" || fail "alias too long" "$(wc -l < "$ALIAS")"
desc=$(sed -n 's/^description: //p' "$ALIAS")
[ "$(printf '%s' "$desc" | wc -c)" -le 80 ] && pass "its description is at most 80 bytes" || fail "alias description" "$desc"
[ "$(awk 'f && NF {print; exit} /^---$/ {c++; if (c == 2) f = 1}' "$ALIAS")" = "deprecated → /status" ] \
    && pass "its first body line is 'deprecated → /status'" || fail "alias first line"
[ "$(sed -n 's/^description: //p' "$PLUGIN_ROOT/skills/status/SKILL.md" | wc -c)" -le 1024 ] \
    && pass "status/SKILL.md's description fits 1024 bytes" || fail "status description too long"

summary "status project root"
