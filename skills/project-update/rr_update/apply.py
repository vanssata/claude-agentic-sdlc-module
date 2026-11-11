"""Writing the plan: the preconditions, the atomic write, the record of what was taken away, and the abort.

shell: current_sha, check, default_mode, write_file, keep_original, record_run, apply, apply_item, prune_empty
core: Abort
"""

import json
import os
import tempfile
from collections import OrderedDict

from rr_update import files
from rr_update import paths


class Abort(Exception):
    """A precondition failed: the project is not what the dry run described."""

    def __init__(self, item, why):
        super().__init__(why)
        self.item, self.why = item, why


def current_sha(root, target):
    """The sha of a target now, or None when it is absent. A path that is not a
    regular file has no content this tool may replace."""
    path = os.path.join(root, target)
    if os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):
        raise Abort(None, "%s is not a regular file" % target)
    return files.sha(files.read(path)) if os.path.isfile(path) else None


def check(plan, item, target, expect, written):
    """The target must still be what the dry run read, or what this run wrote."""
    try:
        now_sha = current_sha(plan.root, target)
    except Abort as exc:
        raise Abort(item, exc.why) from exc
    want = written.get(target, expect)
    if now_sha != want:
        raise Abort(item, "%s changed since the dry run read it" % target)


def default_mode():
    mask = os.umask(0)
    os.umask(mask)
    return 0o666 & ~mask


def write_file(root, target, content, mode=None):
    """Atomic, like state.py: a crash leaves the old file or the new one, never
    half of one. The temp file is created with mkstemp in the target's directory,
    so a planted name cannot redirect the write, and a symlinked target is
    refused rather than followed. The target keeps the mode it had. A symlinked
    *directory* on the way to it is still followed, as every writer here always
    has."""
    path = os.path.join(root, target)
    if os.path.islink(path) or (os.path.exists(path) and not os.path.isfile(path)):
        raise Abort(None, "%s is not a regular file" % target)
    parent = os.path.dirname(path) or "."
    os.makedirs(parent, exist_ok=True)
    if mode is None:
        mode = os.stat(path).st_mode & 0o7777 if os.path.isfile(path) else default_mode()
    fd, tmp = tempfile.mkstemp(dir=parent, prefix=os.path.basename(path) + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def keep_original(plan, target):
    """A faithful copy of what a move or a delete takes away, mode included.
    Nothing else is ever lost, so nothing else is copied."""
    path = os.path.join(plan.root, target)
    write_file(plan.root, os.path.join(plan.report_dir, "original", target),
               files.read(path), mode=os.stat(path).st_mode & 0o7777)



def record_run(plan, ops, deletions):
    """The record of what was taken away or overwritten, rewritten after every such operation:
    an abort must not lose the note of a change a human approved. A second run on the same
    day appends to the record instead of replacing it."""
    path = os.path.join(plan.report_dir, "migration.json")
    existing = {}
    full = os.path.join(plan.root, path)
    if os.path.isfile(full):
        try:
            existing = json.loads(files.read(full), object_pairs_hook=OrderedDict)
        except (ValueError, RecursionError):  # too deep reads as malformed
            existing = {}
        if not isinstance(existing, dict):  # hand-edited into another shape
            existing = {}
    record = OrderedDict()
    record["from"] = existing.get("from", plan.version_from)
    # The version the project is actually at now, read from the disk: this record is
    # written before the files change, and an aborted run never reaches the template's.
    version_path = os.path.join(plan.root, paths.VERSION_FILE)
    on_disk = files.read(version_path).decode().strip() if os.path.isfile(version_path) else ""
    record["to"] = int(on_disk) if on_disk.isdigit() else record["from"]
    record["applied_at"] = files.utc_now()
    # A recovery re-run replays the same operation: record it once.
    record["ops"] = list(existing.get("ops", []))
    record["ops"] += [o for o in ops if o not in record["ops"]]
    record["deletions"] = list(existing.get("deletions", []))
    record["deletions"] += [d for d in deletions
                            if not any(e.get("path") == d["path"] for e in record["deletions"])]
    if existing and all(existing.get(k) == record[k] for k in ("from", "to", "ops", "deletions")):
        return  # a run that changed nothing leaves the record as it was
    write_file(plan.root, path, files.dump_json(record))


def apply(plan):
    """Write the plan, in order. Every item checks its target first; a violation
    or a failed write aborts before the next item, leaving everything after it
    unwritten. Every operation is idempotent, so the re-run is the recovery."""
    written, recorded = {}, []
    for item in plan.items:
        try:
            apply_item(plan, item, written, recorded)
        except Abort as exc:
            raise Abort(exc.item or item, exc.why) from exc
        except OSError as exc:
            raise Abort(item, str(exc)) from exc
    # The run finished: say which version it actually reached.
    try:
        if recorded or os.path.isfile(os.path.join(plan.root, plan.report_dir, "migration.json")):
            record_run(plan, [], [])
    except OSError as exc:
        raise Abort(None, str(exc)) from exc


def apply_item(plan, item, written, recorded):
    target, action = item["target"], item["action"]
    reason = item.get("reason") or ""
    cleanup = reason.startswith("[cleanup]")
    if action in ("delete?", "regenerate?"):  # listed only, until a human confirms it
        return
    by = dict(confirmed_by=plan.confirm_cleanup if cleanup else plan.confirm_delete,
              via=plan.cleanup_via if cleanup else plan.confirm_via, at=files.utc_now())
    if action == "delete":
        # the plan-time symlink check is repeated: a path swapped since is refused
        why = files.unsafe_path(plan.root, target)
        if why:
            raise Abort(item, why)
        check(plan, item, target, item["expect"], written)
        # git-ignored task state: a [cleanup] deletion of it is NOT recoverable through git, and
        # copying what it removes would defeat the cleanup, so no original/ copy is kept. A report
        # file git tracks, or should, is kept like any other deletion.
        if not target.startswith(".ai/state/") and (not cleanup or target in plan.git_kept):
            keep_original(plan, target)
        recorded.append(target)
        # Recorded before the file is gone: an abort later must not lose the note
        # of what was taken away, or of who approved it.
        record_run(plan, [dict(action=action, path=target)], [dict(path=target, **by)])
        os.remove(os.path.join(plan.root, target))
        written[target] = None
        if reason.startswith(("[cleanup]", "[local]")):
            prune_empty(plan.root, target)
        return
    check(plan, item, target, item["expect"], written)
    if item["keep"] and item["expect"] is not None and target not in written:
        # A change a human confirmed overwrites what they wrote: keep it, so it can be read back.
        if not os.path.exists(os.path.join(plan.root, plan.original_of(target))):
            keep_original(plan, target)
        recorded.append(target)
        record_run(plan, [dict(action=action, path=target, **by)], [])
    write_file(plan.root, target, item["content"])
    written[target] = files.sha(item["content"])


def prune_empty(root, target):
    """The directories a cleanup or cache deletion left empty, up to (not including)
    .ai/reports, .ai/state/logs and .ai/local; a directory with anything in it stays."""
    top = ".ai/state/logs" if target.startswith(".ai/state/logs/") else \
        ".ai/local" if target.startswith(paths.LOCAL_CACHE + "/") else ".ai/reports"
    here = os.path.dirname(target)
    while here.startswith(top + "/"):
        try:
            os.rmdir(os.path.join(root, here))
        except OSError:
            return
        here = os.path.dirname(here)
