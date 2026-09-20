#!/usr/bin/env bash
# state.py: a full task round-trip, the validation rules, and the failure modes
# that must be loud rather than silent.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATE="$PLUGIN_ROOT/skills/ai-task/state.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"; mkdir -p "$ROOT/.ai/state" "$ROOT/.ai/reports"
S() { python3 "$STATE" --root "$ROOT" "$@"; }

echo "== state.py round trip"
TASK=$(S init --goal "add a payment fee" --workflow feature 2>&1)
case "$TASK" in T-*) pass "init prints a task id ($TASK)";; *) fail "init should print a task id" "$TASK";; esac

[ "$(S get --field current_stage)" = discovery ] && pass "a new task starts at discovery" || fail "should start at discovery"

S stage context >/dev/null
[ "$(S get --field current_stage)" = context ] && pass "stage advances" || fail "stage should advance"

S risk T4 --note "touches payments" >/dev/null
[ "$(S get --field risk_tier)" = T4 ] && pass "risk tier is recorded" || fail "risk tier should be recorded"

cat > "$TMP/steps.json" <<'JSON'
[
  { "step_id": "1", "description": "add the fee calculator",
    "allowed_files": ["src/Payment/*.php"], "forbidden_files": ["src/Payment/LegacyGateway.php"],
    "required_tests": ["tests/Payment/FeeTest.php"] },
  { "step_id": "2", "description": "wire it into checkout",
    "allowed_files": ["src/Checkout/*.php"] }
]
JSON
S plan --ref ".ai/reports/$TASK/implementation-plan.md" --steps "$TMP/steps.json" >/dev/null
[ "$(S get --field approved_plan.ref)" = ".ai/reports/$TASK/implementation-plan.md" ] && pass "plan ref recorded" || fail "plan ref should be recorded"

S step 1 >/dev/null
[ "$(S get --field approved_plan.current_step_id)" = 1 ] && pass "current step is set" || fail "current step should be set"

S step-done 1 >/dev/null
[ "$(S get --field approved_plan.current_step_id)" = "" ] && pass "current step cleared when the step is done" || fail "current step should clear"
S get --field completed_steps | grep -q '"1"' && pass "completed step is listed" || fail "completed step should be listed"

S set test_status passing >/dev/null
[ "$(S get --field test_status)" = passing ] && pass "test_status is settable" || fail "test_status should be settable"

S risks --add "legacy gateway path untested" >/dev/null
S get --field open_risks | grep -q legacy && pass "open risks are recorded" || fail "open risks should be recorded"

S approve --by "the human" >/dev/null
S get --field human_approval | grep -q '"granted": true' && pass "approval is recorded with who granted it" || fail "approval should be recorded"

S done >/dev/null
[ "$(S get --field current_stage)" = done ] && pass "task can be closed" || fail "task should close"

echo "== history is an audit trail"
n=$(S get --field history | jq 'length')
[ "$n" -ge 10 ] && pass "history recorded $n events" || fail "history should record every transition" "got $n"
S get --field history | jq -e '.[] | select(.event=="human_approval")' >/dev/null \
  && pass "history contains the approval event" || fail "history should contain the approval"

echo "== validation and failure modes"
out=$(S stage nonsense 2>&1); [ $? -ne 0 ] || true
printf '%s' "$out" | grep -q "stage must be one of" && pass "an unknown stage is rejected" || fail "unknown stage should be rejected" "$out"

out=$(S risk T9 2>&1 || true)
printf '%s' "$out" | grep -q "risk tier must be one of" && pass "an unknown risk tier is rejected" || fail "unknown tier should be rejected" "$out"

out=$(S set test_status green 2>&1 || true)
printf '%s' "$out" | grep -q "must be one of" && pass "an invalid test_status is rejected" || fail "invalid status should be rejected" "$out"

out=$(S step 99 2>&1 || true)
printf '%s' "$out" | grep -q "no step '99'" && pass "an unknown step id is rejected" || fail "unknown step should be rejected" "$out"

echo "== archive and re-init"
ARCHIVED=$(S archive)
[ -f "$ARCHIVED" ] && pass "archive writes the closed task under .ai/reports/" || fail "archive should write a file" "$ARCHIVED"
[ ! -f "$ROOT/.ai/state/current.json" ] && pass "archive clears current.json" || fail "archive should clear current.json"

S init --goal "second task" --workflow bugfix >/dev/null
S stage implementation >/dev/null
out=$(S init --goal "third task" --workflow bugfix 2>&1 || true)
printf '%s' "$out" | grep -q "still at stage" && pass "starting a second task over a live one is refused" || fail "should refuse to clobber a live task" "$out"
S init --goal "third task" --workflow bugfix --force >/dev/null && pass "--force starts a fresh task anyway" || fail "--force should work"

echo "== triage records the four inline stages in one call"
S triage T1 --note "isolated label change" --context "template + translation key" >/dev/null && pass "triage accepts a tier" || fail "triage failed"
[ "$(S get --field risk_tier)" = T1 ] && pass "triage sets the tier" || fail "triage should set the tier"
[ "$(S get --field current_stage)" = risk_classification ] && pass "triage lands on risk_classification" || fail "triage stage wrong"
n=$(S get --field history | jq '[.[] | select(.event=="stage" and (.detail|test("inline")))] | length')
[ "$n" = 4 ] && pass "all four stages are in the audit trail" || fail "expected 4 inline stage records, got $n"
S get --field context_summary_ref | grep -q '^inline: template' && pass "the inline context is kept in the state" || fail "context not stored"
out=$(S triage T9 2>&1 || true)
printf '%s' "$out" | grep -q "risk tier must be one of" && pass "triage rejects an unknown tier" || fail "triage should reject T9" "$out"

