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
  state.py ask    "<question>" --option "A: text" [--option ...] [--recommend A] [--gate G] [--topic S]
  state.py ask    --batch FILE.json [--topic SLUG]
  state.py answer Q1=B [Q2=X:"text"] [--by NAME] [--via picker|prose|file] | --prose "1B 2A 3: text"
  state.py questions [--pending] [--sync] [--format md|prose|json] [--topic SLUG]
  state.py note   decision|rejected|failed "<text>" [--why TEXT] [--error TEXT]
  state.py handoff [--print] [--reason stage|precompact|manual|session-start]
  state.py events [--last N] [--type t1,t2] [--task ID] [--format lines|jsonl]
  state.py event  <type> [--detail TEXT] [--data JSON]   # for hooks; type must be in EVENT_TYPES
  state.py approve --by NAME [--note TEXT]   # outside the agent: a TTY, or AI_UNATTENDED
  state.py reject  --by NAME --why TEXT
  state.py done   [--abandon]
  state.py archive                       # move current.json into .ai/reports/<task_id>/state.json
  state.py close                         # done + archive in one call
"""

import argparse
import contextlib
import json
import os
import re
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

# The questions file is written by state.py and never by a model (R1). One regex
# per line (I2), so a hand edit that keeps the shape round-trips exactly.
QUESTIONS_HEADER = """# Questions — %s
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->
"""
OTHER_OPTION = "X. Other — answer as `X: <text>`"
HEADING_RE = re.compile(r"^## (Q|G)(\d+)\. (.+)$")
OPTION_RE = re.compile(r"^([A-W])\. (.+?)( \(recommended\))?$")
OTHER_RE = re.compile(r"^X\. Other")
ANSWER_RE = re.compile(r"^\[Answer\]:\s*(.*)$")
META_RE = re.compile(r"^asked: (\S+) · stage: (\S+)(?: · by: (.+))?$")
CONTEXT_RE = re.compile(r"^context: (.+)$")
# The trailer must be a suffix free text cannot produce: a closed `via`
# vocabulary, an exact timestamp, and a name that cannot span another em dash —
# otherwise `X: we chose Adyen — by the way it is cheaper` eats its own answer.
VIA_VALUES = "picker|prose|file|terminal|unattended"
TRAILER_RE = re.compile(
    r"\s+—\s+by ([^—]+?) via (%s) at (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$" % VIA_VALUES)
CHOICE_RE = re.compile(r"^[A-W]$")
CHOICE_TEXT_RE = re.compile(r"^([A-W])\s*[—:-]\s*(.+)$")
OTHER_TEXT_RE = re.compile(r"^X\s*:\s*(.+)$")
LETTER_RE = re.compile(r"^[A-Z]$")
PROSE_CHOICE_RE = re.compile(r"\b(\d+)\s*([A-W])\b")
PROSE_TEXT_RE = re.compile(r"\b(\d+)\s*:")
OPTION_INPUT_RE = re.compile(r"^([A-W])\s*[:.]\s*(.+)$")
OPTION_KEY_RE = re.compile(r"^[A-W]$")
OPTION_HEAD_RE = re.compile(r"^([A-Za-z0-9]{1,3})\s*[:.]\s")

# A pending question stops a stage from moving; it never stops a command that
# records, reads or answers (R3). done --abandon is exempt: abandoning a task is
# how an unanswerable question is closed.
BLOCKING_COMMANDS = {
    "stage", "triage", "plan", "step", "step-done", "remediate", "approve", "done", "close",
}
RUNTIMES = ["claude", "codex"]

JOURNAL_MAX_BYTES = 4096
DETAIL_MAX = 500
ERROR_MAX = 1000

# Resolved once in main() and read by emit(): one process serves one runtime.
RUNTIME = "unknown"
# The commands that change the task. Only these take ownership of it: reading a
# task from the other runtime, or writing a note about it, is not a handoff.
MUTATING_COMMANDS = {
    "init", "stage", "risk", "triage", "quick", "plan", "remediate", "step", "step-done",
    "set", "risks", "modules", "ask", "answer", "approve", "reject", "done", "close",
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


def die(message, code=1):
    """1 validation · 2 argparse · 4 QUESTIONS_PENDING · 5 APPROVAL_REFUSED (I1)."""
    print("state.py: %s" % message, file=sys.stderr)
    sys.exit(code)


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
    if args.stage == "human_approval":
        request_gate(root, state, "human_approval")
    emit(root, state, "stage_started",
         "%s -> %s%s" % (previous, args.stage, ": " + args.note if args.note else ""),
         {"from": previous, "to": args.stage, "note": args.note}, legacy="stage")
    set_resume_point(state)
    write_handoff(root, state, "stage")
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
    write_handoff(root, state, "stage")
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
    write_handoff(root, state, "stage")
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
    set_resume_point(state)
    write_handoff(root, state, "stage")
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
    set_resume_point(state)
    write_handoff(root, state, "stage")
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
    set_resume_point(state)
    write_handoff(root, state, "stage")
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
    set_resume_point(state)
    write_handoff(root, state, "stage")
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


def find_docs_root(start):
    """--topic resolves its root from docs/sdlc/, never from .ai/: an intent's
    questions belong to the document they serve, and the sdlc-* skills must work
    in a repository that has no .ai/ at all (I11)."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "docs", "sdlc")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            die("no docs/sdlc/ directory found above %s — run /sdlc-intent first" % start)
        d = parent


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def questions_path(root, state, topic):
    if topic:
        # Topic mode is the one writer that runs without .ai/ and therefore
        # without the path guard, so the slug is validated here rather than
        # trusted: it names a file, it never steers one.
        if not SLUG_RE.match(topic):
            die("--topic takes a slug of lowercase letters, digits and hyphens, not %r" % topic)
        return os.path.join(root, "docs", "sdlc", "intent", "%s.questions.md" % topic)
    return os.path.join(root, ".ai", "reports", state["task_id"], "questions.md")


