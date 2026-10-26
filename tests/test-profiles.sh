#!/usr/bin/env bash
# profiles/*.json and scripts/resolve-profile.py: every plan carries the plugin's
# own tables under `claude_agentic`, max20 is max plus budgets and nothing else,
# and the budgets carry no fan-out and no direct-mode cap since redesign 2.4 —
# what is left is the EXPERT rule and the token table.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

RESOLVE="$PLUGIN_ROOT/scripts/resolve-profile.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== R1: every profile has claude_agentic with tiers, budgets, preferred_runtime"
for f in "$PLUGIN_ROOT"/profiles/*.json; do
    name=$(basename "$f" .json)
    if python3 "$RESOLVE" "$name" --print agentic > "$TMP/$name.json" 2> "$TMP/$name.err"; then
        missing=$(jq -r '[("tiers","budgets","preferred_runtime","plan","label","runtime") as $k
                          | select(has($k) | not) | $k] | join(",")' "$TMP/$name.json")
        [ -z "$missing" ] && pass "$name resolves with every key" || fail "$name misses: $missing"
        n=$(jq '.tiers | [.FAST, .BALANCED, .STRONG, .EXPERT] | map(select(.model and .effort)) | length' "$TMP/$name.json")
        [ "$n" = 4 ] && pass "$name has the four tiers with model and effort" || fail "$name: $n of 4 tiers complete"
    else
        fail "$name does not resolve" "$(head -c 200 "$TMP/$name.err")"
    fi
done

keys=$(jq -r 'keys | join(",")' "$PLUGIN_ROOT/profiles/max20.json")
[ "$keys" = claude_agentic ] && pass "max20.json holds only claude_agentic" || fail "max20.json top-level keys: $keys"
[ "$(jq -r .claude_agentic.inherits "$PLUGIN_ROOT/profiles/max20.json")" = max ] \
    && pass "max20 inherits max" || fail "max20 should inherit max"

python3 "$RESOLVE" max20 --print settings | jq -S . > "$TMP/max20.settings"
python3 "$RESOLVE" max --print settings | jq -S . > "$TMP/max.settings"
jq -S 'del(.claude_agentic)' "$PLUGIN_ROOT/profiles/max.json" > "$TMP/max.raw"
cmp -s "$TMP/max20.settings" "$TMP/max.settings" && cmp -s "$TMP/max.settings" "$TMP/max.raw" \
    && pass "resolved(max20) minus claude_agentic equals max.json minus it" \
    || fail "max20 settings differ from max" "$(diff "$TMP/max20.settings" "$TMP/max.raw" | head -5)"
jq -e '.plan == "max20" and .label == "Max 20x" and .tiers == input.tiers' \
    "$TMP/max20.json" "$TMP/max.json" >/dev/null \
    && pass "max20: own plan and label, max's tiers" || fail "max20 plan/label/tiers wrong"

echo "== resolver overrides"
out=$(python3 "$RESOLVE" pro --plan team-pro --label "Team Pro" --print agentic | jq -r '"\(.plan)|\(.label)"')
[ "$out" = "team-pro|Team Pro" ] && pass "--plan/--label override" || fail "--plan/--label: $out"
out=$(python3 "$RESOLVE" max --fable no --print agentic | jq -r '"\(.fable)|\(.tiers.EXPERT | has("architect_model_with_fable"))"')
[ "$out" = "false|false" ] && pass "--fable no drops the Fable architect" || fail "--fable no: $out"
out=$(python3 "$RESOLVE" max --fable yes --print agentic | jq -r '"\(.fable)|\(.tiers.EXPERT.architect_model_with_fable)"')
[ "$out" = "true|fable[1m]" ] && pass "--fable yes keeps it" || fail "--fable yes: $out"
jq -e '.tiers.EXPERT | has("architect_model_with_fable") | not' "$TMP/pro.json" >/dev/null \
    && pass "pro has no Fable key" || fail "pro should not name Fable"
python3 "$RESOLVE" no-such-plan >/dev/null 2>&1; rc=$?
[ "$rc" = 2 ] && pass "unknown profile exits 2" || fail "unknown profile exit $rc"
printf '{"claude_agentic":{"inherits":"loop-b"}}' > "$TMP/loop-a.json"
printf '{"claude_agentic":{"inherits":"loop-a"}}' > "$TMP/loop-b.json"
mkdir -p "$TMP/src/profiles" && cp "$TMP"/loop-*.json "$TMP/src/profiles/"
python3 "$RESOLVE" loop-a --src "$TMP/src" >/dev/null 2>&1; rc=$?
[ "$rc" = 2 ] && pass "an inheritance cycle exits 2" || fail "cycle exit $rc"

echo "== R2/R29: budgets carry no fan_out and no direct_mode"
python3 "$RESOLVE" pro --plan team-pro --print agentic > "$TMP/team-pro.json"
for name in pro team-pro max max20 balanced-max codex-plus codex-pro codex-balanced-max; do
    jq -e '.budgets | has("fan_out") or has("direct_mode") | not' "$TMP/$name.json" >/dev/null \
        && pass "$name: budgets.fan_out and budgets.direct_mode are gone" || fail "$name still carries fan_out or direct_mode" "$(jq -c .budgets "$TMP/$name.json")"
    jq -e '.budgets.expert | (.without_asking | type) == "boolean" and .max_per_task >= 1' "$TMP/$name.json" >/dev/null \
        && pass "$name: the EXPERT rule stays" || fail "$name: budgets.expert"
done
grep -l '"fan_out"\|"direct_mode"' "$PLUGIN_ROOT"/profiles/*.json && fail "a profile source still names fan_out or direct_mode" \
    || pass "no profile source names fan_out or direct_mode"
for name in codex-plus codex-pro; do
    jq -e '.preferred_runtime.by_workflow == {} and .runtime == "codex"' "$TMP/$name.json" >/dev/null \
        && pass "$name: codex runtime, no workflow preference" || fail "$name: runtime/by_workflow"
    jq -e --slurpfile p "$PLUGIN_ROOT/profiles/$name.json" \
        '[.tiers | to_entries[] | {key, value: {model: .value.model, effort: .value.effort}}] | from_entries
         == ($p[0].tiers | map_values({model, effort}))' "$TMP/$name.json" >/dev/null \
        && pass "$name: tiers read from the Codex profile" || fail "$name: tiers differ from the top-level tiers"
done
for name in pro max max20; do
    jq -e '.preferred_runtime.by_workflow == {"refactoring": "codex"} and .runtime == "claude"' "$TMP/$name.json" >/dev/null \
        && pass "$name: refactoring prefers codex" || fail "$name: runtime/by_workflow"
done

echo "== R16: each agent template's tier is its tier everywhere"
for t in "$PLUGIN_ROOT"/agents/*.md.tmpl; do
    n=$(basename "$t" .md.tmpl)
    tier=$(sed -n 's/^model: {{\([A-Z]*\)_MODEL}}$/\1/p' "$t")
    # architect carries a whole model line rendered per plan
    # (ARCHITECT_MODEL_LINE), not a tier placeholder.
    [ -n "$tier" ] || continue
    grep -qE '^model: [a-z]' "$t" && fail "$n names a model in its source"
    for p in codex-plus codex-pro; do
        role=$(jq -r --arg n "$n" '.roles[$n].tier // "none"' "$PLUGIN_ROOT/profiles/$p.json")
        [ "$role" = "$tier" ] && pass "$n: $tier in the template and in $p" || fail "$n: template $tier, $p role $role"
    done
    for p in pro max; do
        jq -e --arg n "$n" --arg t "$tier" '.tiers[$t].agents | index($n)' "$TMP/$p.json" >/dev/null \
            && pass "$n listed under $tier in $p" || fail "$n not listed under $tier in $p's claude_agentic.tiers"
    done
    eff=$(sed -n 's/^effort: \(.*\)$/\1/p' "$t")
    case "$eff" in "{{${tier}_EFFORT}}"|low|medium|high) ;; *) fail "$n: effort '$eff' is neither its tier's placeholder nor a literal";; esac
done

summary "test-profiles"