echo "== quick: the direct path below T3 in one call"
S init --goal "quick base" --workflow feature --force >/dev/null; S done >/dev/null; S archive >/dev/null
out=$(S quick --goal "rename a label" --workflow feature --tier T1 --files "templates/admin/*.twig,translations/messages.en.yaml" --note "isolated label" 2>&1)
printf '%s' "$out" | grep -q "step 1 armed" && pass "quick records the task and arms step 1" || fail "quick should arm step 1" "$out"
[ "$(S get --field risk_tier)" = T1 ] && pass "quick sets the tier" || fail "quick should set the tier"
[ "$(S get --field current_stage)" = implementation ] && pass "quick lands on implementation" || fail "quick stage wrong"
[ "$(S get --field approved_plan.current_step_id)" = 1 ] && pass "quick arms the scope guard on step 1" || fail "current step should be 1"
S get --field approved_plan.steps | jq -e '.[0].allowed_files | index("translations/messages.en.yaml")' >/dev/null \
  && pass "quick keeps the named files as the step scope" || fail "allowed files missing"
n=$(S get --field history | jq '[.[] | select(.event=="stage" and (.detail|test("inline")))] | length')
[ "$n" = 4 ] && pass "quick still writes the four triage stages to the audit trail" || fail "expected 4 inline stage records, got $n"
out=$(S quick --goal "x" --workflow feature --tier T3 --files a --force 2>&1 || true)
printf '%s' "$out" | grep -q "quick is for T0, T1 and T2" && pass "quick refuses T3 and above" || fail "quick should refuse T3" "$out"
out=$(S quick --goal "x" --workflow feature --tier T1 --files "" --force 2>&1 || true)
printf '%s' "$out" | grep -q "at least one file" && pass "quick refuses an empty scope" || fail "quick should refuse empty --files" "$out"

echo "== remediate: one step for the whole batch of fixes"
out=$(S remediate --files tests/FooTest.php 2>&1 || true)
printf '%s' "$out" | grep -q "still in progress" && pass "remediate refuses while a step is open" || fail "should refuse with an open step" "$out"
S step-done 1 >/dev/null
out=$(S remediate --files "tests/FooTest.php,tests/BarTest.php" --note "3 regressions from the verification run" 2>&1)
printf '%s' "$out" | grep -q "step R1 armed" && pass "remediate arms step R1" || fail "remediate should arm R1" "$out"
[ "$(S get --field approved_plan.current_step_id)" = R1 ] && pass "R1 is the current step" || fail "current step should be R1"
S get --field approved_plan.steps | jq -e '[.[] | select(.step_id=="R1")][0].allowed_files | (index("templates/admin/*.twig") != null) and (index("tests/BarTest.php") != null)' >/dev/null \
  && pass "R1 scope is the union of the finished steps and the named files" || fail "R1 scope wrong"
[ "$(S get --field current_stage)" = implementation ] && pass "remediate returns to implementation" || fail "stage should be implementation"
S step-done R1 >/dev/null
S remediate --note "review findings" >/dev/null
[ "$(S get --field approved_plan.current_step_id)" = R2 ] && pass "a second batch is R2" || fail "second remediation should be R2"
S step-done R2 >/dev/null

echo "== close: done + archive in one call"
ARCHIVED=$(S close | tail -1)
[ -f "$ARCHIVED" ] && pass "close archives the task" || fail "close should archive" "$ARCHIVED"
[ ! -f "$ROOT/.ai/state/current.json" ] && pass "close clears current.json" || fail "close should clear current.json"
jq -e '.current_stage == "done"' "$ARCHIVED" >/dev/null && pass "the archived task is closed" || fail "archived task should be done"

echo "== a corrupt state file is loud, not silently replaced"
printf 'not json at all' > "$ROOT/.ai/state/current.json"
out=$(S get 2>&1 || true)
printf '%s' "$out" | grep -q "unreadable" && pass "a corrupt state file reports the problem" || fail "corrupt state should be loud" "$out"

echo "== no .ai/ at all"
out=$(python3 "$STATE" --root "$TMP" get 2>&1 || true)
printf '%s' "$out" | grep -q "run /ai-init first" && pass "a project without .ai/ says what to do" || fail "should point at /ai-init" "$out"

echo "== the journal: one line per state change (R8, R9)"
ROOT2="$TMP/journal"; mkdir -p "$ROOT2/.ai/state" "$ROOT2/.ai/reports"
# The runtime is pinned per call, never inherited: the suite must behave the
# same inside a Claude Code session and in a bare shell.
J() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT2" "$@"; }
T2=$(J init --goal "journal core" --workflow feature)
JOURNAL="$ROOT2/.ai/reports/$T2/events.jsonl"
[ -f "$JOURNAL" ] && pass "init creates the journal" || fail "init should create events.jsonl" "$JOURNAL"
jq -se '.[0].event=="task_started" and .[0].data.workflow=="feature" and .[0].task=="'"$T2"'"' "$JOURNAL" >/dev/null \
  && pass "the first line is task_started with its typed data" || fail "task_started line wrong" "$(head -1 "$JOURNAL")"