def parse_answer_body(question, body):
    """`LETTER`, `LETTER: text`, `X: text` or bare text, with the trailer this
    command writes parsed back off the end and ignored (I2)."""
    question["choice"] = question["text"] = None
    question["invalid"] = None
    trailer = TRAILER_RE.search(body)
    if trailer:
        question["answered_by"], question["via"], question["answered_at"] = trailer.groups()
        body = body[:trailer.start()]
    body = body.strip()
    if not body:
        return
    letters = [letter for letter, _ in question["options"]]
    if question["other"]:
        letters.append("X")
    other = OTHER_TEXT_RE.match(body)
    pair = CHOICE_TEXT_RE.match(body)
    if other:
        choice, text = "X", other.group(1).strip()
    elif pair:
        choice, text = pair.group(1), pair.group(2).strip()
    elif CHOICE_RE.match(body) or LETTER_RE.match(body):
        choice, text = body, None
    else:
        choice, text = ("X" if question["other"] else None), body
    if choice is not None and choice not in letters:
        question["invalid"] = choice
        return
    question["choice"], question["text"] = choice, text


def parse_questions(path):
    """One regex per line (I2). Returns the file's lines beside the questions, so
    a writer can replace an [Answer]: line and leave every other byte alone."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return [], []
    questions, current = [], None
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading:
            current = {
                "id": heading.group(1) + heading.group(2), "kind": heading.group(1),
                "number": int(heading.group(2)), "question": heading.group(3),
                "asked": None, "stage": None, "by": None, "context": None,
                "options": [], "recommend": None, "other": False,
                "answer_at": None, "choice": None, "text": None, "invalid": None,
                "answered_by": None, "via": None, "answered_at": None,
            }
            questions.append(current)
            continue
        if current is None:
            continue
        meta = META_RE.match(line)
        if meta:
            current["asked"], current["stage"], current["by"] = meta.groups()
            continue
        context = CONTEXT_RE.match(line)
        if context:
            current["context"] = context.group(1)
            continue
        answer = ANSWER_RE.match(line)
        if answer:
            current["answer_at"] = index
            parse_answer_body(current, answer.group(1))
            current = None                # the block ends at its answer line
            continue
        if OTHER_RE.match(line):
            current["other"] = True
            continue
        option = OPTION_RE.match(line)
        if option:
            current["options"].append((option.group(1), option.group(2)))
            if option.group(3):
                current["recommend"] = option.group(1)
    return lines, questions


def is_pending(question):
    return question["choice"] is None


@contextlib.contextmanager
def question_lock(path):
    """questions.md is read, modified and written back. Without a lock across
    that window two `ask` calls lose a block — and the journal would then name a
    question the file does not hold, which nothing would ever block on."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    if fcntl is None:
        yield
        return
    # The lock is taken on the directory itself, so the audit trail gains no
    # lock file and the lock survives the os.replace that swaps the inode.
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        yield
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def write_questions(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp, path)


def one_line(text):
    """Everything a caller writes into the file is collapsed to one line: a
    newline in an answer would otherwise produce a second [Answer]: line, and the
    file a human reads would disagree with the record every command acts on."""
    return " ".join((text or "").split())


