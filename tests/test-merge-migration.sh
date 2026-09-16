#!/usr/bin/env bash
# Behaviour that only exists because this plugin absorbed claude-routing: the
# superseded agent, the legacy unmarked CLAUDE.md section, and the two scaffolds
# composing into one project layout without duplicating anything.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== the superseded reviewer agent"
DIR="$TMP/a"; mkdir -p "$DIR/agents"
cp "$PLUGIN_ROOT/agents/superseded/reviewer.md" "$DIR/agents/reviewer.md"
out=$(CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes 2>&1)
[ -f "$DIR/agents/reviewer.md.superseded" ] && pass "an unmodified reviewer.md is retired" || fail "should be retired" "$out"
[ ! -f "$DIR/agents/reviewer.md" ] && pass "and no longer competes with ai-reviewer" || fail "reviewer.md should be gone"
[ -f "$DIR/agents/ai-reviewer.md" ] && pass "ai-reviewer takes its place" || fail "ai-reviewer missing"

DIR2="$TMP/b"; mkdir -p "$DIR2/agents"
{ cat "$PLUGIN_ROOT/agents/superseded/reviewer.md"; echo "my own extra rule"; } > "$DIR2/agents/reviewer.md"
out=$(CLAUDE_DIR="$DIR2" bash "$INSTALL" --plan max --fable yes 2>&1)
[ -f "$DIR2/agents/reviewer.md" ] && pass "an edited reviewer.md is kept" || fail "an edited file must not be removed"
grep -q 'my own extra rule' "$DIR2/agents/reviewer.md" && pass "with the user's edit intact" || fail "edit lost"
printf '%s' "$out" | grep -q 'you have edited it' && pass "and the conflict is reported" || fail "should report the conflict" "$out"

echo "== a pre-plugin unmarked routing section is migrated"
DIR3="$TMP/c"; mkdir -p "$DIR3"
printf '# Model allocation by task and scope\n\nold hand-written rules\n\n# Something else of mine\n\nkeep me\n' > "$DIR3/CLAUDE.md"
out=$(CLAUDE_DIR="$DIR3" bash "$INSTALL" --plan max --fable yes 2>&1)
printf '%s' "$out" | grep -q "migrated an unmarked" && pass "the unmarked section is migrated" || fail "should migrate it" "$out"
grep -q 'old hand-written rules' "$DIR3/CLAUDE.md" && fail "the superseded rules should be gone" || pass "its superseded rules are removed"
grep -q 'keep me' "$DIR3/CLAUDE.md" && pass "unrelated sections are kept" || fail "unrelated content must survive"
[ "$(grep -c 'claude-agentic:start' "$DIR3/CLAUDE.md")" = 1 ] && pass "one managed block results" || fail "expected one block"

echo "== both scaffolds compose into one project"
DIR4="$TMP/d"; mkdir -p "$DIR4"
CLAUDE_DIR="$DIR4" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
REPO="$TMP/repo"; mkdir -p "$REPO"
CLAUDE_ROUTING_TEMPLATES="$DIR4/skills/project-init/templates" bash "$DIR4/hooks/project-scaffold.sh" "$REPO" >/dev/null
CLAUDE_AGENTIC_TEMPLATES="$DIR4/skills/ai-init/templates" bash "$DIR4/skills/ai-init/scaffold-ai.sh" "$REPO" >/dev/null

for f in docs/sdlc/README.md docs/sdlc/intent/TEMPLATE.md docs/sdlc/specs/TEMPLATE.md \
         docs/sdlc/plans/TEMPLATE.md docs/sdlc/adr/TEMPLATE.md .claude/settings.json \
         .claude/memory/README.md .ai/AGENTS.md .ai/policies/risk-tiers.json CLAUDE.md .gitignore; do
    [ -e "$REPO/$f" ] && pass "$f created" || fail "$f missing"
done

[ "$(grep -c 'claude-agentic:start' "$REPO/CLAUDE.md")" = 1 ] && pass "the project CLAUDE.md carries one agent block" || fail "expected one block in the project CLAUDE.md"
grep -q '/ai-task' "$REPO/CLAUDE.md" && pass "and points at the pipeline as the default route" || fail "should mention /ai-task"
grep -q '.claude/settings.local.json' "$REPO/.gitignore" && pass ".gitignore covers the sdlc layout" || fail "sdlc gitignore entries missing"
grep -q '.ai/state/\*.json' "$REPO/.gitignore" && pass "and the .ai state file" || fail ".ai gitignore entries missing"
[ "$(grep -c 'claude-agentic' "$REPO/.gitignore")" = 2 ] && pass "with one section each, not duplicated" || fail "gitignore sections wrong: $(grep -c 'claude-agentic' "$REPO/.gitignore")"

echo "== running both scaffolds again changes nothing"
before=$(find "$REPO" -type f | sort | xargs md5sum 2>/dev/null | md5sum)
CLAUDE_ROUTING_TEMPLATES="$DIR4/skills/project-init/templates" bash "$DIR4/hooks/project-scaffold.sh" "$REPO" >/dev/null
CLAUDE_AGENTIC_TEMPLATES="$DIR4/skills/ai-init/templates" bash "$DIR4/skills/ai-init/scaffold-ai.sh" "$REPO" >/dev/null
after=$(find "$REPO" -type f | sort | xargs md5sum 2>/dev/null | md5sum)
[ "$before" = "$after" ] && pass "the combined scaffold is idempotent" || fail "a second run changed files"

echo "== every agent this plugin ships declares its tier"
for f in "$PLUGIN_ROOT"/agents/*.md; do
    name=$(basename "$f")
    grep -qE '^effort:' "$f" || fail "$name declares no effort:"
done
pass "every agent declares effort:"
grep -q '{{EXPERT_MODEL_LINE}}' "$PLUGIN_ROOT/agents/architect.md.tmpl" && pass "architect's model line is rendered per plan" || fail "architect.md.tmpl should carry the EXPERT model placeholder"
grep -qE '^model:' "$DIR4/agents/architect.md" && fail "on max, architect must not pin a model" || pass "on max, architect inherits the session model"

summary "merge migration"
