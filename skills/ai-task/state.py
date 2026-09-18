#!/usr/bin/env python3
"""Task state for /ai-task — the small, machine-readable record of one task.

Why a file and not the conversation: a conversation is expensive to re-read and
impossible for a hook to consult. This file is what ai-scope-guard enforces
against, what /ai-status reports, and what lets a task survive a /clear or a
crash. It holds facts, never transcripts.

Everything is stdlib. Writes are atomic (temp file + os.replace), so a hook that
reads the file while a stage is being recorded never sees half a document.

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
  state.py set    <field> <value>        # test_status, review_status, security_status, next_action
  state.py risks  --add TEXT | --clear
  state.py approve --by NAME
  state.py done
  state.py archive                       # move current.json into .ai/reports/<task_id>/state.json
  state.py close                         # done + archive in one call
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

STAGES = [
    "discovery", "context", "impact_analysis", "risk_classification",
    "plan", "plan_review", "implementation", "test", "adversarial_review",
    "security_review", "release_report", "human_approval", "done",
]
TIERS = ["T0", "T1", "T2", "T3", "T4", "T5"]
WORKFLOWS = ["feature", "bugfix", "refactoring", "hotfix", "investigation"]
TEST_STATUS = ["not_run", "passing", "existing_failure", "new_regression", "env_failure", "unknown"]
REVIEW_STATUS = ["not_started", "in_progress", "blockers_open", "passed"]
SECURITY_STATUS = ["not_applicable", "not_started", "in_progress", "passed", "failed"]

SETTABLE = {
    "test_status": TEST_STATUS,
    "review_status": REVIEW_STATUS,
    "security_status": SECURITY_STATUS,
    "next_action": None,
    "context_summary_ref": None,
    "goal": None,
}


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def load(root, required=True):
    path = state_path(root)
    if not os.path.exists(path):
        if required:
            die("no task in flight (%s does not exist). Start one with state.py init." % path)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        # Loud on purpose: a corrupt state file must never be silently replaced,
        # because ai-scope-guard's boundaries are derived from it.
        die("%s is unreadable (%s). Inspect it by hand; do not delete it blindly." % (path, exc))


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
    existing = load(root, required=False)
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
        "review_status": "not_started",
        "security_status": "not_started",
        "open_risks": [],
        "next_action": "run DISCOVERY",
        "human_approval": {"required": True, "granted": False, "granted_by": None, "granted_at": None},
        "created_at": now(),
        "updated_at": now(),
        "history": [],
    }
    record(state, "task_started", "%s (%s)" % (args.goal, args.workflow))
    os.makedirs(os.path.join(root, ".ai", "reports", task_id), exist_ok=True)
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


def cmd_stage(args, root):
    if args.stage not in STAGES:
        die("stage must be one of: %s" % ", ".join(STAGES))
    state = load(root)
    previous = state["current_stage"]
    state["current_stage"] = args.stage
    record(state, "stage", "%s -> %s%s" % (previous, args.stage, ": " + args.note if args.note else ""))
    save(root, state)
    print("%s -> %s" % (previous, args.stage))


def cmd_risk(args, root):
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    state["risk_tier"] = args.tier
    record(state, "risk_classified", "%s%s" % (args.tier, ": " + args.note if args.note else ""))
    save(root, state)
    print(args.tier)


def cmd_triage(args, root):
    """The four inline stages of a small task, recorded in one call so the audit
    trail still shows each of them without four round trips."""
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    previous = state["current_stage"]
    for stage in ("discovery", "context", "impact_analysis", "risk_classification"):
        record(state, "stage", "%s -> %s: inline" % (previous, stage))
        previous = stage
    state["current_stage"] = "risk_classification"
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    record(state, "risk_classified", "%s%s" % (args.tier, ": " + args.note if args.note else ""))
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
    record(state, "plan_approved", "%d steps, %s" % (len(steps), args.ref))
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
    record(state, "step_started", "%s: %s" % (args.step_id, match[0]["description"]))
    save(root, state)
    print("step %s: %s" % (args.step_id, match[0]["description"]))
    print("allowed: %s" % ", ".join(match[0]["allowed_files"]))
    if match[0]["forbidden_files"]:
        print("forbidden: %s" % ", ".join(match[0]["forbidden_files"]))


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
    record(state, "step_completed", args.step_id)
    save(root, state)
    remaining = [s["step_id"] for s in steps if s["status"] != "done"]
    print("step %s done; remaining: %s" % (args.step_id, ", ".join(remaining) or "none"))


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
    for stage in ("discovery", "context", "impact_analysis", "risk_classification"):
        record(state, "stage", "%s -> %s: inline" % (previous, stage))
        previous = stage
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    record(state, "risk_classified", "%s%s" % (args.tier, ": " + args.note if args.note else ""))
    step = {
        "step_id": "1", "description": args.goal, "allowed_files": files,
        "forbidden_files": [], "forbidden_reason": "not part of this task",
        "required_tests": [], "status": "in_progress",
    }
    state["approved_plan"] = {"ref": "inline", "current_step_id": "1", "steps": [step]}
    record(state, "plan_approved", "1 step, inline (quick)")
    state["current_stage"] = "implementation"
    record(state, "stage", "risk_classification -> plan -> implementation: quick")
    record(state, "step_started", "1: %s" % args.goal)
    state["next_action"] = "implement, then run the verification command once"
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
    record(state, "remediation", "%s: %s" % (step_id, step["description"]))
    record(state, "step_started", "%s: %s" % (step_id, step["description"]))
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
    state[args.field] = args.value
    record(state, "set", "%s = %s" % (args.field, args.value))
    save(root, state)
    print("%s = %s" % (args.field, args.value))


def cmd_risks(args, root):
    state = load(root)
    if args.clear:
        state["open_risks"] = []
        record(state, "risks_cleared", "")
    elif args.add:
        state["open_risks"].append(args.add)
        record(state, "risk_added", args.add)
    else:
        die("pass --add TEXT or --clear")
    save(root, state)
    print("%d open risk(s)" % len(state["open_risks"]))


def cmd_modules(args, root):
    state = load(root)
    for module in args.module:
        if module not in state["affected_modules"]:
            state["affected_modules"].append(module)
    record(state, "modules", ", ".join(args.module))
    save(root, state)
    print(", ".join(state["affected_modules"]))


def cmd_approve(args, root):
    state = load(root)
    state["human_approval"] = {
        "required": True, "granted": True,
        "granted_by": args.by, "granted_at": now(),
    }
    record(state, "human_approval", "granted by %s" % args.by)
    save(root, state)
    print("approved by %s" % args.by)


def cmd_done(_args, root):
    state = load(root)
    state["current_stage"] = "done"
    state["next_action"] = "none — task closed"
    record(state, "task_closed", "")
    save(root, state)
    print("%s closed" % state["task_id"])


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

    p = sub.add_parser("approve"); p.add_argument("--by", required=True); p.set_defaults(func=cmd_approve)

    p = sub.add_parser("done"); p.set_defaults(func=cmd_done)
    p = sub.add_parser("archive"); p.set_defaults(func=cmd_archive)
    p = sub.add_parser("close"); p.set_defaults(func=cmd_close)

    args = parser.parse_args()
    root = find_root(args.root)
    args.func(args, root)


if __name__ == "__main__":
    main()