def answer_line(choice, text, by, via):
    text = one_line(text)
    if choice and text:
        body = "%s: %s" % (choice, text)
    elif choice:
        body = choice
    else:
        body = text
    return "[Answer]: %s — by %s via %s at %s" % (body, one_line(by) or "unknown", via, now())


def question_block(question, stage, by):
    by = one_line(by)
    block = ["", "## %s. %s" % (question["id"], one_line(question["question"])),
             "asked: %s · stage: %s%s" % (now(), stage, " · by: " + by if by else "")]
    if question.get("context"):
        block.append("context: %s" % one_line(question["context"]))
    for letter, text in question["options"]:
        block.append("%s. %s%s" % (letter, one_line(text),
                                   " (recommended)" if letter == question.get("recommend") else ""))
    block.append(OTHER_OPTION)
    block.append("[Answer]:")
    return block


def render_prose(questions):
    """The rendering every runtime can show. The number is the question's own id
    number, so the same reply means the same thing whenever it is given."""
    out = []
    for question in questions:
        answered = "" if is_pending(question) else "  — answered: %s" % question["choice"]
        out.append("%s. %s  [%s]%s"
                   % (question["number"], question["question"], question["id"], answered))
        if question["context"]:
            out.append("   context: %s" % question["context"])
        for letter, text in question["options"]:
            out.append("   %s. %s%s" % (letter, text,
                                        " (recommended)" if letter == question["recommend"] else ""))
        if question["other"]:
            out.append("   X. Other — answer as `X: <text>`")
    pending = [q for q in questions if is_pending(q)]
    if pending:
        out.append("Reply `%s`, a free-text answer last, or run: state.py answer %s"
                   % (" ".join("%s<letter>" % q["number"] for q in pending),
                      " ".join("%s=<letter>" % q["id"] for q in pending)))
    return out


def render_md(questions):
    out = []
    for question in questions:
        if is_pending(question):
            out.append("- **%s** — _unanswered_ (%s)" % (question["question"], question["id"]))
            continue
        chosen = dict(question["options"]).get(question["choice"], question["text"] or "Other")
        detail = "%s — %s" % (chosen, question["text"]) if question["text"] and question["choice"] != "X" else chosen
        out.append("- **%s** — %s *(%s, %s)*" % (
            question["question"], detail, question["id"],
            "by %s via %s at %s" % (question["answered_by"], question["via"], question["answered_at"])
            if question["answered_by"] else "answered"))
    return out


def render_questions(questions, fmt):
    if fmt == "json":
        shown = []
        for question in questions:
            item = {k: v for k, v in question.items() if k != "answer_at"}
            item["options"] = [{"key": k, "text": t} for k, t in question["options"]]
            item["pending"] = is_pending(question)
            shown.append(item)
        return [json.dumps(shown, ensure_ascii=False, indent=2)]
    if fmt == "md":
        return render_md(questions)
    return render_prose(questions)


def parse_prose(text, by_id):
    """`3B` is a choice for Q3, `3: …` is free text for Q3.

    The number is the question's own id number, not its position in a rendering
    — a rendering the human saw yesterday must not answer a different question
    today. Free text runs to the end of the reply, because a sentence may
    legitimately contain `2B` or `step 2:` and half an answer is worse than a
    refusal; so a free-text answer comes last.
    """
    assignments = []
    start = PROSE_TEXT_RE.search(text)
    head = text[:start.start()] if start else text
    for token in PROSE_CHOICE_RE.finditer(head):
        assignments.append((prose_id(int(token.group(1)), by_id), token.group(2), None))
    if start:
        assignments.append((prose_id(int(start.group(1)), by_id), "X",
                            text[start.end():].strip()))
    if not assignments:
        die("no answers found in %r — reply like `1B 2A 3: free text`" % text)
    return assignments


def prose_id(number, by_id):
    qid = "Q%d" % number
    if qid not in by_id:
        die("prose answer %d has no question (have: %s)"
            % (number, ", ".join(i for i in by_id if i.startswith("Q")) or "none"))
    return qid


def unquote(text):
    """I1 writes the free-text form as X:"free text"; the quotes belong to the
    body and are stripped only as a matching pair."""
    text = text.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_assignment(token):
    """Q1=B, Q2=X:free text, Q3=B: because."""
    if "=" not in token:
        die("answer takes Q1=B, not %r" % token)
    qid, value = token.split("=", 1)
    value = value.strip()
    other = OTHER_TEXT_RE.match(value)
    if other:
        return (qid.strip(), "X", unquote(other.group(1)))
    pair = CHOICE_TEXT_RE.match(value)
    if pair:
        return (qid.strip(), pair.group(1), unquote(pair.group(2)))
    # A bare letter is a choice even when it is not one of the options, so a
    # typo is refused rather than silently recorded as free text.
    if LETTER_RE.match(value):
        return (qid.strip(), value, None)
    return (qid.strip(), None, unquote(value))


