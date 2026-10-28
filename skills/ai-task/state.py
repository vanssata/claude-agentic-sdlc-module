#!/usr/bin/env python3
"""Task state for /ai-task — the small, machine-readable record of one task.

Why a file and not the conversation: a conversation is expensive to re-read and
impossible for a hook to consult. This file is what ai-scope-guard enforces
against, what /ai-status reports, and what lets a task survive a /clear or a
crash. It holds facts, never transcripts.

Everything is stdlib. Writes are atomic (temp file + os.replace), so a hook that
reads the file while a stage is being recorded never sees half a document.

Every state change is also appended to .ai/reports/<task-id>/events.jsonl, the
append-only journal /ai-status and /usage-report read at zero model cost. The
journal is best effort by contract: a line that cannot be written never fails
the command that emitted it, and nothing here depends on it being lossless.
history[] keeps its exact shape and its original event names beside it.

Usage:
  state.py start  --goal G --workflow W --files a,b [--tests t] [--declare axis=n:"why"]...
                  [--mode M --by WHO [--why TEXT]] [--steps "id:a,b:t;..." | --plan-file F.json]
  state.py start  --amend --files "+c,+d" --why TEXT     widen the task in place (R25)
  state.py verify --scope step|suite|e2e|all [--files a,b] [--expect fail]
                  [--e2e not-applicable WHY] [--after-fix WHAT] [--by WHO]
  state.py review --verdict pass|pass_with_findings|blockers_open --tier BALANCED|STRONG
                  --report -|FILE [--focus security] [--by WHO]  |  review --closes "H1,M2"
  state.py close  [--abandon]            two facts, the mode table, the gate, the archive
  state.py step-done <id>                a multi-step guarded or full task
  state.py status [--json]               what /rr-status prints
  state.py ask    "<question>" --option "A: text" [--option ...] [--recommend A] [--topic S]
  state.py ask    --batch FILE.json [--topic SLUG]
  state.py answer Q1=B [Q2=X:"text"] [--by NAME] [--via picker|prose] | --prose "1B 2A 3: text"
  state.py questions [--pending] [--sync] [--format md|prose|json] [--topic SLUG]
                                         --sync records the [Answer]: lines a human filled in
                                         task.md §Questions, the gate's file route among them
  state.py handoff [--print] [--reason stage|precompact|manual|session-start]
  state.py handoff --to claude|codex [--for continue|review] [--why TEXT]
                                         move the task to the other runtime: it must resume there
                                         (exit 7 RUNTIME_HANDOFF_PENDING from anywhere else)
  state.py profile [--field a.b.c] [--tier FAST|BALANCED|STRONG|EXPERT] [--other] [--json]
                                         the installed plan's tables (read-only, no task needed)
  state.py weight --files a,b [--goal G] [--declare axis=n:"why"]... [--json|--long]
  state.py weight --mirror               six axes and a mode, read-only (no task needed);
                                         --mirror writes .ai/policies/weight.md from weight.json
  state.py event  <type> [--detail TEXT] [--data JSON]   # for hooks; type must be in EVENT_TYPES
  state.py approve --by NAME [--confirm "<what it does>"] [--note TEXT]
                                         outside the agent: a TTY, or AI_UNATTENDED;
                                         full_irreversible: the confirm names every operation
  state.py reject  --by NAME --why TEXT

A task the old surface started (schema < 7; its commands were removed in
redesign 2.6) answers status, handoff and questions, and close --abandon drops
it; every other command refuses it.
"""

import argparse
import base64
import contextlib
import decimal
import hashlib
import importlib.util
import json
import os
import re
import shlex
import sys
from datetime import datetime, timezone

try:
    import fcntl
except ImportError:                       # not POSIX: the journal falls back to O_APPEND alone
    fcntl = None

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None
try:
    import weight                         # pure computation; it writes nothing
except ImportError:
    weight = None

TIERS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
WORKFLOWS = ["feature", "bugfix", "refactoring", "hotfix", "investigation"]

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
]
# The types `event` will not write: each is the record of an authorization or a
# lifecycle decision, and is emitted by the transition that made it. `event` is
# for a hook reporting something that happened outside the state machine.
FORGEABLE_EVENTS = {"gate_requested", "gate_approved", "gate_rejected",
                    "task_started", "task_closed", "weight_set", "weight_raised", "mode_set",
                    "verify_run", "review_verdict"}

# The questions are written by state.py and never by a model (R1). One regex
# per line (I2), so a hand edit that keeps the shape round-trips exactly. A
# task's questions live in task.md §Questions (R7, R8); a topic's in its own file.
QUESTIONS_HEADER = """# Questions — %s
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->
"""
TASK_QUESTIONS_NOTE = """<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines here and run
     `state.py questions --sync`; the rest of task.md is rewritten from the state, this section is kept. -->"""
QUESTIONS_SECTION = "## Questions"
OTHER_OPTION = "X. Other — answer as `X: <text>`"
HEADING_RE = re.compile(r"^## (Q|G)(\d+)\. (.+)$")
OPTION_RE = re.compile(r"^([A-W])\. (.+?)( \(recommended\))?$")
OTHER_RE = re.compile(r"^X\. Other")
ANSWER_RE = re.compile(r"^\[Answer\]:\s*(.*)$")
META_RE = re.compile(r"^asked: (\S+) · stage: (\S+)(?: · by: (.+))?$")
CONTEXT_RE = re.compile(r"^context: (.+)$")
# The trailer must be a suffix free text cannot produce: a closed `via`
# vocabulary, an exact timestamp, and a name that cannot span another em dash —
# otherwise `X: we chose Adyen — by the way it is cheaper` eats its own answer.
VIA_VALUES = "picker|prose|file|terminal|unattended"
TRAILER_RE = re.compile(
    r"\s+—\s+by ([^—]+?) via (%s) at (\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z)\s*$" % VIA_VALUES)
CHOICE_RE = re.compile(r"^[A-W]$")
CHOICE_TEXT_RE = re.compile(r"^([A-W])\s*[—:-]\s*(.+)$")
OTHER_TEXT_RE = re.compile(r"^X\s*:\s*(.+)$")
LETTER_RE = re.compile(r"^[A-Z]$")
PROSE_CHOICE_RE = re.compile(r"\b(\d+)\s*([A-W])\b")
PROSE_TEXT_RE = re.compile(r"\b(\d+)\s*:")
OPTION_INPUT_RE = re.compile(r"^([A-W])\s*[:.]\s*(.+)$")
OPTION_KEY_RE = re.compile(r"^[A-W]$")
OPTION_HEAD_RE = re.compile(r"^([A-Za-z0-9]{1,3})\s*[:.]\s")

# A pending question stops a stage from moving; it never stops a command that
# records, reads or answers (R3). close --abandon is exempt: abandoning a task is
# how an unanswerable question is closed.
BLOCKING_COMMANDS = {"step-done", "approve", "close", "verify"}
RUNTIMES = ["claude", "codex"]

JOURNAL_MAX_BYTES = 4096
DETAIL_MAX = 500
ERROR_MAX = 1000

# Resolved once in main() and read by emit(): one process serves one runtime.
RUNTIME = "unknown"
# The commands that change the task. Only these take ownership of it: reading a
# task from the other runtime, or writing a note about it, is not a handoff.
MUTATING_COMMANDS = {"step-done", "ask", "answer", "close", "start", "verify", "review"}
# The commands that work on the task in flight; a task the old surface started
# refuses them all but close --abandon (route_surface).
TASK_COMMANDS = {"step-done", "ask", "answer", "questions", "approve", "reject", "close", "verify",
                 "review"}
MUTATING = False


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_ms():
    """Millisecond precision, because two journal lines can share a second."""
    stamp = datetime.now(timezone.utc)
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (stamp.microsecond // 1000)


def find_root(start):
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, ".ai")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            die("no .ai/ directory found above %s — run /ai-init first" % start)
        d = parent


def die(message, code=1):
    """1 validation · 2 argparse · 4 QUESTIONS_PENDING · 5 APPROVAL_REFUSED ·
    6 SCOPE_CHANGE_REQUIRED / run budget / REVIEW_BUDGET (I1, WP4 I4) ·
    7 RUNTIME_HANDOFF_PENDING · 8 DIRECT_MODE_CAP (WP5 I4; one meaning per code)."""
    print("state.py: %s" % message, file=sys.stderr)
    sys.exit(code)


STATE_NAMES = ("state.json", "current.json")


def state_path(root):
    """The task's state file, read and written where it is: state.json when a
    later version wrote one, else current.json, where every task starts. R34 is
    expand/contract: this version reads both names and moves nothing, so a
    revert of the move that comes later still finds the task."""
    new, legacy = (os.path.join(root, ".ai", "state", name) for name in STATE_NAMES)
    return new if os.path.exists(new) else legacy


def remove_state(root):
    for path in (os.path.join(root, ".ai", "state", name) for name in STATE_NAMES):
        with contextlib.suppress(FileNotFoundError):
            os.remove(path)


def session_path(root):
    return os.path.join(root, ".ai", "state", "session.json")


