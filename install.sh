#!/usr/bin/env bash
# claude-agentic installer (Claude Code and/or Codex).
#   ./install.sh [--target auto|claude|codex|both] [--plan pro|team-pro|team-max|max|max20|balanced-max]
#                [--fable auto|yes|no] [--codex-plan plus|pro|balanced-max] [--dry-run]
# --target defaults to auto: each runtime is installed only if it is present.
# --plan   Claude only: pro, team-pro (Team Standard seat), team-max (Team Premium seat), max
#          or max20 (Max 20x: max's settings, larger budgets). Defaults to auto-detect from
#          ~/.claude.json (organizationType, organizationRateLimitTier, the seat tiers for a
#          Team org). On a terminal the detected plan is proposed and Enter confirms it (a plan
#          recorded by an earlier install is the proposal); without one the detection is used
#          and printed on stderr. --plan skips the question.
#          balanced-max is never detected, only chosen: a Max account where only the session
#          runs Opus 5.5 (200k window) — readers stay on Haiku, judgement on Sonnet, reviews on
#          Opus, ai-expert on Opus at high; no Fable, no xhigh. It also selects the Codex
#          balanced-max profile unless --codex-plan is given.
# --fable  Claude only. auto = yes on max, max20 and team-max, no on pro and team-pro. On max the
#          session runs Opus 5.5 [1m] (1M window) either way; yes pins Fable 5.1 [1m] on architect alone.
# --codex-plan  Codex only: plus, pro or balanced-max (Sol session, readers on Luna). Defaults to auto-detect from the ChatGPT login in
#          ~/.codex/auth.json (chatgpt_plan_type); confirmed on a terminal like --plan, and
#          assumes pro when it cannot detect or ask.
# Both runtimes get <home>/claude-agentic/profile.json: the resolved plan tables
# (scripts/resolve-profile.py) that the gate, state.py and the reports read.
# --dry-run prints everything that would be written, per runtime, and writes nothing.
#
# Claude Code (~/.claude): model, effort and context settings for the detected
# plan (each agent pins its own tier); the ai-* pipeline agents plus architect,
# Explore and log-reader; six hooks plus runtime-gate (Fable branch on a Fable install); the
# skills; and one managed block in ~/.claude/CLAUDE.md.
#
# Codex (~/.codex): the same pipeline on the Terra -> Sol -> Astra ladder, sized
# per ChatGPT plan (profiles/codex-{plus,pro}.json). Pro: session gpt-5.6-sol at
# high, six agent threads, ai-expert on gpt-6-astra at xhigh. Plus: Sol at medium,
# three threads, Astra at high and xhigh off. Subagents default to gpt-5.6-terra,
# the agents are rendered as custom-agent TOML files, the guards are registered
# in ~/.codex/hooks.json, and one managed block is written to ~/.codex/AGENTS.md.
# Codex lists a non-managed hook until you trust it: run /hooks once afterwards.
#
# pro and team-pro (a Team Standard seat has Pro's models and limits): session model
# `opusplan` — Opus in plan mode, Sonnet when executing — and the EXPERT tier pinned to opus.
# max and team-max (a Team Premium seat has Max's models): session model Opus 5.5 [1m] (1M window
# by default, pinned as claude-opus-5-5[1m]; `/model opus` for a 200k session), ai-expert pinned to opus at xhigh, architect alone on Fable.
#
# This plugin supersedes claude-routing. On the first run it migrates that
# plugin's managed block into this one's, so the two never coexist.
#
# Idempotent: re-running updates in place, backs up what it replaces to *.bak,
# and never duplicates a hook entry or a managed block.
set -euo pipefail

# An explicitly supplied CLAUDE_DIR/CODEX_DIR is how the test suite points the
# installer at a scratch tree. Remember which one was given before defaulting,
# because under --target auto, supplying exactly one of them means "this runtime
# only" — otherwise a test that scopes CLAUDE_DIR would still write to the
# developer's real ~/.codex.
CLAUDE_DIR_GIVEN=0; if [ -n "${CLAUDE_DIR:-}" ]; then CLAUDE_DIR_GIVEN=1; fi
CODEX_DIR_GIVEN=0;  if [ -n "${CODEX_DIR:-}" ];  then CODEX_DIR_GIVEN=1;  fi
CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
CODEX_DIR="${CODEX_DIR:-$HOME/.codex}"
SRC="$(cd "$(dirname "$0")" && pwd)"
PLAN="" FABLE="auto" DRY=0 TARGET=auto PLAN_GIVEN=0
CODEX_PLAN="" CODEX_PLAN_GIVEN=0

while [ $# -gt 0 ]; do
  case "$1" in
    --target) TARGET="${2:?missing value for --target}"; shift 2;;
    --target=*) TARGET="${1#*=}"; shift;;
    --plan)  PLAN="${2:?missing value for --plan}"; PLAN_GIVEN=1; shift 2;;
    --plan=*) PLAN="${1#*=}"; PLAN_GIVEN=1; shift;;
    --fable) FABLE="${2:?missing value for --fable}"; PLAN_GIVEN=1; shift 2;;
    --fable=*) FABLE="${1#*=}"; PLAN_GIVEN=1; shift;;
    --codex-plan) CODEX_PLAN="${2:?missing value for --codex-plan}"; CODEX_PLAN_GIVEN=1; shift 2;;
    --codex-plan=*) CODEX_PLAN="${1#*=}"; CODEX_PLAN_GIVEN=1; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,32p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done
case "$TARGET" in auto|claude|codex|both) ;; *) echo "--target must be auto|claude|codex|both (got '$TARGET')" >&2; exit 2;; esac

command -v jq >/dev/null 2>&1 || { echo "jq is required (apt install jq)" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

# ---------------------------------------------------------------- runtime detection
DO_CLAUDE=0 DO_CODEX=0
case "$TARGET" in
  claude) DO_CLAUDE=1;;
  codex)  DO_CODEX=1;;
  both)   DO_CLAUDE=1; DO_CODEX=1;;
  auto)
    if [ "$CLAUDE_DIR_GIVEN" = 1 ] && [ "$CODEX_DIR_GIVEN" = 0 ]; then
      DO_CLAUDE=1
    elif [ "$CODEX_DIR_GIVEN" = 1 ] && [ "$CLAUDE_DIR_GIVEN" = 0 ]; then
      DO_CODEX=1
    else
      if command -v claude >/dev/null 2>&1 || [ -d "$CLAUDE_DIR" ] || [ "$PLAN_GIVEN" = 1 ]; then DO_CLAUDE=1; fi
      if command -v codex  >/dev/null 2>&1 || [ -d "$CODEX_DIR"  ] || [ "$CODEX_PLAN_GIVEN" = 1 ]; then DO_CODEX=1; fi
    fi;;
esac
if [ "$DO_CLAUDE" = 0 ] && [ "$DO_CODEX" = 0 ]; then
  cat >&2 <<'NONE'
No supported runtime found.

Looked for a `claude` or `codex` executable on PATH and for an existing
~/.claude or ~/.codex directory, and found neither. Install Claude Code or
Codex first, or name the runtime yourself:

  ./install.sh --target claude      # Claude Code only
  ./install.sh --target codex       # Codex only
  ./install.sh --target both        # both, whether or not they are detected
NONE
  exit 1
fi
if [ "$TARGET" = auto ]; then
  chosen=""
  if [ "$DO_CLAUDE" = 1 ]; then chosen="$chosen claude"; fi
  if [ "$DO_CODEX" = 1 ]; then chosen="$chosen codex"; fi
  echo "detected runtime:$chosen"
fi

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# render <src> <dst> — substitute {{PLACEHOLDER}}s from the environment.
# The variable set differs per runtime; both are exported by their render step.
render() {
  python3 - "$1" "$2" <<'PY'
import os, re, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
text = re.sub(r"\{\{([A-Z_]+)\}\}",
              lambda m: os.environ.get("RENDER_" + m.group(1), m.group(0)), text)
assert "{{" not in text, "unrendered placeholder in %s" % src
open(dst, "w").write(text)
PY
}

# render_stub <scope> <runtime> <dst> — the always-loaded managed block, from
# instructions/stub.md. The RENDER_* variables its caller exports are read by the
# renderer exactly as render() reads them.
render_stub() {
  python3 "$SRC/skills/project-update/render_instructions.py" render \
          --scope "$1" --runtime "$2" --kind "${4:-block}" --source "$SRC" --out "$3"
}

# block_size <file.md> <budget> — what the always-loaded block costs, and how much
# of the file is the user's own. Printed after every managed_block; never fatal,
# the user's own file is not the plugin's to refuse.
block_size() {
  python3 -c '
import sys
path, budget = sys.argv[1], int(sys.argv[2])
text = open(path, encoding="utf-8").read()
start = text.find("<!-- claude-agentic:start -->")
end = text.find("<!-- claude-agentic:end -->")
block = len(text[start:end + 26].encode("utf-8")) if start >= 0 and end >= 0 else 0
spaced = lambda n: "{:,}".format(n).replace(",", " ")
print("%s: managed block %s B (budget %s), file %s B — the rest is yours"
      % (path.split("/")[-1], spaced(block), spaced(budget),
         spaced(len(text.encode("utf-8")))))
' "$1" "$2"
}

