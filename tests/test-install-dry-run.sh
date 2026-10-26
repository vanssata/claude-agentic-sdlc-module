#!/usr/bin/env bash
# install.sh: rendering must be complete and correct for every plan/fable
# combination, and a real install into a scratch CLAUDE_DIR must be idempotent.
set -uo pipefail
. "$(dirname "$0")/lib.sh"

INSTALL="$PLUGIN_ROOT/install.sh"
TMP=$(mktemp -d); trap 'rm -rf "$TMP"' EXIT

echo "== dry run renders for every plan"
for combo in "max yes:xhigh:fable[1m]" "max no:high:Opus 5.5 [1m] by default" "pro no:high:Opus 5" \
             "team-max yes:xhigh:fable[1m]" "team-max no:high:Opus 5.5 [1m] by default" "team-pro no:high:Opus 5"; do
    args="${combo%%:*}"; rest="${combo#*:}"; effort="${rest%%:*}"; model="${rest#*:}"
    set -- $args
    out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --target claude --plan "$1" --fable "$2" --dry-run 2>&1)
    rc=$?
    [ $rc -eq 0 ] && pass "--plan $1 --fable $2 exits 0" || fail "--plan $1 --fable $2 should exit 0" "$out"
    grep -q '{{' <<<"$out" && fail "--plan $1 --fable $2 left an unrendered placeholder" || pass "--plan $1 --fable $2 renders every placeholder"
    grep -q "effort: $effort" <<<"$out" && pass "--plan $1 --fable $2 renders architect effort $effort" || fail "expected effort: $effort" "$out"
    grep -qF "$model" <<<"$out" && pass "--plan $1 --fable $2 names $model" || fail "expected $model in the output" "$out"
    grep -q 'nothing written' <<<"$out" && pass "--plan $1 --fable $2 writes nothing" || fail "dry run should write nothing"
done
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --fable no --dry-run 2>&1)
grep -q '"fable' <<<"$(sed -n '/^== settings snippet/,/^== agents/p' <<<"$out")" && fail "--fable no must drop fable from the settings" "$out" || pass "--fable no drops fable from the settings"

echo "== dry run: the shared tree"
for target in claude codex; do
    out=$(HOME="$TMP/h-$target" CLAUDE_DIR="$TMP/none" CODEX_DIR="$TMP/none-x" bash "$INSTALL" --target "$target" --plan max --codex-plan plus --dry-run 2>&1)
    n=$(printf '%s\n' "$out" | grep -c '^   shared:  claude-agentic/ai (31 files), claude-agentic/ai-path$')
    [ "$n" -eq 1 ] && pass "$target: the would-install list names the shared tree once" || fail "$target: shared line count $n" "$out"
    skills=$(printf '%s\n' "$out" | sed -n 's/^   skills:  //p')
    missing=""; for s in rr-setup rr-spec rr-plan rr-build rr-review rr-ship rr-status; do
        grep -qE "(^|,)$s(,|$)" <<<"$skills" || missing="$missing $s"; done
    [ -z "$missing" ] && ! grep -qE '(^|,)status(,|$)' <<<"$skills" \
        && pass "$target: the would-install list names the seven rr- skills and no bare status" \
        || fail "$target: skills line" "missing:$missing — $skills"
    grep -q '^   retire:  skills/status (now skills/rr-status)' <<<"$out" \
        && pass "$target: the dry run names the retire of skills/status" || fail "$target: no retire line" "$out"
    span=$(printf '%s\n' "$out" | sed -n '/^== \(CLAUDE\|AGENTS\)\.md managed block:/,/^== profile\.json/p')
    grep -q '^   shared:' <<<"$span" && fail "$target: the shared line is inside the block/routing span" || pass "$target: the shared line is outside the block/routing span"
    grep -qF 'claude-agentic/ai-path <path>' <<<"$span" && pass "$target: routing.md renders the shared-files line" || fail "$target: routing.md lacks the shared-files line" "$span"
    grep -q '{{' <<<"$out" && fail "$target: an unrendered placeholder" || pass "$target: every placeholder is rendered"
done

