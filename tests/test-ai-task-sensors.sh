#!/usr/bin/env bash
# sensors.py: the deterministic measurements /ai-task gates on.
#
# The scratch project lives under a path containing a space on purpose — every
# path this module hands to git or to a project command must survive one.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SENSORS="$PLUGIN_ROOT/skills/ai-task/sensors.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/with space/project"
mkdir -p "$ROOT/.ai/state" "$ROOT/.ai/reports" "$ROOT/.ai/policies"
N() { python3 "$SENSORS" --root "$ROOT" "$@"; }
G() { git -C "$ROOT" "$@" >/dev/null 2>&1; }

git -C "$ROOT" init -q 2>/dev/null || git init -q "$ROOT"
G config user.email "t@example.com"; G config user.name "Test"
mkdir -p "$ROOT/src/Payment" "$ROOT/tests" "$ROOT/docs"
printf 'base\n' > "$ROOT/src/app.php"
printf 'lock\n' > "$ROOT/composer.lock"
G add -A; G commit -m base

echo "== section 1: snapshot"
BASE=$(N snapshot)
case "$BASE" in
    [0-9a-f][0-9a-f]*) pass "snapshot prints a tree hash" ;;
    *) fail "snapshot should print a tree hash" "$BASE" ;;
esac
[ "$BASE" = "$(git -C "$ROOT" rev-parse 'HEAD^{tree}')" ] \
    && pass "a clean worktree snapshots to HEAD's tree" \
    || fail "a clean worktree should equal HEAD's tree" "$BASE"

# The real index must come out of a snapshot exactly as it went in: the module
# copies it, and a developer who had staged work keeps it staged.
printf 'staged\n' > "$ROOT/src/staged.php"; G add src/staged.php
INDEX_BEFORE=$(git -C "$ROOT" diff --cached --name-only)
N snapshot >/dev/null
[ "$(git -C "$ROOT" diff --cached --name-only)" = "$INDEX_BEFORE" ] \
    && pass "the developer's index is untouched" || fail "snapshot must not touch the index"
G rm --cached -q src/staged.php; rm -f "$ROOT/src/staged.php"

printf 'state\n' > "$ROOT/.ai/state/current.json"
printf 'untracked\n' > "$ROOT/src/new.php"
UNTRACKED_TREE=$(N snapshot)
[ "$UNTRACKED_TREE" != "$BASE" ] \
    && pass "an untracked source file is in the tree, as git diff HEAD would not show" \
    || fail "an untracked file should change the tree"
git -C "$ROOT" ls-tree -r --name-only "$UNTRACKED_TREE" | grep -q '^\.ai/state/' \
    && fail "the task's own state must be dropped from the snapshot" \
    || pass "the task's own state is dropped from the snapshot"
rm -f "$ROOT/src/new.php"

echo "== section 2: diff measurement"
printf 'base\nchanged\nagain\n' > "$ROOT/src/app.php"
printf 'newline in a lock file\n' >> "$ROOT/composer.lock"
printf '# docs\n' > "$ROOT/docs/guide.md"
AFTER=$(N snapshot)

OUT=$(N diff --from "$BASE" --to "$AFTER" --tier T2 --scope step --format json)
[ "$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["files"])')" = 1 ] \
    && pass "the lock file is excluded and the doc is unbudgeted: 1 counted file" \
    || fail "should count exactly the one source file" "$OUT"
[ "$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(json.load(sys.stdin)["lines"])')" = 2 ] \
    && pass "lines are added + deleted after exclusions" || fail "should count 2 lines" "$OUT"
printf '%s' "$OUT" | grep -q '"excluded_lines": 1' \
    && pass "the excluded lines are reported, not silently dropped" || fail "excluded_lines should be 1"
printf '%s' "$OUT" | grep -q '"unbudgeted_lines": 1' \
    && pass "the docs scope is counted but not budgeted" || fail "unbudgeted_lines should be 1"

# git's own numbers are the reference; a sensor that disagrees with git is wrong.
GIT_LINES=$(git -C "$ROOT" diff --numstat "$BASE" "$AFTER" -- src/app.php | awk '{print $1+$2}')
[ "$GIT_LINES" = 2 ] && pass "the count matches git diff --numstat" || fail "git says $GIT_LINES"

