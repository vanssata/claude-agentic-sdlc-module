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
  state.py init   --goal G --workflow W [--task-id ID] [--root DIR]
  state.py get    [--field current_stage] [--root DIR]
  state.py stage  <stage> [--note TEXT]
  state.py risk   <T0..T6> [--note TEXT] [--by NAME]   # --by, outside the agent, to LOWER one
  state.py triage <T0..T6> [--note TEXT] [--context TEXT]   discovery+context+impact+risk in one call
  state.py quick  --goal G --workflow W --tier <T0..T4> --files a,b [--note TEXT] [--context TEXT]
                                         init+triage+one-step plan in one call: the direct path below T5
  state.py plan   --ref PATH --steps STEPS.json
  state.py remediate --files a,b [--note TEXT]   one extra step R<n> for the batch of test/review fixes;
                                         allowed = every finished step's files + the ones named
  state.py step   <step_id>
  state.py step-done <step_id> [--force]    measures the step's diff against its allowed files
                                         (exit 6 asks for a split) and against the tier's budget,
                                         always a warning; a path scope above the tier is a hint
  state.py step-split <step_id> --files a,b [--note TEXT]   move part of a step into its own
  state.py review-gate                   # all sensors green at or below T3 -> review_status=skipped_green
  state.py test-run --scope step|suite|e2e [--files a,b] [--env-retry]
                                         runs the project's own command to the end, records it,
                                         and puts the output in a file instead of the context
  state.py set    <field> <value>        # test_status, e2e_status, review_status, security_status, next_action
  state.py risks  --add TEXT | --clear
  state.py ask    "<question>" --option "A: text" [--option ...] [--recommend A] [--gate G] [--topic S]
  state.py ask    --batch FILE.json [--topic SLUG]
  state.py answer Q1=B [Q2=X:"text"] [--by NAME] [--via picker|prose|file] | --prose "1B 2A 3: text"
  state.py questions [--pending] [--sync] [--format md|prose|json] [--topic SLUG]
  state.py note   decision|rejected|failed "<text>" [--why TEXT] [--error TEXT]
  state.py handoff [--print] [--reason stage|precompact|manual|session-start]
  state.py handoff --to claude|codex [--for continue|review] [--why TEXT]
                                         move the task to the other runtime: it must resume there
                                         (exit 7 RUNTIME_HANDOFF_PENDING from anywhere else)
  state.py profile [--field a.b.c] [--tier FAST|BALANCED|STRONG|EXPERT] [--other] [--json]
                                         the installed plan's tables (read-only, no task needed)
  state.py weight --files a,b [--goal G] [--declare axis=n:"why"]... [--json|--long]
  state.py weight --mirror               six axes and a mode, read-only (no task needed);
                                         --mirror writes .ai/policies/weight.md from weight.json
  state.py events [--last N] [--type t1,t2] [--task ID] [--format lines|jsonl]
  state.py event  <type> [--detail TEXT] [--data JSON]   # for hooks; type must be in EVENT_TYPES
  state.py approve --by NAME [--note TEXT]   # outside the agent: a TTY, or AI_UNATTENDED
  state.py reject  --by NAME --why TEXT
  state.py done   [--abandon]
  state.py archive                       # move current.json into .ai/reports/<task_id>/state.json
  state.py close                         # done + archive in one call

The schema-7 surface (redesign 2.2a), beside the commands above until 2.6. Only
`start` writes "schema": 7, and close, step-done and approve take the new path
only for such a task; every other state keeps the commands above, unchanged:
  state.py start  --goal G --workflow W --files a,b [--tests t] [--declare axis=n:"why"]...
                  [--mode M --by WHO [--why TEXT]] [--steps "id:a,b:t;..." | --plan-file F.json]
  state.py start  --amend --files "+c,+d" --why TEXT     widen the task in place (R25)
  state.py verify --scope step|suite|e2e|all [--files a,b] [--expect fail]
                  [--e2e not-applicable WHY] [--after-fix WHAT] [--by WHO]
  state.py review --verdict pass|pass_with_findings|blockers_open --tier BALANCED|STRONG
                  --report -|FILE [--focus security] [--by WHO]  |  review --closes "H1,M2"
  state.py close  [--abandon]            two facts, the mode table, the gate, the archive
  state.py step-done <id>                a multi-step guarded or full task
  state.py status [--json]               what /status prints
  approve --by WHO [--confirm "<what it does>"]   full_irreversible: the confirm names every
                                                  operation (DROP, ALTER …) as a word
"""

import argparse
import contextlib
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

STAGES = [
    "discovery", "context", "impact_analysis", "risk_classification",
    "plan", "plan_review", "implementation", "test", "adversarial_review",
    "security_review", "release_report", "human_approval", "done",
]
TIERS = ["T0", "T1", "T2", "T3", "T4", "T5", "T6"]
WORKFLOWS = ["feature", "bugfix", "refactoring", "hotfix", "investigation"]
TEST_STATUS = ["not_run", "passing", "existing_failure", "new_regression", "env_failure", "unknown"]
E2E_STATUS = ["not_run", "passing", "failing", "not_applicable"]
REVIEW_STATUS = ["not_started", "in_progress", "blockers_open", "passed_with_findings", "passed",
                 "skipped_green"]
# The values a review writes. Each one is a pass, and a task gets
# review_rounds_max of them before the next verdict is the human's (§3b).
REVIEW_VERDICTS = ("blockers_open", "passed_with_findings", "passed")
SECURITY_STATUS = ["not_applicable", "not_started", "in_progress", "passed", "failed"]

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
NOTE_KINDS = ["decision", "rejected", "failed"]

# The questions file is written by state.py and never by a model (R1). One regex
# per line (I2), so a hand edit that keeps the shape round-trips exactly.
QUESTIONS_HEADER = """# Questions — %s
<!-- Written by state.py. Answer with `state.py answer Q1=B`, or fill the [Answer]: lines and run
     `state.py questions --sync`. Do not edit the questions themselves. -->
"""
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
# records, reads or answers (R3). done --abandon is exempt: abandoning a task is
# how an unanswerable question is closed.
BLOCKING_COMMANDS = {
    "stage", "triage", "plan", "step", "step-done", "step-split", "test-run", "remediate",
    "approve", "done", "close", "verify",
}
RUNTIMES = ["claude", "codex"]

JOURNAL_MAX_BYTES = 4096
DETAIL_MAX = 500
ERROR_MAX = 1000

# Resolved once in main() and read by emit(): one process serves one runtime.
RUNTIME = "unknown"
# The commands that change the task. Only these take ownership of it: reading a
# task from the other runtime, or writing a note about it, is not a handoff.
MUTATING_COMMANDS = {
    "init", "stage", "risk", "triage", "quick", "plan", "remediate", "step", "step-done",
    "step-split", "test-run", "review-gate", "set", "risks", "modules", "ask", "answer",
    "done", "close", "start", "verify", "review",
}
MUTATING = False

# `skipped_green` is missing on purpose: it is a verdict review-gate reaches from
# measurements, never a value anybody may assert. A review nobody did and nobody
# measured would otherwise be one `set` away.
SETTABLE_REVIEW_STATUS = [v for v in REVIEW_STATUS if v != "skipped_green"]

SETTABLE = {
    "test_status": TEST_STATUS,
    "e2e_status": E2E_STATUS,
    "review_status": SETTABLE_REVIEW_STATUS,
    "security_status": SECURITY_STATUS,
    "next_action": None,
    "context_summary_ref": None,
    "goal": None,
}


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
    6 SCOPE_CHANGE_REQUIRED / run budget / REVIEW_BUDGET (I1, WP4 I4; no
    DIFF_BUDGET_EXCEEDED since redesign 1.2) ·
    7 RUNTIME_HANDOFF_PENDING · 8 DIRECT_MODE_CAP (WP5 I4; one meaning per code)."""
    print("state.py: %s" % message, file=sys.stderr)
    sys.exit(code)


def state_path(root):
    return os.path.join(root, ".ai", "state", "current.json")


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
        state["questions"] = {"file": ".ai/reports/%s/questions.md" % task_id, "pending": []}
    if not isinstance(state.get("handoff"), dict):
        state["handoff"] = {"file": ".ai/state/handoff.md", "written_at": None, "reason": None}
    if not isinstance(state.get("human_approval"), dict):
        state["human_approval"] = {"required": True, "granted": False,
                                   "granted_by": None, "granted_at": None}
    for key, default in (("requested_at", None), ("gate_id", None), ("requested_session", None),
                         ("rejected_at", None), ("via", None), ("unattended", False)):
        state["human_approval"].setdefault(key, default)
    # Schema 4 (WP4 I2). A task that started before the gates existed answers
    # every command; its diff simply reads `unavailable`, because the tree it
    # started from was never recorded and cannot be invented afterwards.
    if not isinstance(state.get("diff"), dict):
        state["diff"] = {}
    state["diff"].setdefault("base_commit", None)
    state["diff"].setdefault("base_tree", None)
    if not isinstance(state["diff"].get("task"), dict):
        state["diff"]["task"] = {"files": 0, "added": 0, "deleted": 0, "lines": 0,
                                 "excluded_lines": 0, "unbudgeted_lines": 0, "tree": None,
                                 "measured_at": None, "status": "not_measured"}
    state["diff"].setdefault("rescored_tier", None)
    state["diff"].setdefault("rescore_reasons", [])
    state["diff"].setdefault("rescore_hints", [])
    state["diff"].setdefault("over_budget", False)
    if not isinstance(state.get("sensors"), dict):
        state["sensors"] = {"file": ".ai/reports/%s/sensors.json" % task_id,
                            "tree": None, "verdict": None, "checked_at": None}
    if not isinstance(state.get("tests"), dict):
        state["tests"] = {"runs": [], "suite_runs": 0}
    if not isinstance(state.get("risk_tier_lowered"), dict):
        state["risk_tier_lowered"] = {"by": None, "at": None, "from": None}
    # Schema 5 (WP5 I4): a task handed to the other runtime, and a review asked of it.
    state["handoff"].setdefault("pending_to", None)
    state["handoff"].setdefault("pending_since", None)
    state.setdefault("cross_vendor_review", None)
    for step in ((state.get("approved_plan") or {}).get("steps") or []):
        if isinstance(step, dict):
            step.setdefault("kind", "remediation"
                            if str(step.get("step_id", "")).startswith("R") else "implementation")
            step.setdefault("tree_before", None)
            step.setdefault("diff", None)
    return state


