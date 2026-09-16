#!/usr/bin/env bash
# scripts/render-codex-agents.py: every rendered Codex custom agent must parse as
# TOML, carry the three fields Codex requires, and resolve to the tier its role
# needs. The last part is the point of the suite: Codex resolves a subagent's
# model from the spawn value, then the [agents] default, then the parent — and a
# custom agent file that omits `model` would let an escalation land back on the
# BALANCED default. Asserting the effective model per role is what catches that.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

command -v python3 >/dev/null 2>&1 || { echo "python3 required"; exit 1; }
python3 -c 'import tomllib' 2>/dev/null || { echo "SKIP: python3 has no tomllib (needs 3.11+)"; exit 0; }

TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
OUT="$TMP/agents"

echo "== render"
out=$(python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$OUT" 2>&1)
if [ $? -eq 0 ]; then pass "renderer exits 0"; else fail "renderer should exit 0" "$out"; fi

count=$(ls "$OUT"/*.toml 2>/dev/null | wc -l)
[ "$count" -ge 16 ] && pass "rendered $count agents" || fail "expected at least 16 agents, got $count"

echo "== every file is valid TOML with the three required fields"
bad=$(python3 - "$OUT" <<'PY'
import glob, os, sys, tomllib
problems = []
for path in sorted(glob.glob(os.path.join(sys.argv[1], "*.toml"))):
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except Exception as exc:
        problems.append(f"{os.path.basename(path)}: not valid TOML: {exc}")
        continue
    for key in ("name", "description", "developer_instructions"):
        if not isinstance(data.get(key), str) or not data[key].strip():
            problems.append(f"{os.path.basename(path)}: missing or empty {key}")
    stem = os.path.basename(path)[: -len(".toml")]
    if data.get("name") != stem:
        problems.append(f"{os.path.basename(path)}: name {data.get('name')!r} != filename")
    if "{{" in data.get("developer_instructions", "") or "{{" in data.get("description", ""):
        problems.append(f"{os.path.basename(path)}: unrendered placeholder")
print("\n".join(problems))
PY
)
[ -z "$bad" ] && pass "all files parse and carry name/description/developer_instructions" || fail "invalid rendered agents" "$bad"

# field <agent> <key>
field() { python3 -c 'import sys,tomllib;print(tomllib.load(open(sys.argv[1],"rb")).get(sys.argv[2],""))' "$OUT/$1.toml" "$2"; }

echo "== readers and mechanical workers resolve to Terra"
for a in ai-indexer Explore ai-discovery log-reader; do
    [ "$(field "$a" model)" = "gpt-5.6-terra" ] && pass "$a runs on Terra" || fail "$a should run on Terra, got $(field "$a" model)"
    [ "$(field "$a" model_reasoning_effort)" = "low" ] && pass "$a runs at low effort" || fail "$a should run at low effort"
done
for a in ai-context ai-risk ai-planner ai-release ai-implementer; do
    [ "$(field "$a" model)" = "gpt-5.6-terra" ] && pass "$a runs on Terra" || fail "$a should run on Terra, got $(field "$a" model)"
    [ "$(field "$a" model_reasoning_effort)" = "medium" ] && pass "$a runs at medium effort" || fail "$a should run at medium effort"
done

echo "== strong reviewers and designers resolve to Sol"
for a in ai-reviewer ai-security architect ai-risk-strong ai-planner-strong; do
    [ "$(field "$a" model)" = "gpt-5.6-sol" ] && pass "$a runs on Sol" || fail "$a should run on Sol, got $(field "$a" model)"
    [ "$(field "$a" model_reasoning_effort)" = "high" ] && pass "$a runs at high effort" || fail "$a should run at high effort"
done

echo "== the expert resolves to Astra"
[ "$(field ai-expert model)" = "gpt-6-astra" ] && pass "ai-expert runs on Astra" || fail "ai-expert should run on Astra"
[ "$(field ai-expert model_reasoning_effort)" = "xhigh" ] && pass "ai-expert runs at xhigh" || fail "ai-expert should run at xhigh"

echo "== the plus profile keeps xhigh off"
OUTP="$TMP/plus"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$OUTP" --profile "$PLUGIN_ROOT/profiles/codex-plus.json" >/dev/null 2>&1 \
  && pass "the plus profile renders" || fail "the plus profile should render"
grep -q '^model_reasoning_effort = "xhigh"' "$OUTP/ai-expert.toml" && fail "ai-expert must not run at xhigh on plus" || pass "ai-expert stays below xhigh on plus"
grep -q '^model = "gpt-6-astra"' "$OUTP/ai-expert.toml" && pass "ai-expert still runs on Astra on plus" || fail "ai-expert should run on Astra on plus"
grep -rq 'xhigh' "$OUTP" && fail "no plus agent may run at xhigh" || pass "no plus agent runs at xhigh"
for p in codex-plus codex-pro; do
    diff <(jq -S .roles "$PLUGIN_ROOT/profiles/$p.json") <(jq -S .roles "$PLUGIN_ROOT/profiles/codex-pro.json") >/dev/null \
      && pass "$p has the same roster as codex-pro" || fail "$p roster differs from codex-pro"
done

echo "== the strong variants exist so an escalation cannot be pinned back to Terra"
field ai-risk-strong developer_instructions | grep -q 'STRONG re-run' \
    && pass "ai-risk-strong says it is the escalation" || fail "ai-risk-strong is missing its escalation note"
field ai-planner-strong developer_instructions | grep -q 'T3 or T4' \
    && pass "ai-planner-strong names the tiers it serves" || fail "ai-planner-strong is missing its escalation note"
field ai-risk-strong developer_instructions | grep -q 'You classify risk' \
    && pass "ai-risk-strong reuses the shared ai-risk body" || fail "ai-risk-strong should reuse the shared prompt body"

echo "== read-only roles get a read-only sandbox"
for a in ai-reviewer ai-security ai-expert ai-discovery Explore ai-risk ai-planner architect ai-context ai-indexer ai-tester log-reader; do
    [ "$(field "$a" sandbox_mode)" = "read-only" ] && pass "$a is sandboxed read-only" || fail "$a should be read-only, got $(field "$a" sandbox_mode)"
done
for a in ai-implementer ai-release; do
    [ "$(field "$a" sandbox_mode)" = "workspace-write" ] && pass "$a may write in the workspace" || fail "$a should be workspace-write"
done

echo "== rendering twice produces identical files"
OUT2="$TMP/agents2"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$OUT2" >/dev/null 2>&1
diff -rq "$OUT" "$OUT2" >/dev/null && pass "the renderer is deterministic" || fail "two renders differ"

summary "render-codex-agents.py"