echo "== pro: opusplan session, EXPERT tier pinned to opus"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan pro --dry-run 2>&1)
grep -q '"model": "opusplan"' <<<"$out" && pass "pro sets the session model to opusplan" || fail "pro should set opusplan" "$out"
grep -q 'Opus 5 in plan mode' <<<"$out" && pass "pro names opusplan in the CLAUDE.md block" || fail "block should explain opusplan" "$out"
grep -q '^model: opus' <<<"$out" && pass "pro pins model: opus on architect, the EXPERT agent" || fail "architect should pin opus on pro" "$out"
grep -q '/rr-build <request>' <<<"$out" && pass "the block routes every change through /rr-build" || fail "block should name /rr-build" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan max --fable yes --dry-run 2>&1)
grep -qxF 'model: fable[1m]' <<<"$out" && pass "max+fable pins fable[1m] on architect" || fail "architect should pin fable[1m] on max+fable" "$out"
grep -qx 'effort: xhigh' <<<"$out" && pass "max renders the EXPERT tier at xhigh" || fail "EXPERT effort should be xhigh on max" "$out"

echo "== team-pro and team-max share the pro and max profiles"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan team-pro --dry-run 2>&1)
grep -q 'plan=team-pro (Team Pro, pro profile)' <<<"$out" && pass "team-pro uses the pro profile" || fail "team-pro should use the pro profile" "$out"
grep -q '"model": "opusplan"' <<<"$out" && pass "team-pro sets the session model to opusplan" || fail "team-pro should set opusplan" "$out"
grep -q '^model: opus' <<<"$out" && pass "team-pro pins model: opus on the EXPERT agents" || fail "EXPERT agents should pin opus on team-pro" "$out"
grep -q 'Model routing (Team Pro plan)' <<<"$out" && pass "team-pro is named in the CLAUDE.md block" || fail "block should say Team Pro" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan team-pro --fable yes --dry-run 2>&1)
grep -q 'fable=no' <<<"$out" && pass "team-pro forces --fable no" || fail "team-pro should refuse Fable" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan team-max --dry-run 2>&1)
grep -q 'plan=team-max (Team Max, max profile) fable=yes fable-gate=on' <<<"$out" && pass "team-max uses the max profile with Fable and the gate" || fail "team-max should behave like max" "$out"
grep -q '^model: fable\[1m\]' <<<"$out" && pass "team-max pins fable[1m] on architect" || fail "team-max should pin fable on architect" "$out"
grep -q 'Model routing (Team Max plan)' <<<"$out" && pass "team-max is named in the CLAUDE.md block" || fail "block should say Team Max" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan team-premium --dry-run 2>&1)
grep -q 'plan=team-max' <<<"$out" && pass "team-premium is an alias of team-max" || fail "team-premium should map to team-max" "$out"
out=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --plan team-standard --dry-run 2>&1)
grep -q 'plan=team-pro' <<<"$out" && pass "team-standard is an alias of team-pro" || fail "team-standard should map to team-pro" "$out"

echo "== plan detection reads the seat of a Team org"
HOME_T="$TMP/home-team"; mkdir -p "$HOME_T"
printf '{"oauthAccount":{"organizationType":"claude_team"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'plan=team-pro' <<<"$out" && pass "claude_team with no seat falls back to team-pro" || fail "team org without a seat should map to team-pro" "$out"
grep -q -- '--plan team-max' <<<"$out" && pass "the fallback says how to pick team-max" || fail "the fallback should mention --plan team-max" "$out"
printf '{"oauthAccount":{"organizationType":"claude_team","seatTier":"standard"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'detected plan: team-pro' <<<"$out" && pass "a standard seat is detected as team-pro" || fail "standard seat should map to team-pro" "$out"
printf '{"oauthAccount":{"organizationType":"claude_team","seatTier":"premium"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'detected plan: team-max' <<<"$out" && pass "a premium seat is detected as team-max" || fail "premium seat should map to team-max" "$out"
printf '{"oauthAccount":{"organizationType":"claude_team","organizationRateLimitTier":"default_claude_max_5x"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'detected plan: team-max' <<<"$out" && pass "a max rate-limit tier is detected as team-max" || fail "max rate-limit tier should map to team-max" "$out"
printf '{"oauthAccount":{"organizationType":"claude_max"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'plan=max (Max' <<<"$out" && pass "claude_max is still detected as max" || fail "max org should map to max" "$out"

echo "== balanced-max: only the session is strong"
outb=$(CLAUDE_DIR="$TMP/none" CODEX_DIR="$TMP/nonecx" bash "$INSTALL" --target both --plan balanced-max --dry-run 2>&1)
grep -q 'plan=balanced-max (BalancedMax, max profile) fable=no' <<<"$outb" && pass "--plan balanced-max: BalancedMax on the max profile, Fable off" || fail "--plan balanced-max header" "$(printf '%s' "$outb" | grep '^== claude: plan')"
grep -q '"model": "claude-opus-5-5"' <<<"$outb" && pass "balanced-max pins the session to Opus 5.5" || fail "balanced-max session model"
grep -q 'fable\[1m\]' <<<"$outb" && fail "balanced-max must not offer Fable" || pass "balanced-max offers no Fable"
grep -qx 'effort: xhigh' <<<"$outb" && fail "balanced-max must not render xhigh" || pass "balanced-max renders no xhigh"
grep -q '== codex: plan=balanced-max' <<<"$outb" && pass "--plan balanced-max selects the Codex balanced-max profile" || fail "codex profile not balanced-max"
grep -q '| FAST | `gpt-5.6-luna`' <<<"$outb" && pass "Codex readers run on Luna" || fail "codex FAST should be Luna"
o=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --target claude --plan balanced-max --fable yes --dry-run 2>&1)
grep -q 'fable=no' <<<"$o" && pass "--fable yes is refused on balanced-max" || fail "balanced-max accepted Fable"