def load(root, required=True, claim=None):
    path = state_path(root)
    if not os.path.exists(path):
        if required:
            die("no task in flight (%s does not exist). Start one with state.py init." % path)
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


def read_profile(runtime=None):
    """<home>/claude-agentic/profile.json, written by install.sh; {} when absent,
    which turns every plan budget into a no-op."""
    try:
        with open(os.path.join(runtime_home(runtime or own_runtime()), "claude-agentic",
                               "profile.json"), encoding="utf-8") as fh:
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
    runtime = other_runtime() if args.other else own_runtime()
    prof = read_profile(runtime)
    if not prof:
        die("no plan profile for %s (%s/claude-agentic/profile.json); install.sh writes it"
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


def direct_mode_cap(root, tier):
    """quick reaches only as far as the active pipeline profile allows. The cap
    is the project's, not the plan's — the tier comes from the scope of a
    change, and so does the mode it runs in — and it is read in this order:
    `pipeline_profiles.<profile>.direct_mode_cap` when written (a value that is
    not a tier is an error, never an open gate); else the highest tier whose
    `mode` is "direct" in that profile, counted as the unbroken run from T0;
    else T4 for `solo` and no cap for a profile that declares no direct mode
    at all, as before. A file that still describes the six-tier table caps
    every profile at T3, which was quick's limit when that table was written.
    A malformed file is an error, never an open gate."""
    profile_name, cap = "solo", None
    try:
        with open(os.path.join(root, ".ai", "policies", "risk-tiers.json"), encoding="utf-8") as fh:
            policy = json.load(fh)
    except OSError:
        policy = None
    except ValueError as exc:
        die("risk-tiers.json is not valid JSON: %s" % exc)
    if policy is None:
        cap = DIRECT_MODE_CAP
    else:
        try:
            if not isinstance(policy, dict):
                raise TypeError("the policy is not an object")
            profile_name = policy.get("pipeline_profile") or "solo"
            profiles = policy.get("pipeline_profiles") or {}
            profile = profiles.get(profile_name) or {}
            if not isinstance(profile, dict):
                raise TypeError("pipeline_profiles.%s is not an object" % profile_name)
            legacy = (sensors.legacy_six_tier(policy) if sensors is not None
                      else isinstance(policy.get("tiers"), dict) and "T6" not in policy["tiers"])
            explicit = profile.get("direct_mode_cap")
            modes = profile.get("mode") if isinstance(profile.get("mode"), dict) else {}
            if explicit is not None:
                if explicit not in TIERS:
                    die("direct_mode_cap %r in risk-tiers.json (profile %s) is not a tier T0..T6"
                        % (explicit, profile_name))
                cap = explicit
            elif legacy:
                cap = "T3"
            elif modes:
                for t in TIERS:                 # the unbroken direct run from T0
                    if modes.get(t) != "direct":
                        break
                    cap = t
                cap = cap or "T0"
            elif profile_name == "solo":
                cap = DIRECT_MODE_CAP
        except (AttributeError, TypeError) as exc:
            die("risk-tiers.json is malformed (%s): fix it before quick" % exc)
    if cap is None or tier not in TIERS:
        return
    if TIERS.index(tier) > TIERS.index(cap):
        die("DIRECT_MODE_CAP %s (profile %s): use init, triage and a reviewed plan"
            % (cap, profile_name), 8)


def cmd_init(args, root):
    if args.workflow not in WORKFLOWS:
        die("workflow must be one of: %s" % ", ".join(WORKFLOWS))
    existing = load(root, required=False, claim=False)
    if existing and existing.get("current_stage") != "done" and not args.force:
        die("task %s is still at stage '%s'. Finish it, archive it, or pass --force."
            % (existing.get("task_id"), existing.get("current_stage")))
    pending = ((existing or {}).get("handoff") or {}).get("pending_to") if existing else None
    if pending in RUNTIMES and pending != RUNTIME and existing.get("current_stage") != "done":
        die("RUNTIME_HANDOFF_PENDING: task %s was handed to %s; --force here would discard it. "
            "Take it back first: state.py handoff --to %s" % (existing.get("task_id"), pending,
                                                                RUNTIME if RUNTIME in RUNTIMES else "<claude|codex>"), 7)
    task_id = valid_task_id(args.task_id) if args.task_id else next_task_id(root)
    state = {
        "task_id": task_id,
        "goal": args.goal,
        "workflow": args.workflow,
        "risk_tier": None,
        "current_stage": "discovery",
        "affected_modules": [],
        "context_summary_ref": None,
        "approved_plan": {"ref": None, "current_step_id": None, "steps": []},
        "completed_steps": [],
        "test_status": "not_run",
        "e2e_status": "not_run",
        "review_status": "not_started",
        "security_status": "not_started",
        "open_risks": [],
        "next_action": "run DISCOVERY",
        "human_approval": {"required": True, "granted": False, "granted_by": None, "granted_at": None},
        "created_at": now(),
        "updated_at": now(),
        "history": [],
    }
    apply_defaults(state)
    record_base_tree(root, state)         # the tree every later measurement is against
    claim_runtime(root, state)
    os.makedirs(os.path.join(root, ".ai", "reports", task_id), exist_ok=True)
    emit(root, state, "task_started", "%s (%s)" % (args.goal, args.workflow),
         {"goal": args.goal, "workflow": args.workflow})
    set_resume_point(state)
    # Otherwise the previous task's goal, step and file scope are what a session
    # start injects until the first stage-moving command runs.
    write_handoff(root, state, "stage")
    save(root, state)
    print(task_id)
    if not getattr(args, "quiet_advice", False):
        advise(state)


def cmd_get(args, root):
    state = load(root, required=not args.quiet)
    if state is None:
        print("no task in flight")
        return
    if args.field:
        value = state
        for part in args.field.split("."):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
        print(json.dumps(value) if isinstance(value, (dict, list)) else ("" if value is None else value))
    else:
        json.dump(state, sys.stdout, indent=2, ensure_ascii=False)
        print()


def emit_tier(root, state, previous, tier, note):
    """tier_raised where a tier went up, tier_set otherwise — both keep history's
    'risk_classified' name, and both record the previous value, which is the one
    thing a journal line cannot be backfilled with later."""
    detail = "%s%s" % (tier, ": " + note if note else "")
    if previous in TIERS and TIERS.index(tier) > TIERS.index(previous):
        emit(root, state, "tier_raised", detail,
             {"from": previous, "to": tier, "note": note}, legacy="risk_classified")
        return
    direction = "set"
    if previous in TIERS:
        direction = "unchanged" if previous == tier else "lowered"
    emit(root, state, "tier_set", detail,
         {"tier": tier, "from": previous, "note": note, "direction": direction},
         legacy="risk_classified")


def emit_inline_stages(root, state, previous):
    """The four stages a small task passes through in one call: recorded one by
    one so the audit trail still shows each of them. current_stage advances with
    them, because a journal line's `stage` names the stage the event put the task
    into (I3) — and these lines are never rewritten."""
    for stage in ("discovery", "context", "impact_analysis", "risk_classification"):
        state["current_stage"] = stage
        emit(root, state, "stage_started", "%s -> %s: inline" % (previous, stage),
             {"from": previous, "to": stage, "note": "inline"}, legacy="stage")
        previous = stage


def cmd_stage(args, root):
    if args.stage not in STAGES:
        die("stage must be one of: %s" % ", ".join(STAGES))
    state = load(root)
    previous = state["current_stage"]
    state["current_stage"] = args.stage
    emit(root, state, "stage_started",
         "%s -> %s%s" % (previous, args.stage, ": " + args.note if args.note else ""),
         {"from": previous, "to": args.stage, "note": args.note}, legacy="stage")
    if args.stage == "human_approval":
        request_gate(root, state, "human_approval")
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("%s -> %s" % (previous, args.stage))


def guard_lowering(root, state, tier, by):
    """downgrade_rule, as an exit code rather than a sentence: an agent may
    propose a lower tier with evidence, it may not apply one. Re-scoring is what
    makes this bite — a task raised to T4 by its own diff has an obvious motive
    to call itself T2 again."""
    previous = state.get("risk_tier")
    if previous not in TIERS or TIERS.index(tier) >= TIERS.index(previous):
        return
    if not (by and human_present()):
        refuse_approval_free(root, previous, tier)
    state["risk_tier_lowered"] = {"by": by, "at": now(), "from": previous}
    record(state, "risk_lowered", "%s -> %s by %s" % (previous, tier, by))


def refuse_approval_free(root, previous, tier):
    die("APPROVAL_REFUSED — only a human lowers a risk tier, in writing (downgrade_rule). "
        "The task is %s and you asked for %s. Propose it with evidence and let the human run, "
        "in their own terminal:\n  python3 %s --root %s risk %s --by \"<name>\" --note \"<why>\"%s"
        % (previous, tier, shlex.quote(os.path.abspath(__file__)), shlex.quote(root), tier,
           refused_because()), 5)


def cmd_risk(args, root):
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    previous = state.get("risk_tier")
    guard_lowering(root, state, args.tier, args.by)
    state["risk_tier"] = args.tier
    emit_tier(root, state, previous, args.tier, args.note)
    write_handoff(root, state, "stage")
    save(root, state)
    print(args.tier)
    advise(state)


def cmd_triage(args, root):
    """The four inline stages of a small task, recorded in one call so the audit
    trail still shows each of them without four round trips."""
    if args.tier not in TIERS:
        die("risk tier must be one of: %s" % ", ".join(TIERS))
    state = load(root)
    previous = state["current_stage"]
    emit_inline_stages(root, state, previous)
    state["current_stage"] = "risk_classification"
    previous_tier = state.get("risk_tier")
    guard_lowering(root, state, args.tier, args.by)
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    emit_tier(root, state, previous_tier, args.tier, args.note)
    write_handoff(root, state, "stage")
    save(root, state)
    print("%s, triaged inline through risk_classification" % args.tier)


def cmd_plan(args, root):
    state = load(root)
    try:
        with open(args.steps, encoding="utf-8") as fh:
            steps = json.load(fh)
    except (OSError, ValueError) as exc:
        die("cannot read steps file %s (%s)" % (args.steps, exc))
    if not isinstance(steps, list) or not steps:
        die("steps file must contain a non-empty JSON array")
    for step in steps:
        for field in ("step_id", "description", "allowed_files"):
            if field not in step:
                die("step %s is missing '%s'" % (step.get("step_id", "?"), field))
        step.setdefault("forbidden_files", [])
        step.setdefault("forbidden_reason", "not part of this step")
        step.setdefault("required_tests", [])
        step.setdefault("status", "pending")
        # `characterization` is not decoration: it inverts what the must-bite
        # check expects of the step's tests at the base tree.
        step.setdefault("kind", "implementation")
        step.setdefault("tree_before", None)
        step.setdefault("diff", None)
    state["approved_plan"] = {"ref": args.ref, "current_step_id": None, "steps": steps}
    set_resume_point(state)               # the old one may name a step this plan does not have
    emit(root, state, "plan_registered", "%d steps, %s" % (len(steps), args.ref),
         {"ref": args.ref, "steps": len(steps)}, legacy="plan_approved")
    write_handoff(root, state, "stage")
    save(root, state)
    print("%d steps recorded" % len(steps))


# --------------------------------------------------------------------- the gates
# Everything below measures through sensors.py and decides; sensors.py itself
# decides nothing. A sensor that cannot measure says so and the task carries on:
# a measurement is evidence, and missing evidence is never a reason to refuse
# work a human asked for. The one thing it does refuse is a step that grew past
# its tier's budget or reached outside its own files — and both of those are
# answered by splitting the step, not by abandoning it.

def sensors_available():
    return sensors is not None


def safe_sensor(call, *args, **kwargs):
    """A bug in a sensor must never be able to stop a task. Anything unexpected
    reads as 'unavailable', which keeps every review the tier asked for."""
    if sensors is None:
        return None
    try:
        return call(*args, **kwargs)
    except Exception:                     # pylint: disable=broad-except
        return None


def record_base_tree(root, state):
    """The tree the task started from. Taken once, at init, because a base taken
    later would quietly exclude everything already changed."""
    state["diff"]["base_commit"] = safe_sensor(sensors.head_commit, root)
    state["diff"]["base_tree"] = safe_sensor(sensors.snapshot_tree, root)


def load_policy(root):
    policy = safe_sensor(sensors.load_policy, root)
    if policy is None:                    # no sensors module: budgets cannot bite
        policy = {"diff_budget": {"per_step": {}, "per_task": {}, "exclude": [],
                                  "unbudgeted_scopes": []},
                  "path_scopes": [], "sensors": {}, "remediation_rounds": 2,
                  "review_rounds_max": 2, "tiers": {}}
    return policy


# What a tier asks of close when the policy has no `tiers` table to say it: the
# shipped table's answer — a review from T2, a human's approval from T4.
TIER_GATE_FROM = {"adversarial_review": "T2", "human_approval": "T4"}


def tier_requires(policy, tier, gate):
    """Whether `tier` has `gate` (adversarial_review, human_approval). A
    sentence — T2's "the sensors … one review only when one is red" — is a yes:
    close then runs the review gate, which is what the sentence describes."""
    entry = (policy.get("tiers") or {}).get(tier)
    if isinstance(entry, dict) and gate in entry:
        return bool(entry[gate])
    tier = tier if tier in TIERS else "T2"
    return TIERS.index(tier) >= TIERS.index(TIER_GATE_FROM[gate])


def measure_diff(root, from_tree, to_tree, tier, allowed, scope, deferred_to=None,
                 not_mine=None):
    policy = load_policy(root)
    measurement = safe_sensor(sensors.measure, root, from_tree, to_tree, policy,
                              tier=tier, allowed=allowed or None, scope=scope,
                              deferred_to=deferred_to or None, not_mine=not_mine or None)
    if measurement is None:
        measurement = {"status": "unavailable", "detail": "sensors.py unavailable",
                       "files": 0, "added": 0, "deleted": 0, "lines": 0,
                       "excluded_lines": 0, "unbudgeted_lines": 0, "unscoped": [],
                       "deferred": [],
                       "binary": [], "scopes": [], "over": [], "per_file": [],
                       "budget": {"max_lines": None, "max_files": None},
                       "measured_at": now(), "scope": scope, "tier": tier}
    return policy, measurement


def budget_line(prefix, measurement):
    budget = measurement.get("budget") or {}
    return ("%s: %d files, +%d/-%d = %d lines (%s budget %s/%s)"
            % (prefix, measurement["files"], measurement["added"], measurement["deleted"],
               measurement["lines"], measurement.get("tier"),
               budget.get("max_files"), budget.get("max_lines")))


def rescore_task(root, state, to_tree):
    """What the change turned out to be, against what it was called at the start.
    Since redesign 1.2 it never moves the tier: a path scope whose min_tier sits
    above the declared tier is stored in `diff.rescore_hints` and printed once,
    to stderr. A tier is raised by a human or `state.py risk`, not by a path."""
    declared = state.get("risk_tier") or "T0"
    _policy, measurement = measure_diff(root, state["diff"].get("base_tree"), to_tree,
                                        declared, None, "task")
    task = state["diff"]["task"]
    task.update({"files": measurement["files"], "added": measurement["added"],
                 "deleted": measurement["deleted"], "lines": measurement["lines"],
                 "excluded_lines": measurement["excluded_lines"],
                 "unbudgeted_lines": measurement["unbudgeted_lines"],
                 "tree": to_tree, "measured_at": now(),
                 "status": measurement["status"]})
    state["diff"]["over_budget"] = bool(measurement.get("over"))
    scored = safe_sensor(sensors.rescore, declared, measurement, _policy)
    if not scored or scored.get("status") == "unavailable":
        state["diff"]["rescored_tier"] = None
        state["diff"]["rescore_reasons"] = []
        return measurement, None
    state["diff"]["rescored_tier"] = scored["tier"]
    state["diff"]["rescore_reasons"] = scored["reasons"]
    # A hint names its scope before " (": the first file of a scope can change
    # between steps, the scope cannot, so a scope is printed once per task.
    hints = scored.get("hints") or []
    shown = {h.split(" (", 1)[0] for h in state["diff"].get("rescore_hints") or []}
    for hint in hints:
        if hint.split(" (", 1)[0] not in shown:
            print("hint: %s" % hint, file=sys.stderr)
    state["diff"]["rescore_hints"] = hints
    return measurement, scored


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


def human_present():
    """The condition every human-only command uses: a terminal outside any
    agent session, or a launcher that declared the run unattended."""
    return human_route()[0] is not None


def refused_because():
    """The line a human-only refusal ends with, so a human who did run it in a
    terminal — through the `!` prefix — learns which marker refused them."""
    why = human_route()[1]
    return "\nRefused because %s." % why if why else ""


def refuse_without_human(what, how):
    die("APPROVAL_REFUSED — %s happens outside the agent. Run it in your own terminal:\n  %s"
        % (what, how), 5)


def cmd_step(args, root):
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    match = [s for s in steps if s["step_id"] == args.step_id]
    if not match:
        die("no step '%s' in the approved plan (have: %s)"
            % (args.step_id, ", ".join(s["step_id"] for s in steps) or "none"))
    for s in steps:
        if s["step_id"] == args.step_id:
            s["status"] = "in_progress"
            # Taken once: a step resumed after a crash keeps the tree it began
            # with, and a step split off a bigger one inherits its sibling's.
            if not s.get("tree_before"):
                s["tree_before"] = safe_sensor(sensors.snapshot_tree, root)
    state["approved_plan"]["current_step_id"] = args.step_id
    emit(root, state, "step_started", "%s: %s" % (args.step_id, match[0]["description"]),
         {"step_id": args.step_id, "kind": "step"})
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("step %s: %s" % (args.step_id, match[0]["description"]))
    print("allowed: %s" % ", ".join(match[0]["allowed_files"]))
    if match[0]["forbidden_files"]:
        print("forbidden: %s" % ", ".join(match[0]["forbidden_files"]))
    # Only this step's own tests run inside it; the full suite runs once after
    # the last step and the e2e suite once after that.
    print("step tests: %s" % (", ".join(match[0].get("required_tests") or []) or "none"))


def cmd_step_done(args, root):
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    match = [s for s in steps if s["step_id"] == args.step_id]
    if not match:
        die("no step '%s' in the approved plan" % args.step_id)
    finish_step(root, state, match[0], args.force)


def finish_step(root, state, step, force=False):
    """What step-done does to one step: measure it, refuse it (exit 6), or mark
    it done, re-score the task and save. remediate and close call it for every
    step still open, so the direct path needs no step-done of its own."""
    steps = state.get("approved_plan", {}).get("steps", [])
    step_id = step["step_id"]

    # The gate. Measured before anything is marked done, so a refusal leaves the
    # step exactly where it was: in progress, with a way out that keeps the work.
    tier = state.get("risk_tier") or "T2"
    after = safe_sensor(sensors.snapshot_tree, root)
    before = step.get("tree_before") or _last_tree_after(state, step)
    from_base = not before
    before = before or state["diff"].get("base_tree")
    elsewhere = [f for other in steps if other is not step
                 for f in (other.get("allowed_files") or [])]
    _policy, measured = measure_diff(root, before, after, tier,
                                     step.get("allowed_files"), "step",
                                     deferred_to=elsewhere,
                                     not_mine=step.get("forbidden_files"))
    if measured["status"] == "red" and measured["unscoped"] and not force:
        die("SCOPE_CHANGE_REQUIRED step %s changed %s outside its files — amend the plan, or "
            "move them with:\n  state.py step-split %s --files %s"
            % (step_id, ", ".join(measured["unscoped"][:5]), step_id,
               shlex.quote(",".join(measured["unscoped"][:5]))), 6)
    if measured["over"] and not force:
        # The size of a change is a warning, never its tier and never a refusal,
        # `enforce: true` included (redesign 1.2); only the scope refuses, above.
        print("budget: over — step %s: %s (advisory). Split it when that helps the review:\n"
              "  state.py step-split %s --files \"<the part that is its own step>\""
              % (step_id, "; ".join(measured["over"]), step_id), file=sys.stderr)
    seq = 1 + max([_seq(s.get("diff")) for s in steps] or [0])
    step["diff"] = {"tree_after": after, "seq": seq,
                    "paths": [path for path, _l, _n, _t in measured.get("per_file", [])],
                    "files": measured["files"],
                    "added": measured["added"], "deleted": measured["deleted"],
                    "lines": measured["lines"], "unscoped": measured["unscoped"],
                    "binary": measured["binary"], "status": measured["status"]}

    for s in steps:
        if s["step_id"] == step_id:
            s["status"] = "done"
    if step_id not in state["completed_steps"]:
        state["completed_steps"].append(step_id)
    if state["approved_plan"].get("current_step_id") == step_id:
        state["approved_plan"]["current_step_id"] = None
    emit(root, state, "step_done", step_id, {"step_id": step_id},
         legacy="step_completed")
    task_measured, scored = rescore_task(root, state, after)
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    if measured["status"] == "unavailable":
        print("step %s diff: unavailable (%s)"
              % (step_id, measured.get("detail") or "not measured"))
    else:
        print(budget_line("step %s diff" % step_id, measured)
              + (" — budget: over — %s (advisory)" % "; ".join(measured["over"])
                 if measured["over"] else " — ok"))
    if from_base and measured["status"] != "unavailable" and completed_before(state, step):
        print("step %s measured from the task's base tree: it has no tree_before and no "
              "finished step recorded where the tree stood" % step_id)
    if task_measured["status"] != "unavailable":
        print(budget_line("task diff", task_measured)
              + ("; rescored %s" % scored["tier"] if scored else ""))
    remaining = [s["step_id"] for s in steps if s["status"] != "done"]
    print("step %s done; remaining: %s" % (step_id, ", ".join(remaining) or "none"))
    if not remaining:
        print("last step: run verify_command once, to the end, then e2e_command once")


def _last_tree_after(state, step):
    """Where the last finished step left the tree. A step with no tree_before of
    its own (a remediation recorded before remediate took one) began there, not
    at the task's base tree — measuring from the base would charge it with the
    whole task's diff. "Last" is by when step-done ran (diff.seq): a step done
    again keeps its first place in completed_steps. Steps recorded before seq
    existed fall back to that list's order, and rank below any that have one."""
    steps = state.get("approved_plan", {}).get("steps", [])
    by_id = {s["step_id"]: s for s in steps}
    best, best_key = None, None
    for i, step_id in enumerate(state.get("completed_steps") or []):
        done = by_id.get(step_id)
        if done is None or done is step:
            continue
        diff = done.get("diff") or {}
        if not diff.get("tree_after"):
            continue
        key = (_seq(diff), i)
        if best_key is None or key > best_key:
            best, best_key = diff["tree_after"], key
    return best


def _seq(diff):
    """A step's finishing order; 0 for one recorded before it existed, or hand-edited."""
    seq = (diff or {}).get("seq")
    return seq if isinstance(seq, int) and not isinstance(seq, bool) else 0


def completed_before(state, step):
    """Whether any other step had finished — the case where measuring from the
    base tree is a fallback worth naming rather than the obvious start."""
    return any(sid != step["step_id"] for sid in state.get("completed_steps") or [])


def _split_files(text):
    return [f.strip() for f in (text or "").split(",") if f.strip()]


def cmd_step_split(args, root):
    """The way out of a refused step-done: the part that has grown into its own
    step becomes one. Nothing is undone and nothing is lost — the files move,
    the sibling inherits the tree the original started from, and both halves are
    then measured against their own budget."""
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    match = [s for s in steps if s["step_id"] == args.step_id]
    if not match:
        die("no step '%s' in the approved plan" % args.step_id)
    step = match[0]
    files = _split_files(args.files)
    if not files:
        die("--files must name at least one file or glob to move into the new step")
    existing = {s["step_id"] for s in steps}
    n = 2
    while "%s.%d" % (args.step_id, n) in existing:
        n += 1
    new_id = "%s.%d" % (args.step_id, n)
    sibling = {
        "step_id": new_id,
        "description": args.note or ("split off %s" % args.step_id),
        "allowed_files": files,
        "forbidden_files": list(step.get("forbidden_files") or []),
        "forbidden_reason": step.get("forbidden_reason") or "not part of this step",
        "required_tests": [], "status": "pending",
        "kind": step.get("kind", "implementation"),
        "tree_before": step.get("tree_before"), "diff": None,
    }
    step["allowed_files"] = [f for f in (step.get("allowed_files") or []) if f not in files]
    # A step's own glob usually still matches what it gave away (`src/**` covers
    # `src/Payment/*.php`), so the split says so explicitly. This is also what
    # the scope guard reads, so the original step can no longer write them.
    forbidden = step.setdefault("forbidden_files", [])
    for pattern in files:
        if pattern not in forbidden:
            forbidden.append(pattern)
    step["forbidden_reason"] = "moved to step %s" % new_id
    steps.insert(steps.index(step) + 1, sibling)
    emit(root, state, "scope_change", "%s -> %s: %s" % (args.step_id, new_id, ", ".join(files)),
         {"kind": "split", "from": args.step_id, "step_id": new_id, "files": files})
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("step %s split: %s now covers %s" % (args.step_id, new_id, ", ".join(files)))
    print("finish %s, then run: state.py step %s" % (args.step_id, new_id))


def cmd_quick(args, root):
    """The direct path for T0–T4 (T4 after the human approved the plan in plan
    mode): one call records the task, the four inline
    triage stages and a single step whose allowed files are the ones named, so
    the scope guard is armed without a plan file, a task.md or four round trips."""
    if args.tier not in ("T0", "T1", "T2", "T3", "T4"):
        die("quick is for T0 to T4; from T5 the task needs init, triage and a reviewed plan")
    direct_mode_cap(root, args.tier)
    files = _split_files(args.files)
    if not files:
        die("--files must name at least one file or glob the step may touch")
    args.quiet_advice = True              # said once, below, after the step line
    cmd_init(args, root)
    state = load(root)
    previous = state["current_stage"]
    emit_inline_stages(root, state, previous)
    state["current_stage"] = "risk_classification"
    previous_tier = state.get("risk_tier")
    state["risk_tier"] = args.tier
    if args.context:
        state["context_summary_ref"] = "inline: " + args.context
    emit_tier(root, state, previous_tier, args.tier, args.note)
    step = {
        "step_id": "1", "description": args.goal, "allowed_files": files,
        "forbidden_files": [], "forbidden_reason": "not part of this task",
        "required_tests": _split_files(args.tests), "status": "in_progress",
    }
    state["approved_plan"] = {"ref": "inline", "current_step_id": "1", "steps": [step]}
    emit(root, state, "plan_registered", "1 step, inline (quick)",
         {"ref": "inline", "steps": 1}, legacy="plan_approved")
    state["current_stage"] = "implementation"
    emit(root, state, "stage_started", "risk_classification -> plan -> implementation: quick",
         {"from": "risk_classification", "to": "implementation", "note": "quick"}, legacy="stage")
    emit(root, state, "step_started", "1: %s" % args.goal, {"step_id": "1", "kind": "step"})
    state["next_action"] = "implement (step tests only), then the verification command once, then e2e once"
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("%s %s: step 1 armed for %s" % (state["task_id"], args.tier, ", ".join(files)))
    advise(state)


LABEL_RE = re.compile(r"^[A-Z][0-9]+$")


def review_report_path(root, state):
    return os.path.join(root, ".ai", "reports", state["task_id"], "review-report.md")


def check_closes(root, state, labels):
    """--closes names findings a review wrote down, or nothing. A label is
    found when a finding row carries it after its severity: `- [HIGH] H1 …`."""
    bad = [label for label in labels if not LABEL_RE.match(label)]
    if bad:
        die("--closes takes finding labels like H1 or M2, not: %s" % ", ".join(bad))
    path = review_report_path(root, state)
    try:
        with open(path, encoding="utf-8") as fh:
            report = fh.read()
    except OSError:
        die("--closes needs the review's findings in %s, and there is none. Save the reviewer's "
            "FINDINGS and VERDICT there first." % os.path.relpath(path, root))
    missing = [label for label in labels
               if not re.search(r"\]\s+%s(\s|$)" % re.escape(label), report, re.M)]
    if missing:
        die("--closes names %s, which %s not a finding in %s"
            % (", ".join(missing), "is" if len(missing) == 1 else "are",
               os.path.relpath(path, root)))


def cmd_remediate(args, root):
    """One extra step for the whole batch of fixes after the test run or the
    review — never one step per failure. Its scope is the union of every step
    already done plus the files named (usually the failing tests). A step still
    open is finished first, as step-done would, so a red run on the direct path
    goes straight to its fix."""
    state = load(root)
    steps = state.get("approved_plan", {}).get("steps", [])
    if not steps:
        die("no approved plan to remediate; register one with plan or quick first")
    closes = _split_files(args.closes)
    if closes:
        check_closes(root, state, closes)
    n = 1 + sum(1 for s in steps if str(s["step_id"]).startswith("R"))
    rounds = load_policy(root).get("remediation_rounds", 2)
    if isinstance(rounds, int) and n > rounds and not (args.by and human_present()):
        # remediation_rule: at most two rounds before the human decides. A third
        # round is where a fix starts causing the next regression (review-economy §5).
        die("APPROVAL_REFUSED — this is remediation round %d and the policy allows %d. "
            "Name the invariant behind the repeated failure, show it to the human, and let "
            "them run:\n  python3 %s --root %s remediate --files %s --by \"<name>\"%s"
            % (n, rounds, shlex.quote(os.path.abspath(__file__)), shlex.quote(root),
               shlex.quote(args.files or ""), refused_because()), 5)
    for open_step in [s for s in steps if s["status"] == "in_progress"]:
        finish_step(root, state, open_step)
    allowed = []
    for s in steps:
        for f in s.get("allowed_files", []):
            if f not in allowed:
                allowed.append(f)
    for f in _split_files(args.files) + _split_files(args.tests):
        if f not in allowed:
            allowed.append(f)
    step_id = "R%d" % n
    step = {
        "step_id": step_id,
        "description": args.note or "remediation batch %d" % n,
        "allowed_files": allowed, "forbidden_files": [],
        "forbidden_reason": "not part of this task", "required_tests": _split_files(args.tests),
        "status": "in_progress",
        # Taken now, like cmd_step does: the batch is measured from here, not
        # from the task's base tree, or it carries every finished step's diff.
        "tree_before": safe_sensor(sensors.snapshot_tree, root),
    }
    if closes:
        # The findings this batch fixes, and how many runs came before it: the
        # first green suite after it, on a tree it changed, closes them (§3a).
        step["closes"] = closes
        step["runs_before"] = len(state["tests"]["runs"])
        step["opened_at_event"] = len(state.get("history") or [])
    steps.append(step)
    state["approved_plan"]["current_step_id"] = step_id
    state["current_stage"] = "implementation"
    # Two lines for one step, matching the two history entries and the mapping
    # migration 0002 backfills with: a reader counts data.kind, not the type.
    emit(root, state, "step_started", "%s: %s" % (step_id, step["description"]),
         {"step_id": step_id, "kind": "remediation"}, legacy="remediation")
    emit(root, state, "step_started", "%s: %s" % (step_id, step["description"]),
         {"step_id": step_id, "kind": "step"})
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("step %s armed for %s" % (step_id, ", ".join(allowed)))
    if closes:
        print("closes %s: a green test-run after this batch records them closed"
              % ", ".join(closes))


def cmd_test_run(args, root):
    """One run of one scope, recorded. Why this and not the agent running it:
    a run's own exit code is the verdict when it is green, so a green run costs
    no model at all; and the cap, the one environment retry and the log file
    live where the record does, not in a prompt an agent may read loosely.

    `--scope all` is the direct path's one verification call: the suite, then
    e2e only when the suite is green, each recorded exactly as its own scope."""
    state = load(root)
    policy = load_policy(root)
    config = (policy.get("sensors") or {}).get("tests") or {}
    max_runs = config.get("max_suite_runs", 5)
    tests = state["tests"]
    if args.scope == "all" and args.files:
        die("--files narrows one scope; --scope all runs the whole suite and e2e")
    if args.e2e and args.scope != "all":
        die("--e2e is for --scope all; for a single scope run 'state.py set e2e_status "
            "not_applicable'")
    if args.e2e and (args.e2e[0] != "not-applicable" or not args.e2e[1].strip()):
        die('--e2e takes: not-applicable "<why the change cannot reach an e2e flow>"')
    if args.scope in ("suite", "all") and isinstance(max_runs, int) \
            and tests["suite_runs"] >= max_runs:
        die("run budget exhausted: %d suite runs, the policy allows %d. Running it again is not "
            "the next move — the human decides what is." % (tests["suite_runs"], max_runs), 6)
    if args.env_retry and state.get("test_status") != "env_failure":
        die("--env-retry is for a run already classified as a TEST ENVIRONMENT FAILURE; "
            "this task's test_status is '%s'. Classify the failure first." % state.get("test_status"))

    if args.scope != "all":
        exit_code = run_scope(root, state, args.scope, args, config)
        if exit_code == 0 and args.scope == "suite":
            close_findings(root, state)
        sys.exit(0 if exit_code == 0 else 1)

    if run_scope(root, state, "suite", args, config) != 0:
        print("e2e: not run — the suite is red")
        sys.exit(1)
    if args.e2e:
        e2e_not_applicable(root, state, args.e2e[1])
    else:
        command = (safe_sensor(sensors.command_for, root, "e2e") or "").strip()
        if command == "none":
            e2e_not_applicable(root, state, "e2e_command: none in .ai/policies/testing.md")
        elif run_scope(root, state, "e2e", args, config) != 0:
            sys.exit(1)
    close_findings(root, state)


def run_scope(root, state, scope, args, config):
    """Run one scope's command to the end, record it and print its six lines.
    Returns the exit code; the caller decides what a red one means."""
    tests = state["tests"]
    max_runs = config.get("max_suite_runs", 5)
    command = safe_sensor(sensors.command_for, root, scope) or ""
    if not command:
        die("no command for scope '%s' in .ai/policies/testing.md — write it down first"
            % scope)
    files = _split_files(args.files)
    if files:
        command = safe_sensor(sensors.expand_files, command, files) or command
    n = len([r for r in tests["runs"] if r.get("scope") == scope]) + 1
    log = os.path.join(root, ".ai", "reports", state["task_id"],
                       "tests-%s-%d.log" % (scope, n))
    result = safe_sensor(sensors.run_command, root, command, log,
                         config.get("timeout_seconds", 1800),
                         config.get("log_max_bytes", 2097152))
    if result is None:
        die("sensors.py is not installed beside state.py — run the project's command yourself")

    tests["runs"].append({"n": n, "scope": scope, "command": command,
                          "tree": safe_sensor(sensors.snapshot_tree, root),
                          "exit": result["exit"], "duration_s": result["duration_s"],
                          "log": os.path.relpath(log, root), "at": now(),
                          "env_retry": bool(args.env_retry)})
    if scope == "suite":
        tests["suite_runs"] += 1
    field = "e2e_status" if scope == "e2e" else "test_status"
    previous = state.get(field)
    if result["exit"] == 0:
        # Green needs no interpretation, and this is where the model step goes
        # away: nothing is delegated, nothing is pasted, the exit code is it.
        state[field] = "passing"
    elif result["exit"] is None:
        state[field] = "env_failure" if field == "test_status" else "not_run"
    elif previous in (None, "not_run", "passing"):
        state[field] = "unknown" if field == "test_status" else "failing"
    emit(root, state, "field_set", "%s = %s (%s run %d, exit %s)"
         % (field, state[field], scope, n, result["exit"]),
         {"field": field, "from": previous, "value": state[field],
          "scope": scope, "exit": result["exit"], "log": os.path.relpath(log, root)})
    write_handoff(root, state, "stage")
    save(root, state)

    print("%s run %d: exit %s in %ds" % (scope, n, result["exit"], result["duration_s"]))
    print("command: %s" % command)
    print("log: %s" % os.path.relpath(log, root))
    if result["detail"]:
        print(result["detail"])
    if result["exit"] == 0:
        print("%s = passing" % field)
        return 0
    print("classify: hand ai-tester the log path above — it reads the file, it never re-runs")
    if scope == "suite" and isinstance(max_runs, int):
        print("suite runs used: %d of %d" % (tests["suite_runs"], max_runs))
    return 1 if result["exit"] is None else result["exit"]


def e2e_not_applicable(root, state, why):
    """The one-call spelling of `set e2e_status not_applicable`, with its reason."""
    previous = state.get("e2e_status")
    state["e2e_status"] = "not_applicable"
    emit(root, state, "field_set", "e2e_status = not_applicable (%s)" % one_line(why, 200),
         {"field": "e2e_status", "from": previous, "value": "not_applicable", "why": why},
         legacy="set")
    write_handoff(root, state, "stage")
    save(root, state)
    print("e2e_status = not_applicable: %s" % one_line(why, 200))


def close_findings(root, state):
    """§3a: a review that found something but no blocker is closed by the
    remediation that names its findings and the green run after it — not by a
    second review. Only on a tree that remediation changed: a batch that fixed
    nothing closes nothing."""
    if state.get("review_status") != "passed_with_findings":
        return
    batches = [s for s in state.get("approved_plan", {}).get("steps", []) if s.get("closes")]
    if not batches:
        return
    batch = batches[-1]
    if (batch.get("opened_at_event") or 0) <= (state.get("findings_verdict_at") or 0):
        # The batch answers an earlier verdict. A later passed_with_findings
        # brought findings no --closes has named, so no run closes them.
        return
    runs = state["tests"]["runs"]
    suite = [i for i, r in enumerate(runs) if r.get("scope") == "suite"]
    if not suite or suite[-1] < (batch.get("runs_before") or 0) or runs[suite[-1]].get("exit") != 0:
        return
    run = runs[suite[-1]]
    if not run.get("tree") or run["tree"] == batch.get("tree_before"):
        print("findings %s stay open: the tree is where %s began, so nothing was fixed yet"
              % (", ".join(batch["closes"]), batch["step_id"]))
        return
    state["review_status"] = "passed"
    emit(root, state, "findings_closed", "%s closed by suite run %d on %s"
         % (", ".join(batch["closes"]), run["n"], run["tree"][:9]),
         {"labels": batch["closes"], "step_id": batch["step_id"], "run": run["n"],
          "tree": run["tree"]})
    emit(root, state, "field_set", "review_status = passed (findings closed by a green run)",
         {"field": "review_status", "from": "passed_with_findings", "value": "passed"})
    write_handoff(root, state, "stage")
    save(root, state)
    print("review_status = passed: %s closed by suite run %d" % (", ".join(batch["closes"]), run["n"]))


def cmd_review_gate(args, root):
    """The one place the sensor set can replace a model review.

    It replaces it only at or below `skip_review_at_or_below`, only when every
    required sensor measured something and that something was green, and only on
    the tree as it is right now. Anything else — a red sensor, a tool nobody
    wrote down, a result from an older tree, a declared tier above the
    ceiling — and the review runs exactly as it did before, with the sensor rows
    attached so the reviewer does not re-derive what is already settled.
    """
    state = load(root)
    if not review_gate(root, state, args.no_bite):
        sys.exit(2)


def review_gate(root, state, no_bite=False):
    """Run the sensors, record what they found, and answer whether they stand
    in for the review: True after writing skipped_green, False when it is owed."""
    if sensors is None:
        die("sensors.py is not installed beside state.py — run the review the tier asks for")
    policy = load_policy(root)
    report = safe_sensor(sensors.check, root, state, policy, no_bite, None)
    if report is None:
        die("the sensors could not run — run the review the tier asks for")
    safe_sensor(sensors.write_report, root, state, report, None)
    state["sensors"] = {"file": os.path.relpath(sensors.sensors_file(root, state), root),
                        "tree": report["tree"], "verdict": report["verdict"]["review"],
                        "checked_at": report["checked_at"]}
    sensors.print_report(report)

    if not report["verdict"]["all_green"]:
        state["next_action"] = "run the adversarial review the tier requires"
        emit(root, state, "field_set", "sensors: review required",
             {"field": "sensors", "value": report["verdict"]["review"],
              "blocking": report["verdict"]["blocking"]})
        write_handoff(root, state, "stage")
        save(root, state)
        print("the ledger has what the sensors settled: %s"
              % os.path.relpath(sensors.ledger_file(root, state), root))
        return False

    previous = state.get("review_status")
    state["review_status"] = "skipped_green"
    state["next_action"] = "finish the task: the sensors stand in for the review at this tier"
    emit(root, state, "field_set", "review_status = skipped_green (every sensor green on %s)"
         % (report["tree"] or "?")[:9],
         {"field": "review_status", "from": previous, "value": "skipped_green",
          "tree": report["tree"], "tier": state.get("risk_tier")})
    write_handoff(root, state, "stage")
    save(root, state)
    return True


def at_base_tree(root, state):
    """Nothing changed since the task began — measured, never assumed."""
    base = (state.get("diff") or {}).get("base_tree")
    return bool(base) and safe_sensor(sensors.snapshot_tree, root) == base


def approved_since_last_step(state):
    """A grant counts for close only when it came after the last finished step:
    an approval of the plan is not an approval of the work done after it."""
    approval = state.get("human_approval") or {}
    if not approval.get("granted") or not approval.get("granted_at"):
        return False
    done = [h.get("at") or "" for h in state.get("history") or []
            if h.get("event") in ("step_completed", "step_done")]
    return not done or approval["granted_at"] >= max(done)


def close_summary(root, state):
    measured = (state.get("diff") or {}).get("task") or {}
    print("%s %s ready for approval: %s" % (state["task_id"], state.get("risk_tier"),
                                            state.get("goal")))
    print("steps done: %s; task diff: %s files, %s lines"
          % (", ".join(state.get("completed_steps") or []) or "none",
             measured.get("files", "?"), measured.get("lines", "?")))
    print("tests: %s; e2e: %s; review: %s (%d of %s verdicts)"
          % (state.get("test_status"), state.get("e2e_status"), state.get("review_status"),
             state.get("reviews") or 0, load_policy(root).get("review_rounds_max", 2)))
    closed = [label for s in state.get("approved_plan", {}).get("steps", [])
              for label in s.get("closes") or []]
    if closed:
        print("findings closed by remediation: %s" % ", ".join(closed))
    print("approve in your own terminal, then run close again:\n  python3 %s --root %s approve "
          "--by \"<name>\"" % (shlex.quote(os.path.abspath(__file__)), shlex.quote(root)))


def cmd_close(args, root):
    """The direct path's exit (§5b), stopping at the first thing still owed.
    Exits 4 and 5 (a pending question, a rejection) were decided in main()."""
    state = load(root)
    if not state.get("completed_steps") and at_base_tree(root, state):
        # The escalation exit: a record nothing was done under — a quick task
        # that turned out to be T5 — closes as it always did.
        cmd_done(args, root)
        cmd_archive(args, root)
        return
    for step in [s for s in state.get("approved_plan", {}).get("steps", [])
                 if s["status"] == "in_progress"]:
        finish_step(root, state, step)
    tier = state.get("risk_tier") or "T2"
    policy = load_policy(root)
    if tier_requires(policy, tier, "adversarial_review") and state.get("review_status") != "passed":
        ceiling = (policy.get("sensors") or {}).get("skip_review_at_or_below", "T3")
        status = state.get("review_status")
        # A review's own findings are never overwritten by the sensors; below
        # them the gate runs afresh, and a skipped_green from an older tree is
        # not reused.
        may_skip = tier in TIERS and ceiling in TIERS \
            and TIERS.index(tier) <= TIERS.index(ceiling) \
            and status not in ("blockers_open", "passed_with_findings")
        if not (may_skip and review_gate(root, state)):
            status = state.get("review_status")
            if status == "passed_with_findings":
                how = ("fix the findings in one 'state.py remediate --closes \"<labels>\"' batch, "
                       "run 'state.py test-run --scope all' once more, then close again")
            elif status == "blockers_open":
                how = ("fix the blockers in one 'state.py remediate' batch, run the suite, get one "
                       "scoped re-review, 'state.py set review_status <verdict>', then close again")
            else:
                how = "run the tier's reviewer, 'state.py set review_status <verdict>', then close again"
            die("review required (%s, review_status %s) — %s. To drop this record instead: "
                "'state.py done --abandon' then 'state.py archive'." % (tier, status, how), 2)
    if tier_requires(policy, tier, "human_approval") and not approved_since_last_step(state):
        previous = state["current_stage"]
        state["current_stage"] = "human_approval"
        emit(root, state, "stage_started", "%s -> human_approval: close" % previous,
             {"from": previous, "to": "human_approval", "note": "close"}, legacy="stage")
        request_gate(root, state, "human_approval")
        state["next_action"] = "the human approves in their own terminal, then close again"
        set_resume_point(state)
        write_handoff(root, state, "stage")
        save(root, state)
        close_summary(root, state)
        return
    cmd_done(args, root)
    cmd_archive(args, root)


def cmd_set(args, root):
    if args.field not in SETTABLE:
        die("settable fields: %s" % ", ".join(sorted(SETTABLE)))
    allowed = SETTABLE[args.field]
    if args.field == "review_status" and args.value == "skipped_green":
        die("review_status 'skipped_green' is written only by review-gate, from the sensors. "
            "Run: state.py review-gate")
    if allowed and args.value not in allowed:
        die("%s must be one of: %s" % (args.field, ", ".join(allowed)))
    if args.by and args.field != "review_status":
        die("--by is for review_status: the verdict a human gives when the review budget is spent")
    state = load(root)
    if args.by:
        cmd_set_by_human(args, root, state)
        return
    if args.field == "review_status" and args.value in REVIEW_VERDICTS:
        count_review(root, state, args.value)
    previous = state.get(args.field)
    state[args.field] = args.value
    review = state.get("cross_vendor_review")
    if args.field == "review_status" and isinstance(review, dict) and review.get("status") == "requested" \
            and RUNTIME == review.get("to"):
        # A second review adds to the first; it never clears it. The other
        # vendor's verdict lives in cross_vendor_review.result, and review_status
        # — the field the gates read — keeps the owner's blockers until the
        # owner's own review clears them.
        if previous == "blockers_open":
            state[args.field] = previous
            print("note: review_status stays blockers_open (the task's own review); "
                  "this verdict is recorded as the cross-vendor result")
        if args.value not in ("not_started", "in_progress"):
            review.update({"status": "done", "by_runtime": RUNTIME, "done_at": now(), "result": args.value})
    if args.field == "review_status":
        mark_findings_verdict(state)
    emit(root, state, "field_set", "%s = %s" % (args.field, args.value),
         {"field": args.field, "from": previous, "value": args.value}, legacy="set")
    write_handoff(root, state, "stage")
    save(root, state)
    print("%s = %s" % (args.field, args.value))


def mark_findings_verdict(state):
    """Where in the history a passed_with_findings verdict was written: only a
    --closes batch opened after it may close it (close_findings)."""
    if state.get("review_status") == "passed_with_findings":
        state["findings_verdict_at"] = len(state.get("history") or [])


def count_review(root, state, value):
    """§3b: every verdict a review writes is one pass — the cross-vendor one
    included — and the one past review_rounds_max is the human's to give."""
    limit = load_policy(root).get("review_rounds_max", 2)
    reviews = state.get("reviews") or 0
    if isinstance(limit, int) and not isinstance(limit, bool) and reviews >= limit:
        emit(root, state, "review_budget_refused",
             "review_status %s refused: %d of %d verdicts used" % (value, reviews, limit),
             {"reviews": reviews, "max": limit, "value": value})
        save(root, state)
        die("REVIEW_BUDGET — this task has had %d review verdicts and the policy allows %d "
            "(review_rounds_max). Another pass is not the next move: show the human the "
            "findings and let them decide, in their own terminal:\n"
            "  python3 %s --root %s set review_status %s --by \"<name>\"\n"
            "or, at the approval gate, approve --by \"<name>\"."
            % (reviews, limit, shlex.quote(os.path.abspath(__file__)), shlex.quote(root),
               value), 6)
    state["reviews"] = reviews + 1


def cmd_set_by_human(args, root, state):
    """The human's verdict past the budget: not a review, so not counted and not
    refused by it — and, like approve, only from outside the agent."""
    via, why = human_route()
    if via is None:
        die("APPROVAL_REFUSED — a verdict with --by is the human's, given outside the agent. "
            "Run it in your own terminal:\n  python3 %s --root %s set review_status %s --by %s"
            "\nRefused because %s."
            % (shlex.quote(os.path.abspath(__file__)), shlex.quote(root), args.value,
               shlex.quote(args.by), why), 5)
    previous = state.get("review_status")
    state["review_status"] = args.value
    mark_findings_verdict(state)
    emit(root, state, "human_set", "review_status = %s by %s via %s" % (args.value, args.by, via),
         {"field": "review_status", "from": previous, "value": args.value, "by": args.by,
          "via": via, "unattended": via == "unattended"},
         actor="human" if via == "terminal" else "agent")
    write_handoff(root, state, "stage")
    save(root, state)
    print("review_status = %s (by %s via %s)" % (args.value, args.by, via))


def cmd_risks(args, root):
    state = load(root)
    previous = list(state.get("open_risks", []))
    if args.clear:
        state["open_risks"] = []
        emit(root, state, "field_set", "",
             {"field": "open_risks", "from": previous, "value": []}, legacy="risks_cleared")
    elif args.add:
        state["open_risks"].append(args.add)
        emit(root, state, "field_set", args.add,
             {"field": "open_risks", "from": previous, "value": state["open_risks"]},
             legacy="risk_added")
    else:
        die("pass --add TEXT or --clear")
    save(root, state)
    print("%d open risk(s)" % len(state["open_risks"]))


def cmd_modules(args, root):
    state = load(root)
    previous = list(state.get("affected_modules", []))
    for module in args.module:
        if module not in state["affected_modules"]:
            state["affected_modules"].append(module)
    emit(root, state, "field_set", ", ".join(args.module),
         {"field": "affected_modules", "from": previous, "value": state["affected_modules"]},
         legacy="modules")
    save(root, state)
    print(", ".join(state["affected_modules"]))


def cmd_note(args, root):
    """A decision, a rejected option or a failed attempt. It goes to the journal
    only: these are the facts a compaction loses, not state the guards enforce,
    so current.json does not grow with them."""
    if args.kind not in NOTE_KINDS:
        die("note kind must be one of: %s" % ", ".join(NOTE_KINDS))
    state = load(root)
    data = {"kind": args.kind, "text": args.text}
    if args.why:
        data["why"] = args.why
    if args.error:
        data["error"] = args.error
    append_journal(root, state["task_id"], journal_line(
        state["task_id"], "note", "agent", state.get("current_stage"),
        "%s: %s" % (args.kind, args.text), data))
    print("noted (%s)" % args.kind)


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


def latest_task_id(root):
    """The journal outlives current.json, which archive removes — so the reader
    falls back to the newest journal rather than reporting no task in flight."""
    reports = os.path.join(root, ".ai", "reports")
    candidates = []
    for name in os.listdir(reports) if os.path.isdir(reports) else []:
        path = os.path.join(reports, name, "events.jsonl")
        if os.path.exists(path):
            candidates.append((os.path.getmtime(path), name))
    return sorted(candidates)[-1][1] if candidates else None


def cmd_events(args, root):
    task_id = args.task
    if not task_id:
        state = load(root, required=False)
        task_id = state["task_id"] if state else latest_task_id(root)
    if not task_id:
        die("no task in flight and no journal under .ai/reports/")
    if args.type:
        for wanted in _split_files(args.type):
            # "legacy" is not emitted by anything: it is what migration 0002
            # calls a history entry whose event name this vocabulary never had.
            if wanted not in EVENT_TYPES and wanted != "legacy":
                die("unknown event type '%s' (have: %s)" % (wanted, ", ".join(EVENT_TYPES)))
    events, skipped = read_journal(root, task_id)
    if args.type:
        wanted = _split_files(args.type)
        events = [e for e in events if e.get("event") in wanted]
    if args.last > 0:
        events = events[-args.last:]
    for event in events:
        if args.format == "jsonl":
            print(json.dumps(event, ensure_ascii=False))
        else:
            print("%s  %-16s %s" % (event.get("ts", ""), event.get("event", ""), event.get("detail", "")))
    if skipped:
        print("state.py: events: skipped %d unparseable line(s) in %s"
              % (skipped, journal_path(root, task_id)), file=sys.stderr)


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
    `.ai/reports/<id>/` patterns, which is how a writable questions.md, and
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
    return os.path.join(root, ".ai", "reports", state["task_id"], "questions.md")


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
    """One regex per line (I2). Returns the file's lines beside the questions, so
    a writer can replace an [Answer]: line and leave every other byte alone."""
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().split("\n")
    except OSError:
        return [], []
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
    """questions.md is read, modified and written back. Without a lock across
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
        die("a gate is requested by 'state.py stage human_approval', not by ask")
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
        if not any(line.startswith("# Questions") for line in lines):
            # An existing but empty (or header-less) file still gets the notice
            # that tells a human not to edit the questions.
            lines = (QUESTIONS_HEADER % (args.topic or state["task_id"])).rstrip("\n").split("\n") + lines
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
    state, the journal, questions.md and session.json — never a transcript."""
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
    """A pure function of the state, the journal, questions.md and session.json,
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
        die("task %s is closed; start a new one with init" % state.get("task_id"), 2)
    if not installed(args.to):
        die("%s is not installed here (%s has no skills/ai-task/state.py); run install.sh --target %s"
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


CLOSING_COMMANDS = {"done", "close"}


def guard_rejected(root, args):
    """A rejection is a wall, not a cleared flag.

    reject consumes the request, so without this the very next command could
    finish the task the human just refused. It stops only the commands that
    would close it — going back to implementation to address the rejection is
    the whole point — and a new `stage human_approval` clears it, because asking
    again is how a rejection is answered.
    """
    if args.command not in CLOSING_COMMANDS and args.stage_argument != "done":
        return
    if getattr(args, "abandon", False):
        return                            # abandoning a refused task is allowed
    state = load(root, required=False, claim=False)
    if not state or not (state.get("human_approval") or {}).get("rejected_at"):
        return
    die("APPROVAL_REFUSED — this task was rejected at %s and has not been approved since. "
        "Address the rejection and run 'state.py stage human_approval' to ask again, or close "
        "it with 'state.py done --abandon'."
        % state["human_approval"]["rejected_at"], 5)


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
        if not any(line.startswith("# Questions") for line in lines):
            lines = (QUESTIONS_HEADER % state["task_id"]).rstrip("\n").split("\n") + lines
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
        die("APPROVAL_REFUSED — no gate was requested: run 'state.py stage human_approval' "
            "after presenting the plan.", 5)
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
        die("APPROVAL_REFUSED — no gate was requested: run 'state.py stage human_approval' "
            "after presenting the plan.", 5)
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


def cmd_done(args, root):
    abandoned = bool(getattr(args, "abandon", False))
    state = load(root)
    state["current_stage"] = "done"
    state["next_action"] = "none — task abandoned" if abandoned else "none — task closed"
    emit(root, state, "task_closed", "abandoned" if abandoned else "",
         {"abandoned": abandoned})
    set_resume_point(state)
    write_handoff(root, state, "stage")
    save(root, state)
    print("%s %s" % (state["task_id"], "abandoned" if abandoned else "closed"))


def cmd_archive(_args, root):
    state = load(root)
    target_dir = os.path.join(root, ".ai", "reports", state["task_id"])
    os.makedirs(target_dir, exist_ok=True)
    target = os.path.join(target_dir, "state.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    try:
        os.remove(handoff_path(root))     # before the point of no return, and never fatal
    except OSError:
        pass
    os.remove(state_path(root))
    print(target)


# ---------------------------------------------- the schema-7 surface (redesign 2.2a)
#
# Beside the commands above, not instead of them: /ai-task calls those until the
# skills move (2.3), and they are deleted only in 2.6. Only `start` writes
# "schema": 7, and main() sends close, step-done and approve here only for such
# a task, so a task in flight on the old surface — migration 0007 patched or
# not — keeps the old bodies untouched (D1). The legacy keys the scope guard
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
SCHEMA_ONLY = {"start", "verify", "review", "status"}
V7_ROUTED = {"close", "step-done", "approve"}
# The old surface's own commands: on a schema-7 task they would read keys it
# does not keep, so they refuse rather than half-work.
OLD_ONLY = {"init", "stage", "risk", "triage", "quick", "plan", "remediate", "step",
            "step-split", "test-run", "review-gate", "set", "risks", "modules", "done", "archive"}


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
        state["questions"] = {"file": ".ai/reports/%s/questions.md" % task_id, "pending": []}
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
        die("task %s runs on the old surface (schema %s): it keeps test-run, set and close until "
            "it closes; the schema-7 commands start with 'state.py start'"
            % (state.get("task_id"), state.get("schema") or "<7"))
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


def rescore(root, base_tree, files, current, policy):
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
    """The legacy view ai-scope-guard.sh reads (D2): stage implementation and one
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
    got = rescore(root, state["diff"].get("base_tree"), [d["path"] for d in diff], current, policy)
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
    os.remove(state_path(root))
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
    """A pure function of the state and the journal: eight sections (§Interfaces)."""
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
    pending = (state.get("questions") or {}).get("pending") or []
    asked = any(e.get("event") in ("question_asked", "gate_requested") for e in events)
    out += ["", "## Questions", "",
            ("[questions.md](questions.md) — %d pending" % len(pending)) if asked or pending else "none"]
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
    the state is the contract and task.md is rendered from it."""
    path = task_md_path(root, state)
    tmp = "%s.%d.tmp" % (path, os.getpid())
    try:
        text = "\n".join(task_md_lines(root, state)) + "\n"
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    except Exception as exc:  # pylint: disable=broad-exception-caught  # derived artefact: never fatal
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        print("state.py: task.md not written (%s)" % exc, file=sys.stderr)


def route_surface(root, args):
    """D1: close, step-done and approve take the schema-7 path only for a task
    `start` wrote; the old surface's own commands refuse such a task, and the
    new ones refuse a task the old surface started."""
    if args.command not in V7_ROUTED | OLD_ONLY | SCHEMA_ONLY - {"start", "status"}:
        return
    state = load(root, required=False, claim=False)
    if state is None:
        return
    if is_v7(state):
        if args.command in OLD_ONLY:
            die("task %s runs on the schema-7 surface: '%s' is the old one — use start, verify, review "
                "and close" % (state.get("task_id"), args.command))
        args.v7 = True                    # close handles a rejection itself (cmd_close_v7)
        args.func = {"close": cmd_close_v7, "step-done": cmd_step_done_v7,
                     "approve": cmd_approve_v7}.get(args.command, args.func)
    elif getattr(args, "abandon", False) and args.command == "close":
        die("close --abandon is for a schema-7 task; this one closes with 'state.py done --abandon' "
            "then 'state.py archive'")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--root", default=".", help="project directory (default: search upwards for .ai/)")
    parser.add_argument("--runtime", choices=RUNTIMES,
                        help="overrides AI_RUNTIME and detection for this call")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init"); p.add_argument("--goal", required=True)
    p.add_argument("--workflow", required=True); p.add_argument("--task-id")
    p.add_argument("--force", action="store_true"); p.set_defaults(func=cmd_init)

    p = sub.add_parser("get"); p.add_argument("--field")
    p.add_argument("--quiet", action="store_true"); p.set_defaults(func=cmd_get)

    p = sub.add_parser("stage"); p.add_argument("stage"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_stage)

    p = sub.add_parser("risk"); p.add_argument("tier"); p.add_argument("--note", default="")
    p.add_argument("--by", default="", help="required, with a terminal, to LOWER a tier")
    p.set_defaults(func=cmd_risk)

    p = sub.add_parser("triage"); p.add_argument("tier"); p.add_argument("--note", default="")
    p.add_argument("--by", default="", help="required, with a terminal, to LOWER a tier")
    p.add_argument("--context", default=""); p.set_defaults(func=cmd_triage)

    p = sub.add_parser("quick"); p.add_argument("--goal", required=True)
    p.add_argument("--workflow", required=True); p.add_argument("--tier", required=True)
    p.add_argument("--files", required=True); p.add_argument("--note", default="")
    p.add_argument("--tests", default="", help="the step's own tests: its required_tests")
    p.add_argument("--context", default=""); p.add_argument("--task-id")
    p.add_argument("--force", action="store_true"); p.set_defaults(func=cmd_quick)

    p = sub.add_parser("plan"); p.add_argument("--ref", required=True)
    p.add_argument("--steps", required=True); p.set_defaults(func=cmd_plan)

    p = sub.add_parser("remediate"); p.add_argument("--files", default="")
    p.add_argument("--tests", default="", help="the batch's own tests: its required_tests")
    p.add_argument("--closes", default="",
                   help="finding labels from review-report.md this batch fixes (H1,M2)")
    p.add_argument("--by", default="", help="required, with a terminal, past remediation_rounds")
    p.add_argument("--note", default=""); p.set_defaults(func=cmd_remediate)

    p = sub.add_parser("step"); p.add_argument("step_id"); p.set_defaults(func=cmd_step)
    p = sub.add_parser("step-done"); p.add_argument("step_id")
    p.add_argument("--force", action="store_true",
                   help="record the step although the diff gate refused it; say why in the plan")
    p.set_defaults(func=cmd_step_done)
    p = sub.add_parser("review-gate")
    p.add_argument("--no-bite", action="store_true", dest="no_bite",
                   help="skip the slow sensor; it then blocks the skip as unavailable")
    p.set_defaults(func=cmd_review_gate)
    p = sub.add_parser("test-run")
    p.add_argument("--scope", required=True, choices=["step", "suite", "e2e", "all"])
    p.add_argument("--files", default="")
    p.add_argument("--e2e", nargs=2, metavar=("not-applicable", "WHY"),
                   help="with --scope all: run the suite only and record e2e as not applicable")
    p.add_argument("--env-retry", action="store_true", dest="env_retry")
    p.set_defaults(func=cmd_test_run)
    p = sub.add_parser("step-split"); p.add_argument("step_id")
    p.add_argument("--files", required=True); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_step_split)

    p = sub.add_parser("set"); p.add_argument("field"); p.add_argument("value")
    p.add_argument("--by", default="",
                   help="review_status only: the human's verdict, from a terminal, past the budget")
    p.set_defaults(func=cmd_set)

    p = sub.add_parser("risks"); p.add_argument("--add"); p.add_argument("--clear", action="store_true")
    p.set_defaults(func=cmd_risks)

    p = sub.add_parser("modules"); p.add_argument("module", nargs="+"); p.set_defaults(func=cmd_modules)

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

    p = sub.add_parser("profile"); p.add_argument("--field")
    p.add_argument("--tier", choices=["FAST", "BALANCED", "STRONG", "EXPERT"])
    p.add_argument("--other", action="store_true"); p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_profile)

    p = sub.add_parser("weight"); p.add_argument("--files", default="")
    p.add_argument("--goal", default=""); p.add_argument("--declare", action="append", default=[])
    out = p.add_mutually_exclusive_group()
    out.add_argument("--json", action="store_true"); out.add_argument("--long", action="store_true")
    out.add_argument("--mirror", action="store_true"); p.set_defaults(func=cmd_weight)

    p = sub.add_parser("note"); p.add_argument("kind"); p.add_argument("text")
    p.add_argument("--why", default=""); p.add_argument("--error", default="")
    p.set_defaults(func=cmd_note)

    p = sub.add_parser("event"); p.add_argument("type"); p.add_argument("--detail", default="")
    p.add_argument("--data"); p.set_defaults(func=cmd_event)

    p = sub.add_parser("events"); p.add_argument("--last", type=int, default=20,
                                                 help="0 prints every line")
    p.add_argument("--type"); p.add_argument("--task")
    p.add_argument("--format", choices=["lines", "jsonl"], default="lines")
    p.set_defaults(func=cmd_events)

    p = sub.add_parser("approve"); p.add_argument("--by", required=True)
    p.add_argument("--note", default="")
    p.add_argument("--confirm", default="", help="schema 7: the operation a full_irreversible task performs")
    p.set_defaults(func=cmd_approve)

    p = sub.add_parser("reject"); p.add_argument("--by", required=True)
    p.add_argument("--why", required=True); p.set_defaults(func=cmd_reject)

    p = sub.add_parser("done"); p.add_argument("--abandon", action="store_true")
    p.set_defaults(func=cmd_done)
    p = sub.add_parser("archive"); p.set_defaults(func=cmd_archive)
    p = sub.add_parser("close")
    p.add_argument("--abandon", action="store_true", help="schema 7: archive without the checks")
    p.set_defaults(func=cmd_close)

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
    args.stage_argument = getattr(args, "stage", None)
    if args.command in BLOCKING_COMMANDS and not getattr(args, "abandon", False):
        guard_pending(root, args.command)
    if not getattr(args, "v7", False):
        guard_rejected(root, args)
    args.func(args, root)


if __name__ == "__main__":
    main()