jq -se '.[0].runtime=="unknown" and .[0].actor=="agent" and (.[0].ts|test("\\.[0-9]{3}Z$"))' "$JOURNAL" >/dev/null \
  && pass "a journal line carries runtime, actor and a millisecond timestamp" || fail "line shape wrong" "$(head -1 "$JOURNAL")"

J stage context >/dev/null
J risk T2 --note "small" >/dev/null
J risk T4 --note "payments after all" >/dev/null
cat > "$TMP/steps2.json" <<'JSON'
[ { "step_id": "1", "description": "do it", "allowed_files": ["src/*.php"] } ]
JSON
J plan --ref "plan.md" --steps "$TMP/steps2.json" >/dev/null
J step 1 >/dev/null
J step-done 1 >/dev/null
J set test_status passing >/dev/null
J risks --add "one risk" >/dev/null
J modules billing >/dev/null
J approve --by "the human" >/dev/null
J done >/dev/null

h=$(J get --field history | jq 'length'); e=$(wc -l < "$JOURNAL")
[ "$h" = "$e" ] && pass "the journal has one line per history entry ($h)" || fail "journal/history mismatch" "history $h, journal $e"
J get --field history | jq -e '.[] | select(.event=="risk_classified")' >/dev/null \
  && pass "history keeps its legacy event names" || fail "history should still say risk_classified"
jq -se '[.[] | select(.event=="tier_set")][0] | .data.from==null and .data.tier=="T2" and .data.direction=="set"' "$JOURNAL" >/dev/null \
  && pass "tier_set records the previous tier, which cannot be backfilled" || fail "tier_set data wrong"
jq -se '[.[] | select(.event=="tier_raised")][0] | .data.from=="T2" and .data.to=="T4"' "$JOURNAL" >/dev/null \
  && pass "raising a tier is its own event" || fail "tier_raised missing"
jq -se '[.[] | select(.event=="field_set" and .data.field=="test_status")][0] | .data.from=="not_run" and .data.value=="passing"' "$JOURNAL" >/dev/null \
  && pass "field_set records the value it replaced" || fail "field_set data wrong"
jq -se '[.[] | select(.event=="stage_started")][0] | .data.from=="discovery" and .data.to=="context"' "$JOURNAL" >/dev/null \
  && pass "stage_started records both ends of the move" || fail "stage_started data wrong"
jq -se '[.[] | select(.event=="task_closed")][0].data.abandoned==false' "$JOURNAL" >/dev/null \
  && pass "task_closed says whether the task was abandoned" || fail "task_closed data wrong"

echo "== the invariant holds on the paths that emit more than once"
ROOT5="$TMP/multi"; mkdir -p "$ROOT5/.ai/state" "$ROOT5/.ai/reports"
M() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT5" "$@"; }
T5=$(M --runtime claude quick --goal "small fix" --workflow bugfix --tier T1 --files "src/a.php" | head -1)
JOURNAL5="$ROOT5/.ai/reports/$T5/events.jsonl"
M --runtime claude step-done 1 >/dev/null
M --runtime codex remediate --files "tests/ATest.php" >/dev/null
M --runtime codex step-done R1 >/dev/null
M --runtime codex done >/dev/null
h=$(M get --field history | jq 'length'); e=$(wc -l < "$JOURNAL5")
[ "$h" = "$e" ] && pass "quick, remediate and a runtime handoff keep the journal one-to-one with history ($h)" \
  || fail "journal/history mismatch on the multi-emit paths" "history $h, journal $e"
jq -se '[.[] | select(.event=="stage_started")] | map(.stage) == map(.data.to)' "$JOURNAL5" >/dev/null \
  && pass "a stage_started line names the stage it put the task into" || fail "the stage field lags the move"
jq -se '[.[] | select(.event=="tier_set")][0].stage=="risk_classification"' "$JOURNAL5" >/dev/null \
  && pass "quick records the tier at risk_classification, as triage does" || fail "quick tier_set stage wrong"
# by position, not by timestamp: three events inside one command share a millisecond
jq -se '(to_entries | map(select(.value.event=="runtime_handoff"))[0].key)
        < (to_entries | map(select(.value.event=="step_started" and .value.data.kind=="remediation"))[0].key)' "$JOURNAL5" >/dev/null \
  && pass "the handoff is recorded before the work it covers" || fail "handoff should precede the step"
M archive >/dev/null
M events --last 1 --format jsonl | jq -e '.event=="task_closed"' >/dev/null \
  && pass "the journal is still readable after the task is archived" || fail "events should outlive current.json"

echo "== a journal that cannot be written never fails the command (Risks 1)"
ROOT6="$TMP/nojournal"; mkdir -p "$ROOT6/.ai/state" "$ROOT6/.ai/reports"
N() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT6" "$@"; }
T6=$(N init --goal "journal blocked" --workflow feature)
rm -f "$ROOT6/.ai/reports/$T6/events.jsonl"
mkdir -p "$ROOT6/.ai/reports/$T6/events.jsonl"     # a directory: os.open fails for every user
N stage context >/dev/null 2>&1
[ $? = 0 ] && pass "the command still succeeds" || fail "a blocked journal must not fail the command"
[ "$(N get --field current_stage)" = context ] && pass "and the state change still landed" || fail "the state write is the contract"
rmdir "$ROOT6/.ai/reports/$T6/events.jsonl"

