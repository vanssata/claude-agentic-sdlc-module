"""Export at close (§D5): the outbox, the compaction of a task into a package, the export itself, the
lines it reports, the pending ids and the close hook."""
import collections
import contextlib
import json
import os

import memory_cleanup as mclean
import memory_compact as mc
import memory_config as mcfg
import memory_format as mf
import memory_io as mio
import memory_packages as mpkg


# ------------------------------------------------------------------ export (§D5)
def outbox_path(root, key):
    task, inst = key.rsplit("#", 1)
    return mio.local_path(root, "outbox", "%s~%s.jsonl" % (task, inst))


def exportable(compactions):
    return [c for c in compactions if c.seal and c.seal["result"] in ("closed", "abandoned", "restarted")]


ExportResult = collections.namedtuple("ExportResult",
                                      "package added sealed coverage failures conflicts already added_by_key")


def compact_for_export(root, task_id, cfg):
    found = mc.compact_instances(mc.FsReader(root), task_id, "close", cfg.excerpt_max_bytes)
    problems = [p for c in found for p in c.problems if "torn journal" not in p]
    if problems:
        raise mio.MemoryError_(problems[0], 3)
    ready = exportable(found)
    if not ready:
        raise mio.MemoryError_("%s has no closed instance to export" % task_id, 3)
    return ready


def write_outbox(root, compaction):
    key = mf.key_of(compaction.seal)
    lines = [mf.canonical(e) for e in compaction.entries + [compaction.seal]]
    mio.atomic_write(outbox_path(root, key), b"\n".join(lines) + b"\n")
    return key


def read_outbox(root):
    base = mio.local_path(root, "outbox")
    out = {}
    for name in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if not name.endswith(".jsonl"):
            continue
        entries = []
        for raw in (mio.read_bytes(os.path.join(base, name)) or b"").split(b"\n"):
            if raw.strip():
                with contextlib.suppress(ValueError, UnicodeDecodeError):
                    entries.append(json.loads(raw.decode("utf-8")))
        seals = [e for e in entries if e.get("kind") == "task"]
        if seals:
            out[mf.key_of(seals[-1])] = entries
    return out


def export(root, ids, cfg=None, stamp=None):
    """B2–B4 for every id (or the pending ones); returns ExportResult. A
    failure of one task keeps its outbox and is reported, never raised."""
    cfg = cfg or mcfg.load_config(root)
    if not cfg.packages:
        raise mio.MemoryError_("files mode: nothing is exported ('state.py memory enable' turns packages on)")
    failures, coverage, sealed, already, added_by_key = [], {}, [], [], {}
    if ids == "pending":
        ids = pending_ids(root, cfg)
    ids = list(ids)
    # A key with a seal in the tree is never sealed again from other sources: a
    # second compaction of changed local sources (a restarted id, a cleaned-up
    # directory) would add a degraded seal to an append-only record (R8, R9).
    # The same seal is a repair: the rids it lacks come back, nothing else (V4, V5).
    sealed_here = mpkg.seals_by_key(mpkg.load_packages(root))
    for task_id in ids:
        try:
            for compaction in compact_for_export(root, task_id, cfg):
                key = mf.key_of(compaction.seal)
                coverage[key] = compaction.coverage
                stored = {s["rid"] for _, s in sealed_here.get(key, [])}
                if stored and compaction.seal["rid"] not in stored:
                    already.append(key)
                    continue
                write_outbox(root, compaction)
        except mio.MemoryError_ as exc:
            failures.append((task_id, str(exc)))
        except OSError as exc:
            failures.append((task_id, "the outbox could not be written (%s)" % exc))
    mio.crash("B2")
    added, conflicts, name = 0, [], None
    try:
        with mio.locked(root):
            outbox = read_outbox(root)    # under the lock: another close may have taken it
            packages = mpkg.load_packages(root)
            have = mpkg.all_rids(packages)
            seals = mpkg.seals_by_key(packages)
            recorded = {e.get("key"): set(e.get("rids") or []) for _, entries, _ in packages.values()
                        for e in entries if e.get("kind") == "conflict"}
            new, keep = [], {}
            for key, entries in outbox.items():
                seal_rid = [e for e in entries if e.get("kind") == "task"][-1]["rid"]
                stored = {s["rid"] for _, s in seals.get(key, [])}
                missing = [e for e in entries if e["rid"] not in have]
                if (stored and seal_rid not in stored) or not missing:
                    # Sealed meanwhile from other sources, or nothing lacking (a re-run, B4).
                    os.remove(outbox_path(root, key))
                    if key not in already:
                        already.append(key)
                    continue
                new += missing
                added_by_key[key] = len(missing)
                keep[key] = entries
            for key in coverage:
                if key in seals and key not in keep and key not in already:
                    already.append(key)   # another close took this outbox and sealed it (review L3)
            for key, found in sorted(seals.items()):
                # Two seals that arrived by a merge (one id closed in two clones):
                # recorded side by side, never merged (R9).
                rids = sorted({s["rid"] for _, s in found} - {s.get("supersedes") for _, s in found})
                if len(rids) < 2 or key.rsplit("#", 1)[0] not in ids or set(rids) <= recorded.get(key, set()):
                    continue
                seal = found[-1][1]
                conflict = mf.with_rid({
                    "v": mf.FORMAT, "task": seal["task"], "inst": seal["inst"], "seq": seal["seq"] + 1,
                    "kind": "conflict", "ts": max(s["ts"] for _, s in found), "actor": "agent", "by": None,
                    "runtime": seal["runtime"], "src": ["export"], "key": key, "rids": rids,
                    "reason": "two different seals for one key — kept side by side, never merged"})
                if conflict["rid"] not in have:
                    new.append(conflict)
                conflicts.append(key)
            if not new:
                return ExportResult(None, 0, sealed, coverage, failures, conflicts, already, added_by_key)
            name, branch, books = mpkg.open_batch(root, cfg, stamp)
            path = os.path.join(mio.memory_dir(root), name)
            header, current, _ = packages.get(name, (None, [], []))
            parts = mf.parse_package_name(name)
            header = header or mf.package_header(parts["period"], cfg.author, parts["batch"], stamp or mio.now())
            current = [mf.strip_private(e) for e in current]
            outbox = keep
            if new:
                data = mf.render_package(header, current + new)
                mio.crash("B3")
                mio.atomic_write(path, data)
                added = len(new)
                books["open"][branch] = name
                mpkg.write_batches(root, books)
            mio.crash("B4")
            check = mpkg.load_packages(root)
            present = mpkg.all_rids(check)
            for key, entries in outbox.items():
                seal = [e for e in entries if e.get("kind") == "task"][-1]
                if all(e["rid"] in present for e in entries):
                    os.remove(outbox_path(root, key))
                    sealed.append(key)
                else:
                    failures.append((seal["task"], "read-back found %d of %d entries" % (
                        sum(e["rid"] in present for e in entries), len(entries))))
    except OSError as exc:
        failures.append((",".join(sorted(coverage)) or "the outbox",
                         "%s (%s)" % (exc.strerror or exc, getattr(exc, "filename", ""))))
    if added and cfg.index == "sqlite":
        mio.crash("B5")
        index_import(root, cfg)
    return ExportResult(name, added, sealed, coverage, failures, conflicts, already, added_by_key)


