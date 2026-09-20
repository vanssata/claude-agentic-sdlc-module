#!/usr/bin/env python3
"""Task state for /ai-task — the small, machine-readable record of one task.

Why a file and not the conversation: a conversation is expensive to re-read and
impossible for a hook to consult. This file is what ai-scope-guard enforces
against, what /ai-status reports, and what lets a task survive a /clear or a
crash. It holds facts, never transcripts.

Everything is stdlib. Writes are atomic (temp file + os.replace), so a hook that
reads the file while a stage is being recorded never sees half a document.

Every state change is also appended to .ai/reports/<task-id>/events.jsonl, the
append-only journal /ai-status and /usage-report read at zero model cost. The
journal is best effort by contract: a line that cannot be written never fails
the command that emitted it, and nothing here depends on it being lossless.
history[] keeps its exact shape and its original event names beside it.

Usage:
  state.py init   --goal G --workflow W [--task-id ID] [--root DIR]
  state.py get    [--field current_stage] [--root DIR]
  state.py stage  <stage> [--note TEXT]
  state.py risk   <T0..T5> [--note TEXT]
  state.py triage <T0..T5> [--note TEXT] [--context TEXT]   discovery+context+impact+risk in one call
  state.py quick  --goal G --workflow W --tier <T0..T2> --files a,b [--note TEXT] [--context TEXT]
                                         init+triage+one-step plan in one call: the direct path below T3
  state.py plan   --ref PATH --steps STEPS.json
  state.py remediate --files a,b [--note TEXT]   one extra step R<n> for the batch of test/review fixes;
                                         allowed = every finished step's files + the ones named
  state.py step   <step_id>
  state.py step-done <step_id>
  state.py set    <field> <value>        # test_status, e2e_status, review_status, security_status, next_action
  state.py risks  --add TEXT | --clear
  state.py note   decision|rejected|failed "<text>" [--why TEXT] [--error TEXT]
  state.py events [--last N] [--type t1,t2] [--task ID] [--format lines|jsonl]
  state.py event  <type> [--detail TEXT] [--data JSON]   # for hooks; type must be in EVENT_TYPES
  state.py approve --by NAME
  state.py done   [--abandon]
  state.py archive                       # move current.json into .ai/reports/<task_id>/state.json
  state.py close                         # done + archive in one call
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:                       # not POSIX: the journal falls back to O_APPEND alone
    fcntl = None

STAGES = [
    "discovery", "context", "impact_analysis", "risk_classification",
    "plan", "plan_review", "implementation", "test", "adversarial_review",
    "security_review", "release_report", "human_approval", "done",
]
TIERS = ["T0", "T1", "T2", "T3", "T4", "T5"]
WORKFLOWS = ["feature", "bugfix", "refactoring", "hotfix", "investigation"]
TEST_STATUS = ["not_run", "passing", "existing_failure", "new_regression", "env_failure", "unknown"]
E2E_STATUS = ["not_run", "passing", "failing", "not_applicable"]
REVIEW_STATUS = ["not_started", "in_progress", "blockers_open", "passed"]
SECURITY_STATUS = ["not_applicable", "not_started", "in_progress", "passed", "failed"]

# The journal vocabulary (I3): flat, append-only, one type per command that
# changes something. A new type is added only when it has its own reader.
EVENT_TYPES = [
    "task_started", "stage_started", "tier_set", "tier_raised", "plan_registered",
    "scope_change", "step_started", "step_done", "field_set", "question_asked",
    "question_answered", "gate_requested", "gate_approved", "gate_rejected", "note",
    "handoff_written", "runtime_handoff", "model_fallback", "schema_migrated", "task_closed",
]
NOTE_KINDS = ["decision", "rejected", "failed"]
RUNTIMES = ["claude", "codex"]

JOURNAL_MAX_BYTES = 4096
DETAIL_MAX = 500
ERROR_MAX = 1000

# Resolved once in main() and read by emit(): one process serves one runtime.
RUNTIME = "unknown"
# The commands that change the task. Only these take ownership of it: reading a
# task from the other runtime, or writing a note about it, is not a handoff.
MUTATING_COMMANDS = {
    "init", "stage", "risk", "triage", "quick", "plan", "remediate",
    "step", "step-done", "set", "risks", "modules", "approve", "done", "close",
}
MUTATING = False

SETTABLE = {
    "test_status": TEST_STATUS,
    "e2e_status": E2E_STATUS,
    "review_status": REVIEW_STATUS,
    "security_status": SECURITY_STATUS,
    "next_action": None,
    "context_summary_ref": None,
    "goal": None,
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_ms():
    """Millisecond precision, because two journal lines can share a second."""
    stamp = datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (stamp.microsecond // 1000)


def find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            die("no .ai/ directory found above %s — run /ai-init first" % start)
        d = parent


def die(message):
    print("state.py: %s" % message, file=sys.stderr)
    sys.exit(1)


def state_path(root):
    return os.path.join(root, ".ai", "state", "current.json")


def session_path(root):
    return os.path.join(root, ".ai", "state", "session.json")


def read_session(root):
    """The hook's sidecar (I5). Absent, half-written or unreadable is normal."""
    try:
        with open(session_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def detect_runtime(explicit, root):
    """--runtime > AI_RUNTIME > session.json > CLAUDECODE > unknown (I10)."""
    for candidate in (explicit, os.environ.get("AI_RUNTIME"), read_session(root).get("runtime")):
        if candidate in RUNTIMES:
            return candidate
    return "claude" if os.environ.get("CLAUDECODE") else "unknown"


def journal_path(root, task_id):
    return os.path.join(root, ".ai", "reports", task_id, "events.jsonl")


def journal_line(task_id, event, actor, stage, detail, data):
    line = {
        "ts": now_ms(), "task": task_id, "event": event, "actor": actor,
        "runtime": RUNTIME, "stage": stage or "", "detail": (detail or "")[:DETAIL_MAX],
        "data": dict(data or {}),
    }
    if isinstance(line["data"].get("error"), str):
        line["data"]["error"] = line["data"]["error"][:ERROR_MAX]
    text = json.dumps(line, ensure_ascii=False) + "\n"
    if len(text.encode("utf-8")) > JOURNAL_MAX_BYTES:
        # A line that cannot fit loses its payload, never its existence. The cap
        # covers the terminator too: it is the precondition for the single write.
        line["data"] = {"truncated": True}
        text = json.dumps(line, ensure_ascii=False) + "\n"
    return text


def append_journal(root, task_id, text):
    """One complete line, one os.write, O_APPEND. Best effort: every failure is
    swallowed, because the state write is the contract and the journal is not."""
    if not task_id:
        return False
    path = journal_path(root, task_id)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    except OSError:
        return False
    payload = text.encode("utf-8")
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        # A short write (ENOSPC) returns a count rather than raising, and a torn
        # line is exactly what the single write exists to prevent — so say so.
        written = os.write(fd, payload)
    except OSError:
        return False
    finally:
        os.close(fd)
    return written == len(payload)


def read_journal(root, task_id):
    """Tolerant by design (I3): an unparseable line is counted, never fatal."""
    events, skipped = [], 0
    try:
        with open(journal_path(root, task_id), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    skipped += 1
    except OSError:
        return [], skipped
    return events, skipped


def apply_defaults(state):
    """Schema 2 keys (I6) in memory, so a v1 state answers every command before
    migration 0002 has run; save() then persists them. A reader that opens
    current.json directly — update.py does — sees the file, not these."""
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    # A hand-edited or half-migrated file may hold null where v1 held an object.
    # load() promises to be loud about a file it cannot read and silent about one
    # it can, so the defaults are total rather than assuming the v1 shape.
    if not isinstance(state.get("questions"), dict):
        state["questions"] = {"file": ".ai/reports/%s/questions.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": True, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    return state


def load(root, required=True, claim=None):
    path = state_path(root)
    if not os.path.exists(path):
        if required:
            die("no task in flight (%s does not exist). Start one with state.py init." % path)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            state = apply_defaults(json.load(fh))
    except (OSError, ValueError) as exc:
        # Loud on purpose: a corrupt state file must never be silently replaced,
        # because ai-scope-guard's boundaries are derived from it.
        die("%s is unreadable (%s). Inspect it by hand; do not delete it blindly." % (path, exc))
    # Ownership is taken before the command's own events, so the journal and
    # history both show the handoff ahead of the work it covers.
    if MUTATING if claim is None else claim:
        claim_runtime(root, state)
    return state


def claim_runtime(root, state):
    """Called from load() for the commands in MUTATING_COMMANDS, so ownership is
    taken once rather than in fifteen call sites. A task that changes runtime says
    so in the journal; WP5 is what will move a task on purpose."""
    previous = state.get("owner_runtime")
    if RUNTIME not in RUNTIMES or previous == RUNTIME:
        return
    if previous in RUNTIMES:
        emit(root, state, "runtime_handoff", "%s -> %s" % (previous, RUNTIME),
             {"from": previous, "to": RUNTIME, "via": "resume"})
    state["owner_runtime"] = RUNTIME


def save(root, state):
    state["updated_at"] = now()
    path = state_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def record(state, event, detail=""):
    state.setdefault("history", []).append(
        {"at": now(), "event": event, "detail": detail}
    )


def emit(root, state, event, detail="", data=None, legacy=None, actor="agent"):
    """One state change: today's history entry plus one journal line.

    `legacy` keeps history[]'s original event name where the journal's is newer,
    so every reader and every test written before the journal still sees what it
    expects and the two records stay one-to-one.
    """
    if event not in EVENT_TYPES:
        die("unknown event type '%s' (have: %s)" % (event, ", ".join(EVENT_TYPES)))
    record(state, legacy or event, detail)
    append_journal(root, state.get("task_id"), journal_line(
        state.get("task_id"), event, actor, state.get("current_stage"), detail, data))


def next_task_id(root):
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reports = os.path.join(root, ".ai", "reports")
    existing = []
    if os.path.isdir(reports):
        existing = [n for n in os.listdir(reports) if n.startswith("T-%s-" % day)]
    return "T-%s-%03d" % (day, len(existing) + 1)


def cmd_init(args, root):
    if args.workflow not in WORKFLOWS:
        die("workflow must be one of: %s" % ", ".join(WORKFLOWS))
    existing = load(root, required=False, claim=False)
    if existing and existing.get("current_stage") != "done" and not args.force:
        die("task %s is still at stage '%s'. Finish it, archive it, or pass --force."
            % (existing.get("task_id"), existing.get("current_stage")))
    task_id = args.task_id or next_task_id(root)
    state = {
        "task_id": task_id,
        "goal": args.goal,
        "workflow": args.workflow,
        "risk_tier": None,
        "current_stage": "discovery",
        "affected_modules": [],
        "context_summary_ref": None,
        "approved_plan": {"ref": None, "current_step_id": None, "steps": []},
        "completed_steps": [],
        "test_status": "not_run",
        "e2e_status": "not_run",
        "review_status": "not_started",
        "security_status": "not_started",
        "open_risks": [],
        "next_action": "run DISCOVERY",
        "human_approval": {"required": True, "granted": False, "granted_by": None, "granted_at": None},
        "created_at": now(),
        "updated_at": now(),
        "history": [],
    }
    apply_defaults(state)
    claim_runtime(root, state)
    os.makedirs(os.path.join(root, ".ai", "reports", task_id), exist_ok=True)
    emit(root, state, "task_started", "%s (%s)" % (args.goal, args.workflow),
         {"goal": args.goal, "workflow": args.workflow})
    save(root, state)
    print(task_id)


def cmd_get(args, root):
    state = load(root, required=not args.quiet)
    if state is None:
        print("no task in flight")
        return
    if args.field:
        value = state
        for part in args.field.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
        print(json.dumps(value) if isinstance(value, (dict, list)) else ("" if value is None else value))
    else:
        json.dump(state, sys.stdout, indent=2, ensure_ascii=False)
        print()


def emit_tier(root, state, previous, tier, note):
    """tier_raised where a tier went up, tier_set otherwise — both keep history's
    'risk_classified' name, and both record the previous value, which is the one
    thing a journal line cannot be backfilled with later."""
    detail = "%s%s" % (tier, ": " + note if note else "")
    if previous in TIERS and TIERS.index(tier) > TIERS.index(previous):
        emit(root, state, "tier_raised", detail,
             {"from": previous, "to": tier, "note": note}, legacy="risk_classified")
        return
    direction = "set"
    if previous in TIERS:
        direction = "unchanged" if previous == tier else "lowered"
    emit(root, state, "tier_set", detail,
         {"tier": tier, "from": previous, "note": note, "direction": direction},
         legacy="risk_classified")


def emit_inline_stages(root, state, previous):
    """The four stages a small task passes through in one call: recorded one by
    one so the audit trail still shows each of them. current_stage advances with
    them, because a journal line's `stage` names the stage the event put the task
    into (I3) — and these lines are never rewritten."""
    for stage in ("discovery", "context", "impact_analysis", "risk_classification"):
        state["current_stage"] = stage
        emit(root, state, "stage_started", "%s -> %s: inline" % (previous, stage),
             {"from": previous, "to": stage, "note": "inline"}, legacy="stage")
        previous = stage


def cmd_stage(args, root):
    if args.stage not in STAGES:
        die("stage must be one of: %s" % ", ".join(STAGES))
    state = load(root)
    previous = state["current_stage"]
    state["current_stage"] = args.stage
    emit(root, state, "stage_started",
         "%s -> %s%s" % (previous, args.stage, ": " + args.note if args.note else ""),
         {"from": previous, "to": args.stage, "note": args.note}, legacy="stage")
    save(root, state)
    print("%s -> %s" % (previous, args.stage))


def cmd_risk(args, root):
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    previous = state.get("risk_tier")
    state["risk_tier"] = args.tier
    emit_tier(root, state, previous, args.tier, args.note)
    save(root, state)
    print(args.tier)


def cmd_triage(args, root):
    """The four inline stages of a small task, recorded in one call so the audit
    trail still shows each of them without four round trips."""
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    previous = state["current_stage"]
    emit_inline_stages(root, state, previous)
    state["current_stage"] = "risk_classification"
    previous_tier = state.get("risk_tier")
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    emit_tier(root, state, previous_tier, args.tier, args.note)
    save(root, state)
    print("%s, triaged inline through risk_classification" % args.tier)


def cmd_plan(args, root):
    state = load(root)
    try:
        with open(args.steps, encoding="utf-8") as fh:
            steps = json.load(fh)
    except (OSError, ValueError) as exc:
        die("cannot read steps file %s (%s)" % (args.steps, exc))
    if not isinstance(steps, list) or not steps:
        die("steps file must contain a non-empty JSON array")
    for step in steps:
        for field in ("step_id", "description", "allowed_files"):
            if field not in step:
                die("step %s is missing '%s'" % (step.get("step_id", "?"), field))
        step.setdefault("forbidden_files", [])
        step.setdefault("forbidden_reason", "not part of this step")
        step.setdefault("required_tests", [])
        step.setdefault("status", "pending")
    state["approved_plan"] = {"ref": args.ref, "current_step_id": None, "steps": steps}
    emit(root, state, "plan_registered", "%d steps, %s" % (len(steps), args.ref),
         {"ref": args.ref, "steps": len(steps)}, legacy="plan_approved")
    save(root, state)
    print("%d steps recorded" % len(steps))


def cmd_step(args, root):
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    match = [s for s in steps if s["step_id"] == args.step_id]
    if not match:
        die("no step '%s' in the approved plan (have: %s)"
            % (args.step_id, ", ".join(s["step_id"] for s in steps) or "none"))
    for s in steps:
        if s["step_id"] == args.step_id:
            s["status"] = "in_progress"
    state["approved_plan"]["current_step_id"] = args.step_id
    emit(root, state, "step_started", "%s: %s" % (args.step_id, match[0]["description"]),
         {"step_id": args.step_id, "kind": "step"})
    save(root, state)
    print("step %s: %s" % (args.step_id, match[0]["description"]))
    print("allowed: %s" % ", ".join(match[0]["allowed_files"]))
    if match[0]["forbidden_files"]:
        print("forbidden: %s" % ", ".join(match[0]["forbidden_files"]))
    # Only this step's own tests run inside it; the full suite runs once after
    # the last step and the e2e suite once after that.
    print("step tests: %s" % (", ".join(match[0].get("required_tests") or []) or "none"))


def cmd_step_done(args, root):
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    if not any(s["step_id"] == args.step_id for s in steps):
        die("no step '%s' in the approved plan" % args.step_id)
    for s in steps:
        if s["step_id"] == args.step_id:
            s["status"] = "done"
    if args.step_id not in state["completed_steps"]:
        state["completed_steps"].append(args.step_id)
    if state["approved_plan"].get("current_step_id") == args.step_id:
        state["approved_plan"]["current_step_id"] = None
    emit(root, state, "step_done", args.step_id, {"step_id": args.step_id},
         legacy="step_completed")
    save(root, state)
    remaining = [s["step_id"] for s in steps if s["status"] != "done"]
    print("step %s done; remaining: %s" % (args.step_id, ", ".join(remaining) or "none"))
    if not remaining:
        print("last step: run verify_command once, to the end, then e2e_command once")


def _split_files(text):
    return [f.strip() for f in (text or "").split(",") if f.strip()]


def cmd_quick(args, root):
    """The direct path for T0–T2: one call records the task, the four inline
    triage stages and a single step whose allowed files are the ones named, so
    the scope guard is armed without a plan file, a task.md or four round trips."""
    if args.tier not in ("T0", "T1", "T2"):
        die("quick is for T0, T1 and T2; from T3 the task needs init, triage and a reviewed plan")
    files = _split_files(args.files)
    if not files:
        die("--files must name at least one file or glob the step may touch")
    cmd_init(args, root)
    state = load(root)
    previous = state["current_stage"]
    emit_inline_stages(root, state, previous)
    state["current_stage"] = "risk_classification"
    previous_tier = state.get("risk_tier")
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    emit_tier(root, state, previous_tier, args.tier, args.note)
    step = {
        "step_id": "1", "description": args.goal, "allowed_files": files,
        "forbidden_files": [], "forbidden_reason": "not part of this task",
        "required_tests": [], "status": "in_progress",
    }
    state["approved_plan"] = {"ref": "inline", "current_step_id": "1", "steps": [step]}
    emit(root, state, "plan_registered", "1 step, inline (quick)",
         {"ref": "inline", "steps": 1}, legacy="plan_approved")
    state["current_stage"] = "implementation"
    emit(root, state, "stage_started", "risk_classification -> plan -> implementation: quick",
         {"from": "risk_classification", "to": "implementation", "note": "quick"}, legacy="stage")
    emit(root, state, "step_started", "1: %s" % args.goal, {"step_id": "1", "kind": "step"})
    state["next_action"] = "implement (step tests only), then the verification command once, then e2e once"
    save(root, state)
    print("%s %s: step 1 armed for %s" % (state["task_id"], args.tier, ", ".join(files)))


def cmd_remediate(args, root):
    """One extra step for the whole batch of fixes after the test run or the
    review — never one step per failure. Its scope is the union of every step
    already done plus the files named (usually the failing tests)."""
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    if not steps:
        die("no approved plan to remediate; register one with plan or quick first")
    if any(s["status"] == "in_progress" for s in steps):
        die("a step is still in progress; finish it with step-done before remediating")
    allowed = []
    for s in steps:
        for f in s.get("allowed_files", []):
            if f not in allowed:
                allowed.append(f)
    for f in _split_files(args.files):
        if f not in allowed:
            allowed.append(f)
    n = 1 + sum(1 for s in steps if str(s["step_id"]).startswith("R"))
    step_id = "R%d" % n
    step = {
        "step_id": step_id,
        "description": args.note or "remediation batch %d" % n,
        "allowed_files": allowed, "forbidden_files": [],
        "forbidden_reason": "not part of this task", "required_tests": [],
        "status": "in_progress",
    }
    steps.append(step)
    state["approved_plan"]["current_step_id"] = step_id
    state["current_stage"] = "implementation"
    # Two lines for one step, matching the two history entries and the mapping
    # migration 0002 backfills with: a reader counts data.kind, not the type.
    emit(root, state, "step_started", "%s: %s" % (step_id, step["description"]),
         {"step_id": step_id, "kind": "remediation"}, legacy="remediation")
    emit(root, state, "step_started", "%s: %s" % (step_id, step["description"]),
         {"step_id": step_id, "kind": "step"})
    save(root, state)
    print("step %s armed for %s" % (step_id, ", ".join(allowed)))


def cmd_close(args, root):
    cmd_done(args, root)
    cmd_archive(args, root)


def cmd_set(args, root):
    if args.field not in SETTABLE:
        die("settable fields: %s" % ", ".join(sorted(SETTABLE)))
    allowed = SETTABLE[args.field]
    if allowed and args.value not in allowed:
        die("%s must be one of: %s" % (args.field, ", ".join(allowed)))
    state = load(root)
    previous = state.get(args.field)
    state[args.field] = args.value
    emit(root, state, "field_set", "%s = %s" % (args.field, args.value),
         {"field": args.field, "from": previous, "value": args.value}, legacy="set")
    save(root, state)
    print("%s = %s" % (args.field, args.value))


def cmd_risks(args, root):
    state = load(root)
    previous = list(state.get("open_risks", []))
    if args.clear:
        state["open_risks"] = []
        emit(root, state, "field_set", "",
             {"field": "open_risks", "from": previous, "value": []}, legacy="risks_cleared")
    elif args.add:
        state["open_risks"].append(args.add)
        emit(root, state, "field_set", args.add,
             {"field": "open_risks", "from": previous, "value": state["open_risks"]},
             legacy="risk_added")
    else:
        die("pass --add TEXT or --clear")
    save(root, state)
    print("%d open risk(s)" % len(state["open_risks"]))


def cmd_modules(args, root):
    state = load(root)
    previous = list(state.get("affected_modules", []))
    for module in args.module:
        if module not in state["affected_modules"]:
            state["affected_modules"].append(module)
    emit(root, state, "field_set", ", ".join(args.module),
         {"field": "affected_modules", "from": previous, "value": state["affected_modules"]},
         legacy="modules")
    save(root, state)
    print(", ".join(state["affected_modules"]))


def cmd_note(args, root):
    """A decision, a rejected option or a failed attempt. It goes to the journal
    only: these are the facts a compaction loses, not state the guards enforce,
    so current.json does not grow with them."""
    if args.kind not in NOTE_KINDS:
        die("note kind must be one of: %s" % ", ".join(NOTE_KINDS))
    state = load(root)
    data = {"kind": args.kind, "text": args.text}
    if args.why:
        data["why"] = args.why
    if args.error:
        data["error"] = args.error
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], "note", "agent", state.get("current_stage"),
        "%s: %s" % (args.kind, args.text), data))
    print("noted (%s)" % args.kind)


