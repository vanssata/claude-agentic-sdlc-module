#!/usr/bin/env bash
# update.py --adopt: a project carrying a foreign AI-tool structure (Spec Kit,
# Kiro, Cursor, Copilot, AI-DLC, Junie, Gemini, an oversized CLAUDE.md or
# AGENTS.md) is detected, planned onto claude-agentic's layout, and nothing is
# lost or written without the gates. Fixtures: tests/fixtures/adopt/README.md.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

UPDATE="$PLUGIN_ROOT/skills/project-update/update.py"
FIX="$PLUGIN_ROOT/tests/fixtures/adopt"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

# scaffold <dir> <runtime>: a fresh claude-agentic project, as the skills make it.
scaffold() {
    mkdir -p "$1"
    bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$1" --runtime "$2" >/dev/null
    bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$1" --runtime "$2" >/dev/null
}

# commit <dir>: a git work tree with everything committed.
commit() {
    [ -d "$1/.git" ] || { git -C "$1" init -q; git -C "$1" config user.email t@example.com; git -C "$1" config user.name t; }
    git -C "$1" add -A; git -C "$1" commit -qm "${2:-fixture}" >/dev/null
}

# adopt_fixture <name> <dest>: the fixture materialised as a real project —
# `dot-` components become `.`, `fixture-X.md` becomes `X.md` (appended to the
# scaffolded file when fixture.json says so), then committed.
adopt_fixture() {
    local fx="$FIX/$1" dest="$2" rel out app
    scaffold "$dest" "$(jq -r '.runtime' "$fx/fixture.json")"
    while IFS= read -r rel; do
        rel=${rel#./}
        out=$(printf '%s' "$rel" | sed -E 's#(^|/)dot-#\1.#g; s#(^|/)fixture-([A-Z]+\.md)$#\1\2#')
        app=$(jq -r --arg o "$out" '.instruction_append[$o] // empty' "$fx/fixture.json")
        mkdir -p "$dest/$(dirname "$out")"
        if [ -n "$app" ]; then cat "$fx/$rel" >> "$dest/$out"; else cp -p "$fx/$rel" "$dest/$out"; fi
    done < <(cd "$fx" && find . -type f ! -name README.md ! -name fixture.json ! -name split-proposal.fixture.json)
    commit "$dest"
}

# tree_sha <dir>: one hash over every file and its content, .git excluded.
tree_sha() {
    (cd "$1" && find . -path ./.git -prune -o -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)
}

echo "== fixtures are stored encoded (the path guard and the runtimes never see a real name)"
out=$(find "$FIX" -name '.*' -o -name CLAUDE.md -o -name AGENTS.md -o -name GEMINI.md)
[ -z "$out" ] && pass "no dot-file and no real instruction file under tests/fixtures/adopt" || fail "a fixture path is stored unencoded" "$out"
for d in "$FIX"/*/; do
    grep -q '^Source: ' "$d/README.md" 2>/dev/null && pass "$(basename "$d") README names its source" || fail "$(basename "$d") has no Source: line"
done

echo "== the mapping table loads, and a bad one is refused"
cd "$PLUGIN_ROOT/skills/project-update" || exit 1
python3 -c 'import adopt; adopt.load_table()' && pass "adopt-map.json is a valid table" || fail "adopt-map.json does not load"
printf '{"version":1,"tools":{"x":{"signature":["x/"],"roots":["x/"]}},"rows":[{"tool":"x","source":"x/*","transform":"shred"}]}' > "$TMP/bad.json"
python3 -c 'import adopt, sys
try:
    adopt.load_table(sys.argv[1])
except adopt.TableError:
    sys.exit(0)
sys.exit(1)' "$TMP/bad.json" && pass "an unknown transform is a table error" || fail "an unknown transform was accepted"
cd - >/dev/null || exit 1

echo "== R1, R2: each foreign structure is detected and planned, and the dry run writes nothing"
for base in "$TMP/with space" "$TMP/plain"; do
    for f in speckit kiro cursor copilot aidlc; do
        P="$base/$f"; adopt_fixture "$f" "$P"
        before=$(tree_sha "$P")
        out=$(python3 "$UPDATE" "$P" --adopt); rc=$?
        [ $rc -eq 0 ] && pass "$f under '$(basename "$base")': dry run exits 0" || fail "$f under '$(basename "$base")': rc=$rc" "$out"
        printf '%s' "$out" | grep -qE "^  detect +$f " && pass "$f: one detect line" || fail "$f: no detect line" "$out"
        printf '%s' "$out" | grep -qE '^  adopt ' && pass "$f: at least one source planned" || fail "$f: nothing planned" "$out"
        printf '%s' "$out" | head -1 | grep -q 'mode: migrate' && pass "$f: migrate is the default mode (R3)" || fail "$f: no mode in the header" "$out"
        [ "$(tree_sha "$P")" = "$before" ] && pass "$f: the tree is byte-identical after the dry run" || fail "$f: the dry run wrote something"
    done
done
P="$TMP/plain"
out=$(python3 "$UPDATE" "$P/speckit" --adopt)
printf '%s' "$out" | grep -q '^  adopt     .specify/memory/constitution.md -> docs/sdlc/constitution.md .*append-section' \
    && pass "the Spec Kit constitution is appended to ours, not a conflict" || fail "constitution not planned as append-section" "$out"
printf '%s' "$out" | grep -q '^  dropped   .claude/skills/speckit-plan/SKILL.md' \
    && pass "a current Spec Kit skill is dropped" || fail "the speckit skill layout is not covered" "$out"
out=$(python3 "$UPDATE" "$P/cursor" --adopt)
printf '%s' "$out" | grep -q '.cursor/rules/frontend/react.mdc -> .ai/rules/frontend-react.md .*dirs: \[src/components, src/hooks\]' \
    && pass "a glob-scoped Cursor rule becomes a .ai/rules/ rule with dirs" || fail "react.mdc not a scoped rule" "$out"
printf '%s' "$out" | grep -q '^  ignored   .cursor/mcp.json' && pass "Cursor configuration is ignored, not adopted" || fail "mcp.json not ignored" "$out"
out=$(python3 "$UPDATE" "$P/kiro" --adopt)
printf '%s' "$out" | grep -q '.kiro/steering/tech.md -> .ai/policies/adopted/kiro-tech.md .*always' \
    && pass "a Kiro steering file without frontmatter is always included" || fail "tech.md not always" "$out"
printf '%s' "$out" | grep -q '^  ignored   .kiro/steering/aws-aidlc-rules/' \
    && pass "AI-DLC installed for Kiro stays out of the steering row" || fail "aws-aidlc-rules not ignored" "$out"

echo "== every row of the table is exercised by a fixture"
for f in junie-gemini large-claude-md large-agents-md; do adopt_fixture "$f" "$P/$f"; done
used=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$P" <<'EOF'
import sys, os
sys.dont_write_bytecode = True
import update, adopt
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
used = set()
for f in ("speckit", "kiro", "cursor", "copilot", "aidlc", "junie-gemini", "large-claude-md", "large-agents-md"):
    plan = update.Plan(os.path.join(sys.argv[1], f))
    used |= adopt.plan_adopt(plan, table, "migrate", None, update.shipped_block, caps["skeleton"]).rows_used
missing = [str(r["_n"]) + " " + r["tool"] + " " + r["source"] for r in table["rows"] if r["_n"] not in used]
print("\n".join(missing))
EOF
)
[ -z "$used" ] && pass "every mapping row matched a file in its fixture" || fail "rows no fixture exercises" "$used"

echo "== the four instruction files: foreign without the managed block, a split candidate only when too big"
for rt in claude codex gemini junie claude,codex; do
    S="$TMP/fresh-$rt"; scaffold "$S" "$rt"
    out=$(python3 "$UPDATE" "$S" --adopt); rc=$?
    [ $rc -eq 0 ] && printf '%s' "$out" | grep -q '^  no foreign structure detected$' \
        && pass "a fresh $rt scaffold is not foreign" || fail "a fresh $rt scaffold was detected (rc=$rc)" "$out"
done
S="$TMP/fresh-claude"; head -c 200 /dev/zero | tr '\0' 'n' >> "$S/CLAUDE.md"; printf '\n' >> "$S/CLAUDE.md"
out=$(python3 "$UPDATE" "$S" --adopt); rc=$?
printf '%s' "$out" | grep -q '^  split?    CLAUDE.md' && [ $rc -eq 0 ] && ! printf '%s' "$out" | grep -q unmapped \
    && pass "the scaffold plus 200 B of notes is a split candidate, not unmapped" || fail "no split? for a grown CLAUDE.md (rc=$rc)" "$out"
S="$TMP/fresh-codex"; head -c 200 /dev/zero | tr '\0' 'n' >> "$S/AGENTS.md"; printf '\n' >> "$S/AGENTS.md"
printf "%s" "$(python3 "$UPDATE" "$S" --adopt)" | grep -q '^  split?    AGENTS.md' && pass "the same for AGENTS.md" || fail "no split? for a grown AGENTS.md"
out=$(python3 "$UPDATE" "$P/junie-gemini" --adopt)
printf '%s' "$out" | grep -qE '^  detect +gemini +GEMINI.md' && printf '%s' "$out" | grep -qE '^  detect +junie ' \
    && pass "GEMINI.md and .junie/guidelines.md without the block are foreign" || fail "junie/gemini not detected" "$out"
printf '%s' "$out" | grep -q 'split?' && fail "small foreign instruction files are not split candidates" "$out" || pass "and at this size neither is a split candidate"
printf "%s" "$(python3 "$UPDATE" "$P/large-claude-md" --adopt)" | grep -q '^  split?    CLAUDE.md' && pass "large-claude-md lists split?" || fail "large-claude-md: no split?"
printf "%s" "$(python3 "$UPDATE" "$P/large-agents-md" --adopt)" | grep -q '^  split?    AGENTS.md' && pass "large-agents-md lists split?" || fail "large-agents-md: no split?"

echo "== R4: what no row maps fails loudly, and a human's decision settles it"
K="$TMP/kiro-hooks"; adopt_fixture kiro "$K"
mkdir -p "$K/.kiro/hooks"; printf '{"hooks": []}\n' > "$K/.kiro/hooks/lint-on-save.json"
out=$(python3 "$UPDATE" "$K" --adopt); rc=$?
[ $rc -eq 4 ] && pass "an unmapped Kiro hook exits 4" || fail "expected exit 4, got $rc" "$out"
[ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_INCOMPLETE ] && pass "ADOPT_INCOMPLETE on the first line" || fail "no token on line 1" "$out"
printf '%s' "$out" | grep -q '^  unmapped  .kiro/hooks/lint-on-save.json .*decisions.json' && pass "and it names the file and where to decide" || fail "no unmapped line" "$out"
mkdir -p "$K/.ai/reports/adopt-2000-01-01"
printf '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"drop","why":"Kiro agent hook; no equivalent here"}}}\n' \
    > "$K/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$K" --adopt); rc=$?
[ $rc -eq 0 ] && printf '%s' "$out" | grep -q '^  dropped   .kiro/hooks/lint-on-save.json .*no equivalent here' \
    && pass "a decision in an older adopt-* directory settles it" || fail "decision not honoured (rc=$rc)" "$out"
N="$TMP/nested"; scaffold "$N" claude; mkdir -p "$N/packages/x/.cursor/rules"
printf -- '---\nalwaysApply: true\n---\n\n- Use pnpm.\n' > "$N/packages/x/.cursor/rules/a.mdc"
out=$(python3 "$UPDATE" "$N" --adopt); rc=$?
[ $rc -eq 4 ] && printf '%s' "$out" | grep -q '^  unmapped  packages/x/.cursor/rules/a.mdc .*below the root' \
    && pass "a nested .cursor/rules/ is unmapped, exit 4" || fail "nested signature not unmapped (rc=$rc)" "$out"
I="$TMP/ignore-only"; scaffold "$I" claude; mkdir -p "$I/.kiro/settings"; printf '{}\n' > "$I/.kiro/settings/mcp.json"
out=$(python3 "$UPDATE" "$I" --adopt); rc=$?
[ $rc -eq 0 ] && printf '%s' "$out" | grep -q '^  ignored   .kiro/settings/mcp.json' && printf '%s' "$out" | grep -q '^0 automatic' \
    && pass "a tree with only ignored files prints them and 0 automatic" || fail "ignore-only tree (rc=$rc)" "$out"

echo "== R18, re-review C: rows stay inside their tool's roots; a file under two tools goes to the one that maps it"
X="$TMP/speckit-app"; adopt_fixture speckit "$X"; mkdir -p "$X/src/lib"; printf 'SPECKIT = 1\n' > "$X/src/lib/speckit_x.py"
out=$(python3 "$UPDATE" "$X" --adopt)
printf '%s' "$out" | grep -q 'src/lib/speckit_x.py' && fail "application code matched a Spec Kit row" "$out" || pass "src/lib/speckit_x.py is neither a source nor dropped"
C="$TMP/speckit-cursor"; adopt_fixture cursor "$C"
mkdir -p "$C/.specify/memory" "$C/.cursor/commands" "$C/.cursor/skills/speckit-plan"
printf '# Constitution\n\n### I. Tests first\n' > "$C/.specify/memory/constitution.md"
printf 'Run the plan script.\n' > "$C/.cursor/commands/speckit.plan.md"
printf -- '---\nname: speckit-plan\n---\n\nPlan.\n' > "$C/.cursor/skills/speckit-plan/SKILL.md"
out=$(python3 "$UPDATE" "$C" --adopt); rc=$?
[ $rc -eq 0 ] && printf '%s' "$out" | grep -q '^  dropped   .cursor/commands/speckit.plan.md .*\[speckit\]' && ! printf '%s' "$out" | grep -q unmapped \
    && pass "Spec Kit's .cursor/commands/ file is dropped by speckit, nothing unmapped" || fail "speckit+cursor overlap (rc=$rc)" "$out"

echo "== R23: a secret-looking line is named by file:line, its value never printed"
Z="$TMP/secret"; adopt_fixture cursor "$Z"
value="sk-$(date +%s)abcdefgh"
printf 'API_KEY=%s\n' "$value" >> "$Z/.cursorrules"; commit "$Z"
out=$(python3 "$UPDATE" "$Z" --adopt)
printf '%s' "$out" | grep -q '^  hint      .cursorrules:4 .*looks like a secret' && pass "the hint names .cursorrules:4" || fail "no secret hint" "$out"
printf '%s' "$out" | grep -qF "$value" && fail "the secret value was printed" || pass "and the value is not in the output"

echo "== R3: the mode is explicit"
out=$(python3 "$UPDATE" "$P/cursor" --adopt --mode coexist)
printf '%s' "$out" | head -1 | grep -q 'mode: coexist' && pass "--mode coexist is shown in the header" || fail "coexist header" "$out"
printf '%s' "$out" | grep -q '^  adopt ' && fail "coexist plans no move" "$out" || pass "coexist plans no move"
python3 "$UPDATE" "$P/cursor" --adopt --mode merge >/dev/null 2>&1; [ $? -eq 2 ] && pass "an unknown mode is a usage error" || fail "--mode merge accepted"
python3 "$UPDATE" "$P/cursor" --mode coexist >/dev/null 2>&1; [ $? -eq 2 ] && pass "--mode without --adopt is a usage error" || fail "--mode alone accepted"

echo "== I9 router rows: appended once, idempotent by exact text"
R="$TMP/router"; adopt_fixture cursor "$R"
out=$(python3 "$UPDATE" "$R" --adopt)
printf '%s' "$out" | grep -qE '^  router    .ai/AGENTS.md +\+2 row\(s\)$' && pass "the dry run plans +2 router rows" || fail "no router plan item" "$out"
router_content=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$R" <<'ROUTEREOF'
import sys, os
sys.dont_write_bytecode = True
import update, adopt
root = sys.argv[1]
plan = update.Plan(root)
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adopt.plan_adopt(plan, table, "migrate", None, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files())
router_item = next(i for i in plan.items if i["action"] == "router")
print(router_item["content"].decode("utf-8"))
ROUTEREOF
)
printf '%s' "$router_content" | grep -qF '| anything, first (rules adopted from Cursor) | policies/adopted/ |' \
    && pass "the cursorrules row names the directory relative to .ai" || fail "no cursorrules router row" "$router_content"
printf '%s' "$router_content" | grep -qF '| an adopted Cursor file | rules/ |' \
    && pass "a rule with no explicit router text gets a default" || fail "no default router row" "$router_content"
# Simulate an already-applied router edit: write the planned content, then re-plan.
printf '%s\n' "$router_content" > "$R/.ai/AGENTS.md"
out=$(python3 "$UPDATE" "$R" --adopt)
printf '%s' "$out" | grep -q '^  router' && fail "the second run re-planned the router edit" "$out" || pass "a second run adds no router item: idempotent by text"

echo "== R9, R10: no-line-lost passes on every fixture, and a genuinely missing line fails it"
for f in speckit kiro cursor copilot aidlc junie-gemini large-claude-md large-agents-md; do
    F2="$TMP/lines-$f"; adopt_fixture "$f" "$F2"
    out=$(python3 "$UPDATE" "$F2" --adopt)
    printf '%s' "$out" | grep -qE '^  check +no-line-lost +PASS' \
        && pass "$f: check no-line-lost PASS" || fail "$f: no-line-lost did not pass" "$out"
done
out=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$TMP/lines-cursor" <<'LOSTEOF'
import sys, os
sys.dont_write_bytecode = True
import update, adopt
root = sys.argv[1]
plan = update.Plan(root)
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adoption = adopt.plan_adopt(plan, table, "migrate", None, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files())
dest = ".ai/policies/adopted/cursorrules.md"
for i in plan.items:
    if i["target"] == dest:
        i["content"] = b"nothing kept\n"
plan.final[dest] = b"nothing kept\n"
status, lines, missing, missing_n = adopt.check_lines(plan, adoption)
print(status)
print(missing_n)
print(missing[0] if missing else "")
LOSTEOF
)
echo "$out" | sed -n 1p | grep -q '^fail$' && pass "a genuinely lost line fails the check" || fail "check_lines did not fail" "$out"
echo "$out" | sed -n 2p | grep -qE '^[1-9]' && pass "and counts how many" || fail "no missing count" "$out"
echo "$out" | sed -n 3p | grep -q '^.cursorrules:' && pass "and names file:line" || fail "no file:line" "$out"

echo "== R11: a hard-scope stale reference fails no-dangling, the same in warn scope only warns"
D="$TMP/dangling"; adopt_fixture cursor "$D"
printf '\nSee `@.cursorrules` for the legacy rules.\n' >> "$D/.ai/policies/coding.md"; commit "$D"
out=$(python3 "$UPDATE" "$D" --adopt)
printf '%s' "$out" | grep -qE '^  check +no-dangling +FAIL: .ai/policies/coding.md:[0-9]+ -> .cursorrules$' \
    && pass "a hard-scope reference to .cursorrules fails no-dangling" || fail "hard-scope reference not caught" "$out"
W="$TMP/warn-only"; adopt_fixture cursor "$W"
baseline=$(python3 "$UPDATE" "$W" --adopt | grep -oE 'no-dangling +PASS \([0-9]+' | grep -oE '[0-9]+$')
mkdir -p "$W/src"; printf '# Notes\n\nSee `@.cursorrules` for the legacy rules.\n' > "$W/src/README.md"; commit "$W"
out=$(python3 "$UPDATE" "$W" --adopt)
after=$(printf '%s' "$out" | grep -oE 'no-dangling +PASS \([0-9]+' | grep -oE '[0-9]+$')
printf '%s' "$out" | grep -qE '^  check +no-dangling +PASS' && [ "$after" -eq $((baseline + 1)) ] \
    && pass "the same reference in src/README.md adds one warning, not a failure" || fail "warn-scope reference wrongly failed" "$out (baseline=$baseline after=$after)"

echo "== R14: coexist plans only the router edit; no-line-lost is not applicable, no-dangling checks the linked paths exist"
CO="$TMP/coexist"; adopt_fixture cursor "$CO"
out=$(python3 "$UPDATE" "$CO" --adopt --mode coexist)
[ "$(printf '%s' "$out" | grep -c '^  router\|^  adopt\|^  conflict')" -eq 1 ] \
    && pass "coexist plans exactly one write: the router edit" || fail "coexist planned more than the router row" "$out"
printf '%s' "$out" | grep -qE '^  check +no-line-lost +not applicable' && pass "no-line-lost is not applicable in coexist" || fail "coexist ran no-line-lost" "$out"
printf '%s' "$out" | grep -qE '^  check +no-dangling +PASS' && pass "no-dangling passes: every linked path exists" || fail "coexist no-dangling failed" "$out"
# Simulate an already-linked coexist run: write the router content this dry run
# planned, so the .cursorrules link is on record, then take the file away.
router_content=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$CO" <<'COEXROUTEREOF'
import sys
sys.dont_write_bytecode = True
import update, adopt
root = sys.argv[1]
plan = update.Plan(root)
table = adopt.load_table()
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adopt.plan_adopt(plan, table, "coexist", None, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files())
router_item = next(i for i in plan.items if i["action"] == "router")
print(router_item["content"].decode("utf-8"))
COEXROUTEREOF
)
printf '%s\n' "$router_content" > "$CO/.ai/AGENTS.md"
rm "$CO/.cursorrules"; commit "$CO"
out=$(python3 "$UPDATE" "$CO" --adopt --mode coexist)
printf '%s' "$out" | grep -qE '^  check +no-dangling +FAIL' && pass "a missing linked path fails no-dangling in coexist" || fail "missing linked path not caught" "$out"

echo "== I11: --adopt --check prints exactly one of the five lines"
plant_record() {
    local dir="$1" date="$2" sll="$3" sd="$4" srcsha="$5"
    mkdir -p "$dir/.ai/reports/adopt-$date"
    python3 - "$dir" "$date" "$sll" "$sd" "$srcsha" <<'PLANTEOF'
import json, os, sys
root, date, sll, sd, srcsha = sys.argv[1:6]
rec = {"version": 1, "mode": "migrate", "adopted_at": date + "T00:00:00Z", "plugin_schema": 5,
       "tools": {"cursor": {"files": 1}},
       "sources": [{"path": ".cursorrules", "sha": srcsha, "tool": "cursor", "transform": "copy",
                    "dest": ".ai/policies/adopted/cursorrules.md", "dest_sha": "sha256:x", "cleanup": True}],
       "dropped": 0, "ignored": [], "unmapped": [], "original_bytes": 0,
       "checks": {"no_line_lost": {"status": sll, "checked_at": date + "T00:00:00Z"},
                  "no_dangling": {"status": sd, "checked_at": date + "T00:00:00Z"}},
       "cleanup": {"offered": True, "confirmed_by": None, "at": None, "unattended": None, "tty": None, "deleted": []}}
out = os.path.join(root, ".ai", "reports", "adopt-" + date, "adopt.json")
json.dump(rec, open(out, "w"))
PLANTEOF
}
N="$TMP/check-none"; scaffold "$N" claude; commit "$N"
out=$(python3 "$UPDATE" "$N" --adopt --check); rc=$?
[ "$out" = "no foreign structure detected" ] && [ $rc -eq 0 ] && pass "no record, nothing foreign: line 1, exit 0" || fail "line 1 wrong" "$out/$rc"
U="$TMP/check-undetected"; adopt_fixture cursor "$U"
out=$(python3 "$UPDATE" "$U" --adopt --check); rc=$?
printf '%s' "$out" | grep -q '^foreign structure detected: cursor (.*file' && [ $rc -eq 1 ] \
    && pass "no record, foreign structure present: line 3, exit 1" || fail "line 3 wrong" "$out/$rc"
G="$TMP/check-good"; adopt_fixture cursor "$G"
srcsha="sha256:$(sha256sum "$G/.cursorrules" | cut -d' ' -f1)"
plant_record "$G" "2000-01-01" pass pass "$srcsha"
out=$(python3 "$UPDATE" "$G" --adopt --check); rc=$?
printf '%s' "$out" | grep -qE '^adopted 2000-01-01: cursor — up to date; [0-9]+ file\(s\) await cleanup$' && [ $rc -eq 0 ] \
    && pass "a matching record, both checks pass: line 2, exit 0" || fail "line 2 wrong" "$out/$rc"
RG="$TMP/check-regen"; adopt_fixture cursor "$RG"
plant_record "$RG" "2000-01-01" pass pass "sha256:0000000000000000000000000000000000000000000000000000000000000"
out=$(python3 "$UPDATE" "$RG" --adopt --check); rc=$?
printf '%s' "$out" | grep -q '^foreign files regenerated since the adopt of 2000-01-01: .cursorrules' && [ $rc -eq 1 ] \
    && pass "the source sha no longer matches: line 4, exit 1" || fail "line 4 wrong" "$out/$rc"
IC="$TMP/check-incomplete"; adopt_fixture cursor "$IC"
srcsha="sha256:$(sha256sum "$IC/.cursorrules" | cut -d' ' -f1)"
plant_record "$IC" "2000-01-01" fail pass "$srcsha"
out=$(python3 "$UPDATE" "$IC" --adopt --check); rc=$?
printf '%s' "$out" | grep -q '^adoption of 2000-01-01 incomplete: no-line-lost FAIL' && [ $rc -eq 1 ] \
    && pass "a failed check: line 5, exit 1" || fail "line 5 wrong" "$out/$rc"
python3 "$UPDATE" "$G" --check >/dev/null; [ $? -eq 0 ] && pass "the plain --check line is unchanged by any of this (OQ10)" || fail "plain --check disturbed"

echo "== R5: --adopt --apply refuses, exit 5, until the project is ready"
refused() {  # refused <dir> <what>: exit 5, ADOPT_REFUSED on line 1, and nothing written
    local before out rc
    before=$(tree_sha "$1")
    out=$(python3 "$UPDATE" "$1" --adopt --apply); rc=$?
    [ $rc -eq 5 ] && [ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_REFUSED ] && [ "$(tree_sha "$1")" = "$before" ] \
        && pass "$2: refused, exit 5, nothing written" || fail "$2: expected a refusal (rc=$rc)" "$out"
}
NA="$TMP/no-ai"; mkdir -p "$NA"; printf 'Use tabs.\n' > "$NA/.cursorrules"; commit "$NA"
refused "$NA" "no .ai/"
NG="$TMP/no-git"; adopt_fixture cursor "$NG"; rm -rf "$NG/.git"
refused "$NG" "not a git work tree"
DT="$TMP/dirty"; adopt_fixture cursor "$DT"; printf 'wip\n' > "$DT/notes.txt"
refused "$DT" "an untracked file outside the record"
TF="$TMP/task"; adopt_fixture cursor "$TF"; mkdir -p "$TF/.ai/state"
printf '{"task_id":"T-1","current_stage":"plan"}\n' > "$TF/.ai/state/current.json"
refused "$TF" "a task in flight"
BH="$TMP/behind"; adopt_fixture cursor "$BH"; rm "$BH/.ai/policies/security.md"; commit "$BH"
refused "$BH" "the project behind the plugin"
SP="$TMP/split-apply"; adopt_fixture large-claude-md "$SP"
out=$(python3 "$UPDATE" "$SP" --adopt --apply); rc=$?
[ $rc -eq 4 ] && printf '%s' "$out" | head -1 | grep -q '^ADOPT_INCOMPLETE: .*CLAUDE.md: a split needs a proposal' \
    && pass "a split candidate with no proposal exits 4 and writes nothing (R8)" || fail "split apply (rc=$rc)" "$out"

echo "== R6, R15: apply once, keep the originals, and a second run changes nothing"
A="$TMP/applied"; adopt_fixture speckit "$A"
# Spec Kit's .gemini/commands/ makes the project declare Gemini, so the plain
# update is pending first — R5 refuses until it is applied, as a user would.
refused "$A" "Spec Kit's .gemini/ declares a runtime the project has not scaffolded yet"
python3 "$UPDATE" "$A" --apply >/dev/null; commit "$A" "plain update"
chmod 0640 "$A/specs/001-user-auth/spec.md"
head -c 1048577 /dev/zero | tr '\0' 'r' | fold -w 80 > "$A/specs/001-user-auth/research.md"; commit "$A"
out=$(python3 "$UPDATE" "$A" --adopt --apply); rc=$?
[ $rc -eq 0 ] && pass "speckit applies, exit 0" || fail "speckit apply (rc=$rc)" "$out"
REC=$(ls -d "$A"/.ai/reports/adopt-*/)
[ -f "$REC/original/specs/001-user-auth/spec.md" ] && [ "$(stat -c %a "$REC/original/specs/001-user-auth/spec.md")" = 640 ] \
    && pass "the original is kept with its mode" || fail "no original with mode 640"
