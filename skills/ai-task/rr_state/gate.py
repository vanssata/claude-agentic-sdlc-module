"""gate: the approval gate — the pending-question guard, the gate request and its close, and what close accepts as an approval.

core: gate_question_text, confirm_names, gate_approved_for
shell: guard_pending, request_gate, close_gate
"""
import os
import re

from rr_state import fs
from rr_state import journal
from rr_state import locks
from rr_state import questions as questions_mod   # the bodies keep a local `questions`; the module is aliased
from rr_state import runtime as rr_runtime
from rr_state import task


def guard_pending(root, command, rt=rr_runtime.Runtime()):
    """The file is re-parsed on every stage-moving command — questions.pending is
    only a cache — and nothing is written, so exit 4 leaves the state byte-identical."""
    state = task.load(root, required=False, claim=False, rt=rt)
    if state is None:
        return
    path = fs.questions_path(root, state, None)
    _, questions = questions_mod.parse_questions(path)
    # For a question the file is the truth. For the gate it is not: an
    # authorization is closed by approve or reject, so a hand-filled [Answer]: A
    # must not unblock the pipeline on its own — the state says when the gate is
    # done, and until then its question keeps blocking.
    gate_id = task.open_gate(state)
    blocking = [q for q in questions if q["kind"] != "G" and questions_mod.is_pending(q)]
    if command != "approve" and command != "reject" and gate_id:
        blocking += [q for q in questions if q["id"] == gate_id]
    if not blocking:
        return
    ids = [q["id"] for q in blocking]
    if any(q["kind"] == "G" for q in blocking):
        # `answer` refuses a G id, so the general text would send the human to a
        # command that cannot work. A gate is closed from a terminal.
        fs.die("QUESTIONS_PENDING — %d unanswered in %s: %s. %s is the approval gate: run "
            "'state.py approve --by \"<name>\"' or 'state.py reject --by \"<name>\" --why \"<text>\"' "
            "in your own terminal. Stage stays at %s."
            % (len(blocking), os.path.relpath(path, root), ", ".join(ids),
               ", ".join(q["id"] for q in blocking if q["kind"] == "G"),
               state.get("current_stage")), 4)
    fs.die("QUESTIONS_PENDING — %d unanswered in %s: %s. Answer with 'state.py answer %s' or fill "
        "the [Answer]: lines and run 'state.py questions --sync'. Stage stays at %s."
        % (len(blocking), os.path.relpath(path, root), ", ".join(ids),
           " ".join("%s=<letter>" % i for i in ids), state.get("current_stage")), 4)


def gate_question_text(task_id):
    return "Approve %s for implementation?" % task_id


def request_gate(root, state, gate, rt=rr_runtime.Runtime()):
    """stage human_approval is the request, and the only way to make one: it
    writes the gate's own question, records *which* question it is, and starts
    the gate ungranted. A grant belongs to one gate, never to the task."""
    path = fs.questions_path(root, state, None)
    with locks.question_lock(path):
        lines, questions = questions_mod.parse_questions(path)
        number = max([q["number"] for q in questions if q["kind"] == "G"] or [0]) + 1
        gate_id = "G%d" % number
        while lines and not lines[-1].strip():
            lines.pop()
        lines = questions_mod.with_preamble(path, lines, state["task_id"])
        lines.extend(questions_mod.question_block({
            "id": gate_id,
            "question": "%s (gate: %s)" % (gate_question_text(state["task_id"]), gate),
            "options": [("A", "Approve"), ("B", "Reject — answer as `B: <reason>`")],
        }, "human_approval", None))
        questions_mod.write_questions(path, lines)
        _, questions = questions_mod.parse_questions(path)
    state["human_approval"].update({
        "required": True, "granted": False, "granted_by": None, "granted_at": None,
        "requested_at": fs.now(), "gate_id": gate_id, "rejected_at": None,
        "via": None, "unattended": False,
        # The session the plan was presented in. The file route requires the
        # human's turn to come from *this* session — comparing session.json's two
        # own fields proves nothing, because whichever session ran last wrote
        # both of them.
        "requested_session": fs.read_session(root).get("session_id"),
    })
    questions_mod.set_pending(root, state, questions, path)
    journal.emit(root, state, "gate_requested", "%s: %s" % (gate_id, gate),
             {"gate": gate, "gate_id": gate_id,
              "requested_at": state["human_approval"]["requested_at"]}, rt=rt)


def close_gate(root, state, gate_id, choice, text, by, via):
    """approve and reject are the gate question's `answer`. Without this its
    question would stay pending and block the very next command (Risks 3), and
    `answer` still refuses a G id, because this is the only route that may close
    one. It closes the gate the state names — never "the last G in the file"."""
    path = fs.questions_path(root, state, None)
    with locks.question_lock(path):
        lines, questions = questions_mod.parse_questions(path)
        gates = [q for q in questions if q["id"] == gate_id]
        if not gates:
            return False
        lines[gates[0]["answer_at"]] = questions_mod.answer_line(choice, text, by, via)
        questions_mod.write_questions(path, lines)
        _, questions = questions_mod.parse_questions(path)
    questions_mod.set_pending(root, state, questions, path)
    return True


def confirm_names(confirm, ops):
    """Every operation keyword (DROP, ALTER …) appears as a word in the confirm text."""
    words = set(re.findall(r"[A-Za-z]+", (confirm or "").upper()))
    return bool((confirm or "").strip()) and all(op.upper() in words for op in ops)


def gate_approved_for(state, tree):
    """The approval close accepts, whichever route granted it (terminal or the
    questions file): granted after the gate was requested, for the tree the gate
    was requested on — which must be the tree now — and, for full_irreversible,
    with a confirm that names every operation."""
    gate, approval = state.get("gate") or {}, state["human_approval"]
    if not (approval.get("granted") and tree and gate.get("tree") == tree
            and (approval.get("granted_at") or "") >= (gate.get("requested_at") or "~")):
        return False
    if state["mode"] == "full_irreversible":
        return confirm_names(gate.get("confirm"), state["weight"].get("operations") or [])
    return True