# codex_doc_advisory <file.md> — Codex reads at most 32 KiB of project docs, and
# the plugin owns only the block; say so once the whole file gets close.
codex_doc_advisory() {
  local size
  size=$(wc -c < "$1")
  if [ "$size" -gt 16384 ]; then
    echo "$(basename "$1") is $size B; Codex reads at most 32 KiB of project docs — consider a project .ai/"
  fi
}

# agentic_profile <runtime> <profile> <plan> <label> <fable> — the resolved
# claude_agentic tables plus who wrote them (I2), for <home>/claude-agentic/profile.json.
PLUGIN_VERSION=$(jq -r '.version // "unknown"' "$SRC/.codex-plugin/plugin.json" 2>/dev/null || echo unknown)
agentic_profile() {
  python3 "$SRC/scripts/resolve-profile.py" "$2" --src "$SRC" --plan "$3" --label "$4" --fable "$5" --print agentic \
    | jq --arg rt "$1" --arg v "$PLUGIN_VERSION" --arg at "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
         '.runtime = $rt | .plugin_version = $v | .written_at = $at'
}

# write_profile <home> <rendered> — profile.json is plugin state, replaced
# rather than backed up, and only when something other than written_at changed,
# so a second install leaves it alone.
write_profile() {
  local dst="$1/claude-agentic/profile.json"
  if [ -f "$dst" ] && [ "$(jq -S 'del(.written_at)' "$dst" 2>/dev/null)" = "$(jq -S 'del(.written_at)' "$2")" ]; then
    return 0
  fi
  mkdir -p "$1/claude-agentic"
  cp "$2" "$dst"
  chmod 0644 "$dst"
}

# ================================================================= Claude Code
# The Claude branch is unchanged from the single-runtime installer. It lives in
# functions so the Codex branch can be skipped or run independently; the bodies
# are kept at their original indentation so this stays diff-comparable.
claude_render() {

# ---------------------------------------------------------------- plan detection
# Four plans, two tiers. pro and team-pro (a Team Standard seat) share the pro
# profile; max and team-max (a Team Premium seat) share the max profile. A Team
# org says nothing about the seat in organizationType, so the seat and rate-limit
# tier fields decide, and an undetectable Team seat is asked for on a tty.
PREV_PLAN=$(jq -r '.plan // empty' "$CLAUDE_DIR/claude-agentic/profile.json" 2>/dev/null || true)
if [ -z "$PLAN" ]; then
  org=$(jq -r '.oauthAccount.organizationType // .organizationType // empty' "$HOME/.claude.json" 2>/dev/null || true)
  ratelimit=$(jq -r '.oauthAccount.organizationRateLimitTier // empty' "$HOME/.claude.json" 2>/dev/null || true)
  DETECTED="" DETECTED_FROM=""
  case "$org" in
    claude_max*|*max*)
      case "$ratelimit" in
        *max_20x*) DETECTED=max20; DETECTED_FROM="organizationRateLimitTier $ratelimit";;
        *)         DETECTED=max;   DETECTED_FROM="organizationType $org${ratelimit:+, $ratelimit}";;
      esac;;
    claude_pro*|*pro*) DETECTED=pro; DETECTED_FROM="organizationType $org";;
    claude_team*|*team*|claude_enterprise*|*enterprise*)
      seat=$(jq -r '.oauthAccount | [.seatTier, .userRateLimitTier, .organizationRateLimitTier] | map(select(. != null and . != "")) | join(" ")' \
             "$HOME/.claude.json" 2>/dev/null || true)
      case "$seat" in
        *premium*|*max*) DETECTED=team-max; DETECTED_FROM="$org, seat '$seat'";;
        *standard*|*pro*) DETECTED=team-pro; DETECTED_FROM="$org, seat '$seat'";;
        *) DETECTED_FROM="team";;
      esac;;
  esac
  if [ -t 0 ]; then
    # Propose, then confirm: a plan an earlier install recorded wins over the
    # detection, because the person already chose it once.
    PROPOSED="${PREV_PLAN:-$DETECTED}"
    if [ -n "$PROPOSED" ]; then
      why="detected from $DETECTED_FROM"
      [ -n "$PREV_PLAN" ] && why="recorded by the previous install"
      read -r -p "plan: $PROPOSED ($why) — Enter to confirm, or type pro/team-pro/team-max/max/max20/balanced-max: " PLAN
      PLAN="${PLAN:-$PROPOSED}"
    elif [ "$DETECTED_FROM" = team ]; then
      read -r -p "Team org detected ($org) but not the seat. Enter plan [team-pro/team-max]: " PLAN
    else
      read -r -p "Could not detect plan (organizationType='$org'). Enter plan [pro/team-pro/team-max/max/max20]: " PLAN
    fi
  elif [ -n "$DETECTED" ]; then
    PLAN=$DETECTED; echo "detected plan: $PLAN ($DETECTED_FROM)" >&2
  elif [ "$DETECTED_FROM" = team ]; then
    PLAN=team-pro
    echo "detected plan: team ($org) — seat unknown, using team-pro (Pro's models and limits); pass --plan team-max for a Premium seat" >&2
  elif [ -n "$PREV_PLAN" ]; then
    PLAN=$PREV_PLAN; echo "plan: $PLAN (recorded by the previous install; organizationType='$org')" >&2
  else
    echo "Could not detect plan; pass --plan pro|team-pro|team-max|max|max20" >&2; exit 1
  fi
fi
case "$PLAN" in
  team-standard|team_standard|team) PLAN=team-pro;;
  team-premium|team_premium) PLAN=team-max;;
  team_pro) PLAN=team-pro;;
  team_max) PLAN=team-max;;
esac
case "$PLAN" in
  pro)      TIER=pro; PROFILE_NAME=pro;   PLAN_LABEL="Pro";;
  team-pro) TIER=pro; PROFILE_NAME=pro;   PLAN_LABEL="Team Pro";;
  team-max) TIER=max; PROFILE_NAME=max;   PLAN_LABEL="Team Max";;
  max)      TIER=max; PROFILE_NAME=max;   PLAN_LABEL="Max";;
  max20|max-20x|max_20x) PLAN=max20; TIER=max; PROFILE_NAME=max20; PLAN_LABEL="Max 20x";;
  balanced-max|balanced_max|balancedmax) PLAN=balanced-max; TIER=max; PROFILE_NAME=balanced-max; PLAN_LABEL="BalancedMax";;
  *) echo "--plan must be pro, team-pro, team-max, max, max20 or balanced-max (got '$PLAN')" >&2; exit 2;;
esac
case "$FABLE" in
  auto) [ "$TIER" = max ] && [ "$PLAN" != balanced-max ] && FABLE=yes || FABLE=no;;
  yes|no) ;;
  *) echo "--fable must be auto|yes|no" >&2; exit 2;;
esac
if { [ "$TIER" = pro ] || [ "$PLAN" = balanced-max ]; } && [ "$FABLE" = yes ]; then
  echo "Fable is not available on the $PLAN plan; using --fable no" >&2; FABLE=no
fi

# ---------------------------------------------------------------- render settings
# The profile's claude_agentic tables are the plugin's, not Claude Code's: the
# resolver prints the settings half alone, so they never reach settings.json.
python3 "$SRC/scripts/resolve-profile.py" "$PROFILE_NAME" --src "$SRC" --print settings > "$TMP/profile.settings.json"
if [ "$TIER" = max ] && [ "$FABLE" = no ]; then
  jq '.availableModels = (.availableModels | map(select(startswith("fable") | not)))
      | del(.modelSettings["claude-fable-5-1"])' "$TMP/profile.settings.json" > "$TMP/profile.json"
else
  cp "$TMP/profile.settings.json" "$TMP/profile.json"
fi
agentic_profile claude "$PROFILE_NAME" "$PLAN" "$PLAN_LABEL" "$FABLE" > "$TMP/claude-profile.json"
tier_field() { jq -r --arg t "$1" --arg f "$2" '.tiers[$t][$f]' "$TMP/claude-profile.json"; }
jq -s '.[0] * .[1]' "$SRC/settings.common.json" "$TMP/profile.json" > "$TMP/settings.snippet.json"

