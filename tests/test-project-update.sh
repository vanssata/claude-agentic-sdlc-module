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

summary "project-update"