def set_pending(root, state, questions, path):
    """questions.pending is a cache; the file is the truth (spec alternative 4)."""
    state["questions"] = {
        "file": os.path.relpath(path, root),
        "pending": [q["id"] for q in questions if is_pending(q)],
    }


def cmd_ask(args, root):
    if args.topic and args.gate:
        die("--gate belongs to a task, not to a topic: a topic file has ## Q blocks only")
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    stage = "intent" if args.topic else state["current_stage"]
    asked = []
    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as fh:
                batch = json.load(fh)
        except (OSError, ValueError) as exc:
            die("cannot read batch file %s (%s)" % (args.batch, exc))
        if not isinstance(batch, list) or not batch:
            die("the batch file must contain a non-empty JSON array")
        for item in batch:
            if not isinstance(item, dict):
                die("every batch item must be an object with question and options")
            options = item.get("options") or []
            if not all(isinstance(o, dict) and "key" in o and "text" in o for o in options):
                die("every option needs a key and a text (%r)" % item.get("question"))
            asked.append({"question": item.get("question"),
                          "options": [(o["key"], o["text"]) for o in options],
                          "recommend": item.get("recommend"), "context": item.get("context")})
    else:
        if not args.question:
            die("ask takes a question, or --batch FILE.json")
        options, letters = [], "ABCDEFGHIJKLMNOPQRSTUVW"
        for option in args.option:
            # Collapsed first: a key is only recognisable once the value is one
            # line, and one line is what the file will hold either way.
            option = one_line(option)
            if len(options) >= len(letters):
                die("a question takes at most %d options" % len(letters))
            head = OPTION_INPUT_RE.match(option)
            if head:
                options.append((head.group(1), head.group(2).strip()))
                continue
            labelled = OPTION_HEAD_RE.match(option)
            if labelled:
                # "1: one" or "aa: one" is a key the I2 grammar cannot parse, not
                # an option whose text happens to start that way.
                die("an option key is one letter A–W, not %r" % labelled.group(1))
            options.append((letters[len(options)], option))
        asked.append({"question": args.question, "options": options,
                      "recommend": args.recommend, "context": args.context})
    for item in asked:
        if not item["question"]:
            die("every question needs a question line")
        if len(item["options"]) < 2:
            die("a question needs at least two options (%r has %d)"
                % (item["question"], len(item["options"])))
        keys = [key for key, _ in item["options"]]
        # An option the I2 grammar cannot parse would round-trip as no option at
        # all, and the answer to it would be recorded as free text (R1).
        for key in keys:
            if not OPTION_KEY_RE.match(key):
                die("an option key is one letter A–W, not %r" % key)
        if len(set(keys)) != len(keys):
            die("option keys must be distinct (%s)" % ", ".join(keys))
        for _, text in item["options"]:
            if text.endswith(" (recommended)"):
                die("an option text cannot end with ' (recommended)' — use --recommend")
        if item["recommend"] and item["recommend"] not in keys:
            die("--recommend %s is not one of the options (%s)"
                % (item["recommend"], ", ".join(keys)))

    new_ids = []
    with question_lock(path):
        lines, existing = parse_questions(path)
        while lines and not lines[-1].strip():
            lines.pop()
        if not any(line.startswith("# Questions") for line in lines):
            # An existing but empty (or header-less) file still gets the notice
            # that tells a human not to edit the questions.
            lines = (QUESTIONS_HEADER % (args.topic or state["task_id"])).rstrip("\n").split("\n") + lines
        kind = "G" if args.gate else "Q"
        number = max([q["number"] for q in existing if q["kind"] == kind] or [0])
        for item in asked:
            number += 1
            item["id"] = "%s%d" % (kind, number)
            if args.gate:
                item["question"] = "%s (gate: %s)" % (item["question"], args.gate)
            new_ids.append(item["id"])
            lines.extend(question_block(item, stage, args.by))
        write_questions(path, lines)
        lines, questions = parse_questions(path)
    relative = os.path.relpath(path, root)
    if state is not None:
        for item in asked:
            emit(root, state, "question_asked", "%s: %s" % (item["id"], item["question"]),
                 {"id": item["id"], "options": [letter for letter, _ in item["options"]],
                  "recommended": item["recommend"], "gate": args.gate})
        set_pending(root, state, questions, path)
        save(root, state)
    print("%s asked → %s" % (" ".join(new_ids), relative))
    for line in render_prose([q for q in questions if is_pending(q)]):
        print(line)
    if os.environ.get("AI_UNATTENDED"):
        # The literal line an unattended launcher greps for (R5).
        print("WAITING_FOR_ANSWERS %s %s" % (relative, " ".join(new_ids)))