[ -f "$REC/original/docs/sdlc/constitution.md" ] && pass "the project file this run rewrites (constitution.md) is kept too" || fail "no original of the rewritten constitution"
[ ! -e "$REC/original/specs/001-user-auth/research.md" ] && printf '%s' "$out" | grep -q 'skipped (git has them): specs/001-user-auth/research.md' \
    && pass "a file over 1 MiB is not copied, and says so" || fail "the 1 MiB file was copied or not listed" "$out"
[ "$(jq -r '.original_skipped[0]' "$REC/adopt.json")" = specs/001-user-auth/research.md ] && [ "$(jq '.original_bytes > 0' "$REC/adopt.json")" = true ] \
    && pass "adopt.json records the bytes kept and the file skipped" || fail "original_* not recorded"
[ "$(jq -r '.status' "$REC/adopt.json")" = applied ] && [ "$(jq -r '.checks.no_line_lost.checked_at | length > 0' "$REC/adopt.json")" = true ] \
    && pass "the checks ran on disk and are timestamped (R12)" || fail "adopt.json has no applied status or checked_at"
[ -s "$REC/report.md" ] && [ -f "$REC/dropped.jsonl" ] && [ "$(wc -l < "$REC/dropped.jsonl")" -gt 0 ] \
    && pass "report.md and dropped.jsonl are written" || fail "record files missing"
