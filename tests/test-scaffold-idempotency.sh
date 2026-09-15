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

echo "== both instruction files can coexist over one shared .ai/"
ROOT4="$TMP/project4"; mkdir -p "$ROOT4"
bash "$SCAFFOLD" "$ROOT4" --runtime both >/dev/null 2>&1
grep -q 'claude-agentic:start' "$ROOT4/CLAUDE.md" && pass "CLAUDE.md carries the block" || fail "CLAUDE.md should carry the block"
grep -q 'claude-agentic:start' "$ROOT4/AGENTS.md" && pass "AGENTS.md carries the block" || fail "AGENTS.md should carry the block"
[ "$(find "$ROOT4" -maxdepth 1 -name '.ai' | wc -l)" = 1 ] && pass "there is exactly one .ai/ tree" || fail "expected one .ai/ tree"
grep -q 'ai-task' "$ROOT4/AGENTS.md" && pass "AGENTS.md names the same pipeline entry point" || fail "AGENTS.md should name /ai-task"
out=$(bash "$SCAFFOLD" "$ROOT4" --runtime both 2>&1)
printf '%s' "$out" | grep -q 'nothing to do' && pass "a dual-runtime scaffold is idempotent too" || fail "second run should be a no-op" "$out"
[ "$(grep -c 'claude-agentic:start' "$ROOT4/AGENTS.md")" = 1 ] && pass "the AGENTS.md block is not duplicated" || fail "AGENTS.md block duplicated"

echo "== a Codex-only project gets no stray CLAUDE.md"
ROOT5="$TMP/project5"; mkdir -p "$ROOT5"
bash "$SCAFFOLD" "$ROOT5" --runtime codex >/dev/null 2>&1
[ -e "$ROOT5/AGENTS.md" ] && pass "AGENTS.md is created" || fail "AGENTS.md missing"
[ -e "$ROOT5/CLAUDE.md" ] && fail "a Codex-only scaffold must not create CLAUDE.md" || pass "no CLAUDE.md is created"
[ -f "$ROOT5/.ai/policies/risk-tiers.json" ] && pass "the shared .ai/ tree is still created" || fail ".ai/ should be created for Codex too"

echo "== auto-detection follows what the project already declares"
ROOT6="$TMP/project6"; mkdir -p "$ROOT6"
printf '# existing\n' > "$ROOT6/AGENTS.md"
bash "$SCAFFOLD" "$ROOT6" >/dev/null 2>&1
grep -q 'claude-agentic:start' "$ROOT6/AGENTS.md" && pass "an existing AGENTS.md is extended" || fail "AGENTS.md should be extended"
grep -q '# existing' "$ROOT6/AGENTS.md" && pass "its content survives" || fail "existing AGENTS.md content must survive"
[ -e "$ROOT6/CLAUDE.md" ] && fail "auto must not add CLAUDE.md to an AGENTS.md project" || pass "no CLAUDE.md is added"

echo "== an unknown runtime is rejected"
out=$(bash "$SCAFFOLD" "$TMP/project7" --runtime everything 2>&1); rc=$?
[ $rc -ne 0 ] && pass "--runtime everything is rejected" || fail "an unknown runtime should fail" "$out"

echo "== project-scaffold.sh covers the same ground"
SCAFFOLD2="$PLUGIN_ROOT/hooks/project-scaffold.sh"
ROOT8="$TMP/project8"; mkdir -p "$ROOT8"
bash "$SCAFFOLD2" "$ROOT8" --runtime both >/dev/null 2>&1
for f in docs/sdlc/README.md docs/sdlc/adr/TEMPLATE.md .claude/settings.json .claude/memory/README.md \
         .codex/config.toml .codex/memory/README.md CLAUDE.md AGENTS.md; do
    [ -e "$ROOT8/$f" ] && pass "$f scaffolded" || fail "$f missing"
done
[ "$(find "$ROOT8/docs/sdlc" -name 'TEMPLATE.md' | wc -l)" = 4 ] && pass "the SDLC templates are created once, not per runtime" || fail "SDLC templates duplicated"
before=$(cd "$ROOT8" && find . -type f -print0 | sort -z | xargs -0 sha256sum)
out=$(bash "$SCAFFOLD2" "$ROOT8" --runtime both 2>&1)
after=$(cd "$ROOT8" && find . -type f -print0 | sort -z | xargs -0 sha256sum)
[ "$before" = "$after" ] && pass "a second project scaffold changes no file" || fail "the second run changed files"
printf '%s' "$out" | grep -q 'nothing to do' && pass "it reports nothing to do" || fail "second run should be a no-op" "$out"

summary "scaffold-ai.sh"
