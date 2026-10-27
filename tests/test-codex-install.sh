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
# An isolated HOME: the plan must come from the test, never from this
# machine's ~/.codex/auth.json.
export HOME="$TMP/home"; mkdir -p "$HOME"

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
grep -q 'would have added model = "gpt-5.6-sol"' <<<"$out" && pass "the dry run names the model it would set" || fail "expected the model change in the dry run" "$out"
grep -q '{{' <<<"$out" && fail "an unrendered placeholder reached the output" || pass "the AGENTS.md block renders completely"
grep -q 'riskrails:start' <<<"$out" && pass "the managed block is shown" || fail "the managed block should be printed"
grep -q 'plan=pro (Pro)' <<<"$out" && pass "with no ChatGPT login the pro profile is assumed" || fail "no auth.json should fall back to pro" "$out"
grep -q -- '--codex-plan plus' <<<"$out" && pass "the fallback says how to pick plus" || fail "the fallback should mention --codex-plan plus" "$out"

echo "== the plus plan renders its own profile"
out=$(CODEX_DIR="$TMP/probe" bash "$INSTALL" --target codex --codex-plan plus --dry-run 2>&1); rc=$?
[ $rc -eq 0 ] && pass "--codex-plan plus exits 0" || fail "--codex-plan plus should exit 0" "$out"
grep -q 'plan=plus (Plus)' <<<"$out" && pass "plus is reported" || fail "plus should be reported" "$out"
grep -q 'would have added model_reasoning_effort = "medium"' <<<"$out" && pass "plus runs the session at medium" || fail "plus should set medium" "$out"
grep -q 'would have added max_concurrent_threads_per_session = 3' <<<"$out" && pass "plus caps agent threads at 3" || fail "plus should cap threads at 3" "$out"
grep -q 'ChatGPT Plus plan' <<<"$out" && pass "the AGENTS.md block names the Plus plan" || fail "block should name Plus" "$out"
grep -q '`xhigh` stays off' <<<"$out" && pass "the AGENTS.md block keeps xhigh off on Plus" || fail "block should keep xhigh off" "$out"
grep -q '{{' <<<"$out" && fail "plus left an unrendered placeholder" "$out" || pass "the plus block renders completely"
out=$(CODEX_DIR="$TMP/probe" bash "$INSTALL" --target codex --codex-plan team --dry-run 2>&1); rc=$?
[ $rc -ne 0 ] && pass "an unknown --codex-plan is rejected" || fail "unknown codex plan should fail" "$out"

