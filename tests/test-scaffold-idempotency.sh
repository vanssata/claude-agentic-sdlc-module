#!/usr/bin/env bash
# scaffold-ai.sh must be safe to run repeatedly: it creates what is missing and
# never touches what exists. That property is what lets /ai-init be re-run on a
# project whose .ai/ has been edited by hand.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

SCAFFOLD="$PLUGIN_ROOT/skills/ai-init/scaffold-ai.sh"
export CLAUDE_AGENTIC_TEMPLATES="$PLUGIN_ROOT/skills/ai-init/templates"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
ROOT="$TMP/project"; mkdir -p "$ROOT"

echo "== first run"
out=$(bash "$SCAFFOLD" "$ROOT" 2>&1)
printf '%s' "$out" | grep -q 'created in' && pass "first run creates the tree" || fail "first run should create files" "$out"

EXPECTED=$(find "$CLAUDE_AGENTIC_TEMPLATES/.ai" -type f | wc -l)
ACTUAL=$(find "$ROOT/.ai" -type f | wc -l)
[ "$EXPECTED" = "$ACTUAL" ] && pass "every template file was copied ($ACTUAL)" || fail "file count mismatch" "expected $EXPECTED, got $ACTUAL"

for f in AGENTS.md policies/risk-tiers.json policies/safety.md project/overview.md \
         agents/manager.md workflows/feature.md templates/release-report.md state/README.md; do
    [ -f "$ROOT/.ai/$f" ] && pass ".ai/$f exists" || fail ".ai/$f missing"
done

grep -q '.ai/state/\*.json' "$ROOT/.gitignore" && pass ".gitignore excludes the state file" || fail ".gitignore should exclude state"
grep -q 'claude-agentic:start' "$ROOT/CLAUDE.md" && pass "CLAUDE.md carries the managed block" || fail "CLAUDE.md should carry the block"

echo "== second run"
out=$(bash "$SCAFFOLD" "$ROOT" 2>&1)
printf '%s' "$out" | grep -q 'nothing to do' && pass "second run reports nothing to do" || fail "second run should be a no-op" "$out"

gi_lines=$(grep -c 'claude-agentic' "$ROOT/.gitignore")
[ "$gi_lines" = 1 ] && pass ".gitignore snippet is not duplicated" || fail ".gitignore duplicated" "$gi_lines copies"
md_blocks=$(grep -c 'claude-agentic:start' "$ROOT/CLAUDE.md")
[ "$md_blocks" = 1 ] && pass "the CLAUDE.md block is not duplicated" || fail "CLAUDE.md block duplicated" "$md_blocks copies"

echo "== hand-edited files survive"
printf '# my own notes\n' > "$ROOT/.ai/project/overview.md"
printf 'custom\n' >> "$ROOT/CLAUDE.md"
bash "$SCAFFOLD" "$ROOT" >/dev/null 2>&1
grep -q 'my own notes' "$ROOT/.ai/project/overview.md" && pass "a hand-edited template is not overwritten" || fail "hand edits must survive"
grep -q 'custom' "$ROOT/CLAUDE.md" && pass "hand-edited CLAUDE.md content survives" || fail "CLAUDE.md edits must survive"

echo "== an existing CLAUDE.md is extended, not replaced"
ROOT2="$TMP/project2"; mkdir -p "$ROOT2"
printf '# Existing project\n\n## Commands\n\nmake test\n' > "$ROOT2/CLAUDE.md"
bash "$SCAFFOLD" "$ROOT2" >/dev/null 2>&1
grep -q 'make test' "$ROOT2/CLAUDE.md" && pass "existing CLAUDE.md content is kept" || fail "existing content must be kept"
grep -q 'claude-agentic:start' "$ROOT2/CLAUDE.md" && pass "the block is appended to it" || fail "block should be appended"

echo "== an existing .gitignore is appended to"
ROOT3="$TMP/project3"; mkdir -p "$ROOT3"
printf 'vendor/\nnode_modules/' > "$ROOT3/.gitignore"   # deliberately no trailing newline
bash "$SCAFFOLD" "$ROOT3" >/dev/null 2>&1
head -2 "$ROOT3/.gitignore" | grep -q 'vendor/' && pass "existing .gitignore entries are kept" || fail "existing entries must be kept"
grep -q '^node_modules/$' "$ROOT3/.gitignore" && pass "a missing trailing newline does not corrupt the last entry" || fail "last entry was corrupted" "$(cat "$ROOT3/.gitignore")"

summary "scaffold-ai.sh"
