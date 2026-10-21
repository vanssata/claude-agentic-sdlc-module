#!/usr/bin/env bash
# project-update: a project scaffolded from the oldest shipped templates, then
# edited by hand, is brought up to date without losing an edit.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

UPDATE="$PLUGIN_ROOT/skills/project-update/update.py"
HISTORY="$PLUGIN_ROOT/skills/project-update/history"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
# pty <cmd...>: the command with a terminal on stdin (util-linux script), stdout
# and stderr merged, \r stripped; exit status is the command's. The checkout path
# has a space, hence %q; SHELL is pinned because script -c runs it.
pty() { SHELL=/bin/bash script -qec "$(printf '%q ' "$@")" /dev/null </dev/null | tr -d '\r'; return "${PIPESTATUS[0]}"; }
# NOMARK: env arguments that clear every agent-session marker and AI_UNATTENDED.
NOMARK=(-u CLAUDECODE -u CODEX_THREAD_ID -u CODEX_SESSION_ID -u CODEX_CI -u CODEX_SANDBOX -u CODEX_SANDBOX_NETWORK_DISABLED -u CODEX_VERSION -u AI_UNATTENDED)
HAS_PTY=0; [ "$(pty python3 -c 'import os; print(os.isatty(0))' 2>/dev/null)" = True ] && HAS_PTY=1

echo "== the shipped history covers every current template"
stale=$(python3 - "$PLUGIN_ROOT" "$HISTORY" <<'PY'
import hashlib, json, os, sys
root, hist = sys.argv[1], sys.argv[2]
index = json.load(open(os.path.join(hist, "index.json")))
# The shared tree ai/ is recorded under the ai-init/.ai/ keys it shipped under,
# by hash only: a shared copy is classified, never merged, so it needs no blob.
shared = set()
for name, base in (("ai-init", os.path.join(root, "skills", "ai-init", "templates")),
                   ("project-init", os.path.join(root, "skills", "project-init", "templates")),
                   ("ai-init/.ai", os.path.join(root, "ai"))):
    for d, _, files in os.walk(base):
        for f in files:
            p = os.path.join(d, f)
            key = "%s/%s" % (name, os.path.relpath(p, base))
            if name == "ai-init/.ai":
                shared.add(key)
            h = hashlib.sha256(open(p, "rb").read()).hexdigest()
            if h not in index.get(key, []) or (name != "ai-init/.ai" and not os.path.exists(os.path.join(hist, "blobs", h))):
                print(key)
owned = {h for k, v in index.items() if k not in shared for h in v}
for b in sorted(set(os.listdir(os.path.join(hist, "blobs"))) - owned):
    print("blob only a shared key references: " + b)
PY
)
[ -z "$stale" ] && pass "every template version is in history/ (else run tools/build-template-history.py)" \
    || fail "history is stale — run tools/build-template-history.py" "$stale"

echo "== build the oldest shipped templates from history"
OLD="$TMP/old"
# The shared keys come from the ai/ tree itself, not from a list: those files are
# no longer scaffolded, and test-migration-0006.sh covers a project carrying them.
SHARED_KEYS=$(cd "$PLUGIN_ROOT/ai" && find . -type f | sed 's|^\./|ai-init/.ai/|' | sort)
[ "$(printf '%s\n' "$SHARED_KEYS" | wc -l)" -ge 29 ] && pass "the shared keys are read from ai/" || fail "ai/ yields too few shared keys" "$SHARED_KEYS"
python3 - "$HISTORY" "$OLD" "$SHARED_KEYS" <<'PY'
import json, os, sys
hist, out, shared = sys.argv[1], sys.argv[2], set(sys.argv[3].split())
for key, versions in json.load(open(os.path.join(hist, "index.json"))).items():
    if key == "ai-init/.ai/VERSION":
        continue   # a project from before schema 1 has no VERSION: that is schema 0
    if key in shared:
        continue   # read from the plugin since 0006, never scaffolded
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
# T0.examples is the one tier key identical in the oldest template and the current one, so this edit merges cleanly instead of conflicting.
jq '.tiers.T0.examples += ["Fiscal printer bridge"]' "$P/.ai/policies/risk-tiers.json" > "$TMP/rt" && mv "$TMP/rt" "$P/.ai/policies/risk-tiers.json"
sha=$(sha256sum "$P/.ai/policies/risk-tiers.json" | cut -d' ' -f1)
sed -i "1s/sha256:[0-9a-f]*/sha256:$sha/" "$P/.ai/policies/risk-tiers.md"   # the human kept the mirror in sync
# Line 4 differs between the oldest state README and the current one, so this edit conflicts.
sed -i "4s/.*/my own wording of who writes current.json/" "$P/.ai/state/README.md"
printf 'the overview a human wrote\n' > "$P/.ai/project/overview.md"
printf '\n# my notes\nkeep me\n' >> "$P/CLAUDE.md"
rm "$P/.ai/policies/security.md"

