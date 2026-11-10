"""The store: where the state, the session, the journal and the logs live, and the clock, the root search and the one subprocess runner.

shell: ENTRY, now, now_ms, find_root, find_root_quiet, die, state_path, remove_state, read_session, safe_sensor, find_docs_root, questions_path, read_lines, run_text, read_text, current_tree, ensure_logs
core: session_path, journal_path, _split_files, SLUG_RE, one_line, handoff_path, decision_path, ledger_path, logs_dir, task_md_path
"""

import contextlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone

try:
    import sensors                        # measurement only; it never writes this file
except ImportError:                       # an old install that shipped state.py alone
    sensors = None

ENTRY = ""      # the entry's path: the entry sets it (fs.ENTRY = os.path.abspath(__file__)), code here reads it at call time


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
            die("no .ai/ directory found above %s — run /rr-setup first" % start)
        d = parent


def find_root_quiet(start):
    """find_root without the refusal: profile runs where there is no .ai/."""
    d = os.path.abspath(start or ".")
    while not os.path.isdir(os.path.join(d, ".ai")):
        if os.path.dirname(d) == d:
            return None
        d = os.path.dirname(d)
    return d


def die(message, code=1):
    """1 validation · 2 argparse · 4 QUESTIONS_PENDING · 5 APPROVAL_REFUSED ·
    6 SCOPE_CHANGE_REQUIRED / run budget / REVIEW_BUDGET (I1, WP4 I4) ·
    7 RUNTIME_HANDOFF_PENDING · 8 DIRECT_MODE_CAP (WP5 I4; one meaning per code)."""
    print("state.py: %s" % message, file=sys.stderr)
    sys.exit(code)


def state_path(root):
    """The task's state file: state.json, the only name read."""
    return os.path.join(root, ".ai", "state", "state.json")


def remove_state(root):
    with contextlib.suppress(FileNotFoundError):
        os.remove(os.path.join(root, ".ai", "state", "state.json"))


def session_path(root):
    return os.path.join(root, ".ai", "state", "session.json")


def ai_unattended():
    """AI_UNATTENDED is set when it is non-empty and not 0, false or no (case
    and blanks ignored): one rule in every reader (risk 0587)."""
    return os.environ.get("AI_UNATTENDED", "").strip().lower() not in ("", "0", "false", "no")


def read_session(root):
    """The hook's sidecar (I5). Absent, half-written or unreadable is normal."""
    try:
        with open(session_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, RecursionError):
        return {}
    return data if isinstance(data, dict) else {}


def journal_path(root, task_id):
    return os.path.join(root, ".ai", "reports", task_id, "events.jsonl")


def safe_sensor(call, *args, **kwargs):
    """A bug in a sensor must never be able to stop a task. Anything unexpected
    reads as 'unavailable', which keeps every review the tier asked for."""
    if sensors is None:
        return None
    try:
        return call(*args, **kwargs)
    except Exception:                     # pylint: disable=broad-except
        return None


def _split_files(text):
    return [f.strip() for f in (text or "").split(",") if f.strip()]


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
            die("no docs/sdlc/ directory found above %s — run /rr-spec first" % start)
        d = parent


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def questions_path(root, state, topic):
    if topic:
        # Topic mode is the one writer that runs without .ai/ and therefore
        # without the path guard, so the slug is validated here rather than
        # trusted: it names a file, it never steers one.
        if not SLUG_RE.match(topic):
            die("--topic takes a slug of lowercase letters, digits and hyphens, not %r" % topic)
        return os.path.join(root, "docs", "sdlc", "intent", "%s.questions.md" % topic)
    return task_md_path(root, state)


def read_lines(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read().split("\n")
    except OSError:
        return None


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


def handoff_path(root):
    return os.path.join(root, ".ai", "state", "handoff.md")


def decision_path(root):
    return os.path.join(root, ".ai", "state", "decision.json")


def ledger_path(root):
    return os.path.join(root, ".ai", "state", "consent.jsonl")


def run_text(root, argv):
    try:
        return subprocess.run(argv, cwd=root, capture_output=True, text=True, check=False,
                              timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def read_text(root, rel):
    try:
        with open(os.path.join(root, rel), "rb") as fh:
            data = fh.read(1 << 20)
    except OSError:
        return ""
    return "" if b"\0" in data[:8192] else data.decode("utf-8", "replace")


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
