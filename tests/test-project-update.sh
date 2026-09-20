#!/usr/bin/env bash
# project-update: a project scaffolded from the oldest shipped templates, then
# edited by hand, is brought up to date without losing an edit.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

UPDATE="$PLUGIN_ROOT/skills/project-update/update.py"
HISTORY="$PLUGIN_ROOT/skills/project-update/history"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== the shipped history covers every current template"
stale=$(python3 - "$PLUGIN_ROOT" "$HISTORY" <<'PY'
import hashlib, json, os, sys
root, hist = sys.argv[1], sys.argv[2]
index = json.load(open(os.path.join(hist, "index.json")))
for name in ("ai-init", "project-init"):
    base = os.path.join(root, "skills", name, "templates")
    for d, _, files in os.walk(base):
        for f in files:
            p = os.path.join(d, f)
            key = "%s/%s" % (name, os.path.relpath(p, base))
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            if h not in index.get(key, []) or not os.path.exists(os.path.join(hist, "blobs", h)):
                print(key)
PY
)
[ -z "$stale" ] && pass "every template version is in history/ (else run tools/build-template-history.py)" \
    || fail "history is stale — run tools/build-template-history.py" "$stale"

echo "== build the oldest shipped templates from history"
OLD="$TMP/old"
python3 - "$HISTORY" "$OLD" <<'PY'
import json, os, sys
hist, out = sys.argv[1], sys.argv[2]
for key, versions in json.load(open(os.path.join(hist, "index.json"))).items():
    if key == "ai-init/.ai/VERSION":
        continue   # a project from before schema 1 has no VERSION: that is schema 0
    name, rel = key.split("/", 1)
    dst = os.path.join(out, name, "templates", rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "wb").write(open(os.path.join(hist, "blobs", versions[0]), "rb").read())
PY
P="$TMP/proj"; mkdir -p "$P"
CLAUDE_ROUTING_TEMPLATES="$OLD/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$P" >/dev/null
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P" >/dev/null
git -C "$P" init -q
jq -e 'has("pipeline_profile") | not' "$P/.ai/policies/risk-tiers.json" >/dev/null \
    && pass "the old project has no pipeline_profile yet" || fail "the fixture should start from old templates"

# Hand edits a real project would have.
printf '\nphpunit: vendor/bin/phpunit\n' >> "$P/.ai/policies/testing.md"
jq '.tiers.T4.examples += ["Fiscal printer bridge"]' "$P/.ai/policies/risk-tiers.json" > "$TMP/rt" && mv "$TMP/rt" "$P/.ai/policies/risk-tiers.json"
sha=$(sha256sum "$P/.ai/policies/risk-tiers.json" | cut -d' ' -f1)
sed -i "1s/sha256:[0-9a-f]*/sha256:$sha/" "$P/.ai/policies/risk-tiers.md"   # the human kept the mirror in sync
row=$(grep -n '^| TEST |' "$P/.ai/workflows/feature.md" | cut -d: -f1)
sed -i "${row}s/.*/| TEST | \`ai-tester\` | my own rule |/" "$P/.ai/workflows/feature.md"
printf 'the overview a human wrote\n' > "$P/.ai/project/overview.md"
printf '\n# my notes\nkeep me\n' >> "$P/CLAUDE.md"
rm "$P/.ai/templates/review-report.md"

