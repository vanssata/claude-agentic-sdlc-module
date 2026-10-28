#!/usr/bin/env python3
"""RiskRails: the dialog's recorder and Stop reminder (R36.6, R36.13).

  PostToolUse on the dialog tool (Claude AskUserQuestion, Codex
      request_user_input): the human's answers, read from tool_response, become
      consent-ledger lines (.ai/state/consent.jsonl) — a pick per offered
      command chosen, or a decline. Prints nothing.
  Stop: while a decision is open, blocks the stop with the JSON to send, at
      most stop_blocks_max times per decision per human turn (the turn is
      session.json's prompt_count, which context-guard.py counts); then lets
      the turn end with a systemMessage naming the terminal way out.
  Anything else: exit 0, silent.

Never a deny, and inert unless the effective switch is on (hooks/guard/dialog.py):
with .ai/policies/dialog.json missing or off it reads nothing more and writes
nothing. Fails open: any error exits 0 with no output. Run as
`python3 -I -S`: stdlib only.
"""
import json
import os
import shlex
import sys


def ai_root(cwd):
    """Nearest ancestor of cwd holding a .ai/ directory, or None."""
    d = os.path.abspath(cwd) if cwd else None
    while d:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        d = None if parent == d else parent
    return None


def prompt_count(root):
    try:
        with open(os.path.join(root, ".ai", "state", "session.json"), encoding="utf-8") as fh:
            count = json.load(fh).get("prompt_count")
    except (OSError, ValueError, AttributeError):
        return None
    return count if isinstance(count, int) and not isinstance(count, bool) else None


def on_stop(dialog, root, runtime, payload):
    # Only the session and runtime that opened a decision answer it (7d2).
    decisions = dialog.pending(dialog.bound(dialog.read_decisions(root), runtime, payload.get("session_id")),
                               dialog.read_ledger(root))
    policy = dialog.dialog_policy(root)
    if not decisions or policy is None:
        return None
    ids = [d["id"] for d in decisions]
    turn, session = prompt_count(root), payload.get("session_id")
    state = shlex.quote(dialog.STATE_PY)
    escape = ("python3 %s --root %s decision settle --id %s --pick <n>  (or: decision fallback --id %s "
              "--why \"<why>\")" % (state, shlex.quote(root), ids[0], ids[0]))
    # Without a turn to count by, stop_hook_active is the loop breaker.
    if turn is None and payload.get("stop_hook_active"):
        blocks = policy["stop_blocks_max"]
    else:
        blocks = sum(1 for e in dialog.read_ledger(root, types={dialog.STOP_BLOCK})
                     if e.get("session") == session and e.get("turn") == turn and e.get("decisions") == ids)
    if blocks >= policy["stop_blocks_max"]:
        return {"systemMessage": "DECISION_PENDING %s is still open. Settle it in your terminal: %s"
                                 % (" ".join(ids), escape)}
    with dialog.ledger_lock(root):
        dialog.ledger_append(root, {"type": dialog.STOP_BLOCK, "session": session, "turn": turn,
                                    "decisions": ids})
    tool = dialog.DIALOG_TOOL[runtime]
    return {"decision": "block", "reason": (
        "DECISION_PENDING %s — call %s with exactly this JSON, then run the picked command verbatim, "
        "or 'state.py decision settle --id %s': %s"
        % (" ".join(ids), tool, ids[0], json.dumps(dialog.dialog_payload(decisions, runtime), ensure_ascii=False)))}


def main():
    try:
        hook_dir = os.path.dirname(os.path.abspath(__file__))
        if hook_dir not in sys.path:
            sys.path.insert(0, hook_dir)
        from guard import dialog            # pylint: disable=import-outside-toplevel
        payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
        if not isinstance(payload, dict):
            return 0
        event = payload.get("hook_event_name")
        if event not in ("PostToolUse", "Stop"):
            return 0
        root = ai_root(payload.get("cwd") or os.getcwd())
        runtime = dialog.payload_runtime(payload, __file__)
        if not root or not dialog.effective_switch(root, runtime, payload):
            return 0
        if event == "PostToolUse":
            dialog.record(root, runtime, payload)
            return 0
        out = on_stop(dialog, root, runtime, payload)
        if out:
            sys.stdout.write(json.dumps(out, ensure_ascii=False))
            sys.stdout.flush()
    except Exception:                       # pylint: disable=broad-exception-caught
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
