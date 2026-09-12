#!/usr/bin/env bash
# claude-agentic installer.
#   ./install.sh [--plan pro|max] [--fable auto|yes|no] [--dry-run]
# --plan   defaults to auto-detect from ~/.claude.json (organizationType); prompts if unknown.
# --fable  auto = yes on max, no on pro. Picks the EXPERT tier: Fable 5.1 at xhigh, or Opus 5.
# --dry-run prints everything that would be written, and writes nothing.
#
# Installs into ~/.claude/: model, effort and context settings for the detected
# plan (the session runs Opus 5 [1m] at medium on Max and Sonnet on Pro; agents
# default to Sonnet); the ai-* pipeline agents plus
# architect, Explore and log-reader; five hooks, plus fable-gate on a Fable
# install; nine skills; and one managed block in ~/.claude/CLAUDE.md.
#
# This plugin supersedes claude-routing. On the first run it migrates that
# plugin's managed block into this one's, so the two never coexist.
#
# Idempotent: re-running updates in place, backs up what it replaces to *.bak,
# and never duplicates a hook entry or a managed block.
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
SRC="$(cd "$(dirname "$0")" && pwd)"
PLAN="" FABLE="auto" DRY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --plan)  PLAN="${2:?missing value for --plan}"; shift 2;;
    --plan=*) PLAN="${1#*=}"; shift;;
    --fable) FABLE="${2:?missing value for --fable}"; shift 2;;
    --fable=*) FABLE="${1#*=}"; shift;;
    --dry-run) DRY=1; shift;;
    -h|--help) sed -n '2,17p' "$0"; exit 0;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
done

command -v jq >/dev/null 2>&1 || { echo "jq is required (apt install jq)" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }

# ---------------------------------------------------------------- plan detection
if [ -z "$PLAN" ]; then
  org=$(jq -r '.oauthAccount.organizationType // .organizationType // empty' "$HOME/.claude.json" 2>/dev/null || true)
  case "$org" in
    claude_max*|*max*) PLAN=max; echo "detected plan: max ($org)";;
    claude_pro*|*pro*) PLAN=pro; echo "detected plan: pro ($org)";;
    *)
      if [ -t 0 ]; then
        read -r -p "Could not detect plan (organizationType='$org'). Enter plan [pro/max]: " PLAN
      else
        echo "Could not detect plan; pass --plan pro|max" >&2; exit 1
      fi;;
  esac
fi
case "$PLAN" in pro|max) ;; *) echo "--plan must be pro or max (got '$PLAN')" >&2; exit 2;; esac
case "$FABLE" in
  auto) [ "$PLAN" = max ] && FABLE=yes || FABLE=no;;
  yes|no) ;;
  *) echo "--fable must be auto|yes|no" >&2; exit 2;;
esac
if [ "$PLAN" = pro ] && [ "$FABLE" = yes ]; then
  echo "Fable is not available on the pro plan; using --fable no" >&2; FABLE=no
fi

# ---------------------------------------------------------------- render settings
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
PROFILE="$SRC/profiles/$PLAN.json"
if [ "$PLAN" = max ] && [ "$FABLE" = no ]; then
  jq '.availableModels = (.availableModels | map(select(startswith("fable") | not)))
      | del(.modelSettings["claude-fable-5-1"])' "$PROFILE" > "$TMP/profile.json"
else
  cp "$PROFILE" "$TMP/profile.json"
fi
jq -s '.[0] * .[1]' "$SRC/settings.common.json" "$TMP/profile.json" > "$TMP/settings.snippet.json"

SESSION_MODEL=$(jq -r .model "$TMP/settings.snippet.json")
FALLBACK=$(jq -r '.fallbackModel | if type=="array" then join(", then ") else . end' "$TMP/settings.snippet.json")
EFFORT=$(jq -r .effortLevel "$TMP/settings.snippet.json")
COMPACT=$(jq -r .autoCompactWindow "$TMP/settings.snippet.json")
READ_LINES=$(jq -r '.env.CLAUDE_READ_MAX_LINES' "$TMP/settings.snippet.json")
READ_BYTES=$(jq -r '.env.CLAUDE_READ_MAX_BYTES' "$TMP/settings.snippet.json")

