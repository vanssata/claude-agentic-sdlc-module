#!/usr/bin/env bash
# install.sh --target codex: the Codex branch must set the managed routing keys
# and nothing else, register the guards without duplicating them, write exactly
# one managed AGENTS.md block, and survive being run twice over a config the
# user has edited.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
DIR="$TMP/codex"

toml_get() {  # toml_get <file> <dotted.key>
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
data = tomllib.load(open(sys.argv[1], "rb"))
for part in sys.argv[2].split("."):
    data = data.get(part) if isinstance(data, dict) else None
print("" if data is None else data)
PY
}

python3 -c 'import tomllib' 2>/dev/null || { echo "SKIP: python3 has no tomllib (needs 3.11+)"; exit 0; }

echo "== dry run writes nothing and shows the change"
mkdir -p "$TMP/probe"
out=$(CODEX_DIR="$TMP/probe" bash "$INSTALL" --target codex --dry-run 2>&1); rc=$?
[ $rc -eq 0 ] && pass "the dry run exits 0" || fail "dry run should exit 0" "$out"
[ -z "$(ls -A "$TMP/probe")" ] && pass "the target directory is untouched" || fail "the dry run wrote files" "$(ls -A "$TMP/probe")"
printf '%s' "$out" | grep -q 'would have added model = "gpt-5.6-sol"' && pass "the dry run names the model it would set" || fail "expected the model change in the dry run" "$out"
printf '%s' "$out" | grep -q '{{' && fail "an unrendered placeholder reached the output" || pass "the AGENTS.md block renders completely"
printf '%s' "$out" | grep -q 'claude-agentic:start' && pass "the managed block is shown" || fail "the managed block should be printed"

echo "== real install"
out=$(CODEX_DIR="$DIR" bash "$INSTALL" --target codex 2>&1); rc=$?
[ $rc -eq 0 ] && pass "install exits 0" || fail "install should exit 0" "$out"

for f in agents/ai-expert.toml agents/ai-reviewer.toml agents/ai-risk-strong.toml \
         agents/ai-planner-strong.toml agents/architect.toml agents/Explore.toml \
         hooks/ai-git-guard.sh hooks/ai-path-guard.sh hooks/ai-scope-guard.sh \
         hooks/codex-model-gate.py hooks/lib/ai-hook-common.sh hooks/ai-git-guard.json \
         hooks/ai-path-guard-defaults.json hooks.json config.toml AGENTS.md \
         skills/ai-task/state.py skills/ai-init/scaffold-ai.sh skills/usage-report/usage-report.py; do
    [ -e "$DIR/$f" ] && pass "$f installed" || fail "$f missing"
done
[ -x "$DIR/hooks/ai-git-guard.sh" ] && pass "the guards are executable" || fail "guards should be executable"
[ -x "$DIR/hooks/codex-model-gate.py" ] && pass "the model gate is executable" || fail "the gate should be executable"
[ -e "$DIR/hooks/cap-large-read.py" ] && fail "cap-large-read has no Codex event to fire on and must not be installed" \
    || pass "cap-large-read is not installed (Codex has no hookable Read tool)"
[ -e "$DIR/hooks/fable-gate.py" ] && fail "the Fable gate is Claude-only" || pass "the Fable gate is not installed"

echo "== the session defaults to Sol at high effort"
[ "$(toml_get "$DIR/config.toml" model)" = "gpt-5.6-sol" ] && pass "model = gpt-5.6-sol" || fail "model should be gpt-5.6-sol, got $(toml_get "$DIR/config.toml" model)"
[ "$(toml_get "$DIR/config.toml" model_reasoning_effort)" = "high" ] && pass "model_reasoning_effort = high" || fail "effort should be high"
[ "$(toml_get "$DIR/config.toml" agents.enabled)" = "True" ] && pass "agents are enabled" || fail "agents.enabled should be true"
[ "$(toml_get "$DIR/config.toml" agents.default_subagent_model)" = "gpt-5.6-terra" ] && pass "subagents default to Terra" || fail "subagent default should be Terra"
[ "$(toml_get "$DIR/config.toml" agents.default_subagent_reasoning_effort)" = "medium" ] && pass "subagents default to medium effort" || fail "subagent effort should be medium"
[ "$(toml_get "$DIR/config.toml" agents.max_concurrent_threads_per_session)" = "6" ] && pass "concurrency is bounded" || fail "max_concurrent_threads_per_session should be 6"

