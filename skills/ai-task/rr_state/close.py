"""close: the `close` command -- what the mode table still owes, the gate, and the archive of a closed task.

core: close_owed
shell: cmd_close_v7, archive_v7, memory_after_close
"""
import contextlib
import json
import os

from rr_state import dialog, fs, gate, handoff, journal, report, task
from rr_state import policy as rr_policy   # close_owed and cmd_close_v7 bind a local `policy`
from rr_state import runtime as rr_runtime

# sensors.py sits beside state.py; the entry puts that directory on sys.path.
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None


def close_owed(state, facts, tree, policy):
    """What the mode table still asks for, in order (D7), as (kind, text) with
    kind "review" or "verify"; empty means close."""
    review, mode = state["review"], state["mode"]
    reviewed = review["passes"] > 0 and review["status"] != "blockers_open"
    on_tree = bool(reviewed and tree and review.get("tree") == tree)
    red = [why for ok, why in (facts["a"], facts["b"]) if not ok]
    owed = []
    if mode == "light":
        if red and not on_tree:
            owed.append(("review", "a review, because %s — or make the facts green ('verify --scope all'; "
                                   "'start --amend' for a file the task needs)" % "; ".join(red)))
        return owed
    if review["status"] == "blockers_open":
        owed.append(("review", "the blockers fixed, 'verify --scope all --after-fix \"…\"', %s"
                               % ("a full review pass again" if rr_policy.batch_on(state) else "one scoped re-review")))
    elif not reviewed:
        owed.append(("review", "one review verdict (%s mode: %s)"
                               % (mode, rr_policy.mode_setting(policy, mode, "reviewer", "BALANCED"))))
    elif red and not on_tree:
        owed.append(("review", "a fresh 'verify --scope all' or a review of this tree, because %s"
                               % "; ".join(red)))
    e2e = state["verify"].get("e2e")
    if e2e not in ("passing", "not_applicable"):
        owed.append(("verify", "e2e green, or 'verify --scope all --e2e not-applicable \"<why>\"' (e2e is %s)"
                               % e2e))
    elif not tree or state["verify"].get("e2e_tree") != tree:
        owed.append(("verify", "e2e on this tree: 'verify --scope e2e'%s (it was %s on %s)"
                               % (" or 'verify --scope e2e --e2e not-applicable \"<why>\"'"
                                  if e2e == "not_applicable" else "",
                                  e2e, (state["verify"].get("e2e_tree") or "?")[:9])))
    return owed