echo "== dry run"
before=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
out=$(python3 "$UPDATE" "$P" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "the dry run exits 0" || fail "dry run failed" "$out"
after=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
[ "$before" = "$after" ] && pass "the dry run writes nothing" || fail "the dry run changed files"
grep -q 'policy .*+ pipeline_profile$' <<<"$out" && pass "policy changes are listed for confirmation" || fail "pipeline_profile should be a listed policy change" "$out"
grep -q 'pipeline_profiles\.' <<<"$out" && fail "a new subtree should be listed once, at its top" "$out" || pass "a new subtree is listed once"
out=$(python3 "$UPDATE" "$P" --check); [ $? -eq 1 ] && pass "--check exits 1 while an update is pending" || fail "--check should exit 1"
# The exact shape /ai-status reads: one line, the reasons, the command (R21 keeps it byte-identical).
[ "$(printf '%s\n' "$out" | wc -l)" -eq 1 ] && grep -qE '^project is behind the installed plugin: schema 0 -> [0-9]+, [0-9]+ file\(s\) to update, 1 need a manual merge — run /project-update$' <<<"$out" \
    && pass "the plain --check line keeps its exact shape" || fail "the plain --check line changed" "$out"

echo "== apply"
out=$(python3 "$UPDATE" "$P" --apply 2>&1)
RT="$P/.ai/policies/risk-tiers.json"
[ "$(jq -r .pipeline_profile "$RT")" = solo ] && pass "new policy keys are added" || fail "pipeline_profile missing"
[ "$(jq -c .tiers.T0.stages_required "$RT")" = '["discovery","context","implementation"]' ] \
    && pass "an untouched policy value takes the plugin's new value" || fail "T0 stages not updated"
jq -e '.tiers.T0.examples | index("Fiscal printer bridge")' "$RT" >/dev/null \
    && pass "a project edit to the same JSON is kept" || fail "the project's T0 example was lost"
[ "$(sha256sum "$RT" | cut -d' ' -f1)" = "$(grep -o 'sha256:[0-9a-f]*' "$P/.ai/policies/risk-tiers.md" | cut -d: -f2)" ] \
    && pass "a mirror that was in sync stays in sync with the merged JSON" || fail "risk-tiers.md hash not carried forward"
grep -q '^## Verification' "$P/.ai/policies/testing.md" && grep -q 'phpunit: vendor/bin/phpunit' "$P/.ai/policies/testing.md" \
    && pass "an edited markdown policy is merged: new section and the edit" || fail "testing.md merge wrong"
grep -q 'my own wording' "$P/.ai/state/README.md" && pass "a real conflict leaves the project file alone" || fail "state/README.md was overwritten"
cmp -s "$P/.ai/local/plugin-update/.ai/state/README.md" "$PLUGIN_ROOT/skills/ai-init/templates/.ai/state/README.md" \
    && pass "and puts the plugin's version in the local copy" || fail "conflict copy missing"
git -C "$P" check-ignore -q .ai/local/plugin-update/.ai/state/README.md && pass "the conflict copy is git-ignored" || fail "conflict copy should be ignored"
cmp -s "$P/.ai/policies/safety.md" "$PLUGIN_ROOT/skills/ai-init/templates/.ai/policies/safety.md" \
    && pass "an untouched file is replaced" || fail "safety.md not updated"
[ "$(cat "$P/.ai/project/overview.md")" = "the overview a human wrote" ] && pass ".ai/project/ is never updated" || fail "the knowledge base was touched"
[ -f "$P/.ai/policies/security.md" ] && pass "a missing template is created" || fail "missing file not created"
grep -q 'keep me' "$P/CLAUDE.md" && grep -q '.ai/state/handoff.md' "$P/CLAUDE.md" \
    && pass "the CLAUDE.md block is updated and the rest of the file kept" || fail "CLAUDE.md update wrong"
[ "$(grep -c 'claude-agentic:start' "$P/CLAUDE.md")" = 1 ] && pass "one managed block remains" || fail "block duplicated"
grep -q 'verify_command is empty' <<<"$out" && pass "an empty verify_command is flagged" || fail "hint missing" "$out"

echo "== idempotent"
snap=$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)
out=$(python3 "$UPDATE" "$P" --apply 2>&1)
grep -q '^0 automatic, 1 conflict' <<<"$out" && pass "a second run has nothing automatic left" || fail "second run not clean" "$out"
[ "$snap" = "$(cd "$P" && find . -path ./.git -prune -o -type f -print | sort | xargs md5sum | md5sum)" ] \
    && pass "a second run changes nothing" || fail "second run changed files"
out=$(python3 "$UPDATE" "$P" --check) && pass "--check exits 0 once only a hand-merge choice remains" || fail "--check should exit 0"
[ "$out" = "project matches the installed plugin (1 file(s) differ by hand-merge choice)" ] \
    && pass "the plain --check line is byte-identical" || fail "the plain --check line changed" "$out"

echo "== a stale mirror stays stale"
P2="$TMP/proj2"; mkdir -p "$P2"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P2" >/dev/null
jq '.tiers.T0.examples += ["x"]' "$P2/.ai/policies/risk-tiers.json" > "$TMP/rt" && mv "$TMP/rt" "$P2/.ai/policies/risk-tiers.json"
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
grep -q '.ai/state/handoff.md' "$P5/CLAUDE.md" && grep -q 'claude-agentic:start' "$P5/AGENTS.md" \
    && pass "both blocks are brought up to date over the one .ai/ tree" || fail "dual-runtime blocks not updated"

echo "== a project that also declares Gemini and Junie gets their blocks too"
P6="$TMP/proj6"; mkdir -p "$P6"
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P6" --runtime claude,codex,gemini,junie >/dev/null
for f in GEMINI.md .junie/guidelines.md; do
    grep -q 'claude-agentic:start' "$P6/$f" && pass "$f carries the managed block" || fail "$f has no block"
done
grep -q '.ai/policies/safety.md' "$P6/GEMINI.md" \
    && pass "the Gemini block routes to the policies like every other runtime" || fail "the Gemini block is wrong"
python3 "$UPDATE" "$P6" --apply >/dev/null 2>&1
python3 "$UPDATE" "$P6" | grep -q '^0 automatic, 0 conflict' \
    && pass "a four-runtime project is idempotent" || fail "four-runtime project not idempotent" "$(python3 "$UPDATE" "$P6")"
# an edited block is the user's, in a fourth runtime exactly as in the first
printf '\n<!-- claude-agentic:start -->\nmy own text\n<!-- claude-agentic:end -->\n' > "$P6/GEMINI.md"
python3 "$UPDATE" "$P6" | grep -q 'conflict  GEMINI.md' \
    && pass "an edited Gemini block is a conflict, never overwritten" || fail "an edited Gemini block was not protected"

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
out=$(python3 "$UPDATE" "$S0" --check); [ $? -eq 1 ] && grep -q "schema 0 -> $CURRENT" <<<"$out" \
    && pass "--check exits 1 and names the schema step" || fail "--check should name the schema" "$out"
before=$(cd "$S0" && find . -type f | sort | xargs md5sum | md5sum)
python3 "$UPDATE" "$S0" >/dev/null
[ "$before" = "$(cd "$S0" && find . -type f | sort | xargs md5sum | md5sum)" ] \
    && pass "the migration dry run writes nothing" || fail "the dry run changed files"
python3 "$UPDATE" "$S0" --apply >/dev/null
[ "$(cat "$S0/.ai/VERSION")" = "$CURRENT" ] && pass "the apply records the schema version" || fail "VERSION not written"
python3 "$UPDATE" "$S0" | grep -q '^0 automatic' && pass "a second run has nothing left to migrate" || fail "not idempotent" "$(python3 "$UPDATE" "$S0")"
out=$(python3 "$UPDATE" "$S0" --check) && pass "--check exits 0 once the schema is current" || fail "--check should exit 0"
[ "$out" = "project matches the installed plugin" ] && pass "the plain current line is byte-identical" || fail "the plain --check line changed" "$out"

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