echo "== the plan is read from the ChatGPT login"
HOME_P="$TMP/home-plus"; mkdir -p "$HOME_P/.codex"
jwt=$(python3 -c '
import base64, json
b64 = lambda d: base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")
print(b64({"alg":"none"}) + "." + b64({"https://api.openai.com/auth":{"chatgpt_plan_type":"plus"}}) + ".sig")')
printf '{"auth_mode":"chatgpt","tokens":{"id_token":"%s"}}' "$jwt" > "$HOME_P/.codex/auth.json"
out=$(HOME="$HOME_P" CODEX_DIR="$HOME_P/.codex" bash "$INSTALL" --target codex --dry-run 2>&1 </dev/null)
grep -q 'detected codex plan: plus' <<<"$out" && pass "chatgpt_plan_type=plus is detected" || fail "plus should be detected from auth.json" "$out"
grep -q 'plan=plus (Plus)' <<<"$out" && pass "the detected plan selects the plus profile" || fail "detected plus should select the plus profile" "$out"

echo "== real install"
out=$(CODEX_DIR="$DIR" bash "$INSTALL" --target codex 2>&1); rc=$?
[ $rc -eq 0 ] && pass "install exits 0" || fail "install should exit 0" "$out"

grep -q 'plan            pro' <<<"$out" && pass "the summary names the plan" || fail "summary should name the plan" "$out"

for f in agents/ai-discovery.toml agents/ai-reviewer.toml agents/log-reader.toml agents/architect.toml agents/Explore.toml \
         hooks/ai-git-guard.sh hooks/ai-path-guard.sh hooks/ai-scope-guard.sh \
         hooks/runtime-gate.py hooks/context-guard.py hooks/lib/ai-hook-common.sh hooks/ai-git-guard.json \
         hooks/ai-path-guard-defaults.json hooks.json config.toml AGENTS.md \
         skills/ai-task/state.py skills/ai-init/scaffold-ai.sh skills/usage-report/usage-report.py \
         hooks/ai-guard.py hooks/guard/__init__.py hooks/guard/common.py hooks/guard/ere.py \
         hooks/guard/git.py hooks/guard/paths.py hooks/guard/scope.py; do
    [ -e "$DIR/$f" ] && pass "$f installed" || fail "$f missing"
done
[ -x "$DIR/hooks/ai-git-guard.sh" ] && pass "the guards are executable" || fail "guards should be executable"
# The guards are shims over hooks/ai-guard.py and its guard/ package: the
# installed copy must run the port, not only hold its files.
payload() { jq -nc --arg c "$1" '{hook_event_name:"PreToolUse",tool_name:"Bash",cwd:"/",tool_input:{command:$c}}'; }
payload "git push --force" | "$DIR/hooks/ai-git-guard.sh" | grep -q '"permissionDecision":"deny"' \
    && pass "the installed git guard runs the port and denies a force push" \
    || fail "the installed git guard did not deny a force push"
[ -z "$(payload ls | "$DIR/hooks/ai-git-guard.sh")" ] \
    && pass "the installed git guard allows ls" || fail "the installed git guard should allow ls"
[ -x "$DIR/hooks/runtime-gate.py" ] && pass "the model gate is executable" || fail "the gate should be executable"
[ -e "$DIR/hooks/codex-model-gate.py" ] && fail "the codex-model-gate.py shim is gone (redesign 1.3)" || pass "the codex-model-gate.py shim is not installed"
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
jq -e '.hooks.SubagentStop[0].hooks[0].command | test("runtime-gate")' "$DIR/hooks.json" >/dev/null \
    && pass "the runtime gate listens on SubagentStop" || fail "SubagentStop hook missing"
jq -e '.hooks.SubagentStart[0].hooks[0].command | test("runtime-gate")' "$DIR/hooks.json" >/dev/null \
    && pass "and on SubagentStart, to count running agents" || fail "SubagentStart hook missing"
for ev in PreToolUse PostToolUse; do
    # Codex 0.155 multi-agent v2 names the tool collaborationspawn_agent (namespace
    # + name, no separator). A matcher of only [A-Za-z0-9_|] is an exact list in
    # Codex, so it must be a regex; Codex tests it unanchored, like jq's test().
    m=$(jq -r --arg e "$ev" '[.hooks[$e][] | select(.hooks[].command | test("runtime-gate")) | .matcher] | if length == 1 then .[0] else "" end' "$DIR/hooks.json")
    [ -n "$m" ] || fail "$ev: expected exactly one gate entry"
    grep -q '[^A-Za-z0-9_|]' <<<"$m" || fail "$ev gate matcher '$m' is an exact list in Codex, not a regex"
    for t in collaborationspawn_agent spawn_agent Agent; do
        jq -en --arg m "$m" --arg t "$t" '$t | test($m)' >/dev/null || fail "$ev gate matcher '$m' misses $t"
    done
    for t in Bash apply_patch AgentX wait_agent; do
        jq -en --arg m "$m" --arg t "$t" '$t | test($m)' >/dev/null && fail "$ev gate matcher '$m' also matches $t"
    done
done
pass "the gate's PreToolUse/PostToolUse matcher is a regex that sees collaborationspawn_agent, spawn_agent and Agent only"
[ "$(jq '[.hooks[]?[]?.hooks[]? | select(.command | test("codex-model-gate"))] | length' "$DIR/hooks.json")" = 0 ] \
    && pass "no codex-model-gate command is registered" || fail "codex-model-gate still registered"

# Codex has both compaction events and SessionStart, so the context guard is
# registered on the same three events it serves on the Claude side.
for ev in UserPromptSubmit PreCompact SessionStart; do
    n=$(jq --arg e "$ev" '[.hooks[$e][]?.hooks[]?.command | select(test("context-guard"))] | length' "$DIR/hooks.json")
    [ "$n" = 1 ] && pass "the context guard is registered once under $ev" || fail "expected one $ev registration, got $n"
done
[ "$(jq -r '.hooks.SessionStart[] | select(.hooks[].command | test("context-guard")) | .matcher' "$DIR/hooks.json")" \
    = "startup|resume|clear|compact" ] \
    && pass "on every SessionStart source, as on the Claude side" || fail "the SessionStart matcher is wrong"
[ "$(jq -r '.hooks.UserPromptSubmit[0].hooks[0].timeout' "$DIR/hooks.json")" = 5 ] \
    && pass "with the prompt path on the shorter timeout" || fail "UserPromptSubmit should time out at 5"

CODEX_DIR="$DIR" bash "$INSTALL" --target codex >/dev/null 2>&1
n=$(jq '[.hooks | to_entries[] | .value[] | .hooks[] | .command | select(test("context-guard"))] | length' "$DIR/hooks.json")
[ "$n" = 3 ] && pass "a second install does not duplicate any of the three" || fail "expected 3 registrations after a re-install, got $n"
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/hooks.json")
[ "$n" = 4 ] && pass "and the PreToolUse count is still four" || fail "PreToolUse should stay 4, got $n"

echo "== an install from before WP5 is upgraded, not doubled"
UP="$TMP/codex-upgrade"; mkdir -p "$UP/hooks" "$UP/agents"
DAY=$(date +%F)
printf '#!/usr/bin/env python3\n# the old shim\n' > "$UP/hooks/codex-model-gate.py"
mkdir -p "$UP/skills/status"; printf -- '---\nname: status\n---\nold\n' > "$UP/skills/status/SKILL.md"
STALE="code-implementer qa-runner qa-fixer db-migrator doc-lookup log-inspector sylius-i18n-keys"
# Redesign 2.4: nine agents and the four tier twins are no longer installed.
RETIRED_24="ai-context ai-expert ai-implementer ai-indexer ai-planner ai-release ai-risk ai-security ai-tester ai-reviewer-balanced ai-risk-strong ai-planner-strong ai-expert-strong"
for a in $STALE $RETIRED_24; do printf 'name = "%s"\n' "$a" > "$UP/agents/$a.toml"; done
printf 'old\n' > "$UP/agents/ai-reviewer.toml"; printf 'older\n' > "$UP/agents/ai-reviewer.toml.bak"
OLD='"$HOME/.codex/hooks/codex-model-gate.py"'
jq -n --arg c "$OLD" '{hooks:{PreToolUse:[{matcher:"Agent",hooks:[{type:"command",command:$c,timeout:5}]}],
    PostToolUse:[{matcher:"Agent",hooks:[{type:"command",command:$c,timeout:5}]}],
    SubagentStop:[{hooks:[{type:"command",command:$c,timeout:5}]},{hooks:[{type:"command",command:"my-stop.sh"}]}]}}' > "$UP/hooks.json"