echo "== a state file that is readable but oddly shaped still answers"
printf '{"task_id":"T-odd","current_stage":"plan","human_approval":null,"history":[]}' > "$ROOT6/.ai/state/current.json"
out=$(N get --field current_stage 2>&1)
[ "$out" = plan ] && pass "a null human_approval is replaced, not crashed on" || fail "apply_defaults should be total" "$out"

echo "== the state carries the schema-2 keys (I6)"
for field in owner_runtime resume_point questions handoff; do
  J get --field "$field" >/dev/null 2>&1 && pass "get answers $field" || fail "$field should exist"
done
J get --field human_approval | jq -e 'has("requested_at") and has("via") and .unattended==false' >/dev/null \
  && pass "human_approval gains requested_at, via and unattended" || fail "human_approval v2 keys missing"
printf '{"task_id":"T-v1","current_stage":"implementation","history":[]}' > "$ROOT2/.ai/state/current.json"
[ "$(J get --field questions.file)" = ".ai/reports/T-v1/questions.md" ] \
  && pass "a v1 state answers the v2 keys before the migration has run" || fail "v1 defaults not applied"
rm -f "$ROOT2/.ai/state/current.json"

echo "== notes and hook events go to the journal, not to the state (I3)"
T3=$(J init --goal "notes" --workflow bugfix)
JOURNAL3="$ROOT2/.ai/reports/$T3/events.jsonl"
before=$(J get --field history | jq 'length')
J note decision "keep the legacy gateway" --why "two callers still use it" >/dev/null
J note failed "raising the timeout" --error "still times out at 30s" >/dev/null
J event handoff_written --detail "precompact" --data '{"reason":"precompact","lines":21}' >/dev/null
[ "$(J get --field history | jq 'length')" = "$before" ] && pass "a note does not grow the state" || fail "note should not touch history"
jq -se '[.[] | select(.event=="note")] | length==2 and (.[0].data.why|test("two callers"))' "$JOURNAL3" >/dev/null \
  && pass "notes are recorded with their reason" || fail "note events wrong"
jq -se '[.[] | select(.event=="handoff_written")][0] | .actor=="hook" and .data.lines==21' "$JOURNAL3" >/dev/null \
  && pass "a hook event is recorded as actor hook" || fail "event command wrong"
out=$(J event not_a_type 2>&1 || true)
printf '%s' "$out" | grep -q "unknown event type" && pass "an unknown event type is refused" || fail "should refuse unknown types" "$out"
out=$(J note wrong "x" 2>&1 || true)
printf '%s' "$out" | grep -q "note kind must be one of" && pass "note refuses an unknown kind" || fail "should refuse the kind" "$out"

echo "== events reads the journal back"
[ "$(J events --last 0 --format jsonl | wc -l)" = "$(wc -l < "$JOURNAL3")" ] && pass "--last 0 prints every line" || fail "events should print every line"
out=$(J events --type nosuchtype 2>&1 || true)
printf '%s' "$out" | grep -q "unknown event type" && pass "a mistyped filter is refused, not answered with silence" || fail "--type should be validated" "$out"
[ "$(J events --type note --format jsonl | wc -l)" = 2 ] && pass "events filters by type" || fail "--type should filter"
[ "$(J events --last 1 --format jsonl | wc -l)" = 1 ] && pass "events honours --last" || fail "--last should limit"
J events --task "$T2" --type task_closed | grep -q task_closed && pass "events reads another task's journal" || fail "--task should select the task"
printf 'not json\n' >> "$JOURNAL3"
err=$(J events --last 1 2>&1 >/dev/null)
printf '%s' "$err" | grep -q "skipped 1 unparseable" && pass "an unparseable line is reported, not fatal" || fail "should report the skipped line" "$err"

echo "== done --abandon closes without pretending the work landed"
J done --abandon | grep -q abandoned && pass "done --abandon says so" || fail "done --abandon should say so"
J events --type task_closed --format jsonl 2>/dev/null | tail -1 | jq -e '.data.abandoned==true' >/dev/null \
  && pass "the journal records the abandonment" || fail "task_closed should carry abandoned true"
J get --field next_action | grep -q abandoned && pass "next_action says the task was abandoned" || fail "next_action wrong"

echo "== runtime ownership and handoff (R10)"
ROOT3="$TMP/runtime"; mkdir -p "$ROOT3/.ai/state" "$ROOT3/.ai/reports"
R() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT3" "$@"; }
T4=$(R --runtime claude init --goal "owned by claude" --workflow feature)
JOURNAL4="$ROOT3/.ai/reports/$T4/events.jsonl"
[ "$(R get --field owner_runtime)" = claude ] && pass "the first mutating command takes ownership" || fail "owner_runtime should be claude"
R --runtime claude stage context >/dev/null
[ "$(jq -s '[.[] | select(.event=="runtime_handoff")] | length' "$JOURNAL4")" = 0 ] \
  && pass "the same runtime hands nothing off" || fail "no handoff expected yet"
R --runtime codex stage plan >/dev/null
jq -se '[.[] | select(.event=="runtime_handoff")][0] | .data.from=="claude" and .data.to=="codex" and .data.via=="resume"' "$JOURNAL4" >/dev/null \
  && pass "a mutating command from another runtime hands the task over" || fail "runtime_handoff missing"
[ "$(R get --field owner_runtime)" = codex ] && pass "the new runtime owns the task" || fail "owner_runtime should be codex"
R --help 2>&1 | grep -q -- "--runtime" && pass "--runtime is a global flag" || fail "--runtime should be global"

