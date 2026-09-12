#!/usr/bin/env bash
# install.sh: rendering must be complete and correct for every plan/fable
# combination, and a real install into a scratch CLAUDE_DIR must be idempotent.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== dry run renders for every plan"
for combo in "max yes:xhigh:fable:Fable 5.1:Opus 5 [1m]" "max no:high:opus:Opus 5:Opus 5 [1m]" "pro no:high:opus:Opus 5:Sonnet 5"; do
    args="${combo%%:*}"; rest="${combo#*:}"; effort="${rest%%:*}"; rest="${rest#*:}"
    xmodel="${rest%%:*}"; rest="${rest#*:}"; model="${rest%%:*}"; session="${rest#*:}"
    set -- $args
    out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan "$1" --fable "$2" --dry-run 2>&1)
    rc=$?
    [ $rc -eq 0 ] && pass "--plan $1 --fable $2 exits 0" || fail "--plan $1 --fable $2 should exit 0" "$out"
    printf '%s' "$out" | grep -q '{{' && fail "--plan $1 --fable $2 left an unrendered placeholder" || pass "--plan $1 --fable $2 renders every placeholder"
    printf '%s' "$out" | grep -q "effort: $effort" && pass "--plan $1 --fable $2 sets EXPERT effort to $effort" || fail "expected effort: $effort" "$out"
    printf '%s' "$out" | grep -qx "model: $xmodel" && pass "--plan $1 --fable $2 pins ai-expert to $xmodel" || fail "expected model: $xmodel" "$out"
    printf '%s' "$out" | grep -qF "## $model (EXPERT)" && pass "--plan $1 --fable $2 names $model as EXPERT" || fail "expected '## $model (EXPERT)' in the output" "$out"
    printf '%s' "$out" | grep -qF "Session model is $session" && pass "--plan $1 --fable $2 runs the session on $session" || fail "expected a $session session" "$out"
    printf '%s' "$out" | grep -q 'nothing written' && pass "--plan $1 --fable $2 writes nothing" || fail "dry run should write nothing"
done
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --fable no --dry-run 2>&1)
printf '%s' "$out" | grep -q '"fable' && fail "--fable no must drop fable from the settings" "$out" || pass "--fable no drops fable from the settings"

echo "== dry run writes nothing at all"
PROBE="$TMP/probe"; mkdir -p "$PROBE"
CLAUDE_DIR="$PROBE" bash "$INSTALL" --plan max --dry-run >/dev/null 2>&1
[ -z "$(ls -A "$PROBE")" ] && pass "the target directory is untouched" || fail "dry run created files" "$(ls -A "$PROBE")"

echo "== bad arguments are rejected"
out=$(CLAUDE_DIR="$PROBE" bash "$INSTALL" --plan enterprise --dry-run 2>&1); rc=$?
[ $rc -ne 0 ] && pass "an unknown plan is rejected" || fail "unknown plan should fail" "$out"
out=$(CLAUDE_DIR="$PROBE" bash "$INSTALL" --plan max --fable maybe --dry-run 2>&1); rc=$?
[ $rc -ne 0 ] && pass "an unknown --fable value is rejected" || fail "unknown fable should fail" "$out"

echo "== real install into a scratch CLAUDE_DIR"
DIR="$TMP/claude"; mkdir -p "$DIR"
out=$(CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes 2>&1)
[ $? -eq 0 ] && pass "install exits 0" || fail "install should exit 0" "$out"

for f in agents/ai-expert.md agents/ai-reviewer.md agents/architect.md agents/Explore.md \
         agents/log-reader.md hooks/ai-git-guard.sh hooks/lib/ai-hook-common.sh \
         hooks/cap-large-read.py hooks/project-scaffold.sh hooks/ai-git-guard.json \
         skills/ai-init/SKILL.md skills/ai-init/scaffold-ai.sh skills/ai-task/state.py \
         skills/ai-audit/SKILL.md skills/ai-status/SKILL.md skills/project-init/SKILL.md \
         skills/sdlc-intent/SKILL.md skills/sdlc-spec/SKILL.md skills/sdlc-plan/SKILL.md \
         skills/ai-init/templates/.ai/AGENTS.md skills/project-init/templates/intent.md \
         skills/usage-report/SKILL.md skills/usage-report/usage-report.py; do
    [ -e "$DIR/$f" ] && pass "$f installed" || fail "$f missing"
done
[ -x "$DIR/hooks/ai-git-guard.sh" ] && pass "hooks are executable" || fail "hooks should be executable"
[ -x "$DIR/skills/ai-init/scaffold-ai.sh" ] && pass "scaffold-ai.sh is executable" || fail "scaffold should be executable"
grep -q 'effort: xhigh' "$DIR/agents/ai-expert.md" && pass "ai-expert renders at xhigh on max+fable" || fail "expert effort wrong"
grep -qx 'model: fable' "$DIR/agents/ai-expert.md" && pass "ai-expert pins fable on max+fable (the subagent default must not be inherited)" || fail "ai-expert should pin model: fable"
grep -qx 'model: opus' "$DIR/agents/architect.md" && pass "architect pins opus" || fail "architect should pin model: opus"