out=$(CODEX_DIR="$UP" bash "$INSTALL" --target codex --codex-plan pro 2>&1)
[ "$(jq '[.hooks[]?[]?.hooks[]? | select(.command | test("codex-model-gate"))] | length' "$UP/hooks.json")" = 0 ] \
    && pass "an upgrade replaces every codex-model-gate command" || fail "a codex-model-gate command is left"
for ev in PreToolUse PostToolUse SubagentStart SubagentStop; do
    n=$(jq --arg e "$ev" '[.hooks[$e][]?.hooks[]? | select(.command | test("/hooks/runtime-gate\\.py"))] | length' "$UP/hooks.json")
    [ "$n" = 1 ] || fail "$ev has $n gate commands after the upgrade"
done
pass "exactly one gate command per event after the upgrade"
CODEX_DIR="$UP" bash "$INSTALL" --target codex --codex-plan pro >/dev/null 2>&1
[ "$(jq '[.hooks[]?[]?.hooks[]? | select(.command | test("-gate\\.py"))] | length' "$UP/hooks.json")" = 4 ] \
    && pass "a second install changes nothing" || fail "reinstall doubled or renamed the gate"
jq -e '[.hooks.SubagentStop[].hooks[].command] | index("my-stop.sh")' "$UP/hooks.json" >/dev/null \
    && pass "the user's own SubagentStop hook survives" || fail "user hook lost"
grep -q 'replaced: codex-model-gate.py hooks with runtime-gate.py — review the changed gate entries once in /hooks' <<<"$out" \
    && pass "the replacement is reported, with the /hooks re-trust reminder" || fail "replacement not reported" "$out"
[ ! -e "$UP/hooks/codex-model-gate.py" ] && grep -q '^# the old shim' "$UP/backups/$DAY/hooks/codex-model-gate.py" \
    && pass "the installed shim is retired into backups/<date>/hooks/" || fail "shim not retired" "$out"
