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
    [ -e "$1/.git" ] || { git -C "$1" init -q; git -C "$1" config user.email t@example.com; git -C "$1" config user.name t; }
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

# pty <cmd...>: the command with a terminal on stdin (util-linux script), stdout
# and stderr merged, \r stripped; exit status is the command's. The checkout path
# has a space, hence %q; SHELL is pinned because script -c runs it.
pty() { SHELL=/bin/bash script -qec "$(printf '%q ' "$@")" /dev/null </dev/null | tr -d '\r'; return "${PIPESTATUS[0]}"; }
# NOMARK: env arguments that clear every agent-session marker and AI_UNATTENDED,
# so a case sets exactly the markers it names (the suite runs inside Claude Code and in CI).
NOMARK=(-u CLAUDECODE -u CODEX_THREAD_ID -u CODEX_SESSION_ID -u CODEX_CI -u CODEX_SANDBOX -u CODEX_SANDBOX_NETWORK_DISABLED -u CODEX_VERSION -u AI_UNATTENDED)
HAS_PTY=0; [ "$(pty python3 -c 'import os; print(os.isatty(0))' 2>/dev/null)" = True ] && HAS_PTY=1

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
        grep -qE "^  detect +$f " <<<"$out" && pass "$f: one detect line" || fail "$f: no detect line" "$out"
        grep -qE '^  adopt ' <<<"$out" && pass "$f: at least one source planned" || fail "$f: nothing planned" "$out"
        head -1 <<<"$out" | grep -q 'mode: migrate' && pass "$f: migrate is the default mode (R3)" || fail "$f: no mode in the header" "$out"
        [ "$(tree_sha "$P")" = "$before" ] && pass "$f: the tree is byte-identical after the dry run" || fail "$f: the dry run wrote something"
    done
done
P="$TMP/plain"
out=$(python3 "$UPDATE" "$P/speckit" --adopt)
grep -q '^  adopt     .specify/memory/constitution.md -> docs/sdlc/constitution.md .*append-section' <<<"$out" \
    && pass "the Spec Kit constitution is appended to ours, not a conflict" || fail "constitution not planned as append-section" "$out"
grep -q '^  dropped   .claude/skills/speckit-plan/SKILL.md' <<<"$out" \
    && pass "a current Spec Kit skill is dropped" || fail "the speckit skill layout is not covered" "$out"
out=$(python3 "$UPDATE" "$P/cursor" --adopt)
grep -q '.cursor/rules/frontend/react.mdc -> .ai/rules/frontend-react.md .*dirs: \[src/components, src/hooks\]' <<<"$out" \
    && pass "a glob-scoped Cursor rule becomes a .ai/rules/ rule with dirs" || fail "react.mdc not a scoped rule" "$out"
grep -q '^  ignored   .cursor/mcp.json' <<<"$out" && pass "Cursor configuration is ignored, not adopted" || fail "mcp.json not ignored" "$out"
out=$(python3 "$UPDATE" "$P/kiro" --adopt)
grep -qE '^  adopt     .kiro/steering/tech.md -> .ai/policies/adopted/always.md .*rule: always' <<<"$out" \
    && pass "a Kiro steering file without frontmatter is always included (A4)" || fail "tech.md not always" "$out"
grep -q '^  ignored   .kiro/steering/aws-aidlc-rules/' <<<"$out" \
    && pass "AI-DLC installed for Kiro stays out of the steering row" || fail "aws-aidlc-rules not ignored" "$out"

echo "== a nested worktree is not this project's: its foreign files are never detected"
N="$TMP/nested-wt"; scaffold "$N" claude; commit "$N"
git -C "$N" worktree add -q -b wt "$N/.claude/worktrees/wt" 2>/dev/null || fail "git worktree add failed: the case below would prove nothing"
[ -f "$N/.claude/worktrees/wt/.git" ] && pass "the fixture is a real worktree: its .git is a file" || fail "no worktree .git file"
mkdir -p "$N/.claude/worktrees/wt/.cursor/rules"
printf '# theirs\nuse tabs\n' > "$N/.claude/worktrees/wt/.cursorrules"
printf -- '---\nalwaysApply: true\n---\nuse tabs\n' > "$N/.claude/worktrees/wt/.cursor/rules/x.mdc"
commit "$N/.claude/worktrees/wt"
out=$(python3 "$UPDATE" "$N" --adopt 2>&1)
grep -qE 'ADOPT_INCOMPLETE|^  unmapped ' <<<"$out" \
    && fail "the adopt stops on a file of the nested worktree" "$out" || pass "no ADOPT_INCOMPLETE and no unmapped row"
grep -q 'worktrees/wt' <<<"$out" && fail "the adopt names a file in the nested worktree" "$out" || pass "and no file of the nested worktree is named"

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
    [ $rc -eq 0 ] && grep -q '^  no foreign structure detected$' <<<"$out" \
        && pass "a fresh $rt scaffold is not foreign" || fail "a fresh $rt scaffold was detected (rc=$rc)" "$out"
done
S="$TMP/fresh-claude"; head -c 200 /dev/zero | tr '\0' 'n' >> "$S/CLAUDE.md"; printf '\n' >> "$S/CLAUDE.md"
out=$(python3 "$UPDATE" "$S" --adopt); rc=$?
grep -q '^  split?    CLAUDE.md' <<<"$out" && ! grep -q unmapped <<<"$out" \
    && pass "the scaffold plus 200 B of notes is a split candidate, not unmapped" || fail "no split? for a grown CLAUDE.md (rc=$rc)" "$out"
[ $rc -eq 4 ] && head -1 <<<"$out" | grep -q '^ADOPT_INCOMPLETE: .*a split needs a proposal' \
    && pass "I1: the dry run exits 4 while a split awaits its proposal, as --apply would" || fail "split? dry run exit (rc=$rc)" "$out"
S="$TMP/fresh-codex"; head -c 200 /dev/zero | tr '\0' 'n' >> "$S/AGENTS.md"; printf '\n' >> "$S/AGENTS.md"
grep -q '^  split?    AGENTS.md' <<<"$(python3 "$UPDATE" "$S" --adopt)" && pass "the same for AGENTS.md" || fail "no split? for a grown AGENTS.md"
out=$(python3 "$UPDATE" "$P/junie-gemini" --adopt)
grep -qE '^  detect +gemini +GEMINI.md' <<<"$out" && grep -qE '^  detect +junie ' <<<"$out" \
    && pass "GEMINI.md and .junie/guidelines.md without the block are foreign" || fail "junie/gemini not detected" "$out"
grep -q 'split?' <<<"$out" && fail "small foreign instruction files are not split candidates" "$out" || pass "and at this size neither is a split candidate"
grep -q '^  split?    CLAUDE.md' <<<"$(python3 "$UPDATE" "$P/large-claude-md" --adopt)" && pass "large-claude-md lists split?" || fail "large-claude-md: no split?"
grep -q '^  split?    AGENTS.md' <<<"$(python3 "$UPDATE" "$P/large-agents-md" --adopt)" && pass "large-agents-md lists split?" || fail "large-agents-md: no split?"

echo "== R4: what no row maps fails loudly, and a human's decision settles it"
K="$TMP/kiro-hooks"; adopt_fixture kiro "$K"
mkdir -p "$K/.kiro/hooks"; printf '{"hooks": []}\n' > "$K/.kiro/hooks/lint-on-save.json"
out=$(python3 "$UPDATE" "$K" --adopt); rc=$?
[ $rc -eq 4 ] && pass "an unmapped Kiro hook exits 4" || fail "expected exit 4, got $rc" "$out"
[ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_INCOMPLETE ] && pass "ADOPT_INCOMPLETE on the first line" || fail "no token on line 1" "$out"
grep -q '^  unmapped  .kiro/hooks/lint-on-save.json .*decisions.json' <<<"$out" && pass "and it names the file and where to decide" || fail "no unmapped line" "$out"
mkdir -p "$K/.ai/reports/adopt-2000-01-01"
printf '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"drop","why":"Kiro agent hook; no equivalent here"}}}\n' \
    > "$K/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$K" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q '^  dropped   .kiro/hooks/lint-on-save.json .*no equivalent here' <<<"$out" \
    && pass "a decision in an older adopt-* directory settles it" || fail "decision not honoured (rc=$rc)" "$out"
N="$TMP/nested"; scaffold "$N" claude; mkdir -p "$N/packages/x/.cursor/rules"
printf -- '---\nalwaysApply: true\n---\n\n- Use pnpm.\n' > "$N/packages/x/.cursor/rules/a.mdc"
out=$(python3 "$UPDATE" "$N" --adopt); rc=$?
[ $rc -eq 4 ] && grep -q '^  unmapped  packages/x/.cursor/rules/a.mdc .*below the root' <<<"$out" \
    && pass "a nested .cursor/rules/ is unmapped, exit 4" || fail "nested signature not unmapped (rc=$rc)" "$out"