echo "== dry run"
before=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
out=$(python3 "$UPDATE" "$P" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "the dry run exits 0" || fail "dry run failed" "$out"
after=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
[ "$before" = "$after" ] && pass "the dry run writes nothing" || fail "the dry run changed files"
printf '%s' "$out" | grep -q 'policy .*+ pipeline_profile$' && pass "policy changes are listed for confirmation" || fail "pipeline_profile should be a listed policy change" "$out"
printf '%s' "$out" | grep -q 'pipeline_profiles\.' && fail "a new subtree should be listed once, at its top" "$out" || pass "a new subtree is listed once"
python3 "$UPDATE" "$P" --check >/dev/null; [ $? -eq 1 ] && pass "--check exits 1 while an update is pending" || fail "--check should exit 1"

echo "== apply"
out=$(python3 "$UPDATE" "$P" --apply 2>&1)
RT="$P/.ai/policies/risk-tiers.json"
[ "$(jq -r .pipeline_profile "$RT")" = solo ] && pass "new policy keys are added" || fail "pipeline_profile missing"
[ "$(jq -c .tiers.T0.stages_required "$RT")" = '["discovery","context","implementation"]' ] \
    && pass "an untouched policy value takes the plugin's new value" || fail "T0 stages not updated"
jq -e '.tiers.T4.examples | index("Fiscal printer bridge")' "$RT" >/dev/null \
    && pass "a project edit to the same JSON is kept" || fail "the project's T4 example was lost"
[ "$(sha256sum "$RT" | cut -d' ' -f1)" = "$(grep -o 'sha256:[0-9a-f]*' "$P/.ai/policies/risk-tiers.md" | cut -d: -f2)" ] \
    && pass "a mirror that was in sync stays in sync with the merged JSON" || fail "risk-tiers.md hash not carried forward"
grep -q '^## Verification' "$P/.ai/policies/testing.md" && grep -q 'phpunit: vendor/bin/phpunit' "$P/.ai/policies/testing.md" \
    && pass "an edited markdown policy is merged: new section and the edit" || fail "testing.md merge wrong"
grep -q 'my own rule' "$P/.ai/workflows/feature.md" && pass "a real conflict leaves the project file alone" || fail "feature.md was overwritten"
cmp -s "$P/.ai/local/plugin-update/.ai/workflows/feature.md" "$PLUGIN_ROOT/skills/ai-init/templates/.ai/workflows/feature.md" \
    && pass "and puts the plugin's version in the local copy" || fail "conflict copy missing"
git -C "$P" check-ignore -q .ai/local/plugin-update/.ai/workflows/feature.md && pass "the conflict copy is git-ignored" || fail "conflict copy should be ignored"
cmp -s "$P/.ai/workflows/bugfix.md" "$PLUGIN_ROOT/skills/ai-init/templates/.ai/workflows/bugfix.md" \
    && pass "an untouched file is replaced" || fail "bugfix.md not updated"
[ "$(cat "$P/.ai/project/overview.md")" = "the overview a human wrote" ] && pass ".ai/project/ is never updated" || fail "the knowledge base was touched"
[ -f "$P/.ai/templates/review-report.md" ] && pass "a missing template is created" || fail "missing file not created"
grep -q 'keep me' "$P/CLAUDE.md" && grep -q 'pipeline_profile' "$P/CLAUDE.md" \
    && pass "the CLAUDE.md block is updated and the rest of the file kept" || fail "CLAUDE.md update wrong"
[ "$(grep -c 'claude-agentic:start' "$P/CLAUDE.md")" = 1 ] && pass "one managed block remains" || fail "block duplicated"
printf '%s' "$out" | grep -q 'verify_command is empty' && pass "an empty verify_command is flagged" || fail "hint missing" "$out"

echo "== idempotent"
snap=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
out=$(python3 "$UPDATE" "$P" --apply 2>&1)
printf '%s' "$out" | grep -q '^0 automatic, 1 conflict' && pass "a second run has nothing automatic left" || fail "second run not clean" "$out"
[ "$snap" = "$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)" ] \
    && pass "a second run changes nothing" || fail "second run changed files"
python3 "$UPDATE" "$P" --check >/dev/null && pass "--check exits 0 once only a hand-merge choice remains" || fail "--check should exit 0"

echo "== a stale mirror stays stale"
P2="$TMP/proj2"; mkdir -p "$P2"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P2" >/dev/null
jq '.tiers.T4.examples += ["x"]' "$P2/.ai/policies/risk-tiers.json" > "$TMP/rt" && mv "$TMP/rt" "$P2/.ai/policies/risk-tiers.json"
python3 "$UPDATE" "$P2" --apply >/dev/null
[ "$(sha256sum "$P2/.ai/policies/risk-tiers.json" | cut -d' ' -f1)" != "$(grep -o 'sha256:[0-9a-f]*' "$P2/.ai/policies/risk-tiers.md" | cut -d: -f2)" ] \
    && pass "a mirror that was already stale is not silently marked in sync" || fail "stale mirror was hidden"

echo "== a Codex project gets its AGENTS.md block and .codex/ layer, and no stray CLAUDE.md"
P4="$TMP/proj4"; mkdir -p "$P4"
CLAUDE_ROUTING_TEMPLATES="$OLD/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$P4" --runtime codex >/dev/null
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P4" --runtime codex >/dev/null
[ -e "$P4/AGENTS.md" ] && [ ! -e "$P4/CLAUDE.md" ] && pass "the fixture is a Codex-only project" || fail "fixture should be Codex-only"
printf '\n# my codex notes\nkeep me\n' >> "$P4/AGENTS.md"
rm "$P4/.codex/memory/README.md"
out=$(python3 "$UPDATE" "$P4" --apply 2>&1)
grep -q 'keep me' "$P4/AGENTS.md" && grep -q 'claude-agentic:start' "$P4/AGENTS.md" \
    && pass "the AGENTS.md block is managed and the rest of the file kept" || fail "AGENTS.md update wrong" "$out"
[ "$(grep -c 'claude-agentic:start' "$P4/AGENTS.md")" = 1 ] && pass "one AGENTS.md block remains" || fail "AGENTS.md block duplicated"
[ ! -e "$P4/CLAUDE.md" ] && [ ! -d "$P4/.claude" ] && pass "no Claude layer is added to a Codex project" || fail "a stray Claude layer was created"
[ -f "$P4/.codex/memory/README.md" ] && pass "a missing .codex/memory/README.md is recreated" || fail ".codex/memory/README.md not created"
[ -f "$P4/.codex/config.toml" ] && pass ".codex/config.toml is left in place" || fail ".codex/config.toml missing"
grep -q '.codex/memory/local/' "$P4/.gitignore" && pass "the Codex ignore entry is appended" || fail ".gitignore lacks the codex entry"
python3 "$UPDATE" "$P4" --apply >/dev/null 2>&1
python3 "$UPDATE" "$P4" | grep -q '^0 automatic, 0 conflict' && pass "a second run on the Codex project is a no-op" || fail "codex project not idempotent" "$(python3 "$UPDATE" "$P4")"

echo "== a dual-runtime project keeps both instruction files in step"
P5="$TMP/proj5"; mkdir -p "$P5"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P5" --runtime both >/dev/null
python3 "$UPDATE" "$P5" --apply >/dev/null 2>&1
grep -q 'pipeline_profile' "$P5/CLAUDE.md" && grep -q 'claude-agentic:start' "$P5/AGENTS.md" \
    && pass "both blocks are brought up to date over the one .ai/ tree" || fail "dual-runtime blocks not updated"

echo "== an up-to-date project and a non-project"
P3="$TMP/proj3"; mkdir -p "$P3"
CLAUDE_ROUTING_TEMPLATES="$PLUGIN_ROOT/skills/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$P3" >/dev/null
CLAUDE_AGENTIC_TEMPLATES="$PLUGIN_ROOT/skills/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P3" >/dev/null
python3 "$UPDATE" "$P3" | grep -q '^0 automatic, 0 conflict' && pass "a freshly scaffolded project is up to date" || fail "fresh project should need nothing"
mkdir -p "$TMP/empty"
python3 "$UPDATE" "$TMP/empty" >/dev/null 2>&1; [ $? -eq 2 ] && pass "a repository without .ai/ or docs/sdlc/ is refused" || fail "should exit 2"

# ---------------------------------------------------------------- the schema
FIX="$PLUGIN_ROOT/tests/fixtures/project-update"
SYNTH="$FIX/migrations-synthetic"
STATE="$PLUGIN_ROOT/skills/ai-task/state.py"
CURRENT=$(python3 -c "import sys; sys.path.insert(0, '$PLUGIN_ROOT/skills/project-update'); import migrations; print(migrations.CURRENT)")

# A project as it was before .ai/VERSION existed: oldest templates, no VERSION,
# the knowledge base a human wrote, and a task in flight.
v0_project() {
    local d="$1" rt="${2:-auto}"; mkdir -p "$d"
    CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$d" --runtime "$rt" >/dev/null
    cp -r "$FIX/schema-v0/.ai" "$d/"
}

echo "== a project carries a schema version"
S0="$TMP/schema0"; v0_project "$S0"
[ ! -e "$S0/.ai/VERSION" ] && pass "a project from before the schema has no .ai/VERSION" || fail "the v0 fixture should have no VERSION"
python3 "$UPDATE" "$S0" | grep -q "^  schema    0 -> $CURRENT" && pass "the dry run says which schema step is pending" || fail "no schema line" "$(python3 "$UPDATE" "$S0")"
out=$(python3 "$UPDATE" "$S0" --check); [ $? -eq 1 ] && printf '%s' "$out" | grep -q "schema 0 -> $CURRENT" \
    && pass "--check exits 1 and names the schema step" || fail "--check should name the schema" "$out"
before=$(cd "$S0" && find . -type f | sort | xargs md5sum | md5sum)
python3 "$UPDATE" "$S0" >/dev/null
[ "$before" = "$(cd "$S0" && find . -type f | sort | xargs md5sum | md5sum)" ] \
    && pass "the migration dry run writes nothing" || fail "the dry run changed files"
python3 "$UPDATE" "$S0" --apply >/dev/null
[ "$(cat "$S0/.ai/VERSION")" = "$CURRENT" ] && pass "the apply records the schema version" || fail "VERSION not written"
python3 "$UPDATE" "$S0" | grep -q '^0 automatic' && pass "a second run has nothing left to migrate" || fail "not idempotent" "$(python3 "$UPDATE" "$S0")"
python3 "$UPDATE" "$S0" --check >/dev/null && pass "--check exits 0 once the schema is current" || fail "--check should exit 0"

echo "== a task in flight survives the journey to schema 2 (R14)"
S7="$TMP/schema1"; mkdir -p "$S7"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$S7" >/dev/null
cp -r "$FIX/schema-v1/.ai" "$S7/"
# The task is made by the tool, not by the fixture: a hand-written state would
# have to be kept in step with a shape this migration exists to change.
T7=$(env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$S7" quick \
       --goal "add the per-line fee" --workflow feature --tier T2 --files "src/Fee.php" | head -1)
python3 - "$S7/.ai/state/current.json" <<'TOV1'
import json, sys
# Back to what schema 1 actually held: state.py applies the v2 keys in memory,
# so the file it wrote already has them.
path = sys.argv[1]
state = json.load(open(path, encoding="utf-8"))
for key in ("owner_runtime", "resume_point", "questions", "handoff"):
    state.pop(key, None)
state["human_approval"] = {k: v for k, v in state["human_approval"].items()
                           if k in ("required", "granted", "granted_by", "granted_at")}
json.dump(state, open(path, "w", encoding="utf-8"), indent=2)
TOV1
rm -rf "$S7/.ai/reports/$T7/events.jsonl" "$S7/.ai/state/handoff.md"
printf '1\n' > "$S7/.ai/VERSION"

[ "$(env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field current_stage)" = implementation ] \
    && pass "the v1 task answers state.py before the migration" || fail "a v1 state should work as it is"
HIST=$(env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field history | jq 'length')
python3 "$UPDATE" "$S7" | grep -q "^  schema    1 -> $CURRENT" && pass "the dry run names the schema step" || fail "no schema line" "$(python3 "$UPDATE" "$S7")"
[ ! -e "$S7/.ai/reports/$T7/events.jsonl" ] && pass "and writes no journal yet" || fail "the dry run must write nothing"
python3 "$UPDATE" "$S7" --apply >/dev/null
[ "$(cat "$S7/.ai/VERSION")" = "$CURRENT" ] && pass "the apply reaches the current schema" || fail "VERSION not written"
[ "$(env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field current_stage)" = implementation ] \
    && pass "and the task still answers afterwards" || fail "a task in flight must survive the migration"
env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field questions.file | grep -q "$T7" \
    && pass "with the schema-2 keys now on disk" || fail "the defaults should be persisted" \
    "$(env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field questions)"
env -u CLAUDECODE python3 "$STATE" --root "$S7" get --field human_approval \
    | jq -e 'has("requested_at") and has("gate_id") and has("unattended")' >/dev/null \
    && pass "including the gate's own" || fail "human_approval should gain its v2 keys"

J="$S7/.ai/reports/$T7/events.jsonl"
[ -f "$J" ] && pass "the journal is backfilled" || fail "events.jsonl should exist"
# The migration adds one schema_migrated entry to history as it patches the state.
[ "$(wc -l < "$J")" = "$(( HIST + 1 ))" ] && pass "one line per history entry ($(wc -l < "$J"))" \
    || fail "the backfill should match history" "history $((HIST + 1)), journal $(wc -l < "$J")"
jq -se 'all(.data.backfilled == true) and all(.data.legacy_event != null)' "$J" >/dev/null \
    && pass "every line says it was reconstructed, and from what" || fail "backfilled lines must be marked"
jq -se 'all(.actor == "migration" and .runtime == "unknown")' "$J" >/dev/null \
    && pass "and that a migration wrote it, from no runtime" || fail "actor/runtime wrong"
jq -se '[.[] | select(.event=="stage_started")][0] | .data.to=="discovery"' "$J" >/dev/null \
    && pass "a stage line keeps both ends of the move" || fail "stage_started data wrong" "$(head -2 "$J")"
jq -se '[.[] | select(.event=="tier_set")][0] | .data.tier=="T2" and .data.from==null' "$J" >/dev/null \
    && pass "a tier line records what it can, and leaves what it cannot as null" || fail "tier_set wrong"
env -u CLAUDECODE python3 "$STATE" --root "$S7" events --last 3 | grep -q . \
    && pass "and state.py events reads it back" || fail "the backfilled journal should be readable"

python3 "$UPDATE" "$S7" | grep -q '^0 automatic' && pass "a second run has nothing to do" || fail "not idempotent" "$(python3 "$UPDATE" "$S7")"
before=$(md5sum "$J" | cut -d' ' -f1)
python3 "$UPDATE" "$S7" --apply >/dev/null
[ "$(md5sum "$J" | cut -d' ' -f1)" = "$before" ] && pass "and never appends to the journal twice" || fail "the backfill must be written once"
env -u CLAUDECODE python3 "$STATE" --root "$S7" stage test >/dev/null \
    && pass "the migrated task carries on where it left off" || fail "the task should keep working"

echo "== the migration says nothing about which runtime a project uses"
grep -in 'claude\|codex' "$PLUGIN_ROOT/skills/project-update/migrations/0002_task_journal.py" \
    && fail "0002 must not name a runtime" || pass "0002 names no runtime"

echo "== a docs/sdlc-only project has no schema and runs no migration"
S6="$TMP/sdlconly"; mkdir -p "$S6"
CLAUDE_ROUTING_TEMPLATES="$OLD/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$S6" >/dev/null
out=$(python3 "$UPDATE" "$S6")
printf '%s' "$out" | grep -qE 'schema|VERSION' && fail "a project without .ai/ should see no schema" "$out" || pass "no schema for a docs/sdlc-only project"
out=$(CLAUDE_AGENTIC_MIGRATIONS="$FIX/migrations-broken" python3 "$UPDATE" "$S6" 2>&1); [ $? -eq 0 ] \
    && pass "and a broken registry cannot break it" || fail "a schema-less project must not care about migrations" "$out"

echo "== an unusable .ai/VERSION stops the run, with a reason, having written nothing"
S1="$TMP/schemabad"; v0_project "$S1"
for bad in "$((CURRENT + 1))" "abc" ""; do
    printf '%s\n' "$bad" > "$S1/.ai/VERSION"
    snap=$(cd "$S1" && find . -type f | sort | xargs md5sum | md5sum)
    out=$(python3 "$UPDATE" "$S1" --apply 2>&1); rc=$?
    chk=$(python3 "$UPDATE" "$S1" --check 2>/dev/null); crc=$?
    [ $rc -eq 2 ] && [ $crc -eq 2 ] && [ -n "$chk" ] && [ "$snap" = "$(cd "$S1" && find . -type f | sort | xargs md5sum | md5sum)" ] \
        && pass "VERSION '$bad' exits 2 and --check says why" || fail "VERSION '$bad' should exit 2 with a reason" "$out / $chk"
done
rm -rf "$S1"

echo "== the migration registry is ordered, and a broken one is refused"
S2="$TMP/schemabroken"; v0_project "$S2"
out=$(CLAUDE_AGENTIC_MIGRATIONS="$FIX/migrations-broken" python3 "$UPDATE" "$S2" 2>&1); rc=$?
[ $rc -eq 2 ] && printf '%s' "$out" | grep -q '0002' && pass "a gap in the migrations exits 2 and names it" || fail "a gap should exit 2" "$out"
python3 - "$PLUGIN_ROOT" <<'PY'
import os, sys
sys.path.insert(0, os.path.join(sys.argv[1], "skills", "project-update"))
import migrations                                        # noqa: E402
mods = migrations.load()
assert [m.VERSION for m in mods] == list(range(1, len(mods) + 1)), "not contiguous from 0001"
migrations.renames()                                     # the key graph must be acyclic
PY
[ $? -eq 0 ] && pass "the shipped migrations are contiguous and their renames acyclic" || fail "the shipped registry is invalid"

# The plugin the synthetic migrations belong to: the template moves with the file
# (R12 forbids shipping a template at a path a migration moved away) and gains a
# line, so the merge at the new path has something to merge.
NEXT="$TMP/next-templates"; cp -r "$PLUGIN_ROOT/skills/ai-init/templates" "$NEXT"
mv "$NEXT/.ai/workflows/bugfix.md" "$NEXT/.ai/workflows/fix.md"
sed -i '2i A line the next plugin version inserted near the top.' "$NEXT/.ai/workflows/fix.md"

echo "== a migration that breaks the rules is refused before anything is written"
S5="$TMP/schemarules"; v0_project "$S5"
snap=$(cd "$S5" && find . -type f | sort | xargs md5sum | md5sum)
check_refused() {  # <fixture dir> <text the message must contain> <what the rule is>
    local out rc
    out=$(CLAUDE_AGENTIC_MIGRATIONS="$FIX/$1" python3 "$UPDATE" "$S5" --apply 2>&1); rc=$?
    [ $rc -eq 2 ] && printf '%s' "$out" | grep -q "$2" \
        && [ "$snap" = "$(cd "$S5" && find . -type f | sort | xargs md5sum | md5sum)" ] \
        && pass "$3" || fail "$3" "rc=$rc $out"
}
check_refused migrations-invalid      '0001_mismatch.py: VERSION is 2'      "a VERSION that disagrees with the file name is refused"
# The registry must reject these itself, before any migration runs: the message
# starts with the file name. A downstream refusal would not protect a project
# whose files the MOVES pair names.
check_refused migrations-badmoves     '0001_badpath.py: MOVES path'         "a MOVES pair leaving the project is refused by the registry"
check_refused migrations-dupmove      '0002_second.py: MOVES destination'   "two moves onto one destination are refused by the registry"
check_refused migrations-undeclared   'is not in MOVES'                     "a move the module did not declare is refused"
check_refused migrations-escape       'not a normalised project'      "an operation on a path outside the project is refused"
check_refused migrations-bad-content  'must be bytes'                 "content that is not bytes is refused"
[ ! -e "$TMP/outside-the-project.md" ] && pass "and nothing was written outside the project" || fail "a migration escaped the project root"

echo "== migrations run before the merge, and every operation is listed once"
S3="$TMP/schemaops"; v0_project "$S3"
printf '\n## My own rule\nalways reproduce the bug first\n' >> "$S3/.ai/workflows/bugfix.md"
python3 "$STATE" --root "$S3" quick --goal "a task in flight" --workflow feature --tier T2 --files .ai/workflows/bugfix.md >/dev/null
export CLAUDE_AGENTIC_MIGRATIONS="$SYNTH" CLAUDE_AGENTIC_TEMPLATES="$NEXT"
out=$(python3 "$UPDATE" "$S3")
printf '%s' "$out" | grep -q '^  schema    0 -> 3 ' && pass "the schema line counts every pending migration" || fail "schema line wrong" "$out"
[ "$(printf '%s' "$out" | grep -c '^  move      .ai/workflows/bugfix.md -> .ai/workflows/fix.md  \[0002\]')" = 1 ] \
    && pass "a move is listed once, with its source and its migration" || fail "move line wrong" "$out"
printf '%s' "$out" | grep -q 'still-not-there' && fail "a move of a file the project never had should be skipped" "$out" \
    || pass "a move whose source is absent is skipped"
printf '%s' "$out" | grep -q '^  merge     .ai/workflows/fix.md .*your edits kept' \
    && pass "the template history follows the move: the file merges at its new path" \
    || fail "a file edited at the old path must merge at the new one, not conflict" "$out"
printf '%s' "$out" | grep -q '^  delete?   .ai/legacy-notes.md .*needs --apply --confirm-delete NAME' \
    && pass "a deletion is proposed, not performed" || fail "delete? line wrong" "$out"
printf '%s' "$out" | grep -q 'policy .*~ schema_probe\|policy .*+ schema_probe' \
    && pass "a migration's policy edit is listed for confirmation" || fail "no policy line for the migrated policy" "$out"
printf '%s' "$out" | grep -q 'deletion(s) awaiting --confirm-delete' && pass "the summary counts what is waiting for a human" || fail "no deletion count" "$out"
printf '%s' "$out" | grep -q 'a task is in flight while the schema changes' && pass "a task in flight is flagged" || fail "no in-flight hint" "$out"
first=$(printf '%s' "$out" | grep -n '^  \(create\|move\|update\|delete?\)' | head -1)
printf '%s' "$first" | grep -q '\[000' && pass "the migrations are planned before the template merge" || fail "a migration item must come first" "$out"

echo "== the apply keeps the edit at the new path, the original, and the task"
python3 "$UPDATE" "$S3" --apply >/dev/null
grep -q 'always reproduce the bug first' "$S3/.ai/workflows/fix.md" && pass "an edit made at the old path survives the move" || fail "the edit was lost"
grep -q 'A line the next plugin version inserted near the top' "$S3/.ai/workflows/fix.md" \
    && pass "and the new template's change arrives with it" || fail "the merge lost the plugin's change"
[ ! -e "$S3/.ai/workflows/bugfix.md" ] && pass "and the old path is gone" || fail "the move left its source behind"
[ -f "$S3"/.ai/reports/project-update-*/original/.ai/workflows/bugfix.md ] && pass "the original is kept under .ai/reports/" || fail "no original kept"
[ "$(cat "$S3/.ai/project/schema-note.md")" = "added by migration 0001" ] && pass "create adds a file once" || fail "create wrong"
[ "$(jq -r .schema_probe "$S3/.ai/policies/risk-tiers.json")" = "0003" ] && pass "a policy edit is applied" || fail "policy edit missing"
grep -q 'added by migration 0003' "$S3/.ai/policies/testing.md" && pass "a text edit is applied" || fail "text edit missing"
python3 "$UPDATE" "$S3" --apply >/dev/null   # plan() runs again while the schema is held
[ "$(grep -c 'added by migration 0003' "$S3/.ai/policies/testing.md")" = 1 ] \
    && pass "an idempotent edit does not apply twice when the run repeats" || fail "the migration duplicated its edit"
[ -f "$S3/.ai/legacy-notes.md" ] && pass "the proposed deletion did not happen" || fail "a file was deleted without confirmation"
[ ! -e "$S3/.ai/VERSION" ] && pass "and the schema is held until the deletion is settled" || fail "VERSION written with a deletion pending"
out=$(python3 "$UPDATE" "$S3" --check); [ $? -eq 1 ] && printf '%s' "$out" | grep -q 'the schema stays at 0' \
    && pass "--check reports a held schema instead of calling the project current" || fail "--check must not hide a held schema" "$out"
[ "$(jq -r '.approved_plan.steps[0].allowed_files[0]' "$S3/.ai/state/current.json")" = ".ai/workflows/fix.md" ] \
    && pass "the task in flight follows the migration" || fail "the task's allowed_files were not migrated"
[ "$(jq -r '.history[-1].event' "$S3/.ai/state/current.json")" = "schema_migrated" ] && pass "and the state records why" || fail "no schema_migrated entry"
[ "$(python3 "$STATE" --root "$S3" get --field current_stage)" = "implementation" ] && pass "state.py still reads the migrated state" || fail "the task state is no longer parseable"
[ "$(cat "$S3/.ai/project/overview.md" | head -1)" = "# Overview" ] && pass ".ai/project/ is left alone by a migration run" || fail "the knowledge base was touched"

echo "== a human confirms the deletion, and only then is it performed"
python3 "$UPDATE" "$S3" --confirm-delete tester >/dev/null 2>&1; [ $? -eq 2 ] && pass "--confirm-delete without --apply is refused" || fail "should be an argparse error"
python3 "$UPDATE" "$S3" --apply --confirm-delete "" >/dev/null 2>&1; [ $? -eq 2 ] && pass "an empty confirmation name is refused" || fail "empty --confirm-delete should be refused"
python3 "$UPDATE" "$S3" --apply --confirm-delete tester >/dev/null
[ ! -e "$S3/.ai/legacy-notes.md" ] && pass "the confirmed deletion is performed" || fail "the file should be gone"
[ -f "$S3"/.ai/reports/project-update-*/original/.ai/legacy-notes.md ] && pass "its original is kept too" || fail "no original for the deletion"
rec=$(cat "$S3"/.ai/reports/project-update-*/migration.json)
[ "$(printf '%s' "$rec" | jq -r '.deletions[0].confirmed_by')" = tester ] && pass "migration.json records who confirmed it" || fail "no confirmed_by" "$rec"
[ "$(printf '%s' "$rec" | jq -r '.to')" = "$(cat "$S3/.ai/VERSION")" ] && pass "and the version the project actually reached" || fail "migration.json disagrees with .ai/VERSION" "$rec"
python3 "$UPDATE" "$S3" | grep -q '^0 automatic' && pass "a second run after the migrations is a no-op" || fail "not idempotent" "$(python3 "$UPDATE" "$S3")"
unset CLAUDE_AGENTIC_MIGRATIONS CLAUDE_AGENTIC_TEMPLATES

echo "== a target that is not a regular file aborts the apply"
S4="$TMP/schemalink"; v0_project "$S4"
rm "$S4/.ai/policies/testing.md"; ln -s "$TMP/elsewhere" "$S4/.ai/policies/testing.md"
out=$(python3 "$UPDATE" "$S4" --apply 2>&1); rc=$?
[ $rc -eq 3 ] && [ ! -e "$TMP/elsewhere" ] && pass "a symlinked target exits 3 and is not written through" || fail "a symlink must not be followed" "$out"
printf '%s' "$out" | grep -q 'nothing after it was written; run the dry run again' && pass "and the abort says what to do" || fail "abort message wrong" "$out"

echo "== both runtimes reach the same schema"
for rt in claude codex both; do
    d="$TMP/schema-$rt"; v0_project "$d" "$rt"
    python3 "$UPDATE" "$d" --apply >/dev/null
    [ "$(cat "$d/.ai/VERSION")" = "$CURRENT" ] || fail "a $rt project did not reach schema $CURRENT"
done
pass "Claude-only, Codex-only and dual-runtime projects all reach schema $CURRENT"
grep -lE 'claude|codex' "$PLUGIN_ROOT/skills/project-update/migrations/"[0-9]*.py >/dev/null 2>&1 \
    && fail "a migration must not branch on the runtime" || pass "no migration branches on the runtime"

echo "== every key in the template history is accounted for"
python3 - "$PLUGIN_ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import migrations                                        # noqa: E402
index = json.load(open(os.path.join(root, "skills/project-update/history/index.json")))
current, sources = set(), set()
for name in ("ai-init", "project-init"):
    base = os.path.join(root, "skills", name, "templates")
    for d, _, files in os.walk(base):
        for f in files:
            current.add("%s/%s" % (name, os.path.relpath(os.path.join(d, f), base)))
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import update                                            # noqa: E402  # for the same key map production uses
mapped = update.template_targets()
for mod in migrations.load():
    for src, dst in mod.MOVES:
        key = migrations.template_key(src, mapped)
        if key:
            sources.add(key)
migrations.renames(mapped)   # production's key graph must be acyclic, not a smaller one
# A RETIRED successor joins the rename chain: that is how a template renamed on
# disk, which no MOVES pair can describe, keeps the versions it shipped under.
shipped = migrations.RETIRED
migrations.RETIRED = dict(shipped, **{"project-init/gone.md": "project-init/sdlc-README.md"})
chain = migrations.renames(mapped).get("project-init/sdlc-README.md", [])
migrations.RETIRED = shipped
assert "project-init/gone.md" in chain, "RETIRED successors must join the rename chain"
orphans = sorted(set(index) - current - sources - set(migrations.RETIRED))
reused = sorted(current & sources)
if orphans:
    print("orphaned history keys (add the move to MOVES, or the key to RETIRED): %s" % ", ".join(orphans))
if reused:
    print("a template is shipped at a path a migration moved away: %s" % ", ".join(reused))
sys.exit(1 if orphans or reused else 0)
PY
[ $? -eq 0 ] && pass "no history key is orphaned, and no moved-away path is shipped again" || fail "the history index and the migrations disagree"

summary "project-update"