echo "== schema 3: the pipeline text leaves the instruction files, the human's text stays (R12/R13)"
# A project at schema 2, both runtimes, from the oldest templates: its root
# instruction files still carry the shipped `## SDLC workflow` section.
v2_project() {
    local d="$1"; mkdir -p "$d"
    CLAUDE_ROUTING_TEMPLATES="$OLD/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$d" --runtime both >/dev/null
    CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$d" --runtime both >/dev/null
    cp -r "$FIX/schema-v2/.ai" "$d/"
}
S8="$TMP/schema2"; v2_project "$S8"
grep -q '^## SDLC workflow' "$S8/CLAUDE.md" && grep -q '^## SDLC workflow' "$S8/AGENTS.md" \
    && pass "the schema-2 fixture carries the shipped section in both files" || fail "the fixture should start from the old skeletons"
printf '\n# my notes\nkeep me\n' >> "$S8/CLAUDE.md"
# A line rewritten inside the managed block, where the plugin also changed it.
python3 - "$S8/AGENTS.md" <<'PY'
import sys
path = sys.argv[1]
data = open(path, "rb").read()
start = data.find(b"<!-- claude-agentic:start -->")
line2 = data.find(b"\n", data.find(b"\n", start) + 1) + 1
line3 = data.find(b"\n", line2) + 1
open(path, "wb").write(data[:line2] + b"my own rule, right inside the block\n" + data[line3:])
PY
printf '# GEMINI\n\nmy own instructions\n' > "$S8/GEMINI.md"          # a third runtime, no block yet
printf '\n## my routing note\nalways ask me first\n' >> "$S8/.ai/AGENTS.md"

out=$(python3 "$UPDATE" "$S8")
grep -q '^  update    CLAUDE.md .*\[0003\] SDLC workflow section removed (now in the managed block)' <<<"$out" \
    && pass "the dry run names the section it will take out" || fail "no 0003 line for CLAUDE.md" "$out"
grep -q 'AGENTS.md: the managed block was edited here' <<<"$out" \
    && pass "and hints that an edited block cannot be replaced" || fail "no edited-block hint" "$out"
before=$(cd "$S8" && find . -type f | sort | xargs md5sum | md5sum)
[ "$before" = "$(cd "$S8" && find . -type f | sort | xargs md5sum | md5sum)" ] && pass "the dry run writes nothing" || fail "the dry run changed files"

python3 "$UPDATE" "$S8" --apply >/dev/null
grep -q 'SDLC workflow' "$S8/CLAUDE.md" && fail "the shipped section should be gone" || pass "the shipped section is removed"
grep -q 'keep me' "$S8/CLAUDE.md" && [ "$(grep -c 'claude-agentic:start' "$S8/CLAUDE.md")" = 1 ] \
    && pass "and the human's own lines and the one block are kept" || fail "CLAUDE.md lost the user's text"
grep -q 'SDLC workflow' "$S8"/.ai/reports/project-update-*/original/CLAUDE.md \
    && pass "the file the migration rewrote is kept under .ai/reports/" || fail "no original for a migration update outside .ai/"
grep -q 'my own rule, right inside the block' "$S8/AGENTS.md" \
    && pass "an edited managed block is never overwritten" || fail "the edited block was replaced"
cmp -s "$S8/.ai/local/plugin-update/AGENTS.md" "$PLUGIN_ROOT/skills/ai-init/templates/AGENTS.block.md" \
    && pass "and the plugin's stub waits in the local copy" || fail "no conflict copy for the edited block"
grep -q 'SDLC workflow' "$S8/AGENTS.md" && fail "the section should leave an edited-block file too" \
    || pass "the section leaves the file whose block was edited, which is a separate decision"
grep -q 'claude-agentic:start' "$S8/GEMINI.md" && grep -q 'my own instructions' "$S8/GEMINI.md" \
    && pass "a third runtime's file gains the block without losing its text" || fail "GEMINI.md update wrong"
[ "$(cat "$S8/.ai/VERSION")" = "$CURRENT" ] && pass "the schema reaches $CURRENT: 0003 holds it for nothing" || fail "VERSION not written"

out=$(python3 "$UPDATE" "$S8")
# Two hand-merge choices: the edited managed block, and the router — edited on
# the oldest shipped version, so the plugin's later router changes really
# collide with the human's note (T-2026-10-13-004 re-review: not silenced).
grep -q '^0 automatic, 2 conflict' <<<"$out" \
    && grep -qE '^  conflict  *\.ai/AGENTS\.md' <<<"$out" \
    && pass "a second run has only the two hand-merge choices left, the router among them" || fail "second run not clean" "$out"
[ "$(grep -c '^## Shared files$' "$S8/.ai/AGENTS.md")" = 1 ] && grep -q '^always ask me first$' "$S8/.ai/AGENTS.md" \
    && pass "the router keeps the human's note and names the shared files once" || fail "router after the migration" "$(grep -n '^## ' "$S8/.ai/AGENTS.md")"
python3 "$UPDATE" "$S8" --check >/dev/null && pass "--check exits 0 once only a hand-merge choice remains" || fail "--check should exit 0"

echo "== an edited section is the human's, and is only ever hinted at"
S9="$TMP/schema2edited"; v2_project "$S9"
sed -i 's/^`\/ai-task <request>` is the default route for a change: it classifies the risk,$/`\/ai-task <request>` is the default route here, and we always open an ADR first,/' "$S9/CLAUDE.md"
snap=$(md5sum "$S9/CLAUDE.md" | cut -d' ' -f1)
out=$(python3 "$UPDATE" "$S9" --apply 2>&1)
[ "$(md5sum "$S9/CLAUDE.md" | cut -d' ' -f1)" != "$snap" ] && grep -q 'we always open an ADR first' "$S9/CLAUDE.md" \
    && pass "an edited section survives the migration" || fail "an edited section must not be rewritten" "$out"
grep -q 'CLAUDE.md: the SDLC workflow section was edited' <<<"$out" \
    && pass "and the human is told it is now theirs to keep" || fail "no hint for an edited section" "$out"