I="$TMP/ignore-only"; scaffold "$I" claude; mkdir -p "$I/.kiro/settings"; printf '{}\n' > "$I/.kiro/settings/mcp.json"
out=$(python3 "$UPDATE" "$I" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q '^  ignored   .kiro/settings/mcp.json' <<<"$out" && grep -q '^0 automatic' <<<"$out" \
    && pass "a tree with only ignored files prints them and 0 automatic" || fail "ignore-only tree (rc=$rc)" "$out"

echo "== R18, re-review C: rows stay inside their tool's roots; a file under two tools goes to the one that maps it"
X="$TMP/speckit-app"; adopt_fixture speckit "$X"; mkdir -p "$X/src/lib"; printf 'SPECKIT = 1\n' > "$X/src/lib/speckit_x.py"
out=$(python3 "$UPDATE" "$X" --adopt)
grep -q 'src/lib/speckit_x.py' <<<"$out" && fail "application code matched a Spec Kit row" "$out" || pass "src/lib/speckit_x.py is neither a source nor dropped"
C="$TMP/speckit-cursor"; adopt_fixture cursor "$C"
mkdir -p "$C/.specify/memory" "$C/.cursor/commands" "$C/.cursor/skills/speckit-plan"
printf '# Constitution\n\n### I. Tests first\n' > "$C/.specify/memory/constitution.md"
printf 'Run the plan script.\n' > "$C/.cursor/commands/speckit.plan.md"
printf -- '---\nname: speckit-plan\n---\n\nPlan.\n' > "$C/.cursor/skills/speckit-plan/SKILL.md"
out=$(python3 "$UPDATE" "$C" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q '^  dropped   .cursor/commands/speckit.plan.md .*\[speckit\]' <<<"$out" && ! grep -q unmapped <<<"$out" \
    && pass "Spec Kit's .cursor/commands/ file is dropped by speckit, nothing unmapped" || fail "speckit+cursor overlap (rc=$rc)" "$out"

echo "== R23: a secret-looking line is named by file:line, its value never printed"
Z="$TMP/secret"; adopt_fixture cursor "$Z"
value="sk-$(date +%s)abcdefgh"
printf 'API_KEY=%s\n' "$value" >> "$Z/.cursorrules"; commit "$Z"
out=$(python3 "$UPDATE" "$Z" --adopt)
grep -q '^  hint      .cursorrules:4 .*looks like a secret' <<<"$out" && pass "the hint names .cursorrules:4" || fail "no secret hint" "$out"
grep -qF "$value" <<<"$out" && fail "the secret value was printed" || pass "and the value is not in the output"

echo "== R3: the mode is explicit"
out=$(python3 "$UPDATE" "$P/cursor" --adopt --mode coexist)
head -1 <<<"$out" | grep -q 'mode: coexist' && pass "--mode coexist is shown in the header" || fail "coexist header" "$out"
grep -q '^  adopt ' <<<"$out" && fail "coexist plans no move" "$out" || pass "coexist plans no move"
python3 "$UPDATE" "$P/cursor" --adopt --mode merge >/dev/null 2>&1; [ $? -eq 2 ] && pass "an unknown mode is a usage error" || fail "--mode merge accepted"
python3 "$UPDATE" "$P/cursor" --mode coexist >/dev/null 2>&1; [ $? -eq 2 ] && pass "--mode without --adopt is a usage error" || fail "--mode alone accepted"

echo "== I9 router rows: appended once, idempotent by exact text"
R="$TMP/router"; adopt_fixture cursor "$R"
out=$(python3 "$UPDATE" "$R" --adopt)
# A5: cursorrules (policies/adopted/), the path-scoped rule (rules/), and one row per on-demand
# rule under policies/adopted/ (testing.mdc, typescript.mdc); the always rule has no row (A4).
grep -qE '^  router    .ai/AGENTS.md +\+4 row\(s\)$' <<<"$out" && pass "the dry run plans +4 router rows" || fail "no router plan item" "$out"
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
grep -qF '| anything, first (rules adopted from Cursor) | policies/adopted/ |' <<<"$router_content" \
    && pass "the cursorrules row names the directory relative to .ai" || fail "no cursorrules router row" "$router_content"
grep -qF '| an adopted Cursor file | rules/ |' <<<"$router_content" \
    && pass "a rule with no explicit router text gets a default" || fail "no default router row" "$router_content"
# Simulate an already-applied router edit: write the planned content, then re-plan.
printf '%s\n' "$router_content" > "$R/.ai/AGENTS.md"
out=$(python3 "$UPDATE" "$R" --adopt)
grep -q '^  router' <<<"$out" && fail "the second run re-planned the router edit" "$out" || pass "a second run adds no router item: idempotent by text"

echo "== R9, R10: no-line-lost passes on every fixture, and a genuinely missing line fails it"
for f in speckit kiro cursor copilot aidlc junie-gemini large-claude-md large-agents-md; do
    F2="$TMP/lines-$f"; adopt_fixture "$f" "$F2"
    out=$(python3 "$UPDATE" "$F2" --adopt)
    grep -qE '^  check +no-line-lost +PASS' <<<"$out" \
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

echo "== A1, A2: the current Spec Kit machinery is mapped, and a glob decision settles a whole directory"
A1="$TMP/a1"; adopt_fixture speckit "$A1"
out=$(python3 "$UPDATE" "$A1" --adopt)
grep -q 'unmapped' <<<"$out" && fail "the current Spec Kit layout left files unmapped" "$out" || pass "nothing unmapped in the current Spec Kit layout"
for f in extensions.yml init-options.json integrations/claude.manifest.json presets/x/preset.md workflows/x.md; do
    grep -qE "^  dropped   .specify/$f .*Spec Kit tool machinery" <<<"$out" \
        && pass ".specify/$f is dropped as tool machinery" || fail ".specify/$f not dropped as machinery" "$out"
done
grep -qE '^  dropped   .specify/integrations/speckit.manifest.json .*Spec Kit tool machinery' <<<"$out" \
    && pass "speckit.manifest.json is machinery, not an agent command by a filename coincidence" || fail "speckit.manifest.json reason" "$out"
grep -qE '^  adopt     specs/001-user-auth/checklists/requirements.md -> docs/sdlc/specs/001-user-auth-checklists-requirements.md' <<<"$out" \
    && pass "a /speckit.checklist file is copied under docs/sdlc/specs/" || fail "checklist not copied" "$out"
mkdir -p "$A1/specs/001-user-auth/contracts" "$A1/specs/002-cart/contracts"
printf 'openapi: 3.1.0\n' > "$A1/specs/001-user-auth/contracts/api.yaml"
printf 'openapi: 3.1.0\n' > "$A1/specs/002-cart/contracts/api.yaml"; commit "$A1"
mkdir -p "$A1/.ai/reports/adopt-2000-01-01"
printf '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"drop","why":"contracts live in the API repo"}}}\n' \
    > "$A1/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$A1" --adopt)
[ "$(printf '%s' "$out" | grep -c '^  dropped   specs/00[12]-[a-z-]*/contracts/api.yaml .*API repo')" -eq 2 ] && ! grep -q unmapped <<<"$out" \
    && pass "one glob key settles both contracts files" || fail "glob decision not applied" "$out"
printf '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"drop","why":"glob"},"specs/002-cart/contracts/api.yaml":{"action":"ignore","why":"exact"}}}\n' \
    > "$A1/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$A1" --adopt)
grep -qE '^  ignored   specs/002-cart/contracts/api.yaml .*exact' <<<"$out" \
    && grep -qE '^  dropped   specs/001-user-auth/contracts/api.yaml .*glob' <<<"$out" \
    && pass "an exact key wins over a glob" || fail "exact vs glob" "$out"
printf '{"version":1,"unmapped":{"specs/*/contracts/**":{"action":"copy","dest":"docs/sdlc/specs/contracts.md"}}}\n' \
    > "$A1/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$A1" --adopt); rc=$?
[ $rc -eq 4 ] && grep -qE '^  unmapped  specs/001-user-auth/contracts/api.yaml .*a glob decision cannot copy' <<<"$out" \
    && pass "a glob copy is refused: one destination cannot take many files" || fail "glob copy accepted (rc=$rc)" "$out"

echo "== A3: references inside migrated text are rewritten, or named as warnings"
A3="$TMP/a3"; adopt_fixture speckit "$A3"
python3 "$UPDATE" "$A3" --apply >/dev/null; commit "$A3" "plain update"
out=$(python3 "$UPDATE" "$A3" --adopt); rc=$?
[ $rc -eq 0 ] && grep -qE '^  check +no-dangling +PASS' <<<"$out" \
    && pass "a real-shaped Spec Kit tree passes no-dangling" || fail "speckit no-dangling (rc=$rc)" "$out"
grep -qE 'no-dangling +PASS .*docs/sdlc/plans/001-user-auth-tasks.md:[0-9]+ -> specs/' <<<"$out" \
    && pass "the directory reference in tasks.md is a named warning" || fail "tasks.md directory reference not named" "$out"
grep -qE 'no-dangling +PASS .*docs/sdlc/constitution.md:[0-9]+ -> .specify/' <<<"$out" \
    && pass "the Sync Impact Report's .specify/templates/ is a named warning" || fail "constitution comment not named" "$out"
out=$(python3 "$UPDATE" "$A3" --adopt --apply); rc=$?
[ $rc -eq 0 ] && grep -qF 'Feature specification from `docs/sdlc/specs/001-user-auth.md`' "$A3/docs/sdlc/plans/001-user-auth.md" \
    && pass "plan.md's spec path is rewritten to its new home" || fail "path not rewritten (rc=$rc)" "$out$(cat "$A3/docs/sdlc/plans/001-user-auth.md")"
grep -q '"reason": "rewritten: path reference"' "$A3"/.ai/reports/adopt-*/dropped.jsonl \
    && pass "the rewrite is logged in dropped.jsonl" || fail "no rewrite record"
grep -qE '^  check +no-line-lost +PASS' <<<"$out" && pass "no-line-lost still holds after the rewrite" || fail "no-line-lost after rewrite" "$out"
commit "$A3" adopted
out=$(python3 "$UPDATE" "$A3" --adopt)
grep -q '^0 automatic, 0 conflict' <<<"$out" && pass "a second --adopt after the rewrite plans nothing (R15)" || fail "rewrite not idempotent" "$out"
[ "$(printf '%s' "$out" | grep -oE 'docs/sdlc/constitution.md:[0-9]+ -> .specify/' | wc -l)" -eq 2 ] \
    && pass "both Sync Impact Report lines are named, not only the first in the file" || fail "one warning per file" "$out"
printf 'Our own note: the old spec is `specs/001-user-auth/spec.md`.\n' >> "$A3/docs/sdlc/plans/001-user-auth-tasks.md"; commit "$A3" "own note"
out=$(python3 "$UPDATE" "$A3" --adopt); rc=$?
[ $rc -eq 4 ] && grep -qE 'no-dangling +FAIL: docs/sdlc/plans/001-user-auth-tasks.md:[0-9]+ -> specs/' <<<"$out" \
    && pass "a warned adopted line first in a file does not hide the project's own stale line below it" || fail "own line masked (rc=$rc)" "$out"
H3="$TMP/a3-own"; adopt_fixture speckit "$H3"
printf '\nOur own note: see `specs/001-user-auth/spec.md`.\n' >> "$H3/.ai/policies/coding.md"; commit "$H3"
out=$(python3 "$UPDATE" "$H3" --adopt); rc=$?
[ $rc -eq 4 ] && grep -qE 'no-dangling +FAIL: .ai/policies/coding.md:[0-9]+ -> specs/' <<<"$out" \
    && pass "the project's own stale reference still fails hard" || fail "own reference softened (rc=$rc)" "$out"

echo "== A4: an always rule goes into always.md, and every instruction file points at it"
A4="$TMP/a4"; adopt_fixture cursor "$A4"
bash "$PLUGIN_ROOT/hooks/project-scaffold.sh" "$A4" --runtime codex >/dev/null
bash "$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh" "$A4" --runtime claude,codex >/dev/null
python3 "$UPDATE" "$A4" --apply >/dev/null; commit "$A4" "two runtimes"
out=$(python3 "$UPDATE" "$A4" --adopt --apply); rc=$?
AL="$A4/.ai/policies/adopted/always.md"
grep -q '^## Adopted from Cursor (general.mdc)$' "$AL" && grep -q 'Use pnpm, never npm or yarn.' "$AL" \
    && pass "the alwaysApply rule is in always.md" || fail "always rule not in always.md (rc=$rc)" "$out"
for f in CLAUDE.md AGENTS.md; do
    grep -qxF 'Read `.ai/policies/adopted/always.md` first.' "$A4/$f" \
        && ! grep -q 'Use pnpm, never npm or yarn.' "$A4/$f" \
        && pass "$f points at it, and carries none of its text" || fail "no pointer in $f (rc=$rc)" "$out"