def cmd_event(args, root):
    """For hooks and for WP5's model fallback: one journal line, no state write.
    current.json keeps its two writers; this command is not one of them."""
    if args.type not in EVENT_TYPES:
        die("unknown event type '%s' (have: %s)" % (args.type, ", ".join(EVENT_TYPES)))
    data = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except ValueError as exc:
            die("--data must be a JSON object (%s)" % exc)
        if not isinstance(data, dict):
            die("--data must be a JSON object")
    state = load(root)
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], args.type, "hook", state.get("current_stage"), args.detail, data))
    print("%s recorded" % args.type)


def latest_task_id(root):
    """The journal outlives current.json, which archive removes — so the reader
    falls back to the newest journal rather than reporting no task in flight."""
    reports = os.path.join(root, ".ai", "reports")
    candidates = []
    for name in os.listdir(reports) if os.path.isdir(reports) else []:
        path = os.path.join(reports, name, "events.jsonl")
        if os.path.exists(path):
            candidates.append((os.path.getmtime(path), name))
    return sorted(candidates)[-1][1] if candidates else None


def cmd_events(args, root):
    task_id = args.task
    if not task_id:
        state = load(root, required=False)
        task_id = state["task_id"] if state else latest_task_id(root)
    if not task_id:
        die("no task in flight and no journal under .ai/reports/")
    if args.type:
        for wanted in _split_files(args.type):
            if wanted not in EVENT_TYPES:
                die("unknown event type '%s' (have: %s)" % (wanted, ", ".join(EVENT_TYPES)))
    events, skipped = read_journal(root, task_id)
    if args.type:
        wanted = _split_files(args.type)
        events = [e for e in events if e.get("event") in wanted]
    if args.last > 0:
        events = events[-args.last:]
    for event in events:
        if args.format == "jsonl":
            print(json.dumps(event, ensure_ascii=False))
        else:
            print("%s  %-16s %s" % (event.get("ts", ""), event.get("event", ""), event.get("detail", "")))
    if skipped:
        print("state.py: events: skipped %d unparseable line(s) in %s"
              % (skipped, journal_path(root, task_id)), file=sys.stderr)