grep -q '^  update    CLAUDE.md .*\[0003\]' <<<"$out" && fail "0003 must not touch an edited section" "$out" \
    || pass "0003 plans no rewrite it cannot match verbatim"
[ "$(cat "$S9/.ai/VERSION")" = "$CURRENT" ] && pass "and the schema still advances" || fail "a hint must not hold the schema"

echo "== the migration says nothing about which runtime a project uses"
grep -in 'claude\|codex' "$PLUGIN_ROOT/skills/project-update/migrations/0002_task_journal.py" \
    && fail "0002 must not name a runtime" || pass "0002 names no runtime"

echo "== a docs/sdlc-only project has no schema and runs no migration"
S6="$TMP/sdlconly"; mkdir -p "$S6"
CLAUDE_ROUTING_TEMPLATES="$OLD/project-init/templates" bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$S6" >/dev/null
out=$(python3 "$UPDATE" "$S6")
grep -qE 'schema|VERSION' <<<"$out" && fail "a project without .ai/ should see no schema" "$out" || pass "no schema for a docs/sdlc-only project"
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
[ $rc -eq 2 ] && grep -q '0002' <<<"$out" && pass "a gap in the migrations exits 2 and names it" || fail "a gap should exit 2" "$out"
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
mv "$NEXT/.ai/policies/coding.md" "$NEXT/.ai/policies/code-style.md"
sed -i '2i A line the next plugin version inserted near the top.' "$NEXT/.ai/policies/code-style.md"