pretty() {  # model id -> human name
  case "$1" in
    "fable[1m]") echo "Fable 5.1 [1m]";; fable*) echo "Fable 5.1";;
    "opus[1m]") echo "Opus 5 [1m]";; opus*) echo "Opus 5";;
    sonnet*) echo "Sonnet 5";; haiku*) echo "Haiku 4.5";; *) echo "$1";;
  esac
}
SESSION_HUMAN=$(pretty "$SESSION_MODEL")
FALLBACK_HUMAN=$(jq -r '.fallbackModel | if type=="array" then .[] else . end' "$TMP/settings.snippet.json" \
                 | while read -r m; do pretty "$m"; done | paste -sd'|' | sed 's/|/, then /g')

# Agents default to Sonnet (CLAUDE_CODE_SUBAGENT_MODEL), so nothing expensive may be inherited: ai-expert pins
# the EXPERT model (rendered here) and architect pins opus. fallbackModel applies
# to pinned subagents too, so a Fable outage still falls back to Opus.
if [ "$PLAN" = pro ]; then
  PLAN_LABEL="Pro"
  EXPERT_MODEL="opus"
  EXPERT_EFFORT="high"
  PLAN_SPECIFIC="- Fable is off this plan; never request it (\`model: fable\`, \`fable[1m]\`) anywhere. Opus 5 is the top tier and serves both STRONG and EXPERT; \`ai-expert\` differs from STRONG in its brief, not its model. \`xhigh\`/\`max\` are not supported — treat them as unavailable."
  EFFORT_RULE="Raise to \`high\` only for architecture, root-cause analysis and adversarial verification, and say that you are raising it."
else
  PLAN_LABEL="Max"
  if [ "$FABLE" = yes ]; then
    EXPERT_MODEL="fable"
    EXPERT_EFFORT="xhigh"
    PLAN_SPECIFIC="- \`xhigh\` is allowed only for \`ai-expert\` and verify/judge stages on Fable; \`max\` stays off. Readers never go above \`low\`.