echo "== runtime detection precedence (I10)"
env -u CLAUDECODE AI_RUNTIME=codex python3 "$STATE" --root "$ROOT3" get --field owner_runtime >/dev/null
[ "$(jq -s '[.[] | select(.event=="runtime_handoff")] | length' "$JOURNAL4")" = 1 ] \
  && pass "a read-only command hands nothing off" || fail "get should not change ownership"
printf '{"runtime":"claude","session_id":"s1"}' > "$ROOT3/.ai/state/session.json"
env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT3" set next_action "from session.json" >/dev/null
[ "$(R get --field owner_runtime)" = claude ] && pass "session.json decides the runtime when nothing else does" || fail "session.json should be read"
rm -f "$ROOT3/.ai/state/session.json"
env -u AI_RUNTIME CLAUDECODE=1 python3 "$STATE" --root "$ROOT3" --runtime codex set next_action "explicit wins" >/dev/null
[ "$(R get --field owner_runtime)" = codex ] && pass "--runtime outranks CLAUDECODE" || fail "--runtime should win"
env -u AI_RUNTIME CLAUDECODE=1 python3 "$STATE" --root "$ROOT3" set next_action "from CLAUDECODE" >/dev/null
[ "$(R get --field owner_runtime)" = claude ] && pass "CLAUDECODE is the last resort before unknown" || fail "CLAUDECODE fallback"

echo "== R8: two appenders lose and interleave nothing"
python3 - "$STATE" "$ROOT3" <<'CONCURRENCY'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("state_under_test", sys.argv[1])
mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
root, task = sys.argv[2], "T-concurrent"
pids = []
for worker in ("a", "b"):
    pid = os.fork()
    if pid == 0:
        for i in range(200):
            mod.append_journal(root, task, mod.journal_line(
                task, "note", "agent", "test", "%s-%03d" % (worker, i),
                {"kind": "decision", "text": "x" * 300}))
        os._exit(0)
    pids.append(pid)
for pid in pids:
    os.waitpid(pid, 0)