def apply_answers(lines, by_id, assignments, args, relative):
    for qid, choice, text in assignments:
        question = by_id.get(qid)
        if question is None:
            die("no question %s in %s (have: %s)" % (qid, relative, ", ".join(by_id) or "none"))
        if question["kind"] == "G":
            die("%s is a gate: run 'state.py approve' in your terminal or fill its [Answer]: line" % qid)
        letters = [letter for letter, _ in question["options"]]
        if question["other"]:
            letters.append("X")
        if choice is None:
            choice = "X" if question["other"] else None
        if choice not in letters:
            die("%s: invalid choice %r (options: %s)" % (qid, choice, ", ".join(letters)))
        lines[question["answer_at"]] = answer_line(choice, text, args.by, args.via)


def cmd_answer(args, root):
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    with question_lock(path):
        lines, questions = parse_questions(path)
        if not questions:
            die("no questions in %s" % os.path.relpath(path, root))
        by_id = {q["id"]: q for q in questions}
        assignments = []
        if args.prose:
            assignments = parse_prose(args.prose, by_id)
        for token in args.assignment:
            assignments.append(parse_assignment(token))
        if not assignments:
            die("answer takes Q1=B …, or --prose \"1B 2A 3: text\"")
        apply_answers(lines, by_id, assignments, args, os.path.relpath(path, root))
        write_questions(path, lines)
        lines, questions = parse_questions(path)
        by_id = {q["id"]: q for q in questions}
    if state is not None:
        for qid, _, _ in assignments:
            question = by_id[qid]
            # actor is derived from the route, never asserted by the caller:
            # `human` is reserved for the file route and the gate (I3).
            emit(root, state, "question_answered", "%s = %s" % (qid, question["choice"]),
                 {"id": qid, "choice": question["choice"], "text": question["text"],
                  "via": args.via, "by": args.by}, actor="agent")
        set_pending(root, state, questions, path)
        save(root, state)
    pending = [q["id"] for q in questions if is_pending(q)]
    print("%s answered; %s" % (", ".join(qid for qid, _, _ in assignments),
                               ("still pending: " + ", ".join(pending)) if pending else "none pending"))


def sync_answers(root, state, path, lines, questions, args):
    """Pick up hand edits: a filled line with no trailer is a fresh answer, a
    line this command already wrote has one, so syncing twice changes nothing."""
    changed = []
    for question in questions:
        if question["invalid"]:
            print("state.py: %s: invalid choice %r — it stays pending"
                  % (question["id"], question["invalid"]), file=sys.stderr)
            continue
        if question["choice"] is not None and not question["answered_by"]:
            lines[question["answer_at"]] = answer_line(
                question["choice"], question["text"], args.by, "file")
            changed.append(question)
    if not changed:
        return []
    if state is not None:
        # Recording answers changes the task, so it takes ownership as ask does.
        claim_runtime(root, state)
    write_questions(path, lines)
    if state is not None:
        by_id = {q["id"]: q for q in parse_questions(path)[1]}
        for question in changed:
            if question["kind"] == "G":
                continue                          # the gate's file route is step 6's
            current = by_id[question["id"]]
            emit(root, state, "question_answered", "%s = %s" % (current["id"], current["choice"]),
                 {"id": current["id"], "choice": current["choice"], "text": current["text"],
                  "via": "file", "by": args.by}, actor="human")
    return changed


def cmd_questions(args, root):
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    with question_lock(path) if args.sync else contextlib.nullcontext():
        lines, questions = parse_questions(path)
        if args.sync and sync_answers(root, state, path, lines, questions, args):
            _, questions = parse_questions(path)
    if state is not None:
        cached = (state.get("questions") or {}).get("pending")
        set_pending(root, state, questions, path)
        if state["questions"]["pending"] != cached:
            # A read must not bump updated_at: /ai-status calls this every time.
            save(root, state)
    shown = [q for q in questions if is_pending(q)] if args.pending else questions
    for line in render_questions(shown, args.format):
        print(line)


def handoff_path(root):
    return os.path.join(root, ".ai", "state", "handoff.md")


def set_resume_point(state):
    """Where a session that lost its context picks the work up again."""
    plan = state.get("approved_plan") or {}
    state["resume_point"] = {
        "stage": state.get("current_stage"),
        "step_id": plan.get("current_step_id"),
        "next_action": state.get("next_action"),
        "at": now(),
        "runtime": RUNTIME if RUNTIME in RUNTIMES else state.get("owner_runtime"),
    }


