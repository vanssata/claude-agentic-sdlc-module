#!/usr/bin/env bash
# claude-agentic installer.
#   ./install.sh [--plan pro|max] [--fable auto|yes|no] [--dry-run]
# --plan   defaults to auto-detect from ~/.claude.json (organizationType); prompts if unknown.
# --fable  auto = yes on max, no on pro. On max the session runs Opus 5 [1m] either way;
#          yes pins Fable 5.1 [1m] on the architect agent alone.
# --dry-run prints everything that would be written, and writes nothing.
#
# Installs into ~/.claude/: model, effort and context settings for the detected
# plan; the ai-* pipeline agents plus architect, Explore and log-reader; five
# hooks; eight skills; and one managed block in ~/.claude/CLAUDE.md.
#
# pro (and Team Standard, which shares its models): session model `opusplan` —
# Opus in plan mode, Sonnet when executing — and the EXPERT tier pinned to opus.
# max: session model Opus 5 [1m], ai-expert inherits it, architect alone on Fable.
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
    claude_team*|*team*) PLAN=pro; echo "detected plan: team ($org) — uses the pro profile (same models and limits)";;
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
    fable*) echo "Fable 5.1 [1m]";; opusplan) echo "Opus 5 in plan mode, Sonnet 5 when executing (opusplan)";;
    "opus[1m]") echo "Opus 5 [1m]";; opus*) echo "Opus 5";;
    sonnet*) echo "Sonnet 5";; haiku*) echo "Haiku 4.5";; *) echo "$1";;
  esac
}
SESSION_HUMAN=$(pretty "$SESSION_MODEL")
FALLBACK_HUMAN=$(jq -r '.fallbackModel | if type=="array" then .[] else . end' "$TMP/settings.snippet.json" \
                 | while read -r m; do pretty "$m"; done | paste -sd'|' | sed 's/|/, then /g')

# The EXPERT tier is the session model: ai-expert and architect omit `model:` on
# purpose, so a Fable outage falls back exactly as the session does.
if [ "$PLAN" = pro ]; then
  PLAN_LABEL="Pro"
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
  PLAN_LABEL="Max"
  EXPERT_EFFORT="high"
  # The session runs Opus 5 [1m]; ai-expert escalates from it by inheriting it.
  EXPERT_MODEL_LINE="# model: intentionally omitted — inherits the session model (Opus 5 [1m]), so the session's fallback chain applies here too"
  if [ "$FABLE" = yes ]; then
    ARCHITECT_MODEL_LINE="model: fable[1m]"
    ARCHITECT_EFFORT="xhigh"
    EXPERT_ROW="omit \`model:\` — inherits the session (Opus 5 [1m]) / \`high\`; \`architect\` alone pins \`fable[1m]\` / \`xhigh\`"
    PLAN_SPECIFIC="- Session model is Opus 5 [1m]; \`ai-expert\` escalates from it by inheriting it. Fable 5.1 [1m] is reserved for \`architect\` (pinned \`model: fable[1m]\`, \`xhigh\`) — never for the session, a reader, a reviewer or \`ai-expert\`. \`max\` stays off."
  else
    ARCHITECT_MODEL_LINE="# model: intentionally omitted — inherits the session model (Opus 5 [1m], Fable disabled in this install)"
    ARCHITECT_EFFORT="high"
    EXPERT_ROW="omit \`model:\` — inherits the session (Opus 5 [1m]) / \`high\`"
    PLAN_SPECIFIC="- Session model is Opus 5 [1m]; Fable is disabled in this install (\`--fable no\`). Do not request \`model: fable\` anywhere. \`xhigh\`/\`max\` stay off. Never pin \`model: opus\` for the thinking tier — omit \`model:\` so the fallback comes free."
  fi
  EFFORT_RULE="Raise to \`high\` for architecture, root-cause analysis and adversarial verification, and say that you are raising it; readers stay at \`low\`."
fi