echo "== a migration that breaks the rules is refused before anything is written"
S5="$TMP/schemarules"; v0_project "$S5"
snap=$(cd "$S5" && find . -type f | sort | xargs md5sum | md5sum)
check_refused() {  # <fixture dir> <text the message must contain> <what the rule is>
    local out rc
    out=$(CLAUDE_AGENTIC_MIGRATIONS="$FIX/$1" python3 "$UPDATE" "$S5" --apply 2>&1); rc=$?
    [ $rc -eq 2 ] && grep -q "$2" <<<"$out" \
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
printf '\n## My own rule\nalways reproduce the bug first\n' >> "$S3/.ai/policies/coding.md"
python3 "$STATE" --root "$S3" quick --goal "a task in flight" --workflow feature --tier T2 --files .ai/policies/coding.md >/dev/null
export CLAUDE_AGENTIC_MIGRATIONS="$SYNTH" CLAUDE_AGENTIC_TEMPLATES="$NEXT"
out=$(python3 "$UPDATE" "$S3")
grep -q '^  schema    0 -> 3 ' <<<"$out" && pass "the schema line counts every pending migration" || fail "schema line wrong" "$out"
[ "$(printf '%s' "$out" | grep -c '^  move      .ai/policies/coding.md -> .ai/policies/code-style.md  \[0002\]')" = 1 ] \
    && pass "a move is listed once, with its source and its migration" || fail "move line wrong" "$out"
grep -q 'still-not-there' <<<"$out" && fail "a move of a file the project never had should be skipped" "$out" \
    || pass "a move whose source is absent is skipped"
grep -q '^  merge     .ai/policies/code-style.md .*your edits kept' <<<"$out" \
    && pass "the template history follows the move: the file merges at its new path" \
    || fail "a file edited at the old path must merge at the new one, not conflict" "$out"
grep -q '^  delete?   .ai/legacy-notes.md .*needs --apply --confirm-delete NAME' <<<"$out" \
    && pass "a deletion is proposed, not performed" || fail "delete? line wrong" "$out"
grep -q 'policy .*~ schema_probe\|policy .*+ schema_probe' <<<"$out" \
    && pass "a migration's policy edit is listed for confirmation" || fail "no policy line for the migrated policy" "$out"
grep -q 'deletion(s) awaiting --confirm-delete' <<<"$out" && pass "the summary counts what is waiting for a human" || fail "no deletion count" "$out"
grep -q 'a task is in flight while the schema changes' <<<"$out" && pass "a task in flight is flagged" || fail "no in-flight hint" "$out"
first=$(printf '%s' "$out" | grep -n '^  \(create\|move\|update\|delete?\)' | head -1)
grep -q '\[000' <<<"$first" && pass "the migrations are planned before the template merge" || fail "a migration item must come first" "$out"

echo "== the apply keeps the edit at the new path, the original, and the task"
python3 "$UPDATE" "$S3" --apply >/dev/null
grep -q 'always reproduce the bug first' "$S3/.ai/policies/code-style.md" && pass "an edit made at the old path survives the move" || fail "the edit was lost"
grep -q 'A line the next plugin version inserted near the top' "$S3/.ai/policies/code-style.md" \
    && pass "and the new template's change arrives with it" || fail "the merge lost the plugin's change"
[ ! -e "$S3/.ai/policies/coding.md" ] && pass "and the old path is gone" || fail "the move left its source behind"
[ -f "$S3"/.ai/reports/project-update-*/original/.ai/policies/coding.md ] && pass "the original is kept under .ai/reports/" || fail "no original kept"
[ "$(cat "$S3/.ai/project/schema-note.md")" = "added by migration 0001" ] && pass "create adds a file once" || fail "create wrong"
[ "$(jq -r .schema_probe "$S3/.ai/policies/risk-tiers.json")" = "0003" ] && pass "a policy edit is applied" || fail "policy edit missing"
grep -q 'added by migration 0003' "$S3/.ai/policies/testing.md" && pass "a text edit is applied" || fail "text edit missing"
python3 "$UPDATE" "$S3" --apply >/dev/null   # plan() runs again while the schema is held
[ "$(grep -c 'added by migration 0003' "$S3/.ai/policies/testing.md")" = 1 ] \
    && pass "an idempotent edit does not apply twice when the run repeats" || fail "the migration duplicated its edit"
[ -f "$S3/.ai/legacy-notes.md" ] && pass "the proposed deletion did not happen" || fail "a file was deleted without confirmation"
[ ! -e "$S3/.ai/VERSION" ] && pass "and the schema is held until the deletion is settled" || fail "VERSION written with a deletion pending"
out=$(python3 "$UPDATE" "$S3" --check); [ $? -eq 1 ] && grep -q 'the schema stays at 0' <<<"$out" \
    && pass "--check reports a held schema instead of calling the project current" || fail "--check must not hide a held schema" "$out"
[ "$(jq -r '.approved_plan.steps[0].allowed_files[0]' "$S3/.ai/state/current.json")" = ".ai/policies/code-style.md" ] \
    && pass "the task in flight follows the migration" || fail "the task's allowed_files were not migrated"
[ "$(jq -r '.history[-1].event' "$S3/.ai/state/current.json")" = "schema_migrated" ] && pass "and the state records why" || fail "no schema_migrated entry"
[ "$(python3 "$STATE" --root "$S3" get --field current_stage)" = "implementation" ] && pass "state.py still reads the migrated state" || fail "the task state is no longer parseable"
[ "$(cat "$S3/.ai/project/overview.md" | head -1)" = "# Overview" ] && pass ".ai/project/ is left alone by a migration run" || fail "the knowledge base was touched"

echo "== a human confirms the deletion, and only then is it performed"
python3 "$UPDATE" "$S3" --confirm-delete tester >/dev/null 2>&1; [ $? -eq 2 ] && pass "--confirm-delete without --apply is refused" || fail "should be an argparse error"
python3 "$UPDATE" "$S3" --apply --confirm-delete "" >/dev/null 2>&1; [ $? -eq 2 ] && pass "an empty confirmation name is refused" || fail "empty --confirm-delete should be refused"
out=$(env -u AI_UNATTENDED python3 "$UPDATE" "$S3" --apply --confirm-delete tester </dev/null); rc=$?
[ $rc -eq 5 ] && pass "--confirm-delete without a human present is refused (exit 5)" || fail "expected exit 5 without a terminal, got $rc" "$out"
[ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_REFUSED ] && pass "and says so on the first stdout line" || fail "no ADOPT_REFUSED on line 1" "$out"
[ -e "$S3/.ai/legacy-notes.md" ] && pass "and the file is still there" || fail "a refused deletion removed the file"
if [ $HAS_PTY -eq 1 ]; then
    cp -a "$S3" "$TMP/schemaops-tty"
    out=$(pty env "${NOMARK[@]}" CLAUDECODE=1 python3 "$UPDATE" "$S3" --apply --confirm-delete tester); rc=$?
    [ $rc -eq 5 ] && [ -e "$S3/.ai/legacy-notes.md" ] && grep -q CLAUDECODE <<<"$out" \
        && pass "CLAUDECODE=1 with a terminal: exit 5, names the marker, the file stays" || fail "CLAUDECODE under a pty (rc=$rc)" "$out"
    out=$(pty env "${NOMARK[@]}" python3 "$UPDATE" "$TMP/schemaops-tty" --apply --confirm-delete tester); rc=$?
    [ $rc -eq 0 ] && [ ! -e "$TMP/schemaops-tty/.ai/legacy-notes.md" ] \
        && [ "$(jq -r '.deletions[0].via' "$TMP"/schemaops-tty/.ai/reports/project-update-*/migration.json)" = terminal ] \
        && pass "a terminal and no marker: deleted, migration.json says via: terminal" || fail "human deletion (rc=$rc)" "$out"
else
    echo "  SKIP  no pty here (script -qec gives no terminal): the F3 terminal cases did not run"
fi
# The launcher's declaration, on this command only: no terminal here or in CI.
AI_UNATTENDED=1 python3 "$UPDATE" "$S3" --apply --confirm-delete tester >/dev/null
[ ! -e "$S3/.ai/legacy-notes.md" ] && pass "the confirmed deletion is performed" || fail "the file should be gone"
[ -f "$S3"/.ai/reports/project-update-*/original/.ai/legacy-notes.md ] && pass "its original is kept too" || fail "no original for the deletion"
rec=$(cat "$S3"/.ai/reports/project-update-*/migration.json)
[ "$(printf '%s' "$rec" | jq -r '.deletions[0].confirmed_by')" = tester ] && pass "migration.json records who confirmed it" || fail "no confirmed_by" "$rec"
[ "$(printf '%s' "$rec" | jq -r '.deletions[0].via')" = unattended ] && pass "and why the gate passed: via unattended" || fail "no via" "$rec"
[ "$(printf '%s' "$rec" | jq -r '.to')" = "$(cat "$S3/.ai/VERSION")" ] && pass "and the version the project actually reached" || fail "migration.json disagrees with .ai/VERSION" "$rec"
python3 "$UPDATE" "$S3" | grep -q '^0 automatic' && pass "a second run after the migrations is a no-op" || fail "not idempotent" "$(python3 "$UPDATE" "$S3")"
unset CLAUDE_AGENTIC_MIGRATIONS CLAUDE_AGENTIC_TEMPLATES

echo "== a target that is not a regular file aborts the apply"
S4="$TMP/schemalink"; v0_project "$S4"
rm "$S4/.ai/policies/testing.md"; ln -s "$TMP/elsewhere" "$S4/.ai/policies/testing.md"
out=$(python3 "$UPDATE" "$S4" --apply 2>&1); rc=$?
[ $rc -eq 3 ] && [ ! -e "$TMP/elsewhere" ] && pass "a symlinked target exits 3 and is not written through" || fail "a symlink must not be followed" "$out"
grep -q 'nothing after it was written; run the dry run again' <<<"$out" && pass "and the abort says what to do" || fail "abort message wrong" "$out"

echo "== both runtimes reach the same schema"
for rt in claude codex both; do
    d="$TMP/schema-$rt"; v0_project "$d" "$rt"
    python3 "$UPDATE" "$d" --apply >/dev/null
    [ "$(cat "$d/.ai/VERSION")" = "$CURRENT" ] || fail "a $rt project did not reach schema $CURRENT"
done
pass "Claude-only, Codex-only and dual-runtime projects all reach schema $CURRENT"
grep -lE 'claude|codex' "$PLUGIN_ROOT/skills/project-update/migrations/"[0-9]*.py >/dev/null 2>&1 \
    && fail "a migration must not branch on the runtime" || pass "no migration branches on the runtime"

echo "== a rendered rule whose source is gone waits for a human, like any deletion (R9)"
RD="$TMP/rules-gate"; mkdir -p "$RD"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$RD" --runtime claude >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$RD" --runtime claude >/dev/null
cp -r "$PLUGIN_ROOT/tests/fixtures/instructions/rules-project/.ai" "$RD/"
mkdir -p "$RD/src/Payment" "$RD/tests/Payment"
python3 "$UPDATE" "$RD" --apply >/dev/null 2>&1 || fail "the rules could not be rendered"
printf '\n# mine\nkeep me\n' >> "$RD/src/Payment/CLAUDE.md"
rm "$RD/.ai/rules/payment.md"
out=$(python3 "$UPDATE" "$RD" 2>&1)
grep -q "delete? *.claude/rules/payment.md" <<<"$out" \
    && pass "the path-scoped copy is proposed, not deleted" || fail "no delete? for the rendered copy" "$out"
grep -q 'needs --apply --confirm-delete NAME' <<<"$out" \
    && pass "and says how a human confirms it" || fail "the deletion does not name its gate"
python3 "$UPDATE" "$RD" --apply >/dev/null 2>&1
[ -f "$RD/.claude/rules/payment.md" ] \
    && pass "an --apply without the confirmation leaves it alone" || fail "the copy was deleted unconfirmed"
grep -q 'keep me' "$RD/src/Payment/CLAUDE.md" \
    && pass "the human's text around a removed block survives" || fail "the human's text was lost"
grep -q 'claude-agentic:rule:payment' "$RD/src/Payment/CLAUDE.md" \
    && fail "the stale block should have been taken out" || pass "the stale block was taken out without a gate: it is ours"
AI_UNATTENDED=1 python3 "$UPDATE" "$RD" --apply --confirm-delete "Ivan" >/dev/null 2>&1
[ -f "$RD/.claude/rules/payment.md" ] \
    && fail "the confirmed deletion did not happen" || pass "the confirmed deletion is performed"
[ -f "$RD/.ai/reports/project-update-$(date -u +%Y-%m-%d)/original/.claude/rules/payment.md" ] \
    && pass "its original is kept" || fail "the deleted copy was not kept"
out=$(python3 "$UPDATE" "$RD" 2>&1)
grep -q '^0 automatic, 0 conflict' <<<"$out" \
    && pass "and the project is then up to date" || fail "the rules run is not idempotent" "$out"

echo "== every key in the template history is accounted for"
python3 - "$PLUGIN_ROOT" <<'PY'
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "skills", "project-update"))
import migrations                                        # noqa: E402
index = json.load(open(os.path.join(root, "skills/project-update/history/index.json")))
current, sources = set(), set()
for name, base in (("ai-init", os.path.join(root, "skills", "ai-init", "templates")),
                   ("project-init", os.path.join(root, "skills", "project-init", "templates")),
                   ("ai-init/.ai", os.path.join(root, "ai"))):
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

