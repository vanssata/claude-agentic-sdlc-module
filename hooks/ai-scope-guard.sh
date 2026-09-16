#!/usr/bin/env bash
# claude-agentic: task-scope guard (PreToolUse on Edit|Write|NotebookEdit, and on
# apply_patch in Codex — one patch is checked file by file, so a patch that
# touches one file outside the step is refused whole).
#
# During the IMPLEMENTATION stage of an /ai-task run, the approved plan names the
# files each step may touch. This guard makes that boundary mechanical: an edit
# outside allowed_files is refused with the literal token SCOPE_CHANGE_REQUIRED,
# which is the signal the manager watches for. Scope grows by amending the plan,
# never by an implementer quietly editing one more file.
#
# Inert unless .ai/state/current.json exists and current_stage == "implementation".
set -uo pipefail

HOOK_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/ai-hook-common.sh
. "$HOOK_DIR/lib/ai-hook-common.sh"

read_payload

case "$AI_TOOL" in
    Edit|Write|MultiEdit|NotebookEdit) ;;
    *) allow ;;
esac

AI_ROOT=$(find_ai_root "$AI_CWD") || allow
STATE="$AI_ROOT/.ai/state/current.json"
[ -f "$STATE" ] || allow

STAGE=$(jq -r '.current_stage // empty' "$STATE" 2>/dev/null) || allow
[ "$STAGE" = "implementation" ] || allow

STEP_ID=$(jq -r '.approved_plan.current_step_id // empty' "$STATE" 2>/dev/null)
[ -n "$STEP_ID" ] || allow          # no step selected yet: nothing to enforce

STEP=$(jq -c --arg id "$STEP_ID" '.approved_plan.steps[]? | select(.step_id == $id)' "$STATE" 2>/dev/null)
[ -n "$STEP" ] || allow             # state integrity problem; /ai-task flags it on resume

ALLOWED=$(printf '%s' "$STEP" | jq -r '.allowed_files[]?')
FORBIDDEN=$(printf '%s' "$STEP" | jq -r '.forbidden_files[]?')
REASON=$(printf '%s' "$STEP" | jq -r '.forbidden_reason // "not part of this step"')
TASK_ID=$(jq -r '.task_id // "?"' "$STATE" 2>/dev/null)

# match_glob <relative-path> <patterns> — shell-glob match (fnmatch semantics),
# so a plan can say "src/Payment/*.php" or "tests/**" the way a human would.
match_glob() {
    AI_SUBJECT="$1" AI_PATTERNS="$2" python3 -c '
import fnmatch, os, sys
subject = os.environ["AI_SUBJECT"]
patterns = [p for p in os.environ["AI_PATTERNS"].splitlines() if p.strip()]
for pattern in patterns:
    if fnmatch.fnmatch(subject, pattern) or fnmatch.fnmatch(subject, pattern.rstrip("/") + "/*"):
        print(pattern)
        sys.exit(0)
sys.exit(1)
' 2>/dev/null
}

while IFS= read -r f; do
    [ -n "$f" ] || continue
    abs=$(abs_path "$f")
    rel="${abs#"$AI_ROOT"/}"

    if [ -n "$FORBIDDEN" ] && hit=$(match_glob "$rel" "$FORBIDDEN"); then
        deny "$rel is explicitly forbidden for step $STEP_ID of task $TASK_ID (matched: $hit).
Reason recorded in the plan: $REASON

Do not edit it. If the step genuinely cannot be completed without this file, stop
and report SCOPE_CHANGE_REQUIRED so the plan is amended and re-approved."
    fi

    if [ -n "$ALLOWED" ] && ! match_glob "$rel" "$ALLOWED" >/dev/null; then
        deny "SCOPE_CHANGE_REQUIRED — $rel is outside the approved scope of step $STEP_ID (task $TASK_ID).

Allowed for this step:
$(printf '  - %s\n' $ALLOWED)

Stop implementing, report SCOPE_CHANGE_REQUIRED with the reason this file is
needed, and let the planner amend the step. Widening scope silently is what this
guard exists to prevent. See .ai/policies/safety.md."
    fi
done < <(target_paths)

allow