done
grep -q 'split?' <<<"$out" && fail "the pointer took an instruction file over its budget" "$out" || pass "no instruction file goes over its budget"
[ ! -e "$A4/.ai/policies/adopted/cursor-general.md" ] && pass "and no cursor-general.md of its own" || fail "always rule also written as a policy"
grep -qE '^  check +no-line-lost +PASS' <<<"$out" && pass "no-line-lost holds" || fail "no-line-lost with an always rule" "$out"
commit "$A4" adopted
out=$(python3 "$UPDATE" "$A4" --adopt)
grep -q '^0 automatic' <<<"$out" && [ "$(grep -c '^## Adopted from Cursor (general.mdc)$' "$AL")" -eq 1 ] \
    && [ "$(grep -cxF 'Read `.ai/policies/adopted/always.md` first.' "$A4/CLAUDE.md")" -eq 1 ] \
    && pass "a second run appends nothing" || fail "always rule appended twice" "$out"
B4="$TMP/a4-budget"; adopt_fixture cursor "$B4"
{ printf -- '---\ndescription: Everything\nalwaysApply: true\n---\n\n'; for i in $(seq 1 400); do printf -- '- Convention number %d applies to every change in this repository.\n' "$i"; done; } \
    > "$B4/.cursor/rules/big.mdc"; commit "$B4"
out=$(python3 "$UPDATE" "$B4" --adopt --apply); rc=$?
[ $rc -eq 0 ] && ! grep -q 'split?' <<<"$out" && grep -q 'Convention number 400 ' "$B4/.ai/policies/adopted/always.md" \
    && pass "a 25 KB always rule does not touch the instruction file's budget" || fail "large always rule (rc=$rc)" "$out"
# M-new-2: --tool names cursor only, yet CLAUDE.md gets the pointer, so its budget is checked too.
B5="$TMP/a4-budget-tool"; adopt_fixture cursor "$B5"
python3 "$UPDATE" "$B5" --apply >/dev/null
size=$(wc -c < "$B5/CLAUDE.md"); { printf '\n'; head -c $((2048 - 20 - size - 1)) /dev/zero | tr '\0' 'x'; } >> "$B5/CLAUDE.md"
commit "$B5" "CLAUDE.md 20 B under the skeleton budget"
out=$(python3 "$UPDATE" "$B5" --adopt --tool cursor); rc=$?
[ $rc -eq 4 ] && grep -qE 'split\?.*CLAUDE.md|CLAUDE.md.*split\?' <<<"$out" \
    && pass "--tool cursor: the pointer that takes CLAUDE.md over its budget makes it a split?" || fail "pointer unchecked under --tool (rc=$rc, $(wc -c < "$B5/CLAUDE.md") B)" "$out"

echo "== A5: router rows carry a trigger; coexist has one row per directory"
A5="$TMP/a5"; adopt_fixture cursor "$A5"
rows=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$A5" <<'A5EOF'
import sys
sys.dont_write_bytecode = True
import update, adopt
plan = update.Plan(sys.argv[1])
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adopt.plan_adopt(plan, adopt.load_table(), "migrate", None, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files())
print(next(i for i in plan.items if i["action"] == "router")["content"].decode("utf-8"))
A5EOF
)
grep -qF '| How to write and run tests; apply when adding or changing tests | policies/adopted/cursor-testing.md |' <<<"$rows" \
    && pass "an on-demand rule's row is triggered by its description and names its file" || fail "no description row" "$rows"
grep -qF '| TypeScript conventions | policies/adopted/cursor-typescript.md |' <<<"$rows" \
    && pass "the glob-only rule gets its own row too" || fail "no typescript row" "$rows"
C5="$TMP/a5-coexist"; adopt_fixture speckit "$C5"
out=$(python3 "$UPDATE" "$C5" --adopt --mode coexist)
n=$(printf '%s' "$out" | grep -oE '^  router +.ai/AGENTS.md +\+[0-9]+' | grep -oE '[0-9]+$')
dirs=$(cd "$C5" && git ls-files .specify specs .claude .github .gemini | xargs -n1 dirname | sort -u | wc -l)
[ -n "$n" ] && [ "$n" -le "$dirs" ] && pass "coexist adds $n row(s) for $dirs directories, not one per file" || fail "coexist rows (n=$n dirs=$dirs)" "$out"
rows=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$C5" <<'C5EOF'
import sys
sys.dont_write_bytecode = True
import update, adopt
plan = update.Plan(sys.argv[1])
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
adopt.plan_adopt(plan, adopt.load_table(), "coexist", None, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files())
print(next(i for i in plan.items if i["action"] == "router")["content"].decode("utf-8"))
C5EOF
)
printf '%s' "$rows" | grep -F 'specs/001-user-auth/' | grep -q 'globs' && fail "a spec row carries the globs suffix" "$rows" || pass "no globs suffix on a spec row"
C6="$TMP/a5-coexist-cursor"; adopt_fixture cursor "$C6"
rows=$(python3 "$UPDATE" "$C6" --adopt --mode coexist --diff)
printf '%s' "$rows" | grep -E '^\+\|.*\.cursor/rules/' | grep -q 'its globs are not applied' \
    && pass "the Cursor rules row keeps the globs suffix" || fail "cursor coexist suffix" "$rows"

echo "== STRONG review of package B: what a later pass over the same files must keep"
# B1: a reference to an always rule goes where the rule really went.
V1="$TMP/rv-always-ref"; adopt_fixture cursor "$V1"
printf 'See `.cursor/rules/general.mdc` for the conventions.\n' >> "$V1/.cursorrules"; commit "$V1"
out=$(python3 "$UPDATE" "$V1" --adopt --apply); rc=$?
[ $rc -eq 0 ] && grep -qF 'See `.ai/policies/adopted/always.md` for the conventions.' "$V1/.ai/policies/adopted/cursorrules.md" \
    && pass "a reference to an always rule is rewritten to always.md, a file that exists" || fail "always-rule reference (rc=$rc)" "$out$(grep -F conventions "$V1/.ai/policies/adopted/cursorrules.md")"
grep -qx '_Project-wide conventions_' "$V1/.ai/policies/adopted/always.md" \
    && pass "the always rule's description is kept above its text" || fail "always description dropped"
# B2: the pointer survives a split and is paid for out of the budget.
V2="$TMP/rv-pointer-split"; adopt_fixture cursor "$V2"
head -c 120 /dev/zero | tr '\0' 'n' >> "$V2/CLAUDE.md"; printf '\n' >> "$V2/CLAUDE.md"; commit "$V2"
out=$(python3 "$UPDATE" "$V2" --adopt); rc=$?
[ $rc -eq 4 ] && grep -q '^  split?    CLAUDE.md' <<<"$out" \
    && pass "a file the pointer would take over the budget is a split? candidate" || fail "pointer not counted (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$V2" --adopt --apply --split fallback); rc=$?
[ $rc -eq 0 ] && grep -qxF 'Read `.ai/policies/adopted/always.md` first.' "$V2/CLAUDE.md" \
    && ! grep -qF 'always.md' "$V2/.ai/policies/adopted/claude-md.md" \
    && pass "--split fallback keeps the pointer in CLAUDE.md and moves only the project's lines" || fail "pointer evicted by the split (rc=$rc)" "$out"
commit "$V2" adopted
out=$(python3 "$UPDATE" "$V2" --adopt)
grep -q '^0 automatic' <<<"$out" && pass "and the next --adopt plans nothing (R15)" || fail "pointer re-planned after a split" "$out"
head -c 1000 /dev/zero | tr '\0' 'm' >> "$V2/CLAUDE.md"; printf '\n' >> "$V2/CLAUDE.md"; commit "$V2" "the file grows again"
out=$(python3 "$UPDATE" "$V2" --adopt --apply --split fallback); rc=$?
[ $rc -eq 0 ] && grep -q 'CLAUDE.md -> CLAUDE.md .*split (fallback)' <<<"$out" \
    && grep -qxF 'Read `.ai/policies/adopted/always.md` first.' "$V2/CLAUDE.md" \
    && ! grep -qF 'always.md' "$V2"/.ai/policies/adopted/claude-md*.md \
    && pass "a later split of a file already carrying the pointer keeps it, and copies it nowhere" || fail "pointer moved by a later split (rc=$rc)" "$out"
# B3: two always rules with one basename.
V3="$TMP/rv-same-name"; adopt_fixture cursor "$V3"; mkdir -p "$V3/.cursor/rules/a" "$V3/.cursor/rules/b"
printf -- '---\nalwaysApply: true\n---\n\n- Rule from a.\n' > "$V3/.cursor/rules/a/index.mdc"
printf -- '---\nalwaysApply: true\n---\n\n- Rule from b.\n' > "$V3/.cursor/rules/b/index.mdc"; commit "$V3"
out=$(python3 "$UPDATE" "$V3" --adopt --apply); rc=$?
AL3="$V3/.ai/policies/adopted/always.md"
[ $rc -eq 0 ] && grep -qx '## Adopted from Cursor (a/index.mdc)' "$AL3" && grep -qx '## Adopted from Cursor (b/index.mdc)' "$AL3" \
    && grep -q 'Rule from a.' "$AL3" && grep -q 'Rule from b.' "$AL3" \
    && pass "two always rules named index.mdc keep a heading and a body each" || fail "same-basename always rules (rc=$rc)" "$out"
# B4: a foreign heading that names a path is the tool's wording too.
V4="$TMP/rv-heading"; adopt_fixture speckit "$V4"
printf '\n## Layout under `specs/001-user-auth/`\n' >> "$V4/specs/001-user-auth/plan.md"; commit "$V4"
out=$(python3 "$UPDATE" "$V4" --adopt); rc=$?
[ $rc -eq 0 ] && grep -qE 'no-dangling +PASS .*docs/sdlc/plans/001-user-auth.md:[0-9]+ -> specs/' <<<"$out" \
    && pass "a foreign heading with a directory path is a named warning" || fail "foreign heading failed hard (rc=$rc)" "$out"
# B5: a later run moves a file an earlier-adopted document already named.
V5="$TMP/rv-later"; adopt_fixture speckit "$V5"
printf '\nSee also `specs/002-cart/spec.md`.\n' >> "$V5/specs/001-user-auth/research.md"; commit "$V5"
python3 "$UPDATE" "$V5" --apply >/dev/null; commit "$V5" "plain update"
python3 "$UPDATE" "$V5" --adopt --apply >/dev/null; commit "$V5" adopted
mkdir -p "$V5/specs/002-cart"; printf '# Cart\n\nThe cart holds items.\n' > "$V5/specs/002-cart/spec.md"; commit "$V5" "second feature"
out=$(python3 "$UPDATE" "$V5" --adopt --apply); rc=$?
[ $rc -eq 0 ] && ! grep -q '^  conflict' <<<"$out" \
    && grep -qF 'See also `docs/sdlc/specs/002-cart.md`.' "$V5/docs/sdlc/specs/001-user-auth-research.md" \
    && pass "a later run updates the reference in an untouched destination instead of a conflict" || fail "later-run rewrite (rc=$rc)" "$out"
