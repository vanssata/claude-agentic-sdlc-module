#!/usr/bin/env python3
"""/status — where the task in this directory stands, in at most twenty lines.

  status.py [--root DIR] [--cost]

Read-only and model-free. A schema-7 task is described by `state.py status`;
for any other task, and whenever that call fails, it reads the files directly —
.ai/state/state.json (or the legacy current.json), the task's events.jsonl, .ai/policies/weight.json (else the shipped table)
and .ai/VERSION — so it answers in a project whose state.py is older, newer or
broken. The root is found the way the guards find it (find_ai_root in
hooks/lib/ai-hook-common.sh): the nearest ancestor holding .ai/, not stopping at
a git root, so a .ai/ inherited from a parent directory shows up here.

--cost adds the task's token report from usage-report.py.
"""
import argparse
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.dirname(HERE)


def find_ai_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def state_file(root):
    """R34: state.json, or the legacy current.json for one version."""
    path = os.path.join(root, ".ai", "state", "state.json")
    return path if os.path.isfile(path) else os.path.join(root, ".ai", "state", "current.json")


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def last_event(root, task_id):
    line = ""
    try:
        with open(os.path.join(root, ".ai", "reports", task_id, "events.jsonl"),
                  encoding="utf-8") as fh:
            for raw in fh:
                if raw.strip():
                    line = raw
        event = json.loads(line) if line else {}
    except (OSError, ValueError):
        return "none"
    if not isinstance(event, dict) or not event:
        return "none"
    return " ".join(x for x in (one_line(event.get("ts")), one_line(event.get("event")),
                                one_line(event.get("detail"), 80)) if x)


def schema_line(root):
    try:
        with open(os.path.join(root, ".ai", "VERSION"), encoding="utf-8") as fh:
            project = fh.read().strip() or "0"
    except OSError:
        project = "0"
    # The plugin's schema is its newest migration, as update.py counts it.
    try:
        names = os.listdir(os.path.join(SKILLS, "project-update", "migrations"))
    except OSError:
        names = []
    numbers = [int(name[:4]) for name in names if re.match(r"\d{4}_", name)]
    plugin = str(max(numbers)) if numbers else "?"
    behind = project.isdigit() and plugin.isdigit() and int(project) < int(plugin)
    return "schema: project %s · plugin %s%s" % (project, plugin, " — behind: run /rr-setup --update" if behind else "")


def one_line(value, limit=160):
    """Free text from the state (a goal, a risk, an event detail) on one line:
    a multi-line value must not break the twenty-line bound."""
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit - 1] + "…"


def short(items, limit=4):
    items = [one_line(i, 80) for i in items or []]
    more = " (+%d more)" % (len(items) - limit) if len(items) > limit else ""
    return ", ".join(items[:limit]) + more if items else "none"


def budgets(root, state):
    """(max_suite_runs, review_rounds_max) as state.py's budget() enforces them:
    weight.json's batch section while the batch loop is on, else tests.max_suite_runs
    and review_rounds_max. A project without weight.json runs the shipped table."""
    policy = read_json(os.path.join(root, ".ai", "policies", "weight.json")) \
        or read_json(os.path.join(SKILLS, "ai-init", "templates", ".ai", "policies", "weight.json"))

    def whole(value, default):
        return value if isinstance(value, int) and not isinstance(value, bool) and value >= 1 else default

    if (state.get("batch") or {}).get("on"):
        section = policy.get("batch") if isinstance(policy.get("batch"), dict) else {}
        return whole(section.get("max_suite_runs"), 8), whole(section.get("review_rounds_max"), 3)
    tests = policy.get("tests") if isinstance(policy.get("tests"), dict) else {}
    return tests.get("max_suite_runs", 2), policy.get("review_rounds_max", 2)


def counter(state, section, key, legacy):
    """A schema-7 counter (verify.suite_runs, review.passes), else the legacy one
    (tests.suite_runs, reviews); 0 when neither is a number."""
    new = state.get(section)
    if isinstance(new, dict) and isinstance(new.get(key), int):
        return new[key]
    old = state.get(legacy)
    old = old.get(key) if isinstance(old, dict) else old
    return old if isinstance(old, int) else 0


def report(root):
    lines = ["root: %s" % root]
    state = read_json(state_file(root))
    if not state.get("task_id"):
        return lines + ["task: none — no task in flight", schema_line(root)], None
    max_runs, max_rounds = budgets(root, state)
    plan = state.get("approved_plan") or {}
    steps = plan.get("steps") or []
    current = plan.get("current_step_id")
    step = next((s for s in steps if s.get("step_id") == current), None)
    done = len([s for s in steps if s.get("status") == "done"])
    questions = (state.get("questions") or {}).get("pending") or []
    risks = state.get("open_risks") or []
    approval = state.get("human_approval") or {}
    lines += [
        "task: %s — %s" % (state["task_id"], one_line(state.get("goal"))),
        "tier: %s · workflow %s" % (state.get("risk_tier") or state.get("mode") or "?",
                                    state.get("workflow") or "?"),
        "stage: %s · next: %s" % (state.get("current_stage") or "?", one_line(state.get("next_action")) or "?"),
        ("step: %s (%d of %d done) — files: %s"
         % (current, done, len(steps), short(step.get("allowed_files"))) if step
         else "step: none current (%d of %d done)" % (done, len(steps))),
        "verify: tests %s · suite runs %s/%s · e2e %s"
        % (state.get("test_status") or "?",
           counter(state, "verify", "suite_runs", "tests"),
           max_runs, state.get("e2e_status") or "?"),
        "review: %s (%s of %s) · security %s"
        % (state.get("review_status") or "?", counter(state, "review", "passes", "reviews"),
           max_rounds, state.get("security_status") or "?"),
        "approval: %s" % ("granted by %s" % approval.get("granted_by") if approval.get("granted")
                          else "requested, waiting for the human" if approval.get("requested_at")
                          else "not requested"),
        "questions: %d pending%s" % (len(questions), " — %s" % short(
            [q.get("id", "?") if isinstance(q, dict) else q for q in questions]) if questions else ""),
        "risks: %d open%s" % (len(risks), " — %s" % one_line(risks[0], 100) if risks else ""),
        schema_line(root),
        "last event: %s" % last_event(root, state["task_id"]),
    ]
    return lines, state["task_id"]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Where the task in this directory stands.")
    parser.add_argument("--root", default=os.getcwd(), help="start the .ai/ walk here (default: cwd)")
    parser.add_argument("--cost", action="store_true", help="add the task's usage report")
    args = parser.parse_args(argv)
    root = find_ai_root(args.root)
    if not root:
        print("root: none — no .ai/ in %s or above it; run /rr-setup first" % os.path.abspath(args.root))
        return 1
    lines, task_id = None, None
    state = read_json(state_file(root))
    if state.get("schema") == 7:
        # A schema-7 task is state.py's to describe; this file's own read stays for
        # an older task, and for an install whose state.py cannot answer.
        done = subprocess.run([sys.executable, "-I", os.path.join(SKILLS, "ai-task", "state.py"),
                               "--root", root, "status"], capture_output=True, text=True, check=False)
        if done.returncode == 0 and done.stdout.strip():
            lines, task_id = done.stdout.rstrip("\n").split("\n")[:20], state.get("task_id")
    if lines is None:
        lines, task_id = report(root)
    print("\n".join(lines))
    if args.cost and task_id:
        sys.stdout.flush()
        subprocess.run([sys.executable, "-I", os.path.join(SKILLS, "usage-report", "usage-report.py"),
                        "--task", task_id, "--project", root], check=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