- \`fable-gate\` checks Fable at run time. \`fallbackModel\` covers an overload; after a rate-limit or model-not-found failure, and while the weekly limit is ${CLAUDE_FABLE_GATE_WEEKLY_PCT:-90}% or more used, the gate sends every \`model: fable\` agent to Opus until the reset, and says so in the agent's context. If a Fable agent still returns such an error, re-run the same brief once with \`model: opus\` — an availability switch, not a downgrade. \`~/.claude/hooks/fable-gate.py status\` shows the gate; \`clear\` re-enables Fable early."
  else
    EXPERT_MODEL="opus"
    EXPERT_EFFORT="high"
    PLAN_SPECIFIC="- Fable is disabled in this install (\`--fable no\`): Opus 5 serves both STRONG and EXPERT. Do not request \`model: fable\` anywhere. \`xhigh\`/\`max\` stay off."
  fi
  EFFORT_RULE="Raise to \`high\` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; above \`high\` only per the plan rule above."
fi
EXPERT_HUMAN=$(pretty "$EXPERT_MODEL")

# The Fable gate exists only where Fable does: its hooks are merged into the
# snippet on a Fable install, and stripped from settings.json on any other.
if [ "$EXPERT_MODEL" = fable ]; then
  GATE=on
  jq -s '.[0] as $base | reduce (.[1].hooks | to_entries[]) as $e
           ($base; .hooks[$e.key] = ((.hooks[$e.key] // []) + $e.value))' \
     "$TMP/settings.snippet.json" "$SRC/settings.fable.json" > "$TMP/snippet.gate.json"
  mv "$TMP/snippet.gate.json" "$TMP/settings.snippet.json"
else
  GATE=off
fi

render() {  # render <src> <dst>
  PLAN_LABEL="$PLAN_LABEL" SESSION_HUMAN="$SESSION_HUMAN" FALLBACK_HUMAN="$FALLBACK_HUMAN" \
  EFFORT="$EFFORT" COMPACT="$COMPACT" READ_LINES="$READ_LINES" \
  PLAN_SPECIFIC="$PLAN_SPECIFIC" EFFORT_RULE="$EFFORT_RULE" \
  EXPERT_EFFORT="$EXPERT_EFFORT" EXPERT_MODEL="$EXPERT_MODEL" EXPERT_HUMAN="$EXPERT_HUMAN" \
  python3 - "$1" "$2" <<'PY'
import os, sys
src, dst = sys.argv[1], sys.argv[2]
text = open(src).read()
for key, value in {
    "{{PLAN}}": os.environ["PLAN_LABEL"],
    "{{SESSION_MODEL}}": os.environ["SESSION_HUMAN"],
    "{{FALLBACK_MODEL}}": os.environ["FALLBACK_HUMAN"],
    "{{DEFAULT_EFFORT}}": os.environ["EFFORT"],
    "{{COMPACT_WINDOW}}": "{:,}".format(int(os.environ["COMPACT"])).replace(",", " "),
    "{{READ_LINES}}": os.environ["READ_LINES"],
    "{{PLAN_SPECIFIC_ROUTING}}": os.environ["PLAN_SPECIFIC"],
    "{{EFFORT_RULE}}": os.environ["EFFORT_RULE"],
    "{{EXPERT_EFFORT}}": os.environ["EXPERT_EFFORT"],
    "{{EXPERT_MODEL}}": os.environ["EXPERT_MODEL"],
    "{{EXPERT_MODEL_HUMAN}}": os.environ["EXPERT_HUMAN"],
}.items():
    text = text.replace(key, value)
assert "{{" not in text, "unrendered placeholder in %s" % src
open(dst, "w").write(text)
PY
}

render "$SRC/agents/ai-expert.md.tmpl" "$TMP/ai-expert.md"
render "$SRC/CLAUDE.snippet.md" "$TMP/CLAUDE.block.md"

# Only the statusline receives the account's rate_limits, so the gate's weekly
# check rides on it: on a Fable install the statusline command is wrapped as
#   "$HOME/.claude/hooks/fable-gate.py" statusline --then '<your command>'
# (or set to the bare check when there was none), and unwrapped to exactly the
# original command on any other install.
statusline_gate() {  # statusline_gate <settings.json> <on|off> <apply|dry>
  python3 - "$@" <<'PY'
import json, os, shlex, sys
path, gate, mode = sys.argv[1:4]
PREFIX = '"$HOME/.claude/hooks/fable-gate.py" statusline'
try:
    settings = json.load(open(path)) if os.path.exists(path) else {}
except ValueError:
    print("statusline: settings.json is not valid JSON; left alone"); sys.exit(0)
line = settings.get("statusLine")
cmd = line.get("command", "") if isinstance(line, dict) else ""
ours = isinstance(cmd, str) and cmd.startswith(PREFIX)
action = None
if gate == "on":
    if ours:
        print("statusline: already checks the Fable weekly limit"); sys.exit(0)
    if line is None:
        settings["statusLine"] = {"type": "command", "command": PREFIX}
        action = "added a silent statusline that checks the Fable weekly limit"
    elif isinstance(line, dict) and line.get("type") == "command" and cmd.strip():
        line["command"] = f"{PREFIX} --then {shlex.quote(cmd)}"
        action = "wrapped your statusline command with the Fable weekly-limit check (its output is unchanged)"
    else:
        print("statusline: not a command statusline; the weekly-limit check is not wired"); sys.exit(0)
else:
    if not ours:
        sys.exit(0)
    rest = cmd[len(PREFIX):].strip()
    if rest.startswith("--then"):
        parts = shlex.split(rest)
        line["command"] = parts[1] if len(parts) > 1 else ""
        action = "restored your original statusline command (no Fable on this install)"
    else:
        del settings["statusLine"]
        action = "removed the Fable weekly-limit statusline (no Fable on this install)"
if mode == "dry":
    print("statusline: would have " + action); sys.exit(0)
tmp = path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(settings, fh, indent=2); fh.write("\n")
os.replace(tmp, path)
print("statusline: " + action)
PY
}

if [ "$DRY" = 1 ]; then
  echo "== plan=$PLAN fable=$FABLE fable-gate=$GATE (dry run, nothing written)"
  statusline_gate "$CLAUDE_DIR/settings.json" "$GATE" dry | sed 's/^/== /'
  echo "== settings snippet (merged into $CLAUDE_DIR/settings.json):"
  jq . "$TMP/settings.snippet.json"
  echo "== agents/ai-expert.md (rendered head):"
  sed -n '1,10p' "$TMP/ai-expert.md"
  echo "== CLAUDE.md managed block:"
  cat "$TMP/CLAUDE.block.md"
  echo "== would install:"
  echo "   agents:  $(ls "$SRC/agents" | grep -v '^superseded$' | sed 's/\.md\(\.tmpl\)\?$//' | paste -sd,)"
  echo "   hooks:   $(ls "$SRC/hooks" | paste -sd,)"
  echo "   skills:  $(ls "$SRC/skills" | paste -sd,)"
  echo "   config:  ai-git-guard.json (only if absent)"
  echo "== would migrate: the claude-routing managed block, if present, into this one"
  exit 0
fi

mkdir -p "$CLAUDE_DIR/agents" "$CLAUDE_DIR/hooks/lib" "$CLAUDE_DIR/skills"

install_file() {  # install_file <src> <dst> — back up on a real change, then copy
  local src="$1" dst="$2"
  if [ -e "$dst" ] && ! cmp -s "$src" "$dst"; then
    cp "$dst" "$dst.bak"
    echo "backup: ${dst#"$CLAUDE_DIR"/} -> $(basename "$dst").bak"
  fi
  cp "$src" "$dst"
  echo "installed: ${dst#"$CLAUDE_DIR"/}"
}

# ---------------------------------------------------------------- 1. agents
for f in "$SRC"/agents/*.md; do
  [ -e "$f" ] || continue
  install_file "$f" "$CLAUDE_DIR/agents/$(basename "$f")"
done
install_file "$TMP/ai-expert.md" "$CLAUDE_DIR/agents/ai-expert.md"

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

# ---------------------------------------------------------------- 3. skills
# A backup must not land inside skills/: Claude Code loads every directory there
# as a skill, so a "<name>.bak" copy would show up in /skills as a second,
# stale command. Backups go to a sibling directory instead.
SKILL_BACKUPS="$CLAUDE_DIR/backups/skills"
for d in "$SRC"/skills/*/; do
  name=$(basename "$d")
  dst="$CLAUDE_DIR/skills/$name"
  if [ -d "$dst" ] && ! diff -rq "$d" "$dst" >/dev/null 2>&1; then
    mkdir -p "$SKILL_BACKUPS"
    rm -rf "$SKILL_BACKUPS/$name"; cp -r "$dst" "$SKILL_BACKUPS/$name"
    echo "backup: skills/$name -> backups/skills/$name"
  fi
  rm -rf "$dst"; cp -r "$d" "$dst"
  echo "installed: skills/$name"
done

# Clean up backups a previous version of this installer left inside skills/,
# where they were being loaded as duplicate skills.
for stale in "$CLAUDE_DIR"/skills/*.bak; do
  [ -d "$stale" ] || continue
  mkdir -p "$SKILL_BACKUPS"
  rm -rf "$SKILL_BACKUPS/$(basename "${stale%.bak}")-old"
  mv "$stale" "$SKILL_BACKUPS/$(basename "${stale%.bak}")-old"
  echo "moved: skills/$(basename "$stale") -> backups/skills/ (it was loading as a duplicate skill)"
done
chmod +x "$CLAUDE_DIR/skills/ai-init/scaffold-ai.sh" "$CLAUDE_DIR/skills/ai-task/state.py"

# ---------------------------------------------------------------- 4. settings.json
SETTINGS="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS" ]; then cp "$SETTINGS" "$SETTINGS.bak"; else echo '{}' > "$SETTINGS"; fi
# jq's * replaces arrays wholesale (wanted for availableModels/fallbackModel), so
# merge everything but .hooks first, then append our hook entries only when no
# existing entry under the same event already runs the same command.
jq -s '
  (.[1] | del(.hooks)) as $snippet
  | (.[1].hooks // {}) as $newhooks
  | (.[0] * $snippet) as $merged
  | reduce ($newhooks | to_entries[]) as $event
      ($merged;
        .hooks[$event.key] = (
          (.hooks[$event.key] // [])
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

# No Fable on this install: drop the gate's entries a previous Fable install left,
# and an event list only when the gate was all it held. Other hooks stay.
if [ "$GATE" = off ]; then
  before=$(jq -c '.hooks // {}' "$SETTINGS")
  jq 'if (.hooks | type) == "object" then
        .hooks |= with_entries(
          . as $e
          | ($e.value | map(select(((.hooks // []) | map(.command // "") | any(test("fable-gate"))) | not))) as $kept
          | if ($kept | length) == ($e.value | length) then $e
            elif ($kept | length) == 0 then empty
            else $e | .value = $kept end)
      else . end' "$SETTINGS" > "$SETTINGS.tmp" && mv "$SETTINGS.tmp" "$SETTINGS"
  [ "$before" != "$(jq -c '.hooks // {}' "$SETTINGS")" ] && echo "removed: fable-gate hooks (no Fable on this install)"
fi
statusline_gate "$SETTINGS" "$GATE" apply

# ---------------------------------------------------------------- 5. CLAUDE.md block
GLOBAL_MD="$CLAUDE_DIR/CLAUDE.md"
touch "$GLOBAL_MD"
cp "$GLOBAL_MD" "$GLOBAL_MD.bak"
BLOCK="$TMP/CLAUDE.block.md" python3 - "$GLOBAL_MD" <<'PY'
import os, re, sys
path = sys.argv[1]
block = open(os.environ["BLOCK"]).read().strip("\n")
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
print("CLAUDE.md: %s%s (backup in CLAUDE.md.bak)"
      % (action, " + " + " + ".join(notes) if notes else ""))
PY

# ---------------------------------------------------------------- 6. audits
missing="" unpinned=""
for f in "$CLAUDE_DIR"/agents/*.md; do
  case "$f" in *.bak|*.superseded) continue;; esac
  [ -e "$f" ] || continue
  grep -qE '^effort:' "$f" || missing="$missing $(basename "$f")"
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
  echo "WARNING: these agents declare no 'model:' and resolve to CLAUDE_CODE_SUBAGENT_MODEL (sonnet):"
  for m in $unpinned; do echo "  - $m"; done
  echo "Pin 'model: haiku|sonnet|opus|fable' to the tier the role needs."
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

# ---------------------------------------------------------------- 7. summary
cat <<SUM

Done.
  plan            $PLAN  (fable=$FABLE)
  session model   $SESSION_MODEL ($SESSION_HUMAN), effort $EFFORT
  fallback        $FALLBACK
  STRONG tier     opus at effort high (ai-reviewer, ai-security, architect)
  EXPERT tier     $EXPERT_MODEL ($EXPERT_HUMAN) at effort $EXPERT_EFFORT (ai-expert)
  compaction      $COMPACT tokens
  read guard      an unbounded Read is refused above $READ_LINES lines / $READ_BYTES bytes
  agents          $(ls "$SRC/agents" | grep -v '^superseded$' | sed 's/\.md\(\.tmpl\)\?$//' | paste -sd' ')
  hooks           cap-large-read, project-scaffold (Setup:init), ai-git-guard (global),
                  ai-path-guard + ai-scope-guard (active where .ai/ exists)
  fable gate      $GATE $( [ "$GATE" = on ] && echo "(Fable agents go to Opus while Fable is rate-limited, unreachable,
                  or the weekly limit is ${CLAUDE_FABLE_GATE_WEEKLY_PCT:-90}% used — checked through the statusline)" || echo "(no Fable on this install)" )
  skills          $(ls "$SRC/skills" | paste -sd' ')

Restart Claude Code, then:
  /config        model and effort match the profile
  /hooks         lists the five hooks$( [ "$GATE" = on ] && echo ", plus fable-gate on PreToolUse, PostToolUse and StopFailure" )
  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*, usage-report
  /ai-init       in a project, to survey it and build .ai/
SUM