CONCURRENCY
CJ="$ROOT3/.ai/reports/T-concurrent/events.jsonl"
n=$(wc -l < "$CJ")
# What this proves is the requirement (R8): nothing is lost and no line is split.
# O_APPEND carries most of that weight on Linux; flock is the belt for the
# platforms and sizes where it does not.
[ "$n" = 400 ] && pass "400 appends from two processes give 400 lines" || fail "lines lost or split" "got $n"
parsed=$(python3 -c 'import json, sys
ok = 0
for line in open(sys.argv[1], encoding="utf-8"):
    try:
        json.loads(line); ok += 1
    except ValueError:
        pass
print(ok)' "$CJ")
[ "$parsed" = 400 ] && pass "every one of them parses" || fail "interleaved writes" "parsed $parsed"

echo "== a journal line stays under the 4 KB cap"
python3 -c 'import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("s", sys.argv[1])
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
cut = json.loads(m.journal_line("T-x", "note", "agent", "plan", "d" * 5000, {"error": "e" * 9000}))
assert len(cut["detail"]) == 500, len(cut["detail"])
assert len(cut["data"]["error"]) == 1000, len(cut["data"]["error"])
huge = m.journal_line("T-x", "note", "agent", "plan", "d", {"text": "x" * 9000})
assert len(huge.encode()) <= 4096, len(huge)
assert json.loads(huge)["data"] == {"truncated": True}, json.loads(huge)["data"]' "$STATE" \
  && pass "detail and error are cut, and a line that still will not fit keeps only its shape" \
  || fail "the 4 KB cap is not enforced"

echo "== questions: ask writes the file, never the model (R1)"
ROOT7="$TMP/questions"; mkdir -p "$ROOT7/.ai/state" "$ROOT7/.ai/reports"
Q() { env -u CLAUDECODE -u AI_RUNTIME -u AI_UNATTENDED python3 "$STATE" --root "$ROOT7" "$@"; }
T7=$(Q init --goal "fee rounding" --workflow feature)
QF="$ROOT7/.ai/reports/$T7/questions.md"
Q stage plan >/dev/null
Q ask "Which rounding rule applies to the per-line fee?" \
  --option "A: Round half up per line" --option "B: Round half even per order total" \
  --recommend A --context "src/Payment/FeeCalculator.php:42" --by "ai-planner via main session" >/dev/null
[ -f "$QF" ] && pass "ask creates .ai/reports/<id>/questions.md" || fail "the questions file should exist" "$QF"
Q questions --format json | jq -e '.[0] | .id=="Q1" and .question=="Which rounding rule applies to the per-line fee?"
  and (.options|map(.key))==["A","B"] and .recommend=="A" and .stage=="plan"
  and (.context|test("FeeCalculator.php:42")) and .pending==true' >/dev/null \
  && pass "the question round-trips through questions --format json" || fail "R1 round trip broken" "$(Q questions --format json)"
grep -q '^X\. Other — answer as' "$QF" && pass "every question offers the free-text option" || fail "the X line is missing"
Q get --field questions.pending | grep -q '"Q1"' && pass "the state caches the pending id" || fail "questions.pending should cache Q1"
Q events --type question_asked --format jsonl | jq -e '.data.id=="Q1" and .data.recommended=="A"' >/dev/null \
  && pass "asking is a journal event" || fail "question_asked missing"

echo "== a hand-edited answer round-trips without touching the question (R2)"
grep -v '^\[Answer\]' "$QF" > "$TMP/q-before.txt"
python3 - "$QF" <<'HANDEDIT'
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().split("\n")
lines[lines.index("[Answer]:")] = "[Answer]: B"
open(path, "w", encoding="utf-8").write("\n".join(lines))
HANDEDIT
Q questions --sync --by ivan >/dev/null
grep -v '^\[Answer\]' "$QF" > "$TMP/q-after.txt"
cmp -s "$TMP/q-before.txt" "$TMP/q-after.txt" && pass "--sync leaves the question block byte-identical" || fail "the question text changed" "$(diff "$TMP/q-before.txt" "$TMP/q-after.txt")"
grep -q '^\[Answer\]: B — by ivan via file at ' "$QF" && pass "--sync writes the trailer onto the answer" || fail "the trailer is missing" "$(grep '^\[Answer\]' "$QF")"
Q events --type question_answered --format jsonl | jq -e '.data.via=="file" and .data.choice=="B" and .actor=="human"' >/dev/null \
  && pass "a hand edit is recorded as answered via the file, by a human" || fail "question_answered{via:file} missing"
grep -c '^\[Answer\]: B — by ivan via file at ' "$QF" | grep -q '^1$' \
  && pass "and the answer landed on the question that was edited" || fail "--sync wrote the answer somewhere else"
cp "$QF" "$TMP/q-synced.md"
Q questions --sync >/dev/null
cmp -s "$TMP/q-synced.md" "$QF" && pass "syncing an already-synced file changes nothing" || fail "--sync is not idempotent"
[ "$(Q events --type question_answered --format jsonl | wc -l)" = 1 ] && pass "and emits nothing the second time" || fail "a second sync should emit nothing"

echo "== an answer that is not an option stays pending"
sed -i 's/^\[Answer\]: B — by ivan.*/[Answer]: F/' "$QF"
err=$(Q questions --sync 2>&1 >/dev/null)
printf '%s' "$err" | grep -q "Q1: invalid choice 'F'" && pass "--sync reports the invalid choice" || fail "should report the invalid choice" "$err"
Q questions --format json | jq -e '.[0].pending==true' >/dev/null && pass "and the question stays pending" || fail "an invalid choice must not answer the question"
Q answer Q1=B --by ivan --via picker >/dev/null
Q questions --format json | jq -e '.[0].pending==false and .[0].choice=="B"' >/dev/null && pass "answer sets the choice" || fail "answer should set the choice"
Q events --type question_answered --format jsonl | tail -1 | jq -e '.actor=="agent" and .data.via=="picker"' >/dev/null \
  && pass "an answer the agent relays is recorded as the agent's, not a human's" || fail "actor must follow the route"
Q answer --help 2>&1 | grep -q -- "--via {picker,prose}" && pass "--via file cannot be claimed by a caller" || fail "--via should not offer file"

echo "== free text and the prose reply"
Q ask --batch /dev/stdin <<'BATCH' >/dev/null
[{"question":"Which gateway?","options":[{"key":"A","text":"Stripe"},{"key":"B","text":"Adyen"}],"recommend":"B"},
 {"question":"Migration window?","options":[{"key":"A","text":"tonight"},{"key":"B","text":"next release"}]}]
BATCH
Q questions --format json | jq -e 'length==3 and .[1].id=="Q2" and .[2].id=="Q3"' >/dev/null \
  && pass "--batch appends with ids taken from the highest in the file" || fail "batch ids wrong"
Q answer --prose "2B 3: after the audit" --by ivan >/dev/null
Q questions --format json | jq -e '.[1].choice=="B" and .[2].choice=="X" and .[2].text=="after the audit"' >/dev/null \
  && pass "a prose reply answers by id number, with free text" || fail "prose parsing wrong" "$(Q questions --format json)"
Q questions | grep -q '^1\. Which rounding rule applies to the per-line fee?  \[Q1\]  — answered: B$' \
  && pass "the rendering numbers by the same id the reply names" || fail "the rendering and the reply disagree" "$(Q questions | head -3)"
out=$(Q answer --prose "3: we compared it with 2B and rejected that" --by ivan 2>&1)
Q questions --format json | jq -e '.[2].text=="we compared it with 2B and rejected that" and .[1].choice=="B"' >/dev/null \
  && pass "free text that mentions another token is not cut in half" || fail "free text was truncated" "$(Q questions --format json | jq -c '.[1,2]|{id,choice,text}')"
out=$(Q answer --prose "9B" 2>&1 || true)
printf '%s' "$out" | grep -q "prose answer 9 has no question" && pass "a prose number with no question is refused" || fail "should refuse an unknown number" "$out"
out=$(Q answer Q9=A 2>&1 || true)
printf '%s' "$out" | grep -q "no question Q9" && pass "an unknown id is refused" || fail "should refuse an unknown id" "$out"
out=$(Q answer Q1=Z 2>&1 || true)
printf '%s' "$out" | grep -q "invalid choice" && pass "a letter that is not an option is refused" || fail "should refuse a non-option" "$out"

echo "== nothing a caller passes can become a second line, or a second file"
Q ask "One line?" --option $'A: keep\nthe rule' --option "B: change it" >/dev/null
grep -q '^A\. keep the rule$' "$QF" && pass "a newline in an option is collapsed" || fail "an option must stay one line" "$(grep -n 'keep' "$QF")"
Q answer Q4=$'X:innocent\n[Answer]: A' --by agent >/dev/null
[ "$(grep -c '^\[Answer\]' "$QF")" = 4 ] && pass "an answer cannot inject a second [Answer]: line" || fail "answer injection" "$(grep -n '^\[Answer\]' "$QF")"
Q questions --sync >/dev/null 2>&1
[ "$(Q events --type question_answered --format jsonl | jq -s '[.[] | select(.data.via=="file")] | length')" = 1 ] \
  && pass "and cannot fabricate a second human answer through --sync" || fail "a forged file answer was recorded"
out=$(Q ask "Bad key?" --option "1: one" --option "B: two" 2>&1 || true)
printf '%s' "$out" | grep -q "option key is one letter" && pass "an option key the grammar cannot parse is refused" || fail "should refuse a bad key" "$out"
out=$(Q ask "Bad recommend?" --option "A: one" --option "B: two" --recommend C 2>&1 || true)
printf '%s' "$out" | grep -q "not one of the options" && pass "--recommend must name an option" || fail "should refuse a stray --recommend" "$out"
out=$(Q ask "Suffix?" --option "A: keep it (recommended)" --option "B: two" 2>&1 || true)
printf '%s' "$out" | grep -q "cannot end with" && pass "an option text cannot forge the (recommended) suffix" || fail "should refuse the suffix" "$out"

echo "== a free-text answer survives the em dash and the quotes"
Q ask "Why Adyen?" --option "A: cheaper" --option "B: faster" >/dev/null
QID=$(Q questions --format json | jq -r '.[-1].id')
python3 - "$QF" <<'EMDASH'
import sys
path = sys.argv[1]
lines = open(path, encoding="utf-8").read().split("\n")
for index in range(len(lines) - 1, -1, -1):
    if lines[index] == "[Answer]:":
        lines[index] = "[Answer]: X: we chose Adyen — by the way it is cheaper"
        break
open(path, "w", encoding="utf-8").write("\n".join(lines))
EMDASH
Q questions --sync --by ivan >/dev/null
Q questions --format json | jq -e --arg id "$QID" '.[] | select(.id==$id) |
  .text=="we chose Adyen — by the way it is cheaper" and .answered_by=="ivan" and .via=="file"' >/dev/null \
  && pass "an em dash in free text does not become the trailer" || fail "the trailer ate the answer" "$(Q questions --format json | jq -c --arg id "$QID" '.[]|select(.id==$id)|{text,answered_by}')"
Q ask "Quoted?" --option "A: one" --option "B: two" >/dev/null
QID=$(Q questions --format json | jq -r '.[-1].id')
Q answer "$QID=X:\"free text\"" --by ivan >/dev/null
Q questions --format json | jq -e --arg id "$QID" '.[] | select(.id==$id) | .text=="free text"' >/dev/null \
  && pass "X:\"free text\" keeps its text and loses its quotes" || fail "the quote pair was mishandled"

echo "== a gate question is not answered with answer"
Q ask "Approve $T7 for implementation?" --option "A: Approve" --option "B: Reject — answer as \`B: <reason>\`" --gate human_approval >/dev/null
grep -q "^## G1\. Approve .* (gate: human_approval)$" "$QF" && pass "a gate question is a G id" || fail "the gate heading is wrong" "$(grep '^## G' "$QF")"
out=$(Q answer G1=A 2>&1 || true)
printf '%s' "$out" | grep -q "G1 is a gate: run 'state.py approve' in your terminal" && pass "answer refuses a gate id with the route to take" || fail "wrong gate message" "$out"

echo "== a pending question blocks a stage, and nothing else (R3)"
TB=$(Q init --goal "one open question" --workflow feature --force)
Q stage plan >/dev/null
Q ask "Which rule?" --option "A: one" --option "B: two" >/dev/null
cp "$ROOT7/.ai/state/current.json" "$TMP/state-before.json"
cp "$ROOT7/.ai/reports/$TB/questions.md" "$TMP/questions-before.md"
blocked_ok=yes
for c in "stage implementation" "triage T2" "plan --ref x --steps /dev/null" "step 1" "step-done 1" \
         "remediate --files a" "approve --by me" "done" "close"; do
  out=$(Q $c 2>&1); rc=$?
  [ "$rc" = 4 ] || { blocked_ok="'$c' exited $rc, not 4: $out"; break; }
  printf '%s' "$out" | grep -q "QUESTIONS_PENDING — 1 unanswered in .ai/reports/$TB/questions.md: Q1\. Answer with 'state.py answer Q1=<letter>'" \
    || { blocked_ok="'$c' printed: $out"; break; }
  cmp -s "$TMP/state-before.json" "$ROOT7/.ai/state/current.json" \
    || { blocked_ok="'$c' changed the state while refusing"; break; }
  cmp -s "$TMP/questions-before.md" "$ROOT7/.ai/reports/$TB/questions.md" \
    || { blocked_ok="'$c' changed the questions file while refusing"; break; }
done
[ "$blocked_ok" = yes ] && pass "each of the nine stage-moving commands exits 4 and leaves the state byte-identical" \
  || fail "R3's blocked list is wrong" "$blocked_ok"
printf '%s' "$(Q stage implementation 2>&1)" | grep -q "Stage stays at plan\." && pass "the refusal names the stage it stays at" || fail "the exit-4 text is wrong"
open_ok=yes
for c in "get" "set next_action x" "risks --add r" "modules billing" "note decision d" \
         "ask q --option A:one --option B:two" "questions" "events"; do
  Q $c >/dev/null 2>&1 || { open_ok="'$c' was blocked"; break; }
done
[ "$open_ok" = yes ] && pass "recording, reading and asking are never blocked" || fail "R3's open list is wrong" "$open_ok"
Q answer Q1=A >/dev/null 2>&1 && pass "answer itself is not blocked" || fail "answer must not be blocked"
Q answer Q2=A >/dev/null 2>&1
Q archive >/dev/null 2>&1 && pass "archive is not blocked either" || fail "archive must not be blocked"

echo "== twelve asks at once all land in the file"
ROOT9="$TMP/concurrent-questions"; mkdir -p "$ROOT9/.ai/state" "$ROOT9/.ai/reports"
C() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT9" "$@"; }
TC=$(C init --goal "many askers" --workflow feature)
for i in $(seq 1 12); do
  C ask "Question $i?" --option "A: one" --option "B: two" >/dev/null 2>&1 &
done
wait
n=$(C questions --format json | jq 'length')
[ "$n" = 12 ] && pass "twelve concurrent asks give twelve questions" || fail "a question was lost" "got $n"
[ "$(C events --type question_asked --format jsonl | wc -l)" = "$n" ] \
  && pass "and the journal names exactly the questions the file holds" || fail "the journal and the file disagree"

echo "== ask and answer take ownership of the task (R10)"
ROOTR="$TMP/questions-runtime"; mkdir -p "$ROOTR/.ai/state" "$ROOTR/.ai/reports"
A() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOTR" "$@"; }
TR=$(A --runtime claude init --goal "owned" --workflow feature)
A --runtime codex ask "Whose task?" --option "A: claude" --option "B: codex" >/dev/null
[ "$(A get --field owner_runtime)" = codex ] && pass "ask hands the task over like any other change" || fail "ask should claim the runtime"
A events --type runtime_handoff --format jsonl | jq -e '.data.to=="codex"' >/dev/null \
  && pass "and says so in the journal" || fail "runtime_handoff missing for ask"

echo "== reading the questions does not change the task"
before=$(A get --field updated_at)
A questions >/dev/null; A questions --pending >/dev/null
[ "$(A get --field updated_at)" = "$before" ] && pass "questions is a read: updated_at does not move" || fail "a read must not write the state"

echo "== done --abandon is the way out of an unanswerable question"
T8=$(Q init --goal "abandon me" --workflow investigation --force)
Q ask "Is this reproducible?" --option "A: yes" --option "B: no" >/dev/null
out=$(Q done 2>&1); [ $? = 4 ] && pass "done is blocked" || fail "done should be blocked" "$out"
Q done --abandon >/dev/null && pass "done --abandon is not" || fail "done --abandon should be exempt"

echo "== ask ends an unattended turn with the line a launcher greps for (R5)"
T9=$(Q init --goal "unattended" --workflow feature --force)
last=$(env -u CLAUDECODE -u AI_RUNTIME AI_UNATTENDED=1 python3 "$STATE" --root "$ROOT7" \
        ask "Ship it?" --option "A: yes" --option "B: no" | tail -1)
case "$last" in
  "WAITING_FOR_ANSWERS .ai/reports/$T9/questions.md Q1") pass "the last line is WAITING_FOR_ANSWERS <file> <ids>";;
  *) fail "R5's literal line is wrong" "$last";;
