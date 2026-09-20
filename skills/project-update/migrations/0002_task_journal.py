"""0002: the event journal, and the state keys a task in flight needs for it.

Schema 1 recorded a task's history inside the state file and nowhere else. A
history entry has three fields and no types, so a reader cannot ask it which
tier a task was raised from, which step a scope change touched, or how an
approval was given. The journal answers those, one line per change, append-only,
beside the audit trail it belongs to.

Two operations, both idempotent:

  * the new state keys, added only where they are absent, so a re-run records
    nothing and a task at any stage keeps working;
  * a journal backfilled from `history[]`, written once. Every line it produces
    carries `backfilled: true` and the legacy event name it came from, because a
    line reconstructed after the fact is not the same evidence as one written at
    the moment it happened — and the values that were never recorded (the tier a
    task was raised *from*, who granted an approval and how) stay missing rather
    than being invented.

A run interrupted between the two leaves .ai/VERSION at 1, and the next --apply
completes both.
"""
import json

VERSION = 2
TITLE = "add the task journal and the schema-2 state keys"
MOVES = []

# history[] event name -> the journal type it becomes. Anything not named here
# keeps its name in data.legacy_event and is recorded as "legacy": a type this
# file does not know is still a fact that happened.
LEGACY_TYPES = {
    "task_started": "task_started",
    "stage": "stage_started",
    "risk_classified": "tier_set",
    "plan_approved": "plan_registered",
    "step_started": "step_started",
    "step_completed": "step_done",
    "remediation": "step_started",
    "set": "field_set",
    "risk_added": "field_set",
    "risks_cleared": "field_set",
    "modules": "field_set",
    "human_approval": "gate_approved",
    "task_closed": "task_closed",
    "schema_migrated": "schema_migrated",
}
STAGES_IN_DETAIL = " -> "


def _add_defaults(state):
    """The schema-2 keys, added only where they are absent."""
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    state.setdefault("questions",
                     {"file": ".ai/reports/%s/questions.md" % task_id, "pending": []})
    state.setdefault("handoff",
                     {"file": ".ai/state/handoff.md", "written_at": None, "reason": None})
    approval = state.setdefault("human_approval", {})
    if isinstance(approval, dict):
        for key, value in (("requested_at", None), ("gate_id", None),
                           ("requested_session", None), ("rejected_at", None),
                           ("via", None), ("unattended", False)):
            approval.setdefault(key, value)
    return state


def _stage_of(detail, current):
    """The stage a history entry left the task in, read out of its own text."""
    if STAGES_IN_DETAIL not in detail:
        return current
    return detail.split(STAGES_IN_DETAIL)[-1].split(":")[0].strip() or current


def _line(entry, stage, task_id):
    legacy = entry.get("event") or "legacy"
    detail = entry.get("detail") or ""
    data = {"backfilled": True, "legacy_event": legacy}
    if legacy == "stage" and STAGES_IN_DETAIL in detail:
        data["from"] = detail.split(STAGES_IN_DETAIL)[0].strip()
        data["to"] = stage
    elif legacy == "risk_classified":
        data["tier"] = detail.split(":")[0].strip()
        data["from"] = None
    elif legacy in ("step_completed", "step_started", "remediation"):
        data["step_id"] = detail.split(":")[0].strip()
        if legacy == "remediation":
            data["kind"] = "remediation"
    elif legacy == "human_approval":
        data["via"] = "legacy"
    elif legacy in ("set", "risk_added", "risks_cleared", "modules"):
        data["field"] = detail.split(" = ")[0].strip() if " = " in detail else legacy
    return {
        "ts": entry.get("at") or "",
        "task": task_id,
        "event": LEGACY_TYPES.get(legacy, "legacy"),
        "actor": "migration",
        "runtime": "unknown",
        "stage": stage,
        "detail": detail[:500],
        "data": data,
    }


def _backfill(state):
    """One line per history entry, in order, with the stage each one left."""
    task_id = state.get("task_id") or "unknown"
    stage, out = "", []
    for entry in state.get("history") or []:
        if not isinstance(entry, dict):
            continue
        stage = _stage_of(entry.get("detail") or "", stage)
        out.append(json.dumps(_line(entry, stage, task_id), ensure_ascii=False))
    return ("\n".join(out) + "\n").encode("utf-8") if out else b""


def plan(ctx):
    ctx.patch_state(_add_defaults)
    state = ctx.state
    if not state or not state.get("task_id"):
        return                            # no task in flight: the journal starts empty
    ctx.create(".ai/reports/%s/events.jsonl" % state["task_id"], _backfill(state))