def cmd_close_v7(args, root, rt=rr_runtime.Runtime()):
    """Two facts, the mode table, the gate, the archive; exits 2 naming what is owed."""
    state = task.load_v7(root, rt=rt)
    if args.abandon:
        archive_v7(root, state, fs.current_tree(root), "abandoned", rt=rt)
        memory_after_close(root, state["task_id"])
        return
    policy = rr_policy.weight_policy(root)
    tree = fs.current_tree(root)
    if state["human_approval"].get("rejected_at"):
        # A rejection is answered by changing the work, not by asking again: on the
        # tree the human rejected, close refuses; on a changed one it asks anew.
        if (state.get("gate") or {}).get("tree") == tree:
            fs.die("APPROVAL_REFUSED — rejected at %s and nothing changed since. Address the rejection, "
                "'verify --scope all', then close again; or 'state.py close --abandon'."
                % state["human_approval"]["rejected_at"], 5)
        state["human_approval"]["rejected_at"] = None
    for step in state["steps"]:
        if step.get("status") == "in_progress":
            step.update(status="done", tree_after=tree)
            journal.emit(root, state, "step_done", "%s (finished by close)" % step["id"],
                 {"step_id": step["id"], "by": "close"}, legacy="step_completed", rt=rt)
    rr_policy.rescore_v7(root, state, policy, "close", rt=rt)
    facts = report.two_facts(root, state, tree)
    state["facts"] = {"a": list(facts["a"]), "b": list(facts["b"]), "tree": tree, "at": fs.now()}
    if facts["documents"]:
        state["facts"]["documents"] = facts["documents"]
    owed = close_owed(state, facts, tree, policy)
    if owed:
        state["next_action"] = owed[0][1]
        handoff.set_resume_point(state, rt=rt)
        handoff.write_handoff(root, state, "close", rt=rt)
        task.save(root, state)
        report.write_task_md(root, state)
        fs.die("%s required (%s mode) — %s. To drop the task instead: 'state.py close --abandon'."
            % ("review" if any(k == "review" for k, _ in owed) else "verify", state["mode"],
               " · ".join(text for _, text in owed)), 2)
    if state["mode"] in ("full", "full_irreversible") and not gate.gate_approved_for(state, tree):
        if state["human_approval"].get("granted") and (state.get("gate") or {}).get("tree") == tree:
            print("the approval on record does not cover this task: full_irreversible needs approve "
                  "--confirm naming %s — asking again" % " and ".join(state["weight"].get("operations") or
                                                                      ["the operation"]))
        gate.request_gate(root, state, "human_approval", rt=rt)
        state["gate"] = {"requested_at": state["human_approval"]["requested_at"],
                         "gate_id": state["human_approval"]["gate_id"], "tree": tree,
                         "approved_by": None, "approved_at": None, "approved_tree": None, "via": None,
                         "confirm": None, "operations": list(state["weight"].get("operations") or [])}
        state["stage"] = "ship"
        state["next_action"] = "the human approves in their own terminal, then 'state.py close' again"
        handoff.set_resume_point(state, rt=rt)
        handoff.write_handoff(root, state, "close", rt=rt)
        task.save(root, state)
        report.write_task_md(root, state)
        print("%s %s ready for approval: %s" % (state["task_id"], state["mode"], state.get("goal")))
        print("facts: (a) %s · (b) %s" % (facts["a"][1], facts["b"][1]))
        decision = dialog.offer_approval(root, state, facts, rt=rt) if state["mode"] == "full" else None
        if decision:
            state["next_action"] = "the human picks in the dialog (%s), then 'state.py close' again" % decision["id"]
            handoff.set_resume_point(state, rt=rt)
            handoff.write_handoff(root, state, "close", rt=rt)
            task.save(root, state)
            return
        print("approve in your own terminal, then run close again:\n  %s" % dialog.approve_command(root, state))
        return
    if state.get("gate") and not state["gate"].get("approved_by"):
        # The questions-file route grants through human_approval alone.
        approval = state["human_approval"]
        state["gate"].update(approved_by=approval.get("granted_by"), approved_at=approval.get("granted_at"),
                             via=approval.get("via"), approved_tree=state["gate"].get("tree"))
    archive_v7(root, state, tree, "closed", facts, rt=rt)
    memory_after_close(root, state["task_id"])


def archive_v7(root, state, tree, result, facts=None, rt=rr_runtime.Runtime()):
    """§Changes and §Verdict into task.md, the state into .ai/state/logs/<task>/,
    and nothing else under reports/ (D4, R8)."""
    base = state["diff"].get("base_tree")
    stats = {f["path"]: f for f in (fs.safe_sensor(sensors.numstat, root, base, tree) or [])} if base and tree else {}
    names = (facts or {}).get("diff") or fs.safe_sensor(sensors.diff_files, root, base, tree) or []
    state["changes"] = [{"path": d["path"], "status": d["status"],
                         "added": (stats.get(d["path"]) or {}).get("added", 0),
                         "deleted": (stats.get(d["path"]) or {}).get("deleted", 0),
                         "binary": (stats.get(d["path"]) or {}).get("binary", False)} for d in names]
    state["stage"] = "done"
    state["current_stage"] = "done"
    state["result"] = result
    state["closed_at"] = fs.now()
    state["next_action"] = "none — task %s" % result
    journal.emit(root, state, "task_closed", "abandoned" if result == "abandoned" else "",
         {"abandoned": result == "abandoned", "mode": state["mode"], "w": state["weight"].get("w")}, rt=rt)
    report.write_task_md(root, state)
    fs.ensure_logs(root, state["task_id"])
    target = os.path.join(fs.logs_dir(root, state["task_id"]), "state.json")
    state["updated_at"] = fs.now()
    tmp = "%s.%d.tmp" % (target, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, target)
    with contextlib.suppress(OSError):
        os.remove(fs.handoff_path(root))
    fs.remove_state(root)
    print("%s %s (%s): %s" % (state["task_id"], result, state["mode"],
                              os.path.relpath(fs.task_md_path(root, state), root)))
    print("state: %s" % os.path.relpath(target, root))


def memory_after_close(root, task_id):
    """§D5: packages mode exports the closed task. Files mode (no memory.json)
    imports nothing and prints nothing (R15)."""
    if not os.path.exists(os.path.join(root, ".ai", "policies", "memory.json")):
        return
    try:
        import memory_sync                # pylint: disable=import-outside-toplevel
    except ImportError:
        return
    memory_sync.after_close(root, task_id)