for a in $STALE; do
    [ ! -e "$UP/agents/$a.toml" ] && [ -f "$UP/backups/$DAY/agents/$a.toml" ] || fail "agents/$a.toml not retired" "$out"
done
pass "the seven stale agents are retired into backups/<date>/agents/"
for a in $RETIRED_24; do
    [ ! -e "$UP/agents/$a.toml" ] && [ -f "$UP/backups/$DAY/agents/$a.toml" ] \
        && grep -q "retired: agents/$a.toml -> backups/$DAY/agents/$a.toml" <<<"$out" || fail "agents/$a.toml not retired (2.4)" "$out"
done
pass "the nine agents and four twins of redesign 2.4 are retired into backups/<date>/agents/"
got=$(cd "$UP/agents" && ls *.toml | sed 's/\.toml$//' | LC_ALL=C sort | paste -sd' ')
[ "$got" = "Explore ai-discovery ai-reviewer architect log-reader" ] && pass "and exactly the five agents are left" || fail "codex agents after the upgrade" "$got"
[ ! -e "$UP/skills/status" ] && [ -f "$UP/backups/$DAY/skills/status/SKILL.md" ] \
    && grep -q "retired: skills/status -> backups/$DAY/skills/status" <<<"$out" \
    && pass "skills/status is retired into backups/<date>/skills/ on the Codex home" || fail "skills/status not retired" "$out"
[ ! -e "$UP/agents/ai-reviewer.toml.bak" ] && [ "$(cat "$UP/backups/$DAY/agents/ai-reviewer.toml.bak")" = older ] \
    && pass "a *.bak beside a live agent moves to backups/<date>/agents/" || fail "agent .bak not swept" "$out"
[ -z "$(cd "$UP" && find . -path ./backups -prune -o -name '*.bak' -print)" ] \
    && pass "no *.bak is left outside backups/" || fail "*.bak left" "$(cd "$UP" && find . -path ./backups -prune -o -name '*.bak' -print)"

echo "== the managed AGENTS.md block"
[ "$(grep -c 'riskrails:start' "$DIR/AGENTS.md")" = 1 ] && pass "exactly one managed block" || fail "expected one managed block"
grep -q 'gpt-5.6-terra' "$DIR/riskrails/routing.md" && pass "routing.md names the BALANCED model" || fail "routing.md should name Terra"
grep -q 'gpt-6-astra' "$DIR/riskrails/routing.md" && pass "routing.md names the EXPERT model" || fail "routing.md should name Astra"
grep -q 'Models are tiers, not names' "$DIR/AGENTS.md" && pass "the block carries tiers, not model names" || fail "the block should carry tiers, not names"
grep -q 'rr-build' "$DIR/AGENTS.md" && pass "the block carries the pipeline contract" || fail "the pipeline contract is missing"

echo "== profile.json (R4)"
jq -e '.runtime == "codex" and (.plan == "plus" or .plan == "pro") and .fable == false and (.tiers.STRONG.model | length > 0)' \
    "$DIR/riskrails/profile.json" >/dev/null \
    && pass "profile.json written for the Codex install, tiers read from the Codex profile" || fail "codex profile.json missing or wrong"
grep -q 'riskrails' "$DIR/config.toml" && fail "riskrails leaked into config.toml" || pass "config.toml has no riskrails"
out=$(CODEX_DIR="$TMP/probe-profile" bash "$INSTALL" --target codex --codex-plan plus --dry-run 2>&1)
grep -q "^== profile.json (plan tables): $TMP/probe-profile/riskrails/profile.json" <<<"$out" \
    && pass "--dry-run lists the Codex profile.json" || fail "codex dry run should list profile.json"
[ ! -e "$TMP/probe-profile/riskrails/profile.json" ] && pass "and does not write it" || fail "dry run wrote profile.json"