echo "== hooks.json"
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/hooks.json")
[ "$n" = 4 ] && pass "four PreToolUse guards registered" || fail "expected 4 PreToolUse commands, got $n"
jq -e '.hooks.PreToolUse[] | select(.matcher | test("apply_patch")) | .hooks[0].command | test("ai-scope-guard")' "$DIR/hooks.json" >/dev/null \
    && pass "the scope guard watches apply_patch" || fail "the scope guard should match apply_patch"
jq -e '.hooks.SubagentStop[0].hooks[0].command | test("codex-model-gate")' "$DIR/hooks.json" >/dev/null \
    && pass "the model gate listens on SubagentStop" || fail "SubagentStop hook missing"

echo "== the managed AGENTS.md block"
[ "$(grep -c 'claude-agentic:start' "$DIR/AGENTS.md")" = 1 ] && pass "exactly one managed block" || fail "expected one managed block"
grep -q 'gpt-5.6-terra' "$DIR/AGENTS.md" && pass "the block names the BALANCED model" || fail "the block should name Terra"
grep -q 'gpt-6-astra' "$DIR/AGENTS.md" && pass "the block names the EXPERT model" || fail "the block should name Astra"
grep -q 'ai-task' "$DIR/AGENTS.md" && pass "the block carries the pipeline contract" || fail "the pipeline contract is missing"

echo "== re-install is idempotent"
before=$(cd "$DIR" && find . -type f ! -name '*.bak' -print0 | sort -z | xargs -0 sha256sum)
CODEX_DIR="$DIR" bash "$INSTALL" --target codex >/dev/null 2>&1
after=$(cd "$DIR" && find . -type f ! -name '*.bak' -print0 | sort -z | xargs -0 sha256sum)
[ "$before" = "$after" ] && pass "a second install changes no file" || fail "the second install changed files" "$(diff <(printf '%s' "$before") <(printf '%s' "$after") | head -10)"
[ "$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/hooks.json")" = 4 ] && pass "hook entries are not duplicated" || fail "hooks duplicated"
[ "$(grep -c 'claude-agentic:start' "$DIR/AGENTS.md")" = 1 ] && pass "the managed block is not duplicated" || fail "block duplicated"

echo "== a user-owned config survives untouched apart from the managed keys"
DIR2="$TMP/codex2"; mkdir -p "$DIR2"
cat > "$DIR2/config.toml" <<'CFG'
# my own notes, keep these
model = "gpt-6-astra"
model_reasoning_effort = "xhigh"
service_tier = "fast"

[projects."/home/me/work"]
trust_level = "trusted"

[mcp_servers.docs]
url = "https://developers.openai.com/mcp"

[agents]
interrupt_message = false