echo "== max20: Max 20x, detected from organizationRateLimitTier (R3)"
snippet() { sed -n '/^== settings snippet/,/^== agents/p'; }
out20=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --target claude --plan max20 --dry-run 2>&1)
outmax=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --target claude --plan max --dry-run 2>&1)
grep -q 'plan=max20 (Max 20x, max profile) fable=yes' <<<"$out20" && pass "--plan max20 is Max 20x on the max profile" || fail "--plan max20 header" "$(printf '%s' "$out20" | grep '^== claude: plan')"
[ "$(printf '%s' "$out20" | snippet)" = "$(printf '%s' "$outmax" | snippet)" ] \
    && pass "max20's settings snippet equals max's" || fail "max20 snippet differs from max"
for plan in pro team-pro team-max max max20; do
    o=$(CLAUDE_DIR="$TMP/none" bash "$INSTALL" --target claude --plan "$plan" --dry-run 2>&1)
    printf '%s' "$o" | snippet | sed '1d;$d' | jq -e 'has("claude_agentic") | not' >/dev/null \
        && pass "$plan: claude_agentic never reaches settings.json" || fail "$plan: claude_agentic leaked into the snippet"
    grep -q "^== profile.json (plan tables): $TMP/none/claude-agentic/profile.json" <<<"$o" \
        && pass "$plan: --dry-run lists profile.json" || fail "$plan: profile.json not listed"
done
printf '%s' "$out20" | sed -n '/^== profile.json/,/^== would install/p' | sed '1d;$d' \
    | jq -e '.plan == "max20" and .label == "Max 20x" and .runtime == "claude" and .fable == true
             and .budgets.expert.max_per_task == 2 and (.budgets | has("fan_out") | not) and (.plugin_version | length > 0) and (.written_at | length > 0)' >/dev/null \
    && pass "max20 profile.json carries plan, runtime, fable and the max20 budgets" || fail "max20 profile.json content"
printf '{"oauthAccount":{"organizationType":"claude_max","organizationRateLimitTier":"default_claude_max_20x"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'plan=max20 (Max 20x' <<<"$out" && pass "default_claude_max_20x is detected as max20" || fail "max_20x should map to max20" "$out"
err=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 >/dev/null </dev/null)
grep -q 'detected plan: max20 (organizationRateLimitTier default_claude_max_20x)' <<<"$err" \
    && pass "without a terminal the detection is printed on stderr" || fail "detection should be on stderr" "$err"