def notes_by_kind(root, task_id, kind, limit=3):
    events, _ = read_journal(root, task_id)
    notes = [e for e in events
             if e.get("event") == "note" and (e.get("data") or {}).get("kind") == kind]
    return list(reversed(notes))[:limit]


def handoff_lines(root, state, reason):
    """The six parts of I4, ≤ 30 lines by construction: a header, the three
    facts a session needs first, three sections of three notes, and the user's
    own last words. Everything here is a fact the runtime cannot lose — the
    state, the journal, questions.md and session.json — never a transcript."""
    plan = state.get("approved_plan") or {}
    steps = plan.get("steps") or []
    step = " · step %s/%d" % (plan.get("current_step_id") or "-", len(steps)) if steps else ""
    out = ["# Handoff — %s (%s, %s) · stage %s%s · owner %s · written %s (%s)"
           % (state.get("task_id"), state.get("workflow"), state.get("risk_tier") or "untiered",
              state.get("current_stage"), step, state.get("owner_runtime") or "unknown",
              now(), reason),
           "Goal: %s" % one_line(state.get("goal"))[:160]]

    resume = state.get("resume_point") or {}
    allowed = [s for s in steps if s.get("step_id") == resume.get("step_id")]
    where = ""
    if resume.get("step_id"):
        where = "   ← resume point (step %s: %s)" % (
            resume["step_id"],
            ", ".join((allowed[0].get("allowed_files") or [])[:2]) if allowed else "scope in the plan")
    out.append("Next: %s%s" % (one_line(state.get("next_action")) or "none recorded", where))

    path = questions_path(root, state, None)
    pending = [q["id"] for q in parse_questions(path)[1] if is_pending(q)]
    out.append("Pending questions: %s" % (
        "%s — %s" % (", ".join(pending), os.path.relpath(path, root)) if pending else "none"))

    for kind, heading in (("decision", "Decisions"), ("rejected", "Rejected"),
                          ("failed", "Failed attempts")):
        out.append("## %s (latest 3)" % heading)
        notes = notes_by_kind(root, state.get("task_id"), kind)
        if not notes:
            out.append("- none")
            continue
        for note in notes:
            data = note.get("data") or {}
            text = one_line(data.get("text"))
            if kind == "failed":
                out.append("- %s — error: %s" % (text, one_line(data.get("error"))[:160] or "none given"))
            else:
                out.append("- %s%s" % (text, " — because %s" % one_line(data.get("why")) if data.get("why") else ""))

    session = read_session(root)
    out.append("## Latest user instruction (verbatim, %s, %s)"
               % (session.get("last_prompt_at") or "never", session.get("runtime") or "unknown"))
    if os.environ.get("AI_HANDOFF_NO_PROMPT"):
        # The prompt may carry a secret; recording it is the default, not a duty.
        out.append("> omitted (AI_HANDOFF_NO_PROMPT=1)")
    else:
        out.append("> %s" % (one_line(session.get("last_prompt"))[:300] or "none recorded"))
    return out


def write_handoff(root, state, reason):
    """A pure function of the state, the journal, questions.md and session.json,
    written atomically — rendering it twice gives the same file but its
    timestamp. Best effort like the journal: a handoff that cannot be written
    must never fail the command that moved the stage."""
    lines = handoff_lines(root, state, reason)
    path = handoff_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        os.replace(tmp, path)
    except OSError:
        return lines
    state["handoff"] = {"file": os.path.relpath(path, root), "written_at": now(), "reason": reason}
    # Journal-only, like note: the handoff is derived, and history[] records
    # what changed the task, not what was rendered from it.
    append_journal(root, state.get("task_id"), journal_line(
        state.get("task_id"), "handoff_written", "agent", state.get("current_stage"),
        reason, {"reason": reason, "lines": len(lines)}))
    return lines


def cmd_handoff(args, root):
    state = load(root)
    lines = write_handoff(root, state, args.reason)
    save(root, state)
    if args.print_it:
        for line in lines:
            print(line)
    else:
        print(os.path.relpath(handoff_path(root), root))


