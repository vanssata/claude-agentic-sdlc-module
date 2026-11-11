"""Files and the two outside readers: the clock, a hash, a read, git's view of a tree, JSON bytes, a path safe to delete.

shell: utc_now, read, git_dirty_ai, git_states, unsafe_path
core: sha, dump_json
"""

import hashlib
import json
import os
import subprocess
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    with open(path, "rb") as fh:
        return fh.read()



def git_dirty_ai(root):
    """True when .ai/ has changes git does not hold yet: git is the rollback of
    a migration that deletes, so it must hold them first. False outside a work
    tree, where there is nothing to say."""
    try:
        res = subprocess.run(["git", "-C", root, "status", "--porcelain", "--", ".ai"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return res.returncode == 0 and bool(res.stdout.strip())


def git_states(root, rel_dir):
    """A function path -> how git holds a file under `rel_dir` (project-relative):
    "tracked" (committed and unchanged), "uncommitted" (changed, staged or not yet
    tracked, so git has no copy to restore) or "ignored"; None outside a work tree
    or for a path git does not know."""
    def run(*args):
        res = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=30, check=False)
        return res.stdout.decode("utf-8", "replace") if res.returncode == 0 else None
    try:
        prefix = run("rev-parse", "--show-prefix")
        tracked = run("ls-files", "-z", "--", rel_dir)
        status = run("status", "--porcelain=v1", "-z", "--ignored", "-uall", "--", rel_dir)
    except (OSError, subprocess.SubprocessError):
        return lambda path: None
    if prefix is None or tracked is None or status is None:
        return lambda path: None
    prefix = prefix.strip()
    tracked = set(tracked.split("\0"))
    dirty, ignored = set(), []
    entries = status.split("\0")
    skip = False
    for entry in entries:
        if skip:  # the origin path of a rename
            skip = False
            continue
        if len(entry) < 4:
            continue
        xy, path = entry[:2], entry[3:]
        if prefix and path.startswith(prefix):
            path = path[len(prefix):]
        if "R" in xy or "C" in xy:
            skip = True
        if xy == "!!":
            ignored.append(path)
        else:
            dirty.add(path)

    def classify(path):
        if path in dirty:
            return "uncommitted"
        if any(path == i or (i.endswith("/") and path.startswith(i)) for i in ignored):
            return "ignored"
        return "tracked" if path in tracked else None
    return classify


def dump_json(value):
    return (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode()


def unsafe_path(root, path):
    """Why a project-relative path must not be deleted: a symlink on the way to it,
    or a real path outside the project; None when it is safe. Run at plan time and
    again right before the delete."""
    real_root = os.path.realpath(root)
    here = root
    for part in path.split("/"):
        here = os.path.join(here, part)
        if os.path.islink(here):
            return "%s is a symlink" % os.path.relpath(here, root).replace(os.sep, "/")
    real = os.path.realpath(os.path.join(root, path))
    if real != real_root and not real.startswith(real_root + os.sep):
        return "%s resolves outside the project (%s)" % (path, real)
    return None

# ---------------------------------------------------------------- the one gate
