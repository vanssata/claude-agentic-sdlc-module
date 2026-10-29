"""R36.12: the gate while a dialog decision is open — the first check of
hooks/ai-guard.py, on every tool (the Claude matcher is `*`).

With no .ai/state/decision.json the check costs one stat per ancestor
directory and allows. With the dialog on and a decision of this session
pending, every tool is denied (DECISION_PENDING and the JSON to send) except:

  1. the dialog tool, when its questions equal what state.py prepared (R36.5);
     the call is appended as an `offer`;
  2. a Bash command equal to the next live pick (R36.7); a git pick's `use` is
     appended here and handed to the git check on ctx.consent, a state.py pick
     is spent by state.py itself after its argv check (R36.10);
  3. `state.py decision show|settle|fallback`.

A guarded command (git commit/push, a human-only state.py command) that is not
the next live pick voids the decision's picks: CONSENT_MISMATCH (R36.8). An
offer neither picked nor declined by the next tool call means the recorder did
not run; the decision falls back to the terminal (R36.15).

It fails open: it is not the security boundary (R36.9 and R36.10 are).
"""
import json
import os
import subprocess
from datetime import datetime, timezone

from guard.common import Allow, Deny, b_bytes, exists, find_ai_root, text_to_b


def check(ctx):
    # Its own failure is an Allow, never an exception: ai-guard.py ends the
    # run on one, and the git, paths and scope checks after this must still run.
    try:
        root = find_ai_root(ctx.payload.cwd, ctx.pwd)
        if root is None or not exists(root + "/.ai/state/decision.json"):
            raise Allow()
        gate(ctx, os.fsdecode(b_bytes(root)))
    except (Allow, Deny):
        raise
    except Exception:                       # pylint: disable=broad-exception-caught
        raise Allow() from None
    raise Allow()


def gate(ctx, root):                        # pylint: disable=too-many-locals
    from guard import dialog                # pylint: disable=import-outside-toplevel
    values = ctx.payload.values
    raw = values[0] if len(values) == 1 and isinstance(values[0], dict) else None
    hook_file = os.path.join(os.fsdecode(b_bytes(ctx.hook_dir)), "ai-guard.py")
    runtime = dialog.payload_runtime(raw, hook_file)
    if raw is None or not dialog.effective_switch(root, runtime, raw):
        raise Allow()
    session, call = raw.get("session_id"), raw.get("tool_use_id") or ""
    ledger = dialog.read_ledger(root)
    decisions = dialog.pending(dialog.bound(dialog.read_decisions(root), runtime, session), ledger)
    if not decisions:
        raise Allow()
    ids = [d["id"] for d in decisions]
    command = (b_bytes(ctx.payload.bash_command()).decode("utf-8", "replace").strip()
               if ctx.payload.tool == "Bash" else "")
    # The way out stays open even when the automatic fallback cannot run.
    if command and dialog.decision_command(command):
        raise Allow()
    offer = dialog.unanswered_offer(ledger, session, call, ids)
    if offer:
        fall_back(dialog, root, offer["decisions"])
    expected = dialog.dialog_payload(decisions, runtime)
    tool = dialog.DIALOG_TOOL[runtime]
    pending_text = ("DECISION_PENDING %s — a decision is open: call %s with exactly this JSON, then run the "
                    "picked command verbatim; or run 'state.py decision settle --id %s' for a recorded answer, or "
                    "'state.py decision fallback --id %s --why \"<why>\"': %s"
                    % (" ".join(ids), tool, ids[0], ids[0], json.dumps(expected, ensure_ascii=False)))
    if raw.get("tool_name") == tool:
        sent = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
        # Only what state.py prepared: no title, no pre-filled answers beside it.
        if dialog.canonical(sent.get("questions")) != dialog.canonical(expected["questions"]) \
                or set(sent) - {"questions", "metadata"} or sent.get("metadata"):
            raise Deny(text_to_b(pending_text))
        with dialog.ledger_lock(root):
            dialog.ledger_append(root, {"type": "offer", "decisions": ids, "session": session, "tool_use_id": call})
        raise Allow()
    if ctx.payload.tool == "Bash":
        pick = dialog.next_live_pick(root, session, datetime.now(timezone.utc))
        if pick and pick.get("decision") in ids and pick.get("label") == command:
            if dialog.is_git_label(command):
                with dialog.ledger_lock(root):
                    # Read again under the lock: two calls must not spend one pick.
                    again = dialog.next_live_pick(root, session, datetime.now(timezone.utc))
                    if not again or again.get("id") != pick["id"]:
                        raise Deny(text_to_b(pending_text))
                    dialog.ledger_append(root, {"type": "use", "id": pick["id"], "by": "git"})
                ctx.consent = pick
            raise Allow()
        if dialog.guarded(command):
            voided = dialog.unused_picks(ledger, ids, session)
            if voided:
                labels = [e.get("label") for e in ledger if e.get("type") == "pick" and e.get("id") in voided]
                with dialog.ledger_lock(root):
                    dialog.ledger_append(root, {"type": "void", "ids": voided, "session": session,
                                                "why": "mismatch"})
                raise Deny(text_to_b(
                    "CONSENT_MISMATCH — this is not the next command the human picked; the picks are void and %s "
                    "is open again. Picked, in order: %s. Send the dialog again ('state.py decision show') or "
                    "run 'state.py decision fallback --id %s --why \"<why>\"'."
                    % (" ".join(ids), "; ".join(labels), ids[0])))
    raise Deny(text_to_b(pending_text))


def fall_back(dialog, root, ids):
    """R36.15: state.py moves the decisions to the terminal route; the call is
    denied once with the commands the human runs."""
    printed = []
    for decision_id in ids:
        # A fallback that cannot run is the gate's own error: it fails open.
        done = subprocess.run(["python3", dialog.STATE_PY, "--root", root, "decision", "fallback", "--id",
                               decision_id, "--why", "the dialog's answer was not recorded (the recorder hook "
                               "did not run)"], capture_output=True, text=True, check=False, timeout=5,
                              stdin=subprocess.DEVNULL)
        if done.returncode != 0:
            raise Allow()
        printed.append(done.stdout.strip())
    raise Deny(text_to_b("DECISION_FALLBACK %s — the dialog was sent but its answer was not recorded (R36.15); "
                         "the decision is back on the terminal route.\n%s" % (" ".join(ids), "\n".join(printed))))
