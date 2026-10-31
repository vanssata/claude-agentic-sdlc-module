"""locks: the two locks that serialise writers of the questions file and the consent ledger.

LOCK_DEPTH: shell
question_lock: shell
LOCK_STALE: core
ledger_lock: shell
"""
import contextlib
import os
import time

try:
    import fcntl
except ImportError:                       # not POSIX: the journal falls back to O_APPEND alone
    fcntl = None


# One counter per process, held in a list changed in place: `global` is refused under
# rr_state/ (R4), and a per-object counter would deadlock on the second descriptor
# (the gate locks the questions file and write_task_md locks it again inside).
LOCK_DEPTH = [0]


@contextlib.contextmanager
def question_lock(path):
    """The questions are read, modified and written back. Without a lock across
    that window two `ask` calls lose a block — and the journal would then name a
    question the file does not hold, which nothing would ever block on.

    Re-entrant within the process: flock is per open file description, so a
    nested acquisition on a second fd would wait for the first for ever. That is
    what lets the gate decide and apply inside one critical section."""
    directory = os.path.dirname(path)
    os.makedirs(directory, exist_ok=True)
    if fcntl is None or LOCK_DEPTH[0]:
        LOCK_DEPTH[0] += 1
        try:
            yield
        finally:
            LOCK_DEPTH[0] -= 1
        return
    # The lock is taken on the directory itself, so the audit trail gains no
    # lock file and the lock survives the os.replace that swaps the inode.
    try:
        fd = os.open(directory, os.O_RDONLY)
    except OSError:
        yield
        return
    LOCK_DEPTH[0] += 1
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        LOCK_DEPTH[0] -= 1
        os.close(fd)


LOCK_STALE = 2.0


@contextlib.contextmanager
def ledger_lock(root):
    """consent.lock by O_EXCL, portable where flock is not; a lock older than
    LOCK_STALE belongs to a writer that died and is taken over (R36.6)."""
    path = os.path.join(root, ".ai", "state", "consent.lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    deadline = time.time() + 3 * LOCK_STALE
    while True:
        try:
            os.close(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600))
            break
        except FileExistsError:
            with contextlib.suppress(OSError):
                if time.time() - os.stat(path).st_mtime > LOCK_STALE:
                    os.remove(path)
                    continue
            if time.time() > deadline:
                raise OSError("consent.lock is held and cannot be taken over") from None
            time.sleep(0.02)
    try:
        yield
    finally:
        with contextlib.suppress(OSError):
            os.remove(path)
