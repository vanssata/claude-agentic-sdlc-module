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
python3 "$UPDATE" "$S" --adopt | grep -q '^  split?    AGENTS.md' && pass "the same for AGENTS.md" || fail "no split? for a grown AGENTS.md"
out=$(python3 "$UPDATE" "$P/junie-gemini" --adopt)
printf '%s' "$out" | grep -qE '^  detect +gemini +GEMINI.md' && printf '%s' "$out" | grep -qE '^  detect +junie ' \
    && pass "GEMINI.md and .junie/guidelines.md without the block are foreign" || fail "junie/gemini not detected" "$out"
printf '%s' "$out" | grep -q 'split?' && fail "small foreign instruction files are not split candidates" "$out" || pass "and at this size neither is a split candidate"
python3 "$UPDATE" "$P/large-claude-md" --adopt | grep -q '^  split?    CLAUDE.md' && pass "large-claude-md lists split?" || fail "large-claude-md: no split?"
python3 "$UPDATE" "$P/large-agents-md" --adopt | grep -q '^  split?    AGENTS.md' && pass "large-agents-md lists split?" || fail "large-agents-md: no split?"

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

summary "project-adopt"