SESSION_MODEL=$(jq -r .model "$TMP/settings.snippet.json")
FALLBACK=$(jq -r '.fallbackModel | if type=="array" then join(", then ") else . end' "$TMP/settings.snippet.json")
EFFORT=$(jq -r .effortLevel "$TMP/settings.snippet.json")
COMPACT=$(jq -r .autoCompactWindow "$TMP/settings.snippet.json")
# Auto-compaction fires about 33k under the window (measured: a 150000 window
# compacts near 117k), so that is the number a person should read.
# context-guard.py derives its warn and block thresholds from the same point.
#
# `autoCompactWindow` is one value for every model, but Claude Code caps it at the
# model's own window, so the single setting means two different things: an ordinary
# 200k session compacts near MODEL_WINDOW - 33000, a [1m] session near COMPACT - 33000.
# Print the number that matches the session this install configures.
MODEL_WINDOW=200000
case "$SESSION_MODEL" in *"[1m]"*) MODEL_WINDOW=1000000;; esac
COMPACT_EFFECTIVE=$COMPACT
[ "$COMPACT" -gt "$MODEL_WINDOW" ] && COMPACT_EFFECTIVE=$MODEL_WINDOW
COMPACT_AT=$((COMPACT_EFFECTIVE - 33000))
ONE_M_WINDOW=$(sed -n 's/^WINDOW="${CLAUDE_1M_COMPACT_WINDOW:-\([0-9]*\)}"$/\1/p' "$SRC/bin/claude-1m")
ONE_M_AT=$((ONE_M_WINDOW - 33000))
ONE_M_FABLE=""
[ "$FABLE" = yes ] && ONE_M_FABLE=" and \`claude-1m fable\` for Fable 5.1 [1m]"
ONE_M_RULE="One \`autoCompactWindow\` of ${COMPACT} serves every model: Claude Code caps it at the model's own window, so this session compacts near ${COMPACT_AT} and a \`[1m]\` one near ${ONE_M_AT}, whether it was started with \`claude-1m\` (\`~/.claude/bin/claude-1m\`) for \`opus[1m]\`${ONE_M_FABLE} or switched to with \`/model\`. \`claude-1m\` pins the model at launch and \`CLAUDE_1M_COMPACT_WINDOW\` lowers the window for that one process; it is no longer what grants the large window. When a task inside an ordinary session needs one large-context read, say so and, once the user agrees, run \`claude-1m -p '<brief>'\` from Bash — its own process, only the answer comes back."
if [ "$MODEL_WINDOW" -gt 200000 ]; then
  ONE_M_RULE="\`autoCompactWindow\` ${COMPACT} applies uncapped to this 1M session, so it compacts near ${COMPACT_AT}; a 200k model picked with \`/model opus\` is capped at its own window and compacts near 167000. For a small task a 200k session is cheaper per turn — say so and let the user switch. \`claude-1m\` (\`~/.claude/bin/claude-1m\`) still pins the model at launch${ONE_M_FABLE}, and \`CLAUDE_1M_COMPACT_WINDOW\` lowers the window for that one process."
fi
READ_LINES=$(jq -r '.env.CLAUDE_READ_MAX_LINES' "$TMP/settings.snippet.json")
READ_BYTES=$(jq -r '.env.CLAUDE_READ_MAX_BYTES' "$TMP/settings.snippet.json")

SESSION_HUMAN=$(pretty "$SESSION_MODEL")
FALLBACK_HUMAN=$(jq -r '.fallbackModel | if type=="array" then .[] else . end' "$TMP/settings.snippet.json" \
                 | while read -r m; do pretty "$m"; done | paste -sd'|' | sed 's/|/, then /g')

# Every agent definition pins its own `model:`; CLAUDE_CODE_SUBAGENT_MODEL is not
# set, because before Claude Code v2.1.251 (still bundled by the JetBrains ACP
# adapter) it overrides both the frontmatter and the per-call model, and from
# v2.1.251 it would send an agent that omits `model:` on purpose (architect with
# --fable no) to Sonnet instead of the session. The EXPERT-tier agents
# are rendered per tier: on pro/team-pro both pin opus (an inherited model would
# be Sonnet outside plan mode); on max/team-max ai-expert pins opus at xhigh and
# architect alone is pinned to fable[1m] when Fable is enabled.
# fallbackModel applies to pinned subagents too, so a Fable outage still falls back.
if [ "$TIER" = pro ]; then
  EXPERT_EFFORT="high"
  # On opusplan a subagent that omits `model:` inherits Sonnet outside plan mode,
  # so both EXPERT-tier agents pin opus explicitly on this plan.
  EXPERT_MODEL_LINE="model: opus"
  ARCHITECT_MODEL_LINE="model: opus"
  ARCHITECT_EFFORT="high"
  EXPERT_ROW="\`opus\` / \`high\`, pinned — on opusplan an inherited model is Sonnet outside plan mode"
  PLAN_SPECIFIC="- Session model is \`opusplan\`: Opus 5 in plan mode, Sonnet 5 when executing. Use plan mode for T3+ and for a T2 that spans several modules — that is where Opus is paid for. Fable is off this plan; never request it. \`xhigh\`/\`max\` are unavailable. STRONG and EXPERT both pin \`model: opus\` explicitly."
  EFFORT_RULE="Raise to \`high\` only for architecture, root-cause analysis and adversarial verification, and say that you are raising it."
else
  # Pinned rather than inherited: a session may run on Sonnet (the JetBrains ACP
  # agent's Model setting, or /model), and the last-resort tier must not drop below
  # the opus reviewer it escalates from. xhigh is what separates it from STRONG,
  # which is already opus/high; fallbackModel still applies to a pinned agent.
  EXPERT_EFFORT="$(tier_field EXPERT effort)"
  EXPERT_MODEL_LINE="model: opus"
  if [ "$FABLE" = yes ]; then
    ARCHITECT_MODEL_LINE="model: fable[1m]"
    ARCHITECT_EFFORT="xhigh"
    EXPERT_ROW="\`opus\` / \`xhigh\`, pinned so a Sonnet session cannot weaken it; \`architect\` alone pins \`fable[1m]\` / \`xhigh\`"
    PLAN_SPECIFIC="- Session model is ${SESSION_HUMAN} by default, compaction near ${COMPACT_AT} tokens (\`autoCompactWindow\` ${COMPACT}). A large context is not free: every turn re-reads it, so keep \`/clear\` between tasks. ${ONE_M_RULE} \`ai-expert\` pins \`opus\` at \`xhigh\` rather than inheriting the session: a session may run on Sonnet (the IDE agent's Model setting), and the last-resort tier must not drop below the \`opus\` reviewer it escalates from. Fable 5.1 [1m] is pinned on \`architect\` (\`model: fable[1m]\`, \`xhigh\`) and is the session only when the user starts one with \`claude-1m fable\` — never pick it for a reader, a reviewer or \`ai-expert\`. \`max\` stays off.
