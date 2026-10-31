"""gate_cmd: the approval gate's commands -- approve (the human's grant), reject, and approve with the tree check and the irreversible confirm.

shell: cmd_approve, cmd_reject, cmd_approve_v7
"""
import os
import sys

from rr_state import dialog, fs, handoff, journal, report, task
from rr_state import gate as rr_gate      # cmd_approve_v7 binds a local `gate`
from rr_state import runtime as rr_runtime


def cmd_approve(args, root, rt=rr_runtime.Runtime()):
    """The one thing the agent cannot do. A pending Q blocks this at exit 4
    before we get here; what is left is whether a gate is open and whether the
    approval comes from outside the agent (R11)."""
    state = task.load(root, rt=rt)
    gate_id = task.open_gate(state)
    if gate_id is None:
        if state["human_approval"].get("granted"):
            # The gate that was open has been granted and consumed. One approval
            # per gate, or the unattended signal in the journal is unreadable.
            print("already approved by %s at %s (via %s)"
                  % (state["human_approval"].get("granted_by"),
                     state["human_approval"].get("granted_at"),
                     state["human_approval"].get("via")))
            return
        fs.die("APPROVAL_REFUSED — no gate was requested: 'state.py close' requests it for a full-mode "
            "task.", 5)
    tty = os.isatty(0)
    # A terminal is the stronger evidence: a launcher variable left in a human's
    # shell must not downgrade an approval they gave in person.
    # full_irreversible never takes the dialog: its --confirm is the human's own
    # words, so the terminal command is offered as before (R36.10).
    via, why = dialog.human_route(root, allow_dialog=state.get("mode") != "full_irreversible", rt=rt)
    if via is None:
        dialog.refuse_approval(root, state, gate_id, args.by, why)
    task.claim_runtime(root, state, rt=rt)
    state["human_approval"].update({
        "required": True, "granted": True, "granted_by": args.by, "granted_at": fs.now(),
        "requested_at": None, "gate_id": None, "requested_session": None,
        "rejected_at": None, "via": via, "unattended": via == "unattended",
    })
    journal.record(state, "human_approval", "granted by %s via %s" % (args.by, via))
    handoff.write_handoff(root, state, "stage", rt=rt)
    task.save(root, state)                     # durable first: the rest is derived
    journal.append_journal(root, state["task_id"], journal.journal_line(
        state["task_id"], "gate_approved", "human" if via == "terminal" else "agent",
        state.get("current_stage"), "granted by %s via %s" % (args.by, via),
        dict({"by": args.by, "gate_id": gate_id, "via": via,
              "unattended": via == "unattended", "tty": tty}, **dialog.pick_data(dialog.DIALOG_PICK[0])), runtime=rt.name))
    if not rr_gate.close_gate(root, state, gate_id, "A", args.note, args.by, via):
        print("state.py: %s is not in %s — the gate was granted, answer it by hand"
              % (gate_id, os.path.relpath(fs.questions_path(root, state, None), root)),
              file=sys.stderr)
    task.save(root, state)
    dialog.retire_approvals(root, state["task_id"], "approved")
    print("approved by %s (via %s)%s" % (args.by, via, " — recorded as unattended"
                                         if via == "unattended" else ""))


def cmd_reject(args, root, rt=rr_runtime.Runtime()):
    """Rejection needs no terminal: it cannot let anything through. It needs an
    open gate, though — otherwise it would erase a grant it never opened."""
    state = task.load(root, rt=rt)
    gate_id = task.open_gate(state)
    if gate_id is None:
        fs.die("APPROVAL_REFUSED — no gate was requested: 'state.py close' requests it for a full-mode "
            "task.", 5)
    # A rejection needs no route, but a picked reject spends its pick, so the
    # approval decision settles.
    pick = dialog.dialog_pick(root, rt=rt)
    task.claim_runtime(root, state, rt=rt)
    state["human_approval"].update({
        "required": True, "granted": False, "granted_by": None, "granted_at": None,
        "requested_at": None, "gate_id": None, "via": None, "unattended": False,
    })
    state["human_approval"]["rejected_at"] = fs.now()
    state["next_action"] = "address the rejection: %s" % fs.one_line(args.why)
    journal.record(state, "gate_rejected", "%s: %s" % (args.by, args.why))
    handoff.write_handoff(root, state, "stage", rt=rt)
    task.save(root, state)
    journal.append_journal(root, state["task_id"], journal.journal_line(
        state["task_id"], "gate_rejected", "human", state.get("current_stage"),
        "%s: %s" % (args.by, args.why),
        dict({"by": args.by, "gate_id": gate_id, "why": args.why}, **dialog.pick_data(pick)), runtime=rt.name))
    rr_gate.close_gate(root, state, gate_id, "B", args.why, args.by,
               "dialog" if pick else "terminal" if os.isatty(0) else "prose")
    task.save(root, state)
    dialog.retire_approvals(root, state["task_id"], "declined")
    print("rejected by %s; stage stays at %s" % (args.by, state["current_stage"]))


# ---------------------------------------------- the dialog (R36, step 7c)
#


def cmd_approve_v7(args, root, rt=rr_runtime.Runtime()):
    """approve, plus the gate's tree and, for full_irreversible, the operation
    the human names (--confirm). The grant itself is cmd_approve's, unchanged."""
    state = task.load_v7(root, rt=rt)
    ops = state["weight"].get("operations") or []
    confirm = (args.confirm or "").strip()
    gate = state.get("gate") or {}
    if task.open_gate(state):
        tree = fs.current_tree(root)
        if gate.get("tree") != tree:
            # The work changed after close put it up: approving now would sign
            # a tree nobody presented.
            fs.die("APPROVAL_REFUSED — the tree changed after close asked for this approval (%s, now %s). "
                "Reject it ('reject --by \"<name>\" --why \"the tree changed\"'); the next close asks "
                "again for the tree as it is." % ((gate.get("tree") or "?")[:9], (tree or "?")[:9]), 5)
        if state["mode"] == "full_irreversible" and not rr_gate.confirm_names(confirm, ops):
            fs.die("APPROVAL_REFUSED — full_irreversible needs --confirm \"<what it does>\" naming %s"
                % (" and ".join(ops) or "the irreversible operation"), 5)
    cmd_approve(args, root, rt=rt)
    state = task.load(root, claim=False, rt=rt)
    gate = state.get("gate") or {}
    if state["human_approval"].get("granted") and gate and not gate.get("approved_by"):
        gate.update(approved_by=args.by, approved_at=state["human_approval"].get("granted_at"),
                    via=state["human_approval"].get("via"), confirm=confirm or None,
                    approved_tree=gate.get("tree"))
        state["gate"] = gate
        task.save(root, state)
        report.write_task_md(root, state)