# B5b (M-new-1): the same for a file named in an append-section destination and in always.md.
V5B="$TMP/rv-later-append"; adopt_fixture speckit "$V5B"
printf '\nSee also `specs/002-cart/spec.md`.\n' >> "$V5B/.specify/memory/constitution.md"; commit "$V5B"
python3 "$UPDATE" "$V5B" --apply >/dev/null; commit "$V5B" "plain update"
python3 "$UPDATE" "$V5B" --adopt --apply >/dev/null; commit "$V5B" adopted
mkdir -p "$V5B/specs/002-cart"; printf '# Cart\n\nThe cart holds items.\n' > "$V5B/specs/002-cart/spec.md"; commit "$V5B" "second feature"
out=$(python3 "$UPDATE" "$V5B" --adopt --apply); rc=$?
[ $rc -eq 0 ] && grep -qF 'See also `docs/sdlc/specs/002-cart.md`.' "$V5B/docs/sdlc/constitution.md" \
    && [ "$(grep -c '^## Adopted from Spec Kit (constitution.md)$' "$V5B/docs/sdlc/constitution.md")" -eq 1 ] \
    && pass "a later run updates the reference in an append-section destination" || fail "later-run append-section rewrite (rc=$rc)" "$out"
V5D="$TMP/rv-later-own-line"; adopt_fixture speckit "$V5D"
printf '\nSee also `specs/002-cart/spec.md`.\n' >> "$V5D/.specify/memory/constitution.md"; commit "$V5D"
python3 "$UPDATE" "$V5D" --apply >/dev/null; commit "$V5D" "plain update"
python3 "$UPDATE" "$V5D" --adopt --apply >/dev/null; commit "$V5D" adopted
printf '\nC11. Every cart change updates `specs/002-cart/spec.md` by hand.\n' >> "$V5D/docs/sdlc/constitution.md"; commit "$V5D" "own principle"
mkdir -p "$V5D/specs/002-cart"; printf '# Cart\n\nThe cart holds items.\n' > "$V5D/specs/002-cart/spec.md"; commit "$V5D" "second feature"
own=$(grep -n '^C11\. ' "$V5D/docs/sdlc/constitution.md" | cut -d: -f1)
out=$(python3 "$UPDATE" "$V5D" --adopt); rc=$?
[ $rc -eq 4 ] && grep -qE "no-dangling +FAIL: docs/sdlc/constitution.md:$own -> specs/" <<<"$out" \
    && ! grep -qE "FAIL: .*constitution.md:[0-9]+ -> specs/.*constitution.md:[0-9]+ -> specs/" <<<"$out" \
    && grep -q 'append-section; references to newly moved files updated' <<<"$out" \
    && pass "the project's own line naming a moved file stays as written and fails hard; the adopted one is rewritten, and the plan says so" \
    || fail "own constitution line (rc=$rc, line $own)" "$out"
V5C="$TMP/rv-later-always"; adopt_fixture kiro "$V5C"
printf '\nSee also `.kiro/specs/cart/requirements.md`.\n' >> "$V5C/.kiro/steering/tech.md"; commit "$V5C"
python3 "$UPDATE" "$V5C" --apply >/dev/null; commit "$V5C" "plain update"
python3 "$UPDATE" "$V5C" --adopt --apply >/dev/null; commit "$V5C" adopted
mkdir -p "$V5C/.kiro/specs/cart"; printf '# Cart\n\nThe cart holds items.\n' > "$V5C/.kiro/specs/cart/requirements.md"; commit "$V5C" "second feature"
out=$(python3 "$UPDATE" "$V5C" --adopt --apply); rc=$?
[ $rc -eq 0 ] && ! grep -qF '.kiro/specs/cart/requirements.md' "$V5C/.ai/policies/adopted/always.md" \
    && grep -qF 'See also `' "$V5C/.ai/policies/adopted/always.md" \
    && pass "a later run updates the reference in always.md" || fail "later-run always.md rewrite (rc=$rc)" "$out"
# B6: coexist rows written per file before 2026-09-27 are superseded, not kept beside the new ones.
V6="$TMP/rv-old-rows"; adopt_fixture speckit "$V6"
python3 "$UPDATE" "$V6" --apply >/dev/null; commit "$V6" "plain update"
python3 - "$V6/.ai/AGENTS.md" <<'OLDROWS'
import sys
p = sys.argv[1]
lines = open(p).read().split("\n")
last = max(i for i, l in enumerate(lines) if l.startswith("|"))
old = ["| an adopted Spec Kit spec | specs/001-user-auth/spec.md (kept in place; its globs are not applied by this runtime) |",
       "| an adopted Spec Kit file | specs/001-user-auth/tasks.md (kept in place; its globs are not applied by this runtime) |"]
open(p, "w").write("\n".join(lines[:last + 1] + old + lines[last + 1:]))
OLDROWS
commit "$V6" "old coexist rows"
out=$(python3 "$UPDATE" "$V6" --adopt --mode coexist --apply); rc=$?
[ $rc -eq 0 ] && ! grep -q 'specs/001-user-auth/spec.md (kept in place' "$V6/.ai/AGENTS.md" \
    && grep -q '| specs/001-user-auth/ (kept in place' "$V6/.ai/AGENTS.md" \
    && grep -qE '^  router .*-2 superseded' <<<"$out" \
    && pass "the old per-file coexist rows give way to the directory row" || fail "old coexist rows kept (rc=$rc)" "$out"
# L2: a source that is not UTF-8 is copied byte for byte, never re-encoded.
V7="$TMP/rv-latin1"; adopt_fixture speckit "$V7"
printf 'caf\351 see `specs/001-user-auth/spec.md`\n' > "$V7/specs/001-user-auth/research.md"; commit "$V7"
python3 "$UPDATE" "$V7" --apply >/dev/null; commit "$V7" "plain update"
out=$(python3 "$UPDATE" "$V7" --adopt --apply); rc=$?
cmp -s "$V7/specs/001-user-auth/research.md" "$V7/docs/sdlc/specs/001-user-auth-research.md" \
    && pass "a non-UTF-8 source is copied unchanged, not rewritten lossily" || fail "latin-1 source re-encoded (rc=$rc)" "$out"

echo "== R11: a hard-scope stale reference fails no-dangling, the same in warn scope only warns"
D="$TMP/dangling"; adopt_fixture cursor "$D"
printf '\nSee `@.cursorrules` for the legacy rules.\n' >> "$D/.ai/policies/coding.md"; commit "$D"
out=$(python3 "$UPDATE" "$D" --adopt); rc=$?
grep -qE '^  check +no-dangling +FAIL: .ai/policies/coding.md:[0-9]+ -> .cursorrules$' <<<"$out" \
    && pass "a hard-scope reference to .cursorrules fails no-dangling" || fail "hard-scope reference not caught" "$out"
[ $rc -eq 4 ] && head -1 <<<"$out" | grep -q '^ADOPT_INCOMPLETE: .*no-dangling FAIL' \
    && pass "I1: a failed check is exit 4 in the dry run, not a PASS-looking exit 0" || fail "failed check dry run exit (rc=$rc)" "$out"
W="$TMP/warn-only"; adopt_fixture cursor "$W"
baseline=$(python3 "$UPDATE" "$W" --adopt | grep -oE 'no-dangling +PASS \([0-9]+' | grep -oE '[0-9]+$')
mkdir -p "$W/src"; printf '# Notes\n\nSee `@.cursorrules` for the legacy rules.\n' > "$W/src/README.md"; commit "$W"
out=$(python3 "$UPDATE" "$W" --adopt)
after=$(printf '%s' "$out" | grep -oE 'no-dangling +PASS \([0-9]+' | grep -oE '[0-9]+$')
grep -qE '^  check +no-dangling +PASS' <<<"$out" && [ "$after" -eq $((baseline + 1)) ] \
    && pass "the same reference in src/README.md adds one warning, not a failure" || fail "warn-scope reference wrongly failed" "$out (baseline=$baseline after=$after)"
grep -qE '^  check +no-dangling +PASS \([0-9]+ warning\(s\) outside the new structure: .*src/README.md:3 -> .cursorrules' <<<"$out" \
    && pass "the warning is named by file:line, not only counted" || fail "warning not named" "$out"

echo "== R14: coexist plans only the router edit; no-line-lost is not applicable, no-dangling checks the linked paths exist"
CO="$TMP/coexist"; adopt_fixture cursor "$CO"
out=$(python3 "$UPDATE" "$CO" --adopt --mode coexist)
[ "$(printf '%s' "$out" | grep -c '^  router\|^  adopt\|^  conflict')" -eq 1 ] \
    && pass "coexist plans exactly one write: the router edit" || fail "coexist planned more than the router row" "$out"
grep -qE '^  check +no-line-lost +not applicable' <<<"$out" && pass "no-line-lost is not applicable in coexist" || fail "coexist ran no-line-lost" "$out"
grep -qE '^  check +no-dangling +PASS' <<<"$out" && pass "no-dangling passes: every linked path exists" || fail "coexist no-dangling failed" "$out"
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
grep -qE '^  check +no-dangling +FAIL' <<<"$out" && pass "a missing linked path fails no-dangling in coexist" || fail "missing linked path not caught" "$out"

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
grep -q '^foreign structure detected: cursor (.*file' <<<"$out" && [ $rc -eq 1 ] \
    && pass "no record, foreign structure present: line 3, exit 1" || fail "line 3 wrong" "$out/$rc"
G="$TMP/check-good"; adopt_fixture cursor "$G"
srcsha="sha256:$(sha256sum "$G/.cursorrules" | cut -d' ' -f1)"
plant_record "$G" "2000-01-01" pass pass "$srcsha"
out=$(python3 "$UPDATE" "$G" --adopt --check); rc=$?
grep -qE '^adopted 2000-01-01: cursor — up to date; [0-9]+ file\(s\) await cleanup$' <<<"$out" && [ $rc -eq 0 ] \
    && pass "a matching record, both checks pass: line 2, exit 0" || fail "line 2 wrong" "$out/$rc"
RG="$TMP/check-regen"; adopt_fixture cursor "$RG"
plant_record "$RG" "2000-01-01" pass pass "sha256:0000000000000000000000000000000000000000000000000000000000000"
out=$(python3 "$UPDATE" "$RG" --adopt --check); rc=$?
grep -q '^foreign files regenerated since the adopt of 2000-01-01: .cursorrules' <<<"$out" && [ $rc -eq 1 ] \
    && pass "the source sha no longer matches: line 4, exit 1" || fail "line 4 wrong" "$out/$rc"
