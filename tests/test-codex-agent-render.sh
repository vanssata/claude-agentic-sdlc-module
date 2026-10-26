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

echo "== R11: exactly the five agents, no -strong/-balanced twins"
got=$(cd "$OUT" && ls *.toml 2>/dev/null | sed 's/\.toml$//' | LC_ALL=C sort | tr '\n' ' ')
[ "$got" = "Explore ai-discovery ai-reviewer architect log-reader " ] \
    && pass "rendered Explore, ai-discovery, ai-reviewer, architect, log-reader" || fail "the rendered roster is wrong" "$got"
ls "$OUT" | grep -qE -- '-(strong|balanced)\.toml$' && fail "a tier twin was rendered" "$(ls "$OUT")" || pass "no tier twin is rendered"

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

echo "== readers resolve to Terra at low effort"
for a in Explore ai-discovery log-reader; do
    [ "$(field "$a" model)" = "gpt-5.6-terra" ] && pass "$a runs on Terra" || fail "$a should run on Terra, got $(field "$a" model)"
    [ "$(field "$a" model_reasoning_effort)" = "low" ] && pass "$a runs at low effort" || fail "$a should run at low effort"
done

echo "== the reviewer and the designer resolve to Sol"
for a in ai-reviewer architect; do
    [ "$(field "$a" model)" = "gpt-5.6-sol" ] && pass "$a runs on Sol" || fail "$a should run on Sol, got $(field "$a" model)"
    [ "$(field "$a" model_reasoning_effort)" = "high" ] && pass "$a runs at high effort" || fail "$a should run at high effort"
done
field ai-reviewer developer_instructions | grep -q '^## Focus: security' \
    && pass "ai-reviewer carries the security focus" || fail "ai-reviewer is missing its Focus: security section"

echo "== the plus profile keeps xhigh off"
OUTP="$TMP/plus"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$OUTP" --profile "$PLUGIN_ROOT/profiles/codex-plus.json" >/dev/null 2>&1 \
  && pass "the plus profile renders" || fail "the plus profile should render"
grep -rq 'xhigh' "$OUTP" && fail "no plus agent may run at xhigh" || pass "no plus agent runs at xhigh"
for p in codex-plus codex-pro codex-balanced-max; do
    diff <(jq -S .roles "$PLUGIN_ROOT/profiles/$p.json") <(jq -S .roles "$PLUGIN_ROOT/profiles/codex-pro.json") >/dev/null \
      && pass "$p has the same roster as codex-pro" || fail "$p roster differs from codex-pro"
done

echo "== a variant_of role still renders: the mechanism stays, no profile ships one"
jq '.roles["ai-reviewer-strong"] = {"variant_of": "ai-reviewer", "tier": "EXPERT", "sandbox_mode": "read-only",
      "description_prefix": "Twin.", "escalation_note": "You are the twin."}' \
   "$PLUGIN_ROOT/profiles/codex-pro.json" > "$TMP/variant.json"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$TMP/variant" --profile "$TMP/variant.json" >/dev/null 2>&1 \
    && python3 -c 'import sys,tomllib;a,b=(tomllib.load(open(f,"rb")) for f in sys.argv[1:]);sys.exit(not (a["developer_instructions"]=="You are the twin.\n\n"+b["developer_instructions"] and a["model"]=="gpt-6-astra"))' \
         "$TMP/variant/ai-reviewer-strong.toml" "$TMP/variant/ai-reviewer.toml" 2>/dev/null \
    && pass "a variant reuses its parent's body, on its own tier" || fail "variant_of no longer renders"

echo "== read-only roles get a read-only sandbox"
for a in ai-reviewer ai-discovery Explore architect log-reader; do
    [ "$(field "$a" sandbox_mode)" = "read-only" ] && pass "$a is sandboxed read-only" || fail "$a should be read-only, got $(field "$a" sandbox_mode)"
done

echo "== rendering twice produces identical files"
OUT2="$TMP/agents2"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$OUT2" >/dev/null 2>&1
diff -rq "$OUT" "$OUT2" >/dev/null && pass "the renderer is deterministic" || fail "two renders differ"

echo "== --ai-shared fills {{AI_SHARED}}"
READERS="ai-discovery ai-reviewer"
python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$TMP/ai1" --ai-shared /opt/x/ai >/dev/null 2>&1 \
    || fail "render with --ai-shared should exit 0"
for a in $READERS; do
    grep -qF '/opt/x/ai/<path>' "$TMP/ai1/$a.toml" && pass "$a names the shared tree" || fail "$a does not name /opt/x/ai/<path>"
done
CODEX_HOME="$TMP/ch" python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$TMP/ai2" >/dev/null 2>&1 \
    && grep -qF "$TMP/ch/claude-agentic/ai/<path>" "$TMP/ai2/ai-reviewer.toml" \
    && pass "the default is \$CODEX_HOME/claude-agentic/ai" || fail "the --ai-shared default is wrong"
env -u CODEX_HOME HOME="$TMP/h" python3 "$PLUGIN_ROOT/scripts/render-codex-agents.py" --src "$PLUGIN_ROOT" --out "$TMP/ai3" >/dev/null 2>&1 \
    && grep -qF "$TMP/h/.codex/claude-agentic/ai/<path>" "$TMP/ai3/ai-reviewer.toml" \
    && pass "without CODEX_HOME the default is ~/.codex/claude-agentic/ai" || fail "the --ai-shared fallback is wrong"
grep -rq '{{' "$TMP/ai1" && fail "a placeholder survived" || pass "no placeholder survives"

summary "render-codex-agents.py"