N diff --from "$BASE" --to "$AFTER" --tier T2 --allowed "src/**" >/dev/null 2>&1
[ $? -eq 0 ] && pass "a file inside allowed_files is in scope" || fail "src/** should allow src/app.php"
OUT=$(N diff --from "$BASE" --to "$AFTER" --tier T2 --allowed "tests/**"); RC=$?
[ $RC -eq 2 ] && printf '%s' "$OUT" | grep -q 'unscoped: src/app.php' \
    && pass "a file outside allowed_files is red and named" || fail "should be red and name the file" "$OUT($RC)"

# The scope guard's reading of a plan glob, not a stricter one: a file the hook
# allows must never be refused by the measurement.
mkdir -p "$ROOT/src/Payment"; printf 'fee\n' > "$ROOT/src/Payment/Fee.php"
DEEP=$(N snapshot)
N diff --from "$BASE" --to "$DEEP" --allowed "src/*.php" >/dev/null 2>&1
[ $? -eq 0 ] && pass "a plan glob reads as the scope guard reads it (* crosses /)" \
             || fail "src/*.php must match src/Payment/Fee.php, as the hook does"

echo "== section 2b: the budget"
python3 - "$ROOT" <<'PY'
import json, sys
root = sys.argv[1]
policy = {"version": 3, "diff_budget": {"per_step": {"T2": {"max_lines": 1, "max_files": 1}},
                                        "per_task": {"T2": {"max_lines": 1, "max_files": 1}},
                                        "exclude": [], "unbudgeted_scopes": []}}
with open(root + "/.ai/policies/risk-tiers.json", "w") as fh:
    json.dump(policy, fh)
PY
OUT=$(N diff --from "$BASE" --to "$AFTER" --tier T2 --scope step); RC=$?
[ $RC -eq 2 ] && printf '%s' "$OUT" | grep -q 'over: ' \
    && pass "over the per-step budget is red and says by how much" || fail "should be red" "$OUT($RC)"
printf '%s' "$OUT" | grep -q 'budget 1 / 1' \
    && pass "the project's own numbers are used, not the defaults" || fail "should read the project policy"
rm -f "$ROOT/.ai/policies/risk-tiers.json"

echo "== section 2c: unavailable is never a refusal"
BARE="$TMP/with space/bare"; mkdir -p "$BARE/.ai/state"
OUT=$(python3 "$SENSORS" --root "$BARE" snapshot); RC=$?
[ $RC -eq 3 ] && printf '%s' "$OUT" | grep -qi unavailable \
    && pass "a non-git root is unavailable (exit 3), not an error" || fail "should exit 3" "$OUT($RC)"
OUT=$(N diff --from "$BASE" --to 0000000000000000000000000000000000000000); RC=$?
[ $RC -eq 3 ] && printf '%s' "$OUT" | grep -q 'UNAVAIL' \
    && pass "a tree that is gone is unavailable, not a crash" || fail "should exit 3" "$OUT($RC)"

echo "== section 3: re-scoring and detect"
OUT=$(N rescore --from "$BASE" --to "$AFTER" --declared T2); RC=$?
[ $RC -eq 0 ] && printf '%s' "$OUT" | grep -q 'green' \
    && pass "a source-only diff keeps its declared tier" || fail "should stay T2" "$OUT($RC)"

OUT=$(N rescore --from "$BASE" --to "$DEEP" --declared T2); RC=$?
[ $RC -eq 2 ] && printf '%s' "$OUT" | grep -q 'T2 -> T4' \
    && pass "a diff reaching **/Payment/** re-scores to T4" || fail "should raise to T4" "$OUT($RC)"

OUT=$(N rescore --from "$BASE" --to "$DEEP" --declared T5)
printf '%s' "$OUT" | grep -q 'T5' \
    && pass "re-scoring never lowers a declared tier (downgrade_rule)" || fail "must not lower" "$OUT"

printf '{"scripts": {"lint": "eslint ."}}\n' > "$ROOT/package.json"
OUT=$(N detect)
printf '%s' "$OUT" | grep -q 'lint_command: npm run lint' \
    && pass "detect proposes the command it found" || fail "should propose npm run lint" "$OUT"
printf '%s' "$OUT" | grep -q 'typecheck_command: none' \
    && pass "nothing detected proposes an explicit none, never a silent green" || fail "should ask for none" "$OUT"
[ ! -e "$ROOT/node_modules" ] && pass "detect runs nothing it detected" || fail "detect must not run a tool"

summary "sensors"