IC="$TMP/check-incomplete"; adopt_fixture cursor "$IC"
srcsha="sha256:$(sha256sum "$IC/.cursorrules" | cut -d' ' -f1)"
plant_record "$IC" "2000-01-01" fail pass "$srcsha"
out=$(python3 "$UPDATE" "$IC" --adopt --check); rc=$?
grep -q '^adoption of 2000-01-01 incomplete: no-line-lost FAIL' <<<"$out" && [ $rc -eq 1 ] \
    && pass "a failed check: line 5, exit 1" || fail "line 5 wrong" "$out/$rc"
python3 "$UPDATE" "$G" --check >/dev/null; [ $? -eq 0 ] && pass "the plain --check line is unchanged by any of this (OQ10)" || fail "plain --check disturbed"
CX="$TMP/check-coexist"; adopt_fixture cursor "$CX"
srcsha="sha256:$(sha256sum "$CX/.cursorrules" | cut -d' ' -f1)"
plant_record "$CX" "2000-01-01" pass pass "$srcsha"
jq '.mode = "coexist" | .cleanup.offered = false' "$CX/.ai/reports/adopt-2000-01-01/adopt.json" > "$TMP/cx.json" \
    && mv "$TMP/cx.json" "$CX/.ai/reports/adopt-2000-01-01/adopt.json"
out=$(python3 "$UPDATE" "$CX" --adopt --check); rc=$?
[ "$out" = "adopted 2000-01-01: cursor — up to date" ] && [ $rc -eq 0 ] \
    && pass "a coexist record offers no cleanup (R14)" || fail "coexist --check line" "$out/$rc"

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
[ $rc -eq 4 ] && head -1 <<<"$out" | grep -q '^ADOPT_INCOMPLETE: .*CLAUDE.md: a split needs a proposal' \
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
[ ! -e "$REC/original/specs/001-user-auth/research.md" ] && grep -q 'skipped (git has them): specs/001-user-auth/research.md' <<<"$out" \
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
grep -q '^0 automatic' <<<"$out" && [ "$(tree_sha "$A")" = "$before" ] \
    && pass "a second --adopt plans nothing and writes nothing" || fail "not idempotent" "$out"
out=$(python3 "$UPDATE" "$A")
grep -q '^  conflict  .ai/AGENTS.md' <<<"$out" && fail "the router rows became a conflict for the plain update" "$out" \
    || pass "the plain dry run keeps the router rows as project edits"
printf 'extra\n' >> "$A/specs/001-user-auth/spec.md"; commit "$A" regen
out=$(python3 "$UPDATE" "$A" --adopt --check); rc=$?
grep -q '^foreign files regenerated since the adopt of .*specs/001-user-auth/spec.md' <<<"$out" && [ $rc -eq 1 ] \
    && pass "a changed source makes --adopt --check say regenerated (R16)" || fail "no regenerated line (rc=$rc)" "$out"
grep -q '^  hint      foreign files regenerated' <<<"$(python3 "$UPDATE" "$A")" \
    && pass "and the plain dry run carries it as a hint (D5)" || fail "no D5 hint for regeneration"
out=$(python3 "$UPDATE" "$A" --adopt)
grep -qE '^  check +no-line-lost +FAIL: 1 line\(s\): specs/001-user-auth/spec.md:[0-9]+$' <<<"$out" \
    && pass "F9: the conflicted destination's lines count, so only the new line is named lost" || fail "no-line-lost after a regeneration" "$out"
out=$(python3 "$UPDATE" "$A" --adopt --cleanup); rc=$?
[ $rc -eq 5 ] && grep -q 'restore the adopted version from git' <<<"$out" \
    && ! grep -q 'run /project-update --adopt --apply again' <<<"$out" \
    && pass "F9: cleanup on a changed source gives a way out, not another --apply" || fail "changed-source cleanup hint (rc=$rc)" "$out"
grep -q '^  hint      foreign structure detected: cursor' <<<"$(python3 "$UPDATE" "$P/cursor")" \
    && pass "an un-adopted foreign structure is a hint in the plain dry run (D5)" || fail "no D5 hint for detection"

echo "== R15: an interrupted apply resumes, and only its own writes count as allowed dirt"
for phase in 1 2; do
    I="$TMP/interrupt-$phase"; adopt_fixture cursor "$I"
    out=$(CLAUDE_AGENTIC_TEST=1 ADOPT_STOP_AFTER=$phase python3 "$UPDATE" "$I" --adopt --apply); rc=$?
    [ $rc -eq 3 ] && [ "$(jq -r '.status' "$I"/.ai/reports/adopt-*/adopt.json)" = partial ] \
        && pass "stopped after phase $phase: exit 3, the record says partial" || fail "phase $phase stop (rc=$rc)" "$out"
    out=$(python3 "$UPDATE" "$I" --adopt --check)
    grep -q 'incomplete: the apply was interrupted' <<<"$out" \
        && pass "--adopt --check calls it incomplete" || fail "no incomplete line after phase $phase" "$out"
    out=$(python3 "$UPDATE" "$I" --adopt --apply); rc=$?
    [ $rc -eq 0 ] && [ "$(jq -r '.status' "$I"/.ai/reports/adopt-*/adopt.json)" = applied ] \
        && grep -qE '^  check +no-line-lost +PASS' <<<"$out" \
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

echo "== R7, R8: the instruction-file split — request, fallback, proposal, diff"
# proposal <project> <file> [jq filter]: the fixture's canned proposal as a real
# I5 document for the file on disk (tests/fixtures/adopt/README.md), into the
# record directory; the filter plants a defect.
proposal() {
    local dir="$1" name="$2" filter="${3:-.}" fx rec
    fx="$FIX/large-$( [ "$name" = CLAUDE.md ] && echo claude || echo agents )-md"
    rec="$dir/.ai/reports/adopt-$(date -u +%F)"; mkdir -p "$rec"
    python3 - "$dir/$name" "$name" "$fx/split-proposal.fixture.json" "$fx/fixture-$name" <<'PROPEOF' | jq -c "$filter" > "$rec/split-proposal.json"
import hashlib, json, sys
path, name, canned, appended = sys.argv[1:5]
text = open(path, encoding="utf-8").read()
lines = text.split("\n")[:-1]
off = len(lines) - len(open(appended, encoding="utf-8").read().split("\n")[:-1])
start = next(i for i, l in enumerate(lines, 1) if "claude-agentic:start" in l)
fx = json.load(open(canned))
sh = lambda r: [r[0] + off, r[1] + off]
json.dump({"version": 1, "source": name, "source_sha": "sha256:" + hashlib.sha256(text.encode()).hexdigest(),
           "keep": [[1, start - 1]] + [sh(r) for r in fx["keep"]],
           "moves": [dict(m, lines=sh(m["lines"])) for m in fx["moves"]],
           "dropped": [dict(d, lines=sh(d["lines"])) for d in fx["dropped"]]}, sys.stdout)
PROPEOF
}
SQ="$TMP/split-request"; adopt_fixture large-claude-md "$SQ"
before=$(cd "$SQ" && find . -path ./.git -prune -o -type f -print | sort)
out=$(python3 "$UPDATE" "$SQ" --adopt --split-request); rc=$?
REQ=$(ls "$SQ"/.ai/reports/adopt-*/split-request.json 2>/dev/null)
after=$(cd "$SQ" && find . -path ./.git -prune -o -type f -print | grep -v '/split-request.json$' | sort)
[ $rc -eq 0 ] && [ -n "$REQ" ] && [ "$before" = "$after" ] && [ -z "$(git -C "$SQ" status --porcelain | grep -v '^?? .ai/reports/')" ] \
    && pass "--split-request writes split-request.json and nothing else" || fail "split-request (rc=$rc)" "$out"
[ "$(jq -r '.source, .keep_budget_bytes > 0, (.outline | length > 0), .block[0] > 0' "$REQ" | tr '\n' ' ')" = "CLAUDE.md true true true " ] \
    && pass "the request has the outline, the block and the keep budget" || fail "request fields" "$(cat "$REQ")"
grep -q 'Money is an integer' "$REQ" && fail "the request carries source text" || pass "and no line of body text"
proposal "$SQ" CLAUDE.md; commit "$SQ"; PROP=$(ls "$SQ"/.ai/reports/adopt-*/split-proposal.json)
mtime=$(stat -c %Y "$PROP"); sleep 1
out=$(python3 "$UPDATE" "$SQ" --adopt --split-request)
grep -q 'a proposal for this sha exists, reused' <<<"$out" && [ "$(stat -c %Y "$PROP")" = "$mtime" ] \
    && pass "a matching proposal is reused, not re-requested (mtime unchanged)" || fail "proposal not reused" "$out"

FB="$TMP/split-fallback"; adopt_fixture large-claude-md "$FB"
out=$(python3 "$UPDATE" "$FB" --adopt --split fallback); rc=$?
[ $rc -eq 0 ] && grep -q '^  adopt     CLAUDE.md -> .ai/policies/adopted/claude-md.md .*split (fallback)' <<<"$out" \
    && pass "--split fallback plans every line to .ai/policies/adopted/claude-md.md" || fail "fallback dry run (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$FB" --adopt --apply --split fallback); rc=$?
[ $rc -eq 0 ] && grep -qE '^  check +no-line-lost +PASS' <<<"$out" && grep -qE '^  check +no-dangling +PASS' <<<"$out" \
    && pass "the fallback applies with both checks PASS" || fail "fallback apply (rc=$rc)" "$out"
[ "$(grep -c '^| .* | policies/adopted/ |$' "$FB/.ai/AGENTS.md")" -eq 1 ] && pass "and one router row" || fail "fallback router row" "$(grep '^|' "$FB/.ai/AGENTS.md" | tail -3)"
python3 "$UPDATE" "$FB" --check --budget >/dev/null && pass "the split CLAUDE.md is within the skeleton budget" || fail "fallback result over budget"
grep -q 'Money is an integer number of cents' "$FB/.ai/policies/adopted/claude-md.md" && ! grep -q 'Money is an integer' "$FB/CLAUDE.md" \
    && pass "the notes moved verbatim, out of CLAUDE.md" || fail "fallback did not move the notes"
[ "$(jq -r '.sources[] | select(.path == "CLAUDE.md") | .cleanup' "$FB"/.ai/reports/adopt-*/adopt.json)" = false ] \
    && [ "$(jq -r '.split["CLAUDE.md"].by' "$FB"/.ai/reports/adopt-*/adopt.json)" = fallback ] \
    && pass "the instruction file is recorded, split by fallback, never for cleanup (R17)" || fail "adopt.json split record"
DF="$TMP/split-decided"; adopt_fixture large-claude-md "$DF"; mkdir -p "$DF/.ai/reports/adopt-2000-01-01"
printf '{"version":1,"split":"fallback"}\n' > "$DF/.ai/reports/adopt-2000-01-01/decisions.json"; commit "$DF"
out=$(python3 "$UPDATE" "$DF" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q 'split (fallback)' <<<"$out" && pass "\"split\": \"fallback\" in decisions.json chooses the fallback" || fail "decided fallback (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$DF" --adopt --split proposal); rc=$?
[ $rc -eq 4 ] && head -1 <<<"$out" | grep -q 'no split-proposal.json matches' && pass "--split proposal with no proposal exits 4" || fail "--split proposal (rc=$rc)" "$out"

