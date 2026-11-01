"""handoff: the resume point, the recent notes, the handoff file and the move of a task to the other runtime.

core: TIERS, RESUME_COMMAND
shell: set_resume_point, recent_notes, handoff_lines, write_handoff, handoff_to
"""
import os
import shlex

from rr_state import fs
from rr_state import journal
from rr_state import policy as rr_policy
from rr_state import profile
from rr_state import questions
from rr_state import runtime as rr_runtime
from rr_state import task

# weight.py sits beside state.py; the entry puts that directory on sys.path.
try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None

TIERS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]


def set_resume_point(state, rt=rr_runtime.Runtime()):
    """Where a session that lost its context picks the work up again."""
    plan = state.get("approved_plan") or {}
    state["resume_point"] = {
        "stage": state.get("current_stage"),
        "step_id": plan.get("current_step_id"),
        "next_action": state.get("next_action"),
        "at": fs.now(),
        "runtime": rt.name if rt.name in rr_runtime.RUNTIMES else state.get("owner_runtime"),
    }


def recent_notes(root, state, limit=3):
    """One pass for all three kinds — the journal is read on every stage-moving
    command — and only this task's own notes: a report directory can be deleted,
    and then next_task_id hands the same id to a different task."""
    events, _ = journal.read_journal(root, state.get("task_id"))
    found = {"decision": [], "rejected": [], "failed": []}
    for event in reversed(events):
        # A report directory can be deleted, and next_task_id then hands the same
        # id to a different task. The scan stops at this task's own task_started
        # rather than at a timestamp: two tasks can share a second, but not a
        # position in an append-only file.
        if event.get("event") == "task_started":
            break
        if event.get("event") != "note":
            continue
        kind = (event.get("data") or {}).get("kind")
        if kind in found and len(found[kind]) < limit:
            found[kind].append(event)
    return found


def handoff_lines(root, state, reason, rt=rr_runtime.Runtime()):
    """The six parts of I4, ≤ 30 lines by construction: a header, the three
    facts a session needs first, three sections of three notes, and the user's
    own last words. Everything here is a fact the runtime cannot lose — the
    state, the journal, task.md §Questions and session.json — never a transcript."""
    plan = state.get("approved_plan") or {}
    steps = plan.get("steps") or []
    # step ids and file scopes come from a model-authored plan file, so they are
    # collapsed like every other free text before they reach the frame.
    step = " · step %s/%d" % (fs.one_line(plan.get("current_step_id"), 40) or "-", len(steps)) if steps else ""
    out = ["# Handoff — %s (%s, %s) · stage %s%s · owner %s · written %s (%s)"
           % (state.get("task_id"), state.get("workflow"),
              state.get("risk_tier") or state.get("mode") or "untiered",
              state.get("current_stage"), step, state.get("owner_runtime") or "unknown",
              fs.now(), reason),
           "Goal: %s" % fs.one_line(state.get("goal"))[:160]]

    resume = state.get("resume_point") or {}
    allowed = [s for s in steps if s.get("step_id") == resume.get("step_id")]
    where = ""
    if resume.get("step_id") and allowed:
        # A step the plan no longer has is not a resume point: saying nothing
        # beats pointing a context-less session at a deleted scope.
        where = "   ← resume point (step %s: %s)" % (
            fs.one_line(resume["step_id"], 40),
            fs.one_line(", ".join(str(f) for f in (allowed[0].get("allowed_files") or [])[:2]), 120))
    out.append("Next: %s%s" % (fs.one_line(state.get("next_action"), 200) or "none recorded", where))

    path = fs.questions_path(root, state, None)
    pending = [q["id"] for q in questions.parse_questions(path)[1] if questions.is_pending(q)]
    out.append("Pending questions: %s" % (
        "%s — %s" % (", ".join(pending), os.path.relpath(path, root)) if pending else "none"))
    if rr_policy.batch_on(state):
        try:
            policy = weight.load_policy(root)[0] if weight else {}
        except (OSError, ValueError, RecursionError):
            policy = {}                       # best effort: the handoff never fails a command
        out.append("Batch: on · ready %s · review %d/%d · suite %d/%d" % (
            ", ".join(fs.one_line(s["id"], 40) for s in task.ready_steps(state)) or "none",
            (state.get("review") or {}).get("passes", 0), rr_policy.budget(policy, state, "review_rounds_max")[0],
            (state.get("verify") or {}).get("suite_runs", 0), rr_policy.budget(policy, state, "max_suite_runs")[0]))

    notes = recent_notes(root, state)
    for kind, heading in (("decision", "Decisions"), ("rejected", "Rejected"),
                          ("failed", "Failed attempts")):
        out.append("## %s (latest 3)" % heading)
        if not notes[kind]:
            out.append("- none")
            continue
        for note in notes[kind]:
            data = note.get("data") or {}
            text = fs.one_line(data.get("text"), 200)
            if kind == "failed":
                out.append("- %s — error: %s" % (text, fs.one_line(data.get("error"), 160) or "none given"))
            else:
                why = fs.one_line(data.get("why"), 200)
                out.append("- %s%s" % (text, " — because %s" % why if why else ""))

    pending_to = (state.get("handoff") or {}).get("pending_to")
    if pending_to:
        review = state.get("cross_vendor_review") or {}
        out.append("Handed to %s at %s%s — resume there with /rr-build" % (
            pending_to, (state.get("handoff") or {}).get("pending_since"),
            " for the cross-vendor review" if review.get("status") == "requested" else ""))
    advice = profile.advisory_line(state, rt=rt)
    if advice:
        out.append(advice)

    session = fs.read_session(root)
    out.append("## Latest user instruction (verbatim, %s, %s)"
               % (session.get("last_prompt_at") or "never", session.get("runtime") or "unknown"))
    if os.environ.get("AI_HANDOFF_NO_PROMPT"):
        # The prompt may carry a secret; recording it is the default, not a duty.
        out.append("> omitted (AI_HANDOFF_NO_PROMPT=1)")
    else:
        out.append("> %s" % (fs.one_line(session.get("last_prompt"), 300) or "none recorded"))
    return out