echo "== schema 4: a task in flight gains the gate keys and keeps working (R14)"
S9="$TMP/schema3"; mkdir -p "$S9"
FIXV3="$FIX/schema-v3"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$S9" --runtime claude >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$S9" --runtime claude >/dev/null
cp -r "$FIXV3/.ai" "$S9/"      # VERSION 3 and a task in flight, as the fixture ships them

out=$(python3 "$UPDATE" "$S9")
grep -q '\[0004\]' <<<"$out" \
    && pass "the dry run names the state migration" || fail "no 0004 line" "$out"
python3 - "$S9" <<'PY2'
import json, os, sys
state = json.load(open(os.path.join(sys.argv[1], ".ai", "state", "current.json")))
raise SystemExit(0 if "diff" not in state else 1)
PY2
[ $? -eq 0 ] && pass "and the dry run writes nothing into the state" || fail "the dry run must not write"

python3 "$UPDATE" "$S9" --apply >/dev/null
python3 - "$S9" <<'PY2'
import json, os, sys
state = json.load(open(os.path.join(sys.argv[1], ".ai", "state", "current.json")))
assert state["diff"]["base_tree"] is None, "a base tree must not be invented"
assert state["diff"]["task"]["status"] == "not_measured"
assert state["tests"] == {"runs": [], "suite_runs": 0}
assert state["risk_tier_lowered"]["by"] is None
assert state["sensors"]["file"].endswith("sensors.json")
steps = state["approved_plan"]["steps"]
assert [s["kind"] for s in steps] == ["implementation", "implementation"], steps
assert all(s["tree_before"] is None and s["diff"] is None for s in steps)
assert state["goal"] == "widen the export" and state["completed_steps"] == ["1"]
PY2
[ $? -eq 0 ] && pass "the keys are added with nulls, and nothing else is touched" || fail "0004 changed the task"
[ "$(cat "$S9/.ai/VERSION")" = "$CURRENT" ] && pass "the schema reaches $CURRENT" || fail "VERSION not written"
python3 "$UPDATE" "$S9" | grep -q '^0 automatic' && pass "a second run has nothing to do" || fail "0004 is not idempotent"

out=$(env -u CLAUDECODE python3 "$STATE" --root "$S9" step-done 2 2>&1); rc=$?
[ $rc -eq 0 ] && grep -q 'unavailable' <<<"$out" \
    && pass "a task that started before schema 4 finishes its step, measuring nothing" \
    || fail "step-done should carry on" "$out($rc)"

grep -qiE 'claude|codex' "$PLUGIN_ROOT/skills/project-update/migrations/0004_deterministic_gates.py" \
    && fail "a migration must not name a runtime" || pass "0004 names no runtime"

echo "== schema 5: a task in flight gains the handoff keys and keeps working (R17)"
S10="$TMP/schema4"; mkdir -p "$S10"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$S10" --runtime claude >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$S10" --runtime claude >/dev/null
cp -r "$FIX/schema-v4/.ai" "$S10/"     # VERSION 4 and a task in flight
[ "$CURRENT" -ge 5 ] && pass "the migrations reach schema 5 or later" || fail "CURRENT is $CURRENT, expected 5 or later"
env -u CLAUDECODE python3 "$STATE" --root "$S10" set next_action "before 0005" >/dev/null 2>&1 \
    && pass "a mutating command works at schema 4, defaults filled in memory" || fail "state.py failed on a schema-4 task"