declare -A DESTS
for name in CLAUDE.md AGENTS.md; do
    f=$( [ $name = CLAUDE.md ] && echo large-claude-md || echo large-agents-md )
    S="$TMP/split-$f"; adopt_fixture "$f" "$S"; proposal "$S" "$name"; commit "$S"
    out=$(python3 "$UPDATE" "$S" --adopt --diff); rc=$?
    [ $rc -eq 0 ] && [ "$(printf '%s' "$out" | grep -c '^+++ b/')" -eq "$(printf '%s' "$out" | grep -c '^--- a/')" ] \
        && grep -q "^+++ b/$name$" <<<"$out" && grep -q '^+++ b/.ai/rules/payment.md$' <<<"$out" \
        && pass "$f: --diff prints ---/+++ for each target" || fail "$f: --diff (rc=$rc)" "$out"
    out=$(python3 "$UPDATE" "$S" --adopt --apply); rc=$?
    [ $rc -eq 0 ] && grep -qE '^  check +no-line-lost +PASS' <<<"$out" \
        && pass "$f: the proposal applies, both checks PASS" || fail "$f: proposal apply (rc=$rc)" "$out"
    DESTS[$f]=$(printf '%s' "$out" | sed -nE "s#^  adopt     $name -> ([^ ]+) .*#\1#p" | grep -v "^$name$" | sort | tr '\n' ' ')
    python3 "$UPDATE" "$S" --check --budget >/dev/null && pass "$f: $name is within the skeleton budget after the split" || fail "$f: over budget after the split"
    python3 "$UPDATE" "$S" --check >/dev/null && pass "$f: and the project is current" || fail "$f: behind after the split"
    grep -q '^dirs: \[src/Payment\]$' "$S/.ai/rules/payment.md" && grep -q 'declined card' "$S/src/Payment/$name" \
        && pass "$f: the payment rule has dirs and renders into src/Payment/$name" || fail "$f: payment rule"
    grep -q '^## Conventions$' "$S/.ai/policies/adopted/conventions.md" && [ "$(grep -c '^## Conventions$' "$S/.ai/policies/adopted/conventions.md")" -eq 1 ] \
        && pass "$f: an outline heading is used once, not repeated" || fail "$f: conventions heading"
    grep -q 'takes orders and payments' "$S/.ai/project/overview.md" && pass "$f: overview.md gets its lines under a generated heading" || fail "$f: overview"
    [ "$(jq -r '.checks.no_line_added.status' "$S"/.ai/reports/adopt-*/adopt.json)" = pass ] && pass "$f: no-line-added is recorded PASS (R9)" || fail "$f: no no_line_added"
    commit "$S" split
    out=$(python3 "$UPDATE" "$S" --adopt)
    grep -q '^0 automatic' <<<"$out" && ! grep -q 'split?' <<<"$out" \
        && pass "$f: a second --adopt plans nothing" || fail "$f: not idempotent after the split" "$out"
done
[ -n "${DESTS[large-claude-md]}" ] && [ "${DESTS[large-claude-md]}" = "${DESTS[large-agents-md]}" ] \
    && pass "large-claude-md and large-agents-md reach the same destinations (R19)" || fail "parity" "${DESTS[large-claude-md]} / ${DESTS[large-agents-md]}"

IR="$TMP/split-interrupted"; adopt_fixture large-claude-md "$IR"; proposal "$IR" CLAUDE.md; commit "$IR"
CLAUDE_AGENTIC_TEST=1 ADOPT_STOP_AFTER=1 python3 "$UPDATE" "$IR" --adopt --apply >/dev/null
grep -q 'Money is an integer' "$IR/CLAUDE.md" && pass "stopped after phase 1: the lines are at their destinations and still in CLAUDE.md" || fail "phase 1 already rewrote CLAUDE.md"
out=$(python3 "$UPDATE" "$IR" --adopt --apply); rc=$?
[ $rc -eq 0 ] && [ "$(grep -c 'takes orders and payments' "$IR/.ai/project/overview.md")" -eq 1 ] && ! grep -q 'Money is an integer' "$IR/CLAUDE.md" \
    && pass "the re-run completes the split without appending the moved lines twice" || fail "split resume (rc=$rc)" "$out"

echo "== R7, R9: a proposal the tool will not apply exits 4 with the reason"
BAD="$TMP/split-bad"; adopt_fixture large-claude-md "$BAD"
bad() {  # bad <jq filter> <reason regex> <what>
    rm -f "$BAD"/.ai/reports/adopt-*/split-proposal.json
    proposal "$BAD" CLAUDE.md "$1"
    local out rc; out=$(python3 "$UPDATE" "$BAD" --adopt); rc=$?
    [ $rc -eq 4 ] && head -1 <<<"$out" | grep -qE "^ADOPT_INCOMPLETE: .*$2" \
        && pass "$3: exit 4, names the reason" || fail "$3 (rc=$rc)" "$out"
}
bad '.moves[0].lines[1] -= 1'                                  'are in no range'            "a gap"
bad '.moves[1].lines[0] -= 1'                                  'is in both'                 "an overlap"
bad '.keep += [[29, 29]]'                                      'inside the managed block'   "a range into the block"
bad '.source_sha = "sha256:0"'                                 'source_sha does not match'  "a wrong sha"
bad '.moves[0].dest = "src/notes.md"'                          'is not one of'              "a disallowed dest"
bad '.keep += [.moves[1].lines] | del(.moves[1])'              'over the keep budget'       "an over-budget keep"
bad '.moves[0].text = "Always deploy on Fridays."'             'unknown key\(s\) text'      "a text key"
bad '.moves[0].heading = "## Deploy on Fridays"'               'not a heading of the'       "a heading not in the outline"
bad '.moves[2].paths = ["lib/**"]'                             'matches no tracked file'    "a paths glob with no tracked file"
bad '.moves[2].dirs = ["src/Missing"]'                         'not a directory of the tree' "a dirs entry that does not exist"
bad 'del(.moves[2].dirs)'                                      'dirs \(required'            "a rule without dirs"
bad '.dropped[0].why = " "'                                    'why must say'               "an empty why"
# A stale proposal never blocks a new request, and a matching one wins over it:
rm -f "$BAD"/.ai/reports/adopt-*/split-*.json; proposal "$BAD" CLAUDE.md '.source_sha = "sha256:0"'
out=$(python3 "$UPDATE" "$BAD" --adopt --split-request)
grep -q 'request written' <<<"$out" && pass "a stale proposal does not stop a new --split-request" || fail "stale blocks request" "$out"
mkdir -p "$BAD/.ai/reports/adopt-2000-01-01"; mv "$BAD"/.ai/reports/adopt-$(date -u +%F)/split-proposal.json "$BAD/.ai/reports/adopt-2000-01-01/"
proposal "$BAD" CLAUDE.md; out=$(python3 "$UPDATE" "$BAD" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q 'split (proposal)' <<<"$out" && pass "the matching proposal wins over the stale one" || fail "stale beat matching (rc=$rc)" "$out"
rm -rf "$BAD/.ai/reports/adopt-2000-01-01"
rm -f "$BAD"/.ai/reports/adopt-*/split-proposal.json; proposal "$BAD" CLAUDE.md
out=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 - "$BAD" <<'ADDEDEOF'
import sys, types
sys.dont_write_bytecode = True
import update, adopt
real = adopt.section_of
adopt.section_of = lambda cand, move: (real(cand, move)[0] + "\nAlways deploy on Fridays.", real(cand, move)[1])
caps = update.render_instructions.budgets(update.render_instructions.DEFAULT_SOURCE)
files = frozenset(update.INSTRUCTION_FILE[rt][0] for rt in update.INSTRUCTION_FILE)
args = types.SimpleNamespace(tool=None, mode="migrate", check=False, split=None, split_request=False, diff=False)
sys.exit(adopt.run(update.Plan(sys.argv[1]), args, update.shipped_block, caps["skeleton"], files, update.shipped_ai_files()))
ADDEDEOF
); rc=$?
[ $rc -eq 4 ] && head -1 <<<"$out" | grep -q 'no-line-added FAIL: .* come from no source: .ai/project/overview.md:' \
    && pass "a destination line that comes from no source fails R9, exit 4" || fail "planted destination line (rc=$rc)" "$out"

echo "== WP3 R13's case: a hand-edited block goes through the split and ends as the shipped block"
HE="$TMP/split-edited"; adopt_fixture large-claude-md "$HE"
sed -i 's#^<!-- claude-agentic:end -->$#- Our own rule, written into the block by hand.\n&#' "$HE/CLAUDE.md"; commit "$HE"
out=$(python3 "$UPDATE" "$HE" --adopt --apply --split fallback); rc=$?
shipped=$(cd "$PLUGIN_ROOT/skills/project-update" && python3 -c 'import update; print(update.shipped_block("claude"))')
[ $rc -eq 0 ] && [ "$(python3 -c 'import sys; sys.path.insert(0, sys.argv[2]); import render_instructions as r; print(r.block_of(open(sys.argv[1]).read()))' "$HE/CLAUDE.md" "$PLUGIN_ROOT/skills/project-update")" = "$shipped" ] \
    && pass "the edited block is replaced by the shipped one" || fail "edited block (rc=$rc)" "$out"
grep -q 'Our own rule, written into the block by hand' "$HE/.ai/policies/adopted/claude-md.md" \
    && pass "and the hand-written line moved with the rest, not lost" || fail "the edited line was lost"
[ -f "$(ls -d "$HE"/.ai/reports/adopt-*/)original/CLAUDE.md" ] && pass "the original CLAUDE.md is kept" || fail "no original CLAUDE.md"

echo "== R13, R14: cleanup deletes only after both checks hold again and a human confirms"
# cleaned <dir>: the fixture adopted and committed, ready for --cleanup.
cleaned() { adopt_fixture cursor "$1"; python3 "$UPDATE" "$1" --adopt --apply >/dev/null; commit "$1" adopted; }
# cleanup_refused <dir> <what>: confirmed as a launcher would, still exit 5, ADOPT_REFUSED on line 1, nothing removed.
cleanup_refused() {
    local before out rc
    before=$(tree_sha "$1")
    out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$1" --adopt --cleanup --apply --confirm-delete tester </dev/null); rc=$?
    [ $rc -eq 5 ] && [ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_REFUSED ] && [ "$(tree_sha "$1")" = "$before" ] \
        && pass "$2: cleanup refused, exit 5, nothing removed" || fail "$2: expected a cleanup refusal (rc=$rc)" "$out"
}
CL="$TMP/cleanup"; cleaned "$CL"
before=$(tree_sha "$CL")
out=$(python3 "$UPDATE" "$CL" --adopt --cleanup); rc=$?
want=$(jq -r '.sources[] | select(.cleanup) | .path' "$CL"/.ai/reports/adopt-*/adopt.json | sort)
got=$(printf '%s\n' "$out" | awk '$1 == "delete?" {print $2}' | sort)
[ $rc -eq 0 ] && [ -n "$want" ] && [ "$got" = "$want" ] && [ "$(tree_sha "$CL")" = "$before" ] \
    && pass "the cleanup dry run lists exactly the cleanup: true sources and writes nothing" || fail "cleanup list (rc=$rc)" "$out"