def write_handoff(root, state, reason, rt=rr_runtime.Runtime()):
    """A pure function of the state, the journal, task.md §Questions and session.json,
    written atomically — rendering it twice gives the same file but its
    timestamp. Best effort end to end, rendering included: a handoff that cannot
    be built or written must never fail the command that moved the stage, and
    its inputs include a hook-written sidecar and an append-only journal that
    nothing validates.

    It mutates `state` in memory only. The caller that is already changing the
    task persists it; `handoff` on its own never writes the state file, because
    the hook calls it while another command may be mid-write."""
    path = fs.handoff_path(root)
    try:
        lines = handoff_lines(root, state, reason, rt=rt)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        # It carries the user's verbatim instruction, so it is theirs to read.
        # events.jsonl is committed with the task and stays 0644; this one is
        # git-ignored and describes a session.
        os.chmod(tmp, 0o600)
        os.replace(tmp, path)
    except Exception:  # pylint: disable=broad-exception-caught  # derived artefact: never fatal
        return None
    # Updated, not replaced: pending_to/pending_since (schema 5) live here too.
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {}
    state["handoff"].update({"file": os.path.relpath(path, root), "written_at": fs.now(), "reason": reason})
    # Journal-only, like note: the handoff is derived, and history[] records
    # what changed the task, not what was rendered from it.
    journal.append_journal(root, state.get("task_id"), journal.journal_line(
        state.get("task_id"), "handoff_written", "agent", state.get("current_stage"),
        reason, {"reason": reason, "lines": len(lines)}, runtime=rt.name))
    return lines


RESUME_COMMAND = {"claude": "claude -p '/rr-build'", "codex": "codex exec '/rr-build'"}


def handoff_to(args, root, rt=rr_runtime.Runtime()):
    """Move the task to the other runtime on purpose (WP5 R10). Ownership moves
    now; the receiving runtime's first change completes it, and until then any
    other runtime's change is refused with exit 7. Pending questions do not
    block it: they travel with the task."""
    state = task.load(root, claim=False, rt=rt)
    source = state.get("owner_runtime") or (rt.name if rt.name in rr_runtime.RUNTIMES else None)
    if not state.get("owner_runtime") and args.to == source:
        fs.die("task %s is already with %s; nothing to hand over" % (state.get("task_id"), args.to), 2)
    if args.to == state.get("owner_runtime"):
        fs.die("task %s is already owned by %s%s" % (
            state.get("task_id"), args.to,
            " (handed over, waiting for it to resume)" if (state.get("handoff") or {}).get("pending_to") else ""), 2)
    if state.get("current_stage") == "done":
        fs.die("task %s is closed; start a new one with start" % state.get("task_id"), 2)
    if not rr_runtime.installed(args.to):
        fs.die("%s is not installed here (%s has no skills/ai-task/state.py); run npx riskrails --target %s"
            % (args.to, rr_runtime.runtime_home(args.to), args.to), 2)
    tier = state.get("risk_tier")
    via = "review" if args.for_ == "review" else "manual"
    review = state.get("cross_vendor_review")
    if isinstance(review, dict) and review.get("status") == "requested":
        # Any move of the task ends an open request: taken back, it was not done;
        # handed on again, a new --for review opens a fresh one. Left open, it
        # sent a later plain handoff straight into an unasked-for review.
        review.update({"status": "cancelled", "cancelled_at": fs.now(), "by_runtime": rt.name})
    data = {"from": source, "to": args.to, "via": via, "reason": args.why or "", "tier": tier,
            "tty": bool(os.isatty(0) and os.isatty(1))}
    if via == "review":
        threshold = (profile.read_profile(rt=rt).get("preferred_runtime") or {}).get("cross_vendor_review_from") or "T5"
        if tier in TIERS and threshold in TIERS and TIERS.index(tier) >= TIERS.index(threshold):
            state["cross_vendor_review"] = {"from": source, "to": args.to, "tier": tier,
                                            "requested_at": fs.now(), "status": "requested",
                                            "by_runtime": None}
        else:
            data["below_threshold"] = threshold
            print("note: %s is below cross_vendor_review_from %s — handed over for review anyway, "
                  "not recorded as a cross-vendor review" % (tier or "an untiered task", threshold))
    state["owner_runtime"] = args.to
    set_resume_point(state, rt=rt)
    state["resume_point"]["runtime"] = args.to
    state["handoff"]["pending_to"] = args.to
    state["handoff"]["pending_since"] = fs.now()
    journal.emit(root, state, "runtime_handoff", "%s -> %s (%s)" % (source, args.to, via), data, rt=rt)
    write_handoff(root, state, "manual", rt=rt)
    task.save(root, state)
    print("Handed %s to %s (%s). In %s, run /rr-build: it resumes from the state file in .ai/state/."
          % (state.get("task_id"), args.to, via, args.to))
    print("headless (not run): cd %s && %s" % (shlex.quote(root), RESUME_COMMAND[args.to]))