def cmd_approve(args, root):
    state = load(root)
    state["human_approval"].update({
        "required": True, "granted": True,
        "granted_by": args.by, "granted_at": now(),
    })
    # via/unattended/tty stay unset here: the routes that fill them, and the
    # refusal that guards them, are step 3's.
    emit(root, state, "gate_approved", "granted by %s" % args.by,
         {"by": args.by, "via": None, "unattended": False, "tty": None},
         legacy="human_approval")
    save(root, state)
    print("approved by %s" % args.by)


def cmd_done(args, root):
    abandoned = bool(getattr(args, "abandon", False))
    state = load(root)
    state["current_stage"] = "done"
    state["next_action"] = "none — task abandoned" if abandoned else "none — task closed"
    emit(root, state, "task_closed", "abandoned" if abandoned else "",
         {"abandoned": abandoned})
    save(root, state)
    print("%s %s" % (state["task_id"], "abandoned" if abandoned else "closed"))


def cmd_archive(_args, root):
    state = load(root)
    target_dir = os.path.join(root, ".ai", "reports", state["task_id"])
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, "state.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.remove(state_path(root))
    print(target)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".", help="project directory (default: search upwards for .ai/)")
    parser.add_argument("--runtime", choices=RUNTIMES,
                        help="overrides AI_RUNTIME and detection for this call")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init"); p.add_argument("--goal", required=True)
    p.add_argument("--workflow", required=True); p.add_argument("--task-id")
    p.add_argument("--force", action="store_true"); p.set_defaults(func=cmd_init)

    p = sub.add_parser("get"); p.add_argument("--field")
    p.add_argument("--quiet", action="store_true"); p.set_defaults(func=cmd_get)

    p = sub.add_parser("stage"); p.add_argument("stage"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_stage)

    p = sub.add_parser("risk"); p.add_argument("tier"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_risk)

    p = sub.add_parser("triage"); p.add_argument("tier"); p.add_argument("--note", default="")
    p.add_argument("--context", default=""); p.set_defaults(func=cmd_triage)

    p = sub.add_parser("quick"); p.add_argument("--goal", required=True)
    p.add_argument("--workflow", required=True); p.add_argument("--tier", required=True)
    p.add_argument("--files", required=True); p.add_argument("--note", default="")
    p.add_argument("--context", default=""); p.add_argument("--task-id")
    p.add_argument("--force", action="store_true"); p.set_defaults(func=cmd_quick)

    p = sub.add_parser("plan"); p.add_argument("--ref", required=True)
    p.add_argument("--steps", required=True); p.set_defaults(func=cmd_plan)

    p = sub.add_parser("remediate"); p.add_argument("--files", default="")
    p.add_argument("--note", default=""); p.set_defaults(func=cmd_remediate)

    p = sub.add_parser("step"); p.add_argument("step_id"); p.set_defaults(func=cmd_step)
    p = sub.add_parser("step-done"); p.add_argument("step_id"); p.set_defaults(func=cmd_step_done)

    p = sub.add_parser("set"); p.add_argument("field"); p.add_argument("value")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("risks"); p.add_argument("--add"); p.add_argument("--clear", action="store_true")
    p.set_defaults(func=cmd_risks)

    p = sub.add_parser("modules"); p.add_argument("module", nargs="+"); p.set_defaults(func=cmd_modules)

    p = sub.add_parser("note"); p.add_argument("kind"); p.add_argument("text")
    p.add_argument("--why", default=""); p.add_argument("--error", default="")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("event"); p.add_argument("type"); p.add_argument("--detail", default="")
    p.add_argument("--data"); p.set_defaults(func=cmd_event)

    p = sub.add_parser("events"); p.add_argument("--last", type=int, default=20,
                                                 help="0 prints every line")
    p.add_argument("--type"); p.add_argument("--task")
    p.add_argument("--format", choices=["lines", "jsonl"], default="lines")
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("approve"); p.add_argument("--by", required=True); p.set_defaults(func=cmd_approve)

    p = sub.add_parser("done"); p.add_argument("--abandon", action="store_true")
    p.set_defaults(func=cmd_done)
    p = sub.add_parser("archive"); p.set_defaults(func=cmd_archive)
    p = sub.add_parser("close"); p.set_defaults(func=cmd_close)

    global RUNTIME, MUTATING              # pylint: disable=global-statement
    args = parser.parse_args()
    root = find_root(args.root)
    RUNTIME = detect_runtime(args.runtime, root)
    MUTATING = args.command in MUTATING_COMMANDS
    args.func(args, root)


if __name__ == "__main__":
    main()