grep -qE '^  check +no-dangling +PASS \(recomputed' <<<"$out" && pass "both checks are recomputed for the listing" || fail "no recomputed check line" "$out"
out=$(python3 "$UPDATE" "$CL" --adopt --cleanup --apply 2>&1); rc=$?
[ $rc -eq 2 ] && pass "--cleanup --apply without --confirm-delete is a usage error" || fail "--cleanup --apply alone (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$CL" --adopt --cleanup --apply --confirm-delete tester </dev/null); rc=$?
[ $rc -eq 5 ] && head -1 <<<"$out" | grep -q '^ADOPT_REFUSED' && [ "$(tree_sha "$CL")" = "$before" ] \
    && pass "--confirm-delete with no terminal and no AI_UNATTENDED: exit 5, nothing removed" || fail "no-human cleanup (rc=$rc)" "$out"
out=$(CLAUDECODE=1 AI_UNATTENDED=1 python3 "$UPDATE" "$CL" --adopt --cleanup --apply --confirm-delete tester </dev/null); rc=$?
REC=$(ls -d "$CL"/.ai/reports/adopt-*/)
gone=0; kept=0
for f in $want; do [ -e "$CL/$f" ] || gone=$((gone + 1)); [ -f "$REC/original/$f" ] && kept=$((kept + 1)); done
n=$(printf '%s\n' "$want" | wc -l)
[ $rc -eq 0 ] && [ $gone -eq "$n" ] && pass "AI_UNATTENDED=1: every listed file is deleted" || fail "cleanup apply (rc=$rc, $gone/$n gone)" "$out"
[ $kept -eq "$n" ] && pass "and original/ still holds every one of them" || fail "original/ holds $kept/$n"
[ "$(jq -r '.cleanup.unattended' "$REC/adopt.json")" = true ] && [ "$(jq -r '.cleanup.confirmed_by' "$REC/adopt.json")" = tester ] \
    && [ "$(jq -r '.cleanup.tty' "$REC/adopt.json")" = false ] && [ "$(jq -r '.cleanup.at | length > 0' "$REC/adopt.json")" = true ] \
    && pass "adopt.json.cleanup records who, when, unattended and tty" || fail "cleanup record" "$(jq .cleanup "$REC/adopt.json")"
[ "$(jq -r '.cleanup.via' "$REC/adopt.json")" = unattended ] \
    && pass "and via: unattended — AI_UNATTENDED passed the gate inside an agent session" || fail "cleanup via" "$(jq .cleanup "$REC/adopt.json")"
grep -q 'deleted unattended' "$REC/report.md" && grep -q '(deleted unattended)' <<<"$out" \
    && pass "report.md and the output say deleted unattended" || fail "no deleted unattended line"
[ ! -d "$CL/.cursor/rules" ] && [ -f "$CL/.cursor/mcp.json" ] \
    && pass "a directory left empty inside the tool's roots goes with its files; an ignored file keeps its own" \
    || fail ".cursor/rules/ left behind, or the ignored .cursor/mcp.json removed"
[ -z "$(find "$CL/.ai/reports" -name migration.json)" ] && pass "cleanup writes no migration.json" || fail "cleanup wrote migration.json"
commit "$CL" cleanup
out=$(python3 "$UPDATE" "$CL" --adopt --check); rc=$?
[ $rc -eq 0 ] && grep -qE '^adopted [0-9-]+: cursor — up to date$' <<<"$out" \
    && pass "--adopt --check after cleanup says up to date" || fail "check after cleanup (rc=$rc)" "$out"
git -C "$CL" checkout -q HEAD~1 -- .cursorrules
out=$(python3 "$UPDATE" "$CL" --adopt --check); rc=$?
[ $rc -eq 1 ] && grep -q '^foreign files regenerated since the adopt of .*\.cursorrules' <<<"$out" \
    && pass "a .cursorrules that reappears byte for byte says regenerated (R16)" || fail "reappearing file (rc=$rc)" "$out"

echo "== F3: an agent session cannot pass --confirm-delete, even with a terminal"
if [ $HAS_PTY -eq 1 ]; then
    TT="$TMP/cleanup-tty"; cleaned "$TT"; before=$(tree_sha "$TT")
    out=$(pty env "${NOMARK[@]}" CLAUDECODE=1 python3 "$UPDATE" "$TT" --adopt --cleanup --apply --confirm-delete tester); rc=$?
    [ $rc -eq 5 ] && [ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_REFUSED ] && [ "$(tree_sha "$TT")" = "$before" ] \
        && grep -q CLAUDECODE <<<"$out" \
        && pass "CLAUDECODE=1 with a terminal: exit 5, ADOPT_REFUSED names CLAUDECODE, nothing removed" || fail "CLAUDECODE under a pty (rc=$rc)" "$out"
    out=$(pty env "${NOMARK[@]}" CODEX_THREAD_ID=x python3 "$UPDATE" "$TT" --adopt --cleanup --apply --confirm-delete tester); rc=$?
    [ $rc -eq 5 ] && [ "$(printf '%s' "$out" | head -1 | cut -d: -f1)" = ADOPT_REFUSED ] && [ "$(tree_sha "$TT")" = "$before" ] \
        && grep -q CODEX_THREAD_ID <<<"$out" \
        && pass "CODEX_THREAD_ID alone with a terminal: exit 5, names it, nothing removed" || fail "CODEX_THREAD_ID under a pty (rc=$rc)" "$out"
    # adopt.py stands alone: its own gate says no under a marker, whatever stdin is.
    out=$(cd "$PLUGIN_ROOT/skills/project-update" && pty env "${NOMARK[@]}" CODEX_SANDBOX= python3 -c 'import adopt; print(adopt.human_gate()[0])')
    [ "$out" = False ] && pass "adopt.human_gate() refuses an empty-valued marker under a terminal" || fail "human_gate under CODEX_SANDBOX=" "$out"
    out=$(cd "$PLUGIN_ROOT/skills/project-update" && pty env "${NOMARK[@]}" CODEX_VERSION=0.1 python3 -c 'import adopt; g = adopt.human_gate(); print(g[0], g[2])')
    [ "${out%% *}" = False ] && grep -q '(CODEX_VERSION is set)' <<<"$out" \
        && pass "adopt.human_gate() refuses CODEX_VERSION alone: 'is set'" || fail "human_gate under CODEX_VERSION" "$out"
    out=$(cd "$PLUGIN_ROOT/skills/project-update" && pty env "${NOMARK[@]}" CLAUDECODE=1 CODEX_CI=1 python3 -c 'import adopt; print(adopt.human_gate()[2])')
    grep -q '(CLAUDECODE, CODEX_CI are set)' <<<"$out" \
        && pass "two markers: the refusal names both and says 'are set'" || fail "plural markers" "$out"
    out=$(pty env "${NOMARK[@]}" python3 "$UPDATE" "$TT" --adopt --cleanup --apply --confirm-delete tester); rc=$?
    TREC=$(ls "$TT"/.ai/reports/adopt-*/adopt.json)
    [ $rc -eq 0 ] && [ ! -e "$TT/.cursorrules" ] && pass "a terminal and no marker: the cleanup runs" || fail "human cleanup (rc=$rc)" "$out"
    [ "$(jq -r '.cleanup.via' "$TREC")" = terminal ] && [ "$(jq -r '.cleanup.unattended' "$TREC")" = false ] && [ "$(jq -r '.cleanup.tty' "$TREC")" = true ] \
        && pass "and adopt.json.cleanup says via: terminal, unattended: false, tty: true" || fail "terminal cleanup record" "$(jq .cleanup "$TREC")"
else
    echo "  SKIP  no pty here (script -qec gives no terminal): the F3 terminal cases did not run"
fi

LD="$TMP/cleanup-later"; cleaned "$LD"
dirs=$(ls "$LD/.ai/reports" | grep -c '^adopt-')
out=$(CLAUDE_AGENTIC_TEST=1 ADOPT_TODAY=2099-01-01 AI_UNATTENDED=1 python3 "$UPDATE" "$LD" --adopt --cleanup --apply --confirm-delete tester </dev/null); rc=$?
[ $rc -eq 0 ] && [ ! -e "$LD/.ai/reports/adopt-2099-01-01" ] && [ "$(ls "$LD/.ai/reports" | grep -c '^adopt-')" = "$dirs" ] \
    && [ "$(jq -r '.cleanup.deleted | length > 0' "$LD"/.ai/reports/adopt-*/adopt.json)" = true ] \
    && pass "a cleanup on a later day writes into the adopt's own directory, none new" || fail "later-day cleanup (rc=$rc)" "$out"

