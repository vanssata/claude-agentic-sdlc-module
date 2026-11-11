"""Status and show: the lines `state.py memory status` prints and the rendering of one task's record."""
import os

import memory_compact as mc
import memory_config as mcfg
import memory_export as mexp
import memory_format as mf
import memory_hook as mhook
import memory_io as mio
import memory_packages as mpkg


def status_lines(root):
    cfg = mcfg.load_config(root)
    packages = mpkg.load_packages(root)
    size = sum(os.path.getsize(os.path.join(mio.memory_dir(root), n)) for n in packages)
    books = mpkg.read_batches(root)
    branch = mio.current_branch(root)
    pending = mexp.pending_ids(root, cfg) if cfg.packages else []
    legacy = unmigrated(root, packages)
    lines = ["mode: %s%s" % (cfg.mode, "" if cfg.present else " (no %s)" % mio.POLICY_REL),
             "period: %s · author: %s · index: %s%s" % (cfg.period, cfg.author, cfg.index, fts_line(cfg)),
             "open batch: %s" % (books["open"].get(branch) or "none") + " (branch %s)" % branch,
             "packages: %d · %s bytes" % (len(packages), mf.fmt_n(size)),
             "closed, not exported: %s" % (", ".join(pending) if pending else "none"),
             "legacy, not migrated: %d%s" % (len(legacy), " — state.py memory migrate --report" if legacy else ""),
             "pre-push: %s" % mhook.hook_state(root), "cleanup: %s" % ("on" if cfg.cleanup else "off")]
    return lines


def fts_line(cfg):
    if cfg.index != "sqlite":
        return ""
    import memory_store  # pylint: disable=import-outside-toplevel
    if memory_store.fts5_available():
        return " · fts5: yes"
    import sqlite3  # pylint: disable=import-outside-toplevel
    return " · FTS5 unavailable in this SQLite %s: search scans; results identical, slower" % sqlite3.sqlite_version


def unmigrated(root, packages):
    sealed = mpkg.sealed_task_ids(packages)
    reports = os.path.join(root, ".ai", "reports")
    out = []
    for name in sorted(os.listdir(reports)) if os.path.isdir(reports) else []:
        path = os.path.join(reports, name, "events.jsonl")
        if mf.LEGACY_ID_RE.match(name) and name not in sealed and b'"task_closed"' in (mio.read_bytes(path) or b""):
            out.append(name)
    return out


def show(root, task_id, fmt="md", rid=None):
    import memory_store  # pylint: disable=import-outside-toplevel
    cfg = mcfg.load_config(root)
    history = memory_store.open_history(root, cfg)
    if rid:
        found = [e for e in history.all_entries() if e.get("rid") == rid]
        if not found:
            raise mio.MemoryError_("no entry %s" % rid, 1)
        return [mf.canonical(found[0]).decode("utf-8")]
    if task_id == memory_store.current_task(root):
        found = mc.compact_instances(mc.FsReader(root), task_id, "tracked", cfg.excerpt_max_bytes)
        entries = [e for c in found for e in c.entries]
        lines = ["# %s — in flight — live state ('state.py status' is the authority)" % task_id, ""]
        return lines + mf.render_task_md(entries)[1:] if fmt == "md" else \
            [mf.canonical(e).decode("utf-8") for e in entries]
    entries = history.entries(task_id)
    if not entries:
        raise mio.MemoryError_("nothing recorded for %s" % task_id, 1)
    if fmt == "json":
        return [mf.canonical(e).decode("utf-8") for e in entries]
    out = []
    for inst in sorted({e.get("inst") for e in entries}):
        out += mf.render_task_md([e for e in entries if e.get("inst") == inst])
    return out