echo "== re-install is idempotent"
before=$(cd "$DIR" && find . -path ./backups -prune -o -type f -print0 | sort -z | xargs -0 sha256sum)
CODEX_DIR="$DIR" bash "$INSTALL" --target codex >/dev/null 2>&1
after=$(cd "$DIR" && find . -path ./backups -prune -o -type f -print0 | sort -z | xargs -0 sha256sum)
[ "$before" = "$after" ] && pass "a second install changes no file" || fail "the second install changed files" "$(diff <(printf '%s' "$before") <(printf '%s' "$after") | head -10)"
[ "$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/hooks.json")" = 4 ] && pass "hook entries are not duplicated" || fail "hooks duplicated"
[ "$(grep -c 'riskrails:start' "$DIR/AGENTS.md")" = 1 ] && pass "the managed block is not duplicated" || fail "block duplicated"

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
[ -f "$DIR2/backups/$(date +%F)/config.toml" ] && [ ! -e "$DIR2/config.toml.bak" ] \
    && pass "the old config is backed up into backups/<date>/, not beside it" || fail "no backups/<date>/config.toml"
cmp -s "$TMP/config.orig" "$DIR2/backups/$(date +%F)/config.toml" && pass "the backup is the original file" || fail "the backup does not match the original"
# Review M1: a second install the same day changes nothing in config.toml, so
# it must not replace the user's original in that day's backup with ours.
out=$(CODEX_DIR="$DIR2" bash "$INSTALL" --target codex 2>&1)
cmp -s "$TMP/config.orig" "$DIR2/backups/$(date +%F)/config.toml" \
    && pass "a second install the same day keeps the original in the backup" || fail "same-day re-install overwrote the config backup" "$(cat "$DIR2/backups/$(date +%F)/config.toml")"
grep -q 'backup: config.toml' <<<"$out" && fail "an unchanged config.toml was backed up again" "$out" || pass "an unchanged config.toml is not backed up again"
# Review I1: a symlinked instruction file is saved as its content, not as a link.
mkdir -p "$TMP/dotfiles"; printf 'dotfile notes\n' > "$TMP/dotfiles/AGENTS.md"
rm -f "$DIR2/AGENTS.md"; ln -s "$TMP/dotfiles/AGENTS.md" "$DIR2/AGENTS.md"
CODEX_DIR="$DIR2" bash "$INSTALL" --target codex >/dev/null 2>&1
[ ! -L "$DIR2/backups/$(date +%F)/AGENTS.md" ] && grep -qx 'dotfile notes' "$DIR2/backups/$(date +%F)/AGENTS.md" \
    && pass "a symlinked AGENTS.md is backed up as its content" || fail "symlinked AGENTS.md backed up as a link"
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
[ -d "$DIR/backups/$(date +%F)/skills/ai-init" ] && pass "the backup went to backups/<date>/skills/" || fail "backup not found in backups/<date>/skills/"

echo "== an AGENTS.md with a legacy Codex-agentic pair gets one block, renamed"
LG="$TMP/codex-legacy"; mkdir -p "$LG"
sed 's/riskrails:\(start\|end\)/Codex-agentic:\1/' "$PLUGIN_ROOT/skills/ai-init/templates/AGENTS.block.md" > "$TMP/legacy-block"
{ printf '# legacy\n\nkeep me above\n\n'; cat "$TMP/legacy-block"; printf '\n# my notes\nkeep me below\n'; } > "$LG/AGENTS.md"
out=$(CODEX_DIR="$LG" bash "$INSTALL" --target codex --codex-plan pro 2>&1)
[ "$(grep -c -E '(riskrails|[Cc]odex-agentic):start' "$LG/AGENTS.md")" = 1 ] && pass "exactly one managed block after the install" || fail "a legacy pair was doubled" "$(grep -n 'agentic:' "$LG/AGENTS.md")"
if grep -q 'Codex-agentic' "$LG/AGENTS.md"; then fail "the legacy markers are still there"; else pass "the legacy markers are renamed"; fi
grep -q 'keep me above' "$LG/AGENTS.md" && grep -q 'keep me below' "$LG/AGENTS.md" && pass "the text around the block is kept" || fail "text around the legacy block lost"
grep -q 'AGENTS.md: updated + renamed the legacy Codex-agentic markers' <<<"$out" \
    && pass "the install says what it renamed" || fail "no rename note in the install output" "$(printf '%s' "$out" | grep AGENTS.md)"
if grep -q 'AGENTS.md: managed block 0 B' <<<"$out"; then fail "block_size measured 0 B"; else pass "block_size measures the renamed block"; fi
CODEX_DIR="$LG" bash "$INSTALL" --target codex --codex-plan pro >/dev/null 2>&1
[ "$(grep -c 'riskrails:start' "$LG/AGENTS.md")" = 1 ] && pass "a reinstall keeps one block" || fail "reinstall doubled the block"

summary "codex install"
