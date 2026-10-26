#!/usr/bin/env bash
# state.py: what needs no task — the failure modes that must be loud rather
# than silent, and topic questions, which live with a document and need no .ai/.
#
# Redesign 2.6 removed the old surface (init, stage, get, …). The cases whose
# subject outlives it — the journal, ownership, questions, the gate and its file
# route, handoff.md, WP5 — run in tests/test_ai_task_state.py on start and close;
# the rest went with the commands they tested.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

STATE="$PLUGIN_ROOT/skills/ai-task/state.py"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT
export CLAUDE_CONFIG_DIR="$TMP/home/.claude" CODEX_HOME="$TMP/home/.codex"
ROOT="$TMP/project"; mkdir -p "$ROOT/.ai/state" "$ROOT/.ai/reports"
S() { python3 "$STATE" --root "$ROOT" "$@"; }

echo "== a corrupt state file is loud, not silently replaced"
printf 'not json at all' > "$ROOT/.ai/state/current.json"
out=$(S status 2>&1 || true)
grep -q "unreadable" <<<"$out" && pass "a corrupt state file reports the problem" || fail "corrupt state should be loud" "$out"
[ "$(cat "$ROOT/.ai/state/current.json")" = "not json at all" ] \
  && pass "and is left exactly as it was" || fail "a corrupt state must not be replaced"

echo "== no .ai/ at all"
out=$(python3 "$STATE" --root "$TMP" status 2>&1 || true)
grep -q "run /ai-init first" <<<"$out" && pass "a project without .ai/ says what to do" || fail "should point at /ai-init" "$out"

echo "== topic questions live with the document and need no .ai/ (R17)"
ROOT10="$TMP/topic"; mkdir -p "$ROOT10/docs/sdlc/intent"
P() { env -u CLAUDECODE -u AI_RUNTIME python3 "$STATE" --root "$ROOT10" "$@"; }
P ask "What problem are we solving?" --option "A: decisions are lost" --option "B: cost" --topic my-idea >/dev/null
[ -f "$ROOT10/docs/sdlc/intent/my-idea.questions.md" ] && pass "a topic question lands beside its intent" || fail "topic file missing"
P answer Q1=A --topic my-idea --by ivan >/dev/null
P questions --topic my-idea --format md | grep -q '^- \*\*What problem are we solving?\*\* — decisions are lost' \
  && pass "--format md renders the Decisions taken line" || fail "md rendering wrong" "$(P questions --topic my-idea --format md)"
[ ! -d "$ROOT10/.ai" ] && pass "and no .ai/ was created" || fail "topic mode must not need .ai/"
[ -z "$(find "$ROOT10" -name 'events.jsonl' -o -name '.ai' 2>/dev/null)" ] \
  && pass "a topic question writes no journal anywhere in the tree" || fail "topic mode wrote a journal"
out=$(P ask "Escape?" --option "A: one" --option "B: two" --topic "../../pwned/evil" 2>&1 || true)
grep -q "takes a slug of lowercase letters" <<<"$out" && pass "a slug that is a path is refused" || fail "--topic must not steer the path" "$out"
[ ! -e "$ROOT10/../pwned" ] && [ ! -e "$ROOT10/docs/pwned" ] && pass "and nothing was written outside docs/sdlc/intent/" || fail "the traversal wrote a file"
out=$(P ask "Gate?" --option "A: one" --option "B: two" --gate human_approval --topic my-idea 2>&1 || true)
grep -q "a gate is requested by" <<<"$out" && pass "a topic file cannot hold a gate either" || fail "--gate --topic should be refused" "$out"

summary "state"