[ ! -e "$REC/migration.json" ] && pass "no migration.json under adopt-*" || fail "adopt wrote migration.json"
python3 "$UPDATE" "$A" --check >/dev/null && pass "plain --check exits 0 right after the apply" || fail "the project is behind after adopt"
commit "$A" adopted
before=$(tree_sha "$A")
out=$(python3 "$UPDATE" "$A" --adopt)
printf '%s' "$out" | grep -q '^0 automatic' && [ "$(tree_sha "$A")" = "$before" ] \
    && pass "a second --adopt plans nothing and writes nothing" || fail "not idempotent" "$out"
out=$(python3 "$UPDATE" "$A")
printf '%s' "$out" | grep -q '^  conflict  .ai/AGENTS.md' && fail "the router rows became a conflict for the plain update" "$out" \
    || pass "the plain dry run keeps the router rows as project edits"
printf 'extra\n' >> "$A/specs/001-user-auth/spec.md"; commit "$A" regen
out=$(python3 "$UPDATE" "$A" --adopt --check); rc=$?
printf '%s' "$out" | grep -q '^foreign files regenerated since the adopt of .*specs/001-user-auth/spec.md' && [ $rc -eq 1 ] \
    && pass "a changed source makes --adopt --check say regenerated (R16)" || fail "no regenerated line (rc=$rc)" "$out"
