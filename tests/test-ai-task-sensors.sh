#!/usr/bin/env bash
# sensors.py: tree snapshots, tree diffs and the project's own commands (R6).
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
rm -f "$ROOT/src/new.php" "$ROOT/.ai/state/current.json"

echo "== section 2: the diff is a file list between two trees"
printf 'base\nchanged\nagain\n' > "$ROOT/src/app.php"
printf 'newline in a lock file\n' >> "$ROOT/composer.lock"
printf '# docs\n' > "$ROOT/docs/guide.md"
AFTER=$(N snapshot)

OUT=$(N diff --from "$BASE" --to "$AFTER"); RC=$?
[ $RC -eq 0 ] && [ "$OUT" = "$(printf 'M\tcomposer.lock\nA\tdocs/guide.md\nM\tsrc/app.php')" ] \
    && pass "every changed file is listed with its status, a lock file included" \
    || fail "diff should list the three files" "$OUT($RC)"
OUT=$(N diff --from "$BASE" --to "$AFTER" --format json)
[ "$(printf '%s' "$OUT" | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["files"]))')" = 3 ] \
    && pass "--format json carries the same list" || fail "json should list three files" "$OUT"
# git's own list is the reference; a sensor that disagrees with git is wrong.
[ "$(git -C "$ROOT" diff --name-only "$BASE" "$AFTER" | wc -l)" = 3 ] \
    && pass "the list matches git diff --name-only" || fail "git disagrees"

OUT=$(N diff --to "$AFTER"); RC=$?
[ $RC -eq 3 ] && grep -q 'no base tree recorded' <<<"$OUT" \
    && pass "no base tree is unavailable, never an empty diff" || fail "should be unavailable" "$OUT($RC)"

# The scope guard's reading of a plan glob, not a stricter one: a file the hook
# allows must never be refused by state.py's step-done.
OUT=$(python3 - "$SENSORS" <<'PY'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sensors", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
print(bool(m.scope_any("src/Payment/Fee.php", ["src/*.php"])), bool(m.scope_any("src/a/b.php", ["src"])),
      bool(m.scope_any("tests/x.php", ["src/**"])))
PY
)
[ "$OUT" = "True True False" ] \
    && pass "a plan glob reads as the scope guard reads it (* crosses /, a directory prefixes)" \
    || fail "scope_any should read globs as ai-scope-guard.sh does" "$OUT"

echo "== section 3: run is the project's own command, to the end, into a log"
cat > "$ROOT/.ai/policies/testing.md" <<'MD'
# Testing policy
verify_command:      printf 'ok\n'; exit ${FAKE_EXIT:-0}
step_test_command:   printf 'step %s\n' {files}
e2e_command:         none
single_test:         # the template's comment, not a value
MD
OUT=$(N run --scope suite --log "$TMP/suite.log"); RC=$?
[ $RC -eq 0 ] && grep -q '^suite *green' <<<"$OUT" && [ "$(cat "$TMP/suite.log")" = ok ] \
    && pass "a green run exits 0 and its output is in the log" || fail "green run" "$OUT($RC)"
OUT=$(FAKE_EXIT=1 N run --scope suite --log "$TMP/suite.log"); RC=$?
[ $RC -eq 2 ] && grep -q 'RED' <<<"$OUT" && pass "a red run exits 2" || fail "red run should exit 2" "$OUT($RC)"
N run --scope step --files "tests/a b.php" --log "$TMP/step.log" >/dev/null
[ "$(cat "$TMP/step.log")" = "step tests/a b.php" ] \
    && pass "{files} takes the step's paths, quoted" || fail "files should expand" "$(cat "$TMP/step.log")"
OUT=$(N run --scope e2e); RC=$?
[ $RC -eq 0 ] && grep -q 'n/a' <<<"$OUT" && pass "a command written as none is not applicable" \
    || fail "none should be n/a" "$OUT($RC)"
OUT=$(N run --scope single --test x); RC=$?
[ $RC -eq 3 ] && grep -q 'not written down' <<<"$OUT" \
    && pass "a comment-only line is not written down yet, which is not none" || fail "single" "$OUT($RC)"

echo "== section 3b: the project command never gets the human's terminal"
# A human runs 'verify --by' past the budget from their own terminal. The suite
# must not inherit it: an installer that prompts when stdin is a tty, or a test
# of the terminal-only approve route, behaves differently there (T-2026-10-26-001 run 17).
OUT=$(python3 - "$SENSORS" "$TMP/tty.log" <<'PY'
import importlib.util, os, pty, subprocess, sys
sensors, log = sys.argv[1], sys.argv[2]
code = ("import importlib.util, sys; s = importlib.util.spec_from_file_location('sensors', sys.argv[1]); "
        "m = importlib.util.module_from_spec(s); s.loader.exec_module(m); "
        "m.run_command('.', 'if [ -t 0 ]; then echo tty; else echo notty; fi; read -r x; echo read=$?', sys.argv[2], 10)")
master, slave = pty.openpty()
done = subprocess.run([sys.executable, "-c", code, sensors, log], stdin=slave, timeout=30, check=False)
os.close(slave); os.close(master)
print(done.returncode, open(log).read().replace("\n", " ").strip())
PY
)
[ "$OUT" = "0 notty read=1" ] && pass "run_command gives the command /dev/null, not a terminal, as stdin" \
    || fail "the command saw the caller's terminal" "$OUT"

echo "== section 4: the old sensors are gone (R6)"
for c in rescore check report bite detect; do
    N "$c" >/dev/null 2>&1; [ $? -eq 2 ] && pass "sensors.py $c is gone" || fail "sensors.py $c should be gone"
done
for f in --tier --allowed --scope; do
    N diff --from "$BASE" --to "$AFTER" "$f" x >/dev/null 2>&1
    [ $? -eq 2 ] && pass "diff takes no $f: size is not measured" || fail "diff should refuse $f"
done

summary "sensors"