R="$TMP/cleanup-changed"; cleaned "$R"; printf 'Use spaces.\n' >> "$R/.cursorrules"; commit "$R"
cleanup_refused "$R" "a source changed after adopt"
R="$TMP/cleanup-task"; cleaned "$R"; mkdir -p "$R/.ai/state"
cp "$TF"/.ai/state/* "$R/.ai/state/"  # the stage-plan task of the R5 case above
cleanup_refused "$R" "a task in flight at stage plan"
R="$TMP/cleanup-dirty"; cleaned "$R"; printf 'wip\n' > "$R/notes.txt"
cleanup_refused "$R" "an untracked file anywhere in the tree"
R="$TMP/cleanup-uncommitted"; adopt_fixture cursor "$R"; python3 "$UPDATE" "$R" --adopt --apply >/dev/null
cleanup_refused "$R" "the adopt itself not yet committed"
R="$TMP/cleanup-stale"; cleaned "$R"; printf 'Read .cursorrules before you start.\n' > "$R/docs/sdlc/specs/notes.md"; commit "$R"
out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$R" --adopt --cleanup --apply --confirm-delete tester </dev/null)
cleanup_refused "$R" "a stale reference planted after adopt"
head -1 <<<"$out" | grep -q 'no-dangling FAIL' && pass "and the refusal names no-dangling" || fail "stale refusal reason" "$out"
R="$TMP/cleanup-coexist"; adopt_fixture cursor "$R"; python3 "$UPDATE" "$R" --adopt --apply --mode coexist >/dev/null; commit "$R"
out=$(python3 "$UPDATE" "$R" --adopt --cleanup); rc=$?
[ $rc -eq 5 ] && head -1 <<<"$out" | grep -q '^ADOPT_REFUSED: coexist keeps the foreign files' \
    && pass "coexist cleanup: exit 5, coexist keeps the foreign files (R14)" || fail "coexist cleanup (rc=$rc)" "$out"
cleanup_refused "$R" "coexist, even confirmed"

SK="$TMP/cleanup-speckit"; adopt_fixture speckit "$SK"
# A skill that ships more than its SKILL.md: the nested directory must go too.
mkdir -p "$SK/.claude/skills/speckit-plan/scripts"; echo 'echo plan' > "$SK/.claude/skills/speckit-plan/scripts/helper.sh"
commit "$SK" "nested skill file"
python3 "$UPDATE" "$SK" --apply >/dev/null; commit "$SK" "plain update"
python3 "$UPDATE" "$SK" --adopt --apply >/dev/null; commit "$SK" adopted
out=$(python3 "$UPDATE" "$SK" --adopt --cleanup); rc=$?
[ $rc -eq 0 ] && grep -qE '^  delete\? +\.claude/commands/speckit' <<<"$out" \
    && ! grep -qE '^  delete\? +(CLAUDE\.md|AGENTS\.md|GEMINI\.md|\.junie/guidelines\.md) ' <<<"$out" \
    && pass "Spec Kit's .claude/ commands are listed, the instruction files never (R17)" || fail "speckit cleanup list (rc=$rc)" "$out"
out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$SK" --adopt --cleanup --apply --confirm-delete tester </dev/null); rc=$?
[ $rc -eq 0 ] && [ ! -e "$SK/.specify" ] && [ -f "$SK/CLAUDE.md" ] && [ -d "$SK/.claude" ] \
    && pass "with no task in flight they are deleted; .specify/ goes, CLAUDE.md and .claude/ stay" || fail "speckit cleanup (rc=$rc)" "$out"
[ ! -e "$SK/.claude/skills/speckit-plan" ] && [ -d "$SK/.claude/skills" ] \
    && pass "the emptied .claude/skills/speckit-plan/ goes with its files, scripts/ included; .claude/skills/ stays" || fail "an empty speckit skill dir was left" "$(find "$SK/.claude/skills")"
grep -q 'Run `/project-update --adopt --cleanup` to review' "$SK"/.ai/reports/adopt-*/report.md \
    && fail "report.md still invites a cleanup review after the cleanup" || pass "after the cleanup report.md no longer invites a review"

echo "== the confirmer's name is a name, and a stale task directory is explained"
PH="$TMP/placeholder"; cleaned "$PH"; before=$(tree_sha "$PH")
for name in "<your name>" "  <name>  " "Your Name"; do
    out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$PH" --adopt --cleanup --apply --confirm-delete "$name" </dev/null 2>&1); rc=$?
    [ $rc -eq 2 ] && grep -q 'placeholder' <<<"$out" && [ "$(tree_sha "$PH")" = "$before" ] \
        && pass "--confirm-delete '$name' is refused as a placeholder, nothing removed" || fail "placeholder '$name' accepted (rc=$rc)" "$out"
done
cd "$PLUGIN_ROOT/skills/project-update" || exit 1
real=$(python3 -c 'import adopt, sys
print(" ".join(n for n in sys.argv[1:] if adopt.placeholder_name(n)))' "Ana Your-Name" "I prefer your name convention" "O<Brien" "Ivan Kakurov")
cd - >/dev/null || exit 1
[ -z "$real" ] && pass "a real name that merely contains the words is not a placeholder" || fail "real names refused" "$real"
out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$PH" --apply --confirm-delete "<your name>" </dev/null 2>&1); rc=$?
[ $rc -eq 2 ] && grep -q 'placeholder' <<<"$out" && pass "the plain --apply --confirm-delete refuses it too" || fail "plain placeholder (rc=$rc)" "$out"
TD="$TMP/task-dir"; adopt_fixture cursor "$TD"
mkdir -p "$TD/.ai/reports/T-2000-01-01-001"; echo "left behind" > "$TD/.ai/reports/T-2000-01-01-001/notes.md"
out=$(python3 "$UPDATE" "$TD" --adopt --apply); rc=$?
[ $rc -eq 5 ] && grep -q 'leaves its .ai/reports/<task-id>/ untracked' <<<"$out" \
    && pass "a stale task report dir: the refusal says why and what to do" || fail "task dir refusal (rc=$rc)" "$out"

echo "== review: cleanup and decisions never reach outside the project, and never lose what git cannot restore"
# forge <dir> <jq filter> [jq args]: a hand edit of the committed adopt.json, committed.
forge() {
    local rec; rec=$(ls "$1"/.ai/reports/adopt-*/adopt.json)
    jq "${@:3}" "$2" "$rec" > "$rec.new" && mv "$rec.new" "$rec"; commit "$1" forged
}
printf 'keep me\n' > "$TMP/outside.txt"; osha="sha256:$(sha256sum "$TMP/outside.txt" | cut -d' ' -f1)"
R="$TMP/forge-parent"; cleaned "$R"
forge "$R" '.sources += [{"path":"../outside.txt","sha":$s,"tool":"cursor","transform":"copy","cleanup":true}]' --arg s "$osha"
cleanup_refused "$R" "an adopt.json source with ../"
R="$TMP/forge-abs"; cleaned "$R"
forge "$R" '.sources += [{"path":$p,"sha":$s,"tool":"cursor","transform":"copy","cleanup":true}]' --arg p "$TMP/outside.txt" --arg s "$osha"
cleanup_refused "$R" "an adopt.json source with an absolute path"
[ -f "$TMP/outside.txt" ] && pass "and the file outside the project is still there" || fail "a file outside the project was deleted"
R="$TMP/forge-stranger"; cleaned "$R"
bsha="sha256:$(sha256sum "$R/src/components/Button.tsx" | cut -d' ' -f1)"
forge "$R" '.sources += [{"path":"src/components/Button.tsx","sha":$s,"tool":"cursor","transform":"copy","cleanup":true}]' --arg s "$bsha"
cleanup_refused "$R" "an adopt.json source the mapping does not offer for cleanup"
[ -f "$R/src/components/Button.tsx" ] && pass "and the project's own source file stays" || fail "src/components/Button.tsx was deleted"
R="$TMP/cleanup-ignored"; adopt_fixture cursor "$R"
printf '.cursor/rules/local.mdc\n' >> "$R/.gitignore"; commit "$R" ignore
cp "$R/.cursor/rules/testing.mdc" "$R/.cursor/rules/local.mdc"
python3 "$UPDATE" "$R" --adopt --apply >/dev/null; commit "$R" adopted
out=$(AI_UNATTENDED=1 python3 "$UPDATE" "$R" --adopt --cleanup --apply --confirm-delete tester </dev/null)
cleanup_refused "$R" "a git-ignored cleanup source"
head -1 <<<"$out" | grep -q 'git does not track' && [ -f "$R/.cursor/rules/local.mdc" ] \
    && pass "it names the untracked file, which stays" || fail "ignored-file refusal" "$out"
R="$TMP/cleanup-resumed"; cleaned "$R"
forge "$R" '.cleanup += {"confirmed_by":"first","at":"2000-01-01T00:00:00Z","via":"terminal","unattended":false,"tty":true,"deleted":["gone-earlier.md"]}'
AI_UNATTENDED=1 python3 "$UPDATE" "$R" --adopt --cleanup --apply --confirm-delete tester </dev/null >/dev/null
rec=$(ls "$R"/.ai/reports/adopt-*/adopt.json)
[ "$(jq -r '.cleanup.deleted[0]' "$rec")" = gone-earlier.md ] && [ "$(jq -r '.cleanup.history[0].confirmed_by' "$rec")" = first ] \
    && [ "$(jq -r '.cleanup.confirmed_by' "$rec")" = tester ] && [ "$(jq -r '.cleanup.history[0].via' "$rec")" = terminal ] \
    && pass "a second cleanup keeps the first one's deletions and who confirmed them" || fail "cleanup audit trail" "$(jq .cleanup "$rec")"
grep -q 'confirmed by first' "$(dirname "$rec")/report.md" && grep -q 'over 2 run(s)' "$(dirname "$rec")/report.md" \
    && pass "and report.md names both runs, not only the last" || fail "report.md credits only the last run"
R="$TMP/forge-nopath"; cleaned "$R"; forge "$R" '.sources += [{"sha":"sha256:x","tool":"cursor","cleanup":false}]'
out=$(python3 "$UPDATE" "$R" --adopt --cleanup 2>&1); rc=$?
[ $rc -eq 0 ] && ! grep -q Traceback <<<"$out" && pass "a record entry without a path is skipped, not a traceback" \
    || fail "entry without path (rc=$rc)" "$out"

K2="$TMP/decision-escape"; adopt_fixture kiro "$K2"
mkdir -p "$K2/.kiro/hooks" "$K2/.ai/reports/adopt-2000-01-01"; printf '{"hooks": []}\n' > "$K2/.kiro/hooks/lint-on-save.json"; commit "$K2"
printf '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"copy","dest":"../escape.md"}}}\n' \
    > "$K2/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$K2" --adopt); rc=$?
[ $rc -eq 4 ] && grep -q '^  unmapped  .kiro/hooks/lint-on-save.json .*not an allowed destination' <<<"$out" \
    && pass "a decisions.json copy to ../ stays unmapped, exit 4" || fail "decision escape dry run (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$K2" --adopt --apply); rc=$?
[ $rc -eq 4 ] && [ ! -e "$TMP/escape.md" ] && pass "and --apply writes nothing outside the project" || fail "decision escape apply (rc=$rc)" "$out"
printf '{"version":1,"unmapped":{".kiro/hooks/lint-on-save.json":{"action":"copy","dest":"docs/sdlc/specs/kiro-hooks/lint-on-save.json"}}}\n' \
    > "$K2/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$K2" --adopt); rc=$?
[ $rc -eq 0 ] && grep -q 'lint-on-save.json -> docs/sdlc/specs/kiro-hooks/lint-on-save.json' <<<"$out" \
    && pass "a copy under docs/sdlc/specs/ is accepted (I6)" || fail "allowed decision dest (rc=$rc)" "$out"

B="$TMP/broken-decisions"; adopt_fixture cursor "$B"; mkdir -p "$B/.ai/reports/adopt-2000-01-01"
printf '{"version":' > "$B/.ai/reports/adopt-2000-01-01/decisions.json"
out=$(python3 "$UPDATE" "$B" 2>&1); rc=$?
[ $rc -eq 0 ] && ! grep -q Traceback <<<"$out" && grep -q '^  hint      adopt state unreadable' <<<"$out" \
    && pass "a truncated decisions.json is a hint in the plain dry run, not a traceback" || fail "plain dry run on broken decisions (rc=$rc)" "$out"
out=$(python3 "$UPDATE" "$B" --adopt --check 2>&1); rc=$?
[ $rc -eq 1 ] && [ "$(printf '%s\n' "$out" | wc -l)" -eq 1 ] && grep -q '^adopt state unreadable' <<<"$out" \
    && pass "and --adopt --check prints one line, exit 1" || fail "--adopt --check on broken decisions (rc=$rc)" "$out"

summary "project-adopt"