printf "%s" "$(python3 "$UPDATE" "$A")" | grep -q '^  hint      foreign files regenerated' \
    && pass "and the plain dry run carries it as a hint (D5)" || fail "no D5 hint for regeneration"
printf "%s" "$(python3 "$UPDATE" "$P/cursor")" | grep -q '^  hint      foreign structure detected: cursor' \
    && pass "an un-adopted foreign structure is a hint in the plain dry run (D5)" || fail "no D5 hint for detection"

echo "== R15: an interrupted apply resumes, and only its own writes count as allowed dirt"
for phase in 1 2; do
    I="$TMP/interrupt-$phase"; adopt_fixture cursor "$I"
    out=$(CLAUDE_AGENTIC_TEST=1 ADOPT_STOP_AFTER=$phase python3 "$UPDATE" "$I" --adopt --apply); rc=$?
    [ $rc -eq 3 ] && [ "$(jq -r '.status' "$I"/.ai/reports/adopt-*/adopt.json)" = partial ] \
        && pass "stopped after phase $phase: exit 3, the record says partial" || fail "phase $phase stop (rc=$rc)" "$out"
    out=$(python3 "$UPDATE" "$I" --adopt --check)
    printf '%s' "$out" | grep -q 'incomplete: the apply was interrupted' \
        && pass "--adopt --check calls it incomplete" || fail "no incomplete line after phase $phase" "$out"
    out=$(python3 "$UPDATE" "$I" --adopt --apply); rc=$?
    [ $rc -eq 0 ] && [ "$(jq -r '.status' "$I"/.ai/reports/adopt-*/adopt.json)" = applied ] \
        && printf '%s' "$out" | grep -qE '^  check +no-line-lost +PASS' \
        && pass "the re-run completes past the clean-tree gate and passes both checks" || fail "resume after phase $phase (rc=$rc)" "$out"
