#!/usr/bin/env bash
# install.sh: rendering must be complete and correct for every plan/fable
# combination, and a real install into a scratch CLAUDE_DIR must be idempotent.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== dry run renders for every plan"
for combo in "max yes:xhigh:fable[1m]" "max no:high:Opus 5 [1m]" "pro no:high:Opus 5"; do
    args="${combo%%:*}"; rest="${combo#*:}"; effort="${rest%%:*}"; model="${rest#*:}"
    set -- $args
    out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan "$1" --fable "$2" --dry-run 2>&1)
    rc=$?
    [ $rc -eq 0 ] && pass "--plan $1 --fable $2 exits 0" || fail "--plan $1 --fable $2 should exit 0" "$out"
    printf '%s' "$out" | grep -q '{{' && fail "--plan $1 --fable $2 left an unrendered placeholder" || pass "--plan $1 --fable $2 renders every placeholder"
    printf '%s' "$out" | grep -q "effort: $effort" && pass "--plan $1 --fable $2 renders architect effort $effort" || fail "expected effort: $effort" "$out"
    printf '%s' "$out" | grep -qF "$model" && pass "--plan $1 --fable $2 names $model" || fail "expected $model in the output" "$out"
    printf '%s' "$out" | grep -q 'nothing written' && pass "--plan $1 --fable $2 writes nothing" || fail "dry run should write nothing"
done

echo "== pro: opusplan session, EXPERT tier pinned to opus"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan pro --dry-run 2>&1)
printf '%s' "$out" | grep -q '"model": "opusplan"' && pass "pro sets the session model to opusplan" || fail "pro should set opusplan" "$out"
printf '%s' "$out" | grep -q 'Opus 5 in plan mode' && pass "pro names opusplan in the CLAUDE.md block" || fail "block should explain opusplan" "$out"
printf '%s' "$out" | grep -q '^model: opus' && pass "pro pins model: opus on the EXPERT agents" || fail "EXPERT agents should pin opus on pro" "$out"
printf '%s' "$out" | grep -q 'solo' && pass "the block mentions the solo pipeline profile" || fail "block should mention the solo profile" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --fable yes --dry-run 2>&1)
printf '%s' "$out" | grep -q '^model: opus' && fail "max must not pin opus on the EXPERT agents" "$out" || pass "max leaves the EXPERT agents on the session model"

echo "== plan detection maps a Team org to the pro profile"
HOME_T="$TMP/home-team"; mkdir -p "$HOME_T"
printf '{"oauthAccount":{"organizationType":"claude_team"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1)
printf '%s' "$out" | grep -q 'plan=pro' && pass "claude_team is detected as the pro profile" || fail "team org should map to pro" "$out"

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
         skills/project-update/SKILL.md skills/project-update/update.py skills/project-update/history/index.json; do
    [ -e "$DIR/$f" ] && pass "$f installed" || fail "$f missing"
done
[ -x "$DIR/hooks/ai-git-guard.sh" ] && pass "hooks are executable" || fail "hooks should be executable"
[ -x "$DIR/skills/ai-init/scaffold-ai.sh" ] && pass "scaffold-ai.sh is executable" || fail "scaffold should be executable"
grep -q 'effort: high' "$DIR/agents/ai-expert.md" && pass "ai-expert renders at high on max" || fail "expert effort wrong"
grep -q '^model:' "$DIR/agents/ai-expert.md" && fail "ai-expert must NOT pin a model" || pass "ai-expert omits model: so it inherits the Opus session"
grep -q '^model: fable\[1m\]' "$DIR/agents/architect.md" && pass "architect alone is pinned to fable[1m] on max+fable" || fail "architect should pin fable[1m]"
grep -q 'effort: xhigh' "$DIR/agents/architect.md" && pass "architect runs at xhigh on Fable" || fail "architect effort wrong"

echo "== real pro install"
DIRP="$TMP/claude-pro"; mkdir -p "$DIRP"
CLAUDE_DIR="$DIRP" bash "$INSTALL" --plan pro >/dev/null 2>&1 && pass "pro install exits 0" || fail "pro install should exit 0"
grep -q '^model: opus' "$DIRP/agents/ai-expert.md" && pass "pro: ai-expert pins opus" || fail "pro: ai-expert should pin opus"
grep -q '^model: opus' "$DIRP/agents/architect.md" && pass "pro: architect pins opus" || fail "pro: architect should pin opus"
grep -q '^effort: high' "$DIRP/agents/ai-expert.md" && pass "pro: ai-expert runs at high" || fail "pro: expert effort wrong"
[ "$(jq -r .model "$DIRP/settings.json")" = "opusplan" ] && pass "pro: settings.json model is opusplan" || fail "pro: model not opusplan"
[ "$(jq -r '.fallbackModel[0]' "$DIRP/settings.json")" = "sonnet" ] && pass "pro: fallback is sonnet" || fail "pro: fallback wrong"
[ "$(jq -r .effortLevel "$DIRP/settings.json")" = "medium" ] && pass "pro: default effort is medium" || fail "pro: effort wrong"
grep -q '^model: opus$' "$DIR/agents/architect.md" && fail "max: architect must not pin opus" || pass "max: architect is not pinned to opus"

echo "== settings.json"
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/settings.json")
[ "$n" = 4 ] && pass "four PreToolUse hooks registered" || fail "expected 4 PreToolUse commands, got $n"
jq -e '.hooks.Setup[0].hooks[0].command | test("project-scaffold")' "$DIR/settings.json" >/dev/null \
    && pass "the Setup:init scaffold hook is registered" || fail "Setup hook missing"
[ "$(jq -r .model "$DIR/settings.json")" = "opus[1m]" ] && pass "the max session model is Opus 5 [1m], not Fable" || fail "model not set"
[ "$(jq -r .effortLevel "$DIR/settings.json")" = "medium" ] && pass "the default effort is medium" || fail "effort not set"
jq -e '.availableModels | index("fable[1m]")' "$DIR/settings.json" >/dev/null && pass "fable[1m] stays available for architect" || fail "fable should remain in availableModels"
DIRN="$TMP/claude-nofable"; mkdir -p "$DIRN"
CLAUDE_DIR="$DIRN" bash "$INSTALL" --plan max --fable no >/dev/null 2>&1
grep -q '^model:' "$DIRN/agents/architect.md" && fail "with --fable no, architect must inherit the session" || pass "with --fable no, architect inherits the Opus session"
jq -e '.availableModels | index("fable[1m]")' "$DIRN/settings.json" >/dev/null && fail "fable should be removed with --fable no" || pass "with --fable no, fable is not offered"
[ "$(jq -r .autoCompactWindow "$DIR/settings.json")" = "600000" ] && pass "the compaction window is set" || fail "compaction not set"
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
[ "$n" = 4 ] && pass "hook entries are not duplicated on re-install" || fail "hooks duplicated: $n"
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
[ "$(jq '[.hooks.PreToolUse[].hooks[].command]|length' "$DIR2/settings.json")" = 5 ] \
  && pass "our four PreToolUse hooks are appended alongside it" || fail "expected 5 hook commands total"
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