render() {  # render <src> <dst>
  PLAN_LABEL="$PLAN_LABEL" SESSION_HUMAN="$SESSION_HUMAN" FALLBACK_HUMAN="$FALLBACK_HUMAN" \
  EFFORT="$EFFORT" COMPACT="$COMPACT" READ_LINES="$READ_LINES" \
  PLAN_SPECIFIC="$PLAN_SPECIFIC" EFFORT_RULE="$EFFORT_RULE" \
  EXPERT_EFFORT="$EXPERT_EFFORT" EXPERT_MODEL_LINE="$EXPERT_MODEL_LINE" EXPERT_ROW="$EXPERT_ROW" \
  ARCHITECT_MODEL_LINE="$ARCHITECT_MODEL_LINE" ARCHITECT_EFFORT="$ARCHITECT_EFFORT" \
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
    "{{EXPERT_MODEL_LINE}}": os.environ["EXPERT_MODEL_LINE"],
    "{{EXPERT_ROW}}": os.environ["EXPERT_ROW"],
    "{{ARCHITECT_MODEL_LINE}}": os.environ["ARCHITECT_MODEL_LINE"],
    "{{ARCHITECT_EFFORT}}": os.environ["ARCHITECT_EFFORT"],
}.items():
    text = text.replace(key, value)
assert "{{" not in text, "unrendered placeholder in %s" % src
open(dst, "w").write(text)
PY
}

render "$SRC/agents/ai-expert.md.tmpl" "$TMP/ai-expert.md"
render "$SRC/agents/architect.md.tmpl" "$TMP/architect.md"
render "$SRC/CLAUDE.snippet.md" "$TMP/CLAUDE.block.md"

if [ "$DRY" = 1 ]; then
  echo "== plan=$PLAN fable=$FABLE (dry run, nothing written)"
  echo "== settings snippet (merged into $CLAUDE_DIR/settings.json):"
  jq . "$TMP/settings.snippet.json"
  echo "== agents/ai-expert.md (rendered head):"
  sed -n '1,10p' "$TMP/ai-expert.md"
  echo "== agents/architect.md (rendered head):"
  sed -n '1,8p' "$TMP/architect.md"
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
install_file "$TMP/architect.md" "$CLAUDE_DIR/agents/architect.md"

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
missing=""
for f in "$CLAUDE_DIR"/agents/*.md; do
  case "$f" in *.bak|*.superseded) continue;; esac
  [ -e "$f" ] || continue
  grep -qE '^effort:' "$f" || missing="$missing $(basename "$f")"
done
if [ -n "$missing" ]; then
  echo
  echo "WARNING: these agents declare no 'effort:' and inherit the session effort:"
  for m in $missing; do echo "  - $m"; done
  echo "Add 'effort: low' for readers and runners, 'effort: medium' for mechanical work."
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
  EXPERT tier     ai-expert on $( [ "$PLAN" = pro ] && echo "opus, pinned" || echo "the session model" ) at effort $EXPERT_EFFORT;
                  architect on $( [ "$PLAN" = pro ] && echo "opus, pinned" || { [ "$FABLE" = yes ] && echo "fable[1m], pinned" || echo "the session model"; } ) at effort $ARCHITECT_EFFORT
  compaction      $COMPACT tokens
  read guard      an unbounded Read is refused above $READ_LINES lines / $READ_BYTES bytes
  agents          $(ls "$SRC/agents" | grep -v '^superseded$' | sed 's/\.md\(\.tmpl\)\?$//' | paste -sd' ')
  hooks           cap-large-read, project-scaffold (Setup:init), ai-git-guard (global),
                  ai-path-guard + ai-scope-guard (active where .ai/ exists)
  skills          $(ls "$SRC/skills" | paste -sd' ')

Restart Claude Code, then:
  /config        model and effort match the profile
  /hooks         lists the five hooks
  /skills        lists ai-init, ai-audit, ai-task, ai-status, project-init, sdlc-*
  /ai-init       in a project, to survey it and build .ai/
SUM