[marketplaces.personal]
source_type = "git"
CFG
cp "$DIR2/config.toml" "$TMP/config.orig"
CODEX_DIR="$DIR2" bash "$INSTALL" --target codex >/dev/null 2>&1
[ "$(toml_get "$DIR2/config.toml" model)" = "gpt-5.6-sol" ] && pass "the managed model key is updated in place" || fail "model should be gpt-5.6-sol"
[ "$(toml_get "$DIR2/config.toml" model_reasoning_effort)" = "high" ] && pass "the managed effort key is updated in place" || fail "effort should be high"
[ "$(toml_get "$DIR2/config.toml" service_tier)" = "fast" ] && pass "an unrelated top-level key survives" || fail "service_tier was lost"
[ "$(toml_get "$DIR2/config.toml" mcp_servers.docs.url)" = "https://developers.openai.com/mcp" ] && pass "an MCP server survives" || fail "the MCP server was lost"
[ "$(toml_get "$DIR2/config.toml" marketplaces.personal.source_type)" = "git" ] && pass "a marketplace table survives" || fail "the marketplace was lost"
[ "$(toml_get "$DIR2/config.toml" agents.interrupt_message)" = "False" ] && pass "an unmanaged key inside [agents] survives" || fail "agents.interrupt_message was lost"
[ "$(toml_get "$DIR2/config.toml" agents.default_subagent_model)" = "gpt-5.6-terra" ] && pass "the managed [agents] keys are added alongside it" || fail "the subagent default was not added"
grep -q '# my own notes, keep these' "$DIR2/config.toml" && pass "comments survive" || fail "a comment was dropped"
[ -f "$DIR2/config.toml.bak" ] && pass "the old config is backed up" || fail "no config.toml.bak"
cmp -s "$TMP/config.orig" "$DIR2/config.toml.bak" && pass "the backup is the original file" || fail "the backup does not match the original"
python3 -c 'import sys,tomllib;tomllib.load(open(sys.argv[1],"rb"))' "$DIR2/config.toml" \
    && pass "the edited config still parses" || fail "the edited config is not valid TOML"

echo "== a malformed config is left alone"
DIR3="$TMP/codex3"; mkdir -p "$DIR3"
printf 'this is not = = toml\n' > "$DIR3/config.toml"
out=$(CODEX_DIR="$DIR3" bash "$INSTALL" --target codex 2>&1); rc=$?
[ $rc -ne 0 ] && pass "a config that does not parse aborts the install" || fail "expected a non-zero exit" "$out"
grep -qx 'this is not = = toml' "$DIR3/config.toml" && pass "the unparseable config is left exactly as it was" || fail "the broken config was modified"

echo "== an existing third-party hook survives the merge"
DIR4="$TMP/codex4"; mkdir -p "$DIR4"
jq -n '{hooks:{PreToolUse:[{matcher:"Bash",hooks:[{type:"command",command:"my-own-guard.sh"}]}]}}' > "$DIR4/hooks.json"
CODEX_DIR="$DIR4" bash "$INSTALL" --target codex >/dev/null 2>&1
jq -e '[.hooks.PreToolUse[].hooks[].command] | index("my-own-guard.sh")' "$DIR4/hooks.json" >/dev/null \
    && pass "the user's own hook is kept" || fail "the user's hook was clobbered"
[ "$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR4/hooks.json")" = 5 ] \
    && pass "our four guards are appended alongside it" || fail "expected 5 PreToolUse commands"

echo "== a hand-edited git guard config survives a re-install"
jq '.protected_branches += ["develop"]' "$DIR/hooks/ai-git-guard.json" > "$TMP/g.json" && mv "$TMP/g.json" "$DIR/hooks/ai-git-guard.json"
CODEX_DIR="$DIR" bash "$INSTALL" --target codex >/dev/null 2>&1
jq -e '.protected_branches | index("develop")' "$DIR/hooks/ai-git-guard.json" >/dev/null \
    && pass "a local edit to ai-git-guard.json is preserved" || fail "the user's git guard config was overwritten"

echo "== backups never land inside skills/"
printf 'stale\n' > "$DIR/skills/ai-init/EXTRA.md"
CODEX_DIR="$DIR" bash "$INSTALL" --target codex >/dev/null 2>&1
[ -z "$(ls -d "$DIR"/skills/*.bak 2>/dev/null)" ] && pass "no *.bak directory is left in skills/" || fail "a backup was left in skills/"
[ -d "$DIR/backups/skills/ai-init" ] && pass "the backup went to backups/skills/" || fail "backup not found in backups/skills/"

summary "codex install"
