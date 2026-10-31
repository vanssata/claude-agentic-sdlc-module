"""ledger: the consent ledger and the decision file, read and written as plain data.

core: LEDGER_LINE_MAX, LEDGER_TYPES, parse_ts, latest_rounds, next_decision_id
shell: ledger_append, read_ledger, live_picks, read_decisions, write_decisions
"""
import contextlib
import json
import os
import re
from datetime import datetime, timezone

from rr_state import fs

LEDGER_LINE_MAX = 4096
LEDGER_TYPES = {"offer", "pick", "use", "void", "decline", "settle"}


def ledger_append(root, entry):
    """One line, one write, O_APPEND; called under ledger_lock."""
    line = dict({"v": 1}, **entry)
    line["at"] = fs.now()
    payload = (json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    if len(payload) > LEDGER_LINE_MAX:
        raise OSError("a consent line is over %d bytes" % LEDGER_LINE_MAX)
    fd = os.open(fs.ledger_path(root), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
    try:
        if os.write(fd, payload) != len(payload):
            raise OSError("short write to consent.jsonl")
    finally:
        os.close(fd)


def read_ledger(root, path=None):
    """Every well-formed line, in order. A torn or foreign line is skipped, so a
    damaged ledger can only show fewer picks than were written (fails closed).
    The hooks keep their own reader (hooks/guard/dialog.py, 7d1); the contract
    test feeds both the same fixtures."""
    entries = []
    try:
        with open(path or fs.ledger_path(root), encoding="utf-8") as fh:
            for raw in fh:
                try:
                    entry = json.loads(raw)
                except (ValueError, RecursionError):
                    continue
                if isinstance(entry, dict) and entry.get("v") == 1 and entry.get("type") in LEDGER_TYPES:
                    entries.append(entry)
    except OSError:
        return []
    return entries


def parse_ts(text):
    try:
        return datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def latest_rounds(ledger):
    """decision -> the picks of its latest dialog call (one tool_use_id). A
    re-offer's picks replace the earlier round's whatever became of them, so an
    expired, voided or other-session pick never blocks the new one (R36.8)."""
    rounds = {}
    for entry in ledger:
        if entry["type"] == "pick" and isinstance(entry.get("order"), int):
            call, picks = rounds.get(entry.get("decision"), (None, []))
            if not picks or call != entry.get("tool_use_id"):
                rounds[entry.get("decision")] = (entry.get("tool_use_id"), [entry])
            else:
                picks.append(entry)
    return {decision: picks for decision, (_, picks) in rounds.items()}


def live_picks(ledger, session, at=None):
    """The picks a command may consume now (R36.7): of each decision's latest
    round, unused, not voided, the decision not settled, same session, inside
    the window — and only the first unused one in its order. A later pick's
    window restarts when the one before it is used."""
    at = at or datetime.now(timezone.utc)
    used, voided, settled = {}, set(), set()
    for entry in ledger:
        kind = entry["type"]
        if kind == "use":
            used[entry.get("id")] = parse_ts(entry.get("at"))
        elif kind == "void":
            voided.update(entry.get("ids") or [])
        elif kind == "settle":
            settled.add(entry.get("decision"))
    live = []
    for decision, chain in latest_rounds(ledger).items():
        if decision in settled:
            continue
        previous_use = None
        for pick in sorted(chain, key=lambda p: p["order"]):
            if pick.get("id") in used:
                previous_use = used[pick.get("id")]
                continue
            picked, expires = parse_ts(pick.get("at")), parse_ts(pick.get("expires_at"))
            if pick.get("id") in voided or pick.get("session") != session or not picked or not expires:
                break
            if previous_use and previous_use > picked:
                expires = previous_use + (expires - picked)
            if at <= expires:
                live.append(pick)
            break
    return live


def read_decisions(root):
    """decision.json, or an empty document when there is none."""
    try:
        with open(fs.decision_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except FileNotFoundError:
        return {"version": 1, "open": []}
    except (OSError, ValueError, RecursionError) as exc:
        fs.die("%s is unreadable (%s); only state.py writes it. Remove it to drop every open decision."
            % (fs.decision_path(root), exc))
    if not isinstance(data, dict) or not isinstance(data.get("open"), list):
        fs.die("%s is not a decision document; remove it to drop every open decision." % fs.decision_path(root))
    return data


def write_decisions(root, data):
    """Atomic; the file is deleted when nothing is open (R36.14)."""
    path = fs.decision_path(root)
    if not data["open"]:
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)


def next_decision_id(data, ledger):
    """One more than any id the file or the ledger has seen: ids are never reused."""
    seen = [d.get("id") for d in data["open"]] + [e.get("decision") for e in ledger] + \
        [d for e in ledger for d in (e.get("decisions") or [])]
    numbers = [int(x[1:]) for x in seen if isinstance(x, str) and re.match(r"^D\d+$", x)]
    return "D%d" % (max(numbers or [0]) + 1)
