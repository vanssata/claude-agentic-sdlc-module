"""The small I/O of packages mode: the path constants, the refusal type, the clock, fault
injection, JSON and byte reads, the atomic write, the clone lock and the git runner. It imports no other
memory module; HERE is the one place that reads its own path (SELF stays the validator entry's path)."""
import contextlib
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


try:
    import fcntl
except ImportError:                       # not POSIX: last writer wins within one clone (docs/local-memory.md)
    fcntl = None

HERE = os.path.dirname(os.path.abspath(__file__))

POLICY_REL = os.path.join(".ai", "policies", "memory.json")
MEMORY_REL = os.path.join(".ai", "memory")
LOCAL_REL = os.path.join(".ai", "local", "memory")
PENDING_MAX = 5
BATCH_CHARS = "0123456789abcdefghjkmnpqrstvwxyz"
HOOK_MARKER = "# riskrails-memory-pre-push 1"
VALIDATOR = os.path.normpath(os.path.join(HERE, "..", "..", "hooks", "memory-pre-push.py"))
SELF = os.path.join(HERE, "memory_sync.py")   # the fallback validator: the entry, run as a script
FINDINGS_MAX = 40
ZERO_SHA = "0" * 40


class MemoryError_(Exception):            # pylint: disable=invalid-name  # not the builtin MemoryError
    """A refusal with its exit code (§I4: 1 findings, 2 usage, 3 aborted, 5 human, 6 scope)."""

    def __init__(self, message, code=2):
        super().__init__(message)
        self.code = code


def now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def crash(point):
    """Fault injection (A9): AI_MEMORY_CRASH_AT=B2..B6 ends the process here."""
    if os.environ.get("AI_MEMORY_CRASH_AT") == point:
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(70)                      # pylint: disable=protected-access  # a crash, not an exit


def read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


# ------------------------------------------------------------------ small I/O
def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    handle, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
    try:
        with os.fdopen(handle, "wb") as fh:
            fh.write(data if isinstance(data, bytes) else data.encode("utf-8"))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.remove(tmp)
        raise


@contextlib.contextmanager
def locked(root):
    """flock on .ai/local/memory/lock: two closes in one clone serialise here."""
    os.makedirs(os.path.join(root, LOCAL_REL), exist_ok=True)
    fd = os.open(os.path.join(root, LOCAL_REL, "lock"), os.O_RDWR | os.O_CREAT, 0o644)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def git(root, *args, stdin=None, binary=False):
    done = subprocess.run(["git", "-C", root, *args], input=stdin, capture_output=True, check=False,
                          text=not binary)
    return done.returncode, done.stdout, done.stderr


def shared(root):
    """False only when git ignores .ai/memory/ (the record is local, nothing of it travels); True when it does not,
    and when git cannot answer: the validator then keeps checking."""
    try:
        return git(root, "check-ignore", "-q", "--no-index", ".ai/memory/x")[0] != 0
    except OSError:
        return True


def current_branch(root):
    code, out, _ = git(root, "symbolic-ref", "--short", "-q", "HEAD")
    if code == 0 and out.strip():
        return out.strip()
    code, out, _ = git(root, "rev-parse", "--short=8", "HEAD")
    return "HEAD@%s" % (out.strip() if code == 0 and out.strip() else "unborn")


def memory_dir(root):
    return os.path.join(root, MEMORY_REL)


def local_path(root, *parts):
    return os.path.join(root, LOCAL_REL, *parts)


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except OSError:
        return None