def guard_pending(root, command):
    """The file is re-parsed on every stage-moving command — questions.pending is
    only a cache — and nothing is written, so exit 4 leaves the state byte-identical."""
    state = load(root, required=False, claim=False)
    if state is None:
        return
    path = questions_path(root, state, None)
    _, questions = parse_questions(path)
    blocking = [q for q in questions if is_pending(q)]
    if command == "approve":
        # The gate's own question is answered by approve/reject themselves.
        blocking = [q for q in blocking if q["kind"] != "G"]
    if not blocking:
        return
    ids = [q["id"] for q in blocking]
    die("QUESTIONS_PENDING — %d unanswered in %s: %s. Answer with 'state.py answer %s' or fill "
        "the [Answer]: lines and run 'state.py questions --sync'. Stage stays at %s."
        % (len(blocking), os.path.relpath(path, root), ", ".join(ids),
           " ".join("%s=<letter>" % i for i in ids), state.get("current_stage")), 4)


def gate_question_text(task_id):
    return "Approve %s for implementation?" % task_id


def request_gate(root, state, gate):
    """stage human_approval is the request: it puts the gate's own question in
    the file, stamps requested_at and says so in the journal. A second request
    refreshes the stamp and reuses the question rather than stacking G2, G3."""
    path = questions_path(root, state, None)
    with question_lock(path):
        lines, questions = parse_questions(path)
        pending_gate = [q for q in questions if q["kind"] == "G" and is_pending(q)]
        if not pending_gate:
            number = max([q["number"] for q in questions if q["kind"] == "G"] or [0]) + 1
            while lines and not lines[-1].strip():
                lines.pop()
            if not any(line.startswith("# Questions") for line in lines):
                lines = (QUESTIONS_HEADER % state["task_id"]).rstrip("\n").split("\n") + lines
            lines.extend(question_block({
                "id": "G%d" % number,
                "question": "%s (gate: %s)" % (gate_question_text(state["task_id"]), gate),
                "options": [("A", "Approve"), ("B", "Reject — answer as `B: <reason>`")],
            }, "human_approval", None))
            write_questions(path, lines)
        _, questions = parse_questions(path)
    state["human_approval"]["requested_at"] = now()
    set_pending(root, state, questions, path)
    emit(root, state, "gate_requested", gate,
         {"gate": gate, "requested_at": state["human_approval"]["requested_at"]})


def gate_requested(root, state):
    """The durable signal is the state's requested_at; the journal line is the
    record of it. Approval must not depend on a journal that is best effort by
    contract (concern 10), so either is enough — and neither can be set by
    anything but `stage human_approval`."""
    if (state.get("human_approval") or {}).get("requested_at"):
        return True
    events, _ = read_journal(root, state["task_id"])
    return any(event.get("event") == "gate_requested" for event in events)


def close_gate(root, state, choice, text, by, via):
    """approve and reject are the gate question's `answer`. Without this its G1
    would stay pending and block the very next command (Risks 3); `answer` still
    refuses a G id, because this is the only route that may close one."""
    path = questions_path(root, state, None)
    with question_lock(path):
        lines, questions = parse_questions(path)
        gates = [q for q in questions if q["kind"] == "G" and is_pending(q)]
        if not gates:
            return None
        gate = gates[-1]
        lines[gate["answer_at"]] = answer_line(choice, text, by, via)
        write_questions(path, lines)
        _, questions = parse_questions(path)
    set_pending(root, state, questions, path)
    return gate["id"]


def refuse_approval(root, state, by):
    gates = [q["id"] for q in parse_questions(questions_path(root, state, None))[1]
             if q["kind"] == "G" and is_pending(q)]
    die("APPROVAL_REFUSED — approval happens outside the agent. Run in your own terminal:\n"
        "  python3 %s --root %s approve --by \"%s\"\n"
        "or set [Answer]: A on %s in %s and tell the session to sync. An unattended run exports "
        "AI_UNATTENDED=1 in the launcher's environment; the journal then records the approval as "
        "unattended."
        % (os.path.abspath(__file__), root, by, gates[-1] if gates else "G1",
           os.path.relpath(questions_path(root, state, None), root)), 5)


def cmd_approve(args, root):
    """The one thing the agent cannot do. A pending Q blocks this at exit 4
    before we get here; what is left is whether the approval comes from outside
    the agent, and whether anyone asked for it (R11)."""
    state = load(root)
    if state["human_approval"].get("granted"):
        # One approval per gate, or the unattended signal in the journal is
        # unreadable. A repeat prints the grant that exists.
        print("already approved by %s at %s (via %s)"
              % (state["human_approval"].get("granted_by"),
                 state["human_approval"].get("granted_at"),
                 state["human_approval"].get("via")))
        return
    if not gate_requested(root, state):
        die("APPROVAL_REFUSED — no gate was requested: run 'state.py stage human_approval' "
            "after presenting the plan.", 5)
    unattended = bool(os.environ.get("AI_UNATTENDED"))
    tty = os.isatty(0)
    if not (tty or unattended):
        refuse_approval(root, state, args.by)
    via = "unattended" if unattended else "terminal"
    close_gate(root, state, "A", args.note, args.by, via)
    state["human_approval"].update({
        "required": True, "granted": True, "granted_by": args.by,
        "granted_at": now(), "via": via, "unattended": unattended,
    })
    emit(root, state, "gate_approved", "granted by %s via %s" % (args.by, via),
         {"by": args.by, "via": via, "unattended": unattended, "tty": tty},
         legacy="human_approval", actor="human")
    write_handoff(root, state, "stage")
    save(root, state)
    print("approved by %s (via %s)%s" % (args.by, via, " — recorded as unattended" if unattended else ""))