- \`runtime-gate\` checks Fable at run time. \`fallbackModel\` covers an overload; after a rate-limit or model-not-found failure, and while the weekly limit is ${CLAUDE_FABLE_GATE_WEEKLY_PCT:-90}% or more used, the gate sends every \`model: fable\` agent to Opus until the reset, and says so in the agent's context. If a Fable agent still returns such an error, re-run the same brief once with \`model: opus\` — an availability switch, not a downgrade. \`~/.claude/hooks/runtime-gate.py status\` shows the gate (\`fable-gate.py status\` still works); \`clear\` re-enables Fable early."
  else
    ARCHITECT_MODEL_LINE="# model: intentionally omitted — inherits the session model (${SESSION_HUMAN}, Fable disabled in this install)"
    ARCHITECT_EFFORT="high"
    EXPERT_ROW="\`opus\` / \`${EXPERT_EFFORT}\`, pinned so a Sonnet session cannot weaken it"
    PLAN_SPECIFIC="- Session model is ${SESSION_HUMAN} by default, compaction near ${COMPACT_AT} tokens (\`autoCompactWindow\` ${COMPACT}). ${ONE_M_RULE} Fable is disabled in this install (\`--fable no\`). Do not request \`model: fable\` anywhere. \`ai-expert\` alone pins \`model: opus\` at \`xhigh\`, so a Sonnet session cannot weaken the last-resort tier; \`xhigh\` stays off everywhere else and \`max\` stays off."
  fi
  if [ "$PLAN" = balanced-max ]; then
    ARCHITECT_MODEL_LINE="# model: intentionally omitted — inherits the session model (Opus 5.5; no Fable on BalancedMax)"
    PLAN_SPECIFIC="- BalancedMax: only the session runs the strong model. Session model is Opus 5.5 with the 200k window and compaction near ${COMPACT_AT} tokens (\`autoCompactWindow\` ${COMPACT}); it plans and implements. Agents keep their cheap tiers — readers and runners (\`Explore\`, \`log-reader\`, \`ai-tester\`, \`ai-indexer\`) on \`$(tier_field FAST model)\` / \`$(tier_field FAST effort)\`, judgement on \`$(tier_field BALANCED model)\`, \`ai-reviewer\` and \`ai-security\` on \`$(tier_field STRONG model)\`. \`ai-expert\` pins \`opus\` at \`${EXPERT_EFFORT}\` and \`architect\` inherits the session. \`opus[1m]\` is a per-task choice, never the default. ${ONE_M_RULE} Fable is off on this plan; never request \`model: fable\`. \`xhigh\` and \`max\` stay off."
  fi
  EFFORT_RULE="Raise to \`high\` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; readers stay at \`low\`."
fi

# runtime-gate runs on every plan (budgets, the running-agent count, quota).
# Its Fable branch — StopFailure, and the Fable reroute it feeds — exists only
# where Fable does: on Max with --fable yes, where architect is pinned to
# fable[1m]. Elsewhere the StopFailure entry is left out of the snippet.
if [ "$TIER" = max ] && [ "$FABLE" = yes ]; then
  GATE=on
  jq '.' "$SRC/settings.gate.json" > "$TMP/gate.json"
else
  GATE=off
  jq 'del(.hooks.StopFailure)' "$SRC/settings.gate.json" > "$TMP/gate.json"
fi
jq -s '.[0] as $base | reduce (.[1].hooks | to_entries[]) as $e
         ($base; .hooks[$e.key] = ((.hooks[$e.key] // []) + $e.value))' \
   "$TMP/settings.snippet.json" "$TMP/gate.json" > "$TMP/snippet.gate.json"
mv "$TMP/snippet.gate.json" "$TMP/settings.snippet.json"

RENDER_PLAN="$PLAN_LABEL" \
RENDER_PLAN_LABEL="$PLAN_LABEL" \
RENDER_SESSION_MODEL="$SESSION_HUMAN" \
RENDER_FALLBACK_MODEL="$FALLBACK_HUMAN" \
RENDER_DEFAULT_EFFORT="$EFFORT" \
RENDER_COMPACT_WINDOW="$(printf '%s' "$COMPACT_AT" | python3 -c 'import sys;print("{:,}".format(int(sys.stdin.read())).replace(",", " "))')" \
RENDER_CONTEXT_WARN="$((COMPACT_AT * 80 / 100000))k" \
RENDER_CONTEXT_BLOCK="$((COMPACT_AT * 120 / 100000))k" \
RENDER_READ_LINES="$READ_LINES" \
RENDER_PLAN_SPECIFIC_ROUTING="$PLAN_SPECIFIC" \
RENDER_EFFORT_RULE="$EFFORT_RULE" \
RENDER_EXPERT_EFFORT="$EXPERT_EFFORT" \
RENDER_EXPERT_MODEL_LINE="$EXPERT_MODEL_LINE" \
RENDER_EXPERT_ROW="$EXPERT_ROW" \
RENDER_ARCHITECT_MODEL_LINE="$ARCHITECT_MODEL_LINE" \
RENDER_ARCHITECT_EFFORT="$ARCHITECT_EFFORT" \
RENDER_FAST_MODEL="$(tier_field FAST model)" \
RENDER_FAST_EFFORT="$(tier_field FAST effort)" \
RENDER_BALANCED_MODEL="$(tier_field BALANCED model)" \
RENDER_BALANCED_EFFORT="$(tier_field BALANCED effort)" \
RENDER_STRONG_MODEL="$(tier_field STRONG model)" \
RENDER_STRONG_EFFORT="$(tier_field STRONG effort)" \
  render_claude_files
}

render_claude_files() {
  # Every agent source is a template: the tier placeholders come from the
  # resolved profile's tiers, the EXPERT lines from the plan logic above.
  mkdir -p "$TMP/agents"
  for f in "$SRC"/agents/*.md.tmpl; do
    render "$f" "$TMP/agents/$(basename "$f" .tmpl)"
  done
  render_stub global claude "$TMP/CLAUDE.block.md"
  render_stub global claude "$TMP/routing.md" routing
}

pretty() {  # model id -> human name
  case "$1" in
    "fable[1m]") echo "Fable 5.1 [1m]";; fable*) echo "Fable 5.1";;
    opusplan) echo "Opus 5 in plan mode, Sonnet 5 when executing (opusplan)";;
    "claude-opus-5-5[1m]") echo "Opus 5.5 [1m]";; "opus[1m]") echo "Opus 5 [1m]";; claude-opus-5-5*) echo "Opus 5.5";; opus*) echo "Opus 5";;
    sonnet*) echo "Sonnet 5";; haiku*) echo "Haiku 4.5";; *) echo "$1";;
  esac
}

# Only the statusline receives the account's rate_limits, so the gate's weekly
# check rides on it: on a Fable install the statusline command is wrapped as
#   "$HOME/.claude/hooks/runtime-gate.py" statusline --then '<your command>'
# (or set to the bare check when there was none), and unwrapped to exactly the
# original command on any other install.
statusline_gate() {  # statusline_gate <settings.json> <on|off> <apply|dry>
  python3 - "$@" <<'PY'
import json, os, shlex, sys
path, gate, mode = sys.argv[1:4]
PREFIX = '"$HOME/.claude/hooks/runtime-gate.py" statusline'
OLD_PREFIX = '"$HOME/.claude/hooks/fable-gate.py" statusline'
try:
    settings = json.load(open(path)) if os.path.exists(path) else {}
except ValueError:
    print("statusline: settings.json is not valid JSON; left alone"); sys.exit(0)
line = settings.get("statusLine")
cmd = line.get("command", "") if isinstance(line, dict) else ""
ours = isinstance(cmd, str) and cmd.startswith(PREFIX)
if isinstance(cmd, str) and cmd.startswith(OLD_PREFIX):
    # A wrapper an earlier install wrote: re-point it, keeping the user's command.
    line["command"] = PREFIX + cmd[len(OLD_PREFIX):]
    ours, gate = True, "moved"
action = None
if gate == "moved":
    action = "moved the fable-gate statusline wrapper to runtime-gate (your command is unchanged)"
elif gate == "on":
    if ours:
        print("statusline: already records the quota"); sys.exit(0)
    if line is None:
        settings["statusLine"] = {"type": "command", "command": PREFIX}
        action = "added a silent statusline that records the quota (and the Fable weekly limit)"
    elif isinstance(line, dict) and line.get("type") == "command" and cmd.strip():
        line["command"] = f"{PREFIX} --then {shlex.quote(cmd)}"
        action = "wrapped your statusline command with the quota check (its output is unchanged)"
    else:
        print("statusline: not a command statusline; the weekly-limit check is not wired"); sys.exit(0)
else:
    if not ours:
        sys.exit(0)
    rest = cmd[len(PREFIX):].strip()
    if rest.startswith("--then"):
        parts = shlex.split(rest)
        line["command"] = parts[1] if len(parts) > 1 else ""
        action = "restored your original statusline command (runtime-gate off)"
    else:
        del settings["statusLine"]
        action = "removed the quota statusline (runtime-gate off)"
if mode == "dry":
    print("statusline: would have " + action); sys.exit(0)
tmp = path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(settings, fh, indent=2); fh.write("\n")
os.replace(tmp, path)
print("statusline: " + action)
PY
}

claude_dry_run() {
  echo "== claude: plan=$PLAN ($PLAN_LABEL, $TIER profile) fable=$FABLE fable-gate=$GATE runtime-gate=on (dry run, nothing written)"
  echo "== claude: target directory $CLAUDE_DIR"
  statusline_gate "$CLAUDE_DIR/settings.json" on dry | sed 's/^/== /'
  echo "== settings snippet (merged into $CLAUDE_DIR/settings.json):"
  jq . "$TMP/settings.snippet.json"
  echo "== agents/ai-expert.md (rendered head):"
  sed -n '1,10p' "$TMP/agents/ai-expert.md"
  echo "== agents/architect.md (rendered head):"
  sed -n '1,8p' "$TMP/agents/architect.md"
  echo "== CLAUDE.md managed block:"
  cat "$TMP/CLAUDE.block.md"
  echo "== routing.md (on demand): $CLAUDE_DIR/claude-agentic/routing.md"
  cat "$TMP/routing.md"
  echo "== profile.json (plan tables): $CLAUDE_DIR/claude-agentic/profile.json"
  jq . "$TMP/claude-profile.json"
  echo "== would install:"
  echo "   agents:  $(ls "$SRC/agents" | grep -v '^superseded$' | sed 's/\.md\(\.tmpl\)\?$//' | paste -sd,)"
  echo "   hooks:   $(ls "$SRC/hooks" | paste -sd,)"
  [ "$TIER" = max ] && echo "   bin:     claude-1m (opus[1m]$( [ "$FABLE" = yes ] && echo " / fable[1m]" ), pins the model at launch; compacts near $ONE_M_AT)"
  echo "   skills:  $(ls "$SRC/skills" | paste -sd,)"
  echo "   config:  ai-git-guard.json (only if absent)"
  echo "   routing: claude-agentic/routing.md"
  echo "   profile: claude-agentic/profile.json"
  echo "== would migrate: the claude-routing managed block, if present, into this one"
}

install_file() {  # install_file <src> <dst> [root] — back up on a real change, then copy
  local src="$1" dst="$2" root="${3:-$CLAUDE_DIR}"
  if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp "$dst" "$dst.bak"
    echo "backup: ${dst#"$root"/} -> $(basename "$dst").bak"
  fi
  cp "$src" "$dst"
  echo "installed: ${dst#"$root"/}"
}

# install_skills <destination-root> — a backup must not land inside skills/:
# both runtimes load every directory there as a skill, so a "<name>.bak" copy
# would show up as a second, stale command. Backups go to a sibling directory.
install_skills() {
  local root="$1" backups="$1/backups/skills" d name dst stale
  for d in "$SRC"/skills/*/; do
    name=$(basename "$d")
    dst="$root/skills/$name"
    if [ -d "$dst" ] && ! diff -rq -x __pycache__ "$d" "$dst" >/dev/null 2>&1; then
      mkdir -p "$backups"
      rm -rf "$backups/$name"; cp -r "$dst" "$backups/$name"
      echo "backup: skills/$name -> backups/skills/$name"
    fi
    rm -rf "$dst"; cp -r "$d" "$dst"
    # A developer who ran the scripts in place leaves __pycache__ behind; it
    # would otherwise be copied into the install and then shipped onward.
    find "$dst" -name '__pycache__' -type d -prune -exec rm -rf {} + 2>/dev/null || true
    echo "installed: skills/$name"
  done
  # Clean up backups a previous version of this installer left inside skills/,
  # where they were being loaded as duplicate skills.
  for stale in "$root"/skills/*.bak; do
    [ -d "$stale" ] || continue
    mkdir -p "$backups"
    rm -rf "$backups/$(basename "${stale%.bak}")-old"
    mv "$stale" "$backups/$(basename "${stale%.bak}")-old"
    echo "moved: skills/$(basename "$stale") -> backups/skills/ (it was loading as a duplicate skill)"
  done
  chmod +x "$root/skills/ai-init/scaffold-ai.sh" "$root/skills/ai-task/state.py" \
           "$root/skills/ai-task/sensors.py" "$root/skills/project-update/update.py"
}

# managed_block <target.md> <block-file> <label> — replace the one managed block,
# or append it; migrates the predecessor plugin's block and an unmarked legacy
# section on the way. Writes <target>.bak first.
managed_block() {
  local target="$1" block="$2" label="$3"
  touch "$target"
  cp "$target" "$target.bak"
  BLOCK="$block" LABEL="$label" python3 - "$target" <<'PY'
import os, re, sys
path = sys.argv[1]
block = open(os.environ["BLOCK"]).read().strip("\n")
label = os.environ["LABEL"]
text = open(path).read()
start, end = "<!-- claude-agentic:start -->", "<!-- claude-agentic:end -->"
notes = []

# Migrate the predecessor plugin's block: this one now carries its rules.
routing = re.search(r"<!-- claude-routing:start -->.*?<!-- claude-routing:end -->\n?", text, flags=re.S)
if routing:
    text = text[: routing.start()] + text[routing.end():]
    notes.append("migrated the claude-routing block")

# Migrate a pre-plugin unmarked "# Model allocation by task and scope" section.
legacy = re.search(r"(?m)^# Model allocation by task and scope.*?(?=^# |\Z)", text, flags=re.S)
if legacy and start not in text[: legacy.start()]:
    text = text[: legacy.start()] + text[legacy.end():]
    notes.append("migrated an unmarked 'Model allocation' section")

if start in text and end in text:
    new = re.sub(re.escape(start) + r".*?" + re.escape(end), lambda m: block, text, flags=re.S)
    action = "updated"
else:
    sep = "\n\n" if text.strip() else ""
    new = text.rstrip("\n") + sep + block + "\n"
    action = "appended"
new = re.sub(r"\n{4,}", "\n\n\n", new)
open(path, "w").write(new)
print("%s: %s%s (backup in %s.bak)"
      % (label, action, " + " + " + ".join(notes) if notes else "", label))
PY
}

claude_apply() {

mkdir -p "$CLAUDE_DIR/agents" "$CLAUDE_DIR/hooks/lib" "$CLAUDE_DIR/skills"

# ---------------------------------------------------------------- 1. agents
for f in "$TMP"/agents/*.md; do
  install_file "$f" "$CLAUDE_DIR/agents/$(basename "$f")"
done

# `reviewer` is superseded by `ai-reviewer`, which is adversarial, tier-aware and
# reads the project's policies. Retire it only when it is byte-identical to the
# copy claude-routing shipped — an edited one is the user's, and stays.
STALE="$CLAUDE_DIR/agents/reviewer.md"
if [ -e "$STALE" ]; then
  if cmp -s "$SRC/agents/superseded/reviewer.md" "$STALE"; then
    mv "$STALE" "$STALE.superseded"
    echo "retired: agents/reviewer.md -> reviewer.md.superseded (ai-reviewer replaces it)"
  else
    echo "kept: agents/reviewer.md — you have edited it. ai-reviewer supersedes it; delete it when you are ready."
  fi
fi

# ---------------------------------------------------------------- 2. hooks
for f in "$SRC"/hooks/*.sh "$SRC"/hooks/*.py "$SRC"/hooks/lib/*.sh; do
  [ -e "$f" ] || continue
  case "$f" in
    */codex-*) continue;;   # Codex-only guards; Claude has no event that fires them
    */lib/*) dst="$CLAUDE_DIR/hooks/lib/$(basename "$f")";;
    *)       dst="$CLAUDE_DIR/hooks/$(basename "$f")";;
  esac
  install_file "$f" "$dst"
  chmod +x "$dst"
done
install_file "$SRC/hooks/ai-path-guard-defaults.json" "$CLAUDE_DIR/hooks/ai-path-guard-defaults.json"
install_file "$SRC/hooks/ai-git-guard-defaults.json"  "$CLAUDE_DIR/hooks/ai-git-guard-defaults.json"

# The git guard's live config is user-owned: seed it once, never overwrite it.
if [ ! -e "$CLAUDE_DIR/hooks/ai-git-guard.json" ]; then
  cp "$SRC/hooks/ai-git-guard-defaults.json" "$CLAUDE_DIR/hooks/ai-git-guard.json"
  echo "installed: hooks/ai-git-guard.json (edit this one; it is never overwritten)"
else
  echo "kept: hooks/ai-git-guard.json (your edits are preserved)"
fi

# ---------------------------------------------------------------- 2b. opus[1m] launcher
# Max only: Pro has no opus[1m]. Linked into ~/.local/bin on a real install so it is
# on PATH; a scratch CLAUDE_DIR (tests) never writes outside itself.
if [ "$TIER" = max ]; then
  mkdir -p "$CLAUDE_DIR/bin"
  install_file "$SRC/bin/claude-1m" "$CLAUDE_DIR/bin/claude-1m"
  chmod +x "$CLAUDE_DIR/bin/claude-1m"
  LINK="$HOME/.local/bin/claude-1m"
  if [ "$CLAUDE_DIR" = "$HOME/.claude" ] && [ -d "$HOME/.local/bin" ]; then
    if [ ! -e "$LINK" ] || [ -L "$LINK" ]; then
      ln -sfn "$CLAUDE_DIR/bin/claude-1m" "$LINK"
      echo "linked: ~/.local/bin/claude-1m -> $CLAUDE_DIR/bin/claude-1m"
    else
      echo "kept: ~/.local/bin/claude-1m is not a link to this install; run $CLAUDE_DIR/bin/claude-1m directly"
    fi
  fi
fi

# ---------------------------------------------------------------- 3. skills
install_skills "$CLAUDE_DIR"

# ---------------------------------------------------------------- 4. settings.json
SETTINGS="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS" ]; then cp "$SETTINGS" "$SETTINGS.bak"; else echo '{}' > "$SETTINGS"; fi
# Every gate entry already in settings.json — fable-gate from before WP5, or
# runtime-gate from an earlier run — is removed first and the snippet's own are
# merged below, so an upgrade never leaves two gates on one event (the shim
# would run the gate twice and count every agent twice). Only the gate's own
# commands go (matched by their /hooks/<name>.py path, not a substring); a group
# or event list left empty by that is dropped, the user's own hooks stay.
before_gate=$(jq -c '[.hooks // {} | .[]?[]? | select((.hooks // []) | map(.command // "") | any(test("fable-gate")))] | length' "$SETTINGS" 2>/dev/null || echo 0)
had_stopfailure=$(jq -c '[.hooks.StopFailure // [] | .[] | select((.hooks // []) | map(.command // "") | any(test("fable-gate|runtime-gate")))] | length' "$SETTINGS" 2>/dev/null || echo 0)
jq 'if (.hooks | type) == "object" then
      .hooks |= (with_entries(.value |= [ .[]
          | if (.hooks | type) == "array" and (.hooks | length) > 0 then
              .hooks |= map(select((.command // "") | test("/hooks/(fable-gate|runtime-gate)\\.py") | not))
              | select(.hooks | length > 0)
            else . end ])
        | with_entries(select(.value | length > 0)))
    else . end' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
[ "$before_gate" != 0 ] && echo "replaced: fable-gate hooks with runtime-gate" || true
[ "$GATE" = off ] && [ "$had_stopfailure" != 0 ] && echo "removed: runtime-gate StopFailure (no Fable on this install)" || true

# jq's * replaces arrays wholesale (wanted for availableModels/fallbackModel), so
# merge everything but .hooks first, then append our hook entries only when no
# existing entry under the same event already runs the same command.
# Older installs set CLAUDE_CODE_SUBAGENT_MODEL=sonnet, which overrides every
# agent's own model:, so that value is removed; any other value is the user's.
jq -s '
  (.[1] | del(.hooks)) as $snippet
  | (.[1].hooks // {}) as $newhooks
  | (.[0] | if .env.CLAUDE_CODE_SUBAGENT_MODEL == "sonnet"
            then del(.env.CLAUDE_CODE_SUBAGENT_MODEL) else . end) as $base
  | ($base * $snippet) as $merged
  | reduce ($newhooks | to_entries[]) as $event
      ($merged;
        .hooks[$event.key] = (
          # An entry that already runs one of our commands is replaced by ours,
          # not left alone: otherwise a matcher this version widens (or a
          # timeout it raises) never reaches an install that has the old entry.
          ( (.hooks[$event.key] // [])
            | map( . as $old
                   | ( $event.value
                       | map(select(((.hooks // []) | map(.command))
                                    == (($old.hooks // []) | map(.command)))) ) as $ours
                   | if ($ours | length) > 0 then $ours[0] else $old end ) )
          + ( $event.value
              | map( . as $entry
                     | select( ($entry.hooks // []) | map(.command)
                               | any( . as $c | $merged.hooks[$event.key] // []
                                      | map(.hooks // [] | map(.command)) | flatten
                                      | index($c) ) | not ) ) )
        )
      )
' "$SETTINGS" "$TMP/settings.snippet.json" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
echo "merged: settings.json (backup in settings.json.bak)"

statusline_gate "$SETTINGS" on apply

# ---------------------------------------------------------------- 5. CLAUDE.md block
GLOBAL_MD="$CLAUDE_DIR/CLAUDE.md"
managed_block "$GLOBAL_MD" "$TMP/CLAUDE.block.md" "CLAUDE.md"
mkdir -p "$CLAUDE_DIR/claude-agentic"
install_file "$TMP/routing.md" "$CLAUDE_DIR/claude-agentic/routing.md"
write_profile "$CLAUDE_DIR" "$TMP/claude-profile.json"
block_size "$GLOBAL_MD" 2560

# ---------------------------------------------------------------- 6. audits
missing="" unpinned=""
for f in "$CLAUDE_DIR"/agents/*.md; do
  case "$f" in *.bak|*.superseded) continue;; esac
  [ -e "$f" ] || continue
  grep -qE '^effort:' "$f" || missing="$missing $(basename "$f")"
  case "$(basename "$f")" in architect.md) continue;; esac  # may inherit the session on purpose
  grep -qE '^model:' "$f" || unpinned="$unpinned $(basename "$f")"
done
if [ -n "$missing" ]; then
  echo
  echo "WARNING: these agents declare no 'effort:' and inherit the session effort:"
  for m in $missing; do echo "  - $m"; done
  echo "Add 'effort: low' for readers and runners, 'effort: medium' for mechanical work."
fi
if [ -n "$unpinned" ]; then
  echo
  echo "WARNING: these agents declare no 'model:' and inherit the session model:"
  for m in $unpinned; do echo "  - $m"; done
  echo "Pin 'model: haiku|sonnet|opus|fable' to the tier the role needs."
fi
subagent_override=$(jq -r '.env.CLAUDE_CODE_SUBAGENT_MODEL // empty' "$SETTINGS")
if [ -n "$subagent_override" ]; then
  echo
  echo "WARNING: CLAUDE_CODE_SUBAGENT_MODEL=$subagent_override is set. Since Claude Code 2.1.251 it only"
  echo "applies to an agent whose call and definition name no model. Before 2.1.251 (the JetBrains ACP"
  echo "adapter bundles 2.1.219) it outranks every agent's 'model:' and the call's own model, so the"
  echo "FAST/BALANCED/STRONG tiers all run on that one model. Unset it."
fi

if python3 - "$GLOBAL_MD" <<'PY'
import re, sys
t = open(sys.argv[1]).read()
outside = re.sub(r"<!-- claude-agentic:start -->.*?<!-- claude-agentic:end -->", "", t, flags=re.S)
sys.exit(0 if re.search(r"claude-routing:start|# Model routing|# Model allocation by task", outside) else 1)
PY
then
  echo
  echo "WARNING: $GLOBAL_MD still has routing rules outside the managed block."
  echo "They are superseded by the block above — remove them by hand."
fi
}

claude_summary() {
cat <<SUM

Done (Claude Code).
  target          $CLAUDE_DIR
  plan            $PLAN  ($PLAN_LABEL, $PROFILE_NAME profile, fable=$FABLE)
  plan tables     $CLAUDE_DIR/claude-agentic/profile.json
  session model   $SESSION_MODEL ($SESSION_HUMAN), effort $EFFORT
  fallback        $FALLBACK
  EXPERT tier     ai-expert on opus, pinned, at effort $EXPERT_EFFORT;
                  architect on $( [ "$TIER" = pro ] && echo "opus, pinned" || { [ "$FABLE" = yes ] && echo "fable[1m], pinned" || echo "the session model"; } ) at effort $ARCHITECT_EFFORT
  compaction      near $COMPACT_AT tokens on this $((MODEL_WINDOW / 1000))k session (autoCompactWindow $COMPACT,
                  capped at the model's window); context-guard warns from
                  $((COMPACT_AT * 80 / 100)) and holds a prompt back once from $((COMPACT_AT * 120 / 100))
$( [ "$TIER" = max ] && echo "  large context   claude-1m$( [ "$FABLE" = yes ] && echo " [opus|fable]" ) starts one session on opus[1m]$( [ "$FABLE" = yes ] && echo " or fable[1m] (Fable 5.1)" ) that compacts near $ONE_M_AT
                  (the same autoCompactWindow, uncapped on a 1M model)" )
  read guard      an unbounded Read is refused above $READ_LINES lines / $READ_BYTES bytes
  agents          $(ls "$SRC/agents" | grep -v '^superseded$' | sed 's/\.md\(\.tmpl\)\?$//' | paste -sd' ')
  hooks           cap-large-read, project-scaffold (Setup:init), ai-git-guard (global),
                  ai-path-guard + ai-scope-guard (active where .ai/ exists),
                  context-guard (UserPromptSubmit, PreCompact, SessionStart:compact)
  runtime gate    on — budgets from claude-agentic/profile.json, running agents, quota through the statusline
  fable branch    $GATE $( [ "$GATE" = on ] && echo "(Fable agents go to Opus while Fable is rate-limited, unreachable,
                  or the weekly limit is ${CLAUDE_FABLE_GATE_WEEKLY_PCT:-90}% used — checked through the statusline)" || echo "(no Fable on this install)" )
  skills          $(ls "$SRC/skills" | paste -sd' ')

Restart Claude Code, then:
  /config        model and effort match the profile
  /hooks         lists the six hooks, plus runtime-gate on PreToolUse, PostToolUse, SubagentStart, SubagentStop$( [ "$GATE" = on ] && echo " and StopFailure" )
  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report
  /ai-init       in a project, to survey it and build .ai/
  /project-update in a project that already has .ai/ or docs/sdlc/, to pull in these rules
SUM
}

# ======================================================================= Codex
# Two ChatGPT plans, two profiles. Pro (profiles/codex-pro.json) runs the session
# on Sol at high with six agent threads and Astra at xhigh for EXPERT; Plus
# (profiles/codex-plus.json) has a smaller usage window, so the session runs Sol
# at medium, three threads, and Astra at high with xhigh off. The plan is read
# from the ChatGPT login: the JWT in ~/.codex/auth.json carries chatgpt_plan_type.
codex_detect_plan() {
  python3 - "$CODEX_DIR/auth.json" "${HOME:-/nonexistent}/.codex/auth.json" <<'PY'
import base64, json, sys
def claim(tok):
    try:
        body = tok.split(".")[1]
        pad = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        auth = json.loads(pad).get("https://api.openai.com/auth") or {}
        return auth.get("chatgpt_plan_type") or ""
    except Exception:
        return ""
for path in sys.argv[1:]:
    try:
        data = json.load(open(path))
    except (OSError, ValueError):
        continue
    tokens = data.get("tokens") or {}
    for key in ("id_token", "access_token"):
        plan = claim(tokens.get(key) or "")
        if plan:
            print(plan.lower()); sys.exit(0)
print("")
PY
}

codex_render() {
  CODEX_PREV_PLAN=$(jq -r '.plan // empty' "$CODEX_DIR/claude-agentic/profile.json" 2>/dev/null || true)
  # BalancedMax is one routing idea on both runtimes: --plan balanced-max selects
  # the Codex balanced-max profile too, unless --codex-plan says otherwise.
  if [ -z "$CODEX_PLAN" ] && [ "$PLAN" = balanced-max ]; then CODEX_PLAN=balanced-max; fi
  if [ -z "$CODEX_PLAN" ]; then
    detected=$(codex_detect_plan 2>/dev/null || true)
    CODEX_DETECTED="" CODEX_WHY=""
    case "$detected" in
      plus)   CODEX_DETECTED=plus; CODEX_WHY="chatgpt_plan_type";;
      pro)    CODEX_DETECTED=pro;  CODEX_WHY="chatgpt_plan_type";;
      team*|business*|enterprise*|edu*)
              CODEX_DETECTED=pro;  CODEX_WHY="chatgpt_plan_type $detected, uses the pro profile";;
    esac
    if [ -t 0 ]; then
      proposed="${CODEX_PREV_PLAN:-$CODEX_DETECTED}"
      if [ -n "$proposed" ]; then
        why="detected from $CODEX_WHY"
        [ -n "$CODEX_PREV_PLAN" ] && why="recorded by the previous install"
        read -r -p "codex plan: $proposed ($why) — Enter to confirm, or type plus/pro/balanced-max: " CODEX_PLAN
        CODEX_PLAN="${CODEX_PLAN:-$proposed}"
      else
        read -r -p "Could not detect the ChatGPT plan (chatgpt_plan_type='$detected'). Enter plan [plus/pro]: " CODEX_PLAN
      fi
    elif [ -n "$CODEX_DETECTED" ]; then
      CODEX_PLAN=$CODEX_DETECTED; echo "detected codex plan: $CODEX_PLAN ($CODEX_WHY)" >&2
    elif [ -n "$CODEX_PREV_PLAN" ]; then
      CODEX_PLAN=$CODEX_PREV_PLAN; echo "codex plan: $CODEX_PLAN (recorded by the previous install)" >&2
    else
      CODEX_PLAN=pro
      echo "could not detect the ChatGPT plan; using the pro profile — pass --codex-plan plus on Plus" >&2
    fi
  fi
  case "$CODEX_PLAN" in
    plus) CODEX_PLAN_LABEL="Plus";;
    pro)  CODEX_PLAN_LABEL="Pro";;
    balanced-max|balanced_max|balancedmax) CODEX_PLAN=balanced-max; CODEX_PLAN_LABEL="BalancedMax";;
    *) echo "--codex-plan must be plus, pro or balanced-max (got '$CODEX_PLAN')" >&2; exit 2;;
  esac
  CODEX_PROFILE="$SRC/profiles/codex-$CODEX_PLAN.json"
  agentic_profile codex "codex-$CODEX_PLAN" "$CODEX_PLAN" "$CODEX_PLAN_LABEL" no > "$TMP/codex-profile.json"

  CODEX_SESSION_MODEL=$(jq -r .session.model "$CODEX_PROFILE")
  CODEX_SESSION_EFFORT=$(jq -r .session.model_reasoning_effort "$CODEX_PROFILE")
  CODEX_SUBAGENT_MODEL=$(jq -r .agents.default_subagent_model "$CODEX_PROFILE")
  CODEX_SUBAGENT_EFFORT=$(jq -r .agents.default_subagent_reasoning_effort "$CODEX_PROFILE")
  CODEX_MAX_THREADS=$(jq -r .agents.max_concurrent_threads_per_session "$CODEX_PROFILE")
  CODEX_FAST=$(jq -r .tiers.FAST.model "$CODEX_PROFILE")
  CODEX_FAST_EFFORT=$(jq -r .tiers.FAST.effort "$CODEX_PROFILE")
  CODEX_BALANCED=$(jq -r .tiers.BALANCED.model "$CODEX_PROFILE")
  CODEX_BALANCED_EFFORT=$(jq -r .tiers.BALANCED.effort "$CODEX_PROFILE")
  CODEX_STRONG=$(jq -r .tiers.STRONG.model "$CODEX_PROFILE")
  CODEX_STRONG_EFFORT=$(jq -r .tiers.STRONG.effort "$CODEX_PROFILE")
  CODEX_EXPERT=$(jq -r .tiers.EXPERT.model "$CODEX_PROFILE")
  CODEX_EXPERT_EFFORT=$(jq -r .tiers.EXPERT.effort "$CODEX_PROFILE")
  codex_label() { jq -r --arg m "$1" '.labels[$m] // $m' "$CODEX_PROFILE"; }
  # The profile's plan rule names the EXPERT model by placeholder; render() makes
  # one pass, so it is filled in here before the snippet is rendered.
  CODEX_PLAN_RULE=$(jq -r '.plan_rule // empty' "$CODEX_PROFILE")
  CODEX_PLAN_RULE=${CODEX_PLAN_RULE//\{\{EXPERT_MODEL\}\}/$(codex_label "$CODEX_EXPERT")}

  python3 "$SRC/scripts/render-codex-agents.py" --src "$SRC" --out "$TMP/codex-agents" --profile "$CODEX_PROFILE" >/dev/null

  RENDER_CODEX_PLAN="$CODEX_PLAN_LABEL" \
  RENDER_CODEX_PLAN_RULE="$CODEX_PLAN_RULE" \
  RENDER_SESSION_MODEL="$(codex_label "$CODEX_SESSION_MODEL")" \
  RENDER_SESSION_MODEL_ID="$CODEX_SESSION_MODEL" \
  RENDER_SESSION_EFFORT="$CODEX_SESSION_EFFORT" \
  RENDER_SUBAGENT_EFFORT="$CODEX_SUBAGENT_EFFORT" \
  RENDER_FAST_EFFORT="$CODEX_FAST_EFFORT" \
  RENDER_BALANCED_EFFORT="$CODEX_BALANCED_EFFORT" \
  RENDER_STRONG_EFFORT="$CODEX_STRONG_EFFORT" \
  RENDER_FAST_MODEL="$(codex_label "$CODEX_FAST")" \
  RENDER_FAST_MODEL_ID="$CODEX_FAST" \
  RENDER_BALANCED_MODEL="$(codex_label "$CODEX_BALANCED")" \
  RENDER_BALANCED_MODEL_ID="$CODEX_BALANCED" \
  RENDER_STRONG_MODEL="$(codex_label "$CODEX_STRONG")" \
  RENDER_STRONG_MODEL_ID="$CODEX_STRONG" \
  RENDER_EXPERT_MODEL="$(codex_label "$CODEX_EXPERT")" \
  RENDER_EXPERT_MODEL_ID="$CODEX_EXPERT" \
  RENDER_EXPERT_EFFORT="$CODEX_EXPERT_EFFORT" \
  RENDER_MAX_THREADS="$CODEX_MAX_THREADS" \
  RENDER_PLAN_LABEL="ChatGPT $CODEX_PLAN_LABEL" \
  RENDER_READ_LINES="$(jq -r '.env.CLAUDE_READ_MAX_LINES' "$SRC/settings.common.json")" \
    codex_render_files
}

codex_render_files() {
  render_stub global codex "$TMP/AGENTS.block.md"
  render_stub global codex "$TMP/routing.md" routing
}

codex_dry_run() {
  echo "== codex: plan=$CODEX_PLAN ($CODEX_PLAN_LABEL) session $CODEX_SESSION_MODEL at $CODEX_SESSION_EFFORT (dry run, nothing written)"
  echo "== codex: target directory $CODEX_DIR"
  python3 "$SRC/scripts/merge-codex-config.py" "$CODEX_DIR/config.toml" \
          --profile "$CODEX_PROFILE" --dry-run | sed 's/^/== /'
  echo "== AGENTS.md managed block:"
  cat "$TMP/AGENTS.block.md"
  echo "== routing.md (on demand): $CODEX_DIR/claude-agentic/routing.md"
  cat "$TMP/routing.md"
  echo "== profile.json (plan tables): $CODEX_DIR/claude-agentic/profile.json"
  jq . "$TMP/codex-profile.json"
  echo "== would install:"
  echo "   agents:  $(ls "$TMP/codex-agents" | sed 's/\.toml$//' | paste -sd,)"
  echo "   hooks:   $(codex_hook_files | xargs -n1 basename | paste -sd,)"
  echo "   skills:  $(ls "$SRC/skills" | paste -sd,)"
  echo "   config:  ai-git-guard.json (only if absent)"
  echo "   routing: claude-agentic/routing.md"
  echo "   profile: claude-agentic/profile.json"
  echo "== hooks.json entries (merged into $CODEX_DIR/hooks.json):"
  jq . "$SRC/codex/hooks.json"
  echo "== reminder: Codex lists a non-managed hook until you review it in /hooks"
}

# The guard scripts Codex can actually use. cap-large-read.py and fable-gate.py
# are deliberately absent: Codex has no hookable Read tool, and Fable is a
# Claude model. context-guard.py is here because Codex has both compaction
# events and SessionStart, so the handoff, the questions and session.json cross
# unchanged; what does not cross is the transcript-derived snapshot, which is
# built from a Claude transcript and stays Claude-only. The same file serves
# both: it reads its own location to know which runtime it is in.
codex_hook_files() {
  printf '%s\n' \
    "$SRC/hooks/ai-git-guard.sh" \
    "$SRC/hooks/ai-path-guard.sh" \
    "$SRC/hooks/ai-scope-guard.sh" \
    "$SRC/hooks/codex-model-gate.py" \
    "$SRC/hooks/runtime-gate.py" \
    "$SRC/hooks/context-guard.py"
}

codex_apply() {
  mkdir -p "$CODEX_DIR/agents" "$CODEX_DIR/hooks/lib" "$CODEX_DIR/skills"

  # -------------------------------------------------------------- 1. agents
  for f in "$TMP"/codex-agents/*.toml; do
    install_file "$f" "$CODEX_DIR/agents/$(basename "$f")" "$CODEX_DIR"
  done

  # -------------------------------------------------------------- 2. hooks
  local f dst
  while IFS= read -r f; do
    dst="$CODEX_DIR/hooks/$(basename "$f")"
    install_file "$f" "$dst" "$CODEX_DIR"
    chmod +x "$dst"
  done < <(codex_hook_files)
  install_file "$SRC/hooks/lib/ai-hook-common.sh" "$CODEX_DIR/hooks/lib/ai-hook-common.sh" "$CODEX_DIR"
  install_file "$SRC/hooks/ai-path-guard-defaults.json" "$CODEX_DIR/hooks/ai-path-guard-defaults.json" "$CODEX_DIR"
  install_file "$SRC/hooks/ai-git-guard-defaults.json"  "$CODEX_DIR/hooks/ai-git-guard-defaults.json" "$CODEX_DIR"
  if [ ! -e "$CODEX_DIR/hooks/ai-git-guard.json" ]; then
    cp "$SRC/hooks/ai-git-guard-defaults.json" "$CODEX_DIR/hooks/ai-git-guard.json"
    echo "installed: hooks/ai-git-guard.json (edit this one; it is never overwritten)"
  else
    echo "kept: hooks/ai-git-guard.json (your edits are preserved)"
  fi

  # -------------------------------------------------------------- 3. skills
  install_skills "$CODEX_DIR"

  # -------------------------------------------------------------- 4. hooks.json
  local HOOKS="$CODEX_DIR/hooks.json"
  [ -f "$HOOKS" ] || echo '{}' > "$HOOKS"
  cp "$HOOKS" "$HOOKS.bak"
  # codex-model-gate entries from before WP5 and runtime-gate ones from an
  # earlier run are removed first, so the merge below adds exactly one gate per
  # event. Codex runs only hooks the user has reviewed; config.toml keeps each
  # approval as [hooks.state."<file>:<event>:<group>:<index>"] trusted_hash, a
  # hash of the whole entry. An install that already registers
  # codex-model-gate.py keeps that command (the shim execs runtime-gate.py), so
  # an entry that is otherwise unchanged keeps its approval; a changed one
  # (a new matcher, a new event) needs one review in /hooks.
  local GATE_HOOKS="$SRC/codex/hooks.json"
  if jq -e '[.hooks // {} | .[]?[]? | .hooks[]?.command // "" | select(test("/hooks/codex-model-gate\\.py"))] | length > 0' "$HOOKS" >/dev/null 2>&1; then
    GATE_HOOKS="$TMP/codex-hooks.json"
    sed 's|/hooks/runtime-gate\.py|/hooks/codex-model-gate.py|g' "$SRC/codex/hooks.json" > "$GATE_HOOKS"
    echo "kept: codex-model-gate.py as the gate command (it runs runtime-gate.py); review the changed gate entries once in /hooks, or Codex skips them"
  fi
  jq 'if (.hooks | type) == "object" then
      .hooks |= (with_entries(.value |= [ .[]
          | if (.hooks | type) == "array" and (.hooks | length) > 0 then
              .hooks |= map(select((.command // "") | test("/hooks/(codex-model-gate|runtime-gate)\\.py") | not))
              | select(.hooks | length > 0)
            else . end ])
        | with_entries(select(.value | length > 0)))
    else . end' "$HOOKS" > "$HOOKS.tmp" && mv "$HOOKS.tmp" "$HOOKS"
  jq -s '
    .[0] as $cur
    | (.[1].hooks // {}) as $new
    | reduce ($new | to_entries[]) as $event
        ($cur;
          .hooks[$event.key] = (
            (.hooks[$event.key] // [])
            + ( $event.value
                | map( . as $entry
                       | select( ($entry.hooks // []) | map(.command)
                                 | any( . as $c | $cur.hooks[$event.key] // []
                                        | map(.hooks // [] | map(.command)) | flatten
                                        | index($c) ) | not ) ) )
          )
        )
  ' "$HOOKS" "$GATE_HOOKS" > "$HOOKS.tmp" && mv "$HOOKS.tmp" "$HOOKS"
  echo "merged: hooks.json (backup in hooks.json.bak)"

  # -------------------------------------------------------------- 5. config.toml
  python3 "$SRC/scripts/merge-codex-config.py" "$CODEX_DIR/config.toml" --profile "$CODEX_PROFILE"

  # -------------------------------------------------------------- 6. AGENTS.md
  managed_block "$CODEX_DIR/AGENTS.md" "$TMP/AGENTS.block.md" "AGENTS.md"
  mkdir -p "$CODEX_DIR/claude-agentic"
  install_file "$TMP/routing.md" "$CODEX_DIR/claude-agentic/routing.md" "$CODEX_DIR"
  write_profile "$CODEX_DIR" "$TMP/codex-profile.json"
  block_size "$CODEX_DIR/AGENTS.md" 2560
  codex_doc_advisory "$CODEX_DIR/AGENTS.md"
}

codex_summary() {
cat <<SUM

Done (Codex).
  target          $CODEX_DIR
  plan            $CODEX_PLAN  ($CODEX_PLAN_LABEL)
  session model   $CODEX_SESSION_MODEL at effort $CODEX_SESSION_EFFORT
  subagent default $CODEX_SUBAGENT_MODEL at $CODEX_SUBAGENT_EFFORT, at most $CODEX_MAX_THREADS threads at once
  FAST tier       $CODEX_FAST at $CODEX_FAST_EFFORT (ai-indexer, Explore, log-reader, ai-tester)
  BALANCED tier   $CODEX_BALANCED at $CODEX_BALANCED_EFFORT (ai-discovery at low, ai-context, ai-risk, ai-planner, ai-release, ai-implementer,
                  ai-reviewer-balanced for the T2 review)
  STRONG tier     $CODEX_STRONG at $CODEX_STRONG_EFFORT (ai-reviewer, ai-security, architect, ai-risk-strong, ai-planner-strong,
                  ai-expert-strong: the gate's stand-in for ai-expert)
  EXPERT tier     $CODEX_EXPERT at $CODEX_EXPERT_EFFORT (ai-expert)
  runtime gate    sends EXPERT work to $CODEX_STRONG while $CODEX_EXPERT is rate-limited or
                  unavailable, explains launches past the plan's budgets, reads the quota
                  from the session rollouts; 'runtime-gate.py status' / 'quota' show it
  agents          $(ls "$TMP/codex-agents" | sed 's/\.toml$//' | paste -sd' ')
  hooks           ai-git-guard (global), ai-path-guard + ai-scope-guard (active where .ai/ exists),
                  runtime-gate. No cap-large-read: Codex has no hookable Read tool.
  skills          $(ls "$SRC/skills" | paste -sd' ')

Restart Codex, then:
  /hooks         review and trust the four hooks — until you do, Codex skips them
  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report
  /ai-init       in a project, to survey it and build .ai/

Your previous default model was replaced. config.toml.bak holds the old one.
SUM
}

# ======================================================================= run
if [ "$DO_CLAUDE" = 1 ]; then claude_render; fi
if [ "$DO_CODEX" = 1 ]; then codex_render; fi

if [ "$DRY" = 1 ]; then
  if [ "$DO_CLAUDE" = 1 ]; then claude_dry_run; fi
  if [ "$DO_CODEX" = 1 ]; then codex_dry_run; fi
  exit 0
fi

if [ "$DO_CLAUDE" = 1 ]; then claude_apply; fi
if [ "$DO_CODEX" = 1 ]; then codex_apply; fi
if [ "$DO_CLAUDE" = 1 ]; then claude_summary; fi
if [ "$DO_CODEX" = 1 ]; then codex_summary; fi
exit 0
