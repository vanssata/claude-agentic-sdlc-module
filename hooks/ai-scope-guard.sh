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

HOOK_SRC="${BASH_SOURCE[0]}"
case "$HOOK_SRC" in */*) HOOK_SRC="${HOOK_SRC%/*}" ;; *) HOOK_SRC=. ;; esac
HOOK_DIR="$(cd "${HOOK_SRC:-/}" && pwd)"
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

# Everything this guard needs out of the state file, in one jq call: the guard
# runs on every write, and each process costs milliseconds. Each list value is
# tagged with its list and split on newlines, the way `jq -r '.allowed_files[]?'`
# printed them; the reason comes last, as the remainder of the output, so a
# multi-line reason survives. Nothing is printed unless the guard is armed —
# wrong stage, no current step, a step that is not in the plan, and a state file
# that does not parse all end here, allowing, as they did before.
STEP_ID="" TASK_ID="" ALLOWED="" FORBIDDEN="" REASON="" IN_REASON=""
while IFS= read -r line; do
    if [ -n "$IN_REASON" ]; then REASON+="$line"$'\n'; continue; fi
    case "$line" in
        i$'\t'*) STEP_ID="${line#?$'\t'}" ;;
        t$'\t'*) TASK_ID="${line#?$'\t'}" ;;
        a$'\t'*) ALLOWED+="${line#?$'\t'}"$'\n' ;;
        f$'\t'*) FORBIDDEN+="${line#?$'\t'}"$'\n' ;;
        r)       IN_REASON=1 ;;
    esac
done < <(jq -r '
    def tagged($t; $l): ($l // []) | .[]? | select(type == "string")
        | split("\n")[] | "\($t)\t\(.)";
    select((.current_stage // "") == "implementation")
    | ((.approved_plan.current_step_id // "") | tostring) as $sid
    | select($sid != "")
    | [ .approved_plan.steps[]? | select(.step_id == $sid) ] as $steps
    | select(($steps | length) > 0)
    | $steps[0] as $step
    | "i\t\($sid)", "t\t\(.task_id // "?")",
      tagged("a"; $step.allowed_files), tagged("f"; $step.forbidden_files),
      "r", ($step.forbidden_reason // "not part of this step")
' "$STATE" 2>/dev/null)
[ -n "$STEP_ID" ] || allow

ALLOWED=$(chomp_all "$ALLOWED")
FORBIDDEN=$(chomp_all "$FORBIDDEN")
REASON=$(chomp_all "$REASON")

# match_glob <relative-path> <patterns> — true when one of the newline-separated
# patterns matches, leaving that pattern in AI_GLOB_HIT so a deny can name it.
# A plan says "src/Payment/*.php" or "tests/**" the way a human would; bash's own
# pattern matching has the fnmatch semantics that wants ("*" crosses "/", "[!x]"
# negates), so this is the test the python one-liner made, without paying for an
# interpreter on every write. A pattern is expanded before it is matched, so a
# glob in a plan must not contain "$", "~" or a backslash.
AI_GLOB_HIT=""
match_glob() {
    local subject="$1" pattern dir
    AI_GLOB_HIT=""
    while IFS= read -r pattern; do
        [ -n "${pattern//[[:space:]]/}" ] || continue
        dir="$pattern"
        while [ "${dir%/}" != "$dir" ]; do dir="${dir%/}"; done
        if [[ $subject == $pattern || $subject == $dir/* ]]; then
            AI_GLOB_HIT="$pattern"
            return 0
        fi
    done <<< "$2"
    return 1
}

while IFS= read -r f; do
    [ -n "$f" ] || continue
    abs=$(abs_path "$f")
    rel="${abs#"$AI_ROOT"/}"

    if [ -n "$FORBIDDEN" ] && match_glob "$rel" "$FORBIDDEN"; then
        deny "$rel is explicitly forbidden for step $STEP_ID of task $TASK_ID (matched: $AI_GLOB_HIT).
Reason recorded in the plan: $REASON

Do not edit it. If the step genuinely cannot be completed without this file, stop
and report SCOPE_CHANGE_REQUIRED so the plan is amended and re-approved."
    fi

    if [ -n "$ALLOWED" ] && ! match_glob "$rel" "$ALLOWED"; then
        deny "SCOPE_CHANGE_REQUIRED — $rel is outside the approved scope of step $STEP_ID (task $TASK_ID).

Allowed for this step:
$(printf '  - %s\n' $ALLOWED)

Stop implementing, report SCOPE_CHANGE_REQUIRED with the reason this file is
needed, and let the planner amend the step. Widening scope silently is what this
guard exists to prevent. See .ai/policies/safety.md."
    fi
done < <(target_paths)

allow