python3 - "$S10" <<'PY2'
import json, os, sys
state = json.load(open(os.path.join(sys.argv[1], ".ai", "state", "current.json")))
assert state["handoff"]["pending_to"] is None and state["cross_vendor_review"] is None
PY2
[ $? -eq 0 ] && pass "and state.py saved the schema-5 defaults with it" || fail "schema-5 defaults not saved by state.py"
cp -r "$FIX/schema-v4/.ai" "$S10/"     # back to the bare schema-4 task
python3 "$UPDATE" "$S10" --check >/dev/null; [ $? -eq 1 ] && pass "--check exits 1 at schema 4" || fail "--check should exit 1 at schema 4"
out=$(python3 "$UPDATE" "$S10")
grep -q '\[0005\]' <<<"$out" && pass "the dry run names migration 0005" || fail "no 0005 line" "$out"
python3 "$UPDATE" "$S10" --apply >/dev/null
python3 - "$S10" <<'PY2'
import json, os, sys
state = json.load(open(os.path.join(sys.argv[1], ".ai", "state", "current.json")))
assert state["handoff"]["pending_to"] is None and state["handoff"]["pending_since"] is None
assert state["handoff"]["file"] == ".ai/state/handoff.md"
assert state["cross_vendor_review"] is None
assert state["diff"]["task"]["status"] == "not_measured"     # schema 4 untouched
assert state["goal"] == "widen the export" and state["completed_steps"] == ["1"]
PY2
[ $? -eq 0 ] && pass "the keys are added with nulls, and nothing else is touched" || fail "0005 changed the task"
[ "$(cat "$S10/.ai/VERSION")" = "$CURRENT" ] && pass "the schema reaches $CURRENT" || fail "VERSION not written"
python3 "$UPDATE" "$S10" | grep -q '^0 automatic' && pass "a second run has nothing to do" || fail "0005 is not idempotent"
python3 "$UPDATE" "$S10" --check >/dev/null && pass "--check exits 0 once migrated" || fail "--check should exit 0 after 0005"
env -u CLAUDECODE python3 "$STATE" --root "$S10" get --field history 2>/dev/null \
    | grep -q '"detail": "0005 ' && pass "schema_migrated 0005 is recorded in the task's history" \
    || fail "no schema_migrated entry for 0005"
env -u CLAUDECODE python3 "$STATE" --root "$S10" set next_action "after 0005" >/dev/null 2>&1 \
    && pass "and a mutating command still works at schema 5" || fail "state.py failed after 0005"
grep -qiE 'claude|codex' "$PLUGIN_ROOT/skills/project-update/migrations/0005_runtimes_and_plans.py" \
    && fail "a migration must not name a runtime" || pass "0005 names no runtime"

echo "== a conflict on a model key in risk-tiers.json prints the tier hint (R21)"
P21="$TMP/proj21"; mkdir -p "$P21"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P21" >/dev/null
jq '.model_tiers.EXPERT.model = "my own expert"' "$P21/.ai/policies/risk-tiers.json" > "$TMP/rt" && mv "$TMP/rt" "$P21/.ai/policies/risk-tiers.json"
out=$(python3 "$UPDATE" "$P21" 2>&1)
grep -q 'kept your value for: .*model_tiers.EXPERT.model' <<<"$out" && pass "the edited model value is a conflict" || fail "no model_tiers conflict" "$out"
[ "$(printf '%s' "$out" | grep -c 'the plugin now names tiers (FAST/BALANCED/STRONG/EXPERT), not models; the model of a tier comes from the installed plan: state.py profile --tier <TIER>')" = 1 ] \
    && pass "one hint names the tier vocabulary and state.py profile --tier" || fail "tier hint missing or repeated" "$out"
P22="$TMP/proj22"; mkdir -p "$P22"
CLAUDE_AGENTIC_TEMPLATES="$OLD/ai-init/templates" bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$P22" >/dev/null
sed -i "4s/.*/my own wording of who writes current.json/" "$P22/.ai/state/README.md"
out=$(python3 "$UPDATE" "$P22" 2>&1)
grep -q 'names tiers' <<<"$out" && fail "the hint must appear only for a model-key conflict" "$out" || pass "any other conflict prints no tier hint"

echo "== --check --budget: a root instruction file over its byte budget exits 1 (WP6 R21)"
B="$TMP/budget"; mkdir -p "$B"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$B" --runtime claude >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$B" --runtime claude >/dev/null
out=$(python3 "$UPDATE" "$B" --check --budget); rc=$?
[ $rc -eq 0 ] && [ -z "$out" ] && pass "a fresh scaffold is within budget: exit 0, nothing printed" || fail "fresh scaffold: rc=$rc" "$out"
python3 "$UPDATE" "$B" --budget >/dev/null 2>&1; [ $? -eq 2 ] && pass "--budget without --check is a usage error" || fail "--budget alone should exit 2"
head -c 400 /dev/zero | tr '\0' 'x' >> "$B/CLAUDE.md"; printf '\n' >> "$B/CLAUDE.md"
out=$(python3 "$UPDATE" "$B" --check --budget); rc=$?
[ $rc -eq 1 ] && grep -qE '^CLAUDE\.md file [0-9]+ B over the skeleton budget of 2048 B$' <<<"$out" \
    && pass "a padded CLAUDE.md exits 1 and names the file and the budget" || fail "padded file: rc=$rc" "$out"
grep -q ' block ' <<<"$out" && fail "the block itself is within budget and must not be listed" "$out" || pass "only the offender is listed"
# An installed plugin has skills/ but no instructions/: the budgets must still apply.
INST="$TMP/installed/skills"; mkdir -p "$INST"; cp -r "$PLUGIN_ROOT/skills/project-update" "$INST/"
out=$(python3 "$INST/project-update/update.py" "$B" --check --budget 2>&1); rc=$?
[ $rc -eq 1 ] && grep -q 'over the skeleton budget of 2048 B' <<<"$out" && ! grep -q Traceback <<<"$out" \
    && pass "from a skills-only install the shipped budgets apply" || fail "skills-only install: rc=$rc" "$out"
echo "== a legacy Codex-agentic marker pair is renamed, not doubled"
# An AGENTS.md written before the plugin's markers were unified carries
# <!-- Codex-agentic:start/end -->. The block inside is the shipped one.
L="$TMP/legacy"; mkdir -p "$L/.codex"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$L" >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$L" >/dev/null
git -C "$L" init -q
sed 's/claude-agentic:\(start\|end\)/Codex-agentic:\1/' "$PLUGIN_ROOT/skills/ai-init/templates/AGENTS.block.md" > "$TMP/legacy-block"
{ printf '# legacy\n\nkeep me above\n\n'; cat "$TMP/legacy-block"; printf '\n# my notes\nkeep me below\n'; } > "$L/AGENTS.md"
out=$(python3 "$UPDATE" "$L" 2>&1); rc=$?
[ $rc -eq 0 ] && pass "the dry run exits 0 on a legacy marker" || fail "dry run failed on a legacy marker" "$out"
grep -q 'AGENTS.md .*legacy Codex-agentic markers renamed' <<<"$out" \
    && pass "the dry run says the markers will be renamed" || fail "no rename line for the legacy block" "$out"