done
I="$TMP/interrupt-dirty"; adopt_fixture cursor "$I"
CLAUDE_AGENTIC_TEST=1 ADOPT_STOP_AFTER=1 python3 "$UPDATE" "$I" --adopt --apply >/dev/null
printf 'wip\n' > "$I/notes.txt"
refused "$I" "a dirty path that is not a planned destination, while resuming"
out=$(ADOPT_STOP_AFTER=1 python3 "$UPDATE" "$TMP/check-good" --adopt --apply 2>&1)
[ -n "$(ls "$TMP"/check-good/.ai/reports/ 2>/dev/null)" ] && pass "without CLAUDE_AGENTIC_TEST the stop switch is ignored" || fail "stop switch honoured outside tests"

echo "== R14: coexist --apply writes only the router rows and the record"
CA="$TMP/coexist-apply"; adopt_fixture cursor "$CA"
out=$(python3 "$UPDATE" "$CA" --adopt --apply --mode coexist); rc=$?
changed=$(git -C "$CA" status --porcelain --untracked-files=all | awk '{print $2}' | grep -v '^.ai/reports/adopt-' | sort | tr '\n' ' ')
[ $rc -eq 0 ] && [ "$changed" = ".ai/AGENTS.md " ] && pass "coexist changed only .ai/AGENTS.md (and its record)" || fail "coexist apply (rc=$rc) changed: $changed" "$out"
grep -q '(kept in place; its globs are not applied by this runtime)' "$CA/.ai/AGENTS.md" && pass "its rows say the files are kept in place" || fail "no kept-in-place rows"

summary "project-adopt"