def record_lines(result):
    """What close and `memory export` print: each key newly sealed with what it
    added, each key that was already sealed, each conflict recorded (review L5)."""
    out = []
    for key in result.sealed:
        cov = result.coverage.get(key) or {}
        out.append("record: %s (+%d entries, %s sealed, coverage %s/%s lines)" % (
            os.path.join(mio.MEMORY_REL, result.package or "-"), result.added_by_key.get(key, 0),
            key.rsplit("#", 1)[0], cov.get("accounted", "?"), cov.get("lines", "?")))
    for key in result.already:
        out.append("record: %s already sealed in %s — nothing added" % (key, mio.MEMORY_REL))
    for key in result.conflicts:
        out.append("conflict: %s has two different seals — recorded side by side, never merged "
                   "('state.py memory show %s')" % (key, key.rsplit("#", 1)[0]))
    return out


def index_import(root, cfg):
    """B5: the index learns the new package; any failure marks it stale."""
    try:
        import memory_store  # pylint: disable=import-outside-toplevel
        memory_store.SqliteHistory(root, cfg).refresh()
    except Exception:  # pylint: disable=broad-except  # a stale index is rebuilt by the next read
        with contextlib.suppress(Exception):
            import memory_store  # pylint: disable=import-outside-toplevel
            memory_store.mark_stale(root)


def pending_ids(root, cfg=None):
    """Closed new-shape tasks (and anything in the outbox) without a seal:
    B1 left them closed but not exported. Legacy ids wait for the migration."""
    sealed = mpkg.sealed_task_ids(mpkg.load_packages(root))
    found = set(k.rsplit("#", 1)[0] for k in read_outbox(root))
    logs = os.path.join(root, ".ai", "state", "logs")
    for name in os.listdir(logs) if os.path.isdir(logs) else []:
        if not mf.NEW_ID_RE.match(name) or name in sealed:
            continue
        with contextlib.suppress(OSError, ValueError):
            state = mio.read_json(os.path.join(logs, name, "state.json"))
            if state.get("result") in ("closed", "abandoned"):
                found.add(name)
    del cfg
    return sorted(found - sealed)


def after_close(root, task_id, out=print):
    """The one call close makes after archive_v7. Packages mode only; every
    failure is one printed line and close still exits 0 (B4)."""
    try:
        cfg = mcfg.load_config(root)
    except mio.MemoryError_ as exc:
        out("memory: %s — the task is closed in files mode" % exc)
        return None
    if not cfg.packages:
        return None
    try:
        pending = [t for t in pending_ids(root, cfg) if t != task_id][:mio.PENDING_MAX]
        result = export(root, [task_id] + pending, cfg)
    except (mio.MemoryError_, ValueError, OSError) as exc:
        out("memory: export of %s failed (%s) — the task is closed; 'state.py memory export %s' retries"
            % (task_id, exc, task_id))
        return None
    for failed, why in result.failures:
        out("memory: export of %s failed (%s) — the task is closed; 'state.py memory export %s' retries"
            % (failed, why, failed))
    for line in record_lines(result):
        out(line)
    if cfg.cleanup and any(k.rsplit("#", 1)[0] == task_id for k in result.sealed + result.already):
        mio.crash("B6")
        try:
            done = mclean.cleanup_task(root, task_id, cfg)
            out("cleanup: %s" % done)
        except mio.MemoryError_ as exc:
            out("cleanup: %s kept in .ai/reports/ (%s)" % (task_id, exc))
    return result