printf '{"oauthAccount":{"organizationType":"claude_max","organizationRateLimitTier":"default_claude_max_5x"}}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$TMP/none" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'plan=max (Max' <<<"$out" && pass "default_claude_max_5x stays max" || fail "max_5x should map to max" "$out"
PREV="$TMP/prev"; mkdir -p "$PREV/claude-agentic"; printf '{"plan":"max20"}' > "$PREV/claude-agentic/profile.json"
printf '{}' > "$HOME_T/.claude.json"
out=$(HOME="$HOME_T" CLAUDE_DIR="$PREV" bash "$INSTALL" --dry-run 2>&1 </dev/null)
grep -q 'plan=max20' <<<"$out" && pass "an undetectable account falls back to the plan the last install recorded" || fail "previous profile.json plan not used" "$out"

echo "== R16/R18: every installed agent's model and effort, per plan"
# Captured from the installer before the agent sources became templates (WP5
# step 3); since redesign 2.4 five agents are left. The four tier agents are
# the same on every plan; only architect differs. A change here is a model or
# effort change, which R18 forbids.
COMMON="ai-discovery sonnet low;ai-reviewer opus high;Explore haiku low;log-reader haiku low"
for combo in "pro no|architect opus high" \
             "team-pro no|architect opus high" \
             "max yes|architect fable[1m] xhigh" \
             "max no|architect - high" \
             "team-max yes|architect fable[1m] xhigh" \
             "team-max no|architect - high" \
             "max20 yes|architect fable[1m] xhigh"; do
    args="${combo%%|*}"; set -- $args
    D="$TMP/fm-$1-$2"; mkdir -p "$D"
    CLAUDE_DIR="$D" bash "$INSTALL" --target claude --plan "$1" --fable "$2" >/dev/null 2>&1 </dev/null
    got=$(for f in "$D"/agents/*.md; do
              awk -v n="$(basename "$f" .md)" 'NR>1 && /^---$/{exit} /^model:/{m=$2} /^effort:/{e=$2} END{print n, (m==""?"-":m), e}' "$f"
          done | sort | paste -sd';')
    want=$(printf '%s' "$COMMON;${combo#*|}" | tr ';' '\n' | sort | paste -sd';')
    [ "$got" = "$want" ] && pass "--plan $1 --fable $2: all 5 agents keep their model and effort" \
        || fail "--plan $1 --fable $2: agent frontmatter changed" "$(diff <(tr ';' '\n' <<<"$want") <(tr ';' '\n' <<<"$got") | head -6)"
    bad=""
    for t in "$PLUGIN_ROOT"/agents/*.md.tmpl; do
        tier=$(sed -n 's/^model: {{\([A-Z]*\)_MODEL}}$/\1/p' "$t"); [ -n "$tier" ] || continue
        n=$(basename "$t" .md.tmpl)
        want_m=$(jq -r --arg t "$tier" '.tiers[$t].model' "$D/claude-agentic/profile.json")
        grep -qx "model: $want_m" "$D/agents/$n.md" || bad="$bad $n"
    done
    [ -z "$bad" ] && pass "--plan $1: each installed model is the profile's tiers[<tier>].model" || fail "--plan $1: model differs from its tier:$bad"
    grep -rl '{{' "$D/agents" >/dev/null && fail "--plan $1: an installed agent has an unrendered placeholder" || pass "--plan $1: no placeholder left in any agent"
done

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
jq -e '.plan == "max" and .runtime == "claude" and .fable == true' "$DIR/claude-agentic/profile.json" >/dev/null \
    && pass "profile.json written for the Claude install (R4)" || fail "profile.json missing or wrong"
[ "$(stat -c %a "$DIR/claude-agentic/profile.json" 2>/dev/null)" = 644 ] && pass "profile.json is mode 0644" || fail "profile.json mode"
jq -e 'has("claude_agentic") | not' "$DIR/settings.json" >/dev/null && pass "settings.json has no claude_agentic" || fail "claude_agentic leaked into settings.json"

for f in agents/ai-discovery.md agents/ai-reviewer.md agents/architect.md agents/Explore.md \
         agents/log-reader.md hooks/ai-git-guard.sh hooks/lib/ai-hook-common.sh \
         hooks/cap-large-read.py hooks/project-scaffold.sh hooks/ai-git-guard.json \
         skills/ai-init/SKILL.md skills/ai-init/scaffold-ai.sh skills/ai-task/state.py \
         skills/ai-audit/SKILL.md skills/ai-status/SKILL.md skills/project-init/SKILL.md \
         skills/rr-status/SKILL.md skills/rr-status/status.py \
         skills/sdlc-intent/SKILL.md skills/sdlc-spec/SKILL.md skills/sdlc-plan/SKILL.md \
         skills/ai-init/templates/.ai/AGENTS.md skills/project-init/templates/intent.md \
         skills/project-update/SKILL.md skills/project-update/update.py skills/project-update/history/index.json \
         skills/project-update/migrations/__init__.py skills/project-update/migrations/0001_schema_version.py \
         skills/usage-report/SKILL.md skills/usage-report/usage-report.py \
         hooks/context-guard.py claude-agentic/routing.md claude-agentic/ai-path \
         claude-agentic/ai/policies/git.md claude-agentic/ai/workflows/feature.md \
         skills/project-update/render_instructions.py; do
    [ -e "$DIR/$f" ] && pass "$f installed" || fail "$f missing"
done
[ -x "$DIR/hooks/ai-git-guard.sh" ] && pass "hooks are executable" || fail "hooks should be executable"
[ -x "$DIR/skills/rr-status/status.py" ] && pass "rr-status/status.py is executable" || fail "rr-status/status.py should be executable"
[ ! -e "$DIR/skills/status" ] && pass "skills/status is not installed (redesign 2.3)" || fail "skills/status installed"
for f in hooks/fable-gate.py hooks/codex-model-gate.py; do
    [ ! -e "$DIR/$f" ] && pass "$f is not installed (redesign 1.3)" || fail "$f installed"
done
[ -x "$DIR/claude-agentic/ai-path" ] && pass "ai-path is executable" || fail "ai-path should be executable"
grep -qF "$DIR/claude-agentic/ai/" "$DIR/claude-agentic/routing.md" && pass "routing.md names the installed shared tree" || fail "routing.md should name $DIR/claude-agentic/ai/"
grep -qF "$DIR/claude-agentic/ai-path <path>" "$DIR/claude-agentic/routing.md" && pass "routing.md names the resolver" || fail "routing.md should name the resolver"
for a in ai-discovery ai-reviewer; do
    grep -qF "$DIR/claude-agentic/ai/<path>" "$DIR/agents/$a.md" && pass "$a names the installed shared tree" || fail "$a should name $DIR/claude-agentic/ai/<path>"
done
[ -x "$DIR/skills/ai-init/scaffold-ai.sh" ] && pass "scaffold-ai.sh is executable" || fail "scaffold should be executable"
RETIRED_24="ai-context ai-expert ai-implementer ai-indexer ai-planner ai-release ai-risk ai-security ai-tester"
got=$(cd "$DIR/agents" && ls *.md | sed 's/\.md$//' | LC_ALL=C sort | paste -sd' ')
[ "$got" = "Explore ai-discovery ai-reviewer architect log-reader" ] && pass "exactly the five agents are installed (redesign 2.4)" || fail "installed agents" "$got"
grep -q '^model: fable\[1m\]' "$DIR/agents/architect.md" && pass "architect alone is pinned to fable[1m] on max+fable" || fail "architect should pin fable[1m]"
grep -q 'effort: xhigh' "$DIR/agents/architect.md" && pass "architect runs at xhigh on Fable" || fail "architect effort wrong"

echo "== real pro install"
DIRP="$TMP/claude-pro"; mkdir -p "$DIRP"
CLAUDE_DIR="$DIRP" bash "$INSTALL" --plan pro >/dev/null 2>&1 && pass "pro install exits 0" || fail "pro install should exit 0"
grep -q '^model: opus' "$DIRP/agents/architect.md" && pass "pro: architect pins opus" || fail "pro: architect should pin opus"
grep -q '^effort: high' "$DIRP/agents/architect.md" && pass "pro: architect runs at high" || fail "pro: expert effort wrong"
[ -e "$DIRP/bin/claude-1m" ] && fail "pro has no opus[1m]; the launcher must not be installed" || pass "pro: no opus[1m] launcher"
[ "$(jq -r .model "$DIRP/settings.json")" = "opusplan" ] && pass "pro: settings.json model is opusplan" || fail "pro: model not opusplan"
[ "$(jq -r '.fallbackModel[0]' "$DIRP/settings.json")" = "sonnet" ] && pass "pro: fallback is sonnet" || fail "pro: fallback wrong"
[ "$(jq -r .effortLevel "$DIRP/settings.json")" = "medium" ] && pass "pro: default effort is medium" || fail "pro: effort wrong"
grep -q '^model: opus$' "$DIR/agents/architect.md" && fail "max: architect must not pin opus" || pass "max: architect is not pinned to opus"

echo "== settings.json"
n=$(jq '[.hooks.PreToolUse[].hooks[].command] | length' "$DIR/settings.json")
[ "$n" = 5 ] && pass "five PreToolUse hooks registered (four guards + runtime-gate)" || fail "expected 5 PreToolUse commands, got $n"
jq -e '.hooks.Setup[0].hooks[0].command | test("project-scaffold")' "$DIR/settings.json" >/dev/null \
    && pass "the Setup:init scaffold hook is registered" || fail "Setup hook missing"
[ "$(jq -r .model "$DIR/settings.json")" = "claude-opus-5-5[1m]" ] && pass "the max session model is pinned to Opus 5.5 [1m], not Fable" || fail "model not set"
[ "$(jq -r .effortLevel "$DIR/settings.json")" = "medium" ] && pass "the default effort is medium" || fail "effort not set"
jq -e '.availableModels | index("fable[1m]")' "$DIR/settings.json" >/dev/null && pass "fable[1m] stays available for architect" || fail "fable should remain in availableModels"
DIRN="$TMP/claude-nofable"; mkdir -p "$DIRN"
CLAUDE_DIR="$DIRN" bash "$INSTALL" --plan max --fable no >/dev/null 2>&1
grep -q '^model:' "$DIRN/agents/architect.md" && fail "with --fable no, architect must inherit the session" || pass "with --fable no, architect inherits the Opus session"
jq -e '.availableModels | index("fable[1m]")' "$DIRN/settings.json" >/dev/null && fail "fable should be removed with --fable no" || pass "with --fable no, fable is not offered"
[ "$(jq -r .autoCompactWindow "$DIR/settings.json")" = "800000" ] && pass "the compaction window is 800k on max; uncapped on the 1M session, so it fires near 767k" || fail "compaction not set"
[ -x "$DIR/hooks/context-guard.py" ] && pass "context-guard is executable" || fail "context-guard should be executable"
for ev in UserPromptSubmit PreCompact SessionStart; do
    [ "$(jq -r --arg e "$ev" '[.hooks[$e][]?.hooks[]?.command | select(test("context-guard"))] | length' "$DIR/settings.json")" = 1 ] \
        && pass "context-guard is registered under $ev" || fail "context-guard is not registered under $ev"
done
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(jq -r '[.hooks.UserPromptSubmit[]?.hooks[]?.command | select(test("context-guard"))] | length' "$DIR/settings.json")" = 1 ] \
    && pass "a second install does not register context-guard twice" || fail "context-guard registered twice"
grep -q 'Compaction near 767 000 tokens' "$DIR/claude-agentic/routing.md" && pass "routing.md names the point where compaction fires on the 1M session" || fail "routing.md should say compaction fires near 767 000"
grep -q 'warning from 613k tokens, and from 920k' "$DIR/claude-agentic/routing.md" && pass "routing.md names the guard's thresholds" || fail "the guard thresholds are not rendered"
grep -q 'On compaction keep' "$DIR/CLAUDE.md" && pass "the block carries what a compaction must keep" || fail "the compaction rule is missing from the block"
grep -q '{{' "$DIR/CLAUDE.md" && fail "an unrendered placeholder is left in CLAUDE.md" || pass "every placeholder is rendered"
[ -x "$DIR/bin/claude-1m" ] && pass "max installs the opus[1m] launcher" || fail "bin/claude-1m missing or not executable"
printf '#!/usr/bin/env bash\necho "window=$CLAUDE_CODE_AUTO_COMPACT_WINDOW args=$*"\n' > "$TMP/fake-claude"; chmod +x "$TMP/fake-claude"
out1m=$(CLAUDE_BIN="$TMP/fake-claude" "$DIR/bin/claude-1m" -p hi)
[ "$out1m" = "window=800000 args=--model opus[1m] -p hi" ] && pass "claude-1m runs opus[1m] with an 800k compaction window" || fail "claude-1m launched the wrong session" "$out1m"
out1m=$(CLAUDE_1M_COMPACT_WINDOW=500000 CLAUDE_BIN="$TMP/fake-claude" "$DIR/bin/claude-1m")
[ "$out1m" = "window=500000 args=--model opus[1m]" ] && pass "CLAUDE_1M_COMPACT_WINDOW lowers the 1m window" || fail "the window override was ignored" "$out1m"
out1m=$(CLAUDE_BIN="$TMP/fake-claude" "$DIR/bin/claude-1m" fable -p hi)
[ "$out1m" = "window=800000 args=--model fable[1m] -p hi" ] && pass "claude-1m fable runs fable[1m] with the same 800k window" || fail "claude-1m fable launched the wrong session" "$out1m"
out1m=$(CLAUDE_BIN="$TMP/fake-claude" "$DIR/bin/claude-1m" opus)
[ "$out1m" = "window=800000 args=--model opus[1m]" ] && pass "claude-1m opus is the default spelled out" || fail "claude-1m opus launched the wrong session" "$out1m"
grep -q 'claude-1m fable' "$DIR/claude-agentic/routing.md" && pass "routing.md offers Fable 5.1 [1m] as a session through claude-1m fable" || fail "routing.md does not mention claude-1m fable"
CLAUDE_1M_COMPACT_WINDOW=lots CLAUDE_BIN="$TMP/fake-claude" "$DIR/bin/claude-1m" >/dev/null 2>&1 && fail "a non-numeric window must be refused" || pass "a non-numeric window is refused"
[ "$(jq -r .autoCompactWindow "$DIR/settings.json")" = "800000" ] && pass "the launcher leaves the settings window for every other model alone" || fail "settings window changed"
grep -q 'claude-1m' "$DIR/claude-agentic/routing.md" && pass "routing.md says opus[1m] starts with claude-1m" || fail "routing.md does not mention claude-1m"
[ "$(jq -r '.modelSettings["claude-opus-5"].effortLevel' "$DIR/settings.json")" = "medium" ] && pass "Opus runs at medium" || fail "opus effort not medium"
[ "$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL // "unset"' "$DIR/settings.json")" = "unset" ] && pass "CLAUDE_CODE_SUBAGENT_MODEL is not set, so each agent's own model: applies" || fail "CLAUDE_CODE_SUBAGENT_MODEL would override every agent tier"
jq '.env.CLAUDE_CODE_SUBAGENT_MODEL = "sonnet"' "$DIR/settings.json" > "$DIR/s.tmp" && mv "$DIR/s.tmp" "$DIR/settings.json"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ "$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL // "unset"' "$DIR/settings.json")" = "unset" ] && pass "a reinstall removes the stale sonnet override" || fail "the stale sonnet override survived a reinstall"
[ "$(jq -r '.env.CLAUDE_READ_MAX_LINES' "$DIR/settings.json")" = "4000" ] && pass "the rest of env survives the cleanup" || fail "the cleanup dropped other env keys"
jq '.env.CLAUDE_CODE_SUBAGENT_MODEL = "opus"' "$DIR/settings.json" > "$DIR/s.tmp" && mv "$DIR/s.tmp" "$DIR/settings.json"
out=$(CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes 2>&1)
[ "$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL' "$DIR/settings.json")" = "opus" ] && pass "a user-chosen override is kept" || fail "a user-chosen override was removed"
grep -q 'CLAUDE_CODE_SUBAGENT_MODEL=opus is set' <<<"$out" && pass "the installer warns about a user-set override" || fail "no warning for a user-set override"
grep -q 'Before 2.1.251' <<<"$out" && pass "the warning says the override flattens the tiers only before Claude Code 2.1.251" || fail "the warning does not name the 2.1.251 boundary"
jq 'del(.env.CLAUDE_CODE_SUBAGENT_MODEL)' "$DIR/settings.json" > "$DIR/s.tmp" && mv "$DIR/s.tmp" "$DIR/settings.json"
grep -q 'claude-agentic:start' "$DIR/CLAUDE.md" && pass "the CLAUDE.md block is written" || fail "block missing"

echo "== backups never land inside skills/"
printf 'stale\n' > "$DIR/skills/ai-init/EXTRA.md"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ -z "$(ls -d "$DIR"/skills/*.bak 2>/dev/null)" ] \
    && pass "no *.bak directory is left in skills/ (they would load as duplicate skills)" \
    || fail "a backup was left in skills/" "$(ls -d "$DIR"/skills/*.bak)"
[ -d "$DIR/backups/$(date +%F)/skills/ai-init" ] && pass "the backup went to backups/<date>/skills/ instead" || fail "backup not found in backups/<date>/skills/"
mkdir -p "$DIR/skills/legacy.bak"
CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes >/dev/null 2>&1
[ ! -d "$DIR/skills/legacy.bak" ] && pass "a backup left by an older installer is moved out" || fail "stale .bak skill not cleaned up"

echo "== an older install: its *.bak files, the stale agents (2026-09-02 and redesign 2.4) and the shim move to backups/<date>/"
DAY=$(date +%F)
STALE="code-implementer qa-runner qa-fixer db-migrator doc-lookup log-inspector sylius-i18n-keys"
for a in $STALE $RETIRED_24; do printf -- '---\nname: %s\n---\nold\n' "$a" > "$DIR/agents/$a.md"; done
printf 'mine\n' > "$DIR/agents/x.md"; printf 'old mine\n' > "$DIR/agents/x.md.bak"
printf 'orphan\n' > "$DIR/agents/gone.md.bak"
printf 'old\n' > "$DIR/hooks/ai-git-guard.sh.bak"; printf 'old\n' > "$DIR/hooks/lib/ai-hook-common.sh.bak"
printf 'old\n' > "$DIR/claude-agentic/routing.md.bak"
printf '{}\n' > "$DIR/settings.json.bak"; printf 'old\n' > "$DIR/CLAUDE.md.bak"
printf '#!/usr/bin/env python3\n' > "$DIR/hooks/fable-gate.py"
printf 'old\n' > "$DIR/bin/claude-1m.bak"
mkdir -p "$DIR/skills/status"; printf -- '---\nname: status\n---\nold\n' > "$DIR/skills/status/SKILL.md"
out=$(CLAUDE_DIR="$DIR" bash "$INSTALL" --plan max --fable yes 2>&1)
[ ! -e "$DIR/skills/status" ] && [ -f "$DIR/backups/$DAY/skills/status/SKILL.md" ] \
    && grep -q "retired: skills/status -> backups/$DAY/skills/status" <<<"$out" \
    && pass "an installed skills/status is retired into backups/<date>/skills/" || fail "skills/status not retired" "$out"
[ ! -e "$DIR/bin/claude-1m.bak" ] && [ -f "$DIR/backups/$DAY/bin/claude-1m.bak" ] \
    && pass "bin/claude-1m.bak is swept too" || fail "bin/*.bak not swept" "$out"
for a in $STALE $RETIRED_24; do
    [ ! -e "$DIR/agents/$a.md" ] && [ -f "$DIR/backups/$DAY/agents/$a.md" ] \
        && grep -q "retired: agents/$a.md -> backups/$DAY/agents/$a.md" <<<"$out" \
        && pass "agents/$a.md is retired into backups/<date>/agents/" || fail "agents/$a.md not retired" "$out"
done
[ -f "$DIR/agents/x.md" ] && [ "$(cat "$DIR/backups/$DAY/agents/x.md.bak")" = "old mine" ] && [ ! -e "$DIR/agents/x.md.bak" ] \
    && pass "a seeded x.md.bak beside a live x.md moves to backups/<date>/agents/x.md.bak" || fail "x.md.bak not swept" "$out"
grep -q "moved: agents/x.md.bak -> backups/$DAY/agents/x.md.bak" <<<"$out" && pass "and the move is printed" || fail "sweep not reported" "$out"
[ -f "$DIR/agents/gone.md.bak" ] && pass "a .bak with no live file beside it is left alone" || fail "orphan .bak moved"
[ ! -e "$DIR/hooks/fable-gate.py" ] && [ -f "$DIR/backups/$DAY/hooks/fable-gate.py" ] \
    && pass "an installed fable-gate.py shim is retired too" || fail "shim not retired" "$out"
left=$(for f in "$DIR"/*.bak "$DIR"/agents/*.bak "$DIR"/hooks/*.bak "$DIR"/hooks/lib/*.bak "$DIR"/claude-agentic/*.bak "$DIR"/bin/*.bak; do
           [ -f "$f" ] && [ -e "${f%.bak}" ] && printf '%s ' "${f#"$DIR"/}"; done)
[ -z "$left" ] && pass "no *.bak is left beside a live file" || fail "*.bak left beside a live file" "$left"
[ -z "$(cd "$DIR" && find . -path ./backups -prune -o -name '*.bak' -print | grep -v '^./agents/gone.md.bak$')" ] \
    && pass "an install writes no *.bak anywhere outside backups/" || fail "*.bak written" "$(cd "$DIR" && find . -path ./backups -prune -o -name '*.bak' -print)"
[ -f "$DIR/backups/$DAY/settings.json" ] && [ -f "$DIR/backups/$DAY/CLAUDE.md" ] \
    && pass "settings.json and CLAUDE.md are backed up into backups/<date>/" || fail "root backups missing" "$(ls "$DIR/backups/$DAY")"
rm -f "$DIR/agents/x.md" "$DIR/agents/gone.md.bak"

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
grep -q 'migrated the claude-routing block' <<<"$out" && pass "the migration is reported" || fail "migration should be reported" "$out"
[ "$(grep -c 'claude-agentic:start' "$DIR3/CLAUDE.md")" = 1 ] && pass "exactly one managed block remains" || fail "expected one block"
grep -q 'claude-routing:start' "$DIR3/CLAUDE.md" && fail "the predecessor block should have been migrated away" || pass "the claude-routing block is migrated away"
grep -q 'routing rules' "$DIR3/CLAUDE.md" && fail "the old block's content should be gone" || pass "its superseded content is removed"
grep -q '# My own notes' "$DIR3/CLAUDE.md" && pass "the user's own content is kept" || fail "user content must survive migration"

summary "install.sh"
