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

echo "== section 4: the step-done gate"
GATE="$TMP/with space/gate"
mkdir -p "$GATE/.ai/state" "$GATE/.ai/reports" "$GATE/.ai/policies" "$GATE/src/Payment" "$GATE/tests"
STATE_PY="$PLUGIN_ROOT/skills/ai-task/state.py"
S() { python3 "$STATE_PY" --root "$GATE" "$@"; }
J() { python3 -c 'import json,sys
d = json.load(open(sys.argv[1]))
for part in sys.argv[2].split("."):
    d = d[int(part)] if isinstance(d, list) else (d or {}).get(part)
print(json.dumps(d) if isinstance(d, (list, dict)) else ("" if d is None else d))' "$GATE/.ai/state/current.json" "$1"; }
git init -q "$GATE"; git -C "$GATE" config user.email t@example.com
git -C "$GATE" config user.name Test
printf 'one\n' > "$GATE/src/app.php"; git -C "$GATE" add -A
git -C "$GATE" commit -qm base
cat > "$GATE/.ai/policies/risk-tiers.json" <<'JSON'
{"version": 3,
 "diff_budget": {"per_step": {"T2": {"max_lines": 5, "max_files": 5}},
                 "per_task": {"T2": {"max_lines": 400, "max_files": 15},
                              "T4": {"max_lines": 400, "max_files": 15}},
                 "exclude": [], "unbudgeted_scopes": ["docs"]},
 "path_scopes": [{"scope": "tests", "min_tier": "T1", "paths": ["tests/**"]},
                 {"scope": "payments", "min_tier": "T4", "paths": ["**/Payment/**"]}],
 "remediation_rounds": 2}
JSON

TASK=$(S init --goal "widen the fee" --workflow feature)
BASE_TREE=$(S get --field diff.base_tree)
[ -n "$BASE_TREE" ] && [ "$BASE_TREE" != "None" ] \
    && pass "init records the tree the task starts from" || fail "init should record a base tree"
S risk T2 --note "isolated" >/dev/null
cat > "$TMP/steps.json" <<'JSON'
[{ "step_id": "1", "description": "widen the fee", "allowed_files": ["src/*.php", "tests/**"],
   "required_tests": ["tests/FeeTest.php"] }]
JSON
S plan --ref ".ai/reports/$TASK/plan.md" --steps "$TMP/steps.json" >/dev/null
S step 1 >/dev/null
[ -n "$(J approved_plan.steps.0.tree_before)" ] \
    && pass "starting a step records the tree it began with" || fail "step should record tree_before"

printf 'one\ntwo\nthree\nfour\nfive\nsix\nseven\n' > "$GATE/src/app.php"
OUT=$(S step-done 1 2>&1); RC=$?
[ $RC -eq 6 ] && printf '%s' "$OUT" | grep -q DIFF_BUDGET_EXCEEDED \
    && pass "a step over its tier's budget exits 6" || fail "should exit 6" "$OUT($RC)"
printf '%s' "$OUT" | grep -q 'step-split' \
    && pass "the refusal names the way out" || fail "should suggest step-split" "$OUT"
[ "$(S get --field approved_plan.current_step_id)" = 1 ] \
    && pass "a refused step stays in progress — no work is lost" || fail "step should stay current"

printf 'one\ntwo\n' > "$GATE/src/app.php"
mkdir -p "$GATE/lib"; printf 'stray\n' > "$GATE/lib/Other.php"
OUT=$(S step-done 1 2>&1); RC=$?
[ $RC -eq 6 ] && printf '%s' "$OUT" | grep -q 'SCOPE_CHANGE_REQUIRED' \
    && pass "a file outside the step's files exits 6 and is named" || fail "should exit 6" "$OUT($RC)"
rm -f "$GATE/lib/Other.php"

# The step grew a second concern: the payment file is its own step now. The
# original step's own glob still matches it, so the split must say otherwise.
printf 'fee\ntwo\nthree\nfour\nfive\nsix\n' > "$GATE/src/Payment/Fee.php"
OUT=$(S step-done 1 2>&1); RC=$?
[ $RC -eq 6 ] && pass "the step that grew a second concern is refused" || fail "should refuse" "$OUT($RC)"
OUT=$(S step-split 1 --files "src/Payment/*.php" --note "the payment part" 2>&1)
printf '%s' "$OUT" | grep -q '1.2' && pass "step-split makes a sibling step" || fail "should split" "$OUT"
OUT=$(S step-done 1 2>&1); RC=$?
[ $RC -eq 0 ] && pass "after the split the step measures only its own files" \
               || fail "step 1 should pass now" "$OUT($RC)"
printf '%s' "$OUT" | grep -q 'step 1 diff' \
    && pass "step-done reports what it measured" || fail "should print the step diff" "$OUT"

echo "== section 5: re-scoring at the gate"
[ "$(S get --field risk_tier)" = T4 ] \
    && pass "the payment file re-scores the task from T2 to T4" || fail "should raise to T4"
S events --last 20 --format jsonl 2>/dev/null | grep -q '"event": "tier_raised"' \
    && pass "the raise is in the journal" || fail "tier_raised should be journalled"
J diff.rescore_reasons | grep -q payments \
    && pass "the reason names the scope and the file" || fail "reasons should name payments"

echo "== section 6: only a human lowers a tier"
OUT=$(S risk T2 --note "it is small really" 2>&1 </dev/null); RC=$?
[ $RC -eq 5 ] && printf '%s' "$OUT" | grep -q 'APPROVAL_REFUSED' \
    && pass "an agent cannot lower a tier (downgrade_rule)" || fail "should exit 5" "$OUT($RC)"
[ "$(S get --field risk_tier)" = T4 ] && pass "the tier is unchanged by the refusal" || fail "tier moved"
OUT=$(AI_UNATTENDED=1 S risk T2 --by "Ivan" --note "reviewed by hand" 2>&1 </dev/null); RC=$?
[ $RC -eq 0 ] && [ "$(S get --field risk_tier)" = T2 ] \
    && pass "a human with --by lowers it" || fail "should lower with --by" "$OUT($RC)"
[ "$(S get --field risk_tier_lowered.by)" = "Ivan" ] \
    && pass "who lowered it, and from what, is recorded" || fail "should record the lowering"
OUT=$(S risk T5 --note "actually a migration" 2>&1 </dev/null); RC=$?
[ $RC -eq 0 ] && pass "raising a tier needs nobody's permission" || fail "raising should work" "$OUT"

# --force is the escape hatch a human uses when a refusal is wrong; here it is
# only bookkeeping, to reach the third remediation round.
S step 1.2 >/dev/null; S step-done 1.2 --force >/dev/null
S remediate --files "tests/**" --note "first batch" >/dev/null
S step-done R1 --force >/dev/null
S remediate --files "tests/**" --note "second batch" >/dev/null
S step-done R2 --force >/dev/null
OUT=$(S remediate --files "tests/**" --note "third batch" 2>&1 </dev/null); RC=$?
[ $RC -eq 5 ] && printf '%s' "$OUT" | grep -q 'round 3' \
    && pass "a third remediation round needs the human (remediation_rule)" \
    || fail "should refuse round 3" "$OUT($RC)"

echo "== section 7: running the tests is the state's job, not an agent's"
cat > "$GATE/.ai/policies/testing.md" <<'MD'
# Testing policy
verify_command:      printf 'ok\n'; exit ${FAKE_EXIT:-0}
step_test_command:   printf 'step %s\n' {files}
e2e_command:         none
single_test:         printf 'one %s\n'
lint_command:        none
typecheck_command:   none
MD
OUT=$(S test-run --scope suite 2>&1); RC=$?
[ $RC -eq 0 ] && pass "a green run needs no agent at all" || fail "green run should exit 0" "$OUT($RC)"
[ "$(printf '%s\n' "$OUT" | wc -l)" -le 6 ] \
    && pass "the session sees at most six lines, never the log" || fail "too much output" "$OUT"
[ "$(S get --field test_status)" = passing ] \
    && pass "exit 0 records test_status deterministically" || fail "test_status should be passing"
LOG=$(J tests.runs.0.log)
[ -f "$GATE/$LOG" ] && pass "the output is in a file: $LOG" || fail "the log should exist" "$LOG"
[ -n "$(J tests.runs.0.tree)" ] \
    && pass "the run is bound to the tree it ran on" || fail "a run should record its tree"

OUT=$(S test-run --scope suite --env-retry 2>&1); RC=$?
[ $RC -ne 0 ] && printf '%s' "$OUT" | grep -q 'classified' \
    && pass "--env-retry is refused until a failure was classified as one" \
    || fail "should refuse an unclassified retry" "$OUT($RC)"

FAKE_EXIT=1 S test-run --scope suite >/dev/null 2>&1
[ "$(S get --field test_status)" != passing ] \
    && pass "a red run does not report itself as passing" || fail "red run should not be passing"
S test-run --scope suite >/dev/null 2>&1
S test-run --scope suite >/dev/null 2>&1
S test-run --scope suite >/dev/null 2>&1
OUT=$(S test-run --scope suite 2>&1); RC=$?
[ $RC -eq 6 ] && printf '%s' "$OUT" | grep -q 'run budget exhausted' \
    && pass "the suite cannot be run forever: the cap is the human's cue" \
    || fail "should exhaust the run budget" "$OUT($RC)"

echo "== section 8: the static sensors"
NG() { python3 "$SENSORS" --root "$GATE" "$@"; }
OUT=$(NG check --no-bite 2>&1)
printf '%s' "$OUT" | grep -q 'lint          n/a' \
    && pass "lint_command: none is not applicable, and does not block" || fail "none should be n/a" "$OUT"
printf '%s' "$OUT" | grep -q 'traceability  RED' \
    && pass "a finished step whose named test does not exist is red" || fail "traceability should be red" "$OUT"

# A missing line is unavailable — never green — and says what to write.
python3 - "$GATE" <<'PY2'
import sys, re
p = sys.argv[1] + "/.ai/policies/testing.md"
s = open(p).read().replace("typecheck_command:   none\n", "")
open(p, "w").write(s)
PY2
printf '{}\n' > "$GATE/tsconfig.json"
OUT=$(NG check --no-bite 2>&1)
printf '%s' "$OUT" | grep -q 'typecheck     UNAVAIL' \
    && pass "a missing typecheck_command is unavailable, not green" || fail "should be unavailable" "$OUT"
printf '%s' "$OUT" | grep -q 'npx tsc --noEmit' \
    && pass "and it proposes the line it found" || fail "should propose tsc" "$OUT"
printf '%s' "$OUT" | grep -q 'review: required' \
    && pass "one unavailable sensor is enough to keep the review" || fail "review should be required" "$OUT"
rm -f "$GATE/tsconfig.json"

# The same eight lines in two files is the cheapest half of what a reviewer
# would have to read the whole diff to find.
for f in dup1 dup2; do
  printf 'function a() {\n  one();\n  two();\n  three();\n  four();\n  five();\n  six();\n  seven();\n}\n' \
      > "$GATE/src/$f.php"
done
OUT=$(NG check --only duplicates 2>&1)
printf '%s' "$OUT" | grep -q 'duplicates    RED' \
    && pass "a block repeated in two files is red" || fail "duplicates should be red" "$OUT"
rm -f "$GATE/src/dup1.php" "$GATE/src/dup2.php"

echo "== section 8b: a result belongs to the tree it was taken on"
NG check --no-bite >/dev/null 2>&1
printf 'moved on\n' >> "$GATE/src/app.php"
OUT=$(NG report 2>&1)
printf '%s' "$OUT" | grep -q 'STALE' \
    && pass "a report from an older tree reads as stale, not as a pass" || fail "should be stale" "$OUT"
printf '%s' "$OUT" | grep -q 'review: required' \
    && pass "and stale keeps the review" || fail "stale should keep the review" "$OUT"

LEDGER="$GATE/.ai/reports/$TASK/review-ledger.md"
[ -f "$LEDGER" ] && grep -q 'sensors.py' "$LEDGER" \
    && pass "what a sensor settled is written into the review ledger" || fail "ledger should have rows"
grep -q 'CONFIRMED\|DEFECT' "$LEDGER" \
    && pass "each row says whether it confirmed or found something" || fail "rows need an outcome"

echo "== section 9: the test must bite"
BITE="$TMP/with space/bite"
mkdir -p "$BITE/.ai/state" "$BITE/.ai/reports" "$BITE/.ai/policies" "$BITE/src" "$BITE/tests"
B() { python3 "$STATE_PY" --root "$BITE" "$@"; }
NB() { python3 "$SENSORS" --root "$BITE" "$@"; }
git init -q "$BITE"; git -C "$BITE" config user.email t@example.com
git -C "$BITE" config user.name Test
printf 'def fee(x):\n    return x\n' > "$BITE/src/fee.py"
# The test the plan names: it exercises the NEW behaviour, so it fails without it.
printf 'import sys; sys.path.insert(0, "src")\nfrom fee import fee\nassert fee(2) == 4\nprint("ok")\n' \
    > "$BITE/tests/fee_test.py"
# And one that never reaches the change, however green it looks.
printf 'print("ok")\n' > "$BITE/tests/blind_test.py"
git -C "$BITE" add -A; git -C "$BITE" commit -qm base
cat > "$BITE/.ai/policies/testing.md" <<'MD'
# Testing policy
verify_command:      python3 tests/fee_test.py
step_test_command:   python3 {files}
e2e_command:         none
lint_command:        none
typecheck_command:   none
MD
python3 - "$BITE" <<'PY2'
import json, sys
policy = {
    "version": 3,
    "diff_budget": {"per_step": {"T2": {"max_lines": 50, "max_files": 10}},
                    "per_task": {"T2": {"max_lines": 50, "max_files": 10}},
                    "exclude": [], "unbudgeted_scopes": ["docs"]},
    "path_scopes": [{"scope": "tests", "min_tier": "T1", "paths": ["tests/**"]}],
    "sensors": {"skip_review_at_or_below": "T2",
                "required_for_skip": ["tests", "lint", "typecheck", "diff", "rescore",
                                      "traceability", "duplicates", "bite"],
                "bite": {"timeout_seconds": 60, "required_from": "T2"},
                "tests": {"max_suite_runs": 5, "timeout_seconds": 60},
                "duplicates": {"min_lines": 8, "ignore_scopes": ["tests", "docs"]}},
    "remediation_rounds": 2}
json.dump(policy, open(sys.argv[1] + "/.ai/policies/risk-tiers.json", "w"), indent=2)
PY2
BTASK=$(B init --goal "double the fee" --workflow feature)
B risk T2 >/dev/null
cat > "$TMP/bsteps.json" <<'JSON'
[{ "step_id": "1", "description": "double it", "allowed_files": ["src/**"],
   "required_tests": ["tests/fee_test.py"] }]
JSON
B plan --ref ".ai/reports/$BTASK/plan.md" --steps "$TMP/bsteps.json" >/dev/null
B step 1 >/dev/null
printf 'def fee(x):\n    return x * 2\n' > "$BITE/src/fee.py"
B step-done 1 >/dev/null
B test-run --scope suite >/dev/null

TREE_BEFORE_BITE=$(NB snapshot)
OUT=$(NB bite 2>&1); RC=$?
[ $RC -eq 0 ] && printf '%s' "$OUT" | grep -q 'bite          green' \
    && pass "a test that fails without the change bites" || fail "bite should be green" "$OUT($RC)"
[ "$(NB snapshot)" = "$TREE_BEFORE_BITE" ] \
    && pass "the worktree is byte-identical afterwards" || fail "bite must restore the worktree"
[ ! -f "$BITE/.ai/state/bite.lock" ] \
    && pass "the recovery lock is cleared on a clean run" || fail "the lock should be cleared"

# The same green suite, a test that never reaches the change: not evidence.
python3 - "$BITE" <<'PY2'
import json, sys
p = sys.argv[1] + "/.ai/state/current.json"
state = json.load(open(p))
state["approved_plan"]["steps"][0]["required_tests"] = ["tests/blind_test.py"]
json.dump(state, open(p, "w"), indent=2)
PY2
OUT=$(NB bite 2>&1); RC=$?
[ $RC -eq 2 ] && printf '%s' "$OUT" | grep -q 'do not reach it' \
    && pass "a test that passes without the change is red, however green the suite is" \
    || fail "bite should be red" "$OUT($RC)"
[ "$(NB snapshot)" = "$TREE_BEFORE_BITE" ] \
    && pass "and the worktree is restored after a red run too" || fail "must restore after red"

# A characterization step promises the opposite: it describes what is already there.
python3 - "$BITE" <<'PY2'
import json, sys
p = sys.argv[1] + "/.ai/state/current.json"
state = json.load(open(p))
step = state["approved_plan"]["steps"][0]
step["kind"] = "characterization"
step["required_tests"] = ["tests/blind_test.py"]
json.dump(state, open(p, "w"), indent=2)
PY2
OUT=$(NB bite 2>&1); RC=$?
[ $RC -eq 0 ] && pass "a characterization test must pass at the base, and does" \
               || fail "characterization bite should be green" "$OUT($RC)"

echo "== section 9b: an interrupted revert is recoverable"
python3 - "$BITE" "$TREE_BEFORE_BITE" <<'PY2'
import json, sys
root, tree = sys.argv[1], sys.argv[2]
# What an interruption leaves behind: the lock, and a reverted worktree.
json.dump({"tree_after": tree, "paths": ["src/fee.py"], "at": "now", "why": "test"},
          open(root + "/.ai/state/bite.lock", "w"))
open(root + "/src/fee.py", "w").write("def fee(x):\n    return x\n")
PY2
[ "$(NB snapshot)" != "$TREE_BEFORE_BITE" ] || fail "the fixture should leave a reverted worktree"
OUT=$(NB bite --restore 2>&1)
[ "$(NB snapshot)" = "$TREE_BEFORE_BITE" ] \
    && pass "bite --restore puts back what an interrupted run left" || fail "--restore failed" "$OUT"
[ ! -f "$BITE/.ai/state/bite.lock" ] \
    && pass "and clears the lock once the tree matches" || fail "the lock should be gone"

summary "sensors"