esac
Q ask "Second?" --option "A: yes" --option "B: no" | tail -1 | grep -q WAITING_FOR_ANSWERS \
  && fail "the line must only appear under AI_UNATTENDED" || pass "and it is absent without the flag"

echo "== topic questions live with the document and need no .ai/ (R17)"
ROOT10="$TMP/topic"; mkdir -p "$ROOT10/docs/sdlc/intent"
P() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT10" "$@"; }
P ask "What problem are we solving?" --option "A: decisions are lost" --option "B: cost" --topic my-idea >/dev/null
[ -f "$ROOT10/docs/sdlc/intent/my-idea.questions.md" ] && pass "a topic question lands beside its intent" || fail "topic file missing"
P answer Q1=A --topic my-idea --by ivan >/dev/null
P questions --topic my-idea --format md | grep -q '^- \*\*What problem are we solving?\*\* — decisions are lost' \
  && pass "--format md renders the Decisions taken line" || fail "md rendering wrong" "$(P questions --topic my-idea --format md)"
[ ! -d "$ROOT10/.ai" ] && pass "and no .ai/ was created" || fail "topic mode must not need .ai/"
[ -z "$(find "$ROOT10" -name 'events.jsonl' -o -name '.ai' 2>/dev/null)" ] \
  && pass "a topic question writes no journal anywhere in the tree" || fail "topic mode wrote a journal"
out=$(P ask "Escape?" --option "A: one" --option "B: two" --topic "../../pwned/evil" 2>&1 || true)
printf '%s' "$out" | grep -q "takes a slug of lowercase letters" && pass "a slug that is a path is refused" || fail "--topic must not steer the path" "$out"
[ ! -e "$ROOT10/../pwned" ] && [ ! -e "$ROOT10/docs/pwned" ] && pass "and nothing was written outside docs/sdlc/intent/" || fail "the traversal wrote a file"
out=$(P ask "Gate?" --option "A: one" --option "B: two" --gate human_approval --topic my-idea 2>&1 || true)
printf '%s' "$out" | grep -q "gate belongs to a task" && pass "a topic file cannot hold a gate" || fail "--gate --topic should be refused" "$out"

summary "state.py"