def read_session(root):
    """The hook's sidecar (I5). Absent, half-written or unreadable is normal."""
    try:
        with open(session_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def installed_runtime():
    """The runtime whose home this copy is installed in, or None for a checkout.
    Both skills call state.py from their own home ($AI_HOME), so this answers
    for every call a runtime makes."""
    here = os.path.abspath(__file__)
    for runtime in ("codex", "claude"):
        home = os.path.abspath(runtime_home(runtime)).rstrip(os.sep) + os.sep
        if here.startswith(home):
            return runtime
    return None


def detect_runtime(explicit, root):
    """--runtime > AI_RUNTIME > install location > CLAUDECODE > session.json >
    unknown (I10). session.json names whichever runtime was prompted last, so it
    comes after everything the process itself can tell: read first, it let one
    runtime's change pass as the other's while both were working. The install
    location outranks CLAUDECODE because an environment variable is inherited:
    codex started from a Claude Code shell carries CLAUDECODE=1 (seen live)."""
    for candidate in (explicit, os.environ.get("AI_RUNTIME"), installed_runtime(),
                      "claude" if os.environ.get("CLAUDECODE") else None,
                      read_session(root).get("runtime")):
        if candidate in RUNTIMES:
            return candidate
    return "unknown"


def journal_path(root, task_id):
    return os.path.join(root, ".ai", "reports", task_id, "events.jsonl")


def journal_line(task_id, event, actor, stage, detail, data):
    line = {
        "ts": now_ms(), "task": task_id, "event": event, "actor": actor,
        "runtime": RUNTIME, "stage": stage or "", "detail": (detail or "")[:DETAIL_MAX],
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
    path = journal_path(root, task_id)
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
        with open(journal_path(root, task_id), encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except ValueError:
                    skipped += 1
    except OSError:
        return [], skipped
    return events, skipped


def apply_defaults(state):
    """Schema 2 keys (I6) in memory, so a v1 state answers every command before
    migration 0002 has run; save() then persists them. A reader that opens
    current.json directly — update.py does — sees the file, not these."""
    if is_v7(state):
        return apply_defaults_v7(state)
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    # A hand-edited or half-migrated file may hold null where v1 held an object.
    # load() promises to be loud about a file it cannot read and silent about one
    # it can, so the defaults are total rather than assuming the v1 shape.
    if not isinstance(state.get("questions"), dict):
        state["questions"] = {"file": ".ai/reports/%s/task.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": True, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("gate_id", None), ("requested_session", None),
                         ("rejected_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    # Schema 4 (WP4 I2): a task that started before the gates existed has no
    # tree to measure from, and one cannot be invented afterwards.
    if not isinstance(state.get("diff"), dict):
        state["diff"] = {}
    state["diff"].setdefault("base_commit", None)
    state["diff"].setdefault("base_tree", None)
    # Schema 5 (WP5 I4): a task handed to the other runtime, and a review asked of it.
    state["handoff"].setdefault("pending_to", None)
    state["handoff"].setdefault("pending_since", None)
    state.setdefault("cross_vendor_review", None)
    return state


def load(root, required=True, claim=None):
    path = state_path(root)
    if not os.path.exists(path):
        if required:
            die("no task in flight (%s does not exist). Start one with state.py start." % path)
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            state = apply_defaults(json.load(fh))
    except (OSError, ValueError) as exc:
        # Loud on purpose: a corrupt state file must never be silently replaced,
        # because ai-scope-guard's boundaries are derived from it.
        die("%s is unreadable (%s). Inspect it by hand; do not delete it blindly." % (path, exc))
    # Ownership is taken before the command's own events, so the journal and
    # history both show the handoff ahead of the work it covers.
    if MUTATING if claim is None else claim:
        claim_runtime(root, state)
    return state


def claim_runtime(root, state):
    """Called from load() for the commands in MUTATING_COMMANDS, so ownership is
    taken once rather than in fifteen call sites. A task that changes runtime says
    so in the journal; WP5 is what will move a task on purpose."""
    pending = (state.get("handoff") or {}).get("pending_to")
    if pending in RUNTIMES:
        if RUNTIME != pending:
            back = ("state.py handoff --to %s" % RUNTIME if RUNTIME in RUNTIMES else
                    "state.py --runtime %s handoff --to %s (this shell is neither runtime; "
                    "name the one taking it)" % ((other_runtime(pending),) * 2))
            die("RUNTIME_HANDOFF_PENDING: task %s was handed to %s at %s. Resume it there "
                "(/ai-task), or take it back here with: %s"
                % (state.get("task_id"), pending, state["handoff"].get("pending_since"), back), 7)
        # The receiving runtime's first change: the handoff is complete. The
        # move itself was journaled when it was made, so there is no second event.
        state["handoff"]["pending_to"] = None
        state["handoff"]["pending_since"] = None
    previous = state.get("owner_runtime")
    if RUNTIME not in RUNTIMES or previous == RUNTIME:
        return
    if previous in RUNTIMES:
        emit(root, state, "runtime_handoff", "%s -> %s" % (previous, RUNTIME),
             {"from": previous, "to": RUNTIME, "via": "resume"})
    state["owner_runtime"] = RUNTIME


def save(root, state):
    state["updated_at"] = now()
    path = state_path(root)
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = "%s.%d.tmp" % (path, os.getpid())
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, path)
    except OSError as exc:
        die("cannot write %s (%s) — the state is the contract, so nothing was recorded" % (path, exc))


def record(state, event, detail=""):
    state.setdefault("history", []).append(
        {"at": now(), "event": event, "detail": detail}
    )


def emit(root, state, event, detail="", data=None, legacy=None, actor="agent"):
    """One state change: today's history entry plus one journal line.

    `legacy` keeps history[]'s original event name where the journal's is newer,
    so every reader and every test written before the journal still sees what it
    expects and the two records stay one-to-one.
    """
    if event not in EVENT_TYPES:
        die("unknown event type '%s' (have: %s)" % (event, ", ".join(EVENT_TYPES)))
    record(state, legacy or event, detail)
    append_journal(root, state.get("task_id"), journal_line(
        state.get("task_id"), event, actor, state.get("current_stage"), detail, data))


def next_task_id(root):
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    reports = os.path.join(root, ".ai", "reports")
    existing = []
    if os.path.isdir(reports):
        existing = [n for n in os.listdir(reports) if n.startswith("T-%s-" % day)]
    return "T-%s-%03d" % (day, len(existing) + 1)


# ------------------------------------------------------------------ plan profile (WP5)
def runtime_home(runtime):
    if runtime == "codex":
        return os.environ.get("CODEX_HOME") or os.path.join(os.path.expanduser("~"), ".codex")
    return os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(os.path.expanduser("~"), ".claude")


def own_runtime():
    """This process's runtime; an undetected one is read from where this file
    is installed, so a plain shell under ~/.codex still reads the Codex plan."""
    if RUNTIME in RUNTIMES:
        return RUNTIME
    return "codex" if "%s.codex%s" % (os.sep, os.sep) in os.path.abspath(__file__) else "claude"


def other_runtime(runtime=None):
    return "codex" if (runtime or own_runtime()) == "claude" else "claude"


def installed(runtime):
    return os.path.isfile(os.path.join(runtime_home(runtime), "skills", "ai-task", "state.py"))


def profile_file(home):
    """<home>/riskrails/profile.json, or <home>/claude-agentic/profile.json where
    the installer has not run since 3.4b (R35, one version)."""
    path = os.path.join(home, "riskrails", "profile.json")
    return path if os.path.exists(path) else os.path.join(home, "claude-agentic", "profile.json")


def read_profile(runtime=None):
    """<home>/riskrails/profile.json, written by the installer; {} when absent,
    which turns every plan budget into a no-op."""
    try:
        with open(profile_file(runtime_home(runtime or own_runtime())), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def read_quota(runtime):
    """The weekly percentage runtime-gate last recorded, or None when unknown
    or stale — advice never rests on a reading older than a day."""
    try:
        with open(os.path.join(runtime_home(runtime), "state", "runtime-gate.json"),
                  encoding="utf-8") as fh:
            quota = json.load(fh).get("quota") or {}
        seen, resets = float(quota.get("seen_at") or 0), float(quota.get("resets_at") or 0)
        now_s = datetime.now(timezone.utc).timestamp()
        if not seen or now_s - seen > 86400 or (resets and now_s > resets):
            return None
        pct = quota.get("weekly_pct")
        return float(pct) if pct is not None else None
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def preferred_runtime(workflow):
    """(runtime, reason) when the plan's table or the quota rule names the
    other runtime and it is installed; None otherwise. Advice only (D3)."""
    me = own_runtime()
    other = other_runtime(me)
    if not installed(other):
        return None
    pref = read_profile(me).get("preferred_runtime") or {}
    named = (pref.get("by_workflow") or {}).get(workflow) or pref.get("default") or "same"
    if named == other:
        return other, "plan table: %s -> %s" % (workflow, other)
    limit = pref.get("quota_pct")
    mine, theirs = read_quota(me), read_quota(other)
    if limit is not None and mine is not None and mine >= float(limit) \
            and (theirs is None or theirs < float(limit)):
        return other, "quota %.0f%% >= %.0f%%" % (mine, float(limit))
    return None


def advisory_line(state):
    found = preferred_runtime(state.get("workflow"))
    return "preferred runtime: %s (%s)" % found if found else None


def advise(state):
    line = advisory_line(state)
    if line:
        print(line, file=sys.stderr)      # stdout carries the task id callers capture


def cmd_profile(args, _root):
    if args.action == "detect":
        cmd_profile_detect(args)
        return
    if args.action == "set":
        cmd_profile_set(args)
        return
    if args.plan:
        die("unrecognized argument %r: profile takes detect or set" % args.plan, 2)
    if args.open or args.detect_runtime:
        die("--open and --runtime after profile belong to profile detect")
    runtime = other_runtime() if args.other else own_runtime()
    prof = read_profile(runtime)
    if not prof:
        die("no plan profile for %s (%s/riskrails/profile.json); npx riskrails writes it"
            % (runtime, runtime_home(runtime)))
    if args.tier:
        model = ((prof.get("tiers") or {}).get(args.tier) or {}).get("model")
        if not model:
            die("the %s profile has no %s tier" % (runtime, args.tier))
        print(model)
        return
    value = prof
    if args.field:
        for part in args.field.split("."):
            if not isinstance(value, dict) or part not in value:
                die("the %s profile has no %s" % (runtime, args.field))
            value = value[part]
    if args.json or isinstance(value, (dict, list)):
        print(json.dumps(value, indent=None if args.field else 2, ensure_ascii=False))
    else:
        print(value)



def js_number(value):
    """Number.prototype.toString for a JSON number: shortest digits, exponent
    form below 1e-6 and from 1e21."""
    f = float(value)
    if f == 0:
        return "0"
    d = decimal.Decimal(repr(f))
    if 1e-6 <= abs(f) < 1e21:
        text = format(d, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    sign, digits, exp = d.normalize().as_tuple()
    mant = "".join(map(str, digits))
    power = exp + len(mant) - 1
    return "%s%s%s%se%s%d" % ("-" if sign else "", mant[0], "." if len(mant) > 1 else "", mant[1:],
                               "+" if power >= 0 else "-", abs(power))


def js_str(value):
    """String(value) as bin/riskrails.js wrote it, for the detection port; None
    is "" because every JS caller had already turned null into ''."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value) if abs(value) <= 2 ** 53 else js_number(value)
    if isinstance(value, float):
        return js_number(value)
    if isinstance(value, list):
        return ",".join(js_str(v) for v in value)
    if isinstance(value, dict):
        return "[object Object]"
    return str(value)


def js_truthy(value):
    return not (value is None or value is False or value == "" or
                (isinstance(value, (int, float)) and not isinstance(value, bool) and value == 0))


def read_json_object(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else {}


def detect_claude():
    """The port of detectClaudePlan (bin/riskrails.js before R36.16): ~/.claude.json's
    oauthAccount, the same regular expressions in the same order."""
    home = os.environ.get("HOME") or os.path.expanduser("~")
    account = read_json_object(os.path.join(home, ".claude.json")) or {}
    oauth = account.get("oauthAccount")
    o = oauth if isinstance(oauth, dict) else {}

    def s(value):
        return "" if value is False else js_str(value)
    org = s(o.get("organizationType")) or s(account.get("organizationType"))
    ratelimit = s(o.get("organizationRateLimitTier"))
    plan, why = None, ""
    if re.search(r"^claude_max|max", org):
        if "max_20x" in ratelimit:
            plan, why = "max20", "organizationRateLimitTier %s" % ratelimit
        else:
            plan, why = "max", "organizationType %s%s" % (org, ", " + ratelimit if ratelimit else "")
    elif re.search(r"pro", org):
        plan, why = "pro", "organizationType %s" % org
    elif re.search(r"team|enterprise", org):
        seat = " ".join(js_str(v) for v in (o.get("seatTier"), o.get("userRateLimitTier"),
                                             o.get("organizationRateLimitTier")) if v is not None and v != "")
        if re.search(r"premium|max", seat):
            plan, why = "team-max", "%s, seat '%s'" % (org, seat)
        elif re.search(r"standard|pro", seat):
            plan, why = "team-pro", "%s, seat '%s'" % (org, seat)
        else:
            why = "team"
    api = not isinstance(oauth, dict) and any(os.environ.get(k) for k in (
        "ANTHROPIC_API_KEY", "CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"))
    fields = {k: js_str(o.get(k)) for k in ("organizationType", "organizationRateLimitTier", "seatTier",
                                            "userRateLimitTier")}
    fields.update(accountOrganizationType=js_str(account.get("organizationType")), api=api)
    return {"plan": plan, "from": why or None, "org": org}, api, fields


def jwt_plan_type(token):
    """chatgpt_plan_type from a JWT's body, decoded as leniently as Node's
    Buffer.from(body, 'base64url'): characters outside the alphabet are skipped,
    decoding stops at '=', bad UTF-8 becomes U+FFFD. The value is returned as
    JSON gave it; the caller applies JS truthiness."""
    try:
        body = token.split(".")[1].split("=")[0].replace("+", "-").replace("/", "_")
        body = re.sub(r"[^A-Za-z0-9_-]", "", body)
        body = body[:len(body) - 1] if len(body) % 4 == 1 else body
        text = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode("utf-8", "replace")
        auth = json.loads(text).get("https://api.openai.com/auth") or {}
        value = auth.get("chatgpt_plan_type")
        return value if js_truthy(value) else ""
    except (IndexError, ValueError, AttributeError, TypeError):
        return ""


def detect_codex():
    """The port of codexDetectPlan and codexRender's mapping: chatgpt_plan_type from
    the JWT in <CODEX_HOME>/auth.json, then ~/.codex/auth.json."""
    home = os.environ.get("HOME") or os.path.expanduser("~")
    raw, first = "", None
    for path in (os.path.join(runtime_home("codex"), "auth.json"), os.path.join(home, ".codex", "auth.json")):
        data = read_json_object(path)
        if data is None:
            continue
        first = data if first is None else first
        tokens = data.get("tokens") or {}
        tokens = tokens if isinstance(tokens, dict) else {}
        for key in ("id_token", "access_token"):
            value = tokens.get(key)
            found = jwt_plan_type(js_str(value) if js_truthy(value) else "")
            if js_truthy(found):
                raw = js_str(found).lower()
                break
        if raw:
            break
    plan, why = None, ""
    if raw in ("plus", "pro"):
        plan, why = raw, "chatgpt_plan_type"
    elif re.search(r"^(team|business|enterprise|edu)", raw):
        plan, why = "pro", "chatgpt_plan_type %s, uses the pro profile" % raw
    first = first or {}
    mode = first.get("auth_mode")
    api = (bool(first.get("OPENAI_API_KEY")) and not first.get("tokens")) or \
        (mode is not None and mode != "chatgpt")
    fields = {"chatgpt_plan_type": raw, "auth_mode": js_str(mode), "api": api}
    return {"plan": plan, "from": why or None, "raw": raw}, api, fields


# Pairs whose profiles differ only in profile.json (R36.17), so `profile set` fixes a
# drift; any other pair needs the installer. Codex plus and pro differ in tiers, session
# and agents, so every Codex change is the installer's.
SAME_TIER = {"claude": ({"max", "max20"}, {"pro", "team-pro"}, {"max", "team-max"}), "codex": ()}


def installer_command(runtime, plan, version):
    return "npx riskrails%s --target %s %s %s --yes" % (
        "@%s" % version if version else "", runtime, "--plan" if runtime == "claude" else "--codex-plan", plan)


def profile_detect(runtime):
    live, api, fields = detect_claude() if runtime == "claude" else detect_codex()
    live["fingerprint"] = "sha256:" + hashlib.sha256(
        json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()
    prof = read_profile(runtime)
    installed = {k: prof.get(k) for k in ("plan", "profile", "plugin_version")} if prof else None
    have = (installed or {}).get("plan")
    render = command = None
    if api:
        status = "unsupported"
    elif not live["plan"]:
        status = "unknown"
    elif not installed:
        status = "no_profile"
    elif have == live["plan"] or (runtime == "claude" and have == "balanced-max" and live["plan"] in ("max", "max20")):
        status = "same"
    else:
        status = "drift"
        if any({have, live["plan"]} <= pair for pair in SAME_TIER[runtime]):
            render = "profile"
            command = "python3 %s profile set %s --runtime %s" % (
                shlex.quote(os.path.abspath(__file__)), live["plan"], runtime)
        else:
            render = "installer"
            command = installer_command(runtime, live["plan"], installed.get("plugin_version"))
    return {"runtime": runtime, "status": status, "installed": installed, "live": live,
            "render": render, "command": command, "decision": None}


def cmd_profile_detect(args):
    """Read-only, exit 0 always (R36.16); `--open` belongs to 7c."""
    if args.open:
        die("--open needs state.py decision (task 7c)", 1)
    if args.field or args.tier or args.other or args.plan:
        die("--field, --tier, --other and a plan belong to the profile reader or profile set, not to profile detect")
    found = profile_detect(args.detect_runtime or own_runtime())
    if args.json:
        print(json.dumps(found, ensure_ascii=False))
        return
    have = (found["installed"] or {}).get("plan") or "none"
    live = found["live"]
    print("plan: installed %s · account %s%s → %s" % (
        have, live["plan"] or "unknown", " (%s)" % live["from"] if live["from"] else "", found["status"]))
    if found["command"]:
        print("fix: %s" % found["command"])

# plan -> (profile, label), as bin/riskrails.js maps --plan and --codex-plan; the
# installer and `profile set` must resolve a plan to the same profile.json.
PLAN_PROFILES = {
    "claude": {"pro": ("pro", "Pro"), "team-pro": ("pro", "Team Pro"), "team-max": ("max", "Team Max"),
               "max": ("max", "Max"), "max20": ("max20", "Max 20x"), "balanced-max": ("balanced-max", "BalancedMax")},
    "codex": {"plus": ("codex-plus", "Plus"), "pro": ("codex-pro", "Pro"),
              "balanced-max": ("codex-balanced-max", "BalancedMax")},
}


def load_resolver(runtime):
    """The installed scripts/resolve-profile.py beside its profiles/ (the installer copies
    both to <home>/riskrails/), else the plugin's, else this checkout's; None when none."""
    here = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for base in (os.path.join(runtime_home(runtime), "riskrails"), os.environ.get("CLAUDE_PLUGIN_ROOT"), here):
        path = os.path.join(base, "scripts", "resolve-profile.py") if base else ""
        if path and os.path.isfile(path) and os.path.isdir(os.path.join(base, "profiles")):
            spec = importlib.util.spec_from_file_location("resolve_profile", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            return module, base
    return None, None


def cmd_profile_set(args):
    """R36.17: the human route only. A same-tier plan rewrites profile.json alone;
    one whose settings or tiers differ is the installer's (exit 6)."""
    if args.open or args.field or args.tier or args.other or args.json:
        die("profile set takes a plan and --runtime only")
    runtime = args.detect_runtime or own_runtime()
    plans = PLAN_PROFILES.get(runtime) or {}
    if args.plan not in plans:
        die("profile set needs a %s plan: %s (got %r)" % (runtime, ", ".join(plans), args.plan or ""))
    via, why = human_route()
    if not via:
        die("profile set is the human's: %s" % why, 5)
    prof = read_profile(runtime)
    if not prof:
        die("no plan profile for %s (%s/riskrails/profile.json); npx riskrails writes it"
            % (runtime, runtime_home(runtime)))
    have = prof.get("plan")
    if have == args.plan:
        print("profile.json: already %s (%s); nothing written" % (have, runtime))
        return
    refusal = "PROFILE_NEEDS_INSTALLER — %s → %s also changes %s: %s" % (
        have, args.plan, "settings.json and the agents" if runtime == "claude" else "config.toml and the agents",
        installer_command(runtime, args.plan, prof.get("plugin_version")))
    if have not in plans or not any({have, args.plan} <= pair for pair in SAME_TIER[runtime]):
        die(refusal, 6)
    resolver, src = load_resolver(runtime)
    if resolver is None:
        die("no resolve-profile.py under %s/riskrails/scripts or the plugin; npx riskrails installs it"
            % runtime_home(runtime))
    fable = bool(prof.get("fable"))
    try:
        old = resolver.resolve(src, plans[have][0], have, plans[have][1], fable)
        new = resolver.resolve(src, plans[args.plan][0], args.plan, plans[args.plan][1], fable)
    except (OSError, ValueError) as exc:
        die("cannot resolve the %s profile: %s" % (args.plan, exc))
    key = resolver.KEY

    def rendered(data):
        return ({k: v for k, v in data.items() if k != key}, data[key].get("tiers"))
    if rendered(old) != rendered(new):
        die(refusal, 6)
    out = dict(new[key], runtime=runtime, written_at=now(), set_by={"via": via, "at": now()})
    for kept in ("plugin_version", "dialog"):
        if kept in prof:
            out[kept] = prof[kept]
    target = os.path.join(runtime_home(runtime), "riskrails", "profile.json")
    tmp = "%s.%d.tmp" % (target, os.getpid())
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=2, ensure_ascii=False)
            fh.write("\n")
        os.replace(tmp, target)
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        die("cannot write %s: %s" % (target, exc))
    print("profile.json: %s → %s (%s); settings and agents unchanged; the managed block and routing.md "
          "keep the label '%s' until the next npx riskrails" % (have, args.plan, runtime, plans[have][1]))


def cmd_weight(args, root):
    """Six axes and a mode from weight.json. Read-only, and it needs no task:
    the weight is what decides how a task is run, so it comes before one."""
    if weight is None:
        die("weight.py is missing beside state.py: reinstall the plugin")
    try:
        policy, path = weight.load_policy(root)
    except (OSError, ValueError) as exc:
        die("cannot read the weight table: %s" % exc)
    if args.mirror:
        own = os.path.join(root, ".ai", "policies", "weight.json")
        if path != own:
            die("%s has no .ai/policies/weight.json: the mirror is written beside the project's own table"
                % root)
        target = os.path.join(os.path.dirname(own), "weight.md")
        tmp = "%s.%d.tmp" % (target, os.getpid())
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(weight.mirror(own))
            os.replace(tmp, target)
        except OSError as exc:
            with contextlib.suppress(OSError):
                os.unlink(tmp)
            die("cannot write %s: %s" % (target, exc))
        print(target)
        return
    files = _split_files(args.files)
    if not files:
        die("weight needs --files: the declared files are what it measures")
    declared = {}
    for item in args.declare:
        m = re.match(r"^(\w+)=(\d{1,3}):(.*\S.*)$", item, re.S)
        if not m:
            die("--declare %r: write axis=n:\"evidence\" — a declaration without its evidence is not one"
                % item)
        declared[m.group(1)] = (int(m.group(2)), m.group(3).strip())
    try:
        result = weight.compute(root, files, declared, args.goal, policy=policy)
    except ValueError as exc:
        die(str(exc))
    except (TypeError, AttributeError) as exc:     # a table whose values have the wrong shape
        die("%s is malformed: %s" % (path, exc))
    if args.json:
        print(json.dumps(dict(result.as_dict(), policy=path), indent=2, ensure_ascii=False))
    else:
        print(weight.render(result, long=args.long))


DIRECT_MODE_CAP = "T4"


# --------------------------------------------------------------------- the gates
# Everything below measures through sensors.py and decides; sensors.py itself
# decides nothing. A sensor that cannot measure says so and the task carries on:
# a measurement is evidence, and missing evidence is never a reason to refuse
# work a human asked for. The one thing it does refuse is a step that grew past
# its tier's budget or reached outside its own files — and both of those are
# answered by splitting the step, not by abandoning it.


def safe_sensor(call, *args, **kwargs):
    """A bug in a sensor must never be able to stop a task. Anything unexpected
    reads as 'unavailable', which keeps every review the tier asked for."""
    if sensors is None:
        return None
    try:
        return call(*args, **kwargs)
    except Exception:                     # pylint: disable=broad-except
        return None


# Set by the runtimes in every process they start, the `!` prefix's shell
# included. Duplicated on purpose from skills/project-update/adopt.py
# (AGENT_MARKERS): the two skills are installed independently and neither
# imports the other.
AGENT_MARKERS = ("CLAUDECODE", "CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_CI",
                 "CODEX_SANDBOX", "CODEX_SANDBOX_NETWORK_DISABLED", "CODEX_VERSION")


def agent_markers():
    return [name for name in AGENT_MARKERS if name in os.environ]


def human_route():
    """(via, why): "terminal" for a terminal outside any agent session,
    "unattended" for a launcher that declared the run unattended, else None and
    what was seen. A terminal alone is not enough — an agent can open a pty — so
    a terminal that carries an agent marker is the agent's. The same condition
    as adopt.human_gate()."""
    markers = agent_markers()
    if os.isatty(0) and not markers:
        return "terminal", ""
    if os.environ.get("AI_UNATTENDED"):
        return "unattended", ""
    if markers:
        return None, ("this run is inside an agent session (%s %s set); run it in a terminal "
                      "outside Claude Code or Codex, not through the `!` prefix"
                      % (", ".join(markers), "is" if len(markers) == 1 else "are"))
    return None, "this run has no terminal"


def _split_files(text):
    return [f.strip() for f in (text or "").split(",") if f.strip()]


def cmd_event(args, root):
    """For hooks and for WP5's model fallback: one journal line, no state write.
    current.json keeps its two writers; this command is not one of them."""
    if args.type not in EVENT_TYPES:
        die("unknown event type '%s' (have: %s)" % (args.type, ", ".join(EVENT_TYPES)))
    if args.type in FORGEABLE_EVENTS:
        # The journal is the compensating control for every route the gate
        # cannot block, so the actor it audits may not author its lines. These
        # types are emitted by the state transition that earns them, and by
        # nothing else: an agent that took the unattended route could otherwise
        # append a second, honest-looking gate_approved next to it.
        die("'%s' is emitted by the state transition that earns it, not by 'event'. "
            "A journal the agent can write is not an audit trail." % args.type, 5)
    data = {}
    if args.data:
        try:
            data = json.loads(args.data)
        except ValueError as exc:
            die("--data must be a JSON object (%s)" % exc)
        if not isinstance(data, dict):
            die("--data must be a JSON object")
    state = load(root)
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], args.type, "hook", state.get("current_stage"), args.detail, data))
    print("%s recorded" % args.type)


def find_docs_root(start):
    """--topic resolves its root from docs/sdlc/, never from .ai/: an intent's
    questions belong to the document they serve, and the sdlc-* skills must work
    in a repository that has no .ai/ at all (I11)."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "docs", "sdlc")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            die("no docs/sdlc/ directory found above %s — run /sdlc-intent first" % start)
        d = parent


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TASK_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def valid_task_id(task_id, flag="--task-id"):
    """A task id is a directory name under .ai/reports/, and everything the
    journal and the questions file are worth rests on it staying one. A '/' or
    a '..' in it puts both outside the project — and outside the path guard's
    `.ai/reports/<id>/` patterns, which is how a writable task.md, and
    with it a self-granted gate, would come back."""
    if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id) or ".." in task_id:
        die("%s takes a directory name — letters, digits, '.', '_' and '-', "
            "no path separators — not %r" % (flag, task_id))
    return task_id


def questions_path(root, state, topic):
    if topic:
        # Topic mode is the one writer that runs without .ai/ and therefore
        # without the path guard, so the slug is validated here rather than
        # trusted: it names a file, it never steers one.
        if not SLUG_RE.match(topic):
            die("--topic takes a slug of lowercase letters, digits and hyphens, not %r" % topic)
        return os.path.join(root, "docs", "sdlc", "intent", "%s.questions.md" % topic)
    return task_md_path(root, state)


def in_task_md(path):
    return os.path.basename(path) == "task.md"


def split_task_md(lines):
    """task.md as (before, section, after): `before` ends with the §Questions
    heading, `section` runs to the next `## ` heading that is not a question's.
    No heading: everything is `before` and the section is None."""
    try:
        start = lines.index(QUESTIONS_SECTION) + 1
    except ValueError:
        return lines, None, []
    end = start
    while end < len(lines) and not (lines[end].startswith("## ") and not HEADING_RE.match(lines[end])):
        end += 1
    return lines[:start], lines[start:end], lines[end:]


def read_lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().split("\n")
    except OSError:
        return None


def question_lines(path):
    """The lines the questions live in. For task.md that is §Questions only; a
    task started before the fold may still hold its questions in questions.md
    beside it, which is read until the first write carries them into task.md."""
    lines = read_lines(path)
    if not in_task_md(path):
        return lines or []
    section = split_task_md(lines or [])[1] or []
    if not any(HEADING_RE.match(line) for line in section):
        legacy = read_lines(os.path.join(os.path.dirname(path), "questions.md"))
        if legacy and any(HEADING_RE.match(line) for line in legacy):
            first = next(i for i, line in enumerate(legacy) if HEADING_RE.match(line))
            return [""] + TASK_QUESTIONS_NOTE.split("\n") + [""] + legacy[first:]
    return section


def with_preamble(path, lines, name):
    """An existing but empty (or header-less) question store still gets the
    notice that tells a human not to edit the questions."""
    if in_task_md(path):
        if not any(line.startswith("<!-- Written by state.py") for line in lines):
            lines = [""] + TASK_QUESTIONS_NOTE.split("\n") + [line for line in lines
                                                              if line.strip() not in ("", "none")]
        return lines
    if not any(line.startswith("# Questions") for line in lines):
        lines = (QUESTIONS_HEADER % name).rstrip("\n").split("\n") + lines
    return lines


def parse_answer_body(question, body):
    """`LETTER`, `LETTER: text`, `X: text` or bare text, with the trailer this
    command writes parsed back off the end and ignored (I2)."""
    question["choice"] = question["text"] = None
    question["invalid"] = None
    trailer = TRAILER_RE.search(body)
    if trailer:
        question["answered_by"], question["via"], question["answered_at"] = trailer.groups()
        body = body[:trailer.start()]
    body = body.strip()
    if not body:
        return
    letters = [letter for letter, _ in question["options"]]
    if question["other"]:
        letters.append("X")
    other = OTHER_TEXT_RE.match(body)
    pair = CHOICE_TEXT_RE.match(body)
    if other:
        choice, text = "X", other.group(1).strip()
    elif pair:
        choice, text = pair.group(1), pair.group(2).strip()
    elif CHOICE_RE.match(body) or LETTER_RE.match(body):
        choice, text = body, None
    else:
        choice, text = ("X" if question["other"] else None), body
    if choice is not None and choice not in letters:
        question["invalid"] = choice
        return
    question["choice"], question["text"] = choice, text


def parse_questions(path):
    """One regex per line (I2). Returns the store's lines beside the questions, so
    a writer can replace an [Answer]: line and leave every other byte alone."""
    lines = question_lines(path)
    questions, current = [], None
    for index, line in enumerate(lines):
        heading = HEADING_RE.match(line)
        if heading:
            current = {
                "id": heading.group(1) + heading.group(2), "kind": heading.group(1),
                "number": int(heading.group(2)), "question": heading.group(3),
                "asked": None, "stage": None, "by": None, "context": None,
                "options": [], "recommend": None, "other": False,
                "answer_at": None, "choice": None, "text": None, "invalid": None,
                "answered_by": None, "via": None, "answered_at": None,
            }
            questions.append(current)
            continue
        if current is None:
            continue
        meta = META_RE.match(line)
        if meta:
            current["asked"], current["stage"], current["by"] = meta.groups()
            continue
        context = CONTEXT_RE.match(line)
        if context:
            current["context"] = context.group(1)
            continue
        answer = ANSWER_RE.match(line)
        if answer:
            current["answer_at"] = index
            parse_answer_body(current, answer.group(1))
            current = None                # the block ends at its answer line
            continue
        if OTHER_RE.match(line):
            current["other"] = True
            continue
        option = OPTION_RE.match(line)
        if option:
            current["options"].append((option.group(1), option.group(2)))
            if option.group(3):
                current["recommend"] = option.group(1)
    return lines, questions


def is_pending(question):
    return question["choice"] is None


LOCK_DEPTH = 0


@contextlib.contextmanager
def question_lock(path):
    """The questions are read, modified and written back. Without a lock across
    that window two `ask` calls lose a block — and the journal would then name a
    question the file does not hold, which nothing would ever block on.

    Re-entrant within the process: flock is per open file description, so a
    nested acquisition on a second fd would wait for the first for ever. That is
    what lets the gate decide and apply inside one critical section."""
    global LOCK_DEPTH                     # pylint: disable=global-statement
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    if fcntl is None or LOCK_DEPTH:
        LOCK_DEPTH += 1
        try:
            yield
        finally:
            LOCK_DEPTH -= 1
        return
    # The lock is taken on the directory itself, so the audit trail gains no
    # lock file and the lock survives the os.replace that swaps the inode.
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        yield
        return
    LOCK_DEPTH += 1
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        LOCK_DEPTH -= 1
        os.close(fd)


def write_questions(path, lines):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if in_task_md(path):
        # Only §Questions is replaced; the other sections stay as rendered.
        before, section, after = split_task_md(read_lines(path) or [])
        lines = lines + ([""] if lines and lines[-1] else [])
        if section is not None:
            lines = before + lines + after
        else:
            lines = before + (["", QUESTIONS_SECTION] if before else [QUESTIONS_SECTION]) + lines
    tmp = "%s.%d.tmp" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines).rstrip("\n") + "\n")
    os.replace(tmp, path)


def one_line(text, limit=None):
    """Everything a caller writes into a file is collapsed to one line: a newline
    in an answer would otherwise produce a second [Answer]: line, and the file a
    human reads would disagree with the record every command acts on.

    Total on purpose. session.json is written by a hook and the journal takes
    typed data from one, so a value that is not a string is normal input here,
    never a reason to fail the command that was reading it."""
    if text is None:
        return ""
    if not isinstance(text, str):
        text = str(text)
    text = " ".join(text.split())
    return text[:limit] if limit else text


def answer_line(choice, text, by, via):
    text = one_line(text)
    if TRAILER_RE.search(text):
        # An answer that ends in the trailer's exact shape would re-parse as
        # somebody else's; the em dash is the anchor, so it goes.
        text = text.replace("—", "-")
    by = one_line(by).replace("—", "-")
    if choice and text:
        body = "%s: %s" % (choice, text)
    elif choice:
        body = choice
    else:
        body = text
    return "[Answer]: %s — by %s via %s at %s" % (body, by or "unknown", via, now())


def question_block(question, stage, by):
    by = one_line(by)
    block = ["", "## %s. %s" % (question["id"], one_line(question["question"])),
             "asked: %s · stage: %s%s" % (now(), stage, " · by: " + by if by else "")]
    if question.get("context"):
        block.append("context: %s" % one_line(question["context"]))
    for letter, text in question["options"]:
        block.append("%s. %s%s" % (letter, one_line(text),
                                   " (recommended)" if letter == question.get("recommend") else ""))
    block.append(OTHER_OPTION)
    block.append("[Answer]:")
    return block


def render_prose(questions):
    """The rendering every runtime can show. The number is the question's own id
    number, so the same reply means the same thing whenever it is given."""
    out = []
    for question in questions:
        answered = "" if is_pending(question) else "  — answered: %s" % question["choice"]
        out.append("%s. %s  [%s]%s"
                   % (question["number"], question["question"], question["id"], answered))
        if question["context"]:
            out.append("   context: %s" % question["context"])
        for letter, text in question["options"]:
            out.append("   %s. %s%s" % (letter, text,
                                        " (recommended)" if letter == question["recommend"] else ""))
        if question["other"]:
            out.append("   X. Other — answer as `X: <text>`")
    pending = [q for q in questions if is_pending(q)]
    if pending:
        out.append("Reply `%s`, a free-text answer last, or run: state.py answer %s"
                   % (" ".join("%s<letter>" % q["number"] for q in pending),
                      " ".join("%s=<letter>" % q["id"] for q in pending)))
    return out


def render_md(questions):
    out = []
    for question in questions:
        if is_pending(question):
            out.append("- **%s** — _unanswered_ (%s)" % (question["question"], question["id"]))
            continue
        chosen = dict(question["options"]).get(question["choice"], question["text"] or "Other")
        detail = "%s — %s" % (chosen, question["text"]) if question["text"] and question["choice"] != "X" else chosen
        out.append("- **%s** — %s *(%s, %s)*" % (
            question["question"], detail, question["id"],
            "by %s via %s at %s" % (question["answered_by"], question["via"], question["answered_at"])
            if question["answered_by"] else "answered"))
    return out


def render_questions(questions, fmt):
    if fmt == "json":
        shown = []
        for question in questions:
            item = {k: v for k, v in question.items() if k != "answer_at"}
            item["options"] = [{"key": k, "text": t} for k, t in question["options"]]
            item["pending"] = is_pending(question)
            shown.append(item)
        return [json.dumps(shown, ensure_ascii=False, indent=2)]
    if fmt == "md":
        return render_md(questions)
    return render_prose(questions)


def parse_prose(text, by_id):
    """`3B` is a choice for Q3, `3: …` is free text for Q3.

    The number is the question's own id number, not its position in a rendering
    — a rendering the human saw yesterday must not answer a different question
    today. Free text runs to the end of the reply, because a sentence may
    legitimately contain `2B` or `step 2:` and half an answer is worse than a
    refusal; so a free-text answer comes last.
    """
    assignments = []
    start = PROSE_TEXT_RE.search(text)
    head = text[:start.start()] if start else text
    for token in PROSE_CHOICE_RE.finditer(head):
        assignments.append((prose_id(int(token.group(1)), by_id), token.group(2), None))
    if start:
        assignments.append((prose_id(int(start.group(1)), by_id), "X",
                            text[start.end():].strip()))
    if not assignments:
        die("no answers found in %r — reply like `1B 2A 3: free text`" % text)
    return assignments


def prose_id(number, by_id):
    qid = "Q%d" % number
    if qid not in by_id:
        die("prose answer %d has no question (have: %s)"
            % (number, ", ".join(i for i in by_id if i.startswith("Q")) or "none"))
    return qid


def unquote(text):
    """I1 writes the free-text form as X:"free text"; the quotes belong to the
    body and are stripped only as a matching pair."""
    text = text.strip()
    if len(text) > 1 and text[0] == text[-1] and text[0] in "\"'":
        return text[1:-1]
    return text


def parse_assignment(token):
    """Q1=B, Q2=X:free text, Q3=B: because."""
    if "=" not in token:
        die("answer takes Q1=B, not %r" % token)
    qid, value = token.split("=", 1)
    value = value.strip()
    other = OTHER_TEXT_RE.match(value)
    if other:
        return (qid.strip(), "X", unquote(other.group(1)))
    pair = CHOICE_TEXT_RE.match(value)
    if pair:
        return (qid.strip(), pair.group(1), unquote(pair.group(2)))
    # A bare letter is a choice even when it is not one of the options, so a
    # typo is refused rather than silently recorded as free text.
    if LETTER_RE.match(value):
        return (qid.strip(), value, None)
    return (qid.strip(), None, unquote(value))


def set_pending(root, state, questions, path):
    """questions.pending is a cache; the file is the truth (spec alternative 4)."""
    state["questions"] = {
        "file": os.path.relpath(path, root),
        "pending": [q["id"] for q in questions if is_pending(q)],
    }


def cmd_ask(args, root):
    if args.gate:
        # A gate the agent can author is a gate the agent can have signed: the
        # human would approve whichever G was pending last.
        die("a gate is requested by 'state.py close' in full mode, not by ask")
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    stage = "intent" if args.topic else state["current_stage"]
    asked = []
    if args.batch:
        try:
            with open(args.batch, encoding="utf-8") as fh:
                batch = json.load(fh)
        except (OSError, ValueError) as exc:
            die("cannot read batch file %s (%s)" % (args.batch, exc))
        if not isinstance(batch, list) or not batch:
            die("the batch file must contain a non-empty JSON array")
        for item in batch:
            if not isinstance(item, dict):
                die("every batch item must be an object with question and options")
            options = item.get("options") or []
            if not all(isinstance(o, dict) and "key" in o and "text" in o for o in options):
                die("every option needs a key and a text (%r)" % item.get("question"))
            asked.append({"question": item.get("question"),
                          "options": [(o["key"], o["text"]) for o in options],
                          "recommend": item.get("recommend"), "context": item.get("context")})
    else:
        if not args.question:
            die("ask takes a question, or --batch FILE.json")
        options, letters = [], "ABCDEFGHIJKLMNOPQRSTUVW"
        for option in args.option:
            # Collapsed first: a key is only recognisable once the value is one
            # line, and one line is what the file will hold either way.
            option = one_line(option)
            if len(options) >= len(letters):
                die("a question takes at most %d options" % len(letters))
            head = OPTION_INPUT_RE.match(option)
            if head:
                options.append((head.group(1), head.group(2).strip()))
                continue
            labelled = OPTION_HEAD_RE.match(option)
            if labelled:
                # "1: one" or "aa: one" is a key the I2 grammar cannot parse, not
                # an option whose text happens to start that way.
                die("an option key is one letter A–W, not %r" % labelled.group(1))
            options.append((letters[len(options)], option))
        asked.append({"question": args.question, "options": options,
                      "recommend": args.recommend, "context": args.context})
    for item in asked:
        if not item["question"]:
            die("every question needs a question line")
        if len(item["options"]) < 2:
            die("a question needs at least two options (%r has %d)"
                % (item["question"], len(item["options"])))
        keys = [key for key, _ in item["options"]]
        # An option the I2 grammar cannot parse would round-trip as no option at
        # all, and the answer to it would be recorded as free text (R1).
        for key in keys:
            if not OPTION_KEY_RE.match(key):
                die("an option key is one letter A–W, not %r" % key)
        if len(set(keys)) != len(keys):
            die("option keys must be distinct (%s)" % ", ".join(keys))
        for _, text in item["options"]:
            if text.endswith(" (recommended)"):
                die("an option text cannot end with ' (recommended)' — use --recommend")
        if item["recommend"] and item["recommend"] not in keys:
            die("--recommend %s is not one of the options (%s)"
                % (item["recommend"], ", ".join(keys)))

    new_ids = []
    with question_lock(path):
        lines, existing = parse_questions(path)
        while lines and not lines[-1].strip():
            lines.pop()
        lines = with_preamble(path, lines, args.topic or state["task_id"])
        kind = "G" if args.gate else "Q"
        number = max([q["number"] for q in existing if q["kind"] == kind] or [0])
        for item in asked:
            number += 1
            item["id"] = "%s%d" % (kind, number)
            if args.gate:
                item["question"] = "%s (gate: %s)" % (item["question"], args.gate)
            new_ids.append(item["id"])
            lines.extend(question_block(item, stage, args.by))
        write_questions(path, lines)
        lines, questions = parse_questions(path)
    relative = os.path.relpath(path, root)
    if state is not None:
        for item in asked:
            emit(root, state, "question_asked", "%s: %s" % (item["id"], item["question"]),
                 {"id": item["id"], "options": [letter for letter, _ in item["options"]],
                  "recommended": item["recommend"], "gate": args.gate})
        set_pending(root, state, questions, path)
        write_handoff(root, state, "stage")
        save(root, state)
    print("%s asked → %s" % (" ".join(new_ids), relative))
    for line in render_prose([q for q in questions if is_pending(q)]):
        print(line)
    if os.environ.get("AI_UNATTENDED"):
        # The literal line an unattended launcher greps for (R5).
        print("WAITING_FOR_ANSWERS %s %s" % (relative, " ".join(new_ids)))


def apply_answers(lines, by_id, assignments, args, relative):
    for qid, choice, text in assignments:
        question = by_id.get(qid)
        if question is None:
            die("no question %s in %s (have: %s)" % (qid, relative, ", ".join(by_id) or "none"))
        if question["kind"] == "G":
            die("%s is a gate: run 'state.py approve' in your terminal or fill its [Answer]: line" % qid)
        letters = [letter for letter, _ in question["options"]]
        if question["other"]:
            letters.append("X")
        if choice is None:
            choice = "X" if question["other"] else None
        if choice not in letters:
            die("%s: invalid choice %r (options: %s)" % (qid, choice, ", ".join(letters)))
        lines[question["answer_at"]] = answer_line(choice, text, args.by, args.via)


def cmd_answer(args, root):
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    with question_lock(path):
        lines, questions = parse_questions(path)
        if not questions:
            die("no questions in %s" % os.path.relpath(path, root))
        by_id = {q["id"]: q for q in questions}
        assignments = []
        if args.prose:
            assignments = parse_prose(args.prose, by_id)
        for token in args.assignment:
            assignments.append(parse_assignment(token))
        if not assignments:
            die("answer takes Q1=B …, or --prose \"1B 2A 3: text\"")
        apply_answers(lines, by_id, assignments, args, os.path.relpath(path, root))
        write_questions(path, lines)
        lines, questions = parse_questions(path)
        by_id = {q["id"]: q for q in questions}
    if state is not None:
        for qid, _, _ in assignments:
            question = by_id[qid]
            # actor is derived from the route, never asserted by the caller:
            # `human` is reserved for the file route and the gate (I3).
            emit(root, state, "question_answered", "%s = %s" % (qid, question["choice"]),
                 {"id": qid, "choice": question["choice"], "text": question["text"],
                  "via": args.via, "by": args.by}, actor="agent")
        set_pending(root, state, questions, path)
        write_handoff(root, state, "stage")
        save(root, state)
    pending = [q["id"] for q in questions if is_pending(q)]
    print("%s answered; %s" % (", ".join(qid for qid, _, _ in assignments),
                               ("still pending: " + ", ".join(pending)) if pending else "none pending"))


def sync_answers(root, state, path, lines, questions, args):
    """Pick up hand edits: a filled line with no trailer is a fresh answer, a
    line this command already wrote has one, so syncing twice changes nothing."""
    changed, gates = [], []
    for question in questions:
        if question["invalid"]:
            print("state.py: %s: invalid choice %r — it stays pending"
                  % (question["id"], question["invalid"]), file=sys.stderr)
            continue
        if question["kind"] == "G":
            # A gate is not answered, it is granted or rejected: a filled answer
            # on the open gate goes through the file route, and any other G block
            # is left exactly as it is rather than consumed.
            if (state is not None and question["id"] == open_gate(state)
                    and question["choice"] and not question["answered_by"] and not gates):
                if question["choice"] not in ("A", "B"):
                    # A gate has two answers. Free text — the likeliest thing a
                    # human writes into a question file — must not be read as a
                    # rejection with their own approving sentence as the reason.
                    print("state.py: %s is the approval gate: answer it A or B, not %r"
                          % (question["id"], question["text"] or question["choice"]),
                          file=sys.stderr)
                    continue
                gates.append(question)
            continue
        if question["choice"] is not None and not question["answered_by"]:
            lines[question["answer_at"]] = answer_line(
                question["choice"], question["text"], args.by, "file")
            changed.append(question)
    if not changed:
        return gates
    if state is not None:
        # Recording answers changes the task, so it takes ownership as ask does.
        claim_runtime(root, state)
    write_questions(path, lines)
    if state is not None:
        by_id = {q["id"]: q for q in parse_questions(path)[1]}
        for question in changed:
            if question["kind"] == "G":
                continue                          # the gate's file route is step 6's
            current = by_id[question["id"]]
            emit(root, state, "question_answered", "%s = %s" % (current["id"], current["choice"]),
                 {"id": current["id"], "choice": current["choice"], "text": current["text"],
                  "via": "file", "by": args.by}, actor="human")
    return changed + gates


def cmd_questions(args, root):
    state = None if args.topic else load(root)
    path = questions_path(root, state, args.topic)
    granted, touched = None, []
    with question_lock(path) if args.sync else contextlib.nullcontext():
        lines, questions = parse_questions(path)
        if args.sync:
            touched = sync_answers(root, state, path, lines, questions, args)
        if state is not None and touched:
            # Persisted before the gate is evaluated, because a refusal there
            # exits 5 and never returns: the answers this sync already wrote
            # into the file must be in the state and the history too.
            # Only a sync that changed something writes at all — questions.pending
            # is a cache, and guard_pending re-parses the file anyway, so a read
            # (which /ai-status and the session-start hook both perform) never
            # races a command that is mid-write.
            _, questions = parse_questions(path)
            set_pending(root, state, questions, path)
            save(root, state)
        for question in [q for q in touched if q["kind"] == "G"]:
            granted = close_gate_from_file(root, state, question, args.by)
        if touched:
            _, questions = parse_questions(path)
            if state is not None:
                set_pending(root, state, questions, path)
                save(root, state)
    if granted is not None:
        print("gate %s by %s via the file" % ("approved" if granted else "rejected", args.by))
    shown = [q for q in questions if is_pending(q)] if args.pending else questions
    for line in render_questions(shown, args.format):
        print(line)


def handoff_path(root):
    return os.path.join(root, ".ai", "state", "handoff.md")


def set_resume_point(state):
    """Where a session that lost its context picks the work up again."""
    plan = state.get("approved_plan") or {}
    state["resume_point"] = {
        "stage": state.get("current_stage"),
        "step_id": plan.get("current_step_id"),
        "next_action": state.get("next_action"),
        "at": now(),
        "runtime": RUNTIME if RUNTIME in RUNTIMES else state.get("owner_runtime"),
    }


def recent_notes(root, state, limit=3):
    """One pass for all three kinds — the journal is read on every stage-moving
    command — and only this task's own notes: a report directory can be deleted,
    and then next_task_id hands the same id to a different task."""
    events, _ = read_journal(root, state.get("task_id"))
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


def handoff_lines(root, state, reason):
    """The six parts of I4, ≤ 30 lines by construction: a header, the three
    facts a session needs first, three sections of three notes, and the user's
    own last words. Everything here is a fact the runtime cannot lose — the
    state, the journal, task.md §Questions and session.json — never a transcript."""
    plan = state.get("approved_plan") or {}
    steps = plan.get("steps") or []
    # step ids and file scopes come from a model-authored plan file, so they are
    # collapsed like every other free text before they reach the frame.
    step = " · step %s/%d" % (one_line(plan.get("current_step_id"), 40) or "-", len(steps)) if steps else ""
    out = ["# Handoff — %s (%s, %s) · stage %s%s · owner %s · written %s (%s)"
           % (state.get("task_id"), state.get("workflow"),
              state.get("risk_tier") or state.get("mode") or "untiered",
              state.get("current_stage"), step, state.get("owner_runtime") or "unknown",
              now(), reason),
           "Goal: %s" % one_line(state.get("goal"))[:160]]

    resume = state.get("resume_point") or {}
    allowed = [s for s in steps if s.get("step_id") == resume.get("step_id")]
    where = ""
    if resume.get("step_id") and allowed:
        # A step the plan no longer has is not a resume point: saying nothing
        # beats pointing a context-less session at a deleted scope.
        where = "   ← resume point (step %s: %s)" % (
            one_line(resume["step_id"], 40),
            one_line(", ".join(str(f) for f in (allowed[0].get("allowed_files") or [])[:2]), 120))
    out.append("Next: %s%s" % (one_line(state.get("next_action"), 200) or "none recorded", where))

    path = questions_path(root, state, None)
    pending = [q["id"] for q in parse_questions(path)[1] if is_pending(q)]
    out.append("Pending questions: %s" % (
        "%s — %s" % (", ".join(pending), os.path.relpath(path, root)) if pending else "none"))

    notes = recent_notes(root, state)
    for kind, heading in (("decision", "Decisions"), ("rejected", "Rejected"),
                          ("failed", "Failed attempts")):
        out.append("## %s (latest 3)" % heading)
        if not notes[kind]:
            out.append("- none")
            continue
        for note in notes[kind]:
            data = note.get("data") or {}
            text = one_line(data.get("text"), 200)
            if kind == "failed":
                out.append("- %s — error: %s" % (text, one_line(data.get("error"), 160) or "none given"))
            else:
                why = one_line(data.get("why"), 200)
                out.append("- %s%s" % (text, " — because %s" % why if why else ""))

    pending_to = (state.get("handoff") or {}).get("pending_to")
    if pending_to:
        review = state.get("cross_vendor_review") or {}
        out.append("Handed to %s at %s%s — resume there with /ai-task" % (
            pending_to, (state.get("handoff") or {}).get("pending_since"),
            " for the cross-vendor review" if review.get("status") == "requested" else ""))
    advice = advisory_line(state)
    if advice:
        out.append(advice)

    session = read_session(root)
    out.append("## Latest user instruction (verbatim, %s, %s)"
               % (session.get("last_prompt_at") or "never", session.get("runtime") or "unknown"))
    if os.environ.get("AI_HANDOFF_NO_PROMPT"):
        # The prompt may carry a secret; recording it is the default, not a duty.
        out.append("> omitted (AI_HANDOFF_NO_PROMPT=1)")
    else:
        out.append("> %s" % (one_line(session.get("last_prompt"), 300) or "none recorded"))
    return out


def write_handoff(root, state, reason):
    """A pure function of the state, the journal, task.md §Questions and session.json,
    written atomically — rendering it twice gives the same file but its
    timestamp. Best effort end to end, rendering included: a handoff that cannot
    be built or written must never fail the command that moved the stage, and
    its inputs include a hook-written sidecar and an append-only journal that
    nothing validates.

    It mutates `state` in memory only. The caller that is already changing the
    task persists it; `handoff` on its own never writes current.json, because
    the hook calls it while another command may be mid-write."""
    path = handoff_path(root)
    try:
        lines = handoff_lines(root, state, reason)
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
    state["handoff"].update({"file": os.path.relpath(path, root), "written_at": now(), "reason": reason})
    # Journal-only, like note: the handoff is derived, and history[] records
    # what changed the task, not what was rendered from it.
    append_journal(root, state.get("task_id"), journal_line(
        state.get("task_id"), "handoff_written", "agent", state.get("current_stage"),
        reason, {"reason": reason, "lines": len(lines)}))
    return lines


RESUME_COMMAND = {"claude": "claude -p '/ai-task'", "codex": "codex exec '/ai-task'"}


def handoff_to(args, root):
    """Move the task to the other runtime on purpose (WP5 R10). Ownership moves
    now; the receiving runtime's first change completes it, and until then any
    other runtime's change is refused with exit 7. Pending questions do not
    block it: they travel with the task."""
    state = load(root, claim=False)
    source = state.get("owner_runtime") or (RUNTIME if RUNTIME in RUNTIMES else None)
    if not state.get("owner_runtime") and args.to == source:
        die("task %s is already with %s; nothing to hand over" % (state.get("task_id"), args.to), 2)
    if args.to == state.get("owner_runtime"):
        die("task %s is already owned by %s%s" % (
            state.get("task_id"), args.to,
            " (handed over, waiting for it to resume)" if (state.get("handoff") or {}).get("pending_to") else ""), 2)
    if state.get("current_stage") == "done":
        die("task %s is closed; start a new one with start" % state.get("task_id"), 2)
    if not installed(args.to):
        die("%s is not installed here (%s has no skills/ai-task/state.py); run npx riskrails --target %s"
            % (args.to, runtime_home(args.to), args.to), 2)
    tier = state.get("risk_tier")
    via = "review" if args.for_ == "review" else "manual"
    review = state.get("cross_vendor_review")
    if isinstance(review, dict) and review.get("status") == "requested":
        # Any move of the task ends an open request: taken back, it was not done;
        # handed on again, a new --for review opens a fresh one. Left open, it
        # sent a later plain handoff straight into an unasked-for review.
        review.update({"status": "cancelled", "cancelled_at": now(), "by_runtime": RUNTIME})
    data = {"from": source, "to": args.to, "via": via, "reason": args.why or "", "tier": tier,
            "tty": bool(os.isatty(0) and os.isatty(1))}
    if via == "review":
        threshold = (read_profile().get("preferred_runtime") or {}).get("cross_vendor_review_from") or "T5"
        if tier in TIERS and threshold in TIERS and TIERS.index(tier) >= TIERS.index(threshold):
            state["cross_vendor_review"] = {"from": source, "to": args.to, "tier": tier,
                                            "requested_at": now(), "status": "requested",
                                            "by_runtime": None}
        else:
            data["below_threshold"] = threshold
            print("note: %s is below cross_vendor_review_from %s — handed over for review anyway, "
                  "not recorded as a cross-vendor review" % (tier or "an untiered task", threshold))
    state["owner_runtime"] = args.to
    set_resume_point(state)
    state["resume_point"]["runtime"] = args.to
    state["handoff"]["pending_to"] = args.to
    state["handoff"]["pending_since"] = now()
    emit(root, state, "runtime_handoff", "%s -> %s (%s)" % (source, args.to, via), data)
    write_handoff(root, state, "manual")
    save(root, state)
    print("Handed %s to %s (%s). In %s, run /ai-task: it resumes from .ai/state/current.json."
          % (state.get("task_id"), args.to, via, args.to))
    print("headless (not run): cd %s && %s" % (shlex.quote(root), RESUME_COMMAND[args.to]))


def cmd_handoff(args, root):
    if args.to:
        handoff_to(args, root)
        return
    state = load(root)
    lines = write_handoff(root, state, args.reason)
    if lines is None:
        print("state.py: could not write %s" % os.path.relpath(handoff_path(root), root),
              file=sys.stderr)
        # --print still answers from the render the caller asked for.
        lines = handoff_lines(root, state, args.reason)
    if args.print_it:
        for line in lines:
            print(line)
    else:
        print(os.path.relpath(handoff_path(root), root))


def guard_pending(root, command):
    """The file is re-parsed on every stage-moving command — questions.pending is
    only a cache — and nothing is written, so exit 4 leaves the state byte-identical."""
    state = load(root, required=False, claim=False)
    if state is None:
        return
    path = questions_path(root, state, None)
    _, questions = parse_questions(path)
    # For a question the file is the truth. For the gate it is not: an
    # authorization is closed by approve or reject, so a hand-filled [Answer]: A
    # must not unblock the pipeline on its own — the state says when the gate is
    # done, and until then its question keeps blocking.
    gate_id = open_gate(state)
    blocking = [q for q in questions if q["kind"] != "G" and is_pending(q)]
    if command != "approve" and command != "reject" and gate_id:
        blocking += [q for q in questions if q["id"] == gate_id]
    if not blocking:
        return
    ids = [q["id"] for q in blocking]
    if any(q["kind"] == "G" for q in blocking):
        # `answer` refuses a G id, so the general text would send the human to a
        # command that cannot work. A gate is closed from a terminal.
        die("QUESTIONS_PENDING — %d unanswered in %s: %s. %s is the approval gate: run "
            "'state.py approve --by \"<name>\"' or 'state.py reject --by \"<name>\" --why \"<text>\"' "
            "in your own terminal. Stage stays at %s."
            % (len(blocking), os.path.relpath(path, root), ", ".join(ids),
               ", ".join(q["id"] for q in blocking if q["kind"] == "G"),
               state.get("current_stage")), 4)
    die("QUESTIONS_PENDING — %d unanswered in %s: %s. Answer with 'state.py answer %s' or fill "
        "the [Answer]: lines and run 'state.py questions --sync'. Stage stays at %s."
        % (len(blocking), os.path.relpath(path, root), ", ".join(ids),
           " ".join("%s=<letter>" % i for i in ids), state.get("current_stage")), 4)


def gate_question_text(task_id):
    return "Approve %s for implementation?" % task_id


def request_gate(root, state, gate):
    """stage human_approval is the request, and the only way to make one: it
    writes the gate's own question, records *which* question it is, and starts
    the gate ungranted. A grant belongs to one gate, never to the task."""
    path = questions_path(root, state, None)
    with question_lock(path):
        lines, questions = parse_questions(path)
        number = max([q["number"] for q in questions if q["kind"] == "G"] or [0]) + 1
        gate_id = "G%d" % number
        while lines and not lines[-1].strip():
            lines.pop()
        lines = with_preamble(path, lines, state["task_id"])
        lines.extend(question_block({
            "id": gate_id,
            "question": "%s (gate: %s)" % (gate_question_text(state["task_id"]), gate),
            "options": [("A", "Approve"), ("B", "Reject — answer as `B: <reason>`")],
        }, "human_approval", None))
        write_questions(path, lines)
        _, questions = parse_questions(path)
    state["human_approval"].update({
        "required": True, "granted": False, "granted_by": None, "granted_at": None,
        "requested_at": now(), "gate_id": gate_id, "rejected_at": None,
        "via": None, "unattended": False,
        # The session the plan was presented in. The file route requires the
        # human's turn to come from *this* session — comparing session.json's two
        # own fields proves nothing, because whichever session ran last wrote
        # both of them.
        "requested_session": read_session(root).get("session_id"),
    })
    set_pending(root, state, questions, path)
    emit(root, state, "gate_requested", "%s: %s" % (gate_id, gate),
         {"gate": gate, "gate_id": gate_id,
          "requested_at": state["human_approval"]["requested_at"]})


def open_gate(state):
    """The one signal that a gate is open, and the one thing that names it.

    R11 words this as "a gate_requested event exists", and the first draft read
    the journal for one. It must not: events.jsonl is append-only, unprotected,
    and keyed on a caller-supplied task id, so a single hand-written line — or
    an `init --task-id` that reuses an old id — satisfied the precondition. The
    state is the contract and the path guard protects it; `stage human_approval`
    is the only writer, and approve/reject consume what it wrote.
    """
    approval = state.get("human_approval") or {}
    if approval.get("requested_at") and approval.get("gate_id"):
        return approval["gate_id"]
    return None


def close_gate(root, state, gate_id, choice, text, by, via):
    """approve and reject are the gate question's `answer`. Without this its
    question would stay pending and block the very next command (Risks 3), and
    `answer` still refuses a G id, because this is the only route that may close
    one. It closes the gate the state names — never "the last G in the file"."""
    path = questions_path(root, state, None)
    with question_lock(path):
        lines, questions = parse_questions(path)
        gates = [q for q in questions if q["id"] == gate_id]
        if not gates:
            return False
        lines[gates[0]["answer_at"]] = answer_line(choice, text, by, via)
        write_questions(path, lines)
        _, questions = parse_questions(path)
    set_pending(root, state, questions, path)
    return True


def human_turn(root, state):
    """Did a human take a turn in this project since the gate was requested?

    The evidence is .ai/state/session.json, which only context-guard.py writes,
    on UserPromptSubmit. It is what makes the file route different from the
    agent filling in the answer itself: the agent cannot advance last_prompt_at
    without the human sending a prompt. Weaker than a TTY, and documented as
    such — but it is a turn the human took, at a moment they could see the plan.
    """
    session = read_session(root)
    relative = os.path.relpath(session_path(root), root)
    turn = session.get("last_prompt_at")
    requested = (state.get("human_approval") or {}).get("requested_at")
    if not isinstance(turn, str) or not turn:
        return False, "there is no %s, so no human turn can be seen" % relative
    if not requested or turn < requested:
        return False, ("the last prompt in %s (%s) is older than the approval request (%s)"
                       % (relative, turn, requested))
    opened_in = (state.get("human_approval") or {}).get("requested_session")
    if not opened_in:
        # The gate was opened without a session on record — the hook had never
        # run in this project (Codex before /hooks, or a task older than the
        # install). There is then nothing to bind the turn to, and any later
        # session's prompt would do. The terminal route is unaffected; this
        # route fails closed, because it is the weaker of the two.
        return False, ("no session was recorded when the gate was requested, so a prompt in %s "
                       "cannot be tied to it — approve from your own terminal instead" % relative)
    if session.get("last_prompt_session") != opened_in:
        # One file per project, last writer wins, so session.json's own two
        # fields always agree after any real second session. The turn has to
        # come from the session the plan was presented in.
        return False, ("the last prompt in %s came from another session (%s, not %s, "
                       "which is where the gate was requested)"
                       % (relative, session.get("last_prompt_session"), opened_in))
    return True, ""


def close_gate_from_file(root, state, question, by):
    """R13: an [Answer]: filled into the gate's own question grants or rejects,
    but only behind a human turn in the session the plan was presented in — or
    AI_UNATTENDED, which says there is nobody to take one.

    The whole decision happens inside the questions lock and on a state re-read,
    because the human may be typing `reject` in their terminal in exactly these
    seconds: deciding before the lock and applying after it would overwrite them.
    """
    gate_id = question["id"]
    unattended = bool(os.environ.get("AI_UNATTENDED"))
    with question_lock(questions_path(root, state, None)):
        fresh = load(root, claim=False)
        if open_gate(fresh) != gate_id:
            # Somebody closed it between the parse and here: their outcome wins.
            return None
        state.clear()
        state.update(fresh)
        seen, why = (True, "") if unattended else human_turn(root, state)
        if not seen:
            die("APPROVAL_REFUSED — %s. Fill the answer, tell the session, and sync again, or run "
                "in your own terminal:\n  python3 %s --root %s approve --by %s"
                % (why, shlex.quote(os.path.abspath(__file__)), shlex.quote(root),
                   shlex.quote(by)), 5)
        approved = question["choice"] == "A"
        session = read_session(root)
        claim_runtime(root, state)
        state["human_approval"].update({
            "required": True, "granted": approved,
            "granted_by": by if approved else None,
            "granted_at": now() if approved else None,
            "requested_at": None, "gate_id": None, "requested_session": None,
            "via": "file" if approved else None, "unattended": approved and unattended,
        })
        if approved:
            state["human_approval"]["rejected_at"] = None
        if approved:
            record(state, "human_approval", "granted by %s via file" % by)
        else:
            state["next_action"] = "address the rejection: %s" % one_line(question["text"])
            state["human_approval"]["rejected_at"] = now()
            record(state, "gate_rejected", "%s: %s" % (by, question["text"] or "no reason given"))
        write_handoff(root, state, "stage")
        save(root, state)                 # durable first: the answer line is derived
        # The evidence, recorded beside the outcome: this is the weakest of the
        # three routes, and an audit has to be able to see what it rested on.
        evidence = {"session": session.get("last_prompt_session"),
                    "at": session.get("last_prompt_at"), "unattended": unattended}
        append_journal(root, state["task_id"], journal_line(
            state["task_id"], "gate_approved" if approved else "gate_rejected",
            "human" if not unattended else "agent",
            state.get("current_stage"), "%s by %s via file" % (gate_id, by),
            {"by": by, "gate_id": gate_id, "via": "file", "unattended": unattended,
             "tty": False, "evidence": evidence}
            if approved else {"by": by, "gate_id": gate_id, "why": question["text"],
                              "via": "file", "evidence": evidence}))
        close_gate(root, state, gate_id, question["choice"], question["text"], by, "file")
        save(root, state)
    return approved


def refuse_approval(root, state, gate_id, by, why):
    # Quoted: this project's own path has a space in it, and the command the
    # refusal prints is the only route a human without the flag has.
    die("APPROVAL_REFUSED — approval happens outside the agent. Run in your own terminal:\n"
        "  python3 %s --root %s approve --by %s\n"
        "or set [Answer]: A on %s in %s and tell the session to sync. An unattended run exports "
        "AI_UNATTENDED=1 in the launcher's environment; the journal then records the approval as "
        "unattended.\nRefused because %s."
        % (shlex.quote(os.path.abspath(__file__)), shlex.quote(root), shlex.quote(by), gate_id,
           os.path.relpath(questions_path(root, state, None), root), why), 5)


def cmd_approve(args, root):
    """The one thing the agent cannot do. A pending Q blocks this at exit 4
    before we get here; what is left is whether a gate is open and whether the
    approval comes from outside the agent (R11)."""
    state = load(root)
    gate_id = open_gate(state)
    if gate_id is None:
        if state["human_approval"].get("granted"):
            # The gate that was open has been granted and consumed. One approval
            # per gate, or the unattended signal in the journal is unreadable.
            print("already approved by %s at %s (via %s)"
                  % (state["human_approval"].get("granted_by"),
                     state["human_approval"].get("granted_at"),
                     state["human_approval"].get("via")))
            return
        die("APPROVAL_REFUSED — no gate was requested: 'state.py close' requests it for a full-mode "
            "task.", 5)
    tty = os.isatty(0)
    # A terminal is the stronger evidence: a launcher variable left in a human's
    # shell must not downgrade an approval they gave in person.
    via, why = human_route()
    if via is None:
        refuse_approval(root, state, gate_id, args.by, why)
    claim_runtime(root, state)
    state["human_approval"].update({
        "required": True, "granted": True, "granted_by": args.by, "granted_at": now(),
        "requested_at": None, "gate_id": None, "requested_session": None,
        "rejected_at": None, "via": via, "unattended": via == "unattended",
    })
    record(state, "human_approval", "granted by %s via %s" % (args.by, via))
    write_handoff(root, state, "stage")
    save(root, state)                     # durable first: the rest is derived
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], "gate_approved", "human" if via == "terminal" else "agent",
        state.get("current_stage"), "granted by %s via %s" % (args.by, via),
        {"by": args.by, "gate_id": gate_id, "via": via,
         "unattended": via == "unattended", "tty": tty}))
    if not close_gate(root, state, gate_id, "A", args.note, args.by, via):
        print("state.py: %s is not in %s — the gate was granted, answer it by hand"
              % (gate_id, os.path.relpath(questions_path(root, state, None), root)),
              file=sys.stderr)
    save(root, state)
    print("approved by %s (via %s)%s" % (args.by, via, " — recorded as unattended"
                                         if via == "unattended" else ""))


def cmd_reject(args, root):
    """Rejection needs no terminal: it cannot let anything through. It needs an
    open gate, though — otherwise it would erase a grant it never opened."""
    state = load(root)
    gate_id = open_gate(state)
    if gate_id is None:
        die("APPROVAL_REFUSED — no gate was requested: 'state.py close' requests it for a full-mode "
            "task.", 5)
    claim_runtime(root, state)
    state["human_approval"].update({
        "required": True, "granted": False, "granted_by": None, "granted_at": None,
        "requested_at": None, "gate_id": None, "via": None, "unattended": False,
    })
    state["human_approval"]["rejected_at"] = now()
    state["next_action"] = "address the rejection: %s" % one_line(args.why)
    record(state, "gate_rejected", "%s: %s" % (args.by, args.why))
    write_handoff(root, state, "stage")
    save(root, state)
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], "gate_rejected", "human", state.get("current_stage"),
        "%s: %s" % (args.by, args.why), {"by": args.by, "gate_id": gate_id, "why": args.why}))
    close_gate(root, state, gate_id, "B", args.why, args.by, "terminal" if os.isatty(0) else "prose")
    save(root, state)
    print("rejected by %s; stage stays at %s" % (args.by, state["current_stage"]))


# ---------------------------------------------- the schema-7 surface (redesign 2.2a)
#
# The old surface's commands were deleted in 2.6. Only `start` writes
# "schema": 7; a task in flight on the old surface — migration 0007 patched or
# not — is read or abandoned, never worked (route_surface). The legacy keys the scope guard
# reads (current_stage, approved_plan) are written beside the new ones, as one
# synthetic step "task" holding every file of the task (D2).

SCHEMA = 7
MODES = ["light", "guarded", "full", "full_irreversible"]
# tier_set compat (R18): the old budget tables price a task by its T-label.
MODE_TIER = {"light": "T2", "guarded": "T4", "full": "T5", "full_irreversible": "T6"}
REVIEW_TIERS = ["BALANCED", "STRONG"]
VERDICT_STATUS = {"pass": "passed", "pass_with_findings": "passed_with_findings",
                  "blockers_open": "blockers_open"}
FINDING_RE = re.compile(r"\[(BLOCKER|HIGH|MEDIUM|LOW|INFO)\]\s+([A-Z][0-9]+)\b")
OUT_OF_SCOPE_RE = re.compile(r"in_scope:\s*no\b", re.I)
def is_v7(state):
    return isinstance(state, dict) and state.get("schema") == SCHEMA


def apply_defaults_v7(state):
    """The keys every shared helper reads (questions, handoff, the gate) and the
    schema-7 ones; none of the old surface's own keys, so a schema-7 file holds
    only what its commands use."""
    task_id = state.get("task_id") or ""
    state.setdefault("owner_runtime", None)
    state.setdefault("resume_point", None)
    state.setdefault("cross_vendor_review", None)
    if not isinstance(state.get("questions"), dict):
        state["questions"] = {"file": ".ai/reports/%s/task.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    state["handoff"].setdefault("pending_to", None)
    state["handoff"].setdefault("pending_since", None)
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": False, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("gate_id", None), ("requested_session", None),
                         ("rejected_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    for key, default in (("files", []), ("tests", []), ("steps", []), ("amendments", []),
                         ("findings", []), ("diff", {}), ("gate", None), ("mode_override", None)):
        if not isinstance(state.get(key), type(default)) and not (default is None and key in state):
            state[key] = default
    if not isinstance(state.get("verify"), dict):
        state["verify"] = {}
    for key, default in (("status", "not_run"), ("e2e", "not_run"), ("suite_runs", 0), ("runs", [])):
        state["verify"].setdefault(key, default)
    if not isinstance(state.get("review"), dict):
        state["review"] = {}
    for key, default in (("status", "not_started"), ("passes", 0), ("tier", None),
                         ("findings", []), ("tree", None), ("log", []), ("closed", [])):
        state["review"].setdefault(key, default)
    return state


def load_v7(root):
    state = load(root)
    if not is_v7(state):
        die(old_surface_refusal(state))
    return state


def weight_policy(root):
    if weight is None:
        die("weight.py is missing beside state.py: reinstall the plugin")
    try:
        return weight.load_policy(root)[0]
    except (OSError, ValueError) as exc:
        die("cannot read the weight table: %s" % exc)
    return None                           # unreachable: die() exits


def mode_for(axes, policy, irreversible=False):
    """The mode six axis values earn under `policy`'s thresholds — weight.compute's
    rule, applied to re-scored axes; an irreversible_content hit is
    full_irreversible whatever the sum."""
    modes = policy.get("modes") or {}
    full = modes.get("full") or {}
    hard = full.get("hard_axes") or ["reversibility", "domain"]
    light_max = int((modes.get("light") or {}).get("max_w", 2))
    guarded_max = int((modes.get("guarded") or {}).get("max_w", 7))
    w = sum(int(axes.get(a) or 0) for a in weight.AXES)
    if irreversible or all(int(axes.get(a) or 0) >= 2 for a in hard):
        return "full_irreversible"
    if w >= int(full.get("min_w", guarded_max + 1)) or any(int(axes.get(a) or 0) >= 2 for a in hard):
        return "full"
    return "light" if w <= light_max else "guarded"


def higher_mode(a, b):
    return max(a, b, key=lambda m: MODES.index(m) if m in MODES else -1)


def mode_setting(policy, mode, key, default=None):
    """modes.<mode>.<key>; full_irreversible inherits what it does not say from full."""
    modes = policy.get("modes") or {}
    for name in ([mode, "full"] if mode == "full_irreversible" else [mode]):
        if key in (modes.get(name) or {}):
            return modes[name][key]
    return default


def read_text(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            data = fh.read(1 << 20)
    except OSError:
        return ""
    return "" if b"\0" in data[:8192] else data.decode("utf-8", "replace")


def added_lines(root, base_tree, rel):
    """The lines `rel` gained since `base_tree` — all of them for a new file — so
    content that was already there never raises a re-score."""
    before = ""
    if base_tree and sensors is not None:
        code, text = sensors.git(root, ["cat-file", "-p", "%s:%s" % (base_tree, rel)])
        before = text if code == 0 and "\0" not in text[:8192] else ""
    seen = {}
    for line in before.splitlines():
        seen[line] = seen.get(line, 0) + 1
    out = []
    for line in read_text(root, rel).splitlines():
        if seen.get(line):
            seen[line] -= 1
        else:
            out.append(line)
    return out


def rescore_weight(root, base_tree, files, current, policy):
    """Reversibility and domain from the diff's `files`, only upward (R26).

    It lives here, not in weight.py, because weight.py is at the spec's 300-line
    cap; the rules it applies are weight.json's, through weight.match. Returns
    {"axes", "raised": [{axis, from, to, evidence}], "operations", "irreversible"}.
    A pattern of `irreversible_content` in the lines a `needs_step` file gained is
    reversibility 2 and full_irreversible. The patterns are case-sensitive, as
    the SQL keywords they name are written: `rename()` in Python is not RENAME."""
    spec = policy.get("axes") or {}
    rules = policy.get("rules") or {}
    rev, dom = spec.get("reversibility") or {}, spec.get("domain") or {}
    axes = dict(current or {})
    found, operations = {}, []
    files = [f for f in dict.fromkeys(files or []) if f]
    for rel in files:
        hit = weight.match(rel, rev.get("irreversible"))
        if hit:
            found["reversibility"] = (2, "%s matches irreversible %s" % (rel, hit))
        elif weight.match(rel, rev.get("needs_step")):
            gained = added_lines(root, base_tree, rel)
            for pattern in rev.get("irreversible_content") or []:
                try:
                    rx = re.compile(pattern)
                except re.error:
                    continue
                line = next((ln for ln in gained if rx.search(ln)), None)
                if line is not None:
                    # The operation's keyword (DROP, ALTER …), not the pattern's
                    # source: it is what a human names in approve --confirm.
                    operations.append(rx.search(line).group(0).split()[0].upper())
                    if found.get("reversibility", (0,))[0] < 2:
                        found["reversibility"] = (2, "%s adds %r (irreversible_content %r)"
                                                  % (rel, line.strip()[:60], pattern))
            found.setdefault("reversibility", (1, "%s matches needs_step %s"
                                               % (rel, weight.match(rel, rev.get("needs_step")))))
        for value, key, said in ((2, "modules", "matches modules"), (1, "customer_visible", "is customer-visible:")):
            hit = weight.match(rel, dom.get(key))
            if hit and value > found.get("domain", (0,))[0]:
                found["domain"] = (value, "%s %s %s" % (rel, said, hit))
                break
    for hint in policy.get("hints") or []:
        hit = next((f for f in files if weight.match(f, hint.get("paths"))), None)
        if hit and hint.get("axis") == "domain":
            value, why = found.get("domain", (0, ""))
            found["domain"] = (min(2, value + int(rules.get("hint_raises_by", 1))),
                               "%shint %s (%s)" % (why + "; " if why else "", hint.get("note", ""), hit))
            break
    raised = []
    for axis in rules.get("rescore_axes") or ["reversibility", "domain"]:
        if axis not in found:
            continue
        value, why = found[axis]
        if value > int(axes.get(axis) or 0):
            raised.append({"axis": axis, "from": int(axes.get(axis) or 0), "to": value, "evidence": why})
            axes[axis] = value
    return {"axes": axes, "raised": raised, "operations": sorted(set(operations)),
            "irreversible": bool(operations)}


def task_files(state):
    """Every file and glob the task may touch: its files, its tests, every step's."""
    out = list(state.get("files") or []) + list(state.get("tests") or [])
    for step in state.get("steps") or []:
        out += list(step.get("files") or []) + list(step.get("tests") or [])
    return list(dict.fromkeys(out))


def arm_scope(state):
    """The legacy view the scope guard (hooks/guard/scope.py) reads (D2): stage implementation and one
    step holding every file of the task, for as long as the task is open."""
    state["current_stage"] = "implementation"
    state["approved_plan"] = {"ref": "inline", "current_step_id": "task", "steps": [{
        "step_id": "task", "description": state.get("goal"), "allowed_files": task_files(state),
        "forbidden_files": [], "forbidden_reason": "not part of this task",
        "required_tests": list(state.get("tests") or []), "status": "in_progress"}]}


def current_tree(root):
    return safe_sensor(sensors.snapshot_tree, root)


def logs_dir(root, task_id):
    return os.path.join(root, ".ai", "state", "logs", task_id)


def ensure_logs(root, task_id):
    """.ai/state/logs/<task>/, ignored by its own .gitignore (D4), so the shipped
    gitignore snippet stays as it is."""
    base = os.path.join(root, ".ai", "state", "logs")
    os.makedirs(os.path.join(base, task_id), exist_ok=True)
    ignore = os.path.join(base, ".gitignore")
    if not os.path.exists(ignore):
        with open(ignore, "w", encoding="utf-8") as fh:
            fh.write("*\n")


def task_md_path(root, state):
    return os.path.join(root, ".ai", "reports", state["task_id"], "task.md")


def parse_steps(text, plan_file):
    """--steps "id:a,b:t;id2:c" or --plan-file F.json ([{id, files, tests}])."""
    raw = []
    if plan_file:
        try:
            with open(plan_file, encoding="utf-8") as fh:
                raw = json.load(fh)
        except (OSError, ValueError) as exc:
            die("--plan-file %s: %s" % (plan_file, exc))
        if not isinstance(raw, list) or not all(isinstance(s, dict) for s in raw):
            die("--plan-file holds a JSON list of {\"id\", \"files\", \"tests\"}")
        raw = [(str(s.get("id") or ""), ",".join(s.get("files") or []), ",".join(s.get("tests") or []))
               for s in raw]
    for chunk in [c for c in (text or "").split(";") if c.strip()]:
        parts = chunk.split(":")
        raw.append((parts[0], parts[1] if len(parts) > 1 else "", parts[2] if len(parts) > 2 else ""))
    steps = []
    for step_id, files, tests in raw:
        step_id = one_line(step_id, 40)
        if not step_id or not _split_files(files):
            die("a step is id:files[:tests], with at least one file: %r" % ":".join((step_id, files, tests)))
        if step_id in [s["id"] for s in steps]:
            die("step id %s appears twice" % step_id)
        steps.append({"id": step_id, "files": _split_files(files), "tests": _split_files(tests),
                      "status": "pending", "tree_before": None, "tree_after": None})
    return steps


def parse_declares(items):
    declared = {}
    for item in items or []:
        m = re.match(r"^(\w+)=(\d{1,3}):(.*\S.*)$", item, re.S)
        if not m:
            die("--declare %r: write axis=n:\"evidence\" — a declaration without its evidence is not one"
                % item)
        declared[m.group(1)] = (int(m.group(2)), m.group(3).strip())
    return declared


def next_action_for(state):
    return {
        "light": "edit, then 'state.py verify --scope all', then 'state.py close'",
        "guarded": "edit, 'state.py verify --scope all', one review ('state.py review'), then 'state.py close'",
        "full": "edit, 'state.py verify --scope all', one STRONG review, then 'state.py close' "
                "requests the human's approval",
        "full_irreversible": "edit, 'state.py verify --scope all', one STRONG review, then 'state.py close'; "
                             "the human approves with --confirm \"<operation>\"",
    }.get(state.get("mode"), "edit, verify, close")


def cmd_start(args, root):
    """The task, its weight and its mode in one call; the scope guard is armed."""
    if args.amend:
        start_amend(args, root)
        return
    missing = [flag for flag, value in (("--goal", args.goal), ("--workflow", args.workflow),
                                        ("--files", args.files)) if not value]
    if missing:
        die("start needs %s (or --amend to widen the task in flight)" % ", ".join(missing))
    if args.workflow not in WORKFLOWS:
        die("workflow must be one of: %s" % ", ".join(WORKFLOWS))
    existing = load(root, required=False, claim=False)
    if existing and existing.get("current_stage") != "done":
        die("task %s is in flight: finish it with 'state.py close' (or 'close --abandon'), or widen it "
            "with 'state.py start --amend --files \"+a\" --why \"…\"'" % existing.get("task_id"))
    files, tests = _split_files(args.files), _split_files(args.tests)
    if not files:
        # An empty list would arm a scope guard that allows everything.
        die("--files must name at least one file or glob the task may touch")
    if current_tree(root) is None:
        die("start needs a git repository: the two facts close decides by are measured on its tree")
    steps = parse_steps(args.steps, args.plan_file)
    policy = weight_policy(root)
    concrete = [f for f in files if not any(c in f for c in "*?[")]
    try:
        result = weight.compute(root, concrete, parse_declares(args.declare), args.goal, policy=policy)
    except ValueError as exc:
        die(str(exc))
    except (TypeError, AttributeError) as exc:
        die("the weight table is malformed: %s" % exc)
    mode, override = result.mode, None
    if args.mode:
        if args.mode not in MODES:
            die("--mode takes one of: %s" % ", ".join(MODES))
        if not args.by:
            die("--mode needs --by \"<who>\": an override is journaled with its author")
        if args.mode == mode:
            args.mode = None              # the weight already says so: nothing to override
    if args.mode:
        if MODES.index(args.mode) < MODES.index(mode):
            via, why = human_route()
            if via is None:
                die("APPROVAL_REFUSED — lowering the mode from %s to %s is a human's decision. Run it in "
                    "your own terminal:\n  python3 %s --root %s start … --mode %s --by %s\nRefused because %s."
                    % (mode, args.mode, shlex.quote(os.path.abspath(__file__)), shlex.quote(root),
                       args.mode, shlex.quote(args.by), why), 5)
        override = {"from": mode, "to": args.mode, "by": args.by, "why": args.why, "ts": now()}
        mode = args.mode
    task_id = valid_task_id(args.task_id) if args.task_id else next_task_id(root)
    base_tree = current_tree(root)
    state = {
        "schema": SCHEMA, "task_id": task_id, "goal": args.goal, "workflow": args.workflow,
        "mode": mode, "weight": dict(result.as_dict(), lines=weight.render(result).split("\n"),
                                     tree=base_tree, computed_at=now(), rescores=[], operations=[]),
        "mode_override": override, "stage": "build", "files": files, "tests": tests,
        "steps": steps, "amendments": [], "findings": [],
        "diff": {"base_tree": base_tree, "base_commit": safe_sensor(sensors.head_commit, root)},
        "gate": None, "owner_runtime": RUNTIME if RUNTIME in RUNTIMES else None,
        "created": now(), "created_at": now(), "history": [],
    }
    apply_defaults_v7(state)
    if steps:
        steps[0].update(status="in_progress", tree_before=base_tree)
    arm_scope(state)
    state["next_action"] = next_action_for(state)
    emit(root, state, "task_started", one_line(args.goal, 200),
         {"goal": args.goal, "workflow": args.workflow, "mode": mode, "schema": SCHEMA})
    emit(root, state, "weight_set", "W %d → %s" % (result.w, result.mode),
         {"w": result.w, "mode": result.mode, "axes": result.axes, "hints": result.hints,
          "unknown": result.unknown})
    if override:
        emit(root, state, "mode_set", "%s -> %s by %s" % (override["from"], mode, args.by),
             {"from": override["from"], "to": mode, "by": args.by, "why": args.why},
             actor="human" if MODES.index(mode) < MODES.index(override["from"]) else "agent")
    emit(root, state, "tier_set", "%s (mode %s, compat)" % (MODE_TIER[mode], mode),
         {"tier": MODE_TIER[mode], "mode": mode, "w": result.w})
    set_resume_point(state)
    write_handoff(root, state, "start")
    save(root, state)
    write_task_md(root, state)
    print(weight.render(result))
    if override:
        print("mode: %s (override of %s by %s)" % (mode, override["from"], args.by))
    advice = int((policy.get("rules") or {}).get("steps_advice_over", 8))
    if len(steps) > advice:
        print("advice: %d steps, over %d — fewer, larger steps cost fewer handoffs (not a gate)"
              % (len(steps), advice))
    print("%s started: %s · %d files in scope · %s"
          % (task_id, mode, len(task_files(state)), os.path.relpath(task_md_path(root, state), root)))
    print("next: %s" % state["next_action"])
    advise(state)


def start_amend(args, root):
    """R25: the task's files grow in place, journaled, never back to a plan."""
    state = load_v7(root)
    added = [f.lstrip("+").strip() for f in _split_files(args.files)]
    added = [f for f in added if f]
    if not added or not (args.why or "").strip():
        die("--amend needs --files \"+a,+b\" and --why \"<why the task needs them>\"")
    new = [f for f in added if f not in state["files"]]
    if not new:
        print("scope unchanged: %s already in the task" % ", ".join(added))
        return
    state["files"] += new
    state["amendments"].append({"ts": now(), "added": new, "why": args.why})
    arm_scope(state)
    emit(root, state, "scope_change", "+%s — %s" % (", ".join(new), one_line(args.why, 200)),
         {"added": new, "why": args.why})
    save(root, state)
    write_task_md(root, state)
    print("scope amended: +%s (%d files in scope)" % (", ".join(new), len(task_files(state))))


def rescore_v7(root, state, policy, at):
    """R26 at verify and close: raises are applied, journaled and printed; the
    task never restarts and the other four axes are not recomputed."""
    if sensors is None:
        return
    diff = safe_sensor(sensors.diff_files, root, state["diff"].get("base_tree"), current_tree(root))
    if not diff:
        return
    current = state["weight"].get("axes") or {}
    got = rescore_weight(root, state["diff"].get("base_tree"), [d["path"] for d in diff], current, policy)
    before = state["mode"]
    ops = sorted(set(state["weight"].get("operations") or []) | set(got["operations"]))
    # Only what the diff moved can move the mode: an unchanged measurement must
    # not undo a mode a human lowered (R27).
    was = mode_for(current, policy, bool(state["weight"].get("operations")))
    now_measured = mode_for(got["axes"], policy, bool(ops))
    mode = higher_mode(before, now_measured) if now_measured != was else before
    if not got["raised"] and mode == before and ops == (state["weight"].get("operations") or []):
        return
    state["weight"].update(axes=got["axes"], w=sum(got["axes"].values()), operations=ops)
    state["mode"] = mode
    for r in got["raised"]:
        emit(root, state, "weight_raised", "%s %d -> %d at %s: %s" % (r["axis"], r["from"], r["to"], at,
                                                                     one_line(r["evidence"], 200)),
             dict(r, mode_from=before, mode_to=mode))
        state["weight"]["rescores"].append("%s at %s: %s %d → %d — %s"
                                           % (now(), at, r["axis"], r["from"], r["to"], r["evidence"]))
        print("re-score: %s %d → %d — %s" % (r["axis"], r["from"], r["to"], one_line(r["evidence"], 120)))
    if mode != before:
        state["weight"]["rescores"].append("%s at %s: mode %s → %s%s" % (
            now(), at, before, mode, " (irreversible: %s)" % ", ".join(ops) if got["irreversible"] else ""))
        emit(root, state, "tier_set", "%s (mode %s, compat)" % (MODE_TIER[mode], mode),
             {"tier": MODE_TIER[mode], "mode": mode, "w": state["weight"]["w"]})
        state["next_action"] = next_action_for(state)
        print("mode: %s → %s — %s" % (before, mode, state["next_action"]))


def full_suite(run):
    """A run of the whole suite: one narrowed with --files proves only those files."""
    return run.get("scope") == "suite" and not run.get("expected_fail") and not run.get("files")


def suite_green(state):
    return any(full_suite(r) and r.get("exit") == 0 for r in state["verify"]["runs"])


def run_v7(root, state, scope, args, tcfg):
    """One scope's command, to the end, logged under .ai/state/logs/; returns the run."""
    command = safe_sensor(sensors.command_for, root, scope) or ""
    if not command:
        die("no command for scope '%s' in .ai/policies/testing.md — write it down first" % scope)
    files = _split_files(args.files)
    if files:
        command = safe_sensor(sensors.expand_files, command, files) or command
    runs = state["verify"]["runs"]
    n = len(runs) + 1
    ensure_logs(root, state["task_id"])
    log = os.path.join(logs_dir(root, state["task_id"]), "%s-%d.log" % (scope, n))
    before = current_tree(root)
    result = safe_sensor(sensors.run_command, root, command, log, tcfg.get("timeout_seconds", 1800),
                         tcfg.get("log_max_bytes", 2097152))
    if result is None:
        die("sensors.py is not installed beside state.py — run the project's command yourself")
    after = current_tree(root)
    # A tree that moved during the run was not the tree the run tested: the run
    # is kept in the record, but stands for no tree at all.
    run = {"n": n, "scope": scope, "exit": result["exit"], "tree": after if after == before else None,
           "tree_moved": after != before,
           "log": os.path.relpath(log, root), "ts": now(), "expected_fail": args.expect == "fail",
           "runtime": RUNTIME, "command": command, "duration_s": result["duration_s"],
           "after_fix": args.after_fix or None, "files": files}
    runs.append(run)
    if scope == "suite":
        state["verify"]["suite_runs"] += 1
        state["verify"]["status"] = ("passing" if run["exit"] == 0 else
                                     "env_failure" if run["exit"] is None else "failing")
    elif scope == "e2e":
        state["verify"]["e2e"] = "passing" if run["exit"] == 0 else "failing"
        state["verify"]["e2e_tree"] = run["tree"]
    if run["tree_moved"]:
        print("tree moved during the run: run %d stands for no tree — run it again on a still tree" % n)
    emit(root, state, "verify_run", "%s run %d: exit %s" % (scope, n, run["exit"]),
         {k: run[k] for k in ("n", "scope", "exit", "tree", "log", "expected_fail")})
    if full_suite(run) and run["exit"] is not None and run["tree"]:
        other = [r for r in runs[:-1] if full_suite(r) and r.get("tree") == run["tree"]
                 and r.get("runtime") != RUNTIME and (r.get("exit") == 0) != (run["exit"] == 0)
                 and r.get("exit") is not None]
        red, green = (run, other[-1]) if other and run["exit"] != 0 else \
            (other[-1], run) if other else (None, None)
        if red:
            # R19: the same tree green under one runtime and red under the other, in
            # either order, goes into task.md. A red under Codex is best effort and
            # never a gate; a red under any other runtime is the change's, and the
            # green elsewhere does not answer it (two_facts).
            state["findings"].append("%s: suite red under %s (run %d) and green under %s (run %d) on %s"
                                     % (now(), red.get("runtime"), red["n"], green.get("runtime"),
                                        green["n"], run["tree"][:9]))
            if red.get("runtime") == "codex":
                print("finding: red under %s on a tree green under %s — recorded in task.md, close is not "
                      "blocked" % (red.get("runtime"), green.get("runtime")))
            else:
                print("red under %s on a tree green under %s — recorded in task.md; the red is the change's "
                      "and close is blocked until it is green under %s"
                      % (red.get("runtime"), green.get("runtime"), red.get("runtime")))
    print("%s run %d: exit %s in %ds" % (scope, n, run["exit"], run["duration_s"]))
    print("command: %s" % command)
    print("log: %s" % run["log"])
    if result.get("detail"):
        print(result["detail"])
    return run


def e2e_na_refusal(root, state):
    """Why e2e cannot be declared not applicable now, or None. The last e2e run
    decides, on whatever tree it ran: a red flow is fixed and run again, never
    declared away by an edit and a declaration; a run that could not finish
    (exit None) is run again."""
    runs = [r for r in state["verify"]["runs"] if r.get("scope") == "e2e"]
    if not runs or runs[-1].get("exit") == 0:
        return None
    last, tree = runs[-1], current_tree(root)
    if last.get("exit") is None:
        return ("e2e run %d did not finish: run it again with 'verify --scope e2e' — an environment "
                "failure is not a reason to declare e2e not applicable" % last["n"])
    where = "on this tree" if tree and last.get("tree") == tree else \
        "on %s, and no e2e run since has passed" % (last.get("tree") or "a moving tree")[:9]
    return ("e2e run %d is red %s: a failing flow is fixed and 'verify --scope e2e' run again, not "
            "declared not applicable" % (last["n"], where))


def e2e_na(root, state, why):
    refusal = e2e_na_refusal(root, state)
    if refusal:
        die(refusal)
    tree = current_tree(root)
    state["verify"]["e2e_tree"] = tree
    state["verify"]["e2e"] = "not_applicable"
    state["verify"]["e2e_why"] = why
    emit(root, state, "verify_run", "e2e not applicable: %s" % one_line(why, 200),
         {"scope": "e2e", "exit": None, "not_applicable": True, "why": why})
    print("e2e: not applicable — %s" % one_line(why, 200))


E2E_NONE = "e2e_command: none in .ai/policies/testing.md"


def e2e_none(root):
    return (safe_sensor(sensors.command_for, root, "e2e") or "").strip() == "none"


def cmd_verify(args, root):
    """Run, record, re-score up; exit 0 green, 1 red, 6 SUITE_BUDGET (R20)."""
    state = load_v7(root)
    policy = weight_policy(root)
    tcfg = policy.get("tests") or {}
    scope = args.scope
    if args.expect and (scope != "step" or not args.files):
        die("--expect fail is for one test shown failing before the fix: --scope step --files <test>")
    if args.e2e and (scope not in ("all", "e2e") or args.e2e[0] != "not-applicable"
                     or not args.e2e[1].strip()):
        die('--e2e takes: not-applicable "<why the change cannot reach an e2e flow>", with --scope all or e2e')
    if scope == "all" and args.files:
        die("--files narrows one scope; --scope all runs the whole suite and e2e")
    if args.e2e and e2e_na_refusal(root, state):
        die(e2e_na_refusal(root, state))         # before the suite runs, not after (N3)
    max_runs = int(tcfg.get("max_suite_runs", 2))
    if scope in ("suite", "all") and state["verify"]["suite_runs"] >= max_runs:
        if not args.by:
            die("SUITE_BUDGET — %d suite runs; weight.json allows %d (tests.max_suite_runs). Running it "
                "again is not the next move: the human decides. In their own terminal:\n  python3 %s "
                "--root %s verify --scope %s --by \"<name>\""
                % (state["verify"]["suite_runs"], max_runs, shlex.quote(os.path.abspath(__file__)),
                   shlex.quote(root), scope), 6)
        via, why = human_route()
        if via is None:
            die("APPROVAL_REFUSED — a run past the suite budget is the human's, from their own terminal."
                "\nRefused because %s." % why, 5)
        emit(root, state, "human_set", "suite run %d past the budget by %s via %s"
             % (state["verify"]["suite_runs"] + 1, args.by, via),
             {"field": "suite_runs", "value": state["verify"]["suite_runs"] + 1, "by": args.by,
              "via": via, "unattended": via == "unattended"},
             actor="human" if via == "terminal" else "agent")
    green_before = suite_green(state)
    state["stage"] = "verify"
    code = 0
    if scope == "e2e" and args.e2e:
        e2e_na(root, state, args.e2e[1])
    elif scope == "e2e" and e2e_none(root):
        e2e_na(root, state, E2E_NONE)            # `none` is a declaration, not a command (N1)
    else:
        run = run_v7(root, state, "suite" if scope == "all" else scope, args, tcfg)
        code = run["exit"]
        if args.expect == "fail":
            run["bites"] = code not in (0, None)
            print("expected fail: %s" % ("the test fails without the fix — it bites" if run["bites"]
                                         else "the test passes without the fix — it does not bite yet"))
            code = 0 if run["bites"] else 1
        elif scope == "all" and code == 0:
            if args.e2e:
                e2e_na(root, state, args.e2e[1])
            elif not mode_setting(policy, state["mode"], "e2e", False):
                state["verify"]["e2e"] = "not_required"
                print("e2e: not required in %s mode" % state["mode"])
            elif e2e_none(root):
                e2e_na(root, state, E2E_NONE)
            else:
                code = run_v7(root, state, "e2e", args, tcfg)["exit"]
        elif scope == "all":
            print("e2e: not run — the suite is red")
    rescore_v7(root, state, policy, "verify")
    if not green_before and suite_green(state):
        write_handoff(root, state, "verify")
    save(root, state)
    write_task_md(root, state)
    if scope in ("suite", "all"):
        print("suite runs used: %d of %d" % (state["verify"]["suite_runs"], max_runs))
    sys.exit(0 if code == 0 else 1)


def read_report(source):
    if not source:
        return ""
    if source == "-":
        return sys.stdin.read()
    try:
        with open(source, encoding="utf-8") as fh:
            return fh.read()
    except OSError as exc:
        die("--report %s: %s" % (source, exc))
    return ""                             # unreachable: die() exits


def open_findings(text, severities=("BLOCKER", "HIGH")):
    """Labels of `severities` whose block does not say in_scope: no."""
    hits = list(FINDING_RE.finditer(text or ""))
    out = []
    for i, m in enumerate(hits):
        block = text[m.start():hits[i + 1].start() if i + 1 < len(hits) else len(text)]
        if m.group(1) in severities and not OUT_OF_SCOPE_RE.search(block):
            out.append(m.group(2))
    return out


# "VERDICT pass", "VERDICT: pass", "## VERDICT pass" and the shipped reviewer's
# "## VERDICT" section with its "verdict: pass" line (ai/agents/reviewer.md).
VERDICT_LINE_RE = re.compile(r"^(?:#+[ \t]*)?verdict[ \t]*:?[ \t]*(pass_with_findings|blockers_open|pass)\b",
                             re.M | re.I)


def verdict_matches_findings(verdict, text):
    """The verdict a reviewer's FINDINGS block allows: an in-scope BLOCKER is
    blockers_open, an in-scope HIGH is not a pass, and a VERDICT line in the
    block is the verdict. The block is the evidence; a verdict without it is a
    claim nobody can audit."""
    if not (text or "").strip() or "FINDINGS" not in text:
        die("review needs the reviewer's FINDINGS block: --report - (stdin) or --report FILE")
    blockers, highs = (open_findings(text, (sev,)) for sev in ("BLOCKER", "HIGH"))
    said = VERDICT_LINE_RE.search(text)
    if said and said.group(1) != verdict:
        die("--verdict %s, but the report's VERDICT line says %s" % (verdict, said.group(1)))
    if blockers and verdict != "blockers_open":
        die("the report has an in-scope BLOCKER (%s): the verdict is blockers_open, not %s"
            % (", ".join(blockers), verdict))
    if highs and verdict == "pass":
        die("the report has an in-scope HIGH (%s): the verdict is pass_with_findings or blockers_open"
            % ", ".join(highs))


def cmd_review(args, root):
    """One pass recorded; the pass past review_rounds_max is the human's (exit 6)."""
    state = load_v7(root)
    policy = weight_policy(root)
    review = state["review"]
    if args.closes:
        review_closes(root, state, _split_files(args.closes))
        return
    if not args.verdict or not args.tier:
        die("review needs --verdict pass|pass_with_findings|blockers_open and --tier BALANCED|STRONG")
    rounds = int(policy.get("review_rounds_max", 2))
    by_human = None
    if review["passes"] >= rounds:
        if not args.by:
            die("REVIEW_BUDGET — %d review passes; weight.json allows %d (review_rounds_max). The next "
                "verdict is the human's, in their own terminal:\n  python3 %s --root %s review --verdict "
                "<verdict> --tier %s --by \"<name>\"" % (review["passes"], rounds,
                                                         shlex.quote(os.path.abspath(__file__)),
                                                         shlex.quote(root), args.tier), 6)
        via, why = human_route()
        if via is None:
            die("APPROVAL_REFUSED — a verdict past the review budget is the human's, from their own "
                "terminal.\nRefused because %s." % why, 5)
        by_human = (args.by, via)
    wanted = mode_setting(policy, state["mode"], "reviewer", "BALANCED")
    if wanted in REVIEW_TIERS and REVIEW_TIERS.index(args.tier) < REVIEW_TIERS.index(wanted):
        die("%s mode needs a %s review (weight.json modes.%s.reviewer); this one was %s"
            % (state["mode"], wanted, state["mode"], args.tier))
    text = read_report(args.report)
    if not by_human:
        verdict_matches_findings(args.verdict, text)
    labels = [m.group(2) for m in FINDING_RE.finditer(text)]
    status = VERDICT_STATUS[args.verdict]
    tree = current_tree(root)
    review.update(status=status, passes=review["passes"] + (0 if by_human else 1), tier=args.tier,
                  findings=open_findings(text), tree=tree, ts=now(),
                  runs_at=len(state["verify"]["runs"]))
    review["log"].append({"n": len(review["log"]) + 1, "tier": args.tier, "verdict": args.verdict,
                          "focus": args.focus, "text": text[:20000], "tree": tree, "ts": now(),
                          "runtime": RUNTIME, "by": by_human[0] if by_human else None})
    state["stage"] = "review"
    if by_human:
        emit(root, state, "human_set", "review %s by %s via %s" % (args.verdict, by_human[0], by_human[1]),
             {"field": "review", "value": status, "by": by_human[0], "via": by_human[1],
              "unattended": by_human[1] == "unattended"},
             actor="human" if by_human[1] == "terminal" else "agent")
    emit(root, state, "review_verdict", "%s on %s (pass %d)" % (args.verdict, args.tier, review["passes"]),
         {"verdict": args.verdict, "tier": args.tier, "pass_n": review["passes"], "labels": labels,
          "focus": args.focus})
    state["next_action"] = ("fix the blockers, 'state.py verify --scope all --after-fix \"…\"', one scoped "
                            "re-review" if status == "blockers_open" else "'state.py close'")
    write_handoff(root, state, "review")
    save(root, state)
    write_task_md(root, state)
    print("review: %s (%s, pass %d of %d)%s" % (status, args.tier, review["passes"], rounds,
                                               " — open: %s" % ", ".join(review["findings"])
                                               if review["findings"] else ""))


def review_closes(root, state, labels):
    """passed_with_findings → passed once a green suite run after the verdict, on
    a tree the fix changed, is the tree now (§3a, without a second review)."""
    review = state["review"]
    if review["status"] != "passed_with_findings":
        die("--closes is for a passed_with_findings review; this one is %s" % review["status"])
    unknown = [l for l in labels if l not in review["findings"]]
    if not labels or unknown:
        die("--closes names open findings (%s); not open: %s"
            % (", ".join(review["findings"]) or "none", ", ".join(unknown) or "none given"))
    tree = current_tree(root)
    runs = [r for r in state["verify"]["runs"][review.get("runs_at") or 0:]
            if full_suite(r) and r.get("exit") == 0]
    if not runs or runs[-1].get("tree") != tree or tree == review.get("tree"):
        die("findings %s stay open: they close on a green 'state.py verify --scope suite|all --after-fix "
            "\"…\"' after the verdict, on a tree the fix changed, which is the tree now" % ", ".join(labels))
    review["findings"] = [l for l in review["findings"] if l not in labels]
    review["closed"] = list(review.get("closed") or []) + labels
    if not review["findings"]:
        review["status"] = "passed"
    emit(root, state, "findings_closed", "%s closed by suite run %d on %s"
         % (", ".join(labels), runs[-1]["n"], tree[:9]),
         {"labels": labels, "run": runs[-1]["n"], "tree": tree})
    save(root, state)
    write_task_md(root, state)
    print("findings closed: %s; review %s" % (", ".join(labels), review["status"]))


def two_facts(root, state, tree):
    """R6: (a) a green suite on the tree as it is now; (b) the diff since the base
    tree inside the task's files. Each is (green, why)."""
    runs = [r for r in state["verify"]["runs"] if full_suite(r)]
    here = [r for r in runs if tree and r.get("tree") == tree]
    green = [r for r in here if r.get("exit") == 0]
    if not tree:
        a = (False, "the tree cannot be measured (not a git repository)")
    elif not runs:
        a = (False, "no whole-suite 'verify --scope suite|all' has run")
    elif not here:
        a = (False, "the tree changed after the last verify (run %d on %s, now %s)"
             % (runs[-1]["n"], (runs[-1].get("tree") or "?")[:9], tree[:9]))
    elif not green:
        a = (False, "the suite is red on this tree (run %d, exit %s)" % (here[-1]["n"], here[-1].get("exit")))
    else:
        # R19: a red under Codex on a tree green under another runtime is waived,
        # in either order (Codex is best effort). Any other red stands until a
        # later green under its own runtime: a green elsewhere does not answer it.
        others = any(g.get("runtime") != "codex" for g in green)

        def answered(r):
            return (r.get("runtime") == "codex" and others) or any(
                g["n"] > r["n"] and g.get("runtime") == r.get("runtime") for g in green)
        unwaived = [r for r in here if r.get("exit") != 0 and not answered(r)]
        before = [g for g in green if unwaived and g["n"] < unwaived[-1]["n"]]
        if unwaived and before:
            a = (False, "the suite went red on this tree after run %d (run %d under %s)"
                 % (before[-1]["n"], unwaived[-1]["n"], unwaived[-1].get("runtime")))
        elif unwaived:
            a = (False, "the suite is red on this tree under %s (run %d); green under %s (run %d) does "
                        "not answer it" % (unwaived[-1].get("runtime"), unwaived[-1]["n"],
                                           green[-1].get("runtime"), green[-1]["n"]))
        else:
            a = (True, "suite green on %s (run %d)" % (tree[:9], green[-1]["n"]))
    diff = safe_sensor(sensors.diff_files, root, state["diff"].get("base_tree"), tree)
    allowed = task_files(state)
    outside = [d["path"] for d in diff or [] if not sensors.scope_any(d["path"], allowed)]
    if diff is None:
        b = (False, "the diff since the base tree cannot be measured")
    elif outside:
        b = (False, "outside the task's files: %s" % ", ".join(outside[:5])
             + (" (+%d more)" % (len(outside) - 5) if len(outside) > 5 else ""))
    else:
        b = (True, "%d changed files, all in the task's files" % len(diff))
    return {"a": a, "b": b, "diff": diff or [], "outside": outside}


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
        owed.append(("review", "the blockers fixed, 'verify --scope all --after-fix \"…\"', one scoped re-review"))
    elif not reviewed:
        owed.append(("review", "one review verdict (%s mode: %s)"
                               % (mode, mode_setting(policy, mode, "reviewer", "BALANCED"))))
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


def approve_command(root, state):
    ops = state["weight"].get("operations") or []
    confirm = (" --confirm \"<what it does, naming %s>\"" % (" and ".join(ops) or "the operation")
               if state["mode"] == "full_irreversible" else "")
    return "python3 %s --root %s approve --by \"<name>\"%s" % (
        shlex.quote(os.path.abspath(__file__)), shlex.quote(root), confirm)


def cmd_close_v7(args, root):
    """Two facts, the mode table, the gate, the archive; exits 2 naming what is owed."""
    state = load_v7(root)
    if args.abandon:
        archive_v7(root, state, current_tree(root), "abandoned")
        return
    policy = weight_policy(root)
    tree = current_tree(root)
    if state["human_approval"].get("rejected_at"):
        # A rejection is answered by changing the work, not by asking again: on the
        # tree the human rejected, close refuses; on a changed one it asks anew.
        if (state.get("gate") or {}).get("tree") == tree:
            die("APPROVAL_REFUSED — rejected at %s and nothing changed since. Address the rejection, "
                "'verify --scope all', then close again; or 'state.py close --abandon'."
                % state["human_approval"]["rejected_at"], 5)
        state["human_approval"]["rejected_at"] = None
    for step in state["steps"]:
        if step.get("status") == "in_progress":
            step.update(status="done", tree_after=tree)
            emit(root, state, "step_done", "%s (finished by close)" % step["id"],
                 {"step_id": step["id"], "by": "close"}, legacy="step_completed")
    rescore_v7(root, state, policy, "close")
    facts = two_facts(root, state, tree)
    state["facts"] = {"a": list(facts["a"]), "b": list(facts["b"]), "tree": tree, "at": now()}
    owed = close_owed(state, facts, tree, policy)
    if owed:
        state["next_action"] = owed[0][1]
        set_resume_point(state)
        write_handoff(root, state, "close")
        save(root, state)
        write_task_md(root, state)
        die("%s required (%s mode) — %s. To drop the task instead: 'state.py close --abandon'."
            % ("review" if any(k == "review" for k, _ in owed) else "verify", state["mode"],
               " · ".join(text for _, text in owed)), 2)
    if state["mode"] in ("full", "full_irreversible") and not gate_approved_for(state, tree):
        if state["human_approval"].get("granted") and (state.get("gate") or {}).get("tree") == tree:
            print("the approval on record does not cover this task: full_irreversible needs approve "
                  "--confirm naming %s — asking again" % " and ".join(state["weight"].get("operations") or
                                                                      ["the operation"]))
        request_gate(root, state, "human_approval")
        state["gate"] = {"requested_at": state["human_approval"]["requested_at"],
                         "gate_id": state["human_approval"]["gate_id"], "tree": tree,
                         "approved_by": None, "approved_at": None, "approved_tree": None, "via": None,
                         "confirm": None, "operations": list(state["weight"].get("operations") or [])}
        state["stage"] = "ship"
        state["next_action"] = "the human approves in their own terminal, then 'state.py close' again"
        set_resume_point(state)
        write_handoff(root, state, "close")
        save(root, state)
        write_task_md(root, state)
        print("%s %s ready for approval: %s" % (state["task_id"], state["mode"], state.get("goal")))
        print("facts: (a) %s · (b) %s" % (facts["a"][1], facts["b"][1]))
        print("approve in your own terminal, then run close again:\n  %s" % approve_command(root, state))
        return
    if state.get("gate") and not state["gate"].get("approved_by"):
        # The questions-file route grants through human_approval alone.
        approval = state["human_approval"]
        state["gate"].update(approved_by=approval.get("granted_by"), approved_at=approval.get("granted_at"),
                             via=approval.get("via"), approved_tree=state["gate"].get("tree"))
    archive_v7(root, state, tree, "closed", facts)


def archive_v7(root, state, tree, result, facts=None):
    """§Changes and §Verdict into task.md, the state into .ai/state/logs/<task>/,
    and nothing else under reports/ (D4, R8)."""
    base = state["diff"].get("base_tree")
    stats = {f["path"]: f for f in (safe_sensor(sensors.numstat, root, base, tree) or [])} if base and tree else {}
    names = (facts or {}).get("diff") or safe_sensor(sensors.diff_files, root, base, tree) or []
    state["changes"] = [{"path": d["path"], "status": d["status"],
                         "added": (stats.get(d["path"]) or {}).get("added", 0),
                         "deleted": (stats.get(d["path"]) or {}).get("deleted", 0),
                         "binary": (stats.get(d["path"]) or {}).get("binary", False)} for d in names]
    state["stage"] = "done"
    state["current_stage"] = "done"
    state["result"] = result
    state["closed_at"] = now()
    state["next_action"] = "none — task %s" % result
    emit(root, state, "task_closed", "abandoned" if result == "abandoned" else "",
         {"abandoned": result == "abandoned", "mode": state["mode"], "w": state["weight"].get("w")})
    write_task_md(root, state)
    ensure_logs(root, state["task_id"])
    target = os.path.join(logs_dir(root, state["task_id"]), "state.json")
    state["updated_at"] = now()
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with contextlib.suppress(OSError):
        os.remove(handoff_path(root))
    remove_state(root)
    print("%s %s (%s): %s" % (state["task_id"], result, state["mode"],
                              os.path.relpath(task_md_path(root, state), root)))
    print("state: %s" % os.path.relpath(target, root))


def cmd_step_done_v7(args, root):
    """A multi-step task's step is done when its diff stays inside the task."""
    state = load_v7(root)
    steps = state["steps"]
    if not steps:
        die("step-done is for a multi-step guarded or full task; this one is one scope — verify, then close")
    step = next((s for s in steps if s["id"] == args.step_id), None)
    if step is None:
        die("no step %s (have: %s)" % (args.step_id, ", ".join(s["id"] for s in steps)))
    if step["status"] == "done":
        print("step %s already done" % step["id"])
        return
    tree = current_tree(root)
    diff = safe_sensor(sensors.diff_files, root, step.get("tree_before") or state["diff"].get("base_tree"), tree)
    outside = [d["path"] for d in diff or [] if not sensors.scope_any(d["path"], task_files(state))]
    if outside:
        die("SCOPE_CHANGE_REQUIRED — step %s changed %s, outside the task's files. Widen the task in "
            "place: state.py start --amend --files \"%s\" --why \"…\""
            % (step["id"], ", ".join(outside), ",".join("+" + p for p in outside)), 6)
    step.update(status="done", tree_after=tree)
    emit(root, state, "step_done", "%s: %d files changed" % (step["id"], len(diff or [])),
         {"step_id": step["id"], "files": len(diff or [])}, legacy="step_completed")
    following = next((s for s in steps if s["status"] == "pending"), None)
    if following:
        following.update(status="in_progress", tree_before=tree)
        emit(root, state, "step_started", following["id"], {"step_id": following["id"], "kind": "step"})
    save(root, state)
    write_task_md(root, state)
    print("step %s done%s" % (step["id"], "; next: %s" % following["id"] if following else "; all steps done"))


def cmd_approve_v7(args, root):
    """approve, plus the gate's tree and, for full_irreversible, the operation
    the human names (--confirm). The grant itself is cmd_approve's, unchanged."""
    state = load_v7(root)
    ops = state["weight"].get("operations") or []
    confirm = (args.confirm or "").strip()
    gate = state.get("gate") or {}
    if open_gate(state):
        tree = current_tree(root)
        if gate.get("tree") != tree:
            # The work changed after close put it up: approving now would sign
            # a tree nobody presented.
            die("APPROVAL_REFUSED — the tree changed after close asked for this approval (%s, now %s). "
                "Reject it ('reject --by \"<name>\" --why \"the tree changed\"'); the next close asks "
                "again for the tree as it is." % ((gate.get("tree") or "?")[:9], (tree or "?")[:9]), 5)
        if state["mode"] == "full_irreversible" and not confirm_names(confirm, ops):
            die("APPROVAL_REFUSED — full_irreversible needs --confirm \"<what it does>\" naming %s"
                % (" and ".join(ops) or "the irreversible operation"), 5)
    cmd_approve(args, root)
    state = load(root, claim=False)
    gate = state.get("gate") or {}
    if state["human_approval"].get("granted") and gate and not gate.get("approved_by"):
        gate.update(approved_by=args.by, approved_at=state["human_approval"].get("granted_at"),
                    via=state["human_approval"].get("via"), confirm=confirm or None,
                    approved_tree=gate.get("tree"))
        state["gate"] = gate
        save(root, state)
        write_task_md(root, state)


def status_lines(root, state):
    """≤ 20 lines; read-only (the facts are measured, nothing is written)."""
    lines = ["root: %s" % root]
    if not state or not state.get("task_id"):
        return lines + ["task: none — no task in flight", schema_line(root)]
    events, _ = read_journal(root, state["task_id"])
    last = events[-1] if events else {}
    pending = (state.get("questions") or {}).get("pending") or []
    lines.append("task: %s — %s" % (state["task_id"], one_line(state.get("goal"), 140)))
    if not is_v7(state):
        lines += ["tier: %s · workflow %s · stage %s" % (state.get("risk_tier") or "?", state.get("workflow"),
                                                        state.get("current_stage")),
                  "next: %s" % (one_line(state.get("next_action"), 160) or "?"),
                  "old surface (schema < 7): /status reads it directly"]
    else:
        w = state.get("weight") or {}
        policy = weight_policy(root)
        tree = current_tree(root)
        facts = two_facts(root, state, tree)
        steps = state.get("steps") or []
        cur = next((s for s in steps if s.get("status") == "in_progress"), None)
        review, ver, gate = state["review"], state["verify"], state.get("gate") or {}
        override = state.get("mode_override") or {}
        lines += [
            "mode: %s · W %s · workflow %s%s" % (state["mode"], w.get("w"), state.get("workflow"),
                                                 " · override %s → %s by %s" % (override.get("from"),
                                                                               override.get("to"),
                                                                               override.get("by"))
                                                 if override else ""),
            "axes: %s" % " ".join("%s %s" % (a, (w.get("axes") or {}).get(a, "?")) for a in weight.AXES),
            "stage: %s · next: %s" % (state.get("stage"), one_line(state.get("next_action"), 140)),
            ("steps: %d of %d done — current %s" % (len([s for s in steps if s["status"] == "done"]), len(steps),
                                                    cur["id"] if cur else "none")
             if steps else "steps: one scope"),
            "files: %d in scope — %s" % (len(task_files(state)), ", ".join(task_files(state)[:4])
                                         + (" (+%d more)" % (len(task_files(state)) - 4)
                                            if len(task_files(state)) > 4 else "")),
            "verify: suite %s · runs %d/%s · e2e %s" % (ver["status"], ver["suite_runs"],
                                                        (policy.get("tests") or {}).get("max_suite_runs", 2),
                                                        ver.get("e2e")),
            "facts: (a) %s — %s" % ("green" if facts["a"][0] else "RED", facts["a"][1]),
            "       (b) %s — %s" % ("green" if facts["b"][0] else "RED", facts["b"][1]),
            "review: %s (%d of %s) · tier %s%s" % (review["status"], review["passes"],
                                                   policy.get("review_rounds_max", 2), review.get("tier") or "-",
                                                   " · open %s" % ", ".join(review["findings"])
                                                   if review["findings"] else ""),
            "gate: %s" % ("approved by %s%s" % (gate["approved_by"], " · confirm \"%s\"" % gate["confirm"]
                                                if gate.get("confirm") else "")
                          if gate.get("approved_by") else "requested %s, waiting for the human" % gate.get("gate_id")
                          if open_gate(state) else "not requested"
                          if state["mode"] in ("full", "full_irreversible") else "none in %s mode" % state["mode"]),
            "findings: %d recorded in task.md" % len(state.get("findings") or []),
        ]
    lines += ["questions: %d pending%s" % (len(pending), " — %s" % ", ".join(map(str, pending[:4])) if pending else ""),
              schema_line(root),
              "last event: %s" % (" ".join(one_line(last.get(k), 80) for k in ("ts", "event", "detail")
                                           if last.get(k)) or "none")]
    return lines[:20]


def schema_line(root):
    try:
        with open(os.path.join(root, ".ai", "VERSION"), encoding="utf-8") as fh:
            project = fh.read().strip() or "0"
    except OSError:
        project = "0"
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    try:
        names = os.listdir(os.path.join(here, "project-update", "migrations"))
    except OSError:
        names = []
    numbers = [int(n[:4]) for n in names if re.match(r"\d{4}_", n)]
    plugin = str(max(numbers)) if numbers else "?"
    behind = project.isdigit() and plugin.isdigit() and int(project) < int(plugin)
    return "schema: project %s · plugin %s%s" % (project, plugin, " — behind: run /project-update" if behind else "")


def cmd_status(args, root):
    state = load(root, required=False, claim=False)
    if args.json:
        out = {"root": root, "task_id": (state or {}).get("task_id"), "schema": (state or {}).get("schema")}
        if is_v7(state):
            tree = current_tree(root)
            facts = two_facts(root, state, tree)
            out.update({k: state.get(k) for k in ("goal", "workflow", "mode", "stage", "next_action",
                                                  "files", "tests", "steps", "verify", "review", "gate",
                                                  "mode_override", "findings")})
            out["weight"] = {k: (state.get("weight") or {}).get(k) for k in ("w", "axes", "hints", "unknown",
                                                                            "operations")}
            out["facts"] = {"a": list(facts["a"]), "b": list(facts["b"]), "tree": tree}
            out["questions_pending"] = len((state.get("questions") or {}).get("pending") or [])
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return
    print("\n".join(status_lines(root, state)))


def md_cell(text):
    return one_line(text, 200).replace("|", "\\|")


def task_md_lines(root, state):
    """A pure function of the state and the journal: eight sections (§Interfaces).
    §Questions is "none" here; write_task_md keeps the section already on disk."""
    events, _ = read_journal(root, state["task_id"])
    w = state.get("weight") or {}
    override = state.get("mode_override")
    out = ["# %s — %s" % (state["task_id"], one_line(state.get("goal"))), "",
           "%s · %s · started %s · %s" % (state.get("workflow"), state.get("mode"), state.get("created"),
                                          state.get("owner_runtime") or "unknown"), "",
           "## Weight", "", "```"] + list(w.get("lines") or []) + ["```"]
    if override:
        out.append("override: %s → %s by %s at %s%s" % (override.get("from"), override.get("to"),
                                                        override.get("by"), override.get("ts"),
                                                        " — %s" % one_line(override["why"])
                                                        if override.get("why") else ""))
    out += ["re-score %s" % one_line(line, 300) for line in w.get("rescores") or []]
    out += ["", "## Plan", "", "files: %s" % (", ".join(state.get("files") or []) or "none"),
            "tests: %s" % (", ".join(state.get("tests") or []) or "none")]
    for step in state.get("steps") or []:
        out.append("- %s · %s · %s · %s" % (step["id"], ", ".join(step["files"]),
                                            ", ".join(step["tests"]) or "no tests", step["status"]))
    out += ["amended %s: +%s — %s" % (a["ts"], ", ".join(a["added"]), one_line(a["why"]))
            for a in state.get("amendments") or []]
    out += ["", QUESTIONS_SECTION, "", "none"]
    out += ["", "## Verify", "", "| n | scope | exit | tree | log | expected_fail |", "|---|---|---|---|---|---|"]
    for r in state["verify"]["runs"]:
        out.append("| %s | %s | %s | %s | %s | %s |" % (r["n"], r["scope"], r.get("exit"),
                                                        (r.get("tree") or "-")[:9], md_cell(r.get("log")),
                                                        "yes" if r.get("expected_fail") else "no"))
    out.append("")
    out.append("suite %s · e2e %s%s · suite runs %d" % (
        state["verify"]["status"], state["verify"].get("e2e"),
        " (%s)" % one_line(state["verify"]["e2e_why"]) if state["verify"].get("e2e_why") else "",
        state["verify"]["suite_runs"]))
    out += ["finding: %s" % one_line(f, 300) for f in state.get("findings") or []]
    out += ["", "## Review", ""]
    for p in state["review"]["log"]:
        out += ["### Pass %d — %s, %s%s%s" % (p["n"], p["tier"], p["verdict"],
                                             " (focus %s)" % p["focus"] if p.get("focus") else "",
                                             " by %s" % p["by"] if p.get("by") else ""), ""]
        # A fence longer than any backtick run in the text, so a report quoting
        # code cannot close it early.
        fence = "`" * max([3] + [len(run) + 1 for run in re.findall(r"`+", p.get("text") or "")])
        out += ([fence] + p["text"].rstrip("\n").split("\n") + [fence]) if p.get("text", "").strip() \
            else ["no FINDINGS block"]
        out.append("")
    if not state["review"]["log"]:
        out += ["none yet", ""]
    if state["review"].get("closed"):
        out += ["closed by a green run: %s" % ", ".join(state["review"]["closed"]), ""]
    out += ["## Changes", ""]
    changes = state.get("changes")
    if changes is None:
        out.append("measured at close")
    else:
        kind = {"A": "New", "D": "Delete"}
        out += ["| File | Change | New/Edit/Delete |", "|---|---|---|"]
        out += ["| %s | %s | %s |" % (md_cell(c["path"]), "binary" if c.get("binary") else
                                      "+%d −%d" % (c["added"], c["deleted"]), kind.get(c["status"], "Edit"))
                for c in changes]
        out += ["", "+%d −%d lines, %d files" % (sum(c["added"] for c in changes),
                                                 sum(c["deleted"] for c in changes), len(changes))]
    gate, facts = state.get("gate") or {}, state.get("facts") or {}
    handoffs = len([e for e in events if e.get("event") == "handoff_written"])
    out += ["", "## Verdict", "",
            "close: %s" % (state.get("result") or "open — %s" % one_line(state.get("next_action"))),
            "facts: (a) %s · (b) %s" % tuple(
                "%s — %s" % ("green" if facts[k][0] else "RED", facts[k][1]) if facts.get(k) else "not measured"
                for k in ("a", "b")),
            "gate: %s" % ("requested %s at %s; approved by %s at %s via %s" % (
                gate.get("gate_id"), gate.get("requested_at"), gate.get("approved_by") or "-",
                gate.get("approved_at") or "-", gate.get("via") or "-") if gate else "none"),
            "confirm: %s" % (gate.get("confirm") or "none"),
            "handoffs: %d · suite runs: %d · review passes: %d" % (handoffs, state["verify"]["suite_runs"],
                                                                   state["review"]["passes"])]
    return out


def write_task_md(root, state):
    """Rewritten whole and atomically after every change; best effort, because
    the state is the contract and task.md is rendered from it — except
    §Questions, which is read back from disk under the questions lock, so an
    [Answer]: line a human filled survives until `questions --sync` reads it."""
    path = task_md_path(root, state)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with question_lock(path):
            before, _, after = split_task_md(task_md_lines(root, state))
            section = question_lines(path)
            if not any(HEADING_RE.match(line) for line in section):
                section = ["", "none"]
            text = "\n".join(before + section + ([""] if section[-1] else []) + after) + "\n"
            with open(tmp, "w", encoding="utf-8") as fh:
                fh.write(text)
            os.replace(tmp, path)
    except Exception as exc:  # pylint: disable=broad-exception-caught  # derived artefact: never fatal
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        print("state.py: task.md not written (%s)" % exc, file=sys.stderr)


def old_surface_refusal(state):
    return ("task %s runs on the old surface (schema %s), whose commands were removed in redesign 2.6: "
            "finish it with the plugin version that started it, or drop it with 'state.py close --abandon'"
            % (state.get("task_id"), state.get("schema") or "<7"))


def abandon_old(_args, root):
    """close --abandon for a task the old surface started: the record moves to
    .ai/state/logs/<task>/state.json as it is, and nothing else is measured."""
    state = load(root)
    state["result"] = "abandoned"
    state["closed_at"] = now()
    emit(root, state, "task_closed", "abandoned", {"abandoned": True, "surface": "old"})
    ensure_logs(root, state["task_id"])
    target = os.path.join(logs_dir(root, state["task_id"]), "state.json")
    state["updated_at"] = now()
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with contextlib.suppress(OSError):
        os.remove(handoff_path(root))
    remove_state(root)
    print("%s abandoned (old surface)" % state["task_id"])
    print("state: %s" % os.path.relpath(target, root))


def route_surface(root, args):
    """A task the old surface started (schema < 7) is read (status, handoff,
    questions without --sync) or dropped (close --abandon); every command that
    works on it refuses."""
    if args.command not in TASK_COMMANDS:
        return
    state = load(root, required=False, claim=False)
    if state is None or is_v7(state) or (args.command == "questions" and not args.sync):
        return
    if args.command == "close" and args.abandon:
        args.func = abandon_old
        return
    die(old_surface_refusal(state))


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".", help="project directory (default: search upwards for .ai/)")
    parser.add_argument("--runtime", choices=RUNTIMES,
                        help="overrides AI_RUNTIME and detection for this call")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("step-done"); p.add_argument("step_id")
    p.add_argument("--force", action="store_true",
                   help="accepted for older callers; it forces nothing")
    p.set_defaults(func=cmd_step_done_v7)

    who = os.environ.get("USER") or "unknown"
    p = sub.add_parser("ask"); p.add_argument("question", nargs="?")
    p.add_argument("--option", action="append", default=[]); p.add_argument("--recommend")
    p.add_argument("--context", default=""); p.add_argument("--gate")
    p.add_argument("--batch"); p.add_argument("--topic"); p.add_argument("--by", default="")
    p.set_defaults(func=cmd_ask)

    p = sub.add_parser("answer"); p.add_argument("assignment", nargs="*")
    p.add_argument("--prose"); p.add_argument("--by", default=who)
    # `file` is not offered: it is what --sync writes, and it is the one route
    # that is recorded as a human's.
    p.add_argument("--via", choices=["picker", "prose"], default="prose")
    p.add_argument("--topic"); p.set_defaults(func=cmd_answer)

    p = sub.add_parser("questions"); p.add_argument("--pending", action="store_true")
    p.add_argument("--sync", action="store_true"); p.add_argument("--topic")
    p.add_argument("--by", default=who)
    p.add_argument("--format", choices=["md", "prose", "json"], default="prose")
    p.set_defaults(func=cmd_questions)

    p = sub.add_parser("handoff")
    p.add_argument("--print", dest="print_it", action="store_true")
    p.add_argument("--reason", choices=["stage", "precompact", "manual", "session-start"],
                   default="manual")
    p.add_argument("--to", choices=RUNTIMES)
    p.add_argument("--for", dest="for_", choices=["continue", "review"], default="continue")
    p.add_argument("--why", default="")
    p.set_defaults(func=cmd_handoff)

    p = sub.add_parser("profile"); p.add_argument("action", nargs="?", choices=["detect", "set"])
    p.add_argument("plan", nargs="?")
    p.add_argument("--field")
    p.add_argument("--runtime", dest="detect_runtime", choices=RUNTIMES)
    p.add_argument("--open", action="store_true")
    p.add_argument("--tier", choices=["FAST", "BALANCED", "STRONG", "EXPERT"])
    p.add_argument("--other", action="store_true"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("weight"); p.add_argument("--files", default="")
    p.add_argument("--goal", default=""); p.add_argument("--declare", action="append", default=[])
    out = p.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true"); out.add_argument("--long", action="store_true")
    out.add_argument("--mirror", action="store_true"); p.set_defaults(func=cmd_weight)

    p = sub.add_parser("event"); p.add_argument("type"); p.add_argument("--detail", default="")
    p.add_argument("--data"); p.set_defaults(func=cmd_event)

    p = sub.add_parser("approve"); p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--confirm", default="", help="the operation a full_irreversible task performs")
    p.set_defaults(func=cmd_approve_v7)

    p = sub.add_parser("reject"); p.add_argument("--by", required=True)
    p.add_argument("--why", required=True); p.set_defaults(func=cmd_reject)

    p = sub.add_parser("close")
    p.add_argument("--abandon", action="store_true", help="archive without the checks")
    p.set_defaults(func=cmd_close_v7)

    p = sub.add_parser("start"); p.add_argument("--goal", default="")
    p.add_argument("--workflow", default=""); p.add_argument("--files", default="")
    p.add_argument("--tests", default=""); p.add_argument("--declare", action="append", default=[])
    p.add_argument("--mode"); p.add_argument("--by", default=""); p.add_argument("--why", default="")
    p.add_argument("--steps", default=""); p.add_argument("--plan-file", dest="plan_file")
    p.add_argument("--task-id"); p.add_argument("--amend", action="store_true")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("verify")
    p.add_argument("--scope", required=True, choices=["step", "suite", "e2e", "all"])
    p.add_argument("--files", default=""); p.add_argument("--expect", choices=["fail"])
    p.add_argument("--e2e", nargs=2, metavar=("not-applicable", "WHY"))
    p.add_argument("--after-fix", dest="after_fix", default="")
    p.add_argument("--by", default=""); p.set_defaults(func=cmd_verify)

    p = sub.add_parser("review"); p.add_argument("--verdict", choices=sorted(VERDICT_STATUS))
    p.add_argument("--tier", choices=REVIEW_TIERS); p.add_argument("--focus", choices=["security"])
    p.add_argument("--report", default=""); p.add_argument("--closes", default="")
    p.add_argument("--by", default=""); p.set_defaults(func=cmd_review)

    p = sub.add_parser("status"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_status)

    global RUNTIME, MUTATING              # pylint: disable=global-statement
    args = parser.parse_args()
    if getattr(args, "topic", None):
        # Topic mode never touches .ai/: it must work where there is none (I11).
        args.func(args, find_docs_root(args.root))
        return
    if args.command == "profile":
        # Read-only and task-free: it answers where there is no .ai/ at all.
        RUNTIME = args.runtime or os.environ.get("AI_RUNTIME") or \
            ("claude" if os.environ.get("CLAUDECODE") else "unknown")
        args.func(args, None)
        return
    root = find_root(args.root)
    RUNTIME = detect_runtime(args.runtime, root)
    MUTATING = args.command in MUTATING_COMMANDS
    route_surface(root, args)
    if args.command in BLOCKING_COMMANDS and not getattr(args, "abandon", False):
        guard_pending(root, args.command)
    args.func(args, root)


if __name__ == "__main__":
    main()
