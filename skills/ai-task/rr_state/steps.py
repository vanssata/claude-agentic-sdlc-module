"""steps: the `steps`, `step-done` and `batch` commands -- a multi-step task's steps and the batch loop's switch.

shell: cmd_step_done_v7, cmd_steps, cmd_batch
"""
# pylint: disable=unused-argument
# (uniform cli dispatch: every cmd_* takes rt last, whether it uses it or not)
import json
import shlex

from rr_state import dialog, fs, handoff, journal, report, task
from rr_state import policy as rr_policy   # cmd_batch binds a local `policy`
from rr_state import runtime as rr_runtime

# sensors.py sits beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None


def cmd_step_done_v7(args, root, rt=rr_runtime.Runtime()):
    """A multi-step task's step is done when its diff stays inside the task."""
    state = task.load_v7(root, rt=rt)
    steps = state["steps"]
    if not steps:
        fs.die("step-done is for a multi-step guarded or full task; this one is one scope — verify, then close")
    step = next((s for s in steps if s["id"] == args.step_id), None)
    if step is None:
        fs.die("no step %s (have: %s)" % (args.step_id, ", ".join(s["id"] for s in steps)))
    if step["status"] == "done":
        print("step %s already done" % step["id"])
        return
    tree = fs.current_tree(root)
    diff = fs.safe_sensor(sensors.diff_files, root, step.get("tree_before") or state["diff"].get("base_tree"), tree)
    outside = [d["path"] for d in diff or [] if not sensors.scope_any(d["path"], task.task_files(state))]
    if outside:
        fs.die("SCOPE_CHANGE_REQUIRED — step %s changed %s, outside the task's files. Widen the task in "
            "place: state.py start --amend --files \"%s\" --why \"…\""
            % (step["id"], ", ".join(outside), ",".join("+" + p for p in outside)), 6)
    # In a wave the diff since the step began holds other steps' work too. The
    # journal says which changed paths were this step's own (its files and
    # tests) and which were not, so a step that strayed into another's files is
    # visible; `unready` names dependencies it was recorded ahead of.
    own_scope = list(step.get("files") or []) + list(step.get("tests") or [])
    own = [d["path"] for d in diff or [] if sensors.scope_any(d["path"], own_scope)]
    others = [d["path"] for d in diff or [] if d["path"] not in own]
    unready = [dep for dep in step.get("after") or [] if any(s["id"] == dep and s["status"] != "done" for s in steps)]
    step.update(status="done", tree_after=tree)
    journal.emit(root, state, "step_done", "%s: %d files changed" % (step["id"], len(diff or [])),
         {"step_id": step["id"], "files": len(diff or []), "own": own, "others": others, "unready": unready},
         legacy="step_completed", rt=rt)
    # The first pending step whose dependencies are done — the first pending one
    # when no step has `after`, as before the batch loop.
    following = next((s for s in task.ready_steps(state) if s["status"] == "pending"), None)
    if following:
        following.update(status="in_progress", tree_before=tree)
        journal.emit(root, state, "step_started", following["id"], {"step_id": following["id"], "kind": "step"}, rt=rt)
    task.save(root, state)
    report.write_task_md(root, state)
    open_steps = [s["id"] for s in steps if s["status"] != "done"]
    if unready:
        print("note: %s was done before %s, which it is after" % (step["id"], ", ".join(unready)))
    if others and rr_policy.batch_on(state):
        print("note: the diff also holds %d file(s) outside this step's own — %s"
              % (len(others), ", ".join(others[:4]) + (" …" if len(others) > 4 else "")))
    print("step %s done%s" % (step["id"], "; next: %s" % following["id"] if following
                              else "; %d still open: %s" % (len(open_steps), ", ".join(open_steps)) if open_steps
                              else "; all steps done"))


def cmd_steps(args, root, rt=rr_runtime.Runtime()):
    """Read-only: the steps, their status and `after`; --ready prints the next
    wave (R3), nothing when there is none."""
    state = task.load_v7(root, rt=rt)
    steps = state.get("steps") or []
    ready = [s["id"] for s in task.ready_steps(state)]
    if args.json:
        print(json.dumps({"task_id": state["task_id"], "batch": rr_policy.batch_on(state), "ready": ready, "steps": steps,
                          "batch_policy": rr_policy.batch_policy(rr_policy.weight_policy(root))}, indent=2, ensure_ascii=False))
        return
    if args.ready:
        for step_id in ready:
            print(step_id)
        return
    if not steps:
        print("steps: one scope — no plan-file steps")
        return
    for s in steps:
        print("%s · %s · after %s · %s" % (s["id"], s["status"], ", ".join(s.get("after") or []) or "-",
                                            "ready" if s["id"] in ready else "waiting" if s["status"] != "done" else "-"))


def cmd_batch(args, root, rt=rr_runtime.Runtime()):
    """The batch loop's switch during a task (R9). `off` raises the rigor — the
    standard budgets from here, counting what was spent — and is anyone's with
    --by and --why. `on` lowers it, so it takes the human route or exits 5."""
    state = task.load_v7(root, rt=rt)
    want = args.action == "on"
    if not args.by:
        fs.die("batch %s needs --by \"<who>\"" % args.action)
    if want == rr_policy.batch_on(state):
        print("batch is already %s" % args.action)
        return
    via = None
    if want:
        via, why = dialog.human_route(root, rt=rt)
        if via is None:
            fs.die("APPROVAL_REFUSED — turning the batch loop on during a task lowers the rigor, so it is the "
                "human's. In their own terminal:\n  python3 %s --root %s batch on --by \"<name>\"\nRefused "
                "because %s." % (shlex.quote(fs.ENTRY), shlex.quote(root), why), 5)
    elif not (args.why or "").strip():
        fs.die("batch off needs --why \"<why the standard loop from here>\"")
    policy = rr_policy.weight_policy(root)
    if want:
        rr_policy.batch_policy(policy, strict=True)          # a malformed section is refused before the loop starts
    state["batch"] = {"on": want, "by": args.by, "why": args.why or None, "since": fs.now()}
    if state.get("stage") in ("build", "verify", "review"):
        # At the gate (stage ship) the next action is the human's and stays so.
        state["next_action"] = rr_policy.review_next_action(state)
    journal.emit(root, state, "batch_set", "%s by %s%s" % (args.action, args.by, " via %s" % via if via else ""),
         {"on": want, "by": args.by, "why": args.why or None, "via": via,
          "review_passes": state["review"]["passes"], "suite_runs": state["verify"]["suite_runs"]},
         actor="human" if via == "terminal" else "agent", rt=rt)
    handoff.set_resume_point(state, rt=rt)
    handoff.write_handoff(root, state, "batch", rt=rt)
    task.save(root, state)
    report.write_task_md(root, state)
    print("batch %s by %s · review %d/%d · suite %d/%d" % (
        args.action, args.by, state["review"]["passes"], rr_policy.budget(policy, state, "review_rounds_max")[0],
        state["verify"]["suite_runs"], rr_policy.budget(policy, state, "max_suite_runs")[0]))
    print("next: %s" % state["next_action"])