def cmd_reject(args, root):
    """Rejection needs no terminal: it cannot let anything through. It is
    recorded with the same honesty as an approval and leaves the stage alone."""
    state = load(root)
    if not gate_requested(root, state):
        die("APPROVAL_REFUSED — no gate was requested: run 'state.py stage human_approval' "
            "after presenting the plan.", 5)
    close_gate(root, state, "B", args.why, args.by, "terminal" if os.isatty(0) else "prose")
    state["human_approval"].update({
        "required": True, "granted": False, "granted_by": None, "granted_at": None,
        "via": None, "unattended": False,
    })
    state["next_action"] = "address the rejection: %s" % one_line(args.why)
    emit(root, state, "gate_rejected", "%s: %s" % (args.by, args.why),
         {"by": args.by, "why": args.why}, actor="human")
    write_handoff(root, state, "stage")
    save(root, state)
    print("rejected by %s; stage stays at %s" % (args.by, state["current_stage"]))


def cmd_done(args, root):
    abandoned = bool(getattr(args, "abandon", False))
    state = load(root)
    state["current_stage"] = "done"
    state["next_action"] = "none — task abandoned" if abandoned else "none — task closed"
    emit(root, state, "task_closed", "abandoned" if abandoned else "",
         {"abandoned": abandoned})
    set_resume_point(state)
    write_handoff(root, state, "stage")
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
    if os.path.exists(handoff_path(root)):
        os.remove(handoff_path(root))
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

    who = os.environ.get("USER") or "unknown"
    p = sub.add_parser("ask"); p.add_argument("question", nargs="?")
    p.add_argument("--option", action="append", default=[]); p.add_argument("--recommend")
    p.add_argument("--context", default=""); p.add_argument("--gate")
    p.add_argument("--batch"); p.add_argument("--topic"); p.add_argument("--by", default="")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("answer"); p.add_argument("assignment", nargs="*")
    p.add_argument("--prose"); p.add_argument("--by", default=who)
    # `file` is not offered: it is what --sync writes, and it is the one route
    # that is recorded as a human's.
    p.add_argument("--via", choices=["picker", "prose"], default="prose")
    p.add_argument("--topic"); p.set_defaults(func=cmd_answer)

    p = sub.add_parser("questions"); p.add_argument("--pending", action="store_true")
    p.add_argument("--sync", action="store_true"); p.add_argument("--topic")
    p.add_argument("--by", default=who)
    p.add_argument("--format", choices=["md", "prose", "json"], default="prose")
    p.set_defaults(func=cmd_questions)

    p = sub.add_parser("handoff")
    p.add_argument("--print", dest="print_it", action="store_true")
    p.add_argument("--reason", choices=["stage", "precompact", "manual", "session-start"],
                   default="manual")
    p.set_defaults(func=cmd_handoff)

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

    p = sub.add_parser("approve"); p.add_argument("--by", required=True)
    p.add_argument("--note", default=""); p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject"); p.add_argument("--by", required=True)
    p.add_argument("--why", required=True); p.set_defaults(func=cmd_reject)

    p = sub.add_parser("done"); p.add_argument("--abandon", action="store_true")
    p.set_defaults(func=cmd_done)
    p = sub.add_parser("archive"); p.set_defaults(func=cmd_archive)
    p = sub.add_parser("close"); p.set_defaults(func=cmd_close)

    global RUNTIME, MUTATING              # pylint: disable=global-statement
    args = parser.parse_args()
    if getattr(args, "topic", None):
        # Topic mode never touches .ai/: it must work where there is none (I11).
        args.func(args, find_docs_root(args.root))
        return
    root = find_root(args.root)
    RUNTIME = detect_runtime(args.runtime, root)
    MUTATING = args.command in MUTATING_COMMANDS
    if args.command in BLOCKING_COMMANDS and not getattr(args, "abandon", False):
        guard_pending(root, args.command)
    args.func(args, root)


if __name__ == "__main__":
    main()
