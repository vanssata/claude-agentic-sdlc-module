"""journal: the event vocabulary, the journal line and its append-only file, and the one function that records a state change in both the history and the journal.

core: EVENT_TYPES, FORGEABLE_EVENTS, JOURNAL_MAX_BYTES, DETAIL_MAX, ERROR_MAX
shell: journal_line, append_journal, read_journal, record, emit
"""
import json
import os

try:
    import fcntl
except ImportError:                       # not POSIX: the journal falls back to O_APPEND alone
    fcntl = None

from rr_state import fs
from rr_state import runtime as rr_runtime

# The journal vocabulary (I3): flat, append-only, one type per command that
# changes something. A new type is added only when it has its own reader.
EVENT_TYPES = [
    "task_started", "stage_started", "tier_set", "tier_raised", "plan_registered",
    "scope_change", "step_started", "step_done", "field_set", "question_asked",
    "question_answered", "gate_requested", "gate_approved", "gate_rejected", "note",
    "handoff_written", "runtime_handoff", "model_fallback", "missed_reroute", "schema_migrated",
    "task_closed", "findings_closed", "review_budget_refused", "human_set",
    # schema 7 (redesign 2.2a): the weight model's surface.
    "weight_set", "weight_raised", "mode_set", "verify_run", "review_verdict",
    # R36 (7c): the dialog's decisions and the consent ledger, mirrored by state.py.
    "decision_opened", "consent_recorded", "consent_used", "consent_voided", "decision_declined",
    "decision_settled", "decision_fallback", "plan_drift",
    # compact-project-memory §D9: a risk recorded with `memory risk`, compacted at close.
    "risk_recorded",
    # the batch loop (/rr-build-all): the switch, at start or during the task.
    "batch_set",
]
# The types `event` will not write: each is the record of an authorization or a
# lifecycle decision, and is emitted by the transition that made it. `event` is
# for a hook reporting something that happened outside the state machine.
FORGEABLE_EVENTS = {"gate_requested", "gate_approved", "gate_rejected",
                    "task_started", "task_closed", "weight_set", "weight_raised", "mode_set",
                    "verify_run", "review_verdict", "decision_opened", "consent_recorded",
                    "consent_used", "consent_voided", "decision_declined", "decision_settled",
                    "decision_fallback", "plan_drift", "risk_recorded", "batch_set"}

JOURNAL_MAX_BYTES = 4096
DETAIL_MAX = 500
ERROR_MAX = 1000


def journal_line(task_id, event, actor, stage, detail, data, runtime="unknown"):
    line = {
        "ts": fs.now_ms(), "task": task_id, "event": event, "actor": actor,
        "runtime": runtime, "stage": stage or "", "detail": (detail or "")[:DETAIL_MAX],
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
    path = fs.journal_path(root, task_id)
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
        with open(fs.journal_path(root, task_id), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except (ValueError, RecursionError):
                    skipped += 1
    except OSError:
        return [], skipped
    return events, skipped


def record(state, event, detail=""):
    state.setdefault("history", []).append(
        {"at": fs.now(), "event": event, "detail": detail}
    )


def emit(root, state, event, detail="", data=None, legacy=None, actor="agent", rt=rr_runtime.Runtime()):
    """One state change: today's history entry plus one journal line.

    `legacy` keeps history[]'s original event name where the journal's is newer,
    so every reader and every test written before the journal still sees what it
    expects and the two records stay one-to-one.
    """
    if event not in EVENT_TYPES:
        fs.die("unknown event type '%s' (have: %s)" % (event, ", ".join(EVENT_TYPES)))
    record(state, legacy or event, detail)
    append_journal(root, state.get("task_id"), journal_line(
        state.get("task_id"), event, actor, state.get("current_stage"), detail, data, runtime=rt.name))