grep -q 'AGENTS.md (split?)' <<<"$out" \
    && fail "the dry run still reads the legacy block as no block and hints --adopt" "$out" \
    || pass "the dry run sees the legacy block as the managed block (no split? hint)"
python3 "$UPDATE" "$L" --apply >/dev/null 2>&1
[ "$(grep -c 'claude-agentic:start' "$L/AGENTS.md")" = 1 ] && pass "one current block remains" || fail "block doubled or missing" "$(cat "$L/AGENTS.md")"
if grep -q 'Codex-agentic' "$L/AGENTS.md"; then fail "the legacy markers are still there"; else pass "the legacy markers are gone"; fi
grep -q 'keep me above' "$L/AGENTS.md" && grep -q 'keep me below' "$L/AGENTS.md" \
    && pass "the text around the block is kept" || fail "text around the block lost"
diff <(sed -n '/claude-agentic:start/,/claude-agentic:end/p' "$L/AGENTS.md") "$PLUGIN_ROOT/skills/ai-init/templates/AGENTS.block.md" >/dev/null \
    && pass "the renamed block is the shipped one" || fail "the renamed block differs from the shipped block"
out=$(python3 "$UPDATE" "$L" --apply 2>&1)
grep -q '^0 automatic, 0 conflict' <<<"$out" && pass "a second run has nothing left" || fail "second run not clean" "$out"
# An edited line inside a legacy block: the markers are renamed and the edit is
# kept — the same path an edited current block takes.
E="$TMP/legacy-edited"; mkdir -p "$E/.codex"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$E" >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$E" >/dev/null
git -C "$E" init -q
{ printf '# legacy\n\n'; sed '3a my own rule, right inside the block' "$TMP/legacy-block"; } > "$E/AGENTS.md"
python3 "$UPDATE" "$E" --apply >/dev/null 2>&1
if grep -q 'Codex-agentic' "$E/AGENTS.md"; then fail "an edited legacy block keeps its old markers"; else pass "an edited legacy block gets the current markers"; fi
grep -q 'my own rule, right inside the block' "$E/AGENTS.md" && pass "and its edit is kept" || fail "the edit inside the legacy block was lost" "$(cat "$E/AGENTS.md")"
[ "$(grep -c 'claude-agentic:start' "$E/AGENTS.md")" = 1 ] && pass "with one block" || fail "edited legacy block doubled"
# Half a current pair next to a legacy pair is a broken file: nothing is renamed.
H="$TMP/legacy-half"; mkdir -p "$H/.codex"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$H" >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$H" >/dev/null
git -C "$H" init -q
{ printf '# half

<!-- claude-agentic:start -->
lone start

'; cat "$TMP/legacy-block"; } > "$H/AGENTS.md"
python3 "$UPDATE" "$H" --apply >/dev/null 2>&1
grep -q 'Codex-agentic:start' "$H/AGENTS.md" && [ "$(grep -c 'claude-agentic:end' "$H/AGENTS.md")" = 1 ] \
    && pass "a lone current marker beside a legacy pair renames nothing" || fail "a half pair plus a legacy pair was rewritten" "$(cat "$H/AGENTS.md")"

shipped=$(jq -cS '._budgets' "$PLUGIN_ROOT/instructions/runtimes.json")
default=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 -c 'import json, render_instructions as r; print(json.dumps(r.DEFAULT_BUDGETS, sort_keys=True, separators=(",", ":")))')
[ "$shipped" = "$default" ] && pass "DEFAULT_BUDGETS equals _budgets in runtimes.json" || fail "DEFAULT_BUDGETS drifted from runtimes.json" "$shipped / $default"

echo "== budget hint: a pristine legacy block over the budget is the plugin's to trim, not the project's"
# The hint compares the block with the shipped one. A legacy pair must be
# compared through its renamed markers, or a block that --apply will rewrite
# anyway is reported as "edited here, trimming it is yours".
PT="$TMP/padded-tpl"; rm -rf "$PT"; cp -r "$PLUGIN_ROOT/skills/ai-init/templates" "$PT"
python3 - "$PT/AGENTS.block.md" <<'PYT'
import sys
p = sys.argv[1]; t = open(p, encoding="utf-8").read()
i = t.index("<!-- claude-agentic:end -->")
open(p, "w", encoding="utf-8").write(t[:i] + "<!-- padding, over the project budget -->\n" * 60 + t[i:])
PYT
PB="$TMP/padded-legacy"; mkdir -p "$PB/.codex"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$PB" >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$PB" >/dev/null
git -C "$PB" init -q
{ printf '# legacy\n\n'; sed 's/claude-agentic:\(start\|end\)/Codex-agentic:\1/' "$PT/AGENTS.block.md"; } > "$PB/AGENTS.md"
out=$(CLAUDE_AGENTIC_TEMPLATES="$PT" python3 "$UPDATE" "$PB" 2>&1); rc=$?
grep -q 'AGENTS.md: the managed block is [0-9]* B, budget [0-9]* B — the plugin ships it that size' <<<"$out" \
    && pass "an untouched legacy block over budget is the plugin's" || fail "the hint blames the project for the plugin's own block (rc=$rc)" "$out"
grep -q 'trimming it is yours' <<<"$out" \
    && fail "an untouched legacy block is reported as edited here" "$out" || pass "no 'edited here' for the untouched block"
# The same block with one line of the project's own inside it is the project's.
sed -i '3a my own rule, right inside the block' "$PB/AGENTS.md"
out=$(CLAUDE_AGENTIC_TEMPLATES="$PT" python3 "$UPDATE" "$PB" 2>&1)
grep -q 'AGENTS.md: the managed block is .* trimming it is yours' <<<"$out" \
    && pass "an edited legacy block over budget is the project's" || fail "an edited legacy block should be the project's to trim" "$out"

summary "project-update"