echo "== settings.json"
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/settings.json")
[ "$n" = 5 ] && pass "five PreToolUse hooks registered (four guards + fable-gate on a Fable install)" || fail "expected 5 PreToolUse commands, got $n"
jq -e '.hooks.Setup[0].hooks[0].command | test("project-scaffold")' "$DIR/settings.json" >/dev/null \
    && pass "the Setup:init scaffold hook is registered" || fail "Setup hook missing"
[ "$(jq -r .model "$DIR/settings.json")" = "opus[1m]" ] && pass "the session model is opus[1m] on Max" || fail "model not set to opus[1m]"
[ "$(jq -r .effortLevel "$DIR/settings.json")" = "medium" ] && pass "the default effort is medium" || fail "effort not set to medium"
[ "$(jq -r '.modelSettings["claude-opus-5"].effortLevel' "$DIR/settings.json")" = "medium" ] && pass "Opus runs at medium" || fail "opus effort not medium"
[ "$(jq -r .autoCompactWindow "$DIR/settings.json")" = "300000" ] && pass "the compaction window is set" || fail "compaction not set"
[ "$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL' "$DIR/settings.json")" = "sonnet" ] && pass "the subagent default is sonnet" || fail "subagent default not set"
grep -q 'claude-agentic:start' "$DIR/CLAUDE.md" && pass "the CLAUDE.md block is written" || fail "block missing"

echo "== backups never land inside skills/"
printf 'stale\n' > "$DIR/skills/ai-init/EXTRA.md"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ -z "$(ls -d "$DIR"/skills/*.bak 2>/dev/null)" ] \
    && pass "no *.bak directory is left in skills/ (they would load as duplicate skills)" \
    || fail "a backup was left in skills/" "$(ls -d "$DIR"/skills/*.bak)"
[ -d "$DIR/backups/skills/ai-init" ] && pass "the backup went to backups/skills/ instead" || fail "backup not found in backups/skills/"
mkdir -p "$DIR/skills/legacy.bak"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ ! -d "$DIR/skills/legacy.bak" ] && pass "a backup left by an older installer is moved out" || fail "stale .bak skill not cleaned up"

echo "== re-install is idempotent"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/settings.json")
[ "$n" = 5 ] && pass "hook entries are not duplicated on re-install" || fail "hooks duplicated: $n"
[ "$(jq '[.hooks.Setup[].hooks[].command] | length' "$DIR/settings.json")" = 1 ] \
    && pass "the Setup hook is not duplicated either" || fail "Setup hook duplicated"
b=$(grep -c 'claude-agentic:start' "$DIR/CLAUDE.md")
[ "$b" = 1 ] && pass "the CLAUDE.md block is not duplicated" || fail "block duplicated: $b copies"

echo "== a user edit to the git guard config survives a re-install"
jq '.protected_branches += ["develop"]' "$DIR/hooks/ai-git-guard.json" > "$TMP/g.json" && mv "$TMP/g.json" "$DIR/hooks/ai-git-guard.json"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
jq -e '.protected_branches | index("develop")' "$DIR/hooks/ai-git-guard.json" >/dev/null \
  && pass "a local edit to ai-git-guard.json is preserved" || fail "the user's git guard config was overwritten"

echo "== coexistence with a hook the plugin does not own"
DIR2="$TMP/claude2"; mkdir -p "$DIR2"
jq -n '{permissions:{allow:["Bash(ls:*)"]}, hooks:{PreToolUse:[{matcher:"Edit|Write",hooks:[{type:"command",command:"\"$HOME/.claude/hooks/vendor-write-guard.sh\""}]}]}}' > "$DIR2/settings.json"
CLAUDE_DIR="$DIR2" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
jq -e '[.hooks.PreToolUse[].hooks[].command] | index("\"$HOME/.claude/hooks/vendor-write-guard.sh\"")' "$DIR2/settings.json" >/dev/null \
  && pass "a third-party hook survives the merge" || fail "the user's own hook was clobbered"
[ "$(jq '[.hooks.PreToolUse[].hooks[].command]|length' "$DIR2/settings.json")" = 6 ] \
  && pass "our five PreToolUse hooks are appended alongside it" || fail "expected 6 hook commands total"
jq -e '.permissions.allow | index("Bash(ls:*)")' "$DIR2/settings.json" >/dev/null \
  && pass "unrelated settings keys are preserved" || fail "unrelated settings were lost"

echo "== migration off the predecessor plugin's block"
DIR3="$TMP/claude3"; mkdir -p "$DIR3"
printf '<!-- claude-routing:start -->\nrouting rules\n<!-- claude-routing:end -->\n\n# My own notes\n' > "$DIR3/CLAUDE.md"
out=$(CLAUDE_DIR="$DIR3" bash "$INSTALL" --plan max --fable yes 2>&1)
printf '%s' "$out" | grep -q 'migrated the claude-routing block' && pass "the migration is reported" || fail "migration should be reported" "$out"
[ "$(grep -c 'claude-agentic:start' "$DIR3/CLAUDE.md")" = 1 ] && pass "exactly one managed block remains" || fail "expected one block"
grep -q 'claude-routing:start' "$DIR3/CLAUDE.md" && fail "the predecessor block should have been migrated away" || pass "the claude-routing block is migrated away"
grep -q 'routing rules' "$DIR3/CLAUDE.md" && fail "the old block's content should be gone" || pass "its superseded content is removed"
grep -q '# My own notes' "$DIR3/CLAUDE.md" && pass "the user's own content is kept" || fail "user content must survive migration"

summary "install.sh"
